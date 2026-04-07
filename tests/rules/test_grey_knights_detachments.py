import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
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


def _make_unit(name, *, keywords=None, faction_keywords=None, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        abilities=abilities,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Brotherhood Strike"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 2

    army_gk = Army.with_detachment("Grey Knights", detachment_type)
    army_gk.faction_id = "GK"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army_gk)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)

    return game, army_gk, army_enemy, p1


class TestGreyKnightsDetachments(unittest.TestCase):
    def test_duty_before_all_allows_fall_back_shoot_and_charge(self):
        from warhammer40k_ai.roster.army import Army

        army = Army.with_detachment("Grey Knights", "Hallowed Conclave")
        army.faction_id = "GK"

        terminators = _make_unit(
            "Terminators",
            keywords=["TERMINATOR"],
            faction_keywords=["GREY KNIGHTS"],
        )
        army.add_unit(terminators)
        self.assertTrue(terminators.has_fell_back_and_shoot())
        self.assertTrue(terminators.can_charge_after_fall_back())

        strike = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        army.add_unit(strike)
        self.assertFalse(strike.has_fell_back_and_shoot())
        self.assertFalse(strike.can_charge_after_fall_back())

    def test_fury_of_titan_rerolls_after_deep_strike(self):
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.units import wargear as wargear_mod

        game, army_gk, army_enemy, player = _build_game()

        deep_strike = {
            "name": "Deep Strike",
            "description": "Deep Strike",
            "type": "Core",
            "parameter": "",
        }
        unit = _make_unit(
            "Interceptors",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
            abilities=[deep_strike],
        )
        army_gk.add_unit(unit)
        unit.reserve_status = "reserves"
        unit.deployed = True

        unit._finalize_reserves_arrival(turn=2, game_map=None)
        self.assertTrue(unit.special_rules.get("fury_of_titan_active"))
        self.assertEqual(unit.special_rules.get("fury_of_titan_expires_phase"), "FIGHT_PHASE")

        target = _make_unit(
            "Target",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_enemy.add_unit(target)

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

        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

        rolls = iter([1, 6, 1, 5])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = profile._hit_target_with_tracking(target, unit.models[0], attack_instance)
            self.assertEqual(int(hit_res["roll"]), 6)
            self.assertTrue(any("Fury of Titan" in x for x in hit_res.get("special_effects", [])))

            wound_res = profile._wound_target_with_tracking(target, unit.models[0], attack_instance)
            self.assertEqual(int(wound_res["roll"]), 5)
            self.assertTrue(any("Fury of Titan" in x for x in wound_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = original_roll

        game.event_system.publish("phase_end", player=player, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertNotIn("fury_of_titan_active", unit.special_rules)

    def test_mailed_fist_sets_fixed_advance_distance_for_grey_knights_vehicles(self):
        from warhammer40k_ai.engine.phase import BattleRoundPhases

        game, army_gk, _army_enemy, _player = _build_game(detachment_type="Sanctic Spearhead")
        game.phase = BattleRoundPhases.MOVEMENT_PHASE

        vehicle = _make_unit(
            "Nemesis Dreadknight",
            keywords=["VEHICLE"],
            faction_keywords=["GREY KNIGHTS"],
        )
        vehicle.deployed = True
        army_gk.add_unit(vehicle)

        effect = vehicle._get_advance_no_roll_effect()
        self.assertIsInstance(effect, dict)
        self.assertEqual(int(effect.get("distance", 0) or 0), 6)
        self.assertEqual(str(effect.get("expires_phase", "") or ""), "MOVEMENT_PHASE")
        self.assertEqual(str(effect.get("source", "") or ""), "Mailed Fist")

        infantry = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        infantry.deployed = True
        army_gk.add_unit(infantry)
        self.assertIsNone(infantry._get_advance_no_roll_effect())

    def test_mailed_fist_grants_ranged_assault_after_advancing(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        game, army_gk, _army_enemy, _player = _build_game(detachment_type="Sanctic Spearhead")
        vehicle = _make_unit(
            "Nemesis Dreadknight",
            keywords=["VEHICLE"],
            faction_keywords=["GREY KNIGHTS"],
        )
        vehicle.deployed = True
        army_gk.add_unit(vehicle)

        ranged_parent = SimpleNamespace(name="Heavy Psycannon", is_melee=lambda: False, is_ranged=lambda: True)
        ranged_profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "8",
                "AP": "-1",
                "D": "2",
                "description": "",
            },
            parent_wargear=ranged_parent,
        )

        melee_parent = SimpleNamespace(name="Greatsword", is_melee=lambda: True, is_ranged=lambda: False)
        melee_profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "10",
                "AP": "-2",
                "D": "3",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

        vehicle.round_state.advanced_this_round = False
        self.assertFalse(vehicle.can_shoot_after_advance(ranged_profile))

        vehicle.round_state.advanced_this_round = True
        self.assertTrue(vehicle.can_shoot_after_advance(ranged_profile))
        self.assertFalse(vehicle.can_shoot_after_advance(melee_profile))

    def test_hallowed_ground_melee_reroll_ones(self):
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.units import wargear as wargear_mod

        game, army_gk, army_enemy, _player = _build_game(detachment_type="Warpbane Task Force")

        unit = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        army_gk.add_unit(unit)

        target = _make_unit(
            "Target",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_enemy.add_unit(target)

        parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
        profile = WargearProfile(
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

        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

        rolls = iter([1, 5])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = profile._hit_target_with_tracking(target, unit.models[0], attack_instance)
            self.assertEqual(int(hit_res["roll"]), 5)
            self.assertTrue(any("Hallowed Ground" in x for x in hit_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = original_roll

    def test_hallowed_ground_melee_full_reroll_purifier(self):
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.units import wargear as wargear_mod

        game, army_gk, army_enemy, _player = _build_game(detachment_type="Warpbane Task Force")

        unit = _make_unit(
            "Purifier Squad",
            keywords=["PURIFIER SQUAD", "INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        army_gk.add_unit(unit)

        target = _make_unit(
            "Target",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_enemy.add_unit(target)

        parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
        profile = WargearProfile(
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

        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

        rolls = iter([2, 6])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = profile._hit_target_with_tracking(target, unit.models[0], attack_instance)
            self.assertEqual(int(hit_res["roll"]), 6)
            self.assertTrue(any("Hallowed Ground" in x for x in hit_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = original_roll

    def test_hallowed_ground_melee_full_reroll_wholly_within_deployment(self):
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.units import wargear as wargear_mod
        from warhammer40k_ai.engine.deployment import DeploymentManager

        game, army_gk, army_enemy, _player = _build_game(detachment_type="Warpbane Task Force")

        unit = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        army_gk.add_unit(unit)

        target = _make_unit(
            "Target",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_enemy.add_unit(target)

        dm = DeploymentManager(game, mission_name="Crucible of Battle")
        zones = dm.create_deployment_zones()
        defender_zone = next(z for z in zones if z.get("zone_type") == "defender")
        attacker_zone = next(z for z in zones if z.get("zone_type") == "attacker")
        game.deployment_zones = {
            army_gk.player.id: defender_zone,
            army_enemy.player.id: attacker_zone,
        }

        base = unit.models[0].model_base
        found = None
        for x in range(1, 60):
            for y in range(1, 44):
                if game.is_position_wholly_in_deployment_zone(float(x), float(y), base, army_gk.player.id):
                    found = (float(x), float(y))
                    break
            if found:
                break
        self.assertIsNotNone(found, "Failed to find a deployment zone point for Hallowed Ground test.")
        unit.models[0].set_location(found[0], found[1], 0.0, 0.0)

        parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
        profile = WargearProfile(
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

        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

        rolls = iter([2, 6])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = profile._hit_target_with_tracking(target, unit.models[0], attack_instance)
            self.assertEqual(int(hit_res["roll"]), 6)
            self.assertTrue(any("Hallowed Ground" in x for x in hit_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = original_roll

    def test_prescient_redeployment_queues_and_moves_unit_to_reserves(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.engine.phase import BattleRoundPhases
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command
        from warhammer40k_ai.utility.entity_ids import get_entity_id
        from warhammer40k_ai.utility.ability_support import ABILITY_GATE_OF_INFINITY

        game, army_gk, army_enemy, player = _build_game(detachment_type="Augurium Task Force")
        enemy_player = army_enemy.player
        army_gk.gate_of_infinity._army_has_gate = lambda: True

        gate = {
            "name": "Gate of Infinity",
            "id": ABILITY_GATE_OF_INFINITY,
            "description": "Gate of Infinity",
            "type": "Faction",
            "parameter": "",
        }
        unit = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
            abilities=[gate],
        )
        army_gk.add_unit(unit)
        army_gk.gate_of_infinity.get_eligible_units = lambda **_kwargs: [unit]

        enemy = _make_unit(
            "Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_enemy.add_unit(enemy)
        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(24.0, 0.0, 0.0, 0.0)
        game.map.units = [unit, enemy]
        game.rebuild_entity_registry()

        game.phase = BattleRoundPhases.FIGHT_PHASE
        game._on_phase_end_gate_of_infinity(player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)

        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game._on_phase_start_prescient_redeployment(player=player, phase=BattleRoundPhases.MOVEMENT_PHASE)

        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "prescient_redeployment"
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]

        unit_id = str(get_entity_id(unit) or "")
        option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "") == unit_id
        )
        result = resolve_decision_command(game, request, option.option_id, player_id=player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(str(getattr(unit, "reserve_status", "") or ""), "strategic_reserves")
        self.assertNotIn(unit, list(getattr(game.map, "units", []) or []))

    def test_prescient_redeployment_not_available_when_gate_was_maxed(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.engine.phase import BattleRoundPhases
        from warhammer40k_ai.utility.ability_support import ABILITY_GATE_OF_INFINITY

        game, army_gk, army_enemy, player = _build_game(detachment_type="Augurium Task Force")
        enemy_player = army_enemy.player
        army_gk.gate_of_infinity._army_has_gate = lambda: True

        gate = {
            "name": "Gate of Infinity",
            "id": ABILITY_GATE_OF_INFINITY,
            "description": "Gate of Infinity",
            "type": "Faction",
            "parameter": "",
        }
        unit = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
            abilities=[gate],
        )
        army_gk.add_unit(unit)
        game.map.units = [unit]
        game.rebuild_entity_registry()

        gate_mgr = army_gk.gate_of_infinity
        gate_mgr.begin_gate_window(game=game, turn_owner_id=enemy_player.id, max_units=1)
        gate_mgr.record_gate_selection_count(1)

        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game._on_phase_start_prescient_redeployment(player=player, phase=BattleRoundPhases.MOVEMENT_PHASE)

        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "prescient_redeployment"
        ]
        self.assertEqual(pending, [])

    def test_prescient_redeployment_requires_battle_round_two_or_later(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.engine.phase import BattleRoundPhases
        from warhammer40k_ai.utility.ability_support import ABILITY_GATE_OF_INFINITY

        game, army_gk, army_enemy, player = _build_game(detachment_type="Augurium Task Force")
        enemy_player = army_enemy.player
        game.turn = 1
        army_gk.gate_of_infinity._army_has_gate = lambda: True

        gate = {
            "name": "Gate of Infinity",
            "id": ABILITY_GATE_OF_INFINITY,
            "description": "Gate of Infinity",
            "type": "Faction",
            "parameter": "",
        }
        unit = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
            abilities=[gate],
        )
        army_gk.add_unit(unit)
        game.map.units = [unit]
        game.rebuild_entity_registry()

        gate_mgr = army_gk.gate_of_infinity
        gate_mgr.begin_gate_window(game=game, turn_owner_id=enemy_player.id, max_units=3)

        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game._on_phase_start_prescient_redeployment(player=player, phase=BattleRoundPhases.MOVEMENT_PHASE)

        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "prescient_redeployment"
        ]
        self.assertEqual(pending, [])

    def test_channelled_force_passed_test_applies_to_psychic_melee_only(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.engine.phase import BattleRoundPhases
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.utility.decision_utils import resolve_decision_value

        game, army_gk, army_enemy, player = _build_game(detachment_type="Banishers")
        unit = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        unit.pass_leadership_check = lambda: True
        unit.deployed = True
        army_gk.add_unit(unit)

        target = _make_unit(
            "Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_enemy.add_unit(target)
        game.rebuild_entity_registry()
        game.phase = BattleRoundPhases.FIGHT_PHASE

        game.event_system.publish("fight_unit_selected", unit=unit, selecting_player=player)

        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "channelled_force"
        )
        option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((getattr(opt, "payload", {}) or {}).get("choice", "") or "") == "LETHAL_HITS"
        )
        _value, apply_result = resolve_decision_value(game, request, option.option_id, player_id=player.id)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        psychic_parent = SimpleNamespace(name="Psychic Blade", is_melee=lambda: True, is_ranged=lambda: False)
        psychic_profile = WargearProfile(
            profile_name="Psychic",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "-2",
                "D": "2",
                "description": "",
            },
            parent_wargear=psychic_parent,
        )
        psychic_profile.is_psychic = lambda: True

        mundane_parent = SimpleNamespace(name="Mundane Blade", is_melee=lambda: True, is_ranged=lambda: False)
        mundane_profile = WargearProfile(
            profile_name="Mundane",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "-2",
                "D": "2",
                "description": "",
            },
            parent_wargear=mundane_parent,
        )
        mundane_profile.is_psychic = lambda: False

        psychic_attack = {}
        psychic_hit = psychic_profile._hit_target_with_tracking(
            target,
            unit.models[0],
            psychic_attack,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(psychic_attack.get("lethal_hit", False)))
        self.assertTrue(any("Lethal Hits" in str(s) for s in list(psychic_hit.get("special_effects", []) or [])))

        mundane_attack = {}
        mundane_profile._hit_target_with_tracking(
            target,
            unit.models[0],
            mundane_attack,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(mundane_attack.get("lethal_hit", False)))

    def test_channelled_force_failed_test_applies_no_bonus(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.engine.phase import BattleRoundPhases
        from warhammer40k_ai.utility.decision_utils import resolve_decision_value

        game, army_gk, army_enemy, player = _build_game(detachment_type="Banishers")
        unit = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        unit.pass_leadership_check = lambda: False
        unit.deployed = True
        army_gk.add_unit(unit)

        target = _make_unit(
            "Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_enemy.add_unit(target)
        game.rebuild_entity_registry()
        game.phase = BattleRoundPhases.FIGHT_PHASE

        game.event_system.publish("fight_unit_selected", unit=unit, selecting_player=player)

        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "channelled_force"
        )
        option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((getattr(opt, "payload", {}) or {}).get("choice", "") or "") == "SUSTAINED_HITS_1"
        )
        _value, apply_result = resolve_decision_value(game, request, option.option_id, player_id=player.id)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        self.assertFalse(bool(unit.special_rules.get("channelled_force_sustained_hits_active")))
        self.assertFalse(bool(unit.special_rules.get("channelled_force_lethal_hits_active")))


if __name__ == "__main__":
    unittest.main()
