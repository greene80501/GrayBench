"""Conservative identities extracted from provider metadata, without guessing aliases."""

import re

from graybench.identity import identity
from graybench.providers import adapter, model_metadata_path


def observe_run(ledger, run_id, transport, *, attempt_id=None, post_token=None):
    ledger.require_run_open(run_id)
    protocol = ledger.protocol(run_id)
    ledger.require_protocol_serialization_stable(run_id, protocol)
    spec = protocol.model
    if transport.spec != spec:
        raise ValueError("Discovery transport differs from frozen model")
    provider = adapter(spec.adapter)
    if protocol.adapter_code_manifest is None:
        observations = transport.discover(provider)
    else:
        observations = transport.discover(
            provider,
            expected_adapter_code_digest=identity(protocol.adapter_code_manifest),
        )
    return ledger.record_model_observation(
        run_id,
        {
            "model_spec_digest": spec.digest,
            "observations": [o.model_dump(mode="json") for o in observations],
            "identity": discovery_identity(spec, observations),
        },
        attempt_id=attempt_id,
        post_token=post_token,
    )


def discovery_identity(spec, observations):
    if len({o.name for o in observations}) != len(observations):
        return {"status": "unavailable", "reason": "duplicate discovery observations"}
    if spec.discovery_policy == "unverified_development":
        if adapter(spec.adapter).discovery_requests(spec):
            return {
                "status": "unavailable",
                "reason": "discovery exception is invalid when an endpoint exists",
            }
        if (
            len(observations) != 1
            or observations[0].name != "model_metadata"
            or observations[0].status != "unavailable"
        ):
            return {"status": "unavailable", "reason": "invalid no-endpoint observation"}
        declared = {
            "adapter": spec.adapter,
            "model": spec.model,
            "base_url": spec.base_url,
            "reason": spec.discovery_exception_reason,
        }
        return {
            "status": "unverified_development",
            "digest": identity(declared),
            "identity": declared,
            "verification": "operator-declared; model identity not observed",
        }
    if spec.adapter in {"openai-chat", "openai-responses", "gemini"}:
        return hosted_identity(spec, observations)
    if spec.adapter != "ollama":
        return {
            "status": "unavailable",
            "reason": "provider-specific identity extraction not implemented",
        }
    records = {o.name: o for o in observations}
    required = ("/api/version", "/api/tags", "/api/show")
    if any(name not in records or records[name].status != "observed" for name in required):
        return {"status": "unavailable", "reason": "required discovery failed"}
    version, tags, show = (records[name].value for name in required)
    if not all(type(v) is dict for v in (version, tags, show)):
        return {"status": "unavailable", "reason": "invalid discovery shapes"}
    if not isinstance(show.get("model_info"), dict) or not show["model_info"]:
        return {"status": "unavailable", "reason": "missing model configuration"}
    models = tags.get("models")
    if not isinstance(models, list) or not isinstance(version.get("version"), str):
        return {"status": "unavailable", "reason": "missing server version or model catalog"}
    matches = [
        m for m in models if type(m) is dict and spec.model in (m.get("name"), m.get("model"))
    ]
    if len(matches) != 1:
        return {
            "status": "unavailable",
            "reason": "requested model does not have one exact catalog match",
        }
    digest = matches[0].get("digest")
    if not isinstance(digest, str) or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", digest):
        return {"status": "unavailable", "reason": "missing valid model digest"}
    stable = {
        "server_version": version["version"],
        "model_digest": digest.removeprefix("sha256:"),
        "show": {k: v for k, v in show.items() if k != "modified_at"},
    }
    return {
        "status": "observed",
        "digest": identity(stable),
        "identity": stable,
        "verification": "server-reported; not independent weight attestation",
    }


def hosted_identity(spec, observations):
    """A fingerprint of provider claims, never an assertion about actual model weights."""
    path = model_metadata_path(spec)
    matches = [o for o in observations if o.name == path and o.status == "observed"]
    if len(matches) != 1 or type(matches[0].value) is not dict:
        return {"status": "unavailable", "reason": "required model metadata unavailable"}
    record = matches[0].value
    if spec.adapter == "gemini":
        expected = "models/" + spec.model.removeprefix("models/")
        valid = (
            record.get("name") == expected
            and isinstance(record.get("version"), str)
            and bool(record["version"].strip())
            and all(
                type(record.get(k)) is int and record[k] > 0
                for k in ("inputTokenLimit", "outputTokenLimit")
            )
            and type(record.get("supportedGenerationMethods")) is list
            and all(type(m) is str for m in record["supportedGenerationMethods"])
            and "generateContent" in record["supportedGenerationMethods"]
        )
    else:
        valid = (
            record.get("id") == spec.model
            and record.get("object") == "model"
            and type(record.get("created")) is int
            and record["created"] >= 0
            and isinstance(record.get("owned_by"), str)
            and bool(record["owned_by"].strip())
        )
    if not valid:
        return {"status": "unavailable", "reason": "incomplete or mismatched model metadata"}
    stable = {"adapter": spec.adapter, "base_url": spec.base_url, "metadata": record}
    return {
        "status": "observed",
        "digest": identity(stable),
        "identity": stable,
        "verification": (
            "provider-reported metadata; not independent weight attestation "
            "or effective-setting verification"
        ),
    }
