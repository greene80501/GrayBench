"""One predeclared extraction rule; no repair, oracle-guided selection, or helper injection."""

import ast
import re
from dataclasses import dataclass

from graybench.contracts import PublicTask


@dataclass(frozen=True)
class Extracted:
    code: str
    method: str
    error: str | None = None


def extract(text: str, task: PublicTask) -> Extracted:
    if "```" in text:
        fences = list(
            re.finditer(r"^```([^\n`]*)\r?\n(.*?)^```[ \t]*$", text, flags=re.MULTILINE | re.DOTALL)
        )
        if len(fences) != 1 or fences[0][1].strip().lower() not in {"", "python", "py"}:
            return Extracted("", "rejected", "Expected one unambiguous Python code block")
        if text.count("```") != 2:
            return Extracted("", "rejected", "Ambiguous fence delimiters")
        code, method = fences[0][2], "single_fence"
    else:
        code, method = text, "raw"
    if not code.strip():
        return Extracted(code, method, "Empty answer")
    if task.prompt_format == "function_completion":
        # Full definitions are accepted only if they are syntactically present, not guessed.
        try:
            tree = ast.parse(code)
            full = any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == task.entry_point
                for node in tree.body
            )
        except SyntaxError:
            full = False
        if not full:
            code = task.prompt + code
            method += "+prompt"
    return Extracted(code, method)
