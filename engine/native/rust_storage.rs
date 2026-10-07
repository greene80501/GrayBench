// GrayBench experimental adaptation of Rust NumPy 0.28.0.
// Original Rust NumPy remains under its BSD-2-Clause license. This added module
// records allocation provenance; it does not change numerical algorithms.
// Supported only with the CPython GIL, not a free-threaded interpreter.

use crate::{
    npyffi::{self, PY_ARRAY_API},
    slice_container::PySliceContainer,
    Element, PyArrayDescr, PyArrayDescrMethods, PyUntypedArray, PyUntypedArrayMethods,
};
use pyo3::{
    exceptions::{PyTypeError, PyValueError},
    ffi,
    prelude::*,
    types::{PyBytes, PyInt, PyString, PyTuple},
    PyTypeInfo,
};
use std::{mem, ptr, slice, sync::OnceLock};

const LIMIT: usize = 16 * 1024 * 1024;

#[derive(Debug)]
struct Origin {
    weak: Py<PyAny>,
    offset: usize,
}

#[derive(Debug)]
pub(crate) struct Storage {
    code: Option<&'static str>,
    kind: &'static str,
    initialized: usize,
    allocated: usize,
    origin: OnceLock<Origin>,
}

impl Storage {
    pub(crate) fn of<T>(len: usize, cap: usize, kind: &'static str) -> Self {
        let code = match std::any::type_name::<T>() {
            "f32" => Some("f"),
            "f64" => Some("d"),
            "num_complex::Complex<f32>" => Some("F"),
            "num_complex::Complex<f64>" => Some("D"),
            _ => None,
        };
        Self {
            code,
            kind,
            initialized: len.checked_mul(mem::size_of::<T>()).unwrap_or(usize::MAX),
            allocated: cap.checked_mul(mem::size_of::<T>()).unwrap_or(usize::MAX),
            origin: OnceLock::new(),
        }
    }
}

fn exact<T: PyTypeInfo>(value: &Bound<'_, PyAny>) -> PyResult<()> {
    if !value.get_type().is(value.py().get_type::<T>()) {
        return Err(PyTypeError::new_err("Exact native input type required"));
    }
    Ok(())
}

fn integer(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    exact::<PyInt>(value)?;
    value.extract()
}

fn text<'a>(value: &'a Bound<'_, PyAny>) -> PyResult<&'a str> {
    exact::<PyString>(value)?;
    value.cast::<PyString>()?.to_str()
}

fn checked<'a>(owner: &'a Bound<'_, PyAny>) -> PyResult<&'a PySliceContainer> {
    exact::<PySliceContainer>(owner)?;
    let storage = owner.cast::<PySliceContainer>()?.get();
    let meta = &storage.graybench;
    if meta.code.is_none()
        || meta.initialized > meta.allocated
        || meta.allocated > LIMIT
        || meta
            .origin
            .get()
            .is_none_or(|origin| origin.offset > meta.initialized)
    {
        return Err(PyValueError::new_err(
            "Unsupported or unbounded Rust storage",
        ));
    }
    Ok(storage)
}

pub(crate) fn register(
    owner: &Bound<'_, PySliceContainer>,
    root: &Bound<'_, PyAny>,
) -> PyResult<()> {
    exact::<PyUntypedArray>(root)?;
    let array = root.cast::<PyUntypedArray>()?;
    let storage = owner.get();
    let address = unsafe { (*array.as_array_ptr()).data as usize };
    let offset = address
        .checked_sub(storage.ptr as usize)
        .ok_or_else(|| PyValueError::new_err("Root precedes Rust allocation"))?;
    // Never dereference memory here: unsupported generic/ZST allocations retain
    // upstream behavior but cannot be inspected through the bounded helpers.
    let weak = unsafe {
        Bound::<PyAny>::from_owned_ptr_or_err(
            root.py(),
            ffi::PyWeakref_NewRef(root.as_ptr(), ptr::null_mut()),
        )?
    };
    storage
        .graybench
        .origin
        .set(Origin {
            weak: weak.unbind(),
            offset,
        })
        .map_err(|_| PyValueError::new_err("Rust root already registered"))
}

