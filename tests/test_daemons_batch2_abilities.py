import unittest
from types import SimpleNamespace

from shapely.geometry import Polygon

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.utility.entity_registry import EntityRegistry
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry
from warhammer40k_ai.utility.aura_effects import get_enemy_aura_move_oc_penalties
from warhammer40k_ai.battlefield.map import Map, RuinsTerrain
from warhammer40k_ai.engine.game import Game


class TestDaemonsBatch2Abilities(unittest.TestCase):
    def _make_unit(self, name, army, *, abilities=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.keywords = []
        unit.faction_keywords = []
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0)
        unit.models_lost = []
        unit.attached_leaders = []
        unit.attached_to = None
        unit.embarked_in = None
        unit.can_be_attached_to = []
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.is_in_reserves = lambda: False
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.has_any_keyword = lambda _kw: False
        return unit

    def _make_model(self, name, unit, *, x=0.0, y=0.0, z=0.0, wounds=10):
        model = Model(
            name=name,
            movement=6,
            toughness=6,
            save=3,
            wounds=int(wounds),
            leadership=7,
            objective_control=2,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(float(x), float(y), float(z), 0.0)
        return model

    def _setup_attached_leader(self, army, *, ability_name, ability_desc):
        ability = Ability(ability_name, "CD", ability_desc, "Datasheet", "")
        bodyguard = self._make_unit("Bodyguard", army)
        leader = self._make_unit("Leader", army, abilities=[ability])
        leader.attached_to = bodyguard
        leader.can_be_attached_to = [bodyguard.name]
        bodyguard.attached_leaders = [leader]
        bodyguard.get_attached_unit_members = lambda: [bodyguard, leader]
        leader.get_attached_unit_root = lambda: bodyguard
        return bodyguard, leader, ability

    def test_beast_handler_heroic_intervention_discount_once(self):
        army = Army("Chaos Daemons", detachment_type="Other")
        army.faction_id = "CD"
        ability_desc = (
            "While this model is leading a unit, you can re-roll Charge rolls made for that unit. "
            "In addition, once per battle, you can target that unit with the Heroic Intervention Stratagem for 0CP, "
            "and can do so even if you have already used that Stratagem on a different unit this phase."
        )
        bodyguard, leader, _ability = self._setup_attached_leader(
            army,
            ability_name="Beast Handler",
            ability_desc=ability_desc,
        )
        bodyguard_model = self._make_model("Bodyguard", bodyguard)
        leader_model = self._make_model("Leader", leader)
        bodyguard.models = [bodyguard_model]
        leader.models = [leader_model]
        bodyguard.get_attached_unit_models = lambda: [bodyguard_model, leader_model]
        army.units = [bodyguard, leader]

        player = Player("Daemon", PlayerControl.REMOTE, army=army)
        player.game = SimpleNamespace(turn=1, players=[player])
        player.stratagems = SimpleNamespace(_used_this_turn={})

        strat = SimpleNamespace(name="Heroic Intervention", cp_cost=1)
        player.set_next_optional_decision("BEAST_HANDLER_HEROIC_INTERVENTION", True)
        applied = player.apply_stratagem_cp_cost(strat, target_unit=bodyguard)
        self.assertEqual(applied.get("cost"), 0)
        self.assertTrue(bodyguard.has_used_unit_once_per_battle("beast_handler_heroic_intervention"))
        self.assertFalse(bodyguard.can_use_beast_handler_heroic_intervention())

    def test_skullmasters_fury_grants_devastating_wounds(self):
        army = Army("Chaos Daemons", detachment_type="Other")
        army.faction_id = "CD"
        ability_desc = (
            "While this model is leading a unit, each time that unit ends a Charge move, until the end of the turn, "
            "Juggernaut’s bladed horns equipped by models in that unit have the [DEVASTATING WOUNDS] ability."
        )
        bodyguard, leader, _ability = self._setup_attached_leader(
            army,
            ability_name="Skullmaster’s Fury",
            ability_desc=ability_desc,
        )
        bodyguard_model = self._make_model("Bodyguard", bodyguard)
        leader_model = self._make_model("Leader", leader)
        bodyguard.models = [bodyguard_model]
        leader.models = [leader_model]
        bodyguard.get_attached_unit_models = lambda: [bodyguard_model, leader_model]
        army.units = [bodyguard, leader]

        applied = bodyguard._apply_charge_move_weapon_keyword_bonuses()
        self.assertTrue(applied)
        bonuses = bodyguard_model.get_temporary_weapon_keyword_bonuses("Juggernaut's bladed horns")
        keywords = {b.get("keyword") for b in bonuses}
        self.assertIn("DEVASTATING WOUNDS", keywords)

    def test_deluge_of_nurgle_aura_penalties(self):
        army = Army("Chaos Daemons", detachment_type="Other")
        army.faction_id = "CD"
        ability_desc = (
            "While an enemy unit is within 6\" of this model, subtract 2 from the Move characteristic and subtract 1 "
            "from the Objective Control characteristic of models in that unit."
        )
        ability = Ability("Deluge of Nurgle (Aura)", "CD", ability_desc, "Datasheet", "")
        source = self._make_unit("Rotigus", army, abilities=[ability])
        target = self._make_unit("Target", army)
        source.models = [self._make_model("Rotigus", source, x=0.0, y=0.0)]
        target.models = [self._make_model("Target", target, x=0.0, y=0.0)]

        class DummyMap:
            def get_enemy_units(self, unit):
                return [source] if unit is target else []

        move_pen, oc_pen = get_enemy_aura_move_oc_penalties(target, game_map=DummyMap())
        self.assertEqual(move_pen, -2)
        self.assertEqual(oc_pen, -1)

    def test_virulent_blessing_death_guard_wording_grants_damage_bonus(self):
        army = Army("Death Guard", detachment_type="Other")
        army.faction_id = "DG"
        ability_desc = (
            "At the start of the Fight phase, you can select one enemy unit within 24\" and visible to this model. "
            "Until the end of the phase, each time an attack made by a Plague Legions model is allocated to a model "
            "in that unit, add 1 to the Damage characteristic of that attack."
        )
        ability = Ability("Virulent Blessing (Psychic)", "DG", ability_desc, "Datasheet", "")
        source = self._make_unit("Rotigus", army, abilities=[ability])
        source_model = self._make_model("Rotigus", source, x=0.0, y=0.0)
        source.models = [source_model]

        target = self._make_unit("Enemy", army)
        target.models = [self._make_model("Enemy", target, x=2.0, y=0.0)]

        attacker = self._make_unit("Plague Unit", army)
        attacker.keywords = ["PLAGUE LEGIONS"]
        attacker.has_any_keyword = lambda kw: str(kw).strip().upper() in {
            str(k).strip().upper() for k in attacker.keywords
        }

        specs = source.model_start_fight_phase_target_attack_bonus_specs(source_model)
        self.assertEqual(len(specs), 1)
        spec = specs[0]
        self.assertEqual(spec["range"], 24)
        self.assertTrue(spec["requires_visibility"])
        self.assertEqual(spec["keyword"], "plague legions")
        self.assertEqual(spec["damage_bonus"], 1)

        target.apply_fight_phase_target_attack_bonus(
            owner_id="p1",
            turn=2,
            source="Virulent Blessing (Psychic)",
            keyword=spec["keyword"],
            attack_type=spec["attack_type"],
            damage_bonus=spec["damage_bonus"],
        )
        game = SimpleNamespace(phase=SimpleNamespace(name="FIGHT_PHASE"), turn=2)
        bonuses = target.get_fight_phase_target_attack_bonuses(attacker, game=game, attack_type="melee")
        self.assertEqual(int(bonuses.get("damage_bonus", 0) or 0), 1)

    def test_nurgles_rot_selection_applies_toughness_penalty_and_cleanup(self):
        army = Army("Chaos Daemons", detachment_type="Other")
        army.faction_id = "CD"
        ability_desc = (
            "At the end of your Movement phase, you can select one enemy unit within 12\" of this model. "
            "Until the start of your next Movement phase, subtract 1 from the Toughness characteristic of models in that unit."
        )
        ability = Ability("Nurgle’s Rot (Psychic)", "CD", ability_desc, "Datasheet", "")
        source = self._make_unit("Great Unclean One", army, abilities=[ability])
        source_model = self._make_model("Great Unclean One", source)
        source.models = [source_model]
        target = self._make_unit("Enemy", army)
        target_model = self._make_model("Enemy", target)
        target.models = [target_model]
        army.units = [source, target]

        specs = source.model_movement_phase_end_toughness_penalty_specs(source_model)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["range"], 12)
        self.assertEqual(specs[0]["penalty"], -1)

        player = SimpleNamespace(id="p1", name="Daemon", get_army=lambda: army)
        army.player = player

        game = SimpleNamespace(turn=2)
        registry = EntityRegistry()
        registry.register(source, kind="unit")
        registry.register(target, kind="unit")
        game.entity_registry = registry

        base_toughness = getattr(target_model, "_toughness", target_model.toughness)
        options = [DecisionOption.create("Enemy", payload={"target_unit_id": target._id})]
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Nurgle's Rot",
            player_id=player.id,
            options=options,
            context={
                "ability": "nurgles_rot",
                "ability_name": "Nurgle's Rot",
                "source_unit_id": source._id,
                "penalty": -1,
            },
        )
        res = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=req.options[0].option_id)
        _apply_choose_quarry(game, req, res)

        self.assertTrue(target.special_rules.get("nurgles_rot_active"))
        t_val = target.get_effective_model_characteristic(target_model, "toughness")
        self.assertEqual(t_val, base_toughness - 1)

        cleanup_game = Game.__new__(Game)
        cleanup_game.players = [player]
        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        cleanup_game._on_phase_start_nurgles_rot_cleanup(player=player, phase=phase)
        self.assertFalse(target.special_rules.get("nurgles_rot_active", False))

    def test_seed_the_garden_marks_terrain(self):
        army = Army("Chaos Daemons", detachment_type="Other")
        army.faction_id = "CD"
        ability_desc = (
            "At the end of your Movement phase, if this model is within one Area Terrain feature, until the end of the battle, "
            "that AREA TERRAIN feature is considered to be within your army’s Shadow of Chaos."
        )
        ability = Ability("Seed the Garden of Nurgle", "CD", ability_desc, "Datasheet", "")
        unit = self._make_unit("Horticulous Slimux", army, abilities=[ability])
        model = self._make_model("Horticulous Slimux", unit, x=1.0, y=1.0)
        unit.models = [model]
        army.units = [unit]

        player = SimpleNamespace(id="p1", name="Daemon", get_army=lambda: army)
        army.player = player

        game = Game.__new__(Game)
        game.players = [player]
        game.current_player_index = 0
        game.is_authoritative = True
        game.map = Map(60, 44)

        footprint = Polygon([(0, 0), (0, 5), (5, 5), (5, 0)])
        ruins = RuinsTerrain(footprint)
        game.map.terrain_features = [ruins]

        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game._on_phase_end_seed_the_garden_of_nurgle(player=player, phase=phase)
        self.assertIn(player.id, getattr(ruins, "shadow_of_chaos_owner_ids", set()))

    def test_fight_phase_destroyed_strategic_reserves_confirmation(self):
        unit = SimpleNamespace()
        unit._id = "warp-talons"
        unit.enter_strategic_reserves_midgame_called = False

        def _enter(*_args, **_kwargs):
            unit.enter_strategic_reserves_midgame_called = True
            return True

        unit.enter_strategic_reserves_midgame = _enter
        unit.get_parent_army = lambda: SimpleNamespace(player=SimpleNamespace(id="p1"))

        game = Game.__new__(Game)
        game.entity_registry = EntityRegistry()
        game.entity_registry.register(unit, kind="unit")
        game.map = SimpleNamespace()

        options = [DecisionOption.create("Use", payload={"choice": True, "unit_id": unit._id})]
        req = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            "Warp Strike",
            player_id="p1",
            options=options,
            context={"ability": "fight_phase_destroyed_strategic_reserves", "unit_id": unit._id, "ability_name": "Warp Strike"},
        )
        res = DecisionResult(decision_id=req.decision_id, player_id="p1", option_id=req.options[0].option_id)
        game._maybe_apply_optional_ability_confirmation(req, res)
        self.assertTrue(unit.enter_strategic_reserves_midgame_called)


if __name__ == "__main__":
    unittest.main()
