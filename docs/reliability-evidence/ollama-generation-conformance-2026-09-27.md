# Ollama generation conformance, 2026-09-27

This is a **two-task development integration check**, not an admitted model
score. It exercised GrayBench's native Ollama adapter, metadata discovery,
frozen requests, append-only attempts, model observations, and protected
judgment using a model already installed on the local machine. No hosted API
or IBM Quantum service was used.

The frozen setup selected `qwen3:8b`, reported by local Ollama 0.34.4 with
model digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`
and Q4_K_M quantization. It selected normal and hard `qiskitHumanEval/0`, one
answer each, `qhe0-size-domain-v1`, protocol 3.3 pre/post model observations,
the default `raw_or_single_python_fence_v1` extraction, no system prompt, and
no requested sampling settings. The evaluator image was
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`
(Python 3.12.14, Qiskit 2.4.2); the generation source-manifest digest was
`f956780dc8bb5bccea2386c4149ec1150586b7c8b17658c00982f4ccadb4642c`.
The setup digest was
`773ecab8e7da0752bbb4b43fdec398a3d792d3e8a7b760be8b7a786a90dcee91`.

Run `a27b773d7a834ece874efe290adbbf67` returned both scheduled answers.
The normal answer passed the development task-0 judgment. The hard answer
received `candidate_error`: it contained three fenced blocks, which the frozen
v1 extractor rejects as ambiguous. No answer was regenerated, repaired or
silently rejudged. A later **read-only, extraction-only** probe found that both
v2 and v3 select the same sole entry-point Python block from that hard text.
That observation is not a v2/v3 judge result and does not establish whether
the selected function would pass. It also cannot justify selecting a different
extractor for this particular model after seeing its answer.

`graybench verify-ledger` reported 17 valid chained events and verified row
bindings. The cohort was complete, returned model names matched, discovery was
stable, and attempt-bound observations were complete. Its summary remains
`score_status: development_only` and `publication_eligible: false`, with task
and protocol admission and independent reproducibility blockers. The known
candidate-side serialization boundary also prevents treating this task-0
diagnostic as proof of native-object fidelity.

Exact local artifacts are retained outside the public PR in
`outputs/ollama-conformance-2026-09-27/`:

| File | SHA-256 |
| --- | --- |
| `model.json` | `b8208730a007ce79497a4eb115dcd18e9ffcf1c939d06c3777a6dfc5211aef8e` |
| `setup.json` | `5f96616a52460581b572cfebd917367f0f9a36a038cbae45920a6ff8c964c72c` |
| `run.sqlite` | `3377e6aee9c97ff82ce74a874e4fa668584ff2b64e1273b1ab0ec6206d5f4699` |

The ledger contains raw model output and host metadata. Its hash is a useful
integrity reference only while separately preserved; it is not an external
authentication of the machine or model weights.
