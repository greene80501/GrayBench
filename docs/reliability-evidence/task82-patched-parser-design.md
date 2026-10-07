# Task 82 patched QPY parser: development design

The existing `task82-file-semantic-v1` candidate and oracle use the historical
Qiskit 2.4.2 image. QPY parsing is isolated, but that version is affected by
[GHSA-65ww-qhxg-c6h6](https://github.com/Qiskit/qiskit/security/advisories/GHSA-65ww-qhxg-c6h6).
The separate parser should use Qiskit 2.5.2 while candidate creation and the
trusted oracle retain their original immutable image. IBM documents forward
QPY compatibility from older producers to newer readers in its
[Qiskit SDK version strategy](https://quantum.cloud.ibm.com/docs/en/guides/qiskit-sdk-version-strategy);
the protected task controls must verify this particular pair rather than
assuming all circuit payloads are compatible.

`QpyFileJudge` accepts an optional immutable `parser_image` digest and freezes
it in its judgment manifest. The parser defaults to `image` only for preserving
historical development behavior; this default is not an admitted safe parser.
`decode_qpy` receives `parser_image`, and the parser evidence records the
runtime image. The candidate and oracle continue to use `image`. A Dockerfile
derives a parser-only image from the historical digest and replaces just the
Qiskit wheel with the 2.5.2 Linux x86-64 wheel verified by SHA-256. The
Dockerfile binds the full base digest in `FROM`, so a stale or retargeted local
tag cannot silently change the inherited runtime. The resulting image is
referenced by its immutable digest in the cross-version test and
evidence, never by a mutable tag in a frozen protocol.

Offline `campaign-plan` also accepts `--parser-image` for this recipe only.
`CampaignSetup` stores the digest and reconstructs the same judge on resume.
Changing it after planning must fail cohort identity validation, before any
generation or judgment. An explicit parser image on another recipe is invalid.

The controls cover two valid Phi-plus constructions and wrong/absent/malformed
QPY, showing the patched parser still distinguishes those outcomes. An image
digest and package-version check establish the actual parser runtime. No
parser version alone admits the task: malformed-file adjudication, resource
calibration, oracle review and whole-plan reproducibility remain open.
