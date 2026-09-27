"""Verify the BB84 control ledger, declared outcomes, source and runtime bindings."""

import hashlib
import json
import sys
from pathlib import Path

from graybench.bb84_revision import PINNED_SOURCE_TASK_DIGESTS, RECIPE
from graybench.identity import identity
from graybench.provenance import source_manifest
from graybench.reference_scan import inspect_reference_scan


def main(path: Path):
    summary = inspect_reference_scan(path)
    if not summary["complete"] or summary["planned"] != 14:
        raise ValueError("BB84 evidence is incomplete")
    rows = [json.loads(line)["event"] for line in path.open(encoding="utf-8")]
    header = rows[0]
    selection = header["selection"]
    probe = Path(__file__).with_name("task63_explicit_bases_probe.py")
    if header["source"] != source_manifest():
        raise ValueError("Engine source differs from the recorded source")
    if (
        selection["recipe"] != RECIPE
        or selection["probe_sha256"] != hashlib.sha256(probe.read_bytes()).hexdigest()
    ):
        raise ValueError("Probe identity differs from the declared identity")
    cases = selection["cases"]
    if len(cases) != 14 or set(cases) != set(summary["results"]):
        raise ValueError("BB84 case roster differs from the result roster")
    if any(header["tasks"][key] != identity(record) for key, record in cases.items()):
        raise ValueError("BB84 declared case identity differs from selection metadata")
    for event in rows:
        if event["kind"] != "result":
            continue
        key = event["task_key"]
        case = cases[key]
        suite = key.split("/", 1)[0]
        if case["original_task_digest"] != PINNED_SOURCE_TASK_DIGESTS[suite]:
            raise ValueError("Original pinned task identity mismatch")
        evidence = event["evidence"]
        judgment = evidence["judgment"]
        manifest = judgment["manifest"]
        inner = judgment["inner"]
        if (
            event["outcome"] != case["expected"]
            or evidence["expected"] != case["expected"]
            or evidence["matches_expectation"] is not True
            or event["judge_digest"] != identity(manifest)
            or manifest["track"] != RECIPE
            or manifest["release_eligible"] is not False
            or manifest["pinned_source_task_digest"] != case["original_task_digest"]
            or manifest["task_digest"] != case["revised_task_digest"]
            or manifest["public_task_digest"] != case["revised_public_digest"]
            or manifest["source"] != header["source"]
            or inner["manifest"]["image"] != selection["image"]
            or inner["manifest"]["protocol"] != "upstream-graph-v4"
            or inner["public_task_digest"] != case["revised_public_digest"]
            or inner["completion_sha256"] != case["completion_sha256"]
        ):
            raise ValueError(f"BB84 result binding or outcome mismatch: {key}")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
