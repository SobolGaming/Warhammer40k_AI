from __future__ import annotations

import re

from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class GenestealerCultsDetachmentManager(DetachmentManagerBase):
    faction_id = "GC"

    _A_PERFECT_AMBUSH_RULE_NAME = "A Perfect Ambush"
    _A_PERFECT_AMBUSH_SR_KEY = "gsc_a_perfect_ambush_effects"
    _A_PERFECT_AMBUSH_KEY_PREFIX = "gsc_a_perfect_ambush"
    _A_PERFECT_AMBUSH_KEYWORDS = ("SUSTAINED HITS 1", "IGNORES COVER")

    @staticmethod
    def _attached_root(unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
            if root is not None:
                return root
        return unit

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    def _unit_is_genestealer_cults(self, unit) -> bool:
        return self._unit_has_keyword_or_faction(unit, "GENESTEALER CULTS", faction_id=self.faction_id)

    def _iter_unit_roots(self) -> list:
        if self.army is None:
            return []
        unique_roots = {}
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            root_id = str(get_entity_id(root) or "")
            if not root_id or root_id in unique_roots:
                continue
            unique_roots[root_id] = root
        return [unique_roots[k] for k in sorted(unique_roots.keys())]

    def _iter_attached_models(self, unit) -> list:
        get_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        else:
            models = list(getattr(unit, "models", []) or [])
        return sorted(
            [model for model in models if model is not None],
            key=lambda m: str(get_entity_id(m) or ""),
        )

    @staticmethod
    def _weapon_name_token(weapon_name: str) -> str:
        token = re.sub(r"[^a-z0-9]+", " ", str(weapon_name or "").lower())
        return re.sub(r"\s+", " ", token).strip()

    def _model_weapon_names(self, model) -> list[str]:
        by_key: dict[str, str] = {}
        for wargear in list(getattr(model, "wargear", []) or []):
            weapon_name = str(getattr(wargear, "name", "") or "").strip()
            if not weapon_name:
                continue
            token = self._weapon_name_token(weapon_name)
            if not token or token in by_key:
                continue
            by_key[token] = weapon_name
        return [by_key[k] for k in sorted(by_key.keys())]

    def is_host_of_ascension(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Host of Ascension")

    def _clear_a_perfect_ambush_effects(self, unit, *, owner_id: str | None = None) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return

        entries_raw = list(sr.get(self._A_PERFECT_AMBUSH_SR_KEY, []) or [])
        if not entries_raw:
            return

        model_by_id = {
            str(get_entity_id(model) or ""): model
            for model in self._iter_attached_models(unit)
        }

        remaining: list[dict] = []
        owner_key = str(owner_id or "")
        for entry in entries_raw:
            if not isinstance(entry, dict):
                continue
            entry_owner = str(entry.get("owner_id", "") or "")
            if owner_key and entry_owner != owner_key:
                remaining.append(entry)
                continue

            for model_key in list(entry.get("model_effect_keys", []) or []):
                if not isinstance(model_key, dict):
                    continue
                model_id = str(model_key.get("model_id", "") or "")
                effect_key = str(model_key.get("effect_key", "") or "").strip().lower()
                if not model_id or not effect_key:
                    continue
                model = model_by_id.get(model_id)
                if model is None:
                    continue
                effects = getattr(model, "_temporary_effects", None)
                if isinstance(effects, dict):
                    effects.pop(effect_key, None)

        if remaining:
            sr[self._A_PERFECT_AMBUSH_SR_KEY] = remaining
        else:
            sr.pop(self._A_PERFECT_AMBUSH_SR_KEY, None)
        unit.special_rules = sr

    def on_unit_set_up(self, *, unit=None, game=None, set_up_as_reinforcements: bool = False) -> None:
        if not self.is_host_of_ascension():
            return
        if not bool(set_up_as_reinforcements):
            return

        root = self._attached_root(unit)
        if root is None:
            return
        if not self._unit_in_army(root):
            return
        if not self._unit_is_genestealer_cults(root):
            return

        army = self.army
        if army is None:
            return
        player = getattr(army, "player", None)
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return

        self._clear_a_perfect_ambush_effects(root)

        model_effect_keys: list[dict] = []
        for model in self._iter_attached_models(root):
            if not bool(getattr(model, "is_alive", False)):
                continue
            set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
            if not callable(set_keywords):
                continue
            model_id = str(get_entity_id(model) or "")
            if not model_id:
                continue
            for idx, weapon_name in enumerate(self._model_weapon_names(model)):
                effect_key = f"{self._A_PERFECT_AMBUSH_KEY_PREFIX}:{model_id}:{idx}"
                set_keywords(
                    key=effect_key,
                    weapon_name=weapon_name,
                    keywords=list(self._A_PERFECT_AMBUSH_KEYWORDS),
                    source=self._A_PERFECT_AMBUSH_RULE_NAME,
                    expires_phase="",
                    attack_type="any",
                )
                model_effect_keys.append(
                    {
                        "model_id": model_id,
                        "effect_key": effect_key,
                    }
                )

        if not model_effect_keys:
            return

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        entries = [
            entry
            for entry in list(sr.get(self._A_PERFECT_AMBUSH_SR_KEY, []) or [])
            if isinstance(entry, dict)
        ]
        effect_entry: dict = {
            "owner_id": owner_id,
            "source": self._A_PERFECT_AMBUSH_RULE_NAME,
            "model_effect_keys": model_effect_keys,
        }
        if game is not None:
            effect_entry["battle_round"] = int(getattr(game, "turn", 0) or 0)
        entries.append(effect_entry)
        sr[self._A_PERFECT_AMBUSH_SR_KEY] = entries
        root.special_rules = sr

    def cleanup_on_phase_end(self, phase, active_player) -> None:
        if not self.is_host_of_ascension():
            return
        phase_name = str(getattr(phase, "name", phase) or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        owner_id = str(getattr(active_player, "id", "") or "")
        if not owner_id:
            return
        for root in self._iter_unit_roots():
            self._clear_a_perfect_ambush_effects(root, owner_id=owner_id)
