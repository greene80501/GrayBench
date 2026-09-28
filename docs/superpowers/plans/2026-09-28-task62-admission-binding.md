# Task-62 admission binding plan

**Goal:** Preserve a successor 302-card inventory and audit that bind the task-62 protected value controls without promoting them to certification.

**Source:** [Design](../specs/2026-09-28-task62-admission-binding.md).

1. Create a deterministic builder that reads the prior schema-3 inventory and its three exact logs, the protected task-62 log, and the pinned cache; reject source, judge, probe or outcome mismatch.
2. Bind only normal/hard task 62 to the revised public contract, exact protected judge and authored control case digests. Keep oracle fixture links, finding resolutions and independent reviews empty.
3. Write a successor bundle with four byte-pinned logs, inventory, schema-5 audit and manifest; verify it through `admission-bundle-verify` and check coverage counts.
4. Run focused checks, review the artifact and claims, commit and push to draft PR #3 while GitHub Actions remain disabled.
