# Published comparison references

Numbers below are **published results, not scores produced by this overhaul**. They must not be used to tune a harness toward a preferred outcome. Live comparison runs are reported separately from these published references.

## Current IBM model table

| Model | QHE normal (%) | QHE hard (%) |
|---|---:|---:|
| mistral-small-3.2-24b-qiskit | 47.02 | 32.45 |
| Qwen2.5-Coder-14B-Qiskit | 49.01 | 25.17 |
| granite-3.3-8b-qiskit | 27.15 | 14.57 |
| granite-3.2-8b-qiskit | 24.50 | 9.93 |

[IBM's official table](https://quantum.cloud.ibm.com/docs/en/guides/qiskit-code-assistant) states these models used their respective system prompts. Matching model weights alone is insufficient: dataset revision, prompt template, runtime, decoding, token cap and task coverage must also match. IBM's table labels Qiskit versions used for **training**; do not misrepresent those as complete evaluation-environment specifications.

## Original paper: a different dataset size

| Model | QHE normal pass@1 (%) |
|---|---:|
| CodeLlama-34b-Python-hf | 26.73 |
| deepseek-coder-33b-base | 39.60 |
| starcoder2-15b | 37.62 |
| codegemma-7b | 24.75 |
| granite-8b-code-base | 28.71 |
| granite-8b-code-qk | 46.53 |

[The original QHE paper, v1](https://arxiv.org/html/2406.14712v1) reports greedy decoding on **101 tasks**. Comparing those percentages directly against the current 151-task suite, or a credential-free subset, is invalid. This is one concrete explanation for apparently conflicting benchmark numbers.

## Historical GrayBench Kimi run

The repository's `kimiK25/e86b3315_*` export reports 58/151 passes (38.41%) on the hard suite. Its 34 empty completions all have `finish_reason="length"`. Its configuration records a 4,096-token cap and nominal temperature 0/top-p 1, whereas the adapter's Kimi K2.5 request uses temperature 1/top-p .95. This discrepancy prevents the stored run configuration alone from reproducing the generation settings. The old runner also retried empty completions and retained only the final attempt's accounting.

These are observations from the stored run and source code. They do not establish what its score would be with another cap or runtime, or justify retroactively treating reasoning text as a final answer. New Moonshot calls are excluded from the user's current scope.

The historical export has ten prompts that differ from the current dataset. Restricting the direct comparison to the 133 unchanged, offline-eligible prompts gives **54/133 (40.60%)** both under the stored old outcomes and under final saved-answer rescoring. Task 9 changes from pass to assertion failure; task 71 changes from assertion failure to pass. Reused task IDs must not conceal changed questions. The broader 143-answer replay is retained only as a diagnostic; its 54 passes are not a matched-prompt benchmark score. Rescoring changes extraction, runtime and tests together and does not isolate a single cause. No new Moonshot calls were made.

## Additional published API-model references

[ScienceOne-AI's ScienceEval repository](https://github.com/ScienceOne-AI/ScienceEval) reports Qiskit HumanEval results of 52.98% for Gemini 2.5 Pro and 47.02% for OpenAI o3 High. Its documented QHE command uses temperature 0.6, top-p 0.95 and presence penalty 1.0. Those settings differ from this shared-prompt protocol; these are additional published comparisons, not matched replications. They do not provide a GPT-4o mini or Gemini 3.6 Flash score to compare directly. Its [QHE runner](https://github.com/ScienceOne-AI/ScienceEval/blob/main/benchmarks/Qiskit_HumanEval/run.py) additionally supplies a code-only instruction, strips import/function-definition lines and triple-quoted strings, and can retry empty completions up to ten times. We do not adopt these transformations merely to match its scores.


Direct comparison of ScienceEval's committed dataset at `f90e004468a1b18fcb71f4d5200f5accf057e723` with our pinned normal dataset finds 23 different prompts, 19 different references and three different entry points. Although 138 test ASTs differ, most differences are assertion messages; 22 still differ after ignoring those messages. Task 104 changes from choosing the lowest-complexity backend to the highest; tasks 84 and 86 change from pulse exercises to different circuit/transpiler tasks. Identical dataset size and reused task IDs therefore do not establish identical questions. See the [exact dataset revision](https://github.com/ScienceOne-AI/ScienceEval/blob/f90e004468a1b18fcb71f4d5200f5accf057e723/benchmarks/Qiskit_HumanEval/Qhumaneval.jsonl). This comparison identifies the committed file, not proof of the precise dataset used for every published table row.

## Comparison plan

1. Freeze a Docker image, reference preflight, task IDs and generation protocol before any paid evaluation.
2. Smoke-test the selected exact OpenAI snapshot and Google model for transport/account compatibility, without publishing the tiny sample as a benchmark score.
3. Run both suites on the same validated tasks, preserve every attempt, and show coverage, failures, truncations and uncertainty.
4. Reproduce at least one published open-weight Qiskit model only if its exact weights, chat template and evaluation setup are available. Keep native-template reproduction separate from a shared-prompt comparison.
5. Attribute disagreements to a verified setting or report them as unresolved. Never change tests merely to make percentages agree.

Sources accessed 2026-09-13. A broad HumanEval score advertised on a model card is a different benchmark from Qiskit HumanEval and is not a valid QHE reference.

## Reproducibility recheck, 2026-09-19

The [IBM table](https://quantum.cloud.ibm.com/docs/en/guides/qiskit-code-assistant)
still reports the four normal/hard pairs above and model-specific system prompts.
Its installation examples are not complete benchmark run manifests. In particular,
the Mistral model listing describes Qiskit 2.1 training while the table names 2.2;
neither establishes the precise evaluator dependency lock.

Pinned primary model cards inspected:

- [Mistral, revision 0c541958](https://huggingface.co/Qiskit/mistral-small-3.2-24b-qiskit/blob/0c541958022de04bd7c200b14a4b7a58977ae751/README.md).
- [Qwen, revision 9dbc517d](https://huggingface.co/Qiskit/Qwen2.5-Coder-14B-Qiskit/blob/9dbc517d40b6baa7c20bfa0d7ca1a988c99fba2a/README.md).

Their inference examples use a 512-token generation cap. This is not evidence that
the published evaluation used that cap. Exact dataset revisions, evaluation
dependency locks, decoding settings and per-task outputs remain unverified for
these table rows. Native-template replication and shared-prompt comparison remain
separate experiments; no local score has been certified against either reference.
