import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        wounds="4",
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
                "W": wounds,
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


def _make_unit(name, *, keywords=None, faction_keywords=None, wounds="4"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        wounds=wounds,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("World Eaters", "Possessed Slaughterband")
    army1.faction_id = "WE"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    game.turn = 1
    p1.command_points = 6
    p2.command_points = 6
    return game, p1, p2, army1, army2


def _place_unit(game, unit, x, y):
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


class _MeleeWargear:
    name = "Test Claws"

    @staticmethod
    def is_melee():
        return True

    @staticmethod
    def is_ranged():
        return False


def _melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    return WargearProfile(
        "Test Claws",
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=_MeleeWargear(),
    )


class TestWorldEatersPossessedSlaughterbandStratagems(unittest.TestCase):
    def test_horrifying_violence_queues_at_opponent_command_phase_start(self):
        game, p1, p2, army1, army2 = _build_game()
        possessed = _make_unit(
            "Possessed",
            keywords=["INFANTRY", "POSSESSED"],
            faction_keywords=["WORLD EATERS"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(possessed)
        army2.add_unit(enemy)
        _place_unit(game, possessed, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        phase = SimpleNamespace(name="COMMAND_PHASE")
        game.phase = phase
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=p2, phase=phase)

        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "HORRIFYING VIOLENCE" for r in pending))

    def test_horrifying_violence_applies_battleshock_modifier_and_test(self):
        game, p1, p2, army1, army2 = _build_game()
        possessed = _make_unit(
            "Possessed",
            keywords=["INFANTRY", "POSSESSED"],
            faction_keywords=["WORLD EATERS"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(possessed)
        army2.add_unit(enemy)
        _place_unit(game, possessed, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        phase = SimpleNamespace(name="COMMAND_PHASE")
        game.phase = phase
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=p2, phase=phase)

        with patch.object(enemy, "take_battle_shock_test") as mocked:
            ok = p1.stratagems.use(
                "HORRIFYING VIOLENCE",
                unit=possessed,
                candidates=[possessed],
                phase_name="Command phase",
            )
        self.assertTrue(ok)
        self.assertEqual(int(enemy.special_rules.get("battle_shock_test_modifier", 0) or 0), -1)
        mocked.assert_called_once()

    def test_immortal_fury_queues_on_fight_targets_selected(self):
        game, p1, p2, army1, army2 = _build_game()
        possessed = _make_unit(
            "Possessed",
            keywords=["INFANTRY", "POSSESSED"],
            faction_keywords=["WORLD EATERS"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(possessed)
        army2.add_unit(enemy)
        _place_unit(game, possessed, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.phase = phase
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=p2, phase=phase)
        game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[possessed])

        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "IMMORTAL FURY" for r in pending))

    def test_immortal_fury_defers_fight_on_death(self):
        game, p1, p2, army1, army2 = _build_game()
        possessed = _make_unit(
            "Possessed",
            keywords=["INFANTRY", "POSSESSED"],
            faction_keywords=["WORLD EATERS"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(possessed)
        army2.add_unit(enemy)
        _place_unit(game, possessed, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        possessed.round_state.fought_this_phase = False
        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.phase = phase
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=p2, phase=phase)

        ok = p1.stratagems.use(
            "IMMORTAL FURY",
            unit=possessed,
            attacking_unit=enemy,
            candidates=[possessed],
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertTrue(possessed.special_rules.get("immortal_fury_active"))

        model = possessed.models[0]
        model._wounds = 0
        possessed._handle_model_destroyed(model, game.map)
        pending = getattr(possessed, "_immortal_fury_pending_models", [])
        self.assertIn(model, pending)

        with patch.object(possessed, "_try_fight_on_death") as mocked:
            possessed.end_attack_resolution(game_map=game.map)
        self.assertEqual(mocked.call_count, 1)
        self.assertFalse(getattr(possessed, "_immortal_fury_pending_models", []))

    def test_daemonic_strength_conditional_damage_bonus(self):
        game, p1, _p2, army1, army2 = _build_game()
        eightbound = _make_unit(
            "Eightbound",
            keywords=["INFANTRY", "POSSESSED", "EIGHTBOUND"],
            faction_keywords=["WORLD EATERS"],
            wounds="6",
        )
        exalted = _make_unit(
            "Exalted Eightbound",
            keywords=["INFANTRY", "POSSESSED", "EIGHTBOUND", "EXALTED EIGHTBOUND"],
            faction_keywords=["WORLD EATERS"],
            wounds="6",
        )
        enemy_infantry = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds="6")
        enemy_monster = _make_unit("Enemy Monster", keywords=["MONSTER"], faction_keywords=["ENEMY"], wounds="8")
        army1.add_unit(eightbound)
        army1.add_unit(exalted)
        army2.add_unit(enemy_infantry)
        army2.add_unit(enemy_monster)
        _place_unit(game, eightbound, 10.0, 10.0)
        _place_unit(game, exalted, 12.0, 10.0)
        _place_unit(game, enemy_infantry, 16.0, 10.0)
        _place_unit(game, enemy_monster, 18.0, 10.0)

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use("DAEMONIC STRENGTH", unit=eightbound, phase_name="Fight phase")
        self.assertTrue(ok)
        profile = _melee_profile()
        dmg_vs_infantry = profile._damage_target_with_tracking(enemy_infantry.models[0], eightbound.models[0], {})
        dmg_vs_monster = profile._damage_target_with_tracking(enemy_monster.models[0], eightbound.models[0], {})
        self.assertEqual(int(dmg_vs_infantry.get("damage_applied", 0) or 0), 2)
        self.assertEqual(int(dmg_vs_monster.get("damage_applied", 0) or 0), 1)

        ok2 = p1.stratagems.use("DAEMONIC STRENGTH", unit=exalted, phase_name="Fight phase")
        self.assertFalse(ok2)  # once per phase core limit

        p1.stratagems._used_stratagems_this_phase.clear()
        ok3 = p1.stratagems.use("DAEMONIC STRENGTH", unit=exalted, phase_name="Fight phase")
        self.assertTrue(ok3)
        dmg_exalted_vs_monster = profile._damage_target_with_tracking(enemy_monster.models[0], exalted.models[0], {})
        self.assertEqual(int(dmg_exalted_vs_monster.get("damage_applied", 0) or 0), 2)

    def test_rapid_manifestation_sets_deep_strike_override_and_no_charge(self):
        game, p1, _p2, army1, army2 = _build_game()
        exalted = _make_unit(
            "Exalted Eightbound",
            keywords=["INFANTRY", "POSSESSED", "EIGHTBOUND", "EXALTED EIGHTBOUND"],
            faction_keywords=["WORLD EATERS"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(exalted)
        army2.add_unit(enemy)
        _place_unit(game, enemy, 14.0, 10.0)

        exalted.deployed = False
        exalted.reserve_status = "reserves"
        exalted.special_rules["bearer_unit_deep_strike"] = True
        game.turn = 2

        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use("RAPID MANIFESTATION", unit=exalted, phase_name="Movement phase")
        self.assertTrue(ok)
        self.assertEqual(float(exalted.special_rules.get("rapid_manifestation_deep_strike_min_distance", 0.0) or 0.0), 6.0)
        self.assertEqual(float(exalted.get_deep_strike_min_distance_override() or 0.0), 6.0)

        exalted.deployed = True
        exalted.reserve_status = "deployed"
        exalted.arrived_from_reserves_this_turn = True
        exalted.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        if exalted not in game.map.units:
            game.map.place_unit(exalted)
        self.assertFalse(exalted.can_declare_charge_against(enemy, game))

        game.event_system.publish("phase_end", player=p1, phase=phase)
        self.assertNotIn("rapid_manifestation_deep_strike_min_distance", exalted.special_rules)

    def test_warp_stalkers_sets_and_clears_phase_move_rules(self):
        game, p1, _p2, army1, _army2 = _build_game()
        possessed = _make_unit(
            "Possessed",
            keywords=["INFANTRY", "POSSESSED"],
            faction_keywords=["WORLD EATERS"],
        )
        army1.add_unit(possessed)
        _place_unit(game, possessed, 10.0, 10.0)

        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use("WARP STALKERS", unit=possessed, phase_name="Movement phase")
        self.assertTrue(ok)
        sr = possessed.special_rules
        self.assertIn("move", sr.get("bearer_unit_phase_move_types", []))
        self.assertIn("charge", sr.get("bearer_unit_phase_move_types", []))
        self.assertIn("move", sr.get("bearer_unit_phase_move_block_monster_vehicle_types", []))
        self.assertTrue(sr.get("bearer_unit_auto_pass_desperate_escape"))

        game.event_system.publish("phase_end", player=p1, phase=phase)
        sr = possessed.special_rules
        self.assertFalse(sr.get("warp_stalkers_active", False))
        self.assertFalse(sr.get("bearer_unit_phase_move_block_monster_vehicle_types"))
        self.assertFalse(sr.get("bearer_unit_auto_pass_desperate_escape", False))


if __name__ == "__main__":
    unittest.main()
