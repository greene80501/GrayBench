"""Frozen, single-suite development campaigns for reviewed value interfaces.

Only task 20 has a development contract today. Every other pinned suite task
is explicitly excluded; no run from this module is a publication score.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from graybench.campaign import GenerationRunner
from graybench.contracts import (
    Contract,
    Generation,
    ModelObservationTiming,
    ModelSpec,
    Protocol,
    RetryPolicy,
    require_credential_scope_for_new_run,
)
from graybench.datasets import PINS, JudgeTask, load_suite
from graybench.identity import canonical, identity
from graybench.ledger import Ledger, StateError
from graybench.protected_semantic_judge import ProtectedSemanticJudge, ProtectedSemanticTask
from graybench.protected_task20 import task20_value_task
from graybench.protected_value_runner import ValueRunner
from graybench.provenance import source_manifest
from graybench.providers import adapter


def task_key(task: ProtectedSemanticTask) -> str:
    public = task.contract.public
    return f"{public.suite}/{public.task_id}"


def suite_keys(suite: str) -> set[str]:
    return {f"{suite}/qiskitHumanEval/{number}" for number in range(151)}


class ProtectedCohort(Contract):
    track: Literal["graybench-protected-semantic-v1"] = "graybench-protected-semantic-v1"
    suite: Literal["normal", "hard"]
    population: Literal["custom_development"] = "custom_development"
    label: str = Field(min_length=1)
    task_keys: tuple[str, ...] = Field(min_length=1)
    task_digests: dict[str, str]
    excluded: dict[str, str]
    dataset_pin: dict[str, str]
    image: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def complete_inventory(self) -> "ProtectedCohort":
        scheduled = set(self.task_keys)
        if (
            not scheduled <= suite_keys(self.suite)
            or len(scheduled) != len(self.task_keys)
            or set(self.excluded) != suite_keys(self.suite) - scheduled
            or any(not reason.strip() for reason in self.excluded.values())
            or set(self.task_digests) != scheduled
            or any(len(digest) != 64 for digest in self.task_digests.values())
            or self.dataset_pin != PINS[self.suite]
        ):
            raise ValueError("Protected cohort must freeze one complete 151-task suite inventory")
        return self


def _pinned(cache: Path, suite: str) -> dict[str, JudgeTask]:
    return {
        f"{source.public.suite}/{source.public.task_id}": source
        for source in load_suite(suite, cache)
    }


def validate_protected_cohort(
    cohort: ProtectedCohort, tasks: tuple[ProtectedSemanticTask, ...], *, cache: Path
) -> dict[str, JudgeTask]:
    ProtectedCohort.model_validate_json(cohort.model_dump_json())
    if cohort.source_digest != source_manifest()["digest"]:
        raise StateError("Protected engine source changed")
    pinned = _pinned(cache, cohort.suite)
    if set(pinned) != suite_keys(cohort.suite):
        raise StateError("Pinned protected suite is incomplete")
    if tuple(task_key(task) for task in tasks) != cohort.task_keys:
        raise StateError("Protected task order differs from frozen cohort")
    if cohort.task_keys != tuple(key for key in pinned if key in cohort.task_digests):
        raise StateError("Protected task order differs from pinned dataset order")
    for task in tasks:
        key = task_key(task)
        source = pinned[key]
        if (
            task.digest != cohort.task_digests[key]
            or task.contract.source_task_digest != source.digest
            or task.contract.public.digest == source.public.digest
            or task != task20_value_task(source)
        ):
            raise StateError("Protected task or its revised contract differs from pinned source")
    return pinned


def freeze_protected_cohort(
    tasks: tuple[ProtectedSemanticTask, ...],
    *,
    cache: Path,
    suite: Literal["normal", "hard"],
    image: str,
    label: str,
    excluded: dict[str, str],
) -> ProtectedCohort:
    cohort = ProtectedCohort(
        suite=suite,
        label=label,
        task_keys=tuple(task_key(task) for task in tasks),
        task_digests={task_key(task): task.digest for task in tasks},
        excluded=dict(excluded),
        dataset_pin=dict(PINS[suite]),
        image=image,
        source_digest=source_manifest()["digest"],
    )
    validate_protected_cohort(cohort, tasks, cache=cache)
    return cohort


class ProtectedCampaignSetup(Contract):
    protocol: Protocol
    cohort: ProtectedCohort
    tasks: tuple[ProtectedSemanticTask, ...] = Field(min_length=1)
    purpose: Literal["development"] = "development"
    judge_timeout: float = Field(default=120.0, gt=0, le=3600, allow_inf_nan=False)
    output_limit: int = Field(default=1048576, ge=1024, le=16777216)
    memory_bytes: int = Field(default=2 * 1024**3, ge=128 * 1024**2)
    cpus: float = Field(default=2.0, gt=0, le=128, allow_inf_nan=False)
    pids_limit: int = Field(default=64, ge=2)
    tmpfs_bytes: int = Field(default=64 * 1024**2, ge=1024**2)
    http_timeout: float = Field(default=600.0, gt=0, le=3600, allow_inf_nan=False)
    response_limit: int = Field(default=16777216, ge=1024, le=67108864)

    def judge(self, docker: str = "docker") -> ProtectedSemanticJudge:
        return ProtectedSemanticJudge(
            ValueRunner(
                image=self.cohort.image,
                docker=docker,
                timeout=self.judge_timeout,
                output_limit=self.output_limit,
                memory_bytes=self.memory_bytes,
                cpus=self.cpus,
                pids_limit=self.pids_limit,
                tmpfs_bytes=self.tmpfs_bytes,
            )
        )

    def validate_for_run(
        self, cache: Path, run_protocol: Protocol, *, docker: str = "docker"
    ) -> dict[str, JudgeTask]:
        if self.protocol != run_protocol:
            raise StateError("Stored protected setup differs from run protocol")
        if (
            self.protocol.track != self.cohort.track
            or self.protocol.protected_cohort_digest != self.cohort.digest
            or self.protocol.protected_suite != self.cohort.suite
            or self.protocol.protected_population != self.cohort.population
            or self.protocol.protected_excluded != self.cohort.excluded
            or self.protocol.task_keys != self.cohort.task_keys
        ):
            raise StateError("Protected protocol and cohort identities differ")
        pinned = validate_protected_cohort(self.cohort, self.tasks, cache=cache)
        binding = cohort_identities(self.tasks, pinned, self.judge(docker))
        for field in ("dataset_digest", "judge_digest", "runtime_digest"):
            if getattr(self.protocol, field) != binding[field]:
                raise StateError("Frozen protected cohort mismatch: " + field)
        provider = adapter(self.protocol.model.adapter)
        for task in self.tasks:
            key = task_key(task)
            request = provider.prepare(
                self.protocol.model, task.contract.public, self.protocol.system_prompt
            )
            if request.digest != self.protocol.request_digests[key]:
                raise StateError("Protected request differs from revised public contract")
        if self.protocol.generation_code_digest != source_manifest()["digest"]:
            raise StateError("Protected generation source changed")
        if self.protocol.extraction != self.tasks[0].contract.extraction or any(
            task.contract.extraction != self.protocol.extraction for task in self.tasks
        ):
            raise StateError("Protected extraction policy differs from frozen contract")
        return pinned


def cohort_identities(
    tasks: tuple[ProtectedSemanticTask, ...],
    pinned: dict[str, JudgeTask],
    judge: ProtectedSemanticJudge,
) -> dict:
    datasets = {
        task_key(task): {
            "source": pinned[task_key(task)].digest,
            "revised_task": task.digest,
        }
        for task in tasks
    }
    judges = {task_key(task): identity(judge.manifest(task)) for task in tasks}
    return {
        "dataset_digest": identity(datasets),
        "judge_digest": identity(judges),
        "runtime_digest": judge.runner.image.removeprefix("sha256:"),
        "tasks": datasets,
        "judges": judges,
    }


def build_protected_setup(
    name: str,
    model: ModelSpec,
    cohort: ProtectedCohort,
    tasks: tuple[ProtectedSemanticTask, ...],
    *,
    cache: Path,
    repeats: int = 1,
    system_prompt: str | None = None,
    model_observation_timing: ModelObservationTiming | None = None,
) -> ProtectedCampaignSetup:
    require_credential_scope_for_new_run(model)
    pinned = validate_protected_cohort(cohort, tasks, cache=cache)
    setup_stub = ProtectedCampaignSetup(
        protocol=Protocol(
            schema_version="3.3",
            name=name,
            track=cohort.track,
            protected_cohort_digest=cohort.digest,
            protected_suite=cohort.suite,
            protected_population=cohort.population,
            protected_excluded=cohort.excluded,
            dataset_digest="0" * 64,
            task_keys=cohort.task_keys,
            request_digests={key: "0" * 64 for key in cohort.task_keys},
            repeats=repeats,
            retry=RetryPolicy(max_attempts=1, statuses=(), delays_seconds=()),
            model_observation_timing=model_observation_timing or ModelObservationTiming(),
            model=model,
            generation_code_digest="0" * 64,
            runtime_digest="0" * 64,
            judge_digest="0" * 64,
            analysis_digest="0" * 64,
        ),
        cohort=cohort,
        tasks=tasks,
    )
    binding = cohort_identities(tasks, pinned, setup_stub.judge())
    source = source_manifest()["digest"]
    extraction = {task.contract.extraction for task in tasks}
    if len(extraction) != 1:
        raise ValueError("Protected cohort cannot mix extraction policies")
    protocol = setup_stub.protocol.model_copy(
        update={
            "dataset_digest": binding["dataset_digest"],
            "request_digests": {
                task_key(task): adapter(model.adapter)
                .prepare(model, task.contract.public, system_prompt)
                .digest
                for task in tasks
            },
            "system_prompt": system_prompt,
            "extraction": extraction.pop(),
            "generation_code_digest": source,
            "runtime_digest": binding["runtime_digest"],
            "judge_digest": binding["judge_digest"],
            "analysis_digest": source,
        }
    )
    setup = setup_stub.model_copy(update={"protocol": protocol})
    setup.validate_for_run(cache, protocol)
    return setup


class ProtectedCampaign:
    """One step dispatches at most one generation or one durable judgment."""

    def __init__(
        self,
        ledger: Ledger,
        run_id: str,
        setup: ProtectedCampaignSetup,
        cache: Path,
        transport,
        *,
        docker="docker",
    ):
        self.ledger, self.run_id, self.setup, self.cache = ledger, run_id, setup, cache
        self.transport, self.docker = transport, docker
        self.pinned = setup.validate_for_run(cache, ledger.protocol(run_id), docker=docker)
        protocol = setup.protocol
        self.judge = setup.judge(docker)
        self.binding = cohort_identities(setup.tasks, self.pinned, self.judge)
        self.generations = GenerationRunner(
            ledger,
            run_id,
            {
                task_key(task): adapter(protocol.model.adapter).prepare(
                    protocol.model, task.contract.public, protocol.system_prompt
                )
                for task in setup.tasks
            },
            transport,
        )

    def step(self) -> dict:
        self.pinned = self.setup.validate_for_run(
            self.cache, self.ledger.protocol(self.run_id), docker=self.docker
        )
        self.binding = cohort_identities(self.setup.tasks, self.pinned, self.judge)
        self.ledger.verify()
        if self.ledger.model_identity(self.run_id)["status"] == "unresolved":
            return {"state": "stopped", "reason": "model_identity_unresolved"}
        observation = self.ledger.attempt_observation_status(self.run_id)["status"]
        if observation == "timing_violation":
            return {"state": "stopped", "reason": "model_observation_timing_violation"}
        if observation == "missing_post_check":
            return {"state": "stopped", "reason": "model_post_observation_check_missing"}
        if observation != "complete":
            return {"state": "stopped", "reason": "model_post_observation_missing"}
        if self.ledger.discovery_status(self.run_id)["status"] == "unresolved":
            return {"state": "stopped", "reason": "model_discovery_unresolved"}
        result = self._judge_one()
        if result["state"] != "awaiting_generations":
            return result
        return self.generations.step()

    def _judge_one(self) -> dict:
        protocol = self.setup.protocol
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
        tasks = {task_key(task): task for task in self.setup.tasks}
        for row in rows:
            if row["content"] is None or row["outcome"] is not None:
                continue
            generation = Generation.model_validate_json(canonical(self.ledger.blob(row["content"])))
            self.ledger.claim_judgment(row["id"], protocol.judge_digest)
            try:
                result = self.judge.evaluate(
                    tasks[row["task_key"]], self.pinned[row["task_key"]], generation.text
                )
                if result.judge_digest != self.binding["judges"][row["task_key"]]:
                    raise StateError("Protected judge changed after cohort validation")
                outcome = result.outcome
                evidence = {"task_judge_digest": result.judge_digest, "judgment": result.evidence}
            except Exception as exc:
                outcome = "infrastructure_error"
                evidence = {"error_type": type(exc).__name__}
            evidence["cohort"] = self.binding
            evidence["generation_digest"] = row["content"]
            self.ledger.judge(row["id"], protocol.judge_digest, outcome, evidence)
            return {"state": "judged", "sample_id": row["id"], "outcome": outcome}
        return {
            "state": "judgments_complete"
            if all(row["outcome"] is not None for row in rows)
            else "awaiting_generations"
        }
