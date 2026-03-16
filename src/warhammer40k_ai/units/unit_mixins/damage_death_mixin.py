"""Auto-extracted Unit mixin methods from unit.py."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class DamageDeathMixin:
    def _maybe_activate_watcher_in_the_dark(
        self,
        *,
        target_model: Optional[Model],
        attacker_model: Optional[Model] = None,
        attacker_unit: Optional['Unit'] = None,
        weapon_profile=None,
        game_map: Optional['Map'] = None,
        phase_name: str = "",
    ) -> bool:
        if target_model is None:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        try:
            if target_model not in list(root.get_attached_unit_models() or []):
                return False
        except Exception:
            pass
        has_astartes = getattr(target_model, "has_any_keyword", None)
        if callable(has_astartes) and not bool(has_astartes("ADEPTUS ASTARTES")):
            return False

        specs_fn = getattr(root, "unit_watcher_in_the_dark_specs", None)
        specs = list(specs_fn() or []) if callable(specs_fn) else []
        if not specs:
            return False

        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return False
        game = getattr(player, "game", None)

        current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if not current_phase:
            current_phase = str(phase_name or "").strip().upper()
        if not current_phase:
            current_phase = "ANY_PHASE"

        phase_label = str(phase_name or "").strip()
        if not phase_label:
            phase_map = {
                "COMMAND_PHASE": "Command phase",
                "MOVEMENT_PHASE": "Movement phase",
                "SHOOTING_PHASE": "Shooting phase",
                "CHARGE_PHASE": "Charge phase",
                "FIGHT_PHASE": "Fight phase",
            }
            phase_label = phase_map.get(current_phase, current_phase.replace("_", " ").title())

        unit_id = ""
        model_id = ""
        attacker_unit_id = ""
        attacker_model_id = ""
        weapon_name = ""
        try:
            unit_id = str(get_entity_id(root) or "")
        except Exception:
            unit_id = ""
        try:
            model_id = str(get_entity_id(target_model) or "")
        except Exception:
            model_id = ""
        try:
            if attacker_unit is None and attacker_model is not None:
                attacker_unit = getattr(attacker_model, "parent_unit", None)
            attacker_unit_root = (
                attacker_unit.get_attached_unit_root()
                if attacker_unit is not None and hasattr(attacker_unit, "get_attached_unit_root")
                else attacker_unit
            )
            attacker_unit_id = str(get_entity_id(attacker_unit_root) or "") if attacker_unit_root is not None else ""
        except Exception:
            attacker_unit_id = ""
        try:
            attacker_model_id = str(get_entity_id(attacker_model) or "") if attacker_model is not None else ""
        except Exception:
            attacker_model_id = ""
        try:
            weapon_name = str(
                getattr(getattr(weapon_profile, "parent_wargear", None), "name", "")
                or getattr(weapon_profile, "name", "")
                or ""
            )
        except Exception:
            weapon_name = ""

        provider = getattr(game_map, "unit_mortal_wound_fnp_provider", None) if game_map is not None else None

        for spec in list(specs):
            ability_key = str(spec.get("ability_key") or "watcher_in_the_dark").strip().lower()
            if not ability_key:
                ability_key = "watcher_in_the_dark"
            if getattr(root, "has_used_unit_once_per_battle", lambda _k: False)(ability_key):
                continue
            try:
                fnp_value = int(spec.get("value", 0) or 0)
            except (TypeError, ValueError):
                fnp_value = 0
            if fnp_value <= 0:
                continue
            ability_name = str(spec.get("source", "") or "Watcher in the Dark").strip() or "Watcher in the Dark"
            condition = str(spec.get("condition", "") or "against mortal wounds").strip() or "against mortal wounds"
            context = {
                "ability": "watcher_in_the_dark",
                "ability_name": ability_name,
                "unit_id": unit_id,
                "model_id": model_id,
                "ability_key": ability_key,
                "fnp_value": int(fnp_value),
                "condition": condition,
                "phase_name": phase_label,
                "attacker_unit_id": attacker_unit_id,
                "attacker_model_id": attacker_model_id,
                "weapon_name": weapon_name,
            }

            use_now = False
            if callable(getattr(player, "has_control", None)) and player.has_control() and callable(provider):
                if game is not None:
                    from ...engine.decision_kinds import DECISION_CONFIRM_YES_NO
                    from ...engine.decisions import DecisionOption, DecisionRequest

                    request = DecisionRequest.create(
                        DECISION_CONFIRM_YES_NO,
                        ability_name,
                        player_id=getattr(player, "id", None),
                        options=[
                            DecisionOption.create("Use", payload={"choice": True}),
                            DecisionOption.create("Skip", payload={"choice": False}),
                        ],
                        context=context,
                    )
                    request_fn = getattr(game, "request_decision", None)
                    if callable(request_fn):
                        request_fn(request)
                decision = provider(
                    player=player,
                    unit=root,
                    target_model=target_model,
                    attacker_model=attacker_model,
                    weapon_profile=weapon_profile,
                    ability_name=ability_name,
                    ability_key=ability_key,
                    fnp_value=int(fnp_value),
                    condition=condition,
                    phase_name=phase_label,
                )
                use_now = str(decision or "").strip().lower() in ("use", "yes", "true")
            elif game is not None:
                from ...engine.decision_kinds import DECISION_CONFIRM_YES_NO
                from ...engine.decisions import DecisionOption, DecisionRequest
                from ...utility.decision_utils import resolve_decision_value

                request = DecisionRequest.create(
                    DECISION_CONFIRM_YES_NO,
                    ability_name,
                    player_id=getattr(player, "id", None),
                    options=[
                        DecisionOption.create("Use", payload={"choice": True}),
                        DecisionOption.create("Skip", payload={"choice": False}),
                    ],
                    context=context,
                )
                request_fn = getattr(game, "request_decision", None)
                if callable(request_fn):
                    request_fn(request)
                should_use_fn = getattr(player, "_should_use_optional_ability", None)
                if callable(should_use_fn):
                    use_now = bool(should_use_fn("WATCHER_IN_THE_DARK", context))
                option_id = None
                for opt in list(getattr(request, "options", []) or []):
                    payload = dict(getattr(opt, "payload", {}) or {})
                    if bool(payload.get("choice", False)) == use_now:
                        option_id = opt.option_id
                        break
                if option_id:
                    _value, apply_result = resolve_decision_value(
                        game,
                        request,
                        option_id,
                        player_id=getattr(player, "id", None),
                    )
                    if apply_result is None or not getattr(apply_result, "ok", False):
                        use_now = False
            if not use_now:
                continue

            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            for model in list(models or []):
                alive_attr = getattr(model, "is_alive", False)
                alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if not alive:
                    continue
                set_temporary_fnp = getattr(model, "set_temporary_fnp", None)
                if callable(set_temporary_fnp):
                    set_temporary_fnp(
                        key=f"{ability_key}:{get_entity_id(model)}",
                        value=int(fnp_value),
                        source=ability_name,
                        condition=condition,
                        expires_phase=current_phase,
                    )
            mark_used = getattr(root, "mark_unit_once_per_battle_used", None)
            if callable(mark_used):
                mark_used(ability_key, ability_name=ability_name)
            try:
                from ...utility.event_bus import append_action

                append_action(
                    player,
                    f"{getattr(root, 'name', 'Unit')}: {ability_name} grants Feel No Pain {int(fnp_value)}+ {condition} until end of phase.",
                )
            except Exception:
                pass
            return True
        return False

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
                    if self._maybe_publish_using_sir_hekhtur_parent_destroyed(last_model=model, game_map=game_map):
                        return
                except Exception:
                    pass
                try:
                    using_sir_state = self._handle_using_sir_hekhtur_on_destroyed(last_model=model, game_map=game_map)
                    if using_sir_state in ("defer", "published"):
                        return
                except Exception:
                    pass
                try:
                    if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                        self.detach_from_unit()
                except Exception:
                    pass
                try:
                    if (not bool(getattr(self, "is_leader", False))) and list(getattr(self, "attached_leaders", []) or []):
                        any_leader_alive = any(len(getattr(l, "models", []) or []) > 0 for l in (getattr(self, "attached_leaders", []) or []))
                        if any_leader_alive:
                            try:
                                clear_tokens = getattr(self, "clear_aspect_shrine_tokens", None)
                                if callable(clear_tokens):
                                    clear_tokens()
                            except Exception:
                                pass
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
            try:
                if self._maybe_publish_using_sir_hekhtur_parent_destroyed(last_model=model, game_map=game_map):
                    return
            except Exception:
                pass
            try:
                using_sir_state = self._handle_using_sir_hekhtur_on_destroyed(last_model=model, game_map=game_map)
                if using_sir_state in ("defer", "published"):
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
                        try:
                            clear_tokens = getattr(self, "clear_aspect_shrine_tokens", None)
                            if callable(clear_tokens):
                                clear_tokens()
                        except Exception:
                            pass
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

    @staticmethod
    def _using_sir_hekhtur_normalize(value: object) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    def _is_canis_rex_unit(self) -> bool:
        if self._using_sir_hekhtur_normalize(getattr(self, "name", "")) == "canis rex":
            return True
        has_any_keyword = getattr(self, "has_any_keyword", None)
        if callable(has_any_keyword):
            try:
                return bool(has_any_keyword("Canis Rex"))
            except Exception:
                return False
        return False

    def _create_sir_hekhtur_unit_for_parent(self):
        from ...waha_helper.waha_helper import WahaHelper
        from ..unit import Unit

        parent_army = self.get_parent_army()
        if parent_army is None:
            return None

        faction_id = str(getattr(parent_army, "faction_id", "") or "").strip().upper() or None
        datasheet = WahaHelper().get_datasheet("Sir Hekhtur", faction_id=faction_id)
        if datasheet is None:
            return None

        unit = Unit(datasheet)
        unit.spawned_in_battle = True
        unit.deployed = True
        set_reserve = getattr(unit, "set_reserve_status", None)
        if callable(set_reserve):
            set_reserve("deployed")
        else:
            unit.reserve_status = "deployed"
        return unit

    def _resolve_using_sir_hekhtur_parent(self, parent_unit_id: str):
        parent_id = str(parent_unit_id or "").strip()
        if not parent_id:
            return None
        parent_army = self.get_parent_army()
        player = getattr(parent_army, "player", None) if parent_army is not None else None
        game = getattr(player, "game", None)
        resolver = getattr(game, "_resolve_unit_by_id", None) if game is not None else None
        if callable(resolver):
            parent = resolver(parent_id)
            if parent is not None:
                return parent
        for cand in list(getattr(parent_army, "units", []) or []):
            if str(get_entity_id(cand) or "") == parent_id:
                return cand
        return None

    def _maybe_publish_using_sir_hekhtur_parent_destroyed(
        self,
        *,
        last_model: Optional[Model],
        game_map: Optional['Map'],
    ) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        parent_id = str(sr.get("using_sir_hekhtur_parent_unit_id", "") or "").strip()
        if not parent_id:
            return False

        parent_unit = self._resolve_using_sir_hekhtur_parent(parent_id)
        if parent_unit is None:
            return False

        parent_sr = getattr(parent_unit, "special_rules", None)
        if not isinstance(parent_sr, dict):
            parent_sr = {}
        if bool(parent_sr.get("using_sir_hekhtur_destroyed_event_published", False)):
            return True

        parent_army = self.get_parent_army()
        player = getattr(parent_army, "player", None) if parent_army is not None else None
        game = getattr(player, "game", None)
        if game is None or not hasattr(game, "event_system"):
            return False

        parent_sr["using_sir_hekhtur_destroyed_event_published"] = True
        parent_sr.pop("using_sir_hekhtur_destroyed_pending", None)
        parent_unit.special_rules = parent_sr

        game.event_system.publish(
            "unit_destroyed",
            unit=parent_unit,
            last_model=last_model,
            destroyed_by_model=getattr(self, "_last_destroyed_by_model", None),
            destroyed_by_unit=getattr(self, "_last_destroyed_by_unit", None),
            destroyed_by_weapon_profile=getattr(self, "_last_destroyed_by_weapon_profile", None),
            game_map=game_map,
        )
        return True

    def _handle_using_sir_hekhtur_on_destroyed(
        self,
        *,
        last_model: Optional[Model],
        game_map: Optional['Map'],
    ) -> str:
        if game_map is None:
            return "none"
        if not self._is_canis_rex_unit():
            return "none"

        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if bool(sr.get("using_sir_hekhtur_destroyed_event_published", False)):
            return "published"
        if bool(sr.get("using_sir_hekhtur_destroyed_pending", False)):
            return "defer"

        parent_army = self.get_parent_army()
        if parent_army is None:
            return "none"

        sir_unit = None
        parent_id = str(get_entity_id(self) or "")
        for cand in list(getattr(parent_army, "units", []) or []):
            cand_sr = getattr(cand, "special_rules", None)
            if not isinstance(cand_sr, dict):
                continue
            if str(cand_sr.get("using_sir_hekhtur_parent_unit_id", "") or "") != parent_id:
                continue
            if cand is self:
                continue
            alive_attr = getattr(cand, "is_alive", None)
            alive = bool(alive_attr()) if callable(alive_attr) else bool(alive_attr)
            if alive:
                sir_unit = cand
                break

        if sir_unit is None:
            sir_unit = self._create_sir_hekhtur_unit_for_parent()
            if sir_unit is None:
                return "none"
            add_unit = getattr(parent_army, "add_unit", None)
            if callable(add_unit):
                add_unit(sir_unit)
            else:
                sir_unit.set_parent_army(parent_army)
                parent_army.units.append(sir_unit)

        sir_sr = getattr(sir_unit, "special_rules", None)
        if not isinstance(sir_sr, dict):
            sir_sr = {}
        sir_sr["using_sir_hekhtur_parent_unit_id"] = parent_id
        sir_sr["using_sir_hekhtur_parent_unit_name"] = str(getattr(self, "name", "") or "Canis Rex")
        sir_sr["stratagem_target_core_only"] = True
        sir_sr["stratagem_target_core_only_source"] = "USING SIR HEKHTUR"
        sir_unit.special_rules = sir_sr

        sir_unit.spawned_in_battle = True
        sir_unit.embarked_in = self
        sir_unit.round_state.embarked_this_round = True
        if sir_unit not in self.transport_passengers:
            self.transport_passengers.append(sir_unit)
        if hasattr(game_map, "units") and sir_unit in game_map.units:
            game_map.units.remove(sir_unit)

        if last_model is not None and getattr(last_model, "model_base", None) is not None:
            self._last_known_base = copy.deepcopy(last_model.model_base)

        parent_player = getattr(parent_army, "player", None)
        game = getattr(parent_player, "game", None)
        current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        disembarked = bool(
            sir_unit.disembark(
                game_map=game_map,
                transport_unit=self,
                destroyed_transport=True,
                emergency=True,
                current_turn=current_turn,
            )
        )

        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if bool(sr.get("using_sir_hekhtur_destroyed_event_published", False)):
            self.special_rules = sr
            return "published"

        sir_alive_attr = getattr(sir_unit, "is_alive", None)
        sir_alive = bool(sir_alive_attr()) if callable(sir_alive_attr) else bool(sir_alive_attr)
        if disembarked and sir_alive:
            sr["using_sir_hekhtur_destroyed_pending"] = True
            sr["using_sir_hekhtur_spawned_unit_id"] = str(get_entity_id(sir_unit) or "")
            self.special_rules = sr
            return "defer"

        self.special_rules = sr
        return "none"

    def _has_triarchal_menhirs_ability(self) -> bool:
        for ability in list(getattr(self, "possible_abilities", []) or []):
            if isinstance(ability, str):
                ability_name = str(ability or "")
            elif isinstance(ability, dict):
                ability_name = str(ability.get("name", "") or "")
            else:
                ability_name = str(getattr(ability, "name", "") or "")
            if str(ability_name or "").strip().upper() == "TRIARCHAL MENHIRS":
                return True
        return False

    def _maybe_handle_triarchal_menhirs(
        self,
        model: Optional[Model],
        game_map: Optional['Map'] = None,
    ) -> None:
        """TRIARCHAL MENHIRS: if Szarekh is destroyed, destroy remaining Menhirs."""
        if model is None:
            return
        if not self._has_triarchal_menhirs_ability():
            return
        if self._normalize_model_name(str(getattr(model, "name", "") or "")) != "szarekh":
            return

        remaining_menhirs = [
            candidate
            for candidate in list(getattr(self, "models", []) or [])
            if candidate is not model
            and getattr(candidate, "is_alive", False)
            and not getattr(candidate, "_pending_placement", False)
            and self._normalize_model_name(str(getattr(candidate, "name", "") or "")) == "triarchal menhir"
        ]
        for menhir in list(remaining_menhirs):
            menhir.wounds = 0
            menhir.die(game_map=game_map)

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
                effective_spec = dict(spec or {})
                wounds_if_battle_shocked = effective_spec.get("wounds_if_battle_shocked")
                if wounds_if_battle_shocked is not None:
                    is_battle_shocked = False
                    is_battle_shocked_fn = getattr(self, "is_battle_shocked", None)
                    if callable(is_battle_shocked_fn):
                        try:
                            is_battle_shocked = bool(is_battle_shocked_fn())
                        except Exception:
                            is_battle_shocked = False
                    else:
                        try:
                            is_battle_shocked = bool(getattr(self, "battle_shocked", False))
                        except Exception:
                            is_battle_shocked = False
                    if is_battle_shocked:
                        effective_spec["wounds"] = wounds_if_battle_shocked
                if effective_spec.get("skip_deadly_demise"):
                    try:
                        setattr(model, "_skip_deadly_demise_once", True)
                    except Exception:
                        pass
                reattach_bodyguard_unit = None
                was_attached_when_destroyed = False
                if bool(effective_spec.get("must_reattach_if_attached", False)):
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
                        spec=effective_spec,
                        reattach_bodyguard_unit=reattach_bodyguard_unit,
                        was_attached_when_destroyed=bool(was_attached_when_destroyed),
                    )
                    try:
                        label = str(effective_spec.get("name") or "Return on Death")
                        logger.info(f"{label}: {model.name} will attempt to return at end of phase.")
                    except Exception:
                        pass
                model.mark_used_once_per_battle(
                    once_key,
                    phase_name=phase_name,
                    ability_name=str(effective_spec.get("name") or "Return on Death"),
                    source="enhancement",
                )
                break

        # Crewed Platform: destroy platform models when the last crew model is destroyed.
        self._maybe_handle_crewed_platform(model, game_map=game_map)
        self._maybe_handle_triarchal_menhirs(model, game_map=game_map)

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

        # Emperor's Children (Slaanesh's Chosen): BEAUTIFUL DEATH (defer fight-on-death until attacker finishes attacks).
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
                    if isinstance(sr, dict) and sr.get("beautiful_death_active"):
                        exp = str(sr.get("beautiful_death_expires_phase", "") or "").strip().upper()
                        if not exp or exp == phase_name:
                            try:
                                if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                                    roll = int(get_roll("D6") or 0)
                                    bonus = 0
                                    mgr = getattr(army, "emperors_children", None) if army is not None else None
                                    is_favoured = getattr(mgr, "is_favoured_champions", None) if mgr is not None else None
                                    if callable(is_favoured) and bool(is_favoured(root)):
                                        bonus = 1
                                    total = int(roll + bonus)
                                    from ...utility.event_bus import append_dice
                                    if army is not None and getattr(army, "player", None) is not None:
                                        label = str(sr.get("beautiful_death_source", "") or "Beautiful Death").strip()
                                        if bonus:
                                            append_dice(
                                                army.player,
                                                f"{label} roll: {roll} +1 (Favoured Champions) = {total} for {self.name}",
                                            )
                                        else:
                                            append_dice(army.player, f"{label} roll: {roll} for {self.name}")
                                    if total >= 4:
                                        pending = getattr(root, "_beautiful_death_pending_models", None)
                                        if not isinstance(pending, list):
                                            pending = []
                                        if model not in pending:
                                            pending.append(model)
                                        root._beautiful_death_pending_models = pending
                                        return
                            except Exception:
                                pass
        except Exception:
            # Fail-safe: don't break death processing
            pass

        # Drukhari (Spectacle of Spite): BERSERK FUGUE (defer fight-on-death until attacker finishes attacks).
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
                    if isinstance(sr, dict) and sr.get("berserk_fugue_active"):
                        exp = str(sr.get("berserk_fugue_expires_phase", "") or "").strip().upper()
                        if not exp or exp == phase_name:
                            try:
                                if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                                    pending = getattr(root, "_berserk_fugue_pending_models", None)
                                    if not isinstance(pending, list):
                                        pending = []
                                    if model not in pending:
                                        pending.append(model)
                                    root._berserk_fugue_pending_models = pending
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

        # Adepta Sororitas: Spirit of the Martyr (defer fight-on-death until attacker finishes attacks).
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
                    if isinstance(sr, dict) and sr.get("spirit_of_martyr_active"):
                        exp = str(sr.get("spirit_of_martyr_expires_phase", "") or "").strip().upper()
                        if not exp or exp == phase_name:
                            try:
                                if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                                    pending = getattr(root, "_spirit_of_martyr_pending_models", None)
                                    if not isinstance(pending, list):
                                        pending = []
                                    if model not in pending:
                                        pending.append(model)
                                    root._spirit_of_martyr_pending_models = pending
                                    return
                            except Exception:
                                pass
        except Exception:
            # Fail-safe: don't break death processing
            pass

        # World Eaters (Possessed Slaughterband): Immortal Fury (defer fight-on-death until attacker finishes attacks).
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
                    if isinstance(sr, dict) and sr.get("immortal_fury_active"):
                        exp = str(sr.get("immortal_fury_expires_phase", "") or "").strip().upper()
                        if not exp or exp == phase_name:
                            try:
                                if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                                    pending = getattr(root, "_immortal_fury_pending_models", None)
                                    if not isinstance(pending, list):
                                        pending = []
                                    if model not in pending:
                                        pending.append(model)
                                    root._immortal_fury_pending_models = pending
                                    return
                            except Exception:
                                pass
        except Exception:
            # Fail-safe: don't break death processing
            pass

        # Chaos Daemons (Blood Legion): WRATH UNDENIABLE (defer fight-on-death on a 4+ for melee kills).
        if game_map is not None:
            army = self.get_parent_army()
            game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            if phase_name == "FIGHT_PHASE":
                root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("blood_legion_wrath_undeniable_active"):
                    exp = str(sr.get("blood_legion_wrath_undeniable_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_name:
                        if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                            wp = getattr(self, "_last_destroyed_by_weapon_profile", None)
                            parent = getattr(wp, "parent_wargear", None)
                            is_melee = False
                            is_melee_fn = getattr(parent, "is_melee", None)
                            if callable(is_melee_fn):
                                is_melee = bool(is_melee_fn())
                            if is_melee:
                                threshold = int(sr.get("blood_legion_wrath_undeniable_threshold", 4) or 4)
                                roll = int(get_roll("D6"))
                                if army is not None and getattr(army, "player", None) is not None:
                                    from ...utility.event_bus import append_dice

                                    label = str(sr.get("blood_legion_wrath_undeniable_source", "") or "Wrath Undeniable").strip()
                                    append_dice(army.player, f"{label} roll: {roll} for {self.name}")
                                if roll >= threshold:
                                    pending = getattr(root, "_blood_legion_wrath_undeniable_pending_models", None)
                                    if not isinstance(pending, list):
                                        pending = []
                                    if model not in pending:
                                        pending.append(model)
                                    root._blood_legion_wrath_undeniable_pending_models = pending
                                    return

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
                    if bool(rule.get("automatic", False)):
                        pending = getattr(root, "_melee_fight_on_death_pending_models", None)
                        if not isinstance(pending, list):
                            pending = []
                        if model not in pending:
                            pending.append(model)
                        root._melee_fight_on_death_pending_models = pending
                        return
                    roll = int(get_roll("D6"))
                    total = int(roll)
                    fortify_bonus = int(rule.get("fortify_takeover_bonus", 0) or 0)
                    if fortify_bonus > 0:
                        try:
                            army = self.get_parent_army()
                        except Exception:
                            army = None
                        mgr = getattr(army, "prioritised_efficiency", None) if army is not None else None
                        if mgr is not None and callable(getattr(mgr, "is_fortify_takeover", None)):
                            try:
                                if mgr.is_fortify_takeover():
                                    total += int(fortify_bonus)
                            except Exception:
                                pass
                    try:
                        from ...utility.event_bus import append_dice
                        pn = self.get_parent_army().player
                        if total != int(roll):
                            append_dice(
                                pn,
                                f"{rule.get('source', 'Fight on death')} roll: {roll}+{int(total - int(roll))}={total} for {self.name}",
                            )
                        else:
                            append_dice(pn, f"{rule.get('source', 'Fight on death')} roll: {roll} for {self.name}")
                    except Exception:
                        pass
                    if total >= int(rule.get("threshold", 0) or 0):
                        pending = getattr(root, "_melee_fight_on_death_pending_models", None)
                        if not isinstance(pending, list):
                            pending = []
                        if model not in pending:
                            pending.append(model)
                        root._melee_fight_on_death_pending_models = pending
                        return

        shoot_rule = self.get_shoot_on_death_after_attacks_rule(model=model)
        if shoot_rule is not None:
            try:
                root = self.get_attached_unit_root()
            except Exception:
                root = self
            if root is not None:
                wp = getattr(self, "_last_destroyed_by_weapon_profile", None)
                trigger_attack_type = str(shoot_rule.get("attack_type", "ranged") or "ranged").strip().lower()
                is_ranged = False
                is_melee = False
                try:
                    parent = getattr(wp, "parent_wargear", None)
                    is_ranged = bool(parent is not None and parent.is_ranged())
                    is_melee = bool(parent is not None and parent.is_melee())
                except Exception:
                    is_ranged = False
                    is_melee = False
                should_trigger = bool(is_ranged)
                if trigger_attack_type == "any":
                    should_trigger = True
                elif trigger_attack_type == "melee":
                    should_trigger = bool(is_melee)
                elif trigger_attack_type == "ranged":
                    should_trigger = bool(is_ranged)
                if should_trigger:
                    roll = int(get_roll("D6"))
                    total = int(roll)
                    from ...utility.event_bus import append_dice
                    army = self.get_parent_army()
                    player = getattr(army, "player", None) if army is not None else None
                    if player is not None:
                        append_dice(
                            player,
                            f"{shoot_rule.get('source', 'Shoot on death')} roll: {roll} for {self.name}",
                        )
                    if total >= int(shoot_rule.get("threshold", 0) or 0):
                        pending = getattr(root, "_shoot_on_death_pending_models", None)
                        if not isinstance(pending, list):
                            pending = []
                        if model not in pending:
                            pending.append(model)
                        root._shoot_on_death_pending_models = pending
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

        logger.info(f"{model.name} fights on death into {target_unit.name}")
        for profile in melee_profiles:
            try:
                profile.attack(target_unit, model, game_map=game_map)
            except Exception as e:
                logger.exception(f"Fight on Death attack error: {e}")

        return True

    def _try_shoot_on_death(self, model: Model, game_map: 'Map') -> bool:
        """Attempt to resolve Shoot-on-Death for a single destroyed model."""
        if getattr(model, "_shoot_on_death_used", False):
            return False

        shoot_rule = self.get_shoot_on_death_after_attacks_rule(model=model)
        full_wounds_remaining = bool((shoot_rule or {}).get("full_wounds_remaining", False))

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

        logger.info(f"{model.name} shoots on death into {best_target.name}")
        shots_executed = 0
        hit_models_by_target_weapon: dict = {}
        hit_models_by_target_psychic: dict = {}
        attack_context = {
            "pending_mortal_wounds": {},
            "defer_mortal_wounds": True,
            "hit_models_by_target_weapon": hit_models_by_target_weapon,
            "hit_models_by_target_psychic": hit_models_by_target_psychic,
        }
        original_wounds = None
        try:
            original_wounds = int(getattr(model, "wounds", 0) or 0)
        except Exception:
            original_wounds = None
        try:
            if full_wounds_remaining:
                try:
                    base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
                except Exception:
                    base_wounds = 0
                if base_wounds > 0:
                    model.wounds = int(base_wounds)
                    if hasattr(model, "_check_damaged_profile"):
                        model._check_damaged_profile()
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
                    logger.exception(f"Shoot on Death attack error: {e}")
        finally:
            if full_wounds_remaining and original_wounds is not None:
                try:
                    model.wounds = int(original_wounds)
                    if hasattr(model, "_check_damaged_profile"):
                        model._check_damaged_profile()
                except Exception:
                    pass

        self._resolve_pending_attack_mortal_wounds(attack_context, best_target, game_map=game_map)
        return shots_executed > 0

    def _apply_deadly_demise_explosion(self, *, damage_dice: DiceCollection, position, game_map: 'Map') -> None:
        if not position:
            logger.info("Cannot determine position for Deadly Demise")
            return

        putrid_afflicted = False
        putrid_owner_id = ""
        putrid_source = "Putrid Detonation"
        putrid_turn = 0
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("putrid_detonation_active"):
                putrid_afflicted = True
                putrid_owner_id = str(sr.get("putrid_detonation_owner", "") or "")
                putrid_source = str(sr.get("putrid_detonation_source", "") or "Putrid Detonation").strip() or "Putrid Detonation"
                putrid_turn = int(sr.get("putrid_detonation_turn", 0) or 0)
        except Exception:
            putrid_afflicted = False
            putrid_owner_id = ""
            putrid_source = "Putrid Detonation"
            putrid_turn = 0
        if putrid_afflicted and not putrid_owner_id:
            try:
                putrid_owner_id = str(getattr(getattr(self.get_parent_army(), "player", None), "id", "") or "")
            except Exception:
                putrid_owner_id = ""
        if putrid_afflicted and not putrid_turn:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                putrid_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            except Exception:
                putrid_turn = 0

        # Find all units within 6 inches of the explosion
        nearby_units = self._get_units_within_range(position, 6.0, game_map)
        if not nearby_units:
            logger.info("Deadly Demise triggered but no units within 6\" - no damage dealt")
            return

        # Apply damage to each nearby unit
        total_damage_dealt = 0
        for target_unit in nearby_units:
            # Roll damage independently for each unit (if it's a dice roll)
            if damage_dice.number > 0:  # It's a dice roll like D3, D6
                damage_amount = damage_dice.roll()
            else:  # It's a fixed number
                damage_amount = damage_dice.modifier

            logger.info(f"{target_unit.name} suffers {damage_amount} mortal wounds from Deadly Demise!")

            # Apply mortal wounds to the target unit
            models_destroyed = self._apply_mortal_wounds_to_unit(target_unit, damage_amount, game_map=game_map)
            total_damage_dealt += damage_amount

            if models_destroyed > 0:
                logger.info(f"Deadly Demise destroyed {models_destroyed} model(s) in {target_unit.name}")

            # Virulent Vectorium (Putrid Detonation): enemy units damaged by this explosion become Afflicted.
            if putrid_afflicted and int(damage_amount or 0) > 0:
                try:
                    target_army = target_unit.get_parent_army()
                    source_army = self.get_parent_army()
                except Exception:
                    target_army = None
                    source_army = None
                if target_army is not None and source_army is not None and target_army is not source_army:
                    tsr = getattr(target_unit, "special_rules", None)
                    if not isinstance(tsr, dict):
                        tsr = {}
                    tsr["post_shoot_afflicted_active"] = True
                    tsr["post_shoot_afflicted_owner"] = putrid_owner_id
                    tsr["post_shoot_afflicted_turn"] = int(putrid_turn or 0)
                    tsr["post_shoot_afflicted_source"] = putrid_source
                    target_unit.special_rules = tsr

        logger.info(f"Deadly Demise complete: {total_damage_dealt} total mortal wounds dealt to {len(nearby_units)} unit(s)")

    def _trigger_deadly_demise(self, dying_model: Model, game_map: 'Map') -> bool:
        """Trigger Deadly Demise ability when a model is killed.

        Returns True if the explosion is deferred (e.g., CAREEN)."""
        # Check if the unit has Deadly Demise ability
        has_deadly_demise, damage_dice = self.has_deadly_demise()
        if not has_deadly_demise:
            return False

        trigger_threshold = 6
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and sr.get("enhancement_violent_demise"):
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
            dying_id = str(get_entity_id(dying_model) or "")
            if not bearer_id or (dying_id and dying_id == bearer_id):
                trigger_threshold = int(sr.get("enhancement_violent_demise_trigger_threshold", 2) or 2)
                damage_expr = str(sr.get("enhancement_violent_demise_damage_dice", "") or "D3+1")
                damage_dice = DiceCollection.from_string(damage_expr)
        if isinstance(sr, dict) and sr.get("enhancement_gateway_unto_damnation"):
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
            dying_id = str(get_entity_id(dying_model) or "")
            if not bearer_id or (dying_id and dying_id == bearer_id):
                trigger_threshold = int(sr.get("enhancement_gateway_unto_damnation_trigger_threshold", 2) or 2)
                try:
                    destroyed_units = int(
                        sr.get("enhancement_gateway_unto_damnation_destroyed_enemy_units_this_battle", 0) or 0
                    )
                except Exception:
                    destroyed_units = 0
                if destroyed_units >= 1:
                    damage_expr = str(sr.get("enhancement_gateway_unto_damnation_damage_dice", "") or "D3+3")
                    damage_dice = DiceCollection.from_string(damage_expr)
        trigger_threshold = int(max(2, min(6, int(trigger_threshold or 6))))

        # Thousand Sons (Warpforged Cabal): Warpfire Infusion.
        # Deadly Demise triggers on 5+ while the destroyed VEHICLE model is within 6" of a friendly TS PSYKER.
        try:
            army = self.get_parent_army()
            ts_mgr = getattr(army, "thousand_sons_detachments", None) if army is not None else None
            threshold_fn = getattr(ts_mgr, "warpfire_deadly_demise_trigger_threshold", None) if ts_mgr is not None else None
            if callable(threshold_fn):
                ts_threshold = int(threshold_fn(self, model=dying_model) or 0)
                if ts_threshold > 0:
                    trigger_threshold = int(min(int(trigger_threshold), int(ts_threshold)))
        except Exception:
            pass

        # Adepta Sororitas (Exorcist): Devastating Refrain.
        # If an enemy model with Deadly Demise is destroyed by one of this source's
        # INDIRECT FIRE attacks, Deadly Demise triggers on 5+ instead of 6.
        try:
            last_weapon_profile = getattr(self, "_last_destroyed_by_weapon_profile", None)
            last_attacker_unit = getattr(self, "_last_destroyed_by_unit", None)
            if last_weapon_profile is not None and last_attacker_unit is not None:
                is_indirect_fn = getattr(last_weapon_profile, "is_indirect_fire", None)
                is_indirect = bool(is_indirect_fn()) if callable(is_indirect_fn) else False
                if is_indirect:
                    try:
                        attacker_root = last_attacker_unit.get_attached_unit_root()
                    except Exception:
                        attacker_root = last_attacker_unit
                    has_devastating_refrain = False
                    for ability in list(getattr(attacker_root, "possible_abilities", []) or []):
                        ability_name = ""
                        try:
                            if isinstance(ability, str):
                                ability_name = str(ability or "")
                            elif isinstance(ability, dict):
                                ability_name = str(ability.get("name", "") or "")
                            else:
                                ability_name = str(getattr(ability, "name", "") or "")
                        except Exception:
                            ability_name = ""
                        norm_name = re.sub(r"[^a-z0-9]+", " ", str(ability_name or "").lower()).strip()
                        if norm_name == "devastating refrain":
                            has_devastating_refrain = True
                            break
                    if has_devastating_refrain:
                        trigger_threshold = int(min(int(trigger_threshold), 5))
        except Exception:
            pass

        # Astra Militarum (Banesword): Armour Obliteration.
        # Deadly Demise triggers on 3+ instead of 6 when the destroyed model was killed by this source's quake cannon.
        try:
            last_weapon_profile = getattr(self, "_last_destroyed_by_weapon_profile", None)
            last_attacker_unit = getattr(self, "_last_destroyed_by_unit", None)
            if last_weapon_profile is not None and last_attacker_unit is not None:
                weapon_name = ""
                try:
                    parent_wargear = getattr(last_weapon_profile, "parent_wargear", None)
                    if parent_wargear is not None:
                        weapon_name = str(getattr(parent_wargear, "name", "") or "")
                except Exception:
                    weapon_name = ""
                if not weapon_name:
                    weapon_name = str(getattr(last_weapon_profile, "name", "") or "")
                weapon_key = re.sub(r"[^a-z0-9]+", " ", str(weapon_name or "").lower()).strip()
                if weapon_key == "quake cannon":
                    try:
                        attacker_root = last_attacker_unit.get_attached_unit_root()
                    except Exception:
                        attacker_root = last_attacker_unit
                    has_armour_obliteration = False
                    for ability in list(getattr(attacker_root, "possible_abilities", []) or []):
                        ability_name = ""
                        try:
                            if isinstance(ability, str):
                                ability_name = str(ability or "")
                            elif isinstance(ability, dict):
                                ability_name = str(ability.get("name", "") or "")
                            else:
                                ability_name = str(getattr(ability, "name", "") or "")
                        except Exception:
                            ability_name = ""
                        norm_name = re.sub(r"[^a-z0-9]+", " ", str(ability_name or "").lower()).strip()
                        if norm_name == "armour obliteration":
                            has_armour_obliteration = True
                            break
                    if has_armour_obliteration:
                        trigger_threshold = int(min(int(trigger_threshold), 3))
        except Exception:
            pass

        auto_trigger = False
        putrid_auto_trigger = False
        sanctified_auto_trigger = False
        emotionless_auto_trigger = False
        emotionless_source = ""
        try:
            putrid_auto_trigger = bool(getattr(dying_model, "_putrid_detonation_auto_trigger_once", False))
        except Exception:
            putrid_auto_trigger = False
        try:
            sanctified_auto_trigger = bool(getattr(dying_model, "_sanctified_immolation_auto_trigger_once", False))
        except Exception:
            sanctified_auto_trigger = False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        adm_mgr = getattr(army, "adeptus_mechanicus_detachments", None) if army is not None else None
        trigger_fn = getattr(adm_mgr, "emotionless_clarity_auto_trigger_for_destroyed_model", None) if adm_mgr is not None else None
        if callable(trigger_fn):
            try:
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            except Exception:
                game = None
            try:
                emotionless_auto_trigger, emotionless_source = trigger_fn(self, dying_model, game=game)
            except Exception:
                emotionless_auto_trigger = False
                emotionless_source = ""
        auto_trigger = bool(putrid_auto_trigger or sanctified_auto_trigger or emotionless_auto_trigger)
        if putrid_auto_trigger:
            try:
                setattr(dying_model, "_putrid_detonation_auto_trigger_once", False)
            except Exception:
                pass
        if sanctified_auto_trigger:
            try:
                setattr(dying_model, "_sanctified_immolation_auto_trigger_once", False)
            except Exception:
                pass

        logger.info(f"{self.name} has Deadly Demise {damage_dice} - checking for explosion!")

        # Roll D6 to see if Deadly Demise triggers unless auto-triggered by a stratagem.
        if not auto_trigger:
            trigger_roll = get_roll("D6")
            try:
                from ...utility.event_bus import append_dice
                pn = self.get_parent_army().player
                append_dice(pn, f"Deadly Demise trigger: rolled {trigger_roll} (need {int(trigger_threshold)}+)")
            except Exception:
                pass
            if int(trigger_roll) < int(trigger_threshold):
                logger.info(f"Deadly Demise trigger roll: {trigger_roll} (needed {int(trigger_threshold)}+) - No explosion!")
                return False
            logger.info(f"Deadly Demise trigger roll: {trigger_roll} - EXPLOSION! ")
        else:
            if sanctified_auto_trigger and not putrid_auto_trigger:
                logger.info("Deadly Demise auto-triggered (Sanctified Immolation).")
            elif emotionless_auto_trigger:
                logger.info(f"Deadly Demise auto-triggered ({str(emotionless_source or 'Emotionless Clarity')}).")
            else:
                logger.info("Deadly Demise auto-triggered (Putrid Detonation).")

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
            logger.info(f"Cannot determine position of dying model for Deadly Demise")
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

    def _legion_of_excess_thieves_of_pain_redirect_target(self, *, game_map: Optional['Map'] = None):
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return None
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            return None
        if not bool(special_rules.get("legion_of_excess_thieves_of_pain_active", False)):
            return None
        redirect_unit_id = str(special_rules.get("legion_of_excess_thieves_of_pain_redirect_unit_id", "") or "").strip()
        if not redirect_unit_id:
            return None

        game = None
        try:
            army = root.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        except Exception:
            game = None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        if game_map is None:
            return None

        expires_phase = str(special_rules.get("legion_of_excess_thieves_of_pain_expires_phase", "") or "").strip().upper()
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
        if expires_phase and phase_name and phase_name != expires_phase:
            return None

        for unit in list(getattr(game_map, "units", []) or []):
            try:
                candidate = unit.get_attached_unit_root()
            except Exception:
                candidate = unit
            if candidate is None:
                continue
            if str(get_entity_id(candidate) or "") != redirect_unit_id:
                continue
            if candidate is root:
                return None
            try:
                if not candidate.is_alive():
                    return None
            except Exception:
                return None
            try:
                if not bool(getattr(candidate, "deployed", False)):
                    return None
            except Exception:
                return None
            try:
                if getattr(candidate, "is_in_reserves", lambda: False)():
                    return None
            except Exception:
                return None
            try:
                if bool(getattr(candidate, "is_embarked", False)) or bool(getattr(candidate, "embarked_in", None)):
                    return None
            except Exception:
                return None
            return candidate
        return None

    def _apply_legion_of_excess_thieves_of_pain_redirect(
        self,
        wound_count: int,
        *,
        game_map: Optional['Map'] = None,
        source_model: Optional['Model'] = None,
        damage_source: str = "",
    ) -> int:
        wounds = int(wound_count or 0)
        if wounds <= 0:
            return 0
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return 0

        redirected = 0
        for _ in range(wounds):
            redirect_target = root._legion_of_excess_thieves_of_pain_redirect_target(game_map=game_map)
            if redirect_target is None:
                break
            root._apply_mortal_wounds_to_unit(
                redirect_target,
                1,
                game_map=game_map,
                attacker_unit=root,
                attacker_model=source_model,
                damage_source="legion_of_excess_thieves_of_pain",
            )
            redirected += 1
        return int(redirected)

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
        damage_source: str = "mortal",
    ) -> int:
        """Apply mortal wounds to a unit, distributing them among models.

        Args:
            target_unit: The unit to apply mortal wounds to
            mortal_wound_amount: Number of mortal wounds to apply
            initial_model: Optional model to allocate the first mortal wound to (e.g., Precision)
            apply_fn: Optional callback to apply each mortal wound to a model (defaults to Model.take_damage)
            allocation_ctx: Optional DamageAllocationCtx override for UI context
            allow_initial_model_outside_candidates: Allow initial_model even if not in allocation candidates
            damage_source: Label used for per-wound damage source context

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
        ctx = allocation_ctx or DamageAllocationCtx(
            reason="Allocate mortal wound",
            damage_source=str(damage_source or "mortal"),
        )
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

