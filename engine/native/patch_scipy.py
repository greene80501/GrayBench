"""Apply one hash-bound experimental patch to the pinned SciPy native module."""

import hashlib
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])
target = root / "scipy/linalg/_matfuncsmodule.c"
raw = target.read_bytes()
assert (
    hashlib.sha256(raw).hexdigest()
    == "e2e6897101a0743a8921c5aac18f767b626516e58f7f5d56bc0f54180dffd54d"
)
source = raw.decode()
source = source.replace(
    "static PyObject* matfuncs_error;",
    'static PyObject* matfuncs_error;\n#include "registered_storage.h"',
    1,
)
source = source.replace(
    "    void *ptr = PyCapsule_GetPointer(capsule, NULL);",
    "    gb_unregister(capsule);\n    void *ptr = PyCapsule_GetPointer(capsule, NULL);",
    1,
)
needle = "    if (PyArray_SetBaseObject(ap_ret, capsule) == -1) {"
assert source.count(needle) == 2
# NumPy steals the supplied reference on success AND failure. Preserve the new
# registration-error decref below, but remove the inherited SetBaseObject ones.
cleanup = needle + "\n        Py_DECREF(ap_ret);\n        Py_DECREF(capsule);"
assert source.count(cleanup) == 2
source = source.replace(cleanup, needle + "\n        Py_DECREF(ap_ret);")
source = source.replace(
    needle,
    """    if (gb_register(capsule, mem_ret, PyArray_NBYTES(ap_ret), ap_ret) < 0) {
        Py_DECREF(ap_ret);
        Py_DECREF(capsule);
        return NULL;
    }
"""
    + needle,
)
source = source.replace(
    "  {NULL, NULL, 0, NULL}",
    """  {"_graybench_storage_info", gb_info, METH_O, "Registered storage metadata."},
  {"_graybench_storage_descriptor", gb_descriptor, METH_O, "Registered storage origin."},
  {"_graybench_storage_read", gb_read, METH_O, "Read bounded registered storage."},
  {"_graybench_storage_write", gb_write, METH_VARARGS, "Write exact registered storage."},
  {"_graybench_storage_new", gb_new, METH_VARARGS, "Allocate bounded registered storage."},
  {"_graybench_storage_view", gb_view, METH_VARARGS, "Construct bounded registered alias."},
  {NULL, NULL, 0, NULL}""",
    1,
)
# This experimental registry has one GIL-protected global state; do not advertise
# per-interpreter or free-threaded support which has not been implemented.
source = source.replace(
    "Py_MOD_PER_INTERPRETER_GIL_SUPPORTED", "Py_MOD_MULTIPLE_INTERPRETERS_NOT_SUPPORTED"
)
source = source.replace("Py_MOD_GIL_NOT_USED", "Py_MOD_GIL_USED")
target.write_text(source, encoding="utf-8", newline="\n")
shutil.copyfile(
    Path(__file__).with_name("registered_storage.h"), target.with_name("registered_storage.h")
)
print("Applied hash-bound registered-storage experiment")
