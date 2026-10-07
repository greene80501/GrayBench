# Task 114: physical-qubit identities and graph fidelity

Both pinned public prompts require an initial directed chain on qubits 0–5,
an added edge (5, 6), and the addition of physical qubit 7. The upstream checks
compare the edge set and require eight physical qubits, without checking their
identities. An authored map with physical qubits `{0,1,2,3,4,5,6,8}` and the
requested edges passes both suites. It omits the required qubit 7.

The [validated exact-test diagnostic](GrayBench-v3-coupling-diagnostic-validated.json)
records the pinned tasks, authored fixtures, worker source, immutable image and
outputs from Qiskit 2.4.2 / rustworkx 0.18.1. Both references pass, both wrong-node
fixtures pass, and both reversed-edge controls fail. This is a trusted-fixture
diagnostic in a restricted container, not the protected candidate/judge pipeline.
It must never become an execution route for model answers. No model API was called.

An initial local diagnostic forgot to invoke normal-suite `check`, which that
dataset defines without a top-level call. The reversed-edge control exposed the
mistake. The corrected diagnostic explicitly invokes the normal check; hard
already invokes it in its pinned source. The earlier failed diagnostic remains
in local outputs and is not used as evidence of normal-suite outcomes.

## Why topology alone is insufficient for transport

The same validated diagnostic exercises graph mutation after serialization. Build
a five-node PyDiGraph, remove nodes 3 then 1, serialize with `__getstate__`, and
restore with `__setstate__`. Both graphs have nodes 0, 2 and 4, but the next
`add_node` returns 1 in the original and 3 in the restored graph. Standard graph
state serialization therefore does not establish equivalent future behavior.

CouplingMap also has cached qubit lists, size, symmetry and distance data. Clearing
or recomputing those caches can change observable results if the exposed graph
was mutated directly. A local installed-SDK probe cached distance(0,2)=2 on a
three-node chain, then directly added edge(0,2); the original still returned 2,
while rebuilding from its edges returned 1. This secondary observation motivates
preserving or rejecting inconsistent cache state, not silently repairing it.

A codec must account for node/edge identities, ordered data and parallel edges,
graph options, mutation behavior, metadata and caches, under explicit allocation
limits. Simple edge-list reconstruction is insufficient. These issues remain
open; no CouplingMap support or task admission is claimed by this review.

A stronger task-114 contract check must verify the required node set as well as
directed edges. It must not impose incidental node payloads or operation ordering
unless those are part of the declared public requirement. Historical upstream
checks remain unchanged.

[IBM's CouplingMap documentation](https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.4/qiskit.transpiler.CouplingMap)
describes physical-qubit nodes and directed coupling edges. The cited page is
version 1.4; the concrete observations above come from the pinned 2.4.2 runtime.

Validated diagnostic SHA-256:
`c34355eeeb1299f80a794ee0f6223825fce70a972702ac32df3cf3f4f0a7e0b8`.
