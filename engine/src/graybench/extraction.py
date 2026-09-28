"""One predeclared extraction rule; no repair, oracle-guided selection, or helper injection."""

import ast
import re
from dataclasses import dataclass
from typing import get_args

from graybench.contracts import ExtractionPolicy, PublicTask

EXTRACTION_POLICIES = get_args(ExtractionPolicy)
FENCE = re.compile(r"^```([^\n`]*)\r?\n(.*?)^```[ \t]*$", flags=re.MULTILINE | re.DOTALL)
FENCE_V2_MULTIBLOCK = re.compile(
    r"^```([^\n`]*)\r?\n(.*?)^```[ \t]*\r?$", flags=re.MULTILINE | re.DOTALL
)
FENCE_V3 = re.compile(
    r"^( {0,3})```([^\n`]*)\r?\n(.*?)^ {0,3}```[ \t]*\r?$",
    flags=re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True)
class Extracted:
    code: str
    method: str
    error: str | None = None
    public_prefix: str = ""


@dataclass(frozen=True)
class FenceBlock:
    info: str
    code: str
    start: int
    end: int


def _fence_blocks(text: str, pattern: re.Pattern, *, indented: bool) -> list[FenceBlock]:
    blocks = []
    for match in pattern.finditer(text):
        if indented:
            spaces = len(match[1])
            code = "\n".join(
                line[min(spaces, len(line) - len(line.lstrip(" "))) :]
                for line in match[3].split("\n")
            )
            info = match[2]
        else:
            code, info = match[2], match[1]
        blocks.append(FenceBlock(info, code, match.start(), match.end()))
    return blocks


def _class_declares_global(body: list[ast.stmt], name: str) -> bool:
    def declares(node: ast.AST) -> bool:
        if isinstance(node, ast.Global):
            return name in node.names
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return False
        return any(declares(child) for child in ast.iter_child_nodes(node))

    return any(declares(statement) for statement in body)


