from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utility.ability_support import ABILITY_NURGLES_GIFT, army_has_ability_id
from ..utility.aura_effects import nurgles_gift_contagion_range
from ..utility.entity_ids import get_entity_id


@dataclass(frozen=True)
class NurglesPlague:
    key: str
    name: str
    summary: str


PLAGUE_SKULLSQUIRM = NurglesPlague(
    key="SKULLSQUIRM_BLIGHT",
    name="Skullsquirm Blight",
    summary="Afflicted units suffer -1 to Hit rolls.",
)
PLAGUE_RATTLEJOINT = NurglesPlague(
    key="RATTLEJOINT_AGUE",
    name="Rattlejoint Ague",
    summary="Afflicted units worsen their Save characteristic by 1.",
)
PLAGUE_SCABROUS = NurglesPlague(
    key="SCABROUS_SOULROT",
    name="Scabrous Soulrot",
    summary="Afflicted units worsen Move, Leadership, and OC by 1 (OC min 1).",
)

DEFAULT_PLAGUES: tuple[NurglesPlague, ...] = (
    PLAGUE_SKULLSQUIRM,
    PLAGUE_RATTLEJOINT,
    PLAGUE_SCABROUS,
)


class NurglesGiftManager:
    """
    Death Guard army rule: Nurgle's Gift (Aura) + selected Plague.
    """

    def __init__(self, army=None):
        self.army = army
        self.active_plague_key: Optional[str] = None
        self.plaguesurge_active: bool = False
        self.plaguesurge_bonus: int = 0
        self.plaguesurge_owner: str = ""
        self.plaguesurge_turn: int = 0
        self.plaguesurge_source: str = ""

    def _clear_plaguesurge_state(self) -> None:
        self.plaguesurge_active = False
        self.plaguesurge_bonus = 0
        self.plaguesurge_owner = ""
        self.plaguesurge_turn = 0
        self.plaguesurge_source = ""

    def _plaguesurge_bonus_for_current_state(self) -> float:
        if not bool(self.plaguesurge_active):
            return 0.0
        player = getattr(self.army, "player", None) if self.army is not None else None
        if player is None:
            return float(int(self.plaguesurge_bonus or 3))
        owner_id = str(self.plaguesurge_owner or "")
        player_id = str(getattr(player, "id", "") or "")
        if owner_id and player_id and owner_id != player_id:
            self._clear_plaguesurge_state()
            return 0.0
        game = getattr(player, "game", None)
        if game is None:
            return float(int(self.plaguesurge_bonus or 3))
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        try:
            used_turn = int(self.plaguesurge_turn or 0)
        except Exception:
            used_turn = 0
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        current_player = getattr(game, "get_current_player", lambda: None)()
        if current_turn > used_turn and current_player is player and phase_name == "COMMAND_PHASE":
            self._clear_plaguesurge_state()
            return 0.0
        return float(int(self.plaguesurge_bonus or 3))

    def _army_has_gift(self) -> bool:
        if self.army is None:
            return False
        return army_has_ability_id(self.army, ABILITY_NURGLES_GIFT)

    def _unit_is_death_guard(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return unit.has_any_keyword("DEATH GUARD")
        except Exception:
            return False

    def _unit_is_valid_contagion_source(self, unit, *, game=None, game_map=None) -> bool:
        if unit is None:
            return False
        source = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if source is None:
            return False
        has_nurgles_gift_source = self._unit_is_death_guard(source)
        if not has_nurgles_gift_source:
            dg_mgr = getattr(self.army, "death_guard_detachments", None) if self.army is not None else None
            grants_fn = (
                getattr(dg_mgr, "reverberant_rancidity_grants_nurgles_gift_source", None)
                if dg_mgr is not None
                else None
            )
            if callable(grants_fn):
                has_nurgles_gift_source = bool(grants_fn(source, game=game, game_map=game_map))
        if not has_nurgles_gift_source:
            return False

        if not bool(getattr(source, "deployed", False)):
            return False
        is_alive_fn = getattr(source, "is_alive", None)
        if callable(is_alive_fn) and not bool(is_alive_fn()):
            return False
        if bool(getattr(source, "is_embarked", False)) or bool(getattr(source, "embarked_in", None)):
            return False
        in_reserves_fn = getattr(source, "is_in_reserves", None)
        if callable(in_reserves_fn) and bool(in_reserves_fn()):
            return False
        return True

    @staticmethod
    def _unit_has_named_ability(unit, ability_name: str) -> bool:
        name_key = str(ability_name or "").strip().lower()
        if not name_key or unit is None:
            return False
        try:
            for ab in list(getattr(unit, "possible_abilities", []) or []):
                if isinstance(ab, str):
                    nm = str(ab or "").strip().lower()
                else:
                    nm = str(getattr(ab, "name", "") or "").strip().lower()
                if nm == name_key:
                    return True
        except Exception:
            pass
        try:
            for model in list(getattr(unit, "models", []) or []):
                abilities = getattr(model, "abilities", None)
                if not isinstance(abilities, dict):
                    continue
                for ab in list(abilities.values()):
                    if isinstance(ab, str):
                        nm = str(ab or "").strip().lower()
                    else:
                        nm = str(getattr(ab, "name", "") or "").strip().lower()
                    if nm == name_key:
                        return True
        except Exception:
            pass
        return False

    def _army_has_gift_of_poxes_source(self) -> bool:
        if self.army is None:
            return False
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            if not self._unit_is_valid_contagion_source(unit):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            if self._unit_has_named_ability(unit, "Gift of Poxes"):
                return True
        return False

    def get_contagion_range(self, battle_round: int, *, source_unit=None, game=None, game_map=None) -> float:
        base = float(nurgles_gift_contagion_range(battle_round))
        bonus = 3.0 if self._army_has_gift_of_poxes_source() else 0.0
        detachment_bonus = 0.0
        if source_unit is not None and self.army is not None:
            dg_mgr = getattr(self.army, "death_guard_detachments", None)
            bonus_fn = (
                getattr(dg_mgr, "reverberant_rancidity_contagion_range_bonus_for_unit", None)
                if dg_mgr is not None
                else None
            )
            if callable(bonus_fn):
                detachment_bonus = float(bonus_fn(source_unit, game=game, game_map=game_map) or 0.0)
        return float(base + bonus + self._plaguesurge_bonus_for_current_state() + detachment_bonus)

    def get_active_plague(self) -> Optional[NurglesPlague]:
        if not self.active_plague_key:
            return None
        key = str(self.active_plague_key).strip().upper()
        for plague in DEFAULT_PLAGUES:
            if plague.key == key:
                return plague
        return None

    def is_plague_active(self, key: str) -> bool:
        if not self._army_has_gift():
            return False
        if not self.active_plague_key:
            return False
        return str(self.active_plague_key).strip().upper() == str(key or "").strip().upper()

    def on_declare_battle_formations_start(self, *, game=None) -> None:
        if not self._army_has_gift():
            return
        if self.active_plague_key:
            return
        if game is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_PLAGUE
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.entity_ids import get_entity_id
        except Exception:
            return

        player = getattr(self.army, "player", None) if self.army is not None else None
        army_id = get_entity_id(self.army) if self.army is not None else None
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_PLAGUE:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("army_id", "")) == str(army_id):
                    return

        options = list(DEFAULT_PLAGUES)
        req_options = []
        for plague in options:
            req_options.append(
                DecisionOption.create(
                    plague.name,
                    payload={"choice_key": plague.key, "summary": plague.summary, "army_id": army_id},
                )
            )
        if not req_options:
            return
        req = DecisionRequest.create(
            DECISION_CHOOSE_PLAGUE,
            "Nurgle's Gift: select one Plague.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={
                "ability": "nurgles_gift_declare",
                "ability_name": "Nurgle's Gift",
                "army_id": army_id,
                "optional": False,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(req)

    def is_unit_afflicted(self, unit, *, game=None, game_map=None) -> bool:
        return self.get_afflicted_plague_for_unit(unit, game=game, game_map=game_map) is not None

    @staticmethod
    def get_afflicted_plague_for_unit(unit, *, game=None, game_map=None) -> Optional[NurglesPlague]:
        if unit is None:
            return None
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive):
                if not unit.is_alive():
                    return None
        except Exception:
            pass
        try:
            if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", True)):
                return None
        except Exception:
            pass

        if game is None:
            try:
                army = unit.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None

        def _resolve_source_army(owner_id: str):
            if game is None or not owner_id:
                return None
            for p in list(getattr(game, "players", []) or []):
                if p is None:
                    continue
                if str(getattr(p, "id", "") or "") != owner_id:
                    continue
                source_army = getattr(p, "army", None)
                if source_army is None and hasattr(p, "get_army"):
                    source_army = p.get_army()
                if source_army is not None:
                    return source_army
            return None

        # Datasheet effects can mark units as Afflicted outside contagion range checks.
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict) and sr.get("post_shoot_afflicted_active"):
            owner_id = str(sr.get("post_shoot_afflicted_owner", "") or "")
            source_army = _resolve_source_army(owner_id)
            if source_army is not None:
                mgr = getattr(source_army, "nurgles_gift", None)
                if mgr is not None:
                    plague = mgr.get_active_plague()
                    if plague is not None:
                        return plague

        if isinstance(sr, dict) and sr.get("miasmic_bombardment_active"):
            owner_id = str(sr.get("miasmic_bombardment_owner", "") or "")
            round_matches = True
            if game is not None:
                try:
                    current_round = int(getattr(game, "turn", 0) or 0)
                except Exception:
                    current_round = 0
                try:
                    marked_round = int(sr.get("miasmic_bombardment_round", 0) or 0)
                except Exception:
                    marked_round = 0
                if marked_round and current_round and marked_round != current_round:
                    round_matches = False
            if round_matches:
                source_army = _resolve_source_army(owner_id)
                if source_army is not None:
                    mgr = getattr(source_army, "nurgles_gift", None)
                    if mgr is not None:
                        plague = mgr.get_active_plague()
                        if plague is not None:
                            return plague

        if game_map is None:
            if game is not None:
                game_map = getattr(game, "map", None)
        if game_map is None:
            return None

        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0

        try:
            enemy_units = list(game_map.get_enemy_units(unit))
        except Exception:
            try:
                unit_army = unit.get_parent_army()
            except Exception:
                unit_army = None
            try:
                enemy_units = [
                    u for u in list(getattr(game_map, "units", []) or [])
                    if getattr(u, "get_parent_army", lambda: None)() is not unit_army
                ]
            except Exception:
                enemy_units = []

        if not enemy_units:
            return None

        from ..utility import aura_utils as _aura_utils

        checked_armies: set[str] = set()
        for enemy in enemy_units:
            try:
                enemy_army = enemy.get_parent_army()
            except Exception:
                enemy_army = None
            if enemy_army is None:
                continue
            try:
                key = get_entity_id(enemy_army)
            except Exception:
                key = ""
            if key in checked_armies:
                continue
            checked_armies.add(key)

            mgr = getattr(enemy_army, "nurgles_gift", None)
            if mgr is None:
                continue
            if not getattr(mgr, "_army_has_gift", lambda: False)():
                continue
            plague = mgr.get_active_plague()
            if plague is None:
                continue

            try:
                sources = list(getattr(enemy_army, "units", []) or [])
            except Exception:
                sources = [u for u in enemy_units if getattr(u, "get_parent_army", lambda: None)() is enemy_army]

            for source in sources:
                if not mgr._unit_is_valid_contagion_source(source, game=game, game_map=game_map):
                    continue
                rng = mgr.get_contagion_range(br, source_unit=source, game=game, game_map=game_map)
                if _aura_utils.unit_within_range_of_unit(source, unit, rng, use_attached_aggregate=True):
                    return plague

            # Virulent Vectorium: Worldblight turns controlled objectives into contagion sources.
            objectives = list(getattr(game_map, "objectives", []) or [])
            for obj in objectives:
                loc = getattr(obj, "location", None)
                if loc is None or getattr(loc, "removed", False):
                    continue
                worldblight_owner = getattr(loc, "worldblight_controller", None)
                if worldblight_owner is None:
                    continue
                if getattr(worldblight_owner, "army", None) is not enemy_army:
                    continue
                if (
                    getattr(loc, "controlling_player", None) is not worldblight_owner
                    and getattr(loc, "sticky_controller", None) is not worldblight_owner
                ):
                    continue
                if _aura_utils.unit_within_range_of_point_3d(unit, (loc.x, loc.y), rng, use_attached_aggregate=True):
                    return plague

        return None
