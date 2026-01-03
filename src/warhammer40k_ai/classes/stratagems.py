import time
from typing import Callable, Optional, Dict, Any, List


IMPLEMENTED_STRATAGEM_NAMES = {
    "COMMAND RE-ROLL",
    "COUNTER-OFFENSIVE",
    "EPIC CHALLENGE",
    "FIRE OVERWATCH",
    "OVERWATCH",
    "GO TO GROUND",
    "GRENADE",
    "HEROIC INTERVENTION",
    "INSANE BRAVERY",
    "NEW ORDERS",
    "RAPID INGRESS",
    "SMOKESCREEN",
    "TANK SHOCK",
}

REACTION_ONLY_STRATAGEM_NAMES = {
    "COMMAND RE-ROLL",
    "COUNTER-OFFENSIVE",
    "FIRE OVERWATCH",
    "OVERWATCH",
    "GO TO GROUND",
    "HEROIC INTERVENTION",
    "INSANE BRAVERY",
    "NEW ORDERS",
    "RAPID INGRESS",
    "SMOKESCREEN",
}


def _unit_cannot_be_target_of_stratagem(unit: Any) -> bool:
    """
    Core rule: Battle-shocked units cannot be the target of a Stratagem.

    Also: Units embarked within a Transport are not on the battlefield and cannot be targeted by rules,
    including Stratagems (unless explicitly stated otherwise).

    We treat a unit as battle-shocked if either:
    - it implements `is_battle_shocked()` and returns True, or
    - it has `special_rules['cannot_use_stratagems'] == True` (set by BattleShockEffect)

    This helper is intentionally defensive because some tests use lightweight stubs instead of full Unit objects.
    """
    if unit is None:
        return False

    # Embarked restriction: cannot target embarked units with stratagems (even INSANE BRAVERY).
    try:
        is_embarked = getattr(unit, "is_embarked", None)
        if callable(is_embarked) and bool(is_embarked):
            return True
    except Exception:
        pass
    try:
        if getattr(unit, "embarked_in", None) is not None:
            return True
    except Exception:
        pass
    try:
        is_bs = getattr(unit, "is_battle_shocked", None)
        if callable(is_bs) and bool(is_bs()):
            return True
    except Exception:
        # Fallback to special_rules below.
        pass
    try:
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict) and sr.get("cannot_use_stratagems") is True:
            return True
    except Exception:
        pass
    return False


def _extract_friendly_target_unit_from_kwargs(kwargs: Dict[str, Any]) -> Any:
    """
    Best-effort extraction of the *friendly* unit being targeted by a stratagem.

    Notes:
    - We intentionally do NOT treat `enemy_unit` as a target, since it is typically the trigger context.
    - Multiple keys exist across special-cases (e.g. Overwatch uses `shooter_unit`).
    """
    for key in ("target_unit", "unit", "shooter_unit", "attacker_unit", "defender_unit"):
        u = kwargs.get(key)
        if u is not None:
            return u
    return None


class Stratagem:
    def __init__(
        self,
        *,
        id: str,
        name: str,
        type: str,
        description: str,
        cp_cost: int,
        turn: str,
        phase: str,
        detachment: str,
        faction_id: str,
        effect: Optional[Callable] = None,
        conditions: Optional[Callable] = None,
    ) -> None:
        self.id = id
        self.name = name
        self.type = type
        self.description = description
        self.cp_cost = int(cp_cost) if isinstance(cp_cost, (int, str)) else 0
        self.turn = turn
        self.phase = phase
        self.detachment = detachment or ""
        self.faction_id = faction_id or ""
        self.effect = effect
        self.conditions = conditions

    @staticmethod
    def from_json(data: Dict[str, Any]) -> "Stratagem":
        return Stratagem(
            id=data.get("id", ""),
            name=data.get("name", ""),
            type=data.get("type", ""),
            description=data.get("description", ""),
            cp_cost=data.get("cp_cost", 0),
            turn=data.get("turn", ""),
            phase=data.get("phase", ""),
            detachment=data.get("detachment", ""),
            faction_id=data.get("faction_id", ""),
        )

    def applies_to_army(self, army) -> bool:
        # Global if no faction_id
        is_global = self.faction_id == ""
        if is_global:
            return True
        # Otherwise must match faction and (if present) detachment
        if getattr(army, "faction_id", None) and army.faction_id != self.faction_id:
            return False
        if self.detachment:
            # Must match detachment name exactly (source data string)
            return getattr(army, "detachment_type", "") == self.detachment
        return True

    def can_use(self, player, game, **kwargs) -> bool:
        # Targeting restrictions:
        # - Embarked units cannot be targeted by stratagems (no exceptions here).
        # - Battle-shocked units cannot be targeted by stratagems, except INSANE BRAVERY.
        try:
            tgt = _extract_friendly_target_unit_from_kwargs(kwargs)
            # Embarked is always blocked (rule is broader than Battle-shock).
            if _unit_cannot_be_target_of_stratagem(tgt):
                if (self.name or "").strip().upper() == "INSANE BRAVERY":
                    # Allow INSANE BRAVERY only to bypass Battle-shock restriction, not embarked restriction.
                    # If target is embarked, still blocked.
                    try:
                        is_embarked = getattr(tgt, "is_embarked", None)
                        if callable(is_embarked) and bool(is_embarked):
                            return False
                    except Exception:
                        pass
                    try:
                        if getattr(tgt, "embarked_in", None) is not None:
                            return False
                    except Exception:
                        pass
                    # Otherwise, if this was blocked only due to battle-shock, allow it.
                    # (We can't perfectly distinguish reasons here, so do a focused check.)
                    try:
                        is_bs = getattr(tgt, "is_battle_shocked", None)
                        if callable(is_bs) and bool(is_bs()):
                            pass
                        else:
                            # If not battle-shocked but still blocked, keep blocked.
                            return False
                    except Exception:
                        return False
                else:
                    return False
        except Exception:
            # Defensive: never crash availability checks due to unexpected stub shapes.
            pass

        # Allow CP cost modifiers (e.g. Direct the Slaughter) to affect affordability.
        target_unit = kwargs.get("target_unit", None)
        eff_cost = self.cp_cost
        try:
            if hasattr(player, "preview_stratagem_cp_cost"):
                eff_cost = int(player.preview_stratagem_cp_cost(self, target_unit=target_unit).get("cost", self.cp_cost))
        except Exception:
            eff_cost = self.cp_cost
        if player.command_points < eff_cost:
            return False
        # Phase awareness
        phase_name = kwargs.get("phase_name")
        if phase_name and not self.is_phase_allowed(phase_name):
            return False
        # Turn awareness
        active_player = getattr(game, 'get_current_player', lambda: None)()
        is_active_turn = active_player is player
        if not self.is_turn_allowed(is_active_turn):
            return False
        if self.conditions is None:
            return True
        return bool(self.conditions(player, game, **kwargs))

    def use(self, player, game, **kwargs) -> bool:
        if not self.can_use(player, game, **kwargs):
            return False
        # Apply CP cost modifiers now (consumes once-per-battle-round discounts if used)
        target_unit = kwargs.get("target_unit", None)
        eff_cost = self.cp_cost
        try:
            if hasattr(player, "apply_stratagem_cp_cost"):
                eff_cost = int(player.apply_stratagem_cp_cost(self, target_unit=target_unit).get("cost", self.cp_cost))
        except Exception:
            eff_cost = self.cp_cost
        if not player.spend_command_points(eff_cost):
            return False
        if self.effect is not None:
            self.effect(player, game, **kwargs)
        else:
            try:
                print(f"⚠️ No effect implemented for Stratagem: {self.name}")
            except Exception:
                pass
        return True

    def __str__(self) -> str:
        return f"{self.name} ({self.type}): {self.description}"

    def __repr__(self) -> str:
        return (
            f"Stratagem(id={self.id}, name={self.name}, type={self.type}, cp_cost={self.cp_cost}, "
            f"turn={self.turn}, phase={self.phase}, detachment={self.detachment}, faction_id={self.faction_id})"
        )

    # ---------------- Timing helpers ----------------
    def is_phase_allowed(self, phase_name: str) -> bool:
        """
        phase_name: canonical current phase name, e.g. 'Command phase', 'Movement phase', 'Shooting phase', 'Charge phase', 'Fight phase'.
        Source data may contain 'Any phase' or combined text like 'Shooting or Fight phase'.
        """
        if not phase_name:
            return True
        current = phase_name.strip().lower()
        raw = (self.phase or "").strip().lower()
        if not raw or 'any phase' in raw:
            return True
        # Allow simple substring or 'x or y' checks
        if current in raw:
            return True
        # Common aliasing
        aliases = {
            'command phase': ['command'],
            'movement phase': ['movement', 'move'],
            'shooting phase': ['shooting', 'shoot'],
            'charge phase': ['charge'],
            'fight phase': ['fight', 'fighting']
        }
        for canonical, keys in aliases.items():
            if current == canonical:
                if any(k in raw for k in keys):
                    return True
        return False

    def is_turn_allowed(self, is_active_turn: bool) -> bool:
        raw = (self.turn or "").strip().lower()
        if not raw or 'either' in raw:
            return True
        if 'your turn' in raw:
            return is_active_turn
        if "opponent's turn" in raw or 'opponents turn' in raw:
            return not is_active_turn
        return True


