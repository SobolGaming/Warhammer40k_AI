from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        faction_keywords=None,
        keywords=None,
        wounds: str = "2",
        move: str = "8",
        model_count: int = 1,
    ):
        count = max(1, int(model_count or 1))
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(move),
                "T": "4",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    faction_keywords=None,
    keywords=None,
    wounds: str = "2",
    move: str = "8",
    quantity: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            wounds=wounds,
            move=move,
            model_count=int(quantity),
        ),
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    aeldari_army = Army("Aeldari", "Seer Council")
    aeldari_army.faction_id = "AE"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Aeldari", control=PlayerControl.LOCAL, army=aeldari_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 10
    p2.command_points = 10

    aeldari_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, aeldari_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 2.0, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _norm_name(name: str) -> str:
    text = str(name or "").strip().upper()
    return text.replace("\u2019", "'")


def _pending_by_name(stratagems, name_substring: str):
    wanted = _norm_name(name_substring)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if wanted in _norm_name(reaction.get("stratagem", "")):
            return reaction
    return None


def _find_unshrouded_move_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_MOVE_UNIT:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("placement_kind", "") or "") == "aeldari_unshrouded_truth":
            return req
    return None


def _placement_payload(unit: Unit, positions: list[tuple[float, float, float]]) -> dict:
    out = []
    for model, position in zip(list(getattr(unit, "models", []) or []), list(positions or [])):
        out.append(
            {
                "model_id": get_entity_id(model),
                "position": [float(position[0]), float(position[1]), float(position[2])],
                "facing": 0.0,
            }
        )
    return {"model_positions": out}


