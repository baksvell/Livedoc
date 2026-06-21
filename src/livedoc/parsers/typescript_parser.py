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


def _normalize_param_signature(param: str) -> str:
    """Extract param with type/default details, normalized for stable hashing."""
    original = param.strip()
    name = _normalize_param(original)
    if not name or name == "?":
        return name
    if original.startswith("{") or original.startswith("["):
        # Destructuring can be noisy; keep normalized name to avoid unstable hashes.
        return name
    default_expr = ""
    if "=" in original:
        before_default, after_default = original.split("=", 1)
        original = before_default.strip()
        default_expr = re.sub(r"\s+", " ", after_default.strip())
    type_expr = ""
    if ":" in original:
        _, raw_type = original.split(":", 1)
        type_expr = re.sub(r"\s+", " ", raw_type.strip())
    sig = name
    if type_expr:
        sig = f"{sig}: {type_expr}"
    if default_expr:
        sig = f"{sig} = {default_expr}"
    return sig


def _split_top_level_commas(text: str) -> list[str]:
    """Split by commas, ignoring commas inside (), {}, [], <> and strings."""
    parts: list[str] = []
    current: list[str] = []
    paren = brace = bracket = angle = 0
    in_single = False
    in_double = False
    in_backtick = False
    escaped = False

    for ch in text:
        if escaped:
            current.append(ch)
            escaped = False
            continue
        if ch == "\\":
            current.append(ch)
            escaped = True
            continue
        if in_single:
            current.append(ch)
            if ch == "'":
                in_single = False
            continue
        if in_double:
            current.append(ch)
            if ch == '"':
                in_double = False
            continue
        if in_backtick:
            current.append(ch)
            if ch == "`":
                in_backtick = False
            continue
        if ch == "'":
            current.append(ch)
            in_single = True
            continue
        if ch == '"':
            current.append(ch)
            in_double = True
            continue
        if ch == "`":
            current.append(ch)
            in_backtick = True
            continue
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
        elif ch == "<":
            angle += 1
        elif ch == ">":
            angle = max(0, angle - 1)
        elif ch == "," and paren == 0 and brace == 0 and bracket == 0 and angle == 0:
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
    in_single = in_double = in_backtick = False
    escaped = False
    for i in range(open_idx, len(source)):
        ch = source[i]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if in_single:
            if ch == "'":
                in_single = False
            continue
        if in_double:
            if ch == '"':
                in_double = False
            continue
        if in_backtick:
            if ch == "`":
                in_backtick = False
            continue
        if ch == "'":
            in_single = True
            continue
        if ch == '"':
            in_double = True
            continue
        if ch == "`":
            in_backtick = True
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _nesting_depths(source: str) -> list[tuple[int, int, int]]:
    """Return brace/paren/bracket depth before every character in source."""
    depths: list[tuple[int, int, int]] = []
    brace = paren = bracket = 0
    in_single = in_double = in_backtick = False
    in_line_comment = in_block_comment = False
    escaped = False
    index = 0

    while index < len(source):
        depths.append((brace, paren, bracket))
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            index += 1
            continue
        if in_block_comment:
            if char == "*" and next_char == "/":
                depths.append((brace, paren, bracket))
                in_block_comment = False
                index += 2
            else:
                index += 1
            continue
        if escaped:
            escaped = False
            index += 1
            continue
        if char == "\\" and (in_single or in_double or in_backtick):
            escaped = True
            index += 1
            continue
        if in_single:
            if char == "'":
                in_single = False
            index += 1
            continue
        if in_double:
            if char == '"':
                in_double = False
            index += 1
            continue
        if in_backtick:
            if char == "`":
                in_backtick = False
            index += 1
            continue

        if char == "/" and next_char == "/":
            depths.append((brace, paren, bracket))
            in_line_comment = True
            index += 2
            continue
        if char == "/" and next_char == "*":
            depths.append((brace, paren, bracket))
            in_block_comment = True
            index += 2
            continue
        if char == "'":
            in_single = True
        elif char == '"':
            in_double = True
        elif char == "`":
            in_backtick = True
        elif char == "{":
            brace += 1
        elif char == "}":
            brace = max(0, brace - 1)
        elif char == "(":
            paren += 1
        elif char == ")":
            paren = max(0, paren - 1)
        elif char == "[":
            bracket += 1
        elif char == "]":
            bracket = max(0, bracket - 1)
        index += 1

    depths.append((brace, paren, bracket))
    return depths


