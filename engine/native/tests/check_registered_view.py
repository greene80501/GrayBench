"""Bounded native aliases preserve independent flags without accepting pointers."""

import numpy as np
from scipy.linalg import _internal_matfuncs as native
from scipy.linalg import expm

root = expm(np.zeros((2, 2), dtype=np.complex128))
alias = root.view()
root.flags.writeable = False
assert alias.flags.writeable

view = native._graybench_storage_view(root, np.dtype("complex128"), (2, 2), (32, 16), 0)
assert view.base is root
assert view.flags.writeable
view[0, 0] = 13
assert alias[0, 0] == 13


def rejects(*args):
    try:
        native._graybench_storage_view(*args)
    except (TypeError, ValueError, OverflowError):
        return
    raise AssertionError("Invalid registered view was accepted")


rejects(np.zeros((2, 2)), np.dtype("float64"), (2, 2), (16, 8), 0)
rejects(root, np.dtype(object), (2, 2), (16, 8), 0)
rejects(root, np.dtype("complex128"), (2, 2), (32, 16), 16)
rejects(root, np.dtype("complex128"), (2, 2), (-32, 16), 0)
rejects(root, np.dtype("complex128"), (2, 2), (32, 16), -1)
rejects(root, np.dtype("complex128"), (2, 2), (32, 16), 64)
rejects(root, np.dtype("uint8"), (2**24, 2**24), (0, 0), 0)

print("Registered readonly-root writable view and geometry rejections passed")