def _entrypoint_bindings(node: ast.AST, name: str, *, active: bool = True) -> int:
    """Count bindings in the module scope, including executed class-body globals."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        # The body has its own scope. Decorators, defaults, and annotations are
        # evaluated in the containing scope when the definition is constructed.
        evaluated = [*node.decorator_list, node.args, node.returns, *node.type_params]
        return int(active and node.name == name) + sum(
            _entrypoint_bindings(child, name, active=active)
            for child in evaluated
            if child is not None
        )
    if isinstance(node, ast.ClassDef):
        evaluated = [*node.decorator_list, *node.bases, *node.keywords, *node.type_params]
        body_active = _class_declares_global(node.body, name)
        return (
            int(active and node.name == name)
            + sum(_entrypoint_bindings(child, name, active=active) for child in evaluated)
            + sum(_entrypoint_bindings(child, name, active=body_active) for child in node.body)
        )
    if isinstance(node, ast.Lambda):
        return _entrypoint_bindings(node.args, name, active=active)
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        # Comprehension loop targets live in a local scope. Assignment
        # expressions in their element/filter expressions bind outside it.
        expressions = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
        for generator in node.generators:
            expressions.extend([generator.iter, *generator.ifs])
        return sum(_entrypoint_bindings(child, name, active=active) for child in expressions)
    if isinstance(node, ast.Import):
        return int(active) * sum(
            (alias.asname or alias.name.split(".", 1)[0]) == name for alias in node.names
        )
    if isinstance(node, ast.ImportFrom):
        # A wildcard import may bind any public entry point; do not inspect or
        # execute the module to decide whether it happens to contain this one.
        return int(active) * sum(
            alias.name == "*" or (alias.asname or alias.name) == name for alias in node.names
        )
    if isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
        binding = int(active and node.name == name)
    elif isinstance(node, ast.MatchMapping):
        binding = int(active and node.rest == name)
    else:
        binding = 0
    return (
        binding
        + int(
            active
            and isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Store)
            and node.id == name
        )
        + sum(
            _entrypoint_bindings(child, name, active=active) for child in ast.iter_child_nodes(node)
        )
    )


def _v2_multifence(
    text: str, task: PublicTask, fences: list[FenceBlock], policy: ExtractionPolicy
) -> Extracted:
    definition = re.compile(
        rf"(?m)^[ \t]*(?:(?:async[ \t]+)?def|class)[ \t]+{re.escape(task.entry_point)}\b"
    )
    assignment = re.compile(
        rf"(?m)^[ \t]*{re.escape(task.entry_point)}\b[ \t]*(?:[+\-*/%@&|^=]|<<|>>|:)"
    )
    outside = "".join(
        text[end:start]
        for end, start in zip(
            (0, *(fence.end for fence in fences)),
            (*(fence.start for fence in fences), len(text)),
            strict=True,
        )
    )
    if definition.search(outside) or assignment.search(outside):
        return Extracted("", "rejected", "Expected one unambiguous entry-point Python code block")
    matches = []
    for fence in fences:
        if fence.info.strip().lower() not in {"", "python", "py"}:
            if policy == "unique_entrypoint_fence_v3":
                try:
                    mislabeled_tree = ast.parse(fence.code)
                except (SyntaxError, ValueError, UnicodeError, RecursionError):
                    ambiguous = bool(definition.search(fence.code) or assignment.search(fence.code))
                else:
                    ambiguous = bool(_entrypoint_bindings(mislabeled_tree, task.entry_point))
                if ambiguous:
                    return Extracted(
                        "", "rejected", "Expected one unambiguous entry-point Python code block"
                    )
            continue
        code = fence.code
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError, UnicodeError, RecursionError):
            if definition.search(code) or assignment.search(code):
                return Extracted(
                    "", "rejected", "Expected one unambiguous entry-point Python code block"
                )
            continue
        definitions = sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == task.entry_point
            for node in tree.body
        )
        bindings = _entrypoint_bindings(tree, task.entry_point)
        if bindings and (definitions != 1 or bindings != 1):
            return Extracted(
                "", "rejected", "Expected one unambiguous entry-point Python code block"
            )
        if definitions == 1:
            matches.append(code)
    if len(matches) != 1:
        return Extracted("", "rejected", "Expected one unambiguous entry-point Python code block")
    return Extracted(matches[0], policy)


def extract(
    text: str,
    task: PublicTask,
    policy: ExtractionPolicy = "raw_or_single_python_fence_v1",
) -> Extracted:
    if policy not in EXTRACTION_POLICIES:
        raise ValueError("Unknown extraction policy")
    if policy == "exact_prompt_suffix_v1":
        if task.prompt_format != "function_completion":
            return Extracted(
                "", "rejected", "Exact prompt suffix requires a function-completion task"
            )
        try:
            text.encode("utf-8")
            code = task.prompt + text
            ast.parse(code)
        except (SyntaxError, ValueError, UnicodeError, RecursionError):
            return Extracted("", "rejected", "Invalid exact prompt suffix")
        return Extracted(code, policy)
    if policy in {"unique_entrypoint_fence_v2", "unique_entrypoint_fence_v3"}:
        try:
            text.encode("utf-8")
        except UnicodeEncodeError:
            return Extracted("", "rejected", "Response is not UTF-8 encodable")
    if "```" in text:
        fence_pattern = (
            FENCE_V3
            if policy == "unique_entrypoint_fence_v3"
            else FENCE_V2_MULTIBLOCK
            if policy == "unique_entrypoint_fence_v2" and text.count("```") > 2
            else FENCE
        )
        fences = _fence_blocks(text, fence_pattern, indented=policy == "unique_entrypoint_fence_v3")
        if policy == "raw_or_single_python_fence_v1" and (
            len(fences) != 1 or fences[0].info.strip().lower() not in {"", "python", "py"}
        ):
            return Extracted("", "rejected", "Expected one unambiguous Python code block")
        if text.count("```") != 2 * len(fences):
            return Extracted("", "rejected", "Ambiguous fence delimiters")
        if len(fences) == 1:
            if fences[0].info.strip().lower() not in {"", "python", "py"}:
                return Extracted("", "rejected", "Expected one unambiguous Python code block")
            code, method = fences[0].code, "single_fence"
        elif (
            policy in {"unique_entrypoint_fence_v2", "unique_entrypoint_fence_v3"}
            and len(fences) > 1
        ):
            selected = _v2_multifence(text, task, fences, policy)
            if selected.error:
                return selected
            code, method = selected.code, selected.method
        else:
            return Extracted("", "rejected", "Expected one unambiguous Python code block")
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
        except (ValueError, UnicodeError, RecursionError):
            if policy in {"unique_entrypoint_fence_v2", "unique_entrypoint_fence_v3"}:
                return Extracted("", "rejected", "Invalid Python source")
            raise
        if not full:
            code = task.prompt + code
            method += "+prompt"
        else:
            prompt_tree = ast.parse(task.prompt)
            definition = next(
                n
                for n in prompt_tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name == task.entry_point
            )
            # Execute the given public prefix separately so a generated future import remains
            # legal. No test/reference imports or inferred helper definitions enter this namespace.
            prefix = "".join(task.prompt.splitlines(keepends=True)[: definition.lineno - 1])
            return Extracted(code, method, public_prefix=prefix)
    return Extracted(code, method)
