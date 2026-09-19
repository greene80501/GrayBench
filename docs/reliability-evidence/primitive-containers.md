# Primitive result container transport

The fixed data-only registry supports Qiskit 2.4.2 BitArray, DataBin,
PrimitiveResult, PubResult and SamplerPubResult. It retains packed uint8 bytes,
declared bit width, array/shot dimensions, ordered fields, ordered per-pub results,
and global and per-pub metadata through the existing bounded value codec.
It neither expands packed samples into a histogram nor changes padding bytes.
The SamplerPubResult subclass is retained, including its ordered join behavior.

The [Qiskit sampler result documentation](https://quantum.cloud.ibm.com/docs/en/guides/sampler-input-output)
describes these separate data and metadata layers. Constructors and array shape
rules were also inspected in the installed pinned source. Only fixed constructors
are callable during decoding; wire values cannot select arbitrary Python classes.
Special/reserved DataBin attribute names are rejected. Shapes, byte sizes,
field counts and nesting have explicit limits. Cyclic metadata remains unsupported.

A DataBin can be mutated so its attribute and mapping disagree. Encoding detects
that divergence and leaves it unsupported rather than selecting one version and
silently repairing the candidate. General aliases, arbitrary extra attributes,
private-state mutations, subclasses and live job objects are not admitted.
Metadata values still need a supported bounded representation. This is interface
support, not proof of correct algorithm execution or task admission.

Tests cover packed padding bytes, array shape and shot order, empty arrays,
ordered registers and joined samples, result subclasses, nested metadata,
malformed bit width, special field names, metadata cycles and divergent DataBin
attributes. The new codec is explicitly included in candidate and protected-judge
mount manifests; the candidate receives no private tests or credentials.

## Protected replay and task 37 defect

The canonical task 37 and 149 answers pass both pinned normal and hard tests.
The protected replay also shows that task 37 accepts a fabricated result with
`["not-a-bitstring"]`, one unrelated zero-valued sample, and no circuit/sampler
execution at all. The test checks list type, list length against shot count and
PrimitiveResult type; it does not check bit validity, register width, consistency
between the two returned parts, or the algorithm's recovered string.

Both canonical task 37 invocations return `00000` for input `1111`. The preserved
source creates a zero-initialized circuit with CX gates and measurement, without
the algorithm's state preparation and interference steps. CX gates leave the
all-zero state unchanged. This is incompatible with recovery of the hidden
nonzero string, the goal described by [IBM's Bernstein-Vazirani documentation](https://quantum.cloud.ibm.com/docs/api/qiskit/0.28/qiskit.aqua.algorithms.BernsteinVazirani).
A corrected task needs explicit output-register/ancilla semantics and meaningful
functional checks. Returned result objects alone cannot prove that a particular
sampler or backend was actually used. Do not add undisclosed reference procedure
requirements or treat reference compatibility as semantic correctness.

The source-guarded six-case log is `GrayBench-v3-primitive-container-evidence.jsonl`,
SHA-256 `1eed2bbb2a093fbef8171fad2bf68c2412c32db219ca76f5524dedbc46e0d935`.
It retains task records, probe code, actual data and metadata, original reference
answers and protected transcripts. Reference contract expectations are explicitly
not adjudicated. Actual source bytes are retained, with Windows line-ending
normalization distinguished from Git bytes. No hosted model generations or IBM
Quantum account setup were used; the canonical sampler ran on local Aer inside
the isolated container.

Final validation: 355 tests passed with Docker enabled, zero failures/errors/skips,
in 136.68 seconds. Ruff lint/format and credential-value scans passed. The earlier
full run recorded 354 passes and one expected-file-order assertion failure; that
report is preserved separately. Correcting the expected alphabetical order made
the isolation check and final full suite pass. No source behavior was changed
after the protected reference replay.
