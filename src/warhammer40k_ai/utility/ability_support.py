from __future__ import annotations

import json
import html
import re
from functools import lru_cache
from pathlib import Path

ABILITY_BATTLE_FOCUS = "000009894"
ABILITY_DISPARATE_PATHS = "000009896"
ABILITY_BLESSINGS_OF_KHORNE = "000008428"
ABILITY_NURGLES_GIFT = "000008396"
ABILITY_TEMPLAR_VOWS = "000008526"
ABILITY_SHADOW_OF_CHAOS = "000008433"
ABILITY_OATH_OF_MOMENT = "000008350"
ABILITY_HARBINGERS_OF_DREAD = "000008512"
ABILITY_SUPER_HEAVY_WALKER = "000008513"
ABILITY_DREADBLADES = "000008514"
ABILITY_DARK_PACTS = "000008359"
ABILITY_CULT_OF_DARK_GODS = "000008360"
ABILITY_CABAL_OF_SORCERERS = "000008424"
ABILITY_PACT_OF_SORCERY = "000010190"
ABILITY_SYNAPSE = "000000705"
ABILITY_SHADOW_IN_THE_WARP = "000000707"
ABILITY_POWER_FROM_PAIN = "000008507"
ABILITY_FOR_THE_GREATER_GOOD = "000008439"
ABILITY_WAAAGH = "000003676"
ABILITY_PRIORITISED_EFFICIENCY = "000010432"
ABILITY_CULT_AMBUSH = "000008501"
ABILITY_CORSAIRS_AND_TRAVELLING_PLAYERS = "000009974"
_PACT_PREFIX = "pact of "
_PACT_RE = re.compile(r"cannot select\s+(.+?)\s+as your army faction", re.IGNORECASE)


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


@lru_cache(maxsize=1)
def _load_pact_restrictions() -> dict[str, list[dict[str, str]]]:
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

    out: dict[str, list[dict[str, str]]] = {}
    for entry in data:
        try:
            name = str(entry.get("name") or "").strip()
            if not name.lower().startswith(_PACT_PREFIX):
                continue
            faction_id = str(entry.get("faction_id") or "").strip().upper()
            desc = str(entry.get("description") or "")
        except Exception:
            continue
        if not faction_id:
            continue
        text = re.sub(r"<[^>]+>", " ", desc)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        match = _PACT_RE.search(text)
        if not match:
            continue
        forbidden = match.group(1).strip().strip(".")
        if not forbidden:
            continue
        out.setdefault(faction_id, []).append({"name": name, "forbidden": forbidden})
    return out


def pact_restrictions_for_faction(faction_id: str) -> list[dict[str, str]]:
    fid = str(faction_id or "").strip().upper()
    if not fid:
        return []
    return list(_load_pact_restrictions().get(fid, []))
