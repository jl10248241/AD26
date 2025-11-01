# engine/src/ui_inbox_cli.py
# v17.9 — Read-only Inbox CLI (filters: --only-pledges, --since DAYS, --open N)
from __future__ import annotations

import argparse, json, os, sys, time, webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
ENV = {}
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            ENV[k.strip()] = v.strip()

LOGS = (ROOT / ENV.get("LOG_DIR", "logs")).resolve()
INBOX = LOGS / "INBOX"
INBOX.mkdir(parents=True, exist_ok=True)

def load_packets() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in sorted(INBOX.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data["_path"] = str(p)
            data["_name"] = p.name
            out.append(data)
        except Exception:
            continue
    out.sort(key=lambda d: d.get("_name",""), reverse=True)
    return out

def _is_pledge(pkt: Dict[str, Any]) -> bool:
    return str(pkt.get("type","")).lower().startswith("pledge_")

def match(packet: Dict[str, Any], *, type_f: Optional[str], tag_f: Optional[str],
          search: Optional[str], only_pledges: bool, since_days: Optional[int]) -> bool:
    if only_pledges and not _is_pledge(packet):
        return False
    if type_f and str(packet.get("type","")).lower() != type_f.lower():
        return False
    if tag_f:
        tags = packet.get("tags") or []
        if isinstance(tags, list):
            if not any(tag_f.lower() == str(t).lower() for t in tags):
                return False
        else:
            return False
    if since_days is not None:
        d = packet.get("days_ago")
        if isinstance(d, int):
            if d > since_days:
                return False
        # if no days_ago, we keep it (we can’t safely exclude)
    if search:
        s = search.lower()
        hay = " ".join([
            str(packet.get("subject","")),
            str(packet.get("summary","")),
            str(packet.get("donor","")),
            str(packet.get("coach","")),
            str(packet.get("team","")),
            str(packet.get("type","")),
        ]).lower()
        if s not in hay:
            return False
    return True

def fmt_money(v: Any) -> str:
    try:
        x = float(v)
    except Exception:
        return "—"
    return "$0" if abs(x) < 0.5 else f"${int(round(x)):,}"

def one_line(p: Dict[str, Any]) -> str:
    who = p.get("donor") or p.get("coach") or p.get("team") or ""
    amt = f" • {fmt_money(p.get('amount'))}" if p.get("amount") is not None else ""
    w = f" [W{int(p['week']):02d}]" if p.get("week") is not None else ""
    return f"{p.get('type','update')} — {p.get('subject', who or 'Update')}{amt}{w}"

def print_list(items: List[Dict[str, Any]]) -> None:
    if not items:
        print("No inbox items match your filters.")
        return
    width = len(str(len(items)))
    for i, p in enumerate(items, start=1):
        print(f"{str(i).rjust(width)}. {one_line(p)}")

def print_detail(p: Dict[str, Any]) -> None:
    print("="*60)
    print(one_line(p))
    print("-"*60)
    rows = [
        ("subject", p.get("subject")),
        ("summary", p.get("summary")),
        ("donor", p.get("donor")),
        ("coach", p.get("coach")),
        ("team", p.get("team")),
        ("amount", fmt_money(p.get("amount")) if p.get("amount") is not None else "—"),
        ("severity", p.get("severity")),
        ("tags", ", ".join(p.get("tags") or []) if isinstance(p.get("tags"), list) else "—"),
        ("week", p.get("week")),
        ("days_ago", p.get("days_ago")),
        ("timestamp", p.get("timestamp")),
        ("id", p.get("id")),
        ("file", p.get("_name")),
        ("path", p.get("_path")),
    ]
    for k, v in rows:
        print(f"{k.rjust(10)} : {v if v not in (None, '') else '—'}")
    extra = p.get("extra") or {}
    if isinstance(extra, dict) and extra:
        print("-"*60)
        print("extra:")
        for k, v in extra.items():
            print(f"  - {k}: {v}")
    print("="*60)

def interactive_loop(items: List[Dict[str, Any]]) -> None:
    print_list(items)
    if not items:
        return
    print("\nType a number to view, 'o N' to open in editor, 'r' to refresh, 'q' to quit.")
    while True:
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not cmd:
            continue
        low = cmd.lower()
        if low in {"q","quit","exit"}:
            break
        if low in {"r","refresh"}:
            items = load_packets()
            print_list(items)
            continue
        if low.startswith("o "):
            try:
                idx = int(low.split()[1]) - 1
                if 0 <= idx < len(items):
                    p = items[idx]
                    path = p.get("_path")
                    if path:
                        # Try default OS open; fallback to printing path
                        try:
                            if os.name == "nt":
                                os.startfile(path)  # type: ignore[attr-defined]
                            else:
                                webbrowser.open(f"file://{path}")
                        except Exception:
                            print(path)
                    else:
                        print("No path recorded for that item.")
                else:
                    print("Out of range.")
            except Exception:
                print("Usage: o <number>")
            continue
        if low.isdigit():
            idx = int(low) - 1
            if 0 <= idx < len(items):
                print_detail(items[idx])
            else:
                print("Out of range.")
        else:
            print("Enter a number, 'o N' to open, 'r' to refresh, or 'q' to quit.")

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only Inbox CLI for College AD")
    ap.add_argument("--type", dest="type_f", help="filter by event type (e.g., pledge_received)")
    ap.add_argument("--tag", dest="tag_f", help="filter by tag (exact match)")
    ap.add_argument("--search", dest="search", help="substring search over subject/summary/who/type")
    ap.add_argument("--only-pledges", action="store_true", help="only show pledge_* events")
    ap.add_argument("--since", type=int, help="only items with days_ago <= N")
    ap.add_argument("--watch", action="store_true", help="auto-refresh list view every 5s")
    ap.add_argument("--detail", type=int, default=0, help="show details for Nth item and exit")
    ap.add_argument("--open", type=int, default=0, help="open Nth item file in default editor and exit")
    args = ap.parse_args(argv)

    all_items = load_packets()
    items = [p for p in all_items if match(
        p,
        type_f=args.type_f,
        tag_f=args.tag_f,
        search=args.search,
        only_pledges=args.only_pledges,
        since_days=args.since
    )]

    if args.open > 0:
        idx = args.open - 1
        if 0 <= idx < len(items) and items[idx].get("_path"):
            path = items[idx]["_path"]
            try:
                if os.name == "nt":
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    webbrowser.open(f"file://{path}")
            except Exception:
                print(path)
            return 0
        print("No such item or path missing.")
        return 1

    if args.detail > 0:
        idx = args.detail - 1
        if 0 <= idx < len(items):
            print_detail(items[idx])
            return 0
        print("No such item.")
        return 1

    if args.watch:
        try:
            while True:
                os.system("cls" if os.name == "nt" else "clear")
                print_list([p for p in load_packets() if match(
                    p, type_f=args.type_f, tag_f=args.tag_f, search=args.search,
                    only_pledges=args.only_pledges, since_days=args.since
                )])
                time.sleep(5)
        except KeyboardInterrupt:
            print()
            return 0

    interactive_loop(items)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
