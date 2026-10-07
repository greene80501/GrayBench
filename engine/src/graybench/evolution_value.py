"""Independent basis-index oracle for declared Pauli evolution matrix values."""

import math
from itertools import product

TASK116_ORACLE = "task116-pauli-evolution-matrix-values-v1"


def evolution_case_inputs():
    """Freeze legacy action probes, all width-1/2 tensors at three times, and width 5."""
    initial = (
        ("I", 0.0),
        ("I", 0.37),
        ("X", 1.0),
        ("X", -0.23),
        ("Y", 0.41),
        ("Z", -0.61),
        ("XI", 0.29),
        ("IX", 0.29),
        ("YZ", -0.47),
        ("ZY", -0.47),
        ("ZZ", 0.0),
        ("II", 0.73),
        ("XYZ", 0.19),
        ("ZYX", -0.53),
        ("IXYZ", 0.11),
        ("ZYXI", -0.31),
    )
    seen = set()
    for case in initial:
        seen.add(case)
        yield case
    for width in (1, 2):
        for letters in product("IXYZ", repeat=width):
            for time in (0.0, 0.37, -0.23):
                case = ("".join(letters), time)
                if case not in seen:
                    seen.add(case)
                    yield case
    yield from (
        ("IIIII", 0.37),
        ("XXXXI", 0.19),
        ("IXXXX", 0.19),
        ("YXZIY", -0.43),
        ("YIZXY", 0.67),
        ("ZZZZZ", -0.22),
        ("XXXXX", 1.0),
        ("IXYZI", 0.59),
    )


def _finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def check_evolution_matrix(label, time, value):
    """Check exp(-i*t*P) without SDK extraction, eigensolvers or tensor matrices."""
    if (
        type(label) is not str
        or not 1 <= len(label) <= 5
        or any(char not in "IXYZ" for char in label)
        or not _finite_number(time)
    ):
        return {"passed": False, "reason": "invalid_case"}
    size = 1 << len(label)
    if (
        type(value) is not list
        or len(value) != size
        or any(type(row) is not list or len(row) != size for row in value)
    ):
        return {"passed": False, "reason": "invalid_matrix_shape"}
    cosine, sine = math.cos(time), math.sin(time)
    max_error = 0.0
    for column in range(size):
        destination, factor = column, 1 + 0j
        for qubit, char in enumerate(reversed(label)):
            bit = (column >> qubit) & 1
            if char in "XY":
                destination ^= 1 << qubit
            if char == "Y":
                factor *= -1j if bit else 1j
            elif char == "Z" and bit:
                factor = -factor
        for row in range(size):
            pair = value[row][column]
            if type(pair) is not list or len(pair) != 2 or not all(map(_finite_number, pair)):
                return {"passed": False, "reason": "invalid_matrix_entry"}
            expected = cosine if row == column else 0.0
            if row == destination:
                expected += -1j * sine * factor
            try:
                error = abs(complex(*pair) - expected)
            except OverflowError:
                return {"passed": False, "reason": "nonfinite_matrix_error"}
            if not math.isfinite(error):
                return {"passed": False, "reason": "nonfinite_matrix_error"}
            max_error = max(max_error, error)
    return {"passed": max_error <= 1e-10, "max_entry_error": max_error}
