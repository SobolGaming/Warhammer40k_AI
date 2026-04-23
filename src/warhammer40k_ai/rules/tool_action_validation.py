from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..engine.decision_handlers._helpers import resolve_entity


_ENTITY_FALLBACK_KINDS = ("unit", "model", "objective", "terrain", "player", "army", "wargear")


@dataclass(frozen=True)
class ToolActionValidationIssue:
    code: str
    message: str
    missing_keys: tuple[str, ...] = ()
    severity: str = "WARNING"


@dataclass(frozen=True)
class ToolActionSpecValidation:
    kwargs: dict[str, Any]
    issues: tuple[ToolActionValidationIssue, ...]


class ToolActionCandidateValidator:
    """Shared legality firewall for generic stratagem tool-action candidates."""

    def __init__(self, manager: object) -> None:
        self.manager = manager

    def with_phase_name(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        probe = dict(kwargs or {})
        if not str(probe.get("phase_name", "") or "").strip():
            resolved_phase_name = self._resolved_phase_name()
            if resolved_phase_name:
                probe["phase_name"] = resolved_phase_name
        return probe

    def validate_probe(self, stratagem: object, kwargs: dict[str, Any]) -> ToolActionSpecValidation:
        probe = self.with_phase_name(kwargs)
        issues: list[ToolActionValidationIssue] = []

        missing = self._missing_required_bindings(stratagem, probe)
        if missing:
            issues.append(
                ToolActionValidationIssue(
                    code="missing_tool_action_context",
                    message="Tool action candidate is missing required context.",
                    missing_keys=tuple(missing),
                )
            )
            return ToolActionSpecValidation(kwargs=probe, issues=tuple(issues))

        descriptor_issue = self._descriptor_filter_issue(stratagem, probe)
        if descriptor_issue is not None:
            issues.append(descriptor_issue)
            return ToolActionSpecValidation(kwargs=probe, issues=tuple(issues))

        can_use = getattr(self.manager, "can_use", None)
        if callable(can_use):
            tool_name = str(getattr(stratagem, "name", "") or "")
            if not bool(can_use(tool_name, **probe)):
                issues.append(
                    ToolActionValidationIssue(
                        code="illegal_tool_candidate_filtered_preflight",
                        message="Tool action candidate failed manager.can_use preflight.",
                        missing_keys=("can_use",),
                    )
                )
        return ToolActionSpecValidation(kwargs=probe, issues=tuple(issues))

    def validate_serialized_payload(self, stratagem: object, payload: dict[str, Any]) -> ToolActionSpecValidation:
        raw_kwargs = dict(payload or {}).get("resolved_kwargs")
        if not isinstance(raw_kwargs, dict):
            return ToolActionSpecValidation(
                kwargs={},
                issues=(
                    ToolActionValidationIssue(
                        code="malformed_tool_candidate_filtered_preflight",
                        message="Tool action payload missing resolved_kwargs.",
                        missing_keys=("resolved_kwargs",),
                        severity="ERROR",
                    ),
                ),
            )

        if self._contains_entity_ref(raw_kwargs) and not self._can_resolve_entity_refs():
            return ToolActionSpecValidation(kwargs=dict(raw_kwargs), issues=())

        resolved_kwargs, unresolved = self._resolve_serialized_value(raw_kwargs, path="resolved_kwargs")
        if unresolved:
            return ToolActionSpecValidation(
                kwargs=resolved_kwargs if isinstance(resolved_kwargs, dict) else {},
                issues=(
                    ToolActionValidationIssue(
                        code="malformed_tool_candidate_filtered_preflight",
                        message="Tool action payload contains unresolvable entity references.",
                        missing_keys=tuple(sorted(set(unresolved))),
                        severity="ERROR",
                    ),
                ),
            )
        if not isinstance(resolved_kwargs, dict):
            return ToolActionSpecValidation(
                kwargs={},
                issues=(
                    ToolActionValidationIssue(
                        code="malformed_tool_candidate_filtered_preflight",
                        message="Tool action resolved_kwargs did not resolve to a mapping.",
                        missing_keys=("resolved_kwargs",),
                        severity="ERROR",
                    ),
                ),
            )
        return self.validate_probe(stratagem, resolved_kwargs)

    def _resolved_phase_name(self) -> str:
        resolved = getattr(self.manager, "_resolved_phase_name", None)
        if callable(resolved):
            return str(resolved() or "")
        return str(getattr(self.manager, "_current_phase_name", "") or "")

    def _missing_required_bindings(self, stratagem: object, kwargs: dict[str, Any]) -> list[str]:
        missing_fn = getattr(self.manager, "_tool_action_missing_required_bindings", None)
        if not callable(missing_fn):
            return []
        return sorted(str(key) for key in list(missing_fn(stratagem, kwargs) or []) if str(key or "").strip())

    def _descriptor_filter_issue(self, stratagem: object, kwargs: dict[str, Any]) -> ToolActionValidationIssue | None:
        descriptor = getattr(stratagem, "tool_descriptor", None)
        target_text = str(getattr(descriptor, "target", "") or "").strip().lower()
        if not target_text:
            return None

        unit = self._target_unit_for_descriptor(target_text, kwargs)
        if unit is None:
            return None
        root = self._unit_root(unit)

        if "world_eaters_possessed" in target_text:
            if not self._unit_has_all_keywords(root, ("WORLD EATERS", "POSSESSED")):
                return self._descriptor_issue("unit_keywords")
        if "aspect_warriors_or_avatar" in target_text:
            if not self._unit_has_any_keyword(root, ("ASPECT WARRIORS", "AVATAR OF KHAINE")):
                return self._descriptor_issue("unit_keywords")
        elif "aspect_warriors" in target_text:
            if not self._unit_has_any_keyword(root, ("ASPECT WARRIORS",)):
                return self._descriptor_issue("unit_keywords")
        if "avatar_of_khaine" in target_text or target_text.startswith("avatar_"):
            if not self._unit_has_any_keyword(root, ("AVATAR OF KHAINE",)):
                return self._descriptor_issue("unit_keywords")
        if "legiones_daemonica" in target_text:
            if not self._unit_has_any_keyword(root, ("LEGIONES DAEMONICA",)):
                return self._descriptor_issue("unit_keywords")
        if "arriving_from_deep_strike" in target_text:
            if not self._unit_is_in_reserves(root) or not self._unit_has_deep_strike(root):
                return self._descriptor_issue("deep_strike_arrival")
        if "not_in_engagement_range" in target_text or "not_within_engagement_range" in target_text:
            if self._unit_is_in_engagement_range(root):
                return self._descriptor_issue("not_in_engagement_range")
        elif "engagement_range" in target_text and not self._unit_is_in_engagement_range(root):
            return self._descriptor_issue("engagement_range")

        phase_name = str(kwargs.get("phase_name") or self._resolved_phase_name() or "").strip().lower()
        round_state = getattr(root, "round_state", None)
        if "not_yet_shot" in target_text and bool(
            getattr(round_state, "shot_this_phase", False) or getattr(round_state, "shot_this_round", False)
        ):
            return self._descriptor_issue("not_yet_shot")
        if "not_yet_fought" in target_text and self._unit_has_fought(root):
            return self._descriptor_issue("not_yet_fought")
        if "not_yet_selected" in target_text:
            if phase_name == "shooting phase" and bool(
                getattr(round_state, "shot_this_phase", False) or getattr(round_state, "shot_this_round", False)
            ):
                return self._descriptor_issue("not_yet_selected")
            if phase_name == "fight phase" and self._unit_has_fought(root):
                return self._descriptor_issue("not_yet_selected")
            if phase_name == "movement phase" and bool(getattr(round_state, "moved_this_round", False)):
                return self._descriptor_issue("not_yet_selected")
            if phase_name == "charge phase" and bool(getattr(round_state, "attempted_charge_this_round", False)):
                return self._descriptor_issue("not_yet_selected")
        return None

    @staticmethod
    def _descriptor_issue(reason_key: str) -> ToolActionValidationIssue:
        return ToolActionValidationIssue(
            code="illegal_tool_candidate_filtered_preflight",
            message="Tool action candidate failed descriptor-derived eligibility preflight.",
            missing_keys=(reason_key,),
        )

    @staticmethod
    def _target_unit_for_descriptor(target_text: str, kwargs: dict[str, Any]) -> Any:
        if "enemy_unit" in target_text or "attacker_unit" in target_text:
            return kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit") or kwargs.get("attacker_unit")
        unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("source_unit")
        if unit is not None:
            return unit
        model = kwargs.get("model") or kwargs.get("target_model")
        return getattr(model, "parent_unit", None)

    @staticmethod
    def _unit_root(unit: Any) -> Any:
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
            if root is not None:
                return root
        return unit

    @staticmethod
    def _unit_has_any_keyword(unit: Any, keywords: tuple[str, ...]) -> bool:
        for keyword in keywords:
            if ToolActionCandidateValidator._unit_has_keyword(unit, keyword):
                return True
        return False

    @staticmethod
    def _unit_has_all_keywords(unit: Any, keywords: tuple[str, ...]) -> bool:
        return all(ToolActionCandidateValidator._unit_has_keyword(unit, keyword) for keyword in keywords)

    @staticmethod
    def _unit_has_keyword(unit: Any, keyword: str) -> bool:
        wanted = str(keyword or "").strip().upper()
        if not wanted:
            return False
        for method_name in ("has_keyword", "has_any_keyword"):
            checker = getattr(unit, method_name, None)
            if callable(checker) and bool(checker(wanted)):
                return True
        values: list[Any] = []
        for attr_name in ("keywords", "faction_keywords", "keyword", "faction_keyword"):
            raw = getattr(unit, attr_name, None)
            if isinstance(raw, str):
                values.append(raw)
            else:
                values.extend(list(raw or []))
        normalized = {str(value or "").strip().upper() for value in values if str(value or "").strip()}
        return wanted in normalized

    @staticmethod
    def _unit_is_in_reserves(unit: Any) -> bool:
        checker = getattr(unit, "is_in_reserves", None)
        if callable(checker) and bool(checker()):
            return True
        reserve_status = str(getattr(unit, "reserve_status", "") or "").strip().lower()
        return reserve_status in {"reserves", "strategic_reserves", "deep_strike"}

    def _unit_is_in_engagement_range(self, unit: Any) -> bool:
        game = getattr(self.manager, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(is_within_engagement):
            return False
        try:
            enemies = list(get_enemy_units(root) or [])
        except (AttributeError, TypeError, ValueError):
            enemies = []
        for enemy in enemies:
            enemy_root = self._unit_root(enemy)
            if enemy_root is None:
                continue
            if not self._unit_is_on_battlefield(enemy_root):
                continue
            try:
                if bool(is_within_engagement(root, enemy_root)):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    @staticmethod
    def _unit_is_on_battlefield(unit: Any) -> bool:
        if unit is None:
            return False
        alive = getattr(unit, "is_alive", None)
        if callable(alive):
            try:
                if not bool(alive()):
                    return False
            except (AttributeError, TypeError, ValueError):
                return False
        if bool(getattr(unit, "is_embarked", False)) or getattr(unit, "embarked_in", None) is not None:
            return False
        if getattr(unit, "deployed", True) is False:
            return False
        reserve_status = str(getattr(unit, "reserve_status", "deployed") or "deployed").strip().lower()
        return reserve_status == "deployed"

    @staticmethod
    def _unit_has_deep_strike(unit: Any) -> bool:
        checker = getattr(unit, "has_deep_strike", None)
        if callable(checker) and bool(checker()):
            return True
        special_rules = dict(getattr(unit, "special_rules", {}) or {})
        if any("deep_strike" in str(key or "").lower() and bool(value) for key, value in special_rules.items()):
            return True
        return ToolActionCandidateValidator._unit_has_keyword(unit, "DEEP STRIKE")

    def _unit_has_fought(self, unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        if bool(getattr(round_state, "fought_this_phase", False) or getattr(round_state, "fought_this_round", False)):
            return True
        game = getattr(self.manager, "game", None)
        fight_mgr = getattr(game, "fight_phase_manager", None) if game is not None else None
        fought_units = getattr(fight_mgr, "fought_units", set()) if fight_mgr is not None else set()
        for fought_unit in list(fought_units or []):
            if fought_unit is unit or fought_unit == unit:
                return True
        return False

    def _can_resolve_entity_refs(self) -> bool:
        game = getattr(self.manager, "game", None)
        if game is None:
            return False
        if getattr(game, "entity_registry", None) is not None:
            return True
        if getattr(game, "players", None):
            return True
        game_map = getattr(game, "map", None)
        if getattr(game_map, "objectives", None) or getattr(game_map, "terrain_features", None):
            return True
        return bool(getattr(game, "objectives", None))

    def _resolve_serialized_value(self, value: Any, *, path: str) -> tuple[Any, list[str]]:
        if isinstance(value, dict):
            enum_ref = value.get("__enum_ref__")
            if isinstance(enum_ref, dict):
                return enum_ref.get("value"), []
            entity_ref = value.get("__entity_ref__")
            if isinstance(entity_ref, dict):
                entity_id = str(entity_ref.get("id", "") or "")
                entity_kind = str(entity_ref.get("kind", "") or "").strip().lower()
                if not entity_id:
                    return None, [path]
                resolved = self._resolve_entity_ref(entity_id, entity_kind)
                if resolved is None:
                    return None, [path]
                return resolved, []
            resolved_dict: dict[str, Any] = {}
            unresolved: list[str] = []
            for key, item in value.items():
                child, child_unresolved = self._resolve_serialized_value(item, path=f"{path}.{key}")
                resolved_dict[str(key)] = child
                unresolved.extend(child_unresolved)
            return resolved_dict, unresolved
        if isinstance(value, list):
            resolved_list: list[Any] = []
            unresolved: list[str] = []
            for idx, item in enumerate(value):
                child, child_unresolved = self._resolve_serialized_value(item, path=f"{path}[{idx}]")
                resolved_list.append(child)
                unresolved.extend(child_unresolved)
            return resolved_list, unresolved
        return value, []

    def _resolve_entity_ref(self, entity_id: str, entity_kind: str) -> Any:
        game = getattr(self.manager, "game", None)
        if game is None:
            return None
        kinds: list[str] = []
        if entity_kind:
            kinds.append(entity_kind)
        for fallback_kind in _ENTITY_FALLBACK_KINDS:
            if fallback_kind not in kinds:
                kinds.append(fallback_kind)
        for kind in kinds:
            resolved = resolve_entity(game, entity_id, kind=kind)
            if resolved is not None:
                return resolved
        return None

    @classmethod
    def _contains_entity_ref(cls, value: Any) -> bool:
        if isinstance(value, dict):
            if isinstance(value.get("__entity_ref__"), dict):
                return True
            return any(cls._contains_entity_ref(item) for item in value.values())
        if isinstance(value, list):
            return any(cls._contains_entity_ref(item) for item in value)
        return False
