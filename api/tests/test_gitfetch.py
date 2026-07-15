import cortex.ingestion.gitfetch as g
from cortex.config import Settings


def _with_token(monkeypatch, token: str) -> None:
    monkeypatch.setattr(g, "get_settings", lambda: Settings(git_token=token))


def test_scrub_removes_embedded_credentials():
    msg = "git clone https://x-access-token:SECRET@github.com/o/r.git failed: fatal"
    scrubbed = g._scrub(msg)
    assert "SECRET" not in scrubbed
    assert "https://github.com/o/r.git" in scrubbed


def test_authenticated_uri_injects_token_for_https(monkeypatch):
    _with_token(monkeypatch, "TOK")
    assert g._authenticated_uri("https://github.com/o/r.git") == (
        "https://x-access-token:TOK@github.com/o/r.git"
    )


def test_authenticated_uri_public_when_no_token(monkeypatch):
    _with_token(monkeypatch, "")
    assert g._authenticated_uri("https://github.com/o/r.git") == "https://github.com/o/r.git"


def test_authenticated_uri_leaves_local_and_credentialed_untouched(monkeypatch):
    _with_token(monkeypatch, "TOK")
    assert g._authenticated_uri("/local/path") == "/local/path"
    assert g._authenticated_uri("git@github.com:o/r.git") == "git@github.com:o/r.git"
    # already carries credentials — don't double-inject
    assert g._authenticated_uri("https://u@github.com/o/r.git") == "https://u@github.com/o/r.git"
