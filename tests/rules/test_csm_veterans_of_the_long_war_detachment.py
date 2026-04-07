from __future__ import annotations

import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    toughness: str = "4",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _make_profile(*, weapon_type: str, strength: str = "4"):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if str(weapon_type).lower() == "melee" else "Ranged",
            "range": "Melee" if str(weapon_type).lower() == "melee" else "24",
            "A": "1",
            "BS_WS": "4+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army.with_detachment("Chaos Space Marines", "Veterans of the Long War")
    army1.faction_id = "CSM"
    army2 = Army.with_detachment("Enemy", "Other")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    game.turn = 1
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, p1, p2, army1, army2


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="CSM",
        detachment="Veterans of the Long War",
        points=20,
        description="",
    ).apply_to_unit(unit)


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def _find_focus_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "veterans_of_the_long_war_focus_of_hatred_target":
            continue
        return req
    return None


def _find_target_option(request, *, target_unit_id: str):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "").strip() == str(target_unit_id).strip():
            return opt
    return None


class TestCsmVeteransOfTheLongWarDetachment(unittest.TestCase):
    def test_veterans_enhancement_descriptors_exist(self):
        expected = {
            "000008960002": ("Eager for Vengeance", "fallback_shoot_charge_and_focus_bonuses_after_fall_back"),
            "000008960003": ("Eye of Abaddon", "gain_cp_on_focus_of_hatred_destroyed"),
            "000008960004": ("Mark of Legend", "once_per_turn_reroll_hit_wound_or_save_for_bearer"),
            "000008960005": ("Warmaster's Gift", "focus_of_hatred_wound_roll_critical_on_5_plus_for_bearer"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_focus_of_hatred_prompt_and_hit_reroll(self):
        game, p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        damned_attacker = _make_unit(
            "Accursed Cultists",
            keywords=["HERETIC ASTARTES", "DAMNED", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy_a = _make_unit(
            "Enemy A",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_b = _make_unit(
            "Enemy B",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )

        attacker.possible_abilities = ["Dark Pacts"]
        damned_attacker.possible_abilities = ["Dark Pacts"]

        army1.add_unit(attacker)
        army1.add_unit(damned_attacker)
        army2.add_unit(enemy_a)
        army2.add_unit(enemy_b)
        game.map.units = [attacker, damned_attacker, enemy_a, enemy_b]
        game.rebuild_entity_registry()

        game._maybe_prompt_csm_focus_of_hatred()
        req = _find_focus_request(game)
        self.assertIsNotNone(req)

        enemy_a_id = str(get_entity_id(enemy_a) or "")
        option = _find_target_option(req, target_unit_id=enemy_a_id)
        self.assertIsNotNone(option)

        result = resolve_decision_command(game, req, option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        profile = _make_profile(weapon_type="ranged")

        hit_focus = profile._hit_target_with_tracking(
            enemy_a,
            attacker.models[0],
            {},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )
        hit_other = profile._hit_target_with_tracking(
            enemy_b,
            attacker.models[0],
            {},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )
        hit_damned = profile._hit_target_with_tracking(
            enemy_a,
            damned_attacker.models[0],
            {},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )

        focus_reasons = list(hit_focus.get("reroll_full_reasons", []) or [])
        other_reasons = list(hit_other.get("reroll_full_reasons", []) or [])
        damned_reasons = list(hit_damned.get("reroll_full_reasons", []) or [])

        self.assertTrue(any("Focus of Hatred" in str(reason) for reason in focus_reasons))
        self.assertFalse(any("Focus of Hatred" in str(reason) for reason in other_reasons))
        self.assertFalse(any("Focus of Hatred" in str(reason) for reason in damned_reasons))

    def test_eager_for_vengeance_grants_fall_back_mobility_and_focus_bonuses(self):
        game, _p1, _p2, army1, army2 = _build_game()
        bearer_unit = _make_unit(
            "Chaos Lord",
            keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER", "CHAOS LORD"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy_focus = _make_unit(
            "Enemy Focus",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_other = _make_unit(
            "Enemy Other",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(bearer_unit)
        army2.add_unit(enemy_focus)
        army2.add_unit(enemy_other)
        game.map.units = [bearer_unit, enemy_focus, enemy_other]
        game.rebuild_entity_registry()

        _apply_enhancement(
            bearer_unit,
            enhancement_id="000008960002",
            enhancement_name="Eager for Vengeance",
        )
        mgr = getattr(army1, "chaos_space_marines_detachments", None)
        self.assertIsNotNone(mgr)
        mgr.veterans_focus_of_hatred_target_unit_id = str(get_entity_id(enemy_focus) or "")
        bearer_unit.round_state.fell_back_this_round = True

        profile = _make_profile(weapon_type="ranged")
        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)

        self.assertTrue(bool(bearer_unit.can_shoot_after_fall_back(profile, bearer)))
        self.assertTrue(bool(bearer_unit.can_charge_after_fall_back()))

        hit_focus = profile._hit_target_with_tracking(
            enemy_focus,
            bearer,
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        hit_other = profile._hit_target_with_tracking(
            enemy_other,
            bearer,
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(hit_focus.get("hit", False)))
        self.assertFalse(bool(hit_other.get("hit", False)))
        focus_mods = list(hit_focus.get("modifiers", []) or [])
        self.assertTrue(any("Eager for Vengeance" in str(reason) for reason in focus_mods))

        focus_charge_mods = list(game.get_charge_roll_modifiers(bearer_unit, target_unit=enemy_focus) or [])
        other_charge_mods = list(game.get_charge_roll_modifiers(bearer_unit, target_unit=enemy_other) or [])
        self.assertTrue(any(int(val) == 1 and "Eager for Vengeance" in str(src) for val, src in focus_charge_mods))
        self.assertFalse(any(int(val) == 1 and "Eager for Vengeance" in str(src) for val, src in other_charge_mods))

    def test_eye_of_abaddon_gains_cp_when_focus_destroyed(self):
        game, p1, _p2, army1, army2 = _build_game()
        source = _make_unit(
            "Chaos Lord",
            keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER", "CHAOS LORD"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        focus_target = _make_unit(
            "Enemy Focus",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(source)
        army2.add_unit(focus_target)
        game.map.units = [source, focus_target]
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000008960003",
            enhancement_name="Eye of Abaddon",
        )
        mgr = getattr(army1, "chaos_space_marines_detachments", None)
        self.assertIsNotNone(mgr)
        mgr.veterans_focus_of_hatred_target_unit_id = str(get_entity_id(focus_target) or "")

        before_cp = int(getattr(p1, "command_points", 0) or 0)
        with patch("warhammer40k_ai.rules.chaos_space_marines_detachments.get_roll", return_value=4):
            game._on_unit_destroyed_rules(
                unit=focus_target,
                destroyed_by_unit=source,
                destroyed_by_model=source.models[0],
            )
        after_cp = int(getattr(p1, "command_points", 0) or 0)
        self.assertEqual(after_cp, before_cp + 1)

    def test_mark_of_legend_is_single_shared_reroll_per_turn(self):
        game, _p1, _p2, army1, army2 = _build_game()
        bearer_unit = _make_unit(
            "Chaos Lord",
            keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER", "CHAOS LORD"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(bearer_unit)
        army2.add_unit(enemy)
        game.map.units = [bearer_unit, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(
            bearer_unit,
            enhancement_id="000008960004",
            enhancement_name="Mark of Legend",
        )
        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        profile = _make_profile(weapon_type="ranged")

        hit_result = profile._hit_target_with_tracking(
            enemy,
            bearer,
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        self.assertIn("reroll", hit_result)
        self.assertTrue(any("Mark of Legend" in str(reason) for reason in list(hit_result.get("special_effects", []) or [])))

        wound_result = profile._wound_target_with_tracking(
            enemy,
            bearer,
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        self.assertNotIn("reroll", wound_result)

        save_result_same_turn = profile._save_with_tracking(
            bearer,
            {"attacker_model": enemy.models[0], "attacker_unit": enemy, "target_unit": bearer_unit},
            ap=0,
            roll_value=2,
            allow_rerolls=True,
            log_roll=False,
        )
        self.assertNotIn("reroll", save_result_same_turn)

        game.turn = 2
        save_result_next_turn = profile._save_with_tracking(
            bearer,
            {"attacker_model": enemy.models[0], "attacker_unit": enemy, "target_unit": bearer_unit},
            ap=0,
            roll_value=2,
            allow_rerolls=True,
            log_roll=False,
        )
        self.assertIn("reroll", save_result_next_turn)

    def test_warmasters_gift_sets_focus_crit_wound_threshold_for_bearer(self):
        game, _p1, _p2, army1, army2 = _build_game()
        bearer_unit = _make_unit(
            "Chaos Lord",
            keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER", "CHAOS LORD"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy_focus = _make_unit(
            "Enemy Focus",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness="4",
        )
        enemy_other = _make_unit(
            "Enemy Other",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness="4",
        )
        army1.add_unit(bearer_unit)
        army2.add_unit(enemy_focus)
        army2.add_unit(enemy_other)
        game.map.units = [bearer_unit, enemy_focus, enemy_other]
        game.rebuild_entity_registry()

        _apply_enhancement(
            bearer_unit,
            enhancement_id="000008960005",
            enhancement_name="Warmaster's Gift",
        )
        mgr = getattr(army1, "chaos_space_marines_detachments", None)
        self.assertIsNotNone(mgr)
        mgr.veterans_focus_of_hatred_target_unit_id = str(get_entity_id(enemy_focus) or "")

        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        profile = _make_profile(weapon_type="melee", strength="4")

        focus_attack = {}
        focus_wound = profile._wound_target_with_tracking(
            enemy_focus,
            bearer,
            focus_attack,
            roll_value=5,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(focus_wound.get("wound", False)))
        self.assertTrue(bool(focus_attack.get("crit_wound", False)))
        self.assertEqual(int(focus_wound.get("crit_threshold", 6) or 6), 5)

        other_attack = {}
        other_wound = profile._wound_target_with_tracking(
            enemy_other,
            bearer,
            other_attack,
            roll_value=5,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(other_wound.get("wound", False)))
        self.assertFalse(bool(other_attack.get("crit_wound", False)))
        self.assertEqual(int(other_wound.get("crit_threshold", 6) or 6), 6)

    def test_focus_of_hatred_excludes_embarked_enemy_units_from_candidates(self):
        game, _p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        embarked_target = _make_unit(
            "Embarked Enemy",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        other_target = _make_unit(
            "Enemy B",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        transport = _make_unit(
            "Enemy Transport",
            faction_name="Enemy",
            keywords=["TRANSPORT", "VEHICLE"],
            faction_keywords=["ENEMY"],
        )
        embarked_target.embarked_in = transport

        army1.add_unit(attacker)
        army2.add_unit(embarked_target)
        army2.add_unit(other_target)
        army2.add_unit(transport)
        game.map.units = [attacker, other_target, transport]
        game.rebuild_entity_registry()

        mgr = getattr(army1, "chaos_space_marines_detachments", None)
        self.assertIsNotNone(mgr)
        candidates = list(mgr.veterans_focus_of_hatred_candidate_enemy_units(game=game, player=army1.player) or [])
        candidate_ids = {str(get_entity_id(unit) or "") for unit in candidates}
        self.assertIn(str(get_entity_id(other_target) or ""), candidate_ids)
        self.assertNotIn(str(get_entity_id(embarked_target) or ""), candidate_ids)

    def test_focus_of_hatred_applies_to_each_unit_created_from_a_split_target(self):
        game, _p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        original_target = _make_unit(
            "Enemy Blob",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        split_a = _make_unit(
            "Enemy Blob A",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        split_b = _make_unit(
            "Enemy Blob B",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        original_target_id = str(get_entity_id(original_target) or "")
        split_a.special_rules["combat_squads_split_origin_unit_id"] = original_target_id
        split_b.special_rules["combat_squads_split_origin_unit_id"] = original_target_id

        army1.add_unit(attacker)
        army2.add_unit(original_target)
        army2.add_unit(split_a)
        army2.add_unit(split_b)
        game.map.units = [attacker, split_a, split_b]
        game.rebuild_entity_registry()

        mgr = getattr(army1, "chaos_space_marines_detachments", None)
        self.assertIsNotNone(mgr)
        mgr.veterans_focus_of_hatred_target_unit_id = original_target_id

        self.assertTrue(mgr._veterans_focus_of_hatred_target_matches(split_a))
        self.assertTrue(mgr._veterans_focus_of_hatred_target_matches(split_b))
        applies_a, _ = mgr.veterans_focus_of_hatred_reroll_hit_applies(attacker.models[0], split_a)
        applies_b, _ = mgr.veterans_focus_of_hatred_reroll_hit_applies(attacker.models[0], split_b)
        self.assertTrue(applies_a)
        self.assertTrue(applies_b)


if __name__ == "__main__":
    unittest.main()
