from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
)
from warhammer40k_ai.engine.decision_requests import (
    build_deployment_zone_request,
    build_select_next_deploy_unit_request,
    canonical_deployment_zone_key,
)
from warhammer40k_ai.engine.deployment import DeploymentDecisionMaker, DeploymentManager
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _StubUnit:
    def __init__(self, unit_id: str, name: str) -> None:
        self.id = unit_id
        self.name = name


class _ScriptedDecisionMaker(DeploymentDecisionMaker):
    def __init__(self, *, zone_name: str, next_unit_id: str) -> None:
        self._zone_name = str(zone_name)
        self._next_unit_id = str(next_unit_id)

    def choose_deployment_zone(self, available_zones: list[dict]) -> dict:
        return next(zone for zone in list(available_zones or []) if str(zone.get("name", "") or "") == self._zone_name)

    def declare_reserves(self, player: Player) -> dict:
        return {}

    def choose_next_deploy_unit(self, deployable_units: list[_StubUnit], deployment_zone: dict, already_deployed: list[_StubUnit]):
        return next(unit for unit in list(deployable_units or []) if str(getattr(unit, "id", "") or "") == self._next_unit_id)

    def choose_unit_deployment_position(self, unit: _StubUnit, deployment_zone: dict, already_deployed: list[_StubUnit]):
        return (0.0, 0.0)


