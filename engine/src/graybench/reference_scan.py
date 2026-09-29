"""Append-only reference calibration evidence, separate from model scoring."""

import hashlib
import json
import os
from pathlib import Path

from graybench.contracts import ExtractionPolicy, NativeExceptionPolicy
from graybench.datasets import EXTERNAL_IDS, load_suite
from graybench.fs_paths import readable_path
from graybench.identity import canonical, identity
from graybench.ledger import now
from graybench.native_cohort import Suite, freeze_native_cohort, task_key
from graybench.native_judge import NativeJudge
from graybench.provenance import source_manifest


def run_reference_scan(tasks, judge, output: Path, *, selection=None):
    tasks = tuple(tasks)
    return run_evidence_cases(
        [(f"{t.public.suite}/{t.public.task_id}", t.digest, t) for t in tasks],
        lambda task: judge.evaluate(task, task.canonical_solution),
        output,
        purpose="reference interface calibration; not model scoring",
        selection=selection,
    )


def run_native_reference_scan(
    cache: Path,
    output: Path,
    *,
    suite: Suite,
    image: str,
    extraction: ExtractionPolicy,
    exception_policy: NativeExceptionPolicy = "conservative_unattributed_v1",
    task_keys: tuple[str, ...] = (),
    include_external: bool = False,
    docker: str = "docker",
):
    """Calibrate canonical answers in a frozen native cohort, never a model score."""
    pinned = load_suite(suite, cache)
    indexed = {task_key(task): task for task in pinned}
    if len(set(task_keys)) != len(task_keys) or set(task_keys) - indexed.keys():
        raise ValueError("Native reference selection has duplicate or unknown task keys")
    if task_keys:
        chosen = set(task_keys)
        tasks = tuple(task for task in pinned if task_key(task) in chosen)
        population = "custom_development"
    elif include_external:
        tasks = pinned
        population = "custom_development"
    else:
        tasks = tuple(
            task
            for task in pinned
            if int(task.public.task_id.rsplit("/", 1)[1]) not in EXTERNAL_IDS
        )
        population = "offline_143"
    if not include_external and any(
        int(task.public.task_id.rsplit("/", 1)[1]) in EXTERNAL_IDS for task in tasks
    ):
        raise ValueError("External-service reference tasks require --include-external")
    selected = {task_key(task) for task in tasks}
    excluded = {
        key: (
            "external_service"
            if int(key.rsplit("/", 1)[1]) in EXTERNAL_IDS
            else "out_of_scope_development"
        )
        for key in indexed
        if key not in selected
    }
    cohort = freeze_native_cohort(
        tasks,
        cache=cache,
        suite=suite,
        population=population,
        image=image,
        extraction=extraction,
        exception_policy=exception_policy,
        label="native reference calibration",
        excluded=excluded,
    )
    judge = NativeJudge(cohort, tasks, cache=cache, docker=docker)
    result = run_reference_scan(
        tasks,
        judge,
        output,
        selection={
            "track": cohort.track,
            "cohort": cohort.model_dump(mode="json"),
            "cohort_digest": cohort.digest,
            "include_external": include_external,
        },
    )
    return {
        **result,
        "cohort_digest": cohort.digest,
        "exception_policy": cohort.exception_policy,
    }


def run_evidence_cases(items, evaluate, output: Path, *, purpose, selection=None):
    items = tuple(items)
    keys = [item[0] for item in items]
    if not keys or len(set(keys)) != len(keys):
        raise ValueError("Evidence scan requires unique, nonempty case keys")
    source = source_manifest()
    previous, sequence = "0" * 64, 0
    # Reserve before executing anything. Existing evidence is never overwritten or appended
    # to by a fresh scan; interrupted invocations require explicit adjudication.
    with output.open("x", encoding="utf-8", newline="\n") as stream:

        def append(event):
            nonlocal previous, sequence
            sequence += 1
            payload = {"sequence": sequence, "previous": previous, "event": event}
            digest = identity(payload)
            stream.write(canonical({**payload, "digest": digest}).decode() + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            previous = digest

        append(
            {
                "kind": "header",
                "purpose": purpose,
                "created_at": now(),
                "source": source,
                "selection": selection or {},
                "tasks": {key: digest for key, digest, _ in items},
            }
        )
        for key, _, case in items:
            if source_manifest() != source:
                raise ValueError("Reference source changed during scan")
            append({"kind": "started", "task_key": key, "at": now()})
            result = evaluate(case)
            if source_manifest() != source:
                raise ValueError("Reference source changed during invocation")
            append(
                {
                    "kind": "result",
                    "task_key": key,
                    "outcome": result.outcome,
                    "judge_digest": result.judge_digest,
                    "evidence": result.evidence,
                    "at": now(),
                }
            )
        append({"kind": "complete", "at": now()})
    return inspect_reference_scan(output)


def inspect_reference_scan(path: Path):
    path = readable_path(path)
    previous, count, header, pending, results, complete = "0" * 64, 0, None, None, {}, False
    file_digest = hashlib.sha256()
    with path.open("rb") as stream:
        while line := stream.readline(32 * 1024 * 1024 + 1):
            if len(line) > 32 * 1024 * 1024:
                raise ValueError("Reference event exceeds inspection byte limit")
            file_digest.update(line)
            if not line.endswith(b"\n"):
                raise ValueError("Truncated reference event; evidence requires adjudication")
            record = json.loads(line)
            digest = record.pop("digest")
            count += 1
            if (
                record["sequence"] != count
                or record["previous"] != previous
                or identity(record) != digest
            ):
                raise ValueError("Reference evidence chain mismatch")
            previous = digest
            event = record["event"]
            if complete:
                raise ValueError("Unexpected events after completion")
            if event["kind"] == "header" and count == 1:
                header = event
            elif header and event["kind"] == "started" and pending is None:
                pending = event["task_key"]
                if pending not in header["tasks"] or pending in results:
                    raise ValueError("Unexpected or repeated reference task")
            elif header and event["kind"] == "result" and pending == event["task_key"]:
                if event["outcome"] not in {
                    "pass",
                    "fail",
                    "unsupported",
                    "candidate_error",
                    "infrastructure_error",
                    "timeout",
                }:
                    raise ValueError("Unknown reference outcome")
                results[pending] = event["outcome"]
                pending = None
            elif (
                header
                and event["kind"] == "complete"
                and pending is None
                and set(results) == set(header["tasks"])
            ):
                complete = True
            else:
                raise ValueError("Invalid reference event sequence")
    if header is None:
        raise ValueError("Missing reference header")
    return {
        "complete": complete,
        "pending_task": pending,
        "planned": len(header["tasks"]),
        "results": results,
        "chain_head": previous,
        "purpose": header["purpose"],
        "file_sha256": file_digest.hexdigest(),
    }
