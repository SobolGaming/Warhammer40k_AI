from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decision_requests import build_patrol_squad_requests
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.LOCAL, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.rebuild_entity_registry()
    return game, sm_army, sm_player


def _choice_option_id(request, *, choice: bool) -> str:
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if payload.get("choice") is bool(choice):
            return str(getattr(option, "option_id", "") or "")
    raise AssertionError(f"Choice {choice} option not found")


def test_combat_squads_split_creates_two_five_model_tactical_units() -> None:
    game, sm_army, sm_player = _build_game()
    tactical = _actual_unit("Tactical Squad")
    sm_army.add_unit(tactical)
    game.rebuild_entity_registry()

    original_model_ids = {get_entity_id(model) for model in list(tactical.models or [])}

    requests = build_patrol_squad_requests(game, sm_army.units, queue_requests=True)
    assert len(requests) == 1
    request = requests[0]
    assert request.decision_type == DECISION_CONFIRM_YES_NO
    assert str((request.context or {}).get("ability", "") or "") == "combat_squads"
    assert str((request.context or {}).get("ability_name", "") or "") == "Combat Squads"

    result = resolve_decision_command(game, request, _choice_option_id(request, choice=True), player_id=sm_player.id)
    assert result.ok is True

    split_units = [unit for unit in list(sm_army.units or []) if str(getattr(unit, "name", "") or "") == "Tactical Squad"]
    assert len(split_units) == 2
    assert all(len(getattr(unit, "models", []) or []) == 5 for unit in split_units)
    assert tactical not in split_units

    split_model_ids = {
        get_entity_id(model)
        for split_unit in split_units
        for model in list(getattr(split_unit, "models", []) or [])
    }
    assert split_model_ids == original_model_ids
    assert all(bool((getattr(unit, "special_rules", {}) or {}).get("combat_squads_declared", False)) for unit in split_units)
    assert all(bool((getattr(unit, "special_rules", {}) or {}).get("combat_squads_split_applied", False)) for unit in split_units)


def test_combat_squads_keep_together_marks_unit_declared_and_does_not_split() -> None:
    game, sm_army, sm_player = _build_game()
    tactical = _actual_unit("Tactical Squad")
    sm_army.add_unit(tactical)
    game.rebuild_entity_registry()

    requests = build_patrol_squad_requests(game, sm_army.units, queue_requests=True)
    assert len(requests) == 1
    request = requests[0]
    assert str((request.context or {}).get("ability", "") or "") == "combat_squads"

    result = resolve_decision_command(game, request, _choice_option_id(request, choice=False), player_id=sm_player.id)
    assert result.ok is True

    tactical_units = [unit for unit in list(sm_army.units or []) if str(getattr(unit, "name", "") or "") == "Tactical Squad"]
    assert len(tactical_units) == 1
    assert tactical_units[0] is tactical
    assert len(getattr(tactical, "models", []) or []) == 10
    assert bool((getattr(tactical, "special_rules", {}) or {}).get("combat_squads_declared", False)) is True

    followup = build_patrol_squad_requests(game, sm_army.units, queue_requests=False)
    assert followup == []
