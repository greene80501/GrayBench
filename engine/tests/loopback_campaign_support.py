"""Test-only HTTP fixtures and trusted authored execution; never a model service."""

import gzip
import hashlib
import json
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from graybench.protected_value_runner import (
    WORKER,
    ValueExecution,
    parse_value_response,
    value_payload,
)

SECRET = "loopback-fixture-credential-not-a-provider-key"
IMAGE = "sha256:" + "f" * 64  # Synthetic fixture identity; no image is executed.


def answer(suite, correct):
    body = (
        "    import math\n    r = 1 / math.sqrt(2)\n    return [[r,0],[0,0],[0,0],[r,0]]\n"
        if correct
        else "    return [[1,0],[0,0],[0,0],[0,0]]\n"
    )
    return "\n" + body if suite == "normal" else "def bell_amplitudes():\n" + body


class AuthoredRunner:
    image = IMAGE

    def manifest(self, contract):
        return {
            "scope": "test-only trusted authored subprocess; no container qualification",
            "contract_digest": contract.digest,
            "worker_sha256": hashlib.sha256(WORKER.read_bytes()).hexdigest(),
            "fixture_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }

    def execute(self, contract, completion, calls):
        allowed = {
            answer(suite, correct) for suite in ("normal", "hard") for correct in (True, False)
        }
        if completion not in allowed:
            raise ValueError("The local fixture executor refuses all other code")
        response = subprocess.run(
            [sys.executable, str(WORKER)],
            input=json.dumps(value_payload(contract, completion, calls)).encode(),
            capture_output=True,
            timeout=10,
            check=True,
        ).stdout
        if len(response) > 1024 * 1024:
            raise ValueError("Authored response exceeds the output allowance")
        values = parse_value_response(response, contract, expected_count=len(calls))
        return ValueExecution(
            "returned",
            values,
            {
                "scope": "trusted authored fixture",
                "response_sha256": hashlib.sha256(response).hexdigest(),
            },
        )


def provider_response(name, completion):
    if name == "ollama":
        return {
            "model": "fixture",
            "done": True,
            "done_reason": "stop",
            "message": {"role": "assistant", "content": completion},
        }
    if name == "gemini":
        return {
            "modelVersion": "fixture",
            "responseId": "fixture-response",
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"role": "model", "parts": [{"text": completion}]},
                }
            ],
        }
    if name == "openai-responses":
        return {
            "model": "fixture",
            "id": "fixture-response",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": completion}],
                }
            ],
        }
    return {
        "model": "fixture",
        "id": "fixture-response",
        "choices": [
            {"finish_reason": "stop", "message": {"role": "assistant", "content": completion}}
        ],
    }


@contextmanager
def endpoint(name, suite, scenario):
    records = []
    generation_path = {
        "ollama": "/api/chat",
        "gemini": "/models/fixture:generateContent",
        "openai-responses": "/responses",
    }.get(name, "/chat/completions")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            credential = "x-goog-api-key" if name == "gemini" else "Authorization"
            expected = SECRET if name == "gemini" else "Bearer " + SECRET
            record = {
                "method": self.command,
                "path": self.path,
                "body": body,
                "auth_ok": self.headers.get(credential) == expected,
            }
            records.append(record)
            is_generation = self.path == generation_path
            status = 200
            if is_generation:
                number = sum(r["path"] == generation_path for r in records)
                payload = provider_response(name, answer(suite, number == 1))
                if scenario == "server-error":
                    status, payload = 503, {"error": "fixture server error"}
                elif scenario == "redirect":
                    status, payload = 302, {"error": "fixture redirect"}
            else:
                metadata = {
                    "/api/version": {"version": "fixture-1"},
                    "/api/tags": {"models": [{"name": "fixture", "digest": "a" * 64}]},
                    "/api/show": {"model_info": {"architecture": "fixture"}},
                    "/api/ps": {"models": []},
                    "/models/fixture": {
                        "name": "models/fixture",
                        "version": "fixture",
                        "inputTokenLimit": 1024,
                        "outputTokenLimit": 1024,
                        "supportedGenerationMethods": ["generateContent"],
                    }
                    if name == "gemini"
                    else {"id": "fixture", "object": "model", "created": 0, "owned_by": "fixture"},
                }
                payload = metadata.get(self.path, {"error": "unexpected route"})
                if self.path not in metadata:
                    status = 404
            raw = json.dumps(payload, separators=(",", ":")).encode()
            wire = gzip.compress(raw, mtime=0) if is_generation else raw
            record.update({"wire": wire, "decoded": raw, "status": status})
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if status == 302:
                self.send_header("Location", "/forbidden")
            if is_generation:
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                for offset in range(0, len(wire), 11):
                    chunk = wire[offset : offset + 11]
                    self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                self.wfile.write(b"0\r\n\r\n")
            else:
                self.send_header("Content-Length", str(len(wire)))
                self.end_headers()
                self.wfile.write(wire)
            self.wfile.flush()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", generation_path, records
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()
