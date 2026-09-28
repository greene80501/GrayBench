"""Native wire adapters with explicit settings and no hidden retries or prompt helpers.

Adapter support is extensible; it is not a claim that every endpoint/model has been validated.
"""

import os
from abc import ABC, abstractmethod
from importlib.metadata import entry_points
from typing import Any
from urllib.parse import quote

from graybench.adapter_provenance import adapter_code_digest
from graybench.contracts import Generation, ModelSpec, PreparedRequest, PublicTask
from graybench.request_headers import freeze_credential_header_names, freeze_public_headers


class CapabilityError(ValueError):
    pass


class ResponseError(ValueError):
    pass


class Adapter(ABC):
    name: str
    supported_settings: frozenset[str] = frozenset()
    credential_header_names: frozenset[str] = frozenset({"authorization"})

    def auth_headers(self, secret: str) -> dict[str, str]:
        """Trusted native plugins may implement their endpoint's authentication scheme."""
        return {"Authorization": f"Bearer {secret}"} if secret else {}

    def public_headers(self, spec: ModelSpec) -> dict[str, str]:
        """Non-secret provider headers that can affect the request or response."""
        return {}

    def settings(self, spec: ModelSpec) -> dict:
        result = {}
        for setting in spec.settings:
            if setting.name not in self.supported_settings:
                raise CapabilityError(f"{self.name} does not map setting {setting.name}")
            if setting.support not in {"documented", "verified"}:
                raise CapabilityError(f"Cannot apply {setting.name}: {setting.support}")
            result[setting.name] = setting.value
        return result

    @abstractmethod
    def prepare(self, spec: ModelSpec, task: PublicTask, system: str | None) -> PreparedRequest:
        pass

    @abstractmethod
    def parse(self, response: dict) -> Generation:
        pass

    def request(self, spec: ModelSpec, path: str, body: dict) -> PreparedRequest:
        if spec.adapter != self.name:
            raise CapabilityError("Adapter identity mismatch")
        profile = spec.capability_profile
        if profile is not None:
            ModelSpec.model_validate_json(spec.model_dump_json())
            if profile.generation_path != path:
                raise CapabilityError("Capability profile generation path mismatch")
        public_headers = freeze_public_headers(self.public_headers(spec))
        secret = os.environ.get(spec.credential_env, "") if spec.credential_env else ""
        if secret and any(secret in value for value in public_headers.values()):
            raise ValueError("Credential may not enter public request headers")
        return PreparedRequest(
            adapter=self.name,
            model=spec.model,
            path=path,
            body=body,
            setting_evidence=spec.settings,
            public_headers=public_headers,
            credential_header_names=freeze_credential_header_names(
                self.credential_header_names if spec.credential_env else frozenset()
            ),
            adapter_code_digest=adapter_code_digest(self),
            capability_profile_digest=profile.digest if profile is not None else None,
        )

    def discovery_requests(self, spec: ModelSpec) -> tuple[tuple[str, str, dict | None], ...]:
        return ()


def model_metadata_path(spec: ModelSpec) -> str:
    model = spec.model.removeprefix("models/") if spec.adapter == "gemini" else spec.model
    return "/models/" + quote(model, safe="")


def messages(task: PublicTask, system: str | None) -> list[dict]:
    result = []
    if system is not None:
        result.append({"role": "system", "content": system})
    result.append({"role": "user", "content": task.prompt})
    return result


