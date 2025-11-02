# relationship_core.py — v19 Task 1 (AI Relationship Core)
# Safe for the v17.2 base tree; no new folders auto-created.
from __future__ import annotations
import argparse, json, os, sys, csv
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Tuple

DEFAULT_BASELINE = 50  # gravity point
CLAMP_MIN, CLAMP_MAX = 0, 100

@dataclass
class Link:
    trust: float = DEFAULT_BASELINE
    loyalty: float = DEFAULT_BASELINE
    respect: float = DEFAULT_BASELINE

    def as_row(self, subject: str, target: str, week: int):
        return {
            "week": week,
            "subject": subject,
            "target": target,
            "trust": round(self.trust, 2),
            "loyalty": round(self.loyalty, 2),
            "respect": round(self.respect, 2),
        }

def clamp(x: float, lo=CLAMP_MIN, hi=CLAMP_MAX) -> float:
    return max(lo, min(hi, x))

def project_paths(root: Path):
    return {
        "data": root / "data",
        "logs": root / "logs",
        "docs": root / "docs",
        "state": root / "data" / "relationships.json",
        "log_csv": root / "logs" / "RELATIONSHIP_LOG.csv",
        "week_state": root / "scripts" / "SESSION_STATE_v18.json",  # reuse week anchor if present
    }

def load_state(state_path: Path) -> Dict[str, Dict[str, Link]]:
    if not state_path.exists():
        return {}
    with state_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    state: Dict[str, Dict[str, Link]] = {}
    for s, targets in raw.get("links", {}).items():
        state[s] = {}
        for t, vals in targets.items():
            state[s][t] = Link(**vals)
    return state

def save_state(state_path: Path, state: Dict[str, Dict[str, Link]]):
    serial = {"links": {s:{t:asdict(link) for t,link in targets.items()} for s,targets in state.items()}}
    with state_path.open("w", encoding="utf-8") as f:
        json.dump(serial, f, indent=2)

def get_week(paths) -> int:
    # Try to read existing session week; default to 1
    try:
        if paths["week_state"].exists():
            data = json.loads(paths["week_state"].read_text(encoding="utf-8"))
            return int(data.get("week", 1))
    except Exception:
        pass
    return 1

def seed_minimal(state: Dict[str, Dict[str, Link]]):
    state.setdefault("Player_AD", {})
    for npc in ["Coach.HeadCoach", "Donor.TopBooster", "Board.Chair"]:
        state["Player_AD"].setdefault(npc, Link())

EFFECT_TABLE = {
    ("win","positive"):  {"trust": +6,  "loyalty": +4, "respect": +6},
    ("loss","negative"): {"trust": -4,  "loyalty": -3, "respect": -5},
    ("donation","positive"): {"trust": +3, "loyalty": +7, "respect": +2},
    ("scandal","negative"): {"trust": -12, "loyalty": -8, "respect": -15},
    ("praise","positive"): {"trust": +5, "loyalty": +4, "respect": +3},
    ("conflict","negative"): {"trust": -6, "loyalty": -7, "respect": -4},
    ("meeting_good","positive"): {"trust": +7, "loyalty": +6, "respect": +5},
    ("meeting_bad","negative"): {"trust": -5, "loyalty": -6, "respect": -5},
    ("media_heat","negative"): {"trust": -3, "loyalty": -2, "respect": -4},
}

def apply_effect(link: Link, effect: str, tone: str, intensity: int):
    key = (effect, "positive" if tone == "positive" else "negative" if tone == "negative" else ("positive" if intensity>0 else "negative"))
    base = EFFECT_TABLE.get(key, {"trust":0,"loyalty":0,"respect":0})
    scale = max(1, abs(intensity)) / 10.0  # 10 → 1.0x, 20 → 2.0x
    link.trust   = clamp(link.trust   + base["trust"]   * scale)
    link.loyalty = clamp(link.loyalty + base["loyalty"] * scale)
    link.respect = clamp(link.respect + base["respect"] * scale)

def decay_toward_gravity(x: float, gravity=DEFAULT_BASELINE, rate=0.08) -> float:
    # simple exponential pull toward baseline
    return x + (gravity - x) * rate

def weekly_decay(link: Link):
    link.trust   = clamp(decay_toward_gravity(link.trust))
    link.loyalty = clamp(decay_toward_gravity(link.loyalty, rate=0.06))
    link.respect = clamp(decay_toward_gravity(link.respect, rate=0.05))

def write_log_row(paths, row: dict):
    logs_dir = paths["logs"]
    if not logs_dir.exists():
        return  # respect Rule #1: do not create missing folders
    write_header = not paths["log_csv"].exists()
    with paths["log_csv"].open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["week","subject","target","trust","loyalty","respect"])
        if write_header: w.writeheader()
        w.writerow(row)

def cmd_init(paths):
    if not paths["data"].exists():
        print("ERROR: data\\ folder missing. Create it first (no auto-create).", file=sys.stderr)
        sys.exit(2)
    state = load_state(paths["state"])
    seed_minimal(state)
    save_state(paths["state"], state)
    print(f"Initialized relationships at {paths['state']} with {len(state.get('Player_AD',{}))} links.")

def cmd_apply(paths, subject, target, effect, intensity, tone):
    state = load_state(paths["state"])
    if subject not in state: state[subject] = {}
    link = state[subject].get(target, Link())
    apply_effect(link, effect, tone, intensity)
    state[subject][target] = link
    save_state(paths["state"], state)
    week = get_week(paths)
    write_log_row(paths, link.as_row(subject, target, week))
    print(json.dumps({"subject":subject,"target":target,"week":week,**link.as_row(subject,target,week)}, indent=2))

def cmd_tick(paths, weeks: int):
    state = load_state(paths["state"])
    if not state:
        print("No relationships found. Run init first.", file=sys.stderr)
        sys.exit(3)
    week = get_week(paths)
    for _ in range(max(1,weeks)):
        for subject, targets in state.items():
            for target, link in targets.items():
                weekly_decay(link)
                write_log_row(paths, link.as_row(subject, target, week))
        week += 1
    save_state(paths["state"], state)
    print(f"Applied weekly decay for {weeks} week(s).")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_init = sub.add_parser("init")
    ap_apply = sub.add_parser("apply")
    ap_apply.add_argument("--subject", required=True)
    ap_apply.add_argument("--target", required=True)
    ap_apply.add_argument("--effect", required=True)
    ap_apply.add_argument("--intensity", type=int, default=10)
    ap_apply.add_argument("--tone", choices=["positive","negative","neutral"], default="neutral")
    ap_tick = sub.add_parser("tick")
    ap_tick.add_argument("--weeks", type=int, default=1)

    args = ap.parse_args()
    paths = project_paths(Path(args.project_root))

    if args.cmd == "init":
        cmd_init(paths)
    elif args.cmd == "apply":
        cmd_apply(paths, args.subject, args.target, args.effect, args.intensity, args.tone)
    elif args.cmd == "tick":
        cmd_tick(paths, args.weeks)

if __name__ == "__main__":
    main()
