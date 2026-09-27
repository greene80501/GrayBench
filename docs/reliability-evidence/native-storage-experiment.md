# Registered native storage experiment

The current SciPy 1.18.1 experiment instruments the two matrix-function native
allocation sites and provides bounded registration, byte read/write and a
receiving-side array factory. This is adapted runtime behavior, not a verified
upstream reproduction or an admitted benchmark transport.

The exact development image is
`sha256:46097c2b63d5fc0c605641424d65eb3eac6782b9a7aa2ac9ed96d12fc13422d4`.
The SciPy wheel built in that image had SHA256
`e97c7c19bbc2e7388171df77681af94fd828a92c913988d822ca3b862a4ccf03`.
The installed build context and patched source both contain the same native
header, SHA256 `050d8638a262446f0fc1a151f2e9b2ee12446dec297424310b3e06997482c21e`.
The patch script in the image has SHA256
`516dc7ca1a91e8f525cc801b914ab5297dfb1aa71e7d9ecf018faa4723ef680b`.
The source archive and exact original C file are checked before patching in
`engine/native/patch_scipy.py` and the development Dockerfile.

`GrayBench-native-storage-experiment-with-asan.json` records the image digest,
workspace source and test hashes, exit codes and captured output for four
standalone native integration checks plus the AddressSanitizer reentry harness.
All five returned zero. The factory test first failed against the preceding
two-phase image because the constructor was absent, then passed after the
factory was built. A prior ASan run of the production registry header detected
a heap-use-after-free during nested destructor cleanup; the two-phase sweep
passed the same test, including multiple retired capsules. An independent
read-only review found no further concrete native lifecycle blocker in the
bounded helper and factory.

This experiment retains capsule identities in a process-global registry until
a later registration sweeps unused entries. That changes destruction timing.
The build installs unpinned apt and isolated Python dependencies, so the
development image is evidence of behavior on this host, not a reproducible
release recipe. The registry and factory are not connected to graph transport.
Capsule, root-array and view identity; private transaction validation; protected
snapshot and delta execution; full regression; reference replay; resource
calibration; and oracle review remain open. The existing Hamiltonian graph
controls still fail on the original protected image. Nothing in this experiment
is a model score or certification evidence.
