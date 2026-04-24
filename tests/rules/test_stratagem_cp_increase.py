import unittest
from types import SimpleNamespace

from tests.decision_request_helpers import install_decision_request_support


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
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


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities, keywords=keywords, faction_keywords=faction_keywords)
    return Unit(datasheet)


def _make_players(active_units, opponent_units, *, turn=1, current_player_index=0):
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    army1 = Army.with_detachment("Active", "Test")
    army2 = Army.with_detachment("Opponent", "Test")
    army1.units = list(active_units if isinstance(active_units, (list, tuple)) else [active_units])
    army2.units = list(opponent_units if isinstance(opponent_units, (list, tuple)) else [opponent_units])

    for unit in army1.units:
        try:
            unit.set_parent_army(army1)
        except Exception:
            pass
    for unit in army2.units:
        try:
            unit.set_parent_army(army2)
        except Exception:
            pass

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.LOCAL, army=army2)
    game = install_decision_request_support(
        SimpleNamespace(turn=turn, current_player_index=current_player_index, players=[p1, p2])
    )
    p1.set_game(game)
    p2.set_game(game)
    return p1, p2, game


class TestStratagemCpIncrease(unittest.TestCase):
    def _aura_text(self):
        return (
            "Each time your opponent targets a unit from their army with a Stratagem, "
            "if that unit is within 12\" of this model, increase the CP cost of that Stratagem by 1CP "
            "(to a maximum of 2CP)."
        )

    def _optional_text(self):
        return (
            "Once per turn, when your opponent targets a unit from their army with a Stratagem, "
            "if that unit is within 12\" of this model, you can use this ability. If you do, "
            "increase the CP cost of that Stratagem by 1CP."
        )

    def test_parses_stratagem_cp_increase_aura(self):
        ability = {
            "name": "One Head Looks Back (Aura)",
            "description": self._aura_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Harbinger", abilities=[ability])
        specs = list(unit.special_rules.get("stratagem_target_cp_increase_aura", []) or [])
        self.assertTrue(specs)
        self.assertEqual(int(specs[0].get("range", 0)), 12)
        self.assertEqual(int(specs[0].get("max_cp", 0)), 2)
        self.assertFalse(bool(specs[0].get("optional", False)))

    def test_increase_blocks_affordability_and_counts_used(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        ability = {
            "name": "One Head Looks Back (Aura)",
            "description": self._aura_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        opponent_unit = _make_unit("Harbinger", abilities=[ability])
        active_unit = _make_unit("Defenders")
        opponent_unit.models[0].model_base.set_position(0.0, 0.0, 0.0)
        active_unit.models[0].model_base.set_position(6.0, 0.0, 0.0)

        player, opponent, game = _make_players(active_unit, opponent_unit, turn=1, current_player_index=0)
        player.command_points = 1
        strat = Stratagem(
            id="x",
            name="Test Strat",
            type="Core",
            description="",
            cp_cost=1,
            turn="Either",
            phase="Any phase",
            detachment="",
            faction_id="",
        )

        ok = strat.can_use(player, game, target_unit=active_unit)
        self.assertTrue(ok)

        used = strat.use(player, game, target_unit=active_unit)
        self.assertFalse(used)
        self.assertEqual(int(player.command_points), 1)
        self.assertIn("TEST STRAT", player.stratagems._used_stratagems_this_phase)

    def test_optional_cp_increase_requires_decision(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        ability = {
            "name": "Torc of Morai-Heg",
            "description": self._optional_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        opponent_unit = _make_unit("Seer", abilities=[ability])
        active_unit = _make_unit("Defenders")
        opponent_unit.models[0].model_base.set_position(0.0, 0.0, 0.0)
        active_unit.models[0].model_base.set_position(6.0, 0.0, 0.0)

        player, opponent, game = _make_players(active_unit, opponent_unit, turn=1, current_player_index=0)
        opponent.decision_hook = lambda _p, key, _ctx: key == "OPPONENT_STRATAGEM_CP_INCREASE"
        player.command_points = 2
        strat = Stratagem(
            id="x",
            name="Test Strat",
            type="Core",
            description="",
            cp_cost=1,
            turn="Either",
            phase="Any phase",
            detachment="",
            faction_id="",
        )

        used = strat.use(player, game, target_unit=active_unit)
        self.assertTrue(used)
        self.assertEqual(int(player.command_points), 0)

    def test_torc_optional_increase_unaffordable_counts_used_and_spends_no_cp(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        ability = {
            "name": "Torc of Morai-Heg",
            "description": self._optional_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        opponent_unit = _make_unit("Seer", abilities=[ability])
        active_unit = _make_unit("Defenders")
        opponent_unit.models[0].model_base.set_position(0.0, 0.0, 0.0)
        active_unit.models[0].model_base.set_position(6.0, 0.0, 0.0)

        player, opponent, game = _make_players(active_unit, opponent_unit, turn=1, current_player_index=0)
        opponent.decision_hook = lambda _p, key, _ctx: key == "OPPONENT_STRATAGEM_CP_INCREASE"
        player.command_points = 1
        strat = Stratagem(
            id="x",
            name="Test Strat",
            type="Core",
            description="",
            cp_cost=1,
            turn="Either",
            phase="Any phase",
            detachment="",
            faction_id="",
        )

        used = strat.use(player, game, target_unit=active_unit)
        self.assertFalse(used)
        self.assertEqual(int(player.command_points), 1)
        self.assertIn("TEST STRAT", player.stratagems._used_stratagems_this_phase)

    def test_enhancement_parsed_for_cp_increase(self):
        from warhammer40k_ai.rules.enhancement import Enhancement

        enhancement = Enhancement.from_waha_dict(
            {
                "id": "enh1",
                "name": "Torc of Morai-Heg",
                "faction_id": "AE",
                "detachment": "Seer Council",
                "detachment_id": "000001023",
                "cost": "20",
                "description": self._optional_text(),
            }
        )
        unit = _make_unit("Seer")
        unit.enhancement = enhancement
        enhancement.apply_to_unit(unit)
        specs = list(unit.special_rules.get("stratagem_target_cp_increase_aura", []) or [])
        self.assertTrue(specs)
        self.assertTrue(bool(specs[0].get("optional", False)))


if __name__ == "__main__":
    unittest.main()
