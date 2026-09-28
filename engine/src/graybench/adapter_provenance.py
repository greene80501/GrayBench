"""Local adapter-code change detection; hashes are not plugin attestations."""

import hashlib
import sys
from importlib import import_module
from importlib.metadata import entry_points
from pathlib import Path

from graybench.identity import identity
from graybench.provenance import source_manifest

MAX_FILES = 4096
MAX_BYTES = 64 * 1024 * 1024
EXCLUDED_DIRS = frozenset({"__pycache__", ".git", ".pytest_cache", ".ruff_cache"})


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
