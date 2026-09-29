# Task-62 protected value case-coverage limit

The current `task62-bb84-sender-amplitudes-v1` condition freezes 124 valid
state/basis pairs. Its declared binary-list domain has 1,364 pairs over widths
one through five. Widths one through three are exhaustive; widths four and five
are sampled. The [host-side probe](task62_case_coverage_probe.py) constructs a
function that computes the correct BB84 amplitudes on every frozen input but
returns the wrong state on the omitted valid input `state=[1,0,0,0]`,
`basis=[0,0,0,0]`. It passes the host oracle on all 124 frozen pairs and fails
on the omitted pair. This is an exact case-set false pass, not a model result.
An optional isolated-worker run also confirms that the current
normal and hard protected judges accept the constructed Python candidate.

From `engine/`, reproduce without API access, Docker, or the pinned dataset
cache:

```sh
uv run --locked python ../docs/reliability-evidence/task62_case_coverage_probe.py
```

With the pinned QHE cache and image available, execute the same mutant in the
Docker value worker:

```sh
uv run --locked python ../docs/reliability-evidence/task62_case_coverage_probe.py --cache CACHE --image sha256:IMAGE_ID
```

On source digest `bcd6b4379ee62c3c8a15be4d6368e961467ab7506d6787a39ede36d60782a70d`
and image `sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`,
both suites returned `pass` on all 124 cases under a 60-second diagnostic
timeout. The candidate source hash was
`1fc8e6b76fa1cecda4da6309d1c16c78f38a38be06e0cec2613cd9208dcbdc67`.
This run has a different judge timeout from the preserved 16-control bundle,
so its judge digests are a separate diagnostic condition. No model was queried
and no prior judgment was changed.

The probe prints its source-manifest digest, script hash and frozen-input
digest so the result can be bound to the implementation under review. This
version's script SHA-256 is
`cd77e5c929c78bb189d1387011ecae154bc687caea04abcd9f96f71d4c905bb9`,
and its frozen-input digest is
`96b6e251b970c74d9386783abb343b454224538e71830e2fcd579d5f2e4c57c3`.

One straightforward correct numeric representation of all 1,364 expected outputs
was 533,164 bytes in compact JSON in a local sizing check, below the runner's
default 1 MiB output limit. That single representation is not resource
calibration: other correct implementations, serialization choices and runtimes
may exceed the limit or timeout. The current `ProtectedSemanticTask` schema
also caps cases at 256. An exhaustive condition therefore needs a separately
versioned oracle and case contract, raised and calibrated resource limits,
positive alternatives and wrong-answer controls, then a new source-bound
admission review. It must preserve v1 evidence rather than rewriting old
judgments. Even exhaustive inputs would attest only the stated amplitude
values, not a native `QuantumCircuit` or the algorithm used to produce them.
