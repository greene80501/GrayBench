import pytest

from graybench.contracts import ModelSpec, Protocol, PublicTask
from graybench.ledger import Ledger
from graybench.providers import Ollama


@pytest.fixture
def task():
    return PublicTask(
        suite="hard",
        task_id="qiskitHumanEval/0",
        family_id="qhe/0",
        prompt="Write answer(x) returning x + 1.",
        entry_point="answer",
        prompt_format="standalone_function",
    )


@pytest.fixture
def model():
    return ModelSpec(adapter="ollama", model="test-model", base_url="http://localhost:11434")


@pytest.fixture
def protocol(model, task):
    return Protocol(
        name="test",
        track="strengthened",
        dataset_digest="1" * 64,
        task_keys=("hard/qiskitHumanEval/0",),
        request_digests={"hard/qiskitHumanEval/0": Ollama().prepare(model, task, None).digest},
        model=model,
        generation_code_digest="2" * 64,
        runtime_digest="3" * 64,
        judge_digest="4" * 64,
        analysis_digest="5" * 64,
    )


@pytest.fixture
def ledger(tmp_path):
    result = Ledger(tmp_path / "ledger.sqlite")
    yield result
    result.close()
