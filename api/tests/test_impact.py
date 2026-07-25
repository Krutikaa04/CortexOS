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


# ---- v2 reasoning ---------------------------------------------------------

from cortex.kernel.impact import (
    _build_chains,
    _categorize,
    _compare_revisions,
    _confidence,
    _follow_ups,
    classify_dimension,
)


def test_classify_dimension():
    assert classify_dimension("api/routes/users.py", "users.py::list_users") == "api"
    assert classify_dimension("db/models.py", "models.py::User") == "database"
    assert classify_dimension("web/components/Card.tsx", "Card.tsx::Card") == "frontend"
    assert classify_dimension("cortex/worker.py", "worker.py::main") == "background_worker"
    assert classify_dimension("lib/stripe_client.py", "stripe_client.py::charge") == "external_service"
    assert classify_dimension("app/config.py", "config.py::Settings") == "configuration"
    assert classify_dimension("util/misc.py", "misc.py::helper") == "dependency"


def test_categorize_buckets_by_dimension():
    changed = [{"id": 1, "qualified_name": "db/models.py::User", "path": "db/models.py", "kind": "class"}]
    direct = [{"id": 2, "qualified_name": "api/routes.py::get_user", "path": "api/routes.py",
               "kind": "function", "edge_kind": "calls"}]
    dims = _categorize(changed, direct, [])
    assert "database" in dims and "api" in dims
    assert dims["api"][0]["reason"]  # every entry carries a reason


def test_inherits_edge_marks_architectural():
    direct = [{"id": 2, "qualified_name": "svc.py::Sub", "path": "svc.py", "kind": "class",
               "edge_kind": "inherits"}]
    dims = _categorize([], direct, [])
    assert "architectural" in dims


def test_build_chains_traces_to_seed():
    changed = [{"id": "seed", "qualified_name": "a.py::verify", "path": "a.py"}]
    direct = [{"id": "n1", "qualified_name": "b.py::login", "path": "b.py", "edge_kind": "calls"}]
    parents = {"n1": ("seed", "calls", 0.8)}
    chains = _build_chains(changed, direct, [], parents)
    assert chains[0]["target"] == "login"
    assert "calls" in chains[0]["chain"] and "verify" in chains[0]["chain"]


def test_confidence_explains_factors():
    conf = _confidence(
        resolved_paths={"a.py"}, code_files=[object()],
        direct=[{"id": 1}], indirect=[], parents={1: ("s", "calls", 1.0)},
        has_inherit=False, dimensions={"api": []},
    )
    assert conf["level"] in ("High", "Medium", "Low")
    signals = {f["signal"] for f in conf["factors"]}
    assert "direct dependency confirmed" in signals
    assert "call graph verified" in signals


def test_follow_ups_from_dimensions():
    ups = _follow_ups({"database": [], "api": []}, ["authentication"], has_inherit=True)
    actions = " ".join(u["action"].lower() for u in ups)
    assert "schema" in actions and "api" in actions
    assert any("subclass" in u["action"].lower() for u in ups)


def test_compare_revisions_trend_and_risk_deltas():
    prior = {"risk_level": "LOW", "confidence": 60, "problems": ["old risk"],
             "direct_impact": [{}], "indirect_impact": []}
    current = {"risk_level": "HIGH", "confidence": 80, "problems": ["new risk"],
               "direct_impact": [{}, {}], "indirect_impact": [{}]}
    cmp = _compare_revisions(prior, current)
    assert cmp["risk_trend"] == "increased"
    assert cmp["new_risks"] == ["new risk"]
    assert cmp["resolved_risks"] == ["old risk"]
    assert cmp["blast_radius_delta"] == 2
    assert cmp["confidence_delta"] == 20
