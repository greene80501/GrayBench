# Local admission evidence bundle, 2026-09-28

This directory contains the exact bytes behind the [admission-control audit](../../admission-control-audit.md): the pending 302-card inventory, two historical task-0/1 control logs, the predeclared protected task-2/20 control log, and the schema-5 combined audit. [`manifest.json`](manifest.json) lists each file's SHA-256 and byte count. The files contain authored test completions and local judge observations, not model responses or credentials.

From `engine/`, install the locked Python 3.12 environment and download the two pinned Qiskit HumanEval parquet files into a local cache if needed:

```sh
uv sync --locked --extra dataset --extra qiskit
uv run graybench inventory CACHE --download
uv run graybench admission-bundle-verify ../docs/reliability-evidence/artifacts/admission-2026-09-28 CACHE
```

Replace `CACHE` with the same cache directory in both commands. The importer checks the exact pinned parquet SHA-256 values. The verifier checks the listed file sizes and hashes, re-inspects every control log and source-task ancestry, recomputes the complete audit against pinned tasks, and requires byte-for-byte equality with the saved audit. It reports 42 controls across 8 cards, 294 uncovered cards, eight upstream false passes, and zero controls credited to a card-bound protected judge. The last zero reflects pending task-card bindings, not failure of the 24 new protected controls.

These logs are reviewable at this Git commit. Their internal hash chains and the manifest do not authenticate their authors, prove that the recorded judge actually ran, establish independent oracle review, or certify any task or model score. The older upstream and strengthened logs were produced at earlier engine source versions; each log records its own source-manifest digest. The protected log was produced with the source at commit `5ca716c520df23a844054e71288450fcc011d02d`. Re-running controls creates new timestamped evidence rather than reproducing byte-identical JSONL.
