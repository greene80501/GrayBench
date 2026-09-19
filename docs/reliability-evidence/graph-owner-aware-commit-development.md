# Owner-aware graph commit foundation

The standalone graph can now preserve native CircuitData membership caches across
owner transitions. This is the owner-allocation foundation for Task 3, not complete
QuantumCircuit or instruction transport. CircuitData currently requires an empty
instruction stream, no variables/stretches and a canonical finite numeric phase.

## Commit sequence

GraphArena still validates the complete wire schema, IDs, immutable records,
references and resource limits first. Graphs with native-owned children then use a
separate path:

1. Reconstruct the previously exported graph privately from its saved records.
2. Rehearse the proposed membership transition on those private objects.
3. Bind child handles to the caches actually created by the native owner.
4. Construct new immutable nodes and prepare/apply ordinary component updates
   using those bound objects, so tuples cannot capture placeholder lists.
5. Verify that caches remain bound and the owner re-encodes to exactly its declared
   state. Constructor normalization is not accepted.
6. Bind the validated internal plan to arena identity, generation and sequence.
   Only commit repeats this schedule against live objects and resolves return roots.

No live mutation happens during prepare. Unexpected live execution failures close
the arena. The schedule comes from fixed local codecs; payloads never choose a
callable, class path, attribute or operation program. The existing ordinary graph
path remains in use when there are no native-owned children.

## Preserved behavior

Fresh owners share the actual exposed list/map objects with separately supplied
arguments. Adding quantum or classical bits creates new cache handles while old
lists, dictionaries and tuples remain detached with their earlier contents.
Equal-valued membership replacement still changes cache identity. Appending a
register to existing membership retains the bit-list cache while replacing the
index-map cache. BitLocations retains its actual registers list by reference.

A public cache may contain values that differ from intrinsic Rust membership,
including cyclic Python references. The graph preserves both states. Intrinsic
membership comes from a fresh copy_empty_like(); the original caches are not
repaired or substituted.

Two owner slots cannot claim one child handle. A new owner cannot adopt an
already-exported unattached list/map through an SDK interface that copies it.
Such late attachment is rejected before live mutation. Register removal/replacement,
anonymous bit identity, nonempty instruction streams and symbolic phase remain
unfinished capabilities, not silently narrower certified benchmark requirements.

## Verification

Nine initial owner tests failed at the missing capability, then passed. Subsequent
RED tests exposed two accepted noncanonical phases and an escaping integer-overflow
exception; the phase schema now rejects all three before reconstruction.
Seventeen focused cases pass, covering private rehearsal, dynamic binding failure,
malformed late data, detached aliases, cycles, stale/foreign plans, classical
transitions and invalid native reconstruction.

The full Docker-enabled suite passed **691 tests** in 192.02 seconds with no
failures, errors or skips. Local JUnit artifact:
outputs/GrayBench-v4-owner-aware-commit-full-tests.xml. Ruff lint, 107-file
formatting and secret-value diff checks passed.

The trusted standalone probe passed 22 checks in image
sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd.
Fifteen dependency modules and the fixture were mounted readonly, without network,
as user 65534 with 512 MiB memory, one CPU, 64 PIDs and 16 MiB temporary storage.
Source and probe hashes were checked against actual mounted bytes.
[Raw result](GrayBench-v4-owner-aware-commit-linux-probe.json) SHA-256:
bdce8ec52599969938c0b693cd3d77d09fb80e8b84f21308cd36a1574ff0c952.

The worker/oracle production bridge still uses v3. Its preserved identity defects
are not resolved by these standalone modules. No model generation, reference
cohort scan or certified score was produced in this increment.
