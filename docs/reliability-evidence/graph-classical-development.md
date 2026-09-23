# Classical expression development

The native-valid expression snapshot regression initially failed with Unsupported
graph object: Unary. The new closed codec represents held expression roots as
graph nodes and intrinsic children as values: Qiskit 2.4.2 returns fresh wrappers
from child getters. Equal roots remain distinct, while repeated references to the
same root retain identity. IfElse Python conditions and native cached conditions
are separate, just as they are for tuple conditions.

Fixed expression forms cover Var, Value, Stretch, Cast, Unary, Binary and Index.
Intrinsic type descriptors cover Bool, Uint, Float and Duration; integer and float
literal payloads are bounded. Variables use fixed classical-bit/register or UUID
descriptors. There are no payload-selected classes, imports, pickle or QPY.
Validation checks exact fields, constructor results and canonical reconstruction.
Trees are limited to 4096 nodes and depth 16, widths/integers to 1024 bits.
The existing overall graph message cap remains in force.

Nineteen new tests pass, including protected input-circuit mutation, retained root
aliases, equal distinct wrappers, all seven expression forms, malformed payloads,
and depth/sibling budget enforcement. The resource-error test initially exposed
a generic ValueError handler swallowing WireLimitError; it now preserves the
resource outcome. The final full Docker regression passed 903 tests in 352.92 seconds, with
zero failures, errors or skips. Ruff lint/format (131 files), whitespace and
secret-value checks passed. Report: GrayBench-v4-classical-tests.xml.

The source-guarded task128 replay passes normal and hard. Its full event chain was
independently inspected, and its source manifest exactly matched runtime bytes.
Raw evidence: GrayBench-v4-classical-reference.jsonl; SHA256
083a0491a0261644f96ce0b59ceb48eeefdf03126c13f306ad10095de297daa9;
chain head e9febb643a03d04e79e0c1dfcc4b9b83dea273b80c2ef20fc28758c63df59102.
These two reference cases are interface calibration, not model scores or a new
whole-suite aggregate.

Remaining capabilities include circuit-owned variable/capture storage, duration
literal objects, separately exported type/enum objects, loops and other interfaces.
This increment does not establish full Qiskit support or complete benchmark
admission. The uniform resource-policy audit remains required.

Source: IBM's [Qiskit 2.4 classical API](https://eu-de.quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/circuit_classical),
consulted September 23, 2026. Wrapper identity and cached-condition behavior were
measured directly against the pinned Qiskit 2.4.2 runtime; API descriptions alone
are not treated as evidence for those implementation details.
