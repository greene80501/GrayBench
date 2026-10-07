# Barrier state across protected calls

Barrier objects are now an explicit fixed InstructionCodec class. Retained Python
barriers preserve their actual dictionary, parameter list and label separately from
the labels cached in each CircuitInstruction. Two circuits can retain the same
Barrier while caching different insertion-time labels.

Native packed barriers, such as those in efficient_su2, have different behavior:
accessing separate instruction wrappers yields distinct Barrier objects. Their
closed descriptor records intrinsic width, operands and label. Reconstruction uses
a private, single-barrier circuit and Qiskit's native DAG conversion to remove the
Python operation cache, then remaps operands. It does not convert the transported
circuit as a whole or invent a persistent wrapper. A separately exported wrapper
remains detached from the packed instruction.

The native representation and constructor cache behavior are supported by the
[pinned Qiskit 2.4.2 source](https://github.com/Qiskit/qiskit/blob/2.4.2/crates/circuit/src/circuit_instruction.rs).
Native probes verify wrapper behavior after remapping and appending; tests cover
retained aliases, cached labels, detached wrappers, zero-width barriers, Unicode
labels, operand order, compiled ansatz parameters, malformed descriptors rejected
before mutation, and measure_all through the actual protected boundary.

The original three regressions failed with unsupported Barrier errors before the
implementation. The focused barrier/instruction run then passed all 31 tests.
The first Docker-enabled run finished with 833 passes and two failures in existing
four-second graph startup fixtures. Both failed during bootstrap, before candidate
authorization. The fixtures now use 15 seconds, with the paused-idle interval also
increased beyond that budget; production limits were not changed. The final full run
including the exception-hardening regressions passed all 840 tests in 403.70 seconds,
with zero failures, errors or skips in the verified JUnit report.

The source-guarded 18-case reference replay is complete. Both normal and hard have
the same outcomes: tasks9,52,64 pass; tasks3,4,5,6,51 are unsupported; task63 fails
its assertion. Task3 now reaches its Figure return, while tasks4,5,6,51 still need
UnitaryGate, StatePreparation or IfElseOp support. Task63 reaches its private
assertion after mutation transfer, but its private-only NumPy seeding remains a
separate oracle/environment issue. No private RNG state was transferred.

Raw evidence: `GrayBench-v4-barrier-targeted-reference.jsonl`, SHA256
`e96454572e21205fbdea959f2420e021c8dda42a188449e5fa6c72156cee7adf`.
This targeted replay is not a new full-cohort aggregate or a model score. It is
separate from the earlier complete/ongoing protocol4 baseline and prior v3 evidence.
The implementation was developed in an isolated worktree so the baseline runtime
source stayed unchanged. The [completed baseline](reference-scan-3ed07d2.md) remains
separate from this targeted replay. Broader object admission, oracle review and
benchmark release requirements remain open.

## Unexpected bridge exceptions

Fault injection exposed another false-pass path: unexpected exceptions from graph
snapshot, preparation or commit could escape the proxy, be caught by private test
code, and result in a pass. The before-fix raw probe is preserved as
`GrayBench-v4-unexpected-bridge-error-before.jsonl`, SHA256
`14339e32539a6680f60577714b48bdb7eb25e16c14513bfc787f56569ac642b0`.

The proxy now distinguishes reconstructed candidate exceptions by identity. Every
other unexpected exception records a fatal infrastructure marker before diagnostic
formatting. Even a broken exception __str__ cannot erase it. Four fault-injection
regressions failed before the fix and pass after it. A positive regression confirms
that candidate RuntimeError arguments retain input identity and mutation, remain
catchable, and allow a subsequent call. These five tests and the two corrected
timing fixtures passed together: seven passed in 49.66 seconds. The final 840-test
run includes all these cases. This does not establish whole-cohort admission.

The identical source-bound fault fixture now records infrastructure_error instead
of pass. Before/after task identities match. After-fix raw evidence:
`GrayBench-v4-unexpected-bridge-error-after.jsonl`, SHA256
`28eeb2c8675f50b7502fe893a6f9e279b76ed92bfa52ceffd498bc961af28c59`.
