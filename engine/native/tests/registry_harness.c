/* Test-only ASan harness compiling the actual registry implementation. */
#include <Python.h>
#include <numpy/arrayobject.h>
#include "../registered_storage.h"

static void capsule_destructor(PyObject *capsule) {
    gb_unregister(capsule);
    free(PyCapsule_GetPointer(capsule, NULL));
}

static PyObject *allocate(PyObject *self, PyObject *unused) {
    void *buffer = calloc(1, 32);
    if (buffer == NULL) { return PyErr_NoMemory(); }
    PyObject *capsule = PyCapsule_New(buffer, NULL, capsule_destructor);
    if (capsule == NULL) { free(buffer); return NULL; }
    if (gb_register(capsule, buffer, 32, NULL) < 0) {
        Py_DECREF(capsule);
        return NULL;
    }
    return capsule;
}

static PyMethodDef methods[] = {
    {"allocate", allocate, METH_NOARGS, NULL},
    {"read", gb_read, METH_O, NULL},
    {"new", gb_new, METH_VARARGS, NULL},
    {"view", gb_view, METH_VARARGS, NULL},
    {NULL, NULL, 0, NULL}
};
static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT, "_registry_test", NULL, -1, methods
};
PyMODINIT_FUNC PyInit__registry_test(void) {
    import_array();
    return PyModule_Create(&module);
}
