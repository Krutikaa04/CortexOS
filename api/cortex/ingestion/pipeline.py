"""Repository ingestion pipeline.

Stages: FETCH -> ENUMERATE -> PARSE -> LINK -> EMBED -> BASELINE -> FINALIZE

Idempotency: every write is keyed on (source_version_id, path/qualified_name),
so a crashed and re-claimed job re-runs stages as no-op upserts. The commit
SHA is pinned into the job payload on first run — a resumed job never
silently ingests a newer commit.
"""

import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.config import get_settings
from cortex.db import get_session_factory
from cortex.ingestion.gitfetch import fetch_repository
from cortex.ingestion.js_parser import JS_EXTENSIONS, parse_js_file
from cortex.ingestion.markdown_parser import parse_markdown_file
from cortex.ingestion.python_parser import ParsedEdge, parse_python_file
from cortex.jobs import HANDLERS, JobCancelled, checkpoint
from cortex.models_client import get_model_client
from cortex.tokens import estimate_tokens

log = logging.getLogger("cortex.ingestion")

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".next",
    "dist", "build", ".pytest_cache", ".ruff_cache", "vendor", ".idea",
}
TEXT_EXTENSIONS = {".py", ".md", ".txt", ".toml", ".cfg", ".ini", ".yaml", ".yml", ".json",
                   *JS_EXTENSIONS}
MAX_FILE_BYTES = 1_000_000
EMBED_BATCH_SIZE = 16
EMBED_MAX_CHARS = 8_000  # embedding model context guard

# Baseline RAG chunking parameters (fixed, conventional — the thing we must beat)
BASELINE_CHUNK_TOKENS = 512
BASELINE_OVERLAP_TOKENS = 64

# File extension -> language label (drives which structural parser runs).
_LANGUAGE_BY_EXT = {".py": "python", ".md": "markdown",
                    **{ext: "javascript" for ext in JS_EXTENSIONS}}


async def handle_ingest_source(job_id: uuid.UUID, payload: dict[str, Any]) -> None:
    """Job handler: payload = {"uri": ..., "ref": optional, "display_name": optional}."""
    uri = payload["uri"]
    ref = payload.get("ref")

    await checkpoint(job_id, stage="cloning")
    worktree, commit_sha = fetch_repository(uri, ref)
    factory = get_session_factory()

    async with factory() as session:
        source_id = await _upsert_source(session, uri, payload.get("display_name"))
        version_id = await _get_or_create_version(session, source_id, commit_sha)
        await session.commit()

    log.info("ingesting %s @ %s (version %s)", uri, commit_sha[:12], version_id)
    stats: dict[str, Any] = {"files": 0, "skipped": 0, "artifacts": 0, "edges": 0,
                             "embeddings": 0, "baseline_chunks": 0, "parse_fallbacks": 0}

    try:
        await checkpoint(job_id, stage="parsing")
        async with factory() as session:
            files = await _ingest_files(session, version_id, worktree, stats)
            await session.commit()

        async with factory() as session:
            unresolved_edges = await _parse_files(session, version_id, files, stats)
            await session.commit()

        await checkpoint(job_id, stage="linking")
        async with factory() as session:
            await _link_edges(session, version_id, unresolved_edges, stats)
            await session.commit()

        await _embed_artifacts(job_id, version_id, stats)
        await _build_baseline_chunks(job_id, version_id, files, stats)
        await checkpoint(job_id, stage="finalizing")
    except JobCancelled:
        # A cancelled ingestion must never surface as a READY version.
        # Writes so far are idempotent upserts, so a later re-ingest of the
        # same commit resumes cleanly.
        async with factory() as session:
            await session.execute(
                text("UPDATE source_version SET status = 'failed' "
                     "WHERE id = :id AND status = 'ingesting'"),
                {"id": version_id},
            )
            await session.commit()
        raise

    async with factory() as session:
        await session.execute(
            text(
                "UPDATE source_version SET status = 'ready', stats = cast(:stats as jsonb) "
                "WHERE id = :id"
            ),
            {"id": version_id, "stats": _json(stats)},
        )
        # Supersede older ready versions of the same source
        superseded = (
            await session.execute(
                text(
                    "UPDATE source_version SET status = 'superseded' "
                    "WHERE source_id = :source_id AND id != :id AND status = 'ready' "
                    "RETURNING id"
                ),
                {"source_id": source_id, "id": version_id},
            )
        ).scalars().all()
        await session.commit()

    # SVM invalidation: resident pages built on superseded versions are stale
    from cortex.svm import manager as svm_manager

    for old_version_id in superseded:
        invalidated = await svm_manager.invalidate_superseded_version(old_version_id)
        if invalidated:
            log.info("invalidated %d SVM pages from superseded version %s",
                     invalidated, old_version_id)

    # Storage hygiene: on ephemeral/cloud disks the clone is disposable once
    # everything is persisted in Postgres. Opt-in so local dev keeps the fast
    # re-ingest path (an existing clone is fetched, not re-cloned).
    if get_settings().ingest_cleanup:
        import shutil

        shutil.rmtree(worktree, ignore_errors=True)
        log.info("cleaned up ingestion workspace %s", worktree)
    log.info("ingestion complete: %s", stats)


