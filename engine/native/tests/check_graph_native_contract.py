"""Run graph ownership controls inside the declared adapted SciPy image."""

import gc
import weakref

import numpy as np
from scipy.linalg import _internal_matfuncs as native
from scipy.linalg import expm

from graybench.circuit_wire import WireError
from graybench.graph_limits import GraphLimits
from graybench.graph_wire import GraphArena


def arenas(session):
    return tuple(
        GraphArena(side=side, session=session, limits=GraphLimits())
        for side in ("judge", "candidate")
    )


source, target = arenas("native-root-alias")
root = expm(np.zeros((3, 3), dtype=complex))
capsule = root.base
alias = root.view()
root.flags.writeable = False
alias[0, 0] = 3
wire = source.snapshot({"root": root, "capsule": capsule, "alias": alias}, sequence=1)
received = target.commit(target.prepare(wire, sequence=1))
remote_root = received["root"]
remote_capsule = received["capsule"]
remote_alias = received["alias"]
assert remote_root.base is remote_capsule
assert remote_alias.base is remote_root
assert not remote_root.flags.owndata and not remote_root.flags.writeable
assert remote_alias.flags.writeable
assert native._graybench_storage_read(remote_capsule) == native._graybench_storage_read(capsule)
alias[1, 1] = 7
wire = source.snapshot({"root": root, "capsule": capsule, "alias": alias}, sequence=2)
received = target.commit(target.prepare(wire, sequence=2))
assert received["root"] is remote_root and received["capsule"] is remote_capsule
assert received["alias"] is remote_alias and remote_root[1, 1] == 7

# A view created before the root was frozen may enter the graph only on a
# later transfer. Its independent writable flag must survive reconstruction.
source, target = arenas("late-native-alias")
root = expm(np.zeros((2, 2), dtype=complex))
late_alias = root.view()
root.flags.writeable = False
first = source.snapshot({"root": root}, sequence=1)
remote_root = target.commit(target.prepare(first, sequence=1))["root"]
assert not remote_root.flags.writeable
late_alias[0, 0] = 11
second = source.snapshot({"root": root, "alias": late_alias}, sequence=2)
prepared = target.prepare(second, sequence=2)
assert remote_root[0, 0] == 1  # Private rehearsal must not mutate live storage.
remote = target.commit(prepared)
assert remote["root"] is remote_root
assert remote["alias"].base is remote_root
assert remote["alias"].flags.writeable
assert remote_root[0, 0] == 11

source, target = arenas("capsule-without-root")
root = expm(np.eye(2))
capsule = root.base
expected = native._graybench_storage_read(capsule)
reference = weakref.ref(root)
del root
gc.collect()
assert reference() is None
wire = source.snapshot({"capsule": capsule}, sequence=1)
received = target.commit(target.prepare(wire, sequence=1))
assert native._graybench_storage_read(received["capsule"]) == expected

source, _ = arenas("foreign-capsule")
try:
    source.snapshot({"capsule": np.arange(2).__dlpack__()}, sequence=1)
except WireError:
    pass
else:
    raise AssertionError("Foreign capsule was accepted as registered storage")

print("Registered native graph root, capsule and alias contract passed")
