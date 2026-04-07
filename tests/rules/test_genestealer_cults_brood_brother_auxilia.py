from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO
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
        self.name = str(name)
        self._ranged = bool(ranged)

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
