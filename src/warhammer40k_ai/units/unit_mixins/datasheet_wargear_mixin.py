"""Auto-extracted Unit mixin methods from unit.py."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class DatasheetWargearMixin:
    def _transport_disembark_rules(self) -> dict:
        """
        Detect transport abilities that modify disembark behavior (Assault Ramp/Vehicle patterns).

        Returns:
            dict with keys:
              - allow_after_advance (bool): can disembark after transport Advanced
              - allow_charge_after_normal_move (bool): can charge after disembarking from a Normal move
              - allow_charge_after_setup (bool): can charge after disembarking from a transport just set up
        """
        cache_key = "transport_disembark_rules"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rules = {
            "allow_after_advance": False,
            "allow_charge_after_normal_move": False,
            "allow_charge_after_setup": False,
        }

        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text = self._normalize_rules_text(desc or name or "")
            if not text:
                continue
            low = text.lower()

            # Assault Ramp: disembark after Normal move and still eligible to charge.
            if (
                "disembark" in low
                and "after it has made a normal move" in low
                and ("eligible to declare a charge" in low or "can declare a charge" in low)
            ):
                rules["allow_charge_after_normal_move"] = True

            # Drop Pod-style setup disembark: immediate disembark after setup can still charge.
            if (
                "disembark" in low
                and "after it has been set up on the battlefield" in low
                and ("eligible to declare a charge" in low or "can declare a charge" in low)
            ):
                rules["allow_charge_after_setup"] = True

            # Assault Vehicle: disembark after Advance, counts as Normal move, cannot charge.
            if (
                "disembark" in low
                and "after it has advanced" in low
                and "cannot declare a charge" in low
            ):
                rules["allow_after_advance"] = True

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rules
        return rules

    def _parse_attribute(self, attribute_value: str) -> int:
        # Remove " and + from the attribute value
        attribute_value = attribute_value.replace("\"", "").replace("+", "").replace("*", "")
        if "-" in attribute_value:
            return 0
        return int(attribute_value)

    def _parse_range(self, range_string: str) -> Range:
        return Range.from_string(range_string)

    def _is_unknown_base_size(self, base_size: str) -> bool:
        raw = str(base_size or "").strip().lower()
        return raw in ("", "use model", "no official base size")

    def _warn_unknown_base_size(self, model_name: str, fallback_desc: str) -> None:
        if not hasattr(self, "_unknown_base_size_warnings"):
            self._unknown_base_size_warnings = set()
        key = (str(model_name or "").strip().lower(), str(fallback_desc or "").strip().lower())
        if key in self._unknown_base_size_warnings:
            return
        self._unknown_base_size_warnings.add(key)
        logger.warning(f"WARNING: {self.name}: base size for '{model_name or 'model'}' is unspecified; "
            f"using {fallback_desc}.")

    def _strip_flying_base_marker(self, raw: str) -> tuple[str, bool]:
        cleaned = str(raw or "")
        is_flying = "flying base" in cleaned.lower()
        if is_flying:
            cleaned = re.sub(r"flying base", "", cleaned, flags=re.IGNORECASE).strip()
        return cleaned, is_flying

    def _unknown_base_fallback_desc(self) -> str:
        if bool(getattr(self, "is_vehicle", False)) or bool(getattr(self, "is_monster", False)) or bool(getattr(self, "is_transport", False)):
            return "80x40mm hull"
        return "32mm base"

    def _base_size_fallback_warning_desc(
        self,
        base_size: str,
        *,
        fallback_base_size: Optional[str] = None,
    ) -> Optional[str]:
        cleaned, _ = self._strip_flying_base_marker(base_size)
        if self._is_unknown_base_size(cleaned):
            if fallback_base_size and not self._is_unknown_base_size(self._strip_flying_base_marker(fallback_base_size)[0]):
                return None
            return self._unknown_base_fallback_desc()
        if cleaned.replace("mm", "").strip().lower() == "hull":
            return "80x40mm hull"
        return None

    def _parse_base_size(
        self,
        base_size: str,
        *,
        fallback_base_size: Optional[str] = None,
        model_name: str = "",
        emit_unknown_base_warning: bool = True,
    ) -> Base:
        cleaned, is_flying = self._strip_flying_base_marker(base_size)
        if self._is_unknown_base_size(cleaned):
            if fallback_base_size and not self._is_unknown_base_size(fallback_base_size):
                cleaned, fallback_flying = self._strip_flying_base_marker(fallback_base_size)
                is_flying = is_flying or fallback_flying
            else:
                # No reliable base size provided; use a conservative default and warn once.
                if bool(getattr(self, "is_vehicle", False)) or bool(getattr(self, "is_monster", False)) or bool(getattr(self, "is_transport", False)):
                    base = Base(BaseType.HULL, (convert_mm_to_inches(80 / 2), convert_mm_to_inches(40 / 2)))
                    if emit_unknown_base_warning:
                        self._warn_unknown_base_size(model_name, "80x40mm hull")
                else:
                    base = Base(BaseType.CIRCULAR, convert_mm_to_inches(32 / 2.0))
                    if emit_unknown_base_warning:
                        self._warn_unknown_base_size(model_name, "32mm base")
                if is_flying:
                    setattr(base, "is_flying_base", True)
                return base

        cleaned = cleaned.replace("mm", "").strip()
        low_cleaned = cleaned.lower().strip()
        if low_cleaned == "hull":
            base = Base(BaseType.HULL, (convert_mm_to_inches(80 / 2.0), convert_mm_to_inches(40 / 2.0)))
            if emit_unknown_base_warning:
                self._warn_unknown_base_size(model_name, "80x40mm hull")
        elif "x" in cleaned:
            major, minor = cleaned.split("x")
            major = convert_mm_to_inches(float(major.strip()) / 2.0)
            minor = convert_mm_to_inches(float(minor.strip()) / 2.0)
            base = Base(BaseType.ELLIPTICAL, (major, minor))
        else:
            base = Base(BaseType.CIRCULAR, convert_mm_to_inches(float(cleaned.strip()) / 2.0))

        if is_flying:
            setattr(base, "is_flying_base", True)
        return base

    def _apply_resolved_model_geometry(self, model: Model, datasheet, model_name: str):
        if model is None or getattr(model, "model_base", None) is None:
            return None
        unit_keywords = list(getattr(self, "keywords", []) or [])
        unit_keywords.extend(list(getattr(self, "faction_keywords", []) or []))
        datasheet_id = str(getattr(datasheet, "id", "") or "")
        datasheet_name = str(getattr(datasheet, "name", getattr(self, "name", "")) or "")
        resolved = resolve_model_geometry(
            datasheet_id=datasheet_id,
            datasheet_name=datasheet_name,
            model_name=str(model_name or getattr(model, "name", "") or ""),
            unit_keywords=unit_keywords,
            parsed_base_type=model.model_base.base_type,
            parsed_radius=model.model_base.radius,
            parsed_is_flying_base=bool(getattr(model.model_base, "is_flying_base", False)),
        )

        old_base = model.model_base
        new_base = Base(resolved.base_type, resolved.radius)
        new_base.set_model_height(float(resolved.model_height))
        new_base.set_z_offset(float(resolved.z_offset))
        if resolved.compound_parts:
            new_base.set_compound_parts(resolved.compound_parts)
        if bool(getattr(old_base, "is_flying_base", False)):
            setattr(new_base, "is_flying_base", True)
        model.model_base = new_base
        return resolved

    def _normalize_base_size_name(self, text: str) -> str:
        text = (text or "").lower()
        text = re.sub(r"\([^)]*\)", " ", text)
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _parse_base_size_descr_overrides(self, base_size_descr: str) -> dict:
        if not base_size_descr:
            return {}
        base_size_descr = (
            base_size_descr.replace("\u2019", "'")
            .replace("\u2013", "-")
            .replace("\u2014", "-")
        )
        overrides: dict[str, str] = {}
        patterns = [
            r"(?P<name>[A-Za-z0-9 '\-]+?)\s+model\s+(?P<size>\d+(?:\.\d+)?\s*mm|\d+\s*x\s*\d+\s*mm)",
            r"(?P<name>[A-Za-z0-9 '\-]+?)\s+on\s+(?P<size>\d+(?:\.\d+)?\s*mm|\d+\s*x\s*\d+\s*mm)",
            r"(?P<name>[A-Za-z0-9 '\-]+?)\s+(?P<size>\d+(?:\.\d+)?\s*mm|\d+\s*x\s*\d+\s*mm)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, base_size_descr, flags=re.IGNORECASE):
                name = match.group("name").strip()
                size = match.group("size").strip()
                if not re.search(r"[A-Za-z]", name):
                    continue
                overrides[self._normalize_base_size_name(name)] = size
        return overrides

    def _select_base_size_override(self, base_size_descr: str, model_name: str) -> Optional[str]:
        if not base_size_descr or not model_name:
            return None
        overrides = self._parse_base_size_descr_overrides(base_size_descr)
        if not overrides:
            return None
        model_norm = self._normalize_base_size_name(model_name)
        if not model_norm:
            return None
        best = None
        best_len = -1
        for name_norm, size in overrides.items():
            if not name_norm:
                continue
            if name_norm == model_norm or name_norm in model_norm or model_norm in name_norm:
                if len(name_norm) > best_len:
                    best = size
                    best_len = len(name_norm)
        return best

    @property
    def id(self) -> str:
        return self._id

    def _parse_unit_composition(self, unit_composition):
        """
        Parse `datasheets_unit_composition` entries.

        Most entries are simple:
        - "1 Boss Nob"
        - "2-5 Space Marine Bikers"

        Some entries are composite (multiple parts):
        - "1 Runtherd and 10 Gretchin"
        - "1 Grenadier Sergeant, 7 Grenadiers and 1 Heavy Weapons Team"

        We ignore pure informational lines like:
        - "This unit can contain a maximum of 10 models."
        - "10 MODELS MAXIMUM"
        """
        import re

        def _split_top_level_commas(text: str) -> list[str]:
            parts: list[str] = []
            buf: list[str] = []
            depth = 0
            for ch in text:
                if ch == "(":
                    depth += 1
                elif ch == ")" and depth > 0:
                    depth -= 1
                if ch == "," and depth == 0:
                    seg = "".join(buf).strip()
                    if seg:
                        parts.append(seg)
                    buf = []
                else:
                    buf.append(ch)
            tail = "".join(buf).strip()
            if tail:
                parts.append(tail)
            return parts

        def _split_top_level_and(text: str) -> list[str]:
            # Split on " and " only when it looks like it separates entries (next token starts with a digit/range),
            # and only at top-level (not inside parentheses).
            parts: list[str] = []
            buf: list[str] = []
            depth = 0
            i = 0
            while i < len(text):
                ch = text[i]
                if ch == "(":
                    depth += 1
                elif ch == ")" and depth > 0:
                    depth -= 1
                if depth == 0 and text[i : i + 5].lower() == " and ":
                    nxt = text[i + 5 : i + 15].lstrip()
                    if nxt and re.match(r"^\d", nxt):
                        seg = "".join(buf).strip()
                        if seg:
                            parts.append(seg)
                        buf = []
                        i += 5
                        continue
                buf.append(ch)
                i += 1
            tail = "".join(buf).strip()
            if tail:
                parts.append(tail)
            return parts

        # Optional overall cap from informational lines like "10 MODELS MAXIMUM".
        # This is useful for validation and for complex compositions we don't fully model yet.
        self.unit_models_maximum = None

        options: list[dict[str, tuple[int, int]]] = []
        current: dict[str, tuple[int, int]] = {}
        for comp in unit_composition or []:
            desc = str(comp.get("description", "") or "").strip()
            if not desc:
                continue

            dlow = desc.strip().rstrip(".").lower()
            # Capture max models (do not treat as composition entry).
            if dlow.startswith("this unit can contain a maximum of "):
                mmax = re.search(r"maximum of\s+(\d+)\s+models", dlow)
                if mmax:
                    try:
                        self.unit_models_maximum = int(mmax.group(1))
                    except Exception:
                        pass
                continue
            if dlow.endswith("models maximum"):
                mmax = re.search(r"(\d+)\s+models maximum", dlow)
                if mmax:
                    try:
                        self.unit_models_maximum = int(mmax.group(1))
                    except Exception:
                        pass
                continue
            if dlow in ("or", "or:"):
                if current:
                    options.append(current)
                    current = {}
                continue
            if dlow.startswith("one of the following:"):
                continue

            # Remove trailing keyword annotation after an en-dash (" \u2013 EPIC HERO", etc.)
            main = desc.split(" \u2013 ", 1)[0].strip().rstrip(".")

            # Split into segments at top level: commas, then "and" separators.
            segments: list[str] = []
            for seg in _split_top_level_commas(main):
                for s2 in _split_top_level_and(seg):
                    s2 = s2.strip().rstrip(".")
                    if s2:
                        segments.append(s2)

            for seg in segments or [main]:
                seg = seg.strip().rstrip(".")
                m = re.match(r"^(?P<count>\d+(?:-\d+)?)\s+(?P<name>.+)$", seg)
                if not m:
                    continue
                count = m.group("count")
                model_name = m.group("name").strip().rstrip(".")
                if "-" in count:
                    min_size, max_size = map(int, count.split("-", 1))
                else:
                    min_size = max_size = int(count)
                if model_name in current:
                    prev_min, prev_max = current[model_name]
                    current[model_name] = (prev_min + min_size, prev_max + max_size)
                else:
                    current[model_name] = (min_size, max_size)

        if current:
            options.append(current)

        def _total_min(opt: dict[str, tuple[int, int]]) -> int:
            return sum(min_size for min_size, _ in opt.values())

        if options:
            try:
                self.unit_composition_options = options
            except Exception:
                pass
            return min(options, key=_total_min)

        try:
            self.unit_composition_options = []
        except Exception:
            pass
        return {}

    def _normalize_model_name(self, name: str) -> str:
        s = (name or "").replace("\u2019", "'").strip().lower()
        s = re.sub(r"<[^>]+>", " ", s)
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _pick_profile_for_model(self, datasheet, model_name: str) -> dict:
        """
        Datasheets often have multiple model profiles (e.g. Exarch vs regular).
        Unit composition names don't always match profile names 1:1.

        Heuristic: exact/substring match on normalized names; otherwise token overlap with
        light fuzzy matching (biker~bike). Falls back to first profile.
        """
        try:
            profiles = list(getattr(datasheet, "datasheets_models", []) or [])
        except Exception:
            profiles = []
        if not profiles:
            return {}

        want = self._normalize_model_name(model_name)
        want_tokens = set(want.split())

        best = profiles[0]
        best_score = -1

        for prof in profiles:
            pname = self._normalize_model_name(str(prof.get("name", "") or ""))
            if not pname:
                continue
            if pname == want:
                return prof
            if pname and (pname in want or want in pname):
                score = 100
            else:
                p_tokens = set(pname.split())
                overlap = len(want_tokens & p_tokens)
                fuzzy = 0
                if "biker" in want_tokens and "bike" in p_tokens:
                    fuzzy += 1
                if "bikes" in want_tokens and "bike" in p_tokens:
                    fuzzy += 1
                if "bike" in want_tokens and "biker" in p_tokens:
                    fuzzy += 1
                score = overlap + fuzzy

            if score > best_score:
                best = prof
                best_score = score

        return best

    def _resolve_composition_model_name(self, datasheet, model_name: str, *, model_count: int = 1) -> str:
        """
        Convert a composition entry into the per-model name used at runtime.

        Composition rows often pluralize model names ("Jakhals"), but some
        canonical model names legitimately end in "s" ("Khorne Lord of Skulls").
        Preserve exact profile names for single-model rows, then strip a
        trailing "s" when the singular form is explicitly supported by one of
        the model profiles, or when the composition row is creating more than
        one runtime model and therefore represents a plural label.
        """
        name = str(model_name or "").strip()
        if not name:
            return name

        count = int(model_count or 0)
        normalized_name = self._normalize_model_name(name)
        profile_names = {
            self._normalize_model_name(str(profile.get("name", "") or ""))
            for profile in list(getattr(datasheet, "datasheets_models", []) or [])
        }

        if count <= 1 and normalized_name in profile_names:
            return name
        if not name.endswith("s"):
            return name

        singular = name[:-1].strip()
        if not singular:
            return name
        normalized_singular = self._normalize_model_name(singular)
        if normalized_singular in profile_names or count > 1:
            return singular
        return name

    def _select_fallback_base_size(self, datasheet) -> Optional[str]:
        try:
            profiles = list(getattr(datasheet, "datasheets_models", []) or [])
        except Exception:
            profiles = []
        for prof in profiles:
            try:
                raw = str(prof.get("base_size", "") or "").strip()
            except Exception:
                raw = ""
            if raw and not self._is_unknown_base_size(raw):
                return raw
        return None

    def _build_model_from_profile(self, datasheet, model_name: str, profile: dict, *, fallback_base_size: Optional[str] = None) -> Model:
        if not profile:
            profile = datasheet.datasheets_models[0]
        base_size_value = (
            self._select_base_size_override(
                str(profile.get("base_size_descr", datasheet.datasheets_models[0].get("base_size_descr", "")) or ""),
                model_name,
            )
            or profile.get("base_size", datasheet.datasheets_models[0]["base_size"])
        )
        fallback_warning_desc = self._base_size_fallback_warning_desc(
            base_size_value,
            fallback_base_size=fallback_base_size,
        )
        model = Model(
            name=model_name,
            movement=self._parse_attribute(profile.get("M", datasheet.datasheets_models[0]["M"])),
            toughness=self._parse_attribute(profile.get("T", datasheet.datasheets_models[0]["T"])),
            save=self._parse_attribute(profile.get("Sv", datasheet.datasheets_models[0]["Sv"])),
            wounds=self._parse_attribute(profile.get("W", datasheet.datasheets_models[0]["W"])),
            leadership=self._parse_attribute(profile.get("Ld", datasheet.datasheets_models[0]["Ld"])),
            objective_control=self._parse_attribute(profile.get("OC", datasheet.datasheets_models[0]["OC"])),
            model_base=self._parse_base_size(
                base_size_value,
                fallback_base_size=fallback_base_size,
                model_name=model_name,
                emit_unknown_base_warning=False,
            ),
            inv_save=self._parse_attribute(profile.get("inv_sv", datasheet.datasheets_models[0]["inv_sv"])),
            inv_save_condition=str(profile.get("inv_sv_descr", datasheet.datasheets_models[0].get("inv_sv_descr", "")) or "").lower(),
            movement_raw=str(profile.get("M", datasheet.datasheets_models[0].get("M", "")) or ""),
            toughness_raw=str(profile.get("T", datasheet.datasheets_models[0].get("T", "")) or ""),
            save_raw=str(profile.get("Sv", datasheet.datasheets_models[0].get("Sv", "")) or ""),
            wounds_raw=str(profile.get("W", datasheet.datasheets_models[0].get("W", "")) or ""),
            leadership_raw=str(profile.get("Ld", datasheet.datasheets_models[0].get("Ld", "")) or ""),
            objective_control_raw=str(profile.get("OC", datasheet.datasheets_models[0].get("OC", "")) or ""),
            inv_save_raw=str(profile.get("inv_sv", datasheet.datasheets_models[0].get("inv_sv", "")) or ""),
            keywords=list(getattr(datasheet, 'keywords', []) or []),
            faction_keywords=list(getattr(datasheet, 'faction_keywords', []) or []),
        )
        resolved_geometry = self._apply_resolved_model_geometry(model, datasheet, model_name)
        geometry_source = str(getattr(resolved_geometry, "geometry_source", "") or "")
        if fallback_warning_desc and not geometry_source.startswith("geometry_override:"):
            self._warn_unknown_base_size(model_name, fallback_warning_desc)
        return model

    def _initialize_horrors_state(self) -> None:
        """Initialize Pink/Blue Horrors tracking (origin/state/model tags)."""
        self._horrors_origin = None
        self._horrors_state = None
        self._horrors_origin_name = None
        self._horrors_blue_datasheet_id = None
        self._horrors_blue_datasheet_name = None
        self._pending_horrors_split = []
        ds = getattr(self, "_datasheet", None)
        ds_name = str(getattr(ds, "name", "") or "")
        if not ds_name:
            return
        low = ds_name.lower()
        if "pink horrors" in low:
            self._horrors_origin = "pink"
            self._horrors_state = "pink"
            self._horrors_origin_name = ds_name
            self._horrors_blue_datasheet_name = "Blue Horrors"
        elif "blue horrors" in low:
            self._horrors_origin = "blue"
            self._horrors_state = "blue"
            self._horrors_origin_name = ds_name
        else:
            return

        for m in list(getattr(self, "models", []) or []):
            kind = self._horrors_model_kind_from_name(getattr(m, "name", "") or "")
            if kind:
                try:
                    setattr(m, "_horrors_kind", kind)
                except Exception:
                    pass

    def _is_horrors_unit(self) -> bool:
        return bool(getattr(self, "_horrors_origin", None) in ("pink", "blue"))

    def _horrors_model_kind_from_name(self, name: str) -> Optional[str]:
        n = str(name or "").lower()
        if "pink horror" in n:
            return "pink"
        if "brimstone" in n:
            return "brimstone"
        if "blue horror" in n:
            return "blue"
        return None

    def _horrors_model_kind(self, model: Model) -> Optional[str]:
        if model is None:
            return None
        kind = getattr(model, "_horrors_kind", None)
        if kind:
            return kind
        kind = self._horrors_model_kind_from_name(getattr(model, "name", "") or "")
        if kind:
            try:
                setattr(model, "_horrors_kind", kind)
            except Exception:
                pass
        return kind

    def _horrors_has_pink_models(self) -> bool:
        if not self._is_horrors_unit():
            return False
        for m in list(getattr(self, "models", []) or []):
            try:
                if not getattr(m, "is_alive", True):
                    continue
            except Exception:
                continue
            if self._horrors_model_kind(m) == "pink":
                return True
        return False

    def _horrors_has_blue_models(self) -> bool:
        if not self._is_horrors_unit():
            return False
        for m in list(getattr(self, "models", []) or []):
            try:
                if not getattr(m, "is_alive", True):
                    continue
            except Exception:
                continue
            if getattr(m, "_pending_placement", False):
                continue
            if self._horrors_model_kind(m) == "blue":
                return True
        return False

    def _horrors_blue_abilities_active(self) -> bool:
        if not self._is_horrors_unit():
            return False
        if getattr(self, "_horrors_origin", None) == "pink":
            return not self._horrors_has_pink_models()
        return True

    def _lookup_blue_horrors_datasheet(self):
        if not self._is_horrors_unit():
            return None
        try:
            from ...waha_helper import WahaHelper
        except Exception:
            return None
        try:
            faction_id = getattr(self._datasheet, "faction_id", None)
        except Exception:
            faction_id = None
        waha = WahaHelper()
        ds = waha.get_full_datasheet_info_by_name("Blue Horrors", faction_id=faction_id)
        if ds is None:
            return None
        try:
            self._horrors_blue_datasheet_id = getattr(ds, "id", None)
        except Exception:
            pass
        try:
            self._horrors_blue_datasheet_name = getattr(ds, "name", None)
        except Exception:
            pass
        return ds

    def _apply_datasheet_override(self, datasheet) -> None:
        if datasheet is None:
            return
        self._datasheet = datasheet
        try:
            base_name = str(getattr(datasheet, "name", "") or "")
        except Exception:
            base_name = str(getattr(self, "name", "") or "")
        if base_name and getattr(self, "_horrors_origin", None) == "pink":
            origin_label = str(getattr(self, "_horrors_origin_name", "Pink Horrors") or "Pink Horrors")
            self.name = f"{base_name} (from {origin_label})"
        else:
            self.name = base_name or self.name
        try:
            self.faction = datasheet.faction_data["name"]
        except Exception:
            pass
        self.keywords = list(getattr(datasheet, 'keywords', []) or [])
        self.faction_keywords = list(getattr(datasheet, 'faction_keywords', []) or [])
        try:
            self.unit_composition = self._parse_unit_composition(datasheet.datasheets_unit_composition)
        except Exception:
            pass
        try:
            self.models_cost = self._parse_models_cost(datasheet.datasheets_models_cost)
        except Exception:
            pass
        self.possible_wargear = self._parse_wargear(datasheet)
        self.wargear_options = []
        try:
            self._parse_wargear_options(datasheet)
        except Exception:
            pass
        self.possible_abilities = self._parse_abilities(datasheet)
        self.can_be_attached_to = getattr(datasheet, 'attached_to', [])
        self.can_be_attached_to_names = getattr(datasheet, 'attached_to_names', [])
        try:
            if hasattr(datasheet, 'damaged_w') and datasheet.damaged_w:
                self.damaged_profile = self._parse_range(datasheet.damaged_w)
                self.damaged_profile_desc = getattr(datasheet, 'damaged_description', None)
            else:
                self.damaged_profile = None
                self.damaged_profile_desc = None
        except Exception:
            pass
        try:
            self.transport_rules_text = str(getattr(datasheet, "transport", "") or "")
            self.transport_capacity = self._parse_transport_capacity(datasheet)
            self.transport_required_keywords, self.transport_excluded_keywords = self._parse_transport_restrictions(datasheet)
        except Exception:
            pass
        try:
            if hasattr(self, "_invalidate_ability_cache"):
                self._invalidate_ability_cache()
        except Exception:
            pass
        try:
            self._refresh_command_phase_flags()
        except Exception:
            pass
        try:
            self._refresh_fall_back_desperate_escape_flags()
        except Exception:
            pass
        try:
            self._refresh_targeted_stratagem_cp_discount_flags()
        except Exception:
            pass
        try:
            self._refresh_return_on_death_flags()
        except Exception:
            pass
        try:
            self._refresh_charge_end_mortal_wounds_flags()
        except Exception:
            pass
        try:
            self._refresh_fight_within_3_flags()
        except Exception:
            pass
        try:
            self._refresh_bearer_unit_common_modifiers()
        except Exception:
            pass
        try:
            self._refresh_advance_no_roll_flags()
        except Exception:
            pass
        try:
            self._refresh_ignore_vertical_distance_move_types()
        except Exception:
            pass
        try:
            self._refresh_bearer_keyword_flags()
        except Exception:
            pass
        try:
            self._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass

    def _maybe_swap_horrors_datasheet(self) -> None:
        if not self._is_horrors_unit():
            return
        if getattr(self, "_horrors_origin", None) != "pink":
            return
        if getattr(self, "_horrors_state", None) == "blue":
            return
        if self._horrors_has_pink_models():
            return
        ds = self._lookup_blue_horrors_datasheet()
        if ds is None:
            return
        self._horrors_state = "blue"
        self._apply_datasheet_override(ds)

    def _spawn_horrors_models(self, kind: str, count: int, *, from_split: bool = True) -> list[Model]:
        if int(count or 0) <= 0:
            return []
        if kind not in ("blue", "brimstone", "pink"):
            return []
        name_map = {"pink": "Pink Horror", "blue": "Blue Horror", "brimstone": "Brimstone Horror"}
        model_name = name_map[kind]
        ds = getattr(self, "_datasheet", None)
        if ds is None:
            return []
        fallback_base_size = self._select_fallback_base_size(ds)
        profile = self._pick_profile_for_model(ds, model_name)
        models: list[Model] = []
        for _ in range(int(count or 0)):
            model = self._build_model_from_profile(
                ds,
                model_name,
                profile,
                fallback_base_size=fallback_base_size,
            )
            model.set_parent_unit(self)
            try:
                setattr(model, "_horrors_kind", kind)
            except Exception:
                pass
            self._assign_default_wargear_to_model(model, from_split=from_split)
            models.append(model)
        return models

    def _pending_placement_models(self) -> list[Model]:
        return [m for m in (getattr(self, "models", []) or []) if getattr(m, "_pending_placement", False)]

    def _request_pending_placement_decision(self, *, game_map: Optional['Map'] = None) -> None:
        pending = self._pending_placement_models()
        if not pending:
            return
        game = None
        try:
            army = self.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        except Exception:
            game = None
        if game is None:
            return
        try:
            from ...engine.decision_kinds import DECISION_MOVE_UNIT
            from ...engine.decisions import DecisionOption, DecisionRequest
            from ...utility.entity_ids import get_entity_id
        except Exception:
            return

        # Avoid duplicate placement requests for this unit.
        try:
            queue = getattr(game, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if getattr(req, "decision_type", None) != DECISION_MOVE_UNIT:
                        continue
                    ctx = getattr(req, "context", {}) or {}
                    if str(ctx.get("unit_id", "")) == str(get_entity_id(self)) and ctx.get("placement_kind"):
                        return
        except Exception:
            pass

        unit_id = get_entity_id(self)
        allowed_ids = [get_entity_id(m) for m in pending]
        sources = {str(getattr(m, "_pending_placement_source", "") or "") for m in pending if m is not None}
        placement_kind = sources.pop() if len(sources) == 1 else "placement"
        allow_skip = False

        options = [
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": unit_id, "movement_type": "deploy", "action": "confirm"},
            )
        ]
        if allow_skip:
            options.append(
                DecisionOption.create(
                    "Skip",
                    payload={"unit_id": unit_id, "movement_type": "deploy", "action": "skip", "skip": True},
                )
            )
        player_id = None
        try:
            player_id = self.get_parent_army().player.id
        except Exception:
            player_id = None
        title = f"Place models for {getattr(self, 'name', 'Unit')}"
        req = DecisionRequest.create(
            DECISION_MOVE_UNIT,
            title,
            player_id=player_id,
            options=options,
            context={
                "unit_id": unit_id,
                "movement_type": "deploy",
                "placement_kind": placement_kind,
                "allowed_model_ids": list(allowed_ids),
                "allow_skip": bool(allow_skip),
            },
        )
        try:
            if hasattr(game, "request_decision"):
                game.request_decision(req)
        except Exception:
            return

    def _mark_models_pending_placement(self, models: list[Model], *, source: Optional[str] = None) -> None:
        if not models:
            return
        tag = str(source or "placement")
        for model in list(models or []):
            if model is None:
                continue
            model._pending_placement = True
            model._pending_placement_source = tag

    def _horrors_brimstone_models(self) -> list[Model]:
        if not self._is_horrors_unit():
            return []
        models = []
        for m in list(getattr(self, "models", []) or []):
            if not getattr(m, "is_alive", True):
                continue
            if getattr(m, "_pending_placement", False):
                continue
            if self._horrors_model_kind(m) == "brimstone":
                models.append(m)
        return models

    def _horrors_can_return_model(self, model: Optional[Model]) -> bool:
        if model is None:
            return False
        if not self._is_horrors_unit():
            return True
        if getattr(self, "_horrors_origin", None) != "pink":
            return True
        if getattr(self, "_horrors_state", None) != "blue":
            return True
        return self._horrors_model_kind(model) != "pink"

    def _maybe_queue_horrors_split(self, model: Optional[Model]) -> None:
        if model is None or not self._is_horrors_unit():
            return
        kind = self._horrors_model_kind(model)
        if kind not in ("pink", "blue"):
            return
        damage_source = str(getattr(model, "_last_damage_source_kind", "") or "").lower()
        if damage_source not in ("attack", "hazardous"):
            return
        if damage_source == "attack":
            root = self._attack_resolution_root()
            depth = int(getattr(root, "_attack_resolution_depth", 0) or 0)
            if depth <= 0:
                return
        root = self._attack_resolution_root()
        queue = getattr(root, "_pending_horrors_split", None)
        if not isinstance(queue, list):
            queue = []
            root._pending_horrors_split = queue
        queue.append({"kind": kind})

    def _resolve_pending_horrors_split(self, *, game_map: Optional['Map'] = None) -> None:
        root = self._attack_resolution_root()
        queue = getattr(root, "_pending_horrors_split", None)
        if not isinstance(queue, list) or not queue:
            return
        root._pending_horrors_split = []
        if not root.is_alive():
            return

        spawned: list[Model] = []
        for entry in list(queue or []):
            kind = str(entry.get("kind", "") or "")
            roll = int(get_roll("D6"))
            if roll < 4:
                continue
            if kind == "pink":
                spawned.extend(root._spawn_horrors_models("blue", 2, from_split=True))
            elif kind == "blue":
                spawned.extend(root._spawn_horrors_models("brimstone", 1, from_split=True))
        if not spawned:
            return
        root._mark_models_pending_placement(spawned, source="split")
        for model in spawned:
            root.add_model(model)
        root._request_pending_placement_decision(game_map=game_map)

    def can_use_exploding_horrors(self) -> bool:
        if not self._is_horrors_unit():
            return False
        if not self._horrors_blue_abilities_active():
            return False
        return bool(self._horrors_brimstone_models())

    def resolve_exploding_horrors(
        self,
        target_unit: Optional['Unit'],
        selected_models: Optional[list[Model]] = None,
        *,
        game_map: Optional['Map'] = None,
    ) -> int:
        if target_unit is None or not self.can_use_exploding_horrors():
            return 0
        if game_map is not None:
            within_fn = getattr(game_map, "is_within_engagement_range", None)
            if callable(within_fn):
                if not within_fn(self, target_unit):
                    return 0
        brimstones = set(self._horrors_brimstone_models())
        if selected_models:
            chosen = [m for m in list(selected_models or []) if m in brimstones]
        else:
            chosen = list(brimstones)
        if not chosen:
            return 0

        successes = 0
        for model in list(chosen or []):
            roll = int(get_roll("D6"))
            if roll < 4:
                continue
            successes += 1
            model._last_damage_source_kind = "non_attack"
            model._last_damage_weapon_profile = None
            model.wounds = 0
            if hasattr(model, "die"):
                model.die(game_map=game_map)
        if successes > 0:
            self._apply_mortal_wounds_to_unit(target_unit, successes, game_map=game_map)
        return successes

    def _create_models(self, datasheet, quantity=None):
        models = []
        total_models = 0

        def _select_unit_composition_option(requested_qty: Optional[int]):
            options = getattr(self, "unit_composition_options", None)
            if not isinstance(options, list) or not options:
                return getattr(self, "unit_composition", {})

            def _totals(opt: dict[str, tuple[int, int]]) -> tuple[int, int]:
                min_total = sum(min_size for min_size, _ in opt.values())
                max_total = sum(max_size for _, max_size in opt.values())
                return min_total, max_total

            if requested_qty is None:
                return min(options, key=lambda opt: _totals(opt)[0])

            for opt in options:
                min_total, max_total = _totals(opt)
                if min_total <= requested_qty <= max_total:
                    return opt

            return min(options, key=lambda opt: _totals(opt)[0])

        chosen = _select_unit_composition_option(quantity)
        if isinstance(chosen, dict) and chosen:
            self.unit_composition = chosen

        fallback_base_size = self._select_fallback_base_size(datasheet)

        if quantity is None:
            # If no quantity is specified, use the minimum number of models
            quantity = sum(min_size for _, (min_size, _) in self.unit_composition.items())

        # Enforce an overall maximum if provided in datasheet composition metadata.
        try:
            max_cap = getattr(self, "unit_models_maximum", None)
            if isinstance(max_cap, int) and max_cap > 0 and quantity > max_cap:
                logger.info(f" {self.name} requested size {quantity} exceeds maximum {max_cap}; clamping to {max_cap}.")
                quantity = max_cap
        except Exception:
            pass

        for composition_model_name, (min_size, max_size) in self.unit_composition.items():
            if isinstance(max_size, tuple):
                max_size = max_size[1]  # Use the second value if it's a tuple
            model_count = min(max_size, max(min_size, quantity - total_models))
            model_name = self._resolve_composition_model_name(
                datasheet,
                composition_model_name,
                model_count=model_count,
            )

            profile = self._pick_profile_for_model(datasheet, model_name)
            # Default to first profile if anything is missing
            if not profile:
                profile = datasheet.datasheets_models[0]
            for _ in range(model_count):
                model = self._build_model_from_profile(
                    datasheet,
                    model_name,
                    profile,
                    fallback_base_size=fallback_base_size,
                )
                model.set_parent_unit(self)
                models.append(model)
                total_models += 1
            if total_models >= quantity:
                break
        return models

    def _parse_loadout(
        self,
        loadout: str,
        model_name: str = "",
        return_optional: bool = False,
        *,
        from_split: bool = False,
    ) -> List[Wargear] | Tuple[List[Wargear], List[str]]:
        def _norm_item(s: str) -> str:
            s = (s or "").replace("\u2019", "'").lower().strip()
            s = re.sub(r"<[^>]+>", " ", s)
            # remove punctuation but keep hyphens (for items like "grav-gun")
            s = re.sub(r"[^\w\s\-']", " ", s)
            s = s.replace("'", "")  # ignore apostrophes for matching
            s = re.sub(r"\s+", " ", s).strip()
            return s

        entries = (loadout or "").replace('\u2019', "'").lower().split('.')
        model_name_norm = _norm_item(model_name)

        def _parse_loadout_quantity(item_name: str) -> Tuple[int, str]:
            token = str(item_name or "").strip()
            if not token:
                return 1, ""
            if quantity_match := re.match(r"^(?P<count>\d+)\s+(?P<item>.+)$", token):
                count = int(quantity_match.group("count"))
                parsed_item = str(quantity_match.group("item") or "").strip()
                if count != 1 and parsed_item.endswith("s"):
                    parsed_item = parsed_item[:-1].strip()
                return count, parsed_item
            return 1, token

        def _split_loadout_items(raw_items: str) -> List[str]:
            return [item.strip() for item in re.split(r"[;,]", str(raw_items or "")) if str(item or "").strip()]

        starting_wargear = []
        optional_wargear: List[str] = []
        wargear_lookup = {
            _norm_item(getattr(wg, "name", "")): wg
            for wg in (getattr(self, "possible_wargear", []) or [])
            if wg
        }
        wargear_ability_names: dict[str, str] = {}
        for ab in list(getattr(self, "possible_abilities", []) or []):
            try:
                atype = str(getattr(ab, "type", "") or "").lower()
                if "wargear" not in atype:
                    continue
                name = getattr(ab, "name", "") or ""
                if name:
                    wargear_ability_names[_norm_item(name)] = name
            except Exception:
                continue

        def _record_item(item_name: str, quantity: int) -> None:
            norm = _norm_item(item_name)
            if not norm:
                return
            wg = wargear_lookup.get(norm)
            if wg is not None:
                for _ in range(quantity):
                    starting_wargear.append(wg)
                return
            ability_name = wargear_ability_names.get(norm)
            if ability_name:
                for _ in range(quantity):
                    optional_wargear.append(ability_name)
        for entry in entries:
            if not entry:
                continue
            entry = entry.strip()

            if match := re.match(r"^this model is equipped with: (.*)$", entry):
                for item_name in _split_loadout_items(match.group(1)):
                    quantity, item_name = _parse_loadout_quantity(item_name)
                    _record_item(item_name, quantity)
            elif match := re.match(r"^every model is equipped with: (.*)$", entry):
                for item_name in _split_loadout_items(match.group(1)):
                    quantity, item_name = _parse_loadout_quantity(item_name)
                    _record_item(item_name, quantity)
            elif match := re.match(r"^(?:the|every|a|an)?\s*(\D+)\s+added to this unit using the split ability is equipped with: (.*)$", entry):
                if not from_split:
                    continue
                actors = [match.group(1)]
                if " and " in actors[0]:
                    actors = actors[0].split(" and ")
                for actor in actors:
                    if model_name_norm and model_name_norm == _norm_item(actor.strip()):
                        for item_name in _split_loadout_items(match.group(2)):
                            quantity, item_name = _parse_loadout_quantity(item_name)
                            _record_item(item_name, quantity)
                    else:
                        continue
            elif match := re.match(r"^(?:the|every) (.*) model is equipped with: (.*)$", entry):
                if model_name_norm and model_name_norm == _norm_item(match.group(1).strip()):
                    for item_name in _split_loadout_items(match.group(2)):
                        quantity, item_name = _parse_loadout_quantity(item_name)
                        _record_item(item_name, quantity)
                else:
                    continue
            elif match := re.match(r"^(?:the|every|a|an) (\D+) is equipped with: (.*)$", entry):
                actors = [match.group(1)]
                if " and " in actors[0]:
                    actors = actors[0].split(" and ")
                for actor in actors:
                    if model_name_norm and model_name_norm == _norm_item(actor.strip()):
                        for item_name in _split_loadout_items(match.group(2)):
                            quantity, item_name = _parse_loadout_quantity(item_name)
                            _record_item(item_name, quantity)
                    else:
                        continue
            elif match := re.match(r"^(\D+) is equipped with: (.*)$", entry):
                actors = [match.group(1)]
                if " and " in actors[0]:
                    actors = actors[0].split(" and ")
                for actor in actors:
                    if model_name_norm and model_name_norm == _norm_item(actor.strip()):
                        for item_name in _split_loadout_items(match.group(2)):
                            quantity, item_name = _parse_loadout_quantity(item_name)
                            _record_item(item_name, quantity)
                    else:
                        continue
            elif match := re.match(r"^this (?:model|unit) is equipped with: nothing$", entry):
                continue
            else:
                logger.info(f"UNKNOWN LOADOUT: {entry}")
        if return_optional:
            return starting_wargear, optional_wargear
        return starting_wargear

    def _parse_wargear(self, datasheet):
        possible_wargear = []
        if hasattr(datasheet, 'datasheets_wargear'):
            for wargear_data in datasheet.datasheets_wargear:
                raw_name = str(wargear_data.get("name", "") or "").strip()
                if not raw_name:
                    continue
                #print(f"Parsing wargear {raw_name}")
                if ' \u2013 ' in raw_name:
                    name, profile = raw_name.split(' \u2013 ')
                    if name not in [wargear.name for wargear in possible_wargear]:
                        #print(f"Adding wargear {name} with profile {profile}")
                        possible_wargear.append(Wargear(wargear_data))
                    else:
                        for wargear in possible_wargear:
                            if wargear.name == name:
                                #print(f"Adding profile {profile} to wargear {name}")
                                wargear.add_profile(profile, wargear_data)
                                break
                else:
                    #print(f"Adding wargear {raw_name}")
                    possible_wargear.append(Wargear(wargear_data))
        return possible_wargear

    def _parse_wargear_options(self, datasheet) -> None:
        wargear_options = []
        if hasattr(datasheet, 'datasheets_options'):
            for wargear_option_data in datasheet.datasheets_options:
                wargear_options.append(wargear_option_data["description"])
        self.parse_wargear_options(wargear_options)

    def _parse_abilities(self, datasheet) -> List[Ability]:
        abilities = []
        if hasattr(datasheet, 'datasheets_abilities'):
            for ability in datasheet.datasheets_abilities:
                if 'ability_data' in ability.keys():
                    abilities.append(Ability(ability["ability_data"]["name"],
                                            ability["ability_data"]["faction_id"],
                                            ability["ability_data"]["description"],
                                            ability["type"],
                                            ability["parameter"],
                                            ability["ability_data"]["legend"]))
                else:
                    abilities.append(Ability(ability["name"],
                                            "",
                                            ability["description"],
                                            ability["type"],
                                            ability["parameter"]))
        return abilities

    def parse_wargear_option(self, option: str) -> None:
        return parse_option_string(option, unit_ref=self)

    def parse_wargear_options(self, options: List[str]):
        if len(options) == 1 and options[0].lower() == "none":
            self.wargear_options = {}
            return
        import re

        def _norm(s: str) -> str:
            s = (s or "").replace("\u2019", "'").lower().strip()
            s = re.sub(r"<[^>]+>", " ", s)
            s = re.sub(r"[^\w\s\-']", " ", s)
            s = s.replace("'", "")
            s = re.sub(r"\s+", " ", s).strip()
            return s

        def _parse_count_token(token: str) -> int | None:
            raw = (token or "").strip().lower()
            if not raw:
                return None
            if raw.isdigit():
                return int(raw)
            words = {
                "one": 1,
                "two": 2,
                "three": 3,
                "four": 4,
                "five": 5,
                "six": 6,
                "seven": 7,
                "eight": 8,
                "nine": 9,
                "ten": 10,
            }
            return words.get(raw)

        # Parse and store constraint-only lines (they are not selectable options, but affect validity).
        # These are the "Additional / Not implemented" lines like pistol pairing and max ranged weapon limits.
        self._wargear_constraints = getattr(self, "_wargear_constraints", {}) or {}
        self._wargear_constraints.setdefault("max_ranged_weapons", None)
        self._wargear_constraints.setdefault("two_ranged_requires_pistol", False)
        self._wargear_constraints.setdefault("two_ranged_requires_cyclone_pair", False)
        self._wargear_constraints.setdefault("mutex_sets", [])  # list[set[str]]
        self._wargear_constraints.setdefault("max_counts", {})  # dict[str,int]
        self._wargear_constraints.setdefault("model_option_mutex", False)
        self._wargear_constraints.setdefault("forbidden_if_any_option", set())

        cleaned: List[str] = []
        for raw in options:
            text = (raw or "").strip()
            t = _norm(text)
            # Max ranged weapons
            m = re.match(r"each model cannot be equipped with more than (\d+) ranged weapons", t)
            if m:
                self._wargear_constraints["max_ranged_weapons"] = int(m.group(1))
                continue
            # Pistol pairing when 2 ranged
            if "can only be equipped with two ranged weapons if one of them is a pistol" in t:
                self._wargear_constraints["two_ranged_requires_pistol"] = True
                # Also: only have one pistol (already implied by that text)
                continue
            # Cyclone pairing (Wolf Guard Pack Leader in Terminator Armour)
            if "can only be equipped with two ranged weapons if one of them is a cyclone missile launcher" in t:
                self._wargear_constraints["two_ranged_requires_cyclone_pair"] = True
                continue
            # Mutual exclusion: "cannot be equipped with both X and Y"
            m = re.match(r"(?:no model|this model) can(?:not)? be equipped with both (.+?) and (.+?)(?: at the same time)?$", t)
            if m:
                a = _norm(m.group(1))
                b = _norm(m.group(2))
                if a and b:
                    self._wargear_constraints["mutex_sets"].append({a, b})
                continue
            # Max counts: "cannot be equipped with more than 1 X"
            # Hive Tyrant line has multiple clauses; parse all occurrences.
            maxes = list(
                re.finditer(
                    r"more than "
                    r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten) "
                    r"([\w\s\-']+?)(?=(?:\s+or\s+more\s+than|\s+and\s+more\s+than|$))",
                    t,
                )
            )
            if maxes:
                for mm in maxes:
                    n = _parse_count_token(mm.group(1))
                    if n is None:
                        continue
                    nm = _norm(mm.group(2))
                    if nm:
                        self._wargear_constraints["max_counts"][nm] = min(self._wargear_constraints["max_counts"].get(nm, n), n)
                continue
            # Model option mutex / forbidden weapons for that group
            if "a model can only take one of these options" in t:
                self._wargear_constraints["model_option_mutex"] = True
                # "cannot be equipped with a X or an Y"
                forbid = re.findall(r"cannot be equipped with an? ([\w\s\-']+)", t)
                for f in forbid:
                    ff = _norm(f)
                    if ff:
                        self._wargear_constraints["forbidden_if_any_option"].add(ff)
                continue
            if "cannot be equipped with more than one of these wargear options" in t:
                self._wargear_constraints["model_option_mutex"] = True
                continue

            cleaned.append(text)

        wargear_options = parse_alternate_3(cleaned, self)
        self.wargear_options = wargear_options

    def apply_wargear_option(self, wargear_option: WargearOption):
        """
        Apply a wargear option to the unit.

        IMPORTANT:
        - A wargear option is a *rule* granting allowed additions/replacements. This method applies one chosen
          option outcome to models (used by army-list parsing and any future UI selection).
        - `wargear_option.wargear_to` is a list of possible "choices", each being a list of (qty, item_name) tuples.
        """
        import re
        from warhammer40k_ai.units.wargear import WargearOptionType

        def _norm(s: str) -> str:
            s = (s or "").replace("\u2019", "'").lower().strip()
            s = re.sub(r"<[^>]+>", " ", s)
            s = re.sub(r"[^\w\s\-']", " ", s)
            s = s.replace("'", "")
            s = re.sub(r"\s+", " ", s).strip()
            return s

        def _iter_choice_item_names() -> list[str]:
            out: list[str] = []
            for choice in (wargear_option.wargear_to or []):
                for qty, nm in (choice or []):
                    if nm:
                        out.append(_norm(str(nm)))
            return out

        def _actor_matches_model(actor: str, model_name: str) -> bool:
            a = _norm(actor)
            m = _norm(model_name)
            if not a or not m:
                return False
            if a in ("model", "this model", "unit"):
                return True
            return a == m or a in m or m in a

        def _effective_model_limit_max() -> int:
            """Apply common scaling conditionals (e.g. 'For every 5 models in this unit,...')."""
            max_models = int(getattr(wargear_option.model_quantity, "max", 1) or 1)
            # Scale by "for every N models in this unit"
            for cond in list(getattr(wargear_option, "conditionals", []) or []):
                m = re.search(r"for every\s+(\d+)\s+[\w\s']+\s+in th[ei]s unit", (cond or "").lower())
                if m:
                    try:
                        n = int(m.group(1))
                        if n > 0:
                            max_models = max_models * max(1, (len(self.models) // n))
                    except Exception:
                        pass
            return max_models

        def _conditions_met(model) -> bool:
            # Best-effort: supports common constraint phrases produced by the parser.
            for cond in list(getattr(wargear_option, "conditionals", []) or []):
                cl = (cond or "").lower().strip()
                if cl.startswith("not equipped with "):
                    excluded = _norm(cl.replace("not equipped with ", ""))
                    # Check both currently equipped wargear and already-picked option names
                    try:
                        for wg in getattr(model, "wargear", []) or []:
                            if _norm(getattr(wg, "name", "")) == excluded:
                                return False
                    except Exception:
                        pass
                    try:
                        for ow in getattr(model, "optional_wargear", []) or []:
                            if _norm(ow) == excluded:
                                return False
                    except Exception:
                        pass
                elif cl.startswith("equipped with "):
                    required = _norm(cl.replace("equipped with ", ""))
                    has_req = False
                    for wg in list(getattr(model, "wargear", []) or []):
                        if wg and _norm(getattr(wg, "name", "")) == required:
                            has_req = True
                            break
                    if not has_req:
                        return False
                elif cl.startswith("contains ") and " models" in cl:
                    # "contains 10 models" (unit-level conditional)
                    m = re.match(r"contains\s+(\d+)\s+models", cl)
                    if m:
                        if len(self.models) != int(m.group(1)):
                            return False
                elif cl.startswith("cannot replace "):
                    # This is handled by replacement lock checks, not eligibility.
                    continue
            return True

        def _get_replacement_locks(model) -> set[str]:
            locks = getattr(model, "_wargear_replacement_locks", None)
            if locks is None:
                locks = set()
                setattr(model, "_wargear_replacement_locks", locks)
            return locks

        def _apply_post_locks(model) -> None:
            # Conditionals like "cannot replace lasgun" apply to the model that receives this option.
            locks = _get_replacement_locks(model)
            for cond in list(getattr(wargear_option, "conditionals", []) or []):
                cl = (cond or "").lower().strip()
                if cl.startswith("cannot replace "):
                    locks.add(_norm(cl.replace("cannot replace ", "")))

        def _per_model_mutex_blocked(model) -> bool:
            # If the same model can't take more than one of these options, block if it already has any
            # item from this option's choices.
            conds = " | ".join(list(getattr(wargear_option, "conditionals", []) or [])).lower()
            if ("same model cannot be equipped with more than one of these wargear options" not in conds
                and "you cannot select both of these options for the same model" not in conds):
                return False
            option_items = {_norm(nm) for choice in (getattr(wargear_option, "wargear_to", []) or []) for qty, nm in (choice or []) if nm}
            for wg in list(getattr(model, "wargear", []) or []):
                if wg and _norm(getattr(wg, "name", "")) in option_items:
                    return True
            return False

        def _no_duplicates_in_choices_blocked(model) -> bool:
            conds = " | ".join(list(getattr(wargear_option, "conditionals", []) or [])).lower()
            if "no duplicates in choices" not in conds:
                return False
            allowed = {_norm(nm) for choice in (getattr(wargear_option, "wargear_to", []) or []) for qty, nm in (choice or []) if nm}
            counts = {}
            for wg in list(getattr(model, "wargear", []) or []):
                if wg:
                    n = _norm(getattr(wg, "name", ""))
                    if n in allowed:
                        counts[n] = counts.get(n, 0) + 1
                        if counts[n] > 1:
                            return True
            return False

        def _lock_selected_items(model, selected_names_norm: set[str]) -> None:
            conds = " | ".join(list(getattr(wargear_option, "conditionals", []) or [])).lower()
            if "lock_selected_items" not in conds:
                return
            locks = _get_replacement_locks(model)
            for n in selected_names_norm:
                locks.add(n)

        def _max_per_models_limit() -> tuple[int, int] | None:
            # Parse "to a maximum of X per Y models in this unit"
            for cond in list(getattr(wargear_option, "conditionals", []) or []):
                cl = (cond or "").lower().strip().replace("\u2019", "'")
                m = re.match(r"to a maximum of (\d+) per (\d+) models in this unit", cl)
                if m:
                    return int(m.group(1)), int(m.group(2))
            return None

        def _max_one_per_model() -> bool:
            return any((c or "").lower().strip() == "maximum 1 per model" for c in (getattr(wargear_option, "conditionals", []) or []))

        def _unit_dynamic_cap_for_item(item_norm: str) -> int | None:
            # Handle: "you cannot select the same weapon more than once per unit unless it contains 20 models, ..."
            conds = " | ".join(list(getattr(wargear_option, "conditionals", []) or [])).lower()
            m = re.search(r"you cannot select the same (?:weapon|option) more than once per unit unless it contains (\d+) models, in which case you cannot select the same (?:weapon|option) more than twice per unit", conds)
            if m:
                n = int(m.group(1))
                return 2 if len(self.models) >= n else 1
            return None

        def _unit_unique_cap(item_norm: str) -> int | None:
            conds = " | ".join(list(getattr(wargear_option, "conditionals", []) or [])).lower()
            if "you cannot select the same weapon from this list more than once per unit" in conds:
                return 1
            if "you cannot select the same weapon from this list more than twice per unit" in conds:
                return 2
            return None

        def _unit_count_item(item_norm: str) -> int:
            n = 0
            for m in (self.models or []):
                for wg in list(getattr(m, "wargear", []) or []):
                    if wg and _norm(getattr(wg, "name", "")) == item_norm:
                        n += 1
            return n

        def _find_wargear(item_name: str):
            wanted = _norm(item_name)
            for wg in (getattr(self, "possible_wargear", []) or []):
                if wg and _norm(getattr(wg, "name", "")) == wanted:
                    return wg
            return None

        def _is_ranged_wargear(wg) -> bool:
            try:
                for prof in getattr(wg, "profiles", {}).values():
                    if prof and hasattr(prof, "is_ranged") and prof.is_ranged():
                        return True
            except Exception:
                pass
            return False

        def _is_pistol_wargear(wg) -> bool:
            try:
                for prof in getattr(wg, "profiles", {}).values():
                    if prof and hasattr(prof, "is_pistol") and prof.is_pistol():
                        return True
            except Exception:
                pass
            return False

        def _validate_constraints_for_wargear(wargear) -> bool:
            c = getattr(self, "_wargear_constraints", {}) or {}
            wargear = list(wargear or [])

            # Max counts for named items
            max_counts = c.get("max_counts", {}) or {}
            if max_counts:
                counts = {}
                for wg in wargear:
                    if wg:
                        nm = _norm(getattr(wg, "name", ""))
                        counts[nm] = counts.get(nm, 0) + 1
                for nm, mx in max_counts.items():
                    if counts.get(nm, 0) > int(mx):
                        return False

            # Mutual exclusions
            for s in c.get("mutex_sets", []) or []:
                present = 0
                for wg in wargear:
                    if wg and _norm(getattr(wg, "name", "")) in s:
                        present += 1
                        if present > 1:
                            return False

            # Max ranged weapons
            max_r = c.get("max_ranged_weapons")
            if max_r is not None:
                ranged = [wg for wg in wargear if wg and _is_ranged_wargear(wg)]
                if len(ranged) > int(max_r):
                    return False

            # Two ranged requires pistol
            if c.get("two_ranged_requires_pistol"):
                ranged = [wg for wg in wargear if wg and _is_ranged_wargear(wg)]
                if len(ranged) == 2:
                    pistols = [wg for wg in ranged if _is_pistol_wargear(wg)]
                    if len(pistols) != 1:
                        return False
                if len(ranged) > 2:
                    return False

            # Cyclone pairing constraint
            if c.get("two_ranged_requires_cyclone_pair"):
                ranged = [wg for wg in wargear if wg and _is_ranged_wargear(wg)]
                if len(ranged) == 2:
                    names = {_norm(getattr(wg, "name", "")) for wg in ranged if wg}
                    if "cyclone missile launcher" not in names:
                        return False
                    other = (names - {"cyclone missile launcher"})
                    if not other:
                        return False
                    # Allowed partners: storm bolter OR combi-weapon
                    if not (("storm bolter" in other) or ("combi-weapon" in other)):
                        return False
                if len(ranged) > 2:
                    return False

            return True

        def _validate_constraints(model) -> bool:
            return _validate_constraints_for_wargear(getattr(model, "wargear", []) or [])

        def _mark_model_took_any_option(model) -> None:
            try:
                setattr(model, "_took_any_wargear_option", True)
            except Exception:
                pass

        def _model_has_bundle(model, bundle) -> bool:
            """
            bundle: list[(qty, item_name)] describing the items that must exist on the model.
            """
            if not bundle:
                return True
            counts: dict[str, int] = {}
            for wg in list(getattr(model, "wargear", []) or []):
                if not wg:
                    continue
                nm = _norm(getattr(wg, "name", ""))
                counts[nm] = counts.get(nm, 0) + 1
            for qty, nm in bundle:
                want = _norm(nm)
                if counts.get(want, 0) < int(qty):
                    return False
            return True

        def _pick_matching_from_bundle(model):
            """
            wargear_from can represent alternatives (A or B). Pick the first bundle that matches this model.
            Returns None if none match.
            """
            from_bundles = list(getattr(wargear_option, "wargear_from", []) or [])
            if not from_bundles:
                return []
            for bundle in from_bundles:
                if _model_has_bundle(model, bundle):
                    return bundle
            return None

        # Select models eligible for this option
        actor = getattr(wargear_option, "model_name", "") or ""
        eligible_models = [m for m in (self.models or []) if _actor_matches_model(actor, getattr(m, "name", "")) and _conditions_met(m)]
        if not eligible_models:
            return

        # "All ..." semantics: boolean toggle (everyone or no one).
        # Do NOT treat "exactly 1 model" as all-or-none; that's just a single-model pick.
        req_min = int(getattr(getattr(wargear_option, "model_quantity", None), "min", 0) or 0)
        req_max = int(getattr(getattr(wargear_option, "model_quantity", None), "max", 0) or 0)
        cond_blob = " | ".join(list(getattr(wargear_option, "conditionals", []) or [])).lower()
        all_or_none = ("all_or_none" in cond_blob) or (req_min == req_max and req_min > 1 and len(eligible_models) == req_min)

        if all_or_none:
            # Must apply to exactly the required number of models, otherwise none.
            if len(eligible_models) != req_min:
                return
            # For replacements: ensure every model can satisfy a "from" bundle.
            if getattr(wargear_option, "wargear_type", None) == WargearOptionType.REPLACEMENT:
                for m in eligible_models:
                    if _pick_matching_from_bundle(m) is None:
                        return

        # Apply model limit (max)
        max_models = _effective_model_limit_max()
        eligible_models = eligible_models[:max_models]

        # Choose the first "choice" by default (callers can filter options beforehand).
        choices = list(getattr(wargear_option, "wargear_to", []) or [])
        if not choices:
            return
        choice = choices[0]

        # Apply to models
        for model in eligible_models:
            original_wargear = list(getattr(model, "wargear", []) or [])
            option_invalid = False
            # Global option mutex / forbidden weapons
            c = getattr(self, "_wargear_constraints", {}) or {}
            if c.get("model_option_mutex") and getattr(model, "_took_any_wargear_option", False):
                continue
            forbidden = c.get("forbidden_if_any_option", set()) or set()
            if forbidden:
                if any(_norm(getattr(wg, "name", "")) in forbidden for wg in list(getattr(model, "wargear", []) or []) if wg):
                    continue

            if _per_model_mutex_blocked(model):
                continue
            if _max_one_per_model():
                # If model already has any of the option's choice items, block further selections
                allowed = {_norm(nm) for choice in (getattr(wargear_option, "wargear_to", []) or []) for qty, nm in (choice or []) if nm}
                if any(_norm(getattr(wg, "name", "")) in allowed for wg in list(getattr(model, "wargear", []) or []) if wg):
                    continue
            if _no_duplicates_in_choices_blocked(model):
                continue
            # Replacement: remove wargear_from then add choice items.
            if getattr(wargear_option, "wargear_type", None) == WargearOptionType.REPLACEMENT:
                bundle = _pick_matching_from_bundle(model)
                if bundle is None:
                    # For non-all-or-none options, just skip models that don't match the "from" clause.
                    continue
                # Respect replacement locks (e.g. "that model's lasgun cannot be replaced")
                locks = _get_replacement_locks(model)
                if any(_norm(nm) in locks for qty, nm in bundle):
                    continue
                for qty, nm in bundle:
                    tgt = _norm(nm)
                    removed = 0
                    kept = []
                    for wg in list(getattr(model, "wargear", []) or []):
                        if wg and removed < int(qty) and _norm(getattr(wg, "name", "")) == tgt:
                            removed += 1
                            continue
                        kept.append(wg)
                    model.wargear = kept

            # Add items from the selected choice
            # Support: "item_limit is equal to number of equipped X"
            # Interpreted as "you have N slots equal to count(equipped X); each selection consumes 1 slot".
            remaining_slots = None
            for cond in list(getattr(wargear_option, "conditionals", []) or []):
                cl = (cond or "").lower().strip()
                if cl.startswith("item_limit is equal to number of equipped "):
                    what = _norm(cl.replace("item_limit is equal to number of equipped ", ""))
                    if not what:
                        remaining_slots = 0
                        break
                    cap = sum(
                        1
                        for wg in list(getattr(model, "wargear", []) or [])
                        if wg and _norm(getattr(wg, "name", "")) == what
                    )
                    allowed_items = {
                        _norm(nm)
                        for ch in (getattr(wargear_option, "wargear_to", []) or [])
                        for q, nm in (ch or [])
                        if nm
                    }
                    already_taken = sum(
                        1
                        for wg in list(getattr(model, "wargear", []) or [])
                        if wg and _norm(getattr(wg, "name", "")) in allowed_items
                    )
                    remaining_slots = max(0, int(cap) - int(already_taken))
                    break
            if remaining_slots is not None and remaining_slots <= 0:
                _apply_post_locks(model)
                continue

            for qty, nm in choice:
                cap = _unit_unique_cap(_norm(nm))
                if cap is not None:
                    if _unit_count_item(_norm(nm)) >= cap:
                        continue
                dyn = _unit_dynamic_cap_for_item(_norm(nm))
                if dyn is not None and _unit_count_item(_norm(nm)) >= dyn:
                    continue
                ratio = _max_per_models_limit()
                if ratio is not None:
                    x, y = ratio
                    limit = max(0, (len(self.models) // y) * x)
                    # Cap applies across the unit for any items in this option's choice list
                    allowed = {_norm(nn) for ch in (getattr(wargear_option, "wargear_to", []) or []) for qq, nn in (ch or []) if nn}
                    already = sum(1 for mm in (self.models or []) for wg in list(getattr(mm, "wargear", []) or []) if wg and _norm(getattr(wg, "name", "")) in allowed)
                    if already >= limit:
                        continue
                wg = _find_wargear(nm)
                if wg is None:
                    # Keep as optional note (so UI/printouts can still show it)
                    try:
                        if _norm(nm) in ("aspect shrine token", "incubi shrine token"):
                            self.add_aspect_shrine_tokens(int(qty) if qty else 1)
                        model.optional_wargear.append(str(nm))
                    except Exception:
                        pass
                    continue
                to_add = int(qty) if qty else 1
                if remaining_slots is not None:
                    to_add = min(to_add, remaining_slots)
                for _ in range(to_add):
                    model.wargear.append(wg)
                    if not _validate_constraints(model):
                        model.wargear = list(original_wargear)
                        option_invalid = True
                        break
                if option_invalid:
                    break
                # Lock selected items if required
                _lock_selected_items(model, {_norm(getattr(wg, "name", ""))} if wg else set())
                if remaining_slots is not None:
                    remaining_slots -= to_add
                    if remaining_slots <= 0:
                        break

            if option_invalid:
                continue

            # Apply any post-locks to the model after successfully taking this option
            _apply_post_locks(model)
            _mark_model_took_any_option(model)

        # Wargear selection can activate/deactivate wargear abilities.
        try:
            self._invalidate_ability_cache()
        except Exception:
            pass
        try:
            self._parse_against_attack_characteristic_defensive_rules()
        except Exception:
            pass
        try:
            self._refresh_bearer_unit_common_modifiers()
        except Exception:
            pass
        try:
            self._refresh_advance_no_roll_flags()
        except Exception:
            pass
        try:
            self._refresh_ignore_vertical_distance_move_types()
        except Exception:
            pass
        try:
            self._refresh_bearer_keyword_flags()
        except Exception:
            pass
        try:
            self._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass
        try:
            self._refresh_command_phase_flags()
        except Exception:
            pass
        try:
            self._refresh_fall_back_desperate_escape_flags()
        except Exception:
            pass
        try:
            self._refresh_targeted_stratagem_cp_discount_flags()
        except Exception:
            pass
        try:
            self._refresh_charge_end_mortal_wounds_flags()
        except Exception:
            pass
        try:
            self._refresh_fight_within_3_flags()
        except Exception:
            pass

    def apply_wargear_options(self, wargear_name: Optional[str] = None) -> None:
        """
        Apply wargear options.

        - If `wargear_name` is provided: apply the first option that can yield that wargear item (best-effort).
        - If not provided: apply a conservative default set of non-weapon options (those that only add
          "optional wargear" notes because the items do not exist in `possible_wargear`).
        """
        import re

        def _norm(s: str) -> str:
            s = (s or "").replace("\u2019", "'").lower().strip()
            s = re.sub(r"[^\w\s\-']", " ", s)
            s = s.replace("'", "")
            s = re.sub(r"\s+", " ", s).strip()
            return s

        def _find_wargear(item_name: str):
            wanted = _norm(item_name)
            for wg in (getattr(self, "possible_wargear", []) or []):
                if wg and _norm(getattr(wg, "name", "")) == wanted:
                    return wg
            return None

        if not wargear_name:
            # Default behavior used by some unit construction tests:
            # apply only "non-weapon" options that would otherwise be represented as optional_wargear notes.
            for opt in list(getattr(self, "wargear_options", []) or []):
                choices = list(getattr(opt, "wargear_to", []) or [])
                if not choices:
                    continue
                first = choices[0] or []
                if not first:
                    continue
                # Only auto-apply if *all* items are unknown wargear (i.e. they will land in optional_wargear)
                if all(_find_wargear(nm) is None for qty, nm in first if nm):
                    if any(_norm(nm) in ("aspect shrine token", "incubi shrine token") for qty, nm in first if nm):
                        continue
                    self.apply_wargear_option(opt)
            return

        def _norm_variants(s: str) -> set[str]:
            n = _norm(s)
            out = {n}
            if n.endswith("s") and not n.endswith("ss") and len(n) > 3:
                out.add(n[:-1])
            return out

        # Allow disambiguation by exact bundle:
        # - "2 big shootas"
        # - "1 big shoota and 1 rokkit launcha"
        # If user provides qty or multiple items, we require an exact match against a choice.
        spec = (wargear_name or "").strip().lower()
        spec = spec.replace(", ", " and ")
        parts = [p.strip() for p in spec.split(" and ") if p.strip()]
        wanted_tuples = []
        explicit = False
        for p in parts:
            m = re.match(r"^\s*(\d+)\s+(.+?)\s*$", p)
            if m:
                explicit = True
                q = int(m.group(1))
                nm = m.group(2)
            else:
                q = 1
                nm = p
            wanted_tuples.append((q, nm))
        if len(wanted_tuples) > 1:
            explicit = True

        wanted_single = _norm(spec)
        wanted_vars = _norm_variants(spec)

        # STRICT SELECTION RULE:
        # `wargear_name` must uniquely identify exactly one (option, choice) in this unit.
        # If it matches multiple choices/options, we do nothing rather than guessing.
        matches: list[tuple[object, object]] = []
        for opt in list(getattr(self, "wargear_options", []) or []):
            all_choices = list(getattr(opt, "wargear_to", []) or [])
            if not all_choices:
                continue
            for choice in all_choices:
                if not choice:
                    continue
                if explicit:
                    # exact bundle match (order-insensitive)
                    wanted_norm = sorted([(int(q), _norm(nm)) for q, nm in wanted_tuples])
                    choice_norm = sorted([(int(q), _norm(nm)) for q, nm in (choice or []) if nm])
                    if wanted_norm == choice_norm:
                        matches.append((opt, choice))
                else:
                    for qty, nm in (choice or []):
                        nm_vars = _norm_variants(nm)
                        name_match = bool(nm_vars & wanted_vars) or (_norm(nm) == wanted_single)
                        if name_match:
                            matches.append((opt, choice))
                            break

        if not matches:
            # Silent by default (used by UI/other callers), but army-list parsing can request strict behavior.
            strict = False
            try:
                strict = bool(getattr(self, "_strict_wargear_option_resolution", False))
            except Exception:
                strict = False
            if strict:
                raise ValueError(f"Could not resolve wargear option for '{wargear_name}' on unit '{getattr(self, 'name', '<unknown>')}'")
            return

        if len(matches) != 1:
            # Ambiguous (common filler items like "close combat weapon", or shared bundle items like "axe of khorne").
            # Special-case: if there is exactly one ADDITIONAL match and the rest are REPLACEMENT,
            # default to the ADDITIONAL (common "equip X OR replace Y with X" phrasing).
            try:
                from warhammer40k_ai.units.wargear import WargearOptionType
                additional = [(o, c) for (o, c) in matches if getattr(o, "wargear_type", None) == WargearOptionType.ADDITIONAL]
                replacement = [(o, c) for (o, c) in matches if getattr(o, "wargear_type", None) == WargearOptionType.REPLACEMENT]
                if len(additional) == 1 and len(additional) + len(replacement) == len(matches):
                    matches = additional
                else:
                    strict = False
                    try:
                        strict = bool(getattr(self, "_strict_wargear_option_resolution", False))
                    except Exception:
                        strict = False
                    if strict:
                        raise ValueError(
                            f"Ambiguous wargear option '{wargear_name}' for unit '{getattr(self, 'name', '<unknown>')}' "
                            f"(matched {len(matches)} choices)"
                        )
                    return
            except Exception:
                strict = False
                try:
                    strict = bool(getattr(self, "_strict_wargear_option_resolution", False))
                except Exception:
                    strict = False
                if strict:
                    raise ValueError(
                        f"Ambiguous wargear option '{wargear_name}' for unit '{getattr(self, 'name', '<unknown>')}' "
                        f"(matched {len(matches)} choices)"
                    )
                return

        opt, choice = matches[0]
        # Reorder choices to put selected choice first, then apply.
        try:
            choices = list(getattr(opt, "wargear_to", []) or [])
            idx = choices.index(choice)
            if idx != 0:
                choices[0], choices[idx] = choices[idx], choices[0]
                opt.wargear_to = choices
            self.apply_wargear_option(opt)
        except Exception:
            return

    def apply_wargear_options_strict(self, wargear_name: str) -> None:
        """
        Strict variant used by army list parsing: failure to resolve a requested option is an error.
        """
        setattr(self, "_strict_wargear_option_resolution", True)
        try:
            self.apply_wargear_options(wargear_name)
        finally:
            # Always restore default behavior
            try:
                delattr(self, "_strict_wargear_option_resolution")
            except Exception:
                setattr(self, "_strict_wargear_option_resolution", False)

    @staticmethod
    def _norm_wargear_name(s: str) -> str:
        import re
        s = (s or "").replace("\u2019", "'").lower().strip()
        s = re.sub(r"<[^>]+>", " ", s)
        s = re.sub(r"[^\w\s\-']", " ", s)
        s = s.replace("'", "")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def validate_wargear_selection(self) -> None:
        """
        Validate that currently equipped wargear respects parsed wargear constraints.
        This is especially important for army-list parsing, which may directly assign wargear.
        """
        c = getattr(self, "_wargear_constraints", {}) or {}
        if not c:
            return

        def _is_ranged(wg) -> bool:
            return bool(wg) and hasattr(wg, "is_ranged") and wg.is_ranged()

        def _is_pistol(wg) -> bool:
            if not wg:
                return False
            for prof in (getattr(wg, "profiles", {}) or {}).values():
                if prof.is_pistol():
                    return True
            return False

        max_counts = c.get("max_counts", {}) or {}
        mutex_sets = c.get("mutex_sets", []) or []
        max_r = c.get("max_ranged_weapons", None)
        two_ranged_requires_pistol = bool(c.get("two_ranged_requires_pistol", False))
        two_ranged_requires_cyclone_pair = bool(c.get("two_ranged_requires_cyclone_pair", False))

        for model in list(getattr(self, "models", []) or []):
            wargear = [wg for wg in list(getattr(model, "wargear", []) or []) if wg]
            names_norm = [self._norm_wargear_name(getattr(wg, "name", "")) for wg in wargear]

            # Max counts for named items
            if max_counts:
                counts = {}
                for nm in names_norm:
                    counts[nm] = counts.get(nm, 0) + 1
                for nm, mx in max_counts.items():
                    if counts.get(nm, 0) > int(mx):
                        raise ValueError(
                            f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                            f"'{nm}' exceeds max {mx}. Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                        )

            # Mutual exclusions
            for s in mutex_sets:
                present = [nm for nm in names_norm if nm in (s or set())]
                if len(set(present)) > 1:
                    raise ValueError(
                        f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                        f"Mutually exclusive items equipped: {sorted(set(present))}. Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                    )

            # Max ranged weapons
            if max_r is not None:
                ranged = [wg for wg in wargear if _is_ranged(wg)]
                if len(ranged) > int(max_r):
                    raise ValueError(
                        f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                        f"Has {len(ranged)} ranged weapons (max {max_r}). Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                    )

            # Two ranged requires pistol
            if two_ranged_requires_pistol:
                ranged = [wg for wg in wargear if _is_ranged(wg)]
                if len(ranged) == 2:
                    pistols = [wg for wg in ranged if _is_pistol(wg)]
                    if len(pistols) != 1:
                        raise ValueError(
                            f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                            f"Two ranged weapons require exactly one pistol. Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                        )
                if len(ranged) > 2:
                    raise ValueError(
                        f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                        f"Has {len(ranged)} ranged weapons (max 2 under pistol pairing rule). Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                    )

            # Cyclone pairing constraint
            if two_ranged_requires_cyclone_pair:
                ranged = [wg for wg in wargear if _is_ranged(wg)]
                if len(ranged) == 2:
                    names = {self._norm_wargear_name(getattr(wg, "name", "")) for wg in ranged}
                    if "cyclone missile launcher" not in names:
                        raise ValueError(
                            f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                            f"Two ranged weapons require 'cyclone missile launcher'. Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                        )
                    other = (names - {"cyclone missile launcher"})
                    if not other or not (("storm bolter" in other) or ("combi-weapon" in other)):
                        raise ValueError(
                            f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                            f"'cyclone missile launcher' must be paired with 'storm bolter' or 'combi-weapon'. "
                            f"Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                        )
                if len(ranged) > 2:
                    raise ValueError(
                        f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                        f"Has {len(ranged)} ranged weapons (max 2 under cyclone pairing rule). Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                    )

    def _assign_default_wargear_to_model(self, model: Model, *, from_split: bool = False) -> None:
        if model is None:
            return
        try:
            parsed = self._parse_loadout(
                getattr(self._datasheet, "loadout", []),
                str(getattr(model, "name", "") or "").lower(),
                return_optional=True,
                from_split=from_split,
            )
        except Exception:
            parsed = ([], [])
        wargear_to_add = []
        optional_wargear = []
        if isinstance(parsed, tuple):
            wargear_to_add, optional_wargear = parsed
        else:
            wargear_to_add = parsed
        for wargear_instance in wargear_to_add:
            if wargear_instance:
                model.wargear.append(wargear_instance.clone())
        if optional_wargear:
            for ow in optional_wargear:
                try:
                    model.optional_wargear.append(str(ow))
                except Exception:
                    continue
        self._apply_optional_wargear_weapon_grants(model)

    def _apply_optional_wargear_weapon_grants(self, model: Model) -> None:
        """Materialize weapon grants from optional wargear abilities onto the bearer model."""
        if model is None:
            return
        optional_items = [str(v or "").strip() for v in list(getattr(model, "optional_wargear", []) or []) if str(v or "").strip()]
        if not optional_items:
            return

        wargear_by_name: dict[str, Wargear] = {}
        for wargear in list(getattr(self, "possible_wargear", []) or []):
            if wargear is None:
                continue
            key = self._norm_wargear_name(getattr(wargear, "name", "") or "")
            if key and key not in wargear_by_name:
                wargear_by_name[key] = wargear
        if not wargear_by_name:
            return

        ability_by_name: dict[str, Ability] = {}
        for ability in list(getattr(self, "possible_abilities", []) or []):
            if ability is None:
                continue
            try:
                atype = str(getattr(ability, "type", "") or "").lower()
            except Exception:
                atype = ""
            if "wargear" not in atype:
                continue
            key = self._norm_wargear_name(str(getattr(ability, "name", "") or ""))
            if key and key not in ability_by_name:
                ability_by_name[key] = ability
        if not ability_by_name:
            return

        desired_counts: dict[str, int] = {}
        for optional_name in optional_items:
            ability = ability_by_name.get(self._norm_wargear_name(optional_name))
            if ability is None:
                continue
            text = self._normalize_rules_text(str(getattr(ability, "description", "") or getattr(ability, "name", "") or ""))
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            for match in re.finditer(
                r"(?:the\s+)?bearer\s+is\s+equipped\s+with\s+(?P<count>\d+|one)\s+(?P<weapon>[a-z0-9][a-z0-9 '\-]+?)(?:\.|,|;| and |$)",
                norm,
                flags=re.IGNORECASE,
            ):
                count_token = str(match.group("count") or "").strip().lower()
                if not count_token:
                    continue
                if count_token == "one":
                    count = 1
                else:
                    try:
                        count = int(count_token)
                    except Exception:
                        count = 0
                if count <= 0:
                    continue
                weapon_key = self._norm_wargear_name(str(match.group("weapon") or ""))
                if weapon_key not in wargear_by_name:
                    continue
                desired_counts[weapon_key] = int(desired_counts.get(weapon_key, 0) or 0) + int(count)

        if not desired_counts:
            return

        current_counts: dict[str, int] = {}
        for wargear in list(getattr(model, "wargear", []) or []):
            key = self._norm_wargear_name(getattr(wargear, "name", "") or "")
            if not key:
                continue
            current_counts[key] = int(current_counts.get(key, 0) or 0) + 1

        for weapon_key, desired in desired_counts.items():
            template = wargear_by_name.get(weapon_key)
            if template is None:
                continue
            current = int(current_counts.get(weapon_key, 0) or 0)
            missing = max(0, int(desired) - current)
            for _ in range(missing):
                model.wargear.append(template.clone())
            if missing > 0:
                current_counts[weapon_key] = int(current + missing)

    def add_wargear(self, wargear: List[Wargear]=[], model_name: str=None) -> None:
        for model_instance in self.models:
            wargear_to_add = []
            optional_wargear = []
            if not wargear:
                parsed = self._parse_loadout(
                    getattr(self._datasheet, 'loadout', []),
                    model_instance.name.lower(),
                    return_optional=True,
                    from_split=False,
                )
                if isinstance(parsed, tuple):
                    wargear_to_add, optional_wargear = parsed
                else:
                    wargear_to_add = parsed
            else:
                wargear_to_add.extend(wargear)
            for wargear_instance in wargear_to_add:
                if model_name:
                    if model_instance.name.lower() == model_name.lower():
                        if wargear_instance:
                            model_instance.wargear.append(wargear_instance.clone())
                else:
                    if wargear_instance:
                        model_instance.wargear.append(wargear_instance.clone())
            if optional_wargear:
                for ow in optional_wargear:
                    try:
                        model_instance.optional_wargear.append(str(ow))
                    except Exception:
                        continue
            self._apply_optional_wargear_weapon_grants(model_instance)
        if wargear:
            self.validate_wargear_selection()

    def set_parent_army(self, army_ptr) -> None:
        """Set the parent army of the unit."""
        self.parent_army = army_ptr

    def get_parent_army(self) -> Optional['Army']:
        """Get the parent army of the unit."""
        return getattr(self, "parent_army", None)

    def _publish_unit_event(self, event_name: str, **kwargs) -> None:
        if not event_name:
            return
        if "unit" not in kwargs:
            kwargs["unit"] = self
        army = self.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        game = getattr(player, "game", None) if player is not None else None
        event_system = getattr(game, "event_system", None) if game is not None else None
        if event_system is None:
            return
        try:
            event_system.publish(event_name, **kwargs)
        except Exception:
            pass

    def add_ability(self, ability: Ability, model_name: str=None, quantity: int=1000) -> None:
        """Add ability to the unit."""
        count = 0
        for model in self.models:
            if count >= quantity:
                break
            if model_name:
                if model.name == model_name:
                    model.add_ability(ability)
            else:
                model.add_ability(ability)
            count += 1
        # Invalidate ability cache since abilities changed
        self._invalidate_ability_cache()

    def _ability_cache_owner(self):
        try:
            return self.get_attached_unit_root()
        except Exception:
            return self

    def _ensure_ability_cache_generations(self) -> None:
        owner = self._ability_cache_owner()
        if owner is None:
            return
        if not hasattr(owner, "_ability_structure_generation"):
            owner._ability_structure_generation = 0
        if not hasattr(owner, "_ability_activity_generation"):
            owner._ability_activity_generation = 0

    def _bump_ability_structure_generation(self) -> None:
        owner = self._ability_cache_owner()
        if owner is None:
            return
        self._ensure_ability_cache_generations()
        owner._ability_structure_generation = int(getattr(owner, "_ability_structure_generation", 0) or 0) + 1
        # Structure changes always imply activity generation changes as well.
        owner._ability_activity_generation = int(getattr(owner, "_ability_activity_generation", 0) or 0) + 1

    def _bump_ability_activity_generation(self) -> None:
        owner = self._ability_cache_owner()
        if owner is None:
            return
        self._ensure_ability_cache_generations()
        owner._ability_activity_generation = int(getattr(owner, "_ability_activity_generation", 0) or 0) + 1

    def _invalidate_ability_cache(self) -> None:
        """Invalidate ability cache when unit state changes."""
        owner = self._ability_cache_owner()
        if owner is None:
            owner = self
        try:
            self._bump_ability_structure_generation()
        except Exception:
            pass
        if hasattr(owner, '_ability_cache'):
            owner._ability_cache.clear()
        # Keep local cache object in sync for callers that read from self directly.
        if owner is not self and hasattr(self, "_ability_cache"):
            self._ability_cache.clear()

    def _invalidate_ability_activity_cache(self) -> None:
        """
        Invalidate caches tied to ability activation state without marking structure changed.
        """
        owner = self._ability_cache_owner()
        if owner is None:
            owner = self
        try:
            self._bump_ability_activity_generation()
        except Exception:
            pass
        if hasattr(owner, "_ability_cache"):
            owner._ability_cache.clear()
        if owner is not self and hasattr(self, "_ability_cache"):
            self._ability_cache.clear()

    # Remove a Model from a Unit (e.g., when it dies)

