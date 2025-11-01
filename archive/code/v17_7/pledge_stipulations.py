# engine/src/v17_7/pledge_stipulations.py
# Forwarder to canonical pledge_stipulations.
from __future__ import annotations
from ..pledge_stipulations import *  # noqa: F401,F403

import warnings as _w
_w.warn(
    "v17_7.pledge_stipulations is deprecated; use engine.src.pledge_stipulations.",
    DeprecationWarning,
    stacklevel=2,
)
