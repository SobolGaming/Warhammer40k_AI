from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id

from tests.orks_enhancement_test_utils import (
    alive_wounds,
    apply_enhancement,
    build_game,
    find_battleshock_clear_request,
    find_quarry_request,
    make_unit,
    option_for_target,
    register_units_on_map,
    set_phase,
    set_unit_location,
    simple_melee_profile,
    simple_ranged_profile,
)


def _sequence_rng(*values: int):
    rolls = iter(values)
    return SimpleNamespace(randint=lambda _lo, _hi: next(rolls))


def test_da_kaptin_applies_d3_mortals_then_clears_battleshock_once_per_battle_round():
    leader = make_unit(
        "Warboss",
        "orks-da-kaptin-source",
        keywords=["CHARACTER", "INFANTRY", "WARBOSS"],
        faction_keywords=["ORKS"],
        wounds="6",
    )
    rattled = make_unit(
        "Rattled Boyz",
        "orks-da-kaptin-target",
        keywords=["INFANTRY"],
        faction_keywords=["ORKS"],
        wounds="4",
    )
    bystander = make_unit(
        "Fresh Boyz",
        "orks-da-kaptin-bystander",
        keywords=["INFANTRY"],
        faction_keywords=["ORKS"],
        wounds="4",
    )
    enemy = make_unit(
        "Enemy Unit",
        "enemy-da-kaptin-dummy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, ork_army, _enemy_army = build_game(
        detachment="Freebooter Krew",
        ork_units=[leader, rattled, bystander],
        enemy_units=[enemy],
    )
    apply_enhancement(ork_army, leader, "Da Kaptin")
    rattled.apply_status_effect(BattleShockEffect(game.turn))
    assert rattled.is_battle_shocked() is True

    set_unit_location(leader, 0.0, 0.0)
    set_unit_location(rattled, 3.0, 0.0)
    set_unit_location(bystander, 5.0, 0.0)
    set_unit_location(enemy, 20.0, 0.0)
    register_units_on_map(game, leader, rattled, bystander, enemy)
    game.random_source = _sequence_rng(3)

    wounds_before = alive_wounds(rattled)
    set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0, active_player=ork_player)
    request = find_battleshock_clear_request(game)
    assert request is not None

    outcome = resolve_decision_command(
        game,
        request,
        option_for_target(request, rattled).option_id,
        player_id=ork_player.id,
    )
    assert bool(getattr(outcome, "ok", False))
    assert rattled.is_battle_shocked() is False
    assert alive_wounds(rattled) == wounds_before - 2
    assert bystander.is_battle_shocked() is False

    set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0, active_player=ork_player)
    assert find_battleshock_clear_request(game) is None

    game.turn = 2
    rattled.apply_status_effect(BattleShockEffect(game.turn))
    set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0, active_player=ork_player)
    assert find_battleshock_clear_request(game) is not None


def test_da_kaptin_does_not_queue_for_non_battleshocked_or_out_of_range_targets():
    leader = make_unit(
        "Warboss",
        "orks-da-kaptin-negative-source",
        keywords=["CHARACTER", "INFANTRY", "WARBOSS"],
        faction_keywords=["ORKS"],
    )
    calm = make_unit(
        "Calm Boyz",
        "orks-da-kaptin-negative-calm",
        keywords=["INFANTRY"],
        faction_keywords=["ORKS"],
    )
    far = make_unit(
        "Far Boyz",
        "orks-da-kaptin-negative-far",
        keywords=["INFANTRY"],
        faction_keywords=["ORKS"],
    )
    enemy = make_unit(
        "Enemy Unit",
        "enemy-da-kaptin-negative",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, ork_army, _enemy_army = build_game(
        detachment="Freebooter Krew",
        ork_units=[leader, calm, far],
        enemy_units=[enemy],
    )
    apply_enhancement(ork_army, leader, "Da Kaptin")
    far.apply_status_effect(BattleShockEffect(game.turn))

    set_unit_location(leader, 0.0, 0.0)
    set_unit_location(calm, 4.0, 0.0)
    set_unit_location(far, 13.5, 0.0)
    set_unit_location(enemy, 20.0, 0.0)
    register_units_on_map(game, leader, calm, far, enemy)

    set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0, active_player=ork_player)
    assert find_battleshock_clear_request(game) is None


