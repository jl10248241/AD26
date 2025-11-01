# src/excel_bridge.py — College AD v17.5 (Enhanced, Drop-in)
# Orchestrates weekly ticks and writes logs; optionally runs analyzer each tick.

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import json
import logging
import random
import argparse
import datetime

# Local imports (relative to package layout)
from .run_tick import run_one_tick
from .analyzer import analyze_finance

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Workspace Roots / ENV (consistent with run_tick.py & analyzer.py)
# -----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]

def _load_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
        except Exception as e:
            logger.warning(f"Failed to load .env file: {e}")
    return env

ENV = _load_env()
LOG_DIR     = (ROOT / ENV.get("LOG_DIR", "logs")).resolve()
CONFIG_DIR  = (ROOT / ENV.get("CONFIG_DIR", "configs")).resolve()
DOCS_DIR    = (ROOT / ENV.get("DOCS_DIR", "docs")).resolve()
DATA_DIR    = (ROOT / ENV.get("DATA_DIR", "data")).resolve()

for d in (LOG_DIR, CONFIG_DIR, DOCS_DIR, DATA_DIR):
    d.mkdir(parents=True, exist_ok=True)

WORLD_EVENTS_LOG = LOG_DIR / "WORLD_EVENTS_LOG.csv"
FINANCE_LOG      = LOG_DIR / "FINANCE_LOG.csv"

