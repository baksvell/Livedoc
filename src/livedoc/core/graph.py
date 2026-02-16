"""
Граф связей: code_id <-> doc_fragment_id.
Хранит пары и позволяет по изменённым code_id находить устаревшие фрагменты доки.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DocFragment:
    """Фрагмент документации с привязкой к коду."""

    doc_fragment_id: str  # например "docs/api.md#add"
    file_path: Path
    line_start: int
    code_ids: list[str]
    heading: str = ""


@dataclass
class DocGraph:
    """
    Граф связей код ↔ документация.
    code_id -> список doc_fragment_id; по изменённым code_id можно получить «устаревшие» фрагменты.
    """

    # code_id -> список DocFragment (фрагменты доки, описывающие этот код)
    code_to_docs: dict[str, list[DocFragment]] = field(default_factory=dict)
    # все фрагменты для итерации
    fragments: list[DocFragment] = field(default_factory=list)

    def add_link(self, code_id: str, fragment: DocFragment) -> None:
        """Добавить связь code_id -> фрагмент доки."""
        if code_id not in self.code_to_docs:
            self.code_to_docs[code_id] = []
        if fragment not in self.code_to_docs[code_id]:
            self.code_to_docs[code_id].append(fragment)
        if fragment not in self.fragments:
            self.fragments.append(fragment)

    def get_outdated_fragments(self, changed_code_ids: set[str]) -> list[DocFragment]:
        """По множеству изменённых code_id вернуть все связанные фрагменты доки (устаревшие)."""
        outdated: list[DocFragment] = []
        seen: set[str] = set()
        for code_id in changed_code_ids:
            for fragment in self.code_to_docs.get(code_id, []):
                if fragment.doc_fragment_id not in seen:
                    seen.add(fragment.doc_fragment_id)
                    outdated.append(fragment)
        return outdated
