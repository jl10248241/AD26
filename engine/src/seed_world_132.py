from __future__ import annotations
from pathlib import Path
import json

# Project root is two levels up from this file (…/engine/src/ -> project root)
ROOT = Path(__file__).resolve().parents[2]

def load_env():
    """Load environment variables from a .env file."""
    env = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        with env_file.open(encoding="utf-8") as f:
            for line in f.readlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

ENV = load_env()
DATA_DIR = (ROOT / ENV.get("DATA_DIR", "data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT = DATA_DIR / "world.json"

def school_record(name: str, prestige: float = 0.0) -> dict:
    """
    Creates a standardized school record dictionary for the game world.

    Args:
        name: The name of the school.
        prestige: The starting prestige value for the school.

    Returns:
        A dictionary representing the school's data.
    """
    # v17.5-safe finance block; run_tick seeds/maintains these fields
    return {
        "name": name,
        "prestige": float(prestige),
        "media_heat": 0.0,
        "sentiment": 0.0,
        "finance": {
            "balance": 0.0,
            "expenses_week": 0.0,
            "prestige_last": float(prestige),
            "_tick": {"donor_yield": 0.0}
        }
    }

def main():
    """Generates a JSON file with 132 schools and writes it to disk."""
    # 132 schools total. Keep "State U" as #1 so your test events still match.
    names = ["State U"] + [f"School {i:03d}" for i in range(2, 133)]

    world = {
        "version": "v17.5-multischool-132",
        "schools": [school_record(n, prestige=0.0) for n in names],
        "metrics": {}  # (Prestige/Facilities/Integrity/MediaHeat) optional world buckets
    }

    try:
        with OUT.open("w", encoding="utf-8") as f:
            json.dump(world, f, indent=2)
        print(f"[seed_world_132] wrote {OUT} with {len(world['schools'])} schools.")
    except IOError as e:
        print(f"[seed_world_132] Error writing to file {OUT}: {e}")

if __name__ == "__main__":
    main()

