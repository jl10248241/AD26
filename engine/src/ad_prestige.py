from __future__ import annotations
import json, math, random, argparse
from pathlib import Path
from typing import Dict, Any, Tuple, List
# engine/src/ad_prestige.py
import json, math, random, argparse
from pathlib import Path
from typing import Dict, Any, Tuple, List

# ---------- Paths
WS_ROOT = Path(__file__).resolve().parents[1].parents[0]  # workspace root
CFG_PATH = WS_ROOT / "engine" / "configs" / "ad_prestige.config.json"
STATE_PATH = WS_ROOT / "engine" / "state" / "ad_prestige_state.json"
DOC_MAIN = WS_ROOT / "docs" / "AD_PRESTIGE_TRENDS.md"
DOC_ALIAS = WS_ROOT / "docs" / "AD_PRESTIGE.md"

# ---------- IO helpers
def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- Config (built-in defaults so it always runs)
_BUILTIN_CFG: Dict[str, Any] = {
    "smoothing": {"alpha_current": 0.30, "alpha_historical": 0.06},
    "sports": {
        "football": {"weight": 0.40, "visibility": 1.00},
        "mens_bb": {"weight": 0.20, "visibility": 0.90},
        "womens_bb": {"weight": 0.10, "visibility": 0.75},
        "baseball": {"weight": 0.07, "visibility": 0.60},
        "softball": {"weight": 0.05, "visibility": 0.55},
        "soccer": {"weight": 0.05, "visibility": 0.50},
        "track": {"weight": 0.05, "visibility": 0.40},
        "others": {"weight": 0.08, "visibility": 0.30}
    },
    "facilities": {
        "decay_per_week": {
            "stadium": 0.0005, "arena": 0.0007, "weight_room": 0.0015, "practice": 0.0010, "none": 0.0
        },
        "nostalgia": {
            "stadium": {"max": 0.20, "build_per_season": 0.02},
            "arena": {"max": 0.12, "build_per_season": 0.015},
            "weight_room": {"max": 0.00, "build_per_season": 0.00},
            "practice": {"max": 0.00, "build_per_season": 0.00}
        },
        "facility_to_sport": {
            "football": "stadium", "mens_bb": "arena", "womens_bb": "arena",
            "baseball": "stadium", "softball": "stadium", "soccer": "stadium",
            "track": "stadium", "others": "practice"
        },
        "cp_facility_scale": 8.0,
        "hr_nostalgia_scale": 100.0
    },
    "ui": { "stars_thresholds": [20,35,50,65,80,90,96,99], "markdown_limit_rows": 12 }
}

def load_config() -> Dict[str, Any]:
    cfg = _read_json(CFG_PATH, {})
    if not cfg:
        # Fall back silently to built-in defaults
        cfg = _BUILTIN_CFG
    return cfg

def load_state() -> Dict[str, Any]:
    return _read_json(STATE_PATH, {"schools": {}})

def save_state(state: Dict[str, Any]) -> None:
    _write_json(STATE_PATH, state)

# ---------- Core helpers
def _sports_in_cfg(cfg: Dict[str, Any]) -> List[str]:
    return list(cfg["sports"].keys())

def ensure_school(state: Dict[str, Any], cfg: Dict[str, Any], school: str) -> None:
    schools = state.setdefault("schools", {})
    if school in schools:
        return
    rng = random.Random(hash(school) & 0xFFFFFFFF)
    sports = _sports_in_cfg(cfg)
    schools[school] = {
        "programs": {
            s: {
                "current_prestige": float(max(0, min(100, 55 + rng.randint(-10, 10)))),
                "historical_rating": float(max(0, min(100, 60 + rng.randint(-10, 10)))),
                "facility": { "condition": 0.80 + rng.random() * 0.10, "nostalgia": 0.05 * rng.random() }
            } for s in sports
        },
        "meta": { "seasons": 0, "weeks": 0 }
    }

def rollup_department(school_data: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, float]:
    weights = cfg["sports"]
    cp_sum = hr_sum = w_sum = 0.0
    for sport, data in school_data["programs"].items():
        w = float(weights.get(sport, {}).get("weight", 0.0))
        vis = float(weights.get(sport, {}).get("visibility", 1.0))
        cp = float(data["current_prestige"])
        hr = float(data["historical_rating"])
        cp_sum += w * (cp * vis)
        hr_sum += w * hr
        w_sum += w
    if w_sum <= 0: 
        return 0.0, 0.0
    return cp_sum / w_sum, hr_sum / w_sum

