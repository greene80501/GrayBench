# Indented-fence extraction v3 (development condition)

`unique_entrypoint_fence_v3` is a separately frozen answer-format condition.
It extends [v2](extraction-protocol-v2-development.md) to recognize triple
backtick fences opened and closed with zero to three leading spaces. This
follows the indentation rule in
[CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/#fenced-code-blocks).
For a fence opened with N spaces, the extractor removes up to N leading spaces
from each content line. It accepts CRLF and LF. This is a deliberately narrow
backtick grammar, not a claim to implement all CommonMark constructs.

When there are multiple blocks, v3 selects a Python or unlabeled block only
if it has the sole top-level definition of the public entry point. Competing
definitions (including plausible Python bindings in a mislabeled block),
another binding of that name, malformed or unmatched delimiters, and
unrecognized four-space-delimited text are rejected. Non-Python example blocks
are not executed. Raw answers retain the existing behavior. Unindented
single-fence answers retain it for LF text, while v3 also accepts CRLF-closing
fences; the normal-suite public prefix and hard-suite lack of injected imports
are unchanged. The chosen policy and extraction method are part of the frozen
judge identity. v1 and v2 keep their previous meanings.

The triggering [live provider check](hosted-generation-conformance-2026-09-27.md)
is development evidence, not a training set for selecting the best extractor
per model. Its stored answers were inspected read-only: one unique OpenAI hard
function became extractable, while a Gemini normal answer with three competing
definitions remained rejected. No old judgment was rewritten and no v3 model
score is claimed. The policy needs broader preregistered format-sensitivity
evaluation before a release recommendation.
