from __future__ import annotations

import types
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_MOVE_UNIT,
    DECISION_REQUEST_DICE_ROLL,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


RED_SKULL_KOMMANDOS_TEXT = "While this model is leading a unit, models in that unit have the Benefit of Cover."
KUNNIN_INFILTRATOR_TEXT = (
    "Once per battle, in your Movement phase, instead of making a Normal move with this model's unit, you can remove it "
    "from the battlefield and set it up again anywhere on the battlefield that is more than 9\" horizontally away from "
    "all enemy models."
)
BURNA_BOMB_TEXT = (
    "Each time this model ends a Normal move, you can select one enemy unit it moved over during that move. Until the "
    "end of the turn, models in that unit cannot have the Benefit of Cover. In addition, roll one D6 for each model in "
    "that unit: for each 6, that unit suffers 1 mortal wound."
)
PYROMANIAKS_TEXT = (
    "Each time a model in this unit makes a ranged attack with a burna that targets an enemy unit within 6\", re-roll "
    "a Wound roll of 1. If the target of that attack is also within range of an objective marker, you can re-roll the "
    "Wound roll instead."
)
PISTON_DRIVEN_BRUTALITY_TEXT = (
    "Each time this model ends a Charge move, select one enemy unit within Engagement Range of this model and roll one "
    "D6: on a 2-5, that enemy unit suffers D3 mortal wounds; on a 6, that enemy unit suffers D3+3 mortal wounds."
)
GUN_CRAZY_SHOW_OFFS_TEXT = (
    "Each time a model in this unit targets the closest eligible target with its snazzgun, until the end of the phase, "
    "that weapon has an Attacks characteristic of 4."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Orks",
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: str = "4",
        save: str = "4",
        inv_sv: str = "7",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": str(save),
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": str(inv_sv),
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


def _make_unit(
    name: str,
    *,
    ability_name: str | None = None,
    ability_desc: str | None = None,
    faction_name: str = "Orks",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: str = "4",
    save: str = "4",
    inv_sv: str = "7",
) -> Unit:
    abilities = []
    if ability_desc:
        abilities.append(
            {
                "name": ability_name or name,
                "description": ability_desc,
                "type": "Datasheet",
                "parameter": "",
            }
        )
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            save=save,
            inv_sv=inv_sv,
        )
    )


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    leader.can_be_attached_to = [bodyguard.name]


def _make_profile(*, weapon_name: str, range_val: str, is_ranged: bool, attacks: str = "1", damage: str = "1") -> WargearProfile:
    parent = SimpleNamespace(
        name=weapon_name,
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": str(range_val),
        "A": str(attacks),
        "BS_WS": "4+",
        "S": "4",
        "AP": "0",
        "D": str(damage),
        "description": "",
    }
    return WargearProfile("default", wargear_data=data, parent_wargear=parent)


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


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army("Orks", "Other")
    ork_army.faction_id = "ORK"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ork_player = Player("Orks", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)
    return game, ork_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float, *, spacing: float = 2.1) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(spacing) * idx), float(y), 0.0, 0.0)
    units = list(getattr(game.map, "units", []) or [])
    if unit not in units:
        units.append(unit)
    game.map.units = units


