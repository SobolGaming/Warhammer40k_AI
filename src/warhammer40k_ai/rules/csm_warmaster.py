from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WarmasterOption:
    key: str
    name: str
    summary: str


WARMMASTER_NAME = "The Warmaster"
PARAGON_OF_HATRED_NAME = "Paragon of Hatred (Aura)"
MARK_OF_CHAOS_ASCENDANT_NAME = "Mark of Chaos Ascendant (Aura)"
LORD_OF_THE_TRAITOR_LEGIONS_NAME = "Lord of the Traitor Legions (Aura)"

KEY_PARAGON_OF_HATRED = "PARAGON_OF_HATRED"
KEY_MARK_OF_CHAOS_ASCENDANT = "MARK_OF_CHAOS_ASCENDANT"
KEY_LORD_OF_THE_TRAITOR_LEGIONS = "LORD_OF_THE_TRAITOR_LEGIONS"

PARAGON_OF_HATRED = WarmasterOption(
    key=KEY_PARAGON_OF_HATRED,
    name=PARAGON_OF_HATRED_NAME,
    summary='Friendly HERETIC ASTARTES (excluding DAMNED) within 6" can re-roll Hit rolls.',
)
MARK_OF_CHAOS_ASCENDANT = WarmasterOption(
    key=KEY_MARK_OF_CHAOS_ASCENDANT,
    name=MARK_OF_CHAOS_ASCENDANT_NAME,
    summary='Friendly HERETIC ASTARTES INFANTRY/MOUNTED (excluding DAMNED) within 6" gain a 4+ invulnerable save.',
)
LORD_OF_THE_TRAITOR_LEGIONS = WarmasterOption(
    key=KEY_LORD_OF_THE_TRAITOR_LEGIONS,
    name=LORD_OF_THE_TRAITOR_LEGIONS_NAME,
    summary='Friendly HERETIC ASTARTES (excluding DAMNED) within 6" can re-roll Leadership and Battle-shock tests.',
)

WARMMASTER_OPTIONS: tuple[WarmasterOption, ...] = (
    PARAGON_OF_HATRED,
    MARK_OF_CHAOS_ASCENDANT,
    LORD_OF_THE_TRAITOR_LEGIONS,
)

_ACTIVE_KEY = "warmaster_active_key"
_ACTIVE_START_ROUND = "warmaster_active_start_round"
_ACTIVE_UNTIL_ROUND = "warmaster_active_until_round"
_ACTIVE_UNTIL_PLAYER = "warmaster_active_until_player_id"


def _norm_name(text: str) -> str:
    return (text or "").replace("\u2019", "'").replace("\u00e2\u20ac\u2122", "'").strip().lower()


def _get_game_for_unit(unit):
    try:
        army = unit.get_parent_army()
    except Exception:
        return None
    return getattr(getattr(army, "player", None), "game", None)


def _ensure_special_rules(unit) -> dict:
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    return sr


def _invalidate_warmaster_caches(unit) -> None:
    try:
        root = unit.get_attached_unit_root()
    except Exception:
        root = unit
    cache = getattr(root, "_ability_cache", None)
    if isinstance(cache, dict):
        cache.clear()
        root._ability_cache = cache


def unit_has_warmaster_ability(unit) -> bool:
    if unit is None:
        return False
    try:
        for ab in list(getattr(unit, "possible_abilities", []) or []):
            if _norm_name(getattr(ab, "name", "")) == _norm_name(WARMMASTER_NAME):
                return True
    except Exception:
        return False
    return False


def ability_name_to_key(name: str) -> Optional[str]:
    norm = _norm_name(name)
    if norm == _norm_name(PARAGON_OF_HATRED_NAME):
        return KEY_PARAGON_OF_HATRED
    if norm == _norm_name(MARK_OF_CHAOS_ASCENDANT_NAME):
        return KEY_MARK_OF_CHAOS_ASCENDANT
    if norm == _norm_name(LORD_OF_THE_TRAITOR_LEGIONS_NAME):
        return KEY_LORD_OF_THE_TRAITOR_LEGIONS
    return None


