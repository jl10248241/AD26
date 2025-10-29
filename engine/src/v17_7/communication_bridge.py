# engine/src/v17_7/communication_bridge.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
import json, argparse, datetime as dt, random
from dataclasses import dataclass
import uuid # ADDED: Required for _packet unique ID

# --- top of file additions (Integrated & Corrected) ---
# NOTE: Path and json are assumed to be imported from standard library (like the original file)

ROOT = Path(__file__).resolve().parents[3]  # .../workspace
ENV = {}
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1); ENV[k.strip()] = v.strip()

CONFIG_DIR = (ROOT / ENV.get("CONFIG_DIR", "configs")).resolve()

def _load_bridge_filters() -> Dict[str, Any]:
    p = CONFIG_DIR / "bridge_filters.json"
    if not p.exists():
        # resilient defaults if config missing
        return {
            "schema":"v1",
            "urgency_thresholds":{
                "low":{"score_min":-999.0,"score_max":1.0}, # ensure floats
                "normal":{"score_min":1.0,"score_max":3.0},
                "high":{"score_min":3.0,"score_max":6.0},
                "urgent":{"score_min":6.0,"score_max":999.0}
            }
        }
    return json.loads(p.read_text(encoding="utf-8"))

def _score_events(events: List[Dict[str,Any]]) -> float:
    # Simple heuristic: sum mapped intensities; scandals negative spike
    if not events: return 0.0
    w = {"championship":6.0,"rival_win":2.5,"upset_win":2.0,"win":1.0,
          "coach_fire":-2.5,"scandal":-6.0}
    s = 0.0
    for e in events:
        eff = str(e.get("effect","")).lower()
        
        # FIX: Ensure intensity is a float and defaults safely to 1.0
        try:
            inten = float(e.get("intensity") or 1.0)
        except (TypeError, ValueError):
            inten = 1.0
            
        s += (w.get(eff, 0.5) * inten)
    return s

def _bucket(score: float, thresholds: Dict[str, Dict[str,float]]) -> str:
    for name, rng in thresholds.items():
        if rng["score_min"] <= score < rng["score_max"]:
            return name
    return "normal"

def _packet(role:str, week:int, summary:str, events: List[Dict[str, Any]], urgency:str, extra:dict) -> dict:
    return {
        "version":"1.1",
        "id": str(uuid.uuid4()),
        "role": role,
        "week": int(week),
        "urgency": urgency,      # low|normal|high|urgent
        "subject": f"[{role}] {summary}",
        "summary": summary,
        "facts": extra,          # donor / finance / pledges snapshot
        "events": events[:50],
    }
# --- end additions ---

# NOTE: The original file should include:
# from pathlib import Path
# from typing import Any, Dict, List, Optional
# import json, argparse, datetime as dt, random
# ... which the user-provided code assumes.

def emit_message_packets(events: Optional[List[Dict[str, Any]]] = None,
                         world: Optional[Dict[str, Any]] = None,
                         week: Optional[int] = None,
                         out_dir: str = "logs/INBOX") -> None:
    # REVISED: Standardize timestamp format to include underscore for ui_mock compatibility
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    outp = Path(out_dir); outp.mkdir(parents=True, exist_ok=True)
    evs = events or []
    wk  = int(week or -1)

    cfg = _load_bridge_filters()
    thr = cfg.get("urgency_thresholds", {})
    score = _score_events(evs)
    urgency = _bucket(score, thr)

    # pull a tiny world snapshot (safe defaults)
    finance = {}
    try:
        schools = world.get("schools", []) if isinstance(world, dict) else []
        if schools:
            s0 = schools[0]
            fin = s0.get("finance", {})
            finance = {
                "school": s0.get("name","?"),
                "balance": round(float(fin.get("balance",0.0)),2),
                "donor_yield": round(float(fin.get("_tick",{}).get("donor_yield",0.0)),2),
                "sentiment": round(float(s0.get("sentiment",0.0)),3),
                "prestige": round(float(s0.get("prestige",0.0)),3)
            }
    except Exception:
        # In a real system, you might log this error. Here, we just use empty defaults.
        finance = {}

    summary = f"W{wk}: {len(evs)} events, score {score:.1f} ({urgency})"

    aad = _packet("AAD", wk, f"Weekly wrap {summary}", evs, urgency, finance)
    coach = _packet("Coach", wk, f"Weekly briefing {summary}", evs, urgency, finance)
    board = _packet("Board", wk, f"Governance brief {summary}", evs, urgency, finance)

    (outp / f"AAD_{ts}.json").write_text(json.dumps(aad, indent=2), encoding="utf-8")
    (outp / f"Coach_{ts}.json").write_text(json.dumps(coach, indent=2), encoding="utf-8")
    (outp / f"Board_{ts}.json").write_text(json.dumps(board, indent=2), encoding="utf-8")