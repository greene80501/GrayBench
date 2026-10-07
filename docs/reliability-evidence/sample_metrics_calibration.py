"""Calibrate exact opportunity metrics against subsets and a pinned numerical reference."""

import argparse
import ast
import hashlib
import itertools
import json
import platform
from fractions import Fraction
from importlib.metadata import version
from pathlib import Path
from typing import Union

import numpy as np

from graybench.binary_comparison import load_binary_json, probability_record
from graybench.identity import canonical
from graybench.provenance import source_manifest
from graybench.sample_metrics import pass_at_k_fraction

REFERENCE_COMMIT = "6d43fb980f9fee3c892a914eda09951f772ad10d"
REFERENCE_BLOB = "9ce96dfc4cb4c553e41e4530b710fdf94d4442f5"
REFERENCE_SHA256 = "e926d5e9b8f1ec040096cd5952e8cf79f8dc0b7fb80ba6667ce604ffea0397bc"


def numeric_reference(path):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Exact reviewed HumanEval source required before numerical execution")
    text = data.decode("utf-8")
    definitions = [
        node
        for node in ast.parse(text).body
        if isinstance(node, ast.FunctionDef) and node.name == "estimate_pass_at_k"
    ]
    if len(definitions) != 1:
        raise ValueError("Expected one fixed numerical reference function")
    function = definitions[0]
    scope = {"np": np, "itertools": itertools, "List": list, "Union": Union}
    # Only the reviewed numerical function is compiled. Module imports, the
    # evaluator and candidate execution machinery never execute here.
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), "fixed-numerical-reference", "exec"),
        scope,
    )
    return scope["estimate_pass_at_k"], hashlib.sha256(
        ast.get_source_segment(text, function).encode()
    ).hexdigest()


def subset_reference():
    result = {}
    for n in range(1, 13):
        for c in range(n + 1):
            totals = [0] * (n + 1)
            successes = [0] * (n + 1)
            pass_mask = (1 << c) - 1
            for mask in range(1, 1 << n):
                k = mask.bit_count()
                totals[k] += 1
                successes[k] += bool(mask & pass_mask)
            for k in range(1, n + 1):
                result[(n, c, k)] = Fraction(successes[k], totals[k])
    return result


def build(reference_file):
    reference, function_sha = numeric_reference(reference_file)
    subsets = subset_reference()
    observations = []
    subset_matches = 0
    for n in (*range(1, 21), 30, 100, 1000):
        cs = list(range(n + 1)) if n <= 20 else [0, 1, n // 2, n - 1, n]
        ks = (
            list(range(1, n + 1))
            if n <= 20
            else sorted({k for k in (1, 2, 5, 10, 20, 50, 100, n) if k <= n})
        )
        for k in ks:
            expected = reference(n, np.array(cs, dtype=np.int64), k)
            if expected.shape != (len(cs),):
                raise ValueError("Unexpected numerical reference shape")
            for c, original in zip(cs, expected, strict=True):
                actual = pass_at_k_fraction(n, c, k)
                error = abs(float(actual) - float(original))
                if not np.isfinite(original) or error > 1e-13:
                    raise ValueError("Exact estimator differs from fixed HumanEval tolerance")
                subset = subsets.get((n, c, k))
                if subset is not None:
                    if subset != actual:
                        raise ValueError("Exact fraction differs from enumerated candidate subsets")
                    subset_matches += 1
                if k == 1 and actual != Fraction(c, n):
                    raise ValueError("Pass@1 does not equal the single-answer success fraction")
                observations.append(
                    {
                        "n": n,
                        "c": c,
                        "k": k,
                        "exact_probability": probability_record(actual),
                        "humaneval_probability": float(original),
                        "absolute_float_error": error,
                        "enumerated_subset_match": True if subset is not None else None,
                    }
                )
    if subset_matches != len(subsets):
        raise ValueError("Every predeclared enumerated subset case must be checked")
    lock = Path(__file__).resolve().parents[2] / "engine" / "uv.lock"
    return {
        "kind": "graybench_sample_metrics_calibration_v1",
        "scope": "exact arithmetic and a fixed numeric reference; no campaign/candidate execution",
        "publication_eligible": False,
        "independent_task_review": False,
        "engine_source": source_manifest(),
        "engine_lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reference": {
            "repository": "https://github.com/openai/human-eval",
            "commit": REFERENCE_COMMIT,
            "path": "human_eval/evaluation.py",
            "git_blob": REFERENCE_BLOB,
            "file_sha256": REFERENCE_SHA256,
            "function": "estimate_pass_at_k",
            "function_sha256": function_sha,
            "executed_scope": "only reviewed numeric function; no module/evaluator imports",
        },
        "environment": {"python": platform.python_version(), "numpy": version("numpy")},
        "human_eval_case_count": len(observations),
        "enumerated_subset_case_count": subset_matches,
        "absolute_float_tolerance": 1e-13,
        "max_absolute_float_error": max(row["absolute_float_error"] for row in observations),
        "cases": observations,
        "limitations": [
            "Float agreement alone does not certify probabilities extremely close to zero or one.",
            "Subset enumeration covers n=1..12; larger cases use the fixed float reference.",
            "Arithmetic consistency does not establish iid sampling, fair settings "
            "or task validity.",
            "No task admission, isolated runtime, provider behavior or model score is qualified.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build(args.reference)
    if args.check:
        if canonical(load_binary_json(args.output.read_bytes())) != canonical(report):
            raise ValueError("Saved sample-metric calibration differs from exact recreation")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "humaneval_cases": report["human_eval_case_count"],
                "subset_cases": report["enumerated_subset_case_count"],
                "max_float_error": report["max_absolute_float_error"],
                "publication_eligible": False,
                "recreated": args.check,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
