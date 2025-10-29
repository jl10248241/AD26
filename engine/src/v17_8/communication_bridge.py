# engine/src/v17_X/communication_bridge.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json, argparse, datetime as dt, random, csv, uuid, os

# ---------------------------
# Environment & Config roots
# ---------------------------
ROOT = Path(__file__).resolve().parents[3]
ENV: Dict[str, str] = {}
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1); ENV[k.strip()] = v.strip()

# Canonical defaults (match validator)
CONFIG_DIR = (ROOT / ENV.get("CONFIG_DIR", "engine/config")).resolve()

# ---------------------------
# Urgency helpers (v17.8)
# ---------------------------
def _derive_urgency(pkt: Dict[str, Any]) -> str:
    """
    Return INFO/WARN/URGENT.
    Rule of thumb:
      1) trust explicit fields first (derived_urgency, urgency)
      2) then infer from keywords in subject/summary/body
    """
    explicit = str(pkt.get("derived_urgency", "") or pkt.get("urgency", "")).upper()
    if explicit in ("URGENT", "WARN", "INFO"):
        return explicit

    # Allow loose buckets if provided (low/normal/high/urgent)
    if explicit in ("URGENT", "HIGH"):
        return "URGENT"
    if explicit in ("NORMAL", "LOW"):
        return "INFO"

    subj = (pkt.get("subject") or "").lower()
    # packets in this bridge commonly use "summary" instead of "body"
    body = (pkt.get("summary") or pkt.get("body") or "").lower()
    text = subj + " " + body

    if any(k in text for k in ("deadline", "violation", "crisis", "incident", "terminate", "suspension", "scandal")):
        return "URGENT"
    if any(k in text for k in ("reminder", "escalate", "overdue", "concern", "flag")):
        return "WARN"
    return "INFO"

_BADGE = {"INFO": "[ ]", "WARN": "[!]", "URGENT": "[!!!]"}

# ---------------------------
# CSV index helpers
# ---------------------------
INDEX_HEADER = ["timestamp", "role", "subject", "urgency", "file"]

