"""
Outcome categories for code execution.

Provides fine-grained categorization of execution results
for detailed analysis of model performance.
"""

from enum import Enum


class Outcome(Enum):
    """
    Detailed outcome categories for code execution.

    These categories allow for fine-grained analysis of why
    a model's solution passed or failed.
    """

    # Success
    PASS = "pass"

    # Test failures (code ran but didn't pass tests)
    FAIL_TEST = "fail_test"
    FAIL_ASSERTION = "fail_assertion"

    # Syntax/parsing errors (code couldn't be parsed)
    FAIL_SYNTAX = "fail_syntax"
    FAIL_INDENTATION = "fail_indentation"

    # Import/dependency errors
    FAIL_IMPORT = "fail_import"
    FAIL_MODULE_NOT_FOUND = "fail_module_not_found"

    # Runtime errors
    FAIL_RUNTIME = "fail_runtime"
    FAIL_TYPE_ERROR = "fail_type_error"
    FAIL_NAME_ERROR = "fail_name_error"
    FAIL_ATTRIBUTE_ERROR = "fail_attribute_error"
    FAIL_VALUE_ERROR = "fail_value_error"
    FAIL_INDEX_ERROR = "fail_index_error"
    FAIL_KEY_ERROR = "fail_key_error"

    # Resource errors
    TIMEOUT = "timeout"
    MEMORY_ERROR = "memory_error"
    OUTPUT_LIMIT = "output_limit"

    # Extraction errors (couldn't extract code from model output)
    EXTRACTION_FAILED = "extraction_failed"
    NO_FUNCTION_FOUND = "no_function_found"

    # Other errors
    ERROR_OTHER = "error_other"
    API_ERROR = "api_error"
    EMPTY_COMPLETION = "empty_completion"

    @classmethod
    def from_exception(cls, exception: Exception) -> "Outcome":
        """
        Determine the outcome category from an exception.

        Args:
            exception: The exception that was raised

        Returns:
            The appropriate Outcome category
        """
        exception_name = type(exception).__name__

        # Map exception types to outcomes
        mapping = {
            "SyntaxError": cls.FAIL_SYNTAX,
            "IndentationError": cls.FAIL_INDENTATION,
            "TabError": cls.FAIL_INDENTATION,
            "ImportError": cls.FAIL_IMPORT,
            "ModuleNotFoundError": cls.FAIL_MODULE_NOT_FOUND,
            "TypeError": cls.FAIL_TYPE_ERROR,
            "NameError": cls.FAIL_NAME_ERROR,
            "AttributeError": cls.FAIL_ATTRIBUTE_ERROR,
            "ValueError": cls.FAIL_VALUE_ERROR,
            "IndexError": cls.FAIL_INDEX_ERROR,
            "KeyError": cls.FAIL_KEY_ERROR,
            "AssertionError": cls.FAIL_ASSERTION,
            "TimeoutError": cls.TIMEOUT,
            "MemoryError": cls.MEMORY_ERROR,
        }

        return mapping.get(exception_name, cls.ERROR_OTHER)

    @classmethod
    def from_stderr(cls, stderr: str) -> "Outcome":
        """
        Determine the outcome category from stderr output.

        Args:
            stderr: The captured stderr output

        Returns:
            The appropriate Outcome category
        """
        stderr_lower = stderr.lower()

        # Check for specific error types in order of specificity
        if "syntaxerror" in stderr_lower:
            return cls.FAIL_SYNTAX
        if "indentationerror" in stderr_lower or "taberror" in stderr_lower:
            return cls.FAIL_INDENTATION
        if "modulenotfounderror" in stderr_lower:
            return cls.FAIL_MODULE_NOT_FOUND
        if "importerror" in stderr_lower:
            return cls.FAIL_IMPORT
        if "assertionerror" in stderr_lower:
            return cls.FAIL_ASSERTION
        if "typeerror" in stderr_lower:
            return cls.FAIL_TYPE_ERROR
        if "nameerror" in stderr_lower:
            return cls.FAIL_NAME_ERROR
        if "attributeerror" in stderr_lower:
            return cls.FAIL_ATTRIBUTE_ERROR
        if "valueerror" in stderr_lower:
            return cls.FAIL_VALUE_ERROR
        if "indexerror" in stderr_lower:
            return cls.FAIL_INDEX_ERROR
        if "keyerror" in stderr_lower:
            return cls.FAIL_KEY_ERROR
        if "memoryerror" in stderr_lower:
            return cls.MEMORY_ERROR
        if "timeout" in stderr_lower:
            return cls.TIMEOUT

        # Generic failure
        if stderr.strip():
            return cls.FAIL_RUNTIME

        return cls.ERROR_OTHER

    @property
    def is_pass(self) -> bool:
        """Check if this outcome represents a passing result."""
        return self == Outcome.PASS

    @property
    def is_test_failure(self) -> bool:
        """Check if this outcome is a test failure (code ran but failed tests)."""
        return self in (Outcome.FAIL_TEST, Outcome.FAIL_ASSERTION)

    @property
    def is_syntax_error(self) -> bool:
        """Check if this outcome is a syntax-related error."""
        return self in (Outcome.FAIL_SYNTAX, Outcome.FAIL_INDENTATION)

    @property
    def is_import_error(self) -> bool:
        """Check if this outcome is an import-related error."""
        return self in (Outcome.FAIL_IMPORT, Outcome.FAIL_MODULE_NOT_FOUND)

    @property
    def is_runtime_error(self) -> bool:
        """Check if this outcome is a runtime error."""
        return self in (
            Outcome.FAIL_RUNTIME,
            Outcome.FAIL_TYPE_ERROR,
            Outcome.FAIL_NAME_ERROR,
            Outcome.FAIL_ATTRIBUTE_ERROR,
            Outcome.FAIL_VALUE_ERROR,
            Outcome.FAIL_INDEX_ERROR,
            Outcome.FAIL_KEY_ERROR,
        )

    @property
    def category(self) -> str:
        """Get the high-level category for this outcome."""
        if self.is_pass:
            return "pass"
        if self.is_test_failure:
            return "test_failure"
        if self.is_syntax_error:
            return "syntax_error"
        if self.is_import_error:
            return "import_error"
        if self.is_runtime_error:
            return "runtime_error"
        if self == Outcome.TIMEOUT:
            return "timeout"
        if self in (Outcome.MEMORY_ERROR, Outcome.OUTPUT_LIMIT):
            return "resource_error"
        if self in (Outcome.EXTRACTION_FAILED, Outcome.NO_FUNCTION_FOUND):
            return "extraction_error"
        return "other_error"


# Backwards compatibility alias
OutcomeCategory = Outcome