HANDLERS["ingest_source"] = handle_ingest_source


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------


async def _upsert_source(session: AsyncSession, uri: str, display_name: str | None) -> uuid.UUID:
    row = (
        await session.execute(text("SELECT id FROM source WHERE uri = :uri"), {"uri": uri})
    ).first()
    if row:
        return row.id
    source_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO source (id, kind, uri, display_name) "
            "VALUES (:id, 'git_repo', :uri, :name)"
        ),
        {"id": source_id, "uri": uri, "name": display_name or uri.rstrip("/").split("/")[-1]},
    )
    return source_id


async def _get_or_create_version(
    session: AsyncSession, source_id: uuid.UUID, commit_sha: str
) -> uuid.UUID:
    row = (
        await session.execute(
            text(
                "SELECT id FROM source_version "
                "WHERE source_id = :sid AND commit_sha = :sha AND status != 'failed'"
            ),
            {"sid": source_id, "sha": commit_sha},
        )
    ).first()
    if row:
        return row.id
    version_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO source_version (id, source_id, commit_sha, status, stats) "
            "VALUES (:id, :sid, :sha, 'ingesting', '{}')"
        ),
        {"id": version_id, "sid": source_id, "sha": commit_sha},
    )
    return version_id


async def _ingest_files(
    session: AsyncSession, version_id: uuid.UUID, worktree: Path, stats: dict
) -> list[dict]:
    """ENUMERATE: walk the tree, store file rows. Returns file records."""
    files: list[dict] = []
    for path in sorted(worktree.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(worktree).as_posix()
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            stats["skipped"] += 1
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            stats["skipped"] += 1
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            stats["skipped"] += 1
            continue

        file_id = uuid.uuid4()
        sha = hashlib.sha256(content.encode()).hexdigest()
        language = _LANGUAGE_BY_EXT.get(path.suffix.lower(), "text")
        result = await session.execute(
            text(
                "INSERT INTO source_file "
                "(id, source_version_id, path, language, content_sha256, byte_size, raw_content) "
                "VALUES (:id, :vid, :path, :lang, :sha, :size, :content) "
                "ON CONFLICT (source_version_id, path) DO UPDATE SET content_sha256 = EXCLUDED.content_sha256 "
                "RETURNING id"
            ),
            {
                "id": file_id, "vid": version_id, "path": rel, "lang": language,
                "sha": sha, "size": len(content.encode()), "content": content,
            },
        )
        actual_id = result.scalar_one()
        files.append({"id": actual_id, "path": rel, "language": language, "content": content})
        stats["files"] += 1
    return files


async def _parse_files(
    session: AsyncSession, version_id: uuid.UUID, files: list[dict], stats: dict
) -> list[ParsedEdge]:
    """PARSE: create semantic artifacts; collect unresolved edges for LINK."""
    unresolved: list[ParsedEdge] = []
    for f in files:
        artifacts: list = []
        if f["language"] == "python":
            try:
                artifacts, edges = parse_python_file(f["path"], f["content"])
                unresolved.extend(edges)
            except SyntaxError:
                stats["parse_fallbacks"] += 1
                artifacts = []
        elif f["language"] == "javascript":
            try:
                artifacts, edges = parse_js_file(f["path"], f["content"])
                unresolved.extend(edges)
            except Exception:  # noqa: BLE001 — regex parser must never fail ingestion
                stats["parse_fallbacks"] += 1
                artifacts = []
        elif f["language"] == "markdown":
            sections = parse_markdown_file(f["path"], f["content"])
            for s in sections:
                await _upsert_artifact(
                    session, version_id, f["id"], "doc_section", s.qualified_name,
                    s.span_start_line, s.span_end_line, s.raw_text, [], s.metadata,
                )
                stats["artifacts"] += 1
            continue

        if not artifacts:
            # Fallback: whole file as one module-level artifact
            await _upsert_artifact(
                session, version_id, f["id"], "module", f["path"],
                1, f["content"].count("\n") + 1, f["content"], [],
                {"parse_fallback": f["language"] != "python"},
            )
            stats["artifacts"] += 1
            continue

        for a in artifacts:
            await _upsert_artifact(
                session, version_id, f["id"], a.kind, a.qualified_name,
                a.span_start_line, a.span_end_line, a.raw_text, a.facts, a.metadata,
            )
            stats["artifacts"] += 1
    return unresolved


async def _upsert_artifact(
    session: AsyncSession, version_id: uuid.UUID, file_id: uuid.UUID, kind: str,
    qualified_name: str, start: int, end: int, raw_text: str, facts: list, metadata: dict,
) -> None:
    await session.execute(
        text(
            "INSERT INTO semantic_artifact "
            "(id, source_version_id, source_file_id, kind, qualified_name, "
            " span_start_line, span_end_line, raw_text, facts, raw_token_count, "
            " reliability_score, metadata) "
            "VALUES (:id, :vid, :fid, :kind, :qn, :start, :end, :text, "
            "        cast(:facts as jsonb), :tokens, 1.0, cast(:meta as jsonb)) "
            "ON CONFLICT (source_version_id, qualified_name) DO UPDATE SET "
            "  raw_text = EXCLUDED.raw_text, facts = EXCLUDED.facts, "
            "  span_start_line = EXCLUDED.span_start_line, span_end_line = EXCLUDED.span_end_line"
        ),
        {
            "id": uuid.uuid4(), "vid": version_id, "fid": file_id, "kind": kind,
            "qn": qualified_name, "start": start, "end": end, "text": raw_text,
            "facts": _json(facts), "tokens": estimate_tokens(raw_text), "meta": _json(metadata),
        },
    )


async def _link_edges(
    session: AsyncSession, version_id: uuid.UUID, unresolved: list[ParsedEdge], stats: dict
) -> None:
    """LINK: resolve symbol names to artifact ids within this version.

    Resolution strategy (best-effort, confidence-weighted):
    - 'contains' edges reference exact qualified names -> direct lookup.
    - imports: match module dotted path to file path (a.b.c -> a/b/c.py).
    - calls/inherits: match the last symbol segment against artifact
      qualified names; ambiguous matches are skipped.
    """
    rows = (
        await session.execute(
            text("SELECT id, qualified_name FROM semantic_artifact WHERE source_version_id = :vid"),
            {"vid": version_id},
        )
    ).all()
    by_qn = {r.qualified_name: r.id for r in rows}
    # symbol name (last segment) -> [artifact ids]
    by_symbol: dict[str, list] = {}
    for r in rows:
        if "::" in r.qualified_name:
            symbol = r.qualified_name.split("::", 1)[1].split(".")[-1]
            by_symbol.setdefault(symbol, []).append(r.id)

    for edge in unresolved:
        from_id = by_qn.get(edge.from_qualified_name)
        if from_id is None:
            continue
        to_id, confidence = None, edge.confidence

        if edge.kind == "contains":
            to_id = by_qn.get(edge.to_name)
        elif edge.kind == "imports":
            # Python imports arrive dotted ('a.b.c'); JS/TS imports arrive as
            # repo-relative paths pre-resolved by the parser ('src/a/b'). Try
            # both language families' module-file conventions — a bare package
            # ('react', 'os') simply matches nothing and stays unresolved.
            candidate = edge.to_name.replace(".", "/") if "/" not in edge.to_name else edge.to_name
            suffixes = [
                f"{candidate}.py", f"{candidate}/__init__.py",
                f"{candidate}.js", f"{candidate}.jsx", f"{candidate}.mjs", f"{candidate}.cjs",
                f"{candidate}.ts", f"{candidate}.tsx",
                f"{candidate}/index.js", f"{candidate}/index.ts",
                f"{candidate}/index.jsx", f"{candidate}/index.tsx",
            ]
            for suffix in suffixes:
                for qn, aid in by_qn.items():
                    if qn == suffix or qn.endswith(f"/{suffix}"):
                        to_id = aid
                        break
                if to_id:
                    break
        else:  # calls / inherits
            symbol = edge.to_name.split(".")[-1]
            candidates = by_symbol.get(symbol, [])
            if len(candidates) == 1:
                to_id = candidates[0]
            elif len(candidates) > 1:
                confidence = 0.5
                to_id = candidates[0]

        if to_id is None or to_id == from_id:
            continue
        await session.execute(
            text(
                "INSERT INTO artifact_edge "
                "(id, source_version_id, from_artifact_id, to_artifact_id, kind, confidence, metadata) "
                "VALUES (:id, :vid, :f, :t, :kind, :conf, '{}') "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "id": uuid.uuid4(), "vid": version_id, "f": from_id, "t": to_id,
                "kind": edge.kind, "conf": confidence,
            },
        )
        stats["edges"] += 1


async def _embed_artifacts(job_id: uuid.UUID, version_id: uuid.UUID, stats: dict) -> None:
    """EMBED: batch-embed raw text of artifacts missing an embedding.

    Reports honest done/total progress and checks for cancellation between
    batches — each batch is a safe boundary (embeddings are upserts).
    """
    model_name = get_settings().embed_model
    client = get_model_client()
    factory = get_session_factory()

    async with factory() as session:
        total = (
            await session.execute(
                text(
                    "SELECT count(*) FROM semantic_artifact a "
                    "WHERE a.source_version_id = :vid AND NOT EXISTS ("
                    "  SELECT 1 FROM artifact_embedding e "
                    "  WHERE e.artifact_id = a.id AND e.representation = 'raw' "
                    "        AND e.model_name = :model)"
                ),
                {"vid": version_id, "model": model_name},
            )
        ).scalar_one()

    while True:
        await checkpoint(job_id, stage="embedding", done=stats["embeddings"], total=total)
        async with factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT a.id, a.raw_text FROM semantic_artifact a "
                        "WHERE a.source_version_id = :vid AND NOT EXISTS ("
                        "  SELECT 1 FROM artifact_embedding e "
                        "  WHERE e.artifact_id = a.id AND e.representation = 'raw' "
                        "        AND e.model_name = :model) "
                        "ORDER BY a.id LIMIT :batch"
                    ),
                    {"vid": version_id, "model": model_name, "batch": EMBED_BATCH_SIZE},
                )
            ).all()
            if not rows:
                break
            texts = [r.raw_text[:EMBED_MAX_CHARS] for r in rows]
            embeddings = await client.embed(texts)
            for row, emb in zip(rows, embeddings):
                await session.execute(
                    text(
                        "INSERT INTO artifact_embedding "
                        "(id, artifact_id, representation, model_name, embedding) "
                        "VALUES (:id, :aid, 'raw', :model, :emb) "
                        "ON CONFLICT (artifact_id, representation, model_name) DO NOTHING"
                    ),
                    {"id": uuid.uuid4(), "aid": row.id, "model": model_name, "emb": str(emb)},
                )
                stats["embeddings"] += 1
            await session.commit()
        log.info("embedded %d artifacts so far", stats["embeddings"])


