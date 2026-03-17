from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Optional

from ..utility.entity_ids import get_entity_id


@dataclass(frozen=True)
class PrimarchOfTheFirstLegionOption:
    key: str
    name: str
    summary: str


PRIMARCH_OF_THE_FIRST_LEGION_NAME = "Primarch of the First Legion"
MIST_WREATHED_SHADOW_REALMS_NAME = "Mist-wreathed Shadow Realms"
MARTIAL_EXEMPLAR_NAME = "Martial Exemplar (Aura)"
NO_HIDING_FROM_THE_WATCHERS_NAME = "No Hiding From the Watchers (Aura)"

KEY_MIST_WREATHED_SHADOW_REALMS = "MIST_WREATHED_SHADOW_REALMS"
KEY_MARTIAL_EXEMPLAR = "MARTIAL_EXEMPLAR"
KEY_NO_HIDING_FROM_THE_WATCHERS = "NO_HIDING_FROM_THE_WATCHERS"

MIST_WREATHED_SHADOW_REALMS = PrimarchOfTheFirstLegionOption(
    key=KEY_MIST_WREATHED_SHADOW_REALMS,
    name=MIST_WREATHED_SHADOW_REALMS_NAME,
    summary='In your Command phase, if this unit is not within Engagement Range, it can enter Strategic Reserves.',
)
MARTIAL_EXEMPLAR = PrimarchOfTheFirstLegionOption(
    key=KEY_MARTIAL_EXEMPLAR,
    name=MARTIAL_EXEMPLAR_NAME,
    summary='Friendly ADEPTUS ASTARTES units within 6" re-roll melee Hit rolls of 1 and Wound rolls of 1.',
)
NO_HIDING_FROM_THE_WATCHERS = PrimarchOfTheFirstLegionOption(
    key=KEY_NO_HIDING_FROM_THE_WATCHERS,
    name=NO_HIDING_FROM_THE_WATCHERS_NAME,
    summary='Friendly ADEPTUS ASTARTES units within 6" gain Feel No Pain 4+ against mortal wounds.',
)

PRIMARCH_OF_THE_FIRST_LEGION_OPTIONS: tuple[PrimarchOfTheFirstLegionOption, ...] = (
    MIST_WREATHED_SHADOW_REALMS,
    MARTIAL_EXEMPLAR,
    NO_HIDING_FROM_THE_WATCHERS,
)
PRIMARCH_OF_THE_FIRST_LEGION_BY_KEY = {
    option.key: option for option in PRIMARCH_OF_THE_FIRST_LEGION_OPTIONS
}
_PRIMARCH_ORDER_BY_KEY = {
    option.key: idx for idx, option in enumerate(PRIMARCH_OF_THE_FIRST_LEGION_OPTIONS)
}

_ACTIVE_KEYS = "primarch_of_the_first_legion_active_keys"
_ACTIVE_START_ROUND = "primarch_of_the_first_legion_active_start_round"
_ACTIVE_UNTIL_ROUND = "primarch_of_the_first_legion_active_until_round"
_ACTIVE_UNTIL_PLAYER = "primarch_of_the_first_legion_active_until_player_id"


def _norm_name(text: str) -> str:
    return (
        str(text or "")
        .replace("\u2019", "'")
        .replace("\u00e2\u20ac\u2122", "'")
        .strip()
        .lower()
    )


