"""Native metadata forgery controls, isolated from the host benchmark process."""

import ctypes

import numpy as np
from scipy.linalg import _internal_matfuncs as native
from scipy.linalg import expm

array = expm(np.eye(2))
capsule = array.base
saved = array.tobytes()
get_pointer = ctypes.pythonapi.PyCapsule_GetPointer
get_pointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
get_pointer.restype = ctypes.c_void_p
get_destructor = ctypes.pythonapi.PyCapsule_GetDestructor
get_destructor.argtypes = [ctypes.py_object]
get_destructor.restype = ctypes.c_void_p
pointer = get_pointer(capsule, None)
destructor = get_destructor(capsule)
foreign = ctypes.create_string_buffer(len(saved))

for field, argtype, changed, original in (
    ("Name", ctypes.c_char_p, b"foreign", None),
    ("Context", ctypes.c_void_p, ctypes.addressof(foreign), None),
    ("Pointer", ctypes.c_void_p, ctypes.addressof(foreign), pointer),
    ("Destructor", ctypes.c_void_p, None, destructor),
):
    setter = getattr(ctypes.pythonapi, "PyCapsule_Set" + field)
    setter.argtypes = [ctypes.py_object, argtype]
    setter.restype = ctypes.c_int
    assert setter(capsule, changed) == 0
    try:
        for operation in (
            lambda: native._graybench_storage_info(capsule),
            lambda: native._graybench_storage_read(capsule),
            lambda: native._graybench_storage_write(capsule, saved),
        ):
            try:
                operation()
            except ValueError:
                pass
            else:
                raise AssertionError(f"Modified capsule {field} was accepted")
    finally:
        assert setter(capsule, original) == 0
    assert native._graybench_storage_read(capsule) == saved
    assert foreign.raw == bytes(len(saved)), "Foreign allocation was written"

print("All four modified capsule fields rejected by info/read/write")
