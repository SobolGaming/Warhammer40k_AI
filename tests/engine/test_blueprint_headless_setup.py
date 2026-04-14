from __future__ import annotations

import pytest

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.deployment_headless import DeterministicDeploymentDecisionMaker
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.engine.local_runtime import LocalAuthoritativeRuntime
from warhammer40k_ai.engine.phase import BattleRoundPhases, SetupPhase
from warhammer40k_ai.roster.army_build import ArmyBlueprint, DetachmentSelection, RosterEntry
from warhammer40k_ai.roster.player import Player, PlayerControl


def _player_one_blueprint() -> ArmyBlueprint:
    return ArmyBlueprint(
        faction="Space Marines",
        points_limit=2000,
        battle_size="Strike Force",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Gladius Task Force",
            )
        ],
        unit_entries=[
            RosterEntry(
                entry_id="unit_intercessors",
                name="Intercessor Squad",
                count=5,
                detachment_selection_id="detachment_alpha",
            )
        ],
    )


def _player_two_blueprint() -> ArmyBlueprint:
    return ArmyBlueprint(
        faction="Chaos Daemons",
        points_limit=2000,
        battle_size="Strike Force",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Daemonic Incursion",
            )
        ],
        unit_entries=[
            RosterEntry(
                entry_id="unit_bloodletters",
                name="Bloodletters",
                count=10,
                detachment_selection_id="detachment_alpha",
            )
        ],
    )


def _drain_pending_decisions(game: Game, *, max_attempts: int = 400) -> None:
    queue = getattr(game, "decision_queue", None)
    event_system = getattr(game, "event_system", None)
    if queue is None or event_system is None:
        return

    attempts = 0
    while True:
        request = queue.peek()
        if request is None:
            return
        if attempts >= max_attempts:
            raise RuntimeError(
                f"Unable to resolve pending decision after {max_attempts} attempts: "
                f"{getattr(request, 'decision_type', '')}"
            )
        decision_id_before = str(getattr(request, "decision_id", "") or "")
        event_system.publish("decision_requested", request=request, game=game)
        request_after = queue.peek()
        if request_after is None:
            return
        decision_id_after = str(getattr(request_after, "decision_id", "") or "")
        if decision_id_after == decision_id_before:
            raise RuntimeError(
                "Headless policy could not resolve decision "
                f"{decision_id_after} ({getattr(request_after, 'decision_type', '')})."
            )
        attempts += 1


@pytest.mark.integration
def test_headless_setup_and_first_turn_accept_blueprint_input() -> None:
    player_one = Player("Player One", control=PlayerControl.REMOTE)
    player_two = Player("Player Two", control=PlayerControl.REMOTE)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player_one, player_two])
    seed_fn = getattr(getattr(game, "random_source", None), "seed", None)
    if callable(seed_fn):
        seed_fn(12345)
    game.army_muster_requests = {
        "player1": _player_one_blueprint(),
        "player2": _player_two_blueprint(),
    }

    HeadlessPolicyDecisionController(
        game=game,
        auto_attach=True,
        max_reserves_arrival_seconds=1.0,
    )
    runtime = LocalAuthoritativeRuntime(game, manual_phases=False)
    deployment_decision_makers = {
        player_one.id: DeterministicDeploymentDecisionMaker(game, reserve_policy="forced_only"),
        player_two.id: DeterministicDeploymentDecisionMaker(game, reserve_policy="forced_only"),
    }

    while game.is_in_setup_phase():
        if runtime.is_driver_managed_setup_phase():
            runtime.run_setup_autosteps()
            _drain_pending_decisions(game)
            continue
        setup_kwargs: dict[str, object] = {}
        if game.get_current_setup_phase() == SetupPhase.DEPLOY_ARMIES:
            setup_kwargs["decision_makers"] = deployment_decision_makers
        game.execute_current_setup_phase(**setup_kwargs)
        _drain_pending_decisions(game)
        game.advance_setup_phase()
        _drain_pending_decisions(game)

    player_one_army = game.players[0].army
    player_two_army = game.players[1].army

    assert game.setup_complete is True
    assert game.turn == 1
    assert game.phase == BattleRoundPhases.COMMAND_PHASE
    assert player_one_army is not None
    assert player_two_army is not None
    assert len(player_one_army.units) == 1
    assert len(player_two_army.units) == 1
    assert player_one_army.army_blueprint_hash == _player_one_blueprint().army_blueprint_hash
    assert player_two_army.army_blueprint_hash == _player_two_blueprint().army_blueprint_hash

    _drain_pending_decisions(game)
    game.next_phase()
    _drain_pending_decisions(game)

    assert game.phase == BattleRoundPhases.MOVEMENT_PHASE
