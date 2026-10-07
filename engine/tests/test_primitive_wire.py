import numpy as np
import pytest
from qiskit.primitives import BitArray, DataBin, PrimitiveResult, PubResult, SamplerPubResult

from graybench.circuit_wire import WireError, WireLimitError
from graybench.value_wire import decode, encode


def test_bit_array_preserves_shape_padding_bytes_and_shot_order():
    array = np.array([[[255, 1], [128, 2]], [[31, 3], [17, 4]]], dtype=np.uint8)
    original = BitArray(array, 9)
    restored = decode(encode(original))
    assert type(restored) is BitArray
    assert restored.num_bits == 9
    assert restored.shape == (2,)
    assert restored.num_shots == 2
    np.testing.assert_array_equal(restored.array, array)
    assert restored.get_bitstrings(1) == original.get_bitstrings(1)


def test_nested_primitive_result_preserves_classes_metadata_and_field_order():
    bits = BitArray.from_samples(["101", "001", "101"])
    data = DataBin(zeta=bits, alpha=bits, evs=np.array([0.5]))
    original = PrimitiveResult(
        [SamplerPubResult(data, {"shots": 3}), PubResult(DataBin(shape=(0,)), {"x": [1, 2]})],
        {"global": {"label": "retained", "numeric": np.int64(7)}},
    )
    restored = decode(encode(original))
    assert type(restored) is PrimitiveResult
    assert [type(pub) for pub in restored] == [SamplerPubResult, PubResult]
    assert restored.metadata == original.metadata
    assert restored[0].metadata == {"shots": 3}
    assert list(restored[0].data.keys()) == ["zeta", "alpha", "evs"]
    assert restored[0].join_data(["zeta", "alpha"]).get_bitstrings() == [
        "101101",
        "001001",
        "101101",
    ]
    assert restored[1].data.shape == (0,)
    assert restored[1].metadata == {"x": [1, 2]}


def test_primitive_metadata_cycles_are_bounded():
    original = PrimitiveResult([])
    original.metadata["cycle"] = original
    with pytest.raises(WireLimitError):
        encode(original)


def test_bit_array_invalid_width_is_rejected():
    value = encode(BitArray.from_samples(["001"]))
    value["num_bits"] = 9
    with pytest.raises(WireError):
        decode(value)


def test_data_bin_special_attributes_are_not_installed():
    value = encode(DataBin(meas=BitArray.from_samples(["1"])))
    value["data"]["items"][0][0] = "__dict__"
    with pytest.raises(WireError):
        decode(value)


def test_divergent_data_bin_attribute_is_not_silently_repaired():
    data = DataBin(meas=BitArray.from_samples(["1"]))
    data.meas = BitArray.from_samples(["0"])
    with pytest.raises(WireError, match="diverge"):
        encode(data)


@pytest.mark.parametrize("shape,bits", [((0, 1), 3), ((2, 0), 0)])
def test_empty_bit_arrays_remain_empty(shape, bits):
    original = BitArray(np.empty(shape, dtype=np.uint8), bits)
    restored = decode(encode(original))
    assert restored.array.shape == shape
    assert restored.num_bits == bits
