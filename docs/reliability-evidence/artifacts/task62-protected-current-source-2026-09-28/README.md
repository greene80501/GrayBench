# Task-62 protected controls after campaign-resume fix

This bundle preserves a fresh [source-bound control log](control.jsonl) for the separately named, development-only [BB84 value revision](../../protected-task62-bb84-value.md) at engine commit `d6d667db706f4b4da8e2bb96864f870abffa54ca`. It repeats the same sixteen predeclared authored controls under the pinned Python 3.12 Qiskit image after the campaign-resume source edit. Six valid alternatives passed and ten deliberately wrong candidates failed in the normal and hard suites, matching 16/16 declared expectations. The earlier [control bundle](../task62-protected-value-2026-09-28/README.md) remains unchanged as historical evidence.

From `engine/`, with the SHA-256-pinned QHE parquet files in `CACHE`, verify the captured bytes and current source:

```sh
uv run --locked python ../docs/reliability-evidence/artifacts/task62-protected-current-source-2026-09-28/verify.py CACHE
```

The verifier checks the byte-pinned log, full evidence chain, pinned task ancestry, source manifest, reconstructed contracts and judge manifests, exact authored completions and expected outcomes. It must be run at the captured source revision; later source changes do not erase this historical result. This is local authored control evidence, not independent certification, native-circuit equivalence, or a model score. `publication_eligible` is false. The admission inventory has not yet been advanced to this source revision.
