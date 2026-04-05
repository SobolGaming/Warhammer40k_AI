import unittest
from types import SimpleNamespace
from unittest import mock

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.utility.entity_registry import EntityRegistry
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry
from warhammer40k_ai.battlefield.map import Map


class TestChaosDaemonsShootingCoverAbilities(unittest.TestCase):
    def _make_unit(self, name, army, *, abilities=None, keywords=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.keywords = list(keywords or [])
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
        return unit

    def _make_model(self, name, unit, *, x=0.0, y=0.0, z=0.0, wounds=10, radius=1.0):
        model = Model(
            name=name,
            movement=6,
            toughness=6,
            save=3,
            wounds=int(wounds),
            leadership=7,
            objective_control=2,
            model_base=Base(BaseType.CIRCULAR, radius),
        )
        model.parent_unit = unit
        model.set_location(float(x), float(y), float(z), 0.0)
        return model

    def test_eldritch_flames_no_cover_spec_any_weapon(self):
        army = Army("Chaos Daemons", detachment_type="Other")
        army.faction_id = "CD"
        ability_desc = (
            "In your Shooting phase, after this model has shot, select one enemy unit that was hit by one or more of those attacks. "
            "Until the end of the phase, that unit cannot have the Benefit of Cover."
        )
        ability = Ability("Eldritch Flames (Psychic)", "CD", ability_desc, "Datasheet", "")
        unit = self._make_unit("Burning Chariot", army, abilities=[ability])
        specs = unit.unit_post_shoot_no_cover_specs()
        self.assertEqual(len(specs), 1)
        self.assertTrue(specs[0].get("any_weapon"))
        self.assertIsNone(specs[0].get("weapon_key"))

    def test_deaths_heads_post_shoot_wound_reroll(self):
        army = Army("Chaos Daemons", detachment_type="Other")
        army.faction_id = "CD"
        ability_desc = (
            "In your Shooting phase, after this unit has shot, select one enemy unit hit by one or more of those attacks. "
            "Until the end of the turn, each time a friendly Nurgle Legiones Daemonica unit makes an attack that targets that unit, "
            "you can re-roll the Wound roll."
        )
        ability = Ability("Death's Heads", "CD", ability_desc, "Datasheet", "")
        attacker = self._make_unit(
            "Plague Drones",
            army,
            abilities=[ability],
            keywords=["NURGLE", "LEGIONES DAEMONICA"],
        )
        target_army = Army("Target", detachment_type="Other")
        target_army.faction_id = "TA"
        target = self._make_unit("Target", target_army)
        army.units = [attacker]
        target_army.units = [target]

        player = Player("P1", PlayerControl.REMOTE, army=army)
        enemy_player = Player("P2", PlayerControl.REMOTE, army=target_army)
        game = SimpleNamespace(turn=1, get_current_player=lambda: player)
        player.game = game
        enemy_player.game = game

        registry = EntityRegistry()
        registry.register(attacker, kind="unit")
        registry.register(target, kind="unit")
        game.entity_registry = registry

        specs = attacker.unit_post_shoot_keyword_wound_reroll_specs()
        self.assertEqual(len(specs), 1)
        ctx = {
            "ability": "post_shoot_keyword_wound_reroll",
            "ability_name": "Death's Heads",
            "attacker_unit_id": attacker._id,
            "keyword_phrase": specs[0]["keyword_phrase"],
        }
        options = [DecisionOption.create("Target", payload={"target_unit_id": target._id})]
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Death's Heads",
            player_id=player.id,
            options=options,
            context=ctx,
        )
        res = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=req.options[0].option_id)
        _apply_choose_quarry(game, req, res)

        mods = attacker.get_unit_wound_reroll_modifiers("any", target=target)
        self.assertTrue(mods.get("reroll_wound_full"))

    def test_deaths_heads_death_guard_wording_post_shoot_wound_reroll(self):
        army = Army("Death Guard", detachment_type="Other")
        army.faction_id = "DG"
        ability_desc = (
            "In your Shooting phase, after this unit has shot, select one enemy unit hit by one or more of those attacks. "
            "Until the end of the turn, each time a friendly Plague Legions unit makes an attack that targets that unit, "
            "you can re-roll the Wound roll."
        )
        ability = Ability("Death's Heads", "DG", ability_desc, "Datasheet", "")
        attacker = self._make_unit(
            "Plague Drones",
            army,
            abilities=[ability],
            keywords=["PLAGUE LEGIONS"],
        )
        target_army = Army("Target", detachment_type="Other")
        target_army.faction_id = "TA"
        target = self._make_unit("Target", target_army)
        army.units = [attacker]
        target_army.units = [target]

        player = Player("P1", PlayerControl.REMOTE, army=army)
        enemy_player = Player("P2", PlayerControl.REMOTE, army=target_army)
        game = SimpleNamespace(turn=1, get_current_player=lambda: player)
        player.game = game
        enemy_player.game = game

        registry = EntityRegistry()
        registry.register(attacker, kind="unit")
        registry.register(target, kind="unit")
        game.entity_registry = registry

        specs = attacker.unit_post_shoot_keyword_wound_reroll_specs()
        self.assertEqual(len(specs), 1)
        ctx = {
            "ability": "post_shoot_keyword_wound_reroll",
            "ability_name": "Death's Heads",
            "attacker_unit_id": attacker._id,
            "keyword_phrase": specs[0]["keyword_phrase"],
        }
        options = [DecisionOption.create("Target", payload={"target_unit_id": target._id})]
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Death's Heads",
            player_id=player.id,
            options=options,
            context=ctx,
        )
        res = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=req.options[0].option_id)
        _apply_choose_quarry(game, req, res)

        mods = attacker.get_unit_wound_reroll_modifiers("any", target=target)
        self.assertTrue(mods.get("reroll_wound_full"))

    def test_death_hex_roll_success_marks_target(self):
        army = Army("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        ability_desc = (
            "At the start of your Shooting phase, one Psyker with this ability can use it. "
            "If it does, select one enemy unit within 12\" of and visible to that Psyker and roll one D6: "
            "on a 1, that Psyker’s unit suffers D3 mortal wounds; on a 2+, until the start of your next Movement phase, "
            "each time an attack targets that enemy unit, improve the Armour Penetration characteristic of that attack by 1."
        )
        ability = Ability("Death Hex (Psychic)", "CSM", ability_desc, "Datasheet", "")
        source = self._make_unit("Sorcerer", army, abilities=[ability], keywords=["PSYKER"])
        source_model = self._make_model("Sorcerer", source, wounds=6)
        source.models = [source_model]
        target_army = Army("Target", detachment_type="Other")
        target = self._make_unit("Target", target_army)
        target_model = self._make_model("Target", target)
        target.models = [target_model]
        army.units = [source]
        target_army.units = [target]

        player = Player("P1", PlayerControl.REMOTE, army=army)
        enemy_player = Player("P2", PlayerControl.REMOTE, army=target_army)
        game = SimpleNamespace(turn=1, get_current_player=lambda: player, map=None)
        player.game = game
        enemy_player.game = game

        registry = EntityRegistry()
        registry.register(source, kind="unit")
        registry.register(target, kind="unit")
        registry.register(source_model, kind="model")
        game.entity_registry = registry

        options = [DecisionOption.create("Target", payload={"target_unit_id": target._id, "model_id": source_model._id, "source_unit_id": source._id})]
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Death Hex",
            player_id=player.id,
            options=options,
            context={"ability": "death_hex", "ability_name": "Death Hex", "ability_key": "DEATH_HEX", "ap_bonus": 1},
        )
        res = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=req.options[0].option_id)
        with mock.patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[4]):
            _apply_choose_quarry(game, req, res)

        sr = target.special_rules
        self.assertTrue(sr.get("death_hex_active"))
        self.assertEqual(sr.get("death_hex_ap_bonus"), 1)

    def test_opponent_shooting_phase_disrupt_roll_6_blocks_shooting(self):
        attacker_army = Army("Chaos Daemons", detachment_type="Other")
        attacker_army.faction_id = "CD"
        source = self._make_unit("Changeling", attacker_army)
        source_model = self._make_model("Changeling", source)
        source.models = [source_model]
        attacker_army.units = [source]

        target_army = Army("Target", detachment_type="Other")
        target = self._make_unit("Target", target_army)
        target_model = self._make_model("Target", target)
        target.models = [target_model]
        target_army.units = [target]

        attacker_player = Player("P1", PlayerControl.REMOTE, army=attacker_army)
        target_player = Player("P2", PlayerControl.REMOTE, army=target_army)
        game = SimpleNamespace(turn=1, get_current_player=lambda: target_player, map=None)
        attacker_player.game = game
        target_player.game = game

        registry = EntityRegistry()
        registry.register(source, kind="unit")
        registry.register(target, kind="unit")
        registry.register(source_model, kind="model")
        game.entity_registry = registry

        options = [DecisionOption.create("Target", payload={"target_unit_id": target._id, "model_id": source_model._id, "source_unit_id": source._id})]
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Mischief and Confusion",
            player_id=attacker_player.id,
            options=options,
            context={
                "ability": "opponent_shooting_phase_disrupt",
                "ability_name": "Mischief and Confusion",
                "ability_key": "MISCHIEF_AND_CONFUSION",
                "mortal_on_one": False,
                "limit_one_per_army": False,
            },
        )
        res = DecisionResult(decision_id=req.decision_id, player_id=attacker_player.id, option_id=req.options[0].option_id)
        with mock.patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[6]):
            _apply_choose_quarry(game, req, res)

        self.assertTrue(target.is_shooting_phase_ineligible(game))

    def test_fortification_cover_detection(self):
        army = Army("Chaos Daemons", detachment_type="Other")
        army.faction_id = "CD"
        fort_desc = (
            "Each time a ranged attack is allocated to a model, if that model is not fully visible to every model in the attacking unit "
            "because of this FORTIFICATION, that model has the Benefit of Cover against that attack."
        )
        fort_ability = Ability("Cover", "CD", fort_desc, "Datasheet", "")
        fort = self._make_unit("Skull Altar", army, abilities=[fort_ability], keywords=["FORTIFICATION"])
        fort_model = self._make_model("Skull Altar", fort, x=5.0, y=0.0, radius=1.0)
        fort.models = [fort_model]

        attacker = self._make_unit("Attacker", army)
        attacker_model = self._make_model("Attacker", attacker, x=0.0, y=0.0)
        attacker.models = [attacker_model]

        target_army = Army("Target", detachment_type="Other")
        target = self._make_unit("Target", target_army)
        target_model = self._make_model("Target", target, x=10.0, y=0.0)
        target.models = [target_model]

        game_map = Map(60, 44)
        cover_info = game_map.get_benefit_of_cover_from_fortifications(
            attacking_unit=attacker,
            target_model=target_model,
            fortification_units=[fort],
        )
        self.assertTrue(cover_info.get("has_benefit_of_cover"))

    def test_diseased_cover_death_guard_wording_detection(self):
        army = Army("Death Guard", detachment_type="Other")
        army.faction_id = "DG"
        fort_desc = (
            "Each time a ranged attack is allocated to a model, if that model is not fully visible to the attacking unit "
            "because of this Fortification, that model has the Benefit of Cover against that attack."
        )
        fort_ability = Ability("Diseased Cover", "DG", fort_desc, "Datasheet", "")
        fort = self._make_unit("Miasmic Malignifier", army, abilities=[fort_ability], keywords=["FORTIFICATION"])
        fort_model = self._make_model("Miasmic Malignifier", fort, x=5.0, y=0.0, radius=1.0)
        fort.models = [fort_model]

        attacker = self._make_unit("Attacker", army)
        attacker_model = self._make_model("Attacker", attacker, x=0.0, y=0.0)
        attacker.models = [attacker_model]

        target_army = Army("Target", detachment_type="Other")
        target = self._make_unit("Target", target_army)
        target_model = self._make_model("Target", target, x=10.0, y=0.0)
        target.models = [target_model]

        game_map = Map(60, 44)
        cover_info = game_map.get_benefit_of_cover_from_fortifications(
            attacking_unit=attacker,
            target_model=target_model,
            fortification_units=[fort],
        )
        self.assertTrue(cover_info.get("has_benefit_of_cover"))


if __name__ == "__main__":
    unittest.main()
