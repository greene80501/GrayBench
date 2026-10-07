# Repeated-sample metrics: arithmetic and workflow evidence

[calibration.json](calibration.json) checks the exact empirical pass@k fraction
against enumerated subsets and a fixed OpenAI HumanEval numerical function.
No provider request, model generation, candidate evaluator or container runs
in this calibration. See the [frozen analysis contract](../../repeated-sample-metrics.md).
These are arithmetic and synthetic workflow checks, not model scores.

For every n=1..12, every success count and every valid k, independently enumerated
nonempty candidate subsets agree exactly with the rational estimator: 728 cases.
The subset reference counts bit masks; it does not use the estimator's binomial
formula. The pinned HumanEval function agrees within the declared absolute
tolerance of 1e-13 on 3,185 cases: all counts/k for n=1..20 and declared boundary
cases for n=30, 100 and 1,000. Maximum float difference is
`5.551115123125783e-16`. Pass@1 also agrees exactly with c/n. This finite grid
does not prove every possible input; float agreement alone does not certify
an extreme complement close to zero or one.

The [public numerical reference](https://github.com/openai/human-eval/blob/6d43fb980f9fee3c892a914eda09951f772ad10d/human_eval/evaluation.py)
is commit `6d43fb980f9fee3c892a914eda09951f772ad10d`, Git blob
`9ce96dfc4cb4c553e41e4530b710fdf94d4442f5`. Its complete-file SHA-256 is
`e926d5e9b8f1ec040096cd5952e8cf79f8dc0b7fb80ba6667ce604ffea0397bc`.
The explicitly supplied file is rejected before parsing/execution if any byte
differs. Only the reviewed `estimate_pass_at_k` function is compiled; module
imports and evaluator/candidate execution never run. The selected function's
source-fragment SHA-256 is
`61bff87c81fbf4b1c8c26158ef39a938a121e66a905d125ef6fcb4b00ef4ff11`.

Environment: Python 3.12.14, NumPy 2.2.4. Engine source:
`0cb4b0ac158e5e48ae2e5ba5f3e9050b1532b6c6a24cbb015c13b04524307b9e`.
Engine lock SHA-256:
`b0789c7a994abdd96b3172563ae58a420c60e80c33ba05447257e1d35174524d`.
Calibration script SHA-256:
`ef1940284f4fbc248b6984a068700a775025879c85724d9ac0ba7ffe8fbd79a2`.
Report: 1,111,063 bytes, SHA-256
`41e9211a669877b9ccea1879993d5b9fc5a61f8e3efff8244d7d04900d9a6ae4`.

From `engine/`, with locked dependencies and the exact reference file saved as
`REFERENCE.py` at an explicitly chosen path:

```text
python ../docs/reliability-evidence/sample_metrics_calibration.py REFERENCE.py ../docs/reliability-evidence/artifacts/sample-metrics-2026-10-07/calibration.json --check
```

The reference can be obtained from the fixed public commit URL above; its bytes
are not included in this artifact. Creation refuses to overwrite evidence.
Verification reconstructs all counts, fractions, source/script/lock identities
and environment fields, then compares canonical JSON. The main environment
exactly recreated the complete report.

The [focused JUnit](focused.xml) records 111 passes, two Docker-dependent skips
and zero failures/errors. Pytest wall time was 48.30 seconds; JUnit records
48.272 seconds. Twelve warnings concern existing Windows temporary-directory
cleanup. The seven selected files are `test_sample_metrics.py`,
`test_binary_comparison.py`, `test_comparison.py`, `test_ledger.py`,
`test_ledger_evidence.py`, `test_summary.py` and `test_campaign_cli.py`.
All 18 new sample-metric tests passed. They cover exact subset arithmetic,
strict invalid-count refusal, unequal family sizes, retained failure/error/timeout
denominators, incomplete-cohort withholding, actual native/protected setup
binding, saved-report tampering, read-only ledger preservation, exclusive report
creation and the reference-file guard before execution. Synthetic outcomes
do not establish oracle adequacy or provider behavior. Focused JUnit SHA-256:
`07fbf8b77a714520351c03f43063b4dc0f48f9cf10d5ef624dcaf3351441a7c1`.

Bounded read-only code review found no important issue and independently ran
55 focused sample/comparison/binary tests with two Docker skips. It exactly
recreated the 3,185/728-case calibration. The missing artifact README noted
during review is supplied here. This is software review, not independent human
task admission or a separate-machine reproduction.

Ruff lint and formatting pass for 242 engine/calibration files using the explicit
`engine/pyproject.toml` configuration. No new full-suite validation is claimed.
Pass@k describes multiple-candidate opportunity; future independent k-draw
inference requires iid fixed-policy sampling. No confidence interval,
preregistration timing certification, task admission, provider conformance or
runtime qualification is supplied. All reports remain publication-ineligible.
Historical source-bound evidence and original benchmark results are preserved.
