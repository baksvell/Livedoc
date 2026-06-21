"""Tests for shared source-code discovery."""

from __future__ import annotations

import shutil
from pathlib import Path

from livedoc.core.discovery import (
    discover_code_entities,
    filter_code_entities,
    find_duplicate_code_ids,
)
from livedoc.core.signatures import CodeEntity


FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    project_root = tmp_path / name
    shutil.copytree(FIXTURES_ROOT / name, project_root)
    return project_root


def test_discover_code_entities_finds_all_supported_languages(tmp_path: Path) -> None:
    project_root = _copy_fixture(tmp_path, "e2e_project")

    entities = discover_code_entities(project_root)

    assert {entity.code_id for entity in entities} == {
        "calc:Multiply",
        "math:add",
        "web.service:render",
    }


def test_discover_code_entities_respects_livedocignore(tmp_path: Path) -> None:
    project_root = _copy_fixture(tmp_path, "e2e_project")
    (project_root / ".livedocignore").write_text("web\n", encoding="utf-8")

    entities = discover_code_entities(project_root)

    assert {entity.code_id for entity in entities} == {
        "calc:Multiply",
        "math:add",
    }


def test_filter_code_entities_supports_glob_patterns(tmp_path: Path) -> None:
    project_root = _copy_fixture(tmp_path, "e2e_project")
    entities = discover_code_entities(project_root)

    filtered = filter_code_entities(entities, ("web.*", "calc:*"))

    assert [entity.code_id for entity in filtered] == ["math:add"]


def test_find_duplicate_code_ids_returns_all_conflicts(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    entities = [
        CodeEntity("pkg:add", "add", [], "", source, 1),
        CodeEntity("pkg:add", "add", [], "", source, 5),
        CodeEntity("pkg:subtract", "subtract", [], "", source, 9),
    ]

    duplicates = find_duplicate_code_ids(entities)

    assert list(duplicates) == ["pkg:add"]
    assert [entity.line for entity in duplicates["pkg:add"]] == [1, 5]
