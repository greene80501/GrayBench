# Explicit task 113 barrier-metrics revision

`qhe113-barrier-metrics-v1` is a development recipe, separate from upstream scores.
It addresses the constant-result and wrong-return-type false accepts reproduced
in the [contract review](task113-contract-review.md).

The public addition is frozen before generation. It specifies a PropertySet with
Python or NumPy integer metrics (not booleans), total quantum-plus-classical width,
depth after removing only barriers while preserving other instructions and order,
and no mutation of the supplied circuit. Extra result entries are permitted.
Scoring assesses returned metrics; it cannot certify the internal procedure used.
Unsupported mutation remains unscored at the existing bridge boundary.

Nine fixed circuits cover zero to five qubits, empty circuits, classical bits,
cases where barriers change depth and where they do not, repeated and partial
barriers, measurements, and consecutive X gates that must not be canceled as an
extra optimization. Expected metrics are computed from a circuit rebuilt without
barriers, independently of the reference's RemoveBarriers pass-manager path.

The revised prompt ends with a newline in both prompt formats. Original task
records are rejected by this judge until revised; a saved campaign reconstructs
the same revised public request and task/test identities. The recipe rejects
other families and entry points before dispatch. Original datasets and their
upstream checks are preserved.

From `engine/`, select both variants explicitly:

```powershell
uv run graybench campaign-plan model.json ../data/datasets barriers.json --name barrier-metrics --image $image --evaluation-recipe qhe113-barrier-metrics-v1 --task normal/qiskitHumanEval/113 --task hard/qiskitHumanEval/113
```

Use the existing campaign-create, campaign-step and comparison commands with this
setup. Generation may incur provider costs; planning does not call the provider.

Finite fixed cases cannot prove general correctness or resistance to hardcoding.
This public dataset is development material, not an untouched holdout. Independent
review of the scientific contract, broader input coverage and release admission
remain outstanding. The recipe is always publication-ineligible.

## Validation evidence

The [16-case protected replay](GrayBench-v3-barrier-revision-evidence.jsonl) covers
both pinned suites: references and manual-filter alternatives pass; plain
dictionaries, constant PropertySets, unchanged-depth results, qubit-only widths,
boolean widths and floating-point widths fail. All expected outcomes matched.
SHA-256: `d40b128bbd005fd709fc73ead69d35e0b378e358e2536b37a9ef3ba57e03ac9d`.
The chain records original and revised public/task digests, authored answers,
actual engine bytes, protected transcripts and the immutable image. These are
validation fixtures, not model generations; no model API was called.

The full Docker-enabled suite passed 384 tests in 163.58 seconds. After lint cleanup,
the 20 affected recipe tests passed in 22.31 seconds. Ruff lint and format checks
pass. A separate scoped review found no actionable issues; this is code review,
not independent scientific certification.
