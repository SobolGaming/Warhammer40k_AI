from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utility.aura_utils import unit_within_range_of_unit
from ..utility.entity_ids import get_entity_id
from ..utility.keyword_utils import unit_has_keyword


@dataclass(frozen=True)
class CrimsonKingOption:
    key: str
    name: str
    summary: str


UNEARTHLY_POWER_NAME = "Unearthly Power"
IMPOSSIBLE_FORM_NAME = "Impossible Form (Psychic)"
TREASON_OF_TZEENTCH_NAME = "Treason of Tzeentch (Psychic)"
TIME_FLUX_NAME = "Time Flux (Aura, Psychic)"

KEY_IMPOSSIBLE_FORM = "IMPOSSIBLE_FORM"
KEY_TREASON_OF_TZEENTCH = "TREASON_OF_TZEENTCH"
KEY_TIME_FLUX = "TIME_FLUX"

IMPOSSIBLE_FORM = CrimsonKingOption(
    key=KEY_IMPOSSIBLE_FORM,
    name=IMPOSSIBLE_FORM_NAME,
    summary="Each time an attack is allocated to this model, subtract 1 from that attack's Damage characteristic.",
)
TREASON_OF_TZEENTCH = CrimsonKingOption(
    key=KEY_TREASON_OF_TZEENTCH,
    name=TREASON_OF_TZEENTCH_NAME,
    summary='Start of opponent Shooting phase: select an enemy unit within 24"; its ranged weapons gain [HAZARDOUS].',
)
TIME_FLUX = CrimsonKingOption(
    key=KEY_TIME_FLUX,
    name=TIME_FLUX_NAME,
    summary='Friendly THOUSAND SONS units within 6" gain +2" Move.',
)

CRIMSON_KING_OPTIONS: tuple[CrimsonKingOption, ...] = (
    IMPOSSIBLE_FORM,
    TREASON_OF_TZEENTCH,
    TIME_FLUX,
)
CRIMSON_KING_BY_KEY = {opt.key: opt for opt in CRIMSON_KING_OPTIONS}

_ACTIVE_KEY = "crimson_king_active_key"
_ACTIVE_START_ROUND = "crimson_king_active_start_round"
_ACTIVE_UNTIL_ROUND = "crimson_king_active_until_round"
_ACTIVE_UNTIL_PLAYER = "crimson_king_active_until_player_id"


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


def _invalidate_crimson_king_caches(unit) -> None:
    try:
        root = unit.get_attached_unit_root()
    except Exception:
        root = unit
    cache = getattr(root, "_ability_cache", None)
    if isinstance(cache, dict):
        cache.clear()
        root._ability_cache = cache
    try:
        parse_fn = getattr(root, "_parse_against_attack_characteristic_defensive_rules", None)
        if callable(parse_fn):
            parse_fn()
    except Exception:
        pass


def ability_name_to_key(name: str) -> Optional[str]:
    norm = _norm_name(name)
    if norm == _norm_name(IMPOSSIBLE_FORM_NAME):
        return KEY_IMPOSSIBLE_FORM
    if norm == _norm_name(TREASON_OF_TZEENTCH_NAME):
        return KEY_TREASON_OF_TZEENTCH
    if norm == _norm_name(TIME_FLUX_NAME):
        return KEY_TIME_FLUX
    return None


def unit_has_crimson_king_ability(unit) -> bool:
    if unit is None:
        return False
    try:
        for ab in list(getattr(unit, "possible_abilities", []) or []):
            if _norm_name(getattr(ab, "name", "")) == _norm_name(UNEARTHLY_POWER_NAME):
                return True
    except Exception:
        return False
    return False


def unit_has_crimson_king_sub_ability(unit) -> bool:
    if unit is None:
        return False
    keys = {opt.key for opt in CRIMSON_KING_OPTIONS}
    try:
        for ab in list(getattr(unit, "possible_abilities", []) or []):
            key = ability_name_to_key(getattr(ab, "name", ""))
            if key in keys:
                return True
    except Exception:
        return False
    return False


def get_active_crimson_king_key(unit, *, game=None, battle_round: Optional[int] = None) -> Optional[str]:
    if unit is None or not unit_has_crimson_king_ability(unit):
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


def unit_has_active_crimson_king(unit, key: str, *, game=None, battle_round: Optional[int] = None) -> bool:
    choice_key = str(key or "").strip().upper()
    if not choice_key:
        return False
    return get_active_crimson_king_key(unit, game=game, battle_round=battle_round) == choice_key


