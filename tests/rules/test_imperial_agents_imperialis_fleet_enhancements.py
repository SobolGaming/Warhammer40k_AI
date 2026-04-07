from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_SELECT_REALM_OF_CHAOS_UNITS,
)
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        wounds: int = 2,
        leadership: int = 7,
        objective_control: int = 1,
    ):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Imperial Agents",
    keywords=None,
    faction_keywords=None,
    wounds: int = 2,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ia_army = Army.with_detachment("Imperial Agents", "Imperialis Fleet")
    ia_army.faction_id = "AOI"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    return game, ia_army, enemy_army, ia_player, enemy_player


def _set_model_location(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + 0.1 * float(idx), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    for unit in units:
        if unit not in list(getattr(game.map, "units", []) or []):
            game.map.units.append(unit)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str, description: str) -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="AOI",
        detachment="Imperialis Fleet",
        detachment_id="000000895",
        points=0,
        description=str(description),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _find_request(game: Game, decision_type: str, ability: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability):
            return request
    return None


def _confirm_option_id(request) -> str:
    for option in list(getattr(request, "options", []) or []):
        if str((getattr(option, "payload", {}) or {}).get("action", "") or "").strip().lower() == "confirm":
            return str(getattr(option, "option_id", "") or "")
    raise AssertionError("Confirm option was not found.")


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    bodyguard.get_attached_unit_members = lambda: [bodyguard, leader]
    bodyguard.get_attached_unit_models = lambda: list(bodyguard.models) + list(leader.models)
    for unit in (leader, bodyguard):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()


def test_imperialis_fleet_enhancement_descriptors_registered():
    clandestine = get_enhancement_tool_descriptor(enhancement_id="000009138002")
    combat = get_enhancement_tool_descriptor(enhancement_id="000009138003")
    digital = get_enhancement_tool_descriptor(enhancement_id="000009138004")

    assert clandestine is not None
    assert clandestine.name == "Clandestine Operation"
    assert int(clandestine.effect_params.get("max_units", 0) or 0) == 3

    assert combat is not None
    assert combat.name == "Combat Landers"
    assert tuple(combat.effect_params.get("required_keywords", ()) or ()) == ("VOIDFARERS",)

    assert digital is not None
    assert digital.name == "Digital Weapons"
    assert int(digital.effect_params.get("dice", 0) or 0) == 3
    assert int(digital.effect_params.get("threshold", 0) or 0) == 4


