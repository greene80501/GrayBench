# Task 113: output type and input dependence

The pinned normal and hard prompts require a PropertySet containing depth before
and after barrier removal, and width, for the supplied circuit. The upstream test
uses one circuit and checks three mapping lookups. It never verifies the required
type or varies the input.

The following authored answer passes both exact upstream checks through the
protected bridge:

```python
def calculate_depth_after_barrier_removal(qc):
    return {"depth_before": 4, "depth_after": 4, "width": 6}
```

It ignores its argument and returns the wrong declared type. This establishes a
false accept, not a model result. The unchanged reference returns a PropertySet
and is currently unsupported by the bridge in both suites. Merely enabling the
reference's return type would not fix the oracle's input coverage or type check.

The four-case source-guarded evidence is retained in
[GrayBench-v3-property-set-oracle-evidence.jsonl](GrayBench-v3-property-set-oracle-evidence.jsonl),
SHA-256 `69c106281ebebe3d51a125b13bb5274165eaae64d15c96d686f73e5b9c870157`.
Its chain completes with no pending invocation. It records original tasks,
authored answers, private checks, actual engine bytes and immutable Docker image.
Reference outcomes are compatibility observations, not assertions that every
reference satisfies its public contract.

An independent local Qiskit 2.4.2 fixture, `H(0); barrier(); H(1)` on two qubits,
has depth 2 before removal and 1 after removal, with width 2. The existing test
instead has depth 4 both before and after removal, with width 6. A revised oracle
needs cases where barrier removal changes depth, cases where it does not, varied
width and classical bits, empty circuits and multiple/disjoint barriers. It must
reject constant dictionaries and constant PropertySets while accepting equivalent
implementations. The PropertySet boundary must preserve its concrete mapping type
and missing-key behavior, not silently convert it to a plain dictionary.

Returned metrics alone cannot prove that no other optimization was performed on
a temporary internal circuit. The public contract must state what observable
behavior is assessed before any stronger track is enabled. No revised track or
task admission is claimed here. The upstream pinned check remains unchanged.

[IBM's RemoveBarriers documentation](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.transpiler.passes.RemoveBarriers)
describes the barrier-removal transformation; this does not justify replacing the
task with unitary-equivalence-only checking, which cannot distinguish barriers.
