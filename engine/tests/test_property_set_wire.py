import os

import pytest
from qiskit.transpiler import PropertySet

from graybench.circuit_wire import WireError, WireLimitError
from graybench.sandbox import Candidate
from graybench.value_wire import decode, encode


def test_property_set_preserves_type_order_values_and_missing_key_behavior():
    original = PropertySet()
    original["depth_before"] = 2
    original[("nested", 1)] = PropertySet({"value": [None, 1.5, (2, 3)]})
    original["width"] = 2
    restored = decode(encode(original))
    assert type(restored) is PropertySet
    assert list(restored) == list(original)
    assert restored == original
    assert type(restored[("nested", 1)]) is PropertySet
    assert restored["absent"] is None
    assert "absent" not in restored
    assert type(decode(encode(dict(original)))) is dict


def test_property_set_custom_classes_and_instance_state_are_not_discarded():
    class Custom(PropertySet):
        def __missing__(self, key):
            return 7

    with pytest.raises(WireError):
        encode(Custom())
    original = PropertySet({"depth": 2})
    original.extra = "custom state"
    with pytest.raises(WireError):
        encode(original)


def test_property_set_cycles_are_bounded():
    original = PropertySet()
    original["self"] = original
    with pytest.raises(WireLimitError):
        encode(original)


@pytest.mark.parametrize(
    "items",
    [[["x", 1], ["x", 2]], [[{"kind": "list", "items": []}, 1]], [["x"]]],
)
def test_property_set_malformed_entries_are_rejected(items):
    with pytest.raises(WireError):
        decode({"kind": "property_set_v1", "items": items})


def test_property_set_cannot_install_arbitrary_attributes():
    restored = decode({"kind": "property_set_v1", "items": [["__class__", "x"]]})
    assert type(restored) is PropertySet
    assert restored["__class__"] == "x"
    assert type(restored).__missing__ is PropertySet.__missing__
    with pytest.raises(WireError):
        decode({"kind": "property_set_v1", "items": [], "class": "os.system"})


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires immutable image")
def test_property_set_crosses_candidate_boundary_in_both_directions():
    code = """from qiskit.transpiler import PropertySet
def answer(value):
    assert type(value) is PropertySet
    assert value['absent'] is None and 'absent' not in value
    value['depth_after'] = 1
    return value
"""
    with Candidate(
        code,
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
    ) as candidate:
        call = candidate.call_with_updates("answer", PropertySet({"depth_before": 2}))
        result = call.value
    assert type(result) is PropertySet
    assert list(result.items()) == [("depth_before", 2), ("depth_after", 1)]
    assert result["absent"] is None
    assert type(call.args_after[0]) is PropertySet
    assert call.args_after[0] == result
