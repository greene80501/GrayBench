"""Exact Bell-shot arithmetic and trusted-data probes of pinned check functions.

No sampler, model code, external imports, transpiler or isolated runtime executes.
The original tasks remain unchanged; seeded runtime behavior is not inferred.
"""

import argparse
import ast
import hashlib
import json
import math
import platform
from collections import Counter
from fractions import Fraction
from pathlib import Path

from graybench.datasets import PINS, load_suite
from graybench.identity import canonical, identity
from graybench.provenance import source_manifest

SOURCE_DIGESTS = {
    "normal": {
        1: "30376cfac1b0cb57a3693c1ddd9663fab834c93117cb48a8233ea15636b124b5",
        14: "1814bdd0ae1fb2d7796c2c65b23191fb89ee0c0c21b4239bf196ee5164909ce2",
        15: "5ac412dfb946a4265054bf7b0f4a2ff28209095ea11ae6b9c12c3e7e67ed7416",
        31: "755fac671d9d406500f2340fa5c6b8699b84ac0a74f3bb2c8555138e0244e628",
    },
    "hard": {
        1: "019ee7770e01996d30cddc71224bbb42e93647484a9e9fc2cd9b59753862d10e",
        14: "f64f0c6638fd2b1014c75017c9ace0f06808d0b001df265d95f3ae939a9767c5",
        15: "81ba57e53e74f35514ec99a177cdfae66b9adb1221931be9019587338fbfaa12",
        31: "84cc81ea374311c63d5f905317ef5d224f648b840abcb2b6dcf00e791fb61c54",
    },
}
SHOT_COUNTS = (*range(1, 129), 1000, 1024)
NOISE_PROBABILITIES = (Fraction(0), Fraction(1, 1000), Fraction(1, 100), Fraction(1, 10))
# These are returned-data fixtures, not implementations satisfying sampler/process obligations.
# Each tuple freezes ID, data, expected check outcome and its interpretation before execution.
CASES = {
    1: (
        ("balanced_1000", {"00": 500, "11": 500}, "pass", "Valid balanced sample data"),
        ("two_shot_balance", {"00": 1, "11": 1}, "pass", "Shot count is not public"),
        ("lower_boundary", {"00": 400, "11": 600}, "fail", "Strict lower boundary"),
        ("upper_boundary", {"00": 600, "11": 400}, "fail", "Strict upper boundary"),
        ("all_00", {"00": 1000}, "fail", "Possible ideal shot tail"),
        ("negative_counts", {"00": -5, "11": -5}, "pass", "Invalid negative counts"),
        ("fractional_counts", {"00": 0.5, "11": 0.5}, "pass", "Invalid fractional counts"),
        ("zero_total", {"00": 0, "11": 0}, "error", "Empty count total"),
        ("invalid_bitstring", {"00": 1, "invalid": 1}, "fail", "Invalid count label"),
        ("not_dict", ["00", "11"], "fail", "Wrong return type"),
    ),
    14: (
        ("100_balanced_shots", ["00", "11"] * 50, "pass", "Requested shot count"),
        ("two_shots", ["00", "11"], "pass", "Violates public 100-shot requirement"),
        ("99_shots", ["00"] * 49 + ["11"] * 50, "pass", "Too few shots"),
        ("101_shots", ["00"] * 50 + ["11"] * 51, "pass", "Too many shots"),
        ("100_identical_shots", ["00"] * 100, "fail", "Possible ideal shot tail"),
        ("invalid_bitstring", ["00", "11", "01"], "fail", "Outside ideal Bell support"),
        ("empty", [], "fail", "No returned shots"),
    ),
    15: (
        (
            "ideal_bell_counts",
            {"00": 500, "11": 500},
            "fail",
            "Noise model/rate is not specified in prose",
        ),
        (
            "psi_bell_counts",
            {"01": 500, "10": 500},
            "error",
            "Bell variant is not specified in prose",
        ),
        ("one_error_count", {"00": 500, "11": 499, "01": 1}, "pass", "Positive outside event"),
        ("negative_error_count", {"00": 500, "11": 500, "01": -1}, "pass", "Negative count"),
        ("fractional_counts", {"00": 0.5, "11": 0.5, "01": 0.1}, "pass", "Fractional counts"),
        ("invalid_bitstring", {"00": 500, "11": 500, "invalid": 1}, "pass", "Invalid bit label"),
        ("missing_key", {"11": 1}, "error", "Possible ideal one-shot output lacks 00"),
    ),
    31: (
        ("pinned_counts", {"00": 521, "11": 503}, "pass", "Exact private snapshot"),
        ("other_total", {"00": 500, "11": 500}, "fail", "Shots are not public; seed not executed"),
        ("swapped_counts", {"00": 503, "11": 521}, "fail", "Seed behavior is not inferred"),
        (
            "psi_bell_counts",
            {"01": 521, "10": 503},
            "fail",
            "Bell variant is not specified in prose",
        ),
        ("floating_counts", {"00": 521.0, "11": 503.0}, "pass", "Count types not validated"),
        ("extra_entry", {"00": 521, "11": 503, "01": 0}, "fail", "Exact dictionary comparison"),
    ),
}


