import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
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

    army1 = Army("Aeldari", "Warhost")
    army1.faction_id = "AE"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    return game, army1, army2


def _attach_leader(leader, bodyguard):
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    leader.can_be_attached_to = [bodyguard.name]


def _make_weapon(*, name: str, description: str):
    from warhammer40k_ai.units.wargear import Wargear

    data = {
        "range": "12",
        "A": "1",
        "BS_WS": "3+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": description,
        "type": "Ranged",
        "name": name,
    }
    weapon = Wargear(data)
    return weapon, weapon.profiles["default"]


class TestBurningLance(unittest.TestCase):
    def test_burning_lance_extends_melta_range_when_leading(self):
        ability = {
            "name": "Burning Lance",
            "description": (
                "While this model is leading a unit, add 6\" to the Range characteristic of Melta weapons "
                "equipped by models in that unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        target = _make_unit("Target")

        _attach_leader(leader, bodyguard)

        melta_weapon, melta_profile = _make_weapon(name="Melta Gun", description="Melta 2")
        bodyguard.models[0].wargear = [melta_weapon]

        game, army1, army2 = _build_game()
        army1.add_unit(bodyguard)
        army1.add_unit(leader)
        army2.add_unit(target)
        game.map.units = [bodyguard, leader, target]

        bodyguard.models[0].set_location(0, 0, 0, 0)
        target.models[0].set_location(19, 0, 0, 0)

        can_shoot = bodyguard._can_model_shoot_weapon_at_target(
            bodyguard.models[0],
            melta_profile,
            target,
            game.map,
        )
        self.assertTrue(can_shoot)

    def test_burning_lance_requires_leading(self):
        ability = {
            "name": "Burning Lance",
            "description": (
                "While this model is leading a unit, add 6\" to the Range characteristic of Melta weapons "
                "equipped by models in that unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        target = _make_unit("Target")

        melta_weapon, melta_profile = _make_weapon(name="Melta Gun", description="Melta 2")
        bodyguard.models[0].wargear = [melta_weapon]

        game, army1, army2 = _build_game()
        army1.add_unit(bodyguard)
        army1.add_unit(leader)
        army2.add_unit(target)
        game.map.units = [bodyguard, leader, target]

        bodyguard.models[0].set_location(0, 0, 0, 0)
        target.models[0].set_location(19, 0, 0, 0)

        can_shoot = bodyguard._can_model_shoot_weapon_at_target(
            bodyguard.models[0],
            melta_profile,
            target,
            game.map,
        )
        self.assertFalse(can_shoot)

    def test_burning_lance_does_not_extend_non_melta(self):
        ability = {
            "name": "Burning Lance",
            "description": (
                "While this model is leading a unit, add 6\" to the Range characteristic of Melta weapons "
                "equipped by models in that unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        target = _make_unit("Target")

        _attach_leader(leader, bodyguard)

        weapon, profile = _make_weapon(name="Rifle", description="Rapid Fire 1")
        bodyguard.models[0].wargear = [weapon]

        game, army1, army2 = _build_game()
        army1.add_unit(bodyguard)
        army1.add_unit(leader)
        army2.add_unit(target)
        game.map.units = [bodyguard, leader, target]

        bodyguard.models[0].set_location(0, 0, 0, 0)
        target.models[0].set_location(19, 0, 0, 0)

        can_shoot = bodyguard._can_model_shoot_weapon_at_target(
            bodyguard.models[0],
            profile,
            target,
            game.map,
        )
        self.assertFalse(can_shoot)


if __name__ == "__main__":
    unittest.main()
