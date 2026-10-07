# Planned exact binary comparisons

This is an opt-in development analysis beside the existing paired family
bootstrap. It uses one complete binary observation per task family, with an
explicit operator declaration explaining pairing, independence across families,
and justification for the conditional null. Distinct family names do not
establish these assumptions.
Normal and hard versions of a family, or repeated generations, cannot enter
this test as separate independent observations. They need a cluster-aware
analysis. The original bootstrap schema and historical report identities are
unchanged.

The paired-population null is equal marginal pass probabilities for the two
frozen conditions. Exact binomial calibration additionally requires independent
discordant directions with probability one half under that null, conditional on
discordance. Equal aggregate rates over a fixed heterogeneous task cohort alone
do not supply that condition. The declaration does not prove a sampling model
or make the benchmark a random sample of all possible tasks.
For discordance counts `b` and `c`, the conditional two-sided McNemar p-value is
`min(1, 2 * sum(C(b+c,k), k=0..min(b,c)) / 2**(b+c))`.
No discordances gives p=1. The descriptive effect is `(b-c)/N` over all pairs;
the p-value is not a probability that one model is superior. The exact binomial
choice follows the [statsmodels McNemar documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html).

A study freezes every named contrast and its alpha before analysis. Holm uses
step-down Bonferroni adjustment, as described in the
[statsmodels multiple-testing documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html).
Sorted p-values receive the cumulative maximum of `(m-rank)*p`, capped at one.
Raw and adjusted probabilities and alpha comparisons use exact fractions.
Holm permits dependence across contrasts, but requires valid individual p-values.
Hexadecimal numerator/denominator strings preserve probabilities beyond float
range and Python's decimal integer serialization bound. Underflowing positive
probabilities have `float_value: null`, never a displayed false exact zero.
Alpha is interpreted as the decimal spelling of the validated finite float.
Adjusted p-values equal to alpha reject the null; this is a conditional test,
not a model ranking or an equivalence test.

The implementation bounds analysis at 10,000 pairs per contrast and 100
contrasts per study. These are explicit computational bounds. Repeated or
related observations are refused regardless of those limits. Each pair must
match task bytes, public requests, track, suites/populations/exclusions, judge,
runtime, prompts, extraction, retry and source identities. Protocol differences
in model/settings remain described and are not certified equivalent.

Every planned contrast must have an input and actual bound task records.
Missing or extra named inputs are errors. An incomplete/unsupported run
withholds that pair's statistics and the whole study's Holm results. Complete
pairs remain visible as explicitly uncorrected results. Exact duplicate protocol
pairs, including side-reversed pairs, cannot inflate a study's hypothesis set.
Two-sided duplicate names and duplicate JSON object keys are refused.

Example commands (setup and ledger files already exist):

```text
graybench binary-comparison-plan left-setup.json right-setup.json CACHE ab.json --configuration-comparison "Declared condition differences" --independence-basis "Justification for pairing, independence and conditional null"
graybench binary-study-plan contrasts.json study.json --purpose "All planned primary contrasts" --alpha 0.05
graybench binary-study study.json runs.json CACHE report.json
graybench binary-study-verify study.json runs.json CACHE report.json
```

`contrasts.json` maps each planned ID to a binary plan filename, for example
`{"ab":"ab.json","ac":"ac.json"}`. Filenames resolve relative to that JSON
file. `runs.json` maps the same IDs to objects with exactly `left_ledger`,
`left_run`, `right_ledger`, and `right_run`; ledger filenames resolve relative
to the runs file. Absolute filenames also work. One contrast is a valid study.
Use one suite per pair unless unrelated families across suites are explicitly
selected. The same normal/hard family cannot be duplicated within a pair.

Output creation is exclusive. Analysis opens existing SQLite ledgers in read-only
mode without creating schema or rows; SQLite may still manage WAL/shared-memory
sidecars. Verification rebuilds the complete report from the frozen study,
actual tasks and verified ledger snapshots, then compares canonical JSON.
Changed counts, decisions, source, plan, run mappings or claims fail replay.
Replay requires the same consistent ledger snapshots used for analysis; later
appends, including unrelated runs, can change global verification metadata.
Archive consistent SQLite backups after campaign closure rather than copying a
live database without its WAL state. This proves local consistency, not external
author authenticity. Freeze the
study, selected runs and reporting policy before observing outcomes; these
commands do not prove preregistration timing or prevent selective study creation.
All results remain `publication_eligible: false`.

[Arithmetic calibration](artifacts/exact-binary-analysis-2026-10-07/README.md)
retains a SciPy binomial comparison grid and a separate closed-intersection
enumeration of Holm examples. The
[SciPy binomial documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html)
defines the independent float implementation used in that check. Synthetic
ledger and CLI tests cover complete and incomplete studies, read-only evidence,
tampering, context binding and input validation. These checks do not qualify
independent tasks, provider behavior, model performance or isolated execution.
