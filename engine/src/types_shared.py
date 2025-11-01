# engine/src/types_shared.py
# v17.9 — shared TypedDicts (no runtime dependency)
from __future__ import annotations
from typing import TypedDict, List, Dict, Optional

class InboxPacketDict(TypedDict, total=False):
    id: str
    type: str
    subject: str
    summary: str
    donor: Optional[str]
    coach: Optional[str]
    team: Optional[str]
    amount: Optional[float]
    severity: str
    tags: Optional[List[str]]
    week: Optional[int]
    timestamp: str
    days_ago: Optional[int]
    extra: Dict[str, object]

class LedgerRow(TypedDict, total=False):
    timestamp: str
    week: int
    donor: str
    type: str
    amount: int
    severity: str
    id: str
    subject: str
