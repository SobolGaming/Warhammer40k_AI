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
        cache_key = f"model_post_shoot_battleshock:{get_entity_id(model)}"
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
            source = str(name or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
            key = (source.lower(), infantry_only, 0, 0, False)
            if key in seen:
                continue
            seen.add(key)
            specs.append({"infantry_only": infantry_only, "source": source})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
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
                source = str(name or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
                key = (source.lower(), infantry_only, 0, 0, False)
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "infantry_only": infantry_only,
                        "exclude_monster_vehicle": bool(exclude_mv),
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
            except Exception:
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
            - psyker_penalty: int
        """
        if model is None:
            return []
        cache_key = f"model_opponent_command_phase_below_starting_battleshock:{get_entity_id(model)}"
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
            m = self._OPPONENT_COMMAND_PHASE_BELOW_STARTING_BATTLESHOCK_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            try:
                psyker_penalty = int(m.group("pen") or 0)
            except Exception:
                psyker_penalty = 0
            if range_value <= 0:
                continue
            psyker_penalty = max(0, int(psyker_penalty))
            source = str(name or "Opponent Command phase Battle-shock").strip() or "Opponent Command phase Battle-shock"
            key = (source.lower(), int(range_value), int(psyker_penalty))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "psyker_penalty": int(psyker_penalty),
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
            m = self._POST_SHOOT_OR_FIGHT_BATTLESHOCK_CONDITIONAL_RE.fullmatch(normalized)
            if not m:
                continue
            if str(m.group("subject") or "").strip().lower() != "model":
                continue
            try:
                pen = int(m.group("pen") or 0)
            except Exception:
                pen = 0
            try:
                rng = int(m.group("range") or 0)
            except Exception:
                rng = 0
            phrase = str(m.group("friendly") or "").strip()
            if pen <= 0 or rng <= 0:
                continue
            source = str(name or "Post-fight Battle-shock").strip() or "Post-fight Battle-shock"
            key = (
                source.lower(),
                "model_post_fight_battleshock",
                -int(pen),
                int(rng),
                phrase.lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "test_modifier_if_target_within_range": -int(pen),
                    "test_modifier_range": int(rng),
                    "test_modifier_friendly_keyword_phrase": phrase,
                    "source": source,
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
            m = self._FIGHT_PHASE_ENGAGEMENT_BATTLESHOCK_RE.fullmatch(normalized)
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
                bonus = int(m.group("attacks") or 0)
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
            move_dice = str(m.group("move") or "").strip().upper()
            if not move_dice:
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
                    "move_bonus_dice": move_dice,
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
            try:
                max_models = int(m.group("max") or 0)
            except Exception:
                max_models = 0
            if max_models <= 0:
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
        Unit-level rule: end of Fight phase, if the unit was eligible to fight this phase,
        it can make a Normal move (if not engaged) or a Fall Back move (if engaged) of D3+3".

        Returns list of specs with keys:
            - source: ability name
            - move_expr: movement roll expression string
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
            if not self._RAID_AND_RUN_RE.fullmatch(normalized):
                continue
            source = str(name or "Raid and Run").strip() or "Raid and Run"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "move_expr": "D3+3",
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
        """
        if model is None:
            return []
        cache_key = f"model_start_shooting_phase_visible_battleshock:{get_entity_id(model)}"
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
            m = self._START_SHOOTING_PHASE_VISIBLE_BATTLESHOCK_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            source = str(name or "Start of Shooting phase Battle-shock").strip() or "Start of Shooting phase Battle-shock"
            key = (source.lower(), int(range_value))
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "range": int(range_value)})

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
            m = self._SHOOTING_PHASE_EATER_PLAGUE_RE.fullmatch(normalized)
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
            source = str(name or "Eater Plague").strip() or "Eater Plague"
            key = (source.lower(), int(range_value), int(lone_range))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "lone_operative_range": int(lone_range),
                    "optional": True,
                    "self_mortal_on_one": "d3",
                    "target_mortal_on_mid": "d6",
                    "target_mortal_on_six": "d3+3",
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
        Model-specific rule: end of Movement phase, optionally select an enemy VEHICLE within range;
        that unit takes a Battle-shock test.

        Returns a list of specs with keys:
            - source: ability name
            - range: int
            - optional: bool
            - ability_key: str
        """
        if model is None:
            return []
        cache_key = f"model_movement_phase_end_vehicle_battleshock:{get_entity_id(model)}"
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
            if "end of your movement phase" not in normalized:
                continue
            if "battle shock test" not in normalized:
                continue
            if "enemy vehicle unit within" not in normalized:
                continue
            if "of this model" not in normalized:
                continue
            m = re.search(r"enemy vehicle unit within (?P<range>\d+) of this model", normalized)
            if m is None:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            optional = "you can select one enemy vehicle unit" in normalized
            source = str(name or "Enrage Machine Spirits").strip() or "Enrage Machine Spirits"
            ability_key_seed = self._normalize_keyword_phrase(source) or "movement_phase_end_vehicle_battleshock"
            ability_key = f"movement_phase_end_vehicle_battleshock:{ability_key_seed}"
            key = (source.lower(), int(range_value), bool(optional))
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "range": int(range_value),
                    "optional": bool(optional),
                    "ability_key": ability_key,
                }
            )

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
            m = self._START_SHOOTING_PHASE_CORRUPT_MACHINE_SPIRITS_RE.fullmatch(normalized)
            if not m:
                continue
            try:
                range_value = int(m.group("range") or 0)
            except Exception:
                range_value = 0
            if range_value <= 0:
                continue
            source = str(name or "Corrupt Machine Spirits").strip() or "Corrupt Machine Spirits"
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
        """
        if model is None:
            return []
        cache_key = f"model_start_opponent_shooting_phase_disrupt:{get_entity_id(model)}"
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
            key = (source.lower(), int(range_value), bool(mortal_on_one), bool(grant_ranged_hazardous))
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
                m = unit._FIGHT_PHASE_ENGAGEMENT_BATTLESHOCK_UNIT_RE.fullmatch(normalized)
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
            m = self._MALIGN_SACRIFICE_RE.fullmatch(normalized)
            if not m:
                continue
            model_name = str(m.group("model") or "dark disciple").strip() or "dark disciple"
            source = str(name or "Malign Sacrifice").strip() or "Malign Sacrifice"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source, "model_name": model_name})

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
            if "moved over" not in normalized:
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
            if "moved over" not in normalized or "mortal wound" not in normalized:
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
                if "moved over" not in normalized or "mortal wound" not in normalized:
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

        try:
            is_vehicle = bool(root.has_any_keyword("VEHICLE"))
        except Exception:
            try:
                is_vehicle = bool(root.has_keyword("VEHICLE"))
            except Exception:
                is_vehicle = False
        if is_vehicle:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
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
        if choice == "TRICKSTER":
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

