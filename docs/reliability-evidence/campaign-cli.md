# Development campaign commands

`campaign-create SETUP CACHE LEDGER` validates a CampaignSetup JSON document and the pinned
cached task records, checks engine source identity, and commits protocol plus execution context
in one ledger transaction. It performs no provider generations. Missing cached datasets are not
silently downloaded. The setup currently requires a previously constructed frozen Protocol.

`campaign-step LEDGER RUN_ID CACHE --docker PATH` loads that persisted setup, verifies the
ledger chain, compares its protocol to the run, checks host provenance, revalidates the task
cohort, and performs at most one generation or protected judgment. Deferred states return a
not-before timestamp instead of sleeping. The setup file is not read again during resume.

The append-only run_contexts table stores setup, full relevant environment observations and
the host compatibility fields. Python, OS, installed package versions, architecture and source
must match; volatile observation timestamps and GPU status do not define compatibility.
Execution and HTTP limits are frozen with the setup. Timeout values are normalized to floats
before hashing judge manifests, so numerically equivalent JSON integers do not create drift.

CLI tests create a run without any HTTP calls, remove the original setup file, then resume a
mock metadata observation followed by generation from stored context. A changed package
environment blocks both discovery and dispatch. Existing
Docker integration verifies the underlying generation/judgment pipeline separately.

These are development commands: task adequacy admission and model drift/capability evidence
are still incomplete. A user-friendly setup builder, workflow documentation, broader provider
metadata coverage and verified reporting remain required. No scores are certified by creating
a context.
