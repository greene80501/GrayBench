# Source-bound native canonical calibration

The normal and hard logs rerun all 143 offline pinned canonical answers in each suite with Python 3.12 and immutable image `sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`. Engine source digest: `0daeaf62640237d5a4af2645c75f4f71a9645c78490781cd30ae79787833b924`. The eight external-service tasks remain excluded.

| Suite | Extraction | Canonical passes | SHA-256 | Chain head |
| --- | --- | ---: | --- | --- |
| [Normal](normal.jsonl) | Exact prompt suffix | 143/143 | `ee45a513dd3f08b303b070df50e146679f539b1de67701b68bde8fc5ca90b824` | `9d0367b93504ae06c956558a0c37ffc0f008969528bf1513f52c9b7a05c820d6` |
| [Hard](hard.jsonl) | Raw or single Python fence | 143/143 | `1057d1d903185ea2d796bd6c7b24532abf243232a38f013d03d5b68bec1218e9` | `d0bce1c38d8ecc96731c573d244c4a607d253553911c205929a2d337f95f4702` |

From `engine/`, run `uv run python ../docs/reliability-evidence/verify_native_reference_current.py ../docs/reliability-evidence/artifacts/native-reference-current-2026-10-06-v2 <pinned-cache>` to reconstruct task, cohort, judge, completion, result, and chain bindings. These passing references calibrate the interface only; they do not establish oracle adequacy, independent execution, or a model score.
