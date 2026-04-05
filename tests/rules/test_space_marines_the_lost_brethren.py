import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        save: str = "3",
        wounds: int = 2,
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
                "Sv": str(save),
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4, save: str = "3", wounds: int = 2):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        save=save,
        wounds=wounds,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "The Lost Brethren"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1

    army_sm = Army("Space Marines", detachment_type)
    army_sm.faction_id = "SM"
    army_enemy = Army("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army_sm)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)

    return game, army_sm, army_enemy


def _make_melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Chainsword", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-1",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_ranged_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-1",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesTheLostBrethren(unittest.TestCase):
    def test_death_company_units_gain_battleline_keyword(self):
        _game, army_sm, _army_enemy = _build_game("The Lost Brethren")
        death_company = _make_unit(
            "Death Company Marines",
            keywords=["INFANTRY", "DEATH COMPANY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        death_company_bolters = _make_unit(
            "Death Company Marines with Bolt Rifles",
            keywords=["INFANTRY", "DEATH COMPANY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        intercessors = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(death_company)
        army_sm.add_unit(death_company_bolters)
        army_sm.add_unit(intercessors)

        self.assertTrue(death_company.is_battleline)
        self.assertTrue(death_company_bolters.is_battleline)
        self.assertFalse(intercessors.is_battleline)

    def test_death_company_does_not_gain_battleline_outside_lost_brethren(self):
        _game, army_sm, _army_enemy = _build_game("Gladius Task Force")
        death_company = _make_unit(
            "Death Company Marines",
            keywords=["INFANTRY", "DEATH COMPANY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(death_company)
        self.assertFalse(death_company.is_battleline)

    def test_a_noble_death_in_combat_rerolls_ones_in_melee_below_starting_strength(self):
        _game, army_sm, army_enemy = _build_game("The Lost Brethren")
        attacker = _make_unit(
            "Death Company Marines",
            keywords=["INFANTRY", "DEATH COMPANY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            wounds=4,
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        attacker.models[0].wounds = 3
        self.assertTrue(attacker.is_below_starting_strength())
        self.assertFalse(attacker.is_below_half_strength())

        profile = _make_melee_profile()
        wound = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 1.0},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertIn(1, list(wound.get("reroll_values", []) or []))
        self.assertTrue(any("A Noble Death in Combat" in r for r in list(wound.get("reroll_value_reasons", []) or [])))

    def test_a_noble_death_in_combat_rerolls_full_in_melee_below_half_strength(self):
        _game, army_sm, army_enemy = _build_game("The Lost Brethren")
        attacker = _make_unit(
            "Death Company Marines",
            keywords=["INFANTRY", "DEATH COMPANY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            wounds=4,
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        attacker.models[0].wounds = 1
        self.assertTrue(attacker.is_below_half_strength())

        profile = _make_melee_profile()
        wound = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 1.0},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("A Noble Death in Combat" in r for r in list(wound.get("reroll_full_reasons", []) or [])))

    def test_a_noble_death_in_combat_only_applies_to_melee_attacks(self):
        _game, army_sm, army_enemy = _build_game("The Lost Brethren")
        attacker = _make_unit(
            "Death Company Marines",
            keywords=["INFANTRY", "DEATH COMPANY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            wounds=4,
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        attacker.models[0].wounds = 1

        profile = _make_ranged_profile()
        wound = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 18.0},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertNotIn(1, list(wound.get("reroll_values", []) or []))
        self.assertFalse(any("A Noble Death in Combat" in r for r in list(wound.get("reroll_value_reasons", []) or [])))
        self.assertFalse(any("A Noble Death in Combat" in r for r in list(wound.get("reroll_full_reasons", []) or [])))


if __name__ == "__main__":
    unittest.main()
