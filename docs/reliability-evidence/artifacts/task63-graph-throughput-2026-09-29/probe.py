"""Throwaway task-63 graph-call throughput probe; never a benchmark score."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from graybench.bb84_revision import (
    HARD_REFERENCE,
    PINNED_SOURCE_TASK_DIGESTS,
    REFERENCE_BODY,
    BB84Judge,
)
from graybench.datasets import load_suite
from graybench.identity import identity
from graybench.reference_scan import run_evidence_cases
from graybench.upstream import UpstreamJudge


def check_source(max_width: int) -> str:
    return f"""def check(candidate):
    from itertools import product
    from qiskit import QuantumCircuit
    for width in range(1, {max_width + 1}):
        vectors = tuple(product((0, 1), repeat=width))
        for sender in vectors:
            for receiver in vectors:
                for bits in vectors:
                    circuit = QuantumCircuit(width)
                    for i, bit in enumerate(bits):
                        if bit:
                            circuit.x(i)
                        if sender[i]:
                            circuit.h(i)
                    expected = ''.join(str(bits[i]) for i in range(width)
                                       if sender[i] == receiver[i])
                    observed = candidate(list(sender), circuit, list(receiver))
                    assert type(observed) is str
                    assert observed == expected
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--suite", choices=("normal", "hard"), required=True)
    parser.add_argument("--max-width", type=int, choices=(2, 3), required=True)
    parser.add_argument("--transport", choices=("snapshot-v1", "delta-v1"), required=True)
    parser.add_argument("--wire-mib", type=int, choices=(1, 16), required=True)
    parser.add_argument("--timeout", type=int, choices=(120, 300), default=120)
    args = parser.parse_args()

    docs = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(docs))
    from task63_explicit_bases_probe import STATEVECTOR  # noqa: PLC0415

    source = load_suite(args.suite, args.cache)[63]
    if source.digest != PINNED_SOURCE_TASK_DIGESTS[args.suite]:
        raise ValueError("Pinned task 63 differs")
    revised = BB84Judge(image=args.image).revise(source)
    check = check_source(args.max_width)
    task = revised.model_copy(update={"upstream_test": check})
    judge = UpstreamJudge(
        image=args.image,
        protocol=4,
        graph_transport=args.transport,
        timeout=args.timeout,
        candidate_timeout=120,
        output_limit=args.wire_mib * 1024**2,
    )
    controls = (
        ("simulator-reference", REFERENCE_BODY if args.suite == "normal" else HARD_REFERENCE),
        ("statevector-alternative", STATEVECTOR),
    )
    rows = []
    for name, code in controls:
        metadata = {
            "suite": args.suite,
            "source_task_digest": source.digest,
            "revised_task_digest": task.digest,
            "test_sha256": hashlib.sha256(check.encode()).hexdigest(),
            "candidate_sha256": hashlib.sha256(code.encode()).hexdigest(),
            "max_width": args.max_width,
            "transport": args.transport,
            "wire_mib": args.wire_mib,
            "timeout": args.timeout,
            "expected": "pass",
        }
        rows.append((f"{args.suite}/63/{name}", identity(metadata), (task, code)))
    summary = run_evidence_cases(
        rows,
        lambda case: judge.evaluate(*case),
        args.output,
        purpose="task63 exhaustive-case feasibility; not model scoring",
        selection={
            "image": args.image,
            "max_width": args.max_width,
            "transport": args.transport,
            "wire_mib": args.wire_mib,
            "timeout": args.timeout,
            "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "case_count": sum(8**width for width in range(1, args.max_width + 1)),
        },
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
