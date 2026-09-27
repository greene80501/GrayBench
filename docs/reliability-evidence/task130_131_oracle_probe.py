"""Exact pinned task-130/131 diagnostics; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite


def circuit_body(*, width="n", first_gate="h"):
    return (
        "    from qiskit import QuantumCircuit\n"
        f"    circuit = QuantumCircuit({width})\n"
        f"    circuit.{first_gate}(1)\n"
        "    circuit.h(2)\n"
        "    circuit.cx(1, 3)\n"
        "    circuit.cx(2, 4)\n"
        "    return circuit.inverse()\n"
    )


def backend_body(*, mode="dynamic"):
    if mode == "dynamic":
        lookup = (
            "    from qiskit_ibm_runtime import fake_provider\n"
            "    selected = None\n"
            "    for backend_type in vars(fake_provider).values():\n"
            "        if not isinstance(backend_type, type):\n"
            "            continue\n"
            "        if not backend_type.__name__.startswith('Fake'):\n"
            "            continue\n"
            "        try:\n"
            "            backend = backend_type()\n"
            "            name = backend.name\n"
            "        except Exception:\n"
            "            continue\n"
            "        if name == backend_name:\n"
            "            selected = backend\n"
            "            break\n"
            "    if selected is None:\n"
            "        raise ValueError('Unknown fake backend')\n"
        )
    else:
        lookup = (
            "    from qiskit_ibm_runtime.fake_provider import FakeCairoV2\n"
            "    selected = FakeCairoV2()\n"
        )
    width = "config.num_qubits + 1" if mode == "wrong_width" else "config.num_qubits"
    return (
        lookup
        + "    config = selected.configuration()\n"
        f"    return {{'num_qubits': {width},\n"
        "            'coupling_map': config.coupling_map,\n"
        "            'supported_instructions': config.supported_instructions}\n"
    )


def cases(task):
    number = int(task.public.task_id.rsplit("/", 1)[1])
    if number == 130:
        variants = {
            "reference": task.canonical_solution,
            "independent_explicit_circuit": circuit_body(),
            "fixed_five_qubits": circuit_body(width="5"),
            "wrong_gate_control": circuit_body(first_gate="x"),
        }
    else:
        variants = {
            "reference": task.canonical_solution,
            "independent_module_lookup": backend_body(),
            "fixed_cairo_backend": backend_body(mode="fixed"),
            "wrong_width_control": backend_body(mode="wrong_width"),
        }
    for name, implementation in variants.items():
        if name == "reference":
            source = (
                task.public.prompt + implementation
                if task.public.suite == "normal"
                else implementation
            )
        elif task.public.suite == "normal":
            source = task.public.prompt + "\n" + implementation
        else:
            argument = "n" if number == 130 else "backend_name"
            source = f"def {task.public.entry_point}({argument}):\n"
            source += implementation
        yield name, source


def untested_input_observation(number, candidate):
    if number == 130:
        result = candidate(6)
        return {"requested_qubits": 6, "returned_qubits": result.num_qubits}
    from qiskit_ibm_runtime.fake_provider import FakeBelemV2

    backend = FakeBelemV2()
    result = candidate(backend.name)
    return {
        "requested_backend": backend.name,
        "expected_qubits": backend.configuration().num_qubits,
        "returned_qubits": result["num_qubits"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {
        130: {
            "reference": "pass",
            "independent_explicit_circuit": "pass",
            "fixed_five_qubits": "pass",
            "wrong_gate_control": "fail",
        },
        131: {
            "reference": "pass",
            "independent_module_lookup": "pass",
            "fixed_cairo_backend": "pass",
            "wrong_width_control": "fail",
        },
    }
    observations = []
    for suite in ("normal", "hard"):
        tasks = {t.public.task_id: t for t in load_suite(suite, args.cache)}
        for number in (130, 131):
            task = tasks[f"qiskitHumanEval/{number}"]
            for name, source in cases(task):
                namespace = {}
                try:
                    exec(compile(source, "<authored-solution>", "exec"), namespace)
                    exec(compile(task.upstream_test, "<pinned-test>", "exec"), namespace)
                    if suite == "normal":
                        namespace["check"](namespace[task.public.entry_point])
                    outcome, assertion = "pass", None
                except AssertionError as exc:
                    outcome, assertion = "fail", str(exc)
                if outcome != expected[number][name]:
                    raise RuntimeError(
                        f"Unexpected {suite}/{number}/{name}: {outcome}; assertion={assertion}"
                    )
                extra = untested_input_observation(number, namespace[task.public.entry_point])
                if number == 130 and name == "fixed_five_qubits":
                    if extra["returned_qubits"] != 5:
                        raise RuntimeError("Fixed-width fixture was not constructed as intended")
                if number == 131 and name == "fixed_cairo_backend":
                    if extra["returned_qubits"] == extra["expected_qubits"]:
                        raise RuntimeError("Fixed-backend fixture was not constructed as intended")
                observations.append(
                    {
                        "suite": suite,
                        "task_id": task.public.task_id,
                        "task_digest": task.digest,
                        "case": name,
                        "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
                        "outcome": outcome,
                        "assertion": assertion,
                        "untested_input": extra,
                    }
                )
    print(
        json.dumps(
            {
                "kind": "graybench_task130_131_exact_oracle_probe_v1",
                "scope": "Authored exact-test diagnostic, not protected judging or a model score",
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "cases": observations,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
