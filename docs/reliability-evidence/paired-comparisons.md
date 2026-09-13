# Explicit development comparisons

`comparison-plan LEFT_SETUP RIGHT_SETUP CACHE PLAN --seed SEED --configuration-comparison TEXT`
freezes two protocols, task families, source, resample count (default 10,000),
confidence level (default 0.95) and a description of configuration differences.
It uses pinned task records and regenerates public requests for each model.
Create the plan before dispatch; file creation does not externally attest that timing.

`compare PLAN LEFT_LEDGER LEFT_RUN RIGHT_LEDGER RIGHT_RUN CACHE OUTPUT` revalidates
task/family identity, protocols, analysis source and both complete ledger reports.
It creates an exclusive output file. Unsupported or incomplete cohorts stay unscored.
Different task sets, repeats, system prompts, extraction, retry policy, evaluation
track, judge, runtime or code identity are rejected. Effective equivalence of model
settings requires separate calibration and is explicitly not certified.

The estimate is left minus right mean single-attempt success. Whole families are
sampled with replacement using the same indices for both models. Normal/hard
variants and observed repeats remain together. Summed pass differences are divided
by sampled slot totals, preserving task weighting for unequal family sizes.

The exploratory interval uses percentile endpoints with linear interpolation and
a frozen Python 3.12 Random/randrange seed. Python identity and the distribution
digest are recorded. With fewer than two families or no empirical between-family
variation, the report withholds the interval and gives a reason. It does not claim
certainty from a collapsed interval, a p-value, or a universal ranking.

This is **task-family resampling uncertainty conditional on observed generations**.
It assumes exchangeable families; the benchmark is not a probability sample of all
possible tasks. Independent generation variability, multiple comparisons, coverage
calibration and alternative interval methods remain required work. Small or unusual
samples can have poor percentile-bootstrap coverage. Reports remain development-only.

The paired-index construction and percentile procedure follow the
[SciPy bootstrap reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html),
which also describes other commonly used interval methods. Stochastic generation
uncertainty is a separate concern; see
[Towards Reproducible LLM Evaluation](https://arxiv.org/abs/2410.03492).

Tests cover a two-family distribution with known support, unequal cluster sizes,
sign reversal, seed/order reproducibility, degenerate intervals, family identity,
incompatible protocols, unsupported cohorts and CLI creation without overwriting.
Synthetic fixture results are not model benchmark scores.

Validation:269 tests pass with Docker enabled, zero failures/errors/skips; lint,
format and credential-value checks pass. An offline plan from the real pinned
datasets contains302 tasks in151 two-variant families. Its digest is
`8bfdde50f033ddf759eed4ce183e03df42d16b0918bfc7261e29f77147ac72c9`.
The plan uses explicitly unverified placeholder models; no API requests or model
results are implied.
