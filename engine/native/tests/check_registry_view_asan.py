"""Exercise the actual header view constructor under AddressSanitizer."""

import sys

import numpy as np

sys.path.insert(0, "/tmp")
import _registry_test as native  # noqa: E402

root = native.new("D", (2, 2))
root.flags.writeable = False
view = native.view(root, np.dtype("complex128"), (2, 2), (32, 16), 0)
assert view.base is root and view.flags.writeable
view[0, 0] = 17
assert root[0, 0] == 17


def rejects(*args):
    try:
        native.view(*args)
    except (TypeError, ValueError, OverflowError):
        return
    raise AssertionError("Invalid native view was accepted")


rejects(np.zeros((2, 2)), np.dtype("float64"), (2, 2), (16, 8), 0)
rejects(root, np.dtype(object), (2, 2), (16, 8), 0)
rejects(root, np.dtype("uint8"), (2**24, 2**24), (0, 0), 0)
rejects(root, np.dtype("complex128"), (2, 2), (32, 16), 16)
print("ASan registered native view rejection and writable alias passed")
