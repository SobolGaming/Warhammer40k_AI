import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(self, name, *, abilities=None):
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


def _attach_leader(leader, bodyguard):
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    leader.can_be_attached_to = [bodyguard.name]


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


class TestLeadingUnmodifiedSix(unittest.TestCase):
    def _setup_game(self, player, provider):
        game = SimpleNamespace(
            turn=1,
            phase=SimpleNamespace(name="Shooting"),
            get_current_player=lambda: player,
            map=SimpleNamespace(leading_unmodified_six_provider=provider),
        )
        player.game = game
        return game

    def _make_profile(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        return WargearProfile(
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

    def test_leading_unmodified_six_once_per_phase(self):
        ability = {
            "name": "Fated Guidance",
            "description": (
                "While this model is leading a unit, once per phase, you can change the result of one Hit roll, "
                "one Wound roll or one Damage roll made for a model in that unit to an unmodified 6."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        target = _make_unit("Target")

        _attach_leader(leader, bodyguard)

        player = SimpleNamespace(name="P1", id="P1", has_control=lambda: True, game=None)
        army = SimpleNamespace(player=player, units=[leader, bodyguard, target])
        leader.set_parent_army(army)
        bodyguard.set_parent_army(army)
        target.set_parent_army(army)

        def _provider(**kwargs):
            options = list(kwargs.get("options", []) or [])
            if not options:
                return "skip"
            return options[0].get("ability_key")

        self._setup_game(player, _provider)

        profile = self._make_profile()

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            result_first = profile._hit_target_with_tracking(
                target,
                bodyguard.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )
            result_second = profile._hit_target_with_tracking(
                target,
                bodyguard.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )

        self.assertEqual(int(result_first.get("roll", 0)), 6)
        self.assertIn("Leading ability: set roll to 6", result_first.get("special_effects", []))
        self.assertEqual(int(result_second.get("roll", 0)), 2)

    def test_leading_unmodified_six_excludes_support_weapon_models(self):
        ability = {
            "name": "Fated Guidance",
            "description": (
                "While this model is leading a unit, once per phase, you can change the result of one Hit roll, "
                "one Wound roll or one Damage roll made for a model in that unit (excluding Support Weapon models) "
                "to an unmodified 6."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        target = _make_unit("Target")

        support_weapon_ability = {
            "name": "Support Weapon",
            "description": (
                "Each time an attack targets this model's unit, if that unit contains one or more other models, "
                "until that attack is resolved, this model has a Toughness characteristic of 3."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        support_weapon = _make_unit("Support Weapon", abilities=[support_weapon_ability])

        _attach_leader(leader, bodyguard)
        support_weapon.support_joined_to = bodyguard
        bodyguard.attached_support_units = [support_weapon]

        player = SimpleNamespace(name="P1", id="P1", has_control=lambda: True, game=None)
        army = SimpleNamespace(player=player, units=[leader, bodyguard, target, support_weapon])
        leader.set_parent_army(army)
        bodyguard.set_parent_army(army)
        target.set_parent_army(army)
        support_weapon.set_parent_army(army)

        called = {"value": False}

        def _provider(**kwargs):
            called["value"] = True
            options = list(kwargs.get("options", []) or [])
            if not options:
                return "skip"
            return options[0].get("ability_key")

        self._setup_game(player, _provider)

        profile = self._make_profile()

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            result = profile._hit_target_with_tracking(
                target,
                support_weapon.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )

        self.assertEqual(int(result.get("roll", 0)), 2)
        self.assertFalse(called["value"])


if __name__ == "__main__":
    unittest.main()
