from __future__ import annotations

import re
from typing import Optional

from ..utility.ability_support import ABILITY_SYNAPSE, army_has_ability_id
from ..utility.aura_utils import model_within_range_of_unit, unit_within_range_of_unit

_NEUROCYTES_RULE_RE = re.compile(
    r"while this unit is within synapse range of a friendly tyranids unit excluding neurogaunt units it has the synapse keyword"
)


class SynapseManager:
    """
    Tyranids army rule: Synapse.
    """

    def __init__(self, army=None):
        self.army = army

    def _army_has_synapse(self) -> bool:
        army = self.army
        if army is None:
            return False
        try:
            faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "TYR":
            return False
        if army_has_ability_id(army, ABILITY_SYNAPSE):
            return True
        if not faction_id:
            for unit in list(getattr(army, "units", []) or []):
                if self._unit_is_tyranids(unit):
                    return True
        return False

    @staticmethod
    def _unit_is_tyranids(unit) -> bool:
        if unit is None:
            return False
        try:
            return unit.has_any_keyword("TYRANIDS")
        except Exception:
            return False

    @staticmethod
    def _normalize_rules_text(text: object) -> str:
        raw = str(text or "")
        if not raw:
            return ""
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = raw.replace("\u2019", "'")
        raw = raw.lower()
        raw = re.sub(r"[^a-z0-9]+", " ", raw)
        raw = re.sub(r"\s+", " ", raw).strip()
        return raw

    @staticmethod
    def _iter_unit_ability_entries(unit) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        pools = [
            list(getattr(unit, "possible_abilities", []) or []),
            list(getattr(unit, "abilities", []) or []),
        ]
        for pool in pools:
            for ability in pool:
                if isinstance(ability, str):
                    entries.append((str(ability or ""), ""))
                    continue
                if isinstance(ability, dict):
                    entries.append(
                        (
                            str(ability.get("name", "") or ""),
                            str(ability.get("description", "") or ""),
                        )
                    )
                    continue
                entries.append(
                    (
                        str(getattr(ability, "name", "") or ""),
                        str(getattr(ability, "description", "") or ""),
                    )
                )
        return entries

    @staticmethod
    def _unit_has_keyword_token(unit, keyword: str) -> bool:
        token = str(keyword or "").strip().upper()
        if not token:
            return False
        try:
            has_any = getattr(unit, "has_any_keyword", None)
            if callable(has_any) and has_any(token):
                return True
        except Exception:
            pass
        normalized_target = token.rstrip("S")
        entries = list(getattr(unit, "keywords", []) or []) + list(getattr(unit, "faction_keywords", []) or [])
        for value in entries:
            entry = str(value or "").strip().upper()
            if not entry:
                continue
            if entry == token or entry.rstrip("S") == normalized_target:
                return True
        return False

    def _unit_is_neurogaunt(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword_token(unit, "NEUROGAUNT")

    @staticmethod
    def _unit_on_battlefield(unit) -> bool:
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
            if bool(getattr(unit, "embarked_in", None)):
                return False
            if bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            pass
        return True

    def _unit_has_native_synapse_keyword(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_is_tyranids(unit):
            return False
        try:
            if not unit.has_any_keyword("SYNAPSE"):
                return False
        except Exception:
            return False
        return True

    def _unit_has_neurocytes_rule(self, unit) -> bool:
        if unit is None or not self._unit_is_tyranids(unit):
            return False
        for ability_name, ability_desc in self._iter_unit_ability_entries(unit):
            name_norm = self._normalize_rules_text(ability_name)
            desc_norm = self._normalize_rules_text(ability_desc)
            if name_norm and name_norm != "neurocytes":
                continue
            if not desc_norm:
                continue
            if _NEUROCYTES_RULE_RE.fullmatch(desc_norm):
                return True
        return False

    def _unit_has_neuroloids_synapse_marker(self, unit) -> bool:
        if unit is None:
            return False
        candidates = [unit]
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is not None and root is not unit:
            candidates.insert(0, root)
        army_owner = str(getattr(getattr(self.army, "player", None), "id", "") or "").strip()
        for candidate in candidates:
            sr = getattr(candidate, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("neuroloids_synapse_active", False)):
                continue
            marker_owner = str(sr.get("neuroloids_synapse_owner", "") or "").strip()
            if marker_owner and army_owner and marker_owner != army_owner:
                continue
            return True
        return False

    @staticmethod
    def _units_within_range(source_unit, target_unit, range_inches: float) -> bool:
        try:
            return bool(
                unit_within_range_of_unit(
                    source_unit,
                    target_unit,
                    float(range_inches),
                    use_attached_aggregate=True,
                )
            )
        except Exception:
            return False

    def _unit_is_in_range_of_sources(self, unit, sources: list, *, linchpin_sources: list) -> bool:
        for source in list(sources or []):
            if source is None:
                continue
            if self._units_within_range(source, unit, 6.0):
                return True
        for source in list(linchpin_sources or []):
            if source is None:
                continue
            rng = self._linchpin_range_for_unit(source)
            try:
                get_bearer = getattr(source, "_get_enhancement_bearer_model", None)
                bearer = get_bearer() if callable(get_bearer) else None
            except Exception:
                bearer = None
            if bearer is not None:
                try:
                    if model_within_range_of_unit(bearer, unit, rng, use_attached_aggregate=True):
                        return True
                except Exception:
                    continue
            else:
                if self._units_within_range(source, unit, float(rng)):
                    return True
        return False

    def _unit_is_synapse_source(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_is_tyranids(unit):
            return False
        if not self._unit_on_battlefield(unit):
            return False
        if self._unit_has_native_synapse_keyword(unit):
            return True
        for source in self.get_synapse_sources():
            if source is unit:
                return True
        return False

    @staticmethod
    def _unit_has_synaptic_linchpin(unit) -> bool:
        if unit is None:
            return False
        try:
            sr = getattr(unit, "special_rules", None)
        except Exception:
            sr = None
        if isinstance(sr, dict) and bool(sr.get("enhancement_synaptic_linchpin", False)):
            return True
        try:
            enh = getattr(unit, "enhancement", None)
        except Exception:
            enh = None
        if enh is None:
            return False
        try:
            enh_id = str(getattr(enh, "id", "") or "").strip()
        except Exception:
            enh_id = ""
        if enh_id == "000008348004":
            return True
        try:
            enh_name = str(getattr(enh, "name", "") or "").replace("\u2019", "'").strip().lower()
        except Exception:
            enh_name = ""
        return enh_name == "synaptic linchpin"

    @staticmethod
    def _linchpin_range_for_unit(unit) -> float:
        default = 9.0
        if unit is None:
            return default
        try:
            sr = getattr(unit, "special_rules", None)
        except Exception:
            sr = None
        if not isinstance(sr, dict):
            return default
        try:
            return float(sr.get("enhancement_synaptic_linchpin_range", default) or default)
        except Exception:
            return default

    def get_synaptic_linchpin_sources(self) -> list:
        if not self._army_has_synapse():
            return []
        sources = []
        for unit in list(getattr(self.army, "units", []) or []):
            if not self._unit_is_tyranids(unit):
                continue
            if not self._unit_on_battlefield(unit):
                continue
            if not self._unit_has_synaptic_linchpin(unit):
                continue
            sources.append(unit)
        return sources

    def unit_within_synaptic_linchpin_sources(self, unit, *, game=None, game_map=None) -> bool:
        if not self._army_has_synapse():
            return False
        if unit is None:
            return False
        sources = self.get_synaptic_linchpin_sources()
        if not sources:
            return False
        for source in sources:
            rng = self._linchpin_range_for_unit(source)
            try:
                get_bearer = getattr(source, "_get_enhancement_bearer_model", None)
                bearer = get_bearer() if callable(get_bearer) else None
            except Exception:
                bearer = None
            if bearer is not None:
                try:
                    if model_within_range_of_unit(bearer, unit, rng, use_attached_aggregate=True):
                        return True
                except Exception:
                    continue
            else:
                try:
                    if unit_within_range_of_unit(source, unit, rng, use_attached_aggregate=True):
                        return True
                except Exception:
                    continue
        return False

    def get_synapse_sources(self, *, game=None, game_map=None) -> list:
        if not self._army_has_synapse():
            return []
        tyr_units = []
        for unit in list(getattr(self.army, "units", []) or []):
            if not self._unit_is_tyranids(unit):
                continue
            if not self._unit_on_battlefield(unit):
                continue
            tyr_units.append(unit)

        sources: list = []
        source_ids: set[int] = set()
        for unit in tyr_units:
            if not self._unit_has_native_synapse_keyword(unit):
                continue
            sources.append(unit)
            source_ids.add(id(unit))

        neurocyte_candidates = []
        for unit in tyr_units:
            if id(unit) in source_ids:
                continue
            if self._unit_has_neurocytes_rule(unit):
                neurocyte_candidates.append(unit)
        if not neurocyte_candidates:
            return sources

        linchpin_sources = self.get_synaptic_linchpin_sources()
        changed = True
        while changed:
            changed = False
            for candidate in neurocyte_candidates:
                if id(candidate) in source_ids:
                    continue
                for friendly in tyr_units:
                    if friendly is candidate:
                        continue
                    if self._unit_is_neurogaunt(friendly):
                        continue
                    if not self._units_within_range(friendly, candidate, 6.0):
                        continue
                    if not self._unit_is_in_range_of_sources(friendly, sources, linchpin_sources=linchpin_sources):
                        continue
                    sources.append(candidate)
                    source_ids.add(id(candidate))
                    changed = True
                    break
        return sources

    def unit_within_synapse_sources(self, unit, *, game=None, game_map=None) -> bool:
        if not self._army_has_synapse():
            return False
        if unit is None:
            return False
        sources = self.get_synapse_sources(game=game, game_map=game_map)
        if not sources:
            return False
        for source in sources:
            try:
                if unit_within_range_of_unit(source, unit, 6.0, use_attached_aggregate=True):
                    return True
            except Exception:
                continue
        return False

    def unit_in_synapse_range(self, unit, *, game=None, game_map=None) -> bool:
        if unit is None:
            return False
        if not self._army_has_synapse():
            return False
        if not self._unit_is_tyranids(unit):
            return False
        if not self._unit_on_battlefield(unit):
            return False
        if self._unit_has_neuroloids_synapse_marker(unit):
            return True
        if self.unit_within_synapse_sources(unit, game=game, game_map=game_map):
            return True
        return self.unit_within_synaptic_linchpin_sources(unit, game=game, game_map=game_map)
