# selftest_guardrails.py — verify preconditions for autopilot run

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
CFG  = ROOT / "engine" / "config"
STATE = ROOT / "engine" / "state"

def guard_before_advance(week:int) -> bool:
    """Check if it's safe to advance a simulation week."""
    required = [
        CFG / "MEDIA_REACH.json",
        CFG / "comm_auto_policy.json",
        CFG / "media_map.config.json",
    ]
    for r in required:
        if not r.exists():
            print(f"[HALT] Missing required config: {r.name}")
            return False
    # sanity: recruiting + relationships exist
    for name in ("recruiting_modifiers.json", "relationships.json"):
        if not (STATE / name).exists():
            print(f"[HALT] Missing state: {name}")
            return False
    print(f"[OK] Guard check passed for week {week}")
    return True

if __name__ == "__main__":
    from engine.src.run_tick import _load_clock
    wk = _load_clock().get("week", 1)
    guard_before_advance(wk)
