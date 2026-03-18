from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Optional

from ..utility.entity_ids import get_entity_id


@dataclass(frozen=True)
class AuthorOfTheCodexOption:
    key: str
    name: str
    summary: str


AUTHOR_OF_THE_CODEX_NAME = "Author of the Codex"
PRIMARCH_OF_THE_XIII_NAME = "Primarch of the XIII (Aura)"
MASTER_OF_BATTLE_NAME = "Master of Battle"
SUPREME_STRATEGIST_NAME = "Supreme Strategist"

KEY_PRIMARCH_OF_THE_XIII = "PRIMARCH_OF_THE_XIII"
KEY_MASTER_OF_BATTLE = "MASTER_OF_BATTLE"
KEY_SUPREME_STRATEGIST = "SUPREME_STRATEGIST"

PRIMARCH_OF_THE_XIII = AuthorOfTheCodexOption(
    key=KEY_PRIMARCH_OF_THE_XIII,
    name=PRIMARCH_OF_THE_XIII_NAME,
    summary=(
        'Friendly ADEPTUS ASTARTES units within 6" gain +1 Objective Control and can re-roll '
        "Battle-shock and Leadership tests."
    ),
)
MASTER_OF_BATTLE = AuthorOfTheCodexOption(
    key=KEY_MASTER_OF_BATTLE,
    name=MASTER_OF_BATTLE_NAME,
    summary=(
        "After selecting your Oath of Moment target, select a second enemy unit; if the Oath target is "
        "destroyed, that second unit becomes your Oath target until a new one is selected."
    ),
)
SUPREME_STRATEGIST = AuthorOfTheCodexOption(
    key=KEY_SUPREME_STRATEGIST,
    name=SUPREME_STRATEGIST_NAME,
    summary=(
        'Once per battle round, one ADEPTUS ASTARTES unit within 12" can reduce the CP cost of a Stratagem '
        "that targets it by 1."
    ),
)

AUTHOR_OF_THE_CODEX_OPTIONS: tuple[AuthorOfTheCodexOption, ...] = (
    PRIMARCH_OF_THE_XIII,
    MASTER_OF_BATTLE,
    SUPREME_STRATEGIST,
)
AUTHOR_OF_THE_CODEX_BY_KEY = {
    option.key: option for option in AUTHOR_OF_THE_CODEX_OPTIONS
}
_AUTHOR_OF_THE_CODEX_ORDER_BY_KEY = {
    option.key: idx for idx, option in enumerate(AUTHOR_OF_THE_CODEX_OPTIONS)
}

_ACTIVE_KEYS = "author_of_the_codex_active_keys"
_ACTIVE_START_ROUND = "author_of_the_codex_active_start_round"
_ACTIVE_UNTIL_ROUND = "author_of_the_codex_active_until_round"
_ACTIVE_UNTIL_PLAYER = "author_of_the_codex_active_until_player_id"


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


def _invalidate_author_of_the_codex_caches(unit) -> None:
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
    refresh_targeted_discount = getattr(root, "_refresh_targeted_stratagem_cp_discount_flags", None)
    if callable(refresh_targeted_discount):
        refresh_targeted_discount()


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
    if norm == _norm_name(PRIMARCH_OF_THE_XIII_NAME):
        return KEY_PRIMARCH_OF_THE_XIII
    if norm == _norm_name(MASTER_OF_BATTLE_NAME):
        return KEY_MASTER_OF_BATTLE
    if norm == _norm_name(SUPREME_STRATEGIST_NAME):
        return KEY_SUPREME_STRATEGIST
    return None


def unit_has_author_of_the_codex_ability(unit) -> bool:
    if unit is None:
        return False
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if _norm_name(getattr(ability, "name", "")) == _norm_name(AUTHOR_OF_THE_CODEX_NAME):
            return True
    return False


def unit_has_author_of_the_codex_sub_ability(unit) -> bool:
    if unit is None:
        return False
    valid_keys = set(AUTHOR_OF_THE_CODEX_BY_KEY)
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        key = ability_name_to_key(getattr(ability, "name", ""))
        if key in valid_keys:
            return True
    return False


def get_active_author_of_the_codex_keys(
    unit,
    *,
    game=None,
    battle_round: Optional[int] = None,
) -> tuple[str, ...]:
    if unit is None or not unit_has_author_of_the_codex_ability(unit):
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
            if str(key or "").strip().upper() in AUTHOR_OF_THE_CODEX_BY_KEY
        },
        key=lambda key: _AUTHOR_OF_THE_CODEX_ORDER_BY_KEY.get(key, 999),
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


