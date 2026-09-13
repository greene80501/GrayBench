"""Canonical JSON identities. NaN, credentials, and implicit serialization are forbidden."""

import hashlib
import json
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def identity(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def reject_credentials(value: Any) -> None:
    """Prevent credential fields in durable config; actual secret values stay in transport."""
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower().replace("-", "_")
            if normalized in {
                "api_key",
                "apikey",
                "authorization",
                "password",
                "access_token",
                "refresh_token",
                "cookie",
                "secret",
                "x_goog_api_key",
            }:
                raise ValueError(f"Credential field is not allowed in an artifact: {key}")
            reject_credentials(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            reject_credentials(item)
