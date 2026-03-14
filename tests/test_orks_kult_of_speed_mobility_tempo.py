from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Orks",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        movement: str = "10",
        toughness: str = "5",
        wounds: str = "4",
        leadership: str = "7",
        objective_control: str = "1",
        abilities=None,
        transport: str = "",
    ) -> None:
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(movement),
                "T": str(toughness),
                "Sv": "4",
                "W": str(wounds),
                "Ld": str(leadership),
                "OC": str(objective_control),
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Orks",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    movement: str = "10",
    toughness: str = "5",
    wounds: str = "4",
    leadership: str = "7",
    objective_control: str = "1",
    abilities=None,
    transport: str = "",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
            abilities=abilities,
            transport=transport,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, detachment: str, ork_units: list[Unit], enemy_units: list[Unit]):
    ork_army = Army("Orks", detachment)
    ork_army.faction_id = "ORK"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)

    ork_player = Player("Ork Player", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0

    ork_player.command_points = 20
    enemy_player.command_points = 20
    ork_army.configure_rule_managers(force=True)
    ork_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, ork_player, enemy_player, ork_army, enemy_army


def _set_phase(game: Game, *, phase_name, current_player_index: int, active_player: Player) -> None:
    game.phase = phase_name
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=active_player, phase=phase_name)


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    assert placed, f"failed to place {getattr(unit, 'name', 'Unit')}"
    game.rebuild_entity_registry()


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)


def _apply_kult_of_speed_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> Enhancement:
    get_parent_army = getattr(unit, "get_parent_army", None)
    parent_army = get_parent_army() if callable(get_parent_army) else None
    if parent_army is None:
        parent_army = Army("Orks", "Kult of Speed")
        parent_army.faction_id = "ORK"
        parent_army.add_unit(unit)
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="ORK",
        detachment="Kult of Speed",
        points=0,
        description=str(enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _embark(transport: Unit, passenger: Unit) -> None:
    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport


def _find_reactive_move_request(game: Game, *, kind: str, source_contains: str = ""):
    wanted_kind = str(kind or "").strip()
    source_filter = str(source_contains or "").strip().lower()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_MOVE_UNIT:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("reactive_move_kind", "") or "").strip() != wanted_kind:
            continue
        if source_filter and source_filter not in str(context.get("reactive_move_source", "") or "").strip().lower():
            continue
        return request
    return None


def _find_confirm_option(request):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "") == "confirm":
            return option
    return None


def _current_stratagem_name(player: Player, canonical_name: str) -> str:
    expected = str(canonical_name or "").strip().upper()
    for stratagem in list(player.stratagems.available or []):
        name = str(getattr(stratagem, "name", "") or "").strip()
        if name.upper() == expected:
            return name
    raise AssertionError(f"Missing stratagem '{canonical_name}'.")


def _pending_reaction_by_name(player: Player, name: str):
    expected = str(name or "").strip().lower().replace("\u2019", "'")
    for reaction in list(player.stratagems.get_pending_reactions() or []):
        reaction_name = str(reaction.get("stratagem", "") or "").strip().lower().replace("\u2019", "'")
        if reaction_name == expected:
            return reaction
    return None


def _assault_vehicle_ability() -> dict:
    return {
        "name": "Assault Vehicle",
        "description": (
            "Units can disembark from this TRANSPORT after it has Advanced. "
            "Units that do so count as having made a Normal move that phase, and cannot declare a charge "
            "in the same turn, but can otherwise act normally."
        ),
        "type": "Datasheet",
        "parameter": "",
    }


