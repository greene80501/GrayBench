# DAG investigation (no codec admitted)

The ongoing complete reference scan confirms missing DAGCircuit interfaces on
normal tasks26 and27. Their current oracles use type, qubit count, depth, operation
counts, descendants and statevector equivalence. Supporting only those assertions
would not establish a faithful general DAG bridge.

Pinned Qiskit2.4.2 native probes show op_nodes returns fresh equal node wrappers.
DAG qubits/clbits lists and qregs/cregs/metadata dictionaries are stable getters.
The native state exposes fresh qubit/clbit lists, live register/metadata maps,
node IDs, removed-node gaps and edge slots (including None for removed edges).
Calling __setstate__ on an already populated object raises duplicate-bit mapping
errors; it is not a general in-place transition operation.

Most importantly, native state reconstruction can change future node allocation.
Starting from X,H,Z on one qubit, removing original operations0 then2 yields next
node ID4 in the original and a native copy, but ID2 after state reconstruction.
Removing2 then0 yields ID2 in all three. The public state therefore does not by
itself preserve allocator history, even when current nodes and edges match.

Reproducer: dag_native_probe.py. Recorded observations:
GrayBench-native-dag-allocator.json. The file includes Python3.12.14,
Qiskit2.4.2 and the probe source hash. These are native semantics observations,
not model evaluations. The probe uses state reconstruction only inside a local
controlled experiment; no such decoder has been admitted to the benchmark.

A future codec must account for node/edge allocator behavior, cached child aliases,
retained operation state, fresh wrappers, validation of graph connectivity and
bounded private reconstruction before live mutation. It cannot just convert the
DAG to a circuit or invoke native state reconstruction on arbitrary payloads.
Read-only probes ran during the source-guarded reference scan without modifying
any evaluator source. The completed scan records both DAG tasks as unsupported in both suites; see
reference-scan-38db7fa.md.
