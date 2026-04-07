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


class TestPostShootNoCover(unittest.TestCase):
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

    def test_post_shoot_no_cover_marks_target(self):
        army = Army.with_detachment("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability_desc = (
            "In your Shooting phase, after this unit has shot, select one enemy unit hit by one or more of those "
            "attacks made with a long rifle. Until the end of the phase, that enemy unit cannot have the Benefit of Cover."
        )
        ability = Ability("No Cover", "AE", ability_desc, "Datasheet", "")

        attacker_unit = self._make_unit("Rangers", army, abilities=[ability], faction_keywords=["AELDARI"])
        attacker_model = self._make_model("Ranger", attacker_unit)
        attacker_unit.models = [attacker_model]
        army.units = [attacker_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_model = self._make_model("Target", target_unit)
        target_model.set_location(6.0, 0.0, 0.0, 0.0)
        target_unit.models = [target_model]
        enemy_army.units = [target_unit]

        game.rebuild_entity_registry()

        weapon_key = attacker_unit._normalize_keyword_phrase("long rifle")
        hit_models_by_target_weapon = {target_unit: {weapon_key: {attacker_model}}}
        hits_by_target = {target_unit: 1}

        game._on_unit_shooting_resolved_post_shoot_no_cover(
            attacker_unit=attacker_unit,
            hits_by_target=hits_by_target,
            hit_models_by_target_weapon=hit_models_by_target_weapon,
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "post_shoot_no_cover")

        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        sr = getattr(target_unit, "special_rules", {}) or {}
        self.assertTrue(sr.get("post_shoot_no_cover_active"))

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
        ranged_parent = SimpleNamespace(name="Long rifle", is_ranged=lambda: True, is_melee=lambda: False)
        profile = WargearProfile(
            profile_name="Rifle",
            wargear_data={
                "range": "36",
                "A": "1",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
        )
        attack_instance = {"_aura_attack_mods": aura_stub}
        profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance, roll_value=4, allow_rerolls=False)
        self.assertTrue(attack_instance.get("ignores_cover", False))

    def test_post_shoot_no_cover_model_any_weapon_marks_target(self):
        army = Army.with_detachment("Death Guard", detachment_type="Other")
        army.faction_id = "DG"
        enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability_desc = (
            "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those attacks. "
            "Until the end of the phase, that unit cannot have the Benefit of Cover."
        )
        ability = Ability("Barrage of Filth", "DG", ability_desc, "Datasheet", "")

        attacker_unit = self._make_unit("Defiler", army, abilities=[ability], faction_keywords=["DEATH GUARD"])
        attacker_model = self._make_model("Defiler", attacker_unit)
        attacker_unit.models = [attacker_model]
        army.units = [attacker_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_model = self._make_model("Target", target_unit)
        target_model.set_location(6.0, 0.0, 0.0, 0.0)
        target_unit.models = [target_model]
        enemy_army.units = [target_unit]

        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_no_cover(
            attacker_unit=attacker_unit,
            hits_by_target={target_unit: 1},
            hit_models_by_target_weapon={},
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        self.assertEqual((request.context or {}).get("ability"), "post_shoot_no_cover")

        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        sr = getattr(target_unit, "special_rules", {}) or {}
        self.assertTrue(bool(sr.get("post_shoot_no_cover_active")))


if __name__ == "__main__":
    unittest.main()
