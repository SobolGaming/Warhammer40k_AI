from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


_ALPHA_WARRIOR_DESCRIPTION = (
    "Weapons equipped by models in this model's unit have the [SUSTAINED HITS 1] ability."
)
_AGGRESSIVE_LEADER_BEAST_DESCRIPTION = (
    "In your opponent's Shooting phase, each time an enemy unit has shot, if any models from this unit were destroyed as a "
    "result of those attacks, this unit can make a Surge move. To do so, roll one D6: models in this unit move a number of "
    "inches up to this result, but this unit must end that move as close as possible to the closest enemy unit (excluding "
    "AIRCRAFT). When doing so, those models can be moved within Engagement Range of that enemy unit. This unit cannot make "
    "a Surge move while it is Battle-shocked or within Engagement Range of one or more enemy units, and can only make one "
    "Surge move per phase."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None, model_count: int = 1):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model(s)", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "5",
                "Sv": "4",
                "W": "4",
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None, model_count: int = 1) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _aura_stub():
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


def _first_option(request, predicate):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if predicate(payload):
            return opt
    return None


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    enemy_army = Army("Enemy", "Detachment")
    enemy_army.faction_id = "EN"
    tyr_army = Army("Tyranids", "Detachment")
    tyr_army.faction_id = "TYR"
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    tyr_player = Player("TYR", control=PlayerControl.REMOTE, army=tyr_army)
    game.add_player(enemy_player)
    game.add_player(tyr_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, enemy_player, tyr_player


def test_alpha_warrior_grants_sustained_hits_to_this_models_unit():
    attacker = _make_unit(
        "Tyranid Prime with Lash Whip",
        abilities=[
            {
                "name": "Alpha Warrior",
                "description": _ALPHA_WARRIOR_DESCRIPTION,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
    )
    target = _make_unit("Enemy Unit")
    parent = SimpleNamespace(name="Bio-weapon", is_melee=lambda: False, is_ranged=lambda: True)
    profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={"range": "18", "A": "1", "BS_WS": "3+", "S": "5", "AP": "0", "D": "1", "description": ""},
        parent_wargear=parent,
    )

    attack_instance = {"_aura_attack_mods": _aura_stub()}
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            attack_instance,
            allow_rerolls=False,
            log_roll=False,
        )
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 1


def test_aggressive_leader_beast_triggers_after_model_destroyed_and_marks_use():
    game, enemy_player, tyr_player = _build_game()
    attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    prime = _make_unit(
        "Tyranid Prime with Lash Whip",
        model_count=2,
        abilities=[
            {
                "name": "Aggressive Leader-beast",
                "description": _AGGRESSIVE_LEADER_BEAST_DESCRIPTION,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
    )
    enemy_player.army.add_unit(attacker)
    tyr_player.army.add_unit(prime)
    attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    prime.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    prime.models[1].set_location(12.0, 0.0, 0.0, 0.0)
    game.map.units = [attacker, prime]
    game.rebuild_entity_registry()

    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[prime])
    prime.models[0].wounds = 0

    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker)

    confirm_req = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CONFIRM_YES_NO
        and str((req.context or {}).get("reactive_move_kind", "")) == "aggressive_leader_beast"
    )
    assert str(confirm_req.player_id) == str(tyr_player.id)
    yes_opt = _first_option(confirm_req, lambda payload: bool(payload.get("choice", False)))
    assert yes_opt is not None

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        resolve_decision_command(game, confirm_req, yes_opt.option_id, player_id=tyr_player.id)
    move_req = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_MOVE_UNIT
        and str((req.context or {}).get("movement_type", "")) == "aggressive_leader_beast"
    )
    move_ctx = dict(getattr(move_req, "context", {}) or {})
    assert int(move_ctx.get("max_distance", 0) or 0) == 4
    assert bool(move_ctx.get("reactive_move_allow_engagement_range", False))

    confirm_move = _first_option(move_req, lambda payload: str(payload.get("action", "")) == "confirm")
    assert confirm_move is not None
    model_positions = []
    for model in list(prime.models or []):
        x, y, z, facing = model.get_location()
        model_positions.append(
            {
                "model_id": get_entity_id(model),
                "position": [float(x), float(y), float(z)],
                "facing": float(facing),
            }
        )
    resolve_decision_command(
        game,
        move_req,
        confirm_move.option_id,
        player_id=tyr_player.id,
        result_payload={"model_positions": model_positions},
    )
    assert prime.aggressive_leader_beast_used_this_phase(game)


def test_aggressive_leader_beast_does_not_trigger_without_model_destroyed():
    game, enemy_player, tyr_player = _build_game()
    attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    prime = _make_unit(
        "Tyranid Prime with Lash Whip",
        model_count=2,
        abilities=[
            {
                "name": "Aggressive Leader-beast",
                "description": _AGGRESSIVE_LEADER_BEAST_DESCRIPTION,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
    )
    enemy_player.army.add_unit(attacker)
    tyr_player.army.add_unit(prime)
    attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    prime.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    prime.models[1].set_location(12.0, 0.0, 0.0, 0.0)
    game.map.units = [attacker, prime]

    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[prime])
    prime.models[0].wounds = max(1, int(prime.models[0].wounds or 0) - 1)
    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker)

    assert not any(
        req.decision_type == DECISION_CONFIRM_YES_NO
        and str((req.context or {}).get("reactive_move_kind", "")) == "aggressive_leader_beast"
        for req in list(game.decision_queue.list() or [])
    )
