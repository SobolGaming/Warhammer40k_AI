from __future__ import annotations

from typing import Any, Optional
import math
import logging

from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id
from ..utility.aura_utils import unit_within_range_of_unit

logger = logging.getLogger(__name__)


class AdeptaSororitasStratagemMixin:
    @staticmethod
    def _as_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _as_sort_key(unit: Any) -> str:
        return str(get_entity_id(unit) or "")

    @staticmethod
    def _as_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _as_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _as_has_keyword(unit: Any, keyword: str) -> bool:
        if unit is None:
            return False
        kw = str(keyword or "").strip()
        if not kw:
            return False
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            try:
                if bool(has_keyword(kw)):
                    return True
            except Exception:
                pass
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            try:
                return bool(has_any_keyword(kw))
            except Exception:
                return False
        return False

    @classmethod
    def _as_on_battlefield(cls, unit: Any) -> bool:
        root = cls._as_root(unit)
        if root is None:
            return False
        if not cls._as_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves):
            try:
                if bool(is_in_reserves()):
                    return False
            except Exception:
                return False
        if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
            return False
        return True

    def _get_adepta_sororitas_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "adepta_sororitas_detachments", None) if army is not None else None

    def _is_hallowed_martyrs(self) -> bool:
        mgr = self._get_adepta_sororitas_mgr()
        checker = getattr(mgr, "is_hallowed_martyrs", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_army_of_faith(self) -> bool:
        mgr = self._get_adepta_sororitas_mgr()
        checker = getattr(mgr, "is_army_of_faith", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_bringers_of_flame(self) -> bool:
        mgr = self._get_adepta_sororitas_mgr()
        checker = getattr(mgr, "is_bringers_of_flame", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_champions_of_faith(self) -> bool:
        mgr = self._get_adepta_sororitas_mgr()
        checker = getattr(mgr, "is_champions_of_faith", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_penitent_host(self) -> bool:
        mgr = self._get_adepta_sororitas_mgr()
        checker = getattr(mgr, "is_penitent_host", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_adepta_sororitas_unit(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None:
            return False
        mgr = self._get_adepta_sororitas_mgr()
        checker = getattr(mgr, "unit_is_adepta_sororitas", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._as_has_keyword(root, "ADEPTA SORORITAS")

    def _is_penitent_unit(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None:
            return False
        mgr = self._get_adepta_sororitas_mgr()
        checker = getattr(mgr, "unit_is_penitent", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._as_has_keyword(root, "PENITENT")

    def _is_penitent_model(self, model: Any, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None:
            return False
        mgr = self._get_adepta_sororitas_mgr()
        checker = getattr(mgr, "model_is_penitent", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(model, root))
        has_any_keyword = getattr(model, "has_any_keyword", None)
        if callable(has_any_keyword) and bool(has_any_keyword("PENITENT")):
            return True
        return self._is_penitent_unit(root)

    def _is_penitent_engines_unit(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None:
            return False
        return self._is_penitent_unit(root) and self._as_has_keyword(root, "PENITENT ENGINES")

    def _is_adepta_sororitas_infantry_or_walker(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None or not self._is_adepta_sororitas_unit(root):
            return False
        return bool(self._as_has_keyword(root, "INFANTRY") or self._as_has_keyword(root, "WALKER"))

    def _is_adepta_sororitas_vehicle(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None or not self._is_adepta_sororitas_unit(root):
            return False
        if self._as_has_keyword(root, "VEHICLE"):
            return True
        return bool(getattr(root, "is_vehicle", False))

    def _is_adepta_sororitas_transport(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None:
            return False
        if not self._is_adepta_sororitas_vehicle(root):
            return False
        return bool(self._as_has_keyword(root, "TRANSPORT") or bool(getattr(root, "is_transport", False)))

    def _is_adepta_sororitas_character(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None or not self._is_adepta_sororitas_unit(root):
            return False
        return self._as_has_keyword(root, "CHARACTER")

    def _as_resolve_friendly_transport_for_disembarked_unit(self, unit: Any) -> Any:
        root = self._as_root(unit)
        if root is None:
            return None
        round_state = getattr(root, "round_state", None)
        transport_id = str(getattr(round_state, "disembarked_from_transport_id", "") or "")
        if not transport_id:
            return None
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        for unit_entry in list(getattr(army, "units", []) or []):
            candidate = self._as_root(unit_entry)
            if candidate is None:
                continue
            if self._as_sort_key(candidate) != transport_id:
                continue
            if not self._as_owned_by_player(candidate, self.player):
                continue
            return candidate
        return None

    @staticmethod
    def _as_is_saint_celestine(unit: Any) -> bool:
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                root = get_root()
            except Exception:
                root = unit
        name = str(getattr(root, "name", "") or "").strip().lower()
        return "saint celestine" in name

    @staticmethod
    def _as_phase_name_lower(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _as_phase_key(value: Any) -> str:
        return str(value or "").strip().upper().replace(" ", "_")

    @staticmethod
    def _as_alive_model_count(unit: Any) -> int:
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                root = get_root()
            except Exception:
                root = unit
        models = []
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            try:
                models = list(get_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
        else:
            models = list(getattr(root, "models", []) or [])
        count = 0
        for model in models:
            alive = getattr(model, "is_alive", None)
            if callable(alive):
                try:
                    if bool(alive()):
                        count += 1
                    continue
                except Exception:
                    continue
            if bool(alive):
                count += 1
                continue
            wounds = int(getattr(model, "wounds", 0) or 0)
            if wounds > 0:
                count += 1
        return int(count)

    @staticmethod
    def _as_total_current_wounds(unit: Any) -> int:
        if unit is None:
            return 0
        models = []
        get_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_models):
            try:
                models = list(get_models() or [])
            except Exception:
                models = list(getattr(unit, "models", []) or [])
        else:
            models = list(getattr(unit, "models", []) or [])
        total = 0
        for model in models:
            alive = getattr(model, "is_alive", None)
            if callable(alive):
                try:
                    if not bool(alive()):
                        continue
                except Exception:
                    continue
            elif not bool(alive):
                continue
            try:
                total += max(0, int(getattr(model, "wounds", 0) or 0))
            except Exception:
                continue
        return int(total)

    @staticmethod
    def _as_is_battle_shocked(unit: Any) -> bool:
        if unit is None:
            return False
        checker = getattr(unit, "is_battle_shocked", None)
        if callable(checker):
            return bool(checker())
        return bool(getattr(unit, "battle_shocked", False))

    def _as_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_cost = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_cost):
            preview = apply_cost(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return cp_cost

    def _as_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = self._as_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _as_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _as_place_unit_into_strategic_reserves(self, unit: Any, *, reason: str = "") -> bool:
        root = self._as_root(unit)
        if root is None:
            return False
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        place_fn = getattr(root, "enter_strategic_reserves_midgame", None)
        if callable(place_fn):
            return bool(place_fn(game=game, game_map=game_map, reason=reason))

        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            if member is None:
                continue
            set_status = getattr(member, "set_reserve_status", None)
            if callable(set_status):
                set_status("strategic_reserves")
            else:
                member.reserve_status = "strategic_reserves"
            mark_midgame = getattr(member, "mark_entered_reserves_midgame", None)
            if callable(mark_midgame):
                mark_midgame(game=game)
            if bool(getattr(member, "is_aircraft", False)) and not bool(getattr(member, "hover_mode", False)):
                member._aircraft_return_turn = int(getattr(game, "turn", 0) or 0) + 1 if game is not None else 0
            member.deployed = True
            member.reserve_turn_deployed = None
            member.arrived_from_reserves_this_turn = False
            if game_map is not None and isinstance(getattr(game_map, "units", None), list) and member in game_map.units:
                game_map.units.remove(member)
        return True

    def _as_has_enemy_within_engagement_range(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None:
            return False
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement_range = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(is_within_engagement_range):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._as_root(enemy)
            if enemy_root is None:
                continue
            if not self._as_on_battlefield(enemy_root):
                continue
            if bool(is_within_engagement_range(root, enemy_root)):
                return True
        return False

    @classmethod
    def _as_unit_in_candidates(cls, root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = cls._as_sort_key(root)
        for candidate in list(candidates or []):
            cand_root = cls._as_root(candidate)
            if cand_root is None:
                continue
            if cand_root is root:
                return True
            if rid and rid == cls._as_sort_key(cand_root):
                return True
        return False

    @staticmethod
    def _as_unit_models(unit: Any) -> list[Any]:
        root = AdeptaSororitasStratagemMixin._as_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            return list(get_models() or [])
        return list(getattr(root, "models", []) or [])

    @staticmethod
    def _as_model_is_alive(model: Any) -> bool:
        if model is None:
            return False
        alive = getattr(model, "is_alive", None)
        if callable(alive):
            return bool(alive())
        return bool(alive)

    @staticmethod
    def _as_profile_has_keyword(profile: Any, keyword: str) -> bool:
        target = str(keyword or "").strip().upper()
        if not target or profile is None:
            return False
        get_keywords = getattr(profile, "get_keywords", None)
        if callable(get_keywords):
            for value in list(get_keywords() or []):
                text = str(value or "").strip().upper()
                if text == target or text.startswith(f"{target} "):
                    return True
        parent = getattr(profile, "parent_wargear", None)
        if parent is not None and target == "TORRENT":
            is_torrent = getattr(parent, "is_torrent", None)
            if callable(is_torrent) and bool(is_torrent()):
                return True
        return False

    def _as_unit_has_weapon_profiles(
        self,
        unit: Any,
        *,
        attack_type: str,
        required_keyword: str = "",
    ) -> bool:
        for model in self._as_unit_models(unit):
            if not self._as_model_is_alive(model):
                continue
            for profile in self._as_model_weapon_profiles(model, attack_type=attack_type):
                if required_keyword and not self._as_profile_has_keyword(profile, required_keyword):
                    continue
                return True
        return False

    def _as_unit_has_ranged_weapon(self, unit: Any) -> bool:
        return self._as_unit_has_weapon_profiles(unit, attack_type="ranged")

    def _as_unit_has_torrent_ranged_weapon(self, unit: Any) -> bool:
        return self._as_unit_has_weapon_profiles(unit, attack_type="ranged", required_keyword="TORRENT")

    def _as_unit_has_melee_weapon(self, unit: Any) -> bool:
        return self._as_unit_has_weapon_profiles(unit, attack_type="melee")

    def _army_of_faith_angelic_descent_candidates(self) -> list[Any]:
        if not self._is_army_of_faith():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._as_root(unit)
            if root is None:
                continue
            uid = self._as_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._as_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            if not self._as_has_keyword(root, "JUMP PACK"):
                continue
            if self._as_has_enemy_within_engagement_range(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._as_sort_key)

    @staticmethod
    def _as_turn_phase_key(game: Any) -> str:
        if game is None:
            return "0::UNKNOWN"
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        owner_id = str(get_entity_id(current_player) or getattr(current_player, "id", "") or "")
        phase_key = AdeptaSororitasStratagemMixin._as_phase_key(getattr(getattr(game, "phase", None), "name", ""))
        if not phase_key:
            phase_key = "UNKNOWN"
        return f"{turn}:{owner_id}:{phase_key}"

    def _as_current_turn(self) -> int:
        if self.game is None:
            return 0
        return int(getattr(self.game, "turn", 0) or 0)

    def _as_current_turn_owner_id(self) -> str:
        if self.game is None:
            return ""
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        return str(getattr(active_player, "id", "") or "")

    def _as_submit_decision_request(self, request: Any) -> bool:
        if request is None or self.game is None:
            return False
        request_decision = getattr(self.game, "request_decision", None)
        if callable(request_decision):
            request_decision(request)
            return True
        queue = getattr(self.game, "decision_queue", None)
        if queue is not None and hasattr(queue, "add"):
            queue.add(request)
            return True
        return False

    def _as_pending_choose_quarry_request(
        self,
        *,
        player_id: str = "",
        ctx_filters: Optional[dict[str, Any]] = None,
    ) -> bool:
        if self.game is None:
            return False
        queue = getattr(self.game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        filters = dict(ctx_filters or {})
        for pending in list(queue.list() or []):
            if str(getattr(pending, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            if player_id and str(getattr(pending, "player_id", "") or "") != str(player_id):
                continue
            ctx = dict(getattr(pending, "context", {}) or {})
            matches = True
            for key, value in filters.items():
                if key in {"phase_name", "phase_key"}:
                    if self._as_phase_key(ctx.get(key, "") or "") != self._as_phase_key(value):
                        matches = False
                        break
                    continue
                if key == "turn":
                    if int(ctx.get("turn", 0) or 0) != int(value or 0):
                        matches = False
                        break
                    continue
                if str(ctx.get(key, "") or "").strip() != str(value or "").strip():
                    matches = False
                    break
            if matches:
                return True
        return False

    def _champions_of_faith_is_righteous(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None or not self._is_champions_of_faith():
            return False
        mgr = self._get_adepta_sororitas_mgr()
        checker = getattr(mgr, "righteous_purpose_is_righteous", None) if mgr is not None else None
        return bool(checker(root)) if callable(checker) else False

    @staticmethod
    def _champions_of_faith_is_celestian_sacresants(unit: Any) -> bool:
        root = AdeptaSororitasStratagemMixin._as_root(unit)
        if root is None:
            return False
        name = str(getattr(root, "name", "") or "").strip().lower()
        return name == "celestian sacresants" or name.startswith("celestian sacresants ")

    def _army_of_faith_battlefield_units(
        self,
        *,
        require_jump_pack: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_targetable: bool = True,
    ) -> list[Any]:
        if not self._is_army_of_faith():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._as_root(unit)
            if root is None:
                continue
            uid = self._as_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._as_on_battlefield(root):
                continue
            if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            if require_jump_pack and not self._as_has_keyword(root, "JUMP PACK"):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._as_sort_key)

    def _army_of_faith_units_within_range(
        self,
        source_unit: Any,
        *,
        range_inches: float,
        include_source: bool = False,
        require_jump_pack: bool = False,
    ) -> list[Any]:
        if not self._is_army_of_faith():
            return []
        source_root = self._as_root(source_unit)
        if source_root is None or not self._as_on_battlefield(source_root):
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._as_root(unit)
            if root is None:
                continue
            uid = self._as_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if root is source_root and not include_source:
                continue
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._as_on_battlefield(root):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            if require_jump_pack and not self._as_has_keyword(root, "JUMP PACK"):
                continue
            if not unit_within_range_of_unit(source_root, root, float(range_inches), use_attached_aggregate=True):
                continue
            out.append(root)
        return sorted(out, key=self._as_sort_key)

    def _army_of_faith_divine_guidance_candidates(self, *, phase_name: str) -> list[Any]:
        phase_lower = self._as_phase_name_lower(phase_name)
        if phase_lower == "shooting phase":
            return self._army_of_faith_battlefield_units(require_not_shot=True, require_targetable=True)
        if phase_lower == "fight phase":
            return self._army_of_faith_battlefield_units(require_not_fought=True, require_targetable=True)
        return []

    def _army_of_faith_faith_and_fury_candidates(self) -> list[Any]:
        return self._army_of_faith_battlefield_units(require_not_fought=True, require_targetable=True)

    def _army_of_faith_light_of_the_emperor_candidates(self) -> list[Any]:
        return self._army_of_faith_battlefield_units(require_targetable=True)

    def _army_of_faith_blinding_radiance_candidates(self, *, target_units: Any) -> list[Any]:
        if not self._is_army_of_faith():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._as_root(unit)
            if root is None:
                continue
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._as_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            uid = self._as_sort_key(root)
            if uid and uid not in seen:
                seen.add(uid)
                out.append(root)
            for jump_pack_unit in self._army_of_faith_units_within_range(
                root,
                range_inches=3.0,
                require_jump_pack=True,
            ):
                if bool(self._unit_cannot_be_target_of_stratagem(jump_pack_unit)):
                    continue
                jump_uid = self._as_sort_key(jump_pack_unit)
                if jump_uid and jump_uid not in seen:
                    seen.add(jump_uid)
                    out.append(jump_pack_unit)
        return sorted(out, key=self._as_sort_key)

    def _army_of_faith_shield_of_faith_candidates(self, *, source_unit: Any) -> list[Any]:
        if not self._is_army_of_faith():
            return []
        root = self._as_root(source_unit)
        if root is None or not self._as_on_battlefield(root):
            return []
        if not self._as_owned_by_player(root, self.player):
            return []
        if not self._is_adepta_sororitas_unit(root):
            return []
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return []
        out = [root]
        seen = {self._as_sort_key(root)}
        for jump_pack_unit in self._army_of_faith_units_within_range(
            root,
            range_inches=3.0,
            require_jump_pack=True,
        ):
            if bool(self._unit_cannot_be_target_of_stratagem(jump_pack_unit)):
                continue
            uid = self._as_sort_key(jump_pack_unit)
            if uid and uid in seen:
                continue
            seen.add(uid)
            out.append(jump_pack_unit)
        return sorted(out, key=self._as_sort_key)

    def _as_can_use_army_of_faith_shield_of_faith_tool_action(self, kwargs: dict[str, Any]) -> bool:
        if not self._is_army_of_faith():
            return False
        source_unit = kwargs.get("source_unit") or kwargs.get("trigger_unit") or kwargs.get("suffering_unit")
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if (source_unit is None or unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SHIELD OF FAITH":
                    continue
                source_unit = source_unit or reaction.get("source_unit") or reaction.get("trigger_unit")
                unit = unit or reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        source_root = self._as_root(source_unit)
        if source_root is None:
            return False
        if not candidates:
            candidates = self._army_of_faith_shield_of_faith_candidates(source_unit=source_root)
        if unit is None:
            return bool(candidates)
        root = self._as_root(unit)
        if root is None:
            return False
        if candidates and not self._as_unit_in_candidates(root, candidates):
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return self._is_adepta_sororitas_unit(root)

    def _army_of_faith_jump_pack_aura_units(self, source_unit: Any) -> list[Any]:
        root = self._as_root(source_unit)
        if root is None:
            return []
        if not self._as_has_keyword(root, "JUMP PACK"):
            return [root]
        return self._army_of_faith_units_within_range(
            root,
            range_inches=3.0,
            include_source=True,
        )

    def _as_model_weapon_profiles(self, model: Any, *, attack_type: str) -> list[Any]:
        attack_type_key = str(attack_type or "").strip().lower()
        if attack_type_key not in {"melee", "ranged"}:
            return []
        profiles: list[Any] = []
        for wargear in list(getattr(model, "wargear", []) or []):
            is_melee = bool(callable(getattr(wargear, "is_melee", None)) and wargear.is_melee())
            is_ranged = bool(callable(getattr(wargear, "is_ranged", None)) and wargear.is_ranged())
            if attack_type_key == "melee" and not is_melee:
                continue
            if attack_type_key == "ranged" and not is_ranged:
                continue
            for profile in list((getattr(wargear, "profiles", {}) or {}).values()):
                if profile is not None:
                    profiles.append(profile)
        return profiles

    def _bringers_of_flame_battlefield_units(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_disembarked_from_transport: bool = False,
        require_targetable: bool = True,
    ) -> list[Any]:
        if not self._is_bringers_of_flame():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._as_root(unit)
            if root is None:
                continue
            uid = self._as_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._as_on_battlefield(root):
                continue
            if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            if require_disembarked_from_transport:
                if not bool(getattr(round_state, "disembarked_this_round", False)):
                    continue
                if not str(getattr(round_state, "disembarked_from_transport_id", "") or "").strip():
                    continue
            out.append(root)
        return sorted(out, key=self._as_sort_key)

    def _bringers_of_flame_cleansing_flames_candidates(self) -> list[Any]:
        return [
            unit
            for unit in self._bringers_of_flame_battlefield_units(require_not_shot=True, require_targetable=True)
            if self._as_unit_has_torrent_ranged_weapon(unit)
        ]

    def _bringers_of_flame_righteous_blows_candidates(self) -> list[Any]:
        return [
            unit
            for unit in self._bringers_of_flame_battlefield_units(require_not_fought=True, require_targetable=True)
            if self._as_unit_has_melee_weapon(unit)
        ]

    def _bringers_of_flame_rites_of_fire_candidates(self) -> list[Any]:
        return [
            unit
            for unit in self._bringers_of_flame_battlefield_units(
                require_not_shot=True,
                require_disembarked_from_transport=True,
                require_targetable=True,
            )
            if self._as_unit_has_ranged_weapon(unit)
        ]

    def _champions_of_faith_battlefield_units(
        self,
        *,
        require_righteous: bool = False,
        require_sacresants: bool = False,
        require_not_battle_shocked: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_targetable: bool = True,
    ) -> list[Any]:
        if not self._is_champions_of_faith():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._as_root(unit)
            if root is None:
                continue
            uid = self._as_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._as_on_battlefield(root):
                continue
            if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            if require_righteous and not self._champions_of_faith_is_righteous(root):
                continue
            if require_sacresants and not self._champions_of_faith_is_celestian_sacresants(root):
                continue
            if require_not_battle_shocked and self._as_is_battle_shocked(root):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._as_sort_key)

    def _champions_of_faith_path_of_the_righteous_candidates(self) -> list[Any]:
        return self._champions_of_faith_battlefield_units(require_not_fought=True, require_targetable=True)

    def _champions_of_faith_shield_of_denial_candidates(self, *, source_unit: Any) -> list[Any]:
        root = self._as_root(source_unit)
        if root is None or not self._is_champions_of_faith():
            return []
        if not self._as_owned_by_player(root, self.player):
            return []
        if not self._as_on_battlefield(root):
            return []
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return []
        if not self._is_adepta_sororitas_unit(root):
            return []
        return [root]

    def _champions_of_faith_suffer_not_the_unfaithful_candidates(self, *, phase_name: str) -> list[Any]:
        phase_lower = self._as_phase_name_lower(phase_name)
        candidates = self._champions_of_faith_battlefield_units(
            require_righteous=True,
            require_not_shot=phase_lower == "shooting phase",
            require_not_fought=phase_lower == "fight phase",
            require_targetable=True,
        )
        if phase_lower == "shooting phase":
            return [unit for unit in candidates if self._as_unit_has_ranged_weapon(unit)]
        if phase_lower == "fight phase":
            return [unit for unit in candidates if self._as_unit_has_melee_weapon(unit)]
        return []

    def _champions_of_faith_to_the_heart_of_heresy_candidates(self) -> list[Any]:
        return [
            unit
            for unit in self._champions_of_faith_battlefield_units(require_not_fought=True, require_targetable=True)
            if self._as_unit_has_melee_weapon(unit)
        ]

    def _champions_of_faith_indefatigable_dedication_candidates(self, *, moved_unit: Any, action: Any) -> list[Any]:
        if str(action or "").strip().lower() != "fall_back":
            return []
        root = self._as_root(moved_unit)
        if root is None:
            return []
        candidates = self._champions_of_faith_battlefield_units(require_targetable=True)
        return [root] if self._as_unit_in_candidates(root, candidates) else []

    def _champions_of_faith_bastion_of_faith_candidates(self, *, target_units: Any) -> list[Any]:
        if not self._is_champions_of_faith():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._as_root(unit)
            if root is None:
                continue
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._as_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._champions_of_faith_is_celestian_sacresants(root):
                continue
            uid = self._as_sort_key(root)
            if uid and uid not in seen:
                seen.add(uid)
                out.append(root)
        return sorted(out, key=self._as_sort_key)

    def _champions_of_faith_bastion_secondary_candidates(self, *, primary_unit: Any) -> list[Any]:
        primary_root = self._as_root(primary_unit)
        if primary_root is None:
            return []
        if not self._champions_of_faith_is_righteous(primary_root):
            return []
        out: list[Any] = []
        for unit in self._champions_of_faith_battlefield_units(
            require_sacresants=True,
            require_not_battle_shocked=True,
            require_targetable=True,
        ):
            if unit is primary_root:
                continue
            if not unit_within_range_of_unit(primary_root, unit, 6.0, use_attached_aggregate=True):
                continue
            out.append(unit)
        return sorted(out, key=self._as_sort_key)

    def _penitent_host_battlefield_units(
        self,
        *,
        require_penitent: bool = True,
        require_not_fought: bool = False,
        require_not_shot: bool = False,
        require_targetable: bool = True,
    ) -> list[Any]:
        if not self._is_penitent_host():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._as_root(unit)
            if root is None:
                continue
            uid = self._as_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._as_on_battlefield(root):
                continue
            if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            if require_penitent and not self._is_penitent_unit(root):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._as_sort_key)

    def _penitent_host_passion_of_the_penitent_candidates(self) -> list[Any]:
        return [
            unit
            for unit in self._penitent_host_battlefield_units(
                require_penitent=True,
                require_not_fought=True,
                require_targetable=True,
            )
            if self._as_unit_has_melee_weapon(unit)
        ]

    def _penitent_host_lash_of_guilt_candidates(self, *, moved_unit: Any, action: Any) -> list[Any]:
        if str(action or "").strip().lower() != "advance":
            return []
        root = self._as_root(moved_unit)
        if root is None:
            return []
        candidates = self._penitent_host_battlefield_units(require_penitent=True, require_targetable=True)
        return [root] if self._as_unit_in_candidates(root, candidates) else []

    def _penitent_host_boundless_zeal_candidates(self, *, moved_unit: Any, action: Any) -> list[Any]:
        if str(action or "").strip().lower() != "fall_back":
            return []
        root = self._as_root(moved_unit)
        if root is None:
            return []
        candidates = self._penitent_host_battlefield_units(require_penitent=False, require_targetable=True)
        return [root] if self._as_unit_in_candidates(root, candidates) else []

    def _penitent_host_purity_of_suffering_candidates(self, *, target_units: Any) -> list[Any]:
        if not self._is_penitent_host():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._as_root(unit)
            if root is None:
                continue
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._as_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_penitent_unit(root):
                continue
            uid = self._as_sort_key(root)
            if uid and uid not in seen:
                seen.add(uid)
                out.append(root)
        return sorted(out, key=self._as_sort_key)

    def _penitent_host_objective_candidates(self, *, unit: Any, last_model: Any = None) -> list[Any]:
        root = self._as_root(unit)
        if root is None or self.game is None:
            return []
        snapshot = getattr(self.game, "_objective_control_snapshot", None)
        if not isinstance(snapshot, dict) or not snapshot:
            return []
        pos = None
        if last_model is not None:
            get_location = getattr(last_model, "get_location", None)
            if callable(get_location):
                pos = get_location()
        if pos is None:
            get_models = getattr(root, "get_attached_unit_models", None)
            models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
            for model in list(models or []):
                get_location = getattr(model, "get_location", None)
                if callable(get_location):
                    pos = get_location()
                    break
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            return []
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        try:
            ux = float(pos[0])
            uy = float(pos[1])
        except (TypeError, ValueError):
            return []
        base_radius = 0.0
        base = getattr(last_model, "model_base", None) if last_model is not None else None
        if base is None:
            models = list(getattr(root, "models", []) or [])
            if models:
                base = getattr(models[0], "model_base", None)
        if base is not None:
            try:
                base_radius = float(getattr(base, "base_size", 0.0) or 0.0)
            except (TypeError, ValueError):
                base_radius = 0.0
        candidates: list[Any] = []
        for objective in list(getattr(game_map, "objectives", []) or []):
            loc = getattr(objective, "location", None)
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            if snapshot.get(loc) is not self.player:
                continue
            try:
                radius = float(getattr(loc, "control_radius", 0.0) or 0.0)
                dx = ux - float(getattr(loc, "x", 0.0))
                dy = uy - float(getattr(loc, "y", 0.0))
            except (TypeError, ValueError):
                continue
            if math.sqrt(dx * dx + dy * dy) <= (radius + base_radius):
                candidates.append(objective)
        return candidates

    def _penitent_host_devout_targets(self) -> dict[str, list[Any]]:
        snapshots = getattr(self, "_penitent_host_devout_target_units_by_attacker", None)
        if not isinstance(snapshots, dict):
            snapshots = {}
            self._penitent_host_devout_target_units_by_attacker = snapshots
        return snapshots

    @staticmethod
    def _penitent_host_parse_boundless_zeal_choice(raw_choice: Any) -> str:
        choice = raw_choice
        if isinstance(choice, dict):
            choice = (
                choice.get("choice_key")
                or choice.get("choice")
                or choice.get("selection")
                or choice.get("value")
                or choice.get("label")
            )
        key = str(choice or "").strip().upper().replace("-", "_").replace(" ", "_")
        if key in {"SHOOT", "SHOOT_AFTER_FALL_BACK"}:
            return "SHOOT"
        if key in {"CHARGE", "CHARGE_AFTER_FALL_BACK"}:
            return "CHARGE"
        return ""

    @staticmethod
    def _penitent_host_boundless_zeal_choice_label(choice_key: str) -> str:
        if str(choice_key or "").strip().upper() == "CHARGE":
            return "Charge"
        return "Shoot"

    def _build_penitent_host_boundless_zeal_choice_request(
        self,
        *,
        unit: Any,
        phase_name: str,
        stratagem_name: str,
    ) -> Any:
        if self.game is None or not bool(getattr(self.game, "is_authoritative", True)):
            return None
        root = self._as_root(unit)
        if root is None:
            return None
        unit_id = self._as_sort_key(root)
        if not unit_id:
            return None
        player_id = str(getattr(self.player, "id", "") or "")
        phase_label = str(phase_name or "").strip() or "Movement phase"
        turn = self._as_current_turn()
        turn_owner_id = self._as_current_turn_owner_id()
        if self._as_pending_choose_quarry_request(
            player_id=player_id,
            ctx_filters={
                "ability": "penitent_host_boundless_zeal_mode",
                "unit_id": unit_id,
                "phase_name": phase_label,
                "turn": turn,
                "turn_owner_id": turn_owner_id,
            },
        ):
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{str(stratagem_name or '').strip() or 'BOUNDLESS ZEAL'}: choose Shoot or Charge.",
            player_id=player_id,
            options=[
                DecisionOption.create(
                    "Shoot",
                    payload={"choice_key": "SHOOT", "unit_id": unit_id},
                ),
                DecisionOption.create(
                    "Charge",
                    payload={"choice_key": "CHARGE", "unit_id": unit_id},
                ),
            ],
            context={
                "ability": "penitent_host_boundless_zeal_mode",
                "ability_name": str(stratagem_name or "").strip() or "BOUNDLESS ZEAL",
                "army_id": str(get_entity_id(getattr(self.player, "army", None)) or ""),
                "unit_id": unit_id,
                "phase_name": phase_label,
                "turn": turn,
                "turn_owner_id": turn_owner_id,
                "candidate_choice_keys": ["SHOOT", "CHARGE"],
                "stratagem_name": str(stratagem_name or "").strip() or "BOUNDLESS ZEAL",
                "optional": False,
            },
        )

    def validate_penitent_host_boundless_zeal_choice(
        self,
        unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        turn: int = 0,
        turn_owner_id: str = "",
        stratagem_name: str = "",
    ) -> tuple[bool, str]:
        root = self._as_root(unit)
        if root is None:
            return False, "BOUNDLESS ZEAL choice unit was not found."
        if player is not None and player is not self.player:
            return False, "BOUNDLESS ZEAL choice must be resolved by the owning player."
        if not self._is_penitent_host():
            return False, "BOUNDLESS ZEAL requires Penitent Host."
        if not self._as_owned_by_player(root, self.player):
            return False, "BOUNDLESS ZEAL target must belong to you."
        if not self._as_on_battlefield(root):
            return False, "BOUNDLESS ZEAL target must be on the battlefield."
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False, "BOUNDLESS ZEAL target can no longer be selected."
        if not self._is_adepta_sororitas_unit(root):
            return False, "BOUNDLESS ZEAL target must be ADEPTA SORORITAS."
        if self._is_penitent_unit(root):
            return False, "BOUNDLESS ZEAL mode choice is only used for non-PENITENT units."
        if game is not None:
            current_phase = self._as_phase_key(getattr(getattr(game, "phase", None), "name", "") or "")
            expected_phase = self._as_phase_key(phase_name)
            if current_phase and expected_phase and current_phase != expected_phase:
                return False, "BOUNDLESS ZEAL choice is no longer in the same phase."
            if int(turn or 0) > 0 and int(getattr(game, "turn", 0) or 0) != int(turn or 0):
                return False, "BOUNDLESS ZEAL choice is no longer in the same turn."
            if turn_owner_id:
                active_player = getattr(game, "get_current_player", lambda: None)()
                current_owner_id = str(getattr(active_player, "id", "") or "")
                if current_owner_id and current_owner_id != str(turn_owner_id):
                    return False, "BOUNDLESS ZEAL choice is no longer in the same turn."
        if self._as_phase_name_lower(phase_name) != "movement phase":
            return False, "BOUNDLESS ZEAL choice requires the Movement phase."
        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "fell_back_this_round", False)):
            return False, "BOUNDLESS ZEAL target must have just Fallen Back."
        choice_key = self._penitent_host_parse_boundless_zeal_choice(payload)
        if choice_key not in {"SHOOT", "CHARGE"}:
            return False, "BOUNDLESS ZEAL choice must be Shoot or Charge."
        resolved_name = str(stratagem_name or payload.get("stratagem_name", "") or "").strip().upper()
        if resolved_name and resolved_name != "BOUNDLESS ZEAL":
            return False, "BOUNDLESS ZEAL choice payload does not match the stratagem."
        return True, ""

    def apply_penitent_host_boundless_zeal_choice(
        self,
        unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        turn: int = 0,
        turn_owner_id: str = "",
        stratagem_name: str = "",
    ) -> Any:
        valid, _reason = self.validate_penitent_host_boundless_zeal_choice(
            unit,
            payload,
            game=game,
            player=player,
            phase_name=phase_name,
            turn=turn,
            turn_owner_id=turn_owner_id,
            stratagem_name=stratagem_name,
        )
        if not valid:
            return None
        root = self._as_root(unit)
        if root is None:
            return None
        choice_key = self._penitent_host_parse_boundless_zeal_choice(payload)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["penitent_host_boundless_zeal_active"] = True
        sr["penitent_host_boundless_zeal_mode"] = "shoot" if choice_key == "SHOOT" else "charge"
        sr["penitent_host_boundless_zeal_turn_owner"] = str(turn_owner_id or self._as_current_turn_owner_id())
        sr["penitent_host_boundless_zeal_turn"] = int(turn or self._as_current_turn())
        sr["penitent_host_boundless_zeal_source"] = (
            str(stratagem_name or payload.get("stratagem_name", "") or "BOUNDLESS ZEAL").strip() or "BOUNDLESS ZEAL"
        )
        root.special_rules = sr
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.pop("fell_back_and_shoot", None)
        return {
            "unit_id": self._as_sort_key(root),
            "unit_name": str(getattr(root, "name", "Unit") or "Unit"),
            "choice_key": choice_key,
            "choice_label": self._penitent_host_boundless_zeal_choice_label(choice_key),
            "stratagem_name": str(stratagem_name or payload.get("stratagem_name", "") or "BOUNDLESS ZEAL"),
        }

    @staticmethod
    def _champions_of_faith_parse_suffer_choice(raw_choice: Any) -> str:
        choice = raw_choice
        if isinstance(choice, dict):
            choice = (
                choice.get("choice_key")
                or choice.get("choice")
                or choice.get("selection")
                or choice.get("value")
                or choice.get("label")
            )
        key = str(choice or "").strip().upper().replace("-", "_").replace(" ", "_")
        if key in {"LETHAL", "LETHAL_HITS", "[LETHAL_HITS]"}:
            return "LETHAL_HITS"
        if key in {"SUSTAINED", "SUSTAINED_HITS", "SUSTAINED_HITS_1", "[SUSTAINED_HITS_1]"}:
            return "SUSTAINED_HITS_1"
        return ""

    @staticmethod
    def _champions_of_faith_suffer_choice_label(choice_key: str) -> str:
        if str(choice_key or "").strip().upper() == "LETHAL_HITS":
            return "LETHAL HITS"
        return "SUSTAINED HITS 1"

    @staticmethod
    def _as_resolve_game_unit(game: Any, unit_id: str) -> Any:
        if game is None:
            return None
        registry = getattr(game, "entity_registry", None)
        if registry is None or not hasattr(registry, "get"):
            return None
        target_id = str(unit_id or "").strip()
        if not target_id:
            return None
        unit = registry.get(target_id, kind="unit")
        if unit is not None:
            return unit
        return registry.get(target_id)

    def _build_champions_of_faith_suffer_choice_request(
        self,
        *,
        unit: Any,
        phase_name: str,
        stratagem_name: str,
    ) -> Any:
        if self.game is None or not bool(getattr(self.game, "is_authoritative", True)):
            return None
        root = self._as_root(unit)
        if root is None:
            return None
        unit_id = self._as_sort_key(root)
        if not unit_id:
            return None
        player_id = str(getattr(self.player, "id", "") or "")
        phase_label = str(phase_name or "").strip() or "Fight phase"
        turn = self._as_current_turn()
        turn_owner_id = self._as_current_turn_owner_id()
        if self._as_pending_choose_quarry_request(
            player_id=player_id,
            ctx_filters={
                "ability": "champions_of_faith_suffer_not_the_unfaithful_choice",
                "unit_id": unit_id,
                "phase_name": phase_label,
                "turn": turn,
                "turn_owner_id": turn_owner_id,
            },
        ):
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{str(stratagem_name or '').strip() or 'SUFFER NOT THE UNFAITHFUL'}: choose a weapon ability.",
            player_id=player_id,
            options=[
                DecisionOption.create(
                    "Lethal Hits",
                    payload={"choice_key": "LETHAL_HITS", "unit_id": unit_id},
                ),
                DecisionOption.create(
                    "Sustained Hits 1",
                    payload={"choice_key": "SUSTAINED_HITS_1", "unit_id": unit_id},
                ),
            ],
            context={
                "ability": "champions_of_faith_suffer_not_the_unfaithful_choice",
                "ability_name": str(stratagem_name or "").strip() or "SUFFER NOT THE UNFAITHFUL",
                "army_id": str(get_entity_id(getattr(self.player, "army", None)) or ""),
                "unit_id": unit_id,
                "phase_name": phase_label,
                "attack_type": "ranged" if self._as_phase_name_lower(phase_label) == "shooting phase" else "melee",
                "turn": turn,
                "turn_owner_id": turn_owner_id,
                "candidate_choice_keys": ["LETHAL_HITS", "SUSTAINED_HITS_1"],
                "stratagem_name": str(stratagem_name or "").strip() or "SUFFER NOT THE UNFAITHFUL",
                "optional": False,
            },
        )

    def validate_champions_of_faith_suffer_choice(
        self,
        unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        attack_type: str = "",
        turn: int = 0,
        turn_owner_id: str = "",
        stratagem_name: str = "",
    ) -> tuple[bool, str]:
        root = self._as_root(unit)
        if root is None:
            return False, "SUFFER NOT THE UNFAITHFUL choice unit was not found."
        if player is not None and player is not self.player:
            return False, "SUFFER NOT THE UNFAITHFUL choice must be resolved by the owning player."
        if not self._is_champions_of_faith():
            return False, "SUFFER NOT THE UNFAITHFUL requires Champions of Faith."
        if not self._as_owned_by_player(root, self.player):
            return False, "SUFFER NOT THE UNFAITHFUL target must belong to you."
        if not self._as_on_battlefield(root):
            return False, "SUFFER NOT THE UNFAITHFUL target must be on the battlefield."
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False, "SUFFER NOT THE UNFAITHFUL target can no longer be selected."
        if not self._champions_of_faith_is_righteous(root):
            return False, "SUFFER NOT THE UNFAITHFUL target must be Righteous."
        if game is not None:
            current_phase = self._as_phase_key(getattr(getattr(game, "phase", None), "name", "") or "")
            expected_phase = self._as_phase_key(phase_name)
            if current_phase and expected_phase and current_phase != expected_phase:
                return False, "SUFFER NOT THE UNFAITHFUL choice is no longer in the same phase."
            if int(turn or 0) > 0 and int(getattr(game, "turn", 0) or 0) != int(turn or 0):
                return False, "SUFFER NOT THE UNFAITHFUL choice is no longer in the same turn."
            if turn_owner_id:
                active_player = getattr(game, "get_current_player", lambda: None)()
                current_owner_id = str(getattr(active_player, "id", "") or "")
                if current_owner_id and current_owner_id != str(turn_owner_id):
                    return False, "SUFFER NOT THE UNFAITHFUL choice is no longer in the same turn."
        phase_lower = self._as_phase_name_lower(phase_name)
        round_state = getattr(root, "round_state", None)
        if phase_lower == "shooting phase":
            if bool(getattr(round_state, "shot_this_round", False)):
                return False, "SUFFER NOT THE UNFAITHFUL target has already been selected to shoot."
            if not self._as_unit_has_ranged_weapon(root):
                return False, "SUFFER NOT THE UNFAITHFUL target has no ranged weapons."
        elif phase_lower == "fight phase":
            if bool(getattr(round_state, "fought_this_phase", False)):
                return False, "SUFFER NOT THE UNFAITHFUL target has already been selected to fight."
            if not self._as_unit_has_melee_weapon(root):
                return False, "SUFFER NOT THE UNFAITHFUL target has no melee weapons."
        else:
            return False, "SUFFER NOT THE UNFAITHFUL choice requires the Shooting or Fight phase."
        expected_attack_type = "ranged" if phase_lower == "shooting phase" else "melee"
        if attack_type and str(attack_type or "").strip().lower() != expected_attack_type:
            return False, "SUFFER NOT THE UNFAITHFUL choice payload does not match the phase."
        choice_key = self._champions_of_faith_parse_suffer_choice(payload)
        if choice_key not in {"LETHAL_HITS", "SUSTAINED_HITS_1"}:
            return False, "SUFFER NOT THE UNFAITHFUL choice must be LETHAL HITS or SUSTAINED HITS 1."
        resolved_name = str(stratagem_name or payload.get("stratagem_name", "") or "").strip().upper()
        if resolved_name and resolved_name != "SUFFER NOT THE UNFAITHFUL":
            return False, "SUFFER NOT THE UNFAITHFUL choice payload does not match the stratagem."
        return True, ""

    def apply_champions_of_faith_suffer_choice(
        self,
        unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        attack_type: str = "",
        turn: int = 0,
        turn_owner_id: str = "",
        stratagem_name: str = "",
    ) -> Any:
        valid, _reason = self.validate_champions_of_faith_suffer_choice(
            unit,
            payload,
            game=game,
            player=player,
            phase_name=phase_name,
            attack_type=attack_type,
            turn=turn,
            turn_owner_id=turn_owner_id,
            stratagem_name=stratagem_name,
        )
        if not valid:
            return None
        root = self._as_root(unit)
        if root is None:
            return None
        choice_key = self._champions_of_faith_parse_suffer_choice(payload)
        keyword = self._champions_of_faith_suffer_choice_label(choice_key)
        phase_key = self._as_phase_key(phase_name)
        resolved_attack_type = str(attack_type or "").strip().lower() or (
            "ranged" if self._as_phase_name_lower(phase_name) == "shooting phase" else "melee"
        )
        stratagem_source = str(stratagem_name or payload.get("stratagem_name", "") or "SUFFER NOT THE UNFAITHFUL")
        for model in self._as_unit_models(root):
            if not self._as_model_is_alive(model):
                continue
            model_id = str(get_entity_id(model) or "")
            for profile in self._as_model_weapon_profiles(model, attack_type=resolved_attack_type):
                lookup_name_fn = getattr(profile, "_temporary_weapon_lookup_name", None)
                weapon_name = lookup_name_fn() if callable(lookup_name_fn) else str(getattr(profile, "name", "") or "")
                if not weapon_name:
                    continue
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if not callable(set_keywords):
                    continue
                set_keywords(
                    key=f"champions_of_faith_suffer_not_the_unfaithful:{self._as_sort_key(root)}:{model_id}:{weapon_name}",
                    weapon_name=weapon_name,
                    keywords=[keyword],
                    source=stratagem_source,
                    expires_phase=phase_key,
                    attack_type=resolved_attack_type,
                )
        return {
            "unit_id": self._as_sort_key(root),
            "unit_name": str(getattr(root, "name", "Unit") or "Unit"),
            "choice_key": choice_key,
            "choice_label": keyword,
            "attack_type": resolved_attack_type,
            "stratagem_name": stratagem_source,
        }

    def _build_champions_of_faith_bastion_secondary_request(
        self,
        *,
        primary_unit: Any,
        phase_name: str,
        stratagem_name: str,
    ) -> Any:
        if self.game is None or not bool(getattr(self.game, "is_authoritative", True)):
            return None
        primary_root = self._as_root(primary_unit)
        if primary_root is None:
            return None
        candidates = self._champions_of_faith_bastion_secondary_candidates(primary_unit=primary_root)
        if not candidates:
            return None
        player_id = str(getattr(self.player, "id", "") or "")
        primary_unit_id = self._as_sort_key(primary_root)
        phase_label = str(phase_name or "").strip() or "Fight phase"
        turn = self._as_current_turn()
        turn_owner_id = self._as_current_turn_owner_id()
        if self._as_pending_choose_quarry_request(
            player_id=player_id,
            ctx_filters={
                "ability": "champions_of_faith_bastion_of_faith_secondary",
                "primary_unit_id": primary_unit_id,
                "phase_name": phase_label,
                "turn": turn,
                "turn_owner_id": turn_owner_id,
            },
        ):
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = [
            DecisionOption.create(
                "None",
                payload={"action": "skip", "primary_unit_id": primary_unit_id},
            )
        ]
        for unit in candidates:
            unit_id = self._as_sort_key(unit)
            options.append(
                DecisionOption.create(
                    str(getattr(unit, "name", "Celestian Sacresants") or "Celestian Sacresants"),
                    payload={
                        "target_unit_id": unit_id,
                        "unit_id": unit_id,
                        "primary_unit_id": primary_unit_id,
                    },
                )
            )
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{str(stratagem_name or '').strip() or 'BASTION OF FAITH'}: select another Celestian Sacresants unit to protect, or None.",
            player_id=player_id,
            options=options,
            context={
                "ability": "champions_of_faith_bastion_of_faith_secondary",
                "ability_name": str(stratagem_name or "").strip() or "BASTION OF FAITH",
                "army_id": str(get_entity_id(getattr(self.player, "army", None)) or ""),
                "primary_unit_id": primary_unit_id,
                "phase_name": phase_label,
                "turn": turn,
                "turn_owner_id": turn_owner_id,
                "candidate_unit_ids": [self._as_sort_key(unit) for unit in candidates],
                "stratagem_name": str(stratagem_name or "").strip() or "BASTION OF FAITH",
                "optional": True,
            },
        )

    def validate_champions_of_faith_bastion_secondary_choice(
        self,
        primary_unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        turn: int = 0,
        turn_owner_id: str = "",
        stratagem_name: str = "",
        candidate_unit_ids: Optional[list[str]] = None,
    ) -> tuple[bool, str]:
        primary_root = self._as_root(primary_unit)
        if primary_root is None:
            return False, "BASTION OF FAITH primary unit was not found."
        if player is not None and player is not self.player:
            return False, "BASTION OF FAITH secondary choice must be resolved by the owning player."
        if not self._is_champions_of_faith():
            return False, "BASTION OF FAITH requires Champions of Faith."
        if not self._champions_of_faith_is_righteous(primary_root):
            return False, "BASTION OF FAITH secondary choice requires the primary unit to be Righteous."
        if game is not None:
            current_phase = self._as_phase_key(getattr(getattr(game, "phase", None), "name", "") or "")
            expected_phase = self._as_phase_key(phase_name or "Fight phase")
            if current_phase and expected_phase and current_phase != expected_phase:
                return False, "BASTION OF FAITH secondary choice is no longer in the Fight phase."
            if int(turn or 0) > 0 and int(getattr(game, "turn", 0) or 0) != int(turn or 0):
                return False, "BASTION OF FAITH secondary choice is no longer in the same turn."
            if turn_owner_id:
                active_player = getattr(game, "get_current_player", lambda: None)()
                current_owner_id = str(getattr(active_player, "id", "") or "")
                if current_owner_id and current_owner_id != str(turn_owner_id):
                    return False, "BASTION OF FAITH secondary choice is no longer in the same turn."
        if str(payload.get("action", "") or "").strip().lower() == "skip":
            return True, ""
        target_id = str(payload.get("target_unit_id") or payload.get("unit_id") or "").strip()
        if not target_id:
            return False, "BASTION OF FAITH secondary choice requires a target unit or None."
        target_unit = self._as_resolve_game_unit(game, target_id)
        if target_unit is None:
            return False, "BASTION OF FAITH secondary target was not found."
        target_root = self._as_root(target_unit)
        if target_root is None:
            return False, "BASTION OF FAITH secondary target was not found."
        allowed_ids = {str(v or "").strip() for v in list(candidate_unit_ids or []) if str(v or "").strip()}
        target_root_id = self._as_sort_key(target_root)
        if allowed_ids and target_root_id not in allowed_ids:
            return False, "BASTION OF FAITH secondary target is no longer eligible."
        if not self._as_owned_by_player(target_root, self.player):
            return False, "BASTION OF FAITH secondary target must belong to you."
        if not self._as_on_battlefield(target_root):
            return False, "BASTION OF FAITH secondary target must be on the battlefield."
        if bool(self._unit_cannot_be_target_of_stratagem(target_root)):
            return False, "BASTION OF FAITH secondary target can no longer be selected."
        if not self._champions_of_faith_is_celestian_sacresants(target_root):
            return False, "BASTION OF FAITH secondary target must be a Celestian Sacresants unit."
        if self._as_is_battle_shocked(target_root):
            return False, "BASTION OF FAITH secondary target cannot be Battle-shocked."
        if not unit_within_range_of_unit(primary_root, target_root, 6.0, use_attached_aggregate=True):
            return False, "BASTION OF FAITH secondary target must be within 6\" of the primary unit."
        resolved_name = str(stratagem_name or payload.get("stratagem_name", "") or "").strip().upper()
        if resolved_name and resolved_name != "BASTION OF FAITH":
            return False, "BASTION OF FAITH secondary choice payload does not match the stratagem."
        return True, ""

    def apply_champions_of_faith_bastion_secondary_choice(
        self,
        primary_unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        turn: int = 0,
        turn_owner_id: str = "",
        stratagem_name: str = "",
        candidate_unit_ids: Optional[list[str]] = None,
    ) -> Any:
        valid, _reason = self.validate_champions_of_faith_bastion_secondary_choice(
            primary_unit,
            payload,
            game=game,
            player=player,
            phase_name=phase_name,
            turn=turn,
            turn_owner_id=turn_owner_id,
            stratagem_name=stratagem_name,
            candidate_unit_ids=candidate_unit_ids,
        )
        if not valid:
            return None
        primary_root = self._as_root(primary_unit)
        if primary_root is None:
            return None
        if str(payload.get("action", "") or "").strip().lower() == "skip":
            return {
                "primary_unit_id": self._as_sort_key(primary_root),
                "primary_unit_name": str(getattr(primary_root, "name", "Unit") or "Unit"),
                "skipped": True,
                "stratagem_name": str(stratagem_name or "BASTION OF FAITH"),
            }
        target_id = str(payload.get("target_unit_id") or payload.get("unit_id") or "").strip()
        target_unit = self._as_resolve_game_unit(game, target_id)
        target_root = self._as_root(target_unit)
        if target_root is None:
            return None
        self._append_defensive_effect(
            target_root,
            "defensive_hit_mods",
            {
                "value": 1,
                "attack_type": "melee",
                "expires_phase": self._as_phase_key(phase_name or "Fight phase"),
                "source": str(stratagem_name or "BASTION OF FAITH"),
            },
        )
        return {
            "primary_unit_id": self._as_sort_key(primary_root),
            "primary_unit_name": str(getattr(primary_root, "name", "Unit") or "Unit"),
            "target_unit_id": self._as_sort_key(target_root),
            "target_unit_name": str(getattr(target_root, "name", "Unit") or "Unit"),
            "skipped": False,
            "stratagem_name": str(stratagem_name or "BASTION OF FAITH"),
        }

    def _as_battlefield_units(
        self,
        *,
        require_character: bool = False,
        require_infantry_or_walker: bool = False,
        require_vehicle: bool = False,
        require_not_fought: bool = False,
        require_targetable: bool = True,
    ) -> list[Any]:
        if not self._is_hallowed_martyrs():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._as_root(unit)
            if root is None:
                continue
            uid = self._as_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._as_on_battlefield(root):
                continue
            if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            if require_character and not self._is_adepta_sororitas_character(root):
                continue
            if require_infantry_or_walker and not self._is_adepta_sororitas_infantry_or_walker(root):
                continue
            if require_vehicle and not self._is_adepta_sororitas_vehicle(root):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._as_sort_key)

    def _hallowed_righteous_vengeance_candidates(self) -> list[Any]:
        return self._as_battlefield_units(require_not_fought=True, require_targetable=True)

    def _hallowed_suffering_and_sacrifice_candidates(self) -> list[Any]:
        return self._as_battlefield_units(require_infantry_or_walker=True, require_targetable=True)

    def _hallowed_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        enemy_unit: Any = None,
        destroyed_model_id: str = "",
        unit: Any = None,
    ) -> bool:
        unit_id = self._as_sort_key(self._as_root(unit)) if unit is not None else ""
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name):
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != str(phase_name or "").strip().lower():
                continue
            if enemy_unit is not None and reaction.get("enemy_unit") is not enemy_unit:
                continue
            if destroyed_model_id:
                if str(reaction.get("destroyed_model_id", "") or "") != str(destroyed_model_id):
                    continue
            if unit_id:
                rid = self._as_sort_key(self._as_root(reaction.get("unit") or reaction.get("target_unit")))
                if rid != unit_id:
                    continue
            return True
        return False

    def _as_praise_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        snapshots = getattr(self, "_as_praise_targets_before", None)
        if not isinstance(snapshots, dict):
            snapshots = {}
            self._as_praise_targets_before = snapshots
        return snapshots

    def _as_divine_pending(self) -> list[dict[str, Any]]:
        pending = getattr(self, "_as_divine_intervention_pending", None)
        if not isinstance(pending, list):
            pending = []
            self._as_divine_intervention_pending = pending
        return pending

    def _as_divine_used_units(self) -> set[str]:
        used = getattr(self, "_as_divine_intervention_used_unit_ids", None)
        if not isinstance(used, set):
            used = set()
            self._as_divine_intervention_used_unit_ids = used
        return used

    def _as_miracle_dice_manager(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "acts_of_faith", None) if army is not None else None

    def _queue_army_of_faith_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_army_of_faith():
            return
        if player is self.player:
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("ANGELIC DESCENT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._army_of_faith_angelic_descent_candidates()
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return
        payload = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_adepta_sororitas_phase_start_reaction(
        self,
        *,
        stratagem_name: str,
        phase_name: str,
        candidates: list[Any],
    ) -> None:
        if not candidates:
            return
        stratagem = self.get_by_name(stratagem_name)
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        if self._hallowed_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name=phase_name,
        ):
            return
        payload = {
            "event": "phase_start",
            "phase": phase_name,
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_army_of_faith_phase_start_reaction(
        self,
        *,
        stratagem_name: str,
        phase_name: str,
        candidates: list[Any],
    ) -> None:
        self._queue_adepta_sororitas_phase_start_reaction(
            stratagem_name=stratagem_name,
            phase_name=phase_name,
            candidates=candidates,
        )

    def _queue_army_of_faith_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_army_of_faith():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key == "COMMAND_PHASE":
            self._queue_army_of_faith_phase_start_reaction(
                stratagem_name="LIGHT OF THE EMPEROR",
                phase_name="Command phase",
                candidates=self._army_of_faith_light_of_the_emperor_candidates(),
            )
            return
        if phase_key == "SHOOTING_PHASE":
            if player is not self.player:
                return
            self._queue_army_of_faith_phase_start_reaction(
                stratagem_name="DIVINE GUIDANCE",
                phase_name="Shooting phase",
                candidates=self._army_of_faith_divine_guidance_candidates(phase_name="Shooting phase"),
            )
            return
        if phase_key != "FIGHT_PHASE":
            return
        self._queue_army_of_faith_phase_start_reaction(
            stratagem_name="DIVINE GUIDANCE",
            phase_name="Fight phase",
            candidates=self._army_of_faith_divine_guidance_candidates(phase_name="Fight phase"),
        )
        self._queue_army_of_faith_phase_start_reaction(
            stratagem_name="FAITH AND FURY",
            phase_name="Fight phase",
            candidates=self._army_of_faith_faith_and_fury_candidates(),
        )

    def _queue_bringers_of_flame_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_bringers_of_flame():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key == "SHOOTING_PHASE":
            if player is not self.player:
                return
            self._queue_adepta_sororitas_phase_start_reaction(
                stratagem_name="CLEANSING FLAMES",
                phase_name="Shooting phase",
                candidates=self._bringers_of_flame_cleansing_flames_candidates(),
            )
            self._queue_adepta_sororitas_phase_start_reaction(
                stratagem_name="RITES OF FIRE",
                phase_name="Shooting phase",
                candidates=self._bringers_of_flame_rites_of_fire_candidates(),
            )
            return
        if phase_key != "FIGHT_PHASE":
            return
        self._queue_adepta_sororitas_phase_start_reaction(
            stratagem_name="RIGHTEOUS BLOWS",
            phase_name="Fight phase",
            candidates=self._bringers_of_flame_righteous_blows_candidates(),
        )

    def _queue_champions_of_faith_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_champions_of_faith():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key == "SHOOTING_PHASE":
            if player is not self.player:
                return
            self._queue_adepta_sororitas_phase_start_reaction(
                stratagem_name="SUFFER NOT THE UNFAITHFUL",
                phase_name="Shooting phase",
                candidates=self._champions_of_faith_suffer_not_the_unfaithful_candidates(phase_name="Shooting phase"),
            )
            return
        if phase_key != "FIGHT_PHASE":
            return
        self._queue_adepta_sororitas_phase_start_reaction(
            stratagem_name="PATH OF THE RIGHTEOUS",
            phase_name="Fight phase",
            candidates=self._champions_of_faith_path_of_the_righteous_candidates(),
        )
        self._queue_adepta_sororitas_phase_start_reaction(
            stratagem_name="SUFFER NOT THE UNFAITHFUL",
            phase_name="Fight phase",
            candidates=self._champions_of_faith_suffer_not_the_unfaithful_candidates(phase_name="Fight phase"),
        )
        self._queue_adepta_sororitas_phase_start_reaction(
            stratagem_name="TO THE HEART OF HERESY",
            phase_name="Fight phase",
            candidates=self._champions_of_faith_to_the_heart_of_heresy_candidates(),
        )

    def _queue_penitent_host_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_penitent_host():
            return
        self._penitent_host_devout_targets().clear()
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        self._queue_adepta_sororitas_phase_start_reaction(
            stratagem_name="PASSION OF THE PENITENT",
            phase_name="Fight phase",
            candidates=self._penitent_host_passion_of_the_penitent_candidates(),
        )

    def _queue_army_of_faith_blinding_radiance_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_army_of_faith():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip()
        phase_lower = self._as_phase_name_lower(phase_name)
        if phase_lower not in {"shooting phase", "fight phase"}:
            return
        if self._as_owned_by_player(attacking_unit, self.player):
            return
        stratagem = self.get_by_name("BLINDING RADIANCE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._army_of_faith_blinding_radiance_candidates(target_units=target_units)
        if not candidates:
            return
        event_name = "shooting_targets_selected" if phase_lower == "shooting phase" else "fight_targets_selected"
        if self._hallowed_reaction_already_queued(
            event_name=event_name,
            stratagem_name=stratagem.name,
            phase_name=phase_name,
            enemy_unit=attacking_unit,
        ):
            return
        payload = {
            "event": event_name,
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_army_of_faith_shield_of_faith_reactions(
        self,
        *,
        target_unit: Any,
        attacker_unit: Any,
        target_model: Any,
        phase_name: str,
    ) -> None:
        if target_unit is None or not self._is_army_of_faith():
            return
        root = self._as_root(target_unit)
        if root is None or not self._as_owned_by_player(root, self.player):
            return
        if not self._is_adepta_sororitas_unit(root):
            return
        stratagem = self.get_by_name("SHIELD OF FAITH")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        resolved_phase = str(phase_name or self._current_phase_name or "").strip() or "Any phase"
        candidates = self._army_of_faith_shield_of_faith_candidates(source_unit=root)
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="mortal_wound_allocated",
            stratagem_name=stratagem.name,
            phase_name=resolved_phase,
            unit=root,
        ):
            return
        payload = {
            "event": "mortal_wound_allocated",
            "phase_name": resolved_phase,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "source_unit": root,
            "attacking_unit": attacker_unit,
            "target_model": target_model,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_champions_of_faith_shield_of_denial_reactions(
        self,
        *,
        target_unit: Any,
        attacker_unit: Any,
        target_model: Any,
        phase_name: str,
    ) -> None:
        if target_unit is None or not self._is_champions_of_faith():
            return
        root = self._as_root(target_unit)
        if root is None or not self._as_owned_by_player(root, self.player):
            return
        if not self._is_adepta_sororitas_unit(root):
            return
        stratagem = self.get_by_name("SHIELD OF DENIAL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        resolved_phase = str(phase_name or self._current_phase_name or "").strip() or "Any phase"
        candidates = self._champions_of_faith_shield_of_denial_candidates(source_unit=root)
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="mortal_wound_allocated",
            stratagem_name=stratagem.name,
            phase_name=resolved_phase,
            unit=root,
        ):
            return
        payload = {
            "event": "mortal_wound_allocated",
            "phase_name": resolved_phase,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "source_unit": root,
            "attacking_unit": attacker_unit,
            "target_model": target_model,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_hallowed_martyrs_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_hallowed_martyrs():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("SUFFERING AND SACRIFICE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._hallowed_suffering_and_sacrifice_candidates()
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return
        payload = {
            "event": "phase_start",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _capture_hallowed_martyrs_praise_the_fallen_targets(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_hallowed_martyrs():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "shooting phase":
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            return
        if self._as_owned_by_player(attacking_unit, self.player):
            return
        stratagem = self.get_by_name("PRAISE THE FALLEN")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_key = self._attacker_unit_key(attacking_unit)
        if not attacker_key:
            return
        snapshot_by_unit: dict[str, dict[str, Any]] = {}
        for unit in list(target_units or []):
            root = self._as_root(unit)
            if root is None:
                continue
            if not self._as_is_alive(root):
                continue
            if not self._as_on_battlefield(root):
                continue
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            uid = self._as_sort_key(root)
            if not uid:
                continue
            snapshot_by_unit[uid] = {
                "unit": root,
                "models_before": self._as_alive_model_count(root),
                "wounds_before": self._as_total_current_wounds(root),
            }
        if not snapshot_by_unit:
            return
        snapshots = self._as_praise_snapshots()
        snapshots[attacker_key] = snapshot_by_unit

    def _queue_hallowed_martyrs_fight_target_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_hallowed_martyrs():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "fight phase":
            return
        if self._as_owned_by_player(attacking_unit, self.player):
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            return
        stratagem = self.get_by_name("SPIRIT OF THE MARTYR")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._as_root(unit)
            if root is None:
                continue
            uid = self._as_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._as_is_alive(root):
                continue
            if not self._as_on_battlefield(root):
                continue
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._as_sort_key)
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            enemy_unit=attacking_unit,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacking_unit,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_champions_of_faith_fight_target_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_champions_of_faith():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "fight phase":
            return
        if self._as_owned_by_player(attacking_unit, self.player):
            return
        stratagem = self.get_by_name("BASTION OF FAITH")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._champions_of_faith_bastion_of_faith_candidates(target_units=target_units)
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            enemy_unit=attacking_unit,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacking_unit,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_penitent_host_shooting_target_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_penitent_host():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "shooting phase":
            return
        if self._as_owned_by_player(attacking_unit, self.player):
            return
        attacker_root = self._as_root(attacking_unit)
        if attacker_root is None:
            return
        attacker_id = self._as_sort_key(attacker_root)
        if attacker_id:
            snapshots = self._penitent_host_devout_targets()
            snapshots[attacker_id] = list(target_units or [])
        stratagem = self.get_by_name("PURITY OF SUFFERING")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._penitent_host_purity_of_suffering_candidates(target_units=target_units)
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_root,
        ):
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_penitent_host_fight_target_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_penitent_host():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "fight phase":
            return
        if self._as_owned_by_player(attacking_unit, self.player):
            return
        attacker_root = self._as_root(attacking_unit)
        if attacker_root is None:
            return
        stratagem = self.get_by_name("PURITY OF SUFFERING")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._penitent_host_purity_of_suffering_candidates(target_units=target_units)
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            enemy_unit=attacker_root,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_hallowed_martyrs_shooting_resolved_reactions(self, *, attacker_unit: Any, hits_by_target: Any = None) -> None:
        if attacker_unit is None or not self._is_hallowed_martyrs():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "shooting phase":
            return
        if self._as_owned_by_player(attacker_unit, self.player):
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            return
        stratagem = self.get_by_name("PRAISE THE FALLEN")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_key = self._attacker_unit_key(attacker_unit)
        if not attacker_key:
            return
        snapshots = self._as_praise_snapshots()
        snapshot_by_unit = snapshots.pop(attacker_key, {})
        if not isinstance(snapshot_by_unit, dict) or not snapshot_by_unit:
            return
        candidates: list[Any] = []
        for entry in list(snapshot_by_unit.values()):
            if not isinstance(entry, dict):
                continue
            root = self._as_root(entry.get("unit"))
            if root is None:
                continue
            if not self._as_is_alive(root):
                continue
            if not self._as_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            before = int(entry.get("models_before", 0) or 0)
            after = self._as_alive_model_count(root)
            if after >= before:
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._as_sort_key)
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="unit_shooting_resolved",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_unit,
        ):
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_unit,
            "attacking_unit": attacker_unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_bringers_of_flame_move_started_reactions(self, *, unit: Any, action: Any) -> None:
        if unit is None or not self._is_bringers_of_flame():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "movement phase":
            return
        if str(action or "").strip().lower() != "advance":
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is not self.player:
            return
        root = self._as_root(unit)
        if root is None:
            return
        if not self._as_owned_by_player(root, self.player):
            return
        if not self._as_on_battlefield(root):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return
        if not self._is_adepta_sororitas_transport(root):
            return
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "moved_this_round", False)):
            return
        if bool(getattr(round_state, "advanced_this_round", False)):
            return
        if bool(getattr(round_state, "fell_back_this_round", False)):
            return
        stratagem = self.get_by_name("CARRY FORTH THE FAITHFUL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_started":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem.name or "").strip().upper():
                continue
            if reaction.get("unit") is root:
                return
        payload = {
            "event": "unit_move_started",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "candidates": [root],
            "action": "advance",
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_champions_of_faith_move_started_reactions(self, *, unit: Any, action: Any) -> None:
        if unit is None or not self._is_champions_of_faith():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "movement phase":
            return
        if str(action or "").strip().lower() != "fall_back":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        root = self._as_root(unit)
        if root is None:
            return
        if not self._as_owned_by_player(root, self.player):
            return
        if not self._as_on_battlefield(root):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return
        if not self._is_adepta_sororitas_unit(root):
            return
        stratagem = self.get_by_name("INDEFATIGABLE DEDICATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._champions_of_faith_indefatigable_dedication_candidates(moved_unit=root, action=action)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_started":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem.name or "").strip().upper():
                continue
            if reaction.get("unit") is root:
                return
        payload = {
            "event": "unit_move_started",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "candidates": candidates,
            "action": "fall_back",
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_penitent_host_move_started_reactions(self, *, unit: Any, action: Any) -> None:
        if unit is None or not self._is_penitent_host():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "movement phase":
            return
        if str(action or "").strip().lower() != "advance":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        root = self._as_root(unit)
        if root is None:
            return
        if not self._as_owned_by_player(root, self.player):
            return
        if not self._as_on_battlefield(root):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return
        stratagem = self.get_by_name("LASH OF GUILT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._penitent_host_lash_of_guilt_candidates(moved_unit=root, action=action)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_started":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem.name or "").strip().upper():
                continue
            if reaction.get("unit") is root:
                return
        payload = {
            "event": "unit_move_started",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "candidates": candidates,
            "action": "advance",
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_penitent_host_move_end_reactions(self, *, unit: Any, action: Any) -> None:
        if unit is None or not self._is_penitent_host():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "movement phase":
            return
        if str(action or "").strip().lower() != "fall_back":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        root = self._as_root(unit)
        if root is None:
            return
        if not self._as_owned_by_player(root, self.player):
            return
        if not self._as_on_battlefield(root):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return
        stratagem = self.get_by_name("BOUNDLESS ZEAL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._penitent_host_boundless_zeal_candidates(moved_unit=root, action=action)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_ended":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem.name or "").strip().upper():
                continue
            if reaction.get("unit") is root:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "candidates": candidates,
            "action": "fall_back",
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_bringers_of_flame_shooting_resolved_reactions(self, *, attacker_unit: Any, hits_by_target: Any = None) -> None:
        if attacker_unit is None or not self._is_bringers_of_flame():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "shooting phase":
            return
        if self._as_owned_by_player(attacker_unit, self.player):
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            return
        stratagem = self.get_by_name("BLAZING IRE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for target_unit in list((hits_by_target or {}).keys() if isinstance(hits_by_target, dict) else []):
            root = self._as_root(target_unit)
            if root is None:
                continue
            uid = self._as_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._as_on_battlefield(root):
                continue
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._is_adepta_sororitas_transport(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            embarked = list(getattr(root, "transport_passengers", []) or [])
            if not embarked:
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._as_sort_key)
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="unit_shooting_resolved",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_unit,
        ):
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_unit,
            "attacking_unit": attacker_unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_penitent_host_shooting_resolved_reactions(self, *, attacker_unit: Any) -> None:
        if attacker_unit is None or not self._is_penitent_host():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "shooting phase":
            return
        if self._as_owned_by_player(attacker_unit, self.player):
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            return
        attacker_root = self._as_root(attacker_unit)
        if attacker_root is None:
            return
        stratagem = self.get_by_name("DEVOUT FANATICISM")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_id = self._as_sort_key(attacker_root)
        targets = []
        if attacker_id:
            targets = list(self._penitent_host_devout_targets().pop(attacker_id, []) or [])
        candidates = self._penitent_host_purity_of_suffering_candidates(target_units=targets)
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="unit_shooting_resolved",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_root,
        ):
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_hallowed_martyrs_model_destroyed_reactions(self, *, unit: Any, model: Any) -> None:
        if unit is None or model is None or not self._is_hallowed_martyrs():
            return
        root = self._as_root(unit)
        if root is None:
            return
        if not self._as_owned_by_player(root, self.player):
            return
        if not self._is_adepta_sororitas_vehicle(root):
            return
        has_deadly_demise = getattr(root, "has_deadly_demise", None)
        if not callable(has_deadly_demise):
            return
        try:
            has_deadly, _damage_dice = has_deadly_demise()
        except Exception:
            has_deadly = False
        if not has_deadly:
            return
        stratagem = self.get_by_name("SANCTIFIED IMMOLATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "")
        destroyed_model_id = str(get_entity_id(model) or "")
        if self._hallowed_reaction_already_queued(
            event_name="model_destroyed_before_removal",
            stratagem_name=stratagem.name,
            phase_name=phase_name,
            destroyed_model_id=destroyed_model_id,
        ):
            return
        payload = {
            "event": "model_destroyed_before_removal",
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "destroyed_unit": root,
            "destroyed_model": model,
            "destroyed_model_id": destroyed_model_id,
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_hallowed_martyrs_unit_destroyed_reactions(self, *, unit: Any, last_model: Any) -> None:
        if unit is None or not self._is_hallowed_martyrs():
            return
        root = self._as_root(unit)
        if root is None:
            return
        if not self._as_owned_by_player(root, self.player):
            return
        if not self._is_adepta_sororitas_character(root):
            return
        if self._as_is_saint_celestine(root):
            return
        unit_id = self._as_sort_key(root)
        if unit_id and unit_id in self._as_divine_used_units():
            return
        acts_mgr = self._as_miracle_dice_manager()
        pool = list(getattr(acts_mgr, "miracle_dice", []) or []) if acts_mgr is not None else []
        if not pool:
            return
        stratagem = self.get_by_name("DIVINE INTERVENTION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "")
        if self._hallowed_reaction_already_queued(
            event_name="unit_destroyed",
            stratagem_name=stratagem.name,
            phase_name=phase_name,
            unit=root,
        ):
            return
        destroyed_position = None
        if last_model is not None:
            get_location = getattr(last_model, "get_location", None)
            if callable(get_location):
                try:
                    destroyed_position = get_location()
                except Exception:
                    destroyed_position = None
        payload = {
            "event": "unit_destroyed",
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "destroyed_unit": root,
            "destroyed_model": last_model,
            "destroyed_position": destroyed_position,
            "miracle_dice_pool": list(pool),
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_penitent_host_unit_destroyed_reactions(self, *, unit: Any, last_model: Any) -> None:
        if unit is None or not self._is_penitent_host():
            return
        root = self._as_root(unit)
        if root is None:
            return
        if not self._as_owned_by_player(root, self.player):
            return
        if not self._is_penitent_unit(root):
            return
        stratagem = self.get_by_name("FINAL REDEMPTION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._penitent_host_objective_candidates(unit=root, last_model=last_model)
        if not candidates:
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "")
        if self._hallowed_reaction_already_queued(
            event_name="unit_destroyed",
            stratagem_name=stratagem.name,
            phase_name=phase_name,
            unit=root,
        ):
            return
        payload = {
            "event": "unit_destroyed",
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "objective_candidates": candidates,
        }
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_hallowed_martyrs_fight_phase_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        for unit in list(getattr(army, "units", []) or []):
            root = self._as_root(unit)
            if root is None:
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            for key in (
                "righteous_vengeance_active",
                "righteous_vengeance_expires_phase",
                "righteous_vengeance_turn_owner",
                "righteous_vengeance_turn",
                "righteous_vengeance_source",
                "suffering_and_sacrifice_active",
                "suffering_and_sacrifice_expires_phase",
                "suffering_and_sacrifice_turn_owner",
                "suffering_and_sacrifice_turn",
                "suffering_and_sacrifice_source",
                "spirit_of_martyr_active",
                "spirit_of_martyr_expires_phase",
                "spirit_of_martyr_turn_owner",
                "spirit_of_martyr_turn",
                "spirit_of_martyr_source",
            ):
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if changed:
                root.special_rules = sr

    def _resolve_hallowed_martyrs_phase_end(self, *, player: Any, phase: Any) -> None:
        self._cleanup_hallowed_martyrs_fight_phase_effects(phase=phase)
        self._resolve_hallowed_martyrs_divine_intervention_returns(phase=phase)

    def _resolve_hallowed_martyrs_divine_intervention_returns(self, *, phase: Any) -> None:
        pending = self._as_divine_pending()
        if not pending:
            return
        phase_key = self._as_phase_key(getattr(phase, "name", "") or getattr(self, "_current_phase_name", ""))
        if not phase_key:
            return
        remaining: list[dict[str, Any]] = []
        for entry in list(pending):
            if not isinstance(entry, dict):
                continue
            trigger_key = self._as_phase_key(entry.get("trigger_phase_key") or entry.get("trigger_phase_name") or "")
            if trigger_key and trigger_key != phase_key:
                remaining.append(entry)
                continue
            root = self._as_root(entry.get("unit"))
            model = entry.get("model")
            if root is None or model is None:
                continue
            discarded = int(entry.get("discard_count", 0) or 0)
            if discarded < 1:
                discarded = 1
            try:
                rolled = dice_module.get_roll("D3")
            except Exception:
                rolled = 0
            wounds_remaining = int(rolled + discarded)
            try:
                starting_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 1)) or 1)
            except Exception:
                starting_wounds = 1
            wounds_remaining = max(1, min(int(starting_wounds), int(wounds_remaining)))
            in_unit = False
            try:
                in_unit = model in list(getattr(root, "models", []) or [])
            except Exception:
                in_unit = False
            if not in_unit:
                try:
                    if model in list(getattr(root, "models_lost", []) or []):
                        root.models_lost.remove(model)
                except Exception:
                    pass
                try:
                    if hasattr(root, "add_model"):
                        root.add_model(model)
                    else:
                        root.models.append(model)
                except Exception:
                    try:
                        root.models.append(model)
                    except Exception:
                        pass
            try:
                model.wounds = int(wounds_remaining)
            except Exception:
                try:
                    model._wounds = int(wounds_remaining)
                except Exception:
                    pass
            try:
                setattr(model, "_on_death_reactions_resolved", False)
                setattr(model, "_fight_on_death_used", False)
                setattr(model, "_shoot_on_death_used", False)
            except Exception:
                pass
            pos = self._as_find_divine_intervention_position(
                unit=root,
                model=model,
                origin=entry.get("destroyed_position"),
            )
            if pos is not None:
                try:
                    model.set_location(float(pos[0]), float(pos[1]), float(pos[2]), float(pos[3]))
                except Exception:
                    pass
            root.deployed = True
            try:
                root.reserve_status = "deployed"
            except Exception:
                pass
            game_map = getattr(self.game, "map", None) if self.game is not None else None
            if game_map is not None:
                units = list(getattr(game_map, "units", []) or [])
                if root not in units:
                    try:
                        if not bool(game_map.place_unit(root)):
                            game_map.units.append(root)
                    except Exception:
                        game_map.units.append(root)
            logger.info(
                f"INFO: DIVINE INTERVENTION: returned {getattr(model, 'name', 'Model')} "
                f"with {int(wounds_remaining)} wound(s)."
            )
        self._as_divine_intervention_pending = remaining

    def _as_position_is_valid_for_divine_intervention(
        self,
        *,
        unit: Any,
        model: Any,
        x: float,
        y: float,
        z: float,
        facing: float,
    ) -> bool:
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None or unit is None or model is None:
            return False
        get_location = getattr(model, "get_location", None)
        previous = None
        if callable(get_location):
            try:
                previous = get_location()
            except Exception:
                previous = None
        try:
            model.set_location(float(x), float(y), float(z), float(facing))
        except Exception:
            return False
        try:
            if not bool(game_map.is_within_boundary(model)):
                return False
            if bool(game_map.check_collision_with_terrain(model)):
                return False
            if bool(game_map.check_collision_with_other_friendly_units(model)):
                return False
            if bool(game_map.check_collision_with_other_enemy_units(model)):
                return False
            for other in list(getattr(unit, "models", []) or []):
                if other is model:
                    continue
                other_alive = getattr(other, "is_alive", None)
                if callable(other_alive):
                    try:
                        if not bool(other_alive()):
                            continue
                    except Exception:
                        continue
                elif not bool(other_alive):
                    continue
                try:
                    if model.model_base.collides_with(other.model_base):
                        return False
                except Exception:
                    continue
            for enemy in list(game_map.get_enemy_units(unit) or []):
                if enemy is None:
                    continue
                enemy_root = self._as_root(enemy)
                if enemy_root is None:
                    continue
                if not self._as_is_alive(enemy_root):
                    continue
                try:
                    if bool(game_map.is_within_engagement_range(unit, enemy_root)):
                        return False
                except Exception:
                    continue
            return True
        finally:
            if previous is not None:
                try:
                    model.set_location(
                        float(previous[0]),
                        float(previous[1]),
                        float(previous[2]),
                        float(previous[3]),
                    )
                except Exception:
                    pass

    def _as_find_divine_intervention_position(self, *, unit: Any, model: Any, origin: Any) -> Optional[tuple[float, float, float, float]]:
        if unit is None or model is None:
            return None
        x0, y0, z0, facing0 = (0.0, 0.0, 0.0, 0.0)
        origin_tuple = None
        if isinstance(origin, (list, tuple)) and len(origin) >= 4:
            origin_tuple = origin
        if origin_tuple is None:
            get_location = getattr(model, "get_location", None)
            if callable(get_location):
                try:
                    loc = get_location()
                    if isinstance(loc, (list, tuple)) and len(loc) >= 4:
                        origin_tuple = loc
                except Exception:
                    origin_tuple = None
        if origin_tuple is not None:
            try:
                x0 = float(origin_tuple[0])
                y0 = float(origin_tuple[1])
                z0 = float(origin_tuple[2])
                facing0 = float(origin_tuple[3])
            except Exception:
                x0, y0, z0, facing0 = (0.0, 0.0, 0.0, 0.0)
        if self._as_position_is_valid_for_divine_intervention(
            unit=unit,
            model=model,
            x=x0,
            y=y0,
            z=z0,
            facing=facing0,
        ):
            return (x0, y0, z0, facing0)
        max_radius = 12.0
        step = 0.5
        ring = step
        while ring <= max_radius + 1e-6:
            deg = 0
            while deg < 360:
                angle = math.radians(float(deg))
                x = float(x0 + math.cos(angle) * ring)
                y = float(y0 + math.sin(angle) * ring)
                if self._as_position_is_valid_for_divine_intervention(
                    unit=unit,
                    model=model,
                    x=x,
                    y=y,
                    z=z0,
                    facing=facing0,
                ):
                    return (x, y, z0, facing0)
                deg += 15
            ring += step
        return None

    def _cleanup_champions_of_faith_phase_end_effects(self, *, phase: Any = None) -> None:
        if not self._is_champions_of_faith():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        active_turn_owner_id = self._as_current_turn_owner_id()
        current_turn = self._as_current_turn()
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._as_root(unit)
            if root is None:
                continue
            root_id = self._as_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            path_owner = str(sr.get("champions_of_faith_path_of_the_righteous_turn_owner", "") or "")
            path_turn = int(sr.get("champions_of_faith_path_of_the_righteous_turn", 0) or 0)
            if (
                sr.get("champions_of_faith_path_of_the_righteous_active") is True
                and path_owner
                and active_turn_owner_id
                and path_owner == active_turn_owner_id
                and (not path_turn or not current_turn or path_turn == current_turn)
            ):
                for key in (
                    "champions_of_faith_path_of_the_righteous_active",
                    "champions_of_faith_path_of_the_righteous_turn_owner",
                    "champions_of_faith_path_of_the_righteous_turn",
                    "champions_of_faith_path_of_the_righteous_source",
                    "stratagem_pile_in_distance_override",
                    "stratagem_consolidate_distance_override",
                    "stratagem_choreographer_of_war_source",
                    "stratagem_choreographer_of_war_expires_phase",
                    "stratagem_choreographer_of_war_turn_owner",
                    "stratagem_choreographer_of_war_turn",
                ):
                    sr.pop(key, None)
                cache = getattr(root, "_ability_cache", None)
                if isinstance(cache, dict):
                    cache.pop("choreographer_of_war_source", None)
            retreat_owner = str(sr.get("champions_of_faith_indefatigable_dedication_turn_owner", "") or "")
            retreat_turn = int(sr.get("champions_of_faith_indefatigable_dedication_turn", 0) or 0)
            if (
                sr.get("champions_of_faith_indefatigable_dedication_active") is True
                and retreat_owner
                and active_turn_owner_id
                and retreat_owner == active_turn_owner_id
                and (not retreat_turn or not current_turn or retreat_turn == current_turn)
            ):
                for key in (
                    "champions_of_faith_indefatigable_dedication_active",
                    "champions_of_faith_indefatigable_dedication_turn_owner",
                    "champions_of_faith_indefatigable_dedication_turn",
                    "champions_of_faith_indefatigable_dedication_source",
                    "champions_of_faith_indefatigable_dedication_can_charge",
                ):
                    sr.pop(key, None)
                cache = getattr(root, "_ability_cache", None)
                if isinstance(cache, dict):
                    cache.pop("fell_back_and_shoot", None)
            root.special_rules = sr

    def _cleanup_penitent_host_phase_end_effects(self, *, phase: Any = None) -> None:
        if not self._is_penitent_host():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name not in {"MOVEMENT_PHASE", "FIGHT_PHASE"}:
            return
        active_turn_owner_id = self._as_current_turn_owner_id()
        current_turn = self._as_current_turn()
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._as_root(unit)
            if root is None:
                continue
            root_id = self._as_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            if phase_name == "FIGHT_PHASE":
                lash_owner = str(sr.get("penitent_host_lash_of_guilt_turn_owner", "") or "")
                lash_turn = int(sr.get("penitent_host_lash_of_guilt_turn", 0) or 0)
                if (
                    sr.get("penitent_host_lash_of_guilt_active") is True
                    and lash_owner
                    and active_turn_owner_id
                    and lash_owner == active_turn_owner_id
                    and (not lash_turn or not current_turn or lash_turn == current_turn)
                ):
                    for key in (
                        "penitent_host_lash_of_guilt_active",
                        "penitent_host_lash_of_guilt_turn_owner",
                        "penitent_host_lash_of_guilt_turn",
                        "penitent_host_lash_of_guilt_source",
                    ):
                        sr.pop(key, None)
                    changed = True
                zeal_owner = str(sr.get("penitent_host_boundless_zeal_turn_owner", "") or "")
                zeal_turn = int(sr.get("penitent_host_boundless_zeal_turn", 0) or 0)
                if (
                    sr.get("penitent_host_boundless_zeal_active") is True
                    and zeal_owner
                    and active_turn_owner_id
                    and zeal_owner == active_turn_owner_id
                    and (not zeal_turn or not current_turn or zeal_turn == current_turn)
                ):
                    for key in (
                        "penitent_host_boundless_zeal_active",
                        "penitent_host_boundless_zeal_mode",
                        "penitent_host_boundless_zeal_turn_owner",
                        "penitent_host_boundless_zeal_turn",
                        "penitent_host_boundless_zeal_source",
                    ):
                        sr.pop(key, None)
                    changed = True
                passion_owner = str(sr.get("penitent_host_passion_of_the_penitent_turn_owner", "") or "")
                passion_turn = int(sr.get("penitent_host_passion_of_the_penitent_turn", 0) or 0)
                if (
                    sr.get("penitent_host_passion_of_the_penitent_active") is True
                    and passion_owner
                    and active_turn_owner_id
                    and passion_owner == active_turn_owner_id
                    and (not passion_turn or not current_turn or passion_turn == current_turn)
                ):
                    for key in (
                        "penitent_host_passion_of_the_penitent_active",
                        "penitent_host_passion_of_the_penitent_crit_threshold",
                        "penitent_host_passion_of_the_penitent_turn_owner",
                        "penitent_host_passion_of_the_penitent_turn",
                        "penitent_host_passion_of_the_penitent_source",
                    ):
                        sr.pop(key, None)
                    changed = True
            if changed:
                cache = getattr(root, "_ability_cache", None)
                if isinstance(cache, dict):
                    cache.pop("fell_back_and_shoot", None)
                root.special_rules = sr

    def _use_adepta_sororitas_hallowed_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "BLAZING IRE":
            return self._use_bringers_of_flame_blazing_ire(stratagem, **kwargs)
        if name_u == "CARRY FORTH THE FAITHFUL":
            return self._use_bringers_of_flame_carry_forth_the_faithful(stratagem, **kwargs)
        if name_u == "CLEANSING FLAMES":
            return self._use_bringers_of_flame_cleansing_flames(stratagem, **kwargs)
        if name_u == "RIGHTEOUS BLOWS":
            return self._use_bringers_of_flame_righteous_blows(stratagem, **kwargs)
        if name_u == "RITES OF FIRE":
            return self._use_bringers_of_flame_rites_of_fire(stratagem, **kwargs)
        if name_u == "BOUNDLESS ZEAL":
            return self._use_penitent_host_boundless_zeal(stratagem, **kwargs)
        if name_u == "DEVOUT FANATICISM":
            return self._use_penitent_host_devout_fanaticism(stratagem, **kwargs)
        if name_u == "FINAL REDEMPTION":
            return self._use_penitent_host_final_redemption(stratagem, **kwargs)
        if name_u == "LASH OF GUILT":
            return self._use_penitent_host_lash_of_guilt(stratagem, **kwargs)
        if name_u == "PASSION OF THE PENITENT":
            return self._use_penitent_host_passion_of_the_penitent(stratagem, **kwargs)
        if name_u == "PURITY OF SUFFERING":
            return self._use_penitent_host_purity_of_suffering(stratagem, **kwargs)
        if name_u == "BASTION OF FAITH":
            return self._use_champions_of_faith_bastion_of_faith(stratagem, **kwargs)
        if name_u == "INDEFATIGABLE DEDICATION":
            return self._use_champions_of_faith_indefatigable_dedication(stratagem, **kwargs)
        if name_u == "PATH OF THE RIGHTEOUS":
            return self._use_champions_of_faith_path_of_the_righteous(stratagem, **kwargs)
        if name_u == "SHIELD OF DENIAL":
            return self._use_champions_of_faith_shield_of_denial(stratagem, **kwargs)
        if name_u == "SUFFER NOT THE UNFAITHFUL":
            return self._use_champions_of_faith_suffer_not_the_unfaithful(stratagem, **kwargs)
        if name_u == "TO THE HEART OF HERESY":
            return self._use_champions_of_faith_to_the_heart_of_heresy(stratagem, **kwargs)
        if name_u == "BLINDING RADIANCE":
            return self._use_army_of_faith_blinding_radiance(stratagem, **kwargs)
        if name_u == "DIVINE GUIDANCE":
            return self._use_army_of_faith_divine_guidance(stratagem, **kwargs)
        if name_u == "FAITH AND FURY":
            return self._use_army_of_faith_faith_and_fury(stratagem, **kwargs)
        if name_u == "LIGHT OF THE EMPEROR":
            return self._use_army_of_faith_light_of_the_emperor(stratagem, **kwargs)
        if name_u == "SHIELD OF FAITH":
            return self._use_army_of_faith_shield_of_faith(stratagem, **kwargs)
        if name_u == "ANGELIC DESCENT":
            return self._use_army_of_faith_angelic_descent(stratagem, **kwargs)
        if name_u == "RIGHTEOUS VENGEANCE":
            return self._use_hallowed_righteous_vengeance(stratagem, **kwargs)
        if name_u == "SUFFERING AND SACRIFICE":
            return self._use_hallowed_suffering_and_sacrifice(stratagem, **kwargs)
        if name_u == "SPIRIT OF THE MARTYR":
            return self._use_hallowed_spirit_of_the_martyr(stratagem, **kwargs)
        if name_u == "PRAISE THE FALLEN":
            return self._use_hallowed_praise_the_fallen(stratagem, **kwargs)
        if name_u == "SANCTIFIED IMMOLATION":
            return self._use_hallowed_sanctified_immolation(stratagem, **kwargs)
        if name_u == "DIVINE INTERVENTION":
            return self._use_hallowed_divine_intervention(stratagem, **kwargs)
        return None

    def _use_bringers_of_flame_blazing_ire(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_bringers_of_flame():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("transport_unit") or kwargs.get("transport")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if (unit is None or attacking_unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "BLAZING IRE":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BLAZING IRE: no target transport provided")
            return False
        root = self._as_root(unit)
        attacker_root = self._as_root(attacking_unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "shooting phase":
            logger.error("ERROR: BLAZING IRE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: BLAZING IRE: not opponent's Shooting phase")
            return False
        if candidates and not self._as_unit_in_candidates(root, candidates):
            logger.error("ERROR: BLAZING IRE: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: BLAZING IRE: target transport is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: BLAZING IRE: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_transport(root):
            logger.error("ERROR: BLAZING IRE: target must be an ADEPTA SORORITAS TRANSPORT")
            return False
        if attacker_root is not None and self._as_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: BLAZING IRE: attacker is not enemy")
            return False
        embarked_units = list(getattr(root, "transport_passengers", []) or [])
        if not embarked_units:
            logger.error("ERROR: BLAZING IRE: no embarked units")
            return False

        queue_fn = getattr(self.game, "_queue_transport_reactive_disembark_decisions", None) if self.game is not None else None
        if not callable(queue_fn):
            logger.error("ERROR: BLAZING IRE: reactive disembark decision queue unavailable")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        requests = list(
            queue_fn(
                player=self.player,
                transport=root,
                enemy_unit=attacker_root,
                ability={"name": str(stratagem.name or "BLAZING IRE")},
                trigger="unit_shooting_resolved",
                max_units=1,
            )
            or []
        )
        if not requests:
            logger.error("ERROR: BLAZING IRE: no disembark decision was queued")
            return False
        enemy_id = self._as_sort_key(attacker_root) if attacker_root is not None else ""
        for req in requests:
            req_ctx = dict(getattr(req, "context", {}) or {})
            req_ctx["reactive_disembark_then_shoot_enemy_only"] = True
            req_ctx["reactive_disembark_shoot_enemy_id"] = str(enemy_id or "")
            req_ctx["reactive_disembark_shoot_source"] = str(stratagem.name or "BLAZING IRE")
            req.context = req_ctx

        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BLAZING IRE: queued disembark decision and follow-up reactive shooting into the attacking unit."
        )
        return True

    def _use_bringers_of_flame_carry_forth_the_faithful(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_bringers_of_flame():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("transport_unit") or kwargs.get("transport")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: no target transport provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "movement phase":
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: not your Movement phase")
            return False
        if candidates and not self._as_unit_in_candidates(root, candidates):
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: target transport is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_transport(root):
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: target must be an ADEPTA SORORITAS TRANSPORT")
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "moved_this_round", False)) or bool(getattr(round_state, "advanced_this_round", False)):
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: target transport already moved")
            return False
        if bool(getattr(round_state, "fell_back_this_round", False)):
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: target transport already Fell Back")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False

        owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["carry_forth_the_faithful_active"] = True
        sr["carry_forth_the_faithful_turn_owner"] = owner_id
        sr["carry_forth_the_faithful_turn"] = int(turn)
        sr["carry_forth_the_faithful_source"] = str(stratagem.name or "CARRY FORTH THE FAITHFUL")
        sr["carry_forth_the_faithful_disembark_allow_after_advance"] = True
        sr["carry_forth_the_faithful_disembark_force_no_charge"] = True
        sr["stratagem_carry_forth_the_faithful_reroll_advance"] = True
        sr["stratagem_carry_forth_the_faithful_reroll_advance_owner"] = owner_id
        sr["stratagem_carry_forth_the_faithful_reroll_advance_turn"] = int(turn)
        root.special_rules = sr

        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CARRY FORTH THE FAITHFUL: %s can re-roll Advance; disembarking after Advance is allowed but those units cannot charge this turn.",
            getattr(root, "name", "Transport"),
        )
        return True

    def _use_bringers_of_flame_cleansing_flames(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_bringers_of_flame():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CLEANSING FLAMES: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "shooting phase":
            logger.error("ERROR: CLEANSING FLAMES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CLEANSING FLAMES: not your Shooting phase")
            return False
        eligible = candidates or self._bringers_of_flame_cleansing_flames_candidates()
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: CLEANSING FLAMES: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: CLEANSING FLAMES: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: CLEANSING FLAMES: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: CLEANSING FLAMES: target is not ADEPTA SORORITAS")
            return False
        if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: CLEANSING FLAMES: target has already shot")
            return False
        if not self._as_unit_has_torrent_ranged_weapon(root):
            logger.error("ERROR: CLEANSING FLAMES: target has no Torrent ranged weapons")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        phase_key = self._as_phase_key(kwargs.get("phase_name") or self._current_phase_name or "")
        for model in self._as_unit_models(root):
            if not self._as_model_is_alive(model):
                continue
            model_id = str(get_entity_id(model) or "")
            for profile in self._as_model_weapon_profiles(model, attack_type="ranged"):
                if not self._as_profile_has_keyword(profile, "TORRENT"):
                    continue
                lookup_name_fn = getattr(profile, "_temporary_weapon_lookup_name", None)
                weapon_name = lookup_name_fn() if callable(lookup_name_fn) else str(getattr(profile, "name", "") or "")
                if not weapon_name:
                    continue
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if not callable(set_keywords):
                    continue
                set_keywords(
                    key=f"bringers_of_flame_cleansing_flames:{self._as_sort_key(root)}:{model_id}:{weapon_name}",
                    weapon_name=weapon_name,
                    keywords=["DEVASTATING WOUNDS"],
                    source=str(stratagem.name or "CLEANSING FLAMES"),
                    expires_phase=phase_key,
                    attack_type="ranged",
                )
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CLEANSING FLAMES: %s gains [DEVASTATING WOUNDS] on Torrent ranged weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_bringers_of_flame_righteous_blows(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_bringers_of_flame():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RIGHTEOUS BLOWS: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: RIGHTEOUS BLOWS: wrong phase")
            return False
        eligible = candidates or self._bringers_of_flame_righteous_blows_candidates()
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: RIGHTEOUS BLOWS: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: RIGHTEOUS BLOWS: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: RIGHTEOUS BLOWS: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: RIGHTEOUS BLOWS: target is not ADEPTA SORORITAS")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: RIGHTEOUS BLOWS: target has already fought")
            return False
        if not self._as_unit_has_melee_weapon(root):
            logger.error("ERROR: RIGHTEOUS BLOWS: target has no melee weapons")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        phase_key = self._as_phase_key(kwargs.get("phase_name") or self._current_phase_name or "")
        for model in self._as_unit_models(root):
            if not self._as_model_is_alive(model):
                continue
            model_id = str(get_entity_id(model) or "")
            for profile in self._as_model_weapon_profiles(model, attack_type="melee"):
                lookup_name_fn = getattr(profile, "_temporary_weapon_lookup_name", None)
                weapon_name = lookup_name_fn() if callable(lookup_name_fn) else str(getattr(profile, "name", "") or "")
                if not weapon_name:
                    continue
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if not callable(set_keywords):
                    continue
                set_keywords(
                    key=f"bringers_of_flame_righteous_blows:{self._as_sort_key(root)}:{model_id}:{weapon_name}",
                    weapon_name=weapon_name,
                    keywords=["LETHAL HITS"],
                    source=str(stratagem.name or "RIGHTEOUS BLOWS"),
                    expires_phase=phase_key,
                    attack_type="melee",
                )
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["bringers_of_flame_righteous_blows_active"] = {
            "phase_key": self._as_turn_phase_key(self.game),
            "battle_shock_triggered": False,
            "source": str(stratagem.name or "RIGHTEOUS BLOWS"),
        }
        root.special_rules = sr
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RIGHTEOUS BLOWS: %s gains [LETHAL HITS] on melee weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_bringers_of_flame_rites_of_fire(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_bringers_of_flame():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RITES OF FIRE: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "shooting phase":
            logger.error("ERROR: RITES OF FIRE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: RITES OF FIRE: not your Shooting phase")
            return False
        eligible = candidates or self._bringers_of_flame_rites_of_fire_candidates()
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: RITES OF FIRE: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: RITES OF FIRE: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: RITES OF FIRE: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: RITES OF FIRE: target is not ADEPTA SORORITAS")
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: RITES OF FIRE: target has already shot")
            return False
        if not bool(getattr(round_state, "disembarked_this_round", False)):
            logger.error("ERROR: RITES OF FIRE: target did not disembark this round")
            return False
        if not str(getattr(round_state, "disembarked_from_transport_id", "") or "").strip():
            logger.error("ERROR: RITES OF FIRE: target did not disembark from a transport this round")
            return False
        if not self._as_unit_has_ranged_weapon(root):
            logger.error("ERROR: RITES OF FIRE: target has no ranged weapons")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["bringers_of_flame_rites_of_fire_active"] = {
            "phase_key": self._as_turn_phase_key(self.game),
            "battle_shock_triggered": False,
            "source": str(stratagem.name or "RITES OF FIRE"),
        }
        root.special_rules = sr
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RITES OF FIRE: %s gains +1 to wound on qualifying ranged attacks this phase and can force a Battle-shock test after a qualifying kill.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_penitent_host_boundless_zeal(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_penitent_host():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        action = kwargs.get("action")
        candidates = list(kwargs.get("candidates") or [])
        if (unit is None or not candidates or action is None) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "BOUNDLESS ZEAL":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if action is None:
                    action = reaction.get("action")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BOUNDLESS ZEAL: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "movement phase":
            logger.error("ERROR: BOUNDLESS ZEAL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: BOUNDLESS ZEAL: not your Movement phase")
            return False
        if str(action or "").strip().lower() != "fall_back":
            logger.error("ERROR: BOUNDLESS ZEAL: target must have just Fallen Back")
            return False
        eligible = candidates or self._penitent_host_boundless_zeal_candidates(moved_unit=root, action=action)
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: BOUNDLESS ZEAL: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: BOUNDLESS ZEAL: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: BOUNDLESS ZEAL: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: BOUNDLESS ZEAL: target is not ADEPTA SORORITAS")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        if self._is_penitent_unit(root):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["penitent_host_boundless_zeal_active"] = True
            sr["penitent_host_boundless_zeal_mode"] = "both"
            sr["penitent_host_boundless_zeal_turn_owner"] = self._as_current_turn_owner_id()
            sr["penitent_host_boundless_zeal_turn"] = self._as_current_turn()
            sr["penitent_host_boundless_zeal_source"] = str(stratagem.name or "BOUNDLESS ZEAL")
            root.special_rules = sr
            cache = getattr(root, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("fell_back_and_shoot", None)
            self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: BOUNDLESS ZEAL: %s can shoot and charge after Falling Back this turn.",
                getattr(root, "name", "Unit"),
            )
            return True
        choice_request = self._build_penitent_host_boundless_zeal_choice_request(
            unit=root,
            phase_name="Movement phase",
            stratagem_name=str(getattr(stratagem, "name", "") or "BOUNDLESS ZEAL"),
        )
        if choice_request is None:
            logger.error("ERROR: BOUNDLESS ZEAL: failed to build choice request")
            return False
        if not self._as_submit_decision_request(choice_request):
            logger.error("ERROR: BOUNDLESS ZEAL: failed to queue choice request")
            return False
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BOUNDLESS ZEAL: queued Shoot-or-Charge choice for %s.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_penitent_host_devout_fanaticism(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_penitent_host():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if (unit is None or attacking_unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "DEVOUT FANATICISM":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DEVOUT FANATICISM: no target unit provided")
            return False
        root = self._as_root(unit)
        attacker_root = self._as_root(attacking_unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "shooting phase":
            logger.error("ERROR: DEVOUT FANATICISM: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: DEVOUT FANATICISM: not opponent's Shooting phase")
            return False
        eligible = candidates
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: DEVOUT FANATICISM: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: DEVOUT FANATICISM: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: DEVOUT FANATICISM: target cannot be selected")
            return False
        if not self._is_penitent_unit(root):
            logger.error("ERROR: DEVOUT FANATICISM: target must be PENITENT")
            return False
        if attacker_root is not None and self._as_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: DEVOUT FANATICISM: attacker is not enemy")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: DEVOUT FANATICISM: reactive move queue unavailable")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        max_distance = max(0, dice_module.get_roll("D6"))
        if max_distance <= 0:
            logger.error("ERROR: DEVOUT FANATICISM: invalid reactive move distance")
            return False
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(max_distance),
            kind="devout_fanaticism",
            movement_type="reactive",
            reactive_movement_type="devout_fanaticism",
            source=str(getattr(stratagem, "name", "") or "DEVOUT FANATICISM"),
            attacker_unit=attacker_root,
            allow_engagement_range=True,
            extra_context={
                "devout_fanaticism_source": str(getattr(stratagem, "name", "") or "DEVOUT FANATICISM"),
                "devout_fanaticism_closest_enemy_exclude_keywords_any": ["AIRCRAFT"],
            },
        )
        if request is not None:
            request.context["reactive_move_allow_engagement_range"] = True
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DEVOUT FANATICISM: %s can make a reactive move of up to %d\" toward the closest enemy unit.",
            getattr(root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _use_penitent_host_final_redemption(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_penitent_host():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("destroyed_unit")
        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        if (unit is None or not objective_candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "FINAL REDEMPTION":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit") or reaction.get("destroyed_unit")
                if not objective_candidates:
                    objective_candidates = list(reaction.get("objective_candidates") or [])
                break
        if unit is None:
            logger.error("ERROR: FINAL REDEMPTION: no destroyed unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        if objective is None:
            objective = objective_candidates[0] if objective_candidates else None
        if objective is None:
            logger.error("ERROR: FINAL REDEMPTION: no objective marker available")
            return False
        if objective_candidates and objective not in list(objective_candidates or []):
            logger.error("ERROR: FINAL REDEMPTION: objective is not eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if not self._is_penitent_unit(root):
            logger.error("ERROR: FINAL REDEMPTION: target must be PENITENT")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        objective_location = getattr(objective, "location", None)
        if objective_location is None:
            logger.error("ERROR: FINAL REDEMPTION: objective marker location is unavailable")
            return False
        set_sticky = getattr(objective_location, "set_sticky_control", None)
        if callable(set_sticky):
            set_sticky(self.player, source="penitent_host_final_redemption")
        else:
            objective_location.sticky_controller = self.player
            objective_location.sticky_source = "penitent_host_final_redemption"
            objective_location.controlling_player = self.player
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: FINAL REDEMPTION: objective remains under your control until broken.")
        return True

    def _use_penitent_host_lash_of_guilt(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_penitent_host():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        action = kwargs.get("action")
        candidates = list(kwargs.get("candidates") or [])
        if (unit is None or not candidates or action is None) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "LASH OF GUILT":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if action is None:
                    action = reaction.get("action")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: LASH OF GUILT: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "movement phase":
            logger.error("ERROR: LASH OF GUILT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: LASH OF GUILT: not your Movement phase")
            return False
        if str(action or "").strip().lower() != "advance":
            logger.error("ERROR: LASH OF GUILT: target must have just been selected to Advance")
            return False
        eligible = candidates or self._penitent_host_lash_of_guilt_candidates(moved_unit=root, action=action)
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: LASH OF GUILT: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: LASH OF GUILT: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: LASH OF GUILT: target cannot be selected")
            return False
        if not self._is_penitent_unit(root):
            logger.error("ERROR: LASH OF GUILT: target must be PENITENT")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["penitent_host_lash_of_guilt_active"] = True
        sr["penitent_host_lash_of_guilt_turn_owner"] = self._as_current_turn_owner_id()
        sr["penitent_host_lash_of_guilt_turn"] = self._as_current_turn()
        sr["penitent_host_lash_of_guilt_source"] = str(stratagem.name or "LASH OF GUILT")
        if self._is_penitent_engines_unit(root):
            entry_tag = f"stratagem:penitent_host_lash_of_guilt:{self._as_sort_key(root)}"
            effects = list(sr.get("advance_no_roll_effects", []) or [])
            kept = [
                entry
                for entry in effects
                if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == entry_tag)
            ]
            kept.append(
                {
                    "distance": 6,
                    "source": str(stratagem.name or "LASH OF GUILT"),
                    "tag": entry_tag,
                    "expires_phase": "MOVEMENT_PHASE",
                }
            )
            sr["advance_no_roll_effects"] = kept
        root.special_rules = sr
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: LASH OF GUILT: %s can charge after Advancing this turn%s.",
            getattr(root, "name", "Unit"),
            " and treats the Advance roll as 6" if self._is_penitent_engines_unit(root) else "",
        )
        return True

    def _use_penitent_host_passion_of_the_penitent(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_penitent_host():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PASSION OF THE PENITENT: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: PASSION OF THE PENITENT: wrong phase")
            return False
        eligible = candidates or self._penitent_host_passion_of_the_penitent_candidates()
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: PASSION OF THE PENITENT: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: PASSION OF THE PENITENT: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: PASSION OF THE PENITENT: target cannot be selected")
            return False
        if not self._is_penitent_unit(root):
            logger.error("ERROR: PASSION OF THE PENITENT: target must be PENITENT")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: PASSION OF THE PENITENT: target has already fought")
            return False
        if not self._as_unit_has_melee_weapon(root):
            logger.error("ERROR: PASSION OF THE PENITENT: target has no melee weapons")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["penitent_host_passion_of_the_penitent_active"] = True
        sr["penitent_host_passion_of_the_penitent_crit_threshold"] = 5
        sr["penitent_host_passion_of_the_penitent_turn_owner"] = self._as_current_turn_owner_id()
        sr["penitent_host_passion_of_the_penitent_turn"] = self._as_current_turn()
        sr["penitent_host_passion_of_the_penitent_source"] = str(stratagem.name or "PASSION OF THE PENITENT")
        root.special_rules = sr
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PASSION OF THE PENITENT: %s scores critical melee hits on 5+ this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_penitent_host_purity_of_suffering(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_penitent_host():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        if (unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "PURITY OF SUFFERING":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PURITY OF SUFFERING: no target unit provided")
            return False
        root = self._as_root(unit)
        attacker_root = self._as_root(attacking_unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: PURITY OF SUFFERING: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: PURITY OF SUFFERING: not opponent's Shooting phase")
            return False
        eligible = candidates or self._penitent_host_purity_of_suffering_candidates(target_units=target_units)
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: PURITY OF SUFFERING: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: PURITY OF SUFFERING: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: PURITY OF SUFFERING: target cannot be selected")
            return False
        if not self._is_penitent_unit(root):
            logger.error("ERROR: PURITY OF SUFFERING: target must be PENITENT")
            return False
        if attacker_root is not None and self._as_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: PURITY OF SUFFERING: attacker is not enemy")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        phase_key = self._as_phase_key("Shooting phase" if phase_name == "shooting phase" else "Fight phase")
        for model in self._as_unit_models(root):
            if not self._as_model_is_alive(model):
                continue
            if not self._is_penitent_model(model, root):
                continue
            set_temporary_fnp = getattr(model, "set_temporary_fnp", None)
            if not callable(set_temporary_fnp):
                continue
            set_temporary_fnp(
                key=f"penitent_host_purity_of_suffering:{self._as_sort_key(root)}:{get_entity_id(model)}",
                value=4,
                source=str(stratagem.name or "PURITY OF SUFFERING"),
                expires_phase=phase_key,
            )
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PURITY OF SUFFERING: %s gains Feel No Pain 4+ for PENITENT models this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_champions_of_faith_bastion_of_faith(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_champions_of_faith():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        if (unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "BASTION OF FAITH":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BASTION OF FAITH: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: BASTION OF FAITH: wrong phase")
            return False
        eligible = candidates or self._champions_of_faith_bastion_of_faith_candidates(target_units=target_units)
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: BASTION OF FAITH: target is not currently eligible")
            return False
        if attacking_unit is not None and self._as_owned_by_player(attacking_unit, self.player):
            logger.error("ERROR: BASTION OF FAITH: attacker is not enemy")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: BASTION OF FAITH: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: BASTION OF FAITH: target cannot be selected")
            return False
        if not self._champions_of_faith_is_celestian_sacresants(root):
            logger.error("ERROR: BASTION OF FAITH: target must be Celestian Sacresants")
            return False
        secondary_candidates = self._champions_of_faith_bastion_secondary_candidates(primary_unit=root)
        secondary_request = None
        if secondary_candidates:
            secondary_request = self._build_champions_of_faith_bastion_secondary_request(
                primary_unit=root,
                phase_name="Fight phase",
                stratagem_name=str(getattr(stratagem, "name", "") or "BASTION OF FAITH"),
            )
            if secondary_request is None:
                logger.error("ERROR: BASTION OF FAITH: failed to build secondary selection request")
                return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        self._append_defensive_effect(
            root,
            "defensive_hit_mods",
            {
                "value": 1,
                "attack_type": "melee",
                "expires_phase": self._as_phase_key("Fight phase"),
                "source": str(stratagem.name or "BASTION OF FAITH"),
            },
        )
        if secondary_request is not None and not self._as_submit_decision_request(secondary_request):
            logger.error("ERROR: BASTION OF FAITH: failed to queue secondary selection request")
            return False
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BASTION OF FAITH: %s gains -1 to hit against melee attacks%s.",
            getattr(root, "name", "Unit"),
            " and queued an optional second Sacresants selection"
            if secondary_request is not None
            else "",
        )
        return True

    def _use_champions_of_faith_indefatigable_dedication(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_champions_of_faith():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        action = kwargs.get("action")
        candidates = list(kwargs.get("candidates") or [])
        if (unit is None or not candidates or action is None) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "INDEFATIGABLE DEDICATION":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if action is None:
                    action = reaction.get("action")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: INDEFATIGABLE DEDICATION: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "movement phase":
            logger.error("ERROR: INDEFATIGABLE DEDICATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: INDEFATIGABLE DEDICATION: not your Movement phase")
            return False
        if str(action or "").strip().lower() != "fall_back":
            logger.error("ERROR: INDEFATIGABLE DEDICATION: target unit must have just Fallen Back")
            return False
        eligible = candidates or self._champions_of_faith_indefatigable_dedication_candidates(moved_unit=root, action=action)
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: INDEFATIGABLE DEDICATION: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: INDEFATIGABLE DEDICATION: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: INDEFATIGABLE DEDICATION: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: INDEFATIGABLE DEDICATION: target is not ADEPTA SORORITAS")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["champions_of_faith_indefatigable_dedication_active"] = True
        sr["champions_of_faith_indefatigable_dedication_turn_owner"] = self._as_current_turn_owner_id()
        sr["champions_of_faith_indefatigable_dedication_turn"] = self._as_current_turn()
        sr["champions_of_faith_indefatigable_dedication_source"] = str(stratagem.name or "INDEFATIGABLE DEDICATION")
        sr["champions_of_faith_indefatigable_dedication_can_charge"] = self._champions_of_faith_is_righteous(root)
        root.special_rules = sr
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.pop("fell_back_and_shoot", None)
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: INDEFATIGABLE DEDICATION: %s can shoot after Falling Back this turn%s.",
            getattr(root, "name", "Unit"),
            " and charge as well" if self._champions_of_faith_is_righteous(root) else "",
        )
        return True

    def _use_champions_of_faith_path_of_the_righteous(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_champions_of_faith():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PATH OF THE RIGHTEOUS: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: PATH OF THE RIGHTEOUS: wrong phase")
            return False
        eligible = candidates or self._champions_of_faith_path_of_the_righteous_candidates()
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: PATH OF THE RIGHTEOUS: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: PATH OF THE RIGHTEOUS: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: PATH OF THE RIGHTEOUS: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: PATH OF THE RIGHTEOUS: target is not ADEPTA SORORITAS")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: PATH OF THE RIGHTEOUS: target has already fought")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        turn_owner_id = self._as_current_turn_owner_id()
        current_turn = self._as_current_turn()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["champions_of_faith_path_of_the_righteous_active"] = True
        sr["champions_of_faith_path_of_the_righteous_turn_owner"] = turn_owner_id
        sr["champions_of_faith_path_of_the_righteous_turn"] = current_turn
        sr["champions_of_faith_path_of_the_righteous_source"] = str(stratagem.name or "PATH OF THE RIGHTEOUS")
        sr["stratagem_pile_in_distance_override"] = max(float(sr.get("stratagem_pile_in_distance_override", 0.0) or 0.0), 6.0)
        sr["stratagem_consolidate_distance_override"] = max(
            float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0),
            6.0,
        )
        if self._champions_of_faith_is_righteous(root):
            sr["stratagem_choreographer_of_war_source"] = str(stratagem.name or "PATH OF THE RIGHTEOUS")
            sr["stratagem_choreographer_of_war_expires_phase"] = "FIGHT_PHASE"
            sr["stratagem_choreographer_of_war_turn_owner"] = turn_owner_id
            sr["stratagem_choreographer_of_war_turn"] = current_turn
        root.special_rules = sr
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.pop("choreographer_of_war_source", None)
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PATH OF THE RIGHTEOUS: %s can Pile-in and Consolidate up to 6\" this phase%s.",
            getattr(root, "name", "Unit"),
            " and follows the closest enemy unit rule" if self._champions_of_faith_is_righteous(root) else "",
        )
        return True

    def _use_champions_of_faith_shield_of_denial(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_champions_of_faith():
            return False
        source_unit = kwargs.get("source_unit") or kwargs.get("trigger_unit") or kwargs.get("suffering_unit")
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if (source_unit is None or unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SHIELD OF DENIAL":
                    continue
                if source_unit is None:
                    source_unit = reaction.get("source_unit") or reaction.get("trigger_unit")
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if source_unit is None:
            logger.error("ERROR: SHIELD OF DENIAL: no source unit provided")
            return False
        if unit is None:
            logger.error("ERROR: SHIELD OF DENIAL: no target unit provided")
            return False
        source_root = self._as_root(source_unit)
        root = self._as_root(unit)
        if source_root is None or root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip() or "Any phase"
        eligible = candidates or self._champions_of_faith_shield_of_denial_candidates(source_unit=source_root)
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: SHIELD OF DENIAL: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: SHIELD OF DENIAL: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: SHIELD OF DENIAL: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: SHIELD OF DENIAL: target is not ADEPTA SORORITAS")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        phase_key = self._as_phase_key(phase_name)
        fnp_value = 5 if self._champions_of_faith_is_righteous(root) else 6
        for model in self._as_unit_models(root):
            if not self._as_model_is_alive(model):
                continue
            set_temporary_fnp = getattr(model, "set_temporary_fnp", None)
            if not callable(set_temporary_fnp):
                continue
            set_temporary_fnp(
                key=f"champions_of_faith_shield_of_denial:{self._as_sort_key(root)}:{get_entity_id(model)}",
                value=fnp_value,
                source=str(stratagem.name or "SHIELD OF DENIAL"),
                condition="against mortal wounds",
                expires_phase=phase_key,
            )
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SHIELD OF DENIAL: %s gains Feel No Pain %d+ against mortal wounds this phase.",
            getattr(root, "name", "Unit"),
            int(fnp_value),
        )
        return True

    def _use_champions_of_faith_suffer_not_the_unfaithful(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_champions_of_faith():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SUFFER NOT THE UNFAITHFUL: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: SUFFER NOT THE UNFAITHFUL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: SUFFER NOT THE UNFAITHFUL: shooting-phase use requires your Shooting phase")
            return False
        eligible = candidates or self._champions_of_faith_suffer_not_the_unfaithful_candidates(
            phase_name="Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        )
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: SUFFER NOT THE UNFAITHFUL: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: SUFFER NOT THE UNFAITHFUL: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: SUFFER NOT THE UNFAITHFUL: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: SUFFER NOT THE UNFAITHFUL: target is not ADEPTA SORORITAS")
            return False
        if not self._champions_of_faith_is_righteous(root):
            logger.error("ERROR: SUFFER NOT THE UNFAITHFUL: target must be Righteous")
            return False
        round_state = getattr(root, "round_state", None)
        if phase_name == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: SUFFER NOT THE UNFAITHFUL: target has already been selected to shoot")
            return False
        if phase_name == "fight phase" and bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: SUFFER NOT THE UNFAITHFUL: target has already fought")
            return False
        choice_request = self._build_champions_of_faith_suffer_choice_request(
            unit=root,
            phase_name="Shooting phase" if phase_name == "shooting phase" else "Fight phase",
            stratagem_name=str(getattr(stratagem, "name", "") or "SUFFER NOT THE UNFAITHFUL"),
        )
        if choice_request is None:
            logger.error("ERROR: SUFFER NOT THE UNFAITHFUL: failed to build choice request")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        if not self._as_submit_decision_request(choice_request):
            logger.error("ERROR: SUFFER NOT THE UNFAITHFUL: failed to queue choice request")
            return False
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SUFFER NOT THE UNFAITHFUL: queued keyword choice for %s.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_champions_of_faith_to_the_heart_of_heresy(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_champions_of_faith():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: TO THE HEART OF HERESY: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: TO THE HEART OF HERESY: wrong phase")
            return False
        eligible = candidates or self._champions_of_faith_to_the_heart_of_heresy_candidates()
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: TO THE HEART OF HERESY: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: TO THE HEART OF HERESY: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: TO THE HEART OF HERESY: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: TO THE HEART OF HERESY: target is not ADEPTA SORORITAS")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: TO THE HEART OF HERESY: target has already fought")
            return False
        if not self._as_unit_has_melee_weapon(root):
            logger.error("ERROR: TO THE HEART OF HERESY: target has no melee weapons")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        phase_key = self._as_phase_key("Fight phase")
        ap_bonus = 1 if self._champions_of_faith_is_righteous(root) else 0
        for model in self._as_unit_models(root):
            if not self._as_model_is_alive(model):
                continue
            model_id = str(get_entity_id(model) or "")
            for profile in self._as_model_weapon_profiles(model, attack_type="melee"):
                lookup_name_fn = getattr(profile, "_temporary_weapon_lookup_name", None)
                weapon_name = lookup_name_fn() if callable(lookup_name_fn) else str(getattr(profile, "name", "") or "")
                if not weapon_name:
                    continue
                set_bonus = getattr(model, "set_temporary_weapon_bonus", None)
                if not callable(set_bonus):
                    continue
                set_bonus(
                    key=f"champions_of_faith_to_the_heart_of_heresy:{self._as_sort_key(root)}:{model_id}:{weapon_name}",
                    weapon_name=weapon_name,
                    strength_bonus=1,
                    ap_bonus=ap_bonus,
                    source=str(stratagem.name or "TO THE HEART OF HERESY"),
                    expires_phase=phase_key,
                )
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TO THE HEART OF HERESY: %s gains +1 Strength on melee weapons this phase%s.",
            getattr(root, "name", "Unit"),
            " and +1 AP" if ap_bonus else "",
        )
        return True

    def _use_army_of_faith_divine_guidance(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_army_of_faith():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DIVINE GUIDANCE: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: DIVINE GUIDANCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: DIVINE GUIDANCE: shooting-phase use requires your Shooting phase")
            return False
        eligible = candidates or self._army_of_faith_divine_guidance_candidates(
            phase_name="Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        )
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: DIVINE GUIDANCE: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: DIVINE GUIDANCE: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: DIVINE GUIDANCE: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: DIVINE GUIDANCE: target is not ADEPTA SORORITAS")
            return False
        round_state = getattr(root, "round_state", None)
        if phase_name == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: DIVINE GUIDANCE: target has already been selected to shoot")
            return False
        if phase_name == "fight phase" and bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: DIVINE GUIDANCE: target has already fought")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        phase_key = self._as_phase_key(kwargs.get("phase_name") or self._current_phase_name or "")
        attack_type = "ranged" if phase_name == "shooting phase" else "melee"
        for model in list(getattr(root, "get_attached_unit_models", lambda: [])() or []):
            if not bool(getattr(model, "is_alive", True)):
                continue
            model_id = str(get_entity_id(model) or "")
            for profile in self._as_model_weapon_profiles(model, attack_type=attack_type):
                lookup_name_fn = getattr(profile, "_temporary_weapon_lookup_name", None)
                weapon_name = lookup_name_fn() if callable(lookup_name_fn) else str(getattr(profile, "name", "") or "")
                if not weapon_name:
                    continue
                model.set_temporary_weapon_bonus(
                    key=f"army_of_faith_divine_guidance:{self._as_sort_key(root)}:{model_id}:{weapon_name}",
                    weapon_name=weapon_name,
                    ap_bonus=1,
                    source=str(stratagem.name or "DIVINE GUIDANCE"),
                    expires_phase=phase_key,
                )
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["army_of_faith_divine_guidance_active"] = {
            "phase_key": self._as_turn_phase_key(self.game),
            "awarded": False,
            "source": str(stratagem.name or "DIVINE GUIDANCE"),
        }
        root.special_rules = sr
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DIVINE GUIDANCE: %s improves the AP of its %s attacks by 1 this phase.",
            getattr(root, "name", "Unit"),
            attack_type,
        )
        return True

    def _use_army_of_faith_faith_and_fury(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_army_of_faith():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FAITH AND FURY: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: FAITH AND FURY: wrong phase")
            return False
        eligible = candidates or self._army_of_faith_faith_and_fury_candidates()
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: FAITH AND FURY: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: FAITH AND FURY: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: FAITH AND FURY: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: FAITH AND FURY: target is not ADEPTA SORORITAS")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: FAITH AND FURY: target has already fought")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        phase_key = self._as_phase_key(kwargs.get("phase_name") or self._current_phase_name or "")
        for model in list(getattr(root, "get_attached_unit_models", lambda: [])() or []):
            if not bool(getattr(model, "is_alive", True)):
                continue
            model_id = str(get_entity_id(model) or "")
            for profile in self._as_model_weapon_profiles(model, attack_type="melee"):
                lookup_name_fn = getattr(profile, "_temporary_weapon_lookup_name", None)
                weapon_name = lookup_name_fn() if callable(lookup_name_fn) else str(getattr(profile, "name", "") or "")
                if not weapon_name:
                    continue
                model.set_temporary_weapon_keyword_bonuses(
                    key=f"army_of_faith_faith_and_fury:{self._as_sort_key(root)}:{model_id}:{weapon_name}",
                    weapon_name=weapon_name,
                    keywords=["LANCE"],
                    source=str(stratagem.name or "FAITH AND FURY"),
                    expires_phase=phase_key,
                    attack_type="melee",
                )
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["army_of_faith_faith_and_fury_active"] = {
            "phase_key": self._as_turn_phase_key(self.game),
            "awarded": False,
            "source": str(stratagem.name or "FAITH AND FURY"),
        }
        root.special_rules = sr
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FAITH AND FURY: %s gains [LANCE] on melee weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_army_of_faith_light_of_the_emperor(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_army_of_faith():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: LIGHT OF THE EMPEROR: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "command phase":
            logger.error("ERROR: LIGHT OF THE EMPEROR: wrong phase")
            return False
        eligible = candidates or self._army_of_faith_light_of_the_emperor_candidates()
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: LIGHT OF THE EMPEROR: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: LIGHT OF THE EMPEROR: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: LIGHT OF THE EMPEROR: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: LIGHT OF THE EMPEROR: target is not ADEPTA SORORITAS")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        mgr = self._get_adepta_sororitas_mgr()
        apply_fn = getattr(mgr, "apply_light_of_the_emperor", None) if mgr is not None else None
        if not callable(apply_fn) or not bool(apply_fn(root, game=self.game, source_name=str(stratagem.name or ""))):
            logger.error("ERROR: LIGHT OF THE EMPEROR: failed to apply blessed state")
            return False
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: LIGHT OF THE EMPEROR: %s is blessed until the end of the turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_army_of_faith_blinding_radiance(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_army_of_faith():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        if (unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "BLINDING RADIANCE":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BLINDING RADIANCE: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: BLINDING RADIANCE: wrong phase")
            return False
        eligible = candidates or self._army_of_faith_blinding_radiance_candidates(target_units=target_units)
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: BLINDING RADIANCE: target is not currently eligible")
            return False
        if attacking_unit is not None and self._as_owned_by_player(attacking_unit, self.player):
            logger.error("ERROR: BLINDING RADIANCE: attacker is not enemy")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: BLINDING RADIANCE: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: BLINDING RADIANCE: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: BLINDING RADIANCE: target is not ADEPTA SORORITAS")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        attack_type = "ranged" if phase_name == "shooting phase" else "melee"
        phase_key = self._as_phase_key(kwargs.get("phase_name") or self._current_phase_name or "")
        for affected_unit in self._army_of_faith_jump_pack_aura_units(root):
            self._append_defensive_effect(
                affected_unit,
                "defensive_hit_mods",
                {
                    "value": 1,
                    "attack_type": attack_type,
                    "expires_phase": phase_key,
                    "source": str(stratagem.name or "BLINDING RADIANCE"),
                },
            )
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BLINDING RADIANCE: %s applies -1 to hit against attacks targeting protected units this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_army_of_faith_shield_of_faith(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_army_of_faith():
            return False
        source_unit = kwargs.get("source_unit") or kwargs.get("trigger_unit") or kwargs.get("suffering_unit")
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if (source_unit is None or unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SHIELD OF FAITH":
                    continue
                if source_unit is None:
                    source_unit = reaction.get("source_unit") or reaction.get("trigger_unit")
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if source_unit is None:
            logger.error("ERROR: SHIELD OF FAITH: no source unit provided")
            return False
        if unit is None:
            logger.error("ERROR: SHIELD OF FAITH: no target unit provided")
            return False
        source_root = self._as_root(source_unit)
        root = self._as_root(unit)
        if source_root is None or root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip() or "Any phase"
        eligible = candidates or self._army_of_faith_shield_of_faith_candidates(source_unit=source_root)
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: SHIELD OF FAITH: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: SHIELD OF FAITH: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: SHIELD OF FAITH: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: SHIELD OF FAITH: target is not ADEPTA SORORITAS")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        phase_key = self._as_phase_key(phase_name)
        for affected_unit in self._army_of_faith_jump_pack_aura_units(root):
            for model in list(getattr(affected_unit, "get_attached_unit_models", lambda: [])() or []):
                if not bool(getattr(model, "is_alive", True)):
                    continue
                model.set_temporary_fnp(
                    key=f"army_of_faith_shield_of_faith:{self._as_sort_key(affected_unit)}:{get_entity_id(model)}",
                    value=5,
                    source=str(stratagem.name or "SHIELD OF FAITH"),
                    condition="against mortal wounds",
                    expires_phase=phase_key,
                )
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SHIELD OF FAITH: %s grants Feel No Pain 5+ against mortal wounds to protected units this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_army_of_faith_angelic_descent(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_army_of_faith():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: ANGELIC DESCENT: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: ANGELIC DESCENT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: ANGELIC DESCENT: not opponent's Fight phase")
            return False
        eligible = candidates or self._army_of_faith_angelic_descent_candidates()
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: ANGELIC DESCENT: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: ANGELIC DESCENT: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: ANGELIC DESCENT: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: ANGELIC DESCENT: target is not ADEPTA SORORITAS")
            return False
        if not self._as_has_keyword(root, "JUMP PACK"):
            logger.error("ERROR: ANGELIC DESCENT: target must have JUMP PACK")
            return False
        if self._as_has_enemy_within_engagement_range(root):
            logger.error("ERROR: ANGELIC DESCENT: target is within Engagement Range")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        if not self._as_place_unit_into_strategic_reserves(root, reason=str(getattr(stratagem, "name", "") or "")):
            logger.error("ERROR: ANGELIC DESCENT: failed to place target into Strategic Reserves")
            return False
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ANGELIC DESCENT: %s entered Strategic Reserves.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_hallowed_righteous_vengeance(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_martyrs():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RIGHTEOUS VENGEANCE: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: RIGHTEOUS VENGEANCE: wrong phase")
            return False
        if not self._as_on_battlefield(root):
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if not self._is_adepta_sororitas_unit(root):
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: RIGHTEOUS VENGEANCE: target already fought")
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: RIGHTEOUS VENGEANCE: target cannot be selected")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["righteous_vengeance_active"] = True
        sr["righteous_vengeance_expires_phase"] = "FIGHT_PHASE"
        sr["righteous_vengeance_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["righteous_vengeance_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["righteous_vengeance_source"] = str(getattr(stratagem, "name", "") or "RIGHTEOUS VENGEANCE")
        root.special_rules = sr
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            f"INFO: RIGHTEOUS VENGEANCE: {getattr(root, 'name', 'Unit')} re-rolls melee hit rolls "
            "and re-rolls melee wound rolls while Below Half-strength this phase."
        )
        return True

    def _use_hallowed_suffering_and_sacrifice(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_martyrs():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SUFFERING AND SACRIFICE: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: SUFFERING AND SACRIFICE: wrong phase")
            return False
        if not self._as_on_battlefield(root):
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if not self._is_adepta_sororitas_infantry_or_walker(root):
            logger.error("ERROR: SUFFERING AND SACRIFICE: target must be ADEPTA SORORITAS INFANTRY or WALKER")
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: SUFFERING AND SACRIFICE: target cannot be selected")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["suffering_and_sacrifice_active"] = True
        sr["suffering_and_sacrifice_expires_phase"] = "FIGHT_PHASE"
        sr["suffering_and_sacrifice_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["suffering_and_sacrifice_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["suffering_and_sacrifice_source"] = str(getattr(stratagem, "name", "") or "SUFFERING AND SACRIFICE")
        root.special_rules = sr
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            f"INFO: SUFFERING AND SACRIFICE: enemy units in Engagement Range must target {getattr(root, 'name', 'Unit')} this phase."
        )
        return True

    def _use_hallowed_spirit_of_the_martyr(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_martyrs():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit")
        candidates = list(kwargs.get("candidates") or kwargs.get("target_units") or [])
        if unit is None:
            if len(candidates) == 1:
                unit = candidates[0]
            else:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "SPIRIT OF THE MARTYR":
                        continue
                    unit = reaction.get("unit") or reaction.get("target_unit")
                    enemy_unit = enemy_unit or reaction.get("enemy_unit") or reaction.get("attacking_unit")
                    candidates = candidates or list(reaction.get("candidates") or [])
                    break
        if unit is None:
            logger.error("ERROR: SPIRIT OF THE MARTYR: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: SPIRIT OF THE MARTYR: wrong phase")
            return False
        if not self._as_on_battlefield(root):
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SPIRIT OF THE MARTYR: target was not selected by the attacker")
            return False
        if enemy_unit is not None and self._as_owned_by_player(enemy_unit, self.player):
            logger.error("ERROR: SPIRIT OF THE MARTYR: attacker is not enemy")
            return False
        if not self._is_adepta_sororitas_unit(root):
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: SPIRIT OF THE MARTYR: target already fought")
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: SPIRIT OF THE MARTYR: target cannot be selected")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["spirit_of_martyr_active"] = True
        sr["spirit_of_martyr_expires_phase"] = "FIGHT_PHASE"
        sr["spirit_of_martyr_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["spirit_of_martyr_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["spirit_of_martyr_source"] = str(getattr(stratagem, "name", "") or "SPIRIT OF THE MARTYR")
        root.special_rules = sr
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: SPIRIT OF THE MARTYR: {getattr(root, 'name', 'Unit')} can fight on death this phase.")
        return True

    def _use_hallowed_praise_the_fallen(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_martyrs():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            if len(candidates) == 1:
                unit = candidates[0]
            else:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "PRAISE THE FALLEN":
                        continue
                    unit = reaction.get("unit") or reaction.get("target_unit")
                    enemy_unit = enemy_unit or reaction.get("enemy_unit") or reaction.get("attacking_unit")
                    candidates = candidates or list(reaction.get("candidates") or [])
                    break
        if unit is None:
            logger.error("ERROR: PRAISE THE FALLEN: no target unit provided")
            return False
        root = self._as_root(unit)
        enemy_root = self._as_root(enemy_unit)
        if root is None or enemy_root is None:
            logger.error("ERROR: PRAISE THE FALLEN: missing attacker context")
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "shooting phase":
            logger.error("ERROR: PRAISE THE FALLEN: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            logger.error("ERROR: PRAISE THE FALLEN: not opponent's Shooting phase")
            return False
        if not self._as_on_battlefield(root):
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if self._as_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: PRAISE THE FALLEN: attacker is not enemy")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: PRAISE THE FALLEN: target was not damaged by the attacker")
            return False
        if not self._is_adepta_sororitas_unit(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: PRAISE THE FALLEN: target cannot be selected")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        queued = None
        queue_fn = getattr(self.game, "_queue_setup_reactive_shooting_decision", None) if self.game is not None else None
        if callable(queue_fn):
            queued = queue_fn(
                player=self.player,
                unit=root,
                target_unit=enemy_root,
                source=stratagem.name,
            )
        if queued is None:
            logger.error("ERROR: PRAISE THE FALLEN: failed to queue reactive shooting decision")
            return False
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            f"INFO: PRAISE THE FALLEN: {getattr(root, 'name', 'Unit')} can shoot reactively into {getattr(enemy_root, 'name', 'Unit')}."
        )
        return True

    def _use_hallowed_sanctified_immolation(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_martyrs():
            return False
        root = self._as_root(
            kwargs.get("destroyed_unit")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        destroyed_model = kwargs.get("destroyed_model") or kwargs.get("model")
        if root is None or destroyed_model is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SANCTIFIED IMMOLATION":
                    continue
                root = root or self._as_root(
                    reaction.get("destroyed_unit")
                    or reaction.get("unit")
                    or reaction.get("target_unit")
                )
                destroyed_model = destroyed_model or reaction.get("destroyed_model")
                break
        if root is None or destroyed_model is None:
            logger.error("ERROR: SANCTIFIED IMMOLATION: missing destroyed model context")
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if not self._is_adepta_sororitas_vehicle(root):
            logger.error("ERROR: SANCTIFIED IMMOLATION: target must be ADEPTA SORORITAS VEHICLE")
            return False
        has_deadly_demise = getattr(root, "has_deadly_demise", None)
        if not callable(has_deadly_demise):
            return False
        try:
            has_deadly, _damage_dice = has_deadly_demise()
        except Exception:
            has_deadly = False
        if not has_deadly:
            logger.error("ERROR: SANCTIFIED IMMOLATION: target model has no Deadly Demise")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        try:
            setattr(destroyed_model, "_sanctified_immolation_auto_trigger_once", True)
        except Exception:
            pass
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: SANCTIFIED IMMOLATION: Deadly Demise auto-triggers for the destroyed model.")
        return True

    def _resolve_divine_intervention_context(self, **kwargs) -> tuple[Any, Any, Optional[tuple]]:
        root = self._as_root(
            kwargs.get("unit")
            or kwargs.get("target_unit")
            or kwargs.get("destroyed_unit")
        )
        model = kwargs.get("destroyed_model") or kwargs.get("model")
        destroyed_position = kwargs.get("destroyed_position")
        if root is not None and model is not None:
            return root, model, destroyed_position
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "DIVINE INTERVENTION":
                continue
            if root is None:
                root = self._as_root(
                    reaction.get("unit")
                    or reaction.get("target_unit")
                    or reaction.get("destroyed_unit")
                )
            if model is None:
                model = reaction.get("destroyed_model")
            if destroyed_position is None:
                destroyed_position = reaction.get("destroyed_position")
            break
        return root, model, destroyed_position

    @staticmethod
    def _resolve_discard_values_from_kwargs(
        *,
        kwargs: dict[str, Any],
        pool: list[int],
    ) -> list[int]:
        discard_values = kwargs.get("miracle_dice_to_discard")
        if discard_values is None:
            discard_values = kwargs.get("discard_miracle_dice_values")
        if discard_values is None:
            discard_values = kwargs.get("miracle_dice_discard")
        values: list[int] = []
        if isinstance(discard_values, (list, tuple)):
            for value in list(discard_values):
                try:
                    values.append(int(value))
                except Exception:
                    continue
        if values:
            return values
        count = kwargs.get("discard_count")
        if count is None:
            count = kwargs.get("miracle_dice_discard_count")
        try:
            discard_count = int(count or 0)
        except Exception:
            discard_count = 0
        if discard_count <= 0:
            return []
        sorted_pool = sorted(int(v) for v in list(pool or []))
        if not sorted_pool:
            return []
        return list(sorted_pool[: min(discard_count, len(sorted_pool))])

    @staticmethod
    def _can_consume_discard_values(*, pool: list[int], values: list[int]) -> bool:
        remaining = list(pool or [])
        for value in list(values or []):
            try:
                idx = remaining.index(int(value))
            except Exception:
                return False
            remaining.pop(idx)
        return True

    @staticmethod
    def _consume_discard_values(*, pool: list[int], values: list[int]) -> list[int]:
        remaining = list(pool or [])
        for value in list(values or []):
            idx = remaining.index(int(value))
            remaining.pop(idx)
        return remaining

    def _use_hallowed_divine_intervention(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_martyrs():
            return False
        root, model, destroyed_position = self._resolve_divine_intervention_context(**kwargs)
        if root is None or model is None:
            logger.error("ERROR: DIVINE INTERVENTION: missing destroyed CHARACTER context")
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if not self._is_adepta_sororitas_character(root):
            logger.error("ERROR: DIVINE INTERVENTION: target must be an ADEPTA SORORITAS CHARACTER unit")
            return False
        if self._as_is_saint_celestine(root):
            logger.error("ERROR: DIVINE INTERVENTION: Saint Celestine cannot be selected")
            return False
        unit_id = self._as_sort_key(root)
        if unit_id and unit_id in self._as_divine_used_units():
            logger.error("ERROR: DIVINE INTERVENTION: this CHARACTER unit was already selected this battle")
            return False
        acts_mgr = self._as_miracle_dice_manager()
        if acts_mgr is None:
            logger.error("ERROR: DIVINE INTERVENTION: Acts of Faith manager unavailable")
            return False
        pool = list(getattr(acts_mgr, "miracle_dice", []) or [])
        if not pool:
            logger.error("ERROR: DIVINE INTERVENTION: no Miracle dice available to discard")
            return False
        discard_values = self._resolve_discard_values_from_kwargs(kwargs=kwargs, pool=pool)
        if not discard_values:
            logger.error("ERROR: DIVINE INTERVENTION: no Miracle dice selected to discard")
            return False
        if len(discard_values) < 1 or len(discard_values) > 3:
            logger.error("ERROR: DIVINE INTERVENTION: must discard 1-3 Miracle dice")
            return False
        if not self._can_consume_discard_values(pool=pool, values=discard_values):
            logger.error("ERROR: DIVINE INTERVENTION: selected Miracle dice are not available")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        try:
            acts_mgr.miracle_dice = self._consume_discard_values(pool=pool, values=discard_values)
        except Exception:
            logger.error("ERROR: DIVINE INTERVENTION: failed to discard Miracle dice")
            return False
        trigger_phase = kwargs.get("phase_name") or self._current_phase_name or ""
        self._as_divine_pending().append(
            {
                "unit": root,
                "model": model,
                "destroyed_position": destroyed_position,
                "discard_count": int(len(discard_values)),
                "trigger_phase_name": str(trigger_phase or ""),
                "trigger_phase_key": self._as_phase_key(trigger_phase),
                "source": str(getattr(stratagem, "name", "") or "DIVINE INTERVENTION"),
            }
        )
        if unit_id:
            self._as_divine_used_units().add(unit_id)
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            f"INFO: DIVINE INTERVENTION: will return {getattr(model, 'name', 'Model')} at phase end after discarding "
            f"{int(len(discard_values))} Miracle dice."
        )
        return True