def get_active_warmaster_key(unit, *, game=None, battle_round: Optional[int] = None) -> Optional[str]:
    if unit is None or not unit_has_warmaster_ability(unit):
        return None
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        return None
    key = str(sr.get(_ACTIVE_KEY, "") or "").strip().upper()
    if not key:
        return None
    stored_until = sr.get(_ACTIVE_UNTIL_ROUND)
    if battle_round is None:
        if game is None:
            game = _get_game_for_unit(unit)
        try:
            battle_round = int(getattr(game, "turn", 0) or 0)
        except Exception:
            battle_round = None
    if battle_round is not None and stored_until is not None:
        try:
            if int(battle_round or 0) > int(stored_until or 0):
                return None
        except Exception:
            return None
    return key


def unit_has_active_warmaster(unit, key: str, *, game=None, battle_round: Optional[int] = None) -> bool:
    choice_key = str(key or "").strip().upper()
    if not choice_key:
        return False
    return get_active_warmaster_key(unit, game=game, battle_round=battle_round) == choice_key


def set_active_warmaster(
    unit,
    key: str,
    *,
    start_round: int,
    expires_round: int,
    player_id: Optional[str] = None,
) -> None:
    if unit is None or not unit_has_warmaster_ability(unit):
        return
    sr = _ensure_special_rules(unit)
    sr[_ACTIVE_KEY] = str(key or "").strip().upper()
    sr[_ACTIVE_START_ROUND] = int(start_round or 0)
    sr[_ACTIVE_UNTIL_ROUND] = int(expires_round or 0)
    sr[_ACTIVE_UNTIL_PLAYER] = str(player_id or "")
    unit.special_rules = sr
    _invalidate_warmaster_caches(unit)


def clear_active_warmaster(unit) -> None:
    if unit is None:
        return
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        return
    sr.pop(_ACTIVE_KEY, None)
    sr.pop(_ACTIVE_START_ROUND, None)
    sr.pop(_ACTIVE_UNTIL_ROUND, None)
    sr.pop(_ACTIVE_UNTIL_PLAYER, None)
    unit.special_rules = sr
    _invalidate_warmaster_caches(unit)


def _unit_is_valid_warmaster_source(unit) -> bool:
    if unit is None or not unit_has_warmaster_ability(unit):
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


def warmaster_units(army) -> list:
    if army is None:
        return []
    units = []
    for unit in list(getattr(army, "units", []) or []):
        if unit is None:
            continue
        if unit_has_warmaster_ability(unit):
            units.append(unit)
    return units


def warmaster_selectable_units(army) -> list:
    if army is None:
        return []
    return [u for u in list(getattr(army, "units", []) or []) if _unit_is_valid_warmaster_source(u)]


class WarmasterManager:
    """Abaddon: select one Warmaster ability in your Command phase."""

    def __init__(self, army=None):
        self.army = army

    def get_warmaster_units(self) -> list:
        return warmaster_selectable_units(self.army)

    def on_command_phase_start(self, player, *, game=None) -> None:
        if self.army is None:
            return
        army_player = getattr(self.army, "player", None)
        if army_player is None:
            return
        if player is not None and player is not army_player:
            if str(getattr(player, "id", "") or "") != str(getattr(army_player, "id", "") or ""):
                return
        if game is None:
            game = getattr(army_player, "game", None)

        units = warmaster_units(self.army)
        if not units:
            return

        try:
            battle_round = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        except Exception:
            battle_round = 0
        expires_round = int(battle_round or 0) + 1 if battle_round else 0
        player_id = str(getattr(army_player, "id", "") or "")

        for unit in units:
            clear_active_warmaster(unit)
            if game is None or not bool(getattr(game, "is_authoritative", True)):
                continue
            if not _unit_is_valid_warmaster_source(unit):
                continue
            try:
                from ..engine.decision_kinds import DECISION_CHOOSE_WARMASTER_ABILITY
                from ..engine.decisions import DecisionOption, DecisionRequest
                from ..utility.entity_ids import get_entity_id
            except Exception:
                continue
            unit_id = get_entity_id(unit)
            queue = getattr(game, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_WARMASTER_ABILITY:
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
                        for opt in WARMMASTER_OPTIONS
                    ]
                    if not req_options:
                        continue
                    req = DecisionRequest.create(
                        DECISION_CHOOSE_WARMASTER_ABILITY,
                        "Select Warmaster ability.",
                        player_id=player_id,
                        options=req_options,
                        context={
                            "unit_id": unit_id,
                            "battle_round": int(battle_round or 0),
                            "player_id": player_id,
                            "expires_round": int(expires_round or 0),
                        },
                    )
                    if hasattr(game, "request_decision"):
                        game.request_decision(req)
