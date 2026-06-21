"""Python parser: extract functions and methods with stable signatures."""

from __future__ import annotations

import ast
import fnmatch
from pathlib import Path

from livedoc.core.signatures import CodeEntity

DEFAULT_IGNORE = ("tests", "test_*", "venv", ".venv", "__pycache__", ".git", "*.egg-info")

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def _qualified_name(module_path: str, node: FunctionNode, class_name: str | None = None) -> str:
    """Build code_id as module_path:name or module_path:Class.method."""
    if class_name:
        return f"{module_path}:{class_name}.{node.name}"
    return f"{module_path}:{node.name}"


def _is_static_method(node: FunctionNode) -> bool:
    """Return whether a function is decorated with ``@staticmethod``."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "staticmethod":
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == "staticmethod":
            return True
    return False


def _format_annotation(annotation: ast.expr | None) -> str:
    """Return a source-like representation of a type annotation."""
    if annotation is None:
        return ""
    return ast.unparse(annotation)


def _format_default(default: ast.expr | None) -> str:
    """Return a source-like representation of a default value."""
    if default is None:
        return ""
    return ast.unparse(default)


def _format_arg(arg: ast.arg, default: ast.expr | None = None, *, detailed: bool) -> str:
    """Format one argument, optionally preserving its annotation and default."""
    value = arg.arg
    if detailed and arg.annotation is not None:
        value = f"{value}: {_format_annotation(arg.annotation)}"
    if detailed and default is not None:
        value = f"{value} = {_format_default(default)}"
    return value


def _signature_parts(
    node: FunctionNode,
    *,
    detailed: bool,
    skip_implicit_first: bool,
) -> list[str]:
    """Build Python signature parts, including ``/`` and ``*`` separators."""
    parts: list[str] = []

    positional = [*node.args.posonlyargs, *node.args.args]
    positional_defaults: list[ast.expr | None] = [None] * (
        len(positional) - len(node.args.defaults)
    ) + list(node.args.defaults)

    skip_first = (
        skip_implicit_first
        and bool(positional)
        and positional[0].arg in {"self", "cls"}
        and not _is_static_method(node)
    )
    if skip_first:
        positional = positional[1:]
        positional_defaults = positional_defaults[1:]

    original_posonly_count = len(node.args.posonlyargs)
    remaining_posonly_count = max(0, original_posonly_count - int(skip_first))

    for index, (arg, default) in enumerate(zip(positional, positional_defaults, strict=True)):
        parts.append(_format_arg(arg, default, detailed=detailed))
        if remaining_posonly_count and index + 1 == remaining_posonly_count:
            parts.append("/")

    if node.args.vararg is not None:
        vararg = _format_arg(node.args.vararg, detailed=detailed)
        parts.append(f"*{vararg}")
    elif node.args.kwonlyargs:
        parts.append("*")

    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True):
        parts.append(_format_arg(arg, default, detailed=detailed))

    if node.args.kwarg is not None:
        kwarg = _format_arg(node.args.kwarg, detailed=detailed)
        parts.append(f"**{kwarg}")

    return parts


def _get_args(node: FunctionNode, *, skip_implicit_first: bool = False) -> list[str]:
    """Extract argument names while preserving Python parameter kinds."""
    return _signature_parts(
        node,
        detailed=False,
        skip_implicit_first=skip_implicit_first,
    )


def _get_signature_args(
    node: FunctionNode,
    *,
    skip_implicit_first: bool = False,
) -> list[str]:
    """Extract arguments with type/default details for stable hashing."""
    return _signature_parts(
        node,
        detailed=True,
        skip_implicit_first=skip_implicit_first,
    )


def _return_annotation(node: FunctionNode) -> str:
    """Return a source-like representation of the return annotation."""
    return _format_annotation(node.returns)


def _build_entity(
    node: FunctionNode,
    file_path: Path,
    module_path: str,
    class_name: str | None = None,
) -> CodeEntity:
    """Create a ``CodeEntity`` from a Python function or method node."""
    is_method = class_name is not None
    return CodeEntity(
        code_id=_qualified_name(module_path, node, class_name),
        name=node.name,
        args=_get_args(node, skip_implicit_first=is_method),
        return_annotation=_return_annotation(node),
        file_path=file_path,
        line=node.lineno,
        signature_args=_get_signature_args(node, skip_implicit_first=is_method),
    )


def parse_python_file(file_path: Path, module_path: str) -> list[CodeEntity]:
    """Parse one ``.py`` file and return top-level functions and class methods."""
    entities: list[CodeEntity] = []
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            entities.append(_build_entity(node, file_path, module_path))
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    entities.append(_build_entity(child, file_path, module_path, node.name))
    return entities


def _path_to_module(root: Path, file_path: Path) -> str:
    """Convert a file path relative to root into a dotted module name."""
    rel = file_path.relative_to(root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def _is_ignored(rel_path: Path, ignore_patterns: tuple[str, ...]) -> bool:
    """Return True if a path matches an ignored segment or glob."""
    parts = rel_path.parts
    for pattern in ignore_patterns:
        for part in parts:
            if fnmatch.fnmatch(part, pattern) or part == pattern:
                return True
    return False


def parse_python_module(
    root: Path,
    package_path: Path,
    ignore_patterns: tuple[str, ...] = DEFAULT_IGNORE,
) -> list[CodeEntity]:
    """Recursively parse a Python package/module and return all entities."""
    all_entities: list[CodeEntity] = []
    if package_path.is_file() and package_path.suffix == ".py":
        if _is_ignored(package_path.relative_to(root), ignore_patterns):
            return all_entities
        module_path = _path_to_module(root, package_path)
        all_entities.extend(parse_python_file(package_path, module_path))
        return all_entities

    for path in package_path.rglob("*.py"):
        if path.name.startswith("_"):
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        if _is_ignored(rel, ignore_patterns):
            continue
        module_path = _path_to_module(root, path)
        all_entities.extend(parse_python_file(path, module_path))
    return all_entities


def build_current_signatures(entities: list[CodeEntity]) -> dict[str, str]:
    """Build a ``code_id -> signature_hash`` map from parsed entities."""
    return {entity.code_id: entity.get_signature_hash() for entity in entities}
