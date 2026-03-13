"""Tests for parsers and outdated detection."""

from pathlib import Path

import pytest

from livedoc.core.graph import DocGraph
from livedoc.core.signatures import CodeSignatures, signature_hash
from livedoc.parsers.doc_parser import parse_doc_file
from livedoc.parsers.python_parser import (
    build_current_signatures,
    parse_python_file,
    parse_python_module,
)
from livedoc.parsers.typescript_parser import (
    parse_typescript_file,
    parse_typescript_module,
)
from livedoc.parsers.go_parser import parse_go_file, parse_go_module


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


def test_report_outdated_json_format() -> None:
    from livedoc.core.graph import DocFragment
    from livedoc.report.reporter import report_outdated

    f = DocFragment("api.md#add", Path("api.md"), 5, ["m:add"], "add")
    changes = {"m:add": ("add(a)", "add(a, b)")}
    report = report_outdated([f], changes=changes, output_format="json")
    assert '"ok": false' in report
    assert "api.md#add" in report
    assert "m:add" in report


def test_report_up_to_date_json() -> None:
    from livedoc.report.reporter import report_outdated

    report = report_outdated([], output_format="json")
    assert '"ok": true' in report
    assert '"outdated": []' in report


def test_config_load() -> None:
    import tempfile
    from livedoc.config import load_config

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        config_path = root / ".livedoc.json"
        config_path.write_text(
            '{"docs": "mydocs", "ignore": ["build"], "format": "json"}',
            encoding="utf-8",
        )
        config = load_config(root)
        assert config["docs"] == "mydocs"
        assert config["ignore"] == ["build"]
        assert config["format"] == "json"


def test_config_load_empty_missing() -> None:
    from livedoc.config import load_config

    config = load_config(Path("/nonexistent"))
    assert config == {}


def test_config_load_invalid_json() -> None:
    import tempfile
    from livedoc.config import load_config

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".livedoc.json").write_text("not json {", encoding="utf-8")
        config = load_config(root)
        assert config == {}


def test_code_entity_format_signature() -> None:
    from livedoc.core.signatures import CodeEntity

    e = CodeEntity(
        code_id="m:add",
        name="add",
        args=["a", "b"],
        return_annotation="int",
        file_path=Path("x.py"),
        line=1,
    )
    assert e.format_signature() == "add(a, b) -> int"


def test_parse_doc_file_empty() -> None:
    import tempfile
    from livedoc.parsers.doc_parser import parse_doc_file

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# No anchors here\n")
        path = Path(f.name)
    try:
        fragments = parse_doc_file(path, path.parent)
        assert fragments == []
    finally:
        path.unlink()


def test_parse_typescript_file() -> None:
    utils = EXAMPLES_ROOT / "ts_sample" / "utils.ts"
    root = EXAMPLES_ROOT
    module_path = "ts_sample.utils"
    entities = parse_typescript_file(utils, module_path)
    code_ids = {e.code_id for e in entities}
    assert "ts_sample.utils:add" in code_ids
    assert "ts_sample.utils:subtract" in code_ids
    assert "ts_sample.utils:multiply" in code_ids
    assert "ts_sample.utils:Calculator.divide" in code_ids
    assert "ts_sample.utils:createCalculator" in code_ids
    assert "ts_sample.utils:Point" in code_ids
    assert "ts_sample.utils:UserId" in code_ids
    assert "ts_sample.utils:greet" in code_ids
    point = next(e for e in entities if e.code_id == "ts_sample.utils:Point")
    assert "x" in point.args and "y" in point.args
    greet_ent = next(e for e in entities if e.code_id == "ts_sample.utils:greet")
    assert "name" in greet_ent.args


def test_parse_go_file() -> None:
    calc = EXAMPLES_ROOT / "go_sample" / "calc.go"
    entities = parse_go_file(calc, "calc")
    code_ids = {e.code_id for e in entities}
    assert "calc:Add" in code_ids
    assert "calc:Subtract" in code_ids
    assert "calc:(*Calculator).Multiply" in code_ids
    assert "calc:Calculator.Divide" in code_ids
    add_ent = next(e for e in entities if e.code_id == "calc:Add")
    assert "a" in add_ent.args and "b" in add_ent.args


def test_parse_go_module() -> None:
    root = EXAMPLES_ROOT
    entities = parse_go_module(root, root, ignore_patterns=())
    code_ids = {e.code_id for e in entities}
    assert "calc:Add" in code_ids
    assert "calc:(*Calculator).Multiply" in code_ids


def test_parse_go_ignores_test_files() -> None:
    """*_test.go files should be ignored."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "calc.go").write_text(
            "package calc\n\nfunc Add(a, b int) int { return a + b }\n",
            encoding="utf-8",
        )
        (root / "calc_test.go").write_text(
            "package calc\n\nfunc TestAdd(t *testing.T) {}\n",
            encoding="utf-8",
        )
        entities = parse_go_module(root, root, ignore_patterns=())
        code_ids = {e.code_id for e in entities}
        assert "calc:Add" in code_ids
        assert "calc:TestAdd" not in code_ids


def test_parse_typescript_ignores_d_ts() -> None:
    """*.d.ts files should be ignored."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "types.d.ts").write_text(
            "export declare function foo(x: number): void;\n",
            encoding="utf-8",
        )
        (root / "impl.ts").write_text(
            "export function bar(): number { return 1; }\n",
            encoding="utf-8",
        )
        entities = parse_typescript_module(root, root, ignore_patterns=())
        code_ids = {e.code_id for e in entities}
        assert "impl:bar" in code_ids
        assert "types:foo" not in code_ids


def test_parse_typescript_module() -> None:
    root = EXAMPLES_ROOT
    entities = parse_typescript_module(root, root, ignore_patterns=())
    code_ids = {e.code_id for e in entities}
    assert "ts_sample.utils:add" in code_ids
    assert "ts_sample.utils:Calculator.divide" in code_ids


def test_parse_doc_file_malformed_anchor() -> None:
    import tempfile
    from livedoc.parsers.doc_parser import parse_doc_file

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write('<!-- livedoc: code_id = "" -->\n## Empty\n')
        path = Path(f.name)
    try:
        fragments = parse_doc_file(path, path.parent)
        assert len(fragments) == 0
    finally:
        path.unlink()
