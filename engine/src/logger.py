# engine/src/logger.py
# v17.9 — minimal logger to logs/engine.log (rotates at ~1MB x 3)
from __future__ import annotations
import logging, os
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS / "engine.log"

_level = os.environ.get("ENGINE_LOG_LEVEL", "INFO").upper()

_logger = logging.getLogger("college_ad")
if not _logger.handlers:
    _logger.setLevel(getattr(logging, _level, logging.INFO))
    fh = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    fh.setFormatter(fmt)
    _logger.addHandler(fh)

def get_logger(name: str = "college_ad"):
    return _logger.getChild(name)
