# Runtime failures must not count as model mistakes

The previous worker emitted its first ready message only after executing the
candidate module. As a result, a missing/broken worker dependency or a worker
startup hang could be recorded as `candidate_error` or `timeout`. Both outcomes
are included as failures in development accuracy. Docker fault-injection tests
reproduced both misclassifications with a valid candidate answer.

Startup now has three explicit messages:

1. The worker imports the transport code and executes the supplied public prefix,
   then announces `runtime_ready`.
2. The host resets the candidate clock and sends the `start` command.
3. The worker executes the generated module and announces candidate `ready`.

Before the start command, bootstrap exits, invalid startup messages, transport
diagnostic limits and bootstrap timeouts are unscored infrastructure failures.
The bootstrap wait is bounded by the configured timeout separately from the
candidate budget. After authorization, generated syntax errors and initialization
exceptions remain candidate errors, and candidate execution consumes its active
wall-clock allowance. Idle time while the protected judge works remains excluded.
Imports present in the supplied public prefix belong to runtime preparation;
imports written by the model belong to candidate execution.

The host start command prevents candidate code from racing bootstrap
classification. It is not a correctness verdict: candidate messages remain
untrusted and only the separate judge decides pass/fail. A start-channel write
failure leaves execution authorization uncertain and remains unscored.
Failures retain their stage, exception type, timing and bounded observed stderr.
That stderr snapshot is diagnostic evidence, not a promise that every final byte
has been drained from a failing process.

Upstream manifests identify timing as `active-wall-v3-after-runtime-bootstrap`
and startup as `runtime-ready-host-start-candidate-ready-v1`. Successful upstream
and file-semantic judgments report bootstrap time separately. Existing frozen
runs need their original source; this change must not silently resume an older
timing protocol or rewrite historical outcomes.

Regression coverage includes a broken worker, a hung worker, a broken supplied
prefix, generated syntax/initialization failures, and startup plus candidate work
that exceeds a single combined budget but fits each separately. The existing
stdout-forgery, isolation, timeout, freeze/resume and protected bridge tests remain
applicable. This fixes pre-authorization attribution; it does not prove that every
failure after authorization can be attributed to the model, or certify tasks.

Final validation: 342 tests passed with Docker enabled, zero failures/errors/skips,
in 132.52 seconds. Lint and formatting pass. Six protected canonical replays
(tasks 0, 107 and 141 in both suites) also pass. The source-guarded append-only
log is `GrayBench-v3-runtime-bootstrap-reference.jsonl`, SHA-256
`0940d6c0f7a4a106de5e44e88a8c31c7e5069a9d117f9f18f2079a8cce98ec95`.
Actual worktree bytes are retained; Windows line endings may differ from Git
blobs. No hosted generation calls were used. These targeted replays do not
replace the preserved full-suite reference scan or establish task admission.
