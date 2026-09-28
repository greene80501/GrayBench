"""Canonical non-secret application headers for a frozen provider request."""

from collections.abc import Mapping

BASE_PUBLIC_HEADERS = {
    "accept": "application/json",
    "accept-encoding": "identity",
    "content-type": "application/json",
}
_TOKEN_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'*+-.^_`|~"
)
_CREDENTIAL_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "api-key",
        "x-api-key",
        "x-goog-api-key",
        "anthropic-api-key",
    }
)
_ROUTING_HEADERS = frozenset(
    {
        "host",
        "content-length",
        "content-encoding",
        "transfer-encoding",
        "connection",
        "proxy-connection",
        "upgrade",
        "te",
        "trailer",
    }
)


def valid_header_name(name: str) -> bool:
    return type(name) is str and 0 < len(name) <= 256 and all(c in _TOKEN_CHARS for c in name)


def valid_header_value(value: str) -> bool:
    return type(value) is str and 0 < len(value) <= 8192 and all(32 <= ord(c) <= 126 for c in value)


def credential_like(name: str) -> bool:
    return name in _CREDENTIAL_HEADERS or name.endswith(("-api-key", "-token", "-secret"))


def freeze_public_headers(extra: Mapping[str, str]) -> dict[str, str]:
    """Freeze base JSON headers plus an adapter's non-secret, semantic extensions."""
    if not isinstance(extra, Mapping):
        raise ValueError("Public headers must be a mapping")
    result = dict(BASE_PUBLIC_HEADERS)
    for original, value in extra.items():
        if not valid_header_name(original) or not valid_header_value(value):
            raise ValueError("Invalid public header name or value")
        name = original.lower()
        if name in result or credential_like(name) or name in _ROUTING_HEADERS:
            raise ValueError("Public header overrides a reserved or credential field")
        result[name] = value
    if len(result) != len(extra) + len(BASE_PUBLIC_HEADERS):
        raise ValueError("Duplicate case-insensitive public header")
    return dict(sorted(result.items()))


def validate_frozen_public_headers(headers: dict[str, str]) -> dict[str, str]:
    """Reject a copied or edited request that bypassed adapter preparation."""
    if type(headers) is not dict or any(type(k) is not str for k in headers):
        raise ValueError("Frozen public headers must be a mapping")
    extra = {k: v for k, v in headers.items() if k not in BASE_PUBLIC_HEADERS}
    if freeze_public_headers(extra) != headers:
        raise ValueError("Frozen public headers are not canonical")
    return headers