class _OptionSelectingDecisionMaker(_ScriptedDecisionMaker):
    def __init__(self, *, zone_name: str, next_unit_id: str) -> None:
        super().__init__(zone_name=zone_name, next_unit_id=next_unit_id)
        self.zone_fallback_calls = 0
        self.unit_fallback_calls = 0

    def choose_deployment_zone(self, available_zones: list[dict]) -> dict:
        self.zone_fallback_calls += 1
        return super().choose_deployment_zone(available_zones)

    def choose_next_deploy_unit(self, deployable_units: list[_StubUnit], deployment_zone: dict, already_deployed: list[_StubUnit]):
        self.unit_fallback_calls += 1
        return super().choose_next_deploy_unit(deployable_units, deployment_zone, already_deployed)

    def choose_deployment_zone_option(self, request, available_zones: list[dict]):
        del available_zones
        for option in list(getattr(request, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            if str(payload.get("zone_name", "") or "") == self._zone_name:
                return str(getattr(option, "option_id", "") or "")
        return None

    def choose_next_deploy_unit_option(self, request, deployable_units: list[_StubUnit], deployment_zone: dict, already_deployed: list[_StubUnit]):
        del deployable_units, deployment_zone, already_deployed
        for option in list(getattr(request, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            if str(payload.get("unit_id", "") or "") == self._next_unit_id:
                return str(getattr(option, "option_id", "") or "")
        return None


def _build_game() -> tuple[Game, Player, Player]:
    player_one = Player("P1", PlayerControl.LOCAL, None)
    player_two = Player("P2", PlayerControl.LOCAL, None)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player_one, player_two])
    return game, player_one, player_two


def test_build_deployment_zone_request_resolves_through_decision_stack() -> None:
    game, player, _other = _build_game()
    zones = [
        {"name": "Right Zone", "zone_type": "attacker", "x_range": [30.0, 60.0], "y_range": [0.0, 44.0]},
        {"name": "Left Zone", "zone_type": "defender", "x_range": [0.0, 30.0], "y_range": [0.0, 44.0]},
    ]
    request = build_deployment_zone_request(game, player, zones, queue_requests=True)
    assert request is not None
    assert request.decision_type == DECISION_CHOOSE_DEPLOYMENT_ZONE
    assert request.context.get("selection_kind") == "deployment_zone"
    assert len(request.options) == 2
    first_payload = dict(request.options[0].payload or {})
    assert isinstance(first_payload.get("board_affordances"), dict)

    by_label = {str(option.label): option for option in list(request.options or [])}
    selected_option = by_label["Left Zone"]
    result = resolve_decision_command(game, request, selected_option.option_id, player_id=player.id)
    assert bool(getattr(result, "ok", False))
    assert game.decision_queue.get(request.decision_id) is None

    record = game.decision_record_store.records[-1]
    assert str(record.get("decision_type", "") or "") == DECISION_CHOOSE_DEPLOYMENT_ZONE


def test_build_select_next_deploy_unit_request_sorts_unit_ids_deterministically() -> None:
    game, player, _other = _build_game()
    units = [
        _StubUnit("unit:c", "Gamma"),
        _StubUnit("unit:a", "Alpha"),
        _StubUnit("unit:b", "Beta"),
    ]
    request = build_select_next_deploy_unit_request(
        game,
        player,
        units,
        deployment_zone={"name": "Left Zone", "zone_type": "defender"},
        queue_requests=True,
    )
    assert request is not None
    assert request.decision_type == DECISION_SELECT_NEXT_DEPLOY_UNIT
    assert request.context.get("selection_kind") == "deployment_next_unit"
    assert request.context.get("deployment_zone_key") == canonical_deployment_zone_key({"name": "Left Zone", "zone_type": "defender"})

    option_unit_ids = [str(dict(option.payload or {}).get("unit_id", "") or "") for option in list(request.options or [])]
    assert option_unit_ids == ["unit:a", "unit:b", "unit:c"]

    selected_option = next(option for option in list(request.options or []) if option.payload.get("unit_id") == "unit:b")
    result = resolve_decision_command(game, request, selected_option.option_id, player_id=player.id)
    assert bool(getattr(result, "ok", False))
    assert game.decision_queue.get(request.decision_id) is None


def test_deployment_manager_resolves_zone_and_next_unit_choices_via_requests() -> None:
    game, player, _other = _build_game()
    manager = DeploymentManager(game)
    decision_maker = _ScriptedDecisionMaker(zone_name="Zone B", next_unit_id="unit:b")
    zones = [
        {"name": "Zone A", "zone_type": "defender"},
        {"name": "Zone B", "zone_type": "attacker"},
    ]
    selected_zone = manager._resolve_deployment_zone_decision(player, decision_maker, zones)
    assert str(selected_zone.get("name", "") or "") == "Zone B"

    deployable = [_StubUnit("unit:a", "Alpha"), _StubUnit("unit:b", "Beta")]
    selected_unit = manager._resolve_next_deploy_unit_choice(
        player,
        decision_maker,
        deployable,
        selected_zone,
        already_deployed=[],
    )
    assert str(getattr(selected_unit, "id", "") or "") == "unit:b"
    manager._pop_selected_deploy_unit(deployable, selected_unit)
    assert [str(getattr(unit, "id", "") or "") for unit in deployable] == ["unit:a"]


def test_deployment_manager_prefers_option_selection_hooks_when_available() -> None:
    game, player, _other = _build_game()
    manager = DeploymentManager(game)
    decision_maker = _OptionSelectingDecisionMaker(zone_name="Zone B", next_unit_id="unit:b")
    zones = [
        {"name": "Zone A", "zone_type": "defender"},
        {"name": "Zone B", "zone_type": "attacker"},
    ]
    selected_zone = manager._resolve_deployment_zone_decision(player, decision_maker, zones)
    assert str(selected_zone.get("name", "") or "") == "Zone B"
    assert int(decision_maker.zone_fallback_calls) == 0

    deployable = [_StubUnit("unit:a", "Alpha"), _StubUnit("unit:b", "Beta")]
    selected_unit = manager._resolve_next_deploy_unit_choice(
        player,
        decision_maker,
        deployable,
        selected_zone,
        already_deployed=[],
    )
    assert str(getattr(selected_unit, "id", "") or "") == "unit:b"
    assert int(decision_maker.unit_fallback_calls) == 0
