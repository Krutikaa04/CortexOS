import pytest

from cortex import graphstore
from cortex.config import get_settings
from cortex.ingestion.gitfetch import _authenticated_uri
from cortex.security import ValidationError, validate_repo_uri


def test_query_tokens_split_and_stem():
    t = graphstore.query_tokens("What happens when authentication fails in TokenService?")
    assert "auth" in t and "token" in t and "service" in t and "the" not in t


def test_reasoning_path_walks_parents_to_anchor():
    found = {
        "anchor_meta": {"a": {"name": "A", "kind": "function", "path": "a.py"}},
        "nodes": {
            "b": {"hop": 1, "name": "B", "kind": "function", "path": "b.py",
                  "parent": {"aid": "a", "rel": "CALLS", "from_parent": False}},
            "c": {"hop": 2, "name": "C", "kind": "function", "path": "c.py",
                  "parent": {"aid": "b", "rel": "CALLS", "from_parent": False}},
        },
    }
    p = graphstore.reasoning_path(["a"], found, {"c"})
    assert {n["id"] for n in p["nodes"]} == {"a", "b", "c"}
    assert {"from": "c", "to": "b", "type": "CALLS", "confidence": 1.0} in p["edges"]


def test_dotted_identifier_is_first_anchor_and_filler_dropped():
    t = graphstore.query_tokens("If I modify Signer.unsign, what could be affected?")
    assert t[0] == "signer.unsign" and "modify" not in t and "affected" not in t


def test_is_test_path():
    for t in ("tests/test_x.py", "src/foo/__tests__/a.ts", "web/a.test.tsx", "pkg/conftest.py"):
        assert graphstore.is_test_path(t), t
    for p in ("src/itsdangerous/signer.py", "src/contest/main.py", "app/latest.py"):
        assert not graphstore.is_test_path(p), p


def test_disambiguate_prefers_same_file_then_production_code():
    from cortex.ingestion.pipeline import _disambiguate

    c = [(1, "src/a.py::Signer.sign"), (2, "tests/test_a.py::TestSigner.sign")]
    assert _disambiguate(c, "src/b.py::Serializer.dumps") == [c[0]]  # drop test candidate
    assert _disambiguate(c, "tests/test_a.py::T.run") == [c[1]]  # same file wins
    amb = [(1, "src/a.py::X.f"), (2, "src/b.py::Y.f")]
    assert _disambiguate(amb, "src/c.py::Z.g") == amb  # no evidence: stays ambiguous


def test_token_only_sent_to_allowed_hosts(monkeypatch):
    monkeypatch.setenv("CORTEX_GIT_TOKEN", "secret")
    get_settings.cache_clear()
    try:
        assert "secret" in _authenticated_uri("https://github.com/o/r")
        assert "secret" not in _authenticated_uri("https://evil.example.com/o/r")
    finally:
        get_settings.cache_clear()


def test_production_restricts_hosts(monkeypatch):
    monkeypatch.setenv("CORTEX_ENV", "production")
    get_settings.cache_clear()
    try:
        assert validate_repo_uri("https://github.com/o/r")
        for bad in ("http://github.com/o/r", "https://169.254.169.254/x", "git://github.com/o/r"):
            with pytest.raises(ValidationError):
                validate_repo_uri(bad)
    finally:
        get_settings.cache_clear()
