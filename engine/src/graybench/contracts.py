"""Versioned experiment contracts, independent of SDKs and private task oracles."""

from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from graybench.identity import identity, reject_credentials


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @property
    def digest(self) -> str:
        return identity(self.model_dump(mode="json"))


class PublicTask(Contract):
    """The only task data a provider is allowed to receive."""

    suite: Literal["normal", "hard"]
    task_id: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    entry_point: str = Field(pattern=r"^[A-Za-z_]\w*$")
    prompt_format: Literal["function_completion", "standalone_function"]


class Setting(Contract):
    name: str
    value: JsonValue
    support: Literal["documented", "verified", "unknown", "ignored", "unsupported"]
    evidence: str = Field(min_length=1)


class ModelSpec(Contract):
    adapter: str = Field(min_length=1)
    model: str = Field(min_length=1)
    base_url: str
    credential_env: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$")
    settings: tuple[Setting, ...] = ()
    accepted_returned_models: tuple[str, ...] = ()
    model_identity_evidence: str | None = None
    discovery_policy: Literal["required", "unverified_development"] = "required"
    discovery_exception_reason: str | None = Field(default=None, max_length=512)

    @field_validator("base_url")
    @classmethod
    def endpoint(cls, value: str) -> str:
        url = urlsplit(value)
        if (
            url.scheme not in {"https", "http"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("Endpoint must be an HTTP(S) URL without credentials/query/fragment")
        if url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Remote endpoints require HTTPS; use a local tunnel for local HTTP")
        return value.rstrip("/")

    @model_validator(mode="after")
    def settings_unique(self) -> "ModelSpec":
        if len({s.name for s in self.settings}) != len(self.settings):
            raise ValueError("Duplicate model settings")
        reject_credentials({s.name: s.value for s in self.settings})
        if len(set(self.accepted_returned_models)) != len(self.accepted_returned_models) or any(
            not name.strip() for name in self.accepted_returned_models
        ):
            raise ValueError("Returned model identities must be nonempty and unique")
        if self.accepted_returned_models and not (self.model_identity_evidence or "").strip():
            raise ValueError("Declared returned-model identities require supporting evidence")
        if self.discovery_policy == "unverified_development":
            if not (self.discovery_exception_reason or "").strip():
                raise ValueError(
                    "discovery_exception_reason is required for unverified development"
                )
        elif self.discovery_exception_reason is not None:
            raise ValueError("discovery_exception_reason requires unverified development policy")
        return self


class RetryPolicy(Contract):
    max_attempts: int = Field(default=3, ge=1, le=10)
    statuses: tuple[int, ...] = (429, 500, 502, 503, 504)
    delays_seconds: tuple[float, ...] = (2.0, 10.0)
    ambiguous_delivery: Literal["stop"] = "stop"

    @model_validator(mode="after")
    def valid_policy(self) -> "RetryPolicy":
        if len(self.delays_seconds) != self.max_attempts - 1:
            raise ValueError("Freeze one backoff delay per possible retry")
        if any(s not in {429, 500, 502, 503, 504} for s in self.statuses):
            raise ValueError("Only explicit transient HTTP failures may be retried")
        if any(not 0 <= d <= 3600 for d in self.delays_seconds):
            raise ValueError("Invalid backoff delay")
        return self


class Protocol(Contract):
    schema_version: Literal["3.1"] = "3.1"
    name: str = Field(min_length=1)
    track: Literal["upstream", "strengthened", "robustness"]
    dataset_digest: str = Field(pattern="^[0-9a-f]{64}$")
    task_keys: tuple[str, ...]
    request_digests: dict[str, str]
    repeats: int = Field(default=1, ge=1, le=1000)
    system_prompt: str | None = None
    extraction: Literal["raw_or_single_python_fence_v1"] = "raw_or_single_python_fence_v1"
    retry: RetryPolicy = RetryPolicy()
    model: ModelSpec
    generation_code_digest: str = Field(pattern="^[0-9a-f]{64}$")
    runtime_digest: str = Field(pattern="^[0-9a-f]{64}$")
    judge_digest: str = Field(pattern="^[0-9a-f]{64}$")
    analysis_digest: str = Field(pattern="^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def nonempty_unique_tasks(self) -> "Protocol":
        if not self.task_keys or len(set(self.task_keys)) != len(self.task_keys):
            raise ValueError("Schedule must contain nonempty, unique task keys")
        if set(self.request_digests) != set(self.task_keys):
            raise ValueError("Freeze an exact public request digest for every task")
        if any(
            len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
            for value in self.request_digests.values()
        ):
            raise ValueError("Invalid frozen request digest")
        return self


class PreparedRequest(Contract):
    """Exact public wire body. Headers and secrets are intentionally separate."""

    adapter: str
    model: str
    path: str
    body: dict[str, JsonValue]
    setting_evidence: tuple[Setting, ...]


class Generation(Contract):
    """Empty or refused answers are still returned generations and cannot be replaced."""

    text: str
    returned_model: str | None
    response_id: str | None
    finish_reason: str | None
    usage: dict[str, JsonValue]
    effective_settings: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class Observation(Contract):
    name: str
    status: Literal["observed", "unavailable", "error"]
    value: JsonValue = None
    detail: str | None = None
    evidence: dict[str, JsonValue] = Field(default_factory=dict)


def load_contract(kind: type[Contract], content: str) -> Any:
    # JSON arrays legitimately become tuple fields under strict JSON validation.
    return kind.model_validate_json(content)
