# Task41: explicit Pauli subsystem values

## Original ambiguity and new condition

The [pinned pair audit](artifacts/qhe-pair-audit-2026-10-07/README.md) reproduces
Task41's conflicting normal wording (XZ and YX), hard wording (YX), and the
private placement `[0, 2]` absent from both prompts. Original prompts, checks,
reference answers and observations remain historical; this revision does not
silently repair or replace their scores.

`qhe41-explicit-pauli-subsystems-values-v1` chooses YX and publicly places its
local qubit 0 on global qubit 0 and local qubit 1 on global qubit 2. The other
qubit is unchanged. Choosing YX is an explicit revision decision: hard wording,
the normal Pauli name and both original references/checks agree on it. This is
evidence of a likely intended label, not proof that the contradictory original
prompt was sound. The previously private placement is now part of the public
requirement before generation.

Normal retains its imports, annotated function-completion prefix and no-argument
signature. Hard supplies the same requirement and asks for a standalone
`compose_op()` function. Both require a plain Operator value, input and output
dimensions `(2, 2, 2)`, an eight-by-eight logical matrix, finite complex64/complex128
entries, basis order `|q2 q1 q0>` and row/output-column/input conventions.
Absolute tolerance is `1e-10`, relative tolerance is zero, and there is no extra
global-phase alignment. This is a specified Pauli operator, rather than a channel
equivalence task. Small differences within the numeric tolerance can pass.

In Qiskit's declared Pauli convention, the rightmost label character acts on
local qubit zero. The pinned
[Qiskit 2.4.2 Pauli source](https://raw.githubusercontent.com/Qiskit/qiskit/2.4.2/qiskit/quantum_info/operators/symplectic/pauli.py)
defines the single-qubit matrices and ordering. The resulting full matrix acts
as Y on global qubit 2, identity on qubit 1 and X on qubit 0. The checker derives
each basis column by flipping bits zero and two, with amplitude `i` or `-i`
depending on the input bit two; it never asks the candidate's equality or
equivalence method whether the answer is correct.

## Value and process boundaries

The protected condition judges logical matrix values and subsystem dimensions.
It permits any correct construction: composing before/after identity, explicit
gates, a tensor product, basis action, a full Pauli label or a sparse representation
converted to Operator. Even a reversed local description—XY placed on `[2, 0]`—
is accepted when it produces the same complete matrix. A fixed no-argument task
does not make a constant correct matrix a shortcut to reject.

The original prompt's use of particular constructors is a process requirement.
This value condition explicitly does not attest Pauli/Operator constructor use
or the candidate's native object provenance. The encoded category is reconstructed
as an Operator by the trusted codec; that is not proof of the candidate's actual
return-object identity. Constructor/process evidence needs its own qualification.

Matrix placement and Operator binding metadata are different. Placement changes
the eight-by-eight matrix and is checked. Returned `Operator.qargs` binding tags
are explicitly ignored by this profile. Storage aliases, writeability, strides,
dtype metadata and byte order are not attested. The existing codec transfers the
logical numeric array and dimensions; the pinned Operator constructor reconstructs
it at complex128 precision. Supported complex64 values widen without a numeric
change. No rounding, matrix correction or canonical-answer substitution is used.
These decisions are public and bound to the named recipe, rather than hidden
transport restrictions. Native object semantics remain a separate track.

The revision reconstructs and verifies each exact original source digest before
creating its new prompt/check. Only the exact ancestor or exact revision is
accepted. Campaign preparation/restoration must use the revision before freezing
requests and judge manifests. All five provider preparation paths contain the
revised public prompt and exclude the exact private checker and canonical answer;
these local inspections make no API request or general disclosure guarantee.

## Evidence and qualification

The [source-bound evidence bundle](artifacts/task41-explicit-subsystems-2026-10-07/README.md)
predeclares 90 host trials: 36 correct alternatives, 50 incorrect values/categories,
and four outside-domain unsupported screens across both suites. All behave as
declared. Independent tensor factors calibrate 16 two-qubit Pauli labels across
all six ordered placements against the SDK: two constructions match the target,
and the other 94 are rejected. All 128 separately altered matrix entries fail.
262 fixed phase samples agree with the independent analytic chord-distance
expectation: four within tolerance pass, and 258 fail. These finite probes do
not exhaust all floating-point implementations.

Both exact pinned checker functions also accept an authored non-Operator object
whose equality method always returns true. That is an observed host false pass
for a wrong return category, preserved separately from the value-codec outcome
`unsupported`. Unsupported encoding is not claimed as a protected oracle failure
or isolated adversarial qualification. No model-generated code executes on the
host in these probes.

The isolated semantic runner predeclares 86 cases (36 pass, 50 fail) and both
judge manifests before execution. The four unsupported screens stay separate.
The isolated test remains gated on an explicit immutable image. Runtime
qualification, adversarial encoder integrity, resource calibration and independent
human contract/oracle admission are pending; the judge is always release-ineligible.
Code and host-evidence AI review do not satisfy human admission. Scores from this
changed-information condition cannot be compared directly with original baselines.

Required next steps are to qualify the isolated semantic roster and resource
behavior once Docker is available, investigate encoder attacks without trusting
candidate self-report, obtain independent admission and freeze a complete admitted
cohort before any headline model campaign. This resolves one family's contract,
not the full 151-family review queue or the overall overhaul.
