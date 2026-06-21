"""Safe project initialization for the ``livedoc init`` command."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from livedoc.config import CONFIG_FILE


@dataclass(frozen=True)
class InitResult:
    """Files and directories affected by project initialization."""

    created: tuple[str, ...]
    overwritten: tuple[str, ...]
    skipped: tuple[str, ...]
    docs_dir: str


def _validated_docs_path(root: Path, docs_dir: str) -> tuple[Path, str]:
    """Resolve a safe documentation directory located inside the project root."""
    value = docs_dir.strip()
    if not value:
        raise ValueError("documentation directory cannot be empty")

    relative = Path(value)
    if relative.is_absolute():
        raise ValueError("documentation directory must be relative to the project root")

    docs_path = (root / relative).resolve()
    if docs_path == root or not docs_path.is_relative_to(root):
        raise ValueError("documentation directory must be inside the project root")

    return docs_path, relative.as_posix()


def _starter_document(docs_dir: str) -> str:
    """Return documentation content that does not create a fake LiveDoc anchor."""
    return (
        "# Project Documentation\n\n"
        "This directory was initialized by LiveDoc.\n\n"
        "## Next steps\n\n"
        "1. Discover reusable code IDs with `livedoc symbols .`.\n"
        "2. Add the selected `code_id` to the relevant documentation.\n"
        f"3. Check documentation freshness with `livedoc . --docs {docs_dir}`.\n\n"
        "See the LiveDoc project README for the anchor syntax.\n"
    )


def initialize_project(
    project_root: Path,
    docs_dir: str = "docs",
    force: bool = False,
) -> InitResult:
    """Create a LiveDoc config and starter documentation without unsafe overwrites."""
    root = project_root.resolve()
    docs_path, normalized_docs_dir = _validated_docs_path(root, docs_dir)
    config_path = root / CONFIG_FILE
    readme_path = docs_path / "README.md"

    created: list[str] = []
    overwritten: list[str] = []
    skipped: list[str] = []

    if not docs_path.exists():
        docs_path.mkdir(parents=True)
        created.append(f"{normalized_docs_dir}/")
    elif not docs_path.is_dir():
        raise ValueError(f"documentation path is not a directory: {docs_path}")

    config_content = json.dumps(
        {
            "docs": normalized_docs_dir,
            "ignore": [],
            "ignore_code_ids": [],
            "format": "text",
        },
        indent=2,
        ensure_ascii=False,
    ) + "\n"

    files = (
        (config_path, CONFIG_FILE, config_content),
        (readme_path, f"{normalized_docs_dir}/README.md", _starter_document(normalized_docs_dir)),
    )
    for path, display_name, content in files:
        if path.exists() and not force:
            skipped.append(display_name)
            continue
        existed = path.exists()
        path.write_text(content, encoding="utf-8")
        if existed:
            overwritten.append(display_name)
        else:
            created.append(display_name)

    return InitResult(
        created=tuple(created),
        overwritten=tuple(overwritten),
        skipped=tuple(skipped),
        docs_dir=normalized_docs_dir,
    )
