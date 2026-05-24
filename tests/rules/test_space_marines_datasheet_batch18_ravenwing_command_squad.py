from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagems import Stratagem, StratagemManager
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.CHARGE_PHASE
    return game, sm_army, enemy_army, sm_player, enemy_player


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.get_datasheet_id()]
    try:
        leader.attach_to_unit(bodyguard)
    except Exception:
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        for unit in (leader, bodyguard):
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()
    bodyguard._refresh_bearer_unit_common_modifiers()


def _remove_model_named(unit: Unit, model_name: str) -> None:
    target = None
    for model in list(getattr(unit, "models", []) or []):
        if str(getattr(model, "name", "") or "").strip().lower() == str(model_name or "").strip().lower():
            target = model
            break
    assert target is not None
    unit.remove_model(target)


def test_ravenwing_command_squad_honour_or_death_applies_to_attached_unit_while_champion_alive() -> None:
    game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
    outriders = _actual_unit("Outrider Squad", datasheet_id="000002712")
    command_squad = _actual_unit("Ravenwing Command Squad", datasheet_id="000002748")
    sm_army.add_unit(outriders)
    outriders._refresh_bearer_unit_common_modifiers()
    game.map.units = [outriders]
    game.rebuild_entity_registry()
    baseline_advance = outriders._apply_advance_roll_modifiers(4)
    baseline_charge = game._apply_charge_modifiers(outriders, 7)
    sm_army.add_unit(command_squad)
    _attach_leader(outriders, command_squad)
    game.map.units = [outriders, command_squad]
    game.rebuild_entity_registry()

    assert outriders._apply_advance_roll_modifiers(4) == baseline_advance + 1
    assert game._apply_charge_modifiers(outriders, 7) == baseline_charge + 1


def test_ravenwing_command_squad_honour_or_death_turns_off_when_champion_is_destroyed() -> None:
    game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
    outriders = _actual_unit("Outrider Squad", datasheet_id="000002712")
    command_squad = _actual_unit("Ravenwing Command Squad", datasheet_id="000002748")
    sm_army.add_unit(outriders)
    outriders._refresh_bearer_unit_common_modifiers()
    game.map.units = [outriders]
    game.rebuild_entity_registry()
    baseline_advance = outriders._apply_advance_roll_modifiers(4)
    baseline_charge = game._apply_charge_modifiers(outriders, 7)
    sm_army.add_unit(command_squad)
    _attach_leader(outriders, command_squad)

    _remove_model_named(command_squad, "Ravenwing Champion")
    outriders._refresh_bearer_unit_common_modifiers()
    game.map.units = [outriders, command_squad]
    game.rebuild_entity_registry()

    assert outriders._apply_advance_roll_modifiers(4) == baseline_advance
    assert game._apply_charge_modifiers(outriders, 7) == baseline_charge


def test_ravenwing_command_squad_honour_or_death_allows_zero_cp_heroic_intervention_on_attached_unit() -> None:
    game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
    outriders = _actual_unit("Outrider Squad", datasheet_id="000002712")
    command_squad = _actual_unit("Ravenwing Command Squad", datasheet_id="000002748")
    sm_army.add_unit(outriders)
    sm_army.add_unit(command_squad)
    _attach_leader(outriders, command_squad)

    preview = sm_player.preview_stratagem_cp_cost(
        SimpleNamespace(name="Heroic Intervention", cp_cost=1),
        target_unit=outriders,
        assume_optional_discounts=True,
    )
    assert int(preview.get("cost", 99)) == 0

    sm_player.set_next_optional_decision("UNIT_CONTAINS_HEROIC_INTERVENTION", True)
    applied = sm_player.apply_stratagem_cp_cost(
        SimpleNamespace(name="Heroic Intervention", cp_cost=1),
        target_unit=outriders,
    )

    assert int(applied.get("cost", 99)) == 0
    assert bool(applied.get("unit_contains_heroic_intervention_use", False)) is True
    assert "honour or death" in str(applied.get("unit_contains_heroic_intervention_source", "") or "").lower()


def test_ravenwing_command_squad_honour_or_death_queues_heroic_intervention_with_zero_cp() -> None:
    game, sm_army, enemy_army, sm_player, enemy_player = _build_game()
    outriders = _actual_unit("Outrider Squad", datasheet_id="000002712")
    command_squad = _actual_unit("Ravenwing Command Squad", datasheet_id="000002748")
    enemy = _actual_unit("Outrider Squad", datasheet_id="000002712")
    enemy_army.add_unit(enemy)
    sm_army.add_unit(outriders)
    sm_army.add_unit(command_squad)
    _attach_leader(outriders, command_squad)
    _deploy(outriders, 0.0, 0.0)
    _deploy(command_squad, 0.0, 0.0)
    _deploy(enemy, 5.0, 0.0)
    game.map.units = [outriders, command_squad, enemy]
    game.rebuild_entity_registry()

    sm_player.command_points = 0
    outriders.can_declare_charge_against = lambda target, current_game, out_of_turn=False: True

    manager = StratagemManager.__new__(StratagemManager)
    manager.player = sm_player
    manager.game = game
    manager.available = [
        Stratagem(
            id="core_heroic_intervention",
            name="HEROIC INTERVENTION",
            type="Stratagem",
            description="",
            cp_cost=1,
            turn="Opponent's turn",
            phase="Charge phase",
            detachment="",
            faction_id="",
        )
    ]
    manager._used_this_turn = {}
    manager._used_stratagems_this_phase = set()
    manager._current_phase_name = "Charge phase"
    manager._pending_reactions = []
    manager._heroic_intervention_units_this_phase = set()
    manager._queue_reaction = lambda payload: manager._pending_reactions.append(payload)
    sm_player.stratagems = manager
    game.current_player_index = 1
    assert game.get_current_player() is enemy_player

    manager._maybe_queue_heroic_intervention(enemy, action="charge")

    assert len(manager._pending_reactions) == 1
    reaction = manager._pending_reactions[0]
    assert str(reaction.get("stratagem", "") or "").upper() == "HEROIC INTERVENTION"
    assert reaction["dispatch_mode"] == "interrupt"
    assert reaction["interrupt_window"] == "after_enemy_charge_move"
    assert reaction["interrupt_source"] == "heroic_intervention"
    candidate_ids = {
        str(get_entity_id(unit) or "")
        for unit in list(reaction.get("candidates", []) or [])
    }
    assert str(get_entity_id(outriders) or "") in candidate_ids
