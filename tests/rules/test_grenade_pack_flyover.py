import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_REQUEST_DICE_ROLL
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestGrenadePackFlyover(unittest.TestCase):
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
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0)
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

    def test_grenade_pack_flyover_queues_and_rolls(self):
        army = Army.with_detachment("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0
        game.auto_resolve_dice_rolls = False

        ability_desc = (
            "Once per turn, in your Movement phase, when this unit is set up on the battlefield or ends a Normal, "
            "Advance or Fall Back move, it can use this ability. If it does, select one enemy unit within 8\" of and "
            "visible to this unit and roll one D6 for each Swooping Hawks model in this unit: for each 4+, that enemy "
            "unit suffers 1 mortal wound (to a maximum of 6 mortal wounds). Each time this unit uses this ability, "
            "until the end of the turn, you cannot target this unit with the Grenade Stratagem."
        )
        ability = Ability("Grenade Pack Flyover", "AE", ability_desc, "Datasheet", "")

        unit = self._make_unit("Swooping Hawks", army, faction_keywords=["AELDARI"], abilities=[ability])
        model = self._make_model("Swooping Hawk", unit, x=0.0)
        unit.models = [model]
        unit._attacking_unit_has_any_los_to_target_unit = lambda _target, _map: True

        target_unit = self._make_unit("Target", enemy_army)
        target_model = self._make_model("Target", target_unit, x=6.0)
        target_unit.models = [target_model]

        army.units = [unit]
        enemy_army.units = [target_unit]
        game.rebuild_entity_registry()
        game.map.units = [unit, target_unit]

        game._on_unit_move_ended_grenade_pack_flyover(unit=unit, action="move")

        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "grenade_pack_flyover")

        target_id = get_entity_id(target_unit)
        option_id = None
        for opt in list(request.options or []):
            if opt.payload.get("target_unit_id") == target_id:
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)

        resolve_decision_command(game, request, option_id, player_id=player.id)

        sr = getattr(unit, "special_rules", {}) or {}
        self.assertTrue(sr.get("grenade_pack_flyover_used_turn_owner"))
        self.assertTrue(sr.get("grenade_pack_flyover_no_grenade_turn_owner"))

        roll_requests = [r for r in list(game.decision_queue.list() or []) if r.decision_type == DECISION_REQUEST_DICE_ROLL]
        self.assertEqual(len(roll_requests), 1)


if __name__ == "__main__":
    unittest.main()
