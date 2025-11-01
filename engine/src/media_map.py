from __future__ import annotations
import re
import os, json, math, glob, datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

ROOT = Path(__file__).resolve().parents[2]  # ...\College_AD_...\ (workspace root)
CFG_PATH = ROOT / "engine" / "config" / "media_map.config.json"
MEDIA_DIR = ROOT / "logs" / "MEDIA"
DOCS_DIR  = ROOT / "docs"
OUT_PATH  = DOCS_DIR / "MEDIA_REACH_MAP.md"

def _now_utc() -> datetime.datetime:
    return datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

def load_config() -> Dict[str, Any]:
    if not CFG_PATH.exists():
        return {
            "grid_size": 21,
            "max_extra_radius": 6,
            "base_radii": {"Local":3,"Regional":6,"National":9},
            "weights": {
                "status":{"amplify":1.0,"downplay":0.4,"new":0.2,"ignore":0.0},
                "reach":{"Local":1.0,"Regional":1.2,"National":1.5}
            },
            "decay_days_half_life": 28,
            "charset": " .:-=+*#%@",
            "show_axes": True,
            "max_items": 500
        }
    with open(CFG_PATH, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def _load_json(p: Path) -> Dict[str, Any] | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def load_media_items(cfg: Dict[str,Any]) -> List[Dict[str,Any]]:
    if not MEDIA_DIR.exists():
        return []
    files = sorted(MEDIA_DIR.glob("*.media.json"), key=os.path.getmtime)
    if cfg.get("max_items"):
        files = files[-int(cfg["max_items"]):]
    items = []
    for fp in files:
        d = _load_json(fp)
        if not d: 
            continue
        # Expect keys: 'when', 'reach' ('Local'|'Regional'|'National'), 'status' ('new','amplify','downplay','ignore')
        # Fallbacks:
        d.setdefault("status", "new")
        # some earlier files used 'source'; treat it as reach if present
        if "reach" not in d and "source" in d:
            d["reach"] = d["source"]
        items.append(d)
    return items

def _parse_when(s: str) -> datetime.datetime | None:
    # Accepts ISO-like or missing tz; best effort
    try:
        # 2025-10-31T11:28:52Z
        if s.endswith("Z"):
            s = s.replace("Z","+00:00")
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return None

def _age_weight(when: str | None, half_life_days: float) -> float:
    if not when:
        return 1.0
    t = _parse_when(when)
    if not t:
        return 1.0
    if not t.tzinfo:
        t = t.replace(tzinfo=datetime.timezone.utc)
    dt_days = max(0.0, (_now_utc() - t).total_seconds() / 86400.0)
    # exponential decay: weight = 0.5^(days/half_life)
    return math.pow(0.5, dt_days / max(1e-6, half_life_days))

def aggregate_reach_scores(items: List[Dict[str,Any]], cfg: Dict[str,Any]) -> Dict[str,float]:
    w_status = cfg["weights"]["status"]
    w_reach  = cfg["weights"]["reach"]
    half     = float(cfg.get("decay_days_half_life", 28))
    sums: Dict[str,float] = {"Local":0.0,"Regional":0.0,"National":0.0}
    for it in items:
        reach = it.get("reach","Local")
        if reach not in sums:
            continue
        status = it.get("status","new")
        s_w = w_status.get(str(status), 0.0)
        r_w = w_reach.get(str(reach), 1.0)
        a_w = _age_weight(it.get("when"), half)
        sums[reach] += s_w * r_w * a_w
    # normalize to 0..1 by dividing by max (if any)
    maxv = max(1e-9, max(sums.values()))
    for k in sums:
        sums[k] = min(1.0, sums[k] / maxv)
    return sums

def compute_radii(scores: Dict[str,float], cfg: Dict[str,Any]) -> Dict[str,float]:
    base = cfg["base_radii"]
    extra = float(cfg["max_extra_radius"])
    return {
        "Local":    float(base["Local"])    + extra * scores["Local"],
        "Regional": float(base["Regional"]) + extra * scores["Regional"],
        "National": float(base["National"]) + extra * scores["National"]
    }

def _intensity_at(r: float, radii: Dict[str,float]) -> float:
    # Map distance to an intensity 0..1 based on which zone the cell falls into
    # closer to center = higher intensity
    if r <= radii["Local"]:
        # inner third highest
        return 0.85 * (1.0 - r/max(1e-6, radii["Local"]))
    elif r <= radii["Regional"]:
        span = max(1e-6, radii["Regional"] - radii["Local"])
        return 0.55 * (1.0 - (r - radii["Local"]) / span)
    elif r <= radii["National"]:
        span = max(1e-6, radii["National"] - radii["Regional"])
        return 0.25 * (1.0 - (r - radii["Regional"]) / span)
    else:
        return 0.0

def render_ascii_map(radii: Dict[str,float], cfg: Dict[str,Any]) -> str:
    N = int(cfg["grid_size"])
    if N % 2 == 0:
        N += 1
    half = N // 2
    charset = cfg["charset"]
    # ensure at least 2 chars
    if len(charset) < 2:
        charset = " .#"
    lines: List[str] = []
    for y in range(N):
        row_chars: List[str] = []
        for x in range(N):
            dx = x - half
            dy = y - half
            r = math.hypot(dx, dy)
            val = _intensity_at(r, radii) # 0..1
            idx = int(val * (len(charset) - 1) + 1e-9)
            ch = charset[idx]
            # mark center
            if dx == 0 and dy == 0:
                ch = "◎"  # school center
            row_chars.append(ch)
        lines.append("".join(row_chars))
    if cfg.get("show_axes", True):
        # draw + on axes (skip center already ◎)
        mid = list(lines[half])
        for i in range(N):
            # vertical axis
            if i != half:
                row = list(lines[i])
                row[half] = "┆"
                lines[i] = "".join(row)
            # horizontal axis
            if i != half:
                mid[i] = "┄"
        mid[half] = "◎"
        lines[half] = "".join(mid)
    return "\n".join(lines)

def write_doc(scores: Dict[str,float], radii: Dict[str,float], art: str) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    header = "# Media Reach — latest\n\n"
    legend = (
        "| Zone | Score (0..1) | Radius (cells) |\n"
        "|---|---:|---:|\n"
        f"| Local | {scores['Local']:.2f} | {radii['Local']:.1f} |\n"
        f"| Regional | {scores['Regional']:.2f} | {radii['Regional']:.1f} |\n"
        f"| National | {scores['National']:.2f} | {radii['National']:.1f} |\n\n"
    )
    block = "```\n" + art + "\n```\n"
    (OUT_PATH).write_text(header + legend + block, encoding="utf-8")

def build() -> Tuple[Dict[str,float], Dict[str,float], str]:
    cfg = load_config()
    items = load_media_items(cfg)
    scores = aggregate_reach_scores(items, cfg)
    radii  = compute_radii(scores, cfg)
    art    = render_ascii_map(radii, cfg)
    write_doc(scores, radii, art)
    return scores, radii, art

def main():
    # simple: always build
    build()

if __name__ == "__main__":
    main()


# --- permissive JSON loader override (appended by setup) ---
def __load_config_permissive():
    import json, re
    # BOM-safe read
    with open(CFG_PATH, "r", encoding="utf-8-sig") as f:
        txt = f.read()
    # Strip // line comments and /* */ block comments
    txt = re.sub(r"//.*?$", "", txt, flags=re.MULTILINE)
    txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.DOTALL)
    # Tolerate single quotes -> normalize to double quotes
    txt = txt.replace("'", '"')
    # Remove trailing commas before } or ]
    txt = re.sub(r",\s*(\}|\])", r"\1", txt)
    return json.loads(txt)

