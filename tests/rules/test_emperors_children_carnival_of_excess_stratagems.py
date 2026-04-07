from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Emperor's Children",
        faction_keywords=None,
        keywords=None,
        movement: int = 6,
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
                "M": str(int(movement)),
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
    movement: int = 6,
    toughness: int = 4,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ec_army = Army.with_detachment("Emperor's Children", "Carnival of Excess")
    ec_army.faction_id = "EC"
    enemy_army = Army.with_detachment("Enemy", "Other")
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


def _pending_reactions_by_name(player: Player, name: str):
    target = str(name or "").strip().upper()
    return [
        r
        for r in list(player.stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == target
    ]


class TestEmperorsChildrenCarnivalOfExcessStratagems(unittest.TestCase):
    def test_sustained_by_agony_reacts_and_heals_legions_of_excess_target(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        source = _make_unit(
            "Noise Marines",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "SLAANESH"],
        )
        target = _make_unit(
            "Possessed",
            keywords=["INFANTRY", "LEGIONS OF EXCESS", "SLAANESH"],
            wounds=4,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )

        ec_army.add_unit(source)
        ec_army.add_unit(target)
        enemy_army.add_unit(enemy)
        _place_unit(game, source, 10.0, 10.0)
        _place_unit(game, target, 14.0, 10.0)
        _place_unit(game, enemy, 11.0, 12.0)

        target.models[0].wounds = 1

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        game.event_system.publish("unit_destroyed", unit=enemy, destroyed_by_unit=source, last_model=enemy.models[0])
        pending = _pending_reactions_by_name(p1, "SUSTAINED BY AGONY")
        self.assertTrue(pending)

        ok = p1.stratagems.use("SUSTAINED BY AGONY", phase_name="Fight phase", dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(target.models[0].wounds or 0), 4)
        self.assertEqual(int(p1.command_points or 0), 9)

    def test_ecstatic_slaughter_reacts_and_attempts_out_of_turn_charge(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        source = _make_unit(
            "Daemon Source",
            keywords=["INFANTRY", "LEGIONS OF EXCESS", "SLAANESH"],
        )
        charger = _make_unit(
            "EC Charger",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "SLAANESH"],
        )
        enemy_destroyed = _make_unit(
            "Destroyed Enemy",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        enemy_charge_target = _make_unit(
            "Charge Target",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )

        ec_army.add_unit(source)
        ec_army.add_unit(charger)
        enemy_army.add_unit(enemy_destroyed)
        enemy_army.add_unit(enemy_charge_target)
        _place_unit(game, source, 10.0, 10.0)
        _place_unit(game, charger, 14.0, 10.0)
        _place_unit(game, enemy_destroyed, 11.0, 12.0)
        _place_unit(game, enemy_charge_target, 18.0, 10.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        game.event_system.publish(
            "unit_destroyed",
            unit=enemy_destroyed,
            destroyed_by_unit=source,
            last_model=enemy_destroyed.models[0],
        )
        pending = _pending_reactions_by_name(p1, "ECSTATIC SLAUGHTER")
        self.assertTrue(pending)

        with patch.object(game, "attempt_charge", return_value=True) as attempt_charge_mock:
            ok = p1.stratagems.use(
                "ECSTATIC SLAUGHTER",
                enemy_unit=enemy_charge_target,
                phase_name="Fight phase",
                dequeue=True,
            )

        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        attempt_charge_mock.assert_called_once()
        args, kwargs = attempt_charge_mock.call_args
        self.assertIs(args[0], charger)
        self.assertIs(args[1], enemy_charge_target)
        self.assertTrue(bool(kwargs.get("out_of_turn")))

    def test_sycophantic_surge_allows_charge_after_advance_but_enforces_target_condition(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        sycophant = _make_unit(
            "Sycophant Unit",
            keywords=["INFANTRY", "LEGIONS OF EXCESS", "SLAANESH"],
        )
        ec_anchor = _make_unit(
            "EC Anchor",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "SLAANESH"],
        )
        enemy_good = _make_unit(
            "Engaged Enemy",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        enemy_bad = _make_unit(
            "Not Engaged Enemy",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )

        ec_army.add_unit(sycophant)
        ec_army.add_unit(ec_anchor)
        enemy_army.add_unit(enemy_good)
        enemy_army.add_unit(enemy_bad)
        _place_unit(game, sycophant, 20.0, 20.0)
        _place_unit(game, ec_anchor, 24.0, 20.0)
        _place_unit(game, enemy_good, 25.5, 20.0)
        _place_unit(game, enemy_bad, 23.0, 25.0)

        sycophant.round_state.advanced_this_round = True

        _set_phase(game, p1, "CHARGE_PHASE", 0)
        ok = p1.stratagems.use(
            "SYCOPHANTIC SURGE",
            unit=sycophant,
            phase_name="Charge phase",
        )
        self.assertTrue(ok)
        self.assertTrue(sycophant.can_charge_after_advance())

        denied = game.declare_charge(sycophant, [enemy_bad], out_of_turn=False)
        self.assertIsNone(denied)
        self.assertEqual(int(p1.command_points or 0), 9)

    def test_uncanny_reactions_queues_and_applies_defensive_hit_penalty(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        defender = _make_unit(
            "Defender",
            keywords=["INFANTRY", "SLAANESH", "EMPEROR'S CHILDREN"],
        )
        attacker = _make_unit(
            "Shooter",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )

        ec_army.add_unit(defender)
        enemy_army.add_unit(attacker)
        _place_unit(game, defender, 10.0, 30.0)
        _place_unit(game, attacker, 18.0, 30.0)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])
        pending = _pending_reactions_by_name(p1, "UNCANNY REACTIONS")
        self.assertTrue(pending)

        ok = p1.stratagems.use("UNCANNY REACTIONS", phase_name="Shooting phase", dequeue=True)
        self.assertTrue(ok)

        mods = list(defender.special_rules.get("defensive_hit_mods", []) or [])
        self.assertTrue(any(str(m.get("source", "")).strip().upper() == "UNCANNY REACTIONS" for m in mods))
        self.assertEqual(int(p1.command_points or 0), 9)

    def test_violent_crescendo_applies_and_cleans_fight_phase_overrides(self):
        game, p1, _p2, ec_army, _enemy_army = _build_game()
        fighter = _make_unit(
            "Fight Unit",
            keywords=["INFANTRY", "SLAANESH", "EMPEROR'S CHILDREN"],
        )
        ec_army.add_unit(fighter)
        _place_unit(game, fighter, 30.0, 10.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        fighter.round_state.fought_this_phase = False
        ok = p1.stratagems.use("VIOLENT CRESCENDO", unit=fighter, phase_name="Fight phase")
        self.assertTrue(ok)

        self.assertEqual(float(fighter.special_rules.get("bearer_unit_pile_in_distance_override", 0.0) or 0.0), 6.0)
        self.assertEqual(float(fighter.special_rules.get("stratagem_consolidate_distance_override", 0.0) or 0.0), 6.0)
        self.assertEqual(str(fighter.get_choreographer_of_war_source() or ""), "VIOLENT CRESCENDO")

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))

        self.assertNotIn("carnival_violent_crescendo_active", dict(fighter.special_rules or {}))
        self.assertNotIn("stratagem_choreographer_of_war_source", dict(fighter.special_rules or {}))
        self.assertEqual(str(fighter.get_choreographer_of_war_source() or ""), "")
        self.assertEqual(int(p1.command_points or 0), 8)

    def test_dark_apparitions_reacts_and_grants_next_movement_deep_strike_constraints(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        daemonettes = _make_unit(
            "Daemonettes",
            keywords=["INFANTRY", "DAEMONETTES", "LEGIONS OF EXCESS", "SLAANESH"],
        )
        ec_anchor = _make_unit(
            "EC Anchor",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "SLAANESH"],
        )
        enemy = _make_unit(
            "Enemy",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )

        ec_army.add_unit(daemonettes)
        ec_army.add_unit(ec_anchor)
        enemy_army.add_unit(enemy)
        _place_unit(game, daemonettes, 10.0, 40.0)
        _place_unit(game, ec_anchor, 40.0, 20.0)
        _place_unit(game, enemy, 50.0, 20.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending = _pending_reactions_by_name(p1, "DARK APPARITIONS")
        self.assertTrue(pending)

        ok = p1.stratagems.use("DARK APPARITIONS", phase_name="Fight phase", dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(str(getattr(daemonettes, "reserve_status", "") or ""), "strategic_reserves")

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        self.assertTrue(daemonettes.has_deep_strike())
        self.assertEqual(float(daemonettes.get_deep_strike_min_distance_override() or 0.0), 6.0)
        self.assertEqual(float(daemonettes.get_dark_apparitions_friendly_distance_requirement(game=game) or 0.0), 9.0)

        near_positions = [(42.0, 20.0, 0.0, 0.0)]
        far_positions = [(60.0, 20.0, 0.0, 0.0)]
        self.assertTrue(daemonettes.is_dark_apparitions_arrival_valid(near_positions, game=game, game_map=game.map))
        self.assertFalse(daemonettes.is_dark_apparitions_arrival_valid(far_positions, game=game, game_map=game.map))
        self.assertEqual(int(p1.command_points or 0), 8)


if __name__ == "__main__":
    unittest.main()
