import copy
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET,
    DECISION_CHOOSE_QUARRY,
    DECISION_SELECT_TARGET_MODEL,
)
from warhammer40k_ai.engine.decisions import DecisionOption
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.ability_usage import START_ANY_PHASE_BATTLESHOCK_CLEAR_TURN_USAGE, current_player_turn_key
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


GUNG_HO_COMMAND_TEXT = (
    "While this unit contains an OFFICER, ranged weapons equipped by models in this unit have the [ASSAULT] ability."
)

BRING_IT_DOWN_TEXT = (
    "Each time a model in this unit makes a ranged attack that targets a MONSTER of VEHICLE unit, re-roll a Hit roll "
    "of 1 and re-roll a Wound roll of 1."
)

JUNGLE_FIGHTERS_TEXT = (
    "Each time a model in this unit makes a melee attack, if this unit made a Charge move or was charged this turn, "
    "add 1 to the Wound roll."
)

POLITICAL_OVERWATCH_TEXT = (
    "While another OFFICER model is in this unit, you can re-roll Battle-shock tests taken for this unit."
)

SUMMARY_EXECUTION_TEXT = (
    "Once per battle round, at the start of any phase, you can select one friendly Astra Militarum Infantry unit "
    "that is Battle-shocked and within 12\" of this model. If you do, one model in that unit is destroyed, and that "
    "unit is then no longer Battle-shocked."
)

BRUTAL_DISCIPLINARIAN_ON_FOOT_TEXT = (
    "Once per phase, at the start of any phase, you can select one friendly Astra Militarum Infantry "
    "(excluding units that only contain one model) unit that is Battle-shocked and within 12\" of this model. "
    "If you do, one model in that unit is destroyed, and that unit is no longer Battle-shocked."
)

BRUTAL_DISCIPLINARIAN_MOUNTED_TEXT = (
    "Once per turn, at the start of any phase, you can select one friendly Astra Militarum Infantry unit "
    "(excluding units that only contain one model) that is Battle-shocked and within 24\" of and visible to this "
    "model. If you do, one model in that unit is destroyed, and that unit is no longer Battle-shocked."
)

