# College AD — v17.6 Personality Core (Design)

**Version:** v17.6 Design • Personality & Tone Engine  
**Author:** GPT-5 (System Design)  
**Last Updated:** 2025-10-28

---

## 🎯 Goal
Introduce a lightweight, seedable **Personality Core** for NPCs (Donors, Coaches, Journalists, Admins).  
This core informs: event likelihood tweaks, communication tone, and future live conversations (calls/meetings).

---

## 🧱 Data Model

### Personality Object
```json
{
  "id": "DONOR_0071",
  "archetype": "Donor_Patron",
  "seed": "DONOR_0071",
  "traits": {
    "charisma": 0.68,
    "authenticity": 0.41,
    "communication": 0.77,
    "strategy": 0.35,
    "temperament": 0.82
  },
  "modifiers": {
    "risk_tolerance": 0.45,
    "generosity": 0.72,
    "media_savvy": 0.51
  },
  "style": {
    "email": "warm",
    "text": "brief",
    "call": "animated",
    "meeting": "collaborative"
  }
}
```

### Archetypes
Defined in `engine/config/personality_profiles.json`. Each archetype supplies target ranges + style defaults.  
Archetype examples: `Donor_Patron`, `Donor_Corporate`, `Coach_Charismatic`, `Coach_Grinder`, `Journalist_Aggressive`, `Admin_Cautious`.

---

## ⚙️ Engine API (v17.6)

Provided by `engine/src/personality_engine.py`:

- `generate(seed: str, role: str, overrides: dict|None) -> dict`  
  Returns a stable personality dict for an entity (seeded by id/name).

- `interaction_stance(persona: dict, context: dict) -> dict`  
  Maps personality + context (event category, intensity, sentiment) → a stance object:
  ```json
  { "tone": "positive|neutral|negative", "energy": "low|medium|high", "risk": 0.42 }
  ```

- `donor_propensity(persona: dict, school_sentiment: float, prestige: float) -> float`  
  Returns a 0..1 propensity that can nudge donor event probabilities.

- `style_for_channel(persona: dict, channel: str) -> str`  
  E.g., `"warm"`, `"curt"`, `"animated"` — drives comms formatting later.

---

## 🔗 Minimal Integration (v17.6)

- (Optional) In `reg_engine.advance_reg_tick`, when choosing donor events, multiply trigger chance by `donor_propensity()` if a donor persona is present. Keep bounded (e.g., clamp 0.25×..1.75×).  
- Write `personality_ref` into `WORLD_EVENTS_LOG` notes (e.g., `Donor Persona: Donor_Patron`).
- No schema changes required. Finance & Analyzer remain unchanged.

---

## 🧪 Validation Checklist

1. Seed 10 sample donors and print personalities.  
2. Simulate `ALUMNI_PUSH` with random schools; ensure a spread of tones in WORLD_EVENTS_LOG notes.  
3. Run 10-week sim — confirm performance unchanged and logs readable.

---

## 🚀 Road to v18

- v18.0: Inbox reads `interaction_stance` to render subject/body tone and style per NPC.  
- v18.2: Calls leverage tone + temperament for turn-taking and escalation.  
- v18.4: Meetings coordinate multiple personas with role-based objectives.

---

**End of Design — v17.6 Personality Core**
