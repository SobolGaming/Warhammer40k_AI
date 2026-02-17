from __future__ import annotations

from typing import Any, Optional
import logging

from ..utility.entity_ids import maybe_entity_id

logger = logging.getLogger(__name__)


class ImperialKnightsStratagemMixin:
    @staticmethod
    def _ik_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _ik_sort_key(unit: Any) -> str:
        return str(maybe_entity_id(unit) or "")

    def _ik_detachment_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "imperial_knights_detachments", None)

    def _is_valourstrike_lance(self) -> bool:
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "is_valourstrike_lance", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _ik_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _ik_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _ik_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return True
        checker = getattr(unit, "is_in_reserves", None)
        if callable(checker):
            return bool(checker())
        return bool(getattr(unit, "is_in_reserves", False))

    def _ik_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._ik_is_in_reserves(root):
            return False
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
            return False
        if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return True

    def _is_imperial_knights_unit(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        if root is None:
            return False
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "_unit_is_imperial_knights", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if callable(has_any_keyword):
            return bool(has_any_keyword("IMPERIAL KNIGHTS"))
        return str(getattr(root, "faction_id", "") or "").strip().upper() == "QI"

    def _imperial_knights_vow_of_retribution_candidates(self) -> list[Any]:
        if not self._is_valourstrike_lance():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _ik_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            preview = apply_fn(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return bool(
            self.player.spend_command_points(
                int(cp_cost),
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Unknown')}",
                source="stratagem",
            )
        )

    def _ik_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u:
                used.add(name_u)

    def _use_imperial_knights_valourstrike_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "VOW OF RETRIBUTION":
            return self._use_valourstrike_vow_of_retribution(stratagem, **kwargs)
        return None

    def _use_valourstrike_vow_of_retribution(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: VOW OF RETRIBUTION: wrong phase")
            return False

        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: VOW OF RETRIBUTION: not your Shooting phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: VOW OF RETRIBUTION: no target unit provided")
            return False

        root = self._ik_root(unit)
        if root is None:
            return False

        candidates = self._imperial_knights_vow_of_retribution_candidates()
        if root not in candidates:
            logger.error(
                "ERROR: VOW OF RETRIBUTION: target must be an IMPERIAL KNIGHTS unit on the battlefield that has not shot"
            )
            return False

        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["vow_of_retribution_active"] = True
        sr["vow_of_retribution_expires_phase"] = "SHOOTING_PHASE"
        sr["vow_of_retribution_owner"] = str(getattr(self.player, "id", "") or "")
        sr["vow_of_retribution_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["vow_of_retribution_source"] = str(getattr(stratagem, "name", "") or "VOW OF RETRIBUTION")
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            f"INFO: VOW OF RETRIBUTION: {getattr(root, 'name', 'Unit')} gains Lethal Hits with ranged weapons this phase."
        )
        return True
