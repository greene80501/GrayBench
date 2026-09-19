"""Explicit bootstrap identities for fixed public SDK objects; no live binding yet."""

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from types import MappingProxyType

from graybench.circuit_wire import WireError, WireLimitError, fields
from graybench.graph_types import SCALAR_MISSING, codec_for, scalar_record
from graybench.graph_wire import wire_bytes


@dataclass(frozen=True, slots=True)
class PublicAnchorRegistry:
    _objects: object
    _identities: object
    _types: object
    _records: object
    _graph: bytes
    _digest: str

    @classmethod
    def capture(cls, *, max_nodes=10000, max_bytes=1048576):
        """Call once before user code; recapture must never redefine session anchors."""
        from qiskit.circuit.library import get_standard_gate_name_mapping

        if type(max_nodes) is not int or not 1 <= max_nodes <= 10000:
            raise WireError("Invalid public anchor node budget")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 1048576:
            raise WireError("Invalid public anchor byte budget")
        factories = {
            name: value
            for name, value in sorted(get_standard_gate_name_mapping().items())
            if not value.mutable
        }
        singleton_names = {id(value): name for name, value in reversed(list(factories.items()))}
        identities, objects, records, pending = {}, {}, {}, deque()
        edges = 0

        def ref(value):
            nonlocal edges
            edges += 1
            if edges > 100000:
                raise WireLimitError("Public anchor edge budget exceeded")
            scalar = scalar_record(value)
            if scalar is not SCALAR_MISSING:
                return scalar
            if id(value) in identities:
                return {"ref": identities[id(value)]}
            if len(objects) >= max_nodes:
                raise WireLimitError("Public anchor node budget exceeded")
            handle = str(len(objects))
            identities[id(value)] = handle
            objects[handle] = value
            pending.append(handle)
            return {"ref": handle}

        roots = {name: ref(value) for name, value in factories.items()}
        encoded_bytes = 0
        while pending:
            handle = pending.popleft()
            value = objects[handle]
            if id(value) in singleton_names:
                kind = "public_singleton"
                state = {"factory": singleton_names[id(value)], "attributes": ref(vars(value))}
            else:
                codec = codec_for(value)
                kind = codec.kind
                state = codec.state(value, ref)
            record = {"kind": kind, "state": state}
            encoded_bytes += len(wire_bytes(record))
            if encoded_bytes > max_bytes:
                raise WireLimitError("Public anchor byte budget exceeded")
            records[handle] = record
        graph = wire_bytes({"roots": roots, "records": records})
        if len(graph) > max_bytes:
            raise WireLimitError("Public anchor byte budget exceeded")
        return cls(
            MappingProxyType(objects),
            MappingProxyType(identities),
            MappingProxyType({key: type(value) for key, value in objects.items()}),
            MappingProxyType({key: wire_bytes(value) for key, value in records.items()}),
            graph,
            hashlib.sha256(graph).hexdigest(),
        )

    def manifest(self):
        return {
            "format": "qiskit_public_anchors_v1",
            "sha256": self._digest,
            "nodes": len(self._objects),
        }

    def validate_manifest(self, manifest):
        fields(manifest, {"format", "sha256", "nodes"})
        if type(manifest["nodes"]) is not int or manifest != self.manifest():
            raise WireError("Incompatible public anchor registry")

    def key_for(self, value):
        key = self._identities.get(id(value))
        if key is None:
            return None
        if self._objects[key] is not value or type(value) is not self._types[key]:
            raise WireError("Public anchor runtime type changed")
        return key

    def record(self, key):
        if type(key) is not str or key not in self._records:
            raise WireError("Unknown public anchor key")
        return json.loads(self._records[key])

    def resolve(self, key, *, kind):
        record = self.record(key)
        if type(kind) is not str or record["kind"] != kind:
            raise WireError("Public anchor kind mismatch")
        value = self._objects[key]
        if type(value) is not self._types[key]:
            raise WireError("Public anchor runtime type changed")
        return value

    def snapshot(self):
        """Private bootstrap material only; never add this whole graph to call payloads."""
        return json.loads(self._graph)
