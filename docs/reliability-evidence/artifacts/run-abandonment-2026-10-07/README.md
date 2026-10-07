# Terminal abandonment: offline verification

The [source and test record](verification.json) binds the [full offline JUnit](full-offline.xml)
to engine source `f868915bdbe72c14fe3f8fb0be3e7228cda7be41dfb7b9255775347823d64410`, the exact new test file and lockfile.
The [workflow contract](../../run-abandonment.md) explains operational closure,
its irreversible effect, the worker-stop declaration and verification limits.

Full offline result: **1722 passed, 293 skipped, zero failures/errors**
in 612.166 JUnit seconds. All **31 new abandonment tests** passed.
The run uses Python 3.12.14, locked dependencies and the pinned
QHE cache. Docker image variables were unset; skipped tests and their exact
reasons are retained in the JUnit and summarized in the identity record.
Sixty warnings comprise 48 original Diagonal deprecations and 12 existing
Windows temporary-directory cleanup warnings. No model generation or live
provider request occurred. This run does not qualify container execution.

Six tests launch a fresh Python worker and call `os._exit(73)` without cleanup
after durable dispatch intent, ambiguous delivery, returned answer, judgment
claim, protocol-3.3 return missing its post observation, and committed post
observation missing its timing check. The parent checks that exact terminal
exit code, reopens the same ledger and verifies its record chain. It snapshots
all original attempt/delivery/generation/judgment and observation rows, closes
the run, checks those rows are unchanged, then reopens read-only. These are
fixed authored answers and synthetic metadata, not candidate/model evaluation.
The child executes no provider requests. This tests abrupt process termination
after commits, not arbitrary power loss, kernel failure or hardware durability.

Additional tests cover retained denominators, refused execution writes,
stale plans after another run appends, strict reason/declaration fields,
source-drift protection of completed historical cohorts, exclusive/read-only
CLI planning, missing-ledger refusal, concurrent closure, absent historical
optional tables, immutable records and rehashed contradictory counts.
All five scheduler entry points and direct discovery stop before touching a
transport, setup or oracle that may no longer exist after a process restart.

Code review identified a chronological-stop bypass: unrelated event identifiers
could redirect the closed-run ownership check. Its regression failed before
the fix. Canonical ownership now follows each event kind. Review also reproduced
and prompted refusal of completed archived cohorts whose sole blocker is source
drift. Final bounded review found no important remaining issue. This is software
review, not independent human task admission or a separate-machine reproduction.

Engine lock SHA-256: `b0789c7a994abdd96b3172563ae58a420c60e80c33ba05447257e1d35174524d`.
New test-file SHA-256: `e84826c3eb3592503444ea20c7a2aa7075befc175541f0890465648c47cc363e`.
Full JUnit SHA-256: `89197782cd9a9ad8f35a0e770dfda398edf32723a73dcfb3443aeb991c15583a`.

Reproduce from `engine/` with dependencies installed from `uv.lock`, the exact
pinned task cache and Docker image variables unset:

```text
python -m pytest -q --disable-warnings --tb=short --junitxml=FRESH_OUTPUT.xml
```

Ruff lint and formatting pass for 243 engine source/test files using
`engine/pyproject.toml` from the engine working directory. Existing source-bound
reports and provider ledgers remain unchanged. Completed software checks do not
establish fair effective provider settings, oracle adequacy, independent task
admission, historical summary authenticity, untouched holdouts or publication
eligibility. All abandonment records remain unscored and release-ineligible.
