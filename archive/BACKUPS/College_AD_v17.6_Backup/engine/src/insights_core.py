# engine/src/insights_core.py — v17.6 Insights Core (shared across all reports)
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import json, datetime, math

INSIGHTS_VERSION = "insights-1"

def now_stamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

def clamp(x: float, lo: float, hi: float) -> float:
    return hi if x > hi else lo if x < lo else x

def pct(x: float) -> float:
    return 100.0 * x

def arrow(delta: float, eps: float = 1e-6) -> str:
    return "↑" if delta > eps else "↓" if delta < -eps else "→"

def delta_tuple(curr: float, prev: float) -> Dict[str, Any]:
    d = curr - prev
    return {"abs": round(d, 4), "pct": round((d / prev) * 100.0, 2) if abs(prev) > 1e-9 else None, "dir": arrow(d)}

def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

def envelope(entity_type: str, scope: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "version": INSIGHTS_VERSION,
        "entity_type": entity_type,          # e.g., "donor", "coach", "board", "athlete"
        "generated": now_stamp(),
        "scope": scope,                      # e.g., {"schools":[...], "weeks":{"min":1,"max":10}}
        "items": items                       # normalized per-entity facts
    }

def score_linear(trust: float, leverage: float) -> int:
    """
    Generic composite score 0..100. For donors:
    trust in [0..1], leverage in [-1..1] -> combine and scale.
    """
    s = 0.5 * trust + 0.5 * ((leverage + 1.0) / 2.0)    # both 0..1
    return int(round(clamp(s, 0.0, 1.0) * 100))

def top_k(items: List[Dict[str, Any]], key: str, k: int = 10, reverse: bool = True) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda x: x.get(key, 0.0), reverse=reverse)[:k]
