"""Untrusted candidate-side worker. Nothing emitted here is a verdict.

This file is copied into the disposable container with candidate.py. It receives no tests,
reference answers, ledger, provider credentials, or Docker socket. The host accepts only
bounded typed values and decides correctness independently. Numeric circuits are supported;
the remaining Qiskit interfaces still require explicit codecs.
"""

import contextlib
import json
import sys
from pathlib import Path

from value_wire import decode, encode


def main():
    channel = sys.stdout
    namespace = {"__name__": "candidate"}
    with contextlib.redirect_stdout(sys.stderr):
        prefix = Path("/input/public_prefix.py")
        if prefix.exists():
            exec(compile(prefix.read_text(encoding="utf-8"), "public_prefix.py", "exec"), namespace)
        with open("/input/candidate.py", encoding="utf-8") as source:
            exec(compile(source.read(), "candidate.py", "exec"), namespace)
    print(json.dumps({"protocol": 2, "ready": True}), file=channel, flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        try:
            with contextlib.redirect_stdout(sys.stderr):
                args, kwargs = decode(request["args"]), decode(request["kwargs"])
                result = namespace[request["entry_point"]](*args, **kwargs)
            response = {
                "protocol": 2,
                "sequence": request["sequence"],
                "value": encode(result),
                "args_after": encode(args),
                "kwargs_after": encode(kwargs),
            }
        except BaseException as exc:
            response = {
                "protocol": 2,
                "sequence": request["sequence"],
                "error": type(exc).__name__,
                "detail": str(exc)[:4096],
            }
        print(json.dumps(response, allow_nan=False), file=channel, flush=True)


if __name__ == "__main__":
    main()
