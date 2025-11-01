from __future__ import annotations
import json, time
from pathlib import Path
from typing import Dict, Tuple

STATE = Path("engine/state/relationships.json")
STATE.parent.mkdir(parents=True, exist_ok=True)

CFG_PATH = Path("engine/config/relationships.config.json")

def _now() -> float:
    return time.time()

def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))

def _read_json(path: Path, default):
    try:
        if path.exists() and path.stat().st_size > 0:
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _load_config() -> dict:
    # Defaults if config missing
    cfg = {
        "decay_per_week": 0.01,
        "seed": {"nodes": [], "edges": []},
        "cooldowns_hours": {},
        "intents": {}
    }
    user = _read_json(CFG_PATH, {})
    # shallow merge
    for k, v in user.items():
        cfg[k] = v
    return cfg

def _edge_key(a: str, b: str) -> str:
    return f"{a}→{b}"

def _ensure_dict(st: dict):
    if not isinstance(st, dict):
        st.clear()
    if "nodes" not in st or not isinstance(st["nodes"], dict):
        st["nodes"] = {}
    if "edges" not in st or not isinstance(st["edges"], dict):
        st["edges"] = {}
    if "meta" not in st or not isinstance(st["meta"], dict):
        st["meta"] = {}

def load_state() -> dict:
    st = _read_json(STATE, {})
    if not isinstance(st, dict):
        st = {}
    _ensure_dict(st)
    return st

def save_state(st: dict) -> None:
    _ensure_dict(st)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")

def ensure_node(st: dict, key: str) -> None:
    _ensure_dict(st)
    node_type = key.split(":", 1)[0] if ":" in key else "Node"
    st["nodes"].setdefault(key, {"type": node_type})

def get_edge(st: dict, a: str, b: str) -> dict:
    _ensure_dict(st)
    ensure_node(st, a)
    ensure_node(st, b)
    k = _edge_key(a, b)
    return st["edges"].setdefault(k, {
        "trust": 0.50, "rapport": 0.50, "influence": 0.50,
        "last_intents": {}  # intent -> unix_ts
    })

def decay_all(st: dict, weeks: float, rate: float) -> None:
    _ensure_dict(st)
    for e in st["edges"].values():
        # simple multiplicative decay toward 0.5 (neutral)
        for key in ("trust", "rapport", "influence"):
            val = e.get(key, 0.5)
            drift = (0.5 - val) * (rate * weeks)
            e[key] = _clamp(val + drift)

def _apply_intent(edge: dict, intent: str, cfg: dict) -> None:
    delta = cfg.get("intents", {}).get(intent, {})
    edge["trust"] = _clamp(edge.get("trust", 0.5) + float(delta.get("d_trust", 0.0)))
    edge["rapport"] = _clamp(edge.get("rapport", 0.5) + float(delta.get("d_rapport", 0.0)))
    edge["influence"] = _clamp(edge.get("influence", 0.5) + float(delta.get("d_influence", 0.0)))

def interact(st: dict, actor: str, target: str, intent: str) -> Tuple[dict, dict]:
    """
    Applies the intent with cooldown protection.
    Returns (edge, result_block) where result_block has ok/because/remaining fields.
    """
    _ensure_dict(st)
    cfg = _load_config()

    e = get_edge(st, actor, target)

    # Cooldown check
    cd_hours = float(cfg.get("cooldowns_hours", {}).get(intent, 0))
    now = _now()
    last = float(e.get("last_intents", {}).get(intent, 0))
    remaining = (cd_hours * 3600) - (now - last)
    if cd_hours > 0 and remaining > 0:
        return e, {
            "ok": False,
            "because": "cooldown",
            "remaining_seconds": remaining,
            "cooldown_hours": cd_hours
        }

    # Apply effect deltas
    _apply_intent(e, intent, cfg)

    # Stamp last time for this intent
    e["last_intents"][intent] = now

    return e, {"ok": True}

# Convenience: seeding used by CLI autoseed
def seed_from_config(st: dict) -> None:
    cfg = _load_config()
    for n in cfg.get("seed", {}).get("nodes", []):
        ensure_node(st, n)
    for a, b in cfg.get("seed", {}).get("edges", []):
        get_edge(st, a, b)
