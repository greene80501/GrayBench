# Task41 explicit Pauli subsystem development evidence

The [development condition](../../task41-explicit-subsystems.md) resolves the
normal prompt's XZ/YX conflict by declaring YX and its previously private placement
on qubits `[0, 2]` before generation. The original tasks and evidence stay unchanged.
This value condition is separate from original native scores and external baselines.

[host-plan.json](host-plan.json) was written before control execution and binds
exact ancestor/revised/public digests, authored completion hashes, engine source,
oracle, script hashes and calibration expectations. [host.json](host.json) exactly
recreates 90 normal/hard trials: 36 pass, 50 fail and four outside-domain codec
screens unsupported. Unsupported encoding is distinct from an oracle rejection.

Independent tensor factors calibrate all 16 two-qubit Pauli labels over six ordered
placements against the SDK: 96 numeric agreements, two matching target constructions
pass and 94 fail. The reversed local description XY on `[2, 0]` produces the same
target and passes. All 128 individual matrix-entry mutations fail. The 262 fixed
phase comparisons agree with analytic chord distance: four within tolerance pass
and 258 fail. These finite probes are not an exhaustive numerical proof.

Both exact original checker functions accept an authored non-Operator object with
an equality method that always returns true. This host false pass remains separate
from its protected codec outcome, unsupported. The revision's checker never calls
candidate equality/equivalence methods. No model-generated code executes on the host.

Logical matrix values and dimensions are checked, with any correct construction
allowed. Operator binding tags, layout, ownership, writeability and dtype metadata
are not attested; complex64/complex128 values reconstruct as complex128 without
changing supported numeric values. The public contract declares these choices.
This is not proof of constructor use or candidate native object identity.

No model generation, API call or isolated container runs in these reports. Host
codec round trips do not qualify candidate encoder integrity, process isolation,
resource behavior or independent human admission. All release/qualification flags
remain false. The isolated semantic roster predeclares 86 cases (36 pass, 50 fail)
and two judge manifests; its test is skipped until an explicit image is supplied.

Environment: Python 3.12.14, Qiskit 2.4.2, NumPy 2.2.4, SciPy 1.18.1.
Engine source digest:
`3b137cbcf666d377d0347ba0eca6a77b9d07e06eaf712e93cb514764c9bae91e`.

From `engine/` at this exact source, recreate saved host evidence without overwriting:

```powershell
python ../docs/reliability-evidence/task41_local_verification.py <pinned-cache> ../docs/reliability-evidence/artifacts/task41-explicit-subsystems-2026-10-07/host.json --check
```

Exact recreation passes in main and read-only AI review. The [focused JUnit record](focused.xml)
contains 20 passes, one isolated skip, zero failures/errors and 2.064
JUnit seconds. The [full offline regression record](full.xml) contains **1,767 passes,
295 skips, zero failures/errors**, and 619.045 JUnit seconds
(619.08 wall seconds). Its 48 warnings are original Diagonal deprecations.
The [verification record](verification.json) binds exact bytes, dependencies, source
and bounded review scope. Ruff lint/formatting pass for 251 source/test/evidence files.
Neither the full local suite nor AI review qualifies the skipped isolated groups.

host-plan.json: 67,952 bytes, SHA-256
`4638e007fc552a118e8c720dea93d69f3cf0975eeeab985b79157cd9162fb146`.

host.json: 260,930 bytes, SHA-256
`98f0eedcafe5d0623378d5680a0a32790bfd93521d1c248659c95ca9095dd67f`.

focused.xml: 3,313 bytes, SHA-256
`9e3cde9647a89b2e755a2cc667238eaad4c7250241aff09b3e9ce517bfc144c1`.

full.xml: 391,321 bytes, SHA-256
`913e56054be65074033ac761eb8681a122269f28569304ec062fff4166611e05`.

verification.json: 13,673 bytes, SHA-256
`5f47eb548db19a505f244f71693647257da379e13c408249211f45d09948085e`.

Independent admission, isolated runtime/resource and adversarial encoder qualification remain pending. This resolves one family's development contract, not the full benchmark review or the overhaul.
