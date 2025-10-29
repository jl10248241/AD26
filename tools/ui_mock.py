# tools/ui_mock.py — v17.7 inbox CLI preview
from __future__ import annotations
from pathlib import Path
import json, argparse, datetime as dt, textwrap

DEFAULT_INBOX = Path("logs/INBOX")

# 📌 ADDED: ANSI Color Helper
def _color(s, kind):
    # basic ANSI without external deps
    codes = {"info":"\033[32m","warn":"\033[33m","err":"\033[31m","dim":"\033[90m","reset":"\033[0m"}
    return f"{codes.get(kind,'')}{s}{codes['reset']}"

def _load_messages(inbox: Path):
    if not inbox.exists():
        print(f"[ui_mock] inbox path not found: {inbox}")
        return []
    msgs = []
    for p in sorted(inbox.glob("*.json")):
        try:
            msg = json.loads(p.read_text(encoding="utf-8"))
            msg["_path"] = str(p)
            msgs.append(msg)
        except Exception as e:
            print(f"[ui_mock] skip {p.name}: {e}")
    return msgs

def _filter_messages(msgs, role=None, urgent=False, since_weeks=None):
    out = []
    now = dt.datetime.now()
    # Using standard 4 spaces for indentation consistency (fixed in previous step)
    
    for m in msgs:
        if role and str(m.get("role","")).lower() != role.lower():
            continue
        if urgent and "urgent" not in str(m.get("subject","")).lower():
            # Check for explicit urgency field as well
            if str(m.get("urgency","")).lower() != "urgent":
                continue
        if since_weeks:
            ts = Path(m.get("_path","")) 
            try:
                stamp_part = ts.stem.rsplit('_', 1)[-1] 
                
                if len(stamp_part) == 15 and stamp_part[8] == '_':
                    t = dt.datetime.strptime(stamp_part, "%Y%m%d_%H%M%S")
                elif len(stamp_part) >= 6:
                     t = dt.datetime.strptime(stamp_part, "%H%M%S")
                else:
                    raise ValueError("Timestamp format not recognized")
                
                if (now - t).days > since_weeks * 7:
                    continue
            except Exception:
                pass
        out.append(m)
    return out

def _print_messages(msgs, limit=None):
    if not msgs:
        print("[ui_mock] No messages found.")
        return
        
    INDENT_STR = "    "
    # 📌 REPLACED: Loop with color and badge logic
    for i, m in enumerate(msgs[:limit or len(msgs)], 1):
        # Ensure role is padded/truncated cleanly
        role = m.get("role","?").ljust(6)[:6]
        subj = m.get("subject","(no subject)")
        
        # Urgency/Color Logic
        urg  = str(m.get("urgency","normal")).lower()
        badge = {"urgent":"ERR", "high":"WARN", "normal":"INFO", "low":"INFO"}.get(urg, "INFO")
        kind  = {"urgent":"err","high":"warn","normal":"info","low":"info"}.get(urg,"info")
        
        summ = m.get("summary","").strip()
        facts = m.get("facts",{})

        head = f"[{i:02}] {role} | {subj} | {badge}"
        print(_color(head, kind))
        
        # Dimmed Finance Facts
        if facts:
            fact_line = f"{INDENT_STR}$ balance={facts.get('balance','?')}  donor_yield={facts.get('donor_yield','?')}  prestige={facts.get('prestige','?')}  sentiment={facts.get('sentiment','?')}"
            print(_color(fact_line, "dim"))
            
        # Summary and Path
        print(textwrap.indent(summ, INDENT_STR))
        print(f"{INDENT_STR}↳", m.get("_path",""))
        print("-" * 60)

def selftest():
    inbox = DEFAULT_INBOX
    msgs = _load_messages(inbox)
    print(f"[ui_mock] Loaded {len(msgs)} messages from {inbox}")
    _print_messages(msgs[:5])

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--role", help="Filter by role (AAD, Coach, Board)")
    p.add_argument("--urgent", action="store_true", help="Show only urgent items")
    p.add_argument("--since", type=int, help="Only show messages newer than N weeks")
    p.add_argument("--limit", type=int, help="Max messages to display")
    p.add_argument("--inbox", default=str(DEFAULT_INBOX), help="Path to inbox directory")
    p.add_argument("--selftest", action="store_true", help="Run quick preview")
    args = p.parse_args()

    inbox = Path(args.inbox)
    if args.selftest:
        selftest()
        return

    msgs = _load_messages(inbox)
    msgs = _filter_messages(msgs, role=args.role, urgent=args.urgent, since_weeks=args.since)
    _print_messages(msgs, limit=args.limit)

if __name__ == "__main__":
    main()