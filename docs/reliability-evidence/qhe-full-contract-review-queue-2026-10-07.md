# Full QHE contract review queue, 2026-10-07

This authored draft covers all 151 pinned families and therefore both variants
of all 302 records. It derives obligations and questions from the public
requirements, not from whichever input a private test happens to use. The
[source-bound pair audit](artifacts/qhe-pair-audit-2026-10-07/report.json) is the
exact public-wording and signature roster for each row. That report has SHA-256
`c393ab8c364ae7a460b03bdd0db5eb27b83572396c2f26c4ba15cca306721471`.
It binds normal revision `a0066805f7a15cb48e9d0cface2210056185be6d` and hard
revision `315e167a479d5c546565d7f9f8c63a644c84cb50`, both parquet hashes, and
every public/full task identity. Rows refer to `qiskitHumanEval/<ID>`.

This is a requirement-review work queue, not an admitted task release, a
completed requirement-to-test mapping, independent Qiskit review, or observed
mutation results. Every question and proposed control still needs adjudication.
The existing task-specific evidence remains useful; this table does not replace
it or label the other families sound. Original prompts/tests and score
denominators remain frozen. A changed specification belongs to a separately
named strengthened condition with its ancestry and changes disclosed.

## Rules carried into every row

- Resolve the input domain, output type/shape, mutation and alias policy, phase,
  bit/subsystem ordering, tolerance, randomness and resource bounds in the public
  contract before generation. A missing choice is a review question, not license
  to import a hidden-test assumption. Do not test unspecified invalid inputs.
- Separate a value/structure claim from a claim about how it was computed.
  An identical output cannot establish a hidden Sampler call, transpiler setting,
  SDK constructor, backend query or internal synthesis method. Preserve explicit
  process requirements for native reproduction. A protected behavioral revision
  must disclose the changed claim; authenticated process evidence needs separate
  design and qualification, never a candidate's self-report.
- Add independent correct implementations and multiple permitted input classes.
  Accept valid alternatives, global-phase freedoms and degenerate decompositions
  where the reviewed contract allows them. A canonical answer is not authority
  for choices absent from the prompt. Constant output is not automatically wrong:
  some tasks have one fixed correct value or permit repeated valid outputs.
- For each scored requirement, bind cases and non-equivalent wrong controls to
  the exact contract/judge. Validate statistical false-rejection behavior and
  performance on correct alternatives. Reserve controls before execution. The
  controls below are hypotheses; equivalent or out-of-domain mutants must be
  excluded with a reason, not counted as successes.
- Native SDK objects, in-place edits, files, plots, jobs and passes need separate
  interface qualification. Numerical output alone does not establish object
  identity, register topology, method use or side effects. Full external-service
  evaluation remains separate from the declared 143-task offline cohort.

