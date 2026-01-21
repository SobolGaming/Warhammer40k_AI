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
        model_count=1,
        base_size="32mm",
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, model_count=1):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Emperor's Children", detachment_type="Peerless Bladesmen")
    army1.faction_id = "EC"
    army2 = Army("Enemy", detachment_type="Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 5
    p2.command_points = 5
    return game, p1, p2, army1, army2


def _place_unit(game, unit, x, y):
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


class TestPeerlessBladesmenStratagems(unittest.TestCase):
    def test_cruel_bladesman_grants_melee_ap_bonus(self):
        game, p1, _p2, army1, _army2 = _build_game()
        unit = _make_unit(
            "Blades",
            keywords=["INFANTRY"],
            faction_keywords=["EMPEROR'S CHILDREN"],
        )
        army1.add_unit(unit)
        unit.deployed = True
        unit.round_state.charged_this_round = True
        unit.round_state.fought_this_phase = False

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use("CRUEL BLADESMAN", unit=unit, phase_name="Fight phase")
        self.assertTrue(ok)
        sr = unit.special_rules
        self.assertEqual(int(sr.get("charge_melee_ap_bonus", 0) or 0), 1)
        self.assertEqual(sr.get("charge_melee_ap_bonus_source"), "CRUEL BLADESMAN")
        self.assertEqual(sr.get("charge_melee_ap_bonus_expires_phase"), "FIGHT_PHASE")

    def test_incessant_violence_sets_consolidate_override(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Blades",
            keywords=["INFANTRY"],
            faction_keywords=["EMPEROR'S CHILDREN"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use("INCESSANT VIOLENCE", unit=unit, phase_name="Fight phase")
        self.assertTrue(ok)
        sr = unit.special_rules
        self.assertEqual(int(sr.get("stratagem_consolidate_distance_override", 0) or 0), 6)
        self.assertTrue(sr.get("stratagem_consolidate_requires_engagement"))
        self.assertEqual(sr.get("stratagem_consolidate_source"), "INCESSANT VIOLENCE")

    def test_incessant_violence_blocks_without_engagement_path(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Blades",
            keywords=["INFANTRY"],
            faction_keywords=["EMPEROR'S CHILDREN"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 30.0, 10.0)

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use("INCESSANT VIOLENCE", unit=unit, phase_name="Fight phase")
        self.assertFalse(ok)

    def test_death_ecstasy_defers_fight_on_death(self):
        game, p1, _p2, army1, _army2 = _build_game()
        unit = _make_unit(
            "Blades",
            keywords=["INFANTRY"],
            faction_keywords=["EMPEROR'S CHILDREN"],
        )
        army1.add_unit(unit)
        _place_unit(game, unit, 10.0, 10.0)
        unit.special_rules["death_ecstasy_active"] = True
        unit.special_rules["death_ecstasy_expires_phase"] = "FIGHT_PHASE"
        unit.round_state.fought_this_phase = False

        game.phase = SimpleNamespace(name="FIGHT_PHASE")
        model = unit.models[0]
        model._wounds = 0

        unit._handle_model_destroyed(model, game.map)
        pending = getattr(unit, "_death_ecstasy_pending_models", [])
        self.assertIn(model, pending)

        with patch.object(unit, "_try_fight_on_death") as mocked:
            unit.end_attack_resolution(game_map=game.map)
        self.assertEqual(mocked.call_count, 1)
        self.assertFalse(getattr(unit, "_death_ecstasy_pending_models", []))

    def test_terrifying_spectacle_forces_battleshock_and_suppresses(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Blades",
            keywords=["INFANTRY"],
            faction_keywords=["EMPEROR'S CHILDREN"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        unit.special_rules["ec_last_turn_charged"] = True
        unit.special_rules["ec_last_turn_destroyed_enemy_in_fight"] = True

        calls = []
        enemy.take_battle_shock_test = lambda *_args, **_kwargs: calls.append("tested")
        enemy.is_below_half_strength = lambda: True

        phase = SimpleNamespace(name="COMMAND_PHASE")
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use("TERRIFYING SPECTACLE", unit=unit, phase_name="Command phase")
        self.assertTrue(ok)
        self.assertEqual(calls, ["tested"])
        sr = enemy.special_rules
        self.assertEqual(int(sr.get("battle_shock_test_modifier", 0) or 0), -1)
        self.assertEqual(sr.get("battle_shock_suppress_other_tests_phase"), "COMMAND_PHASE")
        self.assertEqual(sr.get("battle_shock_suppress_other_tests_source"), "TERRIFYING SPECTACLE")

    def test_cut_down_the_weak_charges_without_bonus(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Blades",
            keywords=["INFANTRY"],
            faction_keywords=["EMPEROR'S CHILDREN"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.event_system.publish("phase_start", player=p1, phase=phase)

        def _force_charge_move(_self, _destination, _game_map, target_unit=None, target_units=None):
            tx, ty, tz, facing = target_unit.models[0].get_location()
            _self.models[0].set_location(tx - 0.5, ty, tz, facing)
            return True

        from warhammer40k_ai.units.unit import Unit

        with patch.object(Unit, "charge_move", new=_force_charge_move), patch(
            "warhammer40k_ai.utility.dice.get_dice_roll",
            return_value=6,
        ):
            ok = p1.stratagems.use(
                "CUT DOWN THE WEAK",
                unit=unit,
                enemy_unit=enemy,
                phase_name="Movement phase",
            )
        self.assertTrue(ok)
        self.assertTrue(unit.round_state.charged_this_round)
        self.assertTrue(unit.charge_bonus_suppressed(game))


if __name__ == "__main__":
    unittest.main()
