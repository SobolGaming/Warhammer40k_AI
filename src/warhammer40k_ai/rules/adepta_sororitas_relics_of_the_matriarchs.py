from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Optional

from ..utility.entity_ids import get_entity_id


@dataclass(frozen=True)
class MatriarchRelicOption:
    key: str
    name: str
    summary: str


RELICS_OF_THE_MATRIARCHS_NAME = "Relics of the Matriarchs"
THE_FIERY_HEART_NAME = "The Fiery Heart (Aura)"
CENSER_OF_THE_SACRED_ROSE_NAME = "Censer of the Sacred Rose (Aura)"
SIMULACRUM_OF_THE_EBON_CHALICE_NAME = "Simulacrum of the Ebon Chalice (Aura)"
SIMULACRUM_OF_THE_ARGENT_SHROUD_NAME = "Simulacrum of the Argent Shroud (Aura)"
ICON_OF_THE_VALOROUS_HEART_NAME = "Icon of the Valorous Heart (Aura)"
PETALS_OF_THE_BLOODY_ROSE_NAME = "Petals of the Bloody Rose (Aura)"

KEY_THE_FIERY_HEART = "THE_FIERY_HEART"
KEY_CENSER_OF_THE_SACRED_ROSE = "CENSER_OF_THE_SACRED_ROSE"
KEY_SIMULACRUM_OF_THE_EBON_CHALICE = "SIMULACRUM_OF_THE_EBON_CHALICE"
KEY_SIMULACRUM_OF_THE_ARGENT_SHROUD = "SIMULACRUM_OF_THE_ARGENT_SHROUD"
KEY_ICON_OF_THE_VALOROUS_HEART = "ICON_OF_THE_VALOROUS_HEART"
KEY_PETALS_OF_THE_BLOODY_ROSE = "PETALS_OF_THE_BLOODY_ROSE"

THE_FIERY_HEART = MatriarchRelicOption(
    key=KEY_THE_FIERY_HEART,
    name=THE_FIERY_HEART_NAME,
    summary='Friendly ADEPTA SORORITAS units within 6" gain +2" Move and +1 to Advance/Charge rolls.',
)
CENSER_OF_THE_SACRED_ROSE = MatriarchRelicOption(
    key=KEY_CENSER_OF_THE_SACRED_ROSE,
    name=CENSER_OF_THE_SACRED_ROSE_NAME,
    summary='Friendly ADEPTA SORORITAS units within 6" can re-roll Battle-shock tests.',
)
SIMULACRUM_OF_THE_EBON_CHALICE = MatriarchRelicOption(
    key=KEY_SIMULACRUM_OF_THE_EBON_CHALICE,
    name=SIMULACRUM_OF_THE_EBON_CHALICE_NAME,
    summary='Friendly ADEPTA SORORITAS units within 6" can perform up to two Acts of Faith per phase.',
)
SIMULACRUM_OF_THE_ARGENT_SHROUD = MatriarchRelicOption(
    key=KEY_SIMULACRUM_OF_THE_ARGENT_SHROUD,
    name=SIMULACRUM_OF_THE_ARGENT_SHROUD_NAME,
    summary='Friendly ADEPTA SORORITAS units within 6" re-roll Wound rolls of 1 for ranged attacks.',
)
ICON_OF_THE_VALOROUS_HEART = MatriarchRelicOption(
    key=KEY_ICON_OF_THE_VALOROUS_HEART,
    name=ICON_OF_THE_VALOROUS_HEART_NAME,
    summary='Friendly ADEPTA SORORITAS units within 6" gain Feel No Pain 6+.',
)
PETALS_OF_THE_BLOODY_ROSE = MatriarchRelicOption(
    key=KEY_PETALS_OF_THE_BLOODY_ROSE,
    name=PETALS_OF_THE_BLOODY_ROSE_NAME,
    summary='Friendly ADEPTA SORORITAS units within 6" improve melee AP by 1.',
)

RELICS_OF_THE_MATRIARCHS_OPTIONS: tuple[MatriarchRelicOption, ...] = (
    THE_FIERY_HEART,
    CENSER_OF_THE_SACRED_ROSE,
    SIMULACRUM_OF_THE_EBON_CHALICE,
    SIMULACRUM_OF_THE_ARGENT_SHROUD,
    ICON_OF_THE_VALOROUS_HEART,
    PETALS_OF_THE_BLOODY_ROSE,
)
RELICS_OF_THE_MATRIARCHS_BY_KEY = {
    option.key: option for option in RELICS_OF_THE_MATRIARCHS_OPTIONS
}
_RELIC_ORDER_BY_KEY = {
    option.key: idx for idx, option in enumerate(RELICS_OF_THE_MATRIARCHS_OPTIONS)
}

