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


def _build_game(detachment_type: str = "Liberator Assault Group"):
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

    return game, p1, army_sm, army_enemy


def _make_melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Astartes Chainsword", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesLiberatorAssaultGroup(unittest.TestCase):
    def test_red_thirst_applies_attacks_and_strength_after_charge(self):
        game, p1, army_sm, army_enemy = _build_game("Liberator Assault Group")
        attacker = _make_unit(
            "Assault Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness=4,
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        attacker.round_state.charged_this_round = True

        game._on_fight_unit_selected_red_thirst(unit=attacker, selecting_player=p1)
        self.assertEqual(int(attacker.special_rules.get("red_thirst_melee_attacks_bonus", 0)), 1)
        self.assertEqual(int(attacker.special_rules.get("red_thirst_melee_strength_bonus", 0)), 2)
        game.phase = SimpleNamespace(name="FIGHT_PHASE")

        profile = _make_melee_profile()
        captured = []
        original_summary = profile._print_attack_summary
        profile._print_attack_summary = lambda result: captured.append(result)
        try:
            profile.attack(target, attacker.models[0], game_map=None)
        finally:
            profile._print_attack_summary = original_summary
        self.assertTrue(captured, "Expected attack summary to capture an AttackResult")
        attack_result = captured[0]
        self.assertEqual(int(attack_result.attacks_rolled), 2)
        self.assertTrue(any("Red Thirst" in s for s in list(attack_result.attacks_special_modifiers or [])))

        wound_result = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 1.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Red Thirst" in s for s in list(wound_result.get("modifiers", []) or [])))

    def test_red_thirst_does_not_apply_without_charge(self):
        game, p1, army_sm, _army_enemy = _build_game("Liberator Assault Group")
        attacker = _make_unit(
            "Assault Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(attacker)
        attacker.round_state.charged_this_round = False

        game._on_fight_unit_selected_red_thirst(unit=attacker, selecting_player=p1)
        self.assertNotIn("red_thirst_melee_attacks_bonus", attacker.special_rules)
        self.assertNotIn("red_thirst_melee_strength_bonus", attacker.special_rules)

    def test_red_thirst_does_not_apply_outside_liberator_detachment(self):
        game, p1, army_sm, _army_enemy = _build_game("Gladius Task Force")
        attacker = _make_unit(
            "Assault Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(attacker)
        attacker.round_state.charged_this_round = True

        game._on_fight_unit_selected_red_thirst(unit=attacker, selecting_player=p1)
        self.assertNotIn("red_thirst_melee_attacks_bonus", attacker.special_rules)
        self.assertNotIn("red_thirst_melee_strength_bonus", attacker.special_rules)

    def test_red_thirst_cleans_up_at_end_of_fight_phase(self):
        game, p1, army_sm, _army_enemy = _build_game("Liberator Assault Group")
        attacker = _make_unit(
            "Assault Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(attacker)
        attacker.round_state.charged_this_round = True

        game._on_fight_unit_selected_red_thirst(unit=attacker, selecting_player=p1)
        self.assertIn("red_thirst_melee_attacks_bonus", attacker.special_rules)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertNotIn("red_thirst_melee_attacks_bonus", attacker.special_rules)
        self.assertNotIn("red_thirst_melee_strength_bonus", attacker.special_rules)
        self.assertNotIn("red_thirst_expires_phase", attacker.special_rules)

    def test_red_thirst_handler_is_registered_for_fight_unit_selected(self):
        game, _p1, _army_sm, _army_enemy = _build_game("Liberator Assault Group")
        callbacks = [cb for cb, _grp in list(game.event_system.subscribers.get("fight_unit_selected", []) or [])]
        callback_names = {getattr(cb, "__name__", "") for cb in callbacks}
        self.assertIn("_on_fight_unit_selected_red_thirst", callback_names)


if __name__ == "__main__":
    unittest.main()