class StratagemManager:
    def __init__(self, player) -> None:
        # Lazy import to avoid cycles
        from warhammer40k_ai.waha_helper import WahaHelper

        self.player = player
        self.game = getattr(player, "game", None)
        self._waha = WahaHelper()
        self.available: List[Stratagem] = []
        self._event_subscribed = False
        self._last_failed_battle_shock_unit = None
        self._current_phase_name: Optional[str] = None
        self._pending_reactions: List[Dict[str, Any]] = []
        self._reaction_timeout_s = 5.0
        # Track temporary per-phase stratagem buffs that must be cleaned up.
        self._epic_challenge_models: list[Any] = []
        self._build_available()
        self._subscribe_events()
        # Per-turn usage limits (e.g., Overwatch once/turn)
        self._used_this_turn: Dict[str, bool] = {
            'OVERWATCH': False,
        }
        # Core rules: a player cannot use the same Stratagem more than once in the same phase.
        # (Unless an ability explicitly names the Stratagem; we do not implement such bypasses generically.)
        self._used_stratagems_this_phase: set[str] = set()
        # Once-per-battle limits (e.g., INSANE BRAVERY once per battle)
        self._used_once_per_battle: Dict[str, bool] = {
            'INSANE BRAVERY': False,
        }

    def _dequeue_reaction_by_name(self, stratagem_name: str) -> None:
        """Remove the first pending reaction matching this stratagem name."""
        try:
            target = (stratagem_name or "").strip().lower()
            if not target:
                return
            for i, r in enumerate(list(self._pending_reactions)):
                if str(r.get("stratagem", "")).strip().lower() == target:
                    self._pending_reactions.pop(i)
                    return
        except Exception:
            return

    def _now(self) -> float:
        return float(time.monotonic())

    def _queue_reaction(self, payload: Dict[str, Any], use_timer: bool = True) -> None:
        if not isinstance(payload, dict):
            return
        if use_timer:
            payload["expires_at"] = self._now() + float(self._reaction_timeout_s)
        payload["reaction"] = True
        self._pending_reactions.append(payload)

    def _prune_expired_reactions(self, now: Optional[float] = None) -> None:
        ts = self._now() if now is None else float(now)
        kept = []
        for r in list(self._pending_reactions):
            try:
                expires_at = r.get("expires_at", None)
                if expires_at is not None and ts >= float(expires_at):
                    continue
            except Exception:
                pass
            kept.append(r)
        self._pending_reactions = kept

    def _reaction_time_left(self, reaction: Dict[str, Any], now: Optional[float] = None) -> Optional[float]:
        try:
            expires_at = reaction.get("expires_at", None)
            if expires_at is None:
                return None
            ts = self._now() if now is None else float(now)
            return max(0.0, float(expires_at) - ts)
        except Exception:
            return None

    def _is_implemented_stratagem(self, stratagem: Stratagem) -> bool:
        try:
            return (stratagem.name or "").strip().upper() in IMPLEMENTED_STRATAGEM_NAMES
        except Exception:
            return False

    def _turn_category(self, stratagem: Stratagem) -> str:
        try:
            if stratagem.is_turn_allowed(True) and stratagem.is_turn_allowed(False):
                return "either"
            if stratagem.is_turn_allowed(False) and not stratagem.is_turn_allowed(True):
                return "opponent"
            return "your"
        except Exception:
            return "your"

    def _effective_cp_cost(self, stratagem: Stratagem, context: Dict[str, Any]) -> int:
        target_unit = context.get("target_unit") or context.get("unit")
        cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        try:
            if hasattr(self.player, "preview_stratagem_cp_cost"):
                prev = self.player.preview_stratagem_cp_cost(stratagem, target_unit=target_unit)
                return int(prev.get("cost", cost))
        except Exception:
            return cost
        return cost

    def _evaluate_availability(
        self,
        stratagem: Stratagem,
        context: Dict[str, Any],
        *,
        is_active_turn: bool,
    ) -> Dict[str, Any]:
        result = {"available": False, "reason": None, "cp_cost": self._effective_cp_cost(stratagem, context)}
        name_u = (stratagem.name or "").strip().upper()
        phase_name = context.get("phase_name") or self._current_phase_name or ""

        if name_u and name_u in self._used_stratagems_this_phase:
            result["reason"] = "Already used this phase"
            return result
        if name_u and self._used_once_per_battle.get(name_u, False):
            result["reason"] = "Once per battle used"
            return result
        if name_u == "OVERWATCH" or name_u == "FIRE OVERWATCH":
            if self._used_this_turn.get("OVERWATCH", False):
                result["reason"] = "Already used this turn"
                return result

        if not stratagem.is_phase_allowed(phase_name):
            result["reason"] = "Wrong phase"
            return result
        if not stratagem.is_turn_allowed(is_active_turn):
            result["reason"] = "Wrong turn"
            return result

        if int(getattr(self.player, "command_points", 0) or 0) < int(result["cp_cost"] or 0):
            result["reason"] = "Not enough CP"
            return result

        # Targeting restrictions for provided context
        target = _extract_friendly_target_unit_from_kwargs(context)
        if target is not None and _unit_cannot_be_target_of_stratagem(target):
            if name_u != "INSANE BRAVERY":
                result["reason"] = "Target cannot be selected"
                return result

        # Last pass: delegate to stratagem conditions
        try:
            if stratagem.can_use(self.player, self.game, **context):
                result["available"] = True
                result["reason"] = None
                return result
        except Exception:
            pass

        result["reason"] = "Requires valid trigger or target"
        return result

    def _reaction_target_label(self, reaction: Dict[str, Any]) -> str:
        try:
            if reaction.get("enemy_unit") is not None:
                return f"Vs {getattr(reaction['enemy_unit'], 'name', 'Enemy')}"
            if reaction.get("target_unit") is not None:
                return f"Target: {getattr(reaction['target_unit'], 'name', 'Unit')}"
            if reaction.get("unit") is not None:
                return f"Target: {getattr(reaction['unit'], 'name', 'Unit')}"
            if reaction.get("target_model") is not None:
                return f"Target model: {getattr(reaction['target_model'], 'name', 'Model')}"
        except Exception:
            return ""
        return ""

    def _build_available(self) -> None:
        """
        Chapter Approved scope:
        - Only global stratagems (faction_id == "").
        - Only "Core – ..." and mission-pack "Core Stratagem – ..." entries.
        - Exclude Boarding Actions / Challenger / other game modes and all faction/detachment stratagems.
        """
        raw = self._waha.get_stratagems_for_faction(faction_id=None, detachment=None)
        tnorm = lambda t: (t or "").strip().lower()
        filtered: list[dict] = []
        for s in list(raw or []):
            try:
                if (s.get("faction_id") or "").strip():
                    continue  # skip faction/detachment stratagems entirely
                tt = tnorm(s.get("type"))
                if "boarding actions" in tt or "boarding action" in tt:
                    continue
                if "challenger" in tt:
                    continue
                # Keep only core + core stratagem variants
                if not (tt.startswith("core ") or tt.startswith("core\u00a0") or tt.startswith("core\u2013") or tt.startswith("core-") or tt.startswith("core stratagem")):
                    # For safety, also keep "core –" variants that might not start with "core " due to unicode dashes.
                    if "core" not in tt:
                        continue
                    if "core stratagem" not in tt and "core \u2013" not in tt and "core -" not in tt:
                        continue
                filtered.append(s)
            except Exception:
                continue
        # Deduplicate by name: keep the newest/highest id for each name (case-insensitive).
        def _id_key(entry: dict) -> int:
            try:
                return int((entry.get("id") or "0").strip())
            except Exception:
                return 0
        by_name: dict[str, dict] = {}
        for entry in filtered:
            name_key = (entry.get("name", "") or "").strip().lower()
            if not name_key:
                continue
            prev = by_name.get(name_key)
            if prev is None or _id_key(entry) > _id_key(prev):
                by_name[name_key] = entry
        unique = list(by_name.values())
        # Stable ordering
        unique.sort(key=lambda e: ((e.get("name") or "").strip().lower(), -_id_key(e)))
        self.available = [Stratagem.from_json(s) for s in unique]

    def _subscribe_events(self) -> None:
        if self._event_subscribed or not self.game:
            return
        es = getattr(self.game, "event_system", None)
        if not es:
            return
        es.subscribe("phase_start", self._on_phase_start)
        es.subscribe("phase_end", self._on_phase_end)
        es.subscribe("battle_shock_test_started", self._on_battle_shock_test_started)
        es.subscribe("battle_shock_test_resolved", self._on_battle_shock_test_resolved)
        # Movement events for Overwatch
        es.subscribe("unit_move_started", self._on_unit_move_started)
        es.subscribe("unit_move_ended", self._on_unit_move_ended)
        # Shooting targeting events for reaction stratagems (e.g. GO TO GROUND)
        es.subscribe("shooting_targets_selected", self._on_shooting_targets_selected)
        # Fight phase selections for reaction stratagems (e.g. EPIC CHALLENGE)
        es.subscribe("fight_unit_selected", self._on_fight_unit_selected)
        # Fight sequence completion for COUNTER-OFFENSIVE
        es.subscribe("fight_sequence_complete", self._on_fight_sequence_complete)
        # Dice events for Command Re-roll
        es.subscribe("roll_made", self._on_roll_made)
        self._event_subscribed = True

    # -------- Event handlers --------
    def _on_phase_start(self, player, phase, **kwargs):
        # Clear per-phase transient allowances
        self._last_failed_battle_shock_unit = None
        # Track phase for phase-aware filtering
        try:
            # Phase may be an Enum; normalize to a friendly string
            name = getattr(phase, 'name', None)
            if name:
                # Convert ENUM_NAME to 'Name phase'
                name_map = {
                    'COMMAND_PHASE': 'Command phase',
                    'MOVEMENT_PHASE': 'Movement phase',
                    'SHOOTING_PHASE': 'Shooting phase',
                    'CHARGE_PHASE': 'Charge phase',
                    'FIGHT_PHASE': 'Fight phase',
                }
                self._current_phase_name = name_map.get(name, name.title().replace('_', ' '))
            else:
                # If provided as string already
                self._current_phase_name = str(phase)
        except Exception:
            self._current_phase_name = None
        # Reset once-per-turn limits on your turn start
        try:
            is_active_turn = player is self.player
            if is_active_turn and getattr(phase, 'name', None) == 'COMMAND_PHASE':
                self._used_this_turn['OVERWATCH'] = False
        except Exception:
            pass
        try:
            self._used_stratagems_this_phase.clear()
        except Exception:
            self._used_stratagems_this_phase = set()

    def _on_phase_end(self, player, phase, **kwargs):
        # Queue NEW ORDERS at end of your Command phase
        try:
            is_your_turn = player is self.player
            phase_name = getattr(phase, 'name', None)
            if is_your_turn and phase_name == 'COMMAND_PHASE':
                s = self.get_by_name('NEW ORDERS')
                if s and s.can_use(self.player, self.game, phase_name='Command phase'):
                    if getattr(self.player, 'active_secondaries', None) and self.player.can_draw_secondary():
                        # Deduplicate if already present for this phase end
                        already = False
                        for r in self._pending_reactions:
                            if r.get('event') == 'phase_end' and r.get('stratagem') == s.name and r.get('phase') == 'Command phase':
                                already = True
                                break
                        if not already:
                            self._queue_reaction({
                                'event': 'phase_end',
                                'phase': 'Command phase',
                                'phase_name': 'Command phase',
                                'stratagem': s.name,
                                'cp_cost': s.cp_cost,
                                'options': [c for c in self.player.active_secondaries],
                            }, use_timer=False)
        except Exception:
            pass

        # Clear end-of-phase defensive buffs (e.g. GO TO GROUND) to avoid leaking into later phases (e.g. Overwatch).
        try:
            phase_name = getattr(phase, 'name', None)
            if phase_name == 'SHOOTING_PHASE':
                for u in list(getattr(self.player.get_army(), "units", []) or []):
                    try:
                        sr = getattr(u, "special_rules", None)
                        if isinstance(sr, dict) and sr.get("go_to_ground_active") is True:
                            sr.pop("go_to_ground_active", None)
                            u.special_rules = sr
                        if isinstance(sr, dict) and sr.get("smokescreen_active") is True:
                            sr.pop("smokescreen_active", None)
                            u.special_rules = sr
                    except Exception:
                        continue
        except Exception:
            pass

        # Clear end-of-phase offensive buffs (e.g. EPIC CHALLENGE) to avoid leaking into later phases.
        try:
            phase_name = getattr(phase, "name", None)
            if phase_name == "FIGHT_PHASE":
                for m in list(getattr(self, "_epic_challenge_models", []) or []):
                    try:
                        sr = getattr(m, "special_rules", None)
                        if isinstance(sr, dict) and sr.get("epic_challenge_precision_active") is True:
                            sr.pop("epic_challenge_precision_active", None)
                            m.special_rules = sr
                    except Exception:
                        continue
                self._epic_challenge_models = []
        except Exception:
            pass

        # Queue RAPID INGRESS at end of opponent's Movement phase
        try:
            # Event supplies the active player as `player`. We offer this to the NON-active player.
            is_opponents_turn = player is not self.player
            phase_name = getattr(phase, 'name', None)
            if is_opponents_turn and phase_name == 'MOVEMENT_PHASE':
                s = self.get_by_name('RAPID INGRESS')
                if not s:
                    return
                # Must have at least one eligible unit in Reserves that could arrive this battle round
                candidates = []
                try:
                    # Prefer Game helper if present
                    if hasattr(self.game, 'get_units_that_can_arrive_from_reserves'):
                        candidates = list(self.game.get_units_that_can_arrive_from_reserves(self.player))
                    else:
                        candidates = [u for u in getattr(self.player.get_army(), 'units', []) or []
                                      if getattr(u, 'is_in_reserves', lambda: False)()
                                      and getattr(u, 'can_arrive_from_reserves', lambda _t: False)(getattr(self.game, 'turn', 0))]
                except Exception:
                    candidates = []
                if not candidates:
                    return
                # Timing checks (CP/turn/phase)
                if not s.can_use(self.player, self.game, phase_name='Movement phase'):
                    return
                # Deduplicate per phase end
                for r in self._pending_reactions:
                    if r.get('event') == 'phase_end' and str(r.get('stratagem', '')).upper() == 'RAPID INGRESS':
                        return
                self._queue_reaction({
                    'event': 'phase_end',
                    'phase': 'Movement phase',
                    'phase_name': 'Movement phase',
                    'stratagem': s.name,
                    'cp_cost': s.cp_cost,
                    'candidates': candidates,
                })
        except Exception:
            pass
    def _on_battle_shock_test_started(self, unit, **kwargs):
        # Core: INSANE BRAVERY is used just before taking a Battle-shock test (auto-pass).
        try:
            if unit is None:
                return
            # Only offer when the unit belongs to this player
            try:
                if unit.get_parent_army().player is not self.player:
                    return
            except Exception:
                return
            s = self.get_by_name("INSANE BRAVERY")
            if not s:
                return
            # Once per battle restriction
            if self._used_once_per_battle.get("INSANE BRAVERY", False):
                return
            # Timing: Battle-shock step of your Command phase (best-effort via phase tracker)
            if (self._current_phase_name or "").strip().lower() != "command phase":
                return
            if not s.can_use(self.player, self.game, unit=unit, phase_name=self._current_phase_name):
                return
            # Queue as a reaction (UI can choose to use it)
            self._queue_reaction({
                "event": "battle_shock_test_started",
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "unit": unit,
                "phase_name": self._current_phase_name,
            })
        except Exception:
            return

    def _on_battle_shock_test_resolved(self, unit, passed: bool, **kwargs):
        if not passed and unit and unit.get_parent_army() and unit.get_parent_army().player is self.player:
            self._last_failed_battle_shock_unit = unit
            # Queue a reaction opportunity for UI: INSANE BRAVERY
            s = self.get_by_name('INSANE BRAVERY')
            if s:
                phase_name = self._current_phase_name
                if s.can_use(self.player, self.game, unit=unit, phase_name=phase_name):
                    self._queue_reaction({
                        'event': 'battle_shock_failed',
                        'stratagem': s.name,
                        'unit': unit,
                        'phase_name': phase_name,
                        'cp_cost': s.cp_cost,
                    })

    # Overwatch triggers: on enemy movement start/end (enqueue for non-active player)
    def _on_unit_move_started(self, unit, action: str, **kwargs):
        self._maybe_queue_overwatch(unit, action, when='start')

    def _on_unit_move_ended(self, unit, action: str, **kwargs):
        self._maybe_queue_overwatch(unit, action, when='end')
        self._maybe_queue_tank_shock(unit, action)
        self._maybe_queue_heroic_intervention(unit, action)

    def _maybe_queue_tank_shock(self, charging_unit, action: str) -> None:
        # Trigger condition: just after a VEHICLE unit from your army ends a Charge move.
        try:
            if str(action or "").strip().lower() != "charge":
                return
            if charging_unit is None or not getattr(charging_unit, "is_alive", lambda: True)():
                return
            # Must be your unit
            owner_player = charging_unit.get_parent_army().player
            if owner_player is not self.player:
                return
            # Must be Charge phase and your turn (best-effort; phase gate is also enforced at use-time)
            if (self._current_phase_name or "").strip().lower() != "charge phase":
                return
            if not bool(getattr(charging_unit, "is_vehicle", False)):
                return
        except Exception:
            return

        s = self.get_by_name("TANK SHOCK")
        if not s:
            return
        if self.player.command_points < s.cp_cost:
            return

        # Must have at least one enemy unit within Engagement Range
        enemy_units = []
        try:
            enemy_units = list(self.game.map.get_enemy_units(charging_unit)) if self.game and getattr(self.game, "map", None) else []
        except Exception:
            enemy_units = []
        eligible = []
        for e in enemy_units:
            try:
                if e is None or not e.is_alive():
                    continue
                if self.game and getattr(self.game, "map", None) and self.game.map.is_within_engagement_range(charging_unit, e):
                    eligible.append(e)
            except Exception:
                continue
        if not eligible:
            return

        # Queue reaction: UI can choose enemy_unit later; default heuristic will pick the first.
        self._queue_reaction({
            "event": "charge_move_ended",
            "phase_name": "Charge phase",
            "stratagem": s.name,
            "cp_cost": s.cp_cost,
            "unit": charging_unit,
            "target_unit": charging_unit,
            "eligible_enemy_units": eligible,
        })

    def _maybe_queue_heroic_intervention(self, charging_unit, action: str) -> None:
        # Trigger condition: after an enemy unit ends a Charge move (opponent's turn).
        try:
            if str(action or "").strip().lower() != "charge":
                return
            if charging_unit is None or not getattr(charging_unit, "is_alive", lambda: True)():
                return
            owner_player = charging_unit.get_parent_army().player
            if owner_player is self.player:
                return
            if (self._current_phase_name or "").strip().lower() != "charge phase":
                return
        except Exception:
            return

        s = self.get_by_name("HEROIC INTERVENTION")
        if not s:
            return
        if self.player.command_points < s.cp_cost:
            return

        # Find eligible friendly units within 6" that could charge that enemy unit.
        candidates = []
        try:
            for unit in list(getattr(self.player.get_army(), "units", []) or []):
                if not unit.is_alive() or not unit.deployed:
                    continue
                # Restriction: only WALKER vehicles can be selected.
                try:
                    if unit.has_keyword("Vehicle") and not unit.has_keyword("Walker"):
                        continue
                except Exception:
                    pass
                # Core rule: battle-shocked or embarked units cannot be targeted.
                if _unit_cannot_be_target_of_stratagem(unit):
                    continue
                dist = None
                try:
                    if self.game and getattr(self.game, "map", None):
                        dist = self.game.map.get_distance_between_units(unit, charging_unit)
                except Exception:
                    dist = None
                if dist is None or dist > 6.0:
                    continue
                try:
                    if not unit.can_declare_charge_against(charging_unit, self.game, out_of_turn=True):
                        continue
                except Exception:
                    continue
                candidates.append(unit)
        except Exception:
            return

        if not candidates:
            return

        # Deduplicate for the same enemy unit.
        already = False
        for r in self._pending_reactions:
            if r.get("event") == "heroic_intervention" and r.get("stratagem") == s.name and r.get("enemy_unit") is charging_unit:
                already = True
                break
        if already:
            return

        self._queue_reaction({
            "event": "heroic_intervention",
            "phase_name": "Charge phase",
            "stratagem": s.name,
            "cp_cost": s.cp_cost,
            "enemy_unit": charging_unit,
            "candidates": candidates,
        })

    def _on_shooting_targets_selected(self, attacking_unit=None, target_units=None, **kwargs):
        """
        Reaction window for GO TO GROUND:
        Opponent Shooting phase, just after an enemy unit has selected its targets.
        """
        try:
            if not self.game or not getattr(self.game, "map", None):
                return
            if (self._current_phase_name or "").strip().lower() != "shooting phase":
                return
            # This event is published by the active shooter's execution; we offer to the NON-active player.
            if attacking_unit is None:
                return
            owner_player = attacking_unit.get_parent_army().player
            if owner_player is self.player:
                return  # only opponent can react
            s = self.get_by_name("GO TO GROUND")
            if not s:
                return
            if self.player.command_points < s.cp_cost:
                return
            candidates = []
            for u in list(target_units or []):
                try:
                    if u is None or not u.is_alive():
                        continue
                    if u.get_parent_army().player is not self.player:
                        continue
                    if not bool(getattr(u, "is_infantry", False)):
                        continue
                    if _unit_cannot_be_target_of_stratagem(u):
                        continue
                    candidates.append(u)
                except Exception:
                    continue
            if not candidates:
                return
            # Queue as a reaction with candidates; UI may choose which unit to protect.
            self._queue_reaction({
                "event": "shooting_targets_selected",
                "phase_name": "Shooting phase",
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "attacking_unit": attacking_unit,
                "candidates": candidates,
            })
        except Exception:
            return

        # Also offer SMOKESCREEN in the same window (opponent Shooting phase, after targets selected).
        try:
            s2 = self.get_by_name("SMOKESCREEN")
            if not s2:
                return
            if self.player.command_points < s2.cp_cost:
                return
            # Core rule: can't use the same stratagem more than once per phase
            if (s2.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            smoke_candidates = []
            for u in list(target_units or []):
                try:
                    if u is None or not u.is_alive():
                        continue
                    if u.get_parent_army().player is not self.player:
                        continue
                    if _unit_cannot_be_target_of_stratagem(u):
                        continue
                    # Target must be a SMOKE unit
                    if hasattr(u, "has_keyword") and callable(getattr(u, "has_keyword")):
                        if not u.has_keyword("SMOKE"):
                            continue
                    else:
                        continue
                    smoke_candidates.append(u)
                except Exception:
                    continue
            if not smoke_candidates:
                return
            self._queue_reaction({
                "event": "shooting_targets_selected",
                "phase_name": "Shooting phase",
                "stratagem": s2.name,
                "cp_cost": s2.cp_cost,
                "attacking_unit": attacking_unit,
                "candidates": smoke_candidates,
            })
        except Exception:
            return

    def _on_fight_unit_selected(self, unit=None, selecting_player=None, **kwargs):
        """
        Reaction window for EPIC CHALLENGE:
        Fight phase, when a CHARACTER unit from your army that is within Engagement Range of one or more
        Attached units is selected to fight.
        """
        try:
            if unit is None:
                return
            if (self._current_phase_name or "").strip().lower() != "fight phase":
                return
            # Offer only to the player selecting the unit
            if selecting_player is not self.player:
                return
            s = self.get_by_name("EPIC CHALLENGE")
            if not s:
                return
            if self.player.command_points < s.cp_cost:
                return
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            # Must be a CHARACTER unit
            if not bool(getattr(unit, "is_character", False)) and not (hasattr(unit, "has_keyword") and unit.has_keyword("CHARACTER")):
                return
            # Must be within ER of one or more enemy Attached units
            try:
                enemy_units = self.game.map.get_enemy_units(unit)
            except Exception:
                enemy_units = []
            ok = False
            for e in list(enemy_units or []):
                try:
                    if not e.is_alive():
                        continue
                    if not self.game.map.is_within_engagement_range(unit, e):
                        continue
                    members = []
                    try:
                        fn = getattr(e, "get_attached_unit_members", None)
                        if callable(fn):
                            members = list(fn())
                    except Exception:
                        members = []
                    if len(members) > 1:
                        ok = True
                        break
                except Exception:
                    continue
            if not ok:
                return
            # Eligible models: CHARACTER models in your unit (usually the unit itself is a single CHARACTER model).
            models = []
            for m in list(getattr(unit, "models", []) or []):
                try:
                    if getattr(m, "is_alive", True):
                        models.append(m)
                except Exception:
                    continue
            if not models:
                return
            self._queue_reaction({
                "event": "fight_unit_selected",
                "phase_name": "Fight phase",
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "unit": unit,
                "eligible_models": models,
            })
        except Exception:
            return

    def _on_fight_sequence_complete(self, unit=None, player=None, stage=None, **kwargs):
        """
        Reaction window for COUNTER-OFFENSIVE:
        Fight phase, just after an enemy unit has fought.
        """
        try:
            if unit is None or not self.game:
                return
            if (self._current_phase_name or "").strip().lower() != "fight phase":
                return
            # Offer only to the opponent of the unit that just fought
            owner_player = None
            try:
                owner_player = unit.get_parent_army().player
            except Exception:
                owner_player = player
            if owner_player is None or owner_player is self.player:
                return
            s = self.get_by_name("COUNTER-OFFENSIVE")
            if not s:
                return
            if self.player.command_points < s.cp_cost:
                return
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            # Avoid duplicate pending entries
            for r in self._pending_reactions:
                if str(r.get("stratagem", "")).strip().upper() == "COUNTER-OFFENSIVE":
                    return
            # Build eligible candidates (any unit that can fight and has not fought)
            try:
                if hasattr(self.game, "get_eligible_fighting_units"):
                    base_units = list(self.game.get_eligible_fighting_units(self.player))
                else:
                    base_units = list(getattr(self.player.get_army(), "units", []) or [])
            except Exception:
                base_units = []
            fight_mgr = getattr(self.game, "fight_phase_manager", None)
            try:
                fought = set(getattr(fight_mgr, "fought_units", set()) or []) if fight_mgr else set()
            except Exception:
                fought = set()
            canonicalize = getattr(fight_mgr, "_canonical_unit_for_fight", None) if fight_mgr else None
            candidates = []
            seen = set()
            for u in list(base_units or []):
                try:
                    root = canonicalize(u) if callable(canonicalize) else u
                except Exception:
                    root = u
                if root is None:
                    continue
                rid = id(root)
                if rid in seen:
                    continue
                seen.add(rid)
                try:
                    if root in fought:
                        continue
                except Exception:
                    pass
                try:
                    if getattr(root, "round_state", None) and getattr(root.round_state, "fought_this_phase", False):
                        continue
                except Exception:
                    pass
                try:
                    if _unit_cannot_be_target_of_stratagem(root):
                        continue
                except Exception:
                    pass
                try:
                    if root.get_parent_army().player is not self.player:
                        continue
                except Exception:
                    pass
                try:
                    if hasattr(root, "is_eligible_to_fight") and callable(root.is_eligible_to_fight):
                        if not root.is_eligible_to_fight(self.game.map):
                            continue
                except Exception:
                    pass
                candidates.append(root)
            if not candidates:
                return
            self._queue_reaction({
                "event": "fight_sequence_complete",
                "phase_name": "Fight phase",
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "enemy_unit": unit,
                "stage": stage,
                "candidates": candidates,
            })
        except Exception:
            return

    def _maybe_queue_overwatch(self, moving_unit, action: str, when: str) -> None:
        # Only offer to the opponent of the moving unit's owner
        try:
            owner_player = moving_unit.get_parent_army().player
            if owner_player is self.player:
                return
        except Exception:
            return
        s = self.get_by_name('FIRE OVERWATCH') or self.get_by_name('Overwatch')
        if not s:
            return
        # Enforce once per turn limit
        if self._used_this_turn.get('OVERWATCH', False):
            return
        # Phase check: Movement or Charge phase per data
        phase_name = self._current_phase_name
        if not s.is_phase_allowed(phase_name or ''):
            return
        # Turn check: opponent's turn
        active_player = getattr(self.game, 'get_current_player', lambda: None)()
        is_active_turn = active_player is self.player
        if not s.is_turn_allowed(is_active_turn):
            # For Overwatch, it should be opponent's turn
            pass
        # CP check
        if self.player.command_points < s.cp_cost:
            return
        # QUICK ELIGIBILITY PRECHECKS per Stratagem text:
        # - Your unit must be within 24" of the enemy unit
        # - Cannot target a TITANIC friendly unit to fire Overwatch
        # - Enemy must be visible to your unit (checked later at use-time; here we only queue if 24" condition holds)
        try:
            candidates = []
            for unit in getattr(self.player.get_army(), 'units', []) or []:
                if not unit.is_alive() or not unit.deployed:
                    continue
                if getattr(unit, 'is_titanic', False):
                    continue  # Restriction: cannot select a TITANIC friendly unit
                # Core rule: Overwatch targets the shooter; battle-shocked units cannot be targeted.
                if _unit_cannot_be_target_of_stratagem(unit):
                    continue
                # Distance check to moving enemy unit (edge-to-edge shortest model pair)
                dist = None
                try:
                    if hasattr(self.game, 'map') and hasattr(self.game.map, 'get_distance_between_units'):
                        dist = self.game.map.get_distance_between_units(unit, moving_unit)
                except Exception:
                    dist = None
                if dist is not None and dist <= 24.0:
                    candidates.append(unit)
            if not candidates:
                return
        except Exception:
            # If we fail to evaluate candidates, be conservative and don't queue
            return

        # Queue opportunity with minimal context; UI will choose shooter before resolving
        # Deduplicate if same enemy move reaction is already queued
        already = False
        for r in self._pending_reactions:
            if r.get('event') == 'enemy_move' and r.get('stratagem') == s.name and r.get('enemy_unit') is moving_unit:
                already = True
                break
        if not already:
            self._queue_reaction({
                'event': 'enemy_move',
                'when': when,
                'action': action,
                'stratagem': s.name,
                'enemy_unit': moving_unit,
                'phase_name': phase_name,
                'cp_cost': s.cp_cost,
                'candidates': candidates,
            })

    # Command Re-roll trigger on roll_made for active player only
    def _on_roll_made(self, player, unit, roll_type: str, value, reroll, dice=None, **kwargs):
        # If some other rule already rerolled/locks this roll (10e: a dice can't be re-rolled more than once),
        # do not offer Command Re-roll.
        try:
            if bool(kwargs.get("reroll_locked", False)):
                return
        except Exception:
            pass
        if player is not self.player:
            return
        s = self.get_by_name('COMMAND RE-ROLL')
        if not s:
            return
        # Core rules: cannot use the same stratagem more than once per phase (per player).
        try:
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
        except Exception:
            pass
        phase_name = self._current_phase_name
        if not s.is_phase_allowed(phase_name or ''):
            return
        if not s.is_turn_allowed(True):
            return
        if self.player.command_points < s.cp_cost:
            return
        # Queue re-roll opportunity with a callable to execute reroll if chosen
        self._queue_reaction({
            'event': 'roll_made',
            'stratagem': s.name,
            'unit': unit,
            'roll_type': roll_type,
            'value': value,
            'dice': dice,
            'phase_name': phase_name,
            'cp_cost': s.cp_cost,
            'reroll': reroll,
        })

    def _on_model_destroyed(
        self,
        attacker_model=None,
        attacker_unit=None,
        target_model=None,
        target_unit=None,
        weapon_profile=None,
        **kwargs,
    ) -> None:
        """
        Faction stratagem reactions that trigger "just after" a model is destroyed.
        """
        # WORLD EATERS: SKULLS FOR THE SKULL THRONE!
        try:
            s = self.get_by_name("SKULLS FOR THE SKULL THRONE!")
        except Exception:
            s = None
        if not s:
            return
        # Must be your stratagem manager's player army, in Fight phase (per stratagem text).
        if attacker_unit is None or target_unit is None:
            return
        try:
            if attacker_unit.get_parent_army().player is not self.player:
                return
        except Exception:
            return
        # Ensure current phase is Fight phase
        phase_name = self._current_phase_name
        if not (phase_name and phase_name.strip().lower() == "fight phase"):
            return
        # Must be a melee kill (Fight phase should imply, but be explicit).
        try:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is None or not parent.is_melee():
                return
        except Exception:
            return
        # Target must be CHARACTER or MONSTER model (approximate via unit keywords)
        try:
            is_char = bool(target_unit.has_keyword("Character"))
            is_mon = bool(target_unit.has_keyword("Monster"))
            if not (is_char or is_mon):
                return
        except Exception:
            return
        # Check CP / turn / phase gating
        if not s.can_use(self.player, self.game, phase_name=phase_name):
            return
        # Deduplicate same reaction for same attacker+target model in this phase
        for r in self._pending_reactions:
            try:
                if r.get("event") == "model_destroyed" and r.get("stratagem") == s.name and r.get("attacker_unit") is attacker_unit and r.get("target_model") is target_model:
                    return
            except Exception:
                continue
        self._queue_reaction({
            "event": "model_destroyed",
            "phase_name": phase_name,
            "stratagem": s.name,
            "cp_cost": s.cp_cost,
            "attacker_unit": attacker_unit,
            "target_model": target_model,
            "target_unit": target_unit,
        })

    # -------- Public API --------
    def list_available(self) -> List[Stratagem]:
        return list(self.available)

    def get_by_name(self, name: str) -> Optional[Stratagem]:
        for s in self.available:
            if s.name.lower() == name.lower():
                return s
        return None

    def can_use(self, name: str, **kwargs) -> bool:
        s = self.get_by_name(name)
        if not s:
            return False
        return s.can_use(self.player, self.game, **kwargs)

    def use(self, name: str, **kwargs) -> bool:
        s = self.get_by_name(name)
        if not s:
            return False

        # Core restriction: a player cannot use the same Stratagem more than once in the same phase.
        # Applies to all stratagems (including ones usable in "Any phase"), unless an ability explicitly
        # names the stratagem (not implemented as a generic bypass).
        try:
            phase_name = kwargs.get("phase_name") or self._current_phase_name
            if phase_name:
                key = (s.name or "").strip().upper()
                if key and key in self._used_stratagems_this_phase:
                    print(f"❌ Cannot use {s.name} more than once in the same phase (core rules)")
                    return False
        except Exception:
            pass

        # Targeting restrictions (manager layer too, since several special-cases bypass Stratagem.use()).
        # - Embarked units cannot be targeted by stratagems (no exceptions here).
        # - Battle-shocked units cannot be targeted by stratagems, except INSANE BRAVERY.
        try:
            tgt = _extract_friendly_target_unit_from_kwargs(kwargs)
            if _unit_cannot_be_target_of_stratagem(tgt):
                if (s.name or "").strip().upper() == "INSANE BRAVERY":
                    # Only bypass battle-shock restriction, not embarked restriction.
                    try:
                        is_embarked = getattr(tgt, "is_embarked", None)
                        if callable(is_embarked) and bool(is_embarked):
                            print("❌ Cannot target an embarked unit with a Stratagem")
                            return False
                    except Exception:
                        pass
                    try:
                        if getattr(tgt, "embarked_in", None) is not None:
                            print("❌ Cannot target an embarked unit with a Stratagem")
                            return False
                    except Exception:
                        pass
                    # If the unit is battle-shocked, allow INSANE BRAVERY.
                    try:
                        is_bs = getattr(tgt, "is_battle_shocked", None)
                        if callable(is_bs) and bool(is_bs()):
                            pass
                        else:
                            return False
                    except Exception:
                        return False
                else:
                    print("❌ Cannot target a Battle-shocked or embarked unit with a Stratagem")
                    return False
        except Exception:
            pass

        # Core: INSANE BRAVERY (auto-pass a Battle-shock test about to be taken; once per battle)
        if s.name.upper() == "INSANE BRAVERY":
            if self._used_once_per_battle.get("INSANE BRAVERY", False):
                print("❌ INSANE BRAVERY can only be used once per battle")
                return False
            target = kwargs.get("unit")
            if not target:
                print("❌ INSANE BRAVERY: no target unit provided")
                return False
            # Spend CP
            if not self.player.spend_command_points(s.cp_cost):
                return False
            # Mark auto-pass flag to be consumed by Unit.take_battle_shock_test()
            try:
                sr = getattr(target, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["auto_pass_next_battle_shock_test"] = True
                target.special_rules = sr
            except Exception:
                pass
            self._used_once_per_battle["INSANE BRAVERY"] = True
            try:
                print(f"🛡️ INSANE BRAVERY used on {getattr(target, 'name', 'Unit')}: next Battle-shock test auto-passes (once per battle)")
            except Exception:
                pass
            if kwargs.get('dequeue') is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                pass
            return True

        # Core: COUNTER-OFFENSIVE
        if s.name.upper() == "COUNTER-OFFENSIVE":
            target_unit = kwargs.get("target_unit") or kwargs.get("unit")
            if target_unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "COUNTER-OFFENSIVE":
                        cands = r.get("candidates") or []
                        if cands:
                            target_unit = cands[0]
                        break
            if target_unit is None:
                print("ERROR: COUNTER-OFFENSIVE: no target unit provided")
                return False
            if (self._current_phase_name or "").strip().lower() != "fight phase":
                print("ERROR: COUNTER-OFFENSIVE: not in Fight phase")
                return False
            fight_mgr = getattr(self.game, "fight_phase_manager", None)
            try:
                if fight_mgr and hasattr(fight_mgr, "_canonical_unit_for_fight"):
                    target_unit = fight_mgr._canonical_unit_for_fight(target_unit)
            except Exception:
                pass
            try:
                if target_unit.get_parent_army().player is not self.player:
                    print("ERROR: COUNTER-OFFENSIVE: target unit is not yours")
                    return False
            except Exception:
                pass
            try:
                if fight_mgr and hasattr(fight_mgr, "fought_units") and target_unit in fight_mgr.fought_units:
                    print("ERROR: COUNTER-OFFENSIVE: target unit already fought this phase")
                    return False
            except Exception:
                pass
            try:
                if getattr(target_unit, "round_state", None) and getattr(target_unit.round_state, "fought_this_phase", False):
                    print("ERROR: COUNTER-OFFENSIVE: target unit already fought this phase")
                    return False
            except Exception:
                pass
            try:
                if hasattr(target_unit, "is_eligible_to_fight") and callable(target_unit.is_eligible_to_fight):
                    if not target_unit.is_eligible_to_fight(self.game.map):
                        print("ERROR: COUNTER-OFFENSIVE: target unit is not eligible to fight")
                        return False
            except Exception:
                pass
            if not fight_mgr or not hasattr(fight_mgr, "force_next_unit"):
                print("WARNING: COUNTER-OFFENSIVE: fight phase manager not available")
                return False
            try:
                if not fight_mgr.force_next_unit(target_unit, self.player):
                    print("ERROR: COUNTER-OFFENSIVE: could not force unit to fight next")
                    return False
            except Exception:
                return False
            if not self.player.spend_command_points(s.cp_cost):
                try:
                    fight_mgr._forced_next_unit = None
                    fight_mgr._forced_next_player = None
                except Exception:
                    pass
                return False
            try:
                if getattr(fight_mgr, "_current_player", None) is not None and getattr(fight_mgr, "_opponent_player", None) is not None:
                    fight_mgr._request_unit_selection(fight_mgr._current_player, fight_mgr._opponent_player)
            except Exception:
                pass
            if kwargs.get('dequeue') is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                pass
            return True

        # Core: SMOKESCREEN (Benefit of Cover + Stealth until end of phase)
        if s.name.upper() == "SMOKESCREEN":
            target_unit = kwargs.get("target_unit") or kwargs.get("unit")
            if not target_unit:
                # Try candidates from pending
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "SMOKESCREEN":
                        cands = r.get("candidates") or []
                        if cands:
                            target_unit = cands[0]
                        break
            if not target_unit:
                print("❌ SMOKESCREEN: missing target unit")
                return False
            # Target must be SMOKE
            try:
                if not (hasattr(target_unit, "has_keyword") and target_unit.has_keyword("SMOKE")):
                    print("❌ SMOKESCREEN: target is not a SMOKE unit")
                    return False
            except Exception:
                return False
            if not self.player.spend_command_points(s.cp_cost):
                return False
            try:
                sr = getattr(target_unit, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["smokescreen_active"] = True
                target_unit.special_rules = sr
            except Exception:
                pass
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                pass
            print(f"🛡️ SMOKESCREEN: {getattr(target_unit, 'name', 'Unit')} gains Benefit of Cover + Stealth until end of phase.")
            return True
        # Special-case: FIRE OVERWATCH full resolution
        if s.name.upper() in ("FIRE OVERWATCH", "OVERWATCH"):
            enemy_unit = kwargs.get("enemy_unit")
            if not enemy_unit:
                # Try to take from last pending
                if self._pending_reactions:
                    for r in self._pending_reactions:
                        if r.get('stratagem','').upper() in ("FIRE OVERWATCH", "OVERWATCH"):
                            enemy_unit = r.get('enemy_unit')
                            break
            if not enemy_unit:
                print("❌ Overwatch: no enemy unit context")
                return False
            # Choose shooter unit
            shooter = kwargs.get("shooter_unit")
            if not shooter:
                # Prefer candidates if present, else find any within 24"
                candidates = []
                try:
                    for unit in getattr(self.player.get_army(), 'units', []) or []:
                        if not unit.is_alive() or not unit.deployed:
                            continue
                        if getattr(unit, 'is_titanic', False):
                            continue
                        # Core rule: Overwatch targets the shooter; battle-shocked units cannot be targeted.
                        if _unit_cannot_be_target_of_stratagem(unit):
                            continue
                        dist = None
                        try:
                            if hasattr(self.game, 'map') and hasattr(self.game.map, 'get_distance_between_units'):
                                dist = self.game.map.get_distance_between_units(unit, enemy_unit)
                        except Exception:
                            dist = None
                        if dist is not None and dist <= 24.0:
                            candidates.append(unit)
                except Exception:
                    candidates = []
                # Pick heuristic: most ranged weapons
                if candidates:
                    shooter = max(candidates, key=lambda u: sum(1 for m in u.models for w in getattr(m, 'wargear', []) if getattr(w, 'is_ranged', lambda: False)()))
            if not shooter:
                print("❌ Overwatch: no eligible shooter in 24\"")
                return False
            # Even if a shooter was explicitly provided, enforce battle-shock restriction.
            if _unit_cannot_be_target_of_stratagem(shooter):
                print("❌ Overwatch: cannot target a Battle-shocked unit")
                return False
            # Build declarations: group best ranged profile per model for target
            declarations = []
            profile_to_models = {}
            for model in shooter.models:
                if not getattr(model, 'is_alive', False):
                    continue
                best_profile = None
                best_score = -1.0
                for wargear in getattr(model, 'wargear', []) or []:
                    if not getattr(wargear, 'is_ranged', lambda: False)():
                        continue
                    for _, profile in getattr(wargear, 'profiles', {}).items():
                        try:
                            score = float(profile.get_damage_potential(enemy_unit))
                        except Exception:
                            score = 0.0
                        if score > best_score:
                            best_score = score
                            best_profile = profile
                if best_profile is not None:
                    profile_to_models.setdefault(best_profile, []).append(model)
            for profile, models in profile_to_models.items():
                declarations.append({'weapon_profile': profile, 'target_unit': enemy_unit, 'models': models})
            if not declarations:
                print("❌ Overwatch: no ranged weapons eligible")
                return False
            # Apply Overwatch hit restriction: only unmodified 6 hits
            ok = False
            try:
                setattr(shooter, '_overwatch_sixes_only', True)
                print(f"🎯 Overwatch: {shooter.name} firing at {enemy_unit.name} ({len(declarations)} weapons)")
                ok = shooter.execute_shooting_declarations(declarations, self.game.map)
            finally:
                try:
                    delattr(shooter, '_overwatch_sixes_only')
                except Exception:
                    pass
                # If execution failed, ensure we do not mark the unit as having shot
                if not ok and getattr(shooter, 'round_state', None):
                    shooter.round_state.shot_this_round = False
            if ok:
                # Mark once per turn consumed
                self._used_this_turn['OVERWATCH'] = True
                # If this was a queued reaction, drop it
                if kwargs.get('dequeue') is True:
                    self._dequeue_reaction_by_name(s.name)
                # Spend CP and return through normal use path (so CP is deducted consistently)
                if not self.player.spend_command_points(s.cp_cost):
                    print("⚠️ Overwatch succeeded but CP spend failed; adjusting CP manually")
                try:
                    self._used_stratagems_this_phase.add((s.name or "").strip().upper())
                except Exception:
                    pass
                return True
            else:
                print("❌ Overwatch: shooting failed or invalid")
                return False

        # Special-case: COMMAND RE-ROLL
        if s.name.upper() == "COMMAND RE-ROLL":
            # Find the pending roll context if not provided
            roll_type = kwargs.get('roll_type')
            reroll_cb = kwargs.get('reroll')
            unit = kwargs.get('unit')
            dice = kwargs.get('dice')
            value = kwargs.get('value')
            if not reroll_cb:
                for r in reversed(self._pending_reactions):
                    if r.get('stratagem', '').upper() == 'COMMAND RE-ROLL':
                        reroll_cb = r.get('reroll')
                        roll_type = roll_type or r.get('roll_type')
                        unit = unit or r.get('unit')
                        dice = dice or r.get('dice')
                        value = value or r.get('value')
                        break
            if not callable(reroll_cb):
                print("❌ Command Re-roll: no reroll callback available")
                return False
            # Spend CP first per rules, then perform the reroll
            if not self.player.spend_command_points(s.cp_cost):
                return False
            try:
                result = reroll_cb()
                # Optional: log outcome
                try:
                    name = getattr(unit, 'name', 'Unit') if unit else 'Unit'
                    if roll_type == 'advance':
                        print(f"🔁 Command Re-roll: {name} new advance roll -> {result}")
                    elif roll_type == 'charge':
                        total = result[0] if isinstance(result, (list, tuple)) else result
                        print(f"🔁 Command Re-roll: {name} new charge roll -> {total}")
                    elif roll_type == 'hazardous':
                        print(f"🔁 Command Re-roll: {name} new hazardous roll -> {result}")
                    elif roll_type in ('hit','wound','save','damage','attacks'):
                        print(f"🔁 Command Re-roll: {name} new {roll_type} roll -> {result}")
                    else:
                        print(f"🔁 Command Re-roll executed ({roll_type})")
                except Exception:
                    pass
                # Remove the matching pending reaction if present
                for i in range(len(self._pending_reactions)-1, -1, -1):
                    if self._pending_reactions[i].get('stratagem', '').upper() == 'COMMAND RE-ROLL':
                        self._pending_reactions.pop(i)
                        break
                try:
                    self._used_stratagems_this_phase.add((s.name or "").strip().upper())
                except Exception:
                    pass
                return True
            except Exception as e:
                print(f"❌ Command Re-roll failed: {e}")
                return False

        # Core: EPIC CHALLENGE (grant Precision to a selected CHARACTER model's melee attacks until end of phase)
        if s.name.upper() == "EPIC CHALLENGE":
            unit = kwargs.get("unit")
            model = kwargs.get("model")
            # Try to resolve from pending reaction context
            if unit is None or model is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "EPIC CHALLENGE":
                        unit = unit or r.get("unit")
                        elig = r.get("eligible_models") or []
                        model = model or (elig[0] if elig else None)
                        break
            if unit is None or model is None:
                print("❌ EPIC CHALLENGE: missing unit/model context")
                return False
            # Must be a CHARACTER model in your unit
            try:
                pu = getattr(model, "parent_unit", None)
                if pu is None or pu is not unit:
                    # Some internal structures may wrap, so accept as long as model is in unit.models
                    if model not in list(getattr(unit, "models", []) or []):
                        return False
            except Exception:
                return False
            if not self.player.spend_command_points(s.cp_cost):
                return False
            try:
                sr = getattr(model, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["epic_challenge_precision_active"] = True
                model.special_rules = sr
                self._epic_challenge_models.append(model)
            except Exception:
                pass
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                pass
            print(f"⚔️ EPIC CHALLENGE: {getattr(model, 'name', 'Character')} gains [PRECISION] on melee attacks until end of phase.")
            return True

        # Special-case: NEW ORDERS (discard one active Secondary and draw a new one)
        if s.name.upper() == "NEW ORDERS":
            # Must be your Command phase end; we gate to Command phase + your turn via is_phase_allowed/is_turn_allowed
            # Additional availability: need an active secondary and at least one card to draw
            player_obj = self.player
            if not getattr(player_obj, 'active_secondaries', None):
                print("❌ New Orders: no active Secondary to discard")
                return False
            if not player_obj.can_draw_secondary():
                print("❌ New Orders: no Secondary cards left to draw")
                return False
            # Choose target card (allow UI to pass one)
            target_card = kwargs.get('secondary_card')
            if target_card is None:
                # Default heuristic: discard the first active
                try:
                    target_card = player_obj.active_secondaries[0]
                except Exception:
                    target_card = None
            if target_card is None or target_card not in player_obj.active_secondaries:
                print("❌ New Orders: invalid or missing target Secondary card")
                return False
            # Spend CP per stratagem cost
            if not self.player.spend_command_points(s.cp_cost):
                return False
            # Discard chosen card and draw back up to two
            try:
                name = getattr(target_card, 'name', 'Secondary')
                print(f"🗂️ New Orders: discarding '{name}' and drawing a new Secondary")
            except Exception:
                pass
            player_obj.discard_secondary(target_card, gain_cp=False)
            player_obj.draw_secondary_until_two(self.game)
            if kwargs.get('dequeue') is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                pass
            return True

        # Special-case: RAPID INGRESS (arrive from reserves at end of opponent's Movement phase)
        if s.name.upper() == "RAPID INGRESS":
            # Choose target unit
            target = kwargs.get("unit") or kwargs.get("target_unit")
            if target is None:
                # Try candidates from queued reaction context
                cand = kwargs.get("candidates") or []
                if cand:
                    # Prefer Deep Strike units (non-strategic reserves) first
                    try:
                        target = next((u for u in cand if not getattr(u, "is_in_strategic_reserves", lambda: False)()), cand[0])
                    except Exception:
                        target = cand[0]
            if target is None:
                print("❌ Rapid Ingress: no target unit provided")
                return False
            # Validate ownership + reserves status
            try:
                if target.get_parent_army().player is not self.player:
                    print("❌ Rapid Ingress: target unit does not belong to player")
                    return False
            except Exception:
                return False
            if not getattr(target, "is_in_reserves", lambda: False)():
                print("❌ Rapid Ingress: target unit is not in reserves")
                return False
            # Restriction: cannot arrive in a battle round it would not normally be able to
            if not getattr(target, "can_arrive_from_reserves", lambda _t: False)(getattr(self.game, "turn", 0)):
                print("❌ Rapid Ingress: target unit cannot arrive from reserves this battle round")
                return False
            # Determine placement
            position = kwargs.get("position")
            if position is None:
                try:
                    position = self.game.find_valid_reserves_position(target) if hasattr(self.game, "find_valid_reserves_position") else None
                except Exception:
                    position = None
            if not position:
                print("❌ Rapid Ingress: could not find a valid placement position")
                return False
            # Attempt arrival
            try:
                ok = target.arrive_from_reserves(position, getattr(self.game, "turn", 0), getattr(self.game, "map", None))
            except Exception as e:
                print(f"❌ Rapid Ingress: arrival failed: {e}")
                return False
            if not ok:
                print("❌ Rapid Ingress: arrival failed")
                return False
            # Add to map unit list if needed
            try:
                if hasattr(self.game, "map") and hasattr(self.game.map, "units"):
                    if target not in self.game.map.units:
                        self.game.map.units.append(target)
            except Exception:
                pass
            # Spend CP (after success to avoid consuming CP on placement failure)
            if not self.player.spend_command_points(s.cp_cost):
                print("⚠️ Rapid Ingress succeeded but CP spend failed; adjusting CP manually")
            print(f"🪂 Rapid Ingress: {target.name} arrived from reserves")
            if kwargs.get('dequeue') is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                pass
            return True

        # Core: GO TO GROUND
        if s.name.upper() == "GO TO GROUND":
            target = kwargs.get("unit") or kwargs.get("target_unit")
            if target is None:
                cand = kwargs.get("candidates") or []
                if cand:
                    target = cand[0]
            if target is None:
                print("❌ GO TO GROUND: no target unit provided")
                return False
            # Spend CP
            if not self.player.spend_command_points(s.cp_cost):
                return False
            # Mark active until end of Shooting phase; cleared in _on_phase_end.
            try:
                sr = getattr(target, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["go_to_ground_active"] = True
                target.special_rules = sr
                print(f"🛡️ GO TO GROUND used on {getattr(target, 'name', 'Unit')}: Benefit of Cover + 6++ until end of phase")
            except Exception:
                pass
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                pass
            return True

        # Core: GRENADE
        if s.name.upper() == "GRENADE":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            enemy = kwargs.get("enemy_unit")
            if unit is None:
                # Best-effort pick: first eligible GRENADES unit from your army
                for u in list(getattr(self.player.get_army(), "units", []) or []):
                    try:
                        if not u.is_alive() or not getattr(u, "deployed", False):
                            continue
                        if not u.has_keyword("Grenades"):
                            continue
                        if getattr(u.round_state, "advanced_this_round", False) or getattr(u.round_state, "fell_back_this_round", False) or getattr(u.round_state, "shot_this_round", False):
                            continue
                        if self.game and getattr(self.game, "map", None):
                            if any(self.game.map.is_within_engagement_range(u, e) for e in (self.game.map.get_enemy_units(u) or []) if e.is_alive()):
                                continue
                        unit = u
                        break
                    except Exception:
                        continue
            if unit is None:
                print("❌ GRENADE: no eligible friendly GRENADES unit")
                return False
            if enemy is None and self.game and getattr(self.game, "map", None):
                # Best-effort: pick the first eligible enemy within 8" and visible, and not in engagement range of any friendly unit.
                try:
                    enemies = list(self.game.map.get_enemy_units(unit)) or []
                except Exception:
                    enemies = []
                for e in enemies:
                    try:
                        if e is None or not e.is_alive():
                            continue
                        # Enemy must not be within engagement range of any friendly unit
                        ok = True
                        for f in list(getattr(self.player.get_army(), "units", []) or []):
                            if f is None or not getattr(f, "deployed", False) or not f.is_alive():
                                continue
                            if self.game.map.is_within_engagement_range(f, e):
                                ok = False
                                break
                        if not ok:
                            continue
                        if self.game.map.get_distance_between_units(unit, e) > 8.0:
                            continue
                        # Visibility: any model in unit can see any model in enemy
                        vis = False
                        for m in (unit.get_models_for_collision() or []):
                            if not getattr(m, "is_alive", False):
                                continue
                            for tm in (e.get_models_for_collision() or []):
                                if not getattr(tm, "is_alive", False):
                                    continue
                                if self.game.map.can_model_see_model(m, tm):
                                    vis = True
                                    break
                            if vis:
                                break
                        if not vis:
                            continue
                        enemy = e
                        break
                    except Exception:
                        continue
            if enemy is None:
                print("❌ GRENADE: no eligible enemy target found/provided")
                return False
            # Spend CP
            if not self.player.spend_command_points(s.cp_cost):
                return False
            # Roll 6D6; each 4+ = 1 mortal wound
            from ..utility.dice import get_roll
            rolls = [get_roll("D6") for _ in range(6)]
            mw = sum(1 for r in rolls if int(r) >= 4)
            try:
                print(f"💣 GRENADE: rolls={rolls} -> {mw} mortal wounds to {enemy.name}")
            except Exception:
                pass
            if mw > 0:
                try:
                    unit._apply_mortal_wounds_to_unit(enemy, int(mw), game_map=getattr(self.game, "map", None))
                except Exception:
                    pass
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                pass
            return True

        # Core: TANK SHOCK
        if s.name.upper() == "TANK SHOCK":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            enemy = kwargs.get("enemy_unit")
            eligible_enemies = kwargs.get("eligible_enemy_units") or []
            if unit is None:
                print("❌ TANK SHOCK: no charging VEHICLE unit provided")
                return False
            if not bool(getattr(unit, "is_vehicle", False)):
                print("❌ TANK SHOCK: target unit is not a VEHICLE")
                return False
            if enemy is None:
                enemy = eligible_enemies[0] if eligible_enemies else None
            if enemy is None and self.game and getattr(self.game, "map", None):
                try:
                    for e in (self.game.map.get_enemy_units(unit) or []):
                        if e is None or not e.is_alive():
                            continue
                        if self.game.map.is_within_engagement_range(unit, e):
                            enemy = e
                            break
                except Exception:
                    enemy = None
            if enemy is None:
                print("❌ TANK SHOCK: no enemy unit in Engagement Range")
                return False
            # Spend CP
            if not self.player.spend_command_points(s.cp_cost):
                return False
            # Pick a VEHICLE model in your unit within ER of that enemy unit.
            chosen_model = None
            try:
                from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
                for m in unit.get_models_for_collision():
                    if not getattr(m, "is_alive", False):
                        continue
                    for tm in enemy.get_models_for_collision():
                        if not getattr(tm, "is_alive", False):
                            continue
                        hd = float(horizontal_distance_between_bases_2d(m.model_base, tm.model_base))
                        vd = float(vertical_distance_between_bases(m.model_base, tm.model_base))
                        if hd <= ENGAGEMENT_RANGE_HORIZONTAL and vd <= ENGAGEMENT_RANGE_VERTICAL:
                            chosen_model = m
                            break
                    if chosen_model is not None:
                        break
            except Exception:
                chosen_model = None
            if chosen_model is None:
                try:
                    chosen_model = next(m for m in unit.get_models_for_collision() if getattr(m, "is_alive", False))
                except Exception:
                    chosen_model = None
            if chosen_model is None:
                print("❌ TANK SHOCK: no alive VEHICLE model found")
                return False
            try:
                tval = int(getattr(chosen_model, "toughness", getattr(unit, "toughness", 0)) or 0)
            except Exception:
                tval = 0
            if tval <= 0:
                print("❌ TANK SHOCK: could not determine Toughness for VEHICLE model")
                return False
            from ..utility.dice import get_roll
            rolls = [get_roll("D6") for _ in range(int(tval))]
            mw = min(6, sum(1 for r in rolls if int(r) >= 5))
            try:
                print(f"🚙 TANK SHOCK: rolls={rolls} (T{tval}) -> {mw} mortal wounds to {enemy.name}")
            except Exception:
                pass
            if mw > 0:
                try:
                    unit._apply_mortal_wounds_to_unit(enemy, int(mw), game_map=getattr(self.game, "map", None))
                except Exception:
                    pass
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                pass
            return True

        # Core: HEROIC INTERVENTION
        if s.name.upper() == "HEROIC INTERVENTION":
            enemy = kwargs.get("enemy_unit")
            candidates = list(kwargs.get("candidates") or [])
            if enemy is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").upper() == "HEROIC INTERVENTION":
                        enemy = r.get("enemy_unit") or enemy
                        if not candidates:
                            candidates = list(r.get("candidates") or [])
                        break
            if enemy is None:
                print("Heroic Intervention: no enemy unit context")
                return False

            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None and candidates:
                unit = candidates[0]
            if unit is None:
                print("Heroic Intervention: no eligible unit selected")
                return False

            try:
                if unit.get_parent_army().player is not self.player:
                    print("Heroic Intervention: target unit does not belong to player")
                    return False
            except Exception:
                return False

            try:
                if unit.has_keyword("Vehicle") and not unit.has_keyword("Walker"):
                    print("Heroic Intervention: only WALKER vehicles can be selected")
                    return False
            except Exception:
                pass

            dist = None
            try:
                if self.game and getattr(self.game, "map", None):
                    dist = self.game.map.get_distance_between_units(unit, enemy)
            except Exception:
                dist = None
            if dist is None or dist > 6.0:
                print("Heroic Intervention: target not within 6\" of enemy")
                return False

            try:
                if not unit.can_declare_charge_against(enemy, self.game, out_of_turn=True):
                    print("Heroic Intervention: target cannot declare charge against enemy")
                    return False
            except Exception:
                print("Heroic Intervention: target cannot declare charge against enemy")
                return False

            if not self.player.spend_command_points(s.cp_cost):
                return False

            ok = False
            try:
                ok = bool(self.game.attempt_charge(unit, enemy, out_of_turn=True, count_as_charged=False))
            except Exception:
                ok = False

            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                pass
            if not ok:
                print("Heroic Intervention: charge failed")
            return True

        # Provide phase_name for timing checks
        if 'phase_name' not in kwargs:
            kwargs['phase_name'] = self._current_phase_name
        ok = s.use(self.player, self.game, **kwargs)
        if ok:
            # Mark per-turn limiter
            key = s.name.upper()
            if key in self._used_this_turn:
                self._used_this_turn[key] = True
            # If this was a queued reaction, drop it
            if 'dequeue' in kwargs and kwargs['dequeue'] is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                pass
        return ok

    # -------- UI helpers for non-disruptive prompts --------
    def get_phase_stratagem_items(self) -> List[Dict[str, Any]]:
        self._prune_expired_reactions()
        phase_name = self._current_phase_name or ""
        active_player = self.game.get_current_player() if self.game else None
        is_active_turn = active_player is self.player
        now = self._now()

        items: List[Dict[str, Any]] = []
        pending_names: set[str] = set()

        # Pending reactions first
        for r in list(self._pending_reactions):
            s = self.get_by_name(str(r.get("stratagem", "")))
            if not s or not self._is_implemented_stratagem(s):
                continue
            ctx = dict(r)
            if "phase_name" not in ctx and phase_name:
                ctx["phase_name"] = phase_name
            if not s.is_phase_allowed(ctx.get("phase_name", "") or phase_name):
                continue
            availability = self._evaluate_availability(s, ctx, is_active_turn=is_active_turn)
            time_left = None
            if availability["available"]:
                time_left = self._reaction_time_left(r, now=now)
            trigger_label = ""
            try:
                if r.get("event") == "enemy_move":
                    action = str(r.get("action", "") or "").strip().lower()
                    when = str(r.get("when", "") or "").strip().lower()
                    if action == "charge":
                        trigger_label = "Trigger: enemy charge"
                    elif when == "start":
                        trigger_label = "Trigger: enemy move start"
                    elif when == "end":
                        trigger_label = "Trigger: enemy move end"
                elif r.get("event") in ("charge_move_ended", "heroic_intervention"):
                    trigger_label = "Trigger: enemy charge end"
                elif r.get("event") == "shooting_targets_selected":
                    trigger_label = "Trigger: after targets selected"
                elif r.get("event") == "fight_sequence_complete":
                    trigger_label = "Trigger: after enemy fought"
                elif r.get("event") == "roll_made":
                    trigger_label = "Trigger: roll made"
                elif r.get("event") == "battle_shock_test_started":
                    trigger_label = "Trigger: battle-shock test"
                elif r.get("event") == "phase_end":
                    trigger_label = "Trigger: phase end"
            except Exception:
                trigger_label = ""
            items.append({
                "name": s.name,
                "cp_cost": availability["cp_cost"],
                "available": availability["available"],
                "reason": availability["reason"],
                "turn_category": self._turn_category(s),
                "is_reaction": True,
                "context": ctx,
                "target_label": self._reaction_target_label(r),
                "trigger_label": trigger_label,
                "time_left": time_left,
            })
            try:
                pending_names.add((s.name or "").strip().upper())
            except Exception:
                pass

        # Phase-available stratagems (implemented only)
        for s in self.available:
            if not self._is_implemented_stratagem(s):
                continue
            if not s.is_phase_allowed(phase_name or ""):
                continue
            name_u = (s.name or "").strip().upper()
            if name_u in pending_names and name_u in REACTION_ONLY_STRATAGEM_NAMES:
                continue
            ctx = {"phase_name": phase_name}
            availability = self._evaluate_availability(s, ctx, is_active_turn=is_active_turn)
            if name_u in REACTION_ONLY_STRATAGEM_NAMES:
                if availability["available"]:
                    availability["available"] = False
                    availability["reason"] = "No trigger"
                elif availability["reason"] in (None, "", "Requires valid trigger or target"):
                    availability["reason"] = "No trigger"
            items.append({
                "name": s.name,
                "cp_cost": availability["cp_cost"],
                "available": availability["available"],
                "reason": availability["reason"],
                "turn_category": self._turn_category(s),
                "is_reaction": False,
                "context": ctx,
                "target_label": "",
                "trigger_label": "",
                "time_left": None,
            })

        return items

    def get_pending_reactions(self, clear: bool = False) -> List[Dict[str, Any]]:
        self._prune_expired_reactions()
        items = list(self._pending_reactions)
        if clear:
            self._pending_reactions = []
        return items
