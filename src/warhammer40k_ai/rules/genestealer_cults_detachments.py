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
    _A_CHINK_RULE_NAME = "A Chink in Their Armour"
    _A_CHINK_SR_KEY = "gsc_a_chink_in_their_armour_effects"
    _A_CHINK_KEY_PREFIX = "gsc_a_chink_in_their_armour"
    _A_CHINK_KEYWORDS = ("LETHAL HITS",)
    _A_CHINK_ENHANCEMENT_ID = "000009067003"
    _A_CHINK_NAME_KEY = "achinkintheirarmour"

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

    def _model_weapon_names(self, model, *, attack_type: str = "any") -> list[str]:
        attack = str(attack_type or "any").strip().lower()
        if attack not in ("any", "ranged", "melee"):
            attack = "any"
        by_key: dict[str, str] = {}
        for wargear in list(getattr(model, "wargear", []) or []):
            if attack == "ranged":
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
            elif attack == "melee":
                is_melee = getattr(wargear, "is_melee", None)
                if not callable(is_melee) or not bool(is_melee()):
                    continue
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

    def _clear_temporary_weapon_keyword_effects(
        self,
        unit,
        *,
        sr_key: str,
        owner_id: str | None = None,
    ) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return

        entries_raw = list(sr.get(sr_key, []) or [])
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
            sr[sr_key] = remaining
        else:
            sr.pop(sr_key, None)
        unit.special_rules = sr

    def _clear_a_perfect_ambush_effects(self, unit, *, owner_id: str | None = None) -> None:
        self._clear_temporary_weapon_keyword_effects(
            unit,
            sr_key=self._A_PERFECT_AMBUSH_SR_KEY,
            owner_id=owner_id,
        )

    def _clear_a_chink_in_their_armour_effects(self, unit, *, owner_id: str | None = None) -> None:
        self._clear_temporary_weapon_keyword_effects(
            unit,
            sr_key=self._A_CHINK_SR_KEY,
            owner_id=owner_id,
        )

    def _has_host_of_ascension_enhancement(self, unit, *, enhancement_id: str, name_key: str) -> bool:
        target_id = str(enhancement_id or "").strip()
        target_name_key = str(name_key or "").strip().lower()
        try:
            members = list(unit.get_attached_unit_members() or [])
        except Exception:
            members = [unit]
        if not members:
            members = [unit]
        for member in members:
            enhancement = getattr(member, "enhancement", None)
            if enhancement is None:
                continue
            enh_id = str(getattr(enhancement, "id", "") or "").strip()
            if target_id and enh_id == target_id:
                return True
            enh_name = str(getattr(enhancement, "name", "") or "").strip().lower()
            enh_name = re.sub(r"[^a-z0-9]+", "", enh_name)
            if target_name_key and enh_name == target_name_key:
                return True
        return False

    def _apply_host_of_ascension_reinforcement_weapon_keywords(
        self,
        unit,
        *,
        game,
        owner_id: str,
        source_name: str,
        sr_key: str,
        key_prefix: str,
        keywords: tuple[str, ...],
        attack_type: str = "any",
    ) -> None:
        self._clear_temporary_weapon_keyword_effects(unit, sr_key=sr_key)

        model_effect_keys: list[dict] = []
        for model in self._iter_attached_models(unit):
            alive = getattr(model, "is_alive", True)
            if callable(alive):
                alive = alive()
            if not bool(alive):
                continue
            set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
            if not callable(set_keywords):
                continue
            model_id = str(get_entity_id(model) or "")
            if not model_id:
                continue
            weapon_names = self._model_weapon_names(model, attack_type=attack_type)
            for idx, weapon_name in enumerate(weapon_names):
                effect_key = f"{key_prefix}:{model_id}:{idx}"
                set_keywords(
                    key=effect_key,
                    weapon_name=weapon_name,
                    keywords=list(keywords),
                    source=source_name,
                    expires_phase="",
                    attack_type=str(attack_type or "any"),
                )
                model_effect_keys.append(
                    {
                        "model_id": model_id,
                        "effect_key": effect_key,
                    }
                )

        if not model_effect_keys:
            return

        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        entries = [
            entry
            for entry in list(sr.get(sr_key, []) or [])
            if isinstance(entry, dict)
        ]
        effect_entry: dict = {
            "owner_id": owner_id,
            "source": source_name,
            "model_effect_keys": model_effect_keys,
        }
        if game is not None:
            effect_entry["battle_round"] = int(getattr(game, "turn", 0) or 0)
        entries.append(effect_entry)
        sr[sr_key] = entries
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

        self._apply_host_of_ascension_reinforcement_weapon_keywords(
            root,
            game=game,
            owner_id=owner_id,
            source_name=self._A_PERFECT_AMBUSH_RULE_NAME,
            sr_key=self._A_PERFECT_AMBUSH_SR_KEY,
            key_prefix=self._A_PERFECT_AMBUSH_KEY_PREFIX,
            keywords=self._A_PERFECT_AMBUSH_KEYWORDS,
            attack_type="any",
        )

        if self._has_host_of_ascension_enhancement(
            root,
            enhancement_id=self._A_CHINK_ENHANCEMENT_ID,
            name_key=self._A_CHINK_NAME_KEY,
        ):
            self._apply_host_of_ascension_reinforcement_weapon_keywords(
                root,
                game=game,
                owner_id=owner_id,
                source_name=self._A_CHINK_RULE_NAME,
                sr_key=self._A_CHINK_SR_KEY,
                key_prefix=self._A_CHINK_KEY_PREFIX,
                keywords=self._A_CHINK_KEYWORDS,
                attack_type="ranged",
            )

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
            self._clear_a_chink_in_their_armour_effects(root, owner_id=owner_id)
