from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_CHARGE
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules, validate_final_position
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adeptus Mechanicus",
        keywords=None,
        faction_keywords=None,
        wounds: int = 3,
        base_size: str = "32mm",
        transport: str = "",
    ) -> None:
        self.id = f"ds_{name.lower().replace(' ', '_').replace('-', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "10" if "VEHICLE" in set(self.keywords) else "6",
                "T": "10" if "VEHICLE" in set(self.keywords) else "4",
                "Sv": "3" if "VEHICLE" in set(self.keywords) else "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "3" if "VEHICLE" in set(self.keywords) else "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Adeptus Mechanicus",
    keywords=None,
    faction_keywords=None,
    wounds: int = 3,
    base_size: str = "32mm",
    transport: str = "",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            base_size=base_size,
            transport=transport,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.round_state.shot_this_round = False
    unit.round_state.moved_this_round = False
    unit.round_state.advanced_this_round = False
    unit.round_state.fell_back_this_round = False
    unit.round_state.attempted_charge_this_round = False
    return unit


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(x=float(x), y=float(y), z=0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description=f"Control {name}",
        conditions=lambda _game: False,
        location=point,
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.auto_resolve_dice_rolls = False

    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Explorator Maniple")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    admech_player = Player("AdMech", PlayerControl.LOCAL, army=admech_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.current_player_idx = 0
    admech_player.command_points = 10
    enemy_player.command_points = 10

    objective_a = _make_objective("Alpha", 10.0, 10.0)
    objective_b = _make_objective("Beta", 19.0, 10.0)
    game.objectives = [objective_a, objective_b]
    game.map.objectives = [objective_a, objective_b]
    return game, admech_army, enemy_army, admech_player, enemy_player, objective_a, objective_b


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    refresh = getattr(game, "refresh_rule_subscribers", None)
    if callable(refresh):
        refresh()
    for player in players:
        player.stratagems.refresh_available()


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.current_player_idx = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    wanted = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == wanted:
            return reaction
    return None


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


def _find_option(request, *, target_unit_id: str | None = None):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if target_unit_id is not None and str(payload.get("target_unit_id", "") or "") != str(target_unit_id):
            continue
        return option
    return None


def _select_acquisition_objective(game: Game, objective, *, player, army) -> None:
    mgr = army.adeptus_mechanicus_detachments
    selection = mgr.select_acquisition_objective(
        str(get_entity_id(objective) or ""),
        game=game,
        player=player,
        battle_round=int(getattr(game, "turn", 0) or 0),
    )
    assert isinstance(selection, dict)


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_explorator_stratagem_descriptors_registered():
    expected = {
        "000008569002": ("Cached Acquisition", "objective_marker_sticky_control_on_destroyed_unit"),
        "000008569003": ("Priority Reclamation", "consolidate_distance_override_with_acquisition_objective_end_requirement"),
        "000008569004": ("Infoslave Skull", "additional_acquisition_objective_marker"),
        "000008569005": ("Auto-Oracular Retrieval", "ranged_wound_bonus_vs_targets_within_acquisition_objective"),
        "000008569006": ("Incense Exhausts", "stealth_and_benefit_of_cover_for_two_units"),
        "000008569007": ("Reactive Safeguard", "reactive_embark_and_charge_retarget"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_infoslave_skull_adds_secondary_acquisition_objective():
    game, admech_army, enemy_army, admech_player, enemy_player, objective_a, objective_b = _build_game()
    tech_priest = _make_unit(
        "Tech-priest Manipulus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    skitarii = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(tech_priest)
    admech_army.add_unit(skitarii)
    _deploy_unit(game, tech_priest, 10.0, 10.0)
    _deploy_unit(game, skitarii, 19.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _select_acquisition_objective(game, objective_a, player=admech_player, army=admech_army)
    _set_phase(game, admech_player, "COMMAND_PHASE", 0)
    ok = admech_player.stratagems.use(
        "INFOSLAVE SKULL",
        unit=tech_priest,
        objective=objective_b,
        phase_name="Command phase",
    )
    assert ok is True

    mgr = admech_army.adeptus_mechanicus_detachments
    active_ids = set(mgr.explorator_active_acquisition_objective_ids(game=game, game_map=game.map))
    assert active_ids == {str(get_entity_id(objective_a) or ""), str(get_entity_id(objective_b) or "")}
    assert bool(mgr.explorator_unit_within_acquisition_objective(skitarii, game=game, game_map=game.map)) is True


def test_auto_oracular_retrieval_grants_ranged_wound_bonus_vs_acquisition_objective():
    game, admech_army, enemy_army, admech_player, enemy_player, objective_a, _objective_b = _build_game()
    transport = _make_unit(
        "Skorpius Dunerider",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        wounds=10,
        transport="Transport Capacity 12",
    )
    shooter = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    target = _make_unit(
        "Enemy Intercessors",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(transport)
    admech_army.add_unit(shooter)
    enemy_army.add_unit(target)
    _deploy_unit(game, transport, 16.0, 10.0)
    _deploy_unit(game, shooter, 23.0, 10.0)
    _deploy_unit(game, target, 10.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    shooter.round_state.disembarked_this_round = True
    shooter.round_state.disembarked_from_transport_id = str(get_entity_id(transport) or "")
    _select_acquisition_objective(game, objective_a, player=admech_player, army=admech_army)
    _set_phase(game, admech_player, "SHOOTING_PHASE", 0)

    ok = admech_player.stratagems.use(
        "AUTO-ORACULAR RETRIEVAL",
        unit=shooter,
        phase_name="Shooting phase",
    )
    assert ok is True

    result = _ranged_profile()._wound_target_with_tracking(
        target,
        shooter.models[0],
        {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        },
    )
    assert any("AUTO-ORACULAR RETRIEVAL" in text for text in list(result.get("modifiers", []) or []))


def test_incense_exhausts_queues_and_applies_stealth_and_cover_until_phase_end():
    game, admech_army, enemy_army, admech_player, enemy_player, _objective_a, _objective_b = _build_game()
    primary = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    support = _make_unit(
        "Onager Dunecrawler",
        keywords=["VEHICLE", "SMOKE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        wounds=10,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(primary)
    admech_army.add_unit(support)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, primary, 10.0, 10.0)
    _deploy_unit(game, support, 14.0, 10.0)
    _deploy_unit(game, attacker, 24.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[primary])

    pending = _pending_by_name(admech_player.stratagems, "INCENSE EXHAUSTS")
    assert pending is not None

    ok = admech_player.stratagems.use(
        "INCENSE EXHAUSTS",
        unit=primary,
        support_unit=support,
        attacking_unit=attacker,
        target_units=[primary],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True

    for unit in (primary, support):
        sr = dict(getattr(unit, "special_rules", {}) or {})
        assert bool(sr.get("opponent_shooting_phase_stealth_active", False)) is True
        cover_bonuses = list(sr.get("defensive_cover_bonuses", []) or [])
        assert any("INCENSE EXHAUSTS" in str(entry.get("source", "") or "") for entry in cover_bonuses)

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    for unit in (primary, support):
        sr = dict(getattr(unit, "special_rules", {}) or {})
        assert bool(sr.get("opponent_shooting_phase_stealth_active", False)) is False


def test_cached_acquisition_queues_and_makes_objective_sticky():
    game, admech_army, enemy_army, admech_player, enemy_player, objective_a, _objective_b = _build_game()
    destroyed = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(destroyed)
    _deploy_unit(game, destroyed, 10.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    game._objective_control_snapshot = {objective_a.location: admech_player}
    last_model = destroyed.models[0]
    game.event_system.publish("unit_destroyed", unit=destroyed, last_model=last_model)

    pending = _pending_by_name(admech_player.stratagems, "CACHED ACQUISITION")
    assert pending is not None
    assert objective_a in list(pending.get("objective_candidates") or [])

    ok = admech_player.stratagems.use(
        "CACHED ACQUISITION",
        destroyed_unit=destroyed,
        objective=objective_a,
        last_model=last_model,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert objective_a.location.sticky_controller is admech_player
    assert str(getattr(objective_a.location, "sticky_source", "") or "") == "explorator_cached_acquisition"


def test_priority_reclamation_limits_consolidate_objective_fallback_to_acquisition_objectives():
    game, admech_army, enemy_army, admech_player, enemy_player, objective_a, objective_b = _build_game()
    unit = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Guard",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 50.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _select_acquisition_objective(game, objective_b, player=admech_player, army=admech_army)
    _set_phase(game, admech_player, "FIGHT_PHASE", 0)
    game.event_system.publish("fight_attacks_resolved", unit=unit, target_unit=enemy)

    pending = _pending_by_name(admech_player.stratagems, "PRIORITY RECLAMATION")
    assert pending is not None

    ok = admech_player.stratagems.use(
        "PRIORITY RECLAMATION",
        unit=unit,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True

    sr = dict(getattr(unit, "special_rules", {}) or {})
    assert float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0) == 6.0
    assert list(sr.get("stratagem_consolidate_allowed_objective_ids") or []) == [str(get_entity_id(objective_b) or "")]

    rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=unit)
    invalid = validate_final_position(unit.models[0], (13.0, 10.0, 0.0), rules, game.map)
    valid = validate_final_position(unit.models[0], (18.0, 10.0, 0.0), rules, game.map)
    assert bool(invalid.get("valid", False)) is False
    assert "objective" in str(invalid.get("reason", "") or "").lower()
    assert bool(valid.get("valid", False)) is True


def test_reactive_safeguard_embarks_target_and_queues_charge_retarget():
    game, admech_army, enemy_army, admech_player, enemy_player, objective_a, _objective_b = _build_game()
    charger = _make_unit(
        "Enemy Chargers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    transport = _make_unit(
        "Skorpius Dunerider",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        wounds=10,
        transport="Transport Capacity 12",
    )
    target = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    replacement = _make_unit(
        "Sicarian Infiltrators",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    transport.transport_capacity = 12
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = set()

    enemy_army.add_unit(charger)
    admech_army.add_unit(transport)
    admech_army.add_unit(target)
    admech_army.add_unit(replacement)
    _deploy_unit(game, charger, 6.0, 10.0)
    _deploy_unit(game, transport, 15.8, 10.0)
    _deploy_unit(game, target, 13.4, 10.0)
    _deploy_unit(game, replacement, 20.0, 12.5)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _select_acquisition_objective(game, objective_a, player=admech_player, army=admech_army)
    game.map.is_path_blocked = lambda *_args, **_kwargs: False
    game.map.is_within_engagement_range = lambda *_args, **_kwargs: False
    charger._can_declare_charge_base = lambda _game, out_of_turn=False: True
    charger.can_declare_charge_against = lambda unit, _game, out_of_turn=False: unit is target or unit is replacement

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    declared = game.declare_charge(charger, [target, replacement])
    assert declared is not None
    assert _pending_by_name(admech_player.stratagems, "REACTIVE SAFEGUARD") is not None

    ok = admech_player.stratagems.use(
        "REACTIVE SAFEGUARD",
        unit=target,
        transport_unit=transport,
        charging_unit=charger,
        target_units=[target, replacement],
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok is True
    assert target.embarked_in is transport
    assert target in list(getattr(transport, "transport_passengers", []) or [])

    retarget_request = _find_request(game, DECISION_DECLARE_CHARGE, reason="emergency_combat_embarkation")
    assert retarget_request is not None
    assert _find_option(retarget_request, target_unit_id=str(get_entity_id(replacement) or "")) is not None
    assert _find_option(retarget_request, target_unit_id=str(get_entity_id(target) or "")) is None
