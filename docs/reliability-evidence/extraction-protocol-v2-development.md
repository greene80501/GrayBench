# Versioned multi-block extraction (development condition)

The [original Qiskit HumanEval dataset](https://github.com/qiskit-community/qiskit-human-eval)
gives normal prompts imports and a function prefix; hard supplies a problem
statement and asks for a function. A local
two-slot Ollama pilot on task 0 showed why answer packaging matters: its hard
response contained a Python function block, a separate Python example-call
block, and an unlabeled diagram block. The frozen
`raw_or_single_python_fence_v1` policy returned `candidate_error` before
executing code. That result and its ledger remain unchanged; see the
[local pilot](compatible-provider-local-pilot.md).

`unique_entrypoint_fence_v2` is a **separate development condition**. An
operator chooses it with `campaign-plan --extraction` before any generation.
UTF-8-encodable raw and single-fence answers retain v1 behavior; v2 rejects
unencodable text as a candidate format error. A multi-fence answer must
have complete line-delimited fences. The extractor accepts a block only when
it is Python or unlabeled, parses, and contains the sole top-level definition
of the public entry point. Another block or statement that binds the same
name, a duplicate definition, a wildcard import whose bindings are unknown,
or an unmatched delimiter rejects the answer. Comprehension loop variables,
lambda-local assignments and class-local attributes do not replace the module
entry point; an executed class-body `global` assignment does.
Multi-block v2 accepts LF and CRLF fence lines; v1 remains unchanged.
The selected block executes in full; examples and diagrams in other blocks
are not executed. Selection never reads a private test, reference answer, or
model identity, and never tries candidates until one passes. The hard prompt
receives no missing imports. The policy name, judge manifest/digest,
extraction method and resulting code hash are retained for audit.

This rule can discard a separate helper block and can ignore example code.
It should be compared as a formatting-sensitivity condition, not promoted as
the one fair parser. Any first-answer denominator still includes formatting
failures. Cross-policy cohorts must not be pooled as though the judgment
contract were identical. The old pilot is **not rescored** under v2. A
read-only extraction probe on its saved hard response observed the v1
rejection and a v2 selection of a 323-byte function block with SHA-256
`4cd72fee31cb1a8cecb1489faeb6dd774f3999f80b5a078eaad4a9f37c10058a`;
it did not run that code or produce a new outcome.

Focused controls cover unique function plus example/diagram, duplicate
definitions, competing blocks, assignment alternatives, module versus local
scope, wildcard imports, malformed code and fences, LF/CRLF multi-block
formats, unencodable text, raw/single-fence behavior, and no hard-suite import
help. A read-only differential probe compared 24 normal/hard v1 cases against
the extractor from the prior commit and matched code, method, public prefix
and error in every case. The Docker-backed protected judge accepted authored
multi-block functions in both suites, rejected an unimported hard dependency,
and kept the v1 format rejection. Planning tests confirmed distinct judge
digests and rejection of a forged extraction label before dispatch.

The first broader targeted run passed 89 tests with four expected skips.
Independent read-only review reproduced parser and scope errors; each was
covered with a failing regression before correction. Final review reported no
remaining Critical or Important finding against this v2 policy. The complete
Python 3.12 suite on pinned candidate/oracle image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`
and parser image
`sha256:731a7ed19488145b2a0ba0d7efbb4528d13cc6466ca3ba114254bb5ab4782ae9`
passed **1,083 tests, one expected experimental-image skip, zero failures and
errors** in 651.93 seconds. The source manifest digest was
`44f58a486d2ac4d735a5dd085fe0508c9598e8d9e1b243c0019277d53d11a160`.
The external JUnit report
`work/outputs/GrayBench-v4-extraction-policy-release-tests.xml` has SHA-256
`082b676b4d89b0915bc9b8390ae72aae16ac326cf5b704b9c4ab44c8865aa7d9`.

All of these are interface controls, not task admission, model accuracy, or
proof that v2 is unbiased across models. See the
[design](../superpowers/specs/2026-09-27-extraction-protocol-design.md) and
[implementation plan](../superpowers/plans/2026-09-27-extraction-protocol.md)
for the predeclared scope and adverse cases.
