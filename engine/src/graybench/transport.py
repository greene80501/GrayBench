"""Bounded HTTP transport. One call is one attempt; redirects and SDK retries are disabled."""

import hashlib
import json
import os
import time
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from graybench.contracts import Generation, ModelSpec, Observation, PreparedRequest
from graybench.identity import canonical
from graybench.providers import Adapter


@dataclass(frozen=True)
class Delivery:
    kind: str
    status: int | None
    evidence: dict
    generation: Generation | None = None


def _bounded_zlib(raw: bytes, limit: int, wbits: int) -> bytes:
    decoder = zlib.decompressobj(wbits)
    decoded = decoder.decompress(raw, limit + 1)
    if len(decoded) > limit or decoder.unconsumed_tail:
        raise ValueError("Response exceeded frozen decoded byte limit")
    if not decoder.eof:
        raise ValueError("Compressed response is incomplete")
    if decoder.unused_data:
        raise ValueError("Compressed response has trailing data")
    return decoded


def _decode_entity(raw: bytes, encoding: str, limit: int) -> bytes:
    encoding = encoding.strip().lower()
    if encoding in {"", "identity"}:
        return raw
    try:
        if encoding == "gzip":
            return _bounded_zlib(raw, limit, zlib.MAX_WBITS | 16)
        if encoding == "deflate":
            try:
                return _bounded_zlib(raw, limit, zlib.MAX_WBITS)
            except zlib.error:
                return _bounded_zlib(raw, limit, -zlib.MAX_WBITS)
    except zlib.error as error:
        raise ValueError("Invalid compressed response") from error
    raise ValueError("Unsupported Content-Encoding: " + encoding)


