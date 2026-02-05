"""
Code extraction from model outputs.

Handles extracting Python code from various model output formats
including markdown code blocks, raw code, and mixed content.
"""

import ast
import re
import textwrap
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
    
    # Pattern for markdown code blocks
    MARKDOWN_PATTERN = re.compile(
        r'```(?:python|py)?\s*\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )
    
    # Pattern for function definitions
    FUNCTION_PATTERN = re.compile(
        r'^((?:async\s+)?def\s+\w+\s*\([^)]*\).*?)(?=\n(?:def\s|\Z|class\s|if\s+__name__))',
        re.MULTILINE | re.DOTALL
    )
    
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
            ("function_search", lambda x: self._extract_function(x, entry_point)),
            ("raw", self._extract_raw_code),
        ]
        
        for method_name, extractor in methods:
            code = extractor(model_output)
            if code:
                code = self._normalize_code(code)
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
            code=self._normalize_code(model_output) if allow_partial else "",
            method="fallback",
            error=error or "Could not extract valid code",
            entry_point_found=has_entry_point,
        )
    
    def _extract_from_markdown(self, text: str) -> str:
        """Extract code from markdown code blocks."""
        matches = self.MARKDOWN_PATTERN.findall(text)
        if matches:
            # Join all code blocks (in case there are multiple)
            return "\n\n".join(match.strip() for match in matches)
        return ""
    
    def _extract_function(self, text: str, entry_point: str) -> str:
        """Extract a specific function from the text."""
        # First try to find the exact function definition
        pattern = rf'^((?:async\s+)?def\s+{re.escape(entry_point)}\s*\([^)]*\).*?)(?=\n(?:def\s|\Z|class\s|if\s+__name__))'
        match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
        
        if match:
            # Include any imports before the function
            imports = self._extract_imports(text)
            function_code = match.group(1).strip()
            if imports:
                return imports + "\n\n" + function_code
            return function_code
        
        return ""
    
    def _extract_raw_code(self, text: str) -> str:
        """Extract code assuming the text is raw Python."""
        # Try to find the start of Python code
        lines = text.split('\n')
        code_lines = []
        in_code = False
        
        for line in lines:
            stripped = line.strip()
            
            # Heuristics for code detection
            if (stripped.startswith(('import ', 'from ', 'def ', 'class ', '@'))
                or stripped.startswith('#')
                or (in_code and (line.startswith((' ', '\t')) or not stripped))):
                in_code = True
                code_lines.append(line)
            elif in_code and stripped and not stripped.startswith(('*', '-', '>')):
                # Continue if it looks like code
                if any(c in stripped for c in ['=', '(', ')', '[', ']', ':', '+', '-']):
                    code_lines.append(line)
                elif stripped.isidentifier() or stripped.startswith(('return', 'if', 'for', 'while', 'try', 'with')):
                    code_lines.append(line)
                else:
                    # Probably end of code
                    break
        
        return '\n'.join(code_lines).strip()

    def _normalize_code(self, code: str) -> str:
        """Normalize indentation and trim leading/trailing blank lines."""
        if not code:
            return code
        # Remove leading/trailing blank lines first
        stripped = code.strip("\n")
        # Dedent common leading whitespace
        dedented = textwrap.dedent(stripped)
        # Ensure no leading blank lines remain
        return dedented.lstrip("\n")
    
    def _extract_imports(self, text: str) -> str:
        """Extract import statements from text."""
        import_lines = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ')):
                import_lines.append(stripped)
        return '\n'.join(import_lines)
    
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
            pattern = rf'def\s+{re.escape(entry_point)}\s*\('
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
