import unittest
from types import SimpleNamespace


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


class TestTargetedStratagemCpDiscount(unittest.TestCase):
    def _make_player(self, units, *, battle_round=1):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army.with_detachment("Test", "Test")
        if not isinstance(units, (list, tuple)):
            units = [units]
        army.units = list(units)
        for unit in army.units:
            try:
                unit.set_parent_army(army)
            except Exception:
                pass
        player = Player("P1", control=PlayerControl.LOCAL, army=army)
        player.command_points = 1
        player.set_game(SimpleNamespace(turn=battle_round))
        return player

    def _ability_text(self):
        return (
            "Once per battle round, one unit from your army with this ability can use it when its unit is targeted "
            "with a Stratagem. If it does, reduce the CP cost of that use of that Stratagem by 1CP."
        )

    def _aura_ability_text(self):
        return (
            "Once per battle round, one model from your army with this ability can use it when a friendly World Eaters "
            "unit within 12\" of that model is targeted with a Stratagem. If it does, reduce the CP cost of that usage "
            "of that Stratagem by 1CP."
        )

    def _once_per_turn_model_text(self):
        return (
            "Once per turn, when you target this model with a stratagem, you may reduce the CP cost of that use of that "
            "stratagem by 1CP."
        )

    def _select_model_ability_texts(self):
        return [
            (
                "Once per battle round, you can select one model from your army with this ability. That model's unit can be "
                "targeted with a Stratagem. If it does, reduce the CP cost of that use of that Stratagem by 1CP."
            ),
            (
                "Once per battle round, you can select one model from your army with this ability and target that model's unit "
                "with a Stratagem. If it does, reduce the CP cost of that use of that Stratagem by 1CP."
            ),
        ]

    def test_parses_targeted_stratagem_cp_discount(self):
        ability = {
            "name": "Strategic Coordination",
            "description": self._ability_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Coordinator", abilities=[ability])
        self.assertTrue(unit.special_rules.get("stratagem_target_cp_discount"))
        sources = unit.special_rules.get("stratagem_target_cp_discount_sources", [])
        self.assertIn("Strategic Coordination", sources)

    def test_parses_select_model_stratagem_cp_discount_variants(self):
        for text in self._select_model_ability_texts():
            with self.subTest(text=text):
                ability = {
                    "name": "Strategic Coordination",
                    "description": text,
                    "type": "Datasheet",
                    "parameter": "",
                }
                unit = _make_unit("Coordinator", abilities=[ability])
                self.assertTrue(unit.special_rules.get("stratagem_target_cp_discount"))
                sources = unit.special_rules.get("stratagem_target_cp_discount_sources", [])
                self.assertIn("Strategic Coordination", sources)

    def test_parses_once_per_turn_target_this_model_discount(self):
        ability = {
            "name": "Legendary Freeblade",
            "description": self._once_per_turn_model_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Canis Rex", abilities=[ability])
        self.assertTrue(unit.special_rules.get("stratagem_target_cp_discount"))
        specs = list(unit.special_rules.get("stratagem_target_cp_discount_specs", []) or [])
        self.assertTrue(specs)
        self.assertEqual(str(specs[0].get("limit", "") or "").lower(), "turn")
        self.assertEqual(str(specs[0].get("usage_scope", "") or "").lower(), "source_model")

    def test_discount_applies_once_per_battle_round(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        ability = {
            "name": "Strategic Coordination",
            "description": self._ability_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Coordinator", abilities=[ability])
        player = self._make_player(unit, battle_round=1)
        player.decision_hook = lambda _p, key, _ctx: key == "TARGETED_STRATAGEM_DISCOUNT"
        strat = Stratagem(id="x", name="Test", type="Core", description="", cp_cost=2, turn="Either", phase="Any phase", detachment="", faction_id="")

        ok = strat.can_use(player, player.game, target_unit=unit)
        self.assertTrue(ok)

        used = strat.use(player, player.game, target_unit=unit)
        self.assertTrue(used)
        self.assertEqual(int(player.command_points), 0)

        player.command_points = 1
        ok2 = strat.can_use(player, player.game, target_unit=unit)
        self.assertFalse(ok2)

    def test_once_per_turn_model_discount_resets_on_turn_change(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        ability = {
            "name": "Legendary Freeblade",
            "description": self._once_per_turn_model_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Canis Rex", abilities=[ability])
        player = self._make_player(unit, battle_round=1)
        player.game.current_player_index = 0
        player.decision_hook = lambda _p, key, _ctx: key == "TARGETED_STRATAGEM_DISCOUNT"
        strat = Stratagem(id="x", name="Test", type="Core", description="", cp_cost=2, turn="Either", phase="Any phase", detachment="", faction_id="")

        used = strat.use(player, player.game, target_unit=unit)
        self.assertTrue(used)
        self.assertEqual(int(player.command_points), 0)

        player.command_points = 1
        same_turn_ok = strat.can_use(player, player.game, target_unit=unit)
        self.assertFalse(same_turn_ok)

        player.game.current_player_index = 1
        next_turn_ok = strat.can_use(player, player.game, target_unit=unit)
        self.assertTrue(next_turn_ok)

    def test_no_auto_use_without_decision_hook(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        ability = {
            "name": "Strategic Coordination",
            "description": self._ability_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Coordinator", abilities=[ability])
        player = self._make_player(unit, battle_round=1)
        strat = Stratagem(id="x", name="Test", type="Core", description="", cp_cost=2, turn="Either", phase="Any phase", detachment="", faction_id="")

        ok = strat.can_use(player, player.game, target_unit=unit)
        self.assertFalse(ok)

    def test_one_shot_override_allows_discount(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        ability = {
            "name": "Strategic Coordination",
            "description": self._ability_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Coordinator", abilities=[ability])
        player = self._make_player(unit, battle_round=1)
        player.set_next_optional_decision("TARGETED_STRATAGEM_DISCOUNT", True)
        strat = Stratagem(id="x", name="Test", type="Core", description="", cp_cost=2, turn="Either", phase="Any phase", detachment="", faction_id="")

        used = strat.use(player, player.game, target_unit=unit)
        self.assertTrue(used)

    def test_parses_targeted_stratagem_cp_discount_aura(self):
        ability = {
            "name": "Battlefield Tactician",
            "description": self._aura_ability_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Herald", abilities=[ability])
        specs = list(unit.special_rules.get("stratagem_target_cp_discount_aura", []) or [])
        self.assertTrue(specs)
        self.assertEqual(int(specs[0].get("range", 0)), 12)
        self.assertEqual(specs[0].get("keyword"), "WORLD EATERS")

    def test_discount_applies_within_range_for_friendly_world_eaters(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        ability = {
            "name": "Battlefield Tactician",
            "description": self._aura_ability_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        source = _make_unit("Herald", abilities=[ability])
        target = _make_unit("Berserkers", keywords=["WORLD EATERS"])
        source.models[0].model_base.set_position(0.0, 0.0, 0.0)
        target.models[0].model_base.set_position(10.0, 0.0, 0.0)
        player = self._make_player([source, target], battle_round=1)
        player.decision_hook = lambda _p, key, _ctx: key == "TARGETED_STRATAGEM_DISCOUNT"
        strat = Stratagem(id="x", name="Test", type="Core", description="", cp_cost=2, turn="Either", phase="Any phase", detachment="", faction_id="")

        ok = strat.can_use(player, player.game, target_unit=target)
        self.assertTrue(ok)
        used = strat.use(player, player.game, target_unit=target)
        self.assertTrue(used)
        self.assertEqual(int(player.command_points), 0)

    def test_discount_requires_range_for_aura(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        ability = {
            "name": "Battlefield Tactician",
            "description": self._aura_ability_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        source = _make_unit("Herald", abilities=[ability])
        target = _make_unit("Berserkers", keywords=["WORLD EATERS"])
        source.models[0].model_base.set_position(0.0, 0.0, 0.0)
        target.models[0].model_base.set_position(20.0, 0.0, 0.0)
        player = self._make_player([source, target], battle_round=1)
        player.decision_hook = lambda _p, key, _ctx: key == "TARGETED_STRATAGEM_DISCOUNT"
        strat = Stratagem(id="x", name="Test", type="Core", description="", cp_cost=2, turn="Either", phase="Any phase", detachment="", faction_id="")

        ok = strat.can_use(player, player.game, target_unit=target)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
