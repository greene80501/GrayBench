# Protected graph protocol4: first end-to-end integration

Protocol4 now runs through the actual candidate container, host relay and separate
trusted upstream-test container. graph_worker.py and upstream_graph_process.py use
one persistent anchor-enabled GraphArena each. graph_runtime.py stages an explicit
23-module package, and graph_rpc.py defines closed call-root and basic exception
schemas. The host forwards bounded JSON envelopes and never reconstructs candidate
graph objects. Candidate output remains data, never a judgment.

Both processes capture the fixed public anchor registry before executing user/test
code. The host checks the candidate bootstrap manifest before authorizing candidate
execution. Each attempt receives a fresh random session token; it is independent
of private test contents. The frozen configuration identity stays stable across
attempts, while evidence records the token and actual runtime task-payload digest.

Calls carry args/kwargs in one graph. Responses carry those same argument roots,
result, exception_args and every previously exported object. Root identity, root
kinds, keyword keys, protocol/session/sequence, schema and graph constraints are
checked before live commit. Returned inputs resolve to original judge objects;
state retained from an earlier call remains synchronized even when omitted from
later call arguments.

Nine fixed builtin exception classes can carry their argument tuple, including
references to mutated inputs. State is committed before the trusted proxy raises
that admitted exception, allowing normal test try/except behavior. Custom classes,
instance metadata, causes, contexts and suppressed contexts are explicitly
unsupported. Traceback/frame transfer and exception-instance identity are not
provided by this basic value-exception contract; broader exception admission
remains required where tests depend on them.

Adversarial tests exposed a false-pass risk during implementation: a test catching
BaseException could swallow a bridge failure and then pass. The trusted proxy now
retains a fatal failure marker and overrides judgment even if test code catches
that failure. Malformed roots, foreign sessions, stale sequence, extra fields,
protocol downgrade, unsupported exception metadata and execution timeout cannot
be converted into a successful judgment this way. These failures remain distinct
from legitimate candidate value-exceptions.

Protected tests also cover normal-suite public prefixes, candidate global changes
after bootstrap, circuit-only singleton mutation, exclusion of private tests and
references from candidate files, bootstrap mismatch before authorization, container
pausing/idle-time exclusion and discard-result finalization before state capture.
A one-second timeout fixture first failed during Qiskit bootstrap, correctly
classified as infrastructure before candidate authorization; with four seconds
for startup, its infinite candidate body produces the intended execution timeout.

The six preserved identity fixtures run natively and through real protected Docker
calls. Expected outcomes are five passes and one failure of the deliberately wrong
identity implementation. This is fixture calibration, not a model benchmark score.
The evidence runner verifies configuration source hashes against the executing
checkout and preserves complete call/response transcripts, image, fixture/probe
hashes, runtime timing and task/completion identities. Explicit staging copies these
source files; these hashes are not a separate container attestation mechanism.

Use the new path explicitly:

- Python: UpstreamJudge(..., protocol=4).
- Reference calibration: reference-scan ... --bridge-protocol 4.
- Frozen development campaign: campaign-plan ... --evaluation-recipe upstream-graph-v4.

Recipe/configuration identities distinguish protocol4 from the historical v3 path.
Changing a frozen setup to v3 fails cohort validation; no protocol4 operation falls
back to v3. The current legacy default is retained during development, and its known
identity defects remain recorded. It must not be treated as certified evaluation.
The graph path is now integrated, but full normal/hard reference admission, remaining
object interfaces, further adversarial coverage, provider calibration/reproducibility
and the final whole-plan review remain open. No model API generations were used.

Final validation of this source: 825 Docker-enabled tests passed in 520.24 seconds,
with zero failures, errors or skips in the JUnit report. Ruff lint and format checks
pass for all 124 selected files. The earlier 821-test run preceded the final session
and bootstrap refinements and is retained as intermediate evidence only.

Preserved six-case raw evidence:
`GrayBench-v4-protected-identity-final-evidence.jsonl`, SHA256
`c870ba1a65be55f27d1ec30aef9d2b82b7b9ef33cf515855c942e25c10374b8f`.

The first pinned reference replay covers tasks50,63,72,73,147 in both suites.
Tasks50,73,147 pass in each suite; tasks63,72 are unsupported because their
mutated circuits contain retained Python operation types without admitted codecs.
The ten-case scan is complete and its event chain verifies. Raw evidence:
`GrayBench-v4-protected-targeted-reference.jsonl`, SHA256
`64cb094d4525c7961220774236346b0632ac7f496a0626c8379490d5fb696f72`.
This is not an aggregate normal/hard score. The separate full offline scan is now
complete: see [the baseline report](reference-scan-3ed07d2.md) for its verified
80 passes, 62 unsupported cases and one infrastructure error per suite, including
explicit comparison with the previous v3 baseline. These are reference compatibility
counts, not task admission or model accuracy.

Task63 also seeds NumPy only inside its private test process. Resolving its codec
gap will not authorize transferring that private RNG state into the candidate.
Task72 requires nested IfElseOp circuit state. These remaining interfaces require
native differential evidence, not circuit simplification or value-only fallback.
