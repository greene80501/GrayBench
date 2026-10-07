# Special instruction graph development

This increment admits fixed LinearFunction, StatePreparation, Delay and
UnitaryGate classes. Their actual instance dictionaries and parameter references
remain graph objects. StatePreparation retains its original argument and three
raw mode flags; definitions are not eagerly synthesized.

Retained Delay operations have two independently observable states: the Python
operation's current duration/unit and the native circuit's cached duration/unit.
A fixed native circuit/DAG conversion reads the cached unit without consulting
the changed Python wrapper. Reconstruction temporarily supplies cached values
and restores the actual dictionary afterwards.

UnitaryGate's native parameter list is empty. Its cached complex matrix is
transported as bounded data independently of the Python parameter array. Fresh
matrix getter wrappers receive no persistent graph IDs. Cached matrix bytes
count toward the aggregate array and matrix budgets. Reconstruction does not
normalize matrix values or check unitarity to repair candidate state.

Native Delay and Unitary instructions produced by compilation use explicit
descriptors. A fixed native conversion drops the temporary Python operation
cache, preserving fresh-wrapper behavior. Labels are installed before insertion
so that their native caches are preserved as well.

The fifteen new tests cover shared matrices, original state-preparation arguments,
retained and fresh wrappers, divergent native/Python state, memory budgets,
malformed matrices rejected before live mutation, and actual protected execution.
All fifteen passed with Docker enabled. A related 113-test run also passed before
the final malformed-payload and protected tests were added. The full Docker-enabled
suite passed 863 tests in 371.05 seconds; the JUnit report confirms zero failures,
errors or skips. The source-guarded twelve-case reference replay passed tasks
4, 5, 6, 22, 46 and 86 in both normal and hard suites. All planned cases completed
and the evidence chain verifies. These are targeted interface results, not a new
aggregate or model score; full admission and the other release gates remain open.

Raw evidence: `GrayBench-v4-special-instructions-reference.jsonl`, SHA256
`210b2b0857b80d5b40db561caf004e8f760f29b1d85fc6f6cca10980b3f73d51`.
Chain head:
`2a034d036d9c47f392a265a0af85db1b53bcd8c46e776f1e4dc2afe95d24da86`.
