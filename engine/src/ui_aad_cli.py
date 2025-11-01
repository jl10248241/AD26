from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any, Dict

from .assistant_ad_engine import load_policies, save_policies, run_once, policy_path

def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))

def cmd_policy(args):
    _print(load_policies())

def cmd_set(args):
    pol = load_policies()
    pol[args.key] = json.loads(args.value) if args.json else args.value
    save_policies(pol)
    print(f"OK: set {args.key}")

def cmd_run(args):
    res = run_once()
    _print(res)

def main():
    ap = argparse.ArgumentParser(prog="ui_aad_cli")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p_pol = sp.add_parser("policy", help="Show current AAD policies")
    p_pol.set_defaults(func=cmd_policy)

    p_set = sp.add_parser("set", help="Set one policy key")
    p_set.add_argument("key", type=str)
    p_set.add_argument("value", type=str, help="value; use --json for JSON literals")
    p_set.add_argument("--json", action="store_true", help="interpret value as JSON")
    p_set.set_defaults(func=cmd_set)

    p_run = sp.add_parser("run", help="Run AAD once")
    p_run.set_defaults(func=cmd_run)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
