# Source-bound admission successor

This development-only bundle rebinds the six protected value cards for tasks 2, 20, and 62 to the [current 42-control log](../protected-current-controls-2026-10-06-v2/README.md) and engine source `0daeaf62640237d5a4af2645c75f4f71a9645c78490781cd30ae79787833b924`. It preserves historical observations and the existing task-139 native false-pass finding. The 22 new task-139 protected controls are [separate](../task139-protected-controls-2026-10-06-v2/README.md); no new task-admission claim is made for them.

`refresh_admission_2026_10_06.py` rebuilt and verified this bundle. The audit reports 60 controls across 10 task cards, 292 uncovered cards, 42 controls bound to current protected judges, eight recorded false passes, zero false rejections, and no independent review. `publication_eligible` remains false. The manifest SHA-256 is `5964ad0a8ac441caa59c153c6f45cb5ec28714db3acf93c21d2a70ee2c2b04af` and audit SHA-256 is `fe8cdb26c4d95ba7167008279e1d684d220f36e296ccb1a517a61a5147d0b189`.

The [exact private-call roster](../oracle-case-roster-2026-10-06-v2.json) contains 3,150 calls for these six cards and leaves requirement-to-case links empty for independent review. Local verification confirms internal consistency, not oracle adequacy or a model score.
