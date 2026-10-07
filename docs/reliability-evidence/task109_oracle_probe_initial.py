"""Trusted authored fixtures against exact task109 tests; not protected scoring."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import platform
import sys
from graybench.datasets import load_suite
from graybench.identity import identity
from graybench.judge import Judgment
from graybench.reference_scan import run_evidence_cases
from qiskit.quantum_info import Statevector, Pauli

fixtures = {
    'phase-alternative': "from qiskit import QuantumCircuit\nfrom qiskit.circuit import Parameter\ndef circuit():\n    qc = QuantumCircuit(1)\n    qc.h(0)\n    qc.p(Parameter('phi'), 0)\n    return qc\n",
    'fixed-plus': "from qiskit import QuantumCircuit\ndef circuit():\n    qc = QuantumCircuit(1)\n    qc.h(0)\n    return qc\n",
    'global-phase-only': "from qiskit import QuantumCircuit\nfrom qiskit.circuit import Parameter\ndef circuit():\n    qc = QuantumCircuit(1)\n    qc.h(0)\n    qc.global_phase = Parameter('phi')\n    return qc\n",
}
tasks = [t for suite in ('normal', 'hard') for t in load_suite(suite, Path('../../GrayBench/data/datasets')) if t.public.family_id == 'qhe/109']
assert len(tasks) == 2
manifest = {'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'python': platform.python_version(), 'packages': {p: importlib.metadata.version(p) for p in ('qiskit', 'numpy')}, 'execution': 'native trusted authored fixtures; exact pinned private test, no isolation claim', 'repetitions': 'unmodified upstream 1000 calls; no injected RNG seed'}
items = []
for task in tasks:
    for name, code in {'canonical':task.canonical_solution, **fixtures}.items():
        items.append((f'{task.public.suite}/109/{name}', identity({'task':task.digest,'code':code}), (task,name,code)))

def evaluate(case):
    task,name,code = case
    scope = {}
    exec(compile(code, '<trusted-authored-fixture>', 'exec'), scope)
    factory = scope['circuit']
    calls = 0
    def counted():
        nonlocal calls
        calls += 1
        return factory()
    scope['circuit'] = counted
    outcome, detail = 'pass', None
    try:
        exec(compile(task.upstream_test, '<pinned-upstream-test>', 'exec'), scope)
    except Exception as exc:
        outcome, detail = 'fail', {'type':type(exc).__name__, 'message':str(exc)}
    witnesses = []
    for angle in (0.0, 1.5707963267948966, 3.141592653589793, 4.71238898038469):
        qc = factory()
        qc.assign_parameters([angle] * qc.num_parameters, inplace=True)
        sv = Statevector(qc)
        witnesses.append({'angle':angle,'bloch':[float(sv.expectation_value(Pauli(p)).real) for p in ('X','Y','Z')]})
    return Judgment(outcome, identity(manifest), {'manifest':manifest,'task_digest':task.digest,'fixture':name,'completion':code,'upstream_calls':calls,'detail':detail,'bloch_witnesses':witnesses,'expected_public_contract': 'reject' if name in ('fixed-plus','global-phase-only') else 'positive control; full minimal-resource contract not certified'})

print(json.dumps(run_evidence_cases(items, evaluate, Path(sys.argv[1]), purpose='task109 oracle adequacy diagnostic; trusted native fixtures, not model scoring', selection={'families':[109],'suites':['normal','hard'],'fixtures':['canonical',*fixtures]})))
