from typing import Callable, Optional, Dict, Any, List


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
        if player.command_points < self.cp_cost:
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
        if not player.spend_command_points(self.cp_cost):
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
        self._build_available()
        self._subscribe_events()
        # Per-turn usage limits (e.g., Overwatch once/turn)
        self._used_this_turn: Dict[str, bool] = {
            'OVERWATCH': False,
            'COMMAND RE-ROLL': False,
        }

    def _build_available(self) -> None:
        army = self.player.get_army()
        faction_id = getattr(army, "faction_id", None)
        detachment = getattr(army, "detachment_type", None)
        raw = self._waha.get_stratagems_for_faction(faction_id=faction_id, detachment=detachment)
        # Exclude Boarding Actions and similar modes not used in standard games
        tnorm = lambda t: (t or '').strip().lower()
        filtered = [s for s in raw if 'boarding actions' not in tnorm(s.get('type')) and 'boarding action' not in tnorm(s.get('type'))]
        # Prefer Core Stratagem variants and deduplicate by name (case-insensitive)
        def _sort_key(entry: dict) -> int:
            type_text = (entry.get('type', '') or '').strip().lower()
            return 0 if 'core stratagem' in type_text else 1
        filtered.sort(key=_sort_key)
        seen_names = set()
        unique: list[dict] = []
        for entry in filtered:
            name_key = (entry.get('name', '') or '').strip().lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)
            unique.append(entry)
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
                self._used_this_turn['COMMAND RE-ROLL'] = False
        except Exception:
            pass

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
                            self._pending_reactions.append({
                                'event': 'phase_end',
                                'phase': 'Command phase',
                                'stratagem': s.name,
                                'cp_cost': s.cp_cost,
                                'options': [c for c in self.player.active_secondaries],
                            })
        except Exception:
            pass
    def _on_battle_shock_test_started(self, unit, **kwargs):
        # Opportunity to use pre-test variants if implemented later
        pass

    def _on_battle_shock_test_resolved(self, unit, passed: bool, **kwargs):
        if not passed and unit and unit.get_parent_army() and unit.get_parent_army().player is self.player:
            self._last_failed_battle_shock_unit = unit
            # Queue a reaction opportunity for UI: INSANE BRAVERY
            s = self.get_by_name('INSANE BRAVERY')
            if s:
                phase_name = self._current_phase_name
                if s.can_use(self.player, self.game, unit=unit, phase_name=phase_name):
                    self._pending_reactions.append({
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
        # Identify opponent for reaction window
        try:
            opponent = next(p for p in self.game.players if p is not owner_player)
        except Exception:
            opponent = None
        # Deduplicate if same enemy move reaction is already queued
        already = False
        for r in self._pending_reactions:
            if r.get('event') == 'enemy_move' and r.get('stratagem') == s.name and r.get('enemy_unit') is moving_unit:
                already = True
                break
        if not already:
            self._pending_reactions.append({
                'event': 'enemy_move',
                'when': when,
                'stratagem': s.name,
                'enemy_unit': moving_unit,
                'phase_name': phase_name,
                'cp_cost': s.cp_cost,
                'candidates': candidates,
            })
        # Publish a UI hint to start a brief reaction window for the opponent
        if opponent is not None and hasattr(self.game, 'event_system'):
            try:
                self.game.event_system.publish("stratagem_window", player=opponent, duration=3.0)
            except Exception:
                pass

    # Command Re-roll trigger on roll_made for active player only
    def _on_roll_made(self, player, unit, roll_type: str, value, reroll, dice=None, **kwargs):
        if player is not self.player:
            return
        s = self.get_by_name('COMMAND RE-ROLL')
        if not s:
            return
        # Respect once per phase/turn depending on your preferred rule; we apply once per turn guard
        if self._used_this_turn.get('COMMAND RE-ROLL', False):
            return
        phase_name = self._current_phase_name
        if not s.is_phase_allowed(phase_name or ''):
            return
        if not s.is_turn_allowed(True):
            return
        if self.player.command_points < s.cp_cost:
            return
        # Queue re-roll opportunity with a callable to execute reroll if chosen
        self._pending_reactions.append({
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
        # Special-case: INSANE BRAVERY (Boarding or Core versions)
        if s.name.upper() == "INSANE BRAVERY":
            target = kwargs.get("unit") or self._last_failed_battle_shock_unit
            if not target:
                return False
            # Remove Battle-shock and mark as passed
            try:
                # If unit already has Battle-shock, remove it; otherwise ensure not applied
                from .status_effects import BattleShockEffect
                to_remove = [e for e in target.status_effects if isinstance(e, BattleShockEffect)]
                for eff in to_remove:
                    target.remove_status_effect(eff)
                # No explicit flag needed beyond removing effect; event or logs
                print(f"🛡️ INSANE BRAVERY used on {target.name}: treat test as passed; not Battle-shocked.")
            except Exception:
                pass
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
                # Spend CP and return through normal use path (so CP is deducted consistently)
                if not self.player.spend_command_points(s.cp_cost):
                    print("⚠️ Overwatch succeeded but CP spend failed; adjusting CP manually")
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
                # Mark once-per-turn limiter
                self._used_this_turn['COMMAND RE-ROLL'] = True
                # Remove the matching pending reaction if present
                for i in range(len(self._pending_reactions)-1, -1, -1):
                    if self._pending_reactions[i].get('stratagem', '').upper() == 'COMMAND RE-ROLL':
                        self._pending_reactions.pop(i)
                        break
                return True
            except Exception as e:
                print(f"❌ Command Re-roll failed: {e}")
                return False

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
                if self._pending_reactions:
                    try:
                        self._pending_reactions.pop(0)
                    except Exception:
                        pass
        return ok

    # -------- UI helpers for non-disruptive prompts --------
    def list_available_for_current_phase(self) -> List[Stratagem]:
        phase_name = self._current_phase_name
        active_player = self.game.get_current_player()
        is_active_turn = active_player is self.player
        # Hide any stratagem whose name is already present as a pending reaction
        reaction_names = {str(r.get('stratagem', '')).strip().lower() for r in self._pending_reactions}
        results: List[Stratagem] = []
        for s in self.available:
            name_key = s.name.strip().lower()
            if name_key in reaction_names:
                continue
            if s.name.upper() in ("COMMAND RE-ROLL", "INSANE BRAVERY"):
                # Only meaningful as reactions when a roll was made or battle-shock failed
                continue
            if not s.is_phase_allowed(phase_name or ''):
                continue
            if not s.is_turn_allowed(is_active_turn):
                continue
            if self.player.command_points < s.cp_cost:
                continue
            results.append(s)
        return results

    def get_pending_reactions(self, clear: bool = False) -> List[Dict[str, Any]]:
        items = list(self._pending_reactions)
        if clear:
            self._pending_reactions = []
        return items