def _append_inbox_index(out_dir: str | Path, role: str, subject: str,
                        urgency: str, filename: str) -> None:
    """Append a single row to logs/INBOX/index.csv (creates with header on first use)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = out_dir / "index.csv"
    exists = idx.exists()
    with idx.open("a", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=INDEX_HEADER)
        if not exists:
            w.writeheader()
        w.writerow({
            "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            "role": role,
            "subject": subject,
            "urgency": urgency,
            "file": str(filename).replace("\\", "/"),
        })

# ---------------------------
# Bridge filters & scoring
# ---------------------------
def _load_bridge_filters() -> Dict[str, Any]:
    p = CONFIG_DIR / "bridge_filters.json"
    if not p.exists():
        # sensible defaults
        return {
            "schema": "v1",
            "urgency_thresholds": {
                "low":    {"score_min": -999.0, "score_max": 1.0},
                "normal": {"score_min": 1.0,   "score_max": 3.0},
                "high":   {"score_min": 3.0,   "score_max": 6.0},
                "urgent": {"score_min": 6.0,   "score_max": 999.0},
            }
        }
    return json.loads(p.read_text(encoding="utf-8"))

def _score_events(events: List[Dict[str, Any]]) -> float:
    if not events:
        return 0.0
    # tiny heuristic: negative for scandals/firings, positive for wins
    weights = {
        "championship": 6.0, "rival_win": 2.5, "upset_win": 2.0, "win": 1.0,
        "coach_fire": -2.5, "scandal": -6.0
    }
    s = 0.0
    for e in events:
        eff = str(e.get("effect", "")).lower()
        try:
            inten = float(e.get("intensity") or 1.0)
        except (TypeError, ValueError):
            inten = 1.0
        s += (weights.get(eff, 0.5) * inten)
    return s

def _bucket(score: float, thresholds: Dict[str, Dict[str, float]]) -> str:
    for name, rng in thresholds.items():
        if rng["score_min"] <= score < rng["score_max"]:
            return name
    return "normal"

# ---------------------------
# Packet factory
# ---------------------------
def _packet(role: str, week: int, summary: str,
            events: List[Dict[str, Any]],
            raw_urgency_bucket: str,
            extra: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "version": "1.1",
        "id": str(uuid.uuid4()),
        "role": role,
        "week": int(week),
        # store raw bucket for transparency; derived INFO/WARN/URGENT set just before write
        "urgency": raw_urgency_bucket,
        "subject": f"[{role}] {summary}",
        "summary": summary,
        "facts": extra,
        "events": events[:50],
    }

# ---------------------------
# Main API
# ---------------------------
def emit_message_packets(events: Optional[List[Dict[str, Any]]] = None,
                         world: Optional[Dict[str, Any]] = None,
                         week: Optional[int] = None,
                         out_dir: str = "logs/INBOX") -> None:
    """
    Emits three packets (AAD / Coach / Board) into out_dir and appends index.csv.
    """
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    outp = Path(out_dir); outp.mkdir(parents=True, exist_ok=True)

    evs = events or []
    wk = int(week or -1)

    cfg = _load_bridge_filters()
    thr = cfg.get("urgency_thresholds", {})
    score = _score_events(evs)
    raw_urgency_bucket = _bucket(score, thr)  # "low|normal|high|urgent"

    # world snapshot (safe/optional)
    finance = {}
    try:
        schools = world.get("schools", []) if isinstance(world, dict) else []
        if schools:
            s0 = schools[0]
            fin = s0.get("finance", {})
            finance = {
                "school": s0.get("name", "?"),
                "balance": round(float(fin.get("balance", 0.0)), 2),
                "donor_yield": round(float(fin.get("_tick", {}).get("donor_yield", 0.0)), 2),
                "sentiment": round(float(s0.get("sentiment", 0.0)), 3),
                "prestige": round(float(s0.get("prestige", 0.0)), 3),
            }
    except Exception:
        finance = {}

    summary = f"W{wk}: {len(evs)} events, score {score:.1f} ({raw_urgency_bucket})"

    aad   = _packet("AAD",   wk, f"Weekly wrap {summary}",        evs, raw_urgency_bucket, finance)
    coach = _packet("Coach", wk, f"Weekly briefing {summary}",    evs, raw_urgency_bucket, finance)
    board = _packet("Board", wk, f"Governance brief {summary}",   evs, raw_urgency_bucket, finance)

    # ---- Write & index (derive INFO/WARN/URGENT + badge just-in-time) ----
    def _write(pkt: Dict[str, Any], filename: str) -> None:
        # derive and attach presentation fields
        derived = _derive_urgency(pkt)               # INFO / WARN / URGENT
        pkt["urgency"] = derived
        pkt["urgency_badge"] = _BADGE[derived]

        # write JSON
        out_path = outp / filename
        out_path.write_text(json.dumps(pkt, indent=2), encoding="utf-8")

        # index row
        _append_inbox_index(outp, pkt.get("role", "?"), pkt.get("subject", "(no subject)"),
                            derived, filename)

    ts_now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    _write(aad,   f"AAD_{ts_now}.json")
    _write(coach, f"Coach_{ts_now}.json")
    _write(board, f"Board_{ts_now}.json")

# ---------------------------
# Self-test / CLI
# ---------------------------
def _make_demo_events(seed: int = 42) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    sample = [
        {"effect": "win", "intensity": 1.0},
        {"effect": "rival_win", "intensity": 1.0},
        {"effect": "scandal", "intensity": 0.5 if rng.random() < 0.5 else 0.0},
    ]
    # trim any zero-intensity
    return [e for e in sample if float(e.get("intensity", 0.0)) > 0.0]

def _make_demo_world() -> Dict[str, Any]:
    return {
        "schools": [{
            "name": "State U.",
            "prestige": 3.2,
            "sentiment": 0.18,
            "finance": {"balance": 125000.0, "_tick": {"donor_yield": 5500.0}}
        }]
    }

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="logs/INBOX")
    ap.add_argument("--week", type=int, default=1)
    ap.add_argument("--emit-samples", action="store_true", help="Write sample packets to out-dir")
    ap.add_argument("--selftest", action="store_true", help="Alias for --emit-samples with demo data")
    args = ap.parse_args(argv)

    out_dir = args.out_dir

    if args.selftest or args.emit-samples:
        events = _make_demo_events()
        world = _make_demo_world()
        emit_message_packets(events=events, world=world, week=args.week, out_dir=out_dir)
        print(f"Emitted sample packets to {out_dir}")
        return 0

    # default: no-op CLI
    print("No action. Use --selftest or --emit-samples.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
