from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_utils import model_within_engagement_range_of_unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str | None = None, faction_id: str = "SM") -> Unit:
    datasheet = _WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id=faction_id)
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.turn = 2
    game.current_player_index = 0
    return game, sm_army, enemy_army, sm_player, enemy_player


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_master_request(game: Game, *, source_unit: Unit | None = None):
    source_id = str(get_entity_id(source_unit) or "") if source_unit is not None else ""
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") != "master_of_mechanisms":
            continue
        if source_id and str(context.get("source_unit_id", "") or "") != source_id:
            continue
        return request
    return None


def _weapon_option(request, target_model, weapon_name: str):
    target_model_id = str(get_entity_id(target_model) or "")
    chosen_weapon = str(weapon_name or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_model_id", "") or "") != target_model_id:
            continue
        if str(payload.get("weapon_name", "") or "").strip().lower() == chosen_weapon:
            return option
    return None


def test_iron_priest_parser_supports_gift_of_the_iron_wolf():
    iron_priest = _actual_unit("Iron Priest")

    rule = iron_priest.get_command_phase_vehicle_repair_hit_bonus_rule()

    assert isinstance(rule, dict)
    assert str(rule.get("source", "") or "") == "Gift of the Iron Wolf"
    assert str(rule.get("phase", "") or "") == "COMMAND_PHASE"
    assert bool(rule.get("target_requires_vehicle", False)) is True
    assert str(rule.get("target_keyword", "") or "") == "ADEPTUS ASTARTES"
    assert str(rule.get("selection_kind", "") or "") == "model"
    assert bool(rule.get("limit_once_per_turn", False)) is True
    assert str(rule.get("limit_scope", "") or "") == "model"
    assert bool(rule.get("weapon_choice_required", False)) is True
    assert str(rule.get("weapon_attack_type", "") or "") == "ranged"
    assert list(rule.get("weapon_keywords", []) or []) == ["RAPID FIRE 1"]


def test_iron_priest_gift_of_the_iron_wolf_heals_and_buffs_only_the_selected_weapon_until_next_command_phase():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    iron_priest = _actual_unit("Iron Priest")
    vehicle = _actual_unit("Ballistus Dreadnought")
    target = _actual_unit("Rhino")
    sm_army.add_unit(iron_priest)
    sm_army.add_unit(vehicle)
    enemy_army.add_unit(target)

    _deploy(iron_priest, 0.0, 0.0)
    _deploy(vehicle, 2.0, 0.0)
    _deploy(target, 20.0, 0.0)
    _register_units(game, iron_priest, vehicle, target)

    vehicle_model = vehicle.models[0]
    vehicle_model.wounds = int(vehicle_model.wounds) - 3
    before_wounds = int(vehicle_model.wounds)

    lascannon = next(wg for wg in list(vehicle_model.wargear or []) if wg.name == "Ballistus lascannon")
    lascannon_profile = lascannon.profiles["default"]
    missile_launcher = next(wg for wg in list(vehicle_model.wargear or []) if wg.name == "Ballistus missile launcher")
    missile_profile = missile_launcher.profiles["krak"]

    game._on_phase_start_master_of_mechanisms(player=sm_player, phase=game.phase)
    request = _find_master_request(game, source_unit=iron_priest)
    assert request is not None
    assert bool((request.context or {}).get("weapon_choice_required", False)) is True
    assert str((request.context or {}).get("weapon_attack_type", "") or "") == "ranged"
    assert list((request.context or {}).get("weapon_keywords", []) or []) == ["RAPID FIRE 1"]

    vehicle_weapon_names = {
        str((getattr(option, "payload", {}) or {}).get("weapon_name", "") or "")
        for option in list(request.options or [])
        if str((getattr(option, "payload", {}) or {}).get("target_model_id", "") or "") == str(get_entity_id(vehicle_model) or "")
    }
    assert {"Ballistus missile launcher", "Ballistus lascannon", "Twin storm bolter"} <= vehicle_weapon_names

    option = _weapon_option(request, vehicle_model, "Ballistus lascannon")
    assert option is not None
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        result = resolve_decision_command(game, request, option.option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert int(vehicle_model.wounds) == before_wounds + 2

    vehicle_sr = dict(getattr(vehicle, "special_rules", {}) or {})
    assert bool(vehicle_sr.get("master_of_mechanisms_weapon_keywords_active", False)) is True
    assert str(vehicle_sr.get("master_of_mechanisms_weapon_name", "") or "") == "Ballistus lascannon"
    assert list(vehicle_sr.get("master_of_mechanisms_weapon_keywords", []) or []) == ["RAPID FIRE 1"]

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    gifted_preview = lascannon_profile.preview_attack_count(target, vehicle_model, publish_roll_event=False)
    other_preview = missile_profile.preview_attack_count(target, vehicle_model, publish_roll_event=False)
    assert any(
        "Rapid Fire 1" in str(entry) and "Gift of the Iron Wolf" in str(entry)
        for entry in list(gifted_preview.special_modifiers or [])
    )
    assert not any(
        "Gift of the Iron Wolf" in str(entry)
        for entry in list(other_preview.special_modifiers or [])
    )

    game.phase = BattleRoundPhases.COMMAND_PHASE
    game._on_phase_start_master_of_mechanisms(player=sm_player, phase=game.phase)
    assert _find_master_request(game, source_unit=iron_priest) is None

    game.turn = 3
    game._on_phase_start_master_of_mechanisms_cleanup(player=sm_player, phase=BattleRoundPhases.COMMAND_PHASE)
    vehicle_sr_after = dict(getattr(vehicle, "special_rules", {}) or {})
    assert bool(vehicle_sr_after.get("master_of_mechanisms_weapon_keywords_active", False)) is False

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    cleaned_preview = lascannon_profile.preview_attack_count(target, vehicle_model, publish_roll_event=False)
    assert int(gifted_preview.num_attacks) == int(cleaned_preview.num_attacks) + 1
    assert not any(
        "Gift of the Iron Wolf" in str(entry)
        for entry in list(cleaned_preview.special_modifiers or [])
    )


def test_iron_priest_judgement_of_the_omnissiah_re_rolls_wounds_only_while_target_is_engaged_by_friendly_vehicle():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    iron_priest = _actual_unit("Iron Priest")
    friendly_vehicle = _actual_unit("Ballistus Dreadnought")
    enemy_target = _actual_unit("Rhino")
    sm_army.add_unit(iron_priest)
    sm_army.add_unit(friendly_vehicle)
    enemy_army.add_unit(enemy_target)

    _deploy(iron_priest, 0.0, 0.0)
    _deploy(friendly_vehicle, 10.0, 0.0)
    _deploy(enemy_target, 10.0, 0.0)
    _register_units(game, iron_priest, friendly_vehicle, enemy_target)

    assert bool(model_within_engagement_range_of_unit(friendly_vehicle.models[0], enemy_target)) is True

    engaged_mods = iron_priest.get_model_wound_reroll_modifiers(
        iron_priest.models[0],
        attack_type="ranged",
        target=enemy_target,
    )
    assert bool(engaged_mods.get("reroll_wound_full", False)) is True
    assert any(
        "Judgement of the Omnissiah" in str(reason)
        for reason in list(engaged_mods.get("reroll_wound_full_reasons", ()) or ())
    )

    _deploy(enemy_target, 30.0, 0.0)
    disengaged_mods = iron_priest.get_model_wound_reroll_modifiers(
        iron_priest.models[0],
        attack_type="ranged",
        target=enemy_target,
    )
    assert bool(disengaged_mods.get("reroll_wound_full", False)) is False