def set_active_crimson_king(
    unit,
    key: str,
    *,
    start_round: int,
    expires_round: int,
    player_id: Optional[str] = None,
) -> None:
    if unit is None or not unit_has_crimson_king_ability(unit):
        return
    sr = _ensure_special_rules(unit)
    sr[_ACTIVE_KEY] = str(key or "").strip().upper()
    sr[_ACTIVE_START_ROUND] = int(start_round or 0)
    sr[_ACTIVE_UNTIL_ROUND] = int(expires_round or 0)
    sr[_ACTIVE_UNTIL_PLAYER] = str(player_id or "")
    unit.special_rules = sr
    _invalidate_crimson_king_caches(unit)


def clear_active_crimson_king(unit) -> None:
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
    _invalidate_crimson_king_caches(unit)


def _unit_is_valid_crimson_king_source(unit) -> bool:
    if unit is None or not unit_has_crimson_king_ability(unit):
        return False
    try:
        if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
            return False
    except Exception:
        return False
    return True


def crimson_king_units(army) -> list:
    if army is None:
        return []
    return [u for u in list(getattr(army, "units", []) or []) if unit_has_crimson_king_ability(u)]


def crimson_king_selectable_units(army) -> list:
    if army is None:
        return []
    return [u for u in list(getattr(army, "units", []) or []) if _unit_is_valid_crimson_king_source(u)]


def time_flux_move_bonus_for_unit(unit, *, game_map=None, battle_round: Optional[int] = None) -> int:
    if unit is None:
        return 0
    if not unit_has_keyword(unit, "THOUSAND SONS"):
        return 0
    try:
        root = unit.get_attached_unit_root()
    except Exception:
        root = unit
    if game_map is None:
        try:
            game = _get_game_for_unit(root)
            game_map = getattr(game, "map", None) if game is not None else None
        except Exception:
            game_map = None
    if game_map is None:
        return 0

    seen: set[str] = set()
    for candidate in list(getattr(game_map, "get_friendly_units", lambda _u: [])(root) or []):
        if candidate is None:
            continue
        try:
            source = candidate.get_attached_unit_root()
        except Exception:
            source = candidate
        sid = str(get_entity_id(source) or "")
        if not sid or sid in seen:
            continue
        seen.add(sid)
        if not _unit_is_valid_crimson_king_source(source):
            continue
        if not unit_has_active_crimson_king(source, KEY_TIME_FLUX, battle_round=battle_round):
            continue
        try:
            if unit_within_range_of_unit(source, root, 6.0, use_attached_aggregate=True):
                return 2
        except Exception:
            continue
    return 0


class CrimsonKingManager:
    """Magnus: at the start of each battle round, select one Crimson King sub-ability."""

    def __init__(self, army=None):
        self.army = army

    def get_crimson_king_units(self) -> list:
        return crimson_king_selectable_units(self.army)

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if self.army is None:
            return
        army_player = getattr(self.army, "player", None)
        if game is None:
            game = getattr(army_player, "game", None) if army_player is not None else None

        units = crimson_king_units(self.army)
        if not units:
            return
        try:
            br = int(battle_round or 0)
        except Exception:
            br = 0
        expires_round = int(br) + 1 if br else 0
        player_id = str(getattr(army_player, "id", "") or "")

        for unit in units:
            clear_active_crimson_king(unit)
            if game is None or not bool(getattr(game, "is_authoritative", True)):
                continue
            if not _unit_is_valid_crimson_king_source(unit):
                continue
            try:
                from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
                from ..engine.decisions import DecisionOption, DecisionRequest
            except Exception:
                continue
            unit_id = str(get_entity_id(unit) or "")
            if not unit_id:
                continue
            queue = getattr(game, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                pending = False
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if str(ctx.get("ability", "") or "") != "unearthly_power":
                        continue
                    if str(ctx.get("source_unit_id", "") or "") == unit_id:
                        pending = True
                        break
                if pending:
                    continue
            options = [
                DecisionOption.create(
                    option.name,
                    payload={"choice_key": option.key, "choice_name": option.name, "summary": option.summary},
                )
                for option in CRIMSON_KING_OPTIONS
            ]
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Unearthly Power: select a Crimson King ability.",
                player_id=getattr(army_player, "id", None),
                options=options,
                context={
                    "ability": "unearthly_power",
                    "ability_name": UNEARTHLY_POWER_NAME,
                    "source_unit_id": unit_id,
                    "unit_id": unit_id,
                    "battle_round": int(br or 0),
                    "expires_round": int(expires_round or 0),
                    "player_id": player_id,
                },
            )
            if hasattr(game, "request_decision"):
                game.request_decision(request)
