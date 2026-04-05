from __future__ import annotations

import uuid
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.utility.decision_utils import resolve_decision_command

from tests.orks_enhancement_test_utils import alive_wounds, build_game, make_unit


class _DummyWargear:
    def __init__(self, name: str, *, ranged: bool = True):
        self._id = str(uuid.uuid4())
        self.name = name
        self._ranged = bool(ranged)

    def is_ranged(self) -> bool:
        return bool(self._ranged)


def _attach_ranged_weapons(unit, *, weapon_name: str) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.wargear = [_DummyWargear(weapon_name, ranged=True)]


def _find_yes_no_request(game, *, ability: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "").strip().lower() == str(ability or "").strip().lower():
            return request
    return None


def _resolve_yes_no(game, request, player, *, use: bool) -> None:
    option_id = None
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if bool(payload.get("choice", False)) == bool(use):
            option_id = option.option_id
            break
    assert option_id is not None
    outcome = resolve_decision_command(game, request, option_id, player_id=player.id)
    assert bool(getattr(outcome, "ok", False))


def _shooty_power_trip_ability() -> Ability:
    return Ability(
        "Shooty Power Trip",
        "ORK",
        (
            "Each time this unit is selected to shoot, you can roll one D6: "
            "- On a 1-2, this unit suffers D3 mortal wounds. "
            "- On a 3-4, until the end of the phase, add 1 to the Strength characteristic of ranged weapons equipped by models in this unit. "
            "- On a 5-6, until the end of the phase, add 1 to the Attacks characteristic of ranged weapons equipped by models in this unit."
        ),
        "Datasheet",
        "",
    )


def _pulsa_rokkit_ability() -> Ability:
    return Ability(
        "Pulsa Rokkit",
        "ORK",
        (
            "Once per battle, when the bearer's unit is selected to shoot in your Shooting phase, "
            "the bearer can use its pulsa rokkit. If it does, until the end of the phase, improve the Strength "
            "and Armour Penetration characteristics of ranged weapons equipped by models in the bearer's unit by 1."
        ),
        "Wargear",
        "",
    )


def test_selected_to_shoot_try_dat_button_roll_count_requires_alive_press_it_fasta_bearer():
    mek = make_unit(
        "Mek",
        "orks-selected-to-shoot-press-roll-count",
        keywords=["CHARACTER", "INFANTRY", "MEK"],
        faction_keywords=["ORKS"],
    )
    bearer = mek.models[0]
    mek.special_rules["enhancement_press_it_fasta"] = True
    mek.special_rules["enhancement_press_it_fasta_extra_rolls"] = 1
    mek.special_rules["enhancement_press_it_fasta_bearer_model_id"] = str(bearer.id)

    assert mek.selected_to_shoot_try_dat_button_roll_count(trigger="shooting") == 2
    assert mek.selected_to_shoot_try_dat_button_roll_count(trigger="fight") == 1

    bearer.wounds = 0
    assert mek.selected_to_shoot_try_dat_button_roll_count(trigger="shooting") == 1


