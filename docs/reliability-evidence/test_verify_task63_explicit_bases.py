"""Evidence verifier must bind the declared case digests to case metadata."""

import copy
import json
import os
from pathlib import Path

import pytest
from graybench.evaluation_recipes import recipe_judge
from graybench.identity import canonical, identity
from task63_explicit_bases_probe import plan_cases
from verify_task63_explicit_bases import main


def _historical_events():
    source = Path(__file__).with_name("GrayBench-v4-task63-explicit-bases-controls.jsonl")
    return [json.loads(line)["event"] for line in source.open(encoding="utf-8")]


def _write_events(tmp_path, events):
    altered = tmp_path / "altered-ledger.jsonl"
    previous = "0" * 64
    with altered.open("wb") as stream:
        for sequence, event in enumerate(events, 1):
            payload = {"sequence": sequence, "previous": previous, "event": event}
            previous = identity(payload)
            stream.write(canonical({**payload, "digest": previous}) + b"\n")
    return altered


def _declared_judges(events):
    return {
        f"{suite}/qiskitHumanEval/63": copy.deepcopy(
            next(
                event["evidence"]["judgment"]["manifest"]
                for event in events
                if event["kind"] == "result" and event["task_key"].startswith(suite + "/")
            )
        )
        for suite in ("normal", "hard")
    }


def test_historical_log_remains_verifiable_after_source_changes():
    source = Path(__file__).with_name("GrayBench-v4-task63-explicit-bases-controls.jsonl")
    report = main(source)
    assert report["complete"] is True
    assert report["judge_predeclared"] is False
    assert report["source_matches_running_source"] is False


def test_declared_case_identity_is_enforced(tmp_path):
    events = _historical_events()
    first = next(iter(events[0]["tasks"]))
    events[0]["tasks"][first] = "f" * 64
    altered = _write_events(tmp_path, events)
    with pytest.raises(ValueError, match="case identity"):
        main(altered)


def test_exact_predeclared_judges_are_verified(tmp_path):
    events = _historical_events()
    events[0]["selection"]["declared_judges"] = _declared_judges(events)
    report = main(_write_events(tmp_path, events))
    assert report["judge_predeclared"] is True


def test_rebound_predeclared_judge_is_rejected(tmp_path):
    events = _historical_events()
    declared = _declared_judges(events)
    declared["normal/qiskitHumanEval/63"]["public_contract"] = "changed after planning"
    events[0]["selection"]["declared_judges"] = declared
    with pytest.raises(ValueError, match="predeclared judge"):
        main(_write_events(tmp_path, events))


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_probe_plan_freezes_both_judges_before_execution():
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    image = "sha256:" + "2" * 64
    judge = recipe_judge("qhe63-explicit-bases-v1", image=image)
    cases, selection = plan_cases(cache, judge, image=image)
    assert len(cases) == 14
    assert set(selection["declared_judges"]) == {
        "normal/qiskitHumanEval/63",
        "hard/qiskitHumanEval/63",
    }
    for key, _, (revised, _, _) in cases:
        task_key = f"{revised.public.suite}/{revised.public.task_id}"
        assert selection["declared_judges"][task_key] == judge.configuration(revised)[1]
        assert key.startswith(revised.public.suite + "/63/")
