from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        movement: str = "10",
        toughness: str = "6",
        save: str = "4",
        wounds: str = "6",
    ):
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Orks" if "ORKS" in [str(k).upper() for k in list(faction_keywords or [])] else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": str(save),
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    movement: str = "10",
    toughness: str = "6",
    save: str = "4",
    wounds: str = "6",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            toughness=toughness,
            save=save,
            wounds=wounds,
        )
    )


def _build_game(*, detachment: str, ork_units: list[Unit], enemy_units: list[Unit]):
    ork_army = Army("Orks", detachment)
    ork_army.faction_id = "ORK"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)

    ork_player = Player("Ork Player", control=PlayerControl.LOCAL, army=ork_army)
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
    return game, ork_player, enemy_player


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    assert game.map.place_unit(unit), f"failed to place {getattr(unit, 'name', 'Unit')}"


def _set_unit_location(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)


def _set_phase(game: Game, *, phase_name: str, current_player_index: int, active_player: Player) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=active_player, phase=phase)


def _normalize_name(value: str) -> str:
    return str(value or "").strip().lower().replace("\u2019", "'")


def _resolve_available_stratagem_name(player: Player, expected_name: str) -> str:
    expected = _normalize_name(expected_name)
    for stratagem in list(player.stratagems.available or []):
        name = str(getattr(stratagem, "name", "") or "")
        if _normalize_name(name) == expected:
            return name
    return expected_name


def _pending_by_name(player: Player, expected_name: str):
    expected = _normalize_name(expected_name)
    for reaction in list(player.stratagems.get_pending_reactions() or []):
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == expected:
            return reaction
    return None


def _first_move_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if getattr(req, "decision_type", None) == DECISION_MOVE_UNIT:
            return req
    return None


def _confirm_move_result(request, unit: Unit, *, x: float, y: float) -> DecisionResult:
    confirm = next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((getattr(opt, "payload", {}) or {}).get("action", "") or "") == "confirm"
    )
    model = unit.models[0]
    return DecisionResult(
        decision_id=request.decision_id,
        player_id=request.player_id,
        option_id=confirm.option_id,
        payload={
            "model_positions": [
                {
                    "model_id": get_entity_id(model),
                    "position": [float(x), float(y), 0.0],
                    "facing": 0.0,
                }
            ]
        },
    )


def test_orks_reactive_reposition_helper_tracks_start_phase_engagement_and_sorts():
    target_a = _make_unit("Alpha Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    target_b = _make_unit("Beta Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Taktikal Brigade",
        ork_units=[target_b, target_a],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target_a, 10.0, 10.0)
    _deploy_unit(game, target_b, 14.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)

    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)
    mgr = ork_player.stratagems
    start_candidates = mgr._orks_start_phase_engaged_candidates_for_enemy(enemy)
    assert [str(get_entity_id(unit) or "") for unit in start_candidates] == sorted(
        [str(get_entity_id(target_a) or ""), str(get_entity_id(target_b) or "")]
    )

    _set_unit_location(enemy, 25.0, 10.0)
    candidates = mgr._orks_reactive_reposition_candidates(
        enemy_unit=enemy,
        target_matcher=mgr._is_orks_unit,
        require_start_phase_engaged=True,
        require_not_engaged_now=True,
        max_distance_to_enemy=None,
    )
    assert [str(get_entity_id(unit) or "") for unit in candidates] == sorted(
        [str(get_entity_id(target_a) or ""), str(get_entity_id(target_b) or "")]
    )


