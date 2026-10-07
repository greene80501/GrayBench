# Complete offline reference scan at 8399f3d

Both pinned offline suites were replayed once through the protected upstream
bridge. Each retained 143 tasks; eight external-service tasks per suite were
explicitly excluded and their identities remain in the evidence header.

| Suite | Pass | Unsupported | Infrastructure error | Total |
|---|---:|---:|---:|---:|
| Normal | 103 | 39 | 1 | 143 |
| Hard | 103 | 39 | 1 | 143 |

The complete append-only evidence chain verifies with no pending invocation.
File SHA-256: `6aa32f51356cca814af5d1d8bed9ac48d0f39d243bdce7fe2869bd8cbcc65dcd`.
The per-task results, unresolved reasons, source manifest, exclusions and transitions
are preserved in `GrayBench-v3-reference-summary-8399f3d.json`.

Compared with the prior complete 0a45d6a scan, 11 references per suite now pass:
45, 78, 91, 92, 100, 108, 109, 112, 119, 125, 145. No previously passing task regressed in this single replay.
The remaining infrastructure error is task 82's upstream cross-process file
assumption. The explicit task82 semantic file track remains separate; its result
was not substituted into this upstream scan.

This checkout's source text matches commit 8399f3d after CRLF normalization;
actual source bytes differ from Git LF blobs for the listed files. The log binds
and guards the actual executed source bytes before/after each invocation. This
is not falsely labeled an exact Git-blob-byte checkout. The runtime image is
sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd.

These counts describe evaluator/reference compatibility, not LLM accuracy,
adequate test coverage, statistical stability or publication admission. All tasks
still require the admission work in the reliability plan. In particular, passing
references coexist with demonstrated weak/contradictory oracles. Task 3 and task 26
now have additional exact-test counterexamples in the separate contract review.

No model generations were made. Read-only OpenAI and Gemini catalog requests also
succeeded in this work session; local Ollama was unavailable at observation time.
The authenticated catalog snapshots remain local outputs, not repository contents.
