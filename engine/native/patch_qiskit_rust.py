"""Hash-bound experimental allocation instrumentation; run on fresh source copies."""

import hashlib
import json
import sys
from pathlib import Path

QISKIT_HASHES = {
    "Cargo.toml": "88e89b78915ff253cac600ca67f5b62b171e39a5047d7054827ce59b0dd6d08f",
    "Cargo.lock": "02460712f52341f3b9e45522fbbf3a0d30407234d146b00843a39ef4f6dd4d6f",
    "crates/pyext/Cargo.toml": "996c72ed40ce2a1cd379df98b3e7f99c4eb5c937bb743a29383141bc0c8a5db5",
    "crates/pyext/src/lib.rs": "e6359f459d1dd1a26b04bd5e13bc31a7a6abbbc3e46271acbce57905ee4110de",
}
NUMPY_HASHES = {
    "src/slice_container.rs": "c97ae5a37b53ca5177f12141c7526a20644c13e0751aab70da34a1eb3b21963a",
    "src/array.rs": "d456fae84c380497218fb87c9c63263936c6a1c9c2c7feed90d3ae1229cada30",
    "src/lib.rs": "b23036673ab97fcdcd95b5a95dc982a3b55d3845a778ff3edcd426986d325eea",
}


def replace(source, old, new, count=1):
    if source.count(old) != count:
        raise ValueError("Pinned source patch anchor mismatch")
    return source.replace(old, new)


def patch(qiskit, numpy):
    qiskit, numpy = qiskit.resolve(), numpy.resolve()
    if qiskit.name != "qiskit-2.4.2" or numpy.name != "numpy-0.28.0":
        raise ValueError("Pinned directory names required")
    if qiskit == numpy or qiskit in numpy.parents or numpy in qiskit.parents:
        raise ValueError("Separate fresh Qiskit and NumPy source directories required")
    sources = {}
    for root, hashes in ((qiskit, QISKIT_HASHES), (numpy, NUMPY_HASHES)):
        for name, expected in hashes.items():
            path = root / name
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError(f"Unmodified pinned source required: {name}")
            sources[path] = raw.decode("utf-8")
    extra = numpy / "src/graybench_storage.rs"
    manifest = qiskit / "graybench-rust-storage-patch.json"
    if extra.exists() or manifest.exists():
        raise ValueError("Experimental patch destination already exists")

    path = numpy / "src/slice_container.rs"
    source = replace(
        sources[path],
        "    drop: unsafe fn(*mut u8, usize, usize),",
        "    drop: unsafe fn(*mut u8, usize, usize),\n"
        "    pub(crate) graybench: crate::graybench_storage::Storage,",
    )
    source = replace(
        source,
        "            drop,\n        }",
        "            drop,\n"
        '            graybench: crate::graybench_storage::Storage::of::<T>(len, len, "box"),\n'
        "        }",
        count=2,
    )
    # The first constructor is Box; the second is Vec and preserves spare capacity.
    anchor = 'Storage::of::<T>(len, len, "box")'
    first = source.index(anchor)
    second = source.index(anchor, first + len(anchor))
    source = source[:second] + source[second:].replace(
        anchor, 'Storage::of::<T>(len, cap, "vec")', 1
    )
    sources[path] = "// Altered by GrayBench: immutable allocation provenance.\n" + source

    path = numpy / "src/array.rs"
    old = """        let container = Bound::new(py, container)
            .expect("Failed to create slice container")
            .into_ptr();

        Self::new_with_data(py, dims, strides, data_ptr, container.cast())"""
    new = """        let container = Bound::new(py, container)
            .expect("Failed to create slice container");
        let result = Self::new_with_data(py, dims, strides, data_ptr,
            container.clone().into_ptr().cast());
        crate::graybench_storage::register(&container, result.as_any())
            .expect("Failed to register Rust allocation origin");
        result"""
    sources[path] = "// Altered by GrayBench: root registration before exposure.\n" + replace(
        sources[path], old, new
    )
    path = numpy / "src/lib.rs"
    sources[path] = "// Altered by GrayBench: private storage instrumentation module.\n" + replace(
        sources[path],
        "mod slice_container;",
        "mod slice_container;\n#[doc(hidden)]\npub mod graybench_storage;",
    )
    path = qiskit / "crates/pyext/Cargo.toml"
    sources[path] = "# Altered by GrayBench: fixed native storage helper dependency.\n" + replace(
        sources[path], "[dependencies]\n", "[dependencies]\nnumpy.workspace = true\n"
    )
    path = qiskit / "crates/pyext/src/lib.rs"
    sources[path] = "// Altered by GrayBench: fixed native storage helpers.\n" + replace(
        sources[path],
        "fn _accelerate(m: &Bound<PyModule>) -> PyResult<()> {",
        "fn _accelerate(m: &Bound<PyModule>) -> PyResult<()> {\n"
        "    numpy::graybench_storage::register_module(m)?;",
    )
    path = qiskit / "Cargo.toml"
    # A fixed relative path, so patch source identity does not contain host paths.
    if numpy.parent != qiskit.parent:
        raise ValueError("Fresh source directories must be siblings")
    sources[path] += (
        "\n# Altered by GrayBench: hash-verified Rust NumPy source.\n[patch.crates-io]\n"
        'numpy = { path = "../numpy-0.28.0" }\n'
    )
    module = Path(__file__).with_name("rust_storage.rs").read_bytes()
    # All hashes, destinations and textual replacements checked before writes.
    for path, source in sources.items():
        if path.name != "Cargo.lock":
            path.write_text(source, encoding="utf-8", newline="\n")
    extra.write_bytes(module)
    records = {
        "profile": "rust-numpy-storage-v1",
        "patch_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "original_qiskit": QISKIT_HASHES,
        "original_rust_numpy": NUMPY_HASHES,
        "patched_qiskit": {
            name: hashlib.sha256((qiskit / name).read_bytes()).hexdigest() for name in QISKIT_HASHES
        },
        "patched_rust_numpy": {
            name: hashlib.sha256((numpy / name).read_bytes()).hexdigest()
            for name in [*NUMPY_HASHES, "src/graybench_storage.rs"]
        },
    }
    manifest.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print("Applied experimental Rust allocation instrumentation; runtime not qualified")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: patch_qiskit_rust.py QISKIT_SOURCE NUMPY_SOURCE")
    patch(Path(sys.argv[1]), Path(sys.argv[2]))
