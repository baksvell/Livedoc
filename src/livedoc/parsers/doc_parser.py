"""Markdown parser: find LiveDoc anchors and link them to document fragments."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from livedoc.core.graph import DocFragment


# <!-- livedoc: code_id = "module:func" --> or code_id = "a", "b"
ANCHOR_RE = re.compile(
    r"<!--\s*livedoc:\s*code_id\s*=\s*(.+?)\s*-->",
    re.IGNORECASE | re.DOTALL,
)


def _parse_code_ids(value: str) -> list[str]:
    """Extract one or more code IDs from an anchor attribute value."""
    ids: list[str] = []
    for part in value.split(","):
        code_id = part.strip().strip('"').strip("'").strip()
        if code_id:
            ids.append(code_id)
    return ids


def _heading_from_next_line(lines: list[str], start: int) -> str:
    """Find a Markdown heading within the next three lines."""
    for index in range(start, min(start + 3, len(lines))):
        line = lines[index].strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def _slugify_heading(heading: str) -> str:
    """Create a stable, readable Markdown fragment slug."""
    slug = heading.casefold().strip()
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE)
    slug = re.sub(r"[\s-]+", "-", slug).strip("-")
    return slug


def parse_doc_file(file_path: Path, root: Path) -> list[DocFragment]:
    """Parse one Markdown file and return all fragments with LiveDoc anchors."""
    fragments: list[DocFragment] = []
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel_path = file_path.relative_to(root)
    doc_id_base = rel_path.as_posix()
    fragment_occurrences: dict[str, int] = defaultdict(int)

    for match in ANCHOR_RE.finditer(text):
        code_ids = _parse_code_ids(match.group(1).strip())
        if not code_ids:
            continue

        anchor_line = text.count("\n", 0, match.start()) + 1
        next_line_index = text.count("\n", 0, match.end()) + 1
        heading = _heading_from_next_line(lines, next_line_index)

        if heading:
            slug = _slugify_heading(heading) or f"section-{anchor_line}"
            base_fragment_id = f"{doc_id_base}#{slug}"
        else:
            base_fragment_id = f"{doc_id_base}#L{anchor_line}"

        occurrence = fragment_occurrences[base_fragment_id]
        fragment_occurrences[base_fragment_id] += 1
        fragment_id = (
            base_fragment_id if occurrence == 0 else f"{base_fragment_id}-{occurrence}"
        )

        fragments.append(
            DocFragment(
                doc_fragment_id=fragment_id,
                file_path=file_path,
                line_start=anchor_line,
                code_ids=code_ids,
                heading=heading,
            )
        )
    return fragments


def parse_doc_anchors(docs_root: Path) -> list[DocFragment]:
    """Recursively scan a documentation directory for Markdown anchors."""
    all_fragments: list[DocFragment] = []
    for path in docs_root.rglob("*.md"):
        all_fragments.extend(parse_doc_file(path, docs_root))
    return all_fragments
