"""Structural parsing of JavaScript / TypeScript source.

CortexOS's Kernel is language-agnostic — the Knowledge Graph, Architecture
view, Dependency Explorer and Change Impact Guard all reason over the same
``semantic_artifact`` / ``artifact_edge`` rows regardless of source language.
This module makes JS/TS a first-class citizen of that graph so blast-radius
and repository reasoning cross the Python↔JS boundary.

It deliberately uses no third-party parser (tree-sitter, esprima): the
runtime must stay zero-dependency and zero-cost. A pragmatic brace-aware
scanner extracts the structural facts the graph needs — modules, classes,
functions/methods, imports, `extends`, and call targets — reusing the exact
``ParsedArtifact`` / ``ParsedEdge`` contract the Python parser emits, so the
ingestion pipeline and linker treat both identically.

Import edges are pre-resolved to repository-relative paths here (the parser
knows the importing file), so the language-neutral link stage can match them
to module artifacts without any JS-specific knowledge.
"""

from __future__ import annotations

import posixpath
import re

# Reuse the Python parser's dataclasses so the pipeline is language-agnostic.
from cortex.ingestion.python_parser import ParsedArtifact, ParsedEdge

JS_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts")

# Keywords that look like a call `name(` but are control flow, not a callee.
_CALL_STOPWORDS = {
    "if", "for", "while", "switch", "catch", "return", "function", "await",
    "typeof", "new", "super", "constructor", "yield", "void", "delete", "in",
    "of", "do", "else", "case", "throw", "with",
}

_IMPORT_FROM = re.compile(r"""\bimport\b[^;'"]*?\bfrom\s*['"]([^'"]+)['"]""")
_IMPORT_BARE = re.compile(r"""\bimport\s*['"]([^'"]+)['"]""")
_EXPORT_FROM = re.compile(r"""\bexport\b[^;'"]*?\bfrom\s*['"]([^'"]+)['"]""")
_REQUIRE = re.compile(r"""\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)""")

_CLASS = re.compile(
    r"\bclass\s+([A-Za-z_$][\w$]*)(?:\s*extends\s+([A-Za-z_$][\w$.]*))?"
)
# function declarations: `function foo(` / `export async function foo(`
_FUNC_DECL = re.compile(r"\bfunction\s*\*?\s+([A-Za-z_$][\w$]*)\s*\(")
# assigned functions/arrows: `const foo = (…) =>` / `let bar = function`
_FUNC_ASSIGN = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*[=:]\s*"
    r"(?:async\s+)?(?:function\b|\([^)]*\)\s*(?::[^=]+)?=>|[A-Za-z_$][\w$]*\s*=>)"
)
_CALL = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")


def _blank_comments(src: str) -> str:
    """Blank line/block comments only, preserving strings (imports live in
    strings). Length and newlines preserved for accurate line numbers."""
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        two = src[i : i + 2]
        if two == "//":
            j = src.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        elif two == "/*":
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append("".join("\n" if ch == "\n" else " " for ch in src[i:j]))
            i = j
        elif src[i] in "'\"`":
            c = src[i]
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 2
                    continue
                j += 1
            out.append(src[i : j + 1])
            i = min(j + 1, n)
        else:
            out.append(src[i])
            i += 1
    return "".join(out)


def _strip_noise(src: str) -> str:
    """Blank out strings and comments so the structural regexes don't trip on
    braces or keywords inside them. Length and line breaks are preserved so
    line numbers stay accurate."""
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        two = src[i : i + 2]
        if two == "//":
            j = src.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        elif two == "/*":
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append("".join("\n" if ch == "\n" else " " for ch in src[i:j]))
            i = j
        elif c in "'\"`":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 2
                    continue
                if c == "`" and src[j] == "\n":
                    break
                j += 1
            out.append("".join("\n" if ch == "\n" else " " for ch in src[i : j + 1]))
            i = min(j + 1, n)
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _block_end(clean: str, open_brace: int) -> int:
    """Index just past the matching `}` for the `{` at ``open_brace``."""
    depth = 0
    for k in range(open_brace, len(clean)):
        if clean[k] == "{":
            depth += 1
        elif clean[k] == "}":
            depth -= 1
            if depth == 0:
                return k + 1
    return len(clean)


def _line_of(src: str, idx: int) -> int:
    return src.count("\n", 0, idx) + 1


def resolve_import(from_path: str, spec: str) -> str:
    """Resolve an import specifier to a repo-relative path (extension stripped).

    Relative specifiers ('./x', '../y') are resolved against the importing
    file's directory so the linker can match them to a module artifact. Bare
    specifiers ('react', '@scope/pkg') are external packages — returned as-is
    and left unresolved by the linker (no artifact exists for them).
    """
    if spec.startswith("."):
        base = posixpath.dirname(from_path)
        resolved = posixpath.normpath(posixpath.join(base, spec))
        return re.sub(r"\.(jsx?|tsx?|mjs|cjs|mts|cts)$", "", resolved)
    return spec


def _called_names(body: str) -> list[str]:
    names: set[str] = set()
    for m in _CALL.finditer(body):
        name = m.group(1)
        if name not in _CALL_STOPWORDS:
            names.add(name)
    return sorted(names)


