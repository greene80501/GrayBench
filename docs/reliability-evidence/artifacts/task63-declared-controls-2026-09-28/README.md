# Task-63 explicit-bases graph controls, 2026-09-28

This is a successor to the historical [task-63 development recipe](../../task63-explicit-bases-revision.md), not a replacement for its raw log. The probe selected the exact pinned normal and hard task-63 records from an explicit cache path, froze each revised task and complete judge manifest in the log header, then ran seven authored candidates per suite in the pinned Python 3.12/Qiskit image. Each result is checked against the predeclared manifest before the next candidate runs. The completed log contains four passes from two correct implementation styles, eight semantic failures from four wrong styles, and two deliberate candidate errors. No model API was called.

The read-only verifier checked all 14 case identities and expectations, the hash chain, original and revised task digests, completion digests, per-result judge manifests, graph protocol, image, and source identity. It reports `judge_predeclared: true`, `source_matches_running_source: true`, `probe_matches_running_probe: true`, and `publication_eligible: false` on the recorded source. The raw `controls.jsonl` is 2,180,963 bytes, SHA-256 `dd0ecd7aadb3fa9cd060ed0758d2d0f01e7139918f9c35dfc0de3ea3c265b483`, with chain head `e738fa7653cca750f30ea0864159c41fe1902d3f4afef70b26da27f2c46fb93f`. [manifest.json](manifest.json) pins the image, engine source, probe and verifier file hashes.

From `engine/`, replay the check with:

```powershell
uv run --locked --extra dataset python ../docs/reliability-evidence/verify_task63_explicit_bases.py ../docs/reliability-evidence/artifacts/task63-declared-controls-2026-09-28/controls.jsonl
```

The verifier can also check the older log after the engine changes; it reports source/probe mismatches rather than mistaking historical bytes for current code. Neither a self-consistent log nor its hashes authenticate the author or make the nine private cases exhaustive. This graph recipe is separate from the value-based admission inventory and retains the known graph-transport and task-domain limitations. Both normal and hard task-63 cards remain pending independent review and release-ineligible.
