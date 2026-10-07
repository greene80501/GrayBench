"""Source-bound paired QHE audit; AST equality is not semantic certification.

Only the task-41 diagnostic executes code: the pinned check function against
four fixed, authored Operator values. No model or arbitrary candidate is run.
"""

import argparse
import ast
import hashlib
import json
import platform
import re
from importlib.metadata import version
from pathlib import Path

from graybench.datasets import PINS, load_suite
from graybench.identity import canonical, identity
from graybench.provenance import source_manifest


def sha(value):
    return hashlib.sha256(value).hexdigest()


def dump(nodes):
    return ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False)


def function(source, name):
    matches = [
        n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name
    ]
    if len(matches) != 1:
        raise ValueError("Expected exactly one declared function")
    return matches[0]


def lines(text):
    # Preserve every internal line and word; discard only boundary indentation
    # and trailing spaces. This does not normalize prose or claim equivalence.
    return [line.strip() for line in text.strip().splitlines()]


class RemoveImports(ast.NodeTransformer):
    def visit_Import(self, node):
        return None

    def visit_ImportFrom(self, node):
        return None


def inspect_pair(normal, hard):
    if (
        normal.public.suite != "normal"
        or hard.public.suite != "hard"
        or normal.public.task_id != hard.public.task_id
        or normal.public.family_id != hard.public.family_id
        or normal.public.entry_point != hard.public.entry_point
    ):
        raise ValueError("Pair identity differs")
    entry = normal.public.entry_point
    prefix = function(normal.public.prompt, entry)
    arguments = prefix.args
    if arguments.posonlyargs or arguments.vararg or arguments.kwarg or arguments.kwonlyargs:
        raise ValueError("Unsupported signature; review explicitly")
    names = [arg.arg for arg in arguments.args]
    suffix = (
        f"You must implement this using a function named `{entry}` "
        f"with the following arguments: {', '.join(names)}."
        if names
        else f"You must implement this using a function named `{entry}` with no arguments."
    )
    hard_lines = hard.public.prompt.strip().splitlines()
    if hard_lines[-1] != suffix:
        raise ValueError("Unexpected hard function declaration")
    doc = ast.get_docstring(prefix, clean=False)
    if doc is None:
        raise ValueError("Normal public requirements missing")
    normal_lines, hard_requirements = lines(doc), lines("\n".join(hard_lines[:-1]))
    ncheck, hcheck = function(normal.upstream_test, "check"), function(hard.upstream_test, "check")
    normal_reference = function(normal.public.prompt + "\n" + normal.canonical_solution, entry)
    hard_reference = function(hard.canonical_solution, entry)
    nbody, hbody = list(normal_reference.body), list(hard_reference.body)
    for body in (nbody, hbody):
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)
    raw_checks = [dump([ncheck]), dump([hcheck])]
    # This second comparison is diagnostic only: import scope/movement can
    # change behavior. Never label it semantic equality.
    without_imports = [
        ast.dump(RemoveImports().visit(ast.parse(source)), include_attributes=False)
        for source in (ast.unparse(ncheck), ast.unparse(hcheck))
    ]
    return {
        "task_id": normal.public.task_id,
        "family_id": normal.public.family_id,
        "normal_task_digest": normal.digest,
        "hard_task_digest": hard.digest,
        "normal_public_digest": normal.public.digest,
        "hard_public_digest": hard.public.digest,
        "normal_test_sha256": sha(normal.upstream_test.encode()),
        "hard_test_sha256": sha(hard.upstream_test.encode()),
        "normal_reference_sha256": sha(normal.canonical_solution.encode()),
        "hard_reference_sha256": sha(hard.canonical_solution.encode()),
        "normal_requirement_lines": normal_lines,
        "hard_requirement_lines": hard_requirements,
        "requirement_lines_equal": normal_lines == hard_requirements,
        "normal_signature": {
            "argument_names": names,
            "annotations": {
                arg.arg: ast.unparse(arg.annotation) for arg in arguments.args if arg.annotation
            },
            "defaults": [ast.unparse(default) for default in arguments.defaults],
            "return_annotation": ast.unparse(prefix.returns) if prefix.returns else None,
        },
        "normal_imports": [
            ast.unparse(node)
            for node in ast.parse(normal.public.prompt).body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ],
        "hard_declared_arguments": names,
        "check_ast_equal": raw_checks[0] == raw_checks[1],
        "check_ast_digests": [sha(check.encode()) for check in raw_checks],
        "check_without_imports_ast_equal": without_imports[0] == without_imports[1],
        "check_without_imports_ast_digests": [sha(check.encode()) for check in without_imports],
        "reference_body_ast_equal": dump(nbody) == dump(hbody),
        "reference_body_ast_digests": [sha(dump(body).encode()) for body in (nbody, hbody)],
        "semantic_adequacy": "unreviewed",
    }


