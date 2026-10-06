"""A capability probe is an audited non-benchmark call, not a score."""

import hashlib
import json
import sys
from datetime import UTC, datetime

import httpx
import pytest

from graybench.campaign_setup import CampaignSetup, build_setup, execution_context
from graybench.capability_probe import (
    CapabilityProbe,
    capture_probe,
    verify_accepted_probe,
    verify_probe_record,
)
from graybench.cli import main
from graybench.contracts import CapabilityProfile, ControlSupport, ModelSpec, Setting
from graybench.datasets import JudgeTask
from graybench.ledger import StateError
from graybench.providers import OpenAIChat

DOC = "https://example.test/model-docs"
IMAGE = "sha256:" + "0" * 64


def spec(*, settings=(), profile=None, base_url="https://probe.example/v1"):
    return ModelSpec(
        adapter="openai-chat",
        model="probe-model",
        base_url=base_url,
        settings=settings,
        capability_profile=profile,
    )


def accepted_response():
    return {
        "id": "probe-response",
        "model": "probe-model",
        "choices": [
            {
                "message": {"role": "assistant", "content": "READY"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 1},
    }


def accepted_probe(*, settings=()):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=accepted_response())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        record = capture_probe(spec(settings=settings), OpenAIChat(), client=client)
    assert len(calls) == 1
    return record


def matching_profile(record, *, controls=None):
    return CapabilityProfile(
        adapter="openai-chat",
        model="probe-model",
        base_url="https://probe.example/v1",
        generation_path="/chat/completions",
        checked_on=datetime.now(UTC).date().isoformat(),
        documentation=(DOC,),
        probe_digests=(record.digest,),
        controls=controls or {},
    )


def private_task(task):
    return JudgeTask(
        public=task,
        canonical_solution="PRIVATE_REFERENCE",
        upstream_test="PRIVATE_TEST",
        upstream_difficulty="fixture",
    )


def test_probe_captures_one_fixed_public_request_and_verifies_response():
    record = accepted_probe()
    assert isinstance(record, CapabilityProbe)
    assert record.request.body["messages"] == [
        {
            "role": "user",
            "content": (
                "GrayBench capability probe. This is not a benchmark task. Reply with READY."
            ),
        }
    ]
    assert record.request.capability_profile_digest is None
    assert record.delivery_kind == "returned"
    assert record.generation.text == "READY"
    assert verify_accepted_probe(record, spec(), OpenAIChat()) == record.digest
    assert "api_key" not in record.model_dump_json().lower()


def test_rebound_probe_with_duplicate_answer_key_cannot_qualify():
    record = accepted_probe()
    body = json.dumps(accepted_response(), separators=(",", ":")).replace(
        '"content":"READY"', '"content":"READY","content":"READY"'
    )
    assert body.count('"content":"READY"') == 2
    digest = hashlib.sha256(body.encode()).hexdigest()
    evidence = {
        **record.evidence,
        "response_body": body,
        "decoded_body_sha256": digest,
        "wire_sha256": digest,
        "response_bytes": len(body.encode()),
        "wire_bytes": len(body.encode()),
    }
    rebound = record.model_copy(update={"evidence": evidence})
    with pytest.raises(ValueError, match="cannot be parsed"):
        verify_accepted_probe(rebound, spec(), OpenAIChat())


def test_probe_artifact_excludes_loaded_credential(monkeypatch):
    monkeypatch.setenv("GRAYBENCH_PROBE_TEST_KEY", "unit-secret-probe-123")
    credentialed = ModelSpec(
        adapter="openai-chat",
        model="probe-model",
        base_url="https://probe.example/v1",
        credential_env="GRAYBENCH_PROBE_TEST_KEY",
        credential_scope_id="openai/project/probe",
    )

    def handler(request):
        assert request.headers["authorization"] == "Bearer unit-secret-probe-123"
        return httpx.Response(200, json=accepted_response())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        record = capture_probe(credentialed, OpenAIChat(), client=client)
    assert "unit-secret-probe-123" not in record.model_dump_json()
    assert verify_accepted_probe(record, credentialed, OpenAIChat()) == record.digest


def test_probe_rejects_credential_in_setting_before_dispatch(monkeypatch):
    secret = "unit-secret-probe-123"
    monkeypatch.delenv("GRAYBENCH_PROBE_TEST_KEY", raising=False)
    credentialed = ModelSpec(
        adapter="openai-chat",
        model="probe-model",
        base_url="https://probe.example/v1",
        credential_env="GRAYBENCH_PROBE_TEST_KEY",
        credential_scope_id="openai/project/probe",
        settings=(Setting(name="stop", value=secret, support="documented", evidence="probe"),),
    )
    monkeypatch.setenv("GRAYBENCH_PROBE_TEST_KEY", secret)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=accepted_response())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="credential"):
            capture_probe(credentialed, OpenAIChat(), client=client)
    assert calls == []


