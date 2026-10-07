# Loopback campaign regression evidence

The [report](report.json) binds engine source
`1b845366bfc60a76f91b771f353ed58da91815cf26e5b70f5688c4f1232ae40f`,
both new test/support files, the engine lockfile and the observed environment.
It was collected from the working tree based on `54c7f97`, with the new tests
present. Runtime engine source is unchanged by this test-only addition.

The full main-checkout suite passed **1,621**, skipped **292**, and had zero
failures in 492.96 seconds. All 30 declared loopback scenarios passed within
that run; their individual case times total 50.394 seconds. The initial focused
run also passed all 30 in 51.37 seconds. Pinned cache was enabled, while
container image tests and strict canonical graph qualification were disabled.
The full run's 60 warnings comprise 48 original Qiskit `Diagonal` deprecations
and 12 Windows temporary-directory cleanup warnings. Lint and formatting
passed for 232 engine source/test files when run from `engine/`.

The complete [JUnit record](full-suite.xml) contains 365,644 bytes with SHA-256
`f88679e9e74e92a50b5dfe2056e4d74eeb2efcabca5ede0308818122ec7e39c2`.
The report contains 9,416 bytes with SHA-256
`e46432ed597bee113e5f95abd42f4c78973e2c20b4843a87c5a9a98e9409ea10`.
Individual verdicts and durations can be checked against that XML. The report
records both console duration and JUnit duration; these are different timing
boundaries. Test assertions check request/response bytes and hashes, but this
bundle does not archive every temporary fixture ledger or server capture.

The [verification description](../../loopback-campaign-verification.md) states
the exact pipeline and its substitutions. Thirty scenarios span five adapters,
both public formats and three delivery conditions. Ten returned-answer
scenarios score two fixed authored answers, one pass and one fail. Twenty
HTTP-503/redirect scenarios remain incomplete and unscored after reopening;
their second scheduled sample is not silently generated. Responses are gzip
entities delivered over chunked HTTP through the actual production client.
Request binding, completion-bound judgment, metadata observations and final
ledger verification remain production code.

Read-only review found no important code issue and separately reproduced four
returned-answer cases spanning normal/hard and Gemini/Responses in 9.51
seconds. A minor documentation claim about a saved report was corrected to
report computation/verification. This is bounded local review, not independent
benchmark admission. No live provider, real API credential, model inference or
Docker execution occurred. The local execution runner allows only four exact
authored completions and labels its synthetic runtime scope explicitly.

Reproduce the focused scenarios from `engine/`:

```sh
uv run --locked --extra dataset pytest tests/test_loopback_campaign.py -q
```

Set `GRAYBENCH_TEST_CACHE` to the pinned source cache first. To collect a new
full record, run `pytest -q --junitxml=NEW_FILE.xml` with the same locked
environment and disabled container-image test setting. Do not overwrite this
historical artifact. Source hashes and verdicts can be reproduced; timings,
host labels, temporary paths and ephemeral ports need not match byte-for-byte.

Publication, provider qualification, container qualification and independent
admission remain false. This is local integration verification with authored
fixtures, not a model score or a native-object/isolation claim.

A clean checkout of `45a62c2`, using separately installed locked dependencies
on the same host, reproduced all **30 focused passes**, with zero failures or
skips, in 49.33 seconds. Its 12 warnings are Windows temporary-directory
cleanup warnings. The [clean JUnit record](clean-loopback.xml) has 5,849 bytes
and SHA-256 `f5b04c890dc2f74af1829458d863275c7609c5d2912cdebd0a4b68011eac8cb5`.
Its declared case roster and verdicts match the main record. Source, fixture,
lockfile and full-JUnit hashes were checked, and lint/formatting passed for the
same 232 files. The clean checkout had no local changes before or after the
run. This is focused same-host reproduction, not a new full clean-suite run or
independent runtime/provider admission.
