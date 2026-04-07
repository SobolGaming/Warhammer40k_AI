from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_PICK_POINT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, faction_id: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, faction_id=faction_id))


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    gsc_army = Army.with_detachment("Genestealer Cults", "Other")
    gsc_army.faction_id = "GC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ORK"

    gsc_player = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(gsc_player)
    game.add_player(enemy_player)
    return game, gsc_player, enemy_player, gsc_army, enemy_army


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _attack_mod_stub() -> SimpleNamespace:
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


def _find_request(game: Game, *, decision_type: str, ability: str):
    ability_key = str(ability or "").strip().lower()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != decision_type:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != ability_key:
            continue
        return request
    return None


def _option_with_marker(request):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        marker_id = str(payload.get("marker_id", "") or "").strip()
        if marker_id:
            return option
    return None


def _option_for_action(request, action: str):
    action_key = str(action or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == action_key:
            return option
    return None


def test_abominant_the_chosen_one_grants_four_plus_fight_on_death_while_leading() -> None:
    game, _gsc_player, _enemy_player, gsc_army, _enemy_army = _build_game()

    abominant = _actual_unit("Abominant", faction_id="GC")
    aberrants = _actual_unit("Aberrants", faction_id="GC")
    gsc_army.add_unit(abominant)
    gsc_army.add_unit(aberrants)

    aberrants.attached_leaders = [abominant]
    abominant.attached_to = aberrants

    rule = aberrants.get_melee_fight_on_death_after_attacks_rule(model=aberrants.models[0])
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 4
    assert str(rule.get("source", "") or "") == "The Chosen One"

    _deploy(aberrants, 0.0, 0.0)
    aberrants.round_state.fought_this_phase = False
    aberrants._last_destroyed_by_weapon_profile = type(
        "_MeleeProfile",
        (),
        {
            "parent_wargear": type(
                "_MeleeWargear",
                (),
                {"is_melee": lambda self: True, "is_ranged": lambda self: False},
            )()
        },
    )()
    model = aberrants.models[0]
    model._wounds = 0

    with patch("warhammer40k_ai.units.unit.get_roll", return_value=4):
        aberrants._handle_model_destroyed(model, game.map)

    pending = list(getattr(aberrants, "_melee_fight_on_death_pending_models", []) or [])
    assert model in pending


def test_achilles_ridgerunners_flare_launcher_enables_smokescreen_for_zero_cp() -> None:
    game, gsc_player, _enemy_player, gsc_army, _enemy_army = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 1

    ridgerunners = _actual_unit("Achilles Ridgerunners", faction_id="GC")
    gsc_army.add_unit(ridgerunners)
    _deploy(ridgerunners, 0.0, 0.0)
    _register_units(game, ridgerunners)

    smokescreen = Stratagem(
        id="test_smokescreen",
        name="Smokescreen",
        type="Core - Strategic Ploy Stratagem",
        description="",
        cp_cost=1,
        turn="Opponent's turn",
        phase="Shooting phase",
        detachment="",
        faction_id="CORE",
    )

    assert ridgerunners.has_any_keyword("SMOKE") is True

    preview = gsc_player.preview_stratagem_cp_cost(
        smokescreen,
        target_unit=ridgerunners,
        assume_optional_discounts=True,
    )
    assert int(preview.get("cost", -1)) == 0
    assert "Flare Launcher" in " ".join(str(v) for v in list(preview.get("reasons", []) or []))

    gsc_player.set_next_optional_decision("FLARE_LAUNCHER_SMOKESCREEN_DISCOUNT", True)
    applied = gsc_player.apply_stratagem_cp_cost(smokescreen, target_unit=ridgerunners)
    assert int(applied.get("cost", -1)) == 0
    assert "Flare Launcher" in " ".join(str(v) for v in list(applied.get("reasons", []) or []))


def test_achilles_ridgerunners_spotter_sets_bearer_bs_three_plus() -> None:
    game, _gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()

    ridgerunners = _actual_unit("Achilles Ridgerunners", faction_id="GC")
    enemy = _actual_unit("Boyz", faction_id="ORK")
    gsc_army.add_unit(ridgerunners)
    enemy_army.add_unit(enemy)
    _deploy(ridgerunners, 0.0, 0.0)
    _deploy(enemy, 10.0, 0.0)
    _register_units(game, ridgerunners, enemy)

    bearer = ridgerunners.models[0]
    bearer.optional_wargear = ["Spotter"]
    ridgerunners._ability_cache = {}

    override = ridgerunners.get_model_attack_skill_override(bearer, attack_type="ranged")
    assert isinstance(override, dict)
    assert int(override.get("value", 0) or 0) == 3

    profile = next(iter(next(wg for wg in bearer.wargear if wg.name == "Heavy mining laser").profiles.values()))
    hit_result = profile._hit_target_with_tracking(
        enemy,
        bearer,
        {"_aura_attack_mods": _attack_mod_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(hit_result.get("hit")) is True
    assert int(hit_result.get("needed", 0) or 0) == 3
    assert any("Spotter" in str(effect or "") for effect in list(hit_result.get("special_effects", []) or []))


def test_achilles_ridgerunners_survey_augur_marks_target_once_and_grants_ignores_cover() -> None:
    game, gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    ridgerunners = _actual_unit("Achilles Ridgerunners", faction_id="GC")
    acolytes = _actual_unit("Acolyte Hybrids With Autopistols", faction_id="GC")
    enemy = _actual_unit("Boyz", faction_id="ORK")
    gsc_army.add_unit(ridgerunners)
    gsc_army.add_unit(acolytes)
    enemy_army.add_unit(enemy)
    _deploy(ridgerunners, 0.0, 0.0)
    _deploy(acolytes, 0.0, 5.0)
    _deploy(enemy, 10.0, 0.0)
    _register_units(game, ridgerunners, acolytes, enemy)

    bearer = ridgerunners.models[0]
    bearer.optional_wargear = ["Survey Augur"]
    ridgerunners._ability_cache = {}

    specs = ridgerunners.unit_post_shoot_no_cover_specs()
    assert len(specs) == 1
    spec = specs[0]
    assert str(spec.get("source", "") or "") == "Survey Augur"
    assert bool(spec.get("any_weapon")) is True
    assert str(spec.get("source_model_id", "") or "").strip()

    game._on_unit_shooting_resolved_post_shoot_no_cover(
        attacker_unit=ridgerunners,
        hits_by_target={enemy: 1},
        hit_models_by_target={enemy: {bearer}},
        hit_models_by_target_weapon={enemy: {"heavy mining laser": {bearer}}},
    )

    request = _find_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="post_shoot_no_cover")
    assert request is not None
    assert str((request.context or {}).get("source_model_id", "") or "") == str(spec.get("source_model_id", "") or "")

    result = resolve_decision_command(game, request, request.options[0].option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True

    profile = next(iter(next(wg for wg in acolytes.models[0].wargear if wg.name == "Autopistol").profiles.values()))
    attack_instance = {"_aura_attack_mods": _attack_mod_stub()}
    profile._hit_target_with_tracking(
        enemy,
        acolytes.models[0],
        attack_instance,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(attack_instance.get("ignores_cover", False)) is True


def test_acolyte_hybrids_with_autopistols_claimed_for_the_cult_gains_at_most_one_cp() -> None:
    game, gsc_player, _enemy_player, gsc_army, _enemy_army = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0

    acolytes = _actual_unit("Acolyte Hybrids With Autopistols", faction_id="GC")
    gsc_army.add_unit(acolytes)
    _deploy(acolytes, 0.0, 0.0)

    objective_1_location = SimpleNamespace(
        id="claimed-loc-1",
        x=0.5,
        y=0.0,
        control_radius=3.0,
        controlling_player=gsc_player,
        removed=False,
    )
    objective_2_location = SimpleNamespace(
        id="claimed-loc-2",
        x=1.5,
        y=0.0,
        control_radius=3.0,
        controlling_player=gsc_player,
        removed=False,
    )
    game.map.objectives = [
        SimpleNamespace(id="claimed-obj-1", location=objective_1_location, name="Objective 1"),
        SimpleNamespace(id="claimed-obj-2", location=objective_2_location, name="Objective 2"),
    ]

    with patch("warhammer40k_ai.engine.game_mixins.phase_handlers_mixin.get_roll", side_effect=[1, 4]):
        game.event_system.publish("phase_start", player=gsc_player, phase=BattleRoundPhases.COMMAND_PHASE)
    assert int(gsc_player.command_points or 0) == 1

    with patch("warhammer40k_ai.engine.game_mixins.phase_handlers_mixin.get_roll", side_effect=[4, 4]):
        game.event_system.publish("phase_start", player=gsc_player, phase=BattleRoundPhases.COMMAND_PHASE)
    assert int(gsc_player.command_points or 0) == 1


def test_acolyte_hybrids_with_hand_flamers_industrialised_destruction_full_reroll_on_objective_targets() -> None:
    game, _gsc_player, enemy_player, gsc_army, enemy_army = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    acolytes = _actual_unit("Acolyte Hybrids With Hand Flamers", faction_id="GC")
    enemy = _actual_unit("Boyz", faction_id="ORK")
    gsc_army.add_unit(acolytes)
    enemy_army.add_unit(enemy)
    _deploy(acolytes, 0.0, 0.0)
    _deploy(enemy, 10.0, 0.0)
    game.map.objectives = [
        SimpleNamespace(
            id="industrialised-obj",
            location=SimpleNamespace(
                id="industrialised-loc",
                x=10.0,
                y=0.0,
                control_radius=3.0,
                controlling_player=enemy_player,
                removed=False,
            ),
            name="Objective",
        )
    ]
    _register_units(game, acolytes, enemy)

    modifiers = acolytes.get_unit_wound_reroll_modifiers(attack_type="ranged", target=enemy)
    assert bool(modifiers.get("reroll_wound_ones")) is True
    assert bool(modifiers.get("reroll_wound_full")) is True
    assert any("objective range" in str(reason or "").lower() for reason in list(modifiers.get("reroll_wound_full_reasons", ()) or ()))

    profile = next(iter(next(wg for wg in acolytes.models[0].wargear if wg.name == "Hand flamer").profiles.values()))
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
        wound_result = profile._wound_target_with_tracking(
            enemy,
            acolytes.models[0],
            {"_aura_attack_mods": _attack_mod_stub()},
            roll_value=2,
            allow_rerolls=True,
            log_roll=False,
        )

    assert bool(wound_result.get("wound")) is True
    assert int(wound_result.get("reroll", 0) or 0) == 5
    assert any("Industrialised Destruction" in str(effect or "") for effect in list(wound_result.get("special_effects", []) or []))


def test_acolyte_iconward_summon_the_cult_invalid_then_valid_relocates_selected_marker() -> None:
    game, gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()

    iconward = _actual_unit("Acolyte Iconward", faction_id="GC")
    enemy = _actual_unit("Boyz", faction_id="ORK")
    gsc_army.add_unit(iconward)
    enemy_army.add_unit(enemy)
    _deploy(iconward, 0.0, 0.0)
    _deploy(enemy, 40.0, 0.0)

    manager = gsc_army.cult_ambush
    assert manager is not None
    first_marker = manager.place_marker_at(game, 10.0, 0.0)
    second_marker = manager.place_marker_at(game, 11.0, 0.0)
    assert first_marker is not None
    assert second_marker is not None

    _deploy(enemy, 18.0, 0.0)
    _register_units(game, iconward, enemy)
    game._on_unit_move_ended_cult_ambush(unit=enemy)

    request = _find_request(
        game,
        decision_type=DECISION_PICK_POINT,
        ability="summon_the_cult_marker_relocation",
    )
    assert request is not None

    marker_option = _option_with_marker(request)
    assert marker_option is not None

    invalid = resolve_decision_command(
        game,
        request,
        marker_option.option_id,
        result_payload={"point": [16.0, 0.0]},
        player_id=gsc_player.id,
    )
    assert bool(getattr(invalid, "ok", False)) is False
    assert "more than 9" in str((getattr(invalid, "errors", ()) or ("",))[0]).lower()
    assert bool(manager.summon_the_cult_used) is False

    active_after_invalid = list(manager.get_active_markers() or [])
    assert len(active_after_invalid) == 2
    assert all(bool(getattr(marker, "pending_relocation", False)) for marker in active_after_invalid)

    valid = resolve_decision_command(
        game,
        request,
        marker_option.option_id,
        result_payload={"point": [3.0, 0.0]},
        player_id=gsc_player.id,
    )
    assert bool(getattr(valid, "ok", False)) is True
    assert bool(manager.summon_the_cult_used) is True

    active_after_valid = list(manager.get_active_markers() or [])
    assert len(active_after_valid) == 1
    relocated = active_after_valid[0]
    assert float(getattr(relocated, "x", -1.0)) == 3.0
    assert float(getattr(relocated, "y", -1.0)) == 0.0
    assert bool(getattr(relocated, "pending_relocation", False)) is False


def test_acolyte_iconward_summon_the_cult_skip_removes_threatened_markers() -> None:
    game, gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()

    iconward = _actual_unit("Acolyte Iconward", faction_id="GC")
    enemy = _actual_unit("Boyz", faction_id="ORK")
    gsc_army.add_unit(iconward)
    enemy_army.add_unit(enemy)
    _deploy(iconward, 0.0, 0.0)
    _deploy(enemy, 40.0, 0.0)

    manager = gsc_army.cult_ambush
    marker = manager.place_marker_at(game, 10.0, 0.0)
    assert marker is not None

    _deploy(enemy, 18.0, 0.0)
    _register_units(game, iconward, enemy)
    game._on_unit_move_ended_cult_ambush(unit=enemy)

    request = _find_request(
        game,
        decision_type=DECISION_PICK_POINT,
        ability="summon_the_cult_marker_relocation",
    )
    assert request is not None

    skip_option = _option_for_action(request, "skip")
    assert skip_option is not None

    skipped = resolve_decision_command(game, request, skip_option.option_id, player_id=gsc_player.id)
    assert bool(getattr(skipped, "ok", False)) is True
    assert list(manager.get_active_markers() or []) == []
    assert bool(manager.summon_the_cult_used) is False
