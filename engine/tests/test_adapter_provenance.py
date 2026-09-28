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


@pytest.fixture
def registered_plugin(monkeypatch, tmp_path):
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
    try:
        yield provider, data
    finally:
        sys.modules.pop("graybench_fixture_plugin", None)


def test_registered_plugin_package_edit_changes_digest(registered_plugin, tmp_path):
    from graybench.adapter_provenance import adapter_code_digest, adapter_code_manifest

    provider, data = registered_plugin
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


def test_prepared_request_binds_adapter_code_and_preserves_historical_digest(model, task):
    from graybench.adapter_provenance import adapter_code_digest
    from graybench.contracts import PreparedRequest
    from graybench.identity import canonical

    request = Ollama().prepare(model, task, None)
    assert request.adapter_code_digest == adapter_code_digest(Ollama())
    historical = request.model_dump(mode="json")
    del historical["adapter_code_digest"]
    restored = PreparedRequest.model_validate_json(canonical(historical))
    assert restored.model_dump(mode="json") == historical
    assert restored.digest == identity(historical)
    assert restored.digest != request.digest


def test_changed_plugin_source_stops_generation_before_network(registered_plugin, task):
    import httpx

    from graybench.contracts import ModelSpec
    from graybench.transport import Transport

    provider, data = registered_plugin
    model = ModelSpec(adapter=provider.name, model="test-model", base_url="http://localhost:11434")
    request = provider.prepare(model, task, None)
    data.write_text('{"mode":"changed"}', encoding="utf-8")
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(503, json={"error": "unavailable"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="(?i)adapter.*code"):
            Transport(model, client).generate(request, provider)
    assert calls == []


def test_changed_plugin_source_stops_discovery_before_network(registered_plugin):
    import httpx

    from graybench.adapter_provenance import adapter_code_digest
    from graybench.contracts import ModelSpec
    from graybench.transport import Transport

    provider, data = registered_plugin
    model = ModelSpec(adapter=provider.name, model="test-model", base_url="http://localhost:11434")
    planned = adapter_code_digest(provider)
    data.write_text('{"mode":"changed"}', encoding="utf-8")
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(503, json={"error": "unavailable"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="(?i)adapter.*code"):
            Transport(model, client).discover(provider, expected_adapter_code_digest=planned)
    assert calls == []


def test_plugin_source_edit_during_auth_stops_before_network(registered_plugin, task):
    import httpx

    from graybench.contracts import ModelSpec
    from graybench.transport import Transport

    provider, data = registered_plugin
    model = ModelSpec(adapter=provider.name, model="test-model", base_url="http://localhost:11434")
    request = provider.prepare(model, task, None)

    def changing_auth(secret):
        data.write_text('{"mode":"during-auth"}', encoding="utf-8")
        return {}

    provider.auth_headers = changing_auth
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(503, json={"error": "unavailable"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="Adapter code changed"):
            Transport(model, client).generate(request, provider)
    assert calls == []


def test_discovery_records_observed_adapter_digest(model):
    import httpx

    from graybench.adapter_provenance import adapter_code_digest
    from graybench.transport import Transport

    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(503, json={"error": "no"}))
    ) as client:
        observations = Transport(model, client).discover(Ollama())
    assert observations
    assert all(
        item.evidence["adapter_code_digest"] == adapter_code_digest(Ollama())
        for item in observations
    )


def test_no_endpoint_discovery_still_records_adapter_digest(model):
    import httpx

    from graybench.adapter_provenance import adapter_code_digest
    from graybench.transport import Transport

    class NoDiscovery(Ollama):
        def discovery_requests(self, spec):
            return ()

    provider = NoDiscovery()
    with httpx.Client(transport=httpx.MockTransport(lambda req: AssertionError(req))) as client:
        observations = Transport(model, client).discover(provider)
    assert len(observations) == 1
    assert observations[0].evidence["adapter_code_digest"] == adapter_code_digest(provider)


def test_protocol_rejects_malformed_or_absolute_path_adapter_manifest(protocol):
    from graybench.contracts import Protocol
    from graybench.identity import canonical

    historical = protocol.model_dump(mode="json")
    assert "adapter_code_manifest" not in historical
    assert Protocol.model_validate_json(canonical(historical)).digest == protocol.digest
    invalid = {
        "schema": "adapter-code-v1",
        "adapter": "fixture",
        "class": "fixture.Adapter",
        "coverage": "module_only_development",
        "files": {"C:/Users/private/plugin.py": "a" * 64},
    }
    with pytest.raises(ValueError, match="adapter code file"):
        Protocol.model_validate_json(canonical({**historical, "adapter_code_manifest": invalid}))
