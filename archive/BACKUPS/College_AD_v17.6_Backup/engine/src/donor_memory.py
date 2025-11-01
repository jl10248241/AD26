from __future__ import annotations
from typing import Dict, Any, Optional

# ---- Config helpers ---------------------------------------------------------
DEFAULT_DECAY = 0.98  # 2% fade per week toward neutral

def _cfg(world: Dict[str, Any]) -> Dict[str, Any]:
    return world.setdefault("donor_cfg", {})  # e.g., {"decay_rate": 0.98}

def set_donor_decay(world: Dict[str, Any], rate: float) -> None:
    """
    Optional: call once to tune memory fade. Example: set_donor_decay(world, 0.99)
    """
    rate = float(rate)
    _cfg(world)["decay_rate"] = max(0.90, min(0.999, rate))  # clamp: 10%..0.1% per week

# ---- Store & records --------------------------------------------------------
def _school_key(name: str) -> str:
    return str(name or "").strip()

def _store(world: Dict[str, Any]) -> Dict[str, Any]:
    return world.setdefault("donors", {})  # { school_name: donor_obj }

def get_or_create_donor(world: Dict[str, Any], school_name: str, persona: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    key = _school_key(school_name)
    donors = _store(world)
    if key not in donors:
        donors[key] = {
            "name": f"{key} Primary Donor",
            "persona": persona or {},
            "trust": 0.50,      # 0..1 sentiment toward AD/School
            "leverage": 0.00,   # positive leverage → bigger pledges / faster commits
            "history": []       # list of pledge records
        }
    if persona:
        donors[key]["persona"] = persona
    return donors[key]

def record_pledge(world: Dict[str, Any], school_name: str, *, week: int, amount: float, earmark: Optional[str] = None, due_week: Optional[int] = None) -> Dict[str, Any]:
    d = get_or_create_donor(world, school_name)
    pledge = {
        "week": int(week),
        "amount": float(amount),
        "earmark": earmark or "",
        "due_week": int(due_week) if due_week is not None else None,
        "fulfilled": False
    }
    d["history"].append(pledge)
    d["trust"] = max(0.0, min(1.0, d["trust"] + 0.02))
    d["leverage"] = max(-1.0, min(1.0, d["leverage"] + 0.01))
    return pledge

def fulfill_pledge(world: Dict[str, Any], school_name: str, pledge_index: int, *, success: bool = True) -> None:
    d = get_or_create_donor(world, school_name)
    if 0 <= pledge_index < len(d["history"]):
        d["history"][pledge_index]["fulfilled"] = bool(success)
        if success:
            d["trust"] = min(1.0, d["trust"] + 0.05)
            d["leverage"] = min(1.0, d["leverage"] + 0.02)
        else:
            d["trust"] = max(0.0, d["trust"] - 0.07)
            d["leverage"] = max(-1.0, d["leverage"] - 0.03)

# ---- Decay / memory fade ----------------------------------------------------
def apply_decay(world: Dict[str, Any], school_name: str, *, weeks: int = 1) -> None:
    """
    Light decay so relationships don’t lock. Called each tick (week).
    Uses world['donor_cfg']['decay_rate'] if set, else DEFAULT_DECAY (0.98).
    """
    d = get_or_create_donor(world, school_name)
    rate = float(_cfg(world).get("decay_rate", DEFAULT_DECAY))
    rate = max(0.90, min(0.999, rate))  # sanity clamp
    # decay toward neutral
    d["trust"] = 0.5 + (d["trust"] - 0.5) * (rate ** weeks)
    d["leverage"] = d["leverage"] * (rate ** weeks)
