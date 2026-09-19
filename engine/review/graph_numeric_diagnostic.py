"""Trusted standalone graph fixture; does not run candidates or score tasks."""

import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import qiskit

import graybench.graph_wire as graph_module
from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def main():
    judge, candidate = (
        GraphArena(side=side, session="numeric-runtime-probe", limits=GraphLimits())
        for side in ("judge", "candidate")
    )

    def transfer(sender, receiver, values, sequence):
        wire = sender.snapshot({"value": values}, sequence=sequence)
        return receiver.commit(receiver.prepare(wire, sequence=sequence))["value"]

    checks = []
    array = np.arange(12, dtype=">i4")
    left, right = array[1:8], array[3:10]
    a, x, y = transfer(judge, candidate, (array, left, right), 1)
    assert x.base is y.base is a and np.shares_memory(x, y)
    x[2] = 91
    assert y[0] == 91
    returned = transfer(candidate, judge, y, 1)
    assert returned is right and left[2] == array[3] == 91
    checks.append("overlap_owner_and_in_place_return")

    a.flags.writeable = False
    assert x.flags.writeable
    x[0] = 17
    transfer(candidate, judge, a, 2)
    assert not array.flags.writeable and left.flags.writeable and array[1] == 17
    checks.append("writable_view_of_readonly_owner")

    for index, scalar_type in enumerate((np.intc, np.uintc, np.int64, np.float32), 3):
        scalar = scalar_type(3)
        source = np.array([1, 2, 3], dtype=scalar_type)
        result, value = transfer(judge, candidate, (source, scalar), index)
        assert result.dtype.type is source.dtype.type and type(value) is type(scalar)
        checks.append("numeric_type_" + scalar_type.__name__)

    backing = np.arange(24, dtype=np.uint8)
    view = np.ndarray((2,), dtype=np.int32, buffer=backing, offset=1)
    _, actual = transfer(judge, candidate, (backing, view), 7)
    assert not actual.flags.aligned
    checks.append("misaligned_storage")

    wire = candidate.snapshot({"value": actual}, sequence=7)
    record = next(n for n in wire["nodes"] if n["id"] == wire["roots"]["value"]["ref"])
    record["state"]["offset"] = 1000
    try:
        judge.prepare(wire, sequence=7)
    except WireError:
        pass
    else:
        raise AssertionError("Out-of-bounds storage was accepted")
    assert backing.tolist() == list(range(24))
    checks.append("malformed_storage_rejected")

    root = Path(graph_module.__file__).parent
    names = (
        "graph_wire.py",
        "graph_types.py",
        "graph_numeric.py",
        "circuit_wire.py",
        "scientific_wire.py",
    )
    print(
        json.dumps(
            {
                "scope": "standalone_graph_development_probe",
                "production_bridge_integrated": False,
                "python": platform.python_version(),
                "system": platform.system(),
                "numpy": np.__version__,
                "qiskit": qiskit.__version__,
                "checks_passed": checks,
                "source_sha256": {
                    name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names
                },
                "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
