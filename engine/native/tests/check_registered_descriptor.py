"""A capsule exported alone still needs trusted origin metadata and extent."""

import gc
import weakref

import numpy as np
from scipy.linalg import _internal_matfuncs as native
from scipy.linalg import expm

for dtype in (np.float32, np.float64, np.complex64, np.complex128):
    root = expm(np.zeros((3, 3), dtype=dtype))
    capsule = root.base
    original = native._graybench_storage_read(capsule)
    code, shape, capacity, alive = native._graybench_storage_descriptor(capsule)
    assert code == root.dtype.char and shape == (3, 3)
    assert capacity == root.nbytes and alive is root
    root.shape = (9,)
    assert native._graybench_storage_descriptor(capsule)[1] == (3, 3)
    reference = weakref.ref(root)
    del alive, root
    gc.collect()
    assert reference() is None
    code, shape, capacity, alive = native._graybench_storage_descriptor(capsule)
    assert code == np.dtype(dtype).char and shape == (3, 3)
    assert capacity == len(original) and alive is None
    assert native._graybench_storage_read(capsule) == original

try:
    native._graybench_storage_descriptor(np.arange(2).__dlpack__())
except (TypeError, ValueError):
    pass
else:
    raise AssertionError("Foreign capsule obtained trusted descriptor")

print("Registered capsule origin survives array mutation and deletion")
