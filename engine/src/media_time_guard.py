from __future__ import annotations
from typing import Tuple

def guard_action(action: str, actor: str, target: str) -> Tuple[bool, str]:
    """
    Try to reserve time for a media action. Returns (ok, msg).
    If schedule engine is missing, we allow the action (ok=True).
    """
    try:
        from .schedule_engine import reserve_action
    except Exception:
        return True, "schedule_engine_not_available"

    # Map media action -> schedule action type
    act_map = {
        "amplify": "media_interview",
        "downplay": "press_conference",
        "press_release": "press_conference"
    }
    atype = act_map.get(action)
    if not atype:
        return True, "unguarded_action"

    title = f"{action.replace('_', ' ').title()} ({target})"
    try:
        booking = reserve_action(
            action_type=atype,
            title=title,
            priority="normal",
            actor=actor,
            target=target
        )
        return True, f"reserved:{booking.get('id','')}"
    except Exception as e:
        return False, f"{e}"
