"""Local HTTP-503 retry-policy diagnostic; never a provider or model call."""

import hashlib
import json
from pathlib import Path

import httpx
from graybench.contracts import ModelSpec, PreparedRequest, RetryPolicy
from graybench.transport import Transport

from graybench.providers import Ollama


def main():
    model = ModelSpec(adapter="ollama", model="probe-model", base_url="http://localhost:11434")
    request = PreparedRequest(
        adapter="ollama",
        model="probe-model",
        path="/api/chat",
        body={
            "model": "probe-model",
            "messages": [{"role": "user", "content": "Return one answer."}],
            "stream": False,
        },
        setting_evidence=(),
    )
    responses = [
        httpx.Response(
            503,
            json={
                "accepted": True,
                "request_id": "fake-first-request",
                "output": "first synthetic answer",
            },
        ),
        httpx.Response(
            200,
            json={
                "model": "probe-model",
                "message": {"role": "assistant", "content": "second synthetic answer"},
                "done": True,
                "done_reason": "stop",
            },
        ),
    ]
    calls = []

    def handler(wire_request):
        calls.append(wire_request.content)
        return responses.pop(0)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = Transport(model, client=client)
        first = transport.generate(request, Ollama())
        second = transport.generate(request, Ollama())

    first_body = json.loads(first.evidence["response_body"])
    policy = RetryPolicy()
    if first.kind != "rejected" or first.status != 503 or first.generation is not None:
        raise RuntimeError("HTTP 503 classification changed")
    if first_body.get("accepted") is not True:
        raise RuntimeError("Synthetic accepted marker was lost")
    if 503 not in policy.statuses:
        raise RuntimeError("Default retry policy no longer includes HTTP 503")
    if second.kind != "returned" or second.generation is None:
        raise RuntimeError("Second synthetic response was not returned")
    if calls[0] != calls[1]:
        raise RuntimeError("Synthetic retry changed request body")
    print(
        json.dumps(
            {
                "kind": "graybench_http503_retry_probe_v1",
                "scope": "Local mock transport and synthetic accepted marker only",
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "first_http_status": first.status,
                "first_delivery_kind": first.kind,
                "first_response_body_recorded": first_body.get("accepted") is True,
                "first_generation_recorded": first.generation is not None,
                "default_policy_allows_503_retry": 503 in policy.statuses,
                "same_request_bytes_on_second_call": calls[0] == calls[1],
                "second_delivery_kind": second.kind,
                "second_generation_recorded": second.generation is not None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
