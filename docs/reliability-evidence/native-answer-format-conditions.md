# Native normal answer-format conditions

The pinned normal prompts contain public imports and a function prefix. The
earlier `raw_or_single_python_fence_v1` policy accepts either a body suffix or
a full replacement function, as the [prompt-format probe](prompt-format-condition-audit.md)
demonstrates. Those are different answer-format conditions even when the same
public prompt is sent to a model. The default remains for historical plans.

The new `exact_prompt_suffix_v1` policy concatenates the exact public prompt
and the raw response, then checks that the result is parseable Python. It does
not infer imports, replace the public prefix, choose a fenced code block, or
repair an answer. A valid suffix may add a top-level import, helper, or even
rebind the entry point, just as ordinary prompt-plus-completion execution
would. A Markdown code fence or malformed concatenation is a candidate format
error. The condition is valid only for normal function-completion tasks; the
shared campaign planner rejects hard or mixed cohorts with this policy.
Even an empty or whitespace-only response is concatenated and sent to the
native judge if the resulting source parses; the pinned test determines its
outcome. This preserves literal assembly instead of assigning a special
pre-test answer status.

Local controls loaded the exact pinned normal parquet and confirmed that all
151 canonical suffixes fit this policy. A pinned-image task-4 native execution
passed its canonical suffix. A raw appended replacement function reached the
pinned test and failed on its value; no code was stripped or selected. The
cohort and protocol bind the policy, the
plan/create output and ledger summary show it, and paired comparisons reject
a policy mismatch. An appended top-level helper and an indirect entry-point
rebinding remain syntactically valid; this is not a code-integrity filter. A
response with an unpaired Unicode surrogate was recorded as a
candidate format error with a disclosed surrogate-pass digest encoding, rather
than interrupting judgment. These tests exercise extraction and one native judgment;
they do not prove all 151 pinned tests or model answers are correct.

The condition does not prove that a hosted provider presented a literal
completion interface to its model. GrayBench still sends the exact public
prompt through the selected adapter; a chat endpoint may render it according
to an unknown internal template. Appended code can mutate global state at
runtime; this is an assembly rule, not a security sandbox. The native
same-process test-integrity limit
and task-admission blockers remain. No result under either answer-format
condition is publication eligible yet, and neither may be asserted equivalent
to an external score without a matching published prompt, parser, model,
runtime, and denominator.

A separate authored task-4 replacement returning `None` reached the pinned
test, where Qiskit raised `QiskitError` while converting the candidate value.
The current native worker classified that non-assertion test exception as
`infrastructure_error`, conservatively blocking a score rather than counting
it as an ordinary wrong answer. Native release work still needs reference
preflight and an exception-attribution policy that distinguishes candidate
errors from a broken or unstable test without silently changing denominators.

Local engine verification on 2026-09-27: `pytest tests -q --disable-warnings`
with the pinned QHE cache and image completed with 1,256 passed, 5 skipped,
and 6 expected failures in 593.79 seconds. Ruff checks and formatting checks
also passed. GitHub Actions workflows were disabled because GitHub-hosted jobs
failed before runner steps began, so this change has no hosted CI result.