AQUILINE_PROW_TEXT = (
    "Each time this unit ends a Charge move, you can select one enemy unit within Engagement Range of it, "
    "then roll one D6: on a 2-3, that enemy unit suffers D3 mortal wounds; on a 4-5, that enemy unit suffers "
    "3 mortal wounds; on a 6, that enemy unit suffers D3+3 mortal wounds."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        attached_to=None,
        datasheet_id: str | None = None,
        save: int = 4,
        move: int = 6,
        wounds: int = 2,
        leadership: int = 7,
        objective_control: int = 1,
        base_size: str = "32mm",
    ):
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(move)),
                "T": "4",
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(
    name: str,
    *,
    x: float = 0.0,
    y: float = 0.0,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    attached_to=None,
    datasheet_id: str | None = None,
    save: int = 4,
    move: int = 6,
    wounds: int = 2,
    leadership: int = 7,
    objective_control: int = 1,
    base_size: str = "32mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
            datasheet_id=datasheet_id,
            save=save,
            move=move,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
            base_size=base_size,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army.with_detachment("Astra Militarum", detachment_type="Combined Regiment")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    am_player = Player("AM", PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    return game, am_army, enemy_army, am_player, enemy_player


def _ranged_profile() -> WargearProfile:
    return WargearProfile(
        "default",
        {"range": "24", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""},
        parent_wargear=SimpleNamespace(name="Test Rifle", is_ranged=lambda: True, is_melee=lambda: False),
    )


def _add_extra_model(unit: Unit, name: str, *, x: float, y: float) -> Model:
    prototype = unit.models[0]
    model = Model(
        name=name,
        movement=int(getattr(prototype, "_base_movement", 6) or 6),
        toughness=int(getattr(prototype, "_base_toughness", 4) or 4),
        save=int(getattr(prototype, "_base_save", 4) or 4),
        wounds=int(getattr(prototype, "_base_wounds", 1) or 1),
        leadership=int(getattr(prototype, "_base_leadership", 7) or 7),
        objective_control=int(getattr(prototype, "_base_objective_control", 1) or 1),
        model_base=copy.deepcopy(getattr(prototype, "model_base", Base(BaseType.CIRCULAR, 1.0))),
        inv_save=getattr(prototype, "_inv_save", None),
        inv_save_condition=getattr(prototype, "_inv_save_condition", None),
        keywords=list(getattr(prototype, "keywords", []) or []),
        faction_keywords=list(getattr(prototype, "faction_keywords", []) or []),
    )
    model.parent_unit = unit
    model.set_location(float(x), float(y), 0.0, 0.0)
    unit.models.append(model)
    return model


def _result_errors(result) -> list:
    errors = list(getattr(result, "errors", []) or [])
    value = getattr(result, "value", None)
    if value is not None:
        errors.extend(list(getattr(value, "errors", []) or []))
    return errors


def test_gung_ho_command_requires_officer_model_for_assault_ranged():
    squad = _make_unit(
        "Catachan Command Squad",
        datasheet_id="catachan-command-squad",
        abilities=[{"name": "Gung-ho Command", "description": GUNG_HO_COMMAND_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "REGIMENT", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    officer = _make_unit(
        "Officer",
        abilities=[],
        keywords=["OFFICER", "CHARACTER", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        attached_to=["catachan-command-squad"],
    )
    officer.attached_to = squad
    officer.can_be_attached_to = ["catachan-command-squad"]
    squad.attached_leaders = [officer]
    squad._refresh_bearer_unit_common_modifiers()

    no_officer = _make_unit(
        "Catachan Command Squad 2",
        datasheet_id="catachan-command-squad-2",
        abilities=[{"name": "Gung-ho Command", "description": GUNG_HO_COMMAND_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "REGIMENT", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )

    ranged = _ranged_profile()
    assert bool(squad.can_shoot_after_advance(ranged)) is True
    assert bool(no_officer.can_shoot_after_advance(ranged)) is False


def test_bring_it_down_supports_wahapedia_vehicle_typo():
    unit = _make_unit(
        "Catachan Heavy Weapons Squad",
        abilities=[{"name": "Bring it Down!", "description": BRING_IT_DOWN_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    target = _make_unit(
        "Enemy Tank",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        wounds=12,
    )

    hit_mods = unit.get_unit_hit_reroll_modifiers("ranged", target=target, attacker_model=unit.models[0])
    wound_mods = unit.get_unit_wound_reroll_modifiers("ranged", target=target, attacker_model=unit.models[0])

    assert tuple(hit_mods.get("reroll_hit_values", ())) == (1,)
    assert tuple(wound_mods.get("reroll_wound_values", ())) == (1,)


def test_jungle_fighters_applies_when_charging_or_charged():
    unit = _make_unit(
        "Catachan Jungle Fighters",
        abilities=[{"name": "Jungle Fighters", "description": JUNGLE_FIGHTERS_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    target = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    unit.round_state.charged_this_round = True
    charged_mods = unit.model_attack_roll_modifiers_vs_weakened_target(
        unit.models[0],
        attack_type="melee",
        target=target,
    )
    assert int(charged_mods.get("wound", 0) or 0) == 1

    unit.round_state.charged_this_round = False
    unit.round_state.was_charged_this_round = True
    was_charged_mods = unit.model_attack_roll_modifiers_vs_weakened_target(
        unit.models[0],
        attack_type="melee",
        target=target,
    )
    assert int(was_charged_mods.get("wound", 0) or 0) == 1


def test_political_overwatch_requires_another_officer_model():
    bodyguard = _make_unit(
        "Infantry Bodyguard",
        datasheet_id="bodyguard-officer",
        keywords=["INFANTRY", "OFFICER", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    commissar = _make_unit(
        "Commissar",
        abilities=[{"name": "Political Overwatch", "description": POLITICAL_OVERWATCH_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["CHARACTER", "OFFICER", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        attached_to=["bodyguard-officer"],
    )
    commissar.attached_to = bodyguard
    commissar.can_be_attached_to = ["bodyguard-officer"]
    bodyguard.attached_leaders = [commissar]
    bodyguard._invalidate_ability_cache()
    assert "Political Overwatch" in list(bodyguard.leading_leadership_reroll_sources() or [])

    no_other_officer = _make_unit(
        "Infantry Bodyguard 2",
        datasheet_id="bodyguard-no-officer",
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    lone_commissar = _make_unit(
        "Commissar 2",
        abilities=[{"name": "Political Overwatch", "description": POLITICAL_OVERWATCH_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["CHARACTER", "OFFICER", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        attached_to=["bodyguard-no-officer"],
    )
    lone_commissar.attached_to = no_other_officer
    lone_commissar.can_be_attached_to = ["bodyguard-no-officer"]
    no_other_officer.attached_leaders = [lone_commissar]
    no_other_officer._invalidate_ability_cache()
    assert list(no_other_officer.leading_leadership_reroll_sources() or []) == []


def test_summary_execution_destroys_selected_model_and_clears_battleshock_once_per_round():
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()
    source = _make_unit(
        "Commissar",
        x=0.0,
        y=0.0,
        abilities=[{"name": "Summary Execution", "description": SUMMARY_EXECUTION_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["CHARACTER", "OFFICER", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    target = _make_unit(
        "Catachan Jungle Fighters",
        x=4.0,
        y=0.0,
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    extra_model = _add_extra_model(target, "Extra Fighter", x=4.5, y=0.0)
    target.apply_status_effect(BattleShockEffect(game.turn))

    am_army.add_unit(source)
    am_army.add_unit(target)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    game._on_phase_start_optional_abilities(player=am_player, phase=game.phase)
    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
    ]
    assert len(requests) == 1
    clear_request = requests[0]
    ability_key = str((clear_request.context or {}).get("ability_key", "") or "")

    target_option = next(
        option
        for option in list(clear_request.options or [])
        if str((option.payload or {}).get("unit_id", "") or "") == str(get_entity_id(target) or "")
    )
    apply_result = resolve_decision_command(game, clear_request, target_option.option_id, player_id=am_player.id)
    assert bool(getattr(apply_result, "ok", False))

    destroy_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_TARGET_MODEL
        and str((getattr(req, "context", {}) or {}).get("selection_kind", "") or "") == "battleshock_clear_destroy_model"
    ]
    assert len(destroy_requests) == 1
    destroy_request = destroy_requests[0]
    destroy_option = next(
        option
        for option in list(destroy_request.options or [])
        if str((option.payload or {}).get("model_id", "") or "") == str(get_entity_id(extra_model) or "")
    )
    destroy_result = resolve_decision_command(game, destroy_request, destroy_option.option_id, player_id=am_player.id)
    assert bool(getattr(destroy_result, "ok", False))

    assert extra_model not in list(target.models or [])
    assert bool(target.is_battle_shocked()) is False
    assert bool(source.models[0].has_used_once_per_battle_round(ability_key, battle_round=game.turn)) is True

    target.apply_status_effect(BattleShockEffect(game.turn))
    game._on_phase_start_optional_abilities(player=am_player, phase=game.phase)
    repeated_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
    ]
    assert repeated_requests == []


def test_brutal_disciplinarian_on_foot_is_once_per_phase_and_excludes_single_model_targets():
    game, am_army, _enemy_army, am_player, _enemy_player = _build_game()
    source = _make_unit(
        "Commissar Graves on Foot",
        x=0.0,
        y=0.0,
        abilities=[
            {
                "name": "Brutal Disciplinarian",
                "description": BRUTAL_DISCIPLINARIAN_ON_FOOT_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["CHARACTER", "OFFICER", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    target = _make_unit(
        "Cadian Shock Troops",
        x=4.0,
        y=0.0,
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    first_extra = _add_extra_model(target, "First Trooper", x=4.5, y=0.0)
    second_extra = _add_extra_model(target, "Second Trooper", x=5.0, y=0.0)
    lone_target = _make_unit(
        "Lone Operative",
        x=6.0,
        y=0.0,
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    target.apply_status_effect(BattleShockEffect(game.turn))
    lone_target.apply_status_effect(BattleShockEffect(game.turn))

    am_army.add_unit(source)
    am_army.add_unit(target)
    am_army.add_unit(lone_target)
    game.map.units = [source, target, lone_target]
    game.rebuild_entity_registry()

    specs = source.unit_start_any_phase_clear_battleshock_specs()
    assert specs
    assert bool(specs[0]["once_per_phase"]) is True
    assert bool(specs[0]["exclude_single_model_units"]) is True

    game._on_phase_start_optional_abilities(player=am_player, phase=game.phase)
    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
    ]
    assert len(requests) == 1
    clear_request = requests[0]
    candidate_ids = {str(value) for value in list((clear_request.context or {}).get("candidate_unit_ids", []) or [])}
    assert str(get_entity_id(target)) in candidate_ids
    assert str(get_entity_id(lone_target)) not in candidate_ids

    invalid_option = DecisionOption.create("Lone Operative", payload={"unit_id": get_entity_id(lone_target)})
    clear_request.options.append(invalid_option)
    clear_request.context.setdefault("candidate_unit_ids", []).append(get_entity_id(lone_target))
    clear_request.candidates = []
    clear_request.mask = []
    clear_request.mask_reasons = []
    clear_request.finalize_candidates()
    invalid = resolve_decision_command(game, clear_request, invalid_option.option_id, player_id=am_player.id)
    assert not bool(getattr(invalid, "ok", False))
    assert any("more than one model" in str(err).lower() for err in _result_errors(invalid))
    clear_request.context["candidate_unit_ids"].remove(get_entity_id(lone_target))

    target_option = next(
        option
        for option in list(clear_request.options or [])
        if str((option.payload or {}).get("unit_id", "") or "") == str(get_entity_id(target) or "")
    )
    apply_result = resolve_decision_command(game, clear_request, target_option.option_id, player_id=am_player.id)
    assert bool(getattr(apply_result, "ok", False)), str(getattr(apply_result, "errors", ()))

    destroy_request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_TARGET_MODEL
        and str((getattr(req, "context", {}) or {}).get("selection_kind", "") or "") == "battleshock_clear_destroy_model"
    )
    destroy_option = next(
        option
        for option in list(destroy_request.options or [])
        if str((option.payload or {}).get("model_id", "") or "") == str(get_entity_id(first_extra) or "")
    )
    destroy_result = resolve_decision_command(game, destroy_request, destroy_option.option_id, player_id=am_player.id)
    assert bool(getattr(destroy_result, "ok", False)), str(getattr(destroy_result, "errors", ()))
    assert first_extra not in list(target.models or [])
    assert bool(target.is_battle_shocked()) is False

    target.apply_status_effect(BattleShockEffect(game.turn))
    game._on_phase_start_optional_abilities(player=am_player, phase=game.phase)
    same_phase_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
    ]
    assert same_phase_requests == []

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game._on_phase_start_optional_abilities(player=am_player, phase=game.phase)
    next_phase_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
    ]
    assert len(next_phase_requests) == 1
    assert second_extra in list(target.models or [])


def test_brutal_disciplinarian_mounted_requires_visibility_and_is_once_per_turn():
    game, am_army, _enemy_army, am_player, _enemy_player = _build_game()
    source = _make_unit(
        "Commissar Graves",
        x=0.0,
        y=0.0,
        abilities=[
            {
                "name": "Brutal Disciplinarian",
                "description": BRUTAL_DISCIPLINARIAN_MOUNTED_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["VEHICLE", "SQUADRON", "OFFICER", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    visible_target = _make_unit(
        "Visible Catachans",
        x=10.0,
        y=0.0,
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    hidden_target = _make_unit(
        "Hidden Catachans",
        x=12.0,
        y=0.0,
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    visible_extra = _add_extra_model(visible_target, "Visible Extra", x=10.5, y=0.0)
    _add_extra_model(visible_target, "Second Visible Extra", x=11.0, y=0.0)
    _add_extra_model(hidden_target, "Hidden Extra", x=12.5, y=0.0)
    visible_target.apply_status_effect(BattleShockEffect(game.turn))
    hidden_target.apply_status_effect(BattleShockEffect(game.turn))

    am_army.add_unit(source)
    am_army.add_unit(visible_target)
    am_army.add_unit(hidden_target)
    game.map.units = [source, visible_target, hidden_target]
    game.rebuild_entity_registry()

    visible_ids = {
        str(get_entity_id(model) or "")
        for model in list(visible_target.get_attached_unit_models() or [])
        if str(get_entity_id(model) or "")
    }
    game.map.can_model_see_model = lambda _source_model, target_model: str(get_entity_id(target_model) or "") in visible_ids

    specs = source.unit_start_any_phase_clear_battleshock_specs()
    assert specs
    assert bool(specs[0]["once_per_turn"]) is True
    assert bool(specs[0]["requires_visibility"]) is True

    game._on_phase_start_optional_abilities(player=am_player, phase=game.phase)
    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
    ]
    assert len(requests) == 1
    clear_request = requests[0]
    candidate_ids = {str(value) for value in list((clear_request.context or {}).get("candidate_unit_ids", []) or [])}
    assert str(get_entity_id(visible_target)) in candidate_ids
    assert str(get_entity_id(hidden_target)) not in candidate_ids

    invalid_option = DecisionOption.create("Hidden Catachans", payload={"unit_id": get_entity_id(hidden_target)})
    clear_request.options.append(invalid_option)
    clear_request.context.setdefault("candidate_unit_ids", []).append(get_entity_id(hidden_target))
    clear_request.candidates = []
    clear_request.mask = []
    clear_request.mask_reasons = []
    clear_request.finalize_candidates()
    invalid = resolve_decision_command(game, clear_request, invalid_option.option_id, player_id=am_player.id)
    assert not bool(getattr(invalid, "ok", False))
    assert any("visible" in str(err).lower() for err in _result_errors(invalid))
    clear_request.context["candidate_unit_ids"].remove(get_entity_id(hidden_target))

    target_option = next(
        option
        for option in list(clear_request.options or [])
        if str((option.payload or {}).get("unit_id", "") or "") == str(get_entity_id(visible_target) or "")
    )
    apply_result = resolve_decision_command(game, clear_request, target_option.option_id, player_id=am_player.id)
    assert bool(getattr(apply_result, "ok", False)), str(getattr(apply_result, "errors", ()))
    destroy_request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_TARGET_MODEL
        and str((getattr(req, "context", {}) or {}).get("selection_kind", "") or "") == "battleshock_clear_destroy_model"
    )
    destroy_option = next(
        option
        for option in list(destroy_request.options or [])
        if str((option.payload or {}).get("model_id", "") or "") == str(get_entity_id(visible_extra) or "")
    )
    destroy_result = resolve_decision_command(game, destroy_request, destroy_option.option_id, player_id=am_player.id)
    assert bool(getattr(destroy_result, "ok", False)), str(getattr(destroy_result, "errors", ()))
    assert bool(visible_target.is_battle_shocked()) is False
    ability_key = str((clear_request.context or {}).get("ability_key", ""))
    turn_usage = dict((source.special_rules or {}).get(START_ANY_PHASE_BATTLESHOCK_CLEAR_TURN_USAGE) or {})
    assert turn_usage.get(ability_key) == current_player_turn_key(game)

    visible_target.apply_status_effect(BattleShockEffect(game.turn))
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game._on_phase_start_optional_abilities(player=am_player, phase=game.phase)
    repeated_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
    ]
    assert repeated_requests == []

    game.current_player_index = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game._on_phase_start_optional_abilities(player=am_player, phase=game.phase)
    opponent_turn_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
    ]
    assert len(opponent_turn_requests) == 1


def test_aquiline_prow_is_optional_charge_end_mortal_wounds(monkeypatch):
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.CHARGE_PHASE
    source = _make_unit(
        "Commissar Graves",
        x=0.0,
        y=0.0,
        abilities=[{"name": "Aquiline Prow", "description": AQUILINE_PROW_TEXT, "type": "Wargear", "parameter": ""}],
        keywords=["VEHICLE", "SQUADRON", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    target = _make_unit(
        "Enemy Infantry",
        x=1.0,
        y=0.0,
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=10,
    )
    am_army.add_unit(source)
    enemy_army.add_unit(target)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    source._refresh_charge_end_mortal_wounds_flags()
    specs = list(getattr(source, "special_rules", {}).get("charge_end_mortal_wounds", []) or [])
    assert len(specs) == 1
    spec = specs[0]
    assert spec["kind"] == "table_d6_2_3_d3_4_5_3_6_d3_3"
    assert bool(spec.get("optional", False)) is True

    applied: list[int] = []

    def _apply(self, _target, amount, game_map=None):
        applied.append(int(amount or 0))
        return 0

    source._apply_mortal_wounds_to_unit = _apply.__get__(source, Unit)
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _die: 6)

    game._on_unit_move_ended_charge_mortal_wounds(unit=source, action="charge")

    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("mortal_wounds_kind", "") or "") == "charge_end"
    ]
    assert len(requests) == 1
    request = requests[0]
    assert bool((request.context or {}).get("optional", False)) is True
    assert bool((request.context or {}).get("allow_skip", False)) is True
    skip_option = next(
        option for option in list(request.options or []) if str((option.payload or {}).get("action", "") or "") == "skip"
    )
    skipped = resolve_decision_command(game, request, skip_option.option_id, player_id=am_player.id)
    assert bool(getattr(skipped, "ok", False))
    assert applied == []


def test_aquiline_prow_selected_target_resolves_d6_table(monkeypatch):
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.CHARGE_PHASE
    source = _make_unit(
        "Commissar Graves",
        x=0.0,
        y=0.0,
        abilities=[{"name": "Aquiline Prow", "description": AQUILINE_PROW_TEXT, "type": "Wargear", "parameter": ""}],
        keywords=["VEHICLE", "SQUADRON", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    target = _make_unit(
        "Enemy Infantry",
        x=1.0,
        y=0.0,
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=10,
    )
    am_army.add_unit(source)
    enemy_army.add_unit(target)
    game.map.units = [source, target]
    game.rebuild_entity_registry()
    source._refresh_charge_end_mortal_wounds_flags()

    applied: list[int] = []

    def _apply(self, resolved_target, amount, game_map=None):
        assert resolved_target is target
        applied.append(int(amount or 0))
        return 0

    source._apply_mortal_wounds_to_unit = _apply.__get__(source, Unit)
    rolls = iter([6, 2])
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _die: next(rolls))

    game._on_unit_move_ended_charge_mortal_wounds(unit=source, action="charge")
    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("mortal_wounds_kind", "") or "") == "charge_end"
    )
    target_option = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(target) or "")
    )
    resolved = resolve_decision_command(game, request, target_option.option_id, player_id=am_player.id)
    assert bool(getattr(resolved, "ok", False))
    assert applied == [5]


def test_support_matrix_classifies_brutal_disciplinarian_variants_as_supported():
    import scripts.generate_ability_support_matrix as support_matrix

    for description in (BRUTAL_DISCIPLINARIAN_ON_FOOT_TEXT, BRUTAL_DISCIPLINARIAN_MOUNTED_TEXT):
        status, notes = support_matrix._classify_ability(
            "Brutal Disciplinarian",
            description,
            faction_id="AM",
        )
        assert status == "Supported"
        assert "Battle-shock clear" in notes
        assert "one model is destroyed" in notes


def test_support_matrix_classifies_aquiline_prow_as_supported():
    import scripts.generate_ability_support_matrix as support_matrix

    status, notes = support_matrix._classify_ability(
        "Aquiline Prow",
        AQUILINE_PROW_TEXT,
        faction_id="AM",
    )

    assert status == "Supported"
    assert "2-3=D3" in notes
    assert "Skip choice" in notes