def unit_has_active_author_of_the_codex(
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
        get_active_author_of_the_codex_keys(
            unit,
            game=game,
            battle_round=battle_round,
        )
    )


def set_active_author_of_the_codex(
    unit,
    keys,
    *,
    start_round: int,
    expires_round: int,
    player_id: Optional[str] = None,
) -> None:
    if unit is None or not unit_has_author_of_the_codex_ability(unit):
        return
    key_tokens = sorted(
        {
            str(key or "").strip().upper()
            for key in list(keys or [])
            if str(key or "").strip().upper() in AUTHOR_OF_THE_CODEX_BY_KEY
        },
        key=lambda key: _AUTHOR_OF_THE_CODEX_ORDER_BY_KEY.get(key, 999),
    )
    if len(key_tokens) != 2:
        clear_active_author_of_the_codex(unit)
        return
    special_rules = _ensure_special_rules(unit)
    special_rules[_ACTIVE_KEYS] = list(key_tokens)
    special_rules[_ACTIVE_START_ROUND] = int(start_round or 0)
    special_rules[_ACTIVE_UNTIL_ROUND] = int(expires_round or 0)
    special_rules[_ACTIVE_UNTIL_PLAYER] = str(player_id or "")
    unit.special_rules = special_rules
    _invalidate_author_of_the_codex_caches(unit)


def clear_active_author_of_the_codex(unit) -> None:
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
    _invalidate_author_of_the_codex_caches(unit)


def author_of_the_codex_units(army) -> list:
    if army is None:
        return []
    return [
        unit
        for unit in list(getattr(army, "units", []) or [])
        if unit_has_author_of_the_codex_ability(unit)
    ]


def author_of_the_codex_selectable_units(army) -> list:
    if army is None:
        return []
    return [
        unit
        for unit in list(getattr(army, "units", []) or [])
        if unit_has_author_of_the_codex_ability(unit) and _unit_on_battlefield(unit)
    ]


def author_of_the_codex_active_units_for_key(army, key: str, *, game=None) -> list:
    choice_key = str(key or "").strip().upper()
    if not choice_key:
        return []
    units = []
    for unit in list(author_of_the_codex_selectable_units(army) or []):
        if unit_has_active_author_of_the_codex(unit, choice_key, game=game):
            units.append(unit)
    units.sort(key=lambda unit: str(get_entity_id(unit) or ""))
    return units


def _choice_combinations() -> tuple[tuple[str, str], ...]:
    option_keys = [option.key for option in AUTHOR_OF_THE_CODEX_OPTIONS]
    return tuple(tuple(group) for group in combinations(option_keys, 2))


class AuthorOfTheCodexManager:
    """Roboute Guilliman: select two Author of the Codex abilities in your Command phase."""

    def __init__(self, army=None):
        self.army = army

    def get_author_of_the_codex_units(self) -> list:
        return author_of_the_codex_selectable_units(self.army)

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

        units = author_of_the_codex_units(self.army)
        if not units:
            return

        battle_round = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        expires_round = int(battle_round or 0) + 1 if battle_round else 0
        player_id = str(getattr(army_player, "id", "") or "")

        for unit in units:
            clear_active_author_of_the_codex(unit)
            if game is None or not bool(getattr(game, "is_authoritative", True)):
                continue
            if unit not in author_of_the_codex_selectable_units(self.army):
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
                    if str(context.get("ability", "") or "") != "author_of_the_codex":
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
                    AUTHOR_OF_THE_CODEX_BY_KEY[key].name
                    for key in choice_keys
                    if key in AUTHOR_OF_THE_CODEX_BY_KEY
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
                "Author of the Codex: select two abilities.",
                player_id=getattr(army_player, "id", None),
                options=options,
                context={
                    "ability": "author_of_the_codex",
                    "ability_name": AUTHOR_OF_THE_CODEX_NAME,
                    "source_unit_id": unit_id,
                    "unit_id": unit_id,
                    "battle_round": int(battle_round or 0),
                    "expires_round": int(expires_round or 0),
                    "player_id": player_id,
                    "allowed_choice_keys": [option.key for option in AUTHOR_OF_THE_CODEX_OPTIONS],
                    "max_choices": 2,
                    "optional": False,
                },
            )
            if hasattr(game, "request_decision"):
                game.request_decision(request)
