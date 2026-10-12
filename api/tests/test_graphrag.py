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
    assert {"from": "c", "to": "b", "type": "CALLS"} in p["edges"]


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
