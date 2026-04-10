from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
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
    unit.round_state.fought_this_phase = False
    unit.round_state.moved_this_round = False
    unit.round_state.advanced_this_round = False
    unit.round_state.fell_back_this_round = False
    unit.round_state.disembarked_this_round = False
    unit.round_state.disembarked_cannot_charge = False
    unit.round_state.embarked_this_round = False
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.auto_resolve_dice_rolls = False

    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Haloscreed Battle Clade")
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
    return game, admech_army, enemy_army, admech_player, enemy_player


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    assert placed, f"Failed to place {getattr(unit, 'name', 'Unit')}"


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


def _find_move_request(game: Game, *, kind: str):
    wanted = str(kind or "").strip()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_MOVE_UNIT:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("reactive_move_kind", "") or "").strip() != wanted:
            continue
        return request
    return None


def _set_halo_override(mgr, unit: Unit, *, choice_key: str = "ELECTROMOTIVE_ENERGISATION") -> None:
    mgr.active_noospheric_unit_ids = [str(get_entity_id(unit.get_attached_unit_root()) or "")]
    mgr.active_noospheric_override_key = str(choice_key)


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


def _melee_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_haloscreed_stratagem_descriptors_registered():
    expected = {
        "000009746002": ("Eradication Protocols", "reroll_wound_ones_with_halo_hit_reroll_ones"),
        "000009746003": ("Targeting Override", "critical_hits_on_five_plus"),
        "000009746004": ("Neural Overload", "grant_selected_halo_override_ability"),
        "000009746005": ("Aggressive Impulse", "disembark_charge_after_normal_move"),
        "000009746006": ("Guided Retreat", "shoot_and_charge_after_fall_back"),
        "000009746007": ("Analytical Divination", "reactive_normal_move_d6_or_six_if_halo_override"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_haloscreed_neural_overload_choice_decision_returns_choice_key():
    game, _admech_army, _enemy_army, admech_player, _enemy_player = _build_game()
    request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Select a HALO OVERRIDE ability.",
        player_id=admech_player.id,
        options=[
            DecisionOption.create(
                "Predation Protocols",
                payload={"choice_key": "PREDATION_PROTOCOLS"},
            )
        ],
        context={
            "ability": "haloscreed_neural_overload_choice",
            "ability_name": "Neural Overload",
            "allowed_choice_keys": ["PREDATION_PROTOCOLS", "MUTED_SERVOMOTORS"],
            "optional": False,
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=admech_player.id,
        option_id=str(request.options[0].option_id),
        payload={},
    )

    apply_result = dispatch_decision(game, request, result)
    assert apply_result.ok is True
    assert apply_result.value == {
        "choice_key": "PREDATION_PROTOCOLS",
        "choice_label": "Predation Protocols",
    }


def test_haloscreed_neural_overload_choice_rejects_invalid_choice():
    game, _admech_army, _enemy_army, admech_player, _enemy_player = _build_game()
    request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Select a HALO OVERRIDE ability.",
        player_id=admech_player.id,
        options=[
            DecisionOption.create(
                "Invalid Choice",
                payload={"choice_key": "INVALID_PROTOCOL"},
            )
        ],
        context={
            "ability": "haloscreed_neural_overload_choice",
            "ability_name": "Neural Overload",
            "allowed_choice_keys": ["PREDATION_PROTOCOLS"],
            "optional": False,
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=admech_player.id,
        option_id=str(request.options[0].option_id),
        payload={},
    )

    apply_result = dispatch_decision(game, request, result)
    assert apply_result.ok is False
    assert any("not an eligible candidate" in str(err).lower() for err in list(apply_result.errors or []))


def test_haloscreed_eradication_protocols_grants_reroll_ones_in_enemy_fight_phase():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    attacker = _make_unit(
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
    admech_army.add_unit(attacker)
    enemy_army.add_unit(target)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, target, 11.5, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    mgr = admech_army.adeptus_mechanicus_detachments
    _set_halo_override(mgr, attacker)
    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)

    ok = admech_player.stratagems.use(
        "ERADICATION PROTOCOLS",
        unit=attacker,
        phase_name="Fight phase",
    )
    assert ok is True

    hit_mods = attacker.get_model_hit_reroll_modifiers(attacker.models[0], attack_type="melee", target=target)
    wound_mods = attacker.get_model_wound_reroll_modifiers(
        attacker.models[0],
        attack_type="melee",
        target=target,
    )
    assert 1 in tuple(hit_mods.get("reroll_hit_values", ()) or ())
    assert 1 in tuple(wound_mods.get("reroll_wound_values", ()) or ())


def test_haloscreed_targeting_override_sets_crit_threshold_in_enemy_fight_phase():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    attacker = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    target = _make_unit(
        "Enemy Assault Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(attacker)
    enemy_army.add_unit(target)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, target, 11.5, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = admech_player.stratagems.use(
        "TARGETING OVERRIDE",
        unit=attacker,
        phase_name="Fight phase",
    )
    assert ok is True

    hit_result = _melee_profile()._hit_target_with_tracking(
        target,
        attacker.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(hit_result.get("crit_threshold", 0) or 0) == 5
    assert bool(hit_result.get("hit")) is True


def test_haloscreed_neural_overload_non_halo_grants_selected_override():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    unit = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, admech_player, "MOVEMENT_PHASE", 0)
    ok = admech_player.stratagems.use(
        "NEURAL OVERLOAD",
        unit=unit,
        choice_key="PREDATION_PROTOCOLS",
        phase_name="Movement phase",
    )
    assert ok is True

    mgr = admech_army.adeptus_mechanicus_detachments
    assert mgr.haloscreed_active_override_keys(unit, game=game) == ("PREDATION_PROTOCOLS",)
    assert unit.can_charge_after_advance() is True


def test_haloscreed_neural_overload_halo_unit_stacks_and_suffers_mortal_wounds():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    unit = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    mgr = admech_army.adeptus_mechanicus_detachments
    _set_halo_override(mgr, unit, choice_key="ELECTROMOTIVE_ENERGISATION")
    _set_phase(game, admech_player, "MOVEMENT_PHASE", 0)

    captured = {}

    def _capture_mortals(target_unit, amount, game_map=None):
        captured["target"] = target_unit
        captured["amount"] = int(amount)
        return 0

    with patch("warhammer40k_ai.rules.stratagems_adeptus_mechanicus.dice_module.get_roll", return_value=2), patch.object(
        unit,
        "_apply_mortal_wounds_to_unit",
        side_effect=_capture_mortals,
    ):
        ok = admech_player.stratagems.use(
            "NEURAL OVERLOAD",
            unit=unit,
            choice_key="MUTED_SERVOMOTORS",
            phase_name="Movement phase",
        )
    assert ok is True
    assert captured == {"target": unit, "amount": 2}
    assert set(mgr.haloscreed_active_override_keys(unit, game=game)) == {
        "ELECTROMOTIVE_ENERGISATION",
        "MUTED_SERVOMOTORS",
    }


def test_haloscreed_aggressive_impulse_allows_charge_after_disembark_from_normal_move():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    transport = _make_unit(
        "Skorpius Dunerider",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        wounds=10,
        transport="Transport Capacity 12",
    )
    passenger = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(transport)
    admech_army.add_unit(passenger)
    _deploy_unit(game, transport, 10.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport
    passenger.reserve_status = "embarked"
    _set_phase(game, admech_player, "MOVEMENT_PHASE", 0)

    ok = admech_player.stratagems.use(
        "AGGRESSIVE IMPULSE",
        unit=transport,
        phase_name="Movement phase",
    )
    assert ok is True

    transport.round_state.moved_this_round = True
    with patch.object(
        passenger,
        "_find_disembark_positions",
        return_value=[(12.0, 10.0, 0.0, 0.0)],
    ), patch.object(game.map, "place_unit", return_value=True):
        disembarked = passenger.disembark(game_map=game.map, transport_unit=transport, current_turn=game.turn)
    assert disembarked is True
    assert passenger.round_state.disembarked_cannot_charge is False


def test_haloscreed_guided_retreat_reaction_and_effects_include_desperate_escape_reroll():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    unit = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    mgr = admech_army.adeptus_mechanicus_detachments
    _set_halo_override(mgr, unit)
    unit.round_state.fell_back_this_round = True
    _set_phase(game, admech_player, "MOVEMENT_PHASE", 0)

    game.event_system.publish("unit_move_ended", unit=unit, action="fall_back")
    pending = _pending_by_name(admech_player.stratagems, "GUIDED RETREAT")
    assert pending is not None

    ok = admech_player.stratagems.use("GUIDED RETREAT", phase_name="Movement phase")
    assert ok is True
    assert unit.can_shoot_after_fall_back(_ranged_profile()) is True
    assert unit.can_charge_after_fall_back() is True

    with patch(
        "warhammer40k_ai.units.unit_mixins.late_gameplay_mixin.get_roll",
        side_effect=[1, 4],
    ):
        models_destroyed = unit.take_desperate_escape_test(game_map=game.map)
    assert models_destroyed == 0
    assert len(list(unit.models or [])) == 1


def test_haloscreed_analytical_divination_reaction_queues_reactive_move():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    unit = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Intercessors",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    mgr = admech_army.adeptus_mechanicus_detachments
    _set_halo_override(mgr, unit)
    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)

    game.event_system.publish("unit_move_ended", unit=enemy, action="advance")
    pending = _pending_by_name(admech_player.stratagems, "ANALYTICAL DIVINATION")
    assert pending is not None

    ok = admech_player.stratagems.use("ANALYTICAL DIVINATION", phase_name="Movement phase")
    assert ok is True

    request = _find_move_request(game, kind="haloscreed_analytical_divination")
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 6
    assert str(context.get("reactive_move_kind", "") or "") == "haloscreed_analytical_divination"
