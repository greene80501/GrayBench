"""Trusted judge entry point. Runs in a different container from generated code."""

import json
from pathlib import Path

from circuit_wire import WireError
from oracles import bell_file_circuits, ghz_custom_layout
from value_wire import decode

ORACLES = {
    "task20-ghz-state-v1": ghz_custom_layout,
    "task82-bell-file-state-v1": bell_file_circuits,
}


def main():
    request = json.loads(Path("/judge/input.json").read_text(encoding="utf-8"))
    oracle = request["oracle"]
    try:
        value = decode(request["value"])
    except (WireError, ValueError, TypeError) as exc:
        outcome, evidence = "candidate_error", {"reason": "invalid typed value", "detail": str(exc)}
    else:
        evidence = ORACLES[oracle](value)
        if type(evidence.get("passed")) is not bool:
            raise RuntimeError("Oracle must return a Boolean judgment")
        outcome = "pass" if evidence["passed"] else "fail"
    print(
        json.dumps(
            {"protocol": 1, "oracle": oracle, "outcome": outcome, "evidence": evidence},
            allow_nan=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
