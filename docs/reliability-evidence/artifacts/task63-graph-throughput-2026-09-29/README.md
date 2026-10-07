# Task-63 graph-call feasibility, 2026-09-29

The [task-63 explicit-bases development recipe](../../task63-explicit-bases-revision.md) has nine private cases. Before extending it, this probe exercised the existing protected graph bridge with a wider, deterministic domain. It called the unchanged simulator reference and independent statevector implementation once for every ideal sender-bit, sender-basis and receiver-basis combination at each selected width. Expected sifted keys were computed in the trusted test from the authored bits and matching bases. The model-facing prompt and historical recipe were not changed, and no model API was called.

Both source-bound logs use the pinned Python 3.12/Qiskit image `sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd` and graph delta transport. They test **normal task 63 only**:

| Frozen condition | Calls per implementation | Simulator reference | Statevector alternative |
|---|---:|---|---|
| Widths 1–2, 1 MiB cumulative wire, 120-second judge and candidate limits | 72 | pass; 10.105 s candidate active, 19.859 s wall | pass; 9.997 s active, 19.625 s wall |
| Widths 1–3, 16 MiB cumulative wire, 300-second judge limit and 120-second candidate-active limit | 584 planned | timeout after 256 graph exchanges; 120.210 s active, 232.969 s wall | timeout after 256 exchanges; 120.268 s active, 232.453 s wall |

The 584-call outcomes are **resource timeouts, not incorrect BB84 answers**. Raising the wire allowance did not make the full matrix fit the active-time limit. Repeated graph calls are the likely scaling cost, but these measurements do not isolate every component of that cost. They do not justify changing a release resource limit or excluding correct approaches. A future version needs an explicitly reviewed bounded case set or an efficiently batched protected call with equivalent input and result semantics, followed by independent controls and resource calibration. The existing nine-case recipe remains unchanged and release-ineligible.

[`manifest.json`](manifest.json) pins the exact probe and two logs. The 72-call log has SHA-256 `7954ff112e151f950f80f8aa99e8600ee3864fa0d076dbdaaf22432e9278d4e9` and chain head `5cdc9fdb71fab6640ecfcd5e1dbfe9f23f772e5193a657a5133597c7bcec8cb4`. The 584-call log has SHA-256 `c75b8df944cd42406dd2f7f83986a25d9613b13b9f9fe47c521f43fb52b0db95` and chain head `4a08a3e3c2444e65d7b9de59b3598f2190d537e9955ebc6f3b135504e53aaaac`. Both record engine source digest `41fcb45ca501f0c8ee3fbe490e492c98c6a24a9c4862636010123ec024d4f6f6` and probe SHA-256 `68f7bb72107d3c9db42ee3c30316ecb05a111ed153d48de1b5ae2db27820c1d7`.

From `engine/`, verify exact bytes, event chains, frozen conditions, judge manifests and outcomes:

```powershell
uv run --locked --extra dataset python ../docs/reliability-evidence/artifacts/task63-graph-throughput-2026-09-29/verify.py
```

`probe.py` can be run with the same flags shown in each log header and a pinned `--cache` path, writing to a **new** output path. A fresh invocation cannot overwrite an existing log. The hashes are a reviewable Git content anchor, not an external signature. The verifier does not prove oracle adequacy, graph-object integrity, independent review, or any model score.
