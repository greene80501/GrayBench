# Controlled-instruction ownership audit

Eight assertions pass in Python3.12.14/Qiskit2.4.2 on Windows and in the pinned
Linux evaluator image. These are native SDK observations, not graph support or
protected reference admission. The fixture is
engine/review/controlled_ownership_diagnostic.py.

The relevant distinctions are:

- A controlled gate's public params is its base gate's actual parameter list.
  Its own raw _params is a separate list, normally empty. Distinct controlled
  objects can share a single base gate and public parameter list.
- An open CRX inserted with copy=False retains that Python operation and a native
  Python-operation representation. Closing the retained gate later leaves the
  native name crx_o0 and cached parameters unchanged. Rebuilding from the current
  gate instead selects a standard-gate representation and different parameters.
- The reverse transition also occurs: a closed CRX retains the standard native
  representation after its Python object becomes open. Rebuilding changes it.
- CircuitInstruction.copy and replace(qubits=...) preserve the original native
  representation, cached values and retained Python operation in both cases.
- Mutable CX and MCX use the same SDK XGate singleton as their base. Replacing it
  with an independent mutable XGate would change observable identity and class.
- Raw _definition and _name must remain distinct from public lazy/decorated
  properties. The audit reads raw definitions and does not trigger synthesis.

The simple retained-instruction reconstruction cannot be generalized by merely
adding controlled fields. It must preserve both native representation and the
current Python object state, including delegated parameters and base ownership.

## Required next implementation

Extend the existing Task3 component graph with fixed controlled class schemas,
base_gate references and the raw control fields. First test standalone shared
base/parameter/definition aliases. The native-operation descriptor must additionally
record its standard-versus-Python representation; reconstructing it from current
control state is insufficient. Canonical verification must include that selector.
Temporary cached parameter reconstruction must account for the base-gate params
property and restore every actual dictionary even if native construction fails.

Before admitting controlled X families, implement the exact singleton ownership
case and shared raw definitions. Do not silently replace a singleton with a mutable
base. Both open-to-closed and closed-to-open retained-operation transitions must
pass in the pinned Linux probe and later through the protected v4 bridge.

## Evidence

Fixture SHA-256:
903c00fe5d3d02c547214fd00626ffb1cd27faa9eedee368561a574f65c46648.

[Windows result](GrayBench-controlled-ownership-windows.json), eight checks,
SHA-256: 9efdb1e03a28dd1ca29331da25a353bf89774e38424fd558cc7338c043bc5747.

[Linux result](GrayBench-controlled-ownership-linux.json), eight checks,
SHA-256: b0421833f21783c81839e5a707aa1d7b88987ff8d36a88ccfeff626deab0270c.

The Linux fixture was mounted readonly, with no network, uid65534,512MiB memory,
one CPU,64PIDs and16MiB temporary storage, in image
sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd.
Both reported fixture hashes were verified against actual source bytes. No
production runtime changed in this audit. The preceding a03f102 implementation's
730-test result remains its historical result; the full suite was not rerun for
this standalone audit. Both a03f102 GitHub workflows completed successfully.
