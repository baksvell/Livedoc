"""Tests for the ``livedoc symbols`` command."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from livedoc.cli import run_symbols


FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    project_root = tmp_path / name
    shutil.copytree(FIXTURES_ROOT / name, project_root)
    return project_root


def _run_main(monkeypatch: pytest.MonkeyPatch, *args: str | Path) -> int:
    from livedoc.cli import main

    monkeypatch.setattr(sys, "argv", ["livedoc", *[str(arg) for arg in args]])
    return main()


def test_run_symbols_text_lists_sorted_symbols(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = _copy_fixture(tmp_path, "e2e_project")

    rc = run_symbols(project_root)
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    assert captured.out.splitlines() == [
        "Found 3 symbols:",
        "calc:Multiply",
        "  Signature: Multiply(a: int, b: int) -> int",
        "  Location: calc.go:3",
        "math:add",
        "  Signature: add(a: int, b: int) -> int",
        "  Location: math.py:1",
        "web.service:render",
        "  Signature: render(name: string) -> string",
        "  Location: web/service.ts:1",
    ]


def test_main_symbols_json_is_machine_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = _copy_fixture(tmp_path, "e2e_project")

    rc = _run_main(monkeypatch, "symbols", project_root, "--format", "json")
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert captured.err == ""
    assert payload == {
        "ok": True,
        "count": 3,
        "symbols": [
            {
                "code_id": "calc:Multiply",
                "signature": "Multiply(a: int, b: int) -> int",
                "file": "calc.go",
                "line": 3,
            },
            {
                "code_id": "math:add",
                "signature": "add(a: int, b: int) -> int",
                "file": "math.py",
                "line": 1,
            },
            {
                "code_id": "web.service:render",
                "signature": "render(name: string) -> string",
                "file": "web/service.ts",
                "line": 1,
            },
        ],
    }


def test_main_symbols_does_not_require_docs_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "module.py").write_text(
        "def run(value: str) -> bool:\n    return bool(value)\n",
        encoding="utf-8",
    )

    rc = _run_main(monkeypatch, "symbols", tmp_path)
    captured = capsys.readouterr()

    assert rc == 0
    assert "module:run" in captured.out
    assert "docs" not in captured.err


def test_main_symbols_uses_config_and_cli_ignores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = _copy_fixture(tmp_path, "e2e_project")
    (project_root / ".livedoc.json").write_text(
        json.dumps(
            {
                "ignore": ["web"],
                "ignore_code_ids": ["calc:*"],
            }
        ),
        encoding="utf-8",
    )

    rc = _run_main(monkeypatch, "symbols", project_root, "--ignore", "math.py")
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out == "No symbols found.\n"


def test_main_symbols_empty_project_returns_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = _run_main(monkeypatch, "symbols", tmp_path, "--format", "json")
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload == {"ok": True, "count": 0, "symbols": []}


def test_main_symbols_rejects_duplicate_code_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "service.ts").write_text(
        "export function run(): void {}\n",
        encoding="utf-8",
    )
    (tmp_path / "service.js").write_text(
        "export function run() {}\n",
        encoding="utf-8",
    )

    rc = _run_main(monkeypatch, "symbols", tmp_path, "--format", "json")
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 2
    assert payload["ok"] is False
    assert "duplicate code_id" in payload["error"]


def test_main_symbols_missing_path_is_a_clean_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing"

    rc = _run_main(monkeypatch, "symbols", missing)
    captured = capsys.readouterr()

    assert rc == 2
    assert captured.out == ""
    assert "project path not found" in captured.err
    assert "Traceback" not in captured.err
