"""Auto-extracted Unit mixin methods from unit.py."""

from ._common import *


class RulesParsingMixin:
    def _parse_warlord_enhancement_restrictions(self) -> None:
        """Parse datasheet abilities that forbid Warlord selection or Enhancements."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}

        found_warlord = False
        found_enhancements = False

        def _scan(text: str) -> None:
            nonlocal found_warlord, found_enhancements
            if not text or (found_warlord and found_enhancements):
                return
            normalized = self._normalize_rules_text(text)
            if not normalized:
                return
            if not found_warlord and self._CANNOT_BE_WARLORD_RE.search(normalized):
                found_warlord = True
            if not found_enhancements and self._CANNOT_BE_GIVEN_ENHANCEMENTS_RE.search(normalized):
                found_enhancements = True

        # Unit-level abilities
        for ab in list(getattr(self, "possible_abilities", []) or []):
            try:
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
            except Exception:
                desc = ""
            _scan(desc)
            if found_warlord and found_enhancements:
                break

        # Model-level abilities
        if not (found_warlord and found_enhancements):
            for model in list(getattr(self, "models", []) or []):
                try:
                    abilities = getattr(model, "abilities", {}) or {}
                except Exception:
                    abilities = {}
                for ab in abilities.values():
                    try:
                        desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
                    except Exception:
                        desc = ""
                    _scan(desc)
                    if found_warlord and found_enhancements:
                        break
                if found_warlord and found_enhancements:
                    break

        if found_warlord:
            self.special_rules["cannot_be_warlord"] = True
        if found_enhancements:
            self.special_rules["cannot_be_given_enhancements"] = True

    def _parse_spawn_only_restrictions(self) -> None:
        """Flag units that cannot be mustered and only spawn via other rules."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}

        try:
            cost_entries = getattr(self._datasheet, "datasheets_models_cost", None) or []
        except Exception:
            cost_entries = []
        if cost_entries:
            return

        for ab in list(getattr(self, "possible_abilities", []) or []):
            try:
                name = ab if isinstance(ab, str) else (getattr(ab, "name", "") or "")
            except Exception:
                name = ""
            if self._SPAWN_ONLY_ABILITY_RE.search(str(name).strip()):
                self.special_rules["spawn_only"] = True
                self.special_rules["spawn_only_reason"] = "USING SIR HEKHTUR + no points data"
                self.special_rules["stratagem_target_core_only"] = True
                self.special_rules["stratagem_target_core_only_source"] = "USING SIR HEKHTUR"
                return

    def _parse_daemonic_allegiance_wargear_options(self, text: str) -> list[tuple[str, str]]:
        norm = self._normalize_rules_text(text or "")
        if not norm:
            return []
        tokens = re.sub(r"[^a-z0-9]+", " ", norm.lower()).split()
        header = list(self._DAEMONIC_ALLEGIANCE_WARGEAR_HEADER_TOKENS)
        if tokens[:len(header)] != header:
            return []
        idx = len(header)
        if idx >= len(tokens):
            return []
        keywords = set(self._DAEMONIC_ALLEGIANCE_WARGEAR_KEYWORDS)
        effect = list(self._DAEMONIC_ALLEGIANCE_WARGEAR_EFFECT_TOKENS)
        options: list[tuple[str, str]] = []
        seen = set()
        while idx < len(tokens):
            kw = tokens[idx]
            if kw not in keywords:
                return []
            idx += 1
            if tokens[idx:idx + len(effect)] != effect:
                return []
            idx += len(effect)
            start = idx
            while idx < len(tokens) and tokens[idx] not in keywords:
                idx += 1
            if start == idx:
                return []
            wargear_raw = " ".join(tokens[start:idx]).strip()
            if not wargear_raw:
                return []
            kw_upper = kw.upper()
            if kw_upper in seen:
                return []
            seen.add(kw_upper)
            resolved = wargear_raw
            try:
                want = Unit._norm_wargear_name(wargear_raw)
                for wg in list(getattr(self, "possible_wargear", []) or []):
                    try:
                        if Unit._norm_wargear_name(getattr(wg, "name", "")) == want:
                            resolved = str(getattr(wg, "name", "") or wargear_raw)
                            break
                    except Exception:
                        continue
            except Exception:
                resolved = wargear_raw
            options.append((kw_upper, resolved))
        return options

    def _parse_daemonic_allegiance_keyword_only_options(self, text: str) -> list[tuple[str, str]]:
        norm = self._normalize_rules_text(text or "")
        if not norm:
            return []
        low = norm.lower().replace("\u2019", "'")
        if "select this model to include in your army" not in low:
            return []
        if "keyword" not in low or "select one of" not in low:
            return []
        tokens = re.sub(r"[^a-z0-9]+", " ", low).split()
        if not tokens:
            return []
        if not all(tok in tokens for tok in self._DAEMONIC_ALLEGIANCE_KEYWORD_ONLY_TOKENS):
            return []
        keywords = set(self._DAEMONIC_ALLEGIANCE_WARGEAR_KEYWORDS)
        options: list[tuple[str, str]] = []
        seen = set()
        for tok in tokens:
            if tok not in keywords:
                continue
            kw = tok.upper()
            if kw in seen:
                continue
            seen.add(kw)
            options.append((kw, ""))
        return options

    def get_daemonic_allegiance_options(self) -> list[tuple[str, str]]:
        cache = getattr(self, "_ability_cache", None)
        if isinstance(cache, dict) and "daemonic_allegiance_options" in cache:
            return list(cache.get("daemonic_allegiance_options") or [])
        options: list[tuple[str, str]] = []
        for ab in self._iter_active_abilities():
            try:
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
            except Exception:
                desc = ""
            parsed = self._parse_daemonic_allegiance_wargear_options(desc or "")
            if parsed:
                options = parsed
                break
            parsed = self._parse_daemonic_allegiance_keyword_only_options(desc or "")
            if parsed:
                options = parsed
                break
        if not isinstance(cache, dict):
            cache = {}
        cache["daemonic_allegiance_options"] = list(options)
        self._ability_cache = cache
        return list(options)

    def get_daemonic_allegiance_selection(self) -> Optional[str]:
        choice = getattr(self, "daemonic_allegiance", None)
        if choice:
            token = str(choice).strip()
            if token.lower() in ("unset", "none"):
                choice = None
            else:
                choice = token
        if choice:
            return str(choice).strip()
        try:
            sr = getattr(self, "special_rules", None)
        except Exception:
            sr = None
        if isinstance(sr, dict):
            choice = sr.get("daemonic_allegiance")
            if choice:
                token = str(choice).strip()
                if token.lower() in ("unset", "none"):
                    choice = None
                else:
                    choice = token
        return str(choice).strip() if choice else None

    def _apply_daemonic_allegiance_effects(self, keyword: str) -> None:
        kw = str(keyword or "").strip().upper()
        if not kw:
            return
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if str(sr.get("daemonic_allegiance_effects_applied", "") or "").upper() == kw:
            return

        sr.pop("daemonic_allegiance_weapon_bonuses", None)
        sr.pop("daemonic_allegiance_move_bonus", None)
        sr.pop("daemonic_allegiance_toughness_bonus", None)
        sr.pop("daemonic_allegiance_move_bonus_source", None)
        sr.pop("daemonic_allegiance_toughness_bonus_source", None)

        weapon_bonuses: list[dict] = []
        move_bonus = 0
        toughness_bonus = 0
        move_source = ""
        toughness_source = ""

        for ab in self._iter_active_abilities():
            try:
                name = ab if isinstance(ab, str) else (getattr(ab, "name", "") or "")
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or "")
            except Exception:
                name = ""
                desc = ""
            if not name:
                continue
            if "daemon prince of " not in str(name).lower():
                continue
            text = self._normalize_rules_text(desc or name)
            if not text:
                continue
            low = text.lower().replace("\u2019", "'")

            m = self._DAEMONIC_ALLEGIANCE_WEAPON_BONUS_RE.search(low)
            if m and str(m.group("keyword") or "").strip().upper() == kw:
                try:
                    bonus_val = int(m.group("value") or 0)
                except Exception:
                    bonus_val = 0
                weapon = str(m.group("weapon") or "").strip()
                char = str(m.group("char") or "").strip().lower()
                if bonus_val > 0 and weapon and char in ("strength", "attacks"):
                    entry = {
                        "weapon_names": [weapon],
                        "source": str(name or "Daemonic Allegiance").strip() or "Daemonic Allegiance",
                    }
                    if char == "strength":
                        entry["strength_bonus"] = bonus_val
                    else:
                        entry["attacks_bonus"] = bonus_val
                    weapon_bonuses.append(entry)
                continue

            m = self._DAEMONIC_ALLEGIANCE_TOUGHNESS_BONUS_RE.search(low)
            if m and str(m.group("keyword") or "").strip().upper() == kw:
                try:
                    toughness_bonus = int(m.group("value") or 0)
                except Exception:
                    toughness_bonus = 0
                toughness_source = str(name or "Daemonic Allegiance").strip()
                continue

            m = self._DAEMONIC_ALLEGIANCE_MOVE_BONUS_RE.search(low)
            if m and str(m.group("keyword") or "").strip().upper() == kw:
                try:
                    move_bonus = int(m.group("value") or 0)
                except Exception:
                    move_bonus = 0
                move_source = str(name or "Daemonic Allegiance").strip()

        if weapon_bonuses:
            sr["daemonic_allegiance_weapon_bonuses"] = weapon_bonuses
        if move_bonus:
            sr["daemonic_allegiance_move_bonus"] = int(move_bonus)
            if move_source:
                sr["daemonic_allegiance_move_bonus_source"] = move_source
        if toughness_bonus:
            sr["daemonic_allegiance_toughness_bonus"] = int(toughness_bonus)
            if toughness_source:
                sr["daemonic_allegiance_toughness_bonus_source"] = toughness_source

        sr["daemonic_allegiance_effects_applied"] = kw
        self.special_rules = sr

    def apply_daemonic_allegiance_selection(self, selection: Optional[str] = None) -> bool:
        options = list(self.get_daemonic_allegiance_options() or [])
        if not options:
            return False
        if not selection:
            selection = self.get_daemonic_allegiance_selection()
        if not selection:
            sr = getattr(self, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["daemonic_allegiance_pending"] = True
            self.special_rules = sr
            return False
        matched = None
        for kw, wargear_name in options:
            if kw.strip().lower() == str(selection).strip().lower():
                matched = (kw, wargear_name)
                break
        if matched is None:
            raise ValueError(f"Daemonic Allegiance selection '{selection}' is not valid for unit '{self.name}'.")
        kw, wargear_name = matched
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if sr.get("daemonic_allegiance_applied") and sr.get("daemonic_allegiance") == kw:
            self._apply_daemonic_allegiance_effects(kw)
            return True
        self.daemonic_allegiance = kw
        sr["daemonic_allegiance"] = kw
        sr["daemonic_allegiance_wargear"] = wargear_name or ""
        sr.pop("daemonic_allegiance_pending", None)
        if kw not in list(getattr(self, "keywords", []) or []):
            try:
                self.keywords.append(kw)
            except Exception:
                pass
        if wargear_name:
            target_norm = Unit._norm_wargear_name(wargear_name)
            matching = None
            for wg in list(getattr(self, "possible_wargear", []) or []):
                try:
                    if Unit._norm_wargear_name(getattr(wg, "name", "")) == target_norm:
                        matching = wg
                        break
                except Exception:
                    continue
            for model in list(getattr(self, "models", []) or []):
                try:
                    wargear_list = list(getattr(model, "wargear", []) or [])
                except Exception:
                    wargear_list = []
                if any(Unit._norm_wargear_name(getattr(wg, "name", "")) == target_norm for wg in wargear_list if wg):
                    continue
                if matching is not None:
                    wargear_list.append(matching)
                    model.wargear = wargear_list
                else:
                    try:
                        optional = list(getattr(model, "optional_wargear", []) or [])
                        optional.append(str(wargear_name))
                        model.optional_wargear = optional
                    except Exception:
                        pass
            if matching is None:
                sr["daemonic_allegiance_wargear_missing"] = wargear_name
        else:
            sr.pop("daemonic_allegiance_wargear_missing", None)
        sr["daemonic_allegiance_applied"] = True
        self.special_rules = sr
        self._apply_daemonic_allegiance_effects(kw)
        return True

    def _scan_command_phase_sticky_objective(self) -> bool:
        found = False
        allow_transport = False
        for ab in self._iter_active_abilities():
            try:
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
            except Exception:
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            low = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
            if "end of your command phase" not in low:
                continue
            if "objective marker remains under your control" not in low:
                continue
            if ("objective marker you control" not in low) and ("control an objective marker" not in low):
                continue
            if "within range of" not in low or "objective marker" not in low:
                continue
            loc_sticky = "level of control" in low and "greater than yours" in low
            timed_sticky = "start or end of any turn" in low and "until your opponent controls it" in low
            if not (loc_sticky or timed_sticky):
                continue
            found = True
            if "transport it is embarked within" in low:
                allow_transport = True

        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if found and allow_transport:
            sr["sticky_objectives_allow_embarked_transport"] = True
        else:
            sr.pop("sticky_objectives_allow_embarked_transport", None)
        self.special_rules = sr
        return bool(found)

    def _scan_command_phase_bodyguard_return_ability(self):
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            low = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
            if "command phase" not in low:
                continue
            if "bodyguard model" not in low:
                continue
            if "return" not in low or "destroyed" not in low:
                continue
            if "not leading a unit" in low:
                continue
            if (
                "leading a unit" not in low
                and "leading this unit" not in low
                and "bearer is leading a unit" not in low
            ):
                continue
            # Rebind Rubricae-style D6 table:
            # 1 = D3 mortals, 2-5 = return 1, 6 = return up to 2.
            if (
                "roll one d6" in low
                and "on a 1" in low
                and "d3 mortal wounds" in low
                and "on a 2-5" in low
                and "destroyed bodyguard model" in low
                and "on a 6" in low
                and "up to 2 destroyed bodyguard models" in low
            ):
                return {
                    "name": name or "Bodyguard Return",
                    "description": desc or "",
                    "table_roll": "D6",
                    "mortal_wounds_roll_on_1": "D3",
                    "amount_on_2_5": 1,
                    "amount_on_6": 2,
                    "allow_skip": True,
                }
            if "can return" not in low:
                continue
            m = re.search(
                r"return\s+(?:up to\s+)?(one|a|\d+|d3)\s+destroyed\s+bodyguard\s+models?",
                low,
            )
            if not m:
                continue
            token = str(m.group(1) or "").strip()
            amount, amount_roll = self._parse_command_phase_return_amount_token(token)
            if amount <= 0:
                continue
            return {
                "amount": amount,
                "amount_roll": amount_roll,
                "name": name or "Bodyguard Return",
                "description": desc or "",
            }
        return None

    def _parse_command_phase_return_amount_token(self, token: str) -> tuple[int, str]:
        token_text = str(token or "").strip().lower()
        if not token_text:
            return 0, ""
        if token_text in ("one", "a"):
            return 1, ""
        if token_text.isdigit():
            try:
                value = int(token_text)
            except Exception:
                value = 0
            return (max(0, value), "")

        compact = re.sub(r"\s+", "", token_text)
        m = re.fullmatch(r"(?:(?P<count>\d+))?d(?P<faces>\d+)(?:\+(?P<modifier>\d+))?", compact)
        if not m:
            return 0, ""
        try:
            count = int(m.group("count") or 1)
            faces = int(m.group("faces") or 0)
            modifier = int(m.group("modifier") or 0)
        except Exception:
            return 0, ""
        if count <= 0 or faces <= 0 or modifier < 0:
            return 0, ""
        max_amount = int(count * faces + modifier)
        if max_amount <= 0:
            return 0, ""
        roll = f"{count}D{faces}" if count != 1 else f"D{faces}"
        if modifier:
            roll = f"{roll}+{modifier}"
        return max_amount, roll

    def _scan_command_phase_unit_return_ability(self):
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            low = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
            if "command phase" not in low:
                continue
            if "bodyguard model" in low or "bodyguard models" in low:
                continue
            if "return" not in low or "destroyed" not in low:
                continue
            if "select one friendly" in low:
                continue
            plain = re.sub(r"[^a-z0-9+]+", " ", low).strip()
            if ("to the bearer s unit" not in plain and "to this unit" not in plain):
                continue
            amount_token_re = r"(one|a|\d+|(?:\d+)?d\d+(?:\+\d+)?)"
            base_match = re.search(
                r"return(?:\s+up\s+to)?\s+" + amount_token_re + r"\s+destroyed\s+models?",
                plain,
            )
            if not base_match:
                continue
            token = str(base_match.group(1) or "").strip()
            amount, amount_roll = self._parse_command_phase_return_amount_token(token)
            if amount <= 0:
                continue
            objective_amount = 0
            objective_amount_roll = ""
            objective_match = re.search(
                r"if\s+the\s+bearer\s+s\s+unit\s+is\s+within\s+range\s+of\s+"
                r"(?:an|one\s+or\s+more)\s+objective\s+markers?\s+you\s+control\s+"
                r"you\s+can\s+return(?:\s+up\s+to)?\s+"
                + amount_token_re
                + r"\s+destroyed\s+models?\s+to\s+(?:that\s+unit|the\s+bearer\s+s\s+unit|this\s+unit)\s+instead",
                plain,
            )
            if objective_match:
                objective_token = str(objective_match.group(1) or "").strip()
                objective_amount, objective_amount_roll = self._parse_command_phase_return_amount_token(
                    objective_token
                )
            parsed = {
                "amount": int(amount),
                "amount_roll": amount_roll,
                "name": name or "Command phase model return",
                "description": desc or "",
                "exclude_character": (
                    ("excluding character" in low)
                    or bool(re.search(r"cannot be used to return destroyed character models? in attached units?", plain))
                ),
            }
            if objective_amount > 0:
                parsed["controlled_objective_amount"] = int(objective_amount)
                parsed["controlled_objective_amount_roll"] = str(objective_amount_roll or "")
            if "select one of the following" in low and ("you gain 1cp" in low or "you gain 1 cp" in low):
                cp_gain = 1
                m_cp = re.search(r"you gain\s+(\d+)\s*cp", low)
                if m_cp:
                    try:
                        cp_gain = int(m_cp.group(1) or 1)
                    except Exception:
                        cp_gain = 1
                cp_range = 0
                m_range = re.search(r"within\s+(\d+)\s*\"?\s+of\s+this\s+unit,\s*you\s+gain\s+\d+\s*cp", low)
                if m_range:
                    try:
                        cp_range = int(m_range.group(1) or 0)
                    except Exception:
                        cp_range = 0
                keyword_phrase = ""
                m_kw = re.search(
                    r"one\s+or\s+more\s+(.+?)\s+units?\s+from\s+your\s+army\s+are\s+below\s+starting\s+strength",
                    low,
                )
                if m_kw:
                    keyword_phrase = str(m_kw.group(1) or "").strip()
                required_model_name = ""
                m_anchor = re.search(
                    r"while\s+this\s+unit(?:'s|\s+s)?\s+([^,]+?)\s+is\s+on\s+the\s+battlefield",
                    low,
                )
                if m_anchor:
                    required_model_name = str(m_anchor.group(1) or "").strip()
                parsed.update(
                    {
                        "single_choice": True,
                        "cp_gain": int(max(0, cp_gain)),
                        "cp_condition_range": int(max(0, cp_range)),
                        "cp_condition_keyword_phrase": keyword_phrase,
                        "cp_condition_requires_below_starting_strength": True,
                        "required_model_name": required_model_name,
                    }
                )
            return parsed
        return None

    def _scan_charge_phase_bodyguard_loss_ability(self):
        pattern = self._CHARGE_PHASE_BODYGUARD_LOSS_RE
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            text_src = self._strip_eligibility_prefix(desc or "")
            text = self._normalize_rules_text(text_src or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if pattern.fullmatch(norm):
                return {
                    "name": name or "Charge Phase Leadership Test",
                    "description": desc or "",
                }
        return None

    def _scan_end_of_opponent_turn_strategic_reserves_ability(self):
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("enhancement_webway_pathstone")):
            enhancement = getattr(self, "enhancement", None)
            ability_name = str(getattr(enhancement, "name", "") or "Webway Pathstone").strip() or "Webway Pathstone"
            ability_desc = str(getattr(enhancement, "description", "") or "")
            ability_key = str(sr.get("enhancement_webway_pathstone_once_key", "") or "webway_pathstone").strip().lower()
            if not ability_key:
                ability_key = "webway_pathstone"
            return {
                "name": ability_name,
                "description": ability_desc,
                "once_per_battle": True,
                "ability_key": ability_key,
                "min_enemy_distance_horiz": 0,
                "min_battlefield_edge_distance_horiz": 0,
            }

        pattern = self._OPPONENT_TURN_STRATEGIC_RESERVES_RE
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            m = pattern.fullmatch(norm)
            if m:
                min_enemy_distance = 0
                min_edge_distance = 0
                try:
                    min_enemy_distance = int(m.group("min_dist") or 0)
                except Exception:
                    min_enemy_distance = 0
                try:
                    min_edge_distance = int(m.group("edge_dist") or m.group("edge_dist_alt") or 0)
                except Exception:
                    min_edge_distance = 0
                return {
                    "name": name or "Strategic Reserves",
                    "description": desc or "",
                    "once_per_battle": "once per battle" in norm,
                    "ability_key": "opponent_turn_strategic_reserves",
                    "min_enemy_distance_horiz": int(min_enemy_distance or 0),
                    "min_battlefield_edge_distance_horiz": int(min_edge_distance or 0),
                }
        return None

    def _scan_end_of_fight_phase_destroyed_strategic_reserves_ability(self):
        pattern = self._FIGHT_PHASE_END_DESTROYED_STRATEGIC_RESERVES_RE
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if pattern.fullmatch(norm):
                return {
                    "name": name or "Strategic Reserves",
                    "description": desc or "",
                    "ability_key": "fight_phase_destroyed_strategic_reserves",
                }
        return None

    def _scan_opponent_turn_friendly_unit_destroyed_reposition_ability(self):
        pattern = self._OPPONENT_TURN_FRIENDLY_UNIT_DESTROYED_REPOSITION_RE
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            match = pattern.fullmatch(norm)
            if match:
                keyword = str(match.group("keyword") or "").strip()
                return {
                    "name": name or "Inevitable Death",
                    "description": desc or "",
                    "keyword": keyword,
                }
        return None

    def _scan_transport_reactive_disembark_ability(self):
        pattern = self._TRANSPORT_REACTIVE_DISEMBARK_RE
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            m = pattern.fullmatch(norm)
            if not m:
                continue
            try:
                rng = int(m.group(1))
            except Exception:
                rng = 0
            if rng <= 0:
                continue
            return {
                "name": name or "Reactive Disembark",
                "description": desc or "",
                "range": rng,
            }
        return None

    def _parse_command_phase_regain_wound_amount(self, text: str) -> int:
        if not text:
            return 0
        m = self._COMMAND_PHASE_REGAIN_WOUND_RE.search(text)
        if not m:
            return 0
        try:
            return int(m.group(1))
        except Exception:
            return 0

    def get_command_phase_regain_wound_amount(self, model: Optional['Model'] = None) -> int:
        """
        Return the number of wounds a model regains at the start of your Command phase.

        - Unit-level abilities apply to every model in the unit.
        - Model-level abilities only apply to that specific model.
        """
        cache_key = "command_phase_regain_wound_unit_amount"
        if cache_key in getattr(self, "_ability_cache", {}):
            base_amount = int(self._ability_cache[cache_key] or 0)
        else:
            base_amount = 0
            for ab in self._iter_active_possible_abilities():
                try:
                    if isinstance(ab, str):
                        desc = ab
                    else:
                        desc = str(getattr(ab, "description", "") or getattr(ab, "name", "") or "")
                except Exception:
                    desc = ""
                text = self._normalize_rules_text(desc or "")
                if not text:
                    continue
                base_amount += self._parse_command_phase_regain_wound_amount(text)
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache[cache_key] = int(base_amount or 0)

        if model is None:
            return int(base_amount or 0)

        amount = int(base_amount or 0)
        for ab in list(getattr(model, "abilities", {}) or {}).values():
            try:
                if not self._ability_is_active(ab):
                    continue
            except Exception:
                pass
            try:
                if isinstance(ab, str):
                    desc = ab
                else:
                    desc = str(getattr(ab, "description", "") or getattr(ab, "name", "") or "")
            except Exception:
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            amount += self._parse_command_phase_regain_wound_amount(text)
        return int(amount or 0)

    def _refresh_command_phase_flags(self) -> None:
        """Parse command-phase CP gains and sticky objective flags into special_rules."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        try:
            if "command_phase_bonus_cp" in sr:
                del sr["command_phase_bonus_cp"]
            if "command_phase_bonus_cp_roll_specs" in sr:
                del sr["command_phase_bonus_cp_roll_specs"]
            if "sticky_objectives" in sr:
                del sr["sticky_objectives"]
        except Exception:
            pass
        try:
            cache = getattr(self, "_ability_cache", None)
            if isinstance(cache, dict) and "command_phase_sticky_objective" in cache:
                del cache["command_phase_sticky_objective"]
        except Exception:
            pass

        bonus_cp = 0
        cp_roll_specs: list[dict] = []
        seen_roll_specs: set[tuple[str, int, int, int]] = set()
        for ab in self._iter_active_abilities():
            try:
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
                name = ab if isinstance(ab, str) else (getattr(ab, "name", "") or "")
            except Exception:
                desc = ""
                name = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            m = self._COMMAND_PHASE_BONUS_CP_RE.search(text)
            if m:
                try:
                    bonus_cp += int(m.group(1))
                except Exception:
                    continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9+]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if not norm:
                continue
            m_roll = self._COMMAND_PHASE_CP_ROLL_RE.fullmatch(norm)
            if not m_roll:
                continue
            try:
                dice_count = int(m_roll.group("dice") or 0)
            except Exception:
                dice_count = 0
            try:
                threshold = int(m_roll.group("threshold") or 0)
            except Exception:
                threshold = 0
            try:
                cp_gain = int(m_roll.group("cp") or 0)
            except Exception:
                cp_gain = 0
            if dice_count <= 0 or threshold <= 0 or cp_gain <= 0:
                continue
            source = str(name or "Command phase CP roll").strip() or "Command phase CP roll"
            key = (source.lower(), int(dice_count), int(threshold), int(cp_gain))
            if key in seen_roll_specs:
                continue
            seen_roll_specs.add(key)
            cp_roll_specs.append(
                {
                    "source": source,
                    "dice_count": int(dice_count),
                    "threshold": int(threshold),
                    "cp": int(cp_gain),
                }
            )

        if bonus_cp > 0:
            sr["command_phase_bonus_cp"] = int(bonus_cp)
        if cp_roll_specs:
            sr["command_phase_bonus_cp_roll_specs"] = list(cp_roll_specs)

        if self._scan_command_phase_sticky_objective():
            sr["sticky_objectives"] = True

        self.special_rules = sr

    def _refresh_fall_back_desperate_escape_flags(self) -> None:
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        try:
            for key in (
                "enemy_fallback_desperate_escape",
                "enemy_fallback_desperate_escape_exclude_monster_vehicle",
                "enemy_fallback_desperate_escape_bs_penalty",
                "enemy_fallback_desperate_escape_sources",
            ):
                if key in sr:
                    del sr[key]
        except Exception:
            pass

        sources: list[str] = []
        exclude_monster_vehicle = False
        bs_penalty = 0
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                continue
            text = self._normalize_rules_text(desc or "").lower()
            if not text:
                continue
            if "desperate escape" not in text:
                continue
            if ("fall back" not in text) and ("falls back" not in text) and ("fallback" not in text):
                continue
            if "excluding monsters and vehicles" in text or ("excluding monsters" in text and "vehicles" in text):
                exclude_monster_vehicle = True
            if "battle-shocked" in text and ("subtract 1" in text or "subtract one" in text):
                bs_penalty = max(bs_penalty, 1)
            if name:
                sources.append(name)

        if sources:
            sr["enemy_fallback_desperate_escape"] = True
            sr["enemy_fallback_desperate_escape_sources"] = sources
            if exclude_monster_vehicle:
                sr["enemy_fallback_desperate_escape_exclude_monster_vehicle"] = True
            if bs_penalty:
                sr["enemy_fallback_desperate_escape_bs_penalty"] = int(bs_penalty)
        self.special_rules = sr

    def _refresh_targeted_stratagem_cp_discount_flags(self) -> None:
        """Parse unit abilities that reduce Stratagem CP cost when this unit is targeted."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        try:
            if "stratagem_target_cp_discount" in sr:
                del sr["stratagem_target_cp_discount"]
            if "stratagem_target_cp_discount_sources" in sr:
                del sr["stratagem_target_cp_discount_sources"]
            if "stratagem_target_cp_discount_specs" in sr:
                del sr["stratagem_target_cp_discount_specs"]
            if "stratagem_target_cp_discount_aura" in sr:
                del sr["stratagem_target_cp_discount_aura"]
        except Exception:
            pass

        names: list[str] = []
        direct_specs: list[dict] = []
        aura_specs: list[dict] = []
        entries: list[tuple[str, str, str]] = []
        entries.extend((name, desc, "") for name, desc in self._iter_ability_entries_for_rules(model=None))
        for model in list(getattr(self, "models", []) or []):
            try:
                model_id = str(get_entity_id(model) or "")
            except Exception:
                model_id = ""
            entries.extend((name, desc, model_id) for name, desc in self._iter_ability_entries_for_rules(model=model))

        model_level_signatures: set[tuple[str, str]] = set()
        for name, desc, source_model_id in entries:
            if not source_model_id:
                continue
            model_level_signatures.add(
                (
                    str(name or "").strip().lower(),
                    str(desc or "").strip().lower(),
                )
            )

        seen_entries: set[tuple[str, str, str]] = set()
        self_target_discount_re = re.compile(
            r"once\s+per\s+(?P<limit>battle\s+round|turn)\s+when\s+you\s+target\s+this\s+(?:model|unit)\s+with\s+a\s+stratagem\s+"
            r"(?:you\s+may\s+)?reduce\s+the\s+cp\s+cost\s+of\s+that\s+(?:use|usage)\s+of\s+that\s+stratagem\s+by\s+1\s*cp",
            re.IGNORECASE,
        )

        for name, desc, source_model_id in entries:
            if (
                not source_model_id
                and (
                    str(name or "").strip().lower(),
                    str(desc or "").strip().lower(),
                ) in model_level_signatures
            ):
                continue
            entry_key = (
                str(name or "").strip().lower(),
                str(desc or "").strip().lower(),
                str(source_model_id or "").strip(),
            )
            if entry_key in seen_entries:
                continue
            seen_entries.add(entry_key)
            text_src = self._strip_eligibility_prefix(desc or name)
            text = self._normalize_rules_text(text_src or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if not norm:
                continue

            limit = ""
            usage_scope = "army_ability"
            if self._TARGETED_STRATAGEM_CP_DISCOUNT_RE.fullmatch(norm) or self._TARGETED_STRATAGEM_CP_DISCOUNT_SELECT_RE.fullmatch(norm):
                limit = "battle_round"
            else:
                m_self = self_target_discount_re.fullmatch(norm)
                if m_self:
                    raw_limit = str(m_self.group("limit") or "").strip().lower()
                    limit = "turn" if raw_limit == "turn" else "battle_round"
                    usage_scope = "source_model" if source_model_id else "source_unit"
            if limit:
                ability_name = str(name or "Stratagem CP Discount").strip() or "Stratagem CP Discount"
                names.append(ability_name)
                key_token = re.sub(r"[^a-z0-9]+", "_", ability_name.lower()).strip("_") or "generic"
                spec = {
                    "name": ability_name,
                    "description": desc or "",
                    "limit": limit,
                    "usage_scope": usage_scope,
                    "usage_key": f"TARGETED_STRATAGEM_DISCOUNT:{key_token}:{str(limit).upper()}",
                }
                if source_model_id:
                    spec["source_model_id"] = str(source_model_id)
                direct_specs.append(spec)
                continue

            for pat in (
                self._TARGETED_STRATAGEM_CP_DISCOUNT_AURA_RE,
                self._TARGETED_STRATAGEM_CP_DISCOUNT_AURA_ALT_RE,
                self._TARGETED_STRATAGEM_CP_DISCOUNT_AURA_ALT2_RE,
            ):
                m = pat.fullmatch(norm)
                if not m:
                    continue
                try:
                    rng = int(m.group("range"))
                except Exception:
                    rng = 0
                if rng <= 0:
                    continue
                kw = str(m.group("keyword") or "").strip()
                if kw:
                    kw = re.sub(r"\s+", " ", kw).strip().upper()
                ability_name = str(name or "Stratagem CP Discount").strip() or "Stratagem CP Discount"
                key_token = re.sub(r"[^a-z0-9]+", "_", ability_name.lower()).strip("_") or "generic"
                aura_usage = f"TARGETED_STRATAGEM_DISCOUNT_AURA:{key_token}:{int(rng)}:{kw.lower()}".rstrip(":")
                spec = {
                    "range": rng,
                    "keyword": kw,
                    "name": ability_name,
                    "description": desc or "",
                    "limit": "battle_round",
                    "usage_scope": "army_ability",
                    "usage_key": f"{aura_usage}:BATTLE_ROUND",
                }
                if source_model_id:
                    spec["source_model_id"] = str(source_model_id)
                aura_specs.append(spec)
                break

        if direct_specs:
            sr["stratagem_target_cp_discount"] = True
            seen_specs: set[tuple] = set()
            deduped_specs: list[dict] = []
            for spec in direct_specs:
                key = (
                    str(spec.get("name", "") or "").strip().lower(),
                    str(spec.get("limit", "") or "").strip().lower(),
                    str(spec.get("usage_scope", "") or "").strip().lower(),
                    str(spec.get("source_model_id", "") or "").strip(),
                )
                if key in seen_specs:
                    continue
                seen_specs.add(key)
                deduped_specs.append(spec)
            if deduped_specs:
                sr["stratagem_target_cp_discount_specs"] = deduped_specs
            seen = set()
            deduped: list[str] = []
            for n in names:
                key = str(n).strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                deduped.append(str(n))
            if deduped:
                sr["stratagem_target_cp_discount_sources"] = deduped

        if aura_specs:
            seen_specs: set[tuple] = set()
            deduped_specs: list[dict] = []
            for spec in aura_specs:
                key = (
                    int(spec.get("range", 0) or 0),
                    str(spec.get("keyword", "") or "").strip().lower(),
                    str(spec.get("name", "") or "").strip().lower(),
                    str(spec.get("limit", "") or "").strip().lower(),
                    str(spec.get("source_model_id", "") or "").strip(),
                )
                if key in seen_specs:
                    continue
                seen_specs.add(key)
                deduped_specs.append(spec)
            if deduped_specs:
                sr["stratagem_target_cp_discount_aura"] = deduped_specs

        self.special_rules = sr

    def _refresh_targeted_stratagem_cp_refund_flags(self) -> None:
        """Parse abilities that refund CP when this unit is targeted by a Stratagem."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        try:
            if "stratagem_target_cp_refund_specs" in sr:
                del sr["stratagem_target_cp_refund_specs"]
        except Exception:
            pass

        entries: list[tuple[str, str]] = []
        entries.extend(list(self._iter_ability_entries_for_rules(model=None)))
        for model in list(getattr(self, "models", []) or []):
            entries.extend(list(self._iter_ability_entries_for_rules(model=model)))

        bonus_clause_re = re.compile(
            r"adding\s+(?P<bonus>\d+)\s+to\s+the\s+result\s+if\s+there\s+(?:are|is)\s+one\s+or\s+more\s+friendly\s+"
            r"(?P<keyword>[a-z0-9 ]+?)\s+models?\s+within\s+(?P<range>\d+)",
            re.IGNORECASE,
        )

        specs: list[dict] = []
        seen_entries: set[tuple[str, str]] = set()
        for name, desc in entries:
            entry_key = (str(name or "").strip().lower(), str(desc or "").strip().lower())
            if entry_key in seen_entries:
                continue
            seen_entries.add(entry_key)

            text_src = self._strip_eligibility_prefix(desc or name)
            text = self._normalize_rules_text(text_src or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if not norm or "stratagem" not in norm:
                continue

            roll_bonus = 0
            roll_bonus_keyword = ""
            roll_bonus_range = 0
            norm_for_match = norm
            m_bonus = bonus_clause_re.search(norm)
            if m_bonus:
                try:
                    roll_bonus = int(m_bonus.group("bonus") or 0)
                except (TypeError, ValueError):
                    roll_bonus = 0
                try:
                    roll_bonus_range = int(m_bonus.group("range") or 0)
                except (TypeError, ValueError):
                    roll_bonus_range = 0
                roll_bonus_keyword = re.sub(r"\s+", " ", str(m_bonus.group("keyword") or "").strip()).upper()
                norm_for_match = re.sub(r"\s+", " ", f"{norm[:m_bonus.start()]} {norm[m_bonus.end():]}").strip()

            m = self._TARGETED_STRATAGEM_CP_REFUND_RE.fullmatch(norm_for_match)
            if not m:
                m = self._TARGETED_STRATAGEM_CP_REFUND_SELECT_RE.fullmatch(norm_for_match)
            if not m:
                continue
            try:
                roll_min = int(m.group("roll") or 5)
            except Exception:
                roll_min = 5
            try:
                cp_gain = int(m.group("cp") or 1)
            except Exception:
                cp_gain = 1
            if roll_min <= 0 or cp_gain <= 0:
                continue
            spec = {
                "roll_min": int(roll_min),
                "cp_gain": int(cp_gain),
                "name": name or "Stratagem CP Refund",
                "description": desc or "",
            }
            if roll_bonus > 0 and roll_bonus_keyword and roll_bonus_range > 0:
                spec["roll_bonus"] = int(roll_bonus)
                spec["roll_bonus_keyword"] = str(roll_bonus_keyword)
                spec["roll_bonus_range"] = int(roll_bonus_range)
            specs.append(spec)

        if specs:
            seen_specs: set[tuple] = set()
            deduped_specs: list[dict] = []
            for spec in specs:
                key = (
                    int(spec.get("roll_min", 0) or 0),
                    int(spec.get("cp_gain", 0) or 0),
                    str(spec.get("name", "") or "").strip().lower(),
                    int(spec.get("roll_bonus", 0) or 0),
                    str(spec.get("roll_bonus_keyword", "") or "").strip().upper(),
                    int(spec.get("roll_bonus_range", 0) or 0),
                )
                if key in seen_specs:
                    continue
                seen_specs.add(key)
                deduped_specs.append(spec)
            if deduped_specs:
                sr["stratagem_target_cp_refund_specs"] = deduped_specs

        self.special_rules = sr

    def _refresh_targeted_stratagem_cp_increase_flags(self) -> None:
        """Parse unit abilities that increase Stratagem CP cost when the opponent targets a unit."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        try:
            if "stratagem_target_cp_increase_aura" in sr:
                del sr["stratagem_target_cp_increase_aura"]
        except Exception:
            pass

        specs: list[dict] = []
        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text_src = self._strip_eligibility_prefix(desc or name)
            text = self._normalize_rules_text(text_src or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if not norm:
                continue
            if "opponent" not in norm:
                continue
            if "stratagem" not in norm:
                continue
            if "increase" not in norm:
                continue
            if "cp cost" not in norm and not re.search(r"increase\s+(?:the\s+)?cost\s+of", norm):
                continue
            if "target" not in norm and "uses a stratagem" not in norm:
                continue
            m_range = self._TARGETED_STRATAGEM_CP_INCREASE_RANGE_RE.search(norm)
            if not m_range:
                continue
            try:
                rng = int(m_range.group("range"))
            except Exception:
                rng = 0
            if rng <= 0:
                continue
            optional = False
            if "can use this ability" in norm or "can use this enhancement" in norm or "you can use this" in norm:
                optional = True
            limit = None
            if "once per battle round" in norm or "once in each battle round" in norm:
                limit = "battle_round"
            elif "once per turn" in norm or "once in each of your opponent s turns" in norm:
                limit = "turn"
            max_cp = None
            m_max = self._TARGETED_STRATAGEM_CP_INCREASE_MAX_RE.search(norm)
            if m_max:
                try:
                    max_cp = int(m_max.group("max"))
                except Exception:
                    max_cp = None
            cp_increase = 1
            m_increase = re.search(r"by\s+(?P<cp>\d+)\s*cp", norm)
            if m_increase:
                try:
                    cp_increase = max(1, int(m_increase.group("cp") or 1))
                except Exception:
                    cp_increase = 1
            usage_key = str(name or "Stratagem CP Increase").strip().upper()
            spec = {
                "range": rng,
                "keyword": "",
                "name": name or "Stratagem CP Increase",
                "description": desc or "",
                "optional": bool(optional),
                "limit": limit or "",
                "max_cp": max_cp,
                "cp_increase": int(cp_increase),
                "usage_key": f"STRATAGEM_CP_INCREASE:{usage_key}" if usage_key else "STRATAGEM_CP_INCREASE",
            }
            if isinstance(sr, dict) and bool(sr.get("enhancement_archraider")):
                source_model_id = str(sr.get("enhancement_bearer_model_id", "") or "")
                if source_model_id:
                    low_name = str(name or "").strip().lower()
                    if "archraider" in low_name or "lord of deceit" in norm:
                        spec["source_model_id"] = source_model_id
            specs.append(spec)

        if specs:
            seen_specs: set[tuple] = set()
            deduped_specs: list[dict] = []
            for spec in specs:
                key = (
                    int(spec.get("range", 0) or 0),
                    str(spec.get("name", "") or "").strip().lower(),
                    str(spec.get("limit", "") or "").strip().lower(),
                    bool(spec.get("optional", False)),
                    int(spec.get("max_cp", 0) or 0),
                    int(spec.get("cp_increase", 1) or 1),
                    str(spec.get("source_model_id", "") or "").strip().lower(),
                )
                if key in seen_specs:
                    continue
                seen_specs.add(key)
                deduped_specs.append(spec)
            if deduped_specs:
                sr["stratagem_target_cp_increase_aura"] = deduped_specs

        self.special_rules = sr

    @staticmethod
    def _parse_return_on_death_wounds(text: str):
        t = str(text or "").strip().lower()
        if not t:
            return "full"
        if "full wounds" in t:
            return "full"
        if "d3" in t:
            return "d3"
        if "d6" in t:
            return "d6"
        m = re.search(r"\d+", t)
        if m:
            try:
                return int(m.group(0))
            except Exception:
                return "full"
        return "full"

    def _refresh_return_on_death_flags(self) -> None:
        """Parse 'first time destroyed' return-to-battlefield abilities into special_rules."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        try:
            if "return_on_death_specs" in sr:
                del sr["return_on_death_specs"]
        except Exception:
            pass

        specs: list[dict] = []
        entries: list[tuple[str, str]] = []
        entries.extend(list(self._iter_ability_entries_for_rules(model=None)))
        for model in list(getattr(self, "models", []) or []):
            entries.extend(list(self._iter_ability_entries_for_rules(model=model)))

        enhancement = getattr(self, "enhancement", None)
        enhancement_name = str(getattr(enhancement, "name", "") or "").strip().lower()
        enhancement_key = re.sub(r"[^a-z0-9]+", "_", enhancement_name).strip("_") if enhancement_name else ""
        bearer_id = self._get_enhancement_bearer_id()
        enhancement_superior_creation = bool(isinstance(sr, dict) and sr.get("enhancement_superior_creation"))
        enhancement_pledge_of_eternal_servitude = bool(
            isinstance(sr, dict) and sr.get("enhancement_pledge_of_eternal_servitude")
        )

        seen_entries: set[tuple[str, str]] = set()
        for name, desc in entries:
            key = (str(name or "").strip().lower(), str(desc or "").strip().lower())
            if key in seen_entries:
                continue
            seen_entries.add(key)
            text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or ""))
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if not norm:
                continue
            m = self._RETURN_ON_DEATH_RE.fullmatch(norm)
            spec = None
            if m:
                try:
                    roll_min = int(m.group("roll") or 2)
                except Exception:
                    roll_min = 2
                wounds_raw = m.group("wounds") or ""
                wounds = self._parse_return_on_death_wounds(wounds_raw)
                skip_deadly = "without resolving its deadly demise ability" in norm
                key = re.sub(r"[^a-z0-9]+", "_", str(name or "return_on_death").lower()).strip("_")
                if not key:
                    key = "return_on_death"
                spec = {
                    "name": name or "Return on Death",
                    "roll_min": roll_min,
                    "wounds": wounds,
                    "skip_deadly_demise": bool(skip_deadly),
                    "key": key,
                }
            else:
                # Fabius Bile (Chirurgeon): first time this unit's FABIUS BILE model is destroyed,
                # end-of-phase 2+ return with full wounds, and if attached when destroyed, return attached.
                if (
                    "first time" in norm
                    and "fabius bile model is destroyed" in norm
                    and (
                        "at the end of the phase roll one d6" in norm
                        or "roll one d6 at the end of the phase" in norm
                    )
                    and "set that model back up on the battlefield" in norm
                    and "full wounds remaining" in norm
                ):
                    m_roll = re.search(r"on a (?P<roll>\d+)", norm)
                    try:
                        roll_min = int(m_roll.group("roll")) if m_roll else 2
                    except Exception:
                        roll_min = 2
                    key = re.sub(r"[^a-z0-9]+", "_", str(name or "chirurgeon").lower()).strip("_")
                    if not key:
                        key = "chirurgeon"
                    must_reattach = "must be set back up attached to that unit" in norm
                    spec = {
                        "name": name or "Chirurgeon",
                        "roll_min": int(roll_min or 2),
                        "wounds": "full",
                        "skip_deadly_demise": False,
                        "key": key,
                        "model_name": "Fabius Bile",
                        "must_reattach_if_attached": bool(must_reattach),
                    }
            if spec is None:
                continue
            # Enhancement: Superior Creation is bearer-only; gate it to the bearer model.
            if enhancement_superior_creation and bearer_id and enhancement_key and key == enhancement_key:
                spec["bearer_model_id"] = bearer_id
            specs.append(spec)

        if enhancement_pledge_of_eternal_servitude:
            specs.append(
                {
                    "name": "Pledge of Eternal Servitude",
                    "roll_min": 1,
                    "wounds": "d6",
                    "skip_deadly_demise": False,
                    "key": "pledge_of_eternal_servitude",
                    "bearer_model_id": str(bearer_id or ""),
                    "requires_leadership_test": True,
                }
            )

        if specs:
            seen: set[tuple] = set()
            deduped: list[dict] = []
            for spec in specs:
                key = (
                    str(spec.get("key", "") or "").strip().lower(),
                    int(spec.get("roll_min", 0) or 0),
                    str(spec.get("wounds", "") or "").strip().lower(),
                    str(spec.get("model_name", "") or "").strip().lower(),
                    bool(spec.get("must_reattach_if_attached", False)),
                    bool(spec.get("requires_leadership_test", False)),
                    str(spec.get("bearer_model_id", "") or "").strip(),
                )
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(spec)
            if deduped:
                sr["return_on_death_specs"] = deduped

        try:
            if hasattr(self, "_ability_cache"):
                self._ability_cache.pop("return_on_death_specs", None)
        except Exception:
            pass

        self.special_rules = sr

    def _get_return_on_death_specs(self) -> list[dict]:
        cache_key = "return_on_death_specs"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache.get(cache_key) or [])

        sr = getattr(self, "special_rules", None)
        specs = list(sr.get("return_on_death_specs", []) or []) if isinstance(sr, dict) else []

        if isinstance(sr, dict) and sr.get("enhancement_phoenix_gem"):
            specs.append(
                {
                    "name": "Phoenix Gem",
                    "roll_min": 2,
                    "wounds": "full",
                    "skip_deadly_demise": False,
                    "key": "phoenix_gem",
                }
            )

        seen: set[tuple] = set()
        deduped: list[dict] = []
        for spec in specs:
            key = (
                str(spec.get("key", "") or "").strip().lower(),
                int(spec.get("roll_min", 0) or 0),
                str(spec.get("wounds", "") or "").strip().lower(),
                str(spec.get("model_name", "") or "").strip().lower(),
                bool(spec.get("must_reattach_if_attached", False)),
                bool(spec.get("requires_leadership_test", False)),
                str(spec.get("bearer_model_id", "") or "").strip(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(spec)

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(deduped)
        return list(deduped)

    def _refresh_charge_end_mortal_wounds_flags(self) -> None:
        """Parse charge-move mortal wound triggers into special_rules."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        specs = []
        seen = set()

        for u in members:
            if u is None:
                continue
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text = u._normalize_rules_text(desc or "")
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                low = text.lower()
                if "charge move" not in low or "mortal wound" not in low:
                    continue
                kind = None
                m_per_model = self._CHARGE_END_MORTAL_PER_MODEL_RE.search(text)
                if m_per_model:
                    mw_token = str(m_per_model.group("mw") or "").strip().lower()
                    if mw_token == "1":
                        kind = "per_model_4plus_1"
                    else:
                        kind = "per_model_4plus_d3"
                elif self._CHARGE_END_MORTAL_REMAINING_WOUNDS_RE.search(text):
                    kind = "per_remaining_wounds_4plus_1_max6"
                elif self._CHARGE_END_MORTAL_TABLE_RE.search(text):
                    kind = "table_d6_2_3_4_5_6"
                elif self._CHARGE_END_MORTAL_TABLE_2_5_D3_RE.search(text):
                    kind = "table_d6_2_5_6"
                if not kind:
                    continue
                source = str(name or "Charge Mortals").strip() or "Charge Mortals"
                key = (kind, source.lower())
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "kind": kind,
                        "name": source,
                        "description": str(desc or ""),
                    }
                )

        # Ghosts of the Webway enhancement: Cegorach's Coil
        for u in members:
            if u is None:
                continue
            sr_u = getattr(u, "special_rules", None)
            if not isinstance(sr_u, dict):
                continue
            if not bool(sr_u.get("enhancement_cegorachs_coil")):
                continue
            source = str(sr_u.get("enhancement_cegorachs_coil_source", "") or "").strip() or "Cegorach's Coil"
            try:
                threshold = int(sr_u.get("enhancement_cegorachs_coil_roll_threshold", 4) or 4)
            except Exception:
                threshold = 4
            try:
                mortal_per_success = int(sr_u.get("enhancement_cegorachs_coil_mortal_per_success", 1) or 1)
            except Exception:
                mortal_per_success = 1
            try:
                max_mortal_wounds = int(sr_u.get("enhancement_cegorachs_coil_max_mortal_wounds", 6) or 6)
            except Exception:
                max_mortal_wounds = 6
            bearer_id = str(sr_u.get("enhancement_bearer_model_id", "") or "").strip()
            key = (
                "per_model_engagement_flat_cap",
                source.lower(),
                int(max(2, threshold)),
                int(max(1, mortal_per_success)),
                int(max(1, max_mortal_wounds)),
                bearer_id,
            )
            if key in seen:
                continue
            seen.add(key)
            spec = {
                "kind": "per_model_engagement_flat_cap",
                "name": source,
                "threshold": int(max(2, threshold)),
                "mortal_per_success": int(max(1, mortal_per_success)),
                "max_mortal_wounds": int(max(1, max_mortal_wounds)),
            }
            if bearer_id:
                spec["bearer_model_id"] = bearer_id
            specs.append(spec)

        for u in members:
            if u is None:
                continue
            sr_u = getattr(u, "special_rules", None)
            if not isinstance(sr_u, dict):
                sr_u = {}
            if specs:
                sr_u["charge_end_mortal_wounds"] = list(specs)
            else:
                if "charge_end_mortal_wounds" in sr_u:
                    del sr_u["charge_end_mortal_wounds"]
            u.special_rules = sr_u

    def _refresh_fight_within_3_flags(self) -> None:
        """Parse fight-within-3\" eligibility abilities into special_rules."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        specs = []
        seen = set()

        for u in members:
            if u is None:
                continue
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text = u._normalize_rules_text(desc or "")
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                low = text.lower()
                if "selected to fight" not in low:
                    continue
                if "eligible to fight" not in low:
                    continue
                if "within 3" not in low:
                    continue
                if "engagement range" not in low:
                    continue
                if not self._FIGHT_WITHIN_3_RE.search(text):
                    continue
                source = str(name or "Fight Within 3\"").strip() or "Fight Within 3\""
                key = source.lower()
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "name": source,
                        "description": str(desc or ""),
                    }
                )

        for u in members:
            if u is None:
                continue
            sr_u = getattr(u, "special_rules", None)
            if not isinstance(sr_u, dict):
                sr_u = {}
            if specs:
                sr_u["fight_within_3"] = list(specs)
            else:
                if "fight_within_3" in sr_u:
                    del sr_u["fight_within_3"]
            if not specs and "fight_within_3_active" in sr_u:
                del sr_u["fight_within_3_active"]
            if not specs and "fight_within_3_active_source" in sr_u:
                del sr_u["fight_within_3_active_source"]
            u.special_rules = sr_u

    def _refresh_bearer_unit_common_modifiers(self) -> None:
        """Parse common bearer/leading-unit rules that grant simple unit-wide modifiers."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        # Clear prior bearer-unit modifiers from all attached members.
        for u in members:
            try:
                u.remove_characteristic_modifiers_by_source("ability:bearer_unit_leadership")
            except Exception:
                pass
            try:
                u.remove_characteristic_modifiers_by_source("ability:bearer_unit_movement_set")
            except Exception:
                pass
            try:
                u.remove_characteristic_modifiers_by_source("ability:bearer_unit_movement_bonus")
            except Exception:
                pass
            try:
                u.remove_characteristic_modifiers_by_source("enhancement:follow_me_ladz")
            except Exception:
                pass
            try:
                u.remove_characteristic_modifiers_by_source("ability:bearer_unit_objective_control")
            except Exception:
                pass
            try:
                u.remove_characteristic_modifiers_by_source("ability:unit_contains_objective_control")
            except Exception:
                pass
            try:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                existing = sr.get("charge_roll_modifiers")
                if isinstance(existing, list):
                    kept = []
                    for item in existing:
                        if isinstance(item, dict) and item.get("tag") == "ability:bearer_unit_charge_bonus":
                            continue
                        kept.append(item)
                    if kept:
                        sr["charge_roll_modifiers"] = kept
                    elif "charge_roll_modifiers" in sr:
                        del sr["charge_roll_modifiers"]
                existing = sr.get("advance_roll_modifiers")
                if isinstance(existing, list):
                    kept = []
                    for item in existing:
                        if isinstance(item, dict) and item.get("tag") == "ability:bearer_unit_advance_bonus":
                            continue
                        kept.append(item)
                    if kept:
                        sr["advance_roll_modifiers"] = kept
                    elif "advance_roll_modifiers" in sr:
                        del sr["advance_roll_modifiers"]
                for key in (
                    "bearer_unit_fnp",
                    "bearer_unit_keyword_fnp_entries",
                    "attached_character_fnp_entries",
                    "unit_contains_character_fnp_entries",
                    "same_unit_keyword_fnp_entries",
                    "bearer_unit_invulnerable_save",
                    "bearer_unit_leadership_bonus_controlled_objective",
                    "bearer_unit_agile_maneuver_reroll",
                    "bearer_unit_sustained_hits_value",
                    "bearer_unit_sustained_hits_value_melee",
                    "bearer_unit_sustained_hits_value_ranged",
                    "bearer_unit_ignores_cover",
                    "bearer_unit_benefit_of_cover",
                    "bearer_unit_target_hit_penalties",
                    "bearer_unit_assault_ranged",
                    "bearer_unit_pile_in_distance_override",
                    "bearer_unit_consolidate_distance_override",
                    "bearer_unit_consolidate_requires_engagement",
                    "bearer_unit_deep_strike",
                    "bearer_unit_phase_move_types",
                    "bearer_unit_phase_move_terrain_only_types",
                    "bearer_unit_phase_move_engagement_types",
                    "bearer_unit_phase_move_block_titanic_types",
                    "bearer_unit_auto_pass_desperate_escape",
                    "enhancement_kunnin_but_brutal_active",
                ):
                    if key in sr:
                        del sr[key]
                u.special_rules = sr
            except Exception:
                pass
            try:
                cache = getattr(u, "_ability_cache", None)
                if isinstance(cache, dict):
                    for k in list(cache.keys()):
                        if k == "feel_no_pain" or k == "deep_strike" or k.startswith("target_hit_penalty:") or k.startswith("model_invulnerable_save:"):
                            del cache[k]
                        if k.startswith("model_save_characteristic:"):
                            del cache[k]
            except Exception:
                pass

        seen = set()
        charge_mods: list[tuple[int, str]] = []
        advance_mods: list[tuple[int, str]] = []
        leadership_sets: list[tuple[int, str]] = []
        leadership_controlled_objective_mods: list[tuple[int, str]] = []
        movement_sets: list[tuple[int, str]] = []
        movement_bonus_mods: list[tuple[int, str]] = []
        oc_mods: list[tuple[int, str]] = []
        contains_oc_mods: list[tuple[int, str]] = []
        fnp_entries: list[dict] = []
        bearer_unit_keyword_fnp_entries: list[dict] = []
        attached_character_fnp_entries: list[dict] = []
        unit_contains_character_fnp_entries: list[dict] = []
        same_unit_keyword_fnp_entries: list[dict] = []
        invuln_entries: list[dict] = []
        sustained_hits_value = 0
        sustained_hits_value_melee = 0
        sustained_hits_value_ranged = 0
        ignores_cover_sources: set[str] = set()
        benefit_of_cover_entries: list[dict] = []
        benefit_of_cover_seen: set[tuple[str, str]] = set()
        hit_penalties: list[dict] = []
        assault_ranged = False
        pile_in_distance_override = 0
        consolidate_distance_override = 0
        consolidate_requires_engagement = False
        phase_move_types: set[str] = set()
        phase_move_terrain_only_types: set[str] = set()
        phase_engagement_types: set[str] = set()
        auto_pass_desperate_escape = False
        grant_deep_strike = False
        kunnin_but_brutal_active = False
        agile_maneuver_reroll = False

        def _iter_sentences(text: str) -> list[str]:
            if not text:
                return []
            cleaned = re.sub(r";\s*", ". ", text)
            return [part.strip() for part in re.split(r"\.\s*", cleaned) if part.strip()]

        def _parse_move_types(value: str) -> set[str]:
            return self._parse_move_types_from_text(value)

        def _attached_unit_has_model_with_keyword(keyword: str) -> bool:
            kw = str(keyword or "").strip()
            if not kw:
                return False
            for member in members:
                if member is None:
                    continue
                model_list = list(getattr(member, "models", []) or [])
                for mdl in model_list:
                    if not bool(getattr(mdl, "is_alive", False)):
                        continue
                    has_any = getattr(mdl, "has_any_keyword", None)
                    if callable(has_any):
                        try:
                            if bool(has_any(kw)):
                                return True
                        except Exception:
                            pass
                    has_local_any = getattr(member, "has_any_keyword_local", None)
                    if callable(has_local_any):
                        try:
                            if bool(has_local_any(kw)):
                                return True
                        except Exception:
                            pass
                    has_effective_any = getattr(member, "has_any_keyword", None)
                    if callable(has_effective_any):
                        try:
                            if bool(has_effective_any(kw)):
                                return True
                        except Exception:
                            pass
            return False

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                key = (
                    str(name or "").strip().lower(),
                    u._normalize_rules_text(desc or "").lower(),
                )
                if key in seen:
                    continue
                seen.add(key)
                text = u._normalize_rules_text(desc or name or "")
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                text_lower = text.lower()
                requires_attached_leader = bool(
                    re.search(r"\b(?:this model|the bearer|bearer|this unit)\s+is\s+leading\b", text_lower)
                    or re.search(r"\bleading\s+a\s+unit\b", text_lower)
                )
                if requires_attached_leader and not getattr(u, "is_attached_leader", False):
                    continue
                if "leading a unit" in text_lower and "bearer's unit" not in text_lower:
                    text = re.sub(r"\bthat unit\b", "the bearer's unit", text, flags=re.IGNORECASE)

                for sentence in _iter_sentences(text):
                    if not sentence:
                        continue
                    m = self._BEARER_UNIT_ADVANCE_AND_CHARGE_BONUS_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            advance_mods.append((val, source))
                            charge_mods.append((val, source))
                    m = self._BEARER_UNIT_ADVANCE_BONUS_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            advance_mods.append((val, source))
                    m = self._BEARER_UNIT_CHARGE_BONUS_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            charge_mods.append((val, source))

                    m = self._BEARER_UNIT_LEADERSHIP_SET_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            leadership_sets.append((val, source))

                    m = self._BEARER_UNIT_CONTROLLED_OBJECTIVE_LEADERSHIP_IMPROVE_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            # Lower Leadership characteristic is better in 10e.
                            leadership_controlled_objective_mods.append((-int(val), source))

                    m = self._BEARER_UNIT_MOVEMENT_SET_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            movement_sets.append((val, source))

                    m = self._BEARER_UNIT_MOVEMENT_BONUS_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            movement_bonus_mods.append((val, source))

                    m = self._BEARER_UNIT_OC_BONUS_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            oc_mods.append((val, source))

                    m = self._BEARER_UNIT_PILE_IN_CONSOLIDATE_DISTANCE_OVERRIDE_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            pile_in_distance_override = max(pile_in_distance_override, int(val))
                            consolidate_distance_override = max(consolidate_distance_override, int(val))

                    m = self._BEARER_UNIT_CONSOLIDATE_DISTANCE_OVERRIDE_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            consolidate_distance_override = max(consolidate_distance_override, int(val))

                    m = self._BEARER_UNIT_CONSOLIDATE_ADDITIONAL_DISTANCE_IF_ENGAGEMENT_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            consolidate_distance_override = max(consolidate_distance_override, int(3 + int(val)))
                            consolidate_requires_engagement = True

                    m = self._UNIT_CONTAINS_OC_BONUS_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group("amt"))
                        except Exception:
                            val = None
                        if val:
                            target = m.group("model")
                            if u._unit_contains_model_named(target):
                                source = str(name or "Unit contains ability").strip() or "Unit contains ability"
                                contains_oc_mods.append((val, source))

                    attached_character_fnp_matched = False
                    m = self._ATTACHED_CHARACTER_FNP_RE.search(sentence)
                    if m:
                        try:
                            g1 = m.group(1)
                        except Exception:
                            g1 = None
                        try:
                            g2 = m.group(2)
                        except Exception:
                            g2 = None
                        try:
                            val = int(g1 or g2 or 0)
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            attached_character_fnp_entries.append(
                                {
                                    "value": int(val),
                                    "source": source,
                                    "exclude_unit_id": get_entity_id(u),
                                }
                            )
                            attached_character_fnp_matched = True

                    bearer_unit_keyword_fnp_matched = False
                    m = self._BEARER_UNIT_KEYWORD_FNP_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group("value"))
                        except Exception:
                            val = None
                        keyword = str(m.group("keyword") or "").strip()
                        if val and keyword:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            bearer_unit_keyword_fnp_entries.append(
                                {
                                    "value": int(val),
                                    "source": source,
                                    "keyword": keyword,
                                }
                            )
                            bearer_unit_keyword_fnp_matched = True

                    m = self._BEARER_UNIT_FNP_RE.search(sentence)
                    if m and not attached_character_fnp_matched and not bearer_unit_keyword_fnp_matched:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            cond = None
                            try:
                                sm = sentence.lower()
                                cm = re.search(
                                    r"(?:feel\s+no\s+pain|fnp)\s*\(?[1-6]\+(?:\)?)\s+(?:ability\s+)?(against|while|when)\s+(.+)",
                                    sm,
                                    flags=re.IGNORECASE,
                                )
                                if cm and cm.group(1) and cm.group(2):
                                    cond = f"{cm.group(1)} {cm.group(2)}".strip()
                            except Exception:
                                cond = None
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            fnp_entries.append({"value": int(val), "condition": cond, "source": source})

                    m = self._UNIT_CONTAINS_CHARACTER_FNP_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group("value"))
                        except Exception:
                            val = None
                        target = m.group("model") if m else None
                        if val and target and u._unit_contains_model_named(target):
                            source = str(name or "Unit contains ability").strip() or "Unit contains ability"
                            unit_contains_character_fnp_entries.append(
                                {
                                    "value": int(val),
                                    "source": source,
                                }
                            )

                    m = self._SAME_UNIT_KEYWORD_FNP_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group("value"))
                        except Exception:
                            val = None
                        keyword = str(m.group("keyword") or "").strip()
                        if val and keyword and _attached_unit_has_model_with_keyword(keyword):
                            source = str(name or "Unit keyword ability").strip() or "Unit keyword ability"
                            same_unit_keyword_fnp_entries.append(
                                {
                                    "value": int(val),
                                    "source": source,
                                    "keyword": keyword,
                                }
                            )

                    unit_contains_invuln_matched = False
                    m = self._UNIT_CONTAINS_INVULNERABLE_SAVE_RE.search(sentence)
                    if m:
                        unit_contains_invuln_matched = True
                        try:
                            val = int(m.group("value"))
                        except Exception:
                            val = None
                        target = m.group("model") if m else None
                        if val and target and u._unit_contains_model_named(target):
                            source = str(name or "Unit contains ability").strip() or "Unit contains ability"
                            invuln_entries.append({"value": int(val), "source": source})

                    if not unit_contains_invuln_matched:
                        m = self._BEARER_UNIT_INVULNERABLE_SAVE_RE.search(sentence)
                        if m:
                            try:
                                val = int(m.group(1))
                            except Exception:
                                val = None
                            if val:
                                source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                                invuln_entries.append({"value": int(val), "source": source})
                    if self._BEARER_UNIT_AGILE_MANEUVER_REROLL_RE.search(sentence):
                        agile_maneuver_reroll = True

                    m = self._BEARER_UNIT_SUSTAINED_HITS_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            scope = sentence.lower()
                            has_melee = "melee" in scope
                            has_ranged = "ranged" in scope
                            if has_melee and not has_ranged:
                                sustained_hits_value_melee = max(int(sustained_hits_value_melee), int(val))
                            elif has_ranged and not has_melee:
                                sustained_hits_value_ranged = max(int(sustained_hits_value_ranged), int(val))
                            elif has_melee and has_ranged:
                                sustained_hits_value_melee = max(int(sustained_hits_value_melee), int(val))
                                sustained_hits_value_ranged = max(int(sustained_hits_value_ranged), int(val))
                            else:
                                sustained_hits_value = max(int(sustained_hits_value), int(val))

                    if self._BEARER_UNIT_IGNORES_COVER_RE.search(sentence):
                        source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                        ignores_cover_sources.add(source)
                    if self._BEARER_UNIT_ASSAULT_RANGED_RE.search(sentence):
                        assault_ranged = True

                    objective_cover_matched = False
                    m = self._OBJECTIVE_RANGE_BENEFIT_OF_COVER_RE.search(sentence)
                    if m:
                        atype = (m.group("atype") or "any").strip().lower()
                        controlled = bool(m.group("controlled"))
                        source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                        key = (atype, source.lower(), "objective", "controlled" if controlled else "any")
                        if key not in benefit_of_cover_seen:
                            benefit_of_cover_seen.add(key)
                            benefit_of_cover_entries.append(
                                {
                                    "attack_type": atype,
                                    "source": source,
                                    "requires_objective": True,
                                    "requires_objective_controlled": bool(controlled),
                                }
                            )
                        objective_cover_matched = True
                    if not objective_cover_matched:
                        m = self._BEARER_UNIT_BENEFIT_OF_COVER_RE.search(sentence)
                        if m:
                            atype = (m.group("atype") or "any").strip().lower()
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            key = (atype, source.lower(), "any", "any")
                            if key not in benefit_of_cover_seen:
                                benefit_of_cover_seen.add(key)
                                benefit_of_cover_entries.append({"attack_type": atype, "source": source})

                    m = self._BEARER_UNIT_TARGET_HIT_PENALTY_RE.search(sentence)
                    if m:
                        atype = (m.group("atype") or "any").strip().lower()
                        source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                        hit_penalties.append({"value": 1, "attack_type": atype, "source": source})

                    sentence_lower = sentence.lower()
                    if self._BEARER_UNIT_DEEP_STRIKE_RE.search(sentence_lower):
                        grant_deep_strike = True

                    if self._BEARER_UNIT_PHASE_MOVE_RE.search(sentence_lower):
                        move_types = _parse_move_types(sentence_lower)
                        if move_types:
                            phase_move_types.update(move_types)
                    elif self._BEARER_UNIT_PHASE_TERRAIN_ONLY_RE.search(sentence_lower):
                        move_types = _parse_move_types(sentence_lower)
                        if move_types:
                            phase_move_terrain_only_types.update(move_types)

                    if self._BEARER_UNIT_PHASE_ENGAGEMENT_RE.search(sentence_lower):
                        move_types = _parse_move_types(sentence_lower)
                        if move_types:
                            phase_engagement_types.update(move_types)
                        if "desperate escape" in sentence_lower and "automatic" in sentence_lower and "pass" in sentence_lower:
                            auto_pass_desperate_escape = True

            try:
                sr = getattr(u, "special_rules", None)
            except Exception:
                sr = None
            if isinstance(sr, dict) and getattr(u, "is_attached_leader", False):
                if sr.get("enhancement_kunnin_but_brutal"):
                    kunnin_but_brutal_active = True

        if charge_mods:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                mods = list(sr.get("charge_roll_modifiers", []) or [])
                for val, source in charge_mods:
                    mods.append({
                        "value": int(val),
                        "source": source,
                        "tag": "ability:bearer_unit_charge_bonus",
                    })
                sr["charge_roll_modifiers"] = mods
                u.special_rules = sr

        if advance_mods:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                mods = list(sr.get("advance_roll_modifiers", []) or [])
                for val, source in advance_mods:
                    mods.append({
                        "value": int(val),
                        "source": source,
                        "tag": "ability:bearer_unit_advance_bonus",
                    })
                sr["advance_roll_modifiers"] = mods
                u.special_rules = sr

        if leadership_sets:
            from ...utility.modifiers import Modifier, ModifierOp

            for u in members:
                for val, source in leadership_sets:
                    u.add_characteristic_modifier(
                        "leadership",
                        Modifier(ModifierOp.SET, int(val), source=f"ability:bearer_unit_leadership:{source}"),
                    )

        if leadership_controlled_objective_mods:
            deduped_entries = []
            seen_entries: set[tuple[int, str]] = set()
            for val, source in leadership_controlled_objective_mods:
                key = (int(val), str(source or "").strip())
                if key in seen_entries:
                    continue
                seen_entries.add(key)
                deduped_entries.append({"value": int(val), "source": key[1] or "Bearer unit ability"})
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_leadership_bonus_controlled_objective"] = list(deduped_entries)
                u.special_rules = sr

        if movement_sets:
            from ...utility.modifiers import Modifier, ModifierOp

            for u in members:
                for val, source in movement_sets:
                    u.add_characteristic_modifier(
                        "movement",
                        Modifier(ModifierOp.SET, int(val), source=f"ability:bearer_unit_movement_set:{source}"),
                    )

        if movement_bonus_mods:
            from ...utility.modifiers import Modifier, ModifierOp

            seen_bonus: set[tuple[int, str]] = set()
            for val, source in movement_bonus_mods:
                try:
                    ival = int(val)
                except Exception:
                    continue
                if ival == 0:
                    continue
                key = (ival, str(source or "").strip())
                if key in seen_bonus:
                    continue
                seen_bonus.add(key)
                label = key[1] or "Bearer unit ability"
                for u in members:
                    u.add_characteristic_modifier(
                        "movement",
                        Modifier(ModifierOp.ADD, ival, source=f"ability:bearer_unit_movement_bonus:{label}"),
                    )

        if oc_mods:
            from ...utility.modifiers import Modifier, ModifierOp

            for u in members:
                for val, source in oc_mods:
                    u.add_characteristic_modifier(
                        "objective_control",
                        Modifier(ModifierOp.ADD, int(val), source=f"ability:bearer_unit_objective_control:{source}"),
                    )

        if contains_oc_mods:
            from ...utility.modifiers import Modifier, ModifierOp

            for u in members:
                for val, source in contains_oc_mods:
                    u.add_characteristic_modifier(
                        "objective_control",
                        Modifier(ModifierOp.ADD, int(val), source=f"ability:unit_contains_objective_control:{source}"),
                    )

        if fnp_entries:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_fnp"] = list(fnp_entries)
                u.special_rules = sr
        if bearer_unit_keyword_fnp_entries:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_keyword_fnp_entries"] = list(bearer_unit_keyword_fnp_entries)
                u.special_rules = sr
        if attached_character_fnp_entries:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["attached_character_fnp_entries"] = list(attached_character_fnp_entries)
                u.special_rules = sr
        if unit_contains_character_fnp_entries:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["unit_contains_character_fnp_entries"] = list(unit_contains_character_fnp_entries)
                u.special_rules = sr
        if same_unit_keyword_fnp_entries:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["same_unit_keyword_fnp_entries"] = list(same_unit_keyword_fnp_entries)
                u.special_rules = sr

        if invuln_entries:
            deduped = []
            seen_invuln = set()
            for entry in invuln_entries:
                try:
                    val = int(entry.get("value"))
                except Exception:
                    continue
                source = str(entry.get("source", "") or "")
                key = (val, source)
                if key in seen_invuln:
                    continue
                seen_invuln.add(key)
                deduped.append({"value": val, "source": source})
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_invulnerable_save"] = list(deduped)
                u.special_rules = sr

        if agile_maneuver_reroll:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_agile_maneuver_reroll"] = True
                u.special_rules = sr

        if sustained_hits_value:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_sustained_hits_value"] = int(sustained_hits_value)
                u.special_rules = sr
        if sustained_hits_value_melee:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_sustained_hits_value_melee"] = int(sustained_hits_value_melee)
                u.special_rules = sr
        if sustained_hits_value_ranged:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_sustained_hits_value_ranged"] = int(sustained_hits_value_ranged)
                u.special_rules = sr

        if ignores_cover_sources:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_ignores_cover"] = True
                u.special_rules = sr

        try:
            if not assault_ranged:
                for u in members:
                    sr = getattr(u, "special_rules", None)
                    if isinstance(sr, dict) and sr.get("enhancement_bestial_aspect"):
                        assault_ranged = True
                        break
        except Exception:
            pass

        if assault_ranged:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_assault_ranged"] = True
                u.special_rules = sr

        if benefit_of_cover_entries:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_benefit_of_cover"] = list(benefit_of_cover_entries)
                u.special_rules = sr

        if hit_penalties:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_target_hit_penalties"] = list(hit_penalties)
                u.special_rules = sr

        if pile_in_distance_override:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_pile_in_distance_override"] = int(pile_in_distance_override)
                u.special_rules = sr

        if consolidate_distance_override:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_consolidate_distance_override"] = int(consolidate_distance_override)
                u.special_rules = sr
        if consolidate_requires_engagement:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_consolidate_requires_engagement"] = True
                u.special_rules = sr

        if grant_deep_strike:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_deep_strike"] = True
                u.special_rules = sr

        if phase_move_types:
            move_types_sorted = sorted(phase_move_types)
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_phase_move_types"] = list(move_types_sorted)
                u.special_rules = sr

        if phase_move_terrain_only_types:
            move_types_sorted = sorted(phase_move_terrain_only_types)
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_phase_move_terrain_only_types"] = list(move_types_sorted)
                u.special_rules = sr

        if phase_engagement_types:
            move_types_sorted = sorted(phase_engagement_types)
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_phase_move_engagement_types"] = list(move_types_sorted)
                u.special_rules = sr

        if auto_pass_desperate_escape:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_auto_pass_desperate_escape"] = True
                u.special_rules = sr

        if kunnin_but_brutal_active:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["enhancement_kunnin_but_brutal_active"] = True
                u.special_rules = sr

        self._refresh_bearer_wounds_bonuses()

    def _refresh_bearer_wounds_bonuses(self) -> None:
        """Apply bearer-only wound modifiers from abilities (set/base bonuses)."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        if not models:
            return

        bonus_by_name: dict[str, int] = {}
        set_by_name: dict[str, int] = {}
        for ab in list(getattr(root, "possible_abilities", []) or []):
            try:
                atype = str(getattr(ab, "type", "") or "").lower()
                if ("wargear" not in atype) and ("datasheet" not in atype):
                    continue
                name = str(getattr(ab, "name", "") or "").strip()
                if not name:
                    continue
                desc = str(getattr(ab, "description", "") or "")
                normalized = self._normalize_rules_text(desc)
                if not normalized:
                    continue
                normalized = normalized.replace("\u2019", "'").lower()
                set_match = self._BEARER_WOUNDS_SET_RE.search(normalized)
                if set_match:
                    try:
                        set_val = int(set_match.group(1) or 0)
                    except Exception:
                        set_val = 0
                    if set_val > 0:
                        set_by_name[self._norm_wargear_name(name)] = int(set_val)
                m = self._BEARER_WOUNDS_BONUS_RE.search(normalized)
                if not m:
                    continue
                try:
                    val = int(m.group(1) or 0)
                except Exception:
                    val = 0
                if val <= 0:
                    continue
                bonus_by_name[self._norm_wargear_name(name)] = int(val)
            except Exception:
                continue

        for model in list(models or []):
            if model is None:
                continue
            base_unmod = getattr(model, "_base_wounds_unmodified", None)
            if base_unmod is None:
                try:
                    base_unmod = int(getattr(model, "_base_wounds", 0) or 0)
                except Exception:
                    base_unmod = 0
                setattr(model, "_base_wounds_unmodified", int(base_unmod))
            try:
                base_unmod = int(base_unmod or 0)
            except Exception:
                base_unmod = 0
            bonus = 0
            set_values: list[int] = []
            try:
                for wg in list(getattr(model, "wargear", []) or []):
                    nm = self._norm_wargear_name(getattr(wg, "name", "") or "")
                    if nm in set_by_name:
                        set_values.append(int(set_by_name.get(nm, 0) or 0))
                    if nm in bonus_by_name:
                        bonus += int(bonus_by_name.get(nm, 0) or 0)
            except Exception:
                pass
            try:
                for ow in list(getattr(model, "optional_wargear", []) or []):
                    nm = self._norm_wargear_name(str(ow or ""))
                    if nm in set_by_name:
                        set_values.append(int(set_by_name.get(nm, 0) or 0))
                    if nm in bonus_by_name:
                        bonus += int(bonus_by_name.get(nm, 0) or 0)
            except Exception:
                pass
            set_base = 0
            if set_values:
                try:
                    set_base = max(int(v or 0) for v in set_values)
                except Exception:
                    set_base = 0
            desired_base = (int(set_base) if int(set_base or 0) > 0 else int(base_unmod)) + int(bonus or 0)
            try:
                prev_base = int(getattr(model, "_base_wounds", 0) or 0)
            except Exception:
                prev_base = 0
            if prev_base != desired_base:
                try:
                    current = int(getattr(model, "_wounds", 0) or 0)
                except Exception:
                    current = 0
                missing = max(0, prev_base - current)
                if current == prev_base:
                    model._wounds = int(desired_base)
                else:
                    model._wounds = max(0, int(desired_base) - int(missing))
                model._base_wounds = int(desired_base)

        try:
            root.starting_total_wounds = sum(int(getattr(m, "_base_wounds", 0) or 0) for m in list(root.models or []))
        except Exception:
            pass

    def _parse_advance_no_roll_distance(self, text: str) -> Optional[int]:
        if not text:
            return None
        low = str(text).lower().replace("\u2019", "'").replace("\u0192?T", "'")
        if "advance" not in low:
            return None
        if "do not make an advance roll" not in low:
            return None
        if "move characteristic" not in low:
            return None
        m = self._ADVANCE_NO_ROLL_MOVE_RE.search(low)
        if not m:
            return None
        try:
            dist = int(m.group(1))
        except Exception:
            return None
        if dist <= 0:
            return None
        return int(dist)

    def _parse_advance_ignore_vertical_distance(self, text: str) -> bool:
        if not text:
            return False
        low = str(text).lower().replace("\u2019", "'").replace("\u0192?T", "'")
        if "advance" not in low:
            return False
        return bool(self._ADVANCE_IGNORE_VERTICAL_RE.search(low))

    def _refresh_advance_no_roll_flags(self) -> None:
        """Parse fixed Advance distance rules that replace the Advance roll."""
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

        ability_tag = "ability:advance_no_roll"
        ignore_tag = "ability:advance_ignore_vertical_distance"

        # Clear previous ability-derived entries while preserving other sources (e.g., stratagems).
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            effects = list(sr.get("advance_no_roll_effects", []) or [])
            kept = [e for e in effects if not (isinstance(e, dict) and e.get("tag") == ability_tag)]
            if kept:
                sr["advance_no_roll_effects"] = kept
            else:
                sr.pop("advance_no_roll_effects", None)
            ignore_effects = list(sr.get("advance_ignore_vertical_distance_effects", []) or [])
            kept_ignore = [
                e for e in ignore_effects if not (isinstance(e, dict) and e.get("tag") == ignore_tag)
            ]
            if kept_ignore:
                sr["advance_ignore_vertical_distance_effects"] = kept_ignore
            else:
                sr.pop("advance_ignore_vertical_distance_effects", None)
            u.special_rules = sr

        parsed: list[tuple[int, str]] = []
        parsed_ignore: list[str] = []
        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = u._strip_eligibility_prefix(desc or name or "")
                text = u._normalize_rules_text(text_src or "")
                dist = u._parse_advance_no_roll_distance(text)
                if not dist:
                    dist = None
                source = str(name or "Advance no-roll ability").strip() or "Advance no-roll ability"
                if dist:
                    parsed.append((int(dist), source))
                if u._parse_advance_ignore_vertical_distance(text):
                    parsed_ignore.append(source)

        if parsed:
            best_dist = max(dist for dist, _src in parsed)
            sources = sorted({src for dist, src in parsed if dist == best_dist})
            source_label = ", ".join(sources) if sources else "Advance no-roll ability"
            entry = {
                "distance": int(best_dist),
                "source": source_label,
                "tag": ability_tag,
            }

            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                effects = list(sr.get("advance_no_roll_effects", []) or [])
                effects.append(dict(entry))
                sr["advance_no_roll_effects"] = effects
                u.special_rules = sr

        if parsed_ignore:
            sources = sorted({src for src in parsed_ignore if src})
            source_label = ", ".join(sources) if sources else "Advance vertical distance ignore"
            entry = {
                "source": source_label,
                "tag": ignore_tag,
            }
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                effects = list(sr.get("advance_ignore_vertical_distance_effects", []) or [])
                effects.append(dict(entry))
                sr["advance_ignore_vertical_distance_effects"] = effects
                u.special_rules = sr

    def _refresh_ignore_vertical_distance_move_types(self) -> None:
        """Parse abilities that ignore vertical distance for specific move types."""
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

        ability_tag = "ability:ignore_vertical_distance_move_types"

        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            effects = list(sr.get("ignore_vertical_distance_effects", []) or [])
            kept = [e for e in effects if not (isinstance(e, dict) and e.get("tag") == ability_tag)]
            if kept:
                sr["ignore_vertical_distance_effects"] = kept
            else:
                sr.pop("ignore_vertical_distance_effects", None)
            u.special_rules = sr

        parsed_types: set[str] = set()
        parsed_sources: set[str] = set()
        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = u._strip_eligibility_prefix(desc or name or "")
                text = u._normalize_rules_text(text_src or "")
                low = str(text or "").lower()
                if "ignore" not in low or "vertical distance" not in low:
                    continue
                move_types = u._parse_move_types_from_text(low)
                if not move_types:
                    continue
                parsed_types.update(move_types)
                parsed_sources.add(str(name or "Ignore vertical distance").strip() or "Ignore vertical distance")

        if parsed_types:
            source_label = ", ".join(sorted(parsed_sources)) if parsed_sources else "Ignore vertical distance"
            entry = {
                "move_types": sorted(parsed_types),
                "source": source_label,
                "tag": ability_tag,
            }
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                effects = list(sr.get("ignore_vertical_distance_effects", []) or [])
                effects.append(dict(entry))
                sr["ignore_vertical_distance_effects"] = effects
                u.special_rules = sr

    def _get_advance_no_roll_effect(self) -> Optional[dict]:
        """Return the best active fixed-Advance effect that replaces the Advance roll."""
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
        try:
            members = sorted(members, key=lambda u: str(get_entity_id(u) or ""))
        except Exception:
            members = list(members)
        effects: list[dict] = []
        for member in members:
            sr = getattr(member, "special_rules", None)
            member_effects = sr.get("advance_no_roll_effects") if isinstance(sr, dict) else None
            if not isinstance(member_effects, list) or not member_effects:
                continue
            effects.extend([entry for entry in member_effects if isinstance(entry, dict)])
        if not effects:
            return None

        phase_name = ""
        try:
            army = root.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            phase_name = ""

        best: Optional[dict] = None
        best_dist = -1
        for effect in effects:
            if not isinstance(effect, dict):
                continue
            try:
                dist = int(effect.get("distance", 0) or 0)
            except Exception:
                continue
            if dist <= 0:
                continue
            exp = str(effect.get("expires_phase", "") or "").strip().upper()
            if exp and phase_name and exp != phase_name:
                continue
            if dist > best_dist:
                best_dist = dist
                best = {
                    "distance": int(dist),
                    "source": str(effect.get("source", "") or "").strip(),
                    "tag": str(effect.get("tag", "") or "").strip(),
                    "expires_phase": exp,
                }
        return best

    def ignores_vertical_distance_for_move_type(self, movement_type) -> bool:
        """Return True if this unit ignores vertical distance for the given move type."""
        def _tag(value) -> str:
            low = str(value or "").lower()
            if "advance" in low:
                return "advance"
            if "fall back" in low or "fallback" in low or "fall_back" in low:
                return "fall_back"
            if "charge" in low:
                return "charge"
            if "move" in low or "normal" in low:
                return "move"
            return low

        mt = _tag(movement_type)
        if not mt:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        effects = sr.get("ignore_vertical_distance_effects") if isinstance(sr, dict) else None
        if not isinstance(effects, list) or not effects:
            return False
        for effect in effects:
            if not isinstance(effect, dict):
                continue
            try:
                types = list(effect.get("move_types", []) or [])
            except Exception:
                types = []
            if mt in types:
                return True
        return False

    def advance_ignores_vertical_distance(self) -> bool:
        """Return True if this unit ignores vertical distance when Advancing."""
        try:
            if self.ignores_vertical_distance_for_move_type("advance"):
                return True
        except Exception:
            pass
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        effects = sr.get("advance_ignore_vertical_distance_effects") if isinstance(sr, dict) else None
        if not isinstance(effects, list) or not effects:
            return False

        phase_name = ""
        try:
            army = root.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            phase_name = ""

        for effect in effects:
            if not isinstance(effect, dict):
                continue
            exp = str(effect.get("expires_phase", "") or "").strip().upper()
            if exp and phase_name and exp != phase_name:
                continue
            return True
        return False

    def _refresh_bearer_keyword_flags(self) -> None:
        """Parse bearer-only keyword additions/removals into special_rules."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        for u in members:
            try:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                if "ability_added_keywords" in sr:
                    del sr["ability_added_keywords"]
                if "ability_removed_keywords" in sr:
                    del sr["ability_removed_keywords"]
                u.special_rules = sr
            except Exception:
                continue

        unit_added_keywords: list[str] = []

        for u in members:
            added: list[str] = []
            removed: list[str] = []
            unit_added: list[str] = []
            for ab in u._iter_active_abilities():
                try:
                    if isinstance(ab, str):
                        desc = ab
                    else:
                        desc = str(getattr(ab, "description", "") or getattr(ab, "name", "") or "")
                except Exception:
                    desc = ""
                text = u._normalize_rules_text(desc or "")
                if not text:
                    continue
                text_lower = text.lower()
                if "leading a unit" in text_lower and "bearer's unit" not in text_lower:
                    text = re.sub(r"\bthat unit\b", "the bearer's unit", text, flags=re.IGNORECASE)
                norm = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
                norm = re.sub(r"'s\b", "s", norm)
                norm = re.sub(r"[^a-z0-9]+", " ", norm)
                norm = re.sub(r"\s+", " ", norm).strip()
                if re.fullmatch(r"(?:the )?" + re.escape(self._BEARER_SMOKE_KEYWORD_TOKENS), norm):
                    added.append("Smoke")
                if re.search(r"\b" + re.escape(self._BEARER_LOSES_SMOKE_KEYWORD_TOKENS) + r"\b", norm):
                    removed.append("Smoke")
                if re.fullmatch(r"(?:the )?bearers unit has the grenades keyword", norm):
                    unit_added.append("Grenades")
                if re.fullmatch(r"this unit has the grenades keyword", norm):
                    unit_added.append("Grenades")
            if added or removed:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
            if added:
                seen = set()
                unique = []
                for kw in added:
                    k = str(kw).strip()
                    lk = k.lower()
                    if not k or lk in seen:
                        continue
                    seen.add(lk)
                    unique.append(k)
                if unique:
                    sr["ability_added_keywords"] = unique
            if removed:
                seen = set()
                unique = []
                for kw in removed:
                    k = str(kw).strip()
                    lk = k.lower()
                    if not k or lk in seen:
                        continue
                    seen.add(lk)
                    unique.append(k)
                if unique:
                    sr["ability_removed_keywords"] = unique
            if added or removed:
                u.special_rules = sr
            if unit_added:
                for kw in unit_added:
                    unit_added_keywords.append(kw)

        if unit_added_keywords:
            seen = set()
            unique = []
            for kw in unit_added_keywords:
                k = str(kw).strip()
                lk = k.lower()
                if not k or lk in seen:
                    continue
                seen.add(lk)
                unique.append(k)
            if unique:
                for u in members:
                    sr = getattr(u, "special_rules", None)
                    if not isinstance(sr, dict):
                        sr = {}
                    existing = list(sr.get("ability_added_keywords", []) or [])
                    combined = []
                    seen_kw = set()
                    for kw in existing + unique:
                        k = str(kw).strip()
                        lk = k.lower()
                        if not k or lk in seen_kw:
                            continue
                        seen_kw.add(lk)
                        combined.append(k)
                    if combined:
                        sr["ability_added_keywords"] = combined
                    u.special_rules = sr

    def _refresh_move_over_friendly_monster_vehicle_flags(self) -> None:
        """Parse move-over friendly MONSTER/VEHICLE and low-terrain traversal rules into special_rules."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        for key in (
            "move_over_friendly_monster_vehicle_types",
            "move_over_low_terrain_height_types",
            "move_over_low_terrain_height_value",
        ):
            if key in sr:
                del sr[key]

        pattern = (
            r"each time (?:this model|this unit) makes a (?P<moves>.+?) move "
            r"it can move (?:over|through) friendly monster (?:and|or) vehicle models? and "
            r"(?:sections of )?terrain features that are (?P<height>\d+) or less in height"
            r"(?: as if they were not there)?"
        )
        terrain_only_pattern = (
            r"each time (?:this model|this unit) makes a (?P<moves>.+?) move "
            r"it can move (?:over|through) (?:sections of )?terrain features that are (?P<height>\d+) or less in height"
            r"(?: as if they were not there)?"
        )
        friendly_move_types: set[str] = set()
        low_terrain_move_types: set[str] = set()
        height_value: Optional[int] = None
        seen: set[str] = set()

        def _parse_move_types(moves_text: str) -> Optional[set[str]]:
            tokens = [t for t in moves_text.split() if t]
            allowed = {"normal", "advance", "fall", "back", "fallback", "or", "and"}
            if not tokens or any(t not in allowed for t in tokens):
                return None
            if "normal" not in tokens:
                return None
            parsed: set[str] = {"move"}
            if "advance" in tokens:
                parsed.add("advance")
            if "fallback" in tokens or "fall back" in moves_text:
                parsed.add("fall_back")
            return parsed

        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text = str(desc or name or "")
            text = self._strip_eligibility_prefix(text)
            norm = self._normalize_rules_text(text)
            if not norm:
                continue
            norm = norm.replace("\u2019", "'").replace("\u0192?T", "'")
            norm = re.sub(r"'s\b", "s", norm, flags=re.IGNORECASE)
            norm = re.sub(r"[^a-z0-9]+", " ", norm.lower())
            norm = re.sub(r"\s+", " ", norm).strip()
            if not norm or norm in seen:
                continue
            seen.add(norm)
            m = re.fullmatch(pattern, norm)
            if m:
                moves_text = (m.group("moves") or "").strip()
                move_types = _parse_move_types(moves_text or "")
                if move_types is None:
                    continue
                friendly_move_types.update(move_types)
                low_terrain_move_types.update(move_types)
                try:
                    height = int(m.group("height"))
                except Exception:
                    height = None
                if height is not None:
                    if height_value is None or height > height_value:
                        height_value = height
                continue
            m = re.fullmatch(terrain_only_pattern, norm)
            if not m:
                continue
            moves_text = (m.group("moves") or "").strip()
            move_types = _parse_move_types(moves_text or "")
            if move_types is None:
                continue
            low_terrain_move_types.update(move_types)
            try:
                height = int(m.group("height"))
            except Exception:
                height = None
            if height is not None:
                if height_value is None or height > height_value:
                    height_value = height

        if friendly_move_types:
            sr["move_over_friendly_monster_vehicle_types"] = sorted(friendly_move_types)
        if height_value is not None:
            sr["move_over_low_terrain_height_value"] = float(height_value)
            sr["move_over_low_terrain_height_types"] = sorted(low_terrain_move_types or {"move", "advance"})
        self.special_rules = sr
        try:
            self._refresh_titanic_move_through_flags()
        except Exception:
            pass

    def _refresh_titanic_move_through_flags(self) -> None:
        """Parse Titanic move-through models/terrain abilities into special_rules."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        for key in (
            "titanic_phase_move_types",
            "titanic_phase_move_engagement_types",
            "titanic_phase_move_block_titanic_types",
            "titanic_stride_tall_terrain_height",
            "titanic_stride_source",
            "titanic_agility_source",
        ):
            if key in sr:
                del sr[key]

        move_types: set[str] = set()
        engagement_types: set[str] = set()
        block_titanic_types: set[str] = set()
        stride_height: Optional[float] = None
        stride_source: str = ""
        agility_source: str = ""

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
            if self._TITANIC_AGILITY_RE.fullmatch(norm):
                move_types.update({"move", "advance", "fall_back"})
                engagement_types.update({"move", "advance", "fall_back"})
                if not agility_source:
                    agility_source = str(name or "Titanic Agility").strip() or "Titanic Agility"
                continue
            m = self._TITANIC_STRIDES_RE.fullmatch(norm)
            if m:
                move_types.update({"move", "advance", "fall_back"})
                engagement_types.update({"move", "advance", "fall_back"})
                block_titanic_types.update({"move", "advance", "fall_back"})
                if not stride_source:
                    stride_source = str(name or "Titanic Strides").strip() or "Titanic Strides"
                try:
                    height_val = float(m.group("height") or 0)
                except Exception:
                    height_val = 0.0
                if height_val:
                    if stride_height is None or height_val > stride_height:
                        stride_height = float(height_val)

        if move_types:
            sr["titanic_phase_move_types"] = sorted(move_types)
        if engagement_types:
            sr["titanic_phase_move_engagement_types"] = sorted(engagement_types)
        if block_titanic_types:
            sr["titanic_phase_move_block_titanic_types"] = sorted(block_titanic_types)
        if stride_height is not None:
            sr["titanic_stride_tall_terrain_height"] = float(stride_height)
        if stride_source:
            sr["titanic_stride_source"] = stride_source
        if agility_source:
            sr["titanic_agility_source"] = agility_source
        self.special_rules = sr

    def _find_model_named(self, target: str):
        norm_target = self._normalize_attached_unit_name(target)
        if not norm_target:
            return None
        for article in ("an ", "a "):
            if norm_target.startswith(article):
                norm_target = norm_target[len(article):].strip()
        if not norm_target:
            return None
        target_tokens = set(norm_target.split())
        for model in list(getattr(self, "models", []) or []):
            try:
                if not getattr(model, "is_alive", True):
                    continue
            except Exception:
                pass
            name = self._normalize_attached_unit_name(getattr(model, "name", ""))
            if not name:
                continue
            if norm_target in name:
                return model
            if target_tokens and target_tokens.issubset(set(name.split())):
                return model
        return None

    def _unit_contains_model_named(self, target: str) -> bool:
        return self._find_model_named(target) is not None

    def has_formless_horror(self) -> bool:
        """Return True if this unit has the Formless Horror ability."""
        cache_key = "formless_horror"
        cache = getattr(self, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))

        found = False
        for name, desc in self._iter_ability_entries_for_rules(model=None):
            name_norm = self._normalize_keyword_phrase(str(name or ""))
            if name_norm == "formless horror":
                found = True
                break
            text_src = self._normalize_rules_text(desc or name or "")
            if "formless horror" in str(text_src or "").lower():
                found = True
                break

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = bool(found)
        self._ability_cache = cache
        return bool(found)

    def _formless_horror_target_blocked(self, target_unit, *, game=None) -> bool:
        """Return True if this unit is blocked from targeting target_unit due to Formless Horror this phase."""
        if target_unit is None:
            return False
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        if target_root is None:
            return False
        try:
            if not bool(target_root.has_formless_horror()):
                return False
        except Exception:
            return False

        phase_name = ""
        if game is None:
            try:
                game = getattr(self.get_parent_army().player, "game", None)
            except Exception:
                game = None
        try:
            phase = getattr(game, "phase", None) if game is not None else None
            phase_name = str(getattr(phase, "name", phase) or "").strip().upper()
        except Exception:
            phase_name = ""

        try:
            from ...utility.entity_ids import get_entity_id
        except Exception:
            get_entity_id = None
        target_id = str(get_entity_id(target_root)) if callable(get_entity_id) else str(getattr(target_root, "_id", "") or "")

        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        blocked = sr.get("formless_horror_blocked")
        if not isinstance(blocked, dict):
            return False
        # Clean up stale phases (best-effort).
        if phase_name:
            changed = False
            for key in list(blocked.keys()):
                if key != phase_name:
                    blocked.pop(key, None)
                    changed = True
            if changed:
                sr["formless_horror_blocked"] = blocked
                self.special_rules = sr
        if not phase_name:
            # If phase is unknown, be permissive.
            return False
        blocked_ids = {str(v) for v in list(blocked.get(phase_name, []) or []) if v is not None}
        return bool(target_id and target_id in blocked_ids)

    def _formless_horror_gate(
        self,
        target_unit,
        *,
        game=None,
        allow_trigger: bool = True,
    ) -> tuple[bool, str | None]:
        """
        Gate targeting a Formless Horror unit. Returns (allowed, reason).

        If allow_trigger is True and the gate has not been resolved for this decision,
        a Battle-shock test is queued and the gate returns False with a reason.
        """
        if target_unit is None:
            return True, None
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        if target_root is None:
            return True, None
        try:
            if not bool(target_root.has_formless_horror()):
                return True, None
        except Exception:
            return True, None

        if game is None:
            try:
                game = getattr(self.get_parent_army().player, "game", None)
            except Exception:
                game = None
        phase_name = ""
        try:
            phase = getattr(game, "phase", None) if game is not None else None
            phase_name = str(getattr(phase, "name", phase) or "").strip().upper()
        except Exception:
            phase_name = ""

        try:
            from ...utility.entity_ids import get_entity_id
        except Exception:
            get_entity_id = None
        target_id = str(get_entity_id(target_root)) if callable(get_entity_id) else str(getattr(target_root, "_id", "") or "")
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}

        # Clean up stale phase blocks (best-effort).
        blocked = sr.get("formless_horror_blocked")
        if not isinstance(blocked, dict):
            blocked = {}
        if phase_name:
            for key in list(blocked.keys()):
                if key != phase_name:
                    blocked.pop(key, None)
        sr["formless_horror_blocked"] = blocked

        if phase_name and target_id:
            blocked_ids = {str(v) for v in list(blocked.get(phase_name, []) or []) if v is not None}
            if target_id in blocked_ids:
                self.special_rules = sr
                return False, "Formless Horror: cannot target this unit this phase."

        allowed = sr.get("formless_horror_allowed")
        if isinstance(allowed, dict):
            if str(allowed.get("target_id", "") or "") == target_id:
                entry_phase = str(allowed.get("phase", "") or "").strip().upper()
                if not entry_phase or not phase_name or entry_phase == phase_name:
                    self.special_rules = sr
                    return True, None

        pending = sr.get("formless_horror_pending")
        if isinstance(pending, dict):
            pending_target = str(pending.get("target_id", "") or "")
            # If any pending gate exists, do not queue another.
            if pending_target:
                self.special_rules = sr
                return False, "Formless Horror: Battle-shock test pending."

        if not allow_trigger:
            self.special_rules = sr
            return False, "Formless Horror: Battle-shock test required."

        # Queue the Battle-shock test and record pending gate.
        pending = {
            "target_id": target_id,
            "phase": phase_name,
        }
        try:
            if game is not None:
                pending["turn"] = int(getattr(game, "turn", 0) or 0)
        except Exception:
            pass
        sr["formless_horror_pending"] = pending
        # Ensure the test fires even if other suppressions are active.
        sr["battle_shock_allow_suppressed_test"] = True
        self.special_rules = sr
        try:
            current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            self.take_battle_shock_test(current_turn)
        except Exception:
            pass
        return False, "Formless Horror: Battle-shock test required."

    def _clear_formless_horror_allowed(self) -> None:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return
        if "formless_horror_allowed" in sr:
            sr.pop("formless_horror_allowed", None)
            self.special_rules = sr

    def _formless_horror_has_pending_gate(self) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        return isinstance(sr.get("formless_horror_pending"), dict)

    def _unit_contains_model_with_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip().lower()
        if not kw:
            return False
        try:
            models = list(self.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(self, "models", []) or [])
        for model in models:
            if model is None:
                continue
            try:
                alive = getattr(model, "is_alive", True)
                if callable(alive):
                    alive = alive()
            except Exception:
                alive = True
            if not alive:
                continue
            try:
                if hasattr(model, "has_any_keyword") and model.has_any_keyword(kw):
                    return True
            except Exception:
                pass
            try:
                if hasattr(model, "has_keyword") and model.has_keyword(kw):
                    return True
            except Exception:
                pass
            try:
                kws = [str(k or "").strip().lower() for k in (getattr(model, "keywords", []) or [])]
                if kw in kws:
                    return True
            except Exception:
                pass
        return False

