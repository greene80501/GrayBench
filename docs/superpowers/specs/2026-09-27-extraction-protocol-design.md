# Versioned code extraction design

## Purpose and scope

The Qiskit HumanEval normal prompt supplies a code prefix; hard supplies a
natural-language task. A real local pilot returned a function, an example
call, and a diagram in separate fences for hard task 0. The current frozen
`raw_or_single_python_fence_v1` rule rejected the response before execution.
That is an honest result under v1, but a strict format rule may change model
rankings. We need a separately labeled sensitivity condition, not a
retrospective replacement of that attempt or a claim that one parser is
universally fair.

## Policy

Keep v1 byte-for-byte in behavior. Add `unique_entrypoint_fence_v2`, selected
before generation in `Protocol.extraction` and exposed by `campaign-plan`.
UTF-8-encodable no-fence and single-fence responses retain v1 behavior;
unencodable text is a candidate format rejection under v2. For two or more
fences, require complete, line-delimited, paired triple-backtick fences; any
unmatched delimiter rejects the response. The multi-block v2 parser accepts
LF or CRLF closing lines without changing v1's historical fence behavior.
Eligible fence languages are
`python`, `py`, or blank. Exactly one eligible block must parse as Python and
contain exactly one top-level `def` or `async def` whose name equals the
public `entry_point`. A block with two such definitions, a second block that
binds the entry point at module scope (including assignment or import), or a syntactically
invalid eligible block starting a definition/assignment of the entry point
makes the response ambiguous and rejects it. A top-level definition or
assignment of the entry point outside the fences also rejects it. The chosen
block is executed in full; other blocks are not executed. No test, reference,
model identity, code repair, helper insertion, or fallback selects a block.
Comprehension and lambda-local bindings do not count as module replacements;
an executed class-body `global` assignment does. A wildcard import in an
eligible block rejects because its bindings cannot be known without loading
the module.
The normal suite receives only its existing public import prefix when the
chosen block contains the full function; the hard suite receives no prefix.

This fixed rule can discard a helper block or ignore an example call. Those
effects must be reported; v2 is a distinct development condition until
representation controls and task admission establish suitability. Formatting
failures remain failures in the frozen first-answer denominator. A model is
not offered v2 after seeing its v1 failures, and the preserved pilot is not
rescored into a new benchmark result.

## Binding and evidence

`campaign-plan` freezes the extraction name in the protocol. The actual
judge receives that name, includes it in its configuration digest, and
rejects a cohort whose declared name differs from the executable judge.
Protected judgments record the selected method and extracted-code hash or
the deterministic rejection reason. Resume and comparison use the existing
protocol and judge digests; unlike-version cohorts cannot be silently pooled.
The source manifest binds extractor, planning, validation, and metric code.

## Controls and limits

Before a live v2 campaign, test raw code, single-fence bodies, a unique
function plus example and diagram, duplicate solutions, duplicate definitions
in one block, unmatched/nested fences, malformed alternative entry-point
blocks, and hard-suite missing imports. Verify a swapped extraction name
stops before generation, even if a caller tries to supply a v1 judge.
Reference execution and adversarial fixtures test the chosen code without
inferring correctness from the pilot. Full normal/hard task admission and
provider identity remain separate release gates.
