import unittest
from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint


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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(name, *, keywords=None, faction_keywords=None):
    datasheet = _MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords)
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.round_state.shot_this_round = False
    return unit


class _GameStub:
    def __init__(self, active_player, phase_name: str):
        from warhammer40k_ai.engine.event.system import EventSystem
        from warhammer40k_ai.engine.decisions import DecisionQueue

        self.event_system = EventSystem()
        self.decision_queue = DecisionQueue()
        self._current_player = active_player
        self.turn = 1
        self.phase = SimpleNamespace(name=phase_name)
        self.map = _MapStub()
        self.is_authoritative = True

    def get_current_player(self):
        return self._current_player

    def request_decision(self, request):
        self.decision_queue.add(request)


class _MapStub:
    def __init__(self):
        self.objectives = []

    def get_friendly_units(self, _unit):
        return []

    def get_enemy_units(self, _unit):
        return []


class TestChaosKnightsInfernalLanceStratagems(unittest.TestCase):
    def _setup_env(self, phase_name: str):
        army = Army("Chaos Knights", detachment_type="Infernal Lance")
        army.faction_id = "QT"
        player = Player("CK", control=PlayerControl.REMOTE, army=army)
        game = _GameStub(active_player=player, phase_name=phase_name)
        player.set_game(game)
        player.command_points = 2
        return army, player, game

    def test_profane_symbiosis_applies_malefic_surge(self):
        army, player, game = self._setup_env("MOVEMENT_PHASE")
        unit = _make_unit("Knight", faction_keywords=["CHAOS KNIGHTS"])
        unit.pass_leadership_check = lambda **_kwargs: True
        army.add_unit(unit)

        ok = player.stratagems.use("PROFANE SYMBIOSIS", unit=unit, phase_name="Movement phase")
        self.assertTrue(ok)
        sr = unit.special_rules
        self.assertTrue(sr.get("malefic_surge_empowered"))
        self.assertEqual(sr.get("profane_symbiosis_last_owner"), player.id)

    def test_corrupting_taint_sets_sticky_objective(self):
        army, player, game = self._setup_env("COMMAND_PHASE")
        unit = _make_unit(
            "Knight",
            keywords=["CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
        )
        unit.is_within_objective_range = lambda _loc: True
        unit.pass_leadership_check = lambda **_kwargs: True
        army.add_unit(unit)

        obj_loc = ObjectivePoint(0.0, 0.0)
        obj_loc.controlling_player = player
        objective = Objective("Marker", ObjectiveCategory.PRIMARY, 0, "", lambda _g: False, location=obj_loc)
        game.map.objectives = [objective]

        ok = player.stratagems.use(
            "CORRUPTING TAINT",
            unit=unit,
            objective=objective,
            objective_candidates=[objective],
            phase_name="Command phase",
        )
        self.assertTrue(ok)
        self.assertIs(objective.location.sticky_controller, player)

    def test_warp_vision_ignores_cover_and_cleans_up(self):
        army, player, game = self._setup_env("SHOOTING_PHASE")
        unit = _make_unit("Knight", faction_keywords=["CHAOS KNIGHTS"])
        army.add_unit(unit)
        target = _make_unit("Enemy", faction_keywords=["ENEMY"])
        target_army = Army("Enemy", detachment_type="None")
        target_army.faction_id = "EN"
        target_army.add_unit(target)

        ok = player.stratagems.use("WARP VISION", unit=unit, phase_name="Shooting phase")
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
        model = unit.models[0]
        attack_instance = {}
        profile._hit_target_with_tracking(
            target,
            model,
            attack_instance,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(attack_instance.get("ignores_cover"))

        game.event_system.publish("phase_end", player=player, phase=game.phase)
        self.assertFalse(unit.special_rules.get("warp_vision_ignores_cover_active"))

    def test_unleash_balefire_queues_post_shoot_decision(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_AFLAME_TARGET

        army, player, game = self._setup_env("SHOOTING_PHASE")
        unit = _make_unit("Knight", faction_keywords=["CHAOS KNIGHTS"])
        army.add_unit(unit)
        enemy_player = Player("EN", control=PlayerControl.REMOTE, army=Army("Enemy", detachment_type="None"))
        enemy_player.army.faction_id = "EN"
        enemy_unit = _make_unit("Enemy", faction_keywords=["ENEMY"])
        enemy_player.army.add_unit(enemy_unit)

        ok = player.stratagems.use("UNLEASH BALEFIRE", unit=unit, phase_name="Shooting phase")
        self.assertTrue(ok)

        game.event_system.publish("phase_start", player=player, phase=game.phase)
        game.event_system.publish("unit_shooting_resolved", attacker_unit=unit, hits_by_target={enemy_unit: 1})

        requests = list(game.decision_queue.list() or [])
        self.assertTrue(requests)
        req = requests[-1]
        self.assertEqual(str(getattr(req, "decision_type", "")), DECISION_CHOOSE_POST_SHOOT_AFLAME_TARGET)
        ctx = dict(getattr(req, "context", {}) or {})
        self.assertTrue(ctx.get("battleshock_on_fail"))
