import pytest

from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.engine.mission_cards import CleanseSecondary


class DummyArmy:
    def __init__(self):
        self.units = []
        self.player = None

    def set_player(self, p):
        self.player = p


def make_game():
    bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    p1 = Player("Player 1", PlayerControl.LOCAL, army=DummyArmy())
    p2 = Player("Player 2", PlayerControl.LOCAL, army=DummyArmy())
    game = Game(bf, players=[p1, p2])
    p1.army.set_player(p1)
    p2.army.set_player(p2)
    return game, p1, p2


def test_primary_cap_50():
    game, p1, _ = make_game()
    added = game.award_vp(p1, 60, source="primary")
    assert added == 50
    assert p1.get_score() == 50
    assert p1.vp_primary == 50


def test_secondary_cap_40():
    game, p1, _ = make_game()
    added = game.award_vp(p1, 999, source="secondary")
    assert added == 40
    assert p1.get_score() == 40
    assert p1.vp_secondary == 40


def test_primary_plus_secondary_cap_90():
    game, p1, _ = make_game()
    assert game.award_vp(p1, 45, source="primary") == 45
    assert game.award_vp(p1, 40, source="secondary") == 40
    # Combined cap leaves only 5 VP remaining for Primary+Secondary
    assert game.award_vp(p1, 10, source="primary") == 5
    assert p1.vp_primary == 50
    assert p1.vp_secondary == 40
    assert p1.get_score() == 90


def test_total_cap_100_and_battle_ready_default_true():
    game, p1, _ = make_game()
    assert p1.is_battle_ready is True

    assert game.award_vp(p1, 50, source="primary") == 50
    assert game.award_vp(p1, 40, source="secondary") == 40
    assert p1.get_score() == 90

    # Battle Ready: 10VP, total reaches 100
    assert game.award_vp(p1, 10, source="battle_ready") == 10
    assert p1.get_score() == 100

    # Any further VP from any source are lost
    assert game.award_vp(p1, 5, source="primary") == 0
    assert game.award_vp(p1, 5, source="secondary") == 0
    assert game.award_vp(p1, 5, source="battle_ready") == 0


def test_fixed_secondary_card_cap_20():
    game, p1, _ = make_game()
    game.secondary_mission_mode = "fixed"

    card = CleanseSecondary()  # no intrinsic total cap
    assert game.award_vp(p1, 15, source="secondary", card=card) == 15
    assert game.award_vp(p1, 15, source="secondary", card=card) == 5  # hits 20VP per-card cap
    assert card.total_scored == 20
    assert p1.vp_secondary == 20


def test_get_winner_returns_none_on_draw_after_battle_ready():
    game, p1, p2 = make_game()
    # Force game over
    game.turn = game.turn + 999
    # Equal VP before final scoring
    game.award_vp(p1, 30, source="primary")
    game.award_vp(p2, 30, source="primary")

    winner = game.get_winner()
    assert winner is None
    # Battle ready should have been applied to both players, keeping it a draw.
    assert p1.get_score() == p2.get_score()


def test_vp_capped_event_published_when_award_is_reduced():
    game, p1, _ = make_game()
    calls = []

    def _publish(event_name, **kwargs):
        calls.append((event_name, kwargs))

    game.event_system.publish = _publish

    # Requesting 60 primary should cap to 50 and publish a notification event.
    added = game.award_vp(p1, 60, source="primary")
    assert added == 50
    assert any(name == "vp_capped" for name, _ in calls)

