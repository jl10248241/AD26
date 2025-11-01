# engine/src/v17_7/donor_memory.py
# Forwarder to canonical donor_memory.
from __future__ import annotations
from ..donor_memory import *  # noqa: F401,F403

import warnings as _w
_w.warn(
    "v17_7.donor_memory is deprecated; use engine.src.donor_memory.",
    DeprecationWarning,
    stacklevel=2,
)