def _coerce_int(value, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _get_game_for_unit(unit):
    get_parent_army = getattr(unit, "get_parent_army", None)
    if not callable(get_parent_army):
        return None
    army = get_parent_army()
    return getattr(getattr(army, "player", None), "game", None)


def _ensure_special_rules(unit) -> dict:
    special_rules = getattr(unit, "special_rules", None)
    if isinstance(special_rules, dict):
        return special_rules
    return {}


def _invalidate_primarch_of_the_first_legion_caches(unit) -> None:
    get_root = getattr(unit, "get_attached_unit_root", None)
    root = get_root() if callable(get_root) else unit
    invalidate = getattr(root, "_invalidate_ability_activity_cache", None)
    if callable(invalidate):
        invalidate()
        return
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
    if norm == _norm_name(MIST_WREATHED_SHADOW_REALMS_NAME):
        return KEY_MIST_WREATHED_SHADOW_REALMS
    if norm == _norm_name(MARTIAL_EXEMPLAR_NAME):
        return KEY_MARTIAL_EXEMPLAR
    if norm == _norm_name(NO_HIDING_FROM_THE_WATCHERS_NAME):
        return KEY_NO_HIDING_FROM_THE_WATCHERS
    return None


def unit_has_primarch_of_the_first_legion_ability(unit) -> bool:
    if unit is None:
        return False
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if _norm_name(getattr(ability, "name", "")) == _norm_name(PRIMARCH_OF_THE_FIRST_LEGION_NAME):
            return True
    return False


def unit_has_primarch_of_the_first_legion_sub_ability(unit) -> bool:
    if unit is None:
        return False
    valid_keys = set(PRIMARCH_OF_THE_FIRST_LEGION_BY_KEY)
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        key = ability_name_to_key(getattr(ability, "name", ""))
        if key in valid_keys:
            return True
    return False


def get_active_primarch_of_the_first_legion_keys(
    unit,
    *,
    game=None,
    battle_round: Optional[int] = None,
) -> tuple[str, ...]:
    if unit is None or not unit_has_primarch_of_the_first_legion_ability(unit):
        return ()
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        return ()
    raw = special_rules.get(_ACTIVE_KEYS, ())
    if isinstance(raw, str):
        raw_keys = [raw]
    elif isinstance(raw, (tuple, list, set)):
        raw_keys = list(raw)
    else:
        raw_keys = []
    valid = sorted(
        {
            str(key or "").strip().upper()
            for key in raw_keys
            if str(key or "").strip().upper() in PRIMARCH_OF_THE_FIRST_LEGION_BY_KEY
        },
        key=lambda key: _PRIMARCH_ORDER_BY_KEY.get(key, 999),
    )
    if not valid:
        return ()
    stored_until = special_rules.get(_ACTIVE_UNTIL_ROUND)
    if battle_round is None:
        if game is None:
            game = _get_game_for_unit(unit)
        battle_round = int(getattr(game, "turn", 0) or 0) if game is not None else None
    if battle_round is not None and stored_until is not None:
        if int(battle_round or 0) > _coerce_int(stored_until, default=0):
            return ()
    return tuple(valid)


def unit_has_active_primarch_of_the_first_legion(
    unit,
    key: str,
    *,
    game=None,
    battle_round: Optional[int] = None,
) -> bool:
    choice_key = str(key or "").strip().upper()
    if not choice_key:
        return False
    return choice_key in set(
        get_active_primarch_of_the_first_legion_keys(
            unit,
            game=game,
            battle_round=battle_round,
        )
    )


def set_active_primarch_of_the_first_legion(
    unit,
    keys,
    *,
    start_round: int,
    expires_round: int,
    player_id: Optional[str] = None,
) -> None:
    if unit is None or not unit_has_primarch_of_the_first_legion_ability(unit):
        return
    key_tokens = sorted(
        {
            str(key or "").strip().upper()
            for key in list(keys or [])
            if str(key or "").strip().upper() in PRIMARCH_OF_THE_FIRST_LEGION_BY_KEY
        },
        key=lambda key: _PRIMARCH_ORDER_BY_KEY.get(key, 999),
    )
    if len(key_tokens) != 2:
        clear_active_primarch_of_the_first_legion(unit)
        return
    special_rules = _ensure_special_rules(unit)
    special_rules[_ACTIVE_KEYS] = list(key_tokens)
    special_rules[_ACTIVE_START_ROUND] = int(start_round or 0)
    special_rules[_ACTIVE_UNTIL_ROUND] = int(expires_round or 0)
    special_rules[_ACTIVE_UNTIL_PLAYER] = str(player_id or "")
    unit.special_rules = special_rules
    _invalidate_primarch_of_the_first_legion_caches(unit)


def clear_active_primarch_of_the_first_legion(unit) -> None:
    if unit is None:
        return
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        return
    special_rules.pop(_ACTIVE_KEYS, None)
    special_rules.pop(_ACTIVE_START_ROUND, None)
    special_rules.pop(_ACTIVE_UNTIL_ROUND, None)
    special_rules.pop(_ACTIVE_UNTIL_PLAYER, None)
    unit.special_rules = special_rules
    _invalidate_primarch_of_the_first_legion_caches(unit)


def primarch_of_the_first_legion_units(army) -> list:
    if army is None:
        return []
    return [
        unit
        for unit in list(getattr(army, "units", []) or [])
        if unit_has_primarch_of_the_first_legion_ability(unit)
    ]


def primarch_of_the_first_legion_selectable_units(army) -> list:
    if army is None:
        return []
    return [
        unit
        for unit in list(getattr(army, "units", []) or [])
        if unit_has_primarch_of_the_first_legion_ability(unit) and _unit_on_battlefield(unit)
    ]


def _choice_combinations() -> tuple[tuple[str, str], ...]:
    option_keys = [option.key for option in PRIMARCH_OF_THE_FIRST_LEGION_OPTIONS]
    return tuple(tuple(group) for group in combinations(option_keys, 2))


def unit_can_use_mist_wreathed_shadow_realms(unit, *, game=None) -> bool:
    if unit is None or not _unit_on_battlefield(unit):
        return False
    if not unit_has_active_primarch_of_the_first_legion(unit, KEY_MIST_WREATHED_SHADOW_REALMS, game=game):
        return False
    if game is None:
        game = _get_game_for_unit(unit)
    game_map = getattr(game, "map", None) if game is not None else None
    if game_map is None:
        return False
    get_enemy_units = getattr(game_map, "get_enemy_units", None)
    is_within_engagement_range = getattr(game_map, "is_within_engagement_range", None)
    if not callable(get_enemy_units) or not callable(is_within_engagement_range):
        return False
    for enemy in list(get_enemy_units(unit) or []):
        if enemy is None:
            continue
        if bool(is_within_engagement_range(unit, enemy)):
            return False
    return True


def queue_mist_wreathed_shadow_realms_prompt(game, unit):
    if game is None or unit is None:
        return None
    if not unit_can_use_mist_wreathed_shadow_realms(unit, game=game):
        return None
    get_parent_army = getattr(unit, "get_parent_army", None)
    army = get_parent_army() if callable(get_parent_army) else None
    player = getattr(army, "player", None)
    if player is None:
        return None
    queue_fn = getattr(game, "_queue_optional_ability_confirmation", None)
    if not callable(queue_fn):
        return None
    unit_id = str(get_entity_id(unit) or "")
    turn = int(getattr(game, "turn", 0) or 0)
    ability_name = MIST_WREATHED_SHADOW_REALMS_NAME
    message = (
        f"Use {ability_name} to remove {getattr(unit, 'name', 'Unit')} from the battlefield and place it into "
        "Strategic Reserves?"
    )
    return queue_fn(
        player=player,
        ability_key="mist_wreathed_shadow_realms",
        ability_name=ability_name,
        message=message,
        context={
            "ability_name": ability_name,
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "battle_round": turn,
            "phase": "COMMAND_PHASE",
        },
        payload={
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "battle_round": turn,
            "phase": "COMMAND_PHASE",
        },
        instance_key=f"{unit_id}:{turn}:mist_wreathed_shadow_realms",
    )


class PrimarchOfTheFirstLegionManager:
    """Lion El'Jonson: select two Primarch of the First Legion abilities in your Command phase."""

    def __init__(self, army=None):
        self.army = army

    def get_primarch_of_the_first_legion_units(self) -> list:
        return primarch_of_the_first_legion_selectable_units(self.army)

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

        units = primarch_of_the_first_legion_units(self.army)
        if not units:
            return

        battle_round = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        expires_round = int(battle_round or 0) + 1 if battle_round else 0
        player_id = str(getattr(army_player, "id", "") or "")

        for unit in units:
            clear_active_primarch_of_the_first_legion(unit)
            if game is None or not bool(getattr(game, "is_authoritative", True)):
                continue
            if unit not in primarch_of_the_first_legion_selectable_units(self.army):
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
                    if str(context.get("ability", "") or "") != "primarch_of_the_first_legion":
                        continue
                    if str(context.get("source_unit_id", "") or "") != unit_id:
                        continue
                    request_round = _coerce_int(context.get("battle_round", 0), default=0)
                    if request_round == battle_round:
                        has_current_pending = True
                        break
                    stale_ids.append(str(getattr(request, "decision_id", "") or ""))
                for decision_id in stale_ids:
                    if decision_id:
                        queue.pop(decision_id)
                if has_current_pending:
                    continue

            options = []
            for choice_keys in _choice_combinations():
                choice_names = [
                    PRIMARCH_OF_THE_FIRST_LEGION_BY_KEY[key].name
                    for key in choice_keys
                    if key in PRIMARCH_OF_THE_FIRST_LEGION_BY_KEY
                ]
                option_label = " + ".join(choice_names)
                options.append(
                    DecisionOption.create(
                        option_label,
                        payload={
                            "choice_keys": list(choice_keys),
                            "choice_names": list(choice_names),
                            "choice_count": len(choice_keys),
                        },
                    )
                )
            if not options:
                continue

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Primarch of the First Legion: select two abilities.",
                player_id=getattr(army_player, "id", None),
                options=options,
                context={
                    "ability": "primarch_of_the_first_legion",
                    "ability_name": PRIMARCH_OF_THE_FIRST_LEGION_NAME,
                    "source_unit_id": unit_id,
                    "unit_id": unit_id,
                    "battle_round": int(battle_round or 0),
                    "expires_round": int(expires_round or 0),
                    "player_id": player_id,
                    "allowed_choice_keys": [option.key for option in PRIMARCH_OF_THE_FIRST_LEGION_OPTIONS],
                    "max_choices": 2,
                    "optional": False,
                },
            )
            if hasattr(game, "request_decision"):
                game.request_decision(request)
