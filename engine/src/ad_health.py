# engine/src/ad_health.py
from __future__ import annotations
from pathlib import Path
import json, math

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine"
CONFIG = ENGINE / "config" / "ad_health.config"
STATE = ENGINE / "state"
FACTORS_JSON = STATE / "PRESTIGE_FACTORS.json"
DOCS = ROOT / "docs"
OUT_MD = DOCS / "AD_HEALTH_TRENDS.md"

DEFAULT_CFG = {
    "weights": {           # weights must sum to ~1.0 (we'll renorm safely)
        "dept_condition": 0.30,
        "fan_energy":     0.20,
        "finance_stab":   0.25,
        "coach_morale":   0.15,
        "board_support":  0.10
    },
    "output": {"top_n": 10}
}

def _read_json(p: Path, fallback: dict):
    try:
        if p.exists() and p.stat().st_size > 0:
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback

def _load_cfg():
    return _read_json(CONFIG, DEFAULT_CFG)

def _load_seed(name: str, default):
    p = STATE / f"{name}.json"
    return _read_json(p, default)

def _renorm(weights: dict) -> dict:
    s = sum(max(0.0, float(v)) for v in weights.values())
    if s <= 0: 
        return {k: 0.0 for k in weights}
    return {k: float(v)/s for k, v in weights.items()}

def _apply_mult(x: float, m: float) -> float:
    return max(0.0, min(1.0, x * m))

def compute_health():
    cfg   = _load_cfg()
    seeds = {
        "name":          _load_seed("name", {"School 029":"School 029", "State U":"State U"}),
        "programs":      _load_seed("programs", {}),         # not used directly here (future)
        "facilities":    _load_seed("facilities", {}),       # nostalgia/decay live here (pre-aggregated)
        "coach_morale":  _load_seed("coach_morale", {"School 029":0.50, "State U":0.50}),
        "board_support": _load_seed("board_support", {"School 029":0.50, "State U":0.50}),
        "ad_health":     _load_seed("ad_health", {}),        # previous snapshot (optional)
    }
    # Base components (stubbed demo values so this runs standalone)
    base = {
        "School 029": {"dept_condition":0.545, "fan_energy":0.344, "finance_stab":0.125},
        "State U":    {"dept_condition":0.545, "fan_energy":0.344, "finance_stab":0.345},
    }
    # Prestige multipliers (recruiting → fan_energy, donor → finance_stab)
    factors = _read_json(FACTORS_JSON, {})
    weights = _renorm(cfg.get("weights", {}))
    rows = []

    for school in sorted(base.keys()):
        comp = base[school].copy()
        # optional factors
        f = factors.get(school, {})
        rmult = float(f.get("recruiting_mult", 1.0))
        dmult = float(f.get("donor_mult", 1.0))

        fan_energy    = _apply_mult(comp["fan_energy"], rmult)
        finance_stab  = _apply_mult(comp["finance_stab"], dmult)
        dept_cond     = comp["dept_condition"]
        morale        = float(seeds["coach_morale"].get(school, 0.5))
        board         = float(seeds["board_support"].get(school, 0.5))

        score = (
            dept_cond    * weights.get("dept_condition", 0) +
            fan_energy   * weights.get("fan_energy", 0) +
            finance_stab * weights.get("finance_stab", 0) +
            morale       * weights.get("coach_morale", 0) +
            board        * weights.get("board_support", 0)
        )
        rows.append({
            "school": school,
            "ad_health": round(score, 3),
            "dept_cond": round(dept_cond, 3),
            "fan_energy": round(fan_energy, 3),
            "finance_stab": round(finance_stab, 3),
            "morale": round(morale, 3),
            "board": round(board, 3),
            "R×": round(rmult, 3),
            "D×": round(dmult, 3),
        })

    top_n = int(cfg.get("output", {}).get("top_n", 10))
    rows.sort(key=lambda r: r["ad_health"], reverse=True)
    rows = rows[:top_n]

    # Write Markdown
    DOCS.mkdir(exist_ok=True)
    lines = [
        "# Athletic Department Health — latest",
        "",
        "| School | AD Health | DeptCond | FanEnergy | FinanceStab | Morale | Board | R× | D× |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['school']} | {r['ad_health']:.3f} | {r['dept_cond']:.3f} | {r['fan_energy']:.3f} "
            f"| {r['finance_stab']:.3f} | {r['morale']:.3f} | {r['board']:.3f} | {r['R×']:.3f} | {r['D×']:.3f} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("OK: wrote", OUT_MD)

if __name__ == "__main__":
    compute_health()
