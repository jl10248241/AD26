from __future__ import annotations
import json, argparse, sys
from pathlib import Path
from typing import Any, Dict, List

# --- Paths
WORKSPACE = Path(__file__).resolve().parents[2]
LOGS      = WORKSPACE / "logs"
INBOX     = LOGS / "INBOX"
MEDIA     = LOGS / "MEDIA"
DOCS      = WORKSPACE / "docs"

MEDIA.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)

# --- Utilities
def _read_json(p: Path, fallback: Any=None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def _write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def list_media_files() -> List[Path]:
    # Prefer *.media.json, fall back to *.json; newest first
    files = sorted(MEDIA.glob("*.media.json"))
    if not files:
        files = sorted(MEDIA.glob("*.json"))
    return sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)

def read_media(p: Path) -> Dict[str, Any]:
    return _read_json(p, {}) or {}

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

# --- Reports
def write_report(docs_dir: Path | None=None) -> Path:
    docs_dir = docs_dir or DOCS
    docs_dir.mkdir(parents=True, exist_ok=True)
    out = docs_dir / "MEDIA_FEED.md"

    rows = []
    for p in list_media_files():
        m = read_media(p)
        when = m.get("when", "")
        title = m.get("title") or m.get("summary") or ""
        status = m.get("status", "new")
        try:
            sentiment = f"{float(m.get('sentiment', 0.0)):+.2f}"
        except Exception:
            sentiment = "+0.00"
        rows.append((when, title, status, sentiment))

    lines = ["# Media Feed — latest", "", "", "| When | Title | Status | Sentiment |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out

# --- Core action
def act(index: int, action: str) -> Dict[str, Any]:
    """
    Apply an action to the media item at 1-based newest-first index.
    Actions: amplify | downplay | ignore
    Returns a tiny result dict with file and new fields.
    """
    files = list_media_files()
    if not files:
        raise RuntimeError("No media files to act on.")
    if index < 1 or index > len(files):
        raise IndexError(f"Index out of range: {index} (have {len(files)})")

    p = files[index - 1]
    m = read_media(p)

    status_before = m.get("status", "new")
    sent_before = float(m.get("sentiment", 0.0))

    if action == "amplify":
        # nudge sentiment slightly more positive, cap at +1
        m["sentiment"] = _clamp(sent_before + 0.02, -1.0, 1.0)
        m["status"] = "amplify"
    elif action == "downplay":
        # nudge sentiment slightly toward neutral (increase if negative, decrease if positive)
        if sent_before < 0:
            m["sentiment"] = _clamp(sent_before + 0.02, -1.0, 1.0)
        else:
            m["sentiment"] = _clamp(sent_before - 0.02, -1.0, 1.0)
        m["status"] = "downplay"
    elif action == "ignore":
        m["status"] = "ignore"
    else:
        raise ValueError(f"Unknown action: {action}")

    _write_json(p, m)
    # keep report up to date (best-effort)
    try:
        write_report(DOCS)
    except Exception:
        pass

    return {
        "file": p.name,
        "status_before": status_before,
        "status_after": m["status"],
        "sent_before": round(sent_before, 4),
        "sent_after": round(float(m.get("sentiment", 0.0)), 4),
    }

# --- CLI
def _cmd_ingest(args: argparse.Namespace) -> None:
    """
    Minimal ingest: copy INBOX *.json to MEDIA as *.media.json if missing.
    (You already populated MEDIA elsewhere, so this is a safe no-op most days.)
    """
    INBOX.mkdir(parents=True, exist_ok=True)
    created = 0
    for src in sorted(INBOX.glob("*.json")):
        dst = MEDIA / (src.stem + ".media.json")
        if not dst.exists():
            _write_json(dst, _read_json(src, {}))
            created += 1
    print(f"Ingested {created} item(s) → {MEDIA}")

def _cmd_report(args: argparse.Namespace) -> None:
    out = write_report(DOCS)
    print(f"Report OK → {out}")

def _cmd_act(args: argparse.Namespace) -> None:
    res = act(int(args.index), args.action)
    print("OK:", res)

def main():
    ap = argparse.ArgumentParser(prog="media_desk")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p_ing = sp.add_parser("ingest", help="Turn INBOX items into MEDIA items")
    p_ing.set_defaults(func=_cmd_ingest)

    p_rep = sp.add_parser("report", help="Build docs/MEDIA_FEED.md")
    p_rep.set_defaults(func=_cmd_report)

    p_act = sp.add_parser("act", help="Act on one item by 1-based newest-first index")
    p_act.add_argument("index", type=int)
    p_act.add_argument("action", choices=["amplify","downplay","ignore"])
    p_act.set_defaults(func=_cmd_act)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
