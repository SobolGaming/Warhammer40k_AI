"""Attack-rule extraction helpers for Unit keyword and profile bonus logic."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class PositioningAttackRulesMixin:
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
            text = type(self)._strip_eligibility_prefix(text)
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
                target_exclude_keywords: tuple[str, ...] = ()
                exclude_match = re.search(r"\bexcluding\s+(?P<excluded>.+)$", target_raw, flags=re.IGNORECASE)
                if exclude_match:
                    target_exclude_keywords = _parse_target_keywords(str(exclude_match.group("excluded") or ""))
                    target_raw = re.sub(r"\bexcluding\s+.+$", "", target_raw, flags=re.IGNORECASE).strip(" ,")
                target_keywords = _parse_target_keywords(target_raw)
                if requires_closest_eligible_target:
                    target_keywords = ()
                if (not target_keywords) and ("afflicted" in target_raw.lower()):
                    target_keywords = ("AFFLICTED",)
                if not target_keywords and not target_exclude_keywords and not requires_closest_eligible_target:
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
                    if target_exclude_keywords:
                        entry["target_exclude_keywords_any"] = target_exclude_keywords
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
            text = type(self)._strip_eligibility_prefix(text)
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
        model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
        if not model_id:
            return []
        cache_key = f"model_weapon_keyword_bonus_rules:{model_id}"
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
            text = type(self)._strip_eligibility_prefix(text)

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

        for entry in self._enhancement_weapon_keyword_rules(model=model):
            attack_type = str(entry.get("attack_type", "any") or "any").strip().lower()
            keyword = str(entry.get("keyword", "") or "").strip()
            source_name = str(entry.get("source", "") or "Enhancement").strip() or "Enhancement"
            key = (attack_type, keyword.lower(), source_name.lower())
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


    def _resolve_attack_keyword_bonuses_from_rules(self, rules: list[dict], *, attack_type: Optional[str]) -> dict:
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"

        bonuses = {
            "ignores_cover": False,
            "lethal_hits": False,
            "assault": False,
            "pistol": False,
            "hazardous": False,
            "blast": False,
            "rapid_fire_bonus": 0,
            "melta_bonus": 0,
            "melta_source": "",
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
            elif kw == "PISTOL":
                bonuses["pistol"] = True
                sources.append(f"Pistol ({source})")
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
            elif kw.startswith("MELTA"):
                match = re.search(r"MELTA\s+(\d+)", kw)
                melta_bonus = int(match.group(1)) if match else 1
                if melta_bonus > int(bonuses["melta_bonus"] or 0):
                    bonuses["melta_bonus"] = int(melta_bonus)
                    bonuses["melta_source"] = source
                sources.append(f"Melta {melta_bonus} ({source})")
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
            or bonuses["pistol"]
            or bonuses["hazardous"]
            or bonuses["blast"]
            or int(bonuses["rapid_fire_bonus"] or 0) > 0
            or int(bonuses["melta_bonus"] or 0) > 0
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
