"""Adapter for the separate GrayGate agent-system track (not a model baseline)."""

import os
import time
import httpx
from graybench.providers.base import (
    ProviderAdapter,
    GenerationRequest,
    GenerationResult,
    TokenUsage,
    ProviderError,
    AuthenticationError,
)

from graybench.pricing import PRICING

GRAYGATE_PRICING = PRICING["graygate"]


class GrayGateAdapter(ProviderAdapter):
    provider_name = "graygate"
    supported_models = ["graygate"]

    def __init__(
        self,
        api_key=None,
        base_url="http://localhost:8000",
        client=None,
        admin_secret=None,
        token_label="graybench",
        use_events=False,
        poll_interval=2,
        timeout=1800,
        **kwargs,
    ):
        super().__init__(api_key, base_url, **kwargs)
        self.client = client or httpx.Client(base_url=base_url, timeout=30)
        self.admin_secret = admin_secret or os.getenv("GRAYGATE_ADMIN_SECRET")
        self.token_label = token_label
        self.use_events = use_events
        self.poll_interval = poll_interval
        self.timeout = timeout
        if self.api_key and "..." in self.api_key:
            self.api_key = None

    def generate(self, request: GenerationRequest) -> GenerationResult:
        start = time.monotonic()
        if not self.api_key:
            if not self.admin_secret:
                raise AuthenticationError("GrayGate token missing", self.provider_name)
            response = self.client.post(
                "/v1/tokens",
                headers={"X-Admin-Secret": self.admin_secret},
                json={"label": self.token_label},
            )
            response.raise_for_status()
            self.api_key = response.json()["token"]
        self._token = self.api_key
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = self.client.post(
            "/v1/runs", headers=headers, json={"input": {"prompt": request.prompt}}
        )
        response.raise_for_status()
        run_id = response.json()["id"]
        if self.use_events:
            # Polling remains authoritative; events are just progress hints.
            with self.client.stream("GET", f"/v1/runs/{run_id}/events", headers=headers) as events:
                events.raise_for_status()
                for line in events.iter_lines():
                    if "run.succeeded" in line or "run.failed" in line:
                        break
        while time.monotonic() - start < self.timeout:
            response = self.client.get(f"/v1/runs/{run_id}/result", headers=headers)
            if response.status_code == 409:
                time.sleep(self.poll_interval)
                continue
            response.raise_for_status()
            raw = response.json()
            if raw.get("status") in ("failed", "cancelled"):
                raise ProviderError(f"GrayGate run {raw['status']}", self.provider_name)
            if raw.get("status") not in (None, "succeeded"):
                time.sleep(self.poll_interval)
                continue
            result = raw.get("result", raw.get("output", {}))
            usage_data = result.get("usage", {})
            usage = TokenUsage(
                **{k: usage_data[k] for k in TokenUsage.__dataclass_fields__ if k in usage_data}
            )
            raw["graybench_track"] = "agent_system"
            raw["usage_known"] = bool(usage_data)
            return GenerationResult(
                provider=self.provider_name,
                model=request.model,
                prompt_text=request.prompt,
                completion_text=result.get("final_code", result.get("code", "")),
                usage=usage,
                cost_usd=result.get("cost_usd"),
                latency_ms=(time.monotonic() - start) * 1000,
                raw_response=raw,
                request_id=run_id,
            )
        raise TimeoutError("GrayGate run exceeded polling timeout")

    def calculate_cost(self, usage, model):
        return None
