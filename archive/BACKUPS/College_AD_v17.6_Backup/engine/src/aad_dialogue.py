# engine/src/aad_dialogue.py
# v17.6 – AAD (Assistant AD) console helper
# Standalone, friendly phrasing, no external deps beyond donors.summary.json

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
LOGS = ROOT / "logs"

SUMMARY_PATH = DATA / "donors.summary.json"   # produced by donor_report_plus
DONORS_PATH  = DATA / "donors.json"           # produced by seed_donors (optional)


# -------------------------------
# I/O utilities
# -------------------------------
def load_json(p: Path) -> Optional[dict]:
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as f:
        return json.load(f)


# -------------------------------
# Light scoring / labels
# -------------------------------
def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))

def score_label(x: float) -> str:
    # x is 0..100
    if x >= 80: return "Excellent"
    if x >= 65: return "Good"
    if x >= 50: return "Fair"
    if x >= 35: return "Wobbly"
    return "At-Risk"

def risk_tag(trust: float, leverage: float, score: float) -> bool:
    return (trust < 0.4) or (score < 40) or (leverage < 0.05 and score < 50)

def opp_tag(trust: float, leverage: float, score: float) -> bool:
    # warm but under-leveraged
    return (trust >= 0.6) and (leverage < 0.25) and (score >= 50)


# -------------------------------
# NLG helpers (friendly phrasing)
# -------------------------------
def nlg_detail(d: Dict[str, Any]) -> str:
    """
    Turn a single school's donor summary dict into a readable, coach-friendly line.
    Expects keys: id, metrics:{trust, lev}, score, flags, pledges:{count,total}
    """
    school = d.get("id", "Unknown")
    trust = float(d.get("metrics", {}).get("trust", 0.5))
    lev   = float(d.get("metrics", {}).get("lev", 0.1))
    score = float(d.get("score", 50))
    label = score_label(score)

    flags = d.get("flags", [])
    flags_txt = "none" if not flags else ", ".join(flags)

    pledges = d.get("pledges", {})
    pcount  = int(pledges.get("count", 0))
    ptotal  = float(pledges.get("total", 0.0))

    # quick advice
    if trust < 0.4:
        tip = "Start soft—quick check-in, share a small win, rebuild confidence."
    elif lev < 0.1 and trust >= 0.6:
        tip = "They’re warm but not influential yet—invite them into a small committee."
    elif score >= 65:
        tip = "Good footing—consider a targeted ask tied to a visible outcome."
    else:
        tip = "Keep a steady cadence—one tangible outcome before the next ask."

    return (f"{school}: trust {trust:.2f}, leverage {lev:.2f}, score {int(round(score))} ({label}). "
            f"Flags: {flags_txt}. Pledges: {pcount} totaling ${ptotal:,.0f}. Suggestion: {tip}")


def nlg_opening(summary: dict) -> str:
    items: List[dict] = summary.get("items", [])
    if not items:
        return "I don’t have any donor relationship data yet."
    trusts  = [float(i.get("metrics", {}).get("trust", 0.5)) for i in items]
    levs    = [float(i.get("metrics", {}).get("lev", 0.1)) for i in items]
    scores  = [float(i.get("score", 50)) for i in items]
    avg_t   = sum(trusts)/len(trusts)
    avg_l   = sum(levs)/len(levs)
    avg_s   = sum(scores)/len(scores)
    return (f"Alright, Coach—what’s on your mind? We’re tracking {len(items)} donor relationships program-wide. "
            f"Avg trust {avg_t:.2f}, leverage {avg_l:.2f}, score {int(round(avg_s))}.")


# -------------------------------
# Data shaping (tolerant to missing fields)
# -------------------------------
def normalize_items(summary: dict) -> List[dict]:
    out: List[dict] = []
    for raw in summary.get("items", []):
        school = raw.get("id") or raw.get("school") or "Unknown"
        trust  = float(raw.get("metrics", {}).get("trust", 0.5))
        lev    = float(raw.get("metrics", {}).get("lev", 0.1))
        score  = float(raw.get("score", 50))
        flags  = raw.get("flags", [])
        pledges = raw.get("pledges", {"count": 0, "total": 0})
        out.append({
            "id": school,
            "metrics": {"trust": trust, "lev": lev},
            "score": score,
            "flags": flags,
            "pledges": {
                "count": int(pledges.get("count", 0)),
                "total": float(pledges.get("total", 0.0))
            }
        })
    return out


# -------------------------------
# Command handlers
# -------------------------------
def handle_overview(summary: dict) -> str:
    return nlg_opening(summary)

def handle_risks(summary: dict) -> str:
    items = normalize_items(summary)
    risky = [i for i in items if risk_tag(i["metrics"]["trust"], i["metrics"]["lev"], i["score"])]
    if not risky:
        return "No donors on the watchlist right now."
    # list concise bullets
    lines = []
    for r in risky[:8]:
        t = r["metrics"]["trust"]; l = r["metrics"]["lev"]; s = r["score"]
        lines.append(f"- {r['id']}: trust {t:.2f}, lev {l:.2f}, score {int(round(s))} ({score_label(s)})")
    if len(risky) > 8:
        lines.append(f"...and {len(risky)-8} more.")
    return "Watchlist:\n" + "\n".join(lines)

def handle_opportunities(summary: dict) -> str:
    items = normalize_items(summary)
    opps = [i for i in items if opp_tag(i["metrics"]["trust"], i["metrics"]["lev"], i["score"])]
    if not opps:
        return "No new donor opportunities this cycle."
    lines = []
    for r in opps[:8]:
        lines.append(f"- {r['id']}: warm relationship; consider a low-risk, specific ask.")
    if len(opps) > 8:
        lines.append(f"...and {len(opps)-8} more.")
    return "Potential opportunities:\n" + "\n".join(lines)

def handle_school(summary: dict, name: str) -> str:
    items = normalize_items(summary)
    # loose match on school name
    name_norm = name.lower().strip()
    best = None
    for i in items:
        if i["id"].lower() == name_norm:
            best = i; break
        if name_norm in i["id"].lower():
            best = i
    if not best:
        return f"I couldn't find anything for '{name}'."
    return nlg_detail(best)


# -------------------------------
# Simple intent router
# -------------------------------
def route(summary: dict, user: str) -> str:
    q = user.strip().lower()

    if q in {"exit", "quit", "q"}:
        return "__EXIT__"

    if any(k in q for k in ["how are donor", "relationships", "overall", "summary"]):
        return handle_overview(summary)

    if any(k in q for k in ["most at risk", "at risk", "watchlist", "who's at risk", "who is at risk"]):
        return handle_risks(summary)

    if any(k in q for k in ["opportunity", "opportunities", "who can we talk", "who can we call"]):
        return handle_opportunities(summary)

    m = re.search(r"(tell me about|report on|show|details for)\s+(.*)", q)
    if m:
        school = m.group(2)
        return handle_school(summary, school)

    # fallbacks
    if "state u" in q:
        return handle_school(summary, "State U")

    # polite prompt for options
    return "I can give you donor summaries, risks, opportunities, or a specific school report."


# -------------------------------
# Main REPL
# -------------------------------
def main() -> None:
    summary = load_json(SUMMARY_PATH) or {"items": []}

    print("Assistant AD ready for duty. Type 'exit' to quit.")
    print(nlg_opening(summary))

    while True:
        try:
            user = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAAD: Until next time, Coach.")
            break

        if not user:
            continue

        out = route(summary, user)
        if out == "__EXIT__":
            print("AAD: Until next time, Coach.")
            break
        print(f"\nAAD: {out}")

if __name__ == "__main__":
    main()