async def _build_baseline_chunks(
    job_id: uuid.UUID, version_id: uuid.UUID, files: list[dict], stats: dict
) -> None:
    """BASELINE: conventional fixed-size chunking + embeddings.

    Same source snapshot, same embedding model as the semantic artifacts —
    the benchmark comparison must be fair.
    """
    client = get_model_client()
    factory = get_session_factory()
    chunk_chars = BASELINE_CHUNK_TOKENS * 4
    overlap_chars = BASELINE_OVERLAP_TOKENS * 4

    async with factory() as session:
        for done, f in enumerate(files):
            # per-file boundary is safe: chunks are keyed on (file, index)
            await checkpoint(job_id, stage="baseline_chunks", done=done, total=len(files))
            content = f["content"]
            index = 0
            pos = 0
            while pos < len(content):
                chunk_text = content[pos : pos + chunk_chars]
                if chunk_text.strip():
                    exists = (
                        await session.execute(
                            text(
                                "SELECT 1 FROM baseline_chunk "
                                "WHERE source_file_id = :fid AND chunk_index = :idx"
                            ),
                            {"fid": f["id"], "idx": index},
                        )
                    ).first()
                    if not exists:
                        emb = (await client.embed([chunk_text]))[0]
                        await session.execute(
                            text(
                                "INSERT INTO baseline_chunk "
                                "(id, source_version_id, source_file_id, chunk_index, text, "
                                " token_count, embedding) "
                                "VALUES (:id, :vid, :fid, :idx, :text, :tokens, :emb)"
                            ),
                            {
                                "id": uuid.uuid4(), "vid": version_id, "fid": f["id"],
                                "idx": index, "text": chunk_text,
                                "tokens": estimate_tokens(chunk_text), "emb": str(emb),
                            },
                        )
                        stats["baseline_chunks"] += 1
                index += 1
                pos += chunk_chars - overlap_chars
        await session.commit()


def _json(value: Any) -> str:
    import json

    return json.dumps(value)
