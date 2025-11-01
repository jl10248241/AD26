# engine/src/communication_bridge.py
# v17.9 — Communication Bridge (inbox + donor ledger with auto-migration)
# Emits /logs/INBOX/*.json and appends pledge_* events to /logs/DONOR_LEDGER.csv.
# Auto-migrates any legacy ledger (old header) to DONOR_LEDGER.legacy.csv.

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional
from pathlib import Path
import json
import re
import uuid
import csv
from datetime import datetime, UTC

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"
INBOX_DIR = LOGS / "INBOX"
INBOX_DIR.mkdir(parents=True, exist_ok=True)
LEDGER_CSV = LOGS / "DONOR_LEDGER.csv"

# ---- time helpers -----------------------------------------------------------
def _now_iso() -> str:
    # timezone-aware UTC; serialize as Z
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

# ---- utils ------------------------------------------------------------------
def _coerce_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

def _slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", (s or "").strip()).strip("-").lower()
    return s or "event"

# ---- inbox packet -----------------------------------------------------------
@dataclass
class InboxPacket:
    id: str
    type: str = "update"
    subject: str = ""
    summary: str = ""
    donor: Optional[str] = None
    coach: Optional[str] = None
    team: Optional[str] = None
    amount: Optional[float] = None
    severity: str = "normal"
    tags: Optional[List[str]] = None
    week: Optional[int] = None
    timestamp: str = ""
    days_ago: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None and v != ""}

# ---- translation ------------------------------------------------------------
def translate_event(e: Dict[str, Any], *, week: Optional[int] = None) -> InboxPacket:
    etype = (
        e.get("type")
        or e.get("event_type")
        or ("pledge_received" if e.get("received") else None)
        or "update"
    )

    donor = e.get("donor") or e.get("donor_name") or e.get("entity")
    coach = e.get("coach") or e.get("coach_name")
    team  = e.get("team") or e.get("school") or e.get("program")

    amount = (
        _coerce_float(e.get("amount"))
        or _coerce_float(e.get("value"))
        or _coerce_float(e.get("pledge") or e.get("pledge_amount"))
        or None
    )

    subject = (e.get("subject") or donor or team or e.get("title") or "Update")
    subject = str(subject or "Update").strip()
    summary = e.get("summary") or e.get("message") or ""
    severity = (e.get("severity") or e.get("urgency") or "normal").lower()
    if severity not in {"low", "normal", "high"}:
        severity = "normal"

    ts = e.get("timestamp") or _now_iso()
    days_ago = e.get("days_ago")
    w = e.get("week", week)

    base = _slug(f"{etype}-{subject}-{w or 0}")
    eid = e.get("id") or f"{base}-{uuid.uuid4().hex[:8]}"

    tags = e.get("tags")
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    pkt = InboxPacket(
        id=str(eid),
        type=str(etype).lower(),
        subject=subject,
        summary=summary,
        donor=donor,
        coach=coach,
        team=team,
        amount=amount,
        severity=severity,
        tags=tags if isinstance(tags, list) else None,
        week=w,
        timestamp=ts,
        days_ago=days_ago if isinstance(days_ago, int) else None,
        extra={k: v for k, v in e.items() if k not in {
            "id","type","event_type","subject","title","summary","message",
            "donor","donor_name","entity","coach","coach_name","team","school","program",
            "amount","value","pledge","pledge_amount","severity","urgency","tags",
            "week","timestamp","days_ago"
        }}
    )
    return pkt

# ---- emission ---------------------------------------------------------------
_COUNTER = 0
def _next_counter() -> int:
    global _COUNTER
    _COUNTER += 1
    return _COUNTER

def write_packet(pkt: InboxPacket) -> Path:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    stem = _slug(pkt.type) + f"-{_next_counter():04d}"
    if pkt.week is not None:
        stem = f"W{int(pkt.week):02d}-" + stem
    path = INBOX_DIR / f"{stem}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(pkt.to_dict(), f, ensure_ascii=False, indent=2)
    return path