class OpenAIChat(Adapter):
    name = "openai-chat"
    supported_settings = frozenset(
        {
            "temperature",
            "top_p",
            "max_completion_tokens",
            "max_tokens",
            "seed",
            "stop",
            "reasoning_effort",
        }
    )

    def discovery_requests(self, spec):
        return (("GET", model_metadata_path(spec), None),)

    def prepare(self, spec, task, system):
        settings = self.settings(spec)
        if "max_tokens" in settings and "max_completion_tokens" in settings:
            raise CapabilityError("Specify only one token limit field for this endpoint")
        return self.request(
            spec,
            "/chat/completions",
            {
                "model": spec.model,
                "messages": messages(task, system),
                "stream": False,
                "n": 1,
                **settings,
            },
        )

    def parse(self, response):
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ResponseError("Expected exactly one response choice")
        choice = choices[0]
        message = choice.get("message", {})
        if message.get("role") != "assistant":
            raise ResponseError("Expected an assistant response message")
        text = message.get("content")
        if text is None and (message.get("refusal") or message.get("tool_calls")):
            text = ""
        if not isinstance(text, str):
            raise ResponseError("Expected text content or an explicit refusal/tool response")
        return Generation(
            text=text,
            returned_model=response.get("model"),
            response_id=response.get("id"),
            finish_reason=choice.get("finish_reason"),
            usage=response.get("usage") or {},
            metadata={
                "system_fingerprint": response.get("system_fingerprint"),
                "refusal": message.get("refusal"),
                "tool_calls": message.get("tool_calls"),
                "reasoning_content": message.get("reasoning_content"),
            },
        )


class OpenAICompatibleChat(OpenAIChat):
    """Chat-shaped endpoint with no assumed model-discovery or setting conformance."""

    name = "openai-compatible-chat"

    def discovery_requests(self, spec):
        return ()

    def settings(self, spec):
        if any(setting.support != "verified" for setting in spec.settings):
            raise CapabilityError("Compatible endpoint settings require verified support")
        return super().settings(spec)


class OpenAIResponses(Adapter):
    name = "openai-responses"
    supported_settings = frozenset({"temperature", "top_p", "max_output_tokens", "reasoning"})

    def discovery_requests(self, spec):
        return (("GET", model_metadata_path(spec), None),)

    def prepare(self, spec, task, system):
        body = {
            "model": spec.model,
            "input": task.prompt,
            "store": False,
            "stream": False,
            **self.settings(spec),
        }
        if system is not None:
            body["instructions"] = system
        return self.request(spec, "/responses", body)

    def parse(self, response):
        if response.get("status") not in {"completed", "incomplete"}:
            raise ResponseError("Response did not reach a terminal generation state")
        if not isinstance(response.get("output"), list):
            raise ResponseError("Missing output array")
        text, refusals = [], []
        for item in response["output"]:
            if item.get("type") == "message" and item.get("role") == "assistant":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        if not isinstance(part.get("text"), str):
                            raise ResponseError("Malformed output text")
                        text.append(part["text"])
                    elif part.get("type") == "refusal":
                        refusals.append(part.get("refusal"))
        return Generation(
            text="".join(text),
            returned_model=response.get("model"),
            response_id=response.get("id"),
            finish_reason=response["status"],
            usage=response.get("usage") or {},
            metadata={
                "incomplete_details": response.get("incomplete_details"),
                "refusals": refusals,
            },
        )


class Ollama(Adapter):
    name = "ollama"
    supported_settings = frozenset(
        {
            "temperature",
            "top_p",
            "top_k",
            "seed",
            "num_predict",
            "num_ctx",
            "stop",
            "think",
            "keep_alive",
        }
    )

    def prepare(self, spec, task, system):
        settings = self.settings(spec)
        body = {"model": spec.model, "messages": messages(task, system), "stream": False}
        for top_level in ("think", "keep_alive"):
            if top_level in settings:
                body[top_level] = settings.pop(top_level)
        if settings:
            body["options"] = settings
        return self.request(spec, "/api/chat", body)

    def parse(self, response):
        if response.get("done") is not True:
            raise ResponseError("Ollama response is incomplete")
        message = response.get("message", {})
        if message.get("role") != "assistant" or not isinstance(message.get("content"), str):
            raise ResponseError("Missing assistant message")
        usage = {
            k: response.get(k)
            for k in ("prompt_eval_count", "prompt_eval_cached_count", "eval_count")
        }
        metadata = {
            k: response.get(k)
            for k in (
                "created_at",
                "total_duration",
                "load_duration",
                "prompt_eval_duration",
                "eval_duration",
            )
        }
        metadata.update(
            {
                "duration_unit": "nanoseconds",
                "thinking": message.get("thinking"),
                "tool_calls": message.get("tool_calls"),
            }
        )
        return Generation(
            text=message["content"],
            returned_model=response.get("model"),
            response_id=None,
            finish_reason=response.get("done_reason"),
            usage=usage,
            metadata=metadata,
        )

    def discovery_requests(self, spec):
        return (
            ("GET", "/api/version", None),
            ("GET", "/api/tags", None),
            ("POST", "/api/show", {"model": spec.model}),
            ("GET", "/api/ps", None),
        )