# Force module-level load_config to use the permissive version
load_config = __load_config_permissive
# --- end override ---



# --- patch: JSON export for recruiting and analytics ---
import json, pathlib
def _export_json(scores, radii):
    docs = pathlib.Path(DOCS_DIR)
    docs.mkdir(exist_ok=True)
    out_json = docs / "MEDIA_REACH.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"scores": scores, "radii": radii}, f, ensure_ascii=False, indent=2)
# --- end patch ---

# ===== v17.9.1 media_map defaults hardening (append-only, safe) =====
try:
    import copy, json
    from pathlib import Path
except Exception:
    pass

_MEDIA_MAP_DEFAULTS = {
    "grid_size": 21,
    "base_radii": {"Local": 9.0, "Regional": 6.0, "National": 9.0},
    "base_radius": 6.0,
    "max_extra_radius": 3.0,
    "local_min_score": 0.85,
    "regional_min_score": 0.55,
    "national_min_score": 0.25,
    "weights": {
        "status": {"amplify": 1.0, "neutral": 0.25, "ignore": 0.10},
        "tier":   {"Local": 1.0, "Regional": 0.7, "National": 0.5},
        "reach":  {"Local": 1.0, "Regional": 0.7, "National": 0.5}
    },
    "charset": {
        "center": "*", "ring1": ".", "ring2": ":", "ring3": "+", "ring4": "-",
        "border": "|", "empty": " "
    }
}

def _deepmerge(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deepmerge(out[k], v)
        else:
            out[k] = v
    return out

def _load_media_map_cfg_file():
    try:
        cfg_path = Path(__file__).resolve().parents[1] / "config" / "media_map.config.json"
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

# monkey-patch a robust loader that callers can use
def load_media_map_cfg():
    return _deepmerge(_MEDIA_MAP_DEFAULTS, _load_media_map_cfg_file())
# ===== end v17.9.1 defaults hardening =====
