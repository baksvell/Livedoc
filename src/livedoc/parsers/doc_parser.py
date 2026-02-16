"""
Парсер документации (Markdown): поиск анкоров livedoc и извлечение связей code_id <-> фрагмент.
"""

from __future__ import annotations

import re
from pathlib import Path

from livedoc.core.graph import DocFragment


# <!-- livedoc: code_id = "module:func" --> или code_id = "a", "b"
ANCHOR_RE = re.compile(
    r"<!--\s*livedoc:\s*code_id\s*=\s*(.+?)\s*-->",
    re.IGNORECASE | re.DOTALL,
)


def _parse_code_ids(value: str) -> list[str]:
    """Из значения атрибута code_id извлечь список идентификаторов ("a", "b" или "a")."""
    ids: list[str] = []
    for part in re.split(r",", value):
        part = part.strip().strip('"').strip("'").strip()
        if part:
            ids.append(part)
    return ids


def _heading_from_next_line(lines: list[str], start: int) -> str:
    """Найти следующий заголовок Markdown (## ...) после start."""
    for i in range(start, min(start + 3, len(lines))):
        line = lines[i]
        if line.strip().startswith("#"):
            return line.lstrip("#").strip()
    return ""


def parse_doc_file(file_path: Path, root: Path) -> list[DocFragment]:
    """
    Парсит один Markdown-файл и возвращает список фрагментов с анкорами livedoc.
    """
    fragments: list[DocFragment] = []
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel_path = file_path.relative_to(root)
    doc_id_base = str(rel_path).replace("\\", "/")

    for i, line in enumerate(lines):
        match = ANCHOR_RE.search(line)
        if not match:
            continue
        code_id_raw = match.group(1).strip()
        code_ids = _parse_code_ids(code_id_raw)
        if not code_ids:
            continue
        heading = _heading_from_next_line(lines, i + 1)
        fragment_id = f"{doc_id_base}#{heading.lower().replace(' ', '-')}" if heading else f"{doc_id_base}#L{i + 1}"
        fragment = DocFragment(
            doc_fragment_id=fragment_id,
            file_path=file_path,
            line_start=i + 1,
            code_ids=code_ids,
            heading=heading,
        )
        fragments.append(fragment)
    return fragments


def parse_doc_anchors(docs_root: Path) -> list[DocFragment]:
    """
    Рекурсивно обходит docs_root и собирает все фрагменты с анкорами livedoc.
    """
    all_fragments: list[DocFragment] = []
    for path in docs_root.rglob("*.md"):
        all_fragments.extend(parse_doc_file(path, docs_root))
    return all_fragments
