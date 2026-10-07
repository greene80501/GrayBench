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


def contains_credential_value(value: Any, credential: str) -> bool:
    """Find the loaded credential in values destined for public artifacts or requests."""
    if not credential:
        return False
    if isinstance(value, str):
        return credential in value
    if isinstance(value, dict):
        return any(
            contains_credential_value(key, credential)
            or contains_credential_value(item, credential)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(contains_credential_value(item, credential) for item in value)
    return False


def reject_credential_value(value: Any, credential: str, context: str) -> None:
    if contains_credential_value(value, credential):
        raise ValueError(f"Loaded credential may not enter {context}")
