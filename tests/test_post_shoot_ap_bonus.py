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


class TestPostShootApBonus(unittest.TestCase):
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

    def test_post_shoot_ap_bonus_marks_target_and_applies(self):
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
            "In your Shooting phase, after this unit has shot, select one enemy unit hit by one or more of those attacks. "
            "Until the end of the phase, each time a friendly AELDARI unit makes an attack that targets that enemy unit, "
            "improve the Armour Penetration characteristic of that attack by 1. Each unit can only be selected for this ability once per turn."
        )
        ability = Ability("Crystalline Targeting", "AE", ability_desc, "Datasheet", "")

        attacker_unit = self._make_unit("War Walkers", army, abilities=[ability], faction_keywords=["AELDARI"])
        attacker_model = self._make_model("War Walker", attacker_unit)
        attacker_unit.models = [attacker_model]
        army.units = [attacker_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_model = self._make_model("Target", target_unit)
        target_model.set_location(6.0, 0.0, 0.0, 0.0)
        target_unit.models = [target_model]
        enemy_army.units = [target_unit]

        game.rebuild_entity_registry()

        hits_by_target = {target_unit: 1}
        game._on_unit_shooting_resolved_post_shoot_ap_bonus(
            attacker_unit=attacker_unit,
            hits_by_target=hits_by_target,
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "post_shoot_ap_bonus")
        self.assertEqual(ctx.get("keyword"), "aeldari")
        self.assertEqual(ctx.get("attack_type"), "any")
        self.assertEqual(ctx.get("duration"), "phase_end")
        self.assertEqual(ctx.get("limit_scope"), "turn")

        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        sr = getattr(target_unit, "special_rules", {}) or {}
        self.assertTrue(sr.get("post_shoot_ap_bonus_active"))

        ranged_parent = SimpleNamespace(name="Shuriken", is_ranged=lambda: True, is_melee=lambda: False)
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
        effective_ap = profile.get_effective_ap(attacker_model, target_unit)
        self.assertEqual(effective_ap, -1)

        ally_unit = self._make_unit("Allies", army)
        ally_model = self._make_model("Ally", ally_unit)
        ally_unit.models = [ally_model]
        effective_ap_non_aeldari = profile.get_effective_ap(ally_model, target_unit)
        self.assertEqual(effective_ap_non_aeldari, 0)

        game._on_unit_shooting_resolved_post_shoot_ap_bonus(
            attacker_unit=attacker_unit,
            hits_by_target=hits_by_target,
        )
        self.assertEqual(len(game.decision_queue.list()), 0)

    def test_post_shoot_ap_bonus_turn_end_melee_only(self):
        army = Army("Tyranids", detachment_type="Other")
        army.faction_id = "TYR"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability_desc = (
            "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those attacks. "
            "Until the end of the turn, each time a friendly TYRANIDS unit makes a melee attack that targets that enemy unit, "
            "improve the Armour Penetration characteristic of that attack by 1. "
            "The same enemy unit can only be affected by this ability once per turn."
        )
        ability = Ability("Bio-stimulus", "TYR", ability_desc, "Datasheet", "")

        attacker_unit = self._make_unit("Psychophage", army, abilities=[ability], faction_keywords=["TYRANIDS"])
        attacker_model = self._make_model("Psychophage", attacker_unit)
        attacker_unit.models = [attacker_model]

        ally_unit = self._make_unit("Hormagaunts", army, faction_keywords=["TYRANIDS"])
        ally_model = self._make_model("Hormagaunt", ally_unit)
        ally_unit.models = [ally_model]
        army.units = [attacker_unit, ally_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_model = self._make_model("Target", target_unit)
        target_model.set_location(6.0, 0.0, 0.0, 0.0)
        target_unit.models = [target_model]
        enemy_army.units = [target_unit]

        game.rebuild_entity_registry()

        hits_by_target = {target_unit: 1}
        game._on_unit_shooting_resolved_post_shoot_ap_bonus(
            attacker_unit=attacker_unit,
            hits_by_target=hits_by_target,
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        ctx = request.context or {}
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        self.assertEqual(ctx.get("attack_type"), "melee")
        self.assertEqual(ctx.get("duration"), "turn_end")
        self.assertEqual(ctx.get("limit_scope"), "turn")

        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        sr = getattr(target_unit, "special_rules", {}) or {}
        self.assertTrue(sr.get("post_shoot_ap_bonus_active"))
        self.assertEqual(str(sr.get("post_shoot_ap_bonus_expires_timing", "")), "TURN_END")
        self.assertIsNone(sr.get("post_shoot_ap_bonus_expires_phase"))

        game._on_unit_shooting_resolved_post_shoot_ap_bonus(
            attacker_unit=attacker_unit,
            hits_by_target=hits_by_target,
        )
        self.assertEqual(len(game.decision_queue.list()), 0)

        melee_parent = SimpleNamespace(name="Talons", is_ranged=lambda: False, is_melee=lambda: True)
        ranged_parent = SimpleNamespace(name="Sprayer", is_ranged=lambda: True, is_melee=lambda: False)
        melee_profile = WargearProfile(
            profile_name="Melee",
            wargear_data={"range": "Melee", "A": "1", "BS_WS": "4+", "S": "4", "AP": "0", "D": "1", "description": ""},
            parent_wargear=melee_parent,
        )
        ranged_profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={"range": "18", "A": "1", "BS_WS": "4+", "S": "4", "AP": "0", "D": "1", "description": ""},
            parent_wargear=ranged_parent,
        )

        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        self.assertEqual(melee_profile.get_effective_ap(ally_model, target_unit), -1)
        self.assertEqual(ranged_profile.get_effective_ap(ally_model, target_unit), 0)

        game.current_player_index = 1
        self.assertEqual(melee_profile.get_effective_ap(ally_model, target_unit), 0)

    def test_post_shoot_ap_bonus_excludes_monster_vehicle_candidates(self):
        army = Army("Death Guard", detachment_type="Other")
        army.faction_id = "DG"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability_desc = (
            "In your Shooting phase, after this model has shot, select one enemy unit (excluding MONSTERS and VEHICLES) "
            "hit by one or more of those attacks. Until the end of the phase, each time a friendly Death Guard unit makes "
            "a ranged attack that targets that enemy unit, improve the Armour Penetration characteristic of that attack by 1. "
            "The same enemy unit can only be affected by this ability once per phase."
        )
        ability = Ability("Hail of Corrosive Disease", "DG", ability_desc, "Datasheet", "")

        attacker_unit = self._make_unit("Chaos Predator Destructor", army, abilities=[ability], faction_keywords=["DEATH GUARD"])
        attacker_model = self._make_model("Predator", attacker_unit)
        attacker_unit.models = [attacker_model]
        army.units = [attacker_unit]

        infantry_target = self._make_unit("Infantry Target", enemy_army, keywords=["INFANTRY"])
        infantry_target.models = [self._make_model("Infantry", infantry_target)]

        monster_target = self._make_unit("Monster Target", enemy_army, keywords=["MONSTER"])
        monster_target.models = [self._make_model("Monster", monster_target)]

        vehicle_target = self._make_unit("Vehicle Target", enemy_army, keywords=["VEHICLE"])
        vehicle_target.models = [self._make_model("Vehicle", vehicle_target)]

        enemy_army.units = [infantry_target, monster_target, vehicle_target]
        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_ap_bonus(
            attacker_unit=attacker_unit,
            hits_by_target={
                infantry_target: 1,
                monster_target: 1,
                vehicle_target: 1,
            },
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        option_ids = {str((opt.payload or {}).get("target_unit_id", "")) for opt in list(request.options or [])}
        self.assertIn(str(infantry_target._id), option_ids)
        self.assertNotIn(str(monster_target._id), option_ids)
        self.assertNotIn(str(vehicle_target._id), option_ids)

    def test_hailstrike_marks_only_hit_non_monster_vehicle_target(self):
        army = Army("Space Marines", detachment_type="Other")
        army.faction_id = "SM"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability_desc = (
            "Each time this model has shot, select one enemy unit (excluding MONSTERS and VEHICLES) hit by one or more of those attacks. "
            "Until the end of the phase, each time a friendly ADEPTUS ASTARTES unit makes a ranged attack that targets that enemy unit, "
            "improve the Armour Penetration characteristic of that attack by 1. "
            "The same enemy unit can only be affected by this ability once per phase."
        )
        ability = Ability("Hailstrike", "SM", ability_desc, "Datasheet", "")

        attacker_unit = self._make_unit(
            "Storm Speeder Hailstrike",
            army,
            abilities=[ability],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        attacker_model = self._make_model("Storm Speeder", attacker_unit)
        attacker_unit.models = [attacker_model]

        ally_unit = self._make_unit("Intercessors", army, faction_keywords=["ADEPTUS ASTARTES"])
        ally_model = self._make_model("Intercessor", ally_unit)
        ally_unit.models = [ally_model]
        army.units = [attacker_unit, ally_unit]

        target_unit = self._make_unit("Enemy Infantry", enemy_army, keywords=["INFANTRY"])
        target_model = self._make_model("Enemy Infantry", target_unit)
        target_unit.models = [target_model]

        monster_unit = self._make_unit("Enemy Monster", enemy_army, keywords=["MONSTER"])
        monster_model = self._make_model("Enemy Monster", monster_unit)
        monster_unit.models = [monster_model]

        enemy_army.units = [target_unit, monster_unit]
        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_ap_bonus(
            attacker_unit=attacker_unit,
            hits_by_target={target_unit: 1, monster_unit: 1},
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(len(request.options), 1)
        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        sr = getattr(target_unit, "special_rules", {}) or {}
        self.assertTrue(sr.get("post_shoot_ap_bonus_active"))

        ranged_parent = SimpleNamespace(name="Bolt Rifle", is_ranged=lambda: True, is_melee=lambda: False)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
        )
        self.assertEqual(profile.get_effective_ap(ally_model, target_unit), -1)
        self.assertEqual(profile.get_effective_ap(ally_model, monster_unit), 0)


if __name__ == "__main__":
    unittest.main()