def test_clandestine_operation_selects_eligible_units_and_grants_infiltrate():
    game, ia_army, _enemy_army, ia_player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Inquisitor",
        keywords=["INFANTRY", "CHARACTER", "AGENTS OF THE IMPERIUM"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    agents_a = _make_unit(
        "Inquisitorial Agents A",
        keywords=["INFANTRY", "AGENTS OF THE IMPERIUM"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    agents_b = _make_unit(
        "Inquisitorial Agents B",
        keywords=["INFANTRY", "AGENTS OF THE IMPERIUM"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    grey_knights_terminators = _make_unit(
        "Grey Knights Terminator Squad",
        keywords=["INFANTRY", "AGENTS OF THE IMPERIUM"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    non_infantry = _make_unit(
        "Corvus Blackstar",
        keywords=["VEHICLE", "AGENTS OF THE IMPERIUM"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    for unit in (bearer, agents_a, agents_b, grey_knights_terminators, non_infantry):
        ia_army.add_unit(unit)
    game.rebuild_entity_registry()

    _apply_enhancement(
        bearer,
        enhancement_id="000009138002",
        enhancement_name="Clandestine Operation",
        description=(
            "AGENTS OF THE IMPERIUM model only. At the start of the Declare Battle Formations step, you can select "
            "up to three AGENTS OF THE IMPERIUM INFANTRY units from your army (excluding GREY KNIGHTS TERMINATOR "
            "SQUAD units) - those units gain the Infiltrators ability."
        ),
    )

    ia_army.on_prebattle_rules_start(game=game)
    request = _find_request(game, DECISION_SELECT_REALM_OF_CHAOS_UNITS, "imperialis_fleet_clandestine_operation_selection")
    assert request is not None
    assert str((request.context or {}).get("source_unit_id", "") or "") == str(get_entity_id(bearer) or "")
    allowed_ids = set(str(v or "") for v in list((request.context or {}).get("allowed_unit_ids", []) or []))
    assert str(get_entity_id(agents_a) or "") in allowed_ids
    assert str(get_entity_id(agents_b) or "") in allowed_ids
    assert str(get_entity_id(grey_knights_terminators) or "") not in allowed_ids
    assert str(get_entity_id(non_infantry) or "") not in allowed_ids

    result = resolve_decision_command(
        game,
        request,
        _confirm_option_id(request),
        result_payload={"unit_ids": [str(get_entity_id(agents_a) or ""), str(get_entity_id(agents_b) or "")]},
        player_id=ia_player.id,
    )
    assert bool(getattr(result, "ok", False)) is True
    assert agents_a.has_infiltrate() is True
    assert agents_b.has_infiltrate() is True
    assert grey_knights_terminators.has_infiltrate() is False
    source_sr = dict(getattr(bearer, "special_rules", {}) or {})
    assert bool(source_sr.get("enhancement_imperialis_fleet_clandestine_operation_resolved", False)) is True


def test_combat_landers_selects_voidfarers_and_grants_deep_strike():
    game, ia_army, _enemy_army, ia_player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Rogue Trader",
        keywords=["INFANTRY", "CHARACTER", "VOIDFARERS"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    voidsmen = _make_unit(
        "Voidsmen-at-Arms",
        keywords=["INFANTRY", "VOIDFARERS"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    breachers = _make_unit(
        "Imperial Navy Breachers",
        keywords=["INFANTRY", "VOIDFARERS"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    arbites = _make_unit(
        "Subductor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    for unit in (bearer, voidsmen, breachers, arbites):
        ia_army.add_unit(unit)
    game.rebuild_entity_registry()

    _apply_enhancement(
        bearer,
        enhancement_id="000009138003",
        enhancement_name="Combat Landers",
        description=(
            "VOIDFARERS model only. At the start of the Declare Battle Formations step, you can select up to three "
            "VOIDFARERS units from your army - those units gain the Deep Strike ability."
        ),
    )

    ia_army.on_prebattle_rules_start(game=game)
    request = _find_request(game, DECISION_SELECT_REALM_OF_CHAOS_UNITS, "imperialis_fleet_combat_landers_selection")
    assert request is not None
    allowed_ids = set(str(v or "") for v in list((request.context or {}).get("allowed_unit_ids", []) or []))
    assert str(get_entity_id(voidsmen) or "") in allowed_ids
    assert str(get_entity_id(breachers) or "") in allowed_ids
    assert str(get_entity_id(arbites) or "") not in allowed_ids

    result = resolve_decision_command(
        game,
        request,
        _confirm_option_id(request),
        result_payload={"unit_ids": [str(get_entity_id(voidsmen) or ""), str(get_entity_id(breachers) or "")]},
        player_id=ia_player.id,
    )
    assert bool(getattr(result, "ok", False)) is True
    assert voidsmen.has_deep_strike() is True
    assert breachers.has_deep_strike() is True
    assert arbites.has_deep_strike() is False


def test_digital_weapons_queues_and_resolves_sequential_precision_targets():
    game, ia_army, enemy_army, ia_player, _enemy_player = _build_game()
    game.phase = type("FightPhase", (), {"name": "FIGHT_PHASE"})()

    bearer = _make_unit(
        "Inquisitor",
        keywords=["INFANTRY", "CHARACTER", "AGENTS OF THE IMPERIUM"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    target_bodyguard = _make_unit(
        "Enemy Bodyguard",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["CHAOS"],
        wounds=2,
    )
    target_leader = _make_unit(
        "Enemy Leader",
        faction_name="Enemy",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["CHAOS"],
        wounds=3,
    )

    ia_army.add_unit(bearer)
    enemy_army.add_unit(target_bodyguard)
    enemy_army.add_unit(target_leader)
    _attach_leader(target_bodyguard, target_leader)
    _apply_enhancement(
        bearer,
        enhancement_id="000009138004",
        enhancement_name="Digital Weapons",
        description=(
            "AGENTS OF THE IMPERIUM model only. Each time the bearer is selected to fight, roll three D6: for each "
            "4+, one enemy unit within Engagement Range of the bearer suffers 1 mortal wound. Mortal wounds inflicted "
            "by this Enhancement are allocated as if they had the [PRECISION] ability."
        ),
    )

    _set_model_location(bearer, 0.0, 0.0)
    _set_model_location(target_bodyguard, 0.5, 0.0)
    _set_model_location(target_leader, 0.55, 0.0)
    _register_units(game, bearer, target_bodyguard)
    game.rebuild_entity_registry()

    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[4, 5, 2]):
        game._on_fight_unit_selected_imperial_agents_digital_weapons(
            unit=bearer,
            selecting_player=ia_player,
        )

    first_request = _find_request(game, DECISION_CHOOSE_QUARRY, "imperialis_fleet_digital_weapons")
    assert first_request is not None
    first_option = next(
        option
        for option in list(first_request.options or [])
        if str((getattr(option, "payload", {}) or {}).get("target_model_id", "") or "")
        == str(get_entity_id(target_leader.models[0]) or "")
    )
    first_result = resolve_decision_command(
        game,
        first_request,
        first_option.option_id,
        player_id=ia_player.id,
    )
    assert bool(getattr(first_result, "ok", False)) is True
    assert int(target_leader.models[0].wounds or 0) == 2
    assert int(target_bodyguard.models[0].wounds or 0) == 2

    second_request = _find_request(game, DECISION_CHOOSE_QUARRY, "imperialis_fleet_digital_weapons")
    assert second_request is not None
    second_option = next(
        option
        for option in list(second_request.options or [])
        if str((getattr(option, "payload", {}) or {}).get("target_unit_id", "") or "")
        == str(get_entity_id(target_bodyguard) or "")
        and not str((getattr(option, "payload", {}) or {}).get("target_model_id", "") or "")
    )
    second_result = resolve_decision_command(
        game,
        second_request,
        second_option.option_id,
        player_id=ia_player.id,
    )
    assert bool(getattr(second_result, "ok", False)) is True
    assert int(target_bodyguard.models[0].wounds or 0) == 1
    assert _find_request(game, DECISION_CHOOSE_QUARRY, "imperialis_fleet_digital_weapons") is None
