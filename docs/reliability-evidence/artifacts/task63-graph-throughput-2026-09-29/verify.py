"""Verify exact task-63 throughput probe bytes and recorded resource outcomes."""

import hashlib
import json
import sys
from pathlib import Path

from graybench.fs_paths import readable_path
from graybench.identity import identity
from graybench.provenance import source_manifest
from graybench.reference_scan import inspect_reference_scan

HERE = Path(__file__).resolve().parent
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
CONDITIONS = {
    "normal-width2-delta-1mib.jsonl": (2, 72, 1, 120, "pass"),
    "normal-width3-delta-16mib.jsonl": (3, 584, 16, 300, "timeout"),
}
CASE_KEYS = {
    "normal/63/simulator-reference",
    "normal/63/statevector-alternative",
}


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate evidence JSON key")
        result[key] = value
    return result


def pinned_bytes(bundle: Path, descriptor: dict, *, limit: int) -> bytes:
    if set(descriptor) != {"bytes", "file", "sha256"}:
        raise ValueError("Invalid file descriptor")
    name = descriptor["file"]
    if not isinstance(name, str) or name not in {"probe.py", *CONDITIONS}:
        raise ValueError("Unexpected evidence file")
    path = bundle / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked evidence file")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if (
        len(raw) > limit
        or len(raw) != descriptor["bytes"]
        or hashlib.sha256(raw).hexdigest() != descriptor["sha256"]
    ):
        raise ValueError("Evidence byte count or digest mismatch")
    return raw


def verify(bundle: Path = HERE) -> dict:
    bundle = readable_path(bundle)
    with (bundle / "manifest.json").open("rb") as stream:
        manifest_raw = stream.read(16 * 1024 + 1)
    if len(manifest_raw) > 16 * 1024:
        raise ValueError("Evidence manifest exceeds byte limit")
    manifest = json.loads(manifest_raw, object_pairs_hook=unique_pairs)
    if (
        set(manifest) != {"image", "logs", "probe", "schema_version", "scope", "source_digest"}
        or manifest["image"] != IMAGE
        or manifest["schema_version"] != "1"
        or manifest["scope"]
        != "task63 graph throughput feasibility; no model score or oracle admission"
        or [entry["file"] for entry in manifest["logs"]] != list(CONDITIONS)
    ):
        raise ValueError("Unexpected throughput evidence manifest")
    pinned_bytes(bundle, manifest["probe"], limit=64 * 1024)
    observations = {}
    for descriptor in manifest["logs"]:
        name = descriptor["file"]
        raw = pinned_bytes(bundle, descriptor, limit=16 * 1024 * 1024)
        summary = inspect_reference_scan(bundle / name)
        events = [
            json.loads(line, object_pairs_hook=unique_pairs)["event"] for line in raw.splitlines()
        ]
        header = events[0]
        width, count, wire_mib, timeout, outcome = CONDITIONS[name]
        selection = header["selection"]
        source = header["source"]
        if (
            not summary["complete"]
            or summary["file_sha256"] != descriptor["sha256"]
            or summary["planned"] != 2
            or set(header["tasks"]) != CASE_KEYS
            or source["digest"] != manifest["source_digest"]
            or identity(source["files"]) != source["digest"]
            or selection
            != {
                "case_count": count,
                "image": IMAGE,
                "max_width": width,
                "probe_sha256": manifest["probe"]["sha256"],
                "timeout": timeout,
                "transport": "delta-v1",
                "wire_mib": wire_mib,
            }
            or set(summary["results"]) != CASE_KEYS
            or any(value != outcome for value in summary["results"].values())
        ):
            raise ValueError("Throughput log header or outcomes differ")
        for event in events:
            if event["kind"] != "result":
                continue
            evidence = event["evidence"]
            judge = evidence["manifest"]
            if (
                event["judge_digest"] != identity(judge)
                or judge["image"] != IMAGE
                or judge["protocol"] != "upstream-graph-v4"
                or judge["graph_transport"]["mode"] != "delta-v1"
                or judge["output_limit"] != wire_mib * 1024**2
                or judge["judge_timeout"] != timeout
                or judge["candidate_timeout"] != 120
            ):
                raise ValueError("Throughput result judge binding differs")
            if outcome == "pass":
                if evidence.get("calls") != count:
                    raise ValueError("Passing throughput result did not cover every call")
            elif (
                not evidence.get("detail", "").startswith("Candidate sample")
                or not 119 <= evidence["candidate_active_seconds"] <= 121
                or not 0 < len(evidence["transcript"]) < count
            ):
                raise ValueError("Timeout was not a bounded candidate resource outcome")
        observations[name] = {
            "file_sha256": descriptor["sha256"],
            "chain_head": summary["chain_head"],
            "case_count": count,
            "results": summary["results"],
        }
    return {
        "verified": True,
        "source_digest": manifest["source_digest"],
        "source_matches_running_source": manifest["source_digest"] == source_manifest()["digest"],
        "observations": observations,
        "publication_eligible": False,
    }


if __name__ == "__main__":
    if len(sys.argv) > 2:
        raise SystemExit("Usage: verify.py [BUNDLE_DIRECTORY]")
    print(json.dumps(verify(Path(sys.argv[1]) if len(sys.argv) == 2 else HERE), sort_keys=True))
