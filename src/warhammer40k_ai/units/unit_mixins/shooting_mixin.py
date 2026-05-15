"""Auto-extracted Unit mixin methods from unit.py."""

from ._common import *
from collections import OrderedDict
import logging
logger = logging.getLogger(__name__)


_SHOOTING_LOS_CACHE_MAX = 8192
_SHOOTING_LOS_GEOMETRY_CACHE_MAX = 8192
_SHOOTING_LOS_SAMPLE_CACHE_MAX = 8192


def _unit_disembarked_in_current_phase(unit: object, game: object | None) -> bool:
    round_state = getattr(unit, "round_state", None)
    if not bool(getattr(round_state, "disembarked_this_round", False)):
        return False
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        return True
    disembark_phase = str(sr.get("voice_of_command_disembark_phase", "") or "").strip().upper()
    if not disembark_phase or game is None:
        return True
    current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
    if current_phase and current_phase != disembark_phase:
        return False

    try:
        disembark_round = int(sr.get("voice_of_command_disembark_round", 0) or 0)
    except (TypeError, ValueError):
        disembark_round = 0
    if disembark_round > 0:
        try:
            current_round = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_round = 0
        if current_round > 0 and current_round != disembark_round:
            return False

    disembark_owner = str(sr.get("voice_of_command_disembark_owner", "") or "").strip()
    if disembark_owner:
        current_player_getter = getattr(game, "get_current_player", None)
        current_player = current_player_getter() if callable(current_player_getter) else None
        current_owner = str(getattr(current_player, "id", "") or "").strip()
        if current_owner and current_owner != disembark_owner:
            return False
    return True


def _shooting_entity_id(entity: object | None) -> str:
    if entity is None:
        return ""
    try:
        return str(get_entity_id(entity) or "")
    except ValueError:
        return ""


def _shooting_declaration_diagnostic(
    *,
    target_unit: object | None,
    weapon_profile: object | None,
    models: object,
    reason: str = "",
    attacks_executed: int | None = None,
) -> dict:
    model_list = list(models or [])
    row = {
        "target_unit_id": _shooting_entity_id(target_unit),
        "weapon_profile_id": _shooting_entity_id(weapon_profile),
        "weapon_profile_name": str(getattr(weapon_profile, "name", "") or ""),
        "model_count": len(model_list),
        "model_ids": [_shooting_entity_id(model) for model in model_list if model is not None],
        "reason": str(reason or ""),
    }
    if attacks_executed is not None:
        row["attacks_executed"] = int(attacks_executed or 0)
    return row


def _shooting_los_entity_key(entity: object | None) -> str:
    if entity is None:
        return ""
    value = getattr(entity, "id", None) or getattr(entity, "_id", None)
    return str(value or id(entity))


def _shooting_los_alive(entity: object) -> bool:
    alive = getattr(entity, "is_alive", True)
    return bool(alive() if callable(alive) else alive)


def _shooting_los_model_key(model: object) -> tuple:
    base = getattr(model, "model_base", None)
    if base is None:
        return (_shooting_los_entity_key(model), _shooting_los_alive(model), None)
    radius = getattr(base, "radius", None)
    if isinstance(radius, (list, tuple)):
        radius_key = tuple(round(float(value), 4) for value in radius)
    else:
        try:
            radius_key = round(float(radius), 4)
        except (TypeError, ValueError):
            radius_key = None
    return (
        _shooting_los_entity_key(model),
        _shooting_los_alive(model),
        round(float(getattr(base, "x", 0.0) or 0.0), 4),
        round(float(getattr(base, "y", 0.0) or 0.0), 4),
        round(float(getattr(base, "z", 0.0) or 0.0), 4),
        round(float(getattr(base, "facing", 0.0) or 0.0), 4),
        str(getattr(getattr(base, "base_type", None), "name", "") or ""),
        radius_key,
    )


def _shooting_los_unit_key(unit: object | None) -> tuple:
    if unit is None:
        return ("",)
    model_rows = tuple(
        _shooting_los_model_key(model)
        for model in list(getattr(unit, "models", []) or [])
        if _shooting_los_alive(model)
    )
    return (
        _shooting_los_entity_key(unit),
        _shooting_los_alive(unit),
        bool(getattr(unit, "deployed", True)),
        bool(getattr(unit, "is_aircraft", False)),
        bool(getattr(unit, "is_towering", False)),
        model_rows,
    )


def _shooting_los_bounds(value: object) -> tuple[float, float, float, float]:
    bounds = tuple(getattr(value, "bounds", ()) or ())
    if len(bounds) != 4:
        return (0.0, 0.0, 0.0, 0.0)
    return tuple(round(float(item), 4) for item in bounds)  # type: ignore[return-value]


def _shooting_los_terrain_key(game_map: object) -> tuple:
    rows: list[tuple] = []
    for terrain in list(getattr(game_map, "terrain_features", []) or []):
        wall_rows: list[tuple] = []
        for wall in list(getattr(terrain, "walls", []) or []):
            if not isinstance(wall, dict):
                continue
            wall_rows.append(
                (
                    _shooting_los_bounds(wall.get("polygon")),
                    round(float(wall.get("z_bottom", 0.0) or 0.0), 4),
                    round(float(wall.get("z_top", wall.get("z_bottom", 0.0)) or 0.0), 4),
                )
            )
        opening_rows: list[tuple] = []
        for opening in list(getattr(terrain, "openings", []) or []):
            if not isinstance(opening, dict):
                continue
            opening_rows.append(
                (
                    _shooting_los_bounds(opening.get("polygon")),
                    round(float(opening.get("z_bottom", 0.0) or 0.0), 4),
                    round(float(opening.get("z_top", 0.0) or 0.0), 4),
                    bool(opening.get("allows_los", False)),
                )
            )
        rows.append(
            (
                str(getattr(terrain, "id", "") or id(terrain)),
                str(getattr(getattr(terrain, "terrain_type", None), "name", "") or ""),
                _shooting_los_bounds(getattr(terrain, "footprint", None)),
                round(float(getattr(terrain, "height", 0.0) or 0.0), 4),
                round(float(getattr(terrain, "rim_height", 0.0) or 0.0), 4),
                tuple(sorted(wall_rows, key=lambda item: str(item))),
                tuple(sorted(opening_rows, key=lambda item: str(item))),
            )
        )
    return tuple(sorted(rows, key=lambda item: str(item[0])))


def _shooting_los_blocker_key(game_map: object, shooter_unit: object, target_unit: object) -> tuple:
    get_enemy_units = getattr(game_map, "get_enemy_units", None)
    enemy_units = list(get_enemy_units(shooter_unit) or []) if callable(get_enemy_units) else []
    rows: list[tuple] = []
    target_id = _shooting_los_entity_key(target_unit)
    for enemy_unit in enemy_units:
        if _shooting_los_entity_key(enemy_unit) == target_id:
            continue
        rows.append(_shooting_los_unit_key(enemy_unit))
    return tuple(sorted(rows, key=lambda item: str(item[0])))


def _shooting_los_cache_key(shooter_unit: object, shooting_model: object, target_unit: object, game_map: object) -> tuple:
    return (
        "shooting_los_v1",
        id(game_map),
        _shooting_los_entity_key(shooter_unit),
        _shooting_los_model_key(shooting_model),
        _shooting_los_unit_key(target_unit),
        _shooting_los_blocker_key(game_map, shooter_unit, target_unit),
        _shooting_los_terrain_key(game_map),
    )


def _shooting_los_cache(game_map: object) -> OrderedDict:
    cache = getattr(game_map, "_shooting_los_cache", None)
    if isinstance(cache, OrderedDict):
        return cache
    cache = OrderedDict()
    try:
        setattr(game_map, "_shooting_los_cache", cache)
    except (AttributeError, TypeError):
        pass
    return cache


def _shooting_los_cache_get(game_map: object, key: tuple) -> bool | None:
    cache = _shooting_los_cache(game_map)
    if key not in cache:
        return None
    cache.move_to_end(key)
    return bool(cache[key])


def _shooting_los_cache_set(game_map: object, key: tuple, value: bool) -> None:
    cache = _shooting_los_cache(game_map)
    cache[key] = bool(value)
    cache.move_to_end(key)
    while len(cache) > _SHOOTING_LOS_CACHE_MAX:
        cache.popitem(last=False)


def _shooting_ordered_map_cache(game_map: object, attr_name: str) -> OrderedDict:
    cache = getattr(game_map, attr_name, None)
    if isinstance(cache, OrderedDict):
        return cache
    cache = OrderedDict()
    try:
        setattr(game_map, attr_name, cache)
    except (AttributeError, TypeError):
        pass
    return cache


def _shooting_los_geometry_cache(game_map: object) -> OrderedDict:
    return _shooting_ordered_map_cache(game_map, "_shooting_los_geometry_cache")


def _shooting_los_sample_cache(game_map: object) -> OrderedDict:
    return _shooting_ordered_map_cache(game_map, "_shooting_los_sample_cache")


