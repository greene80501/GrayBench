# Evaluator runtime reproduction

The original evaluator image is pinned as
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`.
The root `Dockerfile` pins its Python base image and hashes every Python wheel,
but `apt-get update` uses live Debian mirrors. A local no-cache rebuild on
2026-09-28 produced a different image and upgraded three `libheif` packages
from `1.19.8-1+deb13u1` to `1.23.4-1~deb13u1`. That drift is enough to make
the root Dockerfile an unsuitable recipe for reproducing the original runtime.

`Dockerfile.pinned` is a separate reproduction recipe. It keeps the same
digest-pinned Python base and hash-locked Python requirements, but uses Debian
snapshot archives at `20260913T080000Z` and explicitly pins `graphviz` and
`libgomp1`. The original Dockerfile and all historical image references remain
unchanged. Build from the repository root:

```sh
docker build --no-cache --platform linux/amd64 -f engine/runtime/Dockerfile.pinned -t graybench-evaluator:reproduced .
docker image inspect graybench-evaluator:reproduced --format '{{.Id}}'
python engine/runtime/verify_runtime.py sha256:REPLACE_WITH_RUNNABLE_IMAGE_DIGEST
```

For a runtime release, building this specific Dockerfile without cache and
verifying the resulting digest is a required local gate. Pointing the verifier
at the original image only checks the old artifact; it cannot validate the new
recipe. The normal test suite can consume either image through
`GRAYBENCH_TEST_IMAGE`, so record which digest the suite used.

The verifier requires an immutable local `sha256:` image reference. It checks
the selected Linux/amd64 image with no network access, a read-only filesystem,
and a temporary `/tmp` mount. It fingerprints the sorted `pip freeze` and
`dpkg-query -W` inventories with LF line endings and a final newline, compares
counts and hashes to `package-fingerprint.json`, and runs a two-qubit Bell-state
Qiskit smoke test. A mismatch exits 1; a Docker or probe failure exits 2. A
match exits 0 and reports `matching_package_fingerprint`.

On the local Docker host, a no-cache build of this recipe produced runnable
image digest
`sha256:42ac1ae9115df9d72697f5d14b58215217f1ee49e2ed35b57bd4eebad03e4ba2`.
Both that image and the original passed the committed fingerprint: 96 Python
packages, 157 Debian packages, Python 3.12.14, Qiskit 2.4.2, NumPy 2.2.4, and
SciPy 1.18.1. The rebuilt digest also passed the complete local engine suite:
1,431 passed, 5 skipped, and 6 expected failures. The two images have different
image and layer digests. The verifier does not establish byte identity, build
provenance, dependency integrity beyond these
inventories, task correctness, or publication eligibility. Independent hosts
still need to reproduce this check, and a new image is a distinct evaluation
condition unless comparability is established. Do not silently replace the
historical image in existing campaigns.
