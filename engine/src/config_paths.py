# engine/src/config_paths.py — canonical path registry
from __future__ import annotations
from pathlib import Path

# Workspace root: .../College_AD_Unified_Workspace_.../
ROOT   = Path(__file__).resolve().parents[2]

ENGINE = ROOT / "engine"
SRC    = ENGINE / "src"
STATE  = ENGINE / "state"
CONFIG = ENGINE / "config"
LOGS   = ROOT / "logs"
DOCS   = ROOT / "docs"

# Back-compat aliases (some modules may look these up)
DOCS_PATH   = DOCS
CONFIG_PATH = CONFIG
LOGS_PATH   = LOGS
STATE_PATH  = STATE

__all__ = [
    "ROOT","ENGINE","SRC","STATE","CONFIG","LOGS","DOCS",
    "DOCS_PATH","CONFIG_PATH","LOGS_PATH","STATE_PATH",
]
