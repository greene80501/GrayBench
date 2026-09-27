"""Verify complete task-63 canonical repeats without promoting their outcomes."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from graybench.datasets import load_suite
from graybench.identity import identity
from graybench.provenance import source_manifest
from graybench.reference_scan import inspect_reference_scan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    verified = inspect_reference_scan(args.input)
    with args.input.open(encoding="utf-8") as stream:
        events = [json.loads(line)["event"] for line in stream]
    header = events[0]
    selection = header["selection"]
    count = selection["repeats_per_suite"]
    if not verified["complete"] or verified["planned"] != 2 * count:
        raise ValueError("Task-63 repeat is incomplete")
    if header["source"] != source_manifest():
        raise ValueError("Current source differs from repeat source")
    probe = Path(__file__).with_name("task63_reference_repeat.py")
    if selection["probe_sha256"] != hashlib.sha256(probe.read_bytes()).hexdigest():
        raise ValueError("Repeat probe differs from the recorded code")
    tasks = {
        task.public.suite: task
        for suite in ("normal", "hard")
        for task in load_suite(suite, args.cache)
        if task.public.family_id == "qhe/63"
    }
    if set(tasks) != {"normal", "hard"}:
        raise ValueError("Missing pinned task-63 variant")
    results = {event["task_key"]: event for event in events if event["kind"] == "result"}
    counts = {}
    for suite, task in tasks.items():
        outcomes = []
        digests = set()
        for number in range(1, count + 1):
            key = f"{suite}/qiskitHumanEval/63/repeat-{number:02d}"
            expected = identity(
                {"task": task.digest, "completion": task.canonical_solution, "repeat": number}
            )
            if header["tasks"].get(key) != expected or key not in results:
                raise ValueError(f"Missing or changed planned repeat: {key}")
            event = results[key]
            evidence = event["evidence"]
            if identity(evidence["manifest"]) != event["judge_digest"]:
                raise ValueError(f"Judge identity mismatch: {key}")
            if evidence["public_task_digest"] != task.public.digest:
                raise ValueError(f"Public task changed: {key}")
            digests.add((evidence["completion_sha256"], evidence["extracted_code_sha256"]))
            if event["outcome"] not in ("pass", "fail"):
                raise ValueError(f"Non-oracle outcome in repeat: {key}")
            outcomes.append(event["outcome"])
        if len(digests) != 1:
            raise ValueError(f"Canonical completion changed across {suite} repeats")
        counts[suite] = dict(Counter(outcomes))
    if set(results) != set(header["tasks"]):
        raise ValueError("Unexpected repeat result")
    summary = {
        "kind": "task63_canonical_repeat_verification_v1",
        "purpose": "stochastic oracle diagnostic; not model scoring",
        "evidence": verified,
        "source_matches_checkout": True,
        "probe_sha256": selection["probe_sha256"],
        "repeats_per_suite": count,
        "same_canonical_completion_within_each_suite": True,
        "counts": counts,
    }
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"complete": verified["complete"], "counts": counts}))


if __name__ == "__main__":
    main()
