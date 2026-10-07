"""Bind versioned client-side HTTP request evidence to a frozen attempt."""

import hashlib

import httpx

from graybench.contracts import ModelSpec, PreparedRequest
from graybench.identity import canonical, identity

LEGACY_CAPTURE_VERSION = "canonical-body-v1"
CAPTURE_VERSION = "client-built-httpx-v2"


def request_evidence_binding(request: PreparedRequest, model: ModelSpec, evidence: dict) -> str:
    """Return bound/unbound; reject a malformed or contradictory versioned claim.

    Historical evidence without a capture version remains readable but cannot
    claim a request binding. This verifies client records, not provider receipt.
    """
    if type(evidence) is not dict:
        raise ValueError("Delivery request evidence must be an object")
    if "request_capture_version" not in evidence:
        return "unbound"
    version = evidence["request_capture_version"]
    if version not in {LEGACY_CAPTURE_VERSION, CAPTURE_VERSION}:
        raise ValueError("Unknown delivery request evidence version")
    content = canonical(request.body)
    expected = {
        "request_body": request.body,
        "request_content_sha256": hashlib.sha256(content).hexdigest(),
        "request_content_bytes": len(content),
        "path": request.path,
        "method": "POST",
        "base_url": model.base_url,
        "adapter_code_digest": request.adapter_code_digest,
        "credential_scope_id": model.credential_scope_id,
        "request_public_headers": request.public_headers,
        "auth_header_names": list(request.credential_header_names or ()),
    }
    if any(key not in evidence for key in expected):
        raise ValueError("Incomplete delivery request evidence")
    observed = {key: evidence[key] for key in expected}
    if canonical(observed) != canonical(expected):
        raise ValueError("Delivery request evidence differs from frozen request")
    if version == LEGACY_CAPTURE_VERSION:
        return "unbound"
    httpx_headers = evidence.get("request_httpx_headers")
    if type(httpx_headers) is not dict:
        raise ValueError("Missing client-built HTTPX request headers")
    expected_httpx_headers = {
        **request.public_headers,
        "host": httpx.URL(model.base_url).netloc.decode("ascii"),
        "content-length": str(len(content)),
    }
    if httpx_headers.get("connection") == "keep-alive":
        expected_httpx_headers["connection"] = "keep-alive"
    if (
        httpx_headers != expected_httpx_headers
        or evidence.get("request_public_headers_sha256") != identity(request.public_headers)
        or evidence.get("request_httpx_headers_sha256") != identity(httpx_headers)
        or evidence.get("request_accept_encoding") != "identity"
    ):
        raise ValueError("Client-built HTTPX request evidence differs from frozen request")
    return "bound"
