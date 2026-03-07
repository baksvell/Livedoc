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
    """Build stable hash from name and signature (args + return)."""
    payload = json.dumps(
        {"name": name, "args": sorted(args), "return": return_annotation},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class CodeEntity:
    """Code entity with signature (Python: function or method)."""

    code_id: str
    name: str
    args: list[str]
    return_annotation: str
    file_path: Path
    line: int

    def get_signature_hash(self) -> str:
        return signature_hash(self.name, self.args, self.return_annotation)

    def format_signature(self) -> str:
        """Human-readable signature: add(a, b) -> int."""
        args_str = ", ".join(self.args)
        ret = f" -> {self.return_annotation}" if self.return_annotation else ""
        return f"{self.name}({args_str}){ret}"


@dataclass
class CodeSignatures:
    """Store code signatures: code_id -> hash, optionally readable. Compare and get changed code_id."""

    signatures: dict[str, str]  # code_id -> signature_hash
    readable: dict[str, str] = field(default_factory=dict)  # code_id -> "add(a, b) -> int"

    def changed_code_ids(self, current: dict[str, str]) -> set[str]:
        """Return code_ids whose signature changed or entity was removed."""
        changed: set[str] = set()
        for code_id, new_hash in current.items():
            old_hash = self.signatures.get(code_id)
            if old_hash != new_hash:
                changed.add(code_id)
        for code_id in self.signatures:
            if code_id not in current:
                changed.add(code_id)  # removed from code
        return changed

    def get_readable(self, code_id: str) -> str | None:
        """Get stored readable signature if any."""
        return self.readable.get(code_id)

    def update(self, current: dict[str, str], readable: dict[str, str] | None = None) -> None:
        """Update stored signatures to current state."""
        self.signatures = dict(current)
        if readable is not None:
            self.readable = dict(readable)

    def save(self, path: Path, readable: dict[str, str] | None = None) -> None:
        """Save to JSON (e.g. .livedoc/code_signatures.json)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        # Save hash + readable in single format
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
        """Load from JSON; return None if file does not exist."""
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
