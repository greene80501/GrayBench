# Bounded model-observation timing

Protocol 3.2 binds provider-reported metadata before and after each transport
attempt, but a live host process can retain its one-use post token and delay the
post request indefinitely. A late matching observation must not be reported as
timely exposure evidence. Prior 3.1 and 3.2 runs retain their original meaning.

Protocol 3.3 retains the 3.2 append-only bindings and freezes one timing policy
in its manifest: the maximum age of the pre-observation at recorded attempt
start and immediately after the dispatch-intent commit, and the maximum delay
from the host's delivery-receipt timestamp to the post observation and its
post-commit confirmation.
Defaults for new 3.3 development setups are 30 and 120 seconds,
respectively. An operator may predeclare different bounds before generation;
the exact values are included in the protocol identity. Paired comparisons
require the same protocol version and timing policy. A 3.3 setup cannot omit
the policy; earlier versions cannot silently acquire one.

The host rejects dispatch if its exact pre-observation is too old, in the
future, or superseded. If the dispatch-intent commit itself exhausts the bound,
the attempt remains durably unresolved with a bound abort event and no network
dispatch. A delayed post observation is still durably recorded
and bound to the attempt; it makes the observation status a timing violation,
stops further dispatch and judgment, and blocks a complete score. An
unfinished delivery retains its distinct unresolved status. A crash after
post binding but before post-commit confirmation leaves a separate unscored
missing-check state. The ledger reports the measured pre/start, start/finish,
finish/post, finish/confirmation and post/confirmation gaps and which attempts
violate the frozen bounds. The delivery-receipt timestamp is captured before
evidence serialization and database persistence; this conservatively includes
their delay in the post-observation gap. The post-observation timestamp is
captured after metadata retrieval and before its database commit. A separate
append-only event binds a post-commit timestamp; both must pass the frozen
delay bound. These are host samples, not exact durability or network-wire
timestamps. A backwards
jump across these recorded intervals is a timing violation. UTC wall-clock
timestamps are not independent clock attestation. Provider metadata is
self-reported, so compliant timing does not prove fixed weights, routing, or
effective settings during generation. Timing failures affect run coverage,
not the candidate's correctness label.
