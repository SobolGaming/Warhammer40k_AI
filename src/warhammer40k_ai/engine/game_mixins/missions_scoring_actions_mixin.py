from __future__ import annotations

from ._shared import *  # noqa: F401,F403
import logging
logger = logging.getLogger(__name__)


class GameMissionsScoringActionsMixin:
    def can_score_objectives(self) -> bool:
        """Check if objectives can grant points in the current battle round.

        According to Warhammer 40k rules, objectives cannot grant points until
        the 2nd battle round.

        Returns:
            bool: True if objectives can grant points, False otherwise
        """
        return self.turn >= 2

    def get_battle_round(self) -> int:
        """Get the current battle round number.

        Returns:
            int: Current battle round (1-based)
        """
        return self.turn

    # ---------- Scoring windows and tracking ----------

    # Mission pack VP caps (as specified by project rules).
    VP_MAX_TOTAL = 100
    VP_MAX_PRIMARY = 50
    VP_MAX_SECONDARY = 40
    VP_MAX_BATTLE_READY = 10
    VP_MAX_PRIMARY_PLUS_SECONDARY = 90
    VP_MAX_PER_FIXED_SECONDARY_CARD = 20

    def _is_fixed_secondaries(self, player: Player | None = None) -> bool:
        """
        True if the game is using Fixed Secondaries.

        Scoring caps depend on this (20VP max per fixed card). The rest of the fixed-vs-tactical
        flow (draw/discard differences) may be implemented elsewhere.
        """
        mode = getattr(self, "secondary_mission_mode", None)
        return str(mode).lower() == "fixed"

    def _cap_card_vp(self, *, card: object | None, requested_vp: int, player: Player, source: str) -> int:
        """Apply per-card per-turn/total caps (including the Fixed-mission 20VP per-card cap)."""
        if not card:
            return max(0, int(requested_vp or 0))

        vp = int(requested_vp or 0)
        if vp <= 0:
            return 0

        # Per-turn cap (applies whenever the card scores this window).
        per_turn_cap = getattr(card, "score_cap_per_turn", None)
        if per_turn_cap is not None:
            vp = min(vp, int(per_turn_cap))

        # Total cap across the battle for this specific card instance.
        total_scored = int(getattr(card, "total_scored", 0) or 0)
        total_cap = getattr(card, "score_cap_total", None)
        effective_total_cap: int | None = None
        if total_cap is not None:
            effective_total_cap = int(total_cap)

        # Fixed missions: 20VP maximum per Fixed Mission card.
        if source == "secondary" and self._is_fixed_secondaries(player):
            if effective_total_cap is None:
                effective_total_cap = self.VP_MAX_PER_FIXED_SECONDARY_CARD
            else:
                effective_total_cap = min(effective_total_cap, self.VP_MAX_PER_FIXED_SECONDARY_CARD)

        if effective_total_cap is not None:
            remaining = max(0, effective_total_cap - total_scored)
            vp = min(vp, remaining)

        return max(0, int(vp))

    def _notify_vp_capped(
        self,
        *,
        player: Player,
        source: str,
        requested_vp: int,
        awarded_vp: int,
        lost_vp: int,
        reasons: list[str],
        card: object | None = None,
    ) -> None:
        """Notify that VP were lost due to caps (event system only)."""
        if lost_vp <= 0:
            return
        card_name = None
        if card is not None:
            card_name = getattr(card, "name", None)
        payload = {
            "player": player,
            "source": source,
            "requested_vp": int(requested_vp),
            "awarded_vp": int(awarded_vp),
            "lost_vp": int(lost_vp),
            "reasons": list(reasons or []),
            "card_name": card_name,
        }
        if not hasattr(self, "event_system") or not hasattr(self.event_system, "publish"):
            raise RuntimeError("Event system missing for vp_capped notification.")
        self.event_system.publish("vp_capped", **payload)

    def _current_phase_label(self) -> str:
        if hasattr(self, "is_in_setup_phase") and self.is_in_setup_phase():
            setup_phase = self.get_current_setup_phase()
            return setup_phase.name.replace("_", " ").title() if setup_phase else "Setup"
        phase = getattr(self, "phase", None)
        if phase is None:
            return "Unknown Phase"
        if hasattr(phase, "name"):
            return str(phase.name).replace("_", " ").title()
        return str(phase)

    def _record_vp_award(
        self,
        *,
        player: Player,
        requested_vp: int,
        awarded_vp: int,
        source: str,
        card: object | None = None,
        details: list[str] | str | None = None,
        timing: str | None = None,
    ) -> None:
        if not hasattr(player, "vp_history") or player.vp_history is None:
            player.vp_history = []
        card_name = getattr(card, "name", None) if card is not None else None
        card_scoring_text = None
        if card is not None:
            card_scoring_text = getattr(card, "scoring_text", None) or getattr(card, "summary", None)
        entry = {
            "round": int(getattr(self, "get_battle_round", lambda: 0)() or 0),
            "phase": self._current_phase_label(),
            "timing": timing,
            "source": str(source or ""),
            "card_name": card_name,
            "awarded": int(awarded_vp or 0),
            "requested": int(requested_vp or 0),
            "details": details,
            "card_scoring_text": card_scoring_text,
        }
        player.vp_history.append(entry)

    def award_vp(
        self,
        player: Player,
        requested_vp: int,
        *,
        source: str,
        card: object | None = None,
        details: list[str] | str | None = None,
        timing: str | None = None,
    ) -> int:
        """
        Award VP to a player, enforcing caps:
        - Primary Mission: 50VP max
        - Secondary Missions: 40VP max (and 20VP max per Fixed card, if using Fixed)
        - Battle Ready Army: 10VP max (default TRUE)
        - Primary + Secondary combined: 90VP max
        - Total: 100VP max

        Returns the amount actually awarded (excess is lost).
        """
        vp = int(requested_vp or 0)
        if vp <= 0:
            return 0

        source_key = str(source).lower().strip()

        # Apply per-card caps first (per-turn/per-card totals).
        vp_after_card = self._cap_card_vp(card=card, requested_vp=vp, player=player, source=source_key)
        card_capped = vp_after_card < vp
        vp = vp_after_card
        if vp <= 0:
            # Card caps consumed all requested VP (edge case, but still a "capped" scenario).
            if requested_vp and int(requested_vp or 0) > 0 and card_capped:
                self._notify_vp_capped(
                    player=player,
                    source=source_key,
                    requested_vp=int(requested_vp or 0),
                    awarded_vp=0,
                    lost_vp=int(requested_vp or 0),
                    reasons=["per-card cap"],
                    card=card,
                )
            return 0

        total_scored = int(getattr(player, "score", 0) or 0)
        remaining_total = max(0, self.VP_MAX_TOTAL - total_scored)
        if remaining_total <= 0:
            self._notify_vp_capped(
                player=player,
                source=source_key,
                requested_vp=int(requested_vp or 0),
                awarded_vp=0,
                lost_vp=int(requested_vp or 0),
                reasons=["total cap (100VP)"],
                card=card,
            )
            return 0

        primary_scored = int(getattr(player, "vp_primary", 0) or 0)
        secondary_scored = int(getattr(player, "vp_secondary", 0) or 0)
        battle_ready_scored = int(getattr(player, "vp_battle_ready", 0) or 0)

        max_add = remaining_total
        reasons: list[str] = []
        if source_key == "primary":
            remaining_primary = max(0, self.VP_MAX_PRIMARY - primary_scored)
            remaining_combined = max(0, self.VP_MAX_PRIMARY_PLUS_SECONDARY - (primary_scored + secondary_scored))
            max_add = min(max_add, remaining_primary, remaining_combined)
            if remaining_primary <= 0:
                reasons.append("primary cap (50VP)")
            if remaining_combined <= 0:
                reasons.append("primary+secondary cap (90VP)")
        elif source_key == "secondary":
            remaining_secondary = max(0, self.VP_MAX_SECONDARY - secondary_scored)
            remaining_combined = max(0, self.VP_MAX_PRIMARY_PLUS_SECONDARY - (primary_scored + secondary_scored))
            max_add = min(max_add, remaining_secondary, remaining_combined)
            if remaining_secondary <= 0:
                reasons.append("secondary cap (40VP)")
            if remaining_combined <= 0:
                reasons.append("primary+secondary cap (90VP)")
        elif source_key in ("battle_ready", "battleready", "battle-ready"):
            remaining_br = max(0, self.VP_MAX_BATTLE_READY - battle_ready_scored)
            max_add = min(max_add, remaining_br)
            if remaining_br <= 0:
                reasons.append("battle ready cap (10VP)")

        to_add = min(vp, max_add)
        if to_add <= 0:
            # We were blocked by one or more caps.
            lost = int(requested_vp or 0)
            if card_capped:
                reasons = (reasons or []) + ["per-card cap"]
            if remaining_total <= 0 and "total cap (100VP)" not in reasons:
                reasons = (reasons or []) + ["total cap (100VP)"]
            self._notify_vp_capped(
                player=player,
                source=source_key,
                requested_vp=int(requested_vp or 0),
                awarded_vp=0,
                lost_vp=lost,
                reasons=reasons or ["cap reached"],
                card=card,
            )
            return 0

        # Commit to player totals.
        player.add_score(to_add)
        if source_key == "primary":
            player.vp_primary = primary_scored + to_add
        elif source_key == "secondary":
            player.vp_secondary = secondary_scored + to_add
        elif source_key in ("battle_ready", "battleready", "battle-ready"):
            player.vp_battle_ready = battle_ready_scored + to_add

        # Commit to card totals (only increment by the VP actually awarded).
        if card is not None and hasattr(card, "total_scored"):
            card.total_scored = int(getattr(card, "total_scored", 0) or 0) + int(to_add)

        # Notify if the player didn't receive the full VP they would have otherwise gained.
        if int(requested_vp or 0) > int(to_add):
            notify_reasons = list(reasons or [])
            if card_capped:
                notify_reasons.append("per-card cap")
            if remaining_total < vp:
                # total cap was a limiting factor for this award
                notify_reasons.append("total cap (100VP)")
            self._notify_vp_capped(
                player=player,
                source=source_key,
                requested_vp=int(requested_vp or 0),
                awarded_vp=int(to_add),
                lost_vp=int(requested_vp or 0) - int(to_add),
                reasons=notify_reasons or ["cap reached"],
                card=card,
            )

        self._record_vp_award(
            player=player,
            requested_vp=int(requested_vp or 0),
            awarded_vp=int(to_add),
            source=source_key,
            card=card,
            details=details,
            timing=timing,
        )

        details_payload = details
        if isinstance(details, list):
            details_payload = [str(d) for d in details]
        elif details is not None:
            details_payload = str(details)
        card_name = getattr(card, "name", None) if card is not None else None
        self.event_system.publish(
            "vp_awarded",
            player=player,
            source=str(source_key),
            requested_vp=int(requested_vp or 0),
            awarded_vp=int(to_add),
            total_vp=int(getattr(player, "score", 0) or 0),
            vp_primary=int(getattr(player, "vp_primary", 0) or 0),
            vp_secondary=int(getattr(player, "vp_secondary", 0) or 0),
            vp_battle_ready=int(getattr(player, "vp_battle_ready", 0) or 0),
            card_name=card_name,
            timing=str(timing) if timing is not None else None,
            phase=self._current_phase_label(),
            details=details_payload,
        )

        return int(to_add)

    def finalize_battle_scoring(self) -> None:
        """Apply once-per-battle scoring that should only happen at the end of the battle."""
        if getattr(self, "_final_scoring_applied", False):
            return
        if not self.is_game_over():
            return
        for p in list(getattr(self, "players", []) or []):
            if getattr(p, "is_battle_ready", True):
                self.award_vp(
                    p,
                    self.VP_MAX_BATTLE_READY,
                    source="battle_ready",
                    details="Battle Ready bonus",
                    timing="End of battle",
                )
        self._final_scoring_applied = True

    def _queue_dead_reckoning_end_of_turn(self, turn_ending_player) -> None:
        if turn_ending_player is None:
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        if turn <= 0:
            return
        turn_owner_id = str(getattr(turn_ending_player, "id", "") or "")
        if not turn_owner_id:
            return

        pending_units: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "dead_reckoning":
                    continue
                if str(ctx.get("turn_owner", "") or "") != turn_owner_id:
                    continue
                if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                    continue
                unit_id = str(ctx.get("unit_id", "") or ctx.get("source_unit_id", "") or "")
                if unit_id:
                    pending_units.add(unit_id)

        def _unit_sort_key(unit_obj):
            try:
                return str(get_entity_id(unit_obj))
            except Exception:
                return str(getattr(unit_obj, "name", "") or "")

        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            army = player.get_army()
            if army is None:
                continue
            pe = getattr(army, "prioritised_efficiency", None)
            if pe is None:
                continue
            spent_this_turn = bool(
                getattr(pe, "spent_yield_points_in_turn", lambda **_kwargs: False)(
                    game=self,
                    turn=int(turn or 0),
                    turn_owner_id=turn_owner_id,
                )
            )
            if spent_this_turn:
                continue

            seen_units: set[str] = set()
            for unit in sorted(list(getattr(army, "units", []) or []), key=_unit_sort_key):
                if unit is None:
                    continue
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None:
                    continue
                unit_id = str(get_entity_id(root) or "")
                if not unit_id or unit_id in seen_units:
                    continue
                seen_units.add(unit_id)
                if unit_id in pending_units:
                    continue
                if not bool(getattr(root, "is_alive", lambda: False)()):
                    continue
                if not bool(getattr(root, "deployed", True)):
                    continue
                try:
                    if root.is_in_reserves() or root.is_embarked:
                        continue
                except Exception:
                    pass
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict) or not sr.get("enhancement_dead_reckoning"):
                    continue
                bearer = getattr(root, "_get_enhancement_bearer_model", lambda: None)()
                if bearer is None:
                    continue
                try:
                    if (
                        str(sr.get("dead_reckoning_resolved_turn_owner", "") or "") == turn_owner_id
                        and int(sr.get("dead_reckoning_resolved_turn", 0) or 0) == int(turn or 0)
                    ):
                        continue
                except Exception:
                    pass
                self._queue_optional_ability_confirmation(
                    player=player,
                    ability_key="dead_reckoning",
                    ability_name="Dead Reckoning",
                    message="Dead Reckoning: gain 1 YP?",
                    context={
                        "ability_name": "Dead Reckoning",
                        "phase": "End of turn",
                        "unit_id": unit_id,
                        "source_unit_id": unit_id,
                        "turn_owner": turn_owner_id,
                        "turn": int(turn or 0),
                    },
                    payload={
                        "unit_id": unit_id,
                        "source_unit_id": unit_id,
                    },
                    instance_key=f"{unit_id}:{turn}:{turn_owner_id}:dead_reckoning",
                )

    def end_of_turn_scoring(self) -> None:
        """Apply end-of-turn scoring for primaries and secondaries, manage discard rules and CP gain."""
        turn_ending_player = self.get_current_player()

        # Corrupt Realspace: check at the end of any turn before scoring.
        self._evaluate_corrupt_realspace_turn_boundary(timing="end", player=turn_ending_player)

        # Track destroyed units for this turn should already be collected elsewhere; ensure attribute exists
        if not hasattr(self, 'destroyed_units_this_turn'):
            self.destroyed_units_this_turn = []
        if not hasattr(self, 'completed_actions_this_turn'):
            self.completed_actions_this_turn = []

        # Complete mission Actions that trigger at this end of turn FIRST (so scoring can see completions).
        self._complete_actions_for_turn_end(turn_ending_player)

        # Primary: special cases that score at end of turn (e.g., Terraform 1VP per terraformed objective)
        if hasattr(turn_ending_player, 'primary_mission') and isinstance(turn_ending_player.primary_mission, PrimaryMissionCard):
            vp = turn_ending_player.primary_mission.score_at_end_of_turn(self, turn_ending_player)
            if vp:
                added = self.award_vp(
                    turn_ending_player,
                    vp,
                    source="primary",
                    card=turn_ending_player.primary_mission,
                    timing="End of turn",
                )
                if added:
                    logger.info(f"INFO: {turn_ending_player.name} scored {added} VP (end of turn) from Primary: "
                        f"{turn_ending_player.primary_mission.name}")

        # Primary: end-of-opponent's-turn scoring (only for primaries that explicitly do so, e.g. Burden of Trust).
        for p in list(getattr(self, "players", []) or []):
            if p is turn_ending_player:
                continue
            prim = getattr(p, "primary_mission", None)
            fn = getattr(prim, "score_at_end_of_opponents_turn", None)
            if callable(fn):
                vp = int(fn(self, p, turn_ending_player) or 0)
                if vp:
                    added = self.award_vp(
                        p,
                        vp,
                        source="primary",
                        card=prim,
                        timing="End of opponent turn",
                    )
                    if added:
                        logger.info(f"INFO: {p.name} scored {added} VP (opponent turn end) from Primary: "
                            f"{getattr(prim, 'name', 'Primary')}")

        # Secondary: evaluate active cards for BOTH players based on the card's scoring window.
        from ..mission_cards import SecondaryScoringWindow

        def _should_score(card: SecondaryMissionCard, scoring_player: Player, ending_player: Player) -> bool:
            score_window_fn = getattr(card, "score_window", None)
            window = (
                score_window_fn()
                if callable(score_window_fn)
                else getattr(card, "scoring_window", SecondaryScoringWindow.END_OF_YOUR_TURN)
            )
            if scoring_player is ending_player:
                return window in (
                    SecondaryScoringWindow.END_OF_YOUR_TURN,
                    SecondaryScoringWindow.END_OF_EITHER_PLAYER_TURN,
                )
            return window in (SecondaryScoringWindow.END_OF_EITHER_PLAYER_TURN, SecondaryScoringWindow.END_OF_OPPONENT_TURN)

        # Tactical vs Fixed: in Fixed mode, scored cards are NOT discarded on scoring.
        is_fixed = self._is_fixed_secondaries()

        for scoring_player in list(self.players):
            achieved: list[SecondaryMissionCard] = []
            total_secondary_vp = 0
            for card in list(getattr(scoring_player, 'active_secondaries', [])):
                if not _should_score(card, scoring_player, turn_ending_player):
                    continue
                result = card.score_at_end_of_turn(self, scoring_player)
                if not result:
                    continue
                if result.vp:
                    timing = "End of your turn" if scoring_player is turn_ending_player else "End of opponent turn"
                    added = self.award_vp(
                        scoring_player,
                        result.vp,
                        source="secondary",
                        card=card,
                        details=getattr(result, "details", None),
                        timing=timing,
                    )
                    if added:
                        total_secondary_vp += added
                        logger.info(f"INFO: {scoring_player.name} scored {added} VP from Secondary: {card.name}")
                if getattr(result, 'achieved', False):
                    achieved.append(card)

            # a) Tactical: If you scored 1+ VP from a Secondary, discard that card (achieved).
            if (not is_fixed) and total_secondary_vp > 0:
                scoring_player.discard_achieved_secondaries(achieved)

        # Needgaârd Oathband enhancement: optional YP gain if no YP were spent this turn.
        self._queue_dead_reckoning_end_of_turn(turn_ending_player)

        # End-of-turn cleanup for temporary stratagem effects.
        army = getattr(turn_ending_player, "army", None)
        if army is not None:
            for unit in list(getattr(army, "units", []) or []):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if sr.pop("apoplectic_frenzy_active", None) is not None:
                    sr.pop("apoplectic_frenzy_turn", None)
                    unit.special_rules = sr
                if sr.pop("red_wrath_mode", None) is not None:
                    sr.pop("red_wrath_turn_owner", None)
                    sr.pop("red_wrath_turn", None)
                    sr.pop("red_wrath_source", None)
                    unit.special_rules = sr
                if sr.get("selected_to_shoot_charge_reroll_target_ids"):
                    owner = str(sr.get("selected_to_shoot_charge_reroll_turn_owner", "") or "")
                    current_owner = ""
                    try:
                        current_owner = get_entity_id(turn_ending_player)
                    except Exception:
                        current_owner = str(getattr(turn_ending_player, "id", "") or "")
                    if (not owner) or (current_owner and owner == current_owner):
                        for key in (
                            "selected_to_shoot_charge_reroll_target_ids",
                            "selected_to_shoot_charge_reroll_turn_owner",
                            "selected_to_shoot_charge_reroll_turn",
                            "selected_to_shoot_charge_reroll_source",
                        ):
                            sr.pop(key, None)
                        unit.special_rules = sr
                if str(sr.get("post_shoot_ap_bonus_selected_scope", "") or "").strip().lower() == "turn":
                    owner = str(sr.get("post_shoot_ap_bonus_selected_owner", "") or "")
                    current_owner = ""
                    try:
                        current_owner = get_entity_id(turn_ending_player)
                    except Exception:
                        current_owner = str(getattr(turn_ending_player, "id", "") or "")
                    if (not owner) or (current_owner and owner == current_owner):
                        selected_turn = int(sr.get("post_shoot_ap_bonus_selected_turn", 0) or 0)
                        current_turn = int(getattr(self, "turn", 0) or 0)
                        if (not selected_turn) or (current_turn and selected_turn == current_turn):
                            for key in (
                                "post_shoot_ap_bonus_selected_owner",
                                "post_shoot_ap_bonus_selected_turn",
                                "post_shoot_ap_bonus_selected_scope",
                                "post_shoot_ap_bonus_selected_phase",
                            ):
                                sr.pop(key, None)
                            unit.special_rules = sr

        # Imperial Knights: Code Chivalric deed completion at end of turn.
        for p in list(getattr(self, "players", []) or []):
            army = getattr(p, "get_army", lambda: None)()
            mgr = getattr(army, "code_chivalric", None) if army is not None else None
            if mgr is None:
                continue
            mgr.check_end_of_turn(game=self, turn_ending_player=turn_ending_player)

        # b) Allow voluntary discard for current player to gain 1CP (UI/controller should call explicitly). Here we do nothing automatically.

        # c) If deck runs out, player cannot generate additional secondaries (handled by deck empty check during draws)

        # End of opponent's turn: optional abilities to move units into Strategic Reserves.
        self._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player)
        # Chaos Daemons: The Realm of Chaos (end of opponent's turn stratagem).
        for p in list(getattr(self, "players", []) or []):
            if p is None:
                continue
            mgr = getattr(p, "stratagems", None)
            if mgr is not None and hasattr(mgr, "queue_realm_of_chaos_end_of_turn"):
                mgr.queue_realm_of_chaos_end_of_turn(turn_ending_player=turn_ending_player)

        # Clear per-turn event lists
        self.destroyed_units_this_turn = []
        self.completed_actions_this_turn = []
        self.models_destroyed_this_turn = []

    def end_of_battle_round_scoring(self) -> None:
        """Apply end-of-battle-round scoring for primaries that need it (e.g., Purge the Foe)."""
        # Build destroyed counts if not present
        if not hasattr(self, 'destroyed_units_this_battle_round_by_player'):
            self.destroyed_units_this_battle_round_by_player = {}
        for player in self.players:
            # Primary mission score
            if hasattr(player, 'primary_mission') and isinstance(player.primary_mission, PrimaryMissionCard):
                vp = int(player.primary_mission.score_at_end_of_battle_round(self, player) or 0)
                if vp:
                    added = self.award_vp(
                        player,
                        vp,
                        source="primary",
                        card=player.primary_mission,
                        timing="End of battle round",
                    )
                    if added:
                        logger.info(f"INFO: {player.name} scored {added} VP (end of battle round) from Primary: "
                            f"{player.primary_mission.name}")

        # Imperial Knights: Code Chivalric deed completion at end of battle round.
        for p in list(getattr(self, "players", []) or []):
            army = getattr(p, "get_army", lambda: None)()
            mgr = getattr(army, "code_chivalric", None) if army is not None else None
            if mgr is None:
                continue
            mgr.check_end_of_battle_round(game=self, battle_round=self.turn)

        # Emperor's Children: Pledges to the Dark Prince resolution (Coterie of the Conceited).
        for p in list(getattr(self, "players", []) or []):
            army = getattr(p, "get_army", lambda: None)()
            mgr = getattr(army, "emperors_children", None) if army is not None else None
            if mgr is None or not getattr(mgr, "is_coterie_of_conceited", lambda: False)():
                continue
            result = mgr.resolve_pledge_end_of_round(self)
            if result.get("resolved") and getattr(self, "event_system", None) is not None:
                self.event_system.publish(
                    "emperors_children_pact_points_updated",
                    player=p,
                    game=self,
                    manager=mgr,
                    result=dict(result),
                )

        # Chapter Approved: any units still in reserves at the end of battle round 3 are destroyed.
        # `self.turn` is the current battle round number when this hook is invoked.
        if int(getattr(self, "turn", 0) or 0) == 3:
            for p in list(getattr(self, "players", []) or []):
                army = getattr(p, "get_army", lambda: None)()
                if army is None:
                    continue
                to_remove = []
                for u in list(getattr(army, "units", []) or []):
                    if getattr(u, "is_in_reserves", lambda: False)() and bool(getattr(u, "_started_in_reserves", False)):
                        to_remove.append(u)
                for u in to_remove:
                    logger.warning(
                        "%s destroyed - still in reserves at end of battle round 3",
                        getattr(u, "name", "Unit"),
                    )
                    if u in army.units:
                        army.units.remove(u)

    def record_unit_destroyed(self, unit: 'Unit') -> None:
        """Record a unit destroyed event and incrementally score relevant secondaries."""
        if not hasattr(self, "destroyed_units_this_turn"):
            self.destroyed_units_this_turn = []
        self.destroyed_units_this_turn.append(unit)

        # Tally for Purge the Foe end-of-battle-round scoring
        if not hasattr(self, "destroyed_units_this_battle_round_by_player"):
            self.destroyed_units_this_battle_round_by_player = {}
        owner_player = unit.get_parent_army().player if unit.get_parent_army() else None
        if owner_player is not None:
            self.destroyed_units_this_battle_round_by_player[owner_player] = (
                self.destroyed_units_this_battle_round_by_player.get(owner_player, 0) + 1
            )

        # Incremental scoring for active secondaries that score on unit destruction
        for player in self.players:
            if player is owner_player:
                continue
            for card in getattr(player, 'active_secondaries', []) or []:
                fn = getattr(card, "on_unit_destroyed", None)
                if not callable(fn):
                    continue
                points = int(fn(self, player, unit) or 0)
                if points:
                    unit_name = getattr(unit, "name", "Unit")
                    if getattr(unit, "is_character", False):
                        detail = f"Destroyed Character unit: {unit_name}"
                    else:
                        detail = f"Destroyed unit: {unit_name}"
                    added = self.award_vp(
                        player,
                        points,
                        source="secondary",
                        card=card,
                        details=detail,
                        timing="Unit destroyed",
                    )
                    if added:
                        logger.info(f"INFO: {player.name} scored {added} VP from Secondary: "
                            f"{getattr(card, 'name', 'Unknown')} (unit destroyed)")

    def record_model_destroyed(self, model: 'Model') -> None:
        """Record a model destroyed event and incrementally score relevant secondaries that key off models."""
        if not hasattr(self, "models_destroyed_this_turn"):
            self.models_destroyed_this_turn = []
        self.models_destroyed_this_turn.append(model)

        # Incremental scoring for active secondaries that score on model destruction (e.g., Fixed Assassination).
        for player in self.players:
            for card in getattr(player, "active_secondaries", []) or []:
                fn = getattr(card, "on_model_destroyed", None)
                if not callable(fn):
                    continue
                points = int(fn(self, player, model) or 0)
                if points:
                    model_name = getattr(model, "name", "Model")
                    unit = getattr(model, "parent_unit", None)
                    if getattr(model, "is_character", False):
                        detail = f"Destroyed Character: {model_name}"
                    else:
                        detail = f"Destroyed model: {model_name}"
                    if unit is not None and getattr(unit, "name", None) and unit.name != model_name:
                        detail = f"{detail} (Unit: {unit.name})"
                    added = self.award_vp(
                        player,
                        points,
                        source="secondary",
                        card=card,
                        details=detail,
                        timing="Model destroyed",
                    )
                    if added:
                        logger.info(f"INFO: {player.name} scored {added} VP from Secondary: "
                            f"{getattr(card, 'name', 'Unknown')} (model destroyed)")

    def _is_unit_eligible_to_start_action(self, unit: 'Unit') -> Dict[str, Any]:
        # Not if Aircraft
        if getattr(unit, 'is_aircraft', False):
            return {"valid": False, "reason": "Aircraft cannot perform Actions"}
        # Not if Battle-shocked
        if unit.is_battle_shocked():
            return {"valid": False, "reason": "Battle-shocked units cannot perform Actions"}
        # Not if already performing an Action / locked
        if bool(getattr(unit.round_state, "action_locked_until_turn_end", False)) or getattr(unit.round_state, "performing_action_name", None):
            return {"valid": False, "reason": "Unit is already performing an Action this turn"}
        # OC 0 cannot perform
        if getattr(unit, 'objective_control', 0) == 0:
            return {"valid": False, "reason": "Units with OC 0 cannot perform Actions"}
        # Not if within engagement range of any enemy (unless TITANIC CHARACTER)
        if any(self.map.is_within_engagement_range(unit, enemy)
               for enemy in self.map.get_enemy_units(unit) if enemy.is_alive()):
            if not (getattr(unit, 'is_titanic', False) and getattr(unit, 'is_character', False)):
                return {"valid": False, "reason": "Units in Engagement Range cannot perform Actions"}
        # Not if advanced or fell back, unless a rule allows it.
        allow_advance_action = False
        allow_fall_back_action = False
        army = unit.get_parent_army()
        mgr = getattr(army, "templar_vows", None) if army is not None else None
        if mgr is not None and mgr.allow_action_after_advance(unit, self):
            allow_advance_action = True
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        if sm_mgr is not None and getattr(sm_mgr, "interlocking_tactics_allow_action_after_advance_or_fall_back", None):
            if sm_mgr.interlocking_tactics_allow_action_after_advance_or_fall_back(unit, self):
                allow_advance_action = True
                allow_fall_back_action = True
        if sm_mgr is not None and getattr(sm_mgr, "seekers_companions_allow_action_after_advance", None):
            if sm_mgr.seekers_companions_allow_action_after_advance(unit, self):
                allow_advance_action = True
        if unit.round_state.fell_back_this_round and not allow_fall_back_action:
            return {"valid": False, "reason": "Units that Fell Back cannot perform Actions"}
        if unit.round_state.advanced_this_round and not allow_advance_action:
            return {"valid": False, "reason": "Units that Advanced cannot perform Actions"}
        # Not if not eligible to shoot this phase (includes units that have already been selected to shoot)
        if unit.round_state.shot_this_round:
            return {"valid": False, "reason": "Units already selected to shoot cannot start an Action this phase"}
        return {"valid": True, "reason": "Eligible"}

    def _unit_is_in_player_deployment(self, player: Player, unit: 'Unit') -> bool:
        zones = self.deployment_zones.get(player.id, {})
        zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
        if not zone:
            return False
        # Use first alive model position
        for model in unit.models:
            if model.is_alive:
                pos = model.get_location()
                if pos and hasattr(zone, 'contains_point') and zone.contains_point(pos[0], pos[1]):
                    return True
        return False

    def _objective_in_player_deployment(self, player: Player, objective_point) -> bool:
        zones = self.deployment_zones.get(player.id, {})
        zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
        if not zone:
            return False
        return hasattr(zone, 'contains_point') and zone.contains_point(objective_point.x, objective_point.y)

    def _unit_within_any_terrain_feature(self, unit: 'Unit') -> bool:
        for model in unit.models:
            if not model.is_alive:
                continue
            base_geom = model.model_base.get_base_shape()
            for t in self.map.terrain_features:
                if base_geom.intersects(t.footprint):
                    return True
        return False

    def _unit_within_range_of_objective(self, unit: 'Unit') -> Optional[Objective]:
        # Return the Objective (from map.objectives) whose point area intersects the unit
        from shapely.geometry import Point as _ShPoint
        for obj in getattr(self.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc:
                continue
            area = _ShPoint(loc.x, loc.y).buffer(loc.control_radius)
            for model in unit.models:
                if not model.is_alive:
                    continue
                base = model.model_base
                if hasattr(base, 'get_base_shape') and hasattr(area, 'intersects'):
                    base_geom = base.get_base_shape()
                    if base_geom.intersects(area):
                        return obj
                    continue
                mpos = model.get_location()
                if mpos:
                    dx = mpos[0] - loc.x
                    dy = mpos[1] - loc.y
                    radius = getattr(base, 'get_radius', lambda: 1.0)()
                    if (dx * dx + dy * dy) ** 0.5 <= (loc.control_radius + radius):
                        return obj
        return None

    def _clear_expired_guards_for_player(self, player: Player) -> None:
        """Clear any 'guarding' assignments for `player` at the start of their turn."""
        army = getattr(player, "army", None)
        if army is None:
            return
        for u in list(getattr(army, "units", []) or []):
            if getattr(u, "guarding_objective", None) is not None:
                u.guarding_objective = None

    def _assign_burden_of_trust_guards(self, player: Player) -> None:
        """
        End of Command phase (Burden of Trust): for each objective marker the player controls,
        select one eligible unit within range to guard it until the start of the player's next turn.

        Current implementation is deterministic/autopick (UI hooks can override later).
        """
        if getattr(self, "get_battle_round", lambda: 0)() < 2:
            return

        prim = getattr(player, "primary_mission", None)
        from ..mission_cards import BurdenOfTrustPrimary
        if not isinstance(prim, BurdenOfTrustPrimary):
            return

        # Build list of objectives currently controlled by player.
        controlled = []
        for obj in getattr(self.map, "objectives", []):
            loc = getattr(obj, "location", None)
            if not loc or getattr(loc, "removed", False):
                continue
            if hasattr(loc, "update_control"):
                loc.update_control(self)
            if getattr(loc, "controlling_player", None) is player:
                controlled.append(obj)

        # Candidate units: non-aircraft, alive, deployed.
        candidates = []
        for u in getattr(player.army, "units", []) or []:
            if not u.is_alive() or not getattr(u, "deployed", False):
                continue
            if getattr(u, "is_aircraft", False):
                continue
            candidates.append(u)

        # Assign at most one objective per unit.
        used_units = set()
        for obj in controlled:
            # Find first eligible unit within range of this objective.
            chosen = None
            for u in candidates:
                if get_entity_id(u) in used_units:
                    continue
                if self._unit_within_range_of_objective(u) is obj:
                    chosen = u
                    break
            if chosen is None:
                continue
            chosen.guarding_objective = obj
            used_units.add(get_entity_id(chosen))

    def _apply_primary_mission_setup_rules(self) -> None:
        """
        Apply mission-card setup rules that modify objectives at battle start.
        This is invoked after mission objectives are initially placed.
        """
        if not getattr(self, "players", None):
            return
        prim = getattr(self.players[0], "primary_mission", None)
        if prim is None:
            return

        # Helper: objective is in No Man's Land if it is not within any player's deployment zone.
        def _is_nml(loc) -> bool:
            for p in self.players:
                zones = self.deployment_zones.get(p.id, {})
                zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
                if zone and hasattr(zone, "contains_point") and zone.contains_point(loc.x, loc.y):
                    return False
            return True

        # Unexploded Ordnance: NML objectives become Hazard objectives.
        from ..mission_cards import UnexplodedOrdnancePrimary
        if isinstance(prim, UnexplodedOrdnancePrimary):
            for obj in getattr(self.map, "objectives", []) or []:
                loc = getattr(obj, "location", None)
                if not loc or getattr(loc, "removed", False):
                    continue
                if _is_nml(loc):
                    loc.is_hazard = True

        # Supply Drop: initialize Alpha/Omega selection if primary supports it.
        fn = getattr(prim, "initialize_alpha_omega", None)
        if callable(fn):
            fn(self)

    def can_start_terraform(self, unit: 'Unit') -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "Terraform starts in your Shooting phase"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        # Must be within range of an objective not within your deployment zone
        obj = self._unit_within_range_of_objective(unit)
        if not obj:
            return {"valid": False, "reason": "Unit not within range of an objective"}
        # Objective must not be within your deployment zone
        if self._objective_in_player_deployment(unit.get_parent_army().player, obj.location):
            return {"valid": False, "reason": "Objective is within your deployment zone"}
        return {"valid": True, "reason": "Eligible", "objective": obj}

    def can_start_sabotage(self, unit: 'Unit') -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "Sabotage starts in your Shooting phase"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        # Must be within a terrain feature and not within your deployment zone
        if not self._unit_within_any_terrain_feature(unit):
            return {"valid": False, "reason": "Unit must be within a terrain feature"}
        if self._unit_is_in_player_deployment(unit.get_parent_army().player, unit):
            return {"valid": False, "reason": "Unit is within your deployment zone"}
        return {"valid": True, "reason": "Eligible"}

    def can_start_cleanse(self, unit: 'Unit') -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "Cleanse starts in your Shooting phase"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        # Must be within range of an objective not within your deployment zone
        obj = self._unit_within_range_of_objective(unit)
        if not obj:
            return {"valid": False, "reason": "Unit not within range of an objective"}
        if self._objective_in_player_deployment(unit.get_parent_army().player, obj.location):
            return {"valid": False, "reason": "Objective is within your deployment zone"}
        return {"valid": True, "reason": "Eligible", "objective": obj}

    def can_start_establish_locus(self, unit: 'Unit') -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "Establish Locus starts in your Shooting phase"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        return {"valid": True, "reason": "Eligible"}

    def can_start_the_ritual(self, unit: 'Unit', *, new_objective_xy: Tuple[float, float]) -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "The Ritual starts in your Shooting phase"}
        # Must have The Ritual as the primary mission
        from ..mission_cards import TheRitualPrimary
        if not isinstance(getattr(unit.get_parent_army().player, "primary_mission", None), TheRitualPrimary):
            return {"valid": False, "reason": "Primary mission is not The Ritual"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        x, y = float(new_objective_xy[0]), float(new_objective_xy[1])

        # Must be within No Man's Land (not in either deployment zone)
        for p in self.players:
            zones = self.deployment_zones.get(p.id, {})
            zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
            if zone and hasattr(zone, "contains_point") and zone.contains_point(x, y):
                return {"valid": False, "reason": "Objective marker must be wholly within No Man's Land"}

        # Must be within 1" of the unit
        from ...utility.aura_utils import horizontal_distance_point_to_model_base_2d
        in_1 = False
        for m in getattr(unit, "models", []) or []:
            if not getattr(m, "is_alive", True):
                continue
            if horizontal_distance_point_to_model_base_2d(m, x, y) <= 1.0 + 1e-6:
                in_1 = True
                break
        if not in_1:
            return {"valid": False, "reason": "Objective marker must be within 1\" of the unit"}

        # Exactly 12" from one other NML objective, and not within 6" of any other objective.
        nml_objs = []
        for obj in getattr(self.map, "objectives", []) or []:
            loc = getattr(obj, "location", None)
            if not loc or getattr(loc, "removed", False):
                continue
            # Only consider NML markers
            in_any_dz = False
            for p in self.players:
                zones = self.deployment_zones.get(p.id, {})
                zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
                if zone and hasattr(zone, "contains_point") and zone.contains_point(loc.x, loc.y):
                    in_any_dz = True
                    break
            if not in_any_dz:
                nml_objs.append(obj)

        def _dist(a, b):
            dx = float(a[0]) - float(b[0])
            dy = float(a[1]) - float(b[1])
            return (dx * dx + dy * dy) ** 0.5

        dists = [(_dist((x, y), (float(o.location.x), float(o.location.y))), o) for o in nml_objs if getattr(o, "location", None)]
        exact_12 = [o for (d, o) in dists if abs(d - 12.0) <= 0.25]
        if len(exact_12) != 1:
            return {"valid": False, "reason": "Objective marker must be set up exactly 12\" from one other No Man's Land objective marker"}
        for (d, o) in dists:
            if o is exact_12[0]:
                continue
            if d < 6.0 - 1e-6:
                return {"valid": False, "reason": "Objective marker must not be within 6\" of any other objective marker"}

        return {"valid": True, "reason": "Eligible", "x": x, "y": y}

    def can_start_move_hazard(self, unit: 'Unit', *, hazard_objective: Objective, new_xy: Tuple[float, float]) -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "Move Hazard starts in your Shooting phase"}
        # Must have Unexploded Ordnance as the primary mission
        from ..mission_cards import UnexplodedOrdnancePrimary
        if not isinstance(getattr(unit.get_parent_army().player, "primary_mission", None), UnexplodedOrdnancePrimary):
            return {"valid": False, "reason": "Primary mission is not Unexploded Ordnance"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        actor = unit.get_parent_army().player
        if hazard_objective is None or getattr(hazard_objective, "location", None) is None:
            return {"valid": False, "reason": "Invalid hazard objective marker"}
        loc = hazard_objective.location
        if not bool(getattr(loc, "is_hazard", False)):
            return {"valid": False, "reason": "Objective marker is not a Hazard objective marker"}
        if hasattr(loc, "update_control"):
            loc.update_control(self)
        if getattr(loc, "controlling_player", None) is not actor:
            return {"valid": False, "reason": "You do not control that Hazard objective marker"}
        # Must be within range of this hazard marker
        if self._unit_within_range_of_objective(unit) is not hazard_objective:
            return {"valid": False, "reason": "Unit must be within range of that Hazard objective marker"}
        nx, ny = float(new_xy[0]), float(new_xy[1])
        dx = nx - float(loc.x)
        dy = ny - float(loc.y)
        if (dx * dx + dy * dy) ** 0.5 > 6.0 + 1e-6:
            return {"valid": False, "reason": "Hazard objective marker can only be moved up to 6\""}
        return {"valid": True, "reason": "Eligible", "hazard_objective": hazard_objective, "new_x": nx, "new_y": ny}

    def start_terraform_action(self, unit: 'Unit') -> Dict[str, Any]:
        check = self.can_start_terraform(unit)
        if not check["valid"]:
            return check
        objective = check.get("objective")
        # Mark unit round state and add in-progress
        unit.round_state.performing_action_name = 'TERRAFORM'
        unit.round_state.action_locked_until_turn_end = True
        # Consumes the unit's shooting action for the turn
        unit.round_state.shot_this_round = True
        # Complete at end of this player's turn
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'TERRAFORM',
            'started_turn': self.turn,
            'completes_on_player_index': self.current_player_index,
            'metadata': {'objective': objective}
        })
        return {"valid": True, "reason": "Terraform started"}

    def start_sabotage_action(self, unit: 'Unit') -> Dict[str, Any]:
        check = self.can_start_sabotage(unit)
        if not check["valid"]:
            return check
        unit.round_state.performing_action_name = 'SABOTAGE'
        unit.round_state.action_locked_until_turn_end = True
        # Consumes the unit's shooting action for the turn
        unit.round_state.shot_this_round = True
        # Completes at end of opponent's next turn
        opponent_index = (self.current_player_index + 1) % len(self.players)
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'SABOTAGE',
            'started_turn': self.turn,
            'completes_on_player_index': opponent_index,
            'metadata': {}
        })
        return {"valid": True, "reason": "Sabotage started"}

    def start_cleanse_action(self, unit: 'Unit') -> Dict[str, Any]:
        check = self.can_start_cleanse(unit)
        if not check["valid"]:
            return check
        objective = check.get("objective")
        unit.round_state.performing_action_name = 'CLEANSE'
        unit.round_state.action_locked_until_turn_end = True
        unit.round_state.shot_this_round = True
        # Completes at end of this player's turn
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'CLEANSE',
            'started_turn': self.turn,
            'completes_on_player_index': self.current_player_index,
            'metadata': {'objective': objective}
        })
        return {"valid": True, "reason": "Cleanse started"}

    def start_establish_locus_action(self, unit: 'Unit') -> Dict[str, Any]:
        check = self.can_start_establish_locus(unit)
        if not check["valid"]:
            return check
        unit.round_state.performing_action_name = 'ESTABLISH_LOCUS'
        unit.round_state.action_locked_until_turn_end = True
        unit.round_state.shot_this_round = True
        # Completes at end of this player's turn
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'ESTABLISH_LOCUS',
            'started_turn': self.turn,
            'completes_on_player_index': self.current_player_index,
            'metadata': {}
        })
        return {"valid": True, "reason": "Establish Locus started"}

    def start_the_ritual_action(self, unit: 'Unit', *, new_objective_xy: Tuple[float, float]) -> Dict[str, Any]:
        check = self.can_start_the_ritual(unit, new_objective_xy=new_objective_xy)
        if not check["valid"]:
            return check
        unit.round_state.performing_action_name = 'THE_RITUAL'
        unit.round_state.action_locked_until_turn_end = True
        unit.round_state.shot_this_round = True
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'THE_RITUAL',
            'started_turn': self.turn,
            'completes_on_player_index': self.current_player_index,
            'metadata': {'x': check["x"], 'y': check["y"]}
        })
        return {"valid": True, "reason": "The Ritual started"}

    def start_move_hazard_action(self, unit: 'Unit', *, hazard_objective: Objective, new_xy: Tuple[float, float]) -> Dict[str, Any]:
        check = self.can_start_move_hazard(unit, hazard_objective=hazard_objective, new_xy=new_xy)
        if not check["valid"]:
            return check
        unit.round_state.performing_action_name = 'MOVE_HAZARD'
        unit.round_state.action_locked_until_turn_end = True
        unit.round_state.shot_this_round = True
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'MOVE_HAZARD',
            'started_turn': self.turn,
            'completes_on_player_index': self.current_player_index,
            'metadata': {'hazard_objective': check["hazard_objective"], 'new_x': check["new_x"], 'new_y': check["new_y"]}
        })
        return {"valid": True, "reason": "Move Hazard started"}

    # Scorched Earth: Burn Objective (BR2+)

    def can_start_burn_objective(self, unit: 'Unit') -> Dict[str, Any]:
        # Only available if player's primary is Scorched Earth
        prim = getattr(unit.get_parent_army().player, 'primary_mission', None)
        from ..mission_cards import ScorchedEarthPrimary
        if not isinstance(prim, ScorchedEarthPrimary):
            return {"valid": False, "reason": "Primary mission is not Scorched Earth"}
        if self.get_battle_round() < 2:
            return {"valid": False, "reason": "Burn Objective starts from the second battle round"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        obj = self._unit_within_range_of_objective(unit)
        if not obj:
            return {"valid": False, "reason": "Unit not within range of an objective"}
        # Not within your deployment zone
        if self._objective_in_player_deployment(unit.get_parent_army().player, obj.location):
            return {"valid": False, "reason": "Objective is within your deployment zone"}
        return {"valid": True, "reason": "Eligible", "objective": obj}

    def start_burn_objective_action(self, unit: 'Unit') -> Dict[str, Any]:
        check = self.can_start_burn_objective(unit)
        if not check["valid"]:
            return check
        objective = check.get("objective")
        unit.round_state.performing_action_name = 'BURN_OBJECTIVE'
        unit.round_state.action_locked_until_turn_end = True
        # Consumes the unit's shooting action for the turn
        unit.round_state.shot_this_round = True
        opponent_index = (self.current_player_index + 1) % len(self.players)
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'BURN_OBJECTIVE',
            'started_turn': self.turn,
            'completes_on_player_index': opponent_index,
            'metadata': {'objective': objective}
        })
        return {"valid": True, "reason": "Burn Objective started"}

    def _complete_actions_for_turn_end(self, turn_ending_player: Player) -> None:
        # Evaluate any in-progress actions that complete at this player's turn end
        if not hasattr(self, "completed_actions_this_turn"):
            self.completed_actions_this_turn = []
        remaining = []
        for entry in self.in_progress_actions:
            completes_on = entry.get('completes_on_player_index')
            if completes_on != self.current_player_index:
                remaining.append(entry)
                continue
            unit = entry.get('unit')
            action_name = entry.get('action_name')
            actor = entry.get('player')
            # Validate unit still on battlefield
            if not unit or not unit.is_alive() or not unit.deployed:
                # Action fails silently
                if unit:
                    unit.round_state.performing_action_name = None
                    unit.round_state.action_locked_until_turn_end = False
                continue

            if action_name == 'TERRAFORM':
                # Must still be within range of same objective and control it
                objective = entry['metadata'].get('objective')
                loc = getattr(objective, 'location', None)
                if loc and hasattr(loc, 'update_control'):
                    loc.update_control(self)
                # Check in-range
                in_range = False
                if objective:
                    in_range = (self._unit_within_range_of_objective(unit) == objective)
                controls = loc and getattr(loc, 'controlling_player', None) is actor
                if in_range and controls:
                    # Mark terraformed and record completed action
                    if loc:
                        loc.terraformed_by = actor
                    self.completed_actions_this_turn.append({
                        'player': actor,
                        'action_name': 'TERRAFORM',
                        'unit_location': unit.get_closest_model_position_to_target((loc.x, loc.y, loc.z)) if loc else None
                    })
                # Clear unit state
                unit.round_state.performing_action_name = None
                unit.round_state.action_locked_until_turn_end = False
            elif action_name == 'SABOTAGE':
                # Completes if the unit is on the battlefield
                self.completed_actions_this_turn.append({
                    'player': actor,
                    'action_name': 'SABOTAGE',
                    'unit_location': unit.get_closest_model_position_to_target(unit.models[0].get_location() if unit.models else (0, 0, 0))
                })
                unit.round_state.performing_action_name = None
                unit.round_state.action_locked_until_turn_end = False
            elif action_name == 'CLEANSE':
                objective = entry['metadata'].get('objective')
                loc = getattr(objective, 'location', None)
                if loc and hasattr(loc, 'update_control'):
                    loc.update_control(self)
                in_range = False
                if objective:
                    in_range = (self._unit_within_range_of_objective(unit) == objective)
                controls = loc and getattr(loc, 'controlling_player', None) is actor
                if in_range and controls:
                    # Mark cleansed and record completed action
                    if loc:
                        setattr(loc, "cleansed_by", actor)
                    self.completed_actions_this_turn.append({
                        'player': actor,
                        'action_name': 'CLEANSE',
                        'objective': objective,
                        'unit_location': unit.get_closest_model_position_to_target((loc.x, loc.y, loc.z)) if loc else None
                    })
                unit.round_state.performing_action_name = None
                unit.round_state.action_locked_until_turn_end = False
            elif action_name == 'ESTABLISH_LOCUS':
                # Completes if unit is within opponent DZ or within 6" of center
                completes = False
                opponents = [p for p in self.players if p is not actor]
                opp = opponents[0] if opponents else None
                zones = self.deployment_zones.get(opp.id, {}) if opp is not None else {}
                zone = zones.get('zone') or zones.get('Attacker Zone') or zones.get('Defender Zone')
                pos = unit.models[0].get_location() if unit.models else (0, 0, 0)
                if zone and hasattr(zone, 'contains_point') and zone.contains_point(pos[0], pos[1]):
                    completes = True
                else:
                    midx = float(self.map.width) / 2.0
                    midy = float(self.map.height) / 2.0
                    dx = float(pos[0]) - midx
                    dy = float(pos[1]) - midy
                    completes = (dx * dx + dy * dy) ** 0.5 <= 6.0 + 1e-6
                if completes:
                    self.completed_actions_this_turn.append({
                        'player': actor,
                        'action_name': 'ESTABLISH_LOCUS',
                        'unit_location': unit.models[0].get_location() if unit.models else (0, 0, 0),
                    })
                unit.round_state.performing_action_name = None
                unit.round_state.action_locked_until_turn_end = False
            elif action_name == 'THE_RITUAL':
                # Place a new objective marker if still valid (best-effort: uses pre-validated coordinates).
                x = entry['metadata'].get('x')
                y = entry['metadata'].get('y')
                from ...battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
                op = ObjectivePoint(x=float(x), y=float(y), z=0.0, control_radius=3.0)
                obj = Objective(
                    name="Ritual Objective",
                    category=ObjectiveCategory.PRIMARY,
                    points=0,
                    description="Objective marker created by The Ritual.",
                    conditions=lambda g: False,
                    location=op,
                )
                self.map.add_objective(obj)
                self.completed_actions_this_turn.append({
                    'player': actor,
                    'action_name': 'THE_RITUAL',
                    'unit_location': unit.models[0].get_location() if unit.models else (0, 0, 0),
                })
                unit.round_state.performing_action_name = None
                unit.round_state.action_locked_until_turn_end = False
            elif action_name == 'MOVE_HAZARD':
                hazard_obj = entry['metadata'].get('hazard_objective')
                nx = entry['metadata'].get('new_x')
                ny = entry['metadata'].get('new_y')
                loc = getattr(hazard_obj, 'location', None)
                if loc and hasattr(loc, 'update_control'):
                    loc.update_control(self)
                # Still within range and controlled
                in_range = (self._unit_within_range_of_objective(unit) == hazard_obj)
                controls = loc and getattr(loc, 'controlling_player', None) is actor
                if in_range and controls and loc and not getattr(loc, 'removed', False):
                    loc.x = float(nx)
                    loc.y = float(ny)
                    self.completed_actions_this_turn.append({
                        'player': actor,
                        'action_name': 'MOVE_HAZARD',
                        'objective': hazard_obj,
                        'unit_location': unit.models[0].get_location() if unit.models else (0, 0, 0),
                    })
                unit.round_state.performing_action_name = None
                unit.round_state.action_locked_until_turn_end = False
            elif action_name == 'BURN_OBJECTIVE':
                objective = entry['metadata'].get('objective')
                loc = getattr(objective, 'location', None)
                if loc and hasattr(loc, 'update_control'):
                    loc.update_control(self)
                in_range = False
                if objective:
                    in_range = (self._unit_within_range_of_objective(unit) == objective)
                controls = loc and getattr(loc, 'controlling_player', None) is actor
                if in_range and controls and not getattr(loc, 'removed', False):
                    # Determine zone of objective for VP
                    opponent = next((p for p in self.players if p is not actor), None)
                    zones = self.deployment_zones.get(opponent.id, {}) if opponent is not None else {}
                    zone = zones.get('zone') or zones.get('Attacker Zone') or zones.get('Defender Zone')
                    in_opponent_dz = bool(zone and hasattr(zone, 'contains_point') and zone.contains_point(loc.x, loc.y))
                    vp = 10 if in_opponent_dz else 5
                    # Remove the objective
                    loc.removed = True
                    logger.info(f"INFO: Scorched Earth burned objective at ({loc.x:.1f}, {loc.y:.1f})")
                    # Immediate scoring per mission rules (Any time when burned)
                    details = [
                        f"Burned objective at ({loc.x:.1f}, {loc.y:.1f})",
                    ]
                    if in_opponent_dz:
                        details.append("Objective in opponent deployment zone")
                    added = self.award_vp(
                        actor,
                        vp,
                        source="primary",
                        card=getattr(actor, "primary_mission", None),
                        details=details,
                        timing="Action: Burn objective",
                    )
                    if added:
                        logger.info(f"INFO: {actor.name} scored {added} VP for burning objective")
                unit.round_state.performing_action_name = None
                unit.round_state.action_locked_until_turn_end = False
            else:
                remaining.append(entry)
        self.in_progress_actions = remaining
