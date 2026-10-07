# Bell sampling: private checks and conditional shot calibration

The [source-bound bundle](artifacts/bell-shot-diagnostics-2026-10-07/README.md)
examines the exact pinned normal and hard Tasks 1, 14, 15 and 31. It executes
their complete check function AST bodies on trusted returned-data fixtures.
Imports outside those functions, actual candidate implementations, samplers and
transpilers do not run. These observations cannot attest how data was produced
or establish a full native task false pass or observed sampler rejection rate.
Original tasks, thresholds and historical scores remain unchanged.

## Task 1: an unstated shot count changes acceptance

Both prompts explicitly request phi-plus, a level-1 pass manager and a Sampler
with an Aer backend. Neither specifies shots. The reference uses 1000, but that
private implementation is not a public requirement. Both check functions demand
exactly the `00` and `11` keys and strictly between 0.4 and 0.6 of the total in
`00`. They do not validate count positivity or integrality: negative balanced
counts and fractional counts pass; a zero total raises ZeroDivisionError.

For independent ideal Z measurements of phi-plus, each shot has probability
one half for each outcome. With `n` shots and `k` results of `00`, the strict
condition is `2n < 5k < 3n`. Exact acceptance is the sum of `binomial(n,k)/2^n`
over those integers. An independent integer recurrence agrees, and both exact
pinned checks agree on all 20,820 possible count-vector trials for
`n = 1..128, 1000, 1024`. Exhaustive ordered sequences through ten shots and an
independent Pascal-row test also agree.

| Shots | Conditional ideal rejection probability |
|---|---|
| 1 | 100% |
| 2 | 50% |
| 3 | 100% |
| 4 | 62.5% |
| 5 | 100% |
| 10 | 75.390625% |
| 100 | approximately 5.688793% |
| 1000, reference choice | approximately `2.728464 × 10^-10` |

These are probabilities under the declared ideal independent-shot assumption,
not measurements of Aer. A valid low-shot implementation can have a different
opportunity to pass than the reference. The tiny 1000-shot tail also means this
calibration alone does not explain a large discrepancy in a reference-like pilot.

## Task 14: missing the explicit 100-shot obligation

Both prompts require 100 per-shot measurement results. Their checks require a
nonempty list containing both bitstrings, but omit its exact length. Trusted
lists of two, 99 and 101 shots pass. A legitimate all-identical 100-shot ideal
sample fails. Its conditional probability is exactly `2/2^100 = 2^-99`, about
`1.577722 × 10^-30`. The missing length requirement is material; the ideal tail
is negligible in ordinary runs but remains a mathematical false-rejection event.

## Task 15: Bell identity and noise remain underspecified

The prose requests a Bell circuit and Aer execution, without naming its Bell
variant or a noise model/rate. The function name `noisy_bell` and the normal
FakeBelemV2 import provide cues; the private reference uses that backend's noise
model. Those cues do not specify a calibrated public noise condition, and hard
does not supply the import prefix. This is a contract question requiring review.

The check demands that total counts differ from the sum of `00` and `11`.
Ideal phi-support counts fail; psi-support counts raise KeyError. Negative error
counts, fractional counts and an invalid label pass. These are check-function
observations on data, not observed outcomes of valid alternative sampler code.

For a specified independent probability `q` of an event outside phi support,
the probability of observing none in `n` shots is `(1-q)^n`. The report retains
exact rational values for illustrative `q` values. This describes that event
only. It is not the full check failure rate: missing keys can also raise errors,
and no backend noise model was calibrated. With no outside events, the check
cannot pass. A replacement must resolve Bell identity, backend/noise data, shots,
register mapping and statistical policy before generation.

## Task 31: a seed does not specify the private snapshot

The prompt specifies seed 42, but not shots or the Bell variant. Its check
requires exactly `{"00": 521, "11": 503}`, implicitly totaling 1024. Other
totals and psi-support data fail; integral floating values pass dictionary
equality. Seeded sampler behavior has not been executed in this diagnostic.

The root historical runtime lock selects qiskit-ibm-runtime 0.45.0. Its
[versioned SamplerOptions source](https://raw.githubusercontent.com/Qiskit/qiskit-ibm-runtime/10aea649ca998ff7924f0561e41142550aa07242/qiskit_ibm_runtime/options/sampler_options.py)
documents a default of 4096 shots when no PUB or run-level count is supplied.
However, its [local service](https://raw.githubusercontent.com/Qiskit/qiskit-ibm-runtime/10aea649ca998ff7924f0561e41142550aa07242/qiskit_ibm_runtime/fake_provider/local_service.py)
delegates to BackendSamplerV2 and supplies a default-shot option only when present.
The [Qiskit 2.4.2 BackendSamplerV2 source](https://raw.githubusercontent.com/Qiskit/qiskit/5a1cf3159aedad954767956d6a5c81a06d043d71/qiskit/primitives/backend_sampler_v2.py)
defaults to 1024. These paths differ. Generic Runtime documentation alone cannot
establish a 4096-versus-1024 error in this local Aer reference. IBM's
[shot-option guidance](https://quantum.cloud.ibm.com/docs/en/guides/sampler-options)
also distinguishes PUB, run and option settings. Verify the actual local path,
effective shots, seed and exact results under the frozen versions; neither
evolving examples nor source-level defaults attest an observed execution.
The [source review record](artifacts/bell-shot-diagnostics-2026-10-07/runtime-source-review.json)
pins both release tags to immutable commits and records all three raw source
hashes separately from the statistical plan.

## Required follow-up before release

Keep native reproduction unchanged and source-bound. For strengthened tasks,
publish the exact output domain, Bell identity, shot/resource policy, measurement
labels, backend/noise identity and seeded-runtime guarantees before generation.
Map every scored clause to positive alternatives and meaningful wrong controls.
Specify and independently calibrate any statistical false-rejection allowance;
one finite sample cannot prove the distribution or a Sampler invocation.

Return-value validation cannot authenticate a pass-manager or Sampler call.
Scoring construction/execution obligations requires a separately designed and
qualified process boundary; a value-only revision must explicitly disclose the
changed claim. Correct-looking fabricated values cannot become evidence of
execution. Runtime, adversarial qualification and independent human admission
remain pending. This diagnostic makes no replacement-judge or model-score claim.
