import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


def _make_unit(name, army, *, abilities=None, keywords=None, faction_keywords=None):
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
    unit.round_state = type(
        "RoundState",
        (),
        {
            "num_lost_models_this_round": 0,
            "disembarked_from_transport_id": "",
            "advanced_this_round": False,
            "attempted_charge_this_round": False,
            "charged_this_round": False,
            "charge_target_ids": set(),
        },
    )()
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
    unit.get_attached_unit_members = lambda: [unit] + list(unit.attached_leaders or [])
    unit.get_models_for_collision = lambda: list(unit.models)
    unit.get_models_for_wound_allocation = lambda: list(unit.models)
    unit.is_in_reserves = lambda: False
    unit.has_any_keyword = lambda kw: any(
        str(kw or "").strip().upper() == str(k or "").strip().upper()
        for k in (unit.keywords + unit.faction_keywords)
    )
    unit.has_keyword = unit.has_any_keyword
    return unit


def _make_model(name, unit, *, wounds=4):
    model = Model(
        name=name,
        movement=12,
        toughness=3,
        save=3,
        wounds=int(wounds),
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(0.0, 0.0, 0.0, 0.0)
    return model


class TestAdeptaSororitasDivineDeliverance(unittest.TestCase):
    def _make_game(self):
        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield)
        sororitas_army = Army("Adepta Sororitas", detachment_type="Other")
        sororitas_army.faction_id = "AS"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"
        sororitas_player = Player("Sororitas", PlayerControl.REMOTE, army=sororitas_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game.add_player(sororitas_player)
        game.add_player(enemy_player)
        return game, sororitas_player

    def _resolve_yes(self, game, request, player):
        option_id = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=player.id)

    def test_divine_deliverance_queues_and_applies_melee_bonus(self):
        game, player = self._make_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        ability_desc = (
            "Once per battle, at the start of the Fight phase, this model can use this ability. "
            "If it does, until the end of the phase, add 3 to the Attacks characteristic of melee "
            "weapons equipped by this model and those weapons have the [DEVASTATING WOUNDS] ability."
        )
        ability = Ability("Divine Deliverance", "AS", ability_desc, "Datasheet", "")
        canoness = _make_unit(
            "Canoness with Jump Pack",
            player.army,
            abilities=[ability],
            keywords=["CHARACTER", "INFANTRY", "JUMP PACK", "ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
        )
        canoness_model = _make_model("Canoness with Jump Pack", canoness)
        canoness_model.abilities = {"Divine Deliverance": ability}
        canoness.models = [canoness_model]
        player.army.units = [canoness]

        game.rebuild_entity_registry()
        game._on_phase_start_optional_abilities(player=player, phase=game.phase)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self._resolve_yes(game, request, player)

        self.assertEqual(canoness_model.get_temporary_melee_attacks_bonus(), 3)
        self.assertTrue(canoness_model.has_temporary_devastating_wounds_melee())

        buff_key = str(request.context.get("buff_key") or "")
        self.assertTrue(canoness_model.has_used_once_per_battle(buff_key))

        game._on_phase_start_optional_abilities(player=player, phase=game.phase)
        pending_again = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending_again), 0)


if __name__ == "__main__":
    unittest.main()
