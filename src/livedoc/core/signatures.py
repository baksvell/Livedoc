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
        {"name": name, "args": args, "return": return_annotation},
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
    signature_args: list[str] | None = None

    def get_signature_hash(self) -> str:
        args_for_hash = self.signature_args if self.signature_args is not None else self.args
        return signature_hash(self.name, args_for_hash, self.return_annotation)

    def format_signature(self, detailed: bool = False) -> str:
        """Human-readable signature: add(a, b) -> int."""
        args = self.signature_args if detailed and self.signature_args is not None else self.args
        args_str = ", ".join(args)
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
        if not isinstance(data, dict):
            raise ValueError("signature baseline must be a JSON object")

        sigs: dict[str, str] = {}
        readable: dict[str, str] = {}
        for code_id, val in data.items():
            if not isinstance(code_id, str) or not code_id:
                raise ValueError("signature baseline contains an invalid code_id")
            if isinstance(val, str):
                sigs[code_id] = val
                continue
            if not isinstance(val, dict):
                raise ValueError(f"invalid signature entry for {code_id!r}")

            signature = val.get("hash") or val.get("h")
            if not isinstance(signature, str) or not signature:
                raise ValueError(f"missing signature hash for {code_id!r}")
            sigs[code_id] = signature

            readable_signature = val.get("sig") or val.get("s")
            if readable_signature is not None:
                if not isinstance(readable_signature, str):
                    raise ValueError(f"invalid readable signature for {code_id!r}")
                readable[code_id] = readable_signature
        return cls(signatures=sigs, readable=readable)
