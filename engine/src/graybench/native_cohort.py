"""Frozen single-suite cohorts for the development native QHE track."""

import re
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from graybench.contracts import Contract, ExtractionPolicy, NativeExceptionPolicy
from graybench.datasets import EXTERNAL_IDS, PINS, JudgeTask, load_suite
from graybench.extraction import EXTRACTION_POLICIES
from graybench.provenance import source_manifest

Suite = Literal["normal", "hard"]
Population = Literal["offline_143", "custom_development"]
IMAGE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
HEX_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
NATIVE_EXCEPTION_POLICIES = (
    "conservative_unattributed_v1",
    "test_exception_is_failure_v1",
)


def task_key(task: JudgeTask) -> str:
    return f"{task.public.suite}/{task.public.task_id}"


def suite_keys(suite: Suite) -> set[str]:
    return {f"{suite}/qiskitHumanEval/{number}" for number in range(151)}


class NativeCohort(Contract):
    """Content identity only; task admission and publication are separate gates."""

    track: Literal["qhe-pinned-native-v1"] = "qhe-pinned-native-v1"
    suite: Suite
    population: Population
    label: str = Field(min_length=1)
    task_keys: tuple[str, ...] = Field(min_length=1)
    task_digests: dict[str, str]
    excluded: dict[str, str]
    dataset_pin: dict[str, str]
    image: str
    extraction: ExtractionPolicy
    exception_policy: NativeExceptionPolicy = Field(
        default="conservative_unattributed_v1",
        exclude_if=lambda value: value == "conservative_unattributed_v1",
    )
    source_digest: str
    certification: Literal["development_only"] = "development_only"

    @property
    def publication_eligible(self) -> bool:
        return False

    @model_validator(mode="after")
    def valid_frozen_scope(self) -> "NativeCohort":
        if not IMAGE_DIGEST.fullmatch(self.image):
            raise ValueError("Native image must be an immutable SHA-256 digest")
        if self.extraction not in EXTRACTION_POLICIES:
            raise ValueError("Unknown extraction policy")
        if self.extraction == "exact_prompt_suffix_v1" and self.suite != "normal":
            raise ValueError("Exact prompt suffix is available only for the normal suite")
        if not HEX_DIGEST.fullmatch(self.source_digest):
            raise ValueError("Native source identity must be a SHA-256 digest")
        if not self.label.strip():
            raise ValueError("Native cohort label must be nonempty")
        if len(set(self.task_keys)) != len(self.task_keys):
            raise ValueError("Native task keys must be unique")
        if set(self.task_digests) != set(self.task_keys):
            raise ValueError("Native task digests must match scheduled keys")
        if any(not HEX_DIGEST.fullmatch(value) for value in self.task_digests.values()):
            raise ValueError("Invalid native task digest")
        expected = suite_keys(self.suite)
        scheduled = set(self.task_keys)
        if scheduled - expected or set(self.excluded) != expected - scheduled:
            raise ValueError("Native exclusions must cover every unscheduled pinned task")
        if any(not reason.strip() for reason in self.excluded.values()):
            raise ValueError("Native exclusions require explicit reasons")
        if self.population == "offline_143":
            external = {f"{self.suite}/qiskitHumanEval/{number}" for number in EXTERNAL_IDS}
            if (
                len(self.task_keys) != 143
                or set(self.excluded) != external
                or any(reason != "external_service" for reason in self.excluded.values())
            ):
                raise ValueError("Offline cohort must be the exact 143-task pinned subset")
        if set(self.dataset_pin) != {"repo", "revision", "sha256"} or any(
            not value for value in self.dataset_pin.values()
        ):
            raise ValueError("Native dataset pin is incomplete")
        return self


def validate_native_cohort(
    cohort: NativeCohort, tasks: tuple[JudgeTask, ...], *, cache: Path
) -> None:
    """Re-read pinned bytes so caller-supplied task objects cannot claim provenance."""
    # Pydantic's frozen models do not recursively freeze their dict fields.
    NativeCohort.model_validate_json(cohort.model_dump_json())
    if cohort.dataset_pin != PINS[cohort.suite]:
        raise ValueError("Pinned dataset revision changed")
    if cohort.source_digest != source_manifest()["digest"]:
        raise ValueError("Native engine source changed")
    pinned = load_suite(cohort.suite, cache)
    indexed = {task_key(task): task for task in pinned}
    keys = tuple(task_key(task) for task in tasks)
    if keys != cohort.task_keys:
        raise ValueError("Native scheduled task order or suite changed")
    if keys != tuple(key for key in indexed if key in cohort.task_digests):
        raise ValueError("Native task order differs from pinned dataset order")
    for key, task in zip(keys, tasks, strict=True):
        if task.digest != cohort.task_digests[key] or task.digest != indexed[key].digest:
            raise ValueError("Native task differs from the pinned dataset")


def freeze_native_cohort(
    tasks: tuple[JudgeTask, ...],
    *,
    cache: Path,
    suite: Suite,
    population: Population,
    image: str,
    extraction: ExtractionPolicy,
    exception_policy: NativeExceptionPolicy = "conservative_unattributed_v1",
    label: str,
    excluded: dict[str, str],
) -> NativeCohort:
    """Freeze exact input and exclusions before any model generation."""
    cohort = NativeCohort(
        suite=suite,
        population=population,
        label=label,
        task_keys=tuple(task_key(task) for task in tasks),
        task_digests={task_key(task): task.digest for task in tasks},
        excluded=dict(excluded),
        dataset_pin=dict(PINS[suite]),
        image=image,
        extraction=extraction,
        exception_policy=exception_policy,
        source_digest=source_manifest()["digest"],
    )
    validate_native_cohort(cohort, tasks, cache=cache)
    return cohort
