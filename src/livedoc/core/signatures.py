"""
Подписи кода (signature hash) для детектора изменений.
При изменении сигнатуры сущности считаем связанную документацию устаревшей.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


def signature_hash(name: str, args: list[str], return_annotation: str = "") -> str:
    """Строит устойчивый хеш по имени и сигнатуре (аргументы + возврат)."""
    payload = json.dumps(
        {"name": name, "args": sorted(args), "return": return_annotation},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class CodeEntity:
    """Сущность кода с подписью (для Python — функция/метод)."""

    code_id: str
    name: str
    args: list[str]
    return_annotation: str
    file_path: Path
    line: int

    def get_signature_hash(self) -> str:
        return signature_hash(self.name, self.args, self.return_annotation)

    def format_signature(self) -> str:
        """Человекочитаемая сигнатура: add(a, b) -> int."""
        args_str = ", ".join(self.args)
        ret = f" -> {self.return_annotation}" if self.return_annotation else ""
        return f"{self.name}({args_str}){ret}"


@dataclass
class CodeSignatures:
    """
    Хранилище подписей кода: code_id -> hash, опционально readable-сигнатура.
    Позволяет сравнить текущее состояние кода с сохранённым и получить изменённые code_id.
    """

    signatures: dict[str, str]  # code_id -> signature_hash
    readable: dict[str, str] = field(default_factory=dict)  # code_id -> "add(a, b) -> int"

    def changed_code_ids(self, current: dict[str, str]) -> set[str]:
        """
        current: code_id -> текущий signature_hash.
        Возвращает code_id, для которых подпись изменилась или сущность удалена.
        """
        changed: set[str] = set()
        for code_id, new_hash in current.items():
            old_hash = self.signatures.get(code_id)
            if old_hash != new_hash:
                changed.add(code_id)
        for code_id in self.signatures:
            if code_id not in current:
                changed.add(code_id)  # удалён из кода
        return changed

    def get_readable(self, code_id: str) -> str | None:
        """Получить сохранённую readable-сигнатуру (если есть)."""
        return self.readable.get(code_id)

    def update(self, current: dict[str, str], readable: dict[str, str] | None = None) -> None:
        """Обновить сохранённые подписи до текущего состояния."""
        self.signatures = dict(current)
        if readable is not None:
            self.readable = dict(readable)

    def save(self, path: Path, readable: dict[str, str] | None = None) -> None:
        """Сохранить в JSON (например .livedoc/code_signatures.json)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        # Сохраняем hash + readable в едином формате для удобства
        out: dict[str, str | dict] = {}
        for code_id, h in self.signatures.items():
            sig = (readable or self.readable).get(code_id)
            if sig:
                out[code_id] = {"hash": h, "sig": sig}
            else:
                out[code_id] = h
        path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> CodeSignatures | None:
        """Загрузить из JSON; если файла нет — вернуть None."""
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        sigs: dict[str, str] = {}
        readable: dict[str, str] = {}
        for code_id, val in data.items():
            if isinstance(val, str):
                sigs[code_id] = val
            elif isinstance(val, dict):
                sigs[code_id] = val.get("hash") or val.get("h") or ""
                if "sig" in val or "s" in val:
                    readable[code_id] = val.get("sig") or val.get("s") or ""
        return cls(signatures=sigs, readable=readable)
