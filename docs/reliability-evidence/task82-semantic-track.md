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
errors. In v1, invalid QPY, unsupported circuit codecs, parser crashes/timeouts and
unrepresentable artifacts remain unscored pending adjudication; they are not
automatically attributed to an incorrect model answer. Infrastructure failures
stay distinct. Artifact bytes/hashes, parser wire response, oracle evidence,
source/task/runtime identity and execution limits are preserved in the judgment.

`task82-file-semantic-v2` preserves v1 and changes only a definite file-format
case: an existing file that does not start with the six-byte `QISKIT` magic
specified by the [QPY format](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.2/qpy)
fails before parsing. Empty files and truncated prefixes also fail. A file with that
prefix that the parser rejects remains unscored because parser failure alone
does not prove the candidate file invalid. The recipe and manifest record the
changed policy. V2 is development-only and requires explicit campaign selection.
The exact pinned normal and hard references both passed v2 with the patched
parser image. The append-only [v2 reference scan](GrayBench-v4-task82-header-v2-reference.jsonl)
has SHA-256 `d30a85b190dded3cfe1ffe5e25f72a4358aa1d57105c30c5237e7ea93f4365ab`.
It records protected judgments and source identities, not model scores.
The pinned-image Python 3.12 Docker regression for this increment passed
1,053 tests, skipped one experimental case, and had zero failures or errors
in 618.64 seconds. The JUnit record is preserved outside the repository at
`work/outputs/GrayBench-v4-task82-header-v2-tests.xml`, SHA-256
`8533399bd0945a827560460227c5dbba49c502698e018e15ca0578b40e2db203`.

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

A 2026-09-03 [Qiskit security advisory](https://github.com/Qiskit/qiskit/security/advisories/GHSA-65ww-qhxg-c6h6)
reports that malicious parameterized QPY payloads can segfault `qpy.load` in Qiskit
versions from 2.1.0 before the 2.5.2 fix. The pinned development image uses Qiskit
2.4.2 and therefore falls in that affected range. The parser's separate restricted
container limits the impact on the trusted judge but does not make the parser safe or
turn a parser crash into a scored wrong answer. A patched, independently pinned parser
runtime and renewed compatibility/adversarial controls are explicit release gates.

## Patched parser development increment (2026-09-27)

The parser can now use its own immutable `parser_image`; the candidate and trusted
oracle remain on the historical image. A derived Linux x86-64 parser image replaces
only the Qiskit wheel with 2.5.2. `engine/parser/requirements.lock` pins the PyPI
wheel SHA-256 `28fcb983e565b8f027a13ef43cda7aaeb1f1a6caf9df07408708abcf7bc0b59d`.
The local build used:

```powershell
docker tag sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd graybench-qpy-base:2fc74bd3dd29
docker image inspect graybench-qpy-base:2fc74bd3dd29 --format '{{.Id}}'
docker build -f engine/parser/Dockerfile -t graybench-qpy-parser:2.5.2 engine/parser
docker image inspect graybench-qpy-parser:2.5.2 --format '{{.Id}}'
```

The Dockerfile's `FROM` binds the full historical digest, in addition to the
local tag. A deliberate wrong-tag build still inherited the original eight
base layers, and the tag was restored. The pinned-build parser image ID was
`sha256:731a7ed19488145b2a0ba0d7efbb4528d13cc6466ca3ba114254bb5ab4782ae9`.
The tested engine source manifest digest was
`bc0349ddb106cbc38558a079df181d4340fab3c4a6847b21e476c589f5ef13c9`.
A disposable `--network none` container reported Python 3.12.14 and Qiskit
2.5.2; `pip check` reported no broken requirements. Docker's RootFS inspection
showed that the parser retains all eight base layers and adds two layers.
Two valid Phi-plus QPY constructions written by the Qiskit 2.4.2 candidate
passed under this parser and historical oracle. An empty circuit failed, and
malformed bytes remained unscored. The focused protected suite passed 18 tests.
The parser image and its route are frozen in the judgment manifest and campaign
setup; both file recipes accept `--parser-image`. The patched-build focused suite passed all
18 tests again. The pinned normal and hard reference solutions both passed;
their exact source-bound judgment evidence is preserved in
[`GrayBench-v4-task82-pinned-parser-reference.json`](GrayBench-v4-task82-pinned-parser-reference.json),
SHA-256 `b0e9a56cb0f3a4438a7ef7da76b4ec3b8d69572b752f595c4edd37d187389051`.
The artifact stores task/judge digests and QPY bytes, but no canonical source
or private test body.

The complete Python 3.12 Docker-enabled regression on source digest
`bc0349ddb106cbc38558a079df181d4340fab3c4a6847b21e476c589f5ef13c9`
passed 1,039 tests, skipped one experimental cached-Hamiltonian case, and had
zero failures/errors in 586.84 seconds. This full run used the earlier
`sha256:12402b7b4337434917024d06bbbe883bf4d9b31c3ac3fcb4d474d8e8907b01ca`
parser manifest. Its RootFS layers and Docker config exactly matched the
digest-pinned rebuild; the rebuilt digest received the separate 18-test
protected replay and both exact reference replays. JUnit XML is retained
locally as `outputs/GrayBench-v4-task82-parser-final-tests.xml`.

This verifies a specific cross-version path, not arbitrary QPY safety or task
admission. The advisory's published fix addresses its stated segfault vector;
isolated parsing, malformed-file adjudication, resource calibration and
independent oracle review remain necessary. The task stays release-ineligible.

Historical v1 validation: 246 tests passed in its full Docker-enabled run.
After refining ignored return-value release timing, all 38 targeted file-judge,
upstream-bridge and sandbox tests passed, including the added finalization
regression. Ruff lint/format pass.
The reference artifact precedes this final lifecycle refinement and retains its
original exact source identity. No billable model generations were used.
