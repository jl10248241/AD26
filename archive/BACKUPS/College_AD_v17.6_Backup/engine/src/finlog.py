# --- College AD v17.5 --- Finance/Prestige/Sentiment Logging Utility
from __future__ import annotations
import csv, os
from pathlib import Path
from typing import Dict, Any

LOG_DIR = Path("logs")
FINANCE_LOG = LOG_DIR / "FINANCE_LOG.csv"

HEADER = ["week","school","donor_yield","expenses","balance","prestige_change","sentiment"]

def ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

def append_finance_row(row: Dict[str, Any]) -> None:
    ensure_dirs()
    exists = FINANCE_LOG.exists()
    with FINANCE_LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        if not exists:
            w.writeheader()
        # write only known keys to avoid schema drift explosions
        w.writerow({k: row.get(k, "") for k in HEADER})
