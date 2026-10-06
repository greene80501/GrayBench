# Current-source native reference calibration

These append-only logs rerun the pinned canonical answers through the current native Qiskit HumanEval judge and immutable image `sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`. The engine source digest is `344f5f501a33d10d245183289f234c5e8af083a5272b96f9ed140094f017b802`. Each suite is the exact 143-task offline cohort; the eight external-service tasks are excluded.

| Suite | Answer condition | Canonical passes | Log SHA-256 | Chain head |
| --- | --- | ---: | --- | --- |
| [Normal](normal.jsonl) | Exact prompt suffix | 143/143 | `88812cb3f554c821ad770a72a7ad0b3dcd6d71aafd21dea0073905c01559001d` | `761635b68af693d5191b8b7ce151a93dcb126441777289a53a7b68859d52d7db` |
| [Hard](hard.jsonl) | Raw or single Python fence | 143/143 | `208501332383c88c542e2554394bfde3802b26fb6c9df350c9a51677e4ac001a` | `9544a9a14ba27f59f66b19d4a77a66debbc9d047749677d97ecc3bad42e77283` |

The [verifier](../../verify_native_reference_current.py) checks each event chain, task and exclusion set against the pinned cache; recreates the exact cohort and judge manifest; checks the canonical completion and extracted-code hashes; and checks that every reported pass agrees with the worker result and captured result-file hash. The tamper tests rehash a changed completion or outcome and require the verifier to reject it. From `engine/`, run:

```powershell
uv run --locked --extra dataset python ../docs/reliability-evidence/verify_native_reference_current.py ../docs/reliability-evidence/artifacts/native-reference-current-2026-10-05 <pinned-cache>
```

This is source-bound local interface calibration, not independent execution attestation or model scoring. A canonical answer passing a test does not establish that the test rejects wrong answers or treats every valid answer fairly. The known native oracle defects, same-process inspection risk, and task-admission blockers remain; publication is disabled.
