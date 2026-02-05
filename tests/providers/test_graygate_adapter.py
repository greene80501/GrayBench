import json

import httpx

from graybench.providers.base import GenerationRequest
from graybench.providers.graygate_adapter import GrayGateAdapter


def test_graygate_uses_existing_token():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path == "/v1/runs":
            assert request.headers.get("Authorization") == "Bearer gg_live_test"
            body = json.loads(request.content)
            assert body["input"]["prompt"] == "Hello"
            return httpx.Response(200, json={"id": "run_1", "status": "queued"})
        if path == "/v1/runs/run_1/result":
            return httpx.Response(
                200,
                json={"status": "succeeded", "result": {"final_code": "print('ok')"}},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="http://testserver", transport=transport)

    adapter = GrayGateAdapter(
        api_key="gg_live_test",
        base_url="http://testserver",
        client=client,
        use_events=False,
    )

    request = GenerationRequest(prompt="Hello", model="graygate")
    result = adapter.generate(request)
    client.close()

    assert result.completion_text == "print('ok')"
    assert all(call.url.path != "/v1/tokens" for call in calls)


def test_graygate_creates_token_with_admin_secret():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path == "/v1/tokens":
            assert request.headers.get("X-Admin-Secret") == "secret"
            body = json.loads(request.content)
            assert body["label"] == "graybench"
            return httpx.Response(200, json={"token": "gg_live_test"})
        if path == "/v1/runs":
            assert request.headers.get("Authorization") == "Bearer gg_live_test"
            return httpx.Response(200, json={"id": "run_2", "status": "queued"})
        if path == "/v1/runs/run_2/result":
            return httpx.Response(
                200,
                json={"status": "succeeded", "result": {"final_code": "print('ok')"}},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="http://testserver", transport=transport)

    adapter = GrayGateAdapter(
        api_key=None,
        admin_secret="secret",
        token_label="graybench",
        base_url="http://testserver",
        client=client,
        use_events=False,
    )

    request = GenerationRequest(prompt="Hello", model="graygate")
    result = adapter.generate(request)
    client.close()

    assert result.completion_text == "print('ok')"
    assert any(call.url.path == "/v1/tokens" for call in calls)
    assert adapter._token == "gg_live_test"


def test_graygate_ignores_placeholder_api_key():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path == "/v1/tokens":
            return httpx.Response(200, json={"token": "gg_live_test"})
        if path == "/v1/runs":
            assert request.headers.get("Authorization") == "Bearer gg_live_test"
            return httpx.Response(200, json={"id": "run_4", "status": "queued"})
        if path == "/v1/runs/run_4/result":
            return httpx.Response(
                200,
                json={"status": "succeeded", "result": {"final_code": "print('ok')"}},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="http://testserver", transport=transport)

    adapter = GrayGateAdapter(
        api_key="gg_live_...",
        admin_secret="secret",
        base_url="http://testserver",
        client=client,
        use_events=False,
    )

    request = GenerationRequest(prompt="Hello", model="graygate")
    result = adapter.generate(request)
    client.close()

    assert result.completion_text == "print('ok')"
    assert any(call.url.path == "/v1/tokens" for call in calls)


def test_graygate_event_stream_triggers_result_fetch():
    calls = []

    event_stream = (
        'data: {"type":"status","run_id":"run_3","message":"Generating","step":"code","iteration":1,"ts":1}\n\n'
        'data: {"type":"final","run_id":"run_3","status":"succeeded","ts":2}\n\n'
    ).encode("utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path == "/v1/runs":
            return httpx.Response(200, json={"id": "run_3", "status": "queued"})
        if path == "/v1/runs/run_3/events":
            return httpx.Response(200, content=event_stream)
        if path == "/v1/runs/run_3/result":
            return httpx.Response(
                200,
                json={
                    "status": "succeeded",
                    "result": {
                        "final_code": "print('done')",
                        "usage": {"input_tokens": 3, "output_tokens": 5},
                    },
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="http://testserver", transport=transport)

    adapter = GrayGateAdapter(
        api_key="gg_live_test",
        base_url="http://testserver",
        client=client,
        use_events=True,
    )

    request = GenerationRequest(prompt="Hello", model="graygate")
    result = adapter.generate(request)
    client.close()

    paths = [call.url.path for call in calls]
    assert "/v1/runs/run_3/events" in paths
    assert "/v1/runs/run_3/result" in paths
    assert result.completion_text == "print('done')"
    assert result.usage.input_tokens == 3
    assert result.usage.output_tokens == 5


def test_graygate_result_409_is_treated_as_running():
    calls = {"result": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/runs":
            return httpx.Response(200, json={"id": "run_5", "status": "queued"})
        if path == "/v1/runs/run_5/result":
            calls["result"] += 1
            if calls["result"] == 1:
                return httpx.Response(409, json={"detail": "Run run_5 is still running"})
            return httpx.Response(
                200,
                json={"status": "succeeded", "result": {"final_code": "print('ok')"}},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="http://testserver", transport=transport)

    adapter = GrayGateAdapter(
        api_key="gg_live_test",
        base_url="http://testserver",
        client=client,
        use_events=False,
        poll_interval=0.1,
    )

    request = GenerationRequest(prompt="Hello", model="graygate")
    result = adapter.generate(request)
    client.close()

    assert calls["result"] >= 2
    assert result.completion_text == "print('ok')"