def task41_probe(normal, hard):
    import numpy as np
    from qiskit.quantum_info import Operator, Pauli

    if (normal.digest, hard.digest) != (
        "2eaae6d3fb7fdef5399ed1d78dd6aee8b0280db0f01750fe203459e5e806109e",
        "af3f1c7f69f3fb60817415a834e5a4a12c0999f4bd3022b109d0cd3c06d2b50f",
    ):
        raise ValueError("Diagnostic requires exact pinned task 41")
    checks = []
    for task in (normal, hard):
        # Execute only the exact pinned check definition; the hard file's
        # implicit check(entry_point) is deliberately not executed separately.
        check = function(task.upstream_test, "check")
        namespace = {"Operator": Operator, "Pauli": Pauli, "np": np}
        exec(
            compile(ast.Module(body=[check], type_ignores=[]), "pinned-task41-check", "exec"),
            namespace,
        )
        checks.append(namespace["check"])
    controls = []
    for label, qargs in (("YX", [0, 2]), ("XZ", [0, 2]), ("YX", [0, 1]), ("YX", [1, 2])):
        value = Operator(np.eye(8)).compose(Operator(Pauli(label)), qargs=qargs, front=True)
        outcomes = []
        for check in checks:
            try:
                check(lambda value=value: value)
            except AssertionError:
                outcomes.append("fail")
            else:
                outcomes.append("pass")
        matrix = [[[float(z.real), float(z.imag)] for z in row] for row in value.data]
        controls.append(
            {
                "pauli": label,
                "qargs": qargs,
                "matrix_digest": identity(matrix),
                "normal": outcomes[0],
                "hard": outcomes[1],
            }
        )
    return {
        "scope": (
            "trusted fixed values against pinned check functions in the host process; "
            "no sandbox qualification"
        ),
        "source_task_digests": [normal.digest, hard.digest],
        "controls": controls,
        "public_qargs_declared": False,
        "publication_eligible": False,
    }


def build(cache):
    normal, hard = load_suite("normal", cache), load_suite("hard", cache)
    by_suite = [{t.public.task_id: t for t in tasks} for tasks in (normal, hard)]
    expected = {f"qiskitHumanEval/{i}" for i in range(151)}
    if any(
        len(tasks) != 151 or set(index) != expected
        for tasks, index in zip((normal, hard), by_suite, strict=True)
    ):
        raise ValueError("Expected the complete 151-pair population")
    pairs = [
        inspect_pair(*(index[f"qiskitHumanEval/{i}"] for index in by_suite)) for i in range(151)
    ]
    summary = {"pair_count": len(pairs), "task_record_count": 2 * len(pairs)}
    for label, flag in (
        ("requirement_differences", "requirement_lines_equal"),
        ("check_ast_differences", "check_ast_equal"),
        ("check_without_imports_ast_differences", "check_without_imports_ast_equal"),
        ("reference_body_ast_differences", "reference_body_ast_equal"),
    ):
        summary[label] = [
            int(re.search(r"/(\d+)$", row["task_id"])[1]) for row in pairs if not row[flag]
        ]
    return {
        "kind": "graybench_qhe_pair_audit_v1",
        "scope": "All pinned pairs; text/AST diagnostics, not semantic certification",
        "publication_eligible": False,
        "independent_review": False,
        "dataset_pins": PINS,
        "engine_source_digest": source_manifest()["digest"],
        "script_sha256": sha(Path(__file__).read_bytes()),
        "environment": {
            "python": platform.python_version(),
            "qiskit": version("qiskit"),
            "numpy": version("numpy"),
        },
        "summary": summary,
        "pairs": pairs,
        "task41_probe": task41_probe(*(index["qiskitHumanEval/41"] for index in by_suite)),
    }


def verify(report, cache):
    if canonical(report) != canonical(build(cache)):
        raise ValueError("Saved pair audit differs from exact recreation")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build(args.cache)
    if args.check:
        verify(json.loads(args.output.read_bytes()), args.cache)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
