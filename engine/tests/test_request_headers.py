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
