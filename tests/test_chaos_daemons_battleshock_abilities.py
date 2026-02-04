import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET,
    DECISION_SELECT_FIGHT_TARGETS,
)
from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_effects import get_aura_battleshock_test_reroll_sources
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


class DummyMap:
    def __init__(self, enemies=None, engaged=None, friendly=None):
        self._enemies = list(enemies or [])
        self._engaged = set(engaged or [])
        self._friendly = list(friendly or [])

    def get_enemy_units(self, _unit):
        return list(self._enemies)

    def is_within_engagement_range(self, _unit, enemy):
        return enemy in self._engaged

    def get_friendly_units(self, _unit):
        return list(self._friendly)


class TestChaosDaemonsBattleshockAbilities(unittest.TestCase):
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
        unit.has_keyword = unit.has_any_keyword
        return unit

    def _make_model(self, name, unit, *, x=0.0, y=0.0):
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
        model.set_location(float(x), float(y), 0.0, 0.0)
        return model

    def test_demagogue_queues_and_clears_battleshock(self):
        army = Army("Chaos", detachment_type="Other")
        army.faction_id = "CSM"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.turn = 2

        ability_desc = (
            "Once per battle, at the start of any phase, you can select one friendly HERETIC ASTARTES unit "
            "that is Battle-shocked and within 12\" of this unit’s DARK APOSTLE model. That unit is no longer Battle-shocked."
        )
        ability = Ability("Demagogue", "CSM", ability_desc, "Datasheet", "")

        source_unit = self._make_unit("Dark Apostle", army, keywords=["HERETIC ASTARTES"])
        source_model = self._make_model("Dark Apostle", source_unit, x=0.0, y=0.0)
        source_model.abilities = {"Demagogue": ability}
        source_unit.models = [source_model]
        source_unit.possible_abilities = [ability]

        target_unit = self._make_unit("Legionaries", army, keywords=["HERETIC ASTARTES"])
        target_model = self._make_model("Legionary", target_unit, x=1.0, y=0.0)
        target_unit.models = [target_model]
        target_unit.status_effects = [BattleShockEffect(1)]

        army.units = [source_unit, target_unit]
        enemy_army.units = []
        game.rebuild_entity_registry()

        game._on_phase_start_optional_abilities(phase=game.phase)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET)

        target_option = next(
            o for o in request.options if (o.payload or {}).get("unit_id") == target_unit._id
        )
        resolve_decision_command(game, request, target_option.option_id, player_id=player.id)

        self.assertFalse(target_unit.is_battle_shocked())

    def test_devastating_charge_triggers_battleshock(self):
        army = Army("Chaos", detachment_type="Other")
        army.faction_id = "CD"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.turn = 3

        ability_desc = (
            "Each time this model’s unit ends a Charge move, each enemy unit within Engagement Range of that unit "
            "must take a Battle-shock test."
        )
        ability = Ability("Devastating Charge", "CD", ability_desc, "Datasheet", "")

        source_unit = self._make_unit("Skullmaster", army, keywords=["LEGIONES DAEMONICA"])
        source_model = self._make_model("Skullmaster", source_unit)
        source_unit.models = [source_model]
        source_unit.possible_abilities = [ability]

        enemy_unit = self._make_unit("Target", enemy_army, keywords=["INFANTRY"])
        enemy_model = self._make_model("Target", enemy_unit)
        enemy_unit.models = [enemy_model]
        enemy_unit.tests = []
        enemy_unit.take_battle_shock_test = lambda turn=1: enemy_unit.tests.append(int(turn))

        army.units = [source_unit]
        enemy_army.units = [enemy_unit]

        dummy_map = DummyMap(enemies=[enemy_unit], engaged=[enemy_unit])
        game.map = dummy_map

        game._on_unit_move_ended_charge_battleshock(unit=source_unit, action="charge")

        self.assertEqual(enemy_unit.tests, [3])

    def test_disease_of_mirth_aura_excludes_monsters(self):
        army = Army("Chaos", detachment_type="Other")
        army.faction_id = "CD"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.turn = 1

        ability_desc = (
            "At the start of the Fight phase, every enemy unit (excluding MONSTERS and VEHICLES) within 6\" of this model "
            "must take a Battle-shock test."
        )
        ability = Ability("Disease of Mirth (Aura)", "CD", ability_desc, "Datasheet", "")

        source_unit = self._make_unit("Sloppity Bilepiper", army, keywords=["LEGIONES DAEMONICA"])
        source_model = self._make_model("Sloppity Bilepiper", source_unit, x=0.0, y=0.0)
        source_model.abilities = {"Disease of Mirth (Aura)": ability}
        source_unit.models = [source_model]
        source_unit.possible_abilities = [ability]

        infantry_unit = self._make_unit("Infantry", enemy_army, keywords=["INFANTRY"])
        infantry_model = self._make_model("Infantry", infantry_unit, x=3.0, y=0.0)
        infantry_unit.models = [infantry_model]
        infantry_unit.tests = []
        infantry_unit.take_battle_shock_test = lambda turn=1: infantry_unit.tests.append(int(turn))

        monster_unit = self._make_unit("Monster", enemy_army, keywords=["MONSTER"])
        monster_model = self._make_model("Monster", monster_unit, x=3.0, y=0.0)
        monster_unit.models = [monster_model]
        monster_unit.tests = []
        monster_unit.take_battle_shock_test = lambda turn=1: monster_unit.tests.append(int(turn))

        army.units = [source_unit]
        enemy_army.units = [infantry_unit, monster_unit]

        dummy_map = DummyMap(enemies=[infantry_unit, monster_unit], engaged=[])
        game.map = dummy_map

        game._on_phase_start_engagement_battleshock(player=player, phase=game.phase)

        self.assertEqual(infantry_unit.tests, [1])
        self.assertEqual(monster_unit.tests, [])

    def test_terrifying_assault_engagement_battleshock(self):
        army = Army("Chaos", detachment_type="Other")
        army.faction_id = "CSM"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.turn = 2

        ability_desc = (
            "At the start of the Fight phase, each enemy unit within Engagement Range of one or more units with this ability "
            "must take a Battle-shock test."
        )
        ability = Ability("Terrifying Assault", "CSM", ability_desc, "Datasheet", "")

        source_unit = self._make_unit("Raptors", army, keywords=["HERETIC ASTARTES"])
        source_model = self._make_model("Raptor", source_unit)
        source_unit.models = [source_model]
        source_unit.possible_abilities = [ability]

        enemy_unit = self._make_unit("Target", enemy_army, keywords=["INFANTRY"])
        enemy_model = self._make_model("Target", enemy_unit)
        enemy_unit.models = [enemy_model]
        enemy_unit.tests = []
        enemy_unit.take_battle_shock_test = lambda turn=1: enemy_unit.tests.append(int(turn))

    def test_formless_horror_gate_pass_allows_target_for_decision(self):
        army = Army("Chaos", detachment_type="Other")
        army.faction_id = "CD"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.turn = 1

        attacker = self._make_unit("Attacker", enemy_army, keywords=["INFANTRY"])
        target = self._make_unit("The Changeling", army, keywords=["LEGIONES DAEMONICA"])
        ability = Ability(
            "Formless Horror",
            "CD",
            "Each time an enemy unit wishes to select this model as the target of an attack, that unit must first take a Battle-shock test.",
            "Datasheet",
            "",
        )
        target.possible_abilities = [ability]

        army.units = [target]
        enemy_army.units = [attacker]
        game.rebuild_entity_registry()

        calls = []
        attacker.take_battle_shock_test = lambda turn=1: calls.append(int(turn))

        req = DecisionRequest.create(
            DECISION_SELECT_FIGHT_TARGETS,
            "Select target",
            player_id=player.id,
            options=[DecisionOption.create("Target", payload={"target_unit_id": target._id})],
            context={"unit_id": attacker._id},
        )
        result = DecisionResult(
            decision_id=req.decision_id,
            player_id=player.id,
            option_id=req.options[0].option_id,
            payload={"target_unit_ids": [target._id]},
        )
        apply_result = dispatch_decision(game, req, result)
        self.assertFalse(apply_result.ok)
        self.assertTrue(any("Formless Horror" in err for err in apply_result.errors))
        self.assertEqual(calls, [1])

        attacker._apply_battle_shock_outcome(
            passed=True,
            current_turn=1,
            was_battle_shocked=False,
            shadow_ctx=None,
            game=game,
            event_system=None,
        )

        apply_result2 = dispatch_decision(game, req, result)
        self.assertTrue(apply_result2.ok)

    def test_formless_horror_gate_fail_blocks_phase(self):
        army = Army("Chaos", detachment_type="Other")
        army.faction_id = "CD"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.turn = 1

        attacker = self._make_unit("Attacker", enemy_army, keywords=["INFANTRY"])
        target = self._make_unit("The Changeling", army, keywords=["LEGIONES DAEMONICA"])
        ability = Ability(
            "Formless Horror",
            "CD",
            "Each time an enemy unit wishes to select this model as the target of an attack, that unit must first take a Battle-shock test.",
            "Datasheet",
            "",
        )
        target.possible_abilities = [ability]

        army.units = [target]
        enemy_army.units = [attacker]
        game.rebuild_entity_registry()

        calls = []
        attacker.take_battle_shock_test = lambda turn=1: calls.append(int(turn))

        req = DecisionRequest.create(
            DECISION_SELECT_FIGHT_TARGETS,
            "Select target",
            player_id=player.id,
            options=[DecisionOption.create("Target", payload={"target_unit_id": target._id})],
            context={"unit_id": attacker._id},
        )
        result = DecisionResult(
            decision_id=req.decision_id,
            player_id=player.id,
            option_id=req.options[0].option_id,
            payload={"target_unit_ids": [target._id]},
        )
        dispatch_decision(game, req, result)
        self.assertEqual(calls, [1])

        attacker._apply_battle_shock_outcome(
            passed=False,
            current_turn=1,
            was_battle_shocked=False,
            shadow_ctx=None,
            game=game,
            event_system=None,
        )

        # New decision in same phase should be blocked without re-testing.
        req2 = DecisionRequest.create(
            DECISION_SELECT_FIGHT_TARGETS,
            "Select target",
            player_id=player.id,
            options=[DecisionOption.create("Target", payload={"target_unit_id": target._id})],
            context={"unit_id": attacker._id},
        )
        result2 = DecisionResult(
            decision_id=req2.decision_id,
            player_id=player.id,
            option_id=req2.options[0].option_id,
            payload={"target_unit_ids": [target._id]},
        )
        apply_result = dispatch_decision(game, req2, result2)
        self.assertFalse(apply_result.ok)
        self.assertTrue(any("Formless Horror" in err for err in apply_result.errors))
        self.assertEqual(calls, [1])

    def test_shadow_of_khorne_aura_reroll_source(self):
        army = Army("Chaos", detachment_type="Other")
        army.faction_id = "CD"

        target_unit = self._make_unit(
            "Bloodletters",
            army,
            keywords=["LEGIONES DAEMONICA", "KHORNE"],
        )
        target_model = self._make_model("Bloodletter", target_unit, x=0.0, y=0.0)
        target_unit.models = [target_model]

        ability = Ability("Shadow of Khorne (Aura)", "CD", "Aura rules", "Datasheet", "")
        skull_altar = self._make_unit("Skull Altar", army, keywords=["FORTIFICATION"])
        skull_model = self._make_model("Skull Altar", skull_altar, x=2.0, y=0.0)
        skull_altar.models = [skull_model]
        skull_altar.possible_abilities = [ability]

        dummy_map = DummyMap(friendly=[skull_altar, target_unit])
        sources = get_aura_battleshock_test_reroll_sources(target_unit, game_map=dummy_map)

        self.assertIn("Shadow of Khorne (Aura)", sources)


if __name__ == "__main__":
    unittest.main()
