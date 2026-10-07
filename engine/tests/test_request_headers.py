import pytest

from graybench.contracts import PreparedRequest
from graybench.identity import canonical, identity
from graybench.providers import Ollama


def test_builtin_request_freezes_application_headers(model, task):
    request = Ollama().prepare(model, task, None)
    assert request.public_headers == {
        "accept": "application/json",
        "accept-encoding": "identity",
        "content-type": "application/json",
        "user-agent": "python-httpx",
    }
    assert request.credential_header_names == ()


def test_adapter_public_header_changes_prepared_request_identity(model, task):
    class ProfiledOllama(Ollama):
        def __init__(self, profile):
            self.profile = profile

        def public_headers(self, spec):
            return {"X-Model-Profile": self.profile}

    first = ProfiledOllama("stable").prepare(model, task, None)
    second = ProfiledOllama("experimental").prepare(model, task, None)
    assert first.public_headers["x-model-profile"] == "stable"
    assert second.public_headers["x-model-profile"] == "experimental"
    assert first.digest != second.digest


def test_credential_field_name_changes_prepared_request_identity(task):
    from graybench.contracts import ModelSpec

    credentialed = ModelSpec(
        adapter="ollama",
        model="test-model",
        base_url="http://localhost:11434",
        credential_env="TEST_TOKEN",
    )

    class KeyOllama(Ollama):
        credential_header_names = frozenset({"x-api-key"})

    first = Ollama().prepare(credentialed, task, None)
    second = KeyOllama().prepare(credentialed, task, None)
    assert first.credential_header_names == ("authorization",)
    assert second.credential_header_names == ("x-api-key",)
    assert first.digest != second.digest


def test_credential_presence_changes_prepared_request_identity(model, task):
    from graybench.contracts import ModelSpec

    credentialed = ModelSpec(
        adapter="ollama",
        model="test-model",
        base_url="http://localhost:11434",
        credential_env="TEST_TOKEN",
    )
    assert (
        Ollama().prepare(model, task, None).digest
        != Ollama().prepare(credentialed, task, None).digest
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"Accept": "text/plain"},
        {"X-Profile": "one", "x-profile": "two"},
        {"Authorization": "Bearer leaked"},
        {"X-Api-Key": "leaked"},
        {"Host": "wrong.example"},
        {"Content-Length": "0"},
        {"X-Profile": "one\r\ntwo"},
    ],
)
def test_public_headers_reject_overrides_credentials_and_invalid_values(extra):
    from graybench.request_headers import freeze_public_headers

    with pytest.raises(ValueError):
        freeze_public_headers(extra)


def test_public_headers_normalize_case_and_order():
    from graybench.request_headers import freeze_public_headers

    assert freeze_public_headers({"X-Zeta": "z", "x-Alpha": "a"}) == {
        "accept": "application/json",
        "accept-encoding": "identity",
        "content-type": "application/json",
        "user-agent": "python-httpx",
        "x-alpha": "a",
        "x-zeta": "z",
    }


def test_legacy_prepared_request_round_trips_without_changing_identity():
    historical = {
        "adapter": "ollama",
        "model": "test-model",
        "path": "/api/chat",
        "body": {"model": "test-model"},
        "setting_evidence": [],
    }
    request = PreparedRequest.model_validate_json(canonical(historical))
    assert request.model_dump(mode="json") == historical
    assert request.digest == identity(historical)


def test_invalid_frozen_public_headers_cannot_enter_request_artifact():
    historical = {
        "adapter": "ollama",
        "model": "test-model",
        "path": "/api/chat",
        "body": {"model": "test-model"},
        "setting_evidence": [],
        "public_headers": {"accept": "text/plain"},
    }
    with pytest.raises(ValueError, match="public_headers"):
        PreparedRequest.model_validate_json(canonical(historical))


def test_adapter_does_not_persist_a_credential_as_a_public_header(monkeypatch, task):
    monkeypatch.setenv("TEST_TOKEN", "fixture-only-secret")
    from graybench.contracts import ModelSpec

    model = ModelSpec(
        adapter="ollama",
        model="test-model",
        base_url="http://localhost:11434",
        credential_env="TEST_TOKEN",
    )

    class LeakingOllama(Ollama):
        def public_headers(self, spec):
            return {"X-Profile": "prefix-fixture-only-secret-suffix"}

    with pytest.raises(ValueError, match="(?i)credential"):
        LeakingOllama().prepare(model, task, None)


