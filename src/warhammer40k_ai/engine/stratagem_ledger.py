from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


_TARGET_TRACKERS = {
    "COMMAND RE-ROLL": "_command_reroll_units_this_phase",
    "GRENADE": "_grenade_units_this_phase",
    "HEROIC INTERVENTION": "_heroic_intervention_units_this_phase",
    "RAPID INGRESS": "_rapid_ingress_units_this_phase",
}


def _normalize_name(name: str) -> str:
    return str(name or "").strip().upper()


@dataclass(frozen=True)
class StratagemApplicationLedger:
    manager: object

    def phase_name(self) -> str:
        return str(getattr(self.manager, "_current_phase_name", "") or "").strip()

    def used_names_this_phase(self) -> set[str]:
        raw = getattr(self.manager, "_used_stratagems_this_phase", set()) or set()
        return {_normalize_name(value) for value in set(raw or []) if _normalize_name(value)}

    def already_used_this_phase(self, stratagem_name: str) -> bool:
        return _normalize_name(stratagem_name) in self.used_names_this_phase()

    def target_tracker_attr(self, stratagem_name: str) -> str:
        return str(_TARGET_TRACKERS.get(_normalize_name(stratagem_name), "") or "")

    def targets_used_this_phase(self, stratagem_name: str) -> set[str]:
        attr = self.target_tracker_attr(stratagem_name)
        if not attr:
            return set()
        raw = getattr(self.manager, attr, set()) or set()
        return {str(value or "").strip() for value in set(raw or []) if str(value or "").strip()}

    def target_already_used_this_phase(self, stratagem_name: str, unit_id: str) -> bool:
        token = str(unit_id or "").strip()
        if not token:
            return False
        return token in self.targets_used_this_phase(stratagem_name)

    def any_target_available(self, stratagem_name: str, candidate_ids: Iterable[str]) -> bool:
        used = self.targets_used_this_phase(stratagem_name)
        for candidate_id in list(candidate_ids or []):
            token = str(candidate_id or "").strip()
            if token and token not in used:
                return True
        return False

    def mark_used_this_phase(self, stratagem_name: str) -> None:
        key = _normalize_name(stratagem_name)
        if not key:
            return
        used = getattr(self.manager, "_used_stratagems_this_phase", None)
        if not isinstance(used, set):
            used = set()
            setattr(self.manager, "_used_stratagems_this_phase", used)
        used.add(key)

    def mark_target_used_this_phase(self, stratagem_name: str, unit_id: str) -> None:
        token = str(unit_id or "").strip()
        attr = self.target_tracker_attr(stratagem_name)
        if not token or not attr:
            return
        used = getattr(self.manager, attr, None)
        if not isinstance(used, set):
            used = set()
            setattr(self.manager, attr, used)
        used.add(token)
