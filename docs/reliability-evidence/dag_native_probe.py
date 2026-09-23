import copy, hashlib, json, platform
from pathlib import Path
import qiskit
from qiskit import QuantumCircuit
from qiskit.converters import circuit_to_dag
from qiskit.dagcircuit import DAGCircuit
from qiskit.circuit.library import XGate
records=[]
for order in ([0,2],[2,0]):
    qc=QuantumCircuit(1);qc.x(0);qc.h(0);qc.z(0)
    dag=circuit_to_dag(qc);nodes=dag.op_nodes()
    for index in order: dag.remove_op_node(nodes[index])
    rebuilt=DAGCircuit();rebuilt.__setstate__(dag.__getstate__())
    cloned=copy.copy(dag)
    ids={name:value.apply_operation_back(XGate(),[value.qubits[0]])._node_id
         for name,value in [('original',dag),('state_rebuilt',rebuilt),('native_copy',cloned)]}
    records.append({'removal_order':order,'next_node_ids':ids})
assert records[0]['next_node_ids']=={'original':4,'state_rebuilt':2,'native_copy':4}
assert records[1]['next_node_ids']=={'original':2,'state_rebuilt':2,'native_copy':2}
result={'purpose':'native DAG allocator semantics; not model scoring',
        'python':platform.python_version(),'qiskit':qiskit.__version__,
        'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'observations':records}
out=Path('../../../outputs/GrayBench-native-dag-allocator.json')
with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
print(json.dumps(result))
