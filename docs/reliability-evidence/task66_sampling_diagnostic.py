"""Exact ideal-shot calibration and authored Task66 assertion-slice diagnostic.

No sampler, model code, container or full pinned check pipeline executes here.
The diagnostic does not resolve the original prompt's omitted phase convention.
"""

import argparse
import ast
import hashlib
import json
import math
import platform
from fractions import Fraction
from importlib.metadata import version
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from graybench.datasets import PINS, load_suite
from graybench.identity import canonical, identity
from graybench.provenance import source_manifest

SOURCE_DIGESTS = (
    "bae918da0932fdcc5522fdfff18a9a4c2b4092c0e02cf6896c4778edd32ea211",
    "d5e8ffe3c153b6147ff2a24533653cbcddf815ab43bc157d5e10704d274db6be",
)
COUNTS = {
    "balanced": {"001": 341, "010": 341, "100": 342},
    "inclusive_boundary": {"001": 300, "010": 324, "100": 400},
    "lower_tail": {"001": 299, "010": 362, "100": 363},
    "upper_tail": {"001": 401, "010": 300, "100": 323},
    "incorrect_total": {"001": 341, "010": 341, "100": 341},
    "outside_support": {"001": 341, "010": 341, "100": 341, "111": 1},
}
EXPECTED_COUNT_OUTCOMES = {
    "balanced": "pass",
    "inclusive_boundary": "pass",
    "lower_tail": "fail",
    "upper_tail": "fail",
    "incorrect_total": "fail",
    "outside_support": "error",
}
FIXTURE_SPECS = (
    ("canonical_gates", Fraction(1)),
    ("independent_amplitude_preparation", Fraction(1)),
    ("symmetric_wire_permutation", Fraction(1)),
    ("global_phase", Fraction(1)),
    ("relative_pi_q0", Fraction(1, 9)),
    ("relative_pi_q1", Fraction(1, 9)),
    ("relative_pi_q2", Fraction(1, 9)),
    ("relative_i_q1", Fraction(5, 9)),
    ("relative_cube_roots", Fraction(0)),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fraction_record(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def bounds(shots, lower, upper):
    if any(type(value) is not int for value in (shots, lower, upper)):
        raise ValueError("Require strict integers")
    if not 0 <= lower <= upper <= shots <= 2048:
        raise ValueError("Invalid count bounds; require 0 <= lower <= upper <= shots <= 2048")


def acceptance_probability(shots, lower, upper):
    """Count ordered equally probable three-label shot sequences with binomials."""
    bounds(shots, lower, upper)
    accepted = 0
    for a in range(lower, upper + 1):
        for b in range(max(lower, shots - a - upper), min(upper, shots - a - lower) + 1):
            accepted += math.comb(shots, a) * math.comb(shots - a, b)
    return Fraction(accepted, 3**shots)


def factorial_acceptance_probability(shots, lower, upper):
    """Independent multinomial coefficient sum, using a full triple enumeration."""
    bounds(shots, lower, upper)
    factorials = [math.factorial(i) for i in range(shots + 1)]
    accepted = 0
    for a in range(lower, upper + 1):
        for b in range(lower, upper + 1):
            c = shots - a - b
            if lower <= c <= upper:
                accepted += factorials[shots] // (factorials[a] * factorials[b] * factorials[c])
    return Fraction(accepted, 3**shots)


def assertion_slice(task):
    functions = [
        node
        for node in ast.parse(task.upstream_test).body
        if isinstance(node, ast.FunctionDef) and node.name == "check"
    ]
    if len(functions) != 1:
        raise ValueError("Unexpected pinned check shape")
    assertions = [node for node in functions[0].body if isinstance(node, ast.Assert)]
    if len(assertions) != 7:
        raise ValueError("Expected all seven pinned assertions")
    return ast.Module(body=assertions, type_ignores=[])


def validate_tasks(tasks):
    if tuple(task.digest for task in tasks) != SOURCE_DIGESTS:
        raise ValueError("Requires the exact pinned Task66 normal/hard sources")


def fixtures():
    expected = np.zeros(8, dtype=complex)
    expected[[1, 2, 4]] = 1 / np.sqrt(3)
    for name, fidelity in FIXTURE_SPECS:
        circuit = QuantumCircuit(3)
        if name == "independent_amplitude_preparation":
            circuit.prepare_state(expected)
        else:
            circuit.ry(2 * np.arccos(1 / np.sqrt(3)), 0)
            circuit.ch(0, 1)
            circuit.cx(1, 2)
            circuit.cx(0, 1)
            circuit.x(0)
        if name == "symmetric_wire_permutation":
            circuit.swap(0, 2)
        elif name == "global_phase":
            circuit.global_phase = 0.37
        elif name.startswith("relative_pi_q"):
            circuit.z(int(name[-1]))
        elif name == "relative_i_q1":
            circuit.s(1)
        elif name == "relative_cube_roots":
            circuit.p(2 * np.pi / 3, 1)
            circuit.p(4 * np.pi / 3, 2)
        yield name, circuit, fidelity, expected


def outcome(code, circuit, counts):
    try:
        exec(code, {"QuantumCircuit": QuantumCircuit, "result": circuit, "counts": counts})
    except AssertionError as error:
        return {"outcome": "fail", "exception": type(error).__name__, "detail": str(error)}
    except Exception as error:
        return {"outcome": "error", "exception": type(error).__name__, "detail": str(error)}
    return {"outcome": "pass", "exception": None, "detail": None}


def probe(normal, hard):
    validate_tasks((normal, hard))
    checks = [
        compile(assertion_slice(task), "pinned-task66-assertions", "exec")
        for task in (normal, hard)
    ]
    probability = np.zeros(8)
    probability[[1, 2, 4]] = 1 / 3
    rows = []
    for name, circuit, fidelity, expected in fixtures():
        state = Statevector.from_instruction(circuit)
        sdk_probability = state.probabilities()
        observed_fidelity = float(abs(np.vdot(expected, state.data)) ** 2)
        probability_error = float(np.max(np.abs(sdk_probability - probability)))
        fidelity_error = abs(observed_fidelity - float(fidelity))
        if probability_error >= 1e-14 or fidelity_error >= 1e-14:
            raise ValueError("Authored fixture failed independent probability/fidelity calibration")
        circuit.measure_all()
        if len(circuit.data[-3:]) != 3 or any(
            item.operation.name != "measure" for item in circuit.data[-3:]
        ):
            raise ValueError("Expected terminal measurement of all three qubits")
        trials = {}
        for label, counts in COUNTS.items():
            trial = {
                suite: outcome(code, circuit, dict(counts))
                for suite, code in zip(("normal", "hard"), checks, strict=True)
            }
            if any(
                result["outcome"] != EXPECTED_COUNT_OUTCOMES[label] for result in trial.values()
            ):
                raise ValueError("Pinned assertion slice disagrees with predeclared count outcome")
            trials[label] = trial
        rows.append(
            {
                "id": name,
                "expected_symmetric_w_fidelity": fraction_record(fidelity),
                "observed_symmetric_w_fidelity": observed_fidelity,
                "symmetric_w_up_to_global_phase": fidelity == 1,
                "sdk_probability_error": probability_error,
                "sdk_fidelity_error": fidelity_error,
                "statevector": [[float(value.real), float(value.imag)] for value in state.data],
                "probabilities": [float(value) for value in sdk_probability],
                "circuit_operations": [
                    [
                        item.operation.name,
                        [circuit.find_bit(bit).index for bit in item.qubits],
                        [circuit.find_bit(bit).index for bit in item.clbits],
                    ]
                    for item in circuit.data
                ],
                "counts": trials,
            }
        )
    return rows


def tasks_at(cache):
    tasks = tuple(load_suite(suite, cache)[66] for suite in ("normal", "hard"))
    validate_tasks(tasks)
    return tasks


def plan(cache):
    tasks = tasks_at(cache)
    return {
        "kind": "graybench_task66_sampling_plan_v1",
        "source_task_digests": list(SOURCE_DIGESTS),
        "public_task_digests": [task.public.digest for task in tasks],
        "upstream_test_sha256": [sha(task.upstream_test.encode()) for task in tasks],
        "assertion_ast_digests": [
            identity(ast.dump(assertion_slice(task), include_attributes=False)) for task in tasks
        ],
        "engine_source": source_manifest(),
        "script_sha256": sha(Path(__file__).read_bytes()),
        "dataset_pins": PINS,
        "fixture_count": len(FIXTURE_SPECS),
        "fixtures": [
            {"id": name, "symmetric_w_fidelity": fraction_record(value)}
            for name, value in FIXTURE_SPECS
        ],
        "count_vectors": COUNTS,
        "expected_count_outcomes": EXPECTED_COUNT_OUTCOMES,
        "assertion_trials": len(FIXTURE_SPECS) * len(COUNTS) * 2,
        "ideal_multinomial": {
            "shots": 1024,
            "label_probabilities": [fraction_record(Fraction(1, 3))] * 3,
            "inclusive_lower": 300,
            "inclusive_upper": 400,
        },
        "scope": "All exact assertion AST nodes only; "
        "sampler/import/transpiler/candidate-call pipeline excluded",
        "assumptions": [
            "Ideal probabilities exactly one third",
            "Shots independent",
            "Pinned implicit total 1024 used for analytic calibration, not a public contract",
        ],
    }


def build(cache, declared):
    if canonical(declared) != canonical(plan(cache)):
        raise ValueError("Current sources/settings differ from the predeclared plan")
    acceptance = acceptance_probability(1024, 300, 400)
    if acceptance != factorial_acceptance_probability(1024, 300, 400):
        raise ValueError("Independent multinomial derivations disagree")
    rejection = 1 - acceptance
    return {
        "kind": "graybench_task66_sampling_diagnostic_v1",
        "plan_digest": identity(declared),
        "engine_source_digest": source_manifest()["digest"],
        "script_sha256": sha(Path(__file__).read_bytes()),
        "publication_eligible": False,
        "runtime_qualified": False,
        "independent_human_admission": False,
        "isolated_sampler_executed": False,
        "model_generations": 0,
        "sampling_assumption": "1024 independent ideal equal-probability shots",
        "ideal_acceptance": fraction_record(acceptance),
        "ideal_rejection": fraction_record(rejection),
        "ideal_rejection_approximation": float(rejection),
        "hypothetical_independent_20_replays_any_rejection_approximation": -math.expm1(
            20 * math.log(float(acceptance))
        ),
        "environment": {
            "python": platform.python_version(),
            "qiskit": version("qiskit"),
            "numpy": version("numpy"),
        },
        "controls": probe(*tasks_at(cache)),
        "limitations": [
            "Exact probability is conditional on the ideal iid multinomial assumption, "
            "not observed sampler behavior.",
            "Assertion slices exclude candidate invocation, sampler/import/transpiler pipeline "
            "and do not prove a full native false pass.",
            "Relative-phase fixtures are not the explicit symmetric W state; original wording "
            "omits a phase convention, so a revised contract needs adjudication.",
            "Global phase is physically irrelevant; relative phase is invisible to "
            "computational-basis probabilities.",
            "No replacement threshold, strengthened judge, isolated execution or task "
            "admission is supplied.",
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
                "ideal_rejection": report["ideal_rejection_approximation"],
                "assertion_trials": declared["assertion_trials"],
                "publication_eligible": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
