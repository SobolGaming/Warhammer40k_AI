import unittest

from warhammer40k_ai.engine.decision_handlers.movement import _evaluate_reserves_arrival_positions
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "T'au Empire",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "T'au Empire":
                faction_keywords = ["T'AU EMPIRE"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "5",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "40mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "T'au Empire",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    tau_army = Army("T'au Empire", "Auxiliary Cadre")
    tau_army.faction_id = "TAU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tau_player = Player("Tau", control=PlayerControl.REMOTE, army=tau_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tau_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, tau_army, enemy_army


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="TAU",
        detachment="Auxiliary Cadre",
        points=25,
        description="",
    ).apply_to_unit(unit)


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


class TestTauAuxiliaryCadreEnhancements(unittest.TestCase):
    def test_transponder_lock_module_descriptor_registered(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000009839005")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Transponder Lock Module")
        self.assertEqual(
            str(getattr(desc, "effect", "") or ""),
            "first_turn_deep_strike_arrival_with_auxiliary_spotter_requirement",
        )

    def test_transponder_lock_module_sets_expected_special_rules(self):
        game, tau_army, _enemy_army = _build_game()
        unit = _make_unit(
            "XV95 Ghostkeel",
            keywords=["WALKER", "BATTLESUIT", "CHARACTER"],
            faction_keywords=["T'AU EMPIRE"],
        )
        tau_army.add_unit(unit)
        game.rebuild_entity_registry()

        _apply_enhancement(
            unit,
            enhancement_id="000009839005",
            enhancement_name="Transponder Lock Module",
        )
        sr = dict(getattr(unit, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_transponder_lock_module", False)))
        self.assertEqual(int(sr.get("enhancement_transponder_lock_module_round_bonus", 0) or 0), 1)
        self.assertTrue(bool(sr.get("enhancement_transponder_lock_module_requires_deep_strike", False)))
        self.assertEqual(float(sr.get("enhancement_transponder_lock_module_turn_one_spotter_range", 0.0) or 0.0), 12.0)
        self.assertEqual(
            list(sr.get("enhancement_transponder_lock_module_turn_one_spotter_keywords_any", []) or []),
            ["KROOT", "VESPID STINGWINGS"],
        )

    def test_transponder_lock_module_round_bonus_requires_deep_strike(self):
        game, tau_army, _enemy_army = _build_game()
        unit = _make_unit(
            "XV95 Ghostkeel",
            keywords=["WALKER", "BATTLESUIT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        tau_army.add_unit(unit)
        unit.deployed = False
        unit.set_reserve_status("strategic_reserves")
        unit._started_in_reserves = True
        unit.has_deep_strike = lambda: True
        game.rebuild_entity_registry()

        _apply_enhancement(
            unit,
            enhancement_id="000009839005",
            enhancement_name="Transponder Lock Module",
        )

        self.assertEqual(int(unit._strategic_reserves_round_bonus() or 0), 1)
        self.assertTrue(unit.can_arrive_from_reserves(1))

        unit.has_deep_strike = lambda: False
        self.assertEqual(int(unit._strategic_reserves_round_bonus() or 0), 0)
        self.assertFalse(unit.can_arrive_from_reserves(1))

    def test_transponder_turn_one_spotter_requirement_applies_to_both_reserves_validators(self):
        game, tau_army, enemy_army = _build_game()

        arriving = _make_unit(
            "XV95 Ghostkeel",
            keywords=["WALKER", "BATTLESUIT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        tau_army.add_unit(arriving)
        enemy_army.add_unit(enemy)
        _place_unit(game, enemy, 55.0, 30.0)

        _apply_enhancement(
            arriving,
            enhancement_id="000009839005",
            enhancement_name="Transponder Lock Module",
        )
        arriving.deployed = False
        arriving.reserve_status = "strategic_reserves"
        arriving._started_in_reserves = True
        arriving.has_deep_strike = lambda: True
        game.rebuild_entity_registry()

        arrival_pos = (30.0, 30.0, 0.0)
        self.assertFalse(game.can_place_unit_arriving_from_reserves(arriving, arrival_pos))

        evaluation_without_spotter = _evaluate_reserves_arrival_positions(
            game,
            arriving,
            _model_positions_for(arriving, arrival_pos),
        )
        errors_without_spotter = list(evaluation_without_spotter.get("errors") or [])
        self.assertTrue(errors_without_spotter)
        self.assertIn("Transponder Lock Module", errors_without_spotter[0])

        spotter = _make_unit(
            "Kroot Carnivores",
            keywords=["INFANTRY", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        tau_army.add_unit(spotter)
        _place_unit(game, spotter, 36.0, 30.0)
        game.rebuild_entity_registry()

        self.assertTrue(game.can_place_unit_arriving_from_reserves(arriving, arrival_pos))
        evaluation_with_spotter = _evaluate_reserves_arrival_positions(
            game,
            arriving,
            _model_positions_for(arriving, arrival_pos),
        )
        self.assertEqual(list(evaluation_with_spotter.get("errors") or []), [])


if __name__ == "__main__":
    unittest.main()
