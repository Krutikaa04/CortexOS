from cortex.ingestion.ts_config import build_alias_resolver


def _resolver(path, content):
    return build_alias_resolver([{"path": path, "content": content}])


TSCONFIG = """{
  // Next.js
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["./*"], "~lib/*": ["./lib/*"], "config": ["./config/index.ts"] },
  },
}"""


def test_alias_resolution_with_baseurl_and_paths():
    r = _resolver("studio/tsconfig.json", TSCONFIG)
    assert r.active
    assert r.resolve("studio/app/page.tsx", "@/components/Button") == ["studio/components/Button"]
    assert r.resolve("studio/app/page.tsx", "~lib/api") == ["studio/lib/api"]
    # exact (non-wildcard) alias
    assert r.resolve("studio/app/page.tsx", "config") == ["studio/config/index.ts"]


def test_bare_and_unknown_specifiers_return_empty():
    r = _resolver("studio/tsconfig.json", TSCONFIG)
    assert r.resolve("studio/app/page.tsx", "react") == []
    assert r.resolve("studio/app/page.tsx", "./relative") == []


def test_monorepo_config_scoped_to_its_directory():
    r = _resolver("frontend/tsconfig.json", TSCONFIG)
    # a file outside the config's directory must not use its aliases
    assert r.resolve("backend/app.ts", "@/x") == []
    assert r.resolve("frontend/src/x.ts", "@/x") == ["frontend/x"]


def test_lenient_json_tolerates_comments_and_trailing_commas():
    # the JSON above has both a comment and trailing commas; must still parse
    r = _resolver("tsconfig.json", TSCONFIG)
    assert r.active


def test_no_config_is_inactive():
    r = build_alias_resolver([{"path": "readme.md", "content": "# hi"}])
    assert not r.active
    assert r.resolve("a.ts", "@/x") == []
