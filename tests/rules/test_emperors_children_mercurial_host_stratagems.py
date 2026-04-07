from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

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
        movement: int = 6,
        toughness: int = 4,
        wounds: int = 3,
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
    wounds: int = 3,
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
    ec_army = Army.with_detachment("Emperor's Children", "Mercurial Host")
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


def _melee_profile(*, strength: int = 4, ap: int = 0, damage: int = 1):
    weapon = Wargear(
        {
            "name": "Test Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": str(int(damage)),
            "description": "",
        }
    )
    return weapon.profiles["default"]


class TestEmperorsChildrenMercurialHostStratagems(unittest.TestCase):
    def test_capricious_reactions_queues_and_applies_hit_penalty(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        defender = _make_unit(
            "Noise Marines",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(defender)
        enemy_army.add_unit(enemy)
        _place_unit(game, defender, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[defender])

        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "CAPRICIOUS REACTIONS" for r in pending))

        ok = p1.stratagems.use(
            "CAPRICIOUS REACTIONS",
            unit=defender,
            attacking_unit=enemy,
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        hit_mods = list(defender.special_rules.get("defensive_hit_mods", []) or [])
        self.assertTrue(any(int(entry.get("value", 0) or 0) == 1 for entry in hit_mods if isinstance(entry, dict)))

    def test_combat_stimms_queues_and_applies_wound_penalty(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        defender = _make_unit(
            "Chosen",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy Fighters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(defender)
        enemy_army.add_unit(enemy)
        _place_unit(game, defender, 10.0, 10.0)
        _place_unit(game, enemy, 11.5, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[defender])

        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "COMBAT STIMMS" for r in pending))

        ok = p1.stratagems.use(
            "COMBAT STIMMS",
            unit=defender,
            attacking_unit=enemy,
            phase_name="Fight phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        wound_mods = list(defender.special_rules.get("defensive_wound_mods", []) or [])
        self.assertTrue(any(int(entry.get("value", 0) or 0) == 1 for entry in wound_mods if isinstance(entry, dict)))

    def test_honour_the_prince_sets_fixed_advance_and_cleans_up(self):
        game, p1, _p2, ec_army, _enemy_army = _build_game()
        unit = _make_unit(
            "Legionaries",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            movement=6,
        )
        ec_army.add_unit(unit)
        _place_unit(game, unit, 10.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        ok = p1.stratagems.use("HONOUR THE PRINCE", unit=unit, phase_name="Movement phase")
        self.assertTrue(ok)

        effect = unit._get_advance_no_roll_effect()
        self.assertIsNotNone(effect)
        self.assertEqual(int(effect.get("distance", 0) or 0), 6)

        roll = unit.prepare_advance()
        self.assertEqual(int(roll or 0), 6)
        self.assertEqual(int(getattr(unit.round_state, "advance_roll", 0) or 0), 6)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        self.assertIsNone(unit._get_advance_no_roll_effect())

    def test_honour_the_prince_requires_movement_trigger_window(self):
        game, p1, _p2, ec_army, _enemy_army = _build_game()
        unit = _make_unit(
            "Legionaries",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        ec_army.add_unit(unit)
        _place_unit(game, unit, 10.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        unit.round_state.moved_this_round = True
        ok = p1.stratagems.use("HONOUR THE PRINCE", unit=unit, phase_name="Movement phase")
        self.assertFalse(ok)

    def test_violent_excess_grants_melee_sustained_hits_until_phase_end(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        attacker = _make_unit(
            "Noise Marines",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        defender = _make_unit(
            "Enemy",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(attacker)
        enemy_army.add_unit(defender)
        _place_unit(game, attacker, 10.0, 10.0)
        _place_unit(game, defender, 11.5, 10.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        ok = p1.stratagems.use("VIOLENT EXCESS", unit=attacker, phase_name="Fight phase")
        self.assertTrue(ok)

        profile = _melee_profile()
        attack_instance = {
            "target_model": defender.models[0],
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            hit = profile._hit_target_with_tracking(defender, attacker.models[0], attack_instance)
        self.assertTrue(bool(hit.get("hit")))
        self.assertEqual(int(attack_instance.get("sustained_hit", 0) or 0), 1)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertFalse(bool(attacker.special_rules.get("mercurial_violent_excess_active", False)))

    def test_dark_vigour_queues_and_creates_reactive_move_decision(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        target = _make_unit(
            "Legionaries",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy Movers",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(target)
        enemy_army.add_unit(enemy)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, enemy, 17.0, 10.0)

        _set_phase(game, p2, "MOVEMENT_PHASE", 1)

        no_trigger = p1.stratagems.use("DARK VIGOUR", unit=target, enemy_unit=enemy, phase_name="Movement phase")
        self.assertFalse(no_trigger)

        game.event_system.publish("unit_move_ended", unit=enemy, action="move")
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "DARK VIGOUR" for r in pending))

        ok = p1.stratagems.use("DARK VIGOUR", phase_name="Movement phase", dequeue=True)
        self.assertTrue(ok)

        move_reqs = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
        ]
        self.assertTrue(move_reqs)
        ctx = dict(getattr(move_reqs[0], "context", {}) or {})
        self.assertEqual(int(ctx.get("max_distance", 0) or 0), 6)
        self.assertEqual(str(ctx.get("movement_type", "") or ""), "reactive")
        self.assertEqual(str(ctx.get("reactive_move_kind", "") or ""), "dark_vigour")

    def test_cruel_raiders_queues_and_places_unit_into_strategic_reserves(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        raiders = _make_unit(
            "Raiders",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy_far = _make_unit(
            "Enemy Far",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        enemy_close = _make_unit(
            "Enemy Close",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(raiders)
        enemy_army.add_unit(enemy_far)
        enemy_army.add_unit(enemy_close)
        _place_unit(game, raiders, 2.0, 20.0)
        _place_unit(game, enemy_far, 20.0, 20.0)
        _place_unit(game, enemy_close, 4.2, 20.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending_with_close_enemy = p1.stratagems.get_pending_reactions()
        self.assertFalse(any(str(r.get("stratagem", "")).upper() == "CRUEL RAIDERS" for r in pending_with_close_enemy))

        for model in enemy_close.models:
            model._wounds = 0
        enemy_close.deployed = False
        enemy_close.reserve_status = "destroyed"
        if enemy_close in list(getattr(game.map, "units", []) or []):
            game.map.units.remove(enemy_close)

        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "CRUEL RAIDERS" for r in pending))

        ok = p1.stratagems.use("CRUEL RAIDERS", unit=raiders, phase_name="Fight phase", dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(str(getattr(raiders, "reserve_status", "")), "strategic_reserves")
        self.assertNotIn(raiders, list(getattr(game.map, "units", []) or []))


if __name__ == "__main__":
    unittest.main()
