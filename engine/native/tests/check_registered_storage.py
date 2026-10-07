"""Experimental native runtime contract; run inside the declared development image."""

import gc
import sys
import weakref

import numpy as np
from scipy.linalg import _internal_matfuncs as native
from scipy.linalg import expm, sqrtm

assert callable(getattr(native, "_graybench_storage_info", None)), (
    "Native allocation registry missing"
)
assert callable(getattr(native, "_graybench_storage_read", None)), "Native storage reader missing"
assert callable(getattr(native, "_graybench_storage_write", None)), "Native storage writer missing"

for dtype in (np.float32, np.float64, np.complex64, np.complex128):
    array = expm(np.zeros((3, 3), dtype=dtype))
    capsule = array.base
    capacity = array.nbytes
    assert native._graybench_storage_info(capsule) == ("scipy_matfuncs_v1", capacity)
    alias = array.view()
    original = native._graybench_storage_read(capsule)
    assert original == array.tobytes()
    array.flags.writeable = False
    replacement = np.full((3, 3), 2, dtype=dtype).tobytes()
    native._graybench_storage_write(capsule, replacement)
    assert np.all(array == 2) and np.all(alias == 2)
    assert not array.flags.writeable and alias.flags.writeable
    try:
        array.flags.writeable = True
    except ValueError:
        pass
    else:
        raise AssertionError("Native readonly behavior changed")
    try:
        native._graybench_storage_write(capsule, replacement + b"x")
    except ValueError:
        pass
    else:
        raise AssertionError("Oversized update accepted")
    assert native._graybench_storage_read(capsule) == replacement
    array.shape = (9,)
    assert native._graybench_storage_info(capsule)[1] == capacity

for unknown in (None, object(), np.zeros(1), np.arange(2).__dlpack__()):
    try:
        native._graybench_storage_info(unknown)
    except (TypeError, ValueError):
        pass
    else:
        raise AssertionError("Unregistered object accepted")

for source in (np.eye(2), -np.eye(2), np.eye(2, dtype=complex)):
    array = sqrtm(source)
    assert native._graybench_storage_info(array.base)[1] == array.nbytes
    np.testing.assert_allclose(array @ array, source, atol=1e-12)

root = expm(np.eye(2))
retained = root.base
assert sys.getrefcount(retained) >= 4, "Registry must retain capsule identity"
root_reference = weakref.ref(root)
saved = root.tobytes()
del root
gc.collect()
assert root_reference() is None
assert native._graybench_storage_read(retained) == saved
print("Retained capsule survives root deletion; unregistered DLPack capsule rejected")
print("Registered storage contract passed")
