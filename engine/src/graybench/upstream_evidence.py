"""Exact, bounded terminal-message capture from the trusted upstream judge."""

import hashlib
import json

from graybench.identity import canonical

CAPTURE = "bounded-trusted-stdout-v1"
OUTCOMES = frozenset(
    {"pass", "fail", "unsupported", "timeout", "candidate_error", "infrastructure_error"}
)


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate trusted judgment key")
        result[key] = value
    return result


def _finite_constant(_value):
    raise ValueError("Nonfinite trusted judgment value")


def capture_judgment(raw: bytes, *, limit: int) -> tuple[dict, dict]:
    if (
        type(raw) is not bytes
        or type(limit) is not int
        or limit <= 0
        or len(raw) > limit
        or not raw.endswith(b"\n")
        or raw.count(b"\n") != 1
    ):
        raise ValueError("Invalid or incomplete trusted judgment bytes")
    try:
        text = raw.decode("utf-8")
        message = json.loads(text, object_pairs_hook=_unique_pairs, parse_constant=_finite_constant)
        canonical(message)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid trusted judgment JSON") from exc
    if (
        type(message) is not dict
        or set(message) != {"kind", "outcome", "evidence"}
        or message["kind"] != "judgment"
        or type(message["outcome"]) is not str
        or message["outcome"] not in OUTCOMES
        or type(message["evidence"]) is not dict
    ):
        raise ValueError("Invalid trusted judgment schema")
    return message, {
        "capture": CAPTURE,
        "encoding": "utf-8",
        "text": text,
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def verify_judgment(outcome: str, evidence: dict) -> dict:
    """Check local byte/outcome consistency, not author authenticity."""
    if type(evidence) is not dict:
        raise ValueError("Missing trusted judgment evidence")
    manifest = evidence.get("manifest")
    artifact = evidence.get("trusted_judgment_artifact")
    if (
        type(manifest) is not dict
        or manifest.get("trusted_judgment_capture") != CAPTURE
        or evidence.get("termination_source") != "trusted_judgment"
        or type(artifact) is not dict
        or type(artifact.get("text")) is not str
        or type(manifest.get("output_limit")) is not int
        or len(artifact["text"]) > manifest["output_limit"]
    ):
        raise ValueError("Missing or invalid trusted judgment capture")
    try:
        message, expected = capture_judgment(
            artifact["text"].encode("utf-8"), limit=manifest["output_limit"]
        )
        matches = (
            canonical(artifact) == canonical(expected)
            and canonical(evidence.get("trusted_judgment")) == canonical(message)
            and outcome == message["outcome"]
            and all(
                key in evidence and canonical(evidence[key]) == canonical(value)
                for key, value in message["evidence"].items()
            )
        )
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ValueError("Invalid saved trusted judgment") from exc
    if not matches:
        raise ValueError("Saved outcome or evidence differs from trusted judgment")
    return message


def _declares_capture(manifest, depth=0):
    if depth > 16:
        raise ValueError("Excessive nested trusted judgment manifest")
    return type(manifest) is dict and (
        "trusted_judgment_capture" in manifest
        or _declares_capture(manifest.get("inner"), depth + 1)
    )


def verify_review_judgment(outcome: str, evidence: dict, *, _depth=0) -> None:
    """Require evidence for declared nested capture policies, including trusted errors."""
    if _depth > 16 or type(evidence) is not dict:
        raise ValueError("Invalid nested trusted judgment evidence")
    manifest = evidence.get("manifest")
    capture_fields = any(
        field in evidence for field in ("trusted_judgment", "trusted_judgment_artifact")
    )
    if type(manifest) is dict and "trusted_judgment_capture" in manifest:
        host_error = (
            manifest["trusted_judgment_capture"] == CAPTURE
            and evidence.get("termination_source") == "host_error"
            and outcome not in {"pass", "fail"}
            and not capture_fields
        )
        if not host_error:
            verify_judgment(outcome, evidence)
    elif capture_fields or "termination_source" in evidence:
        raise ValueError("Undeclared trusted judgment evidence")
    inner_manifest = manifest.get("inner") if type(manifest) is dict else None
    inner = evidence.get("inner")
    if _declares_capture(inner_manifest):
        if type(inner) is not dict or canonical(inner.get("manifest")) != canonical(inner_manifest):
            raise ValueError("Missing declared nested trusted judgment evidence")
        verify_review_judgment(outcome, inner, _depth=_depth + 1)
    elif type(inner) is dict:
        verify_review_judgment(outcome, inner, _depth=_depth + 1)
