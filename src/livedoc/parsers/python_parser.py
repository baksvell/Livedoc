"""
Парсер Python-модулей: извлечение функций и методов с сигнатурами и построение code_id.
"""

from __future__ import annotations

import ast
from pathlib import Path

from livedoc.core.signatures import CodeEntity


def _qualified_name(module_path: str, node: ast.AST, class_name: str | None = None) -> str:
    """Строит code_id в формате module_path:name или module_path:Class.method."""
    if class_name:
        return f"{module_path}:{class_name}.{getattr(node, 'name', '')}"
    return f"{module_path}:{getattr(node, 'name', '')}"


def _get_args(node: ast.FunctionDef) -> list[str]:
    """Извлечь имена аргументов из ast.FunctionDef (включая *args, **kwargs)."""
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
    """Строковое представление аннотации возврата."""
    if node.returns is None:
        return ""
    return ast.unparse(node.returns) if hasattr(ast, "unparse") else ""


def parse_python_file(file_path: Path, module_path: str) -> list[CodeEntity]:
    """
    Парсит один .py файл и возвращает список сущностей (функции и методы).
    module_path — имя модуля для code_id, например "examples.sample_module.calc".
    """
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
    """Путь к файлу относительно root -> dotted module name."""
    rel = file_path.relative_to(root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def parse_python_module(root: Path, package_path: Path) -> list[CodeEntity]:
    """
    Рекурсивно парсит Python-пакет/модуль и возвращает все сущности.
    root — корень проекта, package_path — папка или файл (например examples/sample_module).
    """
    all_entities: list[CodeEntity] = []
    if package_path.is_file() and package_path.suffix == ".py":
        module_path = _path_to_module(root, package_path)
        all_entities.extend(parse_python_file(package_path, module_path))
        return all_entities
    for path in package_path.rglob("*.py"):
        if path.name.startswith("_"):
            continue
        module_path = _path_to_module(root, path)
        all_entities.extend(parse_python_file(path, module_path))
    return all_entities


def build_current_signatures(entities: list[CodeEntity]) -> dict[str, str]:
    """Из списка сущностей строит code_id -> signature_hash для сравнения."""
    return {e.code_id: e.get_signature_hash() for e in entities}
