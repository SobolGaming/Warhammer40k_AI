from __future__ import annotations

import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_DARK_PACT, DECISION_CHOOSE_QUARRY
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
        leadership: str = "7",
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
                "M": "10",
                "T": str(toughness),
                "Sv": "3",
                "W": "10",
                "Ld": str(leadership),
                "OC": "3",
                "base_size": "120x92mm",
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
    leadership: str = "7",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            leadership=leadership,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.possible_abilities = ["Dark Pacts"]
    return unit


def _make_profile(*, weapon_type: str, strength: str = "4", attacks: str = "1"):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if str(weapon_type).lower() == "melee" else "Ranged",
            "range": "Melee" if str(weapon_type).lower() == "melee" else "24",
            "A": str(attacks),
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
    army1 = Army.with_detachment("Chaos Space Marines", "Soulforged Warpack")
    army1.faction_id = "CSM"
    army2 = Army.with_detachment("Enemy", "Other")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    game.turn = 1
    game.current_player_index = 0
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, p1, p2, army1, army2


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="CSM",
        detachment="Soulforged Warpack",
        points=20,
        description="",
    ).apply_to_unit(unit)


def _find_dark_pact_request(game: Game, *, unit_id: str) -> object | None:
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_DARK_PACT:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("unit_id", "") or "") == str(unit_id):
            return req
    return None


def _find_option(request, *, choice: str, invoke_contract: bool) -> object | None:
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("choice", "") or "").strip().upper() != str(choice).strip().upper():
            continue
        if bool(payload.get("invoke_contract", False)) != bool(invoke_contract):
            continue
        return opt
    return None


def _find_choose_quarry_request(game: Game, *, ability: str) -> object | None:
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip() != str(ability).strip():
            continue
        return req
    return None


def _find_target_option(request, *, target_unit_id: str) -> object | None:
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "").strip() == str(target_unit_id).strip():
            return opt
    return None


