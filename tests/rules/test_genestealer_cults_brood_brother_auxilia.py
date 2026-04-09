from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_MOVE_UNIT,
    DECISION_PICK_POINT,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.voice_of_command import VoiceOfCommandManager
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _DummyWargear:
    def __init__(self, name: str, *, ranged: bool = True):
        self.id = f"wg_{str(name).lower().replace(' ', '_')}_{id(self)}"
        self.name = str(name)
        self._ranged = bool(ranged)
        self.profiles = {}

    def is_ranged(self) -> bool:
        return bool(self._ranged)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        points: int = 100,
        leadership: int = 7,
        objective_control: int = 1,
        attached_to: list[str] | None = None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(points)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "2",
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    points: int = 100,
    possible_abilities: list[str] | None = None,
    leadership: int = 7,
    objective_control: int = 1,
    attached_to: list[str] | None = None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            points=points,
            leadership=leadership,
            objective_control=objective_control,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    if possible_abilities:
        unit.possible_abilities = list(possible_abilities)
    return unit


def _build_game(
    detachment: str = "Brood Brother Auxilia",
    *,
    points_limit: int = 2000,
) -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    gsc_army = Army.with_detachment("Genestealer Cults", detachment, points_limit=points_limit)
    gsc_army.faction_id = "GC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, gsc_army, enemy_army, p1, p2


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (0.2 * idx), float(y), 0.0, 0.0)


def _attach_ranged_weapons(unit: Unit, *, weapon_name: str) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.wargear = [_DummyWargear(weapon_name, ranged=True)]


def _apply_brood_brother_auxilia_enhancement(
    unit: Unit,
    *,
    enhancement_id: str,
    name: str,
    description: str,
) -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="GC",
        detachment="Brood Brother Auxilia",
        points=0,
        description=str(description),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _get_integrated_tactics_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == "integrated_tactics":
            return req
    return None


def _get_yes_no_request(game: Game, *, ability: str):
    target = str(ability or "").strip().lower()
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() == target:
            return req
    return None


def _target_option_id(request, target_unit: Unit | None) -> str:
    target_id = str(get_entity_id(target_unit) or "") if target_unit is not None else ""
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if target_unit is None:
            if str(payload.get("action", "") or "") == "skip":
                return str(getattr(opt, "option_id", "") or "")
            continue
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return str(getattr(opt, "option_id", "") or "")
    return ""


def _yes_no_option_id(request, *, use: bool) -> str:
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if bool(payload.get("choice", False)) == bool(use):
            return str(getattr(opt, "option_id", "") or "")
    return ""


def _pending_reaction_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _find_request(game: Game, *, decision_type: str, ability: str | None = None, reactive_move_kind: str | None = None):
    target_ability = str(ability or "").strip().lower()
    target_kind = str(reactive_move_kind or "").strip().lower()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type or ""):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if target_ability and str(context.get("ability", "") or "").strip().lower() != target_ability:
            continue
        if target_kind and str(context.get("reactive_move_kind", "") or "").strip().lower() != target_kind:
            continue
        return request
    return None


def _option_with_marker(request, *, relocation_mode: str | None = None, source_unit: Unit | None = None):
    target_mode = str(relocation_mode or "").strip().lower()
    source_id = str(get_entity_id(source_unit) or "") if source_unit is not None else ""
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        marker_id = str(payload.get("marker_id", "") or "").strip()
        if not marker_id:
            continue
        if target_mode and str(payload.get("relocation_mode", "") or "").strip().lower() != target_mode:
            continue
        if source_id and str(payload.get("source_unit_id", "") or "") != source_id:
            continue
        return option
    return None


