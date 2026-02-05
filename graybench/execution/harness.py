"""
Execution harness for running and evaluating code solutions.

Provides isolated execution of model-generated code against test cases
with detailed outcome categorization and resource management.
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from graybench.dataset.models import Task
from graybench.execution.outcomes import Outcome
from graybench.execution.code_extractor import CodeExtractor, ExtractionResult


@dataclass
class ExecutionResult:
    """Result of executing a code solution."""
    
    # Did all tests pass?
    passed: bool
    
    # Detailed outcome category
    outcome: Outcome
    
    # Captured output
    stdout: str = ""
    stderr: str = ""
    
    # Error information
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    
    # Timing
    execution_time_ms: float = 0.0
    
    # Code extraction info
    extracted_code: str = ""
    extraction_method: str = ""
    extraction_success: bool = False
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "passed": self.passed,
            "outcome": self.outcome.value,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "extracted_code": self.extracted_code,
            "extraction_method": self.extraction_method,
            "extraction_success": self.extraction_success,
            "metadata": self.metadata,
        }


class ExecutionHarness:
    """
    Harness for executing code solutions in isolation.
    
    Features:
    - Isolated execution in temporary directories
    - Configurable timeouts
    - Detailed output capture
    - Fine-grained outcome categorization
    """
    
    def __init__(
        self,
        timeout_seconds: int = 120,
        max_output_bytes: int = 1024 * 1024,  # 1MB
        python_executable: Optional[str] = None,
    ):
        """
        Initialize the execution harness.
        
        Args:
            timeout_seconds: Maximum time allowed for execution
            max_output_bytes: Maximum output to capture
            python_executable: Path to Python executable (default: sys.executable)
        """
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.python_executable = python_executable or sys.executable
        self.extractor = CodeExtractor()
    
    def execute(
        self,
        task: Task,
        model_output: str,
    ) -> ExecutionResult:
        """
        Execute a model's solution for a task.
        
        Args:
            task: The benchmark task
            model_output: Raw output from the model
        
        Returns:
            ExecutionResult with detailed outcome
        """
        # Step 1: Extract code from model output
        extraction = self.extractor.extract(
            model_output=model_output,
            entry_point=task.entry_point,
            allow_partial=True,
        )
        
        if not extraction.has_code:
            return ExecutionResult(
                passed=False,
                outcome=Outcome.EXTRACTION_FAILED,
                error_type="ExtractionError",
                error_message=extraction.error or "No code extracted",
                extracted_code="",
                extraction_method=extraction.method,
                extraction_success=False,
            )
        
        if not extraction.entry_point_found:
            return ExecutionResult(
                passed=False,
                outcome=Outcome.NO_FUNCTION_FOUND,
                error_type="MissingFunction",
                error_message=f"Function '{task.entry_point}' not found in code",
                extracted_code=extraction.code,
                extraction_method=extraction.method,
                extraction_success=False,
            )
        
        # Step 2: Create execution environment
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Write candidate code
            candidate_path = temp_path / "candidate.py"
            candidate_path.write_text(extraction.code)
            
            # Write test harness
            harness_code = self._create_test_harness(task, extraction.code)
            harness_path = temp_path / "test_harness.py"
            harness_path.write_text(harness_code)
            
            # Step 3: Execute tests
            result = self._run_tests(
                harness_path=harness_path,
                working_dir=temp_path,
            )
            
            # Add extraction info
            result.extracted_code = extraction.code
            result.extraction_method = extraction.method
            result.extraction_success = extraction.success
            
            return result
    
    def validate_with_canonical(self, task: Task) -> ExecutionResult:
        """
        Validate the harness by running the canonical solution.
        
        This should always pass if the environment is set up correctly.
        
        Args:
            task: The benchmark task with canonical solution
        
        Returns:
            ExecutionResult from running the canonical solution
        """
        # Create a "fake" model output with the canonical solution
        return self.execute(task, task.canonical_solution)
    
    def _create_test_harness(self, task: Task, candidate_code: str) -> str:
        """
        Create the test harness script.
        
        This script:
        1. Imports the candidate code
        2. Runs the test cases
        3. Reports success/failure via exit code
        """
        # Escape the candidate code for embedding
        candidate_escaped = candidate_code.replace('\\', '\\\\').replace("'''", "\\'\\'\\'")
        
        harness = f'''#!/usr/bin/env python3
"""Test harness for graybench - auto-generated."""

import sys
import traceback

# Execute candidate code in a namespace
candidate_namespace = {{}}
candidate_code = \'\'\'{candidate_escaped}\'\'\'

try:
    exec(candidate_code, candidate_namespace)
except Exception as e:
    print(f"Error executing candidate code: {{type(e).__name__}}: {{e}}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

# Get the candidate function
candidate_function = candidate_namespace.get("{task.entry_point}")
if candidate_function is None:
    print(f"Function '{task.entry_point}' not found in candidate code", file=sys.stderr)
    sys.exit(1)

# Run the tests
test_code = """{task.test}"""

# Create the check function environment
test_namespace = candidate_namespace.copy()
test_namespace["candidate"] = candidate_function

try:
    exec(test_code, test_namespace)
    
    # Call the check function if it exists
    if "check" in test_namespace:
        test_namespace["check"](candidate_function)
    
    print("All tests passed!")
    sys.exit(0)
    
except AssertionError as e:
    print(f"Test assertion failed: {{e}}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Test error: {{type(e).__name__}}: {{e}}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''
        return harness
    
    def _run_tests(
        self,
        harness_path: Path,
        working_dir: Path,
    ) -> ExecutionResult:
        """
        Run the test harness script.
        
        Args:
            harness_path: Path to the test harness script
            working_dir: Working directory for execution
        
        Returns:
            ExecutionResult from the test run
        """
        start_time = time.perf_counter()
        
        try:
            # Run the test harness
            process = subprocess.run(
                [self.python_executable, str(harness_path)],
                cwd=str(working_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=self._get_execution_env(),
            )
            
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Truncate output if too long
            stdout = process.stdout[:self.max_output_bytes] if process.stdout else ""
            stderr = process.stderr[:self.max_output_bytes] if process.stderr else ""
            
            # Determine outcome
            if process.returncode == 0:
                return ExecutionResult(
                    passed=True,
                    outcome=Outcome.PASS,
                    stdout=stdout,
                    stderr=stderr,
                    execution_time_ms=execution_time_ms,
                )
            else:
                # Parse the error type from stderr
                outcome = Outcome.from_stderr(stderr)
                error_type, error_message = self._parse_error(stderr)
                
                return ExecutionResult(
                    passed=False,
                    outcome=outcome,
                    stdout=stdout,
                    stderr=stderr,
                    error_type=error_type,
                    error_message=error_message,
                    execution_time_ms=execution_time_ms,
                )
                
        except subprocess.TimeoutExpired as e:
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            return ExecutionResult(
                passed=False,
                outcome=Outcome.TIMEOUT,
                stdout=e.stdout[:self.max_output_bytes] if e.stdout else "",
                stderr=e.stderr[:self.max_output_bytes] if e.stderr else "",
                error_type="TimeoutError",
                error_message=f"Execution exceeded {self.timeout_seconds}s timeout",
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            return ExecutionResult(
                passed=False,
                outcome=Outcome.ERROR_OTHER,
                error_type=type(e).__name__,
                error_message=str(e),
                execution_time_ms=execution_time_ms,
            )
    
    def _get_execution_env(self) -> Dict[str, str]:
        """Get the environment variables for execution."""
        env = os.environ.copy()
        
        # Ensure UTF-8 encoding
        env["PYTHONIOENCODING"] = "utf-8"
        
        # Don't buffer output
        env["PYTHONUNBUFFERED"] = "1"
        
        # Add IBM Quantum token if available
        ibm_token = os.getenv("IBM_QUANTUM_TOKEN")
        if ibm_token:
            env["IBM_QUANTUM_TOKEN"] = ibm_token
        
        return env
    
    def _parse_error(self, stderr: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse error type and message from stderr.
        
        Returns:
            Tuple of (error_type, error_message)
        """
        if not stderr:
            return None, None
        
        lines = stderr.strip().split('\n')
        
        # Look for the last error line (usually the most specific)
        for line in reversed(lines):
            line = line.strip()
            if ': ' in line:
                parts = line.split(': ', 1)
                error_type = parts[0].strip()
                error_message = parts[1].strip() if len(parts) > 1 else ""
                
                # Clean up common prefixes
                for prefix in ['Test error: ', 'Error executing candidate code: ']:
                    if error_type.startswith(prefix):
                        error_type = error_type[len(prefix):]
                
                return error_type, error_message
        
        # Fallback: return the last line
        return "Error", lines[-1] if lines else "Unknown error"
