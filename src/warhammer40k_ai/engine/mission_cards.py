from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class ScoreResult:
    vp: int
    achieved: bool = False  # For secondary cards that complete upon scoring
    # Optional detail lines to explain why scoring occurred.
    details: list[str] | str | None = None


class SecondaryScoringWindow(Enum):
    """When a secondary's end-of-turn scoring should be evaluated."""
    END_OF_YOUR_TURN = "end_of_your_turn"
    END_OF_EITHER_PLAYER_TURN = "end_of_either_player_turn"
    END_OF_OPPONENT_TURN = "end_of_opponent_turn"
    END_OF_BATTLE = "end_of_battle"


@dataclass
class MissionCard:
    name: str
    # Short summary for quick display (optional)
    summary: str = ""
    # Structured rules text for UI / logging
    setup_text: Optional[str] = None
    when_drawn_text: Optional[str] = None
    action_text: Optional[str] = None
    fixed_text: Optional[str] = None
    tactical_text: Optional[str] = None
    scoring_text: Optional[str] = None
    # Optional total cap across the battle for this card instance
    score_cap_total: Optional[int] = None
    total_scored: int = 0
    # Optional per-turn cap when scoring is per-turn; set by specific cards as needed
    score_cap_per_turn: Optional[int] = None

    def add_score(self, vp: int) -> int:
        # Apply per-turn cap first if configured
        if self.score_cap_per_turn is not None:
            vp = min(vp, self.score_cap_per_turn)
        if self.score_cap_total is None:
            self.total_scored += vp
            return vp
        # Enforce up-to cap semantics
        remaining = max(0, self.score_cap_total - self.total_scored)
        to_add = min(remaining, vp)
        self.total_scored += to_add
        return to_add


class PrimaryMissionCard(MissionCard):
    def score_at_command_phase(self, game, player) -> int:
        return 0

    def score_at_end_of_turn(self, game, player) -> int:
        return 0

    def score_at_end_of_battle_round(self, game, player) -> int:
        return 0


class SecondaryMissionCard(MissionCard):
    scoring_window: SecondaryScoringWindow = SecondaryScoringWindow.END_OF_YOUR_TURN

    def is_fixed_mode(self, game) -> bool:
        return str(getattr(game, "secondary_mission_mode", "tactical")).lower() == "fixed"

    # When drawn gating (e.g., Bring It Down redraw if no valid targets)
    def can_be_drawn(self, game, player) -> bool:
        return True

    # Whether to shuffle the card back into the deck when it is rejected on draw.
    # Used for "If it is the first battle round, draw a new Secondary Mission card and shuffle this card back..."
    shuffle_back_on_ineligible_draw: bool = False

    # Evaluation windows. These return ScoreResult with achieved flag when the card should be discarded
    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        return ScoreResult(vp=0, achieved=False)

    def score_window(self) -> SecondaryScoringWindow:
        return self.scoring_window

    # Optional hook at start of the player's turn (used by cards needing a start-of-turn snapshot).
    def on_turn_start(self, game, player) -> None:
        return None

    # Optional hook when the card is drawn
    def on_draw(self, game, player) -> None:
        return None


# ---------- Primary Missions ----------

class TakeAndHoldPrimary(PrimaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Take and Hold",
            scoring_text=(
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of the Command phase (or the end of your turn if it is the fifth battle round and you are going second).\n"
                "The player whose turn it is scores:\n"
                "For each objective marker that they control: 5VP (MAX 15VP)."
            ),
            score_cap_per_turn=15,
        )

    def score_at_command_phase(self, game, player) -> int:
        # Second battle round onwards
        if game.get_battle_round() < 2:
            return 0
        # Count objectives controlled by the current player
        control_count = 0
        for objective in getattr(game.map, 'objectives', []):
            try:
                # Update control prior to scoring (idempotent)
                if hasattr(objective, 'location') and hasattr(objective.location, 'update_control'):
                    objective.location.update_control(game)
                if getattr(objective.location, 'removed', False):
                    continue
                if getattr(objective.location, 'controlling_player', None) is player:
                    control_count += 1
            except Exception:
                continue
        return control_count * 5

    def score_at_end_of_turn(self, game, player) -> int:
        # Fifth battle round, going second scores at end of your turn
        if game.get_battle_round() != 5:
            return 0
        # Determine who is going second this round
        starting_idx = game.battle_round_starting_player_index
        if starting_idx is None:
            return 0
        going_second_player = game.players[(starting_idx + 1) % len(game.players)]
        if going_second_player is not player:
            return 0
        # Same scoring as command phase
        return self.score_at_command_phase(game, player)


class TerraformPrimary(PrimaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Terraform",
            action_text=(
                "TERRAFORM (ACTION)\n"
                "STARTS: Your Shooting phase.\n"
                "UNITS: One or more units from your army, each within range of a different objective marker that is not within your deployment zone.\n"
                "COMPLETES: End of the turn, if the unit performing this Action is still within range of the same objective marker and you control that objective marker.\n"
                "IF COMPLETED: Each of those objective markers is terraformed by you. If that objective marker was terraformed by your opponent, it no longer is."
            ),
            scoring_text=(
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of the Command phase (or the end of your turn if it is the fifth battle round and you are going second).\n"
                "The player whose turn it is scores:\n"
                "For each objective marker they control: 4VP (MAX 12VP).\n\n"
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of the turn.\n"
                "Each player scores:\n"
                "For each objective marker that is terraformed by them: 1VP."
            ),
            score_cap_per_turn=12,
        )

    def score_at_command_phase(self, game, player) -> int:
        if game.get_battle_round() < 2:
            return 0
        # 4VP per objective you control
        control_count = 0
        for objective in getattr(game.map, 'objectives', []):
            try:
                if hasattr(objective, 'location') and hasattr(objective.location, 'update_control'):
                    objective.location.update_control(game)
                if getattr(objective.location, 'removed', False):
                    continue
                if getattr(objective.location, 'controlling_player', None) is player:
                    control_count += 1
            except Exception:
                continue
        return control_count * 4

    def score_at_end_of_turn(self, game, player) -> int:
        # 1VP per terraformed objective controlled by player (tracks on game.map ObjectivePoint via attribute)
        vp = 0
        for objective in getattr(game.map, 'objectives', []):
            loc = getattr(objective, 'location', None)
            if not loc:
                continue
            if getattr(loc, 'removed', False):
                continue
            if getattr(loc, 'terraformed_by', None) is player:
                vp += 1
        return vp

