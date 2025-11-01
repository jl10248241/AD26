from __future__ import annotations
from pathlib import Path
import json

# Resolve repo root from this file
ROOT = Path(__file__).resolve().parents[2]  # .../College_AD_Unified_Workspace_Blank_v17.2
LOGS = ROOT / "logs"
MEDIA = LOGS / "MEDIA"

def list_media_files():
    """
    Returns MEDIA/*.media.json sorted by mtime (oldest->newest).
    """
    MEDIA.mkdir(parents=True, exist_ok=True)
    files = list(MEDIA.glob("*.media.json"))
    files.sort(key=lambda p: p.stat().st_mtime)
    return files

def read_media(p: Path) -> dict:
    """
    Safe JSON reader with utf-8.
    """
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
