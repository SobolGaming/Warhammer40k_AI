import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers, get_aura_strength_bonus


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


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
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
    return game, army1, army2


def _deploy_pair(game, army1, army2, friendly, enemy, *, friendly_xy=(0.0, 0.0), enemy_xy=(12.0, 0.0)):
    army1.add_unit(friendly)
    army2.add_unit(enemy)
    friendly.deployed = True
    enemy.deployed = True
    friendly.models[0].set_location(float(friendly_xy[0]), float(friendly_xy[1]), 0.0, 0.0)
    enemy.models[0].set_location(float(enemy_xy[0]), float(enemy_xy[1]), 0.0, 0.0)
    game.map.units = [friendly, enemy]


class TestNecronsDatasheetGroup4Abilities(unittest.TestCase):
    def test_fabricator_claw_array_aura_grants_vehicle_fnp(self):
        ability = {
            "name": "Fabricator Claw Array (Aura)",
            "description": (
                "While a friendly Necrons Vehicle unit is within 6\" of the bearer, "
                "that unit has the Feel No Pain 6+ ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("Canoptek Spyders", abilities=[ability], keywords=["NECRONS"])
        vehicle = _make_unit("Vehicle", keywords=["NECRONS", "VEHICLE"])
        enemy = _make_unit("Enemy")

        army1.add_unit(source)
        army1.add_unit(vehicle)
        army2.add_unit(enemy)
        source.deployed = True
        vehicle.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        vehicle.models[0].set_location(5.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(30.0, 0.0, 0.0, 0.0)
        game.map.units = [source, vehicle, enemy]

        fnp = list(vehicle.has_feel_no_pain())
        self.assertTrue(any(int(v) == 6 for v, _c in fnp))

    def test_gloom_prism_aura_grants_conditional_fnp(self):
        ability = {
            "name": "Gloom Prism (Aura)",
            "description": (
                "While a friendly NECRONS unit is within 6\" of the bearer, models in that unit have the "
                "Feel No Pain 5+ ability against mortal wounds and Psychic Attacks."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("Canoptek Spyders", abilities=[ability], keywords=["NECRONS"])
        target = _make_unit("Necron Unit", keywords=["NECRONS", "INFANTRY"])
        enemy = _make_unit("Enemy")

        army1.add_unit(source)
        army1.add_unit(target)
        army2.add_unit(enemy)
        source.deployed = True
        target.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(5.5, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target, enemy]

        fnp = list(target.has_feel_no_pain())
        self.assertTrue(any(int(v) == 5 and "mortal" in str(c or "").lower() for v, c in fnp))

    def test_nullstone_field_generator_aura_grants_conditional_fnp(self):
        ability = {
            "name": "Nullstone Field Generator (Aura)",
            "description": (
                "While a friendly NECRONS unit is within 6\" of the bearer, models in that unit have the "
                "Feel No Pain 5+ ability against mortal wounds and Psychic Attacks."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("Nekrosor", abilities=[ability], keywords=["NECRONS"])
        target = _make_unit("Necron Unit", keywords=["NECRONS", "INFANTRY"])
        enemy = _make_unit("Enemy")

        army1.add_unit(source)
        army1.add_unit(target)
        army2.add_unit(enemy)
        source.deployed = True
        target.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(5.5, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target, enemy]

        fnp = list(target.has_feel_no_pain())
        self.assertTrue(any(int(v) == 5 and "psychic" in str(c or "").lower() for v, c in fnp))

    def test_reanimation_nodes_aura_grants_infantry_fnp(self):
        ability = {
            "name": "Reanimation Nodes (Aura)",
            "description": (
                "While a friendly Necrons Infantry unit is within 6\" of this Fortification, "
                "models in that unit have Feel No Pain 6+ ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("Convergence Of Dominion", abilities=[ability], keywords=["NECRONS", "FORTIFICATION"])
        target = _make_unit("Infantry", keywords=["NECRONS", "INFANTRY"])
        enemy = _make_unit("Enemy")

        army1.add_unit(source)
        army1.add_unit(target)
        army2.add_unit(enemy)
        source.deployed = True
        target.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(4.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(22.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target, enemy]

        fnp = list(target.has_feel_no_pain())
        self.assertTrue(any(int(v) == 6 for v, _c in fnp))

    def test_ancient_cover_registers_fortification_cover_rule(self):
        ability = {
            "name": "Ancient Cover",
            "description": (
                "Each time a ranged attack is allocated to a model, if that model is not fully visible to every model "
                "in the attacking unit because of this FORTIFICATION, that model has the Benefit of Cover against that attack."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        source = _make_unit("Convergence Of Dominion", abilities=[ability], keywords=["NECRONS", "FORTIFICATION"])
        rule = source.get_fortification_cover_rule()

        self.assertIsNotNone(rule)
        self.assertEqual("Ancient Cover", rule.get("source"))

    def test_relentless_march_adds_move_within_szarekh_aura(self):
        ability = {
            "name": "Relentless March (Aura)",
            "description": (
                "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, "
                "add 2\" to the Move characteristic of models in that unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("The Silent King", abilities=[ability], keywords=["NECRONS"])
        source.models[0].name = "Szarekh"
        target = _make_unit("Necron Unit", keywords=["NECRONS"])
        enemy = _make_unit("Enemy")

        army1.add_unit(source)
        army1.add_unit(target)
        army2.add_unit(enemy)
        source.deployed = True
        target.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(5.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target, enemy]

        effective_move = target.get_effective_model_characteristic(target.models[0], "movement", game_map=game.map)
        self.assertEqual(int(effective_move), 8)

    def test_the_silent_king_improves_leadership_within_szarekh_aura(self):
        ability = {
            "name": "The Silent King",
            "description": (
                "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, "
                "improve that unit's Leadership characteristic by 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("The Silent King", abilities=[ability], keywords=["NECRONS"])
        source.models[0].name = "Szarekh"
        target = _make_unit("Necron Unit", keywords=["NECRONS"])
        enemy = _make_unit("Enemy")

        army1.add_unit(source)
        army1.add_unit(target)
        army2.add_unit(enemy)
        source.deployed = True
        target.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(5.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target, enemy]

        effective_ld = target.get_effective_model_characteristic(target.models[0], "leadership", game_map=game.map)
        self.assertEqual(int(effective_ld), 6)

    def test_phaeron_of_the_stars_grants_hit_and_wound_reroll_ones(self):
        ability = {
            "name": "Phaeron of the Stars (Aura)",
            "description": (
                "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, each time a model in that "
                "unit makes an attack, re-roll a Hit roll of 1 and re-roll a Wound roll of 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("The Silent King", abilities=[ability], keywords=["NECRONS"])
        source.models[0].name = "Szarekh"
        attacker = _make_unit("Attacker", keywords=["NECRONS"])
        enemy = _make_unit("Enemy")
        _deploy_pair(game, army1, army2, attacker, enemy, friendly_xy=(4.0, 0.0), enemy_xy=(12.0, 0.0))
        army1.add_unit(source)
        source.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        game.map.units = [source, attacker, enemy]

        ranged_parent = SimpleNamespace(is_melee=lambda: False, is_ranged=lambda: True)
        profile = SimpleNamespace(parent_wargear=ranged_parent)
        mods = get_aura_attack_modifiers(attacker, enemy, profile, game_map=game.map)
        self.assertTrue(bool(mods.reroll_hit_ones))
        self.assertTrue(bool(mods.reroll_wound_ones))

    def test_phaeron_of_the_blades_grants_melee_strength_and_charge_reroll(self):
        ability = {
            "name": "Phaeron of the Blades (Aura)",
            "description": (
                "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, you can re-roll Charge rolls "
                "made for that unit and each time a model in that unit makes a melee attack, add 1 to the Strength "
                "characteristic of that attack."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("The Silent King", abilities=[ability], keywords=["NECRONS"])
        source.models[0].name = "Szarekh"
        attacker = _make_unit("Attacker", keywords=["NECRONS"])
        enemy = _make_unit("Enemy")

        _deploy_pair(game, army1, army2, attacker, enemy, friendly_xy=(5.0, 0.0), enemy_xy=(12.0, 0.0))
        army1.add_unit(source)
        source.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        game.map.units = [source, attacker, enemy]

        melee_parent = SimpleNamespace(is_melee=lambda: True, is_ranged=lambda: False)
        profile = SimpleNamespace(parent_wargear=melee_parent)
        strength_bonus, _reasons = get_aura_strength_bonus(attacker, profile, game_map=game.map)
        self.assertEqual(int(strength_bonus), 1)
        self.assertTrue(bool(attacker.can_reroll_charge_roll(game_map=game.map)))


if __name__ == "__main__":
    unittest.main()
