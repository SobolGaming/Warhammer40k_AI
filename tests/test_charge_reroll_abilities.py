import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        ds_id="",
        abilities=None,
        attached_to=None,
    ):
        self.id = ds_id
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [{
            "M": "6",
            "T": "4",
            "Sv": "3",
            "W": "2",
            "Ld": "7",
            "OC": "1",
            "base_size": "32mm",
            "inv_sv": "7",
            "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = list(attached_to or [])


def _make_unit(name, *, ds_id="", abilities=None, attached_to=None):
    from warhammer40k_ai.classes.unit import Unit

    datasheet = _MockDatasheet(
        name,
        ds_id=ds_id,
        abilities=abilities,
        attached_to=attached_to,
    )
    return Unit(datasheet)


class TestChargeRerollAbilities(unittest.TestCase):
    def test_unit_reroll_charge_rolls(self):
        ability = {
            "name": "Relentless Combatants",
            "description": "You can re-roll Charge rolls made for this unit.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Lychguard", abilities=[ability])
        self.assertTrue(unit.can_reroll_charge_roll())

    def test_leading_reroll_charge_rolls_requires_attachment(self):
        from warhammer40k_ai.classes.unit import Unit

        ability = {
            "name": "Zealous Path",
            "description": "While this model is leading a unit, you can re-roll Charge rolls made for that unit.",
            "type": "Datasheet",
            "parameter": "",
        }
        bodyguard = _make_unit("Bodyguard", ds_id="BG1")
        leader = _make_unit("Chaplain", ds_id="LD1", abilities=[ability], attached_to=["BG1"])

        class _Army:
            def __init__(self, units):
                self.units = list(units)
                self.player = None
                self.faction_id = "GK"

            def on_battle_round_start(self, *_a, **_k):
                return None

        army = _Army([bodyguard, leader])
        bodyguard.set_parent_army(army)
        leader.set_parent_army(army)

        self.assertFalse(bodyguard.can_reroll_charge_roll())

        leader.attach_to_unit(bodyguard)

        self.assertTrue(bodyguard.can_reroll_charge_roll())
        self.assertTrue(leader.is_attached_leader)

    def test_bearer_unit_reroll_from_attached_leader(self):
        ability = {
            "name": "Ravenwing Instincts",
            "description": "Ravenwing model only. You can re-roll Advance and Charge rolls made for the bearer's unit.",
            "type": "Datasheet",
            "parameter": "",
        }
        bodyguard = _make_unit("Bodyguard", ds_id="BG2")
        leader = _make_unit("Ravenwing Leader", ds_id="LD2", abilities=[ability], attached_to=["BG2"])

        class _Army:
            def __init__(self, units):
                self.units = list(units)
                self.player = None
                self.faction_id = "SM"

            def on_battle_round_start(self, *_a, **_k):
                return None

        army = _Army([bodyguard, leader])
        bodyguard.set_parent_army(army)
        leader.set_parent_army(army)

        self.assertFalse(bodyguard.can_reroll_advance_roll())
        self.assertFalse(bodyguard.can_reroll_charge_roll())

        leader.attach_to_unit(bodyguard)

        self.assertTrue(bodyguard.can_reroll_advance_roll())
        self.assertTrue(bodyguard.can_reroll_charge_roll())

    def test_charge_reroll_requires_setup_turn(self):
        ability = {
            "name": "Rapid Assault",
            "description": "Adeptus Astartes model only. You can re-roll Charge rolls made for the bearer's unit in a turn in which it was set up on the battlefield.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Assault", abilities=[ability])
        unit.deployed = True
        unit.arrived_from_reserves_this_turn = False
        self.assertFalse(unit.can_reroll_charge_roll())

        unit.arrived_from_reserves_this_turn = True
        self.assertTrue(unit.can_reroll_charge_roll())

    def test_charge_reroll_requires_objective_target(self):
        from types import SimpleNamespace

        ability = {
            "name": "Objective Hunter",
            "description": "Adeptus Astartes model only. Each time the bearer's unit declares a charge, if one or more targets of that charge are within range of an objective marker, you can re-roll the Charge roll.",
            "type": "Datasheet",
            "parameter": "",
        }
        charger = _make_unit("Charger", abilities=[ability])
        target = _make_unit("Target")
        charger.deployed = True
        target.deployed = True

        if charger.models:
            charger.models[0].set_location(0, 0, 0, 0)
        if target.models:
            target.models[0].set_location(0, 0, 0, 0)

        objective = SimpleNamespace(location=SimpleNamespace(x=0.0, y=0.0, control_radius=3.0))
        game_map = SimpleNamespace(objectives=[objective])

        self.assertTrue(charger.can_reroll_charge_roll(target_unit=target, game_map=game_map))

        if target.models:
            target.models[0].set_location(50, 50, 0, 0)
        self.assertFalse(charger.can_reroll_charge_roll(target_unit=target, game_map=game_map))

    def test_charge_reroll_requires_closest_eligible_target(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.classes.player import Player, PlayerType

        ability = {
            "name": "Surgical Advance",
            "description": (
                "Each time a model in this unit makes a ranged attack that targets the closest enemy unit, "
                "you can re-roll the Hit roll. Each time this unit declares a charge that targets the "
                "closest eligible enemy unit, you can re-roll the Charge roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        army1 = Army("Test", "Det")
        army1.faction_id = "TST"
        army2 = Army("Enemy", "Det")
        army2.faction_id = "EN"

        p1 = Player("P1", player_type=PlayerType.HUMAN, army=army1)
        p2 = Player("P2", player_type=PlayerType.AI, army=army2)
        game.add_player(p1)
        game.add_player(p2)

        charger = _make_unit("Charger", abilities=[ability])
        target_close = _make_unit("Target Close")
        target_far = _make_unit("Target Far")

        army1.add_unit(charger)
        army2.add_unit(target_close)
        army2.add_unit(target_far)

        charger.deployed = True
        target_close.deployed = True
        target_far.deployed = True

        charger.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target_close.models[0].set_location(8.0, 0.0, 0.0, 0.0)
        target_far.models[0].set_location(10.0, 0.0, 0.0, 0.0)

        self.assertTrue(
            charger.can_reroll_charge_roll(
                target_unit=target_close,
                game_map=game.map,
                game=game,
            )
        )
        self.assertFalse(
            charger.can_reroll_charge_roll(
                target_unit=target_far,
                game_map=game.map,
                game=game,
            )
        )


if __name__ == "__main__":
    unittest.main()
