"""Attack bonus resolution helpers for Unit keyword, half-range, and choice-driven combat modifiers."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class PositioningAttackBonusesMixin:
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
            army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            keyword_fn = getattr(sm_mgr, "augmented_targeting_weapon_keywords", None) if sm_mgr is not None else None
            if callable(keyword_fn):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                keywords, source = keyword_fn(
                    self,
                    weapon_profile=weapon_profile,
                    game=game,
                )
                source_name = str(source or "Augmented Targeting").strip() or "Augmented Targeting"
                for keyword in list(keywords or []):
                    keyword_name = str(keyword or "").strip().upper()
                    if keyword_name:
                        rules = list(rules or []) + [
                            {
                                "attack_type": "ranged",
                                "keyword": keyword_name,
                                "source": source_name,
                            }
                        ]
        except Exception:
            pass
        try:
            army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
            adm_mgr = getattr(army, "adeptus_mechanicus_detachments", None) if army is not None else None
            keyword_fn = (
                getattr(adm_mgr, "auto_divinatory_targeting_attack_keywords", None)
                if adm_mgr is not None
                else None
            )
            if callable(keyword_fn):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                keywords, source = keyword_fn(
                    model,
                    weapon_profile=weapon_profile,
                    game=game,
                )
                source_name = str(source or "Auto-divinatory Targeting").strip() or "Auto-divinatory Targeting"
                for keyword in list(keywords or []):
                    keyword_name = str(keyword or "").strip().upper()
                    if keyword_name:
                        rules = list(rules or []) + [
                            {
                                "attack_type": "ranged",
                                "keyword": keyword_name,
                                "source": source_name,
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
                    army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
                    voice = getattr(army, "voice_of_command", None) if army is not None else None
                    has_any_order = False
                    if voice is not None and hasattr(voice, "attached_unit_has_any_order"):
                        has_any_order = bool(voice.attached_unit_has_any_order(root))
                    else:
                        for candidate in (unit, root):
                            sr = getattr(candidate, "special_rules", None)
                            if not isinstance(sr, dict):
                                continue
                            active_order = str(sr.get("voice_of_command_order_key", "") or "").strip().upper()
                            if active_order:
                                has_any_order = True
                                break
                            additional = list(sr.get("voice_of_command_additional_order_keys", []) or [])
                            if any(str(key or "").strip().upper() for key in additional):
                                has_any_order = True
                                break
                            temporary = list(sr.get("voice_of_command_temp_order_keys", []) or [])
                            if any(str(key or "").strip().upper() for key in temporary):
                                has_any_order = True
                                break
                    if not has_any_order:
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
            realspace_dark_harvest_fn = (
                getattr(drukhari_mgr, "realspace_dark_harvest_weapon_keyword_bonuses", None)
                if drukhari_mgr is not None
                else None
            )
            if callable(realspace_dark_harvest_fn):
                game = getattr(getattr(source_army, "player", None), "game", None) if source_army is not None else None
                for entry in list(
                    realspace_dark_harvest_fn(model, target, weapon_profile=weapon_profile, game=game) or []
                ):
                    if not isinstance(entry, dict):
                        continue
                    keyword = str(entry.get("keyword", "") or "").strip().upper()
                    if not keyword:
                        continue
                    rules = list(rules or []) + [
                        {
                            "attack_type": str(entry.get("attack_type", "any") or "any").strip().lower(),
                            "keyword": keyword,
                            "source": str(entry.get("source", "") or "Dark Harvest"),
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
            avenged_fn = getattr(mgr, "iconoclast_avenged_enemy_lethal_hits", None) if mgr is not None else None
            if callable(avenged_fn):
                lethal_hits, source = avenged_fn(model, target)
                if bool(lethal_hits):
                    rules = list(rules or []) + [
                        {
                            "attack_type": "any",
                            "keyword": "LETHAL HITS",
                            "source": str(source or "Avenge the Masters!"),
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
                flag_key="enhancement_unflinching_will",
                enhancement_id="000008550003",
                enhancement_name="unflinching will",
                require_leading=False,
            ):
                source = "Unflinching Will"
                anti_keyword = "INFANTRY"
                anti_value = 5
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
                    if not isinstance(sr, dict) or not bool(sr.get("enhancement_unflinching_will")):
                        continue
                    source = str(sr.get("enhancement_unflinching_will_source", "") or "").strip() or "Unflinching Will"
                    anti_keyword = (
                        str(sr.get("enhancement_unflinching_will_anti_keyword", "INFANTRY") or "INFANTRY").strip().upper()
                        or "INFANTRY"
                    )
                    try:
                        anti_value = int(sr.get("enhancement_unflinching_will_anti_value", 5) or 5)
                    except Exception:
                        anti_value = 5
                    break
                rules = list(rules or []) + [
                    {
                        "attack_type": "melee",
                        "keyword": "PRECISION",
                        "source": source,
                    },
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
        try:
            source_unit = getattr(model, "parent_unit", None) or self
            army = source_unit.get_parent_army() if hasattr(source_unit, "get_parent_army") else None
            mgr = getattr(army, "leagues_of_votann_detachments", None) if army is not None else None
            sustained_fn = getattr(mgr, "trivarg_cyber_implant_sustained_hits_value", None) if mgr is not None else None
            if callable(sustained_fn):
                sustained_value, source = sustained_fn(model, weapon_profile=weapon_profile)
                if int(sustained_value or 0) > 0:
                    rules = list(rules or []) + [
                        {
                            "attack_type": "ranged",
                            "keyword": f"SUSTAINED HITS {int(sustained_value)}",
                            "source": str(source or "Trivärg Cyber Implant"),
                        }
                    ]
        except Exception:
            pass
        try:
            source_unit = getattr(model, "parent_unit", None) or self
            army = source_unit.get_parent_army() if hasattr(source_unit, "get_parent_army") else None
            mgr = getattr(army, "leagues_of_votann_detachments", None) if army is not None else None
            sustained_fn = (
                getattr(mgr, "etacarn_sb9_targeting_implant_sustained_hits_value", None)
                if mgr is not None
                else None
            )
            if callable(sustained_fn):
                sustained_value, source = sustained_fn(model, weapon_profile=weapon_profile)
                if int(sustained_value or 0) > 0:
                    attack_type = "melee" if is_melee_attack else "ranged" if is_ranged_attack else "any"
                    rules = list(rules or []) + [
                        {
                            "attack_type": attack_type,
                            "keyword": f"SUSTAINED HITS {int(sustained_value)}",
                            "source": str(source or "Etacarn SB9 Targeting Implant"),
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
            if isinstance(sr, dict) and bool(sr.get("tau_arrokon_protocol_active")):
                apply_bonus = True
                exp = str(sr.get("tau_arrokon_protocol_expires_phase", "") or "").strip().upper()
                owner_id = str(sr.get("tau_arrokon_protocol_turn_owner", "") or "")
                try:
                    turn = int(sr.get("tau_arrokon_protocol_turn", 0) or 0)
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
                if apply_bonus and target is not None:
                    target_root = (
                        target.get_attached_unit_root()
                        if hasattr(target, "get_attached_unit_root")
                        else target
                    )
                    target_models = []
                    get_target_models = getattr(target_root, "get_attached_unit_models", None)
                    if callable(get_target_models):
                        target_models = list(get_target_models() or [])
                    if not target_models:
                        target_models = list(getattr(target_root, "models", []) or [])
                    alive_models = 0
                    for target_model in target_models:
                        is_alive_attr = getattr(target_model, "is_alive", False)
                        if bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr):
                            alive_models += 1
                    sustained_value = 0
                    if alive_models >= 11:
                        sustained_value = 2
                    elif alive_models >= 6:
                        sustained_value = 1
                    if sustained_value > 0:
                        source = str(sr.get("tau_arrokon_protocol_source", "") or "THE ARRO'KON PROTOCOL").strip()
                        rules = list(rules or []) + [
                            {
                                "attack_type": "ranged",
                                "keyword": f"SUSTAINED HITS {int(sustained_value)}",
                                "source": source or "THE ARRO'KON PROTOCOL",
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


    def weapon_profile_counts_as_pistol(
        self,
        weapon_profile,
        *,
        model: Optional['Model'] = None,
    ) -> bool:
        if weapon_profile is None:
            return False
        is_pistol = getattr(weapon_profile, "is_pistol", None)
        if callable(is_pistol):
            try:
                if bool(is_pistol()):
                    return True
            except Exception:
                pass

        models: list['Model'] = []
        if model is not None:
            models = [model]
        else:
            get_models = getattr(self, "get_attached_unit_models", None)
            models = list(get_models() or []) if callable(get_models) else list(getattr(self, "models", []) or [])
        if not models:
            return False

        weapon_name = ""
        try:
            weapon_name = str(getattr(getattr(weapon_profile, "parent_wargear", None), "name", "") or "")
        except Exception:
            weapon_name = ""
        if not weapon_name:
            try:
                weapon_name = str(getattr(weapon_profile, "name", "") or "")
            except Exception:
                weapon_name = ""
        attack_type = "ranged"
        try:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is not None and callable(getattr(parent, "is_melee", None)) and bool(parent.is_melee()):
                attack_type = "melee"
        except Exception:
            attack_type = "ranged"

        for candidate in list(models or []):
            if candidate is None:
                continue
            alive_attr = getattr(candidate, "is_alive", True)
            try:
                is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            except Exception:
                is_alive = False
            if not is_alive:
                continue
            bonus = self.get_model_weapon_keyword_bonuses(
                attack_type=attack_type,
                model=candidate,
                weapon_profile=weapon_profile,
                weapon_name=weapon_name,
            )
            if isinstance(bonus, dict) and bool(bonus.get("pistol")):
                return True
        return False


    def get_weapon_target_excluding_keywords_keyword_bonus_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return weapon-scoped attack keyword bonus rules for patterns like:
        "Each time this model makes an attack with its punisher gatling cannon that targets an enemy unit
         (excluding MONSTERS and VEHICLES), that attack has the [DEVASTATING WOUNDS] ability."
        Also supports unit-scoped variants like:
        "Each time a model in this unit makes an attack with an eradication caster that targets a unit
         (excluding MONSTER and VEHICLE units), that attack has the [SUSTAINED HITS 1] ability."
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
                match = None
                for pattern in (
                    r"each time (?:this model|a model in this unit) makes an? (?:melee |ranged )?attack "
                    r"with (?:(?:its|the|an?) )?(?P<weapon>[a-z0-9 ]+?) that targets "
                    r"(?:an? )?(?:enemy )?unit(?:s)? excluding (?P<exclude>[a-z0-9 ]+) that attack has "
                    r"(?:the )?(?P<keyword>[a-z0-9 ]+) ability",
                ):
                    match = re.fullmatch(pattern, normalized)
                    if match:
                        break
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
                    token = re.sub(r"\bunits?\b", "", token, flags=re.IGNORECASE).strip()
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
        Also supports unit-scoped variants like:
        "Each time a model in this unit makes an attack with a neutron fusil against a MONSTER or VEHICLE unit,
         that attack has the [IGNORES COVER] ability."
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
                match = None
                for pattern in (
                    r"each time (?:this model|a model in this unit) makes an? (?:melee |ranged )?attack "
                    r"with (?:(?:its|the|an?) )?(?P<weapon>[a-z0-9 ]+?) that targets "
                    r"(?:an? )?(?:enemy )?(?P<targets>[a-z0-9 ]+?) unit(?:s)? that attack has "
                    r"(?:the )?(?P<keyword>[a-z0-9 ]+) ability",
                    r"each time (?:this model|a model in this unit) makes an? (?:melee |ranged )?attack "
                    r"with (?:(?:its|the|an?) )?(?P<weapon>[a-z0-9 ]+?) against "
                    r"(?:an? )?(?:enemy )?(?P<targets>[a-z0-9 ]+?) unit(?:s)? that attack has "
                    r"(?:the )?(?P<keyword>[a-z0-9 ]+) ability",
                ):
                    match = re.fullmatch(pattern, normalized)
                    if match:
                        break
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
                if re.search(r"\bexcluding\b", raw_targets):
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
        try:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            gk_mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
            keyword_rule_fn = (
                getattr(gk_mgr, "banishers_chaos_bane_attack_keyword_rule", None)
                if gk_mgr is not None
                else None
            )
            if callable(keyword_rule_fn):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                keyword_rule = keyword_rule_fn(
                    model,
                    attack_type=attack_type or "any",
                    weapon_profile=weapon_profile,
                    game=game,
                )
                if isinstance(keyword_rule, dict):
                    rules.append(dict(keyword_rule))
        except Exception:
            pass
        try:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            ia_mgr = getattr(army, "imperial_agents_detachments", None) if army is not None else None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            for helper_name in (
                "violent_acquisition_attack_keyword_bonus_rules",
                "dispense_justice_attack_keyword_bonus_rules",
                "execution_order_attack_keyword_bonus_rules",
                "psybolt_ammunition_attack_keyword_bonus_rules",
                "rites_of_exorcism_attack_keyword_bonus_rules",
            ):
                keyword_rules_fn = getattr(ia_mgr, helper_name, None) if ia_mgr is not None else None
                if not callable(keyword_rules_fn):
                    continue
                rules.extend(
                    list(
                        keyword_rules_fn(
                            model,
                            target,
                            attacker_unit=root,
                            attack_type=attack_type or "any",
                            weapon_profile=weapon_profile,
                            game=game,
                            game_map=game_map,
                        )
                        or []
                    )
                )
        except Exception:
            pass
        if model is not None and target is not None:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            gsc_mgr = getattr(army, "genestealer_cults_detachments", None) if army is not None else None
            sustained_fn = getattr(gsc_mgr, "final_day_inhuman_integration_sustained_hits_value", None) if gsc_mgr is not None else None
            if callable(sustained_fn):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                sustained_value, source = sustained_fn(
                    model,
                    target,
                    game=game,
                    game_map=game_map,
                    weapon_profile=weapon_profile,
                )
                if int(sustained_value or 0) > 0:
                    rules.append(
                        {
                            "attack_type": "any",
                            "keyword": f"SUSTAINED HITS {int(sustained_value)}",
                            "source": str(source or "Inhuman Integration").strip() or "Inhuman Integration",
                        }
                    )
            close_range_fn = getattr(gsc_mgr, "outlander_claw_close_range_shoot_out_lethal_hits", None) if gsc_mgr is not None else None
            if callable(close_range_fn):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                active, source = close_range_fn(
                    model,
                    target,
                    game=game,
                    game_map=game_map,
                    weapon_profile=weapon_profile,
                )
                if bool(active):
                    rules.append(
                        {
                            "attack_type": "ranged",
                            "keyword": "LETHAL HITS",
                            "source": str(source or "Close-range Shoot-out").strip() or "Close-range Shoot-out",
                        }
                    )
        atype = str(attack_type or "").strip().lower()
        is_melee_attack = atype in ("", "any", "melee")
        is_ranged_attack = atype in ("", "any", "ranged")
        if is_ranged_attack and model is not None:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            sustained_fn = (
                getattr(sm_mgr, "armoured_speartip_shock_deployment_sustained_hits_value", None)
                if sm_mgr is not None
                else None
            )
            if callable(sustained_fn):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                sustained_value, source = sustained_fn(model, weapon_profile=weapon_profile, game=game)
                if int(sustained_value or 0) > 0:
                    rules.append(
                        {
                            "attack_type": "ranged",
                            "keyword": f"SUSTAINED HITS {int(sustained_value)}",
                            "source": str(source or "Shock Deployment").strip() or "Shock Deployment",
                        }
                    )
            firestorm_fn = (
                getattr(sm_mgr, "headhunter_firestorm_coordinators_sustained_hits_value", None)
                if sm_mgr is not None
                else None
            )
            if callable(firestorm_fn):
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                sustained_value, source = firestorm_fn(model, weapon_profile=weapon_profile, game=game)
                if int(sustained_value or 0) > 0:
                    rules.append(
                        {
                            "attack_type": "ranged",
                            "keyword": f"SUSTAINED HITS {int(sustained_value)}",
                            "source": str(source or "Firestorm Coordinators").strip() or "Firestorm Coordinators",
                        }
                    )
        if (
            is_melee_attack
            and model is not None
            and self._attached_unit_model_is_enhancement_bearer(
                model,
                flag_key="enhancement_unflinching_will",
                enhancement_id="000008550003",
                enhancement_name="unflinching will",
                require_leading=False,
            )
        ):
            source_name = "Unflinching Will"
            anti_keyword = "INFANTRY"
            anti_value = 5
            members = list(root.get_attached_unit_members() or []) if hasattr(root, "get_attached_unit_members") else [root]
            if not members:
                members = [root]
            for member in members:
                member_sr = getattr(member, "special_rules", None)
                if not isinstance(member_sr, dict) or not bool(member_sr.get("enhancement_unflinching_will")):
                    continue
                source_name = str(member_sr.get("enhancement_unflinching_will_source", "") or "").strip() or "Unflinching Will"
                anti_keyword = (
                    str(member_sr.get("enhancement_unflinching_will_anti_keyword", "INFANTRY") or "INFANTRY").strip().upper()
                    or "INFANTRY"
                )
                anti_value = int(member_sr.get("enhancement_unflinching_will_anti_value", 5) or 5)
                break
            rules.extend(
                [
                    {
                        "attack_type": "melee",
                        "keyword": "PRECISION",
                        "source": source_name,
                    },
                    {
                        "attack_type": "melee",
                        "keyword": f"ANTI-{anti_keyword} {int(max(2, anti_value))}+",
                        "source": source_name,
                    },
                ]
            )
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
        if isinstance(sr, dict) and bool(sr.get("enhancement_speedwaaagh_dakkamek_active")) and model is not None:
            apply_bonus = True
            effect_attack_type = str(sr.get("enhancement_speedwaaagh_dakkamek_attack_type", "ranged") or "ranged").strip().lower()
            if effect_attack_type not in ("any", "melee", "ranged"):
                effect_attack_type = "ranged"
            attack_kind = str(attack_type or "").strip().lower()
            if attack_kind and effect_attack_type not in ("any", attack_kind):
                apply_bonus = False
            target_model_id = str(sr.get("enhancement_speedwaaagh_dakkamek_target_model_id", "") or "").strip()
            if apply_bonus and target_model_id and not self._model_matches_identifier(model, target_model_id):
                apply_bonus = False
            if apply_bonus:
                source_name = str(sr.get("enhancement_speedwaaagh_dakkamek_source", "") or "Dakkamek").strip() or "Dakkamek"
                for keyword in list(sr.get("enhancement_speedwaaagh_dakkamek_weapon_keywords", []) or []):
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
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        necrons_mgr = getattr(army, "necrons_detachments", None) if army is not None else None
        necrons_bonus_fn = getattr(necrons_mgr, "canoptek_court_attack_keyword_bonus_rules", None) if necrons_mgr is not None else None
        if callable(necrons_bonus_fn):
            rules.extend(
                list(
                    necrons_bonus_fn(
                        model,
                        target,
                        attack_type=attack_type or "",
                        weapon_profile=weapon_profile,
                    )
                    or []
                )
            )
        cursed_necrons_bonus_fn = getattr(necrons_mgr, "cursed_legion_attack_keyword_bonus_rules", None) if necrons_mgr is not None else None
        if callable(cursed_necrons_bonus_fn):
            rules.extend(
                list(
                    cursed_necrons_bonus_fn(
                        model,
                        target,
                        attack_type=attack_type or "",
                        weapon_profile=weapon_profile,
                    )
                    or []
                )
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
                    attacker_keyword_phrase = str(effect.get("attacker_keyword_phrase", "") or "").strip()
                    if attacker_keyword_phrase:
                        matches_keyword = False
                        match_fn = getattr(root, "_unit_matches_keyword_phrase", None)
                        if callable(match_fn):
                            matches_keyword = bool(
                                match_fn(root, attacker_keyword_phrase, use_effective=True)
                            )
                        if not matches_keyword:
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
                    weapon_profile=weapon_profile,
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
