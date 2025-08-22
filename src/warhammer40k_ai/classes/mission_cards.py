from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class ScoreResult:
    vp: int
    achieved: bool = False  # For secondary cards that complete upon scoring


@dataclass
class MissionCard:
    name: str
    description: str
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
    # When drawn gating (e.g., Bring It Down redraw if no valid targets)
    def can_be_drawn(self, game, player) -> bool:
        return True

    # Evaluation windows. These return ScoreResult with achieved flag when the card should be discarded
    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        return ScoreResult(vp=0, achieved=False)

    # Optional hook when the card is drawn
    def on_draw(self, game, player) -> None:
        return None


# ---------- Primary Missions ----------

class TakeAndHoldPrimary(PrimaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Take and Hold",
            description=(
                "From the second battle round, at end of your Command phase (or end of your turn if "
                "it is the fifth battle round and you are going second), score 5VP for each objective "
                "marker you control (up to 15VP per turn)."
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
            description=(
                "From the second battle round, at end of your Command phase score 4VP for each objective "
                "you control (up to 12VP per turn). Additionally, at end of each turn, each player scores "
                "1VP for each objective marker they have terraformed. Includes a Terraform Action."
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
            description=(
                "From the second battle round, at end of your Command phase (or end of your turn if it is the fifth "
                "battle round and you are going second): If you do not control the objective in your deployment zone, "
                "score 3VP for each objective you control. Otherwise, score 3VP for your home objective and 5VP for each "
                "other objective you control (up to 15VP per turn)."
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
            description=(
                "End of battle round: score 4VP if one or more enemy units were destroyed this battle round; from the "
                "second battle round also score 4VP if more enemy units than friendly units were destroyed. "
                "End of your Command phase (or end of your turn if fifth round and going second): score 4VP if you "
                "control one or more objective markers, plus 4VP if you control more than opponent."
            )
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
            description=(
                "Action: Burn Objective from your Shooting phase (BR2+): unit within range of an objective not in your "
                "deployment zone. Completes at end of opponent’s next turn if still in range and you control it. If "
                "completed, remove that objective and immediately score 5VP (No Man’s Land) or 10VP (opponent DZ). "
                "At end of your Command phase (BR2+), score 5VP for each objective you control (up to 10VP/turn)."
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
            description=(
                "Place Objective Markers step modifies center objective and adds one in No Man’s Land. Scoring (BR2+): "
                "End of your Command phase, cumulative 5VP: control one not in your DZ; control two not in your DZ; "
                "control more than opponent."
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
            description=(
                "At battle start select two distinct No Man’s Land objectives (not center): Alpha and Omega. Remove "
                "Alpha at start of BR4, Omega at start of BR5. Scoring (BR2+): End of your Command phase, for each "
                "No Man’s Land objective you control: 5VP in BR2-3, 8VP in BR4, 15VP in BR5."
            )
        )
        self.alpha = None
        self.omega = None
        self.initialized = False

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
        # Pick two No Man's Land objectives not center
        candidates = []
        center_x = getattr(game.map, 'width', 60) / 2.0
        center_y = getattr(game.map, 'height', 44) / 2.0
        for obj in getattr(game.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc or getattr(loc, 'removed', False):
                continue
            if not self._is_no_mans_land(game, loc):
                continue
            # Exclude exact center
            if abs(loc.x - center_x) < 0.01 and abs(loc.y - center_y) < 0.01:
                continue
            candidates.append(obj)
        if len(candidates) >= 2:
            # Deterministic pick: first two
            self.alpha = candidates[0]
            self.omega = candidates[1]
        self.initialized = True

    def _remove_if_due(self, game):
        # Remove at start of BR4 and BR5; approximate by Command phase in those rounds
        br = game.get_battle_round()
        def _remove_obj(obj):
            try:
                loc = getattr(obj, 'location', None)
                if loc and not getattr(loc, 'removed', False):
                    loc.removed = True
                    print("🔥 Supply Drop removed objective at ({:.1f}, {:.1f})".format(loc.x, loc.y))
            except Exception:
                pass
        if br >= 4 and self.alpha:
            _remove_obj(self.alpha)
        if br >= 5 and self.omega:
            _remove_obj(self.omega)

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


# ---------- Secondary Missions ----------

class BringItDownSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Bring It Down",
            description=(
                "When drawn: If there are no enemy MONSTER or VEHICLE units on the battlefield, you can discard "
                "this card and draw a new one. Any battle round: At end of either player's turn, if one or more enemy "
                "MONSTER or VEHICLE units were destroyed this turn, score 4VP."
            ),
        )

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


class SabotageSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Sabotage",
            description=(
                "Sabotage (Action): Starts in your Shooting phase by one unit within a terrain feature and not in "
                "your deployment zone. Completes at the end of your opponent’s next turn or end of battle, if the unit "
                "is still on the battlefield. End of your opponent’s turn or end of battle: If your unit committed "
                "sabotage this turn, score 3VP (6VP if within your opponent’s deployment zone)."
            ),
        )

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
            description=(
                "End of your turn: 3VP if one eligible unit wholly within opponent DZ; 4VP if two+ eligible units."
            ),
        )

    def can_be_drawn(self, game, player) -> bool:
        # Can redraw on BR1
        return True

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
            description=(
                "End of your turn: 4VP if you control objective(s) opponent controlled at start; or BR2+ 4VP if "
                "opponent controlled none at start and you control objective(s) you did not control at start."
            ),
        )
        self.start_of_turn_control = {}

    def on_draw(self, game, player) -> None:
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
            description=(
                "End of your turn: 1VP/2VP/4VP for presence in 2/3/4 quarters (eligible units only)."
            ),
        )

    def _unit_in_quarter(self, game, unit):
        # Use first alive model position to determine quarter
        for m in unit.models:
            if not m.is_alive:
                continue
            x, y, *_ = m.get_location()
            return (x, y)
        return None

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        # Presence in quarters by eligible units
        quarters = set()
        mid_x = game.map.width / 2.0
        mid_y = game.map.height / 2.0
        for u in player.army.units:
            if not u.is_alive() or u.is_aircraft or u.is_battle_shocked():
                continue
            pos = self._unit_in_quarter(game, u)
            if not pos:
                continue
            x, y = pos
            # Must be more than 6" from center to count
            if abs(x - mid_x) <= 6 and abs(y - mid_y) <= 6:
                continue
            qx = 0 if x < mid_x else 1
            qy = 0 if y < mid_y else 1
            quarters.add((qx, qy))
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
            description=(
                "BR2+: End of opponent’s turn or end of battle: 3VP if you control one or more objectives in your DZ."
            ),
        )

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        if game.get_battle_round() < 2:
            return ScoreResult(vp=0, achieved=False)
        # Only scores at end of opponent's turn or end of battle; approximate: allow any end-of-turn for now
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
            description=(
                "On draw: opponent selects three Alpha Targets (or fewer if fewer units). You select one Gamma Target. "
                "End of either turn: 5VP if an Alpha Target was destroyed; otherwise 2VP if Gamma Target was destroyed."
            ),
        )
        self.alpha_targets = []
        self.gamma_target = None

    def on_draw(self, game, player) -> None:
        # Opponent picks up to 3 units; we pick 1 gamma target
        try:
            opp = [p for p in game.players if p is not player][0]
            opp_units = [u for u in opp.army.units if u.is_alive()]
            self.alpha_targets = opp_units[:3]
            self.gamma_target = opp_units[0] if opp_units else None
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
            description=(
                "Action in Shooting phase: complete end of your turn if within opponent DZ or within 6\" of center; "
                "score 2VP for center locus or 4VP for opponent DZ locus."
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
                center = abs(loc[0] - midx) <= 6 and abs(loc[1] - midy) <= 6
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
            description=(
                "Action in Shooting phase: end of your turn, score 2VP for one cleansed objective or 5VP for two+."
            ),
        )

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        completed = [e for e in getattr(game, 'completed_actions_this_turn', []) if e.get('player') is player and e.get('action_name') == 'CLEANSE']
        num = len(completed)
        if num >= 2:
            return ScoreResult(vp=5, achieved=True)
        if num == 1:
            return ScoreResult(vp=2, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class AssassinationSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Assassination",
            description=(
                "End of either turn: 5VP if an enemy CHARACTER model was destroyed this turn, or 5VP if all enemy CHARACTERs were destroyed during the battle."
            ),
        )

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        # Immediate per-turn scoring for CHARACTER destroyed
        destroyed = getattr(game, 'models_destroyed_this_turn', [])
        if any(getattr(m, 'is_character', False) for m in destroyed):
            return ScoreResult(vp=5, achieved=True)
        # Or if all enemy CHARACTERs destroyed during the battle (track via game flag if available)
        if getattr(game, 'all_enemy_characters_destroyed', False):
            return ScoreResult(vp=5, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class NoPrisonersSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="No Prisoners",
            description=(
                "While active: score 2VP each time an enemy unit is destroyed (up to 5VP)."
            ),
            score_cap_total=5,
        )

    def on_unit_destroyed(self, game, player, unit) -> int:
        return 2


class CullTheHordeSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Cull the Horde",
            description=(
                "End of either turn: 5VP if an enemy INFANTRY unit with Starting Strength 13+ (including Attached) was destroyed this turn."
            ),
        )

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        destroyed = getattr(game, 'destroyed_units_this_turn', [])
        for u in destroyed:
            if 'Infantry' in getattr(u, 'keywords', []) and getattr(u, 'starting_strength', 0) >= 13:
                return ScoreResult(vp=5, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class DisplayOfMightSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Display of Might",
            description=(
                "End of your turn: 4VP if more of your units than opponent’s units are wholly within No Man’s Land."
            ),
        )

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
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
            description=(
                "While active: 3VP each time an enemy unit that started the turn within range of an objective marker is destroyed (up to 5VP)."
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
            description=(
                "End of your turn: 4VP if you control an objective in your DZ and one in NML; OR 2VP if you control one or more in NML."
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
            description=(
                "On draw: opponent selects one No Man’s Land objective as your Tempting Target. End of either turn: 5VP if you control it."
            ),
        )
        self.target_objective = None

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
            description=(
                "Action in Shooting phase with two or more units across DZ/NML/opponent DZ; end of your turn or end of battle: 3VP for two units, 5VP for three."
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
            description=(
                "End of your turn: 2VP if ≥1 unit within 3\" of center and no enemy within 3\"; 5VP if no enemy within 6\"."
            ),
        )

    def score_at_end_of_turn(self, game, player) -> ScoreResult:
        midx = game.map.width / 2.0
        midy = game.map.height / 2.0
        def _within(r, pos):
            return abs(pos[0] - midx) <= r and abs(pos[1] - midy) <= r
        my_in_3 = False
        enemy_within_3 = False
        enemy_within_6 = False
        for u in player.army.units:
            if not u.is_alive() or u.is_aircraft or u.is_battle_shocked():
                continue
            for m in u.models:
                if not m.is_alive:
                    continue
                pos = m.get_location()
                if _within(3, pos):
                    my_in_3 = True
        for opp in [p for p in game.players if p is not player]:
            for u in opp.army.units:
                if not u.is_alive():
                    continue
                for m in u.models:
                    if not m.is_alive:
                        continue
                    pos = m.get_location()
                    if _within(3, pos):
                        enemy_within_3 = True
                    if _within(6, pos):
                        enemy_within_6 = True
        if my_in_3 and not enemy_within_6:
            return ScoreResult(vp=5, achieved=True)
        if my_in_3 and not enemy_within_3:
            return ScoreResult(vp=2, achieved=True)
        return ScoreResult(vp=0, achieved=False)


class SecureNoMansLandSecondary(SecondaryMissionCard):
    def __init__(self):
        super().__init__(
            name="Secure No Man’s Land",
            description=(
                "End of your turn: 2VP if you control one NML objective; 5VP if you control two+."
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
