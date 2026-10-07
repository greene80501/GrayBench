"""Pinned prompt-rendering and task-0 answer-format diagnostic; no model calls."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.contracts import ModelSpec
from graybench.datasets import PINS, load_suite
from graybench.extraction import extract
from graybench.identity import identity
from graybench.upstream import UpstreamJudge

from graybench.providers import adapter

MODELS = {
    "openai-chat": ("probe-model", "https://example.test/v1"),
    "openai-compatible-chat": ("probe-model", "https://example.test/v1"),
    "openai-responses": ("probe-model", "https://example.test/v1"),
    "ollama": ("probe-model", "http://localhost:11434"),
    "gemini": ("probe-model", "https://example.test/v1beta"),
}


def assert_public_prompt_only(name, body, prompt):
    if name in {"openai-chat", "openai-compatible-chat", "ollama"}:
        expected = [{"role": "user", "content": prompt}]
        if body.get("messages") != expected:
            raise RuntimeError(f"{name} did not send exactly one public user prompt")
    elif name == "openai-responses":
        if body.get("input") != prompt or "instructions" in body:
            raise RuntimeError("Responses changed the public prompt or added instructions")
    elif name == "gemini":
        expected = [{"role": "user", "parts": [{"text": prompt}]}]
        if body.get("contents") != expected or "systemInstruction" in body:
            raise RuntimeError("Gemini changed the public prompt or added instructions")
    else:
        raise RuntimeError("Unknown adapter")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    suites = {name: load_suite(name, args.cache) for name in ("normal", "hard")}
    rendering = {}
    for name, (model, base_url) in MODELS.items():
        spec = ModelSpec(adapter=name, model=model, base_url=base_url)
        provider = adapter(name)
        request_ids = []
        for suite, tasks in suites.items():
            for task in tasks:
                request = provider.prepare(spec, task.public, None)
                assert_public_prompt_only(name, request.body, task.public.prompt)
                request_ids.append((suite, task.public.task_id, request.digest))
        rendering[name] = {
            "request_count": len(request_ids),
            "request_manifest_digest": identity(request_ids),
            "system_prompt": None,
            "all_public_prompts_exact": True,
        }

    task = next(
        item for item in suites["normal"] if item.public.task_id == "qiskitHumanEval/0"
    )
    completions = {
        "literal_suffix": task.canonical_solution,
        "complete_function": (
            "def create_quantum_circuit(n_qubits):\n"
            "    return QuantumCircuit(n_qubits)\n"
        ),
    }
    judge = UpstreamJudge(image=args.image)
    answer_formats = []
    for name, completion in completions.items():
        extracted = extract(completion, task.public)
        result = judge.evaluate(task, completion)
        if extracted.error or result.outcome != "pass":
            raise RuntimeError(f"Unexpected extraction/judgment for {name}")
        answer_formats.append(
            {
                "name": name,
                "completion_sha256": hashlib.sha256(completion.encode()).hexdigest(),
                "extraction_method": extracted.method,
                "public_prefix_sha256": hashlib.sha256(
                    extracted.public_prefix.encode()
                ).hexdigest(),
                "assembled_code_sha256": hashlib.sha256(extracted.code.encode()).hexdigest(),
                "outcome": result.outcome,
                "judge_digest": result.judge_digest,
            }
        )
    if [row["extraction_method"] for row in answer_formats] != ["raw+prompt", "raw"]:
        raise RuntimeError("Current extraction condition changed")
    print(
        json.dumps(
            {
                "kind": "graybench_prompt_format_probe_v1",
                "scope": "Local adapter rendering and pinned protected-bridge diagnostic",
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "suite_task_counts": {name: len(tasks) for name, tasks in suites.items()},
                "rendering": rendering,
                "task0_digest": task.digest,
                "current_extraction_policy": "raw_or_single_python_fence_v1",
                "answer_formats": answer_formats,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
