"""Run only in an isolated native experiment container: exercise destructor reentry."""

import ctypes
import sys

import numpy as np
from scipy.linalg import _internal_matfuncs as native
from scipy.linalg import expm

set_destructor = ctypes.pythonapi.PyCapsule_SetDestructor
set_destructor.argtypes = [ctypes.py_object, ctypes.c_void_p]
set_destructor.restype = ctypes.c_int
callback_type = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
get_destructor = ctypes.pythonapi.PyCapsule_GetDestructor
get_destructor.argtypes = [ctypes.py_object]
get_destructor.restype = ctypes.c_void_p
original_destructor = None
held = []
calls = []


@callback_type
def reenter(_capsule):
    # The preceding registry node loses its last external reference, then a
    # nested allocation sweeps it. No pointer into the live list may survive
    # this callback in the outer sweep.
    held.clear()
    nested = expm(np.eye(2))
    calls.append(native._graybench_storage_read(nested.base))
    original_destructor(_capsule)


for iteration in range(100):
    victim = expm(np.eye(2))
    # Keep victim alive while allocating the preceding list node.
    held.append(expm(np.eye(2)))
    original_destructor = ctypes.PYFUNCTYPE(None, ctypes.c_void_p)(get_destructor(victim.base))
    assert sys.getrefcount(victim.base) >= 3, "Strong identity registry required"
    assert set_destructor(victim.base, ctypes.cast(reenter, ctypes.c_void_p)) == 0
    del victim
    survivor = expm(np.eye(2))
    assert len(calls) == iteration + 1, "Replacement destructor was not invoked"
    assert not held
    assert native._graybench_storage_read(survivor.base) == survivor.tobytes()

print("100 nested cleanup callbacks completed with valid surviving allocations")
