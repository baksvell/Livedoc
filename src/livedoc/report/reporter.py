"""Report generation for outdated documentation fragments."""

from __future__ import annotations

import json
import re
from pathlib import Path

from livedoc.core.graph import DocFragment
from livedoc.core.signatures import CodeEntity


def _format_change(old_sig: str | None, new_sig: str | None) -> str:
    """Format signature diff for report."""
    if old_sig is None and new_sig:
        return f"Added: {new_sig}"
    if old_sig and new_sig is None:
        return f"Removed: {old_sig}"
    if old_sig and new_sig:
        return f"{old_sig}  ->  {new_sig}"
    return "Signature changed"


def _parse_signature(sig: str) -> tuple[str, list[str], str] | None:
    """Parse 'name(a, b) -> ret' into (name, args, ret)."""
    match = re.fullmatch(r"(.+?)\((.*)\)(?:\s*->\s*(.*))?", sig.strip())
    if not match:
        return None
    name = match.group(1).strip()
    args_raw = match.group(2).strip()
    ret = (match.group(3) or "").strip()
    args = [part.strip() for part in args_raw.split(",") if part.strip()] if args_raw else []
    return name, args, ret


def _change_reason(old_sig: str | None, new_sig: str | None) -> str:
    """Return a short human-readable reason for the detected signature change."""
    if old_sig is None and new_sig:
        return "symbol added"
    if old_sig and new_sig is None:
        return "symbol removed"
    if not old_sig or not new_sig:
        return "signature changed"

    old_parts = _parse_signature(old_sig)
    new_parts = _parse_signature(new_sig)
    if not old_parts or not new_parts:
        return "signature changed"

    _, old_args, old_ret = old_parts
    _, new_args, new_ret = new_parts
    args_changed = old_args != new_args
    ret_changed = old_ret != new_ret

    if args_changed and ret_changed:
        return "args and return type changed"
    if args_changed:
        return "args changed"
    if ret_changed:
        return "return type changed"
    return "signature changed"


def _code_location(
    code_id: str,
    entities_by_id: dict[str, CodeEntity] | None,
    project_root: Path | None,
) -> tuple[str | None, int | None]:
    """Return (relative path as str, line) for code_id, or (None, None) if unknown."""
    if not entities_by_id or code_id not in entities_by_id:
        return None, None
    ent = entities_by_id[code_id]
    path = ent.file_path
    try:
        if project_root is not None:
            path = path.resolve().relative_to(project_root.resolve())
    except ValueError:
        pass
    return str(path).replace("\\", "/"), ent.line


def _code_change_entry(
    code_id: str,
    sig_pair: tuple[str | None, str | None],
    entities_by_id: dict[str, CodeEntity] | None,
    project_root: Path | None,
) -> dict:
    old_sig, new_sig = sig_pair
    code_file, code_line = _code_location(code_id, entities_by_id, project_root)
    return {
        "code_id": code_id,
        "old_sig": old_sig,
        "new_sig": new_sig,
        "reason": _change_reason(old_sig, new_sig),
        "diff": _format_change(old_sig, new_sig),
        "code_file": code_file,
        "code_line": code_line,
    }


def _unknown_anchors_json(unknown_refs: list[tuple[str, DocFragment]]) -> list[dict]:
    return [
        {
            "code_id": code_id,
            "doc_fragment_id": frag.doc_fragment_id,
            "file": str(frag.file_path),
            "line": frag.line_start,
            "heading": frag.heading,
        }
        for code_id, frag in unknown_refs
    ]


def report_outdated(
    outdated: list[DocFragment],
    *,
    changes: dict[str, tuple[str | None, str | None]] | None = None,
    unknown_refs: list[tuple[str, DocFragment]] | None = None,
    entities_by_id: dict[str, CodeEntity] | None = None,
    project_root: Path | None = None,
    verbose: bool = True,
    output_format: str = "text",
) -> str:
    """
    Build report: which doc fragments are outdated and what changed.
    changes: code_id -> (old_sig, new_sig)
    unknown_refs: (code_id, fragment) for anchors pointing to missing code
    entities_by_id: current code entities (for code file:line in report)
    project_root: used to show paths relative to project
    output_format: "text" or "json"
    """
    changes = changes or {}
    unknown_refs = unknown_refs or []
    has_unknown = len(unknown_refs) > 0
    has_outdated = len(outdated) > 0

    if output_format == "json":
        payload = {
            "ok": not has_outdated and not has_unknown,
            "outdated": [
                {
                    "doc_fragment_id": f.doc_fragment_id,
                    "file": str(f.file_path),
                    "line": f.line_start,
                    "heading": f.heading,
                    "code_changes": [
                        _code_change_entry(
                            cid,
                            changes.get(cid, (None, None)),
                            entities_by_id,
                            project_root,
                        )
                        for cid in f.code_ids
                    ],
                }
                for f in outdated
            ],
            "unknown_anchors": _unknown_anchors_json(unknown_refs),
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    lines: list[str] = []

    if has_outdated:
        lines.extend(
            [
                "Possibly outdated documentation (code changed):",
                "",
            ]
        )
        for f in outdated:
            lines.append(f"  * {f.doc_fragment_id}")
            lines.append(f"    File: {f.file_path}, line ~{f.line_start}")
            if f.heading:
                lines.append(f"    Section: {f.heading}")
            for code_id in f.code_ids:
                old_sig, new_sig = changes.get(code_id, (None, None))
                reason = _change_reason(old_sig, new_sig)
                diff = _format_change(old_sig, new_sig)
                lines.append(f"    Reason: {reason}")
                lines.append(f"    [{code_id}]  {diff}")
                code_file, code_line = _code_location(code_id, entities_by_id, project_root)
                if code_file is not None and code_line is not None:
                    lines.append(f"    Code: {code_file}:{code_line}")
                elif new_sig is None and old_sig is not None:
                    lines.append("    Code: (symbol removed from codebase)")
            if verbose:
                lines.append("    Suggestion: update parameter/return value descriptions in the docs.")
            lines.append("")

    if has_unknown:
        lines.extend(
            [
                "Unknown code_id references (not found in parsed project code):",
                "",
            ]
        )
        for code_id, f in unknown_refs:
            lines.append(f"  * [{code_id}]")
            lines.append(f"    Doc: {f.doc_fragment_id}")
            lines.append(f"    File: {f.file_path}, line ~{f.line_start}")
            if f.heading:
                lines.append(f"    Section: {f.heading}")
            if verbose:
                lines.append(
                    "    Fix: correct the anchor or add the symbol to the codebase; "
                    "check ignore patterns if the file is excluded."
                )
            lines.append("")

    if not has_outdated and not has_unknown:
        return "Documentation is up to date: no changes detected in linked code."

    return "\n".join(lines).rstrip() + "\n"
