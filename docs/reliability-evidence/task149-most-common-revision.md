# Task 149: separately versioned most-common-bitstring condition

`qhe149-most-common-bitstring-v1` is an opt-in development recipe for the pinned
normal and hard task 149. The original task records and upstream scores remain
unchanged. Both revised public requests specify a nonempty `BitArray` of
equal-width strings with a unique most frequent string. Ties, empty arrays and
mixed widths are outside this condition. The normal request retains the
upstream `statistics.mode` and `BitArray` imports.

The trusted test constructs nine count patterns with different widths, maxima,
counts and insertion orders. It requires an exact Python `str` equal to the
unique most frequent bit string. Local tests show that the pinned normal and
hard reference solutions and a count-based alternative pass, while first-string,
last-string and fixed-string shortcuts fail. The pinned source task digests are
`363fe9e4032fcc9e3f16d0b38d41a9a7233dcee7c31728efc1f566cafc2bd013`
for normal and `8071f037bf801abf0d2f16851d538e5656baadd6cda5a19fa69cd6eba17096bf`
for hard. The recipe binds the revised public prompt, private test, source task
digest and judge configuration before provider requests are frozen.

This condition uses protected value protocol 3. A local roundtrip confirms that
the exact `BitArray.from_counts` input survives its value codec. The graph
bridge cannot currently encode the NumPy-backed `BitArray` as a graph snapshot;
that interface remains unsupported for this recipe. The value bridge is
sufficient for the stated input/output value contract, but candidate-side
encoder substitution remains an integrity risk. Nine authored cases are not an
exhaustive proof. Stateful candidates, independent oracle and task-card review,
and protected Docker controls remain unverified. The manifest therefore records
`release_eligible: false`. These checks are not model generations or scores.

The [pinned upstream oracle finding](task149-most-common-oracle-review.md) and
its protected probe remain separate historical evidence.
