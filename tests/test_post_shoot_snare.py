import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestPostShootSnare(unittest.TestCase):
    def _make_unit(self, name, army, *, abilities=None, keywords=None, faction_keywords=None):
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

    def _make_model(self, name, unit, *, wounds: int = 1):
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

    def test_post_shoot_snare_triggers_move_mortals(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability_desc = (
            "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those "
            "attacks made with its shadow weaver. Until the start of your next turn, that enemy unit is snared. "
            "While a unit is snared, each time that unit makes a Normal, Advance or Fall Back move, roll one D6 for "
            "each model in that unit: for each 1, that unit suffers 1 mortal wound."
        )
        ability = Ability("Snare", "AE", ability_desc, "Datasheet", "")

        attacker_unit = self._make_unit("Support Weapon", army, abilities=[ability], faction_keywords=["AELDARI"])
        attacker_model = self._make_model("Shadow Weaver", attacker_unit)
        attacker_model.abilities = {"Snare": ability}
        attacker_unit.models = [attacker_model]
        army.units = [attacker_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_model_a = self._make_model("Target A", target_unit, wounds=1)
        target_model_b = self._make_model("Target B", target_unit, wounds=1)
        target_unit.models = [target_model_a, target_model_b]
        enemy_army.units = [target_unit]

        game.rebuild_entity_registry()

        weapon_key = attacker_unit._normalize_keyword_phrase("shadow weaver")
        hit_models_by_target_weapon = {target_unit: {weapon_key: {attacker_model}}}
        hits_by_target = {target_unit: 1}

        game._on_unit_shooting_resolved_post_shoot_snare(
            attacker_unit=attacker_unit,
            hits_by_target=hits_by_target,
            hit_models_by_target_weapon=hit_models_by_target_weapon,
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "post_shoot_snare")

        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        sr = getattr(target_unit, "special_rules", {}) or {}
        self.assertTrue(sr.get("snared_active"))

        game.is_authoritative = False
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=1):
            game._on_unit_move_ended_snared_mortal_wounds(unit=target_unit, action="move")

        self.assertEqual(len(target_unit.models), 0)


if __name__ == "__main__":
    unittest.main()
