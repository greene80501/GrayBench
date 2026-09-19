"""Rehearse native owner transitions privately before resolving live child aliases."""

from dataclasses import dataclass

from graybench.circuit_wire import WireError


@dataclass(frozen=True)
class OwnedCommitPlan:
    records: dict
    previous_records: dict
    roots: dict


def has_owned(records):
    from graybench.graph_types import REGISTRY

    return any(hasattr(REGISTRY[r["kind"]], "owner_children") for r in records.values())


def execute_owned(plan, existing_objects, materialize):
    from graybench.graph_types import REGISTRY, token_value

    objects = dict(existing_objects)
    owners = []
    claims = {}
    for handle, record in plan.records.items():
        codec = REGISTRY[record["kind"]]
        if not hasattr(codec, "owner_children"):
            continue
        state = record["state"]
        # One slot per handle, and one native owner per child.
        tokens = list(codec.tokens(state))
        for token in tokens:
            child = token["ref"]
            if child in claims:
                raise WireError("Two owner slots claim one cache handle")
            claims[child] = handle
        owners.append((handle, codec, state))

    for handle, codec, state in owners:
        if handle not in objects:
            objects[handle] = codec.allocate(state, plan.records)
        else:
            codec.transition_owner(
                objects[handle], plan.previous_records[handle]["state"], state, plan.records
            )

    for handle, codec, state in owners:
        for child, actual in codec.owner_children(objects[handle], state).items():
            if child in objects and objects[child] is not actual:
                raise WireError("Cannot bind an existing graph object to a different owner cache")
            objects[child] = actual

    objects, updates = materialize(plan.records, objects)
    if len({id(value) for value in objects.values()}) != len(objects):
        raise WireError("Different graph IDs resolved to one owner object")
    for codec, target, prepared in updates:
        codec.apply(target, prepared)
    for handle, codec, state in owners:
        if any(
            objects[child] is not actual
            for child, actual in codec.owner_children(objects[handle], state).items()
        ):
            raise WireError("Owner update invalidated bound cache objects")
    from graybench.graph_wire import wire_bytes

    identities = {id(value): handle for handle, value in objects.items()}
    for handle, codec, state in owners:
        try:
            actual = codec.state(objects[handle], lambda value: {"ref": identities[id(value)]})
        except KeyError as exc:
            raise WireError("Owner exposed an unbound cache object") from exc
        if wire_bytes(actual) != wire_bytes(state):
            raise WireError("Native owner reconstruction changed the declared state")
    roots = {key: token_value(token, objects.__getitem__) for key, token in plan.roots.items()}
    return objects, roots


def rehearse(records, previous_records, roots, materialize):
    previous = OwnedCommitPlan(previous_records, {}, {})
    staging, _ = execute_owned(previous, {}, materialize)
    plan = OwnedCommitPlan(records, previous_records, roots)
    execute_owned(plan, staging, materialize)
    return plan
