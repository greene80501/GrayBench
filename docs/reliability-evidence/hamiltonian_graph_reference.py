"""Diagnostic official-reference replay for family 116, outside scoring."""

import argparse
import json
from pathlib import Path

from graybench.datasets import load_suite
from graybench.reference_scan import run_reference_scan
from graybench.upstream import UpstreamJudge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--docker", default="docker")
    args = parser.parse_args()
    data = Path(__file__).resolve().parents[2] / "data" / "datasets"
    tasks = [
        task
        for suite in ("normal", "hard")
        for task in load_suite(suite, data)
        if task.public.family_id == "qhe/116"
    ]
    assert len(tasks) == 2
    judge = UpstreamJudge(image=args.image, docker=args.docker, protocol=4)
    result = run_reference_scan(
        tasks,
        judge,
        args.output,
        selection={
            "families": [116],
            "suites": ["normal", "hard"],
            "bridge_protocol": 4,
            "purpose": "Hamiltonian gate interface calibration; not model scoring",
        },
    )
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
