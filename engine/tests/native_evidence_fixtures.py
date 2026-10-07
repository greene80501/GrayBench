"""Synthetic current-plan verifier fixtures; never new execution evidence.

Historical worker messages are reused as test data, with freshly constructed
cohorts/manifests. Outputs live only in pytest temporary paths. This deliberately
does not authenticate a Docker run or relabel any committed historical artifact.
"""

import json

from graybench.datasets import load_suite
from graybench.identity import canonical, identity
from graybench.native_cohort import NativeCohort, freeze_native_cohort, task_key
from graybench.native_judge import NativeJudge
from graybench.provenance import source_manifest


def synthetic_current_native(cache, original, output):
    records = [json.loads(line) for line in original.read_bytes().splitlines()]
    header = records[0]["event"]
    selection = header["selection"]
    originals = (
        {selection["cohort"]["suite"]: selection["cohort"]}
        if "cohort" in selection
        else selection["cohorts"]
    )
    cohorts, judges, tasks_by_key = {}, {}, {}
    for suite, record in originals.items():
        historical = NativeCohort.model_validate_json(json.dumps(record))
        tasks = tuple(
            task for task in load_suite(suite, cache) if task_key(task) in historical.task_keys
        )
        cohort = freeze_native_cohort(
            tasks,
            cache=cache,
            suite=suite,
            population=historical.population,
            image=historical.image,
            extraction=historical.extraction,
            exception_policy=historical.exception_policy,
            label=historical.label,
            excluded=historical.excluded,
        )
        cohorts[suite] = cohort
        judges[suite] = NativeJudge(cohort, tasks, cache=cache)
        tasks_by_key.update((task_key(task), task) for task in tasks)
    header["source"] = source_manifest()
    if "cohorts" in selection:
        selection["cohorts"] = {
            suite: cohort.model_dump(mode="json") for suite, cohort in cohorts.items()
        }
        selection["cohort_digests"] = {suite: cohort.digest for suite, cohort in cohorts.items()}
    else:
        cohort = next(iter(cohorts.values()))
        selection["cohort"] = cohort.model_dump(mode="json")
        selection["cohort_digest"] = cohort.digest
    for record in records:
        event = record["event"]
        if event["kind"] != "result":
            continue
        key = event["task_key"].split("/")
        task = tasks_by_key["/".join(key[:3])]
        _, manifest = judges[task.public.suite].configuration(task)
        event["judge_digest"] = identity(manifest)
        event["evidence"]["manifest"] = manifest
    previous = "0" * 64
    for record in records:
        record["previous"] = previous
        record["digest"] = identity(
            {key: value for key, value in record.items() if key != "digest"}
        )
        previous = record["digest"]
    output.write_bytes(b"".join(canonical(record) + b"\n" for record in records))
    return output
