# engine/src/donor_report_plus.py — v17.6.2 Donor Insights (depth-first)
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import re, csv, math, datetime

from .insights_core import (
    envelope, write_json, score_linear, arrow, delta_tuple, clamp
)

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = (ROOT / "logs").resolve()
DOCS_DIR = (ROOT / "docs").resolve()
DOSSIER_DIR = (DOCS_DIR / "donors").resolve()
INSIGHTS_DIR = (LOG_DIR / "INSIGHTS").resolve()

LOG_DIR.mkdir(parents=True, exist_ok=True)
DOSSIER_DIR.mkdir(parents=True, exist_ok=True)
INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)

WORLD_EVENTS_LOG = LOG_DIR / "WORLD_EVENTS_LOG.csv"
FINANCE_LOG      = LOG_DIR / "FINANCE_LOG.csv"
OUT_CSV          = LOG_DIR / "DONOR_RELATIONSHIPS.csv"
OUT_JSON         = INSIGHTS_DIR / "donors.summary.json"

# Patterns we already emit in WORLD_EVENTS_LOG notes
RX_SCHOOL_FIELD  = re.compile(r"school:([A-Za-z0-9 .&'-]+)")
RX_TARGETING     = re.compile(r"targeting ([A-Za-z0-9 .&'-]+)")
RX_PLEDGE        = re.compile(r"pledge:\$?([\d,]+)")
RX_EARMARK       = re.compile(r"earmark:([A-Za-z0-9 _&'-]+)")
RX_PERSONA       = re.compile(r"Donor Persona:([A-Za-z0-9_]+)")
RX_PROP          = re.compile(r"prop=([0-9.]+)")

# Behavior parameters (aligned with donor_memory defaults)
TRUST_START     = 0.50
LEV_START       = 0.00
DECAY_RATE      = 0.98
TRUST_PLEDGE_D  = 0.02
LEV_PLEDGE_D    = 0.01

def _read_finance_weeks() -> Tuple[int, int]:
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
        rdr = csv.DictReader(f)
        for r in rdr:
            yield r

def _school_from_row(row: Dict[str, str]) -> str | None:
    notes = row.get("notes", "") or ""
    m = RX_SCHOOL_FIELD.search(notes)
    if m: return m.group(1).strip()
    m = RX_TARGETING.search(notes)
    if m: return m.group(1).strip()
    return None

def _money_to_float(s: str) -> float:
    try: return float(str(s).replace(",", "").replace("$", "").strip())
    except: return 0.0

def _reconstruct() -> Dict[str, Dict[str, Any]]:
    wmin, wmax = _read_finance_weeks()
    schools: Dict[str, Dict[str, Any]] = {}
    weeks_seen: Dict[str, List[int]] = {}

    def ensure(sch: str) -> Dict[str, Any]:
        return schools.setdefault(sch, {
            "trust": TRUST_START,
            "lev":   LEV_START,
            "pledges": [],
            "last_persona": "",
            "last_prop": None,
            "w_series": [],   # [(week, trust, lev)]
            "last_week": None
        })

    for row in _iter_world_events():
        notes = row.get("notes", "") or ""
        eid = (row.get("event_id") or "")
        # skip non-donor events quickly unless notes contain donor hints
        if not any(k in eid.upper() for k in ("DONOR", "ALUMNI", "PLEDGE")) and ("Donor Persona:" not in notes and "pledge:" not in notes):
            continue
        try:
            week = int(float(row.get("week", "0")))
        except:
            continue

        sch = _school_from_row(row)
        if not sch: 
            continue
        st = ensure(sch)

        # decay to this week
        if st["last_week"] is None:
            st["last_week"] = week
        else:
            dt = max(0, week - st["last_week"])
            if dt > 0:
                st["trust"] = 0.5 + (st["trust"] - 0.5) * (DECAY_RATE ** dt)
                st["lev"]   = st["lev"] * (DECAY_RATE ** dt)
                st["last_week"] = week

        # persona & prop
        mp = RX_PERSONA.search(notes)
        if mp: st["last_persona"] = mp.group(1)
        mp2 = RX_PROP.search(notes)
        if mp2:
            try: st["last_prop"] = float(mp2.group(1))
            except: pass

        # pledges
        mp3 = RX_PLEDGE.search(notes)
        if mp3:
            amt = _money_to_float(mp3.group(1))
            earm = ""
            me = RX_EARMARK.search(notes)
            if me: earm = me.group(1).strip()
            st["pledges"].append({"week": week, "amount": amt, "earmark": earm})
            st["trust"] = max(0.0, min(1.0, st["trust"] + TRUST_PLEDGE_D))
            st["lev"]   = max(-1.0, min(1.0, st["lev"] + LEV_PLEDGE_D))

        st["w_series"].append((week, st["trust"], st["lev"]))

    # tail decay
    for st in schools.values():
        if st["last_week"] is None:
            st["last_week"] = wmin
        tail = max(0, wmax - st["last_week"])
        if tail > 0:
            st["trust"] = 0.5 + (st["trust"] - 0.5) * (DECAY_RATE ** tail)
            st["lev"]   = st["lev"] * (DECAY_RATE ** tail)
            st["last_week"] = wmax
        st["w_series"].append((wmax, st["trust"], st["lev"]))

    return schools, wmin, wmax

