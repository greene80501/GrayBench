# Native canonical repeat spot check, 2026-09-28

The pinned tests for task families 62, 63, 100 and 109 use NumPy randomness or seed it directly. At GrayBench revision `2e9854d4063291198e4aa5b6dc778418ec2258f4`, the native reference scanner replayed each pinned canonical answer three times in each suite under the Python 3.12 image `sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`. Normal used `exact_prompt_suffix_v1`; hard used `raw_or_single_python_fence_v1`. All 24 completed cases passed. These are four-task `custom_development` selections, not 143-task scores.

The [manifest](manifest.json) fixes all six append-only JSONL files by byte count and SHA-256. From `engine/`, with both SHA-256-pinned QHE parquet files already in `CACHE`, verify the copied bytes, event chains, source digest, selected task ancestry, cohort, reconstructed judge manifests, runtime and outcomes:

```sh
uv run --locked python ../docs/reliability-evidence/artifacts/native-stochastic-repeat-2026-09-28/verify.py CACHE
```

Three observed canonical passes per suite and family do not establish a low flake rate, oracle adequacy, or that wrong solutions fail. In particular, [task 63's fixed-string false pass](../../task63-oracle-review.md) remains unresolved: sharing the seeded NumPy state with the canonical implementation makes this repeat check pass while an input-ignoring answer also passes. Task 100 and 109 draw values without a fixed seed in their pinned tests, so the saved logs provide a bounded repeatability observation for their canonical answers. These local, unsigned observations do not admit any task or model score for publication.
