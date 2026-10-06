# Native reference calibration, 2026-09-27

The later [2026-10-05 current-source calibration](artifacts/native-reference-current-2026-10-05/README.md)
reran all 286 offline canonical answers under the current engine and pinned
image. Both suites passed 143/143, with a verifier that binds every result to
the current pinned answer and judge manifest. The historical results below
remain separate evidence for their earlier source.

A [current-source 572-case literal-mutant screen](artifacts/native-literal-mutants-2026-10-05/README.md)
used the same cohorts. Empty-list answers passed tasks 110 and 139 in both
suites, reproducing known vacuous-loop findings. Canonical passes therefore
must not be read as oracle soundness.

The new `native-reference-scan` command ran the pinned canonical answers in
fresh Docker containers through the same native judge used for model answers.
It wrote append-only, source-bound evidence through the existing reference
scan chain. These are calibration runs, not model generations or scores.

| Suite and answer format | Planned offline tasks | Canonical pass | Evidence SHA-256 | Chain head |
| --- | ---: | ---: | --- | --- |
| [Normal, exact prompt suffix](native-reference-normal-2026-09-27-final.jsonl) | 143 | 143 | `a3a96f9bd3117b92034a63e5fc6652e1c19ddd513f269fc59444ba3d1d11c1b6` | `d6ff0d4ccd0e46f8a3aee31563a3451c66981896f661265e2ad99e05936d6d10` |
| [Hard, raw or single Python fence](native-reference-hard-2026-09-27-final.jsonl) | 143 | 143 | `f84b729ea058f1c3b95411581fb58ec651be8cc50e4cce2b47b66a1c8b672bc5` | `7bf5a36c424a2ef631ff3e92aecef4559e0c24e090e9051507af7f42242c28a7` |

Both `reference-inspect` chains completed with no pending task. Each excludes
the same eight pinned external-service IDs. The source manifest digest was
`a41a40c8a65c42739ef73c88fbca9fa79404bd548897080496b6b1d75193c54e`;
the runtime image was
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`.
The normal cohort digest was
`82a2db728c42f3626b27f75d117d208c2c43a568ec8d94e167975afc9e3caeb5`;
the hard cohort digest was
`fa5bc808703791ccf70397d2c811f97643d2a3d95c0e3f3c9db0d08a6917e8a1`.
The header of each chain binds its exact pinned task digests, extraction policy,
excluded task map, and engine source files. Each result binds its judge and
worker manifest.

To reproduce with the same cache and image, use a new output path for each
invocation:

```sh
graybench native-reference-scan CACHE NORMAL.jsonl --suite normal --image sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd --extraction exact_prompt_suffix_v1
graybench native-reference-scan CACHE HARD.jsonl --suite hard --image sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd --extraction raw_or_single_python_fence_v1
graybench reference-inspect NORMAL.jsonl
graybench reference-inspect HARD.jsonl
```

A single canonical pass only shows that this answer completed this pinned test
once in the specified environment. It does not show that another valid answer
would pass, that wrong answers fail, or that a randomized test is stable.
The later [randomness-focused repeat bundle](artifacts/native-stochastic-repeat-2026-09-28/README.md)
records three additional canonical passes per suite for tasks 62, 63, 100 and
109. This limited spot check does not resolve their oracle adequacy or admit
them for publication.
In particular, [prior task-63 analysis](reference-scan-77f29ff.md) found hidden
randomness coupling. A new [four-case native control](native-task63-control-2026-09-27-final.jsonl)
through the same image and policies passed both canonical answers **and** a
function that ignores the circuit and always returns the fixed string `"1"` in
both suites. This directly demonstrates that the pinned task-63 tests can
award a native pass without the requested BB84 behavior. The chain verified
complete, with SHA-256
`8430d0e170affce1c7e50a13f11a85adf9ff11abb69b295b02bb221136e22c27`,
head `31f8b46fe00b5623fc831249e081d86af06aa4314e15f2b3bc5c887eed333e36`,
and [probe source](native_task63_control.py) SHA-256
`b265af253010a7bc4ec31b00a8ff3f2e05ba970fa144c32c03e115e45d030ac7`.
Both task-63 variants remain ineligible for release.

The [first control attempt](native-task63-control-invalid-suffix-2026-09-27.jsonl)
is preserved separately under the earlier source manifest (SHA-256
`ecf356a1a60cee74eb4ea9e55094a453d53a44173b48681a1df470698d5d75f6`).
It omitted the leading newline needed to complete the normal prompt's final
docstring line, so the normal constant answer was rejected during extraction
and did not test the oracle. The corrected chain above uses a new output file;
the first chain is not counted as evidence of normal oracle rejection.

The native same-process test-integrity limit and pending task admission also
remain. These historical scans do not change model denominators, classify
non-assertion test exceptions as candidate failures, or authorize a published
accuracy. A `None` return in the
[task-4 exception case](native-answer-format-conditions.md) can make the
pinned Qiskit assertion raise `QiskitError`, which the default native policy
conservatively treats as an infrastructure error. A canonical pass alone is
not a sound blanket exception-attribution policy. The companion
[286-case null-return screen](native-null-return-screen.md) quantifies this
ambiguity across both offline suites. A later
[explicit development scoring condition](native-exception-policy.md) has its
own source-bound calibration and control chains.
