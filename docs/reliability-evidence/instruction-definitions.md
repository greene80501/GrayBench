# Instruction and definition transport

Circuit wire v5 adds plain Qiskit Gate/Instruction definitions without flattening,
decomposition or optimization. The constructor is selected from a fixed two-class
registry, never from a candidate-provided Python symbol or gate name. A plain gate
named `h` therefore retains its submitted definition instead of becoming a standard
Hadamard gate. Names, labels, dimensions, symbolic parameters and nested definitions
are carried explicitly. Standalone supported standard instructions retain mutability.

Circuit names and bounded JSON metadata now survive transport, including inside
definitions. Non-JSON metadata types, nonstring keys and nonfinite values are
rejected rather than coerced or discarded. JSON metadata is limited to64KiB,
10,000 visited values and16 nesting levels. The definition graph has a shared
one-million-operation budget and maximum codec recursion depth8. Existing byte,
matrix and container limits still apply. Unsupported interfaces remain unscored.

The raw circuit tag changes from v4 to v5; old wire evidence requires its original
engine. No stored scan, ledger or model answer is migrated in place. The new
instruction codec is copied to candidate/parser/judge containers as needed and its
source participates in their manifests. It contains data codecs, not private tests.

Targeted real reference checks pass tasks78,91,112,125 and145 in both suites. The
exclusive `GrayBench-v3-instruction-reference.jsonl` artifact has SHA-256
`67fec38d7804507124a8980bf8fb6fe46f3772e617062fa61c9209d8ba6459de`.
These are compatibility results, not oracle admission or model scores. The replay
precedes the final standalone cached-definition guard and retains that source identity.

Customized standalone standard definitions are explicitly unsupported. Ordinary
caches are accepted only if their definition and metadata match the fixed constructor.
Generated cache names and lazy-cache state are not claimed to be preserved. Specialized instruction subclasses, control flow, complete
standard-gate cache fidelity inside circuits, aliases and arbitrary metadata still
require work. Plain Gate/Instruction support must not be interpreted as support for
every subclass or every introspectable attribute.

Tests cover nested parameter binding and operator equivalence, classical-bit
definitions, gate-name collisions, recursive/malformed definitions, stable standard
instruction exchange and mutability, metadata type preservation, and the explicit
customized-definition restriction. The candidate file allowlist includes only the new
codec alongside the existing worker codecs; tests and credentials remain absent.

A later replay with the standard-cache validation also passes all ten cases in
`GrayBench-v3-instruction-reference-final.jsonl`, SHA-256
`97eb2247987d8131d40db0dee417bea1720edf0d4aab7ab49fc8ece3457d4563`.
It precedes only the final malformed-record and empty-name decoder checks.

Final validation:292 tests pass with Docker enabled, zero failures/errors/skips.
The final test report is GrayBench-v3-instruction-wire-release-check-tests.xml;
its filename refers to code verification, not benchmark publication admission.
Earlier failed reports remain preserved. Ruff lint/format and the credential-value
scan pass. No model API generations were made.
