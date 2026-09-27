# Published Qiskit HumanEval baselines and comparability

The [2024 Qiskit HumanEval paper](https://arxiv.org/pdf/2406.14712)
reports pass@1 under greedy decoding on **101 tasks**. Its table III partitions
that set into 54 basic, 45 intermediate and 2 difficult tasks. The paper's
table II reports these Qiskit HumanEval results:

| Model named in the paper | QHE pass@1 on its 101 tasks |
| --- | ---: |
| CodeLlama-34B-Python-HF | 26.73% |
| DeepSeek-Coder-33B-Base | 39.60% |
| StarCoder2-15B | 37.62% |
| CodeGemma-7B | 24.75% |
| Granite-8B-Code-Base | 28.71% |
| Granite-8B-Code-QK | 46.53% |

These are historical **paper results**, not GrayBench runs. In particular,
the paper does not report GPT-4o mini, Gemini 2.5 Flash, or Gemini 3.8 Flash.
The [current upstream repository](https://github.com/qiskit-community/qiskit-human-eval)
describes **151 problems** and two prompt versions: normal includes imports
and the function header, while hard supplies only the problem statement and
requires the function. GrayBench's pinned 151-task normal and hard suites
therefore have different denominators and potentially different prompt and
test bytes from the 101-task paper experiment. Its frozen Python 3.12 / Qiskit
2.4.2 environment is also not established as the paper's execution environment.

An apparent difference between a GrayBench percentage and one of these paper
percentages is **not evidence of a judging defect or model improvement** without
a matched task set, prompts, tests, model artifact, decoding configuration,
answer extraction rule, and dependency versions. The paper's greedy setting
also must not be inferred from a provider default when a hosted API cannot
confirm effective sampling controls. A reproduction should first recover the
exact 101 task IDs and experimental protocol, then run the same model artifact
under that historical condition. A current 151-task normal or hard result
should be labeled as a separate condition even if the model name matches.

The two-answer [hosted integration checks](hosted-generation-conformance-2026-09-27.md)
are development diagnostics and cannot be compared with these baselines.
GrayBench currently has no admitted, complete cohort score.
