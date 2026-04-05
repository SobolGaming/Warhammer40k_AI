import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Grey Knights",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        abilities=None,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "Grey Knights":
                faction_keywords = ["GREY KNIGHTS"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Grey Knights",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    abilities=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            abilities=abilities,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    gk_army = Army("Grey Knights", "Brotherhood Strike")
    gk_army.faction_id = "GK"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    gk_player = Player("GK", control=PlayerControl.REMOTE, army=gk_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(gk_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, gk_army, enemy_army, gk_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="GK",
        detachment="Brotherhood Strike",
        points=15,
        description="",
    ).apply_to_unit(unit)


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.arrived_from_reserves_this_turn = False
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _enable_deep_strike(unit: Unit) -> None:
    unit.has_deep_strike = lambda: True


def _arrive_via_deep_strike(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "reserves"
    unit.embarked_in = None
    unit.arrived_from_reserves_this_turn = False
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    ok = unit._finalize_reserves_arrival(turn=int(game.turn or 0), game_map=game.map)
    if not ok:
        raise AssertionError(f"Failed to finalize reserves arrival for {getattr(unit, 'name', 'Unit')}")


class TestGreyKnightsBrotherhoodStrikeEnhancements(unittest.TestCase):
    def test_descriptors_registered(self):
        expected = {
            "000010348002": ("Banishing Wave (Psychic)", "deep_strike_setup_enemy_mortal_wound_table"),
            "000010348003": (
                "Blinding Aura",
                "prevent_fire_overwatch_against_bearer_unit_on_deep_strike_setup_turn",
            ),
            "000010348004": ("Purity of Purpose", "grant_charge_reroll_on_deep_strike_setup_turn"),
            "000010348005": ("Tome of Forbidden Ways", "increase_gate_of_infinity_max_units"),
        }
        for enhancement_id, (name, effect) in expected.items():
            with self.subTest(enhancement_id=enhancement_id):
                desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
                self.assertIsNotNone(desc)
                self.assertEqual(str(getattr(desc, "name", "") or ""), name)
                self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_enhancements_set_expected_special_rules(self):
        expected = {
            "000010348002": (
                "Banishing Wave (Psychic)",
                {
                    "enhancement_banishing_wave": True,
                    "enhancement_banishing_wave_range": 12,
                    "enhancement_banishing_wave_low_roll_min": 2,
                    "enhancement_banishing_wave_low_roll_max": 5,
                    "enhancement_banishing_wave_low_mortal_wounds": 1,
                    "enhancement_banishing_wave_high_roll_threshold": 6,
                    "enhancement_banishing_wave_high_mortal_wounds_roll": "D3",
                },
            ),
            "000010348003": (
                "Blinding Aura",
                {
                    "enhancement_blinding_aura": True,
                    "enhancement_blinding_aura_requires_bearer_alive": True,
                },
            ),
            "000010348004": (
                "Purity of Purpose",
                {
                    "enhancement_purity_of_purpose": True,
                    "enhancement_purity_of_purpose_charge_reroll": True,
                },
            ),
            "000010348005": (
                "Tome of Forbidden Ways",
                {
                    "enhancement_tome_of_forbidden_ways": True,
                    "enhancement_tome_of_forbidden_ways_additional_max_units": 1,
                },
            ),
        }
        for enhancement_id, (enhancement_name, expectations) in expected.items():
            with self.subTest(enhancement_id=enhancement_id):
                game, gk_army, _enemy_army, _gk_player, _enemy_player = _build_game()
                source = _make_unit(
                    "Brotherhood Champion",
                    keywords=["INFANTRY", "CHARACTER"],
                    faction_keywords=["GREY KNIGHTS"],
                )
                gk_army.add_unit(source)
                game.rebuild_entity_registry()

                _apply_enhancement(
                    source,
                    enhancement_id=enhancement_id,
                    enhancement_name=enhancement_name,
                )

                sr = dict(getattr(source, "special_rules", {}) or {})
                for key, value in expectations.items():
                    self.assertEqual(sr.get(key), value)

    def test_banishing_wave_applies_mortal_wounds_to_each_enemy_in_range_on_deep_strike(self):
        game, gk_army, enemy_army, _gk_player, _enemy_player = _build_game()
        source = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        near_enemy = _make_unit(
            "Near Enemy",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            wounds=4,
        )
        second_enemy = _make_unit(
            "Second Enemy",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            wounds=4,
        )
        far_enemy = _make_unit(
            "Far Enemy",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            wounds=4,
        )
        gk_army.add_unit(source)
        enemy_army.add_unit(near_enemy)
        enemy_army.add_unit(second_enemy)
        enemy_army.add_unit(far_enemy)
        _place_unit(game, near_enemy, 25.0, 20.0)
        _place_unit(game, second_enemy, 31.0, 20.0)
        _place_unit(game, far_enemy, 34.5, 20.0)
        _enable_deep_strike(source)
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010348002",
            enhancement_name="Banishing Wave (Psychic)",
        )

        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[2, 6, 3]):
            _arrive_via_deep_strike(game, source, 20.0, 20.0)

        remaining_wounds = sorted(
            [
                int(getattr(near_enemy.models[0], "wounds", 0) or 0),
                int(getattr(second_enemy.models[0], "wounds", 0) or 0),
            ]
        )
        self.assertEqual(remaining_wounds, [1, 3])
        self.assertEqual(int(getattr(far_enemy.models[0], "wounds", 0) or 0), 4)

    def test_blinding_aura_prevents_overwatch_only_on_setup_turn(self):
        game, gk_army, enemy_army, _gk_player, _enemy_player = _build_game()
        source = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        gk_army.add_unit(source)
        enemy_army.add_unit(enemy)
        _place_unit(game, enemy, 28.0, 20.0)
        _enable_deep_strike(source)
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010348003",
            enhancement_name="Blinding Aura",
        )

        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

        _arrive_via_deep_strike(game, source, 20.0, 20.0)
        self.assertTrue(source.is_overwatch_prevented_against(enemy, game=game))

        game.current_player_index = 1
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

        game.current_player_index = 0
        game.turn = 3
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

    def test_purity_of_purpose_grants_charge_reroll_only_on_setup_turn(self):
        game, gk_army, enemy_army, _gk_player, _enemy_player = _build_game()
        source = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        gk_army.add_unit(source)
        enemy_army.add_unit(enemy)
        _place_unit(game, enemy, 27.0, 20.0)
        _enable_deep_strike(source)
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010348004",
            enhancement_name="Purity of Purpose",
        )

        game.phase = BattleRoundPhases.CHARGE_PHASE
        self.assertFalse(source.can_reroll_charge_roll(target_unit=enemy, game=game, game_map=game.map))

        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        _arrive_via_deep_strike(game, source, 20.0, 20.0)
        game.phase = BattleRoundPhases.CHARGE_PHASE
        self.assertTrue(source.can_reroll_charge_roll(target_unit=enemy, game=game, game_map=game.map))

        game.current_player_index = 1
        self.assertFalse(source.can_reroll_charge_roll(target_unit=enemy, game=game, game_map=game.map))

        game.current_player_index = 0
        game.turn = 3
        self.assertFalse(source.can_reroll_charge_roll(target_unit=enemy, game=game, game_map=game.map))
