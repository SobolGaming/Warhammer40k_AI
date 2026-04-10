import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.utility import dice as dice_module


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
    ):
        self.name = name
        self.faction_data = {"name": "Adeptus Custodes" if "ADEPTUS CUSTODES" in [k.upper() for k in list(keywords or [])] else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "2",
                "W": "4",
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    unit = Unit(datasheet)
    return unit


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army.with_detachment("Adeptus Custodes", "Lions of the Emperor")
    army1.faction_id = "AC"
    army2 = Army.with_detachment("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("Custodes", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 5
    p2.command_points = 5
    army1.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, p1, p2, army1, army2


def _place_unit(game, unit, x, y):
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


class TestAdeptusCustodesLionsStratagems(unittest.TestCase):
    def test_defiant_to_the_last_defers_fight_on_death(self):
        game, p1, p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Custodian Guard",
            keywords=["ADEPTUS CUSTODES", "INFANTRY", "CHARACTER"],
            faction_keywords=["ADEPTUS CUSTODES"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        unit.round_state.fought_this_phase = False
        game.phase = SimpleNamespace(name="FIGHT_PHASE")
        game.current_player_index = 1

        ok = p1.stratagems.use(
            "DEFIANT TO THE LAST",
            unit=unit,
            attacking_unit=enemy,
            candidates=[unit],
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertTrue(unit.special_rules.get("defiant_to_last_active"))

        original_roll = dice_module.get_roll
        dice_module.get_roll = lambda _d: 2
        try:
            model = unit.models[0]
            model._wounds = 0
            unit._handle_model_destroyed(model, game.map)
        finally:
            dice_module.get_roll = original_roll

        pending = getattr(unit, "_defiant_to_last_pending_models", [])
        self.assertIn(unit.models[0], pending)

        with patch.object(unit, "_try_fight_on_death") as mocked:
            unit.end_attack_resolution(game_map=game.map)
        self.assertEqual(mocked.call_count, 1)
        self.assertFalse(getattr(unit, "_defiant_to_last_pending_models", []))

    def test_manoeuvre_and_fire_requires_fall_back_trigger_and_allows_shoot_and_charge(self):
        game, p1, _p2, army1, _army2 = _build_game()
        unit = _make_unit(
            "Custodian Guard",
            keywords=["ADEPTUS CUSTODES", "INFANTRY"],
            faction_keywords=["ADEPTUS CUSTODES"],
        )
        army1.add_unit(unit)
        _place_unit(game, unit, 5.0, 5.0)
        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 0

        ok = p1.stratagems.use("MANOEUVRE AND FIRE", unit=unit, phase_name="Movement phase")
        self.assertFalse(ok)

        unit.round_state.fell_back_this_round = True
        game.event_system.publish("unit_move_ended", unit=unit, action="fall_back")
        pending = [r for r in p1.stratagems.get_pending_reactions() if r.get("stratagem") == "MANOEUVRE AND FIRE"]
        self.assertTrue(pending)

        ok = p1.stratagems.use("MANOEUVRE AND FIRE", unit=unit, phase_name="Movement phase", dequeue=True)
        self.assertTrue(ok)
        self.assertTrue(unit.has_fell_back_and_shoot())
        self.assertTrue(unit.can_charge_after_fall_back())

        game.turn += 1
        self.assertFalse(unit.has_fell_back_and_shoot())
        self.assertFalse(unit.can_charge_after_fall_back())

    def test_peerless_warrior_grants_melee_precision_and_works_in_opponent_fight_phase(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Custodian Guard",
            keywords=["ADEPTUS CUSTODES", "INFANTRY"],
            faction_keywords=["ADEPTUS CUSTODES"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        unit.models[0].wargear = [SimpleNamespace(name="Test Blade", is_melee=lambda: True)]
        _place_unit(game, unit, 5.0, 5.0)
        _place_unit(game, enemy, 10.0, 5.0)

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.phase = phase
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=_p2, phase=phase)
        unit.round_state.fought_this_phase = False
        game.event_system.publish("fight_unit_selected", unit=unit, selecting_player=p1)

        pending = [r for r in p1.stratagems.get_pending_reactions() if r.get("stratagem") == "PEERLESS WARRIOR"]
        self.assertTrue(pending)

        ok = p1.stratagems.use(
            "PEERLESS WARRIOR",
            unit=unit,
            phase_name="Fight phase",
            candidates=[unit],
            selecting_player=p1,
            dequeue=True,
        )
        self.assertTrue(ok)

        bonuses = unit.models[0].get_temporary_weapon_keyword_bonuses("Test Blade")
        self.assertTrue(
            any(
                str(item.get("keyword", "") or "").strip().upper() == "PRECISION"
                and str(item.get("attack_type", "") or "").strip().lower() == "melee"
                for item in list(bonuses or [])
            )
        )
        game.event_system.publish("phase_end", player=_p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertEqual(unit.models[0].get_temporary_weapon_keyword_bonuses("Test Blade"), [])

    def test_swift_as_the_eagle_queues_reactive_move(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT

        game, p1, p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Custodian Guard",
            keywords=["ADEPTUS CUSTODES", "INFANTRY"],
            faction_keywords=["ADEPTUS CUSTODES"],
        )
        enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)

        _place_unit(game, unit, 5.0, 5.0)
        _place_unit(game, enemy, 10.0, 5.0)

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.current_player_index = 1
        game.phase = phase
        game.event_system.publish("phase_start", player=p2, phase=phase)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[unit])
        game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={unit: 1})

        reactions = [r for r in p1.stratagems.get_pending_reactions() if r.get("stratagem") == "SWIFT AS THE EAGLE"]
        self.assertTrue(reactions)

        with patch.object(dice_module, "get_roll", return_value=4):
            ok = p1.stratagems.use(
                "SWIFT AS THE EAGLE",
                unit=unit,
                enemy_unit=enemy,
                phase_name="Shooting phase",
                candidates=[unit],
                dequeue=True,
            )
        self.assertTrue(ok)

        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_MOVE_UNIT
        ]
        self.assertTrue(pending)
        ctx = dict(getattr(pending[0], "context", {}) or {})
        self.assertEqual(ctx.get("max_distance"), 4)
        self.assertEqual(ctx.get("movement_type"), "reactive")
        self.assertEqual(ctx.get("reactive_move_kind"), "swift_as_the_eagle")
        self.assertFalse(bool(ctx.get("reactive_move_allow_engagement_range", False)))

    def test_swift_as_the_eagle_excludes_vehicle_targets(self):
        game, p1, p2, army1, army2 = _build_game()
        vehicle = _make_unit(
            "Caladius Grav-Tank",
            keywords=["ADEPTUS CUSTODES", "VEHICLE"],
            faction_keywords=["ADEPTUS CUSTODES"],
        )
        enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(vehicle)
        army2.add_unit(enemy)

        _place_unit(game, vehicle, 5.0, 5.0)
        _place_unit(game, enemy, 10.0, 5.0)

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.current_player_index = 1
        game.phase = phase
        game.event_system.publish("phase_start", player=p2, phase=phase)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[vehicle])
        game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={vehicle: 1})

        reactions = [r for r in p1.stratagems.get_pending_reactions() if r.get("stratagem") == "SWIFT AS THE EAGLE"]
        self.assertFalse(reactions)
        ok = p1.stratagems.use(
            "SWIFT AS THE EAGLE",
            unit=vehicle,
            enemy_unit=enemy,
            phase_name="Shooting phase",
            candidates=[vehicle],
        )
        self.assertFalse(ok)

    def test_lions_stratagem_descriptors_registered(self):
        from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor

        expected = {
            "000009988003": ("DEFIANT TO THE LAST", "fight_on_death_roll"),
            "000009988002": ("GILDED CHAMPION", "grant_one_extra_use_of_same_once_per_battle_ability"),
            "000009988006": ("MANOEUVRE AND FIRE", "eligible_to_shoot_and_charge_after_fall_back"),
            "000009988004": ("PEERLESS WARRIOR", "grant_precision_to_melee_weapons"),
            "000009988007": ("SWIFT AS THE EAGLE", "reactive_normal_move_d6"),
            "000009988005": ("UNLEASH THE LIONS", "split_unit_into_single_model_units"),
        }
        for stratagem_id, (expected_name, expected_effect) in expected.items():
            by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name)
            by_name = get_stratagem_tool_descriptor(name=expected_name)
            self.assertIsNotNone(by_id)
            self.assertIsNotNone(by_name)
            self.assertEqual(by_id.name, expected_name)
            self.assertEqual(by_name.name, expected_name)
            self.assertEqual(by_id.effect, expected_effect)


if __name__ == "__main__":
    unittest.main()
