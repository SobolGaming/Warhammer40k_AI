from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..engine.mission_cards import default_secondary_deck
from ..utility.rng import resolve_rng

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..engine.mission_cards import PrimaryMissionCard, SecondaryMissionCard


def initialize_player_mission_state(player) -> None:
    player.primary_mission = None
    player.secondary_deck = []
    player.active_secondaries = []
    player.discarded_secondaries = []


class PlayerMissionMixin:
    def set_primary_mission(self, primary: PrimaryMissionCard) -> None:
        self.primary_mission = primary

    def set_secondary_deck(self, cards: list[SecondaryMissionCard] | None = None, *, game=None) -> None:
        if cards is not None:
            self.secondary_deck = list(cards)
        else:
            rng = resolve_rng(game)
            self.secondary_deck = default_secondary_deck(rng=rng)
        self.active_secondaries = []
        self.discarded_secondaries = []

    def ensure_secondary_deck_initialized(self, game=None) -> None:
        if not self.secondary_deck and not self.active_secondaries and not self.discarded_secondaries:
            self.set_secondary_deck(game=game)

    def can_draw_secondary(self) -> bool:
        return len(self.secondary_deck) > 0

    def draw_secondary_until_two(self, game) -> None:
        self.ensure_secondary_deck_initialized(game)
        while len(self.active_secondaries) < 2 and self.secondary_deck:
            card = self.secondary_deck.pop(0)
            if hasattr(card, "can_be_drawn") and not card.can_be_drawn(game, self):
                if bool(getattr(card, "shuffle_back_on_ineligible_draw", False)):
                    rng = resolve_rng(game)
                    idx = int(rng.randint(0, len(self.secondary_deck)))
                    self.secondary_deck.insert(idx, card)
                    logger.info(
                        "%s cannot draw Secondary: %s (ineligible); shuffled back into deck",
                        self.name,
                        card.name,
                    )
                else:
                    self.discarded_secondaries.append(card)
                    logger.info(
                        "%s cannot draw Secondary: %s (ineligible); discarded",
                        self.name,
                        card.name,
                    )
                continue
            if hasattr(card, "on_draw"):
                card.on_draw(game, self)
            self.active_secondaries.append(card)
            logger.info("%s drew Secondary: %s", self.name, card.name)

    def discard_secondary(self, card: SecondaryMissionCard, gain_cp: bool = False) -> None:
        if card in self.active_secondaries:
            self.active_secondaries.remove(card)
            self.discarded_secondaries.append(card)
            if gain_cp:
                self.gain_command_points(1, reason="Discard Secondary (gain 1CP)", source="mission_rule")

    def discard_achieved_secondaries(self, achieved_cards: list[SecondaryMissionCard]) -> None:
        for card in list(achieved_cards):
            if card in self.active_secondaries:
                self.active_secondaries.remove(card)
                self.discarded_secondaries.append(card)
