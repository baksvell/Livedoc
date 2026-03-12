"""Load config from .livedoc.json in project root."""

from __future__ import annotations

import json
from pathlib import Path


CONFIG_FILE = ".livedoc.json"


def load_config(root: Path) -> dict:
    """
    Load config from root/.livedoc.json.
    Returns dict with keys: docs, ignore, format. Missing keys use defaults.
    """
    path = root.resolve() / CONFIG_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        result: dict = {}
        if "docs" in data and isinstance(data["docs"], str):
            result["docs"] = data["docs"]
        if "ignore" in data and isinstance(data["ignore"], list):
            result["ignore"] = [str(x) for x in data["ignore"] if isinstance(x, str)]
        if "format" in data and data["format"] in ("text", "json"):
            result["format"] = data["format"]
        return result
    except (json.JSONDecodeError, OSError):
        return {}
