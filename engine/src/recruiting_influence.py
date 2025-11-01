from __future__ import annotations
import json, math
from pathlib import Path
from typing import Dict, Tuple

ROOT = Path(__file__).resolve().parents[1]
CFG  = ROOT / "config" / "recruiting_influence.config.json"
MRJ  = Path.cwd() / "docs" / "MEDIA_REACH.json"             # produced by media_map
OUT  = ROOT / "state" / "recruiting_modifiers.json"
RPT  = Path.cwd() / "docs" / "RECRUITING_READOUT.md"

def _read_json(p: Path, encoding: str = "utf-8-sig"):
    if not p.exists():
        return None
    with p.open("r", encoding=encoding) as f:
        return json.load(f)

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def load_config() -> Dict:
    cfg = _read_json(CFG) or {}
    # defaults
    cfg.setdefault("base", 1.0)
    cfg.setdefault("floor", 0.70)
    cfg.setdefault("cap", 1.35)
    cfg.setdefault("alpha_local", 0.15)
    cfg.setdefault("alpha_regional", 0.25)
    cfg.setdefault("alpha_national", 0.35)
    cfg.setdefault("blend_weights", {"Local":0.50,"Regional":0.35,"National":0.15})
    cfg.setdefault("apply_cap_first", True)
    return cfg

def load_media_reach() -> Dict:
    # MEDIA_REACH.json was created earlier by media_map; treat missing as zeros
    d = _read_json(MRJ)
    if not d:
        return {"scores":{"Local":0.0,"Regional":0.0,"National":0.0},
                "radii":{"Local":0.0,"Regional":0.0,"National":0.0}}
    return d

def zone_multiplier(score: float, alpha: float, base: float, floor: float, cap: float, apply_cap_first: bool) -> float:
    raw = base * (1.0 + alpha * score)
    return clamp(raw, floor, cap) if apply_cap_first else raw

def compute() -> Tuple[Dict[str,float], Dict[str,float], Dict]:
    cfg = load_config()
    d   = load_media_reach()
    s   = d.get("scores", {})
    radii = d.get("radii", {})

    mult = {
        "Local":    zone_multiplier(s.get("Local",0.0),    cfg["alpha_local"],    cfg["base"], cfg["floor"], cfg["cap"], cfg["apply_cap_first"]),
        "Regional": zone_multiplier(s.get("Regional",0.0), cfg["alpha_regional"], cfg["base"], cfg["floor"], cfg["cap"], cfg["apply_cap_first"]),
        "National": zone_multiplier(s.get("National",0.0), cfg["alpha_national"], cfg["base"], cfg["floor"], cfg["cap"], cfg["apply_cap_first"]),
    }

    w = cfg.get("blend_weights", {"Local":0.5,"Regional":0.35,"National":0.15})
    total_w = sum(w.values()) or 1.0
    global_mult = sum(mult[z]*w.get(z,0.0) for z in ("Local","Regional","National"))/total_w
    result = {"multipliers": mult, "global_multiplier": global_mult}
    return result, radii, cfg

def write_state(result: Dict):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

def write_report(result: Dict, radii: Dict, cfg: Dict):
    RPT.parent.mkdir(parents=True, exist_ok=True)
    m = result["multipliers"]
    lines = []
    lines.append("# Recruiting — Media Reach Influence (latest)")
    lines.append("")
    lines.append("| Zone | Reach Score → Multiplier |")
    lines.append("|---|---:|")
    for z in ("Local","Regional","National"):
        lines.append(f"| {z} | {m[z]:.2f}x |")
    lines.append("")
    lines.append(f"**Global Blend:** `{result['global_multiplier']:.2f}x`  ")
    lines.append("")
    lines.append("**Radii (cells)**")
    lines.append("")
    lines.append("| Local | Regional | National |")
    lines.append("|---:|---:|---:|")
    lines.append(f"| {radii.get('Local',0)} | {radii.get('Regional',0)} | {radii.get('National',0)} |")
    lines.append("")
    lines.append("**Config Snapshot**")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(cfg, ensure_ascii=False, indent=2))
    lines.append("```")
    with RPT.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# Convenience: pure function to apply multiplier externally
def apply_probability(base_prob: float, zone: str, result: Dict | None = None) -> float:
    """
    base_prob in [0..1], zone one of Local/Regional/National.
    Returns clamped prob after applying the zone multiplier.
    """
    if result is None:
        result, _, _ = compute()
    mult = result["multipliers"].get(zone, 1.0)
    return clamp(base_prob * mult, 0.0, 1.0)

if __name__ == "__main__":
    res, radii, cfg = compute()
    write_state(res)
    write_report(res, radii, cfg)


# ===================== v17.9 media reach integration (APPENDED) =====================
try:
    from pathlib import Path
    import json
except Exception:
    pass

def _mr_cfg_path():
    try:
        return Path(__file__).resolve().parents[1] / "config" / "MEDIA_REACH.json"
    except Exception:
        return None

def _load_media_reach_cfg():
    fp = _mr_cfg_path()
    try:
        if fp and fp.exists():
            with open(fp, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    # safe defaults
    return {
        "multipliers": {"Local": 1.0, "Regional": 0.9, "National": 0.8},
        "global_multiplier": 1.0
    }

_MEDIA_REACH_CFG = _load_media_reach_cfg()

def media_multiplier(zone: str) -> float:
    """Return multiplier from MEDIA_REACH.json; falls back to ~[1.0,0.9,0.8]."""
    try:
        mults = (_MEDIA_REACH_CFG.get("multipliers") or {})
        g = float(_MEDIA_REACH_CFG.get("global_multiplier", 1.0))
        m = float(mults.get(zone, 1.0))
        out = max(0.0, m * g)
        return out
    except Exception:
        return 1.0

def apply_media_reach_to_probability(base_prob: float, zone: str) -> float:
    """Clamp 0..1 after applying zone multiplier."""
    try:
        m = media_multiplier(zone)
        out = base_prob * m
        if out < 0.0: out = 0.0
        if out > 1.0: out = 1.0
        return out
    except Exception:
        return base_prob
# =================== end v17.9 media reach integration (APPENDED) ===================
