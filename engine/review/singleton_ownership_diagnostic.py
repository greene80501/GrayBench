"""Trusted singleton ownership audit in a disposable Python process."""

import copy
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from qiskit.circuit.library import CXGate, IGate, MCXGate, XGate


def main():
    checks = []
    x = XGate()
    assert XGate() is x and CXGate() is CXGate() and IGate() is IGate()
    assert not x.mutable and x.base_class is XGate and type(x) is not XGate
    checks.append("fixed_factories_reuse_exact_singleton_objects")

    assert copy.copy(x) is x and copy.deepcopy(x) is x and x.copy() is x
    checks.append("ordinary_copy_and_deepcopy_do_not_isolate_singletons")

    clone = object.__new__(type(x))
    object.__setattr__(clone, "__dict__", dict(vars(x)))
    assert type(clone) is type(x) and not clone.mutable and clone.copy() is clone
    assert clone is not XGate()
    checks.append("manual_exact_type_clone_does_not_preserve_factory_identity")

    assert clone._definition is x._definition and clone.params is x.params
    checks.append("shallow_dictionary_clone_still_shares_mutable_children")

    params = x.params
    assert type(params).__name__ == "_frozenlist" and params is x.params
    try:
        params.append(1)
    except TypeError:
        pass
    else:
        raise AssertionError("ordinary singleton parameter mutation unexpectedly allowed")
    before = list(params)
    try:
        list.append(params, 1)
        assert x.params is params and list(params) == before + [1]
    finally:
        list.__setitem__(params, slice(None), before)
    assert list(params) == before
    checks.append("frozen_parameter_list_has_exact_type_and_bypassable_method_guards")

    attrs = vars(x)
    original_label = attrs["_label"]
    try:
        try:
            x.label = "audit"
        except TypeError:
            pass
        else:
            raise AssertionError("ordinary singleton attribute mutation unexpectedly allowed")
        attrs["_label"] = "audit"
        assert XGate().label == "audit" and vars(XGate()) is attrs
    finally:
        attrs["_label"] = original_label
    checks.append("actual_singleton_dictionary_is_mutable_and_globally_visible")

    definition = x._definition
    assert definition is not None
    original_name = definition.name
    try:
        definition.name = "singleton-audit"
        assert XGate()._definition is definition and clone._definition.name == "singleton-audit"
    finally:
        definition.name = original_name
    checks.append("raw_cached_definition_is_a_shared_mutable_circuit")

    cx = CXGate().to_mutable()
    assert cx.base_gate is MCXGate(3).base_gate is x
    assert cx.params is x.params and cx._params is not cx.params
    assert type(cx._params) is list
    checks.append("mutable_controlled_gate_has_plain_raw_list_but_frozen_delegated_params")

    print(
        json.dumps(
            {
                "scope": "trusted_singleton_ownership_audit",
                "production_bridge_integrated": False,
                "python": platform.python_version(),
                "system": platform.system(),
                "qiskit": qiskit.__version__,
                "checks_passed": checks,
                "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
