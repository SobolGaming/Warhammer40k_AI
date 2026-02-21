import unittest
from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Necrons"}
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
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Necrons", "Det")
    army1.faction_id = "NEC"
    army2 = Army("Enemy", "Det")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


class TestNecronsDatasheetGroup1Abilities(unittest.TestCase):
    def test_chronometron_parses_post_shoot_reactive_move(self):
        ability = {
            "name": "Chronometron",
            "description": (
                "In your Shooting phase, after this model's unit has shot, if it is not within Engagement Range of any enemy "
                "units, that unit can make a Normal move of up to 5\" as if it were your Movement phase. If it does, until "
                "the end of the turn, that unit is not eligible to declare a charge."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Chronomancer", abilities=[ability])
        specs = unit.unit_post_shoot_reactive_move_no_charge_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("range", 0)), 5)
        self.assertTrue(bool(specs[0].get("requires_not_engaged", False)))

    def test_evasion_engrams_parses_post_shoot_reactive_move(self):
        ability = {
            "name": "Evasion Engrams",
            "description": (
                "In your Shooting phase, after this unit has shot, it can make a Normal move of up to 6\". If it does, until "
                "the end of the turn, this unit is not eligible to declare a charge."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Tomb Blades", abilities=[ability])
        specs = unit.unit_post_shoot_reactive_move_no_charge_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("range", 0)), 6)
        self.assertFalse(bool(specs[0].get("requires_not_engaged", True)))

    def test_targeting_relay_parses_post_shoot_no_cover(self):
        ability = {
            "name": "Targeting Relay",
            "description": (
                "In your Shooting phase, each time this model is selected to shoot, after resolving its attacks, select one "
                "enemy unit that was hit by one or more of those attacks. Until the end of the phase, that unit cannot have "
                "the Benefit of Cover."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Triarch Stalker", abilities=[ability])
        specs = unit.unit_post_shoot_no_cover_specs()
        self.assertEqual(len(specs), 1)
        self.assertTrue(bool(specs[0].get("any_weapon", False)))
        self.assertEqual(str(specs[0].get("duration", "")), "phase_end")

    def test_implacable_eradication_grants_full_wound_reroll_on_objective_target(self):
        ability = {
            "name": "Implacable Eradication",
            "description": (
                "Each time a model in this unit makes an attack, re-roll a Wound roll of 1. If the target of that attack is "
                "an enemy unit within range of an objective marker, you can re-roll the Wound roll instead."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()
        attacker = _make_unit("Immortals", abilities=[ability])
        target = _make_unit("Enemy")
        army1.add_unit(attacker)
        army2.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target]
        game.map.add_objective(
            Objective(
                name="Obj",
                category=ObjectiveCategory.PRIMARY,
                points=0,
                description="",
                conditions=lambda _g: False,
                location=ObjectivePoint(10.0, 0.0, 0.0, control_radius=3.0),
            )
        )

        mods = attacker.get_unit_wound_reroll_modifiers("ranged", target=target)
        self.assertIn(1, tuple(mods.get("reroll_wound_values", ())))
        self.assertTrue(bool(mods.get("reroll_wound_full", False)))

    def test_hard_wired_for_destruction_full_reroll_only_on_enemy_controlled_objective(self):
        from warhammer40k_ai.units import wargear as wargear_mod
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Hard-wired for Destruction",
            "description": (
                "Each time a model in this unit makes a ranged attack that targets the closest eligible enemy unit, re-roll "
                "a Hit roll of 1. If the target of that attack is within range of an objective marker your opponent controls, "
                "you can re-roll the Hit roll instead."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, p2 = _build_game()
        attacker = _make_unit("Lokhust Destroyers", abilities=[ability])
        target = _make_unit("Target")
        other = _make_unit("Other Target")
        army1.add_unit(attacker)
        army2.add_unit(target)
        army2.add_unit(other)

        attacker.deployed = True
        target.deployed = True
        other.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        other.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target, other]

        objective = Objective(
            name="Obj",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=ObjectivePoint(10.0, 0.0, 0.0, control_radius=3.0),
        )
        objective.location.controlling_player = p2
        game.map.add_objective(objective)

        parent = SimpleNamespace(name="Gauss", is_melee=lambda: False, is_ranged=lambda: True)
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

        rolls = iter([2, 6, 6, 6, 6])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls, 6)
        try:
            result = profile.attack(target, attacker.models[0], game_map=game.map)
        finally:
            wargear_mod.get_roll = original_roll
        self.assertIsNotNone(result.hit_results[0].get("reroll"))

        objective.location.controlling_player = p1
        rolls = iter([2, 6, 6, 6, 6])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls, 6)
        try:
            result = profile.attack(target, attacker.models[0], game_map=game.map)
        finally:
            wargear_mod.get_roll = original_roll
        self.assertIsNone(result.hit_results[0].get("reroll"))

    def test_driven_by_hatred_full_hit_and_wound_rerolls_vs_below_half(self):
        ability = {
            "name": "Driven by Hatred",
            "description": (
                "Each time this model makes an attack that targets an enemy unit that is Below Half-strength, you can "
                "re-roll the Hit roll and you can re-roll the Wound roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Lokhust Lord", abilities=[ability])
        model = attacker.models[0]
        target = _make_unit("Enemy")
        target.is_below_half_strength = lambda: True
        target.is_below_starting_strength = lambda: True

        hit_mods = attacker.get_model_hit_reroll_modifiers(model=model, target=target)
        wound_mods = attacker.get_model_wound_reroll_modifiers(model=model, target=target)
        self.assertTrue(bool(hit_mods.get("reroll_hit_full", False)))
        self.assertTrue(bool(wound_mods.get("reroll_wound_full", False)))

        target.is_below_half_strength = lambda: False
        target.is_below_starting_strength = lambda: False
        hit_mods = attacker.get_model_hit_reroll_modifiers(model=model, target=target)
        wound_mods = attacker.get_model_wound_reroll_modifiers(model=model, target=target)
        self.assertFalse(bool(hit_mods.get("reroll_hit_full", False)))
        self.assertFalse(bool(wound_mods.get("reroll_wound_full", False)))

    def test_whirling_onslaught_charge_upgrades_to_full_hit_reroll(self):
        ability = {
            "name": "Whirling Onslaught",
            "description": (
                "Each time a model in this unit makes a melee attack, re-roll a Hit roll of 1. If this unit made a Charge "
                "move this turn, you can re-roll the Hit roll instead."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Skorpekh Destroyers", abilities=[ability])
        target = _make_unit("Enemy")

        attacker.round_state.charged_this_round = False
        mods = attacker.get_unit_hit_reroll_modifiers("melee", target=target)
        self.assertIn(1, tuple(mods.get("reroll_hit_values", ())))
        self.assertFalse(bool(mods.get("reroll_hit_full", False)))

        attacker.round_state.charged_this_round = True
        mods = attacker.get_unit_hit_reroll_modifiers("melee", target=target)
        self.assertTrue(bool(mods.get("reroll_hit_full", False)))

    def test_sentinel_construct_overwatch_threshold(self):
        ability = {
            "name": "Sentinel Construct",
            "description": (
                "Each time you target this unit with the Fire Overwatch Stratagem, while resolving that Stratagem, "
                "hits are scored on unmodified Hit rolls of 5+."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()
        unit = _make_unit("Canoptek Doomstalker", abilities=[ability])
        enemy = _make_unit("Enemy")
        army1.add_unit(unit)
        army2.add_unit(enemy)
        unit.deployed = True
        enemy.deployed = True
        self.assertEqual(unit.get_destroyer_of_futures_overwatch_hit_threshold(enemy_unit=enemy, game=game), 5)


if __name__ == "__main__":
    unittest.main()
