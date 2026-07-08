"""Structural parsing of Python source via the stdlib ast module.

Produces semantic artifacts (module/class/function/method) with
deterministic, provenance-carrying facts extracted from the AST —
no LLM involved, so code facts are always grounded.
"""

import ast
import logging
from dataclasses import dataclass, field

log = logging.getLogger("cortex.ingestion.python")


@dataclass
class ParsedArtifact:
    kind: str  # 'module' | 'class' | 'function' | 'method'
    qualified_name: str  # e.g. "src/auth.py::AuthService.verify"
    span_start_line: int
    span_end_line: int
    raw_text: str
    facts: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedEdge:
    from_qualified_name: str
    to_name: str  # unresolved symbol/module name; resolved to artifacts in the link stage
    kind: str  # 'imports' | 'calls' | 'inherits' | 'contains'
    confidence: float = 1.0


def parse_python_file(path: str, content: str) -> tuple[list[ParsedArtifact], list[ParsedEdge]]:
    """Parse one Python file. Raises SyntaxError on unparseable input
    (caller falls back to a whole-file artifact)."""
    tree = ast.parse(content)
    lines = content.splitlines()
    artifacts: list[ParsedArtifact] = []
    edges: list[ParsedEdge] = []

    module_qn = path
    module_facts: list[dict] = []

    # Module-level imports and constants
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                edges.append(ParsedEdge(module_qn, alias.name, "imports"))
        elif isinstance(node, ast.ImportFrom) and node.module:
            edges.append(ParsedEdge(module_qn, node.module, "imports"))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    module_facts.append(
                        {
                            "type": "constant",
                            "name": target.id,
                            "value": _safe_unparse(node.value),
                            "provenance": {"line": node.lineno},
                        }
                    )

    docstring = ast.get_docstring(tree)
    artifacts.append(
        ParsedArtifact(
            kind="module",
            qualified_name=module_qn,
            span_start_line=1,
            span_end_line=len(lines),
            raw_text=content,
            facts=module_facts,
            metadata={"docstring": docstring} if docstring else {},
        )
    )

    def visit_scope(body: list[ast.stmt], parent_qn: str, class_name: str | None) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                qn = f"{path}::{_symbol_path(parent_qn, path, node.name)}"
                bases = [_safe_unparse(b) for b in node.bases]
                doc = ast.get_docstring(node)
                artifacts.append(
                    ParsedArtifact(
                        kind="class",
                        qualified_name=qn,
                        span_start_line=node.lineno,
                        span_end_line=node.end_lineno or node.lineno,
                        raw_text=_slice(lines, node),
                        facts=[
                            {"type": "signature", "value": f"class {node.name}({', '.join(bases)})"}
                        ],
                        metadata={"docstring": doc} if doc else {},
                    )
                )
                edges.append(ParsedEdge(parent_qn, qn, "contains"))
                for base in bases:
                    edges.append(ParsedEdge(qn, base, "inherits"))
                visit_scope(node.body, qn, node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qn = f"{path}::{_symbol_path(parent_qn, path, node.name)}"
                kind = "method" if class_name else "function"
                doc = ast.get_docstring(node)
                artifacts.append(
                    ParsedArtifact(
                        kind=kind,
                        qualified_name=qn,
                        span_start_line=node.lineno,
                        span_end_line=node.end_lineno or node.lineno,
                        raw_text=_slice(lines, node),
                        facts=[{"type": "signature", "value": _signature(node)}],
                        metadata={"docstring": doc} if doc else {},
                    )
                )
                edges.append(ParsedEdge(parent_qn, qn, "contains"))
                for called in _called_names(node):
                    edges.append(ParsedEdge(qn, called, "calls", confidence=0.8))

    visit_scope(tree.body, module_qn, None)
    return artifacts, edges


def _symbol_path(parent_qn: str, path: str, name: str) -> str:
    if parent_qn == path:  # parent is the module itself
        return name
    parent_symbol = parent_qn.split("::", 1)[1]
    return f"{parent_symbol}.{name}"


def _slice(lines: list[str], node: ast.stmt) -> str:
    end = node.end_lineno or node.lineno
    return "\n".join(lines[node.lineno - 1 : end])


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = ", ".join(a.arg for a in node.args.args)
    returns = f" -> {_safe_unparse(node.returns)}" if node.returns else ""
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({args}){returns}"


def _called_names(node: ast.stmt) -> list[str]:
    """Best-effort call targets inside a function body (name or dotted path)."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            target = _call_target(child.func)
            if target:
                names.add(target)
    return sorted(names)


def _call_target(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        base = _call_target(func.value)
        return f"{base}.{func.attr}" if base else func.attr
    return None


def _safe_unparse(node: ast.expr | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001 — never fail parsing over one expression
        return "<unparseable>"
