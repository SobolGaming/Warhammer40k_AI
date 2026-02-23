import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestTyranidsUnendingSwarmInsurmountableOdds(unittest.TestCase):
    def _make_unit(self, name, army, *, keywords=None, faction_keywords=None, faction="TYRANIDS"):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = faction
        unit.deployed = True
        unit.models = []
        unit.keywords = list(keywords or [])
        unit.faction_keywords = list(faction_keywords or [])
        unit.possible_abilities = []
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
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

    def _build_game(self):
        army_attacker = Army("Enemy", detachment_type="Other")
        army_attacker.faction_id = "SM"
        army_target = Army("Tyranids", detachment_type="Unending Swarm")
        army_target.faction_id = "TYR"

        p1 = Player("P1", PlayerControl.LOCAL, army=army_attacker)
        p2 = Player("P2", PlayerControl.REMOTE, army=army_target)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        return game, p1, p2, army_attacker, army_target

    def test_insurmountable_odds_applies_only_to_endless_multitude_units(self):
        _game, _p1, _p2, _army_attacker, army_target = self._build_game()

        endless = self._make_unit(
            "Termagants",
            army_target,
            keywords=["INFANTRY", "ENDLESS MULTITUDE", "TYRANIDS"],
            faction_keywords=["TYRANIDS"],
        )
        non_endless = self._make_unit(
            "Warriors",
            army_target,
            keywords=["INFANTRY", "TYRANIDS"],
            faction_keywords=["TYRANIDS"],
        )
        army_target.units = [endless, non_endless]

        self.assertTrue(endless.has_insurmountable_odds())
        self.assertTrue(endless.has_horde_move())
        self.assertFalse(non_endless.has_insurmountable_odds())
        self.assertFalse(non_endless.has_horde_move())

    def test_insurmountable_odds_queues_reactive_move_after_shooting_casualties(self):
        game, _p1, p2, army_attacker, army_target = self._build_game()

        attacker = self._make_unit("Shooter", army_attacker, keywords=["INFANTRY"], faction_keywords=["SM"], faction="SM")
        target = self._make_unit(
            "Gaunts",
            army_target,
            keywords=["INFANTRY", "ENDLESS MULTITUDE", "TYRANIDS"],
            faction_keywords=["TYRANIDS"],
        )
        army_attacker.units = [attacker]
        army_target.units = [target]

        attacker_model = self._make_model("Shooter", attacker, 0.0, 0.0)
        target_model_a = self._make_model("Gaunt A", target, 10.0, 0.0)
        target_model_b = self._make_model("Gaunt B", target, 12.0, 0.0)
        attacker.models = [attacker_model]
        target.models = [target_model_a, target_model_b]
        game.map.units = [attacker, target]

        game.event_system.publish(
            "shooting_targets_selected",
            attacking_unit=attacker,
            target_units=[target],
        )
        target_model_a.wounds = 0
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=attacker,
            hits_by_target={target: 1},
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        self.assertEqual(request.player_id, p2.id)
        ctx = request.context or {}
        self.assertEqual(ctx.get("reactive_move_kind"), "horde_move")
        self.assertEqual(ctx.get("reactive_move_unit_id"), get_entity_id(target))
        self.assertEqual(ctx.get("reactive_move_attacker_unit_id"), get_entity_id(attacker))
        self.assertEqual(str(ctx.get("reactive_move_source", "") or ""), "Insurmountable Odds")

        yes_option = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                yes_option = opt
                break
        self.assertIsNotNone(yes_option)

        resolve_decision_command(game, request, yes_option.option_id, player_id=p2.id)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        move_request = pending[0]
        self.assertEqual(move_request.decision_type, DECISION_MOVE_UNIT)
        move_ctx = move_request.context or {}
        self.assertEqual(move_ctx.get("movement_type"), "horde_move")
        self.assertGreater(int(move_ctx.get("max_distance") or 0), 0)


if __name__ == "__main__":
    unittest.main()
