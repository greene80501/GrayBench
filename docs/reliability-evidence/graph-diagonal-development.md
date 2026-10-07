# Diagonal and uniformly controlled rotation state

The pinned Qiskit 2.4.2 Diagonal conversion retains a DiagonalGate, whose lazy
definition contains uniformly controlled rotations. The graph registry now admits
exact DiagonalGate, UCPauliRotGate, UCRXGate, UCRYGate and UCRZGate classes.
Rotation axes are preserved as bounded raw strings, including mutations after
definition caching. Constructors and lazy definitions are not invoked by transport.
Actual dictionaries, parameters, definition aliases and native cached parameters
remain distinct where the original objects make them distinct. Arbitrary fields,
subclasses and payload-selected imports remain prohibited.

Ten local cases first failed as unsupported before implementation. Four protected
snapshot/delta controls include incorrect diagonals that must fail. The focused
suite passed 41 tests; the full Docker-enabled suite passed **986 tests in 421.66
seconds**, with zero failures, errors or skips. The accompanying JUnit record is
GrayBench-v4-diagonal-tests.xml. Independent read-only review found no blocking
defect; it did not independently execute tests. Existing graph limits apply;
future SDK matrix expansion still requires broader resource calibration.

Exact task120 replays in normal and hard change from unsupported to pass. Both
complete chains, task selection, canonical completions, extracted code, public
digests and judge manifests were verified. The after source matches the tested
checkout; graph_instruction.py is the only changed runtime file in this pair.

| Artifact | SHA256 |
|---|---|
| GrayBench-v4-diagonal-reference-before.jsonl | 3b58072fdee9febb3ff93b4c95f2a1fbcd0f8661ffc26c13104dad312cfb509f |
| GrayBench-v4-diagonal-reference-after.jsonl | e8236bf924999bb5cb7ed661beeeb8c3e30a1de6ae1880e3f82b040941a07a8e |
| diagonal_graph_reference.py | ed2a0b62d33edabd9e0983734caeec631d4e51127e1b9d5abe2c446645c04b9f |

Before chain: 75e32974a426ba45a9fe1343e3820002c2ce23446b4ef7c5f2db484ad97277f8.
After chain: 56486e18a6b717c532374bf1159a1928bab30ca071bb3197ee5c034dd102c423.
The probe and verifier use workspace-relative cache/output paths from engine/;
choose a fresh output filename for reproduction. Concurrent diagnostics make these
timings unsuitable for isolated performance comparison. These results neither
replace the historical complete cohort nor establish task120 oracle adequacy.
