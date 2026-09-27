"""Strict, content-pinned Qiskit HumanEval import with separate public and judge records."""

import ast
import hashlib
import re
from pathlib import Path

from pydantic import Field

from graybench.contracts import Contract, PublicTask
from graybench.identity import identity

PINS = {
    "normal": {
        "repo": "Qiskit/qiskit_humaneval",
        "revision": "a0066805f7a15cb48e9d0cface2210056185be6d",
        "sha256": "1fb8d49195a08c023cc93b489b5d2ae0c2118047a5306f6fd374e3b4e95a94e6",
    },
    "hard": {
        "repo": "Qiskit/qiskit_humaneval_hard",
        "revision": "315e167a479d5c546565d7f9f8c63a644c84cb50",
        "sha256": "3809e1faa0d9bd3b2a366f2c25b36084705602d91318f30acffbd7e0b76df8c9",
    },
}
# Explicit provisional inventory, not discovered by whether a candidate happens to pass.
EXTERNAL_IDS = frozenset({43, 97, 98, 122, 129, 133, 134, 146})
KNOWN_FINDINGS = {
    0: ["Upstream accepts a constant three-qubit circuit that ignores the requested size"],
    1: ["Upstream accepts fabricated balanced counts, negative counts and fractional counts"],
    2: ["Upstream trusts the returned object's equiv method and accepts wrong state amplitudes"],
    3: ["Upstream accepts a blank figure and leaves measurement coverage ambiguous"],
    9: ["Upstream accepts an RX-only non-entangling ansatz"],
    14: ["Upstream accepts two shots instead of the explicitly requested 100"],
    20: ["Empty circuit with correct layout accepted by upstream oracle"],
    26: ["Upstream accepts a Bell pair on the wrong qubits and requires undisclosed measurement"],
    32: ["Oracle depends on an undisclosed signed observable coefficient"],
    35: ["Oracle depends on undisclosed variational parameter preparation"],
    37: ["Upstream accepts fabricated primitive data with an invalid bit string"],
    46: ["Upstream accepts a fixed-width identity function that ignores width and seed"],
    63: ["Private RNG state is unavailable to the candidate; canonical results vary across runs"],
    82: ["Protected upstream bridge cannot see bell.qpy across the candidate/judge boundary"],
    86: ["Upstream accepts identity blocks without the requested CX-chain behavior"],
    109: ["Upstream accepts a fixed physical state despite its parameter-variation request"],
    113: ["Upstream accepts a constant dictionary in place of computed PropertySet metrics"],
    114: ["Upstream accepts the wrong physical qubit when the coupling-map node count matches"],
    116: ["Upstream accepts a fixed circuit that ignores Hamiltonian and time inputs"],
    120: ["Upstream accepts a fixed circuit that ignores diagonal-phase inputs"],
    141: ["Upstream accepts zero SparsePauliOp objects as Pauli anticommutators"],
}


class JudgeTask(Contract):
    public: PublicTask
    canonical_solution: str = Field(min_length=1)
    upstream_test: str = Field(min_length=1)
    upstream_difficulty: str


def load_suite(suite: str, cache: Path, *, download: bool = False) -> tuple[JudgeTask, ...]:
    if suite not in PINS:
        raise ValueError("Expected normal or hard")
    pin = PINS[suite]
    path = cache / suite / pin["revision"][:12] / "data/test-00000-of-00001.parquet"
    if not path.exists() and download:
        from huggingface_hub import hf_hub_download

        path = Path(
            hf_hub_download(
                repo_id=pin["repo"],
                repo_type="dataset",
                revision=pin["revision"],
                filename="data/test-00000-of-00001.parquet",
                local_dir=cache / suite / pin["revision"][:12],
            )
        )
    if hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
        raise ValueError("Pinned dataset file digest mismatch")
    import pyarrow.parquet as parquet

    rows = parquet.read_table(path).to_pylist()
    return parse_rows(suite, rows)


def parse_rows(suite: str, rows: list[dict]) -> tuple[JudgeTask, ...]:
    result = []
    for row in rows:
        if set(row) != {
            "task_id",
            "prompt",
            "entry_point",
            "test",
            "canonical_solution",
            "difficulty_scale",
        }:
            raise ValueError("Unexpected upstream schema; migrate explicitly")
        if not all(type(v) is str and v.strip() for v in row.values()):
            raise ValueError("All pinned task fields must be nonempty strings")
        match = re.fullmatch(r"qiskitHumanEval/(\d+)", row["task_id"])
        if not match:
            raise ValueError("Unexpected upstream task identity")
        public = PublicTask(
            suite=suite,
            task_id=row["task_id"],
            family_id=f"qhe/{int(match[1])}",
            prompt=row["prompt"],
            entry_point=row["entry_point"],
            prompt_format="function_completion" if suite == "normal" else "standalone_function",
        )
        result.append(
            JudgeTask(
                public=public,
                canonical_solution=row["canonical_solution"],
                upstream_test=row["test"],
                upstream_difficulty=row["difficulty_scale"],
            )
        )
    if {r.public.task_id for r in result} != {f"qiskitHumanEval/{i}" for i in range(151)}:
        raise ValueError("Pinned suite must contain exactly task IDs 0 through 150")
    if len(result) != 151:
        raise ValueError("Duplicate task IDs")
    return tuple(result)


def inventory(tasks: tuple[JudgeTask, ...]) -> dict:
    cards = []
    for task in tasks:
        tree = ast.parse(task.upstream_test)
        number = int(task.public.task_id.split("/")[-1])
        cards.append(
            {
                "task_key": f"{task.public.suite}/{task.public.task_id}",
                "family_id": task.public.family_id,
                "public_digest": task.public.digest,
                "judge_record_digest": task.digest,
                "upstream_difficulty": task.upstream_difficulty,
                "external_service": number in EXTERNAL_IDS,
                "assertion_sites": sum(isinstance(n, ast.Assert) for n in ast.walk(tree)),
                "specification_review": "pending",
                "oracle_review": "pending",
                "wire_interface_review": "pending",
                "independent_alternatives": [],
                "mutation_results": [],
                "release_eligible": False,
                "known_findings": KNOWN_FINDINGS.get(number, []),
            }
        )
    return {
        "schema_version": "3.0",
        "dataset_digest": identity([t.digest for t in tasks]),
        "pins": PINS,
        "task_count": len(tasks),
        "cards": cards,
        "release_ready": False,
    }
