"""Exact pinned task-119 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite

GUARD = '    if num_state_qubits != 3 or kind == "half":\n        raise ValueError("unsupported")\n'
ALTERNATIVE = "    return CDKMRippleCarryAdder(num_state_qubits, kind)\n"


def change_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"Expected one occurrence of {old!r}")
    return source.replace(old, new)


def candidates(reference):
    return {
        "reference": reference,
        "three_only_no_half": change_once(
            reference,
            "    adder = CDKMRippleCarryAdder",
            GUARD + "    adder = CDKMRippleCarryAdder",
        ),
        "direct_adder_alternative": change_once(
            reference,
            "    adder = CDKMRippleCarryAdder(num_state_qubits, kind)\n"
            "    qc = QuantumCircuit(adder.num_qubits)\n"
            "    qc.append(adder.to_instruction(), range(adder.num_qubits))\n"
            "    return qc\n",
            ALTERNATIVE,
        ),
        "wrong_full_control": change_once(
            reference,
            "    return qc\n",
            '    if kind == "full":\n'
            "        return QuantumCircuit(adder.num_qubits)\n"
            "    return qc\n",
        ),
        "wrong_fixed_control": change_once(
            reference,
            "    return qc\n",
            '    if kind == "fixed":\n'
            "        return QuantumCircuit(adder.num_qubits)\n"
            "    return qc\n",
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {
        "reference": "pass",
        "three_only_no_half": "pass",
        "direct_adder_alternative": "pass",
        "wrong_full_control": "fail",
        "wrong_fixed_control": "fail",
    }
    cases = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/119"
        )
        for name, solution in candidates(task.canonical_solution).items():
            source = task.public.prompt + solution if suite == "normal" else solution
            namespace = {}
            try:
                exec(compile(source, "<authored-task-119-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-119-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace["create_ripple_carry_adder_circuit"])
                outcome, assertion = "pass", None
            except AssertionError as exc:
                outcome, assertion = "fail", str(exc)
            if outcome != expected[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {outcome}")
            extra = {}
            if name in {"three_only_no_half", "direct_adder_alternative"}:
                function = namespace["create_ripple_carry_adder_circuit"]
                for label, call in (
                    ("half_at_three", (3, "half")),
                    ("full_at_four", (4, "full")),
                ):
                    try:
                        result = function(*call)
                        extra[label] = {"result_type": type(result).__name__}
                    except ValueError:
                        extra[label] = {"error": "ValueError"}
                if name == "three_only_no_half" and any(
                    x != {"error": "ValueError"} for x in extra.values()
                ):
                    raise RuntimeError("Adverse function did not reject public input")
                if name == "direct_adder_alternative" and any(
                    x != {"result_type": "CDKMRippleCarryAdder"} for x in extra.values()
                ):
                    raise RuntimeError("Alternative did not handle public input")
            cases.append(
                {
                    "suite": suite,
                    "task_digest": task.digest,
                    "case": name,
                    "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "outcome": outcome,
                    "assertion": assertion,
                    "public_input_controls": extra,
                }
            )
    print(
        json.dumps(
            {
                "kind": "graybench_task119_exact_oracle_probe_v1",
                "scope": "Authored exact-test diagnostic, not protected judging or a model score",
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "cases": cases,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
