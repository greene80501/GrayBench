"""Check exact saved bytes and local consistency of the 2026-09-28 probes."""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from graybench.capability_probe import (
    CapabilityProbe,
    verify_accepted_probe,
    verify_probe_record,
)
from graybench.contracts import ModelSpec, Observation
from graybench.identity import identity
from graybench.model_discovery import discovery_identity
from graybench.request_headers import freeze_public_headers

from graybench.providers import adapter, adapter_code_digest

HERE = Path(__file__).resolve().parent
EXPECTED = {
    "gemini-2.5-flash": (
        "rejected",
        404,
        "c97a6e85310d225b19d4c4512d31bde3782b5080339bd96290a75e57318bbc31",
    ),
    "gemini-3.8-flash": (
        "returned",
        200,
        "4d4d536ed9cb0653cb95b8f1afd1447fe36e3e30f04035e38696dc4372f14e7f",
    ),
    "gpt-4o-mini-2024-07-18": (
        "returned",
        200,
        "bd2cc076dd97ba0e7ae6535e39db3991080dc8dfb00da82579cdf40adef95695",
    ),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_discovery(spec: ModelSpec, observation: Observation) -> None:
    provider = adapter(spec.adapter)
    requests = provider.discovery_requests(spec)
    require(len(requests) == 1, f"Expected one metadata request: {spec.model}")
    method, path, body = requests[0]
    evidence = observation.evidence
    require(
        observation.name == path
        and observation.status == "observed"
        and evidence.get("method") == method
        and evidence.get("path") == path
        and evidence.get("base_url") == spec.base_url
        and evidence.get("credential_scope_id") == spec.credential_scope_id
        and evidence.get("http_status") == 200
        and evidence.get("request_body") == body
        and evidence.get("request_content_bytes") == 0
        and evidence.get("request_content_sha256") == hashlib.sha256(b"").hexdigest()
        and evidence.get("adapter_code_digest") == adapter_code_digest(provider),
        f"Discovery request or status differs: {spec.model}",
    )
    public_headers = evidence.get("request_public_headers")
    httpx_headers = evidence.get("request_httpx_headers")
    require(
        public_headers == freeze_public_headers(provider.public_headers(spec))
        and evidence.get("request_public_headers_sha256") == identity(public_headers)
        and isinstance(httpx_headers, dict)
        and evidence.get("request_httpx_headers_sha256") == identity(httpx_headers)
        and all(httpx_headers.get(key) == value for key, value in public_headers.items())
        and httpx_headers.get("host") == urlsplit(spec.base_url).netloc
        and httpx_headers.get("connection") in (None, "keep-alive")
        and set(httpx_headers) <= set(public_headers) | {"host", "connection"}
        and evidence.get("auth_header_names") == sorted(provider.credential_header_names),
        f"Discovery headers differ: {spec.model}",
    )
    response_body = evidence.get("response_body")
    require(
        isinstance(response_body, str)
        and evidence.get("decoded_body_sha256")
        == hashlib.sha256(response_body.encode("utf-8")).hexdigest()
        and evidence.get("response_bytes") == len(response_body.encode("utf-8"))
        and json.loads(response_body) == observation.value,
        f"Discovery response differs from observed metadata: {spec.model}",
    )


def main() -> None:
    manifest = json.loads((HERE / "manifest.json").read_bytes())
    require(manifest["schema_version"] == "1", "Unexpected manifest schema")
    require(
        manifest["source_revision"] == "ae60bd4824e268610ee172827404c11589754e6c",
        "Unexpected source revision",
    )
    listed = {item["path"] for item in manifest["files"]}
    require(len(listed) == 9, "Expected nine distinct evidence files")
    require(
        listed == {path.name for path in HERE.glob("*.json")} - {"manifest.json"},
        "Evidence file set differs from manifest",
    )
    for item in manifest["files"]:
        raw = (HERE / item["path"]).read_bytes()
        require(len(raw) == item["bytes"], f"Byte count differs: {item['path']}")
        require(
            hashlib.sha256(raw).hexdigest() == item["sha256"], f"SHA-256 differs: {item['path']}"
        )

    for name, (delivery, status, digest) in EXPECTED.items():
        spec = ModelSpec.model_validate_json((HERE / f"{name}-model.json").read_bytes())
        discovery = json.loads((HERE / f"{name}-discovery.json").read_bytes())
        require(
            discovery["model"] == spec.model_dump(mode="json"), f"Discovery spec differs: {name}"
        )
        observations = tuple(Observation.model_validate(item) for item in discovery["observations"])
        require(len(observations) == 1, f"Unexpected discovery count: {name}")
        verify_discovery(spec, observations[0])
        require(
            discovery_identity(spec, observations)["status"] == "observed",
            f"Discovery failed: {name}",
        )
        probe = CapabilityProbe.model_validate_json(
            (HERE / f"{name}-capability-probe.json").read_bytes()
        )
        require(
            (probe.delivery_kind, probe.status, probe.digest) == (delivery, status, digest),
            f"Unexpected probe outcome: {name}",
        )
        require(
            verify_probe_record(probe, spec, adapter(spec.adapter)) == digest,
            f"Probe evidence differs: {name}",
        )
        if delivery == "returned":
            require(
                verify_accepted_probe(probe, spec, adapter(spec.adapter)) == digest,
                f"Probe not accepted: {name}",
            )
        print(
            f"{name}: metadata observed; generation {delivery} HTTP {status}; local record verified"
        )


if __name__ == "__main__":
    main()
