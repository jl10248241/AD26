# ui_dayplay_cli.py — DayPlay (one-week loop) for v17.9.x
# Safe to run via: python -m engine.src.ui_dayplay_cli play

if __package__ in (None, ""):
    import sys, pathlib
    sys.path.append(str(pathlib.Path(__file__).resolve().parent))
    sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
    __package__ = "engine.src"

import argparse, json
from .run_tick import run_one_week
from .ui_recruiting_influence_cli import cmd_show as _recruit_show
from .ui_comm_auto_cli import main as _noop_import  # ensure CLI modules import cleanly

def _print_header(title: str):
    print("\n" + "="*64)
    print(title)
    print("="*64)

def _show_week_snapshot():
    # Lightweight status peek without coupling to internal formats
    try:
        from .config_paths import DOCS_PATH
        p_feed = DOCS_PATH / "MEDIA_FEED.md"
        p_sched = DOCS_PATH / "SCHEDULE.md"
        if p_feed.exists():
            _print_header("Media Feed (tail)")
            lines = p_feed.read_text(encoding="utf-8").splitlines()[-12:]
            print("\n".join(lines))
        if p_sched.exists():
            _print_header("Schedule (tail)")
            lines = p_sched.read_text(encoding="utf-8").splitlines()[-12:]
            print("\n".join(lines))
    except Exception:
        pass

def play_one_week():
    _print_header("Starting DayPlay (one-week)")
    result = run_one_week()
    print(json.dumps(result, indent=2))
    _show_week_snapshot()

    _print_header("Recruiting Influence (selftest view)")
    class _Args:  # shim to reuse ui_recruiting_influence_cli.cmd_show
        selftest=True; verbose=True
    _recruit_show(_Args())

    print("\n✅ DayPlay complete: docs updated, nudges applied, media/inbox written.")

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    p_play = sub.add_parser("play", help="Run one playable week")
    p_play.set_defaults(func=lambda _a: play_one_week())

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
