# Reproducible public singleton anchor capture

A trusted diagnostic captures the object closure of the fixed public singleton
factories in the pinned SDK before user code executes. It reads raw graph
components through existing closed codecs; singleton roots contribute their actual
instance dictionaries. It never reads private judge globals or RNG and never
invokes lazy definition synthesis, pickle or payload-selected constructors.
This is an implementation-design probe, not an installed transport feature.

Two fresh Windows processes and two fresh pinned Linux containers produced the
same canonical graph: **30 factories, 676 objects, 74,434 bytes**. The graph hash is
e2923337f9e89609c3e2ad1f4d37e0bd4e17a585448831cef4e11980afefc1ce.
Each process captured twice and verified both equal records and identical actual
object identities. A separate assertion replaced XGate's definition metadata with
an equal dictionary: the old dictionary remained in the captured identity set,
while the replacement did not. The original was restored in a finally block.

The closure contains 30 singleton roots, 30 frozen lists, 26 circuits and native
CircuitData objects, 26 builder scopes, 134 dictionaries, 154 ordinary lists,
100 bit wrappers, 50 registers, 50 BitLocations and 50 tuples. These counts describe
this pinned SDK bootstrap, not a portable assumption about every Qiskit version.

## Consequences for the implementation

Capture a fixed public registry before loading user candidate/test code, retaining
strong references to the original factory objects and their exposed children.
A later equal-valued replacement must get a new ordinary graph identity; it must
not be matched back to a registry entry by contents or a freshly traversed path.
Only registry identities that are actually exported by a call should appear in
that call's message. The 676-object bootstrap is not permission to send additional
unpassed state or expose hidden evaluator data.

Use a versioned, validated registry fingerprint to reject incompatible bootstrap
layouts rather than guessing correspondence. A wire anchor must name a fixed
registry entry of the declared graph kind. Reject duplicate anchor claims, changing
an existing handle's anchor, and binding conflicts with existing graph objects.
No payload class path, callable or factory selector outside the fixed table is
allowed.

Private rehearsal must use isolated clones of anchored objects and owned children.
Live commit must bind the same graph identities to actual receiver factory objects.
Initial anchor-bound native owners need an explicit previous-state/binding plan;
merely adding their live objects to the existing-object map would incorrectly
assume a previous exported record exists. Validate those owner transitions before
any live update. Preserve actual dictionary, frozen-list, circuit and native-cache
aliases, including detached replacements. This transition design is still pending.

Acceptance requires separate-process fixtures for factory identity and shared
controlled-X bases; prepare-time nonmutation even on late malformed data; cached
definition updates; equal-valued replacements; and stale/duplicate anchor handling.
A same-interpreter round trip alone cannot establish independent factory binding.

## Evidence

Fixture: engine/review/singleton_anchor_diagnostic.py. Each result records the
fixture hash and nineteen dependency hashes, checked against actual source bytes.

- [Windows A](GrayBench-singleton-anchors-windows-a.json) and
  [Windows B](GrayBench-singleton-anchors-windows-b.json): raw SHA-256
  13e05afb23c130a2848574e51dcc59ef9f84dc16fe683e44fafe3e7e7173eb31.
- [Linux A](GrayBench-singleton-anchors-linux-a.json) and
  [Linux B](GrayBench-singleton-anchors-linux-b.json): raw SHA-256
  ec66b326747ec5d0999e8c73555855cfb3920ae369cc7850117ecf2ea21fc7db.

Linux mounted only the trusted fixture and dependencies readonly, without network,
as uid 65534, with 512 MiB memory, one CPU, 64 PIDs and 16 MiB tmpfs, in image
sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd.
No production runtime changed. The preceding 748-test result is historical; no
full regression rerun was needed for this isolated diagnostic. Singleton transport,
protected v4 admission and the overall benchmark overhaul remain incomplete.
