from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utility.aura_utils import unit_within_range_of_unit


@dataclass(frozen=True)
class WrathfulPresenceOption:
    key: str
    name: str
    summary: str


WRATHFUL_PRESENCE_NAME = "Wrathful Presence"
BLOOD_GODS_FAVOUR_NAME = "The Blood God's Favour"
OVERWHELMING_WRATH_NAME = "Overwhelming Wrath (Aura)"
DRIVEN_BY_ULTIMATE_RAGE_NAME = "Driven by Ultimate Rage (Aura)"

KEY_BLOOD_GODS_FAVOUR = "BLOOD_GODS_FAVOUR"
KEY_OVERWHELMING_WRATH = "OVERWHELMING_WRATH"
KEY_DRIVEN_BY_ULTIMATE_RAGE = "DRIVEN_BY_ULTIMATE_RAGE"

BLOOD_GODS_FAVOUR = WrathfulPresenceOption(
    key=KEY_BLOOD_GODS_FAVOUR,
    name=BLOOD_GODS_FAVOUR_NAME,
    summary="Blessings of Khorne rolls can re-roll up to six dice while Angron is on the battlefield.",
)
OVERWHELMING_WRATH = WrathfulPresenceOption(
    key=KEY_OVERWHELMING_WRATH,
    name=OVERWHELMING_WRATH_NAME,
    summary='Enemy units within 6" that are selected to Fall Back must pass a Leadership test or remain stationary.',
)
DRIVEN_BY_ULTIMATE_RAGE = WrathfulPresenceOption(
    key=KEY_DRIVEN_BY_ULTIMATE_RAGE,
    name=DRIVEN_BY_ULTIMATE_RAGE_NAME,
    summary='Friendly WORLD EATERS within 6" can ignore any or all Move, Advance/Charge, WS and Hit roll modifiers.',
)

WRATHFUL_PRESENCE_OPTIONS: tuple[WrathfulPresenceOption, ...] = (
    BLOOD_GODS_FAVOUR,
    OVERWHELMING_WRATH,
    DRIVEN_BY_ULTIMATE_RAGE,
)

_ACTIVE_KEY = "wrathful_presence_active_key"
_ACTIVE_ROUND = "wrathful_presence_round"


def _norm_name(text: str) -> str:
    return (text or "").replace("\u00e2\u20ac\u2122", "'").strip().lower()


def _unit_has_wrathful_presence(unit) -> bool:
    if unit is None:
        return False
    try:
        for ab in (getattr(unit, "possible_abilities", []) or []):
            if _norm_name(getattr(ab, "name", "")) == _norm_name(WRATHFUL_PRESENCE_NAME):
                return True
    except Exception:
        return False
    return False


def _get_game_for_unit(unit):
    try:
        army = unit.get_parent_army()
        return getattr(getattr(army, "player", None), "game", None)
    except Exception:
        return None


def _ensure_special_rules(unit) -> dict:
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    return sr


def ability_name_to_key(name: str) -> Optional[str]:
    norm = _norm_name(name)
    if norm == _norm_name(BLOOD_GODS_FAVOUR_NAME):
        return KEY_BLOOD_GODS_FAVOUR
    if norm == _norm_name(OVERWHELMING_WRATH_NAME):
        return KEY_OVERWHELMING_WRATH
    if norm == _norm_name(DRIVEN_BY_ULTIMATE_RAGE_NAME):
        return KEY_DRIVEN_BY_ULTIMATE_RAGE
    return None


def get_active_wrathful_presence_key(unit, *, game=None, battle_round: Optional[int] = None) -> Optional[str]:
    if unit is None:
        return None
    if not _unit_has_wrathful_presence(unit):
        return None
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        return None
    key = str(sr.get(_ACTIVE_KEY, "") or "").strip().upper()
    if not key:
        return None
    stored_round = sr.get(_ACTIVE_ROUND)
    if battle_round is None:
        if game is None:
            game = _get_game_for_unit(unit)
        try:
            battle_round = int(getattr(game, "turn", 0) or 0)
        except Exception:
            battle_round = None
    if battle_round is not None:
        try:
            if int(stored_round or 0) != int(battle_round or 0):
                return None
        except Exception:
            return None
    return key


def unit_has_active_wrathful_presence(unit, key: str, *, game=None, battle_round: Optional[int] = None) -> bool:
    if unit is None:
        return False
    key = str(key or "").strip().upper()
    if not key:
        return False
    return get_active_wrathful_presence_key(unit, game=game, battle_round=battle_round) == key


def set_active_wrathful_presence(unit, key: str, *, battle_round: int) -> None:
    if unit is None:
        return
    if not _unit_has_wrathful_presence(unit):
        return
    sr = _ensure_special_rules(unit)
    sr[_ACTIVE_KEY] = str(key or "").strip().upper()
    sr[_ACTIVE_ROUND] = int(battle_round or 0)
    unit.special_rules = sr


def clear_active_wrathful_presence(unit) -> None:
    if unit is None:
        return
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        return
    sr.pop(_ACTIVE_KEY, None)
    sr.pop(_ACTIVE_ROUND, None)
    unit.special_rules = sr


def _unit_is_valid_wrathful_presence_source(unit) -> bool:
    if unit is None:
        return False
    if not _unit_has_wrathful_presence(unit):
        return False
    try:
        if hasattr(unit, "is_alive") and callable(unit.is_alive):
            if not unit.is_alive():
                return False
    except Exception:
        return False
    try:
        if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", True)):
            return False
    except Exception:
        return False
    try:
        if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
            return False
    except Exception:
        return False
    return True


