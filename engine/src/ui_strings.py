
# ui_strings.py
"""
College AD — v17.9
Plain‑language labels & message helpers for UI and AAD summaries.

Drop-in location:
    /engine/src/ui_strings.py  (or any importable path on PYTHONPATH)

Purpose:
- Provide human-friendly labels for internal metrics (trust, leverage, flags, etc.).
- Centralize number/date formatting.
- Offer small, composable phrases to build donor/coach summaries and inbox lines.
- Keep ZERO game logic here; this is presentation only.

Safe to import anywhere. No side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple, Union
import math
import datetime as _dt
import locale

# Try to respect system locale for numbers; fallback to en_US.
try:
    locale.setlocale(locale.LC_ALL, "")
except Exception:
    try:
        locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
    except Exception:
        pass


# -----------------------------
# Label maps (internal -> public)
# -----------------------------

PUBLIC_LABELS: Dict[str, str] = {
    # Core relationship & influence
    "trust": "Trust",
    "leverage": "Influence",
    "score": "Relationship Score",
    "sentiment": "Mood",
    "risk": "Risk",
    "flags": "Attention Flags",
    "tier": "Donor Tier",
    "prestige": "Prestige",
    "momentum": "Momentum",
    # Finance
    "pledge_amount": "Pledge",
    "pledge_expected": "Expected Pledge",
    "pledge_received": "Received",
    "pledge_gap": "Gap to Goal",
    "balance": "Athletics Balance",
    "yield": "Donor Yield",
    # Ops / cadence
    "last_contact_days": "Days Since Contact",
    "next_action": "Next Action",
    "engagement": "Engagement",
}

# Status terms used across donor lifecycle
PLEDGE_STATUS_PUBLIC = {
    "promised": "Promised",
    "pending": "Pending",
    "received": "Received",
    "lapsed": "Lapsed",
    "cancelled": "Cancelled",
    "declined": "Declined",
}


# -----------------------------
# Formatting helpers
# -----------------------------

def _coerce_number(x: Any) -> Optional[float]:
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return None
        return float(x)
    except Exception:
        return None


def fmt_money(x: Union[int, float, None], *, zero="$0") -> str:
    """Format currency in whole dollars with separators."""
    v = _coerce_number(x)
    if v is None:
        return "—"
    if abs(v) < 0.5:
        return zero
    return f"${int(round(v)):,}"


def fmt_percent(x: Union[int, float, None], *, decimals: int = 0) -> str:
    v = _coerce_number(x)
    if v is None:
        return "—"
    p = round(v * 100.0, decimals)
    fmt = f"{{:.{decimals}f}}%" if decimals else "{:.0f}%"
    return fmt.format(p)


def fmt_signed(x: Union[int, float, None], *, decimals: int = 0) -> str:
    v = _coerce_number(x)
    if v is None:
        return "—"
    q = round(v, decimals)
    sign = "+" if q > 0 else ("−" if q < 0 else "±")
    fmt = f"{{:.{decimals}f}}" if decimals else "{:.0f}"
    return f"{sign}{fmt.format(abs(q))}"


def fmt_days(n: Optional[int]) -> str:
    if n is None:
        return "—"
    if n == 0:
        return "today"
    if n == 1:
        return "yesterday"
    if n < 7:
        return f"{n} days ago"
    w = n // 7
    return f"{w} wk ago"


def fmt_stars(x: Union[int, float, None], *, max_stars: int = 5) -> str:
    v = _coerce_number(x)
    if v is None:
        return "—"
    v = max(0.0, min(float(v), float(max_stars)))
    full = int(v)
    half = 1 if (v - full) >= 0.5 and full < max_stars else 0
    empty = max_stars - full - half
    return "★" * full + ("½" if half else "") + "☆" * empty


def fmt_mood(sentiment: Optional[float]) -> str:
    v = _coerce_number(sentiment)
    if v is None:
        return "—"
    if v >= 0.6:
        return "Very Positive"
    if v >= 0.25:
        return "Positive"
    if v > -0.25:
        return "Neutral"
    if v > -0.6:
        return "Negative"
    return "Very Negative"


def fmt_label(key: str) -> str:
    return PUBLIC_LABELS.get(key, key.replace("_", " ").title())


# -----------------------------
# Phrase templates
# -----------------------------

def phrase_trust(trust: Optional[float]) -> str:
    v = _coerce_number(trust)
    if v is None:
        return "Trust is unknown."
    if v >= 0.8:
        return "Trust is excellent—doors are open."
    if v >= 0.6:
        return "Trust is strong—conversations should go well."
    if v >= 0.4:
        return "Trust is fair—be consistent and specific."
    if v >= 0.2:
        return "Trust is thin—show quick wins before asks."
    return "Trust is fragile—repair before any big asks."


def phrase_leverage(lev: Optional[float]) -> str:
    v = _coerce_number(lev)
    if v is None:
        return "Influence is unknown."
    if v >= 0.8:
        return "You have strong influence here."
    if v >= 0.5:
        return "You have some influence—timing matters."
    return "Low influence—bring a shared win or champion."


def phrase_pledge(status: str, expected: Optional[float], received: Optional[float]) -> str:
    st = PLEDGE_STATUS_PUBLIC.get((status or '').lower(), status or '—')
    exp = fmt_money(expected)
    got = fmt_money(received)
    if (status or '').lower() == 'received':
        return f"{st}: {got} received."
    if (status or '').lower() == 'promised':
        return f"{st}: {exp} expected."
    if (status or '').lower() == 'pending':
        return f"{st}: awaiting {exp}."
    if (status or '').lower() == 'lapsed':
        return f"{st}: follow up needed on {exp}."
    return f"{st}: expected {exp}, received {got}."


def phrase_next_action(next_action: Optional[str], when_days: Optional[int]) -> str:
    if not next_action:
        return "No next action set."
    when = fmt_days(when_days)
    if when == "—":
        return f"Next: {next_action}."
    return f"Next: {next_action} ({when})."


# -----------------------------
# Summary builders
# -----------------------------

def donor_summary(d: Mapping[str, Any]) -> str:
    """Return a compact one-paragraph donor summary using public language.

    Expected keys (best effort):
        name, tier, trust, leverage, sentiment, pledge_status,
        pledge_expected, pledge_received, last_contact_days, next_action
    """
    name = d.get('name', 'Donor')
    tier = d.get('tier', '—')
    mood = fmt_mood(d.get('sentiment'))
    line1 = f"{name} — Tier {tier}. Mood: {mood}."

    line2 = f"{phrase_trust(d.get('trust'))} {phrase_leverage(d.get('leverage'))}"

    line3 = phrase_pledge(
        str(d.get('pledge_status', 'pending')),
        d.get('pledge_expected'),
        d.get('pledge_received'),
    )

    line4 = phrase_next_action(d.get('next_action'), d.get('next_action_in_days') or d.get('last_contact_days'))

    return " ".join([line1, line2, line3, line4]).strip()


def coach_summary(c: Mapping[str, Any]) -> str:
    name = c.get('name', 'Coach')
    trust = phrase_trust(c.get('trust'))
    influence = phrase_leverage(c.get('leverage'))
    mood = fmt_mood(c.get('sentiment'))
    return f"{name} — Mood: {mood}. {trust} {influence}".strip()


# -----------------------------
# Inbox helpers (titles & lines)
# -----------------------------

def inbox_title(event: Mapping[str, Any]) -> str:
    etype = (event.get('type') or 'Update').title()
    subject = event.get('subject') or event.get('donor') or event.get('team') or ""
    if subject:
        return f"{etype}: {subject}"
    return etype


def inbox_line(event: Mapping[str, Any]) -> str:
    """One-line, human version of an event for listing screens."""
    et = (event.get('type') or 'update').lower()
    who = event.get('donor') or event.get('coach') or event.get('team') or 'Item'
    when = event.get('days_ago')
    when_s = fmt_days(when) if when is not None else ''

    if et in {"pledge_promised", "pledge_pending", "pledge_received", "pledge_lapsed"}:
        amt = fmt_money(event.get('amount'))
        verb = {
            'pledge_promised': 'promised',
            'pledge_pending': 'pending',
            'pledge_received': 'received',
            'pledge_lapsed': 'lapsed',
        }.get(et, 'updated')
        tail = f" — {when_s}" if when_s else ""
        return f"{who} {verb} {amt}{tail}"

    if et == "contact_required":
        tail = f" — {when_s}" if when_s else ""
        return f"Contact needed: {who}{tail}"

    # Fallback
    tail = f" • {when_s}" if when_s else ""
    return f"{who} — {event.get('summary','Update')}{tail}".strip()


# -----------------------------
# Small rendering helpers for dashboards
# -----------------------------

def kv_label(key: str, value: Any) -> Tuple[str, str]:
    """Return (public_label, formatted_value) pair."""
    label = fmt_label(key)
    if key in {"trust", "leverage"}:
        return label, fmt_percent(value)
    if key in {"sentiment"}:
        return label, fmt_mood(value)
    if key in {"balance", "pledge_amount", "pledge_expected", "pledge_received", "pledge_gap"}:
        return label, fmt_money(value)
    if key.endswith("_rate") or key.endswith("_pct"):
        return label, fmt_percent(value)
    if key.endswith("_delta"):
        return label, fmt_signed(value)
    return label, str(value if value is not None else "—")


# -----------------------------
# AAD adapter (optional use)
# -----------------------------

def aad_to_public(aad: Mapping[str, Any]) -> Dict[str, Any]:
    """Translate AAD/raw payload to public fields without changing meaning.

    Intended to be a thin adapter. Fields are copied when known, and unknown
    fields are passed through unchanged.
    """
    out: Dict[str, Any] = dict(aad)  # copy

    # Normalize common keys
    rename = {
        'influence': 'leverage',
        'mood': 'sentiment',
        'risk_score': 'risk',
    }
    for k_old, k_new in rename.items():
        if k_old in out and k_new not in out:
            out[k_new] = out.pop(k_old)

    # Ensure pledge status spelling
    if 'pledge_status' in out and isinstance(out['pledge_status'], str):
        key = out['pledge_status'].lower()
        out['pledge_status'] = PLEDGE_STATUS_PUBLIC.get(key, out['pledge_status'])

    return out


__all__ = [
    # maps
    'PUBLIC_LABELS', 'PLEDGE_STATUS_PUBLIC',
    # formatters
    'fmt_money', 'fmt_percent', 'fmt_signed', 'fmt_days', 'fmt_stars', 'fmt_mood', 'fmt_label',
    # phrases & builders
    'phrase_trust', 'phrase_leverage', 'phrase_pledge', 'phrase_next_action',
    'donor_summary', 'coach_summary', 'inbox_title', 'inbox_line', 'kv_label',
    # adapters
    'aad_to_public',
]
