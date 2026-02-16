"""
Формирование отчёта об устаревших фрагментах документации.
"""

from __future__ import annotations

from livedoc.core.graph import DocFragment


def _format_change(old_sig: str | None, new_sig: str | None) -> str:
    """Форматирует diff сигнатуры для отчёта."""
    if old_sig is None and new_sig:
        return f"Добавлено: {new_sig}"
    if old_sig and new_sig is None:
        return f"Удалено: {old_sig}"
    if old_sig and new_sig:
        return f"{old_sig}  ->  {new_sig}"
    return "Сигнатура изменилась"


def report_outdated(
    outdated: list[DocFragment],
    *,
    changes: dict[str, tuple[str | None, str | None]] | None = None,
    verbose: bool = True,
) -> str:
    """
    Собирает текстовый отчёт: какие фрагменты доки помечены как устаревшими и что изменилось.
    changes: code_id -> (старая_сигнатура, новая_сигнатура)
    """
    if not outdated:
        return "Документация актуальна: изменений в связанном коде не обнаружено."

    changes = changes or {}

    lines = [
        "Возможно устаревшие фрагменты документации (код изменился):",
        "",
    ]
    for f in outdated:
        lines.append(f"  • {f.doc_fragment_id}")
        lines.append(f"    Файл: {f.file_path}, строка ~{f.line_start}")
        if f.heading:
            lines.append(f"    Раздел: {f.heading}")
        for code_id in f.code_ids:
            old_sig, new_sig = changes.get(code_id, (None, None))
            diff = _format_change(old_sig, new_sig)
            lines.append(f"    [{code_id}]  {diff}")
        if verbose:
            lines.append("    Рекомендация: обновите описание параметров/возвращаемого значения в документации.")
        lines.append("")
    return "\n".join(lines)