def test_red_skull_kommandos_grants_cover_only_against_ranged_attacks():
    leader = _make_unit(
        "Boss Snikrot",
        ability_name="Red Skull Kommandos",
        ability_desc=RED_SKULL_KOMMANDOS_TEXT,
        keywords=["ORKS", "INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
    )
    bodyguard = _make_unit(
        "Kommandos",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=3,
        save="4",
    )
    _attach_leader(bodyguard, leader)
    bodyguard._refresh_bearer_unit_common_modifiers()

    ranged_profile = _make_profile(weapon_name="Test Gun", range_val="24", is_ranged=True)
    ranged_save = ranged_profile._save_with_tracking(
        bodyguard.models[0],
        {"mortal_wound": False},
        ap=0,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(ranged_save.get("saved", False)) is True

    melee_profile = _make_profile(weapon_name="Test Choppa", range_val="2", is_ranged=False)
    melee_save = melee_profile._save_with_tracking(
        bodyguard.models[0],
        {"mortal_wound": False},
        ap=0,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(melee_save.get("saved", False)) is False


def test_kunnin_infiltrator_queues_multimodel_redeploy_and_marks_once_per_battle():
    game, ork_army, enemy_army = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0

    unit = _make_unit(
        "Boss Snikrot",
        ability_name="Kunnin' Infiltrator",
        ability_desc=KUNNIN_INFILTRATOR_TEXT,
        keywords=["ORKS", "INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
        model_count=3,
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", faction_keywords=["EN"], model_count=1)
    ork_army.add_unit(unit)
    enemy_army.add_unit(enemy)

    _deploy_unit(game, unit, 0.0, 0.0)
    _deploy_unit(game, enemy, 40.0, 0.0)
    game.map.is_within_boundary = lambda *_args, **_kwargs: True
    game.map.check_collision_with_obstacles = lambda *_args, **_kwargs: False
    game.rebuild_entity_registry()

    specs = unit.unit_movement_phase_normal_move_redeploy_specs()
    assert len(specs) == 1
    spec = specs[0]
    assert int(spec.get("min_enemy_distance_horiz", 0) or 0) == 9

    game._queue_movement_phase_normal_move_redeploy(player=ork_army.player, unit=unit)

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CONFIRM_YES_NO
    assert str((request.context or {}).get("ability", "")) == "normal_move_redeploy"

    yes_option = next(opt for opt in list(request.options or []) if bool((opt.payload or {}).get("choice", False)))
    resolve_decision_command(game, request, yes_option.option_id, player_id=ork_army.player.id)

    pending_after_yes = list(game.decision_queue.list() or [])
    assert len(pending_after_yes) == 1
    move_request = pending_after_yes[0]
    assert move_request.decision_type == DECISION_MOVE_UNIT
    move_ctx = dict(getattr(move_request, "context", {}) or {})
    assert move_ctx.get("placement_kind") == "normal_move_redeploy_9h"
    assert move_ctx.get("movement_type") == "move"
    assert len(list(move_ctx.get("allowed_model_ids") or [])) == 3

    model_positions = []
    for idx, model in enumerate(list(unit.models or [])):
        model_positions.append(
            {
                "model_id": get_entity_id(model),
                "position": [15.0 + (2.1 * idx), 0.0, 0.0],
                "facing": 0.0,
            }
        )
    result = resolve_decision_command(
        game,
        move_request,
        move_request.options[0].option_id,
        player_id=ork_army.player.id,
        result_payload={"model_positions": model_positions},
    )
    assert bool(getattr(result, "ok", False))
    assert bool(getattr(unit.round_state, "moved_this_round", False))
    assert not bool(getattr(unit.round_state, "advanced_this_round", False))
    assert bool(unit.has_used_unit_once_per_battle(str(spec.get("ability_key", "") or "")))


def test_burna_bomb_uses_target_model_count_and_applies_no_cover():
    game, ork_army, enemy_army = _build_game()
    game.auto_resolve_dice_rolls = False
    bomber = _make_unit(
        "Burna-bommer",
        ability_name="Burna Bomb",
        ability_desc=BURNA_BOMB_TEXT,
        keywords=["ORKS", "VEHICLE", "FLY"],
        faction_keywords=["ORKS"],
    )
    target = _make_unit(
        "Enemy Squad",
        faction_name="Enemy",
        faction_keywords=["EN"],
        model_count=3,
    )
    ork_army.add_unit(bomber)
    enemy_army.add_unit(target)

    _deploy_unit(game, bomber, 10.0, 0.0)
    _deploy_unit(game, target, 5.0, 0.0)
    bomber.models[0].last_move_path = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
    game.rebuild_entity_registry()

    specs = bomber.model_move_over_mortal_wounds_specs(model=bomber.models[0])
    assert len(specs) == 1
    spec = specs[0]
    assert bool(spec.get("dice_per_target_model", False)) is True
    assert bool(spec.get("apply_no_cover_until_end_of_turn", False)) is True

    game._on_unit_move_ended_move_over_mortal_wounds(unit=bomber, action="move")

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    quarry_request = pending[0]
    assert quarry_request.decision_type == DECISION_CHOOSE_QUARRY
    assert str((quarry_request.context or {}).get("mortal_wounds_kind", "")) == "move_over"

    target_id = str(get_entity_id(target) or "")
    option = next(opt for opt in list(quarry_request.options or []) if str((opt.payload or {}).get("target_unit_id", "")) == target_id)
    resolve_decision_command(game, quarry_request, option.option_id, player_id=ork_army.player.id)

    roll_request = next(req for req in list(game.decision_queue.list() or []) if req.decision_type == DECISION_REQUEST_DICE_ROLL)
    roll_id = int((roll_request.context or {}).get("roll_id"))
    roll_state = game.roll_manager.get_roll(roll_id)
    assert int(roll_state.spec.get("dice_count", 0) or 0) == 3
    assert bool(target.special_rules.get("move_over_no_cover_active", False)) is True
    assert "Burna Bomb" in str(target.special_rules.get("move_over_no_cover_source", "") or "")


def test_pyromaniaks_rerolls_wound_rolls_of_one_within_six_inches():
    game, ork_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Burna Boyz",
        ability_name="Pyromaniaks",
        ability_desc=PYROMANIAKS_TEXT,
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
    )
    target = _make_unit("Enemy Unit", faction_name="Enemy", faction_keywords=["EN"])
    ork_army.add_unit(attacker)
    enemy_army.add_unit(target)
    _deploy_unit(game, attacker, 0.0, 0.0)
    _deploy_unit(game, target, 5.0, 0.0)
    attacker._target_within_objective_range = lambda _target, _game_map=None: False

    called = {}

    def _provider(**kwargs):
        called["reason"] = kwargs.get("reason")
        return True

    game.map.roll_reroll_provider = _provider

    profile = _make_profile(weapon_name="burna", range_val="12", is_ranged=True)
    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[1, 6]):
        result = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )

    assert int(result.get("roll", 0) or 0) == 6
    assert int(result.get("reroll_of_one", 0) or 0) == 1
    assert any("Pyromaniaks" in str(reason or "") for reason in list(result.get("reroll_value_reasons", []) or []))


def test_pyromaniaks_applies_full_wound_reroll_on_objective_targets_within_six_inches():
    game, ork_army, enemy_army = _build_game()
    ork_army.player.control = PlayerControl.LOCAL
    attacker = _make_unit(
        "Burna Boyz",
        ability_name="Pyromaniaks",
        ability_desc=PYROMANIAKS_TEXT,
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
    )
    target = _make_unit("Enemy Unit", faction_name="Enemy", faction_keywords=["EN"])
    ork_army.add_unit(attacker)
    enemy_army.add_unit(target)
    _deploy_unit(game, attacker, 0.0, 0.0)
    _deploy_unit(game, target, 5.0, 0.0)
    attacker._target_within_objective_range = lambda _target, _game_map=None: True

    called = {}

    def _provider(**kwargs):
        called["reason"] = kwargs.get("reason")
        return True

    game.map.roll_reroll_provider = _provider

    profile = _make_profile(weapon_name="burna", range_val="12", is_ranged=True)
    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2, 6]):
        result = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )

    assert int(result.get("roll", 0) or 0) == 6
    assert "Pyromaniaks" in str(called.get("reason", "") or "")


