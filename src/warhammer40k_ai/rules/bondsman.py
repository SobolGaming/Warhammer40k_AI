from __future__ import annotations

from itertools import combinations

from ..utility.ability_support import ABILITY_BONDSMAN, army_has_ability_id
from ..utility.entity_ids import get_entity_id, maybe_entity_id


_BONDSMAN_EFFECTS = {
    "paladin's duty": {"lethal_hits": True, "lance": True},
    "errant's duty": {"reroll_advance": True, "assault_ranged": True},
    "warden's duty": {"sustained_hits": 1, "ignores_cover_ranged": True},
    "gallant's duty": {"reroll_charge": True, "reroll_hit_melee": True},
    "crusader's duty": {"ranged_hit_bonus": 1},
    "acheron's duty": {"acheron_battleshock": True},
    "atrapos' duty": {"reroll_hit_wound_vs_titanic": True},
    "castigator's duty": {"sustained_hits_ranged": 1, "ap_bonus_ranged": 1},
    "lancer's duty": {"charge_after_advance": True},
    "magaera's duty": {"magaera_bonus": True},
    "styrix's duty": {"styrix_battleshock": True},
    "mentor": {"reroll_wound_vs_quarry": True},
    "defender's duty": {"damage_reduction": 1},
}


def _norm(text: str) -> str:
    return (text or "").replace("\u2019", "'").replace("\u00e2\u20ac\u2122", "'").strip().lower()


