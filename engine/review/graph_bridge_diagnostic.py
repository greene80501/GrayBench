"""Preserve actual protected protocol4/native outcomes for six known identity cases."""

import argparse
import hashlib
import json
import runpy
from dataclasses import asdict
from pathlib import Path

from graybench.upstream import UpstreamJudge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--docker", default="docker")
    args = parser.parse_args()
    engine = Path(__file__).resolve().parents[1]
    fixture_path = engine / "tests/test_graph_bridge.py"
    fixtures = runpy.run_path(str(fixture_path))
    judge = UpstreamJudge(image=args.image, docker=args.docker, protocol=4)
    outcomes = []
    with args.output.open("xb") as stream:
        for name, code, test, expected in fixtures["CASES"]:
            namespace = {}
            exec(code, namespace)
            exec(test, namespace)
            native = "pass"
            try:
                namespace["check"](namespace["answer"])
            except AssertionError:
                native = "fail"
            result = judge.evaluate(fixtures["task"](test), code)
            assert native == result.outcome == expected, (name, native, result)
            for file, digest in result.evidence["manifest"]["files"].items():
                assert (
                    hashlib.sha256((engine / "src/graybench" / file).read_bytes()).hexdigest()
                    == digest
                )
            record = {
                "scope": "trusted_fixture_native_and_actual_protected_graph_bridge",
                "fixture": name,
                "native": native,
                "expected": expected,
                "judgment": asdict(result),
                "model_score": False,
                "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
                "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            }
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n")
            stream.flush()
            outcomes.append({"fixture": name, "outcome": result.outcome})
            print(name, native, result.outcome, flush=True)
    print(
        json.dumps(
            {"cases": outcomes, "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}
        )
    )


if __name__ == "__main__":
    main()
