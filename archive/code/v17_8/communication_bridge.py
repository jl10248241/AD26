# engine/src/v17_8/communication_bridge.py
# Forwarder to canonical v17.9 bridge.
from __future__ import annotations
from ..communication_bridge import *  # noqa: F401,F403

import warnings as _w
_w.warn(
    "v17_8.communication_bridge is deprecated; use engine.src.communication_bridge.",
    DeprecationWarning,
    stacklevel=2,
)