_ACTIVE_KEYS = "relics_of_the_matriarchs_active_keys"
_ACTIVE_START_ROUND = "relics_of_the_matriarchs_active_start_round"
_ACTIVE_UNTIL_ROUND = "relics_of_the_matriarchs_active_until_round"
_ACTIVE_UNTIL_PLAYER = "relics_of_the_matriarchs_active_until_player_id"


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


def _invalidate_relics_of_the_matriarchs_caches(unit) -> None:
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
    if norm == _norm_name(THE_FIERY_HEART_NAME):
        return KEY_THE_FIERY_HEART
    if norm == _norm_name(CENSER_OF_THE_SACRED_ROSE_NAME):
        return KEY_CENSER_OF_THE_SACRED_ROSE
    if norm == _norm_name(SIMULACRUM_OF_THE_EBON_CHALICE_NAME):
        return KEY_SIMULACRUM_OF_THE_EBON_CHALICE
    if norm == _norm_name(SIMULACRUM_OF_THE_ARGENT_SHROUD_NAME):
        return KEY_SIMULACRUM_OF_THE_ARGENT_SHROUD
    if norm == _norm_name(ICON_OF_THE_VALOROUS_HEART_NAME):
        return KEY_ICON_OF_THE_VALOROUS_HEART
    if norm == _norm_name(PETALS_OF_THE_BLOODY_ROSE_NAME):
        return KEY_PETALS_OF_THE_BLOODY_ROSE
    return None


def unit_has_relics_of_the_matriarchs_ability(unit) -> bool:
    if unit is None:
        return False
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if _norm_name(getattr(ability, "name", "")) == _norm_name(RELICS_OF_THE_MATRIARCHS_NAME):
            return True
    return False


def unit_has_matriarch_relic_sub_ability(unit) -> bool:
    if unit is None:
        return False
    valid_keys = set(RELICS_OF_THE_MATRIARCHS_BY_KEY)
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        key = ability_name_to_key(getattr(ability, "name", ""))
        if key in valid_keys:
            return True
    return False


def relics_of_the_matriarchs_max_choices(unit) -> int:
    max_choices = 2
    special_rules = getattr(unit, "special_rules", None)
    if isinstance(special_rules, dict):
        max_choices = _coerce_int(
            special_rules.get("relics_of_matriarchs_max_choices", 2),
            default=2,
        )
    max_choices = max(0, int(max_choices))
    return min(int(max_choices), len(RELICS_OF_THE_MATRIARCHS_OPTIONS))


def get_active_relics_of_the_matriarchs_keys(
    unit,
    *,
    game=None,
    battle_round: Optional[int] = None,
) -> tuple[str, ...]:
    if unit is None or not unit_has_relics_of_the_matriarchs_ability(unit):
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
            if str(key or "").strip().upper() in RELICS_OF_THE_MATRIARCHS_BY_KEY
        },
        key=lambda key: _RELIC_ORDER_BY_KEY.get(key, 999),
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


def unit_has_active_relics_of_the_matriarchs(
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
        get_active_relics_of_the_matriarchs_keys(
            unit,
            game=game,
            battle_round=battle_round,
        )
    )


def set_active_relics_of_the_matriarchs(
    unit,
    keys,
    *,
    start_round: int,
    expires_round: int,
    player_id: Optional[str] = None,
) -> None:
    if unit is None or not unit_has_relics_of_the_matriarchs_ability(unit):
        return
    key_tokens = sorted(
        {
            str(key or "").strip().upper()
            for key in list(keys or [])
            if str(key or "").strip().upper() in RELICS_OF_THE_MATRIARCHS_BY_KEY
        },
        key=lambda key: _RELIC_ORDER_BY_KEY.get(key, 999),
    )
    max_choices = relics_of_the_matriarchs_max_choices(unit)
    if max_choices >= 0:
        key_tokens = list(key_tokens)[: int(max_choices)]
    if not key_tokens:
        clear_active_relics_of_the_matriarchs(unit)
        return
    special_rules = _ensure_special_rules(unit)
    special_rules[_ACTIVE_KEYS] = list(key_tokens)
    special_rules[_ACTIVE_START_ROUND] = int(start_round or 0)
    special_rules[_ACTIVE_UNTIL_ROUND] = int(expires_round or 0)
    special_rules[_ACTIVE_UNTIL_PLAYER] = str(player_id or "")
    unit.special_rules = special_rules
    _invalidate_relics_of_the_matriarchs_caches(unit)


