# Task 82: isolated file semantics, development track

`QpyFileJudge` provides `task82-file-semantic-v1`, an explicit alternative to the
unchanged upstream replication path. It invokes the submitted function once,
ignores its return value as the upstream check does, and captures `bell.qpy` from
the paused candidate. A new restricted container parses those opaque bytes using
the pinned Qiskit runtime. Only typed circuit data reaches a third container,
which holds the state oracle. Neither the host nor the trusted oracle loads QPY.
Candidate code, parser input and private oracle code have separate mounts.

The oracle checks the first serialized circuit, matching the upstream choice of
index zero. It requires two qubits and Phi-plus state fidelity within absolute
1e-10 of one, with zero relative tolerance. It accepts global phase, unlike raw
vector equality. Other circuits are retained in parser evidence but do not change
the verdict. Names and metadata are not task requirements. This is a semantic
projection, not proof of arbitrary QPY round-trip fidelity or the algorithm used.
Multiple-circuit policy and numeric tolerance still require formal task review.

Missing required output is a failure. Candidate execution errors remain candidate
errors. Invalid QPY, unsupported circuit codecs, parser crashes/timeouts and
unrepresentable artifacts remain unscored pending adjudication; they are not
automatically attributed to an incorrect model answer. Infrastructure failures
stay distinct. Artifact bytes/hashes, parser wire response, oracle evidence,
source/task/runtime identity and execution limits are preserved in the judgment.

Normal and hard pinned reference solutions pass this track in the exclusive
append-only `GrayBench-v3-task82-semantic-reference.jsonl` artifact, SHA-256
`b2f71a6fdfb285903fd3add6008c944152feaa456c27d7d5a2d8c987fe7be189`.
These are reference checks, not model results. The previous capture-only artifact
and historical full-scan failures remain unchanged.

Targeted Docker checks accept H/CX and a different RY/reversed-CX construction with
global phase, even when the function returns an unsupported Python object. They
reject an empty circuit, an unentangled state, Phi-minus and Psi-plus. Separate
checks distinguish absent output, malformed QPY, symlinks and function exceptions.

This track remains release-ineligible and is not silently selected by campaign
commands. Isolation limits the parser's access; it does not prove that a vulnerable
parser cannot fabricate decoded data. QPY security/version admission, additional
valid representations, resource calibration, malformed-file adjudication and
independent oracle review remain required before publishing scores. The unchanged
upstream bridge still lacks general file sharing; this track does not claim to fix
that interface or to establish universal file support.

Validation:246 tests passed in the full Docker-enabled run. After refining ignored
return-value release timing, all38 targeted file-judge, upstream-bridge and sandbox
tests passed, including the added finalization regression. Ruff lint/format pass.
The reference artifact precedes this final lifecycle refinement and retains its
original exact source identity. No billable model generations were used.
