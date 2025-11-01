# engine/src/donor_snapshot.py
# v17.9 — Latest pledge status per donor (from logs/DONOR_LEDGER.csv)
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"
DOCS = ROOT / "docs"
LEDGER = LOGS / "DONOR_LEDGER.csv"
DOCS.mkdir(parents=True, exist_ok=True)

def read_ledger() -> List[Dict[str, str]]:
    if not LEDGER.exists():
        return []
    rows: List[Dict[str, str]] = []
    with LEDGER.open(encoding="utf-8") as fp:
        rd = csv.DictReader(fp)
        for r in rd:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows

def _key(row: Dict[str, str]):
    # newest first: timestamp string (ISO) sorts correctly, tie-break by week numeric
    ts = row.get("timestamp", "")
    try:
        wk = float(row.get("week") or 0)
    except Exception:
        wk = 0.0
    return (ts, wk)

def latest_per_donor(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    by_donor: Dict[str, Dict[str, str]] = {}
    for r in sorted(rows, key=_key, reverse=True):
        donor = r.get("donor") or "UNKNOWN"
        if donor not in by_donor:
            by_donor[donor] = r
    return [by_donor[k] for k in sorted(by_donor)]

def render_table(latest: List[Dict[str, str]], limit: Optional[int] = None) -> str:
    hdr = "| Donor | Latest Status | Amount | Week | ID |\n|---|---|---:|---:|---|"
    lines = [hdr]
    take = latest[:limit] if limit else latest
    for r in take:
        donor = r.get("donor","—")
        status = r.get("type","—")
        amt_s = r.get("amount","")
        try:
            amt = f"${int(round(float(amt_s))):,}" if amt_s else "—"
        except Exception:
            amt = "—"
        wk = r.get("week","—")
        rid = r.get("id","—")
        lines.append(f"| {donor} | {status} | {amt} | {wk} | {rid} |")
    return "\n".join(lines)

def write_markdown(latest: List[Dict[str, str]]) -> Path:
    out = DOCS / "DONOR_SNAPSHOT.md"
    body = [
        "# Donor Snapshot",
        "",
        "Latest pledge status per donor from `logs/DONOR_LEDGER.csv`.",
        "",
        render_table(latest),
        "",
        f"_Total donors: {len(latest)}_",
    ]
    out.write_text("\n".join(body), encoding="utf-8")
    return out

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Latest pledge status per donor")
    ap.add_argument("--donor", help="substring filter for donor name")
    ap.add_argument("--limit", type=int, help="limit number of rows in output")
    ap.add_argument("--json", action="store_true", help="print JSON instead of table")
    args = ap.parse_args(argv)

    rows = read_ledger()
    if not rows:
        print("No donor ledger found at logs/DONOR_LEDGER.csv")
        return 0

    latest = latest_per_donor(rows)
    if args.donor:
        s = args.donor.lower()
        latest = [r for r in latest if s in (r.get("donor","").lower())]

    if args.json:
        print(json.dumps(latest[: args.limit] if args.limit else latest, indent=2))
    else:
        print(render_table(latest, limit=args.limit))
    out = write_markdown(latest if not args.limit else latest[: args.limit])
    print(f"\nWrote {out.relative_to(ROOT)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
