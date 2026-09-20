"""Experimental persistent data-only object graphs; not wired into candidate calls yet."""

import json
from collections import deque
from dataclasses import dataclass

from graybench.circuit_wire import WireError, WireLimitError, fields
from graybench.graph_types import (
    REGISTRY,
    SCALAR_MISSING,
    codec_for,
    scalar_record,
    scalar_value,
    token_value,
)


@dataclass(frozen=True)
class GraphLimits:
    nodes: int = 100_000
    edges: int = 100_000
    message_bytes: int = 1_048_576
    array_bytes: int = 524_288
    matrix_bytes: int = 524_288
    depth: int = 32

    def __post_init__(self):
        ceilings = dict(
            nodes=100_000,
            edges=100_000,
            message_bytes=16_777_216,
            array_bytes=524_288,
            matrix_bytes=524_288,
            depth=32,
        )
        if any(
            type(getattr(self, key)) is not int or not 1 <= getattr(self, key) <= maximum
            for key, maximum in ceilings.items()
        ):
            raise WireError("Invalid graph resource limit")


def wire_bytes(value):
    try:
        return json.dumps(
            value, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True
        ).encode()
    except (ValueError, TypeError, RecursionError, OverflowError) as exc:
        raise WireError("Invalid graph JSON data") from exc


@dataclass(frozen=True)
class PreparedGraph:
    _owner: object
    _generation: int
    _sequence: int
    _objects: dict
    _records: dict
    _updates: tuple
    _roots: dict
    _owned_plan: object = None
    _anchor_plan: object = None


