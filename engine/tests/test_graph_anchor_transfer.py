"""Fresh processes keep public singleton factories genuinely independent."""

import json
import subprocess
import sys
import textwrap

import pytest

COMMON = """
import json, sys
from qiskit.circuit.library import XGate, HGate, CXGate
from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_wire import GraphArena, GraphLimits
from graybench.circuit_wire import WireError
registry = PublicAnchorRegistry.capture()
"""


def run(code, payload=None):
    result = subprocess.run(
        [sys.executable, "-c", COMMON + textwrap.dedent(code)],
        input=None if payload is None else json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def sender(body):
    return run(
        """
a = GraphArena(side='judge', session='anchors', limits=GraphLimits(), anchors=registry)
"""
        + textwrap.dedent(body)
        + "\nprint(json.dumps(a.snapshot(roots, sequence=1)))\n"
    )


def receiver(body, wire):
    return run(
        """
b = GraphArena(side='candidate', session='anchors', limits=GraphLimits(), anchors=registry)
wire = json.load(sys.stdin)
"""
        + textwrap.dedent(body)
        + "\nprint(json.dumps(True))\n",
        wire,
    )


def test_factory_and_actual_children_bind_in_independent_process():
    wire = sender("""
x = XGate()
vars(x)['_label'] = 'from sender'
roots = {'gate': x, 'attrs': vars(x), 'params': x.params,
         'definition': x._definition, 'bits': x._definition._data.qubits}
""")
    assert receiver(
        """
x = XGate()
prepared = b.prepare(wire, sequence=1)
assert x.label is None
out = b.commit(prepared)
assert out['gate'] is x and x.label == 'from sender'
assert out['attrs'] is vars(x) and out['params'] is x.params
assert out['definition'] is x._definition
assert out['bits'] is x._definition._data.qubits
""",
        wire,
    )


def test_equal_replacement_is_distinct_and_unpassed_factory_not_reset():
    wire = sender("""
x = XGate()
old = x._definition.metadata
x._definition.metadata = dict(old)
roots = {'gate': x, 'old': old, 'new': x._definition.metadata}
""")
    assert receiver(
        """
x = XGate()
original = x._definition.metadata
vars(HGate())['_label'] = 'receiver-only'
out = b.commit(b.prepare(wire, sequence=1))
assert out['old'] is original
assert out['new'] is x._definition.metadata and out['new'] is not original
assert out['old'] == out['new']
assert HGate().label == 'receiver-only'
""",
        wire,
    )


def test_initial_native_owner_replacement_preserves_detached_original_cache():
    wire = sender("""
x = XGate()
data = x._definition._data
old = data.qubits
data.replace_bits(qubits=list(old))
roots = {'gate': x, 'old': old, 'new': data.qubits}
""")
    assert receiver(
        """
x = XGate()
data = x._definition._data
original = data.qubits
out = b.commit(b.prepare(wire, sequence=1))
assert out['old'] is original
assert out['new'] is data.qubits and data.qubits is not original
""",
        wire,
    )


@pytest.mark.parametrize("corruption", ["unknown", "duplicate", "kind", "manifest", "factory"])
def test_invalid_anchor_claim_is_rejected_before_factory_mutation(corruption):
    wire = sender("roots = {'gate': XGate(), 'h': HGate()}")
    if corruption == "manifest":
        wire["anchors"]["sha256"] = "0" * 64
    else:
        gates = [n for n in wire["nodes"] if n["kind"] == "public_singleton"]
        if corruption == "unknown":
            gates[0]["anchor"] = "999999"
        elif corruption == "duplicate":
            gates[1]["anchor"] = gates[0]["anchor"]
        elif corruption == "kind":
            next(n for n in wire["nodes"] if n["kind"] == "dict")["anchor"] = gates[0]["anchor"]
        else:
            gates[0]["state"]["factory"] = "h" if gates[0]["state"]["factory"] == "x" else "x"
    assert receiver(
        """
x = XGate()
attrs, params, definition = vars(x), x.params, x._definition
before = dict(attrs)
try:
    b.prepare(wire, sequence=1)
except WireError:
    pass
else:
    raise AssertionError('invalid anchor accepted')
assert vars(x) is attrs and attrs == before
assert x.params is params and x._definition is definition
""",
        wire,
    )


def test_prepare_then_external_change_rejects_commit_without_resetting_live_state():
    wire = sender("roots = {'gate': XGate()}")
    assert receiver(
        """
prepared = b.prepare(wire, sequence=1)
XGate()._definition.metadata['changed-after-prepare'] = True
try:
    b.commit(prepared)
except WireError:
    pass
else:
    raise AssertionError('stale live state accepted')
assert XGate()._definition.metadata['changed-after-prepare']
""",
        wire,
    )


def test_all_fixed_factories_keep_identity_and_controlled_base_aliases():
    wire = sender("""
from qiskit.circuit.library import get_standard_gate_name_mapping
roots = {name: value for name, value in get_standard_gate_name_mapping().items()
         if not value.mutable}
""")
    assert receiver(
        """
from qiskit.circuit.library import get_standard_gate_name_mapping
factories = get_standard_gate_name_mapping()
out = b.commit(b.prepare(wire, sequence=1))
assert len(out) == 30
assert all(value is factories[name] for name, value in out.items())
assert out['cx'].base_gate is XGate()
""",
        wire,
    )


def test_mutable_controlled_gate_and_retained_circuit_share_factory_base():
    wire = sender("""
from qiskit import QuantumCircuit
cx = CXGate().to_mutable()
qc = QuantumCircuit(2)
qc.append(cx, [0, 1], copy=False)
roots = {'gate': cx, 'base': cx.base_gate, 'qc': qc}
""")
    assert receiver(
        """
out = b.commit(b.prepare(wire, sequence=1))
assert out['gate'].base_gate is out['base'] is XGate()
assert out['qc'].data[0].operation is out['gate']
assert out['gate'] is not CXGate()
""",
        wire,
    )


def test_only_exported_anchor_nodes_are_sent():
    wire = sender("roots = {'metadata': XGate()._definition.metadata}")
    assert len(wire["nodes"]) == 1
    assert wire["nodes"][0]["kind"] == "dict"
    assert receiver(
        """
out = b.commit(b.prepare(wire, sequence=1))
assert out['metadata'] is XGate()._definition.metadata
""",
        wire,
    )


def test_child_export_before_owner_binds_existing_public_cache():
    first = sender("roots = {'bits': XGate()._definition._data.qubits}")
    # Preserve the sender's handle allocation across two snapshots.
    pair = run("""
a = GraphArena(side='judge', session='anchors', limits=GraphLimits(), anchors=registry)
first = a.snapshot({'bits': XGate()._definition._data.qubits}, sequence=1)
second = a.snapshot({'gate': XGate()}, sequence=2)
print(json.dumps([first, second]))
""")
    assert first == pair[0]
    assert receiver(
        """
first, second = wire
held = b.commit(b.prepare(first, sequence=1))['bits']
x = b.commit(b.prepare(second, sequence=2))['gate']
assert x is XGate() and held is x._definition._data.qubits
""",
        pair,
    )


@pytest.mark.parametrize("change", ["remove", "replace"])
def test_exported_handle_cannot_change_anchor_claim(change):
    wire = sender("roots = {'metadata': XGate()._definition.metadata}")
    replacement = "None" if change == "remove" else "registry.key_for(HGate()._definition.metadata)"
    assert receiver(
        f"""
b.commit(b.prepare(wire, sequence=1))
wire['sequence'] = 2
wire['nodes'][0]['anchor'] = {replacement}
try:
    b.prepare(wire, sequence=2)
except WireError:
    pass
else:
    raise AssertionError('anchor claim changed')
""",
        wire,
    )


def test_nonfactory_singleton_clone_does_not_become_public_factory():
    wire = sender("""
x = object.__new__(type(XGate()))
object.__setattr__(x, '__dict__', dict(vars(XGate())))
roots = {'clone': x}
""")
    assert receiver(
        """
out = b.commit(b.prepare(wire, sequence=1))['clone']
assert type(out) is type(XGate()) and out is not XGate()
assert vars(out) is not vars(XGate()) and out.params is XGate().params
""",
        wire,
    )


def test_equal_replacement_after_prepare_is_stale_despite_same_values():
    wire = sender("roots = {'gate': XGate()}")
    assert receiver(
        """
prepared = b.prepare(wire, sequence=1)
old = XGate()._definition.metadata
XGate()._definition.metadata = dict(old)
replacement = XGate()._definition.metadata
try:
    b.commit(prepared)
except WireError:
    pass
else:
    raise AssertionError('changed identity accepted')
assert XGate()._definition.metadata is replacement
""",
        wire,
    )


def test_round_trip_preserves_factory_and_detached_aliases_across_processes():
    source = (
        COMMON
        + """
a = GraphArena(side='judge', session='anchors', limits=GraphLimits(), anchors=registry)
x = XGate()
old_metadata = x._definition.metadata
old_bits = x._definition._data.qubits
roots = {'gate': x, 'metadata': old_metadata, 'bits': old_bits}
print(json.dumps(a.snapshot(roots, sequence=1)), flush=True)
reply = json.loads(sys.stdin.readline())
out = a.commit(a.prepare(reply, sequence=1))
assert out['gate'] is x and x.label == 'round-trip'
assert out['old_metadata'] is old_metadata and out['new_metadata'] is x._definition.metadata
assert out['new_metadata'] is not old_metadata
assert out['old_bits'] is old_bits and out['new_bits'] is x._definition._data.qubits
assert out['new_bits'] is not old_bits
print(json.dumps(True))
"""
    )
    with subprocess.Popen(
        [sys.executable, "-c", source],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as process:
        try:
            wire = json.loads(process.stdout.readline())
            reply = run(
                """
b = GraphArena(side='candidate', session='anchors', limits=GraphLimits(), anchors=registry)
out = b.commit(b.prepare(json.load(sys.stdin), sequence=1))
x = out['gate']
vars(x)['_label'] = 'round-trip'
x._definition.metadata = dict(x._definition.metadata)
x._definition._data.replace_bits(qubits=list(x._definition._data.qubits))
roots = {'gate': x, 'old_metadata': out['metadata'], 'new_metadata': x._definition.metadata,
         'old_bits': out['bits'], 'new_bits': x._definition._data.qubits}
print(json.dumps(b.snapshot(roots, sequence=1)))
""",
                wire,
            )
            stdout, stderr = process.communicate(json.dumps(reply) + "\n", timeout=30)
            assert process.returncode == 0, stderr
            assert json.loads(stdout) is True
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


def test_singleton_transport_requires_explicit_bootstrap_on_both_sides():
    assert run("""
a = GraphArena(side='judge', session='anchors', limits=GraphLimits())
try:
    a.snapshot({'x': XGate()}, sequence=1)
except WireError:
    pass
else:
    raise AssertionError('singleton silently admitted without bootstrap')
print(json.dumps(True))
""")
    wire = sender("roots = {'x': XGate()}")
    assert run(
        """
b = GraphArena(side='candidate', session='anchors', limits=GraphLimits())
try:
    b.prepare(json.load(sys.stdin), sequence=1)
except WireError:
    pass
else:
    raise AssertionError('anchor protocol silently downgraded')
print(json.dumps(True))
""",
        wire,
    )


def test_late_native_owner_failure_leaves_factory_dictionary_and_caches_untouched():
    wire = sender("""
vars(XGate())['_label'] = 'must not commit'
roots = {'gate': XGate()}
""")
    owner = next(n for n in wire["nodes"] if n["kind"] == "circuit_data")
    owner["state"]["qregs"].append(dict(owner["state"]["qregs"][0]))
    assert receiver(
        """
x = XGate()
cache = x._definition._data.qubits
attrs = vars(x)
try:
    b.prepare(wire, sequence=1)
except WireError:
    pass
else:
    raise AssertionError('invalid native owner accepted')
assert vars(x) is attrs and x.label is None
assert x._definition._data.qubits is cache
""",
        wire,
    )


@pytest.mark.parametrize("before,after", [(None, "later"), ("cached", None), ("cached", "later")])
def test_controlled_native_mode_survives_shared_base_label_changes(before, after):
    wire = sender(f"""
from qiskit import QuantumCircuit
vars(XGate())['_label'] = {before!r}
cx = CXGate().to_mutable()
qc = QuantumCircuit(2)
qc.append(cx, [0, 1], copy=False)
assert qc._data[0].is_standard_gate() is {before is None!r}
vars(XGate())['_label'] = {after!r}
roots = {{'gate': cx, 'base': XGate(), 'qc': qc}}
""")
    assert receiver(
        f"""
out = b.commit(b.prepare(wire, sequence=1))
assert out['base'] is XGate() and XGate().label == {after!r}
assert out['gate'].base_gate is XGate()
assert out['qc']._data[0].is_standard_gate() is {before is None!r}
assert out['qc'].data[0].operation is out['gate']
""",
        wire,
    )


def test_circuit_only_export_preserves_reachable_singleton_state():
    wire = sender("""
from qiskit import QuantumCircuit
qc = QuantumCircuit(1)
qc.x(0)
assert qc.data[0].operation is XGate()
vars(XGate())['_label'] = 'reachable through circuit'
XGate()._definition.metadata['visible'] = 42
roots = {'qc': qc}
""")
    assert any(n["kind"] == "public_singleton" for n in wire["nodes"])
    assert receiver(
        """
x = XGate()
prepared = b.prepare(wire, sequence=1)
assert x.label is None and 'visible' not in x._definition.metadata
out = b.commit(prepared)['qc']
assert out.data[0].operation is x
assert x.label == 'reachable through circuit'
assert x._definition.metadata['visible'] == 42
assert out._data[0].label is None and out._data[0].is_standard_gate()
""",
        wire,
    )


def test_circuit_retains_distinct_singleton_clone_and_shared_factory_children():
    wire = sender("""
from qiskit import QuantumCircuit
from qiskit.circuit import CircuitInstruction
clone = object.__new__(type(XGate()))
object.__setattr__(clone, '__dict__', dict(vars(XGate())))
vars(clone)['_label'] = 'distinct clone'
qc = QuantumCircuit(1)
qc._data.append(CircuitInstruction(clone, qc.qubits, []))
roots = {'qc': qc, 'clone': clone}
""")
    assert receiver(
        """
out = b.commit(b.prepare(wire, sequence=1))
clone = out['clone']
assert out['qc'].data[0].operation is clone and clone is not XGate()
assert clone.params is XGate().params
assert clone._definition is XGate()._definition
assert clone.label == 'distinct clone' and XGate().label is None
""",
        wire,
    )


@pytest.mark.parametrize("name", ["h", "cx", "ccx", "swap"])
def test_circuit_only_standard_singleton_wrappers_keep_factory_identity(name):
    wire = sender(f"""
from qiskit import QuantumCircuit
from qiskit.circuit.library import get_standard_gate_name_mapping
gate = get_standard_gate_name_mapping()[{name!r}]
qc = QuantumCircuit(gate.num_qubits)
qc.append(gate, qc.qubits, copy=False)
qc.append(gate, qc.qubits, copy=False)
vars(gate)['_label'] = 'later wrapper label'
roots = {{'qc': qc}}
""")
    assert receiver(
        f"""
from qiskit.circuit.library import get_standard_gate_name_mapping
gate = get_standard_gate_name_mapping()[{name!r}]
prepared = b.prepare(wire, sequence=1)
assert gate.label is None
qc = b.commit(prepared)['qc']
assert qc.data[0].operation is qc.data[1].operation is gate
assert gate.label == 'later wrapper label'
assert qc._data[0].label is None and qc._data[1].label is None
assert qc._data[0].is_standard_gate()
""",
        wire,
    )


def test_circuit_only_return_updates_original_factory_and_held_children():
    source = (
        COMMON
        + """
from qiskit import QuantumCircuit
a = GraphArena(side='judge', session='anchors', limits=GraphLimits(), anchors=registry)
qc = QuantumCircuit(1)
qc.x(0)
x = qc.data[0].operation
old = x._definition.metadata
print(json.dumps(a.snapshot({'qc': qc}, sequence=1)), flush=True)
out = a.commit(a.prepare(json.loads(sys.stdin.readline()), sequence=1))
assert out['qc'] is qc and qc.data[0].operation is x is XGate()
assert x.label == 'returned wrapper'
assert out['old'] is old and out['new'] is x._definition.metadata is not old
assert qc._data[0].label is None
print(json.dumps(True))
"""
    )
    with subprocess.Popen(
        [sys.executable, "-c", source],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as process:
        try:
            wire = json.loads(process.stdout.readline())
            reply = run(
                """
b = GraphArena(side='candidate', session='anchors', limits=GraphLimits(), anchors=registry)
qc = b.commit(b.prepare(json.load(sys.stdin), sequence=1))['qc']
x = qc.data[0].operation
old = x._definition.metadata
vars(x)['_label'] = 'returned wrapper'
x._definition.metadata = dict(old)
roots = {'qc': qc, 'old': old, 'new': x._definition.metadata}
print(json.dumps(b.snapshot(roots, sequence=1)))
""",
                wire,
            )
            stdout, stderr = process.communicate(json.dumps(reply) + "\n", timeout=30)
            assert process.returncode == 0, stderr
            assert json.loads(stdout) is True
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
