import unittest
from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _Ability:
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description


class _MockDatasheet:
    def __init__(self, name, *, keywords=None, faction_keywords=None):
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
                "Sv": "4",
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


class _MapStub:
    def __init__(self):
        self.objectives = []

    def get_friendly_units(self, unit):
        army = unit.get_parent_army() if unit is not None else None
        return list(getattr(army, "units", []) or []) if army is not None else []

    def get_enemy_units(self, _unit):
        return []

    def get_distance_between_units(self, _unit1, _unit2):
        return 3.0

    def is_within_engagement_range(self, _unit1, _unit2):
        return False


class _GameStub:
    def __init__(self, active_player, phase_name: str):
        from warhammer40k_ai.engine.decisions import DecisionQueue
        from warhammer40k_ai.engine.event.system import EventSystem

        self.event_system = EventSystem()
        self.decision_queue = DecisionQueue()
        self._current_player = active_player
        self.turn = 1
        self.phase = SimpleNamespace(name=phase_name)
        self.map = _MapStub()
        self.players = []
        self.is_authoritative = True

    def get_current_player(self):
        return self._current_player

    def request_decision(self, request):
        self.decision_queue.add(request)


def _make_unit(name, *, keywords=None, faction_keywords=None, abilities=None):
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.round_state.shot_this_round = False
    unit.possible_abilities = list(abilities or [])
    return unit


