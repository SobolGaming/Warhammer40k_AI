from __future__ import annotations

import re

from ._common import Model


class CombatRuntimeMixin:
    """Combat and characteristic-resolution helpers kept out of `unit.py`."""

    def _add_stat_additive(self, key: str, delta: int) -> None:
        from ...utility.modifiers import Modifier, ModifierOp

        self.add_characteristic_modifier(key, Modifier(ModifierOp.ADD, int(delta), source="damaged_profile"))
        self._damaged_profile_stat_deltas[key] = int(self._damaged_profile_stat_deltas.get(key, 0)) + int(delta)

    def _clear_damaged_profile_effects(self) -> None:
        try:
            self.remove_characteristic_modifiers_by_source("damaged_profile")
        except Exception:
            pass
        self._damaged_profile_stat_deltas = {}
        try:
            if getattr(self, "special_rules", None) is None:
                self.special_rules = {}
            for key in (
                "damaged_hit_roll_modifier",
                "damaged_half_attacks",
                "damaged_melee_attacks_bonus",
                "damaged_attacks_bonus_weapon_name",
                "damaged_attacks_bonus_weapon_amount",
                "relics_of_matriarchs_max_choices",
            ):
                if key in self.special_rules:
                    del self.special_rules[key]
        except Exception:
            pass
        self._damaged_profile_active = False

    def add_characteristic_modifier(self, characteristic: str, modifier) -> None:
        if not characteristic:
            return
        if getattr(self, "_characteristic_modifiers", None) is None:
            self._characteristic_modifiers = {}
        key = str(characteristic).strip().lower()
        self._characteristic_modifiers.setdefault(key, []).append(modifier)

    def remove_characteristic_modifiers_by_source(self, source_prefix: str) -> None:
        if getattr(self, "_characteristic_modifiers", None) is None:
            return
        prefix = str(source_prefix or "")
        if not prefix:
            return
        for key, modifiers in list(self._characteristic_modifiers.items()):
            kept = []
            for modifier in list(modifiers or []):
                try:
                    if str(getattr(modifier, "source", "") or "").startswith(prefix):
                        continue
                except Exception:
                    pass
                kept.append(modifier)
            self._characteristic_modifiers[key] = kept

    def _collect_characteristic_modifiers(
        self,
        model: Model,
        ckey: str,
        *,
        base_val: int,
        base_raw=None,
        game_map=None,
    ):
        return getattr(type(self), "_collect_characteristic_modifiers_impl", lambda *_args, **_kwargs: ([], 0, game_map))(
            self,
            model,
            ckey,
            base_val=base_val,
            base_raw=base_raw,
            game_map=game_map,
        )

    def get_effective_model_characteristic(self, model: Model, characteristic: str, *, game_map=None) -> int:
        return getattr(type(self), "get_effective_model_characteristic_impl", lambda *_args, **_kwargs: 0)(
            self,
            model,
            characteristic,
            game_map=game_map,
        )

    def _apply_damaged_profile_effects(self, profile_text: str) -> None:
        self._clear_damaged_profile_effects()
        text = (profile_text or "").replace("\u2019", "'")
        text = re.sub(r"\s+", " ", text).strip()
        lowered = text.lower()
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}

        match = re.search(r"subtract\s+(\d+)\s+from\s+the\s+hit\s+roll", lowered)
        if match:
            try:
                self.special_rules["damaged_hit_roll_modifier"] = -int(match.group(1))
            except Exception:
                pass

        match = re.search(r"subtract\s+(\d+)\s+from\s+(?:this\s+(?:model|unit)'?s|its)\s+objective\s+control\s+characteristic", lowered)
        if match:
            try:
                self._add_stat_additive("objective_control", -int(match.group(1)))
            except Exception:
                pass

        match = re.search(r"subtract\s+(\d+)\s*(?:\"|inches)?\s+from\s+(?:this\s+model'?s|its)\s+move\s+characteristic", lowered)
        if match:
            try:
                self._add_stat_additive("movement", -int(match.group(1)))
            except Exception:
                pass

        if ("halve the attacks characteristic" in lowered and "weapon" in lowered) or ("attacks characteristics of all of its weapons are halved" in lowered):
            self.special_rules["damaged_half_attacks"] = True

        match = re.search(r"add\s+(\d+)\s+to\s+the\s+attacks\s+characteristic\s+of\s+this\s+model'?s\s+melee\s+weapons", lowered)
        if match:
            try:
                self.special_rules["damaged_melee_attacks_bonus"] = int(match.group(1))
            except Exception:
                pass

        match = re.search(r"add\s+(\d+)\s+to\s+the\s+attacks\s+characteristic\s+of\s+this\s+model'?s\s+([a-z0-9 \\-']+)", lowered)
        if match and "melee weapons" not in lowered:
            try:
                amount = int(match.group(1))
                weapon_name = match.group(2).strip().rstrip(".")
                if weapon_name and weapon_name not in ("weapons", "weapon"):
                    self.special_rules["damaged_attacks_bonus_weapon_name"] = weapon_name
                    self.special_rules["damaged_attacks_bonus_weapon_amount"] = amount
            except Exception:
                pass

        if "relics of the matriarchs" in lowered and "only select one ability" in lowered:
            self.special_rules["relics_of_matriarchs_max_choices"] = 1
        self._damaged_profile_active = True

    def _parse_against_attack_characteristic_defensive_rules(self) -> None:
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        try:
            if "armor_save_bonus_vs_damage_characteristic" in self.special_rules:
                del self.special_rules["armor_save_bonus_vs_damage_characteristic"]
        except Exception:
            pass
        try:
            if "armor_save_bonus_vs_damage_characteristic_entries" in self.special_rules:
                del self.special_rules["armor_save_bonus_vs_damage_characteristic_entries"]
        except Exception:
            pass
        try:
            if "allocated_damage_reductions" in self.special_rules:
                del self.special_rules["allocated_damage_reductions"]
        except Exception:
            pass
        try:
            if "defensive_ap_worsen" in self.special_rules:
                del self.special_rules["defensive_ap_worsen"]
        except Exception:
            pass
        try:
            entries = self.special_rules.get("defensive_wound_mods")
            if isinstance(entries, list):
                kept = [
                    entry
                    for entry in entries
                    if not isinstance(entry, dict)
                    or entry.get("tag") not in (
                        "ability:strength_gt_toughness_wound_penalty",
                        "ability:defensive_wound_penalty",
                    )
                ]
                if kept:
                    self.special_rules["defensive_wound_mods"] = kept
                elif "defensive_wound_mods" in self.special_rules:
                    del self.special_rules["defensive_wound_mods"]
        except Exception:
            pass

        entries = []
        for ability in self._iter_active_possible_abilities():
            if isinstance(ability, str):
                entries.append(("", ability))
            else:
                name = str(getattr(ability, "name", "") or "")
                description = str(getattr(ability, "description", "") or "")
                entries.append((name, description or name))
        for ability, _leader in self._iter_attached_leader_leading_abilities():
            try:
                if isinstance(ability, str):
                    name = str(ability or "")
                    description = str(ability or "")
                else:
                    name = str(getattr(ability, "name", "") or "")
                    description = str(getattr(ability, "description", "") or "") or name
            except Exception:
                continue
            entries.append((name, description or name))
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in members:
            if member is None or member is root:
                continue
            if getattr(member, "attached_to", None) is not root:
                continue
            iter_entries = getattr(member, "_iter_ability_entries_for_rules", None)
            if not callable(iter_entries):
                continue
            for name, description in iter_entries(model=None):
                raw_text = str(description or name or "")
                if not raw_text:
                    continue
                normalized = raw_text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "this model s unit" not in normalized:
                    continue
                entries.append((str(name or ""), raw_text))

        def _normalize_leading_keyword(raw_kw: str) -> str:
            keyword = str(raw_kw or "").strip()
            if not keyword:
                return ""
            keyword = self._normalize_keyword_phrase(keyword) or keyword.upper()
            keyword = re.sub(r"\bmodels?\b$", "", keyword).strip()
            return keyword

        for name, raw in entries:
            text = self._normalize_rules_text(raw)
            if not text:
                continue
            lowered = text.lower()
            sentences = [part.strip() for part in re.split(r"[.;]\s*", raw or "") if part.strip()]

            matched_conditional_damage_save_bonus = False
            match = re.search(
                r"while\s+this\s+unit\s+is\s+within\s+range\s+of\s+an\s+objective\s+marker\s+you\s+control,\s+"
                r"each\s+time\s+an\s+attack\s+with\s+a\s+damage\s+characteristic\s+of\s+(\d+)\s+is\s+allocated\s+to\s+a\s+model\s+in\s+this\s+unit,\s+"
                r"add\s+(\d+)\s+to\s+any\s+armou?r\s+saving\s+throw\s+made\s+against\s+that\s+attack",
                lowered,
                flags=re.IGNORECASE,
            )
            if match:
                damage = int(match.group(1))
                bonus = int(match.group(2))
                damage_entries = self.special_rules.get("armor_save_bonus_vs_damage_characteristic_entries")
                if not isinstance(damage_entries, list):
                    damage_entries = []
                damage_entries.append(
                    {
                        "damage_characteristic": int(damage),
                        "value": int(bonus),
                        "requires_objective_controlled": True,
                        "source": str(name or "Ability").strip() or "Ability",
                    }
                )
                self.special_rules["armor_save_bonus_vs_damage_characteristic_entries"] = damage_entries
                matched_conditional_damage_save_bonus = True
            else:
                match = re.search(
                    r"each\s+time\s+an\s+attack\s+with\s+a\s+damage\s+characteristic\s+of\s+(\d+)\s+is\s+allocated\s+to\s+a\s+model\s+in\s+this\s+unit,\s+add\s+(\d+)\s+to\s+any\s+armou?r\s+saving\s+throw\s+made\s+against\s+that\s+attack",
                    lowered,
                    flags=re.IGNORECASE,
                )
            if match and not matched_conditional_damage_save_bonus:
                damage = int(match.group(1))
                bonus = int(match.group(2))
                spec = self.special_rules.get("armor_save_bonus_vs_damage_characteristic")
                if not isinstance(spec, dict):
                    spec = {}
                spec[int(damage)] = int(spec.get(int(damage), 0)) + int(bonus)
                self.special_rules["armor_save_bonus_vs_damage_characteristic"] = spec

            match = re.search(
                r"each\s+time\s+(?:an|a)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+is\s+allocated\s+to\s+"
                r"(?:this\s+model|a\s+model\s+in\s+this\s+unit)\s*,\s*"
                r"subtract\s+(?P<val>\d+)\s+from\s+the\s+damage\s+characteristic\s+of\s+that\s+attack",
                lowered,
                flags=re.IGNORECASE,
            )
            if match:
                try:
                    value = int(match.group("val"))
                except Exception:
                    value = 0
                if value:
                    attack_type = (match.group("atype") or "any").strip().lower()
                    label = (name or "Damage reduction ability").strip() or "Damage reduction ability"
                    special_rules = self.special_rules
                    items = list(special_rules.get("allocated_damage_reductions", []) or [])
                    items.append(
                        {
                            "value": int(value),
                            "attack_type": attack_type,
                            "source": label,
                            "op": "sub",
                        }
                    )
                    special_rules["allocated_damage_reductions"] = items
                    self.special_rules = special_rules

            match = re.search(
                r"each\s+time\s+(?:an|a)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+is\s+allocated\s+to\s+"
                r"(?:this\s+model|a\s+model\s+in\s+this\s+unit)\s*,\s*"
                r"(?:halve|half)\s+the\s+damage\s+characteristic\s+of\s+that\s+attack",
                lowered,
                flags=re.IGNORECASE,
            )
            if not match:
                match = re.search(
                    r"each\s+time\s+(?:an|a)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+is\s+allocated\s+to\s+"
                    r"(?:this\s+model|a\s+model\s+in\s+this\s+unit).*?"
                    r"damage\s+characteristic\s+of\s+that\s+attack\s+is\s+halved",
                    lowered,
                    flags=re.IGNORECASE,
                )
            if match:
                attack_type = (match.group("atype") or "any").strip().lower()
                label = (name or "Damage halving ability").strip() or "Damage halving ability"
                special_rules = self.special_rules
                items = list(special_rules.get("allocated_damage_reductions", []) or [])
                items.append(
                    {
                        "value": 2,
                        "attack_type": attack_type,
                        "source": label,
                        "op": "div",
                    }
                )
                special_rules["allocated_damage_reductions"] = items
                self.special_rules = special_rules

            seen_generic_wound_mods = set()
            for sentence in sentences:
                if not sentence:
                    continue
                normalized = self._normalize_rules_text(sentence)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"'s\b", "s", normalized)
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "strength characteristic" in normalized:
                    continue
                pattern = (
                    r"(?:while (?:(?:a|an|the) (?P<lemma>[a-z0-9 ]+)|this)(?: model)? is leading (?:this|a) unit |"
                    r"while this unit contains one or more (?P<lemma_contains>[a-z0-9 ]+) models )?"
                    r"each time (?:an|a) (?:(?P<atype>melee|ranged) )?attack(?:s)? "
                    r"(?:targets|target|is allocated to|is made against) "
                    r"(?:this model|this unit|this model s unit|that unit|a model in this unit|the bearer) "
                    r"subtract (?P<val>\d+) from (?:the|that|that attacks) wound roll(?:s)?"
                )
                match = re.fullmatch(pattern, normalized)
                if not match:
                    continue
                try:
                    value = int(match.group("val"))
                except Exception:
                    value = 0
                if not value:
                    continue
                attack_type = (match.group("atype") or "any").strip().lower()
                leader_kw = _normalize_leading_keyword(match.group("lemma"))
                contains_kw = _normalize_leading_keyword(match.group("lemma_contains"))
                label = (name or "Defensive ability").strip() or "Defensive ability"
                key = (label.lower(), attack_type, int(value), leader_kw or "", contains_kw or "")
                if key in seen_generic_wound_mods:
                    continue
                seen_generic_wound_mods.add(key)
                special_rules = self.special_rules
                items = list(special_rules.get("defensive_wound_mods", []) or [])
                entry = {
                    "value": int(value),
                    "attack_type": attack_type,
                    "source": label,
                    "tag": "ability:defensive_wound_penalty",
                }
                if leader_kw:
                    entry["requires_leading_keyword"] = str(leader_kw)
                if contains_kw:
                    entry["requires_unit_contains_keyword"] = str(contains_kw)
                items.append(entry)
                special_rules["defensive_wound_mods"] = items
                self.special_rules = special_rules

            seen_wound_mods = set()
            for sentence in sentences:
                if not sentence:
                    continue
                normalized = self._normalize_rules_text(sentence)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"'s\b", "s", normalized)
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                pattern = (
                    r"(?:while (?:(?:a|an|the) (?P<lemma>[a-z0-9 ]+)|this)(?: model)? is leading (?:this|a) unit )?"
                    r"each time (?:an|a) (?:(?P<atype>melee|ranged) )?attack(?:s)? "
                    r"(?:targets|target|is allocated to) "
                    r"(?:this model|this unit|this model s unit|a model in this unit|the bearer) "
                    r"if (?:the )?(?:strength characteristic of that attack|that attacks strength characteristic) "
                    r"is greater than(?P<inclusive> or equal to)? "
                    r"(?:the toughness characteristic of (?:this model|this unit|that model|that unit)|(?:this model|this unit|that model|that unit)s toughness characteristic) "
                    r"subtract (?P<val>\d+) from (?:the|that|that attacks) wound roll(?:s)?"
                )
                match = re.fullmatch(pattern, normalized)
                if not match:
                    continue
                try:
                    value = int(match.group("val"))
                except Exception:
                    value = 0
                if not value:
                    continue
                attack_type = (match.group("atype") or "any").strip().lower()
                leader_kw = _normalize_leading_keyword(match.group("lemma"))
                label = (name or "Defensive ability").strip() or "Defensive ability"
                inclusive = bool(match.group("inclusive"))
                key = (label.lower(), attack_type, int(value), leader_kw or "", bool(inclusive))
                if key in seen_wound_mods:
                    continue
                seen_wound_mods.add(key)
                special_rules = self.special_rules
                items = list(special_rules.get("defensive_wound_mods", []) or [])
                entry = {
                    "value": int(value),
                    "attack_type": attack_type,
                    "source": label,
                    "requires_strength_gte_toughness" if inclusive else "requires_strength_gt_toughness": True,
                    "tag": "ability:strength_gt_toughness_wound_penalty",
                }
                if leader_kw:
                    entry["requires_leading_keyword"] = str(leader_kw)
                items.append(entry)
                special_rules["defensive_wound_mods"] = items
                self.special_rules = special_rules

            seen_ap_worsen = set()
            for sentence in sentences:
                if not sentence:
                    continue
                normalized = self._normalize_rules_text(sentence)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"'s\b", "s", normalized)
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                pattern = (
                    r"(?:while (?:(?:a|an|the) (?P<lemma>[a-z0-9 ]+)|this)(?: model)? is leading (?:this|a) unit )?"
                    r"each time (?:an|a) (?:(?P<atype>melee|ranged) )?attack(?:s)? "
                    r"(?:targets|target|is allocated to|is made against) "
                    r"(?:this model|this unit|this model s unit|that unit|the bearer|the bearer s unit) "
                    r"worsen the armou?r penetration characteristic of that attack by (?P<val>\d+)"
                )
                match = re.fullmatch(pattern, normalized)
                if not match:
                    continue
                try:
                    value = int(match.group("val"))
                except Exception:
                    value = 0
                if not value:
                    continue
                attack_type = (match.group("atype") or "any").strip().lower()
                leader_kw = _normalize_leading_keyword(match.group("lemma"))
                label = (name or "Defensive ability").strip() or "Defensive ability"
                key = (label.lower(), attack_type, int(value), leader_kw or "")
                if key in seen_ap_worsen:
                    continue
                seen_ap_worsen.add(key)
                special_rules = self.special_rules
                items = list(special_rules.get("defensive_ap_worsen", []) or [])
                entry = {
                    "value": int(value),
                    "attack_type": attack_type,
                    "source": label,
                    "tag": "ability:defensive_ap_worsen",
                }
                if leader_kw:
                    entry["requires_leading_keyword"] = str(leader_kw)
                items.append(entry)
                special_rules["defensive_ap_worsen"] = items
                self.special_rules = special_rules

    def _matches_enemy_melee_hazardous_while_targeted(self, text: str) -> bool:
        if not text:
            return False
        normalized = self._normalize_rules_text(text)
        if not normalized:
            return False
        normalized = normalized.replace("\u2019", "'").lower().strip()
        normalized = re.sub(r"'s\b", "s", normalized)
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return bool(self._ENEMY_MELEE_HAZARDOUS_WHILE_TARGETING_RE.search(normalized))

    def enemy_melee_weapons_hazardous_while_targeted(self) -> list[str]:
        root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
        cache_key = "enemy_melee_hazardous_while_targeted"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return cache[cache_key]

        sources: list[str] = []
        members = root.get_attached_unit_members() if hasattr(root, "get_attached_unit_members") else [root]
        for unit in members:
            for ability in unit._iter_active_possible_abilities():
                if isinstance(ability, str):
                    name = ability
                    desc = ability
                else:
                    name = str(getattr(ability, "name", "") or "")
                    desc = str(getattr(ability, "description", "") or "")
                text = desc or name
                if text and self._matches_enemy_melee_hazardous_while_targeted(text):
                    sources.append(name or "Ability")
            for model in list(getattr(unit, "models", []) or []):
                abilities = getattr(model, "abilities", {}) or {}
                for ability in abilities.values():
                    if isinstance(ability, str):
                        name = ability
                        desc = ability
                    else:
                        name = str(getattr(ability, "name", "") or "")
                        desc = str(getattr(ability, "description", "") or "")
                    text = desc or name
                    if text and self._matches_enemy_melee_hazardous_while_targeted(text):
                        sources.append(name or "Ability")

        deduped: list[str] = []
        seen: set[str] = set()
        for source in sources:
            key = str(source or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(key)

        if not isinstance(cache, dict):
            root._ability_cache = {}
            cache = root._ability_cache
        cache[cache_key] = deduped
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict) or not bool(special_rules.get("space_marines_librarius_fiery_shield_active")):
            return deduped

        apply_effect = True
        army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
        game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        if game is not None:
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            expires_phase = str(special_rules.get("space_marines_librarius_fiery_shield_expires_phase", "") or "").strip().upper()
            if expires_phase and phase_name and phase_name != expires_phase:
                apply_effect = False
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                current_turn = 0
            try:
                effect_turn = int(special_rules.get("space_marines_librarius_fiery_shield_turn", 0) or 0)
            except Exception:
                effect_turn = 0
            if effect_turn and current_turn and effect_turn != current_turn:
                apply_effect = False
        if not bool(special_rules.get("space_marines_librarius_fiery_shield_melee_hazardous")):
            apply_effect = False
        if not apply_effect:
            return deduped

        source_name = str(special_rules.get("space_marines_librarius_fiery_shield_source", "") or "FIERY SHIELD").strip() or "FIERY SHIELD"
        if source_name not in deduped:
            deduped = list(deduped) + [source_name]
        return deduped
