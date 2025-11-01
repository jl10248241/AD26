from __future__ import annotations
import argparse, sys, json
from pathlib import Path
from typing import Dict, Any, List, Tuple

from .media_desk import MEDIA, write_report, act  # MEDIA Path & core actions

def list_media_files() -> List[Path]:
    MEDIA.mkdir(parents=True, exist_ok=True)
    files = sorted(MEDIA.glob("*.media.json"))
    if not files:
        files = sorted(MEDIA.glob("*.json"))
    # newest first for display/indices
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

def read_media(p: Path) -> Dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def cmd_list(args):
    files = list_media_files()
    for i, p in enumerate(files, 1):
        m = read_media(p)
        title = m.get("title") or m.get("summary") or ""
        sent = float(m.get("sentiment", 0.0))
        status = m.get("status", "new")
        print(f"{i:2d}. {title} [{status}] s={sent:+.2f}")

def cmd_detail(args):
    files = list_media_files()
    idx = max(1, int(args.index))
    if idx > len(files):
        print("Index out of range.")
        sys.exit(1)
    p = files[idx-1]
    m = read_media(p)
    print("="*60)
    print(m.get("title","").strip() or "(untitled)")
    print("-"*60)
    print("when      :", m.get("when",""))
    print("type      :", m.get("type",""))
    print("status    :", m.get("status",""))
    print("sentiment :", f"{float(m.get('sentiment',0.0)):+.2f}")
    print("source    :", m.get("source",""))
    print("actors    :", m.get("actors",{}))
    print("file      :", p.name)
    print("="*60)

def cmd_act(args):
    files = list_media_files()
    idx = max(1, int(args.index))
    if idx > len(files):
        print("Index out of range.")
        sys.exit(1)
    # act expects 1-based index in newest-first order
    res = act(idx, args.action)
    try:
        write_report(Path(__file__).resolve().parents[2]/"docs")
    except Exception:
        pass
    print(res if res else "OK")

def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)

    p_list = sp.add_parser("list", help="List media items (newest first)")
    p_list.set_defaults(func=cmd_list)

    p_det = sp.add_parser("detail", help="Show one item by 1-based index")
    p_det.add_argument("index", type=int)
    p_det.set_defaults(func=cmd_detail)

    p_act = sp.add_parser("act", help="Apply action to item (amplify/downplay/ignore)")
    p_act.add_argument("index", type=int)
    p_act.add_argument("action", type=str, choices=["amplify","downplay","ignore"])
    p_act.set_defaults(func=cmd_act)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
