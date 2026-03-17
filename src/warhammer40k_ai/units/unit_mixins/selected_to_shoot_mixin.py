"""Selected-to-shoot utility helpers shared by datasheet and enhancement rules."""

from __future__ import annotations

from ._common import *


class SelectedToShootMixin:
    def _selected_to_shoot_root(self):
        root_getter = getattr(self, "get_attached_unit_root", None)
        root = root_getter() if callable(root_getter) else self
        return root if root is not None else self

    def _selected_to_shoot_member_units(self) -> list["Unit"]:
        root = self._selected_to_shoot_root()
        members_getter = getattr(root, "get_attached_unit_members", None)
        members = list(members_getter() or []) if callable(members_getter) else [root]
        if not members:
            members = [root]
        members.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return members

    @staticmethod
    def _selected_to_shoot_model_is_alive(model: Optional["Model"]) -> bool:
        if model is None:
            return False
        alive_attr = getattr(model, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    @staticmethod
    def _selected_to_shoot_model_matches_id(model: Optional["Model"], source_model_id: str) -> bool:
        if model is None:
            return False
        source_id = str(source_model_id or "").strip()
        if not source_id:
            return False
        entity_id = str(get_entity_id(model) or "").strip()
        if entity_id and entity_id == source_id:
            return True
        local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
        return bool(local_id and local_id == source_id)

    def _selected_to_shoot_find_member_model(self, member, *, source_model_id: str):
        models = list(getattr(member, "models", []) or [])
        models.sort(key=lambda model: str(get_entity_id(model) or ""))
        source_id = str(source_model_id or "").strip()
        if source_id:
            for model in models:
                if self._selected_to_shoot_model_matches_id(model, source_id):
                    return model
        return None

    def _selected_to_shoot_models(self, *, root=None) -> list["Model"]:
        if root is None:
            root = self._selected_to_shoot_root()
        models_getter = getattr(root, "get_attached_unit_models", None)
        models = list(models_getter() or []) if callable(models_getter) else list(getattr(root, "models", []) or [])
        models = [model for model in models if self._selected_to_shoot_model_is_alive(model)]
        models.sort(key=lambda model: str(get_entity_id(model) or ""))
        return models

    def _selected_to_shoot_ranged_weapon_names_for_model(self, model: Optional["Model"]) -> list[str]:
        if model is None:
            return []
        names: list[str] = []
        seen: set[str] = set()
        for wargear in list(getattr(model, "wargear", []) or []):
            if wargear is None:
                continue
            is_ranged = getattr(wargear, "is_ranged", None)
            if not callable(is_ranged) or not bool(is_ranged()):
                continue
            weapon_name = str(getattr(wargear, "name", "") or "").strip()
            if not weapon_name:
                continue
            weapon_key = self._norm_wargear_name(weapon_name)
            if not weapon_key or weapon_key in seen:
                continue
            seen.add(weapon_key)
            names.append(weapon_name)
        names.sort(key=self._norm_wargear_name)
        return names

    def _selected_to_shoot_weapon_name_matches(self, weapon_name: str, required_names: list[str]) -> bool:
        actual = self._norm_wargear_name(str(weapon_name or ""))
        if not actual:
            return False
        actual_variants = {actual, actual.rstrip("s")}
        for required_name in list(required_names or []):
            required = self._norm_wargear_name(str(required_name or ""))
            if not required:
                continue
            required_variants = {required, required.rstrip("s")}
            if actual_variants & required_variants:
                return True
        return False

    def _selected_to_shoot_next_sequence(self, ability_key: str) -> int:
        root = self._selected_to_shoot_root()
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        normalized_key = re.sub(r"[^a-z0-9]+", "_", str(ability_key or "").strip().lower()).strip("_")
        if not normalized_key:
            normalized_key = "selected_to_shoot"
        sequence_key = f"selected_to_shoot_{normalized_key}_sequence"
        current = int(special_rules.get(sequence_key, 0) or 0)
        next_value = int(current + 1)
        special_rules[sequence_key] = int(next_value)
        root.special_rules = special_rules
        return int(next_value)

    def selected_to_shoot_try_dat_button_roll_count(self, *, trigger: str = "") -> int:
        trigger_key = str(trigger or "").strip().lower()
        if trigger_key != "shooting":
            return 1
        extra_rolls = 0
        for member in self._selected_to_shoot_member_units():
            special_rules = getattr(member, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            if not bool(special_rules.get("enhancement_press_it_fasta", False)):
                continue
            bearer = self._selected_to_shoot_find_member_model(
                member,
                source_model_id=str(
                    special_rules.get("enhancement_press_it_fasta_bearer_model_id", "")
                    or special_rules.get("enhancement_bearer_model_id", "")
                    or ""
                ).strip(),
            )
            if bearer is not None and not self._selected_to_shoot_model_is_alive(bearer):
                continue
            bonus_rolls = int(special_rules.get("enhancement_press_it_fasta_extra_rolls", 1) or 1)
            if bonus_rolls > 0:
                extra_rolls += int(bonus_rolls)
        return max(1, int(1 + extra_rolls))

    def unit_selected_to_shoot_roll_table_specs(self) -> list[dict]:
        root = self._selected_to_shoot_root()
        cache_key = "unit_selected_to_shoot_roll_table_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str]] = set()
        pattern = re.compile(
            r"each time this unit is selected to shoot you can roll one d6 "
            r"on a 1 2 this unit suffers d3 mortal wounds "
            r"on a 3 4 until the end of the phase add 1 to the strength characteristic of ranged weapons equipped by models in this unit "
            r"on a 5 6 until the end of the phase add 1 to the attacks characteristic of ranged weapons equipped by models in this unit"
        )

        for member in self._selected_to_shoot_member_units():
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                text_src = member._strip_eligibility_prefix(desc or name or "")
                normalized = member._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not pattern.fullmatch(normalized):
                    continue
                source = str(name or "Selected to shoot roll table").strip() or "Selected to shoot roll table"
                ability_key = re.sub(
                    r"[^a-z0-9]+",
                    "_",
                    str(self._normalize_keyword_phrase(source) or "selected_to_shoot_roll_table").strip().lower(),
                ).strip("_")
                if not ability_key:
                    ability_key = "selected_to_shoot_roll_table"
                dedupe_key = (source.lower(), ability_key)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                specs.append(
                    {
                        "source": source,
                        "ability_key": ability_key,
                        "roll_branches": {
                            "1": {"self_mortal_wounds_roll": "D3"},
                            "2": {"self_mortal_wounds_roll": "D3"},
                            "3": {"strength_bonus": 1},
                            "4": {"strength_bonus": 1},
                            "5": {"attacks_bonus": 1},
                            "6": {"attacks_bonus": 1},
                        },
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def iter_selected_to_shoot_model_ranged_bonus_specs(self) -> list[dict]:
        root = self._selected_to_shoot_root()
        specs: list[dict] = []
        seen: set[tuple[str, str, str]] = set()
        pattern = re.compile(
            r"once per battle when the bearer s unit is selected to shoot in your shooting phase "
            r"the bearer can use its pulsa rokkit "
            r"if it does until the end of the phase improve the strength and armour penetration characteristics of ranged weapons equipped by models in the bearer s unit by 1"
        )

        for member in self._selected_to_shoot_member_units():
            models = list(getattr(member, "models", []) or [])
            models.sort(key=lambda model: str(get_entity_id(model) or ""))
            if not models:
                continue
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                text_src = member._strip_eligibility_prefix(desc or name or "")
                normalized = member._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not pattern.fullmatch(normalized):
                    continue
                source = str(name or "Pulsa Rokkit").strip() or "Pulsa Rokkit"
                source_key = self._norm_wargear_name(source)
                bearer_models: list["Model"] = []
                for model in models:
                    option_names = [
                        self._norm_wargear_name(str(option_name or ""))
                        for option_name in list(getattr(model, "optional_wargear", []) or [])
                    ]
                    ability_names = [
                        self._norm_wargear_name(str(ability_name or ""))
                        for ability_name in list(getattr(model, "abilities", {}) or {})
                    ]
                    if source_key in option_names or source_key in ability_names:
                        bearer_models.append(model)
                if not bearer_models and len(models) == 1:
                    bearer_models = list(models)
                for model in bearer_models:
                    model_id = str(get_entity_id(model) or "")
                    dedupe_key = (source.lower(), "pulsa_rokkit", model_id)
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    specs.append(
                        {
                            "source": source,
                            "ability_key": "pulsa_rokkit",
                            "model": model,
                            "model_id": model_id,
                            "strength_bonus": 1,
                            "ap_bonus": 1,
                        }
                    )
        specs.sort(
            key=lambda spec: (
                str(spec.get("model_id", "") or ""),
                str(spec.get("ability_key", "") or ""),
                str(spec.get("source", "") or "").lower(),
            )
        )
        return specs

    def iter_selected_to_shoot_model_target_attack_keyword_specs(self) -> list[dict]:
        root = self._selected_to_shoot_root()
        specs: list[dict] = []
        seen: set[tuple[str, str, str, int, tuple[str, ...], str]] = set()
        pattern = re.compile(
            r"each time this model s unit is selected to shoot you can select one enemy unit within (?P<range>\d+) "
            r"of and visible to this model until the end of the phase ranged weapons equipped by models in this model s unit "
            r"have the (?P<keyword>[a-z0-9 +\-]+) ability when targeting that enemy unit"
        )

        for member in self._selected_to_shoot_member_units():
            models = [
                model
                for model in list(getattr(member, "models", []) or [])
                if self._selected_to_shoot_model_is_alive(model)
            ]
            models.sort(key=lambda model: str(get_entity_id(model) or ""))
            if len(models) != 1:
                continue
            bearer_model = models[0]
            model_id = str(get_entity_id(bearer_model) or "")
            if not model_id:
                continue
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                text_src = member._strip_eligibility_prefix(desc or name or "")
                normalized = member._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = pattern.fullmatch(normalized)
                if not m:
                    continue
                try:
                    range_value = int(m.group("range") or 0)
                except (TypeError, ValueError):
                    range_value = 0
                if range_value <= 0:
                    continue
                keyword_raw = str(m.group("keyword") or "").strip()
                keyword = str(member._normalize_keyword_phrase(keyword_raw) or keyword_raw).strip().upper()
                if not keyword:
                    continue
                source = str(name or "Selected to shoot").strip() or "Selected to shoot"
                dedupe_key = (
                    source.lower(),
                    model_id,
                    "selected_to_shoot_target_attack_keywords",
                    int(range_value),
                    (keyword,),
                    "ranged",
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                specs.append(
                    {
                        "source": source,
                        "ability_key": "selected_to_shoot_target_attack_keywords",
                        "model": bearer_model,
                        "model_id": model_id,
                        "range": int(range_value),
                        "requires_visibility": True,
                        "keywords": [keyword],
                        "attack_type": "ranged",
                    }
                )

        specs.sort(
            key=lambda spec: (
                str(spec.get("model_id", "") or ""),
                str(spec.get("ability_key", "") or ""),
                str(spec.get("source", "") or "").strip().lower(),
            )
        )
        return specs

    def unit_selected_to_shoot_named_ranged_bonus_specs(self) -> list[dict]:
        root = self._selected_to_shoot_root()
        cache_key = "unit_selected_to_shoot_named_ranged_bonus_specs"
        cached = getattr(root, "_ability_cache", {}).get(cache_key)
        if isinstance(cached, list):
            return list(cached)

        specs: list[dict] = []
        seen: set[tuple[str, str, str, int]] = set()
        pattern = re.compile(
            r"each time this unit is selected to shoot it can use this ability "
            r"if it does until the end of the phase add (?P<attacks>\d+) to the attacks characteristic of "
            r"(?P<weapon>[a-z0-9 '’+\-]+?) equipped by models in this unit and you can only select one enemy unit "
            r"as the target of all of this unit s attacks"
        )

        for member in self._selected_to_shoot_member_units():
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                text_src = member._strip_eligibility_prefix(desc or name or "")
                normalized = member._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = pattern.fullmatch(normalized)
                if not m:
                    continue
                source = str(name or "Selected to shoot").strip() or "Selected to shoot"
                ability_key = str(member._normalize_keyword_phrase(source) or "selected_to_shoot").strip().lower()
                weapon_name = str(m.group("weapon") or "").strip()
                if not weapon_name:
                    continue
                try:
                    attacks_bonus = int(m.group("attacks") or 0)
                except (TypeError, ValueError):
                    attacks_bonus = 0
                if attacks_bonus <= 0:
                    continue
                dedupe_key = (source.lower(), ability_key, weapon_name.lower(), int(attacks_bonus))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                specs.append(
                    {
                        "source": source,
                        "ability_key": ability_key,
                        "weapon_name_phrases": [weapon_name],
                        "attacks_bonus": int(attacks_bonus),
                        "requires_single_target": True,
                    }
                )

        specs.sort(
            key=lambda spec: (
                str(spec.get("ability_key", "") or ""),
                str(spec.get("source", "") or "").strip().lower(),
            )
        )
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def apply_selected_to_shoot_unit_ranged_weapon_bonuses(
        self,
        *,
        key_prefix: str,
        source: str,
        attacks_bonus: int = 0,
        strength_bonus: int = 0,
        ap_bonus: int = 0,
        expires_phase: str = "SHOOTING_PHASE",
        target_root=None,
    ) -> int:
        root = target_root if target_root is not None else self._selected_to_shoot_root()
        try:
            attacks_bonus = int(attacks_bonus or 0)
        except (TypeError, ValueError):
            attacks_bonus = 0
        try:
            strength_bonus = int(strength_bonus or 0)
        except (TypeError, ValueError):
            strength_bonus = 0
        try:
            ap_bonus = int(ap_bonus or 0)
        except (TypeError, ValueError):
            ap_bonus = 0
        if attacks_bonus <= 0 and strength_bonus <= 0 and ap_bonus <= 0:
            return 0

        applied = 0
        for model in self._selected_to_shoot_models(root=root):
            model_id = str(get_entity_id(model) or "")
            for index, weapon_name in enumerate(self._selected_to_shoot_ranged_weapon_names_for_model(model)):
                model.set_temporary_weapon_bonus(
                    key=f"{str(key_prefix or '').strip().lower()}:{model_id}:{index}",
                    weapon_name=weapon_name,
                    attacks_bonus=int(attacks_bonus),
                    strength_bonus=int(strength_bonus),
                    ap_bonus=int(ap_bonus),
                    source=source,
                    expires_phase=expires_phase,
                )
                applied += 1
        return int(applied)

    def apply_selected_to_shoot_named_ranged_weapon_bonuses(
        self,
        *,
        key_prefix: str,
        source: str,
        weapon_names: list[str],
        attacks_bonus: int = 0,
        strength_bonus: int = 0,
        ap_bonus: int = 0,
        expires_phase: str = "SHOOTING_PHASE",
        target_root=None,
    ) -> int:
        root = target_root if target_root is not None else self._selected_to_shoot_root()
        names = [str(name or "").strip() for name in list(weapon_names or []) if str(name or "").strip()]
        if not names:
            return 0
        try:
            attacks_bonus = int(attacks_bonus or 0)
        except (TypeError, ValueError):
            attacks_bonus = 0
        try:
            strength_bonus = int(strength_bonus or 0)
        except (TypeError, ValueError):
            strength_bonus = 0
        try:
            ap_bonus = int(ap_bonus or 0)
        except (TypeError, ValueError):
            ap_bonus = 0
        if attacks_bonus <= 0 and strength_bonus <= 0 and ap_bonus <= 0:
            return 0

        applied = 0
        for model in self._selected_to_shoot_models(root=root):
            model_id = str(get_entity_id(model) or "")
            for index, weapon_name in enumerate(self._selected_to_shoot_ranged_weapon_names_for_model(model)):
                if not self._selected_to_shoot_weapon_name_matches(weapon_name, names):
                    continue
                model.set_temporary_weapon_bonus(
                    key=f"{str(key_prefix or '').strip().lower()}:{model_id}:{index}",
                    weapon_name=weapon_name,
                    attacks_bonus=int(attacks_bonus),
                    strength_bonus=int(strength_bonus),
                    ap_bonus=int(ap_bonus),
                    source=source,
                    expires_phase=expires_phase,
                )
                applied += 1
        return int(applied)

    def apply_selected_to_shoot_self_mortal_wounds(
        self,
        *,
        source: str,
        amount_expr: str | int = "D3",
        game=None,
        target_root=None,
    ) -> int:
        root = target_root if target_root is not None else self._selected_to_shoot_root()
        apply_mortals = getattr(root, "_apply_mortal_wounds_to_unit", None)
        if not callable(apply_mortals):
            return 0
        if isinstance(amount_expr, int):
            mortal_wounds = max(0, int(amount_expr))
        else:
            expr = str(amount_expr or "").strip().upper()
            if not expr:
                mortal_wounds = 0
            elif expr == "D3":
                mortal_wounds = max(0, int(get_roll("D3") or 0))
            else:
                mortal_wounds = max(0, int(expr))
        if mortal_wounds <= 0:
            return 0
        apply_mortals(root, int(mortal_wounds), game_map=getattr(game, "map", None))
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["selected_to_shoot_self_mortal_wounds_source"] = str(source or "").strip() or "Selected to shoot"
        special_rules["selected_to_shoot_self_mortal_wounds_amount"] = int(mortal_wounds)
        root.special_rules = special_rules
        return int(mortal_wounds)

    def resolve_selected_to_shoot_roll_table(self, *, spec: dict, game=None) -> dict | None:
        if not isinstance(spec, dict):
            return None
        source = str(spec.get("source", "") or "Selected to shoot").strip() or "Selected to shoot"
        ability_key = str(spec.get("ability_key", "") or self._normalize_keyword_phrase(source) or "selected_to_shoot").strip().lower()
        roll = int(get_roll("D6") or 1)
        roll = max(1, min(6, int(roll)))
        roll_branches = dict(spec.get("roll_branches", {}) or {})
        branch = roll_branches.get(str(roll)) or roll_branches.get(int(roll))
        if not isinstance(branch, dict):
            branch = {}

        result = {
            "source": source,
            "ability_key": ability_key,
            "roll": int(roll),
            "attacks_bonus": 0,
            "strength_bonus": 0,
            "ap_bonus": 0,
            "mortal_wounds": 0,
        }
        mortal_expr = branch.get("self_mortal_wounds_roll", branch.get("self_mortal_wounds", 0))
        if mortal_expr:
            result["mortal_wounds"] = int(
                self.apply_selected_to_shoot_self_mortal_wounds(
                    source=source,
                    amount_expr=mortal_expr,
                    game=game,
                )
            )
        try:
            attacks_bonus = int(branch.get("attacks_bonus", 0) or 0)
        except (TypeError, ValueError):
            attacks_bonus = 0
        try:
            strength_bonus = int(branch.get("strength_bonus", 0) or 0)
        except (TypeError, ValueError):
            strength_bonus = 0
        try:
            ap_bonus = int(branch.get("ap_bonus", 0) or 0)
        except (TypeError, ValueError):
            ap_bonus = 0
        if attacks_bonus > 0 or strength_bonus > 0 or ap_bonus > 0:
            effect_index = self._selected_to_shoot_next_sequence(ability_key)
            applied = self.apply_selected_to_shoot_unit_ranged_weapon_bonuses(
                key_prefix=f"{ability_key}:{effect_index}",
                source=source,
                attacks_bonus=int(attacks_bonus),
                strength_bonus=int(strength_bonus),
                ap_bonus=int(ap_bonus),
            )
            if applied > 0:
                result["attacks_bonus"] = int(attacks_bonus)
                result["strength_bonus"] = int(strength_bonus)
                result["ap_bonus"] = int(ap_bonus)
        return result

    def activate_selected_to_shoot_once_per_battle_ranged_bonus(
        self,
        *,
        model: Optional["Model"],
        ability_key: str,
        source: str,
        game=None,
        attacks_bonus: int = 0,
        strength_bonus: int = 0,
        ap_bonus: int = 0,
    ) -> bool:
        if model is None or not self._selected_to_shoot_model_is_alive(model):
            return False
        key = str(ability_key or "").strip().lower()
        if not key:
            return False
        if model.has_used_once_per_battle(key):
            return False
        applied = self.apply_selected_to_shoot_unit_ranged_weapon_bonuses(
            key_prefix=f"{key}:{str(get_entity_id(model) or '')}",
            source=source,
            attacks_bonus=int(attacks_bonus or 0),
            strength_bonus=int(strength_bonus or 0),
            ap_bonus=int(ap_bonus or 0),
            target_root=self._selected_to_shoot_root(),
        )
        if applied <= 0:
            return False
        return bool(model.mark_used_once_per_battle(key, ability_name=source, source="datasheet"))
