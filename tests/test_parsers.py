"""Тесты парсеров и проверки устаревания."""

from pathlib import Path

import pytest

from livedoc.core.graph import DocGraph
from livedoc.core.signatures import CodeSignatures, signature_hash
from livedoc.parsers.doc_parser import parse_doc_anchors, parse_doc_file
from livedoc.parsers.python_parser import (
    build_current_signatures,
    parse_python_file,
    parse_python_module,
)


EXAMPLES_ROOT = Path(__file__).resolve().parent.parent / "examples"


def test_signature_hash_stable() -> None:
    h1 = signature_hash("add", ["a", "b"], "int")
    h2 = signature_hash("add", ["a", "b"], "int")
    assert h1 == h2


def test_signature_hash_changes_with_args() -> None:
    h1 = signature_hash("add", ["a", "b"], "int")
    h2 = signature_hash("add", ["a", "b", "c"], "int")
    assert h1 != h2


def test_parse_python_file() -> None:
    calc = EXAMPLES_ROOT / "sample_module" / "calc.py"
    root = EXAMPLES_ROOT
    module_path = "sample_module.calc"
    entities = parse_python_file(calc, module_path)
    code_ids = {e.code_id for e in entities}
    assert "sample_module.calc:add" in code_ids
    assert "sample_module.calc:subtract" in code_ids
    assert "sample_module.calc:Calculator.multiply" in code_ids
    assert "sample_module.calc:Calculator.divide" in code_ids


def test_parse_doc_file() -> None:
    api_md = EXAMPLES_ROOT / "docs" / "api.md"
    docs_root = EXAMPLES_ROOT / "docs"
    fragments = parse_doc_file(api_md, docs_root)
    assert len(fragments) >= 3
    code_ids_found = set()
    for f in fragments:
        code_ids_found.update(f.code_ids)
    assert "sample_module.calc:add" in code_ids_found
    assert "sample_module.calc:Calculator.multiply" in code_ids_found


def test_doc_graph_outdated() -> None:
    from livedoc.core.graph import DocFragment

    graph = DocGraph()
    f1 = DocFragment("api.md#add", Path("api.md"), 1, ["m:add"], "add")
    f2 = DocFragment("api.md#sub", Path("api.md"), 2, ["m:subtract"], "subtract")
    graph.add_link("m:add", f1)
    graph.add_link("m:subtract", f2)
    outdated = graph.get_outdated_fragments({"m:add"})
    assert len(outdated) == 1
    assert outdated[0].doc_fragment_id == "api.md#add"


def test_code_signatures_changed() -> None:
    stored = CodeSignatures({"m:add": "hash1", "m:sub": "hash2"})
    current = {"m:add": "hash1", "m:sub": "hash3"}
    changed = stored.changed_code_ids(current)
    assert changed == {"m:sub"}


def test_code_signatures_removed() -> None:
    stored = CodeSignatures({"m:add": "hash1"})
    current: dict[str, str] = {}
    changed = stored.changed_code_ids(current)
    assert changed == {"m:add"}


def test_parse_python_module_ignores_tests() -> None:
    """Default ignore excludes tests/ and similar paths."""
    from livedoc.parsers.python_parser import DEFAULT_IGNORE, parse_python_module

    root = EXAMPLES_ROOT
    entities = parse_python_module(root, root, ignore_patterns=DEFAULT_IGNORE)
    # examples/ has sample_module, no tests - so we get calc entities
    code_ids = {e.code_id for e in entities}
    assert "sample_module.calc:add" in code_ids
    # With custom ignore including sample_module, we'd get nothing
    empty = parse_python_module(root, root, ignore_patterns=("sample_module",))
    assert len(empty) == 0


def test_load_livedocignore() -> None:
    from livedoc.cli import _load_livedocignore

    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        ignore_file = root / ".livedocignore"
        ignore_file.write_text("build\n# comment\nscripts\n", encoding="utf-8")
        patterns = _load_livedocignore(root)
        assert "build" in patterns
        assert "scripts" in patterns
        assert "#" not in "".join(patterns)


def test_report_outdated_with_changes() -> None:
    from livedoc.core.graph import DocFragment
    from livedoc.report.reporter import report_outdated

    f = DocFragment("api.md#add", Path("api.md"), 5, ["m:add"], "add")
    changes = {"m:add": ("add(a, b) -> int", "add(a, b, c) -> int")}
    report = report_outdated([f], changes=changes)
    assert "add(a, b) -> int" in report
    assert "add(a, b, c) -> int" in report
    assert "m:add" in report
