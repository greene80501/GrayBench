# Task 117: explicit nesting resource condition

The Task 117 v1 public contract permits sixteen circuit levels, but its default graph structural-depth bound of 32 rejected some valid supplied definitions. The [previous source-bound probe](task117-unitary-basis-development.md) recorded all sixteen authored semantic checks passing while first-response encoding accepted only zero through six nested definitions. That is a transport limitation, not evidence of an incorrect answer.

The separately selected `qhe117-unitary-basis-graph-v2` keeps the exact v1 revised task, public prompt, private checker, tolerances, input corpus and method/provenance limitations. It changes the frozen graph structural-depth allowance to 128. Its default expanded-state, wire and accumulated-output bound is still 16 MiB; array and matrix storage remain 512 KiB each, and node/edge bounds remain 100,000. The manifest and campaign judge digest distinguish v1 and v2 even though prepared task requests are identical. Scores from these resource conditions must not be mixed.

The SDK-independent validator now permits an explicit depth up to 128 while keeping the default at 32. Booleans, fractional values, nonpositive values and depths above 128 remain invalid. V1 cannot select a depth above its historical ceiling. V2 fixes depth at 128 and the other structural/storage fields as described above; message, expanded-state, wire and output allowances are bound to the explicitly selected plan budget, with 16 MiB as the default. A different byte budget has a different judge and protocol identity: execution against the default plan and comparison with that plan both reject the mismatch. A receiver with depth 32 still rejects a sender's deeper graph. The wider bound does not disable graph shape, allocation, ownership, cycle, immutable-construction or transport checks, and it does not synthesize or flatten candidate definitions.

All 16 permitted definition depths, from zero wrappers through fifteen, are checked across both public formats. Each implementation wraps a correctly decomposed two-qubit circuit in supplied generic Gate definitions with nonzero global phase. Every depth traverses all 15 unitary inputs through request and response delta arenas, with first-call nodes retained through the final call and accumulated traffic checked against the frozen output allowance. This is 480 authored call pairs. It is local codec/runtime reconstruction evidence, not isolated execution, a complete circuit-domain proof or native provenance attestation.

The host-to-worker staging tests check the advertised record passed by `UpstreamJudge` and the actual configuration written by `Candidate`. A fresh trusted process loads the staged `graybench.graph_limits` module and reconstructs that record; its module path must resolve inside the staged package. No candidate program is executed in this staging check. The candidate and trusted judge processes use the same staged resource validator. Docker integration and runtime resource calibration remain pending.

The existing [authored control runner](task117_protected_graph.py) preserves its v1 default and its original 48 predeclared trials. Selecting v2 adds all sixteen valid nesting implementations per suite, giving 80 predeclared trials: 50 accepted and 30 rejected. The revised task does not give candidates the authored implementations, private cases or an extra repair turn.

From `engine/`, freeze the new condition with:

```sh
uv run graybench campaign-plan model.json CACHE task117-v2-setup.json --name task117-v2-development --image sha256:IMAGE_DIGEST --evaluation-recipe qhe117-unitary-basis-graph-v2 --task normal/qiskitHumanEval/117 --task hard/qiskitHumanEval/117
```

Once Docker is healthy, use a new append-only control log:

```sh
uv run python ../docs/reliability-evidence/task117_protected_graph.py --cache CACHE --image sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd --evaluation-recipe qhe117-unitary-basis-graph-v2 --output NEW_RESULTS.jsonl
```

Judge manifests are predeclared before execution. An interrupted log must be adjudicated rather than replayed under the same output name. Neither condition is admitted for publication. Original source tasks, previous evidence and v1 resource defaults remain unchanged; current source-bound verification must not be attributed to an earlier engine digest.

Bounded implementation review compared the task/checker definitions against the previous commit and found them unchanged. It reproduced resource-budget identity separation, default-plan execution refusal, comparison refusal and both control-roster counts. Its focused run passed 32 tests with the 32 complete-corpus cases deselected to avoid repeating the earlier 187-second run. No blocking issue was reproduced in that reviewed scope. This is implementation review, not independent admission, isolated execution or a complete unitary/circuit-domain proof.

October 7 verification used locked Python 3.12.14/Qiskit 2.4.2 dependencies, the pinned source cache and no Docker test-image setting. The full main-checkout suite completed with **1,524 passed, 286 skipped, zero failures** in 400.28 seconds, with 12 Windows temporary-directory cleanup warnings. Its engine source digest is `c473a44e184707353b3c80ad73c0aed95a4c81f7e0da76e9f8b3b1028de9712a`. Ruff lint and formatting passed for 223 files. The complete-corpus cases, byte-budget incompatibility guards and actual v2 CLI reservation are included in that run; the isolated v2 controls remain skipped.
