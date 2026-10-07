"""Frozen development campaign setup and host provenance; no implicit task certification."""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from graybench.adapter_provenance import adapter_code_manifest
from graybench.capability_probe import CapabilityProbe, verify_probe_bundle
from graybench.contracts import (
    Contract,
    ExtractionPolicy,
    ModelObservationTiming,
    ModelSpec,
    Protocol,
    RetryPolicy,
    reject_model_credential,
    require_credential_scope_for_new_run,
)
from graybench.datasets import JudgeTask, load_suite
from graybench.evaluation_campaign import cohort_identities, validate_cohort
from graybench.evaluation_recipes import EvaluationRecipe, recipe_judge, revised_tasks
from graybench.identity import identity
from graybench.judgment_evidence import POLICY
from graybench.ledger import StateError
from graybench.provenance import environment, source_manifest
from graybench.providers import adapter


class CampaignSetup(Contract):
    protocol: Protocol
    capability_probes: tuple[CapabilityProbe, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    purpose: Literal["development"] = "development"
    evaluation_recipe: EvaluationRecipe = "upstream"
    image: str = Field(pattern="^sha256:[0-9a-f]{64}$")
    parser_image: str | None = Field(default=None, pattern="^sha256:[0-9a-f]{64}$")
    judge_timeout: float = Field(default=120.0, gt=0, le=3600, allow_inf_nan=False)
    candidate_timeout: float = Field(default=120.0, gt=0, le=3600, allow_inf_nan=False)
    parser_timeout: float = Field(default=30.0, gt=0, le=3600, allow_inf_nan=False)
    output_limit: int = Field(default=1048576, ge=1024, le=16777216)
    http_timeout: float = Field(default=600.0, gt=0, le=3600, allow_inf_nan=False)
    response_limit: int = Field(default=16777216, ge=1024, le=67108864)

    @model_validator(mode="after")
    def parser_image_requires_file_recipe(self):
        if self.parser_image is not None and self.evaluation_recipe not in (
            "task82-file-semantic-v1",
            "task82-file-semantic-v2",
        ):
            raise ValueError("parser_image is only valid for task 82 file recipes")
        return self

    def judge(self, docker="docker"):
        return recipe_judge(
            self.evaluation_recipe,
            image=self.image,
            docker=docker,
            timeout=self.judge_timeout,
            candidate_timeout=self.candidate_timeout,
            output_limit=self.output_limit,
            parser_timeout=self.parser_timeout,
            parser_image=self.parser_image,
            extraction=self.protocol.extraction,
        )

    def tasks(self, cache: Path):
        verify_probe_bundle(
            self.protocol.model,
            self.capability_probes,
            adapter(self.protocol.model.adapter),
        )
        if (
            self.protocol.adapter_code_manifest is not None
            and adapter_code_manifest(adapter(self.protocol.model.adapter))
            != self.protocol.adapter_code_manifest
        ):
            raise StateError("Campaign adapter code differs from frozen plan")
        tasks = tuple(
            task
            for suite in ("normal", "hard")
            for task in load_suite(suite, cache)
            if f"{suite}/{task.public.task_id}" in self.protocol.task_keys
        )
        judge = self.judge()
        tasks = revised_tasks(tasks, judge)
        validate_cohort(self.protocol, tasks, judge)
        return tasks


def host_contract(observation):
    # Volatile timestamps/GPU utilization are observations, not resume identities.
    return {
        key: observation[key]
        for key in ("python", "os", "packages", "executable_architecture_bits", "source")
    }


def execution_context(setup: CampaignSetup):
    require_credential_scope_for_new_run(
        setup.protocol.model, system_prompt=setup.protocol.system_prompt
    )
    reject_model_credential(setup.protocol.model, setup.model_dump(mode="json"), "campaign setup")
    verify_probe_bundle(
        setup.protocol.model,
        setup.capability_probes,
        adapter(setup.protocol.model.adapter),
    )
    observation = environment()
    if observation["source"]["digest"] != setup.protocol.generation_code_digest:
        raise StateError("Setup source does not match this engine")
    if (
        setup.protocol.adapter_code_manifest is not None
        and adapter_code_manifest(adapter(setup.protocol.model.adapter))
        != setup.protocol.adapter_code_manifest
    ):
        raise StateError("Setup adapter code differs from frozen campaign")
    return {
        "setup": setup.model_dump(mode="json"),
        "environment": observation,
        "host_contract": host_contract(observation),
        "certification": "not_certified",
    }


def validate_host(context):
    if host_contract(environment()) != context["host_contract"]:
        raise StateError("Host runtime or source changed since campaign creation")


def build_setup(
    name: str,
    model: ModelSpec,
    tasks: tuple[JudgeTask, ...],
    image: str,
    *,
    repeats: int = 1,
    system_prompt: str | None = None,
    evaluation_recipe: EvaluationRecipe = "upstream",
    parser_image: str | None = None,
    extraction: ExtractionPolicy = "raw_or_single_python_fence_v1",
    protocol_version: Literal["3.1", "3.2", "3.3"] = "3.1",
    model_observation_timing: ModelObservationTiming | None = None,
    capability_probes: tuple[CapabilityProbe, ...] = (),
) -> CampaignSetup:
    """Freeze exactly the supplied tasks and public requests without provider access."""
    require_credential_scope_for_new_run(model, system_prompt=system_prompt)
    judge = recipe_judge(
        evaluation_recipe, image=image, parser_image=parser_image, extraction=extraction
    )
    tasks = revised_tasks(tasks, judge)
    binding = cohort_identities(tasks, judge)
    source = source_manifest()["digest"]
    provider = adapter(model.adapter)
    verify_probe_bundle(model, capability_probes, provider)
    adapter_manifest = adapter_code_manifest(provider)
    adapter_digest = identity(adapter_manifest)
    requests = {}
    for task in tasks:
        request = provider.prepare(model, task.public, system_prompt)
        if request.adapter_code_digest != adapter_digest:
            raise StateError("Adapter code changed during campaign planning")
        requests[f"{task.public.suite}/{task.public.task_id}"] = request.digest
    protocol = Protocol(
        schema_version=protocol_version,
        model_observation_timing=(
            model_observation_timing or ModelObservationTiming()
            if protocol_version == "3.3"
            else model_observation_timing
        ),
        name=name,
        track=getattr(judge, "track", "upstream"),
        model=model,
        repeats=repeats,
        system_prompt=system_prompt,
        extraction=extraction,
        retry=RetryPolicy(max_attempts=1, statuses=(), delays_seconds=()),
        task_keys=tuple(requests),
        request_digests=requests,
        dataset_digest=binding["dataset_digest"],
        judge_digest=binding["judge_digest"],
        runtime_digest=binding["runtime_digest"],
        generation_code_digest=source,
        adapter_code_manifest=adapter_manifest,
        # Conservatively bind all engine sources, including summary/metric implementation.
        analysis_digest=source,
        judgment_evidence_policy=POLICY,
    )
    setup = CampaignSetup(
        protocol=protocol,
        capability_probes=capability_probes,
        image=image,
        parser_image=parser_image,
        evaluation_recipe=evaluation_recipe,
    )
    reject_model_credential(model, setup.model_dump(mode="json"), "campaign setup")
    validate_cohort(protocol, tasks, setup.judge())
    return setup
