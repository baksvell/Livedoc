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


def _split_go_top_level_commas(text: str) -> list[str]:
    """Split Go params by top-level commas (ignore commas in (), [], {})."""
    parts: list[str] = []
    current: list[str] = []
    paren = brace = bracket = 0
    for ch in text:
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace = max(0, brace - 1)
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket = max(0, bracket - 1)
        elif ch == "," and paren == 0 and brace == 0 and bracket == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _find_matching_paren(source: str, open_idx: int) -> int:
    """Return index of matching ')' for source[open_idx] == '('; -1 if not found."""
    depth = 0
    for i in range(open_idx, len(source)):
        ch = source[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _return_before(source: str, start: int, stop_char: str) -> str:
    end = source.find(stop_char, start)
    if end == -1:
        return ""
    return source[start:end].strip()


def _extract_go_params(params_str: str) -> list[str]:
    """Extract param names from Go params: 'a, b int' or 'ctx context.Context'."""
    args: list[str] = []
    # Split by comma at top level (Go allows "a, b int" - names share type)
    parts = _split_go_top_level_commas(params_str.strip())
    pending_names: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("..."):
            # Unnamed variadic parameter: type-only, skip.
            continue
        tokens = part.split()
        if len(tokens) >= 2:
            name = tokens[0]
            if re.fullmatch(r"[A-Za-z_]\w*", name) and name != "_":
                args.extend(pending_names)
                pending_names = []
                args.append(name)
            else:
                pending_names = []
            continue
        token = tokens[0]
        if re.fullmatch(r"[A-Za-z_]\w*", token) and token != "_":
            # Could be "a" from "a, b int" or unnamed basic type.
            # Keep temporarily; flush only when a typed segment appears.
            pending_names.append(token)
        else:
            pending_names = []
    return args


def parse_go_file(file_path: Path, pkg: str) -> list[CodeEntity]:
    """Parse one .go file and return entities."""
    source = file_path.read_text(encoding="utf-8")
    entities: list[CodeEntity] = []
    # Methods first (they match func (r) Name pattern)
    for m in re.finditer(r"\bfunc\s+\(([^)]+)\)\s+(\w+)\s*\(", source):
        recv = m.group(1).strip().split()
        method_name = m.group(2)
        open_idx = m.end() - 1
        close_idx = _find_matching_paren(source, open_idx)
        if close_idx == -1:
            continue
        params_str = source[open_idx + 1 : close_idx].strip()
        ret = _return_before(source, close_idx + 1, "{")
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
    # Functions (methods are excluded by requiring "func Name(" pattern)
    func_pattern = r"\bfunc\s+(\w+)\s*\("
    for m in re.finditer(func_pattern, source):
        name = m.group(1)
        open_idx = m.end() - 1
        close_idx = _find_matching_paren(source, open_idx)
        if close_idx == -1:
            continue
        params_str = source[open_idx + 1 : close_idx].strip()
        ret = _return_before(source, close_idx + 1, "{")
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
