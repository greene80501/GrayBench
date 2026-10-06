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

## ScienceEval's public 151-task condition

[ScienceEval's published table at commit `1683e498`](https://github.com/ScienceOne-AI/ScienceEval/blob/1683e4987bab03b706307b5cb9b4a46e8fed5e89/README.md#-evaluation-results)
lists Qiskit HumanEval results including Gemini-2.5-Pro **52.98%**,
OpenAI-o3-High **47.02%**, and Qwen3-8B **23.18%**. These are ScienceEval
results, not GrayBench results. The table does not list GPT-4o mini or Gemini
2.5 Flash. Its [Qiskit HumanEval dataset](https://github.com/ScienceOne-AI/ScienceEval/blob/1683e4987bab03b706307b5cb9b4a46e8fed5e89/benchmarks/Qiskit_HumanEval/Qhumaneval.jsonl)
has 151 unique IDs 0–150 (SHA-256 of the downloaded JSONL:
`6e447d84713b4f0d335ceeb95bbbb4eaf809543ef9dbe7cb6463300d4841628d`).
Comparing decoded values of all six fields by `task_id` shows that **all 151
records exactly match** the upstream `0.1.0` JSON described below. Relative to
GrayBench's pinned current *normal* parquet, the dataset has 23 different
prompts, 19 different canonical solutions, 138 different test strings, 3
different entry points, and 1 different difficulty value; only 9 complete
records match. The hard suite has a different prompt format and no complete
record matches this dataset. This is a verified dataset-revision difference,
not merely a shared denominator.

ScienceEval's [runner](https://github.com/ScienceOne-AI/ScienceEval/blob/1683e4987bab03b706307b5cb9b4a46e8fed5e89/benchmarks/Qiskit_HumanEval/run.py)
adds an instruction to return only function code, extracts the last Python
fenced block, removes triple-quoted text, and discards lines beginning with
`import`, `from`, or `def` before passing a completion to `human-eval`.
Its [reproduction guidance](https://github.com/ScienceOne-AI/ScienceEval/blob/1683e4987bab03b706307b5cb9b4a46e8fed5e89/README.md#-reproducing-evaluation-results)
sets temperature 0.6, top-p 0.95, and presence penalty 1.0 for its ScienceOne
base-model Qiskit run, with model-specific token caps. The
[Qiskit-specific README](https://github.com/ScienceOne-AI/ScienceEval/blob/1683e4987bab03b706307b5cb9b4a46e8fed5e89/benchmarks/Qiskit_HumanEval/README.md)
uses Python 3.12, but its [requirements](https://github.com/ScienceOne-AI/ScienceEval/blob/1683e4987bab03b706307b5cb9b4a46e8fed5e89/benchmarks/Qiskit_HumanEval/requirements.txt)
do not pin Qiskit or `human-eval`. No per-task outputs accompany that pinned
repository tree. Consequently the table is a useful historical reference, but
neither its score nor its per-task pass set can be treated as an exact control
for a current GrayBench normal or hard run. A matched reproduction would need
to freeze the old dataset, full request and extraction protocol, model
revision/endpoint, dependency environment, and raw generations.

## Public-release drift check

The upstream repository's [first public release, `0.1.0`](https://github.com/qiskit-community/qiskit-human-eval/releases/tag/0.1.0),
was published on 2024-11-12, after the paper's June 2024 version. Its
[`dataset_qiskit_test_human_eval.json`](https://github.com/qiskit-community/qiskit-human-eval/blob/7c84727243d7851e3f5e9f90af66ebd5d6f054de/dataset/dataset_qiskit_test_human_eval.json)
contains 151 records with IDs 0–150. The Git blob is
`360ee1ee04d1b153b5bea99c71e9a11387be9235`; the decoded file's SHA-256 is
`496ce82372744e685ee7dd1891f58fb8e2b976b53a5a82208ae3a9994541938e`.
The exact decoded file is retained locally outside the PR as
`outputs/upstream-qhe-0.1.0.json`.

The [GitHub initial commit](https://github.com/qiskit-community/qiskit-human-eval/commit/c5a7d309a3561f12461ee56fd258887a9fff01e9)
on 2024-11-08 had no dataset file. The linked first public release commit on
2024-11-12 introduced the 151-record file. The
[Hugging Face dataset history](https://huggingface.co/datasets/Qiskit/qiskit_humaneval/commits/main)
starts on 2024-11-13 with only a card and attributes; its
[first parquet commit](https://huggingface.co/datasets/Qiskit/qiskit_humaneval/commit/025a2fb7e8192d12eba7951786929b7e73020749)
on 2024-11-15 has 151 records (parquet SHA-256
`e6ef2b6e576cc66a77ddd4ac6b9bb39bd3cfb5f50baad1bcd414931e2b28d64d`).
The [reproducible comparison](earliest_public_qhe_artifacts.py) found zero
decoded differences across all 151 task IDs and five non-ID fields between
that parquet and the first GitHub release. Its
[saved result](GrayBench-earliest-public-qhe-artifacts.json) has SHA-256
`831f89c07e752763694ab982b17aede54785ea584f1688941dd3ecf8ac421aea`.
These two official public histories do not supply the paper's 101-task file;
this does not prove that no private or separately archived copy exists.

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

GrayBench's [current native calibration](artifacts/native-reference-current-2026-10-06-v2/README.md)
exercises only the 143 offline task IDs in each pinned suite; eight
external-service tasks are excluded. Its denominator therefore differs even
from a 151-task result on the same dataset revision. The separately versioned
protected value contracts also ask for different answer types and must be
reported as a distinct track. We will compare per-task results on matched IDs
and protocols before making any aggregate claim against an outside score; we
will not tune a judge merely to reproduce a published percentage.
