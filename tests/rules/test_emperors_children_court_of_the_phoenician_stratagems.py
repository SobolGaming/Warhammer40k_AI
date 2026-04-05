from __future__ import annotations

from types import SimpleNamespace
import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Emperor's Children",
        faction_keywords=None,
        keywords=None,
        toughness: int = 4,
        wounds: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["EMPEROR'S CHILDREN"] if faction_name == "Emperor's Children" else ["ENEMY"]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Emperor's Children",
    faction_keywords=None,
    keywords=None,
    toughness: int = 4,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ec_army = Army("Emperor's Children", "Court of the Phoenician")
    ec_army.faction_id = "EC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=ec_army)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 10
    p2.command_points = 10
    game.turn = 1
    ec_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, ec_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _ranged_profile(*, strength: int = 4, ap: int = 0):
    weapon = Wargear(
        {
            "name": "Test Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


class TestEmperorsChildrenCourtOfThePhoenicianStratagems(unittest.TestCase):
    def test_close_quarters_excruciation_applies_within_12_only(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        shooter = _make_unit(
            "Noise Marines",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        near_target = _make_unit(
            "Near Target",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            toughness=5,
        )
        far_target = _make_unit(
            "Far Target",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            toughness=5,
        )
        ec_army.add_unit(shooter)
        enemy_army.add_unit(near_target)
        enemy_army.add_unit(far_target)
        _place_unit(game, shooter, 10.0, 10.0)
        _place_unit(game, near_target, 20.0, 10.0)
        _place_unit(game, far_target, 30.0, 10.0)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        ok = p1.stratagems.use("CLOSE-QUARTERS EXCRUCIATION", unit=shooter, phase_name="Shooting phase")
        self.assertTrue(ok)

        profile = _ranged_profile(strength=4, ap=0)
        attacker = shooter.models[0]
        self.assertEqual(profile.get_effective_ap(attacker, near_target), -1)
        self.assertEqual(profile.get_effective_ap(attacker, far_target), 0)

        near_wound = profile._wound_target_with_tracking(
            near_target,
            attacker,
            {"_aura_attack_mods": _aura_stub()},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        far_wound = profile._wound_target_with_tracking(
            far_target,
            attacker,
            {"_aura_attack_mods": _aura_stub()},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(near_wound.get("wound")))
        self.assertFalse(bool(far_wound.get("wound")))

    def test_contemptuous_disregard_reacts_and_applies_conditional_wound_penalty(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        defender = _make_unit(
            "Legionaries",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            toughness=4,
        )
        attacker_unit = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(defender)
        enemy_army.add_unit(attacker_unit)
        _place_unit(game, defender, 10.0, 10.0)
        _place_unit(game, attacker_unit, 16.0, 10.0)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=attacker_unit, target_units=[defender])
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "CONTEMPTUOUS DISREGARD" for r in pending))

        ok = p1.stratagems.use(
            "CONTEMPTUOUS DISREGARD",
            unit=defender,
            attacking_unit=attacker_unit,
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)

        profile = _ranged_profile(strength=5, ap=0)
        wound_result = profile._wound_target_with_tracking(
            defender,
            attacker_unit.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(wound_result.get("wound")))

    def test_prideful_superiority_grants_rerolls_only_vs_character(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        unit = _make_unit(
            "Flawless Blades",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        char_target = _make_unit(
            "Enemy Character",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY", "CHARACTER"],
        )
        non_char_target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(unit)
        enemy_army.add_unit(char_target)
        enemy_army.add_unit(non_char_target)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, char_target, 13.0, 10.0)
        _place_unit(game, non_char_target, 15.0, 10.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        unit.round_state.fought_this_phase = False
        ok = p1.stratagems.use("PRIDEFUL SUPERIORITY", unit=unit, phase_name="Fight phase")
        self.assertTrue(ok)

        hit_vs_char = unit.get_unit_hit_reroll_modifiers("melee", target=char_target)
        wound_vs_char = unit.get_unit_wound_reroll_modifiers("melee", target=char_target)
        self.assertTrue(bool(hit_vs_char.get("reroll_hit_full")))
        self.assertTrue(bool(wound_vs_char.get("reroll_wound_full")))

        hit_vs_non_char = unit.get_unit_hit_reroll_modifiers("melee", target=non_char_target)
        wound_vs_non_char = unit.get_unit_wound_reroll_modifiers("melee", target=non_char_target)
        self.assertFalse(bool(hit_vs_non_char.get("reroll_hit_full")))
        self.assertFalse(bool(wound_vs_non_char.get("reroll_wound_full")))

    def test_sinuous_breach_sets_and_cleans_phase_move_terrain_flags(self):
        game, p1, _p2, ec_army, _enemy_army = _build_game()
        daemon = _make_unit(
            "Daemon Unit",
            keywords=["INFANTRY", "DAEMON", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        ec_army.add_unit(daemon)
        _place_unit(game, daemon, 10.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        daemon.round_state.moved_this_round = False
        ok_move = p1.stratagems.use("SINUOUS BREACH", unit=daemon, phase_name="Movement phase")
        self.assertTrue(ok_move)
        self.assertIn("move", list(daemon.special_rules.get("bearer_unit_phase_move_terrain_only_types", []) or []))
        self.assertIn("advance", list(daemon.special_rules.get("bearer_unit_phase_move_terrain_only_types", []) or []))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        self.assertFalse(bool(daemon.special_rules.get("court_sinuous_breach_active")))
        self.assertNotIn("move", list(daemon.special_rules.get("bearer_unit_phase_move_terrain_only_types", []) or []))
        self.assertNotIn("advance", list(daemon.special_rules.get("bearer_unit_phase_move_terrain_only_types", []) or []))

        _set_phase(game, p1, "CHARGE_PHASE", 0)
        daemon.round_state.attempted_charge_this_round = False
        ok_charge = p1.stratagems.use("SINUOUS BREACH", unit=daemon, phase_name="Charge phase")
        self.assertTrue(ok_charge)
        self.assertIn("charge", list(daemon.special_rules.get("bearer_unit_phase_move_terrain_only_types", []) or []))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="CHARGE_PHASE"))
        self.assertNotIn("charge", list(daemon.special_rules.get("bearer_unit_phase_move_terrain_only_types", []) or []))

    def test_euphoric_inspiration_grants_charge_reroll_aura(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        source = _make_unit(
            "Daemon Prince",
            keywords=["MONSTER", "DAEMON", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        nearby = _make_unit(
            "Noise Marines",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        far = _make_unit(
            "Far Unit",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(source)
        ec_army.add_unit(nearby)
        ec_army.add_unit(far)
        enemy_army.add_unit(enemy)
        _place_unit(game, source, 10.0, 10.0)
        _place_unit(game, nearby, 15.0, 10.0)
        _place_unit(game, far, 22.0, 10.0)
        _place_unit(game, enemy, 30.0, 10.0)

        _set_phase(game, p1, "CHARGE_PHASE", 0)
        ok = p1.stratagems.use("EUPHORIC INSPIRATION", unit=source, phase_name="Charge phase")
        self.assertTrue(ok)
        self.assertTrue(nearby.can_reroll_charge_roll(target_unit=enemy, game_map=game.map, game=game))
        self.assertFalse(far.can_reroll_charge_roll(target_unit=enemy, game_map=game.map, game=game))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="CHARGE_PHASE"))
        self.assertFalse(nearby.can_reroll_charge_roll(target_unit=enemy, game_map=game.map, game=game))

    def test_catalytic_stimulus_requires_lost_wounds_and_queues_reactive_move(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        reacting_unit = _make_unit(
            "Legionaries",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            wounds=4,
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(reacting_unit)
        enemy_army.add_unit(enemy)
        _place_unit(game, reacting_unit, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        self.assertFalse(
            p1.stratagems.use(
                "CATALYTIC STIMULUS",
                unit=reacting_unit,
                enemy_unit=enemy,
                phase_name="Shooting phase",
            )
        )

        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[reacting_unit])
        game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={reacting_unit: 1})
        pending = [
            r
            for r in p1.stratagems.get_pending_reactions()
            if str(r.get("stratagem", "")).upper() == "CATALYTIC STIMULUS"
        ]
        self.assertFalse(pending)

        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[reacting_unit])
        reacting_unit.models[0].wounds = int(reacting_unit.models[0].wounds) - 1
        game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={reacting_unit: 1})
        pending = [
            r
            for r in p1.stratagems.get_pending_reactions()
            if str(r.get("stratagem", "")).upper() == "CATALYTIC STIMULUS"
        ]
        self.assertTrue(pending)

        ok = p1.stratagems.use(
            "CATALYTIC STIMULUS",
            phase_name="Shooting phase",
            max_distance=4,
            dequeue=True,
        )
        self.assertTrue(ok)
        queued_moves = [
            req
            for req in list(game.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_MOVE_UNIT
        ]
        self.assertTrue(queued_moves)
        ctx = dict(getattr(queued_moves[0], "context", {}) or {})
        self.assertEqual(int(ctx.get("max_distance", 0) or 0), 4)
        self.assertEqual(str(ctx.get("movement_type", "") or ""), "reactive")
        self.assertEqual(str(ctx.get("reactive_move_kind", "") or ""), "catalytic_stimulus")


if __name__ == "__main__":
    unittest.main()
