import unittest
import uuid
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
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


class TestTauNovaCharge(unittest.TestCase):
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

    def _make_model(self, name, unit):
        model = Model(
            name=name,
            movement=10,
            toughness=9,
            save=2,
            wounds=14,
            leadership=7,
            objective_control=4,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def _setup_game(self):
        tau_army = Army("Tau", detachment_type="Other")
        tau_army.faction_id = "TAU"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        tau_player = Player("Tau", PlayerControl.REMOTE, army=tau_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[tau_player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        return game, tau_army, enemy_army, tau_player

    def test_nova_charge_selects_weapon_and_grants_devastating_wounds(self):
        game, tau_army, enemy_army, tau_player = self._setup_game()
        ability = Ability(
            "Nova Charge",
            "TAU",
            (
                "Once per battle, when this unit is selected to shoot in your Shooting phase, select one ranged weapon "
                "equipped by this model. Until the end of the phase, that weapon has the [DEVASTATING WOUNDS] ability."
            ),
            "Datasheet",
            "",
        )

        attacker = self._make_unit("Riptide Battlesuit", tau_army, abilities=[ability])
        model = self._make_model("Riptide", attacker)
        model.abilities = {"Nova Charge": ability}
        model.wargear = [
            _DummyWargear("Heavy Burst Cannon", ranged=True),
            _DummyWargear("Twin Plasma Rifle", ranged=True),
            _DummyWargear("Riptide Fists", ranged=False),
        ]
        attacker.models = [model]
        tau_army.units = [attacker]

        target = self._make_unit("Target", enemy_army)
        target_model = self._make_model("Target Model", target)
        target.models = [target_model]
        enemy_army.units = [target]
        game.rebuild_entity_registry()

        game._on_shooting_targets_selected_nova_charge(attacking_unit=attacker, target_units=[target])

        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        self.assertEqual((request.context or {}).get("ability"), "nova_charge")
        option_payloads = [dict(opt.payload or {}) for opt in list(request.options or [])]
        self.assertTrue(any(str(p.get("action", "")).lower() == "skip" for p in option_payloads))
        weapon_options = sorted(
            [str(p.get("weapon_name", "")).strip() for p in option_payloads if str(p.get("weapon_name", "")).strip()]
        )
        self.assertEqual(weapon_options, ["Heavy Burst Cannon", "Twin Plasma Rifle"])

        option_id = None
        for opt in list(request.options or []):
            if str((opt.payload or {}).get("weapon_name", "")).strip() == "Heavy Burst Cannon":
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=tau_player.id)

        keywords = {k.get("keyword") for k in model.get_temporary_weapon_keyword_bonuses("Heavy Burst Cannon")}
        self.assertIn("DEVASTATING WOUNDS", keywords)
        ability_key = str((request.context or {}).get("ability_key", "") or "").strip().lower()
        self.assertTrue(ability_key)
        self.assertTrue(model.has_used_once_per_battle(ability_key))

        game._on_shooting_targets_selected_nova_charge(attacking_unit=attacker, target_units=[target])
        self.assertEqual(len(list(game.decision_queue.list() or [])), 0)
