# Current-source protected admission successor

GrayBench must distinguish locally verified controls executed under a frozen
inventory source from valid historical observations. The task-62 exhaustive
admission bundle currently binds 42 protected controls, but only 18 share its
engine source. Replaying tasks 2, 20 and 62 under one source can remove this
particular provenance gap without asserting that their oracles are adequate or
that any task is admitted.

Build an append-only successor to
`admission-task62-exhaustive-2026-09-28`. Keep its two upstream task-0/1 logs
byte-identical. Replace its task-2/20 and task-62 protected logs with the two
predeclared normal/hard replays under pinned image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`.
The task-2/20 log has 24 of 24 matching outcomes (12 passes and 12 failures);
the task-62 exhaustive-v2 log has 18 of 18 (six passes and 12 failures).
Both logs' source identity is
`1515370b867b0160d6da999ac908912ae24337aa60746a7f705cb83dd176a748`.
The task-62 omitted-input mutant must fail at only
`width-4-state-1000-basis-0000` among all 1,364 frozen cases in each suite.

A deterministic builder must verify the predecessor bundle and both new logs,
reconstruct all six exact judge manifests from pinned source tasks, and check
that every predeclared candidate case still matches the card's requirement
links. It advances the inventory's source digest and updates each card's judge
digest only when its exact manifest changed, while
preserving every other card field, all current known findings and the old
requirement identities. It then writes an exclusive byte-pinned successor with
the recomputed schema-5 audit. A second build from the same inputs must produce
identical pinned files. The verifier must report 60 total controls, 42 bound to
declared judges, all 42 matching the inventory source, eight historical
upstream false passes, 292 cards without controls, and publication false.

This is local authored value-condition evidence. It does not resolve known
native or protected findings, verify oracle fixtures, establish independent
review, restore native-object semantics, or produce a model score. A future
engine-source change will again make this snapshot historical relative to the
running engine; the verifier must disclose that rather than silently treating
the snapshot as current.
