# Exact binary analysis: arithmetic and workflow checks

[calibration.json](calibration.json) retains deterministic arithmetic checks for
the opt-in McNemar/Holm analysis. No model, provider request, candidate execution
or container runs in this report. Sampling assumptions, task admission and
publication eligibility are not established. See the
[analysis contract and commands](../../exact-binary-comparisons.md).

The exact conditional two-sided tail agrees with SciPy's independently
implemented binomial test over 961 small-count combinations and six boundary
cases, with maximum absolute float difference `9.992007221626409e-16` against
the declared `1e-14` tolerance. The boundary set includes balanced 10,000-pair
counts and probabilities below float range. Extreme all-one-direction tails
also match an exact power-of-two identity; a SciPy float zero alone is not a
validation of an extreme rational probability.

Holm adjustment agrees with separate enumeration of all closed Bonferroni
intersection hypotheses for 216 three-contrast probability vectors. All six
orderings of each vector agree, totaling 1,296 permutation checks. The record
also checks exact underflow preservation and the inclusive alpha boundary.
This finite grid is a calibration, not a proof for every possible input or a
validation of any real campaign's assumptions.

Environment: Python 3.12.14, SciPy 1.18.1, NumPy 2.2.4.
Engine source:
`40bdde3c2b242d74b82056cfc33ed996126264b4d3d4ffff72a1ac93bf951953`.
Engine lock SHA-256:
`b0789c7a994abdd96b3172563ae58a420c60e80c33ba05447257e1d35174524d`.
Calibration script SHA-256:
`aa1f83104711254734c2cf566e12699dc86158daa11524a74fc614a93b09c410`.
Report: 614,995 bytes, SHA-256
`53ac561a05b3b9c2350f76d345a7bf76f05b10b9074fe65d2ebaa46623402fbf`.

From `engine/`, with locked dependencies:

```text
python ../docs/reliability-evidence/binary_analysis_calibration.py ../docs/reliability-evidence/artifacts/exact-binary-analysis-2026-10-07/calibration.json --check
```

Creation refuses to overwrite evidence. Verification rebuilds the complete
record, including source, script, lock and package identities, and compares
canonical JSON. The main environment exactly recreated the report.

The [focused corrected-source tests](focused.xml) passed 93 tests, skipped two
Docker-dependent groups, and had zero failures/errors. Pytest wall time was
44.77 seconds; JUnit records 44.737 seconds. Twelve warnings concern existing
Windows temporary-directory cleanup. The selected files cover the new binary
analysis, legacy paired comparisons, ledger/ledger evidence, summaries and
campaign CLI. All 20 new binary tests passed. Synthetic ledgers cover complete
and unsupported studies, named-input coverage, tampering, null report rejection,
duplicate JSON fields, read-only file preservation, frozen native/protected
contexts, repeat/family refusal and exact underflow. They are not model evidence.
Focused JUnit SHA-256:
`772e4bb766a5d3692ce1331d07639db8bb625835b1a3981bd3feafb448e77f82`.

Code review caught a report-assumption omission: independence alone and equal
aggregate finite-cohort rates do not establish the conditional binomial null.
A regression failed before correction. Saved reports now name independent
Bernoulli(1/2) discordant directions under the paired-population null, and the
operator declaration covers pairing, independence and that conditional null.
Bounded review reproduced the corrected regression and found no further
important issue. This is code review, not independent human task admission.

Ruff lint and formatting pass for 240 engine/calibration files. No full-suite
validation of this final source or clean-machine qualification is claimed here.
Original benchmark results and historical source-bound reports are unchanged.
