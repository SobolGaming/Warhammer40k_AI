import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_value
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


MIRACULOUS_SAVIOUR_TEXT = (
    "Once per battle, at the end of your opponent's Charge phase, if this model is still in Reserves, you can select "
    "one enemy unit that made a Charge move this phase. Set this model up on the battlefield within Engagement Range "
    "of that enemy unit."
)


class TestAdeptaSororitasMiraculousSaviour(unittest.TestCase):
    def _make_unit(self, name, army, *, ability_text=None, deployed=True, reserve_status="deployed"):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = bool(deployed)
        unit.reserve_status = str(reserve_status)
        unit.reserve_turn_deployed = 0
        unit.arrived_from_reserves_this_turn = False
        unit.models = []
        unit.keywords = []
        unit.faction_keywords = []
        unit.possible_abilities = []
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(
            remained_stationary_this_round=True,
            advanced_this_round=False,
            shot_this_round=False,
            fell_back_this_round=False,
            reinforced_this_round=False,
            attempted_charge_this_round=False,
            charged_this_round=False,
            action_locked_until_turn_end=False,
            disembarked_cannot_charge=False,
            disembarked_from_destroyed_transport=False,
        )
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        if ability_text:
            unit.possible_abilities = [Ability("Miraculous Saviour", unit.faction, ability_text, "")]
        return unit

    def _make_model(self, name, unit, x, y):
        model = Model(
            name=name,
            movement=6,
            toughness=4,
            save=3,
            wounds=4,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(x, y, 0.0, 0.0)
        return model

    def _build_game(self):
        enemy_army = Army("Enemy Army", detachment_type="Other")
        enemy_army.faction_id = "EN"
        sororitas_army = Army("Adepta Sororitas", detachment_type="Other")
        sororitas_army.faction_id = "AS"

        enemy_player = Player("Enemy", PlayerControl.LOCAL, army=enemy_army)
        sororitas_player = Player("Sororitas", PlayerControl.REMOTE, army=sororitas_army)

        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, players=[enemy_player, sororitas_player])
        game.current_player_index = 0
        game.phase = BattleRoundPhases.CHARGE_PHASE
        return game, enemy_player, sororitas_player, enemy_army, sororitas_army

    def _arrange_units(self):
        game, enemy_player, sororitas_player, enemy_army, sororitas_army = self._build_game()
        enemy_unit = self._make_unit("Charging Enemy", enemy_army, deployed=True, reserve_status="deployed")
        source_unit = self._make_unit(
            "Saint Celestine",
            sororitas_army,
            ability_text=MIRACULOUS_SAVIOUR_TEXT,
            deployed=False,
            reserve_status="reserves",
        )
        enemy_unit.round_state.charged_this_round = True
        enemy_unit.models = [self._make_model("Enemy Model", enemy_unit, 20.0, 20.0)]
        source_unit.models = [self._make_model("Celestine", source_unit, 40.0, 40.0)]
        enemy_army.units = [enemy_unit]
        sororitas_army.units = [source_unit]
        game.map.units = [enemy_unit]
        game.rebuild_entity_registry()
        return game, enemy_player, sororitas_player, enemy_unit, source_unit

    def test_miraculous_saviour_queues_choose_quarry_at_end_of_opponent_charge_phase(self):
        game, enemy_player, _sororitas_player, enemy_unit, _source_unit = self._arrange_units()

        game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.CHARGE_PHASE)

        pending = [
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "") or "") == "miraculous_saviour"
        ]
        self.assertEqual(len(pending), 1)
        target_ids = [
            str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            for opt in list(getattr(pending[0], "options", []) or [])
        ]
        self.assertIn(str(get_entity_id(enemy_unit) or ""), target_ids)

    def test_miraculous_saviour_choice_sets_up_model_and_marks_used(self):
        game, enemy_player, sororitas_player, enemy_unit, source_unit = self._arrange_units()

        game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.CHARGE_PHASE)
        request = next(
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "") or "") == "miraculous_saviour"
        )
        target_option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            == str(get_entity_id(enemy_unit) or "")
        )

        _value, apply_result = resolve_decision_value(
            game,
            request,
            target_option.option_id,
            player_id=sororitas_player.id,
        )
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertTrue(bool(source_unit.deployed))
        self.assertFalse(bool(source_unit.is_in_reserves()))
        self.assertTrue(bool(source_unit.round_state.reinforced_this_round))
        self.assertTrue(bool(source_unit.has_used_unit_once_per_battle("miraculous_saviour")))
        self.assertTrue(bool(game.map.is_within_engagement_range(source_unit, enemy_unit)))

        game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.CHARGE_PHASE)
        follow_up = [
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "") or "") == "miraculous_saviour"
        ]
        self.assertEqual(len(follow_up), 0)

    def test_miraculous_saviour_does_not_trigger_when_not_in_reserves(self):
        game, enemy_player, _sororitas_player, _enemy_unit, source_unit = self._arrange_units()
        source_unit.deployed = True
        source_unit.reserve_status = "deployed"

        game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.CHARGE_PHASE)

        pending = [
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "") or "") == "miraculous_saviour"
        ]
        self.assertEqual(len(pending), 0)


if __name__ == "__main__":
    unittest.main()
