import json
import subprocess
import sys
from pathlib import Path

import pytest

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.native_assembly import check_test_shape, native_payload

WORKER = Path(__file__).parents[1] / "src/graybench/native_worker.py"
POLICY = "raw_or_single_python_fence_v1"


def task(suite="normal", *, test=None, prompt=None):
    if prompt is None:
        prompt = (
            'from math import sqrt\ndef answer(x):\n    """Square root."""\n'
            if suite == "normal"
            else "Return the square root using answer(x)."
        )
    if test is None:
        test = "def check(candidate):\n    assert candidate(9) == 3\n"
        if suite == "hard":
            test += "check(answer)\n"
    return JudgeTask(
        public=PublicTask(
            suite=suite,
            task_id="qiskitHumanEval/0",
            family_id="qhe/0",
            prompt=prompt,
            entry_point="answer",
            prompt_format="function_completion" if suite == "normal" else "standalone_function",
        ),
        canonical_solution="return sqrt(x)",
        upstream_test=test,
        upstream_difficulty="fixture",
    )


def completion(suite, body):
    return body if suite == "normal" else "from math import sqrt\ndef answer(x):\n" + body


def invoke(payload, tmp_path):
    result_file = tmp_path / "result.json"
    process = subprocess.run(
        [sys.executable, str(WORKER), str(result_file)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    result = json.loads(result_file.read_text()) if result_file.exists() else None
    return process, result


@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_reference_and_wrong_answer_preserve_original_test(suite, tmp_path):
    original = task(suite)
    check_test_shape(original)
    good = native_payload(original, completion(suite, "    return sqrt(x)\n"), POLICY)
    assert good["test"] == original.upstream_test
    assert good["task_digest"] == original.digest
    assert good["suite"] == suite
    if suite == "normal":
        assert good["code"].startswith(original.public.prompt)
    process, result = invoke(good, tmp_path)
    assert process.returncode == 0
    assert result["status"] == "pass"

    (tmp_path / "result.json").unlink()
    bad = native_payload(original, completion(suite, "    return 0\n"), POLICY)
    process, result = invoke(bad, tmp_path)
    assert process.returncode == 0
    assert result["status"] == "fail"


def test_unexpected_or_duplicate_top_level_check_is_rejected():
    duplicate = task(
        "hard",
        test="def check(candidate): pass\ncheck(answer)\ncheck(answer)\n",
    )
    wrong_target = task("hard", test="def check(candidate): pass\ncheck(other)\n")
    premature = task("normal", test="def check(candidate): pass\ncheck(answer)\n")
    for invalid in (duplicate, wrong_target, premature):
        with pytest.raises(ValueError):
            check_test_shape(invalid)


def test_full_normal_function_keeps_public_imports(tmp_path):
    original = task("normal")
    payload = native_payload(original, "def answer(x):\n    return sqrt(x)\n", POLICY)
    assert payload["public_prefix"] == "from math import sqrt\n"
    process, result = invoke(payload, tmp_path)
    assert process.returncode == 0
    assert result["status"] == "pass"


@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_candidate_mutates_the_exact_object_seen_by_the_native_test(suite, tmp_path):
    test = (
        "def check(candidate):\n    values = [1]\n"
        "    candidate(values)\n    assert values == [1, 2]\n"
    )
    if suite == "hard":
        test += "check(answer)\n"
    original = task(
        suite,
        test=test,
        prompt=(
            'def answer(values):\n    """Append two."""\n'
            if suite == "normal"
            else "Append two to values with answer(values)."
        ),
    )
    answer = (
        "    values.append(2)\n"
        if suite == "normal"
        else "def answer(values):\n    values.append(2)\n"
    )
    process, result = invoke(native_payload(original, answer, POLICY), tmp_path)
    assert process.returncode == 0
    assert result["status"] == "pass"


def test_candidate_exit_and_stdout_forgery_leave_no_completion_result(tmp_path):
    original = task("hard")
    answer = (
        'import os\ndef answer(x):\n    os.write(1, b\'{"status": "pass"}\')\n    os._exit(0)\n'
    )
    process, result = invoke(native_payload(original, answer, POLICY), tmp_path)
    assert process.returncode == 0
    assert '{"status": "pass"}' in process.stdout
    assert result is None


def test_candidate_exception_is_not_a_test_assertion_failure(tmp_path):
    original = task("hard")
    answer = "def answer(x):\n    assert False, 'candidate assertion'\n"
    _, result = invoke(native_payload(original, answer, POLICY), tmp_path)
    assert result["status"] == "candidate_error"
    assert result["exception_type"] == "AssertionError"


def test_candidate_cannot_skip_pinned_test_by_rebinding_builtin_exec(tmp_path):
    original = task("hard")
    answer = (
        "import builtins\n"
        "builtins.exec = lambda *args, **kwargs: None\n"
        "def answer(x):\n"
        "    return 0\n"
    )
    _, result = invoke(native_payload(original, answer, POLICY), tmp_path)
    assert result["status"] != "pass"


def test_candidate_cannot_forge_result_by_rebinding_json_serializer(tmp_path):
    original = task("hard")
    answer = (
        "import json\n"
        "json.dumps = lambda *args, **kwargs: "
        '\'{"status":"pass","completed":true}\'\n'
        "def answer(x):\n"
        "    return 0\n"
    )
    _, result = invoke(native_payload(original, answer, POLICY), tmp_path)
    assert result["status"] != "pass"


def test_candidate_cannot_redirect_worker_result_around_forged_file(tmp_path):
    original = task("hard")
    answer = (
        "import pathlib, sys\n"
        "path = sys.argv[1]\n"
        'pathlib.Path(path).write_text(\'{"status":"pass","completed":true}\')\n'
        "sys.argv[1] = path + '.other'\n"
        "def answer(x):\n"
        "    return 0\n"
    )
    process, result = invoke(native_payload(original, answer, POLICY), tmp_path)
    assert not (process.returncode == 0 and result["status"] == "pass")


def test_extraction_error_is_explicit_before_worker_dispatch():
    original = task("hard")
    payload = native_payload(original, "", POLICY)
    assert payload["extraction_error"] == "Empty answer"
