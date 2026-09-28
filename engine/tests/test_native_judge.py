import hashlib
import os
from pathlib import Path

import pytest

from graybench.contracts import PublicTask
from graybench.datasets import PINS, JudgeTask, load_suite
from graybench.native_assembly import native_payload
from graybench.native_cohort import NativeCohort, freeze_native_cohort
from graybench.native_judge import NativeJudge, native_command
from graybench.provenance import source_manifest

IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")
CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
DOCKER = os.environ.get("GRAYBENCH_TEST_DOCKER", "docker")
WORKER = Path(__file__).parents[1] / "src/graybench/native_worker.py"


def synthetic_task():
    return JudgeTask(
        public=PublicTask(
            suite="hard",
            task_id="qiskitHumanEval/0",
            family_id="qhe/0",
            prompt="Return one using answer().",
            entry_point="answer",
            prompt_format="standalone_function",
        ),
        canonical_solution="def answer(): return 1",
        upstream_test="def check(candidate): assert candidate() == 1\ncheck(answer)",
        upstream_difficulty="fixture",
    )


def synthetic_cohort(task):
    key = f"hard/{task.public.task_id}"
    return NativeCohort(
        suite="hard",
        population="custom_development",
        label="fixture",
        task_keys=(key,),
        task_digests={key: task.digest},
        excluded={
            f"hard/qiskitHumanEval/{number}": "out_of_scope_development" for number in range(1, 151)
        },
        dataset_pin=PINS["hard"],
        image="sha256:" + "a" * 64,
        extraction="raw_or_single_python_fence_v1",
        source_digest=source_manifest()["digest"],
    )


def test_native_command_has_isolation_and_bounded_resources(tmp_path):
    command = native_command(
        docker="docker",
        image="sha256:" + "a" * 64,
        name="graybench-native-fixture",
        mount_dir=tmp_path,
        result_dir=tmp_path / "result",
        memory_bytes=2 * 1024**3,
        cpus=2,
        pids_limit=64,
        tmpfs_bytes=64 * 1024**2,
    )
    text = " ".join(command)
    assert command[:2] == ["docker", "run"]
    assert "-i" in command
    assert "--network none" in text
    assert "--read-only" in command
    assert "--cap-drop ALL" in text
    assert "--security-opt no-new-privileges" in text
    assert "--user 65534:65534" in text
    assert "--memory 2147483648" in text
    assert "--cpus 2" in text
    assert "--pids-limit 64" in text
    assert "--tmpfs /tmp:rw,nosuid,nodev,mode=1777,size=67108864" in text
    assert "readonly" in text
    assert "target=/result" in text
    assert "docker.sock" not in text and "docker_engine" not in text
    assert command[-4:] == [
        "python",
        "-u",
        "/native/native_worker.py",
        "/result/result.json",
    ]


def test_native_manifest_binds_task_worker_image_and_limits(tmp_path):
    task = synthetic_task()
    cohort = synthetic_cohort(task)
    judge = NativeJudge(cohort, (task,), cache=tmp_path)
    _, manifest = judge.configuration(task)
    assert manifest["track"] == "qhe-pinned-native-v1"
    assert manifest["suite"] == "hard"
    assert manifest["cohort_digest"] == cohort.digest
    assert manifest["task_digest"] == task.digest
    assert manifest["image"] == cohort.image
    assert manifest["worker_sha256"] == hashlib.sha256(WORKER.read_bytes()).hexdigest()
    assert manifest["release_eligible"] is False
    assert manifest["timeout_seconds"] > 0
    assert manifest["output_limit"] > 0


def test_unencodable_completion_is_a_format_error_with_stable_digest():
    payload = native_payload(synthetic_task(), "\ud800", "unique_entrypoint_fence_v2")
    assert payload["extraction_error"] == "Response is not UTF-8 encodable"
    assert (
        payload["completion_sha256"]
        == hashlib.sha256("\ud800".encode("utf-8", "surrogatepass")).hexdigest()
    )
    assert payload["completion_digest_encoding"] == "utf-8-surrogatepass"


@pytest.mark.skipif(not CACHE, reason="Pinned source cache not supplied")
def test_native_judge_records_unencodable_answer_without_launching_candidate():
    cache = Path(CACHE)
    task = load_suite("normal", cache)[0]
    cohort = freeze_native_cohort(
        (task,),
        cache=cache,
        suite="normal",
        population="custom_development",
        image=IMAGE or "sha256:" + "a" * 64,
        extraction="exact_prompt_suffix_v1",
        label="unicode fixture",
        excluded={
            f"normal/qiskitHumanEval/{number}": "out_of_scope_development"
            for number in range(1, 151)
        },
    )
    result = NativeJudge(cohort, (task,), cache=cache, docker="no-such-docker").evaluate(
        task, "\ud800"
    )
    assert result.outcome == "candidate_error"
    assert result.evidence["completion_digest_encoding"] == "utf-8-surrogatepass"


def test_native_result_rejects_symlink_and_oversized_file(tmp_path):
    task = synthetic_task()
    judge = NativeJudge(synthetic_cohort(task), (task,), cache=tmp_path)
    target = tmp_path / "target.json"
    target.write_text('{"status":"pass","phase":"test","completed":true}')
    linked = tmp_path / "result.json"
    try:
        linked.symlink_to(target)
    except OSError:
        pass
    else:
        assert judge._result(linked, "a" * 64, {}).outcome == "infrastructure_error"
        linked.unlink()
    linked.write_bytes(b"x" * (16 * 1024 + 1))
    assert judge._result(linked, "a" * 64, {}).outcome == "infrastructure_error"


