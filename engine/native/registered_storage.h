/* Experimental CPython 3.12, single-interpreter allocation registry.
 * No pointer or callback enters through the Python API. Records retain exact
 * capsule identities. Registry-only capsules are swept before registration;
 * graph-retained arrays/capsules keep another reference and cannot be swept.
 */
#include <string.h>

static void capsule_destructor(PyObject *capsule);
typedef struct gb_storage {
    PyObject *capsule;
    void *pointer;
    Py_ssize_t capacity;
    struct gb_storage *next;
} gb_storage;
static gb_storage *gb_head = NULL;
#define GB_STORAGE_LIMIT (16 * 1024 * 1024)
#define GB_REGISTRY_ENTRIES 65536
#define GB_REGISTRY_BYTES (256 * 1024 * 1024)

static void gb_sweep(void) {
    gb_storage **link = &gb_head;
    gb_storage *retired = NULL;
    while (*link != NULL) {
        gb_storage *entry = *link;
        if (Py_REFCNT(entry->capsule) == 1) {
            *link = entry->next;
            entry->next = retired;
            retired = entry;
        } else {
            link = &entry->next;
        }
    }
    /* Callbacks may recursively sweep the live registry. Finish traversing it
     * before any decref; keep only detached nodes across callback execution. */
    while (retired != NULL) {
        gb_storage *entry = retired;
        retired = entry->next;
        Py_DECREF(entry->capsule);
        free(entry);
    }
}

static int gb_register(PyObject *capsule, void *pointer, Py_ssize_t capacity) {
    gb_sweep();
    Py_ssize_t count = 0, bytes = 0;
    for (gb_storage *item = gb_head; item != NULL; item = item->next) {
        count++;
        bytes += item->capacity;
    }
    if (capacity < 0 || capacity > GB_REGISTRY_BYTES ||
        count >= GB_REGISTRY_ENTRIES || bytes > GB_REGISTRY_BYTES - capacity) {
        PyErr_SetString(PyExc_MemoryError, "Experimental native registry capacity exceeded");
        return -1;
    }
    gb_storage *entry = malloc(sizeof(*entry));
    if (entry == NULL) { PyErr_NoMemory(); return -1; }
    entry->capsule = capsule;
    Py_INCREF(capsule);
    entry->pointer = pointer;
    entry->capacity = capacity;
    entry->next = gb_head;
    gb_head = entry;
    return 0;
}

static void gb_unregister(PyObject *capsule) {
    gb_storage **link = &gb_head;
    while (*link != NULL) {
        if ((*link)->capsule == capsule) {
            gb_storage *entry = *link;
            *link = entry->next;
            Py_DECREF(entry->capsule);
            free(entry);
            return;
        }
        link = &(*link)->next;
    }
}

static gb_storage *gb_lookup(PyObject *capsule) {
    if (!PyCapsule_CheckExact(capsule)) {
        PyErr_SetString(PyExc_TypeError, "Registered native capsule required");
        return NULL;
    }
    for (gb_storage *entry = gb_head; entry != NULL; entry = entry->next) {
        if (entry->capsule != capsule) { continue; }
        if (!PyCapsule_IsValid(capsule, NULL) ||
            PyCapsule_GetDestructor(capsule) != capsule_destructor ||
            PyCapsule_GetContext(capsule) != NULL ||
            PyCapsule_GetPointer(capsule, NULL) != entry->pointer) {
            PyErr_SetString(PyExc_ValueError, "Registered capsule metadata changed");
            return NULL;
        }
        if (entry->capacity < 0 || entry->capacity > GB_STORAGE_LIMIT) {
            PyErr_SetString(PyExc_ValueError, "Registered allocation exceeds transport limit");
            return NULL;
        }
        return entry;
    }
    PyErr_SetString(PyExc_ValueError, "Unknown native allocation");
    return NULL;
}

