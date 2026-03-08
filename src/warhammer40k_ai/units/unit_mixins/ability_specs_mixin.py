"""Auto-extracted Unit mixin methods from unit.py."""

from ._common import *


class AbilitySpecsMixin:
    def model_post_shoot_battleshock_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has shot, select a hit enemy unit to take a Battle-shock test.

        Returns a list of specs with keys:
            - infantry_only: bool
            - source: ability name
        """
        if model is None:
            return []
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        root_sr = getattr(root, "special_rules", None)
        has_intoxicating_elixir = bool(
            isinstance(root_sr, dict) and bool(root_sr.get("enhancement_intoxicating_elixir", False))
        )
        cache_key = f"model_post_shoot_battleshock:{get_entity_id(model)}"
        if (not has_intoxicating_elixir) and cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            exclude_mv = "excluding monsters and vehicles" in normalized
            m_kill = self._POST_SHOOT_BATTLESHOCK_ON_KILL_RE.fullmatch(normalized)
            if m_kill:
                if str(m_kill.group("subject") or "").strip().lower() != "model":
                    continue
                try:
                    pen = int(m_kill.group("pen") or 0)
                except Exception:
                    pen = 0
                if pen:
                    source = str(name or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
                    key = (source.lower(), False, 0, -int(pen), exclude_mv)
                    if key not in seen:
                        seen.add(key)
                        specs.append(
                            {
                                "infantry_only": False,
                                "exclude_monster_vehicle": bool(exclude_mv),
                                "test_modifier_on_kill": -int(pen),
                                "source": source,
                            }
                        )
                    continue
            m_pen = self._POST_SHOOT_BATTLESHOCK_PENALTY_RE.fullmatch(normalized)
            if m_pen:
                if str(m_pen.group("subject") or "").strip().lower() != "model":
                    continue
                try:
                    pen = int(m_pen.group("pen") or 0)
                except Exception:
                    pen = 0
                if pen:
                    source = str(name or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
                    key = (source.lower(), False, -int(pen), 0, exclude_mv)
                    if key not in seen:
                        seen.add(key)
                        specs.append(
                            {
                                "infantry_only": False,
                                "exclude_monster_vehicle": bool(exclude_mv),
                                "test_modifier": -int(pen),
                                "source": source,
                            }
                        )
                    continue
            m_cond = self._POST_SHOOT_OR_FIGHT_BATTLESHOCK_CONDITIONAL_RE.fullmatch(normalized)
            if m_cond:
                if str(m_cond.group("subject") or "").strip().lower() != "model":
                    continue
                try:
                    pen = int(m_cond.group("pen") or 0)
                except Exception:
                    pen = 0
                try:
                    rng = int(m_cond.group("range") or 0)
                except Exception:
                    rng = 0
                phrase = str(m_cond.group("friendly") or "").strip()
                if pen <= 0 or rng <= 0:
                    continue
                source = str(name or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
                key = (
                    source.lower(),
                    "model_post_shoot_or_fight_battleshock",
                    -int(pen),
                    int(rng),
                    phrase.lower(),
                )
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "infantry_only": False,
                        "exclude_monster_vehicle": False,
                        "test_modifier_if_target_within_range": -int(pen),
                        "test_modifier_range": int(rng),
                        "test_modifier_friendly_keyword_phrase": phrase,
                        "applies_after_fight": True,
                        "source": source,
                    }
                )
                continue
            m = self._POST_SHOOT_BATTLESHOCK_RE.fullmatch(normalized)
            if not m:
                continue
            if str(m.group("subject") or "").strip().lower() != "model":
                continue
            infantry_only = bool(m.group("infantry"))
            exclude_raw = str(m.group("exclude_paren") or m.group("exclude") or "").strip().lower()
            has_vehicle_exclusion = "vehicle" in exclude_raw
            has_monster_exclusion = "monster" in exclude_raw
            exclude_mv = bool(exclude_mv or (has_vehicle_exclusion and has_monster_exclusion))
            exclude_vehicle_only = bool(has_vehicle_exclusion and not has_monster_exclusion)
            applies_after_fight = bool(
                " in your shooting phase and the fight phase " in normalized
                or " has shot or fought " in normalized
            )
            source = str(name or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
            key = (
                source.lower(),
                infantry_only,
                bool(exclude_mv),
                bool(exclude_vehicle_only),
                bool(applies_after_fight),
            )
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "infantry_only": infantry_only,
                    "exclude_monster_vehicle": bool(exclude_mv),
                    "exclude_vehicle_only": bool(exclude_vehicle_only),
                    "applies_after_fight": bool(applies_after_fight),
                    "source": source,
                }
            )

        if isinstance(root_sr, dict) and root_sr.get("enhancement_storm_of_whispers"):
            bearer_id = str(root_sr.get("enhancement_bearer_model_id", "") or "")
            model_id = str(get_entity_id(model) or "")
            if bearer_id and model_id and bearer_id == model_id:
                source = str(root_sr.get("enhancement_storm_of_whispers_source", "") or "Storm of Whispers").strip()
                source = source or "Storm of Whispers"
                key = (source.lower(), False, 0, 0, False)
                if key not in seen:
                    seen.add(key)
                    specs.append({"infantry_only": False, "exclude_monster_vehicle": False, "source": source})

        if isinstance(root_sr, dict) and bool(root_sr.get("enhancement_intoxicating_elixir", False)):
            bearer_id = str(
                root_sr.get("enhancement_intoxicating_elixir_bearer_model_id", "")
                or root_sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            model_id = str(get_entity_id(model) or "").strip()
            model_local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
            model_is_bearer = bool(
                bearer_id and (model_id == bearer_id or (model_local_id and model_local_id == bearer_id))
            )
            if model_is_bearer:
                phase_name = ""
                try:
                    army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                except Exception:
                    phase_name = ""
                dark_pacts_active = bool(root_sr.get("dark_pacts_active", False))
                dark_pacts_passed = bool(root_sr.get("dark_pacts_test_passed", False))
                dark_pacts_phase = str(root_sr.get("dark_pacts_expires_phase", "") or "").strip().upper()
                dark_pact_ok = bool(
                    dark_pacts_active and dark_pacts_passed and dark_pacts_phase and (not phase_name or dark_pacts_phase == phase_name)
                )
                if dark_pact_ok:
                    source = str(
                        root_sr.get("enhancement_intoxicating_elixir_source", "") or "Intoxicating Elixir"
                    ).strip() or "Intoxicating Elixir"
                    key = (source.lower(), False, 0, 0, True)
                    if key not in seen:
                        seen.add(key)
                        specs.append(
                            {
                                "infantry_only": False,
                                "exclude_monster_vehicle": False,
                                "exclude_vehicle_only": False,
                                "applies_after_fight": True,
                                "source": source,
                            }
                        )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        if not has_intoxicating_elixir:
            self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_post_shoot_battleshock_specs(self) -> List[dict]:
        """
        Unit-specific rule: after this unit has shot, select a hit enemy unit to take a Battle-shock test.

        Returns a list of specs with keys:
            - infantry_only: bool
            - exclude_monster_vehicle: bool
            - test_modifier: int (optional)
            - test_modifier_on_kill: int (optional)
            - source: ability name
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_shoot_battleshock_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = u._strip_eligibility_prefix(text_src)
                normalized = u._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                exclude_mv = "excluding monsters and vehicles" in normalized
                m_kill = self._POST_SHOOT_BATTLESHOCK_ON_KILL_RE.fullmatch(normalized)
                if m_kill:
                    if str(m_kill.group("subject") or "").strip().lower() != "unit":
                        continue
                    try:
                        pen = int(m_kill.group("pen") or 0)
                    except Exception:
                        pen = 0
                    if pen:
                        source = str(name or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
                        key = (source.lower(), False, 0, -int(pen), exclude_mv)
                        if key not in seen:
                            seen.add(key)
                            specs.append(
                                {
                                    "infantry_only": False,
                                    "exclude_monster_vehicle": bool(exclude_mv),
                                    "test_modifier_on_kill": -int(pen),
                                    "source": source,
                                }
                            )
                        continue
                m_pen = self._POST_SHOOT_BATTLESHOCK_PENALTY_RE.fullmatch(normalized)
                if m_pen:
                    if str(m_pen.group("subject") or "").strip().lower() != "unit":
                        continue
                    try:
                        pen = int(m_pen.group("pen") or 0)
                    except Exception:
                        pen = 0
                    if pen:
                        source = str(name or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
                        key = (source.lower(), False, -int(pen), 0, exclude_mv)
                        if key not in seen:
                            seen.add(key)
                            specs.append(
                                {
                                    "infantry_only": False,
                                    "exclude_monster_vehicle": bool(exclude_mv),
                                    "test_modifier": -int(pen),
                                    "source": source,
                                }
                            )
                        continue
                m_cond = self._POST_SHOOT_OR_FIGHT_BATTLESHOCK_CONDITIONAL_RE.fullmatch(normalized)
                if m_cond:
                    if str(m_cond.group("subject") or "").strip().lower() != "unit":
                        continue
                    try:
                        pen = int(m_cond.group("pen") or 0)
                    except Exception:
                        pen = 0
                    try:
                        rng = int(m_cond.group("range") or 0)
                    except Exception:
                        rng = 0
                    phrase = str(m_cond.group("friendly") or "").strip()
                    if pen <= 0 or rng <= 0:
                        continue
                    source = str(name or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
                    key = (
                        source.lower(),
                        "unit_post_shoot_or_fight_battleshock",
                        -int(pen),
                        int(rng),
                        phrase.lower(),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    specs.append(
                        {
                            "infantry_only": False,
                            "exclude_monster_vehicle": False,
                            "test_modifier_if_target_within_range": -int(pen),
                            "test_modifier_range": int(rng),
                            "test_modifier_friendly_keyword_phrase": phrase,
                            "applies_after_fight": True,
                            "source": source,
                        }
                    )
                    continue
                m = self._POST_SHOOT_BATTLESHOCK_RE.fullmatch(normalized)
                if not m:
                    continue
                if str(m.group("subject") or "").strip().lower() != "unit":
                    continue
                infantry_only = bool(m.group("infantry"))
                exclude_raw = str(m.group("exclude_paren") or m.group("exclude") or "").strip().lower()
                has_vehicle_exclusion = "vehicle" in exclude_raw
                has_monster_exclusion = "monster" in exclude_raw
                exclude_mv = bool(exclude_mv or (has_vehicle_exclusion and has_monster_exclusion))
                exclude_vehicle_only = bool(has_vehicle_exclusion and not has_monster_exclusion)
                applies_after_fight = bool(
                    " in your shooting phase and the fight phase " in normalized
                    or " has shot or fought " in normalized
                )
                source = str(name or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
                key = (
                    source.lower(),
                    infantry_only,
                    bool(exclude_mv),
                    bool(exclude_vehicle_only),
                    bool(applies_after_fight),
                )
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "infantry_only": infantry_only,
                        "exclude_monster_vehicle": bool(exclude_mv),
                        "exclude_vehicle_only": bool(exclude_vehicle_only),
                        "applies_after_fight": bool(applies_after_fight),
                        "source": source,
                    }
                )

        context_fn = getattr(root, "_plague_legion_fever_visions_context", None)
        if callable(context_fn):
            game = None
            try:
                game = root.get_parent_army().player.game
            except Exception:
                game = None
            context = context_fn(game=game)
            if isinstance(context, dict) and str(context.get("phase_name", "") or "").strip().upper() == "SHOOTING_PHASE":
                source = str(context.get("source", "") or "FEVER VISIONS").strip() or "FEVER VISIONS"
                key = (source.lower(), False, False, False, False)
                if key not in seen:
                    seen.add(key)
                    specs.append(
                        {
                            "infantry_only": False,
                            "exclude_monster_vehicle": False,
                            "exclude_vehicle_only": False,
                            "applies_after_fight": False,
                            "source": source,
                        }
                    )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def _parse_on_kill_battleshock_specs_from_text(self, ability_name: str, ability_desc: str) -> List[dict]:
        """Parse on-kill Battle-shock aura specs from text (model/unit subject)."""
        raw = self._normalize_rules_text(ability_desc)
        if not raw:
            return []
        raw = raw.replace("\u2019", "'").replace("\u0192?T", "'")
        sentences = [part.strip() for part in re.split(r"[.;]+", raw) if part.strip()]
        if not sentences:
            sentences = [raw]
        specs: list[dict] = []
        source = str(ability_name or "On-kill Battle-shock").strip() or "On-kill Battle-shock"
        for sentence in sentences:
            normalized = sentence.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._ON_KILL_BATTLESHOCK_WITHIN_RANGE_RE.fullmatch(normalized)
            if not m:
                continue
            subject = str(m.group("subject") or "").strip().lower()
            try:
                rng = int(m.group("range") or 0)
            except Exception:
                rng = 0
            if rng <= 0:
                continue
            specs.append(
                {
                    "subject": subject,
                    "range": int(rng),
                    "source": source,
                }
            )
        return specs

    def model_on_kill_battleshock_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """Model-specific rule: enemy unit destroyed by this model's attacks triggers Battle-shock in a radius."""
        if model is None:
            return []
        cache_key = f"model_on_kill_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            for spec in self._parse_on_kill_battleshock_specs_from_text(name, text_src):
                if str(spec.get("subject") or "").strip().lower() != "model":
                    continue
                rng = int(spec.get("range", 0) or 0)
                if rng <= 0:
                    continue
                source = str(spec.get("source", "") or "On-kill Battle-shock").strip() or "On-kill Battle-shock"
                key = (source.lower(), int(rng))
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"range": int(rng), "source": source})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_on_kill_battleshock_specs(self) -> List[dict]:
        """Unit-specific rule: enemy unit destroyed by this unit's attacks triggers Battle-shock in a radius."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_on_kill_battleshock_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = u._strip_eligibility_prefix(text_src)
                for spec in u._parse_on_kill_battleshock_specs_from_text(name, text_src):
                    if str(spec.get("subject") or "").strip().lower() != "unit":
                        continue
                    rng = int(spec.get("range", 0) or 0)
                    if rng <= 0:
                        continue
                    source = str(spec.get("source", "") or "On-kill Battle-shock").strip() or "On-kill Battle-shock"
                    key = (source.lower(), int(rng))
                    if key in seen:
                        continue
                    seen.add(key)
                    specs.append({"range": int(rng), "source": source})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_charge_end_engagement_battleshock_specs(self) -> List[dict]:
        """
        Unit-specific rule: after this unit ends a Charge move, engaged enemies take Battle-shock tests.

        Returns a list of specs with keys:
            - source: ability name
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_charge_end_engagement_battleshock_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, bool, int]] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = u._strip_eligibility_prefix(text_src)
                normalized = u._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                full_enemy_match = self._CHARGE_END_ENGAGEMENT_BATTLESHOCK_RE.fullmatch(normalized)
                single_enemy_match = self._CHARGE_END_ENGAGEMENT_SELECT_ONE_BATTLESHOCK_RE.fullmatch(normalized)
                if not full_enemy_match and not single_enemy_match:
                    continue
                source = str(name or "Charge end Battle-shock").strip() or "Charge end Battle-shock"
                select_one = bool(single_enemy_match)
                penalty = 0
                if single_enemy_match is not None:
                    try:
                        penalty = int(single_enemy_match.group("penalty") or 0)
                    except Exception:
                        penalty = 0
                key = (source.lower(), bool(select_one), int(penalty))
                if key in seen:
                    continue
                seen.add(key)
                spec = {"source": source}
                if select_one:
                    spec["select_one"] = True
                    if penalty:
                        spec["test_modifier"] = -int(penalty)
                specs.append(spec)

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_post_shoot_shoot_again_specs(self) -> List[dict]:
        """
        Unit-specific rule: once per battle, after this unit has shot, it can shoot again.

        Returns a list of specs with keys:
            - source: ability name
            - ability_key: str (once-per-battle tracking key)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_shoot_shoot_again_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = u._strip_eligibility_prefix(text_src)
                normalized = u._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not self._POST_SHOOT_SHOOT_AGAIN_RE.fullmatch(normalized):
                    continue
                source = str(name or "Shoot again").strip() or "Shoot again"
                key_seed = self._normalize_keyword_phrase(source) or "shoot_again"
                ability_key = f"post_shoot_shoot_again:{key_seed}"
                if ability_key in seen:
                    continue
                seen.add(ability_key)
                specs.append({"source": source, "ability_key": ability_key})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_shoot_disembark_wound_reroll_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has shot, select a hit enemy unit; disembarked models can re-roll Wound rolls.

        Returns a list of specs with keys:
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_disembark_wound_reroll:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_DISEMBARK_WOUND_REROLL_RE.fullmatch(normalized)
            if not m:
                if str(name or "").strip().lower() != "fire support":
                    continue
            source = str(name or "Fire Support").strip() or "Fire Support"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_hand_of_asuryan_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: once per battle, when selected to shoot, weapon gains Damage/keywords (Hand of Asuryan).

        Returns a list of specs with keys:
            - source: ability name
            - weapon_name: str
        """
        if model is None:
            return []
        cache_key = f"model_hand_of_asuryan:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            weapon_name = ""
            m = self._HAND_OF_ASURYAN_RE.fullmatch(normalized)
            if m:
                weapon_name = str(m.group("weapon") or "").strip()
            elif str(name or "").strip().lower() == "hand of asuryan":
                weapon_name = "Bloody Twins"
            if not weapon_name:
                continue
            source = str(name or "Hand of Asuryan").strip() or "Hand of Asuryan"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "weapon_name": weapon_name})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_nova_charge_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: once per battle, when selected to shoot, select one ranged weapon
        equipped by this model; that weapon gains [DEVASTATING WOUNDS] until end of phase.

        Returns a list of specs with keys:
            - source: ability name
            - ability_key: deterministic once-per-battle usage key
            - keywords: list[str]
        """
        if model is None:
            return []
        cache_key = f"model_nova_charge:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if "once per battle" not in normalized:
                continue
            if "selected to shoot" not in normalized:
                continue
            if "select one ranged weapon equipped by this model" not in normalized:
                continue
            if "that weapon has the devastating wounds ability" not in normalized:
                continue

            source = str(name or "Nova Charge").strip() or "Nova Charge"
            ability_key_seed = self._normalize_keyword_phrase(source) or "nova_charge"
            ability_key = f"nova_charge:{ability_key_seed}"
            dedupe_key = f"{source.lower()}:{ability_key}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            specs.append(
                {
                    "source": source,
                    "ability_key": ability_key,
                    "keywords": ["DEVASTATING WOUNDS"],
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_ammo_runt_specs(self) -> List[dict]:
        """
        Unit-level rule: when selected to shoot, can gain [LETHAL HITS] for ranged weapons.

        Returns specs with keys:
            - source: ability name
            - per_ammo_runt: bool (True when uses scale with Ammo Runt count)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_ammo_runt_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, bool]] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit in members:
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = unit._strip_eligibility_prefix(text_src)
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                is_named_ammo_runt = str(name or "").strip().lower() == "ammo runt"
                mentions_ammo_runt = "ammo runt" in normalized
                if not (is_named_ammo_runt or mentions_ammo_runt):
                    continue
                m = self._AMMO_RUNT_RE.fullmatch(normalized)
                if not m:
                    if not is_named_ammo_runt:
                        continue
                    if "selected to shoot" not in normalized or "lethal hits" not in normalized:
                        continue
                per_runt = bool((m and m.group("per_runt")) or ("for each ammo runt this unit has" in normalized))
                source = str(name or "Ammo Runt").strip() or "Ammo Runt"
                key = (source.lower(), bool(per_runt))
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"source": source, "per_ammo_runt": bool(per_runt)})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_cat_unit_specs(self) -> List[dict]:
        """
        Unit-level rule: once per battle, when selected to shoot, can gain [IGNORES COVER]
        for ranged weapons until end of phase.

        Returns specs with keys:
            - source: ability name
            - ability_key: deterministic once-per-battle usage key
            - keywords: list[str]
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_cat_unit_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit in members:
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = unit._strip_eligibility_prefix(text_src)
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not normalized:
                    continue

                name_key = str(name or "").strip().lower()
                is_named_cat_unit = name_key == "cat unit"
                if not (
                    "once per battle" in normalized
                    and "selected to shoot" in normalized
                    and "ranged weapons equipped by models in this unit" in normalized
                    and "ignores cover" in normalized
                ):
                    continue
                if not is_named_cat_unit and "cat unit" not in normalized:
                    continue

                source = str(name or "CAT Unit").strip() or "CAT Unit"
                ability_key = "cat_unit"
                dedupe_key = f"{source.lower()}:{ability_key}"
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                specs.append(
                    {
                        "source": source,
                        "ability_key": ability_key,
                        "keywords": ["IGNORES COVER"],
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_plasmacyte_specs(self) -> List[dict]:
        """
        Unit-level rule: when selected to fight, can gain [DEVASTATING WOUNDS] for melee weapons.

        Returns specs with keys:
            - source: ability name
            - per_plasmacyte: bool (True when uses scale with Plasmacyte count)
        """
        root_getter = getattr(self, "get_attached_unit_root", None)
        root = root_getter() if callable(root_getter) else self
        if root is None:
            root = self
        cache_key = "unit_plasmacyte_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, bool]] = set()
        members_getter = getattr(root, "get_attached_unit_members", None)
        members = list(members_getter() or []) if callable(members_getter) else [root]
        if not members:
            members = [root]

        for unit in members:
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = unit._strip_eligibility_prefix(text_src)
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                is_named_plasmacyte = str(name or "").strip().lower() == "plasmacyte"
                mentions_plasmacyte = "plasmacyte" in normalized
                if not (is_named_plasmacyte or mentions_plasmacyte):
                    continue
                m = self._PLASMACYTE_RE.fullmatch(normalized)
                if not m:
                    if not is_named_plasmacyte:
                        continue
                    if "selected to fight" not in normalized or "devastating wounds" not in normalized:
                        continue
                per_plasmacyte = bool(
                    (m and m.group("per_plasmacyte")) or ("for each plasmacyte this unit has" in normalized)
                )
                source = str(name or "Plasmacyte").strip() or "Plasmacyte"
                key = (source.lower(), bool(per_plasmacyte))
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"source": source, "per_plasmacyte": bool(per_plasmacyte)})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_bomb_squigs_specs(self) -> List[dict]:
        """
        Unit-level rule: after ending a Normal move, optionally select one visible enemy within range
        and roll for mortal wounds. Supports the three Bomb Squigs token variants.

        Returns specs with keys:
            - source: ability name
            - move_types: list[str] (always ["move"])
            - range: int
            - threshold: int
            - mortal_per_success: int
            - mortal_per_success_die: str
            - token_mode: str ("fixed" | "per_bomb_squig")
            - fixed_uses: int
            - ability_key: str
            - once_per_battle: bool
            - disable_move_over_rerolls: bool
            - roll_type: str
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_bomb_squigs_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit in members:
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = unit._strip_eligibility_prefix(text_src)
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()

                is_named_bomb_squigs = str(name or "").strip().lower() == "bomb squigs"
                mentions_bomb_squig = "bomb squig" in normalized
                if not (is_named_bomb_squigs or mentions_bomb_squig):
                    continue

                m = unit._BOMB_SQUIGS_RE.fullmatch(normalized)
                if not m:
                    if not is_named_bomb_squigs:
                        continue
                    # Keep a strict fallback for equivalent text forms with punctuation/layout differences.
                    if "ends a normal move" not in normalized:
                        continue
                    if "within 12 and visible to this unit" not in normalized:
                        continue
                    if "on a 3" not in normalized:
                        continue
                    if "d3 mortal wound" not in normalized:
                        continue
                    range_value = 12
                    threshold = 3
                    mw_raw = "d3"
                else:
                    try:
                        range_value = int(m.group("range") or 0)
                    except Exception:
                        range_value = 0
                    try:
                        threshold = int(m.group("threshold") or 0)
                    except Exception:
                        threshold = 0
                    mw_raw = str(m.group("mw") or "").strip().lower()

                if range_value <= 0 or threshold <= 0 or not mw_raw:
                    continue

                mortal_per = 0
                mortal_die = ""
                if mw_raw.startswith("d"):
                    mortal_die = mw_raw.upper()
                else:
                    try:
                        mortal_per = int(mw_raw or 0)
                    except Exception:
                        mortal_per = 0
                if mortal_per <= 0 and not mortal_die:
                    continue

                token_mode = "per_bomb_squig"
                fixed_uses = 0
                if "place two bomb squig tokens next to the unit" in normalized:
                    token_mode = "fixed"
                    fixed_uses = 2
                elif "place a bomb squig token next to the unit" in normalized:
                    token_mode = "fixed"
                    fixed_uses = 1
                elif "place the relevant number of bomb squig tokens next to the unit" in normalized:
                    token_mode = "per_bomb_squig"
                elif "for each bomb squig this unit has" in normalized:
                    token_mode = "per_bomb_squig"

                source = str(name or "Bomb Squigs").strip() or "Bomb Squigs"
                key = (
                    source.lower(),
                    int(range_value),
                    int(threshold),
                    int(mortal_per),
                    str(mortal_die),
                    str(token_mode),
                    int(fixed_uses),
                )
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "move_types": ["move"],
                        "range": int(range_value),
                        "dice": 1,
                        "threshold": int(threshold),
                        "mortal_per_success": int(mortal_per),
                        "mortal_per_success_die": str(mortal_die),
                        "token_mode": str(token_mode),
                        "fixed_uses": int(fixed_uses),
                        "ability_key": "bomb_squigs",
                        "once_per_battle": True,
                        "disable_move_over_rerolls": True,
                        "roll_type": "bomb_squigs",
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_plunder_specs(self) -> List[dict]:
        """
        Unit-level rule: once per battle after ending a Normal move, select a visible enemy in range
        and roll one D6 to inflict mortal wounds on a threshold.

        Returns specs with keys:
            - source: ability name
            - move_types: list[str] (always ["move"])
            - range: int
            - threshold: int
            - mortal_per_success: int
            - mortal_per_success_die: str
            - once_per_battle: bool
            - ability_key: str
            - disable_move_over_rerolls: bool
            - roll_type: str
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_plunder_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit in members:
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                source = str(name or "Plunder").strip() or "Plunder"
                source_key = unit._normalize_keyword_phrase(source)
                if source_key != "plunder":
                    continue
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = unit._strip_eligibility_prefix(text_src)
                normalized = unit._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9+]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()

                if "after this unit ends a normal move" not in normalized:
                    continue
                if "select one visible enemy unit within" not in normalized:
                    continue
                if "roll one d6" not in normalized:
                    continue
                if "mortal wound" not in normalized:
                    continue

                m = re.search(
                    r"select one visible enemy unit within (?P<range>\d+)\s+of it and roll one d6 on a (?P<threshold>\d)\+\s+that enemy unit suffers (?P<mw>(?:d\d+(?:\+\d+)?|\d+)) mortal wound",
                    normalized,
                )
                if not m:
                    continue

                try:
                    range_value = int(m.group("range") or 0)
                except Exception:
                    range_value = 0
                try:
                    threshold = int(m.group("threshold") or 0)
                except Exception:
                    threshold = 0
                mw_raw = str(m.group("mw") or "").strip().lower()
                if range_value <= 0 or threshold <= 0 or not mw_raw:
                    continue

                mortal_per = 0
                mortal_die = ""
                if mw_raw.startswith("d"):
                    mortal_die = mw_raw.upper()
                else:
                    try:
                        mortal_per = int(mw_raw or 0)
                    except Exception:
                        mortal_per = 0
                if mortal_per <= 0 and not mortal_die:
                    continue

                once_per_battle = "once per battle" in normalized
                key = (
                    source.lower(),
                    int(range_value),
                    int(threshold),
                    int(mortal_per),
                    str(mortal_die),
                    bool(once_per_battle),
                )
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "move_types": ["move"],
                        "range": int(range_value),
                        "dice": 1,
                        "threshold": int(threshold),
                        "mortal_per_success": int(mortal_per),
                        "mortal_per_success_die": str(mortal_die),
                        "once_per_battle": bool(once_per_battle),
                        "ability_key": "plunder",
                        "disable_move_over_rerolls": True,
                        "roll_type": "plunder",
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_shoot_mortal_wounds_battleshock_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model's unit has shot, select a hit enemy INFANTRY unit;
        roll 3D6 for mortal wounds, and if any are inflicted, that unit takes a Battle-shock test.

        Returns a list of specs with keys:
            - infantry_only: bool
            - dice: int
            - threshold: int
            - mortal_per_success: int
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_mortal_wounds_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_INFANTRY_MW_BATTLESHOCK_RE.fullmatch(normalized)
            if not m:
                continue
            dice_raw = str(m.group("dice") or "3").strip().lower()
            dice = 3 if dice_raw in ("three", "3") else 3
            threshold = 4
            source = str(name or "Post-shoot Mortals").strip() or "Post-shoot Mortals"
            key = (source.lower(), int(dice), int(threshold))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "infantry_only": True,
                    "dice": int(dice),
                    "threshold": int(threshold),
                    "mortal_per_success": 1,
                    "source": source,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_shoot_wracking_agonies_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has shot, select a hit enemy INFANTRY unit hit by its Agonising Energies;
        until the start of your next turn, that unit suffers Move -2" and Charge roll -2.

        Returns a list of specs with keys:
            - infantry_only: bool
            - weapon_key: str (normalized)
            - move_penalty: int
            - charge_penalty: int
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_wracking_agonies:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_WRACKING_AGONIES_RE.fullmatch(normalized)
            enf = None
            if not m:
                enf = self._POST_SHOOT_ENFEEBLED_RE.fullmatch(normalized)
            if not m and not enf:
                continue
            if enf is not None:
                weapon_raw = str(enf.group("weapon") or "plague wind").strip()
                try:
                    move_penalty = -int(enf.group("move") or 0)
                except Exception:
                    move_penalty = -2
                charge_penalty = 0
            else:
                weapon_raw = str(m.group("weapon") or "agonising energies").strip()
                try:
                    move_penalty = -int(m.group("move") or 0)
                except Exception:
                    move_penalty = -2
                try:
                    charge_penalty = -int(m.group("charge") or 0)
                except Exception:
                    charge_penalty = -2
            weapon_key = self._normalize_keyword_phrase(weapon_raw) or "agonising energies"
            source = str(name or "Wracking Agonies").strip() or "Wracking Agonies"
            key = (source.lower(), weapon_key, int(move_penalty), int(charge_penalty))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "infantry_only": True,
                    "weapon_key": weapon_key,
                    "move_penalty": int(move_penalty),
                    "charge_penalty": int(charge_penalty),
                    "source": source,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_shieldbreaker_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: once per battle, when selecting targets, a named weapon gains +wound
        and successful wound rolls become critical wounds until end of phase.

        Returns specs with keys:
            - source: ability name
            - ability_key: str
            - weapon_name: str
            - wound_bonus: int
            - crit_wound_threshold: int
        """
        if model is None:
            return []
        cache_key = f"model_shieldbreaker:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._SHIELDBREAKER_RE.fullmatch(normalized)
            if not m:
                continue
            weapon_name = str(m.group("weapon") or "").strip()
            if not weapon_name:
                continue
            try:
                wound_bonus = int(m.group("wound") or 0)
            except Exception:
                wound_bonus = 0
            if wound_bonus <= 0:
                continue
            source = str(name or "Shieldbreaker").strip() or "Shieldbreaker"
            key = (
                source.lower(),
                self._normalize_keyword_phrase(weapon_name) or weapon_name.lower(),
                int(wound_bonus),
                2,
            )
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "ability_key": "shieldbreaker",
                    "weapon_name": weapon_name,
                    "wound_bonus": int(wound_bonus),
                    "crit_wound_threshold": 2,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_shoot_monster_vehicle_mortal_threshold_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has shot, select a hit MONSTER/VEHICLE target and
        roll a D6 (optionally modified) to inflict mortal wounds on a threshold.

        Returns a list of specs with keys:
            - source: ability name
            - threshold: int
            - mortal_wounds: str | int
            - afflicted_roll_bonus: int
            - monster_vehicle_only: bool
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_monster_vehicle_mortal_threshold:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_MONSTER_VEHICLE_MORTAL_THRESHOLD_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                threshold = int(m.group("threshold") or 0)
            except Exception:
                threshold = 0
            if threshold <= 0:
                continue
            mw_raw = str(m.group("mw") or "").strip().lower()
            if not mw_raw:
                continue
            try:
                bonus = int(m.group("bonus") or 0)
            except (TypeError, ValueError):
                bonus = 0
            if mw_raw in ("d3", "d6"):
                mw_value: str | int = mw_raw
            else:
                try:
                    mw_value = int(mw_raw)
                except Exception:
                    continue
                if int(mw_value) <= 0:
                    continue
            source = str(name or "Post-shoot mortals").strip() or "Post-shoot mortals"
            key = (source.lower(), int(threshold), str(mw_value), int(bonus))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "threshold": int(threshold),
                    "mortal_wounds": mw_value,
                    "afflicted_roll_bonus": int(bonus),
                    "monster_vehicle_only": True,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_opponent_command_phase_below_starting_battleshock_specs(
        self,
        model: Optional['Model'] = None,
    ) -> List[dict]:
        """
        Model-specific rule: in opponent Command phase Battle-shock step, below-Starting enemy units in range test.

        Returns specs with keys:
            - source: ability name
            - range: int
            - test_penalty: int
            - psyker_penalty: int
        """
        if model is None:
            return []
        cache_key = f"model_opponent_command_phase_below_starting_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._OPPONENT_COMMAND_PHASE_BELOW_STARTING_BATTLESHOCK_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or m.group("range_alt") or 0)
            except (TypeError, ValueError):
                range_value = 0
            try:
                psyker_penalty = int(m.group("pen") or 0)
            except (TypeError, ValueError):
                psyker_penalty = 0
            try:
                test_penalty = int(m.group("test_pen") or m.group("with_pen") or 0)
            except (TypeError, ValueError):
                test_penalty = 0
            if range_value <= 0:
                continue
            psyker_penalty = max(0, int(psyker_penalty))
            test_penalty = max(0, int(test_penalty))
            source = str(name or "Opponent Command phase Battle-shock").strip() or "Opponent Command phase Battle-shock"
            key = (source.lower(), int(range_value), int(test_penalty), int(psyker_penalty))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "test_penalty": int(test_penalty),
                    "psyker_penalty": int(psyker_penalty),
                }
            )

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
        model_id = str(get_entity_id(model) or "").strip()
        repugnomancer_bonus = 0
        for member in members:
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_master_repugnomancer", False)):
                continue
            bearer_id = str(
                sr.get("enhancement_master_repugnomancer_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            if bearer_id and model_id and bearer_id != model_id:
                continue
            try:
                bonus = int(sr.get("enhancement_master_repugnomancer_fear_incarnate_range_bonus", 3) or 3)
            except Exception:
                bonus = 3
            repugnomancer_bonus = max(int(repugnomancer_bonus), int(max(0, bonus)))
        if repugnomancer_bonus > 0:
            adjusted_specs: list[dict] = []
            adjusted_seen: set[tuple[str, int, int, int]] = set()
            for spec in specs:
                if not isinstance(spec, dict):
                    continue
                spec_row = dict(spec)
                source_name = str(spec_row.get("source", "") or "").strip()
                source_key = source_name.lower()
                try:
                    range_value = int(spec_row.get("range", 0) or 0)
                except Exception:
                    range_value = 0
                try:
                    test_penalty = int(spec_row.get("test_penalty", 0) or 0)
                except Exception:
                    test_penalty = 0
                try:
                    psyker_penalty = int(spec_row.get("psyker_penalty", 0) or 0)
                except Exception:
                    psyker_penalty = 0
                if "fear incarnate" in source_key:
                    range_value = max(0, int(range_value) + int(repugnomancer_bonus))
                    spec_row["range"] = int(range_value)
                dedupe_key = (source_key, int(range_value), int(test_penalty), int(psyker_penalty))
                if dedupe_key in adjusted_seen:
                    continue
                adjusted_seen.add(dedupe_key)
                adjusted_specs.append(spec_row)
            specs = adjusted_specs
            seen = adjusted_seen

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
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_avenging_avatar", False)):
                continue
            bearer_id = str(
                sr.get("enhancement_avenging_avatar_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            if bearer_id and model_id and bearer_id != model_id:
                continue
            source = str(
                sr.get("enhancement_avenging_avatar_source", "") or "Avenging Avatar (Aura)"
            ).strip() or "Avenging Avatar (Aura)"
            try:
                range_value = int(float(sr.get("enhancement_avenging_avatar_range", 9.0) or 9.0))
            except Exception:
                range_value = 9
            if range_value <= 0:
                continue
            key = (source.lower(), int(range_value), 0, 0)
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "test_penalty": 0,
                    "psyker_penalty": 0,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_shoot_suppression_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has shot, select a hit enemy unit to become suppressed.

        Returns a list of specs with keys:
            - exclude_monster_vehicle: bool
            - weapon_key: Optional[str] (normalized weapon name if required by the rule)
            - weapon_name: Optional[str] (display text from the rule)
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_suppression:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, bool, str]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_SUPPRESSION_RE.fullmatch(normalized)
            if not m:
                continue
            exclude_mv = bool(m.group("exclude")) or ("excluding monsters and vehicles" in normalized)
            weapon_raw = str(m.group("weapon") or "").strip()
            weapon_key = self._normalize_keyword_phrase(weapon_raw) or weapon_raw.lower()
            source = str(name or "Post-shoot Suppression").strip() or "Post-shoot Suppression"
            key = (source.lower(), exclude_mv, weapon_key or "any")
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "exclude_monster_vehicle": exclude_mv,
                    "weapon_key": weapon_key or None,
                    "weapon_name": weapon_raw or None,
                    "source": source,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_post_shoot_suppression_specs(self) -> List[dict]:
        """
        Unit-specific rule: after this unit has shot, select a hit enemy unit to become suppressed.

        Returns a list of specs with keys:
            - exclude_monster_vehicle: bool
            - weapon_key: Optional[str] (normalized weapon name if required by the rule)
            - weapon_name: Optional[str] (display text from the rule)
            - source: ability name
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_shoot_suppression_specs"
        base_specs = None
        if cache_key in getattr(root, "_ability_cache", {}):
            base_specs = list(root._ability_cache[cache_key])

        if base_specs is None:
            specs: list[dict] = []
            seen: set[tuple[str, bool, str]] = set()
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]

            for u in members:
                for name, desc in u._iter_ability_entries_for_rules(model=None):
                    text_src = desc or name or ""
                    if not text_src:
                        continue
                    text_src = u._strip_eligibility_prefix(text_src)
                    normalized = u._normalize_rules_text(text_src)
                    normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                    normalized = normalized.lower()
                    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                    normalized = re.sub(r"\s+", " ", normalized).strip()
                    m = self._POST_SHOOT_SUPPRESSION_RE.fullmatch(normalized)
                    if not m:
                        continue
                    exclude_mv = bool(m.group("exclude")) or ("excluding monsters and vehicles" in normalized)
                    weapon_raw = str(m.group("weapon") or "").strip()
                    weapon_key = self._normalize_keyword_phrase(weapon_raw) or weapon_raw.lower()
                    source = str(name or "Post-shoot Suppression").strip() or "Post-shoot Suppression"
                    key = (source.lower(), exclude_mv, weapon_key or "any")
                    if key in seen:
                        continue
                    seen.add(key)
                    specs.append(
                        {
                            "exclude_monster_vehicle": exclude_mv,
                            "weapon_key": weapon_key or None,
                            "weapon_name": weapon_raw or None,
                            "source": source,
                        }
                    )

            if not hasattr(root, "_ability_cache"):
                root._ability_cache = {}
            root._ability_cache[cache_key] = list(specs)
            base_specs = list(specs)

        specs = list(base_specs or [])
        seen = {
            (
                str(spec.get("source", "") or "").strip().lower(),
                bool(spec.get("exclude_monster_vehicle", False)),
                str(spec.get("weapon_key", "") or "").strip().lower() or "any",
            )
            for spec in specs
        }

        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and sr.get("unleash_hell_active") and not sr.get("unleash_hell_consumed"):
            game = None
            try:
                army = root.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
            if game is not None and bool(getattr(game, "is_shooting_phase", lambda: False)()):
                owner_id = str(sr.get("unleash_hell_owner", "") or "")
                if owner_id:
                    try:
                        current = game.get_current_player()
                    except Exception:
                        current = None
                    if current is None or str(getattr(current, "id", "") or "") != owner_id:
                        return list(specs)
                try:
                    turn = int(sr.get("unleash_hell_turn", 0) or 0)
                except Exception:
                    turn = 0
                if turn:
                    try:
                        if int(getattr(game, "turn", 0) or 0) != turn:
                            return list(specs)
                    except Exception:
                        return list(specs)
                source = str(sr.get("unleash_hell_source", "") or "Unleash Hell").strip() or "Unleash Hell"
                exclude_mv = bool(sr.get("unleash_hell_exclude_monster_vehicle", False))
                key = (source.lower(), exclude_mv, "any")
                if key not in seen:
                    specs.append(
                        {
                            "exclude_monster_vehicle": exclude_mv,
                            "weapon_key": None,
                            "weapon_name": None,
                            "source": source,
                            "source_key": "unleash_hell",
                        }
                    )
        return list(specs)

    def unit_post_shoot_afflicted_specs(self) -> List[dict]:
        """
        Unit-specific rule: after this unit has shot, select a hit enemy unit; that unit is Afflicted
        until the start of your next turn.

        Returns a list of specs with keys:
            - source: ability name
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_shoot_afflicted_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[str] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not unit._POST_SHOOT_AFFLICTED_RE.fullmatch(normalized):
                    continue
                source = str(name or "Post-shoot Afflicted").strip() or "Post-shoot Afflicted"
                source_key = source.lower()
                if source_key in seen:
                    continue
                seen.add(source_key)
                specs.append({"source": source})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_fight_battleshock_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has fought, select a hit enemy unit to take a Battle-shock test.
        """
        if model is None:
            return []
        cache_key = f"model_post_fight_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()
        for spec in list(self.model_post_shoot_battleshock_specs(model) or []):
            if not bool(spec.get("applies_after_fight", False)):
                continue
            source = str(spec.get("source", "") or "Post-fight Battle-shock").strip() or "Post-fight Battle-shock"
            key = (
                source.lower(),
                bool(spec.get("infantry_only", False)),
                bool(spec.get("exclude_monster_vehicle", False)),
                bool(spec.get("exclude_vehicle_only", False)),
                int(spec.get("test_modifier", 0) or 0),
                int(spec.get("test_modifier_on_kill", 0) or 0),
                int(spec.get("test_modifier_if_target_within_range", 0) or 0),
                int(spec.get("test_modifier_range", 0) or 0),
                str(spec.get("test_modifier_friendly_keyword_phrase", "") or "").strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            entry = dict(spec)
            entry["source"] = source
            specs.append(entry)

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_post_fight_battleshock_specs(self) -> List[dict]:
        """
        Unit-specific rule: after this unit has fought, select a hit enemy unit to take a Battle-shock test.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_fight_battleshock_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()
        for spec in list(root.unit_post_shoot_battleshock_specs() or []):
            if not bool(spec.get("applies_after_fight", False)):
                continue
            source = str(spec.get("source", "") or "Post-fight Battle-shock").strip() or "Post-fight Battle-shock"
            key = (
                source.lower(),
                bool(spec.get("infantry_only", False)),
                bool(spec.get("exclude_monster_vehicle", False)),
                bool(spec.get("exclude_vehicle_only", False)),
                int(spec.get("test_modifier", 0) or 0),
                int(spec.get("test_modifier_on_kill", 0) or 0),
                int(spec.get("test_modifier_if_target_within_range", 0) or 0),
                int(spec.get("test_modifier_range", 0) or 0),
                str(spec.get("test_modifier_friendly_keyword_phrase", "") or "").strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            entry = dict(spec)
            entry["source"] = source
            specs.append(entry)

        context_fn = getattr(root, "_plague_legion_fever_visions_context", None)
        if callable(context_fn):
            game = None
            try:
                game = root.get_parent_army().player.game
            except Exception:
                game = None
            context = context_fn(game=game)
            if isinstance(context, dict) and str(context.get("phase_name", "") or "").strip().upper() == "FIGHT_PHASE":
                source = str(context.get("source", "") or "FEVER VISIONS").strip() or "FEVER VISIONS"
                key = (
                    source.lower(),
                    False,
                    False,
                    False,
                    0,
                    0,
                    0,
                    0,
                    "",
                )
                if key not in seen:
                    seen.add(key)
                    specs.append(
                        {
                            "infantry_only": False,
                            "exclude_monster_vehicle": False,
                            "exclude_vehicle_only": False,
                            "source": source,
                        }
                    )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_any_command_phase_battleshock_specs(
        self,
        model: Optional['Model'] = None,
    ) -> List[dict]:
        """
        Model-specific rule: once per battle, start of any Command phase, nearby enemies
        take Battle-shock tests with a fixed modifier (and optional stronger PSYKER modifier).

        Returns specs with keys:
            - source: ability name
            - range: int
            - test_penalty: int
            - psyker_test_penalty: int
            - ability_key: str
        """
        if model is None:
            return []
        cache_key = f"model_start_any_command_phase_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._START_ANY_COMMAND_PHASE_ENEMY_RANGE_BATTLESHOCK_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            try:
                penalty = int(m.group("pen") or 0)
            except Exception:
                penalty = 0
            try:
                psyker_penalty = int(m.group("psyker_pen") or 0)
            except Exception:
                psyker_penalty = 0
            if range_value <= 0 or penalty <= 0:
                continue
            psyker_penalty = int(psyker_penalty) if int(psyker_penalty or 0) > 0 else int(penalty)
            source = str(name or "Start any Command phase Battle-shock").strip() or "Start any Command phase Battle-shock"
            ability_key = "soulless_horror"
            dedupe_key = (source.lower(), int(range_value), int(penalty), int(psyker_penalty))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "test_penalty": int(penalty),
                    "psyker_test_penalty": int(psyker_penalty),
                    "ability_key": ability_key,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_any_command_phase_objective_battleshock_specs(
        self,
        model: Optional['Model'] = None,
    ) -> List[dict]:
        """
        Model-specific rule: once per battle, start of any Command phase, select one
        objective marker near the bearer; enemy units in range of that marker take
        Battle-shock tests.

        Returns specs with keys:
            - source: ability name
            - objective_selection_range: int
            - exclude_monster_vehicle: bool
            - per_objective_once_per_turn: bool
            - ability_key: str
        """
        if model is None:
            return []
        cache_key = f"model_start_any_command_phase_objective_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, bool, bool]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._START_ANY_COMMAND_PHASE_OBJECTIVE_BATTLESHOCK_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                objective_selection_range = int(m.group("range") or 0)
            except (TypeError, ValueError):
                objective_selection_range = 0
            if objective_selection_range <= 0:
                continue
            exclude_raw = str(m.group("exclude") or "").strip().lower()
            exclude_monster_vehicle = (
                "excluding monsters and vehicles" in exclude_raw
                or "excluding monster and vehicle" in exclude_raw
                or "excluding monsters and vehicles" in normalized
                or "excluding monster and vehicle" in normalized
            )
            per_objective_once_per_turn = "each objective marker can only be targeted by this ability once per turn" in normalized
            source = str(name or "Objective marker Battle-shock").strip() or "Objective marker Battle-shock"
            source_key = re.sub(r"[^a-z0-9]+", "_", source.lower()).strip("_")
            if not source_key:
                source_key = "objective_battleshock"
            ability_key = f"start_any_command_phase_objective_battleshock:{source_key}"
            dedupe_key = (
                source.lower(),
                int(objective_selection_range),
                bool(exclude_monster_vehicle),
                bool(per_objective_once_per_turn),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            specs.append(
                {
                    "source": source,
                    "objective_selection_range": int(objective_selection_range),
                    "exclude_monster_vehicle": bool(exclude_monster_vehicle),
                    "per_objective_once_per_turn": bool(per_objective_once_per_turn),
                    "ability_key": ability_key,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_command_phase_enemy_no_cover_specs(
        self,
        model: Optional['Model'] = None,
    ) -> List[dict]:
        """
        Model-specific rule: in your Command phase, optionally select one enemy unit in range;
        selected unit cannot have the Benefit of Cover until your next Command phase.

        Returns specs with keys:
            - source: ability name
            - range: int
            - ability_key: str
            - optional: bool
            - expires_timing: str ("owner_next_command_start")
        """
        if model is None:
            return []
        cache_key = f"model_command_phase_enemy_no_cover:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._COMMAND_PHASE_ENEMY_NO_COVER_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except (TypeError, ValueError):
                range_value = 0
            if range_value <= 0:
                continue
            source = str(name or "Command phase no cover").strip() or "Command phase no cover"
            source_key = re.sub(r"[^a-z0-9]+", "_", source.lower()).strip("_")
            if not source_key:
                source_key = "command_phase_no_cover"
            ability_key = f"command_phase_no_cover:{source_key}"
            dedupe_key = (ability_key, int(range_value))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "ability_key": ability_key,
                    "optional": True,
                    "expires_timing": "owner_next_command_start",
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_command_phase_psychic_veil_specs(
        self,
        model: Optional['Model'] = None,
    ) -> List[dict]:
        """
        Model-specific rule: in your Command phase, optional Psychic Veil use with D6 roll.

        On 1: this PSYKER's unit suffers D3 mortal wounds.
        On 2+: until your next Command phase, this PSYKER's unit can only be targeted by
        ranged attacks from within a fixed distance.

        Returns specs with keys:
            - source: ability name
            - range: int
            - ability_key: str
            - optional: bool
        """
        if model is None:
            return []
        cache_key = f"model_command_phase_psychic_veil:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._COMMAND_PHASE_PSYCHIC_VEIL_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except (TypeError, ValueError):
                range_value = 0
            if range_value <= 0:
                continue
            source = str(name or "Psychic Veil (Psychic)").strip() or "Psychic Veil (Psychic)"
            source_key = re.sub(r"[^a-z0-9]+", "_", source.lower()).strip("_")
            if not source_key:
                source_key = "psychic_veil"
            ability_key = f"command_phase_psychic_veil:{source_key}"
            dedupe_key = (ability_key, int(range_value))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "ability_key": ability_key,
                    "optional": True,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_leading_psychic_daemon_invulnerable_specs(self) -> List[dict]:
        """
        Unit-level rule parser for "while this model is leading" invulnerable clauses with
        a stronger save vs Psychic attacks and attacks made by DAEMON models.

        Returns specs with keys:
            - source: ability name
            - source_unit_id: str
            - base_invulnerable: int
            - conditioned_invulnerable: int
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_leading_psychic_daemon_invulnerable_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, str, int, int]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._LEADING_UNIT_PSYCHIC_DAEMON_INVULN_RE.fullmatch(normalized)
                if not m:
                    continue
                try:
                    base_inv = int(m.group("base") or 0)
                except (TypeError, ValueError):
                    base_inv = 0
                try:
                    conditioned_inv = int(m.group("vs") or 0)
                except (TypeError, ValueError):
                    conditioned_inv = 0
                if base_inv <= 0 or conditioned_inv <= 0:
                    continue
                source = str(name or "Leading invulnerable save").strip() or "Leading invulnerable save"
                source_unit_id = str(get_entity_id(unit) or "").strip()
                dedupe_key = (source.lower(), source_unit_id, int(base_inv), int(conditioned_inv))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                specs.append(
                    {
                        "source": source,
                        "source_unit_id": source_unit_id,
                        "base_invulnerable": int(base_inv),
                        "conditioned_invulnerable": int(conditioned_inv),
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_selected_phases_enemy_range_battleshock_specs(
        self,
        model: Optional['Model'] = None,
    ) -> List[dict]:
        """
        Model-specific rule: once per turn at the start of selected phases, optionally select
        one enemy unit in range to take a Battle-shock test with a fixed penalty.

        Returns specs with keys:
            - source: ability name
            - range: int
            - test_penalty: int
            - phase_names: list[str]
            - ability_key: str
            - optional: bool
            - once_per_turn: bool
        """
        if model is None:
            return []
        cache_key = f"model_start_selected_phases_enemy_range_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int, tuple[str, ...]]] = set()
        phase_token_order = [
            ("command", "COMMAND_PHASE"),
            ("movement", "MOVEMENT_PHASE"),
            ("shooting", "SHOOTING_PHASE"),
            ("charge", "CHARGE_PHASE"),
            ("fight", "FIGHT_PHASE"),
        ]

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._START_SELECTED_PHASES_ENEMY_RANGE_BATTLESHOCK_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except (TypeError, ValueError):
                range_value = 0
            try:
                test_penalty = int(m.group("pen") or 0)
            except (TypeError, ValueError):
                test_penalty = 0
            if range_value <= 0 or test_penalty <= 0:
                continue
            phases_raw = str(m.group("phases") or "").strip().lower()
            if not phases_raw:
                continue
            phase_names = [
                phase_name
                for token, phase_name in phase_token_order
                if re.search(rf"\b{re.escape(token)}\b", phases_raw)
            ]
            if not phase_names:
                continue
            source = str(name or "Start phase Battle-shock selection").strip() or "Start phase Battle-shock selection"
            source_key = self._normalize_keyword_phrase(source) or re.sub(r"[^a-z0-9]+", "_", source.lower()).strip("_")
            if not source_key:
                source_key = "start_phase_battleshock"
            ability_key = f"start_phase_select_battleshock:{source_key}"
            dedupe_key = (source.lower(), int(range_value), int(test_penalty), tuple(phase_names))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "test_penalty": int(test_penalty),
                    "phase_names": list(phase_names),
                    "ability_key": ability_key,
                    "optional": True,
                    "once_per_turn": True,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_shoot_snare_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has shot, select a hit enemy unit hit by a weapon; target is snared.

        Returns a list of specs with keys:
            - weapon_key: str (normalized weapon name)
            - weapon_name: str (display)
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_snare:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_SNARE_RE.fullmatch(normalized)
            if not m:
                continue
            weapon_raw = str(m.group("weapon") or "").strip()
            if not weapon_raw:
                continue
            weapon_key = self._normalize_keyword_phrase(weapon_raw) or weapon_raw.lower()
            source = str(name or "Snare").strip() or "Snare"
            key = (source.lower(), weapon_key)
            if key in seen:
                continue
            seen.add(key)
            specs.append({"weapon_key": weapon_key, "weapon_name": weapon_raw, "source": source})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_shoot_pinned_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has shot, select a hit enemy unit hit by a weapon; target is pinned.

        Returns a list of specs with keys:
            - weapon_key: str (normalized weapon name)
            - weapon_name: str (display)
            - move_penalty: int
            - charge_penalty: int
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_pinned:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_PINNED_RE.fullmatch(normalized)
            if not m:
                m = self._POST_SHOOT_PINNED_ALT_RE.fullmatch(normalized)
            if not m:
                continue
            weapon_raw = str(m.group("weapon") or "").strip()
            if not weapon_raw:
                continue
            weapon_key = self._normalize_keyword_phrase(weapon_raw) or weapon_raw.lower()
            try:
                move_penalty = -int(m.group("move") or 0)
            except Exception:
                move_penalty = -2
            try:
                charge_penalty = -int(m.group("charge") or 0)
            except Exception:
                charge_penalty = -2
            source = str(name or "Pinned").strip() or "Pinned"
            key = (source.lower(), weapon_key, int(move_penalty), int(charge_penalty))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "weapon_key": weapon_key,
                    "weapon_name": weapon_raw,
                    "move_penalty": int(move_penalty),
                    "charge_penalty": int(charge_penalty),
                    "source": source,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_shoot_aflame_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has shot, select a hit enemy unit, roll a D6; on success, that unit is aflame.

        Returns a list of specs with keys:
            - exclude_monster_vehicle: bool
            - roll_threshold: int
            - move_penalty: int
            - advance_penalty: int
            - charge_penalty: int
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_aflame:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, bool, int, int, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_AFLAME_RE.fullmatch(normalized)
            if not m:
                continue
            exclude_mv = bool(m.group("exclude")) or ("excluding monsters and vehicles" in normalized)
            try:
                threshold = int(m.group("threshold") or 4)
            except Exception:
                threshold = 4
            try:
                move_penalty = -int(m.group("move") or 0)
            except Exception:
                move_penalty = -2
            try:
                advance_penalty = -int(m.group("advance") or 0)
            except Exception:
                advance_penalty = -2
            charge_penalty = int(advance_penalty)
            source = str(name or "Aflame").strip() or "Aflame"
            key = (
                source.lower(),
                bool(exclude_mv),
                int(threshold),
                int(move_penalty),
                int(advance_penalty),
                int(charge_penalty),
            )
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "exclude_monster_vehicle": bool(exclude_mv),
                    "roll_threshold": int(threshold),
                    "move_penalty": int(move_penalty),
                    "advance_penalty": int(advance_penalty),
                    "charge_penalty": int(charge_penalty),
                    "source": source,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_shoot_crit_hit_threshold_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has shot, select a hit enemy unit; friendly keyword attacks gain crit threshold.

        Returns a list of specs with keys:
            - threshold: int
            - keyword: str
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_crit_hit_threshold:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_CRIT_HIT_THRESHOLD_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                threshold = int(m.group("threshold") or 6)
            except Exception:
                threshold = 6
            keyword_raw = str(m.group("keyword") or "").strip()
            if not keyword_raw:
                keyword_raw = "friendly"
            keyword = self._normalize_keyword_phrase(keyword_raw) or keyword_raw.lower()
            source = str(name or "Post-shoot crit threshold").strip() or "Post-shoot crit threshold"
            key = (source.lower(), keyword, int(threshold))
            if key in seen:
                continue
            seen.add(key)
            specs.append({"threshold": int(threshold), "keyword": keyword, "source": source})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_atavistic_instigation_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: when this model targets with a named weapon, opponent chooses Stand Firm or Duck for Cover.

        Returns a list of specs with keys:
            - weapon_key: str
            - weapon_name: str
            - stand_firm_crit_hit_threshold: int
            - duck_hit_roll_penalty: int
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_atavistic_instigation:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._ATAVISTIC_INSTIGATION_RE.fullmatch(normalized)
            if not m:
                continue
            weapon_raw = str(m.group("weapon") or "").strip()
            if not weapon_raw:
                continue
            weapon_key = self._normalize_keyword_phrase(weapon_raw) or weapon_raw.lower()
            try:
                threshold = int(m.group("threshold") or 5)
            except Exception:
                threshold = 5
            try:
                hit_penalty = int(m.group("hit_penalty") or 1)
            except Exception:
                hit_penalty = 1
            source = str(name or "Atavistic Instigation").strip() or "Atavistic Instigation"
            key = (source.lower(), weapon_key, int(threshold), int(hit_penalty))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "weapon_key": weapon_key,
                    "weapon_name": weapon_raw,
                    "stand_firm_crit_hit_threshold": int(threshold),
                    "duck_hit_roll_penalty": int(hit_penalty),
                    "source": source,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_shoot_keyword_strength_bonus_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model's unit has shot, select a hit enemy unit hit by a named weapon;
        friendly keyword models gain +Strength when attacking that marked unit until end of turn.

        Returns a list of specs with keys:
            - weapon_key: str (normalized weapon name)
            - weapon_name: str (display)
            - keyword_phrase: str (normalized keyword phrase)
            - strength_bonus: int
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_keyword_strength_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str, str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_MODEL_WEAPON_KEYWORD_STRENGTH_BONUS_RE.fullmatch(normalized)
            if not m:
                continue
            weapon_raw = str(m.group("weapon") or "").strip()
            if not weapon_raw:
                continue
            weapon_key = self._normalize_keyword_phrase(weapon_raw) or weapon_raw.lower()
            keyword_raw = str(m.group("keyword") or "").strip()
            keyword_raw = re.sub(r"^(?:a|an)\s+", "", keyword_raw)
            keyword_phrase = self._normalize_keyword_phrase(keyword_raw) if keyword_raw else ""
            if not keyword_phrase:
                keyword_phrase = "friendly"
            try:
                bonus = int(m.group("val") or 0)
            except Exception:
                bonus = 0
            if bonus <= 0:
                continue
            source = str(name or "Post-shoot Strength bonus").strip() or "Post-shoot Strength bonus"
            key = (source.lower(), weapon_key, keyword_phrase, int(bonus))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "weapon_key": weapon_key,
                    "weapon_name": weapon_raw,
                    "keyword_phrase": keyword_phrase,
                    "strength_bonus": int(bonus),
                    "source": source,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_tau_advanced_scouting_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific T'au rule: after this model scores a ranged hit on an enemy unit,
        other friendly keyword models can re-roll Hit rolls against that unit until end of turn.

        Returns a list of specs with keys:
            - source: ability name
            - keyword_phrase: str (normalized keyword phrase)
        """
        if model is None:
            return []
        cache_key = f"model_tau_advanced_scouting:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = self._strip_eligibility_prefix(desc or name or "")
            if not text_src:
                continue
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._TAU_ADVANCED_SCOUTING_RE.fullmatch(normalized)
            if not m:
                continue
            keyword_raw = str(m.group("keyword") or "").strip()
            keyword_phrase = self._normalize_keyword_phrase(keyword_raw) if keyword_raw else ""
            if not keyword_phrase:
                keyword_phrase = "kroot"
            source = str(name or "Advanced Scouting").strip() or "Advanced Scouting"
            key = (source.lower(), keyword_phrase)
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "keyword_phrase": keyword_phrase,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_sonic_destruction_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model/unit-specific rule: vibro cannon attacks gain +S/AP/D per other friendly platform that targeted the unit.

        Returns a list of specs with keys:
            - weapon_key: str
            - bonus_per_other: int
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_sonic_destruction:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str, int]] = set()

        entries: list[tuple[str, str]] = []
        try:
            entries.extend(list(self._iter_model_specific_ability_entries(model) or []))
        except Exception:
            pass
        try:
            entries.extend(list(self._iter_ability_entries_for_rules(model=None) or []))
        except Exception:
            pass

        for name, desc in entries:
            text_src = desc or name or ""
            if not text_src:
                continue
            name_norm = str(name or "").strip().lower()
            weapon_key = ""
            bonus_val = 0

            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()

            m = self._SONIC_DESTRUCTION_RE.fullmatch(normalized)
            if m:
                weapon_raw = str(m.group("weapon") or "").strip()
                weapon_key = self._normalize_keyword_phrase(weapon_raw) or weapon_raw.lower()
                try:
                    bonus_val = int(m.group("val") or 0)
                except Exception:
                    bonus_val = 0
            elif name_norm == "sonic destruction":
                weapon_key = "vibro cannon"
                bonus_val = 1

            if not weapon_key or bonus_val <= 0:
                continue
            source = str(name or "Sonic Destruction").strip() or "Sonic Destruction"
            key = (source.lower(), weapon_key, int(bonus_val))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {"weapon_key": weapon_key, "bonus_per_other": int(bonus_val), "source": source}
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_spirit_mark_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: Spirit Mark selection during Movement phase.

        Returns a list of specs with keys:
            - keyword: str
            - range: int
            - sustained_hits_value: int
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_spirit_mark:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str, int, int]] = set()
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._SPIRIT_MARK_RE.fullmatch(normalized)
            if not m:
                continue
            keyword_raw = str(m.group("keyword") or "").strip()
            keyword = self._normalize_keyword_phrase(keyword_raw) or keyword_raw.lower()
            try:
                rng = int(m.group("range") or 0)
            except Exception:
                rng = 0
            try:
                val = int(m.group("val") or 1)
            except Exception:
                val = 1
            if rng <= 0 or val <= 0:
                continue
            source = str(name or "Spirit Mark").strip() or "Spirit Mark"
            key = (source.lower(), keyword, int(rng), int(val))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "keyword": keyword,
                    "range": int(rng),
                    "sustained_hits_value": int(val),
                    "source": source,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_tears_of_isha_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: Tears of Isha (Command phase Wraith Construct heal/return).

        Returns a list of specs with keys:
            - keyword: str
            - range: int
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_tears_of_isha:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str, int]] = set()
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._TEARS_OF_ISHA_RE.fullmatch(normalized)
            if not m:
                continue
            keyword_raw = str(m.group("keyword") or "").strip()
            keyword = self._normalize_keyword_phrase(keyword_raw) or keyword_raw.lower()
            try:
                rng = int(m.group("range") or 0)
            except Exception:
                rng = 0
            if rng <= 0:
                continue
            source = str(name or "Tears of Isha").strip() or "Tears of Isha"
            key = (source.lower(), keyword, int(rng))
            if key in seen:
                continue
            seen.add(key)
            specs.append({"keyword": keyword, "range": int(rng), "source": source})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_canoptek_swarm_specs(self) -> List[dict]:
        """
        Unit-specific rule: Canoptek Swarm (Command phase target selection + model return count).

        Returns a list of specs with keys:
            - target_keyword: str
            - count_keyword: str
            - range: int
            - source: ability name
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_canoptek_swarm_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str, str, int]] = set()

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._CANOPTEK_SWARM_RE.fullmatch(normalized)
                if not m:
                    continue

                target_keyword_raw = str(m.group("target_keyword") or "").strip()
                target_keyword = unit._normalize_keyword_phrase(target_keyword_raw) or target_keyword_raw.lower()
                count_keyword_raw = str(m.group("count_keyword") or "").strip()
                count_keyword = unit._normalize_keyword_phrase(count_keyword_raw) or count_keyword_raw.lower()
                try:
                    rng = int(m.group("range") or 0)
                except Exception:
                    rng = 0
                if rng <= 0 or not target_keyword or not count_keyword:
                    continue

                source = str(name or "Canoptek Swarm").strip() or "Canoptek Swarm"
                key = (source.lower(), target_keyword, count_keyword, int(rng))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "target_keyword": target_keyword,
                        "count_keyword": count_keyword,
                        "range": int(rng),
                        "source": source,
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_surrogate_hosts_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: Surrogate Hosts (start of Command phase model replacement).

        Returns a list of specs with keys:
            - source: ability name
            - required_keywords_all: list[str]
            - excluded_unit_names: list[str]
            - exclude_epic_hero: bool
            - attach_if_target_was_leading: bool
        """
        if model is None:
            return []
        cache_key = f"model_surrogate_hosts:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, tuple[str, ...], tuple[str, ...], bool, bool]] = set()
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = self._strip_eligibility_prefix(desc or name or "")
            if not text_src:
                continue
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not normalized:
                continue
            required_phrases = (
                "at the start of your command phase",
                "if this model is on the battlefield",
                "you can select one other friendly necrons infantry character model on the battlefield",
                "the selected model is destroyed",
                "ignoring any rules that are triggered when a model is destroyed",
                "this model is put in its place",
                "with all of its wounds remaining",
                "if the selected model was leading a unit this model now attaches to that unit as its leader",
            )
            if any(phrase not in normalized for phrase in required_phrases):
                continue
            if "excluding skorpekh lord" not in normalized:
                continue
            if "epic hero" not in normalized:
                continue

            source = str(name or "Surrogate Hosts").strip() or "Surrogate Hosts"
            required_keywords_all = ("NECRONS", "INFANTRY", "CHARACTER")
            excluded_unit_names = ("Skorpekh Lord",)
            exclude_epic_hero = True
            attach_if_target_was_leading = True
            key = (
                source.lower(),
                required_keywords_all,
                excluded_unit_names,
                bool(exclude_epic_hero),
                bool(attach_if_target_was_leading),
            )
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "required_keywords_all": list(required_keywords_all),
                    "excluded_unit_names": list(excluded_unit_names),
                    "exclude_epic_hero": bool(exclude_epic_hero),
                    "attach_if_target_was_leading": bool(attach_if_target_was_leading),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_eternity_gate_specs(self) -> List[dict]:
        """
        Unit-specific rule: Eternity Gate (Reinforcements-step setup of friendly NECRONS INFANTRY).

        Returns a list of specs with keys:
            - source: ability name
            - range: int
            - no_charge_this_turn: bool
            - target_keywords_any: list[str]
            - allow_target_in_reserves: bool
            - allow_target_on_battlefield: bool
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_eternity_gate_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "reinforcements step of your movement phase" not in normalized:
                    continue
                if "select one necrons infantry unit" not in normalized:
                    continue
                if "either in reserves or on the battlefield" not in normalized:
                    continue
                if "remove that unit from the battlefield and place it into reserves" not in normalized:
                    continue
                if "wholly within 6 of this model" not in normalized:
                    continue
                if "not within engagement range of any enemy models" not in normalized:
                    continue
                if "cannot declare a charge this turn" not in normalized:
                    continue
                source = str(name or "Eternity Gate").strip() or "Eternity Gate"
                key = (source.lower(), 6)
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "range": 6,
                        "no_charge_this_turn": True,
                        "target_keywords_any": ["NECRONS", "INFANTRY"],
                        "allow_target_in_reserves": True,
                        "allow_target_on_battlefield": True,
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_prophet_of_destruction_specs(self) -> List[dict]:
        """
        Unit-specific rule: each time this model destroys an enemy unit, select one other friendly
        DESTROYER CULT unit within range; selected unit re-rolls Wound rolls of 1 until phase end.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
            - target_keyword_phrase: str
            - reroll_wound_values: list[int]
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_prophet_of_destruction_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "each time this model destroys an enemy unit" not in normalized:
                    continue
                if "select one other friendly destroyer cult unit within" not in normalized:
                    continue
                if "until the end of the phase" not in normalized:
                    continue
                if "reroll a wound roll of 1" not in normalized and "re roll a wound roll of 1" not in normalized:
                    continue
                match = re.search(
                    r"select one other friendly destroyer cult unit within (?P<range>\d+)",
                    normalized,
                )
                if not match:
                    continue
                try:
                    range_value = int(match.group("range") or 0)
                except Exception:
                    range_value = 0
                if range_value <= 0:
                    continue
                source = str(name or "Prophet of Destruction").strip() or "Prophet of Destruction"
                key = (source.lower(), int(range_value))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "range": int(range_value),
                        "target_keyword_phrase": "DESTROYER CULT",
                        "reroll_wound_values": [1],
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_post_shoot_leadership_debuff_specs(self) -> List[dict]:
        """
        Unit-specific rule: after this unit has shot, select a hit enemy unit; that unit suffers -1 to
        Battle-shock/Leadership tests until the start of your next Shooting phase.

        Returns a list of specs with keys:
            - source: ability name
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_shoot_leadership_debuff_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[str] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not unit._POST_SHOOT_LEADERSHIP_DEBUFF_RE.fullmatch(normalized):
                    continue
                source = str(name or "Post-shoot Leadership debuff").strip() or "Post-shoot Leadership debuff"
                key = source.lower()
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"source": source})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_post_shoot_no_cover_specs(self) -> List[dict]:
        """
        Unit-specific rule: after this unit has shot, select a hit enemy unit; target loses Benefit of Cover.

        Returns a list of specs with keys:
            - source: ability name
            - weapon_key: Optional[str] (normalized; None means any weapon)
            - weapon_name: str (display)
            - any_weapon: bool
            - duration: str ("phase_end" | "owner_next_shooting_start")
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_shoot_no_cover_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, str, str]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._POST_SHOOT_NO_COVER_WEAPON_RE.fullmatch(normalized)
                weapon_raw = ""
                weapon_key = ""
                any_weapon = False
                duration = "phase_end"
                if m:
                    weapon_raw = str(m.group("weapon") or "").strip()
                    if weapon_raw:
                        weapon_key = unit._normalize_keyword_phrase(weapon_raw) or weapon_raw.lower()
                    duration_raw = str(m.group("duration") or "").strip().lower()
                    if "start of your next shooting phase" in duration_raw:
                        duration = "owner_next_shooting_start"
                else:
                    m = unit._POST_SHOOT_NO_COVER_RE.fullmatch(normalized)
                    if not m:
                        continue
                    any_weapon = True
                    duration_raw = str(m.group("duration") or "").strip().lower()
                    if "start of your next shooting phase" in duration_raw:
                        duration = "owner_next_shooting_start"
                source = str(name or "Post-shoot no cover").strip() or "Post-shoot no cover"
                key = (source.lower(), weapon_key or "any", duration)
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "weapon_key": weapon_key or None,
                        "weapon_name": weapon_raw,
                        "any_weapon": bool(any_weapon),
                        "duration": str(duration),
                    }
                )
            source_sr = getattr(unit, "special_rules", None)
            if isinstance(source_sr, dict) and bool(source_sr.get("enhancement_warp_tracer")):
                source = str(source_sr.get("enhancement_warp_tracer_source", "") or "Warp Tracer").strip() or "Warp Tracer"
                duration = str(source_sr.get("enhancement_warp_tracer_expires_timing", "") or "phase_end").strip().lower()
                if duration not in {"phase_end", "owner_next_shooting_start"}:
                    duration = "phase_end"
                key = (source.lower(), "any", duration)
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "weapon_key": None,
                        "weapon_name": "",
                        "any_weapon": True,
                        "duration": str(duration),
                        "source_model_id": str(
                            source_sr.get("enhancement_warp_tracer_bearer_model_id", "")
                            or source_sr.get("enhancement_bearer_model_id", "")
                            or ""
                        ),
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_post_shoot_ap_bonus_specs(self) -> List[dict]:
        """
        Unit-specific rule: after this unit has shot, select a hit enemy unit; friendly keyword attacks vs that unit improve AP.

        Returns a list of specs with keys:
            - source: ability name
            - keyword: str (normalized)
            - attack_type: str (any|ranged|melee)
            - value: int (AP improvement)
            - limit_scope: Optional[str] ("turn"|"phase")
            - exclude_monster_vehicle: bool
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_shoot_ap_bonus_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, str, str, int, bool]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._POST_SHOOT_AP_BONUS_RE.fullmatch(normalized)
                if not m:
                    continue
                keyword_raw = str(m.group("keyword") or "").strip()
                if not keyword_raw:
                    continue
                keyword = unit._normalize_keyword_phrase(keyword_raw) or keyword_raw.lower()
                attack_type = str(m.group("atype") or "any").strip().lower() or "any"
                try:
                    value = int(m.group("val") or 0)
                except Exception:
                    value = 0
                if value <= 0:
                    continue
                exclude_mv = bool(m.group("exclude"))
                limit_scope = None
                if "once per turn" in normalized:
                    limit_scope = "turn"
                elif "once per phase" in normalized:
                    limit_scope = "phase"
                source = str(name or "Post-shoot AP bonus").strip() or "Post-shoot AP bonus"
                key = (source.lower(), keyword, attack_type, int(value), bool(exclude_mv))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "keyword": keyword,
                        "attack_type": attack_type,
                        "value": int(value),
                        "limit_scope": limit_scope,
                        "exclude_monster_vehicle": bool(exclude_mv),
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_daemonic_poisons_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model shoots/fights, select a hit enemy unit; that unit is poisoned.

        Returns a list of specs with keys:
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_daemonic_poisons:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            name_norm = str(name or "").strip().lower()
            if name_norm == "daemonic poisons":
                source = str(name or "Daemonic Poisons").strip() or "Daemonic Poisons"
                key = source.lower()
                if key not in seen:
                    seen.add(key)
                    specs.append({"source": source})
                continue
            text_src = self._strip_eligibility_prefix(desc or name or "")
            if not text_src:
                continue
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._DAEMONIC_POISONS_RE.fullmatch(normalized):
                continue
            source = str(name or "Daemonic Poisons").strip() or "Daemonic Poisons"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_post_shoot_keyword_wound_reroll_specs(self) -> List[dict]:
        """
        Unit-specific rule: after this unit has shot, select a hit enemy unit; friendly keyword units can re-roll Wound rolls vs that unit.

        Returns a list of specs with keys:
            - source: ability name
            - keyword_phrase: str
            - limit_scope: str ("turn")
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_shoot_keyword_wound_reroll_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._POST_SHOOT_KEYWORD_WOUND_REROLL_RE.fullmatch(normalized)
                if not m:
                    continue
                keyword_raw = str(m.group("keyword") or "").strip()
                if not keyword_raw:
                    continue
                keyword_phrase = " ".join(keyword_raw.split())
                source = str(name or "Post-shoot Wound reroll").strip() or "Post-shoot Wound reroll"
                key = (source.lower(), keyword_phrase.lower())
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "keyword_phrase": keyword_phrase,
                        "limit_scope": "turn",
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_engagement_battleshock_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: at the start of the Fight phase, enemies in engagement range test Battle-shock.

        Returns a list of specs with keys:
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_engagement_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._FIGHT_PHASE_ENGAGEMENT_BATTLESHOCK_RE.search(normalized)
            if not m:
                continue
            penalty = 0
            try:
                penalty = int(m.group("penalty") or 0)
            except Exception:
                penalty = 0
            source = str(name or "Fight phase Battle-shock").strip() or "Fight phase Battle-shock"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "penalty": penalty})

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and sr.get("enhancement_traitoris_nightmares_master"):
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
            model_id = str(get_entity_id(model) or "")
            if bearer_id and model_id and bearer_id == model_id:
                source = "Nightmare's Master"
                key = source.lower()
                if key not in seen:
                    seen.add(key)
                    specs.append({"source": source, "penalty": 0})
        if isinstance(sr, dict) and sr.get("enhancement_terrorglut_parasite"):
            bearer_id = str(
                sr.get("enhancement_terrorglut_parasite_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            model_id = str(get_entity_id(model) or "")
            if bearer_id and model_id and bearer_id == model_id:
                requires_bearer_alive = bool(sr.get("enhancement_terrorglut_parasite_requires_bearer_alive", True))
                if (not requires_bearer_alive) or bool(getattr(model, "is_alive", False)):
                    source = str(
                        sr.get("enhancement_terrorglut_parasite_source", "") or "Terrorglut Parasite"
                    ).strip() or "Terrorglut Parasite"
                    key = source.lower()
                    if key not in seen:
                        seen.add(key)
                        try:
                            penalty = int(sr.get("enhancement_terrorglut_parasite_battle_shock_test_modifier", -1) or -1)
                        except (TypeError, ValueError):
                            penalty = -1
                        if penalty > 0:
                            penalty = -penalty
                        if penalty == 0:
                            penalty = -1
                        specs.append(
                            {
                                "source": source,
                                "penalty": int(penalty),
                                "penalty_applies_when_below_half": False,
                            }
                        )
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        model_id = str(get_entity_id(model) or "")
        for member in members:
            sr_member = getattr(member, "special_rules", None)
            if not isinstance(sr_member, dict) or not bool(sr_member.get("enhancement_face_of_death", False)):
                continue
            bearer_id = str(
                sr_member.get("enhancement_face_of_death_bearer_model_id", "")
                or sr_member.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            if bearer_id and model_id and bearer_id != model_id:
                continue
            requires_bearer_alive = bool(sr_member.get("enhancement_face_of_death_requires_bearer_alive", True))
            if requires_bearer_alive and not bool(getattr(model, "is_alive", False)):
                continue
            source = str(sr_member.get("enhancement_face_of_death_source", "") or "Face of Death").strip() or "Face of Death"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "penalty": 0})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_aura_battleshock_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: at the start of the Fight phase, enemies within range test Battle-shock.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
            - exclude_keywords: list[str]
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_range_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, tuple[str, ...]]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._FIGHT_PHASE_RANGE_BATTLESHOCK_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            exclude_raw = str(m.group("exclude") or "").strip()
            exclude_keywords: list[str] = []
            if exclude_raw:
                tokens = re.split(r"\band\b|,", exclude_raw)
                for token in tokens:
                    t = str(token or "").strip().lower()
                    if not t:
                        continue
                    if t == "monsters":
                        exclude_keywords.append("MONSTER")
                    elif t == "vehicles":
                        exclude_keywords.append("VEHICLE")
                    else:
                        exclude_keywords.append(str(t).upper())
            source = str(name or "Fight phase Battle-shock").strip() or "Fight phase Battle-shock"
            key = (source.lower(), int(range_value), tuple(exclude_keywords))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "exclude_keywords": list(exclude_keywords),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_select_engagement_battleshock_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: at the start of the Fight phase, select one enemy unit
        within Engagement Range of this model; that enemy unit takes a Battle-shock test.

        Returns a list of specs with keys:
            - source: ability name
            - ability_key: str
            - optional: bool
            - once_per_turn: bool
            - engagement_only: bool
            - test_penalty: int (optional)
            - context_ability: str
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_select_engagement_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str, bool, bool, int]] = set()
        pattern = (
            r"(?:(?P<once>once per turn) )?"
            r"(?:at the )?start of the fight phase "
            r"(?P<optional>you can )?select one enemy unit within engagement range of "
            r"(?:this model|the bearer|this unit(?: s [a-z0-9 ]+ model)?) "
            r"that(?: enemy)? unit must take a battle shock test"
            r"(?: subtracting (?P<penalty>\d+) from (?:that test|the result)(?: when it does so)?)?"
        )

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = re.fullmatch(pattern, normalized)
            if not m:
                continue
            optional = bool(str(m.group("optional") or "").strip())
            once_per_turn = bool(str(m.group("once") or "").strip())
            try:
                test_penalty = int(m.group("penalty") or 0)
            except (TypeError, ValueError):
                test_penalty = 0
            if test_penalty < 0:
                test_penalty = abs(int(test_penalty))
            source = str(name or "Fight phase select Engagement Battle-shock").strip()
            source = source or "Fight phase select Engagement Battle-shock"
            source_key = self._normalize_keyword_phrase(source) or re.sub(r"[^a-z0-9]+", "_", source.lower()).strip("_")
            if not source_key:
                source_key = "fight_phase_select_engagement_battleshock"
            ability_key = f"fight_phase_select_engagement_battleshock:{source_key}"
            dedupe_key = (
                source.lower(),
                ability_key,
                bool(optional),
                bool(once_per_turn),
                int(test_penalty),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            specs.append(
                {
                    "source": source,
                    "ability_key": ability_key,
                    "optional": bool(optional),
                    "once_per_turn": bool(once_per_turn),
                    "engagement_only": True,
                    "test_penalty": int(test_penalty),
                    "context_ability": "fight_phase_select_engagement_battleshock",
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_select_enemy_melee_hit_penalty_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: at the start of the Fight phase, select one enemy unit within
        Engagement Range; until phase end, models in that unit suffer a Hit roll penalty
        when making attacks in the Fight phase.

        Returns a list of specs with keys:
            - source: ability name
            - ability_key: str
            - optional: bool
            - once_per_turn: bool
            - engagement_only: bool
            - hit_penalty: int
            - context_ability: str
        """
        if model is None:
            return []
        cache_key = f"model_start_fight_phase_select_enemy_melee_hit_penalty:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str, int, bool]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._FIGHT_PHASE_SELECT_ENGAGEMENT_MELEE_HIT_PENALTY_RE.fullmatch(normalized)
            if not m:
                continue
            optional = bool(str(m.group("optional") or "").strip())
            try:
                hit_penalty = int(m.group("penalty") or 0)
            except (TypeError, ValueError):
                hit_penalty = 0
            if hit_penalty <= 0:
                continue
            source = str(name or "Fight phase select enemy hit penalty").strip() or "Fight phase select enemy hit penalty"
            source_key = self._normalize_keyword_phrase(source) or re.sub(r"[^a-z0-9]+", "_", source.lower()).strip("_")
            if not source_key:
                source_key = "fight_phase_select_enemy_melee_hit_penalty"
            ability_key = f"fight_phase_select_enemy_melee_hit_penalty:{source_key}"
            dedupe_key = (source.lower(), ability_key, int(hit_penalty), bool(optional))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            specs.append(
                {
                    "source": source,
                    "ability_key": ability_key,
                    "optional": bool(optional),
                    "once_per_turn": False,
                    "engagement_only": True,
                    "hit_penalty": int(hit_penalty),
                    "context_ability": "fight_phase_select_enemy_melee_hit_penalty",
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_engagement_wound_reroll_ones_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: at the start of the Fight phase, select an engaged enemy unit;
        friendly keyword attacks re-roll Wound rolls of 1 against that unit until phase end.

        Returns a list of specs with keys:
            - source: ability name
            - keyword: str (normalized)
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_engagement_wound_reroll_ones:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._FIGHT_PHASE_ENGAGEMENT_WOUND_REROLL_ONES_RE.fullmatch(normalized)
            if not m:
                continue
            keyword_raw = str(m.group("keyword") or "").strip()
            keyword = self._normalize_keyword_phrase(keyword_raw) or keyword_raw.lower() or "friendly"
            source = str(name or "Fight phase wound reroll").strip() or "Fight phase wound reroll"
            key = (source.lower(), keyword)
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "keyword": keyword})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_melee_attacks_ap_boost_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: once per battle, at the start of the Fight phase, add 3 Attacks and improve AP by 1.

        Returns a list of specs with keys:
            - source: ability name
            - key: once-per-battle tracking key
            - attacks_bonus: int
            - ap_bonus: int
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_melee_ap_boost:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._FIGHT_PHASE_ONCE_MELEE_AP_ATTACKS_RE.fullmatch(normalized):
                continue
            source = str(name or "Fight phase melee boost").strip() or "Fight phase melee boost"
            key_seed = self._normalize_keyword_phrase(source)
            if not key_seed:
                key_seed = "fight_phase_melee_ap_boost"
            key = f"fight_phase_melee_ap_boost:{key_seed}"
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "key": key,
                    "attacks_bonus": 3,
                    "ap_bonus": 1,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_blinding_spray_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: once per battle in the Fight phase, optional activation grants Fights First to its unit.

        Returns specs with keys:
            - source: ability name
            - ability_key: per-model once-per-battle key
        """
        if model is None:
            return []
        cache_key = f"model_start_fight_phase_blinding_spray:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()
        model_id = str(get_entity_id(model) or "")
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"'s\b", "s", normalized)
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._BLINDING_SPRAY_RE.fullmatch(normalized):
                continue
            source = str(name or "Blinding Spray").strip() or "Blinding Spray"
            key = "blinding_spray"
            if model_id:
                key = f"blinding_spray:{model_id}"
            dedupe_key = f"{source.lower()}:{key}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            specs.append({"source": source, "ability_key": key})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_inflamed_infections_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: at the start of the Fight phase, select one engaged enemy unit.
        Until phase end, this model scores critical hits on a lower unmodified Hit roll threshold
        against that unit (typically 5+, or 4+ while that unit is Below Half-strength).
        """
        if model is None:
            return []
        cache_key = f"model_start_fight_phase_inflamed_infections:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"'s\b", "s", normalized)
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if "start of the fight phase" not in normalized:
                continue
            if "within engagement range of this model" not in normalized:
                continue
            if "scores a critical hit" not in normalized:
                continue
            if "hit roll of 5" not in normalized:
                continue
            threshold = 5
            threshold_below_half = 5
            if "below half strength" in normalized:
                if "hit roll of 4" in normalized or "or 4 if" in normalized:
                    threshold_below_half = 4
            source = str(name or "Inflamed Infections").strip() or "Inflamed Infections"
            key = (source.lower(), int(threshold), int(threshold_below_half))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "threshold": int(threshold),
                    "threshold_below_half": int(threshold_below_half),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_melee_attacks_strength_boost_specs(
        self,
        model: Optional['Model'] = None,
    ) -> List[dict]:
        """
        Model-specific rule: once per battle, at the start of the Fight phase, add Attacks and Strength.

        Returns a list of specs with keys:
            - source: ability name
            - key: once-per-battle tracking key
            - attacks_bonus: int
            - strength_bonus: int
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_melee_attacks_strength_boost:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._FIGHT_PHASE_MELEE_ATTACKS_STRENGTH_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                bonus = int(m.group("add_val") or m.group("improve_val") or 0)
            except Exception:
                bonus = 0
            if bonus <= 0:
                continue
            source = str(name or "Fight phase melee attacks/strength boost").strip() or "Fight phase melee attacks/strength boost"
            key_seed = self._normalize_keyword_phrase(source)
            if not key_seed:
                key_seed = "fight_phase_melee_attacks_strength_boost"
            key = f"fight_phase_melee_attacks_strength_boost:{key_seed}"
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "key": key,
                    "attacks_bonus": int(bonus),
                    "strength_bonus": int(bonus),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_weapon_triple_attacks_strength_crit_wound_specs(
        self,
        model: Optional['Model'] = None,
    ) -> List[dict]:
        """
        Model-specific rule: once per battle, at the start of the Fight phase,
        triple a named weapon's Attacks/Strength and make successful wound rolls critical.

        Returns a list of specs with keys:
            - source: ability name
            - key: once-per-battle tracking key
            - weapon_name: str
            - attacks_multiplier: int
            - strength_multiplier: int
            - crit_wound_threshold: int
            - crit_all_attacks: bool
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_weapon_triple_attacks_strength_crit_wound:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, str]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._FIGHT_PHASE_WEAPON_TRIPLE_ATTACKS_STRENGTH_CRIT_WOUND_RE.fullmatch(normalized)
            if not m:
                continue
            weapon_name = str(m.group("weapon") or "").strip()
            if not weapon_name:
                continue
            source = str(name or "Fight phase weapon triple attacks/strength").strip() or "Fight phase weapon triple attacks/strength"
            key_seed = self._normalize_keyword_phrase(source) or "fight_phase_weapon_triple_attacks_strength_crit_wound"
            key = f"fight_phase_weapon_triple_attacks_strength_crit_wound:{key_seed}"
            de_dupe = (key, self._normalize_keyword_phrase(weapon_name) or weapon_name.lower())
            if de_dupe in seen:
                continue
            seen.add(de_dupe)
            specs.append(
                {
                    "source": source,
                    "key": key,
                    "weapon_name": weapon_name,
                    "attacks_multiplier": 3,
                    "strength_multiplier": 3,
                    "crit_wound_threshold": 2,
                    "crit_all_attacks": True,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_melee_attacks_set_invuln_specs(
        self,
        model: Optional['Model'] = None,
    ) -> List[dict]:
        """
        Model-specific rule: once per battle, at the start of the Fight phase, set melee weapon Attacks and invulnerable save.

        Returns a list of specs with keys:
            - source: ability name
            - key: once-per-battle tracking key
            - attacks_value: int (set Attacks characteristic for melee weapons)
            - invuln: int (invulnerable save value)
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_melee_attacks_set_invuln:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._FIGHT_PHASE_MELEE_ATTACKS_SET_INVULN_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                invuln = int(m.group("invuln") or 0)
            except Exception:
                invuln = 0
            try:
                attacks_value = int(m.group("attacks") or 0)
            except Exception:
                attacks_value = 0
            if invuln <= 0 or attacks_value <= 0:
                continue
            source = str(name or "Fight phase melee attacks set").strip() or "Fight phase melee attacks set"
            key_seed = self._normalize_keyword_phrase(source) or "fight_phase_melee_attacks_set_invuln"
            key = f"fight_phase_melee_attacks_set_invuln:{key_seed}"
            spec_key = (key, int(invuln), int(attacks_value))
            if spec_key in seen:
                continue
            seen.add(spec_key)
            specs.append(
                {
                    "source": source,
                    "key": key,
                    "invuln": int(invuln),
                    "attacks_value": int(attacks_value),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_data_spike_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: at the start of the Fight phase, optionally select one engaged enemy VEHICLE unit,
        roll one D6 and on a threshold apply mortal wounds and worsen melee Weapon Skill until phase end.

        Returns list of specs with keys:
            - source: ability name
            - threshold: int
            - mortal_wounds: str
            - ws_penalty: int
        """
        if model is None:
            return []
        cache_key = f"model_start_fight_phase_data_spike:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._FIGHT_PHASE_DATA_SPIKE_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                threshold = int(m.group("threshold") or 0)
            except Exception:
                threshold = 0
            threshold = max(2, min(6, int(threshold or 0)))
            mw_value = str(m.group("mw") or "").strip().upper()
            if not mw_value:
                mw_value = "D6"
            try:
                ws_penalty = int(m.group("pen") or 0)
            except Exception:
                ws_penalty = 0
            if threshold <= 0 or ws_penalty <= 0:
                continue
            source = str(name or "Data-spike").strip() or "Data-spike"
            key = (source.lower(), int(threshold), str(mw_value), int(ws_penalty))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "threshold": int(threshold),
                    "mortal_wounds": str(mw_value),
                    "ws_penalty": int(ws_penalty),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_friendly_melee_ws_bonus_specs(
        self,
        model: Optional['Model'] = None,
    ) -> List[dict]:
        """
        Model-specific rule: at the start of the Fight phase, select one nearby friendly keyword unit and
        improve melee Weapon Skill characteristics by a fixed amount until phase end.

        Returns list of specs with keys:
            - source: ability name
            - range: int
            - keyword: str
            - ws_bonus: int
        """
        if model is None:
            return []
        cache_key = f"model_start_fight_phase_friendly_melee_ws_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._FIGHT_PHASE_FRIENDLY_MELEE_WS_BONUS_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            try:
                ws_bonus = int(m.group("bonus") or 0)
            except Exception:
                ws_bonus = 0
            if range_value <= 0 or ws_bonus <= 0:
                continue
            keyword_raw = str(m.group("keyword") or "").strip()
            keyword = self._normalize_keyword_phrase(keyword_raw) or keyword_raw.lower()
            if not keyword:
                continue
            source = str(name or "Fight phase friendly melee WS bonus").strip() or "Fight phase friendly melee WS bonus"
            key = (source.lower(), int(range_value), str(keyword), int(ws_bonus))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "keyword": str(keyword),
                    "ws_bonus": int(ws_bonus),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_melee_full_characteristic_boost_specs(
        self,
        model: Optional['Model'] = None,
    ) -> List[dict]:
        """
        Model-specific rule: once per battle, at the start of the Fight phase, improve S/A/AP/D by 1.

        Returns a list of specs with keys:
            - source: ability name
            - key: once-per-battle tracking key
            - bonus: int
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_melee_full_boost:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._FIGHT_PHASE_MELEE_FULL_BUFF_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                bonus = int(m.group("val") or 0)
            except Exception:
                bonus = 0
            if bonus <= 0:
                continue
            source = str(name or "Fight phase melee boost").strip() or "Fight phase melee boost"
            key_seed = self._normalize_keyword_phrase(source)
            if not key_seed:
                key_seed = "fight_phase_melee_full_boost"
            key = f"fight_phase_melee_full_boost:{key_seed}"
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "key": key, "bonus": int(bonus)})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_hellforged_attacks_bonus_specs(
        self,
        model: Optional['Model'] = None,
    ) -> List[dict]:
        """
        Model-specific rule: once per battle, at the start of the Fight phase, add Attacks to hellforged weapons.

        Returns a list of specs with keys:
            - source: ability name
            - key: once-per-battle tracking key
            - weapon_name: str
            - attacks_bonus: int
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_hellforged_attacks:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._FIGHT_PHASE_HELLFORGED_ATTACKS_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                bonus = int(m.group("val") or 0)
            except Exception:
                bonus = 0
            if bonus <= 0:
                continue
            source = str(name or "Fight phase hellforged attacks").strip() or "Fight phase hellforged attacks"
            key_seed = self._normalize_keyword_phrase(source)
            if not key_seed:
                key_seed = "fight_phase_hellforged_attacks"
            key = f"fight_phase_hellforged_attacks:{key_seed}"
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "key": key,
                    "weapon_name": "hellforged",
                    "attacks_bonus": int(bonus),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_target_attack_bonus_specs(
        self,
        model: Optional['Model'] = None,
    ) -> List[dict]:
        """
        Model-specific rule: at the start of the Fight phase, select an enemy unit within range (optionally visible);
        friendly keyword attacks gain bonuses vs that target until end of phase.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
            - requires_visibility: bool
            - keyword: str
            - attack_type: str ("melee" | "ranged" | "any")
            - strength_bonus: int
            - ap_bonus: int
            - damage_bonus: int
            - wound_bonus: int
            - enemy_melee_wound_penalty: int
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_target_attack_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            source = str(name or "Fight phase target bonus").strip() or "Fight phase target bonus"

            m = self._FIGHT_PHASE_TARGET_ATTACK_BONUS_RE.fullmatch(normalized)
            if m:
                try:
                    range_value = int(m.group("range") or 0)
                except Exception:
                    range_value = 0
                if range_value <= 0:
                    continue
                try:
                    bonus = int(m.group("val") or 0)
                except Exception:
                    bonus = 0
                if bonus <= 0:
                    continue
                keyword_raw = str(m.group("keyword") or "").strip()
                keyword = self._normalize_keyword_phrase(keyword_raw) or keyword_raw.lower() or "friendly"
                requires_visibility = "visible to this model" in normalized
                key = (source.lower(), range_value, keyword, bonus, "sapd")
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "range": int(range_value),
                        "requires_visibility": bool(requires_visibility),
                        "keyword": keyword,
                        "attack_type": "any",
                        "strength_bonus": int(bonus),
                        "ap_bonus": int(bonus),
                        "damage_bonus": int(bonus),
                        "wound_bonus": 0,
                        "enemy_melee_wound_penalty": 0,
                    }
                )
                continue

            m = self._FIGHT_PHASE_TARGET_DAMAGE_BONUS_RE.fullmatch(normalized)
            if m:
                try:
                    range_value = int(m.group("range") or 0)
                except Exception:
                    range_value = 0
                if range_value <= 0:
                    continue
                try:
                    bonus = int(m.group("val") or 0)
                except Exception:
                    bonus = 0
                if bonus <= 0:
                    continue
                keyword_raw = str(m.group("keyword") or "").strip()
                keyword = self._normalize_keyword_phrase(keyword_raw) or keyword_raw.lower() or "friendly"
                requires_visibility = "visible to this model" in normalized
                key = (source.lower(), range_value, keyword, bonus, "damage")
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "range": int(range_value),
                        "requires_visibility": bool(requires_visibility),
                        "keyword": keyword,
                        "attack_type": "any",
                        "strength_bonus": 0,
                        "ap_bonus": 0,
                        "damage_bonus": int(bonus),
                        "wound_bonus": 0,
                        "enemy_melee_wound_penalty": 0,
                    }
                )
                continue

            m = self._FIGHT_PHASE_TARGET_MELEE_WOUND_BONUS_RE.search(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            keyword_raw = str(m.group("keyword") or "").strip()
            keyword = self._normalize_keyword_phrase(keyword_raw) or keyword_raw.lower() or "friendly"
            try:
                bonus = int(m.group("bonus") or 0)
            except Exception:
                bonus = 0
            if bonus <= 0:
                continue
            penalty = 0
            try:
                p = self._FIGHT_PHASE_TARGET_MELEE_WOUND_PENALTY_RE.search(normalized)
                if p:
                    penalty = int(p.group("pen") or 0)
            except Exception:
                penalty = 0
            key = (source.lower(), range_value, keyword, bonus, penalty, "wound")
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "requires_visibility": False,
                    "keyword": keyword,
                    "attack_type": "melee",
                    "strength_bonus": 0,
                    "ap_bonus": 0,
                    "damage_bonus": 0,
                    "wound_bonus": int(bonus),
                    "enemy_melee_wound_penalty": int(penalty),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_any_phase_damage_set_one_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: once per battle, at the start of any phase, set incoming damage to 1.

        Returns a list of specs with keys:
            - source: ability name
            - key: once-per-battle tracking key
            - value: int (damage override)
        """
        if model is None:
            return []
        cache_key = f"model_start_any_phase_damage_set_one:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._START_ANY_PHASE_DAMAGE_SET_ONE_RE.fullmatch(normalized):
                continue
            source = str(name or "Damage set to 1").strip() or "Damage set to 1"
            key_seed = self._normalize_keyword_phrase(source) or "damage_set_one"
            key = f"start_any_phase_damage_set_one:{key_seed}"
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "key": key, "value": 1})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_any_phase_invulnerable_save_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: once per battle, at the start of any phase, gain an invulnerable save until end of phase.

        Returns a list of specs with keys:
            - source: ability name
            - key: once-per-battle tracking key
            - value: int (invulnerable save)
            - apply_to_unit: bool (if True, apply to all models in this model's unit)
        """
        if model is None:
            return []
        cache_key = f"model_start_any_phase_invuln:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._START_ANY_PHASE_MODEL_INVULN_RE.fullmatch(normalized)
            apply_to_unit = False
            if not m:
                m = self._START_ANY_PHASE_MODEL_UNIT_INVULN_RE.fullmatch(normalized)
                apply_to_unit = bool(m)
            if not m:
                continue
            try:
                invuln = int(m.group("invuln") or 0)
            except Exception:
                invuln = 0
            if invuln <= 0:
                continue
            source = str(name or "Start of phase invulnerable save").strip() or "Start of phase invulnerable save"
            key_seed = self._normalize_keyword_phrase(source) or "start_any_phase_invuln"
            key = f"start_any_phase_invuln:{key_seed}"
            key_tuple = (key, int(invuln))
            if key_tuple in seen:
                continue
            seen.add(key_tuple)
            specs.append(
                {
                    "source": source,
                    "key": key,
                    "value": int(invuln),
                    "apply_to_unit": bool(apply_to_unit),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_start_any_phase_clear_battleshock_specs(self) -> List[dict]:
        """
        Unit-specific rule: once per battle, at the start of any phase, clear Battle-shock on a friendly unit in range.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
            - keyword: str (raw keyword phrase)
            - model_name: Optional[str]
            - ability_key: str (once-per-battle tracking key)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_start_any_phase_clear_battleshock_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, str, str]] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = u._strip_eligibility_prefix(text_src)
                normalized = u._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = self._START_ANY_PHASE_CLEAR_BATTLESHOCK_RE.fullmatch(normalized)
                if not m:
                    continue
                keyword_raw = str(m.group("keyword") or "").strip()
                if not keyword_raw:
                    continue
                try:
                    range_value = int(m.group("range") or 0)
                except Exception:
                    range_value = 0
                if range_value <= 0:
                    continue
                model_name = str(m.group("model") or "").strip()
                source = str(name or "Start of phase Battle-shock clear").strip() or "Start of phase Battle-shock clear"
                key_seed = self._normalize_keyword_phrase(source) or "start_any_phase_clear_battleshock"
                ability_key = f"start_any_phase_clear_battleshock:{key_seed}"
                key = (source.lower(), int(range_value), keyword_raw.lower(), model_name.lower())
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "range": int(range_value),
                        "keyword": keyword_raw,
                        "model_name": model_name,
                        "ability_key": ability_key,
                    }
                )

        for u in members:
            if u is None:
                continue
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_mechanicus_locum", False)):
                continue
            try:
                range_value = int(float(sr.get("enhancement_mechanicus_locum_range", 12) or 12))
            except (TypeError, ValueError):
                range_value = 12
            if range_value <= 0:
                continue
            keyword_raw = str(sr.get("enhancement_mechanicus_locum_keyword_phrase", "") or "CULT MECHANICUS").strip()
            if not keyword_raw:
                keyword_raw = "CULT MECHANICUS"
            source = str(sr.get("enhancement_mechanicus_locum_source", "") or "Mechanicus Locum").strip() or "Mechanicus Locum"
            ability_seed = str(sr.get("enhancement_mechanicus_locum_once_key", "") or "mechanicus_locum").strip().lower()
            if not ability_seed:
                ability_seed = "mechanicus_locum"
            ability_key = f"start_any_phase_clear_battleshock:{ability_seed}"
            model_name = ""
            get_bearer = getattr(u, "_get_enhancement_bearer_model", None)
            if callable(get_bearer):
                bearer_model = get_bearer()
                if bearer_model is not None:
                    model_name = str(getattr(bearer_model, "name", "") or "").strip()
            key = (source.lower(), int(range_value), keyword_raw.lower(), model_name.lower())
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "keyword": keyword_raw,
                    "model_name": model_name,
                    "ability_key": ability_key,
                }
            )

        for u in members:
            if u is None:
                continue
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_inspirational_exemplar", False)):
                continue
            try:
                range_value = int(float(sr.get("enhancement_inspirational_exemplar_range", 12) or 12))
            except (TypeError, ValueError):
                range_value = 12
            if range_value <= 0:
                continue
            keyword_raw = str(sr.get("enhancement_inspirational_exemplar_keyword_phrase", "") or "ADEPTUS CUSTODES").strip()
            if not keyword_raw:
                keyword_raw = "ADEPTUS CUSTODES"
            source = str(sr.get("enhancement_inspirational_exemplar_source", "") or "Inspirational Exemplar").strip() or "Inspirational Exemplar"
            ability_seed = str(sr.get("enhancement_inspirational_exemplar_once_key", "") or "inspirational_exemplar").strip().lower()
            if not ability_seed:
                ability_seed = "inspirational_exemplar"
            ability_key = f"start_any_phase_clear_battleshock:{ability_seed}"
            model_name = ""
            get_bearer = getattr(u, "_get_enhancement_bearer_model", None)
            if callable(get_bearer):
                bearer_model = get_bearer()
                if bearer_model is not None:
                    model_name = str(getattr(bearer_model, "name", "") or "").strip()
            key = (source.lower(), int(range_value), keyword_raw.lower(), model_name.lower())
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "keyword": keyword_raw,
                    "model_name": model_name,
                    "ability_key": ability_key,
                }
            )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_start_any_phase_tome_skull_specs(self) -> List[dict]:
        """
        Unit-specific rule: per Tome-skull, at the start of any phase, choose either:
        - one friendly Battle-shocked unit in range to clear Battle-shock, or
        - one enemy unit in range to take a Battle-shock test.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
            - friendly_keyword: str
            - ability_key: str
            - per_tome_skull: bool
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_start_any_phase_tome_skull_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, str]] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = unit._strip_eligibility_prefix(text_src)
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = self._START_ANY_PHASE_TOME_SKULL_RE.fullmatch(normalized)
                if not m:
                    continue
                try:
                    range_value = int(m.group("range") or 0)
                except (TypeError, ValueError):
                    range_value = 0
                try:
                    enemy_range = int(m.group("enemy_range") or 0)
                except (TypeError, ValueError):
                    enemy_range = 0
                if range_value <= 0:
                    continue
                if enemy_range > 0 and enemy_range != range_value:
                    continue
                friendly_keyword = str(m.group("keyword") or "").strip()
                if not friendly_keyword:
                    continue
                source = str(name or "Tome-skull").strip() or "Tome-skull"
                key_seed = self._normalize_keyword_phrase(source) or "tome_skull"
                ability_key = f"start_any_phase_tome_skull:{key_seed}"
                dedupe_key = (ability_key, int(range_value), friendly_keyword.lower())
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                specs.append(
                    {
                        "source": source,
                        "range": int(range_value),
                        "friendly_keyword": friendly_keyword,
                        "ability_key": ability_key,
                        "per_tome_skull": True,
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_start_any_phase_fnp_specs(self) -> List[dict]:
        """
        Unit-specific rule: once per battle, at the start of any phase, grant Feel No Pain to the unit.

        Returns a list of specs with keys:
            - source: ability name
            - value: int (FNP roll)
            - ability_key: str (once-per-battle tracking key)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_start_any_phase_fnp_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = u._strip_eligibility_prefix(text_src)
                normalized = u._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = self._START_ANY_PHASE_UNIT_FNP_RE.fullmatch(normalized)
                if not m:
                    continue
                try:
                    val = int(m.group("val") or 0)
                except Exception:
                    val = 0
                if val <= 0:
                    continue
                source = str(name or "Start of phase FNP").strip() or "Start of phase FNP"
                key_seed = self._normalize_keyword_phrase(source) or "start_any_phase_fnp"
                ability_key = f"start_any_phase_fnp:{key_seed}"
                key = (source.lower(), int(val))
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"source": source, "value": int(val), "ability_key": ability_key})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_movement_phase_normal_move_weapon_attacks_bonus_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: once per battle, before a Normal move in the Movement phase, add Move (dice) and weapon Attacks.

        Returns a list of specs with keys:
            - source: ability name
            - key: once-per-battle tracking key
            - move_bonus_dice: str (e.g., "2D6")
            - attacks_bonus: int
            - weapon_name: str (weapon name pattern)
        """
        if model is None:
            return []
        cache_key = f"model_movement_phase_normal_move_weapon_attacks_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._MOVEMENT_PHASE_ONCE_NORMAL_MOVE_WEAPON_ATTACKS_RE.fullmatch(normalized)
            if not m:
                continue
            move_token = str(m.group("move") or "").strip().upper()
            if not move_token:
                continue
            move_bonus_dice = ""
            move_bonus_flat = 0
            if "D" in move_token:
                move_bonus_dice = move_token
            else:
                try:
                    move_bonus_flat = int(move_token or 0)
                except Exception:
                    move_bonus_flat = 0
                if move_bonus_flat <= 0:
                    continue
            try:
                attacks_bonus = int(m.group("attacks") or 0)
            except Exception:
                attacks_bonus = 0
            if attacks_bonus <= 0:
                continue
            weapon_name = str(m.group("weapon") or "").strip()
            if not weapon_name:
                continue
            source = str(name or "Movement phase normal move boost").strip() or "Movement phase normal move boost"
            key_seed = self._normalize_keyword_phrase(source)
            if not key_seed:
                key_seed = "movement_phase_normal_move_bonus"
            key = f"movement_phase_normal_move_bonus:{key_seed}"
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "key": key,
                    "move_bonus_dice": move_bonus_dice,
                    "move_bonus_flat": int(move_bonus_flat),
                    "attacks_bonus": int(attacks_bonus),
                    "weapon_name": weapon_name,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_movement_phase_normal_move_speed_mortal_wounds_specs(self) -> List[dict]:
        """
        Unit-specific rule: optional pre-Normal move speed set with end-of-phase mortal wounds.

        Returns a list of specs with keys:
            - source: ability name
            - move_value: int (movement set value)
        """
        cache_key = "unit_movement_phase_normal_move_speed_mortal_wounds_specs"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._MOVEMENT_PHASE_NORMAL_MOVE_SPEED_MORTAL_WOUNDS_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                move_value = int(m.group("move") or 0)
            except Exception:
                move_value = 0
            if move_value <= 0:
                continue
            source = str(name or "Movement phase speed boost").strip() or "Movement phase speed boost"
            key = self._normalize_keyword_phrase(source) or source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "move_value": int(move_value),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_movement_phase_advance_redeploy_specs(self) -> List[dict]:
        """
        Unit-specific rule: when selected to Advance, optionally set the unit up again >X" from enemies.

        Returns a list of specs with keys:
            - source: ability name
            - min_enemy_distance_horiz: int
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_movement_phase_advance_redeploy_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for member in members:
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = member._strip_eligibility_prefix(text_src)
                normalized = member._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                match = member._MOVEMENT_PHASE_ADVANCE_REDEPLOY_RE.fullmatch(normalized)
                if not match:
                    continue
                try:
                    min_enemy = int(match.group("min_dist") or 0)
                except Exception:
                    min_enemy = 0
                if min_enemy <= 0:
                    continue
                source = str(name or "Advance redeploy").strip() or "Advance redeploy"
                key = (source.lower(), int(min_enemy))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "min_enemy_distance_horiz": int(min_enemy),
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_movement_phase_end_visible_wound_bonus_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Movement phase, select a visible enemy within range;
        friendly keyword models gain +wound vs that target until next Command phase.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (selection range)
            - keyword: str (friendly keyword)
            - bonus: int (wound roll bonus)
        """
        if model is None:
            return []
        cache_key = f"model_movement_phase_end_visible_wound_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._MOVEMENT_PHASE_END_VISIBLE_WOUND_BONUS_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            keyword = str(m.group("keyword") or "").strip()
            if not keyword:
                continue
            try:
                bonus = int(m.group("bonus") or 0)
            except Exception:
                bonus = 0
            if bonus <= 0:
                continue
            source = str(name or "Movement phase wound bonus").strip() or "Movement phase wound bonus"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            limit_once = "each unit can only be selected for this ability once per turn" in normalized
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "keyword": keyword,
                    "bonus": int(bonus),
                    "limit_once_per_turn": bool(limit_once),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_movement_phase_end_visible_hit_bonus_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Movement phase, select a visible enemy within range;
        friendly keyword models gain +hit vs that target until next Command phase.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (selection range)
            - keyword: str (friendly keyword)
            - bonus: int (hit roll bonus)
        """
        if model is None:
            return []
        cache_key = f"model_movement_phase_end_visible_hit_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._MOVEMENT_PHASE_END_VISIBLE_HIT_BONUS_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            keyword = str(m.group("keyword") or "").strip()
            if not keyword:
                continue
            try:
                bonus = int(m.group("bonus") or 0)
            except Exception:
                bonus = 0
            if bonus <= 0:
                continue
            source = str(name or "Movement phase hit bonus").strip() or "Movement phase hit bonus"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            limit_once = "each unit can only be selected for this ability once per turn" in normalized
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "keyword": keyword,
                    "bonus": int(bonus),
                    "limit_once_per_turn": bool(limit_once),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_grenade_pack_flyover_specs(self) -> List[dict]:
        """
        Unit-specific rule: grenade pack flyover mortal wounds after setup or movement.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (selection range)
            - threshold: int (D6 threshold)
            - mortal_per_success: int
            - max_mortal: int (cap)
            - move_types: list[str]
        """
        cache_key = "unit_grenade_pack_flyover_specs"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._GRENADE_PACK_FLYOVER_RE.search(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            try:
                threshold = int(m.group("threshold") or 0)
            except Exception:
                threshold = 0
            if threshold <= 0:
                continue
            try:
                mortal_per = int(m.group("mw") or 1)
            except Exception:
                mortal_per = 1
            if mortal_per <= 0:
                continue
            try:
                cap = int(m.group("cap") or 0)
            except Exception:
                cap = 0
            source = str(name or "Grenade Pack Flyover").strip() or "Grenade Pack Flyover"
            models_raw = str(m.group("models") or "").strip()
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            spec = {
                "source": source,
                "range": int(range_value),
                "threshold": int(threshold),
                "mortal_per_success": int(mortal_per),
                "max_mortal": int(cap) if int(cap or 0) > 0 else 0,
                "move_types": ["move", "advance", "fall_back"],
                "once_per_turn": True,
                "trigger_on_setup": True,
                "dice_per_model": True,
            }
            if models_raw:
                spec["model_keyword"] = models_raw
            specs.append(spec)

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_melee_successful_hit_critical_vs_below_half_specs(self) -> List[dict]:
        """
        Unit-specific rule: melee attacks against Below Half-strength targets treat successful Hit rolls as Critical Hits.

        Returns a list of specs with keys:
            - source: ability name
        """
        cache_key = "unit_melee_successful_hit_critical_vs_below_half_specs"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if "each time a model in this unit makes a melee attack" not in normalized:
                continue
            if "target of that attack is below half strength" not in normalized:
                continue
            if "a successful hit roll scores a critical hit" not in normalized:
                continue

            source = str(name or "Melee critical vs Below Half-strength").strip() or "Melee critical vs Below Half-strength"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_end_of_fight_embark_specs(self) -> List[dict]:
        """
        Unit-specific rule: end of Fight phase, select a friendly Infantry unit within 6"
        to embark if the transport is empty.

        Returns a list of specs with keys:
            - source: ability name
            - keyword: str (faction keyword)
            - max_models: int
            - range: int
        """
        cache_key = "unit_end_of_fight_embark_specs"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._END_OF_FIGHT_EMBARK_RE.fullmatch(normalized)
            if not m:
                continue
            keyword = str(m.group("keyword") or "").strip()
            if not keyword:
                continue
            max_models = 0
            try:
                max_raw = str(m.group("max") or "").strip()
                if max_raw:
                    max_models = int(max_raw)
            except Exception:
                max_models = 0
            if max_models < 0:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            source = str(name or "End of fight embark").strip() or "End of fight embark"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "keyword": keyword,
                    "max_models": int(max_models),
                    "range": int(range_value),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_end_of_fight_sweeping_advance_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: once per battle, end of Fight phase, after the unit has fought,
        make a Fall Back move if engaged, otherwise a Normal move.

        Returns list of specs with keys:
            - source: ability name
            - key: once-per-battle tracking key
        """
        if model is None:
            return []
        cache_key = f"model_end_of_fight_sweeping_advance_specs:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._SWEEPING_ADVANCE_RE.fullmatch(normalized):
                continue
            source = str(name or "Sweeping Advance").strip() or "Sweeping Advance"
            key_seed = self._normalize_keyword_phrase(source) or "sweeping_advance"
            key = f"sweeping_advance:{key_seed}"
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "key": key,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_end_of_fight_raid_and_run_specs(self) -> List[dict]:
        """
        End-of-Fight-phase reactive move rules.

        Returns list of specs with keys:
            - source: ability name
            - move_expr: movement roll expression string
            - requires_eligible_to_fight: bool
            - engaged_only: bool
            - engaged_movement_type: str
            - non_engaged_movement_type: str
        """
        cache_key = "unit_end_of_fight_raid_and_run_specs"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            source = str(name or "Raid and Run").strip() or "Raid and Run"
            if self._RAID_AND_RUN_RE.fullmatch(normalized):
                key = f"{source.lower()}:d3+3:raid_and_run"
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "move_expr": "D3+3",
                        "requires_eligible_to_fight": True,
                        "engaged_only": False,
                        "engaged_movement_type": "fall_back",
                        "non_engaged_movement_type": "move",
                    }
                )
                continue

            engaged_fall_back = self._END_OF_FIGHT_ENGAGED_FALL_BACK_MOVE_RE.search(normalized)
            if not engaged_fall_back:
                continue
            move_expr = str(engaged_fall_back.group("move") or "").strip().upper().replace(" ", "+")
            if not move_expr:
                continue
            key = f"{source.lower()}:{move_expr}:engaged_fall_back"
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "move_expr": move_expr,
                    "requires_eligible_to_fight": False,
                    "engaged_only": True,
                    "engaged_movement_type": "fall_back",
                    "non_engaged_movement_type": "",
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_of_battle_keyword_reroll_ones_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: at the start of the battle, select a keyword; re-roll Hit/Wound rolls of 1
        vs targets with the selected keyword.

        Returns a list of specs with keys:
            - source: ability name
            - ability_key: normalized key for storing selections
            - keywords: list[str] of selectable keywords (uppercased)
        """
        if model is None:
            return []
        cache_key = f"model_start_of_battle_keyword_reroll_ones:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()
        allowed = {"infantry", "monster", "mounted", "vehicle"}

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._START_OF_BATTLE_KEYWORD_REROLL_ONES_RE.fullmatch(normalized)
            if not m:
                continue
            raw = str(m.group("keywords") or "").strip()
            if not raw:
                continue
            keywords: list[str] = []
            for token in raw.split():
                if token in allowed and token not in keywords:
                    keywords.append(token)
            if not keywords:
                continue
            source = str(name or "Start of battle keyword selection").strip() or "Start of battle keyword selection"
            key = self._normalize_keyword_phrase(source) or source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "ability_key": key,
                    "keywords": [kw.upper() for kw in keywords],
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_movement_phase_end_misfortune_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Movement phase, select a visible enemy within range; that unit suffers -1 to wound rolls.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (selection range)
            - penalty: int (wound roll penalty)
        """
        if model is None:
            return []
        cache_key = f"model_movement_phase_end_misfortune:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._MOVEMENT_PHASE_END_MISFORTUNE_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            try:
                penalty = int(m.group("pen") or 0)
            except Exception:
                penalty = 0
            if penalty <= 0:
                continue
            source = str(name or "Misfortune").strip() or "Misfortune"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            limit_once = "each unit can only be selected for this ability once per turn" in normalized
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "penalty": -int(penalty),
                    "limit_once_per_turn": bool(limit_once),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_movement_phase_pinned_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: in Movement phase, select one visible enemy within range; that unit is pinned
        until the start of your next Movement phase.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
            - move_penalty: int (negative)
            - charge_penalty: int (negative)
            - expires_phase: str
        """
        if model is None:
            return []
        cache_key = f"model_movement_phase_pinned:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._MOVEMENT_PHASE_PINNED_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            try:
                move_penalty = -int(m.group("move") or 0)
            except Exception:
                move_penalty = -2
            try:
                charge_penalty = -int(m.group("charge") or 0)
            except Exception:
                charge_penalty = -2
            if move_penalty >= 0 and charge_penalty >= 0:
                continue

            source = str(name or "Pinned").strip() or "Pinned"
            key = (source.lower(), int(range_value), int(move_penalty), int(charge_penalty))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "move_penalty": int(move_penalty),
                    "charge_penalty": int(charge_penalty),
                    "expires_phase": "MOVEMENT_PHASE",
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_movement_phase_end_toughness_penalty_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Movement phase, select an enemy within range; that unit suffers -1 Toughness
        until the start of your next Movement phase.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (selection range)
            - penalty: int (toughness penalty, negative)
        """
        if model is None:
            return []
        cache_key = f"model_movement_phase_end_toughness_penalty:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._MOVEMENT_PHASE_END_TOUGHNESS_PENALTY_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            raw_pen = m.group("pen") or m.group("pen_alt") or ""
            try:
                penalty = int(raw_pen or 0)
            except Exception:
                penalty = 0
            if penalty <= 0:
                continue
            source = str(name or "Nurgle's Rot").strip() or "Nurgle's Rot"
            key = (source.lower(), int(range_value))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "penalty": -int(penalty),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_movement_phase_end_shadow_of_chaos_terrain_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Movement phase, if within Area Terrain, that terrain counts as Shadow of Chaos.
        """
        if model is None:
            return []
        cache_key = f"model_movement_phase_end_shadow_of_chaos_terrain:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._MOVEMENT_PHASE_END_SHADOW_OF_CHAOS_TERRAIN_RE.fullmatch(normalized):
                continue
            source = str(name or "Seed the Garden of Nurgle").strip() or "Seed the Garden of Nurgle"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_movement_phase_end_battleshock_reroll_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Movement phase, select a Battle-shocked enemy within range;
        friendly keyword models can re-roll Hit and Wound rolls vs that target until end of turn.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (selection range)
            - keywords: list[str] (required attacker keywords)
        """
        if model is None:
            return []
        cache_key = f"model_movement_phase_end_battleshock_reroll:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._MOVEMENT_PHASE_END_BATTLESHOCK_REROLL_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            source = str(name or "Symphony of Pain").strip() or "Symphony of Pain"
            key = (source.lower(), int(range_value))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "keywords": ["SLAANESH", "LEGIONES DAEMONICA"],
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_shooting_phase_visible_battleshock_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: start of Shooting phase, select a visible enemy within range; that unit takes Battle-shock.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (selection range)
            - use_leadership_test: bool
            - leadership_test_modifier_if_infantry: int
            - fail_mortal_wounds: int
            - leadership_test_counts_as_battle_shock: bool
        """
        if model is None:
            return []
        cache_key = f"model_start_shooting_phase_visible_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int, int, bool, tuple[str, ...]]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._START_SHOOTING_PHASE_VISIBLE_BATTLESHOCK_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except (TypeError, ValueError):
                range_value = 0
            if range_value <= 0:
                continue
            try:
                infantry_penalty = int(m.group("infantry_penalty") or 0)
            except (TypeError, ValueError):
                infantry_penalty = 0
            if infantry_penalty > 0:
                infantry_penalty = -int(infantry_penalty)
            fail_mw_token = str(m.group("fail_mw") or "").strip().lower()
            fail_mortal_wounds = 0
            if fail_mw_token.isdigit():
                try:
                    fail_mortal_wounds = int(fail_mw_token or 0)
                except (TypeError, ValueError):
                    fail_mortal_wounds = 0
            use_leadership_test = bool(infantry_penalty != 0 or fail_mortal_wounds > 0)
            source = str(name or "Start of Shooting phase Battle-shock").strip() or "Start of Shooting phase Battle-shock"
            key = (
                source.lower(),
                int(range_value),
                int(infantry_penalty),
                int(fail_mortal_wounds),
                bool(use_leadership_test),
            )
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "use_leadership_test": bool(use_leadership_test),
                    "leadership_test_modifier_if_infantry": int(infantry_penalty),
                    "fail_mortal_wounds": int(fail_mortal_wounds),
                    "leadership_test_counts_as_battle_shock": bool(use_leadership_test),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_shooting_phase_visible_hit_bonus_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: start of Shooting phase, select a visible enemy; this unit gets +Hit vs that enemy.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (selection range; large sentinel for "visible" with no explicit range)
            - bonus: int
        """
        if model is None:
            return []
        cache_key = f"model_start_shooting_phase_visible_hit_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._START_SHOOTING_PHASE_VISIBLE_HIT_BONUS_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                bonus = int(m.group("val") or 0)
            except Exception:
                bonus = 0
            if bonus <= 0:
                continue
            source = str(name or "Marked by Fate").strip() or "Marked by Fate"
            range_value = 9999
            key = (source.lower(), int(range_value), int(bonus))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "bonus": int(bonus),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_shooting_phase_blight_bombardment_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: start of Shooting phase, select one visible enemy unit in range;
        friendly DEATH GUARD ranged attacks gain hit re-roll support against that unit this phase.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
        """
        if model is None:
            return []
        cache_key = f"model_start_shooting_phase_blight_bombardment:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._START_SHOOTING_PHASE_BLIGHT_BOMBARDMENT_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            source = str(name or "Blight Bombardment").strip() or "Blight Bombardment"
            key = (source.lower(), int(range_value))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_shooting_phase_eater_plague_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: in Shooting phase, optionally select a visible enemy and roll for mortal wounds.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
            - lone_operative_range: int
            - optional: bool
        """
        if model is None:
            return []
        cache_key = f"model_start_shooting_phase_eater_plague:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int, str, int, int, str]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            source = str(name or "Eater Plague").strip() or "Eater Plague"

            m = self._SHOOTING_PHASE_EATER_PLAGUE_RE.fullmatch(normalized)
            if m:
                try:
                    range_value = int(m.group("range") or 0)
                except Exception:
                    range_value = 0
                if range_value <= 0:
                    continue
                try:
                    lone_range = int(m.group("lone_range") or 0)
                except Exception:
                    lone_range = 0
                if lone_range <= 0:
                    lone_range = 12
                key = (source.lower(), int(range_value), int(lone_range), "table", 0, 0, "")
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "range": int(range_value),
                        "lone_operative_range": int(lone_range),
                        "optional": True,
                        "roll_mode": "table_d6_self_1_target_2_5_6",
                        "self_mortal_on_one": "d3",
                        "target_mortal_on_mid": "d6",
                        "target_mortal_on_six": "d3+3",
                        "count_as_curse_of_walking_pox": True,
                    }
                )
                continue

            m = self._SHOOTING_PHASE_DICE_POOL_MORTAL_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            try:
                lone_range = int(m.group("lone_range") or 0)
            except Exception:
                lone_range = 0
            if lone_range <= 0:
                lone_range = 12
            dice_token = str(m.group("dice") or "").strip().lower()
            if dice_token.isdigit():
                dice_count = int(dice_token)
            else:
                dice_count = int(self._NUMBER_WORDS.get(dice_token, 0) or 0)
            try:
                threshold = int(m.group("threshold") or 0)
            except Exception:
                threshold = 0
            mw_token = str(m.group("mw") or "").strip().lower()
            if dice_count <= 0 or threshold <= 0 or not mw_token:
                continue
            key = (source.lower(), int(range_value), int(lone_range), "dice_pool", int(dice_count), int(threshold), mw_token)
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "lone_operative_range": int(lone_range),
                    "optional": True,
                    "roll_mode": "dice_pool_threshold",
                    "dice_count": int(dice_count),
                    "threshold": int(threshold),
                    "mortal_per_success": mw_token,
                    "count_as_curse_of_walking_pox": False,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_shooting_phase_death_hex_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: start of Shooting phase, select a visible enemy within range; roll D6 for Death Hex.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (selection range)
            - ap_bonus: int (AP improvement on 2+)
            - optional: bool
            - limit_one_per_army: bool
        """
        if model is None:
            return []
        cache_key = f"model_start_shooting_phase_death_hex:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._START_SHOOTING_PHASE_DEATH_HEX_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            try:
                ap_bonus = int(m.group("ap") or 0)
            except Exception:
                ap_bonus = 0
            if ap_bonus <= 0:
                ap_bonus = 1
            source = str(name or "Death Hex").strip() or "Death Hex"
            key = (source.lower(), int(range_value), int(ap_bonus))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "ap_bonus": int(ap_bonus),
                    "optional": True,
                    "limit_one_per_army": True,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_shoot_disembark_ap_bonus_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has shot, select a hit enemy unit; disembarked models improve AP.

        Returns a list of specs with keys:
            - source: ability name
            - value: int
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_disembark_ap_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_DISEMBARK_AP_BONUS_RE.fullmatch(normalized)
            if not m:
                continue
            source = str(name or "Disembark AP bonus").strip() or "Disembark AP bonus"
            try:
                val = int(m.group("val") or 0)
            except Exception:
                val = 0
            if val <= 0:
                continue
            key = (source.lower(), int(val))
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "value": int(val)})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_shoot_disembark_psychic_hit_wound_bonus_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has shot, select a hit enemy unit; disembarked models gain +Hit/+Wound
        for Psychic attacks against that target.

        Returns a list of specs with keys:
            - source: ability name
            - hit_bonus: int
            - wound_bonus: int
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_disembark_psychic_hit_wound_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_DISEMBARK_PSYCHIC_HIT_WOUND_BONUS_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                hit_bonus = int(m.group("hit") or 0)
            except Exception:
                hit_bonus = 0
            try:
                wound_bonus = int(m.group("wound") or 0)
            except Exception:
                wound_bonus = 0
            if hit_bonus <= 0 and wound_bonus <= 0:
                continue
            source = str(name or "Sorcerous Support").strip() or "Sorcerous Support"
            key = (source.lower(), int(hit_bonus), int(wound_bonus))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "hit_bonus": int(hit_bonus),
                    "wound_bonus": int(wound_bonus),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_ensorcelled_annihilation_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: ranged attacks can re-roll Hit and Damage vs MONSTER/VEHICLE targets
        marked by Thousand Sons Psychic hits this phase.

        Returns a list of specs with keys:
            - source: ability name
            - reroll_hit: bool
            - reroll_damage: bool
        """
        if model is None:
            return []
        cache_key = f"model_ensorcelled_annihilation:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._RANGED_ATTACK_PSYCHIC_HIT_MONSTER_VEHICLE_HIT_DAMAGE_REROLL_RE.fullmatch(normalized):
                continue
            source = str(name or "Ensorcelled Annihilation").strip() or "Ensorcelled Annihilation"
            source_key = source.lower()
            if source_key in seen:
                continue
            seen.add(source_key)
            specs.append({"source": source, "reroll_hit": True, "reroll_damage": True})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_ensorcelled_destruction_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: ranged attacks gain +Strength and +AP vs non-MONSTER/VEHICLE targets
        marked by Thousand Sons Psychic hits this phase.

        Returns a list of specs with keys:
            - source: ability name
            - strength_bonus: int
            - ap_bonus: int
        """
        if model is None:
            return []
        cache_key = f"model_ensorcelled_destruction:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int]] = set()
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._RANGED_ATTACK_PSYCHIC_HIT_NONMONSTER_NONVEHICLE_STRENGTH_AP_BONUS_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                val = int(m.group("val") or 0)
            except Exception:
                val = 0
            if val <= 0:
                continue
            source = str(name or "Ensorcelled Destruction").strip() or "Ensorcelled Destruction"
            key = (source.lower(), int(val), int(val))
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "strength_bonus": int(val), "ap_bonus": int(val)})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_move_over_no_cover_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after ending a Normal move over an enemy unit, select one such enemy unit;
        target cannot gain Benefit of Cover until end of turn.

        Returns a list of specs with keys:
            - source: ability name
            - move_types: list[str]
        """
        if model is None:
            return []
        cache_key = f"model_move_over_no_cover:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._MOVE_OVER_NO_COVER_RE.fullmatch(normalized):
                continue
            source = str(name or "Flame-wreathed").strip() or "Flame-wreathed"
            source_key = source.lower()
            if source_key in seen:
                continue
            seen.add(source_key)
            specs.append({"source": source, "move_types": ["move"]})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_post_shoot_pinned_specs(self) -> List[dict]:
        """
        Unit-specific rule: after this unit has shot, select a hit enemy unit; target is pinned.

        Returns a list of specs with keys:
            - source: ability name
            - move_penalty: int
            - charge_penalty: int
            - exclude_monster_vehicle: bool
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_shoot_pinned_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, int, int, bool]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._POST_SHOOT_PINNED_UNIT_RE.fullmatch(normalized)
                if not m:
                    continue
                source = str(name or "Pinned").strip() or "Pinned"
                try:
                    move_penalty = -int(m.group("move") or 0)
                except Exception:
                    move_penalty = -2
                try:
                    charge_penalty = -int(m.group("charge") or 0)
                except Exception:
                    charge_penalty = -2
                exclude_mv = bool(m.group("exclude")) or ("excluding monsters and vehicles" in normalized)
                key = (source.lower(), int(move_penalty), int(charge_penalty), bool(exclude_mv))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "move_penalty": int(move_penalty),
                        "charge_penalty": int(charge_penalty),
                        "exclude_monster_vehicle": bool(exclude_mv),
                    }
                )

        # Temporary unit-scoped pinned spec injection used by Saga of the Beastslayer -> Pinning Fire.
        root_sr = getattr(root, "special_rules", None)
        if isinstance(root_sr, dict) and bool(root_sr.get("space_marines_pinning_fire_active", False)):
            effect_active = True
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if game is not None:
                owner_id = str(root_sr.get("space_marines_pinning_fire_turn_owner", "") or "")
                current_player = getattr(game, "get_current_player", lambda: None)()
                current_owner = str(getattr(current_player, "id", "") or "")
                if owner_id and current_owner and owner_id != current_owner:
                    effect_active = False
                if effect_active:
                    try:
                        effect_turn = int(root_sr.get("space_marines_pinning_fire_turn", 0) or 0)
                    except Exception:
                        effect_turn = 0
                    try:
                        current_turn = int(getattr(game, "turn", 0) or 0)
                    except Exception:
                        current_turn = 0
                    if effect_turn and current_turn and effect_turn != current_turn:
                        effect_active = False
            if effect_active:
                source = str(root_sr.get("space_marines_pinning_fire_source", "") or "PINNING FIRE").strip() or "PINNING FIRE"
                try:
                    move_penalty = int(root_sr.get("space_marines_pinning_fire_move_penalty", -2) or -2)
                except Exception:
                    move_penalty = -2
                try:
                    charge_penalty = int(root_sr.get("space_marines_pinning_fire_charge_penalty", -2) or -2)
                except Exception:
                    charge_penalty = -2
                include_keywords_any = [
                    str(kw or "").strip().upper()
                    for kw in list(root_sr.get("space_marines_pinning_fire_target_keywords_any", []) or [])
                    if str(kw or "").strip()
                ]
                expires_phase = str(root_sr.get("space_marines_pinning_fire_pinned_expires_phase", "") or "SHOOTING_PHASE").strip().upper() or "SHOOTING_PHASE"
                key = (
                    source.lower(),
                    int(move_penalty),
                    int(charge_penalty),
                    False,
                    tuple(include_keywords_any),
                    expires_phase,
                )
                if key not in seen:
                    seen.add(key)
                    specs.append(
                        {
                            "source": source,
                            "move_penalty": int(move_penalty),
                            "charge_penalty": int(charge_penalty),
                            "exclude_monster_vehicle": False,
                            "include_keywords_any": list(include_keywords_any),
                            "expires_phase": expires_phase,
                        }
                    )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_post_shoot_shocked_specs(self) -> List[dict]:
        """
        Unit-specific rule: after this unit has shot, select a hit enemy non-MONSTER/non-VEHICLE
        unit; target is shocked until end of opponent's next turn.

        Returns a list of specs with keys:
            - source: ability name
            - move_penalty: int
            - advance_penalty: int
            - charge_penalty: int
            - exclude_monster_vehicle: bool
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_shoot_shocked_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, int, int, int, bool]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._POST_SHOOT_SHOCKED_RE.fullmatch(normalized)
                if not m:
                    continue
                source = str(name or "Shocked").strip() or "Shocked"
                try:
                    move_penalty = -int(m.group("move") or 0)
                except Exception:
                    move_penalty = -2
                try:
                    advance_penalty = -int(m.group("advance") or 0)
                except Exception:
                    advance_penalty = -2
                charge_penalty = int(advance_penalty)
                exclude_mv = bool(m.group("exclude")) or ("excluding monsters and vehicles" in normalized)
                include_keywords_any: list[str] = []
                if str(m.group("infantry") or "").strip():
                    include_keywords_any = ["INFANTRY"]
                key = (
                    source.lower(),
                    int(move_penalty),
                    int(advance_penalty),
                    int(charge_penalty),
                    bool(exclude_mv),
                    tuple(include_keywords_any),
                )
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "move_penalty": int(move_penalty),
                        "advance_penalty": int(advance_penalty),
                        "charge_penalty": int(charge_penalty),
                        "exclude_monster_vehicle": bool(exclude_mv),
                        "include_keywords_any": list(include_keywords_any),
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_post_shoot_no_overwatch_specs(self) -> List[dict]:
        """
        Unit-specific rule: after this unit has shot, select a hit enemy unit that cannot be targeted with Fire Overwatch.

        Returns a list of specs with keys:
            - source: ability name
            - weapon_key: Optional[str] (normalized)
            - weapon_name: str (display)
            - exclude_monster_vehicle: bool
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_shoot_no_overwatch_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, str, bool]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._POST_SHOOT_NO_OVERWATCH_WEAPON_RE.fullmatch(normalized)
                if not m:
                    continue
                weapon_raw = str(m.group("weapon") or "").strip()
                if not weapon_raw:
                    continue
                weapon_key = unit._normalize_keyword_phrase(weapon_raw) or weapon_raw.lower()
                exclude_mv = "excluding monsters and vehicles" in normalized
                source = str(name or "Post-shoot no Overwatch").strip() or "Post-shoot no Overwatch"
                key = (source.lower(), weapon_key, bool(exclude_mv))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "weapon_key": weapon_key,
                        "weapon_name": weapon_raw,
                        "exclude_monster_vehicle": bool(exclude_mv),
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_post_shoot_keyword_hit_bonus_specs(self) -> List[dict]:
        """
        Unit-specific rule: after this unit has shot, select a hit enemy unit; friendly keyword models gain +Hit vs that unit.

        Returns a list of specs with keys:
            - source: ability name
            - keyword: str
            - bonus: int
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_post_shoot_keyword_hit_bonus_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, str, int]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._POST_SHOOT_KEYWORD_HIT_BONUS_RE.fullmatch(normalized)
                if not m:
                    continue
                keyword_raw = str(m.group("keyword") or "").strip()
                keyword_raw = re.sub(r"^(?:a|an)\s+", "", keyword_raw)
                keyword = unit._normalize_keyword_phrase(keyword_raw) if keyword_raw else ""
                if not keyword:
                    keyword = "friendly"
                try:
                    bonus = int(m.group("val") or 0)
                except Exception:
                    bonus = 0
                if bonus <= 0:
                    continue
                source = str(name or "Post-shoot Hit bonus").strip() or "Post-shoot Hit bonus"
                key = (source.lower(), keyword, int(bonus))
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"source": source, "keyword": keyword, "bonus": int(bonus)})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_movement_phase_end_vehicle_battleshock_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Movement phase, optionally select an enemy unit (optionally keyword-limited) within range;
        that unit takes a Battle-shock test.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
            - optional: bool
            - target_keyword_phrase: str (optional)
            - ability_key: str
        """
        if model is None:
            return []
        cache_key = f"model_movement_phase_end_vehicle_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, bool, str]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if "end of your movement phase" not in normalized:
                continue
            if "must take a battle shock test" not in normalized:
                continue
            m = re.search(
                r"select one enemy (?:(?P<keyword>[a-z0-9 ]+?) )?unit within (?P<range>\d+) of (?P<source>this model|this unit)",
                normalized,
            )
            if m is None:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            keyword_raw = str(m.group("keyword") or "").strip()
            target_keyword_phrase = self._normalize_keyword_phrase(keyword_raw) if keyword_raw else ""
            optional = "you can select one enemy vehicle unit" in normalized
            if not optional:
                optional = "you can select one enemy unit" in normalized
            source = str(name or "Enrage Machine Spirits").strip() or "Enrage Machine Spirits"
            ability_key_seed = self._normalize_keyword_phrase(source) or "movement_phase_end_vehicle_battleshock"
            ability_key = f"movement_phase_end_vehicle_battleshock:{ability_key_seed}"
            key = (source.lower(), int(range_value), bool(optional), str(target_keyword_phrase))
            if key in seen:
                continue
            seen.add(key)
            spec = {
                "source": source,
                "range": int(range_value),
                "optional": bool(optional),
                "ability_key": ability_key,
            }
            if target_keyword_phrase:
                spec["target_keyword_phrase"] = str(target_keyword_phrase)
            specs.append(spec)

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_shooting_phase_spirit_thief_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: start of Shooting phase, select a visible enemy VEHICLE to mark
        for friendly HERETIC ASTARTES wound reroll 1s until end of phase.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (0 means no explicit range cap; visibility still required)
            - keyword: str
        """
        if model is None:
            return []
        cache_key = f"model_start_shooting_phase_spirit_thief:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._START_SHOOTING_PHASE_SPIRIT_THIEF_RE.fullmatch(normalized):
                continue
            source = str(name or "Spirit Thief").strip() or "Spirit Thief"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": 0,
                    "keyword": "heretic astartes",
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_shooting_phase_corrupt_machine_spirits_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: start of Shooting phase, select a visible enemy VEHICLE within range
        and roll a mortal-wound table.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
        """
        if model is None:
            return []
        cache_key = f"model_start_shooting_phase_corrupt_machine_spirits:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, str, int, str, bool]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            source = str(name or "Corrupt Machine Spirits").strip() or "Corrupt Machine Spirits"

            m = self._START_SHOOTING_PHASE_CORRUPT_MACHINE_SPIRITS_RE.fullmatch(normalized)
            if m:
                try:
                    range_value = int(m.group("range") or 0)
                except Exception:
                    range_value = 0
                if range_value <= 0:
                    continue
                key = (source.lower(), int(range_value), "table", 0, "", False)
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "range": int(range_value),
                        "roll_mode": "table_2_3_d3_4_5_3_6_d3plus3",
                    }
                )
                continue

            m = self._START_SHOOTING_PHASE_VEHICLE_MORTAL_HEAL_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            try:
                threshold = int(m.group("threshold") or 0)
            except Exception:
                threshold = 0
            mw_token = str(m.group("mw") or "").strip().lower()
            if threshold <= 0 or not mw_token:
                continue
            key = (source.lower(), int(range_value), "single_threshold", int(threshold), mw_token, True)
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "roll_mode": "single_threshold",
                    "threshold": int(threshold),
                    "mortal_on_success": mw_token,
                    "heal_self_on_success": True,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_opponent_shooting_phase_disrupt_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: start of opponent's Shooting phase, select a visible enemy; roll D6 for hit penalty or no-shoot.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (selection range)
            - mortal_on_one: bool
            - optional: bool
            - limit_one_per_army: bool
            - grant_ranged_hazardous: bool
            - resolution_mode: str
            - required_target_keywords: list[str]
            - excluded_target_keywords: list[str]
        """
        if model is None:
            return []
        cache_key = f"model_start_opponent_shooting_phase_disrupt:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._START_OPP_SHOOTING_PHASE_MISCHIEF_CONFUSION_RE.fullmatch(normalized)
            mortal_on_one = False
            optional = False
            limit_one = False
            grant_ranged_hazardous = False
            if not m:
                m = self._START_OPP_SHOOTING_PHASE_HORRIBLE_FASCINATION_RE.fullmatch(normalized)
                if m:
                    mortal_on_one = True
                    optional = True
                    limit_one = True
                else:
                    m = self._START_OPP_SHOOTING_PHASE_TREASON_HAZARDOUS_RE.fullmatch(normalized)
                    if not m:
                        continue
                    grant_ranged_hazardous = True
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            source = str(name or "Opponent Shooting phase disruption").strip() or "Opponent Shooting phase disruption"
            key = (
                source.lower(),
                int(range_value),
                bool(mortal_on_one),
                bool(grant_ranged_hazardous),
                bool(optional),
                bool(limit_one),
                "d6_table",
                tuple(),
                tuple(),
            )
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "mortal_on_one": bool(mortal_on_one),
                    "optional": bool(optional),
                    "limit_one_per_army": bool(limit_one),
                    "grant_ranged_hazardous": bool(grant_ranged_hazardous),
                }
            )

        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("enhancement_osseus_key")):
            try:
                model_id = str(get_entity_id(model) or "")
            except Exception:
                model_id = ""
            bearer_model_id = str(
                sr.get("enhancement_osseus_key_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            if not bearer_model_id or not model_id or model_id == bearer_model_id:
                source = str(sr.get("enhancement_osseus_key_source", "") or "Osseus Key").strip() or "Osseus Key"
                try:
                    range_value = int(float(sr.get("enhancement_osseus_key_range", 12.0) or 12.0))
                except Exception:
                    range_value = 12
                resolution_mode = str(
                    sr.get("enhancement_osseus_key_resolution_mode", "") or "leadership_test"
                ).strip().lower() or "leadership_test"
                required_keywords: list[str] = []
                for keyword in list(sr.get("enhancement_osseus_key_required_target_keywords", ()) or ()):
                    kw = str(keyword or "").strip().upper()
                    if kw and kw not in required_keywords:
                        required_keywords.append(kw)
                excluded_keywords: list[str] = []
                for keyword in list(sr.get("enhancement_osseus_key_excluded_target_keywords", ()) or ()):
                    kw = str(keyword or "").strip().upper()
                    if kw and kw not in excluded_keywords:
                        excluded_keywords.append(kw)
                key = (
                    source.lower(),
                    int(range_value),
                    False,
                    False,
                    False,
                    True,
                    resolution_mode,
                    tuple(required_keywords),
                    tuple(excluded_keywords),
                )
                if range_value > 0 and key not in seen:
                    seen.add(key)
                    specs.append(
                        {
                            "source": source,
                            "range": int(range_value),
                            "mortal_on_one": False,
                            "optional": False,
                            "limit_one_per_army": True,
                            "grant_ranged_hazardous": False,
                            "resolution_mode": resolution_mode,
                            "required_target_keywords": list(required_keywords),
                            "excluded_target_keywords": list(excluded_keywords),
                        }
                    )

        if isinstance(sr, dict) and bool(sr.get("enhancement_lord_of_machines")):
            try:
                model_id = str(get_entity_id(model) or "")
            except Exception:
                model_id = ""
            bearer_model_id = str(
                sr.get("enhancement_lord_of_machines_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            if not bearer_model_id or not model_id or model_id == bearer_model_id:
                source = str(sr.get("enhancement_lord_of_machines_source", "") or "Lord of Machines").strip() or "Lord of Machines"
                try:
                    range_value = int(float(sr.get("enhancement_lord_of_machines_range", 12.0) or 12.0))
                except Exception:
                    range_value = 12
                resolution_mode = str(
                    sr.get("enhancement_lord_of_machines_resolution_mode", "") or "leadership_test"
                ).strip().lower() or "leadership_test"
                required_keywords: list[str] = []
                for keyword in list(sr.get("enhancement_lord_of_machines_required_target_keywords", ("VEHICLE",)) or ("VEHICLE",)):
                    kw = str(keyword or "").strip().upper()
                    if kw and kw not in required_keywords:
                        required_keywords.append(kw)
                excluded_keywords: list[str] = []
                for keyword in list(sr.get("enhancement_lord_of_machines_excluded_target_keywords", ()) or ()):
                    kw = str(keyword or "").strip().upper()
                    if kw and kw not in excluded_keywords:
                        excluded_keywords.append(kw)
                key = (
                    source.lower(),
                    int(range_value),
                    False,
                    False,
                    True,
                    False,
                    resolution_mode,
                    tuple(required_keywords),
                    tuple(excluded_keywords),
                )
                if range_value > 0 and key not in seen:
                    seen.add(key)
                    specs.append(
                        {
                            "source": source,
                            "range": int(range_value),
                            "mortal_on_one": False,
                            "optional": True,
                            "limit_one_per_army": False,
                            "grant_ranged_hazardous": False,
                            "resolution_mode": resolution_mode,
                            "required_target_keywords": list(required_keywords),
                            "excluded_target_keywords": list(excluded_keywords),
                        }
                    )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_opponent_movement_phase_gravitic_pulse_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: start of opponent's Movement phase, select one visible enemy within range.
        Selected unit has Move halved and Advance/Charge rolls halved until end of turn; if it can FLY,
        it suffers D3 mortal wounds on 4+ each time it ends any type of move until the start of your next Movement phase.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (selection range)
            - optional: bool
            - requires_visibility: bool
            - half_move_characteristic: bool
            - half_advance_roll: bool
            - half_charge_roll: bool
            - fly_mortal_threshold: int
            - fly_mortal_wounds: str
            - fly_mortal_expires_phase: str
        """
        if model is None:
            return []
        cache_key = f"model_start_opponent_movement_phase_gravitic_pulse:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()

            if "at the start of your opponent s movement phase" not in normalized:
                continue
            if "select one enemy unit within" not in normalized or "visible to this model" not in normalized:
                continue
            if "until the end of the turn halve the move characteristic of models in that unit" not in normalized:
                continue
            if "halve advance and charge rolls made for that unit" not in normalized:
                continue
            if "if that unit can fly" not in normalized:
                continue
            if "until the start of your next movement phase" not in normalized:
                continue
            if "roll one d6 each time that unit ends any type of move" not in normalized:
                continue
            if (
                "on a 4 that unit suffers d3 mortal wounds" not in normalized
                and "on a 4 that unit suffers d3 mortal wound" not in normalized
            ):
                continue

            m = re.search(r"select one enemy unit within (?P<range>\d+)", normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except (TypeError, ValueError):
                range_value = 0
            if range_value <= 0:
                continue

            source = str(name or "Gravitic Pulse").strip() or "Gravitic Pulse"
            key = (source.lower(), int(range_value))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "optional": True,
                    "requires_visibility": True,
                    "half_move_characteristic": True,
                    "half_advance_roll": True,
                    "half_charge_roll": True,
                    "fly_mortal_threshold": 4,
                    "fly_mortal_wounds": "D3",
                    "fly_mortal_expires_phase": "MOVEMENT_PHASE",
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_start_opponent_shooting_phase_grant_stealth_specs(self) -> List[dict]:
        """
        Unit-specific rule: start of opponent's Shooting phase, optionally select a visible friendly keyworded unit
        within range; that unit gains Stealth until end of phase.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
            - keyword_phrase: str
            - optional: bool
            - ability_key: str
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_start_opponent_shooting_phase_grant_stealth_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, int, str]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = unit._strip_eligibility_prefix(text_src)
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._START_OPP_SHOOTING_PHASE_FRIENDLY_VISIBLE_STEALTH_RE.fullmatch(normalized)
                if not m:
                    continue
                try:
                    range_value = int(m.group("range") or 0)
                except Exception:
                    range_value = 0
                if range_value <= 0:
                    continue
                keyword_phrase = str(m.group("keyword") or "").strip()
                if not keyword_phrase:
                    continue
                source = str(name or "Opponent Shooting phase Stealth").strip() or "Opponent Shooting phase Stealth"
                ability_seed = unit._normalize_keyword_phrase(source) or "opponent_shooting_phase_grant_stealth"
                ability_key = f"opponent_shooting_phase_grant_stealth:{ability_seed}"
                key = (source.lower(), int(range_value), unit._normalize_keyword_phrase(keyword_phrase))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "range": int(range_value),
                        "keyword_phrase": keyword_phrase,
                        "optional": True,
                        "ability_key": ability_key,
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_movement_phase_end_enemy_within_range_mortal_table_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Movement phase, roll D6 for each enemy unit within range; apply mortal wound table.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (aura range)
            - battle_shock: bool (if units within range must take a Battle-shock test)
        """
        if model is None:
            return []
        cache_key = f"model_movement_phase_end_enemy_within_range_mortal_table:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, bool]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._MOVEMENT_PHASE_END_ENEMY_WITHIN_RANGE_MORTAL_TABLE_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            source = str(name or "Movement phase mortals").strip() or "Movement phase mortals"
            battle_shock = "battle shock test" in normalized
            key = (source.lower(), int(range_value), bool(battle_shock))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "battle_shock": bool(battle_shock),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_movement_phase_end_enemy_within_range_mortal_threshold_specs(self) -> List[dict]:
        """
        Unit-specific rule: end of Movement phase, roll D6 for each enemy unit within range of one or more models;
        on a threshold, apply mortal wounds.

        Returns a list of specs with keys:
            - source: ability name
            - range: int (aura range)
            - threshold: int (D6 threshold to apply mortals)
            - mortal_wounds: str | int (e.g., "d3", "d6", or flat number)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_movement_phase_end_enemy_within_range_mortal_threshold_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, int, int, str, int]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._MOVEMENT_PHASE_END_ENEMY_WITHIN_RANGE_MORTAL_THRESHOLD_RE.fullmatch(normalized)
                if not m:
                    continue
                try:
                    range_value = int(m.group("range") or 0)
                except Exception:
                    range_value = 0
                if range_value <= 0:
                    continue
                try:
                    threshold = int(m.group("threshold") or 0)
                except Exception:
                    threshold = 0
                if threshold <= 0:
                    continue
                mw_raw = str(m.group("mw") or "").strip().lower()
                if not mw_raw:
                    continue
                try:
                    afflicted_roll_bonus = int(
                        m.group("bonus_pre")
                        or m.group("bonus_mid")
                        or m.group("bonus_post")
                        or 0
                    )
                except Exception:
                    afflicted_roll_bonus = 0
                if afflicted_roll_bonus < 0:
                    afflicted_roll_bonus = 0
                mw_value: str | int
                if mw_raw in ("d3", "d6"):
                    mw_value = mw_raw
                else:
                    try:
                        mw_value = int(mw_raw)
                    except Exception:
                        continue
                    if int(mw_value) <= 0:
                        continue
                source = str(name or "Movement phase mortals").strip() or "Movement phase mortals"
                key = (
                    source.lower(),
                    int(range_value),
                    int(threshold),
                    str(mw_value),
                    int(afflicted_roll_bonus),
                )
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "range": int(range_value),
                        "threshold": int(threshold),
                        "mortal_wounds": mw_value,
                        "afflicted_roll_bonus": int(afflicted_roll_bonus),
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_start_fight_phase_engagement_battleshock_specs(self) -> List[dict]:
        """
        Unit-specific rule: at the start of the Fight phase, enemies in engagement range test Battle-shock.

        Returns a list of specs with keys:
            - source: ability name
            - penalty: int (optional, applied when enemy is Below Half-strength)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_fight_phase_engagement_battleshock_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[str] = set()

        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._FIGHT_PHASE_ENGAGEMENT_BATTLESHOCK_UNIT_RE.search(normalized)
                if not m:
                    continue
                penalty = 0
                try:
                    penalty = int(m.group("penalty") or 0)
                except Exception:
                    penalty = 0
                source = str(name or "Fight phase Battle-shock").strip() or "Fight phase Battle-shock"
                key = source.lower()
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"source": source, "penalty": penalty})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_enemy_failed_battleshock_mortal_heal_aura_specs(self) -> List[dict]:
        """
        Unit-specific aura: while an enemy unit is within range, if this unit contains a named model,
        each failed Battle-shock test for that enemy causes mortal wounds and heals one model in this unit.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
            - required_model_name: str
            - mortal_wounds_roll: str (e.g. D3)
            - heal_roll: str (e.g. D3)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_enemy_failed_battleshock_mortal_heal_aura_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, int, str, str, str]] = set()
        pattern = (
            r"while an enemy unit is within (?P<range>\d+) of this unit "
            r"if this unit contains an? (?P<model>[a-z0-9 '\-]+?)(?: model)? "
            r"each time that enemy unit fails a battle shock test "
            r"it suffers (?P<mortal>d3|d6|\d+) mortal wounds? and one model in this unit regains up to (?P<heal>d3|d6|\d+) lost wounds?"
        )

        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = re.fullmatch(pattern, normalized)
                if not m:
                    continue
                try:
                    range_value = int(m.group("range") or 0)
                except Exception:
                    range_value = 0
                if range_value <= 0:
                    continue
                required_model_name = " ".join(str(m.group("model") or "").strip().split())
                if not required_model_name:
                    continue
                mortal_expr = str(m.group("mortal") or "").strip().upper()
                heal_expr = str(m.group("heal") or "").strip().upper()
                if not mortal_expr or not heal_expr:
                    continue
                source = str(name or "Failed Battle-shock aura").strip() or "Failed Battle-shock aura"
                key = (
                    source.lower(),
                    int(range_value),
                    required_model_name.lower(),
                    mortal_expr,
                    heal_expr,
                )
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "range": int(range_value),
                        "required_model_name": required_model_name,
                        "mortal_wounds_roll": mortal_expr,
                        "heal_roll": heal_expr,
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_fight_selected_enemy_melee_hit_penalty_specs(self) -> List[dict]:
        """
        Unit-specific rule: enemy units selected to fight while within Engagement Range suffer -1 to hit for melee attacks
        until the end of the phase (may exclude TITANIC/TITAN units).

        Returns a list of specs with keys:
            - source: ability name
            - exclude_keyword: optional keyword to exclude (e.g., TITANIC/TITAN)
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_fight_selected_enemy_melee_hit_penalty_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, str]] = set()

        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._FIGHT_SELECTED_ENEMY_MELEE_HIT_PENALTY_RE.fullmatch(normalized)
                if not m:
                    continue
                exclude = str(m.group("exclude") or "").strip().lower()
                exclude_keyword = ""
                if exclude == "titanic":
                    exclude_keyword = "TITANIC"
                elif exclude == "titan":
                    exclude_keyword = "TITAN"
                source = str(name or "Engagement melee hit penalty").strip() or "Engagement melee hit penalty"
                key = (source.lower(), exclude_keyword)
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"source": source, "exclude_keyword": exclude_keyword})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_fight_selected_daemonic_patrons_specs(self) -> List[dict]:
        """
        Unit-specific rule: selected to fight, optional Daemonic Patrons (critical wound on 3+);
        end of Fight phase penalty if no enemy models destroyed.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_daemonic_patrons_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[str] = set()

        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._DAEMONIC_PATRONS_RE.fullmatch(normalized)
                if not m:
                    continue
                try:
                    threshold = int(m.group("thresh") or 0)
                except Exception:
                    threshold = 0
                if threshold < 2 or threshold > 6:
                    continue
                source = str(name or "Daemonic Patrons").strip() or "Daemonic Patrons"
                key = source.lower()
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"source": source, "crit_wound_threshold": threshold})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_ranged_afflicted_strength_ap_bonus_specs(self) -> List[dict]:
        """
        Unit-specific rule: ranged attacks against Afflicted targets improve Strength and AP by a fixed value
        if unit Starting Strength is high enough or if a CHARACTER is leading the unit.

        Returns specs with keys:
            - source: ability name
            - min_starting_strength: int
            - bonus: int
            - afflicted_only: bool
            - character_leader_ok: bool
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_ranged_afflicted_strength_ap_bonus_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, int, int]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._RANGED_AFFLICTED_STRENGTH_AP_BONUS_RE.fullmatch(normalized)
                if not m:
                    continue
                try:
                    min_strength = int(m.group("min") or 0)
                except Exception:
                    min_strength = 0
                if min_strength <= 0:
                    continue
                try:
                    bonus = int(m.group("val") or 0)
                except Exception:
                    bonus = 0
                if bonus <= 0:
                    continue
                source = str(name or "Ranged Afflicted bonus").strip() or "Ranged Afflicted bonus"
                key = (source.lower(), int(min_strength), int(bonus))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "min_starting_strength": int(min_strength),
                        "bonus": int(bonus),
                        "afflicted_only": True,
                        "character_leader_ok": True,
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_spore_laced_shock_waves_specs(self) -> List[dict]:
        """
        Unit-specific rule: when selecting a target for a specific ranged weapon, roll for target
        and nearby enemy units; struck units suffer mortal wounds after attacks are resolved.

        Returns specs with keys:
            - source: ability name
            - weapon_key: str
            - range: int
            - threshold: int
            - afflicted_roll_bonus: int
            - mortal_wounds: str | int
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_spore_laced_shock_waves_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, str, int, int, int, str]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._SPORE_LACED_SHOCK_WAVES_RE.fullmatch(normalized)
                if not m:
                    continue
                weapon_raw = str(m.group("weapon") or "").strip()
                weapon_key = unit._normalize_keyword_phrase(weapon_raw) or weapon_raw.lower()
                if not weapon_key:
                    continue
                try:
                    range_value = int(m.group("range") or 0)
                except Exception:
                    range_value = 0
                if range_value <= 0:
                    continue
                try:
                    threshold = int(m.group("threshold") or 0)
                except Exception:
                    threshold = 0
                if threshold <= 0:
                    continue
                try:
                    bonus = int(m.group("bonus") or 0)
                except Exception:
                    bonus = 0
                mw_raw = str(m.group("mw") or "").strip().lower()
                if not mw_raw:
                    continue
                if mw_raw in ("d3", "d6"):
                    mw_value: str | int = mw_raw
                else:
                    try:
                        mw_value = int(mw_raw)
                    except Exception:
                        continue
                    if int(mw_value) <= 0:
                        continue
                source = str(name or "Spore-laced Shock Waves").strip() or "Spore-laced Shock Waves"
                key = (
                    source.lower(),
                    weapon_key,
                    int(range_value),
                    int(threshold),
                    int(bonus),
                    str(mw_value),
                )
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "weapon_key": weapon_key,
                        "range": int(range_value),
                        "threshold": int(threshold),
                        "afflicted_roll_bonus": int(bonus),
                        "mortal_wounds": mw_value,
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_thundershock_specs(self) -> List[dict]:
        """
        Unit-specific rule: when selecting a target for a specific ranged weapon, roll for target
        and nearby enemy units; struck units suffer mortal wounds after attacks are resolved.

        Returns specs with keys:
            - source: ability name
            - weapon_key: str
            - range: int
            - threshold: int
            - mortal_wounds: str | int
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_thundershock_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, str, int, int, str]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._THUNDERSHOCK_RE.fullmatch(normalized)
                if not m:
                    continue
                weapon_raw = str(m.group("weapon") or "").strip()
                weapon_key = unit._normalize_keyword_phrase(weapon_raw) or weapon_raw.lower()
                if not weapon_key:
                    continue
                try:
                    range_value = int(m.group("range") or 0)
                except Exception:
                    range_value = 0
                if range_value <= 0:
                    continue
                try:
                    threshold = int(m.group("threshold") or 0)
                except Exception:
                    threshold = 0
                if threshold <= 0:
                    continue
                mw_raw = str(m.group("mw") or "").strip().lower()
                if not mw_raw:
                    continue
                if mw_raw in ("d3", "d6"):
                    mw_value: str | int = mw_raw
                else:
                    try:
                        mw_value = int(mw_raw)
                    except Exception:
                        continue
                    if int(mw_value) <= 0:
                        continue
                source = str(name or "Thundershock").strip() or "Thundershock"
                key = (
                    source.lower(),
                    weapon_key,
                    int(range_value),
                    int(threshold),
                    str(mw_value),
                )
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "weapon_key": weapon_key,
                        "range": int(range_value),
                        "threshold": int(threshold),
                        "mortal_wounds": mw_value,
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_no_advance_start_or_end_within_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: enemy models cannot start or end an Advance move within range of this model.

        Returns specs with keys:
            - source: ability name
            - range: int
        """
        if model is None:
            return []
        cache_key = f"model_no_advance_start_or_end_within:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._NO_ADVANCE_START_OR_END_WITHIN_RE.fullmatch(normalized)
            if not m:
                continue
            source_subject = str(m.groupdict().get("source_subject", "") or "").strip().lower()
            if source_subject and source_subject != "model":
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            source = str(name or "Advance denial").strip() or "Advance denial"
            key = (source.lower(), int(range_value))
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "range": int(range_value)})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_no_advance_start_or_end_within_specs(self) -> List[dict]:
        """
        Unit-specific rule: enemy units/models cannot start or end an Advance move within range of this unit.

        Returns specs with keys:
            - source: ability name
            - range: int
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_no_advance_start_or_end_within_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int]] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for member in members:
            if member is None:
                continue
            for name, desc in member._iter_ability_entries_for_rules(model=None):
                text_src = member._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = member._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = member._NO_ADVANCE_START_OR_END_WITHIN_RE.fullmatch(normalized)
                if not m:
                    continue
                source_subject = str(m.groupdict().get("source_subject", "") or "").strip().lower()
                if source_subject and source_subject != "unit":
                    continue
                try:
                    range_value = int(m.group("range") or 0)
                except Exception:
                    range_value = 0
                if range_value <= 0:
                    continue
                source = str(name or "Advance denial").strip() or "Advance denial"
                key = (source.lower(), int(range_value))
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"source": source, "range": int(range_value)})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_deep_strike_afflicted_distance_specs(self) -> List[dict]:
        """
        Unit-specific Deep Strike rule with split minimum distances for Afflicted vs other enemy units.

        Returns specs with keys:
            - source: ability name
            - afflicted_distance: int
            - other_distance: int
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_deep_strike_afflicted_distance_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, int, int]] = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = unit._DEEP_STRIKE_AFFLICTED_DISTANCE_RE.fullmatch(normalized)
                if not m:
                    continue
                try:
                    afflicted = int(m.group("afflicted") or 0)
                except Exception:
                    afflicted = 0
                try:
                    other = int(m.group("other") or 0)
                except Exception:
                    other = 0
                if afflicted <= 0 or other <= 0:
                    continue
                source = str(name or "Deep Strike distance").strip() or "Deep Strike distance"
                key = (source.lower(), int(afflicted), int(other))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "afflicted_distance": int(afflicted),
                        "other_distance": int(other),
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_fight_selected_mortal_table_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: each time this model's unit is selected to fight, optionally select an engaged enemy
        and apply mortal wounds based on a D6 table.

        Returns list of specs with keys:
            - source: ability name
            - threshold_low_min: int
            - threshold_low_max: int
            - mortal_low: int
            - threshold_mid_min: int
            - threshold_mid_max: int
            - mortal_mid_roll: str
            - threshold_high: int
            - mortal_high_roll: str
            - mortal_high_bonus: int
        """
        if model is None:
            return []
        cache_key = f"model_fight_selected_mortal_table:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._FIGHT_SELECTED_MORTAL_TABLE_RE.fullmatch(normalized):
                continue
            source = str(name or "Fight selected mortals").strip() or "Fight selected mortals"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "threshold_low_min": 2,
                    "threshold_low_max": 3,
                    "mortal_low": 1,
                    "threshold_mid_min": 4,
                    "threshold_mid_max": 5,
                    "mortal_mid_roll": "D3",
                    "threshold_high": 6,
                    "mortal_high_roll": "D3",
                    "mortal_high_bonus": 3,
                }
            )

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and sr.get("enhancement_osseus_key"):
            bearer_id = str(
                sr.get("enhancement_osseus_key_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            model_id = str(get_entity_id(model) or "").strip()
            if model_id and (not bearer_id or bearer_id == model_id):
                try:
                    range_value = int(float(sr.get("enhancement_osseus_key_range", 12.0) or 12.0))
                except Exception:
                    range_value = 12
                if range_value > 0:
                    source = str(sr.get("enhancement_osseus_key_source", "") or "Osseus Key").strip() or "Osseus Key"
                    required_keywords: list[str] = []
                    for keyword in list(sr.get("enhancement_osseus_key_required_target_keywords", ("VEHICLE",)) or []):
                        kw = str(keyword or "").strip().upper()
                        if kw and kw not in required_keywords:
                            required_keywords.append(kw)
                    excluded_keywords: list[str] = []
                    for keyword in list(sr.get("enhancement_osseus_key_excluded_target_keywords", ("TITANIC",)) or []):
                        kw = str(keyword or "").strip().upper()
                        if kw and kw not in excluded_keywords:
                            excluded_keywords.append(kw)
                    resolution_mode = str(
                        sr.get("enhancement_osseus_key_resolution_mode", "") or "leadership_test"
                    ).strip().lower() or "leadership_test"
                    key = (
                        source.lower(),
                        int(range_value),
                        bool(False),
                        bool(False),
                        str(resolution_mode),
                        tuple(required_keywords),
                        tuple(excluded_keywords),
                    )
                    if key not in seen:
                        seen.add(key)
                        specs.append(
                            {
                                "source": source,
                                "range": int(range_value),
                                "mortal_on_one": False,
                                "optional": False,
                                "limit_one_per_army": False,
                                "grant_ranged_hazardous": False,
                                "resolution_mode": str(resolution_mode),
                                "required_target_keywords": list(required_keywords),
                                "excluded_target_keywords": list(excluded_keywords),
                            }
                        )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_end_fight_phase_engagement_mortal_wounds_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Fight phase, select an engaged enemy and roll eight D6 for mortal wounds.

        Returns a list of specs with keys:
            - source: ability name
            - dice: int
            - threshold: int
            - mortal_per_success: int
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_end_mortal_wounds:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._FIGHT_PHASE_END_ENGAGEMENT_MORTAL_EIGHT_D6_RE.fullmatch(normalized):
                continue
            source = str(name or "Fight phase mortals").strip() or "Fight phase mortals"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "dice": 8,
                    "threshold": 4,
                    "mortal_per_success": 1,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_fight_phase_end_enemy_within_range_mortal_threshold_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Fight phase, roll D6 for each enemy unit within range;
        on a threshold, that enemy unit suffers mortal wounds.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
            - threshold: int
            - mortal_wounds: str | int
        """
        if model is None:
            return []
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        root_sr = getattr(root, "special_rules", None)
        has_orbs_of_unlife = bool(isinstance(root_sr, dict) and bool(root_sr.get("enhancement_orbs_of_unlife", False)))
        cache_key = f"model_fight_phase_end_enemy_within_range_mortal_threshold:{get_entity_id(model)}"
        if (not has_orbs_of_unlife) and cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int, str]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._FIGHT_PHASE_END_ENEMY_WITHIN_RANGE_MORTAL_THRESHOLD_RE.fullmatch(normalized)
            if not m:
                continue

            range_token = str(m.group("range") or "").strip()
            threshold_token = str(m.group("threshold") or "").strip()
            if not range_token.isdigit() or not threshold_token.isdigit():
                continue
            range_value = int(range_token)
            threshold = int(threshold_token)
            if range_value <= 0 or threshold <= 0:
                continue

            mortal_raw = str(m.group("mw") or "").strip().lower()
            if not mortal_raw:
                continue
            mortal_wounds: str | int
            if mortal_raw in ("d3", "d6"):
                mortal_wounds = mortal_raw
            elif mortal_raw.isdigit():
                mortal_wounds = int(mortal_raw)
                if int(mortal_wounds) <= 0:
                    continue
            else:
                continue

            source = str(name or "Fight phase mortals").strip() or "Fight phase mortals"
            key = (source.lower(), int(range_value), int(threshold), str(mortal_wounds))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "threshold": int(threshold),
                    "mortal_wounds": mortal_wounds,
                }
            )

        if isinstance(root_sr, dict) and bool(root_sr.get("enhancement_orbs_of_unlife", False)):
            bearer_id = str(
                root_sr.get("enhancement_orbs_of_unlife_bearer_model_id", "")
                or root_sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            model_id = str(get_entity_id(model) or "").strip()
            model_local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
            model_is_bearer = bool(
                bearer_id and (model_id == bearer_id or (model_local_id and model_local_id == bearer_id))
            )
            if model_is_bearer:
                try:
                    range_value = float(root_sr.get("enhancement_orbs_of_unlife_range", 3.0) or 3.0)
                except Exception:
                    range_value = 3.0
                try:
                    threshold = int(root_sr.get("enhancement_orbs_of_unlife_threshold", 4) or 4)
                except Exception:
                    threshold = 4
                if bool(root_sr.get("enhancement_orbs_of_unlife_requires_dark_pact_passed_for_threshold_bonus", True)):
                    dark_pacts_active = bool(root_sr.get("dark_pacts_active", False))
                    dark_pacts_passed = bool(root_sr.get("dark_pacts_test_passed", False))
                    dark_pacts_phase = str(root_sr.get("dark_pacts_expires_phase", "") or "").strip().upper()
                    if dark_pacts_active and dark_pacts_passed and dark_pacts_phase == "FIGHT_PHASE":
                        try:
                            threshold = int(
                                root_sr.get("enhancement_orbs_of_unlife_threshold_if_dark_pact_passed", threshold) or threshold
                            )
                        except Exception:
                            threshold = int(threshold)
                source = str(root_sr.get("enhancement_orbs_of_unlife_source", "") or "Orbs of Unlife").strip()
                source = source or "Orbs of Unlife"
                mortal_wounds = str(root_sr.get("enhancement_orbs_of_unlife_mortal_wounds", "d3") or "d3").strip().lower()
                if mortal_wounds not in ("d3", "d6"):
                    mortal_wounds = "d3"
                key = (source.lower(), int(max(0.0, range_value)), int(max(2, min(6, threshold))), str(mortal_wounds))
                if key not in seen:
                    seen.add(key)
                    specs.append(
                        {
                            "source": source,
                            "range": float(max(0.0, range_value)),
                            "threshold": int(max(2, min(6, threshold))),
                            "mortal_wounds": mortal_wounds,
                        }
                    )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        if not has_orbs_of_unlife:
            self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_start_fight_phase_malign_sacrifice_specs(self) -> List[dict]:
        """
        Unit-specific rule: at the start of the Fight phase, select a Dark Disciple and an engaged enemy,
        then roll for mortal wounds and destroy that model (Malign Sacrifice).
        """
        cache_key = "unit_fight_phase_malign_sacrifice"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            source = str(name or "Malign Sacrifice").strip() or "Malign Sacrifice"

            m = self._MALIGN_SACRIFICE_RE.fullmatch(normalized)
            if m:
                model_name = str(m.group("model") or "dark disciple").strip() or "dark disciple"
                key = source.lower()
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "model_name": model_name,
                        "allow_any_model": False,
                        "roll_bonus_vs_vehicle": 0,
                        "roll_low_min": 2,
                        "roll_low_max": 5,
                        "roll_low_mortal": "1",
                        "roll_high_threshold": 6,
                        "roll_high_mortal": "d3",
                        "destroy_selected_model": True,
                    }
                )
                continue

            m = self._START_FIGHT_PHASE_SELF_DESTRUCTION_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                vehicle_bonus = int(m.group("vehicle_bonus") or 0)
            except Exception:
                vehicle_bonus = 0
            high_raw = str(m.group("high") or "").strip()
            if not high_raw:
                high_raw = "3"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "model_name": "",
                    "allow_any_model": True,
                    "roll_bonus_vs_vehicle": int(max(0, vehicle_bonus)),
                    "roll_low_min": 2,
                    "roll_low_max": 5,
                    "roll_low_mortal": "d3",
                    "roll_high_threshold": 6,
                    "roll_high_mortal": high_raw,
                    "destroy_selected_model": True,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_move_over_battleshock_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Normal/Advance move, select an enemy unit moved over;
        that unit takes a Battle-shock test.

        Returns a list of specs with keys:
            - source: ability name
            - move_types: list[str]
            - optional: bool
            - ability_key: str
        """
        if model is None:
            return []
        cache_key = f"model_move_over_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, tuple[str, ...], bool]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            if not normalized:
                continue
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if "moved over" not in normalized and "moved across" not in normalized:
                continue
            if "battle shock test" not in normalized:
                continue
            if "mortal wound" in normalized:
                continue
            if "each time this model ends a" not in normalized:
                continue
            if "that unit must take a battle shock test" not in normalized:
                continue
            m = re.search(r"each time this model ends a (?P<moves>[a-z0-9 ]+) move", normalized)
            if m is None:
                continue
            moves_text = str(m.group("moves") or "").strip()
            move_types = self._parse_move_types_from_text(moves_text)
            if "move" not in move_types:
                continue
            if not move_types.issubset({"move", "advance"}):
                continue
            source = str(name or "Move-over Battle-shock").strip() or "Move-over Battle-shock"
            optional = "you can select" in normalized or "can select one enemy unit" in normalized
            ability_key_seed = self._normalize_keyword_phrase(source) or "move_over_battleshock"
            ability_key = f"move_over_battleshock:{ability_key_seed}"
            dedupe_key = (source.lower(), tuple(sorted(move_types)), bool(optional))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            specs.append(
                {
                    "source": source,
                    "move_types": sorted(move_types),
                    "optional": bool(optional),
                    "ability_key": ability_key,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_move_over_mortal_wounds_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Normal/Advance move, select an enemy unit moved over and roll D6s for mortals.

        Returns a list of specs with keys:
            - source: ability name
            - dice: int
            - threshold: int
            - mortal_per_success: int
            - move_types: list[str] (e.g., ["move", "advance"])
            - exclude_monster_vehicle: bool
        """
        if model is None:
            return []
        cache_key = f"model_move_over_mortal_wounds:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            if not normalized:
                continue
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9+]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if ("moved over" not in normalized and "moved across" not in normalized) or "mortal wound" not in normalized:
                continue
            if "for each model" in normalized:
                continue
            if "one of the following" in normalized:
                continue

            m = self._MOVE_OVER_MORTAL_WOUNDS_RE.fullmatch(normalized)
            if not m:
                continue

            moves_text = (m.group("moves") or "").strip()
            move_types = self._parse_move_types_from_text(moves_text)
            if "move" not in move_types:
                continue
            if not move_types.issubset({"move", "advance"}):
                continue

            dice_raw = (m.group("dice") or "").strip().lower()
            dice_count = None
            if dice_raw.isdigit():
                dice_count = int(dice_raw)
            else:
                dice_count = self._NUMBER_WORDS.get(dice_raw)
            if not dice_count or dice_count <= 0:
                continue
            try:
                threshold = int(m.group("threshold") or 0)
            except Exception:
                threshold = 0
            mw_token = str(m.group("mw") or "").strip().lower()
            mortal_per = 0
            mortal_die = ""
            if mw_token.startswith("d"):
                mortal_die = mw_token.upper()
            else:
                try:
                    mortal_per = int(mw_token or 0)
                except Exception:
                    mortal_per = 0
            if threshold <= 0 or (mortal_per <= 0 and not mortal_die):
                continue

            exclude_mv = "excluding monsters and vehicles" in normalized or "excluding monster and vehicle" in normalized
            fly_bonus = 0
            try:
                fly_bonus = int(m.group("fly_bonus") or 0)
            except Exception:
                fly_bonus = 0
            source = str(name or "Move-over mortals").strip() or "Move-over mortals"
            key = (
                source.lower(),
                int(dice_count),
                int(threshold),
                str(mortal_die or ""),
                int(mortal_per),
                tuple(sorted(move_types)),
                bool(exclude_mv),
                int(fly_bonus or 0),
            )
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "dice": int(dice_count),
                    "threshold": int(threshold),
                    "mortal_per_success": int(mortal_per),
                    "mortal_per_success_die": str(mortal_die),
                    "move_types": sorted(move_types),
                    "exclude_monster_vehicle": bool(exclude_mv),
                    "fly_bonus": int(fly_bonus or 0),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_move_over_mortal_wounds_specs(self) -> List[dict]:
        """
        Unit-level rule: end of Normal/Advance move, select an enemy unit moved over and roll D6s per model.

        Returns a list of specs with keys:
            - source: ability name
            - threshold: int
            - mortal_per_success: int
            - mortal_per_success_die: str
            - move_types: list[str]
            - exclude_monster_vehicle: bool
            - fly_bonus: int
            - dice_per_model: bool
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_move_over_mortal_wounds"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit in members:
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = unit._strip_eligibility_prefix(text_src)
                normalized = unit._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9+]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if ("moved over" not in normalized and "moved across" not in normalized) or "mortal wound" not in normalized:
                    continue
                if "for each model in this unit" not in normalized:
                    continue
                m = unit._UNIT_MOVE_OVER_MORTAL_WOUNDS_RE.fullmatch(normalized)
                if not m:
                    continue
                moves_text = (m.group("moves") or "").strip()
                move_types = unit._parse_move_types_from_text(moves_text)
                if "move" not in move_types:
                    continue
                if not move_types.issubset({"move", "advance"}):
                    continue
                try:
                    threshold = int(m.group("threshold") or 0)
                except Exception:
                    threshold = 0
                mw_token = str(m.group("mw") or "").strip().lower()
                mortal_per = 0
                mortal_die = ""
                if mw_token.startswith("d"):
                    mortal_die = mw_token.upper()
                else:
                    try:
                        mortal_per = int(mw_token or 0)
                    except Exception:
                        mortal_per = 0
                if threshold <= 0 or (mortal_per <= 0 and not mortal_die):
                    continue
                exclude_mv = "excluding monsters and vehicles" in normalized or "excluding monster and vehicle" in normalized
                once_per_battle = "once per battle" in normalized
                try:
                    fly_bonus = int(m.group("fly_bonus") or 0)
                except Exception:
                    fly_bonus = 0
                source = str(name or "Move-over mortals").strip() or "Move-over mortals"
                key_seed = self._normalize_keyword_phrase(source) or "move_over_mortals"
                ability_key = f"move_over_mortals:{key_seed}"
                key = (
                    source.lower(),
                    int(threshold),
                    str(mortal_die or ""),
                    int(mortal_per),
                    tuple(sorted(move_types)),
                    bool(exclude_mv),
                    int(fly_bonus or 0),
                    bool(once_per_battle),
                )
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "threshold": int(threshold),
                        "mortal_per_success": int(mortal_per),
                        "mortal_per_success_die": str(mortal_die),
                        "move_types": sorted(move_types),
                        "exclude_monster_vehicle": bool(exclude_mv),
                        "fly_bonus": int(fly_bonus or 0),
                        "dice_per_model": True,
                        "once_per_battle": bool(once_per_battle),
                        "ability_key": ability_key,
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_stasis_bomb_specs(self) -> List[dict]:
        """
        Unit-level rule: after ending a Normal move, one model can select a moved-over enemy
        (excluding AIRCRAFT), inflict D3 mortal wounds, then apply a movement lock in the
        opponent's next Movement phase.

        Returns specs with keys:
            - source: ability name
            - move_types: list[str]
            - exclude_aircraft: bool
            - mortal_wounds_die: str
            - restriction_roll_die: str
            - once_per_turn_army: bool
            - once_per_battle_per_model: bool
            - ability_key: str
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_stasis_bomb_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(unit._strip_eligibility_prefix(text_src))
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9+]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                name_low = str(name or "").strip().lower()
                if "stasis bomb" not in name_low and "stasis bomb" not in normalized:
                    continue
                required_phrases = (
                    "ends a normal move",
                    "moved over",
                    "suffers d3 mortal wounds",
                    "roll one d6",
                    "cannot advance or fall back",
                    "must remain stationary",
                    "once per turn",
                    "once per battle",
                )
                if any(phrase not in normalized for phrase in required_phrases):
                    continue
                source = str(name or "Stasis Bomb").strip() or "Stasis Bomb"
                ability_key_seed = self._normalize_keyword_phrase(source) or "stasis_bomb"
                ability_key = f"stasis_bomb:{ability_key_seed}"
                key = (source.lower(), ability_key)
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "move_types": ["move"],
                        "exclude_aircraft": True,
                        "mortal_wounds_die": "D3",
                        "restriction_roll_die": "D6",
                        "restriction_low_max": 3,
                        "restriction_on_low": "no_advance_fall_back",
                        "restriction_on_high": "remain_stationary",
                        "once_per_turn_army": True,
                        "once_per_battle_per_model": True,
                        "ability_key": ability_key,
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_floating_death_specs(self) -> List[dict]:
        """
        Unit-level rule: after this unit or an enemy unit ends a move, each model within range
        self-destructs and inflicts mortal wounds to a selected enemy unit.

        Returns specs with keys:
            - source: ability name
            - range: int
            - on_mid_flat: int
            - on_mid_die: str
            - on_high_die: str
        """
        get_root = getattr(self, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else self
        if root is None:
            root = self
        cache_key = "unit_floating_death_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()

        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]

        for unit in members:
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = unit._strip_eligibility_prefix(text_src)
                normalized = unit._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()

                required_phrases = (
                    "each time this unit or an enemy unit ends a move",
                    "for each model in this unit that is within",
                    "one or more enemy units",
                    "that model in this unit is destroyed",
                    "on a 2 5",
                    "on a 6",
                    "mortal wound",
                )
                if not all(phrase in normalized for phrase in required_phrases):
                    continue

                range_match = re.search(
                    r"for each model in this unit that is within (?P<range>\d+) of one or more enemy units",
                    normalized,
                )
                if range_match is None:
                    continue
                try:
                    range_value = int(range_match.group("range") or 0)
                except (TypeError, ValueError):
                    range_value = 0
                if range_value <= 0:
                    continue

                on_mid_flat = 0
                on_mid_die = ""
                on_high_die = ""

                if (
                    "on a 2 5 that enemy unit suffers 1 mortal wound" in normalized
                    and "on a 6 that enemy unit suffers d3 mortal wounds" in normalized
                ):
                    on_mid_flat = 1
                    on_mid_die = ""
                    on_high_die = "D3"
                elif (
                    "on a 2 5 that enemy unit suffers d3 mortal wounds" in normalized
                    and "on a 6 that enemy unit suffers d6 mortal wounds" in normalized
                ):
                    on_mid_flat = 0
                    on_mid_die = "D3"
                    on_high_die = "D6"
                else:
                    continue

                source = str(name or "Floating Death").strip() or "Floating Death"
                key = (
                    source.lower(),
                    int(range_value),
                    int(on_mid_flat),
                    str(on_mid_die),
                    str(on_high_die),
                )
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "range": int(range_value),
                        "on_mid_flat": int(on_mid_flat),
                        "on_mid_die": str(on_mid_die),
                        "on_high_die": str(on_high_die),
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_parasitic_infection_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: BARBED OVIPOSITOR infantry kill can spawn RIPPER SWARMS.

        Returns specs with keys:
            - source: ability name
            - weapon_name: expected weapon profile/wargear name
            - required_target_keyword: keyword gate for destroyed model
            - spawn_unit_name: unit to spawn
            - spawn_model_count_roll: die expression for spawned model count
            - setup_range: setup distance from source model
            - allow_target_engagement: spawned unit may be within Engagement Range of destroyed model's unit
            - disallow_other_enemy_engagement: spawned unit cannot be within Engagement Range of other enemies
        """
        if model is None:
            return []
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = f"model_parasitic_infection_specs:{get_entity_id(model)}"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return list(cache.get(cache_key) or [])

        specs: list[dict] = []
        seen: set[tuple] = set()
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            if not normalized:
                continue
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"'s\b", " s", normalized)
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()

            required = (
                "each time an infantry model is destroyed by an attack made with this model s",
                "after this model has finished making its attacks",
                "you can add one new",
                "unit to your army consisting of d3 models",
                "set it up within",
                "of this model",
                "can be set up within engagement range of the destroyed model s unit",
                "but not within engagement range of any other enemy units",
            )
            if not all(fragment in normalized for fragment in required):
                continue

            weapon_match = re.search(
                r"destroyed by an attack made with this model s (?P<weapon>[a-z0-9 ]+?) after this model has finished making its attacks",
                normalized,
            )
            if weapon_match is None:
                continue
            weapon_name = str(weapon_match.group("weapon") or "").strip()
            if not weapon_name:
                continue

            spawn_match = re.search(
                r"you can add one new (?P<spawn>[a-z0-9 ]+?) unit to your army consisting of (?P<count>d\d+|\d+) models",
                normalized,
            )
            if spawn_match is None:
                continue
            spawn_name_raw = str(spawn_match.group("spawn") or "").strip()
            if not spawn_name_raw:
                continue
            spawn_unit_name = " ".join(token.capitalize() for token in spawn_name_raw.split())
            count_roll = str(spawn_match.group("count") or "").strip().upper()
            if not count_roll:
                continue

            range_match = re.search(r"set it up within (?P<range>\d+) of this model", normalized)
            if range_match is None:
                continue
            try:
                setup_range = int(range_match.group("range") or 0)
            except (TypeError, ValueError):
                setup_range = 0
            if setup_range <= 0:
                continue

            source = str(name or "Parasitic Infection").strip() or "Parasitic Infection"
            key = (
                source.lower(),
                weapon_name,
                spawn_unit_name.lower(),
                count_roll,
                int(setup_range),
            )
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "weapon_name": weapon_name,
                    "required_target_keyword": "INFANTRY",
                    "spawn_unit_name": spawn_unit_name,
                    "spawn_model_count_roll": count_roll,
                    "setup_range": int(setup_range),
                    "allow_target_engagement": True,
                    "disallow_other_enemy_engagement": True,
                }
            )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def unit_seed_spore_mines_specs(self) -> List[dict]:
        """
        Unit-level Tyranid rule: one unit with this ability can seed a spawned mine unit instead of shooting.

        Returns specs with keys:
            - source: ability name
            - spawn_unit_name: spawned datasheet name
            - setup_range: setup distance from the source model/unit
            - source_scope: "model" or "unit"
            - enemy_exclusion_range_horizontal: minimum horizontal distance from enemy units
            - count_mode: "fixed", "roll", or "per_source_model"
            - spawn_model_count: fixed count when count_mode == "fixed"
            - spawn_model_count_roll: die expression when count_mode == "roll"
            - count_per_source_model: multiplier when count_mode == "per_source_model"
            - once_per_turn_shared: bool
            - instead_of_shooting: bool
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_seed_spore_mines_specs"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return list(cache.get(cache_key) or [])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        specs: list[dict] = []
        seen: set[tuple[str, str, int, str, int, str, int, str, int]] = set()

        for unit in list(members):
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized = unit._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"'s\b", " s", normalized)
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()

                required = (
                    "once per turn",
                    "in your shooting phase",
                    "when selected to shoot",
                    "one unit with this ability can use it instead of making any attacks with its ranged weapons",
                    "you can add one new",
                    "set it up anywhere on the battlefield",
                    "wholly within",
                    "more than",
                    "horizontally away from all enemy units",
                )
                if not all(fragment in normalized for fragment in required):
                    continue

                spawn_match = re.search(r"you can add one new (?P<spawn>[a-z0-9 ]+?) unit", normalized)
                if spawn_match is None:
                    continue
                spawn_name_raw = str(spawn_match.group("spawn") or "").strip()
                if not spawn_name_raw:
                    continue
                spawn_unit_name = " ".join(token.capitalize() for token in spawn_name_raw.split())

                range_match = re.search(r"wholly within (?P<range>\d+) of this (?P<scope>model|unit)", normalized)
                if range_match is None:
                    continue
                try:
                    setup_range = int(range_match.group("range") or 0)
                except (TypeError, ValueError):
                    setup_range = 0
                if setup_range <= 0:
                    continue
                source_scope = str(range_match.group("scope") or "unit").strip().lower()
                if source_scope not in ("model", "unit"):
                    source_scope = "unit"

                enemy_match = re.search(r"more than (?P<enemy>\d+) horizontally away from all enemy units", normalized)
                if enemy_match is None:
                    continue
                try:
                    enemy_exclusion = int(enemy_match.group("enemy") or 0)
                except (TypeError, ValueError):
                    enemy_exclusion = 0
                if enemy_exclusion <= 0:
                    continue

                count_mode = "fixed"
                spawn_model_count = 1
                spawn_model_count_roll = ""
                count_per_source_model = 0
                if "contains 1 model for each model in this unit" in normalized:
                    count_mode = "per_source_model"
                    spawn_model_count = 0
                    count_per_source_model = 1
                else:
                    count_match = re.search(
                        r"unit (?:containing|contains) (?P<count_expr>d\d+|\d+) models?",
                        normalized,
                    )
                    if count_match is not None:
                        count_expr = str(count_match.group("count_expr") or "").strip().upper()
                        if count_expr.startswith("D"):
                            count_mode = "roll"
                            spawn_model_count = 0
                            spawn_model_count_roll = count_expr
                        else:
                            try:
                                spawn_model_count = int(count_expr or 0)
                            except (TypeError, ValueError):
                                spawn_model_count = 0
                            if spawn_model_count <= 0:
                                continue

                source = str(name or "Seed Spore Mines").strip() or "Seed Spore Mines"
                key = (
                    source.lower(),
                    spawn_unit_name.lower(),
                    int(setup_range),
                    str(source_scope),
                    int(enemy_exclusion),
                    str(count_mode),
                    int(spawn_model_count),
                    str(spawn_model_count_roll),
                    int(count_per_source_model),
                )
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "source": source,
                        "spawn_unit_name": spawn_unit_name,
                        "setup_range": int(setup_range),
                        "source_scope": str(source_scope),
                        "enemy_exclusion_range_horizontal": int(enemy_exclusion),
                        "count_mode": str(count_mode),
                        "spawn_model_count": int(spawn_model_count),
                        "spawn_model_count_roll": str(spawn_model_count_roll),
                        "count_per_source_model": int(count_per_source_model),
                        "once_per_turn_shared": True,
                        "instead_of_shooting": True,
                        "allow_target_engagement": False,
                        "disallow_other_enemy_engagement": True,
                    }
                )

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def move_over_mortal_wounds_reroll_count(self) -> int:
        """Count models that can re-roll their move-over mortal wound die (e.g., Cluster Caltrops)."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        if not models:
            return 0
        count = 0
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            for name, desc in root._iter_model_specific_ability_entries(model):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = root._strip_eligibility_prefix(text_src)
                normalized = root._normalize_rules_text(text_src)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if root._MOVE_OVER_MORTAL_WOUNDS_REROLL_RE.fullmatch(normalized):
                    count += 1
                    break
        return int(count)

    def get_first_failed_save_damage_zero_sources(self) -> list[dict]:
        """Return structured sources that can set a failed save's damage to 0."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "first_failed_save_damage_zero_sources"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return list(cache.get(cache_key) or [])

        sources: list[dict] = []
        seen_local: set[str] = set()

        def _matches(text: str) -> bool:
            if not text:
                return False
            norm = root._normalize_rules_text(text)
            if not norm:
                return False
            norm = norm.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", " s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            return bool(root._FIRST_FAILED_SAVE_DAMAGE_ZERO_RE.fullmatch(norm))

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for unit in members:
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                if _matches(desc or name or ""):
                    src = str(name or "First failed save").strip() or "First failed save"
                    key = src.lower()
                    if key in seen_local:
                        continue
                    seen_local.add(key)
                    sources.append(
                        {
                            "source": src,
                            "usage_scope": "turn",
                            "usage_key": "first_failed_save_damage_zero",
                        }
                    )

        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in models:
            for name, desc in root._iter_model_specific_ability_entries(model):
                if _matches(desc or name or ""):
                    src = str(name or "First failed save").strip() or "First failed save"
                    key = src.lower()
                    if key in seen_local:
                        continue
                    seen_local.add(key)
                    sources.append(
                        {
                            "source": src,
                            "usage_scope": "turn",
                            "usage_key": "first_failed_save_damage_zero",
                        }
                    )

        # Adeptus Custodes (Talons Of The Emperor): Aegis Projector.
        for member in members:
            if member is None:
                continue
            source_sr = getattr(member, "special_rules", None)
            if not isinstance(source_sr, dict) or not bool(source_sr.get("enhancement_aegis_projector")):
                continue
            get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
            source_bearer = get_bearer() if callable(get_bearer) else None
            if source_bearer is None or not bool(getattr(source_bearer, "is_alive", True)):
                continue
            source_name = str(source_sr.get("enhancement_aegis_projector_source", "") or "Aegis Projector").strip()
            if not source_name:
                source_name = "Aegis Projector"
            source_unit_id = str(get_entity_id(member) or "")
            if not source_unit_id:
                continue
            usage_scope = str(source_sr.get("enhancement_aegis_projector_usage_scope", "") or "turn").strip().lower()
            if usage_scope not in {"turn", "battle_round", "battle"}:
                usage_scope = "turn"
            key = f"{source_name.lower()}:{source_unit_id}"
            if key in seen_local:
                continue
            seen_local.add(key)
            sources.append(
                {
                    "source": source_name,
                    "usage_scope": usage_scope,
                    "usage_key": f"aegis_projector:{source_unit_id}",
                    "source_unit_id": source_unit_id,
                }
            )

        # Chaos Space Marines (Fellhammer Siege-host): Bastion Plate.
        for member in members:
            if member is None:
                continue
            source_sr = getattr(member, "special_rules", None)
            if not isinstance(source_sr, dict) or not bool(source_sr.get("enhancement_bastion_plate")):
                continue
            get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
            source_bearer = get_bearer() if callable(get_bearer) else None
            if source_bearer is None or not bool(getattr(source_bearer, "is_alive", True)):
                continue
            source_name = str(source_sr.get("enhancement_bastion_plate_source", "") or "Bastion Plate").strip()
            if not source_name:
                source_name = "Bastion Plate"
            source_unit_id = str(get_entity_id(member) or "")
            if not source_unit_id:
                continue
            usage_scope = str(source_sr.get("enhancement_bastion_plate_usage_scope", "") or "battle_round").strip().lower()
            if usage_scope not in {"turn", "battle_round", "battle"}:
                usage_scope = "battle_round"
            key = f"{source_name.lower()}:{source_unit_id}"
            if key in seen_local:
                continue
            seen_local.add(key)
            sources.append(
                {
                    "source": source_name,
                    "usage_scope": usage_scope,
                    "usage_key": f"bastion_plate:{source_unit_id}",
                    "source_unit_id": source_unit_id,
                    "set_damage_to": int(source_sr.get("enhancement_bastion_plate_set_damage_to", 0) or 0),
                    "optional": bool(source_sr.get("enhancement_bastion_plate_optional", True)),
                }
            )

        try:
            army = root.get_parent_army()
        except Exception:
            army = None

        try:
            is_vehicle = bool(root.has_any_keyword("VEHICLE"))
        except Exception:
            try:
                is_vehicle = bool(root.has_keyword("VEHICLE"))
            except Exception:
                is_vehicle = False
        if is_vehicle:
            ec_mgr = getattr(army, "emperors_children", None) if army is not None else None
            if ec_mgr is None and army is not None:
                ec_mgr = getattr(army, "emperors_children_detachments", None)
            try:
                is_ec_vehicle = bool(root.has_any_keyword("EMPEROR'S CHILDREN"))
            except Exception:
                is_ec_vehicle = False
            if not is_ec_vehicle and ec_mgr is not None:
                try:
                    is_ec_vehicle = bool(ec_mgr.is_emperors_children_unit(root))
                except Exception:
                    is_ec_vehicle = False
            if is_ec_vehicle:
                from ...utility.aura_utils import distance_between_models_bases_3d

                try:
                    target_models = list(root.get_attached_unit_models() or [])
                except Exception:
                    target_models = list(getattr(root, "models", []) or [])
                target_models = [m for m in list(target_models or []) if bool(getattr(m, "is_alive", True))]

                if target_models and army is not None:
                    try:
                        army_units = list(getattr(army, "units", []) or [])
                    except Exception:
                        army_units = []
                    seen_source_roots: set[str] = set()
                    heretek_entries: list[dict] = []
                    for unit in list(army_units or []):
                        if unit is None:
                            continue
                        try:
                            source_root = unit.get_attached_unit_root()
                        except Exception:
                            source_root = unit
                        if source_root is None:
                            continue
                        source_root_id = str(get_entity_id(source_root) or "")
                        if source_root_id and source_root_id in seen_source_roots:
                            continue
                        if source_root_id:
                            seen_source_roots.add(source_root_id)
                        try:
                            if not source_root.is_alive() or not bool(getattr(source_root, "deployed", True)):
                                continue
                        except Exception:
                            continue
                        try:
                            if source_root.is_in_reserves() or source_root.is_embarked:
                                continue
                        except Exception:
                            pass
                        try:
                            members = list(source_root.get_attached_unit_members() or [])
                        except Exception:
                            members = [source_root]
                        if not members:
                            members = [source_root]
                        for source_unit in list(members or []):
                            if source_unit is None:
                                continue
                            source_sr = getattr(source_unit, "special_rules", None)
                            if not isinstance(source_sr, dict) or not source_sr.get("enhancement_heretek_adept"):
                                continue
                            source_bearer = getattr(source_unit, "_get_enhancement_bearer_model", lambda: None)()
                            if source_bearer is None or not bool(getattr(source_bearer, "is_alive", True)):
                                continue
                            try:
                                range_value = float(source_sr.get("enhancement_heretek_adept_range", 6) or 6)
                            except Exception:
                                range_value = 6.0
                            if range_value <= 0:
                                continue
                            in_range = False
                            for target_model in list(target_models or []):
                                try:
                                    if float(distance_between_models_bases_3d(source_bearer, target_model)) <= float(range_value) + 1e-6:
                                        in_range = True
                                        break
                                except Exception:
                                    continue
                            if not in_range:
                                continue
                            source_unit_id = str(get_entity_id(source_unit) or "")
                            if not source_unit_id:
                                continue
                            heretek_entries.append(
                                {
                                    "source": "Heretek Adept",
                                    "usage_scope": "battle_round",
                                    "usage_key": f"heretek_adept:{source_unit_id}",
                                    "source_unit_id": source_unit_id,
                                }
                            )
                    if heretek_entries:
                        heretek_entries.sort(key=lambda entry: str(entry.get("source_unit_id", "") or ""))
                        sources.extend(heretek_entries)

        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        is_sm_vehicle = False
        try:
            is_sm_vehicle = bool(root.has_any_keyword("VEHICLE"))
        except Exception:
            is_sm_vehicle = False
        if not is_sm_vehicle:
            try:
                is_sm_vehicle = bool(root.has_keyword("VEHICLE"))
            except Exception:
                is_sm_vehicle = False
        if sm_mgr is not None and is_sm_vehicle and bool(getattr(sm_mgr, "is_ironstorm_spearhead", lambda: False)()):
            try:
                is_adeptus_astartes_vehicle = bool(sm_mgr.attached_unit_is_adeptus_astartes(root))
            except Exception:
                is_adeptus_astartes_vehicle = False
            if is_adeptus_astartes_vehicle:
                from ...utility.aura_utils import distance_between_models_bases_3d

                try:
                    target_models = list(root.get_attached_unit_models() or [])
                except Exception:
                    target_models = list(getattr(root, "models", []) or [])
                target_models = [m for m in list(target_models or []) if bool(getattr(m, "is_alive", True))]

                if target_models and army is not None:
                    try:
                        army_units = list(getattr(army, "units", []) or [])
                    except Exception:
                        army_units = []
                    seen_source_roots: set[str] = set()
                    adept_entries: list[dict] = []
                    for unit in list(army_units or []):
                        if unit is None:
                            continue
                        try:
                            source_root = unit.get_attached_unit_root()
                        except Exception:
                            source_root = unit
                        if source_root is None:
                            continue
                        source_root_id = str(get_entity_id(source_root) or "")
                        if source_root_id and source_root_id in seen_source_roots:
                            continue
                        if source_root_id:
                            seen_source_roots.add(source_root_id)
                        try:
                            if not source_root.is_alive() or not bool(getattr(source_root, "deployed", True)):
                                continue
                        except Exception:
                            continue
                        try:
                            if source_root.is_in_reserves() or source_root.is_embarked:
                                continue
                        except Exception:
                            pass
                        try:
                            members = list(source_root.get_attached_unit_members() or [])
                        except Exception:
                            members = [source_root]
                        if not members:
                            members = [source_root]
                        for source_unit in list(members or []):
                            if source_unit is None:
                                continue
                            source_sr = getattr(source_unit, "special_rules", None)
                            if not isinstance(source_sr, dict) or not source_sr.get("enhancement_adept_of_the_omnissiah"):
                                continue
                            source_bearer = getattr(source_unit, "_get_enhancement_bearer_model", lambda: None)()
                            if source_bearer is None or not bool(getattr(source_bearer, "is_alive", True)):
                                continue
                            try:
                                range_value = float(source_sr.get("enhancement_adept_of_the_omnissiah_range", 6) or 6)
                            except Exception:
                                range_value = 6.0
                            if range_value <= 0:
                                continue
                            in_range = False
                            for target_model in list(target_models or []):
                                try:
                                    if float(distance_between_models_bases_3d(source_bearer, target_model)) <= float(range_value) + 1e-6:
                                        in_range = True
                                        break
                                except Exception:
                                    continue
                            if not in_range:
                                continue
                            source_unit_id = str(get_entity_id(source_unit) or "")
                            if not source_unit_id:
                                continue
                            source_name = str(
                                source_sr.get("enhancement_adept_of_the_omnissiah_source", "") or "Adept of the Omnissiah"
                            ).strip() or "Adept of the Omnissiah"
                            usage_scope = str(
                                source_sr.get("enhancement_adept_of_the_omnissiah_usage", "") or "battle_round"
                            ).strip().lower()
                            if usage_scope not in {"battle_round", "battle"}:
                                usage_scope = "battle_round"
                            adept_entries.append(
                                {
                                    "source": source_name,
                                    "usage_scope": usage_scope,
                                    "usage_key": f"adept_of_the_omnissiah:{source_unit_id}",
                                    "source_unit_id": source_unit_id,
                                }
                            )
                    if adept_entries:
                        adept_entries.sort(key=lambda entry: str(entry.get("source_unit_id", "") or ""))
                        sources.extend(adept_entries)

        adm_mgr = getattr(army, "adeptus_mechanicus_detachments", None) if army is not None else None
        try:
            is_cohort_cybernetica = bool(adm_mgr and adm_mgr.is_cohort_cybernetica())
        except Exception:
            is_cohort_cybernetica = False
        if is_cohort_cybernetica:
            try:
                has_legio_cybernetica = bool(root.has_any_keyword("LEGIO CYBERNETICA"))
            except Exception:
                try:
                    has_legio_cybernetica = bool(root.has_keyword("LEGIO CYBERNETICA"))
                except Exception:
                    has_legio_cybernetica = False
            try:
                has_vehicle = bool(root.has_any_keyword("VEHICLE"))
            except Exception:
                try:
                    has_vehicle = bool(root.has_keyword("VEHICLE"))
                except Exception:
                    has_vehicle = False
            try:
                has_adeptus_mechanicus = bool(root.has_any_keyword("ADEPTUS MECHANICUS"))
            except Exception:
                try:
                    has_adeptus_mechanicus = bool(root.has_keyword("ADEPTUS MECHANICUS"))
                except Exception:
                    has_adeptus_mechanicus = False
            target_eligible = bool(has_legio_cybernetica or (has_vehicle and has_adeptus_mechanicus))
            if target_eligible:
                from ...utility.aura_utils import distance_between_models_bases_3d

                try:
                    target_models = list(root.get_attached_unit_models() or [])
                except Exception:
                    target_models = list(getattr(root, "models", []) or [])
                target_models = [m for m in list(target_models or []) if bool(getattr(m, "is_alive", True))]

                if target_models and army is not None:
                    try:
                        army_units = list(getattr(army, "units", []) or [])
                    except Exception:
                        army_units = []
                    seen_source_roots: set[str] = set()
                    necromechanic_entries: list[dict] = []
                    for unit in list(army_units or []):
                        if unit is None:
                            continue
                        try:
                            source_root = unit.get_attached_unit_root()
                        except Exception:
                            source_root = unit
                        if source_root is None:
                            continue
                        source_root_id = str(get_entity_id(source_root) or "")
                        if source_root_id and source_root_id in seen_source_roots:
                            continue
                        if source_root_id:
                            seen_source_roots.add(source_root_id)
                        try:
                            if not source_root.is_alive() or not bool(getattr(source_root, "deployed", True)):
                                continue
                        except Exception:
                            continue
                        try:
                            if source_root.is_in_reserves() or source_root.is_embarked:
                                continue
                        except Exception:
                            pass
                        try:
                            members = list(source_root.get_attached_unit_members() or [])
                        except Exception:
                            members = [source_root]
                        if not members:
                            members = [source_root]
                        for source_unit in list(members or []):
                            if source_unit is None:
                                continue
                            source_sr = getattr(source_unit, "special_rules", None)
                            if not isinstance(source_sr, dict) or not source_sr.get("enhancement_necromechanic"):
                                continue
                            source_bearer = getattr(source_unit, "_get_enhancement_bearer_model", lambda: None)()
                            if source_bearer is None or not bool(getattr(source_bearer, "is_alive", True)):
                                continue
                            try:
                                range_value = float(source_sr.get("enhancement_necromechanic_range", 12) or 12)
                            except Exception:
                                range_value = 12.0
                            if range_value <= 0:
                                continue
                            in_range = False
                            for target_model in list(target_models or []):
                                try:
                                    if float(distance_between_models_bases_3d(source_bearer, target_model)) <= float(range_value) + 1e-6:
                                        in_range = True
                                        break
                                except Exception:
                                    continue
                            if not in_range:
                                continue
                            source_unit_id = str(get_entity_id(source_unit) or "")
                            if not source_unit_id:
                                continue
                            source_name = str(source_sr.get("enhancement_necromechanic_source", "") or "Necromechanic").strip() or "Necromechanic"
                            usage_scope = str(source_sr.get("enhancement_necromechanic_usage", "") or "battle_round").strip().lower()
                            if usage_scope not in {"battle_round", "battle"}:
                                usage_scope = "battle_round"
                            necromechanic_entries.append(
                                {
                                    "source": source_name,
                                    "usage_scope": usage_scope,
                                    "usage_key": f"necromechanic:{source_unit_id}",
                                    "source_unit_id": source_unit_id,
                                }
                            )
                    if necromechanic_entries:
                        necromechanic_entries.sort(key=lambda entry: str(entry.get("source_unit_id", "") or ""))
                        sources.extend(necromechanic_entries)

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(sources)
        return list(sources)

    def get_target_hit_roll_penalty(
        self,
        attack_type: str,
        target_model: Optional['Model'] = None,
    ) -> tuple[int, tuple[str, ...]]:
        """
        Return total penalties to Hit rolls for attacks that target this unit/model.

        Supports strict patterns:
        - Each time an attack targets this unit/model, subtract 1 from the Hit roll.
        - Each time a melee/ranged attack targets this unit/model, subtract 1 from the Hit roll.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"

        model_key = getattr(target_model, "_id", None) if target_model is not None else "unit"
        cache_key = f"target_hit_penalty:{atype}:{model_key}"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        penalty = 0
        reasons: list[str] = []
        seen: set[str] = set()

        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict):
            entries = sr.get("bearer_unit_target_hit_penalties")
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        at = str(entry.get("attack_type", "any") or "any").lower()
                        val = int(entry.get("value", 1) or 1)
                        src = str(entry.get("source", "") or "Bearer unit ability").strip() or "Bearer unit ability"
                    elif isinstance(entry, (list, tuple)):
                        at = "any"
                        val = int(entry[0]) if entry else 1
                        src = str(entry[1]) if len(entry) > 1 else "Bearer unit ability"
                    else:
                        continue
                    if atype != "any" and at not in ("any", atype):
                        continue
                    key = f"bearer_unit:{src.lower()}"
                    if key in seen:
                        continue
                    seen.add(key)
                    penalty += int(val)
                    reasons.append(f"-{val} to hit from {src}")

        def _match_entries(entries, scope_key: str) -> None:
            nonlocal penalty
            for name, desc in entries:
                text_src = desc or name or ""
                if not text_src:
                    continue
                try:
                    key_text = self._normalize_rules_text(text_src).lower().strip()
                except Exception:
                    key_text = str(text_src or "").lower().strip()
                for rule in self._parse_attack_roll_rules_from_text(text_src):
                    if rule.scope != "defensive":
                        continue
                    if atype != "any" and rule.attack_type not in ("any", atype):
                        continue
                    reason_name = str(name or "Ability").strip() or "Ability"
                    key = key_text or reason_name.lower()
                    if key in seen:
                        break
                    for eff in rule.effects:
                        if eff.roll != "hit" or eff.kind != "sub":
                            continue
                        if eff.condition and not self._attack_condition_met(eff.condition, target=root, source_unit=root):
                            continue
                        val = int(eff.value or 0)
                        if val <= 0:
                            continue
                        seen.add(key)
                        penalty += val
                        reasons.append(f"-{val} to hit from {reason_name}")
                        break
                    if key in seen:
                        break
                reason_name = str(name or "Ability").strip() or "Ability"
                key = key_text or reason_name.lower()
                if key in seen:
                    continue
                try:
                    text_norm = self._normalize_rules_text(text_src or "")
                    text_norm = text_norm.replace("\u2019", "'").replace("\u0192?T", "'").strip()
                except Exception:
                    text_norm = str(text_src or "").strip()
                m = self._TARGET_HIT_ROLL_PENALTY_UNIT_RE.search(text_norm) or self._TARGET_HIT_ROLL_PENALTY_MODEL_RE.search(text_norm)
                if not m:
                    continue
                at = str(m.group("atype") or "any").strip().lower()
                if atype != "any" and at not in ("any", atype):
                    continue
                seen.add(key)
                penalty += 1
                reasons.append(f"-1 to hit from {reason_name}")

        unit_entries = []
        for ab in root._iter_active_possible_abilities():
            if isinstance(ab, str):
                unit_entries.append((ab, ab))
            else:
                unit_entries.append((getattr(ab, "name", "") or "", getattr(ab, "description", "") or ""))
        _match_entries(unit_entries, "unit")

        model = target_model
        if model is None:
            try:
                models = list(getattr(root, "models", []) or [])
            except Exception:
                models = []
            if len(models) == 1:
                model = models[0]
        if model is not None:
            model_entries = list(root._iter_model_specific_ability_entries(model))
            _match_entries(model_entries, "model")

        choice = ""
        try:
            choice_fn = getattr(self, "_dance_of_death_choice", None)
            if callable(choice_fn):
                choice = choice_fn()
        except Exception:
            choice = ""
        if choice in ("TRICKSTER", "ALL"):
            penalty += 1
            reasons.append("Dance of Death (Trickster's Grace): -1 to hit")

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = (int(penalty), tuple(reasons))
        return int(penalty), tuple(reasons)

    def _parse_phase_end_leadership_cp_gain_specs_from_text(self, ability_name: str, ability_desc: str) -> List[dict]:
        """Parse end-of-phase Leadership test CP gain abilities."""
        normalized = self._normalize_rules_text(ability_desc)
        if not normalized:
            return []
        norm = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
        norm = norm.lower()
        norm = re.sub(r"'s\b", "s", norm)
        norm = re.sub(r"[^a-z0-9]+", " ", norm)
        norm = re.sub(r"\s+", " ", norm).strip()
        m = self._PHASE_END_LEADERSHIP_CP_GAIN_RE.fullmatch(norm)
        if not m:
            return []
        token = str(m.group("cp") or "").strip().lower()
        try:
            cp = int(token)
        except Exception:
            cp = 1 if token == "one" else 1
        return [
            {
                "type": "phase_end_leadership_cp_gain",
                "cp": int(cp),
                "source_ability": ability_name or "",
            }
        ]
