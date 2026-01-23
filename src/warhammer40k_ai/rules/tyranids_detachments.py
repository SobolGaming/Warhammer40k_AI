from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .detachment_manager import DetachmentManagerBase


@dataclass(frozen=True)
class HyperAdaptation:
    key: str
    name: str
    summary: str
    target_keywords: tuple[str, ...]
    sustained_hits_value: int = 0
    lethal_hits: bool = False
    precision_on_crit: bool = False


SWARMING_INSTINCTS = HyperAdaptation(
    key="SWARMING_INSTINCTS",
    name="Swarming Instincts",
    summary="Attacks vs INFANTRY or SWARM gain Sustained Hits 1.",
    target_keywords=("INFANTRY", "SWARM"),
    sustained_hits_value=1,
)
HYPER_AGGRESSION = HyperAdaptation(
    key="HYPER_AGGRESSION",
    name="Hyper-aggression",
    summary="Attacks vs MONSTER or VEHICLE gain Lethal Hits.",
    target_keywords=("MONSTER", "VEHICLE"),
    lethal_hits=True,
)
HIVE_PREDATORS = HyperAdaptation(
    key="HIVE_PREDATORS",
    name="Hive Predators",
    summary="On critical hits vs CHARACTER units, attacks gain Precision.",
    target_keywords=("CHARACTER",),
    precision_on_crit=True,
)

HYPER_ADAPTATIONS: tuple[HyperAdaptation, ...] = (
    SWARMING_INSTINCTS,
    HYPER_AGGRESSION,
    HIVE_PREDATORS,
)
HYPER_ADAPTATION_BY_KEY = {h.key: h for h in HYPER_ADAPTATIONS}


class TyranidsDetachmentManager(DetachmentManagerBase):
    faction_id = "TYR"

    def __init__(self, army=None):
        super().__init__(army)
        self.active_hyper_adaptation_key: Optional[str] = None
        self.hyper_adaptation_selected_round: Optional[int] = None

    def is_invasion_fleet(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Invasion Fleet")

    def _army_has_hyper_adaptations(self) -> bool:
        return self.is_invasion_fleet()

    def _unit_is_tyranids(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword_or_faction(unit, "TYRANIDS", faction_id=self.faction_id)

    def get_available_hyper_adaptations(self) -> list[HyperAdaptation]:
        if not self._army_has_hyper_adaptations():
            return []
        return list(HYPER_ADAPTATIONS)

    def get_active_hyper_adaptation(self, *, game=None) -> Optional[HyperAdaptation]:
        if not self._army_has_hyper_adaptations():
            return None
        if not self.active_hyper_adaptation_key:
            return None
        return HYPER_ADAPTATION_BY_KEY.get(str(self.active_hyper_adaptation_key).strip().upper())

    def get_active_hyper_adaptation_for_unit(self, unit, *, game=None) -> Optional[HyperAdaptation]:
        if unit is None:
            return None
        if not self._army_has_hyper_adaptations():
            return None
        if not self.active_hyper_adaptation_key:
            return None
        if not self._unit_is_tyranids(unit):
            return None
        army = self.army
        try:
            if army is not None and hasattr(unit, "get_parent_army"):
                if unit.get_parent_army() is not army:
                    return None
        except Exception:
            return None
        return HYPER_ADAPTATION_BY_KEY.get(str(self.active_hyper_adaptation_key).strip().upper())

    def can_select_hyper_adaptation(self, *, game=None, battle_round: Optional[int] = None) -> bool:
        if not self._army_has_hyper_adaptations():
            return False
        if self.active_hyper_adaptation_key:
            return False
        br = None
        if battle_round is not None:
            try:
                br = int(battle_round)
            except Exception:
                br = None
        if br is None and game is not None:
            try:
                br = int(getattr(game, "turn", 0) or 0)
            except Exception:
                br = None
        if br is None:
            return False
        return br == 1

    def select_hyper_adaptation(self, adaptation, *, battle_round: Optional[int] = None) -> bool:
        if not self._army_has_hyper_adaptations():
            return False
        key = getattr(adaptation, "key", adaptation)
        key = str(key or "").strip().upper()
        if key not in HYPER_ADAPTATION_BY_KEY:
            return False
        if self.active_hyper_adaptation_key:
            return False
        self.active_hyper_adaptation_key = key
        if battle_round is not None:
            try:
                self.hyper_adaptation_selected_round = int(battle_round)
            except Exception:
                pass
        return True

    def _pending_hyper_adaptation_request(self, game, army_id: str):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_HYPER_ADAPTATION":
                continue
            ctx = getattr(req, "context", {}) or {}
            if str(ctx.get("army_id", "")) == str(army_id):
                return req
        return None

    def _build_hyper_adaptation_request(self, game, player, battle_round: int):
        if game is None:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_HYPER_ADAPTATION
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        army = self.army
        army_id = get_entity_id(army) if army is not None else None
        options = []
        for opt in self.get_available_hyper_adaptations():
            key = getattr(opt, "key", None)
            if not key:
                continue
            name = getattr(opt, "name", None) or str(opt)
            summary = getattr(opt, "summary", "") or getattr(opt, "effect", "")
            options.append(
                DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "summary": summary, "army_id": army_id},
                )
            )
        if not options:
            return None
        return DecisionRequest.create(
            DECISION_CHOOSE_HYPER_ADAPTATION,
            "Select Hyper-adaptation.",
            player_id=getattr(player, "id", None),
            options=options,
            context={"army_id": army_id, "battle_round": int(battle_round)},
        )

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self._army_has_hyper_adaptations():
            return
        try:
            br = int(battle_round or 0)
        except Exception:
            return
        if br != 1:
            return
        if self.active_hyper_adaptation_key:
            return

        player = None
        try:
            player = getattr(self.army, "player", None)
        except Exception:
            player = None

        if game is None:
            options = [opt.name for opt in self.get_available_hyper_adaptations()]
            if not options or player is None:
                return
            ctx = {"ability": "Hyper-adaptations", "options": list(options)}
            choice = None
            try:
                choice = player._choose_optional_value("HYPER_ADAPTATIONS", options, ctx)
            except Exception:
                choice = None
            selected = None
            if choice in self.get_available_hyper_adaptations():
                selected = choice
            elif isinstance(choice, str):
                choice_norm = choice.strip().lower()
                for opt in self.get_available_hyper_adaptations():
                    if opt.name.strip().lower() == choice_norm or opt.key.strip().lower() == choice_norm:
                        selected = opt
                        break
            if selected is not None:
                self.select_hyper_adaptation(selected, battle_round=br)
            return

        from ..utility.entity_ids import get_entity_id

        army_id = get_entity_id(self.army) if self.army is not None else None
        if self._pending_hyper_adaptation_request(game, army_id):
            return
        request = self._build_hyper_adaptation_request(game, player, br)
        if request is None:
            return
        if hasattr(game, "request_decision"):
            game.request_decision(request)