def test_selected_to_shoot_shared_ranged_bonus_helper_applies_and_expires():
    kans = make_unit(
        "Killa Kans",
        "orks-selected-to-shoot-shared-bonus",
        keywords=["VEHICLE", "WALKER"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    _attach_ranged_weapons(kans, weapon_name="Rokkit Launcha")

    applied = kans.apply_selected_to_shoot_unit_ranged_weapon_bonuses(
        key_prefix="selected_to_shoot:test",
        source="Selected To Shoot Test",
        attacks_bonus=1,
        strength_bonus=1,
        ap_bonus=1,
    )

    assert applied == 2
    for model in list(kans.models or []):
        assert model.get_temporary_weapon_attacks_bonus("Rokkit Launcha")[0] == 1
        assert model.get_temporary_weapon_strength_bonus("Rokkit Launcha")[0] == 1
        assert model.get_temporary_weapon_ap_bonus("Rokkit Launcha")[0] == 1
        model.on_phase_end(BattleRoundPhases.SHOOTING_PHASE)
        assert model.get_temporary_weapon_attacks_bonus("Rokkit Launcha")[0] == 0
        assert model.get_temporary_weapon_strength_bonus("Rokkit Launcha")[0] == 0
        assert model.get_temporary_weapon_ap_bonus("Rokkit Launcha")[0] == 0


def test_selected_to_shoot_utilities_do_not_queue_outside_shooting_phase():
    kans = make_unit(
        "Killa Kans",
        "orks-selected-to-shoot-wrong-phase-kans",
        keywords=["VEHICLE", "WALKER"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    kans.possible_abilities = [_shooty_power_trip_ability()]
    _attach_ranged_weapons(kans, weapon_name="Grotzooka")

    tankbustas = make_unit(
        "Tankbustas",
        "orks-selected-to-shoot-wrong-phase-tankbustas",
        keywords=["INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    tankbustas.possible_abilities = [_pulsa_rokkit_ability()]
    _attach_ranged_weapons(tankbustas, weapon_name="Rokkit Launcha")
    tankbustas.models[0].optional_wargear.append("Pulsa Rokkit")

    enemy = make_unit(
        "Enemy Unit",
        "enemy-selected-to-shoot-wrong-phase",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, _ork_player, _enemy_player, _ork_army, _enemy_army = build_game(
        detachment="Other",
        ork_units=[kans, tankbustas],
        enemy_units=[enemy],
    )
    game.phase = BattleRoundPhases.COMMAND_PHASE

    game._on_shooting_targets_selected_orks_selected_to_shoot_utilities(attacking_unit=kans, target_units=[enemy])
    game._on_shooting_targets_selected_orks_selected_to_shoot_utilities(attacking_unit=tankbustas, target_units=[enemy])

    assert _find_yes_no_request(game, ability="shooty_power_trip") is None
    assert _find_yes_no_request(game, ability="pulsa_rokkit") is None


def test_shooty_power_trip_e2e_self_mortal_branch():
    kans = make_unit(
        "Killa Kans",
        "orks-selected-to-shoot-shooty-mortals",
        keywords=["VEHICLE", "WALKER"],
        faction_keywords=["ORKS"],
        model_count=1,
    )
    kans.possible_abilities = [_shooty_power_trip_ability()]
    _attach_ranged_weapons(kans, weapon_name="Grotzooka")
    enemy = make_unit(
        "Enemy Unit",
        "enemy-selected-to-shoot-shooty-mortals",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, _ork_army, _enemy_army = build_game(
        detachment="Other",
        ork_units=[kans],
        enemy_units=[enemy],
    )
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    wounds_before = alive_wounds(kans)
    game._on_shooting_targets_selected_orks_selected_to_shoot_utilities(attacking_unit=kans, target_units=[enemy])
    request = _find_yes_no_request(game, ability="shooty_power_trip")
    assert request is not None

    with patch("warhammer40k_ai.units.unit_mixins.selected_to_shoot_mixin.get_roll", side_effect=[1, 2]):
        _resolve_yes_no(game, request, ork_player, use=True)

    assert alive_wounds(kans) == wounds_before - 2
    for model in list(kans.models or []):
        assert model.get_temporary_weapon_strength_bonus("Grotzooka")[0] == 0
        assert model.get_temporary_weapon_attacks_bonus("Grotzooka")[0] == 0


def test_shooty_power_trip_e2e_buff_branch_expires_at_end_of_phase():
    kans = make_unit(
        "Killa Kans",
        "orks-selected-to-shoot-shooty-buff",
        keywords=["VEHICLE", "WALKER"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    kans.possible_abilities = [_shooty_power_trip_ability()]
    _attach_ranged_weapons(kans, weapon_name="Big Shoota")
    enemy = make_unit(
        "Enemy Unit",
        "enemy-selected-to-shoot-shooty-buff",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, _ork_army, _enemy_army = build_game(
        detachment="Other",
        ork_units=[kans],
        enemy_units=[enemy],
    )
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    wounds_before = alive_wounds(kans)
    game._on_shooting_targets_selected_orks_selected_to_shoot_utilities(attacking_unit=kans, target_units=[enemy])
    request = _find_yes_no_request(game, ability="shooty_power_trip")
    assert request is not None

    with patch("warhammer40k_ai.units.unit_mixins.selected_to_shoot_mixin.get_roll", return_value=5):
        _resolve_yes_no(game, request, ork_player, use=True)

    assert alive_wounds(kans) == wounds_before
    for model in list(kans.models or []):
        assert model.get_temporary_weapon_attacks_bonus("Big Shoota")[0] == 1
        assert model.get_temporary_weapon_strength_bonus("Big Shoota")[0] == 0
        model.on_phase_end(BattleRoundPhases.SHOOTING_PHASE)
        assert model.get_temporary_weapon_attacks_bonus("Big Shoota")[0] == 0


def test_pulsa_rokkit_e2e_once_per_battle_gating_and_expiry():
    tankbustas = make_unit(
        "Tankbustas",
        "orks-selected-to-shoot-pulsa",
        keywords=["INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    tankbustas.possible_abilities = [_pulsa_rokkit_ability()]
    _attach_ranged_weapons(tankbustas, weapon_name="Rokkit Launcha")
    bearer = tankbustas.models[0]
    bearer.optional_wargear.append("Pulsa Rokkit")

    enemy = make_unit(
        "Enemy Unit",
        "enemy-selected-to-shoot-pulsa",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, _ork_army, _enemy_army = build_game(
        detachment="Other",
        ork_units=[tankbustas],
        enemy_units=[enemy],
    )
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    game._on_shooting_targets_selected_orks_selected_to_shoot_utilities(attacking_unit=tankbustas, target_units=[enemy])
    request = _find_yes_no_request(game, ability="pulsa_rokkit")
    assert request is not None

    _resolve_yes_no(game, request, ork_player, use=True)

    assert bearer.has_used_once_per_battle("pulsa_rokkit")
    for model in list(tankbustas.models or []):
        assert model.get_temporary_weapon_strength_bonus("Rokkit Launcha")[0] == 1
        assert model.get_temporary_weapon_ap_bonus("Rokkit Launcha")[0] == 1
        model.on_phase_end(BattleRoundPhases.SHOOTING_PHASE)
        assert model.get_temporary_weapon_strength_bonus("Rokkit Launcha")[0] == 0
        assert model.get_temporary_weapon_ap_bonus("Rokkit Launcha")[0] == 0

    game._on_shooting_targets_selected_orks_selected_to_shoot_utilities(attacking_unit=tankbustas, target_units=[enemy])
    assert _find_yes_no_request(game, ability="pulsa_rokkit") is None
