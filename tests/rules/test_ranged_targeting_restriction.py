import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count=1,
        base_size="32mm",
        attached_to=None,
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None, attached_to=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        attached_to=attached_to,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Army1", detachment_type="Detachment1")
    army1.faction_id = "A1"
    army2 = Army("Army2", detachment_type="Detachment2")
    army2.faction_id = "A2"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.LOCAL, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2


def _make_ranged_profile():
    from types import SimpleNamespace
    from warhammer40k_ai.units.wargear import WargearProfile

    ranged_parent = SimpleNamespace(name="Test Gun", is_ranged=lambda: True, is_melee=lambda: False)
    profile = WargearProfile(
        profile_name="Test",
        wargear_data={
            "range": "48",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=ranged_parent,
    )
    profile.is_indirect_fire = lambda: True
    profile.is_torrent = lambda: False
    profile.is_pistol = lambda: False
    profile.is_blast = lambda: False
    return profile


class TestRangedTargetingRestriction(unittest.TestCase):
    def test_unit_ranged_targeting_restriction_18(self):
        game, army1, army2 = _build_game()

        ability = [
            {
                "name": "Shade Weavers",
                "description": "This unit can only be selected as the target of a ranged attack if the attacking model is within 18\".",
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        target_unit = _make_unit("Target", abilities=ability)
        attacker_unit = _make_unit("Attacker")

        army1.add_unit(attacker_unit)
        army2.add_unit(target_unit)

        attacker_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target_unit.models[0].set_location(25.0, 0.0, 0.0, 0.0)

        game.map.units = [attacker_unit, target_unit]
        profile = _make_ranged_profile()

        can_target = attacker_unit._can_model_shoot_weapon_at_target(
            attacker_unit.models[0],
            profile,
            target_unit,
            game.map,
        )
        self.assertFalse(can_target)

        target_unit.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        can_target_close = attacker_unit._can_model_shoot_weapon_at_target(
            attacker_unit.models[0],
            profile,
            target_unit,
            game.map,
        )
        self.assertTrue(can_target_close)

    def test_leading_ranged_targeting_restriction_applies_to_attached_unit(self):
        game, army1, army2 = _build_game()

        ability = [
            {
                "name": "Haloed in Soulfire (Psychic)",
                "description": "While this model is leading a unit, that unit can only be selected as the target of a ranged attack if the attacking model is within 18\".",
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        leader_unit = _make_unit("Leader", abilities=ability, attached_to=["BG"])
        bodyguard_unit = _make_unit("Bodyguard")
        attacker_unit = _make_unit("Attacker")

        leader_unit.attached_to = bodyguard_unit
        bodyguard_unit.attached_leaders = [leader_unit]

        army1.add_unit(attacker_unit)
        army2.add_unit(bodyguard_unit)
        army2.add_unit(leader_unit)

        attacker_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        bodyguard_unit.models[0].set_location(25.0, 0.0, 0.0, 0.0)
        leader_unit.models[0].set_location(25.0, 0.0, 0.0, 0.0)

        game.map.units = [attacker_unit, bodyguard_unit, leader_unit]
        profile = _make_ranged_profile()

        can_target = attacker_unit._can_model_shoot_weapon_at_target(
            attacker_unit.models[0],
            profile,
            bodyguard_unit,
            game.map,
        )
        self.assertFalse(can_target)

        bodyguard_unit.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        leader_unit.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        can_target_close = attacker_unit._can_model_shoot_weapon_at_target(
            attacker_unit.models[0],
            profile,
            bodyguard_unit,
            game.map,
        )
        self.assertTrue(can_target_close)


if __name__ == "__main__":
    unittest.main()
