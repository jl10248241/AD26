# engine/src/persona_demo.py — quick smoke test (package-safe)
from __future__ import annotations

# Use relative import so this works when run as a package module:
from .personality_engine import generate, interaction_stance, donor_propensity

def main() -> None:
    donor = generate(seed="DONOR_0071", role="donor", overrides=None)
    stance = interaction_stance(donor, {"category": "Donor", "intensity": 0.7})
    prop = donor_propensity(donor, school_sentiment=0.3, prestige=45.0)

    print("[persona]", donor)
    print("[stance]", stance)
    print("[donor_propensity]", round(prop, 3))

if __name__ == "__main__":
    # Running directly (python engine/src/persona_demo.py) also works
    main()
