"""Use ASan's real malloc/free instrumentation on the production registry header."""

import ctypes
import sys

sys.path.insert(0, "/tmp")
import _registry_test as registry  # noqa: E402

callback_type = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
get_destructor = ctypes.pythonapi.PyCapsule_GetDestructor
get_destructor.argtypes = [ctypes.py_object]
get_destructor.restype = ctypes.c_void_p
set_destructor = ctypes.pythonapi.PyCapsule_SetDestructor
set_destructor.argtypes = [ctypes.py_object, ctypes.c_void_p]
set_destructor.restype = ctypes.c_int
held = []
calls = []
victim = registry.allocate()
original_destructor = ctypes.PYFUNCTYPE(None, ctypes.c_void_p)(get_destructor(victim))
held.append(registry.allocate())


@callback_type
def reenter(capsule):
    held.clear()
    nested = registry.allocate()
    calls.append(registry.read(nested))
    original_destructor(capsule)


assert set_destructor(victim, ctypes.cast(reenter, ctypes.c_void_p)) == 0
del victim
survivor = registry.allocate()
assert calls == [bytes(32)]
assert registry.read(survivor) == bytes(32)
victims = [registry.allocate() for _ in range(3)]
for victim in victims:
    assert set_destructor(victim, ctypes.cast(reenter, ctypes.c_void_p)) == 0
del victim
victims.clear()
survivor = registry.allocate()
assert calls == [bytes(32)] * 4, "Each detached capsule must finalize exactly once"
assert registry.read(survivor) == bytes(32)
print("ASan nested cleanup regression passed")
