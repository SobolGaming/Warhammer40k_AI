from __future__ import annotations

import re
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import (
    MovementType,
    build_collision_trees,
    get_validation_rules,
    is_position_valid_unified_detailed,
    validate_final_position,
)
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: str = "2",
    ):
        slug = str(name or "unit").lower().replace(" ", "_")
        self.id = f"mock_{slug}"
        self.name = name
        faction_kw = [str(keyword).upper() for keyword in list(faction_keywords or [])]
        self.faction_data = {"name": "Orks" if "ORKS" in faction_kw else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "4",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None, model_count: int = 1, wounds: str = "2") -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army.with_detachment("Orks", "Green Tide")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ork_player = Player("Orks", control=PlayerControl.LOCAL, army=ork_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)

    ork_player.command_points = 10
    enemy_player.command_points = 10
    ork_army.configure_rule_managers(force=True)
    ork_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, ork_player, enemy_player, ork_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _resolve_available_stratagem_name(player: Player, expected_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", str(expected_name or "").lower().replace("’", "'"))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for stratagem in list(player.stratagems.available or []):
        name = str(getattr(stratagem, "name", "") or "")
        normalized_name = re.sub(r"[^a-z0-9 ]+", " ", name.lower().replace("’", "'"))
        normalized_name = re.sub(r"\s+", " ", normalized_name).strip()
        if normalized_name == normalized:
            return name
    return expected_name


def _find_pending_reaction(player: Player, expected_name: str) -> dict | None:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", str(expected_name or "").lower().replace("’", "'"))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for reaction in list(player.stratagems.get_pending_reactions() or []):
        name = str(reaction.get("stratagem", "") or "")
        normalized_name = re.sub(r"[^a-z0-9 ]+", " ", name.lower().replace("’", "'"))
        normalized_name = re.sub(r"\s+", " ", normalized_name).strip()
        if normalized_name == normalized:
            return reaction
    return None


def _find_decision(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if getattr(request, "decision_type", None) == decision_type:
            return request
    return None


def _resolve_yes_option(game: Game, request, *, player_id: str) -> None:
    yes_option = None
    for option in list(getattr(request, "options", []) or []):
        if bool((getattr(option, "payload", {}) or {}).get("choice", False)):
            yes_option = option
            break
    if yes_option is None:
        raise AssertionError("Expected a yes option")
    resolve_decision_command(game, request, yes_option.option_id, player_id=player_id)


def test_come_on_ladz_returns_up_to_d3_plus_2_destroyed_boyz_models():
    game, ork_player, _enemy_player, ork_army, enemy_army = _build_game()
    boyz = _make_unit(
        "Boyz Mob",
        keywords=["INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
        model_count=6,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ork_army.add_unit(boyz)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, boyz, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)

    removed = list(boyz.models[:3])
    for model in removed:
        boyz.remove_model(model)
    assert len(list(getattr(boyz, "models_lost", []) or [])) == 3

    _set_phase(game, ork_player, "COMMAND_PHASE", 0)
    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=2):
        ok = ork_player.stratagems.use("COME ON LADZ!", unit=boyz, phase_name="Command phase")

    assert ok
    assert int(ork_player.command_points or 0) == 9
    assert len(list(getattr(boyz, "models_lost", []) or [])) == 0
    assert len(list(getattr(boyz, "models", []) or [])) == 6


def test_come_on_ladz_excludes_character_models():
    game, ork_player, _enemy_player, ork_army, enemy_army = _build_game()
    boyz = _make_unit(
        "Boyz",
        keywords=["INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
        model_count=5,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ork_army.add_unit(boyz)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, boyz, 20.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)

    removed_normal = boyz.models[0]
    removed_character = boyz.models[1]
    boyz.remove_model(removed_normal)
    boyz.remove_model(removed_character)
    removed_character.keywords.append("CHARACTER")

    _set_phase(game, ork_player, "COMMAND_PHASE", 0)
    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=3):
        ok = ork_player.stratagems.use("COME ON LADZ!", unit=boyz, phase_name="Command phase")

    assert ok
    assert int(ork_player.command_points or 0) == 9
    assert len(list(getattr(boyz, "models", []) or [])) == 4
    assert removed_character in list(getattr(boyz, "models_lost", []) or [])


def test_come_on_ladz_requires_boyz_keyword():
    game, ork_player, _enemy_player, ork_army, enemy_army = _build_game()
    nobz = _make_unit(
        "Nobz",
        keywords=["INFANTRY", "NOBZ"],
        faction_keywords=["ORKS"],
        model_count=4,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ork_army.add_unit(nobz)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, nobz, 30.0, 10.0)
    _deploy_unit(game, enemy, 40.0, 10.0)

    removed = nobz.models[0]
    nobz.remove_model(removed)
    _set_phase(game, ork_player, "COMMAND_PHASE", 0)

    blocked = ork_player.stratagems.use("COME ON LADZ!", unit=nobz, phase_name="Command phase")
    assert not blocked
    assert int(ork_player.command_points or 0) == 10


def test_come_on_ladz_descriptor_registered():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000008882005")
    assert descriptor is not None
    assert descriptor.name == "COME ON LADZ!"
    assert descriptor.effect == "return_destroyed_models"
    assert str(descriptor.effect_params.get("return_roll", "")).upper() == "D3+2"
    assert bool(descriptor.effect_params.get("exclude_character", False)) is True

    by_name = get_stratagem_tool_descriptor(name="COME ON LADZ!")
    assert by_name is not None
    assert by_name.stratagem_id == "000008882005"


def test_bulldozer_brutality_expands_fight_eligibility_only_while_active() -> None:
    game, ork_player, enemy_player, ork_army, enemy_army = _build_game()
    boyz = _make_unit(
        "Boyz Mob",
        keywords=["INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ork_army.add_unit(boyz)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, boyz, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    boyz.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    boyz.models[1].set_location(13.9, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(11.5, 10.0, 0.0, 0.0)
    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)

    strat_name = _resolve_available_stratagem_name(ork_player, "BULLDOZER BRUTALITY")
    assert ork_player.stratagems.use(strat_name, unit=boyz, phase_name="Fight phase")

    base_eligible = boyz.get_fight_eligible_models_for_target(enemy, game_map=game.map, allow_within_3=False)
    expanded_eligible = boyz.get_fight_eligible_models_for_target(enemy, game_map=game.map, allow_within_3=True)

    assert boyz.models[0] in base_eligible
    assert boyz.models[1] not in base_eligible
    assert boyz.models[0] in expanded_eligible
    assert boyz.models[1] in expanded_eligible
    assert bool(boyz.special_rules.get("orks_bulldozer_brutality_active")) is True
    assert str(boyz.special_rules.get("fight_within_3_active_source", "") or "") == strat_name

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert bool(boyz.special_rules.get("orks_bulldozer_brutality_active")) is False
    assert "fight_within_3" not in boyz.special_rules
    assert bool(boyz.special_rules.get("fight_within_3_active")) is False


def test_bulldozer_brutality_rejects_wrong_phase_and_wrong_target_unit() -> None:
    game, ork_player, _enemy_player, ork_army, enemy_army = _build_game()
    nobz = _make_unit(
        "Nobz Mob",
        keywords=["INFANTRY", "NOBZ"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ork_army.add_unit(nobz)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, nobz, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    _set_phase(game, ork_player, "SHOOTING_PHASE", 0)

    strat_name = _resolve_available_stratagem_name(ork_player, "BULLDOZER BRUTALITY")
    assert not ork_player.stratagems.use(strat_name, unit=nobz, phase_name="Shooting phase")
    assert int(ork_player.command_points or 0) == 10

    _set_phase(game, ork_player, "FIGHT_PHASE", 0)
    assert not ork_player.stratagems.use(strat_name, unit=nobz, phase_name="Fight phase")
    assert int(ork_player.command_points or 0) == 10


def test_go_get_em_waits_until_attacker_finishes_shooting_and_uses_reroll_branch() -> None:
    game, ork_player, enemy_player, ork_army, enemy_army = _build_game()
    boyz = _make_unit(
        "Boyz Mob",
        keywords=["INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
        model_count=10,
    )
    attacker = _make_unit("Enemy Shooter", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    bystander = _make_unit("Enemy Bystander", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ork_army.add_unit(boyz)
    enemy_army.add_unit(attacker)
    enemy_army.add_unit(bystander)
    _deploy_unit(game, boyz, 10.0, 10.0)
    _deploy_unit(game, attacker, 16.0, 10.0)
    _deploy_unit(game, bystander, 30.0, 10.0)
    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)

    provider_calls: list[dict] = []
    game.install_decision_providers(roll_reroll_provider=lambda **kwargs: provider_calls.append(dict(kwargs)) or True)

    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=attacker,
        target_units=[boyz],
    )
    pending = _find_pending_reaction(ork_player, "GO GET 'EM!")
    assert pending is not None
    assert pending.get("target_unit") is boyz

    strat_name = _resolve_available_stratagem_name(ork_player, "GO GET 'EM!")
    assert ork_player.stratagems.use(strat_name, unit=boyz, attacking_unit=attacker, phase_name="Shooting phase")
    assert _find_decision(game, DECISION_CONFIRM_YES_NO) is None
    assert _find_decision(game, DECISION_MOVE_UNIT) is None

    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[2, 5]):
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=attacker,
            hits_by_target={boyz: 1},
        )
        confirm_request = _find_decision(game, DECISION_CONFIRM_YES_NO)
        assert confirm_request is not None
        confirm_ctx = confirm_request.context or {}
        assert confirm_ctx.get("reactive_move_kind") == "horde_move"
        assert confirm_ctx.get("reactive_move_attacker_unit_id") == get_entity_id(attacker)

        _resolve_yes_option(game, confirm_request, player_id=ork_player.id)

    move_request = _find_decision(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    move_ctx = move_request.context or {}
    assert move_ctx.get("movement_type") == "horde_move"
    assert int(move_ctx.get("max_distance") or 0) == 5
    assert provider_calls
    assert provider_calls[0]["roll_type"] == "horde_move"
    assert provider_calls[0]["allow_reroll"] is True

    normal_rules = get_validation_rules(MovementType.MOVE, moving_unit=boyz)
    normal_collision_trees = build_collision_trees(
        boyz,
        MovementType.MOVE,
        game.map,
        moving_model=boyz.models[0],
        max_distance=5.0,
    )
    invalid_normal = is_position_valid_unified_detailed(
        (15.0, 10.0, 0.0),
        boyz.models[0],
        normal_collision_trees,
        normal_rules,
        game.map,
        is_final_position=True,
    )
    assert not bool(invalid_normal.get("valid", False))

    horde_rules = get_validation_rules(MovementType.HORDE_MOVE, moving_unit=boyz)
    horde_rules["blood_surge_max_distance"] = 5.0

    invalid_not_closer = validate_final_position(
        boyz.models[0],
        (10.0, 15.0, 0.0),
        horde_rules,
        game.map,
    )
    assert not bool(invalid_not_closer.get("valid", False))

    valid_horde = validate_final_position(
        boyz.models[0],
        (15.0, 10.0, 0.0),
        horde_rules,
        game.map,
    )
    assert bool(valid_horde.get("valid", False))


def test_go_get_em_checks_ten_model_reroll_after_attacker_finishes_shooting() -> None:
    game, ork_player, enemy_player, ork_army, enemy_army = _build_game()
    boyz = _make_unit(
        "Boyz Mob",
        keywords=["INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
        model_count=10,
    )
    attacker = _make_unit("Enemy Shooter", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ork_army.add_unit(boyz)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, boyz, 10.0, 10.0)
    _deploy_unit(game, attacker, 16.0, 10.0)
    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)

    provider_calls: list[dict] = []
    game.install_decision_providers(roll_reroll_provider=lambda **kwargs: provider_calls.append(dict(kwargs)) or True)

    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=attacker,
        target_units=[boyz],
    )
    strat_name = _resolve_available_stratagem_name(ork_player, "GO GET 'EM!'")
    assert ork_player.stratagems.use(strat_name, unit=boyz, attacking_unit=attacker, phase_name="Shooting phase")

    boyz.models = list(boyz.models[:9])

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=attacker,
            hits_by_target={boyz: 1},
        )
        confirm_request = _find_decision(game, DECISION_CONFIRM_YES_NO)
        assert confirm_request is not None
        _resolve_yes_option(game, confirm_request, player_id=ork_player.id)

    move_request = _find_decision(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    move_ctx = move_request.context or {}
    assert int(move_ctx.get("max_distance") or 0) == 2
    assert provider_calls == []


def test_go_get_em_rejects_wrong_phase_and_wrong_target_unit() -> None:
    game, ork_player, enemy_player, ork_army, enemy_army = _build_game()
    nobz = _make_unit(
        "Nobz Mob",
        keywords=["INFANTRY", "NOBZ"],
        faction_keywords=["ORKS"],
        model_count=5,
    )
    attacker = _make_unit("Enemy Shooter", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ork_army.add_unit(nobz)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, nobz, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)

    strat_name = _resolve_available_stratagem_name(ork_player, "GO GET 'EM!")
    _set_phase(game, ork_player, "SHOOTING_PHASE", 0)
    assert not ork_player.stratagems.use(strat_name, unit=nobz, attacking_unit=attacker, phase_name="Shooting phase")

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=attacker,
        target_units=[nobz],
    )
    assert not ork_player.stratagems.use(strat_name, unit=nobz, attacking_unit=attacker, phase_name="Shooting phase")
    assert int(ork_player.command_points or 0) == 10


def test_green_tide_new_descriptors_registered() -> None:
    bulldozer = get_stratagem_tool_descriptor(stratagem_id="000008882003")
    assert bulldozer is not None
    assert bulldozer.name == "BULLDOZER BRUTALITY"
    assert bulldozer.effect == "fight_within_3_activation"

    go_get_em = get_stratagem_tool_descriptor(stratagem_id="000008882007")
    assert go_get_em is not None
    assert go_get_em.name == "GO GET 'EM!"
    assert go_get_em.effect == "reactive_normal_move"
    assert bool(go_get_em.effect_params.get("grant_distance_reroll_if_effective_10_models")) is True