class LinchpinPrimary(PrimaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Linchpin",
            scoring_text=(
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of the Command phase (or the end of your turn if it is the fifth battle round and you are going second).\n"
                "If the player whose turn it is does not control the objective marker in their deployment zone:\n"
                "For each objective marker that the player controls: 3VP.\n\n"
                "OR\n"
                "If the player whose turn it is does control the objective marker in their deployment zone:\n"
                "For controlling the objective marker in their deployment zone: 3VP.\n"
                "AND\n"
                "For each other objective marker that the player controls: 5VP (MAX 15VP)."
            ),
            score_cap_per_turn=15,
        )

    def _get_home_objective(self, game, player):
        # Return any objective located within the player's deployment zone
        try:
            zones = game.deployment_zones.get(player.name, {})
            zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
            if not zone:
                return None
            for obj in getattr(game.map, 'objectives', []):
                loc = getattr(obj, 'location', None)
                if not loc or getattr(loc, 'removed', False):
                    continue
                if hasattr(zone, 'contains_point') and zone.contains_point(loc.x, loc.y):
                    return obj
        except Exception:
            return None
        return None

    def score_at_command_phase(self, game, player) -> int:
        if game.get_battle_round() < 2:
            return 0
        # Determine if player controls home objective
        home_obj = self._get_home_objective(game, player)
        controls_home = False
        if home_obj and hasattr(home_obj, 'location'):
            if hasattr(home_obj.location, 'update_control'):
                home_obj.location.update_control(game)
            controls_home = getattr(home_obj.location, 'controlling_player', None) is player

        total = 0
        for obj in getattr(game.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc or getattr(loc, 'removed', False):
                continue
            if hasattr(loc, 'update_control'):
                loc.update_control(game)
            if getattr(loc, 'controlling_player', None) is player:
                is_home = (home_obj is obj)
                if controls_home:
                    total += 3 if is_home else 5
                else:
                    total += 3
        return total


class PurgeTheFoePrimary(PrimaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Purge the Foe",
            scoring_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: End of the battle round.\n"
                "Each player scores:\n"
                "If one or more enemy units were destroyed this battle round: 4VP.\n\n"
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of the battle round.\n"
                "Each player scores:\n"
                "If more enemy units than friendly units were destroyed this battle round: 4VP.\n\n"
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of the Command phase (or the end of your turn if it is the fifth battle round and you are going second).\n"
                "The player whose turn it is:\n"
                "If the player controls one or more objective markers: 4VP.\n"
                "AND\n"
                "If the player controls more objective markers than their opponent controls: 4VP."
            ),
        )

    def score_at_command_phase(self, game, player) -> int:
        # Control-based scoring
        if game.get_battle_round() < 2:
            # Even in BR1, the control scoring applies (it says second battle round onwards for this part?)
            # The text says: Control scoring at end of Command phase from second battle round onwards.
            return 0
        # Count control
        my_controls = 0
        opp_controls = 0
        for obj in getattr(game.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc or getattr(loc, 'removed', False):
                continue
            if hasattr(loc, 'update_control'):
                loc.update_control(game)
            cp = getattr(loc, 'controlling_player', None)
            if cp is player:
                my_controls += 1
            elif cp is not None:
                opp_controls += 1
        vp = 0
        if my_controls >= 1:
            vp += 4
        if my_controls > opp_controls:
            vp += 4
        return vp

    def score_at_end_of_battle_round(self, game, player) -> int:
        # Uses game.destroyed_units_this_battle_round_by_player if available
        counts = getattr(game, 'destroyed_units_this_battle_round_by_player', None)
        if not counts:
            return 0
        me = counts.get(player, 0)
        # Opponent assumed single opponent
        opp = 0
        for p in game.players:
            if p is not player:
                opp += counts.get(p, 0)
        vp = 0
        if opp >= 1:
            vp += 4
        if game.get_battle_round() >= 2 and opp > me:
            vp += 4
        return vp


class ScorchedEarthPrimary(PrimaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Scorched Earth",
            action_text=(
                "BURN OBJECTIVE (ACTION)\n"
                "WHEN: Your Shooting phase, from the second battle round onwards.\n"
                "UNITS: One unit from your army within range of an objective marker that is not within your deployment zone.\n"
                "COMPLETES: End of your opponent's next turn or the end of the battle (whichever comes first), if your unit is still within range of the same objective marker and you control that objective marker.\n"
                "IF COMPLETED: That objective marker is burned and removed from the battlefield."
            ),
            scoring_text=(
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: Any time.\n"
                "Each time a player burns an objective marker:\n"
                "- Objective marker was in No Man's Land: 5VP.\n"
                "- Objective marker was in their opponent's deployment zone: 10VP.\n\n"
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of the Command phase (or the end of your turn if it is the fifth battle round and you are going second).\n"
                "For each objective marker that the player controls: 5VP (MAX 10VP)."
            ),
            score_cap_per_turn=10,
        )

    def score_at_command_phase(self, game, player) -> int:
        if game.get_battle_round() < 2:
            return 0
        count = 0
        for obj in getattr(game.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc or getattr(loc, 'removed', False):
                continue
            if hasattr(loc, 'update_control'):
                loc.update_control(game)
            if getattr(loc, 'controlling_player', None) is player:
                count += 1
        return count * 5


class HiddenSuppliesPrimary(PrimaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Hidden Supplies",
            setup_text=(
                "PLACE OBJECTIVE MARKERS\n"
                "Players must set up one additional objective marker in No Man's Land.\n"
                "Before setting up this new objective marker, players must first move the objective marker in the centre of the battlefield 6\" directly towards one of the corners of the battlefield "
                "(if No Man's Land touches any of the corners of the battlefield, you must move the objective marker towards one of those corners). Otherwise, the players roll-off, and the winner selects which corner the objective marker is moved towards.\n"
                "Players then set up the new objective marker 6\" from the centre of the battlefield towards the diagonally opposite corner of the battlefield to the previously moved objective marker."
            ),
            scoring_text=(
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of the Command phase (or the end of your turn if it is the fifth battle round and you are going second).\n"
                "The player whose turn it is scores as follows:\n"
                "They control one objective marker not within their deployment zone: 5VP.\n"
                "AND\n"
                "They control two objective markers not within their deployment zone: 5VP.\n"
                "AND\n"
                "They control more objective markers than their opponent controls: 5VP."
            ),
            score_cap_per_turn=None,
        )

    def score_at_command_phase(self, game, player) -> int:
        if game.get_battle_round() < 2:
            return 0
        # Count objectives you control not in your deployment
        def _in_my_dz(loc):
            try:
                zones = game.deployment_zones.get(player.name, {})
                zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
                return zone and hasattr(zone, 'contains_point') and zone.contains_point(loc.x, loc.y)
            except Exception:
                return False
        my_controls = 0
        opp_controls = 0
        for obj in getattr(game.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc or getattr(loc, 'removed', False):
                continue
            if hasattr(loc, 'update_control'):
                loc.update_control(game)
            cp = getattr(loc, 'controlling_player', None)
            if cp is player:
                if not _in_my_dz(loc):
                    my_controls += 1
            elif cp is not None:
                opp_controls += 1
        vp = 0
        if my_controls >= 1:
            vp += 5
        if my_controls >= 2:
            vp += 5
        if (my_controls + 0) > opp_controls:
            vp += 5
        return vp


class SupplyDropPrimary(PrimaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Supply Drop",
            setup_text=(
                "Start of the Battle: Players randomly select two different objective markers in No Man's Land that are not in the centre of the battlefield: "
                "the first selected is the Alpha objective, the second selected is the Omega objective.\n"
                "Start of the Fourth Battle Round: The Alpha objective is removed from the battlefield.\n"
                "Start of the Fifth Battle Round: The Omega objective is removed from the battlefield."
            ),
            scoring_text=(
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of the Command phase (or the end of your turn if it is the fifth battle round and you are going second).\n"
                "The player whose turn it is scores the following VP for each objective marker within No Man's Land that they control depending on the current battle round:\n"
                "- The second and third battle rounds: 5VP.\n"
                "- The fourth battle round: 8VP.\n"
                "- The fifth battle round: 15VP."
            ),
        )
        self.alpha = None
        self.omega = None
        self.initialized = False
        self._alpha_removed = False
        self._omega_removed = False

    def _is_no_mans_land(self, game, loc) -> bool:
        try:
            for p in game.players:
                zones = game.deployment_zones.get(p.name, {})
                zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
                if zone and hasattr(zone, 'contains_point') and zone.contains_point(loc.x, loc.y):
                    return False
            return True
        except Exception:
            return True

    def _ensure_alpha_omega(self, game):
        if self.initialized:
            return
        self.initialize_alpha_omega(game)

    def initialize_alpha_omega(self, game) -> None:
        """Start of the battle: randomly select Alpha and Omega objectives (NML, not center)."""
        if self.initialized:
            return
        candidates = []
        center_x = float(getattr(game.map, 'width', 60)) / 2.0
        center_y = float(getattr(game.map, 'height', 44)) / 2.0
        for obj in getattr(game.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc or getattr(loc, 'removed', False):
                continue
            if not self._is_no_mans_land(game, loc):
                continue
            # Exclude exact center objective marker
            if abs(float(loc.x) - center_x) < 0.01 and abs(float(loc.y) - center_y) < 0.01:
                continue
            candidates.append(obj)
        if len(candidates) >= 2:
            import random
            a, b = random.sample(candidates, 2)
            self.alpha = a
            self.omega = b
        self.initialized = True

    def _remove_if_due(self, game):
        # Remove at start of BR4 and BR5 (approximated by early Command phase in those rounds).
        br = int(game.get_battle_round() or 0)
        def _remove_obj(obj):
            try:
                loc = getattr(obj, 'location', None)
                if loc and not getattr(loc, 'removed', False):
                    loc.removed = True
                    print("INFO: Supply Drop removed objective at ({:.1f}, {:.1f})".format(loc.x, loc.y))
            except Exception:
                pass
        if br == 4 and self.alpha and not self._alpha_removed:
            _remove_obj(self.alpha)
            self._alpha_removed = True
        if br == 5 and self.omega and not self._omega_removed:
            _remove_obj(self.omega)
            self._omega_removed = True

    def score_at_command_phase(self, game, player) -> int:
        if game.get_battle_round() < 2:
            return 0
        self._ensure_alpha_omega(game)
        self._remove_if_due(game)
        # Score per No Man's Land objective you control
        br = game.get_battle_round()
        per_obj = 5 if br in (2, 3) else (8 if br == 4 else 15)
        total = 0
        for obj in getattr(game.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc or getattr(loc, 'removed', False):
                continue
            if hasattr(loc, 'update_control'):
                loc.update_control(game)
            if getattr(loc, 'controlling_player', None) is player and self._is_no_mans_land(game, loc):
                total += per_obj
        return total


# ---------- Additional Primary Missions (Chapter Approved 2025/2026) ----------

class BurdenOfTrustPrimary(PrimaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Burden of Trust",
            setup_text=(
                "At the end of the Command phase, for each objective marker that the player whose turn it is controls, "
                "they can select one unit from their army (excluding AIRCRAFT) within range of that objective marker to guard it until the start of their next turn."
            ),
            scoring_text=(
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of the Command phase (or the end of your turn if it is the fifth battle round and you are going second).\n"
                "The player whose turn it is scores:\n"
                "For each objective marker they control that is not within their deployment zone: 4VP.\n\n"
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of each player's turn.\n"
                "The opponent of the player whose turn it is:\n"
                "For each of their units (excluding Battle-shocked units) that are within range of and guarding an objective marker they control: 2VP."
            ),
        )

    def score_at_command_phase(self, game, player) -> int:
        if game.get_battle_round() < 2:
            return 0
        # 4VP for each controlled objective not within your DZ
        vp = 0
        for obj in getattr(game.map, "objectives", []):
            loc = getattr(obj, "location", None)
            if not loc or getattr(loc, "removed", False):
                continue
            if hasattr(loc, "update_control"):
                loc.update_control(game)
            if getattr(loc, "controlling_player", None) is not player:
                continue
            if not game._objective_in_player_deployment(player, loc):
                vp += 4
        return vp

    def score_at_end_of_opponents_turn(self, game, scoring_player, active_player) -> int:
        """End of active_player's turn: scoring_player is the opponent and may score for guarding."""
        if game.get_battle_round() < 2:
            return 0
        vp = 0
        for u in getattr(scoring_player.army, "units", []) or []:
            if not u.is_alive() or u.is_aircraft or u.is_battle_shocked():
                continue
            guarded = getattr(u, "guarding_objective", None)
            if guarded is None:
                continue
            loc = getattr(guarded, "location", None)
            if not loc or getattr(loc, "removed", False):
                continue
            if hasattr(loc, "update_control"):
                loc.update_control(game)
            if getattr(loc, "controlling_player", None) is not scoring_player:
                continue
            # Must still be within range of the guarded objective marker
            if game._unit_within_range_of_objective(u) is guarded:
                vp += 2
        return vp


class TheRitualPrimary(PrimaryMissionCard):
    def __init__(self):
        super().__init__(
            name="The Ritual",
            action_text=(
                "THE RITUAL (ACTION)\n"
                "STARTS: Your Shooting phase.\n"
                "UNITS: One unit from your army.\n"
                "COMPLETES: End of your turn.\n"
                "IF COMPLETED: Set up one objective marker anywhere on the battlefield wholly within No Man's Land and within 1\" of your unit, provided it can be set up exactly 12\" from one other objective marker within No Man's Land and not within 6\" of any other objective marker."
            ),
            scoring_text=(
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of the Command phase (or the end of your turn if it is the fifth battle round and you are going second).\n"
                "For each objective marker that the player controls in No Man's Land: 5VP (MAX 15VP)."
            ),
            score_cap_per_turn=15,
        )

    def _is_in_no_mans_land(self, game, loc) -> bool:
        for p in getattr(game, "players", []) or []:
            zones = game.deployment_zones.get(p.name, {})
            zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
            if zone and hasattr(zone, "contains_point") and zone.contains_point(loc.x, loc.y):
                return False
        return True

    def score_at_command_phase(self, game, player) -> int:
        if game.get_battle_round() < 2:
            return 0
        vp = 0
        for obj in getattr(game.map, "objectives", []):
            loc = getattr(obj, "location", None)
            if not loc or getattr(loc, "removed", False):
                continue
            if hasattr(loc, "update_control"):
                loc.update_control(game)
            if getattr(loc, "controlling_player", None) is player and self._is_in_no_mans_land(game, loc):
                vp += 5
        return vp

    def score_at_end_of_turn(self, game, player) -> int:
        # Fifth battle round, going second scores at end of your turn instead of command phase.
        if game.get_battle_round() != 5:
            return 0
        starting_idx = game.battle_round_starting_player_index
        if starting_idx is None:
            return 0
        going_second_player = game.players[(starting_idx + 1) % len(game.players)]
        if going_second_player is not player:
            return 0
        return self.score_at_command_phase(game, player)


class UnexplodedOrdnancePrimary(PrimaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Unexploded Ordnance",
            setup_text=(
                "START OF THE BATTLE: The objective markers within No Man's Land become a Hazard objective marker."
            ),
            action_text=(
                "MOVE HAZARD (ACTION)\n"
                "STARTS: Your Shooting phase.\n"
                "UNITS: One or more units from your army, each within range of a different Hazard objective marker you control.\n"
                "COMPLETES: End of your turn, if the unit performing this Action is still within range of the same Hazard objective marker and you control that objective marker.\n"
                "IF COMPLETED: You can move each of those objective markers up to 6\". When doing so, that objective marker cannot end that move on top of any other objective marker or model, or inside impassable parts of terrain features."
            ),
            scoring_text=(
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of each player's turn.\n"
                "The player whose turn it is scores for each Hazard objective marker that is:\n"
                "- Wholly within their opponent's deployment zone: 8VP.\n"
                "- Wholly within 6\" of their opponent's deployment zone: 5VP.\n"
                "- Wholly within 12\" of their opponent's deployment zone: 2VP."
            ),
        )

    def score_at_end_of_turn(self, game, player) -> int:
        if game.get_battle_round() < 2:
            return 0

        # Determine opponent deployment zone shape
        opponents = [p for p in getattr(game, "players", []) or [] if p is not player]
        if not opponents:
            return 0
        opp = opponents[0]
        zones = game.deployment_zones.get(opp.name, {})
        zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
        if zone is None:
            return 0

        # Build a polygon if possible for distance-to-zone checks
        poly = None
        try:
            from shapely.geometry import Polygon as _Poly, Point as _Pt
            verts = getattr(zone, "vertices", None)
            if verts:
                poly = _Poly(list(verts))
        except Exception:
            poly = None

        def _dist_to_zone(x: float, y: float) -> float:
            if poly is None:
                # If we can't compute distance, fall back to "in zone" only.
                return float("inf")
            try:
                return float(poly.distance(_Pt(float(x), float(y))))
            except Exception:
                return float("inf")

        vp = 0
        for obj in getattr(game.map, "objectives", []):
            loc = getattr(obj, "location", None)
            if not loc or getattr(loc, "removed", False):
                continue
            if not bool(getattr(loc, "is_hazard", False)):
                continue
            # Bracket scoring (take best bracket only)
            in_zone = False
            try:
                in_zone = bool(hasattr(zone, "contains_point") and zone.contains_point(loc.x, loc.y))
            except Exception:
                in_zone = False
            if in_zone:
                vp += 8
                continue
            d = _dist_to_zone(loc.x, loc.y)
            if d <= 6.0 + 1e-6:
                vp += 5
            elif d <= 12.0 + 1e-6:
                vp += 2
        return vp

# ---------- Secondary Missions ----------

class BringItDownSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Bring It Down",
            when_drawn_text=(
                "WHEN DRAWN: If there are no enemy MONSTER or VEHICLE units on the battlefield, you can discard this card and draw a new Secondary Mission card."
            ),
            fixed_text=(
                "ANY BATTLEROUND - FIXED\n"
                "WHEN: While this card is active.\n"
                "Each time an enemy MONSTER or VEHICLE unit is destroyed: 2VP.\n"
                "AND\n"
                "The total of the Wounds characteristics of the models in that destroyed unit was 15+ (at its Starting Strength): +2VP.\n"
                "AND\n"
                "The total of the Wounds characteristics of the models in that destroyed unit was 20+ (at its Starting Strength): +2VP."
            ),
            tactical_text=(
                "ANY BATTLE ROUND - TACTICAL\n"
                "WHEN: End of either player's turn.\n"
                "One or more enemy MONSTER or VEHICLE units were destroyed this turn: 4VP."
            ),
        )
        self.scoring_window = SecondaryScoringWindow.END_OF_EITHER_PLAYER_TURN

    def can_be_drawn(self, game, player) -> bool:
        # True if opponent has at least one Monster/Vehicle alive
        opponents = [p for p in game.players if p is not player]
        if not opponents:
            return False
        opp = opponents[0]
        if not opp.army:
            return False
        for unit in opp.army.units:
            if not unit.is_alive():
                continue
            kws = [kw.lower() for kw in getattr(unit, 'keywords', [])]
            if ('monster' in kws) or ('vehicle' in kws):
                return True
        return False

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        # Tactical only (Fixed is event-driven).
        if self.is_fixed_mode(game):
            return ScoreResult(vp=0, achieved=False)
        # If any destroyed unit this turn belonged to the opponent and is Monster/Vehicle, score 4 and achieve
        opponents = [p for p in game.players if p is not player]
        opp = opponents[0] if opponents else None
        if not opp:
            return ScoreResult(vp=0, achieved=False)
        for destroyed in getattr(game, 'destroyed_units_this_turn', []):
            try:
                owner = destroyed.get_parent_army().player if destroyed.get_parent_army() else None
            except Exception:
                owner = None
            if owner is opp:
                kws = [kw.lower() for kw in getattr(destroyed, 'keywords', [])]
                if ('monster' in kws) or ('vehicle' in kws):
                    return ScoreResult(vp=4, achieved=True)
        return ScoreResult(vp=0, achieved=False)

    def on_unit_destroyed(self, game, player, unit) -> int:
        # Fixed scoring: while active, score when enemy MONSTER/VEHICLE units are destroyed.
        if not self.is_fixed_mode(game):
            return 0
        try:
            owner = unit.get_parent_army().player if unit.get_parent_army() else None
        except Exception:
            owner = None
        if owner is player:
            return 0
        is_mv = False
        try:
            is_mv = bool(getattr(unit, "is_monster", False) or getattr(unit, "is_vehicle", False))
        except Exception:
            is_mv = False
        if not is_mv:
            # Fallback keyword check
            kws = [str(kw).lower() for kw in getattr(unit, "keywords", [])]
            is_mv = ("monster" in kws) or ("vehicle" in kws)
        if not is_mv:
            return 0

        # Base 2VP, +2 if starting total wounds 15+, +2 if 20+.
        try:
            stw = int(getattr(unit, "starting_total_wounds", 0) or 0)
        except Exception:
            stw = 0
        vp = 2
        if stw >= 15:
            vp += 2
        if stw >= 20:
            vp += 2
        return int(vp)


class SabotageSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Sabotage",
            action_text=(
                "SABOTAGE (ACTION)\n"
                "STARTS: Your Shooting phase.\n"
                "UNITS: One unit from your army that is within a terrain feature and not within your deployment zone.\n"
                "COMPLETES: End of your opponent's next turn or the end of the battle (whichever comes first), if your unit is on the battlefield.\n"
                "IF COMPLETED: Your unit commits sabotage."
            ),
            scoring_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: End of your opponent's turn or the end of the battle (whichever comes first).\n"
                "Your unit committed sabotage this turn and is not within your opponent's deployment zone: 3VP.\n"
                "OR\n"
                "Your unit committed sabotage this turn and is within your opponent's deployment zone: 6VP."
            ),
        )
        self.scoring_window = SecondaryScoringWindow.END_OF_OPPONENT_TURN

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        # Look for any unit on this player's side that completed a 'Sabotage' action this turn
        completed_units: List = getattr(game, 'completed_actions_this_turn', [])
        vp = 0
        for entry in completed_units:
            if entry.get('player') is not player:
                continue
            if entry.get('action_name') != 'SABOTAGE':
                continue
            # Within opponent deployment zone?
            loc = entry.get('unit_location')
            in_opponent_deployment = False
            try:
                opponent = [p for p in game.players if p is not player][0]
                zones = game.deployment_zones.get(opponent.name, {})
                zone = zones.get('zone') or zones.get('Attacker Zone') or zones.get('Defender Zone')
                if zone and hasattr(zone, 'contains_point') and loc:
                    in_opponent_deployment = zone.contains_point(loc[0], loc[1])
            except Exception:
                in_opponent_deployment = False
            vp = max(vp, 6 if in_opponent_deployment else 3)
        achieved = vp > 0
        return ScoreResult(vp=vp, achieved=achieved)


# ---------- Additional Secondary Missions ----------

class BehindEnemyLinesSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Behind Enemy Lines",
            when_drawn_text=(
                "WHEN DRAWN: If it is the first battle round, you can draw a new Secondary Mission card and shuffle this card back into your Secondary Mission deck."
            ),
            scoring_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: End of your turn.\n"
                "One unit from your army (excluding AIRCRAFT and Battle-shocked units) is wholly within your opponent's deployment zone: 3VP.\n"
                "OR\n"
                "Two or more units from your army (excluding AIRCRAFT and Battle-shocked units) are wholly within your opponent's deployment zone: 4VP."
            ),
        )
        self.shuffle_back_on_ineligible_draw = True

    def can_be_drawn(self, game, player) -> bool:
        # BR1: redraw + shuffle back into deck
        return int(getattr(game, "get_battle_round", lambda: 0)() or 0) != 1

    def on_draw(self, game, player) -> None:
        # If first battle round, allow redraw: handled by caller via can_be_drawn or deck logic
        return None

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        # Count eligible units wholly within opponent DZ
        def _in_opponent_dz(unit):
            try:
                opp = [p for p in game.players if p is not player][0]
                zones = game.deployment_zones.get(opp.name, {})
                zone = zones.get('zone') or zones.get('Attacker Zone') or zones.get('Defender Zone')
                if not zone:
                    return False
                # Any alive model wholly within; approximate by all alive models in zone
                for m in unit.models:
                    if not m.is_alive:
                        continue
                    pos = m.get_location()
                    if not pos or not zone.contains_point(pos[0], pos[1]):
                        return False
                return True
            except Exception:
                return False
        count = 0
        for u in player.army.units:
            if not u.is_alive() or u.is_aircraft or u.is_battle_shocked():
                continue
            if _in_opponent_dz(u):
                count += 1
        if count >= 2:
            return ScoreResult(vp=4, achieved=True)
        if count == 1:
            return ScoreResult(vp=3, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class StormHostileObjectiveSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Storm Hostile Objective",
            when_drawn_text=(
                "WHEN DRAWN: If it is the first battle round, you can draw a new Secondary Mission card and shuffle this card back into your Secondary Mission deck."
            ),
            scoring_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: End of your turn.\n"
                "You control one or more objective markers that were controlled by your opponent at the start of the turn: 4VP.\n\n"
                "OR\n\n"
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of your turn.\n"
                "Your opponent did not control any objective markers at the start of the turn, and you control one or more objective markers that you did not control at the start of the turn: 4VP."
            ),
        )
        self.start_of_turn_control = {}
        self.shuffle_back_on_ineligible_draw = True

    def on_draw(self, game, player) -> None:
        # Initial snapshot; Game should also call on_turn_start each turn for active cards.
        self.on_turn_start(game, player)

    def can_be_drawn(self, game, player) -> bool:
        # BR1: redraw + shuffle back into deck
        return int(getattr(game, "get_battle_round", lambda: 0)() or 0) != 1

    def on_turn_start(self, game, player) -> None:
        # Track control at start of turn for this player
        self.start_of_turn_control = {}
        for obj in getattr(game.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc or getattr(loc, 'removed', False):
                continue
            if hasattr(loc, 'update_control'):
                loc.update_control(game)
            self.start_of_turn_control[id(obj)] = getattr(loc, 'controlling_player', None)

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        # If baseline capture
        captured_hostile = False
        opp_had_any = False
        gained_control = False
        for obj in getattr(game.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc or getattr(loc, 'removed', False):
                continue
            if hasattr(loc, 'update_control'):
                loc.update_control(game)
            at_start = self.start_of_turn_control.get(id(obj), None)
            now = getattr(loc, 'controlling_player', None)
            if at_start is not None and at_start is not player:
                if now is player:
                    captured_hostile = True
            if at_start is not None and at_start is not player:
                opp_had_any = True
            if at_start is player and now is player:
                pass
            elif at_start is not player and now is player:
                gained_control = True
        if captured_hostile:
            return ScoreResult(vp=4, achieved=True)
        if game.get_battle_round() >= 2 and not opp_had_any and gained_control:
            return ScoreResult(vp=4, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class EngageOnAllFrontsSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Engage On All Fronts",
            scoring_text=(
                "If one or more units from your army (excluding AIRCRAFT and Battle-shocked units) are wholly within a table quarter, and those units are more than 6\" away from the centre of the battlefield, you have a presence in that table quarter.\n\n"
                "ANY BATTLE ROUND\n"
                "WHEN: End of your turn.\n"
                "You have a presence in two table quarters: 1VP.\n"
                "OR\n"
                "You have a presence in three table quarters: 2VP.\n"
                "OR\n"
                "You have a presence in four table quarters: 4VP."
            ),
        )

    def _unit_in_quarter(self, game, unit):
        # Deprecated: quarter presence requires wholly within; handled in score_at_end_of_turn.
        return None

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        from shapely.geometry import Polygon as _Poly
        from ..utility.aura_utils import unit_within_horizontal_distance_of_point

        # Presence in quarters by eligible units (wholly within quarter and >6" from center)
        quarters = set()
        mid_x = float(game.map.width) / 2.0
        mid_y = float(game.map.height) / 2.0

        # Define quarter polygons
        q_polys = {
            (0, 0): _Poly([(0, 0), (mid_x, 0), (mid_x, mid_y), (0, mid_y)]),
            (1, 0): _Poly([(mid_x, 0), (game.map.width, 0), (game.map.width, mid_y), (mid_x, mid_y)]),
            (0, 1): _Poly([(0, mid_y), (mid_x, mid_y), (mid_x, game.map.height), (0, game.map.height)]),
            (1, 1): _Poly([(mid_x, mid_y), (game.map.width, mid_y), (game.map.width, game.map.height), (mid_x, game.map.height)]),
        }

        def _unit_wholly_in_poly(unit, poly) -> bool:
            try:
                models = unit.get_models_for_collision()
            except Exception:
                models = unit.models
            alive = [m for m in models if getattr(m, "is_alive", True)]
            if not alive:
                return False
            for m in alive:
                try:
                    if not poly.covers(m.model_base.get_base_shape()):
                        return False
                except Exception:
                    return False
            return True

        for u in player.army.units:
            if not u.is_alive() or u.is_aircraft or u.is_battle_shocked():
                continue

            # Must be more than 6" from center: interpret as base edge distance > 6 from the center point.
            if unit_within_horizontal_distance_of_point(u, mid_x, mid_y, 6.0):
                continue

            # Determine which quarter (if any) the unit is wholly within.
            for (qx, qy), poly in q_polys.items():
                if _unit_wholly_in_poly(u, poly):
                    quarters.add((qx, qy))
                    break

        n = len(quarters)
        if n >= 4:
            return ScoreResult(vp=4, achieved=True)
        if n == 3:
            return ScoreResult(vp=2, achieved=True)
        if n == 2:
            return ScoreResult(vp=1, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class DefendStrongholdSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Defend Stronghold",
            when_drawn_text=(
                "WHEN DRAWN: If it is the first battle round, draw a new Secondary Mission card and shuffle this card back into your Secondary Mission deck."
            ),
            scoring_text=(
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of your opponent's turn or the end of the battle (whichever comes first).\n"
                "You control one or more objective markers in your deployment zone: 3VP."
            ),
        )
        self.scoring_window = SecondaryScoringWindow.END_OF_OPPONENT_TURN
        self.shuffle_back_on_ineligible_draw = True

    def can_be_drawn(self, game, player) -> bool:
        # BR1: redraw + shuffle back into deck
        return int(getattr(game, "get_battle_round", lambda: 0)() or 0) != 1

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        if game.get_battle_round() < 2:
            return ScoreResult(vp=0, achieved=False)
        # Actual timing is enforced by Game using scoring_window=END_OF_OPPONENT_TURN.
        for obj in getattr(game.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc or getattr(loc, 'removed', False):
                continue
            if hasattr(loc, 'update_control'):
                loc.update_control(game)
            if getattr(loc, 'controlling_player', None) is player:
                # In player's DZ?
                try:
                    zones = game.deployment_zones.get(player.name, {})
                    zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
                    if zone and hasattr(zone, 'contains_point') and zone.contains_point(loc.x, loc.y):
                        return ScoreResult(vp=3, achieved=True)
                except Exception:
                    pass
        return ScoreResult(vp=0, achieved=False)


class MarkedForDeathSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Marked For Death",
            when_drawn_text=(
                "WHEN DRAWN: Your opponent must select three units from their army on the battlefield. If there are only one or two units from their army on the battlefield, they must select those units. The selected units are your Alpha Target units.\n"
                "You can then select one unit from your opponent's army on the battlefield to be your Gamma Target unit. If there are no units from their army on the battlefield, discard this card and draw a new Secondary Mission card."
            ),
            scoring_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: End of either player's turn.\n"
                "One or more of your Alpha Target units were destroyed (or removed from the battlefield for any other reason) this turn: 5VP.\n"
                "OR\n"
                "None of your Alpha Target units were destroyed (or removed from the battlefield for any other reason) this turn, but your Gamma Target unit was destroyed (or removed from the battlefield for any other reason) this turn: 2VP."
            ),
        )
        self.alpha_targets = []
        self.gamma_target = None
        self.scoring_window = SecondaryScoringWindow.END_OF_EITHER_PLAYER_TURN

    def on_draw(self, game, player) -> None:
        # Opponent picks up to 3 units; we pick 1 gamma target
        try:
            opp = [p for p in game.players if p is not player][0]
            opp_units = [u for u in opp.army.units if u.is_alive()]
            self.alpha_targets = opp_units[:3]
            # Choose a distinct gamma target if possible
            self.gamma_target = None
            if opp_units:
                for u in opp_units:
                    if u not in self.alpha_targets:
                        self.gamma_target = u
                        break
                if self.gamma_target is None:
                    self.gamma_target = opp_units[0]
        except Exception:
            self.alpha_targets = []
            self.gamma_target = None

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        destroyed_this_turn = getattr(game, 'destroyed_units_this_turn', [])
        if any(u in destroyed_this_turn for u in self.alpha_targets):
            return ScoreResult(vp=5, achieved=True)
        if self.gamma_target in destroyed_this_turn:
            return ScoreResult(vp=2, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class EstablishLocusSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Establish Locus",
            action_text=(
                "ESTABLISH LOCUS (ACTION)\n"
                "STARTS: Your Shooting phase.\n"
                "UNITS: One unit from your army.\n"
                "COMPLETES: End of your turn, if that unit is within your opponent's deployment zone or within 6\" of the centre of the battlefield.\n"
                "IF COMPLETED: Your unit establishes a locus."
            ),
            scoring_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: End of your turn.\n"
                "Your unit established a locus this turn and is within 6\" of the centre of the battlefield: 2VP.\n"
                "OR\n"
                "Your unit established a locus this turn and is within your opponent's deployment zone: 4VP."
            ),
        )

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        completed = [e for e in getattr(game, 'completed_actions_this_turn', []) if e.get('player') is player and e.get('action_name') == 'ESTABLISH_LOCUS']
        vp = 0
        for entry in completed:
            loc = entry.get('unit_location')
            # Check center vs opponent DZ
            center = False
            in_opponent_dz = False
            try:
                midx = game.map.width / 2.0
                midy = game.map.height / 2.0
                # unit_location is a point; check radial distance to center (not box distance)
                dx = float(loc[0]) - float(midx)
                dy = float(loc[1]) - float(midy)
                center = (dx * dx + dy * dy) ** 0.5 <= 6.0 + 1e-6
            except Exception:
                center = False
            try:
                opp = [p for p in game.players if p is not player][0]
                zones = game.deployment_zones.get(opp.name, {})
                zone = zones.get('zone') or zones.get('Attacker Zone') or zones.get('Defender Zone')
                in_opponent_dz = zone and hasattr(zone, 'contains_point') and zone.contains_point(loc[0], loc[1])
            except Exception:
                in_opponent_dz = False
            if in_opponent_dz:
                vp = max(vp, 4)
            elif center:
                vp = max(vp, 2)
        return ScoreResult(vp=vp, achieved=(vp > 0))


class CleanseSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Cleanse",
            action_text=(
                "CLEANSE (ACTION)\n"
                "WHEN: Your Shooting phase.\n"
                "UNITS: One or more units from your army within range of an objective marker that is not within your deployment zone.\n"
                "COMPLETES: End of your turn, if the unit performing this Action is still within range of the same objective marker and you control that objective marker.\n"
                "IF COMPLETED: That objective marker is cleansed by your army."
            ),
            fixed_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: End of your turn.\n"
                "One objective marker was cleansed by your army this turn: 2VP.\n"
                "OR\n"
                "Two or more objective markers were cleansed by your army this turn: 4VP."
            ),
            tactical_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: End of your turn.\n"
                "One objective marker was cleansed by your army this turn: 2VP.\n"
                "OR\n"
                "Two or more objective markers were cleansed by your army this turn: 5VP."
            ),
        )

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        completed = [e for e in getattr(game, 'completed_actions_this_turn', []) if e.get('player') is player and e.get('action_name') == 'CLEANSE']
        num = len(completed)
        if num >= 2:
            return ScoreResult(vp=(4 if self.is_fixed_mode(game) else 5), achieved=True)
        if num == 1:
            return ScoreResult(vp=2, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class AssassinationSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Assassination",
            fixed_text=(
                "ANY BATTLEROUND - FIXED\n"
                "WHEN: While this card is active.\n"
                "Each time an enemy CHARACTER model with a Wounds characteristic of 4 or higher is destroyed: 4VP.\n"
                "Each time an enemy CHARACTER model with a Wounds characteristic of less then 4 is destroyed: 3VP."
            ),
            tactical_text=(
                "ANY BATTLEROUND - TACTICAL\n"
                "WHEN: End of either player's turn.\n"
                "One or more enemy CHARACTER models were destroyed this turn: 5VP.\n"
                "OR\n"
                "All enemy CHARACTER models have been destroyed during the battle: 5VP."
            ),
        )
        self.scoring_window = SecondaryScoringWindow.END_OF_EITHER_PLAYER_TURN

    def on_model_destroyed(self, game, player, model) -> int:
        """Fixed scoring: while active, score when enemy CHARACTER models are destroyed."""
        if not self.is_fixed_mode(game):
            return 0
        if not bool(getattr(model, "is_character", False)):
            return 0
        try:
            owner = getattr(getattr(model, "parent_unit", None), "get_parent_army", lambda: None)()
            owner_player = owner.player if owner is not None else None
        except Exception:
            owner_player = None
        if owner_player is player:
            return 0
        try:
            wounds_char = int(getattr(model, "_base_wounds", 0) or 0)
        except Exception:
            wounds_char = 0
        return 4 if wounds_char >= 4 else 3

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        # Tactical scoring only (Fixed is event-driven).
        if self.is_fixed_mode(game):
            return ScoreResult(vp=0, achieved=False)

        destroyed = getattr(game, 'models_destroyed_this_turn', [])
        # Score if one or more ENEMY character models were destroyed this turn.
        for m in destroyed:
            if not bool(getattr(m, "is_character", False)):
                continue
            try:
                owner_army = m.parent_unit.get_parent_army() if getattr(m, "parent_unit", None) else None
                owner_player = owner_army.player if owner_army else None
            except Exception:
                owner_player = None
            if owner_player is not None and owner_player is not player:
                return ScoreResult(vp=5, achieved=True)

        # Or if all enemy CHARACTER models have been destroyed during the battle (game-level tracking).
        if getattr(game, 'all_enemy_characters_destroyed', False):
            return ScoreResult(vp=5, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class NoPrisonersSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="No Prisoners",
            fixed_text=(
                "ANY BATTLEROUND - FIXED\n"
                "WHEN: While this card is active.\n"
                "Each time an enemy Bodyguard unit or enemy non-CHARACTER unit is destroyed: 2VP (MAX 5VP)."
            ),
            tactical_text=(
                "ANY BATTLEROUND - TACTICAL\n"
                "WHEN: While this card is active.\n"
                "Each time an enemy unit is destroyed: 2VP (MAX 5VP)."
            ),
            score_cap_total=5,
        )

    def on_unit_destroyed(self, game, player, unit) -> int:
        # Fixed excludes CHARACTER units; Tactical includes all enemy units.
        try:
            owner = unit.get_parent_army().player if unit.get_parent_army() else None
        except Exception:
            owner = None
        if owner is player:
            return 0

        if self.is_fixed_mode(game):
            try:
                if bool(getattr(unit, "is_character", False)):
                    return 0
            except Exception:
                pass
        return 2


class CullTheHordeSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Cull the Horde",
            when_drawn_text=(
                "WHEN DRAWN: If there are no enemy units on the battlefield that satisfy the condition required to achieve this card, you can discard this card and draw a new Secondary Mission card."
            ),
            fixed_text=(
                "ANY BATTLEROUND - FIXED\n"
                "WHEN: While this card is active.\n"
                "Each time an enemy INFANTRY unit with a Starting Strength of 13+ (including Attached units) is destroyed: 5VP."
            ),
            tactical_text=(
                "ANY BATTLEROUND - TACTICAL\n"
                "WHEN: End of either player's turn.\n"
                "One or more enemy INFANTRY units with a Starting Strength of 13+ (including Attached units) were destroyed this turn: 5VP."
            ),
        )
        self.scoring_window = SecondaryScoringWindow.END_OF_EITHER_PLAYER_TURN

    def _starting_strength_including_attached(self, unit) -> int:
        try:
            base = int(getattr(unit, "starting_model_count", 0) or 0)
        except Exception:
            base = 0
        try:
            leaders = list(getattr(unit, "attached_leaders", []) or [])
        except Exception:
            leaders = []
        for l in leaders:
            try:
                base += int(getattr(l, "starting_model_count", 0) or 0)
            except Exception:
                continue
        return int(base)

    def can_be_drawn(self, game, player) -> bool:
        # Eligible if opponent has an INFANTRY unit with Starting Strength 13+ on the battlefield.
        try:
            opp = [p for p in game.players if p is not player][0]
        except Exception:
            return False
        if not getattr(opp, "army", None):
            return False
        for u in getattr(opp.army, "units", []) or []:
            if not getattr(u, "is_alive", lambda: False)():
                continue
            try:
                if not bool(getattr(u, "is_infantry", False)):
                    continue
            except Exception:
                continue
            if self._starting_strength_including_attached(u) >= 13:
                return True
        return False

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        # Tactical scoring only (Fixed is event-driven).
        if self.is_fixed_mode(game):
            return ScoreResult(vp=0, achieved=False)
        destroyed = getattr(game, 'destroyed_units_this_turn', [])
        for u in destroyed:
            try:
                owner = u.get_parent_army().player if u.get_parent_army() else None
            except Exception:
                owner = None
            if owner is player:
                continue
            try:
                if not bool(getattr(u, "is_infantry", False)):
                    continue
            except Exception:
                continue
            if self._starting_strength_including_attached(u) >= 13:
                return ScoreResult(vp=5, achieved=True)
        return ScoreResult(vp=0, achieved=False)

    def on_unit_destroyed(self, game, player, unit) -> int:
        # Fixed scoring: each time an enemy qualifying INFANTRY unit is destroyed.
        if not self.is_fixed_mode(game):
            return 0
        try:
            owner = unit.get_parent_army().player if unit.get_parent_army() else None
        except Exception:
            owner = None
        if owner is player:
            return 0
        try:
            if not bool(getattr(unit, "is_infantry", False)):
                return 0
        except Exception:
            return 0
        if self._starting_strength_including_attached(unit) >= 13:
            return 5
        return 0


class DisplayOfMightSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Display of Might",
            when_drawn_text=(
                "WHEN DRAWN: If it is the first battle round, draw a new Secondary Mission card and shuffle this card back into your Secondary Mission deck."
            ),
            scoring_text=(
                "SECOND BATTLE ROUND ONWARDS\n"
                "WHEN: End of your turn.\n"
                "There are more units from your army than from your opponent's army wholly within No Man's Land: 4VP."
            ),
        )
        self.shuffle_back_on_ineligible_draw = True

    def can_be_drawn(self, game, player) -> bool:
        # BR1: redraw + shuffle back into deck
        return int(getattr(game, "get_battle_round", lambda: 0)() or 0) != 1

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        if game.get_battle_round() < 2:
            return ScoreResult(vp=0, achieved=False)
        def _wholly_in_nml(unit):
            try:
                # wholly in NML: all alive models outside both DZs
                for m in unit.models:
                    if not m.is_alive:
                        continue
                    pos = m.get_location()
                    if not pos:
                        return False
                    in_any_dz = False
                    for p in game.players:
                        zones = game.deployment_zones.get(p.name, {})
                        zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
                        if zone and hasattr(zone, 'contains_point') and zone.contains_point(pos[0], pos[1]):
                            in_any_dz = True
                            break
                    if in_any_dz:
                        return False
                return True
            except Exception:
                return False
        my_count = sum(1 for u in player.army.units if u.is_alive() and _wholly_in_nml(u))
        opp = [p for p in game.players if p is not player][0]
        opp_count = sum(1 for u in opp.army.units if u.is_alive() and _wholly_in_nml(u))
        if my_count > opp_count:
            return ScoreResult(vp=4, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class OverwhelmingForceSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Overwhelming Force",
            scoring_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: While this card is active.\n"
                "Each time an enemy unit that started the turn within range of an objective marker is destroyed: 3VP (MAX 5VP).\n\n"
                "NOTE: Destroyed Leader and Bodyguard units count separately for the purpose of scoring this Secondary Mission, provided that Attached unit started the turn within range of an objective marker."
            ),
            score_cap_total=5,
        )

    def on_unit_destroyed(self, game, player, unit) -> int:
        # The test harness should ensure the unit started within objective range; here we trust caller
        return 3


class ExtendBattleLinesSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Extend Battle Lines",
            scoring_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: End of your turn.\n"
                "You control one or more objective markers within your deployment zone and one or more objective markers within No Man's Land: 4VP.\n"
                "OR\n"
                "You control one or more objective markers within No Man's Land: 2VP."
            ),
        )

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        controls_dz = False
        controls_nml = False
        for obj in getattr(game.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc or getattr(loc, 'removed', False):
                continue
            if hasattr(loc, 'update_control'):
                loc.update_control(game)
            cp = getattr(loc, 'controlling_player', None)
            if cp is not player:
                continue
            # In player's DZ?
            try:
                pz = game.deployment_zones.get(player.name, {}).get('zone')
                if pz and hasattr(pz, 'contains_point') and pz.contains_point(loc.x, loc.y):
                    controls_dz = True
            except Exception:
                pass
            # In NML (not in either DZ)
            in_any_dz = False
            for p in game.players:
                z = game.deployment_zones.get(p.name, {}).get('zone')
                if z and hasattr(z, 'contains_point') and z.contains_point(loc.x, loc.y):
                    in_any_dz = True
                    break
            if not in_any_dz:
                controls_nml = True
        if controls_dz and controls_nml:
            return ScoreResult(vp=4, achieved=True)
        if controls_nml:
            return ScoreResult(vp=2, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class ATemptingTargetSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="A Tempting Target",
            when_drawn_text=(
                "WHEN DRAWN: Your opponent must select one objective in No Man's Land to be your Tempting Target objective marker."
            ),
            scoring_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: End of either player's turn.\n"
                "You control your Tempting Target objective marker: 5VP."
            ),
        )
        self.target_objective = None
        self.scoring_window = SecondaryScoringWindow.END_OF_EITHER_PLAYER_TURN

    def on_draw(self, game, player) -> None:
        try:
            # Choose first NML objective deterministically as opponent's choice substitute
            for obj in getattr(game.map, 'objectives', []):
                loc = getattr(obj, 'location', None)
                if not loc or getattr(loc, 'removed', False):
                    continue
                in_any_dz = False
                for p in game.players:
                    z = game.deployment_zones.get(p.name, {}).get('zone')
                    if z and hasattr(z, 'contains_point') and z.contains_point(loc.x, loc.y):
                        in_any_dz = True
                        break
                if not in_any_dz:
                    self.target_objective = obj
                    break
        except Exception:
            self.target_objective = None

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        if not self.target_objective:
            return ScoreResult(vp=0, achieved=False)
        loc = getattr(self.target_objective, 'location', None)
        if not loc or getattr(loc, 'removed', False):
            return ScoreResult(vp=0, achieved=False)
        if hasattr(loc, 'update_control'):
            loc.update_control(game)
        if getattr(loc, 'controlling_player', None) is player:
            return ScoreResult(vp=5, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class RecoverAssetsSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Recover Assets",
            when_drawn_text=(
                "WHEN DRAWN: If you are playing an Incursion mission, or if there are fewer than three units from your army on the battlefield, you can discard this card and draw a new Secondary Mission card."
            ),
            action_text=(
                "RECOVER ASSETS (ACTION)\n"
                "WHEN: Your Shooting phase.\n"
                "UNITS: Two or more units from your army, if each of those units is wholly within a different one of the following areas: your deployment zone; No Man's Land; your opponent's deployment zone.\n"
                "COMPLETES: End of your turn, if either two or three of those units are on the battlefield.\n"
                "IF COMPLETED: Those units recover assets."
            ),
            scoring_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: End of your turn or the end of the battle (whichever comes first).\n"
                "Two of your units recovered assets this turn: 3VP.\n"
                "OR\n"
                "Three of your units recovered assets this turn: 5VP."
            ),
        )

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        completed = [e for e in getattr(game, 'completed_actions_this_turn', []) if e.get('player') is player and e.get('action_name') == 'RECOVER_ASSETS']
        counts = [e.get('units_count', 0) for e in completed]
        max_c = max(counts) if counts else 0
        if max_c >= 3:
            return ScoreResult(vp=5, achieved=True)
        if max_c >= 2:
            return ScoreResult(vp=3, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class AreaDenialSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Area Denial",
            scoring_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: End of your turn.\n"
                "One or more units from your army (excluding AIRCRAFT and Battle-shocked units) are within 3\" of the centre of the battlefield, and there are no enemy units within 3\" of the centre of the battlefield: 2VP.\n"
                "OR\n"
                "One or more units from your army (excluding AIRCRAFT and Battle-shocked units) are within 3\" of the centre of the battlefield, and there are no enemy units within 6\" of the centre of the battlefield: 5VP."
            ),
        )

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        from ..utility.aura_utils import unit_within_horizontal_distance_of_point

        midx = float(game.map.width) / 2.0
        midy = float(game.map.height) / 2.0

        # Our presence: one or more eligible units within 3" (base edge distance).
        my_in_3 = False
        for u in player.army.units:
            if not u.is_alive() or u.is_aircraft or u.is_battle_shocked():
                continue
            if unit_within_horizontal_distance_of_point(u, midx, midy, 3.0):
                my_in_3 = True
                break
        if not my_in_3:
            return ScoreResult(vp=0, achieved=False)

        # Enemy proximity: any enemy unit within 3"/6".
        enemy_within_3 = False
        enemy_within_6 = False
        for opp in [p for p in game.players if p is not player]:
            for u in opp.army.units:
                if not u.is_alive():
                    continue
                if unit_within_horizontal_distance_of_point(u, midx, midy, 3.0):
                    enemy_within_3 = True
                if unit_within_horizontal_distance_of_point(u, midx, midy, 6.0):
                    enemy_within_6 = True

        if not enemy_within_6:
            return ScoreResult(vp=5, achieved=True)
        if not enemy_within_3:
            return ScoreResult(vp=2, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class SecureNoMansLandSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Secure No Man's Land",
            scoring_text=(
                "ANY BATTLE ROUND\n"
                "WHEN: End of your turn.\n"
                "You control one objective marker in No Man's Land: 2VP.\n"
                "OR\n"
                "You control two or more objective markers in No Man's Land: 5VP."
            ),
        )

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        def _in_nml(loc):
            for p in game.players:
                z = game.deployment_zones.get(p.name, {}).get('zone')
                if z and hasattr(z, 'contains_point') and z.contains_point(loc.x, loc.y):
                    return False
            return True
        nml_controls = 0
        for obj in getattr(game.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc or getattr(loc, 'removed', False):
                continue
            if hasattr(loc, 'update_control'):
                loc.update_control(game)
            if getattr(loc, 'controlling_player', None) is player and _in_nml(loc):
                nml_controls += 1
        if nml_controls >= 2:
            return ScoreResult(vp=5, achieved=True)
        if nml_controls == 1:
            return ScoreResult(vp=2, achieved=True)
        return ScoreResult(vp=0, achieved=False)


# ---------- Deck helpers ----------

def default_secondary_deck() -> List[SecondaryMissionCard]:
    # Build full deck and shuffle for randomness each game
    deck: List[SecondaryMissionCard] = [
        BringItDownSecondary(),
        SabotageSecondary(),
        BehindEnemyLinesSecondary(),
        StormHostileObjectiveSecondary(),
        EngageOnAllFrontsSecondary(),
        DefendStrongholdSecondary(),
        MarkedForDeathSecondary(),
        EstablishLocusSecondary(),
        CleanseSecondary(),
        AssassinationSecondary(),
        NoPrisonersSecondary(),
        CullTheHordeSecondary(),
        DisplayOfMightSecondary(),
        OverwhelmingForceSecondary(),
        ExtendBattleLinesSecondary(),
        ATemptingTargetSecondary(),
        RecoverAssetsSecondary(),
        AreaDenialSecondary(),
        SecureNoMansLandSecondary(),
    ]
    try:
        import random
        random.shuffle(deck)
    except Exception:
        pass
    return deck
