# v17.7 — stipulation_tracker (scaffold)
# Purpose: Track pledge stipulations → status transitions with minimal surface area.

from __future__ import annotations
from typing import Dict, Any, Optional, List
import argparse
import random # Added for the tick_update signature

STATUS_ORDER = ("promised", "pending", "received", "lapsed")

def new_entry(*, week:int, school:str, donor_id:str, donor_name:str,
              amount:float, earmark:str = "", note:str = "") -> Dict[str, Any]:
    return {
        "week": int(week),
        "school": school,
        "donor_id": donor_id,
        "donor_name": donor_name,
        "amount": float(amount),
        "earmark": earmark,
        "status": "promised",
        "note": note
    }

def advance_status(entry: Dict[str, Any], to_status: str) -> Dict[str, Any]:
    if to_status not in STATUS_ORDER:
        raise ValueError(f"Unknown status '{to_status}'")
    entry["status"] = to_status
    return entry

def fulfilled(entry: Dict[str, Any], success: bool = True) -> Dict[str, Any]:
    return advance_status(entry, "received" if success else "lapsed")

def filter_open(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [e for e in entries if e.get("status") in ("promised","pending")]

# ------------------------------
# ADDED: The required 'tick_update' function
# ------------------------------
def tick_update(world: Dict[str, Any], cfg: Any, G: Any, week: int, rng: Optional[random.Random]) -> None:
    """
    Placeholder: Called once per week/tick by run_tick.py. 
    This function should handle any necessary weekly processing for stipulations.
    """
    pass

def _demo() -> None:
    e = new_entry(week=12, school="State U", donor_id="DONOR_0001", donor_name="Alex Hughes", amount=250000, earmark="Practice Facility")
    print("[demo] new:", e)
    advance_status(e, "pending")
    print("[demo] pending:", e)
    fulfilled(e, success=True)
    print("[demo] received:", e)

def main(argv: Optional[list] = None) -> None:
    ap = argparse.ArgumentParser(description="v17.7 stipulation tracker scaffold")
    ap.add_argument("--selftest", action="store_true", help="run a quick smoke test")
    args = ap.parse_args(argv)
    if args.selftest:
        _demo()
    else:
        print("stipulation_tracker: ready (v17.7 scaffold)")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        # Running the internal demo
        _demo()
        
        # Testing the tick_update stub
        world = {"schools":[{"name":"State U","finance":{"_tick":{}}}]}
        tick_update(world=world, cfg={}, G={}, week=1, rng=None)
        
        # CORRECTED print statement for module name consistency
        print("[stipulation_tracker] selftest OK")