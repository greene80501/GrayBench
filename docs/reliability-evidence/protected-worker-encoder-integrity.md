# Protected worker-encoder integrity probe

The [probe source](protected-worker-encoder-probe.py) evaluates authored completions
against the **exact pinned normal and hard task-2 records**, with the opt-in
`qhe2-bell-statevector-v1` revision and immutable evaluator image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`.
It creates no model completion and makes no provider API request.

Each suite rejects an ordinary function returning the wrong `|01>` Statevector.
Each accepts a function that returns that same wrong state but replaces the
candidate worker's global `encode` through its caller frame, causing the worker
to serialize Phi-plus. The trusted judge sees the substituted, valid wire value.
The [earlier local probe](worker-encoder-integrity.md) separately observes the
wrong raw return value before encoding. Neither observation implies that a model
has attempted this, and neither licenses a benchmark score.

The [byte-preserved record](GrayBench-protected-worker-encoder-probe.json) has
SHA-256 `2d88a706b725e613d35f0a267ce9ae7d1c459aabc0a96336177d4bc9ee960639`.
It binds the script SHA-256
`4cd06e7fe80ec8174196d7e0535f17ed82b3aec6441f8e7e8c07f6ed017842c3`,
source-manifest digest
`ea0f22f9f5b30d12fe8f6cb8fa5b23dc1fa174c230489604e8580c302390655d`,
Python 3.12.14, Qiskit 2.4.2, image, task and judge digests, completion digests,
and four outcomes. To reproduce with a verified pinned cache from `engine/`:

```powershell
uv run --extra qiskit --extra dataset python ../docs/reliability-evidence/protected-worker-encoder-probe.py --cache <pinned-cache> --image sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd --output <new-output.json>
```

`engine/tests/test_bell_revision.py` retains a strict, outcome-specific expected-failure control
for each suite. The focused protected run reported 18 passed, 2 expected failures.
The recipe manifest remains `release_eligible: false`. The benchmark must either
define and validate explicit value-only semantics for admitted tasks or establish
a different trusted execution boundary before claiming native-object fidelity.
This diagnostic alone does not validate either alternative across 302 tasks.

## Protocol-4 graph transport

The [separate graph probe](protected-graph-encoder-probe.py) evaluates the same
exact pinned task-2 records with protocol 4, testing both `snapshot-v1` and
`delta-v1`. Its ordinary `|01>` return fails in all four suite/transport
combinations. The authored adverse function obtains the candidate arena from
its caller frame and replaces the arena's `snapshot` method before returning
`|01>`. The substituted snapshot serializes Phi-plus, and the protected judge
passes all four combinations. This shows that graph validation and delta-frame
hashes validate **received state**, not the candidate's native return value.
The candidate has no private test or verdict access in this probe.

The [byte-preserved graph record](GrayBench-protected-graph-encoder-probe.json)
has SHA-256
`3e75de6a73f9c961dbba4683caf6d1bf6c427055be03f6ce4f39c1f452a62164`.
It binds script SHA-256
`72499da118b9bfa259665136b2fd1b9217f014a8335ad7861a5ed0fffef0c48f`,
source-manifest digest
`ea0f22f9f5b30d12fe8f6cb8fa5b23dc1fa174c230489604e8580c302390655d`,
Python 3.12.14, Qiskit 2.4.2, the immutable image, original/revised task
digests, per-transport judge digests, completion digests, and eight outcomes.
Reproduce from `engine/` with a verified pinned cache:

```powershell
uv run --extra qiskit --extra dataset python ../docs/reliability-evidence/protected-graph-encoder-probe.py --cache <pinned-cache> --image sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd --output <new-output.json>
```

Four strict, outcome-specific expected-failure controls in
`engine/tests/test_bell_revision.py` preserve the observed false pass. They
fail normally for unrelated judge outcomes and become strict unexpected passes
if the judge begins returning `fail`. Both graph transports and the task-2
revision remain release-ineligible. This probe is authored diagnostic input,
not model behavior, a released score, or a general proof about all task types.
