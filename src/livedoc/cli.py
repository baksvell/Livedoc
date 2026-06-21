"""Command-line interface for LiveDoc."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from livedoc import __version__
from livedoc.config import load_config
from livedoc.core.discovery import (
    discover_code_entities,
    filter_code_entities,
    find_duplicate_code_ids,
    format_duplicate_code_ids,
    is_ignored_code_id,
)
from livedoc.core.graph import DocFragment, DocGraph, find_unknown_anchor_refs
from livedoc.core.signatures import CodeSignatures
from livedoc.parsers.doc_parser import parse_doc_anchors
from livedoc.parsers.python_parser import build_current_signatures
from livedoc.report.reporter import report_outdated


DEFAULT_DOCS_DIR = "docs"
SIGNATURES_FILE = ".livedoc/code_signatures.json"


def _emit_error(message: str, output_format: str) -> int:
    """Print a user-facing error without exposing an internal traceback."""
    if output_format == "json":
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": message,
                    "outdated": [],
                    "unknown_anchors": [],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(f"LiveDoc error: {message}", file=sys.stderr)
    return 2


def _exception_message(exc: Exception, context: str) -> str:
    """Convert parser, filesystem and JSON exceptions into concise messages."""
    if isinstance(exc, SyntaxError):
        location = exc.filename or context
        if exc.lineno is not None:
            location = f"{location}:{exc.lineno}"
        return f"cannot parse Python file {location}: {exc.msg}"
    if isinstance(exc, json.JSONDecodeError):
        return f"invalid JSON in {context} at line {exc.lineno}, column {exc.colno}"
    return f"{context}: {exc}"


def _filter_doc_fragments(
    fragments: list[DocFragment],
    ignore_code_ids: tuple[str, ...],
) -> list[DocFragment]:
    """Remove ignored code_ids from fragments and drop empty fragments."""
    if not ignore_code_ids:
        return fragments
    filtered: list[DocFragment] = []
    for fragment in fragments:
        code_ids = [
            code_id
            for code_id in fragment.code_ids
            if not is_ignored_code_id(code_id, ignore_code_ids)
        ]
        if code_ids:
            filtered.append(
                DocFragment(
                    doc_fragment_id=fragment.doc_fragment_id,
                    file_path=fragment.file_path,
                    line_start=fragment.line_start,
                    code_ids=code_ids,
                    heading=fragment.heading,
                )
            )
    return filtered


def _filter_stored_signatures(
    stored: CodeSignatures | None,
    ignore_code_ids: tuple[str, ...],
) -> CodeSignatures | None:
    """Drop ignored code_ids from stored baseline before comparing changes."""
    if stored is None or not ignore_code_ids:
        return stored
    return CodeSignatures(
        signatures={
            code_id: sig
            for code_id, sig in stored.signatures.items()
            if not is_ignored_code_id(code_id, ignore_code_ids)
        },
        readable={
            code_id: sig
            for code_id, sig in stored.readable.items()
            if not is_ignored_code_id(code_id, ignore_code_ids)
        },
    )


def _relative_source_location(entity_path: Path, project_root: Path) -> str:
    """Return a stable user-facing path relative to the project root when possible."""
    try:
        return entity_path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return entity_path.resolve().as_posix()


def run_symbols(
    project_root: Path,
    ignore_patterns: tuple[str, ...] = (),
    ignore_code_ids: tuple[str, ...] = (),
    output_format: str = "text",
) -> int:
    """Discover code entities and print reusable ``code_id`` values."""
    root = project_root.resolve()
    if not root.exists():
        return _emit_error(f"project path not found: {root}", output_format)
    if not root.is_dir():
        return _emit_error(f"project path is not a directory: {root}", output_format)

    try:
        entities = discover_code_entities(root, ignore_patterns)
    except (OSError, UnicodeError, SyntaxError) as exc:
        return _emit_error(_exception_message(exc, "source code"), output_format)

    duplicates = find_duplicate_code_ids(entities)
    if duplicates:
        return _emit_error(format_duplicate_code_ids(duplicates, root), output_format)

    entities = filter_code_entities(entities, ignore_code_ids)
    entities.sort(key=lambda entity: entity.code_id)

    symbols = [
        {
            "code_id": entity.code_id,
            "signature": entity.format_signature(detailed=True),
            "file": _relative_source_location(entity.file_path, root),
            "line": entity.line,
        }
        for entity in entities
    ]

    if output_format == "json":
        print(
            json.dumps(
                {
                    "ok": True,
                    "count": len(symbols),
                    "symbols": symbols,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if not symbols:
        print("No symbols found.")
        return 0

    print(f"Found {len(symbols)} symbol{'s' if len(symbols) != 1 else ''}:")
    for symbol in symbols:
        print(symbol["code_id"])
        print(f"  Signature: {symbol['signature']}")
        print(f"  Location: {symbol['file']}:{symbol['line']}")
    return 0

def run_check(
    project_root: Path,
    docs_dir: str,
    update_signatures: bool,
    ignore_patterns: tuple[str, ...] = (),
    ignore_code_ids: tuple[str, ...] = (),
    output_format: str = "text",
    quiet: bool = False,
) -> int:
    """
    Build code↔doc graph, compare signatures, output outdated fragments.
    Returns 1 if outdated or unknown anchors, 0 if up to date, 2 on error.
    """
    root = project_root.resolve()
    docs_path = root / docs_dir
    if not docs_path.exists():
        return _emit_error(f"documentation folder not found: {docs_path}", output_format)

    # Parse code (Python + TypeScript/JavaScript + Go)
    try:
        entities = discover_code_entities(root, ignore_patterns)
    except (OSError, UnicodeError, SyntaxError) as exc:
        return _emit_error(_exception_message(exc, "source code"), output_format)

    duplicates = find_duplicate_code_ids(entities)
    if duplicates:
        message = format_duplicate_code_ids(duplicates, root)
        return _emit_error(message, output_format)

    entities = filter_code_entities(entities, ignore_code_ids)
    current_sigs = build_current_signatures(entities)
    entities_by_id = {e.code_id: e for e in entities}
    current_readable = {e.code_id: e.format_signature(detailed=True) for e in entities}

    # Parse docs
    try:
        fragments = _filter_doc_fragments(parse_doc_anchors(docs_path), ignore_code_ids)
    except (OSError, UnicodeError) as exc:
        return _emit_error(_exception_message(exc, "documentation"), output_format)
    graph = DocGraph()
    for f in fragments:
        for code_id in f.code_ids:
            graph.add_link(code_id, f)

    unknown_refs = find_unknown_anchor_refs(fragments, set(current_sigs.keys()))

    # Load stored signatures
    sig_path = root / SIGNATURES_FILE
    try:
        stored = _filter_stored_signatures(CodeSignatures.load(sig_path), ignore_code_ids)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return _emit_error(_exception_message(exc, str(sig_path)), output_format)

    if stored is None:
        # First run: save current state
        cs = CodeSignatures(current_sigs, readable=current_readable)
        cs.save(sig_path, readable=current_readable)
        if output_format == "json" or unknown_refs:
            report = report_outdated(
                [],
                changes={},
                unknown_refs=unknown_refs,
                entities_by_id=entities_by_id,
                project_root=root,
                output_format=output_format,
            )
            print(report)
            return 1 if unknown_refs else 0
        if not quiet:
            print("First run: code signatures saved. Future code changes will mark linked docs as outdated.")
        return 0

    changed = stored.changed_code_ids(current_sigs)
    outdated = graph.get_outdated_fragments(changed)

    # Change details: code_id -> (old_sig, new_sig)
    changes: dict[str, tuple[str | None, str | None]] = {}
    for code_id in changed:
        old_sig = stored.get_readable(code_id)
        if code_id in entities_by_id:
            new_sig = entities_by_id[code_id].format_signature(detailed=True)
        else:
            new_sig = None  # entity removed
        changes[code_id] = (old_sig, new_sig)

    if update_signatures:
        cs = CodeSignatures(current_sigs, readable=current_readable)
        cs.save(sig_path, readable=current_readable)
        if not quiet:
            print("Code signatures updated.")

    report = report_outdated(
        outdated,
        changes=changes,
        unknown_refs=unknown_refs,
        entities_by_id=entities_by_id,
        project_root=root,
        output_format=output_format,
    )
    should_print_report = output_format == "json" or bool(outdated or unknown_refs) or not quiet
    if should_print_report:
        print(report)

    if outdated or unknown_refs:
        return 1
    return 0


def _add_common_discovery_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments shared by commands that scan source files."""
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        type=Path,
        help="Project root (default: current directory)",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Path segment or glob to ignore (e.g. tests, venv). Can be repeated.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default=argparse.SUPPRESS,
        help="Output format: text or json (default: from config or text)",
    )


