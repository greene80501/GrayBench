# Real HTTP campaign wiring checks

These development regressions exercise the production HTTP client, all five
built-in adapters, model observation, frozen protected setup, generation
scheduling, SQLite attempts, semantic judgment and report computation/verification
through an actual loopback socket. Existing in-memory HTTP tests remain useful
for individual failure branches. The new tests check their integration with
real encoded response capture and persisted run reconstruction.

Thirty scenarios cover normal/hard public formats, each adapter, and three
delivery conditions. Ten returned-answer scenarios schedule two fixed authored
answers: the correct Bell-amplitude value followed by an incorrect product
state. The trusted semantic oracle accepts the first and rejects the second.
Twenty scenarios return HTTP 503 or an HTTP redirect; delivery remains
ambiguous, the restarted scheduler makes no further generation request, and
the incomplete campaign receives no score.

Each run freezes the exact task-2 public value revision and all 150 excluded
records for that suite, two replicate slots, a single-dispatch policy and the
current source/adapter/judge identities. After the first delivery, the test
closes the ledger and HTTP client, reloads the setup from its stored JSON,
opens a new ledger/client, and reconstructs the actual protected campaign.
This is object/connection reopening within one test process, not a crash,
power-loss or second-machine reproduction experiment.

The server captures dispatched request bodies independently. The checks compare
their hashes against stored delivery evidence, preserve the complete public
prompt, and reject exact canonical/checker leakage. Generation responses use
gzip entities transmitted in eleven-byte HTTP chunks. Stored entity and decoded
body hashes and byte counts must match the server's original bytes. An encoded
entity hash excludes HTTP headers and chunk framing; it is not a network-packet
capture or server authentication proof. Redirect destinations are never reached.

The tests use a synthetic credential sent through the actual authentication
headers. The server records only whether authentication matched, and the tests
check that no credential literal enters stored ledger blobs. Hosted fixture
metadata and Ollama fixture catalogs remain server-reported claims. The
compatible adapter explicitly declares its lack of metadata as unverified
development and does not become a verified model-discovery condition.

Only `ProtectedCampaignSetup.judge` is substituted: it constructs the real
semantic judge with a test-only runner that allows four exact authored
completions and invokes the actual worker/parser in a local subprocess.
Transport, adapter preparation/parsing, model observations, scheduler, durable
claims, ledger verification and report computation remain production code.
The runner manifest labels its scope, hashes its fixture/worker and makes no
container claim. Its synthetic image-shaped identity is not an installed or
executed image. It must never be used to execute arbitrary model answers.

All reports remain publication-ineligible. The ten successful wiring scenarios
have two bound judgments and two bound requests, with the known fixture success
fraction `0.5`; that number is a fixture result, not LLM performance. The 20
uncertain scenarios have one bound attempt each and no score. These tests do
not qualify live providers, effective settings, TLS, model weights, container
isolation, arbitrary malicious-code execution, task adequacy or admission.

From `engine/`, with an exact pinned dataset cache available:

```sh
GRAYBENCH_TEST_CACHE=CACHE uv run --locked --extra dataset pytest tests/test_loopback_campaign.py -q
```

On PowerShell set `$env:GRAYBENCH_TEST_CACHE` before running the same pytest
command. No user API key, external endpoint, model inference or Docker call is
required. Docker remains a separate qualification requirement.

The [source-bound regression bundle](artifacts/loopback-campaign-2026-10-07/README.md)
records the full-suite result and all 30 declared case verdicts.
