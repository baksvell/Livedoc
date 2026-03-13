"""TypeScript/JavaScript parser: extract functions, classes, methods and build code_id."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from livedoc.core.signatures import CodeEntity

TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx")
TS_IGNORE = ("node_modules", "dist", "build", ".git", "*.test.*", "*.spec.*", "*.d.ts")


def _path_to_module(root: Path, file_path: Path) -> str:
    """File path relative to root -> dotted module name (e.g. src.utils.calc)."""
    rel = file_path.relative_to(root)
    parts = list(rel.parts)
    if parts[-1].endswith((".ts", ".tsx", ".js", ".jsx")):
        parts[-1] = parts[-1].rsplit(".", 1)[0]
    return ".".join(parts)


def _normalize_param(param: str) -> str:
    """Extract effective param name from destructuring, rest, etc."""
    param = param.strip()
    if param.startswith("..."):
        return param
    if param.startswith("{"):
        idx = param.find("}")
        inner = (param[1:idx] if idx > 0 else param[1:]).strip()
        if ":" in inner:
            parts = re.split(r"\s*,\s*", inner)
            return parts[0].split(":")[0].strip() if parts else "?"
        return inner.split(",")[0].strip().split(":")[0].strip() if inner else "?"
    if param.startswith("["):
        inner = param[1 : param.rfind("]")].strip()
        return inner.split(",")[0].strip() if inner else "?"
    return param.split(":")[0].strip().split("=")[0].strip()


def _extract_args_from_parens(s: str) -> list[str]:
    """Extract param names from function(params) string, handling nested parens."""
    args: list[str] = []
    depth = 0
    start = -1
    for i, c in enumerate(s):
        if c == "(":
            if depth == 0:
                start = i
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0 and start >= 0:
                inner = s[start + 1 : i]
                for part in re.split(r"\s*,\s*", inner):
                    part = part.strip()
                    if not part or part.startswith("..."):
                        continue
                    # name: type or just name
                    name = part.split(":")[0].strip().split("=")[0].strip()
                    if name and name not in ("this", "context"):
                        args.append(name)
                break
    return args


def _find_functions(source: str, module_path: str, file_path: Path) -> list[CodeEntity]:
    """Find function declarations: function name(...) and const name = (...) =>."""
    entities: list[CodeEntity] = []
    # function name(...) or export function name(...) or export default function name(...)
    pattern = r"(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?"
    for m in re.finditer(pattern, source):
        name = m.group(1)
        args_str = m.group(2) or ""
        ret = (m.group(3) or "").strip() if m.group(3) else ""
        args = [_normalize_param(p) for p in re.split(r"\s*,\s*", args_str) if p.strip()]
        line = source[: m.start()].count("\n") + 1
        entities.append(
            CodeEntity(
                code_id=f"{module_path}:{name}",
                name=name,
                args=args,
                return_annotation=ret,
                file_path=file_path,
                line=line,
            )
        )
    # const name = (params) => or const name = (params): Type =>
    pattern2 = r"(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)(?:\s*:\s*[^=>]+)?\s*=>"
    for m in re.finditer(pattern2, source):
        name = m.group(1)
        args_str = m.group(2) or ""
        args = [_normalize_param(p) for p in re.split(r"\s*,\s*", args_str) if p.strip()]
        line = source[: m.start()].count("\n") + 1
        entities.append(
            CodeEntity(
                code_id=f"{module_path}:{name}",
                name=name,
                args=args,
                return_annotation="",
                file_path=file_path,
                line=line,
            )
        )
    return entities


def _find_classes_and_methods(source: str, module_path: str, file_path: Path) -> list[CodeEntity]:
    """Find class declarations and their methods."""
    entities: list[CodeEntity] = []
    # class Name { ... } or export default class Name { ... }
    class_pattern = r"(?:export\s+(?:default\s+)?)?class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{"
    for class_match in re.finditer(class_pattern, source):
        class_name = class_match.group(1)
        start = class_match.end()
        brace_depth = 1
        i = start
        while i < len(source) and brace_depth > 0:
            if source[i] == "{":
                brace_depth += 1
            elif source[i] == "}":
                brace_depth -= 1
            i += 1
        class_body = source[start:i]
        # Find methods: name(...) { or async name(...) { or get name() {
        method_pattern = r"(?:async\s+)?(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*\{"
        for m in re.finditer(method_pattern, class_body):
            name = m.group(1)
            if name in ("constructor", "get", "set"):
                continue
            args_str = m.group(2) or ""
            ret = (m.group(3) or "").strip() if m.group(3) else ""
            args = [_normalize_param(p) for p in re.split(r"\s*,\s*", args_str) if p.strip()]
            if "this" in args:
                args = [a for a in args if a != "this"]
            body_start = class_match.start() + len(class_match.group(0)) + m.start()
            line = source[:body_start].count("\n") + 1
            entities.append(
                CodeEntity(
                    code_id=f"{module_path}:{class_name}.{name}",
                    name=name,
                    args=args,
                    return_annotation=ret,
                    file_path=file_path,
                    line=line,
                )
            )
    return entities


def _find_interfaces(source: str, module_path: str, file_path: Path) -> list[CodeEntity]:
    """Find interface declarations: interface Name { ... }."""
    entities: list[CodeEntity] = []
    pattern = r"(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+[\w\s,]+)?\s*\{"
    for m in re.finditer(pattern, source):
        name = m.group(1)
        start = m.end()
        brace_depth = 1
        i = start
        while i < len(source) and brace_depth > 0:
            if source[i] == "{":
                brace_depth += 1
            elif source[i] == "}":
                brace_depth -= 1
            i += 1
        body = source[start : i - 1]
        # Extract property names: "name: Type" or "readonly name: Type" or "name?: Type"
        props = re.findall(r"(?:readonly\s+)?(\w+)\s*\??\s*[:=]", body)
        line = source[: m.start()].count("\n") + 1
        entities.append(
            CodeEntity(
                code_id=f"{module_path}:{name}",
                name=name,
                args=props,
                return_annotation="interface",
                file_path=file_path,
                line=line,
            )
        )
    return entities


def _find_type_aliases(source: str, module_path: str, file_path: Path) -> list[CodeEntity]:
    """Find type alias declarations: type Name = ..."""
    entities: list[CodeEntity] = []
    # type Name = ... (until ; or newline or next declaration)
    pattern = r"(?:export\s+)?type\s+(\w+)\s*=\s*"
    for m in re.finditer(pattern, source):
        name = m.group(1)
        rest = source[m.end() :]
        # Extract type expression: balance braces/parens, stop at ; or \n\n or next keyword
        depth = 0
        in_brace, in_paren, in_bracket = 0, 0, 0
        i = 0
        while i < len(rest):
            c = rest[i]
            if c == "{":
                in_brace += 1
            elif c == "}":
                in_brace -= 1
            elif c == "(":
                in_paren += 1
            elif c == ")":
                in_paren -= 1
            elif c == "[":
                in_bracket += 1
            elif c == "]":
                in_bracket -= 1
            elif c == ";" and in_brace == in_paren == in_bracket == 0:
                break
            elif c == "\n" and in_brace == in_paren == in_bracket == 0:
                break
            i += 1
        type_expr = rest[:i].strip()
        type_expr = re.sub(r"\s+", " ", type_expr)[:200]
        line = source[: m.start()].count("\n") + 1
        entities.append(
            CodeEntity(
                code_id=f"{module_path}:{name}",
                name=name,
                args=[],
                return_annotation=type_expr,
                file_path=file_path,
                line=line,
            )
        )
    return entities


def parse_typescript_file(file_path: Path, module_path: str) -> list[CodeEntity]:
    """Parse one .ts/.tsx/.js/.jsx file and return entities."""
    source = file_path.read_text(encoding="utf-8")
    entities: list[CodeEntity] = []
    entities.extend(_find_functions(source, module_path, file_path))
    entities.extend(_find_classes_and_methods(source, module_path, file_path))
    entities.extend(_find_interfaces(source, module_path, file_path))
    entities.extend(_find_type_aliases(source, module_path, file_path))
    return entities


def _is_ignored(rel_path: Path, ignore_patterns: tuple[str, ...]) -> bool:
    """Return True if path matches any ignore pattern."""
    parts = rel_path.parts
    for pattern in ignore_patterns:
        for part in parts:
            if fnmatch.fnmatch(part, pattern) or part == pattern:
                return True
    if any(fnmatch.fnmatch(rel_path.name, p) for p in ("*.test.*", "*.spec.*", "*.d.ts")):
        return True
    return False


def parse_typescript_module(
    root: Path,
    package_path: Path,
    ignore_patterns: tuple[str, ...] = (),
) -> list[CodeEntity]:
    """
    Recursively parse TypeScript/JavaScript files and return all entities.
    """
    ignore = list(TS_IGNORE) + list(ignore_patterns)
    all_entities: list[CodeEntity] = []
    for ext in TS_EXTENSIONS:
        for path in package_path.rglob(f"*{ext}"):
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            if _is_ignored(rel, tuple(ignore)):
                continue
            module_path = _path_to_module(root, path)
            all_entities.extend(parse_typescript_file(path, module_path))
    return all_entities
