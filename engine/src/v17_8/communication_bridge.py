# engine/src/v17_7/communication_bridge.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import json, argparse, datetime as dt, random, csv
import uuid

# --- CSV Indexing Logic ---
INDEX_HEADER = ["timestamp", "role", "subject", "urgency", "file"]

def _append_inbox_index(out_dir: str | Path, role: str, subject: str,
                         urgency: str, filename: str) -> None:
    """Append a single row to logs/INBOX/index.csv (creates with header on first use)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = out_dir / "index.csv"
    exists = idx.exists()
    
    # NOTE: Using dt.datetime (imported as dt) for consistency
    ts_iso = dt.datetime.now().isoformat(timespec="seconds") 
    
    with idx.open("a", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=INDEX_HEADER)
        if not exists:
            w.writeheader()
        w.writerow({
            "timestamp": ts_iso,
            "role": role,
            "subject": subject,
            "urgency": urgency,
            "file": str(filename).replace("\\", "/"), # Normalize path separators for CSV reading
        })

# --- Configuration & Heuristics ---
ROOT = Path(__file__).resolve().parents[3]  # .../workspace
ENV: Dict[str, str] = {}
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
                "low":{"score_min":-999.0,"score_max":1.0},
                "normal":{"score_min":1.0,"score_max":3.0},
                "high":{"score_min":3.0,"score_max":6.0},
                "urgent":{"score_min":6.0,"score_max":999.0}
            }
        }
    return json.loads(p.read_text(encoding="utf-8"))

def _score_events(events: List[Dict[str,Any]]) -> float:
    if not events: return 0.0
    w = {"championship":6.0,"rival_win":2.5,"upset_win":2.0,"win":1.0,
          "coach_fire":-2.5,"scandal":-6.0}
    s = 0.0
    for e in events:
        eff = str(e.get("effect","")).lower()
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

# --- Main API ---
def emit_message_packets(events: Optional[List[Dict[str, Any]]] = None,
                         world: Optional[Dict[str, Any]] = None,
                         week: Optional[int] = None,
                         out_dir: str = "logs/INBOX") -> None:
    
    # 1. Setup & Scoring
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    outp = Path(out_dir); outp.mkdir(parents=True, exist_ok=True)
    evs = events or []
    wk  = int(week or -1)

    cfg = _load_bridge_filters()
    thr = cfg.get("urgency_thresholds", {})
    score = _score_events(evs)
    urgency = _bucket(score, thr)

    # 2. World Snapshot
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
        finance = {}

    summary = f"W{wk}: {len(evs)} events, score {score:.1f} ({urgency})"

    # 3. Packet Creation
    aad = _packet("AAD", wk, f"Weekly wrap {summary}", evs, urgency, finance)
    coach = _packet("Coach", wk, f"Weekly briefing {summary}", evs, urgency, finance)
    board = _packet("Board", wk, f"Governance brief {summary}", evs, urgency, finance)

    # 4. Write & Index
    
    # AAD
    aad_filename = f"AAD_{ts}.json"
    (outp / aad_filename).write_text(json.dumps(aad, indent=2), encoding="utf-8")
    _append_inbox_index(outp, aad['role'], aad['subject'], aad['urgency'], aad_filename)
    
    # Coach
    coach_filename = f"Coach_{ts}.json"
    (outp / coach_filename).write_text(json.dumps(coach, indent=2), encoding="utf-8")
    _append_inbox_index(outp, coach['role'], coach['subject'], coach['urgency'], coach_filename)

    # Board
    board_filename = f"Board_{ts}.json"
    (outp / board_filename).write_text(json.dumps(board, indent=2), encoding="utf-8")
    _append_inbox_index(outp, board['role'], board['subject'], board['urgency'], board_filename)

# NOTE: For completeness in a real module, the selftest/CLI components from previous steps 
# should also be present here.