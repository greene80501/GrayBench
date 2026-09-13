"""Conservative identities extracted from provider metadata, without guessing aliases."""

import re

from graybench.identity import identity
from graybench.providers import adapter


def observe_run(ledger, run_id, transport):
    spec = ledger.protocol(run_id).model
    if transport.spec != spec:
        raise ValueError("Discovery transport differs from frozen model")
    observations = transport.discover(adapter(spec.adapter))
    return ledger.record_model_observation(
        run_id,
        {
            "model_spec_digest": spec.digest,
            "observations": [o.model_dump(mode="json") for o in observations],
            "identity": discovery_identity(spec, observations),
        },
    )


def discovery_identity(spec, observations):
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
