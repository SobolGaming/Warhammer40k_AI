import unittest
from types import SimpleNamespace


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
        self.faction_data = {"name": "Leagues of Votann"}
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

    army1 = Army.with_detachment("Leagues of Votann", detachment_type="Detachment1")
    army1.faction_id = "LOV"
    army2 = Army.with_detachment("Enemy", detachment_type="Detachment2")
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


class TestVotannBatch1Abilities(unittest.TestCase):
    def test_brokhyr_guild_support_conditional_lone_operative(self):
        game, army1, _army2 = _build_game()
        ability = [
            {
                "name": "Brôkhyr Guild Support",
                "description": (
                    "While this unit is within 3\" of one or more friendly Leagues of Votann Vehicle or "
                    "Ironkin Steeljacks units, if this unit is not an Attached unit, it has the Lone Operative ability."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        hero = _make_unit(
            "Brôkhyr Iron-master",
            abilities=ability,
            keywords=["INFANTRY"],
            faction_keywords=["LEAGUES OF VOTANN"],
        )
        vehicle = _make_unit(
            "Sagitaur",
            keywords=["VEHICLE"],
            faction_keywords=["LEAGUES OF VOTANN"],
        )
        army1.add_unit(hero)
        army1.add_unit(vehicle)
        hero.deployed = True
        vehicle.deployed = True
        hero.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        vehicle.models[0].set_location(2.0, 0.0, 0.0, 0.0)
        game.map.units = [hero, vehicle]

        self.assertTrue(hero.has_lone_operative())

        vehicle.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        self.assertFalse(hero.has_lone_operative())

        hero.attached_to = object()
        vehicle.models[0].set_location(2.0, 0.0, 0.0, 0.0)
        self.assertFalse(hero.has_lone_operative())

    def test_science_guild_support_excludes_lone_operative_units(self):
        game, army1, _army2 = _build_game()
        science_ability = [
            {
                "name": "Science Guild Support",
                "description": (
                    "While this model is within 3\" of one or more other friendly Leagues of Votann Infantry units "
                    "(excluding units with the Lone Operative ability), this model has the Lone Operative ability."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        lone_operative_ability = [
            {
                "name": "Lone Operative",
                "description": (
                    "Unless part of an Attached unit, this unit can only be selected as the target of a ranged "
                    "attack if the attacking model is within 12\"."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        evaluator = _make_unit(
            "Arkanyst Evaluator",
            abilities=science_ability,
            keywords=["INFANTRY"],
            faction_keywords=["LEAGUES OF VOTANN"],
        )
        lo_support = _make_unit(
            "LO Support",
            abilities=lone_operative_ability,
            keywords=["INFANTRY"],
            faction_keywords=["LEAGUES OF VOTANN"],
        )
        regular_support = _make_unit(
            "Regular Support",
            keywords=["INFANTRY"],
            faction_keywords=["LEAGUES OF VOTANN"],
        )
        army1.add_unit(evaluator)
        army1.add_unit(lo_support)
        army1.add_unit(regular_support)
        evaluator.deployed = True
        lo_support.deployed = True
        regular_support.deployed = True
        evaluator.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        lo_support.models[0].set_location(2.0, 0.0, 0.0, 0.0)
        regular_support.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [evaluator, lo_support, regular_support]

        self.assertFalse(evaluator.has_lone_operative())

        regular_support.models[0].set_location(2.0, 0.0, 0.0, 0.0)
        self.assertTrue(evaluator.has_lone_operative())

    def test_decisive_destruction_rerolls_hit_one_only_for_closest_target(self):
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.units import wargear as wargear_mod

        ability = {
            "name": "Decisive Destruction",
            "description": (
                "Each time a model in this unit makes a ranged attack that targets the closest eligible target, "
                "re-roll a Hit roll of 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        attacker = _make_unit("Einhyr Hearthguard", abilities=[ability])
        close_target = _make_unit("Close Target")
        far_target = _make_unit("Far Target")
        army1.add_unit(attacker)
        army2.add_unit(close_target)
        army2.add_unit(far_target)

        attacker.deployed = True
        close_target.deployed = True
        far_target.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        close_target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        far_target.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, close_target, far_target]

        parent = SimpleNamespace(name="Einhyr Weapon", is_melee=lambda: False, is_ranged=lambda: True)
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

        rolls = iter([1, 6, 6, 6, 6])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls, 6)
        try:
            result = profile.attack(close_target, attacker.models[0], game_map=game.map)
        finally:
            wargear_mod.get_roll = original_roll
        self.assertIsNotNone(result.hit_results[0].get("reroll"))
        self.assertEqual(int(result.hit_results[0].get("reroll_of_one", 0)), 1)

        rolls = iter([1, 6, 6, 6, 6])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls, 6)
        try:
            result = profile.attack(far_target, attacker.models[0], game_map=game.map)
        finally:
            wargear_mod.get_roll = original_roll
        self.assertIsNone(result.hit_results[0].get("reroll"))

    def test_panspectral_scanner_bearer_unit_hit_reroll_ones(self):
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.units import wargear as wargear_mod

        ability = {
            "name": "Panspectral Scanner",
            "description": "Each time a model in the bearer's unit makes a ranged attack, re-roll a Hit roll of 1.",
            "type": "Wargear",
            "parameter": "",
        }
        attacker = _make_unit("Hernkyn Pioneers", abilities=[ability])
        attacker.models[0].optional_wargear.append("Panspectral Scanner")
        target = _make_unit("Target")

        parent = SimpleNamespace(name="Mag Rifle", is_melee=lambda: False, is_ranged=lambda: True)
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

        rolls = iter([1, 5])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            hit = profile._hit_target_with_tracking(target, attacker.models[0], {"_aura_attack_mods": _aura_stub()})
        finally:
            wargear_mod.get_roll = original_roll

        self.assertEqual(int(hit["roll"]), 5)
        self.assertEqual(int(hit.get("reroll_of_one", 0)), 1)

    def test_rollbar_searchlight_ignores_hit_modifiers(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Rollbar Searchlight",
            "description": (
                "Each time a model in the bearer's unit makes a ranged attack, "
                "you can ignore any or all modifiers to the Hit roll."
            ),
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Hernkyn Pioneers", abilities=[ability])
        unit.models[0].optional_wargear.append("Rollbar Searchlight")
        attacker_model = unit.models[0]

        profile = WargearProfile(
            profile_name="default",
            wargear_data={
                "range": "24",
                "A": "2",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
        )
        rule = profile._ignore_hit_modifier_rule(attacker_model)
        self.assertIsNotNone(rule)
        self.assertTrue(rule.get("allow_hit"))
        self.assertEqual(rule.get("attack_type"), "ranged")
        self.assertEqual(set(rule.get("skill_kinds") or ()), set())

    def test_destabilising_quakes_weapon_specific_battleshock_penalty(self):
        ability = {
            "name": "Destabilising Quakes",
            "description": (
                "In your Shooting phase, after this unit has shot, select one enemy unit hit by one or more of those "
                "attacks made with its tremor shells. That unit must take a Battle-shock test, subtracting 1 from the result."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Cthonian Earthshakers", abilities=[ability])
        specs = unit.unit_post_shoot_battleshock_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("test_modifier", 0)), -1)

    def test_scanner_uplinks_parses_suppression_with_exclusion(self):
        ability = {
            "name": "Scanner Uplinks",
            "description": (
                "In your Shooting phase, after this model has shot, select one enemy unit (excluding MONSTERS and VEHICLES) "
                "hit by one or more of those attacks. Until the start of your next turn, that enemy unit is suppressed. "
                "While a unit is suppressed, each time a model in that unit makes an attack, subtract 1 from the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Kapricus Carrier", abilities=[ability])
        specs = unit.unit_post_shoot_suppression_specs()
        self.assertEqual(len(specs), 1)
        self.assertTrue(bool(specs[0].get("exclude_monster_vehicle")))

    def test_grimnyrs_regard_parses_start_any_phase_clear_battleshock(self):
        ability = {
            "name": "Grimnyr's Regard",
            "description": (
                "Once per battle, at the start of any phase, you can select one friendly Leagues of Votann unit that is "
                "Battle-shocked and within 12\" of this unit's GRIMNYR model. That unit is no longer Battle-shocked."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Grimnyr", abilities=[ability], faction_keywords=["LEAGUES OF VOTANN"])
        specs = unit.unit_start_any_phase_clear_battleshock_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("range", 0)), 12)
        self.assertEqual(str(specs[0].get("model_name", "")).strip().lower(), "grimnyr")

    def test_luck_has_need_keeps_toil_earns_sets_sticky_objectives(self):
        ability = {
            "name": "Luck Has. Need Keeps. Toil Earns",
            "description": (
                "At the end of your Command phase, if this unit is within range of an objective marker you control, "
                "that objective marker remains under your control until your opponent's Level of Control over that "
                "objective marker is greater than yours at the end of a phase."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Hearthkyn Warriors", abilities=[ability])
        self.assertTrue(bool(unit.special_rules.get("sticky_objectives")))

    def test_predictive_guidance_parses_zero_cp_overwatch_or_heroic(self):
        ability = {
            "name": "Predictive Guidance",
            "description": (
                "Once per battle round, this model can use this ability. If it does, you can target this unit with "
                "the Fire Overwatch or Heroic Intervention Stratagem for 0CP."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Memnyr Strategist", abilities=[ability])
        rule = unit.get_prophetic_sentinels_stratagem_discount_rule()
        self.assertIsNotNone(rule)
        allowed = {str(v).upper() for v in tuple(rule.get("stratagems", ()) or ())}
        self.assertIn("OVERWATCH", allowed)
        self.assertIn("HEROIC INTERVENTION", allowed)


if __name__ == "__main__":
    unittest.main()
