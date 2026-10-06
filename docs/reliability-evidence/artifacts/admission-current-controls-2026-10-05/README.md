# Current-source admission successor

This bundle is a development-only successor of the [2026-09-28 admission
bundle](../admission-current-controls-2026-09-28/README.md). The
[builder](../../refresh_admission_2026_10_05.py), SHA-256
`776221372a5c467204e542d7be7fb160c4be2735f2e019666ad5e2a8ee83cc26`,
preserves its two historical native-oracle logs, replaces its two stale
protected-value logs with the [42-control current-source
log](../protected-current-controls-2026-10-05/README.md), and rebinds only
the six protected semantic task cards for normal and hard families 2, 20 and
62. It carries all 302 cards and the frozen finding registry forward.

The [manifest](manifest.json) has SHA-256
`87b5f1d4e8171c9ddd3005a1836c78a22d20f4123a79e2bbb25c473ac9db74d0`;
the recomputed [audit](audit.json) has SHA-256
`dbadac20405572d0edb56713ed03c001d2a1a13c6cbe56b7252ca3ba42408e7d`.
The bundle verifier found 60 local authored controls across 10 task cards,
including 42 protected controls bound to the current inventory source and
zero protected controls bound to a different source. The other 292 cards have
no local controls in this bundle. The audit retains eight observed false
passes in historical native-oracle controls and zero false rejections.

From `engine/`, verify with the pinned cache:

```powershell
uv run --locked --extra dataset graybench admission-bundle-verify ../docs/reliability-evidence/artifacts/admission-current-controls-2026-10-05 <pinned-cache>
```

To rebuild into a new destination, run
`uv run --locked --extra dataset python ../docs/reliability-evidence/refresh_admission_2026_10_05.py <pinned-cache> <new-output-directory>`.
The builder refuses to overwrite an existing bundle. Its verification checks
the predecessor and current log bytes, declared controls, source, judge and
requirement links before writing the successor.

This is source-bound local evidence, not independent expert review or a model
score. The inventory still has zero reviewer attestations and zero cards without
structural blockers; `publication_eligible` remains false.

The bundle verifier passed from a separate checkout at `c3bc35a`, with the
same manifest SHA-256, 60 controls, 42 source-bound protected controls and
zero different-source protected controls.

The current inventory's structural blocker counts overlap: 296 cards lack a
public value contract, protected judge and requirement map; the six controlled
cards lack verified oracle-case links; 94 cards have unresolved known findings;
all 302 lack two qualified independent reviews; and 16 external-service cards
remain unqualified. A control pass alone clears none of those review gates.

The complete Windows/Python 3.12 engine suite with the verified pinned cache
and image, including both successor-builder tests, reported 1,571 passed,
5 skipped, 6 expected failures and zero failures in 720.59 seconds. Ruff lint
and format checks passed.
