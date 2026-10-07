/* Experimental CPython 3.12, single-interpreter allocation registry.
 * No pointer or callback enters through the Python API. Records retain exact
 * capsule identities. Registry-only capsules are swept before registration;
 * graph-retained arrays/capsules keep another reference and cannot be swept.
 */
#include <string.h>

static void capsule_destructor(PyObject *capsule);
typedef struct gb_storage {
    PyObject *capsule;
    PyObject *root_weakref;
    void *pointer;
    Py_ssize_t capacity;
    int typenum;
    int ndim;
    npy_intp shape[NPY_MAXDIMS];
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
        Py_XDECREF(entry->root_weakref);
        Py_DECREF(entry->capsule);
        free(entry);
    }
}

static int gb_register(PyObject *capsule, void *pointer, Py_ssize_t capacity,
                       PyArrayObject *root) {
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
    entry->root_weakref = root == NULL ? NULL : PyWeakref_NewRef((PyObject *)root, NULL);
    if (root != NULL && entry->root_weakref == NULL) { free(entry); return -1; }
    entry->capsule = capsule;
    Py_INCREF(capsule);
    entry->pointer = pointer;
    entry->capacity = capacity;
    entry->typenum = root == NULL ? NPY_UINT8 : PyArray_TYPE(root);
    entry->ndim = root == NULL ? 0 : PyArray_NDIM(root);
    if (root != NULL) {
        for (int axis = 0; axis < entry->ndim; axis++) {
            entry->shape[axis] = PyArray_DIM(root, axis);
        }
    }
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
            Py_XDECREF(entry->root_weakref);
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

static PyObject *gb_descriptor(PyObject *self, PyObject *capsule) {
    gb_storage *entry = gb_lookup(capsule);
    if (entry == NULL) { return NULL; }
    char code;
    switch (entry->typenum) {
        case NPY_FLOAT: code = 'f'; break;
        case NPY_DOUBLE: code = 'd'; break;
        case NPY_CFLOAT: code = 'F'; break;
        case NPY_CDOUBLE: code = 'D'; break;
        default:
            PyErr_SetString(PyExc_ValueError, "Unsupported native allocation dtype");
            return NULL;
    }
    if (entry->ndim < 1 || entry->ndim > NPY_MAXDIMS) {
        PyErr_SetString(PyExc_ValueError, "Native allocation has no array origin");
        return NULL;
    }
    PyObject *shape = PyTuple_New(entry->ndim);
    if (shape == NULL) { return NULL; }
    for (int axis = 0; axis < entry->ndim; axis++) {
        PyObject *size = PyLong_FromSsize_t(entry->shape[axis]);
        if (size == NULL) { Py_DECREF(shape); return NULL; }
        PyTuple_SET_ITEM(shape, axis, size);
    }
    PyObject *dtype = PyUnicode_FromStringAndSize(&code, 1);
    PyObject *capacity = PyLong_FromSsize_t(entry->capacity);
    if (dtype == NULL || capacity == NULL) {
        Py_DECREF(shape);
        Py_XDECREF(dtype);
        Py_XDECREF(capacity);
        return NULL;
    }
    PyObject *root = entry->root_weakref == NULL ? Py_None :
        PyWeakref_GetObject(entry->root_weakref);
    PyObject *result = PyTuple_Pack(4, dtype, shape, capacity, root);
    Py_DECREF(shape);
    Py_DECREF(dtype);
    Py_DECREF(capacity);
    return result;
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
    if (gb_register(capsule, buffer, capacity, (PyArrayObject *)array) < 0) {
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

/* Construct an independently writable alias of a registered allocation.
 * Its root may already be readonly; no address is accepted from Python. */
static PyObject *gb_view(PyObject *self, PyObject *args) {
    PyObject *root, *dtype, *shape, *strides, *offset_object;
    if (!PyArg_ParseTuple(args, "OOOOO", &root, &dtype, &shape, &strides,
                          &offset_object)) { return NULL; }
    if (!PyArray_CheckExact(root) || !PyArray_DescrCheck(dtype) ||
        !PyTuple_CheckExact(shape) || !PyTuple_CheckExact(strides) ||
        !PyLong_CheckExact(offset_object)) {
        PyErr_SetString(PyExc_TypeError, "Exact registered root and view geometry required");
        return NULL;
    }
    /* The helper is exposed to the candidate process too. Never create an
     * object/refcounted dtype over raw numeric allocation bytes. */
    switch (((PyArray_Descr *)dtype)->type_num) {
        case NPY_BOOL: case NPY_BYTE: case NPY_UBYTE:
        case NPY_SHORT: case NPY_USHORT: case NPY_INT: case NPY_UINT:
        case NPY_LONG: case NPY_ULONG: case NPY_LONGLONG: case NPY_ULONGLONG:
        case NPY_HALF: case NPY_FLOAT: case NPY_DOUBLE:
        case NPY_CFLOAT: case NPY_CDOUBLE: break;
        default:
            PyErr_SetString(PyExc_TypeError, "Numeric view dtype required");
            return NULL;
    }
    PyObject *capsule = PyArray_BASE((PyArrayObject *)root);
    if (capsule == NULL) {
        PyErr_SetString(PyExc_TypeError, "Registered capsule-backed root required");
        return NULL;
    }
    gb_storage *entry = gb_lookup(capsule);
    if (entry == NULL) { return NULL; }
    if (entry->root_weakref == NULL ||
        PyWeakref_GetObject(entry->root_weakref) != root ||
        PyArray_DATA((PyArrayObject *)root) != entry->pointer) {
        PyErr_SetString(PyExc_ValueError, "Registered root identity changed");
        return NULL;
    }
    Py_ssize_t ndim = PyTuple_GET_SIZE(shape);
    if (ndim > NPY_MAXDIMS || PyTuple_GET_SIZE(strides) != ndim) {
        PyErr_SetString(PyExc_ValueError, "Invalid view dimension count");
        return NULL;
    }
    Py_ssize_t offset = PyLong_AsSsize_t(offset_object);
    if (offset == -1 && PyErr_Occurred()) { return NULL; }
    if (offset < 0 || offset > entry->capacity) {
        PyErr_SetString(PyExc_ValueError, "View offset exceeds registered storage");
        return NULL;
    }
    npy_intp dims[NPY_MAXDIMS], steps[NPY_MAXDIMS];
    Py_ssize_t itemsize = PyDataType_ELSIZE((PyArray_Descr *)dtype);
    if (itemsize < 1 || itemsize > GB_STORAGE_LIMIT) {
        PyErr_SetString(PyExc_ValueError, "Invalid numeric view item size");
        return NULL;
    }
    Py_ssize_t logical = itemsize;
    /* Maximum capacity and dimension count keep these sums below int64. */
    Py_ssize_t low = offset, high = offset;
    int empty = 0;
    for (Py_ssize_t axis = 0; axis < ndim; axis++) {
        PyObject *length = PyTuple_GET_ITEM(shape, axis);
        PyObject *stride = PyTuple_GET_ITEM(strides, axis);
        if (!PyLong_CheckExact(length) || !PyLong_CheckExact(stride)) {
            PyErr_SetString(PyExc_TypeError, "Exact view dimensions and strides required");
            return NULL;
        }
        dims[axis] = PyLong_AsSsize_t(length);
        if (dims[axis] == -1 && PyErr_Occurred()) { return NULL; }
        steps[axis] = PyLong_AsSsize_t(stride);
        if (steps[axis] == -1 && PyErr_Occurred()) { return NULL; }
        if (dims[axis] < 0 || dims[axis] > GB_STORAGE_LIMIT ||
            steps[axis] < -GB_STORAGE_LIMIT || steps[axis] > GB_STORAGE_LIMIT) {
            PyErr_SetString(PyExc_ValueError, "Unbounded view dimension or stride");
            return NULL;
        }
        if (dims[axis] == 0) { empty = 1; }
        if (dims[axis] != 0 && logical > GB_STORAGE_LIMIT / dims[axis]) {
            PyErr_SetString(PyExc_ValueError, "Logical view exceeds transport limit");
            return NULL;
        }
        logical *= dims[axis];
    }
    if (!empty) {
        for (Py_ssize_t axis = 0; axis < ndim; axis++) {
            Py_ssize_t delta = (dims[axis] - 1) * steps[axis];
            if (delta < 0) { low += delta; } else { high += delta; }
        }
        if (low < 0 || high > entry->capacity - itemsize) {
            PyErr_SetString(PyExc_ValueError, "View exceeds registered storage");
            return NULL;
        }
    }
    Py_INCREF(dtype); /* PyArray_NewFromDescr steals this reference. */
    PyObject *view = PyArray_NewFromDescr(
        &PyArray_Type, (PyArray_Descr *)dtype, (int)ndim, dims, steps,
        (char *)entry->pointer + offset, NPY_ARRAY_WRITEABLE, NULL);
    if (view == NULL) { return NULL; }
    Py_INCREF(root); /* PyArray_SetBaseObject steals this reference. */
    if (PyArray_SetBaseObject((PyArrayObject *)view, root) < 0) {
        Py_DECREF(view);
        return NULL;
    }
    PyArray_ENABLEFLAGS((PyArrayObject *)view, NPY_ARRAY_WRITEABLE);
    return view;
}
