# Matrix-defined gates

Circuit wire v4 adds a fixed UnitaryGate constructor and instruction labels. Matrix data uses
the existing bounded numeric-array encoding. The decoder requires square complex matrices of
the dimension specified by the instruction's qubits; each instruction is limited to seven
qubits and total matrix storage to 512 KiB per circuit. Unsupported larger representations
remain unscored pending adjudication, not silently counted wrong.

The pinned SDK constructor coerces matrix data to complex values. Its optional input validation
can be disabled by submitted code. The transport therefore preserves nonunitary matrices too,
without normalization or repair: correctness belongs to the protected judge. See the
[official UnitaryGate API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.circuit.library.UnitaryGate).

Tests compare circuit operators with nontrivial qubit order, preserve labels and base class,
keep invalid matrices unchanged, and reject malformed shapes, arity, labels and excess aggregate
storage. Separate normal and hard task-4 reference replays both pass. These are compatibility
checks, not task certification or model scores. The historical full reference scan is unchanged.

StatePreparation remains a separate required interface. Inspection of the pinned SDK shows that
its original constructor argument, normalized stored parameters, label/int mode and inverse flag
affect behavior. A plain amplitude-only substitution would lose those distinctions, particularly
when the judge calls inverse(). Its complete representation must preserve these semantics.
See the [official StatePreparation API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.3/qiskit.circuit.library.StatePreparation).
