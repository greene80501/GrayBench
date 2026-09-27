"""Reject forged native storage relationships before graph reconstruction."""

import copy

import numpy as np
from scipy.linalg import expm

from graybench.circuit_wire import WireError
from graybench.graph_limits import GraphLimits
from graybench.graph_wire import GraphArena

source = GraphArena(side="judge", session="native-forgery", limits=GraphLimits())
root = expm(np.zeros((3, 3), dtype=complex))
wire = source.snapshot({"root": root, "capsule": root.base, "alias": root.view()}, sequence=1)


def records(frame):
    return {node["kind"]: node for node in frame["nodes"]}


def invalid(change):
    frame = copy.deepcopy(wire)
    change(records(frame))
    target = GraphArena(side="candidate", session="native-forgery", limits=GraphLimits())
    try:
        target.prepare(frame, sequence=1)
    except WireError:
        return
    raise AssertionError("Forged native graph was accepted")


invalid(lambda nodes: nodes["native_capsule"]["state"].update(capacity=-1))
invalid(lambda nodes: nodes["native_capsule"]["state"].update(dtype_char="O"))
invalid(lambda nodes: nodes["native_capsule"]["state"].update(origin_shape=[2, 2]))
invalid(lambda nodes: nodes["native_capsule"]["state"].update(bytes="!!!"))
invalid(lambda nodes: nodes["native_capsule"]["state"].update(root=None))
invalid(lambda nodes: nodes["native_root"]["state"].update(base={"ref": "j:999"}))
invalid(lambda nodes: nodes["ndarray_view"]["state"].update(offset=4096))
invalid(
    lambda nodes: nodes["ndarray_view"]["state"].update(base={"ref": nodes["native_capsule"]["id"]})
)
print("Eight forged native graph states rejected before reconstruction")