@pytest.mark.parametrize(
    ("header_name", "header_value"),
    [
        ("x-model-profile", "experimental"),
        ("authorization", "Bearer fixture-only-secret:experimental"),
        ("x-goog-api-key", "fixture-only-secret:experimental"),
    ],
)
def test_credential_fields_cannot_hide_model_settings(monkeypatch, task, header_name, header_value):
    import httpx

    from graybench.contracts import ModelSpec
    from graybench.transport import Transport

    monkeypatch.setenv("TEST_TOKEN", "fixture-only-secret")
    model = ModelSpec(
        adapter="ollama",
        model="test-model",
        base_url="http://localhost:11434",
        credential_env="TEST_TOKEN",
    )

    class MisdeclaredOllama(Ollama):
        credential_header_names = frozenset({header_name})

        def auth_headers(self, secret):
            return {header_name: header_value}

    calls = []
    provider = MisdeclaredOllama()

    def handler(req):
        calls.append(req)
        return httpx.Response(503, json={"error": "unavailable"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="(?i)credential"):
            request = provider.prepare(model, task, None)
            Transport(model, client).generate(request, provider)
    assert calls == []


def test_changed_credential_field_declaration_stops_before_dispatch(monkeypatch, task):
    import httpx

    from graybench.contracts import ModelSpec
    from graybench.transport import Transport

    monkeypatch.setenv("TEST_TOKEN", "fixture-only-secret")
    model = ModelSpec(
        adapter="ollama",
        model="test-model",
        base_url="http://localhost:11434",
        credential_env="TEST_TOKEN",
    )

    class ChangingOllama(Ollama):
        def auth_headers(self, secret):
            return {next(iter(self.credential_header_names)): secret}

    provider = ChangingOllama()
    request = provider.prepare(model, task, None)
    provider.credential_header_names = frozenset({"x-api-key"})
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(503, json={"error": "unavailable"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="credential.*frozen"):
            Transport(model, client).generate(request, provider)
    assert calls == []


def test_auth_hook_cannot_change_credential_field_after_freeze(monkeypatch, task):
    import httpx

    from graybench.contracts import ModelSpec
    from graybench.transport import Transport

    monkeypatch.setenv("TEST_TOKEN", "fixture-only-secret")
    model = ModelSpec(
        adapter="ollama",
        model="test-model",
        base_url="http://localhost:11434",
        credential_env="TEST_TOKEN",
    )

    class MutatingOllama(Ollama):
        def auth_headers(self, secret):
            self.credential_header_names = frozenset({"x-api-key"})
            return {"x-api-key": secret}

    provider = MutatingOllama()
    request = provider.prepare(model, task, None)
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(503, json={"error": "unavailable"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="credential header"):
            Transport(model, client).generate(request, provider)
    assert calls == []


@pytest.mark.parametrize("mode", ["raw", "absent", "extra"])
def test_credentialed_request_requires_exact_bearer_field(monkeypatch, task, mode):
    import httpx

    from graybench.contracts import ModelSpec
    from graybench.transport import Transport

    monkeypatch.setenv("TEST_TOKEN", "fixture-only-secret")
    model = ModelSpec(
        adapter="ollama",
        model="test-model",
        base_url="http://localhost:11434",
        credential_env="TEST_TOKEN",
    )

    class VariableAuthOllama(Ollama):
        def auth_headers(self, secret):
            if mode == "raw":
                return {"authorization": secret}
            if mode == "absent":
                return {}
            return {"authorization": f"Bearer {secret}", "x-api-key": secret}

    provider = VariableAuthOllama()
    request = provider.prepare(model, task, None)
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(503, json={"error": "unavailable"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="(?i)credential"):
            Transport(model, client).generate(request, provider)
    assert calls == []


def test_credentialed_request_rejects_multiple_credential_fields(task):
    from graybench.contracts import ModelSpec

    model = ModelSpec(
        adapter="ollama",
        model="test-model",
        base_url="http://localhost:11434",
        credential_env="TEST_TOKEN",
    )

    class DoubleAuthOllama(Ollama):
        credential_header_names = frozenset({"authorization", "x-api-key"})

    with pytest.raises(ValueError, match="(?i)credential"):
        DoubleAuthOllama().prepare(model, task, None)


def test_auth_hook_cannot_mutate_sent_request_or_recorded_body(monkeypatch, task):
    import json

    import httpx

    from graybench.contracts import ModelSpec
    from graybench.transport import Transport

    monkeypatch.setenv("TEST_TOKEN", "fixture-only-secret")
    model = ModelSpec(
        adapter="ollama",
        model="test-model",
        base_url="http://localhost:11434",
        credential_env="TEST_TOKEN",
    )

    class MutatingOllama(Ollama):
        def public_headers(self, spec):
            return {"X-Model-Profile": "stable"}

        def auth_headers(self, secret):
            self.prepared.public_headers["x-model-profile"] = "experimental"
            self.prepared.body["model"] = "another-model"
            return {"authorization": f"Bearer {secret}"}

    seen = []

    def handler(req):
        seen.append((req.headers["x-model-profile"], json.loads(req.content)))
        return httpx.Response(
            200,
            json={
                "model": model.model,
                "done": True,
                "message": {"role": "assistant", "content": "return 1"},
            },
        )

    provider = MutatingOllama()
    provider.prepared = provider.prepare(model, task, None)
    planned_digest = provider.prepared.digest
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = Transport(model, client).generate(provider.prepared, provider)
    assert result.kind == "returned"
    assert seen[0][0] == "stable"
    assert seen[0][1]["model"] == model.model
    assert result.evidence["request_public_headers"]["x-model-profile"] == "stable"
    assert result.evidence["request_body"]["model"] == model.model
    assert provider.prepared.digest != planned_digest