# -----------------------------------------------------------------------------
# Safe JSON helpers
# -----------------------------------------------------------------------------
def _load_json(path: Path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to read {path.name}: {e} — using defaults.")
        return default

def _save_json(path: Path, obj: Any) -> None:
    try:
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to write {path.name}: {e}")

# -----------------------------------------------------------------------------
# Default seeders (so you can run even with empty /data)
# -----------------------------------------------------------------------------
def _seed_default_world() -> Dict[str, Any]:
    # Minimal viable world with one school that can accrue finance/sentiment
    return {
        "version": "v17.5-seeded",
        "schools": [
            {
                "name": "State U",
                "prestige": 0.0,
                "media_heat": 0.0,
                "sentiment": 0.0,
                "finance": {
                    "balance": 0.0,
                    "expenses_week": 0.0,
                    "prestige_last": 0.0,
                    "_tick": {"donor_yield": 0.0}
                }
            }
        ],
        "metrics": {}  # room for world-level metrics (Prestige, Facilities, etc.)
    }

def _seed_default_coaches() -> List[Dict[str, Any]]:
    # Minimal single coach record; trait engine can still run harmlessly
    return [
        {
            "name": "Coach A",
            "media_heat": 0.0,
            # add any trait fields your engine expects; safe defaults are fine
        }
    ]

def _seed_default_cfg() -> Dict[str, Any]:
    return {
        "REG": {
            "weekly_rolls": 3,
            "weights": {"positive": 0.45, "neutral": 0.25, "negative": 0.30}
        }
    }

def _seed_default_G() -> Dict[str, Any]:
    # Global constants container; adjust as your trait engine expects
    return {}

def _seed_default_ANCH() -> Dict[str, Any]:
    # Anchor/gravities for trait engine; safe to leave empty
    return {}

def _seed_default_CTX() -> Dict[str, Any]:
    # Context/state; safe to leave empty
    return {}

# -----------------------------------------------------------------------------
# Load-or-create project state
# -----------------------------------------------------------------------------
def load_project_state() -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    coaches_path = DATA_DIR / "coaches.json"
    world_path   = DATA_DIR / "world.json"
    cfg_path     = DATA_DIR / "cfg.json"
    G_path       = DATA_DIR / "G.json"
    ANCH_path    = DATA_DIR / "anchors.json"
    CTX_path     = DATA_DIR / "context.json"

    coaches = _load_json(coaches_path, default=_seed_default_coaches())
    world   = _load_json(world_path,   default=_seed_default_world())
    cfg     = _load_json(cfg_path,     default=_seed_default_cfg())
    G       = _load_json(G_path,       default=_seed_default_G())
    ANCH    = _load_json(ANCH_path,    default=_seed_default_ANCH())
    CTX     = _load_json(CTX_path,     default=_seed_default_CTX())

    # If files didn't exist, save the seeds so the user can see/edit them
    if not coaches_path.exists(): _save_json(coaches_path, coaches)
    if not world_path.exists():   _save_json(world_path, world)
    if not cfg_path.exists():     _save_json(cfg_path, cfg)
    if not G_path.exists():       _save_json(G_path, G)
    if not ANCH_path.exists():    _save_json(ANCH_path, ANCH)
    if not CTX_path.exists():     _save_json(CTX_path, CTX)

    return coaches, world, cfg, G, ANCH, CTX

def persist_project_state(coaches, world, cfg, G, ANCH, CTX) -> None:
    # Persist updated state back to /data (optional but handy during dev)
    _save_json(DATA_DIR / "coaches.json", coaches)
    _save_json(DATA_DIR / "world.json", world)
    _save_json(DATA_DIR / "cfg.json", cfg)
    _save_json(DATA_DIR / "G.json", G)
    _save_json(DATA_DIR / "anchors.json", ANCH)
    _save_json(DATA_DIR / "context.json", CTX)

# -----------------------------------------------------------------------------
# Pretty console output (optional)
# -----------------------------------------------------------------------------
def _pretty_tick_summary(week: int, events: List[Dict[str, Any]]) -> str:
    n = len(events or [])
    sample = ", ".join([e.get("event_id", "UNKNOWN") for e in (events[:3] if events else [])])
    if n > 3:
        sample += ", …"
    return f"Week {week}: {n} events [{sample}]"

# -----------------------------------------------------------------------------
# Driver
# -----------------------------------------------------------------------------
def run_simulation(weeks: int,
                   seed: Optional[int] = None,
                   run_analyzer_each_tick: bool = True,
                   pretty_out: bool = True) -> None:
    rng = random.Random(seed) if seed is not None else random.Random()
    coaches, world, cfg, G, ANCH, CTX = load_project_state()

    logger.info(f"Starting simulation for {weeks} week(s). Seed={seed}")
    start_ts = datetime.datetime.now()

    try:
        for w in range(1, weeks + 1):
            events = run_one_tick(
                coaches=coaches,
                world=world,
                cfg=cfg,
                G=G,
                ANCH=ANCH,
                CTX=CTX,
                week=w,
                rng=rng,
                log_csv_path=str(WORLD_EVENTS_LOG)  # still honors run_tick’s default if omitted
            )
            if pretty_out:
                print(_pretty_tick_summary(w, events))

            if run_analyzer_each_tick:
                analyze_finance(finance_log=FINANCE_LOG)  # keeps /docs/FINANCE_TRENDS.md fresh

        # persist state so the next run picks up world/coaches changes
        persist_project_state(coaches, world, cfg, G, ANCH, CTX)

    finally:
        elapsed = (datetime.datetime.now() - start_ts).total_seconds()
        logger.info(f"Simulation complete. Elapsed: {elapsed:.2f}s")
        # Last pass of analyzer (useful if disabled per-tick)
        if not run_analyzer_each_tick:
            try:
                analyze_finance(finance_log=FINANCE_LOG)
            except Exception as e:
                logger.warning(f"Analyzer final pass failed: {e}")

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="College AD — v17.5 Excel Bridge Runner")
    parser.add_argument("--weeks", type=int, default=1, help="Number of weeks to simulate")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    parser.add_argument("--no-analyzer", action="store_true", help="Skip analyzer after each tick")
    parser.add_argument("--pretty", action="store_true", help="Print compact per-week summaries")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Set logging level")

    args = parser.parse_args(argv)
    logging.getLogger().setLevel(args.log_level)

    run_simulation(
        weeks=max(1, int(args.weeks)),
        seed=args.seed,
        run_analyzer_each_tick=(not args.no_analyzer),
        pretty_out=bool(args.pretty),
    )

if __name__ == "__main__":
    main()