def _trend_deltas(series: List[Tuple[int, float]], window: int = 4) -> Dict[str, Any]:
    """
    series: list of (week, value) sorted by week
    returns: {"w1": {...}, "w4": {...}}
    """
    if not series:
        return {"w1": None, "w4": None}
    wk, val = series[-1]
    # WoW
    prev = series[-2][1] if len(series) >= 2 else val
    d1 = delta_tuple(val, prev)
    # 4w
    back_idx = max(0, len(series) - 1 - window)
    prev4 = series[back_idx][1]
    d4 = delta_tuple(val, prev4)
    return {"w1": d1, "w4": d4}

def _flags(trust: float, lev: float, deltas: Dict[str, Any]) -> List[str]:
    flags = []
    # Opportunity: trust mid + leverage high-ish
    if 0.45 <= trust <= 0.75 and lev >= 0.30:
        flags.append("opportunity")
    # Risk: trust low or falling fast
    w1 = deltas.get("w1") or {}
    if trust < 0.45 or (w1.get("pct") is not None and w1["pct"] < -5.0):
        flags.append("risk")
    return flags

def _write_csv(items: List[Dict[str, Any]]) -> None:
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow([
            "school","trust","lev","score",
            "trust_w1_abs","trust_w1_pct","trust_w1_dir",
            "trust_w4_abs","trust_w4_pct","trust_w4_dir",
            "lev_w1_abs","lev_w1_pct","lev_w1_dir",
            "lev_w4_abs","lev_w4_pct","lev_w4_dir",
            "pledges_count","pledges_total","last_persona","last_prop","flags"
        ])
        for it in items:
            tw1 = it["deltas"]["trust"]["w1"]; tw4 = it["deltas"]["trust"]["w4"]
            lw1 = it["deltas"]["lev"]["w1"];   lw4 = it["deltas"]["lev"]["w4"]
            wr.writerow([
                it["id"], f"{it['metrics']['trust']:.3f}", f"{it['metrics']['lev']:.3f}", it["score"],
                None if not tw1 else tw1["abs"], None if not tw1 else tw1["pct"], None if not tw1 else tw1["dir"],
                None if not tw4 else tw4["abs"], None if not tw4 else tw4["pct"], None if not tw4 else tw4["dir"],
                None if not lw1 else lw1["abs"], None if not lw1 else lw1["pct"], None if not lw1 else lw1["dir"],
                None if not lw4 else lw4["abs"], None if not lw4 else lw4["pct"], None if not lw4 else lw4["dir"],
                it["pledges"]["count"], it["pledges"]["total"],
                it.get("last_persona",""), it.get("last_prop",None),
                ",".join(it.get("flags",[]))
            ])

