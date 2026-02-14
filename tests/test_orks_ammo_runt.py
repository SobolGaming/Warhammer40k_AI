import unittest
import uuid
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


class _DummyWargear:
    def __init__(self, name: str, *, ranged: bool = True):
        self._id = str(uuid.uuid4())
        self.name = name
        self._ranged = bool(ranged)

    def is_ranged(self) -> bool:
        return bool(self._ranged)


class TestOrksAmmoRunt(unittest.TestCase):
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
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit._get_bodyguard_support_models = lambda: list(unit.models)
        return unit

    def _make_model(self, name, unit, *, wounds: int = 2):
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

    def _resolve_choice(self, game, request, player, *, use: bool):
        option_id = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)) == bool(use):
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=player.id)

    def _setup_game(self):
        ork_army = Army("Orks", detachment_type="Other")
        ork_army.faction_id = "ORK"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        ork_player = Player("Ork", PlayerControl.REMOTE, army=ork_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[ork_player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        return game, ork_army, enemy_army, ork_player

    def test_ammo_runt_once_per_battle_applies_lethal_hits(self):
        game, ork_army, enemy_army, ork_player = self._setup_game()
        ability = Ability(
            "Ammo Runt",
            "ORK",
            (
                "Once per battle, when this unit is selected to shoot, it can use this ability. "
                "If it does, until the end of the phase, ranged weapons equipped by models in this unit have the [LETHAL HITS] ability. "
                "Designer's Note: Place an Ammo Runt token next to the unit, removing it after this ability has been used."
            ),
            "Datasheet",
            "",
        )
        attacker = self._make_unit("Flash Gitz", ork_army, abilities=[ability])
        model = self._make_model("Flash Git", attacker)
        model.wargear = [_DummyWargear("Snazzgun", ranged=True)]
        attacker.models = [model]
        ork_army.units = [attacker]

        target = self._make_unit("Target", enemy_army)
        target.models = [self._make_model("Target Model", target)]
        enemy_army.units = [target]
        game.rebuild_entity_registry()

        game._on_shooting_targets_selected_ammo_runt(attacking_unit=attacker, target_units=[target])
        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        self.assertEqual((request.context or {}).get("ability"), "ammo_runt")
        self.assertEqual(int((request.context or {}).get("max_uses", 0) or 0), 1)
        self.assertEqual(int((request.context or {}).get("remaining_uses", 0) or 0), 1)

        self._resolve_choice(game, request, ork_player, use=True)

        keywords = {k.get("keyword") for k in model.get_temporary_weapon_keyword_bonuses("Snazzgun")}
        self.assertIn("LETHAL HITS", keywords)
        self.assertEqual(int(attacker.special_rules.get("ammo_runt_uses", 0) or 0), 1)
        self.assertTrue(attacker.has_used_unit_once_per_battle("ammo_runt"))

        game._on_shooting_targets_selected_ammo_runt(attacking_unit=attacker, target_units=[target])
        self.assertEqual(len(game.decision_queue.list()), 0)

    def test_ammo_runt_per_runt_allows_multiple_uses(self):
        game, ork_army, enemy_army, ork_player = self._setup_game()
        ability = Ability(
            "Ammo Runt",
            "ORK",
            (
                "Once per battle for each ammo runt this unit has, when this unit is selected to shoot, it can use this ability. "
                "If it does, until the end of the phase, ranged weapons equipped by models in this unit have the [LETHAL HITS] ability. "
                "Designer's Note: Place the relevant number of Ammo Runt tokens next to the unit, removing one each time the unit uses this ability."
            ),
            "Datasheet",
            "",
        )
        attacker = self._make_unit("Nobz", ork_army, abilities=[ability])
        first = self._make_model("Nob", attacker)
        first.wargear = [_DummyWargear("Slugga", ranged=True)]
        first.optional_wargear = ["Ammo Runt"]
        second = self._make_model("Nob 2", attacker)
        second.wargear = [_DummyWargear("Slugga", ranged=True)]
        second.optional_wargear = ["ammo runt"]
        attacker.models = [first, second]
        ork_army.units = [attacker]

        target = self._make_unit("Target", enemy_army)
        target.models = [self._make_model("Target Model", target)]
        enemy_army.units = [target]
        game.rebuild_entity_registry()

        game._on_shooting_targets_selected_ammo_runt(attacking_unit=attacker, target_units=[target])
        first_req = game.decision_queue.list()[0]
        self.assertEqual(int((first_req.context or {}).get("max_uses", 0) or 0), 2)
        self.assertEqual(int((first_req.context or {}).get("remaining_uses", 0) or 0), 2)
        self._resolve_choice(game, first_req, ork_player, use=True)
        self.assertEqual(int(attacker.special_rules.get("ammo_runt_uses", 0) or 0), 1)
        self.assertFalse(attacker.has_used_unit_once_per_battle("ammo_runt"))

        first.on_phase_end(BattleRoundPhases.SHOOTING_PHASE)
        second.on_phase_end(BattleRoundPhases.SHOOTING_PHASE)

        game._on_shooting_targets_selected_ammo_runt(attacking_unit=attacker, target_units=[target])
        second_req = game.decision_queue.list()[0]
        self.assertEqual(int((second_req.context or {}).get("remaining_uses", 0) or 0), 1)
        self._resolve_choice(game, second_req, ork_player, use=True)
        self.assertEqual(int(attacker.special_rules.get("ammo_runt_uses", 0) or 0), 2)
        self.assertTrue(attacker.has_used_unit_once_per_battle("ammo_runt"))

        game._on_shooting_targets_selected_ammo_runt(attacking_unit=attacker, target_units=[target])
        self.assertEqual(len(game.decision_queue.list()), 0)

    def test_ammo_runt_skip_does_not_consume_use(self):
        game, ork_army, enemy_army, ork_player = self._setup_game()
        ability = Ability(
            "Ammo Runt",
            "ORK",
            (
                "Once per battle, when this unit is selected to shoot, it can use this ability. "
                "If it does, until the end of the phase, ranged weapons equipped by models in this unit have the [LETHAL HITS] ability."
            ),
            "Datasheet",
            "",
        )
        attacker = self._make_unit("Flash Gitz", ork_army, abilities=[ability])
        model = self._make_model("Flash Git", attacker)
        model.wargear = [_DummyWargear("Snazzgun", ranged=True)]
        attacker.models = [model]
        ork_army.units = [attacker]

        target = self._make_unit("Target", enemy_army)
        target.models = [self._make_model("Target Model", target)]
        enemy_army.units = [target]
        game.rebuild_entity_registry()

        game._on_shooting_targets_selected_ammo_runt(attacking_unit=attacker, target_units=[target])
        request = game.decision_queue.list()[0]
        self._resolve_choice(game, request, ork_player, use=False)

        self.assertEqual(int(attacker.special_rules.get("ammo_runt_uses", 0) or 0), 0)
        self.assertFalse(attacker.has_used_unit_once_per_battle("ammo_runt"))
        self.assertEqual(model.get_temporary_weapon_keyword_bonuses("Snazzgun"), [])
