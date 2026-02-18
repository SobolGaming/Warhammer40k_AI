import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_name="Test Faction"):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
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


def _make_unit(name, *, abilities=None, keywords=None, faction_name="Test Faction"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities, keywords=keywords, faction_name=faction_name)
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Attackers", detachment_type="Detachment1")
    army1.faction_id = "ATK"
    army2 = Army("Defenders", detachment_type="Detachment2")
    army2.faction_id = "DEF"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2


class TestModelHitBonusClosestEligibleTarget(unittest.TestCase):
    def test_model_ranged_hit_bonus_applies_vs_closest_eligible_target(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Aggressive Assault",
            "description": "Each time this model makes a ranged attack that targets the closest eligible target, add 1 to the Hit roll.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        attacker = _make_unit("Attacker", abilities=[ability], faction_name="Imperial Knights")
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

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            result = profile.attack(close_target, attacker.models[0], game_map=game.map)

        hit = result.hit_results[0]
        self.assertTrue(hit["hit"])
        self.assertEqual(int(hit.get("final_needed", 0)), 2)
        self.assertIn("+1 to hit from Aggressive Assault", hit.get("modifiers", []))

    def test_model_ranged_hit_bonus_not_applied_vs_non_closest_target(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Aggressive Assault",
            "description": "Each time this model makes a ranged attack that targets the closest eligible target, add 1 to the Hit roll.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        attacker = _make_unit("Attacker", abilities=[ability], faction_name="Imperial Knights")
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

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            result = profile.attack(far_target, attacker.models[0], game_map=game.map)

        hit = result.hit_results[0]
        self.assertFalse(hit["hit"])
        self.assertEqual(int(hit.get("final_needed", 0)), 3)
        self.assertNotIn("+1 to hit from Aggressive Assault", hit.get("modifiers", []))

    def test_model_ranged_ap_bonus_applies_vs_closest_eligible_target(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Seasoned Noble",
            "description": (
                "Each time this model makes a ranged attack that targets the closest eligible target, "
                "improve the Armour Penetration characteristic of that attack by 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        attacker = _make_unit("Attacker", abilities=[ability], faction_name="Imperial Knights")
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

        self.assertEqual(profile.get_effective_ap(attacker.models[0], close_target), -1)

    def test_model_ranged_ap_bonus_not_applied_vs_non_closest_target(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Seasoned Noble",
            "description": (
                "Each time this model makes a ranged attack that targets the closest eligible target, "
                "improve the Armour Penetration characteristic of that attack by 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        attacker = _make_unit("Attacker", abilities=[ability], faction_name="Imperial Knights")
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

        self.assertEqual(profile.get_effective_ap(attacker.models[0], far_target), 0)

    def test_model_stationary_ranged_sustained_hits_applies_when_stationary_on_own_turn(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Punishing Salvoes",
            "description": (
                "In your Movement phase, if this model Remains Stationary, until the end of the turn, "
                "ranged weapons equipped by this model have the [SUSTAINED HITS 1] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        attacker = _make_unit("Attacker", abilities=[ability], faction_name="Imperial Knights")
        target = _make_unit("Target")
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.deployed = True
        target.deployed = True
        game.map.units = [attacker, target]
        game.current_player_index = 0
        attacker.round_state.remained_stationary_this_round = True

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
        attack_instance = {"_aura_attack_mods": SimpleNamespace(hit=0, hit_reasons=())}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            hit_result = profile._hit_target_with_tracking(target, attacker.models[0], attack_instance)

        self.assertTrue(bool(hit_result.get("hit")))
        self.assertEqual(int(attack_instance.get("sustained_hit", 0) or 0), 1)

    def test_model_stationary_ranged_sustained_hits_not_applied_when_not_stationary(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Punishing Salvoes",
            "description": (
                "In your Movement phase, if this model Remains Stationary, until the end of the turn, "
                "ranged weapons equipped by this model have the [SUSTAINED HITS 1] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        attacker = _make_unit("Attacker", abilities=[ability], faction_name="Imperial Knights")
        target = _make_unit("Target")
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.deployed = True
        target.deployed = True
        game.map.units = [attacker, target]
        game.current_player_index = 0
        attacker.round_state.remained_stationary_this_round = False

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
        attack_instance = {"_aura_attack_mods": SimpleNamespace(hit=0, hit_reasons=())}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            profile._hit_target_with_tracking(target, attacker.models[0], attack_instance)

        self.assertEqual(int(attack_instance.get("sustained_hit", 0) or 0), 0)

    def test_model_stationary_ranged_sustained_hits_not_applied_on_opponent_turn(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Punishing Salvoes",
            "description": (
                "In your Movement phase, if this model Remains Stationary, until the end of the turn, "
                "ranged weapons equipped by this model have the [SUSTAINED HITS 1] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        attacker = _make_unit("Attacker", abilities=[ability], faction_name="Imperial Knights")
        target = _make_unit("Target")
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.deployed = True
        target.deployed = True
        game.map.units = [attacker, target]
        game.current_player_index = 1
        attacker.round_state.remained_stationary_this_round = True

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
        attack_instance = {"_aura_attack_mods": SimpleNamespace(hit=0, hit_reasons=())}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            profile._hit_target_with_tracking(target, attacker.models[0], attack_instance)

        self.assertEqual(int(attack_instance.get("sustained_hit", 0) or 0), 0)


if __name__ == "__main__":
    unittest.main()