class Gemini(Adapter):
    name = "gemini"
    credential_header_names = frozenset({"x-goog-api-key"})
    supported_settings = frozenset(
        {
            "temperature",
            "topP",
            "topK",
            "maxOutputTokens",
            "stopSequences",
            "seed",
            "thinkingConfig",
        }
    )

    def auth_headers(self, secret):
        return {"x-goog-api-key": secret} if secret else {}

    def discovery_requests(self, spec):
        return (("GET", model_metadata_path(spec), None),)

    def prepare(self, spec, task, system):
        body = {"contents": [{"role": "user", "parts": [{"text": task.prompt}]}]}
        settings = self.settings(spec)
        if settings:
            body["generationConfig"] = settings
        if system is not None:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        model = spec.model.removeprefix("models/")
        return self.request(spec, f"/models/{quote(model, safe='')}:generateContent", body)

    def parse(self, response):
        candidates = response.get("candidates", [])
        if not candidates and response.get("promptFeedback", {}).get("blockReason"):
            return Generation(
                text="",
                returned_model=response.get("modelVersion"),
                response_id=response.get("responseId"),
                finish_reason="prompt_blocked",
                usage=response.get("usageMetadata") or {},
                metadata={"promptFeedback": response["promptFeedback"]},
            )
        if len(candidates) != 1:
            raise ResponseError("Expected exactly one Gemini candidate")
        candidate = candidates[0]
        text, thoughts = [], []
        content = candidate.get("content")
        if content is None:
            content = {}
        if not isinstance(content, dict):
            raise ResponseError("Malformed Gemini candidate content")
        parts = content.get("parts", [])
        if not isinstance(parts, list):
            raise ResponseError("Malformed Gemini candidate parts")
        if any("text" in part for part in parts) and content.get("role") != "model":
            raise ResponseError("Expected a model role for Gemini text content")
        for part in parts:
            if "text" in part:
                if not isinstance(part["text"], str):
                    raise ResponseError("Malformed text part")
                (thoughts if part.get("thought") else text).append(part["text"])
        if not candidate.get("finishReason"):
            raise ResponseError("Missing Gemini finish reason")
        return Generation(
            text="".join(text),
            returned_model=response.get("modelVersion"),
            response_id=response.get("responseId"),
            finish_reason=candidate["finishReason"],
            usage=response.get("usageMetadata") or {},
            metadata={
                "thoughts": thoughts,
                "safetyRatings": candidate.get("safetyRatings"),
                "promptFeedback": response.get("promptFeedback"),
            },
        )


BUILTINS = {
    cls.name: cls for cls in (OpenAIChat, OpenAICompatibleChat, OpenAIResponses, Ollama, Gemini)
}


def adapter(name: str) -> Adapter:
    """Trusted installed plugins may add native interfaces without changing benchmark logic."""
    if name in BUILTINS:
        return BUILTINS[name]()
    matches = list(entry_points(group="graybench.adapters", name=name))
    if len(matches) != 1:
        raise CapabilityError(f"Expected one installed adapter named {name}; found {len(matches)}")
    instance: Any = matches[0].load()()
    if not isinstance(instance, Adapter) or instance.name != name:
        raise CapabilityError("Plugin does not implement the versioned adapter contract")
    return instance
