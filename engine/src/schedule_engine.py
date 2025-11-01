from __future__ import annotations
import json, uuid
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parents[1]   # engine/
CONFIG = ROOT / "config" / "schedule.config.json"
STATE  = ROOT / "state"  / "schedule.json"
DOCS   = ROOT.parent / "docs"            # workspace/docs

def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def _write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")

def _today_str():
    st = _read_json(STATE, {})
    return st.get("today") or date.today().isoformat()

def load_config():
    cfg = _read_json(CONFIG, {})
    cfg.setdefault("day_hours", 8)
    cfg.setdefault("overtime_hours", 0)
    cfg.setdefault("overtime_penalty", 0.0)
    cfg.setdefault("reschedule_penalty_base", 0.10)
    cfg.setdefault("reschedule_priority_multipliers", {"normal": 1.0})
    cfg.setdefault("relationship_penalty_scale", 0.5)
    cfg.setdefault("action_time_costs", {})
    return cfg

def load_state():
    st = _read_json(STATE, {})
    if "days" not in st:
        st["days"] = {}
    if "today" not in st:
        st["today"] = _today_str()
    return st

def save_state(st):
    _write_json(STATE, st)

def ensure_day(st, day:str):
    cfg = load_config()
    return st["days"].setdefault(day, {
        "hours_used": 0.0,
        "hours_budget": float(cfg["day_hours"]),
        "overtime_hours": float(cfg.get("overtime_hours", 0)),
        "actions": []
    })

def available_hours(st, day:str):
    d = ensure_day(st, day)
    return max(0.0, d["hours_budget"] + d["overtime_hours"] - d["hours_used"])

def _time_cost(action_type:str):
    cfg = load_config()
    return float(cfg["action_time_costs"].get(action_type, 1.0))

def reserve_action(action_type:str, when:str|None=None, hours:float|None=None,
                   title:str|None=None, priority:str="normal",
                   actor:str|None=None, target:str|None=None, meta:dict|None=None):
    cfg = load_config()
    st = load_state()
    day = when or st["today"]
    ensure_day(st, day)

    cost = float(hours) if hours is not None else _time_cost(action_type)
    avail = available_hours(st, day)

    info = {
        "id": str(uuid.uuid4()),
        "day": day,
        "action_type": action_type,
        "title": title or action_type.replace("_"," ").title(),
        "hours": cost,
        "priority": priority,
        "actor": actor, "target": target,
        "meta": meta or {},
        "status": "scheduled"
    }

    if cost <= avail:
        st["days"][day]["actions"].append(info)
        st["days"][day]["hours_used"] += cost
        save_state(st)
        return True, info
    else:
        info["status"] = "insufficient_time"
        info["available"] = avail
        info["needed"] = cost
        return False, info

def reschedule(action_id:str, new_day:str):
    cfg = load_config()
    st = load_state()

    where = None
    for d, rec in st["days"].items():
        for a in rec.get("actions", []):
            if a["id"] == action_id:
                where = (d, a)
                break
        if where: break
    if not where:
        return False, {"error":"not_found"}

    old_day, act = where
    st["days"][old_day]["hours_used"] -= float(act["hours"])
    st["days"][old_day]["actions"] = [x for x in st["days"][old_day]["actions"] if x["id"] != action_id]

    ensure_day(st, new_day)
    avail = available_hours(st, new_day)
    if act["hours"] > avail:
        st["days"][old_day]["actions"].append(act)
        st["days"][old_day]["hours_used"] += float(act["hours"])
        return False, {"error":"insufficient_time_on_target_day", "available":avail}

    base = float(cfg["reschedule_penalty_base"])
    mult = float(cfg["reschedule_priority_multipliers"].get(act.get("priority","normal"), 1.0))
    opp_loss = base * mult
    applied = False
    try:
        from engine.src.relationship_engine import load_state as rl_load, save_state as rl_save, get_edge, ensure_node
        rst = rl_load()
        if act.get("actor") and act.get("target"):
            ensure_node(rst, act["actor"])
            ensure_node(rst, act["target"])
            e = get_edge(rst, act["actor"], act["target"])
            scale = float(cfg["relationship_penalty_scale"])
            e["rapport"] = max(0.0, e["rapport"] * (1.0 - opp_loss*scale))
            e["trust"]   = max(0.0, e["trust"]   * (1.0 - opp_loss*scale*0.3))
            rl_save(rst)
            applied = True
    except Exception:
        applied = False

    act["day"] = new_day
    act["status"] = "rescheduled"
    st["days"][new_day]["actions"].append(act)
    st["days"][new_day]["hours_used"] += float(act["hours"])
    save_state(st)

    return True, {
        "moved_from": old_day, "moved_to": new_day,
        "opportunity_loss": opp_loss,
        "relationship_penalty_applied": applied
    }

def advance_day(days:int=1):
    st = load_state()
    base = date.fromisoformat(st["today"])
    base += timedelta(days=days)
    st["today"] = base.isoformat()
    ensure_day(st, st["today"])
    save_state(st)
    return st["today"]

def write_report():
    st = load_state()
    lines = ["# Schedule — latest", "", f"**Today:** {st['today']}", ""]
    days_sorted = sorted(st["days"].keys())
    for d in days_sorted[-7:]:
        rec = st["days"][d]
        total = rec["hours_budget"] + rec.get("overtime_hours",0)
        lines.append(f"## {d}  (used {rec['hours_used']:.1f}/{total:.1f})")
        if not rec["actions"]:
            lines.append("- (no actions)")
        else:
            lines.append("| Time | Priority | Type | Title | Actor | Target | Status |")
            lines.append("|---:|:--:|---|---|---|---|---|")
            for a in rec["actions"]:
                lines.append(f"| {a['hours']:.1f} | {a.get('priority','')} | {a['action_type']} | {a['title']} | {a.get('actor','')} | {a.get('target','')} | {a['status']} |")
        lines.append("")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "SCHEDULE.md").write_text("\n".join(lines), encoding="utf-8")
    return str(DOCS / "SCHEDULE.md")

