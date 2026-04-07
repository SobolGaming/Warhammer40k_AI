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


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None, model_count=1):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army.with_detachment("Army1", detachment_type="Detachment1")
    army1.faction_id = "A1"
    army2 = Army.with_detachment("Army2", detachment_type="Detachment2")
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


class TestIgnoreLoneOperativeTargeting(unittest.TestCase):
    def test_ignore_lone_operative_allows_targeting_beyond_12(self):
        game, army1, army2 = _build_game()

        ignore_lone_operative_ability = [
            {
                "name": "Ghosthunter Scope",
                "description": (
                    "Each time this model makes a ranged attack, when selecting targets for that attack, "
                    "you can ignore the Lone Operative ability."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        lone_operative_ability = [
            {
                "name": "Lone Operative",
                "description": "Lone Operative.",
                "type": "Datasheet",
                "parameter": "",
            }
        ]

        attacker_plain = _make_unit("Attacker Plain")
        attacker_ignore = _make_unit("Attacker Ignore", abilities=ignore_lone_operative_ability)
        target_unit = _make_unit("Target", abilities=lone_operative_ability)

        army1.add_unit(attacker_plain)
        army1.add_unit(attacker_ignore)
        army2.add_unit(target_unit)

        attacker_plain.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        attacker_ignore.models[0].set_location(0.0, 2.0, 0.0, 0.0)
        target_unit.models[0].set_location(15.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker_plain, attacker_ignore, target_unit]

        profile = _make_ranged_profile()

        can_target_plain = attacker_plain._can_model_shoot_weapon_at_target(
            attacker_plain.models[0],
            profile,
            target_unit,
            game.map,
        )
        self.assertFalse(can_target_plain)

        can_target_ignore = attacker_ignore._can_model_shoot_weapon_at_target(
            attacker_ignore.models[0],
            profile,
            target_unit,
            game.map,
        )
        self.assertTrue(can_target_ignore)

    def test_ignore_lone_operative_still_applies_other_ranged_targeting_caps(self):
        game, army1, army2 = _build_game()

        ignore_lone_operative_ability = [
            {
                "name": "Ghosthunter Scope",
                "description": (
                    "Each time this model makes a ranged attack, when selecting targets for that attack, "
                    "you can ignore the Lone Operative ability."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        target_abilities = [
            {
                "name": "Lone Operative",
                "description": "Lone Operative.",
                "type": "Datasheet",
                "parameter": "",
            },
            {
                "name": "Camouflage Field",
                "description": (
                    "This unit can only be selected as the target of a ranged attack if the attacking model is within 18\"."
                ),
                "type": "Datasheet",
                "parameter": "",
            },
        ]

        attacker = _make_unit("Attacker Ignore", abilities=ignore_lone_operative_ability)
        target_unit = _make_unit("Target", abilities=target_abilities)

        army1.add_unit(attacker)
        army2.add_unit(target_unit)

        attacker.models[0].set_location(15.0, 0.0, 0.0, 0.0)
        target_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target_unit]

        profile = _make_ranged_profile()

        can_target_within_18 = attacker._can_model_shoot_weapon_at_target(
            attacker.models[0],
            profile,
            target_unit,
            game.map,
        )
        self.assertTrue(can_target_within_18)

        attacker.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        can_target_beyond_18 = attacker._can_model_shoot_weapon_at_target(
            attacker.models[0],
            profile,
            target_unit,
            game.map,
        )
        self.assertFalse(can_target_beyond_18)


if __name__ == "__main__":
    unittest.main()
