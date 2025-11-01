# engine/src/run_tick.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import json, random, datetime as _dt, subprocess, sys, time

# ---------- Paths ----------
ROOT = Path(__file__).resolve().parents[2]           # .../College_AD_Unified_Workspace_.../
ENGINE = ROOT / "engine"
SRC    = ENGINE / "src"
STATE  = ENGINE / "state"
CONFIG = ENGINE / "config"
LOGS   = ROOT / "logs"
INBOX  = LOGS / "INBOX"
MEDIA  = LOGS / "MEDIA"
DOCS   = ROOT / "docs"

# ---------- Helpers ----------
def _utcstamp() -> str:
    # timezone-aware, no deprecation warnings
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def _ensure_dirs():
    for p in (STATE, LOGS, INBOX, MEDIA, DOCS, CONFIG):
        p.mkdir(parents=True, exist_ok=True)

def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists() and path.stat().st_size > 0:
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def _fmt_money(x: float) -> str:
    return f"${int(x):,}"

def _fmt_pct(x: float) -> str:
    return f"{round(x*100):d}%"

# ---------- Guardrails (v17.9) ----------
MAX_WEEKS = 52

def _state_ok():
    state_dir = STATE
    required = ["clock.json", "schedule_state.json", "recruiting_modifiers.json"]
    missing = [f for f in required if not (state_dir / f).exists()]
    return (len(missing) == 0, missing)

def _log(msg: str):
    logs = LOGS / "engine.log"
    logs.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S ")
    try:
        with open(logs, "a", encoding="utf-8") as f:
            f.write(ts + msg + "\n")
    except Exception:
        pass

def guard_before_advance(week: int) -> bool:
    ok, missing = _state_ok()
    if week > MAX_WEEKS:
        _log(f"[HALT] week={week} exceeds MAX_WEEKS={MAX_WEEKS}")
        return False
    if not ok:
        _log(f"[HALT] missing state files: {missing}")
        return False
    return True

# ---------- Minimal data seeds ----------
def _seed_schools() -> List[str]:
    # Keep small & fast. You can expand later.
    return ["State U", "School 029"]

def _load_clock() -> Dict[str, Any]:
    clock = _read_json(STATE / "clock.json", {"week": 1})
    if not isinstance(clock, dict) or "week" not in clock:
        clock = {"week": 1}
    return clock

def _save_clock(clock: Dict[str, Any]):
    _write_json(STATE / "clock.json", clock)

# ---------- Nudges (fan energy, coach morale) ----------
def _load_state_vector(name: str, schools: List[str], default_val: float) -> Dict[str, float]:
    path = STATE / f"{name}.json"
    data = _read_json(path, {})
    # ensure keys present
    for s in schools:
        if s not in data:
            data[s] = default_val
    return data

def _bounded(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))

def _apply_nudges(week: int, schools: List[str]) -> Dict[str, Any]:
    random.seed(week * 9973)  # deterministic per week
    fan = _load_state_vector("fan_energy", schools, 0.35)
    mor = _load_state_vector("coach_morale", schools, 0.50)

    # Light-touch updates per school so it "breathes" week to week.
    notes = []
    for s in schools:
        df = random.uniform(-0.015, 0.020)   # fans swing a bit more up than down
        dm = random.uniform(-0.010, 0.015)   # morale a little steadier

        fan[s] = _bounded(fan[s] + df)
        mor[s] = _bounded(mor[s] + dm)

        notes.append((s, df, dm))

    _write_json(STATE / "fan_energy.json", fan)
    _write_json(STATE / "coach_morale.json", mor)

    return {"fan_energy": fan, "coach_morale": mor, "notes": notes}

# ---------- Briefings (INBOX) ----------
def _write_briefings(week: int, schools: List[str]) -> List[Path]:
    files = []
    for idx, s in enumerate(schools, start=1):
        payload = {
            "type": "update",
            "subject": f"[Coach] Weekly briefing W{week}: quick hits",
            "summary": "Two practice notes and one recruiting rumor.",
            "donor": "—",
            "coach": "—",
            "team": "—",
            "amount": 0,
            "severity": "normal",
            "tags": [],
            "week": week,
            "days_ago": 0,
            "timestamp": _utcstamp(),
            "id": f"coach-briefing-{s.lower().replace(' ', '-')}-w{week}",
        }
        name = f"W{week:02d}-update-coach-briefing-{idx:04d}.json"
        path = INBOX / name
        _write_json(path, payload)
        files.append(path)
    return files

# ---------- Media ----------
def _write_media_story(week: int, schools: List[str], nudges: Dict[str, Any]) -> Path:
    # Focus on the first school for the headline to keep it simple
    school = schools[0]
    fan = nudges["fan_energy"][school]
    mor = nudges["coach_morale"][school]

    headline = f"{school} insider: fan buzz {_fmt_pct(fan)} • sideline vibe {_fmt_pct(mor)}"
    blurb    = "Whispers out of practice suggest subtle momentum shifts; AD office declines to comment."

    payload = {
        "type": "media",
        "subject": headline,
        "summary": blurb,
        "week": week,
        "timestamp": _utcstamp(),
        "id": f"media-week-{week:02d}-{school.lower().replace(' ', '-')}",
        "school": school,
        "metrics": {"fan_energy": round(fan, 3), "coach_morale": round(mor, 3)},
    }
    name = f"W{week:02d}-media-{school.lower().replace(' ', '-')}.json"
    path = MEDIA / name
    _write_json(path, payload)
    return path

# ---------- Post hooks (docs rebuild) ----------
def _post_hooks():
    # Safe calls — ignore failure if user hasn't added a module yet.
    cmds = [
        [sys.executable, "-m", "engine.src.ad_health"],
        [sys.executable, "-m", "engine.src.ad_prestige", "--weekly"],
    ]
    for c in cmds:
        try:
            subprocess.run(c, cwd=str(ROOT), check=False, capture_output=True, text=True)
        except Exception:
            pass

# ---------- Main tick ----------
def run_one_week() -> Dict[str, Any]:
    _ensure_dirs()
    clock = _load_clock()
    week = int(clock.get("week", 1))
    schools = _seed_schools()

    # --- v17.9 guardrails: block unsafe advances ---
    if not guard_before_advance(week):
        return {"status": "halted", "week": week, "reason": "guardrails"}

    inbox_files = _write_briefings(week, schools)
    nudges = _apply_nudges(week, schools)
    media_file = _write_media_story(week, schools, nudges)

    # advance clock
    clock["week"] = week + 1
    _save_clock(clock)

    _post_hooks()

    return {
        "status": "ok",
        "week_started": week,
        "week_ended": clock["week"],
        "inbox_files": [str(p.relative_to(ROOT)) for p in inbox_files],
        "media_file": str(media_file.relative_to(ROOT)),
        "nudges": {
            "fan_energy": nudges["fan_energy"],
            "coach_morale": nudges["coach_morale"]
        }
    }

if __name__ == "__main__":
    out = run_one_week()
    print(json.dumps(out, indent=2))
