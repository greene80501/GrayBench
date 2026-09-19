"""Bounded HTTP transport. One call is one attempt; redirects and SDK retries are disabled."""

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from graybench.contracts import Generation, ModelSpec, Observation, PreparedRequest
from graybench.identity import canonical
from graybench.providers import Adapter, adapter


@dataclass(frozen=True)
class Delivery:
    kind: str
    status: int | None
    evidence: dict
    generation: Generation | None = None


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

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        headers.update(adapter(self.spec.adapter).auth_headers(self.secret))
        return headers

    def _exchange(self, method: str, path: str, body: dict | None) -> tuple[int | None, dict]:
        # Plugins cannot redirect credentials to another origin via a supplied absolute URL.
        if not path.startswith("/") or path.startswith("//") or "?" in path or "#" in path:
            raise ValueError("Request path must be a relative, query-free API path")
        started = time.perf_counter()
        evidence = {
            "request_body": body,
            "base_url": self.spec.base_url,
            "path": path,
            "method": method,
            "response_headers": {},
            "response_body": None,
            "billing": "unknown",
        }
        status = None
        received = bytearray()
        try:
            with self.client.stream(
                method,
                self.spec.base_url + path,
                headers=self._headers(),
                content=canonical(body) if body is not None else None,
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
                    }
                }
                for chunk in response.iter_bytes():
                    if len(received) + len(chunk) > self.max_response_bytes:
                        raise ValueError("Response exceeded frozen byte limit")
                    received.extend(chunk)
                evidence["wire_sha256"] = hashlib.sha256(received).hexdigest()
                evidence["response_body"] = self._redact(received.decode("utf-8", errors="strict"))
        except (httpx.HTTPError, ValueError) as exc:
            # Never replay a timeout: the server may already have generated and charged an answer.
            evidence["error_type"] = type(exc).__name__
            evidence["error"] = self._redact(str(exc))
            evidence["partial_response_bytes"] = len(received)
        evidence["latency_seconds"] = time.perf_counter() - started
        evidence["response_bytes"] = len(received)
        return status, evidence

    def generate(self, request: PreparedRequest, adapter: Adapter) -> Delivery:
        status, evidence = self._exchange("POST", request.path, request.body)
        if "error" in evidence:
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
        result = []
        for method, path, body in adapter.discovery_requests(self.spec):
            status, evidence = self._exchange(method, path, body)
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