@pytest.mark.skipif(not IMAGE or not CACHE, reason="Pinned native Docker image/cache not supplied")
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_pinned_reference_and_wrong_control(suite):
    cache = Path(CACHE)
    task = load_suite(suite, cache)[4]
    excluded = {
        f"{suite}/qiskitHumanEval/{number}": "out_of_scope_development"
        for number in range(151)
        if number != 4
    }
    cohort = freeze_native_cohort(
        (task,),
        cache=cache,
        suite=suite,
        population="custom_development",
        image=IMAGE,
        extraction="raw_or_single_python_fence_v1",
        label="task4-fixture",
        excluded=excluded,
    )
    judge = NativeJudge(cohort, (task,), cache=cache, docker=DOCKER, timeout=30)
    assert judge.evaluate(task, task.canonical_solution).outcome == "pass"
    wrong = (
        "\n    return QuantumCircuit(2)\n"
        if suite == "normal"
        else "from qiskit import QuantumCircuit\ndef create_unitary_from_matrix():\n"
        "    return QuantumCircuit(2)\n"
    )
    assert judge.evaluate(task, wrong).outcome == "fail"


@pytest.mark.skipif(not IMAGE or not CACHE, reason="Pinned native Docker image/cache not supplied")
def test_exact_suffix_native_condition_accepts_suffix_and_runs_raw_replacement():
    cache = Path(CACHE)
    task = load_suite("normal", cache)[4]
    excluded = {
        f"normal/qiskitHumanEval/{number}": "out_of_scope_development"
        for number in range(151)
        if number != 4
    }
    cohort = freeze_native_cohort(
        (task,),
        cache=cache,
        suite="normal",
        population="custom_development",
        image=IMAGE,
        extraction="exact_prompt_suffix_v1",
        label="literal task4 fixture",
        excluded=excluded,
    )
    judge = NativeJudge(cohort, (task,), cache=cache, docker=DOCKER, timeout=30)
    assert judge.evaluate(task, task.canonical_solution).outcome == "pass"
    replacement = "\ndef create_unitary_from_matrix():\n    return QuantumCircuit(2)\n"
    result = judge.evaluate(task, replacement)
    assert result.outcome == "fail", result.evidence


@pytest.mark.skipif(not IMAGE or not CACHE, reason="Pinned native Docker image/cache not supplied")
def test_early_exit_and_forged_stdout_are_not_passing_results():
    cache = Path(CACHE)
    task = load_suite("hard", cache)[4]
    excluded = {
        f"hard/qiskitHumanEval/{number}": "out_of_scope_development"
        for number in range(151)
        if number != 4
    }
    cohort = freeze_native_cohort(
        (task,),
        cache=cache,
        suite="hard",
        population="custom_development",
        image=IMAGE,
        extraction="raw_or_single_python_fence_v1",
        label="early-exit-fixture",
        excluded=excluded,
    )
    judge = NativeJudge(cohort, (task,), cache=cache, docker=DOCKER, timeout=30)
    answer = (
        "import os\n"
        "def create_unitary_from_matrix():\n"
        '    os.write(1, b\'{"status":"pass"}\')\n'
        "    os._exit(0)\n"
    )
    result = judge.evaluate(task, answer)
    assert result.outcome != "pass"
    assert result.evidence["reason"] == "missing_native_completion"


@pytest.mark.skipif(not IMAGE or not CACHE, reason="Pinned native Docker image/cache not supplied")
def test_candidate_output_limit_blocks_a_passing_test():
    cache = Path(CACHE)
    task = load_suite("hard", cache)[4]
    excluded = {
        f"hard/qiskitHumanEval/{number}": "out_of_scope_development"
        for number in range(151)
        if number != 4
    }
    cohort = freeze_native_cohort(
        (task,),
        cache=cache,
        suite="hard",
        population="custom_development",
        image=IMAGE,
        extraction="raw_or_single_python_fence_v1",
        label="output-fixture",
        excluded=excluded,
    )
    judge = NativeJudge(cohort, (task,), cache=cache, docker=DOCKER, timeout=30, output_limit=1024)
    answer = "import os\nos.write(1, b'x' * 4096)\n" + task.canonical_solution
    result = judge.evaluate(task, answer)
    assert result.outcome == "candidate_error"
    assert result.evidence["reason"] == "native_output_limit"


@pytest.mark.skipif(not IMAGE or not CACHE, reason="Pinned native Docker image/cache not supplied")
def test_native_deadline_stops_a_nonterminating_candidate():
    cache = Path(CACHE)
    task = load_suite("hard", cache)[4]
    excluded = {
        f"hard/qiskitHumanEval/{number}": "out_of_scope_development"
        for number in range(151)
        if number != 4
    }
    cohort = freeze_native_cohort(
        (task,),
        cache=cache,
        suite="hard",
        population="custom_development",
        image=IMAGE,
        extraction="raw_or_single_python_fence_v1",
        label="timeout-fixture",
        excluded=excluded,
    )
    judge = NativeJudge(cohort, (task,), cache=cache, docker=DOCKER, timeout=4)
    answer = "def create_unitary_from_matrix():\n    while True:\n        pass\n"
    result = judge.evaluate(task, answer)
    assert result.outcome == "timeout"
    assert result.evidence["reason"] == "native_timeout"
