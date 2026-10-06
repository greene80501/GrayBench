# Predeclared task-149 protected controls

`plan.json` was frozen before the protected Docker run. It binds the exact
`qhe149-most-common-bitstring-v1` normal and hard source/revised tasks, public
requests, judge manifests, evaluator image, candidate-code hashes and expected
outcomes. The 14 controls predeclare four passes, eight wrong-answer failures
and two candidate errors. The plan SHA-256 is
`111e5362ed7e7b1dc4636d03c7e73c50fc3ae836a69d96bcc04e886969982f50`;
the byte-preserved probe SHA-256 is
`2af3ccb9d75373b8f34de2fbd089b505908a9e26c0e53fe5596453dd4f017784`.
The frozen engine source digest is
`344f5f501a33d10d245183289f234c5e8af083a5272b96f9ed140094f017b802`.

From `engine/`, run
`uv run --locked --extra dataset python ../docs/reliability-evidence/artifacts/task149-batch-controls-2026-10-05/verify.py`
to check the plan, probe bytes, source manifest and complete declared roster.
The plan-only report says `controls_executed: false`. The frozen plan was
committed and pushed before the Docker run. The [byte-preserved result log](results.jsonl)
is 270,211 bytes with SHA-256
`784f4f84725e6edf7b9cab0779e66e2c2e0245682506789dce0c709791931df0`.
Its event-chain head is
`d905f5367b853c9f088cc9fe92470ccb158048acb19135c394a2422cdd188afa`.
All 14 outcomes matched: four passes, eight wrong-answer failures and two
candidate errors. Run
`uv run --locked --extra dataset python ../docs/reliability-evidence/artifacts/task149-batch-controls-2026-10-05/verify.py ../docs/reliability-evidence/artifacts/task149-batch-controls-2026-10-05 ../docs/reliability-evidence/artifacts/task149-batch-controls-2026-10-05/results.jsonl`
from `engine/` to check the chain, complete roster, source, judge and candidate
bindings. The exact source checkout reported `source_matches_running_source:
true`. This verifies internal consistency, not independent attestation that
Docker performed the execution. These are authored development controls, never
model generations or a published score.