# ---- donor ledger (append-only, with auto-migration) ------------------------
_EXPECTED_LEDGER_HEADER = ["timestamp","week","donor","type","amount","severity","id","subject"]

def _ensure_ledger_ready() -> None:
    LEDGER_CSV.parent.mkdir(parents=True, exist_ok=True)
    if not LEDGER_CSV.exists():
        with LEDGER_CSV.open("w", encoding="utf-8", newline="") as fp:
            csv.writer(fp).writerow(_EXPECTED_LEDGER_HEADER)
        return

    # If it exists, check header; migrate if legacy
    try:
        first = LEDGER_CSV.open(encoding="utf-8").readline().strip()
    except Exception:
        first = ""
    if first.replace(" ", "") != ",".join(_EXPECTED_LEDGER_HEADER):
        # migrate legacy file
        legacy_path = LEDGER_CSV.with_suffix(".legacy.csv")
        # avoid clobber
        if legacy_path.exists():
            legacy_path = LEDGER_CSV.with_name("DONOR_LEDGER.legacy2.csv")
        LEDGER_CSV.rename(legacy_path)
        with LEDGER_CSV.open("w", encoding="utf-8", newline="") as fp:
            csv.writer(fp).writerow(_EXPECTED_LEDGER_HEADER)

def _append_ledger(pkt: InboxPacket) -> None:
    if not pkt.type.startswith("pledge_"):
        return
    _ensure_ledger_ready()
    with LEDGER_CSV.open("a", encoding="utf-8", newline="") as fp:
        w = csv.writer(fp)
        w.writerow([
            pkt.timestamp,
            pkt.week if pkt.week is not None else "",
            pkt.donor or "",
            pkt.type,
            "" if pkt.amount is None else int(round(pkt.amount)),
            pkt.severity,
            pkt.id,
            pkt.subject,
        ])

def emit_inbox_packets(events: Iterable[Dict[str, Any]], *, week: Optional[int] = None) -> List[Path]:
    out_paths: List[Path] = []
    for e in events:
        pkt = translate_event(e, week=week)
        out_paths.append(write_packet(pkt))
        _append_ledger(pkt)
    
    # --- Logging added here ---
    try:
        from .logger import get_logger
        get_logger("bridge").info("wrote %d inbox packets and appended ledger", len(out_paths))
    except Exception:
        pass
    # --- End Logging ---
    
    return out_paths

def bridge_from_tick(reg_events: Iterable[Dict[str, Any]] = (), finance_events: Iterable[Dict[str, Any]] = (), *, week: Optional[int] = None) -> List[Path]:
    merged: List[Dict[str, Any]] = []
    merged.extend(list(reg_events or []))
    merged.extend(list(finance_events or []))
    return emit_inbox_packets(merged, week=week)

# ---- selftest ---------------------------------------------------------------
def _selftest() -> None:
    demo = [
        {"type": "pledge_promised", "donor": "MegaCorp", "amount": 250000, "week": 10, "days_ago": 1},
        {"type": "pledge_pending",  "donor": "Alumni Board", "amount":  50000, "week": 10, "days_ago": 2},
        {"type": "pledge_received", "donor": "MegaCorp", "amount": 100000, "week": 11, "days_ago": 0},
        {"type": "pledge_lapsed",   "donor": "Legacy Family", "amount": 75000, "week": 11, "days_ago": 3, "severity": "high"},
        {"type": "contact_required","donor": "Legacy Family", "week": 11, "summary": "No reply in 14 days", "days_ago": 3},
        {"type": "update", "subject": "Rival Win", "team": "State U", "summary": "Beat Rival 24–20", "week": 11},
    ]
    paths = emit_inbox_packets(demo, week=11)
    print("Wrote:")
    for p in paths:
        print(" -", p.relative_to(ROOT))

if __name__ == "__main__":
    _selftest()