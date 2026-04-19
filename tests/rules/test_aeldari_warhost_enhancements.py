import unittest
from types import SimpleNamespace
from unittest.mock import patch


class MockDatasheet:
    def __init__(self, name: str, keywords=None, movement=6, model_count=1, base_size="32mm", save="4", wounds="1"):
        self.name = name
        self.faction_data = {"name": "Aeldari"}
        self.keywords = keywords or []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [{
            "M": str(movement), "T": "4", "Sv": str(save), "W": str(wounds),
            "Ld": "7", "OC": "1",
            "base_size": base_size, "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


class TestAeldariWarhostEnhancements(unittest.TestCase):
    def _make_ranged_profile(self, *, damage: str = "1", keywords: str = ""):
        from warhammer40k_ai.units.wargear import Wargear

        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": damage,
            "description": keywords,
            "type": "Ranged",
            "name": "Test Gun",
        }
        parent = Wargear(data)
        return parent.profiles["default"]

    def test_psychic_destroyer_adds_damage(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        army = Army.with_detachment("Aeldari", "Warhost")
        army.faction_id = "AE"
        unit = SimpleNamespace(
            special_rules={},
            models=[],
            possible_abilities=[],
            abilities=[],
            round_state=SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False),
        )
        unit.get_parent_army = lambda: army
        army.units = [unit]
        Enhancement(
            id="000009899005",
            name="Psychic Destroyer",
            faction_id="AE",
            detachment="Warhost",
            points=30,
            description="",
        ).apply_to_unit(unit)

        profile = self._make_ranged_profile(damage="1", keywords="Psychic")
        attacker = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker.set_parent_unit(unit)

        target_unit = SimpleNamespace(
            special_rules={},
            models=[],
            has_feel_no_pain=lambda: [],
            damaged_profile=None,
            damaged_profile_desc=None,
        )
        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.set_parent_unit(target_unit)
        target_unit.models = [target_model]

        before = target_model.wounds
        profile._damage_target_with_tracking(
            target_model,
            attacker,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(target_model.wounds, before - 2)

    def test_gift_of_foresight_makes_command_reroll_free_once_per_round(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.engine.game import Game, Battlefield
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.rules.stratagems import Stratagem

        game = Game(Battlefield(width=44, height=30))
        army = Army.with_detachment("Aeldari", "Warhost")
        army.faction_id = "AE"
        player = Player("P1", PlayerControl.LOCAL, army)
        game.add_player(player)

        unit = SimpleNamespace(
            name="Bearer Unit",
            special_rules={},
            deployed=True,
            reserve_status="deployed",
        )
        unit.is_alive = lambda: True
        unit.get_attached_unit_members = lambda: [unit]
        unit.get_parent_army = lambda: army
        army.units = [unit]

        Enhancement(
            id="000009899004",
            name="Gift of Foresight",
            faction_id="AE",
            detachment="Warhost",
            points=15,
            description="",
        ).apply_to_unit(unit)

        strat = Stratagem(
            id="core-cp",
            name="Command Re-roll",
            type="Core",
            description="",
            cp_cost=1,
            turn="Either",
            phase="Any phase",
            detachment="",
            faction_id="",
        )

        preview = player.preview_stratagem_cp_cost(strat, target_unit=unit)
        self.assertEqual(int(preview["cost"]), 0)

        player.set_next_optional_decision("GIFT_OF_FORESIGHT", True)
        applied = player.apply_stratagem_cp_cost(strat, target_unit=unit)
        self.assertEqual(int(applied["cost"]), 0)

        preview_after = player.preview_stratagem_cp_cost(strat, target_unit=unit)
        self.assertEqual(int(preview_after["cost"]), 1)

    def test_timeless_strategist_adds_battle_focus_token(self):
        from warhammer40k_ai.rules.battle_focus import BattleFocusManager
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize

        unit = SimpleNamespace(
            special_rules={"enhancement_timeless_strategist_battle_focus_bonus": 1},
            deployed=True,
            reserve_status="deployed",
        )
        unit.is_alive = lambda: True
        from warhammer40k_ai.roster.army import Army

        army = Army.with_detachment("Aeldari", "Warhost")
        army.faction_id = "AE"
        army.units = [unit]

        mgr = BattleFocusManager(army)
        game = SimpleNamespace(
            battlefield=Battlefield(BattlefieldSize.STRIKE_FORCE),
            turn=1,
            phase=SimpleNamespace(name="COMMAND_PHASE"),
        )

        mgr.on_battle_round_start(1, game=game)
        self.assertEqual(int(mgr.tokens), 6)

    def test_phoenix_gem_returns_at_phase_end(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize, BattleRoundPhases
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.units.unit import Unit

        bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(bf)

        army = Army.with_detachment("Aeldari", "Warhost")
        army.faction_id = "AE"
        player = Player("P1", PlayerControl.LOCAL, army)
        game.add_player(player)

        unit = Unit(MockDatasheet("Phoenix Bearer", model_count=1))
        unit.deployed = True
        unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        army.add_unit(unit)
        game.map.units = [unit]

        Enhancement(
            id="000009899002",
            name="Phoenix Gem",
            faction_id="AE",
            detachment="Warhost",
            points=35,
            description="",
        ).apply_to_unit(unit)
        unit.enhancement = SimpleNamespace(name="Phoenix Gem")

        game.phase = BattleRoundPhases.SHOOTING_PHASE

        unit.models[0].take_damage(2, game_map=game.map)
        self.assertEqual(len(unit.models), 0)
        self.assertTrue(game._phoenix_gem_pending)

        with patch("warhammer40k_ai.engine.game.get_roll", return_value=2):
            game._on_phase_end_cleanup(player=player, phase=game.phase)

        self.assertEqual(len(unit.models), 1)
        self.assertTrue(unit.models[0].is_alive)


if __name__ == "__main__":
    unittest.main()
