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
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "9",
                "Sv": "3",
                "W": "12",
                "Ld": "7",
                "OC": "4",
                "base_size": "80mm",
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
    tyr_army = Army("Tyranids", "Crusher Stampede")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)

    tyr_player.command_points = 10
    tyr_army.configure_rule_managers(force=True)
    tyr_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, tyr_player, enemy_player, tyr_army, enemy_army


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


def test_untrammelled_ferocity_applies_movement_overrides_and_cleans_up():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    monster = _make_unit(
        "Screamer-Killer",
        keywords=["MONSTER"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(monster)
    _deploy_unit(game, monster, 10.0, 10.0)

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "UNTRAMMELLED FEROCITY",
        unit=monster,
        phase_name="Movement phase",
    )
    assert ok
    assert int(tyr_player.command_points or 0) == 9

    sr = dict(getattr(monster, "special_rules", {}) or {})
    assert bool(sr.get("tyranids_untrammelled_ferocity_active")) is True
    assert set(sr.get("bearer_unit_phase_move_types", []) or []) >= {"move", "advance", "fall_back"}
    assert set(sr.get("bearer_unit_phase_move_block_titanic_types", []) or []) >= {"move", "advance", "fall_back"}
    assert set(sr.get("bearer_unit_phase_move_engagement_types", []) or []) >= {"move", "advance", "fall_back"}
    assert float(sr.get("titanic_stride_tall_terrain_height", 0.0) or 0.0) == 4.0

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=monster)
    assert bool(move_rules.get("can_move_through_enemy_models")) is True
    assert bool(move_rules.get("can_move_through_terrain")) is True
    assert bool(move_rules.get("block_titanic_models")) is True
    assert bool(move_rules.get("cannot_move_within_engagement_range", True)) is False
    assert bool(move_rules.get("cannot_end_in_engagement_range")) is True

    game.event_system.publish("phase_end", player=tyr_player, phase=game.phase)
    sr_after = dict(getattr(monster, "special_rules", {}) or {})
    assert bool(sr_after.get("tyranids_untrammelled_ferocity_active", False)) is False
    assert "bearer_unit_phase_move_types" not in sr_after
    assert "bearer_unit_phase_move_block_titanic_types" not in sr_after
    assert "bearer_unit_phase_move_engagement_types" not in sr_after
    assert "titanic_stride_tall_terrain_height" not in sr_after


def test_untrammelled_ferocity_rejects_non_monster_targets():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    infantry = _make_unit(
        "Termagants",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(infantry)
    _deploy_unit(game, infantry, 10.0, 10.0)

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    blocked = tyr_player.stratagems.use(
        "UNTRAMMELLED FEROCITY",
        unit=infantry,
        phase_name="Movement phase",
    )
    assert not blocked
    assert int(tyr_player.command_points or 0) == 10


def test_crusher_stampede_descriptor_registered():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000008422005")
    assert descriptor is not None
    assert descriptor.name == "Untrammelled Ferocity"
    assert descriptor.effect == "move_through_models_terrain_with_titanic_block_and_tall_terrain_battleshock_risk"
    assert list(descriptor.effect_params.get("move_types", []) or []) == ["move", "advance", "fall_back"]
    assert float(descriptor.effect_params.get("tall_terrain_threshold", 0.0) or 0.0) == 4.0
