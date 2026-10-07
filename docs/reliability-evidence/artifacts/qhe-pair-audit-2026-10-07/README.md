# Pinned normal/hard pair audit, 2026-10-07

The [report](report.json) covers all 151 families and 302 pinned records. It
compares public requirement lines after removing only line-boundary whitespace,
verifies every hard function-name/argument declaration against the normal
prefix, and retains normal imports, annotations and defaults as differences in
available information. Those intentional normal/hard information differences
are not removed from generation requests.

There is one requirement-wording difference: task 41. Normal says “Compose XZ”
and also names `Pauli('YX')`; hard consistently says YX. Both judges require
composition on `qargs=[0, 2]`, although neither public description specifies
which two positions of the three-qubit operator to use. The original tasks and
tests are unchanged. A strengthened task needs a separately versioned public
contract resolving both ambiguities before generation.

Four fixed authored `Operator` values were passed to the exact pinned `check`
definitions on the host:

| Pauli | Positions | Normal | Hard |
|---|---|---|---|
| YX | [0, 2] | pass | pass |
| XZ | [0, 2] | fail | fail |
| YX | [0, 1] | fail | fail |
| YX | [1, 2] | fail | fail |

The XZ example is an interpretation of contradictory wording, not a claim that
it satisfies the entire normal description. The other placements demonstrate
the undisclosed position choice. IBM documents that `compose`'s `qargs` selects
the subsystems receiving the other operator, supporting why that choice changes
the result. [Qiskit 2.4 Operator documentation](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/qiskit.quantum_info.Operator#compose).

Both reference function bodies have identical ASTs in every family after the
normal docstring is removed. Raw `check` ASTs differ in tasks 9 and 122 because
imports move between function and module scope. A separately labeled diagnostic
removing imports finds no remaining AST difference. Import movement can change
behavior; this is not semantic-equivalence certification. Top-level imports and
the hard `check(entry_point)` call are not part of the function-body comparison.

The current finding registry now carries task 41 into both pending admission
cards. The frozen historical schema-2 registry is unchanged. Historical schema-3
inventories preserve their snapshots; current-use validation rejects an older
registry until refreshed. Refreshing findings does not resolve them, authenticate
a reviewer, or admit a task.

The audit executes no model-generated code and makes no API calls. The task-41
probe checks exact source-record digests before executing its pinned check
definition against fixed values. It is host-process diagnostic evidence, not
container qualification, native/protected parity, a model score or task admission.
All 151 rows retain `semantic_adequacy: unreviewed`; publication eligibility is
false. A full requirement-to-case review remains necessary.

The report is 377,911 bytes with SHA-256
`c393ab8c364ae7a460b03bdd0db5eb27b83572396c2f26c4ba15cca306721471`.
The [audit script](../../qhe_pair_audit.py) has SHA-256
`b2e06042e31e5f5c7c45f56964ad140f6fb9284d13006aefe287f26e7609dcb9`.
It records engine source
`29345c10352c95e33b1e0b7e3c5018fa304ab28b1cefe871658f7786414982e7`
and Python 3.12.14, Qiskit 2.4.2, NumPy 2.2.4. Both exact parquet file pins and
every public/full task, test and reference identity are retained. Private test
and reference bodies are not copied into the report.

From `engine/`, recreate and compare the saved report using:

```powershell
python ../docs/reliability-evidence/qhe_pair_audit.py <pinned-cache> ../docs/reliability-evidence/artifacts/qhe-pair-audit-2026-10-07/report.json --check
```

The [initial related regression run](admission-related.xml) had 34 passes, six skips,
zero failures in 8.93 seconds, with 12 Windows temporary-directory cleanup
warnings. It includes the full pinned pair audit and actual task-41 controls,
plus inventory/bundle regression tests. Its SHA-256 is
`5feb333f0de381ddf354fbc8a91ccb092f402c37f7c81da98953a02a488e61b6`.
Those skips required `GRAYBENCH_TEST_CACHE`; the new audit test now uses that
same shared variable. Enabling it exposed three stale expectations about which
gate rejects historical builders first. The [failing run](admission-related-pinned.xml)
had 37 passes and three failures: the new current-finding-registry gate correctly
ran before the older source/control checks. Its SHA-256 is
`e6ef1d89cee7da3f364d875bd46cf70c858aef5c4c2cdb7cf2831b2901667096`.
Tests now assert that exact earlier rejection. The tampered-control test restores
only the predecessor's frozen registry within the test to exercise its real
byte guard; it does not accept an unrelated early rejection as tamper evidence.
Production builders and historical artifacts are unchanged.

The [final cache-enabled run](admission-related-pinned-fixed.xml) passed all
40 tests, with zero failures/skips and 12 Windows cleanup warnings in 12.65
seconds. Its SHA-256 is
`99bf3aaf77ccc18802c016144f1a468d14a7041ca57f1b81bf4588a66d78a622`.
Lint and formatting passed for 234 engine/audit files. Code review reproduced
the pair audit and found no actionable issue; it is not human task admission.
These are focused checks; the prior 1,621-pass full-suite result belongs to the
earlier engine source, not this finding-registry revision.

A clean checkout of `64cd028` with separately installed locked dependencies on
the same Windows host reproduced all 40 focused tests in 12.47 seconds, with
zero failures/skips and the same 12 cleanup warnings. Exact report recreation,
lint and formatting passed; the clean checkout stayed unchanged. The
[clean JUnit record](clean-related.xml) has SHA-256
`4b69cbaf94c63599de177088dfb934d704d7c4bbf7c9fd8d86ce78cc592669fa`.
This is not a second-machine, full-suite or container reproduction.
