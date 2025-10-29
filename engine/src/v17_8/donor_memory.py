# v17.7 — donor_memory (scaffold)
# Purpose: Centralize donor trust/leverage updates & weekly decay in one place.
# Safe, no external deps. Can be swapped to use authoritative state later.

from __future__ import annotations
from typing import Dict, Any, Optional
import argparse
import random # Imported for the tick_update signature, though not used in minimal implementation

DEFAULT_DECAY = 0.98  # ~2% fade per week toward neutral

def apply_decay_state(state: Dict[str, Any], *, weeks: int = 1, decay: float = DEFAULT_DECAY) -> Dict[str, Any]:
    """Decay a donor-state dict in-place: {'trust': float, 'leverage': float}."""
    decay = max(0.90, min(0.999, float(decay)))
    # Trust decays toward the neutral point (0.5)
    trust = float(state.get("trust", 0.5))
    # Leverage decays toward zero (0.0)
    lev   = float(state.get("leverage", 0.0))
    trust = 0.5 + (trust - 0.5) * (decay ** weeks)
    lev   = lev * (decay ** weeks)
    state["trust"], state["leverage"] = round(trust, 6), round(lev, 6)
    return state

def bump_from_pledge(state: Dict[str, Any], trust_bump: float = 0.02, lev_bump: float = 0.01) -> Dict[str, Any]:
    """Apply small positive adjustments when a pledge is recorded."""
    state["trust"] = max(0.0, min(1.0, float(state.get("trust", 0.5)) + trust_bump))
    state["leverage"] = max(-1.0, min(1.0, float(state.get("leverage", 0.0)) + lev_bump))
    return state

def bump_from_fulfillment(state: Dict[str, Any], success: bool = True) -> Dict[str, Any]:
    """Adjust after a stipulation is fulfilled or missed."""
    if success:
        state["trust"] = min(1.0, float(state.get("trust", 0.5)) + 0.05)
        state["leverage"] = min(1.0, float(state.get("leverage", 0.0)) + 0.02)
    else:
        state["trust"] = max(0.0, float(state.get("trust", 0.5)) - 0.07)
        state["leverage"] = max(-1.0, float(state.get("leverage", 0.0)) - 0.03)
    return state

# ------------------------------
# ADDED: The required 'tick_update' function
# ------------------------------
def tick_update(world: Dict[str, Any], cfg: Any, G: Any, week: int, rng: Optional[random.Random]) -> None:
    """
    Called once per week/tick by run_tick.py. Applies weekly decay to all donor relationships.
    (Minimal implementation: Assumes donor states are stored in school['donors']).
    """
    for school in world.get("schools", []):
        donors = school.get("donors", [])
        for donor_state in donors:
            # Apply decay to each donor state
            apply_decay_state(donor_state)

        # Safety check: if there are no explicit 'donors', but there is a 'finance' 
        # block, we don't do anything, as this scaffold only updates donor states.
    
    # NOTE: The actual logic for a full V17.7 implementation would likely load
    # a central list of donors from a separate location and update them.
    pass

def _demo() -> None:
    s = {"trust": 0.72, "leverage": 0.18}
    print("[demo] start:", s)
    apply_decay_state(s, weeks=1)
    print("[demo] after 1w decay:", s)
    bump_from_pledge(s)
    print("[demo] after pledge:", s)
    bump_from_fulfillment(s, success=True)
    print("[demo] after fulfillment:", s)

def main(argv: Optional[list] = None) -> None:
    ap = argparse.ArgumentParser(description="v17.7 donor memory scaffold")
    ap.add_argument("--selftest", action="store_true", help="run a quick smoke test")
    args = ap.parse_args(argv)
    if args.selftest:
        _demo()
    else:
        print("donor_memory: ready (v17.7 scaffold)")

if __name__ == "__main__":
    # Corrected the redundant import and added the necessary function call.
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        # Running the quick internal demo
        _demo()
        
        # Testing the tick_update stub, which should run without error
        world = {"schools":[{"name":"State U", "donors": [{"trust": 0.72, "leverage": 0.18}]}]}
        tick_update(world=world, cfg={}, G={}, week=1, rng=None)  # safe to no-op
        print("[donor_memory] selftest OK")