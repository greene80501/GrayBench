# Native matrix allocation: open fidelity requirement

The HamiltonianGate registry extension exposes a second unsupported component:
SciPy's expm result is a NumPy array whose base is a native PyCapsule. The exact
task116 references remain unsupported. Three new cached-definition controls fail;
the uncached local control and incorrect-time protected controls behave as expected.
This investigation does not claim that the registry extension completes support.

`native_capsule_probe.py` checks 16 native cases across float32, float64,
complex64 and complex128, with matrix dimensions 1 through 4. Under the recorded
NumPy 2.2.4 / SciPy 1.18.1 runtime, the twelve dimensions-2-through-4 arrays have
PyCapsule bases and OWNDATA false. Dimension-one arrays own their storage.

For every case, slicing and constructing another array over the buffer retain
the original array as base. A preexisting writable alias can change the root's
contents after the root becomes readonly. For all twelve capsule-backed roots,
attempting to set writeable true again raises ValueError. An owning-array copy
allows that transition. Therefore a value copy changes observable behavior even
when shape, dtype and bytes are identical. Capsule repr addresses are not recorded.

## Requirements before admitting this storage

1. Preserve the distinct native allocation, root-array and view identities,
   including separately exported base references and detached aliases.
2. Establish bounded allocation extent and an explicit supported ownership class.
   A PyCapsule type name alone does not establish origin, destructor semantics,
   allocation size or permission to dereference its pointer.
3. Reconstruct using a fixed trusted allocation mechanism without payload-selected
   constructors, arbitrary imports, pointer dereferences or capsule callbacks.
4. Preserve irreversible readonly transitions and updates through preexisting
   writable views. Existing array update code assumes that an owning ndarray can
   temporarily become writable; that assumption does not hold here.
5. Rehearse changes privately and validate aliases/geometry/capacity before live
   mutation, including late discovery of storage and a readonly root with a
   still-writable view. Do not drop retained objects to simplify reconstruction.
6. Run positive/negative protected tests in both transports, all full regression
   tests, and the unchanged reference replay. The current failing tests stay
   failing until the actual behavior is implemented; a value-copy fallback is
   not an acceptable repair.

The evidence is native observation, not a general safe PyCapsule codec or a new
scoring contract. `GrayBench-native-capsule-ownership.json` binds the probe hash,
package versions and all observations. No model APIs or external services were
used. The Hamiltonian before and registry-only reference artifacts preserve the
original unsupported result and the newly reached unsupported storage boundary.
