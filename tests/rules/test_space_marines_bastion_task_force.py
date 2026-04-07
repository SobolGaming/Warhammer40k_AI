import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


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


def _build_game(detachment_type: str = "Bastion Task Force"):
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


class TestSpaceMarinesBastionTaskForce(unittest.TestCase):
    def test_battleline_can_shoot_and_charge_after_advance_or_fall_back(self):
        _game, _player, army_sm, _army_enemy = _build_game()
        unit = _make_unit(
            "Intercessors",
            keywords=["INFANTRY", "BATTLELINE"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(unit)

        profile = _make_ranged_profile()
        self.assertTrue(unit.can_shoot_after_advance(profile))
        self.assertTrue(unit.can_shoot_after_fall_back(profile))
        self.assertTrue(unit.can_charge_after_advance())
        self.assertTrue(unit.can_charge_after_fall_back())

    def test_non_battleline_does_not_gain_interlocking_tactics_movement_bonuses(self):
        _game, _player, army_sm, _army_enemy = _build_game()
        unit = _make_unit(
            "Hellblasters",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(unit)

        profile = _make_ranged_profile()
        self.assertFalse(unit.can_shoot_after_advance(profile))
        self.assertFalse(unit.can_shoot_after_fall_back(profile))
        self.assertFalse(unit.can_charge_after_advance())
        self.assertFalse(unit.can_charge_after_fall_back())

    def test_interlocking_tactics_allows_actions_after_advance_and_fall_back_for_battleline(self):
        game, _player, army_sm, _army_enemy = _build_game()
        unit = _make_unit(
            "Intercessors",
            keywords=["INFANTRY", "BATTLELINE"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(unit)

        unit.round_state.advanced_this_round = True
        unit.round_state.fell_back_this_round = False
        check_advance = game._is_unit_eligible_to_start_action(unit)
        self.assertTrue(check_advance["valid"])

        unit.round_state.advanced_this_round = False
        unit.round_state.fell_back_this_round = True
        check_fallback = game._is_unit_eligible_to_start_action(unit)
        self.assertTrue(check_fallback["valid"])

    def test_interlocking_tactics_auspex_scan_from_shooting_grants_reroll_hit_ones(self):
        game, player, army_sm, army_enemy = _build_game()
        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY", "BATTLELINE"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target_a = _make_unit("Enemy A", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        target_b = _make_unit("Enemy B", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target_a)
        army_enemy.add_unit(target_b)
        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_interlocking_tactics(
            attacker_unit=attacker,
            hits_by_target={target_a: 1, target_b: 1},
        )

        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        self.assertEqual(str((request.context or {}).get("ability", "")), "interlocking_tactics_auspex_scan")

        chosen_option = request.options[0]
        chosen_target_id = str((chosen_option.payload or {}).get("target_unit_id", "") or "")
        resolve_decision_command(game, request, chosen_option.option_id, player_id=player.id)

        chosen_target = game.entity_registry.get(chosen_target_id, kind="unit")
        self.assertIsNotNone(chosen_target)
        sr = getattr(chosen_target, "special_rules", {}) or {}
        self.assertTrue(bool(sr.get("interlocking_tactics_auspex_scanned_active")))
        self.assertIn(player.id, list(sr.get("interlocking_tactics_auspex_scanned_owner_ids", []) or []))

        hit_mods = attacker.get_unit_hit_reroll_modifiers(
            "ranged",
            target=chosen_target,
            attacker_model=attacker.models[0],
        )
        self.assertTrue(hit_mods.get("reroll_hit_ones"))
        self.assertTrue(
            any("Interlocking Tactics" in r for r in list(hit_mods.get("reroll_hit_reasons", ()) or ()))
        )

    def test_interlocking_tactics_fight_marks_after_sequence_complete(self):
        game, _player, army_sm, army_enemy = _build_game()
        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY", "BATTLELINE"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target_a = _make_unit("Enemy A", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        target_b = _make_unit("Enemy B", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target_a)
        army_enemy.add_unit(target_b)
        game.rebuild_entity_registry()

        game._on_fight_attacks_resolved_interlocking_tactics(
            unit=attacker,
            hits_by_target={target_a: 1, target_b: 1},
        )
        self.assertEqual(len(list(game.decision_queue.list() or [])), 0)

        game._on_fight_sequence_complete_interlocking_tactics(unit=attacker)
        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        self.assertEqual(str((pending[0].context or {}).get("ability", "")), "interlocking_tactics_auspex_scan")

        game._on_fight_sequence_complete_interlocking_tactics(unit=attacker)
        self.assertEqual(len(list(game.decision_queue.list() or [])), 1)


if __name__ == "__main__":
    unittest.main()