def _write_dossiers(items: List[Dict[str, Any]], weeks: Tuple[int,int]) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    for it in items:
        sch = it["id"]
        md = []
        md.append(f"# Donor Dossier — {sch}\n\n_Generated: {ts}_\n\n")
        md.append(f"- **Trust:** {it['metrics']['trust']:.3f}  \n")
        md.append(f"- **Leverage:** {it['metrics']['lev']:.3f}  \n")
        md.append(f"- **Score:** {it['score']} / 100  \n")
        md.append(f"- **Flags:** {', '.join(it.get('flags', [])) or '—'}  \n")
        md.append(f"- **Last Persona:** {it.get('last_persona','') or '—'}  \n")
        lp = it.get("last_prop", None)
        if lp is not None:
            md.append(f"- **Last Propensity:** {lp:.2f}  \n")
        md.append("\n## Trend Deltas\n\n")
        tw1, tw4 = it["deltas"]["trust"]["w1"], it["deltas"]["trust"]["w4"]
        lw1, lw4 = it["deltas"]["lev"]["w1"], it["deltas"]["lev"]["w4"]
        def _fmt(d): 
            return "—" if not d else f"{d['abs']:+.3f} ({'' if d['pct'] is None else str(d['pct'])+'%'} {d['dir']})"
        md.append(f"- Trust (WoW): {_fmt(tw1)}  \n")
        md.append(f"- Trust (4w):  {_fmt(tw4)}  \n")
        md.append(f"- Leverage (WoW): {_fmt(lw1)}  \n")
        md.append(f"- Leverage (4w):  {_fmt(lw4)}  \n")
        md.append("\n## Pledge History\n\n")
        if it["pledges"]["count"] == 0:
            md.append("_No pledges recorded in logs._\n")
        else:
            md.append("| Week | Amount | Earmark |\n| --- | ---: | --- |\n")
            for p in it["pledges"]["items"]:
                md.append(f"| {p['week']} | ${p['amount']:,.0f} | {p['earmark'] or ''} |\n")
        path = DOSSIER_DIR / f"{sch.replace(' ','_')}.md"
        path.write_text("".join(md), encoding="utf-8")

