from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utility.dice import get_roll


@dataclass(frozen=True)
class ShadowFormOption:
    key: str
    name: str
    summary: str


SHADOW_FORM_NAME = "Shadow Form"
WREATHED_NAME = "Wreathed in Shadows (Aura, Psychic)"
PALL_NAME = "Pall of Despair (Aura, Psychic)"
SHADOW_LORD_NAME = "Shadow Lord (Aura, Psychic)"

KEY_WREATHED = "WREATHED_IN_SHADOWS"
KEY_PALL = "PALL_OF_DESPAIR"
KEY_SHADOW_LORD = "SHADOW_LORD"

WREATHED_IN_SHADOWS = ShadowFormOption(
    key=KEY_WREATHED,
    name=WREATHED_NAME,
    summary='Friendly LEGIONES DAEMONICA or SHADOW LEGION units within 6" can only be targeted by ranged attacks if the attacker is within 18".',
)
PALL_OF_DESPAIR = ShadowFormOption(
    key=KEY_PALL,
    name=PALL_NAME,
    summary='In the opponent Command phase, enemy units below Starting Strength within 9" must take Battle-shock; each failed test within 9" heals this model D3.',
)
SHADOW_LORD = ShadowFormOption(
    key=KEY_SHADOW_LORD,
    name=SHADOW_LORD_NAME,
    summary='Friendly LEGIONES DAEMONICA or SHADOW LEGION units within 6" re-roll Hit rolls of 1.',
)

SHADOW_FORM_OPTIONS: tuple[ShadowFormOption, ...] = (
    WREATHED_IN_SHADOWS,
    PALL_OF_DESPAIR,
    SHADOW_LORD,
)

_ACTIVE_KEY = "shadow_form_active_key"
_ACTIVE_ROUND = "shadow_form_round"


def _norm_name(text: str) -> str:
    return (text or "").replace("\u2019", "'").replace("\u00e2\u20ac\u2122", "'").strip().lower()


def _unit_has_shadow_form(unit) -> bool:
    if unit is None:
        return False
    try:
        for ab in (getattr(unit, "possible_abilities", []) or []):
            if _norm_name(getattr(ab, "name", "")) == _norm_name(SHADOW_FORM_NAME):
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


def get_active_shadow_form_key(unit, *, game=None, battle_round: Optional[int] = None) -> Optional[str]:
    if unit is None:
        return None
    if not _unit_has_shadow_form(unit):
        return None
    try:
        sr = getattr(unit, "special_rules", None)
    except Exception:
        sr = None
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


def unit_has_active_shadow_form(unit, key: str, *, game=None, battle_round: Optional[int] = None) -> bool:
    if unit is None:
        return False
    key = str(key or "").strip().upper()
    if not key:
        return False
    return get_active_shadow_form_key(unit, game=game, battle_round=battle_round) == key


def _ensure_special_rules(unit) -> dict:
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    return sr


def set_active_shadow_form(unit, key: str, *, battle_round: int) -> None:
    if unit is None:
        return
    if not _unit_has_shadow_form(unit):
        return
    sr = _ensure_special_rules(unit)
    sr[_ACTIVE_KEY] = str(key or "").strip().upper()
    sr[_ACTIVE_ROUND] = int(battle_round or 0)
    unit.special_rules = sr


def clear_active_shadow_form(unit) -> None:
    if unit is None:
        return
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        return
    sr.pop(_ACTIVE_KEY, None)
    sr.pop(_ACTIVE_ROUND, None)
    unit.special_rules = sr


def _unit_is_valid_shadow_form_source(unit) -> bool:
    if unit is None:
        return False
    if not _unit_has_shadow_form(unit):
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
    return True


def shadow_form_sources_with_active_key(army, key: str, *, game=None, battle_round: Optional[int] = None) -> list:
    if army is None:
        return []
    out = []
    for unit in list(getattr(army, "units", []) or []):
        if not _unit_is_valid_shadow_form_source(unit):
            continue
        if unit_has_active_shadow_form(unit, key, game=game, battle_round=battle_round):
            out.append(unit)
    return out


def target_unit_has_wreathed_in_shadows(target_unit, *, game_map=None) -> bool:
    if target_unit is None:
        return False
    try:
        if not (target_unit.has_any_keyword("LEGIONES DAEMONICA") or target_unit.has_any_keyword("SHADOW LEGION")):
            return False
    except Exception:
        return False
    if game_map is None:
        try:
            game = _get_game_for_unit(target_unit)
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
    if game_map is None:
        return False
    try:
        from ..utility.aura_utils import unit_within_range_of_unit
    except Exception:
        return False

    for source in list(game_map.get_friendly_units(target_unit) or []):
        if not _unit_is_valid_shadow_form_source(source):
            continue
        if not unit_has_active_shadow_form(source, KEY_WREATHED, game=None):
            continue
        try:
            if unit_within_range_of_unit(source, target_unit, 6.0, use_attached_aggregate=True):
                return True
        except Exception:
            continue
    return False


def apply_pall_of_despair_heal(unit) -> int:
    if unit is None:
        return 0
    amount = get_roll("D3")
    if amount <= 0:
        return 0

    damaged_model = None
    try:
        is_max, model = unit.is_max_health()
        if not is_max:
            damaged_model = model
    except Exception:
        damaged_model = None
    if damaged_model is None:
        for model in list(getattr(unit, "models", []) or []):
            try:
                base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
                current = int(getattr(model, "wounds", 0) or 0)
            except Exception:
                continue
            if base_wounds and current < base_wounds:
                damaged_model = model
                break

    if damaged_model is None:
        return 0
    try:
        damaged_model.heal(amount)
    except Exception:
        try:
            base_wounds = int(getattr(damaged_model, "_base_wounds", getattr(damaged_model, "base_wounds", 0)) or 0)
            damaged_model.wounds = min(base_wounds, int(getattr(damaged_model, "wounds", 0) or 0) + amount)
        except Exception:
            return 0
    return int(amount)


class ShadowFormManager:
    """Belakor: Shadow Form selection each battle round."""

    def __init__(self, army=None):
        self.army = army

    def get_shadow_form_units(self) -> list:
        units = []
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            if _unit_has_shadow_form(unit):
                units.append(unit)
        return units

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if self.army is None:
            return
        if game is None:
            try:
                game = getattr(getattr(self.army, "player", None), "game", None)
            except Exception:
                game = None
        units = self.get_shadow_form_units()
        if not units:
            return

        player = getattr(self.army, "player", None)

        for unit in units:
            clear_active_shadow_form(unit)
            if game is not None:
                if not bool(getattr(game, "is_authoritative", True)):
                    continue
                try:
                    from ..engine.decision_kinds import DECISION_CHOOSE_SHADOW_FORM
                    from ..engine.decisions import DecisionOption, DecisionRequest
                    from ..utility.entity_ids import get_entity_id
                except Exception:
                    continue
                unit_id = get_entity_id(unit)
                queue = getattr(game, "decision_queue", None)
                if queue is not None and hasattr(queue, "list"):
                    for req in list(queue.list() or []):
                        if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_SHADOW_FORM:
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
                            for opt in SHADOW_FORM_OPTIONS
                        ]
                        if not req_options:
                            continue
                        req = DecisionRequest.create(
                            DECISION_CHOOSE_SHADOW_FORM,
                            "Select Shadow Form.",
                            player_id=getattr(player, "id", None),
                            options=req_options,
                            context={"unit_id": unit_id, "battle_round": int(battle_round or 0)},
                        )
                        if hasattr(game, "request_decision"):
                            game.request_decision(req)
                continue
            continue
