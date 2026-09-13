# Reference environment v2

Use Python 3.12 and `uv sync --locked --extra dev`. The exact dependency versions are in `uv.lock`; the evaluator installs the hash-checked `requirements.lock` export. Core versions are Qiskit 2.4.2, Aer 0.17.0, IBM Runtime 0.45.0, NumPy 2.2.4 and Matplotlib 3.10.1. The Google SDK is `google-genai`.

The host coordinates API calls and storage. Model-generated code runs in the supplied Linux Docker image, which also includes Graphviz. No provider keys, repository or user profile are mounted in the evaluator. See [methodology](../docs/METHODOLOGY.md) for limits and [README](../README.md) for commands.

Reference preflights record the host Python/OS/packages, evaluator source fingerprint, immutable Docker image ID and full dataset identity. Live runs use that exact image. Rebuilding an image is an environment change; package repositories can change even when application dependencies are locked. Preserve the built image with `docker image save graybench-evaluator:2.0 -o evaluator.tar` when sharing an exact environment, and validate references after updates.

On 2026-09-13 the Docker environment passed all 143 offline references in each 151-task suite. The eight external-service tasks are explicitly excluded. The Windows subprocess audit passed only 140, illustrating why environment validation must precede model scoring. Do not substitute fake service responses or change assertions to obtain a full-suite pass.

Local subprocess execution is for reviewed reference/synthetic code only. Docker is required for live model execution. IBM service credentials are not part of this offline profile.
