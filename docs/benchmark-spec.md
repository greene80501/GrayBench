# Benchmark specification v2

The authoritative rules are in [METHODOLOGY.md](METHODOLOGY.md). This replaces the original January 2026 specification.

- Official Qiskit HumanEval normal and hard data, pinned by immutable revisions and full-content hashes.
- One returned generation per task; no answer repair, failure-only regeneration, hidden-test feedback or tools.
- Official prompt verbatim. Normal includes its public code prefix; hard retains the required name and argument contract.
- Default output cap 16,384 tokens. Temperature zero/top-p one where the API accepts them; record actual parameters. No token cap guarantees enough reasoning capacity, and temperature zero does not guarantee deterministic output.
- Frozen reference-validated task IDs, Docker image and source fingerprint. Offline coverage is 143/151 for each suite in the validated environment.
- Mechanical Python/untagged fence extraction preserving block order and helpers. Other fenced languages are skipped as complete blocks; no syntax or import repair.
- One check invocation. Structured completion evidence plus successful exit is required. Resource limits are documented in the methodology.
- Operational API failures prevent a completed benchmark score. Empty returned answers and generated-code failures remain failures.
- Report numerator/denominator, coverage, actual request/response, uncertainty and provenance. Separate comparison cohorts; preserve all runs.

A passing answer satisfies these tests, not a proof of universal correctness. Any future augmented-test, agent or repair evaluation must be labeled separately from the official-test track.
