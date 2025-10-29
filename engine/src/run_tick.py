# src/run_tick.py — College AD v17.7 (back-compat with v17.5)
# Finance/Prestige/Sentiment logging, REG + trait pass, plus v17_7 donor+pledge hooks.
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import List, Dict, Any, Optional, Callable
import json, random, csv, os

# ---------------------------
# Local engine imports (relative to engine/src)
# ---------------------------
from .reg_engine import advance_reg_tick            # existing
from .engine import advance_week_trait_engine      # existing

# ---------------------------
# Unified workspace root (two levels up from engine/src)
# ---------------------------
ROOT = Path(__file__).resolve().parents[2]

# ---------------------------
# ENV (.env at workspace root)
# ---------------------------
ENV: Dict[str, str] = {}
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            ENV[k.strip()] = v.strip()

LOG_DIR    = (ROOT / ENV.get("LOG_DIR", "logs")).resolve()
CONFIG_DIR = (ROOT / ENV.get("CONFIG_DIR", "configs")).resolve()
DOCS_DIR   = (ROOT / ENV.get("DOCS_DIR", "docs")).resolve()
DATA_DIR   = (ROOT / ENV.get("DATA_DIR", "data")).resolve()
LOG_DIR.mkdir(parents=True, exist_ok=True)

WORLD_EVENTS_LOG   = LOG_DIR / "WORLD_EVENTS_LOG.csv"
TRAIT_HISTORY_LOG  = LOG_DIR / "TRAIT_HISTORY_LOG.csv"
FINANCE_LOG        = LOG_DIR / "FINANCE_LOG.csv"

# ---------------------------
# Optional v17_7 modules (loaded lazily, safe no-ops if missing)
# ---------------------------
def _noop(*args, **kwargs):  # type: ignore
    return None

def _load_tick_fn() -> Dict[str, Callable]:
    """
    Attempts to import:
      - v17_7.donor_memory.tick_update
      - v17_7.pledge_stipulations.tick_update (or v17_7.stipulation_tracker.tick_update)
      - v17_7.communication_bridge (optional: emit on tick end)
    Returns a dict of callables; missing entries are no-ops.
    """
    fns: Dict[str, Callable] = {"donor_memory": _noop, "pledge": _noop, "bridge_emit": _noop}
    try:
        from .v17_7.donor_memory import tick_update as donor_tick
        fns["donor_memory"] = donor_tick
    except Exception:
        pass

    # support both names for early builds
    try:
        from .v17_7.pledge_stipulations import tick_update as pledge_tick
        fns["pledge"] = pledge_tick
    except Exception:
        try:
            from .v17_7.stipulation_tracker import tick_update as pledge_tick_alt
            fns["pledge"] = pledge_tick_alt
        except Exception:
            pass

    # optional bridge: prefer function named emit_message_packets; fallback to selftest emitter
    try:
        from .v17_7 import communication_bridge as _bridge
        if hasattr(_bridge, "emit_message_packets"):
            fns["bridge_emit"] = getattr(_bridge, "emit_message_packets")
        elif hasattr(_bridge, "selftest_emit_samples"):
            fns["bridge_emit"] = getattr(_bridge, "selftest_emit_samples")
    except Exception:
        pass

    return fns

_FN = _load_tick_fn()

# ---------------------------
# v17.5 Finance schema seeding (safe defaults)
# ---------------------------
def _seed_finance_defaults_for_school(s: dict) -> None:
    s.setdefault("finance", {})
    fin = s["finance"]
    fin.setdefault("balance", 0.0)
    fin.setdefault("expenses_week", 0.0)
    # scratch area is cleared every tick; safe if it lingers
    fin.setdefault("_tick", {})
    fin["_tick"].setdefault("donor_yield", 0.0)

    # prestige and sentiment scaffolding
    s.setdefault("prestige", 0.0)
    fin.setdefault("prestige_last", float(s["prestige"]))
    s.setdefault("sentiment", 0.0)  # -1.0..+1.0

def seed_finance_defaults(world: dict) -> None:
    for school in world.get("schools", []):
        _seed_finance_defaults_for_school(school)

