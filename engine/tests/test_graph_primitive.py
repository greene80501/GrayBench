import copy

import numpy as np
import pytest
from qiskit.primitives import BitArray, DataBin, PrimitiveResult, PubResult, SamplerPubResult

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas():
    return tuple(
        GraphArena(side=side, session="primitive", limits=GraphLimits())
        for side in ("judge", "candidate")
    )


def transfer(sender, receiver, value, sequence=1):
    return receiver.commit(
        receiver.prepare(sender.snapshot({"value": value}, sequence=sequence), sequence=sequence)
    )["value"]


def test_bitarray_data_and_instance_dictionary_aliases_update_in_place():
    judge, candidate = arenas()
    data = np.array([[0, 1], [1, 0]], dtype=np.uint8)
    bitarray = BitArray(data, 9)
    remote, array, attributes = transfer(
        judge, candidate, (bitarray, bitarray.array, vars(bitarray))
    )
    assert remote.array is array and vars(remote) is attributes
    array[0, 1] = 3
    result = transfer(candidate, judge, remote)
    assert result is bitarray and bitarray.array is data
    assert bitarray.get_bitstrings() == ["000000011", "100000000"]


def test_databin_preserves_mapping_attributes_repeated_fields_and_divergence():
    judge, candidate = arenas()
    data = np.array([1, 2])
    value = DataBin(shape=(2,), a=data, b=data)
    original_mapping = value._data
    original_attributes = vars(value)
    remote, mapping, attributes, array = transfer(
        judge, candidate, (value, original_mapping, original_attributes, data)
    )
    assert remote._data is mapping and vars(remote) is attributes
    assert remote.a is remote.b is mapping["a"] is mapping["b"] is array
    remote.a = np.array([3, 4])
    assert (
        remote.a is not mapping["a"]
    )  # Native DataBin attribute mutation does not change its mapping.
    transfer(candidate, judge, remote)
    assert value._data is original_mapping and vars(value) is original_attributes
    assert value.a is not value._data["a"] and value.b is data
    np.testing.assert_array_equal(value.a, [3, 4])
    np.testing.assert_array_equal(value._data["a"], [1, 2])


@pytest.mark.parametrize("cls", [PubResult, SamplerPubResult])
def test_pubresult_retains_empty_metadata_and_shared_databin(cls):
    judge, candidate = arenas()
    value = cls(DataBin(x=np.array([3])), {})
    metadata = value.metadata
    remote, data, meta = transfer(judge, candidate, (value, value.data, metadata))
    assert type(remote) is cls and remote.data is data and remote.metadata is meta
    meta["new"] = [1, 2]
    assert transfer(candidate, judge, remote) is value
    assert value.metadata is metadata and metadata == {"new": [1, 2]}


def test_primitive_result_preserves_stored_list_alias_replacements_and_cycles():
    judge, candidate = arenas()
    pub = PubResult(DataBin(), {})
    value = PrimitiveResult([pub, pub], {})
    pubs, metadata = value._pub_results, value.metadata
    metadata["owner"] = value
    remote, array, meta, component = transfer(judge, candidate, (value, pubs, metadata, pub))
    assert remote._pub_results is array and remote.metadata is meta
    assert remote[0] is remote[1] is component and meta["owner"] is remote
    array.pop()
    assert transfer(candidate, judge, remote) is value
    assert value._pub_results is pubs and len(value) == 1 and metadata["owner"] is value


def test_databin_self_reference_and_sampler_instance_dict_are_preserved():
    judge, candidate = arenas()
    data = DataBin()
    data._data["self"] = data
    data.self = data
    value = SamplerPubResult(data)
    result, attributes = transfer(judge, candidate, (value, vars(value)))
    assert vars(result) is attributes
    assert result.data.self is result.data._data["self"] is result.data


@pytest.mark.parametrize(
    "case",
    [
        "reserved_data",
        "reserved_attribute",
        "shape",
        "array",
        "bits",
        "metadata",
        "pub_data",
        "attrs_kind",
    ],
)
def test_invalid_primitive_graph_fails_before_existing_metadata_changes(case):
    judge, candidate = arenas()
    value = SamplerPubResult(
        DataBin(bits=BitArray(np.array([[1]], dtype=np.uint8), 1)), {"before": 1}
    )
    remote = transfer(judge, candidate, value)
    remote.metadata["changed"] = 2
    wire = candidate.snapshot({"value": remote}, sequence=1)
    bad = copy.deepcopy(wire)
    records = {n["id"]: n for n in bad["nodes"]}
    pub = next(n for n in bad["nodes"] if n["kind"] == "sampler_pub_result")
    data = next(n for n in bad["nodes"] if n["kind"] == "data_bin")
    bits = next(n for n in bad["nodes"] if n["kind"] == "bit_array")
    if case in ("reserved_data", "reserved_attribute"):
        key = "data" if case == "reserved_data" else "attributes"
        records[data["state"][key]["ref"]]["state"][0][0] = "__class__"
    elif case == "shape":
        data["state"]["shape"] = data["state"]["data"]
    elif case == "array":
        bits["state"]["array"] = data["state"]["data"]
    elif case == "bits":
        bits["state"]["num_bits"] = 9
        for pair in records[bits["state"]["attributes"]["ref"]]["state"]:
            if pair[0] == "_num_bits":
                pair[1] = 9
    elif case == "metadata":
        pub["state"]["metadata"] = pub["state"]["data"]
    elif case == "pub_data":
        pub["state"]["data"] = pub["state"]["metadata"]
    else:
        pub["state"]["attributes"] = pub["state"]["data"]
    with pytest.raises(WireError):
        judge.prepare(bad, sequence=1)
    assert value.metadata == {"before": 1}


def test_databin_inconsistent_leading_dimensions_are_rejected():
    judge, _ = arenas()
    data = DataBin(shape=(2,), x=np.array([1, 2]))
    data._data["x"] = np.array([1, 2, 3])
    with pytest.raises(WireError):
        judge.snapshot({"value": data}, sequence=1)


def test_empty_bitarray_and_databin_shape_tuple_identity():
    judge, candidate = arenas()
    bits = BitArray(np.empty((2, 3, 0), dtype=np.uint8), 0)
    data = DataBin(shape=(2,), bits=bits)
    result, shape, bitshape = transfer(judge, candidate, (data, data.shape, bits.shape))
    assert result.shape is shape and result.bits.shape is bitshape
    assert result.bits.num_bits == 0 and result.bits.num_shots == 3
