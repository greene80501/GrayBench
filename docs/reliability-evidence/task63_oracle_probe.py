"""Protected constant-answer controls plus native BB84 fixture enumeration."""
from pathlib import Path
from collections import Counter
from itertools import product
import hashlib
import importlib.metadata
import json
import platform
import sys
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from graybench.datasets import load_suite
from graybench.identity import identity
from graybench.reference_scan import run_evidence_cases
from graybench.upstream import UpstreamJudge

tasks = [t for suite in ('normal', 'hard') for t in load_suite(suite, Path('../../GrayBench/data/datasets')) if t.public.family_id == 'qhe/63']
assert len(tasks) == 2
judge = UpstreamJudge(image='sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd', docker='C:/Program Files/Docker/Docker/resources/bin/docker.exe', protocol=4)
items = []
for task in tasks:
    for name, answer in [('constant-one', '1'), ('constant-zero', '0')]:
        code = 'def bb84_circuit_generate_key(senders_basis, circuit):\n    return ' + repr(answer) + '\n'
        items.append((task.public.suite + '/63/' + name, identity({'task':task.digest,'code':code}), (task,code)))
summary = run_evidence_cases(items, lambda case: judge.evaluate(*case), Path(sys.argv[1]), purpose='task63 oracle adequacy diagnostic; protected authored constants, not model scoring', selection={'families':[63], 'suites':['normal','hard'], 'fixtures':['constant-one','constant-zero']})

basis = [1,0,0,1,1]
sender_bits = [0,0,0,1,1]
circuit = QuantumCircuit(5)
circuit.x([3,4])
circuit.h([0,3,4])
witnesses = []
for receiver in product((0,1), repeat=5):
    measured = circuit.copy()
    for i, value in enumerate(receiver):
        if value:
            measured.h(i)
    matching = [i for i in range(5) if basis[i] == receiver[i]]
    expected = ''.join(str(sender_bits[i]) for i in matching)
    probabilities = Statevector(measured).probabilities_dict()
    sifted = Counter()
    for bitstring, probability in probabilities.items():
        # Native Statevector strings index qubit zero on the right.
        key = ''.join(bitstring[-1-i] for i in matching)
        sifted[key] += float(probability)
    assert abs(sifted[expected] - 1.0) < 1e-12
    assert sum(p for key,p in sifted.items() if key != expected) < 1e-12
    witnesses.append({'receiver_basis':list(receiver), 'matching_indices':matching, 'ideal_sifted_key':expected, 'verified_probability':sifted[expected]})
counts = Counter(row['ideal_sifted_key'] for row in witnesses)
assert sum(counts.values()) == 32 and counts['1'] == 2
seeded = np.random.RandomState(12345).randint(2,size=5).tolist()
seeded_key = ''.join(str(sender_bits[i]) for i in range(5) if basis[i] == seeded[i])
assert seeded_key == '1'
result = {'protected_evidence':summary, 'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'python':platform.python_version(), 'packages':{p:importlib.metadata.version(p) for p in ('numpy','qiskit')}, 'task_digests':{t.public.suite:t.digest for t in tasks}, 'sender_basis':basis, 'sender_bits':sender_bits, 'receiver_basis_witnesses':witnesses, 'key_counts_out_of_32_equally_likely_receiver_bases':dict(sorted(counts.items())), 'upstream_seed_receiver_basis':seeded, 'upstream_seed_key':seeded_key, 'interpretation':'For this ideal fixture and independent uniform receiver bases, the upstream required key occurs with probability 2/32. This is exhaustive basis enumeration with native statevector checks, not empirical provider or canonical sampling.'}
with Path(sys.argv[2]).open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(result,stream,indent=2)
    stream.write('\n')
print(json.dumps({'protected':summary,'basis_combinations':32,'required_key_probability':'2/32','seeded_receiver_basis':seeded}))
