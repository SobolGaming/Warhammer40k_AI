import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
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
    unit.transport_passengers = []
    unit._ability_cache = {}
    unit.enhancement = None
    unit.is_alive = lambda: True
    unit.get_parent_army = lambda: army
    unit.get_attached_unit_root = lambda: unit
    unit.get_attached_unit_models = lambda: list(unit.models)
    unit.get_attached_unit_members = lambda: [unit]
    unit.get_models_for_collision = lambda: list(unit.models)
    unit.is_in_reserves = lambda: unit.reserve_status in ("reserves", "strategic_reserves")
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


class TestAeldariGuilefulStrategist(unittest.TestCase):
    def test_guileful_strategist_redeploy_flow(self):
        army = Army("Aeldari", detachment_type="Armoured Warhost")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.attacker_index = 0
        game.defender_index = 1

        enhancer = Enhancement(
            id="000009769005",
            name="Guileful Strategist",
            faction_id="AE",
            detachment="Armoured Warhost",
            description=(
                "AELDARI model only. If your army includes the bearer, after both players have deployed their armies, "
                "select up to three Aeldari Vehicle units from your army and redeploy them. "
                "When doing so, any of those units can be placed into Strategic Reserves, regardless of how many units "
                "are already in Strategic Reserves."
            ),
        )

        bearer = _make_unit("Autarch", army, faction_keywords=["AELDARI", "CHARACTER"])
        bearer_model = _make_model("Autarch", bearer, x=0.0, y=0.0, wounds=5)
        bearer.models = [bearer_model]
        bearer.enhancement = enhancer
        enhancer.apply_to_unit(bearer)

        vehicle_a = _make_unit("Falcon", army, keywords=["VEHICLE"], faction_keywords=["AELDARI"])
        vehicle_a_model = _make_model("Falcon", vehicle_a, x=5.0, y=0.0, wounds=10)
        vehicle_a.models = [vehicle_a_model]

        vehicle_b = _make_unit("WaveSerpent", army, keywords=["VEHICLE"], faction_keywords=["AELDARI"])
        vehicle_b_model = _make_model("WaveSerpent", vehicle_b, x=7.0, y=0.0, wounds=13)
        vehicle_b.models = [vehicle_b_model]

        vehicle_reserve = _make_unit("FirePrism", army, keywords=["VEHICLE"], faction_keywords=["AELDARI"])
        vehicle_reserve.reserve_status = "strategic_reserves"
        vehicle_reserve.deployed = False

        infantry = _make_unit("Guardians", army, keywords=["INFANTRY"], faction_keywords=["AELDARI"])

        passengers = _make_unit("Passengers", army, keywords=["INFANTRY"], faction_keywords=["AELDARI"])
        passengers_model = _make_model("Passengers", passengers, x=0.0, y=0.0, wounds=1)
        passengers.models = [passengers_model]
        passengers.embarked_in = vehicle_a
        vehicle_a.transport_passengers = [passengers]

        army.units = [bearer, vehicle_a, vehicle_b, vehicle_reserve, infantry, passengers]
        game.map.units = [bearer, vehicle_a, vehicle_b, infantry]
        game.rebuild_entity_registry()

        game.execute_redeploy_units_phase()

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "aeldari_guileful_strategist")

        option_targets = {opt.payload.get("target_unit_id") for opt in request.options}
        self.assertIn(vehicle_a._id, option_targets)
        self.assertIn(vehicle_b._id, option_targets)
        self.assertNotIn(vehicle_reserve._id, option_targets)
        self.assertNotIn(infantry._id, option_targets)

        reserves_opt = next(
            opt
            for opt in request.options
            if opt.payload.get("target_unit_id") == vehicle_a._id
            and opt.payload.get("redeploy_action") == "strategic_reserves"
        )
        resolve_decision_command(game, request, reserves_opt.option_id, player_id=player.id)

        self.assertEqual(vehicle_a.reserve_status, "strategic_reserves")
        self.assertNotIn(vehicle_a, game.map.units)
        self.assertIs(passengers.embarked_in, vehicle_a)
        self.assertEqual(passengers.reserve_status, "strategic_reserves")

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        battlefield_opt = next(
            opt
            for opt in request.options
            if opt.payload.get("target_unit_id") == vehicle_b._id
            and opt.payload.get("redeploy_action") == "battlefield"
        )
        resolve_decision_command(game, request, battlefield_opt.option_id, player_id=player.id)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].decision_type, DECISION_MOVE_UNIT)
        self.assertTrue(bool(pending[0].context.get("redeploy_followup")))


if __name__ == "__main__":
    unittest.main()
