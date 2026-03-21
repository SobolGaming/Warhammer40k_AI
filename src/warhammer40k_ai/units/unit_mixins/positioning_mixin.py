"""Auto-extracted Unit mixin methods from unit.py."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class PositioningMixin:
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

    ###########################################################################
    ### Position and Coherency
    ###########################################################################

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
                        heal_amount = int(get_roll(heal_expr or "D3"))
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

    def attached_unit_has_blessings_of_khorne(self) -> bool:
        """Attached unit eligibility: true if any attached member (bodyguard or leader) has Blessings of Khorne ability."""
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "blood_tithe_might_of_khorne_applies", None):
                if mgr.blood_tithe_might_of_khorne_applies(self):
                    return True
            if mgr is not None and getattr(mgr, "unit_is_blood_legions", None):
                if mgr.unit_is_blood_legions(self) and self._unit_within_icon_of_war_range():
                    return True
        except Exception:
            pass
        for u in self.get_attached_unit_members():
            try:
                found, _ = u._find_ability_with_patterns(["blessings of khorne"])
            except Exception:
                found = False
            if found:
                return True
        return False

    def has_icon_of_khorne(self) -> bool:
        """True if this unit has the Icon of Khorne ability."""
        if "icon_of_khorne" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["icon_of_khorne"])
        found, _ = self._find_ability_with_patterns(["icon of khorne"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["icon_of_khorne"] = bool(found)
        return bool(found)

    def has_icon_of_war(self) -> bool:
        """True if this unit has the Icon of War enhancement."""
        cache_key = "icon_of_war"
        if cache_key in getattr(self, "_ability_cache", {}):
            if bool(self._ability_cache[cache_key]):
                return True
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_icon_of_war"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "icon of war" or enh_id == "000010078002":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def has_disciple_of_khorne(self) -> bool:
        """True if this unit has the Disciple of Khorne enhancement."""
        cache_key = "disciple_of_khorne"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_disciple_of_khorne"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "disciple of khorne" or enh_id == "000010078004":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def has_butcher_lord(self) -> bool:
        """True if this unit has the Butcher Lord enhancement."""
        cache_key = "butcher_lord"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_butcher_lord"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "butcher lord" or enh_id == "000010074003":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def has_abhuman_detail(self) -> bool:
        """True if this unit has the Abhuman Detail enhancement."""
        cache_key = "abhuman_detail"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_abhuman_detail"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "abhuman detail" or enh_id == "000010637002":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def has_exalted_patron(self) -> bool:
        """True if this unit has the Exalted Patron enhancement."""
        cache_key = "exalted_patron"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_exalted_patron"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "exalted patron" or enh_id == "000010654003":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def has_wolf_touched(self) -> bool:
        """True if this unit has the Wolf-touched enhancement."""
        cache_key = "wolf_touched"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_wolf_touched"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower().replace("\u2019", "'").replace("\u2018", "'")
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "wolf-touched" or enh_id == "000010269002":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def has_grimnars_mark(self) -> bool:
        """True if this unit has the Grimnar's Mark enhancement."""
        cache_key = "grimnars_mark"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_grimnars_mark"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = (
                    str(getattr(enh, "name", "") or "")
                    .strip()
                    .lower()
                    .replace("\u2019", "'")
                    .replace("\u2018", "'")
                )
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name in ("grimnar's mark", "grimnars mark") or enh_id == "000010660002":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def has_catechism_of_divine_penitence(self) -> bool:
        """True if this unit has the Catechism of Divine Penitence enhancement."""
        cache_key = "catechism_of_divine_penitence"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_catechism_of_divine_penitence"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "catechism of divine penitence" or enh_id == "000009029005":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def _attached_unit_has_enhancement_flag(
        self,
        flag_key: str,
        *,
        enhancement_id: str = "",
        enhancement_name: str = "",
    ) -> bool:
        if not flag_key and not enhancement_id and not enhancement_name:
            return False
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
        norm_name = ""
        if enhancement_name:
            try:
                norm_name = str(enhancement_name or "").strip().lower()
            except Exception:
                norm_name = ""
        for unit in members:
            if unit is None:
                continue
            try:
                sr = getattr(unit, "special_rules", None)
                if isinstance(sr, dict) and flag_key and sr.get(flag_key):
                    return True
            except Exception:
                pass
            try:
                enh = getattr(unit, "enhancement", None)
                if enh is None:
                    continue
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if enhancement_id and enh_id == enhancement_id:
                    return True
                if norm_name:
                    enh_name = str(getattr(enh, "name", "") or "").strip().lower()
                    if enh_name == norm_name:
                        return True
            except Exception:
                continue
        return False

    def _attached_unit_has_active_enhancement(
        self,
        flag_key: str,
        *,
        enhancement_id: str = "",
        enhancement_name: str = "",
        require_bearer_alive: bool = True,
    ) -> bool:
        """
        Return True when any attached-unit member has the enhancement and (by default)
        the bearer model is alive.
        """
        if not flag_key and not enhancement_id and not enhancement_name:
            return False

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

        norm_name = ""
        if enhancement_name:
            try:
                norm_name = str(enhancement_name or "").strip().lower()
            except Exception:
                norm_name = ""

        for unit in members:
            if unit is None:
                continue

            matched = False
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict) and flag_key and sr.get(flag_key):
                matched = True
            if not matched:
                try:
                    enh = getattr(unit, "enhancement", None)
                    if enh is not None:
                        enh_unit_id = str(getattr(enh, "id", "") or "").strip()
                        if enhancement_id and enh_unit_id == enhancement_id:
                            matched = True
                        elif norm_name:
                            enh_name = str(getattr(enh, "name", "") or "").strip().lower()
                            if enh_name == norm_name:
                                matched = True
                except Exception:
                    matched = False
            if not matched:
                continue

            if not require_bearer_alive:
                return True

            bearer_id = ""
            if isinstance(sr, dict):
                bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
            if bearer_id:
                for model in list(getattr(unit, "models", []) or []):
                    try:
                        model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                    except Exception:
                        model_id = ""
                    if model_id != bearer_id:
                        continue
                    try:
                        alive_attr = getattr(model, "is_alive", True)
                        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    except Exception:
                        alive = False
                    if alive:
                        return True
                continue

            get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
            if callable(get_bearer):
                try:
                    if get_bearer() is not None:
                        return True
                    continue
                except Exception:
                    continue

            for model in list(getattr(unit, "models", []) or []):
                try:
                    alive_attr = getattr(model, "is_alive", True)
                    alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                except Exception:
                    alive = False
                if alive:
                    return True

        return False

    @staticmethod
    def _attached_unit_sort_key(entity) -> tuple[int, str, str]:
        entity_id = str(get_entity_id(entity) or "").strip()
        name = str(getattr(entity, "name", "") or "").strip().lower()
        if entity_id:
            return (0, entity_id, name)
        return (1, name, "")

    @staticmethod
    def _enhancement_bearer_is_alive_for_unit(unit, special_rules: Optional[dict] = None) -> bool:
        sr = special_rules if isinstance(special_rules, dict) else getattr(unit, "special_rules", None)
        models = list(getattr(unit, "models", []) or [])

        bearer_id = ""
        if isinstance(sr, dict):
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
        if bearer_id:
            for model in models:
                model_id = str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                if model_id != bearer_id:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                return bool(alive_attr() if callable(alive_attr) else alive_attr)
            return False

        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is None:
                return False
            alive_attr = getattr(bearer, "is_alive", True)
            return bool(alive_attr() if callable(alive_attr) else alive_attr)

        for model in models:
            alive_attr = getattr(model, "is_alive", True)
            if bool(alive_attr() if callable(alive_attr) else alive_attr):
                return True
        return False

    def _attached_unit_active_enhancement_sources(
        self,
        flag_key: str,
        *,
        enhancement_id: str = "",
        enhancement_name: str = "",
        require_bearer_alive: bool = True,
        source_keys: tuple[str, ...] = (),
    ) -> list[dict]:
        """
        Return matching attached-unit enhancement sources sorted by canonical entity id.
        """
        if not flag_key and not enhancement_id and not enhancement_name:
            return []

        get_root = getattr(self, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else self
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]

        norm_name = str(enhancement_name or "").strip().lower()
        ordered_members = [member for member in members if member is not None]
        ordered_members.sort(key=self._attached_unit_sort_key)

        results: list[dict] = []
        for member in ordered_members:
            sr = getattr(member, "special_rules", None)
            enh = getattr(member, "enhancement", None)
            matched = False
            if isinstance(sr, dict) and flag_key and bool(sr.get(flag_key)):
                matched = True
            if not matched and enh is not None:
                enh_unit_id = str(getattr(enh, "id", "") or "").strip()
                if enhancement_id and enh_unit_id == enhancement_id:
                    matched = True
                elif norm_name and str(getattr(enh, "name", "") or "").strip().lower() == norm_name:
                    matched = True
            if not matched:
                continue
            if require_bearer_alive and not self._enhancement_bearer_is_alive_for_unit(
                member,
                sr if isinstance(sr, dict) else None,
            ):
                continue

            source = ""
            if isinstance(sr, dict):
                for source_key in source_keys:
                    source = str(sr.get(source_key, "") or "").strip()
                    if source:
                        break
            if not source and enh is not None:
                source = str(getattr(enh, "name", "") or enhancement_name or "Enhancement").strip()
            if not source and enhancement_name:
                source = str(enhancement_name or "").strip()

            results.append(
                {
                    "unit": member,
                    "special_rules": sr if isinstance(sr, dict) else {},
                    "enhancement": enh,
                    "source": source or "Enhancement",
                }
            )
        return results

    def _attached_unit_has_active_leading_enhancement(
        self,
        flag_key: str,
        *,
        enhancement_id: str = "",
        enhancement_name: str = "",
        require_bearer_alive: bool = True,
    ) -> bool:
        """
        Return True when an attached Leader has the enhancement and (by default)
        its bearer model is alive.
        """
        if not flag_key and not enhancement_id and not enhancement_name:
            return False

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        leaders = list(getattr(root, "attached_leaders", []) or [])
        if not leaders:
            return False

        norm_name = ""
        if enhancement_name:
            try:
                norm_name = str(enhancement_name or "").strip().lower()
            except Exception:
                norm_name = ""

        for leader in leaders:
            if leader is None:
                continue

            matched = False
            sr = getattr(leader, "special_rules", None)
            if isinstance(sr, dict) and flag_key and sr.get(flag_key):
                matched = True
            if not matched:
                try:
                    enh = getattr(leader, "enhancement", None)
                    if enh is not None:
                        enh_unit_id = str(getattr(enh, "id", "") or "").strip()
                        if enhancement_id and enh_unit_id == enhancement_id:
                            matched = True
                        elif norm_name:
                            enh_name = str(getattr(enh, "name", "") or "").strip().lower()
                            if enh_name == norm_name:
                                matched = True
                except Exception:
                    matched = False
            if not matched:
                continue

            if not require_bearer_alive:
                return True

            bearer_id = ""
            if isinstance(sr, dict):
                bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
            if bearer_id:
                for model in list(getattr(leader, "models", []) or []):
                    try:
                        model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                    except Exception:
                        model_id = ""
                    if model_id != bearer_id:
                        continue
                    try:
                        alive_attr = getattr(model, "is_alive", True)
                        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    except Exception:
                        alive = False
                    if alive:
                        return True
                continue

            get_bearer = getattr(leader, "_get_enhancement_bearer_model", None)
            if callable(get_bearer):
                try:
                    bearer = get_bearer()
                except Exception:
                    bearer = None
                if bearer is None:
                    continue
                try:
                    alive_attr = getattr(bearer, "is_alive", True)
                    alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                except Exception:
                    alive = False
                if alive:
                    return True
                continue

            for model in list(getattr(leader, "models", []) or []):
                try:
                    alive_attr = getattr(model, "is_alive", True)
                    alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                except Exception:
                    alive = False
                if alive:
                    return True

        return False

    def _attached_unit_model_is_enhancement_bearer(
        self,
        model,
        *,
        flag_key: str,
        enhancement_id: str = "",
        enhancement_name: str = "",
        require_leading: bool = False,
        require_bearer_alive: bool = True,
    ) -> bool:
        """
        Return True when `model` is the enhancement bearer for a matching attached-unit enhancement.
        """
        if model is None or (not flag_key and not enhancement_id and not enhancement_name):
            return False
        model_id = str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "")
        if not model_id:
            return False

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if require_leading:
            candidates = list(getattr(root, "attached_leaders", []) or [])
        else:
            try:
                candidates = list(root.get_attached_unit_members() or [])
            except Exception:
                candidates = [root]
        if not candidates:
            candidates = [root]

        norm_name = ""
        if enhancement_name:
            try:
                norm_name = str(enhancement_name or "").strip().lower()
            except Exception:
                norm_name = ""

        for unit in candidates:
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            matched = bool(isinstance(sr, dict) and flag_key and sr.get(flag_key))
            if not matched:
                try:
                    enh = getattr(unit, "enhancement", None)
                    if enh is not None:
                        enh_unit_id = str(getattr(enh, "id", "") or "").strip()
                        if enhancement_id and enh_unit_id == enhancement_id:
                            matched = True
                        elif norm_name:
                            enh_name = str(getattr(enh, "name", "") or "").strip().lower()
                            if enh_name == norm_name:
                                matched = True
                except Exception:
                    matched = False
            if not matched:
                continue

            bearer = None
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "") if isinstance(sr, dict) else ""
            if bearer_id:
                for candidate_model in list(getattr(unit, "models", []) or []):
                    candidate_id = str(get_entity_id(candidate_model) or getattr(candidate_model, "id", getattr(candidate_model, "_id", "")) or "")
                    if candidate_id == bearer_id:
                        bearer = candidate_model
                        break
            if bearer is None:
                get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
                if callable(get_bearer):
                    try:
                        bearer = get_bearer()
                    except Exception:
                        bearer = None
            if bearer is None:
                continue

            bearer_entity_id = str(get_entity_id(bearer) or getattr(bearer, "id", getattr(bearer, "_id", "")) or "")
            if bearer_entity_id != model_id:
                continue
            if not require_bearer_alive:
                return True
            try:
                alive_attr = getattr(bearer, "is_alive", True)
                alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            except Exception:
                alive = False
            if alive:
                return True
        return False

    def _is_lord_on_juggernaut(self) -> bool:
        try:
            dsid = str(getattr(getattr(self, "_datasheet", None), "id", "") or "").strip()
        except Exception:
            dsid = ""
        if dsid == "000002625":
            return True
        try:
            name = self._normalize_attached_unit_name(getattr(self, "name", ""))
        except Exception:
            name = ""
        return name == "lord on juggernaut"

    def _disciple_of_khorne_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        try:
            dsid = str(getattr(getattr(bodyguard, "_datasheet", None), "id", "") or "").strip()
        except Exception:
            dsid = ""
        if dsid in {"000004107", "000004108"}:
            return True
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        return name in {"bloodcrushers", "flesh hounds"}

    def _disciple_of_khorne_is_bearer(self) -> bool:
        if not self.has_disciple_of_khorne():
            return False
        if not self.is_leader:
            return False
        if not self._is_lord_on_juggernaut():
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if mgr is None:
            return False
        try:
            if not mgr.is_khorne_daemonkin():
                return False
        except Exception:
            return False
        return True

    def _disciple_of_khorne_active(self, bodyguard=None) -> bool:
        if not self._disciple_of_khorne_is_bearer():
            return False
        if bodyguard is None:
            bodyguard = getattr(self, "attached_to", None)
        if bodyguard is None:
            return False
        return self._disciple_of_khorne_bodyguard_allowed(bodyguard)

    def _disciple_of_khorne_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._disciple_of_khorne_is_bearer():
            return False
        return self._disciple_of_khorne_bodyguard_allowed(bodyguard)

    def _butcher_lord_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        try:
            if bodyguard.has_any_keyword("JAKHALS"):
                return True
        except Exception:
            pass
        try:
            if bodyguard.has_any_keyword("GOREMONGERS"):
                return True
        except Exception:
            pass
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        return name in {"jakhals", "goremongers"}

    def _butcher_lord_is_bearer(self) -> bool:
        if not self.has_butcher_lord():
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if mgr is None:
            return False
        try:
            if not mgr.is_cult_of_blood():
                return False
        except Exception:
            return False
        return True

    def _butcher_lord_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._butcher_lord_is_bearer():
            return False
        return self._butcher_lord_bodyguard_allowed(bodyguard)

    def _abhuman_detail_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        try:
            if bodyguard.has_any_keyword("OGRYN"):
                return True
        except Exception:
            pass
        configured_names: list[str] = []
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict):
                configured_names = [
                    self._normalize_attached_unit_name(v)
                    for v in list(sr.get("enhancement_abhuman_detail_attach_unit_names", ()) or ())
                    if str(v or "").strip()
                ]
        except Exception:
            configured_names = []
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        if name in set(configured_names):
            return True
        return name in {"ogryn squad", "bullgryn squad", "ogryns", "bullgryns"}

    def _abhuman_detail_is_bearer(self) -> bool:
        if not self.has_abhuman_detail():
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        try:
            if not self.has_any_keyword("COMMISSAR"):
                return False
        except Exception:
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        if mgr is None:
            return False
        try:
            if not mgr.is_grizzled_company():
                return False
        except Exception:
            return False
        return True

    def _abhuman_detail_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._abhuman_detail_is_bearer():
            return False
        return self._abhuman_detail_bodyguard_allowed(bodyguard)

    def _butcher_lord_infiltrators_active(self, bodyguard=None) -> bool:
        if not self._butcher_lord_is_bearer():
            return False
        if bodyguard is None:
            bodyguard = getattr(self, "attached_to", None)
        if bodyguard is None:
            return False
        try:
            if bodyguard.has_any_keyword("GOREMONGERS"):
                return True
        except Exception:
            pass
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        return name == "goremongers"

    def _is_lord_exultant(self) -> bool:
        try:
            dsid = str(getattr(getattr(self, "_datasheet", None), "id", "") or "").strip()
        except Exception:
            dsid = ""
        if dsid == "000004078":
            return True
        try:
            name = self._normalize_attached_unit_name(getattr(self, "name", ""))
        except Exception:
            name = ""
        return name == "lord exultant"

    def _exalted_patron_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        try:
            dsid = str(getattr(getattr(bodyguard, "_datasheet", None), "id", "") or "").strip()
        except Exception:
            dsid = ""
        if dsid == "000004089":
            return True
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        return name == "flawless blades"

    def _exalted_patron_is_bearer(self) -> bool:
        if not self.has_exalted_patron():
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        if not self._is_lord_exultant():
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "emperors_children_detachments", None) if army is not None else None
        if mgr is None:
            mgr = getattr(army, "emperors_children", None) if army is not None else None
        if mgr is None:
            return False
        try:
            if not mgr.is_court_of_the_phoenician():
                return False
        except Exception:
            return False
        return True

    def _exalted_patron_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._exalted_patron_is_bearer():
            return False
        return self._exalted_patron_bodyguard_allowed(bodyguard)

    def _wolf_touched_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        has_wulfen_keyword = False
        has_infantry_keyword = False
        try:
            has_wulfen_keyword = bool(bodyguard.has_any_keyword("WULFEN"))
        except Exception:
            has_wulfen_keyword = False
        try:
            has_infantry_keyword = bool(bodyguard.has_any_keyword("INFANTRY"))
        except Exception:
            has_infantry_keyword = False
        if has_wulfen_keyword and has_infantry_keyword:
            return True
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        if "wulfen" not in name:
            return False
        if "dreadnought" in name:
            return False
        if has_infantry_keyword:
            return True
        # Fallback for unit records where INFANTRY keyword may not be hydrated.
        return True

    def _wolf_touched_is_bearer(self) -> bool:
        if not self.has_wolf_touched():
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        if sm_mgr is None:
            return False
        try:
            if not sm_mgr.is_saga_of_the_beastslayer():
                return False
        except Exception:
            return False
        return True

    def _wolf_touched_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._wolf_touched_is_bearer():
            return False
        return self._wolf_touched_bodyguard_allowed(bodyguard)

    def _grimnars_mark_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        configured_names: list[str] = []
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict):
                configured_names = [
                    self._normalize_attached_unit_name(v)
                    for v in list(sr.get("enhancement_grimnars_mark_attach_unit_names", ()) or ())
                    if str(v or "").strip()
                ]
        except Exception:
            configured_names = []
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        if name in set(configured_names):
            return True
        if "wolf guard terminator" in name:
            return True
        try:
            if bool(bodyguard.has_any_keyword("WOLF GUARD TERMINATORS")):
                return True
        except Exception:
            pass
        return False

    def _grimnars_mark_is_bearer(self) -> bool:
        if not self.has_grimnars_mark():
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        if sm_mgr is None:
            return False
        try:
            if not sm_mgr.is_saga_of_the_great_wolf():
                return False
        except Exception:
            return False
        try:
            has_terminator_keyword = bool(self.has_any_keyword("TERMINATOR"))
        except Exception:
            has_terminator_keyword = False
        if not has_terminator_keyword:
            return False
        name_norm = ""
        try:
            name_norm = self._normalize_attached_unit_name(getattr(self, "name", ""))
        except Exception:
            name_norm = ""
        try:
            has_captain_keyword = bool(self.has_any_keyword("CAPTAIN"))
        except Exception:
            has_captain_keyword = False
        if not has_captain_keyword and "captain" not in name_norm:
            return False
        return True

    def _grimnars_mark_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._grimnars_mark_is_bearer():
            return False
        return self._grimnars_mark_bodyguard_allowed(bodyguard)

    def _catechism_of_divine_penitence_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        configured_names: list[str] = []
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict):
                configured_names = [
                    self._normalize_attached_unit_name(v)
                    for v in list(sr.get("enhancement_catechism_of_divine_penitence_attach_unit_names", ()) or ())
                    if str(v or "").strip()
                ]
        except Exception:
            configured_names = []
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        if name in set(configured_names):
            return True
        if "repentia squad" in name:
            return True
        try:
            if bool(bodyguard.has_any_keyword("REPENTIA")):
                return True
        except Exception:
            pass
        return False

    def _catechism_of_divine_penitence_is_bearer(self) -> bool:
        if not self.has_catechism_of_divine_penitence():
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        as_mgr = getattr(army, "adepta_sororitas_detachments", None) if army is not None else None
        if as_mgr is None:
            return False
        try:
            if not as_mgr.is_penitent_host():
                return False
        except Exception:
            return False

        allowed_keywords = ("CANONESS", "PALATINE", "MINISTORUM PRIEST")
        for keyword in allowed_keywords:
            try:
                if bool(self.has_any_keyword(keyword)):
                    return True
            except Exception:
                continue
        try:
            name = self._normalize_attached_unit_name(getattr(self, "name", ""))
        except Exception:
            name = ""
        return bool(
            "canoness" in name
            or "palatine" in name
            or "ministorum priest" in name
        )

    def _catechism_of_divine_penitence_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._catechism_of_divine_penitence_is_bearer():
            return False
        return self._catechism_of_divine_penitence_bodyguard_allowed(bodyguard)

    def _enhancement_bearer_model_is_alive(self, *, flag_key: str) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get(flag_key)):
            return False
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
        if bearer_id:
            for model in list(getattr(self, "models", []) or []):
                model_id = str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "")
                if model_id != bearer_id:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                return bool(alive_attr() if callable(alive_attr) else alive_attr)
            return False
        bearer = self._get_enhancement_bearer_model()
        if bearer is None:
            return False
        alive_attr = getattr(bearer, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    def _taktikal_enhancement_attach_override_names(
        self,
        *,
        flag_key: str,
        attach_names_key: str,
        defaults: tuple[str, ...],
    ) -> list[str]:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
            return []
        configured = [
            self._normalize_attached_unit_name(v)
            for v in list(sr.get(attach_names_key, defaults) or [])
            if str(v or "").strip()
        ]
        return [name for name in configured if name]

    def _bodyguard_matches_attach_override_names(self, bodyguard, names: list[str], *, keyword: str) -> bool:
        if bodyguard is None:
            return False
        bodyguard_name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        if bodyguard_name in set(names):
            return True
        has_any_keyword = getattr(bodyguard, "has_any_keyword", None)
        if callable(has_any_keyword):
            try:
                if bool(has_any_keyword(keyword)):
                    return True
            except Exception:
                return False
        return False

    def _skwad_leader_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        if not self._enhancement_bearer_model_is_alive(flag_key="enhancement_skwad_leader"):
            return False
        names = self._taktikal_enhancement_attach_override_names(
            flag_key="enhancement_skwad_leader",
            attach_names_key="enhancement_skwad_leader_attach_unit_names",
            defaults=("Kommandos",),
        )
        if not names:
            return False
        return self._bodyguard_matches_attach_override_names(bodyguard, names, keyword="KOMMANDOS")

    def _mek_kaptin_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        if not self._enhancement_bearer_model_is_alive(flag_key="enhancement_mek_kaptin"):
            return False
        names = self._taktikal_enhancement_attach_override_names(
            flag_key="enhancement_mek_kaptin",
            attach_names_key="enhancement_mek_kaptin_attach_unit_names",
            defaults=("Flash Gitz",),
        )
        if not names:
            return False
        return self._bodyguard_matches_attach_override_names(bodyguard, names, keyword="FLASH GITZ")

    def _skwad_leader_is_leading_kommandos(self) -> bool:
        if not bool(getattr(self, "is_attached_leader", False)):
            return False
        if not self._enhancement_bearer_model_is_alive(flag_key="enhancement_skwad_leader"):
            return False
        bodyguard = getattr(self, "attached_to", None)
        names = self._taktikal_enhancement_attach_override_names(
            flag_key="enhancement_skwad_leader",
            attach_names_key="enhancement_skwad_leader_attach_unit_names",
            defaults=("Kommandos",),
        )
        if not names:
            return False
        return self._bodyguard_matches_attach_override_names(bodyguard, names, keyword="KOMMANDOS")

    def _disciple_of_khorne_active_leaders(self) -> list["Unit"]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        leaders = list(getattr(root, "attached_leaders", []) or [])
        active: list["Unit"] = []
        for leader in leaders:
            try:
                if leader._disciple_of_khorne_active(bodyguard=root):
                    active.append(leader)
            except Exception:
                continue
        return active

    def _unit_on_battlefield_for_icon_of_war(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if not bool(getattr(unit, "deployed", True)):
                return False
            if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
                return False
        except Exception:
            return False
        try:
            if bool(getattr(unit, "embarked_in", None)) or bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            pass
        return True

    def _models_within_icon_of_war_range(self, source_unit, target_unit, *, radius: float) -> bool:
        try:
            from ...utility.aura_utils import distance_between_models_bases_3d
        except Exception:
            return False
        try:
            src_models = list(getattr(source_unit, "models", []) or [])
        except Exception:
            src_models = []
        try:
            tgt_models = list(target_unit.get_attached_unit_models() or [])
        except Exception:
            tgt_models = list(getattr(target_unit, "models", []) or [])
        if not src_models or not tgt_models:
            return False
        for sm in src_models:
            try:
                if not getattr(sm, "is_alive", True):
                    continue
            except Exception:
                continue
            for tm in tgt_models:
                try:
                    if not getattr(tm, "is_alive", True):
                        continue
                except Exception:
                    continue
                try:
                    if distance_between_models_bases_3d(sm, tm) <= float(radius) + 1e-6:
                        return True
                except Exception:
                    continue
        return False

    def _unit_within_icon_of_war_range(self, *, radius: float = 6.0) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if not self._unit_on_battlefield_for_icon_of_war(root):
            return False
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return False
        try:
            units = list(getattr(army, "units", []) or [])
        except Exception:
            units = []
        for source in units:
            try:
                if not source.has_icon_of_war():
                    continue
            except Exception:
                continue
            if not self._unit_on_battlefield_for_icon_of_war(source):
                continue
            if self._models_within_icon_of_war_range(source, root, radius=radius):
                return True
        return False

    def _unit_within_carmine_reliquary_range(self, *, radius: float = 6.0) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if not self._unit_on_battlefield_for_icon_of_war(root):
            return False
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return False
        try:
            units = list(getattr(army, "units", []) or [])
        except Exception:
            units = []
        for source in units:
            try:
                sr = getattr(source, "special_rules", None)
                if not (isinstance(sr, dict) and sr.get("enhancement_carmine_reliquary")):
                    continue
            except Exception:
                continue
            if not self._unit_on_battlefield_for_icon_of_war(source):
                continue
            if self._models_within_icon_of_war_range(source, root, radius=radius):
                return True
        return False

    def _icon_of_war_battle_shock_reroll_available(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if mgr is None:
            return False
        try:
            if not mgr.is_khorne_daemonkin():
                return False
        except Exception:
            return False
        try:
            if not mgr.is_blood_tithe_active("MIGHT_OF_KHORNE"):
                return False
        except Exception:
            return False
        try:
            if not mgr.unit_is_blood_legions(root):
                return False
        except Exception:
            return False
        return bool(root._unit_within_icon_of_war_range())

    def has_command_phase_sticky_objective(self) -> bool:
        """
        True if this unit has the datasheet ability that makes objectives sticky at end of your Command phase.
        """
        cache_key = "command_phase_sticky_objective"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])

        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("sticky_objectives"):
                found = True
            else:
                found = self._scan_command_phase_sticky_objective()
                if isinstance(sr, dict):
                    if found:
                        sr["sticky_objectives"] = True
                    elif "sticky_objectives" in sr:
                        del sr["sticky_objectives"]
        except Exception:
            found = self._scan_command_phase_sticky_objective()

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def get_command_phase_bodyguard_return_ability(self):
        """
        Return ability info dict for command-phase bodyguard model returns, or None if not available.
        """
        cache_key = "command_phase_bodyguard_return_ability"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        ability = None
        try:
            if not bool(getattr(self, "is_attached_leader", False)):
                ability = None
            else:
                ability = self._scan_command_phase_bodyguard_return_ability()
                sr = getattr(self, "special_rules", None)
                if ability and isinstance(sr, dict) and bool(sr.get("enhancement_needle_of_nurgle", False)):
                    bearer_id = str(
                        sr.get("enhancement_needle_of_nurgle_bearer_model_id", "")
                        or sr.get("enhancement_bearer_model_id", "")
                        or ""
                    ).strip()
                    bearer_alive = False
                    if bearer_id:
                        for model in list(getattr(self, "models", []) or []):
                            model_entity_id = str(get_entity_id(model) or "").strip()
                            model_local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                            if bearer_id != model_entity_id and bearer_id != model_local_id:
                                continue
                            alive_attr = getattr(model, "is_alive", True)
                            bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                            break
                    else:
                        get_bearer = getattr(self, "_get_enhancement_bearer_model", None)
                        bearer = get_bearer() if callable(get_bearer) else None
                        if bearer is not None:
                            alive_attr = getattr(bearer, "is_alive", True)
                            bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    requires_leading = bool(sr.get("enhancement_needle_of_nurgle_requires_bearer_leading", True))
                    if bearer_alive and (not requires_leading or bool(getattr(self, "is_attached_leader", False))):
                        amount_roll = str(
                            sr.get("enhancement_needle_of_nurgle_command_phase_return_amount_roll", "D3") or "D3"
                        ).strip().upper()
                        try:
                            max_return = int(sr.get("enhancement_needle_of_nurgle_command_phase_return_max", 3) or 3)
                        except Exception:
                            max_return = 3
                        ability_key = str(
                            sr.get("enhancement_needle_of_nurgle_ability_key", "needle_of_nurgle")
                            or "needle_of_nurgle"
                        ).strip().lower()
                        merged = dict(ability or {})
                        merged["name"] = str(
                            sr.get("enhancement_needle_of_nurgle_source", "Needle of Nurgle") or "Needle of Nurgle"
                        ).strip() or "Needle of Nurgle"
                        merged["ability_key"] = ability_key if ability_key else "needle_of_nurgle"
                        merged["amount_roll"] = amount_roll if amount_roll else "D3"
                        merged["amount"] = int(max(1, max_return))
                        merged["allow_skip"] = bool(merged.get("allow_skip", True))
                        ability = merged
                if not ability:
                    if isinstance(sr, dict) and bool(sr.get("enhancement_steel_font", False)):
                        bearer_id = str(
                            sr.get("enhancement_bearer_model_id", "")
                            or sr.get("enhancement_steel_font_bearer_model_id", "")
                            or ""
                        ).strip()
                        bearer_alive = False
                        if bearer_id:
                            for model in list(getattr(self, "models", []) or []):
                                model_entity_id = str(get_entity_id(model) or "").strip()
                                model_local_id = str(
                                    getattr(model, "id", getattr(model, "_id", "")) or ""
                                ).strip()
                                if bearer_id != model_entity_id and bearer_id != model_local_id:
                                    continue
                                alive_attr = getattr(model, "is_alive", True)
                                bearer_alive = bool(
                                    alive_attr() if callable(alive_attr) else alive_attr
                                )
                                break
                        else:
                            get_bearer = getattr(self, "_get_enhancement_bearer_model", None)
                            bearer = get_bearer() if callable(get_bearer) else None
                            if bearer is not None:
                                alive_attr = getattr(bearer, "is_alive", True)
                                bearer_alive = bool(
                                    alive_attr() if callable(alive_attr) else alive_attr
                                )
                        if bearer_alive:
                            try:
                                amount = int(
                                    sr.get("enhancement_steel_font_command_phase_return_amount", 1)
                                    or 1
                                )
                            except Exception:
                                amount = 1
                            ability_key = str(
                                sr.get("enhancement_steel_font_ability_key", "steel_font")
                                or "steel_font"
                            ).strip().lower()
                            ability = {
                                "name": str(
                                    sr.get("enhancement_steel_font_source", "Steel Font")
                                    or "Steel Font"
                                ).strip()
                                or "Steel Font",
                                "description": "",
                                "ability_key": ability_key if ability_key else "steel_font",
                                "amount": int(max(1, amount)),
                                "allow_skip": True,
                            }
                    if not ability and isinstance(sr, dict) and bool(sr.get("enhancement_amulet_of_tainted_vigour", False)):
                        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
                        bearer_alive = False
                        if bearer_id:
                            for model in list(getattr(self, "models", []) or []):
                                model_entity_id = str(get_entity_id(model) or "").strip()
                                model_local_id = str(
                                    getattr(model, "id", getattr(model, "_id", "")) or ""
                                ).strip()
                                if bearer_id != model_entity_id and bearer_id != model_local_id:
                                    continue
                                alive_attr = getattr(model, "is_alive", True)
                                bearer_alive = bool(
                                    alive_attr() if callable(alive_attr) else alive_attr
                                )
                                break
                        else:
                            get_bearer = getattr(self, "_get_enhancement_bearer_model", None)
                            bearer = get_bearer() if callable(get_bearer) else None
                            if bearer is not None:
                                alive_attr = getattr(bearer, "is_alive", True)
                                bearer_alive = bool(
                                    alive_attr() if callable(alive_attr) else alive_attr
                                )
                        if bearer_alive:
                            ability_key = str(
                                sr.get("enhancement_amulet_of_tainted_vigour_ability_key", "amulet_of_tainted_vigour")
                                or "amulet_of_tainted_vigour"
                            ).strip().lower()
                            amount_roll = str(
                                sr.get("enhancement_amulet_of_tainted_vigour_return_roll", "D3")
                                or "D3"
                            ).strip().upper()
                            required_keyword = str(
                                sr.get("enhancement_amulet_of_tainted_vigour_required_model_keyword", "DAMNED")
                                or "DAMNED"
                            ).strip().upper()
                            ability = {
                                "name": str(
                                    sr.get("enhancement_amulet_of_tainted_vigour_source", "Amulet of Tainted Vigour")
                                    or "Amulet of Tainted Vigour"
                                ).strip()
                                or "Amulet of Tainted Vigour",
                                "description": "",
                                "ability_key": ability_key if ability_key else "amulet_of_tainted_vigour",
                                "amount": 3,
                                "amount_roll": amount_roll if amount_roll else "D3",
                                "exclude_character": bool(
                                    sr.get("enhancement_amulet_of_tainted_vigour_exclude_character", True)
                                ),
                                "required_keyword": required_keyword if required_keyword else "DAMNED",
                                "allow_skip": bool(
                                    sr.get("enhancement_amulet_of_tainted_vigour_allow_skip", True)
                                ),
                            }
        except Exception:
            ability = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = ability
        return ability

    def get_command_phase_unit_return_ability(self):
        """
        Return ability info dict for command-phase destroyed-model returns to this unit, or None.
        """
        cache_key = "command_phase_unit_return_ability"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        ability = None
        try:
            ability = self._scan_command_phase_unit_return_ability()
        except Exception:
            ability = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = ability
        return ability

    def get_charge_phase_bodyguard_loss_ability(self):
        """
        Return ability info dict for end-of-Charge-phase Leadership test bodyguard losses, or None.
        """
        cache_key = "charge_phase_bodyguard_loss_ability"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        ability = None
        try:
            if not bool(getattr(self, "is_attached_leader", False)):
                ability = None
            else:
                ability = self._scan_charge_phase_bodyguard_loss_ability()
        except Exception:
            ability = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = ability
        return ability

    def get_end_of_opponent_turn_strategic_reserves_ability(self):
        """
        Return ability info dict for end-of-opponent-turn Strategic Reserves removal, or None if not available.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "opponent_turn_strategic_reserves_ability"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        ability = None
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("enhancement_warp_fuelled_thrusters")):
            bearer_alive = False
            bearer_id = str(
                sr.get("enhancement_warp_fuelled_thrusters_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            if bearer_id:
                for model in list(getattr(root, "models", []) or []):
                    if str(get_entity_id(model) or "") != bearer_id:
                        continue
                    alive_attr = getattr(model, "is_alive", True)
                    bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    break
            else:
                get_bearer = getattr(root, "_get_enhancement_bearer_model", None)
                bearer_model = get_bearer() if callable(get_bearer) else None
                if bearer_model is not None:
                    alive_attr = getattr(bearer_model, "is_alive", True)
                    bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if bearer_alive or not bool(sr.get("enhancement_warp_fuelled_thrusters_requires_bearer_alive", True)):
                ability_name = (
                    str(sr.get("enhancement_warp_fuelled_thrusters_source", "") or "Warp-fuelled Thrusters").strip()
                    or "Warp-fuelled Thrusters"
                )
                ability_key = (
                    str(sr.get("enhancement_warp_fuelled_thrusters_ability_key", "") or "warp_fuelled_thrusters")
                    .strip()
                    .lower()
                )
                if not ability_key:
                    ability_key = "warp_fuelled_thrusters"
                ability = {
                    "name": ability_name,
                    "description": "",
                    "once_per_battle": bool(sr.get("enhancement_warp_fuelled_thrusters_once_per_battle", False)),
                    "ability_key": ability_key,
                    "trigger_phase": (
                        str(sr.get("enhancement_warp_fuelled_thrusters_trigger_phase", "") or "OPPONENT_TURN_END")
                        .strip()
                        .upper()
                    ),
                    "min_enemy_distance_horiz": 0,
                    "min_battlefield_edge_distance_horiz": 0,
                }

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not ability:
            for member in members:
                try:
                    ability = member._scan_end_of_opponent_turn_strategic_reserves_ability()
                except Exception:
                    ability = None
                if ability:
                    break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = ability
        return ability

    def get_end_of_fight_phase_destroyed_strategic_reserves_ability(self):
        """
        Return ability info dict for end-of-fight-phase Strategic Reserves removal after destroying enemy units.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "fight_phase_destroyed_strategic_reserves_ability"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        ability = None
        try:
            has_fade_to_darkness = bool(
                root._attached_unit_has_active_enhancement(
                    "enhancement_fade_to_darkness",
                    enhancement_id="000009980004",
                    enhancement_name="fade to darkness",
                )
            )
        except Exception:
            has_fade_to_darkness = False
        if has_fade_to_darkness:
            source_name = "Fade to Darkness"
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if not bool(sr.get("enhancement_fade_to_darkness")):
                    continue
                raw = str(sr.get("enhancement_fade_to_darkness_source", "") or "").strip()
                if raw:
                    source_name = raw
                break
            ability = {
                "name": source_name,
                "description": "",
                "ability_key": "fight_phase_destroyed_strategic_reserves",
            }

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not ability:
            for member in members:
                try:
                    ability = member._scan_end_of_fight_phase_destroyed_strategic_reserves_ability()
                except Exception:
                    ability = None
                if ability:
                    break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = ability
        return ability

    def _transport_has_embarked_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip()
        if not kw:
            return False
        try:
            if not bool(getattr(self, "is_transport", False)):
                return False
        except Exception:
            return False
        passengers = list(getattr(self, "transport_passengers", []) or [])
        if not passengers:
            return False
        for passenger in passengers:
            if passenger is None:
                continue
            try:
                root = passenger.get_attached_unit_root()
            except Exception:
                root = passenger
            if root is None:
                continue
            try:
                if bool(root.has_any_keyword(kw)):
                    return True
            except Exception:
                continue
        return False

    def _transport_embarked_models_with_keyword_count(self, keyword: str) -> int:
        kw = str(keyword or "").strip()
        if not kw:
            return 0
        try:
            if not bool(getattr(self, "is_transport", False)):
                return 0
        except Exception:
            return 0
        passengers = list(getattr(self, "transport_passengers", []) or [])
        if not passengers:
            return 0
        total = 0
        for passenger in passengers:
            if passenger is None:
                continue
            try:
                root = passenger.get_attached_unit_root()
            except Exception:
                root = passenger
            if root is None:
                continue
            try:
                if not bool(root.has_any_keyword(kw)):
                    continue
            except Exception:
                continue
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            total += sum(1 for m in list(models or []) if getattr(m, "is_alive", False))
        return int(total)

    def has_vanguard_of_dark_city(self) -> bool:
        cache_key = "vanguard_of_dark_city"
        cache = getattr(self, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))
        found = False
        try:
            found, _ = self._find_ability_with_patterns(["vanguard of the dark city"])
        except Exception:
            found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def get_vanguard_of_dark_city_selected_mode(self) -> str:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return ""
        return str(sr.get("vanguard_of_dark_city_selected_mode", "") or "").strip().lower()

    def vanguard_of_dark_city_mode_active(self, mode_key: str) -> bool:
        mode = str(mode_key or "").strip().lower()
        if not mode:
            return False
        if not self.has_vanguard_of_dark_city():
            return False
        return self.get_vanguard_of_dark_city_selected_mode() == mode

    def has_canticles_of_the_omnissiah(self) -> bool:
        cache_key = "canticles_of_the_omnissiah"
        cache = getattr(self, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))
        found = False
        try:
            found, _ = self._find_ability_with_patterns(["canticles of the omnissiah"])
        except Exception:
            found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def get_canticles_of_the_omnissiah_selected_mode(self) -> str:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return ""
        return str(sr.get("canticles_of_the_omnissiah_selected_mode", "") or "").strip().lower()

    def canticles_of_the_omnissiah_mode_active(self, mode_key: str) -> bool:
        mode = str(mode_key or "").strip().lower()
        if not mode:
            return False
        if not self.has_canticles_of_the_omnissiah():
            return False
        return self.get_canticles_of_the_omnissiah_selected_mode() == mode

    def get_temple_relics_source_unit(self):
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return None
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        try:
            from ...rules.space_marines_temple_relics import unit_has_temple_relics_ability
        except Exception:
            return None

        for member in sorted(list(members or []), key=lambda u: str(get_entity_id(u) or "")):
            if member is None or not bool(unit_has_temple_relics_ability(member)):
                continue
            contains_named = getattr(member, "_unit_contains_model_named", None)
            if callable(contains_named) and bool(contains_named("Grimaldus")):
                return member
        return None

    def has_temple_relics(self) -> bool:
        return self.get_temple_relics_source_unit() is not None

    def temple_relics_can_select(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None or self.get_temple_relics_source_unit() is None:
            return False
        contains_named = getattr(root, "_attached_unit_contains_model_named", None)
        return bool(callable(contains_named) and contains_named("Cenobyte Servitor"))

    def get_temple_relics_selected_mode(self) -> str:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return ""
        return str(sr.get("space_marines_temple_relics_selected_mode", "") or "").strip().lower()

    def temple_relics_mode_active(self, mode_key: str) -> bool:
        mode = str(mode_key or "").strip().lower()
        if not mode:
            return False
        return self.get_temple_relics_selected_mode() == mode

    def _unit_has_battle_protocols_ability_local(self) -> bool:
        for ability in list(getattr(self, "possible_abilities", []) or []):
            name = str(getattr(ability, "name", "") or "").replace("\u2019", "'").strip().lower()
            if name == "battle protocols":
                return True
        return False

    def _battle_protocols_unit_is_kastelan_robots(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        try:
            if bool(root.has_any_keyword("KASTELAN ROBOT")) or bool(root.has_any_keyword("KASTELAN ROBOTS")):
                return True
        except Exception:
            pass
        name = str(getattr(root, "name", "") or "").replace("\u2019", "'").strip().lower()
        return "kastelan robots" in name or "kastelan robot" in name

    def has_battle_protocols(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        cache_key = "battle_protocols"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))

        found = False
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in list(members or []):
            if member is None:
                continue
            if bool(member._unit_has_battle_protocols_ability_local()):
                found = True
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = bool(found)
        return bool(found)

    def battle_protocols_source_is_eligible(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        if not bool(root.has_battle_protocols()):
            return False
        if not bool(root._battle_protocols_unit_is_kastelan_robots()):
            return False

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for member in list(members or []):
            if member is None:
                continue
            if not bool(member._unit_has_battle_protocols_ability_local()):
                continue
            if not bool(getattr(member, "is_attached_leader", False)):
                continue
            try:
                if member.get_attached_unit_root() is not root:
                    continue
            except Exception:
                continue
            alive_fn = getattr(member, "is_alive", None)
            if callable(alive_fn) and not bool(alive_fn()):
                continue
            return True
        return False

    def get_battle_protocols_selected_mode(self) -> str:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return ""
        return str(sr.get("battle_protocols_selected_mode", "") or "").strip().lower()

    def battle_protocols_mode_active(self, mode_key: str) -> bool:
        mode = str(mode_key or "").strip().lower()
        if not mode:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        if not bool(root.has_battle_protocols()):
            return False
        return str(root.get_battle_protocols_selected_mode() or "") == mode

    def command_phase_sticky_objective_prerequisites_met(self) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return True
        required_mode = str(sr.get("sticky_objectives_requires_vanguard_mode", "") or "").strip().lower()
        if required_mode and not self.vanguard_of_dark_city_mode_active(required_mode):
            return False
        required_keyword = str(sr.get("sticky_objectives_requires_embarked_keyword", "") or "").strip()
        if required_keyword and not self._transport_has_embarked_keyword(required_keyword):
            return False
        return True

    def _command_phase_sticky_objective_rule_is_active(self, root, member, rule: dict[str, object]) -> bool:
        if not bool(rule.get("requires_bearer_leading", False)):
            return True
        return bool(getattr(member, "is_leader", False)) and getattr(member, "attached_to", None) is root

    def _iter_command_phase_sticky_objective_rules(self) -> list[tuple["Unit", dict[str, object]]]:
        root = self.get_attached_unit_root()
        members = sorted(
            list(root.get_attached_unit_members() or []),
            key=lambda unit: str(get_entity_id(unit) or ""),
        )
        entries: list[tuple["Unit", dict[str, object]]] = []
        seen: set[tuple[str, str, str, str, bool, bool]] = set()

        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}

            for raw_entry in list(sr.get("enhancement_sticky_objective_rules", []) or []):
                if not isinstance(raw_entry, dict):
                    continue
                entry = {
                    "source_scope": str(raw_entry.get("source_scope", "unit") or "unit").strip().lower(),
                    "source": str(raw_entry.get("source", "unit_sticky_objective") or "unit_sticky_objective").strip()
                    or "unit_sticky_objective",
                    "allow_embarked_transport": bool(raw_entry.get("allow_embarked_transport", False)),
                    "requires_bearer_leading": bool(raw_entry.get("requires_bearer_leading", False)),
                    "source_model_id": str(raw_entry.get("source_model_id", "") or "").strip(),
                }
                if entry["source_scope"] not in ("unit", "bearer"):
                    entry["source_scope"] = "unit"
                if not self._command_phase_sticky_objective_rule_is_active(root, member, entry):
                    continue
                dedupe_key = (
                    str(get_entity_id(member) or ""),
                    str(entry["source_scope"]),
                    str(entry["source_model_id"]),
                    str(entry["source"]).lower(),
                    bool(entry["allow_embarked_transport"]),
                    bool(entry["requires_bearer_leading"]),
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                entries.append((member, entry))

            scan = member._command_phase_sticky_objective_scan_result()
            if not bool(scan.get("found", False)):
                continue
            entry = {
                "source_scope": "unit",
                "source": "unit_sticky_objective",
                "allow_embarked_transport": bool(scan.get("allow_embarked_transport", False)),
                "requires_bearer_leading": bool(scan.get("requires_leading_unit", False)),
                "source_model_id": "",
            }
            if not self._command_phase_sticky_objective_rule_is_active(root, member, entry):
                continue
            dedupe_key = (
                str(get_entity_id(member) or ""),
                "unit",
                "",
                "unit_sticky_objective",
                bool(entry["allow_embarked_transport"]),
                bool(entry["requires_bearer_leading"]),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            entries.append((member, entry))

        return entries

    def _command_phase_sticky_objective_rule_in_range(self, objective_point, *, member, rule: dict[str, object]) -> bool:
        root = self.get_attached_unit_root()
        if str(rule.get("source_scope", "unit") or "unit").strip().lower() == "bearer":
            source_model_id = str(rule.get("source_model_id", "") or "").strip()
            if not source_model_id:
                return False
            source_model = root.get_attached_unit_model_by_id(source_model_id)
            if source_model is None:
                return False
            return bool(root.is_model_within_objective_range(source_model, objective_point))

        if root.is_within_objective_range(objective_point):
            return True
        if not bool(rule.get("allow_embarked_transport", False)):
            return False
        transport = getattr(root, "embarked_in", None)
        return bool(transport is not None and transport.is_within_objective_range(objective_point))

    def command_phase_sticky_objective_claim_rule(self, objective_point) -> dict[str, object] | None:
        root = self.get_attached_unit_root()
        if root is not self:
            return root.command_phase_sticky_objective_claim_rule(objective_point)
        if objective_point is None:
            return None
        for member, rule in root._iter_command_phase_sticky_objective_rules():
            if not member.command_phase_sticky_objective_prerequisites_met():
                continue
            if root._command_phase_sticky_objective_rule_in_range(objective_point, member=member, rule=rule):
                return dict(rule)
        return None

    def visions_of_butchery_attacks_bonus_for_weapon(self, weapon_name: str) -> int:
        if not self.vanguard_of_dark_city_mode_active("visions_of_butchery"):
            return 0
        weapon_norm = re.sub(r"[^a-z0-9]+", " ", str(weapon_name or "").lower()).strip()
        if not weapon_norm:
            return 0
        if "bladevane" not in weapon_norm and "chainsnare" not in weapon_norm:
            return 0
        return max(0, int(self._transport_embarked_models_with_keyword_count("WRACKS")))

    def archons_will_effects_active(self, *, game=None, game_map=None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        objective_id = str(sr.get("archons_will_objective_id", "") or "").strip()
        if not objective_id:
            return False
        if self.is_battle_shocked():
            return False

        objective = None
        if game_map is None and game is None:
            try:
                army = self.get_parent_army()
            except Exception:
                army = None
            try:
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)

        for obj in list(getattr(game_map, "objectives", []) or []):
            if str(get_entity_id(obj) or "") == objective_id:
                objective = obj
                break
        if objective is None:
            for obj in list(getattr(game, "objectives", []) or []):
                if str(get_entity_id(obj) or "") == objective_id:
                    objective = obj
                    break
        if objective is None:
            return False

        loc = getattr(objective, "location", None)
        if loc is None or bool(getattr(loc, "removed", False)):
            return False
        return bool(self.is_within_objective_range(loc))

    def _selected_model_objective_effects_active(
        self,
        *,
        objective_id_key: str,
        source_model_id_key: str,
        model=None,
        game=None,
        game_map=None,
    ) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        objective_id = str(sr.get(objective_id_key, "") or "").strip()
        if not objective_id:
            return False

        source_model_id = str(sr.get(source_model_id_key, "") or "").strip()
        if model is not None and source_model_id:
            model_id = str(get_entity_id(model) or "").strip()
            if model_id and model_id != source_model_id:
                return False

        try:
            if hasattr(root, "is_alive") and callable(root.is_alive) and not root.is_alive():
                return False
            if not bool(getattr(root, "deployed", True)):
                return False
        except Exception:
            return False
        try:
            if bool(getattr(root, "is_embarked", False)) or root.is_in_reserves():
                return False
        except Exception:
            pass

        objective = None
        if game_map is None and game is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            try:
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        for obj in list(getattr(game_map, "objectives", []) or []):
            if str(get_entity_id(obj) or "") == objective_id:
                objective = obj
                break
        if objective is None:
            for obj in list(getattr(game, "objectives", []) or []):
                if str(get_entity_id(obj) or "") == objective_id:
                    objective = obj
                    break
        if objective is None:
            return False

        loc = getattr(objective, "location", None)
        if loc is None or bool(getattr(loc, "removed", False)):
            return False

        source_model = None
        try:
            models = list(root.get_models_for_collision() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for candidate in list(models or []):
            if candidate is None:
                continue
            try:
                if not bool(getattr(candidate, "is_alive", True)):
                    continue
            except Exception:
                pass
            candidate_id = str(get_entity_id(candidate) or "").strip()
            if source_model_id and candidate_id and candidate_id != source_model_id:
                continue
            source_model = candidate
            break
        if source_model is None and model is not None:
            source_model = model
        if source_model is None:
            return False

        try:
            from shapely.geometry import Point as _ShPoint

            area = _ShPoint(float(getattr(loc, "x", 0.0)), float(getattr(loc, "y", 0.0))).buffer(
                float(getattr(loc, "control_radius", 0.0) or 0.0)
            )
            base = source_model.model_base.get_base_shape()
            if base.intersects(area):
                return True
        except Exception:
            pass

        try:
            sx, sy, _sz, _facing = source_model.get_location()
        except Exception:
            return False
        try:
            dx = float(sx) - float(getattr(loc, "x", 0.0))
            dy = float(sy) - float(getattr(loc, "y", 0.0))
            radius = float(getattr(loc, "control_radius", 0.0) or 0.0)
            base_r = float(getattr(source_model.model_base, "get_radius", lambda: 1.0)())
            return (dx * dx + dy * dy) ** 0.5 <= (radius + base_r)
        except Exception:
            return False

    def singular_purpose_objective_effects_active(self, *, model=None, game=None, game_map=None) -> bool:
        """
        TYRANIDS: Singular Purpose (objective branch).
        Active while the selected source model is within range of the selected objective marker.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        mode = str(sr.get("singular_purpose_mode", "") or "").strip().lower()
        if mode != "objective_marker":
            return False
        return self._selected_model_objective_effects_active(
            objective_id_key="singular_purpose_objective_id",
            source_model_id_key="singular_purpose_source_model_id",
            model=model,
            game=game,
            game_map=game_map,
        )

    def seeker_of_lost_relics_effects_active(self, *, model=None, game=None, game_map=None) -> bool:
        """
        Space Marines: Seeker of Lost Relics.
        Active while the selected source model is within range of its chosen objective marker.
        """
        return self._selected_model_objective_effects_active(
            objective_id_key="seeker_of_lost_relics_objective_id",
            source_model_id_key="seeker_of_lost_relics_source_model_id",
            model=model,
            game=game,
            game_map=game_map,
        )

    def _has_aethersails(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "aethersails_ability"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))
        found = False
        for name, desc in root._iter_ability_entries_for_rules(model=None):
            text = f"{name or ''} {desc or ''}".lower()
            if "aethersails" in text:
                found = True
                break
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = bool(found)
        return bool(found)

    def _aethersails_reroll_active(self) -> bool:
        if not self._has_aethersails():
            return False
        return bool(self._transport_has_embarked_keyword("DRUKHARI"))

    def has_dance_of_death(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "dance_of_death"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))
        found = False
        try:
            for ab, _leader in root._iter_attached_leader_leading_abilities():
                try:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
                except Exception:
                    name = ""
                    desc = ""
                text = f"{name or ''} {desc or ''}".lower()
                if "dance of death" in text:
                    found = True
                    break
        except Exception:
            found = False
        if not found:
            for name, desc in root._iter_ability_entries_for_rules(model=None):
                text = f"{name or ''} {desc or ''}".lower()
                if "dance of death" in text:
                    found = True
                    break
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = bool(found)
        return bool(found)

    def has_bladeguard_stance(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "bladeguard_stance"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))
        found = False
        for name, desc in root._iter_ability_entries_for_rules(model=None):
            text = f"{name or ''} {desc or ''}".lower()
            if "swords of the chapter" in text and "shields of the chapter" in text:
                found = True
                break
            if "bladeguard" in text and "re-roll a saving throw of 1" in text:
                found = True
                break
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = bool(found)
        return bool(found)

    def has_adaptive_instincts(self) -> bool:
        root_fn = getattr(self, "get_attached_unit_root", None)
        root = root_fn() if callable(root_fn) else self
        cache_key = "adaptive_instincts"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))
        found = False
        for name, desc in root._iter_ability_entries_for_rules(model=None):
            text = f"{name or ''} {desc or ''}".lower()
            if "adaptive instincts" in text:
                found = True
                break
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = bool(found)
        return bool(found)

    def _iter_attached_model_specific_ability_entries(self, root, model):
        """Resolve model-specific ability text via each model's owning unit."""
        if model is None:
            return
        model_unit = getattr(model, "parent_unit", None) or root
        iter_fn = getattr(model_unit, "_iter_model_specific_ability_entries", None)
        if callable(iter_fn):
            for name, desc in iter_fn(model):
                yield name, desc
            return
        fallback_fn = getattr(root, "_iter_model_specific_ability_entries", None)
        if callable(fallback_fn):
            for name, desc in fallback_fn(model):
                yield name, desc

    def iter_cruel_amusement_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                if "cruel amusement" not in str(name or text_src).lower():
                    normalized = root._normalize_rules_text(text_src)
                    if not normalized:
                        continue
                    normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                    normalized = normalized.lower()
                    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                    normalized = re.sub(r"\s+", " ", normalized).strip()
                    if not root._CRUEL_AMUSEMENT_RE.fullmatch(normalized):
                        continue
                weapon_name = "shrieker cannon"
                try:
                    normalized = root._normalize_rules_text(text_src)
                    normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                    normalized = re.sub(r"\s+", " ", normalized).strip()
                    m = root._CRUEL_AMUSEMENT_RE.fullmatch(normalized)
                    if m:
                        weapon_name = str(m.group("weapon") or weapon_name).strip() or weapon_name
                except Exception:
                    weapon_name = "shrieker cannon"
                results.append(
                    {
                        "model": model,
                        "weapon_name": weapon_name,
                        "source": str(name or "Cruel Amusement").strip() or "Cruel Amusement",
                    }
                )
                break
        return results

    def iter_master_of_magicks_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                normalized = root._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "master of magicks" not in str(name or text_src).lower():
                    if not root._MASTER_OF_MAGICKS_RE.fullmatch(normalized):
                        continue
                weapon_name = "bolt of change"
                try:
                    m = root._MASTER_OF_MAGICKS_RE.fullmatch(normalized)
                    if m:
                        weapon_name = str(m.group("weapon") or weapon_name).strip() or weapon_name
                except Exception:
                    weapon_name = "bolt of change"
                results.append(
                    {
                        "model": model,
                        "weapon_name": weapon_name,
                        "source": str(name or "Master of Magicks").strip() or "Master of Magicks",
                    }
                )
                break
        return results

    def iter_harbinger_of_death_models(self) -> list[dict]:
        """
        Return models with Harbinger of Death (hellforged weapon keyword choice in Fight phase).
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                normalized = root._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "harbinger of death" not in str(name or text_src).lower():
                    if not root._HARBINGER_OF_DEATH_RE.fullmatch(normalized):
                        continue
                results.append(
                    {
                        "model": model,
                        "weapon_name": "hellforged",
                        "source": str(name or "Harbinger of Death").strip() or "Harbinger of Death",
                    }
                )
                break
        return results

    def get_embodied_prophecy_source(self) -> str:
        """
        Return the source name for Embodied Prophecy on this attached unit root, if present.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "embodied_prophecy_source"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return str(cache.get(cache_key) or "")

        source = ""
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in list(members or []):
            if member is None:
                continue
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                text_src = member._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = root._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                name_norm = str(name or "").strip().lower()
                if "embodied prophecy" not in name_norm:
                    if not root._EMBODIED_PROPHECY_RE.fullmatch(normalized):
                        continue
                source = str(name or "Embodied Prophecy").strip() or "Embodied Prophecy"
                break
            if source:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = source
        return str(source or "")

    def get_extremis_trigger_word_source(self) -> str:
        """
        Return the source name for Extremis Trigger Word on this attached unit root, if present.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "extremis_trigger_word_source"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return str(cache.get(cache_key) or "")

        source = ""
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in list(members or []):
            if member is None:
                continue
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                name_norm = str(name or "").strip().lower()
                text_src = member._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = root._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "extremis trigger word" not in name_norm:
                    if "extremis trigger word" not in normalized:
                        continue
                    if "selected to fight" not in normalized:
                        continue
                    if "arco flails equipped by models in this unit" not in normalized:
                        continue
                    if "attacks characteristic of 6" not in normalized:
                        continue
                    if "hazardous" not in normalized:
                        continue
                source = str(name or "Extremis Trigger Word").strip() or "Extremis Trigger Word"
                break
            if source:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = source
        return str(source or "")

    def apply_extremis_trigger_word_effect(
        self,
        *,
        weapon_name: str = "arco-flails",
        attacks_value: int = 6,
        source: str = "",
        game=None,
        expires_phase: str = "FIGHT_PHASE",
    ) -> bool:
        """
        Apply Extremis Trigger Word to this attached unit:
        - set arco-flails Attacks to a fixed value
        - grant [HAZARDOUS] to those weapons
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        source_name = str(source or "").strip()
        if not source_name:
            source_name = str(root.get_extremis_trigger_word_source() or "").strip()
        if not source_name:
            return False
        try:
            fixed_attacks = int(attacks_value or 0)
        except Exception:
            fixed_attacks = 0
        if fixed_attacks <= 0:
            return False
        target_weapon = str(weapon_name or "").strip() or "arco-flails"
        phase_name = str(expires_phase or "FIGHT_PHASE").strip().upper() or "FIGHT_PHASE"

        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        if not models:
            models = list(getattr(root, "models", []) or [])

        applied = False
        for model in list(models or []):
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if not model_id:
                continue
            if hasattr(model, "set_temporary_weapon_attacks_override"):
                model.set_temporary_weapon_attacks_override(
                    key=f"extremis_trigger_word:{model_id}:attacks",
                    weapon_name=target_weapon,
                    attacks_value=int(fixed_attacks),
                    source=source_name,
                    expires_phase=phase_name,
                )
            if hasattr(model, "set_temporary_weapon_keyword_bonuses"):
                model.set_temporary_weapon_keyword_bonuses(
                    key=f"extremis_trigger_word:{model_id}:keywords",
                    weapon_name=target_weapon,
                    keywords=["HAZARDOUS"],
                    source=source_name,
                    expires_phase=phase_name,
                    attack_type="melee",
                )
            applied = True

        if not applied:
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["extremis_trigger_word_active"] = True
        sr["extremis_trigger_word_source"] = source_name
        sr["extremis_trigger_word_weapon_name"] = target_weapon
        sr["extremis_trigger_word_attacks_value"] = int(fixed_attacks)
        sr["extremis_trigger_word_expires_phase"] = phase_name

        game_obj = game
        if game_obj is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            player = getattr(army, "player", None) if army is not None else None
            game_obj = getattr(player, "game", None) if player is not None else None
        if game_obj is not None:
            try:
                sr["extremis_trigger_word_turn"] = int(getattr(game_obj, "turn", 0) or 0)
            except Exception:
                sr["extremis_trigger_word_turn"] = 0
            try:
                current_player = getattr(game_obj, "get_current_player", lambda: None)()
                owner_id = str(getattr(current_player, "id", "") or "")
            except Exception:
                owner_id = ""
            if owner_id:
                sr["extremis_trigger_word_owner"] = owner_id
        root.special_rules = sr
        return True

    def clear_embodied_prophecy_effect(self) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "embodied_prophecy_lethal_hits_active",
            "embodied_prophecy_sustained_hits_value",
            "embodied_prophecy_expires_phase",
            "embodied_prophecy_turn",
            "embodied_prophecy_turn_owner",
            "embodied_prophecy_source",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def apply_embodied_prophecy_effect(
        self,
        *,
        lethal_hits: bool = False,
        sustained_hits_value: int = 0,
        source: str = "",
        game=None,
        expires_phase: str = "FIGHT_PHASE",
    ) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        source_name = str(source or "").strip()
        if not source_name:
            source_name = str(root.get_embodied_prophecy_source() or "").strip()
        if not source_name:
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        for key in (
            "embodied_prophecy_lethal_hits_active",
            "embodied_prophecy_sustained_hits_value",
            "embodied_prophecy_expires_phase",
            "embodied_prophecy_turn",
            "embodied_prophecy_turn_owner",
            "embodied_prophecy_source",
        ):
            sr.pop(key, None)

        try:
            sustained_value = int(sustained_hits_value or 0)
        except Exception:
            sustained_value = 0
        sustained_value = max(0, int(sustained_value))
        if not bool(lethal_hits) and sustained_value <= 0:
            root.special_rules = sr
            return True

        game_obj = game
        if game_obj is None:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            player = getattr(army, "player", None) if army is not None else None
            game_obj = getattr(player, "game", None) if player is not None else None
        try:
            turn_now = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
        except Exception:
            turn_now = 0

        owner_id = ""
        if game_obj is not None:
            current_player = getattr(game_obj, "get_current_player", lambda: None)()
            owner_id = str(getattr(current_player, "id", "") or "")
        if not owner_id:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            owner_id = str(getattr(getattr(army, "player", None), "id", "") or "")

        sr["embodied_prophecy_lethal_hits_active"] = bool(lethal_hits)
        sr["embodied_prophecy_sustained_hits_value"] = int(sustained_value)
        sr["embodied_prophecy_expires_phase"] = str(expires_phase or "FIGHT_PHASE").strip().upper() or "FIGHT_PHASE"
        sr["embodied_prophecy_turn"] = int(turn_now or 0)
        sr["embodied_prophecy_turn_owner"] = owner_id
        sr["embodied_prophecy_source"] = source_name
        root.special_rules = sr
        return True

    def iter_cry_of_the_wind_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                normalized = root._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not root._CRY_OF_THE_WIND_RE.fullmatch(normalized) and "cry of the wind" not in normalized:
                    continue
                results.append(
                    {
                        "model": model,
                        "source": str(name or "Cry of the Wind").strip() or "Cry of the Wind",
                    }
                )
                break
        return results

    def iter_hysterical_frenzy_models(self) -> list[dict]:
        """
        Return Psyker models with the reactive Hysterical Frenzy (Psychic) ability
        (once per Fight phase, within range of a targeted SLAANESH unit).
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                normalized = root._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                name_low = str(name or text_src).lower()
                if "hysterical frenzy" not in name_low:
                    if not root._HYSTERICAL_FRENZY_RE.fullmatch(normalized):
                        continue
                if "once per fight phase" not in normalized:
                    continue
                range_value = 6
                try:
                    m = root._HYSTERICAL_FRENZY_RE.fullmatch(normalized)
                    if m:
                        range_value = int(m.group("range") or 6)
                    else:
                        m = re.search(r"within (\d+)", normalized)
                        if m:
                            range_value = int(m.group(1) or 6)
                except Exception:
                    range_value = 6
                results.append(
                    {
                        "model": model,
                        "range": int(range_value),
                        "source": str(name or "Hysterical Frenzy").strip() or "Hysterical Frenzy",
                    }
                )
                break
        return results

    def iter_sacrificial_dagger_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                name_low = str(name or text_src).lower()
                normalized = root._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "sacrificial dagger" not in name_low:
                    if not root._SACRIFICIAL_DAGGER_RE.fullmatch(normalized):
                        continue
                results.append(
                    {
                        "model": model,
                        "source": str(name or "Sacrificial Dagger").strip() or "Sacrificial Dagger",
                    }
                )
                break
        return results

    def iter_sacrificial_blessing_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                name_low = str(name or text_src).lower()
                normalized = root._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "sacrificial blessing" not in name_low:
                    if not root._SACRIFICIAL_BLESSING_RE.fullmatch(normalized):
                        continue
                results.append(
                    {
                        "model": model,
                        "source": str(name or "Sacrificial Blessing").strip() or "Sacrificial Blessing",
                    }
                )
                break
        return results

    def iter_twisted_sorceries_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                name_low = str(name or text_src).lower()
                normalized = root._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "twisted sorceries" not in name_low:
                    if not root._TWISTED_SORCERIES_RE.fullmatch(normalized):
                        continue
                results.append(
                    {
                        "model": model,
                        "source": str(name or "Twisted Sorceries").strip() or "Twisted Sorceries",
                    }
                )
                break
        return results

    def iter_gift_of_chaos_models(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        results: list[dict] = []
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in self._iter_attached_model_specific_ability_entries(root, model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                name_low = str(name or text_src).lower()
                normalized = root._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "gift of chaos" not in name_low:
                    if not root._GIFT_OF_CHAOS_RE.fullmatch(normalized):
                        continue
                results.append(
                    {
                        "model": model,
                        "source": str(name or "Gift of Chaos").strip() or "Gift of Chaos",
                    }
                )
                break
        return results

    def _extract_cloudstrider_deep_strike_rule(self, *, name: str = "", description: str = "") -> Optional[dict]:
        text = self._normalize_rules_text(description or name or "")
        if not text:
            return None
        normalized = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if "deep strike" not in normalized:
            return None
        if "not eligible to declare a charge" not in normalized and "not eligible to charge" not in normalized:
            return None
        match = re.search(r"\bmore than\s+(?P<distance>\d+(?:\.\d+)?)\b", normalized)
        if match is None:
            return None
        try:
            min_distance = float(match.group("distance"))
        except (TypeError, ValueError):
            return None
        if min_distance <= 0.0:
            return None
        source = str(name or "Cloudstrider").strip() or "Cloudstrider"
        return {
            "source": source,
            "deep_strike_min_distance": float(min_distance),
        }

    def get_cloudstrider_deep_strike_rule(self) -> Optional[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "cloudstrider_deep_strike_rule"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            cached = cache.get(cache_key)
            return cached if isinstance(cached, dict) else None
        rule = None
        for ab, _leader in root._iter_attached_leader_leading_abilities():
            try:
                name = str(getattr(ab, "name", "") or "")
                desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            rule = root._extract_cloudstrider_deep_strike_rule(name=name, description=desc)
            if rule is not None:
                break
        if rule is None:
            for name, desc in root._iter_ability_entries_for_rules(model=None):
                rule = root._extract_cloudstrider_deep_strike_rule(
                    name=str(name or ""),
                    description=str(desc or name or ""),
                )
                if rule is not None:
                    break
        if rule is None:
            fallback = ""
            for ab, _leader in root._iter_attached_leader_leading_abilities():
                try:
                    name = str(getattr(ab, "name", "") or "")
                except Exception:
                    name = ""
                if name.strip().lower() == "cloudstrider":
                    fallback = name or "Cloudstrider"
                    break
            if not fallback:
                for name, _desc in root._iter_ability_entries_for_rules(model=None):
                    if str(name or "").strip().lower() == "cloudstrider":
                        fallback = str(name or "Cloudstrider").strip() or "Cloudstrider"
                        break
            if fallback:
                rule = {
                    "source": fallback,
                    "deep_strike_min_distance": 6.0,
                }
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule if isinstance(rule, dict) else None

    def get_cloudstrider_deep_strike_source(self) -> str:
        rule = self.get_cloudstrider_deep_strike_rule()
        if not isinstance(rule, dict):
            return ""
        source = str(rule.get("source", "") or "").strip()
        return str(source or "")

    def get_opponent_turn_friendly_unit_destroyed_reposition_ability(self):
        """
        Return ability info dict for opponent-turn reposition after a friendly unit is destroyed.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "opponent_turn_friendly_unit_destroyed_reposition_ability"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        ability = None
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in members:
            try:
                ability = member._scan_opponent_turn_friendly_unit_destroyed_reposition_ability()
            except Exception:
                ability = None
            if ability:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = ability
        return ability

    def get_friendly_destroyed_model_weapon_attacks_override_ability(self):
        """
        Return ability info dict for model-destruction triggered weapon attacks overrides.
        """
        try:
            root = self.get_attached_unit_root()
        except (AttributeError, TypeError, ValueError):
            root = self
        cache_key = "friendly_destroyed_model_weapon_attacks_override_ability"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        ability = None
        try:
            members = list(root.get_attached_unit_members() or [])
        except (AttributeError, TypeError, ValueError):
            members = [root]
        for member in members:
            try:
                ability = member._scan_friendly_destroyed_model_weapon_attacks_override_ability()
            except (AttributeError, TypeError, ValueError):
                ability = None
            if ability:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = ability
        return ability

    def get_transport_reactive_disembark_ability(self):
        """
        Return ability info dict for reactive transport disembark triggers, or None if not available.
        """
        cache_key = "transport_reactive_disembark_ability"
        cache = getattr(self, "_ability_cache", {})
        if cache_key in cache:
            cached = cache.get(cache_key)
            if cached is not None or not bool(getattr(self, "is_transport", False)):
                return cached

        ability = None
        if bool(getattr(self, "is_transport", False)):
            for ab in self._iter_active_abilities():
                parsed = self._parse_transport_reactive_disembark_ability(ab)
                if parsed is not None:
                    ability = parsed
                    break

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = ability
        return ability

    def attached_unit_has_icon_of_khorne(self) -> bool:
        """Attached unit eligibility: true if any attached member has Icon of Khorne."""
        for u in self.get_attached_unit_members():
            try:
                if u.has_icon_of_khorne():
                    return True
            except Exception:
                continue
        return False

    def attached_unit_has_command_phase_sticky_objective(self) -> bool:
        """Attached unit eligibility: true if any attached member has sticky objective ability."""
        return bool(self._iter_command_phase_sticky_objective_rules())

    def attached_unit_has_kill_team(self) -> bool:
        """Attached unit eligibility: true if any attached member has the Kill Team ability."""
        for u in self.get_attached_unit_members():
            try:
                if u.has_kill_team():
                    return True
            except Exception:
                continue
        return False

    def attached_unit_has_martial_katah(self) -> bool:
        """Attached unit eligibility: true if any attached member has Martial Ka'tah."""
        for u in self.get_attached_unit_members():
            try:
                if u.has_martial_katah():
                    return True
            except Exception:
                continue
        return False

    def leading_unit_weapons_have_lethal_hits(self, attack_type: Optional[str] = None) -> bool:
        """
        Leading-only ability: while a leader is attached, weapons in that unit gain [LETHAL HITS].

        attack_type: "melee", "ranged", or None to check any weapon type.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        def _resolve(flags: dict, attack_kind: Optional[str]) -> bool:
            kind = str(attack_kind or "").strip().lower()
            if kind == "melee":
                return bool(flags.get("any")) or bool(flags.get("melee"))
            if kind == "ranged":
                return bool(flags.get("any")) or bool(flags.get("ranged"))
            return bool(flags.get("any")) or bool(flags.get("melee")) or bool(flags.get("ranged"))

        cache_key = "leading_unit_lethal_hits"
        cache = getattr(root, "_ability_cache", {})
        if cache_key in cache:
            cached = cache.get(cache_key)
            if isinstance(cached, dict):
                return _resolve(cached, attack_type)
            return bool(cached)

        flags = {"any": False, "melee": False, "ranged": False}
        lethal_any_re = re.compile(
            r"weapons equipped by models in that unit have the \[?lethal hits\]? ability",
            re.IGNORECASE,
        )
        lethal_melee_re = re.compile(
            r"melee weapons equipped by models in that unit have the \[?lethal hits\]? ability",
            re.IGNORECASE,
        )
        lethal_ranged_re = re.compile(
            r"ranged weapons equipped by models in that unit have the \[?lethal hits\]? ability",
            re.IGNORECASE,
        )
        for ab, _leader in root._iter_attached_leader_leading_abilities():
            try:
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
            except Exception:
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            text = text.replace("\u2019", "'").replace("\u0192?T", "'")
            try:
                rest = self._LEADING_ABILITY_PREFIX_RE.sub("", text, count=1).strip(" ,:;-")
            except Exception:
                rest = text
            if lethal_melee_re.search(rest):
                flags["melee"] = True
            elif lethal_ranged_re.search(rest):
                flags["ranged"] = True
            elif lethal_any_re.search(rest):
                flags["any"] = True
            if flags["any"]:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = flags
        return _resolve(flags, attack_type)

    def leading_unit_melta_range_bonus(self) -> int:
        """
        Leading-only ability: while a leader is attached, Melta weapon range in that unit is increased.
        Returns the summed range bonus (in inches).
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        cache_key = "leading_unit_melta_range_bonus"
        cache = getattr(root, "_ability_cache", {})
        if cache_key in cache:
            try:
                return int(cache.get(cache_key) or 0)
            except Exception:
                return 0

        total_bonus = 0
        melta_range_re = re.compile(
            r"add\s+(?P<val>\d+)\s*\"?\s+to\s+the\s+range\s+characteristic\s+of\s+melta\s+weapons?\s+"
            r"equipped\s+by\s+models\s+in\s+(?:the\s+bearer'?s|that|this)\s+unit",
            re.IGNORECASE,
        )
        for ab, _leader in root._iter_attached_leader_leading_abilities():
            try:
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
            except Exception:
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            text = text.replace("\u2019", "'").replace("\u0192?T", "'")
            try:
                rest = self._LEADING_ABILITY_PREFIX_RE.sub("", text, count=1).strip(" ,:;-")
            except Exception:
                rest = text
            m = melta_range_re.search(rest)
            if not m:
                continue
            try:
                total_bonus += int(m.group("val"))
            except Exception:
                continue

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = int(total_bonus)
        return int(total_bonus)

    def _enhancement_local_passive_entity_id(self, entity) -> str:
        try:
            resolved = get_entity_id(entity)
        except ValueError:
            resolved = getattr(entity, "id", getattr(entity, "_id", ""))
        return str(resolved or "")

    def _enhancement_local_passive_root(self):
        get_root = getattr(self, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else self
        return root if root is not None else self

    def _enhancement_local_passive_members(self) -> list['Unit']:
        root = self._enhancement_local_passive_root()
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        members.sort(key=self._enhancement_local_passive_entity_id)
        return members

    def _enhancement_local_passive_source_model_id(self, source_unit, rule: dict) -> str:
        sr = getattr(source_unit, "special_rules", None)
        fallback_bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip() if isinstance(sr, dict) else ""
        return str(rule.get("source_model_id", "") or fallback_bearer_id or "").strip()

    def _enhancement_local_passive_source_model(self, source_unit, rule: dict):
        source_model_id = self._enhancement_local_passive_source_model_id(source_unit, rule)
        if not source_model_id:
            return None
        for source_model in list(getattr(source_unit, "models", []) or []):
            model_id = self._enhancement_local_passive_entity_id(source_model)
            if model_id == source_model_id:
                return source_model
        return None

    def _enhancement_local_passive_source_model_is_alive(self, source_unit, rule: dict) -> bool:
        source_model = self._enhancement_local_passive_source_model(source_unit, rule)
        if source_model is None:
            return not bool(self._enhancement_local_passive_source_model_id(source_unit, rule))
        alive_attr = getattr(source_model, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    def _enhancement_local_passive_model_matches_source(self, model, source_unit, rule: dict) -> bool:
        if model is None:
            return False
        source_model = self._enhancement_local_passive_source_model(source_unit, rule)
        if source_model is None:
            return False
        return self._enhancement_local_passive_entity_id(model) == self._enhancement_local_passive_entity_id(source_model)

    def _iter_active_attached_enhancement_local_passive_rules(self, storage_key: str) -> list[tuple['Unit', dict]]:
        root = self._enhancement_local_passive_root()
        members = self._enhancement_local_passive_members()
        leader_ids = {
            self._enhancement_local_passive_entity_id(unit)
            for unit in list(getattr(root, "attached_leaders", []) or [])
        }
        entries: list[tuple['Unit', dict]] = []
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            rules = [dict(rule) for rule in list(sr.get(storage_key, []) or []) if isinstance(rule, dict)]
            rules.sort(
                key=lambda rule: (
                    str(rule.get("target_scope", "bearer_unit") or "bearer_unit").strip().lower(),
                    str(rule.get("attack_type", "any") or "any").strip().lower(),
                    str(rule.get("roll", "") or "").strip().lower(),
                    str(rule.get("source_model_id", "") or ""),
                    str(rule.get("source", "") or "").strip().lower(),
                    tuple(
                        str(token or "").strip().upper()
                        for token in list(rule.get("keywords", []) or [])
                        if str(token or "").strip()
                    ),
                    int(rule.get("modifier", 0) or 0),
                )
            )
            member_id = self._enhancement_local_passive_entity_id(member)
            for rule in rules:
                if bool(rule.get("requires_bearer_leading", False)) and member_id not in leader_ids:
                    continue
                if not self._enhancement_local_passive_source_model_is_alive(member, rule):
                    continue
                entries.append((member, rule))
        return entries

    def _enhancement_weapon_keyword_rules(self, model: Optional['Model'] = None) -> list[dict]:
        out: list[dict] = []
        seen: set[tuple] = set()
        for source_unit, rule in self._iter_active_attached_enhancement_local_passive_rules(
            "enhancement_weapon_keyword_rules"
        ):
            target_scope = str(rule.get("target_scope", "bearer_unit") or "bearer_unit").strip().lower()
            if target_scope == "bearer":
                if not self._enhancement_local_passive_model_matches_source(model, source_unit, rule):
                    continue
            elif target_scope != "bearer_unit":
                continue
            attack_type = str(rule.get("attack_type", "any") or "any").strip().lower()
            if attack_type not in ("any", "ranged", "melee"):
                attack_type = "any"
            source = str(rule.get("source", "") or "Enhancement").strip() or "Enhancement"
            source_model_id = str(rule.get("source_model_id", "") or "").strip()
            for keyword in list(rule.get("keywords", []) or []):
                token = str(keyword or "").strip().upper()
                if not token:
                    continue
                key = (target_scope, attack_type, token, source.lower(), source_model_id)
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    {
                        "attack_type": attack_type,
                        "keyword": token,
                        "source": source,
                    }
                )
        return out

    def _get_attack_keyword_bonus_rules(self, model: Optional['Model'] = None) -> list[dict]:
        """Collect objective-target keyword bonuses from ability text."""
        cache_key = f"attack_keyword_bonus_rules:{get_entity_id(model) if model is not None else 'unit'}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        entries: list[tuple[str, str]] = []
        for name, desc in self._iter_ability_entries_for_rules(model=None):
            entries.append((name, desc))

        if model is not None:
            model_unit = getattr(model, "parent_unit", None) or self
            try:
                for ab in getattr(model, "abilities", {}).values():
                    try:
                        if not model_unit._ability_is_active(ab):
                            continue
                    except Exception:
                        pass
                    if isinstance(ab, str):
                        entries.append((ab, ab))
                    else:
                        entries.append((getattr(ab, "name", "") or "", getattr(ab, "description", "") or ""))
            except Exception:
                pass

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            for ab, _leader in root._iter_attached_leader_leading_abilities():
                try:
                    aname = str(getattr(ab, "name", "") or "")
                    adesc = str(getattr(ab, "description", "") or "")
                except Exception:
                    aname = ""
                    adesc = ""
                entries.append((aname, adesc))
        except Exception:
            pass
        if root is not None:
            try:
                for leader in list(getattr(root, "attached_leaders", []) or []):
                    if leader is None:
                        continue
                    for ab in list(getattr(leader, "possible_abilities", []) or []):
                        try:
                            if not leader._ability_is_active(ab):
                                continue
                        except Exception:
                            continue
                        aname = str(getattr(ab, "name", "") or "")
                        adesc = str(getattr(ab, "description", "") or "")
                        normalized = self._normalize_rules_text(adesc or "")
                        if not normalized:
                            continue
                        normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                        if "this model's unit" not in normalized and "this models unit" not in normalized:
                            continue
                        entries.append((aname, adesc))
            except Exception:
                pass

        rules: list[dict] = []
        seen: set[tuple] = set()

        def _parse_target_keywords(value: str) -> tuple[str, ...]:
            cleaned = self._normalize_rules_text(value or "")
            cleaned = cleaned.replace("\u2019", "'").replace("\u0192?T", "'")
            cleaned = cleaned.lower()
            if "afflicted" in cleaned:
                return ("AFFLICTED",)
            cleaned = cleaned.replace("enemy ", "")
            cleaned = cleaned.replace("that is ", "")
            cleaned = cleaned.replace("that are ", "")
            cleaned = re.sub(r"\bunit\b", "", cleaned)
            cleaned = cleaned.replace("&", " and ")
            cleaned = re.sub(r"\s+(and|or)\s+", ",", cleaned, flags=re.IGNORECASE)
            parts = [p.strip(" .") for p in cleaned.split(",") if p.strip(" .")]
            keywords: list[str] = []
            for part in parts:
                if not part:
                    continue
                part = re.sub(r"^(?:an?|the)\s+", "", part, flags=re.IGNORECASE).strip()
                if not part:
                    continue
                norm = self._normalize_keyword_phrase(part) or part.strip().upper()
                if not norm:
                    continue
                up = norm.upper()
                if up not in keywords:
                    keywords.append(up)
            return tuple(keywords)

        def _parse_bonus_keywords(value: str) -> list[str]:
            section = str(value or "").strip()
            if not section:
                return []
            bracketed = [k.strip() for k in re.findall(r"\[([^\]]+)\]", section) if str(k or "").strip()]
            if bracketed:
                return bracketed
            normalized = self._normalize_rules_text(section)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            candidates: list[str] = []
            patterns = (
                r"anti-[a-z0-9 \-]+\s+\d\+",
                r"sustained hits\s+(?:d3|d6|\d+)",
                r"devastating wounds",
                r"ignores cover",
                r"twin linked",
                r"twin-linked",
                r"lethal hits",
                r"precision",
                r"lance",
                r"heavy",
            )
            for pat in patterns:
                for m in re.finditer(pat, normalized, flags=re.IGNORECASE):
                    token = str(m.group(0) or "").strip()
                    if not token:
                        continue
                    token = token.replace("twin linked", "twin-linked")
                    token = re.sub(r"\s+", " ", token).strip().upper()
                    if token and token not in candidates:
                        candidates.append(token)
            return candidates

        def _parse_model_keyword_requirement(condition: str) -> str:
            cond = self._normalize_rules_text(condition or "")
            if not cond:
                return ""
            cond = cond.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            patterns = (
                r"(?:that|the attacking|an attacking|this)\s+model\s+has\s+(?:the\s+)?(?P<keyword>[a-z0-9 \-]+?)\s+keyword",
                r"models?\s+with\s+the\s+(?P<keyword>[a-z0-9 \-]+?)\s+keyword",
            )
            for pat in patterns:
                match = re.search(pat, cond, flags=re.IGNORECASE)
                if not match:
                    continue
                keyword = self._normalize_keyword_phrase(str(match.group("keyword") or ""))
                if keyword:
                    return keyword
            return ""

        def _condition_rule_specs(condition_raw: str) -> list[dict]:
            cond = self._normalize_rules_text(condition_raw or "")
            if not cond:
                return [{}]
            cond = cond.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            parts = [cond]
            if re.search(r"\bor\b", cond):
                parts = [str(p or "").strip() for p in re.split(r"\bor\b", cond) if str(p or "").strip()]
            specs: list[dict] = []
            for part in parts:
                if not part:
                    continue
                spec: dict = {}
                parsed = False
                requires_closest_eligible_target = bool(
                    re.search(r"closest\s+(?:eligible\s+)?(?:enemy\s+)?(?:target|unit)", part)
                )
                if requires_closest_eligible_target:
                    parsed = True
                    spec["requires_closest_eligible_target"] = True
                    closest_clause = re.sub(
                        r"(?:the\s+)?closest\s+(?:eligible\s+)?(?:enemy\s+)?(?:target|unit)",
                        " ",
                        part,
                    )
                    closest_clause = re.sub(r"\b(?:that|is|are|an?|enemy|unit|target)\b", " ", closest_clause)
                    closest_clause = re.sub(r"\s+", " ", closest_clause).strip()
                    closest_require_keywords = _parse_target_keywords(closest_clause)
                    if closest_require_keywords:
                        spec["closest_require_keywords_any"] = closest_require_keywords
                required_model_keyword = _parse_model_keyword_requirement(part)
                if required_model_keyword:
                    parsed = True
                    spec["requires_model_keyword"] = required_model_keyword
                if parsed:
                    specs.append(spec)
            return specs

        def _parse_this_models_unit_target_keyword_rules(source_name: str, text: str) -> list[dict]:
            normalized = str(text or "").replace("\u2019", "'").replace("\u0192?T", "'")
            rules_out: list[dict] = []
            target_keywords: tuple[str, ...] = ()
            attack_type = "any"
            sentences = [s.strip() for s in re.split(r"[.;]\s*", normalized) if s.strip()]
            for sentence in sentences:
                clause = str(sentence or "").strip()
                if not clause:
                    continue
                first_clause = re.search(
                    r"each time a model in this model'?s unit makes (?:a|an)\s+(?:(?P<atype>melee|ranged)\s+)?attack "
                    r"that targets (?P<targets>.+?) unit(?:,\s*|\s+)that attack has (?:the\s+)?(?P<kw>.+?) abilit(?:y|ies)",
                    clause,
                    flags=re.IGNORECASE,
                )
                if first_clause and "any other unit" not in clause.lower():
                    atype = str(first_clause.group("atype") or "").strip().lower()
                    if atype in ("melee", "ranged"):
                        attack_type = atype
                    parsed_targets = _parse_target_keywords(str(first_clause.group("targets") or ""))
                    if not parsed_targets:
                        continue
                    target_keywords = parsed_targets
                    for keyword in _parse_bonus_keywords(str(first_clause.group("kw") or "")):
                        rules_out.append(
                            {
                                "attack_type": attack_type,
                                "keyword": keyword.strip(),
                                "source": source_name,
                                "target_keywords_any": target_keywords,
                            }
                        )
                    continue
                other_clause = re.search(
                    r"each time a model in this model'?s unit makes (?:a|an)\s+(?:(?P<atype>melee|ranged)\s+)?attack "
                    r"that targets any other unit(?:,\s*|\s+)that attack has (?:the\s+)?(?P<kw>.+?) abilit(?:y|ies)",
                    clause,
                    flags=re.IGNORECASE,
                )
                if other_clause is None or not target_keywords:
                    continue
                atype = str(other_clause.group("atype") or "").strip().lower()
                if atype in ("melee", "ranged"):
                    attack_type = atype
                for keyword in _parse_bonus_keywords(str(other_clause.group("kw") or "")):
                    rules_out.append(
                        {
                            "attack_type": attack_type,
                            "keyword": keyword.strip(),
                            "source": source_name,
                            "target_exclude_keywords_any": target_keywords,
                        }
                    )
            return rules_out

        for name, desc in entries:
            text = self._normalize_rules_text(desc or name or "")
            if not text:
                continue
            text = text.replace("\u2019", "'").replace("\u0192?T", "'")
            text = Unit._strip_eligibility_prefix(text)
            for match in self._ATTACK_TARGET_OBJECTIVE_KEYWORD_RE.finditer(text):
                keyword = str(match.group("keyword") or "").strip()
                if not keyword:
                    continue
                atype = str(match.group("atype") or "").strip().lower()
                if atype not in ("melee", "ranged"):
                    atype = "any"
                key = ("objective", atype, keyword.lower())
                if key in seen:
                    continue
                seen.add(key)
                rules.append(
                    {
                        "attack_type": atype,
                        "keyword": keyword,
                        "source": str(name or "Ability"),
                        "requires_objective": True,
                    }
                )
            for match in self._ATTACK_TARGET_OBJECTIVE_KEYWORD_ON_CRIT_WOUND_RE.finditer(text):
                keyword = str(match.group("keyword") or "").strip()
                if not keyword:
                    continue
                atype = str(match.group("atype") or "").strip().lower()
                if atype not in ("melee", "ranged"):
                    atype = "any"
                key = ("objective_crit_wound", atype, keyword.lower())
                if key in seen:
                    continue
                seen.add(key)
                rules.append(
                    {
                        "attack_type": atype,
                        "keyword": keyword,
                        "source": str(name or "Ability"),
                        "requires_objective": True,
                        "requires_critical_wound": True,
                    }
                )
            for match in self._ATTACK_TARGET_KEYWORD_BONUS_RE.finditer(text):
                target_raw = str(match.groupdict().get("target_clause") or match.groupdict().get("target") or "").strip()
                target_low = self._normalize_rules_text(target_raw).replace("\u2019", "'").replace("\u0192?T", "'").lower()
                requires_closest_eligible_target = bool(
                    re.search(r"closest\s+(?:eligible\s+)?(?:enemy\s+)?(?:target|unit)", target_low)
                )
                closest_require_keywords: tuple[str, ...] = ()
                if requires_closest_eligible_target:
                    closest_clause = re.sub(
                        r"(?:the\s+)?closest\s+(?:eligible\s+)?(?:enemy\s+)?(?:target|unit)",
                        " ",
                        target_low,
                    )
                    closest_clause = re.sub(r"\b(?:that|is|are|an?|enemy|unit|target)\b", " ", closest_clause)
                    closest_clause = re.sub(r"\s+", " ", closest_clause).strip()
                    closest_require_keywords = _parse_target_keywords(closest_clause)
                target_keywords = _parse_target_keywords(target_raw)
                if requires_closest_eligible_target:
                    target_keywords = ()
                if (not target_keywords) and ("afflicted" in target_raw.lower()):
                    target_keywords = ("AFFLICTED",)
                if not target_keywords and not requires_closest_eligible_target:
                    continue
                atype = str(match.group("atype") or "").strip().lower()
                if atype not in ("melee", "ranged"):
                    atype = "any"
                kw_section = str(match.group("kw_section") or "")
                bonus_keywords = _parse_bonus_keywords(kw_section)
                if not bonus_keywords:
                    continue
                for bonus_kw in bonus_keywords:
                    key = (
                        "target_kw",
                        atype,
                        bonus_kw.strip().lower(),
                        target_keywords,
                        requires_closest_eligible_target,
                        closest_require_keywords,
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    entry = {
                        "attack_type": atype,
                        "keyword": bonus_kw.strip(),
                        "source": str(name or "Ability"),
                        "target_keywords_any": target_keywords,
                    }
                    if requires_closest_eligible_target:
                        entry["requires_closest_eligible_target"] = True
                        if closest_require_keywords:
                            entry["closest_require_keywords_any"] = closest_require_keywords
                    rules.append(entry)
            for match in self._ATTACK_CONDITIONAL_KEYWORD_BONUS_RE.finditer(text):
                condition_raw = str(match.group("condition") or "").strip()
                condition_specs = _condition_rule_specs(condition_raw)
                if not condition_specs:
                    continue
                atype = str(match.group("atype") or "").strip().lower()
                if atype not in ("melee", "ranged"):
                    atype = "any"
                kw_section = str(match.group("kw_section") or "")
                bonus_keywords = _parse_bonus_keywords(kw_section)
                if not bonus_keywords:
                    continue
                for cond_spec in condition_specs:
                    for bonus_kw in bonus_keywords:
                        key = (
                            "conditional_kw",
                            atype,
                            bonus_kw.strip().lower(),
                            bool(cond_spec.get("requires_closest_eligible_target", False)),
                            tuple(cond_spec.get("closest_require_keywords_any", ()) or ()),
                            str(cond_spec.get("requires_model_keyword", "") or "").strip().lower(),
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        entry = {
                            "attack_type": atype,
                            "keyword": bonus_kw.strip(),
                            "source": str(name or "Ability"),
                            "target_keywords_any": (),
                        }
                        if bool(cond_spec.get("requires_closest_eligible_target", False)):
                            entry["requires_closest_eligible_target"] = True
                            closest_require_keywords = tuple(cond_spec.get("closest_require_keywords_any", ()) or ())
                            if closest_require_keywords:
                                entry["closest_require_keywords_any"] = closest_require_keywords
                        required_model_keyword = str(cond_spec.get("requires_model_keyword", "") or "").strip()
                        if required_model_keyword:
                            entry["requires_model_keyword"] = required_model_keyword
                        rules.append(entry)
            for match in self._ATTACK_ALWAYS_KEYWORD_BONUS_RE.finditer(text):
                suffix = re.sub(r"^[\s,.;:]+", "", str(text[match.end():] or "").lower())
                if suffix.startswith("y "):
                    suffix = suffix[2:]
                if suffix.startswith(("if ", "when ", "while ")):
                    continue
                atype = str(match.group("atype") or "").strip().lower()
                if atype not in ("melee", "ranged"):
                    atype = "any"
                kw_section = str(match.group("kw_section") or "")
                bonus_keywords = _parse_bonus_keywords(kw_section)
                if not bonus_keywords:
                    continue
                for bonus_kw in bonus_keywords:
                    key = ("always_kw", atype, bonus_kw.strip().lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    rules.append(
                        {
                            "attack_type": atype,
                            "keyword": bonus_kw.strip(),
                            "source": str(name or "Ability"),
                        }
                    )
            for match in self._UNIT_CONTAINS_WEAPON_ALWAYS_KEYWORD_RE.finditer(text):
                required_model = str(match.group("model") or "").strip()
                if not required_model:
                    continue
                atype = str(match.group("atype") or "").strip().lower()
                if atype not in ("melee", "ranged"):
                    atype = "any"
                kw_section = str(match.group("kw_section") or "")
                bonus_keywords = _parse_bonus_keywords(kw_section)
                if not bonus_keywords:
                    continue
                for bonus_kw in bonus_keywords:
                    key = ("contains_weapon_kw", atype, bonus_kw.strip().lower(), required_model.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    rules.append(
                        {
                            "attack_type": atype,
                            "keyword": bonus_kw.strip(),
                            "source": str(name or "Ability"),
                            "requires_unit_contains_keyword": required_model,
                        }
                    )
            for entry in _parse_this_models_unit_target_keyword_rules(str(name or "Ability"), text):
                key = (
                    "this_models_unit_target_kw",
                    str(entry.get("attack_type", "any") or "any").strip().lower(),
                    str(entry.get("keyword", "") or "").strip().lower(),
                    tuple(entry.get("target_keywords_any", ()) or ()),
                    tuple(entry.get("target_exclude_keywords_any", ()) or ()),
                    str(entry.get("source", "") or "").strip().lower(),
                )
                if key in seen:
                    continue
                seen.add(key)
                rules.append(entry)

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        leading_weapon_keywords_re = re.compile(
            r"^(?:(?P<atype>melee|ranged)\s+)?weapons equipped by models in that unit have (?P<kw_section>.+?) abilit(?:y|ies)$",
            re.IGNORECASE,
        )
        leading_attack_keywords_re = re.compile(
            r"^each time a model in that unit makes (?:a|an)\s+(?:(?P<atype>melee|ranged)\s+)?attack(?:\s*,\s*|\s+)"
            r"that attack has (?P<kw_section>.+?) abilit(?:y|ies)(?:\s+and\b.*)?$",
            re.IGNORECASE,
        )
        def _split_leading_keyword_clauses(sentence: str) -> list[str]:
            text = str(sentence or "").strip()
            if not text:
                return []
            parts = re.split(
                r"\s+\band\b\s+(?=(?:each time a model in that unit makes|(?:(?:melee|ranged)\s+)?weapons equipped by models in that unit have))",
                text,
                flags=re.IGNORECASE,
            )
            return [str(part or "").strip(" ,") for part in parts if str(part or "").strip(" ,")]
        try:
            for ab, _leader in root._iter_attached_leader_leading_abilities():
                try:
                    source_name = str(getattr(ab, "name", "") or "Leading ability").strip() or "Leading ability"
                    source_desc = str(getattr(ab, "description", "") or source_name)
                except Exception:
                    source_name = "Leading ability"
                    source_desc = source_name
                normalized = self._normalize_rules_text(source_desc or "")
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                try:
                    rest = self._LEADING_ABILITY_PREFIX_RE.sub("", normalized, count=1).strip(" ,:;-")
                except Exception:
                    rest = normalized
                if not rest:
                    continue
                sentences = [s.strip() for s in re.split(r"[.;]\s*", rest) if s.strip()]
                for sentence in sentences:
                    clauses = _split_leading_keyword_clauses(sentence)
                    if not clauses:
                        continue
                    for clause in clauses:
                        m = leading_weapon_keywords_re.fullmatch(clause)
                        if m:
                            atype = str(m.group("atype") or "").strip().lower()
                            if atype not in ("melee", "ranged"):
                                atype = "any"
                            keywords = _parse_bonus_keywords(str(m.group("kw_section") or ""))
                            if not keywords:
                                continue
                            for keyword in keywords:
                                key = ("leading_unit_weapon_kw", atype, keyword.strip().lower(), source_name.lower())
                                if key in seen:
                                    continue
                                seen.add(key)
                                rules.append(
                                    {
                                        "attack_type": atype,
                                        "keyword": keyword.strip(),
                                        "source": source_name,
                                    }
                                )
                            continue
                        m = leading_attack_keywords_re.fullmatch(clause)
                        if not m:
                            continue
                        atype = str(m.group("atype") or "").strip().lower()
                        if atype not in ("melee", "ranged"):
                            atype = "any"
                        keywords = _parse_bonus_keywords(str(m.group("kw_section") or ""))
                        if not keywords:
                            continue
                        for keyword in keywords:
                            key = ("always_kw", atype, keyword.strip().lower())
                            if key in seen:
                                continue
                            seen.add(key)
                            rules.append(
                                {
                                    "attack_type": atype,
                                    "keyword": keyword.strip(),
                                    "source": source_name,
                                }
                            )
        except Exception:
            pass

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            has_architect_of_war = False
            checker = getattr(root, "_attached_unit_has_active_leading_enhancement", None)
            if callable(checker):
                has_architect_of_war = bool(
                    checker(
                        "enhancement_architect_of_war",
                        enhancement_id="000008474005",
                        enhancement_name="architect of war",
                    )
                )
            if has_architect_of_war:
                source_name = "Architect of War"
                leaders = list(getattr(root, "attached_leaders", []) or [])
                for leader in leaders:
                    sr_leader = getattr(leader, "special_rules", None)
                    if not isinstance(sr_leader, dict):
                        continue
                    if not bool(sr_leader.get("enhancement_architect_of_war", False)):
                        continue
                    source_name = (
                        str(sr_leader.get("enhancement_architect_of_war_source", "Architect of War") or "Architect of War").strip()
                        or "Architect of War"
                    )
                    break
                key = ("always_kw", "ranged", "ignores cover")
                if key not in seen:
                    seen.add(key)
                    rules.append(
                        {
                            "attack_type": "ranged",
                            "keyword": "IGNORES COVER",
                            "source": source_name,
                        }
                    )
        except Exception:
            pass

        for entry in self._enhancement_weapon_keyword_rules(model=model):
            attack_type = str(entry.get("attack_type", "any") or "any").strip().lower()
            keyword = str(entry.get("keyword", "") or "").strip()
            source_name = str(entry.get("source", "") or "Enhancement").strip() or "Enhancement"
            key = ("enhancement_unit_weapon_kw", attack_type, keyword.lower(), source_name.lower())
            if key in seen:
                continue
            seen.add(key)
            rules.append(
                {
                    "attack_type": attack_type,
                    "keyword": keyword,
                    "source": source_name,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rules
        return rules

    def _get_attack_half_range_keyword_bonus_rules(self, model: Optional['Model'] = None) -> list[dict]:
        """Collect half-range keyword bonuses from ability text."""
        cache_key = f"attack_half_range_keyword_bonus_rules:{get_entity_id(model) if model is not None else 'unit'}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        entries: list[tuple[str, str]] = []
        for name, desc in self._iter_ability_entries_for_rules(model=None):
            entries.append((name, desc))

        if model is not None:
            model_unit = getattr(model, "parent_unit", None) or self
            try:
                for ab in getattr(model, "abilities", {}).values():
                    try:
                        if not model_unit._ability_is_active(ab):
                            continue
                    except Exception:
                        pass
                    if isinstance(ab, str):
                        entries.append((ab, ab))
                    else:
                        entries.append((getattr(ab, "name", "") or "", getattr(ab, "description", "") or ""))
            except Exception:
                pass

        rules: list[dict] = []
        seen: set[tuple[str, str]] = set()
        def _split_weapon_list(value: str) -> list[str]:
            cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
            if not cleaned:
                return []
            cleaned = cleaned.replace("&", " and ")
            cleaned = re.sub(r"\s+(and|or)\s+", ",", cleaned, flags=re.IGNORECASE)
            parts = [part.strip(" .") for part in cleaned.split(",") if part.strip(" .")]
            out = []
            for part in parts:
                part = re.sub(r"^(the|its)\s+", "", part.strip(), flags=re.IGNORECASE)
                if part:
                    out.append(part)
            return out

        for name, desc in entries:
            text = self._normalize_rules_text(desc or name or "")
            if not text:
                continue
            text = text.replace("\u2019", "'").replace("\u0192?T", "'")
            text = Unit._strip_eligibility_prefix(text)
            for match in self._ATTACK_TARGET_HALF_RANGE_KEYWORD_RE.finditer(text):
                keyword = str(match.group("keyword") or "").strip()
                if not keyword:
                    continue
                atype = str(match.group("atype") or "").strip().lower()
                if atype not in ("melee", "ranged"):
                    atype = "any"
                key = (atype, keyword.lower())
                if key in seen:
                    continue
                seen.add(key)
                rules.append({"attack_type": atype, "keyword": keyword, "source": str(name or "Ability")})
            for match in self._WEAPON_LIST_HALF_RANGE_KEYWORD_RE.finditer(text):
                keyword = str(match.group("keyword") or "").strip()
                if not keyword:
                    continue
                weapons = _split_weapon_list(match.group("weapons") or "")
                if not weapons:
                    continue
                key = ("ranged", keyword.lower(), tuple(sorted(w.lower() for w in weapons)))
                if key in seen:
                    continue
                seen.add(key)
                rules.append({
                    "attack_type": "ranged",
                    "keyword": keyword,
                    "source": str(name or "Ability"),
                    "weapon_names": weapons,
                })
            for match in self._WEAPON_HALF_RANGE_KEYWORD_RE.finditer(text):
                keyword = str(match.group("keyword") or "").strip()
                if not keyword:
                    continue
                atype = str(match.group("atype") or "").strip().lower()
                if atype not in ("melee", "ranged"):
                    atype = "ranged"
                key = (atype, keyword.lower())
                if key in seen:
                    continue
                seen.add(key)
                rules.append({"attack_type": atype, "keyword": keyword, "source": str(name or "Ability")})
            for match in self._WEAPON_HALF_RANGE_KEYWORD_MODEL_RE.finditer(text):
                keyword = str(match.group("keyword") or "").strip()
                if not keyword:
                    continue
                atype = str(match.group("atype") or "").strip().lower()
                if atype not in ("melee", "ranged"):
                    atype = "ranged"
                key = (atype, keyword.lower())
                if key in seen:
                    continue
                seen.add(key)
                rules.append({"attack_type": atype, "keyword": keyword, "source": str(name or "Ability")})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rules
        return rules

    def _get_model_weapon_keyword_bonus_rules(self, model: Optional['Model'] = None) -> list[dict]:
        """Collect always-on weapon keyword grants that apply to a specific model."""
        if model is None:
            return []
        cache_key = f"model_weapon_keyword_bonus_rules:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        entries: list[tuple[str, str]] = []
        try:
            for name, desc in self._iter_model_specific_ability_entries(model):
                entries.append((name, desc))
        except Exception:
            pass

        # Wargear abilities tied to equipped items.
        for ab in list(getattr(self, "possible_abilities", []) or []):
            try:
                atype = str(getattr(ab, "type", "") or "").lower()
                if "wargear" not in atype:
                    continue
                name = getattr(ab, "name", "") or ""
                if not name:
                    continue
                if not self._model_has_wargear_named(model, name):
                    continue
                entries.append((name, getattr(ab, "description", "") or ""))
            except Exception:
                continue

        # Enhancement text applies to the enhancement bearer.
        try:
            enh = getattr(self, "enhancement", None)
            if enh is not None:
                bearer_id = self._get_enhancement_bearer_id()
                model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                if bearer_id and model_id == str(bearer_id):
                    entries.append((getattr(enh, "name", "") or "", getattr(enh, "description", "") or ""))
        except Exception:
            pass

        rules: list[dict] = []
        seen: set[tuple[str, str, str]] = set()

        for name, desc in entries:
            text = self._normalize_rules_text(desc or name or "")
            if not text:
                continue
            text = text.replace("\u2019", "'").replace("\u0192?T", "'")
            text = Unit._strip_eligibility_prefix(text)

            for match in self._BEARER_WEAPON_ALWAYS_KEYWORD_RE.finditer(text):
                try:
                    prefix = str(text[: match.start()] or "").lower()
                    is_stationary_conditional = (
                        ("if this model remains stationary" in prefix)
                        or ("if this model remained stationary" in prefix)
                        or ("if the bearer remains stationary" in prefix)
                        or ("if the bearer remained stationary" in prefix)
                    )
                    if is_stationary_conditional and (
                        ("until the end of the turn" in prefix)
                        or ("until end of the turn" in prefix)
                        or ("until end of turn" in prefix)
                    ):
                        continue
                except Exception:
                    pass
                keyword = str(match.group("keyword") or "").strip()
                if not keyword:
                    continue
                atype = str((match.group("atype") or match.group("atype_alt") or "")).strip().lower()
                if atype not in ("melee", "ranged"):
                    atype = "any"
                source = str(name or "Ability")
                key = (atype, keyword.lower(), source.lower())
                if key in seen:
                    continue
                seen.add(key)
                rules.append({"attack_type": atype, "keyword": keyword, "source": source})

            for match in self._WEAPON_ALWAYS_KEYWORD_MODEL_RE.finditer(text):
                try:
                    prefix = str(text[: match.start()] or "").lower()
                    is_stationary_conditional = (
                        ("if this model remains stationary" in prefix)
                        or ("if this model remained stationary" in prefix)
                        or ("if the bearer remains stationary" in prefix)
                        or ("if the bearer remained stationary" in prefix)
                    )
                    if is_stationary_conditional and (
                        ("until the end of the turn" in prefix)
                        or ("until end of the turn" in prefix)
                        or ("until end of turn" in prefix)
                    ):
                        continue
                except Exception:
                    pass
                keyword = str(match.group("keyword") or "").strip()
                if not keyword:
                    continue
                atype = str(match.group("atype") or "").strip().lower()
                if atype not in ("melee", "ranged"):
                    atype = "any"
                source = str(name or "Ability")
                key = (atype, keyword.lower(), source.lower())
                if key in seen:
                    continue
                seen.add(key)
                rules.append({"attack_type": atype, "keyword": keyword, "source": source})

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            has_architect_of_war = False
            checker = getattr(root, "_attached_unit_has_active_leading_enhancement", None)
            if callable(checker):
                has_architect_of_war = bool(
                    checker(
                        "enhancement_architect_of_war",
                        enhancement_id="000008474005",
                        enhancement_name="architect of war",
                    )
                )
            if has_architect_of_war:
                source_name = "Architect of War"
                leaders = list(getattr(root, "attached_leaders", []) or [])
                for leader in leaders:
                    sr_leader = getattr(leader, "special_rules", None)
                    if not isinstance(sr_leader, dict):
                        continue
                    if not bool(sr_leader.get("enhancement_architect_of_war", False)):
                        continue
                    source_name = (
                        str(sr_leader.get("enhancement_architect_of_war_source", "Architect of War") or "Architect of War").strip()
                        or "Architect of War"
                    )
                    break
                key = ("ranged", "ignores cover", source_name.lower())
                if key not in seen:
                    seen.add(key)
                    rules.append(
                        {
                            "attack_type": "ranged",
                            "keyword": "IGNORES COVER",
                            "source": source_name,
                        }
                    )
        except Exception:
            pass

        try:
            has_eye_of_the_primarch = False
            checker = getattr(root, "_attached_unit_has_active_enhancement", None)
            if callable(checker):
                has_eye_of_the_primarch = bool(
                    checker(
                        "enhancement_eye_of_the_primarch",
                        enhancement_id="000010676002",
                        enhancement_name="eye of the primarch",
                    )
                )
            if has_eye_of_the_primarch:
                is_bearer = False
                bearer_checker = getattr(root, "_attached_unit_model_is_enhancement_bearer", None)
                if callable(bearer_checker):
                    is_bearer = bool(
                        bearer_checker(
                            model,
                            flag_key="enhancement_eye_of_the_primarch",
                            enhancement_id="000010676002",
                            enhancement_name="eye of the primarch",
                            require_leading=False,
                            require_bearer_alive=True,
                        )
                    )

                is_battleline_model = False
                if not is_bearer:
                    has_any = getattr(model, "has_any_keyword", None)
                    if callable(has_any):
                        is_battleline_model = bool(has_any("BATTLELINE"))
                    if not is_battleline_model:
                        model_keywords = [str(k or "").strip().upper() for k in list(getattr(model, "keywords", []) or [])]
                        is_battleline_model = "BATTLELINE" in set(model_keywords)

                if is_bearer or is_battleline_model:
                    source_name = "Eye of the Primarch"
                    configured_keywords = ["PRECISION"]
                    try:
                        members = list(root.get_attached_unit_members() or [])
                    except Exception:
                        members = [root]
                    if not members:
                        members = [root]
                    for member in members:
                        sr_member = getattr(member, "special_rules", None)
                        if not isinstance(sr_member, dict):
                            continue
                        if not bool(sr_member.get("enhancement_eye_of_the_primarch", False)):
                            continue
                        source_name = (
                            str(sr_member.get("enhancement_eye_of_the_primarch_source", "Eye of the Primarch") or "Eye of the Primarch").strip()
                            or "Eye of the Primarch"
                        )
                        raw_keywords = list(sr_member.get("enhancement_eye_of_the_primarch_keywords", []) or [])
                        normalized = []
                        seen_kw = set()
                        for value in raw_keywords:
                            keyword = str(value or "").strip().upper()
                            if not keyword:
                                continue
                            key_kw = keyword.lower()
                            if key_kw in seen_kw:
                                continue
                            seen_kw.add(key_kw)
                            normalized.append(keyword)
                        if normalized:
                            configured_keywords = normalized
                        break

                    for keyword in configured_keywords:
                        key = ("ranged", keyword.strip().lower(), source_name.lower())
                        if key in seen:
                            continue
                        seen.add(key)
                        rules.append(
                            {
                                "attack_type": "ranged",
                                "keyword": keyword.strip(),
                                "source": source_name,
                            }
                        )
        except Exception:
            pass

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rules
        return rules

    def _resolve_attack_keyword_bonuses_from_rules(self, rules: list[dict], *, attack_type: Optional[str]) -> dict:
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"

        bonuses = {
            "ignores_cover": False,
            "lethal_hits": False,
            "assault": False,
            "hazardous": False,
            "blast": False,
            "rapid_fire_bonus": 0,
            "sustained_hits_value": 0,
            "sustained_hits_dice": "",
            "devastating_wounds": False,
            "twin_linked": False,
            "heavy": False,
            "lance": False,
            "precision": False,
            "anti_specs": [],
        }
        sources: list[str] = []

        for rule in rules:
            rtype = str(rule.get("attack_type", "any") or "any").strip().lower()
            if rtype not in ("any", "melee", "ranged"):
                rtype = "any"
            if rtype != "any" and atype != "any" and rtype != atype:
                continue
            raw_kw = str(rule.get("keyword", "") or "").strip()
            if not raw_kw:
                continue
            kw = re.sub(r"\s+", " ", raw_kw).strip().upper()
            source = str(rule.get("source", "") or "Ability")

            if kw == "IGNORES COVER":
                bonuses["ignores_cover"] = True
                sources.append(f"Ignores Cover ({source})")
            elif kw == "ASSAULT":
                bonuses["assault"] = True
                sources.append(f"Assault ({source})")
            elif kw == "HAZARDOUS":
                bonuses["hazardous"] = True
                sources.append(f"Hazardous ({source})")
            elif kw == "BLAST":
                bonuses["blast"] = True
                sources.append(f"Blast ({source})")
            elif kw.startswith("RAPID FIRE"):
                match = re.search(r"RAPID FIRE\s+(\d+)", kw)
                if match:
                    rapid_fire_bonus = int(match.group(1))
                    bonuses["rapid_fire_bonus"] = max(int(bonuses["rapid_fire_bonus"] or 0), rapid_fire_bonus)
                    sources.append(f"Rapid Fire {rapid_fire_bonus} ({source})")
            elif kw == "LETHAL HITS":
                bonuses["lethal_hits"] = True
                sources.append(f"Lethal Hits ({source})")
            elif kw.startswith("SUSTAINED HITS"):
                m = re.search(r"SUSTAINED HITS\s+(\d+)", kw)
                if m:
                    val = int(m.group(1))
                    bonuses["sustained_hits_value"] = max(int(bonuses["sustained_hits_value"] or 0), val)
                    sources.append(f"Sustained Hits {val} ({source})")
                else:
                    md = re.search(r"SUSTAINED HITS\s+(D3|D6)", kw)
                    if md:
                        die = str(md.group(1) or "").strip().upper()
                        if die in ("D3", "D6"):
                            fixed = int(bonuses["sustained_hits_value"] or 0)
                            if fixed <= 0 or (die == "D6" and fixed < 6) or (die == "D3" and fixed < 3):
                                bonuses["sustained_hits_dice"] = die
                            sources.append(f"Sustained Hits {die} ({source})")
            elif kw == "DEVASTATING WOUNDS":
                bonuses["devastating_wounds"] = True
                sources.append(f"Devastating Wounds ({source})")
            elif kw in ("TWIN-LINKED", "TWIN LINKED"):
                bonuses["twin_linked"] = True
                sources.append(f"Twin-linked ({source})")
            elif kw == "HEAVY":
                bonuses["heavy"] = True
                sources.append(f"Heavy ({source})")
            elif kw == "LANCE":
                bonuses["lance"] = True
                sources.append(f"Lance ({source})")
            elif kw == "PRECISION":
                bonuses["precision"] = True
                sources.append(f"Precision ({source})")
            elif kw.startswith("ANTI-"):
                m = re.search(r"ANTI-([A-Z0-9 \-]+)\s+(\d)\+", kw)
                if m:
                    anti_kw = m.group(1).strip().replace("-", " ")
                    anti_val = int(m.group(2))
                    bonuses.setdefault("anti_specs", []).append((anti_kw, anti_val))
                    sources.append(f"Anti-{anti_kw} {anti_val}+ ({source})")

        if sources:
            bonuses["sources"] = sources
        if (
            bonuses["ignores_cover"]
            or bonuses["lethal_hits"]
            or bonuses["assault"]
            or bonuses["hazardous"]
            or bonuses["blast"]
            or int(bonuses["rapid_fire_bonus"] or 0) > 0
            or bonuses["devastating_wounds"]
            or bonuses["twin_linked"]
            or bonuses["heavy"]
            or bonuses["lance"]
            or bonuses["precision"]
            or int(bonuses["sustained_hits_value"] or 0) > 0
            or str(bonuses.get("sustained_hits_dice", "") or "").strip()
            or bool(bonuses.get("anti_specs"))
        ):
            return bonuses
        return {}

    def _target_is_afflicted_for_attack_bonuses(self, target, *, game_map=None) -> bool:
        if target is None:
            return False
        try:
            sr = getattr(target, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("post_shoot_afflicted_active")):
                return True
        except Exception:
            pass
        try:
            from ...rules.nurgles_gift import NurglesGiftManager
        except Exception:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            source_army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        except Exception:
            source_army = None
        try:
            source_player = getattr(source_army, "player", None) if source_army is not None else None
        except Exception:
            source_player = None
        try:
            game = getattr(source_player, "game", None)
        except Exception:
            game = None
        gm = game_map
        if gm is None and game is not None:
            gm = getattr(game, "map", None)
        try:
            return bool(NurglesGiftManager.get_afflicted_plague_for_unit(target, game=game, game_map=gm) is not None)
        except Exception:
            return False

    def get_model_weapon_keyword_bonuses(
        self,
        *,
        attack_type: Optional[str] = None,
        model: Optional['Model'] = None,
        weapon_profile=None,
        weapon_name: str = "",
        target: Optional['Unit'] = None,
    ) -> dict:
        """Return always-on weapon keyword bonuses for a specific model."""
        if model is None:
            return {}
        rules = list(self._get_model_weapon_keyword_bonus_rules(model=model) or [])
        temp_rules: list[dict] = []
        try:
            wname = str(weapon_name or "").strip()
            if not wname and weapon_profile is not None:
                try:
                    wname = str(getattr(getattr(weapon_profile, "parent_wargear", None), "name", "") or "")
                except Exception:
                    wname = ""
                if not wname:
                    try:
                        wname = str(getattr(weapon_profile, "name", "") or "")
                    except Exception:
                        wname = ""
            if wname and hasattr(model, "get_temporary_weapon_keyword_bonuses"):
                temp_rules = list(model.get_temporary_weapon_keyword_bonuses(wname) or [])
        except Exception:
            temp_rules = []
        if temp_rules:
            rules = list(rules or []) + list(temp_rules or [])
        try:
            atype = str(attack_type or "").strip().lower()
            is_melee_attack = atype in ("", "any", "melee")
            if is_melee_attack:
                current_weapon_name = str(weapon_name or "").strip()
                if not current_weapon_name and weapon_profile is not None:
                    try:
                        current_weapon_name = str(getattr(getattr(weapon_profile, "parent_wargear", None), "name", "") or "")
                    except Exception:
                        current_weapon_name = ""
                    if not current_weapon_name:
                        try:
                            current_weapon_name = str(getattr(weapon_profile, "name", "") or "")
                        except Exception:
                            current_weapon_name = ""
                if current_weapon_name and self._weapon_name_matches(["macro-scalpel", "macro scalpel"], current_weapon_name):
                    has_rule = False
                    source = "Devoted to Pain"
                    for name, desc in self._iter_model_specific_ability_entries(model):
                        source_name = str(name or "").strip()
                        text_src = desc or name or ""
                        if not text_src:
                            continue
                        normalized = self._normalize_rules_text(self._strip_eligibility_prefix(text_src))
                        normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                        normalized = normalized.lower()
                        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                        normalized = re.sub(r"\s+", " ", normalized).strip()
                        if source_name.lower() != "devoted to pain" and "equipped with 2 macro scalpels" not in normalized:
                            continue
                        if "gain the twin linked ability" not in normalized and "gain twin linked" not in normalized:
                            continue
                        has_rule = True
                        source = source_name or "Devoted to Pain"
                        break
                    if has_rule:
                        macro_scalpel_count = 0
                        for wargear in list(getattr(model, "wargear", []) or []):
                            name = str(getattr(wargear, "name", "") or "").strip()
                            if name and self._weapon_name_matches(["macro-scalpel", "macro scalpel"], name):
                                macro_scalpel_count += 1
                        if macro_scalpel_count >= 2:
                            rules = list(rules or []) + [
                                {"attack_type": "melee", "keyword": "TWIN-LINKED", "source": source}
                            ]
                if current_weapon_name:
                    melee_wargear = []
                    for wargear in list(getattr(model, "wargear", []) or []):
                        is_melee_fn = getattr(wargear, "is_melee", None)
                        if not callable(is_melee_fn):
                            continue
                        if not bool(is_melee_fn()):
                            continue
                        melee_wargear.append(wargear)
                    if len(melee_wargear) == 2 and any(
                        self._weapon_name_matches([str(getattr(wg, "name", "") or "").strip()], current_weapon_name)
                        for wg in melee_wargear
                    ):
                        has_rule = False
                        source = "Two melee weapons"
                        for name, desc in self._iter_model_specific_ability_entries(model):
                            source_name = str(name or "").strip()
                            text_src = desc or name or ""
                            if not text_src:
                                continue
                            normalized = self._normalize_rules_text(self._strip_eligibility_prefix(text_src))
                            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                            normalized = normalized.lower()
                            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                            normalized = re.sub(r"\s+", " ", normalized).strip()
                            if "equipped with two melee weapons" not in normalized:
                                continue
                            if "those weapon profiles have the twin linked ability" not in normalized:
                                continue
                            has_rule = True
                            source = source_name or "Two melee weapons"
                            break
                        if has_rule:
                            rules = list(rules or []) + [
                                {"attack_type": "melee", "keyword": "TWIN-LINKED", "source": source}
                            ]
        except Exception:
            pass
        try:
            if weapon_profile is not None:
                from ...utility.aura_effects import get_aura_weapon_keyword_bonuses
                aura_rules = get_aura_weapon_keyword_bonuses(
                    self,
                    weapon_profile,
                    target_unit=target,
                    attacker_model=model,
                )
                if aura_rules:
                    rules = list(rules or []) + list(aura_rules or [])
        except Exception:
            pass
        try:
            army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            keyword_fn = getattr(sm_mgr, "black_spear_special_issue_ammunition_attack_keywords", None) if sm_mgr is not None else None
            if callable(keyword_fn):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                keywords, source = keyword_fn(
                    model,
                    weapon_profile=weapon_profile,
                    game=game,
                )
                for keyword in list(keywords or []):
                    rules = list(rules or []) + [
                        {
                            "attack_type": "ranged",
                            "keyword": str(keyword),
                            "source": str(source or "Black Spear Task Force"),
                        }
                    ]
        except Exception:
            pass
        try:
            if target is not None:
                army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
                sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
                keyword_fn = getattr(sm_mgr, "light_of_vengeance_weapon_keyword", None) if sm_mgr is not None else None
                if callable(keyword_fn):
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    keyword = str(keyword_fn(self, target, game=game) or "").strip().upper()
                    if keyword:
                        rules = list(rules or []) + [
                            {
                                "attack_type": "any",
                                "keyword": keyword,
                                "source": "Light of Vengeance",
                            }
                        ]
        except Exception:
            pass
        try:
            army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            keyword_fn = getattr(sm_mgr, "orbital_assault_auto_sense_coordination_weapon_keyword", None) if sm_mgr is not None else None
            if callable(keyword_fn):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                keyword, source = keyword_fn(
                    model,
                    target,
                    weapon_profile=weapon_profile,
                    game=game,
                )
                keyword = str(keyword or "").strip().upper()
                if keyword:
                    rules = list(rules or []) + [
                        {
                            "attack_type": "any",
                            "keyword": keyword,
                            "source": str(source or "AUTO-SENSE COORDINATION").strip() or "AUTO-SENSE COORDINATION",
                        }
                    ]
        except Exception:
            pass
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            rule = None
            get_rule = getattr(root, "get_stationary_ranged_sustained_hits_rule", None)
            if callable(get_rule):
                rule = get_rule(model)
            if isinstance(rule, dict):
                apply_bonus = True
                atype = str(attack_type or "").strip().lower()
                if atype and atype not in ("any", "ranged"):
                    apply_bonus = False
                unit = getattr(model, "parent_unit", None) or root
                if bool(rule.get("requires_remained_stationary")):
                    if not bool(getattr(getattr(unit, "round_state", None), "remained_stationary_this_round", False)):
                        apply_bonus = False
                if apply_bonus and bool(rule.get("requires_owner_turn")):
                    owner_army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
                    owner_player = getattr(owner_army, "player", None) if owner_army is not None else None
                    game = getattr(owner_player, "game", None) if owner_player is not None else None
                    current_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
                    if owner_player is None or current_player is not owner_player:
                        apply_bonus = False
                if apply_bonus and bool(rule.get("requires_active_order")):
                    active_order = ""
                    for candidate in (unit, root):
                        sr = getattr(candidate, "special_rules", None)
                        if not isinstance(sr, dict):
                            continue
                        active_order = str(sr.get("voice_of_command_order_key", "") or "").strip().upper()
                        if active_order:
                            break
                    if not active_order:
                        apply_bonus = False
                if apply_bonus and bool(rule.get("requires_heavy_weapon")):
                    is_heavy_weapon = False
                    try:
                        if weapon_profile is not None and hasattr(weapon_profile, "is_heavy"):
                            is_heavy_weapon = bool(weapon_profile.is_heavy())
                    except Exception:
                        is_heavy_weapon = False
                    if not is_heavy_weapon:
                        apply_bonus = False
                if apply_bonus:
                    source = str(rule.get("source", "") or "Remains Stationary").strip() or "Remains Stationary"
                    sustained_hits_value = int(rule.get("sustained_hits_value", 0) or 0)
                    sustained_hits_dice = str(rule.get("sustained_hits_dice", "") or "").strip().upper()
                    if sustained_hits_value > 0:
                        rules = list(rules or []) + [
                            {"attack_type": "ranged", "keyword": f"SUSTAINED HITS {int(sustained_hits_value)}", "source": source}
                        ]
                    elif sustained_hits_dice in ("D3", "D6"):
                        rules = list(rules or []) + [
                            {"attack_type": "ranged", "keyword": f"SUSTAINED HITS {sustained_hits_dice}", "source": source}
                        ]
        except Exception:
            pass
        try:
            rule = None
            get_rule = getattr(root, "get_stationary_ranged_weapon_keyword_rule", None)
            if callable(get_rule):
                rule = get_rule(model)
            if isinstance(rule, dict):
                apply_bonus = True
                atype = str(attack_type or "").strip().lower()
                if atype and atype not in ("any", "ranged"):
                    apply_bonus = False
                unit = getattr(model, "parent_unit", None) or root
                if bool(rule.get("requires_remained_stationary")):
                    if not bool(getattr(getattr(unit, "round_state", None), "remained_stationary_this_round", False)):
                        apply_bonus = False
                if apply_bonus and bool(rule.get("requires_owner_turn")):
                    owner_army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
                    owner_player = getattr(owner_army, "player", None) if owner_army is not None else None
                    game = getattr(owner_player, "game", None) if owner_player is not None else None
                    current_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
                    if owner_player is None or current_player is not owner_player:
                        apply_bonus = False
                if apply_bonus:
                    allowed_names = list(rule.get("weapon_names", []) or [])
                    if allowed_names:
                        current_weapon_name = str(weapon_name or "").strip()
                        if not current_weapon_name and weapon_profile is not None:
                            try:
                                current_weapon_name = str(getattr(getattr(weapon_profile, "parent_wargear", None), "name", "") or "")
                            except Exception:
                                current_weapon_name = ""
                            if not current_weapon_name:
                                try:
                                    current_weapon_name = str(getattr(weapon_profile, "name", "") or "")
                                except Exception:
                                    current_weapon_name = ""
                        if not self._weapon_name_matches(allowed_names, current_weapon_name):
                            apply_bonus = False
                if apply_bonus:
                    keyword = str(rule.get("keyword", "") or "").strip().upper()
                    if keyword:
                        source = str(rule.get("source", "") or "Remains Stationary").strip() or "Remains Stationary"
                        rules = list(rules or []) + [
                            {"attack_type": "ranged", "keyword": keyword, "source": source}
                        ]
        except Exception:
            pass
        try:
            if target is not None:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict) and sr.get("spirit_mark_active"):
                    target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                    target_id = str(get_entity_id(target_root) or "")
                    if target_id and str(sr.get("spirit_mark_target_id", "") or "") == target_id:
                        val = int(sr.get("spirit_mark_sustained_hits_value", 1) or 1)
                        source = str(sr.get("spirit_mark_source", "") or "Spirit Mark").strip() or "Spirit Mark"
                        if val > 0:
                            rules = list(rules or []) + [
                                {"attack_type": "any", "keyword": f"SUSTAINED HITS {val}", "source": source}
                            ]
        except Exception:
            pass
        if target is not None:
            source_unit = getattr(model, "parent_unit", None) or self
            source_army = source_unit.get_parent_army() if hasattr(source_unit, "get_parent_army") else None
            drukhari_mgr = getattr(source_army, "drukhari_detachments", None) if source_army is not None else None
            murderous_agenda_fn = (
                getattr(drukhari_mgr, "murderous_agenda_weapon_keyword_bonuses", None)
                if drukhari_mgr is not None
                else None
            )
            if callable(murderous_agenda_fn):
                for entry in list(murderous_agenda_fn(model, target) or []):
                    if not isinstance(entry, dict):
                        continue
                    keyword = str(entry.get("keyword", "") or "").strip().upper()
                    if not keyword:
                        continue
                    rules = list(rules or []) + [
                        {
                            "attack_type": str(entry.get("attack_type", "any") or "any").strip().lower(),
                            "keyword": keyword,
                            "source": str(entry.get("source", "") or "Murderous Agenda"),
                        }
                    ]
            mgr = getattr(source_army, "chaos_knights_detachments", None) if source_army is not None else None
            sustained_fn = getattr(mgr, "marked_prey_sustained_hits_value", None) if mgr is not None else None
            if callable(sustained_fn):
                sustained_value, source = sustained_fn(model, target)
                if int(sustained_value or 0) > 0:
                    rules = list(rules or []) + [
                        {
                            "attack_type": "any",
                            "keyword": f"SUSTAINED HITS {int(sustained_value)}",
                            "source": str(source or "Marked Prey"),
                        }
                    ]
            dark_sacrifice_fn = getattr(mgr, "iconoclast_dark_sacrifice_weapon_keyword", None) if mgr is not None else None
            dark_sacrifice_multi_fn = (
                getattr(mgr, "iconoclast_dark_sacrifice_weapon_keywords", None)
                if mgr is not None
                else None
            )
            if callable(dark_sacrifice_multi_fn):
                source_player = getattr(source_army, "player", None) if source_army is not None else None
                game = getattr(source_player, "game", None) if source_player is not None else None
                keywords, source = dark_sacrifice_multi_fn(
                    model,
                    attack_type=str(attack_type or ""),
                    game=game,
                )
                for keyword in list(keywords or []):
                    if not str(keyword or "").strip():
                        continue
                    rules = list(rules or []) + [
                        {
                            "attack_type": "any",
                            "keyword": str(keyword).strip().upper(),
                            "source": str(source or "Dark Sacrifice"),
                        }
                    ]
            elif callable(dark_sacrifice_fn):
                source_player = getattr(source_army, "player", None) if source_army is not None else None
                game = getattr(source_player, "game", None) if source_player is not None else None
                keyword, source = dark_sacrifice_fn(
                    model,
                    attack_type=str(attack_type or ""),
                    game=game,
                )
                if str(keyword or "").strip():
                    rules = list(rules or []) + [
                        {
                            "attack_type": "any",
                            "keyword": str(keyword).strip().upper(),
                            "source": str(source or "Dark Sacrifice"),
                        }
                    ]
        try:
            if target is not None:
                root = self.get_attached_unit_root()
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("piratical_raiders_target_id"):
                    target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                    target_id = str(get_entity_id(target_root) or "")
                    if target_id and str(sr.get("piratical_raiders_target_id", "") or "") == target_id:
                        source = str(sr.get("piratical_raiders_source", "") or "Piratical Raiders").strip() or "Piratical Raiders"
                        rules = list(rules or []) + [
                            {"attack_type": "any", "keyword": "LETHAL HITS", "source": source},
                            {"attack_type": "any", "keyword": "PRECISION", "source": source},
                        ]
        except Exception:
            pass
        try:
            if self._attached_unit_has_active_enhancement(
                "enhancement_mind_blade",
                enhancement_id="000010151004",
                enhancement_name="mind blade",
            ):
                source = "Mind Blade"
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
                for member in members:
                    sr = getattr(member, "special_rules", None)
                    if not isinstance(sr, dict):
                        continue
                    if not sr.get("enhancement_mind_blade"):
                        continue
                    source = str(sr.get("enhancement_mind_blade_source", "") or "").strip() or "Mind Blade"
                    break
                rules = list(rules or []) + [
                    {"attack_type": "melee", "keyword": "LANCE", "source": source}
                ]
        except Exception:
            pass
        try:
            if self._attached_unit_has_active_enhancement(
                "enhancement_alacritous_assault",
                enhancement_id="000010699003",
                enhancement_name="alacritous assault",
            ):
                source = "Alacritous Assault"
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
                for member in members:
                    sr = getattr(member, "special_rules", None)
                    if not isinstance(sr, dict):
                        continue
                    if not sr.get("enhancement_alacritous_assault"):
                        continue
                    source = str(sr.get("enhancement_alacritous_assault_source", "") or "").strip() or "Alacritous Assault"
                    break
                rules = list(rules or []) + [
                    {"attack_type": "melee", "keyword": "LANCE", "source": source}
                ]
        except Exception:
            pass
        try:
            if self._attached_unit_has_active_leading_enhancement(
                "enhancement_skjalds_foretelling",
                enhancement_id="000010660005",
                enhancement_name="skjald's foretelling",
            ):
                source = "Skjald's Foretelling"
                try:
                    root = self.get_attached_unit_root()
                except Exception:
                    root = self
                leaders = list(getattr(root, "attached_leaders", []) or [])
                for leader in list(leaders or []):
                    sr = getattr(leader, "special_rules", None)
                    if not isinstance(sr, dict):
                        continue
                    if not sr.get("enhancement_skjalds_foretelling"):
                        continue
                    source = (
                        str(sr.get("enhancement_skjalds_foretelling_source", "") or "Skjald's Foretelling").strip()
                        or "Skjald's Foretelling"
                    )
                    break
                rules = list(rules or []) + [
                    {"attack_type": "melee", "keyword": "LANCE", "source": source}
                ]
        except Exception:
            pass
        try:
            atype = str(attack_type or "").strip().lower()
            is_melee_attack = atype in ("", "any", "melee")
            if is_melee_attack and self._attached_unit_model_is_enhancement_bearer(
                model,
                flag_key="enhancement_archangels_shard",
                enhancement_id="000009190004",
                enhancement_name="archangel's shard",
                require_leading=False,
            ):
                try:
                    root = self.get_attached_unit_root()
                except Exception:
                    root = self
                source = "Archangel's Shard"
                anti_keyword = "CHAOS"
                anti_value = 5
                has_lance = True
                try:
                    members = list(root.get_attached_unit_members() or [])
                except Exception:
                    members = [root]
                if not members:
                    members = [root]
                for member in members:
                    sr = getattr(member, "special_rules", None)
                    if not isinstance(sr, dict):
                        continue
                    if not sr.get("enhancement_archangels_shard"):
                        continue
                    source = str(sr.get("enhancement_archangels_shard_source", "") or "").strip() or "Archangel's Shard"
                    anti_keyword = (
                        str(sr.get("enhancement_archangels_shard_anti_keyword", "CHAOS") or "CHAOS").strip().upper()
                        or "CHAOS"
                    )
                    try:
                        anti_value = int(sr.get("enhancement_archangels_shard_anti_value", 5) or 5)
                    except Exception:
                        anti_value = 5
                    has_lance = bool(sr.get("enhancement_archangels_shard_lance", True))
                    break
                if has_lance:
                    rules = list(rules or []) + [
                        {"attack_type": "melee", "keyword": "LANCE", "source": source}
                    ]
                if anti_keyword:
                    rules = list(rules or []) + [
                        {
                            "attack_type": "melee",
                            "keyword": f"ANTI-{anti_keyword} {int(max(2, anti_value))}+",
                            "source": source,
                        }
                    ]
        except Exception:
            pass
        try:
            atype = str(attack_type or "").strip().lower()
            is_melee_attack = atype in ("", "any", "melee")
            if is_melee_attack and self._attached_unit_model_is_enhancement_bearer(
                model,
                flag_key="enhancement_champion_of_the_deathwing",
                enhancement_id="000008774002",
                enhancement_name="champion of the deathwing",
                require_leading=False,
            ):
                source = "Champion of the Deathwing"
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
                for member in members:
                    sr = getattr(member, "special_rules", None)
                    if not isinstance(sr, dict):
                        continue
                    if not bool(sr.get("enhancement_champion_of_the_deathwing")):
                        continue
                    source = (
                        str(sr.get("enhancement_champion_of_the_deathwing_source", "") or "Champion of the Deathwing").strip()
                        or "Champion of the Deathwing"
                    )
                    break
                rules = list(rules or []) + [
                    {"attack_type": "melee", "keyword": "LETHAL HITS", "source": source}
                ]
        except Exception:
            pass
        try:
            attack_kind = str(attack_type or "").strip().lower()
            is_melee_attack = attack_kind in ("", "any", "melee")
            if is_melee_attack and self._attached_unit_model_is_enhancement_bearer(
                model,
                flag_key="enhancement_benediction_of_fury",
                enhancement_id="000009843005",
                enhancement_name="benediction of fury",
                require_leading=False,
            ):
                source = "Benediction of Fury"
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
                for member in members:
                    sr = getattr(member, "special_rules", None)
                    if not isinstance(sr, dict):
                        continue
                    if not bool(sr.get("enhancement_benediction_of_fury")):
                        continue
                    source = (
                        str(sr.get("enhancement_benediction_of_fury_source", "") or "Benediction of Fury").strip()
                        or "Benediction of Fury"
                    )
                    break
                rules = list(rules or []) + [
                    {"attack_type": "melee", "keyword": "DEVASTATING WOUNDS", "source": source}
                ]
        except Exception:
            pass
        try:
            if self._attached_unit_model_is_enhancement_bearer(
                model,
                flag_key="enhancement_master_nemesine",
                enhancement_id="000010584003",
                enhancement_name="master nemesine",
                require_leading=False,
            ):
                try:
                    root = self.get_attached_unit_root()
                except Exception:
                    root = self
                source = "Master Nemesine"
                anti_beast = 2
                anti_monster = 4
                try:
                    members = list(root.get_attached_unit_members() or [])
                except Exception:
                    members = [root]
                if not members:
                    members = [root]
                for member in members:
                    sr = getattr(member, "special_rules", None)
                    if not isinstance(sr, dict) or not bool(sr.get("enhancement_master_nemesine", False)):
                        continue
                    source = str(sr.get("enhancement_master_nemesine_source", "") or "Master Nemesine").strip() or "Master Nemesine"
                    try:
                        anti_beast = int(sr.get("enhancement_master_nemesine_anti_beast", 2) or 2)
                    except Exception:
                        anti_beast = 2
                    try:
                        anti_monster = int(sr.get("enhancement_master_nemesine_anti_monster", 4) or 4)
                    except Exception:
                        anti_monster = 4
                    break
                rules = list(rules or []) + [
                    {"attack_type": "any", "keyword": f"ANTI-BEAST {int(max(2, anti_beast))}+", "source": source},
                    {"attack_type": "any", "keyword": f"ANTI-MONSTER {int(max(2, anti_monster))}+", "source": source},
                ]
        except Exception:
            pass
        atype = str(attack_type or "").strip().lower()
        is_ranged_attack = atype in ("", "any", "ranged")
        if is_ranged_attack and self._attached_unit_model_is_enhancement_bearer(
            model,
            flag_key="enhancement_gaze_of_ynnead",
            enhancement_id="000009919002",
            enhancement_name="gaze of ynnead",
            require_leading=False,
        ):
            try:
                root = self.get_attached_unit_root()
            except Exception:
                root = self
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            source = str(sr.get("enhancement_gaze_of_ynnead_source", "") or "Gaze of Ynnead").strip() or "Gaze of Ynnead"
            weapon_names = [
                str(sr.get("enhancement_gaze_of_ynnead_weapon_name", "eldritch storm") or "eldritch storm")
            ]
            gaze_weapon_name = str(weapon_name or "").strip()
            if not gaze_weapon_name and weapon_profile is not None:
                try:
                    gaze_weapon_name = str(getattr(getattr(weapon_profile, "parent_wargear", None), "name", "") or "")
                except Exception:
                    gaze_weapon_name = ""
                if not gaze_weapon_name:
                    try:
                        gaze_weapon_name = str(getattr(weapon_profile, "name", "") or "")
                    except Exception:
                        gaze_weapon_name = ""
            if self._weapon_name_matches(weapon_names, gaze_weapon_name):
                rules = list(rules or []) + [
                    {"attack_type": "ranged", "keyword": "DEVASTATING WOUNDS", "source": source}
                ]
        try:
            source_unit = getattr(model, "parent_unit", None) or self
            army = source_unit.get_parent_army() if hasattr(source_unit, "get_parent_army") else None
            mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
            sustained_fn = getattr(mgr, "boons_of_the_brood_sustained_hits_value_for_model", None) if mgr is not None else None
            if callable(sustained_fn):
                sustained_value = int(sustained_fn(model, unit=source_unit) or 0)
                if sustained_value > 0:
                    rules = list(rules or []) + [
                        {
                            "attack_type": "any",
                            "keyword": f"SUSTAINED HITS {int(sustained_value)}",
                            "source": "Boons of the Brood",
                        }
                    ]
        except Exception:
            pass
        try:
            source_unit = getattr(model, "parent_unit", None) or self
            army = source_unit.get_parent_army() if hasattr(source_unit, "get_parent_army") else None
            mgr = getattr(army, "leagues_of_votann_detachments", None) if army is not None else None
            sustained_fn = getattr(mgr, "mobile_sensor_relays_sustained_hits_value", None) if mgr is not None else None
            if callable(sustained_fn):
                sustained_value, source = sustained_fn(model, weapon_profile=weapon_profile)
                if int(sustained_value or 0) > 0:
                    rules = list(rules or []) + [
                        {
                            "attack_type": "ranged",
                            "keyword": f"SUSTAINED HITS {int(sustained_value)}",
                            "source": str(source or "Mobile Sensor Relays"),
                        }
                    ]
        except Exception:
            pass
        if is_ranged_attack and self._attached_unit_has_active_enhancement(
            "enhancement_exotic_munitions",
            enhancement_id="000010699004",
            enhancement_name="exotic munitions",
        ):
            try:
                root = self.get_attached_unit_root()
            except Exception:
                root = self
            source = "Exotic Munitions"
            anti_monster = 5
            anti_vehicle = 5
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if not sr.get("enhancement_exotic_munitions"):
                    continue
                source = str(sr.get("enhancement_exotic_munitions_source", "") or "").strip() or "Exotic Munitions"
                try:
                    anti_monster = int(sr.get("enhancement_exotic_munitions_anti_monster", 5) or 5)
                except Exception:
                    anti_monster = 5
                try:
                    anti_vehicle = int(sr.get("enhancement_exotic_munitions_anti_vehicle", 5) or 5)
                except Exception:
                    anti_vehicle = 5
                break
            rules = list(rules or []) + [
                {"attack_type": "ranged", "keyword": f"ANTI-MONSTER {int(max(2, anti_monster))}+", "source": source},
                {"attack_type": "ranged", "keyword": f"ANTI-VEHICLE {int(max(2, anti_vehicle))}+", "source": source},
            ]
        try:
            if is_ranged_attack and model is not None:
                root = self.get_attached_unit_root()
                army = root.get_parent_army() if root is not None else None
                sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
                apply_fn = getattr(sm_mgr, "librarius_fusillade_attack_keywords", None) if sm_mgr is not None else None
                if callable(apply_fn):
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    keywords, source = apply_fn(model, weapon_profile=weapon_profile, game=game)
                    source_name = str(source or "Fusillade").strip() or "Fusillade"
                    for keyword in list(keywords or []):
                        kw = str(keyword or "").strip().upper()
                        if not kw:
                            continue
                        rules = list(rules or []) + [
                            {"attack_type": "ranged", "keyword": kw, "source": source_name}
                        ]
        except Exception:
            pass
        if is_ranged_attack and self._attached_unit_has_active_leading_enhancement(
            "enhancement_peerless_eradicator",
            enhancement_id="000008385004",
            enhancement_name="peerless eradicator",
        ):
            rules = list(rules or []) + [
                {"attack_type": "ranged", "keyword": "SUSTAINED HITS 1", "source": "Peerless Eradicator"}
            ]
        if is_ranged_attack and self._attached_unit_model_is_enhancement_bearer(
            model,
            flag_key="enhancement_houndpack_loping_predator",
            enhancement_id="000010312004",
            enhancement_name="loping predator",
            require_leading=False,
        ):
            rules = list(rules or []) + [
                {"attack_type": "ranged", "keyword": "ASSAULT", "source": "Loping Predator"}
            ]
        if is_ranged_attack and self._attached_unit_has_active_enhancement(
            "enhancement_hunters_eye",
            enhancement_id="000010629004",
            enhancement_name="hunter's eye",
        ):
            try:
                root = self.get_attached_unit_root()
            except Exception:
                root = self
            source = "Hunter's Eye"
            keywords = ["SUSTAINED HITS 1", "IGNORES COVER"]
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if not sr.get("enhancement_hunters_eye"):
                    continue
                source = str(sr.get("enhancement_hunters_eye_source", "") or "").strip() or "Hunter's Eye"
                configured = [
                    str(v or "").strip().upper()
                    for v in list(sr.get("enhancement_hunters_eye_keywords", []) or [])
                    if str(v or "").strip()
                ]
                if configured:
                    keywords = configured
                break
            allowed = {"SUSTAINED HITS 1", "IGNORES COVER"}
            for keyword in keywords:
                key = str(keyword or "").strip().upper()
                if key and key in allowed:
                    rules = list(rules or []) + [
                        {"attack_type": "ranged", "keyword": key, "source": source}
                    ]
        if is_ranged_attack and self._attached_unit_has_active_leading_enhancement(
            "enhancement_panoptispex",
            enhancement_id="000008395005",
            enhancement_name="panoptispex",
        ):
            try:
                root = self.get_attached_unit_root()
            except Exception:
                root = self
            source = "Panoptispex"
            keywords = ["IGNORES COVER"]
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict) or not bool(sr.get("enhancement_panoptispex", False)):
                    continue
                if bool(sr.get("enhancement_panoptispex_requires_bearer_leading", True)):
                    if not bool(getattr(member, "is_attached_leader", False)):
                        continue
                source = str(sr.get("enhancement_panoptispex_source", "") or "").strip() or "Panoptispex"
                configured = [
                    str(v or "").strip().upper()
                    for v in list(sr.get("enhancement_panoptispex_keywords", []) or [])
                    if str(v or "").strip()
                ]
                if configured:
                    keywords = configured
                break
            for keyword in keywords:
                key = str(keyword or "").strip().upper()
                if key == "IGNORES COVER":
                    rules = list(rules or []) + [
                        {"attack_type": "ranged", "keyword": "IGNORES COVER", "source": source}
                    ]
        if is_ranged_attack and self._attached_unit_model_is_enhancement_bearer(
            model,
            flag_key="enhancement_autoclavic_denunciation",
            enhancement_id="000008385005",
            enhancement_name="autoclavic denunciation",
            require_leading=False,
        ):
            rules = list(rules or []) + [
                {"attack_type": "ranged", "keyword": "ANTI-INFANTRY 2+", "source": "Autoclavic Denunciation"},
                {"attack_type": "ranged", "keyword": "ANTI-MONSTER 4+", "source": "Autoclavic Denunciation"},
            ]
        if is_ranged_attack and self._attached_unit_model_is_enhancement_bearer(
            model,
            flag_key="enhancement_arch_negator",
            enhancement_id="000008572005",
            enhancement_name="arch-negator",
            require_leading=False,
        ):
            try:
                root = self.get_attached_unit_root()
            except Exception:
                root = self
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            try:
                anti_vehicle = int(sr.get("enhancement_arch_negator_anti_vehicle", 4) or 4)
            except Exception:
                anti_vehicle = 4
            source = str(sr.get("enhancement_arch_negator_source", "") or "Arch-negator").strip() or "Arch-negator"
            rules = list(rules or []) + [
                {"attack_type": "ranged", "keyword": f"ANTI-VEHICLE {int(max(2, anti_vehicle))}+", "source": source},
            ]
        if is_ranged_attack and self._attached_unit_model_is_enhancement_bearer(
            model,
            flag_key="enhancement_iron_artifice",
            enhancement_id="000008976003",
            enhancement_name="iron artifice",
            require_leading=False,
        ):
            root = self.get_attached_unit_root()
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            try:
                anti_vehicle = int(sr.get("enhancement_iron_artifice_anti_vehicle", 4) or 4)
            except (TypeError, ValueError):
                anti_vehicle = 4
            try:
                anti_fortification = int(sr.get("enhancement_iron_artifice_anti_fortification", 4) or 4)
            except (TypeError, ValueError):
                anti_fortification = 4
            source = str(sr.get("enhancement_iron_artifice_source", "") or "Iron Artifice").strip() or "Iron Artifice"
            rules = list(rules or []) + [
                {"attack_type": "ranged", "keyword": f"ANTI-VEHICLE {int(max(2, anti_vehicle))}+", "source": source},
                {
                    "attack_type": "ranged",
                    "keyword": f"ANTI-FORTIFICATION {int(max(2, anti_fortification))}+",
                    "source": source,
                },
            ]
        if is_ranged_attack and self._attached_unit_model_is_enhancement_bearer(
            model,
            flag_key="enhancement_micromelta_rounds",
            enhancement_id="000009757005",
            enhancement_name="micromelta rounds",
            require_leading=False,
        ):
            try:
                root = self.get_attached_unit_root()
            except Exception:
                root = self
            source = "Micromelta Rounds"
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            weapon_names = [str(sr.get("enhancement_micromelta_rounds_weapon_name", "exitus rifle") or "exitus rifle")]
            try:
                anti_monster = int(sr.get("enhancement_micromelta_rounds_anti_monster", 4) or 4)
            except Exception:
                anti_monster = 4
            try:
                anti_vehicle = int(sr.get("enhancement_micromelta_rounds_anti_vehicle", 4) or 4)
            except Exception:
                anti_vehicle = 4
            micromelta_weapon_name = str(weapon_name or "").strip()
            if not micromelta_weapon_name and weapon_profile is not None:
                try:
                    micromelta_weapon_name = str(getattr(getattr(weapon_profile, "parent_wargear", None), "name", "") or "")
                except Exception:
                    micromelta_weapon_name = ""
                if not micromelta_weapon_name:
                    try:
                        micromelta_weapon_name = str(getattr(weapon_profile, "name", "") or "")
                    except Exception:
                        micromelta_weapon_name = ""
            if self._weapon_name_matches(weapon_names, micromelta_weapon_name):
                rules = list(rules or []) + [
                    {"attack_type": "ranged", "keyword": f"ANTI-MONSTER {int(max(2, anti_monster))}+", "source": source},
                    {"attack_type": "ranged", "keyword": f"ANTI-VEHICLE {int(max(2, anti_vehicle))}+", "source": source},
                ]
        if self._attached_unit_model_is_enhancement_bearer(
            model,
            flag_key="enhancement_seersight_strike",
            enhancement_id="000009903004",
            enhancement_name="seersight strike",
            require_leading=False,
        ):
            is_psychic_weapon = False
            if weapon_profile is not None:
                is_psychic = getattr(weapon_profile, "is_psychic", None)
                if callable(is_psychic):
                    is_psychic_weapon = bool(is_psychic())
            if is_psychic_weapon:
                get_root = getattr(self, "get_attached_unit_root", None)
                if callable(get_root):
                    try:
                        root = get_root()
                    except AttributeError:
                        root = self
                else:
                    root = self
                if root is None:
                    root = self
                source = "Seersight Strike"
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                try:
                    anti_monster = int(sr.get("enhancement_seersight_strike_anti_monster", 2) or 2)
                except (TypeError, ValueError):
                    anti_monster = 2
                try:
                    anti_vehicle = int(sr.get("enhancement_seersight_strike_anti_vehicle", 2) or 2)
                except (TypeError, ValueError):
                    anti_vehicle = 2
                rules = list(rules or []) + [
                    {"attack_type": "any", "keyword": f"ANTI-MONSTER {int(max(2, anti_monster))}+", "source": source},
                    {"attack_type": "any", "keyword": f"ANTI-VEHICLE {int(max(2, anti_vehicle))}+", "source": source},
                ]
        try:
            root = self.get_attached_unit_root()
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("aetherstride_sustained_hits_d3_active"):
                model_id = str(get_entity_id(model) or "")
                owner_id = str(sr.get("aetherstride_sustained_hits_d3_owner", "") or "")
                turn = int(sr.get("aetherstride_sustained_hits_d3_turn", 0) or 0)
                source = str(sr.get("aetherstride_source", "") or "Aetherstride").strip() or "Aetherstride"
                apply_bonus = False
                if model_id and model_id == str(sr.get("aetherstride_model_id", "") or ""):
                    game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                    if game is not None:
                        try:
                            cur_turn = int(getattr(game, "turn", 0) or 0)
                            cur_owner = str(getattr(game.get_current_player(), "id", "") or "")
                            apply_bonus = bool(cur_turn == turn and owner_id and cur_owner == owner_id)
                        except Exception:
                            apply_bonus = False
                if apply_bonus:
                    wname = str(weapon_name or "").strip().lower()
                    if "dark blessing" in wname:
                        rules = list(rules or []) + [
                            {"attack_type": "any", "keyword": "SUSTAINED HITS D3", "source": source}
                        ]
        except Exception:
            pass
        try:
            root = self.get_attached_unit_root()
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("resource_transmutation_active_model_id"):
                model_id = str(get_entity_id(model) or "")
                active_model_id = str(sr.get("resource_transmutation_active_model_id", "") or "")
                apply_bonus = bool(model_id and model_id == active_model_id)
                if apply_bonus:
                    owner_id = str(sr.get("resource_transmutation_owner", "") or "")
                    turn = int(sr.get("resource_transmutation_turn", 0) or 0)
                    game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                    if game is not None:
                        try:
                            cur_turn = int(getattr(game, "turn", 0) or 0)
                        except Exception:
                            cur_turn = 0
                        try:
                            cur_owner = str(getattr(game.get_current_player(), "id", "") or "")
                        except Exception:
                            cur_owner = ""
                        try:
                            phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            phase = ""
                        if turn and cur_turn and turn != cur_turn:
                            apply_bonus = False
                        if owner_id and cur_owner and owner_id != cur_owner:
                            apply_bonus = False
                        if phase and phase != "SHOOTING_PHASE":
                            apply_bonus = False
                if apply_bonus:
                    source = str(sr.get("resource_transmutation_source", "") or "Resource Transmutation").strip() or "Resource Transmutation"
                    rules = list(rules or []) + [
                        {"attack_type": "ranged", "keyword": "SUSTAINED HITS 1", "source": source}
                    ]
        except Exception:
            pass
        try:
            if target is not None:
                root = self.get_attached_unit_root()
                prey_ids = getattr(root, "_prey_selection_prey_ids", None)
                keywords = []
                for raw in list(getattr(root, "_prey_selection_keywords", []) or []):
                    keyword = str(raw or "").strip().upper()
                    if keyword and keyword not in keywords:
                        keywords.append(keyword)
                fallback_keyword = str(getattr(root, "_prey_selection_keyword", "") or "").strip().upper()
                if fallback_keyword and fallback_keyword not in keywords:
                    keywords.append(fallback_keyword)
                if prey_ids and keywords:
                    try:
                        target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                        tid = getattr(target_root, "_id", None)
                        rid = getattr(target, "_id", None)
                    except Exception:
                        tid = getattr(target, "_id", None)
                        rid = None
                    if (tid in prey_ids) or (rid in prey_ids):
                        source = str(getattr(root, "_prey_selection_source", "") or "Prey selection").strip() or "Prey selection"
                        for keyword in keywords:
                            rules = list(rules or []) + [{"attack_type": "any", "keyword": keyword, "source": source}]
        except Exception:
            pass
        try:
            if target is not None:
                root = self.get_attached_unit_root()
                quarry_ids = getattr(root, "_exemplar_of_the_code_quarry_ids", None)
                precision_vs_quarry = bool(getattr(root, "_exemplar_of_the_code_precision", False))
                if quarry_ids and precision_vs_quarry:
                    try:
                        target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                        tid = getattr(target_root, "_id", None)
                        rid = getattr(target, "_id", None)
                    except Exception:
                        tid = getattr(target, "_id", None)
                        rid = None
                    if (tid in quarry_ids) or (rid in quarry_ids):
                        source = (
                            str(getattr(root, "_exemplar_of_the_code_source", "") or "Exemplar of the Code").strip()
                            or "Exemplar of the Code"
                        )
                        rules = list(rules or []) + [
                            {"attack_type": "any", "keyword": "PRECISION", "source": source}
                        ]
        except Exception:
            pass
        try:
            root = self.get_attached_unit_root()
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("aeldari_preternatural_precision_active"):
                apply_bonus = True
                exp = str(sr.get("aeldari_preternatural_precision_expires_phase", "") or "").strip().upper()
                owner_id = str(sr.get("aeldari_preternatural_precision_owner", "") or "")
                turn = int(sr.get("aeldari_preternatural_precision_turn", 0) or 0)
                if exp or owner_id or turn:
                    game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                    if game is not None:
                        try:
                            cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            cur_phase = ""
                        try:
                            cur_owner = str(getattr(game.get_current_player(), "id", "") or "")
                        except Exception:
                            cur_owner = ""
                        try:
                            cur_turn = int(getattr(game, "turn", 0) or 0)
                        except Exception:
                            cur_turn = 0
                        if exp and cur_phase and cur_phase != exp:
                            apply_bonus = False
                        if owner_id and cur_owner and owner_id != cur_owner:
                            apply_bonus = False
                        if turn and cur_turn and turn != cur_turn:
                            apply_bonus = False
                atype = str(attack_type or "").strip().lower()
                if atype and atype not in ("any", "ranged"):
                    apply_bonus = False
                if apply_bonus:
                    source = str(sr.get("aeldari_preternatural_precision_source", "") or "PRETERNATURAL PRECISION").strip()
                    source = source or "PRETERNATURAL PRECISION"
                    allowed = {"IGNORES COVER", "LETHAL HITS", "SUSTAINED HITS 1"}
                    for keyword in list(sr.get("aeldari_preternatural_precision_keywords", []) or []):
                        kw = str(keyword or "").strip().upper()
                        if kw in allowed:
                            rules = list(rules or []) + [
                                {"attack_type": "ranged", "keyword": kw, "source": source}
                            ]
        except Exception:
            pass
        try:
            root = self.get_attached_unit_root()
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("aeldari_devoted_soulsight_active"):
                apply_bonus = True
                exp = str(sr.get("aeldari_devoted_soulsight_expires_phase", "") or "").strip().upper()
                owner_id = str(sr.get("aeldari_devoted_soulsight_owner", "") or "")
                try:
                    turn = int(sr.get("aeldari_devoted_soulsight_turn", 0) or 0)
                except (TypeError, ValueError):
                    turn = 0
                if exp or owner_id or turn:
                    game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                    if game is not None:
                        try:
                            cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            cur_phase = ""
                        try:
                            cur_owner = str(getattr(game.get_current_player(), "id", "") or "")
                        except Exception:
                            cur_owner = ""
                        try:
                            cur_turn = int(getattr(game, "turn", 0) or 0)
                        except (TypeError, ValueError):
                            cur_turn = 0
                        if exp and cur_phase and cur_phase != exp:
                            apply_bonus = False
                        if owner_id and cur_owner and owner_id != cur_owner:
                            apply_bonus = False
                        if turn and cur_turn and turn != cur_turn:
                            apply_bonus = False
                atype = str(attack_type or "").strip().lower()
                if atype and atype not in ("any", "ranged"):
                    apply_bonus = False
                if apply_bonus:
                    source = str(sr.get("aeldari_devoted_soulsight_source", "") or "SOULSIGHT").strip() or "SOULSIGHT"
                    rules = list(rules or []) + [
                        {"attack_type": "ranged", "keyword": "LETHAL HITS", "source": source},
                        {"attack_type": "ranged", "keyword": "IGNORES COVER", "source": source},
                    ]
        except Exception:
            pass
        try:
            root = self.get_attached_unit_root()
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("aeldari_outcast_ambush_active"):
                apply_bonus = True
                exp = str(sr.get("aeldari_outcast_ambush_expires_phase", "") or "").strip().upper()
                owner_id = str(sr.get("aeldari_outcast_ambush_turn_owner", "") or "")
                try:
                    turn = int(sr.get("aeldari_outcast_ambush_turn", 0) or 0)
                except (TypeError, ValueError):
                    turn = 0
                if exp or owner_id or turn:
                    game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                    if game is not None:
                        try:
                            cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            cur_phase = ""
                        try:
                            cur_owner = str(getattr(game.get_current_player(), "id", "") or "")
                        except Exception:
                            cur_owner = ""
                        try:
                            cur_turn = int(getattr(game, "turn", 0) or 0)
                        except (TypeError, ValueError):
                            cur_turn = 0
                        if exp and cur_phase and cur_phase != exp:
                            apply_bonus = False
                        if owner_id and cur_owner and owner_id != cur_owner:
                            apply_bonus = False
                        if turn and cur_turn and turn != cur_turn:
                            apply_bonus = False
                atype = str(attack_type or "").strip().lower()
                if atype and atype not in ("any", "ranged"):
                    apply_bonus = False
                if apply_bonus:
                    source = str(sr.get("aeldari_outcast_ambush_source", "") or "OUTCAST AMBUSH").strip()
                    source = source or "OUTCAST AMBUSH"
                    rules = list(rules or []) + [
                        {"attack_type": "ranged", "keyword": "IGNORES COVER", "source": source}
                    ]
        except Exception:
            pass
        try:
            root = self.get_attached_unit_root()
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and (
                sr.get("tau_threat_assessment_analyser_active") or sr.get("threat_assessment_analyser_active")
            ):
                apply_bonus = True
                exp = str(
                    sr.get("tau_threat_assessment_analyser_expires_phase", "")
                    or sr.get("threat_assessment_analyser_expires_phase", "")
                    or ""
                ).strip().upper()
                owner_id = str(
                    sr.get("tau_threat_assessment_analyser_turn_owner", "")
                    or sr.get("threat_assessment_analyser_owner", "")
                    or ""
                )
                try:
                    turn = int(
                        sr.get("tau_threat_assessment_analyser_turn", sr.get("threat_assessment_analyser_turn", 0)) or 0
                    )
                except (TypeError, ValueError):
                    turn = 0
                if exp or owner_id or turn:
                    game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                    if game is not None:
                        try:
                            cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            cur_phase = ""
                        try:
                            cur_owner = str(getattr(game.get_current_player(), "id", "") or "")
                        except Exception:
                            cur_owner = ""
                        try:
                            cur_turn = int(getattr(game, "turn", 0) or 0)
                        except (TypeError, ValueError):
                            cur_turn = 0
                        if exp and cur_phase and cur_phase != exp:
                            apply_bonus = False
                        if owner_id and cur_owner and owner_id != cur_owner:
                            apply_bonus = False
                        if turn and cur_turn and turn != cur_turn:
                            apply_bonus = False
                atype = str(attack_type or "").strip().lower()
                if atype and atype not in ("any", "ranged"):
                    apply_bonus = False
                if apply_bonus:
                    source = str(
                        sr.get("tau_threat_assessment_analyser_source", "")
                        or sr.get("threat_assessment_analyser_source", "")
                        or "THREAT ASSESSMENT ANALYSER"
                    ).strip()
                    source = source or "THREAT ASSESSMENT ANALYSER"
                    if bool(
                        sr.get("tau_threat_assessment_analyser_lethal_hits")
                        or sr.get("threat_assessment_analyser_lethal_hits")
                    ):
                        rules = list(rules or []) + [
                            {"attack_type": "ranged", "keyword": "LETHAL HITS", "source": source}
                        ]
                    sustained_value = 0
                    try:
                        sustained_value = int(
                            sr.get(
                                "tau_threat_assessment_analyser_sustained_hits_value",
                                sr.get("threat_assessment_analyser_sustained_hits_value", 0),
                            )
                            or 0
                        )
                    except (TypeError, ValueError):
                        sustained_value = 0
                    if sustained_value <= 0 and bool(
                        sr.get("tau_threat_assessment_analyser_sustained_hits")
                        or sr.get("threat_assessment_analyser_sustained_hits")
                    ):
                        sustained_value = 1
                    if sustained_value > 0:
                        rules = list(rules or []) + [
                            {
                                "attack_type": "ranged",
                                "keyword": f"SUSTAINED HITS {int(sustained_value)}",
                                "source": source,
                            }
                        ]
        except Exception:
            pass
        try:
            root = self.get_attached_unit_root()
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("enhancement_wolf_master_active")):
                apply_bonus = True
                atype = str(attack_type or "").strip().lower()
                if atype and atype not in ("any", "melee"):
                    apply_bonus = False
                current_weapon_name = str(weapon_name or "").strip()
                if not current_weapon_name and weapon_profile is not None:
                    try:
                        current_weapon_name = str(
                            getattr(getattr(weapon_profile, "parent_wargear", None), "name", "") or ""
                        )
                    except Exception:
                        current_weapon_name = ""
                    if not current_weapon_name:
                        try:
                            current_weapon_name = str(getattr(weapon_profile, "name", "") or "")
                        except Exception:
                            current_weapon_name = ""
                weapon_names = list(sr.get("enhancement_wolf_master_weapon_names", []) or [])
                if not weapon_names:
                    weapon_names = ["teeth and claws", "tyrnak and fenrir"]
                if not self._weapon_name_matches(weapon_names, current_weapon_name):
                    apply_bonus = False
                if apply_bonus:
                    source = str(sr.get("enhancement_wolf_master_source", "") or "Wolf Master").strip() or "Wolf Master"
                    rules = list(rules or []) + [
                        {"attack_type": "melee", "keyword": "LETHAL HITS", "source": source}
                    ]
        except Exception:
            pass
        if not rules:
            return {}
        return self._resolve_attack_keyword_bonuses_from_rules(rules, attack_type=attack_type)

    def get_weapon_target_excluding_keywords_keyword_bonus_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return weapon-scoped attack keyword bonus rules for patterns like:
        "Each time this model makes an attack with its punisher gatling cannon that targets an enemy unit
         (excluding MONSTERS and VEHICLES), that attack has the [DEVASTATING WOUNDS] ability."
        """
        if model is None:
            return None
        cache_key = f"weapon_target_excluding_keywords_keyword_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            entries = list(self._iter_model_specific_ability_entries(model) or [])
            entries.extend(list(self._iter_ability_entries_for_rules(model=None) or []))
            for name, desc in entries:
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                normalized = text.lower().replace("\u2019", "'")
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                match = re.fullmatch(
                    r"each time this model makes an attack with its (?P<weapon>[a-z0-9 ]+?) "
                    r"that targets (?:an? )?(?:enemy )?unit excluding (?P<exclude>[a-z0-9 ]+) that attack has "
                    r"(?:the )?(?P<keyword>[a-z0-9 ]+) ability",
                    normalized,
                )
                if not match:
                    continue
                weapon_name = str(match.group("weapon") or "").strip()
                keyword = str(match.group("keyword") or "").strip().upper()
                raw_exclude = str(match.group("exclude") or "").strip().lower()
                if not weapon_name or not keyword or not raw_exclude:
                    continue
                excluded_values = []
                for token in re.split(r"\s*(?:,|and|or)\s*", raw_exclude):
                    token = token.strip()
                    if not token:
                        continue
                    normalized_keyword = self._normalize_keyword_phrase(token) or token.strip().upper()
                    normalized_keyword = str(normalized_keyword or "").strip().upper()
                    if normalized_keyword.endswith("S") and len(normalized_keyword) > 1:
                        normalized_keyword = normalized_keyword[:-1]
                    if normalized_keyword and normalized_keyword not in excluded_values:
                        excluded_values.append(normalized_keyword)
                excluded = tuple(excluded_values)
                if not excluded:
                    continue
                rule = {
                    "attack_type": "ranged",
                    "weapon_names": [weapon_name],
                    "keyword": keyword,
                    "target_exclude_keywords_any": excluded,
                    "source": str(name or "Weapon keyword bonus").strip() or "Weapon keyword bonus",
                }
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_weapon_target_keywords_keyword_bonus_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return weapon-scoped attack keyword bonus rules for patterns like:
        "Each time this model makes an attack with its volcano cannon that targets a MONSTER or VEHICLE unit,
         that attack has the [DEVASTATING WOUNDS] ability."
        Also supports weapon-worded variants like:
        "This model's twin heavy onslaught gatling cannon has the [SUSTAINED HITS 2] ability when targeting
         INFANTRY units."
        """
        if model is None:
            return None
        cache_key = f"weapon_target_keywords_keyword_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            entries = list(self._iter_model_specific_ability_entries(model) or [])
            entries.extend(list(self._iter_ability_entries_for_rules(model=None) or []))
            for name, desc in entries:
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                normalized = text.lower().replace("\u2019", "'")
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                match = re.fullmatch(
                    r"each time this model makes an? (?:melee |ranged )?attack with its (?P<weapon>[a-z0-9 ]+?) "
                    r"that targets (?:an? )?(?:enemy )?(?P<targets>[a-z0-9 ]+?) unit that attack has "
                    r"(?:the )?(?P<keyword>[a-z0-9 ]+) ability",
                    normalized,
                )
                if not match:
                    match = re.fullmatch(
                        r"this model s (?P<weapon>[a-z0-9 ]+?) has (?:the )?(?P<keyword>[a-z0-9 ]+) ability "
                        r"(?:when|while) targeting (?:an? )?(?:enemy )?(?P<targets>[a-z0-9 ]+?) units?",
                        normalized,
                    )
                if not match:
                    continue
                weapon_name = str(match.group("weapon") or "").strip()
                keyword = str(match.group("keyword") or "").strip().upper()
                raw_targets = str(match.group("targets") or "").strip().lower()
                if not weapon_name or not keyword or not raw_targets:
                    continue
                target_keywords: list[str] = []
                for token in re.split(r"\s*(?:,|\band\b|\bor\b)\s*", raw_targets):
                    token = str(token or "").strip()
                    if not token:
                        continue
                    normalized_keyword = self._normalize_keyword_phrase(token) or token.strip().upper()
                    normalized_keyword = str(normalized_keyword or "").strip().upper()
                    if normalized_keyword.endswith("S") and len(normalized_keyword) > 1:
                        normalized_keyword = normalized_keyword[:-1]
                    if normalized_keyword and normalized_keyword not in target_keywords:
                        target_keywords.append(normalized_keyword)
                if not target_keywords:
                    continue
                rule = {
                    "attack_type": "ranged",
                    "weapon_names": [weapon_name],
                    "keyword": keyword,
                    "target_keywords_any": tuple(target_keywords),
                    "source": str(name or "Weapon keyword bonus").strip() or "Weapon keyword bonus",
                }
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_unit_target_keywords_weapon_keyword_bonus_rules(self) -> list[dict]:
        """
        Return unit-scoped attack keyword bonus rules for patterns like:
        "Melee weapons equipped by models in this unit have the [SUSTAINED HITS 2]
         ability when targeting MONSTER, VEHICLE or FORTIFICATION units."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return []
        cache_key = "unit_target_keywords_weapon_keyword_bonus_rules"
        if cache_key in getattr(root, "_ability_cache", {}):
            cached = root._ability_cache.get(cache_key)
            return list(cached) if isinstance(cached, list) else []

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        rules: list[dict] = []
        seen: set[tuple[str, str, tuple[str, ...], str]] = set()

        for member in list(members or []):
            if member is None:
                continue
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                normalized = text.lower().replace("\u2019", "'")
                normalized = re.sub(r"[^a-z0-9,]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                match = re.fullmatch(
                    r"(?:(?P<scope>melee|ranged) )?weapons equipped by models in "
                    r"(?:this unit|that unit|the bearer s unit) (?:have|gain) "
                    r"(?:the )?(?P<keyword>[a-z0-9 +\-]+?) ability when targeting "
                    r"(?:an? )?(?:enemy )?(?P<targets>[a-z0-9, ]+?) units?",
                    normalized,
                )
                if not match:
                    continue
                attack_type = str(match.group("scope") or "").strip().lower()
                if attack_type not in ("melee", "ranged"):
                    attack_type = "any"
                keyword = str(match.group("keyword") or "").strip().upper()
                raw_targets = str(match.group("targets") or "").strip().lower()
                if not keyword or not raw_targets:
                    continue
                target_keywords: list[str] = []
                for token in re.split(r"\s*(?:,|\band\b|\bor\b)\s*", raw_targets):
                    token = str(token or "").strip()
                    if not token:
                        continue
                    normalized_keyword = self._normalize_keyword_phrase(token) or token.strip().upper()
                    normalized_keyword = str(normalized_keyword or "").strip().upper()
                    if normalized_keyword.endswith("S") and len(normalized_keyword) > 1:
                        normalized_keyword = normalized_keyword[:-1]
                    if normalized_keyword and normalized_keyword not in target_keywords:
                        target_keywords.append(normalized_keyword)
                if not target_keywords:
                    continue
                source = str(name or "Unit keyword bonus").strip() or "Unit keyword bonus"
                key = (attack_type, keyword, tuple(target_keywords), source.lower())
                if key in seen:
                    continue
                seen.add(key)
                rules.append(
                    {
                        "attack_type": attack_type,
                        "keyword": keyword,
                        "target_keywords_any": tuple(target_keywords),
                        "source": source,
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(rules)
        return rules

    def get_attack_keyword_bonuses(
        self,
        *,
        target=None,
        attack_type: Optional[str] = None,
        model: Optional['Model'] = None,
        weapon_profile=None,
        game_map=None,
    ) -> dict:
        """
        Return conditional attack keyword bonuses for this model/unit.

        Supported keywords: Ignores Cover, Lethal Hits, Sustained Hits X, Devastating Wounds, Twin-linked.
        """
        rules = list(self._get_attack_keyword_bonus_rules(model=model) or [])
        target_keyword_rule = self.get_weapon_target_keywords_keyword_bonus_rule(model)
        if isinstance(target_keyword_rule, dict):
            rules.append(target_keyword_rule)
        rules.extend(list(self.get_unit_target_keywords_weapon_keyword_bonus_rules() or []))
        extra_rule = self.get_weapon_target_excluding_keywords_keyword_bonus_rule(model)
        if isinstance(extra_rule, dict):
            rules.append(extra_rule)
        # Unholy Bloodshed: temporary Devastating Wounds after Dark Pact.
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and sr.get("unholy_bloodshed_active"):
            apply_bonus = True
            exp = str(sr.get("unholy_bloodshed_expires_phase", "") or "").strip().upper()
            if exp:
                army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if game is not None:
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    if pname and pname != exp:
                        apply_bonus = False
            if apply_bonus:
                source = str(sr.get("unholy_bloodshed_source", "") or "Unholy Bloodshed").strip() or "Unholy Bloodshed"
                rules.append({"attack_type": "any", "keyword": "DEVASTATING WOUNDS", "source": source})
        if isinstance(sr, dict) and sr.get("aeldari_fate_inescapable_active"):
            apply_bonus = True
            exp = str(sr.get("aeldari_fate_inescapable_expires_phase", "") or "").strip().upper()
            owner_id = str(sr.get("aeldari_fate_inescapable_turn_owner", "") or "")
            try:
                turn = int(sr.get("aeldari_fate_inescapable_turn", 0) or 0)
            except (TypeError, ValueError):
                turn = 0
            if exp or owner_id or turn:
                game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                if game is not None:
                    try:
                        cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    except Exception:
                        cur_phase = ""
                    try:
                        cur_owner = str(getattr(game.get_current_player(), "id", "") or "")
                    except Exception:
                        cur_owner = ""
                    try:
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                    except (TypeError, ValueError):
                        cur_turn = 0
                    if exp and cur_phase and cur_phase != exp:
                        apply_bonus = False
                    if owner_id and cur_owner and owner_id != cur_owner:
                        apply_bonus = False
                    if turn and cur_turn and turn != cur_turn:
                        apply_bonus = False
            atype = str(attack_type or "").strip().lower()
            if atype and atype not in ("any", "ranged"):
                apply_bonus = False
            if apply_bonus:
                source = str(sr.get("aeldari_fate_inescapable_source", "") or "FATE INESCAPABLE").strip()
                source = source or "FATE INESCAPABLE"
                rules.append({"attack_type": "ranged", "keyword": "IGNORES COVER", "source": source})
        if isinstance(sr, dict) and bool(sr.get("enhancement_target_augury_web_active")):
            source_name = str(sr.get("enhancement_target_augury_web_source", "") or "Target Augury Web").strip()
            if not source_name:
                source_name = "Target Augury Web"
            rules.append({"attack_type": "any", "keyword": "LETHAL HITS", "source": source_name})
        if isinstance(sr, dict) and bool(sr.get("master_of_mechanisms_weapon_keywords_active")) and model is not None:
            apply_bonus = True
            effect_attack_type = str(sr.get("master_of_mechanisms_weapon_attack_type", "any") or "any").strip().lower()
            if effect_attack_type not in ("any", "melee", "ranged"):
                effect_attack_type = "any"
            attack_kind = str(attack_type or "").strip().lower()
            if attack_kind and effect_attack_type not in ("any", attack_kind):
                apply_bonus = False
            target_model_id = str(sr.get("master_of_mechanisms_weapon_keyword_model_id", "") or "")
            if apply_bonus and target_model_id and not self._model_matches_identifier(model, target_model_id):
                apply_bonus = False
            current_weapon_name = ""
            if apply_bonus and weapon_profile is not None:
                try:
                    current_weapon_name = str(getattr(getattr(weapon_profile, "parent_wargear", None), "name", "") or "")
                except Exception:
                    current_weapon_name = ""
                if not current_weapon_name:
                    try:
                        current_weapon_name = str(getattr(weapon_profile, "name", "") or "")
                    except Exception:
                        current_weapon_name = ""
            selected_weapon_name = str(sr.get("master_of_mechanisms_weapon_name", "") or "").strip()
            if apply_bonus and selected_weapon_name and not self._weapon_name_matches([selected_weapon_name], current_weapon_name):
                apply_bonus = False
            if apply_bonus:
                source_name = str(sr.get("master_of_mechanisms_source", "") or "Master of Mechanisms").strip() or "Master of Mechanisms"
                for keyword in list(sr.get("master_of_mechanisms_weapon_keywords", []) or []):
                    keyword_text = str(keyword or "").strip().upper()
                    if not keyword_text:
                        continue
                    rules.append(
                        {
                            "attack_type": effect_attack_type,
                            "keyword": keyword_text,
                            "source": source_name,
                        }
                    )
        try:
            target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
        except Exception:
            target_root = target
        target_sr = getattr(target_root, "special_rules", None)
        if isinstance(target_sr, dict):
            effects = list(target_sr.get("selected_to_shoot_target_attack_keyword_effects", []) or [])
            if effects:
                source_unit_id = str(get_entity_id(root) or "")
                try:
                    source_player = getattr(root.get_parent_army(), "player", None)
                except Exception:
                    source_player = None
                source_owner_id = str(getattr(source_player, "id", "") or "")
                game = getattr(source_player, "game", None) if source_player is not None else None
                current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except Exception:
                    current_turn = 0
                seen_selected_to_shoot: set[tuple[str, str]] = set()
                for effect in list(effects or []):
                    if not isinstance(effect, dict):
                        continue
                    effect_source_unit_id = str(effect.get("source_unit_id", "") or "")
                    if effect_source_unit_id and source_unit_id and effect_source_unit_id != source_unit_id:
                        continue
                    effect_owner_id = str(effect.get("owner_id", "") or effect.get("owner", "") or "")
                    if effect_owner_id and source_owner_id and effect_owner_id != source_owner_id:
                        continue
                    try:
                        effect_turn = int(effect.get("turn", 0) or 0)
                    except (TypeError, ValueError):
                        effect_turn = 0
                    if effect_turn and current_turn and effect_turn != current_turn:
                        continue
                    expires_phase = str(effect.get("expires_phase", "") or "").strip().upper()
                    if expires_phase and current_phase and expires_phase != current_phase:
                        continue
                    effect_attack_type = str(effect.get("attack_type", "") or "any").strip().lower()
                    if effect_attack_type not in ("any", "melee", "ranged"):
                        effect_attack_type = "any"
                    attack_kind = str(attack_type or "").strip().lower()
                    if attack_kind and effect_attack_type not in ("any", attack_kind):
                        continue
                    source_name = str(effect.get("source", "") or "Selected to shoot").strip() or "Selected to shoot"
                    for keyword in list(effect.get("keywords", []) or []):
                        keyword_text = str(keyword or "").strip().upper()
                        if not keyword_text:
                            continue
                        dedupe_key = (effect_attack_type, keyword_text)
                        if dedupe_key in seen_selected_to_shoot:
                            continue
                        seen_selected_to_shoot.add(dedupe_key)
                        rules.append(
                            {
                                "attack_type": effect_attack_type,
                                "keyword": keyword_text,
                                "source": source_name,
                            }
                        )
        try:
            if isinstance(sr, dict):
                lethal_active = bool(sr.get("embodied_prophecy_lethal_hits_active", False))
                try:
                    sustained_value = int(sr.get("embodied_prophecy_sustained_hits_value", 0) or 0)
                except Exception:
                    sustained_value = 0
                sustained_value = max(0, int(sustained_value))
                apply_bonus = bool(lethal_active or sustained_value > 0)

                atype = str(attack_type or "").strip().lower()
                if apply_bonus and atype and atype not in ("any", "melee"):
                    apply_bonus = False
                if apply_bonus:
                    source_army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                    source_player = getattr(source_army, "player", None) if source_army is not None else None
                    game = getattr(source_player, "game", None) if source_player is not None else None
                    exp = str(sr.get("embodied_prophecy_expires_phase", "") or "").strip().upper()
                    owner_id = str(sr.get("embodied_prophecy_turn_owner", "") or "")
                    try:
                        effect_turn = int(sr.get("embodied_prophecy_turn", 0) or 0)
                    except Exception:
                        effect_turn = 0
                    if game is not None:
                        try:
                            cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        except Exception:
                            cur_phase = ""
                        try:
                            cur_owner = str(getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or "")
                        except Exception:
                            cur_owner = ""
                        try:
                            cur_turn = int(getattr(game, "turn", 0) or 0)
                        except Exception:
                            cur_turn = 0
                        if exp and cur_phase and cur_phase != exp:
                            apply_bonus = False
                        if apply_bonus and owner_id and cur_owner and owner_id != cur_owner:
                            apply_bonus = False
                        if apply_bonus and effect_turn and cur_turn and effect_turn != cur_turn:
                            apply_bonus = False
                if apply_bonus:
                    source_name = str(sr.get("embodied_prophecy_source", "") or "Embodied Prophecy").strip()
                    source_name = source_name or "Embodied Prophecy"
                    if lethal_active:
                        rules.append({"attack_type": "melee", "keyword": "LETHAL HITS", "source": source_name})
                    if sustained_value > 0:
                        rules.append(
                            {
                                "attack_type": "melee",
                                "keyword": f"SUSTAINED HITS {int(sustained_value)}",
                                "source": source_name,
                            }
                        )
        except Exception:
            pass
        try:
            honourable_rule_fn = getattr(root, "get_an_honourable_death_in_combat_rule", None)
            honourable_rule = honourable_rule_fn() if callable(honourable_rule_fn) else None
            if isinstance(honourable_rule, dict):
                source_name = str(
                    honourable_rule.get("source", "") or "An Honourable Death in Combat"
                ).strip() or "An Honourable Death in Combat"
                sustained_value = 0
                if bool(getattr(root, "is_below_half_strength", lambda: False)()):
                    try:
                        sustained_value = int(
                            honourable_rule.get("below_half_strength_sustained_hits_value", 0) or 0
                        )
                    except Exception:
                        sustained_value = 0
                elif bool(getattr(root, "is_below_starting_strength", lambda: False)()):
                    try:
                        sustained_value = int(
                            honourable_rule.get("below_starting_strength_sustained_hits_value", 0) or 0
                        )
                    except Exception:
                        sustained_value = 0
                if sustained_value > 0:
                    rules.append(
                        {
                            "attack_type": "any",
                            "keyword": f"SUSTAINED HITS {int(sustained_value)}",
                            "source": source_name,
                        }
                    )
        except Exception:
            pass
        try:
            attack_kind = str(attack_type or "").strip().lower()
            if attack_kind in ("", "any", "melee") and model is not None:
                attacker_model_id = str(get_entity_id(model) or "")
                if attacker_model_id:
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
                        if not isinstance(member_sr, dict) or not bool(member_sr.get("enhancement_rage_fuelled_warrior_active")):
                            continue
                        source_model_id = str(
                            member_sr.get("enhancement_rage_fuelled_warrior_active_model_id", "")
                            or member_sr.get("enhancement_rage_fuelled_warrior_bearer_model_id", "")
                            or member_sr.get("enhancement_bearer_model_id", "")
                            or ""
                        )
                        if source_model_id and source_model_id != attacker_model_id:
                            continue
                        applies = True
                        owner_id = str(member_sr.get("enhancement_rage_fuelled_warrior_turn_owner", "") or "")
                        try:
                            effect_turn = int(member_sr.get("enhancement_rage_fuelled_warrior_turn", 0) or 0)
                        except Exception:
                            effect_turn = 0
                        exp = str(member_sr.get("enhancement_rage_fuelled_warrior_expires_phase", "") or "").strip().upper()
                        try:
                            source_army = member.get_parent_army()
                        except Exception:
                            source_army = None
                        game = getattr(getattr(source_army, "player", None), "game", None) if source_army is not None else None
                        if game is not None:
                            if owner_id:
                                current_owner = str(getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or "")
                                if current_owner and current_owner != owner_id:
                                    applies = False
                            if applies and effect_turn:
                                try:
                                    if int(getattr(game, "turn", 0) or 0) != effect_turn:
                                        applies = False
                                except Exception:
                                    applies = False
                            if applies and exp:
                                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                                if phase_name and phase_name != exp:
                                    applies = False
                        if not applies:
                            continue
                        try:
                            sustained_hits = int(
                                member_sr.get(
                                    "enhancement_rage_fuelled_warrior_active_sustained_hits",
                                    member_sr.get("enhancement_rage_fuelled_warrior_sustained_hits", 3),
                                )
                                or 3
                            )
                        except Exception:
                            sustained_hits = 3
                        sustained_hits = int(max(1, sustained_hits))
                        source_name = str(
                            member_sr.get("enhancement_rage_fuelled_warrior_source", "")
                            or "Rage-fuelled Warrior"
                        ).strip() or "Rage-fuelled Warrior"
                        rules.append(
                            {
                                "attack_type": "melee",
                                "keyword": f"SUSTAINED HITS {int(sustained_hits)}",
                                "source": source_name,
                            }
                        )
                        break
        except Exception:
            pass
        temp_effect_iter = getattr(self, "iter_active_orks_temp_effects", None)
        if callable(temp_effect_iter):
            attack_kind = str(attack_type or "any").strip().lower()
            if attack_kind not in ("any", "melee", "ranged"):
                attack_kind = "any"
            for effect in list(
                temp_effect_iter(
                    effect_type="keyword",
                    attack_type=attack_kind,
                    target=target,
                    model=model,
                    game_map=game_map,
                )
                or []
            ):
                keyword = str(effect.get("keyword", "") or "").strip().upper()
                if not keyword:
                    continue
                source_name = str(effect.get("source", "") or "Orks temporary effect").strip() or "Orks temporary effect"
                rules.append(
                    {
                        "attack_type": str(effect.get("attack_type", "any") or "any"),
                        "keyword": keyword,
                        "source": source_name,
                    }
                )
        if not rules:
            return {}
        if target is None:
            return {}
        filtered = []
        current_weapon_name = ""
        if weapon_profile is not None:
            try:
                current_weapon_name = str(getattr(getattr(weapon_profile, "parent_wargear", None), "name", "") or "").strip()
            except Exception:
                current_weapon_name = ""
            if not current_weapon_name:
                try:
                    current_weapon_name = str(getattr(weapon_profile, "name", "") or "").strip()
                except Exception:
                    current_weapon_name = ""

        def _target_has_keyword(val: str) -> bool:
            key = str(val or "").strip()
            if not key:
                return False
            if key.lower() == "afflicted":
                return self._target_is_afflicted_for_attack_bonuses(target, game_map=game_map)
            try:
                return bool(target.has_keyword(key.upper()))
            except Exception:
                try:
                    return bool(target.has_any_keyword(key.upper()))
                except Exception:
                    return False

        for rule in list(rules or []):
            if bool(rule.get("requires_critical_wound", False)):
                continue
            if rule.get("requires_objective"):
                try:
                    if not self._target_within_objective_range(target, game_map):
                        continue
                except Exception:
                    continue
            required_contains_keyword = str(rule.get("requires_unit_contains_keyword", "") or "").strip()
            if required_contains_keyword:
                contains_required_model = False
                contains_keyword_fn = getattr(root, "_unit_contains_model_with_keyword", None)
                if callable(contains_keyword_fn):
                    contains_required_model = bool(contains_keyword_fn(required_contains_keyword))
                if not contains_required_model:
                    contains_named_fn = getattr(root, "_unit_contains_model_named", None)
                    if callable(contains_named_fn):
                        contains_required_model = bool(contains_named_fn(required_contains_keyword))
                if not contains_required_model:
                    continue
            required_model_keyword = str(rule.get("requires_model_keyword", "") or "").strip()
            if required_model_keyword:
                if model is None:
                    continue
                has_required_model_keyword = False
                try:
                    has_required_model_keyword = bool(model.has_keyword(required_model_keyword.upper()))
                except Exception:
                    try:
                        has_required_model_keyword = bool(model.has_any_keyword(required_model_keyword.upper()))
                    except Exception:
                        has_required_model_keyword = False
                if not has_required_model_keyword:
                    continue
            weapon_names = list(rule.get("weapon_names", []) or [])
            if weapon_names:
                if not current_weapon_name:
                    continue
                if not self._weapon_name_matches(weapon_names, current_weapon_name):
                    continue
            target_keywords_any = tuple(rule.get("target_keywords_any") or ())
            if target_keywords_any:
                if not any(_target_has_keyword(k) for k in target_keywords_any):
                    continue
            target_exclude_keywords = tuple(rule.get("target_exclude_keywords_any") or ())
            if target_exclude_keywords:
                if any(_target_has_keyword(k) for k in target_exclude_keywords):
                    continue
            if bool(rule.get("requires_closest_eligible_target", False)):
                if model is None or weapon_profile is None:
                    continue
                gm = game_map
                if gm is None:
                    try:
                        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                    except Exception:
                        army = None
                    player = getattr(army, "player", None) if army is not None else None
                    game = getattr(player, "game", None) if player is not None else None
                    gm = getattr(game, "map", None) if game is not None else None
                if gm is None:
                    continue
                req_keywords = {
                    str(token or "").strip().upper()
                    for token in list(rule.get("closest_require_keywords_any", []) or [])
                    if str(token or "").strip()
                }
                is_closest = getattr(self, "is_target_closest_eligible", None)
                if not callable(is_closest):
                    continue
                if not bool(
                    is_closest(
                        model,
                        weapon_profile,
                        target,
                        gm,
                        require_keywords=req_keywords if req_keywords else None,
                    )
                ):
                    continue
            filtered.append(rule)
        if not filtered:
            return {}
        return self._resolve_attack_keyword_bonuses_from_rules(filtered, attack_type=attack_type)

    def get_attack_keyword_bonuses_on_critical_wound(
        self,
        *,
        target=None,
        attack_type: Optional[str] = None,
        model: Optional['Model'] = None,
        game_map=None,
    ) -> dict:
        """
        Return attack keyword bonuses that are applied only when a critical wound is scored.
        """
        if target is None:
            return {}
        rules = list(self._get_attack_keyword_bonus_rules(model=model) or [])
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("enhancement_stave_of_kurnous_active")):
            source_name = str(sr.get("enhancement_stave_of_kurnous_source", "") or "Stave of Kurnous").strip()
            source_name = source_name or "Stave of Kurnous"
            rules.append(
                {
                    "attack_type": "any",
                    "keyword": "PRECISION",
                    "source": source_name,
                    "requires_critical_wound": True,
                }
            )
        if not rules:
            return {}
        filtered = []

        def _target_has_keyword(val: str) -> bool:
            key = str(val or "").strip()
            if not key:
                return False
            if key.lower() == "afflicted":
                return self._target_is_afflicted_for_attack_bonuses(target, game_map=game_map)
            try:
                return bool(target.has_keyword(key.upper()))
            except Exception:
                try:
                    return bool(target.has_any_keyword(key.upper()))
                except Exception:
                    return False

        for rule in list(rules or []):
            if not bool(rule.get("requires_critical_wound", False)):
                continue
            if rule.get("requires_objective"):
                try:
                    if not self._target_within_objective_range(target, game_map):
                        continue
                except Exception:
                    continue
            required_contains_keyword = str(rule.get("requires_unit_contains_keyword", "") or "").strip()
            if required_contains_keyword:
                contains_required_model = False
                contains_keyword_fn = getattr(root, "_unit_contains_model_with_keyword", None)
                if callable(contains_keyword_fn):
                    contains_required_model = bool(contains_keyword_fn(required_contains_keyword))
                if not contains_required_model:
                    contains_named_fn = getattr(root, "_unit_contains_model_named", None)
                    if callable(contains_named_fn):
                        contains_required_model = bool(contains_named_fn(required_contains_keyword))
                if not contains_required_model:
                    continue
            required_model_keyword = str(rule.get("requires_model_keyword", "") or "").strip()
            if required_model_keyword:
                if model is None:
                    continue
                has_required_model_keyword = False
                try:
                    has_required_model_keyword = bool(model.has_keyword(required_model_keyword.upper()))
                except Exception:
                    try:
                        has_required_model_keyword = bool(model.has_any_keyword(required_model_keyword.upper()))
                    except Exception:
                        has_required_model_keyword = False
                if not has_required_model_keyword:
                    continue
            target_keywords_any = tuple(rule.get("target_keywords_any") or ())
            if target_keywords_any:
                if not any(_target_has_keyword(k) for k in target_keywords_any):
                    continue
            filtered.append(rule)
        if not filtered:
            return {}
        return self._resolve_attack_keyword_bonuses_from_rules(filtered, attack_type=attack_type)

    @staticmethod
    def _normalize_weapon_name(name: str) -> str:
        cleaned = re.sub(r"[^a-z0-9 ]+", " ", str(name or "").lower())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned.startswith("the "):
            cleaned = cleaned[4:]
        if cleaned.startswith("its "):
            cleaned = cleaned[4:]
        return cleaned

    def _weapon_name_matches(self, weapon_names: list[str], weapon_name: str) -> bool:
        if not weapon_names:
            return True
        normalized = self._normalize_weapon_name(weapon_name)
        if not normalized:
            return False
        for entry in list(weapon_names or []):
            candidate = self._normalize_weapon_name(entry)
            if not candidate:
                continue
            if candidate in normalized or normalized in candidate:
                return True
        return False

    def get_attack_half_range_keyword_bonuses(
        self,
        *,
        attack_type: Optional[str] = None,
        model: Optional['Model'] = None,
        within_half_range: bool = False,
        weapon_profile=None,
        weapon_name: str = "",
    ) -> dict:
        """
        Return half-range keyword bonuses for this model/unit.

        Supported keywords: Ignores Cover, Lethal Hits, Sustained Hits X, Devastating Wounds, Twin-linked.
        """
        if not within_half_range:
            return {}
        rules = self._get_attack_half_range_keyword_bonus_rules(model=model)
        if not rules:
            return {}
        wname = str(weapon_name or "").strip()
        if not wname and weapon_profile is not None:
            try:
                wname = str(getattr(getattr(weapon_profile, "parent_wargear", None), "name", "") or "")
            except Exception:
                wname = ""
            if not wname:
                try:
                    wname = str(getattr(weapon_profile, "name", "") or "")
                except Exception:
                    wname = ""
        filtered = []
        for rule in list(rules or []):
            names = rule.get("weapon_names")
            if names and not self._weapon_name_matches(list(names or []), wname):
                continue
            filtered.append(rule)
        if not filtered:
            return {}
        return self._resolve_attack_keyword_bonuses_from_rules(filtered, attack_type=attack_type)

    def set_martial_katah_choice(self, choice: str) -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["martial_katah_choice"] = str(choice or "").strip().upper()
        root.special_rules = sr

    def clear_martial_katah_choice(self) -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        sr.pop("martial_katah_choice", None)
        root.special_rules = sr

    def set_exquisite_swordsmanship_choice(self, choice: str) -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["exquisite_swordsmanship_choice"] = str(choice or "").strip().upper()
        sr["exquisite_swordsmanship_expires_phase"] = "FIGHT_PHASE"
        root.special_rules = sr

    def clear_exquisite_swordsmanship_choice(self) -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for k in ("exquisite_swordsmanship_choice", "exquisite_swordsmanship_expires_phase"):
            sr.pop(k, None)
        root.special_rules = sr

    def set_path_of_warrior_choice(self, choice: str, *, phase_name: str = "") -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["path_of_warrior_choice"] = str(choice or "").strip().upper()
        if phase_name:
            sr["path_of_warrior_expires_phase"] = str(phase_name or "").strip().upper()
        root.special_rules = sr

    def clear_path_of_warrior_choice(self) -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for k in ("path_of_warrior_choice", "path_of_warrior_expires_phase"):
            sr.pop(k, None)
        root.special_rules = sr

    def set_dance_of_death_choice(self, choice: str, *, phase_name: str = "") -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["dance_of_death_choice"] = str(choice or "").strip().upper()
        if phase_name:
            sr["dance_of_death_expires_phase"] = str(phase_name or "").strip().upper()
        root.special_rules = sr

    def clear_dance_of_death_choice(self) -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for k in ("dance_of_death_choice", "dance_of_death_expires_phase"):
            sr.pop(k, None)
        root.special_rules = sr

    def set_bladeguard_choice(self, choice: str, *, phase_name: str = "") -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["bladeguard_choice"] = str(choice or "").strip().upper()
        if phase_name:
            sr["bladeguard_expires_phase"] = str(phase_name or "").strip().upper()
        root.special_rules = sr

    def clear_bladeguard_choice(self) -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for k in ("bladeguard_choice", "bladeguard_expires_phase"):
            sr.pop(k, None)
        root.special_rules = sr

    def set_adaptive_instincts_choice(self, choice: str, *, phase_name: str = "") -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["adaptive_instincts_choice"] = str(choice or "").strip().upper()
        if phase_name:
            sr["adaptive_instincts_expires_phase"] = str(phase_name or "").strip().upper()
        root.special_rules = sr

    def clear_adaptive_instincts_choice(self) -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for k in ("adaptive_instincts_choice", "adaptive_instincts_expires_phase"):
            sr.pop(k, None)
        root.special_rules = sr

    def attached_unit_has_reanimation_protocols(self) -> bool:
        """Attached unit eligibility: true if any attached member has Reanimation Protocols."""
        for u in self.get_attached_unit_members():
            try:
                if u.has_reanimation_protocols():
                    return True
            except Exception:
                continue
        return False

    def get_choreographer_of_war_source(self) -> str:
        """Return the source name if a leading Choreographer of War ability is active."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "choreographer_of_war_source"
        try:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict):
                stratagem_source = str(sr.get("stratagem_choreographer_of_war_source", "") or "").strip()
                if stratagem_source:
                    active = True
                    exp_phase = str(
                        sr.get("stratagem_choreographer_of_war_expires_phase", "")
                        or sr.get("carnival_violent_crescendo_expires_phase", "")
                        or ""
                    ).strip().upper()
                    owner_id = str(
                        sr.get("stratagem_choreographer_of_war_turn_owner", "")
                        or sr.get("carnival_violent_crescendo_owner", "")
                        or ""
                    )
                    effect_turn = int(
                        sr.get("stratagem_choreographer_of_war_turn", sr.get("carnival_violent_crescendo_turn", 0))
                        or 0
                    )
                    game = None
                    try:
                        army = root.get_parent_army()
                    except Exception:
                        army = None
                    try:
                        game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    except Exception:
                        game = None
                    if game is not None:
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        if owner_id and cur_owner and owner_id != cur_owner:
                            active = False
                        if effect_turn and cur_turn and effect_turn != cur_turn:
                            active = False
                        if exp_phase and cur_phase and exp_phase != cur_phase:
                            active = False
                    if active:
                        if not hasattr(root, "_ability_cache"):
                            root._ability_cache = {}
                        root._ability_cache[cache_key] = stratagem_source
                        return str(stratagem_source or "")
        except Exception:
            pass
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return str(cache.get(cache_key) or "")

        source = ""
        for ab, _leader in root._iter_attached_leader_leading_abilities():
            try:
                name = str(getattr(ab, "name", "") or "")
                desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            name_norm = name.strip().lower()
            text = root._normalize_rules_text(desc or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", " s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if name_norm == "choreographer of war":
                source = name or "Choreographer of War"
                break
            if name_norm == "onslaught":
                if (
                    "pile in" in norm
                    and "consolidation move" in norm
                    and "move up to 6" in norm
                    and "instead of up to 3" in norm
                ):
                    source = name or "Onslaught"
                    break
            if (
                "pile in" in norm
                and "consolidation move" in norm
                and "move up to 6" in norm
                and "instead of up to 3" in norm
                and (
                    "as close as possible to the closest enemy unit" in norm
                    or "while this model is leading a unit" in norm
                )
            ):
                source = name or "Choreographer of War"
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = source
        return str(source or "")

    def _can_consolidate_end_in_engagement(self, max_distance: float) -> bool:
        """Return True if this unit can end a consolidate within Engagement Range this move."""
        try:
            distance_limit = float(max_distance)
        except (TypeError, ValueError):
            return False
        if distance_limit <= 0.0:
            return False

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        player = getattr(army, "player", None) if army is not None else None
        game = getattr(player, "game", None) if player is not None else None
        game_map = getattr(game, "map", None)
        if game_map is None:
            # Preserve existing behavior in contexts without a live map (e.g. isolated tests).
            return True

        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if callable(get_enemy_units):
            enemy_units = list(get_enemy_units(root) or [])
        else:
            enemy_units = [
                u
                for u in list(getattr(game_map, "units", []) or [])
                if u is not None and getattr(u, "faction", None) != getattr(root, "faction", None)
            ]
        if not enemy_units:
            return False

        alive_enemies = []
        for enemy in enemy_units:
            if enemy is None:
                continue
            alive_fn = getattr(enemy, "is_alive", None)
            if callable(alive_fn):
                if not alive_fn():
                    continue
            elif getattr(enemy, "is_alive", True) is False:
                continue
            if getattr(enemy, "deployed", True) is False:
                continue
            alive_enemies.append(enemy)
        if not alive_enemies:
            return False

        is_within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if callable(is_within_engagement):
            for enemy in alive_enemies:
                if is_within_engagement(root, enemy):
                    return True

        get_distance_between_units = getattr(game_map, "get_distance_between_units", None)
        if not callable(get_distance_between_units):
            return False

        min_distance = None
        for enemy in alive_enemies:
            try:
                dist = float(get_distance_between_units(root, enemy))
            except (TypeError, ValueError):
                continue
            if min_distance is None or dist < min_distance:
                min_distance = dist
        if min_distance is None:
            return False

        from ...utility.constants import ENGAGEMENT_RANGE_HORIZONTAL

        return float(min_distance) <= float(distance_limit) + float(ENGAGEMENT_RANGE_HORIZONTAL or 1.0)

    def get_fight_phase_move_distance_override(self, movement_kind: str) -> Optional[float]:
        """
        Return a fight-phase move distance override (pile-in / consolidate) if a rule modifies it.
        movement_kind: 'pile_in' or 'consolidate'
        """
        kind = str(movement_kind).strip().lower()
        if kind not in ("pile_in", "consolidate"):
            return None

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        override = None

        try:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict):
                exp = str(sr.get("battle_focus_sudden_strike_expires_phase", "") or "").strip().upper()
                if exp:
                    pname = ""
                    try:
                        army = root.get_parent_army()
                        game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
                        phase = getattr(game, "phase", None) if game is not None else None
                        pname = str(getattr(phase, "name", "") or phase or "").strip().upper()
                    except Exception:
                        pname = ""
                    if not pname or pname == exp:
                        override = max(float(override or 0.0), 6.0)
        except Exception:
            pass

        try:
            if self.get_choreographer_of_war_source():
                override = max(float(override or 0.0), 6.0)
        except Exception:
            pass

        try:
            army = root.get_parent_army()
            mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
            game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
            br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            if mgr is not None and br > 0:
                if root.attached_unit_has_blessings_of_khorne():
                    if mgr.is_blessing_active_for_unit("RAGE_FUELLED_INVIGORATION", root, battle_round=br):
                        override = max(float(override or 0.0), 6.0)
        except Exception:
            pass

        try:
            members = list(root.get_attached_unit_members() or []) if hasattr(root, "get_attached_unit_members") else [root]
            if not members:
                members = [root]
            for member in members:
                sr_member = getattr(member, "special_rules", None)
                if not isinstance(sr_member, dict):
                    continue
                if not bool(sr_member.get("enhancement_singular_will", False)):
                    continue
                bearer = None
                bearer_id = str(
                    sr_member.get("enhancement_singular_will_bearer_model_id", "")
                    or sr_member.get("enhancement_bearer_model_id", "")
                    or ""
                ).strip()
                if bearer_id:
                    for model in list(getattr(member, "models", []) or []):
                        model_entity_id = str(get_entity_id(model) or "").strip()
                        model_local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                        if bearer_id != model_entity_id and bearer_id != model_local_id:
                            continue
                        bearer = model
                        break
                if bearer is None:
                    get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                    if callable(get_bearer):
                        bearer = get_bearer()
                if bearer is None:
                    continue
                alive_attr = getattr(bearer, "is_alive", True)
                bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if not bearer_alive:
                    continue
                if kind == "pile_in":
                    bonus = int(sr_member.get("enhancement_singular_will_pile_in_distance_bonus", 3) or 3)
                else:
                    bonus = int(sr_member.get("enhancement_singular_will_consolidate_distance_bonus", 3) or 3)
                if bonus <= 0:
                    continue
                override = max(float(override or 0.0), 3.0 + float(bonus))
        except Exception:
            pass

        if kind == "consolidate":
            try:
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict):
                    dist = sr.get("stratagem_consolidate_distance_override")
                    if dist is not None:
                        override = max(float(override or 0.0), float(dist))
                    dist = sr.get("bearer_unit_consolidate_distance_override")
                    if dist is not None:
                        dist_value = float(dist)
                        requires_engagement = bool(sr.get("bearer_unit_consolidate_requires_engagement", False))
                        if (not requires_engagement) or self._can_consolidate_end_in_engagement(dist_value):
                            override = max(float(override or 0.0), dist_value)
            except Exception:
                pass
        if kind == "pile_in":
            try:
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict):
                    dist = sr.get("bearer_unit_pile_in_distance_override")
                    if dist is not None:
                        override = max(float(override or 0.0), float(dist))
            except Exception:
                pass

        return float(override) if override else None

    def maybe_resolve_pending_separation(self, game_map: Optional['Map'] = None) -> None:
        """Resolve pending separation only if no attack resolution window is active."""
        root = self._attack_resolution_root()
        try:
            depth = int(getattr(root, "_attack_resolution_depth", 0))
        except Exception:
            depth = 0
        if depth == 0:
            try:
                root.resolve_pending_leader_separation(game_map=game_map)
            except Exception:
                pass



    def get_closest_model_position_to_target(self, target_position: Tuple[float, float, float]) -> Optional[Tuple[float, float, float]]:
        """Get the position of the model closest to a target position.

        Args:
            target_position: (x, y, z) coordinates of the target

        Returns:
            Tuple[float, float, float]: Position of closest model or None if no alive models
        """
        closest_model = None
        closest_distance = float('inf')

        for model in self.models:
            if not model.is_alive:
                continue
            model_pos = model.get_location()
            if model_pos:
                distance = get_dist(
                    target_position[0] - model_pos[0],
                    target_position[1] - model_pos[1],
                    target_position[2] - model_pos[2] if len(model_pos) > 2 else 0
                )
                if distance < closest_distance:
                    closest_distance = distance
                    closest_model = model

        return closest_model.get_location() if closest_model else None

    def is_point_inside(self, x, y):
        # Check if point is within any model's base
        for model in self.models:
            if not model.is_alive:
                continue
            model_pos = model.get_location()
            if model_pos:
                # Check if point is within model's base radius
                model_radius = getattr(model.model_base, 'radius', 1.0)
                if isinstance(model_radius, (tuple, list)):
                    model_radius = max(model_radius)  # Use larger radius for elliptical bases
                distance = get_dist(x - model_pos[0], y - model_pos[1])
                if distance <= model_radius:
                    return True
        return False

    def score_position(self, x, y, z, facing, game_map, model, placed_positions):
        """
        Score a candidate position for model placement.
        Lower is better. 
        You can enhance this to factor in more things: cover, distance to objective, edge, enemy, etc.
        """
        # Simple version: maximize coherency, avoid edge, avoid obstacles.
        battlefield_width, battlefield_height = game_map.width, game_map.height

        # Distance from board edge (prefer center)
        min_x_dist = min(x, battlefield_width - x)
        min_y_dist = min(y, battlefield_height - y)
        edge_penalty = max(0, 6.0 - min(min_x_dist, min_y_dist)) * 10  # penalize <6" from edge

        # Penalty if near obstacle/impassable (cover not scored in this heuristic).
        cover_bonus = 0

        # Coherency bonus (number of coherent neighbors)
        coherent_neighbors = 0
        for pos in placed_positions:
            other_x, other_y, other_z, other_facing = pos
            # Assume unit has .coherency_distance
            dist = get_dist(x - other_x, y - other_y, z - other_z)
            if dist <= self.coherency_distance:
                coherent_neighbors += 1
        # Encourage more neighbors
        coherency_bonus = -coherent_neighbors * 20

        return edge_penalty + cover_bonus + coherency_bonus

    def _get_reduced_boundary_repulsors(self, game_map: 'Map') -> List:
        """Get reduced boundary repulsors for formation finding during movement.
        
        These are smaller than the full battlefield edge repulsors to allow better
        formation finding in crowded areas while still preventing units from going
        off the battlefield.
        """
        from shapely.geometry import Polygon
        
        repulsors = []
        repulsor_thickness = 0.25  # Reduced from 0.5 to 0.25 inches
        
        # Left battlefield edge repulsor (reduced)
        left_edge = Polygon([
            (-repulsor_thickness, -repulsor_thickness),
            (0, -repulsor_thickness),
            (0, game_map.height + repulsor_thickness),
            (-repulsor_thickness, game_map.height + repulsor_thickness)
        ])
        repulsors.append(left_edge)
        
        # Right battlefield edge repulsor (reduced)
        right_edge = Polygon([
            (game_map.width, -repulsor_thickness),
            (game_map.width + repulsor_thickness, -repulsor_thickness),
            (game_map.width + repulsor_thickness, game_map.height + repulsor_thickness),
            (game_map.width, game_map.height + repulsor_thickness)
        ])
        repulsors.append(right_edge)
        
        # Bottom battlefield edge repulsor (reduced)
        bottom_edge = Polygon([
            (-repulsor_thickness, -repulsor_thickness),
            (game_map.width + repulsor_thickness, -repulsor_thickness),
            (game_map.width + repulsor_thickness, 0),
            (-repulsor_thickness, 0)
        ])
        repulsors.append(bottom_edge)
        
        # Top battlefield edge repulsor (reduced)
        top_edge = Polygon([
            (-repulsor_thickness, game_map.height),
            (game_map.width + repulsor_thickness, game_map.height),
            (game_map.width + repulsor_thickness, game_map.height + repulsor_thickness),
            (-repulsor_thickness, game_map.height + repulsor_thickness)
        ])
        repulsors.append(top_edge)

        logger.debug(f"DEBUG: _get_reduced_boundary_repulsors returning {len(repulsors)} repulsors for map size {game_map.width}x{game_map.height}")

        return repulsors

    def calculate_strategic_facing(self, x: float, y: float, game_map: 'Map') -> float:
        """Calculate strategic facing direction towards enemies or objectives"""
        
        # Get our army to determine enemies
        army = self.get_parent_army()
        if not army:
            return 0.0  # Default facing if no army context
        
        best_target = None
        min_distance = float('inf')
        
        # Priority 1: Face nearest visible enemy unit
        for unit in game_map.units:
            if unit != self and unit.get_parent_army() != army and unit.is_alive():
                # Find the closest model in the enemy unit to our position
                closest_enemy_distance = float('inf')
                closest_enemy_pos = None

                for model in unit.models:
                    if model.is_alive:
                        enemy_pos = model.get_location()
                        distance = get_dist(x - enemy_pos[0], y - enemy_pos[1])
                        if distance < closest_enemy_distance:
                            closest_enemy_distance = distance
                            closest_enemy_pos = enemy_pos

                if closest_enemy_pos and closest_enemy_distance < min_distance:
                    min_distance = closest_enemy_distance
                    best_target = closest_enemy_pos
        
        # Priority 2: If no enemies, face towards objectives
        if not best_target and hasattr(game_map, 'objectives'):
            for objective in game_map.objectives:
                obj_pos = (objective.location.x, objective.location.y)
                distance = get_dist(x - obj_pos[0], y - obj_pos[1])
                if distance < min_distance:
                    min_distance = distance
                    best_target = obj_pos
        
        # Priority 3: Face towards center of battlefield
        if not best_target:
            center_x = game_map.width / 2
            center_y = game_map.height / 2
            best_target = (center_x, center_y)
        
        # Calculate angle to target
        dx = best_target[0] - x
        dy = best_target[1] - y
        return get_angle(dy, dx)

    def calculate_model_positions(self,
                                start_x: float,
                                start_y: float,
                                game_map: 'Map',
                                grid_step=0.5,
                                relax_iters=5,
                                avoid_friendly_units=True,
                                boundary_repulsors=None):
        """
        Computes (x, y, z, facing) for each model in self.models.
        Tries formation templates (block, wedge, circle, column) built 
        with safe spacing based on base size; falls back to per-model A*.
        
        Args:
            start_x: Target X coordinate for unit placement
            start_y: Target Y coordinate for unit placement
            game_map: The game map
            grid_step: Step size for pathfinding grid (default 0.5)
            relax_iters: Number of relaxation iterations (default 5)
            avoid_friendly_units: Whether to avoid collisions with friendly units
            boundary_repulsors: Optional list of boundary repulsor polygons to avoid
            
        Returns:
            List of (x, y, z, facing) tuples for each model, or None if failed
        """
        if not self.models:
            return []

        if boundary_repulsors is None:
            boundary_repulsors = []

        # Single model - use fast path
        if len(self.models) == 1:
            z = game_map.get_surface_height_for_model(self.models[0], start_x, start_y)
            self.models[0].set_location(start_x, start_y, z, 0.0)
            return [(start_x, start_y, z, 0.0)]

        logger.debug(f"DEBUG: calculate_model_positions for {self.name} ({len(self.models)} models)")
        logger.debug(f"DEBUG: start position: ({start_x:.1f}, {start_y:.1f})")
        logger.debug(f"DEBUG: avoid_friendly_units: {avoid_friendly_units}")
        logger.debug(f"DEBUG: boundary_repulsors: {len(boundary_repulsors) if boundary_repulsors else 0}")

        # Debug boundary repulsors
        if len(boundary_repulsors) == 0:
            logger.debug(f"DEBUG: No boundary repulsors provided - this might cause formation finding issues")
        else:
            logger.debug(f"DEBUG: Boundary repulsors provided: {[type(br).__name__ for br in boundary_repulsors]}")

        # FAST PATH FOR SINGLE-MODEL UNITS (avoid terrain & enemy models)
        if len(self.models) == 1:
            logger.debug(f"DEBUG: Using single-model fast path")
            # initial drop
            z = game_map.get_surface_height_for_model(self.models[0], start_x, start_y)
            f = self.calculate_strategic_facing(start_x, start_y, game_map)
            pos = [start_x, start_y, z, f]
            m = self.models[0]

            # Build list of blocking models (enemies + optionally friendlies)
            blocking_models = game_map.get_enemy_models(self)
            if avoid_friendly_units:
                # Add friendly models from other units (excluding self)
                friendly_models = []
                for unit in game_map.get_friendly_units(self):
                    if unit != self:  # Don't include models from the unit being positioned
                        friendly_models.extend(unit.models)
                blocking_models.extend(friendly_models)
            
            # Use provided boundary repulsors or default to empty list
            if boundary_repulsors is None:
                boundary_repulsors = []
            
            # one-off spatial index of terrain + blocking models + boundary repulsors
            # Convert terrain features to blocking polygons for this unit
            from ...utility.calcs import get_terrain_blocking_polygons
            terrain_polygons = []
            for terrain_feature in game_map.terrain_features:
                blocking_polygons = get_terrain_blocking_polygons(self, terrain_feature)
                terrain_polygons.extend(blocking_polygons)

            tree = build_spatial_index(terrain_polygons + boundary_repulsors, blocking_models)

            # relax away from any collisions
            for _ in range(relax_iters):
                # build the model's polygon at its trial spot
                base = m.model_base.get_base_shape()
                poly = translate(base,
                                pos[0] - base.centroid.x,
                                pos[1] - base.centroid.y)

                # check for collisions with terrain/enemy/friendly/boundary blockers
                hits = query_spatial_index(tree, poly)
                # if no intersection, we're done
                # DEBUG: Add defensive programming to catch geometry type errors
                try:
                    if not any(poly.intersects(b) for b in hits):
                        break
                except TypeError as e:
                    logger.debug(f"DEBUG: TypeError in single-model intersects check: {e}")
                    logger.debug(f"DEBUG: poly type: {type(poly)}")
                    logger.debug(f"DEBUG: hits count: {len(hits)}")
                    for i, hit in enumerate(hits):
                        logger.debug(f"DEBUG: hit {i}: {type(hit)} - {hit}")
                        if hasattr(hit, 'geom_type'):
                            logger.debug(f"DEBUG:   geom_type: {hit.geom_type}")
                        if hasattr(hit, 'is_valid'):
                            logger.debug(f"DEBUG:   is_valid: {hit.is_valid}")
                    raise

                # repel vector from first blocker
                b = next(b for b in hits if poly.intersects(b))
                vx = poly.centroid.x - b.centroid.x
                vy = poly.centroid.y - b.centroid.y
                norm = get_dist(vx, vy) or 1.0
                pos[0] += (vx / norm) * grid_step
                pos[1] += (vy / norm) * grid_step
                pos[2] = game_map.get_surface_height_for_model(m, pos[0], pos[1])

            # commit and return
            m.set_location(*pos)
            logger.debug(f"DEBUG: Single-model positioning successful")
            return [(pos[0], pos[1], pos[2], pos[3])]

        logger.debug(f"DEBUG: Using multi-model formation templates")
        # SLOW PATH FOR MULTI-MODEL UNITS
        # 1) Build list of blocking models (enemies + optionally friendlies)
        enemy_models = game_map.get_enemy_models(self)
        blocking_models = enemy_models
        logger.debug(f"DEBUG: Found {len(enemy_models)} enemy models")
        
        if avoid_friendly_units:
            # Add friendly models from other units (excluding self)
            friendly_models = []
            for unit in game_map.get_friendly_units(self):
                if unit != self:  # Don't include models from the unit being positioned
                    friendly_models.extend(unit.models)
            blocking_models.extend(friendly_models)
            logger.debug(f"DEBUG: Added {len(friendly_models)} friendly models from other units")
        
        logger.debug(f"DEBUG: Total blocking models: {len(blocking_models)} (enemies: {len(enemy_models)}, friendlies: {len(blocking_models) - len(enemy_models)})")
        
        # 2) Use provided boundary repulsors or default to empty list
        if boundary_repulsors is None:
            boundary_repulsors = []
        
        # 3) Spatial index of terrain + blocking models + boundary repulsors
        # Convert terrain features to blocking polygons for this unit
        from ...utility.calcs import get_terrain_blocking_polygons
        terrain_polygons = []
        for terrain_feature in game_map.terrain_features:
            blocking_polygons = get_terrain_blocking_polygons(self, terrain_feature)
            terrain_polygons.extend(blocking_polygons)

        tree = build_spatial_index(terrain_polygons + boundary_repulsors, blocking_models)

        # 4) Compute safe spacing from the model base shape
        # Use tighter spacing for deployment to allow formations to fit in crowded areas
        # Models can be in base-to-base contact (spacing = 2 * radius) but we allow slightly tighter
        base_radius = self.models[0].model_base.radius[0]
        spacing = 2 * base_radius * 0.8  # 80% of full spacing allows for tighter formations
        logger.debug(f"DEBUG: Computed spacing: {spacing:.2f} inches (base radius: {base_radius:.2f})")

        # 5) Build formation templates
        templates = build_formation_templates(len(self.models), spacing)
        logger.debug(f"DEBUG: Generated {len(templates)} formation templates: {list(templates.keys())}")

        origin_2d = np.array((start_x, start_y), float)

        # 6) Try each template
        for template_name, offsets in templates.items():
            logger.debug(f"DEBUG: Trying template '{template_name}' with {len(offsets)} positions")
            
            # world positions in 2D & then lift to 3D + facing
            world = []
            pts2d = offsets + origin_2d
            for x, y in pts2d:
                z = game_map.get_surface_height_for_model(self.models[len(world)], x, y)
                f = self.calculate_strategic_facing(x, y, game_map)
                world.append([x, y, z, f])

            # Check individual model base collisions instead of unit footprint
            # This allows unit footprints to overlap as long as individual model bases don't overlap
            model_collision_detected = False
            for i, (dx, dy) in enumerate(offsets):
                model_x = origin_2d[0] + dx
                model_y = origin_2d[1] + dy
                
                # Create temporary model base at this position
                temp_model = self.models[i] if i < len(self.models) else self.models[0]
                temp_base = temp_model.model_base.get_base_shape()
                temp_base_positioned = translate(temp_base, 
                                               model_x - temp_base.centroid.x,
                                               model_y - temp_base.centroid.y)
                
                # Check collision with obstacles and enemy models only
                # (friendly unit avoidance is handled by the avoid_friendly_units parameter)
                base_hits = query_spatial_index(tree, temp_base_positioned)
                if len(base_hits) > 0:
                    # Check if any hits are actual overlaps (not just touching)
                    for hit in base_hits:
                        if temp_base_positioned.overlaps(hit):
                            model_collision_detected = True
                            break
                    if model_collision_detected:
                        break
            
            if model_collision_detected:
                logger.debug(f"DEBUG: Template '{template_name}' rejected - model base overlap detected")
                continue

            # Debug: Check if any models are outside battlefield bounds
            models_outside_bounds = 0
            for i, pos in enumerate(world):
                if pos[0] < 0 or pos[0] > game_map.width or pos[1] < 0 or pos[1] > game_map.height:
                    models_outside_bounds += 1

            if models_outside_bounds > 0:
                logger.debug(f"DEBUG: Template '{template_name}' rejected - {models_outside_bounds} models outside battlefield bounds (map: {game_map.width}x{game_map.height})")
                continue

            logger.debug(f"DEBUG: Template '{template_name}' passed footprint check, starting relaxation")

            # Relaxation loop (terrain + self-collisions)
            for relax_iter in range(relax_iters):
                collided = False
                
                # precompute friendly polys at current trial positions
                friendly = []
                for idx, pos in enumerate(world):
                    base = self.models[idx].model_base.get_base_shape()
                    friendly.append(
                        translate(base, 
                                pos[0] - base.centroid.x, 
                                pos[1] - base.centroid.y)
                    )

                for i, pos in enumerate(world):
                    poly_i = friendly[i]
                    # gather blockers as a pure Python list
                    hits = query_spatial_index(tree, poly_i) \
                        + [p for j,p in enumerate(friendly) if j != i]

                    # DEBUG: Add defensive programming to catch geometry type errors
                    try:
                        intersects_any = any(poly_i.intersects(b) for b in hits)
                    except TypeError as e:
                        logger.debug(f"DEBUG: TypeError in multi-model intersects check: {e}")
                        logger.debug(f"DEBUG: poly_i type: {type(poly_i)}")
                        logger.debug(f"DEBUG: hits count: {len(hits)}")
                        for idx, hit in enumerate(hits):
                            logger.debug(f"DEBUG: hit {idx}: {type(hit)} - {hit}")
                            if hasattr(hit, 'geom_type'):
                                logger.debug(f"DEBUG:   geom_type: {hit.geom_type}")
                            if hasattr(hit, 'is_valid'):
                                logger.debug(f"DEBUG:   is_valid: {hit.is_valid}")
                        raise
                    
                    if intersects_any:
                        # repel along the vector between centroids
                        b = next(b for b in hits if poly_i.intersects(b))
                        vx = poly_i.centroid.x - b.centroid.x
                        vy = poly_i.centroid.y - b.centroid.y
                        norm = get_dist(vx, vy) or 1.0
                        pos[0] += (vx / norm) * grid_step
                        pos[1] += (vy / norm) * grid_step
                        pos[2] = game_map.get_surface_height_for_model(self.models[i], pos[0], pos[1])
                        collided = True
                        
                if not collided:
                    logger.debug(f"DEBUG: Template '{template_name}' completed relaxation after {relax_iter + 1} iterations")
                    break
                elif relax_iter == relax_iters - 1:
                    logger.debug(f"DEBUG: Template '{template_name}' still had collisions after {relax_iters} relaxation iterations")

            # after you've cleared collisions...
            attract_iters = 5
            attract_step = 0.2
            target_min = 0.25
            for _ in range(attract_iters):
                moved = False
                for i, m1 in enumerate(self.models):
                    for j, m2 in enumerate(self.models[i+1:], start=i+1):
                        d = m1.model_base.edge_to_edge_distance(m2.model_base)
                        if d > target_min + 1e-6:
                            # move each halfway toward the other
                            dx = (m2.x - m1.x)
                            dy = (m2.y - m1.y)
                            norm = get_dist(dx, dy)
                            shift = min(attract_step, d/2) / norm
                            m1.model_base.x += dx * shift
                            m1.model_base.y += dy * shift
                            m2.model_base.x -= dx * shift
                            m2.model_base.y -= dy * shift
                            moved = True
                if not moved:
                    break

            # Final overlap catcher
            final_polys = []
            for idx, pos in enumerate(world):
                base = self.models[idx].model_base.get_base_shape()
                final_polys.append(
                    translate(base,
                            pos[0] - base.centroid.x,
                            pos[1] - base.centroid.y)
                )

            # if any true-area overlap, reject this template
            ok = True
            for i in range(len(final_polys)):
                for j in range(i+1, len(final_polys)):
                    if final_polys[i].overlaps(final_polys[j]):
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                logger.debug(f"DEBUG: Template '{template_name}' rejected - final overlap check failed")
                continue

            # Commit & coherency-graph check
            for m, pos in zip(self.models, world):
                m.set_location(*pos)
                
            coherency_ok = self.check_coherency_graph()
            logger.debug(f"DEBUG: Template '{template_name}' coherency check: {' PASSED' if coherency_ok else ' FAILED'}")
            
            if coherency_ok:
                logger.debug(f"DEBUG: Successfully found formation using template '{template_name}'")
                return [(x, y, z, f) for x, y, z, f in world]
            else:
                logger.debug(f"DEBUG: Template '{template_name}' rejected - coherency check failed")

        # 7) If none fit, raise or fallback
        logger.debug(f"DEBUG: All {len(templates)} templates failed - no valid formation found")
        # No valid formation found - return None instead of raising exception
        # This allows auto-deployment to try other positions
        return None

    def _create_potential_base(self, x: float, y: float, z: float, facing: float, model: Model = None):
        # Create a new base with the same properties as the specified model's base
        if model is None:
            model = self.models[0]  # Default to first model
        new_base = copy.deepcopy(model.model_base)
        new_base.x, new_base.y, new_base.z = x, y, z
        new_base.set_facing(facing)
        return new_base

    def _collides_with_unit_models(self, x: float, y: float, z: float, facing: float, positions: List[Tuple[float, float, float, float]], model: Model = None) -> bool:
        """Check if the model at the given position collides with any other model in the unit."""
        if not positions:
            return False

        if len(self.models) == 1:
            return False

        new_base = self._create_potential_base(x, y, z, facing, model)

        for i, pos in enumerate(positions):
            # Use the corresponding model for each position
            other_model = self.models[i] if i < len(self.models) else self.models[0]
            other_base = self._create_potential_base(pos[0], pos[1], pos[2], pos[3], other_model)
            if new_base.collides_with(other_base):
                logger.debug(f"Collision detected!")
                return True
        return False

    def _is_coherent_within_unit(self, x: float, y: float, z: float, facing: float, positions: List[Tuple[float, float, float, float]], model: Model = None) -> bool:
        """Check if the model at the given position is within coherency with the unit."""
        new_base = self._create_potential_base(x, y, z, facing, model)

        # Check against already placed models
        found_neighbors = 0
        current_neighbors_needed = 0 if len(positions) == 0 else 1 if len(positions) == 1 else self.required_neighbors

        if current_neighbors_needed == 0:
            return True

        for i, pos in enumerate(positions):
            # Use the corresponding model for each position
            other_model = self.models[i] if i < len(self.models) else self.models[0]
            other_base = self._create_potential_base(pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0, pos[3] if len(pos) > 3 else facing, other_model)
            # 10th ed coherency: <=2" horizontal (base edge-to-edge) AND <=5" vertical (base-to-base)
            try:
                horizontal = new_base.get_base_shape().distance(other_base.get_base_shape())
                vertical = abs(float(getattr(new_base, 'z', 0.0)) - float(getattr(other_base, 'z', 0.0)))
            except Exception:
                horizontal = float('inf')
                vertical = float('inf')
            if horizontal <= self.coherency_distance + 1e-6 and vertical <= 5.0 + 1e-6:
                found_neighbors += 1
                if found_neighbors >= current_neighbors_needed:
                    return True
        return False

    def check_coherency_graph(self):
        """
        Returns True if every model in the unit
        has the required number of neighbors within edge-to-edge
        coherency_distance.

        - Units of 1\u20135 models: each model needs at least 1 neighbor.
        - Units of 6+ models: each model needs at least 2 neighbors.
        """
        models = self.models

        for i, m1 in enumerate(models):
            neighbors = 0
            for j, m2 in enumerate(models):
                if i == j:
                    continue
                # 10th ed coherency: <=2" horizontal (base edge-to-edge) AND <=5" vertical (base-to-base)
                try:
                    horizontal = m1.model_base.get_base_shape().distance(m2.model_base.get_base_shape())
                    vertical = abs(float(getattr(m1.model_base, 'z', 0.0)) - float(getattr(m2.model_base, 'z', 0.0)))
                except Exception:
                    horizontal = float('inf')
                    vertical = float('inf')
                if horizontal <= self.coherency_distance + 1e-6 and vertical <= 5.0 + 1e-6:
                    neighbors += 1
                if neighbors >= self.required_neighbors:
                    break

            if neighbors < self.required_neighbors:
                return False

        return True


    def _is_valid_position(self, x: float, y: float, z: float, facing: float, game_map: 'Map', placed_positions: List[Tuple[float, float, float, float]], model: Model = None) -> bool:
        if model is None:
            model = self.models[0]  # Use the first model as a reference
        if not game_map.is_within_boundary(model, (x, y)):
            return False
        if self._check_collision_with_obstacles_or_terrain(game_map, model, (x, y)):
            return False
        if game_map.check_collision_with_other_friendly_units(model, (x, y)):
            return False
        if game_map.check_collision_with_other_enemy_units(model, (x, y)):
            return False
        if self._collides_with_unit_models(x, y, z, facing, placed_positions, model):
            return False
        if not self._is_coherent_within_unit(x, y, z, facing, placed_positions, model):
            return False
        return True


    ###########################################################################
    ### Range and Line of Sight
    ###########################################################################

    def maximum_range(self) -> int:
        """Maximum range of the unit."""
        if hasattr(self, 'max_shooting_range'):
            return self.max_shooting_range

        max_range = 0
        for model in self.models:
            max_range = max(max_range, model.maximum_range())
        self.max_shooting_range = max_range
        return max_range

    def print_unit(self) -> str:
        return f"{self.name} :: M: {self.movement}\", T: {self.toughness}, Sv: {self.save}, InvSv: {self.inv_save}, OC: {self.objective_control}"

    ###########################################################################
    ### Dunder Methods
    ###########################################################################

    def __str__(self):
        return f"{self.name} ({len(self.models)} models)"

    def __repr__(self):
        return f"Unit(name='{self.name}', models={len(self.models)})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def can_declare_charge_against(self, target_unit: 'Unit', game: 'Game', *, out_of_turn: bool = False) -> bool:
        """Check if this unit can declare a charge against the target unit."""
        if not self.is_alive() or not target_unit.is_alive():
            return False

        if not self._can_declare_charge_base(game, out_of_turn=out_of_turn):
            return False

        # Only FLY units can charge AIRCRAFT.
        try:
            if bool(getattr(target_unit, "is_aircraft", False)) and not bool(getattr(self, "is_flying", False)):
                return False
        except Exception:
            pass
        try:
            army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            target_ok_fn = getattr(sm_mgr, "heresy_undone_target_is_legal", None) if sm_mgr is not None else None
            if callable(target_ok_fn) and not target_ok_fn(self, target_unit, game=game):
                return False
        except Exception:
            pass

        # Cabal of Sorcerers (Temporal Surge): cannot charge until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("cabal_temporal_surge_no_charge_turn_owner"):
                owner = str(sr.get("cabal_temporal_surge_no_charge_turn_owner") or "")
                turn = int(sr.get("cabal_temporal_surge_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    try:
                        if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                            return False
                    except Exception:
                        return False
        except Exception:
            pass

        # Swooping Descent: arriving within 9" denies charges until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_swooping_descent_no_charge_turn_owner"):
                owner = str(sr.get("pain_swooping_descent_no_charge_turn_owner") or "")
                turn = int(sr.get("pain_swooping_descent_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Cloudstrider: cannot charge until end of turn after 6" deep strike option.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("cloudstrider_no_charge_turn_owner"):
                owner = str(sr.get("cloudstrider_no_charge_turn_owner") or "")
                turn = int(sr.get("cloudstrider_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Eternity Gate: cannot charge until end of turn after setup.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("eternity_gate_no_charge_turn_owner"):
                owner = str(sr.get("eternity_gate_no_charge_turn_owner") or "")
                turn = int(sr.get("eternity_gate_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Cosmic Precision: cannot charge until end of turn after 6" Deep Strike option.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("cosmic_precision_no_charge_turn_owner"):
                owner = str(sr.get("cosmic_precision_no_charge_turn_owner") or "")
                turn = int(sr.get("cosmic_precision_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Screaming Descent: cannot charge until end of turn after 6" setup.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("dread_talons_screaming_descent_no_charge_turn_owner"):
                owner = str(sr.get("dread_talons_screaming_descent_no_charge_turn_owner") or "")
                turn = int(sr.get("dread_talons_screaming_descent_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Rapid Manifestation: cannot charge until end of turn after 6" Deep Strike option.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("rapid_manifestation_no_charge_turn_owner"):
                owner = str(sr.get("rapid_manifestation_no_charge_turn_owner") or "")
                turn = int(sr.get("rapid_manifestation_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Combat Manifestation: cannot charge until end of turn after 6" Deep Strike option.
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and sr.get("combat_manifestation_no_charge_turn_owner"):
            owner = str(sr.get("combat_manifestation_no_charge_turn_owner") or "")
            turn_raw = sr.get("combat_manifestation_no_charge_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if owner and game is not None:
                get_current_player = getattr(game, "get_current_player", None)
                current_player = get_current_player() if callable(get_current_player) else None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    current_turn = 0
                if current_owner == owner and current_turn == turn:
                    return False

        # Relic Teleportarium: cannot charge until end of turn after 6" Deep Strike option.
        if isinstance(sr, dict) and sr.get("space_marines_inner_circle_relic_teleportarium_no_charge_turn_owner"):
            owner = str(sr.get("space_marines_inner_circle_relic_teleportarium_no_charge_turn_owner") or "")
            turn_raw = sr.get("space_marines_inner_circle_relic_teleportarium_no_charge_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if owner and game is not None:
                get_current_player = getattr(game, "get_current_player", None)
                current_player = get_current_player() if callable(get_current_player) else None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    current_turn = 0
                if current_owner == owner and current_turn == turn:
                    return False

        # Cloudstrike: cannot charge until end of turn after 6" Deep Strike option.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("cloudstrike_no_charge_turn_owner"):
                owner = str(sr.get("cloudstrike_no_charge_turn_owner") or "")
                turn = int(sr.get("cloudstrike_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Tunnel Crawlers: cannot charge until end of turn after 6" Deep Strike option.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("tunnel_crawlers_no_charge_turn_owner"):
                owner = str(sr.get("tunnel_crawlers_no_charge_turn_owner") or "")
                turn = int(sr.get("tunnel_crawlers_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Fire and Fade: cannot charge until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("fire_and_fade_no_charge_turn_owner"):
                owner = str(sr.get("fire_and_fade_no_charge_turn_owner") or "")
                turn = int(sr.get("fire_and_fade_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Venomous Wrath: cannot charge until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("serpents_brood_venomous_wrath_no_charge_turn_owner"):
                owner = str(sr.get("serpents_brood_venomous_wrath_no_charge_turn_owner") or "")
                turn = int(sr.get("serpents_brood_venomous_wrath_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Tactical Acumen: cannot charge until end of turn after the reactive move.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("tactical_acumen_no_charge_turn_owner"):
                owner = str(sr.get("tactical_acumen_no_charge_turn_owner") or "")
                turn = int(sr.get("tactical_acumen_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # A Foot in the Future: cannot charge until end of turn after the reactive move.
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and sr.get("a_foot_in_the_future_no_charge_turn_owner"):
            owner = str(sr.get("a_foot_in_the_future_no_charge_turn_owner") or "")
            turn_raw = sr.get("a_foot_in_the_future_no_charge_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if owner and game is not None:
                get_current_player = getattr(game, "get_current_player", None)
                current_player = get_current_player() if callable(get_current_player) else None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    current_turn = 0
                if current_owner == owner and current_turn == turn:
                    return False

        # Flickerjump: cannot charge until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("flickerjump_no_charge_turn_owner"):
                owner = str(sr.get("flickerjump_no_charge_turn_owner") or "")
                turn = int(sr.get("flickerjump_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        if not self.has_empyric_ambush():
                            return False
        except Exception:
            pass
            
        if self._thrill_seekers_restriction_reason(target_unit, game):
            return False
        
        # Check if target is within maximum charge range (2D6 = max 12")
        distance = game.map.get_distance_between_units(self, target_unit)
        max_distance = self.max_charge_distance
        getter = getattr(game, "get_max_charge_distance", None) if game is not None else None
        if callable(getter):
            max_distance = float(getter(self, target_unit=target_unit))
        if distance > max_distance:
            return False
            
        # Check if there's a clear charge path
        # This is simplified - in real 40k you can charge around terrain
        if game.map.is_path_blocked(self, target_unit):
            return False
            
        return True

    def _can_declare_charge_base(self, game: 'Game', *, out_of_turn: bool = False) -> bool:
        if not self.is_alive():
            return False
        if bool(getattr(self, "is_aircraft", False)):
            return False
        if self.round_state.attempted_charge_this_round and not out_of_turn:
            return False
        if self.round_state.advanced_this_round and not self.can_charge_after_advance():
            return False
        if getattr(self.round_state, "disembarked_cannot_charge", False):
            return False
        if getattr(self.round_state, "disembarked_from_destroyed_transport", False):
            return False
        if self.round_state.fell_back_this_round and not self.can_charge_after_fall_back():
            return False
        if getattr(self.round_state, 'action_locked_until_turn_end', False):
            return False
        if self.arrived_from_reserves_this_turn and not self.can_charge_after_arriving_from_reserves():
            return False

        # Units within Engagement Range of any enemy cannot declare charges.
        try:
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
        if game_map is not None:
            try:
                enemy_units = list(game_map.get_enemy_units(self) or [])
            except Exception:
                enemy_units = []
            for enemy in enemy_units:
                if not getattr(enemy, "is_alive", False):
                    continue
                if game_map.is_within_engagement_range(self, enemy):
                    return False
        return True

    def can_declare_charge(self, game: 'Game', *, out_of_turn: bool = False) -> bool:
        """Check if this unit is eligible to declare any charge this phase."""
        if not self._can_declare_charge_base(game, out_of_turn=out_of_turn):
            return False
        try:
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
        if game_map is None:
            return False
        enemy_units = [u for u in game_map.get_enemy_units(self) if u.is_alive()]
        if not enemy_units:
            return False
        max_distance = float(getattr(self, "max_charge_distance", 0) or 0)
        getter = getattr(game, "get_max_charge_distance", None)
        if callable(getter):
            max_distance = float(getter(self, target_unit=None))
        sycophantic_active_fn = getattr(self, "_carnival_sycophantic_surge_active_for_charge", None)
        sycophantic_target_fn = getattr(self, "_carnival_sycophantic_target_condition_met", None)
        sycophantic_active = bool(callable(sycophantic_active_fn) and sycophantic_active_fn(game=game))
        if sycophantic_active and not callable(sycophantic_target_fn):
            return False
        for enemy in enemy_units:
            try:
                if game_map.get_distance_between_units(self, enemy) > max_distance:
                    continue
                if sycophantic_active and not bool(sycophantic_target_fn(enemy, game)):
                    continue
                return True
            except Exception:
                continue
        return False

    def validate_charge_end_state(self, target_units: list['Unit'], game_map: 'Map') -> tuple[bool, str]:
        """Validate charge end position against declared targets and non-targets."""
        if not target_units:
            return False, "Charge requires at least one target"
        target_ids = {get_entity_id(u) for u in list(target_units or []) if u is not None}
        missing = []
        for target in target_units:
            if target is None or not getattr(target, "is_alive", False):
                missing.append(getattr(target, "name", "Unknown"))
                continue
            if not game_map.is_within_engagement_range(self, target):
                missing.append(getattr(target, "name", "Unknown"))
        if missing:
            return False, f"Charge must end within Engagement Range of all targets (missing: {', '.join(missing)})"
        # Cannot end within Engagement Range of non-target enemy units.
        for enemy in list(game_map.get_enemy_units(self) or []):
            if enemy is None or not getattr(enemy, "is_alive", False):
                continue
            if get_entity_id(enemy) in target_ids:
                continue
            if game_map.is_within_engagement_range(self, enemy):
                return False, f"Charge cannot end within Engagement Range of non-target unit {enemy.name}"
        return True, ""

    def get_threat_value(self) -> float:
        """Calculate the total threat value of this unit."""
        ranged_threat, melee_threat = self.get_threat_level()
        return ranged_threat + melee_threat

    def get_overwatch_risk(self, charging_unit: 'Unit', game: 'Game') -> float:
        """Calculate the risk this unit poses in overwatch to a charging unit.
        
        Args:
            charging_unit (Unit): The unit attempting to charge
            game (Game): The game instance for distance calculations
            
        Returns:
            float: Risk value from 0.0 to 1.0, where higher values indicate more risk
        """
        # Base risk on our ranged threat level
        ranged_threat, _ = self.get_threat_level()
        
        # Modify based on distance (closer = more dangerous)
        distance = game.get_distance_between_units(charging_unit, self)
        distance_modifier = 1.0 / max(distance, 1.0)  # Avoid division by zero
        
        # Consider if we've already shot this round
        if self.round_state.shot_this_round:
            ranged_threat *= 0.5  # Reduced effectiveness if already shot
            
        # Consider remaining CP for stratagems
        army = self.get_parent_army()
        if army and army.player:
            cp_modifier = min(1.0, army.player.command_points / 3.0)  # Scale based on available CP
            ranged_threat *= (1.0 + cp_modifier)  # More CP = more potential threats
        
        return ranged_threat * distance_modifier
    
    def _get_cached_ability_trait_index(self) -> dict:
        """
        Return generation-scoped parsed ability trait index for this attached-unit root.

        The index is parse-once per structure generation and reused for high-frequency
        trait checks and pattern searches.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            root = self
        cache = getattr(root, "_ability_cache", None)
        if not isinstance(cache, dict):
            root._ability_cache = {}
            cache = root._ability_cache

        generation = int(getattr(root, "_ability_structure_generation", 0) or 0)
        cache_key = "ability_trait_index_v1"
        cached = cache.get(cache_key)
        if isinstance(cached, dict) and int(cached.get("generation", -1) or -1) == generation:
            return cached

        entries: list[tuple[str, str]] = []
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit in members:
            if unit is None:
                continue
            # Unit-level abilities
            for ability in list(getattr(unit, "possible_abilities", []) or []):
                if isinstance(ability, str):
                    entries.append((ability, ability))
                    continue
                entries.append(
                    (
                        str(getattr(ability, "name", "") or ""),
                        str(getattr(ability, "description", "") or ""),
                    )
                )
            # Enhancement text
            enh = getattr(unit, "enhancement", None)
            if enh is not None:
                entries.append(
                    (
                        str(getattr(enh, "name", "") or ""),
                        str(getattr(enh, "description", "") or ""),
                    )
                )
            # Model-level ability objects
            for model in list(getattr(unit, "models", []) or []):
                abilities = getattr(model, "abilities", None)
                if not isinstance(abilities, dict):
                    continue
                for ability in abilities.values():
                    if isinstance(ability, str):
                        entries.append((ability, ability))
                        continue
                    entries.append(
                        (
                            str(getattr(ability, "name", "") or ""),
                            str(getattr(ability, "description", "") or ""),
                        )
                    )

        texts: list[str] = []
        seen: set[str] = set()
        for name, desc in entries:
            for raw in (name, desc):
                text_src = str(raw or "")
                if not text_src:
                    continue
                try:
                    cleaned = self._strip_eligibility_prefix(text_src)
                except Exception:
                    cleaned = text_src
                try:
                    normalized = self._normalize_rules_text(cleaned)
                except Exception:
                    normalized = str(cleaned or "")
                normalized = str(normalized or "").strip().lower()
                if not normalized:
                    continue
                if normalized in seen:
                    continue
                seen.add(normalized)
                texts.append(normalized)

        joined = "\n".join(texts)
        firing_deck_value = 0
        for text in texts:
            match = re.search(r"firing\s+deck\s*\(?(\d+)", str(text or ""), flags=re.IGNORECASE)
            if not match:
                continue
            try:
                firing_deck_value = max(firing_deck_value, int(match.group(1) or 0))
            except Exception:
                continue
        trait_flags = {
            "super_heavy_walker": bool(
                "super-heavy walker" in joined
                or "super-heavy war engine" in joined
                or "super heavy war engine" in joined
            ),
            "flip_belt": bool("flip belt" in joined),
            "kill_team": bool("kill team" in joined),
            "stealth": bool("stealth" in joined),
            "infiltrate": bool("infiltrators" in joined or "infiltrate" in joined),
            "deep_strike": bool("deep strike" in joined or "deepstrike" in joined),
            "firing_deck": bool("firing deck" in joined),
        }

        index = {
            "generation": generation,
            "texts": tuple(texts),
            "joined": joined,
            "trait_flags": trait_flags,
            "trait_values": {"firing_deck": int(firing_deck_value)},
            "pattern_hits": {},
            "pattern_values": {},
        }
        cache[cache_key] = index
        return index

    def _trait_flag(self, key: str, *, default: bool = False) -> bool:
        if not key:
            return bool(default)
        index = self._get_cached_ability_trait_index()
        trait_flags = index.get("trait_flags", {}) if isinstance(index, dict) else {}
        return bool(trait_flags.get(key, default))

    def _trait_value(self, key: str, *, default: int = 0) -> int:
        if not key:
            return int(default)
        index = self._get_cached_ability_trait_index()
        trait_values = index.get("trait_values", {}) if isinstance(index, dict) else {}
        try:
            return int(trait_values.get(key, default) or 0)
        except Exception:
            return int(default)


    def _find_ability_with_patterns(self, patterns: List[str], extract_value: bool = False, value_pattern: str = None) -> Tuple[bool, Optional[str]]:
        r"""
        Helper method to find abilities matching given patterns and optionally extract values.

        Args:
            patterns: List of patterns to search for (case-insensitive)
            extract_value: Whether to extract a value from the matched text
            value_pattern: Regex pattern to extract value (e.g., r'(\d+)' for numbers, r'(\d+|D\d+)' for dice)

        Returns:
            Tuple[bool, Optional[str]]: (found, extracted_value)
        """
        try:
            from ...utility.regex_hotspot_metrics import increment as _increment_regex_hotspot

            _increment_regex_hotspot("positioning_mixin:_find_ability_with_patterns")
        except Exception:
            pass

        pattern_lowers = tuple(
            str(pattern or "").strip().lower()
            for pattern in (patterns or [])
            if str(pattern or "").strip()
        )
        if not pattern_lowers:
            return False, None

        # Fast path: parse-once indexed lookup for known high-frequency traits.
        indexed_patterns = {
            "super-heavy walker",
            "super-heavy war engine",
            "super heavy war engine",
            "flip belt",
            "kill team",
            "firing deck",
        }
        can_use_index = all(pattern in indexed_patterns for pattern in pattern_lowers)
        if can_use_index and (not extract_value or pattern_lowers == ("firing deck",)):
            try:
                index = self._get_cached_ability_trait_index()
                pattern_hits = index.get("pattern_hits", {})
                pattern_values = index.get("pattern_values", {})
                index_key = (pattern_lowers, bool(extract_value), str(value_pattern or ""))
                if index_key in pattern_hits:
                    return bool(pattern_hits.get(index_key)), pattern_values.get(index_key)

                texts = tuple(index.get("texts", ()) or ())
                found = False
                value = None
                if extract_value and value_pattern:
                    matchers = tuple(
                        re.compile(rf"{re.escape(pattern)}\s*\(?{value_pattern}")
                        for pattern in pattern_lowers
                    )
                else:
                    matchers = tuple()
                for text in texts:
                    low = str(text or "").lower()
                    for idx, pattern in enumerate(pattern_lowers):
                        if pattern not in low:
                            continue
                        found = True
                        if not matchers:
                            break
                        match = matchers[idx].search(low)
                        if match:
                            value = match.group(1)
                            break
                    if found and (not matchers or value is not None):
                        break

                # Only commit extract-value indexed hits when value was parsed.
                if found and extract_value and value is None:
                    pass
                else:
                    pattern_hits[index_key] = bool(found)
                    if found and value is not None:
                        pattern_values[index_key] = value
                    elif index_key in pattern_values:
                        pattern_values.pop(index_key, None)
                    index["pattern_hits"] = pattern_hits
                    index["pattern_values"] = pattern_values
                    return bool(found), value
            except Exception:
                pass

        value_matchers: tuple[tuple[str, "re.Pattern"], ...] = tuple()
        if extract_value and value_pattern:
            value_matchers = tuple(
                (pattern, re.compile(rf"{re.escape(pattern)}\s*\(?{value_pattern}"))
                for pattern in pattern_lowers
            )

        def _scan_text(text: str, *, context: str, parameter_text: Optional[str] = None) -> Tuple[bool, Optional[str]]:
            low = str(text or "").lower()
            for idx, pattern in enumerate(pattern_lowers):
                if pattern not in low:
                    continue
                if not value_matchers:
                    return True, None
                matcher = value_matchers[idx][1]
                match = matcher.search(low)
                if match:
                    return True, match.group(1)
                if parameter_text:
                    param_match = re.search(value_pattern, str(parameter_text))
                    if param_match:
                        return True, param_match.group(1)
                raise ValueError(
                    f"{pattern} ability found in {context} but could not extract value for unit '{self.name}'"
                )
            return False, None

        # Check keywords first
        for keyword in (self.keywords or []):
            found, value = _scan_text(str(keyword), context=f"keyword '{keyword}'")
            if found:
                return True, value

        # Check unit-level abilities (possible_abilities)
        for ability in self._iter_active_possible_abilities():
            if isinstance(ability, str):
                for segment in self._iter_conditioned_text_segments(ability):
                    found, value = _scan_text(segment, context=f"ability string '{ability}'")
                    if found:
                        return True, value
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, "name") and ability.name:
                    name_text = str(ability.name)
                    name_low = name_text.lower()
                    ability_name_matched = any(pattern in name_low for pattern in pattern_lowers)
                    if ability_name_matched:
                        parameter_text = str(getattr(ability, "parameter", "") or "")
                        found, value = _scan_text(
                            name_text,
                            context=f"ability name '{ability.name}'",
                            parameter_text=parameter_text,
                        )
                        if found:
                            return True, value

                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, "description") and ability.description:
                    for segment in self._iter_conditioned_text_segments(ability.description):
                        found, value = _scan_text(
                            segment,
                            context=f"ability description '{ability.description}'",
                        )
                        if found:
                            return True, value

        # Check model-level abilities
        for ability in self.abilities:
            try:
                if not self._ability_is_active(ability):
                    continue
            except Exception:
                pass
            if isinstance(ability, str):
                for segment in self._iter_conditioned_text_segments(ability):
                    found, value = _scan_text(segment, context=f"model ability string '{ability}'")
                    if found:
                        return True, value
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, "name") and ability.name:
                    name_text = str(ability.name)
                    name_low = name_text.lower()
                    ability_name_matched = any(pattern in name_low for pattern in pattern_lowers)
                    if ability_name_matched:
                        parameter_text = str(getattr(ability, "parameter", "") or "")
                        found, value = _scan_text(
                            name_text,
                            context=f"model ability name '{ability.name}'",
                            parameter_text=parameter_text,
                        )
                        if found:
                            return True, value

                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, "description") and ability.description:
                    for segment in self._iter_conditioned_text_segments(ability.description):
                        found, value = _scan_text(
                            segment,
                            context=f"model ability description '{ability.description}'",
                        )
                        if found:
                            return True, value

        return False, None

    def has_deep_strike(self) -> bool:
        """Check if the unit has Deep Strike ability."""
        # Use cached result if available
        if 'deep_strike' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['deep_strike']

        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict):
                if sr.get("bearer_unit_deep_strike") or sr.get("realm_of_chaos_temp_deep_strike"):
                    found = True
                elif sr.get("attached_unit_bodyguard_leader_deep_strike") and bool(
                    getattr(self, "is_attached_leader", False)
                ):
                    found = True
                elif sr.get("enhancement_warp_borne_stalker"):
                    bearer_id = str(
                        sr.get("enhancement_warp_borne_stalker_bearer_model_id", "")
                        or sr.get("enhancement_bearer_model_id", "")
                        or ""
                    ).strip()
                    if not bearer_id:
                        found = True
                    else:
                        for model in list(getattr(self, "models", []) or []):
                            model_id = str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "")
                            if model_id != bearer_id:
                                continue
                            alive_attr = getattr(model, "is_alive", True)
                            found = bool(alive_attr() if callable(alive_attr) else alive_attr)
                            break
                elif sr.get("cloudstrike_temp_deep_strike"):
                    found = True
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    owner_id = str(sr.get("cloudstrike_turn_owner", "") or "")
                    turn = int(sr.get("cloudstrike_turn", 0) or 0)
                    exp_phase = str(sr.get("cloudstrike_expires_phase", "") or "").strip().upper()
                    if game is not None:
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        if owner_id and cur_owner and owner_id != cur_owner:
                            found = False
                        elif turn and cur_turn and turn != cur_turn:
                            found = False
                        elif exp_phase and cur_phase and exp_phase != cur_phase:
                            found = False
                elif sr.get("dread_talons_screaming_descent_temp_deep_strike"):
                    found = True
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    owner_id = str(sr.get("dread_talons_screaming_descent_turn_owner", "") or "")
                    turn = int(sr.get("dread_talons_screaming_descent_turn", 0) or 0)
                    exp_phase = str(sr.get("dread_talons_screaming_descent_phase", "") or "").strip().upper()
                    if game is not None:
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        if owner_id and cur_owner and owner_id != cur_owner:
                            found = False
                        elif turn and cur_turn and turn != cur_turn:
                            found = False
                        elif exp_phase and cur_phase and exp_phase != cur_phase:
                            found = False
                elif sr.get("dark_apparitions_temp_deep_strike"):
                    found = True
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    owner_id = str(sr.get("dark_apparitions_turn_owner", "") or "")
                    exp_phase = str(sr.get("dark_apparitions_expires_phase", "") or "").strip().upper()
                    if game is not None:
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        if owner_id and cur_owner and owner_id != cur_owner:
                            found = False
                        elif exp_phase and cur_phase and exp_phase != cur_phase:
                            found = False
                elif sr.get("midgame_temp_deep_strike"):
                    found = True
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    owner_id = str(sr.get("midgame_temp_deep_strike_turn_owner", "") or "")
                    turn = int(sr.get("midgame_temp_deep_strike_must_arrive_turn", 0) or 0)
                    if game is not None:
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        if owner_id and cur_owner and owner_id != cur_owner:
                            found = False
                        elif turn and cur_turn and turn != cur_turn:
                            found = False
                elif sr.get("umbralefic_crystal_temp_deep_strike"):
                    found = True
                    try:
                        army = self.get_parent_army()
                    except Exception:
                        army = None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    owner_id = str(sr.get("umbralefic_crystal_must_arrive_turn_owner", "") or "")
                    turn = int(sr.get("umbralefic_crystal_must_arrive_turn", 0) or 0)
                    if game is not None:
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        if owner_id and cur_owner and owner_id != cur_owner:
                            found = False
                        elif turn and cur_turn and turn != cur_turn:
                            found = False
        except Exception:
            pass
        if not found:
            try:
                if self._disciple_of_khorne_active():
                    found = True
            except Exception:
                found = False
        if not found:
            try:
                if self._fury_from_the_delve_active():
                    found = True
            except Exception:
                found = False
        if not found:
            try:
                if self._root_has_attached_unit_deep_strike_grant():
                    found = True
            except Exception:
                found = False
        if not found:
            if (
                self._first_prince_of_chaos_active()
                and self._is_chaos_undivided()
                and self.has_any_keyword("HERETIC ASTARTES")
            ):
                found = True
            else:
                found, _ = self._find_ability_with_patterns(["deep strike", "deepstrike"])

        # Attached units can only Deep Strike if every model has Deep Strike.
        # If an active rule grants Deep Strike to "models in this/that unit",
        # the grant applies across the attached unit and this per-member check is skipped.
        try:
            root_grants_attached_deep_strike = False
            if found:
                try:
                    root_grants_attached_deep_strike = bool(self._root_has_attached_unit_deep_strike_grant())
                except Exception:
                    root_grants_attached_deep_strike = False
            if (
                found
                and not root_grants_attached_deep_strike
                and (not bool(getattr(self, "is_leader", False)) or getattr(self, "attached_to", None) is None)
            ):
                root = self.get_attached_unit_root()
                leaders = list(getattr(root, "attached_leaders", []) or [])
                for leader in leaders:
                    try:
                        if not leader.has_deep_strike():
                            found = False
                            break
                    except Exception:
                        found = False
                        break
        except Exception:
            pass
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['deep_strike'] = found
        
        return found

    def _root_has_attached_unit_deep_strike_grant(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        try:
            sr_root = getattr(root, "special_rules", None)
            if isinstance(sr_root, dict) and bool(sr_root.get("bearer_unit_deep_strike")):
                return True
        except Exception:
            pass
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = []
        if members:
            for member in members:
                if member is None:
                    continue
                sr_member = getattr(member, "special_rules", None)
                if isinstance(sr_member, dict) and bool(sr_member.get("bearer_unit_deep_strike")):
                    return True
        text_grant_re = re.compile(
            r"models\s+in\s+(?:this|that|the\s+bearer'?s|this\s+model'?s)\s+unit\s+have\s+the\s+deep\s+strike\b",
            re.IGNORECASE,
        )
        abilities = list(getattr(root, "possible_abilities", []) or []) + list(getattr(root, "abilities", []) or [])
        for ability in abilities:
            try:
                checker = getattr(root, "_ability_is_active", None)
                if callable(checker) and not bool(checker(ability)):
                    continue
            except Exception:
                continue
            try:
                if isinstance(ability, str):
                    text = ability
                else:
                    text = str(getattr(ability, "description", "") or getattr(ability, "name", "") or "")
            except Exception:
                continue
            normalized = root._normalize_rules_text(text or "")
            if normalized and text_grant_re.search(normalized):
                return True
        return False

    def get_deep_strike_min_distance_override(self) -> Optional[float]:
        """
        Return an override for the minimum enemy distance when using Deep Strike, if applicable.

        Currently supports:
        - Power from Pain (Swooping Descent) min distance
        - Cloudstrider (Baharroth) min distance when chosen for the current turn
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None
        min_dist: Optional[float] = None
        try:
            pain_min = float(sr.get("pain_deep_strike_min_distance", 0) or 0)
            if pain_min > 0:
                min_dist = pain_min if min_dist is None else min(min_dist, pain_min)
        except Exception:
            pass

        try:
            cloud_min = float(sr.get("cloudstrider_deep_strike_min_distance", 0) or 0)
        except Exception:
            cloud_min = 0.0
        if cloud_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("cloudstrider_choice_turn_owner", "") or "")
                turn = int(sr.get("cloudstrider_choice_turn", 0) or 0)
                if game is not None and owner_id:
                    if str(getattr(game.get_current_player(), "id", "") or "") != owner_id:
                        cloud_min = 0.0
                    elif int(getattr(game, "turn", 0) or 0) != turn:
                        cloud_min = 0.0
            except Exception:
                cloud_min = 0.0
            if cloud_min > 0:
                min_dist = cloud_min if min_dist is None else min(min_dist, cloud_min)

        try:
            cosmic_min = float(sr.get("cosmic_precision_deep_strike_min_distance", 0) or 0)
        except Exception:
            cosmic_min = 0.0
        if cosmic_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("cosmic_precision_turn_owner", "") or "")
                turn = int(sr.get("cosmic_precision_turn", 0) or 0)
                exp = str(sr.get("cosmic_precision_expires_phase", "") or "").strip().upper()
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        cosmic_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        cosmic_min = 0.0
                    elif exp and pname and exp != pname:
                        cosmic_min = 0.0
            except Exception:
                cosmic_min = 0.0
            if cosmic_min > 0:
                min_dist = cosmic_min if min_dist is None else min(min_dist, cosmic_min)

        try:
            screaming_descent_min = float(sr.get("dread_talons_screaming_descent_deep_strike_min_distance", 0) or 0)
        except Exception:
            screaming_descent_min = 0.0
        if screaming_descent_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("dread_talons_screaming_descent_turn_owner", "") or "")
                turn = int(sr.get("dread_talons_screaming_descent_turn", 0) or 0)
                exp = str(sr.get("dread_talons_screaming_descent_phase", "") or "").strip().upper()
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        screaming_descent_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        screaming_descent_min = 0.0
                    elif exp and pname and exp != pname:
                        screaming_descent_min = 0.0
            except Exception:
                screaming_descent_min = 0.0
            if screaming_descent_min > 0:
                min_dist = (
                    screaming_descent_min
                    if min_dist is None
                    else min(min_dist, screaming_descent_min)
                )

        try:
            cloudstrike_min = float(sr.get("cloudstrike_deep_strike_min_distance", 0) or 0)
        except Exception:
            cloudstrike_min = 0.0
        if cloudstrike_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("cloudstrike_turn_owner", "") or "")
                turn = int(sr.get("cloudstrike_turn", 0) or 0)
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    exp = str(sr.get("cloudstrike_expires_phase", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        cloudstrike_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        cloudstrike_min = 0.0
                    elif exp and pname and exp != pname:
                        cloudstrike_min = 0.0
            except Exception:
                cloudstrike_min = 0.0
            if cloudstrike_min > 0:
                min_dist = cloudstrike_min if min_dist is None else min(min_dist, cloudstrike_min)

        try:
            tunnel_crawlers_min = float(sr.get("tunnel_crawlers_deep_strike_min_distance", 0) or 0)
        except Exception:
            tunnel_crawlers_min = 0.0
        if tunnel_crawlers_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("tunnel_crawlers_turn_owner", "") or "")
                turn = int(sr.get("tunnel_crawlers_turn", 0) or 0)
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    exp = str(sr.get("tunnel_crawlers_expires_phase", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        tunnel_crawlers_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        tunnel_crawlers_min = 0.0
                    elif exp and pname and exp != pname:
                        tunnel_crawlers_min = 0.0
            except Exception:
                tunnel_crawlers_min = 0.0
            if tunnel_crawlers_min > 0:
                min_dist = tunnel_crawlers_min if min_dist is None else min(min_dist, tunnel_crawlers_min)

        try:
            denizens_min = float(sr.get("denizens_deep_strike_min_distance", 0) or 0)
        except Exception:
            denizens_min = 0.0
        if denizens_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("denizens_deep_strike_turn_owner", "") or "")
                turn = int(sr.get("denizens_deep_strike_turn", 0) or 0)
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    exp = str(sr.get("denizens_deep_strike_expires_phase", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        denizens_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        denizens_min = 0.0
                    elif exp and pname and exp != pname:
                        denizens_min = 0.0
            except Exception:
                denizens_min = 0.0
            if denizens_min > 0:
                min_dist = denizens_min if min_dist is None else min(min_dist, denizens_min)

        try:
            rapid_min = float(sr.get("rapid_manifestation_deep_strike_min_distance", 0) or 0)
        except Exception:
            rapid_min = 0.0
        if rapid_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("rapid_manifestation_turn_owner", "") or "")
                turn = int(sr.get("rapid_manifestation_turn", 0) or 0)
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    exp = str(sr.get("rapid_manifestation_expires_phase", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        rapid_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        rapid_min = 0.0
                    elif exp and pname and exp != pname:
                        rapid_min = 0.0
            except Exception:
                rapid_min = 0.0
            if rapid_min > 0:
                min_dist = rapid_min if min_dist is None else min(min_dist, rapid_min)

        try:
            combat_manifestation_min = float(sr.get("combat_manifestation_deep_strike_min_distance", 0) or 0)
        except (TypeError, ValueError):
            combat_manifestation_min = 0.0
        if combat_manifestation_min > 0:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            game = getattr(getattr(army, "player", None), "game", None)
            owner_id = str(sr.get("combat_manifestation_deep_strike_turn_owner", "") or "")
            turn_raw = sr.get("combat_manifestation_deep_strike_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if game is not None:
                try:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    cur_turn = 0
                get_current_player = getattr(game, "get_current_player", None)
                cur_player = get_current_player() if callable(get_current_player) else None
                cur_owner = str(getattr(cur_player, "id", "") or "")
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                exp = str(sr.get("combat_manifestation_deep_strike_expires_phase", "") or "").strip().upper()
                if owner_id and cur_owner and owner_id != cur_owner:
                    combat_manifestation_min = 0.0
                elif turn and cur_turn and turn != cur_turn:
                    combat_manifestation_min = 0.0
                elif exp and pname and exp != pname:
                    combat_manifestation_min = 0.0
            if combat_manifestation_min > 0:
                min_dist = (
                    combat_manifestation_min
                    if min_dist is None
                    else min(min_dist, combat_manifestation_min)
                )

        try:
            relic_teleportarium_min = float(
                sr.get("space_marines_inner_circle_relic_teleportarium_deep_strike_min_distance", 0) or 0
            )
        except (TypeError, ValueError):
            relic_teleportarium_min = 0.0
        if relic_teleportarium_min > 0:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            game = getattr(getattr(army, "player", None), "game", None)
            owner_id = str(sr.get("space_marines_inner_circle_relic_teleportarium_deep_strike_turn_owner", "") or "")
            turn_raw = sr.get("space_marines_inner_circle_relic_teleportarium_deep_strike_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if game is not None:
                try:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    cur_turn = 0
                get_current_player = getattr(game, "get_current_player", None)
                cur_player = get_current_player() if callable(get_current_player) else None
                cur_owner = str(getattr(cur_player, "id", "") or "")
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                exp = str(sr.get("space_marines_inner_circle_relic_teleportarium_deep_strike_expires_phase", "") or "").strip().upper()
                if owner_id and cur_owner and owner_id != cur_owner:
                    relic_teleportarium_min = 0.0
                elif turn and cur_turn and turn != cur_turn:
                    relic_teleportarium_min = 0.0
                elif exp and pname and exp != pname:
                    relic_teleportarium_min = 0.0
            if relic_teleportarium_min > 0:
                min_dist = (
                    relic_teleportarium_min
                    if min_dist is None
                    else min(min_dist, relic_teleportarium_min)
                )

        try:
            angelic_host_min = float(
                sr.get("space_marines_angelic_host_descent_of_angels_deep_strike_min_distance", 0) or 0
            )
        except (TypeError, ValueError):
            angelic_host_min = 0.0
        if angelic_host_min > 0:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            game = getattr(getattr(army, "player", None), "game", None)
            owner_id = str(sr.get("space_marines_angelic_host_descent_of_angels_turn_owner", "") or "")
            turn_raw = sr.get("space_marines_angelic_host_descent_of_angels_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if game is not None:
                try:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    cur_turn = 0
                get_current_player = getattr(game, "get_current_player", None)
                cur_player = get_current_player() if callable(get_current_player) else None
                cur_owner = str(getattr(cur_player, "id", "") or "")
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                exp = str(sr.get("space_marines_angelic_host_descent_of_angels_expires_phase", "") or "").strip().upper()
                if owner_id and cur_owner and owner_id != cur_owner:
                    angelic_host_min = 0.0
                elif turn and cur_turn and turn != cur_turn:
                    angelic_host_min = 0.0
                elif exp and pname and exp != pname:
                    angelic_host_min = 0.0
            if angelic_host_min > 0:
                min_dist = angelic_host_min if min_dist is None else min(min_dist, angelic_host_min)

        try:
            hallowed_beacon_min = float(sr.get("hallowed_beacon_deep_strike_min_distance", 0) or 0)
        except Exception:
            hallowed_beacon_min = 0.0
        if hallowed_beacon_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("hallowed_beacon_turn_owner", "") or "")
                turn = int(sr.get("hallowed_beacon_turn", 0) or 0)
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    exp = str(sr.get("hallowed_beacon_expires_phase", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        hallowed_beacon_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        hallowed_beacon_min = 0.0
                    elif exp and pname and exp != pname:
                        hallowed_beacon_min = 0.0
            except Exception:
                hallowed_beacon_min = 0.0
            if hallowed_beacon_min > 0:
                min_dist = hallowed_beacon_min if min_dist is None else min(min_dist, hallowed_beacon_min)

        try:
            gift_of_the_prescient_min = float(sr.get("gift_of_the_prescient_deep_strike_min_distance", 0) or 0)
        except (TypeError, ValueError):
            gift_of_the_prescient_min = 0.0
        if gift_of_the_prescient_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                if game is not None:
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    expires_phase = str(sr.get("gift_of_the_prescient_expires_phase", "") or "").strip().upper()
                    if expires_phase and phase_name and expires_phase != phase_name:
                        gift_of_the_prescient_min = 0.0
            except Exception:
                gift_of_the_prescient_min = 0.0
            if gift_of_the_prescient_min > 0:
                min_dist = (
                    gift_of_the_prescient_min
                    if min_dist is None
                    else min(min_dist, gift_of_the_prescient_min)
                )

        try:
            dark_apparitions_min = float(sr.get("dark_apparitions_deep_strike_min_distance", 0) or 0)
        except Exception:
            dark_apparitions_min = 0.0
        if dark_apparitions_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("dark_apparitions_turn_owner", "") or "")
                if game is not None:
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    exp = str(sr.get("dark_apparitions_expires_phase", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        dark_apparitions_min = 0.0
                    elif exp and pname and exp != pname:
                        dark_apparitions_min = 0.0
            except Exception:
                dark_apparitions_min = 0.0
            if dark_apparitions_min > 0:
                min_dist = dark_apparitions_min if min_dist is None else min(min_dist, dark_apparitions_min)

        return float(min_dist) if min_dist is not None else None

    def get_dark_apparitions_friendly_distance_requirement(self, *, game=None) -> Optional[float]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None
        try:
            required = float(sr.get("dark_apparitions_requires_emperors_children_within", 0) or 0)
        except Exception:
            required = 0.0
        if required <= 0:
            return None
        gm = game
        if gm is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            gm = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        if gm is not None:
            owner_id = str(sr.get("dark_apparitions_turn_owner", "") or "")
            exp_phase = str(sr.get("dark_apparitions_expires_phase", "") or "").strip().upper()
            try:
                cur_player = getattr(gm, "get_current_player", lambda: None)()
                cur_owner = str(getattr(cur_player, "id", "") or "")
            except Exception:
                cur_owner = ""
            try:
                cur_phase = str(getattr(getattr(gm, "phase", None), "name", "") or "").strip().upper()
            except Exception:
                cur_phase = ""
            if owner_id and cur_owner and owner_id != cur_owner:
                return None
            if exp_phase and cur_phase and exp_phase != cur_phase:
                return None
        return float(required)

    def is_dark_apparitions_arrival_valid(
        self,
        prospective_positions: list[tuple[float, float, float, float]],
        *,
        game=None,
        game_map=None,
    ) -> bool:
        required = self.get_dark_apparitions_friendly_distance_requirement(game=game)
        if required is None:
            return True
        if not prospective_positions:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        gm = game_map
        if gm is None and game is not None:
            gm = getattr(game, "map", None)
        if gm is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            try:
                gm = getattr(getattr(getattr(army, "player", None), "game", None), "map", None)
            except Exception:
                gm = None
        if gm is None:
            return False
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return False
        player = getattr(army, "player", None)
        if player is None:
            return False
        mgr = getattr(army, "emperors_children", None)
        checker = getattr(mgr, "is_emperors_children_unit", None) if mgr is not None else None

        def _is_emperors_children_unit(unit_obj) -> bool:
            if unit_obj is None:
                return False
            if callable(checker):
                try:
                    return bool(checker(unit_obj))
                except Exception:
                    return False
            try:
                if unit_obj.has_keyword("EMPEROR'S CHILDREN"):
                    return True
            except Exception:
                pass
            try:
                if unit_obj.has_any_keyword("EMPEROR'S CHILDREN"):
                    return True
            except Exception:
                pass
            return False

        from ...utility.aura_utils import horizontal_distance_between_bases_2d

        unit_id = str(get_entity_id(root) or "")
        friendly_model_bases: list[Any] = []
        seen: set[str] = set()
        for unit_obj in list(getattr(gm, "units", []) or []):
            try:
                friendly_root = unit_obj.get_attached_unit_root() if hasattr(unit_obj, "get_attached_unit_root") else unit_obj
            except Exception:
                friendly_root = unit_obj
            if friendly_root is None:
                continue
            friendly_id = str(get_entity_id(friendly_root) or "")
            if friendly_id and friendly_id == unit_id:
                continue
            if friendly_id and friendly_id in seen:
                continue
            if friendly_id:
                seen.add(friendly_id)
            try:
                if friendly_root.get_parent_army().player is not player:
                    continue
            except Exception:
                continue
            if not _is_emperors_children_unit(friendly_root):
                continue
            try:
                if not friendly_root.is_alive():
                    continue
            except Exception:
                continue
            if not bool(getattr(friendly_root, "deployed", False)):
                continue
            if str(getattr(friendly_root, "reserve_status", "deployed")) != "deployed":
                continue
            if getattr(friendly_root, "embarked_in", None) is not None:
                continue
            if bool(getattr(friendly_root, "is_embarked", False)):
                continue
            for model in list(getattr(friendly_root, "models", []) or []):
                if not getattr(model, "is_alive", True):
                    continue
                base = getattr(model, "model_base", None)
                if base is None:
                    continue
                friendly_model_bases.append(base)
        if not friendly_model_bases:
            return False
        unit_models = list(getattr(root, "models", []) or [])
        for idx, (x, y, z, facing) in enumerate(list(prospective_positions or [])):
            if idx >= len(unit_models):
                break
            try:
                base = root._create_potential_base(x, y, z, facing, model=unit_models[idx])
            except Exception:
                return False
            if base is None:
                return False
            within_required = False
            for friendly_base in list(friendly_model_bases or []):
                try:
                    if float(horizontal_distance_between_bases_2d(base, friendly_base)) <= float(required) + 1e-6:
                        within_required = True
                        break
                except Exception:
                    continue
            if not within_required:
                return False
        return True

    def _enemy_is_afflicted_for_deep_strike_distance(
        self,
        enemy_unit,
        *,
        game=None,
        game_map=None,
    ) -> bool:
        if enemy_unit is None:
            return False
        try:
            from ...rules.nurgles_gift import NurglesGiftManager
        except Exception:
            return False
        try:
            root = enemy_unit.get_attached_unit_root() if hasattr(enemy_unit, "get_attached_unit_root") else enemy_unit
        except Exception:
            root = enemy_unit
        if root is None:
            return False
        gm = game_map
        if gm is None and game is not None:
            gm = getattr(game, "map", None)
        if game is None:
            try:
                army = self.get_parent_army()
            except Exception:
                army = None
            try:
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        try:
            return bool(NurglesGiftManager.get_afflicted_plague_for_unit(root, game=game, game_map=gm) is not None)
        except Exception:
            return False

    def get_deep_strike_min_distance_vs_enemy(
        self,
        enemy_unit,
        *,
        game=None,
        game_map=None,
    ) -> Optional[float]:
        """
        Return a per-enemy Deep Strike minimum distance override, if the unit has one.

        Used for rules like Death Approaches where Afflicted enemies have a smaller
        minimum distance than other enemy units.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        get_specs = getattr(root, "unit_deep_strike_afflicted_distance_specs", None)
        if not callable(get_specs):
            return None
        try:
            specs = list(get_specs() or [])
        except Exception:
            specs = []
        if not specs:
            return None
        afflicted = bool(
            self._enemy_is_afflicted_for_deep_strike_distance(
                enemy_unit,
                game=game,
                game_map=game_map,
            )
        )
        best: Optional[float] = None
        for spec in specs:
            try:
                dist = float(
                    spec.get("afflicted_distance", 0)
                    if afflicted
                    else spec.get("other_distance", 0)
                )
            except Exception:
                dist = 0.0
            if dist <= 0:
                continue
            best = dist if best is None else min(best, dist)
        return float(best) if best is not None else None

    def has_infiltrate(self) -> bool:
        """Check if the unit has Infiltrate ability."""
        # Use cached result if available
        if 'infiltrate' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['infiltrate']

        found = False
        # Rubricae Phalanx (Risen Rubricae): selected unit models gain Infiltrators.
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            rsr = getattr(root, "special_rules", None)
            if isinstance(rsr, dict) and rsr.get("masters_of_misdirection_infiltrators"):
                if self is root:
                    found = True
                else:
                    members = []
                    get_members = getattr(root, "get_attached_unit_members", None)
                    if callable(get_members):
                        members = list(get_members() or [])
                    if not members:
                        members = [root]
                    if self in members:
                        is_character = False
                        has_any_keyword = getattr(self, "has_any_keyword", None)
                        if callable(has_any_keyword):
                            is_character = bool(has_any_keyword("CHARACTER"))
                        if not is_character:
                            has_keyword = getattr(self, "has_keyword", None)
                            if callable(has_keyword):
                                is_character = bool(has_keyword("CHARACTER"))
                        is_epic_hero = False
                        if callable(has_any_keyword):
                            is_epic_hero = bool(has_any_keyword("EPIC HERO"))
                        if not is_epic_hero:
                            has_keyword = getattr(self, "has_keyword", None)
                            if callable(has_keyword):
                                is_epic_hero = bool(has_keyword("EPIC HERO"))
                        if is_character and not is_epic_hero:
                            found = True
            if isinstance(rsr, dict) and rsr.get("risen_rubricae_infiltrators"):
                if self is root:
                    found = True
                else:
                    members = []
                    try:
                        members = list(root.get_attached_unit_members() or [])
                    except Exception:
                        members = []
                    if not members:
                        members = [root]
                    if self in members:
                        found = True
            if not found and isinstance(rsr, dict) and rsr.get("ethereal_pathway_infiltrators"):
                if self is root:
                    found = True
                else:
                    members = []
                    try:
                        members = list(root.get_attached_unit_members() or [])
                    except Exception:
                        members = []
                    if not members:
                        members = [root]
                    if self in members:
                        found = True
            if not found and isinstance(rsr, dict) and rsr.get("informant_network_infiltrators"):
                if self is root:
                    found = True
                else:
                    members = []
                    try:
                        members = list(root.get_attached_unit_members() or [])
                    except Exception:
                        members = []
                    if not members:
                        members = [root]
                    if self in members:
                        found = True
        except Exception:
            found = False
        if not found:
            try:
                if self._butcher_lord_infiltrators_active():
                    found = True
            except Exception:
                pass
        if not found:
            try:
                if self._attached_unit_has_active_leading_enhancement(
                    "enhancement_mistweave",
                    enhancement_id="000009915005",
                    enhancement_name="mistweave",
                ):
                    found = True
            except Exception:
                pass
        if not found:
            try:
                if self._attached_unit_has_active_leading_enhancement(
                    "enhancement_blackwing_shroud",
                    enhancement_id="000010466002",
                    enhancement_name="blackwing shroud",
                ):
                    found = True
            except Exception:
                pass
        if not found:
            try:
                if self._attached_unit_has_active_leading_enhancement(
                    "enhancement_the_blade_driven_deep",
                    enhancement_id="000008490002",
                    enhancement_name="the blade driven deep",
                ):
                    found = True
            except Exception:
                pass
        if not found:
            try:
                if self._attached_unit_has_active_enhancement(
                    "enhancement_skitarii_clandestine_infiltrator",
                    enhancement_id="000008560003",
                    enhancement_name="clandestine infiltrator",
                ):
                    found = True
            except (AttributeError, TypeError, ValueError):
                pass
        if not found:
            try:
                if self._attached_unit_has_active_enhancement(
                    "enhancement_eager_for_bloodshed",
                    enhancement_id="000010688005",
                    enhancement_name="eager for bloodshed",
                ):
                    found = True
            except (AttributeError, TypeError, ValueError):
                pass
        if not found:
            try:
                if self._attached_unit_has_active_enhancement(
                    "enhancement_reapers_cowl_infiltrators",
                    enhancement_id="000009781004",
                    enhancement_name="reaper's cowl",
                ):
                    found = True
            except (AttributeError, TypeError, ValueError):
                pass
        if not found:
            try:
                if self._attached_unit_has_active_leading_enhancement(
                    "declare_battle_formations_selected_leading_infiltrators",
                    require_bearer_alive=True,
                ):
                    found = True
            except (AttributeError, TypeError, ValueError):
                pass
        if not found:
            try:
                if self._skwad_leader_is_leading_kommandos():
                    found = True
            except Exception:
                pass
        if not found:
            found, _ = self._find_ability_with_patterns(["infiltrators", "infiltrate"])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['infiltrate'] = found
        
        return found
    

    def has_stealth(self) -> bool:
        """Check if the unit has Stealth ability."""
        # Stratagem: SMOKESCREEN grants Stealth until end of phase.
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and sr.get("smokescreen_active") is True:
            return True
        # Enhancement: Praesidius grants Stealth to the bearer model.
        if isinstance(sr, dict) and sr.get("enhancement_praesidius_stealth"):
            return True
        # Enhancement: Umbral Raptor grants Stealth to the bearer model.
        if isinstance(sr, dict) and sr.get("enhancement_umbral_raptor_stealth"):
            return True
        # Enhancement: Ghostweave Cloak grants Stealth to the bearer model.
        if isinstance(sr, dict) and sr.get("enhancement_ghostweave_cloak_stealth"):
            return True
        # Deceptors: Shroud of Obfuscation grants Stealth to the bearer model.
        if isinstance(sr, dict) and sr.get("enhancement_shroud_of_obfuscation_stealth"):
            return True
        # Chaos Knights (Lords of Dread): Blessing of the Dark Master grants Stealth to the bearer model.
        if isinstance(sr, dict) and sr.get("enhancement_blessing_of_the_dark_master_stealth"):
            return True
        # Dread Talons: Night's Shroud grants Stealth to models in the bearer's unit.
        if isinstance(sr, dict) and sr.get("enhancement_nights_shroud_stealth"):
            return True
        # Nightmare Hunt: Greyveil Hex grants Stealth to models in the bearer's unit.
        if isinstance(sr, dict) and sr.get("enhancement_greyveil_hex_stealth"):
            return True
        # Enhancement: Phial of the Abyss grants Stealth to models in the bearer's unit.
        if isinstance(sr, dict) and sr.get("enhancement_phial_of_the_abyss"):
            return True
        # Reaper's Wager: Reaper's Cowl grants Stealth to models in the bearer's unit.
        if self._attached_unit_has_active_enhancement(
            "enhancement_reapers_cowl_stealth",
            enhancement_id="000009781004",
            enhancement_name="reaper's cowl",
        ):
            return True
        # Wrathful Procession: Pyrebrand grants Stealth to models in the bearer's unit.
        if self._attached_unit_has_active_enhancement(
            "enhancement_pyrebrand",
            enhancement_id="000009843002",
            enhancement_name="pyrebrand",
        ):
            return True
        # Orks Dread Mob: Smoky Gubbinz grants Stealth to models in the bearer's unit.
        if self._attached_unit_has_active_enhancement(
            "enhancement_smoky_gubbinz",
            enhancement_id="000008877004",
            enhancement_name="smoky gubbinz",
        ):
            return True
        # Orks Taktikal Brigade: Skwad Leader bearer gains Stealth while leading Kommandos.
        try:
            if self._skwad_leader_is_leading_kommandos():
                return True
        except Exception:
            pass
        # Attached leader abilities can grant Stealth to the bodyguard unit while leading.
        try:
            root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
        except Exception:
            root = self
        if root is self:
            try:
                for ability, _leader in root._iter_attached_leader_leading_abilities():
                    try:
                        name = str(getattr(ability, "name", "") or "Leading ability")
                        desc = str(getattr(ability, "description", "") or "") or name
                    except Exception:
                        name = "Leading ability"
                        desc = ""
                    text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                    if not text:
                        continue
                    low = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
                    low = re.sub(r"[^a-z0-9]+", " ", low)
                    low = re.sub(r"\s+", " ", low).strip()
                    if "while this model is leading a unit" not in low:
                        continue
                    if re.search(
                        r"(?:models in that unit|that unit) (?:have|has|gain|gains) (?:the )?stealth ability",
                        low,
                    ):
                        return True
            except Exception:
                pass
        # Rad-Zone Corps: Malphonic Susurrus grants Stealth while the bearer is leading.
        if self._attached_unit_has_active_leading_enhancement(
            "enhancement_malphonic_susurrus",
            enhancement_id="000008385003",
            enhancement_name="malphonic susurrus",
        ):
            return True
        # Start of opponent Shooting phase effects (e.g., Hallucinogen Grenades) can grant Stealth until end of phase.
        if isinstance(sr, dict) and sr.get("opponent_shooting_phase_stealth_active") is True:
            return True
        # Imperial Knights Valourstrike Lance: Bearer of the Evanescent Ion.
        if isinstance(sr, dict) and sr.get("imperial_knights_evanescent_ion_stealth_active") is True:
            return True
        # Death Guard Flyblown Host: Verminous Haze.
        army = self.get_parent_army()
        dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
        applies_fn = getattr(dg_mgr, "verminous_haze_applies_to_unit", None) if dg_mgr is not None else None
        if callable(applies_fn) and applies_fn(self):
            return True
        # Drukhari: Skysplinter Assault (Phantasmal Smoke).
        drukhari_mgr = getattr(army, "drukhari_detachments", None) if army is not None else None
        phantasmal_fn = (
            getattr(drukhari_mgr, "skysplinter_phantasmal_smoke_stealth_applies", None)
            if drukhari_mgr is not None
            else None
        )
        if callable(phantasmal_fn):
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if bool(phantasmal_fn(self, game=game)):
                return True
        # Orks: Taktikal Brigade (Lissen 'Ere - Sneaky Stalkin').
        orks_mgr = getattr(army, "orks_detachments", None) if army is not None else None
        sneaky_fn = getattr(orks_mgr, "taktikal_brigade_sneaky_stalkin_stealth_applies", None) if orks_mgr is not None else None
        if callable(sneaky_fn):
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if bool(sneaky_fn(self, game=game)):
                return True
        # Haloscreed Battle Clade: Muted Servomotors.
        adm_mgr = getattr(army, "adeptus_mechanicus_detachments", None) if army is not None else None
        muted_fn = getattr(adm_mgr, "noospheric_transference_stealth_applies", None) if adm_mgr is not None else None
        if callable(muted_fn):
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if bool(muted_fn(self, game=game)):
                return True
        stealth_opt_fn = getattr(adm_mgr, "stealth_optimisation_stealth_applies", None) if adm_mgr is not None else None
        if callable(stealth_opt_fn) and bool(stealth_opt_fn(self)):
            return True
        # Astra Militarum: Siege Regiment (Smoke Shells).
        am_mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        smoke_fn = getattr(am_mgr, "siege_regiment_smoke_shells_stealth_applies", None) if am_mgr is not None else None
        if callable(smoke_fn) and bool(smoke_fn(self)):
            return True
        mechanised_smoke_fn = (
            getattr(am_mgr, "mechanised_assault_smoke_grenades_stealth_applies", None) if am_mgr is not None else None
        )
        if callable(mechanised_smoke_fn) and bool(mechanised_smoke_fn(self)):
            return True
        # Use cached result if available
        if 'stealth' in getattr(self, '_ability_cache', {}):
            found = self._ability_cache['stealth']
        else:
            found, _ = self._find_ability_with_patterns(["stealth"])
            # Cache the result
            if not hasattr(self, '_ability_cache'):
                self._ability_cache = {}
            self._ability_cache['stealth'] = found

        if found:
            return True

        try:
            from ...utility.aura_effects import get_aura_stealth
            aura_active, _reasons = get_aura_stealth(self)
            if aura_active:
                return True
        except Exception:
            pass
        
        return False

    def _is_non_self_scout_clause(self, text: str) -> bool:
        low = str(text or "").lower().replace("\u2019", "'").replace("\u0192?T", "'")
        low = re.sub(r"\s+", " ", low).strip()
        if "scout" not in low:
            return False
        if re.search(
            r"if this unit has a leader unit attached to it during the declare battle formations step,?\s*"
            r"that leader unit gains(?: the)? scouts?\s*\d+",
            low,
            flags=re.IGNORECASE,
        ):
            return True
        if re.search(
            r"if a [^.;]+ model from your army is attached to this unit during the declare battle formations step,?\s*"
            r"that model gains(?: the)? scouts?\s*\d+",
            low,
            flags=re.IGNORECASE,
        ):
            return True
        return False

    def _has_self_scout_source(self) -> bool:
        for keyword in list(getattr(self, "keywords", []) or []):
            if "scout" in str(keyword or "").lower():
                return True

        for ability in list(self._iter_active_possible_abilities() or []):
            if isinstance(ability, str):
                for segment in self._iter_conditioned_text_segments(ability):
                    seg_low = str(segment or "").lower()
                    if "scout" not in seg_low:
                        continue
                    if self._is_non_self_scout_clause(seg_low):
                        continue
                    return True
                continue

            name = str(getattr(ability, "name", "") or "")
            if "scout" in name.lower():
                return True
            description = str(getattr(ability, "description", "") or "")
            for segment in self._iter_conditioned_text_segments(description):
                seg_low = str(segment or "").lower()
                if "scout" not in seg_low:
                    continue
                if self._is_non_self_scout_clause(seg_low):
                    continue
                return True

        for ability in list(getattr(self, "abilities", []) or []):
            try:
                if not self._ability_is_active(ability):
                    continue
            except Exception:
                pass
            if isinstance(ability, str):
                for segment in self._iter_conditioned_text_segments(ability):
                    seg_low = str(segment or "").lower()
                    if "scout" not in seg_low:
                        continue
                    if self._is_non_self_scout_clause(seg_low):
                        continue
                    return True
                continue

            name = str(getattr(ability, "name", "") or "")
            if "scout" in name.lower():
                return True
            description = str(getattr(ability, "description", "") or "")
            for segment in self._iter_conditioned_text_segments(description):
                seg_low = str(segment or "").lower()
                if "scout" not in seg_low:
                    continue
                if self._is_non_self_scout_clause(seg_low):
                    continue
                return True

        return False

    def _get_attached_unit_scout_bonus_distance(self) -> float:
        """
        Return the maximum scout distance granted via special rules across attached unit members.

        Used for enhancement/formation bonuses that grant Scouts to the bearer's unit.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        bodyguard_not_embarked = True
        try:
            bodyguard_not_embarked = not (
                bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None))
            )
        except Exception:
            bodyguard_not_embarked = True
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        max_dist = 0.0
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            val = 0.0
            try:
                val = max(val, float(sr.get("enhancement_scout_distance", 0) or 0))
            except Exception:
                pass
            try:
                val = max(val, float(sr.get("declare_battle_formations_selected_scout_distance", 0) or 0))
            except Exception:
                pass
            try:
                val = max(val, float(sr.get("enhancement_warped_foresight_scout_distance", 0) or 0))
            except Exception:
                pass
            try:
                val = max(val, float(sr.get("iconoclast_pave_the_way_scout_distance", 0) or 0))
            except Exception:
                pass
            try:
                val = max(val, float(sr.get("leading_bodyguard_scout_distance", 0) or 0))
            except Exception:
                pass
            if bodyguard_not_embarked:
                try:
                    val = max(
                        val,
                        float(sr.get("leading_bodyguard_scout_distance_requires_bodyguard_not_embarked", 0) or 0),
                    )
                except Exception:
                    pass
            if val > max_dist:
                max_dist = val
        return float(max_dist)

    def has_scout(self) -> Tuple[bool, float]:
        """Check if the unit has Scout ability and return the scout distance.
        
        Returns:
            Tuple[bool, float]: A tuple containing:
                - A boolean indicating if the unit has Scout ability
                - The scout distance in inches (0.0 if no Scout ability)
        """
        verminous_haze_active = False
        verminous_haze_distance = 0.0
        army = self.get_parent_army()
        dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
        active_fn = getattr(dg_mgr, "is_flyblown_host", None) if dg_mgr is not None else None
        if callable(active_fn):
            verminous_haze_active = bool(active_fn())
        scout_fn = getattr(dg_mgr, "verminous_haze_scout_distance_for_unit", None) if dg_mgr is not None else None
        if callable(scout_fn):
            verminous_haze_distance = float(scout_fn(self) or 0.0)
        am_scout_dynamic = False
        recon_survival_gear_distance = 0.0
        siege_eager_advance_distance = 0.0
        am_mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        recon_scout_fn = (
            getattr(am_mgr, "recon_element_survival_gear_scout_distance", None) if am_mgr is not None else None
        )
        if callable(recon_scout_fn):
            am_scout_dynamic = True
            recon_survival_gear_distance = float(recon_scout_fn(self) or 0.0)
        siege_scout_fn = (
            getattr(am_mgr, "siege_regiment_eager_advance_scout_distance", None) if am_mgr is not None else None
        )
        if callable(siege_scout_fn):
            am_scout_dynamic = True
            siege_eager_advance_distance = float(siege_scout_fn(self) or 0.0)
        csm_scout_dynamic = False
        mark_of_the_hound_distance = 0.0
        sorrowscent_vulture_distance = 0.0
        csm_mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
        csm_scout_fn = (
            getattr(csm_mgr, "renegade_raiders_mark_of_the_hound_scout_distance", None) if csm_mgr is not None else None
        )
        csm_nightmare_scout_fn = (
            getattr(csm_mgr, "nightmare_hunt_sorrowscent_vulture_scout_distance", None)
            if csm_mgr is not None
            else None
        )
        if callable(csm_scout_fn):
            csm_scout_dynamic = True
            mark_of_the_hound_distance = float(csm_scout_fn(self) or 0.0)
        if callable(csm_nightmare_scout_fn):
            csm_scout_dynamic = True
            sorrowscent_vulture_distance = float(csm_nightmare_scout_fn(self) or 0.0)

        # Use cached result if available
        if (
            (not verminous_haze_active)
            and (not am_scout_dynamic)
            and (not csm_scout_dynamic)
            and 'scout' in getattr(self, '_ability_cache', {})
        ):
            return self._ability_cache['scout']
        
        try:
            found, distance_str = self._find_ability_with_patterns(["scout"], extract_value=True, value_pattern=r'(\d+)')
        except ValueError:
            found, distance_str = False, None
        if found and not self._has_self_scout_source():
            found, distance_str = False, None
        if not found:
            try:
                for txt in self._iter_active_ability_texts():
                    low = str(txt or "").lower()
                    if "scout" not in low:
                        continue
                    if self._is_non_self_scout_clause(low):
                        continue
                    m = re.search(r"scouts?\s*(\d+)", low)
                    if m:
                        found = True
                        distance_str = m.group(1)
                        break
            except Exception:
                found, distance_str = False, None
        dist = float(distance_str) if found else 0.0
        try:
            bonus_dist = float(self._get_attached_unit_scout_bonus_distance() or 0.0)
        except Exception:
            bonus_dist = 0.0
        if bonus_dist > 0:
            found = True
            dist = max(float(dist or 0.0), float(bonus_dist))
        try:
            sr = getattr(self, "special_rules", None)
            leader_bonus_dist = 0.0
            if isinstance(sr, dict) and bool(getattr(self, "is_attached_leader", False)):
                leader_bonus_dist = float(sr.get("attached_unit_bodyguard_leader_scout_distance", 0) or 0.0)
                conditional_bonus_dist = float(
                    sr.get("attached_unit_bodyguard_leader_scout_distance_requires_bodyguard_embarked", 0) or 0.0
                )
                if conditional_bonus_dist > 0:
                    bodyguard = getattr(self, "attached_to", None)
                    if bodyguard is not None and bool(getattr(bodyguard, "is_embarked", False)):
                        leader_bonus_dist = max(float(leader_bonus_dist), float(conditional_bonus_dist))
        except Exception:
            leader_bonus_dist = 0.0
        if leader_bonus_dist > 0:
            found = True
            dist = max(float(dist or 0.0), float(leader_bonus_dist))
        if verminous_haze_distance > 0:
            found = True
            dist = max(float(dist or 0.0), float(verminous_haze_distance))
        if recon_survival_gear_distance > 0:
            found = True
            dist = max(float(dist or 0.0), float(recon_survival_gear_distance))
        if siege_eager_advance_distance > 0:
            found = True
            dist = max(float(dist or 0.0), float(siege_eager_advance_distance))
        if mark_of_the_hound_distance > 0:
            found = True
            dist = max(float(dist or 0.0), float(mark_of_the_hound_distance))
        if sorrowscent_vulture_distance > 0:
            found = True
            dist = max(float(dist or 0.0), float(sorrowscent_vulture_distance))
        result = (True, float(dist)) if found else (False, 0.0)

        # Attached units can only Scout if every model has Scouts (use smallest distance if mixed).
        try:
            if result[0] and (not bool(getattr(self, "is_leader", False)) or getattr(self, "attached_to", None) is None):
                root = self.get_attached_unit_root()
                leaders = list(getattr(root, "attached_leaders", []) or [])
                min_dist = float(result[1])
                for leader in leaders:
                    try:
                        l_found, l_dist = leader.has_scout()
                    except Exception:
                        l_found, l_dist = False, 0.0
                    if not l_found:
                        result = (False, 0.0)
                        break
                    try:
                        min_dist = min(min_dist, float(l_dist))
                    except Exception:
                        pass
                if result[0]:
                    result = (True, float(min_dist))
        except Exception:
            pass
        
        # Cache the result when there are no dynamic Verminous Haze state checks.
        if (not verminous_haze_active) and (not am_scout_dynamic) and (not csm_scout_dynamic):
            if not hasattr(self, '_ability_cache'):
                self._ability_cache = {}
            self._ability_cache['scout'] = result
        
        return result
    

    def get_scout_distance_normalized(self, max_scout_distance: float = 12.0) -> float:
        """Get the normalized scout distance for deployment considerations.
        
        Args:
            max_scout_distance (float): Maximum possible scout distance for normalization
            
        Returns:
            float: Normalized scout distance (0.0 to 1.0), where 1.0 represents maximum scout mobility
        """
        has_scout_ability, scout_distance = self.has_scout()
        if not has_scout_ability:
            return 0.0
        
        return min(scout_distance / max_scout_distance, 1.0)

    def _enhancement_redeploy_specs(self) -> list[dict]:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return []
        raw_specs = list(sr.get("enhancement_redeploy_specs", []) or [])
        specs: list[dict] = []
        for raw in raw_specs:
            if not isinstance(raw, dict):
                continue
            filters: list[str] = []
            for value in list(raw.get("filters", []) or []):
                token = str(value or "").strip().upper()
                if token and token not in filters:
                    filters.append(token)
            excluded_keywords: list[str] = []
            for value in list(raw.get("excluded_keywords", []) or []):
                token = str(value or "").strip().upper()
                if token and token not in excluded_keywords:
                    excluded_keywords.append(token)
            filter_any_groups: list[list[str]] = []
            for raw_group in list(raw.get("filter_any_groups", []) or []):
                raw_values = [raw_group] if isinstance(raw_group, str) else list(raw_group or [])
                group: list[str] = []
                for value in raw_values:
                    token = str(value or "").strip().upper()
                    if token and token not in group:
                        group.append(token)
                if group:
                    filter_any_groups.append(group)
            specs.append(
                {
                    "source": str(raw.get("source", "") or "").strip() or "Redeploy",
                    "source_model_id": str(raw.get("source_model_id", "") or "").strip(),
                    "max_units": max(1, int(raw.get("max_units", 1) or 1)),
                    "can_place_in_reserves": bool(raw.get("can_place_in_reserves", False)),
                    "filters": list(filters),
                    "excluded_keywords": list(excluded_keywords),
                    "filter_any_groups": [list(group) for group in filter_any_groups],
                    "requires_source_on_battlefield": bool(raw.get("requires_source_on_battlefield", False)),
                    "allow_embarked_transport_on_battlefield": bool(
                        raw.get("allow_embarked_transport_on_battlefield", False)
                    ),
                    "exclude_source_unit": bool(raw.get("exclude_source_unit", False)),
                    "must_include_source_unit": bool(raw.get("must_include_source_unit", False)),
                    "require_exact_count": bool(raw.get("require_exact_count", False)),
                    "army_once_per_ability": bool(raw.get("army_once_per_ability", False)),
                    "strategic_reserves_ignore_current_unit_count_limit": bool(
                        raw.get("strategic_reserves_ignore_current_unit_count_limit", False)
                    ),
                }
            )
        specs.sort(
            key=lambda spec: (
                str(spec.get("source_model_id", "") or ""),
                str(spec.get("source", "") or "").lower(),
                int(spec.get("max_units", 0) or 0),
                tuple(spec.get("filters", []) or []),
            )
        )
        return specs

    def has_redeploy(self) -> Tuple[bool, int, bool]:
        """Check if the unit grants redeploy capability.

        Returns:
            Tuple[bool, int, bool]:
                - has_redeploy: True if this unit grants redeploy to units in the army
                - count: number of units that can be redeployed (default 3; D3 treated as 3 for now)
                - can_place_in_reserves: True if redeployed units may be placed into Strategic Reserves regardless of limits

        Notes:
            We intentionally parse ability descriptions rather than names. The wording generally includes
            "after both players have deployed their armies" and "select up to" N units from your army "and redeploy them".
        """
        # Use cached result if available
        if 'redeploy' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['redeploy']

        redeploy_specs = self._enhancement_redeploy_specs()
        if redeploy_specs:
            spec = dict(redeploy_specs[0] or {})
            result = (
                True,
                int(spec.get("max_units", 1) or 1),
                bool(spec.get("can_place_in_reserves", False)),
            )
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if list(spec.get("filters", []) or []):
                self._ability_cache["redeploy_filters"] = list(spec.get("filters", []) or [])
            if list(spec.get("excluded_keywords", []) or []):
                self._ability_cache["redeploy_excluded_keywords"] = list(spec.get("excluded_keywords", []) or [])
            if list(spec.get("filter_any_groups", []) or []):
                self._ability_cache["redeploy_filter_any_groups"] = [
                    list(group) for group in list(spec.get("filter_any_groups", []) or [])
                ]
            self._ability_cache["redeploy_ability_name"] = str(spec.get("source", "") or "Redeploy")
            self._ability_cache["redeploy_requires_source_on_battlefield"] = bool(
                spec.get("requires_source_on_battlefield", False)
            )
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = bool(
                spec.get("allow_embarked_transport_on_battlefield", False)
            )
            self._ability_cache["redeploy_exclude_source_unit"] = bool(spec.get("exclude_source_unit", False))
            self._ability_cache["redeploy_must_include_source_unit"] = bool(
                spec.get("must_include_source_unit", False)
            )
            self._ability_cache["redeploy_require_exact_count"] = bool(spec.get("require_exact_count", False))
            self._ability_cache["redeploy_army_once_per_ability"] = bool(
                spec.get("army_once_per_ability", False)
            )
            self._ability_cache["redeploy_strategic_reserves_ignore_current_unit_count_limit"] = bool(
                spec.get("strategic_reserves_ignore_current_unit_count_limit", False)
            )
            return result

        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("enhancement_orbital_uplink_reliquary", False)):
            try:
                count = int(sr.get("enhancement_orbital_uplink_reliquary_max_units", 3) or 3)
            except Exception:
                count = 3
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(
                sr.get("enhancement_orbital_uplink_reliquary_can_place_in_reserves", True)
            )
            filters = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_orbital_uplink_reliquary_filters", []) or [])
                if str(v or "").strip()
            ]
            ability_name = (
                str(sr.get("enhancement_orbital_uplink_reliquary_source", "") or "Orbital Uplink Reliquary")
                .strip()
                or "Orbital Uplink Reliquary"
            )
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filters:
                self._ability_cache["redeploy_filters"] = list(filters)
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = False
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            return result

        if isinstance(sr, dict) and bool(sr.get("enhancement_hunters_guile", False)):
            try:
                count = int(sr.get("enhancement_hunters_guile_max_units", 3) or 3)
            except Exception:
                count = 3
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(sr.get("enhancement_hunters_guile_can_place_in_reserves", True))
            raw_any_groups = list(sr.get("enhancement_hunters_guile_filter_any_groups", []) or [])
            filter_any_groups: list[list[str]] = []
            for raw_group in raw_any_groups:
                if isinstance(raw_group, str):
                    raw_values = [raw_group]
                else:
                    raw_values = list(raw_group or [])
                group: list[str] = []
                for value in raw_values:
                    keyword = str(value or "").strip().upper()
                    if not keyword or keyword in group:
                        continue
                    group.append(keyword)
                if group:
                    filter_any_groups.append(group)
            ability_name = (
                str(sr.get("enhancement_hunters_guile_source", "") or "Hunter's Guile")
                .strip()
                or "Hunter's Guile"
            )
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filter_any_groups:
                self._ability_cache["redeploy_filter_any_groups"] = [list(group) for group in filter_any_groups]
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = False
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            return result

        if isinstance(sr, dict) and bool(sr.get("enhancement_chariots_of_the_storm", False)):
            try:
                count = int(sr.get("enhancement_chariots_of_the_storm_max_units", 3) or 3)
            except Exception:
                count = 3
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(sr.get("enhancement_chariots_of_the_storm_can_place_in_reserves", True))
            filters = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_chariots_of_the_storm_filters", []) or [])
                if str(v or "").strip()
            ]
            ability_name = (
                str(sr.get("enhancement_chariots_of_the_storm_source", "") or "Chariots of the Storm")
                .strip()
                or "Chariots of the Storm"
            )
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filters:
                self._ability_cache["redeploy_filters"] = list(filters)
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = False
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            return result

        if isinstance(sr, dict) and bool(sr.get("enhancement_advance_augury", False)):
            try:
                count = int(sr.get("enhancement_advance_augury_max_units", 3) or 3)
            except (TypeError, ValueError):
                count = 3
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(sr.get("enhancement_advance_augury_can_place_in_reserves", True))
            filters = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_advance_augury_filters", []) or [])
                if str(v or "").strip()
            ]
            ability_name = (
                str(sr.get("enhancement_advance_augury_source", "") or "Advance Augury")
                .strip()
                or "Advance Augury"
            )
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filters:
                self._ability_cache["redeploy_filters"] = list(filters)
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = False
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            return result

        if isinstance(sr, dict) and bool(sr.get("enhancement_guerrilla_honours", False)):
            try:
                count = int(sr.get("enhancement_guerrilla_honours_max_units", 3) or 3)
            except (TypeError, ValueError):
                count = 3
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(sr.get("enhancement_guerrilla_honours_can_place_in_reserves", True))
            filters = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_guerrilla_honours_filters", []) or [])
                if str(v or "").strip()
            ]
            ability_name = (
                str(sr.get("enhancement_guerrilla_honours_source", "") or "Guerrilla Honours")
                .strip()
                or "Guerrilla Honours"
            )
            exclude_source_unit = bool(sr.get("enhancement_guerrilla_honours_exclude_source_unit", True))
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filters:
                self._ability_cache["redeploy_filters"] = list(filters)
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = True
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            self._ability_cache["redeploy_exclude_source_unit"] = bool(exclude_source_unit)
            return result

        if isinstance(sr, dict) and bool(sr.get("enhancement_skitarii_veiled_hunter", False)):
            try:
                count = int(sr.get("enhancement_skitarii_veiled_hunter_max_units", 3) or 3)
            except (TypeError, ValueError):
                count = 3
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(sr.get("enhancement_skitarii_veiled_hunter_can_place_in_reserves", True))
            filters = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_skitarii_veiled_hunter_filters", []) or [])
                if str(v or "").strip()
            ]
            ability_name = (
                str(sr.get("enhancement_skitarii_veiled_hunter_source", "") or "Veiled Hunter")
                .strip()
                or "Veiled Hunter"
            )
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filters:
                self._ability_cache["redeploy_filters"] = list(filters)
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = False
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            return result

        if isinstance(sr, dict) and bool(sr.get("enhancement_castellans_mark", False)):
            try:
                count = int(sr.get("enhancement_castellans_mark_max_units", 2) or 2)
            except (TypeError, ValueError):
                count = 2
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(sr.get("enhancement_castellans_mark_can_place_in_reserves", True))
            filters = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_castellans_mark_filters", []) or [])
                if str(v or "").strip()
            ]
            excluded_keywords = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_castellans_mark_excluded_keywords", []) or [])
                if str(v or "").strip()
            ]
            ability_name = (
                str(sr.get("enhancement_castellans_mark_source", "") or "Castellan's Mark")
                .strip()
                or "Castellan's Mark"
            )
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filters:
                self._ability_cache["redeploy_filters"] = list(filters)
            if excluded_keywords:
                self._ability_cache["redeploy_excluded_keywords"] = list(excluded_keywords)
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = False
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            return result

        has_redeploy = False
        count = 0
        can_place_in_reserves = False

        # Normalize abilities list: abilities may be attached to models in unit
        abilities_to_check: list[tuple[str, str]] = []
        for model in getattr(self, 'models', []):
            for ability in getattr(model, 'abilities', []):
                if ability and hasattr(ability, 'description'):
                    try:
                        if not self._ability_is_active(ability):
                            continue
                    except Exception:
                        pass
                    abilities_to_check.append((getattr(ability, "name", "") or "", ability.description))

        # Also include unit-level possible_abilities if present
        for ability in self._iter_active_possible_abilities():
            if ability and hasattr(ability, 'description'):
                abilities_to_check.append((getattr(ability, "name", "") or "", ability.description))

        # Enhancement text applies to the enhancement bearer (unit-level for redeploy rules).
        try:
            enh = getattr(self, "enhancement", None)
            if enh is not None:
                desc = getattr(enh, "description", "") or ""
                if desc:
                    abilities_to_check.append((getattr(enh, "name", "") or "", desc))
        except Exception:
            pass

        redeploy_filters: list[str] = []
        redeploy_filter_any_groups: list[list[str]] = []
        ability_name = ""
        requires_source_on_battlefield = False
        allow_embarked_transport_on_battlefield = False
        must_include_source_unit = False
        require_exact_count = False
        army_once_per_ability = False

        def _apply_redeploy_count_token(raw_value: str) -> None:
            nonlocal count
            val = str(raw_value or "").strip().lower()
            if not val:
                return
            if val.startswith("d"):
                try:
                    expr = val.upper().replace(" ", "")
                    d = DiceCollection.from_string(expr)
                    total, rolls = d.roll_detailed()
                    count = max(count, total)
                    setattr(self, "_redeploy_d_roll", {"expr": expr, "total": total, "rolls": rolls})
                    logger.info(f"{self.name} Redeploy {expr} roll: {total} (rolled {rolls})")
                except Exception:
                    count = max(count, 1)
                return
            word_counts = {
                "one": 1,
                "two": 2,
                "three": 3,
                "four": 4,
                "five": 5,
                "six": 6,
            }
            if val in word_counts:
                count = max(count, int(word_counts[val]))
                return
            try:
                count = max(count, int(val))
            except Exception:
                return

        for name, desc in abilities_to_check:
            text = html.unescape(str(desc or ""))
            text = re.sub(r"<[^>]+>", " ", text)
            text = text.lower()
            text = text.replace("\u2019", "'").replace("\u2018", "'")
            text = re.sub(r"\s+", " ", text).strip()
            if ("after both players have deployed their armies" in text and "redeploy" in text):
                # Attempt to extract count from "select up to" phrases
                has_redeploy = True
                if name and not ability_name:
                    ability_name = str(name)
                if (
                    "if your army includes one or more units with this ability" in text
                    or "if your army contains one or more units with this ability" in text
                    or "if your army includes one or more models with this ability" in text
                    or "if your army contains one or more models with this ability" in text
                ):
                    army_once_per_ability = True
                if ("if this unit is on the battlefield" in text) or ("if the bearer is on the battlefield" in text):
                    requires_source_on_battlefield = True
                if "transport it is embarked within is on the battlefield" in text:
                    requires_source_on_battlefield = True
                    allow_embarked_transport_on_battlefield = True
                source_and_other_match = re.search(
                    r"redeploy this model'?s unit and one other friendly ([a-z0-9' ]+?) unit",
                    text,
                )
                if source_and_other_match:
                    count = max(count, 2)
                    other_filter = str(source_and_other_match.group(1) or "").strip().upper()
                    if other_filter:
                        redeploy_filters = [other_filter]
                    must_include_source_unit = True
                    require_exact_count = True
                count_match = re.search(
                    r"after both players have deployed their armies.*?select\s+(?:up\s*to\s+)?"
                    r"(?P<count>(?:\d+)|(?:d\d+(?:\s*\+\s*\d+)?)|one|two|three|four|five|six)"
                    r"\s+(?P<filter>.+?)\s+units?\s+from\s+your\s+army\s+and\s+redeploy"
                    r"(?:\s+all\s+of\s+those\s+units|\s+them|\s+it)?",
                    text,
                    flags=re.IGNORECASE,
                )
                filter_text = text
                if count_match:
                    _apply_redeploy_count_token(str(count_match.group("count") or ""))
                    filter_text = str(count_match.group("filter") or "").strip().lower()
                elif not source_and_other_match:
                    count = max(count, 3)  # default to 3 if unspecified
                if "strategic reserves" in text:
                    can_place_in_reserves = True
                if "imperium battleline" in filter_text:
                    redeploy_filters = ["IMPERIUM", "BATTLELINE"]
                if "agents of the imperium" in filter_text:
                    redeploy_filters = ["AGENTS OF THE IMPERIUM"]
                if (
                    "emperor's children" in filter_text
                    or "emperors children" in filter_text
                ):
                    redeploy_filters = ["EMPEROR'S CHILDREN"]
                if "harlequins" in filter_text:
                    redeploy_filters = ["HARLEQUINS"]
                if "adeptus astartes" in filter_text and "infantry" in filter_text:
                    redeploy_filters = ["ADEPTUS ASTARTES", "INFANTRY"]
                elif "adeptus astartes" in filter_text:
                    redeploy_filters = ["ADEPTUS ASTARTES"]
                if "aeldari" in filter_text and "vehicle" in filter_text:
                    redeploy_filters = ["AELDARI", "VEHICLE"]
                elif "aeldari" in filter_text:
                    redeploy_filters = ["AELDARI"]
                if "jakhals" in filter_text and "goremongers" in filter_text:
                    redeploy_filter_any_groups = [["JAKHALS"], ["GOREMONGERS"]]
                if (
                    "t'au empire" in filter_text
                    or "tau empire" in filter_text
                ):
                    redeploy_filters = ["T'AU EMPIRE"]
                if "thousand sons" in filter_text:
                    redeploy_filters = ["THOUSAND SONS"]
                if "tyranids" in filter_text:
                    redeploy_filters = ["TYRANIDS"]
                if "vanguard invader" in filter_text:
                    redeploy_filters = ["VANGUARD INVADER"]
                if (
                    "heretic astartes" in filter_text
                    or "<heretic astartes>" in filter_text
                ):
                    redeploy_filters = ["HERETIC ASTARTES"]
                if "drukhari" in filter_text:
                    redeploy_filters = ["DRUKHARI"]

        result = (has_redeploy, count, can_place_in_reserves)
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['redeploy'] = result
        if redeploy_filters:
            self._ability_cache['redeploy_filters'] = list(redeploy_filters)
        if redeploy_filter_any_groups:
            self._ability_cache['redeploy_filter_any_groups'] = [list(group) for group in redeploy_filter_any_groups]
        if ability_name:
            self._ability_cache['redeploy_ability_name'] = ability_name
        self._ability_cache['redeploy_requires_source_on_battlefield'] = bool(requires_source_on_battlefield)
        self._ability_cache['redeploy_allow_embarked_transport_on_battlefield'] = bool(
            allow_embarked_transport_on_battlefield
        )
        self._ability_cache['redeploy_must_include_source_unit'] = bool(must_include_source_unit)
        self._ability_cache['redeploy_require_exact_count'] = bool(require_exact_count)
        self._ability_cache['redeploy_army_once_per_ability'] = bool(army_once_per_ability)
        return result
    
