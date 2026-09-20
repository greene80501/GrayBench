"""Rehearse exported anchor bindings against current local state, then commit."""

from collections import deque
from dataclasses import dataclass

from graybench.circuit_wire import WireError, WireLimitError
from graybench.graph_owned import OwnedCommitPlan, execute_owned
from graybench.graph_types import REGISTRY, SCALAR_MISSING, codec_for, scalar_record
from graybench.graph_wire import wire_bytes


def capture_bound(bindings, arena):
    """Local-only closure; supplemental b: IDs never enter a call payload."""
    objects = dict(bindings)
    identities = {id(value): handle for handle, value in objects.items()}
    if len(identities) != len(objects):
        raise WireError("Different graph IDs claim the same public anchor")
    pending = deque(objects)
    records = {}
    edges = 0

    def ref(value):
        nonlocal edges
        edges += 1
        if edges > arena.limits.edges:
            raise WireLimitError("Private anchor rehearsal edge limit exceeded")
        scalar = scalar_record(value)
        if scalar is not SCALAR_MISSING:
            return scalar
        handle = identities.get(id(value))
        if handle is None:
            if len(objects) >= arena.limits.nodes:
                raise WireLimitError("Private anchor rehearsal node limit exceeded")
            handle = "b:" + str(len(objects))
            objects[handle] = value
            identities[id(value)] = handle
            pending.append(handle)
        return {"ref": handle}

    while pending:
        handle = pending.popleft()
        codec = codec_for(objects[handle])
        records[handle] = {
            "id": handle,
            "kind": codec.kind,
            "state": codec.state(objects[handle], ref),
        }
    if len(wire_bytes(records)) > arena.limits.message_bytes:
        raise WireLimitError("Private anchor rehearsal byte limit exceeded")
    arena._validate_records(records)
    arena._check_depth(records, {})
    return records, objects


@dataclass(frozen=True)
class AnchorCommitPlan:
    plan: OwnedCommitPlan
    bindings: dict
    baseline: dict
    baseline_objects: dict


def prepare_anchors(arena, records, roots):
    bindings = dict(arena._objects)
    for handle, record in records.items():
        key = record["anchor"]
        if key is not None:
            actual = arena.anchors.resolve(key, kind=record["kind"])
            if handle in bindings and bindings[handle] is not actual:
                raise WireError("Existing handle changed its public anchor binding")
            bindings[handle] = actual
    baseline, baseline_objects = capture_bound(bindings, arena)
    for handle in bindings:
        record, previous = records[handle], baseline[handle]
        if record["kind"] != previous["kind"]:
            raise WireError("Public anchor runtime kind mismatch")
        codec = REGISTRY[record["kind"]]
        if codec.immutable and wire_bytes(record["state"]) != wire_bytes(previous["state"]):
            raise WireError("Immutable bound anchor state changed")
        codec.validate_update(previous["state"], record["state"])
    staging, _ = execute_owned(OwnedCommitPlan(baseline, {}, {}), {}, arena._materialize)
    # Keep only exported bindings in the object map. Supplemental objects remain
    # reachable through the staged owners, but cannot become phantom exports.
    staging = {key: staging[key] for key in bindings}
    plan = OwnedCommitPlan(records, baseline, roots)
    execute_owned(plan, staging, arena._materialize)
    return AnchorCommitPlan(plan, bindings, baseline, baseline_objects)


def commit_anchors(arena, prepared):
    current, objects = capture_bound(prepared.bindings, arena)
    if wire_bytes(current) != wire_bytes(prepared.baseline) or any(
        objects.get(key) is not value for key, value in prepared.baseline_objects.items()
    ):
        raise WireError("Live anchor state changed after preparation")
    return execute_owned(prepared.plan, prepared.bindings, arena._materialize)
