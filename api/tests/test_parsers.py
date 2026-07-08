from cortex.ingestion.markdown_parser import parse_markdown_file
from cortex.ingestion.python_parser import parse_python_file

SAMPLE_PY = '''\
"""Auth service module."""

import hashlib
from datetime import timedelta

TOKEN_TTL = 900


class AuthService:
    """Verifies tokens."""

    def verify(self, token: str) -> bool:
        digest = hashlib.sha256(token.encode())
        return self._check(digest)

    def _check(self, digest) -> bool:
        return True


def make_service() -> AuthService:
    return AuthService()
'''

SAMPLE_MD = """\
Intro paragraph before any heading.

# Architecture

We use PostgreSQL.

## Database

### Decision

PostgreSQL with pgvector.

## API

FastAPI everywhere.
"""


def test_python_artifacts():
    artifacts, edges = parse_python_file("src/auth.py", SAMPLE_PY)
    by_qn = {a.qualified_name: a for a in artifacts}

    assert "src/auth.py" in by_qn  # module
    assert by_qn["src/auth.py"].facts[0]["name"] == "TOKEN_TTL"
    assert by_qn["src/auth.py"].facts[0]["value"] == "900"

    assert by_qn["src/auth.py::AuthService"].kind == "class"
    assert by_qn["src/auth.py::AuthService.verify"].kind == "method"
    assert by_qn["src/auth.py::make_service"].kind == "function"
    assert "def verify(self, token) -> bool" in by_qn["src/auth.py::AuthService.verify"].facts[0]["value"]


def test_python_edges():
    _, edges = parse_python_file("src/auth.py", SAMPLE_PY)
    kinds = {(e.kind, e.to_name) for e in edges}

    assert ("imports", "hashlib") in kinds
    assert ("imports", "datetime") in kinds
    assert ("contains", "src/auth.py::AuthService") in kinds
    assert ("contains", "src/auth.py::AuthService.verify") in kinds
    # verify() calls self._check -> best-effort call edge
    assert any(e.kind == "calls" and "_check" in e.to_name for e in edges)


def test_python_syntax_error_raises():
    import pytest

    with pytest.raises(SyntaxError):
        parse_python_file("bad.py", "def broken(:\n")


def test_markdown_sections():
    sections = parse_markdown_file("docs/arch.md", SAMPLE_MD)
    by_qn = {s.qualified_name: s for s in sections}

    assert "docs/arch.md#preamble" in by_qn
    assert "docs/arch.md#architecture" in by_qn
    assert "docs/arch.md#architecture/database/decision" in by_qn
    assert "PostgreSQL with pgvector." in by_qn["docs/arch.md#architecture/database/decision"].raw_text
    # sibling heading resets the stack correctly
    assert "docs/arch.md#architecture/api" in by_qn


def test_markdown_spans_cover_content():
    sections = parse_markdown_file("docs/arch.md", SAMPLE_MD)
    for s in sections:
        assert s.span_start_line <= s.span_end_line
        assert s.raw_text.strip()
