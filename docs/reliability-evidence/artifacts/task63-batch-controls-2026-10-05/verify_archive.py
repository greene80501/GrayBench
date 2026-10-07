"""Verify the preserved compressed task-63 control log against its frozen plan."""

import gzip
import hashlib
import json
import tempfile
from pathlib import Path

from verify import verify_results

HERE = Path(__file__).resolve().parent
EXPECTED = {
    "schema_version": "1",
    "source_revision": "22a5f1ac9ae29e855242ddd2b7a59062e31b604b",
    "image": "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd",
    "plan_sha256": "04d67f997a637cebe8376e13294dcf4c85e50825e4f84e261476406a821b6055",
    "archive": {
        "path": "results.jsonl.gz",
        "bytes": 2397198,
        "sha256": "db10b31202993cef79d81d81765f5ad0647b491133d4102e8d6cd7e7ed7fdb8e",
    },
    "raw_log": {
        "bytes": 40030553,
        "sha256": "a7bbefeb705f6b9d578ee4ee1ef4b1bddb7493ee13cb1ee5adc9f528040e8f69",
        "chain_head": "5ec82240dd3dbc4fa7570716535eb886849306c61931d99e8bfcb226d2d240fc",
        "recorded_controls": 16,
        "outcomes": {"pass": 6, "fail": 8, "candidate_error": 2},
    },
    "publication_eligible": False,
}


def main() -> None:
    manifest_path = HERE / "result-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("Missing result manifest")
    manifest = json.loads(manifest_path.read_bytes())
    if manifest != EXPECTED:
        raise ValueError("Result manifest differs from the frozen control result")
    archive = HERE / EXPECTED["archive"]["path"]
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("Missing or linked control archive")
    if archive.stat().st_size != EXPECTED["archive"]["bytes"]:
        raise ValueError("Control archive byte count differs")
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != EXPECTED["archive"]["sha256"]:
        raise ValueError("Control archive digest differs")

    with tempfile.TemporaryDirectory(prefix="graybench-task63-verify-") as temp:
        raw_path = Path(temp) / "results.jsonl"
        raw_digest = hashlib.sha256()
        raw_bytes = 0
        with gzip.open(archive, "rb") as source, raw_path.open("xb") as target:
            while chunk := source.read(1024 * 1024):
                raw_bytes += len(chunk)
                if raw_bytes > EXPECTED["raw_log"]["bytes"]:
                    raise ValueError("Decoded control log exceeds frozen byte count")
                raw_digest.update(chunk)
                target.write(chunk)
        if (
            raw_bytes != EXPECTED["raw_log"]["bytes"]
            or raw_digest.hexdigest() != EXPECTED["raw_log"]["sha256"]
        ):
            raise ValueError("Decoded control log differs")
        report = verify_results(raw_path, HERE)
    if (
        report["plan_sha256"] != EXPECTED["plan_sha256"]
        or report["result_sha256"] != EXPECTED["raw_log"]["sha256"]
        or report["chain_head"] != EXPECTED["raw_log"]["chain_head"]
        or report["recorded_controls"] != EXPECTED["raw_log"]["recorded_controls"]
        or report["results"] != EXPECTED["raw_log"]["outcomes"]
        or report["publication_eligible"] is not False
    ):
        raise ValueError("Control result verification differs from the frozen manifest")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
