"""Heading-based structural segmentation of Markdown documents.

Each heading section becomes a doc_section artifact whose qualified name
is the file path plus the heading slug path — stable across re-ingestion
as long as the heading survives.
"""

import re
from dataclasses import dataclass, field

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class ParsedSection:
    qualified_name: str  # "docs/arch.md#database/decision"
    title: str
    span_start_line: int
    span_end_line: int
    raw_text: str
    metadata: dict = field(default_factory=dict)


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "section"


def parse_markdown_file(path: str, content: str) -> list[ParsedSection]:
    lines = content.splitlines()
    sections: list[ParsedSection] = []

    # (level, slug) stack builds the hierarchical slug path
    stack: list[tuple[int, str]] = []
    current: dict | None = None

    def close_current(end_line: int) -> None:
        nonlocal current
        if current is None:
            return
        body = "\n".join(lines[current["start"] - 1 : end_line])
        if body.strip():
            sections.append(
                ParsedSection(
                    qualified_name=f"{path}#{current['slug_path']}",
                    title=current["title"],
                    span_start_line=current["start"],
                    span_end_line=end_line,
                    raw_text=body,
                    metadata={"heading_level": current["level"]},
                )
            )
        current = None

    for i, line in enumerate(lines, start=1):
        match = _HEADING_RE.match(line)
        if not match:
            continue
        close_current(i - 1)
        level = len(match.group(1))
        title = match.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, _slugify(title)))
        current = {
            "level": level,
            "title": title,
            "start": i,
            "slug_path": "/".join(s for _, s in stack),
        }

    close_current(len(lines))

    # Preamble before the first heading becomes its own section
    first_heading_line = sections[0].span_start_line if sections else len(lines) + 1
    preamble = "\n".join(lines[: first_heading_line - 1])
    if preamble.strip():
        sections.insert(
            0,
            ParsedSection(
                qualified_name=f"{path}#preamble",
                title="(preamble)",
                span_start_line=1,
                span_end_line=first_heading_line - 1,
                raw_text=preamble,
                metadata={"heading_level": 0},
            ),
        )
    return sections
