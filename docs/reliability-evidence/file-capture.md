# Candidate file capture boundary

This records the capture-only milestone at 563cae5. Subsequent task-82 parsing and
oracle work is documented separately in the [semantic track](task82-semantic-track.md).

Task 82 explicitly asks for `bell.qpy`; the pinned check calls the candidate, then
loads that file. Separate candidate and judge filesystems currently make the
upstream check fail with a missing file even for the canonical answer.

`Candidate.capture_artifact` captures an explicitly named regular file from the
paused candidate workdir through the host's Docker connection. It returns opaque
bytes and a content digest. It does not run candidate-side capture code, trust a
candidate file manifest, extract an archive to disk, or deserialize QPY.

Docker's archive API could not read the previous container-local `/tmp` tmpfs in
the real integration test. Candidate workspaces now use unique Docker local-driver
tmpfs volumes with a 256 MiB capacity, mode 1777, nosuid and nodev. They are removed
after container removal. The workspace policy is recorded in the upstream judge
manifest. Process memory remains separately limited to 4 GiB; this workspace
change needs resource calibration before score publication. Judge mounts remain
disjoint and do not receive this volume.

Capture permits one simple relative filename, at most 4 MiB, with a bounded tar
envelope. It rejects links, directories, special files, multiple members and path
traversal. A host inspection requires a running paused container; missing
containers remain infrastructure failures. No candidate process resumes for
capture. Nested paths, input fixtures, file mutation across a judge/candidate
boundary and general filesystem semantics remain unfinished.

The exclusive append-only `GrayBench-v3-task82-file-capture.jsonl` record preserves
the actual bytes of both canonical task-82 outputs, their digests and source
identity. Its file SHA-256 is
`d064a7a062a085c6bd81a88508a0872cce8ca7f63c638e39129e431c625a1358`.
Both outcomes are deliberately **unsupported**: capture succeeded, but isolated
QPY parsing and protected oracle integration are not implemented yet.

Qiskit's [security advisories](https://github.com/Qiskit/qiskit/security/advisories)
document deserialization vulnerabilities. Raw QPY parsing belongs in another
restricted process without trusted tests or a verdict channel. Parser output must
cross a validated typed boundary before the oracle uses it. This is a required
next step, not an assertion that QPY is presently safe to load in the judge.

The adversarial flood test exposed a shutdown deadlock when bounded readers stopped
draining attached pipes. Readers now retain only bounded output but drain excess
bytes through shutdown. An intermediate verification also overlapped a manual
unused-volume cleanup; the final verification excludes concurrent cleanup.
Already-absent volumes are treated as successful cleanup, while other removal
errors remain visible. Earlier failed test reports are retained separately.

Final validation:236 tests pass with Docker enabled, zero failures/errors/skips.
Ruff lint and formatting pass. No billable generations were used.
