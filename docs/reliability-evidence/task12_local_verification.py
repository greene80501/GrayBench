"""Recreate explicit Task12 host/value-codec evidence; never qualify a sandbox."""

import argparse
import hashlib
import importlib.util
import json
import math
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from graybench.datasets import PINS, load_suite
from graybench.identity import canonical, identity
from graybench.provenance import source_manifest
from graybench.task12_revision import CHECK, TRACK, revised_task
from graybench.value_wire import WireError, decode, encode


def sha(data):
    return hashlib.sha256(data).hexdigest()


def controls():
    path = Path(__file__).with_name("task12_controls.py")
    spec = importlib.util.spec_from_file_location("task12_fixed_controls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan(cache):
    module = controls()
    tasks = tuple(load_suite(suite, cache)[12] for suite in ("normal", "hard"))
    cases = []
    for source in tasks:
        task = revised_task(source)
        for probe in module.probes(source):
            cases.append(
                {
                    "suite": source.public.suite,
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
        "kind": "graybench_task12_host_plan_v1",
        "track": TRACK,
        "scope": "Host checker and actual production value codec; no process isolation",
        "release_eligible": False,
        "engine_source": source_manifest(),
        "pins": PINS,
        "script_sha256": sha(Path(__file__).read_bytes()),
        "control_script_sha256": sha(Path(module.__file__).read_bytes()),
        "oracle_sha256": sha(CHECK.encode()),
        "cases": cases,
        "calibration": {
            "phase_angles": "257 equally spaced samples from -pi through pi, inclusive",
            "entry_mutants": "For each of 16 entries, separately add 1e-6 real or imaginary",
            "basis_rule": "H0 amplitudes (-1)**(before0*after0)/sqrt(2), "
            "then after1=before1 xor after0",
        },
    }


def build(cache, declared):
    if canonical(declared) != canonical(plan(cache)):
        raise ValueError("Task12 host plan differs from current sources or conditions")
    module = controls()
    namespace = {}
    exec(compile(CHECK, "authored-task12-check", "exec"), namespace)
    check = namespace["check"]
    observations = []
    for suite in ("normal", "hard"):
        source = load_suite(suite, cache)[12]
        task = revised_task(source)
        for probe in module.probes(source):
            scope = {}
            program = (
                task.public.prompt + probe.completion if suite == "normal" else probe.completion
            )
            exec(compile(program, "fixed-authored-task12-control", "exec"), scope)
            value = scope[task.public.entry_point]()
            calls = 0
            wire = None

            def proxy(value=value):
                nonlocal calls, wire
                calls += 1
                wire = encode(value)
                # Exercise the JSON byte boundary; no custom serialization fallback.
                return decode(json.loads(json.dumps(wire, allow_nan=False)))

            try:
                check(proxy)
            except WireError as exc:
                outcome, detail = "unsupported", str(exc)
            except AssertionError as exc:
                outcome, detail = "fail", str(exc)
            else:
                outcome, detail = "pass", None
            if outcome != probe.expectation or calls != 1:
                raise ValueError(f"Unexpected Task12 host outcome: {suite}/{probe.name}")
            observations.append(
                {
                    "suite": suite,
                    "name": probe.name,
                    "outcome": outcome,
                    "detail": detail,
                    "calls": calls,
                    "wire_value": wire,
                    "logical_value_bytes": None if wire is None else len(canonical(wire)),
                }
            )
    # Independent basis-action derivation, distinct from the checker's tensor product.
    basis = np.zeros((4, 4), dtype=complex)
    for column in range(4):
        before0, before1 = column & 1, column >> 1
        for after0 in range(2):
            row = ((before1 ^ after0) << 1) | after0
            basis[row, column] = (-1) ** (before0 * after0) / math.sqrt(2)
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    sdk = Operator(circuit).data
    error = float(np.max(np.abs(sdk - basis)))
    if error >= 1e-14:
        raise ValueError("Independent basis action and SDK disagree")
    phases = []
    for angle in np.linspace(-np.pi, np.pi, 257):
        value = np.exp(1j * angle) * basis
        check(lambda value=value: decode(encode(value)))
        phases.append(float(angle))
    mutants = []
    for row in range(4):
        for column in range(4):
            for change in (1e-6, 1e-6j):
                value = basis.copy()
                value[row, column] += change
                try:
                    check(lambda value=value: decode(encode(value)))
                except AssertionError:
                    pass
                else:
                    raise ValueError("A changed complete-operator entry was accepted")
                mutants.append({"row": row, "column": column, "delta": [change.real, change.imag]})
    return {
        "kind": "graybench_task12_host_verification_v1",
        "plan_digest": identity(declared),
        "release_eligible": False,
        "runtime_qualified": False,
        "independent_human_admission": False,
        "environment": {
            "python": platform.python_version(),
            "qiskit": version("qiskit"),
            "numpy": version("numpy"),
        },
        "scope": "Host semantic and value-codec evidence only; candidate encoder integrity "
        "and sandbox isolation are unverified",
        "authored_controls": observations,
        "calibration": {
            "basis_value": encode(basis),
            "sdk_value": encode(sdk),
            "max_entry_error": error,
            "accepted_phase_angles": phases,
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
        if canonical(build(args.cache, declared)) != canonical(
            json.loads(args.output.read_bytes())
        ):
            raise ValueError("Saved Task12 evidence differs from exact recreation")
    else:
        declared = plan(args.cache)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Declare all conditions durably before executing a control.
        with plan_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(declared, indent=2, sort_keys=True) + "\n")
        result = build(args.cache, declared)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {"controls": 58, "phase_checks": 257, "entry_mutants": 32, "release_eligible": False}
        )
    )


if __name__ == "__main__":
    main()
