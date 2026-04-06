"""Enhancement, attachment, and bodyguard relationship helpers for Unit positioning/runtime state."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class PositioningEnhancementMixin:
    def attached_unit_has_blessings_of_khorne(self) -> bool:
        """Attached unit eligibility: true if any attached member (bodyguard or leader) has Blessings of Khorne ability."""
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "blood_tithe_might_of_khorne_applies", None):
                if mgr.blood_tithe_might_of_khorne_applies(self):
                    return True
            if mgr is not None and getattr(mgr, "unit_is_blood_legions", None):
                if mgr.unit_is_blood_legions(self) and self._unit_within_icon_of_war_range():
                    return True
        except Exception:
            pass
        for u in self.get_attached_unit_members():
            try:
                found, _ = u._find_ability_with_patterns(["blessings of khorne"])
            except Exception:
                found = False
            if found:
                return True
        return False


    def has_icon_of_khorne(self) -> bool:
        """True if this unit has the Icon of Khorne ability."""
        if "icon_of_khorne" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["icon_of_khorne"])
        found, _ = self._find_ability_with_patterns(["icon of khorne"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["icon_of_khorne"] = bool(found)
        return bool(found)


    def has_icon_of_war(self) -> bool:
        """True if this unit has the Icon of War enhancement."""
        cache_key = "icon_of_war"
        if cache_key in getattr(self, "_ability_cache", {}):
            if bool(self._ability_cache[cache_key]):
                return True
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_icon_of_war"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "icon of war" or enh_id == "000010078002":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)


    def has_disciple_of_khorne(self) -> bool:
        """True if this unit has the Disciple of Khorne enhancement."""
        cache_key = "disciple_of_khorne"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_disciple_of_khorne"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "disciple of khorne" or enh_id == "000010078004":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)


    def has_butcher_lord(self) -> bool:
        """True if this unit has the Butcher Lord enhancement."""
        cache_key = "butcher_lord"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_butcher_lord"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "butcher lord" or enh_id == "000010074003":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)


    def has_abhuman_detail(self) -> bool:
        """True if this unit has the Abhuman Detail enhancement."""
        cache_key = "abhuman_detail"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_abhuman_detail"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "abhuman detail" or enh_id == "000010637002":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)


    def has_exalted_patron(self) -> bool:
        """True if this unit has the Exalted Patron enhancement."""
        cache_key = "exalted_patron"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_exalted_patron"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "exalted patron" or enh_id == "000010654003":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)


    def has_wolf_touched(self) -> bool:
        """True if this unit has the Wolf-touched enhancement."""
        cache_key = "wolf_touched"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_wolf_touched"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower().replace("\u2019", "'").replace("\u2018", "'")
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "wolf-touched" or enh_id == "000010269002":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)


    def has_grimnars_mark(self) -> bool:
        """True if this unit has the Grimnar's Mark enhancement."""
        cache_key = "grimnars_mark"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_grimnars_mark"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = (
                    str(getattr(enh, "name", "") or "")
                    .strip()
                    .lower()
                    .replace("\u2019", "'")
                    .replace("\u2018", "'")
                )
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name in ("grimnar's mark", "grimnars mark") or enh_id == "000010660002":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)


    def has_catechism_of_divine_penitence(self) -> bool:
        """True if this unit has the Catechism of Divine Penitence enhancement."""
        cache_key = "catechism_of_divine_penitence"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_catechism_of_divine_penitence"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "catechism of divine penitence" or enh_id == "000009029005":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)


    def has_synaptic_tyrant(self) -> bool:
        """True if this unit has the Synaptic Tyrant enhancement."""
        cache_key = "synaptic_tyrant"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_synaptic_tyrant"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "synaptic tyrant" or enh_id == "000009737002":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)


    def _attached_unit_has_enhancement_flag(
        self,
        flag_key: str,
        *,
        enhancement_id: str = "",
        enhancement_name: str = "",
    ) -> bool:
        if not flag_key and not enhancement_id and not enhancement_name:
            return False
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
        norm_name = ""
        if enhancement_name:
            try:
                norm_name = str(enhancement_name or "").strip().lower()
            except Exception:
                norm_name = ""
        for unit in members:
            if unit is None:
                continue
            try:
                sr = getattr(unit, "special_rules", None)
                if isinstance(sr, dict) and flag_key and sr.get(flag_key):
                    return True
            except Exception:
                pass
            try:
                enh = getattr(unit, "enhancement", None)
                if enh is None:
                    continue
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if enhancement_id and enh_id == enhancement_id:
                    return True
                if norm_name:
                    enh_name = str(getattr(enh, "name", "") or "").strip().lower()
                    if enh_name == norm_name:
                        return True
            except Exception:
                continue
        return False


    def _attached_unit_has_active_enhancement(
        self,
        flag_key: str,
        *,
        enhancement_id: str = "",
        enhancement_name: str = "",
        require_bearer_alive: bool = True,
    ) -> bool:
        """
        Return True when any attached-unit member has the enhancement and (by default)
        the bearer model is alive.
        """
        if not flag_key and not enhancement_id and not enhancement_name:
            return False

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

        norm_name = ""
        if enhancement_name:
            try:
                norm_name = str(enhancement_name or "").strip().lower()
            except Exception:
                norm_name = ""

        for unit in members:
            if unit is None:
                continue

            matched = False
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict) and flag_key and sr.get(flag_key):
                matched = True
            if not matched:
                try:
                    enh = getattr(unit, "enhancement", None)
                    if enh is not None:
                        enh_unit_id = str(getattr(enh, "id", "") or "").strip()
                        if enhancement_id and enh_unit_id == enhancement_id:
                            matched = True
                        elif norm_name:
                            enh_name = str(getattr(enh, "name", "") or "").strip().lower()
                            if enh_name == norm_name:
                                matched = True
                except Exception:
                    matched = False
            if not matched:
                continue

            if not require_bearer_alive:
                return True

            bearer_id = ""
            if isinstance(sr, dict):
                bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
            if bearer_id:
                for model in list(getattr(unit, "models", []) or []):
                    try:
                        model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                    except Exception:
                        model_id = ""
                    if model_id != bearer_id:
                        continue
                    try:
                        alive_attr = getattr(model, "is_alive", True)
                        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    except Exception:
                        alive = False
                    if alive:
                        return True
                continue

            get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
            if callable(get_bearer):
                try:
                    if get_bearer() is not None:
                        return True
                    continue
                except Exception:
                    continue

            for model in list(getattr(unit, "models", []) or []):
                try:
                    alive_attr = getattr(model, "is_alive", True)
                    alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                except Exception:
                    alive = False
                if alive:
                    return True

        return False

    @staticmethod
    def _attached_unit_sort_key(entity) -> tuple[int, str, str]:
        entity_id = str(get_entity_id(entity) or "").strip()
        name = str(getattr(entity, "name", "") or "").strip().lower()
        if entity_id:
            return (0, entity_id, name)
        return (1, name, "")


    @staticmethod
    def _enhancement_bearer_is_alive_for_unit(unit, special_rules: Optional[dict] = None) -> bool:
        sr = special_rules if isinstance(special_rules, dict) else getattr(unit, "special_rules", None)
        models = list(getattr(unit, "models", []) or [])

        bearer_id = ""
        if isinstance(sr, dict):
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
        if bearer_id:
            for model in models:
                model_id = str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                if model_id != bearer_id:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                return bool(alive_attr() if callable(alive_attr) else alive_attr)
            return False

        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is None:
                return False
            alive_attr = getattr(bearer, "is_alive", True)
            return bool(alive_attr() if callable(alive_attr) else alive_attr)

        for model in models:
            alive_attr = getattr(model, "is_alive", True)
            if bool(alive_attr() if callable(alive_attr) else alive_attr):
                return True
        return False


    def _attached_unit_active_enhancement_sources(
        self,
        flag_key: str,
        *,
        enhancement_id: str = "",
        enhancement_name: str = "",
        require_bearer_alive: bool = True,
        source_keys: tuple[str, ...] = (),
    ) -> list[dict]:
        """
        Return matching attached-unit enhancement sources sorted by canonical entity id.
        """
        if not flag_key and not enhancement_id and not enhancement_name:
            return []

        get_root = getattr(self, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else self
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]

        norm_name = str(enhancement_name or "").strip().lower()
        ordered_members = [member for member in members if member is not None]
        ordered_members.sort(key=self._attached_unit_sort_key)

        results: list[dict] = []
        for member in ordered_members:
            sr = getattr(member, "special_rules", None)
            enh = getattr(member, "enhancement", None)
            matched = False
            if isinstance(sr, dict) and flag_key and bool(sr.get(flag_key)):
                matched = True
            if not matched and enh is not None:
                enh_unit_id = str(getattr(enh, "id", "") or "").strip()
                if enhancement_id and enh_unit_id == enhancement_id:
                    matched = True
                elif norm_name and str(getattr(enh, "name", "") or "").strip().lower() == norm_name:
                    matched = True
            if not matched:
                continue
            if require_bearer_alive and not self._enhancement_bearer_is_alive_for_unit(
                member,
                sr if isinstance(sr, dict) else None,
            ):
                continue

            source = ""
            if isinstance(sr, dict):
                for source_key in source_keys:
                    source = str(sr.get(source_key, "") or "").strip()
                    if source:
                        break
            if not source and enh is not None:
                source = str(getattr(enh, "name", "") or enhancement_name or "Enhancement").strip()
            if not source and enhancement_name:
                source = str(enhancement_name or "").strip()

            results.append(
                {
                    "unit": member,
                    "special_rules": sr if isinstance(sr, dict) else {},
                    "enhancement": enh,
                    "source": source or "Enhancement",
                }
            )
        return results


    def _attached_unit_has_active_leading_enhancement(
        self,
        flag_key: str,
        *,
        enhancement_id: str = "",
        enhancement_name: str = "",
        require_bearer_alive: bool = True,
    ) -> bool:
        """
        Return True when an attached Leader has the enhancement and (by default)
        its bearer model is alive.
        """
        if not flag_key and not enhancement_id and not enhancement_name:
            return False

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        leaders = list(getattr(root, "attached_leaders", []) or [])
        if not leaders:
            return False

        norm_name = ""
        if enhancement_name:
            try:
                norm_name = str(enhancement_name or "").strip().lower()
            except Exception:
                norm_name = ""

        for leader in leaders:
            if leader is None:
                continue

            matched = False
            sr = getattr(leader, "special_rules", None)
            if isinstance(sr, dict) and flag_key and sr.get(flag_key):
                matched = True
            if not matched:
                try:
                    enh = getattr(leader, "enhancement", None)
                    if enh is not None:
                        enh_unit_id = str(getattr(enh, "id", "") or "").strip()
                        if enhancement_id and enh_unit_id == enhancement_id:
                            matched = True
                        elif norm_name:
                            enh_name = str(getattr(enh, "name", "") or "").strip().lower()
                            if enh_name == norm_name:
                                matched = True
                except Exception:
                    matched = False
            if not matched:
                continue

            if not require_bearer_alive:
                return True

            bearer_id = ""
            if isinstance(sr, dict):
                bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
            if bearer_id:
                for model in list(getattr(leader, "models", []) or []):
                    try:
                        model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                    except Exception:
                        model_id = ""
                    if model_id != bearer_id:
                        continue
                    try:
                        alive_attr = getattr(model, "is_alive", True)
                        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    except Exception:
                        alive = False
                    if alive:
                        return True
                continue

            get_bearer = getattr(leader, "_get_enhancement_bearer_model", None)
            if callable(get_bearer):
                try:
                    bearer = get_bearer()
                except Exception:
                    bearer = None
                if bearer is None:
                    continue
                try:
                    alive_attr = getattr(bearer, "is_alive", True)
                    alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                except Exception:
                    alive = False
                if alive:
                    return True
                continue

            for model in list(getattr(leader, "models", []) or []):
                try:
                    alive_attr = getattr(model, "is_alive", True)
                    alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                except Exception:
                    alive = False
                if alive:
                    return True

        return False


    def _attached_unit_model_is_enhancement_bearer(
        self,
        model,
        *,
        flag_key: str,
        enhancement_id: str = "",
        enhancement_name: str = "",
        require_leading: bool = False,
        require_bearer_alive: bool = True,
    ) -> bool:
        """
        Return True when `model` is the enhancement bearer for a matching attached-unit enhancement.
        """
        if model is None or (not flag_key and not enhancement_id and not enhancement_name):
            return False
        model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
        if not model_id:
            return False

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if require_leading:
            candidates = list(getattr(root, "attached_leaders", []) or [])
        else:
            try:
                candidates = list(root.get_attached_unit_members() or [])
            except Exception:
                candidates = [root]
        if not candidates:
            candidates = [root]

        norm_name = ""
        if enhancement_name:
            try:
                norm_name = str(enhancement_name or "").strip().lower()
            except Exception:
                norm_name = ""

        for unit in candidates:
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            matched = bool(isinstance(sr, dict) and flag_key and sr.get(flag_key))
            if not matched:
                try:
                    enh = getattr(unit, "enhancement", None)
                    if enh is not None:
                        enh_unit_id = str(getattr(enh, "id", "") or "").strip()
                        if enhancement_id and enh_unit_id == enhancement_id:
                            matched = True
                        elif norm_name:
                            enh_name = str(getattr(enh, "name", "") or "").strip().lower()
                            if enh_name == norm_name:
                                matched = True
                except Exception:
                    matched = False
            if not matched:
                continue

            bearer = None
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "") if isinstance(sr, dict) else ""
            if bearer_id:
                for candidate_model in list(getattr(unit, "models", []) or []):
                    candidate_id = str(get_entity_id(candidate_model) or getattr(candidate_model, "id", getattr(candidate_model, "_id", "")) or "")
                    if candidate_id == bearer_id:
                        bearer = candidate_model
                        break
            if bearer is None:
                get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
                if callable(get_bearer):
                    try:
                        bearer = get_bearer()
                    except Exception:
                        bearer = None
            if bearer is None:
                continue

            bearer_entity_id = str(get_entity_id(bearer) or getattr(bearer, "id", getattr(bearer, "_id", "")) or "")
            if bearer_entity_id != model_id:
                continue
            if not require_bearer_alive:
                return True
            try:
                alive_attr = getattr(bearer, "is_alive", True)
                alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            except Exception:
                alive = False
            if alive:
                return True
        return False


    def _is_lord_on_juggernaut(self) -> bool:
        try:
            dsid = str(getattr(getattr(self, "_datasheet", None), "id", "") or "").strip()
        except Exception:
            dsid = ""
        if dsid == "000002625":
            return True
        try:
            name = self._normalize_attached_unit_name(getattr(self, "name", ""))
        except Exception:
            name = ""
        return name == "lord on juggernaut"


    def _disciple_of_khorne_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        try:
            dsid = str(getattr(getattr(bodyguard, "_datasheet", None), "id", "") or "").strip()
        except Exception:
            dsid = ""
        if dsid in {"000004107", "000004108"}:
            return True
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        return name in {"bloodcrushers", "flesh hounds"}


    def _disciple_of_khorne_is_bearer(self) -> bool:
        if not self.has_disciple_of_khorne():
            return False
        if not self.is_leader:
            return False
        if not self._is_lord_on_juggernaut():
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if mgr is None:
            return False
        try:
            if not mgr.is_khorne_daemonkin():
                return False
        except Exception:
            return False
        return True


    def _disciple_of_khorne_active(self, bodyguard=None) -> bool:
        if not self._disciple_of_khorne_is_bearer():
            return False
        if bodyguard is None:
            bodyguard = getattr(self, "attached_to", None)
        if bodyguard is None:
            return False
        return self._disciple_of_khorne_bodyguard_allowed(bodyguard)


    def _disciple_of_khorne_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._disciple_of_khorne_is_bearer():
            return False
        return self._disciple_of_khorne_bodyguard_allowed(bodyguard)


    def _butcher_lord_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        try:
            if bodyguard.has_any_keyword("JAKHALS"):
                return True
        except Exception:
            pass
        try:
            if bodyguard.has_any_keyword("GOREMONGERS"):
                return True
        except Exception:
            pass
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        return name in {"jakhals", "goremongers"}


    def _butcher_lord_is_bearer(self) -> bool:
        if not self.has_butcher_lord():
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if mgr is None:
            return False
        try:
            if not mgr.is_cult_of_blood():
                return False
        except Exception:
            return False
        return True


    def _butcher_lord_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._butcher_lord_is_bearer():
            return False
        return self._butcher_lord_bodyguard_allowed(bodyguard)


    def _abhuman_detail_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        try:
            if bodyguard.has_any_keyword("OGRYN"):
                return True
        except Exception:
            pass
        configured_names: list[str] = []
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict):
                configured_names = [
                    self._normalize_attached_unit_name(v)
                    for v in list(sr.get("enhancement_abhuman_detail_attach_unit_names", ()) or ())
                    if str(v or "").strip()
                ]
        except Exception:
            configured_names = []
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        if name in set(configured_names):
            return True
        return name in {"ogryn squad", "bullgryn squad", "ogryns", "bullgryns"}


    def _abhuman_detail_is_bearer(self) -> bool:
        if not self.has_abhuman_detail():
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        try:
            if not self.has_any_keyword("COMMISSAR"):
                return False
        except Exception:
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        if mgr is None:
            return False
        try:
            if not mgr.is_grizzled_company():
                return False
        except Exception:
            return False
        return True


    def _abhuman_detail_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._abhuman_detail_is_bearer():
            return False
        return self._abhuman_detail_bodyguard_allowed(bodyguard)


    def _butcher_lord_infiltrators_active(self, bodyguard=None) -> bool:
        if not self._butcher_lord_is_bearer():
            return False
        if bodyguard is None:
            bodyguard = getattr(self, "attached_to", None)
        if bodyguard is None:
            return False
        try:
            if bodyguard.has_any_keyword("GOREMONGERS"):
                return True
        except Exception:
            pass
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        return name == "goremongers"


    def _is_lord_exultant(self) -> bool:
        try:
            dsid = str(getattr(getattr(self, "_datasheet", None), "id", "") or "").strip()
        except Exception:
            dsid = ""
        if dsid == "000004078":
            return True
        try:
            name = self._normalize_attached_unit_name(getattr(self, "name", ""))
        except Exception:
            name = ""
        return name == "lord exultant"


    def _exalted_patron_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        try:
            dsid = str(getattr(getattr(bodyguard, "_datasheet", None), "id", "") or "").strip()
        except Exception:
            dsid = ""
        if dsid == "000004089":
            return True
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        return name == "flawless blades"


    def _exalted_patron_is_bearer(self) -> bool:
        if not self.has_exalted_patron():
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        if not self._is_lord_exultant():
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "emperors_children_detachments", None) if army is not None else None
        if mgr is None:
            mgr = getattr(army, "emperors_children", None) if army is not None else None
        if mgr is None:
            return False
        try:
            if not mgr.is_court_of_the_phoenician():
                return False
        except Exception:
            return False
        return True


    def _exalted_patron_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._exalted_patron_is_bearer():
            return False
        return self._exalted_patron_bodyguard_allowed(bodyguard)


    def _wolf_touched_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        has_wulfen_keyword = False
        has_infantry_keyword = False
        try:
            has_wulfen_keyword = bool(bodyguard.has_any_keyword("WULFEN"))
        except Exception:
            has_wulfen_keyword = False
        try:
            has_infantry_keyword = bool(bodyguard.has_any_keyword("INFANTRY"))
        except Exception:
            has_infantry_keyword = False
        if has_wulfen_keyword and has_infantry_keyword:
            return True
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        if "wulfen" not in name:
            return False
        if "dreadnought" in name:
            return False
        if has_infantry_keyword:
            return True
        # Fallback for unit records where INFANTRY keyword may not be hydrated.
        return True


    def _wolf_touched_is_bearer(self) -> bool:
        if not self.has_wolf_touched():
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        if sm_mgr is None:
            return False
        try:
            if not sm_mgr.is_saga_of_the_beastslayer():
                return False
        except Exception:
            return False
        return True


    def _wolf_touched_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._wolf_touched_is_bearer():
            return False
        return self._wolf_touched_bodyguard_allowed(bodyguard)


    def _grimnars_mark_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        configured_names: list[str] = []
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict):
                configured_names = [
                    self._normalize_attached_unit_name(v)
                    for v in list(sr.get("enhancement_grimnars_mark_attach_unit_names", ()) or ())
                    if str(v or "").strip()
                ]
        except Exception:
            configured_names = []
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        if name in set(configured_names):
            return True
        if "wolf guard terminator" in name:
            return True
        try:
            if bool(bodyguard.has_any_keyword("WOLF GUARD TERMINATORS")):
                return True
        except Exception:
            pass
        return False


    def _grimnars_mark_is_bearer(self) -> bool:
        if not self.has_grimnars_mark():
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        if sm_mgr is None:
            return False
        try:
            if not sm_mgr.is_saga_of_the_great_wolf():
                return False
        except Exception:
            return False
        try:
            has_terminator_keyword = bool(self.has_any_keyword("TERMINATOR"))
        except Exception:
            has_terminator_keyword = False
        if not has_terminator_keyword:
            return False
        name_norm = ""
        try:
            name_norm = self._normalize_attached_unit_name(getattr(self, "name", ""))
        except Exception:
            name_norm = ""
        try:
            has_captain_keyword = bool(self.has_any_keyword("CAPTAIN"))
        except Exception:
            has_captain_keyword = False
        if not has_captain_keyword and "captain" not in name_norm:
            return False
        return True


    def _grimnars_mark_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._grimnars_mark_is_bearer():
            return False
        return self._grimnars_mark_bodyguard_allowed(bodyguard)


    def _catechism_of_divine_penitence_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        configured_names: list[str] = []
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict):
                configured_names = [
                    self._normalize_attached_unit_name(v)
                    for v in list(sr.get("enhancement_catechism_of_divine_penitence_attach_unit_names", ()) or ())
                    if str(v or "").strip()
                ]
        except Exception:
            configured_names = []
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        if name in set(configured_names):
            return True
        if "repentia squad" in name:
            return True
        try:
            if bool(bodyguard.has_any_keyword("REPENTIA")):
                return True
        except Exception:
            pass
        return False


    def _catechism_of_divine_penitence_is_bearer(self) -> bool:
        if not self.has_catechism_of_divine_penitence():
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        as_mgr = getattr(army, "adepta_sororitas_detachments", None) if army is not None else None
        if as_mgr is None:
            return False
        try:
            if not as_mgr.is_penitent_host():
                return False
        except Exception:
            return False

        allowed_keywords = ("CANONESS", "PALATINE", "MINISTORUM PRIEST")
        for keyword in allowed_keywords:
            try:
                if bool(self.has_any_keyword(keyword)):
                    return True
            except Exception:
                continue
        try:
            name = self._normalize_attached_unit_name(getattr(self, "name", ""))
        except Exception:
            name = ""
        return bool(
            "canoness" in name
            or "palatine" in name
            or "ministorum priest" in name
        )


    def _catechism_of_divine_penitence_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._catechism_of_divine_penitence_is_bearer():
            return False
        return self._catechism_of_divine_penitence_bodyguard_allowed(bodyguard)


    def _synaptic_tyrant_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        configured_names: list[str] = []
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict):
                configured_names = [
                    self._normalize_attached_unit_name(v)
                    for v in list(sr.get("enhancement_synaptic_tyrant_attach_unit_names", ()) or ())
                    if str(v or "").strip()
                ]
        except Exception:
            configured_names = []
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        if name in set(configured_names):
            return True
        if "tyranid warriors" in name:
            return True
        try:
            if bool(bodyguard.has_any_keyword("TYRANID WARRIORS")):
                return True
        except Exception:
            pass
        return False


    def _synaptic_tyrant_is_bearer(self) -> bool:
        if not self.has_synaptic_tyrant():
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        tyr_mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
        if tyr_mgr is None:
            return False
        try:
            if not tyr_mgr.is_warrior_bioform_onslaught():
                return False
        except Exception:
            return False
        try:
            if bool(self.has_any_keyword("NEUROTYRANT")):
                return True
        except Exception:
            pass
        try:
            name = self._normalize_attached_unit_name(getattr(self, "name", ""))
        except Exception:
            name = ""
        return name == "neurotyrant"


    def _synaptic_tyrant_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._synaptic_tyrant_is_bearer():
            return False
        if not self._enhancement_bearer_model_is_alive(flag_key="enhancement_synaptic_tyrant"):
            return False
        return self._synaptic_tyrant_bodyguard_allowed(bodyguard)


    def _enhancement_bearer_model_is_alive(self, *, flag_key: str) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get(flag_key)):
            return False
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
        if bearer_id:
            for model in list(getattr(self, "models", []) or []):
                model_id = str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "")
                if model_id != bearer_id:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                return bool(alive_attr() if callable(alive_attr) else alive_attr)
            return False
        bearer = self._get_enhancement_bearer_model()
        if bearer is None:
            return False
        alive_attr = getattr(bearer, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)


    def _taktikal_enhancement_attach_override_names(
        self,
        *,
        flag_key: str,
        attach_names_key: str,
        defaults: tuple[str, ...],
    ) -> list[str]:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
            return []
        configured = [
            self._normalize_attached_unit_name(v)
            for v in list(sr.get(attach_names_key, defaults) or [])
            if str(v or "").strip()
        ]
        return [name for name in configured if name]


    def _bodyguard_matches_attach_override_names(self, bodyguard, names: list[str], *, keyword: str) -> bool:
        if bodyguard is None:
            return False
        bodyguard_name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        if bodyguard_name in set(names):
            return True
        has_any_keyword = getattr(bodyguard, "has_any_keyword", None)
        if callable(has_any_keyword):
            try:
                if bool(has_any_keyword(keyword)):
                    return True
            except Exception:
                return False
        return False


    def _skwad_leader_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        if not self._enhancement_bearer_model_is_alive(flag_key="enhancement_skwad_leader"):
            return False
        names = self._taktikal_enhancement_attach_override_names(
            flag_key="enhancement_skwad_leader",
            attach_names_key="enhancement_skwad_leader_attach_unit_names",
            defaults=("Kommandos",),
        )
        if not names:
            return False
        return self._bodyguard_matches_attach_override_names(bodyguard, names, keyword="KOMMANDOS")


    def _bray_lord_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        if not self._enhancement_bearer_model_is_alive(flag_key="enhancement_bray_lord"):
            return False
        names = self._taktikal_enhancement_attach_override_names(
            flag_key="enhancement_bray_lord",
            attach_names_key="enhancement_bray_lord_attach_unit_names",
            defaults=("Tzaangors",),
        )
        if not names:
            return False
        return self._bodyguard_matches_attach_override_names(bodyguard, names, keyword="TZAANGOR")


    def _mek_kaptin_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        if not self._enhancement_bearer_model_is_alive(flag_key="enhancement_mek_kaptin"):
            return False
        names = self._taktikal_enhancement_attach_override_names(
            flag_key="enhancement_mek_kaptin",
            attach_names_key="enhancement_mek_kaptin_attach_unit_names",
            defaults=("Flash Gitz",),
        )
        if not names:
            return False
        return self._bodyguard_matches_attach_override_names(bodyguard, names, keyword="FLASH GITZ")


    def _murdermind_is_bearer(self) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("enhancement_murdermind")):
            return False
        if not bool(getattr(self, "is_leader", False)):
            return False
        get_parent_army = getattr(self, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(self, "parent_army", None)
        mgr = getattr(army, "necrons_detachments", None) if army is not None else None
        is_cursed_legion = getattr(mgr, "is_cursed_legion", None) if mgr is not None else None
        return bool(callable(is_cursed_legion) and is_cursed_legion())


    def _murdermind_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("enhancement_murdermind")):
            return False
        required_keyword = str(
            sr.get("enhancement_murdermind_attach_required_keyword", "DESTROYER CULT") or "DESTROYER CULT"
        ).strip().upper()
        if not required_keyword:
            return False
        bodyguard_has_keyword = getattr(bodyguard, "has_any_keyword", None)
        if not callable(bodyguard_has_keyword) or not bool(bodyguard_has_keyword(required_keyword)):
            return False
        excluded_keywords = {
            str(value or "").strip().upper()
            for value in list(sr.get("enhancement_murdermind_attach_exclude_keywords_any", ()) or ())
            if str(value or "").strip()
        }
        for keyword in excluded_keywords:
            if bool(bodyguard_has_keyword(keyword)):
                return False
        for leader in list(getattr(bodyguard, "attached_leaders", []) or []):
            if leader is None or leader is self:
                continue
            leader_has_keyword = getattr(leader, "has_any_keyword", None)
            if not callable(leader_has_keyword):
                return False
            if not bool(leader_has_keyword(required_keyword)):
                return False
        return True


    def _murdermind_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._murdermind_is_bearer():
            return False
        if not self._enhancement_bearer_model_is_alive(flag_key="enhancement_murdermind"):
            return False
        return self._murdermind_bodyguard_allowed(bodyguard)


    def _skwad_leader_is_leading_kommandos(self) -> bool:
        if not bool(getattr(self, "is_attached_leader", False)):
            return False
        if not self._enhancement_bearer_model_is_alive(flag_key="enhancement_skwad_leader"):
            return False
        bodyguard = getattr(self, "attached_to", None)
        names = self._taktikal_enhancement_attach_override_names(
            flag_key="enhancement_skwad_leader",
            attach_names_key="enhancement_skwad_leader_attach_unit_names",
            defaults=("Kommandos",),
        )
        if not names:
            return False
        return self._bodyguard_matches_attach_override_names(bodyguard, names, keyword="KOMMANDOS")


    def _disciple_of_khorne_active_leaders(self) -> list["Unit"]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        leaders = list(getattr(root, "attached_leaders", []) or [])
        active: list["Unit"] = []
        for leader in leaders:
            try:
                if leader._disciple_of_khorne_active(bodyguard=root):
                    active.append(leader)
            except Exception:
                continue
        return active


    def _unit_on_battlefield_for_icon_of_war(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if not bool(getattr(unit, "deployed", True)):
                return False
            if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
                return False
        except Exception:
            return False
        try:
            if bool(getattr(unit, "embarked_in", None)) or bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            pass
        return True


    def _models_within_icon_of_war_range(self, source_unit, target_unit, *, radius: float) -> bool:
        try:
            from ...utility.aura_utils import distance_between_models_bases_3d
        except Exception:
            return False
        try:
            src_models = list(getattr(source_unit, "models", []) or [])
        except Exception:
            src_models = []
        try:
            tgt_models = list(target_unit.get_attached_unit_models() or [])
        except Exception:
            tgt_models = list(getattr(target_unit, "models", []) or [])
        if not src_models or not tgt_models:
            return False
        for sm in src_models:
            try:
                if not getattr(sm, "is_alive", True):
                    continue
            except Exception:
                continue
            for tm in tgt_models:
                try:
                    if not getattr(tm, "is_alive", True):
                        continue
                except Exception:
                    continue
                try:
                    if distance_between_models_bases_3d(sm, tm) <= float(radius) + 1e-6:
                        return True
                except Exception:
                    continue
        return False


    def _unit_within_icon_of_war_range(self, *, radius: float = 6.0) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if not self._unit_on_battlefield_for_icon_of_war(root):
            return False
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return False
        try:
            units = list(getattr(army, "units", []) or [])
        except Exception:
            units = []
        for source in units:
            try:
                if not source.has_icon_of_war():
                    continue
            except Exception:
                continue
            if not self._unit_on_battlefield_for_icon_of_war(source):
                continue
            if self._models_within_icon_of_war_range(source, root, radius=radius):
                return True
        return False


    def _unit_within_carmine_reliquary_range(self, *, radius: float = 6.0) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if not self._unit_on_battlefield_for_icon_of_war(root):
            return False
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return False
        try:
            units = list(getattr(army, "units", []) or [])
        except Exception:
            units = []
        for source in units:
            try:
                sr = getattr(source, "special_rules", None)
                if not (isinstance(sr, dict) and sr.get("enhancement_carmine_reliquary")):
                    continue
            except Exception:
                continue
            if not self._unit_on_battlefield_for_icon_of_war(source):
                continue
            if self._models_within_icon_of_war_range(source, root, radius=radius):
                return True
        return False


    def _icon_of_war_battle_shock_reroll_available(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if mgr is None:
            return False
        try:
            if not mgr.is_khorne_daemonkin():
                return False
        except Exception:
            return False
        try:
            if not mgr.is_blood_tithe_active("MIGHT_OF_KHORNE"):
                return False
        except Exception:
            return False
        try:
            if not mgr.unit_is_blood_legions(root):
                return False
        except Exception:
            return False
        return bool(root._unit_within_icon_of_war_range())
