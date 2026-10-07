# Local evolution matrix-value calibration

The [report](report.json) binds engine source
`1b845366bfc60a76f91b771f353ed58da91815cf26e5b70f5688c4f1232ae40f`
and [calibration script](../../evolution_value_calibration.py) SHA-256
`4ab5a6c1a6c21eb16a4873c17f9e5d61feee24a3b22fadc4e068ed3d4655d94d`.
The report has 183,987 bytes and SHA-256
`b71d2eefe844ebf74248dfdeeb121842320e59711497826eaf1a265666c807bf`.
It records Windows, Python 3.12.14, Qiskit 2.4.2, NumPy 2.2.4 and SciPy 1.18.1.

All 30 authored controls matched their declared outcomes across normal and
hard: six passes, 20 numerical failures and four invalid-output rejections.
Each scored answer includes all 80 case results, totaling 2,080 numerical
checks. Invalid outputs are rejected before numerical scoring. Response hashes
and byte counts bind the real worker/parser boundary; the largest response was
196,113 bytes, below the existing one-MiB output allowance. Manifests record
exact pinned source/public/contract/case identities and both oracle-code hashes.

An independent literal-tensor construction checked all 1,364 unsigned Pauli
strings of widths one through five at times `0.0`, `-0.23` and `0.71`: 4,092
cases agreed with the basis-index oracle, with observed maximum entry error
zero. No phase alignment was applied. This finite calibration does not prove
complete-domain correctness or establish valid model behavior.

The correct controls use canonical Qiskit computation with an explicit matrix
export, tensor eigendecomposition and parity-rotation circuits. Wrong controls
test sign, angle, tensor ordering, transpose, conjugation, phase and magnitude,
including finite components `1.7e308 + 1.7e308j`. Review found that this last
answer could overflow complex absolute error and abort the judge. The direct
regression and actual worker/parser-to-judge controls failed before the repair;
the oracle now reports a deterministic numerical failure. Read-only review of
the repair found no additional issue in its bounded scope. It is not an
independent task-admission attestation.

Only trusted authored fixtures were executed in local subprocesses. This is
not sandbox, container, retained-state, native-object or campaign qualification.
The script must not be used to execute model output. Original QHE/native/graph
conditions and historical results remain unchanged; see the
[separate revised public contract](../../protected-task116-evolution-value.md).
Publication eligibility and independent admission remain false.

From `engine/`, reproduce into a new filename:

```sh
uv run --locked --extra dataset --extra qiskit python ../docs/reliability-evidence/evolution_value_calibration.py --cache CACHE --output NEW_REPORT.json
```

The script refuses an existing output file and stops on an unexpected authored
outcome, parser failure for a correct control, excessive output, worker failure
or mathematical disagreement. It preserves response identities rather than
calling a local process an isolated production runner. Docker controls remain
pending.

The full main-checkout offline suite with locked dependencies and pinned cache
passed **1,591**, skipped **292**, and had zero failures in 442.66 seconds.
Container image tests and strict canonical graph qualification were disabled.
Its 60 warnings comprise 48 original Qiskit `Diagonal` deprecations and 12
Windows temporary-directory cleanup warnings. The task-116 focused run passed
19, skipped its one container check and reported 12 cleanup warnings in 10.74
seconds. Ruff lint and formatting passed for 231 files across engine source,
tests and this evidence script, when run from `engine/`. Running lint from the
legacy root changes package classification and is not the engine lint command.
These checks verify offline implementation behavior, not runtime admission.

A clean checkout of `31cf4fd`, with separately installed locked dependencies on
the same host, reproduced this report byte-for-byte, including source hashes,
worker responses and all calibration results. Its task-116, semantic-judge,
protected-campaign and control-review tests passed **47**, skipped **11**, and
reported 12 Windows cleanup warnings in 19.76 seconds. The same 231-file lint
and formatting checks passed. The checkout was clean before and after
verification. This is a focused clean reproduction, not a new full clean-suite
run, an independently administered experiment or an admission attestation.
