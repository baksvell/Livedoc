"""Python module parser: extract functions/methods with signatures and build code_id."""

from __future__ import annotations

import ast
import fnmatch
from pathlib import Path

from livedoc.core.signatures import CodeEntity

DEFAULT_IGNORE = ("tests", "test_*", "venv", ".venv", "__pycache__", ".git", "*.egg-info")


def _qualified_name(module_path: str, node: ast.AST, class_name: str | None = None) -> str:
    """Build code_id as module_path:name or module_path:Class.method."""
    if class_name:
        return f"{module_path}:{class_name}.{getattr(node, 'name', '')}"
    return f"{module_path}:{getattr(node, 'name', '')}"


def _get_args(node: ast.FunctionDef) -> list[str]:
    """Extract argument names from ast.FunctionDef (including *args, **kwargs)."""
    args: list[str] = []
    for a in node.args.args:
        if a.arg == "self":
            continue
        args.append(a.arg)
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    return args


def _return_annotation(node: ast.FunctionDef) -> str:
    """String representation of return annotation."""
    if node.returns is None:
        return ""
    return ast.unparse(node.returns) if hasattr(ast, "unparse") else ""


def parse_python_file(file_path: Path, module_path: str) -> list[CodeEntity]:
    """Parse one .py file and return entities (functions and methods)."""
    entities: list[CodeEntity] = []
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            code_id = _qualified_name(module_path, node)
            entities.append(
                CodeEntity(
                    code_id=code_id,
                    name=node.name,
                    args=_get_args(node),
                    return_annotation=_return_annotation(node),
                    file_path=file_path,
                    line=node.lineno,
                )
            )
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    code_id = _qualified_name(module_path, child, node.name)
                    entities.append(
                        CodeEntity(
                            code_id=code_id,
                            name=child.name,
                            args=_get_args(child),
                            return_annotation=_return_annotation(child),
                            file_path=file_path,
                            line=child.lineno,
                        )
                    )
    return entities


def _path_to_module(root: Path, file_path: Path) -> str:
    """File path relative to root -> dotted module name."""
    rel = file_path.relative_to(root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def _is_ignored(rel_path: Path, ignore_patterns: tuple[str, ...]) -> bool:
    """Return True if path matches any ignore pattern (segment or glob)."""
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
    """
    Recursively parse Python package/module and return all entities.
    ignore_patterns: path segments or globs to exclude (tests, venv, ...).
    """
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
    """Build code_id -> signature_hash map from entities for comparison."""
    return {e.code_id: e.get_signature_hash() for e in entities}
