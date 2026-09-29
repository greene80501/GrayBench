"""Verify the BB84 control ledger, declared outcomes, source and runtime bindings."""

import hashlib
import json
import re
import sys
from pathlib import Path

from graybench.bb84_revision import PINNED_SOURCE_TASK_DIGESTS, RECIPE
from graybench.fs_paths import readable_path
from graybench.identity import identity
from graybench.provenance import source_manifest
from graybench.reference_scan import inspect_reference_scan


def main(path: Path):
    path = readable_path(path)
    summary = inspect_reference_scan(path)
    if not summary["complete"] or summary["planned"] != 14:
        raise ValueError("BB84 evidence is incomplete")
    with path.open("rb") as stream:
        raw = stream.read(64 * 1024 * 1024 + 1)
    if len(raw) > 64 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != summary["file_sha256"]:
        raise ValueError("BB84 evidence exceeds byte limit or changed during inspection")
    rows = [json.loads(line)["event"] for line in raw.splitlines()]
    header = rows[0]
    selection = header["selection"]
    probe = Path(__file__).with_name("task63_explicit_bases_probe.py")
    source = header["source"]
    if (
        not isinstance(source, dict)
        or set(source) != {"files", "digest"}
        or not isinstance(source["files"], dict)
        or not source["files"]
        or any(
            not isinstance(name, str)
            or ".." in name.split("/")
            or not name.endswith(".py")
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            for name, digest in source["files"].items()
        )
        or identity(source["files"]) != source["digest"]
    ):
        raise ValueError("Recorded engine source manifest is invalid")
    if (
        selection["recipe"] != RECIPE
        or re.fullmatch(r"[0-9a-f]{64}", selection["probe_sha256"]) is None
        or re.fullmatch(r"sha256:[0-9a-f]{64}", selection["image"]) is None
    ):
        raise ValueError("Probe identity differs from the declared identity")
    cases = selection["cases"]
    if len(cases) != 14 or set(cases) != set(summary["results"]):
        raise ValueError("BB84 case roster differs from the result roster")
    if any(header["tasks"][key] != identity(record) for key, record in cases.items()):
        raise ValueError("BB84 declared case identity differs from selection metadata")
    declared = selection.get("declared_judges")
    if declared is not None and (
        not isinstance(declared, dict)
        or set(declared) != {f"{suite}/qiskitHumanEval/63" for suite in ("normal", "hard")}
    ):
        raise ValueError("BB84 predeclared judge roster differs")
    for event in rows:
        if event["kind"] != "result":
            continue
        key = event["task_key"]
        case = cases[key]
        suite = key.split("/", 1)[0]
        if case["original_task_digest"] != PINNED_SOURCE_TASK_DIGESTS[suite]:
            raise ValueError("Original pinned task identity mismatch")
        evidence = event["evidence"]
        judgment = evidence["judgment"]
        manifest = judgment["manifest"]
        inner = judgment["inner"]
        if declared is not None and manifest != declared[f"{suite}/qiskitHumanEval/63"]:
            raise ValueError(f"BB84 predeclared judge differs from result: {key}")
        if (
            event["outcome"] != case["expected"]
            or evidence["expected"] != case["expected"]
            or evidence["matches_expectation"] is not True
            or event["judge_digest"] != identity(manifest)
            or manifest["track"] != RECIPE
            or manifest["release_eligible"] is not False
            or manifest["pinned_source_task_digest"] != case["original_task_digest"]
            or manifest["task_digest"] != case["revised_task_digest"]
            or manifest["public_task_digest"] != case["revised_public_digest"]
            or manifest["source"] != header["source"]
            or inner["manifest"]["image"] != selection["image"]
            or inner["manifest"]["protocol"] != "upstream-graph-v4"
            or inner["public_task_digest"] != case["revised_public_digest"]
            or inner["completion_sha256"] != case["completion_sha256"]
        ):
            raise ValueError(f"BB84 result binding or outcome mismatch: {key}")
    report = {
        **summary,
        "source_digest": source["digest"],
        "source_matches_running_source": source == source_manifest(),
        "probe_matches_running_probe": selection["probe_sha256"]
        == hashlib.sha256(probe.read_bytes()).hexdigest(),
        "judge_predeclared": declared is not None,
        "publication_eligible": False,
    }
    print(json.dumps(report, sort_keys=True))
    return report


if __name__ == "__main__":
    main(Path(sys.argv[1]))