def wrathful_presence_units(army) -> list:
    if army is None:
        return []
    units = []
    for unit in list(getattr(army, "units", []) or []):
        if unit is None:
            continue
        if _unit_has_wrathful_presence(unit):
            units.append(unit)
    return units


def blood_gods_favour_rerolls_for_army(army, *, battle_round: Optional[int] = None) -> int:
    if army is None:
        return 0
    if battle_round is None:
        try:
            game = getattr(getattr(army, "player", None), "game", None)
            battle_round = int(getattr(game, "turn", 0) or 0)
        except Exception:
            battle_round = None
    for unit in list(getattr(army, "units", []) or []):
        if not _unit_is_valid_wrathful_presence_source(unit):
            continue
        if not unit_has_active_wrathful_presence(unit, KEY_BLOOD_GODS_FAVOUR, battle_round=battle_round):
            continue
        try:
            if not (getattr(unit, "deployed", False) and unit.is_alive() and getattr(unit, "reserve_status", "deployed") == "deployed"):
                continue
        except Exception:
            continue
        return 6
    return 0


def driven_by_ultimate_rage_sources_for_unit(unit, *, game_map=None, battle_round: Optional[int] = None) -> list:
    if unit is None:
        return []
    try:
        if not unit.has_any_keyword("WORLD EATERS"):
            return []
    except Exception:
        return []
    if game_map is None:
        try:
            game = _get_game_for_unit(unit)
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
    if game_map is None:
        return []

    sources = []
    for source in list(game_map.get_friendly_units(unit) or []):
        if not _unit_is_valid_wrathful_presence_source(source):
            continue
        if not unit_has_active_wrathful_presence(source, KEY_DRIVEN_BY_ULTIMATE_RAGE, battle_round=battle_round):
            continue
        try:
            if unit_within_range_of_unit(source, unit, 6.0, use_attached_aggregate=True):
                sources.append(source)
        except Exception:
            continue
    return sources


def driven_by_ultimate_rage_applies(unit, *, game_map=None, battle_round: Optional[int] = None) -> bool:
    return bool(driven_by_ultimate_rage_sources_for_unit(unit, game_map=game_map, battle_round=battle_round))


def overwhelming_wrath_sources_for_unit(unit, *, game_map=None, battle_round: Optional[int] = None) -> list:
    if unit is None:
        return []
    if game_map is None:
        try:
            game = _get_game_for_unit(unit)
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
    if game_map is None:
        return []
    sources = []
    for enemy in list(game_map.get_enemy_units(unit) or []):
        if not _unit_is_valid_wrathful_presence_source(enemy):
            continue
        if not unit_has_active_wrathful_presence(enemy, KEY_OVERWHELMING_WRATH, battle_round=battle_round):
            continue
        try:
            if unit_within_range_of_unit(enemy, unit, 6.0, use_attached_aggregate=True):
                sources.append(enemy)
        except Exception:
            continue
    return sources


class WrathfulPresenceManager:
    """Angron: Wrathful Presence selection each battle round."""

    def __init__(self, army=None):
        self.army = army

    def get_wrathful_presence_units(self) -> list:
        return wrathful_presence_units(self.army)

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if self.army is None:
            return
        if game is None:
            try:
                game = getattr(getattr(self.army, "player", None), "game", None)
            except Exception:
                game = None
        units = self.get_wrathful_presence_units()
        if not units:
            return

        player = getattr(self.army, "player", None)

        for unit in units:
            clear_active_wrathful_presence(unit)
            if game is not None:
                if not bool(getattr(game, "is_authoritative", True)):
                    continue
                try:
                    from ..engine.decision_kinds import DECISION_CHOOSE_WRATHFUL_PRESENCE
                    from ..engine.decisions import DecisionOption, DecisionRequest
                    from ..utility.entity_ids import get_entity_id
                except Exception:
                    continue
                unit_id = get_entity_id(unit)
                queue = getattr(game, "decision_queue", None)
                if queue is not None and hasattr(queue, "list"):
                    for req in list(queue.list() or []):
                        if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_WRATHFUL_PRESENCE:
                            continue
                        ctx = getattr(req, "context", {}) or {}
                        if str(ctx.get("unit_id", "")) == str(unit_id):
                            break
                    else:
                        req_options = [
                            DecisionOption.create(
                                opt.name,
                                payload={"choice_key": opt.key, "summary": opt.summary, "unit_id": unit_id},
                            )
                            for opt in WRATHFUL_PRESENCE_OPTIONS
                        ]
                        if not req_options:
                            continue
                        req = DecisionRequest.create(
                            DECISION_CHOOSE_WRATHFUL_PRESENCE,
                            "Select Wrathful Presence.",
                            player_id=getattr(player, "id", None),
                            options=req_options,
                            context={"unit_id": unit_id, "battle_round": int(battle_round or 0)},
                        )
                        if hasattr(game, "request_decision"):
                            game.request_decision(req)
                continue

            choice = None
            try:
                if player is not None:
                    choice = player._choose_optional_value(
                        "WRATHFUL_PRESENCE",
                        [o.name for o in WRATHFUL_PRESENCE_OPTIONS],
                        {"ability": WRATHFUL_PRESENCE_NAME, "options": [o.name for o in WRATHFUL_PRESENCE_OPTIONS]},
                    )
            except Exception:
                choice = None
            selected = None
            if choice in WRATHFUL_PRESENCE_OPTIONS:
                selected = choice
            elif isinstance(choice, str):
                choice_norm = choice.strip().lower()
                for opt in WRATHFUL_PRESENCE_OPTIONS:
                    if opt.name.strip().lower() == choice_norm or opt.key.strip().lower() == choice_norm:
                        selected = opt
                        break
            if selected is not None:
                set_active_wrathful_presence(unit, selected.key, battle_round=int(battle_round or 0))
