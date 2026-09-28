"""One non-benchmark provider call and offline checks of its local evidence."""

import hashlib
import json
import os
from datetime import UTC, date, datetime
from typing import Literal

import httpx
from pydantic import JsonValue

from graybench.contracts import (
    Contract,
    Generation,
    ModelSpec,
    PreparedRequest,
    PublicTask,
    require_credential_scope_for_new_run,
)
from graybench.identity import canonical, identity, reject_credential_value
from graybench.providers import Adapter
from graybench.transport import Transport

PROBE_TASK = PublicTask(
    suite="normal",
    task_id="graybench/capability-probe/v1",
    family_id="graybench/capability-probe/v1",
    prompt="GrayBench capability probe. This is not a benchmark task. Reply with READY.",
    entry_point="probe",
    prompt_format="standalone_function",
)


class CapabilityProbe(Contract):
    """Full client-side probe record; it is not remote-receipt attestation."""

    schema_version: Literal["1"] = "1"
    spec: ModelSpec
    base_url: str
    request: PreparedRequest
    delivery_kind: Literal["returned", "rejected", "ambiguous"]
    status: int | None
    evidence: dict[str, JsonValue]
    generation: Generation | None
    recorded_at: str


def capture_probe(
    spec: ModelSpec, provider: Adapter, *, client: httpx.Client | None = None
) -> CapabilityProbe:
    """Send one fixed probe prompt; return rejected/ambiguous calls as evidence too."""
    bare = ModelSpec.model_validate_json(
        spec.model_copy(update={"capability_profile": None}).model_dump_json()
    )
    require_credential_scope_for_new_run(bare)
    secret = os.environ.get(bare.credential_env, "") if bare.credential_env else ""
    reject_credential_value(bare.model_dump(mode="json"), secret, "capability probe config")
    request = provider.prepare(bare, PROBE_TASK, None)
    reject_credential_value(request.model_dump(mode="json"), secret, "capability probe request")
    transport = Transport(bare, client=client)
    try:
        delivery = transport.generate(request, provider)
    finally:
        transport.close()
    return CapabilityProbe(
        spec=bare,
        base_url=bare.base_url,
        request=request,
        delivery_kind=delivery.kind,
        status=delivery.status,
        evidence=delivery.evidence,
        generation=delivery.generation,
        recorded_at=datetime.now(UTC).isoformat(),
    )


