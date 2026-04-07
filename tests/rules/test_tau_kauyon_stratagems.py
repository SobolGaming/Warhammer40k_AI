from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_DECLARE_CHARGE,
    DECISION_REQUEST_DICE_ROLL,
)
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "T'au Empire"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.auto_resolve_dice_rolls = False
    army_tau = Army.with_detachment("T'au Empire", "Kauyon")
    army_tau.faction_id = "TAU"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("Tau", control=PlayerControl.LOCAL, army=army_tau)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 5
    p2.command_points = 5
    army_tau.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, army_tau, army_enemy


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _add_objective(game: Game, x: float, y: float, *, name: str = "Objective") -> Objective:
    location = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    objective = Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=0,
        description="",
        conditions=lambda _game: False,
        location=location,
    )
    game.map.add_objectives([objective])
    return objective


def _find_request(game: Game, decision_type: str, *, ability: str | None = None, reason: str | None = None):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if ability is not None and str(ctx.get("ability", "") or "") != str(ability):
            continue
        if reason is not None and str(ctx.get("charge_retarget_reason", "") or "") != str(reason):
            continue
        return request
    return None


def _find_option(
    request,
    *,
    target_unit_id: str | None = None,
    transport_id: str | None = None,
    objective_id: str | None = None,
    action: str | None = None,
):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if target_unit_id is not None and str(payload.get("target_unit_id", "") or "") != str(target_unit_id):
            continue
        if transport_id is not None and str(payload.get("transport_id", "") or "") != str(transport_id):
            continue
        if objective_id is not None and str(payload.get("objective_id", "") or "") != str(objective_id):
            continue
        if action is not None and str(payload.get("action", "") or "") != str(action):
            continue
        return option
    return None


def _ranged_profile(*, skill: str = "4+", strength: str = "4", ap: str = "0") -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": str(ap),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _grant_observer_ranged_profile(unit: Unit) -> None:
    wargear = SimpleNamespace(
        id=f"wargear:{get_entity_id(unit)}:observer",
        is_ranged=lambda: True,
        profiles={"default": SimpleNamespace(name="Observer Gun")},
    )
    for model in list(getattr(unit, "models", []) or []):
        model.wargear = [wargear]


def test_a_tempting_trap_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008443002")
    assert desc is not None
    assert desc.name == "A Tempting Trap"
    assert desc.effect == "conditional_ranged_wound_bonus_vs_selected_trap_objective"


def test_coordinate_to_engage_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008443004")
    assert desc is not None
    assert desc.name == "Coordinate to Engage"
    assert desc.effect == "observer_ballistic_skill_bonus_vs_spotted_unit"


def test_combat_embarkation_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008443005")
    assert desc is not None
    assert desc.name == "Combat Embarkation"
    assert desc.effect == "reactive_embark_and_charge_retarget"


def test_photon_grenades_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008443006")
    assert desc is not None
    assert desc.name == "Photon Grenades"
    assert desc.effect == "force_battleshock_and_charge_penalty"


def test_wall_of_mirrors_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008443007")
    assert desc is not None
    assert desc.name == "Wall of Mirrors"
    assert desc.effect == "enter_strategic_reserves"
    assert int(desc.cp_cost or 0) == 1


def test_point_blank_ambush_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008443003")
    assert desc is not None
    assert desc.name == "Point-Blank Ambush"
    assert desc.effect == "conditional_ranged_ap_bonus_within_range"
    assert int(desc.cp_cost or 0) == 1
    assert float(desc.range_in or 0) == 9.0


