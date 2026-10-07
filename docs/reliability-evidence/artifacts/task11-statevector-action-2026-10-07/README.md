# Task 11 host verification

The [report](report.json) recreates fixed authored controls, independent literal
state calibration and the original fixed-state false pass. There are 43
calibrated states and 32 normal/hard trials: ten expected passes and 22 expected
failures, all observed as expected. Maximum SDK-versus-independent amplitude
difference is `4.577566798522237e-16`. Both original checks accept the fixed example
state, which differs from the X0 counterexample by maximum aligned entry error one.

These are trusted host fixtures. No model answer, API call or isolated container
runs in this report. It is not a production verdict transcript, native-object
attestation, runtime qualification, independent admission or score. Publication
eligibility and independent-review status are false. See the
[development condition](../../task11-statevector-action-development.md).

Environment: Python 3.12.14, Qiskit 2.4.2, NumPy 2.2.4.
Engine source:
`15dc8065e371c3b28d9e30883c8845b3cb768104bc4574f3f5cdaa9948f7180e`.
Report: 110,048 bytes, SHA-256
`5763559fc39e43963c91714890241ab4d98feefab08aaac81c326a0c08df8a3d`.
Diagnostic script SHA-256:
`8638488ec07fc77e8220101572ed9e6e95f965ab14f583c13d692acb2fd3b7ac`.
Control script SHA-256:
`1e95796a2224e19029e5d5e8614ab82a3d3589fda9808a435d6c88483f9f2c76`.
Oracle text SHA-256:
`3256bf2f5e3ac32cbf780b8d1a473bac0aa9e3847d17d9661818142d05f5450c`.

From `engine/`, reproduce exactly:

```powershell
python ../docs/reliability-evidence/task11_local_verification.py <pinned-cache> ../docs/reliability-evidence/artifacts/task11-statevector-action-2026-10-07/report.json --check
```

The script refuses to overwrite existing evidence. Pins, full/public task digests,
original test hashes, both scripts and the oracle text are bound in the report.
Prior diagnostics and inventories retain their historical engine source bindings.

The [full offline test run](full.xml) passed 1,653 tests and skipped 293, with
zero failures/errors, in 576.67 seconds. It used locked Python/Qiskit dependencies
and the pinned cache, without any container test-image settings. Its 60 warnings
comprise 48 original Diagonal deprecations and 12 Windows cleanup warnings.
All 22 local Task 11 tests passed; its isolated control group is one of the skips.
Ten retained-graph groups traversed 430 call pairs. Exact host-report recreation
passed, as did Ruff lint/formatting for 241 engine/audit files. These are local
development checks, not isolated runtime qualification or independent admission.
Full JUnit SHA-256:
`e3127b093c2187e34091ed35081bf285d104428911477a5d7f971cc6a3af59be`.
