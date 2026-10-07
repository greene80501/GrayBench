"""Rehearse exported anchor bindings against current local state, then commit."""

from collections import deque
from dataclasses import dataclass

from graybench.circuit_wire import WireError, WireLimitError
from graybench.graph_owned import GraphReconstructionError, OwnedCommitPlan, execute_owned
from graybench.graph_types import REGISTRY, SCALAR_MISSING, codec_for, scalar_record
from graybench.graph_wire import wire_bytes


@dataclass(frozen=True)
class CapturedBindings:
    records: dict
    objects: dict
    canonical: bytes


def capture_bound(bindings, arena):
    """Bounded local-only capture; preparation validates its complete record table.

    Supplemental b: IDs never enter a call payload. Retaining canonical bytes
    lets commit compare an actual new capture with the exact validated baseline.
    """
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

    ref.singleton_refs = True

    while pending:
        handle = pending.popleft()
        codec = codec_for(objects[handle])
        records[handle] = {
            "id": handle,
            "kind": codec.kind,
            "state": codec.state(objects[handle], ref),
        }
    canonical = wire_bytes(records)
    if len(canonical) > arena.limits.message_bytes:
        raise WireLimitError("Private anchor rehearsal byte limit exceeded")
    return CapturedBindings(records, objects, canonical)


@dataclass(frozen=True)
class AnchorCommitPlan:
    plan: OwnedCommitPlan
    bindings: dict
    baseline: bytes
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
    captured = capture_bound(bindings, arena)
    baseline, baseline_objects = captured.records, captured.objects
    arena._validate_records(baseline)
    arena._check_depth(baseline, {})
    for handle in bindings:
        record, previous = records[handle], baseline[handle]
        if record["kind"] != previous["kind"]:
            raise WireError("Public anchor runtime kind mismatch")
        codec = REGISTRY[record["kind"]]
        if codec.immutable and wire_bytes(record["state"]) != wire_bytes(previous["state"]):
            raise WireError("Immutable bound anchor state changed")
        codec.validate_update(previous["state"], record["state"])
    staging, _ = execute_owned(
        OwnedCommitPlan(baseline, {}, {}, singleton_refs=True), {}, arena._materialize
    )
    # Keep only exported bindings in the object map. Supplemental objects remain
    # reachable through the staged owners, but cannot become phantom exports.
    staging = {key: staging[key] for key in bindings}
    plan = OwnedCommitPlan(records, baseline, roots, singleton_refs=True)
    execute_owned(plan, staging, arena._materialize)
    return AnchorCommitPlan(plan, bindings, captured.canonical, baseline_objects)


def commit_anchors(arena, prepared):
    try:
        current = capture_bound(prepared.bindings, arena)
    except WireError as exc:
        # No candidate frame is being decoded here. An inability to recapture
        # the previously validated live baseline is a bridge failure.
        raise GraphReconstructionError(
            f"Live anchor recapture failed after preparation: {type(exc).__name__}: {exc}"[:4096]
        ) from exc
    # Equality with the validated preparation proves the second capture has the
    # same schema, references and depth. Revalidating that table adds no check.
    # Identity remains separate: equal replacement of an unexported child can
    # retain the same local b: token and identical canonical bytes.
    if current.canonical != prepared.baseline or any(
        current.objects.get(key) is not value for key, value in prepared.baseline_objects.items()
    ):
        raise GraphReconstructionError("Live anchor state changed after preparation")
    return execute_owned(prepared.plan, prepared.bindings, arena._materialize)