@pytest.mark.parametrize("base_url", ["https://PROBE.EXAMPLE/v1", "https://probe.example:443/v1"])
def test_probe_verifies_httpx_normalized_host(base_url):
    model = spec(base_url=base_url)
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=accepted_response()))
    ) as client:
        record = capture_probe(model, OpenAIChat(), client=client)
    assert verify_accepted_probe(record, model, OpenAIChat()) == record.digest


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.model_copy(update={"base_url": "https://other.example/v1"}),
        lambda p: p.model_copy(
            update={"request": p.request.model_copy(update={"path": "/responses"})}
        ),
        lambda p: p.model_copy(
            update={"request": p.request.model_copy(update={"body": {"model": "probe-model"}})}
        ),
        lambda p: p.model_copy(
            update={"request": p.request.model_copy(update={"adapter_code_digest": "0" * 64})}
        ),
        lambda p: p.model_copy(
            update={"evidence": {**p.evidence, "decoded_body_sha256": "0" * 64}}
        ),
        lambda p: p.model_copy(
            update={"evidence": {**p.evidence, "request_httpx_headers_sha256": "0" * 64}}
        ),
        lambda p: p.model_copy(update={"evidence": {**p.evidence, "response_body": "{}"}}),
        lambda p: p.model_copy(
            update={"generation": p.generation.model_copy(update={"text": "NO"})}
        ),
    ],
)
def test_probe_rejects_changed_request_or_response(change):
    record = accepted_probe()
    with pytest.raises(ValueError):
        verify_accepted_probe(change(record), spec(), OpenAIChat())


def test_returned_probe_cannot_skip_response_hash_with_redaction_marker():
    record = accepted_probe()
    changed_body = record.evidence["response_body"].replace("READY", "[REDACTED]")
    changed = record.model_copy(
        update={
            "evidence": {**record.evidence, "response_body": changed_body},
            "generation": record.generation.model_copy(update={"text": "[REDACTED]"}),
        }
    )
    with pytest.raises(ValueError, match="hash"):
        verify_accepted_probe(changed, spec(), OpenAIChat())


def test_probe_rejects_unaccepted_returned_model():
    record = accepted_probe()
    body = json.loads(record.evidence["response_body"])
    body["model"] = "different-model"
    encoded = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    changed = record.model_copy(
        update={
            "evidence": {
                **record.evidence,
                "response_body": encoded,
                "decoded_body_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            },
            "generation": record.generation.model_copy(
                update={"returned_model": "different-model"}
            ),
        }
    )
    with pytest.raises(ValueError, match="returned model"):
        verify_accepted_probe(changed, spec(), OpenAIChat())


def test_rejected_call_is_preserved_but_cannot_support_accepted_control():
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(400, json={"error": "bad"}))
    ) as client:
        record = capture_probe(spec(), OpenAIChat(), client=client)
    assert record.delivery_kind == "rejected"
    assert record.status == 400
    verify_probe_record(record, spec(), OpenAIChat())
    with pytest.raises(ValueError, match="returned"):
        verify_accepted_probe(record, spec(), OpenAIChat())


def test_server_error_is_preserved_as_ambiguous_and_cannot_qualify():
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(503, json={"error": "busy"}))
    ) as client:
        record = capture_probe(spec(), OpenAIChat(), client=client)
    assert record.delivery_kind == "ambiguous"
    assert record.status == 503
    verify_probe_record(record, spec(), OpenAIChat())
    with pytest.raises(ValueError, match="returned"):
        verify_accepted_probe(record, spec(), OpenAIChat())


def test_campaign_requires_exact_probe_records_and_control_value(task):
    setting = Setting(name="temperature", value=0.2, support="verified", evidence="probe")
    record = accepted_probe(settings=(setting,))
    profile = matching_profile(
        record,
        controls={
            "temperature": ControlSupport(status="probe_accepted", evidence_refs=(record.digest,))
        },
    )
    model = spec(settings=(setting,), profile=profile)
    item = private_task(task)
    with pytest.raises(ValueError, match="probe"):
        build_setup("missing", model, (item,), IMAGE)
    setup = build_setup("accepted", model, (item,), IMAGE, capability_probes=(record,))
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    assert restored.capability_probes[0].digest == record.digest
    assert (
        execution_context(restored)["setup"]["capability_probes"][0]["delivery_kind"] == "returned"
    )
    with pytest.raises(ValueError, match="probe"):
        build_setup("duplicate", model, (item,), IMAGE, capability_probes=(record, record))
    wrong = record.model_copy(update={"base_url": "https://wrong.example/v1"})
    with pytest.raises(ValueError, match="probe"):
        build_setup("wrong", model, (item,), IMAGE, capability_probes=(wrong,))
    different_setting = setting.model_copy(update={"value": 0.5})
    different_model = spec(settings=(different_setting,), profile=profile)
    with pytest.raises(ValueError, match="probe"):
        build_setup("value", different_model, (item,), IMAGE, capability_probes=(record,))
    stale_profile = profile.model_copy(update={"checked_on": "2020-01-01"})
    with pytest.raises(ValueError, match="probe"):
        build_setup(
            "dated-before-probe",
            spec(settings=(setting,), profile=stale_profile),
            (item,),
            IMAGE,
            capability_probes=(record,),
        )


