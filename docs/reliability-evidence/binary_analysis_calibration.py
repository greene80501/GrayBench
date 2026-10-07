"""Recreate exact arithmetic calibration; no model, network or container execution."""

import argparse
import hashlib
import itertools
import json
import platform
from fractions import Fraction
from importlib.metadata import version
from pathlib import Path

from scipy.stats import binomtest

from graybench.binary_comparison import (
    exact_mcnemar,
    holm_adjust,
    load_binary_json,
    probability_record,
)
from graybench.identity import canonical
from graybench.provenance import source_manifest


def closed_bonferroni(probabilities):
    """Enumerate all intersection hypotheses, separately from the step-down code."""
    return {
        key: max(
            min(Fraction(1), len(subset) * min(probabilities[k] for k in subset))
            for size in range(1, len(probabilities) + 1)
            for subset in itertools.combinations(probabilities, size)
            if key in subset
        )
        for key in probabilities
    }


def build():
    grid = []
    counts = [(left, right) for left in range(31) for right in range(31)]
    counts += [(100, 1), (500, 5), (2000, 0), (10000, 0), (5000, 5000), (5001, 4999)]
    for left, right in counts:
        expected = 1.0 if left + right == 0 else binomtest(left, left + right, 0.5).pvalue
        actual = exact_mcnemar(left, right)
        error = abs(float(actual) - float(expected))
        if error > 1e-14:
            raise ValueError("Exact tail differs from the declared SciPy tolerance")
        if exact_mcnemar(right, left) != actual:
            raise ValueError("Side reversal changed the two-sided probability")
        if min(left, right) == 0 and left + right > 0:
            if actual != Fraction(1, 2 ** (left + right - 1)):
                raise ValueError("One-sided discordance differs from the exact power-of-two tail")
        grid.append(
            {
                "left_only": left,
                "right_only": right,
                "exact_probability": probability_record(actual),
                "scipy_probability": float(expected),
                "absolute_float_error": error,
            }
        )
    probabilities = [
        Fraction(0),
        Fraction(1, 100),
        Fraction(1, 40),
        Fraction(1, 20),
        Fraction(1, 2),
        Fraction(1),
    ]
    holm = []
    permutations = 0
    for values in itertools.product(probabilities, repeat=3):
        named = dict(zip(("a", "b", "c"), values, strict=True))
        expected = closed_bonferroni(named)
        actual = holm_adjust(named)
        if actual != expected:
            raise ValueError("Step-down adjustment differs from closed intersection enumeration")
        for keys in itertools.permutations(named):
            if holm_adjust({key: named[key] for key in keys}) != expected:
                raise ValueError("Input order changed adjusted probabilities")
            permutations += 1
        holm.append(
            {
                "raw": {key: probability_record(value) for key, value in named.items()},
                "adjusted": {key: probability_record(value) for key, value in actual.items()},
                "closed_intersection_match": True,
            }
        )
    tiny = exact_mcnemar(2000, 0)
    tiny_adjusted = holm_adjust({"a": tiny, "b": tiny})
    if tiny_adjusted != {"a": 2 * tiny, "b": 2 * tiny}:
        raise ValueError("Adjustment lost an underflowing exact probability")
    threshold = Fraction("0.05")
    boundary = holm_adjust({"a": threshold})["a"]
    if boundary != threshold or not boundary <= threshold:
        raise ValueError("Inclusive exact threshold boundary failed")
    lock = Path(__file__).resolve().parents[2] / "engine" / "uv.lock"
    return {
        "kind": "graybench_binary_analysis_calibration_v1",
        "scope": "deterministic arithmetic only; assumptions and campaign validity not established",
        "publication_eligible": False,
        "independent_task_review": False,
        "engine_source": source_manifest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "engine_lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
        "environment": {
            "python": platform.python_version(),
            "scipy": version("scipy"),
            "numpy": version("numpy"),
        },
        "mcnemar": {
            "grid_case_count": 961,
            "boundary_case_count": 6,
            "scipy_absolute_tolerance": 1e-14,
            "max_absolute_float_error": max(row["absolute_float_error"] for row in grid),
            "cases": grid,
        },
        "holm": {
            "three_contrast_grid_count": len(holm),
            "permutation_check_count": permutations,
            "closed_intersection_cases": holm,
            "underflow_raw": probability_record(tiny),
            "underflow_adjusted": {
                key: probability_record(value) for key, value in tiny_adjusted.items()
            },
            "inclusive_threshold": probability_record(boundary),
        },
        "limitations": [
            "SciPy float zero does not validate extreme rational tails; "
            "those also use exact power-of-two checks.",
            "Closed intersection enumeration checks this finite grid, not every possible input.",
            "No independent-family assumption, task oracle, provider or runtime is qualified.",
            "Synthetic ledger/CLI behavior is verified separately in the retained test report.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.check:
        if canonical(load_binary_json(args.output.read_bytes())) != canonical(result):
            raise ValueError("Saved arithmetic calibration differs from exact recreation")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "mcnemar_cases": len(result["mcnemar"]["cases"]),
                "holm_cases": result["holm"]["three_contrast_grid_count"],
                "permutations": result["holm"]["permutation_check_count"],
                "max_float_error": result["mcnemar"]["max_absolute_float_error"],
                "publication_eligible": False,
                "recreated": args.check,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
