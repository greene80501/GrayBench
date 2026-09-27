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

## IBM's later normal and hard reference table

[IBM's Qiskit Code Assistant documentation](https://quantum.cloud.ibm.com/docs/en/guides/qiskit-code-assistant)
(read 2026-09-27) reports both Qiskit HumanEval percentages for these named
models:

| IBM-listed model | Normal | Hard |
| --- | ---: | ---: |
| mistral-small-3.2-24b-qiskit | 47.02% | 32.45% |
| Qwen2.5-Coder-14B-Qiskit | 49.01% | 25.17% |
| granite-3.3-8b-qiskit | 27.15% | 14.57% |
| granite-3.2-8b-qiskit | 24.50% | 9.93% |
| granite-8b-qiskit-rc-0.10 | 38.41% | 15.89% |
| granite-8b-qiskit | 44.37% | 17.88% |

IBM describes these datasets as approximately 150 tests and explicitly says
**each model was evaluated with its own Hugging Face system prompt**. The table
does not identify the exact dataset commit, evaluator image, per-task results,
or full decoding configuration. Those model-specific prompts are part of IBM's
reported condition and differ from GrayBench's no-system-prompt development
checks. These figures are useful external reference points for a future matched
reproduction, not expected values for a GrayBench run with other models or a
different prompt protocol. An output-only match in percentage would not verify
that the same tasks passed.

## Public-release drift check

The upstream repository's [first public release, `0.1.0`](https://github.com/qiskit-community/qiskit-human-eval/releases/tag/0.1.0),
was published on 2024-11-12, after the paper's June 2024 version. Its
[`dataset_qiskit_test_human_eval.json`](https://github.com/qiskit-community/qiskit-human-eval/blob/7c84727243d7851e3f5e9f90af66ebd5d6f054de/dataset/dataset_qiskit_test_human_eval.json)
contains 151 records with IDs 0–150. The Git blob is
`360ee1ee04d1b153b5bea99c71e9a11387be9235`; the decoded file's SHA-256 is
`496ce82372744e685ee7dd1891f58fb8e2b976b53a5a82208ae3a9994541938e`.
The exact decoded file is retained locally outside the PR as
`outputs/upstream-qhe-0.1.0.json`.

We compared those 151 records by `task_id` against GrayBench's content-pinned
normal parquet (`a0066805f7a15cb48e9d0cface2210056185be6d`, SHA-256
`1fb8d49195a08c023cc93b489b5d2ae0c2118047a5306f6fd374e3b4e95a94e6`).
The field comparison used decoded JSON strings without trimming whitespace or
normalizing newlines:

| Field | Records with different strings |
| --- | ---: |
| Prompt | 23 |
| Canonical solution | 19 |
| Test | 138 |
| Entry point | 3 |
| Difficulty scale | 1 |

Only 9 complete records match in all five fields. To separate diagnostic-message
edits from Python structure, we also parsed both test strings with Python 3.12,
set every `ast.Assert.msg` to `None`, and compared attribute-free AST dumps.
That still leaves **22 structurally different tests**, at IDs 9, 34, 41, 68,
71, 84, 86, 93, 100, 102, 104, 112, 122, 125, 127, 129, 130, 131, 138,
145, 146 and 150. AST differences do not alone prove a changed acceptance set;
the exact-byte differences already establish that the first public release is
not the same test artifact as the pinned current suite. The 101-task paper set
predates even this first 151-task release, so neither 151-task artifact should
be used as its denominator without recovering the paper's exact task IDs and
test revision.
