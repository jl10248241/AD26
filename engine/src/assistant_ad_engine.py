from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# Local deps
from .media_desk import act as media_act, list_media_files, read_media, write_report

WORKSPACE = Path(__file__).resolve().parents[2]
CONFIG    = WORKSPACE / "engine" / "config"
STATE     = WORKSPACE / "engine" / "state"
DOCS      = WORKSPACE / "docs"

CONFIG.mkdir(parents=True, exist_ok=True)
STATE.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)

# ---------- helpers
def _read_json(p: Path, fb: Any=None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return fb

def _write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def policy_path() -> Path:
    return CONFIG / "aad_policies.json"

def load_policies(p: Optional[Path]=None) -> Dict[str, Any]:
    p = p or policy_path()
    pol = _read_json(p, None)
    if not pol:
        pol = {
            "aad_name": "Assistant AD",
            "max_daily_actions": 2,
            "hours_per_action": 1.0,
            "amplify_threshold": 0.50,   # >= sentiment → amplify
            "downplay_threshold": -0.50, # <= sentiment → downplay
            "ignore_window": [-0.10, 0.10],  # near neutral → ignore
            "allow": ["media.amplify", "media.downplay", "media.ignore"]
        }
        _write_json(p, pol)
    return pol

def save_policies(policies: Dict[str, Any], p: Optional[Path]=None) -> None:
    p = p or policy_path()
    _write_json(p, policies)

def _schedule_state_path() -> Path:
    return STATE / "schedule_state.json"

def _load_schedule_state() -> Dict[str, Any]:
    st = _read_json(_schedule_state_path(), {})
    # ensure shape
    st.setdefault("timebank", {})
    st["timebank"].setdefault("ad", 8.0)
    st["timebank"].setdefault("aad", 0.0)  # default 0 so you must top up
    return st

def _save_schedule_state(st: Dict[str, Any]) -> None:
    _write_json(_schedule_state_path(), st)

def run_once(policies: Optional[Dict[str, Any]]=None) -> Dict[str, Any]:
    pol = policies or load_policies()
    st  = _load_schedule_state()

    hours_per_action = float(pol.get("hours_per_action", 1.0))
    max_actions      = int(pol.get("max_daily_actions", 2))

    # AAD hours gate
    avail = float(st["timebank"].get("aad", 0.0))
    if avail < hours_per_action:
        return {"status": "no_hours", "aad_hours": avail}

    files = list_media_files()
    if not files:
        return {"status": "no_media"}

    amp_thr = float(pol.get("amplify_threshold", 0.5))
    dwn_thr = float(pol.get("downplay_threshold", -0.5))
    ign_lo, ign_hi = pol.get("ignore_window", [-0.10, 0.10])

    actions_done: List[Dict[str, Any]] = []
    remaining   = min(max_actions, int(avail // hours_per_action))

    for pth in files:
        if remaining <= 0:
            break
        m = read_media(pth)
        s = float(m.get("sentiment", 0.0))

        decision = None
        if "media.amplify" in pol.get("allow", []) and s >= amp_thr:
            decision = ("amplify", s)
        elif "media.downplay" in pol.get("allow", []) and s <= dwn_thr:
            decision = ("downplay", s)
        elif "media.ignore" in pol.get("allow", []) and ign_lo <= s <= ign_hi:
            decision = ("ignore", s)

        if decision:
            action = decision[0]
            # act on *this* item index (newest-first). Convert file → index.
            # We already have all files newest-first; map file to its 1-based index
            files_now = list_media_files()
            idx = next((i+1 for i, fp in enumerate(files_now) if fp.name == pth.name), None)
            if idx is None:
                continue
            result = media_act(idx, action)
            actions_done.append({"index": idx, "file": result["file"], "action": action,
                                 "sent_before": result["sent_before"], "sent_after": result["sent_after"]})
            # spend hours
            st["timebank"]["aad"] = float(st["timebank"]["aad"]) - hours_per_action
            remaining -= 1

    _save_schedule_state(st)
    # refresh media report (best-effort)
    try:
        write_report(DOCS)
    except Exception:
        pass

    return {
        "status": "ok",
        "actions": actions_done,
        "aad_hours_left": round(float(st["timebank"]["aad"]), 2),
    }
