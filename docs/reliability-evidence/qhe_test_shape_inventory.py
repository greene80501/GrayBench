"""Static execution-shape audit of the pinned QHE tests; no candidate runs."""

import argparse
import ast
import hashlib
import json
from pathlib import Path

from graybench.datasets import PINS, load_suite
from graybench.identity import identity


def inspect_task(task):
    tree = ast.parse(task.upstream_test)
    checks = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "check"
    ]
    calls = [
        node
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "check"
    ]
    other = [
        type(node).__name__
        for node in tree.body
        if not isinstance(node, (ast.Import, ast.ImportFrom))
        and node not in checks
        and node not in calls
    ]
    check = checks[0] if len(checks) == 1 else None
    args = check.args if check else None
    one_plain_arg = bool(
        args
        and not args.posonlyargs
        and len(args.args) == 1
        and args.args[0].arg == "candidate"
        and not args.vararg
        and not args.kwarg
        and not args.kwonlyargs
        and not args.defaults
        and not args.kw_defaults
    )
    matching_call = bool(
        len(calls) == 1
        and len(calls[0].value.args) == 1
        and isinstance(calls[0].value.args[0], ast.Name)
        and calls[0].value.args[0].id == task.public.entry_point
        and not calls[0].value.keywords
    )
    assertion_count = (
        sum(isinstance(node, ast.Assert) for node in ast.walk(check)) if check else 0
    )
    expected = (
        len(checks) == 1
        and one_plain_arg
        and assertion_count > 0
        and not other
        and (not calls if task.public.suite == "normal" else matching_call)
    )
    return {
        "task_key": f"{task.public.suite}/{task.public.task_id}",
        "task_digest": task.digest,
        "test_sha256": hashlib.sha256(task.upstream_test.encode()).hexdigest(),
        "check_definitions": len(checks),
        "check_has_one_plain_argument": one_plain_arg,
        "check_assertions": assertion_count,
        "top_level_check_calls": len(calls),
        "hard_call_matches_entry_point": matching_call if calls else None,
        "other_top_level_nodes": other,
        "expected_shape": expected,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    suites = {}
    for suite in ("normal", "hard"):
        tasks = load_suite(suite, args.cache)
        rows = [inspect_task(task) for task in tasks]
        failures = [row for row in rows if not row["expected_shape"]]
        suites[suite] = {
            "task_count": len(rows),
            "dataset_digest": identity([task.digest for task in tasks]),
            "shape_records_digest": identity(rows),
            "expected_shape_count": len(rows) - len(failures),
            "check_assertions_min": min(row["check_assertions"] for row in rows),
            "check_assertions_max": max(row["check_assertions"] for row in rows),
            "anomalies": failures,
        }
    print(
        json.dumps(
            {
                "kind": "graybench_qhe_test_shape_inventory_v1",
                "scope": "Static pinned-test AST audit, not execution or task admission",
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "dataset_pins": PINS,
                "suites": suites,
            },
            indent=2,
        )
    )
    if any(item["anomalies"] for item in suites.values()):
        raise RuntimeError("Pinned tests contain a nonstandard execution shape")


if __name__ == "__main__":
    main()
