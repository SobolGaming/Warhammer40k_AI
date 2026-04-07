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
        save=3,
        wounds=3,
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
                "Sv": str(save),
                "W": str(wounds),
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


def _make_unit(name, *, keywords=None, faction_keywords=None, save=3, wounds=3):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        save=save,
        wounds=wounds,
    )
    return Unit(datasheet)


class _MapStub:
    def get_friendly_units(self, _unit):
        return []


class _Game:
    def __init__(self, active_player):
        from warhammer40k_ai.engine.event.system import EventSystem

        self.event_system = EventSystem()
        self.map = _MapStub()
        self._current_player = active_player
        self.turn = 1
        self.phase = SimpleNamespace(name="SHOOTING_PHASE")

    def get_current_player(self):
        return self._current_player


class TestDefensiveStratagemTemplate(unittest.TestCase):
    def _build_env(
        self,
        *,
        faction_id,
        detachment,
        target_keywords=None,
        target_faction_keywords=None,
        target_save=3,
        target_wounds=3,
    ):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army.with_detachment("Test Faction", detachment)
        army.faction_id = faction_id
        target = _make_unit(
            "Target",
            keywords=target_keywords,
            faction_keywords=target_faction_keywords,
            save=target_save,
            wounds=target_wounds,
        )
        army.add_unit(target)

        enemy_army = Army.with_detachment("Enemy", "Other")
        enemy_army.faction_id = "EN"
        attacker = _make_unit("Attacker", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_army.add_unit(attacker)

        player = Player("P1", control=PlayerControl.LOCAL, army=army)
        enemy_player = Player("P2", control=PlayerControl.LOCAL, army=enemy_army)
        game = _Game(active_player=enemy_player)
        player.set_game(game)
        enemy_player.set_game(game)
        player.command_points = 3
        enemy_player.command_points = 3

        target.deployed = True
        attacker.deployed = True
        return player, enemy_player, target, attacker, game

    def _start_phase(self, game, active_player, phase_name):
        phase = SimpleNamespace(name=phase_name)
        game.phase = phase
        game.event_system.publish("phase_start", player=active_player, phase=phase)

    def _end_phase(self, game, active_player, phase_name):
        phase = SimpleNamespace(name=phase_name)
        game.event_system.publish("phase_end", player=active_player, phase=phase)

    def test_generic_defensive_ap_worsen(self):
        from warhammer40k_ai.units.wargear import Wargear

        player, enemy_player, target, attacker, game = self._build_env(
            faction_id="AM",
            detachment="Grizzled Company",
            target_faction_keywords=["ASTRA MILITARUM"],
        )
        self._start_phase(game, enemy_player, "SHOOTING_PHASE")

        ok = player.stratagems.use(
            "ADDITIONAL ARMOUR",
            unit=target,
            attacker_unit=attacker,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        weapon = Wargear(
            {
                "name": "Test Gun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "-2",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        attacker_model = attacker.models[0]

        self.assertEqual(profile.get_effective_ap(attacker_model, target), -1)
        game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker)
        self.assertEqual(profile.get_effective_ap(attacker_model, target), -2)

    def test_generic_defensive_hit_penalty_phase(self):
        from warhammer40k_ai.units.wargear import Wargear

        player, enemy_player, target, attacker, game = self._build_env(
            faction_id="CD",
            detachment="Daemonic Incursion",
            target_faction_keywords=["LEGIONES DAEMONICA"],
        )
        self._start_phase(game, enemy_player, "SHOOTING_PHASE")

        ok = player.stratagems.use(
            "INCORPOREAL TERRORS",
            unit=target,
            attacker_unit=attacker,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        weapon = Wargear(
            {
                "name": "Test Gun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        attacker_model = attacker.models[0]

        hit_result = profile._hit_target_with_tracking(
            target,
            attacker_model,
            {"target_model": target.models[0]},
        )
        self.assertEqual(hit_result.get("final_needed"), 4)

        self._end_phase(game, enemy_player, "SHOOTING_PHASE")
        hit_result = profile._hit_target_with_tracking(
            target,
            attacker_model,
            {"target_model": target.models[0]},
        )
        self.assertEqual(hit_result.get("final_needed"), 3)

    def test_generic_defensive_damage_reduction(self):
        from warhammer40k_ai.units.wargear import Wargear

        player, enemy_player, target, attacker, game = self._build_env(
            faction_id="DG",
            detachment="Virulent Vectorium",
            target_faction_keywords=["DEATH GUARD"],
            target_wounds=3,
        )
        self._start_phase(game, enemy_player, "SHOOTING_PHASE")

        ok = player.stratagems.use(
            "DISGUSTINGLY RESILIENT",
            unit=target,
            attacker_unit=attacker,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        weapon = Wargear(
            {
                "name": "Test Blaster",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "2",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        attacker_model = attacker.models[0]
        target_model = target.models[0]

        dmg = profile._damage_target_with_tracking(target_model, attacker_model, {"mortal_wound": False})
        self.assertEqual(dmg.get("damage_applied"), 1)

        self._end_phase(game, enemy_player, "SHOOTING_PHASE")
        target_model.wounds = 3
        dmg = profile._damage_target_with_tracking(target_model, attacker_model, {"mortal_wound": False})
        self.assertEqual(dmg.get("damage_applied"), 2)

    def test_generic_defensive_invulnerable_save(self):
        from warhammer40k_ai.units.wargear import Wargear

        player, enemy_player, target, attacker, game = self._build_env(
            faction_id="DRU",
            detachment="Skysplinter Assault",
            target_keywords=["VEHICLE"],
            target_faction_keywords=["DRUKHARI"],
            target_save=3,
            target_wounds=3,
        )
        self._start_phase(game, enemy_player, "SHOOTING_PHASE")

        ok = player.stratagems.use(
            "NIGHT SHIELD",
            unit=target,
            attacker_unit=attacker,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        weapon = Wargear(
            {
                "name": "Test Lance",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "8",
                "AP": "-3",
                "D": "2",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        target_model = target.models[0]
        save_result = profile._save_with_tracking(target_model, {}, -3)
        self.assertEqual(save_result.get("save_type"), "invulnerable")
        self.assertEqual(save_result.get("final_save"), 4)

        self._end_phase(game, enemy_player, "SHOOTING_PHASE")
        save_result = profile._save_with_tracking(target_model, {}, -3)
        self.assertEqual(save_result.get("save_type"), "armor")
        self.assertEqual(save_result.get("final_save"), 6)

    def test_generic_defensive_feel_no_pain(self):
        from warhammer40k_ai.units.wargear import Wargear

        player, enemy_player, target, attacker, game = self._build_env(
            faction_id="AoI",
            detachment="Interdiction Team",
            target_faction_keywords=["ADEPTUS ARBITES"],
            target_wounds=2,
        )
        self._start_phase(game, enemy_player, "SHOOTING_PHASE")

        ok = player.stratagems.use(
            "DUTY AND DEATH",
            unit=target,
            attacker_unit=attacker,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        weapon = Wargear(
            {
                "name": "Test Shot",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        attacker_model = attacker.models[0]
        target_model = target.models[0]

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
            dmg = profile._damage_target_with_tracking(target_model, attacker_model, {"mortal_wound": False})
        self.assertEqual(dmg.get("damage_applied"), 0)
        self.assertEqual(dmg.get("fnp_saves"), 1)

        self._end_phase(game, enemy_player, "SHOOTING_PHASE")
        target_model.wounds = 2
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
            dmg = profile._damage_target_with_tracking(target_model, attacker_model, {"mortal_wound": False})
        self.assertEqual(dmg.get("damage_applied"), 1)


if __name__ == "__main__":
    unittest.main()
