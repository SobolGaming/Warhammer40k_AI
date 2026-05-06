from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utility.entity_ids import get_entity_id


@dataclass(frozen=True)
class TriarchOption:
    key: str
    name: str
    summary: str


VOICE_OF_THE_TRIARCH_NAME = "Voice of the Triarch"
PHAERON_OF_THE_STARS_NAME = "Phaeron of the Stars (Aura)"
PHAERON_OF_THE_BLADES_NAME = "Phaeron of the Blades (Aura)"
RELENTLESS_MARCH_NAME = "Relentless March (Aura)"

KEY_PHAERON_OF_THE_STARS = "PHAERON_OF_THE_STARS"
KEY_PHAERON_OF_THE_BLADES = "PHAERON_OF_THE_BLADES"
KEY_RELENTLESS_MARCH = "RELENTLESS_MARCH"

PHAERON_OF_THE_STARS = TriarchOption(
    key=KEY_PHAERON_OF_THE_STARS,
    name=PHAERON_OF_THE_STARS_NAME,
    summary='Friendly NECRONS units within 6" of Szarekh re-roll Hit rolls of 1 and Wound rolls of 1.',
)
PHAERON_OF_THE_BLADES = TriarchOption(
    key=KEY_PHAERON_OF_THE_BLADES,
    name=PHAERON_OF_THE_BLADES_NAME,
    summary='Friendly NECRONS units within 6" of Szarekh can re-roll Charge rolls and gain +1 Strength in melee.',
)
RELENTLESS_MARCH = TriarchOption(
    key=KEY_RELENTLESS_MARCH,
    name=RELENTLESS_MARCH_NAME,
    summary='Friendly NECRONS units within 6" of Szarekh gain +2" Move.',
)

VOICE_OF_TRIARCH_OPTIONS: tuple[TriarchOption, ...] = (
    PHAERON_OF_THE_STARS,
    PHAERON_OF_THE_BLADES,
    RELENTLESS_MARCH,
)
VOICE_OF_TRIARCH_BY_KEY = {option.key: option for option in VOICE_OF_TRIARCH_OPTIONS}

_ACTIVE_KEY = "voice_of_triarch_active_key"
_ACTIVE_START_ROUND = "voice_of_triarch_active_start_round"
_ACTIVE_UNTIL_ROUND = "voice_of_triarch_active_until_round"
_ACTIVE_UNTIL_PLAYER = "voice_of_triarch_active_until_player_id"


def _norm_name(text: str) -> str:
    return (text or "").replace("\u2019", "'").replace("\u00e2\u20ac\u2122", "'").strip().lower()


def _get_game_for_unit(unit):
    get_parent_army = getattr(unit, "get_parent_army", None)
    if not callable(get_parent_army):
        return None
    army = get_parent_army()
    return getattr(getattr(army, "player", None), "game", None)


def _ensure_special_rules(unit) -> dict:
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        special_rules = {}
    return special_rules


def _invalidate_voice_of_triarch_caches(unit) -> None:
    get_root = getattr(unit, "get_attached_unit_root", None)
    root = get_root() if callable(get_root) else unit
    invalidate = getattr(root, "_invalidate_ability_activity_cache", None)
    if callable(invalidate):
        invalidate()
    else:
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.clear()
            root._ability_cache = cache


def _unit_on_battlefield(unit) -> bool:
    if unit is None:
        return False
    is_alive_fn = getattr(unit, "is_alive", None)
    if callable(is_alive_fn):
        if not bool(is_alive_fn()):
            return False
    elif getattr(unit, "is_alive", True) is False:
        return False
    if not bool(getattr(unit, "deployed", True)):
        return False
    if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
        return False
    in_reserves_fn = getattr(unit, "is_in_reserves", None)
    if callable(in_reserves_fn) and bool(in_reserves_fn()):
        return False
    if bool(getattr(unit, "embarked_in", None)) or bool(getattr(unit, "is_embarked", False)):
        return False
    return True


def ability_name_to_key(name: str) -> Optional[str]:
    norm = _norm_name(name)
    if norm == _norm_name(PHAERON_OF_THE_STARS_NAME):
        return KEY_PHAERON_OF_THE_STARS
    if norm == _norm_name(PHAERON_OF_THE_BLADES_NAME):
        return KEY_PHAERON_OF_THE_BLADES
    if norm == _norm_name(RELENTLESS_MARCH_NAME):
        return KEY_RELENTLESS_MARCH
    return None


def unit_has_voice_of_triarch_ability(unit) -> bool:
    if unit is None:
        return False
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if _norm_name(getattr(ability, "name", "")) == _norm_name(VOICE_OF_THE_TRIARCH_NAME):
            return True
    return False


def unit_has_triarch_sub_ability(unit) -> bool:
    if unit is None:
        return False
    valid_keys = {option.key for option in VOICE_OF_TRIARCH_OPTIONS}
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        key = ability_name_to_key(getattr(ability, "name", ""))
        if key in valid_keys:
            return True
    return False


def get_active_voice_of_triarch_key(unit, *, game=None, battle_round: Optional[int] = None) -> Optional[str]:
    if unit is None or not unit_has_voice_of_triarch_ability(unit):
        return None
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        return None
    key = str(special_rules.get(_ACTIVE_KEY, "") or "").strip().upper()
    if not key:
        return None
    stored_until = special_rules.get(_ACTIVE_UNTIL_ROUND)
    if battle_round is None:
        if game is None:
            game = _get_game_for_unit(unit)
        battle_round = int(getattr(game, "turn", 0) or 0) if game is not None else None
    if battle_round is not None and stored_until is not None:
        if int(battle_round or 0) > int(stored_until or 0):
            return None
    return key