def clear_active_relics_of_the_matriarchs(unit) -> None:
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
    _invalidate_relics_of_the_matriarchs_caches(unit)


def _unit_is_valid_relics_of_the_matriarchs_source(unit) -> bool:
    return bool(unit_has_relics_of_the_matriarchs_ability(unit) and _unit_on_battlefield(unit))


def relics_of_the_matriarchs_units(army) -> list:
    if army is None:
        return []
    return [
        unit
        for unit in list(getattr(army, "units", []) or [])
        if unit_has_relics_of_the_matriarchs_ability(unit)
    ]


def relics_of_the_matriarchs_selectable_units(army) -> list:
    if army is None:
        return []
    return [
        unit
        for unit in list(getattr(army, "units", []) or [])
        if _unit_is_valid_relics_of_the_matriarchs_source(unit)
    ]


def _choice_combinations(max_choices: int) -> tuple[tuple[str, ...], ...]:
    option_keys = [option.key for option in RELICS_OF_THE_MATRIARCHS_OPTIONS]
    combos: list[tuple[str, ...]] = [tuple()]
    for count in range(1, max(0, int(max_choices)) + 1):
        combos.extend(tuple(group) for group in combinations(option_keys, count))
    return tuple(combos)


class RelicsOfTheMatriarchsManager:
    """Triumph of Saint Katherine: select up to two relic auras each battle round."""

    def __init__(self, army=None):
        self.army = army

    def get_relics_of_the_matriarchs_units(self) -> list:
        return relics_of_the_matriarchs_selectable_units(self.army)

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if self.army is None:
            return
        army_player = getattr(self.army, "player", None)
        if game is None:
            game = getattr(army_player, "game", None) if army_player is not None else None

        units = relics_of_the_matriarchs_units(self.army)
        if not units:
            return
        battle_round = int(battle_round or 0)
        expires_round = int(battle_round) + 1 if battle_round else 0
        player_id = str(getattr(army_player, "id", "") or "")

        for unit in units:
            clear_active_relics_of_the_matriarchs(unit)
            if game is None or not bool(getattr(game, "is_authoritative", True)):
                continue
            if not _unit_is_valid_relics_of_the_matriarchs_source(unit):
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
                    if str(context.get("ability", "") or "") != "relics_of_the_matriarchs":
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

            max_choices = relics_of_the_matriarchs_max_choices(unit)
            options: list = []
            for choice_keys in _choice_combinations(max_choices):
                if choice_keys:
                    choice_names = [
                        RELICS_OF_THE_MATRIARCHS_BY_KEY[key].name
                        for key in choice_keys
                        if key in RELICS_OF_THE_MATRIARCHS_BY_KEY
                    ]
                    option_label = " + ".join(choice_names) if choice_names else str(choice_keys[0])
                    payload = {
                        "choice_keys": list(choice_keys),
                        "choice_names": list(choice_names),
                        "choice_count": len(choice_keys),
                    }
                else:
                    option_label = "None"
                    payload = {
                        "action": "skip",
                        "skip": True,
                        "choice_keys": [],
                        "choice_names": [],
                        "choice_count": 0,
                    }
                options.append(DecisionOption.create(option_label, payload=payload))
            if not options:
                continue

            choice_word = "ability" if int(max_choices) == 1 else "abilities"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"Relics of the Matriarchs: select up to {int(max_choices)} relic {choice_word}.",
                player_id=getattr(army_player, "id", None),
                options=options,
                context={
                    "ability": "relics_of_the_matriarchs",
                    "ability_name": RELICS_OF_THE_MATRIARCHS_NAME,
                    "source_unit_id": unit_id,
                    "unit_id": unit_id,
                    "battle_round": int(battle_round or 0),
                    "expires_round": int(expires_round or 0),
                    "player_id": player_id,
                    "allowed_choice_keys": [option.key for option in RELICS_OF_THE_MATRIARCHS_OPTIONS],
                    "max_choices": int(max_choices),
                    "optional": True,
                },
            )
            if hasattr(game, "request_decision"):
                game.request_decision(request)
