from __future__ import annotations
from pathlib import Path
import json, random

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

OUT = DATA_DIR / "donors.json"

ARCHETYPES = [
    "Donor_Patron", "Booster_Club", "Corporate_Sponsor",
    "Alumni_Peer", "Athlete_Parent", "Foundation_Partner"
]

FIRST_NAMES = ["Alex", "Taylor", "Jordan", "Morgan", "Riley", "Drew", "Jamie", "Sam", "Quinn", "Cameron"]
LAST_NAMES = ["Hughes", "Walker", "Mendoza", "Nguyen", "Lopez", "Bennett", "Patel", "Sullivan", "Olsen", "Davis"]

def random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def make_donor(i: int, school: str) -> dict:
    return {
        "id": f"DONOR_{i:04d}",
        "name": random_name(),
        "archetype": random.choice(ARCHETYPES),
        "home_school": school,
        "trust": round(random.uniform(0.4, 0.8), 3),
        "leverage": round(random.uniform(0.0, 0.2), 3),
        "pledges": [],
        "memory": {"weeks_since_contact": random.randint(0, 10)}
    }

def main():
    schools = ["State U"] + [f"School {i:03d}" for i in range(2, 11)]
    donors = [make_donor(i, random.choice(schools)) for i in range(1, 41)]
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(donors, f, indent=2)
    print(f"[seed_donors] wrote {len(donors)} donors to {OUT}")

if __name__ == "__main__":
    main()
