from cortex.kernel.impact import (
    classify_sensitivity,
    parse_unified_diff,
    score_risk,
)

DIFF = """\
diff --git a/src/itsdangerous/signer.py b/src/itsdangerous/signer.py
index 1111111..2222222 100644
--- a/src/itsdangerous/signer.py
+++ b/src/itsdangerous/signer.py
@@ -244,7 +244,9 @@ class Signer:
     def unsign(self, signed_value):
-        return want_bytes(signed_value)
+        if signed_value is None:
+            raise BadSignature("no value")
+        return want_bytes(signed_value)
diff --git a/README.md b/README.md
new file mode 100644
--- /dev/null
+++ b/README.md
@@ -0,0 +1,2 @@
+# Title
+text
"""


def test_parse_unified_diff_paths_and_ranges():
    files = parse_unified_diff(DIFF)
    paths = {f.path for f in files}
    assert "src/itsdangerous/signer.py" in paths
    assert "README.md" in paths
    signer = next(f for f in files if f.path.endswith("signer.py"))
    assert signer.new_ranges == [(244, 252)]
    assert signer.added == 3 and signer.removed == 1
    readme = next(f for f in files if f.path == "README.md")
    assert readme.is_new


def test_classify_sensitivity_over_real_names():
    hits = classify_sensitivity(["src/auth/jwt.py::verify_token", "cache/redis.py::get"])
    assert "authentication" in hits
    assert "security" in hits  # verify
    assert "caching" in hits


def test_score_risk_levels():
    # sensitive area -> HIGH regardless of blast size
    level, reasons = score_risk(1, 0, ["authentication"], False)
    assert level == "HIGH"
    # large blast radius -> HIGH
    assert score_risk(9, 8, [], False)[0] == "HIGH"
    # moderate -> MEDIUM
    assert score_risk(3, 1, [], False)[0] == "MEDIUM"
    # isolated, non-sensitive -> LOW
    level, reasons = score_risk(0, 0, [], False)
    assert level == "LOW"
    assert reasons  # always explains itself


def test_score_risk_inherit_signal():
    level, reasons = score_risk(3, 0, [], True)
    assert level == "HIGH"
    assert any("inherit" in r for r in reasons)


import pytest

from cortex.routes.impact import _PR_URL, _fetch_github_pr_diff


@pytest.mark.parametrize(
    "url,owner,repo,number",
    [
        ("https://github.com/pallets/flask/pull/5432", "pallets", "flask", "5432"),
        ("https://github.com/pallets/flask/pull/5432/files", "pallets", "flask", "5432"),
        ("github.com/a-b/c.d/pull/1", "a-b", "c.d", "1"),
    ],
)
def test_pr_url_parse(url, owner, repo, number):
    m = _PR_URL.search(url)
    assert m is not None
    assert (m["owner"], m["repo"], m["number"]) == (owner, repo, number)


@pytest.mark.parametrize(
    "url",
    ["not a url", "https://github.com/owner/repo", "https://gitlab.com/o/r/pull/1"],
)
def test_fetch_github_pr_diff_rejects_non_pr_url(url):
    with pytest.raises(ValueError):
        _fetch_github_pr_diff(url)
