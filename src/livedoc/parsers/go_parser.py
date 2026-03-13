"""Go parser: extract functions, methods and build code_id."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from livedoc.core.signatures import CodeEntity

GO_EXTENSIONS = (".go",)
GO_IGNORE = ("vendor", ".git", "*_test.go")


def _extract_package(source: str) -> str:
    """Extract package name from 'package name' declaration."""
    m = re.search(r"^package\s+(\w+)", source, re.MULTILINE)
    return m.group(1) if m else "main"


def _extract_go_params(params_str: str) -> list[str]:
    """Extract param names from Go params: 'a, b int' or 'ctx context.Context'."""
    args: list[str] = []
    # Split by comma at top level (Go allows "a, b int" - names share type)
    parts = re.split(r"\s*,\s*", params_str.strip())
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # "a int" or "a, b int" - last token is type, rest are names
        tokens = part.split()
        if len(tokens) >= 2:
            # Last is type, rest are param names
            for t in tokens[:-1]:
                if t and not t.startswith("..."):
                    args.append(t)
        elif len(tokens) == 1 and not tokens[0].startswith("..."):
            args.append(tokens[0])
    return args


def parse_go_file(file_path: Path, pkg: str) -> list[CodeEntity]:
    """Parse one .go file and return entities."""
    source = file_path.read_text(encoding="utf-8")
    entities: list[CodeEntity] = []
    # Methods first (they match func (r) Name pattern)
    for m in re.finditer(r"\bfunc\s+\(([^)]+)\)\s+(\w+)\s*\(([^)]*)\)\s*([^{]+)", source):
        recv = m.group(1).strip().split()
        method_name = m.group(2)
        params_str = m.group(3).strip()
        ret = m.group(4).strip()
        if not recv:
            continue
        type_name = recv[-1]
        qualified = f"(*{type_name[1:]}).{method_name}" if type_name.startswith("*") else f"{type_name}.{method_name}"
        args = _extract_go_params(params_str)
        line = source[: m.start()].count("\n") + 1
        entities.append(
            CodeEntity(
                code_id=f"{pkg}:{qualified}",
                name=method_name,
                args=args,
                return_annotation=ret,
                file_path=file_path,
                line=line,
            )
        )
    # Functions (exclude those that are methods - already have "func (" before)
    func_pattern = r"(?<!\)\s)\bfunc\s+(\w+)\s*\(([^)]*)\)\s*([^{]+)"
    for m in re.finditer(func_pattern, source):
        if re.search(r"func\s+\([^)]+\)\s+\w+\s*\(", source[max(0, m.start() - 50) : m.start() + 10]):
            continue
        name = m.group(1)
        params_str = m.group(2).strip()
        ret = m.group(3).strip()
        args = _extract_go_params(params_str)
        line = source[: m.start()].count("\n") + 1
        entities.append(
            CodeEntity(
                code_id=f"{pkg}:{name}",
                name=name,
                args=args,
                return_annotation=ret,
                file_path=file_path,
                line=line,
            )
        )
    return entities


def _is_ignored(rel_path: Path, ignore_patterns: tuple[str, ...]) -> bool:
    """Return True if path matches any ignore pattern."""
    parts = rel_path.parts
    for pattern in ignore_patterns:
        for part in parts:
            if fnmatch.fnmatch(part, pattern) or part == pattern:
                return True
    if fnmatch.fnmatch(rel_path.name, "*_test.go"):
        return True
    return False


def parse_go_module(
    root: Path,
    package_path: Path,
    ignore_patterns: tuple[str, ...] = (),
) -> list[CodeEntity]:
    """Recursively parse Go files and return all entities."""
    ignore = list(GO_IGNORE) + list(ignore_patterns)
    all_entities: list[CodeEntity] = []
    for path in package_path.rglob("*.go"):
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        if _is_ignored(rel, tuple(ignore)):
            continue
        source = path.read_text(encoding="utf-8")
        pkg = _extract_package(source)
        all_entities.extend(parse_go_file(path, pkg))
    return all_entities
