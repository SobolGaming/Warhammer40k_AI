from __future__ import annotations

from tests.orks_enhancement_test_utils import (
    build_game,
    make_unit,
    register_units_on_map,
    set_phase,
    set_unit_location,
    simple_melee_profile,
    simple_ranged_profile,
)


def test_bionik_workshop_helper_persists_choice_and_applies_branch_state():
    leader = make_unit(
        "Kaptin",
        "orks-bionik-helper-kaptin",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ORKS"],
        movement="10",
    )
    enemy = make_unit(
        "Enemy Unit",
        "enemy-bionik-helper",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, _ork_player, _enemy_player, _ork_army, _enemy_army = build_game(
        detachment="Freebooter Krew",
        ork_units=[leader],
        enemy_units=[enemy],
    )
    set_unit_location(leader, 0.0, 0.0)
    set_unit_location(enemy, 10.0, 0.0)
    register_units_on_map(game, leader, enemy)

    applied = leader.apply_bionik_workshop_choice(
        branch_key="legs",
        source="Bionik Workshop",
        ability_key="bionik_workshop",
        source_model_id=str(getattr(leader.models[0], "id", "") or ""),
    )
    assert applied is True

    choice = leader.get_bionik_workshop_choice(ability_key="bionik_workshop")
    assert choice is not None
    assert choice["branch_key"] == "legs"
    assert choice["branch_label"] == "Bionik Legs"
    assert int(choice["move_bonus"]) == 2
    assert int(leader.get_effective_model_characteristic(leader.models[0], "movement", game_map=game.map)) == 12


def test_owner_command_phase_attack_hit_penalty_helper_expires_on_owner_command_phase_only():
    target = make_unit(
        "Enemy Shooters",
        "enemy-hit-penalty-helper",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ork_target = make_unit(
        "Boyz",
        "orks-hit-penalty-helper-target",
        keywords=["INFANTRY"],
        faction_keywords=["ORKS"],
    )
    game, ork_player, enemy_player, _ork_army, _enemy_army = build_game(
        detachment="Freebooter Krew",
        ork_units=[ork_target],
        enemy_units=[target],
    )
    set_unit_location(target, 0.0, 0.0)
    set_unit_location(ork_target, 8.0, 0.0)
    register_units_on_map(game, target, ork_target)

    target.apply_owner_command_phase_attack_hit_penalty(
        owner_id=ork_player.id,
        turn=1,
        source="Supa-glowy Fing",
        penalty=1,
    )
    ranged_profile = simple_ranged_profile()
    attacker_model = target.models[0]
    preview = ranged_profile._hit_target_with_tracking(
        ork_target,
        attacker_model,
        {},
        preview_modifiers=True,
    )
    assert any(value == -1 for value, _reasons in list(preview.get("hit_mods", []) or []))
    assert "owner_command_phase_attack_hit_penalty_active" in dict(getattr(target, "special_rules", {}) or {})

    set_phase(game, phase_name="COMMAND_PHASE", current_player_index=1, active_player=enemy_player)
    preview = ranged_profile._hit_target_with_tracking(
        ork_target,
        attacker_model,
        {},
        preview_modifiers=True,
    )
    assert any(value == -1 for value, _reasons in list(preview.get("hit_mods", []) or []))

    game.turn = 2
    set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0, active_player=ork_player)
    preview = ranged_profile._hit_target_with_tracking(
        ork_target,
        attacker_model,
        {},
        preview_modifiers=True,
    )
    assert not any(value == -1 for value, _reasons in list(preview.get("hit_mods", []) or []))
    assert "owner_command_phase_attack_hit_penalty_active" not in dict(getattr(target, "special_rules", {}) or {})


def test_bionik_workshop_helper_ws_and_strength_branches_feed_weapon_resolution():
    leader = make_unit(
        "Kaptin",
        "orks-bionik-helper-weapon-branches",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ORKS"],
    )
    enemy = make_unit(
        "Enemy Unit",
        "enemy-bionik-helper-weapon-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    game, _ork_player, _enemy_player, _ork_army, _enemy_army = build_game(
        detachment="Freebooter Krew",
        ork_units=[leader],
        enemy_units=[enemy],
    )
    set_unit_location(leader, 0.0, 0.0)
    set_unit_location(enemy, 2.0, 0.0)
    register_units_on_map(game, leader, enemy)

    melee_profile = simple_melee_profile(skill="4+", strength="4")
    attacker_model = leader.models[0]

    leader.apply_bionik_workshop_choice(branch_key="arms", source="Bionik Workshop", ability_key="bionik_workshop")
    wound_preview = melee_profile._wound_target_with_tracking(
        enemy,
        attacker_model,
        {"target_model": enemy.models[0]},
        roll_value=4,
    )
    assert any("+1S from Bionik Workshop" in mod for mod in list(wound_preview.get("modifiers", []) or []))

    leader.apply_bionik_workshop_choice(branch_key="bonce", source="Bionik Workshop", ability_key="bionik_workshop")
    hit_preview = melee_profile._hit_target_with_tracking(enemy, attacker_model, {}, preview_modifiers=True)
    assert any(value == 1 and "Bionik Workshop" in reason for value, reason in list(hit_preview.get("skill_mods", []) or []))
