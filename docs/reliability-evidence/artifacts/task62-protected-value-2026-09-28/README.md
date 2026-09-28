# Protected task-62 BB84 value controls, 2026-09-28

This bundle preserves the [source-bound control log](control.jsonl) for the separately named, development-only [task-62 value revision](../../protected-task62-bb84-value.md). The normal and hard source tasks are pinned by SHA-256, as are the Python 3.12 Qiskit runtime image, current engine source, judge manifests, private calls and exact log bytes in [manifest.json](manifest.json). The eight predeclared authored controls in each suite produced 16/16 expected outcomes: six valid alternatives passed and ten wrong implementations failed. No model was tested or scored here.

From `engine/`, supply both SHA-256-pinned QHE parquet files in `CACHE` and run against the captured engine source:

```sh
uv run --locked python ../docs/reliability-evidence/artifacts/task62-protected-value-2026-09-28/verify.py CACHE
```

The [verifier](verify.py) checks exact log bytes, the complete evidence chain, pinned task ancestry, the current source digest, reconstructed public contracts and predeclared judge manifests, exact authored completions and expectations, and every observed outcome. It must be run against the captured source revision; later engine changes can invalidate the current-source comparison without invalidating this historical record.

The log is local and unsigned. Authored controls and source-bound hashes do not provide independent review, full-domain proof, or native `QuantumCircuit` equivalence. The admission card still requires fixture authenticity, independent oracle review and the remaining release gates. `publication_eligible` is `false`.
