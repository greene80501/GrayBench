# Task 109: equatorial coverage is not tested

The pinned normal and hard contracts request a parameterized circuit using
minimum resources whose output covers the equator of the Bloch sphere. The
upstream check calls the candidate 1,000 times, binds every parameter to a normal
random value, computes a statevector, and asserts only that its polar angle is
approximately pi/2. It computes the azimuth but never checks it. It also does not
require a nonzero parameter count.

## Reproduced false accepts

The trusted authored diagnostic runs the exact pinned test, with all 1,000 calls,
for four fixtures in each suite. All eight cases pass:

| Fixture | Behavior | Interpretation |
|---|---|---|
| Canonical H then RZ(theta) | Relative phase varies around the equator | Positive control |
| H then P(phi) | Equivalent equatorial state family, up to global phase | Alternative positive control |
| H only | Always returns the same plus state, with no parameter | False acceptance: neither parameterized nor equator-covering |
| H with parameterized circuit global phase | Has a parameter but the physical state never changes | False acceptance: parameter count alone cannot establish coverage |

Each result includes state witnesses at 0, pi/2, pi and 3pi/2, reported as X/Y/Z
expectation values. The first two constructions vary around the equator. Both
mutants keep the same Bloch vector (1,0,0), within floating-point error.
The global-phase mutant matters because adding only a parameter-count assertion
would leave this false accept intact.

This probe executes trusted fixture source and the inspected pinned tests in the
local Qiskit environment. It is an oracle diagnostic, **not a protected execution
claim, model score, or full task certification**. The parallel protected canonical
1,000-call calibration is a separate experiment. These local timings are not
used as its performance baseline. No model request or hidden assistance is involved.

## Evidence and reproduction

`task109_oracle_probe.py` uses the engine's public extraction policy, preserving
normal-suite completion assembly and the public prefix. It does not change the
private check body or inject an RNG seed. Like the protected judge, it removes
top-level `check(...)` invocations and explicitly invokes the defined check once.
It asserts exactly 1,000 calls before recording a result. Records bind both task digests, exact fixture
source, engine source, Python/Qiskit/NumPy versions and the probe hash. The complete
event chain contains eight results, each recording exactly 1,000 candidate calls.

- Raw: `GrayBench-task109-oracle-verified-0379d13.jsonl`
- SHA256: `4b207236758a1e2737bad345f6ae1572d8dd0ef96aa988ff35a1ec6d0c265116`
- Chain: `667650345c095465040a5ed9fdf4c0665f818c99494dc01e86a995c8f61d8f07`
- Probe SHA256: `af7527661fc33b1ea96ca38c42613927b074e031508920f849db44a13308a430`

From `engine/` in the development checkout, with the pinned dataset cache at the
path used by the script, run:

```sh
uv run --extra qiskit --extra dataset python ../docs/reliability-evidence/task109_oracle_probe.py NEW_OUTPUT.jsonl
uv run graybench reference-inspect NEW_OUTPUT.jsonl
```

The cache path is relative to this workspace's isolated checkout. Adjust it
explicitly in a copied probe for another workspace and record the new probe hash.
Never overwrite prior output.

The first probe invocation attempted to compile the normal canonical completion
as a standalone program. It failed with `IndentationError` before evaluating any
case. The interrupted evidence and original probe are retained as
`GrayBench-task109-oracle-0379d13.jsonl` (SHA256
`a65c53602c6bf8a1971d288cc1820c6c84bb1520f91a8f542608fd72f72171f8`) and
`task109_oracle_probe_initial.py` (SHA256
`232775c427a931979994d27894474720a6065c5c36309b5f8437fa8ee5ea57a7`).
That file has a pending first case and no verdicts; it is not a benchmark failure.
The corrected invocation used a new output file and the existing extraction rule.

That second invocation still had a diagnostic error: it executed the stored test
text without explicitly invoking a normal-suite check. Hard-suite text includes
that invocation; normal-suite text only defines it. Call-count verification caught
four normal cases with zero calls. Their recorded `pass` values are invalid
diagnostic outputs and must not be treated as evidence of oracle behavior. This
attempt is preserved in `GrayBench-task109-oracle-extracted-0379d13.jsonl`
(SHA256 `31f5450dfc7f198228254e2f7f0b167cb7bfb340cda501f49f32992b959ec225`)
and `task109_oracle_probe_extracted.py`
(SHA256 `3ff386c99e875e29005a542e10cb2f43d093b21a37b73b88f0bd84413d195f49`).
Only the third, explicitly invoked and call-count-verified experiment supports
the eight-case table above. All prior attempts remain intact.

## Required contract and oracle work

Preserve the original upstream outcome. A stronger test belongs to a named,
versioned condition applied uniformly to every candidate, not a silent replacement.
It must distinguish a physically varying equatorial family from a global-phase
parameter or a fixed state. Clarify the allowed parameter domain, output type,
one-qubit requirement and meaning of minimum resources before imposing thresholds.
Do not require the reference's parameter name or gate spelling.

Finite angle samples can reject these mutants but cannot by themselves prove
continuous coverage for arbitrary candidate functions. A revision must state its
finite observable guarantees and unresolved requirements honestly, include
independent valid parameterizations, and test controls for missing arcs, extra
resources and non-equatorial outputs. Task 109 remains unadmitted. Improving
transport speed or completing 1,000 calls does not resolve this oracle defect.
