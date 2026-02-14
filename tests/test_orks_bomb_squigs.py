import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_REQUEST_DICE_ROLL
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class _MapStub:
    def __init__(self, enemy_lookup: dict[str, list]):
        self._enemy_lookup = dict(enemy_lookup or {})

    def get_enemy_units(self, unit):
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        unit_id = str(get_entity_id(root) or "")
        return list(self._enemy_lookup.get(unit_id, []))

    def can_model_see_model(self, _source_model, _target_model):
        return True

    def get_distance_between_units(self, unit_a, unit_b) -> float:
        models_a = [m for m in list(getattr(unit_a, "models", []) or []) if getattr(m, "is_alive", False)]
        models_b = [m for m in list(getattr(unit_b, "models", []) or []) if getattr(m, "is_alive", False)]
        if not models_a or not models_b:
            return float("inf")
        best = float("inf")
        for ma in models_a:
            for mb in models_b:
                ax, ay, az, _ = ma.get_location()
                bx, by, bz, _ = mb.get_location()
                dist = math.dist((float(ax), float(ay), float(az)), (float(bx), float(by), float(bz)))
                if dist < best:
                    best = dist
        return float(best)


class TestOrksBombSquigs(unittest.TestCase):
    _BOMB_SQUIGS_SINGLE = (
        "Once per battle, for each bomb squig this unit has, after this unit ends a Normal move, you can use one Bomb Squig. "
        "If you do, select one enemy unit within 12\" and visible to this unit and roll one D6: on a 3+, that enemy unit suffers D3 mortal wounds. "
        "Designer's Note: Place a Bomb Squig token next to the unit, removing it when this unit uses this ability."
    )
    _BOMB_SQUIGS_PER_SQUIG = (
        "Once per battle, for each bomb squig this unit has, after this unit ends a Normal move, you can use one Bomb Squig. "
        "If you do, select one enemy unit within 12\" and visible to this unit and roll one D6: on a 3+, that enemy unit suffers D3 mortal wounds. "
        "Designer's Note: Place the relevant number of Bomb Squig tokens next to the unit, removing one each time this unit uses this ability."
    )
    _BOMB_SQUIGS_TWO_TOKENS = (
        "Once per battle, for each bomb squig this unit has, after this unit ends a Normal move, you can use one Bomb Squig. "
        "If you do, select one enemy unit within 12\" and visible to this unit and roll one D6: on a 3+, that enemy unit suffers D3 mortal wounds. "
        "Designer's Note: Place two Bomb Squig tokens next to the unit, removing one each time this unit uses this ability."
    )

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
        unit._attacking_unit_has_any_los_to_target_unit = lambda _target, _map=None: True
        return unit

    def _make_model(self, name, unit, *, x: float = 0.0, y: float = 0.0, z: float = 0.0):
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
        model.set_location(float(x), float(y), float(z), 0.0)
        return model

    def _setup_game(self):
        ork_army = Army("Orks", detachment_type="Other")
        ork_army.faction_id = "ORK"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        ork_player = Player("Ork", PlayerControl.REMOTE, army=ork_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[ork_player, enemy_player])
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0
        game.auto_resolve_dice_rolls = False
        return game, ork_army, enemy_army, ork_player

    def _resolve_quarry_choice(self, game, request, player, *, target=None, skip=False):
        option_id = None
        for opt in list(request.options or []):
            payload = dict(opt.payload or {})
            if skip and str(payload.get("action", "") or "") == "skip":
                option_id = opt.option_id
                break
            if target is not None and str(payload.get("target_unit_id", "") or "") == str(get_entity_id(target) or ""):
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=player.id)

    def _resolve_pending_roll(self, game, player, *, fixed_dice):
        pending = list(game.decision_queue.list() or [])
        roll_req = next((r for r in pending if r.decision_type == DECISION_REQUEST_DICE_ROLL), None)
        self.assertIsNotNone(roll_req)
        roll_id = (roll_req.context or {}).get("roll_id")
        self.assertIsNotNone(roll_id)
        state = game.roll_manager.get_roll(int(roll_id))
        state.spec["fixed_dice"] = list(fixed_dice)
        resolve_decision_command(game, roll_req, roll_req.options[0].option_id, player_id=player.id)

    def _build_units_for_bomb_squigs_test(self, ability_desc: str):
        game, ork_army, enemy_army, ork_player = self._setup_game()
        ability = Ability("Bomb Squigs", "ORK", ability_desc, "Datasheet", "")
        attacker = self._make_unit("Ork Unit", ork_army, abilities=[ability])
        enemy = self._make_unit("Enemy Unit", enemy_army)
        attacker.models = [self._make_model("Ork Model", attacker, x=0.0, y=0.0, z=0.0)]
        enemy.models = [self._make_model("Enemy Model", enemy, x=6.0, y=0.0, z=0.0)]
        ork_army.units = [attacker]
        enemy_army.units = [enemy]
        game.map = _MapStub({str(get_entity_id(attacker) or ""): [enemy]})
        game.rebuild_entity_registry()
        return game, attacker, enemy, ork_player

    def test_bomb_squigs_single_token_has_one_use(self):
        game, attacker, enemy, ork_player = self._build_units_for_bomb_squigs_test(self._BOMB_SQUIGS_SINGLE)
        applied = {}

        def _apply(target_unit, amount, game_map=None):
            applied["amount"] = applied.get("amount", 0) + int(amount or 0)
            applied["target"] = target_unit
            return 0

        attacker._apply_mortal_wounds_to_unit = _apply

        game._on_unit_move_ended_bomb_squigs(unit=attacker, action="move")
        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        req = pending[0]
        self.assertEqual(req.decision_type, DECISION_CHOOSE_QUARRY)
        self.assertEqual((req.context or {}).get("mortal_wounds_kind"), "bomb_squigs")
        self.assertEqual(int((req.context or {}).get("spec", {}).get("max_uses", 0) or 0), 1)

        self._resolve_quarry_choice(game, req, ork_player, target=enemy)
        with patch(
            "warhammer40k_ai.utility.dice.get_roll",
            side_effect=lambda die: 2 if str(die).upper() == "D3" else 1,
        ):
            self._resolve_pending_roll(game, ork_player, fixed_dice=[3])

        self.assertEqual(applied.get("amount"), 2)
        self.assertIs(applied.get("target"), enemy)
        self.assertEqual(int(attacker.special_rules.get("bomb_squig_uses", 0) or 0), 1)
        self.assertTrue(attacker.has_used_unit_once_per_battle("bomb_squigs"))

        game._on_unit_move_ended_bomb_squigs(unit=attacker, action="move")
        self.assertEqual(len(list(game.decision_queue.list() or [])), 0)

    def test_bomb_squigs_per_bomb_squig_uses_optional_wargear_count(self):
        game, attacker, enemy, ork_player = self._build_units_for_bomb_squigs_test(self._BOMB_SQUIGS_PER_SQUIG)
        second = self._make_model("Ork Model 2", attacker, x=0.5, y=0.0, z=0.0)
        attacker.models.append(second)
        attacker.models[0].optional_wargear = ["Bomb Squig"]
        attacker.models[1].optional_wargear = ["bomb squig"]
        game.rebuild_entity_registry()

        game._on_unit_move_ended_bomb_squigs(unit=attacker, action="move")
        req1 = list(game.decision_queue.list() or [])[0]
        self.assertEqual(int((req1.context or {}).get("spec", {}).get("max_uses", 0) or 0), 2)
        self._resolve_quarry_choice(game, req1, ork_player, target=enemy)
        with patch(
            "warhammer40k_ai.utility.dice.get_roll",
            side_effect=lambda die: 1 if str(die).upper() == "D3" else 1,
        ):
            self._resolve_pending_roll(game, ork_player, fixed_dice=[3])
        self.assertEqual(int(attacker.special_rules.get("bomb_squig_uses", 0) or 0), 1)
        self.assertFalse(attacker.has_used_unit_once_per_battle("bomb_squigs"))

        game._on_unit_move_ended_bomb_squigs(unit=attacker, action="move")
        req2 = list(game.decision_queue.list() or [])[0]
        self.assertEqual(int((req2.context or {}).get("spec", {}).get("remaining_uses", 0) or 0), 1)
        self._resolve_quarry_choice(game, req2, ork_player, target=enemy)
        with patch(
            "warhammer40k_ai.utility.dice.get_roll",
            side_effect=lambda die: 1 if str(die).upper() == "D3" else 1,
        ):
            self._resolve_pending_roll(game, ork_player, fixed_dice=[3])
        self.assertEqual(int(attacker.special_rules.get("bomb_squig_uses", 0) or 0), 2)
        self.assertTrue(attacker.has_used_unit_once_per_battle("bomb_squigs"))

        game._on_unit_move_ended_bomb_squigs(unit=attacker, action="move")
        self.assertEqual(len(list(game.decision_queue.list() or [])), 0)

    def test_bomb_squigs_two_token_variant_grants_two_uses_without_wargear_count(self):
        game, attacker, enemy, ork_player = self._build_units_for_bomb_squigs_test(self._BOMB_SQUIGS_TWO_TOKENS)

        game._on_unit_move_ended_bomb_squigs(unit=attacker, action="move")
        req1 = list(game.decision_queue.list() or [])[0]
        self.assertEqual(int((req1.context or {}).get("spec", {}).get("max_uses", 0) or 0), 2)
        self._resolve_quarry_choice(game, req1, ork_player, target=enemy)
        with patch(
            "warhammer40k_ai.utility.dice.get_roll",
            side_effect=lambda die: 1 if str(die).upper() == "D3" else 1,
        ):
            self._resolve_pending_roll(game, ork_player, fixed_dice=[3])
        self.assertEqual(int(attacker.special_rules.get("bomb_squig_uses", 0) or 0), 1)
        self.assertFalse(attacker.has_used_unit_once_per_battle("bomb_squigs"))

        game._on_unit_move_ended_bomb_squigs(unit=attacker, action="move")
        req2 = list(game.decision_queue.list() or [])[0]
        self._resolve_quarry_choice(game, req2, ork_player, target=enemy)
        with patch(
            "warhammer40k_ai.utility.dice.get_roll",
            side_effect=lambda die: 1 if str(die).upper() == "D3" else 1,
        ):
            self._resolve_pending_roll(game, ork_player, fixed_dice=[3])
        self.assertEqual(int(attacker.special_rules.get("bomb_squig_uses", 0) or 0), 2)
        self.assertTrue(attacker.has_used_unit_once_per_battle("bomb_squigs"))

    def test_bomb_squigs_skip_does_not_consume_use(self):
        game, attacker, _enemy, ork_player = self._build_units_for_bomb_squigs_test(self._BOMB_SQUIGS_SINGLE)
        game._on_unit_move_ended_bomb_squigs(unit=attacker, action="move")
        req = list(game.decision_queue.list() or [])[0]
        self._resolve_quarry_choice(game, req, ork_player, skip=True)
        self.assertEqual(int(attacker.special_rules.get("bomb_squig_uses", 0) or 0), 0)
        self.assertFalse(attacker.has_used_unit_once_per_battle("bomb_squigs"))

        game._on_unit_move_ended_bomb_squigs(unit=attacker, action="move")
        self.assertEqual(len(list(game.decision_queue.list() or [])), 1)
