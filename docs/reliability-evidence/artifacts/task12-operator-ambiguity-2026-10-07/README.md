# Task 12: a Bell preparation does not identify one unitary

Both pinned public variants ask for the unitary matrix of a phi-plus Bell
circuit. Neither specifies a gate sequence. Their exact `check` definitions
compare the entire returned operator with H on qubit 0 followed by CX(0,1),
up to global phase. The [report](report.json) retains the following fixed
authored circuits and the exact matrices supplied to those checks:

| Circuit | Prepares phi-plus from zero | Normal | Hard |
|---|---|---|---|
| H0, CX(0,1) | yes | pass | pass |
| H1, CX(1,0) | yes | fail | fail |
| Z1, H0, CX(0,1) | yes | fail | fail |
| H0, CX(0,1), global phase 0.37 | yes | pass | pass |
| Identity | no | fail | fail |

Independent literal H/Z tensors and a basis-index CX permutation reconstruct
every authored matrix. All five are unitary within maximum entry error
`2.220446049250313e-16`; the independently derived matrices agree with SDK
matrices exactly in this environment. The first column is the zero-input
prepared state. Four prepare phi-plus up to global phase; the identity control
does not. There are ten direct check calls, four passes and six failures.
Four failures are other valid phi-plus preparations, whose full operators
differ from the reference on other inputs.

This reproduces an unstated specification choice. It does not establish that
any matrix preparing a Bell state is the correct answer to an explicitly
defined full-operator task. The strengthened contract must either declare the
full preparation circuit/operator or explicitly permit the class of phi-plus
preparations. Changing the judge to compare only the first column would change
the task; that is not a silent fix. Original prompts, checks and scores remain
unchanged. The current finding registry carries the unresolved issue into both
task-12 admission cards while frozen historical registries remain unchanged.

The [diagnostic script](../../task12_operator_ambiguity.py) executes only exact
digest-guarded pinned check definitions against five authored values in the host
process. It records each gate sequence, phase, independent matrix, exact judged
matrix, calibration errors and outcomes. No arbitrary candidate, model answer,
API request or Docker process runs. This is not sandbox qualification, a
production-run verdict transcript, native/protected parity, human independent
review, task admission or a score. Publication eligibility is false.

The report is 15,474 bytes with SHA-256
`0d8e94f6e60a4886a4b80f65e23ae5c4d03af6bd4e9e95770d1bbfcc94247a37`.
Script SHA-256:
`5fdef171d5e1c32f43bad533634d45a926b14c67148379deecff3479a8a1598d`.
Engine source:
`9e48215af86585613eee6b2f3afb5c778f4437d649d3b208acfd56932335588d`.
Environment: Python 3.12.14, Qiskit 2.4.2, NumPy 2.2.4. Exact dataset pins,
source/public task digests and original test hashes are retained.

From `engine/`, reconstruct the saved report:

```powershell
python ../docs/reliability-evidence/task12_operator_ambiguity.py <pinned-cache> ../docs/reliability-evidence/artifacts/task12-operator-ambiguity-2026-10-07/report.json --check
```

The [related regression run](related.xml) passed 42 tests with zero failures or
skips in 12.82 seconds and 12 Windows cleanup warnings. It covers both
diagnostics plus inventory/historical-bundle handling. It does not replace the
older full-suite results with a current-source claim.
JUnit SHA-256:
`42b2f335830b6bf695e8aa92c72acf3580642023dc2ea6e45de99ac4f5c383fa`.
