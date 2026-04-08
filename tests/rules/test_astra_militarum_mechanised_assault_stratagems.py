from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_DECLARE_CHARGE,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.units.unit import Unit


class _Ability:
    def __init__(self, name: str, description: str = "", ability_type: str = "") -> None:
        self.name = name
        self.description = description
        self.type = ability_type


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        wounds: int = 3,
        base_size: str = "32mm",
        transport: str = "",
    ) -> None:
        self.id = f"ds_{name.lower().replace(' ', '_').replace('-', '_')}"
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ASTRA MILITARUM"])
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
    keywords=None,
    faction_keywords=None,
    wounds: int = 3,
    base_size: str = "32mm",
    transport: str = "",
    abilities=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            base_size=base_size,
            transport=transport,
        )
    )
    unit.possible_abilities = list(abilities or [])
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.round_state.shot_this_round = False
    unit.round_state.moved_this_round = False
    unit.round_state.advanced_this_round = False
    unit.round_state.fell_back_this_round = False
    unit.round_state.attempted_charge_this_round = False
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    am_army = Army.with_detachment("Astra Militarum", "Mechanised Assault")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    am_player = Player("Astra Militarum", control=PlayerControl.LOCAL, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    am_player.command_points = 10
    enemy_player.command_points = 10
    return game, am_player, enemy_player, am_army, enemy_army


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


def _find_request(game: Game, decision_type: str, *, ability: str = "", reason: str = ""):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if ability:
            ctx = dict(getattr(request, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip() != str(ability):
                continue
        if reason and str(getattr(request, "reason", "") or "").strip() != str(reason):
            continue
        return request
    return None


def _find_option_by_payload(request, **expected):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if all(str(payload.get(key, "") or "") == str(value or "") for key, value in expected.items()):
            return option
    return None


def _mark_disembarked(game: Game, player: Player, unit: Unit, transport: Unit, *, phase_name: str) -> None:
    unit.embarked_in = None
    unit.reserve_status = "deployed"
    unit.round_state.disembarked_this_round = True
    unit.round_state.disembarked_from_transport_id = str(get_entity_id(transport) or "")
    special_rules = dict(getattr(unit, "special_rules", {}) or {})
    special_rules["voice_of_command_disembark_phase"] = str(phase_name or "").strip().upper()
    special_rules["voice_of_command_disembark_round"] = int(getattr(game, "turn", 0) or 0)
    special_rules["voice_of_command_disembark_owner"] = str(getattr(player, "id", "") or "")
    unit.special_rules = special_rules


def test_mechanised_assault_stratagem_descriptors_registered():
    expected = {
        "000009862002": ("Vox-Relay", "embarked_officer_issue_orders_via_transport_and_to_transports_any_distance"),
        "000009862003": ("Rapid Dispersal", "reactive_normal_move_d6"),
        "000009862004": ("Clear and Secure", "disembarked_ranged_hit_and_wound_rerolls_vs_targets_within_objective_range"),
        "000009862005": ("Swift Interception", "reactive_normal_move_up_to_6"),
        "000009862006": ("Hasty Extraction", "reactive_embark_and_continue_original_charge_targets"),
        "000009862007": ("Move Out", "end_of_opponent_turn_embark"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_vox_relay_marks_embarked_officer_active():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    officer = _make_unit(
        "Command Squad",
        keywords=["OFFICER", "INFANTRY", "REGIMENT"],
        abilities=[
            _Ability("Voice of Command"),
            _Ability("Orders", "This model can issue 1 Order to REGIMENT units within 6\"."),
        ],
    )
    transport = _make_unit("Chimera", keywords=["VEHICLE", "TRANSPORT"], wounds=10)
    far_transport = _make_unit("Taurox", keywords=["VEHICLE", "TRANSPORT"], wounds=10)
    transport.transport_capacity = 12
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = set()
    far_transport.transport_capacity = 12
    far_transport.transport_required_keywords = set()
    far_transport.transport_excluded_keywords = set()
    officer.embarked_in = transport
    officer.reserve_status = "embarked"

    am_army.add_unit(officer)
    am_army.add_unit(transport)
    am_army.add_unit(far_transport)
    _deploy_unit(game, transport, 10.0, 10.0)
    _deploy_unit(game, far_transport, 24.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _set_phase(game, am_player, "COMMAND_PHASE", 0)
    ok = am_player.stratagems.use("VOX-RELAY", unit=officer, phase_name="Command phase")
    assert ok is True
    assert int(am_player.command_points or 0) == 9
    assert bool(officer.special_rules.get("mechanised_vox_relay_active", False)) is True
    assert str(officer.special_rules.get("mechanised_vox_relay_transport_id", "") or "") == str(get_entity_id(transport) or "")


def test_rapid_dispersal_queues_move_request_with_d6_distance():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    transport = _make_unit("Chimera", keywords=["VEHICLE", "TRANSPORT"], wounds=10)
    infantry = _make_unit("Shock Troops", keywords=["INFANTRY", "REGIMENT"])
    transport.transport_capacity = 12
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = set()

    am_army.add_unit(transport)
    am_army.add_unit(infantry)
    _deploy_unit(game, transport, 10.0, 10.0)
    _deploy_unit(game, infantry, 13.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _mark_disembarked(game, am_player, infantry, transport, phase_name="MOVEMENT_PHASE")
    _set_phase(game, am_player, "MOVEMENT_PHASE", 0)

    with patch("warhammer40k_ai.rules.stratagems_astra_militarum.get_roll", return_value=4):
        ok = am_player.stratagems.use("RAPID DISPERSAL", unit=infantry, phase_name="Movement phase")
    assert ok is True
    request = _find_request(game, DECISION_MOVE_UNIT)
    assert request is not None
    ctx = dict(getattr(request, "context", {}) or {})
    assert int(ctx.get("max_distance", 0) or 0) == 4
    assert str(ctx.get("reactive_move_source", "") or "") == "RAPID DISPERSAL"


def test_clear_and_secure_grants_ranged_full_rerolls_vs_targets_within_objective_range():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    transport = _make_unit("Chimera", keywords=["VEHICLE", "TRANSPORT"], wounds=10)
    infantry = _make_unit("Kasrkin", keywords=["INFANTRY", "REGIMENT"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    transport.transport_capacity = 12
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = set()

    am_army.add_unit(transport)
    am_army.add_unit(infantry)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, transport, 10.0, 10.0)
    _deploy_unit(game, infantry, 13.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _mark_disembarked(game, am_player, infantry, transport, phase_name="MOVEMENT_PHASE")
    _set_phase(game, am_player, "SHOOTING_PHASE", 0)
    enemy.is_within_any_objective_range = lambda game_map=None: True

    ok = am_player.stratagems.use("CLEAR AND SECURE", unit=infantry, phase_name="Shooting phase")
    assert ok is True

    detachment_mgr = am_army.astra_militarum_detachments
    hit_mods = detachment_mgr.mechanised_assault_clear_and_secure_hit_reroll_mods(
        infantry.models[0],
        enemy,
        attack_type="ranged",
        game=game,
    )
    wound_mods = detachment_mgr.mechanised_assault_clear_and_secure_wound_reroll_mods(
        infantry.models[0],
        enemy,
        attack_type="ranged",
        game=game,
    )
    assert bool(hit_mods.get("reroll_full", False)) is True
    assert bool(wound_mods.get("reroll_full", False)) is True

    enemy.is_within_any_objective_range = lambda game_map=None: False
    assert detachment_mgr.mechanised_assault_clear_and_secure_hit_reroll_mods(
        infantry.models[0],
        enemy,
        attack_type="ranged",
        game=game,
    ) == {}

    _set_phase(game, am_player, "FIGHT_PHASE", 0)
    enemy.is_within_any_objective_range = lambda game_map=None: True
    assert detachment_mgr.mechanised_assault_clear_and_secure_wound_reroll_mods(
        infantry.models[0],
        enemy,
        attack_type="ranged",
        game=game,
    ) == {}


def test_swift_interception_queues_reactive_move_after_enemy_move_end():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    transport = _make_unit("Chimera", keywords=["VEHICLE", "TRANSPORT"], wounds=10)
    enemy = _make_unit("Enemy Movers", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    transport.transport_capacity = 12
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = set()

    am_army.add_unit(transport)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, transport, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")

    pending = _pending_by_name(am_player.stratagems, "SWIFT INTERCEPTION")
    assert pending is not None
    assert transport in list(pending.get("candidates") or [])

    ok = am_player.stratagems.use(
        "SWIFT INTERCEPTION",
        unit=transport,
        enemy_unit=enemy,
        action="move",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True

    request = _find_request(game, DECISION_MOVE_UNIT)
    assert request is not None
    ctx = dict(getattr(request, "context", {}) or {})
    assert int(ctx.get("max_distance", 0) or 0) == 6
    assert str(ctx.get("reactive_move_source", "") or "") == "SWIFT INTERCEPTION"


def test_hasty_extraction_embarks_target_and_charge_continues_against_remaining_original_targets():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    charger = _make_unit("Enemy Chargers", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    transport = _make_unit("Chimera", keywords=["VEHICLE", "TRANSPORT"], wounds=10)
    target = _make_unit("Shock Troops", keywords=["INFANTRY", "REGIMENT"])
    replacement = _make_unit("Kasrkin", keywords=["INFANTRY", "REGIMENT"])
    transport.transport_capacity = 12
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = set()

    enemy_army.add_unit(charger)
    am_army.add_unit(transport)
    am_army.add_unit(target)
    am_army.add_unit(replacement)
    _deploy_unit(game, charger, 6.0, 10.0)
    _deploy_unit(game, transport, 17.0, 10.0)
    _deploy_unit(game, target, 14.8, 10.0)
    _deploy_unit(game, replacement, 14.5, 12.5)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])
    game.map.is_path_blocked = lambda *_args, **_kwargs: False
    game.map.is_within_engagement_range = lambda *_args, **_kwargs: False

    charger._can_declare_charge_base = lambda _game, out_of_turn=False: True
    charger.can_declare_charge_against = (
        lambda unit, _game, out_of_turn=False: unit is target or unit is replacement
    )

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    declared = game.declare_charge(charger, [target, replacement])
    assert declared is not None
    assert _pending_by_name(am_player.stratagems, "HASTY EXTRACTION") is not None

    ok = am_player.stratagems.use(
        "HASTY EXTRACTION",
        charging_unit=charger,
        target_units=[target, replacement],
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok is True

    embark_request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="mechanised_hasty_extraction")
    assert embark_request is not None
    option = _find_option_by_payload(
        embark_request,
        target_unit_id=str(get_entity_id(target) or ""),
        transport_id=str(get_entity_id(transport) or ""),
    )
    assert option is not None

    result = resolve_decision_command(game, embark_request, option.option_id, player_id=am_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert target.embarked_in is transport
    assert target in list(getattr(transport, "transport_passengers", []) or [])
    assert _find_request(game, DECISION_DECLARE_CHARGE, reason="emergency_combat_embarkation") is None

    continued_charge = getattr(result, "value", None)
    assert bool(getattr(continued_charge, "ok", False)) is True
    charge_outcome = dict(getattr(continued_charge, "value", {}) or {})
    assert list(charge_outcome.get("target_unit_ids", []) or []) == [str(get_entity_id(replacement) or "")]
    assert set(getattr(charger.round_state, "charge_target_ids", set()) or set()) == {str(get_entity_id(replacement) or "")}

    move_request = _find_request(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    move_ctx = dict(getattr(move_request, "context", {}) or {})
    assert list(move_ctx.get("target_unit_ids", []) or []) == [str(get_entity_id(replacement) or "")]


def test_move_out_queues_end_of_turn_embark_and_allows_existing_passengers():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    transport = _make_unit("Chimera", keywords=["VEHICLE", "TRANSPORT"], wounds=10)
    infantry = _make_unit("Shock Troops", keywords=["INFANTRY", "REGIMENT"])
    existing = _make_unit("Embarked Unit", keywords=["INFANTRY", "REGIMENT"])
    transport.transport_capacity = 12
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = set()
    transport.transport_passengers = [existing]
    existing.embarked_in = transport
    existing.reserve_status = "embarked"

    am_army.add_unit(transport)
    am_army.add_unit(infantry)
    am_army.add_unit(existing)
    _deploy_unit(game, transport, 10.0, 10.0)
    _deploy_unit(game, infantry, 12.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = _pending_by_name(am_player.stratagems, "MOVE OUT")
    assert pending is not None

    ok = am_player.stratagems.use(
        "MOVE OUT",
        unit=infantry,
        transport_unit=transport,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True

    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="mechanised_turn_end_embark")
    assert request is not None
    option = _find_option_by_payload(
        request,
        target_unit_id=str(get_entity_id(infantry) or ""),
        transport_id=str(get_entity_id(transport) or ""),
    )
    assert option is not None

    result = resolve_decision_command(game, request, option.option_id, player_id=am_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert infantry.embarked_in is transport
    passengers = list(getattr(transport, "transport_passengers", []) or [])
    assert existing in passengers
    assert infantry in passengers