static PyObject *gb_info(PyObject *self, PyObject *capsule) {
    gb_storage *entry = gb_lookup(capsule);
    if (entry == NULL) { return NULL; }
    return Py_BuildValue("sn", "scipy_matfuncs_v1", entry->capacity);
}

static PyObject *gb_read(PyObject *self, PyObject *capsule) {
    gb_storage *entry = gb_lookup(capsule);
    if (entry == NULL) { return NULL; }
    return PyBytes_FromStringAndSize((const char *)entry->pointer, entry->capacity);
}

static PyObject *gb_write(PyObject *self, PyObject *args) {
    PyObject *capsule, *data;
    if (!PyArg_ParseTuple(args, "OO", &capsule, &data)) { return NULL; }
    gb_storage *entry = gb_lookup(capsule);
    if (entry == NULL) { return NULL; }
    if (!PyBytes_CheckExact(data) || PyBytes_GET_SIZE(data) != entry->capacity) {
        PyErr_SetString(PyExc_ValueError, "Exact allocation-sized bytes required");
        return NULL;
    }
    memcpy(entry->pointer, PyBytes_AS_STRING(data), (size_t)entry->capacity);
    Py_RETURN_NONE;
}

static PyObject *gb_new(PyObject *self, PyObject *args) {
    const char *dtype;
    PyObject *shape;
    if (!PyArg_ParseTuple(args, "sO", &dtype, &shape)) { return NULL; }
    if (dtype[0] == '\0' || dtype[1] != '\0' ||
        !PyTuple_CheckExact(shape) || PyTuple_GET_SIZE(shape) != 2) {
        PyErr_SetString(PyExc_ValueError, "A supported dtype and two exact dimensions are required");
        return NULL;
    }
    int typenum, itemsize;
    switch (dtype[0]) {
        case 'f': typenum = NPY_FLOAT; itemsize = 4; break;
        case 'd': typenum = NPY_DOUBLE; itemsize = 8; break;
        case 'F': typenum = NPY_CFLOAT; itemsize = 8; break;
        case 'D': typenum = NPY_CDOUBLE; itemsize = 16; break;
        default:
            PyErr_SetString(PyExc_ValueError, "Unsupported registered native dtype");
            return NULL;
    }
    npy_intp dims[2];
    for (int axis = 0; axis < 2; axis++) {
        PyObject *value = PyTuple_GET_ITEM(shape, axis);
        if (!PyLong_CheckExact(value)) {
            PyErr_SetString(PyExc_TypeError, "Exact integer dimensions required");
            return NULL;
        }
        dims[axis] = PyLong_AsSsize_t(value);
        if (dims[axis] == -1 && PyErr_Occurred()) { return NULL; }
        if (dims[axis] <= 0) {
            PyErr_SetString(PyExc_ValueError, "Positive dimensions required");
            return NULL;
        }
    }
    if (dims[0] > GB_STORAGE_LIMIT / itemsize / dims[1]) {
        PyErr_SetString(PyExc_MemoryError, "Registered native allocation exceeds transport limit");
        return NULL;
    }
    Py_ssize_t capacity = dims[0] * dims[1] * itemsize;
    void *buffer = calloc(1, (size_t)capacity);
    if (buffer == NULL) { return PyErr_NoMemory(); }
    PyObject *array = PyArray_SimpleNewFromData(2, dims, typenum, buffer);
    if (array == NULL) { free(buffer); return NULL; }
    PyObject *capsule = PyCapsule_New(buffer, NULL, capsule_destructor);
    if (capsule == NULL) { Py_DECREF(array); free(buffer); return NULL; }
    if (gb_register(capsule, buffer, capacity) < 0) {
        Py_DECREF(array);
        Py_DECREF(capsule);
        return NULL;
    }
    /* NumPy steals the capsule reference even on error. The registry keeps its
     * own reference, so the unowned buffer is released at the next sweep. */
    if (PyArray_SetBaseObject((PyArrayObject *)array, capsule) < 0) {
        Py_DECREF(array);
        return NULL;
    }
    return array;
}