def test_piston_driven_brutality_parses_and_applies_charge_end_mortals():
    game, ork_army, enemy_army = _build_game()
    dread = _make_unit(
        "Deff Dread",
        ability_name="Piston-driven Brutality",
        ability_desc=PISTON_DRIVEN_BRUTALITY_TEXT,
        keywords=["ORKS", "VEHICLE", "WALKER"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", faction_keywords=["EN"])
    ork_army.add_unit(dread)
    enemy_army.add_unit(enemy)

    dread._refresh_charge_end_mortal_wounds_flags()
    specs = list(getattr(dread, "special_rules", {}).get("charge_end_mortal_wounds", []) or [])
    spec = next((row for row in specs if str(row.get("kind", "") or "") == "table_d6_2_5_6"), None)
    assert spec is not None

    applied = {"amount": 0}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] += int(amount or 0)
        return 0

    dread._apply_mortal_wounds_to_unit = types.MethodType(_apply, dread)

    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[6, 1]):
        game.resolve_charge_end_mortal_wounds(dread, enemy, spec)

    assert applied["amount"] == 4


def test_gun_crazy_show_offs_sets_snazzgun_attacks_to_four_against_closest_target():
    game, ork_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Flash Gitz",
        ability_name="Gun-crazy Show-offs",
        ability_desc=GUN_CRAZY_SHOW_OFFS_TEXT,
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
    )
    close_target = _make_unit("Close Target", faction_name="Enemy", faction_keywords=["EN"])
    far_target = _make_unit("Far Target", faction_name="Enemy", faction_keywords=["EN"])
    ork_army.add_unit(attacker)
    enemy_army.add_unit(close_target)
    enemy_army.add_unit(far_target)

    _deploy_unit(game, attacker, 0.0, 0.0)
    _deploy_unit(game, close_target, 10.0, 0.0)
    _deploy_unit(game, far_target, 20.0, 0.0)

    profile = _make_profile(weapon_name="snazzgun", range_val="24", is_ranged=True, attacks="2")

    close_info = profile.preview_attack_count(
        close_target,
        attacker.models[0],
        game_map=game.map,
        publish_roll_event=False,
    )
    far_info = profile.preview_attack_count(
        far_target,
        attacker.models[0],
        game_map=game.map,
        publish_roll_event=False,
    )

    assert int(close_info.num_attacks or 0) == 4
    assert any("Gun-crazy Show-offs" in str(text or "") for text in list(close_info.special_modifiers or []))
    assert int(far_info.num_attacks or 0) == 2
    assert not any("Gun-crazy Show-offs" in str(text or "") for text in list(far_info.special_modifiers or []))
