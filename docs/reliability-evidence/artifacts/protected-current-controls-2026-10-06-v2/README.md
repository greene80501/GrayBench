# Source-bound protected controls for tasks 2, 20, and 62

The [append-only log](results.jsonl) freezes six protected judge manifests and 42 authored controls before evaluation under immutable Python 3.12/Qiskit image `sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`. All 42 outcomes matched: 18 passes and 24 failures. Engine source digest: `0daeaf62640237d5a4af2645c75f4f71a9645c78490781cd30ae79787833b924`.

The log is 3,012,570 bytes; SHA-256 `c0340de484f8430d94a74476f328ccff7ebf005b3ff4b5c9ab2ef936e2e622b7`; chain head `171d5a92ee4f8b89479441c28e05266a240be560554ff2b7e91a3a794a4186f7`. Verify from `engine/` with `uv run graybench oracle-review-inspect ../docs/reliability-evidence/artifacts/protected-current-controls-2026-10-06-v2/results.jsonl <pinned-cache>`.

The [admission successor](../admission-current-controls-2026-10-06-v2/manifest.json) binds these controls to six cards. It remains development-only: local controls are not independent task reviews or model scores.