fn live_root<'py>(
    py: Python<'py>,
    storage: &PySliceContainer,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let origin = storage.graybench.origin.get().unwrap();
    // The strong owner argument keeps Origin alive; GIL prevents weak referent
    // destruction between borrowing it and acquiring our strong reference.
    let root =
        unsafe { Bound::from_borrowed_ptr(py, ffi::PyWeakref_GetObject(origin.weak.as_ptr())) };
    if root.is_none() {
        return Ok(None);
    }
    exact::<PyUntypedArray>(&root)?;
    let array = root.cast::<PyUntypedArray>()?;
    let raw = unsafe { &*array.as_array_ptr() };
    if raw.base.is_null() {
        return Err(PyValueError::new_err("Registered root lost its owner"));
    }
    let owner = unsafe { Bound::from_borrowed_ptr(py, raw.base) };
    if !std::ptr::eq(checked(&owner)?, storage) {
        return Err(PyValueError::new_err("Registered root changed its owner"));
    }
    if raw.data as usize
        != (storage.ptr as usize)
            .checked_add(origin.offset)
            .ok_or_else(|| PyValueError::new_err("Root offset overflow"))?
    {
        return Err(PyValueError::new_err("Registered root data changed"));
    }
    Ok(Some(root))
}

#[pyfunction]
fn _graybench_rust_storage_descriptor<'py>(
    owner: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyTuple>> {
    let storage = checked(owner)?;
    let meta = &storage.graybench;
    let root = live_root(owner.py(), storage)?;
    PyTuple::new(
        owner.py(),
        [
            meta.code.unwrap().into_pyobject(owner.py())?.into_any(),
            meta.kind.into_pyobject(owner.py())?.into_any(),
            meta.initialized.into_pyobject(owner.py())?.into_any(),
            meta.allocated.into_pyobject(owner.py())?.into_any(),
            meta.origin
                .get()
                .unwrap()
                .offset
                .into_pyobject(owner.py())?
                .into_any(),
            root.unwrap_or_else(|| owner.py().None().into_bound(owner.py())),
        ],
    )
}

#[pyfunction]
fn _graybench_rust_storage_read<'py>(owner: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyBytes>> {
    let storage = checked(owner)?;
    // Initialized numeric elements only. Spare Vec capacity is never read.
    let bytes = unsafe { slice::from_raw_parts(storage.ptr, storage.graybench.initialized) };
    Ok(PyBytes::new(owner.py(), bytes))
}

#[pyfunction]
fn _graybench_rust_storage_write(
    owner: &Bound<'_, PyAny>,
    data: &Bound<'_, PyAny>,
) -> PyResult<()> {
    exact::<PyBytes>(data)?;
    let bytes = data.cast::<PyBytes>()?.as_bytes();
    let storage = checked(owner)?;
    if bytes.len() != storage.graybench.initialized {
        return Err(PyValueError::new_err(
            "Exact initialized byte length required",
        ));
    }
    // Numeric primitives have no invalid bit patterns or drop glue. Storage
    // lifetime is protected by the owner argument; no Rust slice borrow survives.
    unsafe {
        ptr::copy_nonoverlapping(bytes.as_ptr(), storage.ptr, bytes.len());
    }
    Ok(())
}

