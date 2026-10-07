# Task 20: exhaustive declared layout domain

The protected task-20 public value contract accepts a list of three distinct
physical wire indices from 0 through 6 and requests the seven-qubit GHZ+
amplitude vector on those wires. There are 7 × 6 × 5 = 210 ordered valid
layouts. The original `task20-seven-qubit-ghz-amplitudes-v1` development
oracle checked three. A candidate that computed the right vector only for
those three layouts passed v1 despite failing the rest of the declared domain.

The separate `task20-seven-qubit-ghz-amplitudes-all-layouts-v2` oracle freezes
all 210 ordered layouts in both normal and hard revised tasks. The public
numeric-value contract and host-side amplitude comparison are unchanged; the
private case digest, oracle label, task digest, cohort and judge identities
change. New protected task-20 plans select v2. The v1 task definition and
three-case digest remain recognizable, and a newly frozen v1 cohort can still
be inspected under this source. An older persisted cohort cannot resume under
the changed engine source and judge-code digests; replay needs its original
source. The v2 task validator rejects a partial layout set. This remains a
distinct value task, not the original QHE circuit/pass-manager task.

| Suite | Three-layout v1 task digest | All-layouts v2 task digest |
| --- | --- | --- |
| normal | `1794ec084916d55e5a0e6c204b99bf2109f3df44d2bd7a9a7883ad78cf158b0f` | `cb4ba3a8b243e5f621792645466f4ee26b891e89e102245fa9fb2912849524d2` |
| hard | `f5ff8a62d8b395b28f10594613f79333beabe503a7f210ba5511bc65e894812c` | `1964252f5485dc3dbaeeca60295ff9a53b1b98a3bae81d286592dbf9b7f411c7` |

The pinned Python 3.12/Qiskit image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`
ran ten authored controls: in each suite, a direct mathematical solution, an
independent Qiskit `Statevector` construction, and a global-phase variant
passed v2. The three-layout shortcut passed v1 and failed v2 with a candidate
value-format error. All ten observed outcomes matched the declared
expectations. In a local 210-layout timing probe, the direct and Qiskit
alternatives completed in about 0.6 and 1.0 seconds, respectively, with
275,623 output bytes under the default 1 MiB limit. Those measurements are
calibration data, not a guarantee for every correct implementation.

The source-bound, append-only control file was written outside the PR as
`GrayBench-v3-task20-all-layouts-control-final-20260928.jsonl`. Its SHA-256 is
`6f8423cfd24140db480b9b4a1c90820b260da8200c9ff4f49a84a47d9792833f`.
The [replay script](task20-exhaustive-layout-probe.py) records exact candidate
code, expectations, pinned task and revised task digests, image, source
manifest, and each judgment. `graybench reference-inspect` independently
confirmed a complete ten-case chain with head
`3a7a980a07a72581cd185f6c12a058cdefdb2094d50741cd1773ea01435b98a2`.
Reproduction from `engine/`, with a fresh output path:

```powershell
$env:PYTHONPATH=(Resolve-Path .\src).Path
.\.venv\Scripts\python.exe ..\docs\reliability-evidence\task20-exhaustive-layout-probe.py CACHE NEW_OUTPUT --image sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd
```

Exhausting the finite input domain closes this v1 coverage gap for the
declared value task. It does not prove the oracle implementation itself is
correct, attest a native `QuantumCircuit` or pass-manager call, authenticate
the unsigned local evidence, or substitute for independent Qiskit review.
The task remains release-ineligible and no model score was produced.
