# GrayBench evaluation protocol v2

GrayBench measures execution-based success on **Qiskit HumanEval**, not generic HumanEval or Humanity's Last Exam. A passing program satisfies the supplied tests; it is not a proof of correctness for all possible inputs or a measurement of general intelligence.

## Data and prompts

- Load the official normal and hard datasets at immutable Hugging Face revisions. Hash every task's full prompt, tests, reference, entry point, metadata and ordering.
- Send only the official prompt to the model. No canonical answers, hidden tests, test feedback, retrieved examples, task-specific hints, tools, or repair turns are supplied.
- Normal is a completion exercise. The public prefix supplies imports and a function signature. Appending a returned function body to this prefix is required execution assembly, not answer repair. Full function responses may also use imports already present in that public prefix. Those public imports are executed in the candidate namespace before compiling the returned module, so a legitimate leading `__future__` import stays at the beginning of its own module.
- Hard is the official standalone-function exercise. Its prompt includes the function name and argument contract. Never invent hard prompts by stripping the normal prompt.
- Extract every explicitly Python-labeled fenced block in order. If none exist, use untagged fenced blocks; if there are no recognized blocks, use raw output. This keeps unlabeled example output separate when code is explicitly labeled. Preserve helpers, constants and indentation within the selected format. Do not select a function or candidate based on which one passes. Do not insert missing imports in hard mode, rename functions, fix syntax, or salvage reasoning text as a final answer.

## Optional environment-declared experiment

`--prompt-profile environment` adds the same system message for every task: Python 3.12, Qiskit 2.4.2, qiskit-aer 0.17.0 and qiskit-ibm-runtime 0.45.0, followed by a request to target those versions and return Python code only. It supplies no examples, answers, replacement imports, retrieved documentation or test feedback. This profile is recorded and grouped separately from `official`, which remains the default with no system message.

This secondary experiment was introduced after observing outdated imports in baseline outputs; it is exploratory, not an independently preregistered replication. Run all selected tasks under a profile and report both profiles; do not retain only whichever profile scores better. Version disclosure and formatting instructions change together here, so their individual causal effects are not isolated.

## Attempts and generation settings

Each task receives one returned generation, including refusals and empty or truncated answers. Only explicit rate-limit errors may be retried. Record provider response and actual request parameters. Default output cap is 16,384 tokens; this is a declared protocol choice, not a promise that every reasoning model has enough capacity. Report finish reasons and study alternative caps as separate, preregistered experiments. Never retry only the failures and report the best score.

Temperature zero does not guarantee bitwise reproducibility. Some models require their own sampling settings; the actual request is authoritative. A reasoning model's internal token accounting may differ from another model's. Equal token limits are a compute-control convention, not equivalent reasoning capacity. Tools or agent systems such as GrayGate belong in a separately labeled track.

## Reference validation and coverage

Validate references **before** generating any model answers, and freeze the eligible task IDs for all models. Reports include exact dataset identity, installed packages, Python/OS, outcomes and a content fingerprint. A changed environment or dataset invalidates the report.

The offline profile excludes tests or references that require external service credentials. It does not mock an IBM service into always succeeding. An assertion that fails the official canonical solution is a reference/environment failure, not a model failure. Such tasks remain visible in the report. Never relabel an offline subset score as the full 151-task official score.

Normal and hard test functions execute once in a test namespace independent of candidate globals. A zero process exit alone is insufficient evidence of a pass. Incomplete runs and duplicate attempts cannot be marked complete. Generated-answer failures remain in the recorded task denominator. Operational API failures invalidate completion and remain available for diagnosis; they must not be presented as model capability scores.

## Reporting and comparability

Report numerator, denominator, coverage, task IDs, environment, full request/response, finish reasons, elapsed time and usage. Wilson 95% intervals describe uncertainty under a task-sampling interpretation; they do not correct flawed tests or estimate all real-world programming ability. Unknown prices remain unknown. Costs are estimates based on rate tables and reported usage, not invoices. The pre-run budget check reserves the declared output-token cap plus a conservative input allowance; provider price changes or ambiguous network failures can still differ from estimates.

Comparison groups require matching dataset, task selection, environment and evaluation settings. Preserve all runs and seeds. Do not pool subset runs with full runs, choose the best repeated run, or mix agent-system and direct-model results.

## Execution boundary

Live evaluation requires a validated Docker image, pinned by its content ID. Each task runs without network access, as UID 65534, with a read-only root filesystem and read-only task-file mount. Writable storage is a 256 MiB temporary filesystem. Limits are one CPU, 4 GiB memory, 128 processes, 120 seconds and 1 MiB per captured output stream. The host repository, user profile, provider keys and Docker socket are not mounted. Containers are removed after each task, including timeout cleanup.

The local subprocess backend is only for reviewed references and synthetic tests; it is not a security sandbox. Docker reduces host exposure but does not prove immunity to runtime vulnerabilities or deliberate in-process test introspection. The harness checks a structured completion report and a successful exit, but is not a tamper-proof judge against an adversarial program. A public benchmark cannot rule out training-data contamination.

The 2026-09-13 Docker preflight passes all 143 offline references in each suite. Eight service-dependent tasks are excluded: 43, 97, 98, 122, 129, 133, 134 and 146. This is 94.70% task coverage. These IDs were frozen before live model generations. Windows-local validation passed only 140; the Linux image resolved the Graphviz and platform-dependent reference failures without changing assertions.

## Primary sources

- [Official dataset repository](https://github.com/qiskit-community/qiskit-human-eval): normal completion and hard standalone-function formats; Graphviz requirement. Inspected commit `c98ba538239fcfd554aa89627ee8026f4b5de450`.
- [Normal dataset](https://huggingface.co/datasets/Qiskit/qiskit_humaneval), revision `a0066805f7a15cb48e9d0cface2210056185be6d`.
- [Hard dataset](https://huggingface.co/datasets/Qiskit/qiskit_humaneval_hard), revision `315e167a479d5c546565d7f9f8c63a644c84cb50`.
- [Original QHE paper, version 1](https://arxiv.org/html/2406.14712v1): 101 tasks and greedy-decoding pass@1. Those published scores are not directly comparable with a modern 151-task run.
- [IBM Qiskit Code Assistant evaluation table](https://quantum.cloud.ibm.com/docs/en/guides/qiskit-code-assistant): reports normal/hard scores and model-specific system prompts.
- [Google SDK migration](https://ai.google.dev/gemini-api/docs/migrate): supported `google-genai` client.

Sources accessed 2026-09-13. Published numbers are comparison references, never targets used to tune the evaluator until a model achieves them.
