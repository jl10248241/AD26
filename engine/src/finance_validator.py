# engine/src/finance_validator.py — v17.10 (compact console output + filters)
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"
DOCS = ROOT / "docs"
FINANCE_CSV = LOGS / "FINANCE_LOG.csv"
OUT_MD = DOCS / "FINANCE_TRENDS.md"

def _fmt_money(x: float) -> str:
    return f"{x:,.0f}"

def _fmt2(x: float) -> str:
    return f"{x:.2f}"

def _read_finance() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not FINANCE_CSV.exists():
        return rows
    with FINANCE_CSV.open("r", encoding="utf-8", newline="") as fp:
        r = csv.DictReader(fp)
        for row in r:
            try:
                rows.append({
                    "week": int(row.get("week", 0)),
                    "school": row.get("school", "UNKNOWN"),
                    "donor_yield": float(row.get("donor_yield", 0.0)),
                    "expenses": float(row.get("expenses", 0.0)),
                    "balance": float(row.get("balance", 0.0)),
                    "prestige_change": float(row.get("prestige_change", 0.0)),
                    "sentiment": float(row.get("sentiment", 0.0)),
                })
            except Exception:
                pass
    return rows

def _analyze(rows: List[Dict[str, Any]]) -> Tuple[List[str], List[Tuple[str,int,float,float,str,int,float,float]]]:
    by_school: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_school[r["school"]].append(r)

    issues_out: List[str] = []
    table: List[Tuple[str,int,float,float,str,int,float,float]] = []

    for school, items in by_school.items():
        items.sort(key=lambda x: x["week"])
        if not items:
            continue

        smin = min(i["sentiment"] for i in items)
        smax = max(i["sentiment"] for i in items)
        sent_range = f"{_fmt2(smin)}..{_fmt2(smax)}"

        prev_expected = None
        school_issues = 0
        for i, r in enumerate(items):
            expected = r["balance"] if prev_expected is None else prev_expected
            expected_next = expected + r["donor_yield"] - r["expenses"]
            if i + 1 < len(items):
                seen_next = items[i + 1]["balance"]
                if abs(seen_next - expected_next) > 1e-6:
                    issues_out.append(
                        f"- ⚠️ Balance discontinuity for **{school}** at week {items[i + 1]['week']}: "
                        f"expected { _fmt_money(expected_next) }, saw { _fmt_money(seen_next) } "
                        f"(Δ={ _fmt_money(seen_next - expected_next) })"
                    )
                    school_issues += 1
            prev_expected = expected_next

        d_balance_total = items[-1]["balance"] - items[0]["balance"]
        table.append((school, len(items), d_balance_total, items[-1]["balance"], sent_range, school_issues, smin, smax))

    # Sort: schools with issues first (desc by count), then by name
    table.sort(key=lambda t: (-t[5], t[0]))
    return issues_out, table

def _dedupe(seq: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for s in seq:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out

def _write_markdown(issues: List[str], table_rows) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# Finance & Sentiment Trends\n")
    if issues:
        lines.extend(issues)
        lines.append("")  # blank line

    lines.append("| School | Weeks | ΔBalance (recalc) | Last Balance | Sentiment min..max | Issues |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for (school, weeks, d_bal, last_bal, sent_range, n_issues, _smin, _smax) in table_rows:
        lines.append(
            f"| {school} | {weeks} | {_fmt_money(d_bal)} | {_fmt_money(last_bal)} | {sent_range} | {n_issues} |"
        )

    (DOCS / "FINANCE_TRENDS.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

def _ascii(s: str) -> str:
    return (s.replace("⚠️", "!")
             .replace("Δ", "d")
             )

def main() -> None:
    ap = argparse.ArgumentParser(description="Validate finance log and emit trends.")
    ap.add_argument("--limit", type=int, default=25, help="Max schools to print to console table (default: 25).")
    ap.add_argument("--issues-only", action="store_true", help="Only include schools with issues in console table.")
    ap.add_argument("--filter", type=str, default="", help="Substring match on school name for console table.")
    ap.add_argument("--ascii", action="store_true", help="ASCII-only console output (no emojis/symbols).")
    ap.add_argument("--max-issues", type=int, default=25, help="Cap how many issue bullet lines are printed (default: 25).")
    ap.add_argument("--no-file", action="store_true", help="Do not write docs/FINANCE_TRENDS.md (console preview only).")
    args = ap.parse_args()

    rows = _read_finance()
    issues, table = _analyze(rows)

    # Dedupe identical issue lines and cap
    issues = _dedupe(issues)
    clipped = False
    if args.max_issues >= 0 and len(issues) > args.max_issues:
        issues = issues[:args.max_issues]
        clipped = True

    # Always write the full file unless suppressed
    if not args.no_file:
        _write_markdown(issues, table)

    # Apply console filters
    console_rows = list(table)
    if args.issues_only:
        console_rows = [t for t in console_rows if t[5] > 0]
    if args.filter:
        key = args.filter.lower()
        console_rows = [t for t in console_rows if key in t[0].lower()]
    if args.limit and args.limit > 0:
        console_rows = console_rows[:args.limit]

    # Build console text
    header = "# Finance & Sentiment Trends\n"
    if args.ascii:
        header = _ascii(header)

    print(header, end="")

    if issues:
        txt_issues = "\n".join(_ascii(i) if args.ascii else i for i in issues)
        print(txt_issues)
        if clipped:
            more = "… (+more issues clipped)"
            print(_ascii(more) if args.ascii else more)
        print("")  # blank line

    # Console table
    print("| School | Weeks | ΔBalance (recalc) | Last Balance | Sentiment min..max | Issues |")
    print("|---|---:|---:|---:|---:|---:|")
    for (school, weeks, d_bal, last_bal, sent_range, n_issues, _smin, _smax) in console_rows:
        row = f"| {school} | {weeks} | {_fmt_money(d_bal)} | {_fmt_money(last_bal)} | {sent_range} | {n_issues} |"
        print(_ascii(row) if args.ascii else row)

if __name__ == "__main__":
    main()
