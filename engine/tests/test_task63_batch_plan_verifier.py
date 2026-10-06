"""The predeclared batch plan is checked without executing a candidate."""

from pathlib import Path

import pytest

from graybench.identity import canonical, identity


def verifier_module():
    import importlib.util

    path = (
        Path(__file__).resolve().parents[2]
        / "docs/reliability-evidence/artifacts/task63-batch-controls-2026-10-05/verify.py"
    )
    spec = importlib.util.spec_from_file_location("task63_batch_plan_verify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_batch_plan_is_predeclared_without_result_claim():
    report = verifier_module().verify()
    assert report["predeclared"] is True
    assert report["controls_executed"] is False
    assert report["control_count"] == 16
    assert report["expected_outcomes"] == {"pass": 6, "fail": 8, "candidate_error": 2}
    assert report["publication_eligible"] is False


def test_byte_tampered_batch_plan_is_rejected(tmp_path):
    verifier = verifier_module()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    source = verifier.HERE / "plan.json"
    raw = source.read_bytes()
    (bundle / "plan.json").write_bytes(raw[:-2] + b" \n")
    with pytest.raises(ValueError, match="byte|digest"):
        verifier.verify(bundle)


def test_semantically_changed_batch_plan_is_rejected_by_pinned_digest(tmp_path):
    verifier = verifier_module()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    plan = verifier.read_plan(verifier.HERE / "plan.json")
    plan["cases"]["hard/63/fixed-one"]["expected"] = "pass"
    (bundle / "plan.json").write_bytes(canonical(plan) + b"\n")
    with pytest.raises(ValueError, match="byte|digest|outcome"):
        verifier.verify(bundle)


def _synthetic_control_log(tmp_path, *, change=None):
    """Construct a chain for binding tests; this is never real execution evidence."""
    verifier = verifier_module()
    plan = verifier.read_plan(verifier.HERE / "plan.json")
    events = [
        {
            "kind": "header",
            "purpose": "BB84 batch protected authored controls; not model scoring",
            "source": next(iter(plan["declared_judges"].values()))["source"],
            "selection": plan,
            "tasks": {key: identity(record) for key, record in plan["cases"].items()},
        }
    ]
    for key, case in plan["cases"].items():
        suite = key.split("/", 1)[0]
        manifest = plan["declared_judges"][f"{suite}/qiskitHumanEval/63"]
        events.append({"kind": "started", "task_key": key})
        events.append(
            {
                "kind": "result",
                "task_key": key,
                "outcome": case["expected"],
                "judge_digest": identity(manifest),
                "evidence": {
                    "expected": case["expected"],
                    "matches_expectation": True,
                    "judgment": {
                        "manifest": manifest,
                        "inner": {
                            "manifest": manifest["inner"],
                            "public_task_digest": case["revised_public_digest"],
                            "completion_sha256": case["completion_sha256"],
                        },
                    },
                },
            }
        )
    events.append({"kind": "complete"})
    if change is not None:
        change(events)
    path = tmp_path / "synthetic.jsonl"
    previous = "0" * 64
    with path.open("wb") as stream:
        for sequence, event in enumerate(events, 1):
            payload = {"sequence": sequence, "previous": previous, "event": event}
            previous = identity(payload)
            stream.write(canonical({**payload, "digest": previous}) + b"\n")
    return path


def test_result_verifier_binds_a_structurally_valid_synthetic_log(tmp_path):
    report = verifier_module().verify_results(_synthetic_control_log(tmp_path))
    assert report["recorded_controls"] == 16
    assert report["results"] == {"pass": 6, "fail": 8, "candidate_error": 2}
    assert report["execution_independently_attested"] is False
    assert report["publication_eligible"] is False


@pytest.mark.parametrize(
    "change",
    [
        lambda events: events[0]["tasks"].update({"normal/63/fixed-one": "f" * 64}),
        lambda events: events[2]["evidence"]["judgment"]["inner"].update(
            {"completion_sha256": "f" * 64}
        ),
        lambda events: events[2]["evidence"]["judgment"]["manifest"].update(
            {"public_contract": "changed"}
        ),
        lambda events: events[2].update({"outcome": "pass"}),
    ],
)
def test_result_verifier_rejects_rechained_binding_changes(tmp_path, change):
    with pytest.raises(ValueError, match="identity|binding|manifest"):
        verifier_module().verify_results(_synthetic_control_log(tmp_path, change=change))


def test_result_verifier_rejects_missing_completion(tmp_path):
    path = _synthetic_control_log(tmp_path, change=lambda events: events.pop())
    with pytest.raises(ValueError, match="Incomplete"):
        verifier_module().verify_results(path)
