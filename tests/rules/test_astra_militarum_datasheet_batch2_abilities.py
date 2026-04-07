import copy
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET,
    DECISION_SELECT_TARGET_MODEL,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
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