def _make_ranged_profile(*, name: str = "Test Rifle", max_range: float = 24.0, blast: bool = False):
    parent = SimpleNamespace(
        name=str(name),
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    return SimpleNamespace(
        name=str(name),
        parent_wargear=parent,
        range=SimpleNamespace(max=float(max_range)),
        is_indirect_fire=lambda: False,
        is_torrent=lambda: False,
        is_blast=lambda: bool(blast),
        is_melee=lambda: False,
        is_pistol=lambda: False,
    )


def test_integrated_tactics_queues_optional_choice_and_skip_clears_source_lock():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 0

    source = _make_unit(
        "Brood Brothers Squad",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    target_one = _make_unit("Enemy One", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    target_two = _make_unit("Enemy Two", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(source)
    enemy_army.add_unit(target_one)
    enemy_army.add_unit(target_two)

    mgr = gsc_army.genestealer_cults_detachments
    mgr.integrated_tactics_target_candidates_for_unit = lambda *_args, **_kwargs: [target_one, target_two]
    mgr.integrated_tactics_target_eligible = lambda *_args, **_kwargs: True

    game._on_shooting_targets_selected_integrated_tactics(attacking_unit=source, target_units=[target_one, target_two])
    request = _get_integrated_tactics_request(game)
    assert request is not None
    assert bool((request.context or {}).get("optional")) is True
    assert str((request.context or {}).get("unit_id", "") or "") == str(get_entity_id(source) or "")

    target_option = _target_option_id(request, target_one)
    assert target_option
    resolve_decision_command(game, request, target_option, player_id=gsc_player.id)

    sr = dict(getattr(source, "special_rules", {}) or {})
    assert bool(sr.get("gsc_integrated_tactics_active")) is True
    assert str(sr.get("gsc_integrated_tactics_target_unit_id", "") or "") == str(get_entity_id(target_one) or "")

    game._on_shooting_targets_selected_integrated_tactics(attacking_unit=source, target_units=[target_one, target_two])
    request_skip = _get_integrated_tactics_request(game)
    assert request_skip is not None
    skip_option = _target_option_id(request_skip, None)
    assert skip_option
    resolve_decision_command(game, request_skip, skip_option, player_id=gsc_player.id)

    sr_after = dict(getattr(source, "special_rules", {}) or {})
    assert bool(sr_after.get("gsc_integrated_tactics_active")) is False
    assert str(sr_after.get("gsc_integrated_tactics_target_unit_id", "") or "") == ""


def test_integrated_tactics_target_lock_and_hit_bonus_apply_for_gsc_ranged_attacks():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 0

    source = _make_unit(
        "Brood Brothers Squad",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_attacker = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    locked_target = _make_unit("Locked Target", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    other_target = _make_unit("Other Target", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(source)
    gsc_army.add_unit(gsc_attacker)
    enemy_army.add_unit(locked_target)
    enemy_army.add_unit(other_target)

    mgr = gsc_army.genestealer_cults_detachments
    outcome = mgr.apply_integrated_tactics_choice(
        source,
        target_unit=locked_target,
        game=None,
        player=gsc_player,
    )
    assert isinstance(outcome, dict)
    assert bool(mgr.integrated_tactics_target_locked_to(source, locked_target, game=game)) is True
    assert bool(mgr.integrated_tactics_target_locked_to(source, other_target, game=game)) is False

    bonus, source_name = mgr.integrated_tactics_hit_bonus(gsc_attacker.models[0], locked_target, game=game)
    assert int(bonus or 0) == 1
    assert "integrated tactics" in str(source_name or "").lower()

    am_bonus, _am_source_name = mgr.integrated_tactics_hit_bonus(source.models[0], locked_target, game=game)
    assert int(am_bonus or 0) == 0

    melee_profile = SimpleNamespace(is_melee=lambda: True)
    melee_bonus, _ = mgr.integrated_tactics_hit_bonus(
        gsc_attacker.models[0],
        locked_target,
        game=game,
        weapon_profile=melee_profile,
    )
    assert int(melee_bonus or 0) == 0

    game._on_phase_end_cleanup(player=gsc_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    sr_after = dict(getattr(source, "special_rules", {}) or {})
    target_sr_after = dict(getattr(locked_target, "special_rules", {}) or {})
    assert bool(sr_after.get("gsc_integrated_tactics_active")) is False
    assert str(sr_after.get("gsc_integrated_tactics_target_unit_id", "") or "") == ""
    assert bool(target_sr_after.get("gsc_integrated_tactics_overlapping_fire_active")) is False


def test_brood_brothers_validation_enforces_cap_forbidden_units_and_warlord():
    game, gsc_army, enemy_army, _gsc_player, _enemy_player = _build_game(points_limit=1000)
    del game, enemy_army

    invalid_am_unit = _make_unit(
        "Brood Brothers Valkyrie",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "AIRCRAFT"],
        faction_keywords=["ASTRA MILITARUM"],
        points=600,
    )
    gsc_unit = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(invalid_am_unit)
    gsc_army.add_unit(gsc_unit)
    gsc_army.warlord = invalid_am_unit

    mgr = gsc_army.genestealer_cults_detachments
    errors = list(mgr.validate_detachment_rules() or [])
    text = "\n".join(str(msg or "") for msg in errors)
    assert "AIRCRAFT" in text
    assert "Incursion cap of 500" in text
    assert "must be your WARLORD" in text

    with pytest.raises(ArmyValidationError):
        gsc_army.validate_detachment_rules()


def test_brood_brothers_voice_of_command_loss_flags_units_and_disables_voice_check():
    _game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()

    officer = _make_unit(
        "Brood Brothers Commander",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "OFFICER", "INFANTRY"],
        faction_keywords=["ASTRA MILITARUM"],
        possible_abilities=["Voice of Command"],
    )
    gsc_unit = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(officer)
    gsc_army.add_unit(gsc_unit)
    gsc_army.warlord = gsc_unit

    sr = dict(getattr(officer, "special_rules", {}) or {})
    sr["voice_of_command_order_key"] = "test_order"
    sr["voice_of_command_order_owner"] = "owner"
    sr["voice_of_command_order_source"] = "source"
    officer.special_rules = sr
    removed_sources: list[str] = []
    officer.remove_characteristic_modifiers_by_source = lambda source: removed_sources.append(str(source or ""))

    voc = VoiceOfCommandManager(gsc_army)
    assert bool(voc._unit_has_voice(officer)) is True

    mgr = gsc_army.genestealer_cults_detachments
    mgr.apply_brood_brothers_voice_of_command_loss()
    updated_sr = dict(getattr(officer, "special_rules", {}) or {})

    assert bool(updated_sr.get("gsc_brood_brothers_voice_of_command_lost")) is True
    assert "voice_of_command_order_key" not in updated_sr
    assert "voice_of_command_order_owner" not in updated_sr
    assert "voice_of_command_order_source" not in updated_sr
    assert removed_sources == ["voice_of_command:"]
    assert bool(voc._unit_has_voice(officer)) is False


def test_adaptive_reprisal_allows_heroic_intervention_for_zero_cp_once_per_turn_within_range():
    game, gsc_army, _enemy_army, gsc_player, _enemy_player = _build_game()
    game.turn = 1

    bearer = _make_unit(
        "Patriarch",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    target = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(bearer)
    gsc_army.add_unit(target)
    _set_unit_position(bearer, 10.0, 10.0)
    _set_unit_position(target, 16.0, 10.0)

    _apply_brood_brother_auxilia_enhancement(
        bearer,
        enhancement_id="000009084003",
        name="Adaptive Reprisal",
        description=(
            "Once per turn, while the bearer is on the battlefield, you can target one friendly Genestealer Cults "
            "unit within 9\" of the bearer with the Heroic Intervention Stratagem for 0CP."
        ),
    )

    strat = SimpleNamespace(name="Heroic Intervention", cp_cost=1)
    preview = gsc_player.preview_stratagem_cp_cost(
        strat,
        target_unit=target,
        assume_optional_discounts=True,
    )
    assert int(preview.get("cost", -1)) == 0

    gsc_player.set_next_optional_decision("ADAPTIVE_REPRISAL_HEROIC_INTERVENTION", True)
    first = gsc_player.apply_stratagem_cp_cost(strat, target_unit=target)
    assert int(first.get("cost", -1)) == 0
    assert bool(first.get("adaptive_reprisal_heroic_intervention_use", False)) is True

    gsc_player.set_next_optional_decision("ADAPTIVE_REPRISAL_HEROIC_INTERVENTION", True)
    second = gsc_player.apply_stratagem_cp_cost(strat, target_unit=target)
    assert int(second.get("cost", -1)) == 1
    assert bool(second.get("adaptive_reprisal_heroic_intervention_use", False)) is False

    game.turn = 2
    preview_next_turn = gsc_player.preview_stratagem_cp_cost(
        strat,
        target_unit=target,
        assume_optional_discounts=True,
    )
    assert int(preview_next_turn.get("cost", -1)) == 0


def test_martial_espionage_queues_confirmation_and_applies_once_per_turn_owner():
    game, gsc_army, enemy_army, gsc_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 2
    game.current_player_index = 1

    bearer = _make_unit(
        "Primus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    astra_unit = _make_unit(
        "Brood Brothers Infantry",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "INFANTRY"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    enemy_target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    gsc_army.add_unit(bearer)
    gsc_army.add_unit(astra_unit)
    enemy_army.add_unit(enemy_target)
    _set_unit_position(bearer, 10.0, 10.0)
    _set_unit_position(astra_unit, 18.0, 10.0)
    _set_unit_position(enemy_target, 28.0, 10.0)
    _attach_ranged_weapons(astra_unit, weapon_name="Lasgun")

    _apply_brood_brother_auxilia_enhancement(
        bearer,
        enhancement_id="000009084002",
        name="Martial Espionage",
        description=(
            "Once per turn, when a friendly Astra Militarum Infantry or Astra Militarum Mounted unit within 9\" "
            "of the bearer is selected to shoot, the bearer can use this Enhancement. If it does, until the end "
            "of the phase, improve the Armour Penetration characteristic of ranged weapons equipped by models in "
            "that unit by 1."
        ),
    )

    game._on_shooting_targets_selected_martial_espionage(attacking_unit=astra_unit, target_units=[enemy_target])
    request = _get_yes_no_request(game, ability="martial_espionage")
    assert request is not None
    assert str((request.context or {}).get("player_id", "") or "") == ""
    assert str((request.context or {}).get("target_unit_id", "") or "") == str(get_entity_id(astra_unit) or "")
    assert str((request.context or {}).get("turn_owner", "") or "") == str(enemy_player.id or "")

    option_id = _yes_no_option_id(request, use=True)
    assert option_id
    result = resolve_decision_command(game, request, option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False))
    assert int(astra_unit.models[0].get_temporary_weapon_ap_bonus("Lasgun")[0] or 0) == 1

    game._on_shooting_targets_selected_martial_espionage(attacking_unit=astra_unit, target_units=[enemy_target])
    assert _get_yes_no_request(game, ability="martial_espionage") is None

    game.current_player_index = 0
    game._on_shooting_targets_selected_martial_espionage(attacking_unit=astra_unit, target_units=[enemy_target])
    request_next_owner = _get_yes_no_request(game, ability="martial_espionage")
    assert request_next_owner is not None
    assert str((request_next_owner.context or {}).get("turn_owner", "") or "") == str(gsc_player.id or "")


def test_the_hero_returned_improves_bearers_unit_stats_while_bearer_is_alive():
    _game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()

    bodyguard = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        leadership=7,
        objective_control=1,
    )
    leader = _make_unit(
        "Primus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
        leadership=6,
        objective_control=1,
        attached_to=[bodyguard.get_datasheet_id()],
    )
    gsc_army.add_unit(bodyguard)
    gsc_army.add_unit(leader)

    _apply_brood_brother_auxilia_enhancement(
        leader,
        enhancement_id="000009084004",
        name="The Hero Returned",
        description="Improve the Leadership and Objective Control characteristics of models in the bearer's unit by 1.",
    )

    leader_model = leader.models[0]
    assert int(leader.get_effective_model_characteristic(leader_model, "objective_control") or 0) == 2
    assert int(leader.get_effective_model_characteristic(leader_model, "leadership") or 0) == 5

    bodyguard_model = bodyguard.models[0]
    assert int(bodyguard.get_effective_model_characteristic(bodyguard_model, "objective_control") or 0) == 1
    assert int(bodyguard.get_effective_model_characteristic(bodyguard_model, "leadership") or 0) == 7

    leader.attach_to_unit(bodyguard)
    assert int(bodyguard.get_effective_model_characteristic(bodyguard_model, "objective_control") or 0) == 2
    assert int(bodyguard.get_effective_model_characteristic(bodyguard_model, "leadership") or 0) == 6

    leader.models[0].wounds = 0
    invalidate_leader = getattr(leader, "_invalidate_ability_cache", None)
    invalidate_bodyguard = getattr(bodyguard, "_invalidate_ability_cache", None)
    if callable(invalidate_leader):
        invalidate_leader()
    if callable(invalidate_bodyguard):
        invalidate_bodyguard()
    assert int(bodyguard.get_effective_model_characteristic(bodyguard_model, "objective_control") or 0) == 1
    assert int(bodyguard.get_effective_model_characteristic(bodyguard_model, "leadership") or 0) == 7


def test_firepoint_commander_sets_overwatch_threshold_to_five_while_bearer_lives():
    game, gsc_army, enemy_army, _gsc_player, _enemy_player = _build_game()

    bearer = _make_unit(
        "Primus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    gsc_army.add_unit(bearer)
    enemy_army.add_unit(enemy)
    _set_unit_position(bearer, 10.0, 10.0)
    _set_unit_position(enemy, 18.0, 10.0)

    _apply_brood_brother_auxilia_enhancement(
        bearer,
        enhancement_id="000009084005",
        name="Firepoint Commander",
        description=(
            "Each time you target the bearer's unit with the Fire Overwatch Stratagem, while resolving that "
            "Stratagem, hits are scored on unmodified Hit rolls of 5+."
        ),
    )

    assert int(bearer.get_destroyer_of_futures_overwatch_hit_threshold(enemy_unit=enemy, game=game) or 0) == 5

    bearer.models[0].wounds = 0
    invalidate = getattr(bearer, "_invalidate_ability_cache", None)
    if callable(invalidate):
        invalidate()
    assert int(bearer.get_destroyer_of_futures_overwatch_hit_threshold(enemy_unit=enemy, game=game) or 0) == 0


def test_suppress_and_overwhelm_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000009085004")
    assert desc is not None
    assert str(getattr(desc, "name", "") or "") == "SUPPRESS AND OVERWHELM"
    assert "overwatch" in str(getattr(desc, "effect", "") or "").lower()


def test_suppress_and_overwhelm_marks_enemy_for_overwatch_block_and_gsc_charge_reroll():
    game, gsc_army, enemy_army, gsc_player, enemy_player = _build_game(detachment="Brood Brother Auxilia")
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 0
    gsc_player.command_points = 5
    enemy_player.command_points = 5

    astra_shooter = _make_unit(
        "Brood Brothers Infantry",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "INFANTRY"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    gsc_charger = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy_target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    gsc_army.add_unit(astra_shooter)
    gsc_army.add_unit(gsc_charger)
    enemy_army.add_unit(enemy_target)
    _set_unit_position(astra_shooter, 10.0, 10.0)
    _set_unit_position(gsc_charger, 11.0, 10.0)
    _set_unit_position(enemy_target, 18.0, 10.0)
    gsc_army.configure_rule_managers(force=True)
    gsc_player.stratagems.refresh_available()
    enemy_player.stratagems.refresh_available()
    game.event_system.publish("phase_start", player=gsc_player, phase=game.phase)

    game.event_system.publish("unit_shooting_resolved", attacker_unit=astra_shooter, hits_by_target={enemy_target: 1})
    pending = _pending_reaction_by_name(gsc_player.stratagems, "SUPPRESS AND OVERWHELM")
    assert pending is not None

    used = gsc_player.stratagems.use(
        "SUPPRESS AND OVERWHELM",
        unit=astra_shooter,
        enemy_unit=enemy_target,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert bool(used) is True
    assert int(gsc_player.command_points or 0) == 4

    target_sr = dict(getattr(enemy_target, "special_rules", {}) or {})
    assert bool(target_sr.get("gsc_suppress_and_overwhelm_active")) is True

    assert bool(gsc_charger.can_reroll_charge_roll(target_unit=enemy_target, game=game, game_map=game.map)) is True
    assert bool(astra_shooter.can_reroll_charge_roll(target_unit=enemy_target, game=game, game_map=game.map)) is False

    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    can_use_overwatch = enemy_player.stratagems.can_use(
        "FIRE OVERWATCH",
        phase_name="Movement phase",
        shooter_unit=enemy_target,
        enemy_unit=gsc_charger,
    )
    assert bool(can_use_overwatch) is False
    assert bool(enemy_player.stratagems._is_overwatch_shooter_blocked_this_turn(enemy_target)) is True

    game.turn = 3
    assert bool(gsc_charger.can_reroll_charge_roll(target_unit=enemy_target, game=game, game_map=game.map)) is False


def test_brood_brother_auxilia_remaining_stratagem_descriptors_registered():
    expected = {
        "000009085007": ("A DARK NETWORK", "reactive_normal_move_up_to_6"),
        "000009085005": (
            "ACCEPTABLE LOSSES",
            "allow_ranged_attacks_against_selected_engaged_enemy_then_roll_self_mortals_for_each_engaged_gsc_unit",
        ),
        "000009085002": (
            "IN THE SHADOW OF IRON",
            "relocate_cult_ambush_marker_wholly_within_6_of_selected_vehicle",
        ),
        "000009085003": (
            "REGIMENTAL REINFORCEMENTS",
            "on_3_plus_add_identical_unit_to_cult_ambush_and_place_marker_if_possible",
        ),
        "000009085006": ("SYMBIOTIC DESTRUCTION", "lock_selected_units_to_enemy_and_reroll_wound_ones_against_it"),
    }

    for stratagem_id, (name, effect) in expected.items():
        desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_a_dark_network_queues_reaction_after_enemy_reserve_setup_and_use_queues_reactive_move():
    game, gsc_army, enemy_army, gsc_player, enemy_player = _build_game(detachment="Brood Brother Auxilia")
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 3

    reactor = _make_unit(
        "Brood Brothers Infantry",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "INFANTRY"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    enemy = _make_unit(
        "Enemy Reserves",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    gsc_army.add_unit(reactor)
    enemy_army.add_unit(enemy)
    _set_unit_position(reactor, 10.0, 10.0)
    _set_unit_position(enemy, 18.0, 10.0)
    game.map.units = [reactor, enemy]
    game.rebuild_entity_registry()
    gsc_army.configure_rule_managers(force=True)
    gsc_player.stratagems.refresh_available()
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)

    game.event_system.publish("unit_set_up", unit=enemy, set_up_as_reinforcements=True)
    pending = _pending_reaction_by_name(gsc_player.stratagems, "A DARK NETWORK")
    assert pending is not None

    used = gsc_player.stratagems.use(
        "A DARK NETWORK",
        unit=reactor,
        enemy_unit=enemy,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert bool(used) is True
    assert int(gsc_player.command_points or 0) == 2

    request = _find_request(
        game,
        decision_type=DECISION_MOVE_UNIT,
        reactive_move_kind="genestealer_cults_a_dark_network",
    )
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("unit_id", "") or "") == str(get_entity_id(reactor) or "")
    assert str(context.get("reactive_move_moving_unit_id", "") or "") == str(get_entity_id(enemy) or "")
    assert int(context.get("max_distance", 0) or 0) == 6


def test_in_the_shadow_of_iron_queues_relocation_option_and_relocates_marker():
    game, gsc_army, enemy_army, gsc_player, enemy_player = _build_game(detachment="Brood Brother Auxilia")
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 3

    vehicle = _make_unit(
        "Brood Brothers Chimera",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "VEHICLE"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(vehicle)
    enemy_army.add_unit(enemy)
    _set_unit_position(vehicle, 4.0, 0.0)
    _set_unit_position(enemy, 40.0, 0.0)
    game.map.units = [vehicle, enemy]
    game.rebuild_entity_registry()
    gsc_army.configure_rule_managers(force=True)
    gsc_player.stratagems.refresh_available()
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)

    cult_ambush = gsc_army.cult_ambush
    marker = cult_ambush.place_marker_at(game, 10.0, 0.0)
    assert marker is not None

    _set_unit_position(enemy, 18.0, 0.0)
    game.map.units = [vehicle, enemy]
    game.rebuild_entity_registry()

    cult_ambush.on_enemy_unit_move_ended(enemy, game=game)
    request = _find_request(
        game,
        decision_type=DECISION_PICK_POINT,
        ability="cult_ambush_threatened_marker_relocation",
    )
    assert request is not None
    option = _option_with_marker(
        request,
        relocation_mode="in_the_shadow_of_iron",
        source_unit=vehicle,
    )
    assert option is not None
    payload = dict(getattr(option, "payload", {}) or {})
    assert str(payload.get("source_unit_id", "") or "") == str(get_entity_id(vehicle) or "")

    result = resolve_decision_command(
        game,
        request,
        option.option_id,
        result_payload={"point": [3.0, 0.0]},
        player_id=gsc_player.id,
    )
    assert bool(getattr(result, "ok", False))
    active_markers = list(cult_ambush.get_active_markers() or [])
    assert len(active_markers) == 1
    relocated = active_markers[0]
    assert float(getattr(relocated, "x", -1.0) or -1.0) == 3.0
    assert float(getattr(relocated, "y", -1.0)) == 0.0
    assert int(gsc_player.command_points or 0) == 2


def test_regimental_reinforcements_clones_destroyed_unit_and_queues_marker_placement():
    game, gsc_army, enemy_army, gsc_player, enemy_player = _build_game(detachment="Brood Brother Auxilia")
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 4

    destroyed_unit = _make_unit(
        "Brood Brothers Squad",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "INFANTRY", "REGIMENT"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    enemy = _make_unit("Enemy Shooters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(destroyed_unit)
    enemy_army.add_unit(enemy)
    _set_unit_position(destroyed_unit, 5.0, 5.0)
    _set_unit_position(enemy, 40.0, 40.0)
    destroyed_models = list(getattr(destroyed_unit, "models", []) or [])
    for model in list(destroyed_models or []):
        model.wounds = 0
    destroyed_unit.models_lost = list(destroyed_models)
    destroyed_unit.models = []
    game.map.units = [destroyed_unit, enemy]
    game.rebuild_entity_registry()
    gsc_army.configure_rule_managers(force=True)
    gsc_player.stratagems.refresh_available()
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)

    game.event_system.publish("unit_destroyed", unit=destroyed_unit, destroyed_by_unit=enemy)
    pending = _pending_reaction_by_name(gsc_player.stratagems, "REGIMENTAL REINFORCEMENTS")
    assert pending is not None

    with patch("warhammer40k_ai.rules.stratagems_genestealer_cults.dice_module.get_roll", return_value=4):
        used = gsc_player.stratagems.use(
            "REGIMENTAL REINFORCEMENTS",
            unit=destroyed_unit,
            phase_name="Shooting phase",
            dequeue=True,
        )
    assert bool(used) is True
    assert bool(gsc_player.stratagems._used_once_per_battle.get("REGIMENTAL REINFORCEMENTS", False)) is True

    replacement_units = [
        unit
        for unit in list(gsc_army.units or [])
        if unit is not destroyed_unit and getattr(unit, "name", "") == getattr(destroyed_unit, "name", "")
    ]
    assert len(replacement_units) == 1
    replacement = replacement_units[0]
    assert bool(gsc_army.cult_ambush.unit_is_in_cult_ambush(replacement)) is True
    assert bool(replacement.is_alive()) is True

    request = _find_request(
        game,
        decision_type=DECISION_PICK_POINT,
        ability="regimental_reinforcements_marker_placement",
    )
    assert request is not None
    result = resolve_decision_command(
        game,
        request,
        request.options[0].option_id,
        result_payload={"point": [10.0, 10.0]},
        player_id=gsc_player.id,
    )
    assert bool(getattr(result, "ok", False))
    active_markers = list(gsc_army.cult_ambush.get_active_markers() or [])
    assert len(active_markers) == 1


def test_acceptable_losses_allows_selected_engaged_target_and_applies_post_shoot_mortals():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game(detachment="Brood Brother Auxilia")
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 0
    gsc_player.command_points = 4

    astra_shooter = _make_unit(
        "Brood Brothers Squad",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "INFANTRY"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    engaged_gsc_one = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    engaged_gsc_two = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy_target = _make_unit("Enemy Target", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    other_enemy = _make_unit("Other Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(astra_shooter)
    gsc_army.add_unit(engaged_gsc_one)
    gsc_army.add_unit(engaged_gsc_two)
    enemy_army.add_unit(enemy_target)
    enemy_army.add_unit(other_enemy)
    _attach_ranged_weapons(astra_shooter, weapon_name="Lasgun")
    _set_unit_position(astra_shooter, 2.0, 10.0)
    _set_unit_position(engaged_gsc_one, 10.0, 10.0)
    _set_unit_position(engaged_gsc_two, 10.0, 10.8)
    _set_unit_position(enemy_target, 10.6, 10.0)
    _set_unit_position(other_enemy, 16.0, 10.0)
    game.map.units = [astra_shooter, engaged_gsc_one, engaged_gsc_two, enemy_target, other_enemy]
    game.rebuild_entity_registry()
    gsc_army.configure_rule_managers(force=True)
    gsc_player.stratagems.refresh_available()
    game.event_system.publish("phase_start", player=gsc_player, phase=game.phase)

    profile = _make_ranged_profile()
    assert bool(
        astra_shooter._can_model_shoot_weapon_at_target(
            astra_shooter.models[0],
            profile,
            enemy_target,
            game.map,
        )
    ) is False

    recorded_mortals: dict[str, int] = {}

    def _record_mortals(target_unit, mortal_wound_amount, **_kwargs):
        recorded_mortals[str(get_entity_id(target_unit) or "")] = int(mortal_wound_amount or 0)

    astra_shooter._apply_mortal_wounds_to_unit = _record_mortals

    used = gsc_player.stratagems.use(
        "ACCEPTABLE LOSSES",
        unit=astra_shooter,
        enemy_unit=enemy_target,
        phase_name="Shooting phase",
    )
    assert bool(used) is True
    assert bool(
        astra_shooter._can_model_shoot_weapon_at_target(
            astra_shooter.models[0],
            profile,
            enemy_target,
            game.map,
        )
    ) is True

    with patch("warhammer40k_ai.rules.stratagems_genestealer_cults.dice_module.get_roll", side_effect=[5, 2, 5, 1]):
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=astra_shooter,
            declared_targets=[enemy_target],
        )

    assert set(recorded_mortals.keys()) == {
        str(get_entity_id(engaged_gsc_one) or ""),
        str(get_entity_id(engaged_gsc_two) or ""),
    }
    assert sorted(recorded_mortals.values()) == [2, 3]


def test_symbiotic_destruction_target_locks_units_and_grants_wound_reroll_ones():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game(detachment="Brood Brother Auxilia")
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 0
    gsc_player.command_points = 4

    astra_unit = _make_unit(
        "Brood Brothers Squad",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "INFANTRY"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    gsc_unit = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    locked_enemy = _make_unit("Locked Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    other_enemy = _make_unit("Other Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(astra_unit)
    gsc_army.add_unit(gsc_unit)
    enemy_army.add_unit(locked_enemy)
    enemy_army.add_unit(other_enemy)
    _set_unit_position(astra_unit, 0.0, 0.0)
    _set_unit_position(gsc_unit, 2.0, 0.0)
    _set_unit_position(locked_enemy, 10.0, 0.0)
    _set_unit_position(other_enemy, 12.0, 6.0)
    _attach_ranged_weapons(astra_unit, weapon_name="Lasgun")
    _attach_ranged_weapons(gsc_unit, weapon_name="Autogun")
    game.map.units = [astra_unit, gsc_unit, locked_enemy, other_enemy]
    game.rebuild_entity_registry()

    used = gsc_player.stratagems.use(
        "SYMBIOTIC DESTRUCTION",
        phase_name="Shooting phase",
        astra_unit=astra_unit,
        gsc_unit=gsc_unit,
        enemy_unit=locked_enemy,
    )
    assert bool(used) is True

    profile = _make_ranged_profile()
    for shooter in (astra_unit, gsc_unit):
        assert bool(
            shooter._can_model_shoot_weapon_at_target(
                shooter.models[0],
                profile,
                locked_enemy,
                game.map,
            )
        ) is True
        assert bool(
            shooter._can_model_shoot_weapon_at_target(
                shooter.models[0],
                profile,
                other_enemy,
                game.map,
            )
        ) is False

        wound_mods = shooter.get_unit_wound_reroll_modifiers("ranged", target=locked_enemy)
        assert bool(wound_mods.get("reroll_wound_ones", False)) is True
        assert any(
            "SYMBIOTIC DESTRUCTION" in str(reason or "")
            for reason in list(wound_mods.get("reroll_wound_reasons", ()) or ())
        )
