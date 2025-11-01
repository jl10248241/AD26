# engine/src/selftest_guardrails.py
from pathlib import Path
from engine.src.run_tick import guard_before_advance, STATE

def main():
    failures = []

    # week cap
    if guard_before_advance(1) is not True:
        failures.append("week 1 should be allowed")
    if guard_before_advance(60) is not False:
        failures.append("week 60 should be blocked")

    # missing state files case
    # temporarily hide required files if they exist
    req = ["clock.json","schedule_state.json","recruiting_modifiers.json"]
    moved = []
    for f in req:
        p = STATE / f
        if p.exists():
            pb = p.with_suffix(p.suffix + ".bak")
            p.rename(pb)
            moved.append((p, pb))
    try:
        if guard_before_advance(1) is not False:
            failures.append("missing state files should block advance")
    finally:
        # restore
        for p, pb in moved:
            if pb.exists():
                pb.rename(p)

    if failures:
        print("SELFTEST FAIL:", failures)
        raise SystemExit(1)
    print("SELFTEST OK")

if __name__ == "__main__":
    main()
