"""Evidence verifier must bind the declared case digests to case metadata."""

import json
from pathlib import Path

import pytest
from graybench.identity import canonical, identity
from verify_task63_explicit_bases import main


def test_declared_case_identity_is_enforced(tmp_path):
    source = Path(__file__).with_name("GrayBench-v4-task63-explicit-bases-controls.jsonl")
    records = [json.loads(line) for line in source.open(encoding="utf-8")]
    first = next(iter(records[0]["event"]["tasks"]))
    records[0]["event"]["tasks"][first] = "f" * 64
    altered = tmp_path / "altered-ledger.jsonl"
    previous = "0" * 64
    with altered.open("wb") as stream:
        for sequence, record in enumerate(records, 1):
            payload = {"sequence": sequence, "previous": previous, "event": record["event"]}
            previous = identity(payload)
            stream.write(canonical({**payload, "digest": previous}) + b"\n")
    with pytest.raises(ValueError, match="case identity"):
        main(altered)
