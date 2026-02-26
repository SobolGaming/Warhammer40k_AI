"""Auto-extracted Unit mixin methods from unit.py."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class ShootingMixin:
    def execute_shooting_declarations(self, weapon_declarations: List[dict], game_map: 'Map', *, out_of_phase: bool = False) -> bool:
        """
        Execute shooting declarations according to Warhammer 40k rules.
        
        Args:
            weapon_declarations: List of dicts with keys:
                - 'weapon_profile': WargearProfile to use
                - 'target_unit': Unit to target
                - 'models': List of models using this weapon
            game_map: Map instance for line of sight and range checks
            out_of_phase: True for out-of-phase shooting (e.g., Overwatch) so it does not consume normal shooting
            
        Returns:
            bool: True if any attacks were successful
        """
        if not weapon_declarations:
            logger.info(f"{self.name}: No shooting declarations to execute")
            return False

        # Check if unit can shoot
        # Mission Actions: a unit performing an Action is not eligible to shoot until that Action completes or end of turn
        action_lock_active = bool(getattr(self.round_state, "action_locked_until_turn_end", False))
        allow_shoot_while_action = False
        allow_shoot_while_action_source = ""
        if action_lock_active:
            game = None
            try:
                army = self.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
                if sm_mgr is not None and getattr(sm_mgr, "seekers_companions_allow_shoot_while_action", None):
                    allow_shoot_while_action = bool(
                        sm_mgr.seekers_companions_allow_shoot_while_action(
                            self,
                            game=game,
                        )
                    )
                    if allow_shoot_while_action:
                        allow_shoot_while_action_source = "Seeker's Companions"
            except Exception:
                allow_shoot_while_action = False
                allow_shoot_while_action_source = ""
            if not allow_shoot_while_action:
                try:
                    allow_fn = getattr(self, "allows_shoot_while_started_action_from_unit_contains_rule", None)
                    if callable(allow_fn):
                        allow_shoot_while_action = bool(allow_fn(game=game))
                        if allow_shoot_while_action:
                            allow_shoot_while_action_source = "unit contains model Action-shoot rule"
                except Exception:
                    allow_shoot_while_action = False
                    allow_shoot_while_action_source = ""
            if not allow_shoot_while_action:
                logger.info(f"{self.name} is performing an Action and cannot shoot this turn")
                return False
            logger.info(f"{self.name} is performing an Action but can shoot due to {allow_shoot_while_action_source}")
        if (not out_of_phase) and self.round_state.shot_this_round:
            action_shoot_exception_available = bool(
                action_lock_active
                and allow_shoot_while_action
                and (not bool(getattr(self.round_state, "action_permitted_shoot_used", False)))
            )
            if not action_shoot_exception_available:
                logger.info(f"{self.name} has already shot this round")
                return False

        # Chapter Approved exception: if this unit arrived from reserves via the "base touches edge"
        # Strategic Reserves placement, it cannot shoot this turn.
        try:
            if bool(getattr(self, "_reserves_edge_touch_this_turn", False)) and bool(getattr(self, "arrived_from_reserves_this_turn", False)):
                logger.info(f"{self.name} cannot shoot this turn (edge-touch Strategic Reserves placement)")
                return False
        except Exception:
            pass
            
        if self.round_state.fell_back_this_round:
            # Check if any weapons in the declarations can shoot after falling back
            can_shoot_any_weapon = False
            for declaration in weapon_declarations:
                if self.can_shoot_after_fall_back(declaration['weapon_profile']):
                    can_shoot_any_weapon = True
                    break
            
            if not can_shoot_any_weapon:
                logger.info(f"{self.name} cannot shoot after falling back")
                return False

        ficklefire_active = False
        try:
            ficklefire_active = bool(self._is_ficklefire_active())
        except Exception:
            ficklefire_active = False

        # BGNT hit modifier snapshot:
        # When a VEHICLE/MONSTER makes ranged attacks and it was Locked in Combat when it selected targets,
        # apply -1 to Hit (unless Pistols). Snapshot this now so casualties later don't change it mid-activation.
        try:
            bgnt_locked_at_selection = bool((self.is_vehicle or self.is_monster) and self._is_controlling_players_shooting_phase() and self._is_locked_in_combat(game_map))
            if ficklefire_active:
                bgnt_locked_at_selection = False
            setattr(self, "_bgnt_locked_at_target_selection", bgnt_locked_at_selection)
        except Exception:
            # Best-effort only; do not fail shooting if we can't snapshot.
            pass

        # Enforce PISTOL selection rules (10e):
        # - For non-VEHICLE/non-MONSTER models: if any non-pistol ranged weapons are selected, pistols cannot also be used.
        # - While within Engagement Range: only Pistols can be used by non-VEHICLE/non-MONSTER models.
        # This is enforced best-effort by filtering models out of conflicting declarations.
        try:
            is_vehicle_or_monster = bool(self.is_vehicle or self.is_monster)
            # Determine if this unit is engaged with any enemy
            engaged = self._is_locked_in_combat(game_map)
            if engaged and ficklefire_active:
                engaged = False

            # Build per-model "has pistol decl" and "has other decl"
            by_model: dict[str, dict[str, bool]] = {}
            for decl in weapon_declarations:
                wp = decl.get("weapon_profile")
                if wp is None:
                    continue
                is_pistol = bool(wp.is_pistol())
                for m in decl.get("models") or []:
                    if not getattr(m, "is_alive", False):
                        continue
                    key = get_entity_id(m)
                    entry = by_model.setdefault(key, {"pistol": False, "other": False})
                    if is_pistol:
                        entry["pistol"] = True
                    else:
                        entry["other"] = True

            # Filter declarations
            filtered_decls: list[dict] = []
            for decl in weapon_declarations:
                wp = decl.get("weapon_profile")
                if wp is None:
                    filtered_decls.append(decl)
                    continue
                wp_is_pistol = bool(wp.is_pistol())
                keep_models = []
                removed = 0
                for m in decl.get("models") or []:
                    if not getattr(m, "is_alive", False):
                        removed += 1
                        continue
                    flags = by_model.get(get_entity_id(m), {"pistol": False, "other": False})
                    if is_vehicle_or_monster:
                        # VEHICLE/MONSTER are not subject to the pistol-vs-other exclusivity rule.
                        keep_models.append(m)
                        continue
                    if engaged:
                        # Engaged non-VEHICLE/non-MONSTER: only pistols.
                        if wp_is_pistol:
                            keep_models.append(m)
                        else:
                            removed += 1
                        continue
                    # Not engaged non-VEHICLE/non-MONSTER:
                    # If both pistol and other were selected, prefer "other" and drop pistols.
                    if flags["pistol"] and flags["other"] and wp_is_pistol:
                        removed += 1
                        continue
                    keep_models.append(m)
                if removed and keep_models:
                    new_decl = dict(decl)
                    new_decl["models"] = keep_models
                    filtered_decls.append(new_decl)
                elif keep_models:
                    filtered_decls.append(decl)
                # else: drop empty declaration
            weapon_declarations = filtered_decls
        except Exception:
            pass

        ctan_ok, ctan_reason = self.validate_ctan_power_selection(weapon_declarations)
        if not ctan_ok:
            logger.info(f"{self.name}: {ctan_reason}")
            return False

        logger.info(f"{self.name} executing {len(weapon_declarations)} shooting declarations...")

        # Detect interactive dice roll mode (server-authoritative roll decisions).
        game = None
        interactive_mode = False
        try:
            game = getattr(self.get_parent_army().player, "game", None)
            if game is not None and not bool(getattr(game, "auto_resolve_dice_rolls", True)):
                interactive_mode = True
        except Exception:
            game = None
            interactive_mode = False
        
        if not out_of_phase:
            # Mark unit as having shot this round (regardless of success)
            self.round_state.shot_this_round = True
            if action_lock_active and allow_shoot_while_action:
                self.round_state.action_permitted_shoot_used = True

            # Firing Deck: models whose weapons are used via a transport count as having shot.
            # We mark them here (once) so even if some declarations fail validation, they still
            # count as having been selected to shoot via the transport.
            try:
                fd_models = []
                for decl in weapon_declarations:
                    for m in (decl.get("firing_deck_source_models") or []):
                        if m is not None:
                            fd_models.append(m)
                # De-dupe
                seen = set()
                for m in fd_models:
                    mid = get_entity_id(m)
                    if mid in seen:
                        continue
                    seen.add(mid)
                    try:
                        setattr(m, "_shot_via_firing_deck_this_round", True)
                    except Exception:
                        pass
                    # Also mark the source unit as having shot this round (best-effort) to prevent
                    # shoot-again effects from re-selecting that unit in this round.
                    try:
                        pu = getattr(m, "parent_unit", None)
                        if pu is not None and hasattr(pu, "round_state"):
                            pu.round_state.shot_this_round = True
                    except Exception:
                        pass
            except Exception:
                pass
        
        successful_attacks = 0
        hit_tracker = {}
        hit_models_by_target = {}
        hit_models_by_target_weapon: dict = {}
        hit_models_by_target_psychic: dict = {}
        attack_tracker = {}
        touched_targets = []
        try:
            seen_targets = set()
            for decl in weapon_declarations:
                t = decl.get("target_unit")
                if t is None:
                    continue
                tid = get_entity_id(t)
                if tid in seen_targets:
                    continue
                seen_targets.add(tid)
                touched_targets.append(t)
        except Exception:
            touched_targets = []
        
        # Begin attack resolution window(s) for targets (so attached leaders don't separate mid-sequence)
        # Publish a reaction window for defensive stratagems (e.g. GO TO GROUND) right after targets are selected.
        try:
            if weapon_declarations and hasattr(self, "get_parent_army") and self.get_parent_army() is not None:
                game = getattr(self.get_parent_army().player, "game", None)
                if game is not None and hasattr(game, "event_system"):
                    if touched_targets:
                        game.event_system.publish(
                            "shooting_targets_selected",
                            attacking_unit=self,
                            target_units=list(touched_targets),
                            weapon_declarations=list(weapon_declarations),
                        )
        except Exception:
            pass

        selected_to_shoot_charge_reroll_source = ""
        can_apply_selected_to_shoot_charge_reroll = False
        try:
            if (not out_of_phase) and self._is_controlling_players_shooting_phase():
                rule = self.get_selected_to_shoot_charge_reroll_rule()
                if rule:
                    can_apply_selected_to_shoot_charge_reroll = True
                    selected_to_shoot_charge_reroll_source = str(rule.get("source", "") or "")
        except Exception:
            pass

        # Selected-to-shoot rerolls (model-specific, once each for hit/wound/damage).
        try:
            selected_models = {}
            for decl in weapon_declarations:
                for m in list(decl.get("models") or []):
                    if m is None:
                        continue
                    try:
                        if not getattr(m, "is_alive", False):
                            continue
                    except Exception:
                        continue
                    selected_models[get_entity_id(m)] = m
            if selected_models:
                self.grant_selected_to_shoot_rerolls_for_models(list(selected_models.values()))
                self.grant_selected_to_action_reroll_choice_for_models(list(selected_models.values()), action="shoot")
                try:
                    from ...rules.psychic_communion import apply_psychic_communion_on_selected_to_shoot
                    phase_name = ""
                    try:
                        if game is not None:
                            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    except Exception:
                        phase_name = ""
                    apply_psychic_communion_on_selected_to_shoot(
                        self,
                        selected_models=list(selected_models.values()),
                        phase_name=phase_name or None,
                    )
                except Exception:
                    pass
        except Exception:
            pass

        try:
            for t in list(touched_targets or []):
                if hasattr(t, "begin_attack_resolution"):
                    t.begin_attack_resolution()
        except Exception:
            touched_targets = list(touched_targets or [])

        # Interactive dice roll mode: queue attack sequences after bookkeeping and return.
        if interactive_mode:
            try:
                mgr = getattr(game, "attack_manager", None)
                if mgr is not None:
                    queued = mgr.queue_attack_declarations(game, weapon_declarations, out_of_phase=out_of_phase)
                    if queued and can_apply_selected_to_shoot_charge_reroll and len(touched_targets or []) == 1:
                        try:
                            self._record_selected_to_shoot_charge_reroll_target(
                                touched_targets[0],
                                game=game,
                                source=selected_to_shoot_charge_reroll_source,
                            )
                        except Exception:
                            pass
                    return bool(queued)
            except Exception:
                return False

        killing_models_by_target: dict = {}
        attack_context = {
            "pending_mortal_wounds": {},
            "defer_mortal_wounds": True,
            "hit_models_by_target_weapon": hit_models_by_target_weapon,
            "hit_models_by_target_psychic": hit_models_by_target_psychic,
            "killing_models_by_target": killing_models_by_target,
        }
        remaining_by_target: dict[str, dict] = {}
        for decl in weapon_declarations:
            t = decl.get("target_unit")
            if t is None:
                continue
            tid = get_entity_id(t)
            entry = remaining_by_target.get(tid)
            if entry is None:
                remaining_by_target[tid] = {"unit": t, "count": 1}
            else:
                entry["count"] = int(entry.get("count", 0) or 0) + 1

        # Execute each weapon declaration
        for declaration in weapon_declarations:
            weapon_profile = declaration['weapon_profile']
            target_unit = declaration['target_unit']
            models_with_weapon = declaration['models']
            weapon_instance = declaration.get('weapon_instance', None)
            linked_fire_origin_unit = declaration.get('linked_fire_origin_unit', None)
            linked_fire_mode = declaration.get('linked_fire_mode', None)
            if target_unit is None and bool(getattr(weapon_profile, "is_plasma_warhead", lambda: False)()):
                weapon_attacks = self._resolve_plasma_warhead_declaration(
                    weapon_profile,
                    models_with_weapon,
                    game_map,
                    hit_tracker=hit_tracker,
                    hit_models_by_target=hit_models_by_target,
                    attack_tracker=attack_tracker,
                    attack_context=attack_context,
                    out_of_phase=out_of_phase,
                    weapon_instance=weapon_instance,
                )
                successful_attacks += weapon_attacks
                continue
            try:
                # Validate this declaration
                validation = self._validate_shooting_declaration(
                    weapon_profile,
                    target_unit,
                    models_with_weapon,
                    game_map,
                    linked_fire_origin_unit=linked_fire_origin_unit,
                    linked_fire_mode=linked_fire_mode,
                )
                if not validation['valid']:
                    logger.info(f"{self.name} - {weapon_profile.name}: {validation['reason']}")
                    continue

                # Execute attacks with this weapon
                weapon_attacks = self._execute_weapon_attacks(
                    weapon_profile,
                    target_unit,
                    models_with_weapon,
                    game_map,
                    weapon_instance,
                    hit_tracker=hit_tracker,
                    hit_models_by_target=hit_models_by_target,
                    attack_tracker=attack_tracker,
                    attack_context=attack_context,
                    linked_fire_origin_unit=linked_fire_origin_unit,
                    linked_fire_mode=linked_fire_mode,
                )
                successful_attacks += weapon_attacks
            finally:
                if target_unit is not None:
                    tid = get_entity_id(target_unit)
                    entry = remaining_by_target.get(tid)
                    if entry is not None:
                        entry["count"] = int(entry.get("count", 0) or 0) - 1
                        if entry["count"] <= 0:
                            self._resolve_pending_attack_mortal_wounds(attack_context, entry["unit"], game_map=game_map)

        try:
            game_for_effect = None
            try:
                game_for_effect = self.get_parent_army().player.game
            except Exception:
                game_for_effect = None
            if can_apply_selected_to_shoot_charge_reroll and successful_attacks > 0:
                actual_targets = [t for t, c in (attack_tracker or {}).items() if int(c or 0) > 0]
                if len(actual_targets) == 1:
                    self._record_selected_to_shoot_charge_reroll_target(
                        actual_targets[0],
                        game=game_for_effect,
                        source=selected_to_shoot_charge_reroll_source,
                    )
        except Exception:
            pass

        try:
            game = self.get_parent_army().player.game
            if game is not None and hasattr(game, "event_system"):
                game.event_system.publish(
                    "unit_shooting_resolved",
                    attacker_unit=self,
                    hits_by_target=dict(hit_tracker),
                    hit_models_by_target=dict(hit_models_by_target),
                    killing_models_by_target=dict(killing_models_by_target),
                    hit_models_by_target_weapon=dict(hit_models_by_target_weapon),
                    hit_models_by_target_psychic=dict(hit_models_by_target_psychic),
                )
        except Exception:
            pass
            
        # Report shooting results
        if successful_attacks > 0:
            logger.info(f"{self.name} completed shooting with {successful_attacks} attacks executed")
            try:
                from ...utility.event_bus import append_action
                pn = self.get_parent_army().player
                append_action(pn, f"{self.name} completed shooting: {successful_attacks} attacks")
            except Exception:
                pass
            
            # Check if target unit was destroyed
            for declaration in weapon_declarations:
                target_unit = declaration['target_unit']
                if not target_unit.is_alive():
                    logger.info(f"{target_unit.name} has been destroyed!")
        else:
            logger.error(f"{self.name} failed to execute any attacks")
            
        # End attack resolution window(s) and resolve pending separations (now that this unit is done attacking).
        try:
            for t in touched_targets:
                if hasattr(t, "end_attack_resolution"):
                    t.end_attack_resolution(game_map=game_map)
        except Exception:
            pass
        self._resolve_pending_horrors_split(game_map=game_map)

        # Clear BGNT snapshot to avoid leaking state into future activations.
        try:
            delattr(self, "_bgnt_locked_at_target_selection")
        except Exception:
            pass

        # Clear selected-to-shoot reroll allowances once this shooting sequence is resolved.
        try:
            self.clear_selected_to_shoot_rerolls()
        except Exception:
            pass
        try:
            self.clear_selected_to_action_reroll_choice(action="shoot")
        except Exception:
            pass

        return successful_attacks > 0

    @staticmethod
    def _ctan_power_parse_number_token(token: object) -> Optional[int]:
        raw = str(token or "").strip().lower()
        if not raw:
            return None
        if raw.isdigit():
            return int(raw)
        words = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
        }
        return words.get(raw)

    def _is_ctan_power_profile(self, profile) -> bool:
        if profile is None:
            return False
        is_ctan = getattr(profile, "is_ctan_power", None)
        if callable(is_ctan):
            return bool(is_ctan())
        keywords = list(getattr(profile, "get_keywords", lambda: [])() or [])
        lowered = [str(keyword or "").lower() for keyword in keywords]
        return "c'tan power" in lowered

    def _ctan_power_profile_key(self, profile) -> str:
        parent = getattr(profile, "parent_wargear", None)
        if parent is not None:
            parent_id = str(getattr(parent, "id", "") or getattr(parent, "_id", "")).strip()
            if parent_id:
                return f"wargear:{parent_id}"
            parent_name = str(getattr(parent, "name", "") or "").strip().lower()
            if parent_name:
                return f"wargear_name:{parent_name}"
        return f"profile_name:{str(getattr(profile, 'name', '') or '').strip().lower()}"

    def _has_powers_of_ctan_ability(self) -> bool:
        cache = getattr(self, "_ability_cache", None)
        cache_key = "powers_of_ctan_ability"
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache[cache_key])

        def _normalize(text: object) -> str:
            norm = str(text or "").replace("\u2019", "'").lower()
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            return re.sub(r"\s+", " ", norm).strip()

        def _is_powers_of_ctan(text: object) -> bool:
            norm = _normalize(text)
            return "powers of the c tan" in norm

        members = [self]
        get_members = getattr(self, "get_attached_unit_members", None)
        if callable(get_members):
            members = list(get_members() or []) or [self]
        found = False
        for member in members:
            for ability in list(getattr(member, "possible_abilities", []) or []):
                name = ability if isinstance(ability, str) else getattr(ability, "name", "")
                desc = "" if isinstance(ability, str) else getattr(ability, "description", "")
                if _is_powers_of_ctan(name) or _is_powers_of_ctan(desc):
                    found = True
                    break
            if found:
                break
            for ability in list(getattr(member, "abilities", []) or []):
                name = ability if isinstance(ability, str) else getattr(ability, "name", "")
                desc = "" if isinstance(ability, str) else getattr(ability, "description", "")
                if _is_powers_of_ctan(name) or _is_powers_of_ctan(desc):
                    found = True
                    break
            if found:
                break
            datasheet = getattr(member, "_datasheet", None)
            for ability in list(getattr(datasheet, "datasheets_abilities", []) or []):
                if isinstance(ability, dict):
                    name = str(ability.get("name", "") or "")
                    desc = str(ability.get("description", "") or "")
                else:
                    name = str(getattr(ability, "name", "") or "")
                    desc = str(getattr(ability, "description", "") or "")
                if _is_powers_of_ctan(name) or _is_powers_of_ctan(desc):
                    found = True
                    break
            if found:
                break

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = bool(found)
        self._ability_cache = cache
        return bool(found)

    def _ctan_power_active_wounded_limit(self) -> Optional[int]:
        model = None
        for candidate in list(getattr(self, "models", []) or []):
            if bool(getattr(candidate, "is_alive", False)):
                model = candidate
                break
        if model is None:
            return None

        current_wounds = int(getattr(model, "wounds", 0) or 0)
        if current_wounds <= 0:
            return None

        descriptions = []
        desc = getattr(self, "damaged_profile_desc", None)
        if isinstance(desc, str) and desc.strip():
            descriptions.append(desc)
        datasheet = getattr(self, "_datasheet", None)
        ds_desc = getattr(datasheet, "damaged_description", None) if datasheet is not None else None
        if isinstance(ds_desc, str) and ds_desc.strip():
            descriptions.append(ds_desc)

        for raw_desc in descriptions:
            text = str(raw_desc or "").replace("\u2019", "'").lower()
            range_match = re.search(r"while this model has\s*(\d+)\s*-\s*(\d+)\s*wounds remaining", text)
            if range_match is None:
                continue
            low = int(range_match.group(1))
            high = int(range_match.group(2))
            if not (low <= current_wounds <= high):
                continue
            select_match = re.search(
                r"can only select\s+(\d+|one|two|three|four|five)\s+of\s+(?:the\s+)?c[' ]?tan powers weapons",
                text,
            )
            if select_match is None:
                continue
            parsed = self._ctan_power_parse_number_token(select_match.group(1))
            if parsed is not None:
                return int(parsed)
        return None

    def get_ctan_power_selection_limit(self) -> int:
        if not self._has_powers_of_ctan_ability():
            return 0
        wounded_limit = self._ctan_power_active_wounded_limit()
        if wounded_limit is not None and wounded_limit > 0:
            return int(wounded_limit)
        return 2

    def validate_ctan_power_selection(self, weapon_declarations: List[dict]) -> tuple[bool, str]:
        limit = self.get_ctan_power_selection_limit()
        if limit <= 0:
            return True, ""
        selected: dict[str, object] = {}
        for declaration in list(weapon_declarations or []):
            profile = declaration.get("weapon_profile")
            if not self._is_ctan_power_profile(profile):
                continue
            key = self._ctan_power_profile_key(profile)
            if key not in selected:
                selected[key] = profile
        if len(selected) <= limit:
            return True, ""
        return (
            False,
            f"Powers of the C'tan: select up to {int(limit)} different C'tan Powers weapons before resolving shooting.",
        )


    def _validate_shooting_declaration(self, weapon_profile, target_unit, models_with_weapon, game_map, *, linked_fire_origin_unit=None, linked_fire_mode=None) -> dict:
        """Validate a shooting declaration"""
        # Check if target is an enemy unit
        if target_unit.get_parent_army() == self.get_parent_army():
            return {"valid": False, "reason": "Cannot target friendly units"}

        # Check if target is alive
        if not target_unit.is_alive():
            return {"valid": False, "reason": "Target unit is destroyed"}

        # Check if unit can shoot after advancing
        if self.round_state.advanced_this_round:
            # Unit method already checks both weapon-specific and unit-specific abilities
            if not self.can_shoot_after_advance(weapon_profile):
                return {"valid": False, "reason": "Unit advanced and cannot shoot with this weapon"}

        # Check if unit can shoot after falling back
        if self.round_state.fell_back_this_round:
            if not self.can_shoot_after_fall_back(weapon_profile):
                return {"valid": False, "reason": "Unit fell back and cannot shoot with this weapon"}

        # Thrill Seekers: extra target restrictions when advancing or falling back
        game = None
        try:
            game = self.get_parent_army().player.game
        except Exception:
            game = None
        reason = self._thrill_seekers_restriction_reason(target_unit, game)
        if reason:
            return {"valid": False, "reason": reason}

        # Check if any models can actually shoot this weapon at the target
        models_in_range = []
        for model in models_with_weapon:
            if not model.is_alive:
                continue

            if bool(getattr(getattr(self, "round_state", None), "fell_back_this_round", False)):
                if not self.can_shoot_after_fall_back(weapon_profile, model=model):
                    continue

            # Check if this model has the weapon
            has_weapon = False
            for wargear in model.wargear:
                if weapon_profile.parent_wargear == wargear:
                    has_weapon = True
                    break

            if not has_weapon:
                continue

            # ONE SHOT: weapons with this keyword can only be used once per battle (per model).
            try:
                if getattr(weapon_profile, "is_one_shot", lambda: False)():
                    key = getattr(weapon_profile, "one_shot_key", lambda: "")()
                    used = getattr(model, "_one_shot_used", set())
                    if key and key in used:
                        continue
            except Exception:
                # If anything goes wrong, do not block the shot.
                pass

        # Check range and line of sight (use origin unit for Linked Fire/Infernal Puppeteer if provided)
        if self._can_model_shoot_weapon_at_target(model, weapon_profile, target_unit, game_map, origin_unit=linked_fire_origin_unit):
            models_in_range.append(model)

        if not models_in_range:
            return {"valid": False, "reason": "No models in range or line of sight"}

        return {"valid": True, "reason": "Valid shooting declaration"}

    def _resolve_plasma_warhead_declaration(
        self,
        weapon_profile,
        models_with_weapon,
        game_map,
        *,
        hit_tracker=None,
        hit_models_by_target=None,
        attack_tracker: Optional[dict] = None,
        attack_context: Optional[dict] = None,
        out_of_phase: bool = False,
        weapon_instance=None,
    ) -> int:
        if weapon_profile is None or game_map is None:
            return 0
        if not models_with_weapon:
            return 0

        eligible_models = []
        one_shot_key = ""
        if getattr(weapon_profile, "is_one_shot", lambda: False)():
            one_shot_key = getattr(weapon_profile, "one_shot_key", lambda: "")()
        for model in models_with_weapon:
            if not getattr(model, "is_alive", False):
                continue
            if one_shot_key:
                used = getattr(model, "_one_shot_used", set())
                if one_shot_key in used:
                    continue
            if not self._model_has_weapon_profile(model, weapon_profile):
                continue
            eligible_models.append(model)

        if not eligible_models:
            return 0

        can_shoot_fn = getattr(weapon_profile, "can_shoot_plasma_warhead", None)
        if callable(can_shoot_fn):
            can_shoot, reason = can_shoot_fn(eligible_models[0], out_of_phase=out_of_phase)
            if not can_shoot:
                logger.info(f"{self.name} - {weapon_profile.name}: {reason}")
                return 0

        army = self.get_parent_army()
        deathstrike_mgr = getattr(army, "deathstrike", None)
        if deathstrike_mgr is None:
            logger.info(f"{self.name} - {weapon_profile.name}: Deathstrike manager missing")
            return 0
        from ...utility.entity_ids import get_entity_id
        unit_id = get_entity_id(self)
        marker_pos = deathstrike_mgr.get_marker_position(unit_id)
        if marker_pos is None:
            logger.info(f"{self.name} - {weapon_profile.name}: No Deathstrike marker")
            return 0

        from ...utility.aura_utils import get_units_within_range_of_point_3d
        all_units = list(getattr(game_map, "units", []) or [])
        units_in_aoe = get_units_within_range_of_point_3d(
            marker_pos,
            6.0,
            all_units,
            use_attached_aggregate=True,
        )

        if not units_in_aoe:
            for model in eligible_models:
                self._mark_one_shot_used(model, one_shot_key)
            deathstrike_mgr.mark_deathstrike_fired(unit_id)
            logger.info(f"{self.name} - {weapon_profile.name}: No units within 6\" of marker")
            return 0

        successful_attacks = 0
        for target_unit in units_in_aoe:
            if not getattr(target_unit, "is_alive", lambda: False)():
                continue
            successful_attacks += self._execute_weapon_attacks(
                weapon_profile,
                target_unit,
                eligible_models,
                game_map,
                weapon_instance=weapon_instance,
                hit_tracker=hit_tracker,
                hit_models_by_target=hit_models_by_target,
                attack_tracker=attack_tracker,
                attack_context=attack_context,
                skip_one_shot=True,
                skip_target_checks=True,
            )
            if attack_context is not None:
                self._resolve_pending_attack_mortal_wounds(attack_context, target_unit, game_map=game_map)

        for model in eligible_models:
            self._mark_one_shot_used(model, one_shot_key)
        deathstrike_mgr.mark_deathstrike_fired(unit_id)
        return successful_attacks
    

    def _can_model_shoot_weapon_at_target(self, model, weapon_profile, target_unit, game_map, *, origin_unit=None) -> bool:
        """Check if a specific model can shoot a weapon at a target

        Args:
            model: The model shooting
            weapon_profile: The weapon being used
            target_unit: The target unit
            game_map: The game map
            origin_unit: Optional origin unit for Linked Fire (measure range/LOS from this unit instead of bearer)
        """
        # INDIRECT FIRE + TORRENT: Torrent weapons cannot be used "via Indirect Fire" when no target models are visible.
        # Practical enforcement: if a weapon has both keywords, require visibility to at least one target model.
        try:
            if weapon_profile.is_indirect_fire() and weapon_profile.is_torrent():
                if not self._attacking_unit_has_any_los_to_target_unit(target_unit, game_map):
                    return False
        except Exception:
            # If anything goes wrong, be conservative and require LOS for Torrent+Indirect weapons.
            try:
                if weapon_profile.is_indirect_fire() and weapon_profile.is_torrent():
                    if not self._attacking_unit_has_any_los_to_target_unit(target_unit, game_map):
                        return False
            except Exception:
                pass

        # Formless Horror: if this unit is blocked from targeting this unit this phase, disallow.
        try:
            game = None
            try:
                game = getattr(self.get_parent_army().player, "game", None)
            except Exception:
                game = None
            if self._formless_horror_target_blocked(target_unit, game=game):
                return False
        except Exception:
            pass

        # Tau Empire (Mont'ka): Focused Fire target lock.
        try:
            root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
        except Exception:
            root = self
        try:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("tau_focused_fire_active"):
                apply_lock = True
                effect_phase = str(sr.get("tau_focused_fire_expires_phase", "") or "").strip().upper()
                owner_id = str(sr.get("tau_focused_fire_turn_owner", "") or "")
                try:
                    effect_turn = int(sr.get("tau_focused_fire_turn", 0) or 0)
                except Exception:
                    effect_turn = 0
                game = None
                current_phase = ""
                current_owner = ""
                current_turn = 0
                try:
                    game = getattr(self.get_parent_army().player, "game", None)
                except Exception:
                    game = None
                if game is not None:
                    try:
                        current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    except Exception:
                        current_phase = ""
                    try:
                        current_turn = int(getattr(game, "turn", 0) or 0)
                    except Exception:
                        current_turn = 0
                    try:
                        current_player = getattr(game, "get_current_player", lambda: None)()
                        current_owner = str(getattr(current_player, "id", "") or "")
                    except Exception:
                        current_owner = ""
                if effect_phase and current_phase and current_phase != effect_phase:
                    apply_lock = False
                if owner_id and current_owner and owner_id != current_owner:
                    apply_lock = False
                if effect_turn and current_turn and effect_turn != current_turn:
                    apply_lock = False
                target_id = str(sr.get("tau_focused_fire_target_id", "") or "")
                if apply_lock and target_id:
                    try:
                        target_root = target_unit.get_attached_unit_root()
                    except Exception:
                        target_root = target_unit
                    current_target_id = str(get_entity_id(target_root) or "")
                    if current_target_id and current_target_id != target_id:
                        return False
        except Exception:
            pass

        # Genestealer Cults (Host of Ascension): Coordinated Trap target lock.
        try:
            root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
        except Exception:
            root = self
        try:
            game = getattr(self.get_parent_army().player, "game", None)
        except Exception:
            game = None
        try:
            lock_check = getattr(root, "_gsc_coordinated_trap_target_locked_to", None)
            if callable(lock_check) and not bool(lock_check(target_unit, game=game)):
                return False
        except Exception:
            pass

        # Genestealer Cults (Brood Brother Auxilia): Integrated Tactics target lock.
        lock_check = getattr(root, "_gsc_integrated_tactics_target_locked_to", None)
        if callable(lock_check) and not bool(lock_check(target_unit, game=game)):
            return False

        # TARGET LEGALITY: Locked in Combat targeting restrictions (10e).
        # - Units that are Locked in Combat normally cannot be selected as targets of ranged attacks.
        # - Exception: in the controlling player's Shooting phase, VEHICLE/MONSTER units can be targeted even while Locked.
        # - Pistols can target units within Engagement Range of the shooter (own combat), enforced here.
        # - BGNT also allows a VEHICLE/MONSTER (in its controlling player's Shooting phase) to target enemy units
        #   it is within Engagement Range of (i.e., shoot into its own combat), subject to BLAST restriction.
        target_locked = Unit._is_unit_locked_in_combat(target_unit, game_map)
        weapon_name = str(getattr(getattr(weapon_profile, "parent_wargear", None), "name", "") or "").strip().lower()
        has_siege_shield = False
        has_siege_shield_fn = getattr(self, "has_siege_shield", None)
        if callable(has_siege_shield_fn):
            try:
                has_siege_shield = bool(has_siege_shield_fn())
            except Exception:
                has_siege_shield = False
        is_siege_shield_demolisher = has_siege_shield and ("demolisher cannon" in weapon_name)
        ficklefire_active = False
        try:
            if hasattr(self, "_is_ficklefire_active"):
                ficklefire_active = bool(self._is_ficklefire_active())
        except Exception:
            ficklefire_active = False
        fortification_only = False
        if target_locked:
            try:
                fortification_only = bool(target_unit.is_only_within_enemy_fortifications(game_map, enemy_unit=self))
            except Exception:
                fortification_only = False
        if target_locked and not fortification_only and ficklefire_active:
            engaged_with_other = False
            try:
                shooter_root = self.get_attached_unit_root()
            except Exception:
                shooter_root = self
            try:
                for friendly in game_map.get_friendly_units(self):
                    try:
                        root = friendly.get_attached_unit_root()
                    except Exception:
                        root = friendly
                    if root is None:
                        continue
                    if shooter_root is not None and root is shooter_root:
                        continue
                    try:
                        if not root.is_alive() or not getattr(root, "deployed", True):
                            continue
                    except Exception:
                        continue
                    if game_map.is_within_engagement_range(root, target_unit):
                        engaged_with_other = True
                        break
            except Exception:
                engaged_with_other = True
            if not engaged_with_other:
                target_locked = False
        if target_locked and not fortification_only:
            shooter_in_er_of_target = game_map.is_within_engagement_range(self, target_unit)
            if ficklefire_active:
                shooter_in_er_of_target = False
            if weapon_profile.is_pistol():
                if not shooter_in_er_of_target:
                    return False
            else:
                in_phase = self._is_controlling_players_shooting_phase()
                if shooter_in_er_of_target:
                    # BGNT: shoot into own combat (target is in ER of this unit) in-phase.
                    if not ((self.is_vehicle or self.is_monster) and in_phase):
                        return False
                else:
                    # BGNT target exception: target is a VEHICLE/MONSTER and shooter is in its shooting phase.
                    if not ((target_unit.is_vehicle or target_unit.is_monster) and in_phase):
                        return False

        # BLAST restriction supersedes BGNT targeting:
        # Blast weapons cannot target a unit that is within Engagement Range of any friendly unit (relative to the shooter).
        if weapon_profile.is_blast():
            get_shooter_root = getattr(self, "get_attached_unit_root", None)
            shooter_root = get_shooter_root() if callable(get_shooter_root) else self
            siege_shield_override = (
                is_siege_shield_demolisher
                and self._is_controlling_players_shooting_phase()
                and game_map.is_within_engagement_range(self, target_unit)
            )
            for friendly in game_map.get_friendly_units(self):
                if not friendly.is_alive() or not getattr(friendly, "deployed", True):
                    continue
                get_friendly_root = getattr(friendly, "get_attached_unit_root", None)
                friendly_root = get_friendly_root() if callable(get_friendly_root) else friendly
                if ficklefire_active:
                    if shooter_root is not None and friendly_root is shooter_root:
                        continue
                else:
                    if siege_shield_override and shooter_root is not None and friendly_root is shooter_root:
                        # Siege Shield allows Demolisher Cannon shots into this model's own engagement.
                        continue
                if game_map.is_within_engagement_range(friendly, target_unit):
                    return False

        # Linked Fire: measure range and LOS from origin unit models instead of bearer
        # When origin_unit is provided, use its models for range/LOS measurement
        measuring_models = [model]  # Default: measure from the shooting model
        if origin_unit is not None:
            # Use origin unit's models for measurement
            measuring_models = [m for m in origin_unit.models if getattr(m, "is_alive", False)]
            if not measuring_models:
                return False  # Origin unit has no alive models

        # Check range using base-to-base closest-point distance (not centroid-to-centroid, not model height)
        min_distance = float('inf')
        target_models = target_unit.get_models_for_collision()
        from ...utility.aura_utils import distance_between_models_bases_3d
        for measuring_model in measuring_models:
            for target_model in target_models:
                if not target_model.is_alive:
                    continue
                distance = float(distance_between_models_bases_3d(measuring_model, target_model))
                min_distance = min(min_distance, distance)

        effective_max = weapon_profile.range.max
        try:
            if hasattr(weapon_profile, "_effective_range_max"):
                effective_max = weapon_profile._effective_range_max(model)
        except Exception:
            effective_max = weapon_profile.range.max
        if min_distance > effective_max:
            return False

        # Check line of sight (INDIRECT FIRE weapons can target without LOS)
        # For Linked Fire, check LOS from origin unit models
        has_los = False
        try:
            if not getattr(weapon_profile, "is_indirect_fire", lambda: False)():
                for measuring_model in measuring_models:
                    if self._has_line_of_sight_to_target(measuring_model, target_unit, game_map):
                        has_los = True
                        break
                if not has_los:
                    return False
            else:
                has_los = True  # Indirect fire doesn't need LOS
        except Exception:
            # If anything goes wrong determining indirect/LOS, fall back to requiring LOS
            for measuring_model in measuring_models:
                if self._has_line_of_sight_to_target(measuring_model, target_unit, game_map):
                    has_los = True
                    break
            if not has_los:
                return False

        try:
            limit, _sources = target_unit.get_ranged_targeting_restriction(game_map=game_map)
            if limit is not None and min_distance > float(limit):
                return False
        except Exception:
            pass

        # Check engagement range restrictions
        if not self._can_shoot_while_engaged(model, weapon_profile, target_unit, game_map):
            return False

        return True

    def _model_has_weapon_profile(self, model, weapon_profile) -> bool:
        """Return True if the model has the specified weapon profile equipped."""
        for wargear in list(getattr(model, "wargear", []) or []):
            for profile in (getattr(wargear, "profiles", {}) or {}).values():
                if profile is weapon_profile:
                    return True
        return False

    def _mark_one_shot_used(self, model, key: str) -> None:
        if not key:
            return
        used = getattr(model, "_one_shot_used", set())
        if not isinstance(used, set):
            used = set()
        used.add(key)
        setattr(model, "_one_shot_used", used)

    def is_target_closest_eligible(
        self,
        model,
        weapon_profile,
        target_unit,
        game_map,
        *,
        max_distance: Optional[float] = None,
        require_keywords: Optional[set[str]] = None,
    ) -> bool:
        """Return True if target_unit is the closest eligible target for this model/weapon."""
        if model is None or weapon_profile is None or target_unit is None or game_map is None:
            return False

        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        required = None
        if require_keywords:
            try:
                required = {str(k or "").strip() for k in require_keywords if str(k or "").strip()}
            except Exception:
                required = None

        def _matches_required(unit) -> bool:
            if not required:
                return True
            for kw in required:
                try:
                    if unit.has_any_keyword(kw):
                        return True
                except Exception:
                    continue
            return False

        if not _matches_required(target_root):
            return False

        try:
            if not self._can_model_shoot_weapon_at_target(model, weapon_profile, target_root, game_map):
                return False
        except Exception:
            return False

        def _min_distance_to_unit(unit) -> Optional[float]:
            try:
                target_models = unit.get_models_for_collision()
            except Exception:
                target_models = list(getattr(unit, "models", []) or [])
            from ...utility.aura_utils import distance_between_models_bases_3d
            min_dist = float("inf")
            for tm in target_models:
                if not getattr(tm, "is_alive", False):
                    continue
                dist = float(distance_between_models_bases_3d(model, tm))
                if dist < min_dist:
                    min_dist = dist
            if min_dist == float("inf"):
                return None
            return min_dist

        target_dist = _min_distance_to_unit(target_root)
        if target_dist is None:
            return False
        if max_distance is not None and target_dist > max_distance:
            return False

        closest = None
        seen = set()
        for enemy_unit in game_map.get_enemy_units(self):
            try:
                root = enemy_unit.get_attached_unit_root()
            except Exception:
                root = enemy_unit
            if root is None:
                continue
            rid = get_entity_id(root)
            if rid in seen:
                continue
            seen.add(rid)
            try:
                if hasattr(root, "is_alive") and callable(root.is_alive) and not root.is_alive():
                    continue
            except Exception:
                pass
            try:
                if hasattr(root, "deployed") and not bool(getattr(root, "deployed", True)):
                    continue
            except Exception:
                pass
            try:
                if not self._can_model_shoot_weapon_at_target(model, weapon_profile, root, game_map):
                    continue
            except Exception:
                continue
            if not _matches_required(root):
                continue
            dist = _min_distance_to_unit(root)
            if dist is None:
                continue
            if max_distance is not None and dist > max_distance:
                continue
            if closest is None or dist < closest:
                closest = dist

        if closest is None:
            return False
        return target_dist <= closest + 1e-6

    def _attacking_unit_has_any_los_to_target_unit(self, target_unit, game_map) -> bool:
        """Return True if ANY model in this unit has LOS to ANY model in target_unit."""
        try:
            for m in self.models:
                if not getattr(m, "is_alive", False):
                    continue
                if self._has_line_of_sight_to_target(m, target_unit, game_map):
                    return True
        except Exception:
            pass
        return False
    

    def _has_line_of_sight_to_target(self, shooting_model, target_unit, game_map) -> bool:
        """Check if shooting model has line of sight to target unit.

        LOS exists if a line can be drawn from ANY point on the shooter's 3D volume
        to ANY point on the 3D volume of ANY model in the target unit without being
        blocked by terrain or enemy models. Friendly models are ignored for blocking.
        """
        # Late imports to avoid circulars
        from shapely.geometry import LineString

        def sample_model_points_3d(model: 'Model', perimeter_points: int = 8, z_levels: int = 3) -> list:
            base_shape = model.model_base.get_base_shape()
            # Ensure polygon exterior length > 0
            exterior = base_shape.exterior
            perimeter_samples = []
            if exterior.length > 0 and perimeter_points > 0:
                step = exterior.length / perimeter_points
                for i in range(perimeter_points):
                    p = exterior.interpolate(step * i)
                    perimeter_samples.append((p.x, p.y))
            # Always include centroid
            centroid = base_shape.centroid
            xy_points = [(centroid.x, centroid.y)] + perimeter_samples

            # Z samples: bottom, mid, top (minus tiny epsilon to stay within volume)
            z_bottom, z_top = model.model_base.volume_z_bounds()
            if z_levels <= 1:
                z_samples = [z_bottom + 0.01]
            elif z_levels == 2:
                z_samples = [z_bottom + 0.01, z_top - 0.01]
            else:
                z_mid = (z_bottom + z_top) / 2.0
                z_samples = [z_bottom + 0.01, z_mid, z_top - 0.01]

            points_3d = []
            for (x, y) in xy_points:
                for z in z_samples:
                    points_3d.append((x, y, z))
            return points_3d

        def is_segment_blocked(p0: tuple, p1: tuple, target_model: 'Model') -> bool:
            # Quick reject: degenerate line in XY projects to a point
            line2d = LineString([(p0[0], p0[1]), (p1[0], p1[1])])
            if line2d.length == 0:
                return False

            # Helper to compute z at param t along the 2D line
            def z_at_t(t: float) -> float:
                return p0[2] + t * (p1[2] - p0[2])

            # Terrain blocking (including special Ruins visibility rules)
            for terrain in getattr(game_map, 'terrain_features', []):
                footprint = getattr(terrain, 'footprint', None)
                # Special Ruins visibility handling
                is_ruins = hasattr(terrain, 'walls') and hasattr(terrain, 'openings') and footprint is not None
                if is_ruins and footprint is not None:
                    shooter_shape = shooting_model.model_base.get_base_shape()
                    target_shape = target_model.model_base.get_base_shape()
                    shooter_inside_any = footprint.intersects(shooter_shape)
                    target_inside_any = footprint.intersects(target_shape)
                    shooter_wholly_within = footprint.covers(shooter_shape)
                    shooter_is_aircraft = False
                    target_is_aircraft = False
                    shooter_is_towering = False
                    try:
                        shooter_is_aircraft = bool(getattr(shooting_model.parent_unit, "is_aircraft", False))
                        target_is_aircraft = bool(getattr(target_model.parent_unit, "is_aircraft", False))
                        shooter_is_towering = bool(getattr(shooting_model.parent_unit, "is_towering", False))
                    except Exception:
                        pass

                    # Aircraft always default to normal LOS: skip special ruins blocking
                    if shooter_is_aircraft or target_is_aircraft:
                        pass
                    else:
                    # If both models are outside this ruins and the footprint lies between them, LOS is blocked.
                        if not shooter_inside_any and not target_inside_any:
                            if line2d.intersects(footprint):
                                return True

                    # If shooter is inside this ruins but not wholly within and not towering, cannot see out
                        if shooter_inside_any and not shooter_wholly_within and not shooter_is_towering:
                            if not target_inside_any:
                                # Shooter partially within cannot see out of the ruins
                                return True

                    # Otherwise, visibility to/from/within ruins is determined normally below

                # If terrain has explicit walls/openings (e.g., ruins), treat walls as vertical blockers
                walls = getattr(terrain, 'walls', None)
                openings = getattr(terrain, 'openings', None)
                if walls:
                    for wall in walls:
                        wall_poly = wall.get('polygon')
                        if wall_poly is None:
                            continue
                        if not line2d.intersects(wall_poly):
                            continue
                        inter = line2d.intersection(wall_poly)
                        # Representative intersection point in XY
                        inter_pt = None
                        if inter.is_empty:
                            continue
                        if inter.geom_type == 'Point':
                            inter_pt = inter
                        elif inter.geom_type in ('LineString', 'MultiPoint', 'MultiLineString'):
                            # Take centroid for a representative point
                            inter_pt = inter.centroid
                        else:
                            inter_pt = inter.representative_point()

                        # Compute param t along line for z
                        t = line2d.project(inter_pt) / line2d.length if line2d.length > 0 else 0.0
                        # Ignore intersections at endpoints
                        if t <= 1e-6 or t >= 1.0 - 1e-6:
                            continue
                        z_here = z_at_t(t)
                        z_bottom = wall.get('z_bottom', 0.0)
                        z_top = wall.get('z_top', z_bottom)

                        if z_bottom <= z_here <= z_top:
                            # Check if an opening at this XY,Z allows LOS
                            allowed = False
                            if openings:
                                for op in openings:
                                    if not op.get('allows_los', False):
                                        continue
                                    op_poly = op.get('polygon')
                                    if op_poly is None:
                                        continue
                                    if not op_poly.contains(inter_pt):
                                        continue
                                    if op.get('z_bottom', -1e9) <= z_here <= op.get('z_top', 1e9):
                                        allowed = True
                                        break
                            if not allowed:
                                return True  # Blocked by wall without LOS opening
                else:
                    # Generic blocking by terrain footprint with height
                    footprint = getattr(terrain, 'footprint', None)
                    if footprint is None:
                        continue
                    if not line2d.intersects(footprint):
                        continue
                    inter = line2d.intersection(footprint)
                    if inter.is_empty:
                        continue
                    # Representative intersection point
                    if inter.geom_type == 'Point':
                        inter_pt = inter
                    elif inter.geom_type in ('LineString', 'MultiPoint', 'MultiLineString'):
                        inter_pt = inter.centroid
                    else:
                        inter_pt = inter.representative_point()
                    t = line2d.project(inter_pt) / line2d.length if line2d.length > 0 else 0.0
                    if t <= 1e-6 or t >= 1.0 - 1e-6:
                        continue
                    z_here = z_at_t(t)
                    # Determine vertical bounds
                    min_z, max_z = 0.0, 0.0
                    if hasattr(terrain, 'height'):
                        min_z, max_z = 0.0, getattr(terrain, 'height')
                    elif hasattr(terrain, 'rim_height'):
                        min_z, max_z = 0.0, getattr(terrain, 'rim_height')
                    elif hasattr(terrain, 'bounding_box') and isinstance(terrain.bounding_box, dict):
                        try:
                            min_z = terrain.bounding_box.get('min', (0, 0, 0))[2]
                            max_z = terrain.bounding_box.get('max', (0, 0, 0))[2]
                        except Exception:
                            min_z, max_z = 0.0, 2.0
                    else:
                        max_z = 2.0  # default obstacle height
                    if min_z <= z_here <= max_z:
                        return True

            # Enemy models blocking (ignore friendlies and ignore models in the target unit)
            for enemy_unit in game_map.get_enemy_units(self):
                if not enemy_unit.is_alive() or not enemy_unit.deployed:
                    continue
                if enemy_unit == target_unit:
                    continue
                for enemy_model in enemy_unit.models:
                    if not enemy_model.is_alive:
                        continue
                    enemy_poly = enemy_model.model_base.get_base_shape()
                    if not line2d.intersects(enemy_poly):
                        continue
                    inter = line2d.intersection(enemy_poly)
                    if inter.is_empty:
                        continue
                    if inter.geom_type == 'Point':
                        inter_pt = inter
                    elif inter.geom_type in ('LineString', 'MultiPoint', 'MultiLineString'):
                        inter_pt = inter.centroid
                    else:
                        inter_pt = inter.representative_point()
                    t = line2d.project(inter_pt) / line2d.length if line2d.length > 0 else 0.0
                    if t <= 1e-6 or t >= 1.0 - 1e-6:
                        continue
                    z_here = z_at_t(t)
                    em_z0, em_z1 = enemy_model.model_base.volume_z_bounds()
                    if em_z0 <= z_here <= em_z1:
                        return True

            return False

        # Validate inputs
        if shooting_model is None or target_unit is None or game_map is None:
            return False
        if not shooting_model.is_alive or not target_unit.is_alive():
            return False

        # Sample 3D points on shooter and on each target model; LOS if any pair is unblocked
        shooter_points = sample_model_points_3d(shooting_model, perimeter_points=8, z_levels=3)

        for target_model in target_unit.models:
            if not target_model.is_alive:
                continue
            target_points = sample_model_points_3d(target_model, perimeter_points=8, z_levels=3)
            for p0 in shooter_points:
                for p1 in target_points:
                    if not is_segment_blocked(p0, p1, target_model):
                        return True

        return False
    

    def _can_shoot_while_engaged(self, model, weapon_profile, target_unit, game_map) -> bool:
        """Check if model can shoot while engaged with other units"""
        # Check if unit is in engagement range
        is_engaged = any(game_map.is_within_engagement_range(self, enemy)
                        for enemy in game_map.get_enemy_units(self) if enemy.is_alive())
        
        if not is_engaged:
            return True

        if self._is_ficklefire_active():
            try:
                parent = getattr(weapon_profile, "parent_wargear", None)
                if parent is None or parent.is_ranged():
                    return True
            except Exception:
                return True
            
        # If engaged, check weapon type and target
        # PISTOL (10e):
        # - A unit can shoot with Pistols while within Engagement Range.
        # - When it does so, it must target an enemy unit it is within Engagement Range of.
        if weapon_profile.is_pistol():
            return game_map.is_within_engagement_range(self, target_unit)

        # VEHICLE / MONSTER (Big Guns Never Tire style behavior):
        # Only applies in the controlling player's Shooting phase.
        if self.is_vehicle or self.is_monster:
            if not self._is_controlling_players_shooting_phase():
                return False

            # BLAST restriction (friendly engagement) is enforced in _can_model_shoot_weapon_at_target.
            # Keep a small safety-net here too for direct callers.
            if weapon_profile.is_blast():
                weapon_name = str(getattr(getattr(weapon_profile, "parent_wargear", None), "name", "") or "").strip().lower()
                has_siege_shield = False
                has_siege_shield_fn = getattr(self, "has_siege_shield", None)
                if callable(has_siege_shield_fn):
                    try:
                        has_siege_shield = bool(has_siege_shield_fn())
                    except Exception:
                        has_siege_shield = False
                siege_shield_override = (
                    has_siege_shield
                    and ("demolisher cannon" in weapon_name)
                    and self._is_controlling_players_shooting_phase()
                    and game_map.is_within_engagement_range(self, target_unit)
                )
                get_shooter_root = getattr(self, "get_attached_unit_root", None)
                shooter_root = get_shooter_root() if callable(get_shooter_root) else self
                for friendly in game_map.get_friendly_units(self):
                    if not friendly.is_alive() or not getattr(friendly, "deployed", True):
                        continue
                    get_friendly_root = getattr(friendly, "get_attached_unit_root", None)
                    friendly_root = get_friendly_root() if callable(get_friendly_root) else friendly
                    if siege_shield_override and shooter_root is not None and friendly_root is shooter_root:
                        # Siege Shield allows Demolisher Cannon shots into this model's own engagement.
                        continue
                    if game_map.is_within_engagement_range(friendly, target_unit):
                        return False
            return True
            
        # Check if target is the unit we're engaged with
        if game_map.is_within_engagement_range(self, target_unit):
            return weapon_profile.is_pistol()
            
        # If target is different from engaged unit, only vehicles can shoot
        return False
    

    def _execute_weapon_attacks(
        self,
        weapon_profile,
        target_unit,
        models_with_weapon,
        game_map,
        weapon_instance=None,
        hit_tracker=None,
        hit_models_by_target=None,
        attack_tracker: Optional[dict] = None,
        attack_context: Optional[dict] = None,
        linked_fire_origin_unit=None,
        linked_fire_mode=None,
        skip_one_shot: bool = False,
        skip_target_checks: bool = False,
    ) -> int:
        """Execute attacks with a specific weapon profile

        Args:
            linked_fire_origin_unit: Optional origin unit for Linked Fire/Infernal Puppeteer (measure range/LOS from this unit)
        """
        successful_attacks = 0

        for model in models_with_weapon:
            if not model.is_alive:
                continue

            if bool(getattr(getattr(self, "round_state", None), "fell_back_this_round", False)):
                if not self.can_shoot_after_fall_back(weapon_profile, model=model):
                    continue

            active_profile = weapon_profile
            if getattr(active_profile, "is_bubblechukka", lambda: False)():
                roll = int(get_roll("D6") or 0)
                selected = active_profile.get_bubblechukka_profile_for_roll(roll)
                if selected is not None:
                    active_profile = selected
                    army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
                    player = getattr(army, "player", None)
                    if player is not None:
                        from ...utility.event_bus import append_dice
                        append_dice(player, f"Bubblechukka rolled {roll}: using {selected.name}")

            # ONE SHOT: prevent repeated use (per model)
            if not skip_one_shot and getattr(active_profile, "is_one_shot", lambda: False)():
                key = getattr(active_profile, "one_shot_key", lambda: "")()
                used = getattr(model, "_one_shot_used", set())
                if key and key in used:
                    continue

            # Check if this model can still shoot this weapon at this target (use origin unit for Linked Fire)
            if not skip_target_checks:
                if not self._can_model_shoot_weapon_at_target(model, active_profile, target_unit, game_map, origin_unit=linked_fire_origin_unit):
                    continue

            # Verify the model has this weapon
            has_weapon = self._model_has_weapon_profile(model, active_profile)
            
            if not has_weapon:
                continue
                
            # Execute the attack - each declaration represents exactly one weapon firing
            try:
                weapon_display = f"{active_profile.parent_wargear.name}"
                if weapon_instance:
                    weapon_display += f" #{weapon_instance}"

                # Attack count overrides (apply in precedence order)
                attacks_override = None
                attacks_override_note = None

                # Linked Fire: apply Attacks=1 override when using origin unit
                # This takes precedence over other overrides (applied first)
                mode = str(linked_fire_mode or "").strip().lower()
                if linked_fire_origin_unit is not None and mode == "linked_fire":
                    attacks_override = 1
                    attacks_override_note = "Linked Fire"
                    logger.info(f"{model.name} attacking with {weapon_display} (Linked Fire from {linked_fire_origin_unit.name})")
                elif linked_fire_origin_unit is not None and mode == "infernal_puppeteer":
                    logger.info(f"{model.name} attacking with {weapon_display} (Infernal Puppeteer from {linked_fire_origin_unit.name})")
                # Psychic Assassin: apply Attacks=6 override when targeting PSYKER
                # Only applies if no other override is already set
                elif active_profile.is_psychic_assassin() and target_unit.has_any_keyword("PSYKER"):
                    attacks_override = 6
                    attacks_override_note = "Psychic Assassin"
                    logger.info(f"{model.name} attacking with {weapon_display} (Psychic Assassin vs PSYKER)")
                else:
                    logger.info(f"{model.name} attacking with {weapon_display}")

                # Execute the attack using the weapon profile (pass game_map for cover/terrain context)
                try:
                    attack_result = active_profile.attack(
                        target_unit,
                        model,
                        game_map=game_map,
                        attack_context=attack_context,
                        attacks_override=attacks_override,
                        attacks_override_note=attacks_override_note,
                    )
                except TypeError as exc:
                    if "attack_context" in str(exc) or "attacks_override" in str(exc):
                        # Fallback for older attack signatures
                        attack_result = active_profile.attack(
                            target_unit, model, game_map=game_map
                        )
                    else:
                        raise
                if hit_tracker is not None:
                    try:
                        hits = int(getattr(attack_result, "total_hits", 0) or 0)
                    except Exception:
                        hits = 0
                    if hits > 0:
                        hit_tracker[target_unit] = int(hit_tracker.get(target_unit, 0) or 0) + hits
                        if hit_models_by_target is not None:
                            try:
                                hit_models_by_target.setdefault(target_unit, set()).add(model)
                            except Exception:
                                pass
                        try:
                            hit_by_weapon = None
                            if isinstance(attack_context, dict):
                                hit_by_weapon = attack_context.get("hit_models_by_target_weapon")
                            if isinstance(hit_by_weapon, dict):
                                weapon_name = ""
                                try:
                                    parent = getattr(active_profile, "parent_wargear", None)
                                    if parent is not None:
                                        weapon_name = str(getattr(parent, "name", "") or "")
                                except Exception:
                                    weapon_name = ""
                                if not weapon_name:
                                    weapon_name = str(getattr(active_profile, "name", "") or "")
                                weapon_key = self._normalize_keyword_phrase(weapon_name)
                                if weapon_key:
                                    target_map = hit_by_weapon.setdefault(target_unit, {})
                                    if isinstance(target_map, dict):
                                        target_map.setdefault(weapon_key, set()).add(model)
                        except Exception:
                            pass
                if attack_context is not None and target_unit is not None:
                    try:
                        kills = int(getattr(attack_result, "models_killed", 0) or 0)
                    except Exception:
                        kills = 0
                    if kills > 0 and isinstance(attack_context, dict):
                        kill_map = attack_context.get("killing_models_by_target")
                        if not isinstance(kill_map, dict):
                            kill_map = {}
                            attack_context["killing_models_by_target"] = kill_map
                        try:
                            kill_map.setdefault(target_unit, set()).add(model)
                        except Exception:
                            pass
                if attack_tracker is not None and target_unit is not None:
                    try:
                        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
                    except Exception:
                        target_root = target_unit
                    try:
                        attack_tracker[target_root] = int(attack_tracker.get(target_root, 0) or 0) + 1
                    except Exception:
                        pass
                # Count successful execution of the attack (not damage dealt)
                successful_attacks += 1

                # Mark ONE SHOT weapons as expended after firing (hit or miss).
                if not skip_one_shot and getattr(active_profile, "is_one_shot", lambda: False)():
                    key = getattr(active_profile, "one_shot_key", lambda: "")()
                    self._mark_one_shot_used(model, key)
            except Exception as e:
                logger.exception(f"Error executing attack with {weapon_profile.name}: {e}")
                # Don't increment successful_attacks if there was an exception
                
        return successful_attacks

    # Fight Phase Actions

    def pile_in_towards_enemies(self, game_map: 'Map') -> bool:
        logger.warning("WARN: Pile-in requires UI/controlled movement; legacy auto-move removed.")
        return False

    def _is_model_in_base_to_base_contact(self, model: 'Model', enemy_models: List['Model'], game_map: 'Map') -> bool:
        """Check if a model is in base-to-base (edge-to-edge) contact with any enemy model."""
        from ...utility.constants import BASE_CONTACT_EPSILON, ENGAGEMENT_RANGE_VERTICAL
        # Base-to-base contact is defined as bases touching (edge-to-edge ~= 0). We treat
        # anything within BASE_CONTACT_EPSILON as base contact to account for discretization.
        for enemy_model in enemy_models:
            from ...utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
            edge = float(horizontal_distance_between_bases_2d(model.model_base, enemy_model.model_base))
            vert = float(vertical_distance_between_bases(model.model_base, enemy_model.model_base))
            if edge <= BASE_CONTACT_EPSILON and vert <= ENGAGEMENT_RANGE_VERTICAL:
                return True
        return False
    

    def consolidate_towards_enemies(self, game_map: 'Map') -> bool:
        logger.warning("WARN: Consolidate requires UI/controlled movement; legacy auto-move removed.")
        return False

    def auto_blood_surge_move(self, game_map: 'Map', max_distance: float) -> bool:
        logger.warning("WARN: Blood Surge requires UI/controlled movement; legacy auto-move removed.")
        return False

    def take_battle_shock_test(self, current_turn: int = 1):
        """Takes a battle shock test.
        
        Args:
            current_turn: The current battle round number (used for status effect duration)
        """
        # Destroyed units do not take Battle-shock tests, and abilities cannot force a destroyed unit to test.
        try:
            alive_models = any(bool(getattr(m, "is_alive", True)) for m in (getattr(self, "models", []) or []))
        except Exception:
            alive_models = False
        if not alive_models:
            try:
                for u in list(getattr(self, "attached_leaders", []) or []):
                    if any(bool(getattr(m, "is_alive", True)) for m in (getattr(u, "models", []) or [])):
                        alive_models = True
                        break
            except Exception:
                alive_models = alive_models
        if not alive_models:
            return

        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("battle_shock_suppress_other_tests_phase"):
                phase_name = ""
                try:
                    army = self.get_parent_army()
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                except Exception:
                    phase_name = ""
                suppress_phase = str(sr.get("battle_shock_suppress_other_tests_phase", "") or "").strip().upper()
                if suppress_phase and phase_name and phase_name != suppress_phase:
                    sr.pop("battle_shock_suppress_other_tests_phase", None)
                    sr.pop("battle_shock_suppress_other_tests_source", None)
                    sr.pop("battle_shock_allow_suppressed_test", None)
                    self.special_rules = sr
                else:
                    allow = bool(sr.pop("battle_shock_allow_suppressed_test", False))
                    self.special_rules = sr
                    if not allow:
                        return
        except Exception:
            pass

        is_already_battle_shocked = bool(self.is_battle_shocked())

        # Resolve event system (best-effort; avoid crashing on partial test stubs).
        event_system = None
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        player = getattr(army, "player", None) if army is not None else None
        game = getattr(player, "game", None) if player is not None else None
        event_system = getattr(game, "event_system", None) if game is not None else None

        if event_system is not None:
            try:
                event_system.publish("battle_shock_test_started", unit=self)
            except Exception:
                pass
        shadow_ctx = None
        shadow_mod = 0
        try:
            from ...rules.shadow_of_chaos import ShadowOfChaosManager
            shadow_ctx = ShadowOfChaosManager.battle_shock_context(self, game=game)
            shadow_mod = int(getattr(shadow_ctx, "modifier", 0) or 0)
        except Exception:
            shadow_ctx = None
            shadow_mod = 0
        synapse_3d6 = False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        try:
            synapse_mgr = getattr(army, "synapse", None) if army is not None else None
        except Exception:
            synapse_mgr = None
        try:
            if synapse_mgr is not None and synapse_mgr.unit_in_synapse_range(self, game=game):
                synapse_3d6 = True
        except Exception:
            synapse_3d6 = False
        extra_mod = 0
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and "battle_shock_test_modifier" in sr:
                extra_mod = int(sr.get("battle_shock_test_modifier", 0) or 0)
                sr.pop("battle_shock_test_modifier", None)
                sr.pop("battle_shock_test_modifier_reasons", None)
                self.special_rules = sr
        except Exception:
            extra_mod = 0
        post_shoot_mod = 0
        try:
            post_shoot_mod = int(self._post_shoot_leadership_debuff_modifier(game))
        except Exception:
            post_shoot_mod = 0
        aura_mod = 0
        try:
            from ...utility.aura_effects import get_aura_battleshock_test_modifiers
            aura_mods = get_aura_battleshock_test_modifiers(self, game_map=getattr(game, "map", None))
            for val, _src in list(aura_mods or []):
                aura_mod += int(val)
        except Exception:
            aura_mod = 0
        # Core Stratagem: INSANE BRAVERY can make this unit automatically pass this test.
        # It is consumed on use (one-shot for the next Battle-shock test).
        auto_passed = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("auto_pass_next_battle_shock_test") is True:
                sr.pop("auto_pass_next_battle_shock_test", None)
                self.special_rules = sr
                passed = True
                auto_passed = True
            else:
                auto_passed = False
        except Exception:
            auto_passed = False

        icon_of_war_reroll_available = False
        if not auto_passed:
            try:
                icon_of_war_reroll_available = bool(self._icon_of_war_battle_shock_reroll_available())
            except Exception:
                icon_of_war_reroll_available = False
        carmine_reroll_available = False
        if not auto_passed:
            try:
                if self.has_any_keyword("ADEPTUS ASTARTES") and self._unit_within_carmine_reliquary_range():
                    carmine_reroll_available = True
            except Exception:
                carmine_reroll_available = False
        leadership_reroll_sources = []
        if not auto_passed:
            try:
                leadership_reroll_sources = list(self.leading_leadership_reroll_sources() or [])
            except Exception:
                leadership_reroll_sources = []
        if not auto_passed:
            try:
                checker = getattr(self, "_attached_unit_has_active_enhancement", None)
                has_proud = bool(
                    callable(checker)
                    and checker(
                        "enhancement_proud_and_vainglorious",
                        enhancement_id="000010018004",
                        enhancement_name="proud and vainglorious",
                    )
                )
            except Exception:
                has_proud = False
            if has_proud:
                seen = {str(s or "") for s in list(leadership_reroll_sources or [])}
                source_name = "Proud and Vainglorious"
                if source_name not in seen:
                    leadership_reroll_sources.append(source_name)
        if not auto_passed:
            try:
                army = self.get_parent_army()
            except Exception:
                army = None
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            tempered_sources_fn = (
                getattr(sm_mgr, "wrath_of_the_rock_tempered_in_battle_reroll_sources", None)
                if sm_mgr is not None
                else None
            )
            if callable(tempered_sources_fn):
                try:
                    tempered_sources = list(tempered_sources_fn(self, game=game) or [])
                except Exception:
                    tempered_sources = []
                if tempered_sources:
                    seen = {str(s or "") for s in list(leadership_reroll_sources or [])}
                    for source in tempered_sources:
                        source_name = str(source or "")
                        if not source_name or source_name in seen:
                            continue
                        seen.add(source_name)
                        leadership_reroll_sources.append(source_name)
        if not auto_passed:
            try:
                from ...utility.aura_effects import get_aura_battleshock_test_reroll_sources
                aura_sources = list(get_aura_battleshock_test_reroll_sources(self, game_map=getattr(game, "map", None)) or [])
            except Exception:
                aura_sources = []
            if aura_sources:
                seen = {str(s or "") for s in list(leadership_reroll_sources or [])}
                for src in aura_sources:
                    src_name = str(src or "")
                    if not src_name or src_name in seen:
                        continue
                    seen.add(src_name)
                    leadership_reroll_sources.append(src_name)
        leadership_reroll_available = bool(leadership_reroll_sources)

        if not auto_passed:
            total_mod = int(shadow_mod) + int(extra_mod) + int(post_shoot_mod) + int(aura_mod)
            dice_count = 3 if synapse_3d6 else 2
            dice_expr = "3D6" if synapse_3d6 else "2D6"
            leadership_value = None
            def _safe_leadership() -> int:
                try:
                    return int(self.leadership)
                except Exception:
                    try:
                        return int(getattr(self, "_leadership", 0) or 0)
                    except Exception:
                        return 0

            # Dice roll flow (server-authoritative when game exists)
            try:
                if game is not None and bool(getattr(game, "is_authoritative", True)):
                    if leadership_value is None:
                        leadership_value = _safe_leadership()
                    from ...engine.roll_utils import command_reroll_available
                    from ...utility.entity_ids import get_entity_id
                    reroll_rules = []
                    if icon_of_war_reroll_available:
                        reroll_rules.append(
                            {
                                "action_id": "reroll_battle_shock_icon_of_war",
                                "label": "Re-roll Battle-shock (Icon of War)",
                                "mode": "all",
                                "source": "rule",
                            }
                        )
                    if carmine_reroll_available:
                        reroll_rules.append(
                            {
                                "action_id": "reroll_battle_shock_carmine",
                                "label": "Re-roll Battle-shock (Carmine Reliquary)",
                                "mode": "all",
                                "source": "rule",
                            }
                        )
                    if leadership_reroll_available:
                        label = "Re-roll Leadership test"
                        if leadership_reroll_sources:
                            label = f"Re-roll Leadership ({' / '.join(sorted(leadership_reroll_sources))})"
                        reroll_rules.append(
                            {
                                "action_id": "reroll_leadership_test",
                                "label": label,
                                "mode": "all",
                                "source": "ability",
                            }
                        )
                    fixed_dice = []
                    try:
                        mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                        if mgr is not None and mgr.can_use_act_of_faith(self, game=game):
                            chosen = mgr.maybe_use_miracle_die(
                                self,
                                roll_type="battle-shock",
                                dice_count=dice_count,
                                die_faces=6,
                                game=game,
                                needed=leadership_value,
                            )
                            if chosen is not None:
                                fixed_dice = [int(chosen)] + [None] * max(0, int(dice_count) - 1)
                    except Exception:
                        fixed_dice = []
                    roll_spec = {
                        "dice_count": int(dice_count),
                        "faces": 6,
                        "reason": f"Battle-shock test for {self.name} (Ld {leadership_value}+, {dice_expr})",
                        "roll_type": "battle_shock",
                        "show_sum": True,
                        "sum_target": int(leadership_value),
                        "sum_op": "lte",
                        "sum_modifier": int(total_mod),
                        "unit_id": get_entity_id(self),
                        "current_turn": int(current_turn),
                        "was_battle_shocked": bool(is_already_battle_shocked),
                        "shadow_modifier": int(shadow_mod),
                        "shadow_manifestation_active": bool(getattr(shadow_ctx, "manifestation_active", False)) if shadow_ctx is not None else False,
                        "shadow_terror_active": bool(getattr(shadow_ctx, "terror_active", False)) if shadow_ctx is not None else False,
                        "leadership": int(leadership_value),
                        "handler_key": "battle_shock",
                        "reroll_rules": reroll_rules,
                        "command_reroll_allowed": command_reroll_available(game, player, roll_type="battle_shock"),
                        "command_reroll_mode": "whole",
                    }
                    if fixed_dice:
                        roll_spec["fixed_dice"] = list(fixed_dice)
                        roll_spec["miracle_used"] = True
                    try:
                        game.request_dice_roll(player_id=getattr(player, "id", None), spec=roll_spec, prompt=roll_spec["reason"])
                    except Exception:
                        pass
                    return
            except Exception:
                pass

            if game is not None and not bool(getattr(game, "is_authoritative", True)):
                return

            manual_roll = bool(synapse_3d6 or total_mod != 0 or icon_of_war_reroll_available or carmine_reroll_available)
            if not manual_roll:
                try:
                    passed = bool(self.pass_leadership_check())
                except Exception:
                    passed = False
            else:
                if leadership_value is None:
                    leadership_value = _safe_leadership()
                roll_result = None
                dice_rolls = None
                try:
                    army = self.get_parent_army()
                    mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    if mgr is not None and mgr.can_use_act_of_faith(self, game=game):
                        roll_result, dice_rolls, _miracle_used = mgr.resolve_roll(
                            self,
                            roll_type="battle-shock",
                            game=game,
                            dice_count=int(dice_count),
                            die_faces=6,
                        )
                except Exception:
                    roll_result = None
                    dice_rolls = None
                if roll_result is None:
                    roll_result = get_roll(dice_expr)
                try:
                    mod_roll = int(roll_result) + int(total_mod)
                except Exception:
                    mod_roll = roll_result
                dice_note = ""
                try:
                    if dice_rolls and isinstance(dice_rolls, list):
                        dice_note = f" (dice {list(dice_rolls)})"
                except Exception:
                    dice_note = ""
                passed = mod_roll <= leadership_value
                if total_mod:
                    logger.info(f"{self.name} Leadership test: {dice_expr} rolled {roll_result}{dice_note} (mod {total_mod:+}) "
                        f"-> {mod_roll} vs Ld {leadership_value} - {'PASSED' if passed else 'FAILED'}")
                else:
                    logger.info(f"{self.name} Leadership test: {dice_expr} rolled {roll_result}{dice_note} "
                        f"-> {mod_roll} vs Ld {leadership_value} - {'PASSED' if passed else 'FAILED'}")

                reroll_sources = []
                if icon_of_war_reroll_available:
                    reroll_sources.append("Icon of War")
                if carmine_reroll_available:
                    reroll_sources.append("Carmine Reliquary")
                if leadership_reroll_available:
                    if leadership_reroll_sources:
                        reroll_sources.extend(list(leadership_reroll_sources))
                    else:
                        reroll_sources.append("Leadership re-roll")
                if reroll_sources:
                    try:
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                        is_human = self._player_has_local_control(player)
                    except Exception:
                        provider = None
                        is_human = False
                    if is_human and callable(provider):
                        try:
                            want_reroll = bool(
                                provider(
                                    player=player,
                                    unit=self,
                                    roll_type="battle-shock",
                                    value=roll_result,
                                    dice=dice_rolls,
                                )
                            )
                        except Exception:
                            want_reroll = False
                        try:
                            from ...utility.event_bus import append_action
                            pn = player
                        except Exception:
                            append_action = None
                            pn = None
                        source_label = " / ".join(reroll_sources)
                        if want_reroll:
                            original_roll = roll_result
                            new_roll = get_roll(dice_expr)
                            roll_result = new_roll
                            try:
                                mod_roll = int(roll_result) + int(total_mod)
                            except Exception:
                                mod_roll = roll_result
                            passed = mod_roll <= leadership_value
                            if append_action and pn:
                                append_action(
                                    pn,
                                    f"{source_label}: {self.name} re-rolls Battle-shock test ({original_roll} -> {new_roll}).",
                                )
                            if total_mod:
                                logger.info(f"{self.name} Leadership test re-roll: {dice_expr} rolled {roll_result} (mod {total_mod:+}) "
                                    f"-> {mod_roll} vs Ld {leadership_value} - {'PASSED' if passed else 'FAILED'}")
                            else:
                                logger.info(f"{self.name} Leadership test re-roll: {dice_expr} rolled {roll_result} "
                                    f"-> {mod_roll} vs Ld {leadership_value} - {'PASSED' if passed else 'FAILED'}")
                        else:
                            if append_action and pn:
                                append_action(
                                    pn,
                                    f"{source_label}: {self.name} keeps Battle-shock roll ({roll_result}).",
                                )

        self._apply_battle_shock_outcome(
            passed=bool(passed),
            current_turn=int(current_turn),
            was_battle_shocked=bool(is_already_battle_shocked),
            shadow_ctx=shadow_ctx,
            game=game,
            event_system=event_system,
        )

    def _apply_battle_shock_outcome(
        self,
        *,
        passed: bool,
        current_turn: int,
        was_battle_shocked: bool,
        shadow_ctx=None,
        game=None,
        event_system=None,
    ) -> None:
        """Apply Battle-shock outcomes after a test result is known."""
        # Units that are already Battle-shocked can still be forced to take another Battle-shock test,
        # but the result does not change the unit's Battle-shocked status or duration.
        if (not passed) and (not was_battle_shocked):
            battle_shock_effect = BattleShockEffect(int(current_turn))
            self.apply_status_effect(battle_shock_effect)
            logger.error(f"{self.name} has failed the battle shock test and is battle-shocked!")

        try:
            fear_queue_fn = getattr(game, "_queue_fear_made_manifest_trigger", None)
            if callable(fear_queue_fn):
                fear_queue_fn(unit=self, passed=passed, game=game)
        except Exception:
            pass

        if shadow_ctx is not None:
            try:
                from ...rules.shadow_of_chaos import ShadowOfChaosManager, ShadowBattleShockContext

                apply_ctx = shadow_ctx
                defer_terror = False
                queue_fn = getattr(game, "_queue_cankerblight_trigger", None)
                if callable(queue_fn):
                    defer_terror = bool(queue_fn(unit=self, passed=passed, shadow_ctx=shadow_ctx, game=game))
                if defer_terror and (not passed) and bool(getattr(shadow_ctx, "terror_active", False)):
                    apply_ctx = ShadowBattleShockContext(
                        modifier=int(getattr(shadow_ctx, "modifier", 0) or 0),
                        manifestation_active=bool(getattr(shadow_ctx, "manifestation_active", False)),
                        terror_active=False,
                    )
                ShadowOfChaosManager.apply_battle_shock_outcome(self, passed=passed, context=apply_ctx, game=game)
            except Exception:
                pass

        if event_system is not None:
            try:
                event_system.publish("battle_shock_test_resolved", unit=self, passed=passed)
            except Exception:
                pass

        # Resolve Formless Horror gating if this Battle-shock test was triggered for targeting.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and isinstance(sr.get("formless_horror_pending"), dict):
                pending = dict(sr.get("formless_horror_pending") or {})
                target_id = str(pending.get("target_id", "") or "")
                phase_name = str(pending.get("phase", "") or "").strip().upper()
                sr.pop("formless_horror_pending", None)
                if passed:
                    sr["formless_horror_allowed"] = {
                        "target_id": target_id,
                        "phase": phase_name,
                        "turn": int(current_turn),
                    }
                else:
                    blocked = sr.get("formless_horror_blocked")
                    if not isinstance(blocked, dict):
                        blocked = {}
                    if phase_name:
                        ids = list(blocked.get(phase_name, []) or [])
                        if target_id and target_id not in ids:
                            ids.append(target_id)
                        blocked[phase_name] = ids
                        sr["formless_horror_blocked"] = blocked
                self.special_rules = sr
        except Exception:
            pass

    def clear_battle_shock(self) -> bool:
        """Remove Battle-shock from this unit (used at the start of its owner's next Command phase)."""
        lock_round = 0
        current_round = 0
        special_rules = getattr(self, "special_rules", None)
        if isinstance(special_rules, dict):
            lock_round = int(special_rules.get("rad_bombardment_taking_cover_round", 0) or 0)

        parent_army = None
        get_parent_army = getattr(self, "get_parent_army", None)
        if callable(get_parent_army):
            parent_army = get_parent_army()
        if parent_army is None:
            parent_army = getattr(self, "parent_army", None)
        game = getattr(getattr(parent_army, "player", None), "game", None) if parent_army is not None else None
        if game is not None:
            current_round = int(getattr(game, "turn", 0) or 0)

        if lock_round > 0 and (current_round <= 0 or current_round <= lock_round):
            return False
        if lock_round > 0 and current_round > lock_round and isinstance(special_rules, dict):
            updated_rules = dict(special_rules)
            updated_rules.pop("rad_bombardment_taking_cover_round", None)
            updated_rules.pop("rad_bombardment_taking_cover_added_battleshock", None)
            self.special_rules = updated_rules

        removed = False
        for eff in list(getattr(self, "status_effects", []) or []):
            if isinstance(eff, BattleShockEffect):
                try:
                    self.remove_status_effect(eff)
                    removed = True
                except Exception:
                    continue
        return removed

    # ---------------- Reanimation Protocols ----------------

    def _reanimation_choose_model(self, eligible_models, *, is_human: bool, provider, reason: str, instruction: Optional[str] = None):
        if not eligible_models:
            return None
        if len(eligible_models) == 1:
            return eligible_models[0]
        if is_human and callable(provider):
            try:
                ctx = {"reason": reason}
                if instruction:
                    ctx["instruction"] = instruction
                chosen = provider(self.get_attached_unit_root(), list(eligible_models), ctx)
                if chosen is not None and chosen in eligible_models:
                    return chosen
            except Exception:
                pass
        return eligible_models[0]

    def _check_collision_with_obstacles_or_terrain(
        self,
        game_map: Optional['Map'],
        model: Model,
        destination: Tuple[float, float],
    ) -> bool:
        if game_map is None or model is None:
            return False
        fn = getattr(game_map, "check_collision_with_obstacles", None)
        if not callable(fn):
            fn = getattr(game_map, "check_collision_with_terrain", None)
        if callable(fn):
            try:
                return bool(fn(model, destination=destination))
            except Exception:
                return False
        return False

    def _reanimation_position_valid(
        self,
        x: float,
        y: float,
        z: float,
        facing: float,
        model: Model,
        alive_models: list[Model],
        game_map: Optional['Map'],
        required_neighbors: int,
    ) -> bool:
        if game_map is None:
            return True
        try:
            if not game_map.is_within_boundary(model, destination=(x, y)):
                return False
            if self._check_collision_with_obstacles_or_terrain(game_map, model, (x, y)):
                return False
            if game_map.check_collision_with_other_friendly_units(model, destination=(x, y)):
                return False
            if game_map.check_collision_with_other_enemy_units(model, destination=(x, y)):
                return False
        except Exception:
            return False

        try:
            candidate_base = self._create_potential_base(x, y, z, facing, model=model)
        except Exception:
            return False

        for m in list(alive_models or []):
            try:
                if not getattr(m, "is_alive", True):
                    continue
            except Exception:
                pass
            try:
                if candidate_base.collides_with(m.model_base):
                    return False
            except Exception:
                pass

        if required_neighbors <= 0:
            return True

        neighbors = 0
        for m in list(alive_models or []):
            try:
                base = m.model_base
                horizontal = candidate_base.get_base_shape().distance(base.get_base_shape())
                vertical = abs(float(getattr(candidate_base, "z", 0.0)) - float(getattr(base, "z", 0.0)))
            except Exception:
                continue
            if horizontal <= 2.0 + 1e-6 and vertical <= 5.0 + 1e-6:
                neighbors += 1
                if neighbors >= required_neighbors:
                    return True
        return False

    def _find_reanimation_position(
        self,
        model: Model,
        alive_models: list[Model],
        *,
        game_map: Optional['Map'],
        required_neighbors: int,
    ) -> Optional[Tuple[float, float, float, float]]:
        if not alive_models:
            return None
        if game_map is None:
            return None

        try:
            mr = float(model.model_base.get_longest_radius())
        except Exception:
            try:
                mr = float(model.model_base.get_radius())
            except Exception:
                mr = 1.0

        for anchor in list(alive_models or []):
            try:
                ax, ay, az, af = anchor.get_location()
            except Exception:
                continue
            try:
                ar = float(anchor.model_base.get_longest_radius())
            except Exception:
                try:
                    ar = float(anchor.model_base.get_radius())
                except Exception:
                    ar = 1.0

            min_center = ar + mr + 0.05
            max_center = min_center + 2.0 + 1e-6
            for ring in np.arange(0.0, max(0.01, max_center - min_center) + 0.001, 0.5):
                r = float(min_center + ring)
                if r > max_center + 1e-6:
                    break
                for deg in range(0, 360, 15):
                    ang = math.radians(deg)
                    x = ax + math.cos(ang) * r
                    y = ay + math.sin(ang) * r
                    z = az
                    facing = af
                    if self._reanimation_position_valid(
                        x,
                        y,
                        z,
                        facing,
                        model,
                        alive_models,
                        game_map,
                        required_neighbors,
                    ):
                        return (x, y, z, facing)
        return None

    def return_destroyed_bodyguard_models(
        self,
        amount: int,
        *,
        game_map: Optional['Map'] = None,
        chosen_models: Optional[list[Model]] = None,
        wounds: Optional[int] = None,
        placement_source: Optional[str] = None,
    ) -> int:
        if int(amount or 0) <= 0:
            return 0
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return 0
        try:
            if bool(getattr(root, "is_leader", False)):
                return 0
        except Exception:
            pass

        try:
            destroyed = list(getattr(root, "models_lost", []) or [])
        except Exception:
            destroyed = []
        if destroyed:
            destroyed = [m for m in destroyed if root._horrors_can_return_model(m)]
        if not destroyed:
            return 0

        try:
            starting = int(getattr(root, "starting_model_count", 0) or 0)
        except Exception:
            starting = 0
        if starting <= 0:
            try:
                starting = len(getattr(root, "models", []) or []) + len(destroyed)
            except Exception:
                starting = len(destroyed)

        try:
            alive_models = [m for m in (getattr(root, "models", []) or []) if getattr(m, "is_alive", True)]
        except Exception:
            alive_models = list(getattr(root, "models", []) or [])

        current = len(alive_models)
        if starting and current >= starting:
            return 0

        max_return = int(amount or 0)
        if starting:
            max_return = min(max_return, max(0, starting - current))
        if max_return <= 0:
            return 0
        if chosen_models is not None:
            to_return = []
            seen_ids: set[str] = set()
            for model in list(chosen_models or []):
                if model is None:
                    continue
                mid = get_entity_id(model)
                if mid in seen_ids:
                    continue
                if model in destroyed:
                    to_return.append(model)
                    seen_ids.add(mid)
        else:
            to_return = destroyed[:max_return]
        if not to_return:
            return 0
        if len(to_return) > max_return:
            to_return = to_return[:max_return]

        returned = 0
        returned_models: list[Model] = []
        placement_tag = str(placement_source or "return")
        for model in to_return:
            try:
                if hasattr(root, "models_lost") and model in root.models_lost:
                    root.models_lost.remove(model)
            except Exception:
                pass
            try:
                if hasattr(model, "set_parent_unit"):
                    model.set_parent_unit(root)
                else:
                    model.parent_unit = root
            except Exception:
                pass
            try:
                base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
            except Exception:
                base_wounds = 0
            if base_wounds <= 0:
                base_wounds = 1
            desired_wounds = base_wounds if wounds is None else int(wounds)
            if desired_wounds <= 0:
                desired_wounds = base_wounds
            try:
                model.wounds = desired_wounds
            except Exception:
                try:
                    model._wounds = desired_wounds
                except Exception:
                    pass
            try:
                if hasattr(model, "_check_damaged_profile"):
                    model._check_damaged_profile()
            except Exception:
                pass
            try:
                setattr(model, "_on_death_reactions_resolved", False)
                setattr(model, "_fight_on_death_used", False)
                setattr(model, "_shoot_on_death_used", False)
            except Exception:
                pass
            root._mark_models_pending_placement([model], source=placement_tag)
            added = False
            try:
                if hasattr(root, "add_model"):
                    root.add_model(model)
                    added = True
                else:
                    root.models.append(model)
                    added = True
            except Exception:
                added = False
            if not added:
                try:
                    root.models.append(model)
                except Exception:
                    pass
            alive_models.append(model)
            try:
                if hasattr(root, "update_coherency"):
                    root.update_coherency()
            except Exception:
                pass
            returned_models.append(model)
            returned += 1
        if returned_models:
            root._request_pending_placement_decision(game_map=game_map)
        return returned

    def apply_reanimation_protocols(
        self,
        wounds_to_restore: int,
        *,
        game_map: Optional['Map'] = None,
        is_human: bool = False,
        provider=None,
        roll_expr: Optional[str] = None,
    ) -> dict:
        """
        Resolve Reanimation Protocols for this (attached) unit group.

        Returns a dict with counts of healed wounds and returned models.
        """
        result = {"healed": 0, "returned": 0}
        try:
            resolved_wounds = int(wounds_to_restore or 0)
        except Exception:
            resolved_wounds = 0
        if resolved_wounds <= 0:
            return result

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        try:
            if not getattr(root, "deployed", True):
                return result
            if str(getattr(root, "reserve_status", "deployed")) != "deployed":
                return result
            if hasattr(root, "is_in_reserves") and callable(getattr(root, "is_in_reserves")):
                if bool(root.is_in_reserves()):
                    return result
            if bool(getattr(root, "embarked_in", None)):
                return result
            if bool(getattr(root, "is_embarked", False)):
                return result
        except Exception:
            pass

        try:
            if hasattr(root, "is_alive") and callable(getattr(root, "is_alive")) and not root.is_alive():
                return result
        except Exception:
            pass

        try:
            members = root.get_attached_unit_members()
        except Exception:
            members = [root]

        roll_expr_norm = str(roll_expr or "").strip().upper()

        # Their Number is Legion: auto-apply re-roll when the re-roll is strictly better.
        if roll_expr_norm in ("D3", "D6"):
            try:
                reroll_specs = list(root.unit_reanimation_dice_reroll_specs() or [])
            except Exception:
                reroll_specs = []
            if reroll_specs:
                max_roll = 3 if roll_expr_norm == "D3" else 6
                if int(resolved_wounds or 0) < int(max_roll):
                    try:
                        rerolled = int(get_roll(roll_expr_norm) or 0)
                    except Exception:
                        rerolled = int(resolved_wounds or 0)
                    if int(rerolled or 0) > int(resolved_wounds or 0):
                        resolved_wounds = int(rerolled or 0)

        # Necrons Reanimation interactions:
        # - Nanoscarab Reanimation Beam (Aura): add one additional D3 while in range.
        # - Nanoscarab Projector: auto-use one eligible unused bearer (+1, once per battle round).
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)

        is_necrons_target = False
        try:
            has_any_keyword = getattr(root, "has_any_keyword", None)
            if callable(has_any_keyword):
                is_necrons_target = bool(has_any_keyword("NECRONS"))
        except Exception:
            is_necrons_target = False

        if army is not None and is_necrons_target:
            def _unit_sort_key(unit):
                try:
                    return str(get_entity_id(unit))
                except Exception:
                    return str(getattr(unit, "name", "") or "")

            def _model_sort_key(model):
                try:
                    return str(get_entity_id(model))
                except Exception:
                    return str(getattr(model, "name", "") or "")

            seen_roots: set[str] = set()
            beam_applied = False
            projector_applied = False
            for source_unit in sorted(list(getattr(army, "units", []) or []), key=_unit_sort_key):
                if source_unit is None:
                    continue
                try:
                    source_root = source_unit.get_attached_unit_root()
                except Exception:
                    source_root = source_unit
                if source_root is None:
                    continue
                source_root_id = str(get_entity_id(source_root) or "")
                if not source_root_id or source_root_id in seen_roots:
                    continue
                seen_roots.add(source_root_id)
                if not bool(getattr(source_root, "is_alive", lambda: False)()):
                    continue
                if not bool(getattr(source_root, "deployed", True)):
                    continue
                try:
                    if source_root.is_in_reserves() or source_root.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    source_models = list(source_root.get_attached_unit_models() or [])
                except Exception:
                    source_models = list(getattr(source_root, "models", []) or [])
                alive_models_for_source = [m for m in list(source_models or []) if bool(getattr(m, "is_alive", True))]
                if not alive_models_for_source:
                    continue
                for source_model in sorted(alive_models_for_source, key=_model_sort_key):
                    model_owner = getattr(source_model, "parent_unit", None) or source_root
                    spec_fn = getattr(model_owner, "model_reanimation_protocol_bonus_specs", None)
                    if not callable(spec_fn):
                        continue
                    try:
                        specs = list(spec_fn(source_model) or [])
                    except Exception:
                        specs = []
                    if not specs:
                        continue
                    for spec in list(specs or []):
                        stype = str(spec.get("type", "") or "").strip().lower()
                        if stype not in ("nanoscarab_reanimation_beam", "nanoscarab_projector"):
                            continue
                        try:
                            range_value = float(spec.get("range", 0) or 0)
                        except Exception:
                            range_value = 0.0
                        if range_value <= 0:
                            continue
                        try:
                            in_range = bool(source_root._model_within_range_of_unit(source_model, root, float(range_value)))
                        except Exception:
                            in_range = False
                        if not in_range:
                            continue

                        if stype == "nanoscarab_reanimation_beam":
                            if beam_applied:
                                continue
                            try:
                                bonus_roll = int(get_roll("D3") or 0)
                            except Exception:
                                bonus_roll = 0
                            if bonus_roll > 0:
                                resolved_wounds += int(bonus_roll)
                            beam_applied = True
                            continue

                        if stype == "nanoscarab_projector":
                            if projector_applied:
                                continue
                            key = str(spec.get("ability_key", "") or "nanoscarab_projector").strip().lower()
                            if not key:
                                key = "nanoscarab_projector"
                            has_used_round = getattr(source_model, "has_used_once_per_battle_round", None)
                            if callable(has_used_round):
                                try:
                                    if bool(has_used_round(key)):
                                        continue
                                except Exception:
                                    pass
                            mark_used_round = getattr(source_model, "mark_used_once_per_battle_round", None)
                            if callable(mark_used_round):
                                source_name = str(spec.get("source", "") or "Nanoscarab Projector").strip() or "Nanoscarab Projector"
                                if not bool(mark_used_round(key, ability_name=source_name, source="wargear")):
                                    continue
                            try:
                                bonus = int(spec.get("bonus", 1) or 1)
                            except Exception:
                                bonus = 1
                            if bonus > 0:
                                resolved_wounds += int(bonus)
                            projector_applied = True
                            continue

        if int(resolved_wounds or 0) <= 0:
            return result

        def _is_alive_model(m) -> bool:
            try:
                return bool(getattr(m, "is_alive", True))
            except Exception:
                return True

        def _is_wounded_model(m) -> bool:
            try:
                return _is_alive_model(m) and (not bool(getattr(m, "is_max_health", True)))
            except Exception:
                try:
                    w = int(getattr(m, "wounds", 0))
                    bw = int(getattr(m, "_base_wounds", getattr(m, "base_wounds", w)))
                    return _is_alive_model(m) and w < bw
                except Exception:
                    return False

        alive_models = [m for u in (members or []) for m in (getattr(u, "models", []) or []) if _is_alive_model(m)]
        if not alive_models:
            return result

        returned_models: list[Model] = []

        for _ in range(int(resolved_wounds or 0)):
            wounded = [m for m in alive_models if _is_wounded_model(m)]
            if wounded:
                target = self._reanimation_choose_model(
                    wounded,
                    is_human=is_human,
                    provider=provider,
                    reason="Reanimation Protocols - Restore Wound",
                    instruction="Select a wounded model to regain 1 wound.",
                )
                if target is None:
                    break
                try:
                    if hasattr(target, "heal"):
                        target.heal(1)
                    else:
                        base_wounds = int(getattr(target, "_base_wounds", getattr(target, "base_wounds", 0)) or 0)
                        target.wounds = min(base_wounds, int(getattr(target, "wounds", 0) or 0) + 1)
                    if hasattr(target, "_check_damaged_profile"):
                        target._check_damaged_profile()
                except Exception:
                    pass
                result["healed"] += 1
                continue

            try:
                if hasattr(root, "is_below_starting_strength") and callable(getattr(root, "is_below_starting_strength")):
                    if not root.is_below_starting_strength():
                        break
            except Exception:
                pass

            destroyed_pool: List[Tuple['Unit', Model]] = []
            for u in (members or []):
                lost = getattr(u, "models_lost", None)
                if isinstance(lost, list) and lost:
                    for m in lost:
                        if root._horrors_can_return_model(m):
                            destroyed_pool.append((u, m))
            if not destroyed_pool:
                break

            if len(destroyed_pool) == 1:
                unit_for_model, model = destroyed_pool[0]
            else:
                candidates = [m for (_u, m) in destroyed_pool]
                chosen = self._reanimation_choose_model(
                    candidates,
                    is_human=is_human,
                    provider=provider,
                    reason="Reanimation Protocols - Return Model",
                    instruction="Select a destroyed model to return with 1 wound.",
                )
                if chosen is None or chosen not in candidates:
                    chosen = candidates[0]
                unit_for_model = next((u for (u, m) in destroyed_pool if m is chosen), members[0])
                model = chosen

            try:
                if hasattr(unit_for_model, "models_lost") and model in unit_for_model.models_lost:
                    unit_for_model.models_lost.remove(model)
            except Exception:
                pass

            try:
                if hasattr(model, "set_parent_unit"):
                    model.set_parent_unit(unit_for_model)
                else:
                    model.parent_unit = unit_for_model
            except Exception:
                pass

            try:
                model.wounds = 1
            except Exception:
                try:
                    model._wounds = 1
                except Exception:
                    pass
            try:
                if hasattr(model, "_check_damaged_profile"):
                    model._check_damaged_profile()
            except Exception:
                pass

            try:
                setattr(model, "_on_death_reactions_resolved", False)
                setattr(model, "_fight_on_death_used", False)
                setattr(model, "_shoot_on_death_used", False)
            except Exception:
                pass

            unit_for_model._mark_models_pending_placement([model], source="reanimation")
            try:
                if hasattr(unit_for_model, "add_model"):
                    unit_for_model.add_model(model)
                else:
                    unit_for_model.models.append(model)
            except Exception:
                pass

            alive_models = [m for u in (members or []) for m in (getattr(u, "models", []) or []) if _is_alive_model(m)]

            try:
                if hasattr(unit_for_model, "update_coherency"):
                    unit_for_model.update_coherency()
                if root is not unit_for_model and hasattr(root, "update_coherency"):
                    root.update_coherency()
            except Exception:
                pass
            returned_models.append(model)

            result["returned"] += 1

        if returned_models:
            root._request_pending_placement_decision(game_map=game_map)
        return result

    def use_ability(self, ability: Ability, target: 'Unit', game_map: 'Map'):
        """Uses a special ability."""
        from ..map import Map  # Import inside the function
        assert isinstance(game_map, Map)
        if ability:
            ability.activate(self)
            logger.info(f"{self.name} uses ability: {ability.name}.")
        else:
            logger.info(f"{self.name} does not have ability: {ability.name}.")

    def embark(self, transport_unit: 'Unit', *, game_map: 'Map') -> None:
        """
        Embark (10th edition core rules, best-effort):
        - End a Normal/Advance/Fall Back move with all models within 3" of a friendly Transport.
        - Capacity must allow it.
        - Cannot embark and disembark in the same phase/turn (tracked by round_state flags).
        """
        if game_map is None:
            raise RuntimeError("Embark requires an active game map.")
        army = self.get_parent_army()
        if army is None or getattr(army, "player", None) is None or getattr(army.player, "game", None) is None:
            raise RuntimeError("Embark requires a unit assigned to a player with an active game.")
        game = army.player.game

        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and sr.get("fire_and_fade_no_embark_turn_owner"):
            owner = str(sr.get("fire_and_fade_no_embark_turn_owner") or "")
            turn = int(sr.get("fire_and_fade_no_embark_turn", 0) or 0)
            current_player = game.get_current_player()
            if owner and current_player is not None:
                if current_player.id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                    logger.info(f"{self.name} cannot embark this turn (Fire and Fade)")
                    return

        try:
            if self.cannot_embark():
                logger.info(f"{self.name} cannot embark (rule restriction).")
                return
        except Exception:
            pass

        if self.round_state.disembarked_this_round:
            logger.info(f"{self.name} cannot embark after disembarking this turn")
            return

        if not transport_unit.can_transport(self):
            logger.info(f"{self.name} cannot embark onto {transport_unit.name}.")
            return

        # Pre-battle "declare embarked units" support: during setup/deployment, units can start embarked
        # without having moved or being within 3". If neither unit is deployed yet, allow embark bookkeeping only.
        if (not self.deployed) and (not transport_unit.deployed):
            ok = transport_unit.add_passenger(self, game_map=game_map)
            if ok:
                self._apply_aggressive_deployment_scouts(transport_unit)
                logger.info(f"{self.name} starts embarked within {transport_unit.name}.")
            else:
                logger.info(f"{self.name} cannot embark onto {transport_unit.name}.")
            return

        # Must have actually moved (Normal/Advance/Fall Back) this round (not remain stationary)
        if getattr(self.round_state, "remained_stationary_this_round", False):
            logger.info(f"{self.name} cannot embark (did not move this phase)")
            return

        # Must be within 3" with all models
        if transport_unit.models and transport_unit.models[0].is_alive:
            from ...utility.aura_utils import distance_between_models_bases_3d
            t_model = transport_unit.models[0]
            for m in self.models:
                if not m.is_alive:
                    continue
                d = distance_between_models_bases_3d(m, t_model)
                if d > 3.0 + 1e-6:
                    logger.info(f"{self.name} cannot embark: not all models are within 3\" of {transport_unit.name}")
                    return

        ok = transport_unit.add_passenger(self, game_map=game_map)
        if ok:
            logger.info(f"{self.name} embarks onto {transport_unit.name}.")
        else:
            logger.info(f"{self.name} cannot embark onto {transport_unit.name}.")

    def _find_disembark_positions(
        self,
        transport_base,
        game_map: 'Map',
        max_distance: float,
        require_not_in_engagement: bool = True,
        min_enemy_horizontal_distance: Optional[float] = None,
    ) -> Optional[List[Tuple[float, float, float, float]]]:
        """
        Attempt to find legal placements for all models in this unit wholly within
        `max_distance` of the transport, without collisions and (optionally) not within engagement range.
        """
        if transport_base is None:
            return None
        if not self.models:
            return []

        # Determine anchor point & radii
        tx, ty = float(getattr(transport_base, "x", 0.0)), float(getattr(transport_base, "y", 0.0))
        tz = float(getattr(transport_base, "z", 0.0))
        try:
            tr = float(transport_base.get_longest_radius())
        except Exception:
            try:
                tr = float(transport_base.get_radius())
            except Exception:
                tr = 1.0

        enemy_units = [u for u in game_map.get_enemy_units(self) if u.is_alive()]
        enemy_models = []
        for eu in enemy_units:
            for em in eu.models:
                if getattr(em, "is_alive", False):
                    enemy_models.append(em)

        placed: List[Tuple[float, float, float, float]] = []
        facing = 0.0

        for idx, model in enumerate(self.models):
            if not model.is_alive:
                continue
            try:
                mr = float(model.model_base.get_longest_radius())
            except Exception:
                try:
                    mr = float(model.model_base.get_radius())
                except Exception:
                    mr = 1.0

            # Minimum distance to avoid overlapping the transport base itself
            min_center = tr + mr + 0.05
            max_center = max_distance + tr + mr + 1e-6

            found = None
            # Spiral-ish sampling around the transport
            for ring in np.arange(0.0, max(0.01, max_center - min_center) + 0.001, 0.5):
                r = float(min_center + ring)
                if r > max_center + 1e-6:
                    break
                for deg in range(0, 360, 15):
                    ang = math.radians(deg)
                    x = tx + math.cos(ang) * r
                    y = ty + math.sin(ang) * r
                    z = tz

                    # Base-to-base "within max_distance" check
                    try:
                        candidate_base = self._create_potential_base(x, y, z, facing, model=model)
                        # Wholly within X of a unit is stronger than just edge-distance; but for our placement search
                        # we enforce a conservative necessary condition: base-to-base distance <= X.
                        # (The final placement validator for disembark handles the full constraints.)
                        # Use base-plane 3D distance (closest points on bases/hulls), not model height.
                        from ...utility.aura_utils import distance_between_bases_3d
                        edge = float(distance_between_bases_3d(candidate_base, transport_base))
                        if edge > float(max_distance) + 1e-6:
                            continue
                    except Exception:
                        pass

                    # Collision checks vs battlefield
                    try:
                        if not game_map.is_within_boundary(model, destination=(x, y)):
                            continue
                        if self._check_collision_with_obstacles_or_terrain(game_map, model, (x, y)):
                            continue
                        if game_map.check_collision_with_other_friendly_units(model, destination=(x, y)):
                            continue
                        if game_map.check_collision_with_other_enemy_units(model, destination=(x, y)):
                            continue
                    except Exception:
                        continue

                    # Collision checks within this unit
                    try:
                        if self._collides_with_unit_models(x, y, z, facing, placed, model=model):
                            continue
                        if not self._is_coherent_within_unit(x, y, z, facing, placed, model=model):
                            continue
                    except Exception:
                        # If coherency logic fails, allow placement but still avoid collisions.
                        pass

                    # Disembark requirement: not within engagement range (or farther if overridden).
                    min_enemy = 0.0
                    try:
                        min_enemy = float(min_enemy_horizontal_distance or 0.0)
                    except Exception:
                        min_enemy = 0.0
                    if require_not_in_engagement:
                        min_enemy = max(min_enemy, 1.0)
                    if min_enemy > 0 and enemy_models:
                        from ...utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                        candidate_base = self._create_potential_base(x, y, z, facing, model=model)
                        too_close = False
                        for em in enemy_models:
                            if not getattr(em, "is_alive", False):
                                continue
                            horizontal = float(horizontal_distance_between_bases_2d(candidate_base, em.model_base))
                            if min_enemy_horizontal_distance is not None and float(min_enemy_horizontal_distance or 0.0) > 0:
                                if horizontal <= min_enemy + 1e-6:
                                    too_close = True
                                    break
                            else:
                                vertical = float(vertical_distance_between_bases(candidate_base, em.model_base))
                                if horizontal <= 1.0 + 1e-6 and vertical <= 5.0 + 1e-6:
                                    too_close = True
                                    break
                            if horizontal <= min_enemy + 1e-6 and min_enemy > 1.0:
                                # Too close to an enemy model for disembark
                                too_close = True
                                break
                        if too_close:
                            continue

                    found = (x, y, z, facing)
                    break
                if found is not None:
                    break

            if found is None:
                return None
            placed.append(found)

        return placed

    def _find_single_disembark_position(
        self,
        *,
        model: Model,
        transport_base,
        game_map: 'Map',
        max_distance: float,
        placed: List[Tuple[float, float, float, float]],
        require_not_in_engagement: bool = True,
        min_enemy_horizontal_distance: Optional[float] = None,
    ) -> Optional[Tuple[float, float, float, float]]:
        """Find a valid disembark position for one model given already-placed models."""
        if transport_base is None:
            return None
        tx, ty = float(getattr(transport_base, "x", 0.0)), float(getattr(transport_base, "y", 0.0))
        tz = float(getattr(transport_base, "z", 0.0))
        try:
            tr = float(transport_base.get_longest_radius())
        except Exception:
            try:
                tr = float(transport_base.get_radius())
            except Exception:
                tr = 1.0
        try:
            mr = float(model.model_base.get_longest_radius())
        except Exception:
            try:
                mr = float(model.model_base.get_radius())
            except Exception:
                mr = 1.0

        enemy_units = [u for u in game_map.get_enemy_units(self) if u.is_alive()]
        enemy_models = []
        for eu in enemy_units:
            for em in eu.models:
                if getattr(em, "is_alive", False):
                    enemy_models.append(em)

        facing = 0.0
        min_center = tr + mr + 0.05
        max_center = max_distance + tr + mr + 1e-6

        for ring in np.arange(0.0, max(0.01, max_center - min_center) + 0.001, 0.5):
            r = float(min_center + ring)
            if r > max_center + 1e-6:
                break
            for deg in range(0, 360, 15):
                ang = math.radians(deg)
                x = tx + math.cos(ang) * r
                y = ty + math.sin(ang) * r
                z = tz

                # Base-to-base "within max_distance" check
                from ...utility.aura_utils import distance_between_bases_3d
                candidate_base = self._create_potential_base(x, y, z, facing, model=model)
                edge = float(distance_between_bases_3d(candidate_base, transport_base))
                if edge > max_distance + 1e-6:
                    continue

                # Collision checks vs battlefield
                try:
                    if not game_map.is_within_boundary(model, destination=(x, y)):
                        continue
                    if self._check_collision_with_obstacles_or_terrain(game_map, model, (x, y)):
                        continue
                    if game_map.check_collision_with_other_friendly_units(model, destination=(x, y)):
                        continue
                    if game_map.check_collision_with_other_enemy_units(model, destination=(x, y)):
                        continue
                except Exception:
                    continue

                # Collision checks within this unit
                try:
                    if self._collides_with_unit_models(x, y, z, facing, placed, model=model):
                        continue
                    if not self._is_coherent_within_unit(x, y, z, facing, placed, model=model):
                        continue
                except Exception:
                    pass

                min_enemy = 0.0
                try:
                    min_enemy = float(min_enemy_horizontal_distance or 0.0)
                except Exception:
                    min_enemy = 0.0
                if require_not_in_engagement:
                    min_enemy = max(min_enemy, 1.0)
                if min_enemy > 0 and enemy_models:
                    from ...utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                    candidate_base = self._create_potential_base(x, y, z, facing, model=model)
                    blocked = False
                    for em in enemy_models:
                        if not getattr(em, "is_alive", False):
                            continue
                        horizontal = float(horizontal_distance_between_bases_2d(candidate_base, em.model_base))
                        if min_enemy_horizontal_distance is not None and float(min_enemy_horizontal_distance or 0.0) > 0:
                            if horizontal <= min_enemy + 1e-6:
                                blocked = True
                                break
                        else:
                            vertical = float(vertical_distance_between_bases(candidate_base, em.model_base))
                            if horizontal <= 1.0 + 1e-6 and vertical <= 5.0 + 1e-6:
                                blocked = True
                                break
                        if horizontal <= min_enemy + 1e-6 and min_enemy > 1.0:
                            blocked = True
                            break
                    if blocked:
                        continue

                return (x, y, z, facing)

        return None

    def _apply_goretrack_onslaught_disembark_effect(self, *, game=None, current_turn: int = 0) -> None:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "world_eaters_detachments", None)
        if mgr is None or not getattr(mgr, "goretrack_onslaught_applies", None):
            return
        try:
            if not mgr.goretrack_onslaught_applies(self):
                return
        except Exception:
            return
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return
        if game is None:
            try:
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        try:
            owner = str(getattr(current_player, "id", "") or "")
        except Exception:
            owner = ""
        if not owner:
            try:
                owner = str(getattr(getattr(army, "player", None), "id", "") or "")
            except Exception:
                owner = ""
        try:
            turn = int(getattr(game, "turn", current_turn) or current_turn)
        except Exception:
            turn = int(current_turn or 0)
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for unit in members:
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["goretrack_onslaught_active"] = True
            if owner:
                sr["goretrack_onslaught_turn_owner"] = owner
            if turn:
                sr["goretrack_onslaught_turn"] = int(turn)
            unit.special_rules = sr

    def _apply_murderous_onslaught_disembark_effect(self, *, game=None, current_turn: int = 0) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return
        if not self._attached_unit_has_enhancement_flag(
            "enhancement_murderous_onslaught",
            enhancement_id="000010086002",
            enhancement_name="murderous onslaught",
        ):
            return
        if game is None:
            try:
                army = self.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        try:
            owner = str(getattr(current_player, "id", "") or "")
        except Exception:
            owner = ""
        if not owner:
            try:
                army = self.get_parent_army()
                owner = str(getattr(getattr(army, "player", None), "id", "") or "")
            except Exception:
                owner = ""
        try:
            turn = int(getattr(game, "turn", current_turn) or current_turn)
        except Exception:
            turn = int(current_turn or 0)
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for unit in members:
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["murderous_onslaught_no_overwatch"] = True
            if owner:
                sr["murderous_onslaught_turn_owner"] = owner
            if turn:
                sr["murderous_onslaught_turn"] = int(turn)
            unit.special_rules = sr

    def _apply_spearhead_striker_disembark_effect(self, *, game=None, current_turn: int = 0) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return
        if not self._attached_unit_has_enhancement_flag(
            "enhancement_spearhead_striker",
            enhancement_id="000010006003",
            enhancement_name="spearhead striker",
        ):
            return
        if game is None:
            try:
                army = self.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        try:
            owner = str(getattr(current_player, "id", "") or "")
        except Exception:
            owner = ""
        if not owner:
            try:
                army = self.get_parent_army()
                owner = str(getattr(getattr(army, "player", None), "id", "") or "")
            except Exception:
                owner = ""
        try:
            turn = int(getattr(game, "turn", current_turn) or current_turn)
        except Exception:
            turn = int(current_turn or 0)
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for unit in members:
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["spearhead_striker_no_overwatch"] = True
            sr["spearhead_striker_charge_reroll"] = True
            if owner:
                sr["spearhead_striker_turn_owner"] = owner
            if turn:
                sr["spearhead_striker_turn"] = int(turn)
            unit.special_rules = sr

    def _apply_rain_of_cruelty_disembark_effect(self, *, game=None, current_turn: int = 0) -> None:
        army = self.get_parent_army()
        if army is None:
            return
        mgr = getattr(army, "drukhari_detachments", None)
        apply_fn = getattr(mgr, "apply_rain_of_cruelty_on_disembark", None) if mgr is not None else None
        if callable(apply_fn):
            apply_fn(self, game=game, current_turn=current_turn)

    def _disembark_override_rules(self, *, transport_unit: Optional['Unit'] = None, game: Optional['Game'] = None) -> dict:
        overrides: dict[str, object] = {}
        try:
            sr = getattr(self, "special_rules", None)
        except Exception:
            sr = None
        if isinstance(sr, dict) and sr.get("goretrack_aggressive_disembark_active"):
            tid = str(sr.get("goretrack_aggressive_disembark_transport_id", "") or "")
            if tid and transport_unit is not None:
                try:
                    if tid != str(get_entity_id(transport_unit) or ""):
                        return overrides
                except Exception:
                    pass
            try:
                overrides["max_distance"] = float(sr.get("goretrack_aggressive_disembark_distance", 6.0) or 6.0)
            except Exception:
                overrides["max_distance"] = 6.0
            overrides["require_not_in_engagement"] = not bool(
                sr.get("goretrack_aggressive_disembark_allow_engagement", True)
            )
        if isinstance(sr, dict) and sr.get("stratagem_disembark_override_active"):
            tid = str(sr.get("stratagem_disembark_override_transport_id", "") or "")
            transport_matches = True
            if tid and transport_unit is not None:
                try:
                    transport_matches = tid == str(get_entity_id(transport_unit) or "")
                except Exception:
                    transport_matches = True
            if transport_matches:
                try:
                    distance = float(sr.get("stratagem_disembark_override_max_distance", 0) or 0)
                except Exception:
                    distance = 0.0
                if distance > 0:
                    overrides["max_distance"] = float(distance)
                if "stratagem_disembark_override_require_not_in_engagement" in sr:
                    overrides["require_not_in_engagement"] = bool(
                        sr.get("stratagem_disembark_override_require_not_in_engagement", True)
                    )
                if "stratagem_disembark_override_allow_charge_after_normal_move" in sr:
                    overrides["allow_charge_after_normal_move"] = bool(
                        sr.get("stratagem_disembark_override_allow_charge_after_normal_move", False)
                    )
                if "stratagem_disembark_override_allow_after_advance" in sr:
                    overrides["allow_after_advance"] = bool(
                        sr.get("stratagem_disembark_override_allow_after_advance", False)
                    )
                if "stratagem_disembark_override_force_cannot_charge" in sr:
                    overrides["force_cannot_charge_this_turn"] = bool(
                        sr.get("stratagem_disembark_override_force_cannot_charge", False)
                    )
                if "stratagem_disembark_override_min_enemy_horizontal_distance" in sr:
                    try:
                        min_enemy = float(sr.get("stratagem_disembark_override_min_enemy_horizontal_distance", 0) or 0)
                    except Exception:
                        min_enemy = 0.0
                    if min_enemy > 0:
                        overrides["min_enemy_horizontal_distance"] = float(min_enemy)
        try:
            tsr = getattr(transport_unit, "special_rules", None)
        except Exception:
            tsr = None
        mode_active_fn = getattr(transport_unit, "vanguard_of_dark_city_mode_active", None) if transport_unit is not None else None
        if callable(mode_active_fn) and bool(mode_active_fn("speed_of_the_kill")):
            if bool(getattr(self, "has_any_keyword", lambda *_k: False)("WYCHES")):
                try:
                    current = float(overrides.get("max_distance", 0.0) or 0.0)
                except (TypeError, ValueError):
                    current = 0.0
                overrides["max_distance"] = max(6.0, float(current))
        if isinstance(tsr, dict) and tsr.get("swift_deployment_active"):
            swift_active = True
            exp = str(tsr.get("swift_deployment_expires_phase", "") or "").strip().upper()
            if exp:
                try:
                    phase = getattr(game, "phase", None)
                    phase_name = str(getattr(phase, "name", "") or phase or "").strip().upper()
                except Exception:
                    phase_name = ""
                if phase_name and phase_name != exp:
                    swift_active = False
            owner = str(tsr.get("swift_deployment_turn_owner", "") or "")
            turn = int(tsr.get("swift_deployment_turn", 0) or 0)
            if swift_active and game is not None:
                try:
                    current_player = getattr(game, "get_current_player", lambda: None)()
                except Exception:
                    current_player = None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except Exception:
                    current_turn = 0
                if owner and current_owner and owner != current_owner:
                    swift_active = False
                if turn and current_turn and turn != current_turn:
                    swift_active = False
            if swift_active:
                overrides["allow_after_advance"] = True
        if isinstance(tsr, dict) and tsr.get("cloudstrike_transport_no_charge_disembark"):
            cloudstrike_active = True
            owner = str(tsr.get("cloudstrike_transport_disembark_turn_owner", "") or "")
            turn = int(tsr.get("cloudstrike_transport_disembark_turn", 0) or 0)
            if game is not None:
                try:
                    current_player = getattr(game, "get_current_player", lambda: None)()
                except Exception:
                    current_player = None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except Exception:
                    current_turn = 0
                if owner and current_owner and owner != current_owner:
                    cloudstrike_active = False
                if turn and current_turn and turn != current_turn:
                    cloudstrike_active = False
            if cloudstrike_active:
                overrides["force_cannot_charge_this_turn"] = True
                try:
                    min_enemy = float(tsr.get("cloudstrike_transport_disembark_min_enemy_distance", 0) or 0)
                except Exception:
                    min_enemy = 0.0
                if min_enemy > 0:
                    overrides["min_enemy_horizontal_distance"] = float(min_enemy)
        if isinstance(tsr, dict) and tsr.get("goretrack_full_throttle_assault_active"):
            exp = str(tsr.get("goretrack_full_throttle_assault_expires_phase", "") or "").strip().upper()
            if exp:
                try:
                    phase = getattr(game, "phase", None)
                    phase_name = str(getattr(phase, "name", "") or phase or "").strip().upper()
                except Exception:
                    phase_name = ""
                if phase_name and phase_name != exp:
                    return overrides
            owner = str(tsr.get("goretrack_full_throttle_assault_turn_owner", "") or "")
            turn = int(tsr.get("goretrack_full_throttle_assault_turn", 0) or 0)
            if game is not None:
                try:
                    current_player = getattr(game, "get_current_player", lambda: None)()
                except Exception:
                    current_player = None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except Exception:
                    current_turn = 0
                if owner and current_owner and owner != current_owner:
                    return overrides
                if turn and current_turn and turn != current_turn:
                    return overrides
            overrides["allow_charge_after_normal_move"] = True
        return overrides

    def _apply_aggressive_deployment_scouts(self, transport_unit: Optional['Unit'] = None) -> None:
        if transport_unit is None:
            return
        try:
            if not transport_unit.is_dedicated_transport:
                return
        except Exception:
            return
        has_aggressive_deployment = self._attached_unit_has_enhancement_flag(
            "enhancement_aggressive_deployment",
            enhancement_id="000010086003",
            enhancement_name="aggressive deployment",
        )
        has_herald_of_sacred_slaughter = self._attached_unit_has_enhancement_flag(
            "enhancement_herald_of_sacred_slaughter",
            enhancement_id="000010400005",
            enhancement_name="herald of sacred slaughter",
        )
        if not (has_aggressive_deployment or has_herald_of_sacred_slaughter):
            return
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        scouts_distance = 0.0
        for unit in members:
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            try:
                val = float(sr.get("enhancement_aggressive_deployment_scouts_distance", 0) or 0)
            except Exception:
                val = 0.0
            try:
                val = max(val, float(sr.get("enhancement_herald_of_sacred_slaughter_scouts_distance", 0) or 0))
            except Exception:
                pass
            if val > scouts_distance:
                scouts_distance = val
        if scouts_distance <= 0:
            scouts_distance = 9.0
        sr = getattr(transport_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current = float(sr.get("enhancement_scout_distance", 0) or 0)
        if scouts_distance > current:
            sr["enhancement_scout_distance"] = scouts_distance
        if has_aggressive_deployment:
            sr["enhancement_aggressive_deployment_active"] = True
            sr["enhancement_aggressive_deployment_distance"] = scouts_distance
        if has_herald_of_sacred_slaughter:
            sr["enhancement_herald_of_sacred_slaughter_active"] = True
            sr["enhancement_herald_of_sacred_slaughter_distance"] = scouts_distance
        transport_unit.special_rules = sr

    def disembark(
        self,
        game_map: Optional['Map'] = None,
        transport_unit: Optional['Unit'] = None,
        *,
        destroyed_transport: bool = False,
        emergency: bool = False,
        current_turn: int = 1,
    ) -> bool:
        """
        Disembark (10th edition core rules, best-effort).

        - Normally: set up wholly within 3" of the transport and not within engagement range.
        - If the transport moved normally this phase: this unit counts as having made a Normal move,
          cannot move further this turn; charge eligibility depends on transport rules (e.g. Assault Ramp).
        - Cannot disembark after the transport Advanced or Fell Back this turn unless a rule allows it.
        - Destroyed transport: immediate disembark; mortal wounds; battle-shock; counts as Normal move; cannot charge.
        - Emergency disembarkation (only on destroyed transport when 3" setup is impossible):
          set up wholly within 6"; harsher mortals; models that cannot be set up are destroyed.
        """
        if game_map is None:
            raise RuntimeError("Disembark requires an active game map.")

        if self.round_state.embarked_this_round and not destroyed_transport:
            logger.error(f"ERROR: {self.name} cannot disembark after embarking this turn")
            return False

        if self.round_state.disembarked_this_round:
            return False

        if transport_unit is None:
            transport_unit = self.embarked_in
        if transport_unit is None:
            logger.error(f"ERROR: {self.name} is not embarked in a transport")
            return False

        transport_rules = transport_unit._transport_disembark_rules()
        allow_after_advance = bool(transport_rules.get("allow_after_advance", False))
        allow_charge_after_normal_move = bool(transport_rules.get("allow_charge_after_normal_move", False))
        sr = getattr(transport_unit, "special_rules", None)
        if isinstance(sr, dict) and sr.get("pain_rapid_deployment_active"):
            allow_after_advance = True
        game = None
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        if army is not None and getattr(army, "player", None) is not None:
            game = army.player.game
        overrides = self._disembark_override_rules(transport_unit=transport_unit, game=game)
        if overrides.get("allow_after_advance") is True:
            allow_after_advance = True
        if overrides.get("allow_charge_after_normal_move") is True:
            allow_charge_after_normal_move = True
        force_cannot_charge_from_override = bool(overrides.get("force_cannot_charge_this_turn", False))
        min_enemy_horizontal_distance = None
        if overrides.get("min_enemy_horizontal_distance") is not None:
            try:
                min_enemy_horizontal_distance = float(overrides.get("min_enemy_horizontal_distance"))
            except Exception:
                min_enemy_horizontal_distance = None

        # Transport state restrictions for normal disembark
        if not destroyed_transport:
            if getattr(transport_unit.round_state, "advanced_this_round", False):
                if not allow_after_advance:
                    logger.error(f"ERROR: {self.name} cannot disembark: {transport_unit.name} Advanced this turn")
                    return False
            if getattr(transport_unit.round_state, "fell_back_this_round", False):
                logger.error(f"ERROR: {self.name} cannot disembark: {transport_unit.name} Fell Back this turn")
                return False


        # Determine transport base reference (alive transport uses its current model base)
        transport_base = None
        if transport_unit.models and transport_unit.models[0].is_alive:
            transport_base = transport_unit.models[0].model_base

        if transport_base is None:
            # If transport is destroyed, caller should supply a transport_unit that has a last-known base available
            # via attribute `_last_known_base` (set by Game destroyed transport handler).
            transport_base = getattr(transport_unit, "_last_known_base", None)

        if transport_base is None:
            logger.error(f"ERROR: {self.name} cannot disembark (missing transport position)")
            return False

        # Choose disembark radius
        disembark_distance = 6.0 if emergency else 3.0
        require_not_in_engagement = True
        if not destroyed_transport and not emergency:
            if overrides.get("max_distance") is not None:
                try:
                    disembark_distance = float(overrides.get("max_distance"))
                except Exception:
                    disembark_distance = float(disembark_distance)
            if overrides.get("require_not_in_engagement") is not None:
                require_not_in_engagement = bool(overrides.get("require_not_in_engagement"))

        placements = self._find_disembark_positions(
            transport_base=transport_base,
            game_map=game_map,
            max_distance=disembark_distance,
            require_not_in_engagement=require_not_in_engagement,
            min_enemy_horizontal_distance=min_enemy_horizontal_distance,
        )

        if placements is None and destroyed_transport and not emergency:
            # Try emergency disembarkation
            return self.disembark(
                game_map=game_map,
                transport_unit=transport_unit,
                destroyed_transport=True,
                emergency=True,
                current_turn=current_turn,
            )

        if placements is None:
            if destroyed_transport and emergency:
                # Emergency disembarkation: models that cannot be set up are destroyed (not necessarily the whole unit).
                logger.warning(f"WARN: {self.name} emergency disembarkation: could not place all models within 6\"; destroying any unplaced models")
                alive_models = [m for m in self.models if getattr(m, "is_alive", False)]
                placed_positions: List[Tuple[float, float, float, float]] = []
                placed_models: List[Model] = []
                unplaced_models: List[Model] = []
                for m in alive_models:
                    pos = self._find_single_disembark_position(
                        model=m,
                        transport_base=transport_base,
                        game_map=game_map,
                        max_distance=6.0,
                        placed=placed_positions,
                        require_not_in_engagement=require_not_in_engagement,
                        min_enemy_horizontal_distance=min_enemy_horizontal_distance,
                    )
                    if pos is None:
                        unplaced_models.append(m)
                        continue
                    placed_positions.append(pos)
                    placed_models.append(m)

                # Commit placements (if any)
                for m, pos in zip(placed_models, placed_positions):
                    m.set_location(*pos)

                # Destroy any unplaced models (so they don't interfere with placement validation)
                for m in unplaced_models:
                    m.wounds = 0
                    m.die(game_map=game_map)

                if placed_models:
                    if not game_map.place_unit(self):
                        # If battlefield validation fails, treat as no placements
                        placed_models = []
                        placed_positions = []

                # Remove from passengers list (even if unit ended up destroyed)
                transport_unit.remove_passenger(self)
                if not placed_models:
                    # Nothing could be set up; unit is likely destroyed or cannot disembark at all
                    return False

                # Emergency disembarkation from a destroyed transport still applies destroyed-transport effects
                self.round_state.disembarked_this_round = True
                self.round_state.disembarked_from_transport_id = get_entity_id(transport_unit)
                self.round_state.disembarked_from_destroyed_transport = True
                self.round_state.disembarked_cannot_charge = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
                game = None
                army = self.get_parent_army()
                if army is not None and getattr(army, "player", None) is not None:
                    game = army.player.game
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
                sr = getattr(self, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                if pname:
                    sr["voice_of_command_disembark_phase"] = pname
                    sr["voice_of_command_disembark_round"] = int(getattr(game, "turn", current_turn) or current_turn) if game is not None else int(current_turn or 0)
                self.special_rules = sr
                self._apply_goretrack_onslaught_disembark_effect(game=game, current_turn=current_turn)
                self._apply_murderous_onslaught_disembark_effect(game=game, current_turn=current_turn)
                self._apply_spearhead_striker_disembark_effect(game=game, current_turn=current_turn)
                self._apply_rain_of_cruelty_disembark_effect(game=game, current_turn=current_turn)

                # Battle-shock until next Command phase
                if not self.is_battle_shocked():
                    self.apply_status_effect(BattleShockEffect(current_turn))

                # Mortal wounds on 1-3
                for m in list(self.models):
                    if not getattr(m, "is_alive", False):
                        continue
                    roll = get_roll("D6")
                    if roll <= 3:
                        m.take_damage(1, is_mortal=True, game_map=game_map)

                return True
            logger.error(f"ERROR: {self.name} cannot disembark: no valid placement found")
            return False

        # Commit placements (include attached leaders' models if any)
        placement_models = [m for m in self.get_models_for_collision() if getattr(m, "is_alive", False)]

        for model, pos in zip(placement_models, placements):
            model.set_location(*pos)
        # Add back to map (place_unit validates collisions)
        if not hasattr(game_map, "place_unit"):
            raise RuntimeError("Disembark requires a game map with place_unit().")
        if not game_map.place_unit(self):
            logger.error(f"ERROR: {self.name} disembark failed: map placement validation failed")
            return False

        # Remove from transport passengers list
        transport_unit.remove_passenger(self)

        self.round_state.disembarked_this_round = True
        self.round_state.disembarked_from_transport_id = get_entity_id(transport_unit)
        game = None
        army = self.get_parent_army()
        if army is not None and getattr(army, "player", None) is not None:
            game = army.player.game
        pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if pname:
            sr["voice_of_command_disembark_phase"] = pname
            sr["voice_of_command_disembark_round"] = int(getattr(game, "turn", current_turn) or current_turn) if game is not None else int(current_turn or 0)
        self.special_rules = sr
        self._apply_goretrack_onslaught_disembark_effect(game=game, current_turn=current_turn)
        self._apply_murderous_onslaught_disembark_effect(game=game, current_turn=current_turn)
        self._apply_spearhead_striker_disembark_effect(game=game, current_turn=current_turn)
        self._apply_rain_of_cruelty_disembark_effect(game=game, current_turn=current_turn)

        # Apply moved/charge restrictions depending on cause
        if destroyed_transport:
            self.round_state.disembarked_from_destroyed_transport = True
            self.round_state.disembarked_cannot_charge = True
            self.round_state.moved_this_round = True
            self.round_state.remained_stationary_this_round = False
            # Battle-shock until next Command phase
            if not self.is_battle_shocked():
                self.apply_status_effect(BattleShockEffect(current_turn))
            # Mortal wounds
            # Destroyed transport: on 1 take 1 MW; Emergency: on 1-3 take 1 MW
            threshold = 3 if emergency else 1
            for m in list(self.models):
                if not getattr(m, "is_alive", False):
                    continue
                roll = get_roll("D6")
                if roll <= threshold:
                    m.take_damage(1, is_mortal=True, game_map=game_map)
        else:
            moved_this_round = bool(getattr(transport_unit.round_state, "moved_this_round", False))
            remained_stationary = bool(getattr(transport_unit.round_state, "remained_stationary_this_round", False))
            advanced = bool(getattr(transport_unit.round_state, "advanced_this_round", False))
            fell_back = bool(getattr(transport_unit.round_state, "fell_back_this_round", False))

            if advanced and allow_after_advance:
                # Assault Vehicle: counts as Normal move, cannot charge this turn.
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.disembarked_cannot_charge = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
            elif moved_this_round and not remained_stationary and not advanced and not fell_back:
                # Normal moved transport disembark: counts as Normal move, no further move; charge depends on Assault Ramp.
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
                if not allow_charge_after_normal_move:
                    self.round_state.disembarked_cannot_charge = True

        if force_cannot_charge_from_override:
            self.round_state.disembarked_from_moved_transport = True
            self.round_state.moved_this_round = True
            self.round_state.remained_stationary_this_round = False
            self.round_state.disembarked_cannot_charge = True


        return True

    def validate_disembark_placement(
        self,
        model: 'Model',
        x: float,
        y: float,
        z: float,
        *,
        transport_unit: Optional['Unit'] = None,
        game_map: Optional['Map'] = None,
        max_distance: float = 3.0,
        require_not_in_engagement: bool = True,
        min_enemy_horizontal_distance: Optional[float] = None,
    ) -> dict:
        """Validate manual disembark placement for a single model."""
        if game_map is None:
            return {"valid": False, "reason": "No map context"}
        if transport_unit is None:
            transport_unit = self.embarked_in
        if transport_unit is None:
            return {"valid": False, "reason": "No transport"}
        game = None
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        if army is not None and getattr(army, "player", None) is not None:
            game = army.player.game
        overrides = self._disembark_override_rules(transport_unit=transport_unit, game=game)
        if overrides.get("max_distance") is not None:
            try:
                max_distance = float(overrides.get("max_distance"))
            except Exception:
                pass
        if overrides.get("require_not_in_engagement") is not None:
            require_not_in_engagement = bool(overrides.get("require_not_in_engagement"))
        if overrides.get("min_enemy_horizontal_distance") is not None:
            try:
                min_enemy_horizontal_distance = float(overrides.get("min_enemy_horizontal_distance"))
            except Exception:
                min_enemy_horizontal_distance = None

        transport_base = None
        try:
            if transport_unit.models and transport_unit.models[0].is_alive:
                transport_base = transport_unit.models[0].model_base
        except Exception:
            transport_base = None
        if transport_base is None:
            transport_base = getattr(transport_unit, "_last_known_base", None)
        if transport_base is None:
            return {"valid": False, "reason": "Missing transport position"}

        try:
            facing = float(getattr(getattr(model, "model_base", None), "facing", 0.0) or 0.0)
        except Exception:
            facing = 0.0
        try:
            candidate_base = self._create_potential_base(float(x), float(y), float(z), facing, model=model)
        except Exception:
            return {"valid": False, "reason": "Invalid base"}

        try:
            from ...utility.aura_utils import distance_between_bases_3d
            edge = float(distance_between_bases_3d(candidate_base, transport_base))
            if edge > float(max_distance) + 1e-6:
                return {"valid": False, "reason": "Too far from transport"}
        except Exception:
            return {"valid": False, "reason": "Range check failed"}

        try:
            if not game_map.is_within_boundary(model, destination=(float(x), float(y))):
                return {"valid": False, "reason": "Outside battlefield"}
        except Exception:
            pass
        try:
            if self._check_collision_with_obstacles_or_terrain(game_map, model, (float(x), float(y))):
                return {"valid": False, "reason": "Blocked by terrain"}
        except Exception:
            pass
        try:
            if game_map.check_collision_with_other_friendly_units(model, destination=(float(x), float(y))):
                return {"valid": False, "reason": "Collides with friendly unit"}
        except Exception:
            pass
        try:
            if game_map.check_collision_with_other_enemy_units(model, destination=(float(x), float(y))):
                return {"valid": False, "reason": "Collides with enemy unit"}
        except Exception:
            pass

        min_enemy = 0.0
        try:
            min_enemy = float(min_enemy_horizontal_distance or 0.0)
        except Exception:
            min_enemy = 0.0
        if require_not_in_engagement:
            min_enemy = max(min_enemy, 1.0)
        if min_enemy > 0:
            try:
                from ...utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                for enemy in list(game_map.get_enemy_units(self) or []):
                    try:
                        if not getattr(enemy, "deployed", True):
                            continue
                        if hasattr(enemy, "is_alive") and not enemy.is_alive():
                            continue
                    except Exception:
                        continue
                    try:
                        models = list(enemy.get_models_for_collision() or [])
                    except Exception:
                        models = list(getattr(enemy, "models", []) or [])
                    for em in models:
                        if not getattr(em, "is_alive", True):
                            continue
                        horizontal = float(horizontal_distance_between_bases_2d(candidate_base, em.model_base))
                        if min_enemy_horizontal_distance is not None and float(min_enemy_horizontal_distance or 0.0) > 0:
                            if horizontal <= min_enemy + 1e-6:
                                return {"valid": False, "reason": "Too close to enemy unit"}
                        else:
                            vertical = float(vertical_distance_between_bases(candidate_base, em.model_base))
                            if horizontal <= 1.0 + 1e-6 and vertical <= 5.0 + 1e-6:
                                return {"valid": False, "reason": "Within Engagement Range"}
                        if horizontal <= min_enemy + 1e-6 and min_enemy > 1.0:
                            return {"valid": False, "reason": "Too close to enemy unit"}
            except Exception:
                pass

        return {"valid": True, "reason": "OK"}

    def finalize_manual_disembark(
        self,
        game_map: Optional['Map'] = None,
        transport_unit: Optional['Unit'] = None,
        *,
        destroyed_transport: bool = False,
        emergency: bool = False,
        current_turn: int = 1,
    ) -> bool:
        """Finalize disembark bookkeeping after manual placement."""
        if game_map is None:
            raise RuntimeError("Finalize disembark requires an active game map.")

        if self.round_state.embarked_this_round and not destroyed_transport:
            logger.error(f"ERROR: {self.name} cannot disembark after embarking this turn")
            return False

        if self.round_state.disembarked_this_round:
            return False

        if transport_unit is None:
            transport_unit = self.embarked_in
        if transport_unit is None:
            logger.error(f"ERROR: {self.name} is not embarked in a transport")
            return False

        transport_rules = transport_unit._transport_disembark_rules()
        allow_after_advance = bool(transport_rules.get("allow_after_advance", False))
        allow_charge_after_normal_move = bool(transport_rules.get("allow_charge_after_normal_move", False))
        sr = getattr(transport_unit, "special_rules", None)
        if isinstance(sr, dict) and sr.get("pain_rapid_deployment_active"):
            allow_after_advance = True
        game = None
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        if army is not None and getattr(army, "player", None) is not None:
            game = army.player.game
        overrides = self._disembark_override_rules(transport_unit=transport_unit, game=game)
        if overrides.get("allow_after_advance") is True:
            allow_after_advance = True
        if overrides.get("allow_charge_after_normal_move") is True:
            allow_charge_after_normal_move = True
        force_cannot_charge_from_override = bool(overrides.get("force_cannot_charge_this_turn", False))

        if not destroyed_transport:
            if getattr(transport_unit.round_state, "advanced_this_round", False):
                if not allow_after_advance:
                    logger.error(f"ERROR: {self.name} cannot disembark: {transport_unit.name} Advanced this turn")
                    return False
            if getattr(transport_unit.round_state, "fell_back_this_round", False):
                logger.error(f"ERROR: {self.name} cannot disembark: {transport_unit.name} Fell Back this turn")
                return False

        if self in game_map.units:
            game_map.units.remove(self)

        if not hasattr(game_map, "place_unit"):
            raise RuntimeError("Finalize disembark requires a game map with place_unit().")
        if not game_map.place_unit(self):
            logger.error(f"ERROR: {self.name} disembark failed: map placement validation failed")
            return False

        transport_unit.remove_passenger(self)

        self.round_state.disembarked_this_round = True
        self.round_state.disembarked_from_transport_id = get_entity_id(transport_unit)
        game = None
        army = self.get_parent_army()
        if army is not None and getattr(army, "player", None) is not None:
            game = army.player.game
        pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if pname:
            sr["voice_of_command_disembark_phase"] = pname
            sr["voice_of_command_disembark_round"] = int(getattr(game, "turn", current_turn) or current_turn) if game is not None else int(current_turn or 0)
        self.special_rules = sr
        self._apply_goretrack_onslaught_disembark_effect(game=game, current_turn=current_turn)
        self._apply_murderous_onslaught_disembark_effect(game=game, current_turn=current_turn)
        self._apply_spearhead_striker_disembark_effect(game=game, current_turn=current_turn)
        self._apply_rain_of_cruelty_disembark_effect(game=game, current_turn=current_turn)

        if destroyed_transport:
            self.round_state.disembarked_from_destroyed_transport = True
            self.round_state.disembarked_cannot_charge = True
            self.round_state.moved_this_round = True
            self.round_state.remained_stationary_this_round = False
            if not self.is_battle_shocked():
                self.apply_status_effect(BattleShockEffect(current_turn))
            threshold = 3 if emergency else 1
            for m in list(self.models):
                if not getattr(m, "is_alive", False):
                    continue
                roll = get_roll("D6")
                if roll <= threshold:
                    m.take_damage(1, is_mortal=True, game_map=game_map)
        else:
            moved_this_round = bool(getattr(transport_unit.round_state, "moved_this_round", False))
            remained_stationary = bool(getattr(transport_unit.round_state, "remained_stationary_this_round", False))
            advanced = bool(getattr(transport_unit.round_state, "advanced_this_round", False))
            fell_back = bool(getattr(transport_unit.round_state, "fell_back_this_round", False))

            if advanced and allow_after_advance:
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.disembarked_cannot_charge = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
            elif moved_this_round and not remained_stationary and not advanced and not fell_back:
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
                if not allow_charge_after_normal_move:
                    self.round_state.disembarked_cannot_charge = True

        if force_cannot_charge_from_override:
            self.round_state.disembarked_from_moved_transport = True
            self.round_state.moved_this_round = True
            self.round_state.remained_stationary_this_round = False
            self.round_state.disembarked_cannot_charge = True

        return True
