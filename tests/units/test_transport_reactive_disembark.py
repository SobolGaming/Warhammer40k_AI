import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize, BattleRoundPhases
from warhammer40k_ai.engine.decision_kinds import DECISION_DISEMBARK
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


REACTIVE_DISEMBARK_TEXT = (
    "In your opponent's Movement phase, each time an enemy unit is set up or ends a Normal, Advance or Fall Back move "
    "within 9\" of this model, any units embarked within it can disembark."
)


class TestTransportReactiveDisembark(unittest.TestCase):
    def _make_unit(self, name, army, *, keywords=None, abilities=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.keywords = list(keywords or [])
        unit.faction_keywords = []
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(embarked_this_round=False, disembarked_this_round=False)
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit.transport_passengers = []
        unit._ability_cache = {}
        return unit

    def _make_model(self, name, unit, x, y):
        model = Model(
            name=name,
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(x, y, 0.0, 0.0)
        return model

    def test_transport_reactive_disembark_remote_queues_decisions(self):
        army_move = Army.with_detachment("Attackers", detachment_type="Other")
        army_move.faction_id = "ATK"
        army_react = Army.with_detachment("Defenders", detachment_type="Other")
        army_react.faction_id = "DEF"

        moving_player = Player("Mover", PlayerControl.LOCAL, army=army_move)
        reacting_player = Player("Reactor", PlayerControl.REMOTE, army=army_react)

        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, players=[moving_player, reacting_player])
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0

        transport = self._make_unit(
            "Transport",
            army_react,
            keywords=["Transport"],
            abilities=[Ability("Reactive Disembark", "DEF", REACTIVE_DISEMBARK_TEXT, "")],
        )
        passenger_a = self._make_unit("Passengers A", army_react)
        passenger_b = self._make_unit("Passengers B", army_react)
        enemy = self._make_unit("Enemy", army_move)

        transport.models = [self._make_model("Transport", transport, 5.0, 0.0)]
        passenger_a.models = [self._make_model("A", passenger_a, 0.0, 0.0)]
        passenger_b.models = [self._make_model("B", passenger_b, 0.0, 1.0)]
        enemy.models = [self._make_model("Enemy", enemy, 0.0, 0.0)]

        transport.transport_passengers = [passenger_a, passenger_b]
        passenger_a.embarked_in = transport
        passenger_b.embarked_in = transport

        army_react.units = [transport, passenger_a, passenger_b]
        army_move.units = [enemy]
        game.map.units = [transport, enemy]

        game.event_system.publish(
            "unit_move_ended",
            unit=enemy,
            action="move",
        )

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_DISEMBARK]
        self.assertEqual(len(pending), 2)
        unit_ids = {str(req.context.get("unit_id", "")) for req in pending}
        self.assertEqual(unit_ids, {get_entity_id(passenger_a), get_entity_id(passenger_b)})
        for req in pending:
            ctx = req.context or {}
            self.assertTrue(bool(ctx.get("reactive_disembark", False)))
            self.assertEqual(ctx.get("transport_id"), get_entity_id(transport))
            self.assertEqual(ctx.get("reactive_disembark_enemy_unit_id"), get_entity_id(enemy))

    def test_transport_reactive_disembark_does_not_auto_resolve_with_decision_hook(self):
        army_move = Army.with_detachment("Attackers", detachment_type="Other")
        army_move.faction_id = "ATK"
        army_react = Army.with_detachment("Defenders", detachment_type="Other")
        army_react.faction_id = "DEF"

        moving_player = Player("Mover", PlayerControl.LOCAL, army=army_move)
        reacting_player = Player("Reactor", PlayerControl.REMOTE, army=army_react)
        reacting_player.decision_hook = lambda *_args, **_kwargs: True

        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, players=[moving_player, reacting_player])
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0

        transport = self._make_unit(
            "Transport",
            army_react,
            keywords=["Transport"],
            abilities=[Ability("Reactive Disembark", "DEF", REACTIVE_DISEMBARK_TEXT, "")],
        )
        passenger_a = self._make_unit("Passengers A", army_react)
        passenger_b = self._make_unit("Passengers B", army_react)
        enemy = self._make_unit("Enemy", army_move)

        transport.models = [self._make_model("Transport", transport, 5.0, 0.0)]
        passenger_a.models = [self._make_model("A", passenger_a, 0.0, 0.0)]
        passenger_b.models = [self._make_model("B", passenger_b, 0.0, 1.0)]
        enemy.models = [self._make_model("Enemy", enemy, 0.0, 0.0)]

        transport.transport_passengers = [passenger_a, passenger_b]
        passenger_a.embarked_in = transport
        passenger_b.embarked_in = transport

        army_react.units = [transport, passenger_a, passenger_b]
        army_move.units = [enemy]
        game.map.units = [transport, enemy]

        game.event_system.publish(
            "unit_move_ended",
            unit=enemy,
            action="move",
        )

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_DISEMBARK]
        self.assertEqual(len(pending), 2)


if __name__ == "__main__":
    unittest.main()
