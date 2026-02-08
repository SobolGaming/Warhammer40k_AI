"""Auto-extracted Unit mixin methods from unit.py."""

from ._common import *


class KeywordsDetachmentsMixin:
    def has_firing_deck(self) -> Tuple[bool, int]:
        """Check if the unit has Firing Deck ability and return the number of weapons.
        
        Returns:
            Tuple[bool, int]: A tuple containing:
                - A boolean indicating if the unit has Firing Deck ability
                - The number of weapons that can fire from the deck (0 if no Firing Deck ability)
        """
        found, number_str = self._find_ability_with_patterns(["firing deck"], extract_value=True, value_pattern=r'(\d+)')
        if found:
            return True, int(number_str)
        return False, 0

    ###########################################################################
    ### Firing Deck (Transport) support
    ###########################################################################

    def clear_firing_deck_virtual_wargear(self) -> None:
        """
        Remove temporary "virtual" wargear added to the transport model to represent embarked weapons.

        This is used by the UI: the transport is treated as being equipped with those weapons
        for the duration of its shooting selection / resolution.
        """
        # Remove injected wargear from transport models
        vw = list(getattr(self, "_firing_deck_virtual_wargear", []) or [])
        if not vw:
            self._firing_deck_virtual_wargear = []
            self._firing_deck_virtual_sources = {}
            return
        for model in list(getattr(self, "models", []) or []):
            try:
                if not getattr(model, "is_alive", False):
                    continue
                if not hasattr(model, "wargear"):
                    continue
                model.wargear = [w for w in (model.wargear or []) if w not in vw]
            except Exception:
                continue
        self._firing_deck_virtual_wargear = []
        self._firing_deck_virtual_sources = {}

    def apply_firing_deck_virtual_wargear(self, selections: List[dict]) -> None:
        """
        Add temporary wargear/profile objects onto the transport model(s) so the existing
        shooting engine can validate and resolve attacks from the transport's position.

        `selections` entries are expected to include:
        - model: embarked Model providing the weapon
        - wargear: Wargear instance on the embarked model
        - profile: WargearProfile selected
        - profile_name: profile name string (optional)

        After this, `_firing_deck_virtual_sources[profile_clone.id] = [source_model]` is populated
        so shooting resolution can mark those embarked models as having shot.
        """
        import copy

        # Clear any previous injection first (safe even if none)
        self.clear_firing_deck_virtual_wargear()

        # Find at least one alive transport model to host these virtual weapons
        host_models = [m for m in (getattr(self, "models", []) or []) if getattr(m, "is_alive", False)]
        if not host_models:
            return
        host = host_models[0]

        class _VirtualWargear:
            def __init__(self, name: str, profile_obj):
                self.name = (name or "Firing Deck").replace("\u2019", "'")
                self.type = "ranged"
                self.profiles = {"default": profile_obj}

            def is_ranged(self) -> bool:
                return True

            def is_melee(self) -> bool:
                return False

        self._firing_deck_virtual_wargear = []
        self._firing_deck_virtual_sources = {}

        # Build one virtual wargear per selected embarked weapon (keeps them as individual entries)
        for s in list(selections or []):
            src_model = s.get("model")
            src_wargear = s.get("wargear")
            src_profile = s.get("profile")
            if src_model is None or src_wargear is None or src_profile is None:
                continue

            # Exclude ONE SHOT entirely for firing deck selection (explicit requirement)
            if src_profile.is_one_shot():
                continue

            # Clone the profile so we can safely re-parent it without mutating the source model's weapon.
            pclone = copy.copy(src_profile)
            pclone._id = str(uuid.uuid4())
            vname = f"{getattr(src_wargear, 'name', 'Weapon')} (Firing Deck)"
            vwg = _VirtualWargear(vname, pclone)
            pclone.parent_wargear = vwg

            try:
                host.wargear.append(vwg)
            except Exception:
                try:
                    host.wargear = list(getattr(host, "wargear", []) or []) + [vwg]
                except Exception:
                    continue

            self._firing_deck_virtual_wargear.append(vwg)
            self._firing_deck_virtual_sources[pclone.id] = [src_model]
    

    def _attached_leader_grants_fight_first_to_unit(self) -> bool:
        """Return True if any attached leader grants Fight First to the whole unit."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "attached_leader_unit_fight_first"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))

        leaders = list(getattr(root, "attached_leaders", []) or [])
        if not leaders:
            if not isinstance(cache, dict):
                cache = {}
            cache[cache_key] = False
            root._ability_cache = cache
            return False

        disallowed_tokens = (
            "until the end of",
            "at the start of",
            "start of the",
            "end of the",
            "once per battle",
            "each time",
            "battle round",
        )
        leading_start_re = re.compile(r"\bwhile this model is leading(?:s)?\b", re.IGNORECASE)
        unit_grant_re = re.compile(
            r"^(?:models in (?:that|this|the bearers) unit|(?:that|this|the bearers) unit)\s+"
            r"(?:has|have)\s+(?:the\s+)?fights?\s+first(?:\s+ability)?$",
            re.IGNORECASE,
        )

        def _normalize_sentence(value: str) -> str:
            cleaned = leader._normalize_rules_text(value or "")
            cleaned = cleaned.lower().replace("\u2019", "'").replace("\u0192?T", "'")
            cleaned = cleaned.replace("bearer's", "bearers")
            cleaned = re.sub(r"[^a-z0-9\s]+", " ", cleaned)
            return re.sub(r"\s+", " ", cleaned).strip()

        def _strip_leading_clause(norm: str) -> str:
            m = leading_start_re.search(norm or "")
            if not m:
                return norm
            tail = norm[m.start():]
            unit_pos = tail.find(" unit")
            if unit_pos == -1:
                return norm
            clause_len = unit_pos + len(" unit")
            stripped = (norm[:m.start()] + tail[clause_len:]).strip()
            return stripped

        found = False
        for leader in leaders:
            if leader is None:
                continue
            try:
                abilities = list(leader._iter_active_abilities())
            except Exception:
                abilities = []
            for ab in abilities:
                try:
                    desc = ab if isinstance(ab, str) else (
                        getattr(ab, "description", "") or getattr(ab, "name", "")
                    )
                except Exception:
                    desc = ""
                text_src = leader._strip_eligibility_prefix(desc or "")
                text = leader._normalize_rules_text(text_src or "")
                if not text:
                    continue
                sentences = [part.strip() for part in re.split(r"[.;]\s*", text) if part.strip()]
                for sentence in sentences:
                    norm = _normalize_sentence(sentence)
                    if not norm:
                        continue
                    if any(tok in norm for tok in disallowed_tokens):
                        continue
                    norm = _strip_leading_clause(norm)
                    if unit_grant_re.fullmatch(norm):
                        found = True
                        break
                if found:
                    break
            if found:
                break

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = bool(found)
        root._ability_cache = cache
        return bool(found)

    def has_fight_first(self) -> bool:
        """Check if the unit has Fight First ability.
        
        Fight First abilities can come from various sources:
        - Unit keywords like "Fight First"
        - Ability names like "Fights First", "Combat Reflexes", etc.
        - Descriptions containing fight first rules
        
        Returns:
            bool: True if the unit has any Fight First ability
        """
        # Enhancement temporary effects (fight phase) on the attached unit root.
        try:
            root = self.get_attached_unit_root()
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_fight_first_active"):
                return True
        except Exception:
            pass
        # Conditional Fight First (Empowered by Death).
        try:
            root = self.get_attached_unit_root()
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("empowered_by_death_active"):
                return True
        except Exception:
            pass
        # Use cached result if available
        if 'fight_first' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['fight_first']
        
        patterns = [
            "fight first", 
            "fights first", 
            "combat reflexes",
            "lightning reflexes",
            "swift strike",
            "martial prowess"
        ]

        def _is_empowered_by_death_text(value: str) -> bool:
            if not value:
                return False
            try:
                norm = self._normalize_rules_text(value or "")
            except Exception:
                return False
            if not norm:
                return False
            norm = norm.replace("\u2019", "'").replace("\u0192?T", "'")
            norm = re.sub(r"'s\b", "s", norm, flags=re.IGNORECASE)
            norm = re.sub(r"[^a-z0-9]+", " ", norm.lower())
            norm = re.sub(r"\s+", " ", norm).strip()
            return bool(self._EMPOWERED_BY_DEATH_RE.fullmatch(norm))

        found = False
        # Keyword-based Fight First.
        try:
            for keyword in list(getattr(self, "keywords", []) or []):
                low = str(keyword or "").lower()
                if any(pat in low for pat in patterns):
                    found = True
                    break
        except Exception:
            pass

        if not found:
            # Ability-based Fight First (exclude Empowered by Death conditional clause).
            try:
                for text in self._iter_active_ability_texts():
                    low = str(text or "").lower()
                    if not any(pat in low for pat in patterns):
                        continue
                    if _is_empowered_by_death_text(text):
                        continue
                    found = True
                    break
            except Exception:
                found = False

        if not found:
            found = self._attached_leader_grants_fight_first_to_unit()
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['fight_first'] = found
        
        return found

    def empowered_by_death_sources(self) -> list[str]:
        """Return source names for Empowered by Death style Fight First abilities."""
        cache_key = "empowered_by_death_sources"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache.get(cache_key) or [])

        sources: list[str] = []
        seen: set[str] = set()
        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text = str(desc or name or "")
            if not text:
                continue
            text = self._strip_eligibility_prefix(text)
            norm = self._normalize_rules_text(text)
            if not norm:
                continue
            norm = norm.replace("\u2019", "'").replace("\u0192?T", "'")
            norm = re.sub(r"'s\b", "s", norm, flags=re.IGNORECASE)
            norm = re.sub(r"[^a-z0-9]+", " ", norm.lower())
            norm = re.sub(r"\s+", " ", norm).strip()
            if not norm:
                continue
            if not self._EMPOWERED_BY_DEATH_RE.fullmatch(norm):
                continue
            source = str(name or "Empowered by Death").strip() or "Empowered by Death"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            sources.append(source)

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(sources)
        return list(sources)

    def has_empowered_by_death(self) -> bool:
        return bool(self.empowered_by_death_sources())

    def has_enhancement_fight_first_once_per_battle(self) -> bool:
        """Return True if this unit has a once-per-battle enhancement that grants Fight First."""
        sr = getattr(self, "special_rules", None)
        return bool(isinstance(sr, dict) and sr.get("enhancement_fight_first_once_per_battle"))

    def _enhancement_fight_first_once_key(self) -> str:
        enh = getattr(self, "enhancement", None)
        base = str(getattr(enh, "id", "") or "").strip()
        if not base:
            base = str(getattr(enh, "name", "") or "").strip()
        if not base:
            base = "fight_first"
        return f"enhancement_fight_first:{base}".lower()

    def has_used_unit_once_per_battle(self, key: str) -> bool:
        """Return True if this unit has consumed a named once-per-battle ability."""
        key = str(key or "").strip().lower()
        if not key:
            return False
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        used = sr.get("once_per_battle_used")
        if not isinstance(used, dict):
            return False
        return bool(used.get(key))

    def mark_unit_once_per_battle_used(self, key: str, *, ability_name: str = "") -> None:
        """Mark a named once-per-battle ability as used for this unit."""
        key = str(key or "").strip().lower()
        if not key:
            return
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        used = dict(sr.get("once_per_battle_used") or {})
        used[key] = True
        sr["once_per_battle_used"] = used
        if ability_name:
            sr.setdefault("once_per_battle_used_sources", {})[key] = str(ability_name or "").strip()
        self.special_rules = sr

    def _get_enhancement_bearer_model(self):
        sr = getattr(self, "special_rules", None)
        bearer_id = ""
        if isinstance(sr, dict):
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
        if bearer_id:
            for m in list(getattr(self, "models", []) or []):
                try:
                    mid = str(getattr(m, "id", getattr(m, "_id", "")) or "")
                except Exception:
                    mid = ""
                if mid and mid == bearer_id:
                    try:
                        if not getattr(m, "is_alive", True):
                            return None
                    except Exception:
                        return None
                    return m
        for m in list(getattr(self, "models", []) or []):
            try:
                if not getattr(m, "is_alive", True):
                    continue
            except Exception:
                continue
            return m
        return None

    def _get_enhancement_bearer_id(self) -> str:
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict):
            bearer_id = sr.get("enhancement_bearer_model_id")
            if bearer_id:
                return str(bearer_id)
        bearer = self._get_enhancement_bearer_model()
        if bearer is None:
            return ""
        return str(getattr(bearer, "id", getattr(bearer, "_id", "")) or "")

    def can_use_enhancement_fight_first(self) -> bool:
        if not self.has_enhancement_fight_first_once_per_battle():
            return False
        model = self._get_enhancement_bearer_model()
        if model is None:
            return False
        try:
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(self._enhancement_fight_first_once_key()):
                return False
        except Exception:
            return False
        return True

    def activate_enhancement_fight_first(self) -> bool:
        """Activate a once-per-battle enhancement to grant Fight First to the bearer's unit."""
        if not self.has_enhancement_fight_first_once_per_battle():
            return False
        model = self._get_enhancement_bearer_model()
        if model is None:
            return False
        key = self._enhancement_fight_first_once_key()
        try:
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return False
        except Exception:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if getattr(root, "special_rules", None) is None:
            root.special_rules = {}
        sr = root.special_rules
        sr["enhancement_fight_first_active"] = True
        sr["enhancement_fight_first_expires_phase"] = "FIGHT_PHASE"
        try:
            source = str(getattr(getattr(self, "enhancement", None), "name", "") or "").strip()
            if source:
                sr["enhancement_fight_first_source"] = source
        except Exception:
            pass
        getattr(model, "mark_used_once_per_battle", lambda _k, **_kw: None)(
            key,
            ability_name=str(getattr(getattr(self, "enhancement", None), "name", "") or "Fight First Enhancement"),
            source="enhancement",
        )
        root.special_rules = sr
        return True

    def _seductive_gambit_active(self) -> bool:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        if mgr is None or not getattr(mgr, "is_legion_of_excess_detachment", lambda: False)():
            return False
        try:
            sr = getattr(self, "special_rules", None)
            return isinstance(sr, dict) and bool(sr.get("seductive_gambit_active"))
        except Exception:
            return False

    def has_fight_on_death(self) -> bool:
        """Check if the unit has a Fight on Death style ability.

        This is implemented as a pattern match against keywords / abilities text.
        The actual resolution is handled at model death time (see `_handle_model_destroyed`).
        """
        if 'fight_on_death' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['fight_on_death']

        found, _ = self._find_ability_with_patterns([
            "fight on death",
            "fights on death",
            "fight when destroyed",
            "fight when this model is destroyed",
            "fight before removing",
            "fight before it is removed",
            "fight before it is removed from play",
            "fight when slain",
            "fight when killed",
            "last stand",
        ])

        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['fight_on_death'] = found
        return found

    def get_melee_fight_on_death_after_attacks_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time a model in this unit is destroyed by a melee attack, if that model has not fought this phase,
        roll one D6. On a 3+, do not remove it from play; that destroyed model can fight after the attacking unit
        has finished making its attacks, and is then removed from play."
        """
        cache_key = f"melee_fight_on_death_after_attacks:{get_entity_id(model) if model is not None else 'unit'}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            for name, desc in self._iter_ability_entries_for_rules(model=model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower().replace("\u2019", "'")
                if "destroyed by a melee attack" not in low:
                    continue
                if "has not fought this phase" not in low:
                    continue
                if "roll one d6" not in low:
                    continue
                if "do not remove" not in low:
                    continue
                if (
                    "can fight after the attacking unit has finished making its attacks" not in low
                    and "can fight after the attacking model's unit has finished making its attacks" not in low
                ):
                    continue
                m = re.search(r"on a (\d+)\+?", low)
                if not m:
                    continue
                threshold = int(m.group(1))
                if threshold < 2 or threshold > 6:
                    continue
                source = str(name or "Fight on death").strip() or "Fight on death"
                rule = {"threshold": threshold, "source": source}
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def has_shoot_on_death(self) -> bool:
        """Check if the unit has a Shoot on Death style ability.

        Implemented as a pattern match; resolution occurs at model death time.
        """
        if 'shoot_on_death' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['shoot_on_death']

        found, _ = self._find_ability_with_patterns([
            "shoot on death",
            "shoots on death",
            "shoot when destroyed",
            "shoot when this model is destroyed",
            "shoot before removing",
            "shoot before it is removed",
            "shoot before it is removed from play",
            "shoot when slain",
            "shoot when killed",
        ])

        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['shoot_on_death'] = found
        return found

    def has_despoilers(self) -> bool:
        """Return True if this unit has the Despoilers ability."""
        if "despoilers" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["despoilers"])
        found, _ = self._find_ability_with_patterns(["despoilers"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["despoilers"] = bool(found)
        return bool(found)

    def has_unholy_bloodshed(self) -> bool:
        """Return True if this unit has the Unholy Bloodshed ability."""
        if "unholy_bloodshed" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["unholy_bloodshed"])
        found, _ = self._find_ability_with_patterns(["unholy bloodshed"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["unholy_bloodshed"] = bool(found)
        return bool(found)

    def get_hysterical_frenzy_fight_on_death_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for passive Hysterical Frenzy (no roll):
        "Each time a model in this model's unit is destroyed, if that model has not fought this phase,
        do not remove it from play. The destroyed model can fight after the attacking unit has finished
        making its attacks, and is then removed from play."
        """
        cache_key = f"hysterical_frenzy_passive:{get_entity_id(model) if model is not None else 'unit'}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            for name, desc in self._iter_ability_entries_for_rules(model=model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower().replace("\u2019", "'")
                low = re.sub(r"[^a-z0-9]+", " ", low)
                low = re.sub(r"\s+", " ", low).strip()
                if not self._HYSTERICAL_FRENZY_PASSIVE_RE.fullmatch(low):
                    continue
                source = str(name or "Hysterical Frenzy").strip() or "Hysterical Frenzy"
                rule = {"source": source}
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def has_blood_surge(self) -> bool:
        """Check if the unit has the Blood Surge datasheet ability."""
        if 'blood_surge' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['blood_surge']

        found, _ = self._find_ability_with_patterns(["blood surge"])
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['blood_surge'] = found
        return found

    def has_brazen_fury(self) -> bool:
        """Check if the unit has the Brazen Fury detachment ability (Possessed Slaughterband)."""
        if 'brazen_fury' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['brazen_fury']
        applies = False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if mgr is not None and callable(getattr(mgr, "brazen_fury_applies", None)):
            try:
                applies = bool(mgr.brazen_fury_applies(self))
            except Exception:
                applies = False
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['brazen_fury'] = applies
        return applies

    def has_horde_move(self) -> bool:
        """Check if the unit has a Horde Move ability."""
        if 'horde_move' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['horde_move']

        found, _ = self._find_ability_with_patterns(["horde move"])
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['horde_move'] = found
        return found

    def get_victim_selection_rule(self) -> Optional[dict]:
        """
        Detect abilities with text like:
        "At the start of the first battle round, select one unit from your opponent's army to be this model's victim.
        Each time this model makes an attack that targets its victim, you can re-roll the Wound roll.
        Each time this model's victim is destroyed, select one new enemy unit to be this model's victim."

        Returns a rule dict with:
            - source: ability name
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "victim_selection_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        def _matches(text: str) -> bool:
            if not text:
                return False
            if "start of the first battle round" not in text:
                return False
            if "be this model s victim" not in text:
                return False
            if "victim is destroyed" not in text:
                return False
            if "select one new enemy unit" not in text:
                return False
            if "targets its victim" not in text and "targets that victim" not in text:
                return False
            if "re roll the wound roll" not in text and "reroll the wound roll" not in text:
                return False
            return True

        rule = None
        seen = set()
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
                key = (str(name or "").strip().lower(), normalized)
                if key in seen:
                    continue
                seen.add(key)
                if not _matches(normalized):
                    continue
                source = str(name or "Victim selection").strip() or "Victim selection"
                rule = {"source": source}
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def get_prey_selection_rule(self) -> Optional[dict]:
        """
        Detect abilities with text like:
        "At the start of the first battle round, select one enemy unit to be this model's prey.
        Each time a model in this model's unit makes a melee attack that targets its prey, you can re-roll the Wound roll.
        Each time this model's prey is destroyed, select one new enemy unit to be this model's prey."

        Also supports variants:
        - Hit + Wound re-rolls vs prey (no melee restriction).
        - Lethal Hits vs prey.

        Returns a rule dict with:
            - source: ability name
            - reroll_hit: bool
            - reroll_wound: bool
            - melee_only: bool
            - keyword: optional keyword bonus (e.g., "LETHAL HITS")
            - repick_on_destroyed: bool
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "prey_selection_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        def _norm(text: str) -> str:
            if not text:
                return ""
            text = self._normalize_rules_text(text)
            text = text.replace("\u2019", "'").replace("\u0192?T", "'")
            text = text.lower()
            text = re.sub(r"[^a-z0-9]+", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text

        def _has_phrase(text: str, *phrases: str) -> bool:
            for phrase in phrases:
                if phrase and phrase in text:
                    return True
            return False

        rule = None
        seen = set()
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
                normalized = _norm(text_src)
                if not normalized:
                    continue
                key = (str(name or "").strip().lower(), normalized)
                if key in seen:
                    continue
                seen.add(key)

                if "start of the first battle round" not in normalized:
                    continue
                if "select one enemy unit to be this model s prey" not in normalized:
                    continue

                repick_on_destroyed = (
                    "prey is destroyed" in normalized
                    and "select one new enemy unit" in normalized
                )

                # Pattern: melee wound re-roll vs prey (unit-wide).
                if (
                    _has_phrase(normalized, "melee attack")
                    and _has_phrase(normalized, "targets its prey", "targets that prey")
                    and _has_phrase(normalized, "re roll the wound roll", "reroll the wound roll")
                ):
                    source = str(name or "Prey selection").strip() or "Prey selection"
                    rule = {
                        "source": source,
                        "reroll_hit": False,
                        "reroll_wound": True,
                        "melee_only": True,
                        "repick_on_destroyed": bool(repick_on_destroyed),
                    }
                    break

                # Pattern: hit + wound re-roll vs prey (no melee restriction).
                if (
                    _has_phrase(normalized, "makes an attack")
                    and _has_phrase(normalized, "targets its prey", "targets that prey")
                    and _has_phrase(normalized, "re roll the hit roll", "reroll the hit roll")
                    and _has_phrase(normalized, "re roll the wound roll", "reroll the wound roll")
                ):
                    source = str(name or "Prey selection").strip() or "Prey selection"
                    rule = {
                        "source": source,
                        "reroll_hit": True,
                        "reroll_wound": True,
                        "melee_only": False,
                        "repick_on_destroyed": bool(repick_on_destroyed),
                    }
                    break

                # Pattern: Lethal Hits vs prey (unit-wide).
                if (
                    "lethal hits" in normalized
                    and _has_phrase(normalized, "weapons equipped by models in this model s unit")
                    and _has_phrase(normalized, "targeting this model s prey", "targets its prey", "targets that prey")
                ):
                    source = str(name or "Prey selection").strip() or "Prey selection"
                    rule = {
                        "source": source,
                        "reroll_hit": False,
                        "reroll_wound": False,
                        "melee_only": False,
                        "keyword": "LETHAL HITS",
                        "repick_on_destroyed": bool(repick_on_destroyed),
                    }
                    break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def get_loping_speed_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Once per turn, when an enemy unit ends a Normal, Advance or Fall Back move within 9\" of this unit,
        if this unit is not within Engagement Range of one or more enemy units, it can make a Normal move of up to D6\"."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "loping_speed_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        seen = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                key = (str(name or "").strip().lower(), u._normalize_rules_text(text_src).lower())
                if key in seen:
                    continue
                seen.add(key)
                text = u._normalize_rules_text(self._strip_eligibility_prefix(text_src))
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                m = self._ENEMY_MOVE_REACTIVE_D6_RE.search(text)
                if not m:
                    continue
                try:
                    rng = int(m.group("range") or 0)
                except Exception:
                    rng = 0
                if rng <= 0:
                    rng = 9
                move_token = str(m.group("move") or "").strip().lower()
                source = str(name or "Loping Speed").strip() or "Loping Speed"
                rule = {"range": int(rng), "source": source}
                if move_token:
                    if move_token.isdigit():
                        try:
                            move_value = int(move_token)
                        except Exception:
                            move_value = 0
                        if move_value > 0:
                            rule["max_distance"] = int(move_value)
                    else:
                        rule["distance_roll"] = move_token.upper()
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def get_setup_reactive_shoot_or_charge_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "At the end of your opponent's Movement phase, you can select one enemy unit that was set up on the battlefield
        within 12\" of this model; this model can then either shoot at that unit (if eligible) or declare a charge
        against that unit (no Charge bonus)."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "setup_reactive_shoot_or_charge_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        seen = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                key = (str(name or "").strip().lower(), u._normalize_rules_text(text_src).lower())
                if key in seen:
                    continue
                seen.add(key)
                text = u._normalize_rules_text(self._strip_eligibility_prefix(text_src))
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                m = self._SETUP_REACTIVE_SHOOT_CHARGE_RE.search(text)
                if not m:
                    continue
                try:
                    rng = int(m.group("range") or 0)
                except Exception:
                    rng = 0
                if rng <= 0:
                    rng = 12
                source = str(name or "Reactive Response").strip() or "Reactive Response"
                rule = {"range": int(rng), "source": source}
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def get_dark_ritual_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Once per battle, in your Command phase, if this unit contains a CULT DEMAGOGUE model, it can use this ability.
        If it does, until the end of the turn, this unit can declare a charge in a turn in which it Advanced and each
        time a model in this unit makes an attack, add 1 to the Hit roll and add 1 to the Wound roll."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "dark_ritual_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        seen = set()
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
                key = (str(name or "").strip().lower(), u._normalize_rules_text(text_src).lower())
                if key in seen:
                    continue
                seen.add(key)
                text = u._normalize_rules_text(self._strip_eligibility_prefix(text_src))
                if not text:
                    continue
                normalized = text.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "once per battle" not in normalized:
                    continue
                if "command phase" not in normalized:
                    continue
                if "cult demagogue" not in normalized:
                    continue
                if "declare a charge" not in normalized or "advance" not in normalized:
                    continue
                if "add 1 to the hit roll" not in normalized:
                    continue
                if "add 1 to the wound roll" not in normalized:
                    continue
                if "end of the turn" not in normalized:
                    continue
                source = str(name or "Dark Ritual").strip() or "Dark Ritual"
                rule = {"source": source, "ability_key": "dark_ritual"}
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def get_traitor_enforcer_overwatch_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Once per turn, while this unit is leading a unit and contains a TRAITOR ENFORCER model, you can target that unit
        with the Fire Overwatch Stratagem for 0CP, and can do so even if you have already targeted a different unit from
        your army with that Stratagem this turn. Each time you use this ability, one Bodyguard model in that unit is destroyed."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "traitor_enforcer_overwatch_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        try:
            leaders = list(getattr(root, "attached_leaders", []) or [])
        except Exception:
            leaders = []

        for leader in leaders:
            if leader is None:
                continue
            try:
                if not bool(getattr(leader, "is_attached_leader", False)):
                    continue
            except Exception:
                continue
            try:
                alive = getattr(leader, "is_alive", None)
                if callable(alive) and not alive():
                    continue
            except Exception:
                pass
            try:
                has_traitor = leader._unit_contains_model_named("Traitor Enforcer")
            except Exception:
                has_traitor = False
            for name, desc in leader._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text = leader._normalize_rules_text(leader._strip_eligibility_prefix(text_src))
                if not text:
                    continue
                norm = text.replace("\u2019", "'").replace("\u0192?T", "'")
                norm = norm.lower()
                norm = re.sub(r"'s\b", "s", norm)
                norm = re.sub(r"[^a-z0-9]+", " ", norm)
                norm = re.sub(r"\s+", " ", norm).strip()
                if "fire overwatch" not in norm or "stratagem" not in norm:
                    continue
                if "0cp" not in norm:
                    continue
                if "once per turn" not in norm:
                    continue
                if "bodyguard" not in norm or "destroyed" not in norm:
                    continue
                if "leading" not in norm:
                    continue
                if "traitor enforcer" not in norm and not has_traitor:
                    continue
                source = str(name or "Brutal Example").strip() or "Brutal Example"
                rule = {
                    "source": source,
                    "ability_key": "brutal_example_overwatch",
                }
                try:
                    leader_id = get_entity_id(leader)
                except Exception:
                    leader_id = None
                if leader_id:
                    rule["leader_id"] = str(leader_id)
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def get_beast_handler_heroic_intervention_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "While this model is leading a unit... once per battle, you can target that unit with the Heroic Intervention
        Stratagem for 0CP, and can do so even if you have already used that Stratagem on a different unit this phase."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "beast_handler_heroic_intervention_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        try:
            items = list(root._iter_attached_leader_leading_abilities())
        except Exception:
            items = []

        for ab, leader in items:
            try:
                name = str(getattr(ab, "name", "") or "")
                desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            text_src = desc or name or ""
            if not text_src:
                continue
            text = root._normalize_rules_text(root._strip_eligibility_prefix(text_src))
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if "heroic intervention" not in norm or "stratagem" not in norm:
                continue
            if "0cp" not in norm:
                continue
            if "once per battle" not in norm:
                continue
            if "leading" not in norm:
                continue
            source = str(name or "Beast Handler").strip() or "Beast Handler"
            rule = {"source": source, "ability_key": "beast_handler_heroic_intervention"}
            try:
                leader_id = get_entity_id(leader)
            except Exception:
                leader_id = None
            if leader_id:
                rule["leader_id"] = str(leader_id)
            break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def get_fortification_cover_rule(self) -> Optional[dict]:
        """
        Return rule info for Fortification cover abilities like:
        "Each time a ranged attack is allocated to a model, if that model is not fully visible to every model in the attacking unit
        because of this FORTIFICATION, that model has the Benefit of Cover against that attack."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "fortification_cover_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        try:
            if not root.has_any_keyword("Fortification"):
                root._ability_cache[cache_key] = None
                return None
        except Exception:
            pass

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
                if not unit._FORTIFICATION_COVER_RE.fullmatch(normalized):
                    continue
                source = str(name or "Fortification Cover").strip() or "Fortification Cover"
                rule = {"source": source}
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def can_use_beast_handler_heroic_intervention(self, game=None) -> bool:
        """Return True if Beast Handler can grant Heroic Intervention for 0CP (once per battle)."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            rule = root.get_beast_handler_heroic_intervention_rule()
        except Exception:
            rule = None
        if not rule:
            return False
        ability_key = str(rule.get("ability_key") or "beast_handler_heroic_intervention").strip().lower()
        if ability_key and root.has_used_unit_once_per_battle(ability_key):
            return False
        leader_id = str(rule.get("leader_id", "") or "")
        if leader_id:
            try:
                leaders = list(getattr(root, "attached_leaders", []) or [])
            except Exception:
                leaders = []
            found = False
            for leader in leaders:
                try:
                    if str(get_entity_id(leader) or "") != leader_id:
                        continue
                    if not bool(getattr(leader, "is_attached_leader", False)):
                        continue
                    alive = getattr(leader, "is_alive", None)
                    if callable(alive) and not alive():
                        continue
                    found = True
                    break
                except Exception:
                    continue
            if not found:
                return False
        return True

    def get_strategic_reserves_round_bonus_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "If this unit starts the game in Strategic Reserves, it can be set up in the Reinforcements step of your first,
        second or third Movement phase, regardless of any mission rules. If this unit is in Strategic Reserves, for the
        purposes of setting up this unit on the battlefield, treat the current battle round number as being one higher
        than it actually is."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "strategic_reserves_round_bonus_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        seen = set()
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
                key = (str(name or "").strip().lower(), u._normalize_rules_text(text_src).lower())
                if key in seen:
                    continue
                seen.add(key)
                text = u._normalize_rules_text(self._strip_eligibility_prefix(text_src))
                if not text:
                    continue
                normalized = text.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if "starts the game in strategic reserves" not in normalized:
                    continue
                if "reinforcements step" not in normalized:
                    continue
                if "first second or third" not in normalized or "movement phase" not in normalized:
                    continue
                if "battle round number as being one higher" not in normalized and "battle round as being one higher" not in normalized:
                    continue
                source = str(name or "Strategic Reserves").strip() or "Strategic Reserves"
                rule = {"source": source, "round_bonus": 1, "ability_key": "strategic_reserves_round_bonus"}
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def _strategic_reserves_round_bonus(self) -> int:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            rule = root.get_strategic_reserves_round_bonus_rule()
        except Exception:
            rule = None
        if not rule:
            return 0
        try:
            started = bool(getattr(root, "_started_in_reserves", False))
        except Exception:
            started = False
        if not started:
            return 0
        try:
            if not bool(getattr(root, "is_in_strategic_reserves", lambda: False)()):
                return 0
        except Exception:
            return 0
        try:
            bonus = int(rule.get("round_bonus", 1) or 0)
        except Exception:
            bonus = 0
        return max(0, bonus)

    def get_strategic_reserves_setup_turn(self, *, game=None, current_turn: Optional[int] = None) -> int:
        if current_turn is None:
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
                current_turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                current_turn = 0
        try:
            bonus = int(self._strategic_reserves_round_bonus() or 0)
        except Exception:
            bonus = 0
        return int(current_turn) + max(0, int(bonus))

    def _loping_speed_turn_key(self, game=None) -> str:
        if game is None:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        owner = str(getattr(current_player, "name", "") or "")
        return f"{br}:{owner}"

    def _traitor_enforcer_overwatch_turn_key(self, game=None) -> str:
        if game is None:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        owner = str(getattr(current_player, "id", "") or "") or str(getattr(current_player, "name", "") or "")
        return f"{br}:{owner}"

    def traitor_enforcer_overwatch_used_this_turn(self, game=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._traitor_enforcer_overwatch_turn_key(game)
        return str(sr.get("traitor_enforcer_overwatch_used_turn_key", "")) == key

    def mark_traitor_enforcer_overwatch_used(self, game=None, *, source: str = "") -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["traitor_enforcer_overwatch_used_turn_key"] = self._traitor_enforcer_overwatch_turn_key(game)
        if source:
            sr["traitor_enforcer_overwatch_used_source"] = str(source or "").strip()
        root.special_rules = sr

    def can_use_traitor_enforcer_overwatch(self, game=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        try:
            if not root.is_alive() or not getattr(root, "deployed", False):
                return False
        except Exception:
            return False
        try:
            if root.is_in_reserves():
                return False
        except Exception:
            pass
        try:
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                return False
        except Exception:
            pass
        rule = root.get_traitor_enforcer_overwatch_rule()
        if not rule:
            return False
        if root.traitor_enforcer_overwatch_used_this_turn(game):
            return False
        try:
            leaders = list(getattr(root, "attached_leaders", []) or [])
        except Exception:
            leaders = []
        if not any(bool(getattr(l, "is_attached_leader", False)) for l in leaders if l is not None):
            return False
        return True

    def _setup_reactive_shoot_or_charge_turn_key(self, game=None) -> str:
        if game is None:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        try:
            owner = str(getattr(current_player, "id", "") or "")
        except Exception:
            owner = ""
        phase = ""
        try:
            phase = str(getattr(getattr(game, "phase", None), "name", "") or "")
        except Exception:
            phase = ""
        return f"{br}:{owner}:{phase}"

    def setup_reactive_shoot_or_charge_used_this_phase(self, game=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._setup_reactive_shoot_or_charge_turn_key(game)
        return str(sr.get("setup_reactive_shoot_or_charge_used_key", "")) == key

    def mark_setup_reactive_shoot_or_charge_used(self, game=None) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["setup_reactive_shoot_or_charge_used_key"] = self._setup_reactive_shoot_or_charge_turn_key(game)
        root.special_rules = sr

    def record_setup_reactive_shoot_or_charge_candidate(self, enemy_unit, game=None) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if enemy_unit is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        key = self._setup_reactive_shoot_or_charge_turn_key(game)
        if str(sr.get("setup_reactive_shoot_or_charge_candidates_key", "")) != key:
            sr["setup_reactive_shoot_or_charge_candidates"] = []
        sr["setup_reactive_shoot_or_charge_candidates_key"] = key
        try:
            enemy_id = get_entity_id(enemy_unit)
        except Exception:
            enemy_id = None
        if not enemy_id:
            root.special_rules = sr
            return
        candidates = list(sr.get("setup_reactive_shoot_or_charge_candidates", []) or [])
        if enemy_id not in candidates:
            candidates.append(enemy_id)
        sr["setup_reactive_shoot_or_charge_candidates"] = candidates
        root.special_rules = sr

    def get_setup_reactive_shoot_or_charge_candidates(self, game=None) -> list[str]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return []
        key = self._setup_reactive_shoot_or_charge_turn_key(game)
        if str(sr.get("setup_reactive_shoot_or_charge_candidates_key", "")) != key:
            return []
        return list(sr.get("setup_reactive_shoot_or_charge_candidates", []) or [])

    def clear_setup_reactive_shoot_or_charge_candidates(self, game=None) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        key = self._setup_reactive_shoot_or_charge_turn_key(game)
        if str(sr.get("setup_reactive_shoot_or_charge_candidates_key", "")) != key:
            return
        sr.pop("setup_reactive_shoot_or_charge_candidates", None)
        sr.pop("setup_reactive_shoot_or_charge_candidates_key", None)
        root.special_rules = sr

    def can_setup_reactive_shoot_or_charge(
        self,
        game=None,
        game_map=None,
        *,
        enemy_unit=None,
        range_override: Optional[int] = None,
    ) -> bool:
        rule = self.get_setup_reactive_shoot_or_charge_rule()
        if not rule:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        if not root.is_alive() or not getattr(root, "deployed", False):
            return False
        try:
            if root.is_in_reserves():
                return False
        except Exception:
            pass
        try:
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                return False
        except Exception:
            pass
        if root.setup_reactive_shoot_or_charge_used_this_phase(game):
            return False
        if enemy_unit is not None and game_map is not None:
            try:
                rng = int(range_override or rule.get("range", 12) or 12)
            except Exception:
                rng = 12
            try:
                from ...utility.aura_utils import unit_within_range_of_unit
                if not unit_within_range_of_unit(root, enemy_unit, float(rng), use_attached_aggregate=True):
                    return False
            except Exception:
                return False
        return True

    def loping_speed_used_this_turn(self, game=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._loping_speed_turn_key(game)
        return str(sr.get("loping_speed_used_turn_key", "")) == key

    def mark_loping_speed_used(self, game=None) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["loping_speed_used_turn_key"] = self._loping_speed_turn_key(game)
        root.special_rules = sr

    def can_loping_speed(self, game=None, game_map=None, *, moving_unit=None, range_override: Optional[int] = None) -> bool:
        rule = self.get_loping_speed_rule()
        if not rule:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        if not root.is_alive() or not getattr(root, "deployed", False):
            return False
        try:
            if root.is_in_reserves():
                return False
        except Exception:
            pass
        try:
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                return False
        except Exception:
            pass
        if root.loping_speed_used_this_turn(game):
            return False
        if game_map is None:
            try:
                game_map = getattr(game, "map", None)
            except Exception:
                game_map = None
        if game_map is not None:
            try:
                for enemy in game_map.get_enemy_units(root):
                    if game_map.is_within_engagement_range(root, enemy):
                        return False
            except Exception:
                pass
        if moving_unit is not None and game_map is not None:
            try:
                rng = int(range_override or rule.get("range", 9) or 9)
            except Exception:
                rng = 9
            try:
                dist = float(game_map.get_distance_between_units(root, moving_unit))
            except Exception:
                dist = None
            if dist is None or dist > float(rng) + 1e-6:
                return False
        return True

    def has_frenzy(self) -> bool:
        """True if this unit has the Helbrute-style Frenzy ability (shoot or fight vs the triggering unit)."""
        if 'frenzy' in getattr(self, '_ability_cache', {}):
            return bool(self._ability_cache['frenzy'])

        found = False
        try:
            for name, desc in self._iter_ability_entries_for_rules(model=None):
                text = self._normalize_rules_text(f"{name} {desc}").lower()
                if "frenzy" not in text:
                    continue
                if "can either shoot or fight" not in text:
                    continue
                if "only target that enemy unit" not in text:
                    continue
                found = True
                break
        except Exception:
            found = False

        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['frenzy'] = bool(found)
        return bool(found)

    def has_furious_onslaught(self, model: Optional['Model'] = None) -> bool:
        """True if this model has the Furious Onslaught datasheet ability."""
        if model is None:
            return False
        cache_key = f"furious_onslaught:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])

        found = False
        try:
            for name, desc in self._iter_model_specific_ability_entries(model):
                text = self._normalize_rules_text(name or "")
                if text and "furious onslaught" in text.lower():
                    found = True
                    break
                text = self._normalize_rules_text(desc or "")
                if text and "furious onslaught" in text.lower():
                    found = True
                    break
        except Exception:
            found = False

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def get_closest_enemy_hit_reroll_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time a model in this unit makes a ranged attack that targets the closest enemy unit,
        you can re-roll the Hit roll."
        """
        if model is None:
            return None
        cache_key = f"closest_enemy_hit_reroll_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            for name, desc in self._iter_ability_entries_for_rules(model=model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower()
                if "ranged attack" not in low:
                    continue
                if not re.search(r"closest\s+(?:eligible\s+)?enemy\s+unit", low) and not re.search(
                    r"closest\s+eligible\s+(?:target|unit)", low
                ):
                    continue
                if "hit roll" not in low:
                    continue
                if ("re-roll" not in low) and ("reroll" not in low):
                    continue
                if not re.search(r"re-?roll\s+the\s+hit\s+roll", low) and not re.search(
                    r"re-?roll\s+the\s+hit\s+roll\s+instead", low
                ):
                    continue
                source = str(name or "Closest enemy unit").strip() or "Closest enemy unit"
                rule = {"source": source}
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_closest_monster_vehicle_reroll_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time this model makes a ranged attack that targets the closest eligible MONSTER or VEHICLE target within 18\",
        you can re-roll the Wound roll and you can re-roll the Damage roll."
        """
        if model is None:
            return None
        cache_key = f"closest_monster_vehicle_reroll_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            for name, desc in self._iter_model_specific_ability_entries(model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower()
                if "ranged attack" not in low:
                    continue
                if "closest eligible" not in low:
                    continue
                if "monster" not in low or "vehicle" not in low:
                    continue
                if ("re-roll" not in low) and ("reroll" not in low):
                    continue
                m = re.search(r"within\s+(\d+)\s*(?:\"|inches)", low)
                if not m:
                    continue
                allow_wound = bool(re.search(r"re-?roll\s+the\s+wound\s+roll", low))
                allow_damage = bool(re.search(r"re-?roll\s+the\s+damage\s+roll", low))
                if not (allow_wound or allow_damage):
                    continue
                try:
                    rng = int(m.group(1))
                except Exception:
                    continue
                source = str(name or "Closest eligible MONSTER/VEHICLE").strip() or "Closest eligible MONSTER/VEHICLE"
                rule = {
                    "range": rng,
                    "reroll_wound": bool(allow_wound),
                    "reroll_damage": bool(allow_damage),
                    "source": source,
                }
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_monster_vehicle_reroll_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "In your Shooting phase, each time a model in this unit makes a ranged attack that targets a MONSTER or VEHICLE unit,
        you can re-roll the Hit roll, you can re-roll the Wound roll and you can re-roll the Damage roll."
        Also supports model-worded variants such as:
        "Each time a ranged attack made by this model is allocated to a MONSTER or VEHICLE model, you can re-roll the Damage roll."
        """
        if model is None:
            return None
        cache_key = f"monster_vehicle_reroll_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            for name, desc in self._iter_ability_entries_for_rules(model=model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower().replace("\u2019", "'")
                if "ranged attack" not in low:
                    continue
                if "monster" not in low or "vehicle" not in low:
                    continue
                if "closest" in low:
                    continue
                model_attack_phrase = bool(
                    ("each time a model in this unit makes a ranged attack" in low)
                    or ("each time this model makes a ranged attack" in low)
                    or ("each time a ranged attack made by this model" in low)
                )
                if not model_attack_phrase:
                    continue
                if not re.search(
                    r"(?:targets?|allocated to) (?:an? )?(?:enemy )?monster or vehicle (?:unit|model)",
                    low,
                ):
                    continue
                if ("re-roll" not in low) and ("reroll" not in low):
                    continue
                allow_hit = bool(re.search(r"re-?roll the hit roll", low))
                allow_wound = bool(re.search(r"re-?roll the wound roll", low))
                allow_damage = bool(re.search(r"re-?roll the damage roll", low))
                if not (allow_hit or allow_wound or allow_damage):
                    continue
                source = str(name or "Monster/Vehicle rerolls").strip() or "Monster/Vehicle rerolls"
                rule = {
                    "reroll_hit": bool(allow_hit),
                    "reroll_wound": bool(allow_wound),
                    "reroll_damage": bool(allow_damage),
                    "requires_shooting_phase": ("shooting phase" in low),
                    "source": source,
                }
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_model_target_keyword_ap_bonus_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return model attack AP bonus rule for patterns like:
        "Each time a ranged attack made by this model targets an enemy INFANTRY unit,
         improve the Armour Penetration characteristic of that attack by 1."
        """
        if model is None:
            return None
        cache_key = f"model_target_keyword_ap_bonus_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            for name, desc in self._iter_model_specific_ability_entries(model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower().replace("\u2019", "'")
                if "ranged attack" not in low:
                    continue
                if "each time a ranged attack made by this model" not in low:
                    continue
                if "targets" not in low:
                    continue
                if "armour penetration" not in low and "armor penetration" not in low:
                    continue
                if "characteristic" not in low:
                    continue
                if "improve" not in low:
                    continue
                if "enemy infantry unit" not in low:
                    continue
                m = re.search(r"by\s+(\d+)", low)
                if not m:
                    continue
                try:
                    ap_bonus = int(m.group(1) or 0)
                except Exception:
                    ap_bonus = 0
                if ap_bonus <= 0:
                    continue
                source = str(name or "Target AP bonus").strip() or "Target AP bonus"
                rule = {
                    "attack_type": "ranged",
                    "target_keyword": "INFANTRY",
                    "ap_bonus": int(ap_bonus),
                    "source": source,
                }
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_d_cannon_damage_reroll_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time this model makes an attack with its D-cannon, re-roll a Damage roll of 1.
        If that attack targets a TITANIC unit, you can re-roll the Damage roll instead."
        """
        if model is None:
            return None
        cache_key = f"d_cannon_damage_reroll_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            for name, desc in self._iter_model_specific_ability_entries(model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower()
                if "d-cannon" not in low and "d cannon" not in low:
                    continue
                if "damage roll" not in low:
                    continue
                if ("re-roll" not in low) and ("reroll" not in low):
                    continue
                if "damage roll of 1" not in low:
                    continue
                reroll_full_vs_titanic = False
                if "titanic" in low and re.search(r"re-?roll\s+the\s+damage\s+roll", low):
                    reroll_full_vs_titanic = True
                source = str(name or "D-cannon").strip() or "D-cannon"
                rule = {
                    "source": source,
                    "reroll_damage_ones": True,
                    "reroll_damage_full_vs_titanic": bool(reroll_full_vs_titanic),
                    "weapon_match": "d-cannon",
                }
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_point_blank_devastation_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time this model's heavy wraithcannon or suncannon targets a unit within half range,
        you can re-roll the dice to determine the number of attacks made."
        """
        if model is None:
            return None
        cache_key = f"point_blank_devastation_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
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
                m = self._POINT_BLANK_DEVASTATION_RE.fullmatch(normalized)
                weapon_names: list[str] = []
                if m:
                    w1 = str(m.group("weapon1") or "").strip()
                    w2 = str(m.group("weapon2") or "").strip()
                    if w1:
                        weapon_names.append(w1)
                    if w2:
                        weapon_names.append(w2)
                elif str(name or "").strip().lower() == "point-blank devastation":
                    weapon_names = ["heavy wraithcannon", "suncannon"]
                if not weapon_names:
                    continue
                normalized_names = []
                for w in weapon_names:
                    w_key = self._normalize_keyword_phrase(w) or str(w or "").strip().lower()
                    if w_key and w_key not in normalized_names:
                        normalized_names.append(w_key)
                if not normalized_names:
                    continue
                source = str(name or "Point-blank Devastation").strip() or "Point-blank Devastation"
                rule = {"source": source, "weapon_names": normalized_names}
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_sonic_destruction_bonus(
        self,
        model: Optional['Model'] = None,
        target: Optional['Unit'] = None,
        *,
        weapon_profile=None,
        weapon_name: str = "",
    ) -> int:
        """
        Return Sonic Destruction bonus (per other friendly Vibro Cannon Platform model that targeted the unit this phase).
        Applies only in the controlling player's Shooting phase.
        """
        if model is None or target is None:
            return 0
        specs = self.model_sonic_destruction_specs(model)
        if not specs:
            return 0
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            unit = self
        game = None
        owner = None
        try:
            army = unit.get_parent_army()
            owner = getattr(army, "player", None) if army is not None else None
            game = getattr(owner, "game", None) if owner is not None else None
        except Exception:
            owner = None
            game = None
        if game is None or not bool(getattr(game, "is_shooting_phase", lambda: False)()):
            return 0
        if owner is None or owner is not getattr(game, "get_current_player", lambda: None)():
            return 0

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
        if not wname:
            return 0
        weapon_key = self._normalize_keyword_phrase(wname) or wname.lower()

        try:
            target_root = target.get_attached_unit_root()
        except Exception:
            target_root = target

        for spec in list(specs or []):
            spec_weapon = str(spec.get("weapon_key", "") or "").strip()
            if spec_weapon and weapon_key != spec_weapon:
                continue
            try:
                bonus_per = int(spec.get("bonus_per_other", 1) or 1)
            except Exception:
                bonus_per = 1
            if bonus_per <= 0:
                continue

            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            owner_id = str(getattr(owner, "id", "") or "")

            if (
                int(sr.get("sonic_destruction_turn", 0) or 0) != int(turn)
                or str(sr.get("sonic_destruction_owner", "") or "") != owner_id
                or str(sr.get("sonic_destruction_phase", "") or "").strip().upper() != phase_name
            ):
                sr["sonic_destruction_attackers"] = {}

            attackers = sr.get("sonic_destruction_attackers", {})
            if not isinstance(attackers, dict):
                attackers = {}
            existing = set(str(x) for x in list(attackers.get(owner_id, []) or []) if x)
            mid = str(get_entity_id(model) or "")
            other_count = len([x for x in existing if x != mid])
            if mid:
                existing.add(mid)
                attackers[owner_id] = sorted(existing)
            sr["sonic_destruction_attackers"] = attackers
            sr["sonic_destruction_owner"] = owner_id
            sr["sonic_destruction_turn"] = int(turn or 0)
            sr["sonic_destruction_phase"] = phase_name
            target_root.special_rules = sr
            return int(other_count * bonus_per)

        return 0

    def has_fleet_of_foot(self) -> bool:
        """Return True if this unit has the Fleet of Foot ability."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "has_fleet_of_foot"
        if cache_key in getattr(root, "_ability_cache", {}):
            return bool(root._ability_cache[cache_key])
        found = False
        try:
            found, _ = root._find_ability_with_patterns(["fleet of foot"])
        except Exception:
            found = False
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = bool(found)
        return bool(found)

    def model_has_shadow_field_ability(self, model: Optional['Model'] = None) -> bool:
        """Return True if this model has the Shadow Field ability."""
        if model is None:
            return False
        cache_key = f"model_shadow_field:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])

        found = False
        try:
            for name, desc in self._iter_model_specific_ability_entries(model):
                name_norm = str(name or "").strip().lower()
                if name_norm == "shadow field":
                    found = True
                    break
                text_src = desc or name or ""
                if not text_src:
                    continue
                normalized = self._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if self._SHADOW_FIELD_RE.fullmatch(normalized):
                    found = True
                    break
        except Exception:
            found = False

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def is_shadow_field_broken(self, model: Optional['Model'] = None) -> bool:
        if model is None:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        broken = sr.get("shadow_field_broken_model_ids", [])
        mid = str(get_entity_id(model) or "")
        try:
            return mid in list(broken or [])
        except Exception:
            return False

    def mark_shadow_field_broken(self, model: Optional['Model'] = None) -> None:
        if model is None:
            return
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        broken = list(sr.get("shadow_field_broken_model_ids", []) or [])
        mid = str(get_entity_id(model) or "")
        if mid and mid not in broken:
            broken.append(mid)
        sr["shadow_field_broken_model_ids"] = broken
        root.special_rules = sr

    def get_selected_to_shoot_reroll_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time this model is selected to shoot, you can re-roll one Hit roll and you can re-roll one Wound roll
        when resolving those attacks."
        """
        if model is None:
            return None
        cache_key = f"selected_to_shoot_reroll_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            for name, desc in self._iter_model_specific_ability_entries(model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower().replace("\u2019", "'")
                if "selected to shoot" not in low:
                    continue
                if ("re-roll" not in low) and ("reroll" not in low):
                    continue
                if "selected to shoot or fight" in low or "selected to fight" in low:
                    continue
                allow_hit = bool(re.search(r"re-?roll\s+one\s+hit\s+roll", low))
                allow_wound = bool(re.search(r"re-?roll\s+one\s+wound\s+roll", low))
                allow_damage = bool(re.search(r"re-?roll\s+one\s+damage\s+roll", low))
                if not (allow_hit or allow_wound or allow_damage):
                    continue
                source = str(name or "Selected to shoot").strip() or "Selected to shoot"
                rule = {
                    "reroll_hit": bool(allow_hit),
                    "reroll_wound": bool(allow_wound),
                    "reroll_damage": bool(allow_damage),
                    "requires_shooting_phase": ("shooting phase" in low),
                    "source": source,
                }
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_selected_to_shoot_or_fight_reroll_choice_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time this model is selected to shoot or fight, you can re-roll one Hit roll or you can re-roll one Wound roll
        when resolving those attacks."
        Also supports variants that allow one Hit and one Wound re-roll each (not a choice), e.g.
        "Each time this model shoots or fights ... you can re-roll one Hit roll and you can re-roll one Wound roll."
        """
        if model is None:
            return None
        cache_key = f"selected_to_shoot_or_fight_reroll_choice_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            import re

            for name, desc in self._iter_model_specific_ability_entries(model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower().replace("\u2019", "'")
                selected_phrase = (
                    re.search(r"selected\s+to\s+(?:shoot|fire)\s+or\s+fight", low)
                    or re.search(r"selected\s+to\s+fight\s+or\s+(?:shoot|fire)", low)
                )
                shoots_or_fights_phrase = bool(
                    re.search(
                        r"each\s+time\s+this\s+model\s+(?:shoot|shoots|fire|fires)\s+or\s+fight(?:s)?",
                        low,
                    )
                )
                if not (selected_phrase or shoots_or_fights_phrase):
                    continue
                if ("re-roll" not in low) and ("reroll" not in low):
                    continue
                allow_hit = bool(re.search(r"re-?roll\s+one\s+hit\s+roll", low))
                allow_wound = bool(re.search(r"re-?roll\s+one\s+wound\s+roll", low))
                if not (allow_hit and allow_wound):
                    continue
                is_choice = bool(re.search(r"hit\s+roll.*or.*wound\s+roll|wound\s+roll.*or.*hit\s+roll", low))
                is_one_each = not is_choice
                if not (is_choice or is_one_each):
                    continue
                source = str(name or "Selected to shoot or fight").strip() or "Selected to shoot or fight"
                rule = {
                    "reroll_hit": True,
                    "reroll_wound": True,
                    "mode": "choice" if is_choice else "one_each",
                    "requires_shooting_phase": ("shooting phase" in low),
                    "requires_fight_phase": ("fight phase" in low),
                    "source": source,
                }
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def grant_selected_to_shoot_rerolls_for_models(self, models: list['Model']) -> None:
        if not models:
            return
        for model in list(models or []):
            try:
                if not getattr(model, "is_alive", False):
                    continue
            except Exception:
                continue
            rule = self.get_selected_to_shoot_reroll_rule(model)
            if not rule:
                continue
            if rule.get("requires_shooting_phase"):
                game = None
                try:
                    game = self.get_parent_army().player.game
                except Exception:
                    game = None
                if game is None or not bool(getattr(game, "is_shooting_phase", lambda: False)()):
                    continue
                try:
                    if game.get_current_player() is not self.get_parent_army().player:
                        continue
                except Exception:
                    continue
            try:
                model.grant_selected_to_shoot_rerolls(
                    hit=bool(rule.get("reroll_hit")),
                    wound=bool(rule.get("reroll_wound")),
                    damage=bool(rule.get("reroll_damage")),
                    source=str(rule.get("source", "") or ""),
                )
            except Exception:
                continue

    def grant_selected_to_action_reroll_choice_for_models(self, models: list['Model'], *, action: str) -> None:
        if not models:
            return
        action_key = str(action or "").strip().lower()
        if action_key not in ("shoot", "fight"):
            return
        for model in list(models or []):
            try:
                if not getattr(model, "is_alive", False):
                    continue
            except Exception:
                continue
            rule = self.get_selected_to_shoot_or_fight_reroll_choice_rule(model)
            if not rule:
                continue
            if action_key == "shoot" and rule.get("requires_shooting_phase"):
                game = None
                try:
                    game = self.get_parent_army().player.game
                except Exception:
                    game = None
                if game is None or not bool(getattr(game, "is_shooting_phase", lambda: False)()):
                    continue
                try:
                    if game.get_current_player() is not self.get_parent_army().player:
                        continue
                except Exception:
                    continue
            if action_key == "fight" and rule.get("requires_fight_phase"):
                game = None
                try:
                    game = self.get_parent_army().player.game
                except Exception:
                    game = None
                if game is None or not bool(getattr(game, "is_fight_phase", lambda: False)()):
                    continue
                try:
                    if game.get_current_player() is not self.get_parent_army().player:
                        continue
                except Exception:
                    continue
            try:
                model.grant_selected_to_action_reroll_choice(
                    action=action_key,
                    allow_hit=bool(rule.get("reroll_hit")),
                    allow_wound=bool(rule.get("reroll_wound")),
                    source=str(rule.get("source", "") or ""),
                    mode=str(rule.get("mode", "choice") or "choice"),
                )
            except Exception:
                continue

    def clear_selected_to_shoot_rerolls(self) -> None:
        try:
            models = list(getattr(self, "models", []) or [])
        except Exception:
            models = []
        for model in models:
            try:
                model.clear_selected_to_shoot_rerolls()
            except Exception:
                continue

    def clear_selected_to_action_reroll_choice(self, action: str | None = None) -> None:
        try:
            models = list(self.get_attached_unit_models() or [])
        except Exception:
            models = []
        if not models:
            try:
                models = list(getattr(self, "models", []) or [])
            except Exception:
                models = []
        for model in models:
            try:
                model.clear_selected_to_action_reroll_choice(action=action)
            except Exception:
                continue

    def get_two_melee_weapons_attacks_bonus(self, model: Optional['Model'] = None) -> int:
        """
        Return the Attacks bonus for abilities like:
        "If this model is equipped with two melee weapons in addition to its close combat weapon,
        add 2 to the Attacks characteristic of those two weapons."
        """
        if model is None:
            return 0
        cache_key = f"two_melee_weapons_attacks_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            try:
                return int(self._ability_cache[cache_key] or 0)
            except Exception:
                return 0

        bonus = 0
        try:
            import re

            for name, desc in self._iter_model_specific_ability_entries(model):
                text = self._normalize_rules_text(f"{name} {desc}")
                if not text:
                    continue
                low = text.lower().replace("\u2019", "'")
                if "two melee weapons" not in low:
                    continue
                if "close combat weapon" not in low:
                    continue
                m = re.search(
                    r"add\s+(\d+)\s+to\s+the\s+attacks\s+characteristic\s+of\s+those\s+(?:two\s+)?weapons",
                    low,
                )
                if not m:
                    continue
                bonus = int(m.group(1))
                break
        except Exception:
            bonus = 0

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = int(bonus)
        return int(bonus)

    def get_two_melee_weapons_bonus(self, model: Optional['Model'] = None):
        """
        Return (bonus, eligible_wargear) for the two-melee-weapons clause.
        Bonus applies only if the model has a close combat weapon and exactly two other melee weapons.
        """
        if model is None:
            return 0, []
        bonus = int(self.get_two_melee_weapons_attacks_bonus(model) or 0)
        if bonus <= 0:
            return 0, []

        ccw_present = False
        eligible = []
        for wg in list(getattr(model, "wargear", []) or []):
            try:
                if not wg or not wg.is_melee():
                    continue
            except Exception:
                continue
            name_norm = self._norm_wargear_name(getattr(wg, "name", "") or "")
            if "close combat weapon" in name_norm:
                ccw_present = True
                continue
            eligible.append(wg)

        if not ccw_present or len(eligible) != 2:
            return 0, []
        return bonus, eligible

    def can_reroll_blood_surge_roll(self) -> bool:
        """Check for a leader-provided reroll to the Blood Surge D6 (e.g., Forwards, for Blood!)."""
        for t in self._iter_attached_leader_ability_texts():
            s = str(t or "").lower()
            if ("blood surge" in s) and ("re-roll" in s or "reroll" in s):
                return True
        for t in self._iter_active_ability_texts():
            s = str(t or "").lower()
            if ("blood surge" in s) and ("re-roll" in s or "reroll" in s):
                return True
        return False

    def _blood_surge_phase_key(self, game=None) -> str:
        if game is None:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        try:
            phase = getattr(game, "phase", None)
            pname = str(getattr(phase, "name", "") or phase or "").strip().upper()
        except Exception:
            pname = ""
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        owner = str(getattr(current_player, "name", "") or "")
        return f"{br}:{pname}:{owner}"

    def _brazen_fury_phase_key(self, game=None) -> str:
        if game is None:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        try:
            phase = getattr(game, "phase", None)
            pname = str(getattr(phase, "name", "") or phase or "").strip().upper()
        except Exception:
            pname = ""
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        owner = str(getattr(current_player, "name", "") or "")
        return f"{br}:{pname}:{owner}"

    def blood_surge_used_this_phase(self, game=None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._blood_surge_phase_key(game)
        return str(sr.get("blood_surge_used_phase_key", "")) == key

    def mark_blood_surge_used(self, game=None) -> None:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["blood_surge_used_phase_key"] = self._blood_surge_phase_key(game)
        self.special_rules = sr

    def brazen_fury_used_this_phase(self, game=None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._brazen_fury_phase_key(game)
        return str(sr.get("brazen_fury_used_phase_key", "")) == key

    def mark_brazen_fury_used(self, game=None) -> None:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["brazen_fury_used_phase_key"] = self._brazen_fury_phase_key(game)
        self.special_rules = sr

    def can_blood_surge(self, game=None, game_map=None) -> bool:
        if not self.has_blood_surge():
            return False
        if not self.is_alive() or not getattr(self, "deployed", False):
            return False
        if self.is_battle_shocked():
            return False
        if self.blood_surge_used_this_phase(game):
            return False
        if game_map is None:
            try:
                game_map = getattr(game, "map", None)
            except Exception:
                game_map = None
        if game_map is not None:
            try:
                for enemy in game_map.get_enemy_units(self):
                    if game_map.is_within_engagement_range(self, enemy):
                        return False
            except Exception:
                pass
        return True

    def can_brazen_fury(self, game=None, game_map=None) -> bool:
        if not self.has_brazen_fury():
            return False
        if not self.is_alive() or not getattr(self, "deployed", False):
            return False
        if self.is_battle_shocked():
            return False
        if self.brazen_fury_used_this_phase(game):
            return False
        if game_map is None:
            try:
                game_map = getattr(game, "map", None)
            except Exception:
                game_map = None
        if game_map is not None:
            try:
                for enemy in game_map.get_enemy_units(self):
                    if game_map.is_within_engagement_range(self, enemy):
                        return False
            except Exception:
                pass
        return True

    def can_horde_move(self, game=None, game_map=None) -> bool:
        if not self.has_horde_move():
            return False
        if not self.is_alive() or not getattr(self, "deployed", False):
            return False
        if self.is_battle_shocked():
            return False
        try:
            if self.is_in_reserves():
                return False
        except Exception:
            pass
        try:
            if bool(getattr(self, "is_embarked", False)) or bool(getattr(self, "embarked_in", None)):
                return False
        except Exception:
            pass
        return True

    def has_reanimation_protocols(self) -> bool:
        """Check if the unit has Reanimation Protocols (Necrons army rule)."""
        if 'reanimation_protocols' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['reanimation_protocols']

        found, _ = self._find_ability_with_patterns(["reanimation protocols", "reanimation protocol"])

        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['reanimation_protocols'] = found
        return found

    def _normalize_rules_text(self, text: str) -> str:
        """Normalize Wahapedia-style text for rule pattern matching."""
        if not text:
            return ""
        # Strip HTML tags like <span class="kwb">CHARACTER</span>
        try:
            text = re.sub(r"<[^>]+>", " ", text)
        except Exception:
            pass
        # Normalize whitespace and punctuation spacing
        text = text.replace("\n", " ").replace("\r", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _normalize_keyword_phrase(value: str) -> str:
        t = str(value or "").lower()
        t = t.replace("\u2019", "'").replace("\u0192?T", "'")
        t = re.sub(r"[^a-z0-9]+", " ", t)
        return re.sub(r"\s+", " ", t).strip()

    @classmethod
    def _unit_matches_keyword_phrase(cls, unit, phrase: str, *, use_effective: bool = True) -> bool:
        key_phrase = cls._normalize_keyword_phrase(phrase)
        if not key_phrase:
            return False
        tokens = key_phrase.split()
        if not tokens:
            return False
        keywords: set[str] = set()
        if use_effective:
            try:
                kws = list(getattr(unit, "get_effective_keywords")() or [])
            except Exception:
                kws = list(getattr(unit, "keywords", []) or [])
            try:
                kws += list(getattr(unit, "get_effective_faction_keywords")() or [])
            except Exception:
                kws += list(getattr(unit, "faction_keywords", []) or [])
        else:
            kws = list(getattr(unit, "keywords", []) or [])
            kws += list(getattr(unit, "faction_keywords", []) or [])
        for kw in kws:
            norm = cls._normalize_keyword_phrase(kw)
            if norm:
                keywords.add(norm)
        if not keywords:
            return False
        n = len(tokens)
        dp = [False] * (n + 1)
        dp[n] = True
        for i in range(n - 1, -1, -1):
            for j in range(i + 1, n + 1):
                cand = " ".join(tokens[i:j])
                if cand in keywords and dp[j]:
                    dp[i] = True
                    break
        return dp[0]

    @staticmethod
    def _strip_eligibility_prefix(text: str) -> str:
        """
        Strip Wahapedia-style eligibility prefixes like:
          "<KEYWORDS> model only. <rules text...>"
        """
        t = str(text or "")
        low = t.lower()
        for marker in (" model only.", " models only."):
            idx = low.find(marker)
            if idx != -1:
                return t[idx + len(marker):].strip()
        return t

    @staticmethod
    def _parse_move_types_from_text(value: str) -> set[str]:
        """Parse movement type tokens (normal/advance/fall back/charge) from a text fragment."""
        types: set[str] = set()
        if not value:
            return types
        low = str(value).lower()
        if "normal" in low:
            types.add("move")
        if "advance" in low:
            types.add("advance")
        if "fall back" in low or "fallback" in low:
            types.add("fall_back")
        if "charge" in low:
            types.add("charge")
        return types

    def _iter_ability_entries_for_rules(self, model: Optional['Model'] = None):
        """Yield (name, description) pairs for unit/model abilities."""
        # Unit-level abilities
        for a in self._iter_active_possible_abilities():
            if isinstance(a, str):
                yield a, a
            else:
                yield getattr(a, "name", "") or "", getattr(a, "description", "") or ""

        # Enhancement rules (treated as unit-level ability text).
        if model is None:
            enh = getattr(self, "enhancement", None)
            if enh is not None:
                name = getattr(enh, "name", "") or ""
                desc = getattr(enh, "description", "") or ""
                if name or desc:
                    yield name, desc

        # Model-level abilities (if provided)
        if model is not None:
            try:
                for a in getattr(model, "abilities", {}).values():
                    if isinstance(a, str):
                        if self._ability_is_active(a):
                            yield a, a
                    else:
                        if self._ability_is_active(a):
                            yield getattr(a, "name", "") or "", getattr(a, "description", "") or ""
            except Exception:
                pass

    def _iter_model_specific_ability_entries(self, model: Optional['Model'] = None):
        """
        Yield (name, description) pairs for model-specific rules.

        - Always includes model-level abilities (if provided).
        - Includes unit-level abilities only when the unit is a single-model unit.
        """
        if model is None:
            return
        try:
            if len(getattr(self, "models", []) or []) <= 1:
                for a in self._iter_active_possible_abilities():
                    if isinstance(a, str):
                        yield a, a
                    else:
                        yield getattr(a, "name", "") or "", getattr(a, "description", "") or ""
        except Exception:
            pass
        try:
            for a in getattr(model, "abilities", {}).values():
                try:
                    if not self._ability_is_active(a):
                        continue
                except Exception:
                    pass
                if isinstance(a, str):
                    yield a, a
                else:
                    yield getattr(a, "name", "") or "", getattr(a, "description", "") or ""
        except Exception:
            pass

    def _get_model_reroll_modifiers(self, model: Optional['Model'] = None, *, attack_type: str = "any", target=None, roll: str = "hit") -> dict:
        mods = {
            "reroll_values": (),
            "reroll_full": False,
            "reroll_reasons": (),
            "reroll_full_reasons": (),
        }
        if model is None:
            return mods
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"
        roll_key = str(roll or "").strip().lower()
        if roll_key not in ("hit", "wound"):
            return mods

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        rules = self._get_model_attack_roll_rules(model)
        if not rules:
            return mods

        reroll_values: set[int] = set()
        reroll_reasons: list[str] = []
        reroll_full_reasons: list[str] = []

        def _cond_suffix(cond: Optional[AttackRollCondition]) -> str:
            if not cond:
                return ""
            parts = []
            if cond.target_battleshocked:
                parts.append("vs Battle-shocked targets")
            if cond.attacker_below_starting_strength:
                parts.append("while below Starting Strength")
            if cond.attacker_below_half_strength:
                parts.append("while below Half-strength")
            if cond.attacker_charged_this_turn:
                parts.append("after making a Charge move this turn")
            if cond.attacker_contains_model_keywords_any:
                kw = "/".join(k.upper() for k in cond.attacker_contains_model_keywords_any)
                parts.append(f"while containing {kw} model")
            if cond.attacker_within_objective_controlled:
                parts.append("while within a controlled objective")
            if cond.target_within_objective:
                parts.append("vs targets within objective range")
            if cond.target_within_range is not None:
                parts.append(f"vs targets within {cond.target_within_range}\"")
            if cond.target_isolated_within is not None:
                parts.append(f"vs isolated targets (no other enemy units within {cond.target_isolated_within}\")")
            if cond.target_can_fly is True:
                parts.append("vs FLY targets")
            if cond.target_can_fly is False:
                parts.append("vs non-FLY targets")
            if cond.target_keywords_any:
                kw = "/".join(k.upper() for k in cond.target_keywords_any)
                parts.append(f"vs {kw} targets")
            if cond.target_keywords_all:
                kw = " & ".join(k.upper() for k in cond.target_keywords_all)
                parts.append(f"vs {kw} targets")
            if cond.target_below_starting_strength:
                parts.append("vs targets below Starting Strength")
            if cond.target_below_half_strength:
                parts.append("vs targets below Half-strength")
            if cond.target_exclude_keywords_any:
                parts.append("excluding " + ", ".join(cond.target_exclude_keywords_any))
            if not parts:
                return ""
            return " (" + "; ".join(parts) + ")"

        for rule, name in list(rules or []):
            if atype != "any" and rule.attack_type not in ("any", atype):
                continue
            for eff in rule.effects:
                if eff.roll != roll_key or eff.kind != "reroll":
                    continue
                cond = eff.condition
                if cond and not self._attack_condition_met(cond, target=target, source_unit=root):
                    continue
                label = name or "Model ability"
                if eff.reroll_full:
                    reroll_full_reasons.append(f"{label}: re-roll {roll_key.title()} roll{_cond_suffix(cond)}")
                if eff.reroll_values:
                    reroll_values.update(int(v) for v in eff.reroll_values)
                    reroll_reasons.append(
                        f"{label}: re-roll {roll_key.title()} rolls of {', '.join(str(v) for v in sorted(eff.reroll_values))}{_cond_suffix(cond)}"
                    )

        mods["reroll_values"] = tuple(sorted(reroll_values))
        mods["reroll_reasons"] = tuple(reroll_reasons)
        mods["reroll_full_reasons"] = tuple(reroll_full_reasons)
        mods["reroll_full"] = bool(reroll_full_reasons)
        return mods

    def _start_of_battle_keyword_reroll_ones_reasons(
        self,
        model: Optional['Model'],
        target: Optional['Unit'],
        *,
        roll: str,
    ) -> list[str]:
        if model is None or target is None:
            return []
        roll_key = str(roll or "").strip().lower()
        if roll_key not in ("hit", "wound"):
            return []
        reasons: list[str] = []
        entries = self._iter_start_of_battle_keyword_reroll_choices(model)
        for entry in list(entries or []):
            if not isinstance(entry, dict):
                continue
            keyword = str(entry.get("keyword", "") or "").strip()
            if not keyword:
                continue
            target_ok = False
            try:
                if hasattr(target, "has_keyword"):
                    target_ok = bool(target.has_keyword(keyword))
                elif hasattr(target, "has_any_keyword"):
                    target_ok = bool(target.has_any_keyword(keyword))
            except Exception:
                target_ok = False
            if not target_ok:
                continue
            source = str(entry.get("source", "") or "Start of battle selection").strip() or "Start of battle selection"
            reasons.append(f"{source}: re-roll {roll_key.title()} rolls of 1 vs {keyword.upper()} targets")
        return reasons

    def get_model_hit_reroll_modifiers(self, model: Optional['Model'] = None, *, attack_type: str = "any", target=None) -> dict:
        mods = self._get_model_reroll_modifiers(model, attack_type=attack_type, target=target, roll="hit")
        reroll_values = set(mods.get("reroll_values", ()) or ())
        reroll_reasons = list(mods.get("reroll_reasons", ()) or ())
        reroll_full_reasons = list(mods.get("reroll_full_reasons", ()) or ())
        extra_reasons = self._start_of_battle_keyword_reroll_ones_reasons(model, target, roll="hit")
        if extra_reasons:
            reroll_values.add(1)
            reroll_reasons.extend(extra_reasons)
        seen = set()
        deduped_reasons: list[str] = []
        for reason in reroll_reasons:
            key = str(reason or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped_reasons.append(str(reason))
        return {
            "reroll_hit_values": tuple(sorted(reroll_values)),
            "reroll_hit_full": bool(mods.get("reroll_full")),
            "reroll_hit_reasons": tuple(deduped_reasons),
            "reroll_hit_full_reasons": tuple(reroll_full_reasons),
        }

    def get_model_wound_reroll_modifiers(self, model: Optional['Model'] = None, *, attack_type: str = "any", target=None) -> dict:
        mods = self._get_model_reroll_modifiers(model, attack_type=attack_type, target=target, roll="wound")
        reroll_values = set(mods.get("reroll_values", ()) or ())
        reroll_reasons = list(mods.get("reroll_reasons", ()) or ())
        reroll_full_reasons = list(mods.get("reroll_full_reasons", ()) or ())
        extra_reasons = self._start_of_battle_keyword_reroll_ones_reasons(model, target, roll="wound")
        if extra_reasons:
            reroll_values.add(1)
            reroll_reasons.extend(extra_reasons)
        seen = set()
        deduped_reasons: list[str] = []
        for reason in reroll_reasons:
            key = str(reason or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped_reasons.append(str(reason))
        return {
            "reroll_wound_values": tuple(sorted(reroll_values)),
            "reroll_wound_full": bool(mods.get("reroll_full")),
            "reroll_wound_reasons": tuple(deduped_reasons),
            "reroll_wound_full_reasons": tuple(reroll_full_reasons),
        }

    def model_hit_bonus_vs_fly(self, model: Optional['Model'] = None, *, attack_type: str = "any") -> tuple[int, Optional[str]]:
        """
        Model-specific rule: +N to Hit rolls vs targets that can FLY.

        Returns (bonus, reason_name).
        """
        if model is None:
            return 0, None
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"
        cache_key = f"model_hit_bonus_vs_fly:{get_entity_id(model)}:{atype}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        bonus = 0
        reason = None

        def _fly_only_condition(cond: Optional[AttackRollCondition]) -> bool:
            if cond is None:
                return False
            if cond.target_can_fly is not True:
                return False
            if cond.attacker_below_starting_strength or cond.attacker_below_half_strength:
                return False
            if cond.target_battleshocked or cond.target_within_objective or cond.target_within_range is not None:
                return False
            if cond.target_keywords_any or cond.target_keywords_all or cond.target_exclude_keywords_any:
                return False
            if cond.target_below_starting_strength:
                return False
            if cond.target_below_half_strength:
                return False
            return True

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            for rule in self._parse_attack_roll_rules_from_text(text_src):
                if rule.subject not in ("this_model", "model_in_this_unit"):
                    continue
                if atype != "any" and rule.attack_type not in ("any", atype):
                    continue
                for eff in rule.effects:
                    if eff.roll != "hit" or eff.kind != "add":
                        continue
                    if not _fly_only_condition(eff.condition):
                        continue
                    try:
                        val = int(eff.value or 0)
                    except Exception:
                        val = 0
                    if val:
                        bonus = val
                        reason = str(name or "Model ability")
                        break
                if bonus:
                    break
            if bonus:
                break

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = (bonus, reason)
        return bonus, reason

    def _get_model_attack_roll_rules(self, model: Optional['Model'] = None) -> list[tuple['AttackRollRule', str]]:
        if model is None:
            return []
        cache_key = f"model_attack_roll_rules:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        rules: list[tuple[AttackRollRule, str]] = []
        seen_names: set[str] = set()
        for name, desc in self._iter_model_specific_ability_entries(model):
            try:
                ability_name = str(name or "").replace("\u2019", "'").strip()
            except Exception:
                ability_name = ""
            name_key = ability_name.lower().strip()
            if name_key and name_key in seen_names:
                continue
            if name_key:
                seen_names.add(name_key)
            text_src = desc or name or ""
            for rule in self._parse_attack_roll_rules_from_text(text_src):
                if rule.subject != "this_model":
                    continue
                rules.append((rule, ability_name or "Model ability"))

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(rules)
        return list(rules)

    def model_attack_roll_modifiers_vs_weakened_target(
        self,
        model: Optional['Model'] = None,
        *,
        attack_type: str = "any",
        target: Optional['Unit'] = None,
    ) -> dict:
        """
        Model-specific rule: add/subtract to Hit/Wound rolls when parsed attack-roll conditions are met.
        """
        mods = {
            "hit": 0,
            "wound": 0,
            "hit_reasons": (),
            "wound_reasons": (),
        }
        if model is None:
            return mods
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        rules = self._get_model_attack_roll_rules(model)
        if not rules:
            return mods

        hit_reasons: list[str] = []
        wound_reasons: list[str] = []

        def _cond_suffix(cond: Optional[AttackRollCondition]) -> str:
            if not cond:
                return ""
            parts = []
            if cond.target_battleshocked:
                parts.append("vs Battle-shocked targets")
            if cond.attacker_below_starting_strength:
                parts.append("while below Starting Strength")
            if cond.attacker_below_half_strength:
                parts.append("while below Half-strength")
            if cond.attacker_charged_this_turn:
                parts.append("after making a Charge move this turn")
            if cond.attacker_contains_model_keywords_any:
                kw = "/".join(k.upper() for k in cond.attacker_contains_model_keywords_any)
                parts.append(f"while containing {kw} model")
            if cond.attacker_within_objective_controlled:
                parts.append("while within a controlled objective")
            if cond.target_within_objective:
                parts.append("vs targets within objective range")
            if cond.target_within_range is not None:
                parts.append(f"vs targets within {cond.target_within_range}\"")
            if cond.target_isolated_within is not None:
                parts.append(f"vs isolated targets (no other enemy units within {cond.target_isolated_within}\")")
            if cond.target_can_fly is True:
                parts.append("vs FLY targets")
            if cond.target_can_fly is False:
                parts.append("vs non-FLY targets")
            if cond.target_keywords_any:
                kw = "/".join(k.upper() for k in cond.target_keywords_any)
                parts.append(f"vs {kw} targets")
            if cond.target_keywords_all:
                kw = " & ".join(k.upper() for k in cond.target_keywords_all)
                parts.append(f"vs {kw} targets")
            if cond.target_below_starting_strength:
                parts.append("vs targets below Starting Strength")
            if cond.target_below_half_strength:
                parts.append("vs targets below Half-strength")
            if cond.target_exclude_keywords_any:
                parts.append("excluding " + ", ".join(cond.target_exclude_keywords_any))
            if not parts:
                return ""
            return " (" + "; ".join(parts) + ")"

        for rule, name in list(rules or []):
            if atype != "any" and rule.attack_type not in ("any", atype):
                continue
            if rule.scope == "leading" and not bool(getattr(self, "is_attached_leader", False)):
                continue
            for eff in rule.effects:
                if eff.roll not in ("hit", "wound"):
                    continue
                if eff.kind not in ("add", "sub"):
                    continue
                cond = eff.condition
                if not self._attack_condition_met(cond, target=target, source_unit=root):
                    continue
                try:
                    val = int(eff.value or 0)
                except Exception:
                    val = 0
                if eff.kind == "sub":
                    val = -val
                if not val:
                    continue
                label = name or "Model ability"
                if eff.roll == "hit":
                    mods["hit"] += val
                    hit_reasons.append(f"{val:+d} to hit from {label}{_cond_suffix(cond)}")
                else:
                    mods["wound"] += val
                    wound_reasons.append(f"{val:+d} to wound from {label}{_cond_suffix(cond)}")

        mods["hit_reasons"] = tuple(hit_reasons)
        mods["wound_reasons"] = tuple(wound_reasons)
        return mods

