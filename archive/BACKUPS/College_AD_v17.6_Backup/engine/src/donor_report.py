# engine/src/donor_report.py — v17.6 donor relationship report (log-derived)
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import re, csv, math, datetime

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = (ROOT / "logs").resolve()
DOCS_DIR = (ROOT / "docs").resolve()
DOSSIER_DIR = (DOCS_DIR / "donors").resolve()
LOG_DIR.mkdir(parents=True, exist_ok=True)
DOSSIER_DIR.mkdir(parents=True, exist_ok=True)

WORLD_EVENTS_LOG = LOG_DIR / "WORLD_EVENTS_LOG.csv"
FINANCE_LOG      = LOG_DIR / "FINANCE_LOG.csv"
OUT_CSV          = LOG_DIR / "DONOR_RELATIONSHIPS.csv"

# Match patterns we already emit in notes/fields
RX_SCHOOL_FIELD  = re.compile(r"school:([A-Za-z0-9 .&'-]+)")
RX_TARGETING     = re.compile(r"targeting ([A-Za-z0-9 .&'-]+)")
RX_PLEDGE        = re.compile(r"pledge:\$?([\d,]+)")
RX_EARMARK       = re.compile(r"earmark:([A-Za-z0-9 _&'-]+)")
RX_PERSONA       = re.compile(r"Donor Persona:([A-Za-z0-9_]+)")
RX_PROP          = re.compile(r"prop=([0-9.]+)")

# Same flavor as donor_memory defaults so this estimate feels consistent
TRUST_START     = 0.50
LEV_START       = 0.00
DECAY_RATE      = 0.98  # ~2% per week toward neutral
TRUST_PLEDGE_D  = 0.02
LEV_PLEDGE_D    = 0.01

def _read_finance_weeks() -> Tuple[int, int]:
    """Find min/max week in FINANCE_LOG to bound our reconstruction."""
    if not FINANCE_LOG.exists():
        return (1, 1)
    minw, maxw = math.inf, -math.inf
    with FINANCE_LOG.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            try:
                w = int(float(r.get("week", 0)))
                if w < minw: minw = w
                if w > maxw: maxw = w
            except: 
                continue
    if minw is math.inf: minw = 1
    if maxw < 1: maxw = minw
    return (minw, maxw)

def _iter_world_events():
    if not WORLD_EVENTS_LOG.exists():
        return
    with WORLD_EVENTS_LOG.open("r", encoding="utf-8") as f:
        # header: week,event_id,intensity,target,effect,notes
        rdr = csv.DictReader(f)
        for r in rdr:
            yield r

def _school_from_row(row: Dict[str, str]) -> str | None:
    # Try explicit school:..., else "targeting ..."
    notes = row.get("notes", "") or ""
    m = RX_SCHOOL_FIELD.search(notes)
    if m:
        return m.group(1).strip()
    m = RX_TARGETING.search(notes)
    if m:
        return m.group(1).strip()
    # Sometimes target field might include "coach:..." — not helpful. Return None.
    return None

def _money_to_float(s: str) -> float:
    try:
        return float(str(s).replace(",", "").replace("$", "").strip())
    except:
        return 0.0