def parse_js_file(path: str, content: str) -> tuple[list[ParsedArtifact], list[ParsedEdge]]:
    """Parse one JS/TS file into artifacts + unresolved edges.

    Never raises: JS/TS has no stdlib AST here, so on anything unexpected the
    caller still gets at least the module artifact and the import edges (the
    most valuable signal for cross-file reasoning)."""
    clean = _strip_noise(content)      # strings + comments blanked (structure)
    imports_src = _blank_comments(content)  # strings kept (import specifiers)
    module_qn = path
    artifacts: list[ParsedArtifact] = [
        ParsedArtifact(
            kind="module",
            qualified_name=module_qn,
            span_start_line=1,
            span_end_line=content.count("\n") + 1,
            raw_text=content,
            facts=[],
            metadata={"language": "javascript"},
        )
    ]
    edges: list[ParsedEdge] = []

    # --- imports (module-level dependency edges) ---
    seen_imports: set[str] = set()
    for pattern in (_IMPORT_FROM, _EXPORT_FROM, _IMPORT_BARE, _REQUIRE):
        for m in pattern.finditer(imports_src):
            target = resolve_import(path, m.group(1))
            if target not in seen_imports:
                seen_imports.add(target)
                edges.append(ParsedEdge(module_qn, target, "imports"))

    # --- classes (with methods + inheritance) ---
    class_spans: list[tuple[int, int]] = []
    for m in _CLASS.finditer(clean):
        name, base = m.group(1), m.group(2)
        brace = clean.find("{", m.end() - 1)
        if brace == -1:
            continue
        end = _block_end(clean, brace)
        class_spans.append((m.start(), end))
        qn = f"{path}::{name}"
        artifacts.append(
            ParsedArtifact(
                kind="class",
                qualified_name=qn,
                span_start_line=_line_of(content, m.start()),
                span_end_line=_line_of(content, end),
                raw_text=content[m.start():end],
                facts=[{"type": "signature",
                        "value": f"class {name}" + (f" extends {base}" if base else "")}],
                metadata={"language": "javascript"},
            )
        )
        edges.append(ParsedEdge(module_qn, qn, "contains"))
        if base:
            edges.append(ParsedEdge(qn, base.split(".")[-1], "inherits"))

        # methods inside the class body: `name(...) {`
        body = clean[brace + 1: end - 1]
        for mm in re.finditer(r"(?:^|\n)\s*(?:async\s+|static\s+|get\s+|set\s+)*"
                              r"([A-Za-z_$][\w$]*)\s*\([^;{]*\)\s*\{", body):
            mname = mm.group(1)
            if mname in _CALL_STOPWORDS:
                continue
            mstart = brace + 1 + mm.start(1)
            mopen = clean.find("{", brace + 1 + mm.end() - 1)
            mend = _block_end(clean, mopen) if mopen != -1 else mstart
            mqn = f"{path}::{name}.{mname}"
            artifacts.append(
                ParsedArtifact(
                    kind="method",
                    qualified_name=mqn,
                    span_start_line=_line_of(content, mstart),
                    span_end_line=_line_of(content, mend),
                    raw_text=content[mstart:mend],
                    facts=[{"type": "signature", "value": f"{name}.{mname}()"}],
                    metadata={"language": "javascript"},
                )
            )
            edges.append(ParsedEdge(qn, mqn, "contains"))
            for called in _called_names(clean[mopen:mend]):
                if called != mname:
                    edges.append(ParsedEdge(mqn, called, "calls", confidence=0.8))

    def _inside_class(pos: int) -> bool:
        return any(s <= pos < e for s, e in class_spans)

    # --- top-level functions (declarations + assigned arrows) ---
    for pattern in (_FUNC_DECL, _FUNC_ASSIGN):
        for m in pattern.finditer(clean):
            if _inside_class(m.start()):
                continue
            name = m.group(1)
            qn = f"{path}::{name}"
            if any(a.qualified_name == qn for a in artifacts):
                continue
            brace = clean.find("{", m.end() - 1)
            # arrow bodies may be single-expression (no brace) — cap the span
            if brace == -1 or (0 <= clean.find(";", m.end()) < brace):
                start_line = _line_of(content, m.start())
                artifacts.append(
                    ParsedArtifact(
                        kind="function", qualified_name=qn,
                        span_start_line=start_line, span_end_line=start_line,
                        raw_text=content.splitlines()[start_line - 1] if content else "",
                        facts=[{"type": "signature", "value": f"function {name}()"}],
                        metadata={"language": "javascript"},
                    )
                )
                edges.append(ParsedEdge(module_qn, qn, "contains"))
                continue
            end = _block_end(clean, brace)
            artifacts.append(
                ParsedArtifact(
                    kind="function", qualified_name=qn,
                    span_start_line=_line_of(content, m.start()),
                    span_end_line=_line_of(content, end),
                    raw_text=content[m.start():end],
                    facts=[{"type": "signature", "value": f"function {name}()"}],
                    metadata={"language": "javascript"},
                )
            )
            edges.append(ParsedEdge(module_qn, qn, "contains"))
            for called in _called_names(clean[brace:end]):
                if called != name:
                    edges.append(ParsedEdge(qn, called, "calls", confidence=0.8))

    return artifacts, edges
