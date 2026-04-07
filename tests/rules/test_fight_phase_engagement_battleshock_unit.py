import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.engine.game import Game, Battlefield, BattleRoundPhases, BattlefieldSize
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType


ABILITY_TEXT = (
    "At the start of the Fight phase, each enemy unit within Engagement Range of one or more units from your army with "
    "this ability must take a Battle-shock test, subtracting 1 from the result if that enemy unit is Below Half-strength."
)


class TestFightPhaseEngagementBattleshockUnit(unittest.TestCase):
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
        unit.round_state = SimpleNamespace()
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit.transport_passengers = []
        unit._ability_cache = {}
        return unit

    def _make_model(self, name, unit, x, y):
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
        model.set_location(x, y, 0.0, 0.0)
        return model

    def test_unit_engagement_battleshock_applies(self):
        army_a = Army.with_detachment("Army A", detachment_type="Other")
        army_a.faction_id = "A"
        army_b = Army.with_detachment("Army B", detachment_type="Other")
        army_b.faction_id = "B"

        player_a = Player("Player A", PlayerControl.LOCAL, army=army_a)
        player_b = Player("Player B", PlayerControl.LOCAL, army=army_b)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player_a, player_b])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.turn = 2

        ability = Ability("Terrifying Presence", "A", ABILITY_TEXT, "")
        source = self._make_unit("Source", army_a, abilities=[ability])
        enemy = self._make_unit("Enemy", army_b)

        source.models = [self._make_model("Source", source, 0.0, 0.0)]
        enemy.models = [self._make_model("Enemy", enemy, 0.0, 0.0)]

        army_a.units = [source]
        army_b.units = [enemy]
        game.map.units = [source, enemy]

        enemy.battleshock_turns = []
        enemy.last_battleshock_modifier = None
        enemy.is_below_half_strength = lambda: True

        def _take_battleshock(turn):
            enemy.battleshock_turns.append(int(turn))
            enemy.last_battleshock_modifier = enemy.special_rules.get("battle_shock_test_modifier")

        enemy.take_battle_shock_test = _take_battleshock

        game._on_phase_start_engagement_battleshock(player=player_a, phase=game.phase)

        self.assertEqual(enemy.battleshock_turns, [2])
        self.assertEqual(enemy.last_battleshock_modifier, -1)
