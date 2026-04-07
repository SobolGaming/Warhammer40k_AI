import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestTyranidsSingularPurpose(unittest.TestCase):
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
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0, disembarked_from_transport_id="")
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit._characteristic_modifiers = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.get_models_for_collision = lambda: list(unit.models)
        unit.get_models_for_wound_allocation = lambda: list(unit.models)
        unit.is_in_reserves = lambda: False
        unit.has_any_keyword = lambda kw: any(
            str(kw or "").strip().upper() == str(k or "").strip().upper()
            for k in (unit.keywords + unit.faction_keywords)
        )
        unit.has_keyword = unit.has_any_keyword
        return unit

    def _make_model(self, name, unit, *, wounds: int = 1):
        model = Model(
            name=name,
            movement=6,
            toughness=5,
            save=2,
            wounds=int(wounds),
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def _find_quarry_request(self, game, ability_key: str):
        for req in list(game.decision_queue.list() or []):
            if req.decision_type != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") == str(ability_key):
                return req
        return None

    def _aura_stub(self):
        return SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

    def _make_profile(self, *, weapon_type="Ranged", skill="4+", strength="5"):
        parent = SimpleNamespace(
            name="Test Weapon",
            is_melee=lambda: str(weapon_type).strip().lower() == "melee",
            is_ranged=lambda: str(weapon_type).strip().lower() == "ranged",
        )
        data = {
            "range": "Melee" if str(weapon_type).strip().lower() == "melee" else "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        }
        return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)

    def _singular_purpose_ability(self):
        desc = (
            "At the start of the first battle round, select one of the following: "
            "- Select one enemy unit. Until the end of the battle, each time this model makes an attack that targets that unit, "
            "you can re-roll the Hit roll and you can re-roll the Wound roll. "
            "- Select one objective marker. Until the end of the battle, while this model is within range of that objective marker, "
            "it has the Feel No Pain 5+ ability and an Objective Control characteristic of 15."
        )
        return Ability("Singular Purpose", "TYR", desc, "Datasheet", "")

    def test_singular_purpose_enemy_branch_queues_and_grants_hit_wound_rerolls(self):
        army = Army.with_detachment("Tyranids", detachment_type="Other")
        army.faction_id = "TYR"
        enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])

        source_unit = self._make_unit(
            "Norn Emissary",
            army,
            abilities=[self._singular_purpose_ability()],
            faction_keywords=["TYRANIDS"],
        )
        source_model = self._make_model("Norn Emissary", source_unit, wounds=16)
        source_model.abilities = {"Singular Purpose": self._singular_purpose_ability()}
        source_unit.models = [source_model]
        army.units = [source_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_unit.models = [self._make_model("Target Model", target_unit, wounds=3)]
        other_enemy = self._make_unit("Other Enemy", enemy_army)
        other_enemy.models = [self._make_model("Other Enemy Model", other_enemy, wounds=3)]
        enemy_army.units = [target_unit, other_enemy]

        near_objective = SimpleNamespace(
            id="obj-near",
            name="Near Objective",
            location=SimpleNamespace(id="obj-near-loc", x=0.0, y=0.0, z=0.0, control_radius=3.0, removed=False),
        )
        game.objectives = [near_objective]
        game.map.objectives = [near_objective]
        game.map.roll_reroll_provider = lambda **kwargs: not kwargs.get("success")

        game.rebuild_entity_registry()
        army.on_battle_round_start(1)
        request = self._find_quarry_request(game, "singular_purpose")
        self.assertIsNotNone(request)

        enemy_options = [opt for opt in list(request.options or []) if str((opt.payload or {}).get("mode", "")) == "enemy_unit"]
        objective_options = [opt for opt in list(request.options or []) if str((opt.payload or {}).get("mode", "")) == "objective_marker"]
        self.assertTrue(enemy_options)
        self.assertTrue(objective_options)

        selected_option = None
        for opt in enemy_options:
            payload = dict(opt.payload or {})
            if str(payload.get("target_unit_id", "") or "") == str(target_unit._id):
                selected_option = str(opt.option_id)
                break
        self.assertIsNotNone(selected_option)

        cmd_result = resolve_decision_command(game, request, selected_option, player_id=player.id)
        apply_result = getattr(cmd_result, "value", None)
        self.assertTrue(apply_result.ok, msg=str(apply_result.errors))
        self.assertEqual(str(source_unit.special_rules.get("singular_purpose_mode", "") or ""), "enemy_unit")
        self.assertEqual(
            str(source_unit.special_rules.get("singular_purpose_target_unit_id", "") or ""),
            str(target_unit._id),
        )
        target_ids = set(getattr(source_unit, "_singular_purpose_target_ids", set()) or set())
        self.assertIn(str(target_unit._id), target_ids)

        from warhammer40k_ai.units import wargear as wargear_mod

        profile = self._make_profile(weapon_type="Ranged", skill="4+", strength="5")
        seq = iter([2, 6])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _spec: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": self._aura_stub()}
            hit_res = profile._hit_target_with_tracking(target_unit, source_model, attack_instance)
            self.assertEqual(int(hit_res["roll"]), 6)
            self.assertTrue(any("Singular Purpose" in eff for eff in list(hit_res.get("special_effects", []) or [])))
        finally:
            wargear_mod.get_roll = old_get_roll

        profile = self._make_profile(weapon_type="Melee", skill="4+", strength="5")
        seq = iter([2, 6])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _spec: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": self._aura_stub()}
            wound_res = profile._wound_target_with_tracking(target_unit, source_model, attack_instance)
            self.assertEqual(int(wound_res["roll"]), 6)
            self.assertTrue(any("Singular Purpose" in eff for eff in list(wound_res.get("special_effects", []) or [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_singular_purpose_objective_branch_grants_source_model_fnp_and_oc(self):
        army = Army.with_detachment("Tyranids", detachment_type="Other")
        army.faction_id = "TYR"
        enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])

        source_unit = self._make_unit(
            "Norn Assimilator",
            army,
            abilities=[self._singular_purpose_ability()],
            faction_keywords=["TYRANIDS"],
        )
        source_model = self._make_model("Norn Assimilator A", source_unit, wounds=16)
        other_model = self._make_model("Norn Assimilator B", source_unit, wounds=16)
        source_model.abilities = {"Singular Purpose": self._singular_purpose_ability()}
        other_model.abilities = {"Singular Purpose": self._singular_purpose_ability()}
        source_unit.models = [source_model, other_model]
        army.units = [source_unit]

        enemy = self._make_unit("Enemy", enemy_army)
        enemy.models = [self._make_model("Enemy Model", enemy, wounds=3)]
        enemy_army.units = [enemy]

        near_objective = SimpleNamespace(
            id="obj-near",
            name="Near Objective",
            location=SimpleNamespace(id="obj-near-loc", x=0.0, y=0.0, z=0.0, control_radius=3.0, removed=False),
        )
        far_objective = SimpleNamespace(
            id="obj-far",
            name="Far Objective",
            location=SimpleNamespace(id="obj-far-loc", x=24.0, y=24.0, z=0.0, control_radius=3.0, removed=False),
        )
        game.objectives = [near_objective, far_objective]
        game.map.objectives = [near_objective, far_objective]

        game.rebuild_entity_registry()
        army.on_battle_round_start(1)
        request = self._find_quarry_request(game, "singular_purpose")
        self.assertIsNotNone(request)

        selected_option = None
        for opt in list(request.options or []):
            payload = dict(opt.payload or {})
            if str(payload.get("mode", "") or "") != "objective_marker":
                continue
            if str(payload.get("objective_id", "") or "") == "obj-near":
                selected_option = str(opt.option_id)
                break
        self.assertIsNotNone(selected_option)

        cmd_result = resolve_decision_command(game, request, selected_option, player_id=player.id)
        apply_result = getattr(cmd_result, "value", None)
        self.assertTrue(apply_result.ok, msg=str(apply_result.errors))
        self.assertEqual(str(source_unit.special_rules.get("singular_purpose_mode", "") or ""), "objective_marker")
        self.assertEqual(str(source_unit.special_rules.get("singular_purpose_objective_id", "") or ""), "obj-near")

        self.assertTrue(source_unit.singular_purpose_objective_effects_active(model=source_model, game=game))
        self.assertFalse(source_unit.singular_purpose_objective_effects_active(model=other_model, game=game))

        fnp_source = list(source_unit.has_feel_no_pain(target_model=source_model) or [])
        fnp_other = list(source_unit.has_feel_no_pain(target_model=other_model) or [])
        self.assertIn((5, None), fnp_source)
        self.assertNotIn((5, None), fnp_other)

        self.assertEqual(int(source_model.objective_control), 15)
        self.assertEqual(int(other_model.objective_control), 1)

        source_model.set_location(20.0, 20.0, 0.0, 0.0)
        self.assertFalse(source_unit.singular_purpose_objective_effects_active(model=source_model, game=game))
        self.assertEqual(int(source_model.objective_control), 1)
        fnp_source_far = list(source_unit.has_feel_no_pain(target_model=source_model) or [])
        self.assertNotIn((5, None), fnp_source_far)


if __name__ == "__main__":
    unittest.main()