def _is_top_level_member(source: str, start: int, depths: list[tuple[int, int, int]]) -> bool:
    """Return whether a candidate starts at class-body top level."""
    if depths[start] != (0, 0, 0):
        return False
    previous = start - 1
    while previous >= 0 and source[previous].isspace():
        previous -= 1
    return previous < 0 or source[previous] not in ".@"


def _return_before(source: str, start: int, stop_char: str) -> str:
    """Extract ': Type' between start and next stop_char, if present."""
    end = source.find(stop_char, start)
    if end == -1:
        return ""
    between = source[start:end].strip()
    if between.startswith(":"):
        return between[1:].strip()
    return ""


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
    # function name(...) or export/default/async variants
    pattern = r"(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(\w+)(?:\s*<[^>]*>)?\s*\("
    for m in re.finditer(pattern, source):
        name = m.group(1)
        open_idx = m.end() - 1
        close_idx = _find_matching_paren(source, open_idx)
        if close_idx == -1:
            continue
        args_str = source[open_idx + 1 : close_idx]
        ret = _return_before(source, close_idx + 1, "{")
        params = [p for p in _split_top_level_commas(args_str) if p.strip()]
        args = [_normalize_param(p) for p in params]
        signature_args = [_normalize_param_signature(p) for p in params]
        line = source[: m.start()].count("\n") + 1
        entities.append(
            CodeEntity(
                code_id=f"{module_path}:{name}",
                name=name,
                args=args,
                return_annotation=ret,
                file_path=file_path,
                line=line,
                signature_args=signature_args,
            )
        )
    # const/let name = (params) => or const/let name = (params): Type =>
    pattern2 = r"(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\("
    for m in re.finditer(pattern2, source):
        name = m.group(1)
        open_idx = m.end() - 1
        close_idx = _find_matching_paren(source, open_idx)
        if close_idx == -1:
            continue
        args_str = source[open_idx + 1 : close_idx]
        after = source[close_idx + 1 :]
        arrow_pos = after.find("=>")
        ret = ""
        if arrow_pos != -1:
            between = after[:arrow_pos].strip()
            if between.startswith(":"):
                ret = between[1:].strip()
        params = [p for p in _split_top_level_commas(args_str) if p.strip()]
        args = [_normalize_param(p) for p in params]
        signature_args = [_normalize_param_signature(p) for p in params]
        line = source[: m.start()].count("\n") + 1
        entities.append(
            CodeEntity(
                code_id=f"{module_path}:{name}",
                name=name,
                args=args,
                return_annotation=ret,
                file_path=file_path,
                line=line,
                signature_args=signature_args,
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
        depths = _nesting_depths(class_body)
        # Match only declarations at class-body top level, never calls inside methods.
        method_pattern = (
            r"(?:(?:public|private|protected|static|abstract|override|declare|async|get|set)\s+)*"
            r"([A-Za-z_$][\w$]*)\s*(?:<[^>{}()]*>)?\s*\("
        )
        for m in re.finditer(method_pattern, class_body):
            if not _is_top_level_member(class_body, m.start(), depths):
                continue
            name = m.group(1)
            if name == "constructor":
                continue
            open_idx = class_match.end() + m.end() - 1
            close_idx = _find_matching_paren(source, open_idx)
            if close_idx == -1:
                continue
            args_str = source[open_idx + 1 : close_idx]
            ret = _return_before(source, close_idx + 1, "{")
            params = [p for p in _split_top_level_commas(args_str) if p.strip()]
            args = [_normalize_param(p) for p in params]
            signature_args = [_normalize_param_signature(p) for p in params]
            if "this" in args:
                args = [a for a in args if a != "this"]
                signature_args = [a for a in signature_args if not a.startswith("this")]
            line = source[: m.start() + class_match.end()].count("\n") + 1
            entities.append(
                CodeEntity(
                    code_id=f"{module_path}:{class_name}.{name}",
                    name=name,
                    args=args,
                    return_annotation=ret,
                    file_path=file_path,
                    line=line,
                    signature_args=signature_args,
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

    # TypeScript overloads can produce the same code_id multiple times. Keep the
    # last declaration, which is normally the concrete implementation.
    unique_entities: dict[str, CodeEntity] = {}
    for entity in entities:
        unique_entities[entity.code_id] = entity
    return list(unique_entities.values())


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
