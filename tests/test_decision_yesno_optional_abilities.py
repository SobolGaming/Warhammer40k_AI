import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestYesNoOptionalAbilityDecisions(unittest.TestCase):
    def _make_unit(self, name, army, *, keywords=None, faction_keywords=None, abilities=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.keywords = list(keywords or [])
        unit.faction_keywords = list(faction_keywords or [])
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.has_any_keyword = lambda kw: any(
            str(kw or "").strip().upper() == str(k or "").strip().upper()
            for k in (unit.keywords + unit.faction_keywords)
        )
        return unit

    def _make_model(self, name, unit):
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
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def test_shadow_in_the_warp_queues_and_applies(self):
        tyr_army = Army("Tyranids", detachment_type="Other")
        tyr_army.faction_id = "TYR"
        enemy_army = Army("Enemies", detachment_type="Other")
        enemy_army.faction_id = "SM"

        tyr_player = Player("Tyr", PlayerControl.REMOTE, army=tyr_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, players=[tyr_player, enemy_player])
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0

        synapse = self._make_unit(
            "Synapse",
            tyr_army,
            faction_keywords=["TYRANIDS"],
            abilities=[Ability("Shadow in the Warp", "TYR", "", "")],
        )
        tyr_army.units = [synapse]

        game._maybe_prompt_shadow_in_the_warp()

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "shadow_in_the_warp")

        option_id = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=tyr_player.id)

        self.assertTrue(tyr_army.shadow_in_the_warp.used_this_battle)

    def test_waaagh_queues_and_applies(self):
        ork_army = Army("Orks", detachment_type="Other")
        ork_army.faction_id = "ORK"
        enemy_army = Army("Enemies", detachment_type="Other")
        enemy_army.faction_id = "SM"

        ork_player = Player("Ork", PlayerControl.REMOTE, army=ork_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, players=[ork_player, enemy_player])
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0

        mgr = ork_army.waaagh
        if mgr is not None:
            mgr._army_has_waaagh = lambda: True

        game._maybe_prompt_waaagh()

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "waaagh")

        option_id = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=ork_player.id)

        self.assertTrue(mgr.used_this_battle)
        self.assertTrue(mgr.active)
        self.assertIs(mgr.called_player, ork_player)

    def test_possessed_lord_queues_and_applies(self):
        army = Army("Chaos", detachment_type="Other")
        army.faction_id = "CSM"
        player = Player("Chaos", PlayerControl.REMOTE, army=army)
        other_army = Army("Enemies", detachment_type="Other")
        other_player = Player("Enemy", PlayerControl.REMOTE, army=other_army)

        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, players=[player, other_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        unit = self._make_unit(
            "Possessed Lord Unit",
            army,
            abilities=[Ability("Possessed Lord", "CSM", "", "")],
        )
        model = self._make_model("Possessed Lord", unit)
        unit.models = [model]
        army.units = [unit]
        game.rebuild_entity_registry()

        game._on_phase_start_optional_abilities(player=player, phase=game.phase)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "possessed_lord")
        self.assertEqual(ctx.get("model_id"), get_entity_id(model))

        option_id = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=player.id)

        self.assertTrue(model.has_used_once_per_battle("possessed_lord"))


if __name__ == "__main__":
    unittest.main()