class TestAstraMilitarumGrizzledCompanyStratagems(unittest.TestCase):
    def _setup_env(self, phase_name: str, *, control=PlayerControl.REMOTE):
        army = Army("Astra Militarum", detachment_type="Grizzled Company")
        army.faction_id = "AM"
        player = Player("AM", control=control, army=army)

        enemy_army = Army("Enemy", detachment_type="None")
        enemy_army.faction_id = "EN"
        enemy = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)

        game = _GameStub(active_player=player, phase_name=phase_name)
        game.players = [player, enemy]
        player.set_game(game)
        enemy.set_game(game)
        player.command_points = 5
        enemy.command_points = 5
        return army, player, enemy_army, enemy, game

    def test_mordian_minute_adds_ranged_strength(self):
        army, player, enemy_army, _enemy, _game = self._setup_env("SHOOTING_PHASE")
        unit = _make_unit(
            "Infantry",
            keywords=["INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        unit.special_rules["voice_of_command_order_key"] = "FIRST_RANK_FIRE"
        army.add_unit(unit)

        target = _make_unit("Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_army.add_unit(target)

        ok = player.stratagems.use("MORDIAN MINUTE", unit=unit, phase_name="Shooting phase")
        self.assertTrue(ok)

        weapon = Wargear(
            {
                "name": "Lasgun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "4+",
                "S": "3",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        wound = profile._wound_target_with_tracking(
            target,
            unit.models[0],
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(wound.get("wound"))
        self.assertTrue(any("MORDIAN MINUTE" in m for m in wound.get("modifiers", [])))

    def test_purging_fire_grants_lethal_hits(self):
        army, player, enemy_army, _enemy, _game = self._setup_env("SHOOTING_PHASE")
        unit = _make_unit("Veterans", keywords=["REGIMENT"], faction_keywords=["ASTRA MILITARUM"])
        unit.special_rules["voice_of_command_order_key"] = "TAKE_AIM"
        unit.is_within_any_objective_range = lambda game_map=None: True
        army.add_unit(unit)

        target = _make_unit("Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_army.add_unit(target)

        ok = player.stratagems.use("PURGING FIRE", unit=unit, phase_name="Shooting phase")
        self.assertTrue(ok)

        weapon = Wargear(
            {
                "name": "Hot-shot Lasgun",
                "type": "Ranged",
                "range": "18",
                "A": "1",
                "BS_WS": "4+",
                "S": "3",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        attack_instance = {}
        hit = profile._hit_target_with_tracking(
            target,
            unit.models[0],
            attack_instance,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(hit.get("hit"))
        self.assertTrue(attack_instance.get("lethal_hit"))
        self.assertIn("Lethal Hits", hit.get("special_effects", []))

    def test_veteran_sharpshooters_grants_ignores_cover(self):
        army, player, enemy_army, _enemy, _game = self._setup_env("SHOOTING_PHASE")
        unit = _make_unit("Sharpshooters", keywords=["REGIMENT"], faction_keywords=["ASTRA MILITARUM"])
        army.add_unit(unit)

        target = _make_unit("Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_army.add_unit(target)

        ok = player.stratagems.use("VETERAN SHARPSHOOTERS", unit=unit, phase_name="Shooting phase")
        self.assertTrue(ok)

        weapon = Wargear(
            {
                "name": "Long-las",
                "type": "Ranged",
                "range": "36",
                "A": "1",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        attack_instance = {}
        profile._hit_target_with_tracking(
            target,
            unit.models[0],
            attack_instance,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(attack_instance.get("ignores_cover"))

    def test_no_retreat_sets_sticky_control(self):
        army, player, _enemy_army, _enemy, game = self._setup_env("COMMAND_PHASE")
        unit = _make_unit("Line Unit", keywords=["REGIMENT"], faction_keywords=["ASTRA MILITARUM"])
        unit.special_rules["voice_of_command_order_key"] = "DUTY_HONOUR"
        unit._within_controlled_objective_range = lambda game_map=None: True
        unit.is_within_objective_range = lambda _loc: True
        army.add_unit(unit)

        objective_location = ObjectivePoint(0.0, 0.0)
        objective_location.controlling_player = player
        objective = Objective("Center", ObjectiveCategory.PRIMARY, 0, "", lambda _g: False, location=objective_location)
        game.map.objectives = [objective]

        ok = player.stratagems.use(
            "NO RETREAT!",
            unit=unit,
            objective=objective,
            objective_candidates=[objective],
            phase_name="Command phase",
        )
        self.assertTrue(ok)
        self.assertIs(objective.location.sticky_controller, player)
        self.assertEqual(str(getattr(objective.location, "sticky_source", "")), "no_retreat")

    def test_snap_to_it_remote_requires_explicit_choice_payload(self):
        army, player, _enemy_army, _enemy, _game = self._setup_env("MOVEMENT_PHASE", control=PlayerControl.REMOTE)
        officer = _make_unit(
            "Officer",
            keywords=["OFFICER", "ASTRA MILITARUM"],
            faction_keywords=["ASTRA MILITARUM"],
            abilities=[
                _Ability("Voice of Command"),
                _Ability("Orders", "This model can issue 1 order to REGIMENT units within 6\"."),
            ],
        )
        target = _make_unit("Infantry", keywords=["REGIMENT"], faction_keywords=["ASTRA MILITARUM"])
        army.add_unit(officer)
        army.add_unit(target)

        start_cp = int(player.command_points)
        ok = player.stratagems.use("SNAP TO IT", phase_name="Movement phase")
        self.assertFalse(ok)
        self.assertEqual(int(player.command_points), start_cp)

    def test_snap_to_it_remote_with_payload_issues_order(self):
        army, player, _enemy_army, _enemy, _game = self._setup_env("MOVEMENT_PHASE", control=PlayerControl.REMOTE)
        officer = _make_unit(
            "Officer",
            keywords=["OFFICER", "ASTRA MILITARUM"],
            faction_keywords=["ASTRA MILITARUM"],
            abilities=[
                _Ability("Voice of Command"),
                _Ability("Orders", "This model can issue 1 order to REGIMENT units within 6\"."),
            ],
        )
        target = _make_unit("Infantry", keywords=["REGIMENT"], faction_keywords=["ASTRA MILITARUM"])
        army.add_unit(officer)
        army.add_unit(target)

        start_cp = int(player.command_points)
        ok = player.stratagems.use(
            "SNAP TO IT",
            officer_unit=officer,
            order_target_unit=target,
            order_key="MOVE_MOVE_MOVE",
            phase_name="Movement phase",
        )
        self.assertTrue(ok)
        self.assertEqual(target.special_rules.get("voice_of_command_order_key"), "MOVE_MOVE_MOVE")
        self.assertEqual(int(player.command_points), start_cp - 1)


if __name__ == "__main__":
    unittest.main()