def _make_melee_profile(*, strength: str = "4") -> WargearProfile:
    parent = SimpleNamespace(name="Choppa", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Profile",
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_kult_of_speed_mobility_tempo_descriptors_registered():
    enhancement_expected = {
        "000008872002": ("Fasta Than Yooz", "allow_charge_after_disembark_from_transport_normal_move"),
        "000008872004": ("Squig-hide Tyres", "bearer_unit_consolidate_distance_override"),
        "000008872005": ("Wazblasta", "post_shoot_reactive_normal_move_no_charge"),
    }
    for enhancement_id, (name, effect) in sorted(enhancement_expected.items()):
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect

    stratagem = get_stratagem_tool_descriptor(stratagem_id="000008873006")
    assert stratagem is not None
    assert str(getattr(stratagem, "name", "") or "") == "FULL THROTTLE!"
    assert str(getattr(stratagem, "effect", "") or "") == "melee_wound_bonus"


def test_fasta_than_yooz_allows_charge_after_disembark_from_transport_normal_move():
    game, _ork_player, _enemy_player, ork_army, enemy_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[],
        enemy_units=[],
    )
    transport = _make_unit(
        "Trukk",
        keywords=["ORKS", "VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        transport="Transport Capacity 12",
    )
    passenger = _make_unit(
        "Boyz",
        keywords=["ORKS", "INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ork_army.add_unit(transport)
    ork_army.add_unit(passenger)
    enemy_army.add_unit(enemy)

    _apply_kult_of_speed_enhancement(passenger, enhancement_id="000008872002", enhancement_name="Fasta Than Yooz")

    _set_unit_location(transport, x=10.0, y=10.0)
    _set_unit_location(enemy, x=20.0, y=10.0)
    game.map.place_unit(transport)
    game.map.place_unit(enemy)

    transport.round_state.moved_this_round = True
    transport.round_state.remained_stationary_this_round = False
    _embark(transport, passenger)

    ok = passenger.disembark(game_map=game.map, transport_unit=transport, current_turn=1)
    assert ok is True
    assert bool(passenger.round_state.disembarked_from_moved_transport) is True
    assert bool(passenger.round_state.disembarked_cannot_charge) is False
    assert passenger.can_declare_charge_against(enemy, game) is True


def test_fasta_than_yooz_does_not_apply_to_non_infantry_bearer():
    warbikers = _make_unit(
        "Warbikers",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
    )
    _apply_kult_of_speed_enhancement(warbikers, enhancement_id="000008872002", enhancement_name="Fasta Than Yooz")

    rules = dict(getattr(warbikers, "special_rules", {}) or {})
    assert not bool(rules.get("enhancement_kult_of_speed_fasta_than_yooz", False))


def test_fasta_than_yooz_does_not_override_advanced_transport_disembark_charge_lockout():
    game, _ork_player, _enemy_player, ork_army, enemy_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[],
        enemy_units=[],
    )
    transport = _make_unit(
        "Trukk",
        keywords=["ORKS", "VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        abilities=[_assault_vehicle_ability()],
        transport="Transport Capacity 12",
    )
    passenger = _make_unit(
        "Boyz",
        keywords=["ORKS", "INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ork_army.add_unit(transport)
    ork_army.add_unit(passenger)
    enemy_army.add_unit(enemy)

    _apply_kult_of_speed_enhancement(passenger, enhancement_id="000008872002", enhancement_name="Fasta Than Yooz")

    _set_unit_location(transport, x=10.0, y=10.0)
    _set_unit_location(enemy, x=20.0, y=10.0)
    game.map.place_unit(transport)
    game.map.place_unit(enemy)

    transport.round_state.moved_this_round = True
    transport.round_state.remained_stationary_this_round = False
    transport.round_state.advanced_this_round = True
    _embark(transport, passenger)

    ok = passenger.disembark(game_map=game.map, transport_unit=transport, current_turn=1)
    assert ok is True
    assert bool(passenger.round_state.disembarked_from_moved_transport) is True
    assert bool(passenger.round_state.disembarked_cannot_charge) is True
    assert passenger.can_declare_charge_against(enemy, game) is False


def test_squig_hide_tyres_sets_consolidate_override_to_six_inches():
    wartrike = _make_unit(
        "Deffkilla Wartrike",
        keywords=["ORKS", "VEHICLE", "CHARACTER", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
        movement="12",
        toughness="7",
        wounds="9",
    )
    _apply_kult_of_speed_enhancement(wartrike, enhancement_id="000008872004", enhancement_name="Squig-hide Tyres")

    consolidate_rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=wartrike)
    assert float(consolidate_rules.get("max_distance_override") or 0.0) == 6.0


def test_squig_hide_tyres_affects_only_consolidate_distance():
    wartrike = _make_unit(
        "Deffkilla Wartrike",
        keywords=["ORKS", "VEHICLE", "CHARACTER", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
        movement="12",
        toughness="7",
        wounds="9",
    )
    _apply_kult_of_speed_enhancement(wartrike, enhancement_id="000008872004", enhancement_name="Squig-hide Tyres")

    pile_in_rules = get_validation_rules(MovementType.PILE_IN, moving_unit=wartrike)
    assert float(pile_in_rules.get("max_distance_override") or 0.0) == 3.0

    consolidate_rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=wartrike)
    assert float(consolidate_rules.get("max_distance_override") or 0.0) == 6.0


def test_squig_hide_tyres_does_not_apply_to_wrong_bearer():
    warbikers = _make_unit(
        "Warbikers",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
    )
    _apply_kult_of_speed_enhancement(warbikers, enhancement_id="000008872004", enhancement_name="Squig-hide Tyres")

    rules = dict(getattr(warbikers, "special_rules", {}) or {})
    assert not bool(rules.get("enhancement_kult_of_speed_squig_hide_tyres", False))
    consolidate_rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=warbikers)
    assert float(consolidate_rules.get("max_distance_override") or 0.0) == 3.0


def test_wazblasta_queues_post_shoot_reactive_move_and_blocks_charge_after_move():
    wartrike = _make_unit(
        "Deffkilla Wartrike",
        keywords=["ORKS", "VEHICLE", "CHARACTER", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
        movement="12",
        toughness="7",
        wounds="9",
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, ork_army, enemy_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[wartrike],
        enemy_units=[enemy],
    )
    _deploy_unit(game, wartrike, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)

    _apply_kult_of_speed_enhancement(wartrike, enhancement_id="000008872005", enhancement_name="Wazblasta")

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game._on_unit_shooting_resolved_tactical_acumen(attacker_unit=wartrike, hits_by_target={enemy: 1})

    request = _find_reactive_move_request(game, kind="post_shoot_no_charge", source_contains="Wazblasta")
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 6

    confirm_option = _find_confirm_option(request)
    assert confirm_option is not None
    outcome = resolve_decision_command(
        game,
        request,
        confirm_option.option_id,
        result_payload={
            "model_positions": [
                {
                    "model_id": get_entity_id(wartrike.models[0]),
                    "position": [0.0, 0.0, 0.0],
                    "facing": 0.0,
                }
            ]
        },
        player_id=ork_player.id,
    )
    assert bool(getattr(outcome, "ok", False)) is True

    rules = dict(getattr(wartrike, "special_rules", {}) or {})
    assert str(rules.get("tactical_acumen_no_charge_turn_owner", "") or "") == ork_player.id
    assert int(rules.get("tactical_acumen_no_charge_turn", 0) or 0) == game.turn

    game.phase = BattleRoundPhases.CHARGE_PHASE
    assert wartrike.can_declare_charge_against(enemy, game) is False


def test_wazblasta_does_not_queue_while_within_engagement_range():
    wartrike = _make_unit(
        "Deffkilla Wartrike",
        keywords=["ORKS", "VEHICLE", "CHARACTER", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
        movement="12",
        toughness="7",
        wounds="9",
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, _ork_player, _enemy_player, ork_army, enemy_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[wartrike],
        enemy_units=[enemy],
    )
    _deploy_unit(game, wartrike, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.9, 10.0)

    _apply_kult_of_speed_enhancement(wartrike, enhancement_id="000008872005", enhancement_name="Wazblasta")

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game._on_unit_shooting_resolved_tactical_acumen(attacker_unit=wartrike, hits_by_target={enemy: 1})

    request = _find_reactive_move_request(game, kind="post_shoot_no_charge", source_contains="Wazblasta")
    assert request is None


def test_wazblasta_does_not_apply_to_wrong_bearer():
    warbikers = _make_unit(
        "Warbikers",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, _ork_player, _enemy_player, ork_army, enemy_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[warbikers],
        enemy_units=[enemy],
    )
    _deploy_unit(game, warbikers, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)

    _apply_kult_of_speed_enhancement(warbikers, enhancement_id="000008872005", enhancement_name="Wazblasta")

    rules = dict(getattr(warbikers, "special_rules", {}) or {})
    assert not bool(rules.get("enhancement_kult_of_speed_wazblasta", False))

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game._on_unit_shooting_resolved_tactical_acumen(attacker_unit=warbikers, hits_by_target={enemy: 1})

    request = _find_reactive_move_request(game, kind="post_shoot_no_charge", source_contains="Wazblasta")
    assert request is None


def test_full_throttle_queues_after_speed_freeks_charge_and_expires_at_end_of_turn():
    warbikers = _make_unit(
        "Warbikers",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
        toughness="5",
        wounds="3",
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    game, ork_player, enemy_player, ork_army, enemy_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[warbikers],
        enemy_units=[enemy],
    )
    _deploy_unit(game, warbikers, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    _set_phase(
        game,
        phase_name=BattleRoundPhases.CHARGE_PHASE,
        current_player_index=0,
        active_player=ork_player,
    )

    game.event_system.publish("unit_move_ended", unit=warbikers, action="charge")

    stratagem_name = _current_stratagem_name(ork_player, "FULL THROTTLE!")
    pending = _pending_reaction_by_name(ork_player, stratagem_name)
    assert pending is not None

    cp_before = int(ork_player.command_points or 0)
    ok = ork_player.stratagems.use(stratagem_name, unit=warbikers, dequeue=True)
    assert ok is True
    assert int(ork_player.command_points or 0) == cp_before - 1

    game.phase = BattleRoundPhases.FIGHT_PHASE
    melee_profile = _make_melee_profile(strength="4")
    wound_result = melee_profile._wound_target_with_tracking(
        enemy,
        warbikers.models[0],
        attack_instance={},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound_result.get("wound", False)) is True
    assert any("FULL THROTTLE" in str(reason).upper() for reason in list(wound_result.get("modifiers", []) or []))

    game.current_player_index = 1
    wound_result_opponent_turn = melee_profile._wound_target_with_tracking(
        enemy,
        warbikers.models[0],
        attack_instance={},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound_result_opponent_turn.get("wound", False)) is False

    game.current_player_index = 0
    game.turn = 2
    wound_result_next_turn = melee_profile._wound_target_with_tracking(
        enemy,
        warbikers.models[0],
        attack_instance={},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound_result_next_turn.get("wound", False)) is False


def test_full_throttle_rejects_wrong_phase():
    warbikers = _make_unit(
        "Warbikers",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, ork_army, enemy_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[warbikers],
        enemy_units=[enemy],
    )
    _deploy_unit(game, warbikers, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    warbikers.round_state.charged_this_round = True

    stratagem_name = _current_stratagem_name(ork_player, "FULL THROTTLE!")
    assert ork_player.stratagems.use(
        stratagem_name,
        unit=warbikers,
        action="charge",
        phase_name="Movement phase",
    ) is False


def test_full_throttle_rejects_non_speed_freeks_target():
    boyz = _make_unit(
        "Boyz",
        keywords=["ORKS", "INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, enemy_player, ork_army, enemy_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[boyz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, boyz, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    _set_phase(
        game,
        phase_name=BattleRoundPhases.CHARGE_PHASE,
        current_player_index=0,
        active_player=ork_player,
    )
    boyz.round_state.charged_this_round = True

    stratagem_name = _current_stratagem_name(ork_player, "FULL THROTTLE!")
    assert ork_player.stratagems.use(
        stratagem_name,
        unit=boyz,
        action="charge",
        phase_name="Charge phase",
    ) is False
