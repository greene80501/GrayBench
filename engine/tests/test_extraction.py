from graybench.contracts import PublicTask
from graybench.extraction import extract


def normal():
    return PublicTask(
        suite="normal",
        task_id="test",
        family_id="test",
        prompt='from math import sqrt\ndef answer(x):\n    """Square root."""\n',
        entry_point="answer",
        prompt_format="function_completion",
    )


def test_body_completion_keeps_exact_public_prompt():
    result = extract("    return sqrt(x)\n", normal())
    assert result.code == normal().prompt + "    return sqrt(x)\n"
    assert result.public_prefix == ""


def test_full_function_keeps_public_imports_and_future_import_semantics():
    result = extract(
        "from __future__ import annotations\ndef answer(x):\n    return sqrt(x)", normal()
    )
    namespace = {}
    exec(compile(result.public_prefix, "prefix", "exec"), namespace)
    exec(compile(result.code, "candidate", "exec"), namespace)
    assert namespace["answer"](9) == 3


def test_multiple_answers_are_not_selected_using_tests(task):
    result = extract(
        "```python\ndef answer(x): return 1\n```\n```python\ndef answer(x): return 2\n```", task
    )
    assert result.error is not None


def test_helpers_are_not_discarded(task):
    code = "def helper(x): return x+1\ndef answer(x): return helper(x)"
    assert extract(code, task).code == code


def test_no_hidden_import_help_for_hard_suite(task):
    result = extract("def answer(x): return sqrt(x)", task)
    assert result.public_prefix == ""


def test_empty_answer_is_explicit(task):
    assert extract("", task).error == "Empty answer"
