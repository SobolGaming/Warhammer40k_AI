"""Lifecycle, status, and deferred-resolution helpers for Unit positioning/runtime state."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class PositioningLifecycleMixin:
    def take_damage(self, amount: int):
        pass


    def apply_status_effect(self, status_effect: StatusEffect) -> None:
        status_effect.apply_effect(self)
        effects = getattr(self, "status_effects", None)
        if not isinstance(effects, list):
            self.status_effects = []
        self.status_effects.append(status_effect)


    def remove_status_effect(self, status_effect: StatusEffect) -> None:
        status_effect.remove_effect(self)
        effects = getattr(self, "status_effects", None)
        if not isinstance(effects, list):
            self.status_effects = []
        if status_effect in self.status_effects:
            self.status_effects.remove(status_effect)


    def is_alive(self) -> bool:
        if bool(getattr(self, "_careen_pending_destroyed", False)):
            return False
        # Attached unit is alive if either bodyguards or attached leaders have alive models.
        if len(self.models) > 0:
            return True
        try:
            for l in list(getattr(self, "attached_leaders", []) or []):
                if len(getattr(l, "models", []) or []) > 0:
                    return True
        except Exception:
            pass
        return False


    def is_active_for_rules(self) -> bool:
        """True if the unit is alive and on the battlefield for rules purposes."""
        if not self.is_alive():
            return False
        if not bool(getattr(self, "deployed", False)):
            return False
        if str(getattr(self, "reserve_status", "deployed") or "deployed") != "deployed":
            return False
        try:
            if self.is_embarked:
                return False
        except Exception:
            if getattr(self, "embarked_in", None):
                return False
        return True


    def resolve_pending_leader_separation(self, game_map: Optional['Map'] = None) -> None:
        """If this bodyguard has pending separation, detach leaders into solo units now."""
        if not bool(getattr(self, "_pending_leader_separation", False)):
            return
        try:
            attached = list(getattr(self, "attached_leaders", []) or [])
        except Exception:
            attached = []
        if not attached:
            self._pending_leader_separation = False
            return

        try:
            if len(getattr(self, "models", []) or []) == 0:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                event_system = getattr(game, "event_system", None) if game is not None else None
                if event_system is not None:
                    event_system.publish(
                        "bodyguard_unit_destroyed",
                        bodyguard_unit=self,
                        surviving_leaders=list(attached),
                        destroyed_by_model=getattr(self, "_last_destroyed_by_model", None),
                        destroyed_by_unit=getattr(self, "_last_destroyed_by_unit", None),
                        destroyed_by_weapon_profile=getattr(self, "_last_destroyed_by_weapon_profile", None),
                        game_map=game_map,
                    )
        except Exception:
            pass

        for leader in attached:
            try:
                leader.detach_from_unit()
                leader.deployed = True
                leader.set_reserve_status("deployed")
                leader.reserve_turn_deployed = getattr(self, "reserve_turn_deployed", None)
                if game_map is not None and hasattr(game_map, "units"):
                    if leader not in game_map.units:
                        game_map.units.append(leader)
            except Exception:
                continue

        # Remove the bodyguard unit from the map if it has no models left.
        try:
            if game_map is not None and hasattr(game_map, "units") and self in game_map.units and len(self.models) == 0:
                game_map.units.remove(self)
        except Exception:
            pass

        self._pending_leader_separation = False


    def _attack_resolution_root(self) -> 'Unit':
        """Resolve attack-window bookkeeping to the attached-unit root (bodyguard)."""
        try:
            return self.get_attached_unit_root()
        except Exception:
            return self


    def begin_attack_resolution(self) -> None:
        """Mark that an attacking unit has started resolving attacks against this unit."""
        root = self._attack_resolution_root()
        try:
            depth = int(getattr(root, "_attack_resolution_depth", 0))
        except Exception:
            depth = 0
        root._attack_resolution_depth = depth + 1


    def end_attack_resolution(self, game_map: Optional['Map'] = None) -> None:
        """Mark that an attacking unit finished resolving attacks; resolve pending separation if safe."""
        root = self._attack_resolution_root()
        try:
            depth = int(getattr(root, "_attack_resolution_depth", 0))
        except Exception:
            depth = 0
        depth = max(0, depth - 1)
        root._attack_resolution_depth = depth
        if depth == 0:
            try:
                root.resolve_pending_leader_separation(game_map=game_map)
            except Exception:
                pass

            # WORLD EATERS: Resolve any deferred Total Carnage fights now that the attacker finished its attacks.
            try:
                army = root.get_parent_army()
                mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
                game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
                br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                if mgr is not None and br > 0 and mgr.is_blessing_active_for_unit("TOTAL_CARNAGE", root, battle_round=br):
                    # Only if this attached unit group actually qualifies for Blessings
                    if root.attached_unit_has_blessings_of_khorne():
                        mgr.resolve_total_carnage_queue(owning_unit=root, game_map=game_map)
            except Exception:
                pass
            try:
                root._resolve_death_ecstasy_queue(game_map=game_map)
            except Exception:
                pass
            try:
                root._resolve_beautiful_death_queue(game_map=game_map)
            except Exception:
                pass
            try:
                root._resolve_berserk_fugue_queue(game_map=game_map)
            except Exception:
                pass
            try:
                root._resolve_hysterical_frenzy_queue(game_map=game_map)
            except Exception:
                pass
            try:
                root._resolve_deathless_duty_queue(game_map=game_map)
            except Exception:
                pass
            try:
                root._resolve_spirit_of_martyr_queue(game_map=game_map)
            except Exception:
                pass
            try:
                root._resolve_immortal_fury_queue(game_map=game_map)
            except Exception:
                pass
            try:
                root._resolve_blood_legion_wrath_undeniable_queue(game_map=game_map)
            except Exception:
                pass
            try:
                root._resolve_orks_is_never_beaten_queue(game_map=game_map)
            except Exception:
                pass
            try:
                root._resolve_defiant_to_last_queue(game_map=game_map)
            except Exception:
                pass
            try:
                root._resolve_shoot_on_death_after_attacks_queue(game_map=game_map)
            except Exception:
                pass
            try:
                root._resolve_melee_fight_on_death_queue(game_map=game_map)
            except Exception:
                pass
            try:
                root._resolve_death_vision_of_sanguinius_queue(game_map=game_map)
            except Exception:
                pass
            root._resolve_pending_horrors_split(game_map=game_map)


    def _resolve_deferred_fight_on_death_queue(self, attr_name: str, game_map: Optional['Map'] = None) -> None:
        pending = getattr(self, attr_name, None)
        if not pending:
            return
        if not isinstance(pending, list):
            setattr(self, attr_name, [])
            return
        setattr(self, attr_name, [])
        metadata_by_model_id = getattr(self, "_melee_fight_on_death_pending_metadata", None)
        if not isinstance(metadata_by_model_id, dict):
            metadata_by_model_id = {}

        def _enemy_alive_model_count(source_unit) -> int:
            if game_map is None or source_unit is None:
                return 0
            try:
                enemies = list(game_map.get_enemy_units(source_unit) or [])
            except Exception:
                enemies = []
            alive_count = 0
            for enemy in list(enemies or []):
                if enemy is None:
                    continue
                for enemy_model in list(getattr(enemy, "models", []) or []):
                    if enemy_model is None:
                        continue
                    alive_attr = getattr(enemy_model, "is_alive", True)
                    try:
                        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    except Exception:
                        alive = False
                    if alive:
                        alive_count += 1
            return int(alive_count)

        for model in list(pending):
            if model is None:
                continue
            original_wounds = getattr(model, "_wounds", None)
            model_id = str(get_entity_id(model) or "")
            metadata = metadata_by_model_id.pop(model_id, None) if model_id else None
            restore_original_wounds = True
            try:
                source_unit = getattr(model, "parent_unit", None)
                before_enemy_count = 0
                if isinstance(metadata, dict) and bool(metadata.get("survive_if_enemy_models_destroyed", False)):
                    before_enemy_count = _enemy_alive_model_count(source_unit or self)
                if original_wounds is not None and original_wounds <= 0:
                    model._wounds = 1
                self._try_fight_on_death(model=model, game_map=game_map)
                if isinstance(metadata, dict) and bool(metadata.get("survive_if_enemy_models_destroyed", False)):
                    after_enemy_count = _enemy_alive_model_count(source_unit or self)
                    if after_enemy_count < before_enemy_count and source_unit is not None:
                        if model not in list(getattr(source_unit, "models", []) or []):
                            source_unit.models.append(model)
                        try:
                            source_unit.models_lost.remove(model)
                        except Exception:
                            pass
                        try:
                            round_state = getattr(source_unit, "round_state", None)
                            if round_state is not None and hasattr(round_state, "num_lost_models_this_round"):
                                round_state.num_lost_models_this_round = max(
                                    0,
                                    int(getattr(round_state, "num_lost_models_this_round", 0) or 0) - 1,
                                )
                        except Exception:
                            pass
                        try:
                            source_unit._invalidate_ability_cache()
                        except Exception:
                            pass
                        try:
                            source_unit.update_coherency()
                        except Exception:
                            pass
                        if original_wounds is not None:
                            model._wounds = max(0, int(original_wounds))
                        heal_expr = str(metadata.get("heal_expr", "") or "").strip().upper()
                        heal_amount = get_roll(heal_expr or "D3")
                        model.heal(heal_amount)
                        try:
                            army = source_unit.get_parent_army()
                        except Exception:
                            army = None
                        game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                        if game is not None:
                            try:
                                game.event_system.publish(
                                    "model_healed",
                                    model=model,
                                    unit=source_unit,
                                    amount=int(heal_amount),
                                    reason=str(metadata.get("source", "") or "Fight on death").strip() or "Fight on death",
                                )
                            except Exception:
                                pass
                        restore_original_wounds = False
                    elif bool(metadata.get("delay_unit_destroyed_event", False)) and source_unit is not None:
                        try:
                            if bool(getattr(source_unit, "is_leader", False)) and getattr(source_unit, "attached_to", None) is not None:
                                source_unit.detach_from_unit()
                        except Exception:
                            pass
                        try:
                            army = source_unit.get_parent_army()
                        except Exception:
                            army = None
                        game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                        if game is not None:
                            try:
                                game.event_system.publish(
                                    "unit_destroyed",
                                    unit=source_unit,
                                    last_model=model,
                                    destroyed_by_model=getattr(source_unit, "_last_destroyed_by_model", None),
                                    destroyed_by_unit=getattr(source_unit, "_last_destroyed_by_unit", None),
                                    destroyed_by_weapon_profile=getattr(source_unit, "_last_destroyed_by_weapon_profile", None),
                                    game_map=game_map,
                                )
                            except Exception:
                                pass
            finally:
                if restore_original_wounds and original_wounds is not None:
                    model._wounds = original_wounds
        self._melee_fight_on_death_pending_metadata = metadata_by_model_id


    def _resolve_death_ecstasy_queue(self, game_map: Optional['Map'] = None) -> None:
        """Resolve deferred Death Ecstasy fights after an attacker finishes its attacks."""
        self._resolve_deferred_fight_on_death_queue("_death_ecstasy_pending_models", game_map=game_map)


    def _resolve_beautiful_death_queue(self, game_map: Optional['Map'] = None) -> None:
        """Resolve deferred Beautiful Death fights after an attacker finishes its attacks."""
        self._resolve_deferred_fight_on_death_queue("_beautiful_death_pending_models", game_map=game_map)


    def _resolve_berserk_fugue_queue(self, game_map: Optional['Map'] = None) -> None:
        """Resolve deferred Berserk Fugue fights after an attacker finishes its attacks."""
        self._resolve_deferred_fight_on_death_queue("_berserk_fugue_pending_models", game_map=game_map)


    def _resolve_hysterical_frenzy_queue(self, game_map: Optional['Map'] = None) -> None:
        """Resolve deferred Hysterical Frenzy fights after an attacker finishes its attacks."""
        self._resolve_deferred_fight_on_death_queue("_hysterical_frenzy_pending_models", game_map=game_map)


    def _resolve_deathless_duty_queue(self, game_map: Optional['Map'] = None) -> None:
        """Resolve deferred Deathless Duty fights after an attacker finishes its attacks."""
        self._resolve_deferred_fight_on_death_queue("_deathless_duty_pending_models", game_map=game_map)


    def _resolve_spirit_of_martyr_queue(self, game_map: Optional['Map'] = None) -> None:
        """Resolve deferred Spirit of the Martyr fights after an attacker finishes its attacks."""
        self._resolve_deferred_fight_on_death_queue("_spirit_of_martyr_pending_models", game_map=game_map)


    def _resolve_immortal_fury_queue(self, game_map: Optional['Map'] = None) -> None:
        """Resolve deferred Immortal Fury fights after an attacker finishes its attacks."""
        self._resolve_deferred_fight_on_death_queue("_immortal_fury_pending_models", game_map=game_map)


    def _resolve_blood_legion_wrath_undeniable_queue(self, game_map: Optional['Map'] = None) -> None:
        """Resolve deferred Wrath Undeniable fights after an attacker finishes its attacks."""
        self._resolve_deferred_fight_on_death_queue("_blood_legion_wrath_undeniable_pending_models", game_map=game_map)


    def _resolve_orks_is_never_beaten_queue(self, game_map: Optional['Map'] = None) -> None:
        """Resolve deferred Orks Is Never Beaten fights after an attacker finishes its attacks."""
        self._resolve_deferred_fight_on_death_queue("_orks_is_never_beaten_pending_models", game_map=game_map)


    def _resolve_defiant_to_last_queue(self, game_map: Optional['Map'] = None) -> None:
        """Resolve deferred Defiant to the Last fights after an attacker finishes its attacks."""
        self._resolve_deferred_fight_on_death_queue("_defiant_to_last_pending_models", game_map=game_map)


    def _resolve_deferred_shoot_on_death_queue(self, attr_name: str, game_map: Optional['Map'] = None) -> None:
        pending = getattr(self, attr_name, None)
        if not pending:
            return
        if not isinstance(pending, list):
            setattr(self, attr_name, [])
            return
        setattr(self, attr_name, [])
        for model in list(pending):
            if model is None:
                continue
            original_wounds = getattr(model, "_wounds", None)
            try:
                if original_wounds is not None and original_wounds <= 0:
                    model._wounds = 1
                self._try_shoot_on_death(model=model, game_map=game_map)
            finally:
                if original_wounds is not None:
                    model._wounds = original_wounds


    def _resolve_shoot_on_death_after_attacks_queue(self, game_map: Optional['Map'] = None) -> None:
        """Resolve deferred shoot-on-death attacks after an attacker finishes its attacks."""
        self._resolve_deferred_shoot_on_death_queue("_shoot_on_death_pending_models", game_map=game_map)


    def _resolve_melee_fight_on_death_queue(self, game_map: Optional['Map'] = None) -> None:
        """Resolve deferred melee fight-on-death fights after an attacker finishes its attacks."""
        self._resolve_deferred_fight_on_death_queue("_melee_fight_on_death_pending_models", game_map=game_map)