def test_bionik_workshop_roll_table_applies_each_branch_without_leaking_to_other_units():
    expectations = {
        1: "legs",
        3: "arms",
        5: "bonce",
    }
    for roll, expected_branch in expectations.items():
        leader = make_unit(
            "Big Mek",
            f"orks-bionik-roll-{roll}",
            keywords=["CHARACTER", "INFANTRY", "BIG MEK", "MEK"],
            faction_keywords=["ORKS"],
            movement="10",
        )
        bystander = make_unit(
            "Other Boyz",
            f"orks-bionik-bystander-{roll}",
            keywords=["INFANTRY"],
            faction_keywords=["ORKS"],
            movement="10",
        )
        enemy = make_unit(
            "Enemy Unit",
            f"enemy-bionik-roll-{roll}",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness="5",
        )
        game, ork_player, _enemy_player, ork_army, _enemy_army = build_game(
            detachment="Freebooter Krew",
            ork_units=[leader, bystander],
            enemy_units=[enemy],
        )
        apply_enhancement(ork_army, leader, "Bionik Workshop")
        set_unit_location(leader, 0.0, 0.0)
        set_unit_location(bystander, 8.0, 0.0)
        set_unit_location(enemy, 2.0, 0.0)
        register_units_on_map(game, leader, bystander, enemy)
        game.random_source = _sequence_rng(roll)

        game.event_system.publish("battle_round_started", game=game, battle_round=1)

        choice = leader.get_bionik_workshop_choice(ability_key="bionik_workshop")
        assert choice is not None
        assert choice["branch_key"] == expected_branch
        assert bystander.get_bionik_workshop_choice(ability_key="bionik_workshop") is None

        if expected_branch == "legs":
            assert int(leader.get_effective_model_characteristic(leader.models[0], "movement", game_map=game.map)) == 12
            assert int(bystander.get_effective_model_characteristic(bystander.models[0], "movement", game_map=game.map)) == 10
        elif expected_branch == "arms":
            wound_preview = simple_melee_profile()._wound_target_with_tracking(
                enemy,
                leader.models[0],
                {"target_model": enemy.models[0]},
                roll_value=4,
            )
            assert any("+1S from Bionik Workshop" in mod for mod in list(wound_preview.get("modifiers", []) or []))
            bystander_preview = simple_melee_profile()._wound_target_with_tracking(
                enemy,
                bystander.models[0],
                {"target_model": enemy.models[0]},
                roll_value=4,
            )
            assert not any("Bionik Workshop" in mod for mod in list(bystander_preview.get("modifiers", []) or []))
        else:
            hit_preview = simple_melee_profile()._hit_target_with_tracking(
                enemy,
                leader.models[0],
                {},
                preview_modifiers=True,
            )
            assert any(value == 1 and "Bionik Workshop" in reason for value, reason in list(hit_preview.get("skill_mods", []) or []))
            bystander_preview = simple_melee_profile()._hit_target_with_tracking(
                enemy,
                bystander.models[0],
                {},
                preview_modifiers=True,
            )
            assert not any("Bionik Workshop" in reason for _value, reason in list(bystander_preview.get("skill_mods", []) or []))


