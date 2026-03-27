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


def test_run_check_quiet_no_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from livedoc.cli import run_check

    (tmp_path / "mod.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "api.md").write_text(
        '<!-- livedoc: code_id = "mod:add" -->\n## add\nAdd docs.\n',
        encoding="utf-8",
    )

    rc_first = run_check(tmp_path, "docs", update_signatures=False, quiet=True)
    out_first = capsys.readouterr()
    assert rc_first == 0
    assert out_first.out == ""

    rc_second = run_check(tmp_path, "docs", update_signatures=False, quiet=True)
    out_second = capsys.readouterr()
    assert rc_second == 0
    assert out_second.out == ""


def test_run_check_quiet_still_prints_failures(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from livedoc.cli import run_check

    mod_file = tmp_path / "mod.py"
    mod_file.write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "api.md").write_text(
        '<!-- livedoc: code_id = "mod:add" -->\n## add\nAdd docs.\n',
        encoding="utf-8",
    )

    assert run_check(tmp_path, "docs", update_signatures=False, quiet=True) == 0
    _ = capsys.readouterr()

    mod_file.write_text(
        "def add(a: int, b: int, c: int) -> int:\n    return a + b + c\n",
        encoding="utf-8",
    )
    rc = run_check(tmp_path, "docs", update_signatures=False, quiet=True)
    out = capsys.readouterr()
    assert rc == 1
    assert "Possibly outdated documentation" in out.out
    assert "mod:add" in out.out


def test_report_outdated_with_changes() -> None:
    import tempfile
    from livedoc.core.graph import DocFragment
    from livedoc.core.signatures import CodeEntity
    from livedoc.report.reporter import report_outdated

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        code_file = root / "calc.py"
        code_file.write_text("def add(): pass\n", encoding="utf-8")
        f = DocFragment("api.md#add", Path("api.md"), 5, ["m:add"], "add")
        changes = {"m:add": ("add(a, b) -> int", "add(a, b, c) -> int")}
        entities = {
            "m:add": CodeEntity(
                code_id="m:add",
                name="add",
                args=["a", "b", "c"],
                return_annotation="int",
                file_path=code_file,
                line=12,
            )
        }
        report = report_outdated([f], changes=changes, entities_by_id=entities, project_root=root)
    assert "add(a, b) -> int" in report
    assert "add(a, b, c) -> int" in report
    assert "m:add" in report
    assert "calc.py:12" in report
    assert "Code:" in report


def test_report_outdated_json_format() -> None:
    import tempfile
    from livedoc.core.graph import DocFragment
    from livedoc.core.signatures import CodeEntity
    from livedoc.report.reporter import report_outdated

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        cf = root / "m.py"
        cf.write_text("x", encoding="utf-8")
        f = DocFragment("api.md#add", Path("api.md"), 5, ["m:add"], "add")
        changes = {"m:add": ("add(a)", "add(a, b)")}
        entities = {
            "m:add": CodeEntity(
                code_id="m:add",
                name="add",
                args=["a", "b"],
                return_annotation="",
                file_path=cf,
                line=7,
            )
        }
        report = report_outdated(
            [f],
            changes=changes,
            entities_by_id=entities,
            project_root=root,
            output_format="json",
        )
    assert '"ok": false' in report
    assert "api.md#add" in report
    assert "m:add" in report
    assert '"code_file": "m.py"' in report
    assert '"code_line": 7' in report


def test_report_up_to_date_json() -> None:
    from livedoc.report.reporter import report_outdated

    report = report_outdated([], output_format="json")
    assert '"ok": true' in report
    assert '"outdated": []' in report
    assert '"unknown_anchors": []' in report


def test_find_unknown_anchor_refs() -> None:
    from livedoc.core.graph import DocFragment, find_unknown_anchor_refs

    f = DocFragment("api.md#x", Path("api.md"), 1, ["known:id", "missing:func"], "x")
    refs = find_unknown_anchor_refs([f], {"known:id"})
    assert len(refs) == 1
    assert refs[0][0] == "missing:func"
    assert refs[0][1] == f


