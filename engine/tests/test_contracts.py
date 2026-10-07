import pytest
from pydantic import ValidationError

from graybench.contracts import ModelSpec, Protocol, RetryPolicy
from graybench.identity import identity
from graybench.ledger import StateError
from graybench.providers import Ollama


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@example.com",
        "https://example.com?key=x",
        "http://remote.example.com",
        "file:///tmp/test",
    ],
)
def test_endpoints_cannot_embed_credentials_or_use_insecure_remote_transport(url):
    with pytest.raises(ValidationError):
        ModelSpec(adapter="ollama", model="test", base_url=url)


def test_first_dispatch_cannot_change_frozen_prompt(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    request = Ollama().prepare(protocol.model, task, "Extra help")
    with pytest.raises(StateError, match="frozen experiment"):
        ledger.begin_attempt(sample, request)


def test_cannot_claim_incomplete_request_schedule(protocol):
    data = protocol.model_dump(mode="json")
    data["request_digests"] = {}
    import json

    with pytest.raises(ValidationError, match="every task"):
        Protocol.model_validate_json(json.dumps(data))


def test_no_auth_retry_or_ambiguous_replay():
    with pytest.raises(ValidationError):
        RetryPolicy(statuses=(401,))
    with pytest.raises(ValidationError):
        RetryPolicy(ambiguous_delivery="retry")


def test_identity_rejects_non_json_numbers():
    with pytest.raises(ValueError):
        identity({"score": float("nan")})