class TestCsmSoulforgedWarpackDetachment(unittest.TestCase):
    def test_soulforged_enhancement_descriptors_exist(self):
        expected = {
            "000008985002": ("Forge's Blessing", "select_vehicle_unit_gain_fnp"),
            "000008985003": ("Invigorated Mechatendrils", "bearer_move_bonus"),
            "000008985004": ("Tempting Addendum", "contract_failure_mortal_wound_bonus_and_attack_hit_reroll"),
            "000008985005": ("Soul Harvester", "gain_cp_on_destroyed_enemy_unit_within_range"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_dark_pacts_options_include_invoke_contract_for_daemon_vehicle(self):
        game, _p1, _p2, army1, army2 = _build_game()
        daemon_vehicle = _make_unit(
            "Maulerfiend",
            keywords=["HERETIC ASTARTES", "DAEMON", "VEHICLE"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(daemon_vehicle)
        army2.add_unit(enemy)
        game.map.units = [daemon_vehicle, enemy]
        game.rebuild_entity_registry()

        daemon_vehicle.maybe_trigger_dark_pacts(game, phase_name="SHOOTING_PHASE", trigger="shooting")
        req = _find_dark_pact_request(game, unit_id=str(get_entity_id(daemon_vehicle) or ""))
        self.assertIsNotNone(req)

        options = list(getattr(req, "options", []) or [])
        self.assertEqual(5, len(options))
        self.assertIsNotNone(_find_option(req, choice="LETHAL HITS", invoke_contract=False))
        self.assertIsNotNone(_find_option(req, choice="LETHAL HITS", invoke_contract=True))
        self.assertIsNotNone(_find_option(req, choice="SUSTAINED HITS 1", invoke_contract=True))

    def test_invoke_contract_applies_dark_pact_modifier_and_combat_bonuses(self):
        game, p1, _p2, army1, army2 = _build_game()
        daemon_vehicle = _make_unit(
            "Forgefiend",
            keywords=["HERETIC ASTARTES", "DAEMON", "VEHICLE"],
            faction_keywords=["HERETIC ASTARTES"],
            toughness="10",
            leadership="7",
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness="4",
        )
        army1.add_unit(daemon_vehicle)
        army2.add_unit(enemy)
        game.map.units = [daemon_vehicle, enemy]
        game.rebuild_entity_registry()

        daemon_vehicle.maybe_trigger_dark_pacts(game, phase_name="SHOOTING_PHASE", trigger="shooting")
        req = _find_dark_pact_request(game, unit_id=str(get_entity_id(daemon_vehicle) or ""))
        self.assertIsNotNone(req)

        option = _find_option(req, choice="LETHAL HITS", invoke_contract=True)
        self.assertIsNotNone(option)

        with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=8):
            result = resolve_decision_command(game, req, option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        self.assertTrue(bool(daemon_vehicle.special_rules.get("dark_pacts_test_passed")))
        self.assertTrue(bool(daemon_vehicle.special_rules.get("soulforged_warpack_contract_active")))

        ranged_profile = _make_profile(weapon_type="ranged", strength="4", attacks="1")
        wound_result = ranged_profile._wound_target_with_tracking(
            enemy,
            daemon_vehicle.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(wound_result.get("wound", False)))
        self.assertTrue(
            any("Debt to the Soul Forge" in str(mod) for mod in list(wound_result.get("modifiers", []) or []))
        )

        melee_profile = _make_profile(weapon_type="melee", strength="8", attacks="1")
        preview = melee_profile.preview_attack_count(
            enemy,
            daemon_vehicle.models[0],
            publish_roll_event=False,
        )
        self.assertEqual(3, int(preview.num_attacks))
        self.assertTrue(
            any("Debt to the Soul Forge" in str(mod) for mod in list(preview.special_modifiers or []))
        )

    def test_invoke_contract_not_offered_for_non_daemon_vehicle(self):
        game, _p1, _p2, army1, army2 = _build_game()
        legionaries = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(legionaries)
        army2.add_unit(enemy)
        game.map.units = [legionaries, enemy]
        game.rebuild_entity_registry()

        legionaries.maybe_trigger_dark_pacts(game, phase_name="SHOOTING_PHASE", trigger="shooting")
        req = _find_dark_pact_request(game, unit_id=str(get_entity_id(legionaries) or ""))
        self.assertIsNotNone(req)

        options = list(getattr(req, "options", []) or [])
        self.assertEqual(3, len(options))
        self.assertIsNone(_find_option(req, choice="LETHAL HITS", invoke_contract=True))
        self.assertIsNone(_find_option(req, choice="SUSTAINED HITS 1", invoke_contract=True))

    def test_forges_blessing_command_phase_selection_grants_fnp_to_target(self):
        game, p1, _p2, army1, army2 = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE
        source = _make_unit(
            "Warpsmith",
            keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER", "WARPSMITH"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        target_vehicle = _make_unit(
            "Forgefiend",
            keywords=["HERETIC ASTARTES", "DAEMON", "VEHICLE"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        other_vehicle = _make_unit(
            "Maulerfiend",
            keywords=["HERETIC ASTARTES", "DAEMON", "VEHICLE"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(source)
        army1.add_unit(target_vehicle)
        army1.add_unit(other_vehicle)
        army2.add_unit(enemy)
        game.map.units = [source, target_vehicle, other_vehicle, enemy]
        game.rebuild_entity_registry()
        _apply_enhancement(
            source,
            enhancement_id="000008985002",
            enhancement_name="Forge's Blessing",
        )

        game._maybe_prompt_csm_forges_blessing()
        req = _find_choose_quarry_request(game, ability="soulforged_warpack_forges_blessing_target")
        self.assertIsNotNone(req)

        target_unit_id = str(get_entity_id(target_vehicle) or "")
        option = _find_target_option(req, target_unit_id=target_unit_id)
        self.assertIsNotNone(option)
        result = resolve_decision_command(game, req, option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        fnp_target = list(target_vehicle.has_feel_no_pain() or [])
        fnp_other = list(other_vehicle.has_feel_no_pain() or [])
        self.assertTrue(any(int(v) == 6 for v, _cond in fnp_target))
        self.assertFalse(any(int(v) == 6 for v, _cond in fnp_other))

    def test_tempting_addendum_adds_mortal_wound_and_reroll_hit(self):
        game, p1, _p2, army1, army2 = _build_game()
        source = _make_unit(
            "Warpsmith",
            keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER", "WARPSMITH"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        daemon_vehicle = _make_unit(
            "Forgefiend",
            keywords=["HERETIC ASTARTES", "DAEMON", "VEHICLE"],
            faction_keywords=["HERETIC ASTARTES"],
            toughness="10",
            leadership="7",
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(source)
        army1.add_unit(daemon_vehicle)
        army2.add_unit(enemy)
        game.map.units = [source, daemon_vehicle, enemy]
        game.rebuild_entity_registry()
        _apply_enhancement(
            source,
            enhancement_id="000008985004",
            enhancement_name="Tempting Addendum",
        )

        starting_wounds = int(getattr(daemon_vehicle.models[0], "_wounds", 0) or 0)
        daemon_vehicle.maybe_trigger_dark_pacts(game, phase_name="SHOOTING_PHASE", trigger="shooting")
        req = _find_dark_pact_request(game, unit_id=str(get_entity_id(daemon_vehicle) or ""))
        self.assertIsNotNone(req)
        option = _find_option(req, choice="LETHAL HITS", invoke_contract=True)
        self.assertIsNotNone(option)

        with (
            patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=12),
            patch("warhammer40k_ai.utility.dice.DiceCollection.from_string") as dice_from_string,
        ):
            dice_from_string.return_value.roll_detailed.return_value = (2, [2])
            result = resolve_decision_command(game, req, option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        ending_wounds = int(getattr(daemon_vehicle.models[0], "_wounds", 0) or 0)
        self.assertEqual(starting_wounds - ending_wounds, 3)

        profile = _make_profile(weapon_type="ranged", strength="4", attacks="1")
        hit_result = profile._hit_target_with_tracking(
            enemy,
            daemon_vehicle.models[0],
            {},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )
        reroll_reasons = list(hit_result.get("reroll_full_reasons", []) or [])
        self.assertTrue(any("Tempting Addendum" in str(reason) for reason in reroll_reasons))

    def test_soul_harvester_gains_cp_on_destroyed_enemy_within_range(self):
        game, p1, _p2, army1, army2 = _build_game()
        source = _make_unit(
            "Warpsmith",
            keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER", "WARPSMITH"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        killer = _make_unit(
            "Forgefiend",
            keywords=["HERETIC ASTARTES", "DAEMON", "VEHICLE"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(source)
        army1.add_unit(killer)
        army2.add_unit(enemy)
        game.map.units = [source, killer, enemy]
        game.rebuild_entity_registry()
        _apply_enhancement(
            source,
            enhancement_id="000008985005",
            enhancement_name="Soul Harvester",
        )

        before_cp = int(getattr(p1, "command_points", 0) or 0)
        with patch("warhammer40k_ai.rules.chaos_space_marines_detachments.get_roll", return_value=5):
            game._on_unit_destroyed_rules(
                unit=enemy,
                destroyed_by_unit=killer,
                destroyed_by_model=killer.models[0],
            )
        after_cp = int(getattr(p1, "command_points", 0) or 0)
        self.assertEqual(after_cp, before_cp + 1)


if __name__ == "__main__":
    unittest.main()
