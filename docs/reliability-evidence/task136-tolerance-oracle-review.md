# Task 136: one tolerance cannot verify an epsilon-parameterized answer

Both pinned prompts ask for ten density matrices that are pure up to the
provided tolerance `ε`. The unmodified normal and hard tests call the
candidate only once, with `ε = 0.01`, then require ten `DensityMatrix`
objects whose Qiskit entropy is strictly below 0.01. They do not vary the
supplied tolerance.

The [protected-bridge diagnostic](task136_oracle_probe.py) ran the exact
pinned tests in the Python 3.12.14 / Qiskit 2.4.2 evaluator image. In each
suite, the canonical answer and a genuinely pure fixed-state control passed.
A deliberately wrong function that ignores `ε` and always returns ten copies
of `DensityMatrix([[0.9996, 0], [0, 0.0004]])` also passed. Qiskit gives that
state entropy `0.005092047537180205`: it meets the tested 0.01 bound but
fails the same public requirement for the valid tighter tolerance 0.001.
An obviously mixed-state control and a nine-state control both failed.

The [saved ten-case result](GrayBench-task136-oracle-probe.json) has SHA-256
`8d46eb4f78acc6a31d66af52d40006033bc7736cfaff4dd04368286a1c27456f`.
It binds pinned dataset and task digests, completion and judge digests, image
and runtime versions, and the independent smaller-tolerance witness. No
model or external service was called. This is oracle evidence, not a score.

For a separately versioned semantic track, declare a positive-tolerance
domain and test multiple values, including a tighter value that distinguishes
an `ε`-blind near-pure answer from one that meets the input bound. Accept
pure states at every positive tolerance; randomness and distinctness are not
in the public requirement. Keep the pinned tests unchanged for the native
reproduction track. Both task variants remain release-ineligible.
