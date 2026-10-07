# OpenAI-compatible Chat development route

The built-in `openai-compatible-chat` adapter supports a narrowly defined
wire interface: an OpenAI-style non-streaming Chat Completions POST with one
requested choice and one assistant text message in the response. Set `base_url`
to the API prefix, such as `http://localhost:8000/v1`; the adapter appends
`/chat/completions`. This follows the [OpenAI Chat Completions interface](https://platform.openai.com/docs/api-reference/chat/create).
Projects such as [vLLM](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html)
advertise that interface, but compatibility is endpoint- and model-specific.
The adapter does not claim that any particular server, model or setting has
been calibrated.
Chat responses must identify the message as `assistant`. Gemini text candidates
must identify their content producer as `model`. A terminal Gemini safety block
with no content is retained as an empty answer rather than replayed.

Unlike `openai-chat`, this route advertises no model metadata endpoint. A
campaign with the default `discovery_policy: "required"` stops before sending
a generation request. To run a development probe, freeze
`discovery_policy: "unverified_development"` and a nonblank
`discovery_exception_reason` in the model specification. The ledger then
records an unverified identity, the exact public request and response, and a
`model_discovery_unverified` publication blocker. The returned model name must
still match the frozen name or a separately evidenced declared alias.

For a local server that implements this exact route, a starting model
specification is:

```json
{
  "adapter": "openai-compatible-chat",
  "model": "local-model-id",
  "base_url": "http://localhost:8000/v1",
  "discovery_policy": "unverified_development",
  "discovery_exception_reason": "No calibrated model metadata endpoint for this server",
  "settings": []
}
```

Replace the model ID and endpoint with the server's actual values. The normal
`campaign-plan` command freezes this specification and the exact public task
requests before any generation.

Only settings explicitly marked `verified` in the model specification are
accepted by this adapter. That declaration means endpoint-specific evidence
must be retained; it does not make the setting independently verified by
GrayBench. A listed API field alone is insufficient. With no settings, the
server's own defaults apply and remain unverified. For example, vLLM documents
that a served model's `generation_config.json` may influence its defaults.
The request still fixes `stream: false` and `n: 1`; servers that ignore either
field need a separate adapter or conformance work.

This route extends **development access**, not release eligibility or a claim
of universal OpenAI compatibility. Before a publication-eligible campaign, verify the exact
server version, model artifact, chat template, request fields, returned model
identity, output parsing, effective sampling and token budget, then freeze a
capability profile or a native adapter with appropriate metadata evidence.
The strict OpenAI discovery policy and Ollama adapter remain unchanged.

Mock campaign controls verify that a required-discovery run sends no request,
while a reasoned exception sends one Chat Completions request and preserves
the publication blocker. The full original-image Python 3.12 Docker regression
passed 1,062 tests, skipped one experimental case, and had zero failures or
errors in 677.85 seconds. Its JUnit record is preserved at
`work/outputs/GrayBench-v4-compatible-provider-tests.xml`, SHA-256
`34fb49741cbd68af36bf7ffb9d66510e478a2db7799f9e15a42eeba9c5433ea5`.
No live provider generation was used for this route in that regression.
An independent two-slot local Ollama development pilot is recorded in
[`compatible-provider-local-pilot.md`](compatible-provider-local-pilot.md).
It exercised the real route and exposed a multi-block answer rejected by the
frozen extractor; it is not a release score or compatibility certification.
The optional, separately frozen
[`unique_entrypoint_fence_v2`](extraction-protocol-v2-development.md) condition
is intended to measure sensitivity to that response format; it does not
change or rescore the preserved pilot.
