# Deep Windows checkout evidence replay, 2026-09-28

A separate clone of draft PR #3 at `c555241d5f0690fc018f9985a494facc4d40a49d`
was created under `outputs/graybench-repro-c555241`. It contained no virtual
environment. `uv sync --locked --extra dataset --extra qiskit --group dev`
created a Python 3.12.14 environment with 38 locked packages. Its engine
source digest matched the source-bound control bundle:
`1515370b867b0160d6da999ac908912ae24337aa60746a7f705cb83dd176a748`.

The clean checkout initially could not run `admission-bundle-verify` on the
[current-source successor](artifacts/admission-current-controls-2026-09-28/README.md).
The file was present in Git, and PowerShell could list it, but Python's
`Path.is_file()` returned false on the two long historical log paths. Their
canonical absolute lengths were 256 and 261 characters; adding the Windows
extended-length path prefix made the exact same files readable. The standalone
`oracle-review-inspect` path had the same failure on a 267-character control
log. This was a host path-access failure, not missing evidence or an oracle
outcome change.

The engine now converts read-only evidence paths to absolute extended-length
Windows paths before the admission bundle, reference-scan and oracle-review
readers open them. Two regression tests build real hash-chained synthetic logs
in deliberately deep directories and verify the public readers; each test was
observed failing before the fix and passing after it. The focused admission,
oracle-review and reference-scan suites passed with 26 passes and 3 skips.
The source-bound admission snapshot remains byte-for-byte unchanged. As with
any engine-source edit, its inventory source digest now differs from the
running engine; the verifier reports that difference explicitly.

The complete pinned-image suite passed after the fix: 1,475 passed, 5 skipped,
and 6 expected failures. Ruff lint and format checks passed.

Commit `29e50152188be37b5770ada4d2729c051bca7994` was pushed and pulled
into that separate clone with a fast-forward; the locked environment still
resolved to 38 packages. The cloned engine reported source digest
`41fcb45ca501f0c8ee3fbe490e492c98c6a24a9c4862636010123ec024d4f6f6`.
From the clone, `verify_admission_bundle` accepted all 60 controls in the
successor bundle, including 42 bound to its inventory source, with zero
different-source bindings. It accurately reported
`inventory_source_matches_running_source: false` because the path fix changed
engine bytes after the snapshot. Standalone `inspect_oracle_review` verified
the 18 task-62 controls in the 267-character-path log. The focused suite in
the clone passed with 26 passes and 3 skips; pytest emitted 12 warnings while
cleaning up older Windows temp symlinks after the tests.

This is a fresh checkout and Python environment on the same Windows host,
using the same pinned parquet cache and Docker image. It is not an independent
machine reproduction, an oracle adequacy review, or a model score.
