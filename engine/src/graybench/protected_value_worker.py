"""Standalone candidate-side value worker; it has no private oracle or verdict.

The output channel is candidate-controllable. It represents a submitted answer
value only, never native-object provenance or trusted completion evidence.
"""

import contextlib
import json
import sys


def main():
    payload = json.load(sys.stdin)
    if (
        set(payload) != {"protocol", "entry_point", "code", "calls"}
        or payload.get("protocol") != "protected-value-v1"
    ):
        raise ValueError("Invalid protected value payload")
    channel = sys.stdout
    safe_dumps = json.dumps
    namespace = {"__name__": "candidate"}
    try:
        with contextlib.redirect_stdout(sys.stderr):
            exec(compile(payload["code"], "candidate.py", "exec"), namespace)
        values = []
        for call in payload["calls"]:
            with contextlib.redirect_stdout(sys.stderr):
                values.append(namespace[payload["entry_point"]](*call["args"], **call["kwargs"]))
        response = json.dumps(
            {"protocol": "protected-value-v1", "completed": True, "values": values},
            allow_nan=False,
            separators=(",", ":"),
        )
    except BaseException as exc:
        response = safe_dumps(
            {"protocol": "protected-value-v1", "completed": True, "error": type(exc).__name__},
            separators=(",", ":"),
        )
    channel.write(response)
    channel.flush()


if __name__ == "__main__":
    main()
