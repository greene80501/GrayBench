"""Frozen development campaign setup and host provenance; no implicit task certification."""

from pathlib import Path
from typing import Literal

from pydantic import Field

from graybench.contracts import Contract, Protocol
from graybench.datasets import load_suite
from graybench.evaluation_campaign import validate_cohort
from graybench.ledger import StateError
from graybench.provenance import environment
from graybench.upstream import UpstreamJudge


class CampaignSetup(Contract):
    protocol: Protocol
    purpose: Literal["development"] = "development"
    image: str = Field(pattern="^sha256:[0-9a-f]{64}$")
    judge_timeout: float = Field(default=120.0, gt=0, le=3600, allow_inf_nan=False)
    candidate_timeout: float = Field(default=120.0, gt=0, le=3600, allow_inf_nan=False)
    output_limit: int = Field(default=1048576, ge=1024, le=16777216)
    http_timeout: float = Field(default=600.0, gt=0, le=3600, allow_inf_nan=False)
    response_limit: int = Field(default=16777216, ge=1024, le=67108864)

    def judge(self, docker="docker"):
        return UpstreamJudge(
            image=self.image,
            docker=docker,
            timeout=self.judge_timeout,
            candidate_timeout=self.candidate_timeout,
            output_limit=self.output_limit,
        )

    def tasks(self, cache: Path):
        tasks = tuple(
            task
            for suite in ("normal", "hard")
            for task in load_suite(suite, cache)
            if f"{suite}/{task.public.task_id}" in self.protocol.task_keys
        )
        validate_cohort(self.protocol, tasks, self.judge())
        return tasks


def host_contract(observation):
    # Volatile timestamps/GPU utilization are observations, not resume identities.
    return {
        key: observation[key]
        for key in ("python", "os", "packages", "executable_architecture_bits", "source")
    }


def execution_context(setup: CampaignSetup):
    observation = environment()
    if observation["source"]["digest"] != setup.protocol.generation_code_digest:
        raise StateError("Setup source does not match this engine")
    return {
        "setup": setup.model_dump(mode="json"),
        "environment": observation,
        "host_contract": host_contract(observation),
        "certification": "not_certified",
    }


def validate_host(context):
    if host_contract(environment()) != context["host_contract"]:
        raise StateError("Host runtime or source changed since campaign creation")
