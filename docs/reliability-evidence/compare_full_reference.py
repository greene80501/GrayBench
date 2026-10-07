"""Compare two complete, source-bound offline reference scans without scoring models."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from graybench.identity import identity
from graybench.provenance import source_manifest
from graybench.reference_scan import inspect_reference_scan


def events(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line)["event"] for line in stream]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    checked = [inspect_reference_scan(path) for path in (args.before, args.after)]
    if any(not item["complete"] or item["planned"] != 286 for item in checked):
        raise ValueError("Both reference scans must contain the complete 286-case cohort")
    old_events, new_events = events(args.before), events(args.after)
    old_header, new_header = old_events[0], new_events[0]
    if any(old_header[key] != new_header[key] for key in ("tasks", "selection", "purpose")):
        raise ValueError("Reference task identity, exclusions or purpose changed")
    if new_header["source"] != source_manifest():
        raise ValueError("Current source differs from the new scan")

    def result_table(rows):
        return {row["task_key"]: row for row in rows if row["kind"] == "result"}

    old, new = result_table(old_events), result_table(new_events)
    if set(old) != set(new_header["tasks"]) or set(new) != set(old):
        raise ValueError("Reference result identities differ from the planned cohort")
    unchanged_responses = 0
    for key in sorted(old):
        first, second = old[key], new[key]
        for result in (first, second):
            if identity(result["evidence"]["manifest"]) != result["judge_digest"]:
                raise ValueError(f"Judge manifest digest mismatch: {key}")
            if not all(
                field in result["evidence"]
                for field in ("completion_sha256", "extracted_code_sha256", "public_task_digest")
            ):
                raise ValueError(f"Missing canonical response identity: {key}")
        common_conditions = (
            "image",
            "protocol",
            "judge_timeout",
            "candidate_timeout",
            "output_limit",
        )
        if any(
            first["evidence"]["manifest"].get(field) != second["evidence"]["manifest"].get(field)
            for field in common_conditions
        ):
            raise ValueError(f"Common execution condition changed: {key}")
        if any(
            first["evidence"].get(field) != second["evidence"].get(field)
            for field in ("completion_sha256", "extracted_code_sha256", "public_task_digest")
        ):
            raise ValueError(f"Canonical solution or public task changed: {key}")
        unchanged_responses += 1

    suites = {}
    for suite in ("normal", "hard"):
        prefix = suite + "/"
        suites[suite] = {
            "before": dict(Counter(v["outcome"] for k, v in old.items() if k.startswith(prefix))),
            "after": dict(Counter(v["outcome"] for k, v in new.items() if k.startswith(prefix))),
        }
    transitions = [
        {
            "task": key,
            "before": old[key]["outcome"],
            "after": new[key]["outcome"],
            "before_detail": old[key]["evidence"].get("detail"),
            "after_detail": new[key]["evidence"].get("detail"),
        }
        for key in sorted(old)
        if old[key]["outcome"] != new[key]["outcome"]
    ]
    unresolved = [
        {
            "task": key,
            "outcome": new[key]["outcome"],
            "detail": new[key]["evidence"].get("detail"),
        }
        for key in sorted(new)
        if new[key]["outcome"] != "pass"
    ]
    old_files = old_header["source"]["files"]
    new_files = new_header["source"]["files"]
    report = {
        "kind": "offline_reference_comparison_v1",
        "comparator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "purpose": "interface calibration; not model scoring or release admission",
        "before": {"path": args.before.name, **checked[0]},
        "after": {"path": args.after.name, **checked[1]},
        "same_task_identities": True,
        "same_exclusions": True,
        "same_canonical_responses": unchanged_responses,
        "same_common_execution_conditions": True,
        "after_source_matches_checkout": True,
        "selection_digest": identity(new_header["selection"]),
        "changed_source_files": sorted(
            name
            for name in old_files.keys() | new_files.keys()
            if old_files.get(name) != new_files.get(name)
        ),
        "suites": suites,
        "transitions": transitions,
        "unresolved": unresolved,
    }
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                "suites": suites,
                "transitions": len(transitions),
                "unresolved": len(unresolved),
                "after_sha256": checked[1]["file_sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
