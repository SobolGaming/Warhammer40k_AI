from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules, validate_final_position
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        model_count: int = 1,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        wounds: int = 2,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model(s)", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _actual_unit(name: str, *, datasheet_id: str = "000004133") -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_enemy_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    wounds: int = 2,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    game.add_player(enemy_player)
    game.add_player(sm_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, enemy_player, sm_player, enemy_army, sm_army


def _first_option(request, predicate):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if predicate(payload):
            return option
    return None


def test_wulfen_dreadnought_violent_fury_grants_twin_linked_to_each_melee_weapon() -> None:
    dreadnought = _actual_unit("Wulfen Dreadnought")
    target = _make_enemy_unit("Enemy Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    model = dreadnought.models[0]

    greataxe_bonuses = dreadnought.get_model_weapon_keyword_bonuses(
        attack_type="melee",
        model=model,
        weapon_name="Fenrisian greataxe",
        target=target,
    )
    claw_bonuses = dreadnought.get_model_weapon_keyword_bonuses(
        attack_type="melee",
        model=model,
        weapon_name="Great wolf claw",
        target=target,
    )

    assert bool(greataxe_bonuses.get("twin_linked", False))
    assert bool(claw_bonuses.get("twin_linked", False))
    assert any("violent fury" in str(source).lower() for source in list(greataxe_bonuses.get("sources", []) or []))
    assert any("violent fury" in str(source).lower() for source in list(claw_bonuses.get("sources", []) or []))


def test_wulfen_dreadnought_bestial_rage_triggers_on_wound_loss_even_while_battle_shocked() -> None:
    game, enemy_player, sm_player, enemy_army, sm_army = _build_game()
    attacker = _make_enemy_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=2)
    dreadnought = _actual_unit("Wulfen Dreadnought")

    enemy_army.add_unit(attacker)
    sm_army.add_unit(dreadnought)
    attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    dreadnought.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    dreadnought.apply_status_effect(BattleShockEffect(current_turn=1))
    game.map.units = [attacker, dreadnought]
    game.rebuild_entity_registry()

    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[dreadnought])
    dreadnought.models[0].wounds = max(1, int(dreadnought.models[0].wounds or 0) - 1)
    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker)

    confirm_req = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CONFIRM_YES_NO
        and str((req.context or {}).get("reactive_move_kind", "")) == "bestial_rage"
    )
    assert str(confirm_req.player_id) == str(sm_player.id)

    yes_option = _first_option(confirm_req, lambda payload: bool(payload.get("choice", False)))
    assert yes_option is not None

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        resolve_decision_command(game, confirm_req, yes_option.option_id, player_id=sm_player.id)

    move_req = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_MOVE_UNIT
        and str((req.context or {}).get("movement_type", "")) == "bestial_rage"
    )
    move_ctx = dict(getattr(move_req, "context", {}) or {})
    assert int(move_ctx.get("max_distance", 0) or 0) == 6
    assert bool(move_ctx.get("reactive_move_allow_engagement_range", False))

    confirm_move = _first_option(move_req, lambda payload: str(payload.get("action", "")) == "confirm")
    assert confirm_move is not None
    resolve_decision_command(
        game,
        move_req,
        confirm_move.option_id,
        player_id=sm_player.id,
        result_payload={
            "model_positions": [
                {
                    "model_id": get_entity_id(dreadnought.models[0]),
                    "position": [4.0, 0.0, 0.0],
                    "facing": 0.0,
                }
            ]
        },
    )
    assert dreadnought.bestial_rage_used_this_phase(game)


def test_wulfen_dreadnought_bestial_rage_validation_uses_closest_non_aircraft_enemy() -> None:
    game_map = Map(100, 100)
    moving_army = Army.with_detachment("Space Marines", detachment_type="Other")
    moving_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    mover = _actual_unit("Wulfen Dreadnought")
    aircraft = _make_enemy_unit("Enemy Aircraft", keywords=["AIRCRAFT"], faction_keywords=["ENEMY"], wounds=2)
    infantry = _make_enemy_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=2)
    moving_army.add_unit(mover)
    enemy_army.add_unit(aircraft)
    enemy_army.add_unit(infantry)
    mover.faction = "SM"
    aircraft.faction = "EN"
    infantry.faction = "EN"

    mover.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    aircraft.models[0].set_location(6.0, 0.0, 0.0, 0.0)
    infantry.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    game_map.units = [mover, aircraft, infantry]

    rules = get_validation_rules(MovementType.BESTIAL_RAGE, moving_unit=mover)
    assert "AIRCRAFT" in set(rules.get("closest_enemy_unit_exclude_keywords", []) or [])
    rules["blood_surge_max_distance"] = 2.0

    ok = validate_final_position(mover.models[0], (2.0, 0.0, 0.0), rules, game_map)
    bad = validate_final_position(mover.models[0], (1.0, 0.0, 0.0), rules, game_map)
    assert bool(ok.get("valid", False))
    assert not bool(bad.get("valid", True))
