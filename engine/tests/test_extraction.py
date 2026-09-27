import ast

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


def test_v2_selects_unique_entrypoint_not_example_or_diagram(task):
    response = (
        "Here is the function.\n"
        "```python\nfrom math import sqrt\ndef answer(x):\n    return sqrt(x)\n```\n"
        "Example:\n```python\nprint(answer(9))\n```\n"
        "Output:\n```\n┌───┐\n```"
    )
    assert extract(response, task).error == "Expected one unambiguous Python code block"
    result = extract(response, task, policy="unique_entrypoint_fence_v2")
    assert result.error is None
    assert result.method == "unique_entrypoint_fence_v2"
    assert result.code == "from math import sqrt\ndef answer(x):\n    return sqrt(x)\n"
    assert result.public_prefix == ""


def test_v2_multifence_accepts_crlf_without_changing_v1(task):
    response = (
        "```python\r\ndef answer(x): return x + 1\r\n```\r\n"
        "```python\r\nprint(answer(2))\r\n```\r\n"
    )
    assert extract(response, task).error is not None
    result = extract(response, task, policy="unique_entrypoint_fence_v2")
    assert result.error is None
    assert result.code == "def answer(x): return x + 1\r\n"


def test_v2_rejects_multiple_entrypoint_blocks(task):
    response = "```python\ndef answer(x): return 1\n```\n```python\ndef answer(x): return 2\n```"
    assert extract(response, task, policy="unique_entrypoint_fence_v2").error is not None


def test_v2_rejects_alternative_assignment_to_entrypoint(task):
    response = "```python\ndef answer(x): return 1\n```\n```python\nanswer = lambda x: 2\n```"
    assert extract(response, task, policy="unique_entrypoint_fence_v2").error is not None


def test_v2_rejects_two_definitions_in_one_block(task):
    response = (
        "```python\ndef answer(x): return 1\ndef answer(x): return 2\n```\n"
        "```python\nprint(answer(3))\n```"
    )
    assert extract(response, task, policy="unique_entrypoint_fence_v2").error is not None


def test_v2_rejects_unmatched_or_nested_fences(task):
    for response in (
        "```python\ndef answer(x): return x\n```\n```python\nprint(answer(1))",
        "```python\ndef answer(x): return x\n```python\n```",
    ):
        assert extract(response, task, policy="unique_entrypoint_fence_v2").error is not None


def test_v2_rejects_malformed_alternative_entrypoint(task):
    for alternative in (
        "def answer(x) return x + 1",
        "def answer x:",
        "answer +=",
        "class answer",
    ):
        response = f"```python\ndef answer(x): return x\n```\n```python\n{alternative}\n```"
        assert extract(response, task, policy="unique_entrypoint_fence_v2").error is not None


def test_v2_classifies_nul_containing_answer_as_candidate_format_error(task):
    response = "```python\ndef answer(x): return x\x00\n```\n```python\nprint('example')\n```"
    result = extract(response, task, policy="unique_entrypoint_fence_v2")
    assert result.method == "rejected"
    assert result.error is not None


def test_v2_classifies_surrogate_answer_as_candidate_format_error(task):
    response = "```python\ndef answer(x): return x\ud800\n```\n```python\nprint('example')\n```"
    result = extract(response, task, policy="unique_entrypoint_fence_v2")
    assert result.method == "rejected"
    assert result.error is not None


def test_v2_classifies_unencodable_raw_and_single_fence_as_candidate_format_error(task):
    for response in (
        "def answer(x): return x\ud800",
        "```python\ndef answer(x): return x\ud800\n```",
    ):
        result = extract(response, task, policy="unique_entrypoint_fence_v2")
        assert result.method == "rejected"
        assert result.error is not None


def test_v2_classifies_parser_value_error_in_normal_raw_and_single_fence(monkeypatch):
    parse = ast.parse

    def value_error_for_nul(source, *args, **kwargs):
        if "\x00" in source:
            raise ValueError("embedded null")
        return parse(source, *args, **kwargs)

    monkeypatch.setattr("graybench.extraction.ast.parse", value_error_for_nul)
    for response in (
        "    return sqrt(x)\x00\n",
        "```python\n    return sqrt(x)\x00\n```",
    ):
        result = extract(response, normal(), policy="unique_entrypoint_fence_v2")
        assert result.method == "rejected"
        assert result.error is not None


def test_v2_rejects_hidden_entrypoint_bindings(task):
    alternatives = (
        "match 1:\n    case answer: pass",
        "try: pass\nexcept Exception as answer: pass",
        "@(answer := lambda x: x + 1)\ndef helper(): pass",
        "class Helper:\n    global answer\n    answer = lambda x: x + 1",
        "class Outer:\n    class Inner:\n        global answer\n        answer = 2",
        "values = [(answer := x) for x in range(3)]",
        "from math import *",
    )
    for alternative in alternatives:
        response = f"```python\ndef answer(x): return x\n```\n```python\n{alternative}\n```"
        assert extract(response, task, policy="unique_entrypoint_fence_v2").error is not None


def test_v2_ignores_bindings_local_to_example_blocks(task):
    examples = (
        "values = [answer for answer in range(3)]",
        "helper = lambda: (answer := 1)",
        "class Helper:\n    answer = 1",
        "class Helper:\n    def answer(self): pass",
        "def helper(answer): return answer",
    )
    for example in examples:
        response = f"```python\ndef answer(x): return x\n```\n```python\n{example}\n```"
        result = extract(response, task, policy="unique_entrypoint_fence_v2")
        assert result.error is None
        assert result.code == "def answer(x): return x\n"


def test_v2_does_not_supply_hard_imports(task):
    response = "```python\ndef answer(x): return sqrt(x)\n```\n```python\nprint(answer(9))\n```"
    result = extract(response, task, policy="unique_entrypoint_fence_v2")
    assert result.error is None
    assert result.public_prefix == ""
    assert "from math" not in result.code


def test_v2_keeps_raw_and_single_fence_behavior():
    for response in ("    return sqrt(x)\n", "```python\n    return sqrt(x)\n```"):
        old = extract(response, normal())
        new = extract(response, normal(), policy="unique_entrypoint_fence_v2")
        assert (new.code, new.public_prefix, new.error) == (
            old.code,
            old.public_prefix,
            old.error,
        )
