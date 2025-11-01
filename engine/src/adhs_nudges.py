# engine/src/adhs_nudges.py
from __future__ import annotations
import json, math, random
from pathlib import Path
from datetime import datetime, timezone

ROOT   = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine"
STATE  = ENGINE / "state"
LOGS   = ROOT / "logs"
MEDIA  = LOGS / "MEDIA"

FAN_FILE    = STATE / "fan_energy.json"     # { "<school>": 0..1 }
MORALE_FILE = STATE / "coach_morale.json"   # { "<school>": 0..1 }
NUDGE_FILE  = STATE / "adhs_nudges.state.json"  # last_week + residuals per school

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def _read(p: Path, default):
    try:
        if p.exists() and p.stat().st_size > 0:
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _write(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x

def _apply_decay(residual: float, weeks_passed: int, decay: float) -> float:
    # exponential decay: residual * (decay^weeks_passed)
    return residual * (decay ** max(0, weeks_passed))

def _ensure_files():
    LOGS.mkdir(parents=True, exist_ok=True); MEDIA.mkdir(parents=True, exist_ok=True); STATE.mkdir(parents=True, exist_ok=True)

# ---------------------------- public API ----------------------------
def auto_from_coach(school: str, program: str, coach: str, week: int, winrate: float, events: int,
                    decay=0.85,   # weekly decay of previous residuals
                    fan_scale=0.020, morale_scale=0.015, event_bonus=0.004, cap_weekly=0.05):
    """
    Translate a coach week → tiny bumps:
      - fan_energy += (winrate-0.5)*fan_scale + events*event_bonus
      - coach_morale += (winrate-0.5)*morale_scale + 0.5*events*event_bonus
    Decay any outstanding residual each week so effects fade.
    """
    _ensure_files()
    fans   = _read(FAN_FILE, {})
    morale = _read(MORALE_FILE, {})
    nudges = _read(NUDGE_FILE, {"last_week": week, "residuals": {}})

    last_week = int(nudges.get("last_week", week))
    weeks_passed = max(0, week - last_week)

    res = nudges.setdefault("residuals", {})
    r   = res.get(school, {"fan_resid": 0.0, "morale_resid": 0.0})

    # decay old residuals
    r["fan_resid"]    = _apply_decay(r.get("fan_resid", 0.0), weeks_passed, decay)
    r["morale_resid"] = _apply_decay(r.get("morale_resid", 0.0), weeks_passed, decay)

    # compute this week's micro-bumps
    drift = (winrate - 0.5)
    dfan     = drift * fan_scale + events * event_bonus
    dmorale  = drift * morale_scale + 0.5 * events * event_bonus

    # cap total weekly impact (positive or negative)
    dfan    = max(-cap_weekly, min(cap_weekly, dfan))
    dmorale = max(-cap_weekly, min(cap_weekly, dmorale))

    # add to residuals (which will decay in future weeks)
    r["fan_resid"]    += dfan
    r["morale_resid"] += dmorale
    res[school] = r

    # apply to current state snapshots (bounded 0..1)
    base_fan    = float(fans.get(school, 0.35))    # conservative initial feel
    base_morale = float(morale.get(school, 0.50))  # seeded by your ad_seed, default safe
    fans[school]    = _clamp01(base_fan    + r["fan_resid"])
    morale[school]  = _clamp01(base_morale + r["morale_resid"])

    nudges["last_week"] = week

    _write(FAN_FILE, fans)
    _write(MORALE_FILE, morale)
    _write(NUDGE_FILE, nudges)

    # media note (so the world feels alive)
    headline = _make_media_headline(school, program, coach, winrate, events)
    media_obj = {
        "type": "media",
        "timestamp": utc_now(),
        "school": school,
        "program": program,
        "coach": coach,
        "week": week,
        "winrate": round(winrate,3),
        "events": events,
        "headline": headline
    }
    fname = MEDIA / f"W{week:02d}-media-{_rand_id()}.json"
    _write(fname, media_obj)
    return {
        "fan_energy": fans[school],
        "coach_morale": morale[school],
        "residuals": r,
        "media_file": fname.name,
        "headline": headline
    }

def _rand_id():
    return f"{random.randrange(16**8):08x}"

def _make_media_headline(school: str, program: str, coach: str, winrate: float, events: int) -> str:
    vibe = "surging" if winrate >= 0.62 else "steady" if winrate >= 0.48 else "under pressure"
    bits = [
        f"{school} {program.title()} {vibe}",
        f"{coach} cites {events} key update{'s' if events!=1 else ''}",
        "fans react across campus" if winrate>=0.5 else "AD calls for patience"
    ]
    return " — ".join(bits)

# ---------------------------- CLI ----------------------------
def main():
    import argparse
    ap = argparse.ArgumentParser(description="Apply ADHS micro-nudges and log a media item")
    ap.add_argument("--auto", action="store_true", help="use auto formula (requires --school --program --coach --week --winrate --events)")
    ap.add_argument("--school", type=str)
    ap.add_argument("--program", type=str)
    ap.add_argument("--coach", type=str)
    ap.add_argument("--week", type=int)
    ap.add_argument("--winrate", type=float)
    ap.add_argument("--events", type=int, default=0)
    args = ap.parse_args()

    if args.auto:
        if None in (args.school, args.program, args.coach, args.week, args.winrate):
            raise SystemExit("Missing required args for --auto")
        out = auto_from_coach(args.school, args.program, args.coach, args.week, args.winrate, args.events)
        print(f"[nudges] {args.school} fan={out['fan_energy']:.3f} morale={out['coach_morale']:.3f} :: {out['headline']}")
    else:
        raise SystemExit("Nothing to do. Use --auto.")

if __name__ == "__main__":
    main()
