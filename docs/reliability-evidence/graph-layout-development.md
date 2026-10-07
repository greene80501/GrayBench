# Layout and transpilation metadata graphs

The first protocol4 baseline rejected eleven task families at the circuit instance
field boundary. Native transpilation adds optional `_clbit_write_latency` and
`_conditional_latency` fields, and many outputs also carry a TranspileLayout.
The circuit codec now explicitly admits these fixed optional fields, preserving
absence, addition and removal without adding defaults to an existing dictionary.

Layout uses slots, not an instance dictionary. Its `_p2v` and `_v2p` maps and `_regs`
list are separate graph references. Public map getters return those actual maps;
direct updates can make the maps inconsistent. The codec preserves that state
instead of deriving one map from the other or repairing it. Empty physical slots
represented by None are retained. Validation limits physical indices and permits
only admitted quantum bit/register members; wire data cannot select attributes or
constructors.

TranspileLayout's five fixed instance fields are represented alongside its actual
dictionary: initial/final layouts, input mapping, input count and output-qubit list.
In the native fixture, the output list and its bit wrappers are distinct from the
circuit's public list and wrappers. The graph preserves the observed identities,
including equality between distinct registered-bit wrappers, rather than inventing
aliases from equal values.

Three initial regressions failed before implementation. The focused run passed
48 tests, including eight new layout cases, existing circuit/anchor cases and an
actual protected transpilation fixture. Coverage includes exposed-map aliases,
equal slot replacements with retained detached maps, optional-field presence,
native final-index behavior and malformed state rejected before live mutation.

The full Docker-enabled suite passed 848 tests in 364.89 seconds, with zero failures, errors or skips in the verified JUnit report. The source-guarded 22-case reference replay
is complete and its event chain verifies. Tasks10,16,17,18,19,20,21,25 now pass in
both suites: sixteen passes total. Tasks22 and86 in each suite reach a remaining
retained-operation codec gap; task100 reaches the 4096 packed-operation limit.
These six outcomes remain unsupported, not model failures.

Raw evidence: `GrayBench-v4-layout-targeted-reference.jsonl`, SHA256
`8fac1b3b0330104b70f9f87194bb6121f61e12049494a316fa2995edd462d2a5`.
Chain head:
`6490df8aad8d5ff3e16ee3541c5e2212a2a4e3642957f12f04b4255eabbf3378`.
The historical full baseline and its unsupported counts remain unchanged evidence;
targeted outcomes are not a new aggregate. Other object interfaces, full oracle
admission, provider calibration and reproducibility remain open.