def fraction_record(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def valid_shots(shots):
    if type(shots) is not int or not 1 <= shots <= 2048:
        raise ValueError("Require integer shots from 1 through 2048")


def task1_acceptance(shots):
    """Exact strict 0.4 < k/n < 0.6 acceptance for independent ideal Bell shots."""
    valid_shots(shots)
    return Fraction(
        sum(
            math.comb(shots, count)
            for count in range(shots + 1)
            if 2 * shots < 5 * count < 3 * shots
        ),
        2**shots,
    )


def recurrence_acceptance(shots):
    """Independent integer binomial recurrence and inclusive-integer bounds."""
    valid_shots(shots)
    low, high = 2 * shots // 5 + 1, (3 * shots - 1) // 5
    weight, accepted = 1, 0
    for count in range(shots + 1):
        if low <= count <= high:
            accepted += weight
        if count < shots:
            weight = weight * (shots - count) // (count + 1)
    return Fraction(accepted, 2**shots)


def missing_support_probability(shots):
    valid_shots(shots)
    return Fraction(2, 2**shots)


def no_outside_event_probability(shots, probability):
    valid_shots(shots)
    if type(probability) is not Fraction or not 0 <= probability <= 1:
        raise ValueError("Require rational outside-event probability in [0,1]")
    return (1 - probability) ** shots


def check_function(task):
    functions = [
        node
        for node in ast.parse(task.upstream_test).body
        if isinstance(node, ast.FunctionDef) and node.name == "check"
    ]
    if len(functions) != 1:
        raise ValueError("Unexpected pinned check shape")
    function = functions[0]
    # The complete function body is retained. Imports and the hard-suite outer
    # invocation are outside this probe; no assertion slice is substituted.
    if not (
        len(function.body) == {1: 4, 14: 4, 15: 3, 31: 2}[int(task.public.task_id.split("/")[-1])]
        and isinstance(function.body[0], ast.Assign)
        and ast.dump(function.body[0], include_attributes=False)
        == ast.dump(ast.parse("result = candidate()").body[0], include_attributes=False)
        and all(isinstance(node, ast.Assert) for node in function.body[1:])
    ):
        raise ValueError("Unexpected pinned check body")
    return function


def exact_check(task):
    scope = {}
    exec(
        compile(
            ast.Module(body=[check_function(task)], type_ignores=[]), "<pinned-Bell-check>", "exec"
        ),
        scope,
    )
    return scope["check"]


def observe(check, value):
    calls = 0

    def candidate():
        nonlocal calls
        calls += 1
        return value

    try:
        check(candidate)
    except Exception as error:
        return {
            "outcome": "fail" if isinstance(error, AssertionError) else "error",
            "exception": type(error).__name__,
            "detail": str(error),
            "calls": calls,
        }
    return {"outcome": "pass", "exception": None, "detail": None, "calls": calls}


def validate_tasks(tasks):
    expected = [
        (suite, number, digest)
        for suite, rows in SOURCE_DIGESTS.items()
        for number, digest in rows.items()
    ]
    actual = [
        (task.public.suite, int(task.public.task_id.split("/")[-1]), task.digest) for task in tasks
    ]
    if actual != expected:
        raise ValueError(
            "Requires all exact pinned Bell-task normal/hard sources in declared order"
        )


def tasks_at(cache):
    tasks = tuple(
        task
        for suite, numbers in SOURCE_DIGESTS.items()
        for task in (load_suite(suite, cache)[number] for number in numbers)
    )
    validate_tasks(tasks)
    return tasks


def probe(tasks):
    validate_tasks(tasks)
    rows = []
    for task in tasks:
        number = int(task.public.task_id.split("/")[-1])
        check = exact_check(task)
        for name, value, expectation, interpretation in CASES[number]:
            result = observe(check, value)
            if result["outcome"] != expectation or result["calls"] != 1:
                raise ValueError(f"Pinned check differs from predeclared outcome: {number}/{name}")
            rows.append(
                {
                    "suite": task.public.suite,
                    "task_id": number,
                    "case_id": name,
                    "interpretation": interpretation,
                    "judgment": result,
                }
            )
    return rows


def sha(data):
    return hashlib.sha256(data).hexdigest()


def plan(cache):
    tasks = tasks_at(cache)
    return {
        "kind": "graybench_bell_sampling_plan_v1",
        "engine_source": source_manifest(),
        "script_sha256": sha(Path(__file__).read_bytes()),
        "dataset_pins": PINS,
        "tasks": [
            {
                "suite": task.public.suite,
                "task_id": task.public.task_id,
                "source_digest": task.digest,
                "public_digest": task.public.digest,
                "check_sha256": sha(task.upstream_test.encode()),
                "check_ast_digest": identity(
                    ast.dump(check_function(task), include_attributes=False)
                ),
            }
            for task in tasks
        ],
        "cases": [
            {
                "task_id": number,
                "case_id": name,
                "value": value,
                "expected_check_outcome": expected,
                "interpretation": meaning,
            }
            for number, rows in CASES.items()
            for name, value, expected, meaning in rows
        ],
        "shot_counts": list(SHOT_COUNTS),
        "task15_event_probabilities": [fraction_record(q) for q in NOISE_PROBABILITIES],
        "scope": (
            "Complete pinned check functions on trusted data; external imports, sampler, "
            "transpiler and full candidate implementation excluded"
        ),
        "assumptions": [
            "Ideal independent Bell Z measurements have probabilities 1/2 on 00 and 11",
            "Shot-count curve is conditional calibration, not observed sampler behavior",
            "Task15 q values are illustrative outside-event probabilities, "
            "not a calibrated backend noise model",
            "Seed 42 runtime behavior is unexecuted and cannot be inferred "
            "from unseeded probabilities",
        ],
    }


def build(cache, declared):
    if canonical(declared) != canonical(plan(cache)):
        raise ValueError("Current sources/settings differ from the predeclared plan")
    checks = [
        exact_check(task) for task in tasks_at(cache) if task.public.task_id == "qiskitHumanEval/1"
    ]
    curve, trials = [], 0
    for shots in SHOT_COUNTS:
        probability = task1_acceptance(shots)
        if probability != recurrence_acceptance(shots):
            raise ValueError("Independent exact binomial derivations disagree")
        observations = []
        for check in checks:
            accepted = 0
            for count in range(shots + 1):
                counts = {
                    key: value for key, value in (("00", count), ("11", shots - count)) if value
                }
                result = observe(check, counts)
                trials += 1
                if result["calls"] != 1 or result["outcome"] == "error":
                    raise ValueError("Unexpected valid count-vector check behavior")
                if result["outcome"] == "pass":
                    accepted += math.comb(shots, count)
            observed = Fraction(accepted, 2**shots)
            if observed != probability:
                raise ValueError("Exact pinned check differs from binomial calibration")
            observations.append(fraction_record(observed))
        curve.append(
            {
                "shots": shots,
                "ideal_acceptance": fraction_record(probability),
                "ideal_rejection": fraction_record(1 - probability),
                "ideal_rejection_approximation": float(1 - probability),
                "normal_hard_check_acceptance": observations,
            }
        )
    controls = probe(tasks_at(cache))
    return {
        "kind": "graybench_bell_sampling_diagnostic_v1",
        "plan_digest": identity(declared),
        "engine_source_digest": source_manifest()["digest"],
        "script_sha256": sha(Path(__file__).read_bytes()),
        "environment": {"python": platform.python_version()},
        "controls": controls,
        "control_outcomes": dict(Counter(row["judgment"]["outcome"] for row in controls)),
        "task1_shot_curve": curve,
        "task1_exact_check_count_vectors": trials,
        "task14_all_identical_100_shots": fraction_record(missing_support_probability(100)),
        "task15_no_outside_event": [
            {
                "shots": n,
                "outside_probability": fraction_record(q),
                "no_outside_event_probability": fraction_record(no_outside_event_probability(n, q)),
            }
            for n in (100, 1000)
            for q in NOISE_PROBABILITIES
        ],
        "task31_private_total": 1024,
        "task31_seeded_behavior_attested": False,
        "publication_eligible": False,
        "runtime_qualified": False,
        "independent_human_admission": False,
        "isolated_sampler_executed": False,
        "model_generations": 0,
        "limitations": [
            "Trusted returned-data fixtures do not satisfy or attest a "
            "sampler/pass-manager process",
            "Conditional iid arithmetic is not an observed sampler false-rejection rate",
            "Task15 no-outside-event probability describes that event only, "
            "not the complete check failure rate or a backend noise model",
            "Task31 exact seeded counts depend on shots/runtime/generator details; "
            "no seed behavior or failure rate is inferred",
            "No original task, judge, threshold or score is changed; "
            "strengthened conditions need independent contract admission",
        ],
    }


def verify(report, declared, cache):
    if canonical(report) != canonical(build(cache, declared)):
        raise ValueError("Saved diagnostic differs from exact recreation")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    plan_path = args.output.with_name("plan.json")
    if args.check:
        declared = json.loads(plan_path.read_bytes())
        report = json.loads(args.output.read_bytes())
        verify(report, declared, args.cache)
    else:
        declared = plan(args.cache)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with plan_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(declared, indent=2, sort_keys=True) + "\n")
        report = build(args.cache, declared)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "recreated": args.check,
                "control_outcomes": report["control_outcomes"],
                "exact_count_vectors": report["task1_exact_check_count_vectors"],
                "publication_eligible": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
