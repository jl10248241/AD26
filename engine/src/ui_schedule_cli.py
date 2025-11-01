from __future__ import annotations
import argparse
from pathlib import Path

# Use relative import so running "python -m engine.src.ui_schedule_cli ..." always works
from .schedule_engine import (
    load_state, save_state, load_config, ensure_day, available_hours,
    reserve_action, reschedule, advance_day, write_report
)

# Workspace + docs folder (engine/src/.. -> project root)
WORKSPACE = Path(__file__).resolve().parents[2]
DOCS = WORKSPACE / "docs"
DOCS.mkdir(parents=True, exist_ok=True)
DEST_MD = DOCS / "SCHEDULE.md"

def _force_report_into_docs():
    """
    Call schedule_engine.write_report() and ensure the final markdown
    lives under <project_root>/docs/SCHEDULE.md regardless of what the
    engine returns. If the engine already writes there, we just return it.
    """
    try:
        # If your write_report supports a target path, prefer that:
        # (We try both "base" and direct path styles for forwards compatibility.)
        try:
            path = write_report(DOCS)        # write_report(base_docs_dir)
        except TypeError:
            try:
                path = write_report(DEST_MD) # write_report(full_path)
            except TypeError:
                path = write_report()        # legacy signature: no args
    except Exception:
        # Fall back to returning the canonical destination (even if engine raised)
        return DEST_MD

    # If the engine wrote somewhere else, copy the contents into our canonical file.
    try:
        if Path(path).resolve() != DEST_MD.resolve():
            text = Path(path).read_text(encoding="utf-8", errors="replace")
            DEST_MD.write_text(text, encoding="utf-8")
            return DEST_MD
        return Path(path)
    except Exception:
        # If anything odd happens, at least ensure a file exists at DEST_MD
        if not DEST_MD.exists():
            DEST_MD.write_text("# Schedule — latest\n\n(Report generation failed.)\n", encoding="utf-8")
        return DEST_MD

def cmd_status(args):
    st = load_state()
    day = st["today"]
    avail = available_hours(st, day)
    print(f"Today: {day} | Available hours: {avail:.1f}")

def cmd_reserve(args):
    ok, info = reserve_action(
        action_type=args.type,
        when=args.day,
        hours=args.hours,
        title=args.title,
        priority=args.priority,
        actor=args.actor,
        target=args.target,
        meta={}
    )
    if ok:
        print("Reserved:", info["id"], "on", info["day"], f"({info['hours']}h)")
    else:
        print("FAILED:", info.get("status",""), "available=", info.get("available"), "needed=", info.get("needed"))

def cmd_reschedule(args):
    ok, info = reschedule(args.id, args.day)
    if ok:
        print("Rescheduled OK:", info)
    else:
        print("Reschedule FAILED:", info)

def cmd_advance(args):
    newd = advance_day(args.days)
    print("Advanced to:", newd)

def cmd_report(args):
    path = _force_report_into_docs()
    print("Report OK →", str(path))

def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("status");  p.set_defaults(func=cmd_status)

    p = sp.add_parser("reserve")
    p.add_argument("--type", required=True)
    p.add_argument("--hours", type=float)
    p.add_argument("--day")
    p.add_argument("--title")
    p.add_argument("--priority", default="normal", choices=["low","normal","high","critical"])
    p.add_argument("--actor"); p.add_argument("--target")
    p.set_defaults(func=cmd_reserve)

    p = sp.add_parser("resched")
    p.add_argument("--id", required=True)
    p.add_argument("--day", required=True)
    p.set_defaults(func=cmd_reschedule)

    p = sp.add_parser("advance")
    p.add_argument("--days", type=int, default=1)
    p.set_defaults(func=cmd_advance)

    p = sp.add_parser("report"); p.set_defaults(func=cmd_report)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
