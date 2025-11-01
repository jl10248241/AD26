# engine/src/config_paths.py
from __future__ import annotations
from pathlib import Path
import os, json

_ROOT = Path(__file__).resolve().parents[1]  # engine/
_DEFAULT_DIRS = [
    _ROOT / "config",          # canonical
    _ROOT / "configs",         # accidental legacy
]

def resolve_config_path(name: str, dirs: list[Path] | None = None) -> Path:
    """Return first existing config path for name (e.g., 'ad_prestige.config.json')."""
    search_dirs = (dirs or []) + _DEFAULT_DIRS
    for d in search_dirs:
        p = d / name
        if p.exists():
            return p
    # fall back to canonical location
    return _DEFAULT_DIRS[0] / name

def load_json_config(name: str, default: dict) -> dict:
    p = resolve_config_path(name)
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default
