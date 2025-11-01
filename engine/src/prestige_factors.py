# engine/src/prestige_factors.py
from __future__ import annotations
from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[2]  # workspace root
DOCS = ROOT / "docs"
STATE = ROOT / "engine" / "state"
PRESTIGE_MD = DOCS / "AD_PRESTIGE_TRENDS.md"
FACTORS_JSON = STATE / "PRESTIGE_FACTORS.json"
FACTORS_MD = DOCS / "PRESTIGE_FACTORS.md"

TABLE_ROW = re.compile(r'^\|\s*(?P<school>.+?)\s*\|\s*(?P<ad_cp>[\d.]+)\s*\|\s*(?P<ad_hr>[\d.]+)\s*\|', re.M)

def _parse_prestige_rows(md: str):
    for m in TABLE_ROW.finditer(md):
        school = m.group("school").strip()
        ad_cp = float(m.group("ad_cp"))
        ad_hr = float(m.group("ad_hr"))
        yield school, ad_cp, ad_hr

def _clamp(x, lo, hi): 
    return lo if x < lo else hi if x > hi else x

def compute_factors():
    if not PRESTIGE_MD.exists():
        raise SystemExit(f"[prestige_factors] Missing {PRESTIGE_MD} — run `python -m engine.src.ad_prestige --weekly` first.")
    md = PRESTIGE_MD.read_text(encoding="utf-8")
    rows = list(_parse_prestige_rows(md))
    if not rows:
        raise SystemExit("[prestige_factors] Could not parse prestige table.")

    out = {}
    for school, ad_cp, ad_hr in rows:
        # Recruiting multiplier from CURRENT prestige (AD_CP) → 0.90..1.10
        rmult = _clamp(0.90 + 0.20 * (ad_cp / 100.0), 0.90, 1.10)
        # Donor appetite from HISTORICAL prestige (AD_HR) → 0.92..1.15
        dmult = _clamp(0.92 + 0.23 * (ad_hr / 100.0), 0.92, 1.15)
        out[school] = {"recruiting_mult": round(rmult, 3), "donor_mult": round(dmult, 3)}

    STATE.mkdir(parents=True, exist_ok=True)
    FACTORS_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # Pretty Markdown
    lines = [
        "# Prestige Factors — multipliers",
        "",
        "| School | Recruiting× | Donor× | Source: AD_CP | Source: AD_HR |",
        "|---|---:|---:|---:|---:|",
    ]
    for school, ad_cp, ad_hr in rows:
        r = out[school]["recruiting_mult"]
        d = out[school]["donor_mult"]
        lines.append(f"| {school} | {r:.3f} | {d:.3f} | {ad_cp:.1f} | {ad_hr:.1f} |")
    FACTORS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[prestige_factors] OK → {FACTORS_JSON}")
    print(f"[prestige_factors] Wrote {FACTORS_MD}")

if __name__ == "__main__":
    compute_factors()