@pytest.mark.parametrize(
    ("detachment", "stratagem_name", "target_keywords", "reactive_kind"),
    [
        ("Da Big Hunt", "WHERE D'YA FINK YOU'RE GOING?", ["ORKS", "BEAST SNAGGA", "INFANTRY"], "where_dya_fink_youre_going"),
        ("Freebooter Krew", "KRUMP AND RUN", ["ORKS", "INFANTRY"], "krump_and_run"),
        ("Taktikal Brigade", "ON TO DA NEXT", ["ORKS", "INFANTRY"], "on_to_da_next"),
    ],
)
def test_fall_back_reactive_reposition_stratagems_queue_and_use(
    detachment: str,
    stratagem_name: str,
    target_keywords: list[str],
    reactive_kind: str,
):
    target = _make_unit("Reacting Unit", keywords=target_keywords, faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment=detachment,
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    _set_unit_location(enemy, 20.0, 10.0)
    game.event_system.publish("unit_move_ended", unit=enemy, action="fall_back")
    pending = _pending_by_name(ork_player, stratagem_name)
    assert pending is not None

    cp_before = int(ork_player.command_points or 0)
    ok = ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, stratagem_name),
        unit=target,
        moving_unit=enemy,
        action="fall_back",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(ork_player.command_points or 0) == cp_before - 1

    move_request = _first_move_request(game)
    assert move_request is not None
    context = dict(getattr(move_request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 6
    assert str(context.get("movement_type", "") or "") == "reactive"
    assert str(context.get("reactive_move_kind", "") or "") == reactive_kind
    assert str(context.get("reactive_move_moving_unit_id", "") or "") == str(get_entity_id(enemy) or "")


def test_more_gitz_over_ere_queues_and_uses_reactive_move():
    target = _make_unit(
        "Warbikers",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Kult of Speed",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    assert _pending_by_name(ork_player, "MORE GITZ OVER 'ERE!") is not None

    ok = ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "MORE GITZ OVER 'ERE!"),
        unit=target,
        moving_unit=enemy,
        action="move",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True

    move_request = _first_move_request(game)
    assert move_request is not None
    context = dict(getattr(move_request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 6
    assert str(context.get("reactive_move_kind", "") or "") == "more_gitz_over_ere"
    assert int(context.get("reactive_move_range", 0) or 0) == 9


def test_orks_reactive_move_pre_move_rider_helper_applies_d3_plus_1_mortals():
    target = _make_unit("Gretchin", keywords=["ORKS", "INFANTRY", "GRETCHIN"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Dread Mob",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    applied: list[tuple[Unit, int]] = []
    target._apply_mortal_wounds_to_unit = lambda unit, amount, game_map=None: applied.append((unit, int(amount or 0)))

    with patch(
        "warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll",
        side_effect=lambda die: 4 if str(die).strip().upper() == "D6" else 2,
    ):
        result = ork_player.stratagems._orks_resolve_reactive_move_pre_move_rider(
            unit=target,
            enemy_unit=enemy,
            source_name="CONNIVING RUNTS",
            rider_spec={
                "effect": "single_roll_mortal_wounds",
                "trigger_roll": "D6",
                "success_on": 4,
                "mortal_wounds": "D3+1",
            },
        )

    assert bool(result.get("success", False)) is True
    assert int(result.get("mortal_wounds", 0) or 0) == 3
    assert applied == [(enemy, 3)]


def test_conniving_runts_queues_mortal_rider_then_move_request():
    target = _make_unit("Gretchin", keywords=["ORKS", "INFANTRY", "GRETCHIN"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Dread Mob",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("unit_move_ended", unit=enemy, action="advance")
    assert _pending_by_name(ork_player, "CONNIVING RUNTS") is not None

    applied: list[tuple[Unit, int]] = []
    queued_snapshot: dict[str, object] = {}
    target._apply_mortal_wounds_to_unit = lambda unit, amount, game_map=None: applied.append((unit, int(amount or 0)))
    original_queue = game._queue_reactive_move_movement_decision

    def _capture_queue(**kwargs):
        queued_snapshot["applied"] = list(applied)
        return original_queue(**kwargs)

    game._queue_reactive_move_movement_decision = _capture_queue

    with patch(
        "warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll",
        side_effect=lambda die: 4 if str(die).strip().upper() == "D6" else 2,
    ):
        ok = ork_player.stratagems.use(
            _resolve_available_stratagem_name(ork_player, "CONNIVING RUNTS"),
            unit=target,
            moving_unit=enemy,
            action="advance",
            phase_name="Movement phase",
            dequeue=True,
        )

    assert ok is True
    assert queued_snapshot.get("applied") == [(enemy, 3)]
    assert applied == [(enemy, 3)]

    move_request = _first_move_request(game)
    assert move_request is not None
    context = dict(getattr(move_request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 6
    assert str(context.get("reactive_move_kind", "") or "") == "conniving_runts"
    assert str(context.get("reactive_move_movement_type", "") or "") == "move"
    assert int(context.get("reactive_move_range", 0) or 0) == 9
    rider_result = dict(context.get("pre_move_rider_result", {}) or {})
    assert bool(rider_result.get("success", False)) is True
    assert int(rider_result.get("mortal_wounds", 0) or 0) == 3


def test_conniving_runts_failed_roll_still_queues_normal_move():
    target = _make_unit("Gretchin", keywords=["ORKS", "INFANTRY", "GRETCHIN"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Dread Mob",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    assert _pending_by_name(ork_player, "CONNIVING RUNTS") is not None

    applied: list[tuple[Unit, int]] = []
    target._apply_mortal_wounds_to_unit = lambda unit, amount, game_map=None: applied.append((unit, int(amount or 0)))

    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=3):
        ok = ork_player.stratagems.use(
            _resolve_available_stratagem_name(ork_player, "CONNIVING RUNTS"),
            unit=target,
            moving_unit=enemy,
            action="move",
            phase_name="Movement phase",
            dequeue=True,
        )

    assert ok is True
    assert applied == []

    move_request = _first_move_request(game)
    assert move_request is not None
    rider_result = dict((move_request.context or {}).get("pre_move_rider_result", {}) or {})
    assert bool(rider_result.get("success", True)) is False
    assert int(rider_result.get("mortal_wounds", 0) or 0) == 0


def test_conniving_runts_negative_wrong_phase():
    target = _make_unit("Gretchin", keywords=["ORKS", "INFANTRY", "GRETCHIN"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Dread Mob",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    assert _pending_by_name(ork_player, "CONNIVING RUNTS") is None

    ok = ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "CONNIVING RUNTS"),
        unit=target,
        moving_unit=enemy,
        action="move",
        phase_name="Shooting phase",
    )
    assert ok is False


def test_conniving_runts_negative_wrong_unit_type():
    target = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Dread Mob",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    assert _pending_by_name(ork_player, "CONNIVING RUNTS") is None

    ok = ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "CONNIVING RUNTS"),
        unit=target,
        moving_unit=enemy,
        action="move",
        phase_name="Movement phase",
    )
    assert ok is False


def test_conniving_runts_negative_reacting_unit_must_be_within_nine():
    target = _make_unit("Gretchin", keywords=["ORKS", "INFANTRY", "GRETCHIN"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Dread Mob",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 25.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    assert _pending_by_name(ork_player, "CONNIVING RUNTS") is None


def test_conniving_runts_negative_requires_not_currently_engaged():
    target = _make_unit("Gretchin", keywords=["ORKS", "INFANTRY", "GRETCHIN"], faction_keywords=["ORKS"])
    enemy_trigger = _make_unit("Enemy Trigger", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_sticky = _make_unit("Enemy Sticky", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Dread Mob",
        ork_units=[target],
        enemy_units=[enemy_trigger, enemy_sticky],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy_trigger, 17.0, 10.0)
    _deploy_unit(game, enemy_sticky, 10.0, 12.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("unit_move_ended", unit=enemy_trigger, action="move")
    assert _pending_by_name(ork_player, "CONNIVING RUNTS") is None


def test_conniving_runts_negative_wrong_enemy_move_type():
    target = _make_unit("Gretchin", keywords=["ORKS", "INFANTRY", "GRETCHIN"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Dread Mob",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("unit_move_ended", unit=enemy, action="charge")
    assert _pending_by_name(ork_player, "CONNIVING RUNTS") is None

    ok = ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "CONNIVING RUNTS"),
        unit=target,
        moving_unit=enemy,
        action="charge",
        phase_name="Movement phase",
    )
    assert ok is False


def test_conniving_runts_move_request_uses_existing_movement_validation():
    target = _make_unit("Gretchin", keywords=["ORKS", "INFANTRY", "GRETCHIN"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Dread Mob",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=3):
        ok = ork_player.stratagems.use(
            _resolve_available_stratagem_name(ork_player, "CONNIVING RUNTS"),
            unit=target,
            moving_unit=enemy,
            action="move",
            phase_name="Movement phase",
            dequeue=True,
        )
    assert ok is True

    move_request = _first_move_request(game)
    assert move_request is not None
    apply_result = game.resolve_decision(_confirm_move_result(move_request, target, x=18.0, y=10.0))
    assert bool(getattr(apply_result, "ok", False)) is False
    assert list(getattr(apply_result, "errors", []) or [])


def test_orks_reactive_reposition_negative_wrong_trigger_action():
    target = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Freebooter Krew",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    _set_unit_location(enemy, 20.0, 10.0)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    assert _pending_by_name(ork_player, "KRUMP AND RUN") is None

    ok = ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "KRUMP AND RUN"),
        unit=target,
        moving_unit=enemy,
        action="move",
        phase_name="Movement phase",
    )
    assert ok is False


def test_orks_reactive_reposition_negative_wrong_unit_type():
    target = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Da Big Hunt",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    _set_unit_location(enemy, 20.0, 10.0)
    game.event_system.publish("unit_move_ended", unit=enemy, action="fall_back")
    assert _pending_by_name(ork_player, "WHERE D'YA FINK YOU'RE GOING?") is None

    ok = ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "WHERE D'YA FINK YOU'RE GOING?"),
        unit=target,
        moving_unit=enemy,
        action="fall_back",
        phase_name="Movement phase",
    )
    assert ok is False


def test_orks_reactive_reposition_negative_requires_not_currently_engaged():
    target = _make_unit(
        "Warbikers",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
    )
    enemy_trigger = _make_unit("Enemy Trigger", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_sticky = _make_unit("Enemy Sticky", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Kult of Speed",
        ork_units=[target],
        enemy_units=[enemy_trigger, enemy_sticky],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy_trigger, 11.8, 10.0)
    _deploy_unit(game, enemy_sticky, 10.0, 12.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    _set_unit_location(enemy_trigger, 17.0, 10.0)
    game.event_system.publish("unit_move_ended", unit=enemy_trigger, action="move")
    assert _pending_by_name(ork_player, "MORE GITZ OVER 'ERE!") is None


def test_orks_reactive_reposition_negative_movement_queue_failure():
    target = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Taktikal Brigade",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1, active_player=enemy_player)

    _set_unit_location(enemy, 20.0, 10.0)
    game.event_system.publish("unit_move_ended", unit=enemy, action="fall_back")
    assert _pending_by_name(ork_player, "ON TO DA NEXT") is not None

    game._queue_reactive_move_movement_decision = lambda **_kwargs: None
    ok = ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "ON TO DA NEXT"),
        unit=target,
        moving_unit=enemy,
        action="fall_back",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is False


def test_orks_reactive_reposition_stratagem_descriptors_present():
    where_dya = get_stratagem_tool_descriptor(stratagem_id="000008869005", name="WHERE D'YA FINK YOU'RE GOING?")
    krump = get_stratagem_tool_descriptor(stratagem_id="000010713007", name="KRUMP AND RUN")
    on_to_da_next = get_stratagem_tool_descriptor(stratagem_id="000009796006", name="ON TO DA NEXT")
    conniving = get_stratagem_tool_descriptor(stratagem_id="000008878006", name="CONNIVING RUNTS")
    more_gitz = get_stratagem_tool_descriptor(stratagem_id="000008873007", name="MORE GITZ OVER 'ERE!")

    assert where_dya is not None
    assert str(where_dya.effect) == "reactive_normal_move"
    assert str(where_dya.timing) == "opponent_movement_phase_after_enemy_fall_back"

    assert krump is not None
    assert str(krump.effect) == "reactive_normal_move"
    assert str(krump.timing) == "opponent_movement_phase_after_enemy_fall_back"

    assert on_to_da_next is not None
    assert str(on_to_da_next.effect) == "reactive_normal_move"
    assert str(on_to_da_next.timing) == "opponent_movement_phase_after_enemy_fall_back"

    assert conniving is not None
    assert str(conniving.effect) == "reactive_normal_move_with_pre_move_single_roll_mortal_wound_rider"
    assert str(conniving.timing) == "opponent_movement_phase_after_enemy_unit_ends_normal_advance_or_fall_back_move"
    assert int(conniving.effect_params.get("pre_move_success_on", 0) or 0) == 4
    assert str(conniving.effect_params.get("pre_move_mortal_wounds", "") or "").upper() == "D3+1"

    assert more_gitz is not None
    assert str(more_gitz.effect) == "reactive_normal_move"
    assert str(more_gitz.timing) == "opponent_movement_phase_after_enemy_unit_ends_normal_advance_or_fall_back_move"