def _ema(prev: float, new: float, alpha: float) -> float:
    return (1 - alpha) * prev + alpha * new

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def _facility_channel(cfg: Dict[str, Any], sport: str) -> str:
    return cfg["facilities"]["facility_to_sport"].get(sport, "practice")

def _weekly_decay_facility(sport_data: Dict[str, Any], chan: str, cfg: Dict[str, Any]) -> None:
    decay = float(cfg["facilities"]["decay_per_week"].get(chan, 0.0))
    cond = float(sport_data["facility"]["condition"])
    sport_data["facility"]["condition"] = _clamp01(cond - decay)

def _facility_cp_bonus(sport_data: Dict[str, Any], chan: str, cfg: Dict[str, Any]) -> float:
    cond = float(sport_data["facility"]["condition"])
    scale = float(cfg["facilities"]["cp_facility_scale"])
    return scale * (1 / (1 + math.exp(-10 * (cond - 0.7))) - 0.5) * 2.0

def _nostalgia_season_gain(sport_data: Dict[str, Any], chan: str, cfg: Dict[str, Any]) -> float:
    spec = cfg["facilities"]["nostalgia"].get(chan, {"max": 0.0, "build_per_season": 0.0})
    cur = float(sport_data["facility"]["nostalgia"])
    return float(min(spec["max"], cur + spec["build_per_season"]))

def weekly_update(state: Dict[str, Any], cfg: Dict[str, Any], school: str,
                  week_inputs: Dict[str, Dict[str, float]] | None = None) -> None:
    ensure_school(state, cfg, school)
    alpha = float(cfg["smoothing"]["alpha_current"])
    sports = _sports_in_cfg(cfg)
    rng = random.Random(hash((school, state["schools"][school]["meta"]["weeks"])) & 0xFFFFFFFF)

    for s in sports:
        sd = state["schools"][school]["programs"][s]
        chan = _facility_channel(cfg, s)
        _weekly_decay_facility(sd, chan, cfg)
        cp = float(sd["current_prestige"])

        if week_inputs and s in week_inputs:
            res = float(week_inputs[s].get("results", 0.0))
            rec = float(week_inputs[s].get("recruit", 0.0))
        else:
            res = 0.15 * (rng.random() * 2 - 1)
            rec = 0.10 * (rng.random() * 2 - 1)

        base_score = 100.0 * _clamp01(0.5 + 0.35 * res + 0.15 * rec)
        cp_bonus = _facility_cp_bonus(sd, chan, cfg)
        new_cp = _ema(cp, base_score + cp_bonus, alpha)
        sd["current_prestige"] = float(max(0.0, min(100.0, new_cp)))

    state["schools"][school]["meta"]["weeks"] += 1

def season_end_update(state: Dict[str, Any], cfg: Dict[str, Any], school: str,
                      season_legacy: Dict[str, float] | None = None) -> None:
    ensure_school(state, cfg, school)
    alpha = float(cfg["smoothing"]["alpha_historical"])
    sports = _sports_in_cfg(cfg)
    rng = random.Random(hash((school, "season", state["schools"][school]["meta"]["seasons"])) & 0xFFFFFFFF)

    for s in sports:
        sd = state["schools"][school]["programs"][s]
        hr = float(sd["historical_rating"])
        cp = float(sd["current_prestige"])
        chan = _facility_channel(cfg, s)

        if season_legacy and s in season_legacy:
            legacy = float(season_legacy[s])
        else:
            legacy = _clamp01((cp / 100.0) ** 0.7 + 0.05 * (rng.random() - 0.5))

        next_nost = _nostalgia_season_gain(sd, chan, cfg)
        sd["facility"]["nostalgia"] = next_nost
        nostalgia_points = next_nost * float(cfg["facilities"]["hr_nostalgia_scale"])

        new_hr = _ema(hr, 100.0 * legacy + nostalgia_points, alpha)
        sd["historical_rating"] = float(max(0.0, min(100.0, new_hr)))

    state["schools"][school]["meta"]["seasons"] += 1

def _star_band(x: float, bands: List[int]) -> str:
    stars = 1
    for t in bands:
        if x >= t: stars += 1
    return "★" * stars

