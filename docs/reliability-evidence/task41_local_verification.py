"""Recreate fixed Task41 host/value evidence; no model or sandbox execution."""

import argparse
import ast
import cmath
import hashlib
import importlib.util
import itertools
import json
import math
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
from qiskit.quantum_info import Operator, Pauli

from graybench.datasets import PINS, load_suite
from graybench.identity import canonical, identity
from graybench.provenance import source_manifest
from graybench.task41_revision import CHECK, PREFIX, TRACK, revised_task
from graybench.value_wire import WireError, decode, encode


def sha(data):
    return hashlib.sha256(data).hexdigest()


def controls():
    path = Path(__file__).with_name("task41_controls.py")
    spec = importlib.util.spec_from_file_location("task41_fixed_controls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def phases():
    return [-math.pi + 2 * math.pi * i / 256 for i in range(257)] + [
        -0.5e-10,
        0.5e-10,
        -1.5e-10,
        1.5e-10,
        2 * math.pi,
    ]


def plan(cache):
    module = controls()
    cases = []
    for suite in ("normal", "hard"):
        source = load_suite(suite, cache)[41]
        task = revised_task(source)
        for probe in module.probes(source):
            cases.append(
                {
                    "suite": suite,
                    "name": probe.name,
                    "expectation": probe.expectation,
                    "rationale": probe.rationale,
                    "completion_sha256": sha(probe.completion.encode()),
                    "source_task_digest": source.digest,
                    "revised_task_digest": task.digest,
                    "public_task_digest": task.public.digest,
                }
            )
    return {
        "kind": "graybench_task41_host_plan_v1",
        "track": TRACK,
        "scope": "Authored host fixtures and production value codec; no process isolation",
        "release_eligible": False,
        "engine_source": source_manifest(),
        "pins": PINS,
        "script_sha256": sha(Path(__file__).read_bytes()),
        "control_script_sha256": sha(Path(module.__file__).read_bytes()),
        "oracle_sha256": sha(CHECK.encode()),
        "cases": cases,
        "calibration": {
            "labels": ["".join(p) for p in itertools.product("IXYZ", repeat=2)],
            "ordered_placements": list(itertools.permutations(range(3), 2)),
            "phase_angles": phases(),
            "phase_expectation": "2*abs(sin(angle/2)) <= 1e-10; no phase alignment",
            "entry_mutants": "Each of 64 entries separately perturbed by 1e-6 real or imaginary",
        },
        "native_screen": "Exact pinned checks applied to an authored non-Operator forged equality",
    }


def build(cache, declared):
    if canonical(declared) != canonical(plan(cache)):
        raise ValueError("Task41 host plan differs from current source or conditions")
    module = controls()
    namespace = {}
    exec(compile(CHECK, "authored-task41-check", "exec"), namespace)
    check = namespace["check"]

    def judge_value(value):
        calls = 0
        wire = None

        def proxy():
            nonlocal calls, wire
            calls += 1
            wire = encode(value)
            return decode(json.loads(json.dumps(wire, allow_nan=False)))

        try:
            check(proxy)
        except WireError as exc:
            outcome, detail = "unsupported", str(exc)
        except AssertionError as exc:
            outcome, detail = "fail", str(exc)
        else:
            outcome, detail = "pass", None
        if calls != 1:
            raise ValueError("Task41 checker call count differs from its contract")
        return {"outcome": outcome, "detail": detail, "wire_value": wire, "calls": calls}

    observations, native_screens = [], []
    for suite in ("normal", "hard"):
        source = load_suite(suite, cache)[41]
        task = revised_task(source)
        for probe in module.probes(source):
            program = (
                task.public.prompt + probe.completion if suite == "normal" else probe.completion
            )
            scope = {}
            exec(compile(program, "fixed-authored-task41-control", "exec"), scope)
            value = scope[task.public.entry_point]()
            result = judge_value(value)
            if result["outcome"] != probe.expectation:
                raise ValueError(f"Unexpected Task41 host outcome: {suite}/{probe.name}")
            representation = None
            if type(value) is Operator:
                representation = {
                    "shape": list(value.data.shape),
                    "dtype": value.data.dtype.str,
                    "strides": list(value.data.strides),
                    "writeable": value.data.flags.writeable,
                    "qargs": value.qargs,
                }
            observations.append(
                {
                    "suite": suite,
                    "name": probe.name,
                    "candidate_representation": representation,
                    **result,
                }
            )
            if probe.name == "forged-equality":
                functions = [
                    n
                    for n in ast.parse(source.upstream_test).body
                    if isinstance(n, ast.FunctionDef) and n.name == "check"
                ]
                if len(functions) != 1:
                    raise ValueError("Exact pinned checker shape changed")
                trusted = {}
                exec(compile(PREFIX, "pinned-public-imports", "exec"), trusted)
                exec(
                    compile(
                        ast.Module(body=functions, type_ignores=[]),
                        "exact-pinned-task41-check",
                        "exec",
                    ),
                    trusted,
                )
                trusted["check"](lambda value=value: value)
                native_screens.append(
                    {
                        "suite": suite,
                        "native_host_outcome": "pass",
                        "return_category": "Forged, not Operator",
                        "protected_host_codec_outcome": result["outcome"],
                    }
                )

    matrices = {
        "I": np.eye(2, dtype=complex),
        "X": np.array([[0, 1], [1, 0]], dtype=complex),
        "Y": np.array([[0, -1j], [1j, 0]]),
        "Z": np.diag([1, -1]).astype(complex),
    }
    target = np.kron(np.kron(matrices["Y"], matrices["I"]), matrices["X"])
    placement_checks = []
    for label in declared["calibration"]["labels"]:
        for positions in declared["calibration"]["ordered_placements"]:
            factors = [matrices["I"]] * 3
            factors[positions[0]], factors[positions[1]] = matrices[label[1]], matrices[label[0]]
            independent = np.kron(np.kron(factors[2], factors[1]), factors[0])
            value = Operator(np.eye(8)).compose(Operator(Pauli(label)), qargs=list(positions))
            error = float(np.max(np.abs(independent - value.data)))
            if error >= 1e-14:
                raise ValueError("Independent subsystem tensor and SDK disagree")
            expected = "pass" if np.array_equal(independent, target) else "fail"
            result = judge_value(value)
            if result["outcome"] != expected:
                raise ValueError("Unexpected Pauli placement classification")
            placement_checks.append(
                {
                    "label": label,
                    "positions": list(positions),
                    "max_entry_error": error,
                    "expected": expected,
                    "outcome": result["outcome"],
                }
            )
    phase_checks = []
    for angle in phases():
        chord = 2 * abs(math.sin(angle / 2))
        expected = "pass" if chord <= 1e-10 else "fail"
        result = judge_value(Operator(cmath.exp(1j * angle) * target))
        if result["outcome"] != expected:
            raise ValueError("Phase comparison differs from independent analytic expectation")
        phase_checks.append(
            {
                "angle": angle,
                "expected_max_entry_error": chord,
                "expected": expected,
                "outcome": result["outcome"],
            }
        )
    mutants = []
    for row in range(8):
        for column in range(8):
            for change in (1e-6, 1e-6j):
                value = target.copy()
                value[row, column] += change
                result = judge_value(Operator(value))
                if result["outcome"] != "fail":
                    raise ValueError("A changed full-operator entry was accepted")
                mutants.append(
                    {
                        "row": row,
                        "column": column,
                        "delta": [change.real, change.imag],
                        "outcome": "fail",
                    }
                )
    return {
        "kind": "graybench_task41_host_verification_v1",
        "plan_digest": identity(declared),
        "release_eligible": False,
        "runtime_qualified": False,
        "independent_human_admission": False,
        "scope": "Authored host checks and value codec only; "
        "encoder integrity and isolation unverified",
        "environment": {
            "python": platform.python_version(),
            "qiskit": version("qiskit"),
            "numpy": version("numpy"),
        },
        "authored_controls": observations,
        "native_forged_equality_screens": native_screens,
        "calibration": {
            "independent_target": encode(Operator(target)),
            "placement_checks": placement_checks,
            "phase_checks": phase_checks,
            "rejected_entry_mutants": mutants,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    plan_path = args.output.with_name(args.output.stem + "-plan.json")
    if args.check:
        declared = json.loads(plan_path.read_bytes())
        result = build(args.cache, declared)
        if canonical(result) != canonical(json.loads(args.output.read_bytes())):
            raise ValueError("Saved Task41 evidence differs from exact recreation")
    else:
        declared = plan(args.cache)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with plan_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(declared, indent=2, sort_keys=True) + "\n")
        result = build(args.cache, declared)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "controls": len(result["authored_controls"]),
                "placement_checks": len(result["calibration"]["placement_checks"]),
                "phase_checks": len(result["calibration"]["phase_checks"]),
                "entry_mutants": len(result["calibration"]["rejected_entry_mutants"]),
                "release_eligible": False,
            }
        )
    )


if __name__ == "__main__":
    main()