# ---------------------------
# REG catalog loader (robust search)
# ---------------------------
def _first_existing(paths: List[Path]) -> Optional[Path]:
    for p in paths:
        if p and p.exists():
            return p
    return None

def load_reg_catalog() -> List[Dict[str, Any]]:
    """
    Reads reg_catalog.json with robust lookup order:
      1) ENV['REG_CATALOG_PATH'] if provided
      2) <workspace>/configs/reg_catalog.json
      3) <workspace>/engine/config/reg_catalog.json
    Accepts shapes:
      - {"version": "...", "events": [ {...}, {...} ]}
      - [ {...}, {...} ]
    """
    env_override = ENV.get("REG_CATALOG_PATH")
    candidates = [
        Path(env_override) if env_override else None,
        CONFIG_DIR / "reg_catalog.json",
        ROOT / "engine" / "config" / "reg_catalog.json",
    ]
    p = _first_existing([c for c in candidates if c is not None])
    if not p:
        raise FileNotFoundError("[run_tick] reg_catalog.json not found in configs/ or engine/config/ (or ENV override)")

    raw = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        evs = raw.get("events", [])
    elif isinstance(raw, list):
        evs = raw
    else:
        raise RuntimeError(f"[run_tick] Unsupported reg_catalog shape in {p}: {type(raw).__name__}")

    if not isinstance(evs, list):
        raise RuntimeError(f"[run_tick] 'events' must be a list in {p}")

    return [e for e in evs if isinstance(e, dict)]

# ---------------------------
# Coach wrappers (top-level only)
# ---------------------------
def _coach_to_obj(c: Dict[str, Any]) -> SimpleNamespace:
    ns = SimpleNamespace()
    for k, v in c.items():
        setattr(ns, k, v)
    return ns

def _coaches_to_obj_list(coaches):
    return [_coach_to_obj(c) if isinstance(c, dict) else c for c in coaches]

def _coach_to_plain(ns: SimpleNamespace) -> Dict[str, Any]:
    return dict(ns.__dict__) if isinstance(ns, SimpleNamespace) else ns

def _coaches_to_plain_list(coaches_obj):
    return [_coach_to_plain(c) for c in coaches_obj]

# ---------------------------
# CSV logging helpers
# ---------------------------
from pathlib import Path as _P
_WORLD_EVENTS_HEADER = "week,event_id,intensity,target,effect,notes\n"
_FINANCE_HEADER = ["week","school","donor_yield","expenses","balance","prestige_change","sentiment"]

def _ensure_world_events_with_header(path: _P):
    if not path.exists():
        path.write_text(_WORLD_EVENTS_HEADER, encoding="utf-8", newline="")

def _append_world_events_csv(events, csv_path: _P, default_week: Optional[int]):
    _ensure_world_events_with_header(csv_path)
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        for ev in events or ():
            week   = ev.get("week", default_week)
            eid    = ev.get("event_id", ev.get("id",""))
            inten  = ev.get("intensity", ev.get("impact",""))
            target = ev.get("target") or ev.get("targets") or ev.get("coach") or ev.get("school") or ""
            effect = ev.get("effect") or ev.get("delta") or ev.get("result") or ""
            notes  = ev.get("notes") or ev.get("summary") or ev.get("description") or ""

            def _san(v):
                if v is None: return ""
                # Commas -> semicolons to keep CSV shape stable
                return str(v).replace("\n"," ").replace("\r"," ").replace(",",";")
            f.write(f"{_san(week)},{_san(eid)},{_san(inten)},{_san(target)},{_san(effect)},{_san(notes)}\n")

def _append_finance_row(row: Dict[str, Any], path: _P = FINANCE_LOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=_FINANCE_HEADER)
        if not exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in _FINANCE_HEADER})

# ---------------------------
# Sentiment helpers (v17.5)
# ---------------------------
def _clamp(x: float, lo: float, hi: float) -> float:
    return hi if x > hi else lo if x < lo else x

