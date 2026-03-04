import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.movement import _evaluate_reserves_arrival_positions
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
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

    ia_army = Army("Imperial Agents", "Ordo Malleus Daemon Hunters")
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


def _model_positions_for(unit: Unit, position: tuple[float, float, float]) -> list[dict]:
    model_id = str(get_entity_id(unit.models[0]) or "")
    return [
        {
            "model_id": model_id,
            "position": [float(position[0]), float(position[1]), float(position[2])],
            "facing": 0.0,
        }
    ]


def _apply_ordo_malleus_enhancement(
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
        detachment="Ordo Malleus Daemon Hunters",
        detachment_id="000000894",
        points=0,
        description=str(description),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _rapid_ingress_test_stratagem(*, cp_cost: int = 1) -> Stratagem:
    return Stratagem(
        id="test_rapid_ingress",
        name="Rapid Ingress",
        type="Core - Strategic Ploy Stratagem",
        description="",
        cp_cost=int(cp_cost),
        turn="Opponent's turn",
        phase="Movement phase",
        detachment="",
        faction_id="CORE",
    )


class TestImperialAgentsOrdoMalleusEnhancements(unittest.TestCase):
    def test_gift_of_the_prescient_enhancement_descriptor_registered(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000009134004")
        self.assertIsNotNone(desc)
        self.assertEqual(desc.name, "Gift of the Prescient")
        self.assertEqual(tuple(desc.effect_params.get("stratagem_names", ()) or ()), ("RAPID INGRESS",))
        self.assertEqual(
            tuple(desc.effect_params.get("required_target_unit_name_patterns", ()) or ()),
            ("GREY KNIGHTS TERMINATOR SQUAD",),
        )
        self.assertEqual(float(desc.effect_params.get("deep_strike_min_distance", 0.0) or 0.0), 3.0)

    def test_gift_of_the_prescient_applies_zero_cp_once_per_battle_and_requires_gk_terminator_target(self):
        game, ia_player, _enemy_player, ia_army, _enemy_army = _build_game()
        bearer = _make_unit(
            "Ordo Malleus Inquisitor",
            keywords=["INFANTRY", "CHARACTER", "INQUISITOR", "ORDO MALLEUS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        gk_terminators = _make_unit(
            "Grey Knights Terminator Squad",
            keywords=["INFANTRY", "TERMINATOR", "GREY KNIGHTS"],
            faction_keywords=["IMPERIUM", "GREY KNIGHTS"],
        )
        other_target = _make_unit(
            "Imperial Navy Breachers",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        ia_army.add_unit(bearer)
        ia_army.add_unit(gk_terminators)
        ia_army.add_unit(other_target)
        _place_unit(game, bearer, 8.0, 8.0)
        _place_unit(game, other_target, 10.0, 8.0)
        gk_terminators.deployed = False
        gk_terminators.reserve_status = "reserves"

        _apply_ordo_malleus_enhancement(
            bearer,
            enhancement_id="000009134004",
            name="Gift of the Prescient",
            description=(
                "Once per battle, if the bearer is on the battlefield, you can use the Rapid Ingress Stratagem for 0CP. "
                "When doing so, you must target a GREY KNIGHTS TERMINATOR SQUAD unit from your army, and when using that "
                "Stratagem, that unit can be set up anywhere on the battlefield that is more than 3\" away from all enemy units."
            ),
        )

        rapid_ingress = _rapid_ingress_test_stratagem(cp_cost=1)

        non_eligible_preview = ia_player.preview_stratagem_cp_cost(rapid_ingress, target_unit=other_target)
        self.assertEqual(int(non_eligible_preview.get("cost", -1)), 1)

        preview = ia_player.preview_stratagem_cp_cost(rapid_ingress, target_unit=gk_terminators)
        self.assertEqual(int(preview.get("cost", -1)), 0)
        self.assertTrue(any("Gift of the Prescient" in str(r) for r in list(preview.get("reasons", []) or [])))

        first = ia_player.apply_stratagem_cp_cost(rapid_ingress, target_unit=gk_terminators)
        self.assertEqual(int(first.get("cost", -1)), 0)
        self.assertTrue(bool(first.get("gift_of_the_prescient_use", False)))
        self.assertEqual(float(first.get("gift_of_the_prescient_deep_strike_min_distance", 0.0) or 0.0), 3.0)
        self.assertTrue(bool(bearer.has_used_unit_once_per_battle("gift_of_the_prescient_rapid_ingress")))

        second = ia_player.apply_stratagem_cp_cost(rapid_ingress, target_unit=gk_terminators)
        self.assertEqual(int(second.get("cost", -1)), 1)
        self.assertFalse(bool(second.get("gift_of_the_prescient_use", False)))

    def test_gift_of_the_prescient_allows_rapid_ingress_setup_more_than_three_from_enemy(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        bearer = _make_unit(
            "Inquisitor Lord",
            keywords=["INFANTRY", "CHARACTER", "INQUISITOR", "ORDO MALLEUS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        gk_terminators = _make_unit(
            "Grey Knights Terminator Squad",
            keywords=["INFANTRY", "TERMINATOR", "GREY KNIGHTS"],
            faction_keywords=["IMPERIUM", "GREY KNIGHTS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(bearer)
        ia_army.add_unit(gk_terminators)
        enemy_army.add_unit(enemy)

        _place_unit(game, bearer, 8.0, 8.0)
        _place_unit(game, enemy, 28.0, 20.0)

        gk_terminators.deployed = False
        gk_terminators.reserve_status = "reserves"
        gk_terminators._started_in_reserves = True
        gk_terminators.special_rules["bearer_unit_deep_strike"] = True

        _apply_ordo_malleus_enhancement(
            bearer,
            enhancement_id="000009134004",
            name="Gift of the Prescient",
            description=(
                "Once per battle, if the bearer is on the battlefield, you can use the Rapid Ingress Stratagem for 0CP. "
                "When doing so, you must target a GREY KNIGHTS TERMINATOR SQUAD unit from your army, and when using that "
                "Stratagem, that unit can be set up anywhere on the battlefield that is more than 3\" away from all enemy units."
            ),
        )

        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 1  # Opponent's turn
        ia_player.command_points = 0
        enemy_player.command_points = 5

        near_enemy_position = (21.0, 20.0, 0.0)
        evaluation_before = _evaluate_reserves_arrival_positions(
            game,
            gk_terminators,
            _model_positions_for(gk_terminators, near_enemy_position),
        )
        self.assertTrue(bool(list(evaluation_before.get("errors") or [])))

        used = ia_player.stratagems.use(
            "RAPID INGRESS",
            unit=gk_terminators,
            phase_name="Movement phase",
            position=near_enemy_position,
        )
        self.assertTrue(bool(used))
        self.assertEqual(int(ia_player.command_points or 0), 0)
        self.assertTrue(bool(gk_terminators.deployed))
        self.assertEqual(str(gk_terminators.reserve_status or ""), "deployed")
        self.assertNotIn("gift_of_the_prescient_deep_strike_min_distance", gk_terminators.special_rules)


if __name__ == "__main__":
    unittest.main()
