"""Local request-provenance diagnostic with fake credentials; no provider call."""

import hashlib
import json
import os
from pathlib import Path

import httpx
from graybench.contracts import ModelSpec, PreparedRequest
from graybench.identity import canonical
from graybench.transport import Transport

from graybench.providers import OpenAIChat


def main():
    variable = "GRAYBENCH_PROBE_FAKE_TOKEN"
    original = os.environ.get(variable)
    spec = ModelSpec(
        adapter="openai-chat",
        model="probe-model",
        base_url="https://example.test",
        credential_env=variable,
    )
    request = PreparedRequest(
        adapter="openai-chat",
        model="probe-model",
        path="/v1/chat/completions",
        body={
            "model": "probe-model",
            "messages": [{"role": "user", "content": "Return one Python function."}],
        },
        setting_evidence=(),
    )
    observed = []
    try:
        for fake_token in ("probe-fake-alpha", "probe-fake-beta"):
            os.environ[variable] = fake_token
            sent = []

            def handler(wire_request, capture=sent):
                capture.append(wire_request)
                return httpx.Response(
                    200,
                    json={
                        "model": "probe-model",
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "def answer(): return 1",
                                },
                                "finish_reason": "stop",
                            }
                        ],
                    },
                )

            with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                delivery = Transport(spec, client=client).generate(request, OpenAIChat())
            if delivery.kind != "returned" or len(sent) != 1:
                raise RuntimeError("Mock exchange did not return one generation")
            if fake_token in json.dumps(delivery.evidence):
                raise RuntimeError("A fake credential leaked into durable evidence")
            observed.append(
                {
                    "prepared_request_digest": request.digest,
                    "model_spec_digest": spec.digest,
                    "wire_body_sha256": hashlib.sha256(sent[0].content).hexdigest(),
                    "body_matches_prepared_canonical": sent[0].content == canonical(request.body),
                    "auth_header_matched_fake_token": (
                        sent[0].headers.get("authorization") == f"Bearer {fake_token}"
                    ),
                    "evidence_keys": sorted(delivery.evidence),
                }
            )
    finally:
        if original is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = original

    if not all(row["body_matches_prepared_canonical"] for row in observed):
        raise RuntimeError("Wire body differed from prepared canonical body")
    if not all(row["auth_header_matched_fake_token"] for row in observed):
        raise RuntimeError("Mock endpoint did not receive both fake tokens")
    if observed[0]["prepared_request_digest"] != observed[1]["prepared_request_digest"]:
        raise RuntimeError("Prepared request digest unexpectedly changed")
    if observed[0]["model_spec_digest"] != observed[1]["model_spec_digest"]:
        raise RuntimeError("Model spec digest unexpectedly changed")
    if "request_body_sha256" in observed[0]["evidence_keys"]:
        raise RuntimeError("Transport now records a request body digest")
    if "credential_scope" in observed[0]["evidence_keys"]:
        raise RuntimeError("Transport now records credential scope")
    print(
        json.dumps(
            {
                "kind": "graybench_request_scope_probe_v1",
                "scope": "Local mock HTTP transport; fake tokens only",
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "credential_changed": True,
                "prepared_request_digest_unchanged": True,
                "model_spec_digest_unchanged": True,
                "wire_body_digest_unchanged": (
                    observed[0]["wire_body_sha256"] == observed[1]["wire_body_sha256"]
                ),
                "wire_authorization_changed": True,
                "request_body_reconstructable_from_prepared_request": True,
                "evidence_keys": observed[0]["evidence_keys"],
                "credential_scope_recorded": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