def test_a_tempting_trap_queues_objective_selection_and_applies_wound_bonus() -> None:
    game, p1, _p2, army_tau, army_enemy = _build_game()
    shooter = _make_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    near_enemy = _make_unit(
        "Near Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    far_enemy = _make_unit(
        "Far Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_tau.add_unit(shooter)
    army_enemy.add_unit(near_enemy)
    army_enemy.add_unit(far_enemy)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, near_enemy, 30.0, 22.0)
    _deploy_unit(game, far_enemy, 44.0, 36.0)
    objective = _add_objective(game, 30.0, 22.0, name="Trap Objective")
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    ok = p1.stratagems.use("A TEMPTING TRAP", unit=shooter, phase_name="Shooting phase")
    assert ok
    assert int(p1.command_points or 0) == 4

    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="tau_kauyon_tempting_trap_objective")
    assert request is not None
    option = _find_option(request, objective_id=str(get_entity_id(objective) or ""))
    assert option is not None

    result = resolve_decision_command(game, request, option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True

    sr = dict(getattr(shooter, "special_rules", {}) or {})
    assert bool(sr.get("tau_a_tempting_trap_active")) is True
    assert str(sr.get("tau_a_tempting_trap_objective_id", "") or "") == str(get_entity_id(objective) or "")

    profile = _ranged_profile(skill="4+", strength="4")
    attack_instance = {
        "crit_hit": False,
        "crit_wound": False,
        "mortal_wound": False,
        "below_half_distance": False,
        "damage": 0,
        "target_toughness_override": None,
    }

    near_result = profile._wound_target_with_tracking(near_enemy, shooter.models[0], dict(attack_instance))
    assert any("A Tempting Trap" in text for text in list(near_result.get("modifiers", []) or []))

    far_result = profile._wound_target_with_tracking(far_enemy, shooter.models[0], dict(attack_instance))
    assert not any("A Tempting Trap" in text for text in list(far_result.get("modifiers", []) or []))


def test_coordinate_to_engage_reacts_to_observer_selection_and_improves_bs() -> None:
    game, p1, _p2, army_tau, army_enemy = _build_game()
    observer = _make_unit(
        "Pathfinder Team",
        keywords=["INFANTRY", "MARKERLIGHT"],
        faction_keywords=["T'AU EMPIRE"],
    )
    spotted_enemy = _make_unit(
        "Spotted Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    other_enemy = _make_unit(
        "Other Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_tau.add_unit(observer)
    army_enemy.add_unit(spotted_enemy)
    army_enemy.add_unit(other_enemy)
    _grant_observer_ranged_profile(observer)
    _deploy_unit(game, observer, 10.0, 10.0)
    _deploy_unit(game, spotted_enemy, 20.0, 10.0)
    _deploy_unit(game, other_enemy, 28.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    ftgg = getattr(army_tau, "for_the_greater_good", None)
    assert ftgg is not None
    assert ftgg.mark_spotted(observer, spotted_enemy, game=game, player=p1) is True
    assert _pending_by_name(p1.stratagems, "COORDINATE TO ENGAGE") is not None

    ok = p1.stratagems.use(
        "COORDINATE TO ENGAGE",
        unit=observer,
        target_unit=spotted_enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    assert int(p1.command_points or 0) == 4

    profile = _ranged_profile(skill="4+", strength="5")
    attack_vs_spotted = {"benefit_of_cover": True, "benefit_of_cover_source": "RUINS"}
    hit_spotted = profile._hit_target_with_tracking(spotted_enemy, observer.models[0], attack_vs_spotted, roll_value=3)
    assert int(hit_spotted.get("final_needed", 0) or 0) == 3
    assert bool(attack_vs_spotted.get("ignores_cover", False)) is True

    attack_vs_other = {}
    hit_other = profile._hit_target_with_tracking(other_enemy, observer.models[0], attack_vs_other, roll_value=4)
    assert int(hit_other.get("final_needed", 0) or 0) == 4
    assert bool(attack_vs_other.get("ignores_cover", False)) is False


def test_photon_grenades_updates_pending_charge_roll_and_cleans_up() -> None:
    game, p1, p2, army_tau, army_enemy = _build_game()
    grenadier = _make_unit(
        "Breacher Team",
        keywords=["INFANTRY", "GRENADES"],
        faction_keywords=["T'AU EMPIRE"],
    )
    charger = _make_unit(
        "Enemy Chargers",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_tau.add_unit(grenadier)
    army_enemy.add_unit(charger)
    _deploy_unit(game, grenadier, 12.0, 10.0)
    _deploy_unit(game, charger, 6.0, 10.0)
    game.rebuild_entity_registry()

    charger._can_declare_charge_base = lambda _game, out_of_turn=False: True
    charger.can_declare_charge_against = lambda target, _game, out_of_turn=False: target is grenadier
    battle_shock_calls: list[tuple[int, str]] = []
    charger.force_battle_shock_test = lambda current_turn=1, source="": battle_shock_calls.append((int(current_turn), str(source)))

    _set_phase(game, p2, "CHARGE_PHASE", 1)
    declared = game.declare_charge(charger, [grenadier])
    assert declared is not None
    assert _pending_by_name(p1.stratagems, "PHOTON GRENADES") is not None

    roll_request = _find_request(game, DECISION_REQUEST_DICE_ROLL)
    assert roll_request is not None
    base_roll_spec = dict((dict(getattr(roll_request, "context", {}) or {})).get("roll_spec", {}) or {})
    assert int(base_roll_spec.get("sum_modifier", 0) or 0) == 0

    ok = p1.stratagems.use(
        "PHOTON GRENADES",
        unit=grenadier,
        charging_unit=charger,
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok
    assert int(p1.command_points or 0) == 4
    assert battle_shock_calls == [(1, "PHOTON GRENADES")]

    charge_mods = list((dict(getattr(charger, "special_rules", {}) or {})).get("charge_roll_modifiers", []) or [])
    assert any(
        isinstance(entry, dict) and str(entry.get("source_key", "") or "") == "tau_photon_grenades"
        for entry in charge_mods
    )

    roll_request = _find_request(game, DECISION_REQUEST_DICE_ROLL)
    assert roll_request is not None
    roll_spec = dict((dict(getattr(roll_request, "context", {}) or {})).get("roll_spec", {}) or {})
    assert int(roll_spec.get("sum_modifier", 0) or 0) == -2
    assert any("PHOTON GRENADES" in text for text in list(roll_spec.get("sum_modifier_reasons", []) or []))

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="CHARGE_PHASE"))
    charge_mods_after = list((dict(getattr(charger, "special_rules", {}) or {})).get("charge_roll_modifiers", []) or [])
    assert not any(
        isinstance(entry, dict) and str(entry.get("source_key", "") or "") == "tau_photon_grenades"
        for entry in charge_mods_after
    )


def test_combat_embarkation_retargets_charge_after_embark() -> None:
    game, p1, p2, army_tau, army_enemy = _build_game()
    charger = _make_unit(
        "Enemy Chargers",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    transport = _make_unit(
        "Devilfish",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["T'AU EMPIRE"],
    )
    target = _make_unit(
        "Breacher Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    replacement = _make_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    transport.transport_capacity = 12

    army_enemy.add_unit(charger)
    army_tau.add_unit(transport)
    army_tau.add_unit(target)
    army_tau.add_unit(replacement)
    _deploy_unit(game, charger, 6.0, 10.0)
    _deploy_unit(game, transport, 17.0, 10.0)
    _deploy_unit(game, target, 14.8, 10.0)
    _deploy_unit(game, replacement, 14.5, 17.0)
    game.rebuild_entity_registry()
    game.map.is_path_blocked = lambda *_args, **_kwargs: False

    charger._can_declare_charge_base = lambda _game, out_of_turn=False: True
    charger.can_declare_charge_against = (
        lambda unit, _game, out_of_turn=False: unit is target or unit is replacement
    )

    _set_phase(game, p2, "CHARGE_PHASE", 1)
    declared = game.declare_charge(charger, [target])
    assert declared is not None
    assert _pending_by_name(p1.stratagems, "COMBAT EMBARKATION") is not None
    assert _find_request(game, DECISION_REQUEST_DICE_ROLL) is not None

    ok = p1.stratagems.use(
        "COMBAT EMBARKATION",
        charging_unit=charger,
        target_units=[target],
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok
    assert int(p1.command_points or 0) == 4
    assert _find_request(game, DECISION_REQUEST_DICE_ROLL) is None

    embark_request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="emergency_combat_embarkation")
    assert embark_request is not None
    assert _find_option(embark_request, action="skip") is None

    embark_option = _find_option(
        embark_request,
        target_unit_id=str(get_entity_id(target) or ""),
        transport_id=str(get_entity_id(transport) or ""),
    )
    assert embark_option is not None

    embark_result = resolve_decision_command(game, embark_request, embark_option.option_id, player_id=p1.id)
    assert bool(getattr(embark_result, "ok", False)) is True
    assert target.embarked_in is transport
    assert target in list(getattr(transport, "transport_passengers", []) or [])

    retarget_request = _find_request(game, DECISION_DECLARE_CHARGE, reason="emergency_combat_embarkation")
    assert retarget_request is not None
    replacement_id = str(get_entity_id(replacement) or "")
    replacement_option = _find_option(retarget_request, target_unit_id=replacement_id)
    assert replacement_option is not None

    retarget_result = resolve_decision_command(
        game,
        retarget_request,
        replacement_option.option_id,
        result_payload={"target_unit_ids": [replacement_id]},
        player_id=p2.id,
    )
    assert bool(getattr(retarget_result, "ok", False)) is True
    assert charger.round_state.charge_target_ids == {replacement_id}

    roll_request = _find_request(game, DECISION_REQUEST_DICE_ROLL)
    assert roll_request is not None
    roll_spec = dict((dict(getattr(roll_request, "context", {}) or {})).get("roll_spec", {}) or {})
    assert list(roll_spec.get("target_unit_ids", []) or []) == [replacement_id]


def test_wall_of_mirrors_queues_at_opponent_fight_phase_end_and_enters_strategic_reserves():
    game, p1, p2, army_tau, army_enemy = _build_game()
    stealth = _make_unit(
        "Stealth Battlesuits",
        keywords=["INFANTRY", "STEALTH"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_tau.add_unit(stealth)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, stealth, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = _pending_by_name(p1.stratagems, "WALL OF MIRRORS")
    assert pending is not None

    ok = p1.stratagems.use(
        "WALL OF MIRRORS",
        unit=stealth,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok
    assert int(p1.command_points or 0) == 4
    assert str(getattr(stealth, "reserve_status", "") or "") == "strategic_reserves"
    assert stealth not in list(getattr(game.map, "units", []) or [])


def test_point_blank_ambush_grants_ap_within_9_in_battle_round_3():
    from warhammer40k_ai.units.wargear import WargearProfile

    game, p1, _p2, army_tau, army_enemy = _build_game()
    game.turn = 3
    breachers = _make_unit(
        "Breacher Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    close_enemy = _make_unit(
        "Close Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    far_enemy = _make_unit(
        "Far Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_tau.add_unit(breachers)
    army_enemy.add_unit(close_enemy)
    army_enemy.add_unit(far_enemy)
    for unit, x, y in (
        (breachers, 0.0, 0.0),
        (close_enemy, 8.0, 0.0),
        (far_enemy, 15.0, 0.0),
    ):
        for model in list(getattr(unit, "models", []) or []):
            model.set_location(float(x), float(y), 0.0, 0.0)
    game.map.units = [breachers, close_enemy, far_enemy]
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    ok = p1.stratagems.use("POINT-BLANK AMBUSH", unit=breachers, phase_name="Shooting phase")
    assert ok
    assert int(p1.command_points or 0) == 4

    parent = SimpleNamespace(name="Pulse Blaster", is_melee=lambda: False, is_ranged=lambda: True)
    profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "10",
            "A": "1",
            "BS_WS": "3+",
            "S": "6",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )

    assert profile.get_effective_ap(breachers.models[0], close_enemy) == -1
    assert profile.get_effective_ap(breachers.models[0], far_enemy) == 0


def test_point_blank_ambush_rejected_in_battle_round_2():
    game, p1, _p2, army_tau, army_enemy = _build_game()
    game.turn = 2
    breachers = _make_unit(
        "Breacher Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_tau.add_unit(breachers)
    army_enemy.add_unit(enemy)
    for unit, x, y in ((breachers, 0.0, 0.0), (enemy, 8.0, 0.0)):
        for model in list(getattr(unit, "models", []) or []):
            model.set_location(float(x), float(y), 0.0, 0.0)
    game.map.units = [breachers, enemy]
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    before_cp = int(p1.command_points or 0)
    ok = p1.stratagems.use("POINT-BLANK AMBUSH", unit=breachers, phase_name="Shooting phase")
    assert not ok
    assert int(p1.command_points or 0) == before_cp