class BondsmanManager:
    """
    Imperial Knights army rule: Bondsman.

    In your Command phase, each model with a Bondsman ability can select one friendly
    ARMIGER model within 12" that is not already affected by a Bondsman ability.
    The selected ARMIGER gains the Bondsman ability's effects until your next Command phase.
    """

    def __init__(self, army=None):
        self.army = army
        self._used_bondsman_ability_keys: set[str] = set()

    @staticmethod
    def _unit_sort_key(unit) -> str:
        token = maybe_entity_id(unit)
        if token:
            return str(token)
        return str(getattr(unit, "name", "") or "")

    @staticmethod
    def _root_unit(unit):
        if unit is None:
            return None
        root_getter = getattr(unit, "get_attached_unit_root", None)
        if callable(root_getter):
            return root_getter()
        return unit

    def _detachment_manager(self):
        if self.army is None:
            return None
        return getattr(self.army, "imperial_knights_detachments", None)

    def _is_spearhead_at_arms(self) -> bool:
        detachment_mgr = self._detachment_manager()
        check = getattr(detachment_mgr, "is_spearhead_at_arms", None)
        return bool(callable(check) and check())

    def _is_questor_forgepact(self) -> bool:
        detachment_mgr = self._detachment_manager()
        check = getattr(detachment_mgr, "is_questor_forgepact", None)
        return bool(callable(check) and check())

    def _army_is_honoured(self) -> bool:
        if self.army is None:
            return False
        code_mgr = getattr(self.army, "code_chivalric", None)
        if code_mgr is not None and bool(getattr(code_mgr, "honoured", False)):
            return True
        return bool(getattr(self.army, "code_chivalric_honoured", False))

    def _bondsman_target_range(self, source_unit) -> float:
        del source_unit
        if not self._is_spearhead_at_arms():
            return 12.0
        if self._army_is_honoured():
            return 15.0
        return 12.0

    def _bondsman_ability_keys_for_unit(self, unit) -> tuple[str, ...]:
        keys = []
        for name in self._bondsman_ability_names(unit):
            key = _norm(name).replace(" (bondsman)", "").strip()
            if key and key not in keys:
                keys.append(key)
        keys.sort()
        return tuple(keys)

    def _bondsman_primary_ability_key(self, unit) -> str:
        keys = self._bondsman_ability_keys_for_unit(unit)
        if not keys:
            return ""
        return str(keys[0])

    def _bondsman_target_cap(self, source_unit) -> int:
        if not self._is_spearhead_at_arms():
            return 1
        ability_key = self._bondsman_primary_ability_key(source_unit)
        if not ability_key:
            return 1
        if ability_key in self._used_bondsman_ability_keys:
            return 1
        return 3

    def _mark_bondsman_ability_used(self, source_unit) -> None:
        ability_key = self._bondsman_primary_ability_key(source_unit)
        if ability_key:
            self._used_bondsman_ability_keys.add(str(ability_key))

    def _bondsman_ability_used_for_unit(self, source_unit) -> bool:
        ability_key = self._bondsman_primary_ability_key(source_unit)
        if not ability_key:
            return False
        return str(ability_key) in self._used_bondsman_ability_keys

    @staticmethod
    def _selected_target_ids_from_payload(payload: dict | None) -> list[str]:
        data = dict(payload or {})
        selected_ids: list[str] = []
        raw_selected = data.get("selected_unit_ids")
        if isinstance(raw_selected, (list, tuple)):
            for value in list(raw_selected):
                token = str(value or "").strip()
                if token and token not in selected_ids:
                    selected_ids.append(token)
        if selected_ids:
            return selected_ids
        token = str(
            data.get("target_unit_id")
            or data.get("unit_id")
            or data.get("target")
            or ""
        ).strip()
        if token:
            selected_ids.append(token)
        return selected_ids

    def _army_has_bondsman(self) -> bool:
        if self.army is None:
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "QI":
            return False
        if army_has_ability_id(self.army, ABILITY_BONDSMAN):
            return True
        for unit in list(getattr(self.army, "units", []) or []):
            if self._unit_has_bondsman_ability(unit):
                return True
        return False

    def _unit_has_bondsman_ability(self, unit) -> bool:
        if unit is None:
            return False
        for ab in (list(getattr(unit, "possible_abilities", []) or []) + list(getattr(unit, "abilities", []) or [])):
            try:
                name = ab if isinstance(ab, str) else getattr(ab, "name", "")
                if "bondsman" in _norm(name):
                    return True
            except Exception:
                continue
        return False

    def _unit_is_armiger(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return bool(unit.has_any_keyword("ARMIGER"))
        except Exception:
            return False

    def _unit_is_imperial_knights_character(self, unit) -> bool:
        root = self._root_unit(unit)
        if root is None:
            return False
        detachment_mgr = self._detachment_manager()
        is_ik = getattr(detachment_mgr, "_unit_is_imperial_knights", None) if detachment_mgr is not None else None
        if not callable(is_ik) or not bool(is_ik(root)):
            return False
        try:
            return bool(root.has_any_keyword("CHARACTER"))
        except Exception:
            return False

    def _unit_is_adeptus_mechanicus(self, unit) -> bool:
        root = self._root_unit(unit)
        if root is None:
            return False
        detachment_mgr = self._detachment_manager()
        check = getattr(detachment_mgr, "_unit_is_adeptus_mechanicus", None) if detachment_mgr is not None else None
        return bool(callable(check) and check(root))

    @staticmethod
    def _unit_is_knight_preceptor(unit) -> bool:
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
        name = str(getattr(root, "name", "") or "").replace("\u2019", "'").strip().lower()
        return name == "knight preceptor"

    def _unit_is_active_for_rules(self, unit) -> bool:
        root = self._root_unit(unit)
        if root is None:
            return False
        detachment_mgr = self._detachment_manager()
        check = getattr(detachment_mgr, "_battlefield_root_active", None) if detachment_mgr is not None else None
        if callable(check):
            return bool(check(root))
        return self._unit_is_valid_source(root) or self._unit_is_armiger(root)

    def _unit_is_valid_source(self, unit) -> bool:
        if unit is None or not self._unit_has_bondsman_ability(unit):
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            return False
        try:
            if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", True)):
                return False
        except Exception:
            pass
        return True

    def _bondsman_ability_names(self, unit) -> list[str]:
        names: list[str] = []
        for ab in (list(getattr(unit, "possible_abilities", []) or []) + list(getattr(unit, "abilities", []) or [])):
            try:
                name = ab if isinstance(ab, str) else getattr(ab, "name", "")
            except Exception:
                name = ""
            if "bondsman" in _norm(name):
                names.append(str(name))
        return names

    def get_bondsman_ability_names(self, unit) -> list[str]:
        return self._bondsman_ability_names(unit)

    def _clear_questor_forgepact_bonded_imperative(self, source_unit) -> None:
        root = self._root_unit(source_unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "questor_forgepact_bonded_imperative_pending",
            "questor_forgepact_bonded_imperative_source",
            "questor_forgepact_bonded_imperative_turn",
            "questor_forgepact_bonded_imperative_turn_owner",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def _questor_forgepact_bonded_imperative_pending(self, source_unit) -> bool:
        if not self._is_questor_forgepact():
            return False
        root = self._root_unit(source_unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        return bool(isinstance(sr, dict) and sr.get("questor_forgepact_bonded_imperative_pending"))

    def _questor_forgepact_bonded_imperative_admech_candidates(self, source_unit, *, game_map=None) -> list:
        if self.army is None or not self._is_questor_forgepact():
            return []
        source_root = self._root_unit(source_unit)
        if source_root is None or not self._unit_is_imperial_knights_character(source_root):
            return []
        detachment_mgr = self._detachment_manager()
        within_distance = getattr(detachment_mgr, "_unit_within_distance", None) if detachment_mgr is not None else None
        candidates = []
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._root_unit(unit)
            if root is None or root is source_root:
                continue
            if not self._unit_is_adeptus_mechanicus(root):
                continue
            if not self._unit_is_active_for_rules(root):
                continue
            in_range = False
            if callable(within_distance):
                in_range = bool(
                    within_distance(
                        source_root,
                        root,
                        max_distance=12.0,
                        game_map=game_map,
                    )
                )
            elif game_map is not None:
                try:
                    in_range = float(game_map.get_distance_between_units(source_root, root)) <= 12.0 + 1e-6
                except (AttributeError, TypeError, ValueError):
                    in_range = False
            if not in_range:
                continue
            candidates.append(root)
        deduped = []
        seen_ids: set[str] = set()
        for unit in list(candidates):
            unit_id = maybe_entity_id(unit)
            key = str(unit_id or "")
            if key and key in seen_ids:
                continue
            if key:
                seen_ids.add(key)
            deduped.append(unit)
        deduped.sort(key=self._unit_sort_key)
        return deduped

    def get_questor_forgepact_bonded_imperative_sources(self, *, game_map=None) -> list:
        if not self._is_questor_forgepact():
            return []
        sources = []
        for unit in self.get_bondsman_sources():
            root = self._root_unit(unit)
            if root is None or not self._unit_is_imperial_knights_character(root):
                continue
            if self._unit_is_knight_preceptor(root):
                continue
            if self._bondsman_ability_used_for_unit(root):
                continue
            if self._questor_forgepact_bonded_imperative_admech_candidates(root, game_map=game_map):
                sources.append(root)
        sources.sort(key=self._unit_sort_key)
        return sources

    def can_activate_questor_forgepact_bonded_imperative(self, source_unit, *, game_map=None) -> bool:
        if source_unit is None or not self._is_questor_forgepact():
            return False
        source_root = self._root_unit(source_unit)
        if source_root is None:
            return False
        if not self._unit_is_valid_source(source_root):
            return False
        if not self._unit_is_imperial_knights_character(source_root):
            return False
        if self._unit_is_knight_preceptor(source_root):
            return False
        if self._bondsman_ability_used_for_unit(source_root):
            return False
        if self._questor_forgepact_bonded_imperative_pending(source_root):
            return False
        return bool(self._questor_forgepact_bonded_imperative_admech_candidates(source_root, game_map=game_map))

    def _pending_bondsman_request(self, game, source_unit):
        source_id = str(maybe_entity_id(self._root_unit(source_unit)) or "")
        if game is None or not source_id:
            return None
        queue = getattr(game, "decision_queue", None)
        list_fn = getattr(queue, "list", None) if queue is not None else None
        if not callable(list_fn):
            return None
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        except Exception:
            return None
        for req in list(list_fn() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != "bondsman":
                continue
            if str(ctx.get("source_unit_id", "") or "") != source_id:
                continue
            return req
        return None

    def queue_bondsman_selection_request(
        self,
        source_unit,
        *,
        game=None,
        player=None,
        game_map=None,
        refresh: bool = False,
    ):
        if game is None or source_unit is None:
            return None
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest
        except Exception:
            return None
        source_root = self._root_unit(source_unit)
        if source_root is None or not self._unit_is_valid_source(source_root):
            return None
        source_id = maybe_entity_id(source_root)
        if not source_id:
            return None
        existing = self._pending_bondsman_request(game, source_root)
        if existing is not None and not bool(refresh):
            return existing
        queue = getattr(game, "decision_queue", None)
        if existing is not None and bool(refresh) and queue is not None and hasattr(queue, "pop"):
            queue.pop(getattr(existing, "decision_id", None))

        targets = self.get_eligible_armigers(source_root, game_map=game_map)
        target_cap = int(self._bondsman_target_cap(source_root))
        bonded_imperative_active = self._questor_forgepact_bonded_imperative_pending(source_root)
        admech_targets = (
            self._questor_forgepact_bonded_imperative_admech_candidates(source_root, game_map=game_map)
            if bonded_imperative_active
            else []
        )
        options = self._bondsman_target_option_payloads(
            targets,
            max_targets=target_cap,
            admech_targets=admech_targets,
        )
        if not options:
            return None
        req_options = [DecisionOption.create("Skip", payload={"action": "skip"})]
        for label, payload in options:
            req_options.append(DecisionOption.create(label, payload=payload))
        ability_key = self._bondsman_primary_ability_key(source_root)
        candidate_ids = [
            str(maybe_entity_id(target) or "")
            for target in list(targets or [])
            if str(maybe_entity_id(target) or "")
        ]
        candidate_admech_ids = [
            str(maybe_entity_id(target) or "")
            for target in list(admech_targets or [])
            if str(maybe_entity_id(target) or "")
        ]
        prompt = f"Select up to {int(target_cap)} Bondsman target(s)." if int(target_cap) > 1 else "Select Bondsman target."
        if candidate_admech_ids:
            prompt = "Select Bondsman target(s) for this use."
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            prompt,
            player_id=getattr(player, "id", None),
            options=req_options,
            context={
                "source_unit_id": str(source_id),
                "ability": "bondsman",
                "ability_name": "Bondsman",
                "bondsman_ability_key": str(ability_key),
                "max_targets": int(target_cap),
                "candidate_unit_ids": list(candidate_ids),
                "candidate_armiger_unit_ids": list(candidate_ids),
                "candidate_admech_unit_ids": list(candidate_admech_ids),
                "bonded_imperative_active": bool(candidate_admech_ids),
                "optional": True,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(req)
        return req

    def activate_questor_forgepact_bonded_imperative(
        self,
        source_unit,
        *,
        game=None,
        player=None,
        source: str = "BONDED IMPERATIVE",
    ) -> bool:
        source_root = self._root_unit(source_unit)
        if source_root is None or not self.can_activate_questor_forgepact_bonded_imperative(
            source_root,
            game_map=getattr(game, "map", None) if game is not None else None,
        ):
            return False
        sr = getattr(source_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["questor_forgepact_bonded_imperative_pending"] = True
        sr["questor_forgepact_bonded_imperative_source"] = str(source or "BONDED IMPERATIVE").strip() or "BONDED IMPERATIVE"
        sr["questor_forgepact_bonded_imperative_turn"] = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        sr["questor_forgepact_bonded_imperative_turn_owner"] = str(getattr(player, "id", "") or "")
        source_root.special_rules = sr
        if game is not None:
            self.queue_bondsman_selection_request(
                source_root,
                game=game,
                player=player,
                game_map=getattr(game, "map", None),
                refresh=True,
            )
        return True

    def _bondsman_effects_for_unit(self, unit) -> dict:
        effects: dict[str, int | bool] = {}
        for name in self._bondsman_ability_names(unit):
            key = _norm(name).replace(" (bondsman)", "").strip()
            data = _BONDSMAN_EFFECTS.get(key, {})
            for eff_key, value in data.items():
                if isinstance(value, bool):
                    effects[eff_key] = bool(value) or bool(effects.get(eff_key, False))
                else:
                    effects[eff_key] = max(int(value), int(effects.get(eff_key, 0) or 0))
        return effects

    def _quarry_ids_for_unit(self, unit) -> set[str]:
        if unit is None:
            return set()
        quarry_ids: set[str] = set()
        for attr_name in (
            "_bondsman_quarry_ids",
            "_exemplar_of_the_code_quarry_ids",
            "_monarch_of_the_hunt_quarry_ids",
        ):
            values = getattr(unit, attr_name, None)
            if not isinstance(values, (set, list, tuple)):
                continue
            for value in values:
                token = str(value or "").strip()
                if token:
                    quarry_ids.add(token)
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict):
            values = sr.get("bondsman_quarry_ids")
            if isinstance(values, (set, list, tuple)):
                for value in values:
                    token = str(value or "").strip()
                    if token:
                        quarry_ids.add(token)
        return quarry_ids

    def clear_bondsman_effects(self) -> None:
        if self.army is None:
            return
        for unit in list(getattr(self.army, "units", []) or []):
            for attr_name in (
                "_bondsman_quarry_ids",
                "_bondsman_quarry_name",
                "_bondsman_quarry_source_unit_id",
            ):
                if hasattr(unit, attr_name):
                    delattr(unit, attr_name)
            self._clear_questor_forgepact_bonded_imperative(unit)
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not sr:
                continue
            for key in list(sr.keys()):
                if str(key).startswith("bondsman_"):
                    sr.pop(key, None)
            unit.special_rules = sr

    def get_bondsman_sources(self) -> list:
        if not self._army_has_bondsman():
            return []
        sources = []
        for unit in list(getattr(self.army, "units", []) or []):
            if self._unit_is_valid_source(unit):
                sources.append(unit)
        sources.sort(key=self._unit_sort_key)
        return sources

    def get_eligible_armigers(self, source_unit, *, game_map=None, max_distance: float | None = None) -> list:
        if self.army is None or source_unit is None:
            return []
        if not self._unit_is_valid_source(source_unit):
            return []
        source_root = self._root_unit(source_unit)
        distance_limit = float(max_distance) if max_distance is not None else float(self._bondsman_target_range(source_root))
        eligible = []
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._root_unit(unit)
            if not self._unit_is_armiger(root):
                continue
            if root is source_root:
                continue
            try:
                if hasattr(root, "is_alive") and callable(root.is_alive) and not root.is_alive():
                    continue
            except Exception:
                continue
            try:
                if hasattr(root, "deployed") and not bool(getattr(root, "deployed", True)):
                    continue
            except Exception:
                pass
            try:
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("bondsman_active"):
                    continue
            except Exception:
                pass
            if game_map is not None:
                try:
                    dist = float(game_map.get_distance_between_units(source_root, root))
                    if dist > float(distance_limit):
                        continue
                except Exception:
                    pass
            eligible.append(root)
        deduped = []
        seen_ids: set[str] = set()
        for unit in list(eligible):
            unit_id = maybe_entity_id(unit)
            if unit_id:
                key = str(unit_id)
                if key in seen_ids:
                    continue
                seen_ids.add(key)
            deduped.append(unit)
        deduped.sort(key=self._unit_sort_key)
        return deduped

    def _bondsman_target_option_payloads(
        self,
        armiger_targets,
        *,
        max_targets: int,
        admech_targets=None,
    ) -> list[tuple[str, dict]]:
        armiger_entries: list[tuple[str, str, object]] = []
        for target in list(armiger_targets or []):
            target_root = self._root_unit(target)
            target_id = maybe_entity_id(target_root)
            if not target_id:
                continue
            label = str(getattr(target_root, "name", "Unit") or "Unit")
            armiger_entries.append((str(target_id), label, target_root))
        armiger_entries.sort(key=lambda item: self._unit_sort_key(item[2]))
        admech_entries: list[tuple[str, str, object]] = []
        for target in list(admech_targets or []):
            target_root = self._root_unit(target)
            target_id = maybe_entity_id(target_root)
            if not target_id:
                continue
            label = str(getattr(target_root, "name", "Unit") or "Unit")
            admech_entries.append((str(target_id), label, target_root))
        admech_entries.sort(key=lambda item: self._unit_sort_key(item[2]))
        option_payloads: list[tuple[str, dict]] = []
        if armiger_entries:
            select_cap = max(1, min(int(max_targets or 1), len(armiger_entries)))
            for size in range(1, int(select_cap) + 1):
                for combo in combinations(armiger_entries, size):
                    selected_ids = [str(item[0]) for item in combo]
                    selected_names = [str(item[1]) for item in combo]
                    payload = {
                        "target_unit_id": str(selected_ids[0]),
                        "selected_unit_ids": list(selected_ids),
                    }
                    label = selected_names[0] if len(selected_names) == 1 else ", ".join(selected_names)
                    option_payloads.append((label, payload))
                    for admech_id, admech_label, _admech_root in list(admech_entries):
                        combo_ids = list(selected_ids) + [str(admech_id)]
                        combo_names = list(selected_names) + [str(admech_label)]
                        combo_payload = {
                            "target_unit_id": str(combo_ids[0]),
                            "selected_unit_ids": list(combo_ids),
                        }
                        combo_label = ", ".join(combo_names)
                        option_payloads.append((combo_label, combo_payload))
            for admech_id, admech_label, _admech_root in list(admech_entries):
                payload = {
                    "target_unit_id": str(admech_id),
                    "selected_unit_ids": [str(admech_id)],
                }
                option_payloads.append((str(admech_label), payload))
        elif admech_entries:
            for admech_id, admech_label, _admech_root in list(admech_entries):
                payload = {
                    "target_unit_id": str(admech_id),
                    "selected_unit_ids": [str(admech_id)],
                }
                option_payloads.append((str(admech_label), payload))
        return option_payloads

    def validate_bondsman_choice(self, source_unit, selected_unit_ids: list[str], *, game_map=None) -> tuple[bool, str, list]:
        source_root = self._root_unit(source_unit)
        if self.army is None or source_root is None:
            return False, "Bondsman source unit was not found.", []
        if not self._unit_is_valid_source(source_root):
            return False, "Bondsman source unit is not eligible.", []
        selected_ids: list[str] = []
        for value in list(selected_unit_ids or []):
            token = str(value or "").strip()
            if token and token not in selected_ids:
                selected_ids.append(token)
        if not selected_ids:
            return True, "", []
        target_cap = int(self._bondsman_target_cap(source_root))
        eligible_units = self.get_eligible_armigers(source_root, game_map=game_map)
        eligible_by_id = {
            str(unit_id): unit
            for unit in list(eligible_units or [])
            for unit_id in [maybe_entity_id(unit)]
            if unit_id
        }
        bonded_imperative_active = self._questor_forgepact_bonded_imperative_pending(source_root)
        eligible_admech = (
            self._questor_forgepact_bonded_imperative_admech_candidates(source_root, game_map=game_map)
            if bonded_imperative_active
            else []
        )
        eligible_admech_by_id = {
            str(unit_id): unit
            for unit in list(eligible_admech or [])
            for unit_id in [maybe_entity_id(unit)]
            if unit_id
        }
        armiger_count = 0
        admech_count = 0
        resolved_targets = []
        for unit_id in list(selected_ids):
            target = eligible_by_id.get(str(unit_id))
            if target is not None:
                armiger_count += 1
                resolved_targets.append(target)
                continue
            target = eligible_admech_by_id.get(str(unit_id))
            if target is None:
                return False, "Bondsman selection contains an ineligible target.", []
            admech_count += 1
            resolved_targets.append(target)
        max_total = int(target_cap + (1 if bonded_imperative_active else 0))
        if armiger_count > max(1, target_cap):
            if target_cap >= 3:
                return False, "Bondsman selection cannot exceed three friendly Armiger units.", []
            return False, "That Bondsman ability can only target one Armiger after it has already been used this turn.", []
        if admech_count > (1 if bonded_imperative_active else 0):
            return False, "Bonded Imperative can only add one friendly Adeptus Mechanicus unit.", []
        if len(resolved_targets) > max(1, max_total):
            return False, "Bonded Imperative selection exceeds the allowed number of targets.", []
        return True, "", resolved_targets

    def validate_bondsman_payload(self, source_unit, payload: dict | None, *, game_map=None) -> tuple[bool, str, list]:
        selected_ids = self._selected_target_ids_from_payload(payload)
        return self.validate_bondsman_choice(source_unit, selected_ids, game_map=game_map)

    def apply_bondsman_payload(self, source_unit, payload: dict | None, *, game_map=None) -> tuple[bool, str, list]:
        valid, reason, targets = self.validate_bondsman_payload(source_unit, payload, game_map=game_map)
        if not valid:
            return False, str(reason), []
        if not targets:
            return True, "", []
        applied_targets = []
        for target in list(targets):
            if self.apply_bondsman_effects(source_unit, target):
                applied_targets.append(target)
        if not applied_targets:
            return False, "Bondsman effects could not be applied.", []
        self._mark_bondsman_ability_used(source_unit)
        self._clear_questor_forgepact_bonded_imperative(source_unit)
        return True, "", list(applied_targets)

    def apply_bondsman_effects(self, source_unit, target_unit) -> bool:
        if source_unit is None or target_unit is None:
            return False
        effects = self._bondsman_effects_for_unit(source_unit)
        if not effects:
            return False
        sr = getattr(target_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["bondsman_active"] = True
        sr["bondsman_source_name"] = str(getattr(source_unit, "name", "") or "")
        source_unit_id = maybe_entity_id(source_unit)
        if source_unit_id:
            sr["bondsman_source_unit_id"] = str(source_unit_id)
        sr["bondsman_ability_names"] = list(self._bondsman_ability_names(source_unit))
        if effects.get("lethal_hits"):
            sr["bondsman_lethal_hits"] = True
        if effects.get("lance"):
            sr["bondsman_lance"] = True
        if effects.get("reroll_advance"):
            sr["bondsman_reroll_advance"] = True
        if effects.get("assault_ranged"):
            sr["bondsman_assault_ranged"] = True
        if effects.get("sustained_hits"):
            sr["bondsman_sustained_hits"] = int(effects.get("sustained_hits", 1) or 1)
        if effects.get("sustained_hits_ranged"):
            sr["bondsman_sustained_hits_ranged"] = int(effects.get("sustained_hits_ranged", 1) or 1)
        if effects.get("ignores_cover_ranged"):
            sr["bondsman_ignores_cover_ranged"] = True
        if effects.get("reroll_charge"):
            sr["bondsman_reroll_charge"] = True
        if effects.get("reroll_hit_melee"):
            sr["bondsman_reroll_hit_melee"] = True
        if effects.get("ranged_hit_bonus"):
            sr["bondsman_ranged_hit_bonus"] = int(effects.get("ranged_hit_bonus", 1) or 1)
        if effects.get("acheron_battleshock"):
            sr["bondsman_acheron_battleshock"] = True
        if effects.get("reroll_hit_wound_vs_titanic"):
            sr["bondsman_reroll_hit_wound_vs_titanic"] = True
        if effects.get("ap_bonus_ranged"):
            sr["bondsman_ap_bonus_ranged"] = int(effects.get("ap_bonus_ranged", 1) or 1)
        if effects.get("charge_after_advance"):
            sr["bondsman_charge_after_advance"] = True
        if effects.get("magaera_bonus"):
            sr["bondsman_magaera_bonus"] = True
        if effects.get("styrix_battleshock"):
            sr["bondsman_styrix_battleshock"] = True
        if effects.get("reroll_wound_vs_quarry"):
            sr["bondsman_reroll_wound_vs_quarry"] = True
            quarry_ids = self._quarry_ids_for_unit(source_unit)
            if quarry_ids:
                setattr(target_unit, "_bondsman_quarry_ids", set(quarry_ids))
                sr["bondsman_quarry_ids"] = sorted(quarry_ids)
                if source_unit_id:
                    setattr(target_unit, "_bondsman_quarry_source_unit_id", str(source_unit_id))
                quarry_name = str(getattr(source_unit, "_bondsman_quarry_name", "") or "").strip()
                if quarry_name:
                    setattr(target_unit, "_bondsman_quarry_name", quarry_name)
                    sr["bondsman_quarry_name"] = quarry_name
        if effects.get("damage_reduction"):
            sr["bondsman_damage_reduction"] = int(effects.get("damage_reduction", 1) or 1)
        target_unit.special_rules = sr
        return True

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        self.clear_bondsman_effects()
        self._used_bondsman_ability_keys.clear()
        if not self._army_has_bondsman():
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if player is None and self.army is not None:
            player = getattr(self.army, "player", None)
        try:
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        except Exception:
            return
        for source in self.get_bondsman_sources():
            source_root = self._root_unit(source)
            targets = self.get_eligible_armigers(source_root, game_map=game_map)
            has_bonded_imperative_window = bool(
                self._questor_forgepact_bonded_imperative_admech_candidates(source_root, game_map=game_map)
            )
            if not targets and not has_bonded_imperative_window:
                continue
            target_cap = int(self._bondsman_target_cap(source_root))
            if len(targets) == 1 and not has_bonded_imperative_window:
                if self.apply_bondsman_effects(source_root, targets[0]):
                    self._mark_bondsman_ability_used(source_root)
                continue
            source_id = maybe_entity_id(source_root)
            if not source_id:
                continue
            existing = self._pending_bondsman_request(game, source_root)
            if existing is not None:
                continue
            self.queue_bondsman_selection_request(
                source_root,
                game=game,
                player=player,
                game_map=game_map,
            )

    def on_fight_phase_start(self, *, game=None) -> None:
        if self.army is None:
            return
        sources = []
        for unit in list(getattr(self.army, "units", []) or []):
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bondsman_acheron_battleshock"):
                sources.append(unit)
        if not sources:
            return
        try:
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
        if game_map is None:
            return
        affected = set()
        for source in sources:
            try:
                enemies = list(game_map.get_enemy_units(source) or [])
            except Exception:
                enemies = []
            for enemy in enemies:
                try:
                    if not enemy.is_alive():
                        continue
                except Exception:
                    continue
                try:
                    if not game_map.is_within_engagement_range(source, enemy):
                        continue
                except Exception:
                    continue
                key = get_entity_id(enemy)
                if key in affected:
                    continue
                affected.add(key)
                self._apply_battleshock(enemy, game=game, modifier=-1)

    def on_unit_shooting_resolved(self, attacker_unit=None, hits_by_target=None, *, game=None) -> None:
        if attacker_unit is None:
            return
        try:
            sr = getattr(attacker_unit, "special_rules", None)
            if not (isinstance(sr, dict) and sr.get("bondsman_styrix_battleshock")):
                return
        except Exception:
            return
        if not hits_by_target:
            return
        options = []
        for unit, hits in list(hits_by_target.items()):
            try:
                if int(hits or 0) <= 0:
                    continue
            except Exception:
                continue
            options.append((unit, int(hits or 0)))
        if not options:
            return
        options.sort(key=lambda pair: (-pair[1], str(getattr(pair[0], "name", ""))))
        target = options[0][0]
        self._apply_battleshock(target, game=game, modifier=-1)

    def on_fight_sequence_complete(self, unit=None, *, game=None) -> None:
        if unit is None:
            return
        try:
            sr = getattr(unit, "special_rules", None)
            if not (isinstance(sr, dict) and sr.get("bondsman_styrix_battleshock")):
                return
        except Exception:
            return
        targets = []
        try:
            targets = list(getattr(unit.round_state, "last_fight_targets", []) or [])
        except Exception:
            targets = list(getattr(unit, "_last_fight_targets", []) or [])
        if not targets:
            return
        target = targets[0]
        self._apply_battleshock(target, game=game, modifier=-1)

    def _apply_battleshock(self, unit, *, game=None, modifier: int = 0) -> None:
        if unit is None:
            return
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current = int(sr.get("battle_shock_test_modifier", 0) or 0)
        sr["battle_shock_test_modifier"] = current + int(modifier or 0)
        unit.special_rules = sr
        try:
            battle_round = int(getattr(game, "turn", 0) or 0)
        except Exception:
            battle_round = 1
        try:
            unit.take_battle_shock_test(battle_round)
        except Exception:
            return
