
# engine/src/pledge_stipulations.py
# v17.9 — Canonical pledge stipulations module (scaffold)
# Purpose: provide a single import target for legacy forwarders in v17_7/ and v17_8/.
# This file intentionally keeps behavior minimal and side-effect free.
#
# API Surface (kept for compatibility):
#   - tick_update(world, cfg, G, week, rng=None): noop-safe per-tick hook
#   - apply_stipulation(pledge: dict) -> dict: returns normalized pledge info
#   - normalize_status(status: str) -> str: maps to a stable set of statuses
#
from __future__ import annotations
from typing import Any, Dict, Optional

_PLEDGE_STATUSES = {
    "promised": "promised",
    "pending": "pending",
    "received": "received",
    "lapsed": "lapsed",
    "cancelled": "cancelled",
    "declined": "declined",
}

def normalize_status(status: Optional[str]) -> str:
    if not status:
        return "pending"
    key = str(status).strip().lower()
    return _PLEDGE_STATUSES.get(key, "pending")

def apply_stipulation(pledge: Dict[str, Any]) -> Dict[str, Any]:
    """Return a normalized pledge dict (non-destructive)."""
    out = dict(pledge or {})
    out["status"] = normalize_status(out.get("status"))
    # Amount normalization (optional)
    try:
        if "amount" in out and out["amount"] is not None:
            out["amount"] = float(out["amount"])
    except Exception:
        pass
    return out

def tick_update(*, world: Dict[str, Any], cfg: Dict[str, Any], G: Dict[str, Any], week: int, rng=None) -> None:
    """Noop-safe hook: iterate any known pledge records and normalize status.

    This keeps old code paths happy without changing game behavior.
    """
    try:
        schools = world.get("schools", [])
    except Exception:
        return

    for s in schools:
        pledges = s.get("pledges") or []
        if isinstance(pledges, list):
            for i, p in enumerate(list(pledges)):
                pledges[i] = apply_stipulation(p)
        elif isinstance(pledges, dict):
            # if stored as dict keyed by id/name
            for k, v in list(pledges.items()):
                pledges[k] = apply_stipulation(v)
