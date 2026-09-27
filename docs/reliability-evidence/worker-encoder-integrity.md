# Candidate-side encoder integrity: local protocol-3 reproduction

The protocol-3 worker executes candidate code and then calls its `encode`
global on the returned object in the **same Python process**. The candidate
has no private tests or authority to issue a trusted verdict, but it can still
modify that encoder before its returned value is serialized. A trusted judge
then sees only the reconstructed wire value. This distinction matters for tasks
whose public contract requires a native Qiskit return object.

The [reproducer](worker-encoder-integrity-probe.py) runs the actual
`engine/src/graybench/worker.py` loop with authored local input and in-memory
stdio. It substitutes temporary paths for the container's `/input` mounts;
it does **not** invoke Docker or a model. The ordinary control returns a
`Statevector` storing `|01>` and the trusted task-2 development checker rejects
the reconstructed value. The adverse candidate also returns an object whose
raw `_data` stores `|01>`, but changes the worker module's `encode` global from
inside the candidate call frame. The encoder then emits a valid Phi-plus
`Statevector` record. The same trusted checker accepts that reconstructed value.
This works after the narrower `Statevector.data`/`dims` raw-field fix because
the candidate replaces the encoder function itself.

The byte-preserved [record](GrayBench-worker-encoder-integrity-probe.json)
has SHA-256
`b3c2ad1ff730cfaaab5c4f26110c277ea18fce54a9ccd7db3c3bb11f03a80203`.
It binds Python 3.12.14, Qiskit 2.4.2, source-manifest digest
`3ec20f5052a6fbdb048796c119a9774bc529814b4c16e3874f13116eaadee880`,
the script hash, raw amplitudes observed at the candidate function's return
before worker encoding, reconstructed amplitudes, wire digests and checker
outcomes. A second run produced byte-identical JSON. Reproduce from `engine/`:

```powershell
uv run --extra qiskit python ../docs/reliability-evidence/worker-encoder-integrity-probe.py --output "$env:TEMP\graybench-worker-probe-$(Get-Random).json"
```

Use a fresh output path because the script intentionally refuses to overwrite
prior evidence. This is an **in-process local diagnostic**, not a protected
Docker false pass, a model behavior observation or a released score. It proves
that the current worker protocol cannot attest that the candidate's native
returned object matched the reconstructed value under arbitrary Python code.
Value-only scoring can still make a valid, explicitly revised benchmark if
the public contract defines the value representation and the comparison
criteria. It must not be presented as fully faithful execution of every
original Qiskit HumanEval object contract. Native-object fidelity and the
task-2 development recipe remain release-ineligible until this threat-model
decision is resolved and protected adversarial controls run.
