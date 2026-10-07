"""Hash/preflight controls using already downloaded, pinned source files.

These verify the patch process only; they never compile or load native code.
"""

import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

NATIVE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("qiskit_rust_patch", NATIVE / "patch_qiskit_rust.py")
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


@pytest.fixture
def sources(tmp_path):
    default = NATIVE.parents[3] / "outputs/qiskit-rust-storage-sources"
    cache = Path(os.environ.get("GRAYBENCH_RUST_SOURCE_CACHE", default))
    qiskit, numpy = tmp_path / "qiskit-2.4.2", tmp_path / "numpy-0.28.0"
    for root, name, hashes in (
        (qiskit, "qiskit-2.4.2", PATCH.QISKIT_HASHES),
        (numpy, "numpy-0.28.0", PATCH.NUMPY_HASHES),
    ):
        for relative, expected in hashes.items():
            source = cache / name / relative
            assert source.is_file(), "Supply verified source cache; this test never downloads"
            assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    return qiskit, numpy


def snapshot(*roots):
    return {
        str(path): path.read_bytes() for root in roots for path in root.rglob("*") if path.is_file()
    }


def test_verified_patch_retains_lock_destructors_and_records_exact_changes(sources):
    qiskit, numpy = sources
    old = (numpy / "src/slice_container.rs").read_text()
    lock = (qiskit / "Cargo.lock").read_bytes()
    PATCH.patch(qiskit, numpy)
    assert (qiskit / "Cargo.lock").read_bytes() == lock
    assert (numpy / "src/slice_container.rs").read_text().split("impl Drop", 1)[1] == old.split(
        "impl Drop", 1
    )[1]
    assert (numpy / "src/graybench_storage.rs").read_bytes() == (
        NATIVE / "rust_storage.rs"
    ).read_bytes()
    manifest = json.loads((qiskit / "graybench-rust-storage-patch.json").read_text())
    for root, group in ((qiskit, "patched_qiskit"), (numpy, "patched_rust_numpy")):
        for relative, digest in manifest[group].items():
            assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest
    owner = (numpy / "src/slice_container.rs").read_text()
    assert 'Storage::of::<T>(len, len, "box")' in owner
    assert 'Storage::of::<T>(len, cap, "vec")' in owner
    assert "container.clone().into_ptr().cast()" in (numpy / "src/array.rs").read_text()
    assert (
        "numpy::graybench_storage::register_module(m)?;"
        in (qiskit / "crates/pyext/src/lib.rs").read_text()
    )


@pytest.mark.parametrize("group", ["qiskit", "numpy"])
def test_any_changed_input_rejected_before_writes(sources, group):
    qiskit, numpy = sources
    root = qiskit if group == "qiskit" else numpy
    hashes = PATCH.QISKIT_HASHES if group == "qiskit" else PATCH.NUMPY_HASHES
    for relative in hashes:
        path = root / relative
        original = path.read_bytes()
        path.write_bytes(original + b"\nchanged\n")
        before = snapshot(qiskit, numpy)
        with pytest.raises(ValueError, match="Unmodified pinned source"):
            PATCH.patch(qiskit, numpy)
        assert snapshot(qiskit, numpy) == before
        path.write_bytes(original)


@pytest.mark.parametrize("destination", ["module", "manifest"])
def test_existing_destination_rejected_without_overwrite(sources, destination):
    qiskit, numpy = sources
    path = (
        numpy / "src/graybench_storage.rs"
        if destination == "module"
        else qiskit / "graybench-rust-storage-patch.json"
    )
    path.write_text("retain me")
    before = snapshot(qiskit, numpy)
    with pytest.raises(ValueError, match="destination already exists"):
        PATCH.patch(qiskit, numpy)
    assert snapshot(qiskit, numpy) == before


def test_reapplication_rejected_without_second_change(sources):
    qiskit, numpy = sources
    PATCH.patch(qiskit, numpy)
    before = snapshot(qiskit, numpy)
    with pytest.raises(ValueError, match="Unmodified pinned source"):
        PATCH.patch(qiskit, numpy)
    assert snapshot(qiskit, numpy) == before


def test_non_sibling_sources_rejected_before_writes(sources, tmp_path):
    qiskit, numpy = sources
    other = tmp_path / "separate/numpy-0.28.0"
    shutil.copytree(numpy, other)
    before = snapshot(qiskit, other)
    with pytest.raises(ValueError, match="must be siblings"):
        PATCH.patch(qiskit, other)
    assert snapshot(qiskit, other) == before


def test_unexpected_directory_name_rejected_before_writes(sources, tmp_path):
    qiskit, numpy = sources
    other = tmp_path / "numpy-unreviewed"
    shutil.copytree(numpy, other)
    before = snapshot(qiskit, other)
    with pytest.raises(ValueError, match="Pinned directory names"):
        PATCH.patch(qiskit, other)
    assert snapshot(qiskit, other) == before