class GraphArena:
    def __init__(self, *, side, session, limits, anchors=None):
        if side not in ("judge", "candidate"):
            raise WireError("Unknown graph owner")
        if type(session) is not str or not 1 <= len(session) <= 128:
            raise WireError("Invalid graph session")
        if type(limits) is not GraphLimits:
            raise WireError("Invalid graph limits")
        if anchors is not None:
            from graybench.graph_anchors import PublicAnchorRegistry

            if type(anchors) is not PublicAnchorRegistry:
                raise WireError("Invalid public anchor registry")
        self.anchors = anchors
        self.side, self.session, self.limits = side, session, limits
        self._prefix = "j:" if side == "judge" else "c:"
        self._objects, self._ids, self._records = {}, {}, {}
        self._next_id = self._incoming = self._outgoing = self._generation = 0
        self._owner = object()
        self._closed = False

    def _sequence(self, sequence, previous):
        if self._closed:
            raise WireError("Graph arena is closed")
        if type(sequence) is not int or not 1 <= sequence <= 1_000_000 or sequence <= previous:
            raise WireError("Stale or invalid graph sequence")

    def _handle(self, value):
        if type(value) is not str or len(value) > 12 or value[:2] not in ("j:", "c:"):
            raise WireError("Invalid graph object ID")
        suffix = value[2:]
        if not suffix.isascii() or not suffix.isdecimal() or str(int(suffix)) != suffix:
            raise WireError("Invalid graph object ID")
        if int(suffix) >= self.limits.nodes:
            raise WireLimitError("Graph object ID exceeds node limit")
        return value

    def _roots(self, roots):
        if (
            type(roots) is not dict
            or len(roots) > 1024
            or any(type(key) is not str or not 1 <= len(key) <= 4096 for key in roots)
        ):
            raise WireError("Invalid graph roots")

    def snapshot(self, roots, *, sequence):
        self._sequence(sequence, self._outgoing)
        self._roots(roots)
        objects, identifiers = dict(self._objects), dict(self._ids)
        records, next_id, edges = {}, self._next_id, 0
        pending = deque()

        def ref(value):
            nonlocal edges
            edges += 1
            if edges > self.limits.edges:
                raise WireLimitError("Graph edge limit exceeded")
            scalar = scalar_record(value)
            return register(value) if scalar is SCALAR_MISSING else scalar

        def register(value):
            nonlocal next_id
            handle = identifiers.get(id(value))
            if handle in records:
                return {"ref": handle}
            codec = codec_for(value)
            if codec.kind == "public_singleton" and self.anchors is None:
                raise WireError("Singleton transfer requires explicit public anchors")
            if handle is None:
                if len(objects) >= self.limits.nodes or next_id >= self.limits.nodes:
                    raise WireLimitError("Graph node limit exceeded")
                handle = self._prefix + str(next_id)
                next_id += 1
                objects[handle], identifiers[id(value)] = value, handle
            elif self._records[handle]["kind"] != codec.kind:
                raise WireError("Existing graph object changed type")
            records[handle] = {"id": handle, "kind": codec.kind, "state": None}
            if self.anchors is not None:
                records[handle]["anchor"] = self.anchors.key_for(value)
            pending.append((handle, value, codec))
            return {"ref": handle}

        ref.singleton_refs = self.anchors is not None

        # Detached exported children remain observable through either side's aliases.
        for value in self._objects.values():
            register(value)
        root_records = {key: ref(roots[key]) for key in sorted(roots)}
        while pending:
            handle, value, codec = pending.popleft()
            records[handle]["state"] = codec.state(value, ref)
        self._validate_records(records)
        self._check_depth(records, root_records)
        wire = {
            "format": "call_graph_v1",
            "session": self.session,
            "sequence": sequence,
            "roots": root_records,
            "nodes": list(records.values()),
        }
        if self.anchors is not None:
            wire["format"] = "call_graph_anchors_v1"
            wire["anchors"] = self.anchors.manifest()
        if len(wire_bytes(wire)) > self.limits.message_bytes:
            raise WireLimitError("Graph message exceeds byte limit")
        self._objects, self._ids, self._records = objects, identifiers, records
        self._next_id, self._outgoing = next_id, sequence
        self._generation += 1
        # Returned mutable wire records must not alias the arena's immutable history.
        return json.loads(wire_bytes(wire))

    def prepare(self, snapshot, *, sequence):
        self._sequence(sequence, self._incoming)
        raw = wire_bytes(snapshot)
        if len(raw) > self.limits.message_bytes:
            raise WireLimitError("Graph message exceeds byte limit")
        wire = json.loads(raw)
        anchored = self.anchors is not None
        fields(
            wire,
            {"format", "session", "sequence", "roots", "nodes"}
            | ({"anchors"} if anchored else set()),
        )
        expected_format = "call_graph_anchors_v1" if anchored else "call_graph_v1"
        if anchored:
            self.anchors.validate_manifest(wire["anchors"])
        if wire["format"] != expected_format or wire["session"] != self.session:
            raise WireError("Wrong graph format or session")
        if type(wire["sequence"]) is not int or wire["sequence"] != sequence:
            raise WireError("Unmatched graph sequence")
        self._roots(wire["roots"])
        if type(wire["nodes"]) is not list or len(wire["nodes"]) > self.limits.nodes:
            raise WireLimitError("Invalid or excessive graph nodes")
        records = {}
        anchor_claims = set()
        for record in wire["nodes"]:
            fields(record, {"id", "kind", "state"} | ({"anchor"} if anchored else set()))
            handle = self._handle(record["id"])
            if handle in records:
                raise WireError("Duplicate graph object ID")
            kind = record["kind"]
            if type(kind) is not str or kind not in REGISTRY:
                raise WireError("Unknown graph kind")
            if kind == "public_singleton" and not anchored:
                raise WireError("Singleton transfer requires explicit public anchors")
            if anchored:
                key = record["anchor"]
                if key is not None:
                    self.anchors.resolve(key, kind=kind)
                    if key in anchor_claims:
                        raise WireError("Duplicate public anchor claim")
                    anchor_claims.add(key)
                if handle in self._records and key != self._records[handle]["anchor"]:
                    raise WireError("Existing graph handle changed anchor claim")
            if handle in self._objects:
                if kind != self._records[handle]["kind"]:
                    raise WireError("Existing graph object changed type")
                if REGISTRY[kind].immutable and wire_bytes(record["state"]) != wire_bytes(
                    self._records[handle]["state"]
                ):
                    raise WireError("Existing immutable graph node was rewritten")
            elif handle.startswith(self._prefix):
                raise WireError("Peer invented a local graph object ID")
            records[handle] = record
        if not set(self._objects) <= set(records):
            raise WireError("Snapshot omitted an exported graph object")
        self._validate_records(records)
        edges = 0

        def check(token):
            nonlocal edges
            edges += 1
            if edges > self.limits.edges:
                raise WireLimitError("Graph edge limit exceeded")
            if type(token) is dict and set(token) == {"ref"}:
                if self._handle(token["ref"]) not in records:
                    raise WireError("Dangling graph reference")
            else:
                scalar_value(token)

        for token in wire["roots"].values():
            check(token)
        for record in records.values():
            for token in REGISTRY[record["kind"]].tokens(record["state"]):
                check(token)
        self._check_depth(records, wire["roots"])
        from graybench.graph_owned import has_owned, rehearse

        if anchored:
            from graybench.graph_anchor_bindings import prepare_anchors

            plan = prepare_anchors(self, records, wire["roots"])
            return PreparedGraph(
                self._owner,
                self._generation,
                sequence,
                {},
                records,
                (),
                wire["roots"],
                _anchor_plan=plan,
            )
        if has_owned(records):
            plan = rehearse(records, self._records, wire["roots"], self._materialize)
            return PreparedGraph(
                self._owner, self._generation, sequence, {}, records, (), wire["roots"], plan
            )
        # Validate hashability/duplicate mapping keys on private staging objects first.
        self._materialize(records, {})
        objects, updates = self._materialize(records, self._objects)
        if len({id(value) for value in objects.values()}) != len(objects):
            raise WireError("Different graph IDs resolved to the same object")
        roots = {
            key: token_value(token, objects.__getitem__) for key, token in wire["roots"].items()
        }
        return PreparedGraph(
            self._owner, self._generation, sequence, objects, records, tuple(updates), roots
        )

    def _validate_records(self, records):
        total = 0
        for handle, record in records.items():
            codec = REGISTRY[record["kind"]]
            codec.validate(record["state"], records)
            total += codec.array_bytes(record["state"])
            if total > self.limits.array_bytes:
                raise WireLimitError("Graph array storage exceeds byte limit")
            if handle in self._records:
                codec.validate_update(self._records[handle]["state"], record["state"])
        matrix_owners = set()
        for record in records.values():
            for token in REGISTRY[record["kind"]].matrix_refs(record["state"]):
                array = records[token["ref"]]
                if array["kind"] == "ndarray_view":
                    array = records[array["state"]["base"]["ref"]]
                matrix_owners.add(array["id"])
        matrix_bytes = sum(
            REGISTRY[records[handle]["kind"]].array_bytes(records[handle]["state"])
            for handle in matrix_owners
        )
        if matrix_bytes > self.limits.matrix_bytes:
            raise WireLimitError("Graph matrix storage exceeds byte limit")

    def _check_depth(self, records, roots):
        # Canonical root order and explicit stack make sender/receiver checks identical.
        starts = [
            roots[key]["ref"]
            for key in sorted(roots)
            if type(roots[key]) is dict and set(roots[key]) == {"ref"}
        ]
        starts.extend(sorted(records))
        seen = set()
        for start in starts:
            pending = [(start, 0)]
            while pending:
                handle, depth = pending.pop()
                if handle in seen:
                    continue
                if depth > self.limits.depth:
                    raise WireLimitError("Graph nesting exceeds limit")
                seen.add(handle)
                record = records[handle]
                children = [
                    token["ref"]
                    for token in REGISTRY[record["kind"]].tokens(record["state"])
                    if type(token) is dict and set(token) == {"ref"}
                ]
                pending.extend((child, depth + 1) for child in reversed(children))

    def _materialize(self, records, existing, *, codecs=None):
        registry = REGISTRY if codecs is None else codecs
        objects = dict(existing)
        for handle, record in records.items():
            if handle not in objects:
                allocated = registry[record["kind"]].allocate(record["state"], records)
                if allocated is not None:
                    objects[handle] = allocated
        building = set()

        def resolve(handle, depth=0):
            if handle in objects:
                return objects[handle]
            if handle in building:
                raise WireError("Impossible immutable graph cycle")
            if depth > self.limits.depth:
                raise WireLimitError("Immutable graph nesting exceeds limit")
            building.add(handle)
            record = records[handle]
            objects[handle] = registry[record["kind"]].populate(
                None, record["state"], lambda key: resolve(key, depth + 1)
            )
            building.remove(handle)
            return objects[handle]

        for handle in records:
            resolve(handle)
        updates = []
        for handle, record in records.items():
            codec = registry[record["kind"]]
            if codec.immutable:
                continue
            prepared = codec.prepare(record["state"], objects.__getitem__, records)
            updates.append((codec, objects[handle], prepared))
        return objects, updates

    def commit(self, prepared):
        if (
            self._closed
            or type(prepared) is not PreparedGraph
            or prepared._owner is not self._owner
        ):
            raise WireError("Foreign or closed graph preparation")
        if prepared._generation != self._generation:
            raise WireError("Stale graph preparation")
        self._sequence(prepared._sequence, self._incoming)
        if prepared._anchor_plan is not None:
            from graybench.graph_anchor_bindings import commit_anchors

            try:
                objects, roots = commit_anchors(self, prepared._anchor_plan)
            except BaseException:
                self.close()
                raise
            self._objects, self._records = objects, prepared._records
            self._ids = {id(value): handle for handle, value in objects.items()}
            self._incoming = prepared._sequence
            self._generation += 1
            return roots
        if prepared._owned_plan is not None:
            from graybench.graph_owned import execute_owned

            try:
                objects, roots = execute_owned(
                    prepared._owned_plan, self._objects, self._materialize
                )
            except BaseException:
                self.close()
                raise
            self._objects, self._records = objects, prepared._records
            self._ids = {id(value): handle for handle, value in objects.items()}
            self._incoming = prepared._sequence
            self._generation += 1
            return roots
        try:
            for codec, target, state in prepared._updates:
                codec.apply(target, state)
        except BaseException:
            self.close()  # The oracle must not continue after an unexpected partial apply.
            raise
        self._objects, self._records = prepared._objects, prepared._records
        self._ids = {id(value): handle for handle, value in self._objects.items()}
        self._incoming = prepared._sequence
        self._generation += 1
        return prepared._roots

    def close(self):
        self._objects.clear()
        self._ids.clear()
        self._records.clear()
        self._closed = True
        self._generation += 1
