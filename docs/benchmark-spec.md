# Benchmark Specification

## Overview

This document defines the exact evaluation rules for the graybench benchmark suite,
ensuring reproducible and comparable results across all model evaluations.

## Primary Metric

**pass@1**: Each task receives a single attempt, and the solution passes if all tests succeed.

This is the default leaderboard metric. No retries, no self-repair, no iterative refinement.

## Decoding Settings

All evaluations use deterministic decoding for fairness:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| temperature | 0.0 | Deterministic output |
| top_p | 1.0 | No nucleus sampling |
| max_tokens | 4096 | Sufficient for any solution |

These settings ensure that:
1. Results are reproducible across runs
2. All models receive identical conditions
3. Performance reflects model capability, not sampling luck

## Prompt Format

### Normal Suite

The prompt includes:
- Problem description
- Function signature
- Required imports
- Type hints

Example:
```python
from qiskit import QuantumCircuit

def create_bell_state(qc: QuantumCircuit) -> QuantumCircuit:
    """
    Create a Bell state on the given quantum circuit.
    
    Args:
        qc: A quantum circuit with at least 2 qubits
        
    Returns:
        The circuit with Bell state preparation added
    """
```

### Hard Suite

The prompt includes ONLY:
- Raw problem statement
- No imports
- No function signature
- No type hints

Example:
```
Write a function that creates a Bell state on a quantum circuit.
The function should take a QuantumCircuit as input and return the modified circuit.
```

**Important**: We do NOT augment hard prompts with any hints or context.

## Execution Policy

### Timeout

- Default: 120 seconds per task
- Rationale: Generous timeout to not penalize correct but slow solutions
- Quantum circuit simulations can be compute-intensive

### Resource Limits

- Memory: No artificial limit (system default)
- CPU: No throttling
- Network: Allowed (for IBM Quantum runtime tasks)
- File I/O: Allowed

### No Sandboxing

We explicitly do NOT:
- Block network access
- Restrict file system operations
- Limit subprocess creation
- Artificially constrain the execution environment

Rationale: The goal is to evaluate the model's code generation ability in a realistic
environment, not to test sandbox escape. Any task that legitimately requires these
capabilities should be able to use them.

## Outcome Categories

| Outcome | Code | Description |
|---------|------|-------------|
| PASS | 0 | All tests passed |
| FAIL_TEST | 1 | Test assertion failed |
| FAIL_SYNTAX | 2 | Python syntax error |
| FAIL_IMPORT | 3 | Import/module error |
| FAIL_RUNTIME | 4 | Other runtime exception |
| TIMEOUT | 5 | Exceeded timeout limit |
| EXTRACTION_FAILED | 6 | Could not extract code from completion |
| ERROR_OTHER | 7 | Unknown error |

## Self-Repair (Future Track)

The default evaluation does NOT include self-repair. However, we plan to support
a separate "self-repair track" with these rules:

- Up to N retry attempts after failure
- Error message provided as feedback
- Separate leaderboard/metrics
- Not included in main pass@1 score

## Reproducibility Requirements

Each run must record:

1. **Environment**
   - Python version
   - OS/platform
   - Qiskit version
   - All package versions

2. **Dataset**
   - Version number
   - Commit hash
   - Dataset hash

3. **Model**
   - Provider
   - Model ID
   - Actual model version (from API response)

4. **Parameters**
   - Temperature
   - Top-p
   - Max tokens
   - Timeout

5. **Results**
   - Full prompt text
   - Full completion text
   - Raw API response
   - Extracted code
   - Test output (stdout/stderr)
   - Outcome classification

## Comparability

Results are only comparable when:

1. Same dataset version
2. Same suite (normal or hard)
3. Same decoding parameters
4. Same timeout
5. No post-processing of prompts or completions

The benchmark spec version should be recorded with results.

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01 | Initial specification |
