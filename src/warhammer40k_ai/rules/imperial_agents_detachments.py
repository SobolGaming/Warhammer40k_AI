from __future__ import annotations

import re

from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class ImperialAgentsDetachmentManager(DetachmentManagerBase):
    faction_id = "AOI"
    _EXTREMIS_DETACHMENT_NAME = "Veiled Blade Elimination Force"
    _EXTREMIS_SURCHARGE_BY_UNIT_NAME = {
        "callidus assassin": 40,
        "culexus assassin": 40,
        "eversor assassin": 35,
        "vindicare assassin": 45,
    }
    _EXTREMIS_EXTRA_USE_KEY_BY_ABILITY_NAME = {
        "overkill": "movement_phase_normal_move_bonus:overkill",
        "soulless horror": "soulless_horror",
        "shieldbreaker": "shieldbreaker",
    }

    @staticmethod
    def _normalize_name(value: str) -> str:
        text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())
        return re.sub(r"\s+", " ", text).strip()

    def is_veiled_blade_elimination_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._EXTREMIS_DETACHMENT_NAME)

    def _iter_unique_army_roots(self) -> list:
        if self.army is None:
            return []
        roots: list = []
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            rid = str(get_entity_id(root) or "")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            roots.append(root)
        roots.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return roots

    def _unit_is_officio_assassinorum(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_has_keyword(unit, "OFFICIO ASSASSINORUM"):
            return False
        return True

    @staticmethod
    def _model_ability_name_keys(model) -> set[str]:
        abilities = getattr(model, "abilities", None)
        if not isinstance(abilities, dict):
            return set()
        names = set()
        for key in list(abilities.keys()):
            name_key = ImperialAgentsDetachmentManager._normalize_name(str(key or ""))
            if name_key:
                names.add(name_key)
        return names

    def _ability_name_keys_for_model(self, unit, model) -> set[str]:
        names = set(self._model_ability_name_keys(model))
        if unit is None or model is None:
            return names
        iter_fn = getattr(unit, "_iter_model_specific_ability_entries", None)
        if not callable(iter_fn):
            return names
        for name, _desc in list(iter_fn(model) or []):
            name_key = self._normalize_name(str(name or ""))
            if name_key:
                names.add(name_key)
        return names

    def _ensure_model_extra_use(self, model, key: str, *, count: int = 1) -> None:
        if model is None:
            return
        key_norm = str(key or "").strip().lower()
        if not key_norm:
            return
        desired = max(0, int(count or 0))
        if desired <= 0:
            return
        extra = getattr(model, "_once_per_battle_extra_uses", None)
        if not isinstance(extra, dict):
            extra = {}
        try:
            current = int(extra.get(key_norm, 0) or 0)
        except Exception:
            current = 0
        add = desired - current
        if add <= 0:
            return
        grant_fn = getattr(model, "grant_once_per_battle_extra_use", None)
        if callable(grant_fn):
            grant_fn(key_norm, uses=int(add))

    def apply_extremis_sanction_extra_uses(self, unit=None) -> None:
        if not self.is_veiled_blade_elimination_force():
            return
        roots: list
        if unit is None:
            roots = self._iter_unique_army_roots()
        else:
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            roots = [root] if root is not None else []

        for root in list(roots or []):
            if root is None or not self._unit_is_officio_assassinorum(root):
                continue
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            for model in list(models or []):
                if model is None:
                    continue
                ability_name_keys = self._ability_name_keys_for_model(root, model)
                if not ability_name_keys:
                    continue
                for ability_name, once_per_battle_key in self._EXTREMIS_EXTRA_USE_KEY_BY_ABILITY_NAME.items():
                    if ability_name not in ability_name_keys:
                        continue
                    self._ensure_model_extra_use(model, once_per_battle_key, count=1)

    def extremis_sanction_points_surcharge_for_unit(self, unit) -> int:
        if not self.is_veiled_blade_elimination_force():
            return 0
        if unit is None:
            return 0
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None or not self._unit_is_officio_assassinorum(root):
            return 0
        unit_name_key = self._normalize_name(str(getattr(root, "name", "") or ""))
        return int(self._EXTREMIS_SURCHARGE_BY_UNIT_NAME.get(unit_name_key, 0) or 0)

    def validate_detachment_rules(self) -> list[str]:
        self.apply_extremis_sanction_extra_uses()
        return []
