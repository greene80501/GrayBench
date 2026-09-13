import numpy as np
import pytest
from qiskit.quantum_info import Choi, Clifford, StabilizerState, random_clifford

from graybench.circuit_wire import WireError
from graybench.value_wire import decode, encode


def test_clifford_preserves_tableau_phase_and_composition():
    original = random_clifford(3, seed=98)
    restored = decode(encode(original))
    assert type(restored) is Clifford
    np.testing.assert_array_equal(restored.tableau, original.tableau)
    assert restored.compose(original.adjoint()) == Clifford(np.eye(6, 7, dtype=bool))


def test_stabilizer_state_preserves_phases_and_statevector():
    original = StabilizerState(random_clifford(3, seed=37))
    restored = decode(encode(original))
    assert type(restored) is StabilizerState
    np.testing.assert_array_equal(restored.clifford.tableau, original.clifford.tableau)
    np.testing.assert_allclose(restored.to_operator().data, original.to_operator().data)


def test_invalid_symplectic_tableau_is_not_repaired():
    original = Clifford(np.zeros((4, 5), dtype=bool), validate=False)
    restored = decode(encode(original))
    np.testing.assert_array_equal(restored.tableau, original.tableau)
    assert not restored.is_unitary()


def test_seeded_stabilizer_cannot_silently_lose_rng_state():
    original = StabilizerState(random_clifford(1, seed=2))
    original.seed(42)
    with pytest.raises(WireError, match="RNG"):
        encode(original)


def test_rectangular_choi_preserves_invalid_channel_and_subsystems():
    data = np.arange(36).reshape(6, 6).astype(complex)
    data[1, 3] += 2j
    original = Choi(data, input_dims=(2,), output_dims=(3,))
    restored = decode(encode(original))
    assert type(restored) is Choi
    assert restored.input_dims() == (2,)
    assert restored.output_dims() == (3,)
    np.testing.assert_array_equal(restored.data, original.data)
    assert not restored.is_cptp()


@pytest.mark.parametrize("mutation", ["dtype", "shape"])
def test_malformed_tableau_rejected(mutation):
    wire = encode(random_clifford(1, seed=1))
    if mutation == "dtype":
        wire["tableau"]["dtype"] = "|u1"
    else:
        wire["tableau"]["shape"] = [3, 2]
    with pytest.raises(WireError):
        decode(wire)
