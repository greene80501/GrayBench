import json
import sys

import httpx
import pytest

from graybench.campaign_setup import CampaignSetup
from graybench.cli import main
from graybench.datasets import JudgeTask
from graybench.evaluation_campaign import cohort_identities
from graybench.ledger import Ledger, StateError
from graybench.provenance import source_manifest
from graybench.transport import Transport
from graybench.upstream import UpstreamJudge


@pytest.mark.parametrize("drift", [False, True])
def test_create_is_offline_and_step_uses_stored_context(
    tmp_path, protocol, task, monkeypatch, capsys, drift
):
    private = JudgeTask(
        public=task,
        canonical_solution="private",
        upstream_test="def check(candidate): pass",
        upstream_difficulty="fixture",
    )
    image = "sha256:" + "0" * 64
    binding = cohort_identities((private,), UpstreamJudge(image=image))
    protocol = protocol.model_copy(
        update={
            "track": "upstream",
            "generation_code_digest": source_manifest()["digest"],
            **{key: binding[key] for key in ("dataset_digest", "runtime_digest", "judge_digest")},
        }
    )
    setup = CampaignSetup(protocol=protocol, image=image)
    setup_file = tmp_path / "setup.json"
    setup_file.write_text(setup.model_dump_json())
    ledger_file = tmp_path / "run.sqlite"
    observation = {
        "python": {"version": "3.12"},
        "os": {},
        "packages": {},
        "executable_architecture_bits": 64,
        "source": source_manifest(),
    }
    monkeypatch.setattr("graybench.campaign_setup.environment", lambda: observation)
    monkeypatch.setattr(
        "graybench.campaign_setup.load_suite",
        lambda suite, _: (private,) if suite == "hard" else (),
    )
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "done": True,
                "message": {"role": "assistant", "content": "answer"},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("graybench.cli.Transport", lambda spec, **_: Transport(spec, client=client))
    monkeypatch.setattr(
        sys,
        "argv",
        ["graybench", "campaign-create", str(setup_file), str(tmp_path), str(ledger_file)],
    )
    main()
    run = json.loads(capsys.readouterr().out)["run_id"]
    assert calls == []
    # Remove the input file: resume is governed by the persisted context, not an editable file.
    setup_file.unlink()
    if drift:
        observation["packages"] = {"changed-runtime": "1"}
    monkeypatch.setattr(
        sys, "argv", ["graybench", "campaign-step", str(ledger_file), run, str(tmp_path)]
    )
    try:
        if drift:
            with pytest.raises(StateError, match="changed"):
                main()
            assert calls == []
        else:
            main()
            result = json.loads(capsys.readouterr().out)
            assert result["state"] == "dispatched"
            assert result["summary"]["returned_samples"] == 1
            assert result["summary"]["certification"] == "not_certified"
            assert len(calls) == 1
        ledger = Ledger(ledger_file)
        try:
            assert ledger.context(run)["setup"]["http_timeout"] == 600.0
            assert ledger.verify()["integrity"] == "verified"
        finally:
            ledger.close()
    finally:
        client.close()
