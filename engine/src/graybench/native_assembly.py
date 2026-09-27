"""Host-side assembly of one frozen native QHE candidate and pinned test."""

import ast
import hashlib

from graybench.contracts import ExtractionPolicy
from graybench.datasets import JudgeTask
from graybench.extraction import extract


def check_test_shape(task: JudgeTask) -> None:
    """Require the pinned normal/hard top-level check shape without rewriting tests."""
    try:
        body = ast.parse(task.upstream_test).body
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise ValueError("Pinned test is not parseable Python") from exc
    definitions = [
        node for node in body if isinstance(node, ast.FunctionDef) and node.name == "check"
    ]
    calls = [
        node.value
        for node in body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "check"
    ]
    if len(definitions) != 1 or len(calls) != (task.public.suite == "hard"):
        raise ValueError("Unexpected pinned top-level check shape")
    if calls:
        call = calls[0]
        if (
            len(call.args) != 1
            or not isinstance(call.args[0], ast.Name)
            or call.args[0].id != task.public.entry_point
            or call.keywords
        ):
            raise ValueError("Pinned hard check must invoke the declared entry point once")


def native_payload(task: JudgeTask, completion: str, extraction: ExtractionPolicy) -> dict:
    """Prepare exact candidate/test bytes; never include a canonical solution."""
    check_test_shape(task)
    extracted = extract(completion, task.public, extraction)
    result = {
        "protocol": "qhe-native-worker-v1",
        "suite": task.public.suite,
        "entry_point": task.public.entry_point,
        "task_digest": task.digest,
        "completion_sha256": hashlib.sha256(completion.encode("utf-8")).hexdigest(),
        "extraction_method": extracted.method,
        "test": task.upstream_test,
    }
    if extracted.error:
        return {**result, "extraction_error": extracted.error}
    return {
        **result,
        "code": extracted.code,
        "public_prefix": extracted.public_prefix,
        "code_sha256": hashlib.sha256(extracted.code.encode("utf-8")).hexdigest(),
    }
