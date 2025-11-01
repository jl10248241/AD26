# src/run_tick.py — College AD v17.5
# Finance/Prestige/Sentiment logging (backward-compatible), plus REG + trait pass
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
from typing import List, Dict, Any, Optional
import json, random, csv

from .reg_engine import advance_reg_tick     # relative imports
from .engine import advance_week_trait_engine

# ---- Unified workspace root (two levels up from engine/src)
ROOT = Path(__file__).resolve().parents[2]

ENV: Dict[str, str] = {}
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1); ENV[k.strip()] = v.strip()

LOG_DIR     = (ROOT / ENV.get("LOG_DIR", "logs")).resolve()
CONFIG_DIR  = (ROOT / ENV.get("CONFIG_DIR", "configs")).resolve()
DOCS_DIR    = (ROOT / ENV.get("DOCS_DIR", "docs")).resolve()
DATA_DIR    = (ROOT / ENV.get("DATA_DIR", "data")).resolve()
LOG_DIR.mkdir(parents=True, exist_ok=True)

WORLD_EVENTS_LOG = LOG_DIR / "WORLD_EVENTS_LOG.csv"
TRAIT_HISTORY_LOG = LOG_DIR / "TRAIT_HISTORY_LOG.csv"
FINANCE_LOG = LOG_DIR / "FINANCE_LOG.csv"

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
# REG catalog loader (normalized)
# ---------------------------
def load_reg_catalog() -> List[Dict[str, Any]]:
    """
    Reads <workspace>/configs/reg_catalog.json and normalizes to a List[Dict].
    Accepts either:
      - {"version": "...", "events": [ {...}, {...} ]}
      - [ {...}, {...} ]
    """
    p = CONFIG_DIR / "reg_catalog.json"
    if not p.exists():
        raise FileNotFoundError(f"[run_tick] reg_catalog not found at {p}")

    raw = json.loads(p.read_text(encoding="utf-8"))

    # if wrapped inside a dict, pull "events"
    if isinstance(raw, dict):
        evs = raw.get("events", [])
    elif isinstance(raw, list):
        evs = raw
    else:
        raise RuntimeError(f"[run_tick] Unsupported reg_catalog shape in {p}: {type(raw).__name__}")

    if not isinstance(evs, list):
        raise RuntimeError(f"[run_tick] 'events' must be a list in {p}")

    # ensure every event is a dict
    out: List[Dict[str, Any]] = []
    for e in evs:
        if isinstance(e, dict):
            out.append(e)
        else:
            # skip bad rows but keep going
            continue

    return out

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
    if not path.exists(): path.write_text(_WORLD_EVENTS_HEADER, encoding="utf-8")

def _append_world_events_csv(events, csv_path: _P, default_week: Optional[int]):
    _ensure_world_events_with_header(csv_path)
    with csv_path.open("a", encoding="utf-8") as f:
        for ev in events:
            week  = ev.get("week", default_week)
            eid   = ev.get("event_id", ev.get("id",""))
            inten = ev.get("intensity", ev.get("impact",""))
            target = ev.get("target") or ev.get("targets") or ev.get("coach") or ev.get("school") or ""
            effect = ev.get("effect") or ev.get("delta") or ev.get("result") or ""
            notes  = ev.get("notes") or ev.get("summary") or ev.get("description") or ""
            # sanitize inline
            def _san(v):
                if v is None: return ""
                return str(v).replace("\n"," ").replace("\r"," ").replace(",",";")
            f.write(f"{_san(week)},{_san(eid)},{_san(inten)},{_san(target)},{_san(effect)},{_san(notes)}\n")

def _append_finance_row(row: Dict[str, Any], path: _P = FINANCE_LOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=_FINANCE_HEADER)
        if not exists:
            w.writeheader()
        # only known keys → avoids schema drift
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

    coaches_obj = _coaches_to_obj_list(coaches)

    # REG + Traits as before
    events = advance_reg_tick(coaches_obj, world, cfg, reg_catalog, rng, week)
    for c in coaches_obj:
        _pre, _post, _delta, _active = advance_week_trait_engine(c, cfg, G, ANCH, CTX, week)

    coaches[:] = _coaches_to_plain_list(coaches_obj)

    # Log events (existing behavior)
    csv_path = Path(log_csv_path) if log_csv_path else WORLD_EVENTS_LOG
    _append_world_events_csv(events, csv_path, default_week=week)

    # v17.5: passive finance snapshot per school (non-breaking if inputs are missing)
    media_heat_default = 0.0
    donor_norm_div_default = 100_000.0

    for school in world.get("schools", []):
        name = school.get("name", "UNKNOWN")

        fin = school["finance"]
        tick = fin["_tick"]

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
        fin["expenses_week"] = 0.0     # reset for next tick
        tick["donor_yield"] = 0.0      # clear scratch

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

    return events
