# Request evidence and first-answer dispatch safety

Status: development slice implemented and locally verified. This slice does not
certify a model or publish a score.

The dual-track design requires one auditable first answer per scheduled sample. A
provider error can occur after execution, so a generic transient HTTP status is
not evidence that resending the prompt is safe. Existing 3.1–3.3 protocol and
ledger identities must remain readable.

1. Add focused tests for the exact bytes submitted by the HTTP client, a public
   declared credential/account scope in model identity, and ambiguous 5xx
   delivery. Verify the tests fail before implementation.
2. Add transport evidence for the byte digest and length, the non-secret auth
   header names, and the declared scope. Keep the secret itself out of every
   durable artifact. Classify 5xx generation responses as ambiguous.
3. Make new campaign builders freeze a single dispatch (`max_attempts=1`) while
   preserving the historical `RetryPolicy` default and old protocol digests.
   Gate new native/protected run creation against hand-edited retry policies.
   Add tests for native, protected, and legacy campaign builders.
4. Run focused tests, repository lint/format checks, and the relevant full test
   suite. Document remaining limitations, including that a declared scope is
   not independently authenticated and HTTP client evidence is not a packet
   capture. Refresh the draft PR with the verified state; keep GitHub Actions
   disabled while the account's Actions limit is unresolved.

Provider context: [OpenAI's rate-limit guide](https://developers.openai.com/api/docs/guides/rate-limits)
describes ordinary availability retries. GrayBench's single-dispatch choice is
a stricter benchmark rule, not a claim that the provider promises exactly-once
generation. The [OpenAI API overview](https://developers.openai.com/api/reference/overview)
documents request IDs for troubleshooting network-uncertain calls.

Verification on 2026-09-27: the pinned Python 3.12/Qiskit Docker-enabled suite
reported 1,235 passed, 5 skipped, and 6 expected failures in 615.16 seconds.
Repository-wide Ruff check and format check passed. A read-only reviewer found
and verified fixes for a copied-model credential-scope bypass and edited
dual-track retry policies. The expected failures are pre-existing development
controls, not release acceptance.
