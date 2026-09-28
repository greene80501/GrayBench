import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from graybench.contracts import PublicTask
from graybench.protected_value_contract import (
    ProtectedValueContract,
    ValueCall,
    ValueShape,
    validate_value,
)
from graybench.protected_value_runner import (
    ValueRunner,
    parse_value_response,
    value_command,
    value_payload,
)

IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE", "sha256:" + "a" * 64)
WORKER = Path(__file__).parents[1] / "src/graybench/protected_value_worker.py"


def contract(prompt_format="standalone_function"):
    return ProtectedValueContract(
        source_task_digest="a" * 64,
        public=PublicTask(
            suite="normal",
            task_id="qiskitHumanEval/20",
            family_id="qhe/20",
            prompt="Return the declared integer value with answer(n)."
            if prompt_format == "standalone_function"
            else "def answer(n):\n",
            entry_point="answer",
            prompt_format=prompt_format,
        ),
        positional=(ValueShape(kind="integer", minimum=0, maximum=20),),
        result=ValueShape(kind="integer", minimum=0, maximum=20),
    )


def worker(payload):
    return subprocess.run(
        [sys.executable, str(WORKER)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_value_shape_is_strict_and_bounded():
    shape = ValueShape(kind="integer", minimum=0, maximum=20)
    validate_value(4, shape)
    for value in (True, -1, 21, 4.2, "4"):
        with pytest.raises(ValueError):
            validate_value(value, shape)
    text = ValueShape(kind="string", max_length=4)
    with pytest.raises(ValueError):
        validate_value("12345", text)
    nested = ValueShape(kind="array", item=ValueShape(kind="integer"), max_items=2)
    with pytest.raises(ValueError):
        validate_value([1, 2, 3], nested)
    with pytest.raises(ValueError):
        validate_value([1, float("nan")], nested)
    validate_value(int("9" * 400), ValueShape(kind="number"))


def test_response_parser_rejects_duplicates_nonfinite_wrong_shape_and_count():
    spec = contract()
    for wire in (
        b'{"protocol":"protected-value-v1","completed":true,"values":[3],"values":[3]}',
        b'{"protocol":"protected-value-v1","completed":true,"values":[NaN]}',
        b'{"protocol":"protected-value-v1","completed":true,"values":[true]}',
        b'{"protocol":"protected-value-v1","completed":true,"values":[3,4]}',
        b'{"status":"pass"}',
    ):
        with pytest.raises(ValueError):
            parse_value_response(wire, spec, expected_count=1)
    assert parse_value_response(
        b'{"protocol":"protected-value-v1","completed":true,"values":[3]}',
        spec,
        expected_count=1,
    ) == (3,)


def test_payload_contains_only_public_code_contract_and_call_inputs():
    spec = contract()
    calls = (ValueCall(args=(3,)), ValueCall(args=(5,)))
    payload = value_payload(spec, "def answer(n):\n    return n\n", calls)
    assert set(payload) == {"protocol", "entry_point", "code", "calls"}
    assert payload["calls"] == [{"args": [3], "kwargs": {}}, {"args": [5], "kwargs": {}}]
    assert "oracle" not in json.dumps(payload)
    assert "test" not in json.dumps(payload)


def test_invalid_trusted_case_is_not_charged_to_candidate():
    spec = contract()
    runner = ValueRunner(image=IMAGE)
    result = runner.execute(spec, "def answer(n):\n    return n\n", (ValueCall(args=("bad",)),))
    assert result.outcome == "infrastructure_error"
    assert result.evidence["reason"] == "invalid_frozen_case"


def test_worker_returns_multiple_declared_values_and_no_verdict():
    spec = contract()
    payload = value_payload(
        spec, "def answer(n):\n    return n\n", (ValueCall(args=(3,)), ValueCall(args=(5,)))
    )
    result = worker(payload)
    assert result.returncode == 0
    assert parse_value_response(result.stdout.encode(), spec, expected_count=2) == (3, 5)
    assert "pass" not in result.stdout


def test_worker_early_exit_and_forged_pass_are_not_verdicts():
    spec = contract()
    exit_payload = value_payload(
        spec,
        "import os\ndef answer(n):\n    os._exit(0)\n",
        (ValueCall(args=(3,)),),
    )
    result = worker(exit_payload)
    with pytest.raises(ValueError):
        parse_value_response(result.stdout.encode(), spec, expected_count=1)
    forged = value_payload(
        spec,
        'import os\ndef answer(n):\n    os.write(1,b\'{"status":"pass"}\\n\')\n    return 0\n',
        (ValueCall(args=(3,)),),
    )
    result = worker(forged)
    with pytest.raises(ValueError):
        parse_value_response(result.stdout.encode(), spec, expected_count=1)


def test_candidate_encoder_substitution_is_only_a_submitted_value():
    spec = contract()
    payload = value_payload(
        spec,
        "import json\n"
        "def answer(n):\n"
        "    json.dumps = lambda *args, **kwargs: "
        '\'{"protocol":"protected-value-v1","completed":true,"values":[3]}\'\n'
        "    return 0\n",
        (ValueCall(args=(3,)),),
    )
    result = worker(payload)
    assert result.returncode == 0
    assert parse_value_response(result.stdout.encode(), spec, expected_count=1) == (3,)
    assert "pass" not in result.stdout


def test_docker_command_has_no_private_or_credential_mounts(tmp_path):
    command = value_command(
        docker="docker",
        image=IMAGE,
        source_dir=tmp_path,
        memory_bytes=2 * 1024**3,
        cpus=2.0,
        pids_limit=64,
        tmpfs_bytes=64 * 1024**2,
        name="graybench-protected-value-test",
    )
    joined = " ".join(command)
    assert "--network none" in joined
    assert "--read-only" in command
    assert "--cap-drop ALL" in joined
    assert "no-new-privileges" in joined
    assert "--user 65534:65534" in joined
    assert "target=/worker,readonly" in joined
    assert "/input" not in joined
    assert "/judge" not in joined
    assert "docker.sock" not in joined
    assert "--env" in command


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
def test_pinned_docker_value_runner_reference_wrong_shape_and_early_exit():
    spec = contract("function_completion")
    runner = ValueRunner(image=IMAGE, timeout=20)
    calls = (ValueCall(args=(3,)), ValueCall(args=(5,)))
    correct = runner.execute(spec, "    return n\n", calls)
    assert correct.outcome == "returned"
    assert correct.values == (3, 5)
    assert correct.evidence["origin_claim"] == "candidate_submitted_value_only"
    wrong_shape = runner.execute(spec, "    return True\n", calls)
    assert wrong_shape.outcome == "candidate_error"
    early_exit = runner.execute(spec, "    import os\n    os._exit(0)\n", calls)
    assert early_exit.outcome == "candidate_error"
    nonzero_exit = runner.execute(spec, "    import os\n    os._exit(1)\n", calls)
    assert nonzero_exit.outcome == "candidate_error"
    assert nonzero_exit.evidence["reason"] == "candidate_nonzero_exit"
    assert nonzero_exit.evidence["worker_started"] is True


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
def test_docker_launch_failure_remains_infrastructure_error():
    spec = contract("function_completion")
    runner = ValueRunner(image=IMAGE, docker="graybench-no-such-docker-command")
    result = runner.execute(spec, "    return n\n", (ValueCall(args=(3,)),))
    assert result.outcome == "infrastructure_error"
