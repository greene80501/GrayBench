# Task 62: fixed-input circuit accepted by the pinned native tests

Both pinned normal and hard tests seed NumPy to construct one five-qubit input and compare the returned state against a circuit hard-coded for that fixture. The [source-bound native control log](control.jsonl) records four passes under the Python 3.12 image `sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`: the canonical answer and a candidate that ignores both `state` and `basis`, in each suite. The probe source is [task62_fixed_oracle_probe.py](../../task62_fixed_oracle_probe.py), and [manifest.json](manifest.json) fixes the source and log bytes.

The fixed candidate always applies X to qubits 1, 2 and 3 and H to qubits 0 and 3. On the valid input `state=[0,0,0,0,0]`, `basis=[0,0,0,0,0]`, the canonical construction prepares `|00000⟩` with probability 1; the fixed circuit gives that state probability 0. It is therefore a wrong implementation that the pinned test accepts. This is one demonstrated false pass, not a measured model error rate or a claim about every possible mutant.

From `engine/`, check out source revision `54be7e1f4bb94d0adebcf1d675de34a70640668f` and supply both SHA-256-pinned QHE parquet files in `CACHE` before running:

```sh
uv run --locked python ../docs/reliability-evidence/artifacts/task62-fixed-oracle-2026-09-28/verify.py CACHE
```

The verifier checks the log chain, exact file and probe hashes, pinned task ancestry, reconstructed native judge manifests, completion and worker-result consistency, then runs the exact extracted canonical and probe completions locally on the all-zero counterexample. The records are local and unsigned; a same-process native candidate can inspect tests. This evidence blocks task 62 admission in both suites until its oracle is revised and independently reviewed. No model score is produced.
