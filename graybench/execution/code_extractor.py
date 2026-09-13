"""
Code extraction from model outputs.

Handles extracting Python code from various model output formats
including markdown code blocks, raw code, and mixed content.
"""

import ast
import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ExtractionResult:
    """Result of code extraction from model output."""

    success: bool
    code: str
    method: str  # How the code was extracted
    error: Optional[str] = None
    entry_point_found: bool = False

    @property
    def has_code(self) -> bool:
        """Check if any code was extracted."""
        return bool(self.code.strip())


class CodeExtractor:
    """
    Extracts Python code from model outputs.

    Handles various formats:
    - Markdown code blocks (```python ... ```)
    - Raw Python code
    - Code mixed with explanations
    """

    def extract(
        self,
        model_output: str,
        entry_point: str,
        allow_partial: bool = True,
    ) -> ExtractionResult:
        """
        Extract code from model output.

        Args:
            model_output: The raw output from the model
            entry_point: The function name that should be defined
            allow_partial: If True, try to extract partial code even if incomplete

        Returns:
            ExtractionResult with the extracted code
        """
        if not model_output or not model_output.strip():
            return ExtractionResult(
                success=False,
                code="",
                method="none",
                error="Empty model output",
            )

        # Try different extraction methods in order
        methods = [
            ("markdown", self._extract_from_markdown),
            ("raw", lambda text: text),
        ]

        for method_name, extractor in methods:
            code = extractor(model_output)
            if code:
                # Preserve indentation: normal HumanEval responses may be function bodies.
                code = code.strip("\r\n")
                # Verify the code and check for entry point
                is_valid, error = self._validate_code(code)
                has_entry_point = self._has_entry_point(code, entry_point)

                if is_valid or allow_partial:
                    return ExtractionResult(
                        success=is_valid and has_entry_point,
                        code=code,
                        method=method_name,
                        error=error if not is_valid else None,
                        entry_point_found=has_entry_point,
                    )

        # Last resort: return the whole output
        is_valid, error = self._validate_code(model_output)
        has_entry_point = self._has_entry_point(model_output, entry_point)

        return ExtractionResult(
            success=False,
            code=model_output.strip("\r\n") if allow_partial else "",
            method="fallback",
            error=error or "Could not extract valid code",
            entry_point_found=has_entry_point,
        )

    def _extract_from_markdown(self, text: str) -> str:
        """Parse fences in order, including ignored non-Python blocks.

        A closing bash fence must never be mistaken for an opening Python fence.
        Prefer all explicitly Python blocks; use untagged blocks only if none are
        labeled Python. Untagged example output must not pollute labeled code.
        """
        blocks = []
        untagged_blocks = []
        fence = None
        language = None
        lines = []
        for line in text.splitlines():
            if fence is None:
                opening = re.fullmatch(r" {0,3}(`{3,}|~{3,})([^`]*)", line)
                if opening:
                    fence, language = opening.group(1), opening.group(2).strip().lower()
                    lines = []
            elif re.fullmatch(
                r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line
            ):
                if language in ("", "python", "py"):
                    (blocks if language else untagged_blocks).append("\n".join(lines))
                fence = None
            else:
                lines.append(line)
        if fence is not None and language in ("", "python", "py"):
            (blocks if language else untagged_blocks).append("\n".join(lines))
        return "\n\n".join(blocks or untagged_blocks)

    def _validate_code(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that the code is syntactically correct Python.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not code.strip():
            return False, "Empty code"

        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, f"SyntaxError: {e.msg} at line {e.lineno}"
        except Exception as e:
            return False, str(e)

    def _has_entry_point(self, code: str, entry_point: str) -> bool:
        """Check if the code defines the required function."""
        if not entry_point:
            return True

        # Use AST to check for function definition
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == entry_point:
                        return True
        except SyntaxError:
            # Fall back to regex if parsing fails
            pattern = rf"def\s+{re.escape(entry_point)}\s*\("
            return bool(re.search(pattern, code))

        return False


def extract_code(
    model_output: str,
    entry_point: str,
    allow_partial: bool = True,
) -> ExtractionResult:
    """
    Convenience function to extract code from model output.

    Args:
        model_output: The raw output from the model
        entry_point: The function name that should be defined
        allow_partial: If True, try to extract partial code even if incomplete

    Returns:
        ExtractionResult with the extracted code
    """
    extractor = CodeExtractor()
    return extractor.extract(model_output, entry_point, allow_partial)
