# Source-bound native literal-mutant screen

The [append-only log](results.jsonl) runs `return 0` and `return []` against every pinned offline native task in both normal and hard suites: 572 candidate judgments under engine source `0daeaf62640237d5a4af2645c75f4f71a9645c78490781cd30ae79787833b924` and immutable image `sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`. Its cohorts match the [current native canonical calibration](../native-reference-current-2026-10-06-v2/README.md); only the submitted answer changes. The exact probe source is frozen as [probe.py](../native-literal-mutants-2026-10-05/probe.py), SHA-256 `95df27bd75595a5fe14641bb9861e0b0396882e58c93a4d652a4f150160cfd2a`.

The verifier found 366 failures, 202 completed test-phase exceptions conservatively classified as `infrastructure_error`, and four passes. The passes are `return []` on native tasks 110 and 139 in both suites, reproducing their known vacuous-loop findings. No other literal survived this screen; that does not establish that other wrong answers fail. The 202 exceptions are not counted as failures.

Log SHA-256: `ec5266648c9af2d42fcb76898d87b773f8082e01cef9729be8b246e8ba52d6a0`. Chain head: `0ebf578f570faaa55cfc9a0fb5300403479e085838ffaff6e747b695b1ecbc64`. From `engine/`, run `uv run python ../docs/reliability-evidence/native_literal_mutant_screen.py verify <pinned-cache> ../docs/reliability-evidence/artifacts/native-literal-mutants-2026-10-06-v2/results.jsonl`.

The new [protected task-139 value revision](../task139-protected-controls-2026-10-06-v2/README.md) rejects an empty result separately. The native test remains pinned, and neither track's local controls constitute a model score or independent task admission.
