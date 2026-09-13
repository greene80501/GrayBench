from dataclasses import replace

import pytest

from graybench.dataset import Dataset, Task, SuiteType
from graybench.execution import ExecutionHarness
from graybench.execution.code_extractor import CodeExtractor


def example(suite=SuiteType.NORMAL):
    return Task(
        task_id="test/0",
        prompt='def answer(x):\n    """Return x plus one."""',
        entry_point="answer",
        test="def check(candidate):\n    assert candidate(2) == 3",
        canonical_solution="\n    return x + 1\n",
        suite=suite,
    )


def test_normal_accepts_body_completion():
    result = ExecutionHarness().execute(example(), "    return x + 1")
    assert result.passed, result.stderr


def test_canonical_normal_includes_public_prefix():
    assert ExecutionHarness().validate_with_canonical(example()).passed


def test_hard_does_not_supply_missing_function():
    assert not ExecutionHarness().execute(example(SuiteType.HARD), "    return x + 1").passed


def test_early_exit_is_not_a_pass():
    assert (
        not ExecutionHarness().execute(example(), "def answer(x):\n    raise SystemExit(0)").passed
    )


def test_test_is_executed_once():
    task = replace(
        example(SuiteType.HARD),
        test="def check(candidate):\n    assert candidate(2) == 3\ncheck(answer)",
    )
    code = "calls = 0\ndef answer(x):\n    global calls\n    calls += 1\n    assert calls == 1\n    return x + 1"
    result = ExecutionHarness().execute(task, code)
    assert result.passed, result.stderr


def test_missing_test_check_fails_closed():
    with pytest.raises(ValueError, match="check"):
        ExecutionHarness().execute(
            replace(example(), test="pass"), "def answer(x):\n    return x + 1"
        )


def test_hash_covers_tests_and_full_prompts():
    task = example()
    original = Dataset([task], "normal").dataset_hash
    assert (
        original != Dataset([replace(task, test=task.test + "\n# change")], "normal").dataset_hash
    )
    assert (
        original
        != Dataset([replace(task, prompt=task.prompt + " " * 100 + "x")], "normal").dataset_hash
    )


def test_extractor_preserves_helpers_and_constants():
    code = "VALUE = 1\ndef answer(x):\n    return helper(x)\ndef helper(x):\n    return x + VALUE"
    assert CodeExtractor().extract(code, "answer").code == code


def test_generated_code_does_not_inherit_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "not-a-real-key")
    env = ExecutionHarness()._get_execution_env()
    assert "OPENAI_API_KEY" not in env and "GOOGLE_API_KEY" not in env


def test_python_block_after_shell_installation_is_not_lost():
    text = "```bash\npip install qiskit\n```\nExplanation\n```python\ndef answer(x):\n    return x + 1\n```"
    result = ExecutionHarness().execute(example(SuiteType.HARD), text)
    assert result.passed, result.extracted_code


def test_all_python_blocks_are_preserved_after_other_languages():
    text = "```bash\necho ignored\n```\n```python\nVALUE = 1\n```\n```python\ndef answer(x):\n    return x + VALUE\n```"
    result = ExecutionHarness().execute(example(SuiteType.HARD), text)
    assert result.passed, result.extracted_code
