"""Current native scans must bind to the pinned canonical code and judge."""

import importlib.util
import json
import os
from pathlib import Path

import pytest

from graybench.identity import canonical, identity

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "docs/reliability-evidence/verify_native_reference_current.py"
ARTIFACTS = ROOT / "docs/reliability-evidence/artifacts/native-reference-current-2026-10-06-v2"


def load_script():
    spec = importlib.util.spec_from_file_location("verify_native_reference_current", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_current_native_scans_bind_all_286_canonical_answers():
    module = load_script()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    reports = module.verify_pair(ARTIFACTS, cache)
    assert [item["suite"] for item in reports] == ["normal", "hard"]
    assert all(item["planned"] == item["canonical_passes"] == 143 for item in reports)
    assert all(item["complete"] for item in reports)
    assert all(item["publication_eligible"] is False for item in reports)


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
@pytest.mark.parametrize("mutation", ("completion", "outcome"))
def test_current_native_verifier_rejects_rehashed_wrong_result(tmp_path, mutation):
    module = load_script()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    original = ARTIFACTS / "normal.jsonl"
    records = [json.loads(line) for line in original.read_bytes().splitlines()]
    changed = False
    previous = "0" * 64
    for record in records:
        event = record["event"]
        if event["kind"] == "result" and not changed:
            if mutation == "completion":
                event["evidence"]["completion_sha256"] = "0" * 64
            else:
                event["outcome"] = "fail"
            changed = True
        record["previous"] = previous
        record["digest"] = identity({k: v for k, v in record.items() if k != "digest"})
        previous = record["digest"]
    assert changed
    forged = tmp_path / "forged.jsonl"
    forged.write_bytes(b"".join(canonical(row) + b"\n" for row in records))
    with pytest.raises(ValueError, match="Native canonical"):
        module.verify_scan(forged, cache, suite="normal")
