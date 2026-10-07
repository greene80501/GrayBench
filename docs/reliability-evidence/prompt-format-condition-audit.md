# Default request rendering and normal answer-format condition

The [local prompt-format probe](prompt_format_probe.py) prepared every pinned
normal and hard task with each of the five built-in adapters: OpenAI Chat,
OpenAI-compatible Chat, OpenAI Responses, Ollama, and Gemini. It used empty
setting lists and no system prompt. Each adapter rendered all 302 public
prompts exactly once in its user-input field, without adding a
system instruction or reference/test text. This is 1,510 prepared requests,
not 1,510 provider calls; no model API was contacted. The result binds a
per-adapter request-manifest digest and the dataset pins.

The same probe tested pinned normal task 0 in the current protected-bridge
`upstream` recipe. The canonical literal suffix was assembled by extraction
as `raw+prompt` and passed. A complete replacement function with no import
was extracted as `raw`; the evaluator supplied only the import prefix from
the public normal prompt, and it also passed. Both responses use the current
`raw_or_single_python_fence_v1` policy and the same task and judge identity.
The [saved result](GrayBench-prompt-format-probe.json) has SHA-256
`f92a2d8779f7ace6264c794ec766cee03c4063a7a81d8f773db6a95b725dff4a`.
It records the script, pinned data, Python 3.12.14/Qiskit 2.4.2 runtime,
image digest, request aggregates, completion hashes, extraction methods,
and two passing judgments.

Accepting both forms is an explicit current extraction choice, not a hidden
provider-specific prompt helper or proof of bias. It does mean the current
development recipe is broader than a literal function-continuation-only
condition. A released native QHE reproduction must name its answer-format
condition and avoid claiming equivalence to a published literal-continuation
score without matching that rule. If a chat-oriented full-function condition
is offered, freeze and report it separately from literal continuation for
every model. These checks do not validate actual provider-side prompt
processing, effective settings, oracle adequacy, or task admission.
