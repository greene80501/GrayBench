# Explicit development evaluation recipes

Campaign planning now freezes one named recipe and uses it for generation,
protected judgment, resume, summaries and paired comparisons. `upstream` remains
the default. These selections are development evaluations, not certified scores.

| Recipe | Supported family | Public request |
|---|---|---|
| `upstream` | Existing supported upstream boundaries | Original pinned prompt |
| `qhe0-size-domain-v1` | Task 0 | Original pinned prompt |
| `qhe2-bell-statevector-v1` | Task 2 | Explicit Qiskit Statevector, two-qubit and amplitude-tolerance contract |
| `task82-file-semantic-v1` | Task 82 | Original pinned prompt |
| `task82-file-semantic-v2` | Task 82 | Original pinned prompt; reject files without the required QPY magic |
| `qhe141-pauli-group-anticommutator-v1` | Task 141 | Explicit Pauli contract appended before request freezing |
| `qhe113-barrier-metrics-v1` | Task 113 | Explicit observable metrics and no-mutation contract appended before request freezing |
| `qhe116-evolution-semantics-v1` | Task 116 | Explicit evolution matrix, phase and behavioral scoring contract |
| `qhe120-diagonal-semantics-v1` | Task 120 | Explicit diagonal, global-phase allowance and no-mutation contract |
| `qhe63-explicit-bases-v1` | Task 63 | New three-argument BB84 task with receiver bases supplied publicly |

Select exact tasks; a revision rejects other families rather than filtering or
falling back. From `engine/`, with a model specification and an inspected immutable
image ID, the task 141 example is:

```powershell
uv run graybench campaign-plan model.json ../data/datasets pauli-setup.json --name pauli-development --image $image --evaluation-recipe qhe141-pauli-group-anticommutator-v1 --task normal/qiskitHumanEval/141 --task hard/qiskitHumanEval/141
uv run graybench campaign-create pauli-setup.json ../data/datasets pauli.sqlite
uv run graybench campaign-step pauli.sqlite RUN_ID ../data/datasets
```

Each step performs at most one generation or judgment. Planning and creation do
not call the model. Generation uses the configured provider and may incur costs.
Use the returned run ID and `--docker PATH` if Docker is not on PATH.

The setup binds the recipe and applicable limits. Task 82 propagates its output
limit to candidate, isolated QPY decoder and oracle; parser timing is separately
bound. A real Docker regression verifies that an oversized parser response stops
at the parser boundary. A parser rejection remains unscored, not an automatic
incorrect answer.

For either task 82 file recipe, `campaign-plan --parser-image sha256:...` freezes
a separate QPY decoder image. The candidate and oracle keep `--image`.
The parser digest is stored in the setup and judge identity; changing it after
planning fails cohort validation. The option is rejected for other recipes.
The patched-parser development build and controls are documented in
[task82-semantic-track.md](task82-semantic-track.md).

Task 141 revisions are reconstructed before cohort validation and provider
request hashing. Original task records cannot be substituted after planning.
Private tests and references remain outside provider requests. Saved contexts
identify the recipe in summaries; that field records the declared setup and is
not independent certification. Old context-free runs report no declared recipe.

`comparison-plan` loads revised tasks from both setups. `compare` reconstructs
strengthened tasks from both saved run contexts and validates their protocols.
The existing context-free upstream comparison path remains supported. Do not mix
upstream scores with revisions or silently rejudge old answers against new public
contracts. Source-bound historical runs require their original engine bytes and
runtime; these changes do not upgrade old evidence.

## Retained integration evidence

`GrayBench-v3-evaluation-recipe-demo.json` and its SQLite ledger record six runs:
valid and invalid authored answers for each of the three revision recipes, each
covering the pinned normal and hard variants. All twelve protected judgments
matched their expected outcome: six passes and six failures. HTTP responses were
deterministic authored fixtures, not model generations. No model API was called.

Each comparison plan was saved before its generation fixtures. The ledger binds
setup, source, public requests, raw responses and protected judgments; verification
passed. Source bytes remained unchanged across the demonstration. All comparisons
remain publication-ineligible. A single family per comparison cannot estimate
between-family uncertainty; these fixtures establish lifecycle behavior only.

Tests additionally cover wrong-family selection, unknown recipes, setup round
trips, changed limits, private sentinels and CLI reconstruction. Independent oracle
certification, full task admission and live provider calibration remain unfinished.

Report SHA-256: `e54753eb47c871f91106a06563ecf92dfe9ad1cf1e6c34d6403a009e11c2e37f`.
Ledger SHA-256 after close: `5a216c9741d39dc141c0df77313e4a7af8fd655cb7b9513d13993b38b4270611`.
The report is retained as [evaluation-recipe-demo.json](evaluation-recipe-demo.json).
It binds actual worktree bytes, which may differ from Git LF blobs on Windows.
Final validation: 365 tests passed with Docker enabled in 136.20 seconds, with
no failures, errors or skips; Ruff lint and formatting passed.

The [task 116/120 gate revisions](gate-semantics-revisions.md) use independent
expected matrices over varied inputs. They score returned behavior and explicitly
do not certify the named synthesis/construction procedure.

The [task 63 explicit-bases revision](task63-explicit-bases-revision.md) replaces
hidden receiver-basis randomness with a public third argument in a separate
development recipe. Protected positive implementations and mutants pass their
predeclared controls, but the finite task remains release-ineligible.

The [task 2 Bell-state revision](task2-statevector-revision.md) replaces the
upstream call to candidate-controlled `equiv` with a trusted amplitude check.
Its native controls pass, but protected execution and task admission remain
pending.
