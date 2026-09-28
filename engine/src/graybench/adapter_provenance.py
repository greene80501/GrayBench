"""Local adapter-code change detection; hashes are not plugin attestations."""

import hashlib
import re
import sys
from importlib import import_module
from importlib.metadata import entry_points
from pathlib import Path

from graybench.identity import identity
from graybench.provenance import source_manifest

MAX_FILES = 4096
MAX_BYTES = 64 * 1024 * 1024
EXCLUDED_DIRS = frozenset({"__pycache__", ".git", ".pytest_cache", ".ruff_cache"})
HEX = re.compile(r"[0-9a-f]{64}\Z")


def validate_adapter_code_manifest(manifest: dict) -> dict:
    """Validate a serialized observation; matching current code is a separate check."""
    if not isinstance(manifest, dict):
        raise ValueError("Adapter code manifest must be an object")
    common = {"schema", "adapter", "class", "coverage"}
    if not common <= set(manifest) or manifest["schema"] != "adapter-code-v1":
        raise ValueError("Invalid adapter code manifest schema")
    if any(
        type(manifest[key]) is not str or not manifest[key].strip()
        for key in ("adapter", "class", "coverage")
    ):
        raise ValueError("Invalid adapter code manifest identity")
    coverage = manifest["coverage"]
    if coverage == "engine_source":
        if (
            set(manifest) != common | {"engine_source_digest"}
            or not isinstance(manifest["engine_source_digest"], str)
            or not HEX.fullmatch(manifest["engine_source_digest"])
        ):
            raise ValueError("Invalid built-in adapter code manifest")
        return manifest
    if coverage not in {
        "registered_package_tree",
        "registered_module_file",
        "module_only_development",
    }:
        raise ValueError("Unsupported adapter code coverage")
    expected = common | {"files"}
    if coverage != "module_only_development":
        expected |= {"entry_point"}
    if set(manifest) != expected:
        raise ValueError("Invalid adapter code manifest fields")
    files = manifest["files"]
    if type(files) is not dict or not 1 <= len(files) <= MAX_FILES:
        raise ValueError("Invalid adapter code file inventory")
    for name, digest in files.items():
        if (
            type(name) is not str
            or not 0 < len(name) <= 512
            or "\\" in name
            or ":" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))
            or type(digest) is not str
            or not HEX.fullmatch(digest)
        ):
            raise ValueError("Invalid adapter code file identity")
    if "entry_point" in manifest:
        entry = manifest["entry_point"]
        if (
            type(entry) is not dict
            or set(entry)
            != {
                "name",
                "value",
                "distribution",
                "version",
            }
            or any(type(value) is not str or not value.strip() for value in entry.values())
        ):
            raise ValueError("Invalid adapter entry-point identity")
    return manifest


def _source_file(provider) -> Path:
    module = sys.modules.get(type(provider).__module__)
    location = getattr(module, "__file__", None)
    if not location:
        raise ValueError("Adapter source file is unavailable")
    source = Path(location)
    if source.is_symlink() or not source.is_file():
        raise ValueError("Adapter source file is missing or symlinked")
    return source


def _file_digest(path: Path, *, remaining: int) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Adapter source contains a symlink or non-file")
    size = path.stat().st_size
    if size > remaining:
        raise ValueError("Adapter source package exceeds byte limit")
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ValueError("Adapter source file is unreadable") from error
    if len(data) != size:
        raise ValueError("Adapter source file changed during hashing")
    return hashlib.sha256(data).hexdigest(), size


def _package_files(root: Path, defining_source: Path) -> dict[str, str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Adapter package root is unstable")
    try:
        defining_source.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise ValueError("Adapter class source is outside its package") from error
    result = {}
    total = 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if EXCLUDED_DIRS.intersection(relative.parts) or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError("Adapter source package contains a symlink")
        if path.is_dir():
            continue
        if len(result) >= MAX_FILES:
            raise ValueError("Adapter source package exceeds file limit")
        digest, size = _file_digest(path, remaining=MAX_BYTES - total)
        result[relative.as_posix()] = digest
        total += size
    if not result:
        raise ValueError("Adapter source package has no files")
    return result


def _registered_entry(provider):
    matches = list(entry_points(group="graybench.adapters", name=provider.name))
    if len(matches) > 1:
        raise ValueError("Adapter has ambiguous registered entry points")
    if matches and matches[0].load() is type(provider):
        return matches[0]
    return None


def adapter_code_manifest(provider) -> dict:
    """Hash observed local adapter code without exposing absolute paths or bytes."""
    from graybench.providers import BUILTINS

    cls = type(provider)
    base = {
        "schema": "adapter-code-v1",
        "adapter": provider.name,
        "class": f"{cls.__module__}.{cls.__qualname__}",
    }
    if cls is BUILTINS.get(provider.name):
        return {
            **base,
            "coverage": "engine_source",
            "engine_source_digest": source_manifest()["digest"],
        }
    source = _source_file(provider)
    entry = _registered_entry(provider)
    if entry is None:
        digest, _ = _file_digest(source, remaining=MAX_BYTES)
        return {
            **base,
            "coverage": "module_only_development",
            "files": {source.name: digest},
        }
    top_level = import_module(cls.__module__.split(".", 1)[0])
    roots = tuple(getattr(top_level, "__path__", ()))
    if roots:
        if len(roots) != 1:
            raise ValueError("Adapter namespace package has ambiguous roots")
        files = _package_files(Path(roots[0]), source)
        coverage = "registered_package_tree"
    else:
        digest, _ = _file_digest(source, remaining=MAX_BYTES)
        files = {source.name: digest}
        coverage = "registered_module_file"
    return {
        **base,
        "coverage": coverage,
        "entry_point": {
            "name": entry.name,
            "value": entry.value,
            "distribution": entry.dist.metadata["Name"],
            "version": entry.dist.version,
        },
        "files": files,
    }


def adapter_code_digest(provider) -> str:
    return identity(adapter_code_manifest(provider))
