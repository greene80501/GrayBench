# Private public-anchor bootstrap copies

The public-anchor registry can now reconstruct its frozen bootstrap into private
objects using the existing closed graph codecs and native-owner reconstruction.
Singleton shells use their captured exact runtime types with object.__new__;
the copy path never allocates them through public singleton factories. The special
codec is scoped to this trusted bootstrap operation and is not registered as an
accepted transport kind. No peer-provided class or constructor is accepted.

Three new regressions first failed because private_copy was missing, then passed.
The tests check all 676 original objects have distinct private identities and exact
runtime types, re-encode every private node to compare its state and references
with the bootstrap, preserve gate dictionary/params/definition/native-cache aliases,
and mutate private state without affecting live factories. Repeated copies remain
independent and use frozen history even after live metadata changes.

The source-bound diagnostic passes in fresh Windows and pinned Linux processes,
including canonical comparison of every node and private dictionary, frozen-list,
and definition-metadata mutation. Both use Python 3.12.14 and Qiskit 2.4.2.
The Linux probe mounts only the 20 explicit implementation modules and trusted
fixture, with no network, read-only filesystem, unprivileged UID, and resource caps.
Raw artifacts record source and fixture SHA-256 digests; these were verified
against the actual mounted bytes, which can differ from Git's normalized LF bytes.

- Windows raw: GrayBench-private-anchor-copy-windows.json
  SHA-256 fcf86ad691159c9bbdce392cc87ca30fbbd6d917fe0de04c074a83447e21f4cc
- Linux raw: GrayBench-private-anchor-copy-linux.json
  SHA-256 a80693dc82e43c00ef8cfb35e359d9709a229e8f838f6ecdacc88415019c23fb

This is the private baseline required for anchor rehearsal, not completed singleton
transport support. Wire anchor annotations, initial live owner binding, before-user-code
startup, separate-process protected-call identity and atomicity tests remain pending.
The production bridge still uses v3; no model score or complete benchmark-correctness
claim follows from these component tests. Prior evidence is retained unchanged.

Full suite: 770 passed in 207.39 seconds, with JUnit confirming zero failures,
errors or skips (outputs/GrayBench-v4-private-anchor-copy-full-tests.xml).
The focused 22-case registry file also passes with the final canonical-state
assertions; lint, formatting, diff whitespace and secret-value scans pass.
