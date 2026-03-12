"""CLI: livedoc check [project path]."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from livedoc.config import load_config
from livedoc.core.graph import DocGraph
from livedoc.core.signatures import CodeSignatures
from livedoc.parsers.doc_parser import parse_doc_anchors
from livedoc.parsers.python_parser import (
    build_current_signatures,
    parse_python_module,
)
from livedoc.parsers.typescript_parser import parse_typescript_module
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


def run_check(
    project_root: Path,
    docs_dir: str,
    update_signatures: bool,
    ignore_patterns: tuple[str, ...] = (),
    output_format: str = "text",
) -> int:
    """
    Build code↔doc graph, compare signatures, output outdated fragments.
    Returns 1 if outdated, 0 if up to date.
    """
    root = project_root.resolve()
    code_path = root
    docs_path = root / docs_dir
    if not docs_path.exists():
        print(f"Documentation folder not found: {docs_path}", file=sys.stderr)
        return 2

    # Parse code (Python + TypeScript/JavaScript)
    from livedoc.parsers.python_parser import DEFAULT_IGNORE

    ignore = list(DEFAULT_IGNORE)
    ignore.extend(_load_livedocignore(root))
    if ignore_patterns:
        ignore.extend(ignore_patterns)
    ignore_tuple = tuple(ignore)
    entities = parse_python_module(root, code_path, ignore_patterns=ignore_tuple)
    entities.extend(parse_typescript_module(root, code_path, ignore_tuple))
    current_sigs = build_current_signatures(entities)
    entities_by_id = {e.code_id: e for e in entities}
    current_readable = {e.code_id: e.format_signature() for e in entities}

    # Parse docs
    fragments = parse_doc_anchors(docs_path)
    graph = DocGraph()
    for f in fragments:
        for code_id in f.code_ids:
            graph.add_link(code_id, f)

    # Load stored signatures
    sig_path = root / SIGNATURES_FILE
    stored = CodeSignatures.load(sig_path)

    if stored is None:
        # First run: save current state
        cs = CodeSignatures(current_sigs, readable=current_readable)
        cs.save(sig_path, readable=current_readable)
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
        print("Code signatures updated.")

    report = report_outdated(outdated, changes=changes, output_format=output_format)
    print(report)

    if outdated:
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
    args = parser.parse_args()
    root = Path(args.path).resolve()
    config = load_config(root)
    docs = getattr(args, "docs", None) or config.get("docs", DEFAULT_DOCS_DIR)
    output_format = getattr(args, "format", None) or config.get("format", "text")
    ignore_cli = tuple(args.ignore) if args.ignore else ()
    ignore_config = tuple(config.get("ignore", []))
    ignore = ignore_config + ignore_cli
    return run_check(args.path, docs, args.update, ignore, output_format)


if __name__ == "__main__":
    sys.exit(main())
