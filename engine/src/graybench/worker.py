"""Untrusted candidate-side worker. Nothing emitted here is a verdict.

This file is copied into the disposable container with candidate.py. It receives no tests,
reference answers, ledger, provider credentials, or Docker socket. The host accepts only
bounded JSON values and decides correctness independently. Rich Qiskit codecs are pending.
"""

import contextlib
import json
import math
import sys


def value(item, depth=0):
    if depth > 32:
        raise ValueError("Result nesting exceeds wire limit")
    if item is None or type(item) in (bool, str, int):
        return item
    if type(item) is float and math.isfinite(item):
        return item
    if type(item) in (list, tuple):
        return {"kind": type(item).__name__, "items": [value(x, depth + 1) for x in item]}
    if type(item) is dict:
        return {
            "kind": "dict",
            "items": [[value(k, depth + 1), value(v, depth + 1)] for k, v in item.items()],
        }
    raise TypeError("Unsupported wire value: " + type(item).__name__)


def main():
    channel = sys.stdout
    namespace = {"__name__": "candidate"}
    with contextlib.redirect_stdout(sys.stderr):
        with open("/input/candidate.py", encoding="utf-8") as source:
            exec(compile(source.read(), "candidate.py", "exec"), namespace)
    print(json.dumps({"protocol": 1, "ready": True}), file=channel, flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        try:
            with contextlib.redirect_stdout(sys.stderr):
                result = namespace[request["entry_point"]](*request["args"], **request["kwargs"])
            response = {"protocol": 1, "sequence": request["sequence"], "value": value(result)}
        except BaseException as exc:
            response = {
                "protocol": 1,
                "sequence": request["sequence"],
                "error": type(exc).__name__,
                "detail": str(exc)[:4096],
            }
        print(json.dumps(response, allow_nan=False), file=channel, flush=True)


if __name__ == "__main__":
    main()