def test_report_unknown_anchors_text() -> None:
    from livedoc.core.graph import DocFragment
    from livedoc.report.reporter import report_outdated

    f = DocFragment("api.md#bad", Path("api.md"), 3, ["nope:missing"], "Bad")
    report = report_outdated([], unknown_refs=[("nope:missing", f)])
    assert "Unknown code_id" in report
    assert "nope:missing" in report
    assert "api.md" in report


def test_report_outdated_removed_symbol_shows_hint() -> None:
    from livedoc.core.graph import DocFragment
    from livedoc.report.reporter import report_outdated

    f = DocFragment("api.md#gone", Path("api.md"), 1, ["m:gone"], "gone")
    changes = {"m:gone": ("gone() -> void", None)}
    report = report_outdated([f], changes=changes, entities_by_id={})
    assert "removed from codebase" in report


def test_report_unknown_anchors_json() -> None:
    from livedoc.core.graph import DocFragment
    from livedoc.report.reporter import report_outdated

    f = DocFragment("api.md#bad", Path("api.md"), 3, ["x"], "Bad")
    report = report_outdated([], unknown_refs=[("ghost:fn", f)], output_format="json")
    assert '"ok": false' in report
    assert "ghost:fn" in report
    assert "unknown_anchors" in report


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


def test_parse_go_edge_no_return_and_variadic() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "edge.go"
        src.write_text(
            (
                "package edge\n\n"
                "func Log(msg string, tags ...string) {\n"
                "}\n\n"
                "type Logger struct{}\n\n"
                "func (l *Logger) Close() {\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        entities = parse_go_module(root, root, ignore_patterns=())
        by_id = {e.code_id: e for e in entities}
        assert "edge:Log" in by_id
        assert by_id["edge:Log"].args == ["msg", "tags"]
        assert by_id["edge:Log"].return_annotation == ""
        assert "edge:(*Logger).Close" in by_id
        assert by_id["edge:(*Logger).Close"].return_annotation == ""


def test_parse_go_edge_callback_and_multireturn() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "advanced.go"
        src.write_text(
            (
                "package advanced\n\n"
                "func Transform(items []int, mapper func(a int, b int) int) ([]int, error) {\n"
                "    return nil, nil\n"
                "}\n\n"
                "type Service struct{}\n\n"
                "func (s Service) Merge(in map[string][]int) (map[string]int, error) {\n"
                "    return nil, nil\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        entities = parse_go_module(root, root, ignore_patterns=())
        by_id = {e.code_id: e for e in entities}
        assert "advanced:Transform" in by_id
        assert by_id["advanced:Transform"].args == ["items", "mapper"]
        assert by_id["advanced:Transform"].return_annotation == "([]int, error)"
        assert "advanced:Service.Merge" in by_id
        assert by_id["advanced:Service.Merge"].args == ["in"]
        assert by_id["advanced:Service.Merge"].return_annotation == "(map[string]int, error)"


def test_parse_go_edge_grouped_names_channels_and_unnamed_types() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "channels.go"
        src.write_text(
            (
                "package channels\n\n"
                "func Sum(a, b, c int) int { return a + b + c }\n\n"
                "func Pipe(in <-chan int, out chan<- int, mapper func(a int, b int) int) {\n"
                "}\n\n"
                "func Consume(int, string) {\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        entities = parse_go_module(root, root, ignore_patterns=())
        by_id = {e.code_id: e for e in entities}
        assert "channels:Sum" in by_id
        assert by_id["channels:Sum"].args == ["a", "b", "c"]
        assert "channels:Pipe" in by_id
        assert by_id["channels:Pipe"].args == ["in", "out", "mapper"]
        assert "channels:Consume" in by_id
        assert by_id["channels:Consume"].args == []


def test_parse_go_edge_blank_identifier_and_context_arg() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "ctx.go"
        src.write_text(
            (
                "package ctxpkg\n\n"
                "import \"context\"\n\n"
                "func Handle(ctx context.Context, _ string, value int) error {\n"
                "    return nil\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        entities = parse_go_module(root, root, ignore_patterns=())
        by_id = {e.code_id: e for e in entities}
        assert "ctxpkg:Handle" in by_id
        assert by_id["ctxpkg:Handle"].args == ["ctx", "value"]
        assert by_id["ctxpkg:Handle"].return_annotation == "error"


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


def test_parse_typescript_edge_params() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "edge.ts"
        src.write_text(
            (
                "export function withDefaults(a: number = 1, opts = { x: 1, y: 2 }): void {}\n"
                "export const withArrow = ({ name, age }: { name: string; age: number }, tags: string[] = [\"a\", \"b\"]) => tags.length\n"
            ),
            encoding="utf-8",
        )
        entities = parse_typescript_module(root, root, ignore_patterns=())
        by_id = {e.code_id: e for e in entities}
        assert "edge:withDefaults" in by_id
        assert "edge:withArrow" in by_id
        assert by_id["edge:withDefaults"].args == ["a", "opts"]
        assert by_id["edge:withArrow"].args == ["name", "tags"]


def test_parse_typescript_edge_generics_and_callback_types() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "generic.ts"
        src.write_text(
            (
                "export function identity<T>(value: T): T { return value; }\n"
                "export function withCallback(cb: (x: number, y: number) => void): void { cb(1, 2); }\n"
                "export const reduceValues = (mapper: (x: number, y: number) => number, initial = 0): number => initial\n"
            ),
            encoding="utf-8",
        )
        entities = parse_typescript_module(root, root, ignore_patterns=())
        by_id = {e.code_id: e for e in entities}
        assert "generic:identity" in by_id
        assert "generic:withCallback" in by_id
        assert "generic:reduceValues" in by_id
        assert by_id["generic:identity"].args == ["value"]
        assert by_id["generic:withCallback"].args == ["cb"]
        assert by_id["generic:reduceValues"].args == ["mapper", "initial"]
        assert by_id["generic:reduceValues"].return_annotation == "number"


def test_parse_typescript_edge_multiline_and_class_callback_method() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "multi.ts"
        src.write_text(
            (
                "export default async function fetchMapped<T>(\n"
                "  opts: { url: string; headers?: Record<string, string> } = { url: \"/\" },\n"
                "  mapper: (x: T, y: number) => Promise<T>,\n"
                "): Promise<T> {\n"
                "  return mapper({} as T, 1)\n"
                "}\n\n"
                "export class Service {\n"
                "  run(\n"
                "    handler: (a: number, b: number) => number,\n"
                "    values: Array<number>,\n"
                "  ): number {\n"
                "    return handler(values[0], values[1])\n"
                "  }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        entities = parse_typescript_module(root, root, ignore_patterns=())
        by_id = {e.code_id: e for e in entities}
        assert "multi:fetchMapped" in by_id
        assert by_id["multi:fetchMapped"].args == ["opts", "mapper"]
        assert "Promise<T>" in by_id["multi:fetchMapped"].return_annotation
        assert "multi:Service.run" in by_id
        assert by_id["multi:Service.run"].args == ["handler", "values"]


def test_parse_typescript_edge_interface_extends_and_overload_impl() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "contracts.ts"
        src.write_text(
            (
                "interface A { a: string }\n"
                "interface B { b: number }\n"
                "export interface Combined extends A, B {\n"
                "  id: string\n"
                "}\n\n"
                "export class Formatter {\n"
                "  format(x: string): string;\n"
                "  format(x: number): string;\n"
                "  format(x: string | number): string {\n"
                "    return String(x)\n"
                "  }\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        entities = parse_typescript_module(root, root, ignore_patterns=())
        by_id = {e.code_id: e for e in entities}
        assert "contracts:Combined" in by_id
        assert "id" in by_id["contracts:Combined"].args
        assert "contracts:Formatter.format" in by_id
        assert by_id["contracts:Formatter.format"].args == ["x"]


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
