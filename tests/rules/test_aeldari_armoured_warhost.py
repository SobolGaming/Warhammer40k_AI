import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


def _make_unit(name, army, *, keywords=None, faction_keywords=None):
    unit = Unit.__new__(Unit)
    unit.name = name
    unit._id = name
    unit.parent_army = army
    unit.faction = getattr(army, "faction_id", "")
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models = []
    unit.models_lost = []
    unit.keywords = list(keywords or [])
    unit.faction_keywords = list(faction_keywords or [])
    unit.possible_abilities = []
    unit.status_effects = []
    unit.special_rules = {}
    unit.round_state = SimpleNamespace(num_lost_models_this_round=0)
    unit.attached_leaders = []
    unit.attached_to = None
    unit.can_be_attached_to = []
    unit.embarked_in = None
    unit._ability_cache = {}
    unit.enhancement = None
    unit.is_alive = lambda: True
    unit.get_parent_army = lambda: army
    unit.get_attached_unit_root = lambda: unit
    unit.get_attached_unit_models = lambda: list(unit.models)
    unit.get_attached_unit_members = lambda: [unit]
    unit.get_models_for_collision = lambda: list(unit.models)
    unit.is_in_reserves = lambda: False
    unit.has_any_keyword = lambda kw: any(
        str(kw or "").strip().upper() == str(k or "").strip().upper()
        for k in (unit.keywords + unit.faction_keywords)
    )
    return unit


def _make_model(name, unit, *, x=0.0, y=0.0, wounds=6):
    model = Model(
        name=name,
        movement=6,
        toughness=5,
        save=3,
        wounds=wounds,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(x, y, 0.0, 0.0)
    return model


class TestAeldariArmouredWarhost(unittest.TestCase):
    def test_skilled_crews_assault_and_reroll_advance(self):
        army = Army("Aeldari", detachment_type="Armoured Warhost")
        army.faction_id = "AE"

        vehicle_fly = _make_unit(
            "VehicleFly",
            army,
            keywords=["VEHICLE", "FLY"],
            faction_keywords=["AELDARI"],
        )
        vehicle = _make_unit(
            "Vehicle",
            army,
            keywords=["VEHICLE"],
            faction_keywords=["AELDARI"],
        )
        infantry = _make_unit(
            "Infantry",
            army,
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI"],
        )

        ranged_parent = SimpleNamespace(is_ranged=lambda: True, is_melee=lambda: False)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
        )

        self.assertTrue(vehicle_fly.can_shoot_after_advance(profile))
        self.assertTrue(vehicle_fly.can_reroll_advance_roll())
        self.assertFalse(vehicle.can_reroll_advance_roll())
        self.assertFalse(infantry.can_shoot_after_advance(profile))

    def test_guiding_presence_selection_and_hit_bonus(self):
        army = Army("Aeldari", detachment_type="Armoured Warhost")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        enhancer = Enhancement(
            id="000009769002",
            name="Guiding Presence",
            faction_id="AE",
            detachment="Armoured Warhost",
        )

        psyker = _make_unit("Farseer", army, faction_keywords=["AELDARI", "PSYKER"])
        psyker_model = _make_model("Farseer", psyker, x=0.0, y=0.0, wounds=5)
        psyker.models = [psyker_model]
        psyker.enhancement = enhancer
        enhancer.apply_to_unit(psyker)

        vehicle_a = _make_unit("VehicleA", army, keywords=["VEHICLE"], faction_keywords=["AELDARI"])
        vehicle_a_model = _make_model("VehicleA", vehicle_a, x=5.0, y=0.0, wounds=8)
        vehicle_a.models = [vehicle_a_model]

        vehicle_b = _make_unit("VehicleB", army, keywords=["VEHICLE"], faction_keywords=["AELDARI"])
        vehicle_b_model = _make_model("VehicleB", vehicle_b, x=6.0, y=0.0, wounds=8)
        vehicle_b.models = [vehicle_b_model]

        target_unit = _make_unit("Target", enemy_army, keywords=["INFANTRY"])
        target_model = _make_model("Target", target_unit, x=12.0, y=0.0, wounds=2)
        target_unit.models = [target_model]

        army.units = [psyker, vehicle_a, vehicle_b]
        enemy_army.units = [target_unit]
        game.rebuild_entity_registry()

        game._on_phase_start_aeldari_enhancements(player=player, phase=game.phase)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "aeldari_guiding_presence")

        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        sr = getattr(vehicle_a, "special_rules", {}) or {}
        self.assertTrue(sr.get("guiding_presence_active"))

        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )
        ranged_parent = SimpleNamespace(is_ranged=lambda: True, is_melee=lambda: False)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
        )
        attack_instance = {"_aura_attack_mods": aura_stub}
        hit_res = profile._hit_target_with_tracking(
            target_unit, vehicle_a_model, attack_instance, roll_value=4, allow_rerolls=False
        )
        self.assertTrue(any("Guiding Presence" in mod for mod in hit_res.get("modifiers", [])))

    def test_harmonisation_matrix_cp_gain(self):
        army = Army("Aeldari", detachment_type="Armoured Warhost")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0

        obj_loc = ObjectivePoint(0.0, 0.0)
        obj = Objective("Test", ObjectiveCategory.PRIMARY, 5, "", lambda _g: False, location=obj_loc)
        game.map.add_objective(obj)

        enhancer = Enhancement(
            id="000009769003",
            name="Harmonisation Matrix",
            faction_id="AE",
            detachment="Armoured Warhost",
        )
        unit = _make_unit("Harmoniser", army, faction_keywords=["AELDARI"])
        model = _make_model("Harmoniser", unit, x=0.0, y=0.0, wounds=4)
        unit.models = [model]
        unit.enhancement = enhancer
        enhancer.apply_to_unit(unit)
        army.units = [unit]

        before = player.command_points
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
            game._on_phase_start_aeldari_enhancements(player=player, phase=game.phase)
        self.assertEqual(player.command_points, before + 1)

    def test_spirit_stone_heal_and_lone_operative(self):
        army = Army("Aeldari", detachment_type="Armoured Warhost")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0

        enhancer = Enhancement(
            id="000009769004",
            name="Spirit Stone of Raelyth",
            faction_id="AE",
            detachment="Armoured Warhost",
        )
        bearer = _make_unit("Spiritseer", army, faction_keywords=["AELDARI", "PSYKER"])
        bearer_model = _make_model("Spiritseer", bearer, x=0.0, y=0.0, wounds=4)
        bearer.models = [bearer_model]
        bearer.enhancement = enhancer
        enhancer.apply_to_unit(bearer)

        vehicle = _make_unit("Falcon", army, keywords=["VEHICLE"], faction_keywords=["AELDARI"])
        vehicle_model = _make_model("Falcon", vehicle, x=2.0, y=0.0, wounds=10)
        vehicle_model.wounds = 7
        vehicle.models = [vehicle_model]

        army.units = [bearer, vehicle]
        game.map.units = [bearer, vehicle]
        game.rebuild_entity_registry()

        self.assertTrue(bearer.has_lone_operative())

        game._on_phase_start_aeldari_enhancements(player=player, phase=game.phase)
        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "aeldari_spirit_stone_heal")

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
            resolve_decision_command(game, request, request.options[-1].option_id, player_id=player.id)

        self.assertEqual(vehicle_model.wounds, 10)


if __name__ == "__main__":
    unittest.main()
