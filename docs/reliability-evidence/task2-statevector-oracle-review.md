# Task 2: native oracle trusts the returned object's `equiv` method

The pinned normal prompt requests a Phi-plus Bell `Statevector` and annotates
the return type as `Statevector`. The pinned hard prompt requests the same
statevector from a no-argument function. Both upstream tests call the returned
object's `equiv(solution)` method. They do not verify that the object is a
statevector or that its amplitudes describe Phi-plus. Qiskit's documented
[`Statevector.equiv`](https://docs.quantum.ibm.com/api/qiskit/qiskit.quantum_info.Statevector)
compares states up to global phase; calling an arbitrary returned object's
method does not establish that comparison.

The [reproducible native probe](task2_native_oracle_probe.py) loads both pinned
dataset files through `graybench.datasets.load_suite`, so their SHA-256 pins
and all 151 task IDs are checked. It executes the exact pinned task-2 test
with seven safe, authored return values per suite under Python 3.12 and
Qiskit 2.4.2. The results are in the
[machine-readable record](GrayBench-task2-native-oracle-probe.json), SHA-256
`28bd1a9adadb42c1c8fde25378b9799256809ec981a318b6b00f29d63b85f5e2`.
The record binds the script hash and each public/judge task digest; it contains
no model response.

| Authored return | Normal | Hard | Public contract |
| --- | --- | --- | --- |
| Pinned Bell amplitudes | Pass | Pass | Valid |
| H/CX circuit-derived `Statevector` | Pass | Pass | Valid |
| Same state with global phase `i` | Pass | Pass | Valid |
| Phi-minus state | Reject | Reject | Invalid |
| Product state `|00⟩` | Reject | Reject | Invalid |
| Plain object whose `equiv` always returns `True` | **Pass** | **Pass** | Invalid |
| `Statevector` subclass containing `|01⟩` whose `equiv` always returns `True` | **Pass** | **Pass** | Invalid |

The subclass is an `isinstance(..., Statevector)`, yet constructing a trusted
base `Statevector` from its amplitudes shows it is not equivalent to Phi-plus.
A simple type check would therefore leave the second false acceptance intact.
This is a **native upstream-oracle defect**, reproduced without model generation.
The protected bridge might reject or transform these particular objects before
the upstream assertion; this probe does not claim a protected false pass.

A separately versioned strengthened task should preserve the public request
and compare observable amplitudes through a trusted base `Statevector`, while
accepting global phase and noncanonical valid constructions. Its exact type,
representation and tolerance policy needs positive alternatives, adverse
mutants and protected Docker validation before admission. The upstream tests
and historical scores remain unchanged. Task 2 stays release-ineligible.