def _resolve_discovery_options(
    args: argparse.Namespace,
) -> tuple[Path, tuple[str, ...], tuple[str, ...], str]:
    """Load config and merge it with CLI discovery options."""
    root = Path(args.path).resolve()
    config = load_config(root)
    output_format = getattr(args, "format", None) or config.get("format", "text")
    ignore_cli = tuple(args.ignore) if args.ignore else ()
    ignore_config = tuple(config.get("ignore", []))
    ignore = ignore_config + ignore_cli
    ignore_code_ids = tuple(config.get("ignore_code_ids", []))
    return root, ignore, ignore_code_ids, output_format


def _build_symbols_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="livedoc symbols",
        description="List discovered code symbols and their reusable code_id values",
    )
    _add_common_discovery_arguments(parser)
    return parser


def _run_symbols_command(argv: list[str]) -> int:
    args = _build_symbols_parser().parse_args(argv)
    root, ignore, ignore_code_ids, output_format = _resolve_discovery_options(args)
    return run_symbols(root, ignore, ignore_code_ids, output_format)


def _build_check_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="livedoc",
        description="Living Documentation: check doc freshness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "commands:\n"
            "  symbols [path]  List discovered symbols and reusable code_id values\n"
            "\n"
            "examples:\n"
            "  livedoc . --docs docs\n"
            "  livedoc symbols .\n"
            "  livedoc symbols . --format json"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    _add_common_discovery_arguments(parser)
    parser.add_argument(
        "--docs",
        default=argparse.SUPPRESS,
        help=f"Documentation folder (default: from config or {DEFAULT_DOCS_DIR})",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="After check, update stored signatures (mark docs as up to date)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce non-essential output (still shows errors and failures).",
    )
    return parser


def _run_check_command(argv: list[str]) -> int:
    args = _build_check_parser().parse_args(argv)
    root, ignore, ignore_code_ids, output_format = _resolve_discovery_options(args)
    config = load_config(root)
    docs = getattr(args, "docs", None) or config.get("docs", DEFAULT_DOCS_DIR)
    return run_check(root, docs, args.update, ignore, ignore_code_ids, output_format, args.quiet)


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "symbols":
        return _run_symbols_command(argv[1:])
    return _run_check_command(argv)


if __name__ == "__main__":
    sys.exit(main())
