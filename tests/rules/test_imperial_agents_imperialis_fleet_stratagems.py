import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.movement import _evaluate_reserves_arrival_positions
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        faction_name="Imperial Agents",
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, faction_name="Imperial Agents", keywords=None, faction_keywords=None, abilities=None):
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    ia_army = Army("Imperial Agents", "Imperialis Fleet")
    ia_army.faction_id = "AOI"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    ia_player.command_points = 5
    enemy_player.command_points = 5
    return game, ia_player, enemy_player, ia_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _model_positions_for(unit: Unit, position: tuple[float, float, float]) -> list[dict]:
    model_id = str(get_entity_id(unit.models[0]) or "")
    return [
        {
            "model_id": model_id,
            "position": [float(position[0]), float(position[1]), float(position[2])],
            "facing": 0.0,
        }
    ]


def _apply_imperialis_fleet_enhancement(
    unit: Unit,
    *,
    enhancement_id: str,
    name: str,
    description: str,
) -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="AOI",
        detachment="Imperialis Fleet",
        detachment_id="000000895",
        points=0,
        description=str(description),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _fleetmaster_test_stratagem(name: str, *, cp_cost: int = 1) -> Stratagem:
    return Stratagem(
        id=f"test_{str(name).strip().lower().replace(' ', '_')}",
        name=str(name),
        type="Imperialis Fleet - Strategic Ploy Stratagem",
        description="",
        cp_cost=int(cp_cost),
        turn="Your turn",
        phase="Movement phase",
        detachment="Imperialis Fleet",
        faction_id="AOI",
    )


