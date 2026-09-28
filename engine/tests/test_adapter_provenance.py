import importlib
import sys
from pathlib import Path

import pytest

from graybench.identity import identity
from graybench.provenance import source_manifest
from graybench.providers import Ollama


def test_builtin_adapter_uses_engine_source_identity():
    from graybench.adapter_provenance import adapter_code_digest, adapter_code_manifest

    manifest = adapter_code_manifest(Ollama())
    assert manifest == {
        "schema": "adapter-code-v1",
        "adapter": "ollama",
        "class": "graybench.providers.Ollama",
        "coverage": "engine_source",
        "engine_source_digest": source_manifest()["digest"],
    }
    assert adapter_code_digest(Ollama()) == identity(manifest)


def test_direct_subclass_is_module_only_development():
    from graybench.adapter_provenance import adapter_code_manifest

    class CustomOllama(Ollama):
        pass

    manifest = adapter_code_manifest(CustomOllama())
    assert manifest["coverage"] == "module_only_development"
    assert set(manifest["files"]) == {"test_adapter_provenance.py"}
    assert all(len(digest) == 64 for digest in manifest["files"].values())
    assert "C:\\" not in str(manifest)


def test_registered_plugin_package_edit_changes_digest(monkeypatch, tmp_path):
    from graybench.adapter_provenance import adapter_code_digest, adapter_code_manifest

    package = tmp_path / "graybench_fixture_plugin"
    package.mkdir()
    (package / "__init__.py").write_text(
        "from graybench.providers import Ollama\n"
        "class FixtureAdapter(Ollama):\n"
        "    name = 'fixture-plugin'\n",
        encoding="utf-8",
    )
    data = package / "policy.json"
    data.write_text('{"mode":"one"}', encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    module = importlib.import_module("graybench_fixture_plugin")
    provider = module.FixtureAdapter()

    class FakeDistribution:
        metadata = {"Name": "fixture-distribution"}
        version = "1.2.3"

    class FakeEntryPoint:
        name = "fixture-plugin"
        value = "graybench_fixture_plugin:FixtureAdapter"
        dist = FakeDistribution()

        def load(self):
            return module.FixtureAdapter

    monkeypatch.setattr(
        "graybench.adapter_provenance.entry_points", lambda **kwargs: [FakeEntryPoint()]
    )
    first = adapter_code_manifest(provider)
    first_digest = adapter_code_digest(provider)
    data.write_text('{"mode":"two"}', encoding="utf-8")
    second = adapter_code_manifest(provider)
    assert first["coverage"] == "registered_package_tree"
    assert first["entry_point"] == {
        "name": "fixture-plugin",
        "value": "graybench_fixture_plugin:FixtureAdapter",
        "distribution": "fixture-distribution",
        "version": "1.2.3",
    }
    assert first["files"]["policy.json"] != second["files"]["policy.json"]
    assert first_digest != adapter_code_digest(provider)
    assert str(tmp_path) not in str(first)
    assert str(tmp_path) not in str(second)
    sys.modules.pop("graybench_fixture_plugin", None)


def test_unstable_plugin_source_is_rejected(monkeypatch, tmp_path):
    from graybench.adapter_provenance import adapter_code_manifest

    class CustomOllama(Ollama):
        pass

    module = sys.modules[CustomOllama.__module__]
    monkeypatch.setattr(module, "__file__", str(tmp_path / "missing.py"))
    with pytest.raises(ValueError, match="source"):
        adapter_code_manifest(CustomOllama())


def test_registered_package_rejects_symlink(monkeypatch, tmp_path):
    from graybench.adapter_provenance import _package_files

    package = tmp_path / "package"
    package.mkdir()
    source = package / "__init__.py"
    source.write_text("pass", encoding="utf-8")
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    link = package / "linked.json"
    try:
        link.symlink_to(outside)
    except OSError:
        link.write_text("{}", encoding="utf-8")
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda path: path == link or original(path))
    with pytest.raises(ValueError, match="symlink"):
        _package_files(package, source)


def test_registered_package_rejects_oversize_source(monkeypatch, tmp_path):
    import graybench.adapter_provenance as provenance

    package = tmp_path / "package"
    package.mkdir()
    source = package / "__init__.py"
    source.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(provenance, "MAX_BYTES", 4)
    with pytest.raises(ValueError, match="byte limit"):
        provenance._package_files(package, source)


def test_registered_package_rejects_too_many_files(monkeypatch, tmp_path):
    import graybench.adapter_provenance as provenance

    package = tmp_path / "package"
    package.mkdir()
    source = package / "__init__.py"
    source.write_text("pass", encoding="utf-8")
    (package / "policy.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(provenance, "MAX_FILES", 1)
    with pytest.raises(ValueError, match="file limit"):
        provenance._package_files(package, source)
