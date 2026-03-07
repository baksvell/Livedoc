"""Report generation for outdated documentation fragments."""

from __future__ import annotations

import json

from livedoc.core.graph import DocFragment


def _format_change(old_sig: str | None, new_sig: str | None) -> str:
    """Format signature diff for report."""
    if old_sig is None and new_sig:
        return f"Added: {new_sig}"
    if old_sig and new_sig is None:
        return f"Removed: {old_sig}"
    if old_sig and new_sig:
        return f"{old_sig}  ->  {new_sig}"
    return "Signature changed"


def report_outdated(
    outdated: list[DocFragment],
    *,
    changes: dict[str, tuple[str | None, str | None]] | None = None,
    verbose: bool = True,
    output_format: str = "text",
) -> str:
    """
    Build report: which doc fragments are outdated and what changed.
    changes: code_id -> (old_sig, new_sig)
    output_format: "text" or "json"
    """
    changes = changes or {}

    if output_format == "json":
        payload = {
            "ok": len(outdated) == 0,
            "outdated": [
                {
                    "doc_fragment_id": f.doc_fragment_id,
                    "file": str(f.file_path),
                    "line": f.line_start,
                    "heading": f.heading,
                    "code_changes": [
                        {
                            "code_id": cid,
                            "old_sig": old_sig,
                            "new_sig": new_sig,
                            "diff": _format_change(old_sig, new_sig),
                        }
                        for cid in f.code_ids
                        for old_sig, new_sig in [changes.get(cid, (None, None))]
                    ],
                }
                for f in outdated
            ],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    if not outdated:
        return "Documentation is up to date: no changes detected in linked code."

    lines = [
        "Possibly outdated documentation (code changed):",
        "",
    ]
    for f in outdated:
        lines.append(f"  * {f.doc_fragment_id}")
        lines.append(f"    File: {f.file_path}, line ~{f.line_start}")
        if f.heading:
            lines.append(f"    Section: {f.heading}")
        for code_id in f.code_ids:
            old_sig, new_sig = changes.get(code_id, (None, None))
            diff = _format_change(old_sig, new_sig)
            lines.append(f"    [{code_id}]  {diff}")
        if verbose:
            lines.append("    Suggestion: update parameter/return value descriptions in the docs.")
        lines.append("")
    return "\n".join(lines)