def _reconstruct() -> Dict[str, Dict[str, Any]]:
    """
    Build a per-school donor state from WORLD_EVENTS_LOG + week range in FINANCE_LOG.
    This mimics donor_memory's trust/leverage drift and pledge bumps.
    """
    wmin, wmax = _read_finance_weeks()
    schools = {}  # name -> state
    # init empty states
    def ensure(sch):
        return schools.setdefault(sch, {
            "trust": TRUST_START,
            "lev":   LEV_START,
            "pledges": [],  # list[{week, amount, earmark}]
            "last_persona": "",
            "last_prop": None,
            "last_week": None,
        })

    # Collect donor-relevant rows
    for row in _iter_world_events():
        eid = (row.get("event_id") or "").upper()
        if not any(key in eid for key in ("DONOR", "ALUMNI", "PLEDGE")):
            # still check if notes mention pledge/persona
            if "Donor Persona:" not in (row.get("notes") or "") and "pledge:" not in (row.get("notes") or ""):
                continue

        try:
            week = int(float(row.get("week", "0")))
        except:
            continue

        sch = _school_from_row(row)
        if not sch:
            continue
        st = ensure(sch)

        notes = row.get("notes", "") or ""
        # persona + prop
        mp = RX_PERSONA.search(notes)
        if mp:
            st["last_persona"] = mp.group(1)
        mp2 = RX_PROP.search(notes)
        if mp2:
            try:
                st["last_prop"] = float(mp2.group(1))
            except:
                pass

        # pledges
        mp3 = RX_PLEDGE.search(notes)
        if mp3:
            amt = _money_to_float(mp3.group(1))
            earm = ""
            me = RX_EARMARK.search(notes)
            if me:
                earm = me.group(1).strip()
            st["pledges"].append({"week": week, "amount": amt, "earmark": earm})
            # bump estimates similar to donor_memory
            st["trust"] = max(0.0, min(1.0, st["trust"] + TRUST_PLEDGE_D))
            st["lev"]   = max(-1.0, min(1.0, st["lev"] + LEV_PLEDGE_D))

        # apply decay up to this event week (basic approach)
        if st["last_week"] is None:
            st["last_week"] = week
        else:
            dt = max(0, week - st["last_week"])
            if dt > 0:
                st["trust"] = 0.5 + (st["trust"] - 0.5) * (DECAY_RATE ** dt)
                st["lev"]   = st["lev"] * (DECAY_RATE ** dt)
                st["last_week"] = week

    # After last event, decay to wmax
    for st in schools.values():
        if st["last_week"] is None:
            st["last_week"] = wmin
        tail = max(0, wmax - st["last_week"])
        if tail > 0:
            st["trust"] = 0.5 + (st["trust"] - 0.5) * (DECAY_RATE ** tail)
            st["lev"]   = st["lev"] * (DECAY_RATE ** tail)
            st["last_week"] = wmax

    return schools

def _fmt_pct(x: float) -> str:
    return f"{x*100:,.1f}%"

def _write_csv(schools: Dict[str, Dict[str, Any]]) -> None:
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow([
            "school","trust_est","leverage_est","pledges_count","pledges_total",
            "last_persona","last_prop","last_week"
        ])
        for sch in sorted(schools.keys()):
            st = schools[sch]
            total = sum(p["amount"] for p in st["pledges"])
            wr.writerow([
                sch,
                f"{st['trust']:.3f}",
                f"{st['lev']:.3f}",
                len(st["pledges"]),
                f"{total:.0f}",
                st.get("last_persona",""),
                "" if st.get("last_prop") is None else f"{st['last_prop']:.2f}",
                st.get("last_week") or ""
            ])

def _write_dossiers(schools: Dict[str, Dict[str, Any]]) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    for sch, st in schools.items():
        md = []
        md.append(f"# Donor Dossier — {sch}\n\n")
        md.append(f"_Generated: {ts}_\n\n")
        md.append(f"- **Trust (est):** {st['trust']:.3f}  \n")
        md.append(f"- **Leverage (est):** {st['lev']:.3f}  \n")
        md.append(f"- **Last Persona:** {st.get('last_persona','')}  \n")
        lp = st.get("last_prop")
        if lp is not None:
            md.append(f"- **Last Propensity:** {lp:.2f}  \n")
        md.append(f"- **Pledges:** {len(st['pledges'])}  \n")
        md.append("\n## Pledge History\n\n")
        if not st["pledges"]:
            md.append("_No pledges recorded in logs._\n")
        else:
            md.append("| Week | Amount | Earmark |\n| --- | ---: | --- |\n")
            for p in sorted(st["pledges"], key=lambda x: x["week"]):
                md.append(f"| {p['week']} | ${p['amount']:,.0f} | {p['earmark'] or ''} |\n")
        path = DOSSIER_DIR / f"{sch.replace(' ','_')}.md"
        path.write_text("".join(md), encoding="utf-8")

def main() -> None:
    schools = _reconstruct()
    _write_csv(schools)
    _write_dossiers(schools)
    print(f"[donor_report] wrote {OUT_CSV} and {len(schools)} dossiers → {DOSSIER_DIR}")

if __name__ == "__main__":
    main()