def verify_probe_record(record: CapabilityProbe, target: ModelSpec, provider: Adapter) -> str:
    """Check local record cohesion and exact declared endpoint/account scope."""
    record = CapabilityProbe.model_validate_json(record.model_dump_json())
    target = ModelSpec.model_validate_json(target.model_dump_json())
    observed_at = datetime.fromisoformat(record.recorded_at)
    if observed_at.utcoffset() is None or observed_at.utcoffset().total_seconds() != 0:
        raise ValueError("Capability probe recorded_at must be UTC")
    if record.schema_version != "1":
        raise ValueError("Unknown capability probe schema")
    if record.spec.capability_profile is not None:
        raise ValueError("Capability probe request must be unprofiled")
    if (
        (
            record.spec.adapter,
            record.spec.model,
            record.spec.base_url,
            record.spec.credential_env,
            record.spec.credential_scope_id,
        )
        != (
            target.adapter,
            target.model,
            target.base_url,
            target.credential_env,
            target.credential_scope_id,
        )
        or record.base_url != target.base_url
        or provider.name != target.adapter
    ):
        raise ValueError("Capability probe model, endpoint, or account scope differs")
    expected = provider.prepare(record.spec, PROBE_TASK, None)
    if record.request != expected:
        raise ValueError("Capability probe request differs from fixed public prompt")
    evidence = record.evidence
    content = canonical(record.request.body)
    httpx_headers = evidence.get("request_httpx_headers")
    expected_httpx_headers = {
        **(record.request.public_headers or {}),
        "host": httpx.URL(record.base_url).netloc.decode("ascii"),
        "content-length": str(len(content)),
    }
    if (
        evidence.get("base_url") != record.base_url
        or evidence.get("path") != record.request.path
        or evidence.get("method") != "POST"
        or evidence.get("request_body") != record.request.body
        or evidence.get("request_content_sha256") != hashlib.sha256(content).hexdigest()
        or evidence.get("request_content_bytes") != len(content)
        or evidence.get("request_public_headers") != record.request.public_headers
        or evidence.get("request_public_headers_sha256") != identity(record.request.public_headers)
        or evidence.get("credential_scope_id") != record.spec.credential_scope_id
        or evidence.get("auth_header_names") != sorted(record.request.credential_header_names or ())
        or evidence.get("adapter_code_digest") != record.request.adapter_code_digest
        or type(httpx_headers) is not dict
        or evidence.get("request_httpx_headers_sha256") != identity(httpx_headers)
        or set(httpx_headers) - set(expected_httpx_headers) - {"connection"}
        or any(httpx_headers.get(name) != value for name, value in expected_httpx_headers.items())
        or httpx_headers.get("connection") not in (None, "keep-alive")
    ):
        raise ValueError("Capability probe transport request evidence differs")
    body = evidence.get("response_body")
    if isinstance(body, str) and (record.delivery_kind == "returned" or "[REDACTED]" not in body):
        if evidence.get("decoded_body_sha256") != hashlib.sha256(body.encode("utf-8")).hexdigest():
            raise ValueError("Capability probe response body hash differs")
    if record.delivery_kind == "returned":
        if (
            record.status is None
            or not 200 <= record.status < 300
            or "error" in evidence
            or not isinstance(body, str)
            or record.generation is None
        ):
            raise ValueError("Capability probe returned state is inconsistent")
        try:
            parsed = provider.parse(json.loads(body))
        except (ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
            raise ValueError("Capability probe response cannot be parsed") from exc
        if parsed != record.generation:
            raise ValueError("Capability probe parsed generation differs")
        if parsed.returned_model is not None and parsed.returned_model not in {
            target.model,
            *target.accepted_returned_models,
        }:
            raise ValueError("Capability probe returned model is not accepted")
    elif record.delivery_kind == "rejected":
        if record.status is None or not 400 <= record.status < 500 or record.generation is not None:
            raise ValueError("Capability probe rejected state is inconsistent")
    elif record.delivery_kind == "ambiguous":
        if record.generation is not None or "error" not in evidence:
            raise ValueError("Capability probe ambiguous state has a generation")
    else:
        raise ValueError("Unknown capability probe delivery state")
    return record.digest


def verify_accepted_probe(record: CapabilityProbe, target: ModelSpec, provider: Adapter) -> str:
    digest = verify_probe_record(record, target, provider)
    if record.delivery_kind != "returned":
        raise ValueError("Capability probe was not returned and cannot support probe_accepted")
    return digest


def verify_probe_bundle(
    target: ModelSpec, records: tuple[CapabilityProbe, ...], provider: Adapter
) -> tuple[str, ...]:
    """Require every profile probe reference to have one accepted local record."""
    profile = target.capability_profile
    if profile is None:
        if records:
            raise ValueError("Capability probes require a capability profile")
        return ()
    if set(profile.limit_evidence_refs) & set(profile.probe_digests):
        raise ValueError("A short capability probe cannot establish a token limit")
    digests = tuple(record.digest for record in records)
    if len(set(digests)) != len(digests) or set(digests) != set(profile.probe_digests):
        raise ValueError("Capability probe records differ from profile references")
    by_digest = {record.digest: record for record in records}
    for record in records:
        verify_accepted_probe(record, target, provider)
        if (
            date.fromisoformat(profile.checked_on)
            < datetime.fromisoformat(record.recorded_at).date()
        ):
            raise ValueError("Capability probe was observed after profile checked_on")
    requested = {setting.name: setting.value for setting in target.settings}
    for name, control in profile.controls.items():
        if control.status != "probe_accepted":
            continue
        for digest in set(control.evidence_refs) & set(by_digest):
            probed = {setting.name: setting.value for setting in by_digest[digest].spec.settings}
            if name not in probed or (name in requested and probed[name] != requested[name]):
                raise ValueError("Capability probe did not send the requested control value")
    return digests
