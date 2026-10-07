"""Frozen upstream cohort binding and durable judgment scheduling.

This validates identities, not test adequacy. Reviewed eligibility and publication admission
remain separate requirements; a bound development cohort does not become certified.
"""

from graybench.contracts import Generation, Protocol
from graybench.datasets import JudgeTask
from graybench.identity import canonical, identity
from graybench.judgment_evidence import validate_judgment_result
from graybench.ledger import Ledger, StateError
from graybench.providers import adapter
from graybench.upstream import UpstreamJudge


def cohort_identities(tasks: tuple[JudgeTask, ...], judge: UpstreamJudge) -> dict:
    keyed = {f"{task.public.suite}/{task.public.task_id}": task for task in tasks}
    if not tasks or len(keyed) != len(tasks):
        raise StateError("Cohort must contain nonempty unique task keys")
    datasets = {key: task.digest for key, task in keyed.items()}
    judges = {key: identity(judge.configuration(task)[1]) for key, task in keyed.items()}
    return {
        "dataset_digest": identity(datasets),
        "judge_digest": identity(judges),
        "runtime_digest": judge.image.removeprefix("sha256:"),
        "tasks": datasets,
        "judges": judges,
    }


def validate_cohort(protocol: Protocol, tasks: tuple[JudgeTask, ...], judge: UpstreamJudge) -> dict:
    if protocol.extraction == "exact_prompt_suffix_v1" and any(
        task.public.suite != "normal" or task.public.prompt_format != "function_completion"
        for task in tasks
    ):
        raise StateError("Exact prompt suffix requires normal function-completion tasks")
    concrete = judge
    while hasattr(concrete, "inner"):
        concrete = concrete.inner
    if getattr(concrete, "extraction", None) != protocol.extraction:
        raise StateError("Judge extraction differs from frozen protocol")
    binding = cohort_identities(tasks, judge)
    if protocol.track != getattr(judge, "track", "upstream"):
        raise StateError("Judge cannot execute a different evaluation track")
    if set(protocol.task_keys) != set(binding["tasks"]):
        raise StateError("Scheduled tasks differ from supplied cohort")
    for key in ("dataset_digest", "judge_digest", "runtime_digest"):
        if getattr(protocol, key) != binding[key]:
            raise StateError("Frozen cohort mismatch: " + key)
    provider = adapter(protocol.model.adapter)
    for task in tasks:
        key = f"{task.public.suite}/{task.public.task_id}"
        request = provider.prepare(protocol.model, task.public, protocol.system_prompt)
        if request.digest != protocol.request_digests[key]:
            raise StateError("Frozen request does not match the cohort's public task")
    return binding


class JudgmentRunner:
    def __init__(
        self, ledger: Ledger, run_id: str, tasks: tuple[JudgeTask, ...], judge: UpstreamJudge
    ):
        self.ledger, self.run_id, self.tasks, self.judge = ledger, run_id, tasks, judge

    def step(self) -> dict:
        protocol = self.ledger.protocol(self.run_id)
        binding = validate_cohort(protocol, self.tasks, self.judge)
        self.ledger.verify()
        if protocol.schema_version in {"3.2", "3.3"}:
            observation_status = self.ledger.attempt_observation_status(self.run_id)["status"]
            if observation_status == "timing_violation":
                return {"state": "stopped", "reason": "model_observation_timing_violation"}
            if observation_status == "missing_post_check":
                return {"state": "stopped", "reason": "model_post_observation_check_missing"}
            if observation_status != "complete":
                return {"state": "stopped", "reason": "model_post_observation_missing"}
        if (
            protocol.schema_version in {"3.2", "3.3"}
            and self.ledger.discovery_status(self.run_id)["status"] == "unresolved"
        ):
            return {"state": "stopped", "reason": "model_discovery_unresolved"}
        tasks = {f"{task.public.suite}/{task.public.task_id}": task for task in self.tasks}
        rows = self.ledger.db.execute(
            "SELECT s.id,s.task_key,g.content,j.outcome,c.started_at FROM samples s "
            "LEFT JOIN generations g ON g.sample_id=s.id "
            "LEFT JOIN judgments j ON j.sample_id=s.id AND j.judge_digest=? "
            "LEFT JOIN judgment_claims c ON c.sample_id=s.id AND c.judge_digest=? "
            "WHERE s.run_id=? ORDER BY s.task_key,s.replicate",
            (protocol.judge_digest, protocol.judge_digest, self.run_id),
        ).fetchall()
        if any(row["started_at"] and row["outcome"] is None for row in rows):
            return {"state": "stopped", "reason": "unresolved_judgment"}
        for row in rows:
            if row["content"] is None or row["outcome"] is not None:
                continue
            generation = Generation.model_validate_json(canonical(self.ledger.blob(row["content"])))
            self.ledger.claim_judgment(row["id"], protocol.judge_digest)
            result = None
            try:
                result = self.judge.evaluate(tasks[row["task_key"]], generation.text)
                if result.judge_digest != binding["judges"][row["task_key"]]:
                    raise StateError("Judge changed after cohort validation")
                validate_judgment_result(
                    result.outcome,
                    result.evidence,
                    result.judge_digest,
                    completion=generation.text,
                    require_completion=protocol.judgment_evidence_policy is not None,
                )
                outcome = result.outcome
                evidence = {"task_judge_digest": result.judge_digest, "judgment": result.evidence}
            except Exception as exc:
                outcome = "infrastructure_error"
                evidence = {"error_type": type(exc).__name__}
                if result is not None:
                    evidence["rejected_judgment"] = {
                        "outcome": result.outcome,
                        "judge_digest": result.judge_digest,
                        "evidence": result.evidence,
                    }
            evidence["cohort"] = binding
            evidence["generation_digest"] = row["content"]
            self.ledger.judge(row["id"], protocol.judge_digest, outcome, evidence)
            return {"state": "judged", "sample_id": row["id"], "outcome": outcome}
        return {
            "state": "judgments_complete"
            if all(r["outcome"] is not None for r in rows)
            else "awaiting_generations"
        }


class UpstreamCampaign:
    """Development campaign with frozen judge selection; not oracle certification.

    The historical class name is retained for callers. Explicit revision judges are
    accepted only when their track and all cohort/request identities match.
    """

    def __init__(self, ledger, run_id, tasks, judge, transport):
        from graybench.campaign import GenerationRunner

        protocol = ledger.protocol(run_id)
        validate_cohort(protocol, tasks, judge)
        requests = {
            f"{task.public.suite}/{task.public.task_id}": adapter(protocol.model.adapter).prepare(
                protocol.model, task.public, protocol.system_prompt
            )
            for task in tasks
        }
        self.judgments = JudgmentRunner(ledger, run_id, tasks, judge)
        self.generations = GenerationRunner(ledger, run_id, requests, transport)

    def step(self):
        # Validate before either stage, including before the first billable request.
        if (
            self.generations.ledger.model_identity(self.generations.run_id)["status"]
            == "unresolved"
        ):
            return {"state": "stopped", "reason": "model_identity_unresolved"}
        result = self.judgments.step()
        if result["state"] != "awaiting_generations":
            return result
        return self.generations.step()
