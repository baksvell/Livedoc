"""
Подписи кода (signature hash) для детектора изменений.
При изменении сигнатуры сущности считаем связанную документацию устаревшей.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


def parse_readable_signature(sig: str) -> tuple[str, list[str], str] | None:
    """Parse 'name(a, b) -> ret' into (name, args, ret)."""
    match = re.fullmatch(r"(.+?)\((.*)\)(?:\s*->\s*(.*))?", sig.strip())
    if not match:
        return None
    name = match.group(1).strip()
    args_raw = match.group(2).strip()
    ret = (match.group(3) or "").strip()
    args = [part.strip() for part in args_raw.split(",") if part.strip()] if args_raw else []
    return name, args, ret


def parse_readable_parameter(param: str) -> tuple[str, str, str]:
    """Parse parameter into (name, type, default)."""
    raw = param.strip()
    default_expr = ""
    if "=" in raw:
        before_default, after_default = raw.split("=", 1)
        raw = before_default.strip()
        default_expr = after_default.strip()

    type_expr = ""
    name = raw
    if ":" in raw:
        before_type, after_type = raw.split(":", 1)
        name = before_type.strip()
        type_expr = after_type.strip()

    return name, type_expr, default_expr


def _has_single_parameter_type_change(
    old_args: list[str],
    new_args: list[str],
) -> bool:
    """Return True when exactly one parameter type changed."""
    if len(old_args) != len(new_args):
        return False

    type_changes = 0
    for old_arg, new_arg in zip(old_args, new_args):
        old_name, old_type, old_default = parse_readable_parameter(old_arg)
        new_name, new_type, new_default = parse_readable_parameter(new_arg)

        if old_name != new_name or old_default != new_default:
            return False

        if old_type != new_type:
            type_changes += 1

    return type_changes == 1


def _has_single_added_parameter(
    old_args: list[str],
    new_args: list[str],
) -> bool:
    """Return True when new_args differs only by one added parameter."""
    if len(new_args) != len(old_args) + 1:
        return False
    return any(
        new_args[:index] + new_args[index + 1 :] == old_args
        for index in range(len(new_args))
    )


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


CodeChangeKind = Literal[
    "symbol_added",
    "symbol_removed",
    "signature_changed",
    "return_type_changed",
    "parameter_added",
    "parameter_removed",
    "parameter_type_changed",
]


@dataclass(frozen=True)
class CodeChange:
    """A detected change to one code symbol."""

    code_id: str
    old_signature: str | None
    new_signature: str | None
    kind: CodeChangeKind


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

    def build_changes(
        self,
        current: dict[str, str],
        current_readable: dict[str, str],
    ) -> list[CodeChange]:
        """Build structured details for added, changed, or removed code symbols."""
        changes: list[CodeChange] = []
        for code_id in sorted(self.changed_code_ids(current)):
            kind: CodeChangeKind
            if code_id not in self.signatures:
                kind = "symbol_added"
            elif code_id not in current:
                kind = "symbol_removed"
            else:
                kind = "signature_changed"
                old_signature = self.get_readable(code_id)
                new_signature = current_readable.get(code_id)

                if old_signature and new_signature:
                    old_parts = parse_readable_signature(old_signature)
                    new_parts = parse_readable_signature(new_signature)
                    if old_parts and new_parts:
                        old_name, old_args, old_return = old_parts
                        new_name, new_args, new_return = new_parts
                        if old_name == new_name:
                            if old_args == new_args and old_return != new_return:
                                kind = "return_type_changed"
                            elif old_return == new_return:
                                if _has_single_added_parameter(old_args, new_args):
                                    kind = "parameter_added"
                                elif _has_single_added_parameter(new_args, old_args):
                                    kind = "parameter_removed"
                                elif _has_single_parameter_type_change(old_args, new_args):
                                    kind = "parameter_type_changed"

            changes.append(
                CodeChange(
                    code_id=code_id,
                    old_signature=self.get_readable(code_id),
                    new_signature=current_readable.get(code_id),
                    kind=kind,
                )
            )
        return changes

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
