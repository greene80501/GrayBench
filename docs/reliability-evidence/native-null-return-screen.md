# Native test-exception screen, 2026-09-27

The [source-bound diagnostic chain](native-null-return-screen-2026-09-27.jsonl)
ran a deliberately incomplete candidate against every offline pinned normal
and hard task in the native Docker image. Normal responses appended a newline
and `return None` to the public function prefix. Hard responses defined the
declared entry point with variadic arguments and returned `None`. All 286
responses passed the selected answer-format parser before judgment. This is a
candidate-control screen, not a model score, semantic task admission, or a
claim that `None` is wrong under every possible public contract.

| Suite | Planned offline tasks | `fail` | `infrastructure_error` | Pass |
| --- | ---: | ---: | ---: | ---: |
| Normal, exact prompt suffix | 143 | 81 | 62 | 0 |
| Hard, raw or single Python fence | 143 | 81 | 62 | 0 |

Every normal/hard pair has the same outcome and exception type. All 124
`infrastructure_error` outcomes contain a completed native worker result with
phase `test`, rather than a Docker launch or missing-result failure. Per suite,
the worker exception types are 28 `AttributeError`, 22 `TypeError`, 11
`QiskitError`, and one `FileNotFoundError`. The latter is task 82's test trying
to open `bell.qpy` after the candidate failed to create it. Task 4's
`QiskitError` is another direct example: its test passes `None` to Qiskit's
`Operator` constructor. The 62 affected task numbers, shared by both suites,
are:

`2, 3, 4, 7, 8, 10, 16, 17, 18, 19, 20, 21, 22, 23, 25, 37, 38, 39, 44, 45, 46, 47, 61, 74, 76, 77, 78, 81, 82, 83, 85, 86, 87, 88, 89, 91, 92, 93, 94, 95, 100, 102, 103, 104, 108, 109, 110, 111, 112, 113, 114, 136, 137, 139, 140, 141, 142, 143, 144, 147, 148, 150`.

The chain completed with no pending task. Its SHA-256 is
`d2771018cf0afc28d1487a3aceaa416cc7495d47c8249740d7343c2196bbe790`,
its head is `80ad38e88b8dce735fa739087ddea5cd3c489884bac3a0702e66cbf1dda540b2`,
and its [probe source](native_null_return_screen.py) SHA-256 is
`d0598eeb64c2ecaa6709461a8f8081df16599120c3783364acd70ef9d1f83594`.
The bound engine source digest
`a41a40c8a65c42739ef73c88fbca9fa79404bd548897080496b6b1d75193c54e`
and runtime image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`
match the [complete canonical calibration](native-reference-calibration.md),
where all 143 canonical answers passed in each suite. Eight external-service
tasks per suite were excluded before freezing either cohort.

This shows that the worker's current status name conflates a completed
test-phase exception with a failure to run the infrastructure. It does not
prove that every such exception is safely attributable to the candidate:
a test can be defective or unstable, and the native same-process candidate can
tamper with test state. Automatically turning all 124 outcomes into scored
candidate failures would hide those possibilities. The conservative current
behavior leaves a run unscored when this happens. A release policy needs
reviewed task contracts and positive and negative controls, explicit
candidate-versus-harness exception attribution, and a versioned decision
about the denominator. This diagnostic changes none of those policies.