def write_markdown(state: Dict[str, Any], cfg: Dict[str, Any]) -> Path:
    DOC_MAIN.parent.mkdir(parents=True, exist_ok=True)
    bands = cfg["ui"]["stars_thresholds"]
    limit = int(cfg["ui"]["markdown_limit_rows"])

    rows = []
    for school, data in state.get("schools", {}).items():
        ad_cp, ad_hr = rollup_department(data, cfg)
        rows.append((school, ad_cp, ad_hr))
    rows.sort(key=lambda r: (-r[1], r[0]))

    header = "# AD Prestige — Current vs Historical\n\n"
    table_header = "| School | AD_CP | AD_HR | CP_Stars | HR_Stars |\n|---|---:|---:|:---:|:---:|\n"
    lines = []
    for school, ad_cp, ad_hr in rows[:limit]:
        lines.append(f"| {school} | {ad_cp:.1f} | {ad_hr:.1f} | {_star_band(ad_cp, bands)} | {_star_band(ad_hr, bands)} |")

    content = header + table_header + "\n".join(lines) + "\n"
    DOC_MAIN.write_text(content, encoding="utf-8")
    # Also mirror to the short name for convenience
    DOC_ALIAS.write_text(content, encoding="utf-8")
    return DOC_MAIN

# ---------- CLI wrappers (support both styles)
def cli_seed():
    cfg = load_config()
    st = load_state()
    for s in ("State U", "School 029"):
        ensure_school(st, cfg, s)
    save_state(st)
    print("Seeded:", ", ".join(st["schools"].keys()))

def cli_weekly():
    cfg = load_config()
    st = load_state()
    for s in st.get("schools", {}).keys():
        weekly_update(st, cfg, s)
    save_state(st)
    p = write_markdown(st, cfg)
    print("Weekly OK →", p.as_posix())

def cli_season():
    cfg = load_config()
    st = load_state()
    for s in st.get("schools", {}).keys():
        season_end_update(st, cfg, s)
    save_state(st)
    p = write_markdown(st, cfg)
    print("Season OK →", p.as_posix())

def cli_report():
    cfg = load_config()
    st = load_state()
    p = write_markdown(st, cfg)
    print("Report OK →", p.as_posix())

