"""Frozen, single-suite development campaigns for the native QHE track."""

from pathlib import Path
from typing import Literal

from pydantic import Field

from graybench.contracts import (
    Contract,
    ModelObservationTiming,
    ModelSpec,
    Protocol,
    RetryPolicy,
    require_credential_scope_for_new_run,
)
from graybench.datasets import JudgeTask, load_suite
from graybench.evaluation_campaign import UpstreamCampaign, cohort_identities, validate_cohort
from graybench.ledger import StateError
from graybench.native_cohort import NativeCohort, task_key, validate_native_cohort
from graybench.native_judge import NativeJudge
from graybench.provenance import source_manifest
from graybench.providers import adapter


class NativeCampaignSetup(Contract):
    protocol: Protocol
    cohort: NativeCohort
    purpose: Literal["development"] = "development"
    judge_timeout: float = Field(default=120.0, gt=0, le=3600, allow_inf_nan=False)
    output_limit: int = Field(default=1048576, ge=1024, le=16777216)
    memory_bytes: int = Field(default=2 * 1024**3, ge=128 * 1024**2)
    cpus: float = Field(default=2.0, gt=0, le=128, allow_inf_nan=False)
    pids_limit: int = Field(default=64, ge=2)
    tmpfs_bytes: int = Field(default=64 * 1024**2, ge=1024**2)
    http_timeout: float = Field(default=600.0, gt=0, le=3600, allow_inf_nan=False)
    response_limit: int = Field(default=16777216, ge=1024, le=67108864)

    def tasks(self, cache: Path) -> tuple[JudgeTask, ...]:
        pinned = {task_key(task): task for task in load_suite(self.cohort.suite, cache)}
        if any(key not in pinned for key in self.cohort.task_keys):
            raise StateError("Native cohort contains a task absent from the pinned suite")
        tasks = tuple(pinned[key] for key in self.cohort.task_keys)
        validate_native_cohort(self.cohort, tasks, cache=cache)
        return tasks

    def judge(
        self, cache: Path, tasks: tuple[JudgeTask, ...], docker: str = "docker"
    ) -> NativeJudge:
        return NativeJudge(
            self.cohort,
            tasks,
            cache=cache,
            docker=docker,
            timeout=self.judge_timeout,
            output_limit=self.output_limit,
            memory_bytes=self.memory_bytes,
            cpus=self.cpus,
            pids_limit=self.pids_limit,
            tmpfs_bytes=self.tmpfs_bytes,
        )

    def validate_for_run(
        self,
        cache: Path,
        run_protocol: Protocol,
        *,
        tasks: tuple[JudgeTask, ...] | None = None,
        docker: str = "docker",
    ) -> tuple[JudgeTask, ...]:
        if self.protocol != run_protocol:
            raise StateError("Stored native setup differs from run protocol")
        if (
            self.protocol.track != self.cohort.track
            or self.protocol.native_cohort_digest != self.cohort.digest
            or self.protocol.native_suite != self.cohort.suite
            or self.protocol.native_population != self.cohort.population
            or self.protocol.task_keys != self.cohort.task_keys
            or self.protocol.extraction != self.cohort.extraction
        ):
            raise StateError("Native protocol and cohort identities differ")
        tasks = tasks if tasks is not None else self.tasks(cache)
        validate_native_cohort(self.cohort, tasks, cache=cache)
        validate_cohort(self.protocol, tasks, self.judge(cache, tasks, docker))
        if self.protocol.generation_code_digest != source_manifest()["digest"]:
            raise StateError("Native generation source changed")
        return tasks


def build_native_setup(
    name: str,
    model: ModelSpec,
    cohort: NativeCohort,
    tasks: tuple[JudgeTask, ...],
    *,
    cache: Path,
    repeats: int = 1,
    system_prompt: str | None = None,
    model_observation_timing: ModelObservationTiming | None = None,
    judge_timeout: float = 120.0,
    output_limit: int = 1048576,
    memory_bytes: int = 2 * 1024**3,
    cpus: float = 2.0,
    pids_limit: int = 64,
    tmpfs_bytes: int = 64 * 1024**2,
) -> NativeCampaignSetup:
    """Freeze exactly one pinned suite without contacting a model provider."""
    require_credential_scope_for_new_run(model)
    validate_native_cohort(cohort, tasks, cache=cache)
    limits = dict(
        judge_timeout=judge_timeout,
        output_limit=output_limit,
        memory_bytes=memory_bytes,
        cpus=cpus,
        pids_limit=pids_limit,
        tmpfs_bytes=tmpfs_bytes,
    )
    binding = cohort_identities(
        tasks,
        NativeJudge(
            cohort,
            tasks,
            cache=cache,
            timeout=judge_timeout,
            output_limit=output_limit,
            memory_bytes=memory_bytes,
            cpus=cpus,
            pids_limit=pids_limit,
            tmpfs_bytes=tmpfs_bytes,
        ),
    )
    provider = adapter(model.adapter)
    requests = {
        task_key(task): provider.prepare(model, task.public, system_prompt).digest for task in tasks
    }
    source = source_manifest()["digest"]
    protocol = Protocol(
        schema_version="3.3",
        name=name,
        track=cohort.track,
        native_cohort_digest=cohort.digest,
        native_suite=cohort.suite,
        native_population=cohort.population,
        dataset_digest=binding["dataset_digest"],
        task_keys=cohort.task_keys,
        request_digests=requests,
        repeats=repeats,
        system_prompt=system_prompt,
        extraction=cohort.extraction,
        retry=RetryPolicy(max_attempts=1, statuses=(), delays_seconds=()),
        model_observation_timing=model_observation_timing or ModelObservationTiming(),
        model=model,
        generation_code_digest=source,
        runtime_digest=binding["runtime_digest"],
        judge_digest=binding["judge_digest"],
        analysis_digest=source,
    )
    setup = NativeCampaignSetup(protocol=protocol, cohort=cohort, **limits)
    setup.validate_for_run(cache, protocol, tasks=tasks)
    return setup


class NativeCampaign:
    """One-step dispatch with native identity checks before generation or judgment."""

    def __init__(self, ledger, run_id, setup, cache, transport, *, docker="docker"):
        self.ledger, self.run_id = ledger, run_id
        self.setup, self.cache, self.docker = setup, cache, docker
        self.tasks = setup.validate_for_run(cache, ledger.protocol(run_id), docker=docker)
        self.inner = UpstreamCampaign(
            ledger, run_id, self.tasks, setup.judge(cache, self.tasks, docker), transport
        )

    def step(self):
        self.setup.validate_for_run(
            self.cache, self.ledger.protocol(self.run_id), tasks=self.tasks, docker=self.docker
        )
        return self.inner.step()
