from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(self, name: str, *, datasheet_id: str, keywords=None, faction_keywords=None) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ENEMY"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _actual_unit(name: str, *, datasheet_id: str, quantity: int | None = None) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"), quantity=quantity)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _enemy_unit(name: str) -> Unit:
    unit = Unit(_MockDatasheet(name, datasheet_id=f"enemy-{name.lower().replace(' ', '-')}"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, defender_control: PlayerControl = PlayerControl.REMOTE):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_player = Player("Enemy", control=PlayerControl.LOCAL, army=enemy_army)
    sm_player = Player("Space Marines", control=defender_control, army=sm_army)
    game.add_player(enemy_player)
    game.add_player(sm_player)
    game.current_player_index = 0
    game.turn = 1
    return game, enemy_player, sm_player


def _first_option(request, predicate):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if predicate(payload):
            return option
    return None


def test_victrix_honour_guard_glory_of_ultramar_queues_reactive_surge_move() -> None:
    game, enemy_player, sm_player = _build_game(defender_control=PlayerControl.REMOTE)
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    attacker = _enemy_unit("Enemy Shooters")
    victrix = _actual_unit("Victrix Honour Guard", datasheet_id="000004185", quantity=4)

    enemy_player.army.add_unit(attacker)
    sm_player.army.add_unit(victrix)
    attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    for index, model in enumerate(victrix.models):
        model.set_location(10.0 + float(index), 0.0, 0.0, 0.0)
    game.map.units = [attacker, victrix]
    game.rebuild_entity_registry()

    rule = victrix.get_horde_move_rule(game=game)
    assert rule is not None
    assert str(rule.get("source", "")) == "Glory of Ultramar"
    assert bool(rule.get("allow_engagement_range", False)) is True
    assert bool(rule.get("requires_not_engaged", False)) is True
    assert bool(rule.get("use_once_per_phase", False)) is True

    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[victrix])
    victrix.models[-1].wounds = 0
    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker)

    confirm_req = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CONFIRM_YES_NO
        and str((req.context or {}).get("reactive_move_kind", "")) == "horde_move"
    )
    ctx = dict(getattr(confirm_req, "context", {}) or {})
    assert str(ctx.get("reactive_move_source", "")) == "Glory of Ultramar"
    assert bool(ctx.get("reactive_move_allow_engagement_range", False)) is True

    yes_opt = _first_option(confirm_req, lambda payload: bool(payload.get("choice", False)))
    assert yes_opt is not None
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        resolve_decision_command(game, confirm_req, yes_opt.option_id, player_id=sm_player.id)

    move_req = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_MOVE_UNIT
        and str((req.context or {}).get("movement_type", "")) == "horde_move"
    )
    move_ctx = dict(getattr(move_req, "context", {}) or {})
    assert int(move_ctx.get("max_distance", 0) or 0) == 4
    assert bool(move_ctx.get("reactive_move_allow_engagement_range", False)) is True

    confirm_move = _first_option(move_req, lambda payload: str(payload.get("action", "")) == "confirm")
    assert confirm_move is not None
    model_positions = []
    for model in list(victrix.models or []):
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
        player_id=sm_player.id,
        result_payload={"model_positions": model_positions},
    )
    assert victrix.horde_move_used_this_phase(game) is True


def test_victrix_honour_guard_banner_of_macragge_queues_and_applies_unit_melee_buff() -> None:
    game, _enemy_player, sm_player = _build_game(defender_control=PlayerControl.REMOTE)
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 1

    victrix = _actual_unit("Victrix Honour Guard", datasheet_id="000004185", quantity=4)
    for index, model in enumerate(victrix.models):
        model.wargear = [
            SimpleNamespace(
                id=f"melee-{index}",
                name=f"Melee weapon {index}",
                is_melee=lambda: True,
                is_ranged=lambda: False,
            ),
            SimpleNamespace(
                id=f"ranged-{index}",
                name=f"Ranged weapon {index}",
                is_melee=lambda: False,
                is_ranged=lambda: True,
            ),
        ]
    sm_player.army.add_unit(victrix)
    game.map.units = [victrix]
    game.rebuild_entity_registry()

    ancient = next(model for model in victrix.models if str(model.name) == "Chapter Ancient")
    specs = victrix.model_start_fight_phase_unit_melee_attacks_strength_boost_specs(ancient)
    assert specs == [
        {
            "source": "Banner of Macragge",
            "key": "fight_phase_unit_melee_attacks_strength_boost:banner of macragge",
            "attacks_bonus": 1,
            "strength_bonus": 1,
        }
    ]

    game._on_phase_start_optional_abilities(player=sm_player, phase=BattleRoundPhases.FIGHT_PHASE)
    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CONFIRM_YES_NO
        and str((req.context or {}).get("ability", "")) == "fight_phase_unit_melee_attacks_strength_boost"
    )
    yes_opt = _first_option(request, lambda payload: bool(payload.get("choice", False)))
    assert yes_opt is not None
    resolve_decision_command(game, request, yes_opt.option_id, player_id=sm_player.id)

    for index, model in enumerate(victrix.models):
        attacks_bonus, _attack_reasons = model.get_temporary_weapon_attacks_bonus(f"Melee weapon {index}")
        strength_bonus, _strength_reasons = model.get_temporary_weapon_strength_bonus(f"Melee weapon {index}")
        assert int(attacks_bonus or 0) == 1
        assert int(strength_bonus or 0) == 1
        ranged_attacks_bonus, _ = model.get_temporary_weapon_attacks_bonus(f"Ranged weapon {index}")
        ranged_strength_bonus, _ = model.get_temporary_weapon_strength_bonus(f"Ranged weapon {index}")
        assert int(ranged_attacks_bonus or 0) == 0
        assert int(ranged_strength_bonus or 0) == 0

    assert ancient.has_used_once_per_battle("fight_phase_unit_melee_attacks_strength_boost:banner of macragge") is True