fn geometry(
    shape: &Bound<'_, PyAny>,
    strides: &Bound<'_, PyAny>,
    offset: i64,
    size: usize,
    initialized: usize,
) -> PyResult<(Vec<isize>, Vec<isize>)> {
    exact::<PyTuple>(shape)?;
    exact::<PyTuple>(strides)?;
    let shape = shape.cast::<PyTuple>()?;
    let strides = strides.cast::<PyTuple>()?;
    if shape.len() > 32
        || shape.len() != strides.len()
        || offset < 0
        || offset as usize > initialized
    {
        return Err(PyValueError::new_err("Invalid native view geometry"));
    }
    let mut dims = Vec::new();
    let mut steps = Vec::new();
    let mut logical = size as u128;
    let mut low = offset as i128;
    let mut high = low;
    let mut empty = false;
    for (length, stride) in shape.iter().zip(strides.iter()) {
        let n = integer(&length)?;
        let s = integer(&stride)?;
        if n < 0 || n as usize > LIMIT || s < -(LIMIT as i64) || s > LIMIT as i64 {
            return Err(PyValueError::new_err("Unbounded native view geometry"));
        }
        if n == 0 {
            empty = true;
        }
        logical *= n as u128;
        if logical > LIMIT as u128 {
            return Err(PyValueError::new_err("Logical view too large"));
        }
        let delta = (n as i128 - 1).max(0) * s as i128;
        low += delta.min(0);
        high += delta.max(0);
        dims.push(n as isize);
        steps.push(s as isize);
    }
    if !empty && (low < 0 || high + size as i128 > initialized as i128) {
        return Err(PyValueError::new_err(
            "View exceeds initialized Rust storage",
        ));
    }
    Ok((dims, steps))
}

unsafe fn array<'py>(
    py: Python<'py>,
    dtype: Bound<'py, PyArrayDescr>,
    dims: &mut [isize],
    strides: &mut [isize],
    data: *mut u8,
    base: Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let result = Bound::<PyAny>::from_owned_ptr_or_err(
        py,
        PY_ARRAY_API.PyArray_NewFromDescr(
            py,
            PY_ARRAY_API.get_type_object(py, npyffi::NpyTypes::PyArray_Type),
            dtype.into_dtype_ptr(),
            dims.len() as i32,
            dims.as_mut_ptr(),
            strides.as_mut_ptr(),
            data.cast(),
            npyffi::NPY_ARRAY_WRITEABLE,
            ptr::null_mut(),
        ),
    )?;
    // NumPy steals base on both success and failure.
    if PY_ARRAY_API.PyArray_SetBaseObject(py, result.as_ptr().cast(), base.into_ptr()) < 0 {
        return Err(PyErr::fetch(py));
    }
    // Existing writable aliases remain writable even when their root is readonly.
    (*result.cast::<PyUntypedArray>()?.as_array_ptr()).flags |= npyffi::NPY_ARRAY_WRITEABLE;
    Ok(result)
}

#[pyfunction]
fn _graybench_rust_storage_view<'py>(
    root: &Bound<'py, PyAny>,
    dtype: &Bound<'py, PyArrayDescr>,
    shape: &Bound<'py, PyAny>,
    strides: &Bound<'py, PyAny>,
    offset: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    exact::<PyUntypedArray>(root)?;
    // Plain numeric dtypes only, excluding long double, object, structured and
    // subarray types. No Python references may be interpreted from numeric bytes.
    if !matches!(dtype.num(), 0..=12 | 14 | 15 | 23) || dtype.has_object() {
        return Err(PyTypeError::new_err(
            "Plain numeric native view dtype required",
        ));
    }
    let raw = unsafe { &*root.cast::<PyUntypedArray>()?.as_array_ptr() };
    if raw.base.is_null() {
        return Err(PyTypeError::new_err("Registered Rust root required"));
    }
    let owner = unsafe { Bound::from_borrowed_ptr(root.py(), raw.base) };
    let storage = checked(&owner)?;
    let registered = live_root(root.py(), storage)?;
    if registered.as_ref().is_none_or(|value| !value.is(root)) {
        return Err(PyValueError::new_err(
            "Original registered Rust root required",
        ));
    }
    let offset = integer(offset)?;
    let (mut dims, mut steps) = geometry(
        shape,
        strides,
        offset,
        dtype.itemsize(),
        storage.graybench.initialized,
    )?;
    unsafe {
        array(
            root.py(),
            dtype.clone(),
            &mut dims,
            &mut steps,
            storage.ptr.add(offset as usize),
            root.clone(),
        )
    }
}