def test_supa_glowy_fing_does_not_queue_outside_command_phase_or_without_visible_target():
    leader = make_unit(
        "Big Mek",
        "orks-supa-negative-source",
        keywords=["CHARACTER", "INFANTRY", "MEK", "BIG MEK"],
        faction_keywords=["ORKS"],
    )
    visible_enemy = make_unit(
        "Visible Enemy",
        "enemy-supa-visible",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    hidden_enemy = make_unit(
        "Hidden Enemy",
        "enemy-supa-hidden",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, ork_army, _enemy_army = build_game(
        detachment="Dread Mob",
        ork_units=[leader],
        enemy_units=[visible_enemy, hidden_enemy],
    )
    apply_enhancement(ork_army, leader, "Supa-glowy Fing")
    set_unit_location(leader, 0.0, 0.0)
    set_unit_location(visible_enemy, 10.0, 0.0)
    set_unit_location(hidden_enemy, 10.0, 6.0)
    register_units_on_map(game, leader, visible_enemy, hidden_enemy)

    set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0, active_player=ork_player)
    assert find_quarry_request(game, ability="supa_glowy_fing") is None

    leader._has_line_of_sight_to_target = lambda _model, target_unit, _game_map: getattr(target_unit, "name", "") == "Visible Enemy"
    set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0, active_player=ork_player)
    request = find_quarry_request(game, ability="supa_glowy_fing")
    assert request is not None
    option_labels = {str((option.payload or {}).get("target_unit_id", "") or "") for option in list(request.options or [])}
    assert option_for_target(request, visible_enemy) is not None
    assert str(get_entity_id(hidden_enemy) or "") not in option_labels


def test_supa_glowy_fing_does_not_queue_for_enemy_out_of_range():
    leader = make_unit(
        "Big Mek",
        "orks-supa-range-source",
        keywords=["CHARACTER", "INFANTRY", "MEK", "BIG MEK"],
        faction_keywords=["ORKS"],
    )
    enemy = make_unit(
        "Far Enemy",
        "enemy-supa-range-far",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, ork_army, _enemy_army = build_game(
        detachment="Dread Mob",
        ork_units=[leader],
        enemy_units=[enemy],
    )
    apply_enhancement(ork_army, leader, "Supa-glowy Fing")
    set_unit_location(leader, 0.0, 0.0)
    set_unit_location(enemy, 22.0, 0.0)
    register_units_on_map(game, leader, enemy)

    set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0, active_player=ork_player)
    assert find_quarry_request(game, ability="supa_glowy_fing") is None


def test_supa_glowy_fing_forces_battleshock_on_roll_one_to_two_without_leakage():
    leader = make_unit(
        "Big Mek",
        "orks-supa-branch-bs-source",
        keywords=["CHARACTER", "INFANTRY", "MEK", "BIG MEK"],
        faction_keywords=["ORKS"],
    )
    target = make_unit(
        "Enemy Target",
        "enemy-supa-branch-bs-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    bystander = make_unit(
        "Enemy Bystander",
        "enemy-supa-branch-bs-bystander",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, ork_army, _enemy_army = build_game(
        detachment="Dread Mob",
        ork_units=[leader],
        enemy_units=[target, bystander],
    )
    apply_enhancement(ork_army, leader, "Supa-glowy Fing")
    set_unit_location(leader, 0.0, 0.0)
    set_unit_location(target, 10.0, 0.0)
    set_unit_location(bystander, 12.0, 2.0)
    register_units_on_map(game, leader, target, bystander)
    game.random_source = _sequence_rng(2)

    called: list[tuple[int, int, str]] = []
    target.force_battle_shock_test = lambda current_turn, modifier=0, source="": called.append(
        (int(current_turn), int(modifier), str(source))
    )

    set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0, active_player=ork_player)
    request = find_quarry_request(game, ability="supa_glowy_fing")
    assert request is not None
    outcome = resolve_decision_command(
        game,
        request,
        option_for_target(request, target).option_id,
        player_id=ork_player.id,
    )
    assert bool(getattr(outcome, "ok", False))
    assert called == [(1, 0, "Supa-glowy Fing")]
    assert "owner_command_phase_attack_hit_penalty_active" not in dict(getattr(target, "special_rules", {}) or {})
    assert "owner_command_phase_attack_hit_penalty_active" not in dict(getattr(bystander, "special_rules", {}) or {})


