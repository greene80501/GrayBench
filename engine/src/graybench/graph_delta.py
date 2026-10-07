"""Versioned incremental frames over the existing full graph validation contract.

This reduces wire repetition, not full-state capture or private reconstruction.
No exported node is deleted. A failed send must terminate the enclosing session;
outbound snapshots advance the local base and are never implicitly retried.
"""

import hashlib
import json
from dataclasses import dataclass

from graybench.circuit_wire import WireError, WireLimitError, fields
from graybench.graph_wire import GraphArena, GraphLimits, wire_bytes


@dataclass(frozen=True)
class PreparedDelta:
    _owner: object
    _generation: int
    _snapshot: bytes
    _prepared: object

    @property
    def snapshot(self):
        return json.loads(self._snapshot)


class DeltaGraphArena:
    def __init__(self, arena, *, wire_limit):
        if type(arena) is not GraphArena or arena.anchors is None:
            raise WireError("Delta transport requires an anchored graph arena")
        GraphLimits(message_bytes=wire_limit)
        self._arena = arena
        self.limits, self.side, self.session = arena.limits, arena.side, arena.session
        self.wire_limit = wire_limit
        self._records, self._digest = {}, None
        self._owner, self._generation, self._closed = object(), 0, False

    def _open(self):
        if self._closed:
            raise WireError("Delta graph arena is closed")

    def _advance(self, raw):
        snapshot = json.loads(raw)
        self._records = {node["id"]: wire_bytes(node) for node in snapshot["nodes"]}
        self._digest = hashlib.sha256(raw).hexdigest()
        self._generation += 1

    def snapshot(self, roots, *, sequence):
        self._open()
        try:
            snapshot = self._arena.snapshot(roots, sequence=sequence)
            snapshot["nodes"].sort(key=lambda node: node["id"])
            raw = wire_bytes(snapshot)
            frame = {
                **snapshot,
                "format": "call_graph_delta_v1",
                "side": self.side,
                "base": self._digest,
                "digest": hashlib.sha256(raw).hexdigest(),
                "nodes": [
                    node
                    for node in snapshot["nodes"]
                    if self._records.get(node["id"]) != wire_bytes(node)
                ],
            }
            if len(wire_bytes(frame)) > self.wire_limit:
                raise WireLimitError("Delta graph frame exceeds wire byte limit")
            self._advance(raw)
            return frame
        except BaseException:
            # The underlying snapshot may already have allocated IDs. Never
            # resume from an uncertain local/remote base after an encoding error.
            self.close()
            raise

    def prepare(self, frame, *, sequence):
        self._open()
        raw = wire_bytes(frame)
        if len(raw) > self.wire_limit:
            raise WireLimitError("Delta graph frame exceeds wire byte limit")
        frame = json.loads(raw)
        fields(
            frame,
            {
                "format",
                "session",
                "sequence",
                "anchors",
                "roots",
                "nodes",
                "side",
                "base",
                "digest",
            },
        )
        if (
            frame["format"] != "call_graph_delta_v1"
            or frame["session"] != self.session
            or frame["side"] != ("candidate" if self.side == "judge" else "judge")
            or type(sequence) is not int
            or type(frame["sequence"]) is not int
            or frame["sequence"] != sequence
            or frame["base"] != self._digest
        ):
            raise WireError("Wrong delta graph format, session, direction, sequence or base")
        digest = frame["digest"]
        if (
            type(digest) is not str
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise WireError("Invalid delta graph digest")
        if type(frame["nodes"]) is not list or len(frame["nodes"]) > self.limits.nodes:
            raise WireLimitError("Invalid or excessive delta graph records")
        records = {key: json.loads(value) for key, value in self._records.items()}
        changed = set()
        for record in frame["nodes"]:
            fields(record, {"id", "kind", "state", "anchor"})
            handle = self._arena._handle(record["id"])
            if handle in changed:
                raise WireError("Duplicate delta graph record")
            changed.add(handle)
            records[handle] = record
        if len(records) > self.limits.nodes:
            raise WireLimitError("Expanded delta graph exceeds node limit")
        snapshot = {
            "format": "call_graph_anchors_v1",
            "session": frame["session"],
            "sequence": frame["sequence"],
            "anchors": frame["anchors"],
            "roots": frame["roots"],
            "nodes": [records[key] for key in sorted(records)],
        }
        raw = wire_bytes(snapshot)
        if len(raw) > self.limits.message_bytes:
            raise WireLimitError("Expanded delta graph exceeds state byte limit")
        if hashlib.sha256(raw).hexdigest() != digest:
            raise WireError("Delta graph result digest mismatch")
        prepared = self._arena.prepare(snapshot, sequence=sequence)
        return PreparedDelta(self._owner, self._generation, raw, prepared)

    def commit(self, prepared):
        self._open()
        if type(prepared) is not PreparedDelta or prepared._owner is not self._owner:
            raise WireError("Foreign delta graph preparation")
        if prepared._generation != self._generation:
            raise WireError("Stale delta graph preparation")
        try:
            result = self._arena.commit(prepared._prepared)
            self._advance(prepared._snapshot)
            return result
        except BaseException:
            self.close()
            raise

    def close(self):
        self._arena.close()
        self._records.clear()
        self._digest = None
        self._closed = True
        self._generation += 1
