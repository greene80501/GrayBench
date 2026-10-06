"""Bind versioned client-side HTTP request evidence to a frozen attempt."""

import hashlib

from graybench.contracts import ModelSpec, PreparedRequest
from graybench.identity import canonical

CAPTURE_VERSION = "canonical-body-v1"


def request_evidence_binding(request: PreparedRequest, model: ModelSpec, evidence: dict) -> str:
    """Return bound/unbound; reject a malformed or contradictory versioned claim.

    Historical evidence without a capture version remains readable but cannot
    claim a request binding. This verifies client records, not provider receipt.
    """
    if type(evidence) is not dict:
        raise ValueError("Delivery request evidence must be an object")
    if "request_capture_version" not in evidence:
        return "unbound"
    if evidence["request_capture_version"] != CAPTURE_VERSION:
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
    return "bound"
