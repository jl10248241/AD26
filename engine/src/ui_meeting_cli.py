#!/usr/bin/env python3
import argparse, json, sys, os
from pathlib import Path
from datetime import datetime

def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[meeting] ERROR reading JSON: {e}")
        return None

def coalesce(*vals):
    for v in vals:
        if v is not None and str(v).strip() != "":
            return v
    return ""

def main():
    ap = argparse.ArgumentParser(description="College AD v18 — Meeting Scene")
    ap.add_argument("packet", help="Path to INBOX JSON file")
    ap.add_argument("--dry-run", action="store_true", help="Print only; do not write transcript even if status\\ exists")
    args = ap.parse_args()

    packet_path = Path(args.packet).resolve()
    if not packet_path.exists():
        print(f"[meeting] Packet not found: {packet_path}")
        return 1

    # project root = engine/src/../../
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent
    status_dir = project_root / "status"

    data = load_json(packet_path)
    if not data:
        return 1

    attendees = coalesce(data.get("participants"), data.get("from"), "TBD")
    subject = coalesce(data.get("subject"), "(no subject)")
    week = coalesce(data.get("week"), "?")
    urgency = coalesce(data.get("urgency"), 3)
    tone = coalesce(data.get("tone"), "neutral")
    body = coalesce(data.get("body"), "")

    print("\n=== Meeting Scene ===")
    print(f"Attendees: {attendees}")
    print(f"Subject  : {subject}")
    print(f"Week     : {week} | Urgency: {urgency} | Tone: {tone}")
    if body:
        snip = body[:220].replace("\n", " ")
        print(f"Context  : {snip}{'…' if len(body) > 220 else ''}")

    print("\nPick your meeting style:")
    print("  1) Collaborative — gather input and co-create plan")
    print("  2) Command — issue directives and deadlines")
    print("  3) Triage — identify top 3 blockers, assign owners")
    print("  q) Quit")
    choice = input("> ").strip().lower()

    mapping = {
        "1": "Collaborative",
        "2": "Command",
        "3": "Triage",
        "q": "Quit"
    }
    decision = mapping.get(choice, "Quit")
    if decision == "Quit":
        print("[meeting] Scene cancelled.")
        return 0

    outcomes = {
        "Collaborative": "You aligned stakeholders and produced a shared plan with owners and next steps.",
        "Command": "You issued clear directives; progress expected by next checkpoint.",
        "Triage": "You focused the room on top blockers; responsibilities assigned and timelines set."
    }
    print(f"[meeting] Decision: {decision}")
    print(f"[meeting] Outcome : {outcomes[decision]}")

    # Optional transcript — only if status/ exists and not dry-run
    if not args.dry_run and status_dir.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = status_dir / f"SCENE_MEETING_{ts}.md"
        lines = [
            "# Scene — Meeting",
            f"- When: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Attendees: {attendees}",
            f"- Subject: {subject}",
            f"- Week: {week}",
            f"- Decision: {decision}",
            "",
            f"Outcome: {outcomes[decision]}"
        ]
        try:
            out.write_text("\n".join(lines), encoding="utf-8")
            print(f"[meeting] Transcript saved: status\\{out.name}")
        except Exception as e:
            print(f"[meeting] Skipped transcript (write error): {e}")
    else:
        if not status_dir.exists():
            print("[meeting] status\\ not present; transcript skipped (Rule #1).")

    return 0

if __name__ == "__main__":
    sys.exit(main())
