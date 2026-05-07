from __future__ import annotations

from warhammer40k_ai.engine import turn_manager
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.phase import BattleRoundPhases


class _EventSystem:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def publish(self, event_name: str, **kwargs) -> None:
        self.events.append((str(event_name), dict(kwargs)))


class _Army:
    def __init__(self) -> None:
        self.units = []
        self.started_rounds: list[int] = []

    def on_battle_round_start(self, battle_round: int) -> None:
        self.started_rounds.append(int(battle_round))


class _Player:
    def __init__(self, player_id: str, name: str, army: _Army) -> None:
        self.id = player_id
        self.name = name
        self.army = army

    def get_army(self) -> _Army:
        return self.army


class _Game:
    def __init__(self) -> None:
        self.turn = 5
        self.phase = BattleRoundPhases.FIGHT_PHASE
        self.current_player_index = 1
        self.battle_round_starting_player_index = 0
        self.map = None
        self.event_system = _EventSystem()
        self.start_command_phase_calls = 0
        self.end_turn_scoring_calls = 0
        self.end_round_scoring_calls = 0
        self.players = [
            _Player("player:1", "Player 1", _Army()),
            _Player("player:2", "Player 2", _Army()),
        ]

    def get_current_player(self) -> _Player:
        return self.players[self.current_player_index]

    def end_of_turn_scoring(self) -> None:
        self.end_turn_scoring_calls += 1

    def end_of_battle_round_scoring(self) -> None:
        self.end_round_scoring_calls += 1

    def start_command_phase(self) -> None:
        self.start_command_phase_calls += 1


def test_turn_manager_does_not_start_sixth_battle_round_hooks() -> None:
    game = _Game()

    turn_manager.next_phase(game)

    assert game.turn == 6
    assert game.end_turn_scoring_calls == 1
    assert game.end_round_scoring_calls == 1
    assert game.start_command_phase_calls == 0
    assert game.players[0].army.started_rounds == []
    assert game.players[1].army.started_rounds == []
    event_names = [event_name for event_name, _payload in game.event_system.events]
    assert "phase_start" not in event_names
    assert "battle_round_started" not in event_names


def test_controller_driven_deployment_uses_selected_mission(monkeypatch) -> None:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[])
    game.selected_mission_info = {"deployment": "Hammer and Anvil"}
    seen_missions: list[str] = []

    class _DeploymentManager:
        def __init__(self, _game, mission_name: str = "Crucible of Battle") -> None:
            seen_missions.append(str(mission_name))

        def execute_deployment_sequence(self, decision_makers: dict) -> dict:
            assert decision_makers == {"player:1": object_marker}
            return {"deployment_positions": {}}

    object_marker = object()
    monkeypatch.setattr(
        "warhammer40k_ai.engine.deployment.DeploymentManager",
        _DeploymentManager,
    )

    game.execute_deploy_armies_phase(decision_makers={"player:1": object_marker})

    assert seen_missions == ["Hammer and Anvil"]