def test_supa_glowy_fing_applies_d3_mortals_on_roll_three_to_four():
    leader = make_unit(
        "Big Mek",
        "orks-supa-branch-mw-source",
        keywords=["CHARACTER", "INFANTRY", "MEK", "BIG MEK"],
        faction_keywords=["ORKS"],
    )
    target = make_unit(
        "Enemy Target",
        "enemy-supa-branch-mw-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
    )
    bystander = make_unit(
        "Enemy Bystander",
        "enemy-supa-branch-mw-bystander",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
    )
    game, ork_player, _enemy_player, ork_army, _enemy_army = build_game(
        detachment="Dread Mob",
        ork_units=[leader],
        enemy_units=[target, bystander],
    )
    apply_enhancement(ork_army, leader, "Supa-glowy Fing")
    set_unit_location(leader, 0.0, 0.0)
    set_unit_location(target, 10.0, 0.0)
    set_unit_location(bystander, 12.0, 2.0)
    register_units_on_map(game, leader, target, bystander)
    game.random_source = _sequence_rng(4, 3)

    target_wounds_before = alive_wounds(target)
    bystander_wounds_before = alive_wounds(bystander)

    set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0, active_player=ork_player)
    request = find_quarry_request(game, ability="supa_glowy_fing")
    assert request is not None
    outcome = resolve_decision_command(
        game,
        request,
        option_for_target(request, target).option_id,
        player_id=ork_player.id,
    )
    assert bool(getattr(outcome, "ok", False))
    assert alive_wounds(target) == target_wounds_before - 2
    assert alive_wounds(bystander) == bystander_wounds_before


def test_supa_glowy_fing_applies_and_expires_temporary_hit_penalty_without_leakage():
    leader = make_unit(
        "Big Mek",
        "orks-supa-branch-hit-source",
        keywords=["CHARACTER", "INFANTRY", "MEK", "BIG MEK"],
        faction_keywords=["ORKS"],
    )
    target = make_unit(
        "Enemy Target",
        "enemy-supa-branch-hit-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    bystander = make_unit(
        "Enemy Bystander",
        "enemy-supa-branch-hit-bystander",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ork_target = make_unit(
        "Boyz",
        "orks-supa-branch-hit-ork-target",
        keywords=["INFANTRY"],
        faction_keywords=["ORKS"],
    )
    game, ork_player, enemy_player, ork_army, _enemy_army = build_game(
        detachment="Dread Mob",
        ork_units=[leader, ork_target],
        enemy_units=[target, bystander],
    )
    apply_enhancement(ork_army, leader, "Supa-glowy Fing")
    set_unit_location(leader, 0.0, 0.0)
    set_unit_location(ork_target, 6.0, 0.0)
    set_unit_location(target, 10.0, 0.0)
    set_unit_location(bystander, 12.0, 2.0)
    register_units_on_map(game, leader, ork_target, target, bystander)
    game.random_source = _sequence_rng(6)

    set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0, active_player=ork_player)
    request = find_quarry_request(game, ability="supa_glowy_fing")
    assert request is not None
    outcome = resolve_decision_command(
        game,
        request,
        option_for_target(request, target).option_id,
        player_id=ork_player.id,
    )
    assert bool(getattr(outcome, "ok", False))

    ranged_profile = simple_ranged_profile()
    target_preview = ranged_profile._hit_target_with_tracking(
        ork_target,
        target.models[0],
        {},
        preview_modifiers=True,
    )
    assert any(value == -1 and "Supa-glowy Fing" in reasons[0] for value, reasons in list(target_preview.get("hit_mods", []) or []))
    bystander_preview = ranged_profile._hit_target_with_tracking(
        ork_target,
        bystander.models[0],
        {},
        preview_modifiers=True,
    )
    assert not any(value == -1 and reasons and "Supa-glowy Fing" in reasons[0] for value, reasons in list(bystander_preview.get("hit_mods", []) or []))

    set_phase(game, phase_name="COMMAND_PHASE", current_player_index=1, active_player=enemy_player)
    target_preview = ranged_profile._hit_target_with_tracking(
        ork_target,
        target.models[0],
        {},
        preview_modifiers=True,
    )
    assert any(value == -1 for value, _reasons in list(target_preview.get("hit_mods", []) or []))

    game.turn = 2
    set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0, active_player=ork_player)
    target_preview = ranged_profile._hit_target_with_tracking(
        ork_target,
        target.models[0],
        {},
        preview_modifiers=True,
    )
    assert not any(value == -1 for value, _reasons in list(target_preview.get("hit_mods", []) or []))
