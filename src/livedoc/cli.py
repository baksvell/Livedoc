"""
CLI: livedoc check [путь к проекту]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from livedoc.core.graph import DocGraph
from livedoc.core.signatures import CodeSignatures
from livedoc.parsers.doc_parser import parse_doc_anchors
from livedoc.parsers.python_parser import (
    build_current_signatures,
    parse_python_module,
)
from livedoc.report.reporter import report_outdated


DEFAULT_DOCS_DIR = "docs"
SIGNATURES_FILE = ".livedoc/code_signatures.json"


def run_check(project_root: Path, docs_dir: str, update_signatures: bool) -> int:
    """
    Собрать граф код↔док, сравнить подписи с сохранёнными, вывести устаревшие фрагменты.
    Возвращает 1 если есть устаревшие, 0 если всё актуально.
    """
    root = project_root.resolve()
    code_path = root  # по умолчанию весь проект; можно сузить до src/ или пакета
    docs_path = root / docs_dir
    if not docs_path.exists():
        print(f"Папка документации не найдена: {docs_path}", file=sys.stderr)
        return 2

    # Парсим код (Python)
    entities = parse_python_module(root, code_path)
    current_sigs = build_current_signatures(entities)
    entities_by_id = {e.code_id: e for e in entities}
    current_readable = {e.code_id: e.format_signature() for e in entities}

    # Парсим документацию
    fragments = parse_doc_anchors(docs_path)
    graph = DocGraph()
    for f in fragments:
        for code_id in f.code_ids:
            graph.add_link(code_id, f)

    # Загружаем сохранённые подписи
    sig_path = root / SIGNATURES_FILE
    stored = CodeSignatures.load(sig_path)

    if stored is None:
        # Первый запуск: сохраняем текущее состояние, устаревших нет
        cs = CodeSignatures(current_sigs, readable=current_readable)
        cs.save(sig_path, readable=current_readable)
        print("Первый запуск: подписи кода сохранены. При следующих изменениях кода связанная документация будет помечаться как устаревшая.")
        return 0

    changed = stored.changed_code_ids(current_sigs)
    outdated = graph.get_outdated_fragments(changed)

    # Детали изменений: code_id -> (old_sig, new_sig)
    changes: dict[str, tuple[str | None, str | None]] = {}
    for code_id in changed:
        old_sig = stored.get_readable(code_id)
        if code_id in entities_by_id:
            new_sig = entities_by_id[code_id].format_signature()
        else:
            new_sig = None  # сущность удалена
        changes[code_id] = (old_sig, new_sig)

    if update_signatures:
        cs = CodeSignatures(current_sigs, readable=current_readable)
        cs.save(sig_path, readable=current_readable)
        print("Подписи кода обновлены.")

    report = report_outdated(outdated, changes=changes)
    print(report)

    if outdated:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Living Documentation: проверка актуальности документации")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        type=Path,
        help="Корень проекта (по умолчанию текущая папка)",
    )
    parser.add_argument(
        "--docs",
        default=DEFAULT_DOCS_DIR,
        help=f"Папка с документацией (по умолчанию {DEFAULT_DOCS_DIR})",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="После проверки обновить сохранённые подписи (считать док актуальной)",
    )
    args = parser.parse_args()
    return run_check(args.path, args.docs, args.update)


if __name__ == "__main__":
    sys.exit(main())
