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
        save: str = "3",
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
                "Sv": str(save),
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


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4, save: str = "3"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        save=save,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Black Spear Task Force"):
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


class TestSpaceMarinesBlackSpearTaskForce(unittest.TestCase):
    def test_mission_tactics_selection_is_round_limited_and_once_per_battle_per_tactic(self):
        game, _player, army_sm, _army_enemy = _build_game("Black Spear Task Force")
        mgr = army_sm.space_marines_detachments

        self.assertTrue(mgr.can_select_mission_tactic(game=game))
        self.assertTrue(mgr.select_mission_tactic("FUROR_TACTICS", battle_round=1))
        self.assertFalse(mgr.can_select_mission_tactic(game=game))

        game.turn = 2
        mgr.clear_active_mission_tactic(game=game)
        self.assertTrue(mgr.can_select_mission_tactic(game=game))
        self.assertFalse(mgr.select_mission_tactic("FUROR_TACTICS", battle_round=2))
        self.assertTrue(mgr.select_mission_tactic("MALLEUS_TACTICS", battle_round=2))

    def test_mission_tactics_command_phase_decision_applies_selection(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_MISSION_TACTIC
        from warhammer40k_ai.utility.decision_utils import resolve_decision_value

        game, player, army_sm, _army_enemy = _build_game("Black Spear Task Force")
        mgr = army_sm.space_marines_detachments

        game._maybe_prompt_mission_tactics()
        requests = list(game.decision_queue.list() or [])
        req = next(r for r in requests if str(getattr(r, "decision_type", "")) == DECISION_CHOOSE_MISSION_TACTIC)

        chosen = next(
            opt
            for opt in list(getattr(req, "options", []) or [])
            if str((getattr(opt, "payload", {}) or {}).get("choice_key", "") or "") == "MALLEUS_TACTICS"
        )
        value, apply_result = resolve_decision_value(game, req, chosen.option_id, player_id=player.id)
        self.assertIsNotNone(apply_result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertTrue(bool(value))
        self.assertEqual(str(getattr(mgr, "mission_tactics_active_key", "")), "MALLEUS_TACTICS")
        self.assertIn("MALLEUS_TACTICS", set(getattr(mgr, "mission_tactics_selected_keys", ()) or ()))

    def test_furor_tactics_grants_sustained_hits_one(self):
        _game, _player, army_sm, army_enemy = _build_game("Black Spear Task Force")
        attacker = _make_unit(
            "Deathwatch Kill Team",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        army_sm.space_marines_detachments.select_mission_tactic("FUROR_TACTICS", battle_round=1)

        profile = _make_ranged_profile()
        attack_instance = {"distance_to_target": 18.0}
        hit = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            attack_instance,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertEqual(int(attack_instance.get("sustained_hit", 0) or 0), 1)
        self.assertTrue(any("Sustained Hits" in s for s in list(hit.get("special_effects", []) or [])))

    def test_malleus_tactics_grants_lethal_hits(self):
        _game, _player, army_sm, army_enemy = _build_game("Black Spear Task Force")
        attacker = _make_unit(
            "Deathwatch Kill Team",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        army_sm.space_marines_detachments.select_mission_tactic("MALLEUS_TACTICS", battle_round=1)

        profile = _make_ranged_profile()
        attack_instance = {"distance_to_target": 18.0}
        hit = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            attack_instance,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertTrue(bool(attack_instance.get("lethal_hit", False)))
        self.assertTrue(any("Lethal Hits" in s for s in list(hit.get("special_effects", []) or [])))

    def test_purgatus_tactics_grants_precision_on_critical_hit(self):
        _game, _player, army_sm, army_enemy = _build_game("Black Spear Task Force")
        attacker = _make_unit(
            "Deathwatch Kill Team",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        army_sm.space_marines_detachments.select_mission_tactic("PURGATUS_TACTICS", battle_round=1)

        profile = _make_ranged_profile()

        non_crit_attack = {"distance_to_target": 18.0}
        profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            non_crit_attack,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(non_crit_attack.get("bonus_precision", False)))

        crit_attack = {"distance_to_target": 18.0}
        profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            crit_attack,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(crit_attack.get("bonus_precision", False)))


if __name__ == "__main__":
    unittest.main()
