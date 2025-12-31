# This is the player that gets put onto a Battlefield and has an Army

import logging
from enum import Enum, auto
from .army import Army
from .unit import Unit
from warhammer40k_ai.classes.map import Objective
from .mission_cards import PrimaryMissionCard, SecondaryMissionCard, default_secondary_deck
from warhammer40k_ai.utility.calcs import get_dist

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


class PlayerType(Enum):
    AI = auto()
    HUMAN = auto()
    RANDOM = auto()
    NULL = auto()


class Player:
    def __init__(self, name: str, player_type: PlayerType = PlayerType.NULL, army: Army = None):
        self.name = name
        if player_type not in (PlayerType.AI, PlayerType.HUMAN):
            raise ValueError(f"Invalid player type: {player_type}")
        self.type = player_type
        self.round: int = 0
        self.command_points: int = 0  # Players start with 0 Command Points in 10th edition
        self.army: Army = army
        # ---- Victory Points (VP) ----
        # Total VP scored across the battle (capped by mission pack rules in Game awarding logic).
        self.score: int = 0
        # Breakdown by source (kept in-sync by Game awarding logic).
        self.vp_primary: int = 0
        self.vp_secondary: int = 0
        self.vp_battle_ready: int = 0
        # Battle Ready (painted) bonus: assume TRUE by default per project rules.
        self.is_battle_ready: bool = True
        # Mission cards
        self.primary_mission: PrimaryMissionCard | None = None
        self.secondary_deck: list[SecondaryMissionCard] = []
        self.active_secondaries: list[SecondaryMissionCard] = []
        self.discarded_secondaries: list[SecondaryMissionCard] = []
        # Set the player reference on the army
        if self.army:
            self.army.set_player(self)

        # Core rules: CP gain guardrail (Warhammer Community).
        # Per battle round, a player cannot gain more than 1 CP from sources other than the normal +1CP
        # at the start of their own Command phase, unless an ability explicitly exempts it.
        self.cp_gained_this_battle_round_excluding_normal_command_cp: int = 0
        self._cp_gain_guardrail_battle_round: int | None = None
        #print(f"Player {self.name} created with army: {self.army}")
    
    def set_army(self, army: Army) -> None:
        self.army = army
        army.set_player(self)

    def set_game(self, game) -> None:
        """Set the game reference for this player."""
        self.game = game
        try:
            # Lazily attach stratagem manager when a game is set
            from .stratagems import StratagemManager
            self.stratagems = StratagemManager(self)
        except Exception:
            # Do not fail hard if wiring is incomplete
            self.stratagems = None

    def _sync_cp_gain_guardrail_battle_round(self) -> None:
        """Reset per-battle-round CP gain guardrail counter when battle round advances."""
        try:
            br = int(getattr(self.game, "turn", 0) or 0)
        except Exception:
            br = None
        if br is None or br <= 0:
            return
        if self._cp_gain_guardrail_battle_round != br:
            self._cp_gain_guardrail_battle_round = br
            self.cp_gained_this_battle_round_excluding_normal_command_cp = 0

    def get_army(self) -> Army | None:
        return self.army

    def has_unit(self, unit: Unit) -> bool:
        return unit in self.army.units

    def has_units(self) -> bool:
        return len(self.army.units) > 0

    def get_score(self) -> int:
        return self.score

    def add_score(self, points: int) -> None:
        self.score += points

    def get_vp_breakdown(self) -> dict:
        """Return a simple VP breakdown dict. Game logic is the authoritative scorer."""
        return {
            "total": int(self.score or 0),
            "primary": int(self.vp_primary or 0),
            "secondary": int(self.vp_secondary or 0),
            "battle_ready": int(self.vp_battle_ready or 0),
        }
    
    def gain_command_points(self, amount: int = 1, *, is_normal_command_phase_gain: bool = False,
                            exempt_from_guardrail: bool = False, reason: str | None = None) -> int:
        """
        Gain command points, enforcing the core CP gain guardrail:
        - The normal +1CP at the start of your own Command phase is always allowed and does not count.
        - All other CP gains are limited to a maximum of +1 CP per battle round unless exempt.

        Returns the number of CP actually gained (may be less than requested).
        """
        try:
            amount = int(amount or 0)
        except Exception:
            amount = 0
        if amount <= 0:
            return 0

        # Keep battle-round counter fresh
        try:
            self._sync_cp_gain_guardrail_battle_round()
        except Exception:
            pass

        if is_normal_command_phase_gain:
            self.command_points += amount
            return amount

        if exempt_from_guardrail:
            self.command_points += amount
            return amount

        # Guardrail: max +1 CP per battle round from non-normal sources.
        if int(self.cp_gained_this_battle_round_excluding_normal_command_cp or 0) >= 1:
            return 0

        gained = min(amount, 1)
        self.command_points += gained
        self.cp_gained_this_battle_round_excluding_normal_command_cp += 1
        return gained

    def get_normal_command_phase_cp_gain(self) -> int:
        """
        Return the normal CP gained at the start of this player's Command phase.

        Core rules are typically +1CP, but we keep this as an overridable lookup to support
        mission/faction-level variations without hard-coding in Game flow.
        """
        return 1

    def get_command_phase_bonus_cp_gain(self) -> int:
        """
        Return bonus CP gained during *this player's own* Command phase due to abilities while alive.

        This bonus is NOT the normal Command phase CP and is therefore subject to the per-battle-round guardrail.
        """
        army = self.get_army()
        if army is None:
            return 0
        fn = getattr(army, "get_command_phase_bonus_cp_gain", None)
        if callable(fn):
            return int(fn() or 0)
        return 0

    def gain_normal_command_phase_cp(self) -> int:
        """Grant the normal CP at the start of this player's Command phase (does not count toward guardrail)."""
        return self.gain_command_points(self.get_normal_command_phase_cp_gain(), is_normal_command_phase_gain=True, reason="Normal Command phase CP")

    def gain_command_point(self) -> None:
        """Legacy wrapper: gain 1 CP subject to the guardrail (non-normal source)."""
        self.gain_command_points(1)
    
    def spend_command_points(self, amount: int) -> bool:
        """Spend command points if available"""
        if self.command_points >= amount:
            self.command_points -= amount
            return True
        return False

    def compute_average_distance(self, objective: Objective) -> float:
        """Compute the average distance of the player's alive units to the objective."""
        distances = []
        for unit in self.get_army().units:
            if unit.is_alive() and unit.deployed:
                # Find the model closest to the objective
                obj_pos = (objective.location.x, objective.location.y, objective.location.z)
                closest_distance = float('inf')

                for model in unit.models:
                    if model.is_alive:
                        model_pos = model.get_location()
                        distance = get_dist(model_pos[0] - obj_pos[0],
                                          model_pos[1] - obj_pos[1],
                                          model_pos[2] - obj_pos[2])
                        if distance < closest_distance:
                            closest_distance = distance

                if closest_distance != float('inf'):
                    distances.append(closest_distance)
        return sum(distances) / len(distances) if distances else 0.0

    # ---------- Mission card helpers ----------

    def set_primary_mission(self, primary: PrimaryMissionCard) -> None:
        self.primary_mission = primary

    def set_secondary_deck(self, cards: list[SecondaryMissionCard] | None = None) -> None:
        # Use provided or default deck
        if cards is not None:
            self.secondary_deck = list(cards)
        else:
            self.secondary_deck = default_secondary_deck()
            # Shuffle for randomness if not already shuffled upstream
            try:
                import random
                random.shuffle(self.secondary_deck)
            except Exception:
                pass
        self.active_secondaries = []
        self.discarded_secondaries = []

    def ensure_secondary_deck_initialized(self) -> None:
        if not self.secondary_deck and not self.active_secondaries and not self.discarded_secondaries:
            self.set_secondary_deck()

    def can_draw_secondary(self) -> bool:
        return len(self.secondary_deck) > 0

    def draw_secondary_until_two(self, game) -> None:
        # Initialize deck if needed
        self.ensure_secondary_deck_initialized()
        # Draw until two active if deck allows
        while len(self.active_secondaries) < 2 and self.secondary_deck:
            card = self.secondary_deck.pop(0)
            try:
                if hasattr(card, 'can_be_drawn') and not card.can_be_drawn(game, self):
                    # Discard immediately and continue drawing
                    self.discarded_secondaries.append(card)
                    try:
                        print(f"🗑️ {self.name} cannot draw Secondary: {card.name} (ineligible) → discarded")
                    except Exception:
                        pass
                    continue
                # Allow cards to perform on-draw initialization
                if hasattr(card, 'on_draw'):
                    try:
                        card.on_draw(game, self)
                    except Exception:
                        pass
            except Exception:
                pass
            self.active_secondaries.append(card)
            try:
                print(f"🃏 {self.name} drew Secondary: {card.name}")
            except Exception:
                pass

    def discard_secondary(self, card: SecondaryMissionCard, gain_cp: bool = False) -> None:
        if card in self.active_secondaries:
            self.active_secondaries.remove(card)
            self.discarded_secondaries.append(card)
            if gain_cp:
                # Voluntary discard CP gain is subject to the core CP gain guardrail.
                self.gain_command_points(1, reason="Discard Secondary (gain 1CP)")

    def discard_achieved_secondaries(self, achieved_cards: list[SecondaryMissionCard]) -> None:
        for card in list(achieved_cards):
            if card in self.active_secondaries:
                self.active_secondaries.remove(card)
                self.discarded_secondaries.append(card)

    def __str__(self):
        return f"Name: {self.name}\nType: {self.type.name}\nCommand Points: {self.command_points}\nArmy: {self.army}"
