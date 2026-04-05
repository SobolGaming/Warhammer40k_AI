import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_ALLOCATE_DAMAGE,
    DECISION_SELECT_REVERBERATING_SUMMONS_UNIT,
)
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


def _make_unit(name, army, *, keywords=None):
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
    unit.faction_keywords = []
    unit.status_effects = []
    unit.special_rules = {}
    unit.possible_abilities = []
    unit.round_state = SimpleNamespace()
    unit.attached_leaders = []
    unit.attached_to = None
    unit.embarked_in = None
    unit.can_be_attached_to = []
    unit._ability_cache = {}
    unit.starting_model_count = 0
    return unit


def _make_model(name, unit, x, y):
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


def _make_reverberating_profile():
    return WargearProfile(
        "Test Profile",
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "Reverberating Summons",
        },
    )


class TestReverberatingSummons(unittest.TestCase):
    def _build_game(self):
        attacker_army = Army("Chaos Daemons", detachment_type="Test")
        attacker_army.faction_id = "CD"
        defender_army = Army("Opponents", detachment_type="Test")
        defender_army.faction_id = "OP"

        attacker = Player("Attacker", PlayerControl.REMOTE, army=attacker_army)
        defender = Player("Defender", PlayerControl.LOCAL, army=defender_army)

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[attacker, defender])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        return game, attacker, attacker_army, defender_army

    def _arrange_units(self):
        game, attacker, attacker_army, defender_army = self._build_game()

        attacker_unit = _make_unit("Bearer", attacker_army)
        attacker_model = _make_model("Bearer Model", attacker_unit, 0.0, 0.0)
        attacker_unit.models = [attacker_model]

        plague_a = _make_unit("Plague A", attacker_army, keywords=["PLAGUEBEARERS"])
        plague_b = _make_unit("Plague B", attacker_army, keywords=["PLAGUEBEARERS"])

        plague_a_alive = _make_model("Plague A1", plague_a, 6.0, 0.0)
        plague_a_dead = _make_model("Plague A Dead", plague_a, 6.0, 0.0)
        plague_a.models = [plague_a_alive]
        plague_a.models_lost = [plague_a_dead]
        plague_a.starting_model_count = 2

        plague_b_alive = _make_model("Plague B1", plague_b, 10.0, 0.0)
        plague_b_dead = _make_model("Plague B Dead", plague_b, 10.0, 0.0)
        plague_b.models = [plague_b_alive]
        plague_b.models_lost = [plague_b_dead]
        plague_b.starting_model_count = 2

        target_unit = _make_unit("Target", defender_army)
        target_model = _make_model("Target Model", target_unit, 24.0, 0.0)
        target_unit.models = [target_model]

        attacker_army.units = [attacker_unit, plague_a, plague_b]
        defender_army.units = [target_unit]
        game.map.units = [attacker_unit, plague_a, plague_b, target_unit]
        game.rebuild_entity_registry()

        return (
            game,
            attacker,
            attacker_unit,
            attacker_model,
            target_unit,
            target_model,
            plague_a,
            plague_b,
            plague_b_dead,
        )

    def test_reverberating_summons_remote_flow_returns_model(self):
        (
            game,
            attacker,
            attacker_unit,
            attacker_model,
            target_unit,
            target_model,
            plague_a,
            plague_b,
            plague_b_dead,
        ) = self._arrange_units()

        profile = _make_reverberating_profile()
        game.event_system.publish(
            "model_destroyed",
            attacker_model=attacker_model,
            attacker_unit=attacker_unit,
            target_model=target_model,
            target_unit=target_unit,
            weapon_profile=profile,
        )

        pending = [
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_SELECT_REVERBERATING_SUMMONS_UNIT
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]

        unit_option = next(
            opt
            for opt in request.options
            if str((opt.payload or {}).get("unit_id", "")) == get_entity_id(plague_b)
        )
        resolve_decision_command(game, request, unit_option.option_id, player_id=attacker.id)

        model_request = next(
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_ALLOCATE_DAMAGE
        )
        self.assertEqual(model_request.context.get("selection_kind"), "reverberating_summons_return")
        self.assertEqual(model_request.context.get("unit_id"), get_entity_id(plague_b))

        model_option = next(
            opt
            for opt in model_request.options
            if str((opt.payload or {}).get("model_id", "")) == get_entity_id(plague_b_dead)
        )
        resolve_decision_command(game, model_request, model_option.option_id, player_id=attacker.id)

        self.assertIn(plague_b_dead, plague_b.models)
        self.assertNotIn(plague_b_dead, plague_b.models_lost)
        self.assertEqual(len(plague_b.models), 2)
        self.assertEqual(len(plague_a.models), 1)

    def test_reverberating_summons_rejects_invalid_option(self):
        game, attacker, attacker_unit, attacker_model, target_unit, target_model, *_rest = self._arrange_units()

        profile = _make_reverberating_profile()
        game.event_system.publish(
            "model_destroyed",
            attacker_model=attacker_model,
            attacker_unit=attacker_unit,
            target_model=target_model,
            target_unit=target_unit,
            weapon_profile=profile,
        )

        request = next(
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_SELECT_REVERBERATING_SUMMONS_UNIT
        )
        result = resolve_decision_command(game, request, "bad-option", player_id=attacker.id)
        self.assertFalse(bool(result.ok))
        self.assertIs(game.decision_queue.peek(), request)


if __name__ == "__main__":
    unittest.main()
