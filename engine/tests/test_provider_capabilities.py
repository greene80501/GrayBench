"""Capability records bind an exact endpoint without claiming effective settings."""

import pytest
import httpx
from pydantic import ValidationError

from graybench.campaign_setup import CampaignSetup, build_setup
from graybench.contracts import CapabilityProfile, ControlSupport, ModelSpec, Setting
from graybench.datasets import JudgeTask
from graybench.providers import CapabilityError, Ollama, OpenAIChat
from graybench.transport import Transport

DOC = "https://example.test/model-docs"
PROBE = "a" * 64


def profile(**overrides):
    values = {
        "adapter": "openai-chat",
        "model": "gpt-4o-mini-2024-07-18",
        "base_url": "https://api.openai.com/v1",
        "generation_path": "/chat/completions",
        "checked_on": "2026-09-28",
        "documentation": (DOC,),
        "probe_digests": (PROBE,),
        "controls": {
            "temperature": ControlSupport(status="documented", evidence_refs=(DOC,)),
        },
        "input_token_limit": 128000,
        "output_token_limit": 16384,
        "limit_evidence_refs": (DOC,),
    }
    values.update(overrides)
    return CapabilityProfile(**values)


def model(*, capability=None, settings=()):
    return ModelSpec(
        adapter="openai-chat",
        model="gpt-4o-mini-2024-07-18",
        base_url="https://api.openai.com/v1",
        capability_profile=capability,
        settings=settings,
    )


def test_capability_profile_binds_exact_model_and_endpoint():
    current = profile()
    assert model(capability=current).capability_profile.digest == current.digest
    for field, changed in (
        ("adapter", "gemini"),
        ("model", "gpt-4o-mini"),
        ("base_url", "https://other.example/v1"),
    ):
        with pytest.raises(ValidationError, match="capability profile"):
            model(capability=profile(**{field: changed}))


def test_capability_evidence_references_are_typed_and_closed():
    with pytest.raises(ValidationError, match="checked_on"):
        profile(checked_on="20260928")
    with pytest.raises(ValidationError, match="generation_path"):
        profile(generation_path="//outside.example/chat/completions")
    with pytest.raises(ValidationError, match="evidence source"):
        profile(
            documentation=(),
            probe_digests=(),
            controls={},
            limit_evidence_refs=(),
            input_token_limit=None,
            output_token_limit=None,
        )
    with pytest.raises(ValidationError, match="HTTPS"):
        profile(documentation=("http://example.test/docs",))
    with pytest.raises(ValidationError, match="evidence"):
        profile(
            controls={"temperature": ControlSupport(status="documented", evidence_refs=(PROBE,))}
        )
    with pytest.raises(ValidationError, match="probe"):
        profile(
            controls={"temperature": ControlSupport(status="probe_accepted", evidence_refs=(DOC,))}
        )
    with pytest.raises(ValidationError, match="limit"):
        profile(limit_evidence_refs=())


def test_requested_control_needs_model_specific_support():
    requested = (Setting(name="temperature", value=0, support="documented", evidence=DOC),)
    assert model(capability=profile(), settings=requested).settings == requested
    for status in ("ignored", "unsupported", "unknown"):
        evidence = () if status == "unknown" else (DOC,)
        with pytest.raises(ValidationError, match="capability"):
            model(
                capability=profile(
                    controls={"temperature": ControlSupport(status=status, evidence_refs=evidence)}
                ),
                settings=requested,
            )
    with pytest.raises(ValidationError, match="capability"):
        model(capability=profile(controls={}), settings=requested)


def test_legacy_verified_word_requires_probe_acceptance():
    setting = (Setting(name="temperature", value=0, support="verified", evidence="probe"),)
    with pytest.raises(ValidationError, match="probe_accepted"):
        model(capability=profile(), settings=setting)
    observed = profile(
        controls={"temperature": ControlSupport(status="probe_accepted", evidence_refs=(PROBE,))}
    )
    assert model(capability=observed, settings=setting).capability_profile == observed


def test_profile_path_and_digest_are_bound_to_prepared_request(task):
    adapter = OpenAIChat()
    first = profile()
    spec = model(capability=first)
    request = adapter.prepare(spec, task, None)
    assert request.capability_profile_digest == first.digest
    changed = profile(output_token_limit=8192)
    changed_request = adapter.prepare(model(capability=changed), task, None)
    assert changed_request.body == request.body
    assert changed_request.digest != request.digest
    with pytest.raises(CapabilityError, match="generation path"):
        adapter.prepare(model(capability=profile(generation_path="/responses")), task, None)


def test_campaign_freezes_profile_in_model_and_request_identity(task):
    current = profile()
    spec = model(capability=current)
    private = JudgeTask(
        public=task,
        canonical_solution="SECRET_REFERENCE_SENTINEL",
        upstream_test="SECRET_TEST_SENTINEL",
        upstream_difficulty="fixture",
    )
    setup = build_setup("capability", spec, (private,), "sha256:" + "0" * 64)
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    request = OpenAIChat().prepare(spec, task, None)
    assert restored.protocol.model.capability_profile.digest == current.digest
    assert restored.protocol.request_digests[f"{task.suite}/{task.task_id}"] == request.digest


@pytest.mark.parametrize(
    "change",
    [
        {"capability_profile_digest": "0" * 64},
        {"path": "/responses"},
    ],
)
def test_transport_rejects_profile_drift_before_network(task, change):
    spec = model(capability=profile())
    request = OpenAIChat().prepare(spec, task, None).model_copy(update=change)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = Transport(spec, client=client)
        with pytest.raises(ValueError, match="capability"):
            transport.generate(request, OpenAIChat())
    assert not calls


def test_legacy_request_omits_capability_field(task):
    request = OpenAIChat().prepare(model(), task, None)
    assert "capability_profile_digest" not in request.model_dump(mode="json")


def test_copied_capability_mismatch_fails_at_request_and_run_boundaries(ledger, protocol, task):
    mismatched = profile()
    copied = protocol.model.model_copy(update={"capability_profile": mismatched})
    with pytest.raises(ValidationError, match="capability profile"):
        Ollama().prepare(copied, task, None)
    with pytest.raises(ValidationError, match="capability profile"):
        Transport(copied)
    with pytest.raises(ValidationError, match="capability profile"):
        ledger.create_run(protocol.model_copy(update={"model": copied}))
    assert ledger.verify()["events"] == 0


def test_summary_reports_operator_capability_without_effectiveness_claim(ledger, protocol, task):
    legacy = ledger.create_run(protocol)
    legacy_report = ledger.summary(legacy)
    assert legacy_report["provider_capability"]["status"] == "missing"
    assert "provider_capability_profile_missing" in legacy_report["publication_blockers"]

    observed = CapabilityProfile(
        adapter="ollama",
        model=protocol.model.model,
        base_url=protocol.model.base_url,
        generation_path="/api/chat",
        checked_on="2026-09-28",
        documentation=("https://docs.ollama.com/api/chat",),
    )
    qualified_model = protocol.model.model_copy(update={"capability_profile": observed})
    request = Ollama().prepare(qualified_model, task, None)
    revised = protocol.model_copy(
        update={
            "model": qualified_model,
            "request_digests": {protocol.task_keys[0]: request.digest},
        }
    )
    run = ledger.create_run(revised)
    report = ledger.summary(run)
    assert report["provider_capability"]["status"] == "operator_evidence_recorded"
    assert report["provider_capability"]["profile_digest"] == observed.digest
    assert report["provider_capability"]["effective_settings_status"] == "not_attested"
    assert report["publication_eligible"] is False