def main() -> None:
    # Reuse donor_report reconstruction logic (inline) but with extra series capture
    from .donor_report import (_iter_world_events, _read_finance_weeks, _school_from_row,
                               RX_PERSONA, RX_PROP, RX_PLEDGE, RX_EARMARK, _money_to_float,
                               TRUST_START, LEV_START, DECAY_RATE, TRUST_PLEDGE_D, LEV_PLEDGE_D)
    schools: Dict[str, Dict[str, Any]] = {}
    wmin, wmax = _read_finance_weeks()

    def ensure(sch: str) -> Dict[str, Any]:
        return schools.setdefault(sch, {
            "trust": TRUST_START, "lev": LEV_START,
            "pledges": [], "last_persona": "", "last_prop": None,
            "w_series_trust": [], "w_series_lev": [], "last_week": None
        })

    for row in _iter_world_events():
        notes = row.get("notes", "") or ""
        eid = (row.get("event_id") or "")
        if not any(k in eid.upper() for k in ("DONOR","ALUMNI","PLEDGE")) and ("Donor Persona:" not in notes and "pledge:" not in notes):
            continue
        try:
            week = int(float(row.get("week", "0")))
        except:
            continue
        sch = _school_from_row(row)
        if not sch: 
            continue
        st = ensure(sch)
        # decay
        if st["last_week"] is None: st["last_week"] = week
        else:
            dt = max(0, week - st["last_week"])
            if dt > 0:
                st["trust"] = 0.5 + (st["trust"] - 0.5) * (DECAY_RATE ** dt)
                st["lev"]   = st["lev"] * (DECAY_RATE ** dt)
                st["last_week"] = week
        # persona/prop
        mp = RX_PERSONA.search(notes)
        if mp: st["last_persona"] = mp.group(1)
        mp2 = RX_PROP.search(notes)
        if mp2:
            try: st["last_prop"] = float(mp2.group(1))
            except: pass
        # pledges
        mp3 = RX_PLEDGE.search(notes)
        if mp3:
            amt = _money_to_float(mp3.group(1))
            earm = ""
            me = RX_EARMARK.search(notes)
            if me: earm = me.group(1).strip()
            st["pledges"].append({"week": week, "amount": amt, "earmark": earm})
            st["trust"] = max(0.0, min(1.0, st["trust"] + TRUST_PLEDGE_D))
            st["lev"]   = max(-1.0, min(1.0, st["lev"] + LEV_PLEDGE_D))
        st["w_series_trust"].append((week, st["trust"]))
        st["w_series_lev"].append((week, st["lev"]))

    # tail decay to wmax
    for st in schools.values():
        if st["last_week"] is None: st["last_week"] = wmin
        tail = max(0, wmax - st["last_week"])
        if tail > 0:
            st["trust"] = 0.5 + (st["trust"] - 0.5) * (DECAY_RATE ** tail)
            st["lev"]   = st["lev"] * (DECAY_RATE ** tail)
            st["last_week"] = wmax
        st["w_series_trust"].append((wmax, st["trust"]))
        st["w_series_lev"].append((wmax, st["lev"]))

    # Build items
    items: List[Dict[str, Any]] = []
    for sch, st in schools.items():
        # deltas
        d_tr = {
            "w1": delta_tuple(st["w_series_trust"][-1][1], st["w_series_trust"][-2][1]) if len(st["w_series_trust"])>1 else None,
            "w4": delta_tuple(st["w_series_trust"][-1][1], st["w_series_trust"][max(0,len(st["w_series_trust"])-1-4)][1])
        }
        d_lv = {
            "w1": delta_tuple(st["w_series_lev"][-1][1], st["w_series_lev"][-2][1]) if len(st["w_series_lev"])>1 else None,
            "w4": delta_tuple(st["w_series_lev"][-1][1], st["w_series_lev"][max(0,len(st["w_series_lev"])-1-4)][1])
        }
        score = score_linear(st["trust"], st["lev"])
        pledges_total = sum(p["amount"] for p in st["pledges"])
        item = {
            "id": sch,
            "metrics": {"trust": round(st["trust"],3), "lev": round(st["lev"],3)},
            "deltas": {"trust": d_tr, "lev": d_lv},
            "score": score,
            "pledges": {"count": len(st["pledges"]), "total": int(round(pledges_total)), "items": st["pledges"]},
            "last_persona": st.get("last_persona",""),
            "last_prop": st.get("last_prop", None),
        }
        # flags
        flags = []
        if 0.45 <= st["trust"] <= 0.75 and st["lev"] >= 0.30: flags.append("opportunity")
        tw1 = d_tr["w1"]; 
        if st["trust"] < 0.45 or (tw1 and tw1.get("pct") is not None and tw1["pct"] < -5.0):
            flags.append("risk")
        item["flags"] = flags
        items.append(item)

    # Write CSV + dossiers + insights JSON
    # CSV
    from .donor_report import _write_csv as _write_csv_basic, _write_dossiers as _write_dossiers_basic
    # Reuse donor_report writers if present; otherwise inline backups:
    try:
        _write_csv_basic(items)
    except Exception:
        pass
    try:
        _write_dossiers_basic(items, (0,0))
    except Exception:
        # fallback minimal dossiers
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        for it in items:
            md = []
            md.append(f"# Donor Dossier — {it['id']}\n\n_Generated: {ts}_\n\n")
            md.append(f"- **Trust:** {it['metrics']['trust']:.3f}  \n")
            md.append(f"- **Leverage:** {it['metrics']['lev']:.3f}  \n")
            md.append(f"- **Score:** {it['score']} / 100  \n")
            md.append(f"- **Flags:** {', '.join(it.get('flags', [])) or '—'}  \n")
            path = DOSSIER_DIR / f"{it['id'].replace(' ','_')}.md"
            path.write_text("".join(md), encoding="utf-8")

    # Insights JSON (Assistant AD entry point)
    scope = {"schools": sorted([it["id"] for it in items]),
             "weeks": {"min": int(_read_finance_weeks()[0]), "max": int(_read_finance_weeks()[1])}}
    payload = envelope("donor", scope, items)
    write_json(OUT_JSON, payload)
    print(f"[donor_report_plus] wrote {OUT_CSV}, dossiers, and {OUT_JSON}")
    
if __name__ == "__main__":
    main()
