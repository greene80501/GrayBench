"""Verify native task-62 fixed-circuit counterexample against pinned tasks."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from graybench.datasets import EXTERNAL_IDS, load_suite
from graybench.identity import canonical, identity
from graybench.native_assembly import native_payload
from graybench.native_cohort import freeze_native_cohort, task_key
from graybench.native_judge import NativeJudge
from graybench.provenance import source_manifest
from graybench.reference_scan import inspect_reference_scan
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

HERE = Path(__file__).resolve().parent
PROBE = HERE.parents[1] / "task62_fixed_oracle_probe.py"
SOURCE_DIGEST = "be85d5ff6a9c61b3777b6083b183f5f3411cb06b4d484ebcabc9f28b22593cc0"
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path, help="Local SHA-256-pinned QHE dataset cache")
    args = parser.parse_args()
    manifest = json.loads((HERE / "manifest.json").read_bytes())
    require(manifest["schema_version"] == "1", "Unexpected manifest schema")
    require(
        manifest["source_revision"] == "54be7e1f4bb94d0adebcf1d675de34a70640668f",
        "Unexpected source revision",
    )
    require(manifest["source_digest"] == SOURCE_DIGEST, "Unexpected source digest")
    require(
        {item["path"] for item in manifest["files"]}
        == {"control.jsonl", "../../task62_fixed_oracle_probe.py"},
        "Unexpected bundle files",
    )
    require(len(manifest["files"]) == 2, "Unexpected manifest entry count")
    for item in manifest["files"]:
        raw = (HERE / item["path"]).read_bytes()
        require(len(raw) == item["bytes"], f"Byte count differs: {item['path']}")
        require(
            hashlib.sha256(raw).hexdigest() == item["sha256"], f"SHA-256 differs: {item['path']}"
        )
    spec = importlib.util.spec_from_file_location("task62_probe", PROBE)
    require(spec is not None and spec.loader is not None, "Probe source cannot be loaded")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)

    path = HERE / "control.jsonl"
    inspected = inspect_reference_scan(path)
    require(inspected["complete"] and inspected["planned"] == 4, "Incomplete control chain")
    require(inspected["file_sha256"] == manifest["files"][0]["sha256"], "Log hash differs")
    require(set(inspected["results"].values()) == {"pass"}, "A control did not pass")
    rows = [json.loads(line)["event"] for line in path.open(encoding="utf-8")]
    header = rows[0]
    require(header["source"] == source_manifest(), "Current engine differs from captured source")
    require(header["source"]["digest"] == SOURCE_DIGEST, "Captured engine digest differs")
    require(
        header["selection"]["probe_sha256"] == hashlib.sha256(PROBE.read_bytes()).hexdigest(),
        "Probe hash differs",
    )
    require(header["selection"]["image"] == IMAGE, "Runtime image differs")
    require(
        header["purpose"] == "native task-62 oracle counterexample; not model scoring or admission",
        "Evidence purpose differs",
    )
    expected = {}
    for suite in ("normal", "hard"):
        pinned = load_suite(suite, args.cache)
        task = next(task for task in pinned if task.public.task_id == "qiskitHumanEval/62")
        extraction = (
            "exact_prompt_suffix_v1" if suite == "normal" else "raw_or_single_python_fence_v1"
        )
        cohort = freeze_native_cohort(
            (task,),
            cache=args.cache,
            suite=suite,
            population="custom_development",
            image=IMAGE,
            extraction=extraction,
            label="task 62 fixed-input oracle diagnostic",
            excluded={
                task_key(other): (
                    "external_service"
                    if int(other.public.task_id.rsplit("/", 1)[1]) in EXTERNAL_IDS
                    else "out_of_scope_development"
                )
                for other in pinned
                if other != task
            },
        )
        require(header["selection"]["cohorts"][suite] == cohort.digest, "Cohort differs")
        judge = NativeJudge(cohort, (task,), cache=args.cache)
        _, judge_manifest = judge.configuration(task)
        for label, completion in (
            ("canonical", task.canonical_solution),
            ("fixed-input-ignoring", probe.fixed_answer(suite)),
        ):
            key = f"{task_key(task)}/{label}"
            expected[key] = (
                task.digest,
                judge_manifest,
                native_payload(task, completion, extraction),
            )
    require(
        header["tasks"] == {key: value[0] for key, value in expected.items()}, "Task digests differ"
    )
    zero_probabilities = {}
    for event in rows:
        if event["kind"] != "result":
            continue
        key = event["task_key"]
        require(key in expected and event["outcome"] == "pass", f"Control differs: {key}")
        _, judge_manifest, payload = expected[key]
        evidence = event["evidence"]
        require(
            evidence["manifest"] == judge_manifest
            and event["judge_digest"] == identity(judge_manifest)
            and evidence["completion_sha256"] == payload["completion_sha256"]
            and evidence["code_sha256"] == payload["code_sha256"]
            and evidence["extraction_method"] == payload["extraction_method"],
            f"Control provenance differs: {key}",
        )
        worker = {"completed": True, "phase": "test", "status": "pass"}
        result_bytes = canonical(worker)
        require(
            evidence["exit_code"] == 0
            and evidence["worker_result"] == worker
            and evidence["result_artifact"]
            == {
                "capture": "isolated-ephemeral-host-bind-v1",
                "name": "result.json",
                "sha256": hashlib.sha256(result_bytes).hexdigest(),
                "size": len(result_bytes),
            },
            f"Worker completion differs: {key}",
        )
        namespace = {}
        exec(payload["code"], namespace)
        circuit = namespace["bb84_senders_circuit"]([0] * 5, [0] * 5)
        require(isinstance(circuit, QuantumCircuit), f"All-zero output is not a circuit: {key}")
        zero_probabilities[key] = float(Statevector.from_instruction(circuit).probabilities()[0])
    require(
        all(
            probability == (1.0 if key.endswith("/canonical") else 0.0)
            for key, probability in zero_probabilities.items()
        )
        and len(zero_probabilities) == 4,
        "All-zero valid-input counterexample failed",
    )
    print("Four native passes verified; fixed-input mutant is wrong on all-zero inputs")


if __name__ == "__main__":
    main()
