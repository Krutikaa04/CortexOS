"""Precise TS/JS import resolution from tsconfig.json / jsconfig.json.

Next.js and TypeScript projects import through aliases (`@/components/x`,
`~/lib/y`) declared in `compilerOptions.baseUrl` + `paths`. Resolving these
correctly is what makes the JS/TS dependency graph — and therefore the Change
Impact Guard's blast radius — accurate on real apps and monorepos.

This module parses every tsconfig/jsconfig in the repo into an alias resolver
that maps an import specifier (from a given file) to candidate repo-relative
module paths. It is deterministic and dependency-free (tolerant JSON: strips
comments and trailing commas, which tsconfig allows).
"""

from __future__ import annotations

import json
import posixpath
import re
from dataclasses import dataclass

_CONFIG_NAMES = ("tsconfig.json", "jsconfig.json")
_LINE_COMMENT = re.compile(r"//[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def _lenient_json(text: str) -> dict:
    """Parse JSON with comments and trailing commas (tsconfig dialect)."""
    text = _BLOCK_COMMENT.sub("", text)
    text = _LINE_COMMENT.sub("", text)
    text = _TRAILING_COMMA.sub(r"\1", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


@dataclass
class _AliasConfig:
    dir: str  # repo-relative directory containing the config ("" = root)
    base: str  # baseUrl resolved to a repo-relative dir
    paths: dict[str, list[str]]  # e.g. {"@/*": ["./src/*"]}

    def resolve(self, spec: str) -> list[str]:
        """Candidate repo-relative module bases (no extension) for `spec`."""
        out: list[str] = []
        for pattern, targets in self.paths.items():
            if "*" in pattern:
                prefix = pattern.split("*", 1)[0]
                if spec.startswith(prefix):
                    tail = spec[len(prefix):]
                    for t in targets:
                        sub = t.replace("*", tail, 1)
                        out.append(self._join(sub))
            elif spec == pattern:
                out.extend(self._join(t) for t in targets)
        return out

    def _join(self, target: str) -> str:
        combined = posixpath.join(self.dir, self.base, target)
        return posixpath.normpath(combined).lstrip("./")


class TsAliasResolver:
    """Repo-wide alias resolver, choosing the most specific config per file."""

    def __init__(self, configs: list[_AliasConfig]) -> None:
        # longest dir first so the closest tsconfig wins for a given file
        self._configs = sorted(configs, key=lambda c: len(c.dir), reverse=True)

    @property
    def active(self) -> bool:
        return any(c.paths for c in self._configs)

    def resolve(self, from_path: str, spec: str) -> list[str]:
        """Ordered candidate module bases for `spec` imported from `from_path`.

        Empty when `spec` is not an alias any applicable config defines — the
        caller then falls back to relative/convention resolution."""
        from_dir = posixpath.dirname(from_path)
        for cfg in self._configs:
            if cfg.dir and not (from_dir == cfg.dir or from_dir.startswith(cfg.dir + "/")):
                continue
            hits = cfg.resolve(spec)
            if hits:
                return hits
        return []


def build_alias_resolver(files: list[dict]) -> TsAliasResolver:
    """Construct a resolver from ingested files (each: {path, content})."""
    configs: list[_AliasConfig] = []
    for f in files:
        name = f["path"].rsplit("/", 1)[-1]
        if name not in _CONFIG_NAMES:
            continue
        data = _lenient_json(f.get("content", ""))
        opts = data.get("compilerOptions", {}) if isinstance(data, dict) else {}
        paths = opts.get("paths") or {}
        if not isinstance(paths, dict):
            continue
        cfg_dir = posixpath.dirname(f["path"])
        base = opts.get("baseUrl") or "."
        clean_paths = {
            k: [t for t in (v if isinstance(v, list) else [v]) if isinstance(t, str)]
            for k, v in paths.items()
            if isinstance(k, str)
        }
        configs.append(_AliasConfig(dir=cfg_dir, base=base, paths=clean_paths))
    return TsAliasResolver(configs)
