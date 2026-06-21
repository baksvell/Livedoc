"""Shared source-code discovery for LiveDoc commands."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from livedoc.core.signatures import CodeEntity
from livedoc.parsers.go_parser import parse_go_module
from livedoc.parsers.python_parser import DEFAULT_IGNORE, parse_python_module
from livedoc.parsers.typescript_parser import parse_typescript_module


LIVEDOCIGNORE_FILE = ".livedocignore"


def load_livedocignore(root: Path) -> tuple[str, ...]:
    """Load path ignore patterns from ``.livedocignore``."""
    path = root / LIVEDOCIGNORE_FILE
    if not path.exists():
        return ()

    patterns: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            patterns.append(value)
    return tuple(patterns)


def is_ignored_code_id(code_id: str, ignore_code_ids: tuple[str, ...]) -> bool:
    """Return whether a code ID matches a configured glob pattern."""
    return any(fnmatch.fnmatch(code_id, pattern) for pattern in ignore_code_ids)


def discover_code_entities(
    project_root: Path,
    ignore_patterns: tuple[str, ...] = (),
) -> list[CodeEntity]:
    """Discover Python, TypeScript/JavaScript, and Go entities under a project root."""
    root = project_root.resolve()
    ignore = [*DEFAULT_IGNORE, *load_livedocignore(root), *ignore_patterns]
    combined_ignore = tuple(ignore)

    entities = parse_python_module(root, root, ignore_patterns=combined_ignore)
    entities.extend(parse_typescript_module(root, root, combined_ignore))
    entities.extend(parse_go_module(root, root, combined_ignore))
    return entities


def filter_code_entities(
    entities: list[CodeEntity],
    ignore_code_ids: tuple[str, ...],
) -> list[CodeEntity]:
    """Remove entities whose code IDs match configured ignore patterns."""
    if not ignore_code_ids:
        return entities
    return [
        entity
        for entity in entities
        if not is_ignored_code_id(entity.code_id, ignore_code_ids)
    ]


def find_duplicate_code_ids(
    entities: list[CodeEntity],
) -> dict[str, list[CodeEntity]]:
    """Return code IDs that resolve to more than one discovered entity."""
    grouped: dict[str, list[CodeEntity]] = {}
    for entity in entities:
        grouped.setdefault(entity.code_id, []).append(entity)
    return {code_id: matches for code_id, matches in grouped.items() if len(matches) > 1}


def format_duplicate_code_ids(
    duplicates: dict[str, list[CodeEntity]],
    project_root: Path,
) -> str:
    """Format duplicate code IDs with source locations for a user-facing error."""
    root = project_root.resolve()
    details: list[str] = []
    for code_id in sorted(duplicates):
        locations: list[str] = []
        for entity in duplicates[code_id]:
            try:
                path = entity.file_path.resolve().relative_to(root)
            except ValueError:
                path = entity.file_path
            locations.append(f"{path.as_posix()}:{entity.line}")
        details.append(f"{code_id} ({', '.join(locations)})")
    return "duplicate code_id values detected: " + "; ".join(details)
