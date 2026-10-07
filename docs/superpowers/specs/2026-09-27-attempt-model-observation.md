# Attempt-bound model observations

The existing protocol 3.1 campaign records provider metadata immediately before each
generation request. Its append-only run observations do not associate a particular
attempt with a post-response observation. An answer can therefore be durably returned
while a later metadata change, outage, or crash leaves its model exposure uncertain.

Protocol 3.2 adds an opt-in, append-only pre/post observation binding for every
transport attempt. The runner records the pre-observation before dispatch, binds its
row in the same transaction that claims the attempt, stores the delivery and any
generation immediately after the HTTP exchange, then requests and binds a fresh
post-observation. The attempt must bind the exact pre-observation returned to its
caller; an intervening newer observation aborts dispatch. The delivery transaction
issues an in-memory one-use post token and stores only its digest. A restarted runner
cannot recover this token from the ledger and cannot silently attach a later check.
A rejected or ambiguous delivery also needs a post observation;
retry eligibility never erases evidence from the earlier attempt. An unavailable or
changed post identity remains in the ledger and stops further dispatch. A crash after
delivery but before post-observation leaves an explicit missing-post status and must
not silently recover with a later observation treated as if it were immediate.

The new relational binding has a foreign key to the attempt and observation rows,
a unique pre and post phase for each attempt, an immutable post-token claim, and
exact event-chain row bindings.
Verification checks order and that both observations belong to the same run as the
attempt. A 3.2 summary cannot be complete if any attempt lacks either binding or
if discovery is not stable; judgment scheduling stops before scoring when post
evidence is missing. Protocol 3.1 and prior artifacts retain their original
semantics and must not be retroactively upgraded.

This is provider-reported, time-of-check evidence under a trusted host-runner
threat model. A host operator who saves or leaks the live token can still delay
the post request; timestamps and independent review must assess elapsed time.
It cannot independently attest
model weights, prove the weights were fixed throughout the request, or certify
effective generation settings. Those remain separate release gates.
