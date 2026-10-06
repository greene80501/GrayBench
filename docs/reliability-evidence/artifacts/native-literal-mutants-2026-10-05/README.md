# Current-source native literal-mutant screen

The [append-only result chain](results.jsonl) ran two trivial candidates against every task in the pinned 143-task offline normal and hard cohorts. `zero` returned numeric `0`; `empty_list` returned `[]`. Normal used a literal function suffix, and hard used a complete variadic function. The candidates ignored all inputs. The exact [probe source that executed](probe.py) has SHA-256 `95df27bd75595a5fe14641bb9861e0b0396882e58c93a4d652a4f150160cfd2a`.

Both cohorts match the [current native canonical calibration](../native-reference-current-2026-10-05/README.md): engine source `344f5f501a33d10d245183289f234c5e8af083a5272b96f9ed140094f017b802`, image `sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`, the same frozen task sets, answer extraction, conservative exception policy, and judge manifests. Only the candidate answer differs.

| Suite | Mutant | Fail | Completed test-phase exception | Pass |
| --- | --- | ---: | ---: | ---: |
| Normal | `0` | 82 | 61 | 0 |
| Normal | `[]` | 101 | 40 | 2 |
| Hard | `0` | 82 | 61 | 0 |
| Hard | `[]` | 101 | 40 | 2 |

All four passes are `empty_list` on tasks 110 and 139, once in each suite. These reproduce the existing [task-110](../../task50-110-oracle-review.md) and [task-139](../../task139-schmidt-oracle-review.md) findings. Task 110 asks for `n` Clifford circuits but its test only iterates over returned items; task 139 asks for Schmidt decomposition data but likewise only iterates. An empty list executes neither assertion. No new finding was added to the registry from this screen.

The 202 `infrastructure_error` outcomes are **completed test-phase exceptions** under the conservative native condition, not Docker launch failures. They remain unscored pending exception-attribution policy and task review. The 366 `fail` outcomes show rejection of these particular literals, not general oracle adequacy.

The [current verifier](../../native_literal_mutant_screen.py) checks the event chain, pinned task and cohort identities, each answer and judge hash, and each captured worker-result file. The first replay attempt used GrayBench's unescaped UTF-8 canonical JSON to reconstruct that file; the worker actually uses `json.dumps` with escaped Unicode. The corrected verifier uses the worker's exact serialization and requires the archived probe's byte hash to match the predeclared header. Its tamper test rewrites an outcome and recomputes the chain; verification rejects it. From `engine/`, run:

```powershell
uv run --locked --extra dataset python ../docs/reliability-evidence/native_literal_mutant_screen.py verify <pinned-cache> ../docs/reliability-evidence/artifacts/native-literal-mutants-2026-10-05/results.jsonl
```

The result chain's SHA-256 is `17662b890d98700f77eb63428a53239083af4de0765d1e5d01534ec3406b8874`; its chain head is `8f4e38460c1acbade62d392e9f9d306bc3342d90fee70b2690b47024d187f3e9`. This is local authored control evidence, not independent execution attestation, a model score, or task admission. Publication remains disabled.
