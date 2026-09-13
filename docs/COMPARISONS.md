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

Replaying the stored final answers in the validated Docker environment, with no new model calls, yields **54/143 (37.76%)**, equal to the old numerator on those same 143 tasks. Task 9 changes from pass to assertion failure; task 71 changes from assertion failure to pass. The replay changes extraction, runtime and test assembly together and cannot isolate a single cause for either change. It does not regenerate answers or reconstruct the discarded empty-response retries.

## Additional published API-model references

[ScienceOne-AI's ScienceEval repository](https://github.com/ScienceOne-AI/ScienceEval) reports Qiskit HumanEval results of 52.98% for Gemini 2.5 Pro and 47.02% for OpenAI o3 High. Its documented QHE command uses temperature 0.6, top-p 0.95 and presence penalty 1.0. Those settings differ from this shared-prompt protocol; these are additional published comparisons, not matched replications. They do not provide a GPT-4o mini or Gemini 3.6 Flash score to compare directly. Its [QHE runner](https://github.com/ScienceOne-AI/ScienceEval/blob/main/benchmarks/Qiskit_HumanEval/run.py) additionally supplies a code-only instruction, strips import/function-definition lines and triple-quoted strings, and can retry empty completions up to ten times. We do not adopt these transformations merely to match its scores.

## Comparison plan

1. Freeze a Docker image, reference preflight, task IDs and generation protocol before any paid evaluation.
2. Smoke-test the selected exact OpenAI snapshot and Google model for transport/account compatibility, without publishing the tiny sample as a benchmark score.
3. Run both suites on the same validated tasks, preserve every attempt, and show coverage, failures, truncations and uncertainty.
4. Reproduce at least one published open-weight Qiskit model only if its exact weights, chat template and evaluation setup are available. Keep native-template reproduction separate from a shared-prompt comparison.
5. Attribute disagreements to a verified setting or report them as unresolved. Never change tests merely to make percentages agree.

Sources accessed 2026-09-13. A broad HumanEval score advertised on a model card is a different benchmark from Qiskit HumanEval and is not a valid QHE reference.
