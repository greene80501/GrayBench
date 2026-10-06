# Protected value case roster (development evidence)

The [machine-readable roster](artifacts/oracle-case-roster-2026-10-05.json) records the exact calls currently made by the six revised protected value tasks. The [builder and verifier](build_oracle_case_roster_2026_10_05.py) recreate every record from the pinned Qiskit HumanEval cache, the current admission inventory, the task constructors, and the judge manifest. Each case includes its call arguments and canonical SHA-256 identity. The packet also carries the public requirement clauses so a reviewer can examine the two sides together.

| Task, in each suite | Calls | Domain |
| --- | ---: | --- |
| 2 | 1 | Phi+ value with no input arguments |
| 20 | 210 | Every ordered selection of three distinct wires from seven |
| 62 | 1,364 | Every binary state/basis pair of widths 1 through 5 |

Normal and hard each have the same call roster; both retain their separate source-task and judge bindings. The packet has 3,150 task-specific call records and 1,575 distinct call identities across the two suites. Its SHA-256 is `0bd3282555536ae6762518954d7b417ad25c368ceb17c87581d7116101bd04b8`. The saved JSON is compact; use `python -m json.tool` to inspect it with indentation.

This is **an inventory of calls, not a coverage finding**. `requirement_case_links` is intentionally empty. A call digest does not establish that the oracle tests a requirement: for example, the one Phi+ call says nothing by itself about global-phase handling. Reviewers must inspect the value oracle, evaluate valid alternatives and wrong mutants against each clause, adjudicate the known false-pass findings, and provide independent reviews before admission. The current cards still have unresolved blockers and publication is disabled.

With `GRAYBENCH_TEST_CACHE` set to the pinned cache, verify the saved packet with:

```powershell
uv run --project engine python docs/reliability-evidence/build_oracle_case_roster_2026_10_05.py $env:GRAYBENCH_TEST_CACHE docs/reliability-evidence/artifacts/oracle-case-roster-2026-10-05.json --check
```