def test_short_probe_cannot_substantiate_token_limit(task):
    record = accepted_probe()
    profile = matching_profile(record).model_copy(
        update={"output_token_limit": 1024, "limit_evidence_refs": (record.digest,)}
    )
    with pytest.raises(ValueError, match="token limit"):
        build_setup(
            "unsupported-limit",
            spec(profile=profile),
            (private_task(task),),
            IMAGE,
            capability_probes=(record,),
        )


def test_ledger_rechecks_probe_bundle_before_durable_run(ledger, task):
    record = accepted_probe()
    model = spec(profile=matching_profile(record))
    setup = build_setup(
        "ledger-probe", model, (private_task(task),), IMAGE, capability_probes=(record,)
    )
    with pytest.raises(StateError, match="probe"):
        ledger.create_run(setup.protocol)
    assert ledger.verify()["events"] == 0
    context = execution_context(setup)
    tampered = json.loads(json.dumps(context))
    tampered["setup"]["capability_probes"][0]["evidence"]["decoded_body_sha256"] = "0" * 64
    with pytest.raises(StateError, match="probe"):
        ledger.create_run(setup.protocol, tampered)
    assert ledger.verify()["events"] == 0
    run = ledger.create_run(setup.protocol, context)
    report = ledger.summary(run)
    assert report["provider_capability"]["probe_artifacts_status"] == "verified_local_records"
    assert report["provider_capability"]["probe_digests"] == [record.digest]


def test_ledger_rejects_unclaimed_probe_record(ledger, task):
    setup = build_setup("unclaimed", spec(), (private_task(task),), IMAGE)
    assert "capability_probes" not in setup.model_dump(mode="json")
    context = execution_context(setup)
    context["setup"]["capability_probes"] = [accepted_probe().model_dump(mode="json")]
    with pytest.raises(StateError, match="probe"):
        ledger.create_run(setup.protocol, context)
    assert ledger.verify()["events"] == 0


def test_probe_cli_writes_exclusive_artifact(monkeypatch, tmp_path, capsys):
    record = accepted_probe()
    spec_path = tmp_path / "model.json"
    spec_path.write_text(spec().model_dump_json(), encoding="utf-8")
    output = tmp_path / "probe.json"
    monkeypatch.setattr("graybench.cli.capture_probe", lambda _spec, _adapter: record)
    monkeypatch.setattr(sys, "argv", ["graybench", "capability-probe", str(spec_path), str(output)])
    main()
    assert CapabilityProbe.model_validate_json(output.read_bytes()) == record
    assert json.loads(capsys.readouterr().out)["probe_digest"] == record.digest
    with pytest.raises(FileExistsError):
        main()


def test_probe_cli_reports_returned_model_mismatch_as_unqualified(monkeypatch, tmp_path, capsys):
    record = accepted_probe()
    body = json.loads(record.evidence["response_body"])
    body["model"] = "different-model"
    encoded = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    wrong_model = record.model_copy(
        update={
            "evidence": {
                **record.evidence,
                "response_body": encoded,
                "decoded_body_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            },
            "generation": record.generation.model_copy(
                update={"returned_model": "different-model"}
            ),
        }
    )
    spec_path = tmp_path / "model.json"
    spec_path.write_text(spec().model_dump_json(), encoding="utf-8")
    output = tmp_path / "probe.json"
    monkeypatch.setattr("graybench.cli.capture_probe", lambda _spec, _adapter: wrong_model)
    monkeypatch.setattr(sys, "argv", ["graybench", "capability-probe", str(spec_path), str(output)])
    main()
    assert CapabilityProbe.model_validate_json(output.read_bytes()) == wrong_model
    result = json.loads(capsys.readouterr().out)
    assert result["qualifies_for_probe_accepted"] is False
    assert "returned model" in result["qualification_error"]
