# Authored matrix-alternative calibration

The [report](report.json) records the trusted [calibration script](../../matrix_alternative_calibration.py) on engine source `4770bfec384cfe4f52a1fcd4cb832bed65f012a9234462f4dd25f531ab8cf90d`. The [control fixture source](../../matrix_semantics_controls.py) SHA-256 is `d65b7f9fbe1b0f62a21afd12f39670f9026a25ea2c8f231113765f68b6ef571b`; its bytes are retained under an explicit LF Git attribute.

Basis-change/parity-rotation evolution matched expected matrices for all 340 unsigned Pauli labels on widths 1–4, at times `0`, `-0.23` and `0.71`: 1,020 cases, maximum entry error `6.661338147750939e-16`. SDK Pauli-to-matrix conversion is used in this calibration; the production oracle independently uses literal tensor matrices. Walsh-phase synthesis matched 80 random diagonal matrices from seed 251 on widths 1–5, maximum entry error `1.6504651808933464e-15`. Both checks retain global phase and use an absolute entry threshold of `5e-12` without phase alignment.

From `engine/`, reproduce into a new output file with:

```sh
uv run --extra qiskit python ../docs/reliability-evidence/matrix_alternative_calibration.py --output NEW_CALIBRATION.json
```

This executes only trusted authored fixture algorithms. It does not run model code, contact a provider, exercise the graph boundary or start Docker. It calibrates finite inputs and does not prove continuous-domain correctness or independently admit the benchmark tasks. The separate canonical evolution storage qualification remains pending.
