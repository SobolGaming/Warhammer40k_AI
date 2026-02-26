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
        try:
            if hasattr(self, "_trait_flag") and bool(self._trait_flag("firing_deck", default=False)):
                value = 0
                if hasattr(self, "_trait_value"):
                    value = int(self._trait_value("firing_deck", default=0) or 0)
                if value > 0:
                    return True, int(value)
        except Exception:
            pass
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
        # Datasheet activation: Blinding Spray (Fight phase only, selected unit gains Fights First).
        try:
            root = self.get_attached_unit_root()
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("blinding_spray_fight_first_active"):
                valid = True
                owner_id = str(sr.get("blinding_spray_owner", "") or "")
                try:
                    turn = int(sr.get("blinding_spray_turn", 0) or 0)
                except Exception:
                    turn = 0
                expires_phase = str(sr.get("blinding_spray_expires_phase", "") or "FIGHT_PHASE").strip().upper()
                game = None
                current_owner = ""
                current_phase = ""
                current_turn = 0
                try:
                    game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
                except Exception:
                    game = None
                if game is not None:
                    try:
                        current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    except Exception:
                        current_phase = ""
                    try:
                        current_turn = int(getattr(game, "turn", 0) or 0)
                    except Exception:
                        current_turn = 0
                    try:
                        current_owner = str(getattr(game.get_current_player(), "id", "") or "")
                    except Exception:
                        current_owner = ""
                if expires_phase and current_phase and current_phase != expires_phase:
                    valid = False
                if owner_id and current_owner and owner_id != current_owner:
                    valid = False
                if turn and current_turn and turn != current_turn:
                    valid = False
                if valid:
                    return True
                for key in (
                    "blinding_spray_fight_first_active",
                    "blinding_spray_owner",
                    "blinding_spray_turn",
                    "blinding_spray_source",
                    "blinding_spray_expires_phase",
                ):
                    sr.pop(key, None)
                root.special_rules = sr
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

        def _is_blinding_spray_text(value: str) -> bool:
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
            try:
                return bool(self._BLINDING_SPRAY_RE.fullmatch(norm))
            except Exception:
                return False

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
                    if _is_blinding_spray_text(text):
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

    def _aeldari_to_their_final_breath_rule(self) -> Optional[dict]:
        """Return active TO THEIR FINAL BREATH fight-on-death rule when present."""
        try:
            sr = getattr(self, "special_rules", None)
            if not (isinstance(sr, dict) and sr.get("aeldari_to_their_final_breath_active")):
                return None
            phase_name = ""
            current_turn = 0
            try:
                army = self.get_parent_army()
            except Exception:
                army = None
            try:
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            except Exception:
                game = None
            if game is not None:
                try:
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                except Exception:
                    phase_name = ""
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except Exception:
                    current_turn = 0
            try:
                marked_turn = int(sr.get("aeldari_to_their_final_breath_turn", 0) or 0)
            except Exception:
                marked_turn = 0
            exp = str(sr.get("aeldari_to_their_final_breath_expires_phase", "") or "").strip().upper()
            if phase_name == "FIGHT_PHASE" and (not exp or exp == "FIGHT_PHASE"):
                if not (marked_turn and current_turn and marked_turn != current_turn):
                    source = str(sr.get("aeldari_to_their_final_breath_source", "") or "TO THEIR FINAL BREATH").strip()
                    source = source or "TO THEIR FINAL BREATH"
                    try:
                        threshold = int(sr.get("aeldari_to_their_final_breath_threshold", 4) or 4)
                    except Exception:
                        threshold = 4
                    return {
                        "threshold": max(2, min(6, int(threshold))),
                        "source": source,
                    }
            if phase_name and phase_name != "FIGHT_PHASE":
                for key in (
                    "aeldari_to_their_final_breath_active",
                    "aeldari_to_their_final_breath_expires_phase",
                    "aeldari_to_their_final_breath_owner",
                    "aeldari_to_their_final_breath_turn",
                    "aeldari_to_their_final_breath_source",
                    "aeldari_to_their_final_breath_threshold",
                    "aeldari_to_their_final_breath_token_spent",
                ):
                    sr.pop(key, None)
                self.special_rules = sr
        except Exception:
            return None
        return None

    def _aeldari_parting_the_veil_rule(self) -> Optional[dict]:
        """Return active PARTING THE VEIL fight-on-death rule when present."""
        try:
            sr = getattr(self, "special_rules", None)
            if not (isinstance(sr, dict) and sr.get("aeldari_parting_the_veil_active")):
                return None
            phase_name = ""
            current_turn = 0
            try:
                army = self.get_parent_army()
            except Exception:
                army = None
            try:
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            except Exception:
                game = None
            if game is not None:
                try:
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                except Exception:
                    phase_name = ""
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except Exception:
                    current_turn = 0
            try:
                marked_turn = int(sr.get("aeldari_parting_the_veil_turn", 0) or 0)
            except Exception:
                marked_turn = 0
            exp = str(sr.get("aeldari_parting_the_veil_expires_phase", "") or "").strip().upper()
            if phase_name == "FIGHT_PHASE" and (not exp or exp == "FIGHT_PHASE"):
                if not (marked_turn and current_turn and marked_turn != current_turn):
                    source = str(sr.get("aeldari_parting_the_veil_source", "") or "PARTING THE VEIL").strip()
                    source = source or "PARTING THE VEIL"
                    return {
                        "automatic": True,
                        "source": source,
                    }
            if phase_name and phase_name != "FIGHT_PHASE":
                for key in (
                    "aeldari_parting_the_veil_active",
                    "aeldari_parting_the_veil_expires_phase",
                    "aeldari_parting_the_veil_owner",
                    "aeldari_parting_the_veil_turn",
                    "aeldari_parting_the_veil_source",
                    "aeldari_parting_the_veil_automatic",
                ):
                    sr.pop(key, None)
                self.special_rules = sr
        except Exception:
            return None
        return None

    def _aeldari_heroes_fall_rule(self) -> Optional[dict]:
        """Return active HEROES' FALL fight-on-death rule when present."""
        try:
            sr = getattr(self, "special_rules", None)
            if not (isinstance(sr, dict) and sr.get("aeldari_heroes_fall_active")):
                return None
            phase_name = ""
            current_turn = 0
            try:
                army = self.get_parent_army()
            except Exception:
                army = None
            try:
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            except Exception:
                game = None
            if game is not None:
                try:
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                except Exception:
                    phase_name = ""
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except Exception:
                    current_turn = 0
            try:
                marked_turn = int(sr.get("aeldari_heroes_fall_turn", 0) or 0)
            except Exception:
                marked_turn = 0
            exp = str(sr.get("aeldari_heroes_fall_expires_phase", "") or "").strip().upper()
            if phase_name == "FIGHT_PHASE" and (not exp or exp == "FIGHT_PHASE"):
                if not (marked_turn and current_turn and marked_turn != current_turn):
                    source = str(sr.get("aeldari_heroes_fall_source", "") or "HEROES' FALL").strip()
                    source = source or "HEROES' FALL"
                    try:
                        threshold = int(sr.get("aeldari_heroes_fall_threshold", 4) or 4)
                    except Exception:
                        threshold = 4
                    return {
                        "threshold": max(2, min(6, int(threshold))),
                        "source": source,
                    }
            if phase_name and phase_name != "FIGHT_PHASE":
                for key in (
                    "aeldari_heroes_fall_active",
                    "aeldari_heroes_fall_expires_phase",
                    "aeldari_heroes_fall_owner",
                    "aeldari_heroes_fall_turn",
                    "aeldari_heroes_fall_source",
                    "aeldari_heroes_fall_threshold",
                ):
                    sr.pop(key, None)
                self.special_rules = sr
        except Exception:
            return None
        return None

    def empowered_by_death_sources(self) -> list[str]:
        """Return source names for Empowered by Death style Fight First abilities."""
        cache_key = "empowered_by_death_sources"
        try:
            rule = self._aeldari_to_their_final_breath_rule()
            if rule is not None:
                source = str(rule.get("source", "") or "TO THEIR FINAL BREATH").strip() or "TO THEIR FINAL BREATH"
                return [source]
        except Exception:
            pass

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

    def has_enhancement_charge_after_advance_once_per_battle(self) -> bool:
        """Return True if this unit has a once-per-battle enhancement that can grant charge-after-Advance."""
        sr = getattr(self, "special_rules", None)
        return bool(isinstance(sr, dict) and sr.get("enhancement_charge_after_advance_once_per_battle"))

    def _enhancement_charge_after_advance_once_key(self) -> str:
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict):
            key = str(sr.get("enhancement_charge_after_advance_once_key", "") or "").strip().lower()
            if key:
                return key
        return "throne_mechanicum_of_skulls"

    def can_use_enhancement_charge_after_advance_once(self) -> bool:
        if not self.has_enhancement_charge_after_advance_once_per_battle():
            return False
        bearer = self._get_enhancement_bearer_model()
        if bearer is None:
            return False
        alive_attr = getattr(bearer, "is_alive", True)
        try:
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                return False
        except Exception:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            root = self
        key = self._enhancement_charge_after_advance_once_key()
        if bool(getattr(root, "has_used_unit_once_per_battle", lambda _k: False)(key)):
            return False
        if not bool(getattr(getattr(root, "round_state", None), "advanced_this_round", False)):
            return False
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("enhancement_charge_after_advance_once_active")):
            return False
        return True

    def activate_enhancement_charge_after_advance_once(self, *, game=None) -> bool:
        """Activate the once-per-battle charge-after-Advance enhancement until end of Charge phase."""
        if not self.can_use_enhancement_charge_after_advance_once():
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        key = self._enhancement_charge_after_advance_once_key()
        source = str(sr.get("enhancement_charge_after_advance_source", "") or "Throne Mechanicum of Skulls").strip()
        if not source:
            source = "Throne Mechanicum of Skulls"
        sr["enhancement_charge_after_advance_once_active"] = True
        sr["enhancement_charge_after_advance_once_expires_phase"] = "CHARGE_PHASE"
        sr["enhancement_charge_after_advance_source"] = source
        if game is not None:
            sr["enhancement_charge_after_advance_once_turn"] = int(getattr(game, "turn", 0) or 0)
            current_player = getattr(game, "get_current_player", lambda: None)()
            sr["enhancement_charge_after_advance_once_turn_owner"] = str(getattr(current_player, "id", "") or "")
        root.special_rules = sr
        root.mark_unit_once_per_battle_used(key, ability_name=source)
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.pop("leading_once_per_battle_advance_and_charge_specs", None)
        return True

    def _putrid_carapace_bearer_model(self):
        sr = getattr(self, "special_rules", None)
        bearer_id = ""
        if isinstance(sr, dict):
            bearer_id = str(
                sr.get("enhancement_putrid_carapace_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
        if bearer_id:
            for model in list(getattr(self, "models", []) or []):
                if str(get_entity_id(model) or "") != bearer_id:
                    continue
                return model
        return self._get_enhancement_bearer_model()

    def _putrid_carapace_once_key(self) -> str:
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict):
            key = str(sr.get("enhancement_putrid_carapace_once_key", "") or "").strip().lower()
            if key:
                return key
        return "putrid_carapace"

    def can_use_enhancement_putrid_carapace(self) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("enhancement_putrid_carapace")):
            return False
        key = self._putrid_carapace_once_key()
        if bool(getattr(self, "has_used_unit_once_per_battle", lambda _k: False)(key)):
            return False
        bearer = self._putrid_carapace_bearer_model()
        if bearer is None:
            return False
        alive_attr = getattr(bearer, "is_alive", True)
        if not bool(alive_attr() if callable(alive_attr) else alive_attr):
            return False
        base = int(getattr(bearer, "_base_wounds", getattr(bearer, "wounds", 0)) or 0)
        current = int(getattr(bearer, "wounds", 0) or 0)
        return bool(base > current)

    def activate_enhancement_putrid_carapace(self, *, heal_amount: int) -> int:
        """Consume Putrid Carapace once-per-battle and heal the bearer up to `heal_amount` lost wounds."""
        if not self.can_use_enhancement_putrid_carapace():
            return 0
        bearer = self._putrid_carapace_bearer_model()
        if bearer is None:
            return 0
        try:
            amount = int(heal_amount or 0)
        except Exception:
            amount = 0
        amount = max(0, int(amount))
        base = int(getattr(bearer, "_base_wounds", getattr(bearer, "wounds", 0)) or 0)
        current = int(getattr(bearer, "wounds", 0) or 0)
        lost = max(0, int(base - current))
        healed = min(int(amount), int(lost))
        if healed > 0:
            heal_fn = getattr(bearer, "heal", None)
            if callable(heal_fn):
                heal_fn(int(healed))
        sr = getattr(self, "special_rules", None)
        source = "Putrid Carapace"
        if isinstance(sr, dict):
            source = str(sr.get("enhancement_putrid_carapace_source", "") or source).strip() or source
        self.mark_unit_once_per_battle_used(self._putrid_carapace_once_key(), ability_name=source)
        return int(healed)

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

        # Temporary effect hook: Boon of Death (Mortarion).
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("boon_of_death_active"):
                phase_name = ""
                current_turn = 0
                try:
                    army = self.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                except Exception:
                    game = None
                if game is not None:
                    try:
                        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    except Exception:
                        phase_name = ""
                    try:
                        current_turn = int(getattr(game, "turn", 0) or 0)
                    except Exception:
                        current_turn = 0
                try:
                    marked_turn = int(sr.get("boon_of_death_turn", 0) or 0)
                except Exception:
                    marked_turn = 0
                if phase_name == "FIGHT_PHASE" and (not (marked_turn and current_turn and marked_turn != current_turn)):
                    source = str(sr.get("boon_of_death_source", "") or "Boon of Death").strip() or "Boon of Death"
                    try:
                        threshold = int(sr.get("boon_of_death_threshold", 2) or 2)
                    except Exception:
                        threshold = 2
                    return {
                        "threshold": max(2, min(6, int(threshold))),
                        "source": source,
                    }
                if phase_name and phase_name != "FIGHT_PHASE":
                    for key in (
                        "boon_of_death_active",
                        "boon_of_death_owner",
                        "boon_of_death_turn",
                        "boon_of_death_source",
                        "boon_of_death_threshold",
                        "boon_of_death_expires_phase",
                    ):
                        sr.pop(key, None)
                    self.special_rules = sr
        except Exception:
            pass

        # Temporary effect hook: DEATH FRENZY (Tyranids Invasion Fleet).
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("tyranids_death_frenzy_active"):
                phase_name = ""
                current_turn = 0
                try:
                    army = self.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                except Exception:
                    game = None
                if game is not None:
                    try:
                        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    except Exception:
                        phase_name = ""
                    try:
                        current_turn = int(getattr(game, "turn", 0) or 0)
                    except Exception:
                        current_turn = 0
                try:
                    marked_turn = int(sr.get("tyranids_death_frenzy_turn", 0) or 0)
                except Exception:
                    marked_turn = 0
                exp = str(sr.get("tyranids_death_frenzy_expires_phase", "") or "").strip().upper()
                if phase_name == "FIGHT_PHASE" and (not exp or exp == "FIGHT_PHASE"):
                    if not (marked_turn and current_turn and marked_turn != current_turn):
                        source = str(sr.get("tyranids_death_frenzy_source", "") or "DEATH FRENZY").strip()
                        source = source or "DEATH FRENZY"
                        try:
                            threshold = int(sr.get("tyranids_death_frenzy_threshold", 4) or 4)
                        except Exception:
                            threshold = 4
                        return {
                            "threshold": max(2, min(6, int(threshold))),
                            "source": source,
                        }
                if phase_name and phase_name != "FIGHT_PHASE":
                    for key in (
                        "tyranids_death_frenzy_active",
                        "tyranids_death_frenzy_threshold",
                        "tyranids_death_frenzy_expires_phase",
                        "tyranids_death_frenzy_source",
                        "tyranids_death_frenzy_owner",
                        "tyranids_death_frenzy_turn",
                    ):
                        sr.pop(key, None)
                    self.special_rules = sr
        except Exception:
            pass

        # Temporary effect hook: TO THEIR FINAL BREATH (Aeldari).
        try:
            rule = self._aeldari_to_their_final_breath_rule()
            if rule is not None:
                return rule
        except Exception:
            pass

        # Temporary effect hook: HEROES' FALL (Aeldari).
        try:
            rule = self._aeldari_heroes_fall_rule()
            if rule is not None:
                return rule
        except Exception:
            pass

        # Temporary effect hook: PARTING THE VEIL (Aeldari).
        try:
            rule = self._aeldari_parting_the_veil_rule()
            if rule is not None:
                return rule
        except Exception:
            pass

        # Adepta Sororitas: Penitent Host (Death Before Disgrace) temporary vow.
        army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
        as_mgr = getattr(army, "adepta_sororitas_detachments", None) if army is not None else None
        vow_rule_fn = (
            getattr(as_mgr, "desperate_for_redemption_melee_fight_on_death_rule", None)
            if as_mgr is not None
            else None
        )
        if callable(vow_rule_fn):
            vow_rule = vow_rule_fn(self, model=model)
            if isinstance(vow_rule, dict):
                try:
                    threshold = int(vow_rule.get("threshold", 0) or 0)
                except (TypeError, ValueError):
                    threshold = 0
                if 2 <= threshold <= 6:
                    source = (
                        str(vow_rule.get("source", "") or "Desperate for Redemption (Death Before Disgrace)").strip()
                        or "Desperate for Redemption (Death Before Disgrace)"
                    )
                    return {"threshold": int(threshold), "source": source}

        if cache_key in getattr(self, "_ability_cache", {}):
            cached_rule = self._ability_cache[cache_key]
            return self._apply_vindication_warden_of_honour_to_fight_on_death_rule(
                cached_rule,
                model=model,
            )

        rule = None
        def _parse_melee_fight_on_death_rule(name: str, desc: str) -> Optional[dict]:
            text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
            if not text:
                return None
            low = text.lower().replace("\u2019", "'")
            if "destroyed by a melee attack" not in low:
                return None
            if "has not fought this phase" not in low:
                return None
            if "roll one d6" not in low:
                return None
            if "do not remove" not in low:
                return None
            if (
                "can fight after the attacking unit has finished making its attacks" not in low
                and "can fight after the attacking model's unit has finished making its attacks" not in low
            ):
                return None
            m = re.search(r"on a (\d+)\+?", low)
            if not m:
                return None
            threshold = int(m.group(1))
            if threshold < 2 or threshold > 6:
                return None
            source = str(name or "Fight on death").strip() or "Fight on death"
            fortify_bonus = 0
            if "adding 1 to the result if units from your army have fortify takeover" in low:
                fortify_bonus = 1
            return {
                "threshold": threshold,
                "source": source,
                "fortify_takeover_bonus": int(fortify_bonus),
            }

        try:
            for name, desc in self._iter_ability_entries_for_rules(model=model):
                parsed = _parse_melee_fight_on_death_rule(name, desc)
                if parsed is None:
                    continue
                rule = parsed
                break
        except Exception:
            rule = None

        if rule is None:
            try:
                root = self.get_attached_unit_root()
            except Exception:
                root = self
            if root is not None:
                try:
                    members = list(root.get_attached_unit_members() or [])
                except Exception:
                    members = []
                if not members:
                    members = [root]
                members = sorted(members, key=lambda u: str(get_entity_id(u) or ""))
                for member in members:
                    if member is None or member is self:
                        continue
                    try:
                        entries = list(member._iter_ability_entries_for_rules(model=None))
                    except Exception:
                        entries = []
                    for name, desc in entries:
                        parsed = _parse_melee_fight_on_death_rule(name, desc)
                        if parsed is None:
                            continue
                        rule = parsed
                        break
                    if rule is not None:
                        break

        # Enhancement: Avenger's Crown (Vessels of Wrath) bearer-only melee fight-on-death on 2+.
        if rule is None and model is not None:
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict) and sr.get("enhancement_avengers_crown"):
                    bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
                    model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                    if not bearer_id or (model_id and model_id == bearer_id):
                        rule = {"threshold": 2, "source": "Avenger's Crown"}
            except Exception:
                rule = None

        # Enhancement: High Kahl (Hearthband) applies to models in the bearer's current unit.
        if rule is None and model is not None:
            try:
                root = self.get_attached_unit_root()
            except Exception:
                root = self
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = []
            if not members:
                members = [root]
            try:
                attached_models = list(root.get_attached_unit_models() or [])
            except Exception:
                attached_models = list(getattr(root, "models", []) or [])
            attached_model_ids = {
                str(getattr(m, "id", getattr(m, "_id", "")) or "")
                for m in list(attached_models or [])
                if m is not None
            }
            current_model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
            for member in members:
                if member is None:
                    continue
                sr = getattr(member, "special_rules", None)
                if not (isinstance(sr, dict) and sr.get("enhancement_high_kahl")):
                    continue
                bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
                if bearer_id and bearer_id not in attached_model_ids and bearer_id != current_model_id:
                    continue
                rule = {"threshold": 4, "source": "High Kâhl"}
                break

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return self._apply_vindication_warden_of_honour_to_fight_on_death_rule(
            rule,
            model=model,
        )

    def _vindication_warden_of_honour_vengeful_exhortation_roll_bonus(self, *, model: Optional['Model'] = None) -> int:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return 0
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        if sm_mgr is None or not bool(getattr(sm_mgr, "is_vindication_task_force", lambda: False)()):
            return 0

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = []
        if not members:
            members = [root]
        members = sorted(members, key=lambda u: str(get_entity_id(u) or ""))

        for member in members:
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not (isinstance(sr, dict) and bool(sr.get("enhancement_warden_of_honour"))):
                continue
            if bool(sr.get("enhancement_warden_of_honour_requires_bearer_leading", True)):
                if not bool(getattr(member, "is_attached_leader", False)):
                    continue
            bearer_alive = False
            bearer_id = str(
                sr.get("enhancement_warden_of_honour_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            if bearer_id:
                for candidate in list(getattr(member, "models", []) or []):
                    if str(get_entity_id(candidate) or "") != bearer_id:
                        continue
                    alive_attr = getattr(candidate, "is_alive", True)
                    bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    break
            if not bearer_alive:
                bearer = getattr(member, "_get_enhancement_bearer_model", lambda: None)()
                if bearer is not None:
                    alive_attr = getattr(bearer, "is_alive", True)
                    bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not bearer_alive:
                continue
            try:
                bonus = int(sr.get("enhancement_warden_of_honour_vengeful_exhortation_roll_bonus", 1) or 1)
            except Exception:
                bonus = 1
            return int(max(0, bonus))
        return 0

    def _apply_vindication_warden_of_honour_to_fight_on_death_rule(
        self,
        rule: Optional[dict],
        *,
        model: Optional['Model'] = None,
    ) -> Optional[dict]:
        if not isinstance(rule, dict):
            return rule
        source = str(rule.get("source", "") or "").strip().lower().replace("\u2019", "'")
        if "vengeful exhortation" not in source:
            return rule
        bonus = self._vindication_warden_of_honour_vengeful_exhortation_roll_bonus(model=model)
        if bonus <= 0:
            return rule
        adjusted = dict(rule)
        try:
            threshold = int(adjusted.get("threshold", 0) or 0)
        except Exception:
            threshold = 0
        if threshold > 0:
            adjusted["threshold"] = int(max(2, threshold - int(bonus)))
        source_text = str(adjusted.get("source", "") or "Vengeful Exhortation").strip() or "Vengeful Exhortation"
        adjusted["source"] = f"{source_text} + Warden of Honour"
        return adjusted

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

    def has_dark_ascension_aura(self) -> bool:
        """Return True if this unit has the Dark Ascension (Aura) ability."""
        if "dark_ascension_aura" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["dark_ascension_aura"])
        found, _ = self._find_ability_with_patterns(["dark ascension"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["dark_ascension_aura"] = bool(found)
        return bool(found)

    def has_dark_destiny(self) -> bool:
        """Return True if this unit has the Dark Destiny ability."""
        if "dark_destiny" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["dark_destiny"])
        found, _ = self._find_ability_with_patterns(["dark destiny"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["dark_destiny"] = bool(found)
        return bool(found)

    def has_bringers_of_change(self) -> bool:
        """Return True if this unit has the Bringers of Change ability."""
        if "bringers_of_change" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["bringers_of_change"])
        found, _ = self._find_ability_with_patterns(["bringers of change"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["bringers_of_change"] = bool(found)
        return bool(found)

    def has_daemonic_ordnance(self) -> bool:
        """Return True if this unit has the Daemonic Ordnance ability."""
        if "daemonic_ordnance" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["daemonic_ordnance"])
        found, _ = self._find_ability_with_patterns(["daemonic ordnance"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["daemonic_ordnance"] = bool(found)
        return bool(found)

    def has_warp_rift_firepower(self) -> bool:
        """Return True if this unit has the Warp Rift Firepower ability."""
        if "warp_rift_firepower" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["warp_rift_firepower"])
        found, _ = self._find_ability_with_patterns(["warp rift firepower"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["warp_rift_firepower"] = bool(found)
        return bool(found)

    def has_spirit_thief(self) -> bool:
        """Return True if this unit has the Spirit Thief ability."""
        if "spirit_thief" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["spirit_thief"])
        found, _ = self._find_ability_with_patterns(["spirit thief"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["spirit_thief"] = bool(found)
        return bool(found)

    def has_corrupt_machine_spirits(self) -> bool:
        """Return True if this unit has the Corrupt Machine Spirits ability."""
        if "corrupt_machine_spirits" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["corrupt_machine_spirits"])
        found, _ = self._find_ability_with_patterns(["corrupt machine spirits"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["corrupt_machine_spirits"] = bool(found)
        return bool(found)

    def has_surgeon_acolyte(self) -> bool:
        """Return True if this attached unit root has Surgeon Acolyte on any member."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and "surgeon_acolyte" in cache:
            return bool(cache["surgeon_acolyte"])

        found = False
        members = [root]
        try:
            members = list(root.get_attached_unit_members() or [root])
        except Exception:
            members = [root]
        for member in list(members or []):
            if member is None:
                continue
            find_fn = getattr(member, "_find_ability_with_patterns", None)
            if not callable(find_fn):
                continue
            try:
                member_found, _ = find_fn(["surgeon acolyte"])
            except Exception:
                member_found = False
            if member_found:
                found = True
                break

        if not isinstance(cache, dict):
            cache = {}
        cache["surgeon_acolyte"] = bool(found)
        root._ability_cache = cache
        return bool(found)

    def has_enrage_machine_spirits(self) -> bool:
        """Return True if this unit has the Enrage Machine Spirits ability."""
        if "enrage_machine_spirits" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["enrage_machine_spirits"])
        found, _ = self._find_ability_with_patterns(["enrage machine spirits"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["enrage_machine_spirits"] = bool(found)
        return bool(found)

    def has_voice_eater(self) -> bool:
        """Return True if this unit has the Voice Eater ability."""
        if "voice_eater" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["voice_eater"])
        found, _ = self._find_ability_with_patterns(["voice eater"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["voice_eater"] = bool(found)
        return bool(found)

    def has_enhanced_warriors(self) -> bool:
        """Return True if this unit has the Enhanced Warriors ability."""
        if "enhanced_warriors" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["enhanced_warriors"])
        found, _ = self._find_ability_with_patterns(["enhanced warriors"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["enhanced_warriors"] = bool(found)
        return bool(found)

    def get_enhanced_warriors_rule(self) -> Optional[dict]:
        """
        Return parsed rule info for Enhanced Warriors-like text:
        "If this unit is attached to a unit at the start of the battle, add 1 to the Strength
        characteristic of melee weapons equipped by Bodyguard models in that unit and add 1 to
        the Toughness characteristic of Bodyguard models in that unit."
        """
        root = self
        attached_to = getattr(self, "attached_to", None)
        if attached_to is not None:
            root = attached_to
        else:
            support_joined_to = getattr(self, "support_joined_to", None)
            if support_joined_to is not None:
                root = support_joined_to
        cache_key = "enhanced_warriors_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]
        in_progress_key = "_enhanced_warriors_rule_in_progress"
        if bool(getattr(root, in_progress_key, False)):
            return None
        setattr(root, in_progress_key, True)

        try:
            rule = None
            seen = set()

            def _iter_rule_entries(unit):
                # Use raw ability entries instead of active-ability iteration here to avoid
                # recursion through characteristic resolution while parsing this static rule text.
                for ab in list(getattr(unit, "possible_abilities", []) or []):
                    if isinstance(ab, str):
                        yield ab, ab
                        continue
                    if isinstance(ab, dict):
                        yield str(ab.get("name", "") or ""), str(ab.get("description", "") or "")
                        continue
                    yield getattr(ab, "name", "") or "", getattr(ab, "description", "") or ""

                enh = getattr(unit, "enhancement", None)
                if enh is not None:
                    name = getattr(enh, "name", "") or ""
                    desc = getattr(enh, "description", "") or ""
                    if name or desc:
                        yield name, desc

            try:
                members = list(root.get_attached_unit_members() or [])
            except RecursionError:
                return None
            except Exception:
                members = [root]
            if not members:
                members = [root]

            for unit in members:
                if unit is None:
                    continue
                for name, desc in _iter_rule_entries(unit):
                    text_src = desc or name or ""
                    if not text_src:
                        continue
                    key = (str(name or "").strip().lower(), unit._normalize_rules_text(text_src).lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    text = unit._normalize_rules_text(unit._strip_eligibility_prefix(text_src))
                    if not text:
                        continue
                    norm = text.replace("\u2019", "'").replace("\u0192?T", "'")
                    norm = norm.lower()
                    norm = re.sub(r"'s\b", "s", norm)
                    norm = re.sub(r"[^a-z0-9]+", " ", norm)
                    norm = re.sub(r"\s+", " ", norm).strip()
                    if "bodyguard models" not in norm:
                        continue
                    if "melee weapons equipped by bodyguard models" not in norm:
                        continue
                    if "add 1 to the strength characteristic" not in norm:
                        continue
                    if "add 1 to the toughness characteristic of bodyguard models" not in norm:
                        continue
                    if "attached to a unit at the start of the battle" not in norm:
                        continue
                    source = str(name or "Enhanced Warriors").strip() or "Enhanced Warriors"
                    rule = {
                        "source": source,
                        "ability_key": "enhanced_warriors",
                        "melee_strength_bonus": 1,
                        "toughness_bonus": 1,
                        "requires_attached": True,
                        "requires_start_of_battle_attachment": True,
                    }
                    break
                if rule is not None:
                    break

            if not hasattr(root, "_ability_cache"):
                root._ability_cache = {}
            root._ability_cache[cache_key] = rule
            return rule
        finally:
            setattr(root, in_progress_key, False)

    def get_enhanced_warriors_melee_strength_bonus(self, model=None) -> tuple[int, str]:
        """Return (bonus, source) for Enhanced Warriors melee Strength bonus for a specific model."""
        if model is None:
            return 0, ""
        root = self
        attached_to = getattr(self, "attached_to", None)
        if attached_to is not None:
            root = attached_to
        else:
            support_joined_to = getattr(self, "support_joined_to", None)
            if support_joined_to is not None:
                root = support_joined_to
        rule = root.get_enhanced_warriors_rule()
        if not rule:
            return 0, ""
        try:
            parent = getattr(model, "parent_unit", None)
        except Exception:
            parent = None
        if parent is None:
            return 0, ""
        # Applies only to bodyguard models in the attached unit (not Leader models).
        if parent is not root:
            return 0, ""
        try:
            leaders = list(getattr(root, "attached_leaders", []) or [])
        except Exception:
            leaders = []
        if not leaders:
            return 0, ""
        try:
            bonus = int(rule.get("melee_strength_bonus", 0) or 0)
        except Exception:
            bonus = 0
        if bonus <= 0:
            return 0, ""
        source = str(rule.get("source", "") or "Enhanced Warriors").strip() or "Enhanced Warriors"
        return int(bonus), source

    def get_enhanced_warriors_toughness_bonus(self, model=None) -> tuple[int, str]:
        """Return (bonus, source) for Enhanced Warriors Toughness bonus for a specific model."""
        if model is None:
            return 0, ""
        root = self
        attached_to = getattr(self, "attached_to", None)
        if attached_to is not None:
            root = attached_to
        else:
            support_joined_to = getattr(self, "support_joined_to", None)
            if support_joined_to is not None:
                root = support_joined_to
        rule = root.get_enhanced_warriors_rule()
        if not rule:
            return 0, ""
        try:
            parent = getattr(model, "parent_unit", None)
        except Exception:
            parent = None
        if parent is None or parent is not root:
            return 0, ""
        try:
            leaders = list(getattr(root, "attached_leaders", []) or [])
        except Exception:
            leaders = []
        if not leaders:
            return 0, ""
        try:
            bonus = int(rule.get("toughness_bonus", 0) or 0)
        except Exception:
            bonus = 0
        if bonus <= 0:
            return 0, ""
        source = str(rule.get("source", "") or "Enhanced Warriors").strip() or "Enhanced Warriors"
        return int(bonus), source

    def has_herald_of_the_apocalypse(self) -> bool:
        """Return True if this unit has the Herald of the Apocalypse ability."""
        if "herald_of_the_apocalypse" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["herald_of_the_apocalypse"])
        found, _ = self._find_ability_with_patterns(["herald of the apocalypse"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["herald_of_the_apocalypse"] = bool(found)
        return bool(found)

    def get_command_phase_vehicle_repair_hit_bonus_rule(self) -> Optional[dict]:
        """
        Return rule info for command-phase abilities that:
        - select one friendly VEHICLE within X"
        - heal it (typically D3)
        - grant +Hit until the start of your next Command phase

        Covers wording variants such as Master of Mechanisms and Blessing of the Omnissiah.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "command_phase_vehicle_repair_hit_bonus_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        seen: set[tuple[str, str]] = set()
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
                normalized_text = unit._normalize_rules_text(text_src)
                if not normalized_text:
                    continue
                key = (str(name or "").strip().lower(), normalized_text.lower())
                if key in seen:
                    continue
                seen.add(key)
                norm = normalized_text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                norm = re.sub(r"'s\b", "s", norm)
                norm = re.sub(r"[^a-z0-9]+", " ", norm)
                norm = re.sub(r"\s+", " ", norm).strip()
                if "command phase" not in norm:
                    continue
                if "select one friendly" not in norm:
                    continue
                if "vehicle" not in norm:
                    continue
                if "regains" not in norm or "lost wounds" not in norm:
                    continue
                if "hit roll" not in norm or "until the start of your next command phase" not in norm:
                    continue
                range_value = 3
                m_range = re.search(r"within\s+(\d+)", norm)
                if m_range:
                    try:
                        range_value = int(m_range.group(1) or 3)
                    except Exception:
                        range_value = 3
                heal_roll = ""
                heal_flat = 0
                m_heal = re.search(r"regains?\s+up\s+to\s+(\d+|d\d+)\s+lost wounds", norm)
                if m_heal:
                    token = str(m_heal.group(1) or "").strip().lower()
                    if token.startswith("d"):
                        heal_roll = token.upper()
                    else:
                        try:
                            heal_flat = int(token)
                        except Exception:
                            heal_flat = 0
                hit_bonus = 1
                m_hit = re.search(r"add\s+(\d+)\s+to\s+the\s+hit\s+roll", norm)
                if m_hit:
                    try:
                        hit_bonus = int(m_hit.group(1) or 1)
                    except Exception:
                        hit_bonus = 1
                source = str(name or "Master of Mechanisms").strip() or "Master of Mechanisms"
                rule = {
                    "source": source,
                    "range": int(range_value),
                    "heal_roll": str(heal_roll or ""),
                    "heal_flat": int(heal_flat or 0),
                    "hit_bonus": int(hit_bonus or 1),
                    "limit_once_per_turn": "only be selected for this ability once per turn" in norm,
                }
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def has_master_of_mechanisms(self) -> bool:
        """Return True if this unit has the Master of Mechanisms ability."""
        if "master_of_mechanisms" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["master_of_mechanisms"])
        found, _ = self._find_ability_with_patterns(["master of mechanisms"])
        if not found:
            found = bool(self.get_command_phase_vehicle_repair_hit_bonus_rule())
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["master_of_mechanisms"] = bool(found)
        return bool(found)

    def _attached_members_for_rule_scan(self) -> tuple["Unit", list]:
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
        return root, list(members)

    def _attached_unit_has_ability_patterns(self, *, cache_key: str, patterns: list[str]) -> bool:
        root, members = self._attached_members_for_rule_scan()
        if cache_key in getattr(root, "_ability_cache", {}):
            return bool(root._ability_cache[cache_key])
        found = False
        for member in list(members or []):
            if member is None:
                continue
            has_it, _ = member._find_ability_with_patterns(patterns)
            if has_it:
                found = True
                break
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = bool(found)
        return bool(found)

    def _iter_attached_models_with_ability_patterns(self, patterns: list[str]):
        _, members = self._attached_members_for_rule_scan()
        for member in list(members or []):
            if member is None:
                continue
            has_it, _ = member._find_ability_with_patterns(patterns)
            if not has_it:
                continue
            for model in list(getattr(member, "models", []) or []):
                try:
                    alive_attr = getattr(model, "is_alive", False)
                    alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                except Exception:
                    alive = False
                if alive:
                    yield model

    def has_seized_opportunity(self) -> bool:
        return self._attached_unit_has_ability_patterns(
            cache_key="seized_opportunity",
            patterns=["seized opportunity"],
        )

    def has_computational_mastermind(self) -> bool:
        return self._attached_unit_has_ability_patterns(
            cache_key="computational_mastermind",
            patterns=["computational mastermind"],
        )

    def has_geomantic_hunters(self) -> bool:
        return self._attached_unit_has_ability_patterns(
            cache_key="geomantic_hunters",
            patterns=["geomantic hunters"],
        )

    def has_resource_transmutation(self) -> bool:
        return self._attached_unit_has_ability_patterns(
            cache_key="resource_transmutation",
            patterns=["resource transmutation"],
        )

    def has_multiwave_comms_array(self) -> bool:
        return self._attached_unit_has_ability_patterns(
            cache_key="multiwave_comms_array",
            patterns=["multiwave comms array"],
        )

    def has_unhinged_vengeance(self) -> bool:
        return self._attached_unit_has_ability_patterns(
            cache_key="unhinged_vengeance",
            patterns=["unhinged vengeance"],
        )

    def get_resource_transmutation_model(self):
        models = list(self._iter_attached_models_with_ability_patterns(["resource transmutation"]) or [])
        if not models:
            return None
        try:
            models.sort(key=lambda m: str(get_entity_id(m) or ""))
        except Exception:
            pass
        return models[0]

    def get_unhinged_vengeance_model(self):
        models = list(self._iter_attached_models_with_ability_patterns(["unhinged vengeance"]) or [])
        if not models:
            return None
        try:
            models.sort(key=lambda m: str(get_entity_id(m) or ""))
        except Exception:
            pass
        return models[0]

    def get_computational_mastermind_models(self) -> list:
        models = list(self._iter_attached_models_with_ability_patterns(["computational mastermind"]) or [])
        try:
            models.sort(key=lambda m: str(get_entity_id(m) or ""))
        except Exception:
            pass
        return models

    def get_forgewrought_expertise_rule(self) -> Optional[dict]:
        """
        Return rule info for Forgewrought Expertise:
        - End of Movement: repair one friendly LEAGUES OF VOTANN VEHICLE/EXOFRAME/IRONKIN STEELJACKS unit within range.
        - Heal D3, or flat 3 if this unit contains an Ironkin Assistant model.
        - Each target unit can only be repaired once per turn.
        """
        root, members = self._attached_members_for_rule_scan()
        cache_key = "forgewrought_expertise_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        seen: set[tuple[str, str]] = set()
        for unit in list(members or []):
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                if not text_src:
                    continue
                normalized_text = unit._normalize_rules_text(text_src)
                if not normalized_text:
                    continue
                key = (str(name or "").strip().lower(), normalized_text.lower())
                if key in seen:
                    continue
                seen.add(key)
                norm = normalized_text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
                norm = re.sub(r"'s\b", "s", norm)
                norm = re.sub(r"[^a-z0-9]+", " ", norm)
                norm = re.sub(r"\s+", " ", norm).strip()
                if "end of your movement phase" not in norm:
                    continue
                if "repair one friendly leagues of votann" not in norm:
                    continue
                if "vehicle" not in norm or "exoframe" not in norm or "ironkin steeljacks" not in norm:
                    continue
                if "regains up to d3 lost wounds" not in norm:
                    continue
                if "each unit can only be repaired once per turn" not in norm:
                    continue
                range_value = 3
                m_range = re.search(r"within\s+(\d+)", norm)
                if m_range:
                    try:
                        range_value = int(m_range.group(1) or 3)
                    except Exception:
                        range_value = 3
                source = str(name or "Forgewrought Expertise").strip() or "Forgewrought Expertise"
                rule = {
                    "source": source,
                    "range": int(range_value),
                    "heal_roll": "D3",
                    "assistant_model_name": "Ironkin Assistant",
                    "assistant_heal_flat": 3,
                    "limit_once_per_turn": True,
                    "target_keywords": ("VEHICLE", "EXOFRAME", "IRONKIN STEELJACKS"),
                    "optional": True,
                }
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def has_forgewrought_expertise(self) -> bool:
        if "forgewrought_expertise" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["forgewrought_expertise"])
        found = bool(self.get_forgewrought_expertise_rule())
        if not found:
            found = self._attached_unit_has_ability_patterns(
                cache_key="forgewrought_expertise_name_scan",
                patterns=["forgewrought expertise"],
            )
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["forgewrought_expertise"] = bool(found)
        return bool(found)

    def has_truesilver_aegis_aura(self) -> bool:
        """Return True if this unit has Truesilver Aegis aura."""
        cache_key = "truesilver_aegis_aura"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found, _ = self._find_ability_with_patterns(["truesilver aegis"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def has_plough_through_the_enemy(self) -> bool:
        """Return True if this unit has the Plough Through the Enemy ability."""
        if "plough_through_the_enemy" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["plough_through_the_enemy"])
        found, _ = self._find_ability_with_patterns(["plough through the enemy"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["plough_through_the_enemy"] = bool(found)
        return bool(found)

    def has_reorder_reality(self) -> bool:
        """Return True if this unit has the Reorder Reality ability."""
        if "reorder_reality" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["reorder_reality"])
        found, _ = self._find_ability_with_patterns(["reorder reality"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["reorder_reality"] = bool(found)
        return bool(found)

    def has_siege_crawler(self) -> bool:
        """Return True if this unit has the Siege Crawler ability."""
        if "siege_crawler" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["siege_crawler"])
        found, _ = self._find_ability_with_patterns(["siege crawler"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["siege_crawler"] = bool(found)
        return bool(found)

    def has_siege_shield(self) -> bool:
        """Return True if this unit has the Siege Shield ability."""
        if "siege_shield" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["siege_shield"])
        found, _ = self._find_ability_with_patterns(["siege shield"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["siege_shield"] = bool(found)
        return bool(found)

    def has_soul_eater(self) -> bool:
        """Return True if this unit has the Soul Eater ability."""
        if "soul_eater" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["soul_eater"])
        found, _ = self._find_ability_with_patterns(["soul eater"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["soul_eater"] = bool(found)
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

    def has_guns_blazing(self) -> bool:
        """Check if the unit has the Guns Blazing datasheet ability."""
        if "guns_blazing" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["guns_blazing"])

        found, _ = self._find_ability_with_patterns(["guns blazing"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["guns_blazing"] = bool(found)
        return bool(found)

    def has_lord_of_the_death_guard(self) -> bool:
        """Check if the unit has the Lord of the Death Guard datasheet ability."""
        if "lord_of_the_death_guard" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["lord_of_the_death_guard"])
        found, _ = self._find_ability_with_patterns(["lord of the death guard"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["lord_of_the_death_guard"] = bool(found)
        return bool(found)

    def has_boon_of_death(self) -> bool:
        """Check if the unit has the Boon of Death datasheet ability."""
        if "boon_of_death" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["boon_of_death"])
        found, _ = self._find_ability_with_patterns(["boon of death"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["boon_of_death"] = bool(found)
        return bool(found)

    def has_inflamed_reprisal(self) -> bool:
        """Check if the unit has the Inflamed Reprisal datasheet ability."""
        if "inflamed_reprisal" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["inflamed_reprisal"])
        found, _ = self._find_ability_with_patterns(["inflamed reprisal"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["inflamed_reprisal"] = bool(found)
        return bool(found)

    def has_diseased_influence(self) -> bool:
        """Check if the unit has the Diseased Influence datasheet ability."""
        if "diseased_influence" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["diseased_influence"])
        found, _ = self._find_ability_with_patterns(["diseased influence"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["diseased_influence"] = bool(found)
        return bool(found)

    def has_explosive_blight(self) -> bool:
        """Check if the unit has the Explosive Blight datasheet ability."""
        if "explosive_blight" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["explosive_blight"])
        found, _ = self._find_ability_with_patterns(["explosive blight"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["explosive_blight"] = bool(found)
        return bool(found)

    def _lord_of_death_guard_turn_key(self, game=None) -> str:
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
        owner_id = str(getattr(current_player, "id", "") or "")
        owner_name = str(getattr(current_player, "name", "") or "")
        owner = owner_id or owner_name
        return f"{br}:{owner}"

    def lord_of_death_guard_used_this_turn(self, game=None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._lord_of_death_guard_turn_key(game)
        return str(sr.get("lord_of_death_guard_used_turn_key", "")) == key

    def mark_lord_of_death_guard_used(self, game=None, *, ability_name: str = "") -> None:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["lord_of_death_guard_used_turn_key"] = self._lord_of_death_guard_turn_key(game)
        if ability_name:
            sr["lord_of_death_guard_used_source"] = str(ability_name).strip()
        self.special_rules = sr

    def can_use_lord_of_death_guard(self, game=None) -> bool:
        if not self.has_lord_of_the_death_guard():
            return False
        try:
            if not self.is_alive() or not bool(getattr(self, "deployed", False)):
                return False
        except Exception:
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
        return not self.lord_of_death_guard_used_this_turn(game)

    def has_lethal_ichor(self) -> bool:
        """Check if the unit has the Lethal Ichor datasheet ability."""
        if "lethal_ichor" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["lethal_ichor"])
        found, _ = self._find_ability_with_patterns(["lethal ichor"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["lethal_ichor"] = bool(found)
        return bool(found)

    def has_curse_of_the_walking_pox(self) -> bool:
        """Check if the unit has the Curse of the Walking Pox datasheet ability."""
        if "curse_of_the_walking_pox" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["curse_of_the_walking_pox"])
        found, _ = self._find_ability_with_patterns(["curse of the walking pox"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["curse_of_the_walking_pox"] = bool(found)
        return bool(found)

    def has_extraction_of_fresh_disease(self) -> bool:
        """Check if the unit has the Extraction of Fresh Disease datasheet ability."""
        if "extraction_of_fresh_disease" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["extraction_of_fresh_disease"])
        found, _ = self._find_ability_with_patterns(["extraction of fresh disease"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["extraction_of_fresh_disease"] = bool(found)
        return bool(found)

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

    def has_insurmountable_odds(self) -> bool:
        """Check if the unit has the Insurmountable Odds detachment ability (Unending Swarm)."""
        if "insurmountable_odds" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["insurmountable_odds"])
        applies = False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
        if mgr is not None and callable(getattr(mgr, "insurmountable_odds_horde_move_applies", None)):
            try:
                applies = bool(mgr.insurmountable_odds_horde_move_applies(self))
            except Exception:
                applies = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["insurmountable_odds"] = bool(applies)
        return bool(applies)

    def has_righteous_zeal(self) -> bool:
        """Check if the unit has the Righteous Zeal datasheet ability."""
        if "righteous_zeal" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["righteous_zeal"])
        found, _ = self._find_ability_with_patterns(["righteous zeal"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["righteous_zeal"] = bool(found)
        return bool(found)

    def has_horde_move(self) -> bool:
        """Check if the unit has a Horde Move ability."""
        if 'horde_move' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['horde_move']

        found = bool(self.has_insurmountable_odds())
        if not found:
            found, _ = self._find_ability_with_patterns(["horde move"])
        if not found:
            found = bool(self.has_righteous_zeal())
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
        - Start-of-battle selected enemy unit with unit-wide Hit re-rolls vs that unit.

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

                classic_prey_selector = (
                    "start of the first battle round" in normalized
                    and "select one enemy unit to be this model s prey" in normalized
                )
                focused_hunters_selector = (
                    "start of the battle" in normalized
                    and "select one unit from your opponent s army" in normalized
                    and "until the end of the battle" in normalized
                )
                if not (classic_prey_selector or focused_hunters_selector):
                    continue

                repick_on_destroyed = (
                    "prey is destroyed" in normalized
                    and "select one new enemy unit" in normalized
                )

                # Pattern: start-of-battle chosen enemy, unit-wide hit re-rolls vs that unit.
                if (
                    focused_hunters_selector
                    and _has_phrase(normalized, "each time a model in this unit makes an attack", "makes an attack")
                    and _has_phrase(normalized, "targets that unit")
                    and _has_phrase(normalized, "re roll the hit roll", "reroll the hit roll")
                ):
                    source = str(name or "Prey selection").strip() or "Prey selection"
                    rule = {
                        "source": source,
                        "reroll_hit": True,
                        "reroll_wound": False,
                        "melee_only": False,
                        "repick_on_destroyed": bool(repick_on_destroyed),
                    }
                    break

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

    def get_singular_purpose_rule(self) -> Optional[dict]:
        """
        Detect TYRANIDS "Singular Purpose" text:
        - BR1 choose enemy unit: this model re-rolls Hit and Wound rolls vs that unit.
        - BR1 choose objective marker: while this model is within range, it has FNP 5+ and OC 15.

        Returns a rule dict with:
            - source: ability name
            - reroll_hit: bool
            - reroll_wound: bool
            - objective_feel_no_pain: int
            - objective_control: int
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "singular_purpose_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        def _norm(text: str) -> str:
            if not text:
                return ""
            normalized = self._normalize_rules_text(text)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            return normalized

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
                if "select one of the following" not in normalized:
                    continue
                if "select one enemy unit" not in normalized:
                    continue
                if "select one objective marker" not in normalized:
                    continue
                if "each time this model makes an attack" not in normalized:
                    continue
                if "targets that unit" not in normalized:
                    continue
                if not _has_phrase(normalized, "re roll the hit roll", "reroll the hit roll"):
                    continue
                if not _has_phrase(normalized, "re roll the wound roll", "reroll the wound roll"):
                    continue
                if "within range of that objective marker" not in normalized:
                    continue
                if "feel no pain 5" not in normalized:
                    continue
                if "objective control characteristic of 15" not in normalized:
                    continue

                source = str(name or "Singular Purpose").strip() or "Singular Purpose"
                rule = {
                    "source": source,
                    "reroll_hit": True,
                    "reroll_wound": True,
                    "objective_feel_no_pain": 5,
                    "objective_control": 15,
                }
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def get_exemplar_of_the_code_rule(self) -> Optional[dict]:
        """
        Detect abilities with text like:
        "At the start of the battle, select one unit from your opponent's army to be this model's quarry.
        Each time this model makes an attack that targets its quarry, you can re-roll the Wound roll.
        Each time this model's quarry is destroyed, you can select a new unit from your opponent's army to be its quarry."

        Returns a rule dict with:
            - source: ability name
            - reroll_wound: bool
            - repick_on_destroyed: bool
            - optional_repick_on_destroyed: bool
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "exemplar_of_the_code_rule"
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

                if "start of the battle" not in normalized and "start of the first battle round" not in normalized:
                    continue
                if (
                    "to be this model s quarry" not in normalized
                    and "to be this unit s quarry" not in normalized
                ):
                    continue
                if not _has_phrase(normalized, "targets its quarry", "targets that quarry"):
                    continue
                if not _has_phrase(normalized, "re roll the wound roll", "reroll the wound roll"):
                    continue

                repick_on_destroyed = (
                    "quarry is destroyed" in normalized
                    and _has_phrase(
                        normalized,
                        "select a new unit",
                        "select one new unit",
                        "select one new enemy unit",
                    )
                )
                optional_repick = (
                    bool(repick_on_destroyed)
                    and _has_phrase(
                        normalized,
                        "you can select a new unit",
                        "you can select one new unit",
                        "you can select one new enemy unit",
                    )
                )

                source = str(name or "Exemplar of the Code").strip() or "Exemplar of the Code"
                rule = {
                    "source": source,
                    "reroll_wound": True,
                    "repick_on_destroyed": bool(repick_on_destroyed),
                    "optional_repick_on_destroyed": bool(optional_repick),
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
        source_unit, source_sr = root._higher_duty_source_unit()
        if source_unit is not None and isinstance(source_sr, dict):
            try:
                trigger_range = int(source_sr.get("enhancement_higher_duty_trigger_range", 9) or 9)
            except Exception:
                trigger_range = 9
            try:
                normal_move = int(source_sr.get("enhancement_higher_duty_normal_move_distance", 6) or 6)
            except Exception:
                normal_move = 6
            source_name = (
                str(source_sr.get("enhancement_higher_duty_source", "") or "Higher Duty").strip() or "Higher Duty"
            )
            rule = {
                "range": int(max(1, trigger_range)),
                "source": source_name,
                "max_distance": int(max(1, normal_move)),
            }

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
                if "once per battle" in str(text or "").lower():
                    rule["once_per_battle"] = True
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

    def _higher_duty_source_unit(self):
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return None, None
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
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_higher_duty")):
                continue
            bearer = None
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
            if bearer_id:
                for model in list(getattr(member, "models", []) or []):
                    model_id = str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "")
                    if model_id == bearer_id:
                        bearer = model
                        break
            if bearer is None:
                get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                if callable(get_bearer):
                    try:
                        bearer = get_bearer()
                    except Exception:
                        bearer = None
            if bearer is None:
                continue
            try:
                alive_attr = getattr(bearer, "is_alive", True)
                bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            except Exception:
                bearer_alive = False
            if not bearer_alive:
                continue
            return member, sr
        return None, None

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

    def get_prophetic_sentinels_stratagem_discount_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Once per battle round, you can target this unit with the Fire Overwatch or Heroic Intervention Stratagem for 0CP."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "prophetic_sentinels_stratagem_discount_rule"
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
            if u is None:
                continue
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                key = (str(name or "").strip().lower(), u._normalize_rules_text(text_src).lower())
                if key in seen:
                    continue
                seen.add(key)
                normalized = u._normalize_rules_text(u._strip_eligibility_prefix(text_src))
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not u._PROPHETIC_SENTINELS_STRATAGEM_RE.fullmatch(normalized):
                    continue
                source = str(name or "Prophetic Sentinels").strip() or "Prophetic Sentinels"
                rule = {
                    "source": source,
                    "ability_key": "prophetic_sentinels_stratagem_discount",
                    "stratagems": ("OVERWATCH", "FIRE OVERWATCH", "HEROIC INTERVENTION"),
                    "limit": "battle_round",
                }
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def _prophetic_sentinels_battle_round_key(self, game=None) -> str:
        if game is None:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        return str(br)

    def prophetic_sentinels_used_this_battle_round(self, game=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._prophetic_sentinels_battle_round_key(game)
        if not key:
            return False
        return str(sr.get("prophetic_sentinels_used_battle_round", "") or "") == key

    def mark_prophetic_sentinels_used(self, game=None, *, source: str = "", stratagem_name: str = "") -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["prophetic_sentinels_used_battle_round"] = self._prophetic_sentinels_battle_round_key(game)
        if source:
            sr["prophetic_sentinels_used_source"] = str(source or "").strip()
        if stratagem_name:
            sr["prophetic_sentinels_used_stratagem"] = str(stratagem_name or "").strip()
        root.special_rules = sr

    def can_use_prophetic_sentinels_stratagem_discount(self, game=None, *, stratagem_name: str = "") -> bool:
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
        rule = root.get_prophetic_sentinels_stratagem_discount_rule()
        if not rule:
            return False
        if root.prophetic_sentinels_used_this_battle_round(game):
            return False
        name_u = str(stratagem_name or "").strip().upper()
        allowed = {str(v or "").strip().upper() for v in list(rule.get("stratagems", ()) or ()) if str(v or "").strip()}
        if name_u and allowed and name_u not in allowed:
            return False
        return True

    def _unit_is_dire_avengers_or_guardians(self, unit) -> bool:
        if unit is None:
            return False
        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any("DIRE AVENGERS")) or bool(has_any("DIRE AVENGER")):
                    return True
                if bool(has_any("GUARDIANS")) or bool(has_any("GUARDIAN")):
                    return True
            except Exception:
                pass
        name = str(getattr(unit, "name", "") or "").strip().lower()
        return "dire avenger" in name or "guardian" in name

    def _unit_is_storm_guardians(self, unit) -> bool:
        if unit is None:
            return False
        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any("STORM GUARDIANS")):
                    return True
            except Exception:
                pass
        name = str(getattr(unit, "name", "") or "").strip().lower()
        return "storm guardian" in name

    def _guardian_battlehost_overwatch_source_unit(self):
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return None, None
        if not self._unit_is_dire_avengers_or_guardians(root):
            return None, None
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
            if not isinstance(sr, dict):
                continue
            if not sr.get("enhancement_protector_of_paths"):
                continue
            attached_to = getattr(member, "attached_to", None)
            if attached_to is None:
                continue
            try:
                attached_root = attached_to.get_attached_unit_root()
            except Exception:
                attached_root = attached_to
            if attached_root is not root:
                continue
            get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
            bearer = get_bearer() if callable(get_bearer) else None
            if bearer is None:
                continue
            if not bool(getattr(bearer, "is_alive", True)):
                continue
            return member, sr
        return None, None

    def get_protector_of_paths_overwatch_rule(self) -> Optional[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "protector_of_paths_overwatch_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        source_unit, source_sr = root._guardian_battlehost_overwatch_source_unit()
        rule = None
        if source_unit is not None and isinstance(source_sr, dict):
            try:
                base_threshold = int(source_sr.get("enhancement_protector_of_paths_base_threshold", 5) or 5)
            except Exception:
                base_threshold = 5
            try:
                controlled_threshold = int(source_sr.get("enhancement_protector_of_paths_controlled_threshold", 4) or 4)
            except Exception:
                controlled_threshold = 4
            source = "Protector of the Paths"
            enhancement = getattr(source_unit, "enhancement", None)
            if enhancement is not None:
                source = str(getattr(enhancement, "name", "") or source).strip() or source
            rule = {
                "source": source,
                "ability_key": "protector_of_paths_overwatch",
                "stratagems": ("OVERWATCH", "FIRE OVERWATCH"),
                "limit": "battle_round",
                "base_threshold": int(max(2, base_threshold)),
                "controlled_threshold": int(max(2, controlled_threshold)),
            }
            try:
                leader_id = get_entity_id(source_unit)
            except Exception:
                leader_id = None
            if leader_id:
                rule["leader_id"] = str(leader_id)

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def _protector_of_paths_battle_round_key(self, game=None) -> str:
        if game is None:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        return str(br)

    def protector_of_paths_used_this_battle_round(self, game=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._protector_of_paths_battle_round_key(game)
        if not key:
            return False
        return str(sr.get("protector_of_paths_used_battle_round", "") or "") == key

    def mark_protector_of_paths_used(self, game=None, *, source: str = "", stratagem_name: str = "") -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["protector_of_paths_used_battle_round"] = self._protector_of_paths_battle_round_key(game)
        if source:
            sr["protector_of_paths_used_source"] = str(source or "").strip()
        if stratagem_name:
            sr["protector_of_paths_used_stratagem"] = str(stratagem_name or "").strip()
        root.special_rules = sr

    def can_use_protector_of_paths_overwatch(self, game=None, *, stratagem_name: str = "") -> bool:
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
        rule = root.get_protector_of_paths_overwatch_rule()
        if not rule:
            return False
        if root.protector_of_paths_used_this_battle_round(game):
            return False
        name_u = str(stratagem_name or "").strip().upper()
        allowed = {str(v or "").strip().upper() for v in list(rule.get("stratagems", ()) or ()) if str(v or "").strip()}
        if name_u and allowed and name_u not in allowed:
            return False
        return True

    def get_protector_of_paths_overwatch_hit_threshold(self, *, enemy_unit=None, game=None) -> int:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        rule = root.get_protector_of_paths_overwatch_rule()
        if not rule:
            return 0
        try:
            base_threshold = int(rule.get("base_threshold", 0) or 0)
        except Exception:
            base_threshold = 0
        if base_threshold <= 0:
            return 0
        try:
            controlled_threshold = int(rule.get("controlled_threshold", 0) or 0)
        except Exception:
            controlled_threshold = 0
        if controlled_threshold <= 0:
            return int(base_threshold)
        game_map = None
        try:
            game_obj = game
            if game_obj is None:
                game_obj = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
            game_map = getattr(game_obj, "map", None) if game_obj is not None else None
        except Exception:
            game_map = None
        try:
            within_controlled = bool(root._within_controlled_objective_range(game_map))
        except Exception:
            within_controlled = False
        if within_controlled:
            return int(controlled_threshold)
        return int(base_threshold)

    def _guardian_battlehost_breath_source_unit(self):
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return None, None
        if not self._unit_is_storm_guardians(root):
            return None, None
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
            if not isinstance(sr, dict):
                continue
            if not sr.get("enhancement_breath_of_vaul"):
                continue
            attached_to = getattr(member, "attached_to", None)
            if attached_to is None:
                continue
            try:
                attached_root = attached_to.get_attached_unit_root()
            except Exception:
                attached_root = attached_to
            if attached_root is not root:
                continue
            get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
            bearer = get_bearer() if callable(get_bearer) else None
            if bearer is None:
                continue
            if not bool(getattr(bearer, "is_alive", True)):
                continue
            return member, sr
        return None, None

    def can_use_breath_of_vaul_flamer_attacks_reroll(self, *, model=None, weapon_name: str = "") -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        source_unit, source_sr = root._guardian_battlehost_breath_source_unit()
        if source_unit is None or not isinstance(source_sr, dict):
            return False
        if model is not None:
            if not bool(getattr(model, "is_alive", True)):
                return False
            parent = getattr(model, "parent_unit", None)
            if parent is None:
                return False
            try:
                parent_root = parent.get_attached_unit_root()
            except Exception:
                parent_root = parent
            if parent_root is not root:
                return False
        names = [str(v or "").strip() for v in list(source_sr.get("enhancement_breath_of_vaul_flamer_weapon_names", []) or []) if str(v or "").strip()]
        if not names:
            names = ["flamer"]
        weapon = str(weapon_name or "").strip()
        if not weapon:
            return False
        if hasattr(root, "_weapon_name_matches"):
            return bool(root._weapon_name_matches(names, weapon))
        wlow = weapon.lower()
        return any(str(name).lower() in wlow for name in names)

    def can_use_breath_of_vaul_fusion_damage_reroll(self, *, model=None, weapon_name: str = "") -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        source_unit, source_sr = root._guardian_battlehost_breath_source_unit()
        if source_unit is None or not isinstance(source_sr, dict):
            return False
        if model is not None:
            if not bool(getattr(model, "is_alive", True)):
                return False
            parent = getattr(model, "parent_unit", None)
            if parent is None:
                return False
            try:
                parent_root = parent.get_attached_unit_root()
            except Exception:
                parent_root = parent
            if parent_root is not root:
                return False
        names = [str(v or "").strip() for v in list(source_sr.get("enhancement_breath_of_vaul_fusion_weapon_names", []) or []) if str(v or "").strip()]
        if not names:
            names = ["fusion gun"]
        weapon = str(weapon_name or "").strip()
        if not weapon:
            return False
        if hasattr(root, "_weapon_name_matches"):
            return bool(root._weapon_name_matches(names, weapon))
        wlow = weapon.lower()
        return any(str(name).lower() in wlow for name in names)

    def get_snarling_protector_heroic_intervention_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "You can target this model with the Heroic Intervention Stratagem for 0CP, and can do so even if you have
        already targeted a different unit with that Stratagem this phase."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "snarling_protector_heroic_intervention_rule"
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
            if u is None:
                continue
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                key = (str(name or "").strip().lower(), u._normalize_rules_text(text_src).lower())
                if key in seen:
                    continue
                seen.add(key)
                normalized = u._normalize_rules_text(u._strip_eligibility_prefix(text_src))
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not u._SNARLING_PROTECTOR_HEROIC_RE.search(normalized):
                    continue
                source = str(name or "Snarling Protector").strip() or "Snarling Protector"
                rule = {
                    "source": source,
                    "ability_key": "snarling_protector_heroic_intervention",
                }
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def can_use_snarling_protector_heroic_intervention(self, game=None) -> bool:
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
        return bool(root.get_snarling_protector_heroic_intervention_rule())

    def get_destroyer_of_futures_overwatch_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time you target this unit with Fire Overwatch, hits are scored on 5+, or 4+ when the target is
        within 9\" of one or more friendly Thousand Sons Psyker units."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "destroyer_of_futures_overwatch_rule"
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
            if u is None:
                continue
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                key = (str(name or "").strip().lower(), u._normalize_rules_text(text_src).lower())
                if key in seen:
                    continue
                seen.add(key)
                normalized = u._normalize_rules_text(u._strip_eligibility_prefix(text_src))
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = u._DESTROYER_OF_FUTURES_OVERWATCH_RE.fullmatch(normalized)
                if m:
                    try:
                        base_threshold = int(m.group("base") or 0)
                    except Exception:
                        base_threshold = 0
                    try:
                        near_threshold = int(m.group("near") or 0)
                    except Exception:
                        near_threshold = 0
                    try:
                        range_value = float(m.group("range") or 0)
                    except Exception:
                        range_value = 0.0
                    if base_threshold <= 0 or near_threshold <= 0:
                        continue
                    source = str(name or "Destroyer of Futures").strip() or "Destroyer of Futures"
                    rule = {
                        "source": source,
                        "base_threshold": int(base_threshold),
                        "near_threshold": int(near_threshold),
                        "range": float(range_value or 0.0),
                    }
                    break

                m_fortify = u._FORTIFY_OVERWATCH_RE.fullmatch(normalized)
                if m_fortify:
                    try:
                        base_threshold = int(m_fortify.group("base") or 0)
                    except Exception:
                        base_threshold = 0
                    try:
                        fortify_threshold = int(m_fortify.group("fortify") or 0)
                    except Exception:
                        fortify_threshold = 0
                    if base_threshold <= 0 or fortify_threshold <= 0:
                        continue
                    source = str(name or "Overwatch").strip() or "Overwatch"
                    rule = {
                        "source": source,
                        "base_threshold": int(base_threshold),
                        "fortify_takeover_threshold": int(fortify_threshold),
                    }
                    break

                m_simple = u._OVERWATCH_HIT_THRESHOLD_RE.fullmatch(normalized)
                if not m_simple:
                    continue
                try:
                    threshold = int(
                        m_simple.group("threshold_pre")
                        or m_simple.group("threshold_post")
                        or 0
                    )
                except Exception:
                    threshold = 0
                if threshold <= 0:
                    continue
                source = str(name or "Overwatch").strip() or "Overwatch"
                rule = {
                    "source": source,
                    "base_threshold": int(threshold),
                }
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def get_destroyer_of_futures_overwatch_hit_threshold(self, *, enemy_unit=None, game=None) -> int:
        """
        Return the hit threshold used by Overwatch from Destroyer of Futures.
        Returns 0 when the rule does not apply.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        rule = root.get_destroyer_of_futures_overwatch_rule()
        if not rule:
            return 0
        try:
            base_threshold = int(rule.get("base_threshold", 0) or 0)
        except Exception:
            base_threshold = 0
        if base_threshold <= 0:
            return 0
        try:
            near_threshold = int(rule.get("near_threshold", 0) or 0)
        except Exception:
            near_threshold = 0
        fortify_threshold = int(rule.get("fortify_takeover_threshold", 0) or 0)
        if near_threshold <= 0:
            if fortify_threshold > 0:
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                eff_mgr = getattr(army, "prioritised_efficiency", None) if army is not None else None
                if eff_mgr is not None and callable(getattr(eff_mgr, "is_fortify_takeover", None)):
                    try:
                        if eff_mgr.is_fortify_takeover():
                            return int(fortify_threshold)
                    except Exception:
                        pass
            return int(base_threshold)
        if enemy_unit is None:
            return int(base_threshold)
        try:
            game_obj = game
            if game_obj is None:
                game_obj = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
        except Exception:
            game_obj = game
        game_map = getattr(game_obj, "map", None) if game_obj is not None else None
        if game_map is None:
            return int(base_threshold)
        try:
            enemy_root = enemy_unit.get_attached_unit_root()
        except Exception:
            enemy_root = enemy_unit
        if enemy_root is None:
            return int(base_threshold)
        try:
            near_range = float(rule.get("range", 0.0) or 0.0)
        except Exception:
            near_range = 0.0
        if near_range <= 0:
            return int(base_threshold)

        try:
            army = root.get_parent_army()
            friendly_units = list(getattr(army, "units", []) or []) if army is not None else []
        except Exception:
            friendly_units = []
        seen = set()
        for friendly in list(friendly_units or []):
            if friendly is None:
                continue
            try:
                f_root = friendly.get_attached_unit_root()
            except Exception:
                f_root = friendly
            if f_root is None:
                continue
            fid = str(get_entity_id(f_root) or "")
            if fid and fid in seen:
                continue
            if fid:
                seen.add(fid)
            if f_root is root:
                continue
            try:
                if not f_root.is_alive() or not getattr(f_root, "deployed", True):
                    continue
            except Exception:
                continue
            try:
                if f_root.is_in_reserves() or f_root.is_embarked:
                    continue
            except Exception:
                pass
            try:
                has_ts = bool(f_root.has_any_keyword("THOUSAND SONS"))
            except Exception:
                has_ts = False
            try:
                has_psyker = bool(f_root.has_any_keyword("PSYKER"))
            except Exception:
                has_psyker = False
            if not (has_ts and has_psyker):
                continue
            try:
                dist = float(game_map.get_distance_between_units(f_root, enemy_root))
            except Exception:
                continue
            if dist <= float(near_range) + 1e-6:
                return int(near_threshold)
        return int(base_threshold)

    def get_daemonforge_counter_offensive_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Once per Fight phase, one unit from your army with this ability can be targeted with the Counter-offensive
        Stratagem for 0CP, even if you have already targeted a different unit with that Stratagem this phase."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "daemonforge_counter_offensive_rule"
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
            if u is None:
                continue
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
                norm = text.replace("\u2019", "'").replace("\u0192?T", "'")
                norm = norm.lower()
                norm = re.sub(r"'s\b", "s", norm)
                norm = re.sub(r"[^a-z0-9]+", " ", norm)
                norm = re.sub(r"\s+", " ", norm).strip()
                if "counter offensive" not in norm or "stratagem" not in norm:
                    continue
                if "0cp" not in norm:
                    continue
                if "once per fight phase" not in norm:
                    continue
                source = str(name or "Daemonforge").strip() or "Daemonforge"
                rule = {
                    "source": source,
                    "ability_key": "daemonforge_counter_offensive",
                }
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

    def get_guardians_of_the_machine_heroic_intervention_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time an enemy unit ends a charge move ... you can target this model's unit with the Heroic
        Intervention Stratagem for 0CP, and can do so even if you already targeted another unit this phase."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "guardians_of_the_machine_heroic_intervention_rule"
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
            if u is None:
                continue
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
                norm = text.replace("\u2019", "'").replace("\u0192?T", "'")
                norm = norm.lower()
                norm = re.sub(r"'s\b", "s", norm)
                norm = re.sub(r"[^a-z0-9]+", " ", norm)
                norm = re.sub(r"\s+", " ", norm).strip()
                if "heroic intervention" not in norm or "stratagem" not in norm:
                    continue
                if "0cp" not in norm:
                    continue
                if "enemy unit ends a charge move" not in norm:
                    continue
                if "engagement range" not in norm or "vehicle" not in norm:
                    continue
                if "within 6" not in norm:
                    continue
                source = str(name or "Guardians of the Machine").strip() or "Guardians of the Machine"
                rule = {
                    "source": source,
                    "range": 6,
                    "ability_key": "guardians_of_the_machine_heroic_intervention",
                }
                break
            if rule is not None:
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

    def get_selfless_protector_rule(self) -> Optional[dict]:
        """
        Return rule info for Selfless Protector-like abilities:
        "Each time a ranged attack is allocated to an Imperial Knights model from your army,
        if that model is not fully visible to every model in the attacking unit because of this Knight Defender model,
        that model has the Benefit of Cover and a 4+ invulnerable save against that attack."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "selfless_protector_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None

        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        else:
            models = list(getattr(root, "models", []) or [])

        def _normalize_selfless_text(text_src: str) -> str:
            text_src = root._strip_eligibility_prefix(text_src)
            normalized = root._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            return normalized

        iter_model_entries = getattr(root, "_iter_model_specific_ability_entries", None)
        if callable(iter_model_entries):
            for model in models:
                if model is None:
                    continue
                for name, desc in iter_model_entries(model):
                    text_src = desc or name or ""
                    if not text_src:
                        continue
                    normalized = _normalize_selfless_text(text_src)
                    if not root._SELFLESS_PROTECTOR_RE.fullmatch(normalized):
                        continue
                    source = str(name or "Selfless Protector").strip() or "Selfless Protector"
                    rule = {
                        "source": source,
                        "model_id": str(get_entity_id(model) or ""),
                        "invulnerable_save": 4,
                    }
                    break
                if rule is not None:
                    break

        if rule is None:
            for name, desc in root._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                normalized = _normalize_selfless_text(text_src)
                if not root._SELFLESS_PROTECTOR_RE.fullmatch(normalized):
                    continue
                source = str(name or "Selfless Protector").strip() or "Selfless Protector"
                source_model_id = ""
                for model in models:
                    if model is None or not bool(getattr(model, "is_alive", True)):
                        continue
                    source_model_id = str(get_entity_id(model) or "")
                    if source_model_id:
                        break
                rule = {
                    "source": source,
                    "model_id": source_model_id,
                    "invulnerable_save": 4,
                }
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

    def can_use_guardians_of_the_machine_heroic_intervention(self, game=None, enemy_unit=None) -> bool:
        """Return True if Guardians of the Machine can grant Heroic Intervention for 0CP right now."""
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
        rule = root.get_guardians_of_the_machine_heroic_intervention_rule()
        if not rule:
            return False
        if enemy_unit is None:
            return False
        if game is None:
            try:
                game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return False
        try:
            enemy_root = enemy_unit.get_attached_unit_root()
        except Exception:
            enemy_root = enemy_unit
        if enemy_root is None:
            return False
        try:
            if root.get_parent_army() == enemy_root.get_parent_army():
                return False
        except Exception:
            pass
        try:
            if not enemy_root.is_alive() or not getattr(enemy_root, "deployed", True):
                return False
        except Exception:
            return False
        try:
            if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                return False
        except Exception:
            pass
        try:
            rng = float(rule.get("range", 6) or 6)
        except Exception:
            rng = 6.0
        try:
            dist = float(game_map.get_distance_between_units(root, enemy_root))
        except Exception:
            return False
        if dist > (rng + 1e-6):
            return False

        try:
            army = root.get_parent_army()
            units = list(getattr(army, "units", []) or []) if army is not None else []
        except Exception:
            units = []
        seen_ids: set[str] = set()
        for u in units:
            if u is None:
                continue
            try:
                v_root = u.get_attached_unit_root()
            except Exception:
                v_root = u
            uid = str(get_entity_id(v_root) or "")
            if uid and uid in seen_ids:
                continue
            if uid:
                seen_ids.add(uid)
            if v_root is None:
                continue
            try:
                if not v_root.is_alive() or not getattr(v_root, "deployed", True):
                    continue
                if v_root.is_in_reserves() or v_root.is_embarked:
                    continue
            except Exception:
                continue
            try:
                is_vehicle = bool(v_root.has_keyword("VEHICLE") or v_root.has_any_keyword("VEHICLE"))
            except Exception:
                is_vehicle = False
            if not is_vehicle:
                continue
            try:
                if game_map.is_within_engagement_range(v_root, enemy_root):
                    return True
            except Exception:
                continue
        return False

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
        total_bonus = 0
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        try:
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        except Exception:
            game = None
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        master_of_manoeuvre_bonus = 0
        master_of_manoeuvre_bonus_fn = (
            getattr(sm_mgr, "company_of_hunters_master_of_manoeuvre_strategic_reserves_round_bonus", None)
            if sm_mgr is not None
            else None
        )
        if callable(master_of_manoeuvre_bonus_fn):
            try:
                master_of_manoeuvre_bonus = int(master_of_manoeuvre_bonus_fn(root, game=game) or 0)
            except (TypeError, ValueError):
                master_of_manoeuvre_bonus = 0
        if master_of_manoeuvre_bonus > 0:
            total_bonus += int(master_of_manoeuvre_bonus)
        shadowmark_hunters_instincts_bonus = 0
        shadowmark_hunters_instincts_bonus_fn = (
            getattr(sm_mgr, "shadowmark_talon_hunters_instincts_strategic_reserves_round_bonus", None)
            if sm_mgr is not None
            else None
        )
        if callable(shadowmark_hunters_instincts_bonus_fn):
            try:
                shadowmark_hunters_instincts_bonus = int(
                    shadowmark_hunters_instincts_bonus_fn(root, game=game) or 0
                )
            except (TypeError, ValueError):
                shadowmark_hunters_instincts_bonus = 0
        if shadowmark_hunters_instincts_bonus > 0:
            total_bonus += int(shadowmark_hunters_instincts_bonus)
        spearpoint_chogorian_huntmaster_bonus = 0
        spearpoint_chogorian_huntmaster_bonus_fn = (
            getattr(sm_mgr, "spearpoint_chogorian_huntmaster_strategic_reserves_round_bonus", None)
            if sm_mgr is not None
            else None
        )
        if callable(spearpoint_chogorian_huntmaster_bonus_fn):
            try:
                spearpoint_chogorian_huntmaster_bonus = int(
                    spearpoint_chogorian_huntmaster_bonus_fn(root, game=game) or 0
                )
            except (TypeError, ValueError):
                spearpoint_chogorian_huntmaster_bonus = 0
        if spearpoint_chogorian_huntmaster_bonus > 0:
            total_bonus += int(spearpoint_chogorian_huntmaster_bonus)
        stormlance_hunters_instincts_bonus = 0
        stormlance_hunters_instincts_bonus_fn = (
            getattr(sm_mgr, "stormlance_hunters_instincts_strategic_reserves_round_bonus", None)
            if sm_mgr is not None
            else None
        )
        if callable(stormlance_hunters_instincts_bonus_fn):
            try:
                stormlance_hunters_instincts_bonus = int(
                    stormlance_hunters_instincts_bonus_fn(root, game=game) or 0
                )
            except (TypeError, ValueError):
                stormlance_hunters_instincts_bonus = 0
        if stormlance_hunters_instincts_bonus > 0:
            total_bonus += int(stormlance_hunters_instincts_bonus)
        inner_circle_deathwing_assault_bonus = 0
        inner_circle_deathwing_assault_bonus_fn = (
            getattr(sm_mgr, "inner_circle_deathwing_assault_strategic_reserves_round_bonus", None)
            if sm_mgr is not None
            else None
        )
        if callable(inner_circle_deathwing_assault_bonus_fn):
            try:
                inner_circle_deathwing_assault_bonus = int(
                    inner_circle_deathwing_assault_bonus_fn(root, game=game) or 0
                )
            except (TypeError, ValueError):
                inner_circle_deathwing_assault_bonus = 0
        if inner_circle_deathwing_assault_bonus > 0:
            total_bonus += int(inner_circle_deathwing_assault_bonus)
        wrath_of_the_rock_deathwing_assault_bonus = 0
        wrath_of_the_rock_deathwing_assault_bonus_fn = (
            getattr(sm_mgr, "wrath_of_the_rock_deathwing_assault_strategic_reserves_round_bonus", None)
            if sm_mgr is not None
            else None
        )
        if callable(wrath_of_the_rock_deathwing_assault_bonus_fn):
            try:
                wrath_of_the_rock_deathwing_assault_bonus = int(
                    wrath_of_the_rock_deathwing_assault_bonus_fn(root, game=game) or 0
                )
            except (TypeError, ValueError):
                wrath_of_the_rock_deathwing_assault_bonus = 0
        if wrath_of_the_rock_deathwing_assault_bonus > 0:
            total_bonus += int(wrath_of_the_rock_deathwing_assault_bonus)
        try:
            rule = root.get_strategic_reserves_round_bonus_rule()
        except Exception:
            rule = None
        if rule:
            source_name = str(rule.get("source", "") or "").strip().lower() if isinstance(rule, dict) else ""
            if (
                master_of_manoeuvre_bonus > 0
                and source_name in {"master of manoeuvre", "master of maneuver"}
            ):
                rule = None
        if rule:
            try:
                started = bool(getattr(root, "_started_in_reserves", False))
            except Exception:
                started = False
            if started:
                try:
                    in_strategic = bool(getattr(root, "is_in_strategic_reserves", lambda: False)())
                except Exception:
                    in_strategic = False
                if in_strategic:
                    try:
                        total_bonus += int(rule.get("round_bonus", 1) or 0)
                    except Exception:
                        pass

        try:
            sr = getattr(root, "special_rules", None)
        except Exception:
            sr = None
        if isinstance(sr, dict) and bool(sr.get("enhancement_sublime_prescience_active")):
            try:
                in_strategic = bool(getattr(root, "is_in_strategic_reserves", lambda: False)())
            except Exception:
                in_strategic = False
            if in_strategic:
                active = True
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                except Exception:
                    game = None
                owner_id = str(sr.get("enhancement_sublime_prescience_turn_owner", "") or "")
                try:
                    turn = int(sr.get("enhancement_sublime_prescience_turn", 0) or 0)
                except Exception:
                    turn = 0
                expires_phase = str(sr.get("enhancement_sublime_prescience_expires_phase", "") or "").strip().upper()
                if game is not None:
                    try:
                        current_player = getattr(game, "get_current_player", lambda: None)()
                    except Exception:
                        current_player = None
                    current_owner = str(getattr(current_player, "id", "") or "")
                    try:
                        current_turn = int(getattr(game, "turn", 0) or 0)
                    except Exception:
                        current_turn = 0
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    if owner_id and current_owner and owner_id != current_owner:
                        active = False
                    if active and turn and current_turn and turn != current_turn:
                        active = False
                    if active and expires_phase and phase_name and expires_phase != phase_name:
                        active = False
                if active:
                    try:
                        total_bonus += int(sr.get("enhancement_sublime_prescience_round_bonus", 1) or 0)
                    except Exception:
                        pass

        ae_mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
        ride_bonus_fn = getattr(ae_mgr, "ride_the_wind_strategic_reserves_round_bonus", None) if ae_mgr is not None else None
        if callable(ride_bonus_fn):
            try:
                total_bonus += int(ride_bonus_fn(root, game=game) or 0)
            except Exception:
                pass
        return max(0, int(total_bonus or 0))

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

    def can_use_daemonforge_counter_offensive(self, game=None) -> bool:
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
        return bool(root.get_daemonforge_counter_offensive_rule())

    def _intraneural_biotech_source_unit(self):
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return None, None
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
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_intraneural_biotech", False)):
                continue
            bearer = None
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
            if bearer_id:
                for model in list(getattr(member, "models", []) or []):
                    model_id = str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "")
                    if model_id == bearer_id:
                        bearer = model
                        break
            if bearer is None:
                get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                if callable(get_bearer):
                    try:
                        bearer = get_bearer()
                    except Exception:
                        bearer = None
            if bearer is None:
                continue
            try:
                alive_attr = getattr(bearer, "is_alive", True)
                bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            except Exception:
                bearer_alive = False
            if not bearer_alive:
                continue
            return member, sr
        return None, None

    def get_intraneural_biotech_stratagem_rule(self) -> Optional[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "intraneural_biotech_stratagem_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        source_unit, source_sr = root._intraneural_biotech_source_unit()
        if source_unit is not None and isinstance(source_sr, dict):
            enhancement = getattr(source_unit, "enhancement", None)
            source = str(getattr(enhancement, "name", "") or "Intraneural Biotech").strip() or "Intraneural Biotech"
            stratagems = [
                str(v or "").strip().upper()
                for v in list(source_sr.get("enhancement_intraneural_biotech_stratagems", ("HEROIC INTERVENTION", "COUNTER-OFFENSIVE")) or ())
                if str(v or "").strip()
            ]
            if not stratagems:
                stratagems = ["HEROIC INTERVENTION", "COUNTER-OFFENSIVE"]
            rule = {
                "source": source,
                "ability_key": "intraneural_biotech_stratagem_discount",
                "stratagems": tuple(stratagems),
                "limit": str(source_sr.get("enhancement_intraneural_biotech_limit", "battle_round") or "battle_round").strip().lower(),
            }
            try:
                source_id = get_entity_id(source_unit)
            except Exception:
                source_id = None
            if source_id:
                rule["source_unit_id"] = str(source_id)

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def _intraneural_biotech_battle_round_key(self, game=None) -> str:
        if game is None:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        return str(br)

    def intraneural_biotech_used_this_battle_round(self, game=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._intraneural_biotech_battle_round_key(game)
        if not key:
            return False
        return str(sr.get("intraneural_biotech_used_battle_round", "") or "") == key

    def mark_intraneural_biotech_used(self, game=None, *, source: str = "", stratagem_name: str = "") -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["intraneural_biotech_used_battle_round"] = self._intraneural_biotech_battle_round_key(game)
        if source:
            sr["intraneural_biotech_used_source"] = str(source or "").strip()
        if stratagem_name:
            sr["intraneural_biotech_used_stratagem"] = str(stratagem_name or "").strip()
        root.special_rules = sr

    def can_use_intraneural_biotech_stratagem_discount(self, game=None, *, stratagem_name: str = "") -> bool:
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
        rule = root.get_intraneural_biotech_stratagem_rule()
        if not rule:
            return False
        if root.intraneural_biotech_used_this_battle_round(game):
            return False
        name_u = str(stratagem_name or "").strip().upper()
        allowed = {str(v or "").strip().upper() for v in list(rule.get("stratagems", ()) or ()) if str(v or "").strip()}
        if name_u and allowed and name_u not in allowed:
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

    def loping_speed_used_this_battle(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        return bool(sr.get("loping_speed_used_battle", False))

    def mark_loping_speed_used(self, game=None) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        rule = root.get_loping_speed_rule() or {}
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["loping_speed_used_turn_key"] = self._loping_speed_turn_key(game)
        if bool(rule.get("once_per_battle", False)):
            sr["loping_speed_used_battle"] = True
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
        if bool(rule.get("once_per_battle", False)):
            if root.loping_speed_used_this_battle():
                return False
        elif root.loping_speed_used_this_turn(game):
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
        Also supports closest-target variants that only re-roll specific values
        (e.g. "re-roll a Hit roll of 1").
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
                m_value = re.search(r"re-?roll\s+a\s+hit\s+roll\s+of\s+(?P<val>\d+)", low)
                m_full = re.search(r"re-?roll\s+the\s+hit\s+roll(?:\s+instead)?", low)
                full_if_uncontrolled_objective = bool(
                    re.search(
                        r"if\s+the\s+target\s+of\s+that\s+attack\s+is\s+within\s+range\s+of\s+an?\s+objective\s+marker\s+"
                        r"(?:you\s+do\s+not\s+control|your\s+opponent\s+controls)",
                        low,
                    )
                )
                if not m_full and not m_value:
                    continue
                source = str(name or "Closest enemy unit").strip() or "Closest enemy unit"
                rule = {"source": source}
                if m_value:
                    try:
                        roll_value = int(m_value.group("val") or 0)
                    except Exception:
                        roll_value = 0
                    if roll_value <= 0:
                        continue
                    rule["reroll_values"] = (int(roll_value),)
                if m_full and not full_if_uncontrolled_objective:
                    rule["reroll_full"] = True
                else:
                    rule["reroll_full"] = False
                if full_if_uncontrolled_objective:
                    rule["reroll_full_if_target_uncontrolled_objective"] = True
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_closest_eligible_hit_bonus_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time this model makes a ranged attack that targets the closest eligible target, add 1 to the Hit roll."
        """
        if model is None:
            return None
        cache_key = f"closest_eligible_hit_bonus_rule:{get_entity_id(model)}"
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
                if not re.search(r"closest\s+(?:eligible\s+)?(?:enemy\s+)?(?:target|unit)", low):
                    continue
                m = re.search(r"add\s+(\d+)\s+to\s+the\s+hit\s+roll", low)
                if not m:
                    continue
                try:
                    bonus = int(m.group(1) or 0)
                except Exception:
                    bonus = 0
                if bonus <= 0:
                    continue
                source = str(name or "Closest eligible target").strip() or "Closest eligible target"
                rule = {
                    "hit_bonus": int(bonus),
                    "source": source,
                }
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_closest_eligible_ap_bonus_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time this model makes a ranged attack that targets the closest eligible target,
         improve the Armour Penetration characteristic of that attack by 1."
        """
        if model is None:
            return None
        cache_key = f"closest_eligible_ap_bonus_rule:{get_entity_id(model)}"
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
                if not re.search(r"closest\s+(?:eligible\s+)?(?:enemy\s+)?(?:target|unit)", low):
                    continue
                if "armour penetration" not in low and "armor penetration" not in low:
                    continue
                if "characteristic" not in low:
                    continue
                m = re.search(
                    r"improve\s+the\s+(?:armour|armor)\s+penetration\s+characteristic\s+of\s+that\s+attack\s+by\s+(\d+)",
                    low,
                )
                if not m:
                    m = re.search(
                        r"add\s+(\d+)\s+to\s+the\s+(?:armour|armor)\s+penetration\s+characteristic\s+of\s+that\s+attack",
                        low,
                    )
                if not m:
                    continue
                try:
                    ap_bonus = int(m.group(1) or 0)
                except Exception:
                    ap_bonus = 0
                if ap_bonus <= 0:
                    continue
                source = str(name or "Closest eligible target").strip() or "Closest eligible target"
                rule = {
                    "attack_type": "ranged",
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

    def get_stationary_ranged_sustained_hits_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        - "In your Movement phase, if this model Remains Stationary, until the end of the turn,
           ranged weapons equipped by this model have the [SUSTAINED HITS 1] ability."
        - "While this unit is being affected by an Order, provided it Remained Stationary this turn,
           all Heavy weapons equipped by models in this unit have the [SUSTAINED HITS 1] ability."
        """
        if model is None:
            return None
        cache_key = f"stationary_ranged_sustained_hits_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        def _parse_sustained_hits_rule(
            low_text: str,
            *,
            source: str,
            requires_remained_stationary: bool,
            requires_owner_turn: bool,
        ) -> Optional[dict]:
            m = re.search(r"sustained\s+hits\s+(?P<val>\d+|d3|d6)", low_text)
            if not m:
                return None
            raw_val = str(m.group("val") or "").strip().upper()
            parsed_rule = {
                "attack_type": "ranged",
                "requires_remained_stationary": bool(requires_remained_stationary),
                "requires_owner_turn": bool(requires_owner_turn),
                "source": source,
            }
            if raw_val in ("D3", "D6"):
                parsed_rule["sustained_hits_dice"] = raw_val
                return parsed_rule
            try:
                sustained_val = int(raw_val or 0)
            except Exception:
                sustained_val = 0
            if sustained_val <= 0:
                return None
            parsed_rule["sustained_hits_value"] = int(sustained_val)
            return parsed_rule

        rule = None
        try:
            for name, desc in self._iter_model_specific_ability_entries(model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower().replace("\u2019", "'")
                if not re.search(r"\b(?:in|during)\s+your\s+movement\s+phase\b", low):
                    continue
                if not re.search(r"\bif\s+this\s+model\s+remain(?:s|ed)?\s+stationary\b", low):
                    continue
                if "ranged weapons equipped by this model" not in low:
                    continue
                if "sustained hits" not in low:
                    continue
                if not re.search(r"\buntil\s+(?:the\s+)?end\s+of\s+(?:your\s+|the\s+)?turn\b", low):
                    continue
                source = str(name or "Remains Stationary").strip() or "Remains Stationary"
                parsed_rule = _parse_sustained_hits_rule(
                    low,
                    source=source,
                    requires_remained_stationary=True,
                    requires_owner_turn=True,
                )
                if not isinstance(parsed_rule, dict):
                    continue
                rule = parsed_rule
                break
        except Exception:
            rule = None

        if rule is None:
            try:
                for name, desc in self._iter_ability_entries_for_rules(model=None):
                    text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                    if not text:
                        continue
                    low = text.lower().replace("\u2019", "'")
                    if not re.search(r"\bwhile\s+this\s+unit\s+is\s+being\s+affected\s+by\s+an?\s+order\b", low):
                        continue
                    if not re.search(r"\bprovided\s+it\s+remain(?:s|ed)?\s+stationary\s+this\s+turn\b", low):
                        continue
                    if "heavy weapons equipped by models in this unit" not in low:
                        continue
                    if "sustained hits" not in low:
                        continue
                    source = str(name or "Ordered heavy weapons").strip() or "Ordered heavy weapons"
                    parsed_rule = _parse_sustained_hits_rule(
                        low,
                        source=source,
                        requires_remained_stationary=True,
                        requires_owner_turn=True,
                    )
                    if not isinstance(parsed_rule, dict):
                        continue
                    parsed_rule["requires_active_order"] = True
                    parsed_rule["requires_heavy_weapon"] = True
                    rule = parsed_rule
                    break
            except Exception:
                rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_stationary_ranged_weapon_keyword_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        - "In your Movement phase, if this model Remains Stationary, until the end of the turn,
           its doomsday cannon has the [DEVASTATING WOUNDS] ability."
        """
        if model is None:
            return None
        cache_key = f"stationary_ranged_weapon_keyword_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            for name, desc in self._iter_model_specific_ability_entries(model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower().replace("\u2019", "'")
                if not re.search(r"\b(?:in|during)\s+your\s+movement\s+phase\b", low):
                    continue
                if not re.search(r"\bif\s+this\s+model\s+remain(?:s|ed)?\s+stationary\b", low):
                    continue
                if not re.search(r"\buntil\s+(?:the\s+)?end\s+of\s+(?:your\s+|the\s+)?turn\b", low):
                    continue
                m = re.search(
                    r"\bits\s+(?P<weapon>[a-z0-9][a-z0-9 '\-]*)\s+has\s+the\s+\[?(?P<keyword>[a-z0-9 +\-]+)\]?\s+ability\b",
                    low,
                )
                if not m:
                    continue
                weapon_name = str(m.group("weapon") or "").strip()
                keyword = str(m.group("keyword") or "").strip().upper()
                keyword = re.sub(r"\s+", " ", keyword)
                if not weapon_name or not keyword:
                    continue
                source = str(name or "Remains Stationary").strip() or "Remains Stationary"
                rule = {
                    "attack_type": "ranged",
                    "requires_remained_stationary": True,
                    "requires_owner_turn": True,
                    "weapon_names": [weapon_name],
                    "keyword": keyword,
                    "source": source,
                }
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
        Also supports melee variants such as:
        "Each time this model makes a melee attack that targets a MONSTER or VEHICLE unit, you can re-roll ..."
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
                attack_type = "any"
                if "ranged attack" in low:
                    attack_type = "ranged"
                elif "melee attack" in low:
                    attack_type = "melee"
                else:
                    continue
                if "monster" not in low or "vehicle" not in low:
                    continue
                if "closest" in low:
                    continue
                if attack_type == "ranged":
                    model_attack_phrase = bool(
                        ("each time a model in this unit makes a ranged attack" in low)
                        or ("each time this model makes a ranged attack" in low)
                        or ("each time a ranged attack made by this model" in low)
                    )
                else:
                    model_attack_phrase = bool(
                        ("each time a model in this unit makes a melee attack" in low)
                        or ("each time this model makes a melee attack" in low)
                        or ("each time a melee attack made by this model" in low)
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
                    "attack_type": str(attack_type or "any"),
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

    def get_melee_target_excluding_keywords_ap_bonus_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return melee AP bonus rule for patterns like:
        "Each time a model in this unit makes a melee attack that targets a unit (excluding MONSTERS and VEHICLES),
         improve the Armour Penetration characteristic of that attack by 1."
        """
        if model is None:
            return None
        cache_key = f"melee_target_excluding_keywords_ap_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            for name, desc in self._iter_ability_entries_for_rules(model=model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower().replace("\u2019", "'")
                low = re.sub(r"'s\b", "s", low)
                low = re.sub(r"[^a-z0-9]+", " ", low)
                low = re.sub(r"\s+", " ", low).strip()
                if "melee attack" not in low:
                    continue
                if "armour penetration" not in low and "armor penetration" not in low:
                    continue
                if "improve" not in low:
                    continue
                if "excluding monsters and vehicles" not in low:
                    continue
                if "targets a unit" not in low and "targets unit" not in low:
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
                source = str(name or "Melee target AP bonus").strip() or "Melee target AP bonus"
                rule = {
                    "attack_type": "melee",
                    "ap_bonus": int(ap_bonus),
                    "target_exclude_keywords_any": ("monster", "vehicle"),
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
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in members:
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("enhancement_adrenal_infusions")):
                found = True
                break
            enh = getattr(member, "enhancement", None)
            if enh is None:
                continue
            enh_id = str(getattr(enh, "id", "") or "").strip()
            enh_name = str(getattr(enh, "name", "") or "").strip().lower()
            if enh_id == "000010699005" or enh_name == "adrenal infusions":
                found = True
                break
        try:
            if not found:
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
                if name_norm in ("shadow field", "shadowfield"):
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

    def _horde_move_phase_key(self, game=None) -> str:
        return self._blood_surge_phase_key(game)

    def _unhinged_vengeance_phase_key(self, game=None) -> str:
        return self._blood_surge_phase_key(game)

    def _guns_blazing_turn_key(self, game=None) -> str:
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
        owner_id = str(getattr(current_player, "id", "") or "")
        owner_name = str(getattr(current_player, "name", "") or "")
        owner = owner_id or owner_name
        return f"{br}:{owner}"

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

    def horde_move_used_this_phase(self, game=None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._horde_move_phase_key(game)
        return str(sr.get("horde_move_used_phase_key", "")) == key

    def mark_horde_move_used(self, game=None) -> None:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["horde_move_used_phase_key"] = self._horde_move_phase_key(game)
        self.special_rules = sr

    def unhinged_vengeance_used_this_phase(self, game=None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._unhinged_vengeance_phase_key(game)
        return str(sr.get("unhinged_vengeance_used_phase_key", "")) == key

    def mark_unhinged_vengeance_used(self, game=None) -> None:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["unhinged_vengeance_used_phase_key"] = self._unhinged_vengeance_phase_key(game)
        self.special_rules = sr

    def geomantic_hunters_uses(self) -> int:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return 0
        try:
            return int(sr.get("geomantic_hunters_uses", 0) or 0)
        except Exception:
            return 0

    def can_use_geomantic_hunters(self) -> bool:
        if not self.has_geomantic_hunters():
            return False
        return int(self.geomantic_hunters_uses() or 0) < 2

    def mark_geomantic_hunters_used(self) -> None:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        try:
            used = int(sr.get("geomantic_hunters_uses", 0) or 0)
        except Exception:
            used = 0
        sr["geomantic_hunters_uses"] = max(0, min(2, int(used) + 1))
        self.special_rules = sr

    def guns_blazing_used_this_turn(self, game=None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._guns_blazing_turn_key(game)
        return str(sr.get("guns_blazing_used_turn_key", "")) == key

    def mark_guns_blazing_used(self, game=None) -> None:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["guns_blazing_used_turn_key"] = self._guns_blazing_turn_key(game)
        self.special_rules = sr

    def can_blood_surge(self, game=None, game_map=None) -> bool:
        if not self.has_blood_surge():
            return False
        # FAQ: if the bodyguard unit was wiped and only an attached leader remains
        # before separation is finalized, the surviving leader cannot use Blood Surge.
        if len(list(getattr(self, "models", []) or [])) == 0 and list(getattr(self, "attached_leaders", []) or []):
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

    def can_unhinged_vengeance(self, game=None, game_map=None) -> bool:
        if not self.has_unhinged_vengeance():
            return False
        if not self.is_alive() or not getattr(self, "deployed", False):
            return False
        if self.is_battle_shocked():
            return False
        if self.unhinged_vengeance_used_this_phase(game):
            return False
        model = self.get_unhinged_vengeance_model()
        if model is None:
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
        if self.has_righteous_zeal() and self.horde_move_used_this_phase(game):
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
        if self.has_righteous_zeal():
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

    def can_use_guns_blazing(self, game=None, game_map=None, *, enemy_unit=None) -> bool:
        if not self.has_guns_blazing():
            return False
        if not self.is_alive() or not getattr(self, "deployed", False):
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
        if self.guns_blazing_used_this_turn(game):
            return False

        owner_army = self.get_parent_army()
        owner_player = getattr(owner_army, "player", None) if owner_army is not None else None
        current_player = None
        if game is not None:
            current_player = getattr(game, "get_current_player", lambda: None)()
        if owner_player is not None and current_player is owner_player:
            return False

        if enemy_unit is None:
            return True
        try:
            enemy_root = enemy_unit.get_attached_unit_root()
        except Exception:
            enemy_root = enemy_unit
        if enemy_root is None:
            return False
        try:
            enemy_army = enemy_root.get_parent_army()
        except Exception:
            enemy_army = None
        if enemy_army is None or enemy_army is owner_army:
            return False
        return bool(getattr(enemy_root, "is_alive", lambda: False)())

    def has_reanimation_protocols(self) -> bool:
        """Check if the unit has Reanimation Protocols (Necrons army rule)."""
        if 'reanimation_protocols' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['reanimation_protocols']

        found, _ = self._find_ability_with_patterns(["reanimation protocols", "reanimation protocol"])

        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['reanimation_protocols'] = found
        return found

    _RULE_TEXT_HTML_TAG_RE = re.compile(r"<[^>]+>")
    _RULE_TEXT_WHITESPACE_RE = re.compile(r"\s+")

    @staticmethod
    @lru_cache(maxsize=8192)
    def _normalize_rules_text_cached(text: str) -> str:
        """Normalize Wahapedia-style text for rule pattern matching."""
        raw = str(text or "")
        if not raw:
            return ""
        raw = KeywordsDetachmentsMixin._RULE_TEXT_HTML_TAG_RE.sub(" ", raw)
        raw = raw.replace("\n", " ").replace("\r", " ")
        return KeywordsDetachmentsMixin._RULE_TEXT_WHITESPACE_RE.sub(" ", raw).strip()

    def _normalize_rules_text(self, text: str) -> str:
        return KeywordsDetachmentsMixin._normalize_rules_text_cached(str(text or ""))

    @staticmethod
    @lru_cache(maxsize=8192)
    def _normalize_keyword_phrase(value: str) -> str:
        t = str(value or "").lower()
        if not t:
            return ""
        t = t.replace("\u2019", "'").replace("\u0192?T", "'")
        out_chars: list[str] = []
        prev_space = True
        for ch in t:
            is_ascii_alnum = ("a" <= ch <= "z") or ("0" <= ch <= "9")
            if is_ascii_alnum:
                out_chars.append(ch)
                prev_space = False
                continue
            if not prev_space:
                out_chars.append(" ")
                prev_space = True
        if out_chars and out_chars[-1] == " ":
            out_chars.pop()
        return "".join(out_chars)

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

    @staticmethod
    def _target_has_keyword(target: Optional['Unit'], keyword: str) -> bool:
        if target is None or not keyword:
            return False
        kw = str(keyword).strip().upper()
        if not kw:
            return False
        try:
            has_keyword = getattr(target, "has_keyword", None)
            if callable(has_keyword) and has_keyword(kw):
                return True
        except Exception:
            pass
        try:
            has_any = getattr(target, "has_any_keyword", None)
            if callable(has_any) and has_any(kw):
                return True
        except Exception:
            pass
        return False

    def get_hunter_of_souls_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """Parse Hunter of Souls (target CHARACTER rerolls; heal on CHARACTER unit destroyed)."""
        if model is None:
            return None
        cache_key = f"hunter_of_souls_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule: Optional[dict] = None
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            low = normalized.lower()
            if "targets a character unit" not in low:
                continue
            if "re-roll a hit roll of 1" not in low and "re roll a hit roll of 1" not in low:
                continue
            if "re-roll a wound roll of 1" not in low and "re roll a wound roll of 1" not in low:
                continue
            if "targets a psyker character unit" not in low:
                continue
            if "can re-roll the hit roll" not in low and "can re roll the hit roll" not in low:
                continue
            if "can re-roll the wound roll" not in low and "can re roll the wound roll" not in low:
                continue
            if "destroys a character unit" not in low:
                continue
            if "regains up to d3 lost wounds" not in low:
                continue
            if "regains up to 3 lost wounds" not in low:
                continue
            source = str(name or "Hunter of Souls").strip() or "Hunter of Souls"
            rule = {
                "source": source,
                "reroll_vs_character_values": (1,),
                "reroll_vs_psyker_character_full": True,
                "heal_expr": "D3",
                "heal_if_target_psyker": 3,
                "requires_target_character": True,
            }
            break

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    @staticmethod
    def _target_at_starting_strength(target: Optional['Unit']) -> bool:
        if target is None:
            return False
        try:
            return not bool(target.is_below_starting_strength())
        except Exception:
            return False

    def get_eradicate_the_foe_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """Parse Eradicate the Foe hit reroll mode against targets at Starting Strength."""
        if model is None:
            return None
        cache_key = f"eradicate_the_foe_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule: Optional[dict] = None
        for name, desc in self._iter_model_specific_ability_entries(model):
            source = str(name or "").strip()
            source_key = source.lower()
            text_src = desc or name or ""
            if not text_src:
                continue
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            low = normalized.lower().replace("reroll", "re roll")
            low = re.sub(r"[^a-z0-9]+", " ", low)
            low = re.sub(r"\s+", " ", low).strip()
            if source_key != "eradicate the foe" and "at its starting strength" not in low:
                continue
            if "at its starting strength" not in low:
                continue
            if "re roll a hit roll of 1" in low:
                rule = {
                    "source": source or "Eradicate the Foe",
                    "mode": "ones",
                }
                break
            if "re roll the hit roll" in low:
                rule = {
                    "source": source or "Eradicate the Foe",
                    "mode": "full",
                }
                break

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_silent_executioner_source(self, model: Optional['Model'] = None) -> str:
        """Return the active Silent Executioner source name for this model, if present."""
        if model is None:
            return ""
        cache_key = f"silent_executioner_source:{get_entity_id(model)}"
        cache = getattr(self, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return str(cache.get(cache_key) or "")

        source = ""
        for name, desc in self._iter_model_specific_ability_entries(model):
            source_name = str(name or "").strip()
            source_key = source_name.lower()
            text_src = desc or name or ""
            if not text_src:
                continue
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            low = normalized.lower().replace("reroll", "re roll")
            low = re.sub(r"[^a-z0-9]+", " ", low)
            low = re.sub(r"\s+", " ", low).strip()
            if source_key != "silent executioner" and "targets a unit that is below its starting strength" not in low:
                continue
            if "re roll the hit roll" not in low:
                continue
            if "below half strength" not in low or "re roll the wound roll" not in low:
                continue
            source = source_name or "Silent Executioner"
            break

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = source
        return str(source or "")

    def get_model_soul_trap_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """Parse Soul Trap rule for baseline and post-first-melee-kill bonuses."""
        if model is None:
            return None
        cache_key = f"soul_trap_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule: Optional[dict] = None
        for name, desc in self._iter_model_specific_ability_entries(model):
            source = str(name or "").strip()
            source_key = source.lower()
            text_src = desc or name or ""
            if not text_src:
                continue
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            low = normalized.lower()
            low = re.sub(r"[^a-z0-9]+", " ", low)
            low = re.sub(r"\s+", " ", low).strip()
            if source_key != "soul trap" and "add 1 to the attacks and strength characteristics" not in low:
                continue
            if "melee weapons" not in low:
                continue
            if "first time" not in low:
                continue
            if "after all the bearer s attacks have been resolved" not in low and "after all the bearer attacks have been resolved" not in low:
                continue
            rule = {
                "source": source or "Soul Trap",
                "base_bonus": 1,
                "empowered_bonus": 1,
            }
            break

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def model_has_soul_trap_ability(self, model: Optional['Model'] = None) -> bool:
        return bool(self.get_model_soul_trap_rule(model))

    def model_has_soul_trap_empowerment(self, model: Optional['Model'] = None) -> bool:
        if model is None:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        empowered_ids = list(sr.get("soul_trap_empowered_model_ids", []) or [])
        return str(get_entity_id(model) or "") in empowered_ids

    def mark_model_soul_trap_pending(self, model: Optional['Model'] = None) -> None:
        if model is None:
            return
        if not self.model_has_soul_trap_ability(model):
            return
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        model_id = str(get_entity_id(model) or "")
        if not model_id:
            return
        empowered_ids = list(sr.get("soul_trap_empowered_model_ids", []) or [])
        if model_id in empowered_ids:
            return
        pending_ids = list(sr.get("soul_trap_pending_model_ids", []) or [])
        if model_id not in pending_ids:
            pending_ids.append(model_id)
            pending_ids.sort()
        sr["soul_trap_pending_model_ids"] = pending_ids
        root.special_rules = sr

    def promote_pending_soul_trap_models(self) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        pending_ids = list(sr.get("soul_trap_pending_model_ids", []) or [])
        if not pending_ids:
            return
        empowered_ids = list(sr.get("soul_trap_empowered_model_ids", []) or [])
        changed = False
        for model_id in pending_ids:
            mid = str(model_id or "")
            if not mid or mid in empowered_ids:
                continue
            empowered_ids.append(mid)
            changed = True
        empowered_ids.sort()
        sr["soul_trap_empowered_model_ids"] = empowered_ids
        sr["soul_trap_pending_model_ids"] = []
        if changed:
            root.special_rules = sr

    def get_model_soul_trap_melee_bonuses(self, model: Optional['Model'] = None) -> tuple[int, int, str]:
        """
        Return (attacks_bonus, strength_bonus, source) for Soul Trap.

        Baseline bonus is +1A/+1S. After first melee kill resolves, bonus becomes +2A/+2S.
        """
        rule = self.get_model_soul_trap_rule(model)
        if not rule:
            return 0, 0, ""
        try:
            base_bonus = int(rule.get("base_bonus", 1) or 1)
        except Exception:
            base_bonus = 1
        try:
            empowered_bonus = int(rule.get("empowered_bonus", 1) or 1)
        except Exception:
            empowered_bonus = 1
        total = int(base_bonus)
        if self.model_has_soul_trap_empowerment(model):
            total += int(empowered_bonus)
        source = str(rule.get("source", "") or "Soul Trap").strip() or "Soul Trap"
        return int(total), int(total), source

    def get_model_hit_reroll_modifiers(self, model: Optional['Model'] = None, *, attack_type: str = "any", target=None) -> dict:
        mods = self._get_model_reroll_modifiers(model, attack_type=attack_type, target=target, roll="hit")
        reroll_values = set(mods.get("reroll_values", ()) or ())
        reroll_reasons = list(mods.get("reroll_reasons", ()) or ())
        reroll_full_reasons = list(mods.get("reroll_full_reasons", ()) or ())
        reroll_full = bool(mods.get("reroll_full"))
        extra_reasons = self._start_of_battle_keyword_reroll_ones_reasons(model, target, roll="hit")
        if extra_reasons:
            reroll_values.add(1)
            reroll_reasons.extend(extra_reasons)
        if model is not None:
            army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
            mgr = getattr(army, "drukhari_detachments", None) if army is not None else None
            reroll_fn = getattr(mgr, "callous_competition_hit_reroll_ones", None) if mgr is not None else None
            if callable(reroll_fn):
                applies, source = reroll_fn(model, unit=self)
                if bool(applies):
                    reroll_values.add(1)
                    source_name = str(source or "Callous Competition").strip() or "Callous Competition"
                    reroll_reasons.append(f"{source_name}: re-roll Hit rolls of 1")
        hunter = self.get_hunter_of_souls_rule(model)
        if hunter and target is not None and bool(hunter.get("requires_target_character", True)):
            if self._target_has_keyword(target, "CHARACTER"):
                source = str(hunter.get("source", "") or "Hunter of Souls").strip() or "Hunter of Souls"
                if bool(hunter.get("reroll_vs_psyker_character_full")) and self._target_has_keyword(target, "PSYKER"):
                    reroll_full = True
                    reroll_full_reasons.append(f"{source}: re-roll Hit rolls vs PSYKER CHARACTER targets")
                else:
                    for val in tuple(hunter.get("reroll_vs_character_values", ()) or ()):
                        try:
                            reroll_values.add(int(val))
                        except Exception:
                            continue
                    reroll_reasons.append(f"{source}: re-roll Hit rolls of 1 vs CHARACTER targets")
        eradicate = self.get_eradicate_the_foe_rule(model)
        if eradicate and target is not None and self._target_at_starting_strength(target):
            source = str(eradicate.get("source", "") or "Eradicate the Foe").strip() or "Eradicate the Foe"
            mode = str(eradicate.get("mode", "") or "").strip().lower()
            if mode == "full":
                reroll_full = True
                reroll_full_reasons.append(f"{source}: re-roll Hit roll vs targets at Starting Strength")
            elif mode == "ones":
                reroll_values.add(1)
                reroll_reasons.append(f"{source}: re-roll Hit rolls of 1 vs targets at Starting Strength")
        silent_source = self.get_silent_executioner_source(model)
        if silent_source and target is not None:
            try:
                below_starting = bool(target.is_below_starting_strength())
            except Exception:
                below_starting = False
            if below_starting:
                reroll_full = True
                reroll_full_reasons.append(
                    f"{silent_source}: re-roll Hit roll vs targets below Starting Strength"
                )
        if model is not None:
            attack_scope = str(attack_type or "").strip().lower()
            if attack_scope not in {"melee", "ranged"}:
                attack_scope = "any"
            army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            apply_fn = getattr(
                sm_mgr,
                "companions_of_vehemence_merciless_denunciation_hit_reroll",
                None,
            ) if sm_mgr is not None else None
            if callable(apply_fn):
                applies, source = apply_fn(
                    self,
                    model=model,
                    attack_type=attack_scope,
                )
                if bool(applies):
                    reroll_full = True
                    source_name = str(source or "Merciless Denunciation").strip() or "Merciless Denunciation"
                    reroll_full_reasons.append(f"{source_name}: re-roll Hit roll")
        seen = set()
        deduped_reasons: list[str] = []
        for reason in reroll_reasons:
            key = str(reason or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped_reasons.append(str(reason))
        seen = set()
        deduped_full_reasons: list[str] = []
        for reason in reroll_full_reasons:
            key = str(reason or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped_full_reasons.append(str(reason))
        return {
            "reroll_hit_values": tuple(sorted(reroll_values)),
            "reroll_hit_full": bool(reroll_full),
            "reroll_hit_reasons": tuple(deduped_reasons),
            "reroll_hit_full_reasons": tuple(deduped_full_reasons),
        }

    def get_model_wound_reroll_modifiers(self, model: Optional['Model'] = None, *, attack_type: str = "any", target=None) -> dict:
        mods = self._get_model_reroll_modifiers(model, attack_type=attack_type, target=target, roll="wound")
        reroll_values = set(mods.get("reroll_values", ()) or ())
        reroll_reasons = list(mods.get("reroll_reasons", ()) or ())
        reroll_full_reasons = list(mods.get("reroll_full_reasons", ()) or ())
        reroll_full = bool(mods.get("reroll_full"))
        extra_reasons = self._start_of_battle_keyword_reroll_ones_reasons(model, target, roll="wound")
        if extra_reasons:
            reroll_values.add(1)
            reroll_reasons.extend(extra_reasons)
        if model is not None:
            army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
            mgr = getattr(army, "drukhari_detachments", None) if army is not None else None
            reroll_fn = getattr(mgr, "callous_competition_wound_reroll_ones", None) if mgr is not None else None
            if callable(reroll_fn):
                applies, source = reroll_fn(model, unit=self)
                if bool(applies):
                    reroll_values.add(1)
                    source_name = str(source or "Callous Competition").strip() or "Callous Competition"
                    reroll_reasons.append(f"{source_name}: re-roll Wound rolls of 1")
        if model is not None and target is not None:
            army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
            mgr = getattr(army, "adeptus_mechanicus_detachments", None) if army is not None else None
            if mgr is not None and bool(getattr(mgr, "is_explorator_maniple", lambda: False)()):
                apply_reroll = getattr(mgr, "acquisition_at_any_cost_wound_reroll_ones", None)
                if callable(apply_reroll):
                    applies, source = apply_reroll(model, target_unit=target)
                    if bool(applies):
                        reroll_values.add(1)
                        reason = str(source or "Acquisition At Any Cost").strip() or "Acquisition At Any Cost"
                        reroll_reasons.append(f"{reason}: re-roll Wound rolls of 1")
        hunter = self.get_hunter_of_souls_rule(model)
        if hunter and target is not None and bool(hunter.get("requires_target_character", True)):
            if self._target_has_keyword(target, "CHARACTER"):
                source = str(hunter.get("source", "") or "Hunter of Souls").strip() or "Hunter of Souls"
                if bool(hunter.get("reroll_vs_psyker_character_full")) and self._target_has_keyword(target, "PSYKER"):
                    reroll_full = True
                    reroll_full_reasons.append(f"{source}: re-roll Wound rolls vs PSYKER CHARACTER targets")
                else:
                    for val in tuple(hunter.get("reroll_vs_character_values", ()) or ()):
                        try:
                            reroll_values.add(int(val))
                        except Exception:
                            continue
                    reroll_reasons.append(f"{source}: re-roll Wound rolls of 1 vs CHARACTER targets")
        silent_source = self.get_silent_executioner_source(model)
        if silent_source and target is not None:
            try:
                below_half = bool(target.is_below_half_strength())
            except Exception:
                below_half = False
            if below_half:
                reroll_full = True
                reroll_full_reasons.append(
                    f"{silent_source}: re-roll Wound roll vs targets below Half-strength"
                )
        try:
            prime_target_active = getattr(self, "_imperial_agents_prime_target_active", None)
            applies, source = prime_target_active() if callable(prime_target_active) else (False, "")
            if applies and model is not None and target is not None:
                target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
                target_army = target_root.get_parent_army() if target_root is not None and hasattr(target_root, "get_parent_army") else None
                target_warlord = getattr(target_army, "warlord", None) if target_army is not None else None
                is_enemy_warlord = bool(
                    target_root is not None
                    and (bool(getattr(target_root, "is_warlord", False)) or target_root is target_warlord)
                )
                model_has_officio = bool(
                    (hasattr(model, "has_any_keyword") and model.has_any_keyword("OFFICIO ASSASSINORUM"))
                    or (hasattr(model, "has_keyword") and model.has_keyword("OFFICIO ASSASSINORUM"))
                    or self.has_any_keyword("OFFICIO ASSASSINORUM")
                )
                if model_has_officio and is_enemy_warlord:
                    reroll_full = True
                    reroll_full_reasons.append(f"{source}: re-roll Wound roll vs enemy WARLORD target")
        except Exception:
            pass
        try:
            atype = str(attack_type or "").strip().lower()
            if atype not in ("melee", "ranged"):
                atype = "any"
            if model is not None and atype in ("any", "melee"):
                root = self.get_attached_unit_root()
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("enhancement_morbid_might"):
                    bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
                    model_id = str(get_entity_id(model) or "")
                    if bearer_id and model_id and bearer_id == model_id:
                        reroll_full = True
                        source = str(sr.get("enhancement_morbid_might_source", "") or "Morbid Might").strip() or "Morbid Might"
                        reroll_full_reasons.append(f"{source}: re-roll Wound roll")
        except Exception:
            pass
        seen = set()
        deduped_reasons: list[str] = []
        for reason in reroll_reasons:
            key = str(reason or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped_reasons.append(str(reason))
        seen = set()
        deduped_full_reasons: list[str] = []
        for reason in reroll_full_reasons:
            key = str(reason or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped_full_reasons.append(str(reason))
        return {
            "reroll_wound_values": tuple(sorted(reroll_values)),
            "reroll_wound_full": bool(reroll_full),
            "reroll_wound_reasons": tuple(deduped_reasons),
            "reroll_wound_full_reasons": tuple(deduped_full_reasons),
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
                if rule.subject not in ("this_model", "model_in_this_unit"):
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
