"""Tests for the ``livedoc init`` command."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


def _run_main(monkeypatch: pytest.MonkeyPatch, *args: str | Path) -> int:
    from livedoc.cli import main

    monkeypatch.setattr(sys, "argv", ["livedoc", *[str(arg) for arg in args]])
    return main()


def test_main_init_creates_config_docs_and_starter_readme(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = _run_main(monkeypatch, "init", tmp_path)
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    config = json.loads((tmp_path / ".livedoc.json").read_text(encoding="utf-8"))
    assert config == {
        "docs": "docs",
        "ignore": [],
        "ignore_code_ids": [],
        "format": "text",
    }
    starter = (tmp_path / "docs" / "README.md").read_text(encoding="utf-8")
    assert "livedoc symbols ." in starter
    assert "livedoc . --docs docs" in starter
    assert "<!-- livedoc:" not in starter
    assert "Created:" in captured.out
    assert ".livedoc.json" in captured.out
    assert "docs/README.md" in captured.out


def test_main_init_is_idempotent_without_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _run_main(monkeypatch, "init", tmp_path) == 0
    _ = capsys.readouterr()
    config_path = tmp_path / ".livedoc.json"
    readme_path = tmp_path / "docs" / "README.md"
    config_path.write_text("custom config\n", encoding="utf-8")
    readme_path.write_text("custom docs\n", encoding="utf-8")

    rc = _run_main(monkeypatch, "init", tmp_path)
    captured = capsys.readouterr()

    assert rc == 0
    assert config_path.read_text(encoding="utf-8") == "custom config\n"
    assert readme_path.read_text(encoding="utf-8") == "custom docs\n"
    assert "Skipped existing files:" in captured.out
    assert ".livedoc.json" in captured.out
    assert "docs/README.md" in captured.out


def test_main_init_force_overwrites_generated_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / ".livedoc.json").write_text("old\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("old\n", encoding="utf-8")

    rc = _run_main(monkeypatch, "init", tmp_path, "--force")
    captured = capsys.readouterr()

    assert rc == 0
    assert json.loads((tmp_path / ".livedoc.json").read_text(encoding="utf-8"))["docs"] == "docs"
    assert (docs / "README.md").read_text(encoding="utf-8").startswith("# Project Documentation")
    assert "Overwritten:" in captured.out


def test_main_init_supports_custom_docs_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = _run_main(monkeypatch, "init", tmp_path, "--docs", "documentation/api")
    captured = capsys.readouterr()

    assert rc == 0
    config = json.loads((tmp_path / ".livedoc.json").read_text(encoding="utf-8"))
    assert config["docs"] == "documentation/api"
    assert (tmp_path / "documentation" / "api" / "README.md").exists()
    assert "livedoc . --docs documentation/api" in captured.out


def test_main_init_rejects_docs_directory_outside_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = _run_main(monkeypatch, "init", tmp_path, "--docs", "../outside")
    captured = capsys.readouterr()

    assert rc == 2
    assert captured.out == ""
    assert "documentation directory must be inside the project root" in captured.err
    assert not (tmp_path.parent / "outside").exists()


def test_main_init_missing_path_is_a_clean_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing"

    rc = _run_main(monkeypatch, "init", missing)
    captured = capsys.readouterr()

    assert rc == 2
    assert captured.out == ""
    assert "project path not found" in captured.err
    assert "Traceback" not in captured.err


def test_main_init_rejects_file_as_project_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_file = tmp_path / "project.txt"
    project_file.write_text("not a directory\n", encoding="utf-8")

    rc = _run_main(monkeypatch, "init", project_file)
    captured = capsys.readouterr()

    assert rc == 2
    assert captured.out == ""
    assert "project path is not a directory" in captured.err