class ShootingMixin:
    def can_shoot_out_of_phase_at_target(self, target_unit, game_map: 'Map') -> bool:
        """Return whether this unit can currently make any ranged attacks into the target out of phase."""
        if target_unit is None or game_map is None:
            return False
        if not self.is_alive() or not target_unit.is_alive():
            return False

        if bool(getattr(getattr(self, "round_state", None), "action_locked_until_turn_end", False)):
            army = self.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            allow_shoot_while_action = False
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            allow_seekers_companions = (
                getattr(sm_mgr, "seekers_companions_allow_shoot_while_action", None)
                if sm_mgr is not None
                else None
            )
            if callable(allow_seekers_companions):
                allow_shoot_while_action = bool(
                    allow_seekers_companions(
                        self,
                        game=game,
                    )
                )
            if not allow_shoot_while_action:
                allow_fn = getattr(self, "allows_shoot_while_started_action_from_unit_contains_rule", None)
                if callable(allow_fn):
                    allow_shoot_while_action = bool(allow_fn(game=game))
            if not allow_shoot_while_action:
                return False

        if bool(getattr(self, "_reserves_edge_touch_this_turn", False)) and bool(
            getattr(self, "arrived_from_reserves_this_turn", False)
        ):
            return False

        get_models = getattr(self, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(self, "models", []) or [])
        for model in models:
            if not bool(getattr(model, "is_alive", False)):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                if not wargear.is_ranged():
                    continue
                profiles = getattr(wargear, "profiles", {}) or {}
                for profile in list(profiles.values()):
                    if profile is None:
                        continue
                    validation = self._validate_shooting_declaration(profile, target_unit, [model], game_map)
                    if bool(validation.get("valid", False)):
                        return True
        return False

    def _resolve_selected_shooting_target_reactions(self, game, target_units) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if not list(target_units or []):
            return
        try:
            attacking_player = self.get_parent_army().player
        except (AttributeError, RuntimeError, TypeError, ValueError):
            attacking_player = None
        reacting_players = [
            player
            for player in list(getattr(game, "players", []) or [])
            if player is not None and player is not attacking_player
        ]
        if not reacting_players:
            return

        prior_depth = int(getattr(game, "_pre_attack_reaction_window_depth", 0) or 0)
        setattr(game, "_pre_attack_reaction_window_depth", prior_depth + 1)
        try:
            max_passes = max(1, len(reacting_players) * 4)
            for _pass_index in range(max_passes):
                queued_any = False
                for player in reacting_players:
                    manager = getattr(player, "stratagems", None)
                    queue_reaction_decision = getattr(manager, "queue_headless_tool_action_decision", None)
                    if not callable(queue_reaction_decision):
                        continue
                    if bool(queue_reaction_decision(reactions_only=True)):
                        queued_any = True
                if not queued_any:
                    break
        finally:
            if prior_depth > 0:
                setattr(game, "_pre_attack_reaction_window_depth", prior_depth)
            elif hasattr(game, "_pre_attack_reaction_window_depth"):
                delattr(game, "_pre_attack_reaction_window_depth")

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

        ignore_engagement_active = False
        try:
            ignore_engagement_active = bool(self._ignore_engagement_for_ranged_targeting_active())
        except Exception:
            ignore_engagement_active = False
        all_is_rot_active = self._death_guard_all_is_rot_active()

        # BGNT hit modifier snapshot:
        # When a VEHICLE/MONSTER makes ranged attacks and it was Locked in Combat when it selected targets,
        # apply -1 to Hit (unless Pistols). Snapshot this now so casualties later don't change it mid-activation.
        try:
            bgnt_locked_at_selection = bool((self.is_vehicle or self.is_monster) and self._is_controlling_players_shooting_phase() and self._is_locked_in_combat(game_map))
            if ignore_engagement_active or all_is_rot_active:
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
            if engaged and (ignore_engagement_active or all_is_rot_active):
                engaged = False

            # Build per-model "has pistol decl" and "has other decl"
            by_model: dict[str, dict[str, bool]] = {}
            for decl in weapon_declarations:
                wp = decl.get("weapon_profile")
                if wp is None:
                    continue
                for m in decl.get("models") or []:
                    if not getattr(m, "is_alive", False):
                        continue
                    is_pistol = bool(self.weapon_profile_counts_as_pistol(wp, model=m))
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
                keep_models = []
                removed = 0
                for m in decl.get("models") or []:
                    if not getattr(m, "is_alive", False):
                        removed += 1
                        continue
                    wp_is_pistol = bool(self.weapon_profile_counts_as_pistol(wp, model=m))
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

        weapon_declarations = self._expand_tau_droneport_shooting_declarations(
            weapon_declarations,
            game_map=game_map,
        )
        if not weapon_declarations:
            logger.info(f"{self.name}: No legal shooting declarations to execute")
            return False

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
        damage_by_target = {}
        damage_by_target_while_engaged = {}
        executed_declarations = []
        skipped_declarations = []
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
                        self._resolve_selected_shooting_target_reactions(game, touched_targets)
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
                try:
                    army = self.get_parent_army()
                except Exception:
                    army = None
                acts_mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                on_select = getattr(acts_mgr, "on_shoot_unit_selected", None) if acts_mgr is not None else None
                if callable(on_select):
                    selecting_player = getattr(army, "player", None) if army is not None else None
                    try:
                        on_select(self, game=game, selecting_player=selecting_player)
                    except Exception:
                        pass
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
            "damage_by_target": damage_by_target,
            "damage_by_target_while_engaged": damage_by_target_while_engaged,
        }
        sorrowsyphon_triggered = False
        sorrowsyphon_note_fn = None
        sorrowsyphon_consume_fn = None
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        try:
            dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
            sorrowsyphon_note_fn = (
                getattr(dg_mgr, "shamblerot_note_sorrowsyphon_plague_wind_attacks", None)
                if dg_mgr is not None
                else None
            )
            sorrowsyphon_consume_fn = (
                getattr(dg_mgr, "shamblerot_consume_sorrowsyphon_bodyguard_loss", None)
                if dg_mgr is not None
                else None
            )
        except Exception:
            sorrowsyphon_note_fn = None
            sorrowsyphon_consume_fn = None
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
                executed_declarations.append(
                    _shooting_declaration_diagnostic(
                        target_unit=target_unit,
                        weapon_profile=weapon_profile,
                        models=models_with_weapon,
                        reason="plasma_warhead",
                        attacks_executed=int(weapon_attacks or 0),
                    )
                )
                continue
            try:
                within_engagement = getattr(game_map, "is_within_engagement_range", None) if game_map is not None else None
                target_was_within_attacker_engagement = bool(
                    target_unit is not None and callable(within_engagement) and within_engagement(self, target_unit)
                )
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
                    skipped_declarations.append(
                        _shooting_declaration_diagnostic(
                            target_unit=target_unit,
                            weapon_profile=weapon_profile,
                            models=models_with_weapon,
                            reason=str(validation.get("reason", "") or ""),
                        )
                    )
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
                    target_was_within_attacker_engagement=target_was_within_attacker_engagement,
                )
                successful_attacks += weapon_attacks
                executed_declarations.append(
                    _shooting_declaration_diagnostic(
                        target_unit=target_unit,
                        weapon_profile=weapon_profile,
                        models=models_with_weapon,
                        reason="executed",
                        attacks_executed=int(weapon_attacks or 0),
                    )
                )
                if (
                    int(weapon_attacks or 0) > 0
                    and (not sorrowsyphon_triggered)
                    and callable(sorrowsyphon_note_fn)
                ):
                    try:
                        sorrowsyphon_triggered = bool(
                            sorrowsyphon_note_fn(
                                self,
                                weapon_declarations=[declaration],
                                game=game,
                            )
                        )
                    except Exception:
                        sorrowsyphon_triggered = sorrowsyphon_triggered
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

        if sorrowsyphon_triggered and callable(sorrowsyphon_consume_fn):
            try:
                game_for_loss = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game_for_loss = None
            try:
                loss_count, loss_source, _source_unit, bodyguard_root = sorrowsyphon_consume_fn(
                    self,
                    game=game_for_loss,
                )
            except Exception:
                loss_count, loss_source, _source_unit, bodyguard_root = 0, "", None, None
            if int(loss_count or 0) > 0 and bodyguard_root is not None:
                alive_models = []
                for model in list(getattr(bodyguard_root, "models", []) or []):
                    alive_attr = getattr(model, "is_alive", False)
                    model_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    if model_alive:
                        alive_models.append(model)
                alive_models.sort(key=lambda m: str(get_entity_id(m) or ""))
                models_to_destroy = list(alive_models[: int(loss_count)])
                for doomed in models_to_destroy:
                    try:
                        bodyguard_root.remove_model(doomed, game_map=getattr(game_for_loss, "map", None))
                    except Exception:
                        continue
                try:
                    from ...utility.event_bus import append_action
                    player = getattr(bodyguard_root.get_parent_army(), "player", None)
                    source_name = str(loss_source or "Sorrowsyphon").strip() or "Sorrowsyphon"
                    append_action(
                        player,
                        f"{source_name}: {len(models_to_destroy)} bodyguard model(s) destroyed in {getattr(bodyguard_root, 'name', 'unit')}.",
                    )
                except Exception:
                    pass

        try:
            game = self.get_parent_army().player.game
            if game is not None and hasattr(game, "event_system"):
                declared_targets = []
                declared_seen = set()
                for target in list(touched_targets or []):
                    if target is None:
                        continue
                    try:
                        target_root = target.get_attached_unit_root()
                    except Exception:
                        target_root = target
                    target_id = get_entity_id(target_root)
                    if target_id in declared_seen:
                        continue
                    declared_seen.add(target_id)
                    declared_targets.append(target_root)
                game.event_system.publish(
                    "unit_shooting_resolved",
                    attacker_unit=self,
                    hits_by_target=dict(hit_tracker),
                    hit_models_by_target=dict(hit_models_by_target),
                    killing_models_by_target=dict(killing_models_by_target),
                    hit_models_by_target_weapon=dict(hit_models_by_target_weapon),
                    hit_models_by_target_psychic=dict(hit_models_by_target_psychic),
                    damage_by_target=dict(damage_by_target),
                    damage_by_target_while_engaged=dict(damage_by_target_while_engaged),
                    declared_targets=list(declared_targets),
                    successful_attacks=int(successful_attacks or 0),
                    declaration_count=len(list(weapon_declarations or [])),
                    executed_declarations=list(executed_declarations),
                    skipped_declarations=list(skipped_declarations),
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
            reason_counts = {}
            for row in list(skipped_declarations or []):
                reason = str(row.get("reason", "") or "unknown")
                reason_counts[reason] = int(reason_counts.get(reason, 0) or 0) + 1
            if reason_counts:
                logger.warning(
                    "%s resolved shooting with no executable attacks; skipped declarations by reason: %s",
                    self.name,
                    reason_counts,
                )
            elif executed_declarations:
                zero_attack_weapons = [
                    str(row.get("weapon_profile_name", "") or "unknown")
                    for row in list(executed_declarations or [])
                    if int(row.get("attacks_executed", 0) or 0) <= 0
                ]
                logger.warning(
                    "%s resolved shooting with no executable attacks; zero-attack declarations: %s",
                    self.name,
                    zero_attack_weapons,
                )
            else:
                logger.warning(f"{self.name} resolved shooting with no executable attacks")
            
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

    def _death_guard_all_is_rot_active(self) -> bool:
        root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
        iterator = getattr(root, "iter_active_death_guard_temp_effects", None)
        if not callable(iterator):
            return False
        return any(
            iterator(
                effect_type="all_is_rot",
                attack_type="any",
                require_target_match=False,
            )
        )

    def _death_guard_target_locked_only_by_shooter(self, target_unit, game_map) -> bool:
        if target_unit is None or game_map is None:
            return False
        shooter_root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
        shooter_root_id = str(get_entity_id(shooter_root) or "")
        enemy_units = list(game_map.get_enemy_units(target_unit) or [])
        seen_enemy_roots: set[str] = set()
        for enemy in enemy_units:
            enemy_root = enemy.get_attached_unit_root() if hasattr(enemy, "get_attached_unit_root") else enemy
            if enemy_root is None:
                continue
            enemy_root_id = str(get_entity_id(enemy_root) or "")
            if enemy_root_id and enemy_root_id in seen_enemy_roots:
                continue
            if enemy_root_id:
                seen_enemy_roots.add(enemy_root_id)
            if not game_map.is_within_engagement_range(enemy_root, target_unit):
                continue
            if shooter_root is not None and enemy_root is shooter_root:
                continue
            if shooter_root_id and enemy_root_id == shooter_root_id:
                continue
            return False
        return True

    @staticmethod
    def _droneport_norm(text: object) -> str:
        norm = str(text or "").replace("\u2019", "'").lower()
        norm = re.sub(r"[^a-z0-9]+", " ", norm)
        return re.sub(r"\s+", " ", norm).strip()

    def _has_tau_droneport_ability(self) -> bool:
        cache = getattr(self, "_ability_cache", None)
        cache_key = "tau_droneport_ability"
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache[cache_key])

        abilities = list(getattr(self, "possible_abilities", []) or [])
        iter_active = getattr(self, "_iter_active_possible_abilities", None)
        if callable(iter_active):
            abilities = list(iter_active() or [])

        found = False
        for ability in abilities:
            if isinstance(ability, str):
                ability_name = str(ability or "")
                ability_desc = ""
            else:
                ability_name = str(getattr(ability, "name", "") or "")
                ability_desc = str(getattr(ability, "description", "") or "")
            name_norm = self._droneport_norm(ability_name)
            desc_norm = self._droneport_norm(ability_desc)
            if name_norm == "droneport":
                found = True
                break
            if (
                "each time this fortification is selected to shoot" in desc_norm
                and "drone defender" in desc_norm
                and "every enemy unit" in desc_norm
                and "eligible target" in desc_norm
            ):
                found = True
                break

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = bool(found)
        self._ability_cache = cache
        return bool(found)

    def _is_tau_drone_defender_profile(self, weapon_profile) -> bool:
        if weapon_profile is None:
            return False
        parent = getattr(weapon_profile, "parent_wargear", None)
        weapon_name = str(getattr(parent, "name", "") or getattr(weapon_profile, "name", "") or "")
        return "drone defender" in self._droneport_norm(weapon_name)

    def _tau_droneport_declaration_key(self, declaration: dict) -> tuple:
        weapon_profile = declaration.get("weapon_profile")
        parent = getattr(weapon_profile, "parent_wargear", None) if weapon_profile is not None else None
        weapon_name = self._droneport_norm(
            str(getattr(parent, "name", "") or getattr(weapon_profile, "name", "") or "")
        )
        profile_name = self._droneport_norm(str(getattr(weapon_profile, "name", "") or ""))
        model_ids = tuple(
            sorted(
                str(get_entity_id(model) or "")
                for model in list(declaration.get("models") or [])
                if model is not None
            )
        )
        firing_deck_source_ids = tuple(
            sorted(
                str(get_entity_id(model) or "")
                for model in list(declaration.get("firing_deck_source_models") or [])
                if model is not None
            )
        )
        linked_fire_origin = declaration.get("linked_fire_origin_unit")
        linked_fire_origin_id = (
            str(get_entity_id(linked_fire_origin) or "") if linked_fire_origin is not None else ""
        )
        linked_fire_mode = str(declaration.get("linked_fire_mode", "") or "").strip().lower()
        weapon_instance = str(declaration.get("weapon_instance", "") or "")
        return (
            weapon_name,
            profile_name,
            model_ids,
            firing_deck_source_ids,
            linked_fire_origin_id,
            linked_fire_mode,
            weapon_instance,
        )

    def _expand_tau_droneport_shooting_declarations(
        self,
        weapon_declarations: List[dict],
        *,
        game_map: 'Map',
    ) -> List[dict]:
        if not weapon_declarations or not self._has_tau_droneport_ability():
            return weapon_declarations
        get_enemy_units = getattr(game_map, "get_enemy_units", None) if game_map is not None else None
        if not callable(get_enemy_units):
            return weapon_declarations

        enemy_units = [unit for unit in list(get_enemy_units(self) or []) if unit is not None]
        if not enemy_units:
            return weapon_declarations
        enemy_units = sorted(enemy_units, key=lambda unit: str(get_entity_id(unit) or ""))

        expanded = list(weapon_declarations)
        template_by_key: dict[tuple, dict] = {}
        seen_targets_by_key: dict[tuple, set[str]] = {}

        for declaration in list(weapon_declarations):
            weapon_profile = declaration.get("weapon_profile")
            if not self._is_tau_drone_defender_profile(weapon_profile):
                continue
            key = self._tau_droneport_declaration_key(declaration)
            if key not in template_by_key:
                template_by_key[key] = declaration
            target_unit = declaration.get("target_unit")
            if target_unit is not None:
                seen_targets_by_key.setdefault(key, set()).add(str(get_entity_id(target_unit) or ""))

        for key in sorted(template_by_key.keys(), key=str):
            template = template_by_key[key]
            weapon_profile = template.get("weapon_profile")
            models = list(template.get("models") or [])
            if weapon_profile is None or not models:
                continue
            seen_targets = seen_targets_by_key.setdefault(key, set())
            for enemy_unit in enemy_units:
                enemy_id = str(get_entity_id(enemy_unit) or "")
                if not enemy_id or enemy_id in seen_targets:
                    continue
                validation = self._validate_shooting_declaration(
                    weapon_profile,
                    enemy_unit,
                    models,
                    game_map,
                    linked_fire_origin_unit=template.get("linked_fire_origin_unit"),
                    linked_fire_mode=template.get("linked_fire_mode"),
                )
                if not bool((validation or {}).get("valid", False)):
                    continue
                extra_decl = dict(template)
                extra_decl["target_unit"] = enemy_unit
                expanded.append(extra_decl)
                seen_targets.add(enemy_id)

        return expanded

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

    def _space_marines_bastion_heresy_undone_target_restriction_reason(self, target_unit, *, game=None) -> str:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        requires_fn = getattr(sm_mgr, "heresy_undone_requires_auspex_targets", None) if sm_mgr is not None else None
        legal_fn = getattr(sm_mgr, "heresy_undone_target_is_legal", None) if sm_mgr is not None else None
        if not callable(requires_fn) or not callable(legal_fn):
            return ""
        if not requires_fn(self, game=game):
            return ""
        if legal_fn(self, target_unit, game=game):
            return ""
        return "Heresy Undone: target must be an auspex scanned unit after Advancing or Falling Back"

    def _adeptus_mechanicus_auto_divinatory_target_restriction_reason(self, target_unit, *, game=None) -> str:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        adm_mgr = getattr(army, "adeptus_mechanicus_detachments", None) if army is not None else None
        requires_fn = (
            getattr(adm_mgr, "auto_divinatory_targeting_requires_objective_targets", None)
            if adm_mgr is not None
            else None
        )
        legal_fn = getattr(adm_mgr, "auto_divinatory_targeting_target_is_legal", None) if adm_mgr is not None else None
        if not callable(requires_fn) or not callable(legal_fn):
            return ""
        if not requires_fn(self, game=game):
            return ""
        if legal_fn(self, target_unit, game=game):
            return ""
        return "Auto-divinatory Targeting: target must be within range of the selected objective marker"

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
        reason = self._space_marines_bastion_heresy_undone_target_restriction_reason(target_unit, game=game)
        if reason:
            return {"valid": False, "reason": reason}
        reason = self._adeptus_mechanicus_auto_divinatory_target_restriction_reason(target_unit, game=game)
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
            if not self._model_has_weapon_profile(model, weapon_profile):
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
            within_engagement = getattr(game_map, "is_within_engagement_range", None) if game_map is not None else None
            target_was_within_attacker_engagement = bool(
                target_unit is not None and callable(within_engagement) and within_engagement(self, target_unit)
            )
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
                target_was_within_attacker_engagement=target_was_within_attacker_engagement,
            )
            if attack_context is not None:
                self._resolve_pending_attack_mortal_wounds(attack_context, target_unit, game_map=game_map)

        for model in eligible_models:
            self._mark_one_shot_used(model, one_shot_key)
        deathstrike_mgr.mark_deathstrike_fired(unit_id)
        return successful_attacks
    

    def _can_model_shoot_weapon_at_target(
        self,
        model,
        weapon_profile,
        target_unit,
        game_map,
        *,
        origin_unit=None,
        ignore_helhunt_target_lock: bool = False,
    ) -> bool:
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
        try:
            if self._space_marines_bastion_heresy_undone_target_restriction_reason(target_unit, game=game):
                return False
        except Exception:
            pass
        try:
            if self._adeptus_mechanicus_auto_divinatory_target_restriction_reason(target_unit, game=game):
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
        lock_check = getattr(root, "_gsc_symbiotic_destruction_target_locked_to", None)
        if callable(lock_check) and not bool(lock_check(target_unit, game=game)):
            return False
        lock_check = getattr(root, "_helhunt_merciless_fusillade_target_locked_to", None)
        if (
            not bool(ignore_helhunt_target_lock)
            and callable(lock_check)
            and not bool(lock_check(target_unit, game=game, attack_type="ranged"))
        ):
            return False
        lock_check = getattr(root, "_space_marines_hunter_marked_for_destruction_target_locked_to", None)
        if callable(lock_check) and not bool(lock_check(target_unit, game=game)):
            return False
        lock_check = getattr(root, "_adeptus_custodes_witch_hunters_target_locked_to", None)
        if callable(lock_check) and not bool(lock_check(target_unit, game=game, attack_type="ranged")):
            return False
        lock_check = getattr(root, "_adeptus_custodes_talons_interlocked_target_locked_to", None)
        if callable(lock_check) and not bool(lock_check(target_unit, game=game, attack_type="ranged")):
            return False
        acceptable_losses_target = False
        try:
            allow_target = getattr(root, "_gsc_acceptable_losses_allows_target", None)
            if callable(allow_target):
                acceptable_losses_target = bool(allow_target(target_unit, game=game))
        except Exception:
            acceptable_losses_target = False

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
        is_siege_shield_demolisher = has_siege_shield and ("demolisher" in weapon_name and "cannon" in weapon_name)
        ignore_engagement_active = False
        try:
            if hasattr(self, "_ignore_engagement_for_ranged_targeting_active"):
                ignore_engagement_active = bool(self._ignore_engagement_for_ranged_targeting_active())
        except Exception:
            ignore_engagement_active = False
        ceaseless_cannonade_targeting_active = False
        army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
        if army is not None:
            am_mgr = getattr(army, "astra_militarum_detachments", None)
            ceaseless_fn = getattr(am_mgr, "ceaseless_cannonade_allows_ranged_target", None) if am_mgr is not None else None
            if callable(ceaseless_fn):
                game = getattr(getattr(army, "player", None), "game", None)
                ceaseless_cannonade_targeting_active = bool(
                    ceaseless_fn(
                        self,
                        target_unit,
                        weapon_profile=weapon_profile,
                        game=game,
                        game_map=game_map,
                    )
                )
        all_is_rot_active = self._death_guard_all_is_rot_active()
        fortification_only = False
        if target_locked:
            try:
                fortification_only = bool(target_unit.is_only_within_enemy_fortifications(game_map, enemy_unit=self))
            except Exception:
                fortification_only = False
        if target_locked and not fortification_only and all_is_rot_active:
            if self._death_guard_target_locked_only_by_shooter(target_unit, game_map):
                target_locked = False
        if target_locked and not fortification_only and ignore_engagement_active:
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
            try:
                army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
                ia_mgr = getattr(army, "imperial_agents_detachments", None) if army is not None else None
                line_of_fire_fn = getattr(ia_mgr, "line_of_fire_allows_ranged_target", None) if ia_mgr is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if callable(line_of_fire_fn) and bool(
                    line_of_fire_fn(
                        self,
                        target_unit,
                        weapon_profile=weapon_profile,
                        game=game,
                        game_map=game_map,
                    )
                ):
                    target_locked = False
            except Exception:
                pass
        if target_locked and ceaseless_cannonade_targeting_active:
            target_locked = False
        if target_locked and acceptable_losses_target:
            target_locked = False
        if target_locked and not fortification_only:
            shooter_in_er_of_target = game_map.is_within_engagement_range(self, target_unit)
            if ignore_engagement_active or all_is_rot_active:
                shooter_in_er_of_target = False
            if self.weapon_profile_counts_as_pistol(weapon_profile, model=model):
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
                if all_is_rot_active:
                    if shooter_root is not None and friendly_root is shooter_root:
                        continue
                elif ignore_engagement_active or ceaseless_cannonade_targeting_active:
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

        try:
            target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        except Exception:
            target_root = target_unit
        try:
            target_sr = getattr(target_root, "special_rules", None)
            if isinstance(target_sr, dict) and bool(target_sr.get("custodes_null_maiden_psychic_abominations_active")):
                expected_phase = str(
                    target_sr.get("custodes_null_maiden_psychic_abominations_expires_phase", "") or ""
                ).strip().upper()
                current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
                effect_active = not expected_phase or not current_phase or expected_phase == current_phase
                try:
                    effect_turn = int(target_sr.get("custodes_null_maiden_psychic_abominations_turn", 0) or 0)
                except (TypeError, ValueError):
                    effect_turn = 0
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                except (TypeError, ValueError):
                    current_turn = 0
                if effect_turn and current_turn and effect_turn != current_turn:
                    effect_active = False
                effect_owner = str(target_sr.get("custodes_null_maiden_psychic_abominations_turn_owner", "") or "")
                if effect_owner and game is not None:
                    get_current_player = getattr(game, "get_current_player", None)
                    current_player = get_current_player() if callable(get_current_player) else None
                    current_owner = str(getattr(current_player, "id", "") or "")
                    if current_owner and effect_owner != current_owner:
                        effect_active = False
                if effect_active:
                    has_any_keyword = getattr(model, "has_any_keyword", None)
                    model_is_psyker = bool(callable(has_any_keyword) and has_any_keyword("PSYKER"))
                    if not model_is_psyker:
                        has_keyword = getattr(model, "has_keyword", None)
                        model_is_psyker = bool(callable(has_keyword) and has_keyword("PSYKER"))
                    attacker_battle_shocked = bool(getattr(root, "is_battle_shocked", lambda: False)())
                    if model_is_psyker or attacker_battle_shocked:
                        limit = float(
                            target_sr.get("custodes_null_maiden_psychic_abominations_targeting_range", 12.0) or 12.0
                        )
                        if min_distance > limit:
                            return False
        except Exception:
            pass

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

        ignore_lone_operative = False
        ignore_lone_operative_fn = getattr(
            self,
            "_model_can_ignore_lone_operative_when_selecting_targets",
            None,
        )
        if callable(ignore_lone_operative_fn):
            ignore_lone_operative = bool(ignore_lone_operative_fn(model))

        try:
            limit, _sources = target_unit.get_ranged_targeting_restriction(
                game_map=game_map,
                ignore_lone_operative=ignore_lone_operative,
            )
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
        selected_profile_id = _shooting_entity_id(weapon_profile)
        selected_profile_name = str(getattr(weapon_profile, "name", "") or "").strip().casefold()
        selected_parent = getattr(weapon_profile, "parent_wargear", None)
        selected_parent_id = _shooting_entity_id(selected_parent)
        selected_parent_name = str(getattr(selected_parent, "name", "") or "").strip().casefold()
        for wargear in list(getattr(model, "wargear", []) or []):
            carried_parent_id = _shooting_entity_id(wargear)
            carried_parent_name = str(getattr(wargear, "name", "") or "").strip().casefold()
            parent_matches = (
                bool(selected_parent_id and carried_parent_id == selected_parent_id)
                or bool(selected_parent_name and carried_parent_name == selected_parent_name)
            )
            for profile_name, profile in (getattr(wargear, "profiles", {}) or {}).items():
                if profile is weapon_profile:
                    return True
                carried_profile_id = _shooting_entity_id(profile)
                if selected_profile_id and carried_profile_id == selected_profile_id:
                    return True
                carried_profile_names = {
                    str(profile_name or "").strip().casefold(),
                    str(getattr(profile, "name", "") or "").strip().casefold(),
                }
                if parent_matches and selected_profile_name and selected_profile_name in carried_profile_names:
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
        parent_wargear = getattr(weapon_profile, "parent_wargear", None)
        is_ranged_weapon = bool(parent_wargear and callable(getattr(parent_wargear, "is_ranged", None)) and parent_wargear.is_ranged())
        is_melee_weapon = bool(parent_wargear and callable(getattr(parent_wargear, "is_melee", None)) and parent_wargear.is_melee())
        if not is_ranged_weapon and not is_melee_weapon:
            return False

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

        def _is_eligible_target(unit) -> bool:
            if not _matches_required(unit):
                return False
            if is_ranged_weapon:
                try:
                    return bool(self._can_model_shoot_weapon_at_target(model, weapon_profile, unit, game_map))
                except Exception:
                    return False
            if not is_melee_weapon:
                return False
            within_engagement_fn = getattr(self, "_model_within_engagement_range_of_unit", None)
            if callable(within_engagement_fn) and bool(within_engagement_fn(model, unit)):
                return True
            has_fight_within_3_fn = getattr(self, "has_fight_within_3_ability", None)
            fight_within_3_active_fn = getattr(self, "fight_within_3_active", None)
            within_range_fn = getattr(self, "_model_within_range_of_unit", None)
            if not callable(has_fight_within_3_fn) or not bool(has_fight_within_3_fn()):
                return False
            if not callable(fight_within_3_active_fn) or not bool(fight_within_3_active_fn()):
                return False
            if not callable(within_range_fn):
                return False
            try:
                if not bool(game_map.is_within_engagement_range(self, unit)):
                    return False
            except Exception:
                return False
            return bool(within_range_fn(model, unit, 3.0))

        if not _is_eligible_target(target_root):
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
            if not _is_eligible_target(root):
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
        if shooting_model is None or target_unit is None or game_map is None:
            return False
        cache_key = _shooting_los_cache_key(self, shooting_model, target_unit, game_map)
        cached = _shooting_los_cache_get(game_map, cache_key)
        if cached is not None:
            return bool(cached)

        def _cache_and_return(value: bool) -> bool:
            _shooting_los_cache_set(game_map, cache_key, bool(value))
            return bool(value)

        # Late imports to avoid circulars
        from shapely.geometry import LineString

        def _model_alive(model: object) -> bool:
            alive = getattr(model, "is_alive", False)
            return bool(alive() if callable(alive) else alive)

        def _unit_alive(unit: object) -> bool:
            alive = getattr(unit, "is_alive", True)
            return bool(alive() if callable(alive) else alive)

        def _unit_flag(unit: object, attr_name: str) -> bool:
            return bool(getattr(unit, attr_name, False)) if unit is not None else False

        def _bounds_overlap(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> bool:
            return not (
                first[2] < second[0]
                or second[2] < first[0]
                or first[3] < second[1]
                or second[3] < first[1]
            )

        def _segment_bounds_2d(p0: tuple, p1: tuple) -> tuple[float, float, float, float]:
            x0 = float(p0[0])
            y0 = float(p0[1])
            x1 = float(p1[0])
            y1 = float(p1[1])
            return (
                x0 if x0 <= x1 else x1,
                y0 if y0 <= y1 else y1,
                x1 if x0 <= x1 else x0,
                y1 if y0 <= y1 else y0,
            )

        def _blocker_bounds_for_los(
            terrain_contexts: tuple[dict[str, object], ...],
            blocker_contexts: tuple[dict[str, object], ...],
        ) -> tuple[bool, tuple[tuple[float, float, float, float], ...]]:
            bounds_rows: list[tuple[float, float, float, float]] = []
            always_possible = False
            for context in terrain_contexts:
                if bool(context.get("is_ruins")) and bool(context.get("shooter_inside", False)):
                    always_possible = True
                footprint_bounds = context.get("footprint_bounds")
                if footprint_bounds is None:
                    if context.get("footprint") is not None or context.get("walls"):
                        always_possible = True
                else:
                    bounds_rows.append(footprint_bounds)
                for wall in tuple(context.get("walls", ()) or ()):
                    bounds_rows.append(wall["bounds"])
            for blocker in blocker_contexts:
                bounds_rows.append(blocker["bounds"])
            return bool(always_possible), tuple(bounds_rows)

        def _any_blocker_bounds_overlap(
            line_bounds: tuple[float, float, float, float],
            blocker_bounds: tuple[tuple[float, float, float, float], ...],
        ) -> bool:
            for bounds in blocker_bounds:
                if _bounds_overlap(line_bounds, bounds):
                    return True
            return False

        def _line_intersection_point(line2d, geometry):
            intersection = line2d.intersection(geometry)
            if intersection.is_empty:
                return None
            if intersection.geom_type == "Point":
                return intersection
            if intersection.geom_type in ("LineString", "MultiPoint", "MultiLineString"):
                return intersection.centroid
            return intersection.representative_point()

        def _terrain_z_bounds(terrain: object) -> tuple[float, float]:
            if hasattr(terrain, "height"):
                return 0.0, float(getattr(terrain, "height"))
            if hasattr(terrain, "rim_height"):
                return 0.0, float(getattr(terrain, "rim_height"))
            bounding_box = getattr(terrain, "bounding_box", None)
            if isinstance(bounding_box, dict):
                min_value = bounding_box.get("min", (0.0, 0.0, 0.0))
                max_value = bounding_box.get("max", (0.0, 0.0, 0.0))
                if (
                    isinstance(min_value, (tuple, list))
                    and isinstance(max_value, (tuple, list))
                    and len(min_value) >= 3
                    and len(max_value) >= 3
                ):
                    return float(min_value[2]), float(max_value[2])
            return 0.0, 2.0

        model_geometry_cache: dict[int, tuple[object, tuple[float, float, float, float], tuple[float, float]]] = {}

        def _model_geometry(model: object):
            key = id(model)
            cached = model_geometry_cache.get(key)
            if cached is not None:
                return cached
            map_cache_key = _shooting_los_model_key(model)
            map_cache = _shooting_los_geometry_cache(game_map)
            cached = map_cache.get(map_cache_key)
            if cached is not None:
                map_cache.move_to_end(map_cache_key)
                model_geometry_cache[key] = cached
                return cached
            base = getattr(model, "model_base", None)
            if base is None:
                return None
            shape = base.get_base_shape()
            volume_bounds = getattr(base, "volume_z_bounds", None)
            if callable(volume_bounds):
                z_bounds = tuple(float(value) for value in volume_bounds())
            else:
                z = float(getattr(base, "z", 0.0) or 0.0)
                z_bounds = (z, z)
            geometry = (shape, shape.bounds, z_bounds)
            model_geometry_cache[key] = geometry
            map_cache[map_cache_key] = geometry
            map_cache.move_to_end(map_cache_key)
            while len(map_cache) > _SHOOTING_LOS_GEOMETRY_CACHE_MAX:
                map_cache.popitem(last=False)
            return geometry

        def sample_model_points_3d(model: 'Model', perimeter_points: int = 8, z_levels: int = 3) -> tuple:
            sample_cache_key = ("sample_points_3d", _shooting_los_model_key(model), int(perimeter_points), int(z_levels))
            sample_cache = _shooting_los_sample_cache(game_map)
            cached = sample_cache.get(sample_cache_key)
            if cached is not None:
                sample_cache.move_to_end(sample_cache_key)
                return tuple(cached)
            geometry = _model_geometry(model)
            if geometry is None:
                return ()
            base_shape, _bounds, z_bounds = geometry
            exterior = base_shape.exterior
            perimeter_samples = []
            if exterior.length > 0 and perimeter_points > 0:
                step = exterior.length / perimeter_points
                for i in range(perimeter_points):
                    p = exterior.interpolate(step * i)
                    perimeter_samples.append((p.x, p.y))
            centroid = base_shape.centroid
            xy_points = [(centroid.x, centroid.y)] + perimeter_samples

            z_bottom, z_top = z_bounds
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
            samples = tuple(points_3d)
            sample_cache[sample_cache_key] = samples
            sample_cache.move_to_end(sample_cache_key)
            while len(sample_cache) > _SHOOTING_LOS_SAMPLE_CACHE_MAX:
                sample_cache.popitem(last=False)
            return samples

        def _build_terrain_contexts(shooter_shape: object) -> tuple[dict[str, object], ...]:
            contexts: list[dict[str, object]] = []
            for terrain in getattr(game_map, "terrain_features", []):
                footprint = getattr(terrain, "footprint", None)
                walls = tuple(getattr(terrain, "walls", None) or ())
                openings = tuple(getattr(terrain, "openings", None) or ())
                is_ruins = hasattr(terrain, "walls") and hasattr(terrain, "openings") and footprint is not None
                wall_contexts = tuple(
                    {
                        "polygon": wall.get("polygon"),
                        "bounds": wall.get("polygon").bounds,
                        "z_bottom": float(wall.get("z_bottom", 0.0)),
                        "z_top": float(wall.get("z_top", wall.get("z_bottom", 0.0))),
                    }
                    for wall in walls
                    if wall.get("polygon") is not None
                )
                opening_contexts = tuple(
                    {
                        "polygon": opening.get("polygon"),
                        "bounds": opening.get("polygon").bounds,
                        "z_bottom": float(opening.get("z_bottom", -1e9)),
                        "z_top": float(opening.get("z_top", 1e9)),
                    }
                    for opening in openings
                    if bool(opening.get("allows_los", False)) and opening.get("polygon") is not None
                )
                shooter_inside = bool(footprint.intersects(shooter_shape)) if is_ruins else False
                shooter_wholly = bool(footprint.covers(shooter_shape)) if is_ruins else False
                contexts.append(
                    {
                        "terrain": terrain,
                        "footprint": footprint,
                        "footprint_bounds": footprint.bounds if footprint is not None else None,
                        "is_ruins": is_ruins,
                        "walls": wall_contexts,
                        "openings": opening_contexts,
                        "shooter_inside": shooter_inside,
                        "shooter_wholly": shooter_wholly,
                        "z_bounds": _terrain_z_bounds(terrain),
                    }
                )
            return tuple(contexts)

        def _target_ruins_states(target_shape: object, terrain_contexts: tuple[dict[str, object], ...]) -> tuple[bool, ...]:
            states: list[bool] = []
            for context in terrain_contexts:
                footprint = context.get("footprint")
                if bool(context.get("is_ruins")) and footprint is not None:
                    states.append(bool(footprint.intersects(target_shape)))
                else:
                    states.append(False)
            return tuple(states)

        def _build_blocker_contexts() -> tuple[dict[str, object], ...]:
            blockers: list[dict[str, object]] = []
            for enemy_unit in game_map.get_enemy_units(self):
                if enemy_unit == target_unit:
                    continue
                if not _unit_alive(enemy_unit) or not bool(getattr(enemy_unit, "deployed", True)):
                    continue
                for enemy_model in getattr(enemy_unit, "models", []) or []:
                    if not _model_alive(enemy_model):
                        continue
                    geometry = _model_geometry(enemy_model)
                    if geometry is None:
                        continue
                    shape, bounds, z_bounds = geometry
                    blockers.append({"shape": shape, "bounds": bounds, "z_bounds": z_bounds})
            return tuple(blockers)

        def is_segment_blocked(
            p0: tuple,
            p1: tuple,
            *,
            target_ruins_states: tuple[bool, ...],
            target_is_aircraft: bool,
            terrain_contexts: tuple[dict[str, object], ...],
            blocker_contexts: tuple[dict[str, object], ...],
            always_possible_blocker: bool,
            blocker_bounds: tuple[tuple[float, float, float, float], ...],
            shooter_is_aircraft: bool,
            shooter_is_towering: bool,
        ) -> bool:
            # Quick reject: degenerate line in XY projects to a point
            if abs(float(p0[0]) - float(p1[0])) <= 1e-9 and abs(float(p0[1]) - float(p1[1])) <= 1e-9:
                return False
            line_bounds = _segment_bounds_2d(p0, p1)
            if not always_possible_blocker and not _any_blocker_bounds_overlap(line_bounds, blocker_bounds):
                return False
            line2d = LineString([(p0[0], p0[1]), (p1[0], p1[1])])
            if line2d.length == 0:
                return False

            # Helper to compute z at param t along the 2D line
            def z_at_t(t: float) -> float:
                return p0[2] + t * (p1[2] - p0[2])

            # Terrain blocking (including special Ruins visibility rules)
            for terrain_index, context in enumerate(terrain_contexts):
                footprint = context.get("footprint")
                footprint_bounds = context.get("footprint_bounds")
                # Special Ruins visibility handling
                if bool(context.get("is_ruins")) and footprint is not None:
                    shooter_inside_any = bool(context.get("shooter_inside", False))
                    target_inside_any = bool(target_ruins_states[terrain_index])
                    shooter_wholly_within = bool(context.get("shooter_wholly", False))
                    # Aircraft always default to normal LOS: skip special ruins blocking
                    if shooter_is_aircraft or target_is_aircraft:
                        pass
                    else:
                        # If both models are outside this ruins and the footprint lies between them, LOS is blocked.
                        if not shooter_inside_any and not target_inside_any:
                            if footprint_bounds is not None and _bounds_overlap(line_bounds, footprint_bounds) and line2d.intersects(footprint):
                                return True

                        # If shooter is inside this ruins but not wholly within and not towering, cannot see out.
                        if shooter_inside_any and not shooter_wholly_within and not shooter_is_towering:
                            if not target_inside_any:
                                return True

                    # Otherwise, visibility to/from/within ruins is determined normally below

                # If terrain has explicit walls/openings (e.g., ruins), treat walls as vertical blockers
                walls = tuple(context.get("walls", ()) or ())
                openings = tuple(context.get("openings", ()) or ())
                if walls:
                    for wall in walls:
                        wall_poly = wall["polygon"]
                        if not _bounds_overlap(line_bounds, wall["bounds"]):
                            continue
                        if not line2d.intersects(wall_poly):
                            continue
                        inter_pt = _line_intersection_point(line2d, wall_poly)
                        if inter_pt is None:
                            continue

                        # Compute param t along line for z
                        t = line2d.project(inter_pt) / line2d.length if line2d.length > 0 else 0.0
                        # Ignore intersections at endpoints
                        if t <= 1e-6 or t >= 1.0 - 1e-6:
                            continue
                        z_here = z_at_t(t)
                        z_bottom = float(wall["z_bottom"])
                        z_top = float(wall["z_top"])

                        if z_bottom <= z_here <= z_top:
                            # Check if an opening at this XY,Z allows LOS
                            allowed = False
                            if openings:
                                for op in openings:
                                    if not op["bounds"][0] <= inter_pt.x <= op["bounds"][2] or not op["bounds"][1] <= inter_pt.y <= op["bounds"][3]:
                                        continue
                                    if not op["polygon"].contains(inter_pt):
                                        continue
                                    if float(op["z_bottom"]) <= z_here <= float(op["z_top"]):
                                        allowed = True
                                        break
                            if not allowed:
                                return True  # Blocked by wall without LOS opening
                else:
                    # Generic blocking by terrain footprint with height
                    if footprint is None:
                        continue
                    if footprint_bounds is not None and not _bounds_overlap(line_bounds, footprint_bounds):
                        continue
                    if not line2d.intersects(footprint):
                        continue
                    inter_pt = _line_intersection_point(line2d, footprint)
                    if inter_pt is None:
                        continue
                    t = line2d.project(inter_pt) / line2d.length if line2d.length > 0 else 0.0
                    if t <= 1e-6 or t >= 1.0 - 1e-6:
                        continue
                    z_here = z_at_t(t)
                    min_z, max_z = context["z_bounds"]
                    if min_z <= z_here <= max_z:
                        return True

            # Enemy models blocking (ignore friendlies and ignore models in the target unit)
            for blocker in blocker_contexts:
                if not _bounds_overlap(line_bounds, blocker["bounds"]):
                    continue
                enemy_poly = blocker["shape"]
                if not line2d.intersects(enemy_poly):
                    continue
                inter_pt = _line_intersection_point(line2d, enemy_poly)
                if inter_pt is None:
                    continue
                t = line2d.project(inter_pt) / line2d.length if line2d.length > 0 else 0.0
                if t <= 1e-6 or t >= 1.0 - 1e-6:
                    continue
                z_here = z_at_t(t)
                em_z0, em_z1 = blocker["z_bounds"]
                if em_z0 <= z_here <= em_z1:
                    return True

            return False

        # Validate inputs
        if not _model_alive(shooting_model) or not _unit_alive(target_unit):
            return _cache_and_return(False)
        shooter_geometry = _model_geometry(shooting_model)
        if shooter_geometry is None:
            return _cache_and_return(False)
        shooter_shape, _shooter_bounds, _shooter_z_bounds = shooter_geometry
        shooter_unit = getattr(shooting_model, "parent_unit", None)
        shooter_is_aircraft = _unit_flag(shooter_unit, "is_aircraft")
        shooter_is_towering = _unit_flag(shooter_unit, "is_towering")
        terrain_contexts = _build_terrain_contexts(shooter_shape)
        blocker_contexts = _build_blocker_contexts()
        always_possible_blocker, blocker_bounds = _blocker_bounds_for_los(terrain_contexts, blocker_contexts)

        # Sample 3D points on shooter and on each target model; LOS if any pair is unblocked
        shooter_points = sample_model_points_3d(shooting_model, perimeter_points=8, z_levels=3)

        for target_model in getattr(target_unit, "models", []) or []:
            if not _model_alive(target_model):
                continue
            target_geometry = _model_geometry(target_model)
            if target_geometry is None:
                continue
            target_shape, _target_bounds, _target_z_bounds = target_geometry
            target_unit_for_model = getattr(target_model, "parent_unit", target_unit)
            target_is_aircraft = _unit_flag(target_unit_for_model, "is_aircraft")
            target_ruins_states = _target_ruins_states(target_shape, terrain_contexts)
            target_points = sample_model_points_3d(target_model, perimeter_points=8, z_levels=3)
            broad_los_bounds = (
                min(float(_shooter_bounds[0]), float(_target_bounds[0])),
                min(float(_shooter_bounds[1]), float(_target_bounds[1])),
                max(float(_shooter_bounds[2]), float(_target_bounds[2])),
                max(float(_shooter_bounds[3]), float(_target_bounds[3])),
            )
            target_blocker_bounds = tuple(
                bounds for bounds in blocker_bounds if _bounds_overlap(broad_los_bounds, bounds)
            )
            if not always_possible_blocker and not target_blocker_bounds:
                return _cache_and_return(True)
            for p0 in shooter_points:
                for p1 in target_points:
                    if not is_segment_blocked(
                        p0,
                        p1,
                        target_ruins_states=target_ruins_states,
                        target_is_aircraft=target_is_aircraft,
                        terrain_contexts=terrain_contexts,
                        blocker_contexts=blocker_contexts,
                        always_possible_blocker=always_possible_blocker,
                        blocker_bounds=target_blocker_bounds,
                        shooter_is_aircraft=shooter_is_aircraft,
                        shooter_is_towering=shooter_is_towering,
                    ):
                        return _cache_and_return(True)

        return _cache_and_return(False)
    

    def _can_shoot_while_engaged(self, model, weapon_profile, target_unit, game_map) -> bool:
        """Check if model can shoot while engaged with other units"""
        if self._death_guard_all_is_rot_active():
            return True
        # Check if unit is in engagement range
        is_engaged = any(game_map.is_within_engagement_range(self, enemy)
                        for enemy in game_map.get_enemy_units(self) if enemy.is_alive())
        
        if not is_engaged:
            return True

        if self._ignore_engagement_for_ranged_targeting_active():
            try:
                parent = getattr(weapon_profile, "parent_wargear", None)
                if parent is None or parent.is_ranged():
                    return True
            except Exception:
                return True

        army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
        am_mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        ceaseless_fn = getattr(am_mgr, "ceaseless_cannonade_allows_ranged_target", None) if am_mgr is not None else None
        if callable(ceaseless_fn):
            game = getattr(getattr(army, "player", None), "game", None)
            if bool(ceaseless_fn(self, target_unit, weapon_profile=weapon_profile, game=game, game_map=game_map)):
                return True
            
        # If engaged, check weapon type and target
        # PISTOL (10e):
        # - A unit can shoot with Pistols while within Engagement Range.
        # - When it does so, it must target an enemy unit it is within Engagement Range of.
        if self.weapon_profile_counts_as_pistol(weapon_profile, model=model):
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
                    and ("demolisher" in weapon_name and "cannon" in weapon_name)
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
            return bool(self.weapon_profile_counts_as_pistol(weapon_profile, model=model))
            
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
        target_was_within_attacker_engagement: bool = False,
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
                roll = get_roll("D6")
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
                    try:
                        damage = int(getattr(attack_result, "total_damage_dealt", 0) or 0)
                    except Exception:
                        damage = 0
                    if damage > 0 and isinstance(attack_context, dict):
                        damage_map = attack_context.get("damage_by_target")
                        if not isinstance(damage_map, dict):
                            damage_map = {}
                            attack_context["damage_by_target"] = damage_map
                        damage_map[target_unit] = int(damage_map.get(target_unit, 0) or 0) + damage
                        if bool(target_was_within_attacker_engagement):
                            engaged_damage_map = attack_context.get("damage_by_target_while_engaged")
                            if not isinstance(engaged_damage_map, dict):
                                engaged_damage_map = {}
                                attack_context["damage_by_target_while_engaged"] = engaged_damage_map
                            engaged_damage_map[target_unit] = (
                                int(engaged_damage_map.get(target_unit, 0) or 0) + damage
                            )
                try:
                    root = self.get_attached_unit_root()
                except Exception:
                    root = self
                if bool(target_was_within_attacker_engagement) and root is not None:
                    sr = getattr(root, "special_rules", None)
                    if isinstance(sr, dict) and bool(sr.get("freeblade_point_blank_barrage_active")):
                        is_blast = getattr(active_profile, "is_blast", None)
                        if callable(is_blast) and bool(is_blast()):
                            hit_results = list(getattr(attack_result, "hit_results", []) or [])
                            backlash_wounds = 0
                            for hit_result in hit_results:
                                if not isinstance(hit_result, dict):
                                    continue
                                try:
                                    hit_roll = int(hit_result.get("roll", 0) or 0)
                                except Exception:
                                    continue
                                if hit_roll == 1:
                                    backlash_wounds += 1
                            if backlash_wounds > 0:
                                sr["freeblade_point_blank_barrage_pending_mortal_wounds"] = int(
                                    sr.get("freeblade_point_blank_barrage_pending_mortal_wounds", 0) or 0
                                ) + int(backlash_wounds)
                                root.special_rules = sr
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

    def force_battle_shock_test(self, current_turn: int = 1, *, modifier: int = 0, source: str = ""):
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        parsed_modifier = int(modifier or 0)
        if parsed_modifier:
            current = int(sr.get("battle_shock_test_modifier", 0) or 0)
            sr["battle_shock_test_modifier"] = int(current + parsed_modifier)
            source_name = str(source or "").strip()
            if source_name:
                reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
                reasons.append(f"{source_name}: {int(parsed_modifier):+d}")
                sr["battle_shock_test_modifier_reasons"] = reasons
        self.special_rules = sr
        self.take_battle_shock_test(int(current_turn or 1))

    def _light_of_the_emperor_ignore_test_modifier_rule(self) -> Optional[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return None
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        as_mgr = getattr(army, "adepta_sororitas_detachments", None) if army is not None else None
        rule_fn = (
            getattr(as_mgr, "light_of_the_emperor_ignore_modifier_rule", None)
            if as_mgr is not None
            else None
        )
        if not callable(rule_fn):
            return None
        game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        try:
            rule = rule_fn(root, kind="leadership", game=game)
        except Exception:
            rule = None
        return rule if isinstance(rule, dict) and rule else None

    @staticmethod
    def _filter_light_of_the_emperor_test_modifier(value: int, *, rule: Optional[dict]) -> int:
        try:
            modifier_value = int(value or 0)
        except Exception:
            modifier_value = 0
        if modifier_value == 0 or not isinstance(rule, dict):
            return modifier_value
        choice_key = str(rule.get("forced_choice", "") or rule.get("default_choice", "") or "").strip().lower()
        if choice_key == "ignore_all":
            return 0
        if choice_key == "ignore_negative":
            return 0 if modifier_value > 0 else modifier_value
        if choice_key == "ignore_positive":
            return 0 if modifier_value < 0 else modifier_value
        return modifier_value

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
        extra_mod_reasons: list[str] = []
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and "battle_shock_test_modifier" in sr:
                extra_mod = int(sr.get("battle_shock_test_modifier", 0) or 0)
                raw_reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
                extra_mod_reasons = [str(reason).strip() for reason in raw_reasons if str(reason).strip()]
                sr.pop("battle_shock_test_modifier", None)
                sr.pop("battle_shock_test_modifier_reasons", None)
                self.special_rules = sr
        except Exception:
            extra_mod = 0
            extra_mod_reasons = []
        post_shoot_mod = 0
        post_shoot_mod_source = ""
        try:
            post_shoot_mod = int(self._post_shoot_leadership_debuff_modifier(game))
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict):
                post_shoot_mod_source = str(sr.get("post_shoot_leadership_debuff_source", "") or "").strip()
        except Exception:
            post_shoot_mod = 0
            post_shoot_mod_source = ""
        aura_mod = 0
        aura_mod_reasons: list[str] = []
        try:
            from ...utility.aura_effects import get_aura_battleshock_test_modifiers
            aura_mods = get_aura_battleshock_test_modifiers(self, game_map=getattr(game, "map", None))
            for val, src in list(aura_mods or []):
                parsed = int(val)
                aura_mod += parsed
                src_name = str(src or "Aura modifier").strip() or "Aura modifier"
                aura_mod_reasons.append(f"{src_name} ({parsed:+d})")
        except Exception:
            aura_mod = 0
            aura_mod_reasons = []
        try:
            root_for_mod = self.get_attached_unit_root()
        except Exception:
            root_for_mod = self
        try:
            persistent_rules = getattr(root_for_mod, "special_rules", None)
            if isinstance(persistent_rules, dict):
                persistent_mod = int(persistent_rules.get("obeisance_your_time_is_nigh_battle_shock_test_modifier", 0) or 0)
                if persistent_mod:
                    extra_mod += int(persistent_mod)
                    source_name = (
                        str(persistent_rules.get("obeisance_your_time_is_nigh_source", "") or "YOUR TIME IS NIGH").strip()
                        or "YOUR TIME IS NIGH"
                    )
                    extra_mod_reasons.append(f"{source_name} ({int(persistent_mod):+d})")
        except Exception:
            pass
        try:
            dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
            modifier_fn = (
                getattr(dg_mgr, "shamblerot_witherbone_pipes_leadership_test_modifier", None)
                if dg_mgr is not None
                else None
            )
            if callable(modifier_fn):
                dg_mod, dg_source = modifier_fn(self, game=game)
                dg_mod = int(dg_mod or 0)
                if dg_mod:
                    extra_mod += int(dg_mod)
                    src_name = str(dg_source or "Witherbone Pipes").strip() or "Witherbone Pipes"
                    extra_mod_reasons.append(f"{src_name} ({int(dg_mod):+d})")
        except Exception:
            pass
        try:
            dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
            modifier_fn = (
                getattr(dg_mgr, "tallyband_tome_of_bounteous_blessings_battle_shock_modifier", None)
                if dg_mgr is not None
                else None
            )
            if callable(modifier_fn):
                dg_mod, dg_source = modifier_fn(self, game=game)
                dg_mod = int(dg_mod or 0)
                if dg_mod:
                    extra_mod += int(dg_mod)
                    src_name = (
                        str(dg_source or "Tome of Bounteous Blessings").strip()
                        or "Tome of Bounteous Blessings"
                    )
                    extra_mod_reasons.append(f"{src_name} ({int(dg_mod):+d})")
        except Exception:
            pass
        try:
            ignore_rule = self._light_of_the_emperor_ignore_test_modifier_rule()
            shadow_mod = self._filter_light_of_the_emperor_test_modifier(shadow_mod, rule=ignore_rule)
            extra_mod = self._filter_light_of_the_emperor_test_modifier(extra_mod, rule=ignore_rule)
            post_shoot_mod = self._filter_light_of_the_emperor_test_modifier(post_shoot_mod, rule=ignore_rule)
            aura_mod = self._filter_light_of_the_emperor_test_modifier(aura_mod, rule=ignore_rule)
        except Exception:
            pass
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
            sum_modifier_breakdown: list[dict] = []
            sum_modifier_reasons: list[str] = []
            shadow_reason = ""
            if shadow_mod:
                manifestation_active = bool(getattr(shadow_ctx, "manifestation_active", False)) if shadow_ctx is not None else False
                enemy_shadow_active = bool(getattr(shadow_ctx, "enemy_shadow_active", False)) if shadow_ctx is not None else False
                greater_daemon_terror_active = bool(
                    getattr(shadow_ctx, "greater_daemon_terror_active", False)
                ) if shadow_ctx is not None else False
                terror_active = bool(getattr(shadow_ctx, "terror_active", False)) if shadow_ctx is not None else False
                if manifestation_active and shadow_mod > 0:
                    shadow_reason = f"Daemonic Manifestation ({int(shadow_mod):+d})"
                elif shadow_mod < 0:
                    if enemy_shadow_active and greater_daemon_terror_active:
                        shadow_reason = "Enemy in Shadow of Chaos / Greater Daemon terror range (-1)"
                    elif enemy_shadow_active:
                        shadow_reason = "Enemy in Shadow of Chaos (-1)"
                    elif greater_daemon_terror_active:
                        shadow_reason = "Enemy within Greater Daemon terror range (-1)"
                    elif terror_active:
                        shadow_reason = "Enemy in Shadow of Chaos or terror range (-1)"
                if not shadow_reason:
                    shadow_reason = f"Shadow of Chaos ({int(shadow_mod):+d})"
                sum_modifier_breakdown.append(
                    {
                        "source": "Shadow of Chaos",
                        "value": int(shadow_mod),
                        "reason": shadow_reason,
                        "contributor_type": "faction_rule",
                    }
                )
                sum_modifier_reasons.append(shadow_reason)
            if extra_mod:
                if extra_mod_reasons:
                    sum_modifier_reasons.extend(list(extra_mod_reasons))
                    for extra_reason in list(extra_mod_reasons):
                        sum_modifier_breakdown.append(
                            {
                                "source": "Rule modifier",
                                "value": None,
                                "reason": str(extra_reason or ""),
                                "contributor_type": "rule",
                            }
                        )
                else:
                    sum_modifier_reasons.append(f"Rule modifier ({int(extra_mod):+d})")
                    sum_modifier_breakdown.append(
                        {
                            "source": "Rule modifier",
                            "value": int(extra_mod),
                            "reason": f"{int(extra_mod):+d}",
                            "contributor_type": "rule",
                        }
                    )
            if post_shoot_mod:
                if post_shoot_mod_source:
                    post_reason = f"{post_shoot_mod_source} ({int(post_shoot_mod):+d})"
                else:
                    post_reason = f"Post-shoot Leadership debuff ({int(post_shoot_mod):+d})"
                sum_modifier_reasons.append(post_reason)
                sum_modifier_breakdown.append(
                    {
                        "source": "Post-shoot debuff",
                        "value": int(post_shoot_mod),
                        "reason": post_reason,
                        "contributor_type": "unit_ability",
                    }
                )
            if aura_mod:
                if aura_mod_reasons:
                    sum_modifier_reasons.extend(list(aura_mod_reasons))
                    for aura_reason in list(aura_mod_reasons):
                        sum_modifier_breakdown.append(
                            {
                                "source": "Aura modifiers",
                                "value": None,
                                "reason": str(aura_reason or ""),
                                "contributor_type": "aura",
                            }
                        )
                else:
                    sum_modifier_reasons.append(f"Aura modifier ({int(aura_mod):+d})")
                    sum_modifier_breakdown.append(
                        {
                            "source": "Aura modifiers",
                            "value": int(aura_mod),
                            "reason": f"{int(aura_mod):+d}",
                            "contributor_type": "aura",
                        }
                    )
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
                        "shadow_enemy_in_shadow": bool(getattr(shadow_ctx, "enemy_shadow_active", False)) if shadow_ctx is not None else False,
                        "shadow_greater_daemon_terror_active": bool(
                            getattr(shadow_ctx, "greater_daemon_terror_active", False)
                        ) if shadow_ctx is not None else False,
                        "sum_modifier_reasons": list(sum_modifier_reasons),
                        "sum_modifier_breakdown": list(sum_modifier_breakdown),
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
                        provider = get_decision_provider(game, "roll_reroll_provider")
                        is_human = self._player_has_local_control(player)
                    except Exception:
                        provider = None
                        is_human = False
                    if callable(provider):
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
            logger.debug(f"{self.name} has failed the battle shock test and is battle-shocked!")

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

        if passed:
            try:
                army = self.get_parent_army()
            except Exception:
                army = None
            dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
            on_pass_fn = (
                getattr(dg_mgr, "tallyband_tome_of_bounteous_blessings_on_battle_shock_pass", None)
                if dg_mgr is not None
                else None
            )
            if callable(on_pass_fn):
                try:
                    on_pass_fn(self, game=game)
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

    def _reanimation_choose_model(
        self,
        eligible_models,
        *,
        is_human: bool,
        provider,
        reason: str,
        instruction: Optional[str] = None,
        selection_kind: str,
        remaining: int = 0,
    ):
        if not eligible_models:
            return None
        if len(eligible_models) == 1:
            return eligible_models[0]

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        army = root.get_parent_army() if root is not None and hasattr(root, "get_parent_army") else None
        player = getattr(army, "player", None) if army is not None else None
        game = getattr(player, "game", None) if player is not None else None
        request_fn = getattr(game, "request_decision", None) if game is not None else None
        if callable(request_fn):
            try:
                from ...engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
                from ...engine.decisions import DecisionOption, DecisionRequest
                from ...utility.decision_utils import (
                    decision_request_is_pending,
                    require_synchronous_decision_resolution,
                    resolve_or_reuse_payload_choice,
                )
                from ...utility.entity_ids import get_entity_id
            except Exception:
                request_fn = None
            else:
                allowed_model_ids = [str(get_entity_id(model) or "") for model in list(eligible_models or [])]
                options = []
                for model, model_id in zip(list(eligible_models or []), allowed_model_ids):
                    if not model_id:
                        continue
                    options.append(
                        DecisionOption.create(
                            getattr(model, "name", "Model"),
                            payload={"model_id": model_id},
                        )
                    )
                if options:
                    context = {
                        "selection_kind": str(selection_kind or "reanimation"),
                        "unit_id": str(get_entity_id(root) or ""),
                        "allowed_model_ids": list(allowed_model_ids),
                        "remaining_wounds": int(max(0, remaining)),
                        "reason": str(reason or "Reanimation Protocols"),
                        "ability": "reanimation_protocols",
                        "ability_name": "Reanimation Protocols",
                    }
                    if instruction:
                        context["instruction"] = str(instruction)
                    request = DecisionRequest.create(
                        DECISION_ALLOCATE_DAMAGE,
                        str(reason or "Reanimation Protocols"),
                        player_id=getattr(player, "id", None),
                        options=options,
                        context=context,
                    )
                    try:
                        request_fn(request)
                    except ValueError:
                        request = None
                    if request is not None:
                        fallback_model_id = None
                        if decision_request_is_pending(game, request):
                            if is_human and callable(provider):
                                try:
                                    chosen = provider(root, list(eligible_models), dict(context))
                                except Exception:
                                    chosen = None
                                if chosen is not None and chosen in eligible_models:
                                    fallback_model_id = str(get_entity_id(chosen) or "")
                        chosen_model_id, apply_result = resolve_or_reuse_payload_choice(
                            game,
                            request,
                            payload_key="model_id",
                            preselected_value=fallback_model_id,
                            player_id=getattr(player, "id", None),
                        )
                        require_synchronous_decision_resolution(
                            game,
                            request,
                            detail="Reanimation allocation decision remained pending without a synchronous decision owner.",
                        )
                        if apply_result is not None and getattr(apply_result, "ok", False):
                            chosen_model_id = str(chosen_model_id or "")
                            for model, model_id in zip(list(eligible_models or []), allowed_model_ids):
                                if str(model_id or "") == chosen_model_id:
                                    return model

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
        root_fn = getattr(self, "get_attached_unit_root", None)
        root = root_fn() if callable(root_fn) else self
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
        terrain_features = list(getattr(game_map, "terrain_features", []) or [])
        if terrain_features:
            from ...battlefield.map import validate_ruins_placement

            ruins_validation = validate_ruins_placement(
                root,
                (float(x), float(y), float(z)),
                terrain_features,
                moving_model=model,
            )
            if not bool((ruins_validation or {}).get("valid", False)):
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
                        rerolled = get_roll(roll_expr_norm)
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
                                bonus_roll = get_roll("D3")
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
                    selection_kind="reanimation_restore_wound",
                    remaining=int(resolved_wounds or 0) - int(result["healed"] or 0) - int(result["returned"] or 0),
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
                    selection_kind="reanimation_return_model",
                    remaining=int(resolved_wounds or 0) - int(result["healed"] or 0) - int(result["returned"] or 0),
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

        if _unit_disembarked_in_current_phase(self, game):
            logger.info(f"{self.name} cannot embark after disembarking this phase")
            return

        if (
            getattr(self.round_state, "reinforced_this_round", False)
            and not getattr(self.round_state, "moved_this_round", False)
            and not getattr(self.round_state, "advanced_this_round", False)
            and not getattr(self.round_state, "fell_back_this_round", False)
        ):
            logger.info(f"{self.name} cannot embark after arriving from Reserves unless it makes a qualifying move")
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

    def _disembark_collides_with_placed_models(
        self,
        x: float,
        y: float,
        z: float,
        facing: float,
        positions: List[Tuple[float, float, float, float]],
        models: List[Model],
        *,
        model: Model,
    ) -> bool:
        if not positions:
            return False
        new_base = self._create_potential_base(x, y, z, facing, model=model)
        for other_model, pos in zip(list(models or []), list(positions or [])):
            other_base = self._create_potential_base(pos[0], pos[1], pos[2], pos[3], model=other_model)
            if new_base.collides_with(other_base):
                return True
        return False

    def _disembark_is_coherent_with_placed_models(
        self,
        x: float,
        y: float,
        z: float,
        facing: float,
        positions: List[Tuple[float, float, float, float]],
        models: List[Model],
        *,
        model: Model,
    ) -> bool:
        if not positions:
            return True
        required_neighbors = 1 if len(positions) == 1 else int(getattr(self, "required_neighbors", 1) or 1)
        if required_neighbors <= 0:
            return True
        new_base = self._create_potential_base(x, y, z, facing, model=model)
        neighbors = 0
        for other_model, pos in zip(list(models or []), list(positions or [])):
            other_base = self._create_potential_base(pos[0], pos[1], pos[2], pos[3], model=other_model)
            try:
                horizontal = new_base.get_base_shape().distance(other_base.get_base_shape())
                vertical = abs(float(getattr(new_base, "z", 0.0)) - float(getattr(other_base, "z", 0.0)))
            except (AttributeError, TypeError, ValueError):
                continue
            if horizontal <= float(getattr(self, "coherency_distance", 2.0) or 2.0) + 1e-6 and vertical <= 5.0 + 1e-6:
                neighbors += 1
                if neighbors >= required_neighbors:
                    return True
        return False

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
        placement_models = [
            model
            for model in list(self.get_models_for_collision() or [])
            if getattr(model, "is_alive", False)
        ]
        if not placement_models:
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

        placed_models: List[Model] = []
        for model in placement_models:
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
                        if self._disembark_collides_with_placed_models(
                            x,
                            y,
                            z,
                            facing,
                            placed,
                            placed_models,
                            model=model,
                        ):
                            continue
                        if not self._disembark_is_coherent_with_placed_models(
                            x,
                            y,
                            z,
                            facing,
                            placed,
                            placed_models,
                            model=model,
                        ):
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
            placed_models.append(model)

        return placed

    def _find_single_disembark_position(
        self,
        *,
        model: Model,
        transport_base,
        game_map: 'Map',
        max_distance: float,
        placed: List[Tuple[float, float, float, float]],
        placed_models: Optional[List[Model]] = None,
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
                    if placed_models is not None:
                        collides = self._disembark_collides_with_placed_models(
                            x,
                            y,
                            z,
                            facing,
                            placed,
                            list(placed_models or []),
                            model=model,
                        )
                    else:
                        collides = self._collides_with_unit_models(x, y, z, facing, placed, model=model)
                    if collides:
                        continue
                    if placed_models is not None:
                        coherent = self._disembark_is_coherent_with_placed_models(
                            x,
                            y,
                            z,
                            facing,
                            placed,
                            list(placed_models or []),
                            model=model,
                        )
                    else:
                        coherent = self._is_coherent_within_unit(x, y, z, facing, placed, model=model)
                    if not coherent:
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

    def _apply_nightmare_shroud_disembark_effect(self, *, game=None, current_turn: int = 0) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return
        if not self._attached_unit_has_enhancement_flag(
            "enhancement_nightmare_shroud",
            enhancement_id="000010576005",
            enhancement_name="nightmare shroud",
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
            sr["nightmare_shroud_no_overwatch"] = True
            if owner:
                sr["nightmare_shroud_turn_owner"] = owner
            if turn:
                sr["nightmare_shroud_turn"] = int(turn)
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

    def _apply_blitz_brigade_eager_for_the_fight_disembark_effect(
        self,
        *,
        transport_unit=None,
        game=None,
        current_turn: int = 0,
    ) -> None:
        army = self.get_parent_army()
        if army is None:
            return
        mgr = getattr(army, "orks_detachments", None)
        apply_fn = (
            getattr(mgr, "apply_blitz_brigade_eager_for_the_fight_on_disembark", None)
            if mgr is not None
            else None
        )
        if callable(apply_fn):
            apply_fn(self, transport_unit=transport_unit, game=game, current_turn=current_turn)

    def _apply_armoured_speartip_rapid_deployment_disembark_effect(
        self,
        *,
        transport_unit=None,
        game=None,
        current_turn: int = 0,
    ) -> None:
        army = self.get_parent_army()
        if army is None:
            return
        mgr = getattr(army, "space_marines_detachments", None)
        queue_fn = (
            getattr(mgr, "queue_armoured_speartip_rapid_deployment_move", None)
            if mgr is not None
            else None
        )
        if callable(queue_fn):
            queue_fn(self, transport_unit=transport_unit, game=game, current_turn=current_turn)

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
                if "stratagem_disembark_override_allow_after_fall_back" in sr:
                    overrides["allow_after_fall_back"] = bool(
                        sr.get("stratagem_disembark_override_allow_after_fall_back", False)
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
        vanguard_honours_active = False
        try:
            vanguard_honours_active = bool(
                self._attached_unit_has_active_enhancement(
                    "enhancement_vanguard_honours",
                    enhancement_id="000009861005",
                    enhancement_name="Vanguard Honours",
                )
            )
        except Exception:
            vanguard_honours_active = False
        if vanguard_honours_active:
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
            for member in list(members or []):
                if member is None:
                    continue
                member_sr = getattr(member, "special_rules", None)
                if not isinstance(member_sr, dict) or not bool(member_sr.get("enhancement_vanguard_honours", False)):
                    continue
                allow_after_advance = bool(member_sr.get("enhancement_vanguard_honours_allow_after_advance", True))
                force_cannot_charge = bool(
                    member_sr.get("enhancement_vanguard_honours_force_cannot_charge_this_turn", True)
                )
                if allow_after_advance:
                    overrides["allow_after_advance"] = True
                if force_cannot_charge:
                    overrides["force_cannot_charge_this_turn"] = True
                break
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        am_mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        assault_hatches_fn = (
            getattr(am_mgr, "steel_hammer_assault_hatches_allows_charge_after_normal_move_disembark", None)
            if am_mgr is not None
            else None
        )
        if callable(assault_hatches_fn) and transport_unit is not None:
            try:
                if bool(assault_hatches_fn(transport_unit, game=game)):
                    overrides["allow_charge_after_normal_move"] = True
            except (TypeError, ValueError, AttributeError):
                pass
        csm_mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
        raid_leader_apply_fn = (
            getattr(csm_mgr, "hurons_marauders_raid_leader_allows_charge_after_normal_move_disembark", None)
            if csm_mgr is not None
            else None
        )
        if callable(raid_leader_apply_fn):
            try:
                if bool(raid_leader_apply_fn(self, transport_unit=transport_unit, game=game)):
                    overrides["allow_charge_after_normal_move"] = True
            except Exception:
                pass
        fasta_sources = self._attached_unit_active_enhancement_sources(
            "enhancement_kult_of_speed_fasta_than_yooz",
            source_keys=("enhancement_kult_of_speed_fasta_than_yooz_source",),
        )
        if fasta_sources and transport_unit is not None:
            transport_round_state = getattr(transport_unit, "round_state", None)
            moved_normally = bool(getattr(transport_round_state, "moved_this_round", False))
            moved_normally = moved_normally and not bool(getattr(transport_round_state, "advanced_this_round", False))
            moved_normally = moved_normally and not bool(getattr(transport_round_state, "fell_back_this_round", False))
            if moved_normally:
                for source_entry in fasta_sources:
                    source_rules = dict(source_entry.get("special_rules") or {})
                    if bool(
                        source_rules.get(
                            "enhancement_kult_of_speed_fasta_than_yooz_allow_charge_after_normal_move_disembark",
                            False,
                        )
                    ):
                        overrides["allow_charge_after_normal_move"] = True
                        break
        try:
            tsr = getattr(transport_unit, "special_rules", None)
        except Exception:
            tsr = None
        if isinstance(tsr, dict) and tsr.get("carry_forth_the_faithful_active"):
            carry_active = True
            owner = str(tsr.get("carry_forth_the_faithful_turn_owner", "") or "")
            turn = int(tsr.get("carry_forth_the_faithful_turn", 0) or 0)
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
                    carry_active = False
                if turn and current_turn and turn != current_turn:
                    carry_active = False
            if carry_active:
                if bool(tsr.get("carry_forth_the_faithful_disembark_allow_after_advance", True)):
                    overrides["allow_after_advance"] = True
                if bool(tsr.get("carry_forth_the_faithful_disembark_force_no_charge", True)):
                    overrides["force_cannot_charge_this_turn"] = True
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
        if isinstance(tsr, dict) and tsr.get("space_marines_armoured_advanced_deployment_active"):
            advanced_deployment_active = True
            exp = str(tsr.get("space_marines_armoured_advanced_deployment_expires_phase", "") or "").strip().upper()
            if exp:
                try:
                    phase = getattr(game, "phase", None)
                    phase_name = str(getattr(phase, "name", "") or phase or "").strip().upper()
                except Exception:
                    phase_name = ""
                if phase_name and phase_name != exp:
                    advanced_deployment_active = False
            owner = str(tsr.get("space_marines_armoured_advanced_deployment_turn_owner", "") or "")
            try:
                turn = int(tsr.get("space_marines_armoured_advanced_deployment_turn", 0) or 0)
            except (TypeError, ValueError):
                turn = 0
            if advanced_deployment_active and game is not None:
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
                    advanced_deployment_active = False
                if turn and current_turn and turn != current_turn:
                    advanced_deployment_active = False
            if advanced_deployment_active:
                if bool(tsr.get("space_marines_armoured_advanced_deployment_allow_after_advance", True)):
                    overrides["allow_after_advance"] = True
                if bool(tsr.get("space_marines_armoured_advanced_deployment_allow_charge_if_assault_ramp", True)):
                    transport_rules_fn = getattr(transport_unit, "_transport_disembark_rules", None)
                    transport_rules = transport_rules_fn() if callable(transport_rules_fn) else {}
                    if bool(dict(transport_rules or {}).get("allow_charge_after_normal_move", False)):
                        overrides["allow_charge_after_advance_disembark"] = True
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
        if isinstance(tsr, dict) and tsr.get("blitz_brigade_mekanised_brutality_active"):
            mekanised_active = True
            owner = str(tsr.get("blitz_brigade_mekanised_brutality_turn_owner", "") or "")
            try:
                turn = int(tsr.get("blitz_brigade_mekanised_brutality_turn", 0) or 0)
            except (TypeError, ValueError):
                turn = 0
            if game is not None:
                current_getter = getattr(game, "get_current_player", None)
                current_player = current_getter() if callable(current_getter) else None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    current_turn = 0
                if owner and current_owner and owner != current_owner:
                    mekanised_active = False
                if turn and current_turn and turn != current_turn:
                    mekanised_active = False
            transport_round_state = getattr(transport_unit, "round_state", None)
            moved_normally = bool(getattr(transport_round_state, "moved_this_round", False))
            moved_normally = moved_normally and not bool(getattr(transport_round_state, "advanced_this_round", False))
            moved_normally = moved_normally and not bool(getattr(transport_round_state, "fell_back_this_round", False))
            if mekanised_active and moved_normally:
                overrides["allow_charge_after_normal_move"] = True
        if isinstance(tsr, dict) and tsr.get("haloscreed_aggressive_impulse_active"):
            impulse_active = True
            exp = str(tsr.get("haloscreed_aggressive_impulse_expires_phase", "") or "").strip().upper()
            if exp:
                try:
                    phase = getattr(game, "phase", None)
                    phase_name = str(getattr(phase, "name", "") or phase or "").strip().upper()
                except Exception:
                    phase_name = ""
                if phase_name and phase_name != exp:
                    impulse_active = False
            owner = str(tsr.get("haloscreed_aggressive_impulse_turn_owner", "") or "")
            turn = int(tsr.get("haloscreed_aggressive_impulse_turn", 0) or 0)
            if impulse_active and game is not None:
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
                    impulse_active = False
                if turn and current_turn and turn != current_turn:
                    impulse_active = False
            if impulse_active:
                overrides["allow_charge_after_normal_move"] = True
        return overrides

    def _apply_aggressive_deployment_scouts(self, transport_unit: Optional['Unit'] = None) -> None:
        if transport_unit is None:
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
        has_reapers_wager_archraider = self._attached_unit_has_enhancement_flag(
            "enhancement_reapers_wager_archraider",
            enhancement_id="000009781002",
            enhancement_name="archraider",
        )
        has_tip_of_the_spear = self._attached_unit_has_enhancement_flag(
            "enhancement_armoured_speartip_tip_of_the_spear",
            enhancement_id="000010779003",
            enhancement_name="tip of the spear",
        )
        if not (
            has_aggressive_deployment
            or has_herald_of_sacred_slaughter
            or has_reapers_wager_archraider
            or has_tip_of_the_spear
        ):
            return
        if has_tip_of_the_spear:
            transport_has_keyword = getattr(transport_unit, "has_any_keyword", None)
            if callable(transport_has_keyword):
                if not bool(transport_has_keyword("TRANSPORT")):
                    return
            else:
                keywords = {
                    str(value or "").strip().upper()
                    for value in list(getattr(transport_unit, "keywords", []) or [])
                    + list(getattr(transport_unit, "faction_keywords", []) or [])
                }
                if "TRANSPORT" not in keywords:
                    return
        else:
            try:
                if not transport_unit.is_dedicated_transport:
                    return
            except Exception:
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
            try:
                val = max(val, float(sr.get("enhancement_reapers_wager_archraider_scouts_distance", 0) or 0))
            except Exception:
                pass
            try:
                val = max(
                    val,
                    float(sr.get("enhancement_armoured_speartip_tip_of_the_spear_scouts_distance", 0) or 0),
                )
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
        if has_reapers_wager_archraider:
            sr["enhancement_reapers_wager_archraider_active"] = True
            sr["enhancement_reapers_wager_archraider_distance"] = scouts_distance
        if has_tip_of_the_spear:
            sr["enhancement_armoured_speartip_tip_of_the_spear_active"] = True
            sr["enhancement_armoured_speartip_tip_of_the_spear_distance"] = scouts_distance
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
        allow_charge_after_setup = bool(transport_rules.get("allow_charge_after_setup", False))
        transport_sr = getattr(transport_unit, "special_rules", None)
        if isinstance(transport_sr, dict) and transport_sr.get("pain_rapid_deployment_active"):
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
        allow_after_fall_back = bool(overrides.get("allow_after_fall_back", False))
        allow_charge_after_advance_disembark = bool(overrides.get("allow_charge_after_advance_disembark", False))
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
                if not allow_after_fall_back:
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
                alive_models = [
                    m
                    for m in list(self.get_models_for_collision() or [])
                    if getattr(m, "is_alive", False)
                ]
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
                        placed_models=placed_models,
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
                self.round_state.cannot_remain_stationary_after_disembark = True
                self.round_state.remained_stationary_this_round = False
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
                    current_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
                    owner_id = str(getattr(current_player, "id", "") or "").strip()
                    if owner_id:
                        sr["voice_of_command_disembark_owner"] = owner_id
                    else:
                        sr.pop("voice_of_command_disembark_owner", None)
                self.special_rules = sr
                self._apply_goretrack_onslaught_disembark_effect(game=game, current_turn=current_turn)
                self._apply_murderous_onslaught_disembark_effect(game=game, current_turn=current_turn)
                self._apply_nightmare_shroud_disembark_effect(game=game, current_turn=current_turn)
                self._apply_spearhead_striker_disembark_effect(game=game, current_turn=current_turn)
                self._apply_rain_of_cruelty_disembark_effect(game=game, current_turn=current_turn)
                self._apply_blitz_brigade_eager_for_the_fight_disembark_effect(
                    transport_unit=transport_unit,
                    game=game,
                    current_turn=current_turn,
                )
                self._apply_armoured_speartip_rapid_deployment_disembark_effect(
                    transport_unit=transport_unit,
                    game=game,
                    current_turn=current_turn,
                )

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

        prior_locations = [
            (
                float(getattr(model.model_base, "x", 0.0)),
                float(getattr(model.model_base, "y", 0.0)),
                float(getattr(model.model_base, "z", 0.0)),
                float(getattr(model.model_base, "facing", 0.0)),
            )
            for model in placement_models
        ]

        for model, pos in zip(placement_models, placements):
            model.set_location(*pos)
        # Add back to map (place_unit validates collisions)
        if not hasattr(game_map, "place_unit"):
            raise RuntimeError("Disembark requires a game map with place_unit().")
        if not game_map.place_unit(self):
            for model, pos in zip(placement_models, prior_locations):
                model.set_location(*pos)
            if destroyed_transport and not emergency:
                logger.warning(
                    f"WARN: {self.name} destroyed-transport disembark placement failed validation; "
                    "attempting emergency disembarkation"
                )
                return self.disembark(
                    game_map=game_map,
                    transport_unit=transport_unit,
                    destroyed_transport=True,
                    emergency=True,
                    current_turn=current_turn,
                )
            logger.warning(f"WARN: {self.name} disembark failed: map placement validation failed")
            return False

        # Remove from transport passengers list
        transport_unit.remove_passenger(self)

        self.round_state.disembarked_this_round = True
        self.round_state.cannot_remain_stationary_after_disembark = True
        self.round_state.remained_stationary_this_round = False
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
            current_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
            owner_id = str(getattr(current_player, "id", "") or "").strip()
            if owner_id:
                sr["voice_of_command_disembark_owner"] = owner_id
            else:
                sr.pop("voice_of_command_disembark_owner", None)
        self.special_rules = sr
        self._apply_goretrack_onslaught_disembark_effect(game=game, current_turn=current_turn)
        self._apply_murderous_onslaught_disembark_effect(game=game, current_turn=current_turn)
        self._apply_nightmare_shroud_disembark_effect(game=game, current_turn=current_turn)
        self._apply_spearhead_striker_disembark_effect(game=game, current_turn=current_turn)
        self._apply_rain_of_cruelty_disembark_effect(game=game, current_turn=current_turn)
        self._apply_blitz_brigade_eager_for_the_fight_disembark_effect(
            transport_unit=transport_unit,
            game=game,
            current_turn=current_turn,
        )
        self._apply_armoured_speartip_rapid_deployment_disembark_effect(
            transport_unit=transport_unit,
            game=game,
            current_turn=current_turn,
        )

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
            transport_set_up_this_turn = bool(
                isinstance(transport_sr, dict) and transport_sr.get("drop_pod_assault_set_up", False)
            )

            if fell_back and allow_after_fall_back:
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.disembarked_cannot_charge = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
            elif advanced and allow_after_advance:
                # Advanced Deployment: counts as Normal move; Assault Ramp transports preserve charge eligibility.
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
                if not allow_charge_after_advance_disembark:
                    self.round_state.disembarked_cannot_charge = True
            elif transport_set_up_this_turn:
                # Immediate disembark after a reserves transport is set up still counts as a Normal move.
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
                self.round_state.reinforced_this_round = True
                self.arrived_from_reserves_this_turn = True
                self.deployed = True
                try:
                    self.reserve_turn_deployed = int(current_turn or 0)
                except Exception:
                    self.reserve_turn_deployed = 0
                if hasattr(self, "set_reserve_status"):
                    try:
                        self.set_reserve_status("deployed")
                    except Exception:
                        pass
                if not allow_charge_after_setup:
                    self.round_state.disembarked_cannot_charge = True
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
        allow_charge_after_setup = bool(transport_rules.get("allow_charge_after_setup", False))
        transport_sr = getattr(transport_unit, "special_rules", None)
        if isinstance(transport_sr, dict) and transport_sr.get("pain_rapid_deployment_active"):
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
        allow_after_fall_back = bool(overrides.get("allow_after_fall_back", False))
        allow_charge_after_advance_disembark = bool(overrides.get("allow_charge_after_advance_disembark", False))
        if overrides.get("allow_charge_after_normal_move") is True:
            allow_charge_after_normal_move = True
        force_cannot_charge_from_override = bool(overrides.get("force_cannot_charge_this_turn", False))

        if not destroyed_transport:
            if getattr(transport_unit.round_state, "advanced_this_round", False):
                if not allow_after_advance:
                    logger.error(f"ERROR: {self.name} cannot disembark: {transport_unit.name} Advanced this turn")
                    return False
            if getattr(transport_unit.round_state, "fell_back_this_round", False):
                if not allow_after_fall_back:
                    logger.error(f"ERROR: {self.name} cannot disembark: {transport_unit.name} Fell Back this turn")
                    return False

        if self in game_map.units:
            game_map.units.remove(self)

        if not hasattr(game_map, "place_unit"):
            raise RuntimeError("Finalize disembark requires a game map with place_unit().")
        if not game_map.place_unit(self):
            logger.warning(f"WARN: {self.name} disembark failed: map placement validation failed")
            return False

        transport_unit.remove_passenger(self)

        self.round_state.disembarked_this_round = True
        self.round_state.cannot_remain_stationary_after_disembark = True
        self.round_state.remained_stationary_this_round = False
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
            current_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
            owner_id = str(getattr(current_player, "id", "") or "").strip()
            if owner_id:
                sr["voice_of_command_disembark_owner"] = owner_id
            else:
                sr.pop("voice_of_command_disembark_owner", None)
        self.special_rules = sr
        self._apply_goretrack_onslaught_disembark_effect(game=game, current_turn=current_turn)
        self._apply_murderous_onslaught_disembark_effect(game=game, current_turn=current_turn)
        self._apply_nightmare_shroud_disembark_effect(game=game, current_turn=current_turn)
        self._apply_spearhead_striker_disembark_effect(game=game, current_turn=current_turn)
        self._apply_rain_of_cruelty_disembark_effect(game=game, current_turn=current_turn)
        self._apply_blitz_brigade_eager_for_the_fight_disembark_effect(
            transport_unit=transport_unit,
            game=game,
            current_turn=current_turn,
        )
        self._apply_armoured_speartip_rapid_deployment_disembark_effect(
            transport_unit=transport_unit,
            game=game,
            current_turn=current_turn,
        )

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
            transport_set_up_this_turn = bool(
                isinstance(transport_sr, dict) and transport_sr.get("drop_pod_assault_set_up", False)
            )

            if fell_back and allow_after_fall_back:
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.disembarked_cannot_charge = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
            elif advanced and allow_after_advance:
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
                if not allow_charge_after_advance_disembark:
                    self.round_state.disembarked_cannot_charge = True
            elif transport_set_up_this_turn:
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
                self.round_state.reinforced_this_round = True
                self.arrived_from_reserves_this_turn = True
                self.deployed = True
                try:
                    self.reserve_turn_deployed = int(current_turn or 0)
                except Exception:
                    self.reserve_turn_deployed = 0
                if hasattr(self, "set_reserve_status"):
                    try:
                        self.set_reserve_status("deployed")
                    except Exception:
                        pass
                if not allow_charge_after_setup:
                    self.round_state.disembarked_cannot_charge = True
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
