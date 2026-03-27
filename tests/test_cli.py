"""End-to-end CLI tests built on small fixture projects."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from livedoc.core.signatures import CodeSignatures


FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    project_root = tmp_path / name
    shutil.copytree(FIXTURES_ROOT / name, project_root)
    return project_root


def _run_main(monkeypatch: pytest.MonkeyPatch, *args: str | Path) -> int:
    from livedoc.cli import main

    monkeypatch.setattr(sys, "argv", ["livedoc", *[str(arg) for arg in args]])
    return main()


def test_main_e2e_first_run_then_second_run_ok(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = _copy_fixture(tmp_path, "e2e_project")

    rc_first = _run_main(monkeypatch, project_root, "--quiet")
    out_first = capsys.readouterr()
    assert rc_first == 0
    assert out_first.out == ""

    sig_path = project_root / ".livedoc" / "code_signatures.json"
    stored = CodeSignatures.load(sig_path)
    assert stored is not None
    assert "math:add" in stored.signatures
    assert "web.service:render" in stored.signatures
    assert "calc:Multiply" in stored.signatures

    rc_second = _run_main(monkeypatch, project_root, "--quiet")
    out_second = capsys.readouterr()
    assert rc_second == 0
    assert out_second.out == ""


def test_main_e2e_first_run_json_is_machine_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = _copy_fixture(tmp_path, "e2e_project")

    rc = _run_main(monkeypatch, project_root, "--format", "json")
    out = capsys.readouterr()
    assert rc == 0
    payload = json.loads(out.out)
    assert payload["ok"] is True
    assert payload["outdated"] == []
    assert payload["unknown_anchors"] == []


def test_main_e2e_detects_change_then_allows_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = _copy_fixture(tmp_path, "e2e_project")
    assert _run_main(monkeypatch, project_root, "--quiet") == 0
    _ = capsys.readouterr()

    ts_file = project_root / "web" / "service.ts"
    ts_file.write_text(
        (
            "export function render(name: string, locale: string): string {\n"
            "  return `${locale}:${name}`;\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    rc_changed = _run_main(monkeypatch, project_root, "--format", "json", "--quiet")
    out_changed = capsys.readouterr()
    assert rc_changed == 1
    payload = json.loads(out_changed.out)
    assert payload["ok"] is False
    assert payload["unknown_anchors"] == []
    assert len(payload["outdated"]) == 1
    code_change = payload["outdated"][0]["code_changes"][0]
    assert code_change["code_id"] == "web.service:render"
    assert code_change["code_file"] == "web/service.ts"
    assert code_change["new_sig"] == "render(name, locale) -> string"

    rc_update = _run_main(monkeypatch, project_root, "--update", "--quiet")
    out_update = capsys.readouterr()
    assert rc_update == 1
    assert "web.service:render" in out_update.out

    rc_after_update = _run_main(monkeypatch, project_root, "--quiet")
    out_after_update = capsys.readouterr()
    assert rc_after_update == 0
    assert out_after_update.out == ""


def test_main_e2e_reports_unknown_anchor_and_still_saves_signatures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = _copy_fixture(tmp_path, "e2e_project")
    docs_file = project_root / "docs" / "api.md"
    docs_file.write_text(
        docs_file.read_text(encoding="utf-8")
        + '\n<!-- livedoc: code_id = "missing:Symbol" -->\n## Missing\n\nBroken reference.\n',
        encoding="utf-8",
    )

    rc = _run_main(monkeypatch, project_root, "--format", "json")
    out = capsys.readouterr()
    assert rc == 1
    payload = json.loads(out.out)
    assert payload["ok"] is False
    assert payload["outdated"] == []
    assert payload["unknown_anchors"][0]["code_id"] == "missing:Symbol"

    sig_path = project_root / ".livedoc" / "code_signatures.json"
    assert sig_path.exists()
