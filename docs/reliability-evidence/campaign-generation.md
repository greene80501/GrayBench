# Durable generation component

GenerationRunner.step() connects the frozen protocol, prepared requests, single-attempt HTTP
transport and append-only ledger. It performs at most one dispatch per call; a caller may exit
on a deferred result and resume later. It never sleeps through an implicit retry loop.

Each step checks current engine source identity, transport model/endpoint identity and every
prepared request digest before dispatch. The ledger verifies artifact hashes and its event chain.
Dispatch intent commits before network access; a process interruption leaves a pending attempt.
Pending or ambiguous deliveries stop further campaign dispatch. A returned empty answer remains
an answer. A permanent rejection stops retries. Rejected transient responses may retry only after
the frozen delay and within the frozen attempt limit, using the same public request.

The transaction enforcing begin_attempt now checks elapsed backoff itself, preventing a caller
from bypassing the scheduler. Restart tests reopen SQLite and verify the same deferred state,
then advance the controlled clock and confirm identical request bytes on the allowed retry.
Additional tests cover timeout ambiguity, process interruption, source drift, empty responses
and permanent errors. Tests use a mock HTTP transport and incur no provider charges.

This component does not certify task eligibility or execute judgments. Required next work is a
frozen campaign admission manifest, validated dataset/runtime/judge binding, judge scheduling,
model identity/capability observations, command-line orchestration and complete paired reporting.
Backoff currently follows protocol delays; a separately specified Retry-After policy and clock
integrity requirements must be resolved before production campaigns. No release score is certified.