class TestAeldariSeerCouncilStratagems(unittest.TestCase):
    def test_unshrouded_truth_queues_and_creates_redeploy_move_request(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        psyker = _make_unit(
            "Farseer",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "PSYKER"],
            quantity=1,
        )
        infantry = _make_unit(
            "Guardian Defenders",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "GUARDIANS"],
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=2,
        )
        aeldari_army.add_unit(psyker)
        aeldari_army.add_unit(infantry)
        enemy_army.add_unit(enemy)
        _place_unit(game, psyker, 10.0, 10.0)
        _place_unit(game, infantry, 13.0, 10.0)
        _place_unit(game, enemy, 30.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "UNSHROUDED TRUTH")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=infantry, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        request = _find_unshrouded_move_request(game)
        self.assertIsNotNone(request)
        ctx = dict(getattr(request, "context", {}) or {})
        self.assertEqual(str(ctx.get("placement_kind", "") or ""), "aeldari_unshrouded_truth")
        self.assertEqual(str(ctx.get("movement_type", "") or ""), "deploy")
        self.assertFalse(bool(ctx.get("allow_skip", True)))
        self.assertEqual(str(ctx.get("unit_id", "") or ""), str(get_entity_id(infantry) or ""))
        expected_ids = {str(get_entity_id(model) or "") for model in list(infantry.models or [])}
        self.assertEqual(set(str(v) for v in list(ctx.get("allowed_model_ids") or [])), expected_ids)

        self.assertTrue(bool(getattr(infantry.round_state, "moved_this_round", False)))
        self.assertFalse(bool(getattr(infantry.round_state, "remained_stationary_this_round", True)))

    def test_unshrouded_truth_redeploy_requires_more_than_9_horizontal_from_enemy_models(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        psyker = _make_unit(
            "Farseer",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "PSYKER"],
            quantity=1,
        )
        infantry = _make_unit(
            "Guardian Defenders",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "GUARDIANS"],
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=1,
        )
        aeldari_army.add_unit(psyker)
        aeldari_army.add_unit(infantry)
        enemy_army.add_unit(enemy)
        _place_unit(game, psyker, 10.0, 10.0)
        _place_unit(game, infantry, 13.0, 10.0)
        _place_unit(game, enemy, 20.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "UNSHROUDED TRUTH")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=infantry, dequeue=True)
        self.assertTrue(ok)

        request = _find_unshrouded_move_request(game)
        self.assertIsNotNone(request)
        option_id = request.options[0].option_id

        invalid = resolve_decision_command(
            game,
            request,
            option_id,
            result_payload=_placement_payload(
                infantry,
                [
                    (27.0, 10.0, 0.0),
                    (29.0, 10.0, 0.0),
                ],
            ),
            player_id=p1.id,
        )
        self.assertFalse(bool(getattr(invalid, "ok", False)))
        invalid_errors = [str(err or "") for err in list(getattr(invalid, "errors", ()) or ())]
        self.assertTrue(any("Unshrouded Truth placement" in err for err in invalid_errors))

        valid = resolve_decision_command(
            game,
            request,
            option_id,
            result_payload=_placement_payload(
                infantry,
                [
                    (36.0, 10.0, 0.0),
                    (38.0, 10.0, 0.0),
                ],
            ),
            player_id=p1.id,
        )
        self.assertTrue(bool(getattr(valid, "ok", False)))
        first_loc = infantry.models[0].get_location()
        self.assertAlmostEqual(float(first_loc[0]), 36.0, places=3)
        self.assertIsNone(_find_unshrouded_move_request(game))

    def test_ishas_fury_reacts_to_enemy_move_and_deals_mortal_wounds(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        psyker = _make_unit(
            "Warlock",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "PSYKER"],
            quantity=1,
        )
        enemy = _make_unit(
            "Enemy Monster",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["MONSTER"],
            wounds="8",
            quantity=1,
        )
        aeldari_army.add_unit(psyker)
        enemy_army.add_unit(enemy)
        _place_unit(game, psyker, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)

        _set_phase(game, p2, "MOVEMENT_PHASE", 1)
        game.event_system.publish("unit_move_ended", unit=enemy, action="move")
        pending = _pending_by_name(p1.stratagems, "ISHA")
        self.assertIsNotNone(pending)

        enemy_model = enemy.models[0]
        before_wounds = int(getattr(enemy_model, "wounds", 0) or 0)
        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[3, 3, 2, 1, 6, 4]):
            ok = p1.stratagems.use(
                str(pending.get("stratagem", "")),
                unit=psyker,
                enemy_unit=enemy,
                action="move",
                dequeue=True,
            )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        after_wounds = int(getattr(enemy_model, "wounds", 0) or 0)
        self.assertEqual(before_wounds - after_wounds, 4)

    def test_fate_inescapable_applies_ignores_cover_and_critical_wound_ap_bonus(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        psyker = _make_unit(
            "Farseer",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "PSYKER"],
            quantity=1,
        )
        infantry = _make_unit(
            "Guardian Defenders",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "GUARDIANS"],
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=1,
        )
        aeldari_army.add_unit(psyker)
        aeldari_army.add_unit(infantry)
        enemy_army.add_unit(enemy)
        _place_unit(game, psyker, 10.0, 10.0)
        _place_unit(game, infantry, 13.0, 10.0)
        _place_unit(game, enemy, 20.0, 10.0)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        ok = p1.stratagems.use("FATE INESCAPABLE", unit=infantry, phase_name="Shooting phase")
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        bonuses = infantry.get_attack_keyword_bonuses(
            target=enemy,
            attack_type="ranged",
            model=infantry.models[0],
        )
        self.assertTrue(bool((bonuses or {}).get("ignores_cover", False)))

        weapon = Wargear(
            {
                "name": "Test Rifle",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        save_result = profile._save_with_tracking(
            enemy.models[0],
            {
                "attacker_model": infantry.models[0],
                "attacker_unit": infantry,
                "target_unit": enemy,
                "crit_wound": True,
            },
            0,
            roll_value=1,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertEqual(int(save_result.get("needed", 0) or 0), 4)
        self.assertEqual(int(save_result.get("ap_modifier", 0) or 0), -1)
        self.assertTrue(
            any("FATE INESCAPABLE" in str(effect or "").upper() for effect in list(save_result.get("special_effects") or []))
        )

    def test_psychic_shield_queues_and_applies_ranged_targeting_cap(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        psyker = _make_unit(
            "Warlock",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "PSYKER"],
            quantity=1,
        )
        defender = _make_unit(
            "Guardian Defenders",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "GUARDIANS"],
            quantity=2,
        )
        attacker = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=1,
        )
        aeldari_army.add_unit(psyker)
        aeldari_army.add_unit(defender)
        enemy_army.add_unit(attacker)
        _place_unit(game, psyker, 10.0, 10.0)
        _place_unit(game, defender, 13.0, 10.0)
        _place_unit(game, attacker, 35.0, 10.0)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])
        pending = _pending_by_name(p1.stratagems, "PSYCHIC SHIELD")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=defender,
            attacking_unit=attacker,
            target_units=[defender],
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        limit, sources = defender.get_ranged_targeting_restriction(game_map=game.map)
        self.assertEqual(float(limit or 0.0), 18.0)
        self.assertTrue(any("PSYCHIC SHIELD" in str(source or "").upper() for source in list(sources or [])))

        weapon = Wargear(
            {
                "name": "Ranged Weapon",
                "type": "Ranged",
                "range": "30",
                "A": "1",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        profile.is_indirect_fire = lambda: True

        can_target_far = attacker._can_model_shoot_weapon_at_target(
            attacker.models[0],
            profile,
            defender,
            game.map,
        )
        self.assertFalse(can_target_far)

        attacker.models[0].set_location(26.0, 10.0, 0.0, 0.0)
        can_target_close = attacker._can_model_shoot_weapon_at_target(
            attacker.models[0],
            profile,
            defender,
            game.map,
        )
        self.assertTrue(can_target_close)

        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        self.assertFalse(bool(getattr(defender, "special_rules", {}).get("aeldari_psychic_shield_active")))

    def test_seer_council_step1_stratagem_descriptors_registered(self):
        unshrouded = get_stratagem_tool_descriptor(stratagem_id="000009924004")
        self.assertIsNotNone(unshrouded)
        self.assertEqual(str(unshrouded.name), "Unshrouded Truth")
        self.assertEqual(int(unshrouded.cp_cost), 1)
        self.assertEqual(
            str(unshrouded.effect),
            "redeploy_unit_more_than_9_horizontal_from_enemy_models_and_mark_not_eligible_to_move",
        )

        isha = get_stratagem_tool_descriptor(stratagem_id="000009924006")
        self.assertIsNotNone(isha)
        self.assertEqual(str(isha.name), "Isha's Fury")
        self.assertEqual(int(isha.cp_cost), 1)
        self.assertEqual(str(isha.effect), "roll_6d6_each_3plus_deals_1_mortal_wound_to_moved_enemy_unit")

        by_name = get_stratagem_tool_descriptor(name="ISHA'S FURY")
        self.assertIsNotNone(by_name)
        self.assertEqual(str(by_name.stratagem_id), "000009924006")

        by_name_unshrouded = get_stratagem_tool_descriptor(name="UNSHROUDED TRUTH")
        self.assertIsNotNone(by_name_unshrouded)
        self.assertEqual(str(by_name_unshrouded.stratagem_id), "000009924004")

        fate = get_stratagem_tool_descriptor(stratagem_id="000009924005")
        self.assertIsNotNone(fate)
        self.assertEqual(str(fate.name), "Fate Inescapable")
        self.assertEqual(int(fate.cp_cost), 1)
        self.assertEqual(str(fate.effect), "ranged_ignores_cover_and_critical_wound_ap_bonus")

        shield = get_stratagem_tool_descriptor(stratagem_id="000009924007")
        self.assertIsNotNone(shield)
        self.assertEqual(str(shield.name), "Psychic Shield")
        self.assertEqual(int(shield.cp_cost), 1)
        self.assertEqual(str(shield.effect), "ranged_targeting_range_restriction")

        by_name_fate = get_stratagem_tool_descriptor(name="FATE INESCAPABLE")
        self.assertIsNotNone(by_name_fate)
        self.assertEqual(str(by_name_fate.stratagem_id), "000009924005")

        by_name_shield = get_stratagem_tool_descriptor(name="PSYCHIC SHIELD")
        self.assertIsNotNone(by_name_shield)
        self.assertEqual(str(by_name_shield.stratagem_id), "000009924007")


if __name__ == "__main__":
    unittest.main()
