"""Auto-extracted Unit mixin methods from unit.py."""

from ._common import *


class DamageDeathMixin:
    def remove_model(self, model: Model, fleed: bool = False, game_map: Optional['Map'] = None) -> None:
        assert model in self.models

        # If this is the last bodyguard model in an Attached unit, snapshot its toughness so wound rolls
        # continue to use the bodyguard toughness until the attacking unit finishes resolving attacks.
        try:
            if len(self.models) == 1 and (not bool(getattr(self, "is_leader", False))) and list(getattr(self, "attached_leaders", []) or []):
                self._last_bodyguard_toughness = int(getattr(model, "toughness", getattr(model, "_toughness", 0)))
        except Exception:
            pass

        # Check for Deadly Demise ability before removing the model
        skip_deadly = False
        try:
            skip_deadly = bool(getattr(model, "_skip_deadly_demise_once", False))
        except Exception:
            skip_deadly = False
        if skip_deadly:
            try:
                setattr(model, "_skip_deadly_demise_once", False)
            except Exception:
                pass
        defer_deadly = False
        if not fleed and game_map is not None and not skip_deadly:
            defer_deadly = bool(self._trigger_deadly_demise(model, game_map))
        if defer_deadly:
            # Record the loss now, but keep the model to allow CAREEN movement.
            try:
                if not bool(getattr(model, "_careen_loss_recorded", False)):
                    self.round_state.num_lost_models_this_round += 1
                    self.models_lost.append(model)
                    setattr(model, "_careen_loss_recorded", True)
            except Exception:
                pass
            try:
                if not bool(getattr(self, "_careen_pending_destroyed", False)):
                    self._careen_pending_destroyed = True
            except Exception:
                pass

            # If this was the last model, publish unit-destroyed now (the unit is destroyed),
            # but skip re-publishing when we finalize removal after CAREEN resolves.
            if (not fleed) and len(self.models) == 1:
                try:
                    if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                        self.detach_from_unit()
                except Exception:
                    pass
                try:
                    if (not bool(getattr(self, "is_leader", False))) and list(getattr(self, "attached_leaders", []) or []):
                        any_leader_alive = any(len(getattr(l, "models", []) or []) > 0 for l in (getattr(self, "attached_leaders", []) or []))
                        if any_leader_alive:
                            setattr(self, "_pending_leader_separation", True)
                            return
                except Exception:
                    pass
                try:
                    setattr(self, "_skip_unit_destroyed_event_once", True)
                except Exception:
                    pass
                try:
                    game = self.get_parent_army().player.game
                    game.event_system.publish(
                        "unit_destroyed",
                        unit=self,
                        last_model=model,
                        destroyed_by_model=getattr(self, "_last_destroyed_by_model", None),
                        destroyed_by_unit=getattr(self, "_last_destroyed_by_unit", None),
                        destroyed_by_weapon_profile=getattr(self, "_last_destroyed_by_weapon_profile", None),
                        game_map=game_map,
                    )
                except Exception:
                    pass
            return

        # Remove model itself
        try:
            if not bool(getattr(model, "_careen_loss_recorded", False)):
                self.round_state.num_lost_models_this_round += 1
                self.models_lost.append(model)
        except Exception:
            self.round_state.num_lost_models_this_round += 1
            self.models_lost.append(model)
        self.models.remove(model)

        # Invalidate ability cache since unit composition changed
        self._invalidate_ability_cache()

        logger.info(f"Unit has {len(self.models)} models left!")
        #if len(self.models) < 1:
        #    if not fleed:
        #        self.callbacks[hook_events.ENEMY_UNIT_KILLED].append(logger.error(self))
        #    self.parent_detachment.removeUnit(self)
        self.update_coherency()
        self._maybe_swap_horrors_datasheet()
        try:
            self._refresh_bearer_unit_common_modifiers()
        except Exception:
            pass
        try:
            self._refresh_advance_no_roll_flags()
        except Exception:
            pass
        try:
            self._refresh_ignore_vertical_distance_move_types()
        except Exception:
            pass
        try:
            self._refresh_bearer_keyword_flags()
        except Exception:
            pass
        try:
            self._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass

        # Publish unit destroyed event (best-effort). Note: "destroyed" should not
        # trigger for fleeing/removal-type effects.
        if (not fleed) and len(self.models) < 1:
            try:
                if bool(getattr(self, "_skip_unit_destroyed_event_once", False)):
                    setattr(self, "_skip_unit_destroyed_event_once", False)
                    return
            except Exception:
                pass
            # If a Leader is destroyed while attached, immediately detach it so the bodyguard
            # no longer counts it for keyword/strength/collision purposes.
            try:
                if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                    self.detach_from_unit()
            except Exception:
                pass

            # If a BODYGUARD in an Attached unit is destroyed but Leaders remain, do NOT separate immediately.
            # Mark pending separation; it will be resolved after the attacking unit finishes resolving attacks.
            try:
                if (not bool(getattr(self, "is_leader", False))) and list(getattr(self, "attached_leaders", []) or []):
                    any_leader_alive = any(len(getattr(l, "models", []) or []) > 0 for l in (getattr(self, "attached_leaders", []) or []))
                    if any_leader_alive:
                        setattr(self, "_pending_leader_separation", True)
                        return
            except Exception:
                pass

            try:
                game = self.get_parent_army().player.game
                game.event_system.publish(
                    "unit_destroyed",
                    unit=self,
                    last_model=model,
                    destroyed_by_model=getattr(self, "_last_destroyed_by_model", None),
                    destroyed_by_unit=getattr(self, "_last_destroyed_by_unit", None),
                    destroyed_by_weapon_profile=getattr(self, "_last_destroyed_by_weapon_profile", None),
                    game_map=game_map,
                )
            except Exception:
                pass

    def _handle_model_destroyed(self, model: Model, game_map: Optional['Map'] = None) -> None:
        """Handle reactive 'on death' mechanics before the model is removed.

        This is invoked from `Model.die()` right before `type(self).remove_model()`.
        """
        self._maybe_queue_horrors_split(model)
        if game_map is None:
            return

        # Guard: only once per model (avoid double-trigger if die() is called twice)
        if getattr(model, "_on_death_reactions_resolved", False):
            return
        model._on_death_reactions_resolved = True

        # Publish a generic event hook for UI/agents (best-effort)
        try:
            game = self.get_parent_army().player.game
            game.event_system.publish("model_destroyed_before_removal", unit=self, model=model)
            # Mission scoring hooks (e.g., Fixed Assassination)
            if hasattr(game, "record_model_destroyed"):
                game.record_model_destroyed(model)
        except Exception:
            pass

        # Return-on-death abilities (e.g., Phoenix Gem / "first time destroyed" rules).
        try:
            specs = list(self._get_return_on_death_specs() or [])
        except Exception:
            specs = []
        if specs:
            for spec in specs:
                try:
                    key = str(spec.get("key") or spec.get("name") or "return_on_death").strip().lower()
                except Exception:
                    key = "return_on_death"
                if not key:
                    key = "return_on_death"
                once_key = f"return_on_death:{key}"
                try:
                    already = bool(getattr(model, "has_used_once_per_battle", lambda _k: False)(once_key))
                except Exception:
                    already = False
                if already:
                    continue
                required_model_name = str(spec.get("model_name") or "").strip()
                if required_model_name:
                    want = re.sub(r"[^a-z0-9]+", " ", required_model_name.lower()).strip()
                    got = re.sub(r"[^a-z0-9]+", " ", str(getattr(model, "name", "") or "").lower()).strip()
                    if want and want not in got:
                        continue
                bearer_id = str(spec.get("bearer_model_id") or "").strip()
                if bearer_id and str(getattr(model, "id", "") or "") != bearer_id:
                    continue
                try:
                    game = self.get_parent_army().player.game
                except Exception:
                    game = None
                if game is None:
                    continue
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                pos = None
                try:
                    pos = model.get_location()
                except Exception:
                    pos = None
                if pos is None:
                    try:
                        pos = getattr(self, "position", None)
                    except Exception:
                        pos = None
                if spec.get("skip_deadly_demise"):
                    try:
                        setattr(model, "_skip_deadly_demise_once", True)
                    except Exception:
                        pass
                reattach_bodyguard_unit = None
                was_attached_when_destroyed = False
                if bool(spec.get("must_reattach_if_attached", False)):
                    try:
                        reattach_bodyguard_unit = getattr(self, "attached_to", None)
                        was_attached_when_destroyed = reattach_bodyguard_unit is not None
                    except Exception:
                        reattach_bodyguard_unit = None
                        was_attached_when_destroyed = False
                if hasattr(game, "queue_phoenix_gem_return"):
                    game.queue_phoenix_gem_return(
                        unit=self,
                        model=model,
                        position=pos,
                        phase_name=phase_name,
                        game_map=game_map,
                        spec=spec,
                        reattach_bodyguard_unit=reattach_bodyguard_unit,
                        was_attached_when_destroyed=bool(was_attached_when_destroyed),
                    )
                    try:
                        label = str(spec.get("name") or "Return on Death")
                        print(f"{label}: {model.name} will attempt to return at end of phase.")
                    except Exception:
                        pass
                model.mark_used_once_per_battle(
                    once_key,
                    phase_name=phase_name,
                    ability_name=str(spec.get("name") or "Return on Death"),
                    source="enhancement",
                )
                break

        # Crewed Platform: destroy platform models when the last crew model is destroyed.
        self._maybe_handle_crewed_platform(model, game_map=game_map)

        # WORLD EATERS: Total Carnage (Blessings of Khorne) - deferred "fight on death" after attacker finishes attacks.
        # Trigger: a model is destroyed by a MELEE attack, model's unit benefits from Total Carnage, and unit has not fought this phase.
        try:
            # Only if we have map context (needed for fight-on-death targeting)
            if game_map is not None:
                army = self.get_parent_army()
                mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
                game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
                br = int(getattr(game, "turn", 0) or 0) if game is not None else 0

                if mgr is not None and br > 0:
                    # Eligibility: attached unit group qualifies if ANY member has Blessings of Khorne ability
                    qualifies = False
                    try:
                        qualifies = bool(self.get_attached_unit_root().attached_unit_has_blessings_of_khorne())
                    except Exception:
                        qualifies = False

                    if qualifies and mgr.is_blessing_active_for_unit("TOTAL_CARNAGE", self, battle_round=br):
                        # Must not have fought this phase
                        if not bool(getattr(self.round_state, "fought_this_phase", False)):
                            wp = getattr(self, "_last_destroyed_by_weapon_profile", None)
                            is_melee = False
                            try:
                                parent = getattr(wp, "parent_wargear", None)
                                is_melee = bool(parent is not None and parent.is_melee())
                            except Exception:
                                is_melee = False
                            if is_melee:
                                mgr.queue_total_carnage_model(model_obj=model)
        except Exception:
            # Fail-safe: don't break death processing
            pass

        # CHAOS DAEMONS: Hysterical Frenzy (Psychic) - fight on death after attacks.
        if game_map is not None:
            army = self.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            if phase_name == "FIGHT_PHASE":
                root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
                # Passive variant: no roll, requires not already fought this phase.
                rule = root.get_hysterical_frenzy_fight_on_death_rule(model=model)
                if rule is not None:
                    if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                        pending = getattr(root, "_hysterical_frenzy_pending_models", None)
                        if not isinstance(pending, list):
                            pending = []
                        if model not in pending:
                            pending.append(model)
                        root._hysterical_frenzy_pending_models = pending
                        return
                # Reactive variant: roll 4+ while active.
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("hysterical_frenzy_active"):
                    exp = str(sr.get("hysterical_frenzy_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_name:
                        threshold = int(sr.get("hysterical_frenzy_threshold", 4) or 4)
                        roll = int(get_roll("D6"))
                        from ...utility.event_bus import append_dice
                        if army is not None and getattr(army, "player", None) is not None:
                            label = str(sr.get("hysterical_frenzy_source", "") or "Hysterical Frenzy").strip()
                            append_dice(army.player, f"{label} roll: {roll} for {self.name}")
                        if roll >= int(threshold):
                            pending = getattr(root, "_hysterical_frenzy_pending_models", None)
                            if not isinstance(pending, list):
                                pending = []
                            if model not in pending:
                                pending.append(model)
                            root._hysterical_frenzy_pending_models = pending
                            return

        # EMPEROR'S CHILDREN: Death Ecstasy (defer fight-on-death until attacker finishes attacks).
        try:
            if game_map is not None:
                army = self.get_parent_army()
                game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                if phase_name == "FIGHT_PHASE":
                    try:
                        root = self.get_attached_unit_root()
                    except Exception:
                        root = self
                    sr = getattr(root, "special_rules", None)
                    if isinstance(sr, dict) and sr.get("death_ecstasy_active"):
                        exp = str(sr.get("death_ecstasy_expires_phase", "") or "").strip().upper()
                        if not exp or exp == phase_name:
                            try:
                                if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                                    pending = getattr(root, "_death_ecstasy_pending_models", None)
                                    if not isinstance(pending, list):
                                        pending = []
                                    if model not in pending:
                                        pending.append(model)
                                    root._death_ecstasy_pending_models = pending
                                    return
                            except Exception:
                                pass
        except Exception:
            # Fail-safe: don't break death processing
            pass

        # Rage-cursed Onslaught: Deathless Duty (defer fight-on-death until attacker finishes attacks).
        try:
            if game_map is not None:
                army = self.get_parent_army()
                game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                if phase_name == "FIGHT_PHASE":
                    try:
                        root = self.get_attached_unit_root()
                    except Exception:
                        root = self
                    sr = getattr(root, "special_rules", None)
                    if isinstance(sr, dict) and sr.get("deathless_duty_active"):
                        exp = str(sr.get("deathless_duty_expires_phase", "") or "").strip().upper()
                        if not exp or exp == phase_name:
                            try:
                                if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                                    pending = getattr(root, "_deathless_duty_pending_models", None)
                                    if not isinstance(pending, list):
                                        pending = []
                                    if model not in pending:
                                        pending.append(model)
                                    root._deathless_duty_pending_models = pending
                                    return
                            except Exception:
                                pass
        except Exception:
            # Fail-safe: don't break death processing
            pass

        # ORKS: Orks Is Never Beaten (defer fight-on-death until attacker finishes attacks).
        try:
            if game_map is not None:
                army = self.get_parent_army()
                game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                if phase_name == "FIGHT_PHASE":
                    try:
                        root = self.get_attached_unit_root()
                    except Exception:
                        root = self
                    sr = getattr(root, "special_rules", None)
                    if isinstance(sr, dict) and sr.get("orks_is_never_beaten_active"):
                        exp = str(sr.get("orks_is_never_beaten_expires_phase", "") or "").strip().upper()
                        if not exp or exp == phase_name:
                            try:
                                if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                                    pending = getattr(root, "_orks_is_never_beaten_pending_models", None)
                                    if not isinstance(pending, list):
                                        pending = []
                                    if model not in pending:
                                        pending.append(model)
                                    root._orks_is_never_beaten_pending_models = pending
                                    return
                            except Exception:
                                pass
        except Exception:
            # Fail-safe: don't break death processing
            pass

        # Adeptus Custodes: Defiant to the Last (defer fight-on-death on 4+ after attacker finishes attacks).
        try:
            if game_map is not None:
                army = self.get_parent_army()
                game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                if phase_name == "FIGHT_PHASE":
                    try:
                        root = self.get_attached_unit_root()
                    except Exception:
                        root = self
                    sr = getattr(root, "special_rules", None)
                    if isinstance(sr, dict) and sr.get("defiant_to_last_active"):
                        exp = str(sr.get("defiant_to_last_expires_phase", "") or "").strip().upper()
                        if not exp or exp == phase_name:
                            try:
                                if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                                    from ...utility.damage_allocation import _is_character_model
                                    from ...utility import dice as dice_module
                                    roll = int(dice_module.get_roll("D6"))
                                    is_char = bool(_is_character_model(model))
                                    total = roll + (2 if is_char else 0)
                                    try:
                                        from ...utility.event_bus import append_dice
                                        pn = self.get_parent_army().player
                                        label = "Defiant to the Last roll"
                                        bonus_label = f"+2={total}" if is_char else f"={total}"
                                        append_dice(pn, f"{label}: {roll}{bonus_label} for {self.name}")
                                    except Exception:
                                        pass
                                    if total >= 4:
                                        pending = getattr(root, "_defiant_to_last_pending_models", None)
                                        if not isinstance(pending, list):
                                            pending = []
                                        if model not in pending:
                                            pending.append(model)
                                        root._defiant_to_last_pending_models = pending
                                        return
                            except Exception:
                                pass
        except Exception:
            # Fail-safe: don't break death processing
            pass

        # MELEE fight-on-death after attacker finishes attacks (e.g., Malevolent Souls).
        rule = None
        try:
            rule = self.get_melee_fight_on_death_after_attacks_rule(model=model)
        except Exception:
            rule = None
        if rule is not None:
            try:
                root = self.get_attached_unit_root()
            except Exception:
                root = self
            has_fought = False
            try:
                has_fought = bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False))
            except Exception:
                pass
            if not has_fought and root is not None:
                wp = getattr(self, "_last_destroyed_by_weapon_profile", None)
                is_melee = False
                try:
                    parent = getattr(wp, "parent_wargear", None)
                    is_melee = bool(parent is not None and parent.is_melee())
                except Exception:
                    is_melee = False
                if is_melee:
                    roll = int(get_roll("D6"))
                    try:
                        from ...utility.event_bus import append_dice
                        pn = self.get_parent_army().player
                        append_dice(pn, f"{rule.get('source', 'Fight on death')} roll: {roll} for {self.name}")
                    except Exception:
                        pass
                    if roll >= int(rule.get("threshold", 0) or 0):
                        pending = getattr(root, "_melee_fight_on_death_pending_models", None)
                        if not isinstance(pending, list):
                            pending = []
                        if model not in pending:
                            pending.append(model)
                        root._melee_fight_on_death_pending_models = pending
                        return

        # Temporarily treat the model as "alive" so existing targeting/engagement checks work.
        original_wounds = getattr(model, "_wounds", None)
        try:
            if original_wounds is not None and original_wounds <= 0:
                model._wounds = 1

            # Prefer Fight on Death when engaged; otherwise try Shoot on Death.
            did_fight = False
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict) and sr.get("pain_fight_on_death_2plus"):
                    if not bool(getattr(self.round_state, "fought_this_phase", False)):
                        wp = getattr(self, "_last_destroyed_by_weapon_profile", None)
                        is_melee = False
                        try:
                            parent = getattr(wp, "parent_wargear", None)
                            is_melee = bool(parent is not None and parent.is_melee())
                        except Exception:
                            is_melee = False
                        if is_melee:
                            roll = int(get_roll("D6"))
                            try:
                                from ...utility.event_bus import append_dice
                                pn = self.get_parent_army().player
                                append_dice(pn, f"Mindless Killing Machines roll: {roll} for {self.name}")
                            except Exception:
                                pass
                            if roll >= 2:
                                did_fight = self._try_fight_on_death(model=model, game_map=game_map)
            except Exception:
                pass
            if (not did_fight) and self.has_fight_on_death():
                did_fight = self._try_fight_on_death(model=model, game_map=game_map)

            if (not did_fight) and self.has_shoot_on_death():
                self._try_shoot_on_death(model=model, game_map=game_map)
        finally:
            if original_wounds is not None:
                model._wounds = original_wounds

    def _try_fight_on_death(self, model: Model, game_map: 'Map') -> bool:
        """Attempt to resolve Fight-on-Death for a single destroyed model."""
        if getattr(model, "_fight_on_death_used", False):
            return False

        try:
            enemy_units = [u for u in game_map.get_enemy_units(self) if u.is_alive()]
        except Exception:
            try:
                enemy_units = [u for u in list(getattr(game_map, "units", []) or []) if u is not None and getattr(u, "faction", None) != getattr(self, "faction", None) and u.is_alive()]
            except Exception:
                enemy_units = []
        if not enemy_units:
            return False

        from ...utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
        from ...utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases

        engaged = []
        for enemy in enemy_units:
            try:
                if enemy is None or not enemy.is_alive():
                    continue
            except Exception:
                continue
            for em in list(getattr(enemy, "models", []) or []):
                try:
                    if not em.is_alive:
                        continue
                except Exception:
                    continue
                try:
                    horiz = float(horizontal_distance_between_bases_2d(model.model_base, em.model_base))
                    vert = float(vertical_distance_between_bases(model.model_base, em.model_base))
                except Exception:
                    continue
                if horiz <= ENGAGEMENT_RANGE_HORIZONTAL and vert <= ENGAGEMENT_RANGE_VERTICAL:
                    engaged.append(enemy)
                    break
        if not engaged:
            return False

        # Choose the closest engaged unit (edge-to-edge)
        def _closest_dist(enemy_unit: 'Unit') -> float:
            best = float("inf")
            from ...utility.aura_utils import distance_between_models_bases_3d
            for em in enemy_unit.models:
                if not em.is_alive:
                    continue
                best = min(best, float(distance_between_models_bases_3d(model, em)))
            return best

        target_unit = min(engaged, key=_closest_dist)

        melee_profiles = []
        for wargear in getattr(model, "wargear", []) or []:
            try:
                if not wargear.is_melee():
                    continue
            except Exception:
                continue
            if not getattr(wargear, "profiles", None):
                continue
            profile = wargear.profiles.get("default") or next(iter(wargear.profiles.values()))
            melee_profiles.append(profile)

        if not melee_profiles:
            return False

        model._fight_on_death_used = True
        try:
            game = self.get_parent_army().player.game
            game.event_system.publish("fight_on_death_triggered", unit=self, model=model, target=target_unit)
        except Exception:
            pass

        print(f"{model.name} fights on death into {target_unit.name}")
        for profile in melee_profiles:
            try:
                profile.attack(target_unit, model, game_map=game_map)
            except Exception as e:
                print(f"Fight on Death attack error: {e}")

        return True

    def _try_shoot_on_death(self, model: Model, game_map: 'Map') -> bool:
        """Attempt to resolve Shoot-on-Death for a single destroyed model."""
        if getattr(model, "_shoot_on_death_used", False):
            return False

        # Collect one profile per ranged weapon (choose 'default' or the first profile).
        ranged_profiles = []
        for wargear in getattr(model, "wargear", []) or []:
            try:
                if not wargear.is_ranged():
                    continue
            except Exception:
                continue
            if not getattr(wargear, "profiles", None):
                continue
            profile = wargear.profiles.get("default") or next(iter(wargear.profiles.values()))
            ranged_profiles.append(profile)

        if not ranged_profiles:
            return False

        enemy_units = [u for u in game_map.get_enemy_units(self) if u.is_alive()]
        if not enemy_units:
            return False

        # Choose the closest unit that at least one profile can shoot.
        best_target = None
        best_dist = float("inf")
        for enemy_unit in enemy_units:
            for profile in ranged_profiles:
                try:
                    if not self._can_model_shoot_weapon_at_target(model, profile, enemy_unit, game_map):
                        continue
                except Exception:
                    continue
                # compute distance to closest enemy model
                d = float("inf")
                for em in enemy_unit.models:
                    if not em.is_alive:
                        continue
                    from ...utility.aura_utils import distance_between_models_bases_3d
                    d = min(d, float(distance_between_models_bases_3d(model, em)))
                if d < best_dist:
                    best_dist = d
                    best_target = enemy_unit

        if best_target is None:
            return False

        model._shoot_on_death_used = True
        try:
            game = self.get_parent_army().player.game
            game.event_system.publish("shoot_on_death_triggered", unit=self, model=model, target=best_target)
        except Exception:
            pass

        print(f"{model.name} shoots on death into {best_target.name}")
        shots_executed = 0
        hit_models_by_target_weapon: dict = {}
        hit_models_by_target_psychic: dict = {}
        attack_context = {
            "pending_mortal_wounds": {},
            "defer_mortal_wounds": True,
            "hit_models_by_target_weapon": hit_models_by_target_weapon,
            "hit_models_by_target_psychic": hit_models_by_target_psychic,
        }
        for profile in ranged_profiles:
            try:
                shots_executed += self._execute_weapon_attacks(
                    profile,
                    best_target,
                    [model],
                    game_map,
                    attack_context=attack_context,
                )
            except Exception as e:
                print(f"Shoot on Death attack error: {e}")

        self._resolve_pending_attack_mortal_wounds(attack_context, best_target, game_map=game_map)
        return shots_executed > 0

    def _apply_deadly_demise_explosion(self, *, damage_dice: DiceCollection, position, game_map: 'Map') -> None:
        if not position:
            print("Cannot determine position for Deadly Demise")
            return

        # Find all units within 6 inches of the explosion
        nearby_units = self._get_units_within_range(position, 6.0, game_map)
        if not nearby_units:
            print("Deadly Demise triggered but no units within 6\" - no damage dealt")
            return

        # Apply damage to each nearby unit
        total_damage_dealt = 0
        for target_unit in nearby_units:
            # Roll damage independently for each unit (if it's a dice roll)
            if damage_dice.number > 0:  # It's a dice roll like D3, D6
                damage_amount = damage_dice.roll()
            else:  # It's a fixed number
                damage_amount = damage_dice.modifier

            print(f"{target_unit.name} suffers {damage_amount} mortal wounds from Deadly Demise!")

            # Apply mortal wounds to the target unit
            models_destroyed = self._apply_mortal_wounds_to_unit(target_unit, damage_amount, game_map=game_map)
            total_damage_dealt += damage_amount

            if models_destroyed > 0:
                print(f"Deadly Demise destroyed {models_destroyed} model(s) in {target_unit.name}")

        print(f"Deadly Demise complete: {total_damage_dealt} total mortal wounds dealt to {len(nearby_units)} unit(s)")

    def _trigger_deadly_demise(self, dying_model: Model, game_map: 'Map') -> bool:
        """Trigger Deadly Demise ability when a model is killed.

        Returns True if the explosion is deferred (e.g., CAREEN)."""
        # Check if the unit has Deadly Demise ability
        has_deadly_demise, damage_dice = self.has_deadly_demise()
        if not has_deadly_demise:
            return False

        print(f"{self.name} has Deadly Demise {damage_dice} - checking for explosion!")

        # Roll D6 to see if Deadly Demise triggers
        trigger_roll = get_roll("D6")
        try:
            from ...utility.event_bus import append_dice
            pn = self.get_parent_army().player
            append_dice(pn, f"Deadly Demise trigger: rolled {trigger_roll} (need 6)")
        except Exception:
            pass
        if trigger_roll != 6:
            print(f"Deadly Demise trigger roll: {trigger_roll} (needed 6) - No explosion!")
            return False

        print(f"Deadly Demise trigger roll: {trigger_roll} - EXPLOSION! ")

        # Offer CAREEN! if available (Orks War Horde).
        try:
            army = self.get_parent_army()
            player = getattr(army, "player", None) if army is not None else None
            mgr = getattr(player, "stratagems", None) if player is not None else None
            phase_name = ""
            try:
                game = getattr(player, "game", None) if player is not None else None
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "")
            except Exception:
                phase_name = ""
            if mgr is not None and bool(mgr.queue_careen(self, dying_model, game_map=game_map, phase_name=phase_name)):
                return True
        except Exception:
            pass

        # Resolve explosion immediately.
        model_position = dying_model.get_location()
        if not model_position:
            print(f"Cannot determine position of dying model for Deadly Demise")
            return False
        self._apply_deadly_demise_explosion(damage_dice=damage_dice, position=model_position, game_map=game_map)
        return False

    def resolve_careen_deadly_demise(self, game_map: Optional['Map'], *, use_move: bool = True) -> None:
        if not bool(getattr(self, "_careen_pending_destroyed", False)):
            return
        if game_map is None:
            game_map = None
        model = None
        try:
            pending_id = str(getattr(self, "_careen_pending_model_id", "") or "")
            for m in list(getattr(self, "models", []) or []):
                if str(get_entity_id(m)) == pending_id:
                    model = m
                    break
        except Exception:
            model = None
        if model is None:
            try:
                models = list(getattr(self, "models", []) or [])
                model = models[0] if models else None
            except Exception:
                model = None
        if model is None:
            # Nothing to resolve; clear pending state.
            try:
                self._careen_pending_destroyed = False
            except Exception:
                pass
            return

        # Resolve explosion at final (or original) position.
        try:
            position = model.get_location() if use_move else getattr(self, "_careen_origin_position", None)
            if not position:
                position = model.get_location()
        except Exception:
            position = getattr(self, "_careen_origin_position", None)
        try:
            has_deadly_demise, damage_dice = self.has_deadly_demise()
        except Exception:
            has_deadly_demise, damage_dice = (False, None)
        if has_deadly_demise and damage_dice is not None and game_map is not None:
            self._apply_deadly_demise_explosion(damage_dice=damage_dice, position=position, game_map=game_map)

        # Clear pending state before final removal.
        try:
            self._careen_pending_destroyed = False
            self._careen_origin_position = None
            self._careen_pending_model_id = None
            self._careen_pending_phase_name = None
        except Exception:
            pass
        try:
            setattr(model, "_careen_pending_move", False)
        except Exception:
            pass

        # If transport disembark was deferred, resolve now at the final position.
        try:
            if bool(getattr(self, "_careen_pending_transport_disembark", False)):
                game = self.get_parent_army().player.game
                game._on_unit_destroyed_transport_rules(unit=self, last_model=model, game_map=game_map)
                self._careen_pending_transport_disembark = False
        except Exception:
            pass

        # Remove the model without re-triggering Deadly Demise or unit-destroyed events.
        try:
            setattr(model, "_skip_deadly_demise_once", True)
        except Exception:
            pass
        try:
            setattr(self, "_skip_unit_destroyed_event_once", True)
        except Exception:
            pass
        try:
            self.remove_model(model, False, game_map=game_map)
        except Exception:
            pass

    def trigger_deadly_demise_manually(self, dying_model: Model, game_map: 'Map') -> None:
        """Manually trigger Deadly Demise for testing or when game context is available.
        
        This method can be called from the UI or game context when a model is killed
        and the game_map is available.
        
        Args:
            dying_model: The model that is being killed
            game_map: The game map to find nearby units
        """
        self._trigger_deadly_demise(dying_model, game_map)

    def _get_units_within_range(self, position: Tuple[float, float, float, float], range_inches: float, game_map: 'Map') -> List['Unit']:
        """Get all units within the specified range of a position.
        
        Args:
            position: (x, y, z, facing) position to check from
            range_inches: Range in inches to check
            game_map: The game map containing all units
            
        Returns:
            List of units within range (excluding the unit containing the position)
        """
        units_within_range = []
        x, y, z = position[0], position[1], position[2]
        
        for unit in game_map.units:
            if unit == self:  # Skip our own unit
                continue
            
            if not unit.is_alive():  # Skip destroyed units
                continue
            
            # Get the closest model in the unit to our position
            closest_distance = float('inf')
            for model in unit.models:
                if not model.is_alive:
                    continue
                model_pos = model.get_location()
                if model_pos:
                    model_distance = get_dist(
                        x - model_pos[0],
                        y - model_pos[1],
                        z - model_pos[2] if len(model_pos) > 2 else 0
                    )
                    closest_distance = min(closest_distance, model_distance)

            if closest_distance == float('inf'):
                continue

            distance = closest_distance
            
            if distance <= range_inches:
                units_within_range.append(unit)
        
        return units_within_range

    def _apply_mortal_wounds_to_unit(
        self,
        target_unit: 'Unit',
        mortal_wound_amount: int,
        game_map: Optional['Map'] = None,
        *,
        attacker_unit: Optional['Unit'] = None,
        attacker_model: Optional['Model'] = None,
        is_psychic_attack: bool = False,
        initial_model: Optional['Model'] = None,
        apply_fn: Optional[Callable[['Model'], None]] = None,
        allocation_ctx: Optional[object] = None,
        allow_initial_model_outside_candidates: bool = False,
    ) -> int:
        """Apply mortal wounds to a unit, distributing them among models.

        Args:
            target_unit: The unit to apply mortal wounds to
            mortal_wound_amount: Number of mortal wounds to apply
            initial_model: Optional model to allocate the first mortal wound to (e.g., Precision)
            apply_fn: Optional callback to apply each mortal wound to a model (defaults to Model.take_damage)
            allocation_ctx: Optional DamageAllocationCtx override for UI context
            allow_initial_model_outside_candidates: Allow initial_model even if not in allocation candidates

        Returns:
            Number of models destroyed by the mortal wounds
        """
        models_destroyed = 0
        current_model = None
        remaining = int(mortal_wound_amount or 0)

        if remaining <= 0:
            return 0

        from ...utility.damage_allocation import DamageAllocationCtx

        try:
            if initial_model is not None and getattr(initial_model, "is_alive", True):
                current_model = initial_model
        except Exception:
            current_model = None

        game = None
        try:
            army = target_unit.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        except Exception:
            game = None

        can_request_decision = bool(game is not None and getattr(game, "is_authoritative", False) and apply_fn is None)
        ctx = allocation_ctx or DamageAllocationCtx(reason="Allocate mortal wound", damage_source="mortal")
        ctx_dict = {
            "reason": ctx.reason,
            "damage_source": ctx.damage_source,
            "weapon_name": ctx.weapon_name,
            "attacker_name": ctx.attacker_name,
        }
        source_unit = attacker_unit
        if source_unit is None and self is not target_unit:
            source_unit = self
        source_model = attacker_model
        if source_model is None and source_unit is not None:
            candidate_models = [m for m in (getattr(source_unit, "models", []) or []) if getattr(m, "is_alive", True)]
            if len(candidate_models) == 1:
                source_model = candidate_models[0]

        # Apply mortal wounds one at a time to models in the unit
        while remaining > 0:
            if not target_unit.is_alive():
                break  # Unit is destroyed, stop applying wounds

            # Use the standard wound allocation candidate list (handles attached units: bodyguard -> leaders)
            try:
                candidates = target_unit.get_models_for_wound_allocation()
            except Exception:
                candidates = [m for m in (getattr(target_unit, "models", []) or []) if getattr(m, "is_alive", True)]
            if not candidates:
                break

            # Reset current model if it is no longer eligible.
            if current_model is not None:
                try:
                    if not getattr(current_model, "is_alive", True):
                        current_model = None
                    elif current_model not in candidates:
                        if allow_initial_model_outside_candidates:
                            try:
                                all_models = target_unit.get_models_for_collision()
                            except Exception:
                                all_models = list(candidates)
                            if current_model not in all_models:
                                current_model = None
                        else:
                            current_model = None
                except Exception:
                    current_model = None

            if current_model is None:
                from ...utility.damage_allocation import damage_allocation_choice
                choice = damage_allocation_choice(candidates)
                if choice.forced_model is not None:
                    current_model = choice.forced_model
                elif choice.choice_models:
                    if not can_request_decision:
                        current_model = choice.choice_models[0]
                    else:
                        try:
                            from ...engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
                            from ...engine.decisions import DecisionOption, DecisionRequest
                            from ...utility.entity_ids import get_entity_id
                        except Exception:
                            return models_destroyed

                        ordered = list(choice.choice_models or [])
                        ordered.sort(key=lambda m: str(get_entity_id(m)))
                        options = []
                        allowed_ids = []
                        for model in ordered:
                            try:
                                mid = get_entity_id(model)
                            except Exception:
                                continue
                            allowed_ids.append(mid)
                            options.append(DecisionOption.create(getattr(model, "name", "Model"), payload={"model_id": mid}))
                        if not options:
                            return models_destroyed
                        player_id = None
                        try:
                            player_id = target_unit.get_parent_army().player.id
                        except Exception:
                            player_id = None
                        req = DecisionRequest.create(
                            DECISION_ALLOCATE_DAMAGE,
                            ctx.reason or "Allocate mortal wound",
                            player_id=player_id,
                            options=options,
                            context={
                                "selection_kind": "unit_mortal_wound",
                                "unit_id": get_entity_id(target_unit),
                                "remaining_wounds": int(remaining),
                                "is_psychic_attack": bool(is_psychic_attack),
                                "allowed_model_ids": list(allowed_ids),
                                **ctx_dict,
                            },
                        )
                        if hasattr(game, "request_decision"):
                            game.request_decision(req)
                        return models_destroyed
                else:
                    return models_destroyed

            # Apply the mortal wound
            if callable(apply_fn):
                apply_fn(current_model)
            else:
                current_model.take_damage(
                    1,
                    is_mortal=True,
                    weapon_profile=None,
                    game_map=game_map,
                    is_psychic_attack=is_psychic_attack,
                    damage_source=ctx.damage_source or "mortal",
                )

            remaining -= 1

            # Check if the model was destroyed
            if not current_model.is_alive:
                models_destroyed += 1
                if apply_fn is None and source_unit is not None:
                    if target_unit is not None:
                        target_unit._last_destroyed_by_model = source_model
                        target_unit._last_destroyed_by_unit = source_unit
                        target_unit._last_destroyed_by_weapon_profile = None
                    if game is not None and hasattr(game, "event_system"):
                        game.event_system.publish(
                            "model_destroyed",
                            attacker_model=source_model,
                            attacker_unit=source_unit,
                            target_model=current_model,
                            target_unit=target_unit,
                            weapon_profile=None,
                            is_mortal=True,
                            game_map=game_map,
                        )
                current_model = None

        return models_destroyed

    def _resolve_pending_attack_mortal_wounds(
        self,
        attack_context: Optional[dict],
        target_unit: Optional['Unit'],
        game_map: Optional['Map'] = None,
    ) -> None:
        if not isinstance(attack_context, dict) or target_unit is None:
            return
        pending_by_target = attack_context.get("pending_mortal_wounds")
        if not isinstance(pending_by_target, dict):
            return
        from ..wargear import WargearProfile
        WargearProfile.resolve_pending_mortal_wounds_for_target(
            pending_by_target, target_unit, game_map=game_map
        )

    def _player_has_local_control(self, player) -> bool:
        if player is None:
            return False
        try:
            if callable(getattr(player, "has_control", None)):
                return bool(player.has_control())
        except Exception:
            pass
        try:
            from ...roster.player import PlayerControl
            return bool(getattr(player, "control", None) == PlayerControl.LOCAL)
        except Exception:
            return False
        return False

