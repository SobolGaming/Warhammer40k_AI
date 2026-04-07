import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestEndOfFightEmbark(unittest.TestCase):
    def _make_unit(self, name, army, *, keywords=None, faction_keywords=None, abilities=None):
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
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0, disembarked_this_round=False)
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.is_in_reserves = lambda: False
        unit.has_any_keyword = lambda kw: any(
            str(kw or "").strip().upper() == str(k or "").strip().upper()
            for k in (unit.keywords + unit.faction_keywords)
        )
        return unit

    def _make_model(self, name, unit, x=0.0):
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
        model.set_location(x, 0.0, 0.0, 0.0)
        return model

    def test_end_of_fight_embark(self):
        army = Army.with_detachment("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        player = Player("Player", PlayerControl.REMOTE, army=army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        ability_desc = (
            "At the end of the Fight phase, if there are no models currently embarked within this Transport, you can "
            "select one friendly Harlequins Infantry unit that has 6 or fewer models that is wholly within 6\" of this "
            "Transport. Unless that unit is within Engagement Range of one or more enemy units, it can embark within "
            "this Transport."
        )
        ability = Ability("Rapid Embarkation", "AE", ability_desc, "Datasheet", "")

        transport = self._make_unit(
            "Starweaver",
            army,
            keywords=["Transport"],
            faction_keywords=["AELDARI"],
            abilities=[ability],
        )
        transport_model = self._make_model("Starweaver", transport, x=0.0)
        transport.models = [transport_model]
        transport.transport_capacity = 6
        transport.transport_passengers = []
        transport.transport_required_keywords = set()
        transport.transport_excluded_keywords = set()

        passenger = self._make_unit(
            "Harlequins Troupe",
            army,
            keywords=["Infantry", "Harlequins"],
            faction_keywords=["AELDARI"],
        )
        passenger_model = self._make_model("Troupe", passenger, x=3.0)
        passenger.models = [passenger_model]

        army.units = [transport, passenger]
        game.map.units = [transport, passenger]
        game.rebuild_entity_registry()

        game._on_phase_end_transport_end_of_fight_embark(player=player, phase=game.phase)

        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "end_of_fight_embark")

        target_id = get_entity_id(passenger)
        option_id = None
        for opt in list(request.options or []):
            if opt.payload.get("target_unit_id") == target_id:
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)

        resolve_decision_command(game, request, option_id, player_id=player.id)

        self.assertIs(passenger.embarked_in, transport)
        self.assertIn(passenger, transport.transport_passengers)


if __name__ == "__main__":
    unittest.main()
