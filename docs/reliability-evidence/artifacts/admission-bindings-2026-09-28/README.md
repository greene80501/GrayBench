# Task-2/20 admission bindings, 2026-09-28

This is a successor to the [pending inventory bundle](../admission-2026-09-28/README.md). It preserves the three control-log files byte for byte and adds a new 302-card inventory and recomputed schema-5 audit. The four normal/hard task-2 and task-20 cards now bind the public value contract and exact protected judge that produced their predeclared controls. Their requirements cite authored positive alternatives and wrong-answer mutants. The remaining 298 cards have no new bindings.

The four protected judge digests were reproduced from the pinned source tasks, current task constructors and judge code, and Python 3.12 image `sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`. They match the manifests in the saved controls. Task 2 uses one Bell-state case per suite; task 20 uses all 210 ordered three-wire layouts per suite. The requirement clauses are excerpts from the revised public prompts, not the original native-object QHE prompts. The alternatives use mathematical, Qiskit-derived, and global-phase constructions; this is implementation diversity from one author, **not** independent reviewer evidence.

From `engine/`, with the locked environment and both SHA-256-pinned QHE parquet files already in `CACHE`, run:

```sh
uv run graybench admission-bundle-verify ../docs/reliability-evidence/artifacts/admission-bindings-2026-09-28 CACHE
```

[`manifest.json`](manifest.json) fixes each evidence file's length and SHA-256. The verifier checks exact bytes, pinned task ancestry and all control chains, then recomputes the entire audit byte for byte. It reports 42 controls on eight cards, 24 controls matching the four bound protected judges, eight upstream false passes and 294 cards without controls. The new audit SHA-256 is `618d923a7651d87e9f129bec72a41dae70ca940486676283257d82439f4c2c00`; the inventory model digest is `fe353e883c32319c6816ff084ff69982ccd53646fec83e72dd83e727dac5f57b`.

No protected fixture digest is claimed by these requirement links: candidate-control logs do not expose individual oracle fixtures. The four cards still lack fixture review, resolutions for their known upstream findings and two qualified independent reviews. Other cards remain pending, the logs are unsigned local observations, and `publication_eligible` remains `false`. This bundle establishes consistent card-to-judge and card-to-control references, not task admission or a model score.
