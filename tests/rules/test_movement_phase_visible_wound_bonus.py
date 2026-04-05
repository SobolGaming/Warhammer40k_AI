import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestMovementPhaseVisibleWoundBonus(unittest.TestCase):
    def _make_unit(self, name, army, *, keywords=None, faction_keywords=None):
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

    def test_movement_phase_visible_wound_bonus(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0

        ability_desc = (
            "At the end of your Movement phase, select one enemy unit within 18\" of and visible to this model. "
            "Until the start of your next Command phase, each time a friendly AELDARI model makes an attack that "
            "targets that enemy unit, add 1 to the Wound roll."
        )
        ability = Ability("Doom", "AE", ability_desc, "Datasheet", "")

        unit = self._make_unit("Farseer", army, faction_keywords=["AELDARI"])
        model = self._make_model("Farseer", unit)
        model.abilities = {"Doom": ability}
        unit.models = [model]
        unit._has_line_of_sight_to_target = lambda _model, _target, _map: True

        target_unit = self._make_unit("Target", enemy_army)
        target_model = self._make_model("Target", target_unit)
        target_model.set_location(10.0, 0.0, 0.0, 0.0)
        target_unit.models = [target_model]

        army.units = [unit]
        enemy_army.units = [target_unit]
        game.rebuild_entity_registry()

        game._on_phase_end_movement_phase_visible_wound_bonus(player=player, phase=game.phase)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "movement_phase_visible_wound_bonus")

        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        sr = getattr(target_unit, "special_rules", {}) or {}
        self.assertTrue(sr.get("movement_phase_visible_wound_bonus_active"))
        self.assertEqual(int(sr.get("movement_phase_visible_wound_bonus_value", 0) or 0), 1)

        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )
        melee_parent = SimpleNamespace(name="Test Weapon", is_melee=lambda: True)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )
        from warhammer40k_ai.units import wargear as wargear_mod
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 4
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            wound_res = profile._wound_target_with_tracking(target_unit, model, attack_instance, allow_rerolls=False)
            self.assertTrue(any("Doom" in mod for mod in wound_res.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll


if __name__ == "__main__":
    unittest.main()
