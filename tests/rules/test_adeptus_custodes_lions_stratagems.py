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

    army1 = Army("Adeptus Custodes", "Lions of the Emperor")
    army1.faction_id = "AC"
    army2 = Army("Enemy", "Other")
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

    def test_manoeuvre_and_fire_allows_fall_back_shoot(self):
        game, p1, _p2, army1, _army2 = _build_game()
        unit = _make_unit(
            "Custodian Guard",
            keywords=["ADEPTUS CUSTODES", "INFANTRY"],
            faction_keywords=["ADEPTUS CUSTODES"],
        )
        army1.add_unit(unit)
        unit.deployed = True
        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 0

        ok = p1.stratagems.use("MANOEUVRE AND FIRE", unit=unit, phase_name="Movement phase")
        self.assertTrue(ok)
        self.assertTrue(unit.has_fell_back_and_shoot())

    def test_peerless_warrior_adds_melee_attacks(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Custodian Guard",
            keywords=["ADEPTUS CUSTODES", "INFANTRY"],
            faction_keywords=["ADEPTUS CUSTODES"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)

        game.phase = SimpleNamespace(name="FIGHT_PHASE")
        game.current_player_index = 0

        ok = p1.stratagems.use(
            "PEERLESS WARRIOR",
            unit=unit,
            phase_name="Fight phase",
            candidates=[unit],
        )
        self.assertTrue(ok)

        melee_parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

        captured = []
        original_summary = profile._print_attack_summary
        profile._print_attack_summary = lambda result: captured.append(result)
        try:
            profile.attack(enemy, unit.models[0], game_map=None)
        finally:
            profile._print_attack_summary = original_summary

        self.assertTrue(captured, "Expected attack summary to capture an AttackResult")
        attack_result = captured[0]
        self.assertEqual(int(attack_result.attacks_rolled), 2)
        self.assertTrue(any("Peerless Warrior" in x for x in attack_result.attacks_special_modifiers))

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
        self.assertEqual(ctx.get("max_distance"), 6)
        self.assertEqual(ctx.get("movement_type"), "reactive")
        self.assertEqual(ctx.get("reactive_move_kind"), "swift_as_the_eagle")
        self.assertTrue(ctx.get("reactive_move_allow_engagement_range"))


if __name__ == "__main__":
    unittest.main()