def unit_has_active_voice_of_triarch(unit, key: str, *, game=None, battle_round: Optional[int] = None) -> bool:
    choice_key = str(key or "").strip().upper()
    if not choice_key:
        return False
    return get_active_voice_of_triarch_key(unit, game=game, battle_round=battle_round) == choice_key


def set_active_voice_of_triarch(
    unit,
    key: str,
    *,
    start_round: int,
    expires_round: int,
    player_id: Optional[str] = None,
) -> None:
    if unit is None or not unit_has_voice_of_triarch_ability(unit):
        return
    key_token = str(key or "").strip().upper()
    if key_token not in VOICE_OF_TRIARCH_BY_KEY:
        return
    special_rules = _ensure_special_rules(unit)
    special_rules[_ACTIVE_KEY] = key_token
    special_rules[_ACTIVE_START_ROUND] = int(start_round or 0)
    special_rules[_ACTIVE_UNTIL_ROUND] = int(expires_round or 0)
    special_rules[_ACTIVE_UNTIL_PLAYER] = str(player_id or "")
    unit.special_rules = special_rules
    _invalidate_voice_of_triarch_caches(unit)


def clear_active_voice_of_triarch(unit) -> None:
    if unit is None:
        return
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        return
    special_rules.pop(_ACTIVE_KEY, None)
    special_rules.pop(_ACTIVE_START_ROUND, None)
    special_rules.pop(_ACTIVE_UNTIL_ROUND, None)
    special_rules.pop(_ACTIVE_UNTIL_PLAYER, None)
    unit.special_rules = special_rules
    _invalidate_voice_of_triarch_caches(unit)


def _unit_is_valid_voice_of_triarch_source(unit) -> bool:
    return bool(unit_has_voice_of_triarch_ability(unit) and _unit_on_battlefield(unit))


def voice_of_triarch_units(army) -> list:
    if army is None:
        return []
    return [unit for unit in list(getattr(army, "units", []) or []) if unit_has_voice_of_triarch_ability(unit)]


def voice_of_triarch_selectable_units(army) -> list:
    if army is None:
        return []
    return [unit for unit in list(getattr(army, "units", []) or []) if _unit_is_valid_voice_of_triarch_source(unit)]


class VoiceOfTriarchManager:
    """The Silent King: at the start of each battle round, select one Triarch ability."""

    def __init__(self, army=None):
        self.army = army

    def get_voice_of_triarch_units(self) -> list:
        return voice_of_triarch_selectable_units(self.army)

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if self.army is None:
            return
        army_player = getattr(self.army, "player", None)
        if game is None:
            game = getattr(army_player, "game", None) if army_player is not None else None

        units = voice_of_triarch_units(self.army)
        if not units:
            return
        battle_round = int(battle_round or 0)
        expires_round = int(battle_round) + 1 if battle_round else 0
        player_id = str(getattr(army_player, "id", "") or "")

        for unit in units:
            clear_active_voice_of_triarch(unit)
            if game is None or not bool(getattr(game, "is_authoritative", True)):
                continue
            if not _unit_is_valid_voice_of_triarch_source(unit):
                continue

            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest

            unit_id = str(get_entity_id(unit) or "")
            if not unit_id:
                continue

            queue = getattr(game, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                stale_ids: list[str] = []
                has_current_pending = False
                for request in list(queue.list() or []):
                    if str(getattr(request, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    context = dict(getattr(request, "context", {}) or {})
                    if str(context.get("ability", "") or "") != "voice_of_triarch":
                        continue
                    if str(context.get("source_unit_id", "") or "") != unit_id:
                        continue
                    request_round = int(context.get("battle_round", 0) or 0)
                    if request_round == battle_round:
                        has_current_pending = True
                        break
                    stale_ids.append(str(getattr(request, "decision_id", "") or ""))
                for decision_id in stale_ids:
                    if decision_id:
                        queue.pop(decision_id)
                if has_current_pending:
                    continue

            options = [
                DecisionOption.create(
                    option.name,
                    payload={
                        "choice_key": option.key,
                        "choice_name": option.name,
                        "summary": option.summary,
                        "ability": "voice_of_triarch",
                        "ability_name": VOICE_OF_THE_TRIARCH_NAME,
                        "source_unit_id": unit_id,
                        "unit_id": unit_id,
                        "battle_round": int(battle_round or 0),
                        "expires_round": int(expires_round or 0),
                        "player_id": player_id,
                    },
                )
                for option in VOICE_OF_TRIARCH_OPTIONS
            ]
            if not options:
                continue

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Voice of the Triarch: select one Triarch ability.",
                player_id=getattr(army_player, "id", None),
                options=options,
                context={
                    "ability": "voice_of_triarch",
                    "ability_name": VOICE_OF_THE_TRIARCH_NAME,
                    "source_unit_id": unit_id,
                    "unit_id": unit_id,
                    "battle_round": int(battle_round or 0),
                    "expires_round": int(expires_round or 0),
                    "player_id": player_id,
                    "allowed_choice_keys": [option.key for option in VOICE_OF_TRIARCH_OPTIONS],
                },
            )
            if hasattr(game, "request_decision"):
                game.request_decision(request)
