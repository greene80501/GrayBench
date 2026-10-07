# Task 82 header adjudication: development design

The task 82 prompt asks for a QPY file. IBM's [QPY format](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.2/qpy)
specifies the six-byte `QISKIT` prefix for every QPY file. A captured artifact
without that prefix is therefore definitely not the requested serialization.
Today `task82-file-semantic-v1` leaves even this case unscored as `unsupported`.

Preserve v1 exactly. Add `task82-file-semantic-v2` with the same public prompt,
candidate execution, parser isolation and Bell-state oracle. Its only scoring
change is to mark an existing captured file shorter than six bytes or lacking
the prefix as `fail`, with artifact/phase evidence, before invoking Qiskit.
Missing files remain `fail`. Files with the prefix that crash, time out or
raise during parsing remain `unsupported` pending separate adjudication.
Valid reference and equivalent circuits still pass. The recipe name and
manifest bind the changed rule; campaign planning must select it explicitly.

This narrow rule closes a way for invalid answers to evade scoring without
assuming the patched QPY parser recognizes every valid payload. It does not
admit task 82 or alter historical v1 results.
