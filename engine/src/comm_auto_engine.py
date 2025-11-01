from __future__ import annotations
from pathlib import Path
import json, datetime as dt, uuid

# ---- Schedule compat shim -----------------------------------------------
from . import schedule_engine as _SE  # import the module, then adapt

# required handles from schedule_engine
load_sched = _SE.load_state
save_sched = _SE.save_state
today_str  = getattr(_SE, "today_str", lambda: dt.datetime.utcnow().date().isoformat())

def reserve_block(sched: dict, *, when: str, hours: float, priority: str,
                  type: str, title: str, actor: str, target: str):
    # Prefer native reserve_block if present
    if hasattr(_SE, "reserve_block"):
        return _SE.reserve_block(
            sched, when=when, hours=hours, priority=priority,
            type=type, title=title, actor=actor, target=target
        )

    # Fallback: write a minimal block into schedule state
    days = sched.setdefault("days", {})
    day  = days.setdefault(when, {"used": 0.0})

    # normalize container key (support either 'blocks' or 'items')
    key  = "blocks" if "blocks" in day else ("items" if "items" in day else "blocks")
    if key not in day:
        day[key] = []

    cap  = float(sched.get("daily_cap_hours", 8.0))
    used = float(day.get("used", 0.0))
    hours = float(hours)

    if used + hours > cap:
        return (False, None)

    blk = {
        "id": str(uuid.uuid4()),
        "hours": hours,
        "priority": priority,
        "type": type,
        "title": title,
        "actor": actor,
        "target": target,
        "status": "scheduled",
    }
    day[key].append(blk)
    day["used"] = used + hours
    return (True, blk)
# --------------------------------------------------------------------------

ROOT    = Path(__file__).resolve().parents[2]
LOGS    = ROOT / "logs"
MEDIA   = LOGS / "MEDIA"
CFG     = ROOT / "engine" / "config" / "comm_auto.policy.json"

def _read_json(p: Path, default=None):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return default if default is not None else {}

def _write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def load_policy() -> dict:
    pol = _read_json(CFG, {})
    if not pol:
        pol = {
            "aad_name": "Assistant AD",
            "actor": "AAD:1",
            "max_daily_actions": 2,
            "hours_per_action": 0.5,
            "amplify_threshold": 0.50,
            "downplay_threshold": -0.40,
            "ignore_window": [-0.10, 0.10],
            "allow": ["media.amplify","media.downplay","media.ignore"],
            "sentiment_boosts": {
                "amplify": {"Local":0.02,"Regional":0.03,"National":0.05},
                "downplay":{"Local":0.02,"Regional":0.02,"National":0.03}
            },
            "relationship_targets": {
                "Local":"Media:Local Beat","Regional":"Media:Regional","National":"Media:National"
            },
            "schedule_type_map": {"amplify":"comms_media","downplay":"comms_media","ignore":"comms_triage"}
        }
    return pol

def save_policy(pol: dict) -> None: _write_json(CFG, pol)

def _media_files():
    if not MEDIA.exists(): return []
    return sorted(MEDIA.glob("*.media.json"), key=lambda p: p.stat().st_mtime, reverse=True)

def _read_media(p: Path) -> dict: return _read_json(p, {})
def _write_media(p: Path, obj: dict) -> None: _write_json(p, obj)
def _clamp(x, lo, hi): return max(lo, min(hi, x))

def decide_action(item: dict, pol: dict):
    if item.get("status","new") != "new": return None
    s  = float(item.get("sentiment", 0.0))
    lo, hi = pol.get("ignore_window", [-0.10, 0.10])
    if lo <= s <= hi and "media.ignore" in pol.get("allow",[]): return "ignore"
    if s >= pol.get("amplify_threshold", 0.5) and "media.amplify" in pol.get("allow",[]): return "amplify"
    if s <= pol.get("downplay_threshold", -0.4) and "media.downplay" in pol.get("allow",[]): return "downplay"
    return None

def apply_action(item: dict, action: str, pol: dict) -> dict:
    reach  = item.get("source","Local")
    boosts = pol.get("sentiment_boosts", {})
    if action == "amplify":
        bump = boosts.get("amplify", {}).get(reach, 0.0)
        item["sentiment"] = _clamp(float(item.get("sentiment",0.0)) + bump, -1.0, 1.0)
    elif action == "downplay":
        bump = boosts.get("downplay", {}).get(reach, 0.0)
        s = float(item.get("sentiment",0.0))
        if s < 0: s = min(0.0, s + bump)
        item["sentiment"] = _clamp(s, -1.0, 1.0)
    item["status"] = action
    item.setdefault("history", []).append({
        "when": dt.datetime.utcnow().isoformat(timespec="seconds")+"Z",
        "by": pol.get("actor","AAD:1"),
        "action": action
    })
    return item

def spend_time(pol: dict, action: str, title: str, target: str) -> bool:
    sched = load_sched()
    hours = float(pol.get("hours_per_action", 0.5))
    typ   = pol.get("schedule_type_map",{}).get(action, "comms_triage")
    actor = pol.get("actor","AAD:1")
    ok, _ = reserve_block(sched, when=today_str(), hours=hours, priority="normal",
                          type=typ, title=title, actor=actor, target=target)
    if ok: save_sched(sched)
    return ok

from .relationship_engine import load_state as load_rel, save_state as save_rel, ensure_node, interact
def touch_relationships(pol: dict, reach: str, action: str):
    rel = load_rel()
    src = pol.get("actor","AAD:1")
    tgt = pol.get("relationship_targets",{}).get(reach, "Media:Local Beat")
    ensure_node(rel, src); ensure_node(rel, tgt)
    intent_map = {"amplify":"amplify_story","downplay":"downplay_story","ignore":"ignore_story"}
    interact(rel, src, tgt, intent_map.get(action,"ignore_story"))
    save_rel(rel)

def run_once() -> dict:
    pol = load_policy()
    acted, out = 0, []
    for p in _media_files():
        if acted >= int(pol.get("max_daily_actions",2)): break
        item = _read_media(p)
        action = decide_action(item, pol)
        if not action: continue
        reach  = item.get("source","Local")
        title  = item.get("title","(untitled)")
        target = pol.get("relationship_targets",{}).get(reach, "Media:Local Beat")
        if not spend_time(pol, action, title, target):
            out.append({"file": p.name, "result": "no_hours"}); break
        apply_action(item, action, pol); _write_media(p, item)
        touch_relationships(pol, reach, action)
        acted += 1
        out.append({"file": p.name, "action": action, "sentiment": item.get("sentiment",0.0), "reach": reach})
    return {"acted": acted, "details": out}
