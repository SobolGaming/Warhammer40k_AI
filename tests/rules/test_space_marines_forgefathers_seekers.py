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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Forgefather's Seekers"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1

    army_sm = Army.with_detachment("Space Marines", detachment_type)
    army_sm.faction_id = "SM"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army_sm)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)

    return game, army_sm, army_enemy


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
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesForgefathersSeekers(unittest.TestCase):
    def test_vulkans_quest_counts_ranged_weapons_as_assault_for_shoot_after_advance(self):
        _game, army_sm, _army_enemy = _build_game("Forgefather's Seekers")
        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(attacker)

        profile = _make_ranged_profile()
        self.assertTrue(attacker.can_shoot_after_advance(profile))

    def test_vulkans_quest_strength_bonus_within_12_only(self):
        _game, army_sm, army_enemy = _build_game("Forgefather's Seekers")
        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=4)
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        profile = _make_ranged_profile()

        within_result = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 10.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Vulkan's Quest" in m for m in list(within_result.get("modifiers", []) or [])))

        outside_result = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 13.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Vulkan's Quest" in m for m in list(outside_result.get("modifiers", []) or [])))

    def test_seekers_companions_allows_infernus_to_start_action_after_advance_with_vulkan(self):
        game, army_sm, _army_enemy = _build_game("Forgefather's Seekers")
        infernus = _make_unit(
            "Infernus Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        vulkan = _make_unit(
            "Vulkan He'stan",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES", "SALAMANDERS"],
        )
        infernus.deployed = True
        vulkan.deployed = True
        army_sm.add_unit(infernus)
        army_sm.add_unit(vulkan)

        infernus.round_state.advanced_this_round = True
        check = game._is_unit_eligible_to_start_action(infernus)
        self.assertTrue(check["valid"])

    def test_seekers_companions_does_not_allow_infernus_action_after_advance_without_vulkan(self):
        game, army_sm, _army_enemy = _build_game("Forgefather's Seekers")
        infernus = _make_unit(
            "Infernus Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        infernus.deployed = True
        army_sm.add_unit(infernus)

        infernus.round_state.advanced_this_round = True
        check = game._is_unit_eligible_to_start_action(infernus)
        self.assertFalse(check["valid"])
        self.assertIn("advanced", str(check.get("reason", "")).lower())

    def test_seekers_companions_allows_shooting_while_performing_action(self):
        game, army_sm, army_enemy = _build_game("Forgefather's Seekers")
        infernus = _make_unit(
            "Infernus Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        vulkan = _make_unit(
            "Vulkan He'stan",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES", "SALAMANDERS"],
        )
        target = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        infernus.deployed = True
        vulkan.deployed = True
        target.deployed = True
        army_sm.add_unit(infernus)
        army_sm.add_unit(vulkan)
        army_enemy.add_unit(target)
        game.rebuild_entity_registry()

        infernus.round_state.action_locked_until_turn_end = True
        infernus.round_state.performing_action_name = "Investigate Signals"
        infernus.round_state.action_started_turn = game.turn
        infernus.round_state.shot_this_round = False

        infernus.validate_ctan_power_selection = lambda *_args, **_kwargs: (True, "")
        infernus._validate_shooting_declaration = (
            lambda *_args, **_kwargs: {"valid": False, "reason": "intentional no-op for unit test"}
        )

        profile = _make_ranged_profile()
        result = infernus.execute_shooting_declarations(
            [
                {
                    "weapon_profile": profile,
                    "target_unit": target,
                    "models": [infernus.models[0]],
                }
            ],
            game.map,
        )

        self.assertFalse(result)
        self.assertTrue(infernus.round_state.shot_this_round)


if __name__ == "__main__":
    unittest.main()
