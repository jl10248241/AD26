# tools/ui_mock.py
from __future__ import annotations

import argparse, json, os, random
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# ---------------------------
# ANSI color helpers (PowerShell-friendly)
# ---------------------------
def _ansi_ok() -> bool:
    if os.name != "nt":
        return True
    return os.environ.get("NO_ANSI", "0") != "1"

def _paint_header(text: str, urgency: str) -> str:
    if not _ansi_ok():
        return text
    u = (urgency or "INFO").upper()
    if u == "URGENT":
        return f"\x1b[91m{text}\x1b[0m"  # bright red
    if u == "WARN":
        return f"\x1b[93m{text}\x1b[0m"  # yellow
    return f"\x1b[37m{text}\x1b[0m"      # light gray

def _paint_sent(text: str, score: float) -> str:
    if not _ansi_ok():
        return text
    if score > 0.20:
        return f"\x1b[92m{text}\x1b[0m"  # green
    if score < -0.20:
        return f"\x1b[91m{text}\x1b[0m"  # red
    return f"\x1b[37m{text}\x1b[0m"      # gray

# ---------------------------
# Varied phrasing for sentiment
# ---------------------------
_PHRASES = ["Sentiment", "Fan mood", "Pulse", "Crowd vibe", "Temperature"]

def _format_sentiment(pkt: Dict[str, Any]) -> Optional[str]:
    facts = pkt.get("facts") or {}
    s = facts.get("sentiment", None)
    if s is None:
        return None
    label = random.choice(_PHRASES)
    return f"{label}: {float(s):+0.2f}"

# ---------------------------
# Packet loading
# ---------------------------
def _load_packet(p: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def _iter_packets(inbox: Path) -> List[Dict[str, Any]]:
    files = sorted(inbox.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    out: List[Dict[str, Any]] = []
    for f in files:
        pkt = _load_packet(f)
        if pkt is None:
            continue
        pkt["_file"] = f.name
        pkt["_mtime"] = datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")
        out.append(pkt)
    return out

# ---------------------------
# CLI
# ---------------------------
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Console viewer for INBOX packets")
    ap.add_argument("--inbox", default="logs/INBOX", help="Directory with packet JSONs")
    ap.add_argument("--limit", type=int, default=10, help="Max messages to show")
    ap.add_argument("--role", choices=["AAD","Coach","Board"], help="Filter by role")
    ap.add_argument("--since", help="ISO date (YYYY-MM-DD) to filter newer messages")
    args = ap.parse_args(argv)

    inbox = Path(args.inbox)
    if not inbox.exists():
        print(f"INBOX not found: {inbox}")
        return 1

    packets = _iter_packets(inbox)

    # optional filters
    if args.role:
        packets = [p for p in packets if (p.get("role") or "").upper() == args.role.upper()]
    if args.since:
        try:
            cut = datetime.fromisoformat(args.since)
            packets = [p for p in packets if datetime.fromisoformat(p["_mtime"]) >= cut]
        except Exception:
            print("WARN: --since must be YYYY-MM-DD (e.g., 2025-10-29)")

    count = 0
    for pkt in packets:
        if count >= max(args.limit, 1):
            break

        role = pkt.get("role", "?")
        subject = pkt.get("subject", "(no subject)")
        urgency = (pkt.get("urgency") or "INFO").upper()
        badge = pkt.get("urgency_badge") or {"INFO":"[ ]","WARN":"[!]","URGENT":"[!!!]"}[urgency]
        ts = pkt.get("_mtime", "")

        header = f"{badge} {role}: {subject}  — {ts}"
        print(_paint_header(header, urgency))

        sent_line = _format_sentiment(pkt)
        if sent_line:
            facts = pkt.get("facts") or {}
            score = float(facts.get("sentiment", 0.0))
            print("   " + _paint_sent(sent_line, score))

        # optional: show filename in faint text
        if _ansi_ok():
            print(f"\x1b[90m   {pkt.get('_file','')}\x1b[0m")
        else:
            print(f"   {pkt.get('_file','')}")

        count += 1

    if count == 0:
        print("(no messages matched)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