class Transport:
    def __init__(
        self,
        spec: ModelSpec,
        client: httpx.Client | None = None,
        timeout_seconds: float = 600,
        max_response_bytes: int = 16 * 1024 * 1024,
    ):
        self.spec = spec
        self.max_response_bytes = max_response_bytes
        self.secret = os.environ.get(spec.credential_env, "") if spec.credential_env else ""
        if spec.credential_env and not self.secret:
            raise ValueError(f"Missing credential environment variable {spec.credential_env}")
        if self.secret and spec.credential_scope_id and self.secret in spec.credential_scope_id:
            raise ValueError("Credential scope must not contain the credential")
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds, connect=30),
            follow_redirects=False,
            trust_env=False,
            transport=httpx.HTTPTransport(retries=0),
        )
        self.owns_client = client is None

    def close(self):
        if self.owns_client:
            self.client.close()

    def _redact(self, value: str) -> str:
        return value.replace(self.secret, "[REDACTED]") if self.secret else value

    def _exchange(
        self, method: str, path: str, body: dict | None, provider: Adapter
    ) -> tuple[int | None, dict]:
        # Plugins cannot redirect credentials to another origin via a supplied absolute URL.
        if not path.startswith("/") or path.startswith("//") or "?" in path or "#" in path:
            raise ValueError("Request path must be a relative, query-free API path")
        started = time.perf_counter()
        content = canonical(body) if body is not None else b""
        auth_headers = provider.auth_headers(self.secret)
        headers = httpx.Headers(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            }
        )
        headers.update(auth_headers)
        headers["Accept-Encoding"] = "identity"
        evidence = {
            "request_body": body,
            "request_content_sha256": hashlib.sha256(content).hexdigest(),
            "request_content_bytes": len(content),
            "request_accept_encoding": "identity",
            "response_capture_version": "encoded_entity_v2",
            "credential_scope_id": self.spec.credential_scope_id,
            "auth_header_names": sorted(self._redact(name.lower()) for name in auth_headers),
            "base_url": self.spec.base_url,
            "path": path,
            "method": method,
            "response_headers": {},
            "response_body": None,
            "billing": "unknown",
        }
        status = None
        received = bytearray()
        decoded_received = bytearray()
        wire_available = True
        try:
            with self.client.stream(
                method,
                self.spec.base_url + path,
                headers=headers,
                content=content if body is not None else None,
            ) as response:
                status = response.status_code
                evidence["response_headers"] = {
                    k: self._redact(v)
                    for k, v in response.headers.items()
                    if k.lower()
                    in {
                        "x-request-id",
                        "request-id",
                        "x-goog-request-id",
                        "content-type",
                        "retry-after",
                        "date",
                        "openai-processing-ms",
                        "openai-version",
                        "content-encoding",
                    }
                }
                if response.is_stream_consumed:
                    # Injected clients can supply an already-decoded Response.
                    # Its encoded entity cannot be recovered or honestly hashed.
                    wire_available = False
                    evidence["response_capture_version"] = "preconsumed_decoded_v1"
                    try:
                        decoded_chunks = (response.content,)
                    except httpx.ResponseNotRead as error:
                        raise ValueError("Preconsumed decoded response is unavailable") from error
                else:
                    # iter_bytes() can allocate unbounded decompressed chunks.
                    # Capture the encoded entity, then decode with a hard output cap.
                    for chunk in response.iter_raw():
                        if len(received) + len(chunk) > self.max_response_bytes:
                            raise ValueError("Response exceeded frozen encoded byte limit")
                        received.extend(chunk)
                    evidence["wire_sha256"] = hashlib.sha256(received).hexdigest()
                    decoded_chunks = (
                        _decode_entity(
                            bytes(received),
                            response.headers.get("content-encoding", ""),
                            self.max_response_bytes,
                        ),
                    )
                for chunk in decoded_chunks:
                    if len(decoded_received) + len(chunk) > self.max_response_bytes:
                        raise ValueError("Response exceeded frozen decoded byte limit")
                    decoded_received.extend(chunk)
                evidence["decoded_body_sha256"] = hashlib.sha256(decoded_received).hexdigest()
                decoded = decoded_received.decode("utf-8", errors="strict")
                evidence["response_body"] = self._redact(decoded)
                if self.secret and self.secret in decoded and 200 <= status < 300:
                    # Parsing the redacted text would change the model's answer. Persist
                    # redacted evidence, but leave delivery and discovery unresolved.
                    evidence["error_type"] = "CredentialEcho"
                    evidence["error"] = "Successful provider response contained the credential"
        except (httpx.HTTPError, ValueError) as exc:
            # Never replay a timeout: the server may already have generated and charged an answer.
            evidence["error_type"] = type(exc).__name__
            evidence["error"] = self._redact(str(exc))
            evidence["partial_response_bytes"] = len(decoded_received)
            evidence["partial_wire_bytes"] = len(received) if wire_available else None
        evidence["latency_seconds"] = time.perf_counter() - started
        evidence["wire_bytes"] = len(received) if wire_available else None
        evidence["response_bytes"] = len(decoded_received)
        return status, evidence

    def generate(self, request: PreparedRequest, adapter: Adapter) -> Delivery:
        if (
            request.adapter != self.spec.adapter
            or request.model != self.spec.model
            or adapter.name != self.spec.adapter
        ):
            raise ValueError("Transport and prepared request have different model identities")
        status, evidence = self._exchange("POST", request.path, request.body, adapter)
        if "error" in evidence:
            return Delivery("ambiguous", status, evidence)
        if status is not None and status >= 500:
            evidence["error"] = "Server error does not prove no generation occurred"
            return Delivery("ambiguous", status, evidence)
        if status is not None and status >= 400:
            return Delivery("rejected", status, evidence)
        if status is None or not 200 <= status < 300:
            evidence["error"] = "Unexpected HTTP status; redirects are not followed"
            return Delivery("ambiguous", status, evidence)
        try:
            raw = json.loads(evidence["response_body"])
            if not isinstance(raw, dict):
                raise ValueError("Response must be a JSON object")
            generation = adapter.parse(raw)
        except (ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
            evidence["error_type"] = type(exc).__name__
            evidence["error"] = self._redact(str(exc))
            return Delivery("ambiguous", status, evidence)
        return Delivery("returned", status, evidence, generation)

    def discover(self, adapter: Adapter) -> list[Observation]:
        if adapter.name != self.spec.adapter:
            raise ValueError("Discovery adapter differs from frozen model identity")
        result = []
        for method, path, body in adapter.discovery_requests(self.spec):
            status, evidence = self._exchange(method, path, body, adapter)
            evidence["http_status"] = status
            evidence["observed_at"] = datetime.now(UTC).isoformat()
            try:
                if status != 200 or "error" in evidence:
                    raise ValueError(f"Discovery unavailable (HTTP {status})")
                value = json.loads(evidence["response_body"])
                canonical(value)  # Reject non-finite values before they enter durable evidence.
                result.append(
                    Observation(name=path, status="observed", value=value, evidence=evidence)
                )
            except (ValueError, TypeError, RecursionError) as exc:
                result.append(
                    Observation(name=path, status="error", detail=str(exc), evidence=evidence)
                )
        if not result:
            result.append(
                Observation(
                    name="model_metadata",
                    status="unavailable",
                    detail="This adapter has no discovery endpoint",
                )
            )
        return result
