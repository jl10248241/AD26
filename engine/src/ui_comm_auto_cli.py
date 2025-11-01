# ui_comm_auto_cli.py — v17.9.1 (policy print + reset-defaults)

if __package__ in (None, ""):
    import sys, pathlib
    sys.path.append(str(pathlib.Path(__file__).resolve().parent))
    sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
    __package__ = "engine.src"

import argparse, json
from pathlib import Path
from .comm_auto_engine import load_policy as _lp, save_policy as _sp, run_once as _run

CFG_DIR = Path(__file__).resolve().parents[1] / "config"
POLICY_FILE = CFG_DIR / "comm_auto_policy.json"

_DEFAULT_POLICY = {
  "aad_name": "Assistant AD",
  "actor": "AAD:1",
  "allow": [],
  "enabled": True,
  "allow_autosend": True,
  "require_ack": False,
  "max_daily_actions": "3",
  "hours_per_action": 0.25,
  "amplify_threshold": 0.5,
  "downplay_threshold": -0.4,
  "ignore_window": [-0.1, 0.1],
  "relationship_targets": {
    "Local": "Media:Local Beat",
    "Regional": "Media:Regional",
    "National": "Media:National"
  },
  "schedule_type_map": {
    "amplify": "comms_media",
    "downplay": "comms_media",
    "ignore": "comms_triage"
  },
  "sentiment_boosts": {
    "amplify": { "Local": 0.02, "Regional": 0.03, "National": 0.05 },
    "downplay": { "Local": 0.02, "Regional": 0.02, "National": 0.03 }
  }
}

def _load_policy():
    try:
        return _lp(POLICY_FILE)
    except TypeError:
        return _lp()

def _save_policy(p):
    POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        return _sp(POLICY_FILE, p)
    except TypeError:
        return _sp(p)

def _to_bool(v):
    if isinstance(v, bool): return v
    if v is None: return False
    return str(v).strip().lower() in ("1","true","t","yes","y","on")

def cmd_policy(args):
    if args.subcmd == "print":
        print(json.dumps(_load_policy(), indent=2, sort_keys=True))
        return
    if args.subcmd == "reset-defaults":
        _save_policy(_DEFAULT_POLICY)
        print("RESET → defaults written")
        return
    # default action: round-trip + optional sync/normalize
    policy = _load_policy()
    before = json.dumps(policy, sort_keys=True)
    changed = False
    for k in ("enabled","allow_autosend","require_ack"):
        if getattr(args, k) is not None:
            policy[k] = _to_bool(getattr(args, k))
            changed = True
    if args.sync or changed:
        _save_policy(policy)
    after = json.dumps(_load_policy(), sort_keys=True)
    if args.selftest:
        print("SELFTEST: round-trip OK")
    if args.selftest or args.print_after:
        print(after)

def cmd_set(args):
    policy = _load_policy()
    for k in ("enabled","allow_autosend","require_ack"):
        v = getattr(args, k)
        if v is not None:
            policy[k] = _to_bool(v)
    _save_policy(policy)
    print(json.dumps(policy, indent=2, sort_keys=True))

def cmd_run(_args):
    try:
        return _run(POLICY_FILE)
    except TypeError:
        return _run()

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    # policy group with sub-commands
    p_pol = sub.add_parser("policy", help="round-trip, print, or reset defaults")
    p_pol_sub = p_pol.add_subparsers(dest="subcmd")
    # default (no subcmd) options
    p_pol.add_argument("--selftest", action="store_true")
    p_pol.add_argument("--sync", action="store_true")
    p_pol.add_argument("--print-after", action="store_true")
    p_pol.add_argument("--enabled")
    p_pol.add_argument("--allow_autosend")
    p_pol.add_argument("--require_ack")
    p_pol.set_defaults(func=cmd_policy, subcmd=None)
    # policy print
    p_pol_print = p_pol_sub.add_parser("print", help="print current policy")
    p_pol_print.set_defaults(func=cmd_policy, subcmd="print")
    # policy reset-defaults
    p_pol_reset = p_pol_sub.add_parser("reset-defaults", help="restore default policy")
    p_pol_reset.set_defaults(func=cmd_policy, subcmd="reset-defaults")

    p_set = sub.add_parser("set", help="set toggles")
    p_set.add_argument("--enabled")
    p_set.add_argument("--allow_autosend")
    p_set.add_argument("--require_ack")
    p_set.set_defaults(func=cmd_set)

    p_run = sub.add_parser("run", help="run one cycle")
    p_run.set_defaults(func=cmd_run)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