def main():
    ap = argparse.ArgumentParser(prog="ad_prestige", add_help=True)
    ap.add_argument("--mode", choices=["seed","weekly","season","report"], help="(Alt) run mode")
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--weekly", action="store_true")
    ap.add_argument("--season", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    # prefer explicit flags; fall back to --mode
    if args.seed or (args.mode == "seed"):   return cli_seed()
    if args.weekly or (args.mode == "weekly"): return cli_weekly()
    if args.season or (args.mode == "season"): return cli_season()
    if args.report or (args.mode == "report"): return cli_report()
    # default
    return cli_report()

if __name__ == "__main__":
    main()

# ---------- Paths
WS_ROOT = Path(__file__).resolve().parents[1].parents[0]  # workspace root
CFG_PATH = WS_ROOT / "engine" / "configs" / "ad_prestige.config.json"
STATE_PATH = WS_ROOT / "engine" / "state" / "ad_prestige_state.json"
DOC_MAIN = WS_ROOT / "docs" / "AD_PRESTIGE_TRENDS.md"
DOC_ALIAS = WS_ROOT / "docs" / "AD_PRESTIGE.md"

# ---------- IO helpers
def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- Config (built-in defaults so it always runs)
_BUILTIN_CFG: Dict[str, Any] = {
    "smoothing": {"alpha_current": 0.30, "alpha_historical": 0.06},
    "sports": {
        "football": {"weight": 0.40, "visibility": 1.00},
        "mens_bb": {"weight": 0.20, "visibility": 0.90},
        "womens_bb": {"weight": 0.10, "visibility": 0.75},
        "baseball": {"weight": 0.07, "visibility": 0.60},
        "softball": {"weight": 0.05, "visibility": 0.55},
        "soccer": {"weight": 0.05, "visibility": 0.50},
        "track": {"weight": 0.05, "visibility": 0.40},
        "others": {"weight": 0.08, "visibility": 0.30}
    },
    "facilities": {
        "decay_per_week": {
            "stadium": 0.0005, "arena": 0.0007, "weight_room": 0.0015, "practice": 0.0010, "none": 0.0
        },
        "nostalgia": {
            "stadium": {"max": 0.20, "build_per_season": 0.02},
            "arena": {"max": 0.12, "build_per_season": 0.015},
            "weight_room": {"max": 0.00, "build_per_season": 0.00},
            "practice": {"max": 0.00, "build_per_season": 0.00}
        },
        "facility_to_sport": {
            "football": "stadium", "mens_bb": "arena", "womens_bb": "arena",
            "baseball": "stadium", "softball": "stadium", "soccer": "stadium",
            "track": "stadium", "others": "practice"
        },
        "cp_facility_scale": 8.0,
        "hr_nostalgia_scale": 100.0
    },
    "ui": { "stars_thresholds": [20,35,50,65,80,90,96,99], "markdown_limit_rows": 12 }
}

def load_config() -> Dict[str, Any]:
    cfg = _read_json(CFG_PATH, {})
    if not cfg:
        # Fall back silently to built-in defaults
        cfg = _BUILTIN_CFG
    return cfg

def load_state() -> Dict[str, Any]:
    return _read_json(STATE_PATH, {"schools": {}})

def save_state(state: Dict[str, Any]) -> None:
    _write_json(STATE_PATH, state)

# ---------- Core helpers
def _sports_in_cfg(cfg: Dict[str, Any]) -> List[str]:
    return list(cfg["sports"].keys())

def ensure_school(state: Dict[str, Any], cfg: Dict[str, Any], school: str) -> None:
    schools = state.setdefault("schools", {})
    if school in schools:
        return
    rng = random.Random(hash(school) & 0xFFFFFFFF)
    sports = _sports_in_cfg(cfg)
    schools[school] = {
        "programs": {
            s: {
                "current_prestige": float(max(0, min(100, 55 + rng.randint(-10, 10)))),
                "historical_rating": float(max(0, min(100, 60 + rng.randint(-10, 10)))),
                "facility": { "condition": 0.80 + rng.random() * 0.10, "nostalgia": 0.05 * rng.random() }
            } for s in sports
        },
        "meta": { "seasons": 0, "weeks": 0 }
    }

def rollup_department(school_data: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, float]:
    weights = cfg["sports"]
    cp_sum = hr_sum = w_sum = 0.0
    for sport, data in school_data["programs"].items():
        w = float(weights.get(sport, {}).get("weight", 0.0))
        vis = float(weights.get(sport, {}).get("visibility", 1.0))
        cp = float(data["current_prestige"])
        hr = float(data["historical_rating"])
        cp_sum += w * (cp * vis)
        hr_sum += w * hr
        w_sum += w
    if w_sum <= 0: 
        return 0.0, 0.0
    return cp_sum / w_sum, hr_sum / w_sum

def _ema(prev: float, new: float, alpha: float) -> float:
    return (1 - alpha) * prev + alpha * new

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def _facility_channel(cfg: Dict[str, Any], sport: str) -> str:
    return cfg["facilities"]["facility_to_sport"].get(sport, "practice")

def _weekly_decay_facility(sport_data: Dict[str, Any], chan: str, cfg: Dict[str, Any]) -> None:
    decay = float(cfg["facilities"]["decay_per_week"].get(chan, 0.0))
    cond = float(sport_data["facility"]["condition"])
    sport_data["facility"]["condition"] = _clamp01(cond - decay)

def _facility_cp_bonus(sport_data: Dict[str, Any], chan: str, cfg: Dict[str, Any]) -> float:
    cond = float(sport_data["facility"]["condition"])
    scale = float(cfg["facilities"]["cp_facility_scale"])
    return scale * (1 / (1 + math.exp(-10 * (cond - 0.7))) - 0.5) * 2.0

def _nostalgia_season_gain(sport_data: Dict[str, Any], chan: str, cfg: Dict[str, Any]) -> float:
    spec = cfg["facilities"]["nostalgia"].get(chan, {"max": 0.0, "build_per_season": 0.0})
    cur = float(sport_data["facility"]["nostalgia"])
    return float(min(spec["max"], cur + spec["build_per_season"]))

def weekly_update(state: Dict[str, Any], cfg: Dict[str, Any], school: str,
                  week_inputs: Dict[str, Dict[str, float]] | None = None) -> None:
    ensure_school(state, cfg, school)
    alpha = float(cfg["smoothing"]["alpha_current"])
    sports = _sports_in_cfg(cfg)
    rng = random.Random(hash((school, state["schools"][school]["meta"]["weeks"])) & 0xFFFFFFFF)

    for s in sports:
        sd = state["schools"][school]["programs"][s]
        chan = _facility_channel(cfg, s)
        _weekly_decay_facility(sd, chan, cfg)
        cp = float(sd["current_prestige"])

        if week_inputs and s in week_inputs:
            res = float(week_inputs[s].get("results", 0.0))
            rec = float(week_inputs[s].get("recruit", 0.0))
        else:
            res = 0.15 * (rng.random() * 2 - 1)
            rec = 0.10 * (rng.random() * 2 - 1)

        base_score = 100.0 * _clamp01(0.5 + 0.35 * res + 0.15 * rec)
        cp_bonus = _facility_cp_bonus(sd, chan, cfg)
        new_cp = _ema(cp, base_score + cp_bonus, alpha)
        sd["current_prestige"] = float(max(0.0, min(100.0, new_cp)))

    state["schools"][school]["meta"]["weeks"] += 1

def season_end_update(state: Dict[str, Any], cfg: Dict[str, Any], school: str,
                      season_legacy: Dict[str, float] | None = None) -> None:
    ensure_school(state, cfg, school)
    alpha = float(cfg["smoothing"]["alpha_historical"])
    sports = _sports_in_cfg(cfg)
    rng = random.Random(hash((school, "season", state["schools"][school]["meta"]["seasons"])) & 0xFFFFFFFF)

    for s in sports:
        sd = state["schools"][school]["programs"][s]
        hr = float(sd["historical_rating"])
        cp = float(sd["current_prestige"])
        chan = _facility_channel(cfg, s)

        if season_legacy and s in season_legacy:
            legacy = float(season_legacy[s])
        else:
            legacy = _clamp01((cp / 100.0) ** 0.7 + 0.05 * (rng.random() - 0.5))

        next_nost = _nostalgia_season_gain(sd, chan, cfg)
        sd["facility"]["nostalgia"] = next_nost
        nostalgia_points = next_nost * float(cfg["facilities"]["hr_nostalgia_scale"])

        new_hr = _ema(hr, 100.0 * legacy + nostalgia_points, alpha)
        sd["historical_rating"] = float(max(0.0, min(100.0, new_hr)))

    state["schools"][school]["meta"]["seasons"] += 1

def _star_band(x: float, bands: List[int]) -> str:
    stars = 1
    for t in bands:
        if x >= t: stars += 1
    return "★" * stars

def write_markdown(state: Dict[str, Any], cfg: Dict[str, Any]) -> Path:
    DOC_MAIN.parent.mkdir(parents=True, exist_ok=True)
    bands = cfg["ui"]["stars_thresholds"]
    limit = int(cfg["ui"]["markdown_limit_rows"])

    rows = []
    for school, data in state.get("schools", {}).items():
        ad_cp, ad_hr = rollup_department(data, cfg)
        rows.append((school, ad_cp, ad_hr))
    rows.sort(key=lambda r: (-r[1], r[0]))

    header = "# AD Prestige — Current vs Historical\n\n"
    table_header = "| School | AD_CP | AD_HR | CP_Stars | HR_Stars |\n|---|---:|---:|:---:|:---:|\n"
    lines = []
    for school, ad_cp, ad_hr in rows[:limit]:
        lines.append(f"| {school} | {ad_cp:.1f} | {ad_hr:.1f} | {_star_band(ad_cp, bands)} | {_star_band(ad_hr, bands)} |")

    content = header + table_header + "\n".join(lines) + "\n"
    DOC_MAIN.write_text(content, encoding="utf-8")
    # Also mirror to the short name for convenience
    DOC_ALIAS.write_text(content, encoding="utf-8")
    return DOC_MAIN

# ---------- CLI wrappers (support both styles)
def cli_seed():
    cfg = load_config()
    st = load_state()
    for s in ("State U", "School 029"):
        ensure_school(st, cfg, s)
    save_state(st)
    print("Seeded:", ", ".join(st["schools"].keys()))

def cli_weekly():
    cfg = load_config()
    st = load_state()
    for s in st.get("schools", {}).keys():
        weekly_update(st, cfg, s)
    save_state(st)
    p = write_markdown(st, cfg)
    print("Weekly OK →", p.as_posix())

def cli_season():
    cfg = load_config()
    st = load_state()
    for s in st.get("schools", {}).keys():
        season_end_update(st, cfg, s)
    save_state(st)
    p = write_markdown(st, cfg)
    print("Season OK →", p.as_posix())

def cli_report():
    cfg = load_config()
    st = load_state()
    p = write_markdown(st, cfg)
    print("Report OK →", p.as_posix())

def main():
    ap = argparse.ArgumentParser(prog="ad_prestige", add_help=True)
    ap.add_argument("--mode", choices=["seed","weekly","season","report"], help="(Alt) run mode")
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--weekly", action="store_true")
    ap.add_argument("--season", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    # prefer explicit flags; fall back to --mode
    if args.seed or (args.mode == "seed"):   return cli_seed()
    if args.weekly or (args.mode == "weekly"): return cli_weekly()
    if args.season or (args.mode == "season"): return cli_season()
    if args.report or (args.mode == "report"): return cli_report()
    # default
    return cli_report()

if __name__ == "__main__":
    main()
