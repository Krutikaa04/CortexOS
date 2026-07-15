from cortex.ingestion.js_parser import parse_js_file, resolve_import

SRC = """\
import React from "react";
import { helper, other } from "./utils/helper";
const cfg = require("../config");

// a leading comment mentioning import should not create an edge
export class UserService extends BaseService {
  constructor() {
    super();
  }
  async login(name) {
    const clean = validate(name);
    return helper(clean);
  }
}

export function validate(input) {
  return sanitize(input);
}

const format = (value) => value.trim();
"""


def _arts(src, path="src/services/user.ts"):
    a, e = parse_js_file(path, src)
    return {x.qualified_name: x for x in a}, e


def test_module_and_symbols_extracted():
    arts, _ = _arts(SRC)
    assert "src/services/user.ts" in arts  # module
    assert arts["src/services/user.ts"].kind == "module"
    assert "src/services/user.ts::UserService" in arts
    assert arts["src/services/user.ts::UserService"].kind == "class"
    assert "src/services/user.ts::UserService.login" in arts
    assert arts["src/services/user.ts::UserService.login"].kind == "method"
    assert "src/services/user.ts::validate" in arts
    assert arts["src/services/user.ts::validate"].kind == "function"
    assert "src/services/user.ts::format" in arts


def test_import_edges_resolved_relative_paths():
    _, edges = _arts(SRC)
    imports = {e.to_name for e in edges if e.kind == "imports"}
    assert "react" in imports  # bare package kept as-is
    assert "src/services/utils/helper" in imports  # ./ resolved against file dir
    assert "src/config" in imports  # ../ resolved


def test_inherits_and_contains_and_calls():
    _, edges = _arts(SRC)
    kinds = {(e.kind, e.from_qualified_name, e.to_name) for e in edges}
    assert ("inherits", "src/services/user.ts::UserService", "BaseService") in kinds
    assert ("contains", "src/services/user.ts", "src/services/user.ts::UserService") in kinds
    assert (
        "contains",
        "src/services/user.ts::UserService",
        "src/services/user.ts::UserService.login",
    ) in kinds
    calls = {e.to_name for e in edges if e.kind == "calls"}
    assert "validate" in calls and "helper" in calls  # from login()
    assert "sanitize" in calls  # from validate()
    # control-flow keywords are never call targets
    assert "if" not in calls and "return" not in calls and "super" not in calls


def test_constructor_not_emitted_as_call():
    _, edges = _arts(SRC)
    calls = {e.to_name for e in edges if e.kind == "calls"}
    assert "constructor" not in calls


def test_resolve_import():
    assert resolve_import("a/b/c.ts", "./d") == "a/b/d"
    assert resolve_import("a/b/c.ts", "../d/e") == "a/d/e"
    assert resolve_import("a/b/c.ts", "./d.js") == "a/b/d"
    assert resolve_import("a/b/c.ts", "lodash") == "lodash"


def test_never_raises_on_garbage():
    # unbalanced braces / partial syntax must still yield the module artifact
    arts, _ = _arts("class Broken extends {{{ function (", "x/y.js")
    assert "x/y.js" in arts


def test_strings_and_comments_do_not_create_symbols():
    src = 'const s = "class Fake extends Nope {"; // function ghost() {}\n'
    arts, edges = _arts(src, "z.js")
    assert "z.js::Fake" not in arts
    assert not any(e.kind == "inherits" for e in edges)
