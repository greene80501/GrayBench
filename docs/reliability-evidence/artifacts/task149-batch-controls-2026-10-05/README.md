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
The plan-only report says `controls_executed: false`. A result log must be
checked separately with the same verifier's result-log argument. These are
authored development controls, never model generations or a published score.
