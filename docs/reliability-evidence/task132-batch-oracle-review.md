# Task 132: fixed counts do not establish batch execution

Both pinned prompts ask the candidate to generate six seeded random circuits,
optimize them for FakeManilaV2, partition them into two groups of three, execute
the groups using Qiskit Runtime Batch mode, and return the measurement results.
The normal and hard tests call the candidate once and check that it returns a
two-element list whose dictionaries equal one hardcoded count dictionary.
They do not observe circuit generation, transpilation, Batch use, Sampler calls,
or the association between each result and its submitted circuits.

The [exact-test probe](task132_oracle_probe.py) ran eight authored cases against
the unmodified pinned tests in the immutable Python 3.12.14 / Qiskit 2.4.2
evaluator image with network disabled. The canonical reference passed in both
suites. A function that only returns two copies of the hardcoded counts, with
no `Batch` or `Sampler` use, also passed in both suites. Changing one count
or returning a tuple instead of a list failed in both suites. The normal
`check` was invoked explicitly; the hard test invokes it itself. No IBM
account or model API request was made by this probe.

The canonical reference emitted a Qiskit Runtime warning on each sampler
submission: although a batch context was open, the job would run in job mode
because the sampler primitive had been initialized outside the context. Thus
even the reference's passing result does not establish Batch execution in this
pinned runtime. This warning describes the observed local execution; it is not
a claim about how the reference behaves in other Runtime versions.

The [saved UTF-8 result](GrayBench-task132-exact-oracle-probe.json) has SHA-256
`5af04c0164e70a7db7c209012e172af63b67e016c78e2f2f3a1ca46fd86d853d`.
It binds the probe source, dataset pins, task digests, candidate hashes,
runtime, eight outcomes and whether each authored function uses the named
batch/sampler APIs. This is authored native diagnostic evidence, not a
protected-judge run or a benchmark score.

The current return type cannot prove that a particular execution method was
used. A separately versioned task must either score a clearly stated output
contract without claiming Batch use, or define an independently verifiable
execution-evidence contract. Static source inspection or a returned statement
of method use would not by itself prove that execution happened. Keep the
historical upstream tests unchanged; task 132 is not admitted for a verified
score.