class TestImperialAgentsImperialisFleetStratagems(unittest.TestCase):
    def test_fleetmaster_enhancement_descriptor_registered(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000009138005")
        self.assertIsNotNone(desc)
        self.assertEqual(desc.name, "Fleetmaster")
        self.assertEqual(
            tuple(desc.effect_params.get("stratagem_names", ()) or ()),
            ("VIOLENT ACQUISITION", "MASTERS OF THE VOID", "CLOSE-QUARTERS BARRAGE"),
        )

    def test_masters_of_the_void_descriptor_registered(self):
        desc = get_stratagem_tool_descriptor(stratagem_id="000009139003")
        self.assertIsNotNone(desc)
        self.assertEqual(desc.name, "Masters of the Void")
        self.assertEqual(desc.effect, "strategic_reserves_enemy_deployment_zone_override")
        self.assertTrue(bool(desc.effect_params.get("allow_enemy_deployment_zone")))

        by_name = get_stratagem_tool_descriptor(name="MASTERS OF THE VOID")
        self.assertIsNotNone(by_name)
        self.assertEqual(str(getattr(by_name, "stratagem_id", "") or ""), "000009139003")

    def test_masters_of_the_void_requires_voidfarers_character_target(self):
        game, ia_player, _enemy_player, ia_army, _enemy_army = _build_game()
        invalid_target = _make_unit(
            "Agents Character",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        ia_army.add_unit(invalid_target)
        _place_unit(game, invalid_target, 10.0, 10.0)

        _set_phase(game, ia_player, "MOVEMENT_PHASE", 0)
        cp_before = int(ia_player.command_points or 0)
        ok = ia_player.stratagems.use("MASTERS OF THE VOID", unit=invalid_target, phase_name="Movement phase")
        self.assertFalse(ok)
        self.assertEqual(int(ia_player.command_points or 0), cp_before)

    def test_masters_of_the_void_allows_turn2_enemy_deployment_zone_for_strategic_reserves_then_expires(self):
        game, ia_player, _enemy_player, ia_army, _enemy_army = _build_game()

        target = _make_unit(
            "Rogue Trader",
            keywords=["INFANTRY", "CHARACTER", "VOIDFARERS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        arriving = _make_unit(
            "Navy Breachers",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        other_agents = _make_unit(
            "Arbites Squad",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        ia_army.add_unit(target)
        ia_army.add_unit(arriving)
        ia_army.add_unit(other_agents)

        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, other_agents, 12.0, 10.0)

        arriving.deployed = False
        arriving.reserve_status = "strategic_reserves"
        arriving._started_in_reserves = True

        game.is_position_in_enemy_deployment_zone = lambda x, y, _player_id: float(y) >= 39.0
        game.is_valid_strategic_reserves_edge = lambda edge, turn=None: str(edge) == "enemy"

        _set_phase(game, ia_player, "MOVEMENT_PHASE", 0)
        enemy_dz_position = (30.0, 43.0, 0.0)

        self.assertFalse(game.can_place_unit_arriving_from_reserves(arriving, enemy_dz_position, battlefield_edge="enemy"))
        evaluation_before = _evaluate_reserves_arrival_positions(
            game,
            arriving,
            _model_positions_for(arriving, enemy_dz_position),
        )
        self.assertTrue(bool(list(evaluation_before.get("errors") or [])))

        cp_before = int(ia_player.command_points or 0)
        ok = ia_player.stratagems.use("MASTERS OF THE VOID", unit=target, phase_name="Movement phase")
        self.assertTrue(ok)
        self.assertEqual(int(ia_player.command_points or 0), cp_before - 1)

        arriving_sr = getattr(arriving, "special_rules", {}) or {}
        self.assertTrue(bool(arriving_sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_active")))
        other_sr = getattr(other_agents, "special_rules", {}) or {}
        self.assertTrue(bool(other_sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_active")))

        self.assertTrue(game.can_place_unit_arriving_from_reserves(arriving, enemy_dz_position, battlefield_edge="enemy"))
        evaluation_after = _evaluate_reserves_arrival_positions(
            game,
            arriving,
            _model_positions_for(arriving, enemy_dz_position),
        )
        self.assertEqual(list(evaluation_after.get("errors") or []), [])

        game.event_system.publish("phase_end", player=ia_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        arriving_sr_after = getattr(arriving, "special_rules", {}) or {}
        self.assertFalse(bool(arriving_sr_after.get("imperial_agents_masters_of_the_void_enemy_dz_override_active")))
        other_sr_after = getattr(other_agents, "special_rules", {}) or {}
        self.assertFalse(bool(other_sr_after.get("imperial_agents_masters_of_the_void_enemy_dz_override_active")))

        self.assertFalse(game.can_place_unit_arriving_from_reserves(arriving, enemy_dz_position, battlefield_edge="enemy"))
        evaluation_expired = _evaluate_reserves_arrival_positions(
            game,
            arriving,
            _model_positions_for(arriving, enemy_dz_position),
        )
        self.assertTrue(bool(list(evaluation_expired.get("errors") or [])))

    def test_fleetmaster_applies_zero_cp_once_per_battle_round(self):
        game, ia_player, _enemy_player, ia_army, _enemy_army = _build_game()
        bearer = _make_unit(
            "Rogue Trader",
            keywords=["INFANTRY", "CHARACTER", "VOIDFARERS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        ia_army.add_unit(bearer)
        _place_unit(game, bearer, 8.0, 8.0)

        _apply_imperialis_fleet_enhancement(
            bearer,
            enhancement_id="000009138005",
            name="Fleetmaster",
            description=(
                "Once per battle round, you can target the bearer's unit with the Violent Acquisition, "
                "Masters of the Void or Close-quarters Barrage Stratagems for 0CP."
            ),
        )

        masters = _fleetmaster_test_stratagem("Masters of the Void", cp_cost=1)
        preview = ia_player.preview_stratagem_cp_cost(masters, target_unit=bearer)
        self.assertEqual(int(preview.get("cost", -1)), 0)
        self.assertTrue(any("Fleetmaster" in str(r) for r in list(preview.get("reasons", []) or [])))

        first = ia_player.apply_stratagem_cp_cost(masters, target_unit=bearer)
        self.assertEqual(int(first.get("cost", -1)), 0)
        self.assertTrue(bool(first.get("fleetmaster_use", False)))
        self.assertEqual(int(ia_player._ability_used_battle_round.get("FLEETMASTER_FREE_STRATAGEM", 0) or 0), 2)

        second = ia_player.apply_stratagem_cp_cost(masters, target_unit=bearer)
        self.assertEqual(int(second.get("cost", -1)), 1)
        self.assertFalse(bool(second.get("fleetmaster_use", False)))

        game.turn = 3
        third = ia_player.apply_stratagem_cp_cost(masters, target_unit=bearer)
        self.assertEqual(int(third.get("cost", -1)), 0)
        self.assertTrue(bool(third.get("fleetmaster_use", False)))
        self.assertEqual(int(ia_player._ability_used_battle_round.get("FLEETMASTER_FREE_STRATAGEM", 0) or 0), 3)

    def test_fleetmaster_accepts_all_configured_stratagem_names(self):
        game, ia_player, _enemy_player, ia_army, _enemy_army = _build_game()
        bearer = _make_unit(
            "Navis Commander",
            keywords=["INFANTRY", "CHARACTER", "VOIDFARERS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        ia_army.add_unit(bearer)
        _place_unit(game, bearer, 6.0, 6.0)

        _apply_imperialis_fleet_enhancement(
            bearer,
            enhancement_id="000009138005",
            name="Fleetmaster",
            description=(
                "Once per battle round, you can target the bearer's unit with the Violent Acquisition, "
                "Masters of the Void or Close-quarters Barrage Stratagems for 0CP."
            ),
        )

        test_names = [
            "Violent Acquisition",
            "Close-quarters Barrage",
            "Close Quarters Barrage",
        ]
        for turn, stratagem_name in enumerate(test_names, start=2):
            game.turn = int(turn)
            result = ia_player.apply_stratagem_cp_cost(
                _fleetmaster_test_stratagem(stratagem_name, cp_cost=2),
                target_unit=bearer,
            )
            self.assertEqual(int(result.get("cost", -1)), 0)
            self.assertTrue(bool(result.get("fleetmaster_use", False)))

        game.turn = 5
        non_matching = ia_player.apply_stratagem_cp_cost(
            _fleetmaster_test_stratagem("Displacer Field", cp_cost=1),
            target_unit=bearer,
        )
        self.assertEqual(int(non_matching.get("cost", -1)), 1)
        self.assertFalse(bool(non_matching.get("fleetmaster_use", False)))


if __name__ == "__main__":
    unittest.main()
