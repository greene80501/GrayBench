# Pinned normal and hard test execution shapes

The [static AST inventory](qhe_test_shape_inventory.py) parsed every test in
the pinned normal and hard Qiskit HumanEval files, with no candidate code or
model call. All 151 normal tests have exactly one top-level
`check(candidate)` definition, at least one assertion in that function, and
no top-level `check(...)` call. All 151 hard tests have the same definition
and exactly one top-level `check(<declared entry point>)` call. Apart from
imports, that definition, and the hard call, neither suite has other
top-level statements. Assertion-site counts range from one to eleven in
each suite.

The [saved inventory](GrayBench-qhe-test-shape-inventory.json) has SHA-256
`ae6bcd65de5e1eccc8952b1ec472c31ad06120351c23ee3cc4ecca9e82114db0`.
It binds the script, pinned dataset revisions, suite digests, and a digest of
every task's test shape and source identity. Both suites report 151 expected
shapes and zero anomalies. The inventory is reproducible from the pinned
files and fails if a future file has a nonstandard shape. Seven synthetic
positive and negative shapes also matched their predeclared classifications,
including missing, extra, and wrong-target calls and an extra top-level
assignment.

This supports a native-runner preflight for **these pinned revisions**:
execute the normal test source and invoke its `check` exactly once; execute
the hard test source with its own single call and do not call it again. The
test source need not be rewritten to remove a call, as the current protected
proxy does. Unexpected shapes should stop before scoring. This static result
does not prove that canonical answers pass, that test assertions capture the
public requirement, or that same-process candidate code cannot inspect or
tamper with a test. It is execution-shape evidence, not task admission or a
benchmark score.
