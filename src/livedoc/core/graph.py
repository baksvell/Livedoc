"""Link graph: code_id <-> doc_fragment_id. Find outdated fragments by changed code_id."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DocFragment:
    """Documentation fragment linked to code."""

    doc_fragment_id: str  # e.g. "docs/api.md#add"
    file_path: Path
    line_start: int
    code_ids: list[str]
    heading: str = ""


@dataclass
class DocGraph:
    """Link graph code ↔ docs. Get outdated fragments by changed code_id."""

    # code_id -> list of DocFragment
    code_to_docs: dict[str, list[DocFragment]] = field(default_factory=dict)
    fragments: list[DocFragment] = field(default_factory=list)

    def add_link(self, code_id: str, fragment: DocFragment) -> None:
        """Add link code_id -> doc fragment."""
        if code_id not in self.code_to_docs:
            self.code_to_docs[code_id] = []
        if fragment not in self.code_to_docs[code_id]:
            self.code_to_docs[code_id].append(fragment)
        if fragment not in self.fragments:
            self.fragments.append(fragment)

    def get_outdated_fragments(self, changed_code_ids: set[str]) -> list[DocFragment]:
        """Return all doc fragments linked to changed code_id (outdated)."""
        outdated: list[DocFragment] = []
        seen: set[str] = set()
        for code_id in changed_code_ids:
            for fragment in self.code_to_docs.get(code_id, []):
                if fragment.doc_fragment_id not in seen:
                    seen.add(fragment.doc_fragment_id)
                    outdated.append(fragment)
        return outdated


def find_unknown_anchor_refs(
    fragments: list[DocFragment],
    known_code_ids: set[str],
) -> list[tuple[str, DocFragment]]:
    """
    Return (code_id, fragment) for each anchor that references code_id
    not present in known_code_ids (parsed code entities).
    """
    result: list[tuple[str, DocFragment]] = []
    for fragment in fragments:
        for code_id in fragment.code_ids:
            if code_id not in known_code_ids:
                result.append((code_id, fragment))
    return result