def _sentiment_next(prev_sentiment: float, d_prestige: float,
                     donor_yield: float, donor_norm_div: float,
                     media_heat_factor: float) -> float:
    donor_norm = donor_yield / (donor_norm_div or 100_000.0)
    nxt = prev_sentiment + (0.1 * d_prestige) + (0.05 * donor_norm) - (0.1 * media_heat_factor)
    return _clamp(nxt, -1.0, 1.0)

# ---------------------------
# Main tick
# ---------------------------
def run_one_tick(coaches, world, cfg, G, ANCH, CTX, week, rng=None, log_csv_path=None):
    rng = rng or random.Random()
    reg_catalog = load_reg_catalog()

    # v17.5: ensure world has safe finance scaffolding
    seed_finance_defaults(world)

    # v17.7: run donor memory decay + pledge stipulations early in the tick
    try:
        _FN["donor_memory"](world=world, cfg=cfg, G=G, week=week, rng=rng)  # type: ignore[arg-type]
    except Exception:
        # keep sim going if module not present or raises
        pass
    try:
        _FN["pledge"](world=world, cfg=cfg, G=G, week=week, rng=rng)  # type: ignore[arg-type]
    except Exception:
        pass

    # Coaches to objects → REG + Traits
    coaches_obj = _coaches_to_obj_list(coaches)
    events = advance_reg_tick(coaches_obj, world, cfg, reg_catalog, rng, week)
    for c in coaches_obj:
        _pre, _post, _delta, _active = advance_week_trait_engine(c, cfg, G, ANCH, CTX, week)

    # Flush coaches back to plain dicts
    coaches[:] = _coaches_to_plain_list(coaches_obj)

    # Log world events
    csv_path = Path(log_csv_path) if log_csv_path else WORLD_EVENTS_LOG
    _append_world_events_csv(events, csv_path, default_week=week)

    # v17.5: passive finance snapshot per school (non-breaking if inputs are missing)
    media_heat_default = 0.0
    donor_norm_div_default = 100_000.0

    for school in world.get("schools", []):
        name = school.get("name", "UNKNOWN")

        fin = school.get("finance", {})
        tick = fin.get("_tick", {})

        donor_yield = float(tick.get("donor_yield", 0.0))
        expenses = float(fin.get("expenses_week", 0.0))

        prestige_now = float(school.get("prestige", 0.0))
        prestige_last = float(fin.get("prestige_last", prestige_now))
        d_prestige = prestige_now - prestige_last

        media_heat = float(school.get("media_heat", media_heat_default))
        sentiment_prev = float(school.get("sentiment", 0.0))

        sentiment_new = _sentiment_next(
            prev_sentiment=sentiment_prev,
            d_prestige=d_prestige,
            donor_yield=donor_yield,
            donor_norm_div=donor_norm_div_default,
            media_heat_factor=media_heat
        )

        balance_prev = float(fin.get("balance", 0.0))
        balance_new = balance_prev + donor_yield - expenses

        # commit back to world
        school["sentiment"] = sentiment_new
        fin["balance"] = balance_new
        fin["prestige_last"] = prestige_now
        fin["expenses_week"] = 0.0      # reset for next tick
        tick["donor_yield"] = 0.0       # clear scratch
        school["finance"] = fin         # ensure reference kept if it was missing

        # write a finance log row
        _append_finance_row({
            "week": week,
            "school": name,
            "donor_yield": round(donor_yield, 2),
            "expenses": round(expenses, 2),
            "balance": round(balance_new, 2),
            "prestige_change": round(d_prestige, 3),
            "sentiment": round(sentiment_new, 3),
        })

    # Optional: emit message packets via v17_7 communication bridge
    try:
        # prefer workspace logs/INBOX; fallback to engine/logs/INBOX if desired
        out_dir = ROOT / ENV.get("INBOX_DIR", "engine/logs/INBOX")
        # 🔥 FIX: Correctly indented the directory creation inside the try block
        out_dir.mkdir(parents=True, exist_ok=True)
        _FN["bridge_emit"](events=events, world=world, week=week, out_dir=str(out_dir))  # type: ignore[call-arg]
    except Exception:
        pass

    return events