# Current-source protected semantic value controls

The [byte-preserved log](results.jsonl) ran the source-declared authored
controls for revised normal and hard Qiskit HumanEval task families 2, 20, and
62 under the pinned Python 3.12/Qiskit image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`.
The protected track is `graybench-protected-semantic-v1`; tasks 20 and 62 use
their current v2 value conditions. The engine source digest is
`344f5f501a33d10d245183289f234c5e8af083a5272b96f9ed140094f017b802`.
The script froze its six judge manifests and source-declared probes before
evaluating the first candidate, then wrote an append-only result chain.

All 42 controls matched their declared outcomes: 18 passes and 24 failures.
The log is 3,012,480 bytes with SHA-256
`9851d0b9bd9ab2c172c36f36e100afb5efc428cca1dc524b8fad228e21c01f85`;
its chain head is
`ee771972a0ceed115f9878dd107d36e68c209667dc6becf50c66cb7d493ec47a`.
From `engine/`, verify the exact pinned dataset cache with:

```powershell
uv run --locked --extra dataset graybench oracle-review-inspect ../docs/reliability-evidence/artifacts/protected-current-controls-2026-10-05/results.jsonl <pinned-cache>
```

The verifier checks the full chain, task and candidate identities, declared
judge manifests, source digest and expected outcomes. Its `locally_verified`
result is internal consistency evidence, not independent Docker execution
attestation. These publicly authored controls do not independently review the
task contracts or qualify a model score; `publication_eligible` remains false.
