# Task 141: explicit Pauli-group contract revision

The pinned upstream tests accept ten zero operators, although zero is not a
Pauli-group element. The separate `qhe141-pauli-group-anticommutator-v1` track
checks membership as well as the anticommutator relation. Upstream replication
and its historical results remain unchanged.

The public revision specifies ten returned operators or numeric matrices, the
input's qubit count, phases +1/-1/+i/-i, and numerical comparisons with absolute
tolerance 1e-10 and zero relative tolerance. It does not require random sampling,
distinct answers, or the reference implementation's construction method.
Eight fixed one-, two-, and three-qubit inputs exercise the checks. The judge
preserves the input matrix before invoking the candidate and checks dimensions
before dense conversion. It rejects non-finite entries, checks Pauli-basis
membership and then checks the anticommutator against a scalar identity.

Call `PauliAnticommutatorJudge.revise(original)` before freezing the generation
request, then generate and evaluate using that revised task. Configuration and
evaluation reject an unrevised task. This API guard does not authenticate the
history of an arbitrary externally supplied answer; campaign provenance must
bind the revised public request to the actual generation. Normal-suite revisions
end with a newline so the contract comment cannot swallow the generated body.
The track is not automatically selected by the CLI.

Protected replay evidence is retained in
`GrayBench-v3-pauli-revision-evidence.jsonl` (SHA-256
`733017b8fde3393ca79bb4425f73f843214a50e1ee95ab888c3b76ee236dc746`).
All eight cases completed with the expected outcome: both official references
pass, zero operators fail in both suites, and phase/matrix alternatives pass in
both suites. The log binds original and revised task digests, complete authored
answers, the image, actual source bytes and private judge records. Actual
worktree bytes are recorded; Windows line endings can differ from Git blobs.
These are authored validation probes, not model generations or accuracy scores.

This track remains release-ineligible: finite input coverage is not a correctness
proof, independent review is outstanding, and transport support is incomplete.
Bound-subsystem outputs explicitly remain unscored infrastructure errors pending
semantic admission. Other unsupported return representations remain unscored
through the transport boundary. Acceptance of equivalent numeric matrices is an
explicit contract expansion and must not be described as an upstream score.

Final local validation: 336 tests pass with Docker enabled, zero failures, errors
or skips, in 117.50 seconds. Ruff lint and formatting pass. Tests cover invalid
zero/scaled/non-Pauli/non-finite answers, list shape, equivalent representations,
pre-generation contract enforcement and normal-suite body completion boundaries.
