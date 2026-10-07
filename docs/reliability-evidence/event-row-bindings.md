# Event-to-record integrity

New ledger events include exact records for runs, execution contexts, model
observations, dispatch attempts, deliveries, generations, judgments and judgment
claims. In particular, returned-generation content hashes, HTTP statuses, attempt
ordinals and stored timestamps now participate in the event payload digest.
Previously an event could state that delivery finished without binding the saved
answer's contents.

Verification compares the bound records with current database rows and requires
each row in those tables to appear exactly once in its appropriate event. It also
checks run-before-dispatch, dispatch-before-delivery, return-before-judgment and
claim-before-judgment ordering. Attempts must match frozen sample/request identity,
consecutive retry ordinals, retry limits, eligible prior rejection and backoff.
Pending claims and pending deliveries remain valid incomplete states.

Standalone verification and summaries both use a single SQLite snapshot. Hash,
event-chain and foreign-key checks remain in place. Sample schedule completeness
is checked separately by the summary; the row-binding table list is explicit in
verification output. This is not an externally signed history and cannot prevent
a malicious database owner from replacing an entire internally consistent run.
External anchors and stronger provenance admission remain required.

Existing ledgers are not silently rewritten. Events without exact row bindings
produce a legacy-format error in this engine. Inspect them with their original
source environment. Missing historical bindings cannot be reconstructed and
presented as original attestations. This deliberately supersedes the earlier
summary-only compatibility behavior for such ledgers.

Adversarial tests replace an answer with a different valid-hash blob, insert an
unrecorded pass, duplicate a scoring event, reorder and rehash scoring before
delivery, remove row bindings from a rehashed log, and change a delivery timestamp.
Each case is rejected. Existing interrupted-delivery, retry, claim, observation and
concurrent-summary tests continue to exercise normal lifecycle behavior.

Validation:260 tests pass with Docker checks enabled, zero failures/errors/skips;
Ruff lint/format and the credential-value diff scan pass. No model API calls were
made for this change.
