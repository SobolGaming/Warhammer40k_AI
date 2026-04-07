import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
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


def _make_unit(name, *, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army.with_detachment("Orks", "Det")
    army1.faction_id = "ORK"
    army2 = Army.with_detachment("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    return game, army1, army2


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


class TestTargetHitRollPenalty(unittest.TestCase):
    def test_unit_target_hit_penalty(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Shimmer Shield",
            "description": "Each time an attack targets this unit, subtract 1 from the Hit roll.",
            "type": "Datasheet",
            "parameter": "",
        }
        _game, army1, army2 = _build_game()
        attacker = _make_unit("Attacker")
        target = _make_unit("Target", abilities=[ability])
        army1.add_unit(attacker)
        army2.add_unit(target)

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
            result = profile._hit_target_with_tracking(
                target,
                attacker.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )

        self.assertFalse(result["hit"])
        self.assertIn("-1 to hit from Shimmer Shield", result.get("modifiers", []))

    def test_melee_only_target_hit_penalty(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Duelist's Guard",
            "description": "Each time a melee attack targets this unit, subtract 1 from the Hit roll.",
            "type": "Datasheet",
            "parameter": "",
        }
        _game, army1, army2 = _build_game()
        attacker = _make_unit("Attacker")
        target = _make_unit("Target", abilities=[ability])
        army1.add_unit(attacker)
        army2.add_unit(target)

        melee_parent = SimpleNamespace(name="Blade", is_melee=lambda: True, is_ranged=lambda: False)
        melee_profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
            melee_result = melee_profile._hit_target_with_tracking(
                target,
                attacker.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )

        self.assertFalse(melee_result["hit"])
        self.assertIn("-1 to hit from Duelist's Guard", melee_result.get("modifiers", []))

        ranged_parent = SimpleNamespace(name="Pistol", is_melee=lambda: False, is_ranged=lambda: True)
        ranged_profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "12",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
        )

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
            ranged_result = ranged_profile._hit_target_with_tracking(
                target,
                attacker.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )

        self.assertTrue(ranged_result["hit"])
        self.assertNotIn("-1 to hit from Duelist's Guard", ranged_result.get("modifiers", []))

    def test_model_target_hit_penalty_single_model(self):
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.units.ability import Ability

        _game, army1, army2 = _build_game()
        attacker = _make_unit("Attacker")
        target = _make_unit("Solo")
        army1.add_unit(attacker)
        army2.add_unit(target)

        target.models[0].abilities = {
            "Ghost Cloak": Ability(
                "Ghost Cloak",
                "",
                "Each time an attack targets this model, subtract 1 from the Hit roll.",
                "Datasheet",
            )
        }
        target._invalidate_ability_cache()

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
            result = profile._hit_target_with_tracking(
                target,
                attacker.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )

        self.assertFalse(result["hit"])
        self.assertIn("-1 to hit from Ghost Cloak", result.get("modifiers", []))
