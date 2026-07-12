from cortex.routes.graph import _github_blob_url


def test_github_url_from_https_remote():
    url = _github_blob_url(
        "https://github.com/pallets/itsdangerous", "abc123", "src/signer.py", 244, 256
    )
    assert url == "https://github.com/pallets/itsdangerous/blob/abc123/src/signer.py#L244-L256"


def test_github_url_strips_dot_git_and_scp_form():
    assert _github_blob_url("git@github.com:owner/repo.git", "sha", "a.py").startswith(
        "https://github.com/owner/repo/blob/sha/a.py"
    )


def test_github_url_single_line_anchor():
    url = _github_blob_url("https://github.com/o/r", "sha", "a.py", 10, 10)
    assert url.endswith("#L10")  # no redundant -L10 range for a single line


def test_github_url_none_for_local_path():
    assert _github_blob_url("C:/Users/x/scratch/demo-repo", "sha", "a.py", 1, 2) is None
    assert _github_blob_url("", "sha", "a.py") is None
