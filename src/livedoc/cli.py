"""CLI: livedoc check [project path]."""

from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

from livedoc.config import load_config
from livedoc.core.graph import DocGraph, find_unknown_anchor_refs
from livedoc.core.graph import DocFragment
from livedoc.core.signatures import CodeSignatures
from livedoc.parsers.doc_parser import parse_doc_anchors
from livedoc.parsers.python_parser import (
    build_current_signatures,
    parse_python_module,
)
from livedoc.parsers.typescript_parser import parse_typescript_module
from livedoc.parsers.go_parser import parse_go_module
from livedoc.report.reporter import report_outdated


DEFAULT_DOCS_DIR = "docs"
SIGNATURES_FILE = ".livedoc/code_signatures.json"
LIVEDOCIGNORE_FILE = ".livedocignore"


def _load_livedocignore(root: Path) -> tuple[str, ...]:
    """Load patterns from .livedocignore (one per line, # comments ignored)."""
    path = root / LIVEDOCIGNORE_FILE
    if not path.exists():
        return ()
    patterns: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return tuple(patterns)


def _is_ignored_code_id(code_id: str, ignore_code_ids: tuple[str, ...]) -> bool:
    """Return True if code_id matches any configured ignore pattern."""
    return any(fnmatch.fnmatch(code_id, pattern) for pattern in ignore_code_ids)


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
            if not _is_ignored_code_id(code_id, ignore_code_ids)
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
            if not _is_ignored_code_id(code_id, ignore_code_ids)
        },
        readable={
            code_id: sig
            for code_id, sig in stored.readable.items()
            if not _is_ignored_code_id(code_id, ignore_code_ids)
        },
    )


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
    code_path = root
    docs_path = root / docs_dir
    if not docs_path.exists():
        print(f"Documentation folder not found: {docs_path}", file=sys.stderr)
        return 2

    # Parse code (Python + TypeScript/JavaScript + Go)
    from livedoc.parsers.python_parser import DEFAULT_IGNORE

    ignore = list(DEFAULT_IGNORE)
    ignore.extend(_load_livedocignore(root))
    if ignore_patterns:
        ignore.extend(ignore_patterns)
    ignore_tuple = tuple(ignore)
    entities = parse_python_module(root, code_path, ignore_patterns=ignore_tuple)
    entities.extend(parse_typescript_module(root, code_path, ignore_tuple))
    entities.extend(parse_go_module(root, code_path, ignore_tuple))
    if ignore_code_ids:
        entities = [
            entity
            for entity in entities
            if not _is_ignored_code_id(entity.code_id, ignore_code_ids)
        ]
    current_sigs = build_current_signatures(entities)
    entities_by_id = {e.code_id: e for e in entities}
    current_readable = {e.code_id: e.format_signature() for e in entities}

    # Parse docs
    fragments = _filter_doc_fragments(parse_doc_anchors(docs_path), ignore_code_ids)
    graph = DocGraph()
    for f in fragments:
        for code_id in f.code_ids:
            graph.add_link(code_id, f)

    unknown_refs = find_unknown_anchor_refs(fragments, set(current_sigs.keys()))

    # Load stored signatures
    sig_path = root / SIGNATURES_FILE
    stored = _filter_stored_signatures(CodeSignatures.load(sig_path), ignore_code_ids)

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
            new_sig = entities_by_id[code_id].format_signature()
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Living Documentation: check doc freshness")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        type=Path,
        help="Project root (default: current directory)",
    )
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
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce non-essential output (still shows errors and failures).",
    )
    args = parser.parse_args()
    root = Path(args.path).resolve()
    config = load_config(root)
    docs = getattr(args, "docs", None) or config.get("docs", DEFAULT_DOCS_DIR)
    output_format = getattr(args, "format", None) or config.get("format", "text")
    ignore_cli = tuple(args.ignore) if args.ignore else ()
    ignore_config = tuple(config.get("ignore", []))
    ignore = ignore_config + ignore_cli
    ignore_code_ids = tuple(config.get("ignore_code_ids", []))
    return run_check(args.path, docs, args.update, ignore, ignore_code_ids, output_format, args.quiet)


if __name__ == "__main__":
    sys.exit(main())
