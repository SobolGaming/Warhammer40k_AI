from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_MOVE_UNIT,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
)
from warhammer40k_ai.engine.decision_requests import (
    build_deployment_zone_request,
    build_select_next_deploy_unit_request,
    canonical_deployment_zone_key,
)
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.deployment import DeploymentDecisionMaker, DeploymentManager
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _StubModel:
    def __init__(self, model_id: str) -> None:
        self.id = model_id
        self._id = model_id


class _StubUnit:
    def __init__(self, unit_id: str, name: str) -> None:
        self.id = unit_id
        self.name = name
        self.models = [_StubModel(f"{unit_id}:model:0")]


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

    def choose_deployment_move_option(self, request, unit: _StubUnit, deployment_zone: dict, already_deployed: list[_StubUnit]):
        del unit, deployment_zone, already_deployed
        for option in list(getattr(request, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            if int(payload.get("placement_candidate_index", -1) or -1) == 1:
                return str(getattr(option, "option_id", "") or "")
        return None


class _DeploymentArmy:
    def __init__(self, units: list[object]) -> None:
        self.units = list(units)

    def _destroy_unit_models(self, unit, game_map=None) -> None:
        del game_map
        for model in list(getattr(unit, "models", []) or []):
            model.is_alive = False


class _DeployingUnit(_StubUnit):
    def __init__(self, unit_id: str, name: str) -> None:
        super().__init__(unit_id, name)
        self.deployed = False
        self.reserve_status = "deployed"
        self.is_titanic = False
        self.is_attached_leader = False
        self.is_joined_support = False
        self.attached_leaders = []

    def must_start_in_reserves(self) -> bool:
        return False

    def set_reserve_status(self, status: str) -> None:
        self.reserve_status = str(status)


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


def test_deployment_move_request_supports_multi_candidate_payloads_and_option_hooks() -> None:
    game, _player, _other = _build_game()
    manager = DeploymentManager(game)
    decision_maker = _OptionSelectingDecisionMaker(zone_name="Zone A", next_unit_id="unit:a")
    unit = _StubUnit("unit:a", "Alpha")
    request = manager._build_deployment_move_request(
        unit,
        placement_candidates=[
            {
                "anchor": [4.0, 8.0],
                "model_positions": [
                    {
                        "model_id": "unit:a:model:0",
                        "position": [4.0, 8.0, 0.0],
                        "facing": 0.0,
                    }
                ],
                "source": "semantic_anchor",
            },
            {
                "anchor": [6.0, 10.0],
                "model_positions": [
                    {
                        "model_id": "unit:a:model:0",
                        "position": [6.0, 10.0, 0.0],
                        "facing": 0.0,
                    }
                ],
                "source": "lattice",
            },
        ],
        deployment_zone={"name": "Zone A", "zone_type": "defender"},
    )

    assert request.decision_type == DECISION_MOVE_UNIT
    assert int(request.context.get("deployment_candidate_count", 0) or 0) == 2
    assert len(list(request.options or [])) == 2

    selected = manager._select_deployment_move_option(
        request=request,
        decision_maker=decision_maker,
        unit=unit,
        deployment_zone={"name": "Zone A", "zone_type": "defender"},
        already_deployed=[],
    )
    selected_payload = dict(getattr(selected, "payload", {}) or {})
    assert int(selected_payload.get("placement_candidate_index", -1) or -1) == 1


def test_deployment_move_candidate_builder_empty_result_returns_no_candidates() -> None:
    game, _player, _other = _build_game()
    manager = DeploymentManager(game)
    unit = _StubUnit("unit:a", "Alpha")

    class _EmptyCandidateDecisionMaker(_ScriptedDecisionMaker):
        def build_deployment_move_candidates(self, *_args, **_kwargs):
            return []

        def choose_unit_deployment_position(self, *_args, **_kwargs):
            raise AssertionError("empty deployment candidates should not fall back to anchor placement")

    decision_maker = _EmptyCandidateDecisionMaker(zone_name="Zone A", next_unit_id=unit.id)

    candidates = manager._build_deployment_move_candidates(
        unit,
        decision_maker=decision_maker,
        deployment_zone={"name": "Zone A", "zone_type": "defender"},
        already_deployed=[],
    )

    assert candidates == []


def test_execute_alternating_deployment_skips_unplaceable_unit_without_crashing(monkeypatch) -> None:
    game, defender, attacker = _build_game()
    manager = DeploymentManager(game)
    manager.defender = defender
    manager.attacker = attacker

    doomed = _DeployingUnit("unit:doomed", "Bloodletters")
    survivor = _DeployingUnit("unit:other", "Guardian Defenders")
    defender.army = _DeploymentArmy([doomed])
    attacker.army = _DeploymentArmy([survivor])

    class _DecisionMaker(_ScriptedDecisionMaker):
        def __init__(self) -> None:
            super().__init__(zone_name="Zone A", next_unit_id="unit:doomed")

        def build_deployment_intent(self, **kwargs):
            del kwargs
            return {}

        def build_deployment_decision_context(self, **kwargs):
            del kwargs
            return {}

    defender_maker = _DecisionMaker()
    attacker_maker = _DecisionMaker()

    monkeypatch.setattr(
        manager,
        "_resolve_next_deploy_unit_choice",
        lambda player, decision_maker, deployable_units, deployment_zone, already_deployed: deployable_units[0],
    )

    def _fake_candidates(unit, *, decision_maker, deployment_zone, already_deployed, max_candidates=8):
        del decision_maker, deployment_zone, already_deployed, max_candidates
        if unit is doomed:
            return []
        return [
            {
                "anchor": [4.0, 8.0],
                "model_positions": [
                    {
                        "model_id": "unit:other:model:0",
                        "position": [4.0, 8.0, 0.0],
                        "facing": 0.0,
                    }
                ],
                "source": "test",
            }
        ]

    monkeypatch.setattr(manager, "_build_deployment_move_candidates", _fake_candidates)
    monkeypatch.setattr(manager, "_build_deployment_move_request", lambda *args, **kwargs: DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Deploy",
        player_id=attacker.id,
        options=[
            DecisionOption.create(
                "Place",
                payload={
                    "deployment_anchor": [4.0, 8.0],
                    "model_positions": [
                        {
                            "model_id": "unit:other:model:0",
                            "position": [4.0, 8.0, 0.0],
                            "facing": 0.0,
                        }
                    ],
                },
            )
        ],
    ))
    monkeypatch.setattr(manager, "_select_deployment_move_option", lambda **kwargs: kwargs["request"].options[0])
    monkeypatch.setattr(
        game,
        "request_decision",
        lambda request: game.decision_queue.add(request),
    )
    monkeypatch.setattr(
        game,
        "apply_command",
        lambda command: type("Result", (), {"ok": True, "value": type("Apply", (), {"ok": True})()})(),
    )

    deployment_results = {
        "deployment_zones": {
            defender.id: {"name": "Zone A", "zone_type": "defender"},
            attacker.id: {"name": "Zone B", "zone_type": "attacker"},
        },
        "reserves": {
            defender.id: {doomed.id: "deploy"},
            attacker.id: {survivor.id: "deploy"},
        },
    }

    manager.execute_alternating_deployment(
        deployment_results,
        {defender.id: defender_maker, attacker.id: attacker_maker},
    )

    assert bool(getattr(doomed, "_deployment_skipped_no_position", False)) is True
    assert bool(doomed.deployed) is True
    assert bool(doomed.models[0].is_alive) is False


def test_execute_deployment_sequence_reuses_setup_roles_and_reserves(monkeypatch) -> None:
    game, defender, attacker = _build_game()
    defender_unit = _DeployingUnit("unit:defender", "Guardian Defenders")
    attacker_unit = _DeployingUnit("unit:attacker", "Howling Banshees")
    defender.army = _DeploymentArmy([defender_unit])
    attacker.army = _DeploymentArmy([attacker_unit])
    defender_unit.set_reserve_status("strategic_reserves")
    attacker_unit.set_reserve_status("deployed")

    game.defender_index = 0
    game.attacker_index = 1
    game.first_turn_player_index = 1
    game.current_player_index = 0
    game.deployment_zones = {
        defender.id: {"name": "Defender Zone", "zone_type": "defender"},
        attacker.id: {"name": "Attacker Zone", "zone_type": "attacker"},
    }

    class _NoSetupSideEffectsDecisionMaker(_ScriptedDecisionMaker):
        def declare_reserves(self, player: Player) -> dict:
            raise AssertionError(f"DEPLOY_ARMIES must not re-run reserve declarations for {player.name}.")

    defender_maker = _NoSetupSideEffectsDecisionMaker(zone_name="Defender Zone", next_unit_id=defender_unit.id)
    attacker_maker = _NoSetupSideEffectsDecisionMaker(zone_name="Attacker Zone", next_unit_id=attacker_unit.id)
    manager = DeploymentManager(game)

    def _unexpected_get_dice_roll(*_args, **_kwargs):
        raise AssertionError("DEPLOY_ARMIES must not re-roll attacker/defender or first-turn dice.")

    monkeypatch.setattr("warhammer40k_ai.engine.deployment.get_dice_roll", _unexpected_get_dice_roll, raising=False)
    monkeypatch.setattr(manager, "_resolve_deployment_zone_decision", lambda _player, _maker, zones: zones[0])
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        manager,
        "execute_alternating_deployment",
        lambda deployment_results, _decision_makers: captured.__setitem__("results", deployment_results),
    )

    deployment_results = manager.execute_deployment_sequence(
        {defender.id: defender_maker, attacker.id: attacker_maker}
    )

    assert manager.defender is defender
    assert manager.attacker is attacker
    assert deployment_results["defender"] == defender.id
    assert deployment_results["attacker"] == attacker.id
    assert deployment_results["first_turn_player"] is None
    assert deployment_results["reserves"][defender.id] == {defender_unit.id: "strategic_reserves"}
    assert deployment_results["reserves"][attacker.id] == {attacker_unit.id: "deploy"}
    assert captured["results"] is deployment_results
    assert game.first_turn_player_index == 1
    assert game.current_player_index == 0
