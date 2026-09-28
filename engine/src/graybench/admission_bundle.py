"""Recompute a committed local admission audit from its exact evidence bytes.

A matching bundle is reproducible local evidence, not proof of authorship or
independent certification. The Git commit provides a reviewable content anchor.
"""

import hashlib
import json
import re
import tempfile
from pathlib import Path

from graybench.identity import canonical
from graybench.task_admission import AdmissionInventory, audit_control_coverage

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_SCOPE = "local authored controls; not model scoring"
_MAX_TOTAL_REVIEW_BYTES = 256 * 1024**2


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate admission-bundle JSON key")
        result[key] = value
    return result


def _read_bounded(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Admission-bundle file exceeds byte limit")
    return raw


def _artifact(bundle: Path, descriptor: object, limit: int) -> tuple[Path, bytes]:
    if not isinstance(descriptor, dict) or set(descriptor) != {"file", "bytes", "sha256"}:
        raise ValueError("Invalid admission-bundle file descriptor")
    name, size, digest = (
        descriptor["file"],
        descriptor["bytes"],
        descriptor["sha256"],
    )
    if not isinstance(name, str) or _NAME.fullmatch(name) is None or ".." in name:
        raise ValueError("Invalid admission-bundle file name")
    if type(size) is not int or not 0 < size <= limit or not isinstance(digest, str):
        raise ValueError("Invalid admission-bundle file size or digest")
    if _HEX.fullmatch(digest) is None:
        raise ValueError("Invalid admission-bundle file digest")
    path = bundle / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked admission-bundle file")
    data = _read_bounded(path, limit)
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("Admission-bundle file size or digest mismatch")
    return path, data


def verify_admission_bundle(bundle: Path, cache: Path) -> dict:
    """Verify listed bytes and replay schema-5 controls against pinned QHE tasks."""
    manifest_path = bundle / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("Missing or linked admission-bundle manifest")
    manifest_bytes = _read_bounded(manifest_path, 64 * 1024)
    manifest = json.loads(manifest_bytes, object_pairs_hook=_unique_pairs)
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"schema_version", "scope", "inventory", "reviews", "audit"}
        or manifest["schema_version"] != "1"
        or manifest["scope"] != _SCOPE
        or type(manifest["reviews"]) is not list
        or not 1 <= len(manifest["reviews"]) <= 32
    ):
        raise ValueError("Invalid admission-bundle manifest")
    inventory_path, inventory_bytes = _artifact(bundle, manifest["inventory"], 8 * 1024**2)
    audit_path, audit_bytes = _artifact(bundle, manifest["audit"], 32 * 1024**2)
    inventory = AdmissionInventory.model_validate_json(inventory_bytes)
    # The audit API opens paths again. Replay private copies of the already
    # verified bytes so a changed source file cannot replace the checked log.
    with tempfile.TemporaryDirectory(prefix="graybench-admission-bundle-") as temporary:
        review_sources = []
        snapshot_paths = []
        total_review_bytes = 0
        for descriptor in manifest["reviews"]:
            original, data = _artifact(bundle, descriptor, 64 * 1024**2)
            total_review_bytes += len(data)
            if total_review_bytes > _MAX_TOTAL_REVIEW_BYTES:
                raise ValueError("Admission-bundle reviews exceed total byte limit")
            snapshot = Path(temporary) / original.name
            snapshot.write_bytes(data)
            snapshot_paths.append(snapshot)
            review_sources.append((original, descriptor))
            del data
        names = [inventory_path.name, *(path.name for path, _ in review_sources), audit_path.name]
        if len(set(names)) != len(names) or "manifest.json" in names:
            raise ValueError("Duplicate admission-bundle file name")
        recomputed = audit_control_coverage(inventory, cache, tuple(snapshot_paths))
    if recomputed["schema_version"] != "5" or canonical(recomputed) != audit_bytes:
        raise ValueError("Admission-bundle saved report differs from recomputed audit")
    if (
        _read_bounded(manifest_path, 64 * 1024) != manifest_bytes
        or _read_bounded(inventory_path, 8 * 1024**2) != inventory_bytes
        or _read_bounded(audit_path, 32 * 1024**2) != audit_bytes
    ):
        raise ValueError("Admission-bundle source changed during verification")
    for _, descriptor in review_sources:
        try:
            _artifact(bundle, descriptor, 64 * 1024**2)
        except (OSError, ValueError) as error:
            raise ValueError("Admission-bundle source changed during verification") from error
    return {
        "verified": True,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "audit_sha256": hashlib.sha256(audit_bytes).hexdigest(),
        "control_count": recomputed["control_count"],
        "covered_task_count": recomputed["covered_task_count"],
        "uncovered_task_count": recomputed["uncovered_task_count"],
        "declared_frozen_judge_control_count": recomputed["declared_frozen_judge_control_count"],
        "false_pass_count": recomputed["false_pass_count"],
        "false_rejection_count": recomputed["false_rejection_count"],
        "independent_review": False,
        "publication_eligible": False,
    }
