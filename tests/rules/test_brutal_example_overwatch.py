import unittest
from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.rules.stratagems import StratagemManager


class TestBrutalExampleOverwatch(unittest.TestCase):
    def _make_unit(self, name, army, *, abilities=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.keywords = []
        unit.faction_keywords = []
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0)
        unit.models_lost = []
        unit.attached_leaders = []
        unit.attached_to = None
        unit.embarked_in = None
        unit.can_be_attached_to = []
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.is_in_reserves = lambda: False
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.has_any_keyword = lambda kw: False
        return unit

    def _make_model(self, name, unit, *, wounds: int = 2):
        model = Model(
            name=name,
            movement=6,
            toughness=4,
            save=3,
            wounds=int(wounds),
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def _setup_units_with_brutal_example(self, army):
        ability_desc = (
            "Once per turn, while this unit is leading a unit and contains a TRAITOR ENFORCER model, you can target "
            "that unit with the Fire Overwatch Stratagem for 0CP, and can do so even if you have already targeted a "
            "different unit from your army with that Stratagem this turn. Each time you use this ability, one Bodyguard "
            "model in that unit is destroyed."
        )
        ability = Ability("Brutal Example", "CSM", ability_desc, "Datasheet", "")

        bodyguard = self._make_unit("Bodyguard Unit", army)
        leader = self._make_unit("Traitor Enforcer", army, abilities=[ability])
        leader.can_be_attached_to = [bodyguard.name]
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        bodyguard.get_attached_unit_members = lambda: [bodyguard, leader]

        leader.get_attached_unit_root = lambda: bodyguard
        leader_model = self._make_model("Traitor Enforcer", leader)
        leader.models = [leader_model]

        bodyguard_model = self._make_model("Bodyguard", bodyguard)
        bodyguard.models = [bodyguard_model]
        return bodyguard, leader

    def test_brutal_example_rule_detected_and_usage(self):
        army = Army.with_detachment("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        bodyguard, _leader = self._setup_units_with_brutal_example(army)

        player = Player("Chaos", PlayerControl.REMOTE, army=army)
        game = SimpleNamespace(turn=1, get_current_player=lambda: player)

        rule = bodyguard.get_traitor_enforcer_overwatch_rule()
        self.assertIsNotNone(rule)
        self.assertEqual(rule.get("ability_key"), "brutal_example_overwatch")
        self.assertTrue(bodyguard.can_use_traitor_enforcer_overwatch(game))

        bodyguard.mark_traitor_enforcer_overwatch_used(game, source="Brutal Example")
        self.assertTrue(bodyguard.traitor_enforcer_overwatch_used_this_turn(game))
        self.assertFalse(bodyguard.can_use_traitor_enforcer_overwatch(game))

    def test_apply_stratagem_cp_cost_brutal_example(self):
        army = Army.with_detachment("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        bodyguard, _leader = self._setup_units_with_brutal_example(army)

        player = Player("Chaos", PlayerControl.REMOTE, army=army)
        game = SimpleNamespace(turn=1, get_current_player=lambda: player, players=[player])
        player.game = game
        player.stratagems = SimpleNamespace(_used_this_turn={})

        strat = SimpleNamespace(name="Fire Overwatch", cp_cost=1)
        player.set_next_optional_decision("BRUTAL_EXAMPLE_OVERWATCH", True)
        applied = player.apply_stratagem_cp_cost(strat, target_unit=bodyguard)
        self.assertEqual(applied.get("cost"), 0)
        self.assertTrue(applied.get("traitor_enforcer_overwatch_use", False))

        # If Overwatch already used and Brutal Example declined, deny usage.
        player.stratagems._used_this_turn = {"OVERWATCH": True}
        player.set_next_optional_decision("BRUTAL_EXAMPLE_OVERWATCH", False)
        denied = player.apply_stratagem_cp_cost(strat, target_unit=bodyguard)
        self.assertTrue(denied.get("denied", False))

    def test_overwatch_queue_allows_brutal_example_after_used(self):
        moving_unit = SimpleNamespace(
            get_parent_army=lambda: SimpleNamespace(player=SimpleNamespace(name="Attacker", id="attacker-player")),
            special_rules={},
        )
        moving_unit.is_overwatch_prevented_against = lambda _target, game=None: False

        shooter = SimpleNamespace(
            name="Traitor Enforcer Unit",
            is_alive=lambda: True,
            deployed=True,
            is_titanic=False,
            is_embarked=False,
            embarked_in=None,
            special_rules={},
            is_battle_shocked=lambda: False,
        )
        shooter.can_use_traitor_enforcer_overwatch = lambda game=None: True

        defender_player = SimpleNamespace(
            name="Defender",
            id="defender-player",
            command_points=0,
            get_army=lambda: SimpleNamespace(units=[shooter]),
        )

        game = SimpleNamespace(
            get_current_player=lambda: SimpleNamespace(name="Attacker", id="attacker-player"),
            map=SimpleNamespace(get_distance_between_units=lambda u1, u2: 10.0),
        )

        stratagem_mgr = StratagemManager.__new__(StratagemManager)
        stratagem_mgr.player = defender_player
        stratagem_mgr.game = game
        stratagem_mgr._used_this_turn = {"OVERWATCH": True}
        stratagem_mgr._used_stratagems_this_phase = set()
        stratagem_mgr._current_phase_name = "Charge phase"
        stratagem_mgr._pending_reactions = []
        stratagem_mgr._queue_reaction = lambda reaction: stratagem_mgr._pending_reactions.append(reaction)

        stratagem_mgr.get_by_name = lambda name: SimpleNamespace(
            name="FIRE OVERWATCH",
            is_phase_allowed=lambda phase: True,
            is_turn_allowed=lambda is_active: True,
            cp_cost=1,
        )

        stratagem_mgr._maybe_queue_overwatch(moving_unit, "charge", "start")
        self.assertEqual(len(stratagem_mgr._pending_reactions), 1)

    def test_brutal_example_bodyguard_loss_resolves_before_overwatch_shooting(self):
        army = Army.with_detachment("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        bodyguard, leader = self._setup_units_with_brutal_example(army)
        army.units = [bodyguard, leader]

        ranged_weapon = Wargear(
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
        surviving_bodyguard = self._make_model("Bodyguard Survivor", bodyguard)
        bodyguard.models.append(surviving_bodyguard)
        bodyguard.models[0].wargear = [ranged_weapon]
        bodyguard.models[1].wargear = [ranged_weapon]
        leader.models[0].wargear = []

        order = []
        removed = {}

        def _resolve_bodyguard_loss_immediately(**kwargs):
            order.append("loss")
            model = bodyguard.models[0]
            removed["model"] = model
            model.die(game_map=None)
            return model

        def _execute_shooting_declarations(_declarations, _game_map, out_of_phase=False):
            order.append("shoot")
            self.assertEqual(order, ["loss", "shoot"])
            self.assertEqual(len(bodyguard.models), 1)
            self.assertIsNot(bodyguard.models[0], removed.get("model"))
            self.assertTrue(out_of_phase)
            return True

        bodyguard.execute_shooting_declarations = _execute_shooting_declarations
        bodyguard.mark_traitor_enforcer_overwatch_used = lambda *_a, **_k: order.append("mark")
        bodyguard.get_traitor_enforcer_overwatch_rule = lambda: {"leader_id": leader._id}
        bodyguard.is_battle_shocked = lambda: False
        bodyguard.can_use_traitor_enforcer_overwatch = lambda game=None: True

        defender_player = SimpleNamespace(
            name="Defender",
            id="defender-player",
            command_points=1,
            get_army=lambda: army,
            apply_stratagem_cp_cost=lambda *_a, **_k: {
                "cost": 0,
                "traitor_enforcer_overwatch_use": True,
                "traitor_enforcer_overwatch_source": "Brutal Example",
            },
            spend_command_points=lambda *_a, **_k: True,
        )

        enemy_unit = SimpleNamespace(
            name="Enemy",
            models=[],
            is_overwatch_prevented_against=lambda _target, game=None: False,
        )
        game = SimpleNamespace(
            get_current_player=lambda: SimpleNamespace(name="Attacker", id="attacker-player"),
            map=SimpleNamespace(get_distance_between_units=lambda _a, _b: 10.0),
            resolve_bodyguard_loss_immediately=_resolve_bodyguard_loss_immediately,
        )

        stratagem_mgr = StratagemManager.__new__(StratagemManager)
        stratagem_mgr.player = defender_player
        stratagem_mgr.game = game
        stratagem_mgr._used_this_turn = {}
        stratagem_mgr._used_stratagems_this_phase = set()
        stratagem_mgr._current_phase_name = "Charge phase"
        stratagem_mgr._pending_reactions = []
        stratagem_mgr._queue_reaction = lambda reaction: stratagem_mgr._pending_reactions.append(reaction)
        stratagem_mgr._dequeue_reaction_by_name = lambda _name: None
        stratagem_mgr._is_overwatch_shooter_blocked_this_turn = lambda _unit: False
        stratagem_mgr.get_by_name = lambda _name: SimpleNamespace(
            name="FIRE OVERWATCH",
            is_phase_allowed=lambda _phase: True,
            is_turn_allowed=lambda _is_active: True,
            cp_cost=1,
        )

        assert stratagem_mgr.use("FIRE OVERWATCH", shooter_unit=bodyguard, enemy_unit=enemy_unit, phase_name="Charge phase")
        self.assertEqual(order, ["loss", "shoot", "mark"])


if __name__ == "__main__":
    unittest.main()
