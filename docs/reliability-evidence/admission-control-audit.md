# Local admission-control coverage

The protected-track inventory is a durable review checklist for all 302 pinned
normal and hard records. Schema 2 retains the source digest of the engine that
created it but validates task ancestry against the exact pinned parquet bytes,
so an unrelated later engine edit does not erase accumulated task-card work.
Schema 1 keeps its historical current-source validation rule. Neither schema
authenticates its author or makes a card publishable.
Legacy JSON without an explicit version still parses as schema 1.

`admission-control-audit` inspects each supplied authored oracle-review JSONL
file, verifies its event chain and pinned case ancestry, and joins its controls
to the matching cards. The report includes every card, even when it has no
controls. It cites artifact and case digests and records both expected and
actual outcomes. It does not equate one observed pass with correctness or one
observed failure with a sufficient oracle. It cannot prove the logged judge
ran or authenticate an unsigned evidence chain. Requirement mapping, valid
input-domain review, positive alternatives, mutation adequacy and two
independent qualified reviews remain separate obligations.

Using the saved task-0/1 upstream and strengthened task-0 artifacts, the local
report contains 18 controls across 4 cards. The other 298 cards have no controls
from those two files. Eight authored wrong-answer controls unexpectedly pass the
upstream tests; there are no authored correct-control failures or other
mismatches. All six strengthened task-0 controls match expectation. These
artifacts are local outputs outside the PR, so a reader needs the files to
repeat inspection. The inventory and report identities are:

- Schema-2 inventory: `3c924f9a4a09e8fb083a4913df21b1f9dbcab0ae0fd48bcbe76c1efe1ed613ce` (model identity).
- Control audit: `13693c8b931b105e85fb171de3b9207d4ae32eb6ec498afacffad74b01185b5e` (file SHA-256).

Both artifacts and all 302 cards remain `publication_eligible: false`.
