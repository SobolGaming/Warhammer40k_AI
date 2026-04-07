from __future__ import annotations

import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
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
        wounds: str = "3",
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
                "W": str(wounds),
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
    army1 = Army.with_detachment("Chaos Space Marines", "Renegade Warband")
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


def _find_request(game: Game, ability_key: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability_key):
            return req
    return None


def _find_target_option(request, *, target_unit_id: str):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "").strip() == str(target_unit_id).strip():
            return opt
    return None


def _find_skip_option(request):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == "skip":
            return opt
    return None


def _set_bearer_enhancement(unit: Unit, *, flag_key: str, values: dict):
    sr = dict(getattr(unit, "special_rules", {}) or {})
    sr[flag_key] = True
    for key, value in dict(values or {}).items():
        sr[key] = value
    bearer = unit.models[0]
    bearer_id = str(get_entity_id(bearer) or getattr(bearer, "id", getattr(bearer, "_id", "")) or "").strip()
    if bearer_id:
        sr["enhancement_bearer_model_id"] = bearer_id
    unit.special_rules = sr


class TestCsmRenegadeWarbandEnhancements(unittest.TestCase):
    def test_weaponised_hatred_reactive_retargets_vendetta(self):
        game, p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy_a = _make_unit("Enemy A", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_b = _make_unit("Enemy B", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_c = _make_unit("Enemy C", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        _set_bearer_enhancement(
            attacker,
            flag_key="enhancement_weaponised_hatred",
            values={
                "enhancement_weaponised_hatred_source": "Weaponised Hatred",
                "enhancement_weaponised_hatred_requires_vendetta_target": True,
                "enhancement_weaponised_hatred_requires_bearer_on_battlefield": True,
            },
        )
        army1.add_unit(attacker)
        army2.add_unit(enemy_a)
        army2.add_unit(enemy_b)
        army2.add_unit(enemy_c)
        game.map.units = [attacker, enemy_a, enemy_b, enemy_c]
        game.rebuild_entity_registry()

        game._maybe_prompt_csm_vendetta()
        vendetta_req = _find_request(game, "renegade_warband_vendetta_target")
        self.assertIsNotNone(vendetta_req)
        enemy_a_id = str(get_entity_id(enemy_a) or "")
        vendetta_option = _find_target_option(vendetta_req, target_unit_id=enemy_a_id)
        self.assertIsNotNone(vendetta_option)
        result = resolve_decision_command(game, vendetta_req, vendetta_option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertIsNone(_find_request(game, "renegade_warband_weaponised_hatred_target"))

        mgr = army1.chaos_space_marines_detachments
        self.assertEqual(str(mgr.renegade_warband_vendetta_target_unit_id), enemy_a_id)

        game._on_unit_destroyed_rules(unit=enemy_a, destroyed_by_unit=attacker)
        weaponised_req = _find_request(game, "renegade_warband_weaponised_hatred_target")
        self.assertIsNotNone(weaponised_req)
        weaponised_ctx = dict(getattr(weaponised_req, "context", {}) or {})
        self.assertTrue(bool(weaponised_ctx.get("optional", False)))
        self.assertEqual(str(weaponised_ctx.get("destroyed_vendetta_target_unit_id", "") or ""), enemy_a_id)
        enemy_b_id = str(get_entity_id(enemy_b) or "")
        weaponised_option = _find_target_option(weaponised_req, target_unit_id=enemy_b_id)
        self.assertIsNotNone(weaponised_option)
        result = resolve_decision_command(game, weaponised_req, weaponised_option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        self.assertEqual(str(mgr.renegade_warband_vendetta_target_unit_id), enemy_b_id)
        self.assertEqual(str(mgr.renegade_warband_weaponised_hatred_target_unit_id), enemy_b_id)
        self.assertEqual(
            str(getattr(mgr, "_renegade_warband_weaponised_hatred_pending_destroyed_vendetta_unit_id", "") or ""),
            "",
        )

        game._on_unit_destroyed_rules(unit=enemy_b, destroyed_by_unit=attacker)
        self.assertIsNone(_find_request(game, "renegade_warband_weaponised_hatred_target"))
        self.assertEqual(str(mgr.renegade_warband_vendetta_target_unit_id), "")
        self.assertEqual(str(mgr.renegade_warband_weaponised_hatred_target_unit_id), "")

    def test_weaponised_hatred_reactive_choice_can_be_skipped(self):
        game, p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy_a = _make_unit("Enemy A", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_b = _make_unit("Enemy B", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        _set_bearer_enhancement(
            attacker,
            flag_key="enhancement_weaponised_hatred",
            values={
                "enhancement_weaponised_hatred_source": "Weaponised Hatred",
                "enhancement_weaponised_hatred_requires_vendetta_target": True,
                "enhancement_weaponised_hatred_requires_bearer_on_battlefield": True,
            },
        )
        army1.add_unit(attacker)
        army2.add_unit(enemy_a)
        army2.add_unit(enemy_b)
        game.map.units = [attacker, enemy_a, enemy_b]
        game.rebuild_entity_registry()

        game._maybe_prompt_csm_vendetta()
        vendetta_req = _find_request(game, "renegade_warband_vendetta_target")
        self.assertIsNotNone(vendetta_req)
        enemy_a_id = str(get_entity_id(enemy_a) or "")
        vendetta_option = _find_target_option(vendetta_req, target_unit_id=enemy_a_id)
        self.assertIsNotNone(vendetta_option)
        result = resolve_decision_command(game, vendetta_req, vendetta_option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        game._on_unit_destroyed_rules(unit=enemy_a, destroyed_by_unit=attacker)
        weaponised_req = _find_request(game, "renegade_warband_weaponised_hatred_target")
        self.assertIsNotNone(weaponised_req)
        skip_option = _find_skip_option(weaponised_req)
        self.assertIsNotNone(skip_option)
        result = resolve_decision_command(game, weaponised_req, skip_option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        mgr = army1.chaos_space_marines_detachments
        self.assertEqual(str(mgr.renegade_warband_vendetta_target_unit_id), "")
        self.assertEqual(str(mgr.renegade_warband_weaponised_hatred_target_unit_id), "")

    def test_weaponised_hatred_descriptor_uses_reactive_optional_selection(self):
        from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor

        descriptor = get_enhancement_tool_descriptor(enhancement_id="000010694002")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.timing, "after_vendetta_target_destroyed_once_per_battle_round")
        self.assertTrue(bool(descriptor.effect_params.get("optional", False)))
        self.assertTrue(bool(descriptor.effect_params.get("requires_visibility", False)))

    def test_eyes_of_the_hunter_sets_ranged_ignores_cover(self):
        game, _p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy = _make_unit("Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        _set_bearer_enhancement(
            attacker,
            flag_key="enhancement_eyes_of_the_hunter",
            values={
                "enhancement_eyes_of_the_hunter_source": "Eyes of the Hunter",
                "enhancement_eyes_of_the_hunter_ignores_cover_ranged": True,
            },
        )
        army1.add_unit(attacker)
        army2.add_unit(enemy)
        game.map.units = [attacker, enemy]
        game.rebuild_entity_registry()
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        profile = _make_profile(weapon_type="ranged")
        attack_instance = {}
        profile._hit_target_with_tracking(
            enemy,
            attacker.models[0],
            attack_instance,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(attack_instance.get("ignores_cover", False)))

    def test_fratricidal_trophies_rerolls_hit_after_default_to_doctrine(self):
        game, p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy = _make_unit("Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        _set_bearer_enhancement(
            attacker,
            flag_key="enhancement_fratricidal_trophies",
            values={
                "enhancement_fratricidal_trophies_source": "Fratricidal Trophies",
                "enhancement_fratricidal_trophies_reroll_hit": True,
                "enhancement_fratricidal_trophies_requires_default_to_doctrine": True,
            },
        )
        army1.add_unit(attacker)
        army2.add_unit(enemy)
        game.map.units = [attacker, enemy]
        game.rebuild_entity_registry()

        profile = _make_profile(weapon_type="ranged")
        hit_before = profile._hit_target_with_tracking(
            enemy,
            attacker.models[0],
            {},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )
        reasons_before = list(hit_before.get("reroll_full_reasons", []) or [])
        self.assertFalse(any("Fratricidal Trophies" in str(reason) for reason in reasons_before))

        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        attacker.take_battle_shock_test = lambda _turn=0: None
        mgr = army1.chaos_space_marines_detachments
        outcome = mgr.activate_twisted_doctrine(
            attacker,
            choice_key="ADVANCE_CHARGE",
            action="move",
            game=game,
            player=p1,
        )
        self.assertTrue(bool(outcome.get("ok", False)))

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        hit_after = profile._hit_target_with_tracking(
            enemy,
            attacker.models[0],
            {},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )
        reasons_after = list(hit_after.get("reroll_full_reasons", []) or [])
        self.assertTrue(any("Fratricidal Trophies" in str(reason) for reason in reasons_after))

    def test_empyric_symbiote_adds_advance_and_charge_modifiers(self):
        game, _p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy = _make_unit("Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        _set_bearer_enhancement(
            attacker,
            flag_key="enhancement_empyric_symbiote",
            values={
                "enhancement_empyric_symbiote_source": "Empyric Symbiote",
                "enhancement_empyric_symbiote_advance_roll_bonus": 1,
                "enhancement_empyric_symbiote_charge_roll_bonus": 1,
            },
        )
        army1.add_unit(attacker)
        army2.add_unit(enemy)
        game.map.units = [attacker, enemy]
        game.rebuild_entity_registry()

        advance_mods = list(attacker._collect_advance_roll_modifiers() or [])
        self.assertTrue(any(int(value) == 1 and "Empyric Symbiote" in str(source) for value, source in advance_mods))

        charge_mods = list(attacker.get_charge_roll_target_strength_modifiers(target_units=[enemy]) or [])
        self.assertTrue(any(int(value) == 1 and "Empyric Symbiote" in str(source) for value, source in charge_mods))


if __name__ == "__main__":
    unittest.main()
