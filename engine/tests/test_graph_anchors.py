import pytest
from qiskit.circuit.library import XGate

from graybench.circuit_wire import WireError, WireLimitError
from graybench.graph_anchors import PublicAnchorRegistry


def test_registry_resolves_fixed_factory_and_actual_children():
    registry = PublicAnchorRegistry.capture()
    gate = XGate()
    for value, kind in [
        (gate, "public_singleton"),
        (vars(gate), "dict"),
        (gate.params, "qiskit_frozen_list"),
        (gate._definition, "quantum_circuit"),
    ]:
        key = registry.key_for(value)
        assert key is not None and registry.resolve(key, kind=kind) is value
    registry.validate_manifest(registry.manifest())


def test_equal_replacement_does_not_take_original_anchor():
    registry = PublicAnchorRegistry.capture()
    definition = XGate()._definition
    original = definition.metadata
    key = registry.key_for(original)
    try:
        definition.metadata = dict(original)
        assert definition.metadata == original and definition.metadata is not original
        assert registry.key_for(definition.metadata) is None
        assert registry.resolve(key, kind="dict") is original
    finally:
        definition.metadata = original


def test_returned_records_and_manifest_cannot_rewrite_registry():
    registry = PublicAnchorRegistry.capture()
    key = registry.key_for(XGate())
    original = registry.manifest()
    record = registry.record(key)
    record["state"]["factory"] = "forged"
    manifest = registry.manifest()
    manifest["sha256"] = "0" * 64
    snapshot = registry.snapshot()
    snapshot["records"].clear()
    assert registry.record(key)["state"]["factory"] == "x"
    assert registry.manifest() == original and registry.snapshot()["records"]


@pytest.mark.parametrize("change", ["digest", "count", "extra"])
def test_mismatched_or_malformed_manifest_is_rejected(change):
    registry = PublicAnchorRegistry.capture()
    manifest = registry.manifest()
    if change == "digest":
        manifest["sha256"] = "0" * 64
    elif change == "count":
        manifest["nodes"] = True
    else:
        manifest["extra"] = "not part of schema"
    with pytest.raises(WireError):
        registry.validate_manifest(manifest)


@pytest.mark.parametrize("key", ["-1", "00", "999999", "qiskit.XGate()", 0, None])
def test_registry_rejects_unknown_or_noncanonical_keys(key):
    registry = PublicAnchorRegistry.capture()
    with pytest.raises(WireError):
        registry.resolve(key, kind="dict")


def test_anchor_kind_cannot_be_reinterpreted():
    registry = PublicAnchorRegistry.capture()
    key = registry.key_for(XGate())
    with pytest.raises(WireError):
        registry.resolve(key, kind="dict")


def test_bounded_bootstrap_failure_does_not_modify_public_attributes():
    gate = XGate()
    attrs, params, definition = vars(gate), gate.params, gate._definition
    with pytest.raises(WireLimitError):
        PublicAnchorRegistry.capture(max_nodes=1)
    assert vars(gate) is attrs and gate.params is params and gate._definition is definition


def test_byte_budget_failure_is_explicit():
    with pytest.raises(WireLimitError):
        PublicAnchorRegistry.capture(max_bytes=1)


@pytest.mark.parametrize("kwargs", [{"max_nodes": True}, {"max_nodes": 10001}, {"max_bytes": 0}])
def test_invalid_bootstrap_limits_are_rejected(kwargs):
    with pytest.raises(WireError):
        PublicAnchorRegistry.capture(**kwargs)


def test_live_value_change_does_not_rewrite_bootstrap_record():
    registry = PublicAnchorRegistry.capture()
    metadata = XGate()._definition.metadata
    key = registry.key_for(metadata)
    baseline = registry.record(key)
    manifest = registry.manifest()
    old = dict(metadata)
    try:
        metadata["anchor-audit"] = "changed"
        assert registry.resolve(key, kind="dict") is metadata
        assert registry.record(key) == baseline and registry.manifest() == manifest
    finally:
        metadata.clear()
        metadata.update(old)


def test_private_bootstrap_copy_preserves_aliases_without_public_objects():
    registry = PublicAnchorRegistry.capture()
    private = registry.private_copy()
    snapshot = registry.snapshot()
    assert set(private) == set(snapshot["records"])
    for key, record in snapshot["records"].items():
        public = registry.resolve(key, kind=record["kind"])
        assert type(private[key]) is type(public)
        assert private[key] is not public
    from graybench.graph_types import SCALAR_MISSING, codec_for, scalar_record

    identities = {id(value): key for key, value in private.items()}

    def ref(value):
        scalar = scalar_record(value)
        return {"ref": identities[id(value)]} if scalar is SCALAR_MISSING else scalar

    for key, record in snapshot["records"].items():
        value = private[key]
        state = (
            {"factory": record["state"]["factory"], "attributes": ref(vars(value))}
            if record["kind"] == "public_singleton"
            else codec_for(value).state(value, ref)
        )
        assert state == record["state"]
    gate = private[registry.key_for(XGate())]
    assert vars(gate) is private[registry.key_for(vars(XGate()))]
    assert gate.params is private[registry.key_for(XGate().params)]
    assert gate._definition is private[registry.key_for(XGate()._definition)]
    assert (
        gate._definition._data.qubits is private[registry.key_for(XGate()._definition._data.qubits)]
    )


def test_private_bootstrap_mutations_do_not_reach_live_factories():
    registry = PublicAnchorRegistry.capture()
    public = XGate()
    private = registry.private_copy()
    gate = private[registry.key_for(public)]
    original = dict(vars(public))
    metadata = dict(public._definition.metadata)
    params = list(public.params)
    vars(gate)["_label"] = "private rehearsal"
    list.append(gate.params, 123)
    gate._definition.metadata["private"] = True
    assert vars(public) == original
    assert list(public.params) == params
    assert public._definition.metadata == metadata


def test_private_bootstrap_copy_uses_frozen_history_and_is_repeatable():
    registry = PublicAnchorRegistry.capture()
    metadata = XGate()._definition.metadata
    original = dict(metadata)
    try:
        metadata["later-live-change"] = True
        first, second = registry.private_copy(), registry.private_copy()
        key = registry.key_for(metadata)
        assert first[key] == second[key] == original
        assert first[key] is not second[key]
        first[key]["private-only"] = True
        assert "private-only" not in second[key] and "private-only" not in metadata
    finally:
        metadata.clear()
        metadata.update(original)
