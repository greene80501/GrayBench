"""Compare first public QHE GitHub and Hugging Face task files; no model calls."""

import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

import pyarrow.parquet as parquet
from huggingface_hub import hf_hub_download

GITHUB_COMMIT = "7c84727243d7851e3f5e9f90af66ebd5d6f054de"
GITHUB_URL = (
    "https://raw.githubusercontent.com/qiskit-community/qiskit-human-eval/"
    f"{GITHUB_COMMIT}/dataset/dataset_qiskit_test_human_eval.json"
)
GITHUB_SHA256 = "496ce82372744e685ee7dd1891f58fb8e2b976b53a5a82208ae3a9994541938e"
HF_COMMIT = "025a2fb7e8192d12eba7951786929b7e73020749"
HF_SHA256 = "e6ef2b6e576cc66a77ddd4ac6b9bb39bd3cfb5f50baad1bcd414931e2b28d64d"
FIELDS = ("prompt", "canonical_solution", "test", "entry_point", "difficulty_scale")


def main():
    request = Request(GITHUB_URL, headers={"User-Agent": "GrayBench-artifact-audit/1"})
    with urlopen(request, timeout=30) as response:
        github_bytes = response.read(2 * 1024 * 1024)
    github_sha = hashlib.sha256(github_bytes).hexdigest()
    if github_sha != GITHUB_SHA256:
        raise RuntimeError("First public GitHub dataset digest changed")
    github_rows = json.loads(github_bytes)

    hf_path = Path(
        hf_hub_download(
            "Qiskit/qiskit_humaneval",
            filename="data/test-00000-of-00001.parquet",
            repo_type="dataset",
            revision=HF_COMMIT,
            token=False,
        )
    )
    hf_bytes = hf_path.read_bytes()
    hf_sha = hashlib.sha256(hf_bytes).hexdigest()
    if hf_sha != HF_SHA256:
        raise RuntimeError("Earliest public Hugging Face parquet digest changed")
    hf_rows = parquet.read_table(hf_path).to_pylist()

    github = {row["task_id"]: row for row in github_rows}
    hf = {row["task_id"]: row for row in hf_rows}
    mismatches = {
        field: sum(github[task_id][field] != hf[task_id][field] for task_id in github)
        for field in FIELDS
    } if set(github) == set(hf) else None
    if len(github_rows) != 151 or len(hf_rows) != 151 or mismatches != dict.fromkeys(FIELDS, 0):
        raise RuntimeError("First public datasets did not match in all 151 decoded records")
    print(
        json.dumps(
            {
                "kind": "graybench_earliest_public_qhe_artifacts_v1",
                "scope": "Pinned official public artifacts; not the 101-task paper dataset",
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "github_commit": GITHUB_COMMIT,
                "github_url": GITHUB_URL,
                "github_json_sha256": github_sha,
                "github_task_count": len(github_rows),
                "hugging_face_commit": HF_COMMIT,
                "hugging_face_parquet_sha256": hf_sha,
                "hugging_face_task_count": len(hf_rows),
                "same_task_ids": set(github) == set(hf),
                "decoded_field_mismatches": mismatches,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
