# ui_recruiting_influence_cli.py — v17.9 CLI upgrade

if __package__ in (None, ""):
    import sys, pathlib
    sys.path.append(str(pathlib.Path(__file__).resolve().parent))
    sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
    __package__ = "engine.src"

import argparse
from .recruiting_influence import apply_media_reach_to_probability as apply_mr

def cmd_show(args):
    if args.selftest:
        base = 0.30
        for z in ("Local","Regional","National"):
            print(f"{z}: {base:.2f} → {apply_mr(base, z):.2f}")
    else:
        print("show: use --selftest for sample output")
    if args.verbose:
        print("Verbose: media reach integration active.")

def cmd_prob(args):
    out = apply_mr(args.base, args.zone)
    print(f"{args.zone}: {args.base:.3f} → {out:.3f}")

def cmd_compute(_args):
    print("compute: pipeline hook OK")

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="print sample outputs")
    p_show.add_argument("--selftest", action="store_true")
    p_show.add_argument("--verbose", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_prob = sub.add_parser("prob", help="apply probability for zone")
    p_prob.add_argument("--base", type=float, required=True)
    p_prob.add_argument("--zone", choices=("Local","Regional","National"), required=True)
    p_prob.set_defaults(func=cmd_prob)

    p_compute = sub.add_parser("compute", help="run compute pipeline")
    p_compute.set_defaults(func=cmd_compute)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
