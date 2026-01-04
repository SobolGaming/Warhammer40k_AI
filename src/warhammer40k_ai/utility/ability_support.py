from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ABILITY_BATTLE_FOCUS = "000009894"
ABILITY_DISPARATE_PATHS = "000009896"
ABILITY_BLESSINGS_OF_KHORNE = "000008428"


@lru_cache(maxsize=1)
def _load_ability_factions() -> dict[str, set[str]]:
    candidates = [
        Path(__file__).resolve().parents[3] / "wahapedia_data" / "Abilities.json",
        Path.cwd() / "wahapedia_data" / "Abilities.json",
    ]
    data = None
    for path in candidates:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            break
    if not isinstance(data, list):
        return {}

    mapping: dict[str, set[str]] = {}
    for entry in data:
        try:
            ability_id = str(entry.get("id") or "").strip()
            faction_id = str(entry.get("faction_id") or "").strip().upper()
        except Exception:
            continue
        if not ability_id or not faction_id:
            continue
        mapping.setdefault(ability_id, set()).add(faction_id)
    return mapping


def factions_for_ability_id(ability_id: str) -> set[str]:
    ability_id = str(ability_id or "").strip()
    if not ability_id:
        return set()
    return set(_load_ability_factions().get(ability_id, set()))


def army_has_ability_id(army, ability_id: str) -> bool:
    if army is None:
        return False
    faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
    if faction_id and faction_id in factions_for_ability_id(ability_id):
        return True
    return False
