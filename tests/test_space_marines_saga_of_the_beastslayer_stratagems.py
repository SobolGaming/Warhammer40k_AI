from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "6",
                "Sv": "3",
                "W": "4",
                "Ld": "6",
                "OC": "2",
                "base_size": "60mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", "Saga of the Beastslayer")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("SM", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)

    sm_player.command_points = 10
    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def test_shock_cavalry_movement_phase_applies_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    cavalry = _make_unit(
        "Thunderwolf Cavalry",
        keywords=["MOUNTED", "THUNDERWOLF CAVALRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(cavalry)
    _deploy_unit(game, cavalry, 10.0, 10.0)

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    ok = sm_player.stratagems.use("SHOCK CAVALRY", unit=cavalry, phase_name="Movement phase")
    assert ok
    assert int(sm_player.command_points or 0) == 9

    sr = dict(getattr(cavalry, "special_rules", {}) or {})
    assert bool(sr.get("space_marines_shock_cavalry_active")) is True
    assert set(sr.get("bearer_unit_phase_move_models_only_types", []) or []) >= {"move", "advance", "fall_back"}
    assert set(sr.get("bearer_unit_phase_move_models_only_block_titanic_types", []) or []) >= {
        "move",
        "advance",
        "fall_back",
    }
    assert set(sr.get("move_over_low_terrain_height_types", []) or []) >= {"move", "advance", "fall_back"}
    assert float(sr.get("move_over_low_terrain_height_value", 0.0) or 0.0) == 4.0

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=cavalry)
    assert bool(move_rules.get("can_move_through_enemy_models")) is True
    assert bool(move_rules.get("block_titanic_models")) is True
    assert bool(move_rules.get("can_move_through_terrain", False)) is False
    assert bool(move_rules.get("cannot_move_within_engagement_range", True)) is False
    assert bool(move_rules.get("cannot_end_in_engagement_range")) is True

    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    sr_after = dict(getattr(cavalry, "special_rules", {}) or {})
    assert bool(sr_after.get("space_marines_shock_cavalry_active", False)) is False
    assert "bearer_unit_phase_move_models_only_types" not in sr_after
    assert "bearer_unit_phase_move_models_only_block_titanic_types" not in sr_after
    assert "move_over_low_terrain_height_types" not in sr_after
    assert "move_over_low_terrain_height_value" not in sr_after


def test_shock_cavalry_charge_phase_applies_charge_model_passthrough_only():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    cavalry = _make_unit(
        "Thunderwolf Cavalry",
        keywords=["MOUNTED", "THUNDERWOLF CAVALRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(cavalry)
    _deploy_unit(game, cavalry, 10.0, 10.0)

    _set_phase(game, sm_player, "CHARGE_PHASE", 0)
    ok = sm_player.stratagems.use("SHOCK CAVALRY", unit=cavalry, phase_name="Charge phase")
    assert ok

    charge_rules = get_validation_rules(MovementType.CHARGE, moving_unit=cavalry)
    assert bool(charge_rules.get("can_move_through_enemy_models")) is True
    assert bool(charge_rules.get("block_titanic_models")) is True
    assert bool(charge_rules.get("can_move_through_terrain", False)) is False
    assert bool(charge_rules.get("cannot_end_in_engagement_range", False)) is False

    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    sr_after = dict(getattr(cavalry, "special_rules", {}) or {})
    assert bool(sr_after.get("space_marines_shock_cavalry_active", False)) is False


def test_shock_cavalry_rejects_non_thunderwolf_targets():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(intercessors)
    _deploy_unit(game, intercessors, 10.0, 10.0)

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    blocked = sm_player.stratagems.use("SHOCK CAVALRY", unit=intercessors, phase_name="Movement phase")
    assert not blocked
    assert int(sm_player.command_points or 0) == 10


def test_saga_beastslayer_descriptor_registered():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000010270003")
    assert descriptor is not None
    assert descriptor.name == "Shock Cavalry"
    assert descriptor.effect == "move_through_models_with_titanic_block_and_low_terrain"
    phase_map = dict(descriptor.effect_params.get("phase_move_types", {}) or {})
    assert list(phase_map.get("movement", []) or []) == ["move", "advance", "fall_back"]
    assert list(phase_map.get("charge", []) or []) == ["charge"]