fn allocate<'py, T: Element + Default>(
    py: Python<'py>,
    kind: &str,
    len: usize,
    cap: usize,
) -> PyResult<Bound<'py, PySliceContainer>> {
    let owner = match kind {
        "vec" => {
            let mut values = Vec::<T>::with_capacity(cap);
            if values.capacity() != cap {
                return Err(PyValueError::new_err(
                    "Allocator changed requested capacity",
                ));
            }
            values.resize_with(len, T::default);
            PySliceContainer::from(values)
        }
        "box" => {
            let values: Vec<T> = (0..len).map(|_| T::default()).collect();
            PySliceContainer::from(values.into_boxed_slice())
        }
        _ => return Err(PyValueError::new_err("Unknown Rust allocation kind")),
    };
    Bound::new(py, owner)
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn _graybench_rust_storage_new<'py>(
    py: Python<'py>,
    code: &Bound<'py, PyAny>,
    kind: &Bound<'py, PyAny>,
    initialized: &Bound<'py, PyAny>,
    allocated: &Bound<'py, PyAny>,
    shape: &Bound<'py, PyAny>,
    strides: &Bound<'py, PyAny>,
    offset: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let code = text(code)?;
    let kind = text(kind)?;
    let size = match code {
        "f" => 4,
        "d" | "F" => 8,
        "D" => 16,
        _ => {
            return Err(PyTypeError::new_err(
                "Supported Rust numeric dtype required",
            ))
        }
    };
    let len = integer(initialized)?;
    let cap = integer(allocated)?;
    if !matches!(kind, "vec" | "box")
        || len < 0
        || cap < len
        || cap as usize > LIMIT
        || len % size != 0
        || cap % size != 0
        || (kind == "box" && cap != len)
    {
        return Err(PyValueError::new_err("Invalid Rust allocation extent"));
    }
    let offset = integer(offset)?;
    let (mut dims, mut steps) = geometry(shape, strides, offset, size as usize, len as usize)?;
    // All untrusted geometry and extent checks precede allocation.
    let len = (len / size) as usize;
    let cap = (cap / size) as usize;
    let (owner, dtype) = match code {
        "f" => (
            allocate::<f32>(py, kind, len, cap)?,
            crate::dtype::<f32>(py),
        ),
        "d" => (
            allocate::<f64>(py, kind, len, cap)?,
            crate::dtype::<f64>(py),
        ),
        "F" => (
            allocate::<crate::Complex32>(py, kind, len, cap)?,
            crate::dtype::<crate::Complex32>(py),
        ),
        "D" => (
            allocate::<crate::Complex64>(py, kind, len, cap)?,
            crate::dtype::<crate::Complex64>(py),
        ),
        _ => unreachable!(),
    };
    let data = unsafe { owner.get().ptr.add(offset as usize) };
    let result = unsafe {
        array(
            py,
            dtype,
            &mut dims,
            &mut steps,
            data,
            owner.clone().into_any(),
        )?
    };
    register(&owner, &result)?;
    Ok(result)
}

pub fn register_module(module: &Bound<'_, PyModule>) -> PyResult<()> {
    let version = module.py().version_info();
    if version.major != 3 || version.minor != 12 {
        return Err(PyTypeError::new_err(
            "Experimental GrayBench Rust storage requires CPython 3.12",
        ));
    }
    module.add("_graybench_rust_storage_profile", "rust-numpy-storage-v1")?;
    module.add(
        "_graybench_rust_storage_owner_type",
        module.py().get_type::<PySliceContainer>(),
    )?;
    module.add_function(wrap_pyfunction!(
        _graybench_rust_storage_descriptor,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(_graybench_rust_storage_read, module)?)?;
    module.add_function(wrap_pyfunction!(_graybench_rust_storage_write, module)?)?;
    module.add_function(wrap_pyfunction!(_graybench_rust_storage_new, module)?)?;
    module.add_function(wrap_pyfunction!(_graybench_rust_storage_view, module)?)?;
    Ok(())
}
