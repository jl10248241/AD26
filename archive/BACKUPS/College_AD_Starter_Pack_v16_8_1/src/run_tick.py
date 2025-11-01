# src/run_tick.py
from pathlib import Path
from types import SimpleNamespace
import json, random

from reg_engine import advance_reg_tick
from engine import advance_week_trait_engine


# ---------------------------
# Catalog loader (robust to CWD)
# ---------------------------
def load_reg_catalog() -> list:
    # Resolve relative to project root (parent of this file's folder)
    root = Path(__file__).resolve().parents[1]
    p = root / "config" / "reg_catalog.json"
    if not p.exists():
        raise FileNotFoundError(f"reg_catalog not found at {p.resolve()}")
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------
# Coach wrappers
# ---------------------------
def _coach_to_obj(c: dict) -> SimpleNamespace:
    """
    Wrap ONLY the top-level coach dict so engines can set attributes.
    Keep nested structures (traits, subtraits, etc.) as plain dict/list.
    """
    ns = SimpleNamespace()
    for k, v in c.items():
        setattr(ns, k, v)  # no recursive conversion
    return ns

def _coaches_to_obj_list(coaches):
    return [_coach_to_obj(c) if isinstance(c, dict) else c for c in coaches]

def _coach_to_plain(ns: SimpleNamespace) -> dict:
    # Return a plain dict version of the top-level coach object
    # (nested items were left as dict/list already)
    if isinstance(ns, SimpleNamespace):
        return dict(ns.__dict__)
    return ns

def _coaches_to_plain_list(coaches_obj):
    return [_coach_to_plain(c) for c in coaches_obj]


# ---------------------------
# CSV logger (optional)
# ---------------------------
def _append_event_logs_csv(logs, path):
    import os
    header = "week,id,coach,intensity,sentiment,media_heat\n"
    exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if not exists:
            f.write(header)
        for r in logs:
            week = r.get("week", "")
            ev   = r.get("id", "")
            coach= r.get("coach", "")
            inten= r.get("intensity", "")
            sent = r.get("sentiment", 0.0)
            heat = r.get("media_heat", 0.0)
            f.write(f"{week},{ev},{coach},{inten},{sent},{heat}\n")


# ---------------------------
# Main tick
# ---------------------------
def run_one_tick(coaches, world, cfg, G, ANCH, CTX, week, rng=None, log_csv_path=None):
    """
    1) Fire REG events (probability, persistence, cooldowns)
    2) Advance coaches with DBS + gravity (time-step aware)
    NOTE: Only coaches are wrapped (top-level) so engines can set attributes;
          cfg/world/G/ANCH/CTX remain dicts and behave with .get().
    """
    rng = rng or random.Random()
    reg_catalog = load_reg_catalog()

    # Wrap coaches (top-level only)
    coaches_obj = _coaches_to_obj_list(coaches)

    # 1) REG first
    logs = advance_reg_tick(coaches_obj, world, cfg, reg_catalog, rng, week)

    # 2) Trait engine
    for c in coaches_obj:
        pre, post, delta, active = advance_week_trait_engine(c, cfg, G, ANCH, CTX, week)

    # Write back: convert wrapped coaches to plain dicts in place
    coaches[:] = _coaches_to_plain_list(coaches_obj)

    # Optional CSV log
    if log_csv_path:
        _append_event_logs_csv(logs, log_csv_path)

    return logs
a