The emphasis on valid input contracts and richer falsification follows
[EvalPlus](https://arxiv.org/html/2305.01210v3), which identifies both inadequate
tests and imprecise descriptions as sources of misjudgment. It does not establish
QHE's score change. SDK ordering and state equivalence must be pinned explicitly;
the [Qiskit 2.4 Statevector reference](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/qiskit.quantum_info.Statevector)
defines its state representation and comparison methods. This table proposes
review work, not mathematical certification from documentation links.
The [RZGate reference](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/qiskit.circuit.library.RZGate)
confirms the single-qubit operation behind task 129's wording question; the
[process-fidelity reference](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/quantum_info#process_fidelity)
defines the value used in task 126. These facts do not establish service behavior
or the provenance of a candidate's returned number.

## Families 0–50

| ID | Observable requirements to cover | Public choices / process requirements to resolve | Proposed falsification controls |
|---|---|---|---|
| 0 | Circuit with requested integer qubit count. | Valid range, zero width, resources; no extra operations specified. | Fixed three-qubit result across permitted widths. |
| 1 | Counts for a phi-plus Bell experiment. | Shots, register keys, seeds, statistical policy; pass-manager level 1 and Aer Sampler use are process claims. | Product-state distribution, invalid/negative/fractional counts; valid stochastic tails. |
| 2 | Phi-plus Statevector amplitudes and dimension. | Global-phase convention and actual Statevector versus explicit values. | Product state, wrong Bell phase, misleading custom equivalence method. |
| 3 | Three-qubit GHZ circuit with measurements; drawing flag changes return packaging. | Measurement coverage, tuple order, figure content; default false belongs to normal prefix. | Missing entanglement/measurement; blank or mismatched drawing; ignore flag. |
| 4 | Circuit implementing the stated four-by-four matrix. | Wire order, phase, circuit width; literal unitary-gate construction versus equivalent action. | Transpose/inverse, wrong wires, correct shape with identity action. |
| 5 | Circuit prepares binary state 1. | Width and integer-basis versus bit-label interpretation. | Prepare zero; test only widths admitted after clarification. |
| 6 | Requested register prepares the stated state. | Does n-qubit “state 1” mean integer basis index 1 or all ones? Width bounds. | Wrong interpretation after adjudication; ignore n. |
| 7 | One-qubit parameterized RX with theta. | Parameter identity/name, allowed extra gates, structural versus action equivalence. | Fixed angle, wrong axis, wrong parameter name. |
| 8 | Theta RX remains symbolic for None and is bound for supplied value. | Real domain, periodicity, phase, None/default behavior. | Ignore value, bind None, sign reversal; include value zero. |
| 9 | Three-qubit EfficientSU2, one repetition, barriers enabled. | Template/entanglement meaning and barrier positions; constructor use versus equivalent template. | RX-only ansatz, no entanglement, missing barriers, extra repetition. |
| 10 | Given two-qubit unitary using single-qubit/CX basis. | Phase, expansion of composite gates; level-1 pass-manager use cannot follow from action alone. | Opaque two-qubit unitary hiding disallowed basis, wrong operator. |
| 11 | Circuit's resulting statevector. | Supported unitary/measurement/reset circuits, starting state, phase, input mutation. | Always-zero state; reverse ordering; delete input gates. |
| 12 | Matrix for a phi-plus Bell preparation circuit. | A state does not identify a unique preparation unitary; specify gate sequence/operator or score state preparation separately. | Alternative preparations are rejected in the [pinned diagnostic](artifacts/task12-operator-ambiguity-2026-10-07/README.md); resolve the contract first. |
| 13 | U rotation with all three angles pi/2. | Literal UGate/type versus equivalent rotations; phase and width. | One angle changed, wrong axis; permuting equal angles is equivalent. |
| 14 | Exactly 100 per-shot results of a phi-plus Bell experiment. | Key format, measurements, distribution calibration; level-1 transpilation and Aer Sampler process. | Two shots, non-bit strings, product-state outcomes. |
| 15 | Bell experiment counts. | Bell-state identity, shots, keys, seeds; transpiler/Sampler process. | Fabricated non-Bell support, invalid totals; avoid fixed exact-count oracle without a contract. |
| 16 | Input action preserved on FakeCairoV2 target. | Layout convention, allowed inputs, seed, basis/connectivity; level-1 process. | Correct target metadata but different computation, swapped mapping. |
| 17 | Input action preserved in CX/ID/RZ/SX/X/U basis. | Opaque-gate expansion, input domain and mutation. | Keep forbidden gate hidden in a definition; change angles while meeting basis. |
| 18 | Ten-qubit GHZ action mapped to FakeSydneyV2. | Layout, connectivity, resource bounds; no-optimization pass-manager process. | Mapped empty/product-state circuit, wrong width. |
| 19 | Eleven-qubit GHZ action mapped to FakeTorontoV2. | “Maximum” optimization level, layout and resources. | Correct backend width with no GHZ action; wrong mapping. |
| 20 | Three-qubit GHZ with FakePerth layout [2,4,6]. | Logical/physical action and phase; level-1 pass-manager process. | Empty correctly mapped circuit, wrong GHZ wires. |
| 21 | Bell action mapped to FakeOslo. | Bell variant, dense layout policy, seed/tie handling; process evidence. | Wrong action with plausible dense layout. |
| 22 | Bell action mapped/scheduled for FakeAuckland. | Timing units, duration representation, as-late-as-possible and level-1 process. | Correct action but wrong schedule; correct schedule with wrong action. |
| 23 | Constant Deutsch–Jozsa oracle on two inputs and one output. | Both constant-zero and constant-one functions, register order, oracle validity. | Input-dependent oracle; do not reject a permitted constant-one alternative. |
| 24 | Classify supplied oracle as constant or otherwise. | Promise class, reversible encoding, supported width; balanced-only algorithm versus arbitrary nonconstant functions. | Fixed bool; permitted unbalanced/nonconstant cases after domain resolution. |
| 25 | Seven-qubit GHZ routed for supplied coupling map. | Connected/directed maps, impossible routing, layout and mutation; LookaheadSwap process. | Ignore map, wrong action, illegal edge. |
| 26 | Three-qubit DAG with Bell state on qubits 0 and 1. | Extra measurements are not stated; DAG structure/action and phase. | Bell on wrong pair; judge must accept permitted unmeasured output. |
| 27 | Three-qubit DAG: H0, CX0→1, then H0 at back. | Operation ordering, unused qubit, allowable equivalent structure. | H at front, CX direction reversed, wrong qubit. |
| 28 | Histogram of phi-plus and phi-minus results. | What observable distinguishes the phases, shots, plotted labels/data, figure contract. | Blank figure, missing series; equal computational-basis distributions alone are not wrong. |
| 29 | FakeAthensV2 transpiled Bell layout plot. | Plot content/data versus incidental style; Bell variant and transpiler process. | Blank figure; plot inconsistent with declared layout. |
| 30 | Bell state city plot. | Bell variant, plotted density matrix, axis ordering; figure export boundary. | Correct axes but wrong bars; blank plot. |
| 31 | Bell counts under sampler seed 42. | Shots, sampler implementation/defaults, registers; exact-count reproducibility must be qualified. | Non-Bell support, wrong totals, seeded reference instability. |
| 32 | Bell expectation values for II, XX, YY, ZZ. | Return annotation conflicts with plural values; order/packaging, coefficients and estimator process. | Flip YY sign, omit a basis, use undisclosed coefficients. |
| 33 | Counts for two seeded two-qubit depth-two random circuits. | Shots, ordering, generator/runtime identity, seed behavior; Aer Sampler process. | Duplicate first result, wrong seed/depth, invalid counts. |
| 34 | Four named Bell entries with RuntimeJobs and batch id. | Offline fake-backend job/batch semantics and lifecycle; level-3/seed123 process. | Missing/misnamed state, reused unrelated job, fabricated batch identity. |
| 35 | Job estimating specified five-qubit ansatz observable. | Parameter binding absent from prompt; Z_-1 notation, job semantics, seed789 and pairwise/level1 process. | Undisclosed binding dependence; unrelated or forged job. |
| 36 | Bernstein–Vazirani oracle for input bits. | Input length/alphabet, output wire and bit order, clean ancillas. | Ignore one secret bit, reversed bits, fixed example oracle. |
| 37 | BV result strings and PrimitiveResult for input. | Result packaging, measurement width, shots/seed; execution versus fabricated values. | Invalid bit strings, wrong secret, mismatch between strings and result data. |
| 38 | H0, CRZ0→1(theta), H1, CRY1→0(theta). | Finite angle domain, order and phase; circuit structure versus equivalent decomposition. | Sign flip, swapped control/target, ignore theta. |
| 39 | Uniform n-qubit superposition statevector. | Width bounds, normalization and global phase. | Wrong dimension, nonuniform amplitudes, fixed width. |
| 40 | Counts for supplied three-qubit state under seed 42. | Normalized complex domain, “non-trivial” meaning, shots/register order; Sampler process. | Fixed counts, reversed basis labels, valid phase-equivalent state. |
| 41 | Compose a declared two-qubit Pauli into a three-qubit identity. | Normal XZ/YX contradiction; positions [0,2] are undisclosed in both suites. | XZ/YX and alternative positions; already reproduced, unresolved. |
| 42 | Operator 0.5(XX+YY−3ZZ). | Output class and coefficient precision. | Wrong ZZ sign/coefficient, wrong shape, replace YY with YX. |
| 43 | Preset manager for least-busy device, level 3. | Service credentials, candidate access, snapshot/time, tie policy, pass-manager boundary. | Stale/wrong device, fabricated manager; authorized external integration only. |
| 44 | Tensor of X circuit and controlled RY(0.2) circuit. | Tensor order, control/target and circuit width. | Reverse tensor order, angle sign or control reversed. |
| 45 | Random n-qubit Clifford circuit. | Randomness distribution, repetitions/seed, width domain; output membership alone cannot prove random generation. | Fixed Clifford, non-Clifford gate, ignored width; calibrate declared randomness. |
| 46 | Seeded random invertible binary-map circuit. | Generator/version, width, GF(2) map convention; named generation method is a process requirement. | Singular/identity fixed map, ignore width/seed, reversed bit order. |
| 47 | Heads/Tails counts for requested coin-flip samples. | Shot domain, distribution, key spelling; examples are illustrative, not mandatory exact counts. | Wrong total/keys, biased fixed output under calibrated sampling; no example-assisted strengthened prompt. |
| 48 | n random unsigned 8-bit integers. | Duplicates allowed, distribution/independence, n domain; circuit use is not proven by list values. | Wrong count/range; fixed repeated values only under declared statistical rule. |
| 49 | Elitzur–Vaidman bomb tester circuit. | “Simple” leaves live/dud model, wires, measurements and accepted construction unspecified. | Omit interference or bomb interaction after the contract is fixed. |
| 50 | Remove requested instruction from supplied circuit. | Index domain, input mutation/alias policy, custom definitions and retained topology/phase. | Always remove first, delete other gates, alter wire mapping. |

## Families 51–100

| ID | Observable requirements to cover | Public choices / process requirements to resolve | Proposed falsification controls |
|---|---|---|---|
| 51 | Dynamic teleportation of the instruction-prepared sender state. | Instruction/list domain, receiver index, feed-forward registers, measurement and reference-state interpretation. | Omit one correction, wrong receiver, only teleport a fixed zero state. |
| 52 | Encode/decode supplied two classical bits with shared entanglement. | Bit length/order, sender/receiver wires, measurements, communication representation. | Swap bit roles, omit Bell preparation/decoding, ignore input. |
| 53 | Counts encode 8-bit a XOR b. | Signedness/range, padding, result registers, shots; circuit/Sampler execution process. | OR instead of XOR, truncate high bit, fixed example. |
| 54 | Counts encode 3-bit a AND b. | Integer range, ancillas, measured output ordering/shots; execution process. | OR instead of AND, ignore one bit, return input instead. |
| 55 | Counts encode 3-bit a OR b. | Integer range, output width/register ordering/shots; execution process. | XOR instead of OR, fixed output, truncated leading zeros. |
| 56 | Counts encode 8-bit NOT a. | Unsigned range, exactly eight output bits, shots; execution process. | Unbounded signed bitwise NOT, wrong mask width, ignore input. |
| 57 | SWAP action with CX-only basis. | Wire ordering, global phase, expansion of custom definitions. | Identity or two-CX circuit; hide non-CX operations. |
| 58 | Controlled-H action using CX and RY. | Control/target, phase, allowed gate representation/decomposition. | Wrong controlled phase, uncontrolled H, extra forbidden gate. |
| 59 | CZ action using H and CNOT. | Basis and definitions, wire order, phase. | CX alone, H on wrong side/wire, nonunitary measurement. |
| 60 | CY action using exactly one CX plus one-qubit gates. | Literal versus expanded CX count, phase, wires. | Controlled X, two CXs, wrong phase despite correct output on zero. |
| 61 | Quantum/classical registers and measurement circuit. | Register sizes/names and measurement mapping are not stated. | No measurement, missing register after permitted sizes are declared. |
| 62 | BB84 sender action for supplied states and bases. | Binary encoding, equal lengths, width limits, state versus measurement contract; existing explicit value revision is separate. | Ignore either argument, fixed seeded five-qubit circuit, reversed order. |
| 63 | Receiver key derived from sender bases and circuit. | Receiver bases/RNG unavailable; sifting, measurement and empty-key policies. | Fixed key; do not judge against an undisclosed random receiver choice. |
| 64 | Circuit output y satisfies y XOR s = s; register named c. | That equation permits y=0 independently of s; width and measurement contract need clarity. | Wrong register name, nonzero y; input-independent zeros are not intrinsically wrong here. |
| 65 | n-qubit forward QFT using basic gates. | Transform sign, swaps/endian order, phase, domain and allowed basis. | Inverse QFT, dropped controlled phase, wrong swaps. |
| 66 | Measured W-state circuit. | Qubit count and measurement map not stated; size/resource choice must be public. | Product state, wrong excitation distribution, missing measurements. |
| 67 | Measured CHSH circuit for Alice/Bob bits. | Basis-angle convention, initial entangled state, bit order and allowed input values. | Ignore a setting, missing entanglement, incorrect angle sign. |
| 68 | Three live/dud/detonation percentages for 25-cycle Zeno tester. | Fractions versus percentages, shot/statistical policy, bomb interaction model and ordering. | Wrong cycle count/process, swapped categories, invalid probability totals. |
| 69 | H0, CS0→1, H1, CS†1→0 sequence. | Phase, expanded control conventions and circuit structure. | Swap direction, omit dagger, incorrect sequence. |
| 70 | H0, Fredkin0/1/2, H1, CS†1→0. | Which Fredkin wire controls, operation order and width. | Ordinary SWAP, wrong controlled pair, omit dagger. |
| 71 | H0, controlled-root-X0→1, H1. | Root-X convention/phase and control orientation. | Controlled X instead of root-X, wrong wire, sequence swap. |
| 72 | In-place gate application when all chosen classical bits equal 1. | Empty condition, register grouping, index domain, repeated bits, return None and mutation. | OR instead of AND, ignore one condition bit, append unconditionally. |
| 73 | In-place X-basis measurement into chosen classical bit. | Index domain, surrounding operations, return None; preserve unrelated circuit state. | Z-basis measurement, swapped mapping, copied result without mutation. |
| 74 | Barrier-separated circuit segments with barriers omitted. | Leading/trailing/consecutive barriers, empty segments, registers, phase and alias policy. | Drop a nonbarrier gate, retain barriers, wrong segment order. |
| 75 | One sampled outcome as bools indexed by classical-bit order. | Unmeasured bits, circuit domain, seed/shot semantics; no deterministic expected sample without declared randomness. | Reverse list, wrong length/type, ignore classical mapping. |
| 76 | TransformationPass replaces non-controlled Z with H-X-H. | Recursive blocks, literal gate recognition, input mutation and pass/callback boundary. | Replace controlled-Z too, miss a Z, wrong sequence/wires. |
| 77 | Circuit produces supplied probability distribution. | Normalization, nonnegative finite values, width/missing keys, allowed phases and measurement policy. | Correct shape but wrong probabilities, reverse labels, fixed distribution. |
| 78 | Inverse QFT without swap gates. | Width domain, transform/order convention and allowed equivalent decomposition. | Forward QFT, added swaps, sign error in controlled phase. |
| 79 | Total circuit instruction count. | Top-level versus nested blocks, directives and composite expansion. | Count only gates, ignore repeated instructions or supplied circuit. |
| 80 | Total unitary-gate count. | Opaque custom gates, reset/delay/directives/control-flow definition, top-level versus recursive counting. | Count measurements/resets as unitary; exclude valid custom gates. |
| 81 | Returned Bell circuit from generated QASM2. | Which Bell construction/measurements; QASM round-trip process cannot be proven from circuit alone. | Wrong Bell action; separately qualify claimed serialization process. |
| 82 | File bell.qpy serializes phi-plus circuit in binary mode. | Trusted file transfer, working directory, size/version, parsed circuit and side-effect boundary. | Missing/wrong filename, truncated file, valid QPY with wrong state. |
| 83 | Tuple contains phi-plus Bell density matrix then concurrence. | Dimension, tolerance and packaging; state identity is already specified. | Swapped tuple, wrong density with constant concurrence one. |
| 84 | Controlled custom one-qubit unitary on control0/target1. | Unit choice is free; “e.g. U3” is an example, not one mandatory answer; identity/nontriviality policy. | Wrong control/target, uncontrolled operation, inconsistent custom definition. |
| 85 | QASM2 string representing supplied circuit. | Supported instructions, parameters, global phase, registers, parsing and file-free boundary. | Fixed Bell string, missing gate, invalid syntax. |
| 86 | Two collected five-qubit CX-chain circuits, unrestricted and width≤3. | Chain edges/order and collection structure; pass-manager/method use versus observable blocks. | Identity blocks, wrong chain action, oversized restricted block. |
| 87 | One-qubit H, delay100, H circuit. | Delay units/default and placement; action alone cannot identify a delay. | Missing/wrong-duration delay, extra operation. |
| 88 | H/measurement followed by IfElse Z for 1, X for 0, final measurement. | Classical mapping and block structure, branch order, output register policy. | Swapped branches, missing initial measurement, wrong condition. |
| 89 | Doubly controlled H with controls0/1 and target2. | Control state, phase and definitions. | Single control, wrong target, controlled-X replacement. |
| 90 | Custom gate applies X to target1 and H to target2, controlled by0/3. | Phase, control-state and opaque definitions; preserve explicit target correspondence. | Contiguous wrong controls, swapped targets, missing control. |
| 91 | Bell preparation instruction named bell_instruction. | Instruction versus gate/circuit, phase, classical bits and definition boundary. | Wrong name, missing entanglement, incorrect returned type. |
| 92 | Phi-plus Bell stabilizer state and its probability dictionary. | Register basis/order, dictionary keys, tuple order, tolerance. | Product stabilizer with fabricated Bell probabilities, mismatched pair. |
| 93 | Seed1234 n-qubit random Clifford synthesized by named method. | Generator/runtime identity, width domain, synthesis process versus equivalent Clifford. | Wrong width/Clifford; exact representation must not penalize equivalent synthesis without specification. |
| 94 | QASM3 string representing supplied circuit. | Supported dynamic circuits, declarations, parameters, phase and parser compatibility. | Fixed output, dropped branch, malformed declarations. |
| 95 | Input circuit with all barriers removed. | Return packaging, input mutation/alias policy and recursive barriers; preserve all other behavior. | Remove other gates, leave internal barrier, fixed circuit. |
| 96 | FakeKyoto phi-plus Bell counts, sampler seed42. | Shots, noise/backend snapshot and keys; exact counts need runtime calibration. | Ideal/fake mismatches only after noise/shot contract; invalid counts. |
| 97 | Two-qubit connections of supplied fake/IBM backend. | Directed edges, target versus coupling map, object/service snapshot and unavailable backend behavior. | Ignore backend, reverse/deduplicate directed edges incorrectly. |
| 98 | Minimum supplied backend readout error. | Property availability, missing values, finite range and fake/real backend snapshot. | Maximum instead of minimum, fixed value, wrong qubit subset. |
| 99 | Remove operations with unassigned parameters. | Partial bindings, composite/control-flow scope, input mutation and remaining definitions. | Remove bound gates too, retain free parameter, fixed circuit. |
| 100 | Single-qubit gates decomposed to T/T†/H dense basis. | Approximation tolerance is essential; parameter domain, multiqubit preservation, pass-manager process. | Exact identity replacement, excessive approximation error, forbidden basis hidden in definitions. |

## Families 101–150

| ID | Observable requirements to cover | Public choices / process requirements to resolve | Proposed falsification controls |
|---|---|---|---|
| 101 | FakeKyoto coupling graph state. | Directed-to-undirected adjacency, ordering/resources; explicit networkx hint must be disclosed or removed in a named strengthened protocol. | Empty graph, missing edge, wrong backend adjacency. |
| 102 | Backend with fewest level-0 Bell transpilation instructions among three fakes. | Bell construction, runtime defaults/seed, tied minima, instruction definition; process requirement. | Wrong minimum, wrong backend set, tie mishandling. |
| 103 | All FakeBackendV2 provider names supporting ECR. | Name/class convention, enumeration/version, ordering and duplicates. | Partial/hard-coded obsolete list, include non-ECR backend. |
| 104 | Largest prescribed weighted transpilation cost over three fakes. | QFT construction/order, gate arity counting, barriers/directives, seed1234/level3 process. | Minimum instead of maximum, wrong weights, wrong backend. |
| 105 | CNOTDihedral for CX0→1 then T0 circuit. | Type/native representation and action, phase and gate order. | Missing T, reversed CX, correct type with wrong action. |
| 106 | Composition of two stated CNOTDihedral elements. | Returned element versus “circuit” wording; these fixed elements may commute, so swapping order need not be wrong. | Omit second X, reverse CX direction, wrong returned class. |
| 107 | Composed dimension-two ScalarOps, coefficient four. | Dimension notation, type/native-object representation. | Coefficient two, wrong dimension, arbitrary scalar-only output. |
| 108 | Ordered original Choi, its adjoint, and composition for both inputs. | Valid channel/matrix dimensions, vectorization, composition order, alias/mutation and tolerance. | Wrong first return, ignore second input, transpose instead of adjoint. |
| 109 | Parameterized circuit covers Bloch equator with minimum resources. | Resource objective, angle domain, physical variation versus global phase. | Fixed plus state, only global-phase changes, unnecessary resources after metric declared. |
| 110 | Exactly n random Clifford circuits equivalent to input within stated tolerance. | Equivalence metric/phase, validity of tolerance0.4, distribution, duplicates and n domain. | Empty list, wrong length, unrelated Clifford; calibrate permissive tolerance. |
| 111 | Minimal ansatz for uniformly distributed pure Bloch-sphere states. | Parameter sampling law, uniform-area meaning and gate-resource objective; static ansatz alone cannot establish dataset distribution. | Equator-only/polar-biased sampling, fixed state, wrong resource metric. |
| 112 | Lie–Trotter circuit for Pauli/time lists and repetitions. | Matched lengths, real times, repetition domain, ordering, formula/process and approximation contract. | Ignore term/time/reps, wrong sign, reordered noncommuting terms. |
| 113 | Barrier removal with accurate before/after depths and width PropertySet. | Definition of depth/width, recursive scope, mutation, how transformed circuit is observed. | Fixed metrics, remove nonbarrier gate, wrong width. |
| 114 | Directed coupling list, added edge5→6 and physical qubit7. | Isolated-node preservation, extra node6 implied by edge, native representation. | Add qubit8 instead of7, wrong edge direction, omit isolated qubit. |
| 115 | Two-qubit Target with named U parameters, bidirectional CX, nonzero errors/durations. | Valid probability/time ranges, units and native parameter identity. | Zero error/duration, fixed or misnamed U angles, missing direction. |
| 116 | Pauli/time evolution via MatrixExponential. | Width/time domain, phase, native transport and process; explicit matrix-value revision is a different condition. | Ignore time/Pauli, sign flip, reversed tensor order, omit identity phase. |
| 117 | Four-by-four unitary decomposed with CX basis by named decomposer. | Input unitary domain, basis expansion, phase, method versus action; existing value/basis revision is separate. | Constant CX, nonunitary circuit, wrong operator, forbidden opaque gate. |
| 118 | C3SX on first four circuit qubits. | Circuit width, control state, root-X convention/phase, type versus action. | Wrong target, fewer controls, full X rather than root-X. |
| 119 | CDKM ripple-carry adder for size and full/half/fixed kind. | Width/register conventions, valid kinds/sizes, ancillas and class versus arithmetic behavior. | Ignore kind, ignore size, wrong carry action. |
| 120 | Circuit implements supplied diagonal entries. | Power-of-two length, unit-modulus complex domain, phase, input mutation and gate versus action. | Fixed diagonal, permuted entries, wrong phase, changed input. |
| 121 | H-randomized qubit, measure, conditional X on outcome1; two classical bits, register c. | Final measurement role, exact condition and bit mapping; branch method observable structurally. | Unconditional reset, omit first measurement, wrong register/condition. |
| 122 | Circular EfficientSU2 for size, one rep, AI service transpilation on Brisbane level3. | Parameters, service credentials/snapshot and AI evidence; external integration separate. | Correct circuit type only, ignore size, unrelated service result. |
| 123 | FakeBelemV2 error-map plot. | Backend data, axes/labels, renderer/version; output image/figure boundary. | Five blank axes, incorrect data/backend. |
| 124 | Noise model for FakeCairoV2. | Backend snapshot, enabled error families, basis and native NoiseModel boundary. | Empty model, wrong backend/qubit mapping. |
| 125 | Gate equivalent to input circuit action. | Eligible unitary circuits, classical bits, phase, width and alias/mutation policy. | Shape-correct wrong gate, fixed example, altered input. |
| 126 | Hadamard operators differing only by global phase; return process fidelity. | Returned value alone is always one for valid choices, so it cannot verify operator construction or fidelity-method use. | Wrong returned fidelity; constant one is not distinguishable from computation by value alone. |
| 127 | Seed17 random four-qubit depth-three measured circuit. | Generator/runtime identity, depth meaning and measurement position; generation process. | Wrong seed/width, no final measurement, wrong depth. |
| 128 | H on first three qubits, measurements, XOR-conditioned X on fourth, final measurement. | Register layout and branch representation; examine preparation and control separately. | Omit H gates, use AND/OR, wrong destination classical bit. |
| 129 | Highest RZ error backend result; None only when RZ is unsupported. | RZ is single-qubit, while prompt requests a qubit pair; missing/zero errors, ties and live-service snapshot. | Wrong gate/error maximum, fabricated pair, ignore backend; do not turn a service failure into None. |
| 130 | n-qubit circuit inverse of stated H/CX sequence. | n≥5 domain must be declared, one-based ordinal to zero-based wires, phase. | Always five qubits, omit inverse, wrong wire interpretation. |
| 131 | Named fake backend's qubits, coupling map and supported instructions. | Name/class resolution, provider version, ordering/absence semantics. | Fixed Cairo data for other name, missing directed edges/operations. |
| 132 | Six seed17 circuits, level1/seed1 optimization, two size-three batches, seed42 results. | Shots, result packaging and Batch/runtime process; fixed returned counts cannot prove execution. | Wrong partition/count, result/circuit mismatch, fabricated batch process evidence. |
| 133 | RuntimeService jobs submitted within last three months. | Account authorization, calendar versus fixed-day window, timezone, pagination, ordering and service snapshot. | Omit later pages, include old jobs, wrong boundary date. |
| 134 | Sorted operational real devices with ≥20 qubits and requested metadata. | Service snapshot, availability/errors, names and supported-instruction semantics. | Simulator, nineteen-qubit device, unsorted/missing metadata. |
| 135 | Readout noise with declared asymmetric errors for qubit0 and others. | Conditional-probability orientation, how “all other qubits” is represented, finite device width. | Transposed probabilities, swap qubit0/default errors, omit defaults. |
| 136 | Ten density matrices pure within supplied epsilon. | Purity-versus-entropy/distance metric, dimension, valid epsilon, duplicates/diversity not explicitly required. | Wrong count, invalid density, fixed near-pure matrix outside small epsilon. |
| 137 | Two-qubit density matrices with entanglement of formation ≥epsilon. | Dataset length/diversity absent, allowed epsilon and tolerance at inclusive boundary. | Below threshold, invalid matrix, wrong dimension; do not require undisclosed length ten. |
| 138 | Density matrices with mutual information strictly >epsilon. | Dimension/partition, list length, log base, achievable epsilon and strict numerical boundary. | Equality at threshold, invalid state; no undisclosed length requirement. |
| 139 | Schmidt coefficients/vectors for statevector and partition. | Normalization, qubit-order/partition, zero coefficients, degeneracy, ordering and paired phase freedoms. | Empty/fixed decomposition, reversed partition, nonorthogonal vectors, failed reconstruction. |
| 140 | Ten normalized length-sixteen probability vectors with entropy above threshold. | Log base, epsilon domain/max achievable entropy, duplicate policy and strict boundary. | Sum>1, negative/nonfinite entry, equality threshold, wrong length/count. |
| 141 | Ten Pauli operators with anticommutator proportional to identity. | Unit/signed Paulis versus arbitrary SparsePauliOps, zero multiple, width, duplicates and scalar tolerance. | Non-Pauli zero operator only if reviewed domain excludes it; nonidentity anticommutator. |
| 142 | Ten one-qubit density matrices with purity strictly >0.5. | Numerical threshold, duplicate policy and valid density convention. | Two-qubit matrix, exactly maximally mixed boundary, invalid normalization. |
| 143 | Ten one-qubit statevector pairs with fidelity strictly >0.9. | Normalization, phase, duplicate policy and threshold tolerance. | Two-qubit pair, equality/below threshold, invalid vector. |
| 144 | Ten density matrices with zero concurrence. | Two-qubit dimensionality must be explicit for this metric; tolerance, duplicates and valid-state domain. | Entangled Bell matrix, invalid density, wrong count. |
| 145 | Inverse QFT for n qubits. | Width including zero, swaps, endian/sign convention, resources. | Forward QFT, fixed width, swallowed n=0 failure after domain declaration. |
| 146 | Trivial-layout StagedPassManager for least-busy backend. | Authorized live snapshot/ties, manager/pass topology and process qualification. | Wrong device, dense layout, unrelated manager; external track only. |
| 147 | Add MCY on target4 controlled by0–3 while preserving input. | Minimum width, control state, input mutation/alias and expanded definitions. | Discard input, wrong target/control, MCX instead of MCY. |
| 148 | Route supplied circuit with SWAPs on backend coupling map; preserve gates. | Layout/permutation, directed connectivity, impossible maps, dynamic instructions and input mutation. | Right gate counts with wrong wires, transformed original gates, illegal route. |
| 149 | Most common BitArray outcome string. | Ties, empty shots, multiple parameter axes, width/leading zeros and bit order. | First string instead of mode, wrong tie handling, dropped padding. |
| 150 | Append for-loop: RY(pi/n·i), H/CX, measurement, conditional break on1. | Positive n, starting circuit, classical mapping, iteration semantics and preserving input; mandatory loop structure. | Missing break, wrong condition, fixed count, wrong angle/index, discard input. |

## Review order and completion evidence

Start with requirements that can change the meaning of a comparison, rather
than selecting tasks because their references currently pass: contradictory or
undisclosed contracts (6, 12, 32, 35, 41, 61, 63, 66, 68, 100, 111, 129,
136–141), side-effect/identity interfaces, stochastic checks, then the remaining
deterministic families. This is prioritization of questions, not proof that every
listed task is defective. Recorded known false passes remain separate evidence.

For every family, convert these draft clauses into a source-bound public
contract and atomic scored requirements; record which original clauses are
preserved, clarified, removed as hints, or moved to a separately qualified
process/integration track. A reviewer must decide whether normal/hard retain
equal semantic requirements while preserving their intentional context gap.

For each atomic requirement, record permitted inputs and expected behavior,
oracle derivation/tolerance, at least one independently correct alternative,
and a non-equivalent wrong control that the judge rejects. Exercise the actual
candidate boundary, not only the host oracle. Keep method, value, structure,
randomness, resource and provenance findings distinct. Collect independent
Qiskit review and clean isolated reproduction before task admission. Empty
requirements, unresolved questions and unqualified interfaces remain blockers.

The full 151-family population is a review obligation. Unexpected reference
failures block the declared release; they must not shrink the denominator.
The eight currently service-dependent families (43, 97, 98, 122, 129, 133, 134,
146) retain their ancestry and explicit separate coverage status. The wording
review does not authorize creating IBM Quantum credentials or substituting a
fake service for a real-service claim.
