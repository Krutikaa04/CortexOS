import pytest

from cortex import security
from cortex.config import Settings
from cortex.security import (
    ValidationError,
    check_api_token,
    validate_git_ref,
    validate_repo_uri,
)


def _env(monkeypatch, **kw):
    monkeypatch.setattr(security, "get_settings", lambda: Settings(**kw))


def test_valid_remote_uris_pass():
    for uri in [
        "https://github.com/o/r.git",
        "http://host/o/r",
        "git://host/o/r",
        "git@github.com:o/r.git",
    ]:
        assert validate_repo_uri(uri, allow_local=False) == uri


def test_argument_injection_blocked():
    with pytest.raises(ValidationError):
        validate_repo_uri("--upload-pack=evil", allow_local=True)


def test_file_scheme_blocked():
    with pytest.raises(ValidationError):
        validate_repo_uri("file:///etc/passwd", allow_local=True)


def test_whitespace_and_empty_blocked():
    with pytest.raises(ValidationError):
        validate_repo_uri("https://h/ r")
    with pytest.raises(ValidationError):
        validate_repo_uri("   ")


def test_local_path_allowed_in_dev_blocked_in_prod():
    assert validate_repo_uri("/srv/repo", allow_local=True) == "/srv/repo"
    with pytest.raises(ValidationError):
        validate_repo_uri("/srv/repo", allow_local=False)


def test_path_traversal_blocked_even_local():
    with pytest.raises(ValidationError):
        validate_repo_uri("../../etc", allow_local=True)


def test_git_ref_validation():
    assert validate_git_ref("main") == "main"
    assert validate_git_ref("release/1.2.3") == "release/1.2.3"
    assert validate_git_ref(None) is None
    assert validate_git_ref("") is None
    with pytest.raises(ValidationError):
        validate_git_ref("--exec=payload")
    with pytest.raises(ValidationError):
        validate_git_ref("a b; rm -rf")


def test_api_token_open_when_unset(monkeypatch):
    _env(monkeypatch, api_token="")
    assert check_api_token(None) is True
    assert check_api_token("anything") is True


def test_api_token_enforced_when_set(monkeypatch):
    _env(monkeypatch, api_token="secret")
    assert check_api_token("Bearer secret") is True
    assert check_api_token("bearer secret") is True
    assert check_api_token("Bearer wrong") is False
    assert check_api_token(None) is False
    assert check_api_token("secret") is False


def test_per_user_tokens_and_stream_tickets(monkeypatch):
    from cortex.config import get_settings
    from cortex.security import (
        authenticate, make_stream_ticket, verify_stream_ticket,
    )

    monkeypatch.setenv("CORTEX_API_TOKENS", "alice:tok-a,bob:tok-b,bad entry")
    monkeypatch.setenv("CORTEX_API_TOKEN", "legacy")
    get_settings.cache_clear()
    try:
        assert authenticate("Bearer tok-a") == "alice"
        assert authenticate("Bearer tok-b") == "bob"
        assert authenticate("Bearer legacy") == "local"  # legacy token = local user
        assert authenticate("Bearer nope") is None
        assert authenticate(None) is None
        t = make_stream_ticket("exec-1", "alice")
        assert verify_stream_ticket(t, "exec-1") == "alice"
        assert verify_stream_ticket(t, "exec-2") is None  # bound to the execution
        assert verify_stream_ticket(t[:-2] + "00", "exec-1") is None  # tampered
        assert verify_stream_ticket(make_stream_ticket("exec-1", "alice", ttl=-5), "exec-1") is None
    finally:
        get_settings.cache_clear()
