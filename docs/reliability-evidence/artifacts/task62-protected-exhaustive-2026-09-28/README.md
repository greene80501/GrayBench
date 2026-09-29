# Task-62 exhaustive protected-value controls, 2026-09-28

This bundle captures the separately named `task62-bb84-sender-amplitudes-all-inputs-v2`
condition on pinned normal and hard QHE task 62. Each protected judge sends all
1,364 declared binary state/basis pairs to an isolated candidate process and
checks returned amplitudes in the trusted host. The candidate does not receive
expected outputs. The old 124-case v1 condition and its saved controls remain
historical evidence, with distinct oracle and judge identities.

The [log](control.jsonl) is 2,681,337 bytes with SHA-256
`2e29910a57d907e0b6e4e7ceda3067ea04587e01a8858be3368698fbffa15ce0`.
Its header predeclares all 18 controls and both exact judge manifests. Six
correct alternatives passed and twelve wrong variants failed, including the
input-specific mutant that passes v1 but fails on a valid width-4 input in v2.
The exact source digest is
`669b151ec3560455d6ffee16adf9706d2cf4b898cc86fe94517e1561317b8289`;
the image is
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`.

From `engine/`, at the captured source revision and with the pinned parquet
cache available, verify the saved bytes and reconstructed controls:

```sh
uv run --locked python ../docs/reliability-evidence/artifacts/task62-protected-exhaustive-2026-09-28/verify.py CACHE
```

The [manifest](manifest.json) pins the log by byte count and hash. Verification
checks the hash chain, pinned task ancestry, source manifest, all judge
manifests, authored completions and outcomes. This is locally authored control
evidence, not independent certification, a native-circuit claim, or a model
score. The value condition remains development-only and `publication_eligible`
is false. The predecessor admission inventory does not yet contain this log.
