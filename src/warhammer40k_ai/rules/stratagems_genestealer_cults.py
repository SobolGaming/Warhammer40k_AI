from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class GenestealerCultsStratagemMixin:
    @staticmethod
    def _gsc_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                root = get_root()
            except (AttributeError, TypeError, ValueError):
                return unit
            if root is not None:
                return root
        return unit

    @staticmethod
    def _gsc_sort_key(unit: Any) -> str:
        try:
            return str(get_entity_id(unit) or "")
        except (AttributeError, TypeError, ValueError):
            return ""

    @staticmethod
    def _gsc_norm_name(name: str) -> str:
        text = str(name or "").strip().upper()
        return (
            text.replace("\u2019", "'")
            .replace("\u2018", "'")
            .replace("\u2010", "-")
            .replace("\u2011", "-")
            .replace("\u2012", "-")
            .replace("\u2013", "-")
            .replace("\u2014", "-")
        )

    def _gsc_pending_context(self, stratagem_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        wanted = self._gsc_norm_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._gsc_norm_name(reaction.get("stratagem", "")) != wanted:
                continue
            merged.update(dict(reaction))
            break
        for key, value in dict(kwargs or {}).items():
            if value is not None:
                merged[key] = value
        return merged

    def _gsc_reaction_exists(self, event_name: str, stratagem_name: str, *, unit: Any = None) -> bool:
        wanted = self._gsc_norm_name(stratagem_name)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            try:
                if str(reaction.get("event", "") or "") != str(event_name or ""):
                    continue
                if self._gsc_norm_name(reaction.get("stratagem", "")) != wanted:
                    continue
                if unit is not None:
                    if reaction.get("unit") is not unit and reaction.get("target_unit") is not unit:
                        continue
                return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _gsc_army(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        return get_army() if callable(get_army) else getattr(self.player, "army", None)

    def _gsc_detachment_mgr(self):
        army = self._gsc_army()
        if army is None:
            return None
        return getattr(army, "genestealer_cults_detachments", None)

    def _is_host_of_ascension_detachment(self) -> bool:
        mgr = self._gsc_detachment_mgr()
        checker = getattr(mgr, "is_host_of_ascension", None) if mgr is not None else None
        if callable(checker):
            return bool(checker())
        army = self._gsc_army()
        if army is None:
            return False
        faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        has_detachment = getattr(army, "has_detachment_type", None)
        if callable(has_detachment):
            return faction_id == "GC" and bool(has_detachment("Host of Ascension"))
        return False

    def _is_brood_brother_auxilia_detachment(self) -> bool:
        mgr = self._gsc_detachment_mgr()
        checker = getattr(mgr, "is_brood_brother_auxilia", None) if mgr is not None else None
        if callable(checker):
            return bool(checker())
        army = self._gsc_army()
        if army is None:
            return False
        faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        has_detachment = getattr(army, "has_detachment_type", None)
        if callable(has_detachment):
            return faction_id == "GC" and bool(has_detachment("Brood Brother Auxilia"))
        return False

    def _is_biosanctic_broodsurge_detachment(self) -> bool:
        mgr = self._gsc_detachment_mgr()
        checker = getattr(mgr, "is_biosanctic_broodsurge", None) if mgr is not None else None
        if callable(checker):
            return bool(checker())
        army = self._gsc_army()
        if army is None:
            return False
        faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        has_detachment = getattr(army, "has_detachment_type", None)
        if callable(has_detachment):
            return faction_id == "GC" and bool(has_detachment("Biosanctic Broodsurge"))
        return False

    def _is_outlander_claw_detachment(self) -> bool:
        mgr = self._gsc_detachment_mgr()
        checker = getattr(mgr, "is_outlander_claw", None) if mgr is not None else None
        if callable(checker):
            return bool(checker())
        army = self._gsc_army()
        if army is None:
            return False
        faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        has_detachment = getattr(army, "has_detachment_type", None)
        if callable(has_detachment):
            return faction_id == "GC" and bool(has_detachment("Outlander Claw"))
        return False

    def _is_final_day_detachment(self) -> bool:
        mgr = self._gsc_detachment_mgr()
        checker = getattr(mgr, "is_final_day", None) if mgr is not None else None
        if callable(checker):
            return bool(checker())
        army = self._gsc_army()
        if army is None:
            return False
        faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        has_detachment = getattr(army, "has_detachment_type", None)
        if callable(has_detachment):
            return faction_id == "GC" and bool(has_detachment("Final Day"))
        return False

    def _is_xenocreed_congregation_detachment(self) -> bool:
        mgr = self._gsc_detachment_mgr()
        checker = getattr(mgr, "is_xenocreed_congregation", None) if mgr is not None else None
        if callable(checker):
            return bool(checker())
        army = self._gsc_army()
        if army is None:
            return False
        faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        has_detachment = getattr(army, "has_detachment_type", None)
        if callable(has_detachment):
            return faction_id == "GC" and bool(has_detachment("Xenocreed Congregation"))
        return False

    @staticmethod
    def _gsc_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            try:
                return bool(is_alive())
            except (AttributeError, TypeError, ValueError):
                return False
        return bool(getattr(unit, "is_alive", True))

    def _gsc_owned_by_player(self, unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        try:
            army = unit.get_parent_army()
        except (AttributeError, TypeError, ValueError):
            return False
        return getattr(army, "player", None) is player

    def _gsc_is_genestealer_cults_unit(self, unit: Any) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        mgr = self._gsc_detachment_mgr()
        checker = getattr(mgr, "_unit_has_keyword_or_faction", None) if mgr is not None else None
        if callable(checker):
            try:
                return bool(checker(root, "GENESTEALER CULTS", faction_id="GC"))
            except (AttributeError, TypeError, ValueError):
                return False
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any("GENESTEALER CULTS")):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        return str(getattr(root, "faction_id", "") or "").strip().upper() == "GC"

    def _gsc_is_astra_militarum_unit(self, unit: Any) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        mgr = self._gsc_detachment_mgr()
        checker = getattr(mgr, "_unit_is_astra_militarum", None) if mgr is not None else None
        if callable(checker):
            try:
                return bool(checker(root))
            except (AttributeError, TypeError, ValueError):
                return False
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any("ASTRA MILITARUM")):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        return False

    def _gsc_is_tyranids_unit(self, unit: Any) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        mgr = self._gsc_detachment_mgr()
        checker = getattr(mgr, "_unit_is_tyranids", None) if mgr is not None else None
        if callable(checker):
            try:
                return bool(checker(root))
            except (AttributeError, TypeError, ValueError):
                return False
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any("TYRANIDS")):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        return False

    def _gsc_is_battleline(self, unit: Any) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            try:
                return bool(has_any("BATTLELINE"))
            except (AttributeError, TypeError, ValueError):
                return False
        keywords = [str(k or "").strip().upper() for k in list(getattr(root, "keywords", []) or [])]
        return "BATTLELINE" in keywords

    def _gsc_is_infantry(self, unit: Any) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            try:
                return bool(has_any("INFANTRY"))
            except (AttributeError, TypeError, ValueError):
                return False
        keywords = [str(k or "").strip().upper() for k in list(getattr(root, "keywords", []) or [])]
        return "INFANTRY" in keywords

    @staticmethod
    def _gsc_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return False
        checker = getattr(unit, "is_in_reserves", None)
        if callable(checker):
            try:
                return bool(checker())
            except (AttributeError, TypeError, ValueError):
                return False
        status = str(getattr(unit, "reserve_status", "deployed") or "").strip().lower()
        return status not in ("", "deployed")

    def _gsc_can_arrive_from_reserves(self, unit: Any) -> bool:
        if unit is None:
            return False
        turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        checker = getattr(unit, "can_arrive_from_reserves", None)
        if callable(checker):
            try:
                return bool(checker(turn))
            except (AttributeError, TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _gsc_has_deep_strike(unit: Any) -> bool:
        if unit is None:
            return False
        checker = getattr(unit, "has_deep_strike", None)
        if not callable(checker):
            return False
        try:
            return bool(checker())
        except (AttributeError, TypeError, ValueError):
            return False

    @staticmethod
    def _gsc_phase_key_from_name(phase_name: str) -> str:
        return str(phase_name or "").strip().upper().replace(" ", "_")

    @staticmethod
    def _gsc_phase_label(phase_key: str) -> str:
        key = str(phase_key or "").strip().upper()
        if key == "MOVEMENT_PHASE":
            return "Movement phase"
        if key == "SHOOTING_PHASE":
            return "Shooting phase"
        if key == "FIGHT_PHASE":
            return "Fight phase"
        return str(phase_key or "").strip().replace("_", " ").title()

    def _gsc_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        if not self._gsc_is_alive(root):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        if getattr(root, "embarked_in", None) is not None:
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._gsc_is_in_reserves(root):
            return False
        if require_targetable and not self._gsc_targetable(root):
            return False
        return True

    def _gsc_is_within_engagement_range_of_enemy(self, unit: Any) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._gsc_root(enemy)
            if enemy_root is None:
                continue
            if not self._gsc_on_battlefield(enemy_root, require_targetable=False):
                continue
            if bool(game_map.is_within_engagement_range(root, enemy_root)):
                return True
        return False

    def _gsc_place_unit_into_strategic_reserves(self, unit: Any, *, reason: str = "") -> bool:
        root = self._gsc_root(unit)
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
            set_reserve_status = getattr(member, "set_reserve_status", None)
            if callable(set_reserve_status):
                set_reserve_status("strategic_reserves")
            else:
                setattr(member, "reserve_status", "strategic_reserves")
            mark_midgame = getattr(member, "mark_entered_reserves_midgame", None)
            if callable(mark_midgame):
                mark_midgame(game=game)
            if bool(getattr(member, "is_aircraft", False)) and not bool(getattr(member, "hover_mode", False)):
                setattr(member, "_aircraft_return_turn", int(getattr(game, "turn", 0) or 0) + 1 if game is not None else 0)
            member.deployed = True
            member.reserve_turn_deployed = None
            member.arrived_from_reserves_this_turn = False
            if game_map is not None and isinstance(getattr(game_map, "units", None), list) and member in game_map.units:
                game_map.units.remove(member)
        return True

    @staticmethod
    def _gsc_has_shot_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "shot_this_round", False))

    @staticmethod
    def _gsc_has_fought_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "fought_this_phase", False))

    @staticmethod
    def _gsc_has_declared_charge_this_round(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        if round_state is None:
            return False
        if bool(getattr(round_state, "attempted_charge_this_round", False)):
            return True
        target_ids = getattr(round_state, "charge_target_ids", None)
        return bool(target_ids)

    @staticmethod
    def _gsc_has_keyword(unit: Any, keyword: str) -> bool:
        if unit is None:
            return False
        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any):
            try:
                return bool(has_any(str(keyword or "").strip().upper()))
            except (AttributeError, TypeError, ValueError):
                return False
        keywords = [str(value or "").strip().upper() for value in list(getattr(unit, "keywords", []) or [])]
        return str(keyword or "").strip().upper() in keywords

    def _gsc_is_character_unit(self, unit: Any) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        if self._gsc_has_keyword(root, "CHARACTER"):
            return True
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        return any(self._gsc_has_keyword(member, "CHARACTER") for member in list(members or []))

    def _gsc_is_monster_or_vehicle(self, unit: Any) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        return self._gsc_has_keyword(root, "MONSTER") or self._gsc_has_keyword(root, "VEHICLE")

    def _gsc_unit_name_tokens(self, unit: Any) -> set[str]:
        root = self._gsc_root(unit)
        if root is None:
            return set()
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        tokens: set[str] = set()
        for member in list(members or [root]):
            token = self._gsc_norm_name(getattr(member, "name", ""))
            if token:
                tokens.add(token)
        root_name = self._gsc_norm_name(getattr(root, "name", ""))
        if root_name:
            tokens.add(root_name)
        return tokens

    def _gsc_unit_has_any_name(self, unit: Any, *names: str) -> bool:
        wanted = {self._gsc_norm_name(name) for name in list(names or []) if self._gsc_norm_name(name)}
        if not wanted:
            return False
        return bool(self._gsc_unit_name_tokens(unit) & wanted)

    def _gsc_is_mounted_or_vehicle(self, unit: Any) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        return bool(self._gsc_has_keyword(root, "MOUNTED") or self._gsc_has_keyword(root, "VEHICLE"))

    def _gsc_is_biosanctic_stratagem_eligible_unit(self, unit: Any) -> bool:
        if not self._is_biosanctic_broodsurge_detachment():
            return False
        root = self._gsc_root(unit)
        if root is None:
            return False
        mgr = self._gsc_detachment_mgr()
        checker = getattr(mgr, "is_biosanctic_stratagem_eligible_unit", None) if mgr is not None else None
        if callable(checker):
            try:
                return bool(checker(root))
            except (AttributeError, TypeError, ValueError):
                return False
        names: list[str] = []
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        for member in list(members or [root]):
            names.append(str(getattr(member, "name", "") or "").strip().upper())
        return any(
            text in {"ABERRANTS", "BIOPHAGUS", "PURESTRAIN GENESTEALERS"}
            for text in list(names or [])
        )

    def _gsc_unit_in_candidates(self, root: Any, candidates: List[Any]) -> bool:
        if root is None:
            return False
        rid = self._gsc_sort_key(root)
        for candidate in list(candidates or []):
            cand_root = self._gsc_root(candidate)
            if cand_root is None:
                continue
            if cand_root is root:
                return True
            if rid and rid == self._gsc_sort_key(cand_root):
                return True
        return False

    def _gsc_resolve_unit_list(self, selected: Any) -> List[Any]:
        if selected is None:
            return []
        if isinstance(selected, (list, tuple, set)):
            raw = list(selected)
        else:
            raw = [selected]
        out: List[Any] = []
        seen: set[str] = set()
        for item in raw:
            root = self._gsc_root(item)
            if root is None:
                continue
            rid = self._gsc_sort_key(root)
            if rid and rid in seen:
                continue
            if rid:
                seen.add(rid)
            out.append(root)
        return out

    def _gsc_enemy_on_battlefield_candidates(self) -> List[Any]:
        game = getattr(self, "game", None)
        if game is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for player in list(getattr(game, "players", []) or []):
            if player is self.player:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                root = self._gsc_root(unit)
                if root is None:
                    continue
                rid = self._gsc_sort_key(root)
                if rid and rid in seen:
                    continue
                if rid:
                    seen.add(rid)
                if not self._gsc_is_alive(root):
                    continue
                if not self._gsc_on_battlefield(root, require_targetable=True):
                    continue
                out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_biosanctic_broodsurge_candidates(self) -> List[Any]:
        if not self._is_biosanctic_broodsurge_detachment():
            return []
        army = self._gsc_army()
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gsc_root(unit)
            if root is None:
                continue
            rid = self._gsc_sort_key(root)
            if rid and rid in seen:
                continue
            if rid:
                seen.add(rid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_genestealer_cults_unit(root):
                continue
            if not self._gsc_is_biosanctic_stratagem_eligible_unit(root):
                continue
            if not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_biosanctic_fight_candidates(self) -> List[Any]:
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        out: List[Any] = []
        for root in self._gsc_biosanctic_broodsurge_candidates():
            if self._gsc_has_fought_this_phase(root):
                continue
            is_eligible = getattr(root, "is_eligible_to_fight", None)
            if callable(is_eligible):
                try:
                    if not bool(is_eligible(game_map)):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_biosanctic_charge_candidates(self) -> List[Any]:
        game = getattr(self, "game", None)
        out: List[Any] = []
        for root in self._gsc_biosanctic_broodsurge_candidates():
            if self._gsc_has_declared_charge_this_round(root):
                continue
            can_charge = getattr(root, "can_declare_charge", None)
            if callable(can_charge):
                try:
                    if not bool(can_charge(game)):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_final_day_tyranids_candidates(self) -> List[Any]:
        if not self._is_final_day_detachment():
            return []
        army = self._gsc_army()
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gsc_root(unit)
            if root is None:
                continue
            uid = self._gsc_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_tyranids_unit(root):
                continue
            if not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_final_day_genestealer_cults_candidates(self, *, phase_key: str = "") -> List[Any]:
        if not self._is_final_day_detachment():
            return []
        normalized_phase = self._gsc_phase_key_from_name(phase_key)
        army = self._gsc_army()
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gsc_root(unit)
            if root is None:
                continue
            uid = self._gsc_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_genestealer_cults_unit(root):
                continue
            if self._gsc_is_tyranids_unit(root):
                continue
            if not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            if normalized_phase == "CHARGE_PHASE" and self._gsc_has_declared_charge_this_round(root):
                continue
            if normalized_phase == "FIGHT_PHASE" and self._gsc_has_fought_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_final_day_enemy_near_friendly_tyranids_candidates(self) -> List[Any]:
        if not self._is_final_day_detachment():
            return []
        mgr = self._gsc_detachment_mgr()
        in_range_fn = getattr(mgr, "final_day_target_within_range_of_friendly_tyranids", None) if mgr is not None else None
        if not callable(in_range_fn):
            return []
        out: List[Any] = []
        for enemy in self._gsc_enemy_on_battlefield_candidates():
            try:
                if bool(in_range_fn(enemy, range_in=1.0, game=self.game)):
                    out.append(enemy)
            except (AttributeError, TypeError, ValueError):
                continue
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_final_day_resistance_tunnels_candidates(self) -> List[Any]:
        if not self._is_final_day_detachment():
            return []
        army = self._gsc_army()
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gsc_root(unit)
            if root is None:
                continue
            uid = self._gsc_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not (self._gsc_is_genestealer_cults_unit(root) or self._gsc_is_tyranids_unit(root)):
                continue
            if not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            if self._gsc_is_within_engagement_range_of_enemy(root):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_xenocreed_bodyguard_candidates(self, *, require_on_battlefield: bool = True) -> List[Any]:
        if not self._is_xenocreed_congregation_detachment():
            return []
        army = self._gsc_army()
        if army is None:
            return []
        mgr = self._gsc_detachment_mgr()
        eligible_fn = getattr(mgr, "xenocreed_stratagem_eligible_unit", None) if mgr is not None else None
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gsc_root(unit)
            if root is None:
                continue
            uid = self._gsc_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_genestealer_cults_unit(root):
                continue
            if callable(eligible_fn):
                try:
                    if not bool(eligible_fn(root)):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            if require_on_battlefield and not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_xenocreed_fight_candidates(self) -> List[Any]:
        return sorted(
            [root for root in self._gsc_xenocreed_bodyguard_candidates(require_on_battlefield=True) if not self._gsc_has_fought_this_phase(root)],
            key=self._gsc_sort_key,
        )

    def _gsc_xenocreed_shooting_candidates(self) -> List[Any]:
        return sorted(
            [root for root in self._gsc_xenocreed_bodyguard_candidates(require_on_battlefield=True) if not self._gsc_has_shot_this_phase(root)],
            key=self._gsc_sort_key,
        )

    def _gsc_xenocreed_charge_candidates(self) -> List[Any]:
        out: List[Any] = []
        for root in self._gsc_xenocreed_bodyguard_candidates(require_on_battlefield=True):
            if self._gsc_has_declared_charge_this_round(root):
                continue
            can_charge = getattr(root, "can_declare_charge", None)
            if callable(can_charge):
                try:
                    if not bool(can_charge(self.game)):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_xenocreed_downtrodden_rise_candidates(self) -> List[Any]:
        if not self._is_xenocreed_congregation_detachment():
            return []
        army = self._gsc_army()
        cult_ambush = getattr(army, "cult_ambush", None) if army is not None else None
        if cult_ambush is None:
            return []
        units = list(getattr(cult_ambush, "get_units_in_cult_ambush", lambda **_k: [])(game=self.game, only_arrivable=True) or [])
        mgr = self._gsc_detachment_mgr()
        eligible_fn = getattr(mgr, "xenocreed_stratagem_eligible_unit", None) if mgr is not None else None
        out: List[Any] = []
        seen: set[str] = set()
        for unit in units:
            root = self._gsc_root(unit)
            if root is None:
                continue
            uid = self._gsc_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_genestealer_cults_unit(root):
                continue
            if callable(eligible_fn):
                try:
                    if not bool(eligible_fn(root)):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_xenocreed_character_candidates(self, *, exclude_model=None) -> List[Any]:
        if not self._is_xenocreed_congregation_detachment():
            return []
        mgr = self._gsc_detachment_mgr()
        candidate_fn = getattr(mgr, "xenocreed_character_units", None) if mgr is not None else None
        if not callable(candidate_fn):
            return []
        try:
            candidates = list(candidate_fn(exclude_model=exclude_model, include_reserves=True) or [])
        except (AttributeError, TypeError, ValueError):
            return []
        return sorted(
            [self._gsc_root(root) for root in candidates if self._gsc_root(root) is not None],
            key=self._gsc_sort_key,
        )

    def _gsc_xenocreed_path_of_anguish_candidates(
        self,
        attacker_unit: Any,
        *,
        killing_models_by_target: Any = None,
    ) -> List[Any]:
        if not self._is_xenocreed_congregation_detachment():
            return []
        enemy_root = self._gsc_root(attacker_unit)
        if enemy_root is None or self._gsc_owned_by_player(enemy_root, self.player):
            return []
        mgr = self._gsc_detachment_mgr()
        eligible_fn = getattr(mgr, "xenocreed_path_of_anguish_eligible_unit", None) if mgr is not None else None
        if not isinstance(killing_models_by_target, dict):
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for target_unit, destroyed_models in list(killing_models_by_target.items() or []):
            if not destroyed_models:
                continue
            target_root = self._gsc_root(target_unit)
            if target_root is None:
                continue
            uid = self._gsc_sort_key(target_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gsc_owned_by_player(target_root, self.player):
                continue
            if not self._gsc_on_battlefield(target_root, require_targetable=True):
                continue
            if callable(eligible_fn):
                try:
                    if not bool(eligible_fn(target_root)):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            out.append(target_root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_outlander_claw_army_units(self) -> List[Any]:
        if not self._is_outlander_claw_detachment():
            return []
        army = self._gsc_army()
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gsc_root(unit)
            if root is None:
                continue
            uid = self._gsc_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_genestealer_cults_unit(root):
                continue
            if not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_outlander_close_range_shoot_out_candidates(self) -> List[Any]:
        out: List[Any] = []
        for root in self._gsc_outlander_claw_army_units():
            if not self._gsc_is_mounted_or_vehicle(root):
                continue
            if self._gsc_has_shot_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_outlander_rapid_feint_candidates(self, enemy_unit: Any) -> List[Any]:
        enemy_root = self._gsc_root(enemy_unit)
        if enemy_root is None:
            return []
        out: List[Any] = []
        for root in self._gsc_outlander_claw_army_units():
            if not self._gsc_unit_has_any_name(root, "Achilles Ridgerunners", "Atalan Jackals"):
                continue
            if not self._gsc_unit_within_range_of_unit(root, enemy_root, 9.0):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_outlander_encircling_the_prey_candidates(self) -> List[Any]:
        edge_checker = getattr(self, "_unit_wholly_within_battlefield_edge_distance", None)
        if not callable(edge_checker):
            return []
        out: List[Any] = []
        for root in self._gsc_outlander_claw_army_units():
            if not self._gsc_is_mounted_or_vehicle(root):
                continue
            if self._gsc_is_within_engagement_range_of_enemy(root):
                continue
            if not bool(edge_checker(root, 9.0)):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_host_of_ascension_phase_attack_candidates(self, *, phase_key: str) -> List[Any]:
        if not self._is_host_of_ascension_detachment():
            return []
        normalized_phase = self._gsc_phase_key_from_name(phase_key)
        if normalized_phase not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return []
        army = self._gsc_army()
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gsc_root(unit)
            if root is None:
                continue
            rid = self._gsc_sort_key(root)
            if rid and rid in seen:
                continue
            if rid:
                seen.add(rid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_genestealer_cults_unit(root):
                continue
            if not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            if normalized_phase == "SHOOTING_PHASE" and self._gsc_has_shot_this_phase(root):
                continue
            if normalized_phase == "FIGHT_PHASE" and self._gsc_has_fought_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_coordinated_trap_enemy_candidates_for_units(
        self,
        *,
        phase_key: str,
        selected_units: List[Any],
    ) -> List[Any]:
        normalized_phase = self._gsc_phase_key_from_name(phase_key)
        enemy_candidates = self._gsc_enemy_on_battlefield_candidates()
        if normalized_phase != "FIGHT_PHASE":
            return enemy_candidates
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        selected_roots = self._gsc_resolve_unit_list(selected_units)
        if selected_roots:
            out: List[Any] = []
            for enemy in enemy_candidates:
                if all(bool(game_map.is_within_engagement_range(root, enemy)) for root in selected_roots):
                    out.append(enemy)
            return sorted(out, key=self._gsc_sort_key)

        friendly = self._gsc_host_of_ascension_phase_attack_candidates(phase_key="FIGHT_PHASE")
        out = []
        for enemy in enemy_candidates:
            engaged_count = 0
            for root in friendly:
                if bool(game_map.is_within_engagement_range(root, enemy)):
                    engaged_count += 1
                    if engaged_count >= 2:
                        out.append(enemy)
                        break
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_targetable(self, unit: Any) -> bool:
        return not bool(self._unit_cannot_be_target_of_stratagem(unit))

    def _gsc_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        eff_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            try:
                preview = apply_fn(stratagem, target_unit=target_unit) or {}
                eff_cost = int(preview.get("cost", eff_cost))
            except (AttributeError, TypeError, ValueError):
                eff_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        return bool(
            self.player.spend_command_points(
                int(eff_cost),
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Unknown')}",
                source="stratagem",
            )
        )

    def _gsc_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            raw_name = str(getattr(stratagem, "name", "") or "").strip().upper()
            if raw_name:
                used.add(raw_name)
            used.add(self._gsc_norm_name(getattr(stratagem, "name", "")))

    def _gsc_host_of_ascension_tunnel_crawlers_candidates(self) -> List[Any]:
        if not self._is_host_of_ascension_detachment():
            return []
        army = self._gsc_army()
        if army is None:
            return []
        cult_ambush = getattr(army, "cult_ambush", None)
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gsc_root(unit)
            if root is None:
                continue
            uid = self._gsc_sort_key(root)
            if uid and uid in seen:
                continue
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_genestealer_cults_unit(root):
                continue
            if not self._gsc_is_alive(root):
                continue
            if not self._gsc_targetable(root):
                continue
            if not self._gsc_is_in_reserves(root):
                continue
            if not self._gsc_has_deep_strike(root):
                continue
            if not self._gsc_can_arrive_from_reserves(root):
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        if cult_ambush is not None:
            cult_ambush_units = list(
                getattr(cult_ambush, "get_units_in_cult_ambush", lambda **_k: [])(
                    game=self.game,
                    only_arrivable=True,
                )
                or []
            )
            for unit in cult_ambush_units:
                root = self._gsc_root(unit)
                if root is None:
                    continue
                uid = self._gsc_sort_key(root)
                if uid and uid in seen:
                    continue
                if not self._gsc_owned_by_player(root, self.player):
                    continue
                if not self._gsc_is_genestealer_cults_unit(root):
                    continue
                if not self._gsc_is_alive(root):
                    continue
                if not self._gsc_can_arrive_from_reserves(root):
                    continue
                if uid:
                    seen.add(uid)
                out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_host_of_ascension_lying_in_wait_candidates(self) -> List[Any]:
        if not self._is_host_of_ascension_detachment():
            return []
        army = self._gsc_army()
        cult_ambush = getattr(army, "cult_ambush", None) if army is not None else None
        if cult_ambush is None:
            return []
        units = list(getattr(cult_ambush, "get_units_in_cult_ambush", lambda **_k: [])(game=self.game, only_arrivable=True) or [])
        out: List[Any] = []
        seen: set[str] = set()
        for unit in units:
            root = self._gsc_root(unit)
            if root is None:
                continue
            uid = self._gsc_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_genestealer_cults_unit(root):
                continue
            if not self._gsc_is_battleline(root):
                continue
            if not self._gsc_is_alive(root):
                continue
            if not self._gsc_targetable(root):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_host_of_ascension_return_to_the_shadows_candidates(self) -> List[Any]:
        if not self._is_host_of_ascension_detachment():
            return []
        army = self._gsc_army()
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gsc_root(unit)
            if root is None:
                continue
            uid = self._gsc_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_genestealer_cults_unit(root):
                continue
            if not self._gsc_is_infantry(root):
                continue
            if not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            if self._gsc_is_within_engagement_range_of_enemy(root):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_host_of_ascension_deadly_snare_candidates(self, *, target_units: List[Any]) -> List[Any]:
        if not self._is_host_of_ascension_detachment():
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._gsc_root(unit)
            if root is None:
                continue
            uid = self._gsc_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_genestealer_cults_unit(root):
                continue
            if not self._gsc_is_infantry(root):
                continue
            if not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _queue_genestealer_cults_host_of_ascension_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_host_of_ascension_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(game, "get_current_player", lambda: None)()
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())

        def _can_queue(stratagem: Any) -> bool:
            if stratagem is None:
                return False
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return False
            return self._gsc_norm_name(getattr(stratagem, "name", "")) not in used

        if phase_key == "MOVEMENT_PHASE":
            if active_player is self.player:
                stratagem = self.get_by_name("TUNNEL CRAWLERS")
                if not _can_queue(stratagem):
                    return
                candidates = self._gsc_host_of_ascension_tunnel_crawlers_candidates()
                if not candidates or self._gsc_reaction_exists("phase_start", stratagem.name):
                    return
                payload = {
                    "event": "phase_start",
                    "phase": "Movement phase",
                    "phase_name": "Movement phase",
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "candidates": candidates,
                }
                if len(candidates) == 1:
                    payload["unit"] = candidates[0]
                    payload["target_unit"] = candidates[0]
                self._queue_reaction(payload, use_timer=False)
                return

            stratagem = self.get_by_name("LYING IN WAIT")
            if not _can_queue(stratagem):
                return
            candidates = self._gsc_host_of_ascension_lying_in_wait_candidates()
            if not candidates or self._gsc_reaction_exists("phase_start", stratagem.name):
                return
            payload = {
                "event": "phase_start",
                "phase": "Movement phase",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        if active_player is not self.player:
            return
        phase_label = self._gsc_phase_label(phase_key)

        primed = self.get_by_name("PRIMED AND READIED")
        if _can_queue(primed):
            primed_candidates = self._gsc_host_of_ascension_phase_attack_candidates(phase_key=phase_key)
            if primed_candidates and not self._gsc_reaction_exists("phase_start", primed.name):
                payload = {
                    "event": "phase_start",
                    "phase": phase_label,
                    "phase_name": phase_label,
                    "stratagem": primed.name,
                    "cp_cost": primed.cp_cost,
                    "candidates": primed_candidates,
                }
                if len(primed_candidates) == 1:
                    payload["unit"] = primed_candidates[0]
                    payload["target_unit"] = primed_candidates[0]
                self._queue_reaction(payload, use_timer=False)

        coordinated = self.get_by_name("COORDINATED TRAP")
        if not _can_queue(coordinated):
            return
        friendly_candidates = self._gsc_host_of_ascension_phase_attack_candidates(phase_key=phase_key)
        if len(friendly_candidates) < 2:
            return
        enemy_candidates = self._gsc_coordinated_trap_enemy_candidates_for_units(
            phase_key=phase_key,
            selected_units=[],
        )
        if not enemy_candidates or self._gsc_reaction_exists("phase_start", coordinated.name):
            return
        payload = {
            "event": "phase_start",
            "phase": phase_label,
            "phase_name": phase_label,
            "stratagem": coordinated.name,
            "cp_cost": coordinated.cp_cost,
            "friendly_candidates": friendly_candidates,
            "enemy_candidates": enemy_candidates,
        }
        if len(friendly_candidates) == 2:
            payload["selected_units"] = list(friendly_candidates)
            if len(enemy_candidates) == 1:
                payload["enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_genestealer_cults_host_of_ascension_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_host_of_ascension_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        if player is self.player:
            return
        stratagem = self.get_by_name("RETURN TO THE SHADOWS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return
        candidates = self._gsc_host_of_ascension_return_to_the_shadows_candidates()
        if not candidates:
            return
        if self._gsc_reaction_exists("phase_end", stratagem.name):
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
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_genestealer_cults_host_of_ascension_charge_declared_reactions(
        self,
        *,
        charging_unit: Any,
        target_units: List[Any],
    ) -> None:
        if not self._is_host_of_ascension_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "charge phase":
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        charging_root = self._gsc_root(charging_unit)
        if charging_root is None:
            return
        if self._gsc_owned_by_player(charging_root, self.player):
            return
        if not self._gsc_on_battlefield(charging_root, require_targetable=False):
            return
        stratagem = self.get_by_name("A DEADLY SNARE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return
        candidates = self._gsc_host_of_ascension_deadly_snare_candidates(target_units=list(target_units or []))
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "charge_declared":
                continue
            if self._gsc_norm_name(reaction.get("stratagem", "")) != self._gsc_norm_name(stratagem.name):
                continue
            if self._gsc_root(reaction.get("charging_unit")) is charging_root:
                return
        payload = {
            "event": "charge_declared",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "charging_unit": charging_root,
            "enemy_unit": charging_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_genestealer_cults_biosanctic_broodsurge_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_biosanctic_broodsurge_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        stratagem = self.get_by_name("BIO-HORROR REVELATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return
        candidates = self._gsc_biosanctic_broodsurge_candidates()
        if not candidates or self._gsc_reaction_exists("phase_start", stratagem.name):
            return
        payload = {
            "event": "phase_start",
            "phase": "Shooting phase",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    @staticmethod
    def _gsc_bio_horror_effect_active(target_unit: Any, *, game: Any) -> bool:
        sr = getattr(target_unit, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("gsc_bio_horror_revelation_active")):
            return False
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
        expected_phase = str(sr.get("gsc_bio_horror_revelation_expires_phase", "") or "").strip().upper()
        if expected_phase and phase_key and expected_phase != phase_key:
            return False
        try:
            current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        except (TypeError, ValueError):
            current_turn = 0
        try:
            effect_turn = int(sr.get("gsc_bio_horror_revelation_turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        if current_turn and effect_turn and current_turn != effect_turn:
            return False
        return True

    def _gsc_bio_horror_has_attacker_penalty(self, target_unit: Any, *, attacker_key: str, phase_key: str) -> bool:
        sr = getattr(target_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        effects = sr.get("defensive_hit_mods")
        if not isinstance(effects, list):
            return False
        for effect in list(effects or []):
            if not isinstance(effect, dict):
                continue
            if str(effect.get("attacker_key", "") or "") != str(attacker_key or ""):
                continue
            if str(effect.get("expires_phase", "") or "").strip().upper() != str(phase_key or "").strip().upper():
                continue
            if "BIO-HORROR REVELATION" not in self._gsc_norm_name(str(effect.get("source", "") or "")):
                continue
            return True
        return False

    def _process_genestealer_cults_bio_horror_revelation_shooting_targets_selected(
        self,
        *,
        attacking_unit: Any,
        target_units: List[Any],
    ) -> None:
        if not self._is_biosanctic_broodsurge_detachment():
            return
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None:
            return
        attacker_root = self._gsc_root(attacking_unit)
        if attacker_root is None or self._gsc_owned_by_player(attacker_root, self.player):
            return
        if not self._gsc_on_battlefield(attacker_root, require_targetable=False):
            return
        try:
            from ..utility.aura_utils import unit_within_range_of_unit
        except (AttributeError, ImportError, TypeError, ValueError):
            return

        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        attacker_key = str(self._attacker_unit_key(attacker_root) or self._gsc_sort_key(attacker_root) or "")
        if not attacker_key:
            return
        seen: set[str] = set()
        for target in list(target_units or []):
            target_root = self._gsc_root(target)
            if target_root is None:
                continue
            target_id = self._gsc_sort_key(target_root)
            if target_id and target_id in seen:
                continue
            if target_id:
                seen.add(target_id)
            if not self._gsc_owned_by_player(target_root, self.player):
                continue
            if not self._gsc_bio_horror_effect_active(target_root, game=game):
                continue
            if not bool(unit_within_range_of_unit(target_root, attacker_root, 9.0, use_attached_aggregate=True)):
                continue
            if attacker_key and self._gsc_bio_horror_has_attacker_penalty(
                target_root,
                attacker_key=attacker_key,
                phase_key=phase_key,
            ):
                continue

            original_sr = getattr(attacker_root, "special_rules", None)
            attacker_sr = dict(original_sr) if isinstance(original_sr, dict) else {}
            marker = object()
            prior = {
                key: attacker_sr.get(key, marker)
                for key in (
                    "post_shoot_leadership_debuff_active",
                    "post_shoot_leadership_debuff_value",
                    "post_shoot_leadership_debuff_source",
                )
            }
            attacker_sr["post_shoot_leadership_debuff_active"] = True
            attacker_sr["post_shoot_leadership_debuff_value"] = 1
            attacker_sr["post_shoot_leadership_debuff_source"] = "BIO-HORROR REVELATION"
            attacker_root.special_rules = attacker_sr
            passed = True
            leadership_test = getattr(attacker_root, "pass_leadership_check", None)
            if callable(leadership_test):
                try:
                    passed = bool(leadership_test(game=game))
                except (AttributeError, TypeError, ValueError):
                    passed = True
            restored_sr = dict(getattr(attacker_root, "special_rules", None) or {})
            for key, value in list(prior.items()):
                if value is marker:
                    restored_sr.pop(key, None)
                else:
                    restored_sr[key] = value
            attacker_root.special_rules = restored_sr

            if passed:
                continue
            self._append_defensive_effect(
                target_root,
                "defensive_hit_mods",
                {
                    "value": 1,
                    "attack_type": "ranged",
                    "attacker_key": attacker_key,
                    "expires_phase": phase_key,
                    "source": "BIO-HORROR REVELATION",
                },
            )

    def _queue_genestealer_cults_biosanctic_saintly_paroxysm_model_destroyed_reactions(
        self,
        *,
        unit: Any,
        model: Any,
    ) -> None:
        if not self._is_biosanctic_broodsurge_detachment():
            return
        if unit is None or model is None:
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        current_phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if not current_phase_name:
            phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            if phase_key == "FIGHT_PHASE":
                current_phase_name = "fight phase"
        if current_phase_name != "fight phase":
            return
        source_unit = getattr(model, "parent_unit", None) or unit
        if source_unit is None:
            return
        if not self._gsc_owned_by_player(source_unit, self.player):
            return
        if not self._gsc_is_genestealer_cults_unit(source_unit):
            return
        if not self._gsc_is_character_unit(source_unit):
            return
        stratagem = self.get_by_name("SAINTLY PAROXYSM")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return
        enemy_unit = (
            getattr(source_unit, "_last_destroyed_by_unit", None)
            or getattr(unit, "_last_destroyed_by_unit", None)
        )
        enemy_root = self._gsc_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            return
        if self._gsc_owned_by_player(enemy_root, self.player):
            return
        if not self._gsc_on_battlefield(enemy_root, require_targetable=False):
            return
        payload = {
            "event": "model_destroyed_before_removal",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": source_unit,
            "target_unit": source_unit,
            "destroyed_model": model,
            "destroyed_source_unit": source_unit,
            "enemy_unit": enemy_root,
            "attacker_unit": enemy_root,
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_genestealer_cults_final_day_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_final_day_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {
            "COMMAND_PHASE",
            "MOVEMENT_PHASE",
            "SHOOTING_PHASE",
            "CHARGE_PHASE",
            "FIGHT_PHASE",
        }:
            return
        stratagem = self.get_by_name("PSI SURGE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return
        mgr = self._gsc_detachment_mgr()
        cooldown_fn = getattr(mgr, "final_day_psi_surge_on_cooldown", None) if mgr is not None else None
        if callable(cooldown_fn) and bool(cooldown_fn(game=game)):
            return
        candidates = self._gsc_final_day_tyranids_candidates()
        if not candidates or self._gsc_reaction_exists("phase_start", stratagem.name):
            return
        phase_label = self._gsc_phase_label(phase_key)
        payload = {
            "event": "phase_start",
            "phase": phase_label,
            "phase_name": phase_label,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_genestealer_cults_final_day_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_final_day_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE" or player is self.player:
            return
        stratagem = self.get_by_name("RESISTANCE TUNNELS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return
        candidates = self._gsc_final_day_resistance_tunnels_candidates()
        if not candidates or self._gsc_reaction_exists("phase_end", stratagem.name):
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
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_genestealer_cults_final_day_unit_destroyed_reactions(
        self,
        *,
        unit: Any,
        destroyed_by_unit: Any = None,
        **_kwargs,
    ) -> None:
        if not self._is_final_day_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            return
        game = getattr(self, "game", None)
        if game is None or unit is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is self.player:
            return
        destroyed_root = self._gsc_root(unit)
        enemy_root = self._gsc_root(destroyed_by_unit) if destroyed_by_unit is not None else None
        if destroyed_root is None or enemy_root is None:
            return
        if not self._gsc_owned_by_player(destroyed_root, self.player):
            return
        if not self._gsc_is_tyranids_unit(destroyed_root):
            return
        if not self._gsc_is_character_unit(destroyed_root):
            return
        if self._gsc_owned_by_player(enemy_root, self.player):
            return
        if not self._gsc_is_alive(enemy_root):
            return
        stratagem = self.get_by_name("AVENGE THE STAR CHILDREN")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return
        if self._gsc_reaction_exists("unit_destroyed", stratagem.name):
            return
        self._queue_reaction(
            {
                "event": "unit_destroyed",
                "phase_name": "Shooting phase" if phase_name == "shooting phase" else "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "destroyed_unit": destroyed_root,
                "enemy_unit": enemy_root,
                "destroyed_by_unit": enemy_root,
                "candidates": [destroyed_root],
            },
            use_timer=False,
        )

    def _queue_genestealer_cults_xenocreed_model_destroyed_reactions(
        self,
        *,
        attacker_unit: Any = None,
        target_unit: Any = None,
        target_model: Any = None,
        weapon_profile: Any = None,
    ) -> None:
        del weapon_profile  # Unused; parity with other queue hooks.
        if not self._is_xenocreed_congregation_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            return
        game = getattr(self, "game", None)
        if game is None or target_model is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is self.player:
            return
        destroyed_unit = getattr(target_model, "parent_unit", None) or target_unit
        destroyed_root = self._gsc_root(destroyed_unit)
        attacker_root = self._gsc_root(attacker_unit)
        if destroyed_root is None or attacker_root is None:
            return
        if not self._gsc_owned_by_player(destroyed_root, self.player):
            return
        if not self._gsc_is_genestealer_cults_unit(destroyed_root):
            return
        target_is_character = getattr(target_model, "is_character", False)
        if callable(target_is_character):
            try:
                target_is_character = target_is_character()
            except (AttributeError, TypeError, ValueError):
                target_is_character = False
        if not bool(target_is_character):
            return
        if self._gsc_owned_by_player(attacker_root, self.player):
            return
        if not self._gsc_is_alive(attacker_root):
            return
        stratagem = self.get_by_name("VENGEANCE FOR THE MARTYR!")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return
        candidates = self._gsc_xenocreed_character_candidates(exclude_model=target_model)
        if not candidates:
            return
        enemy_id = self._gsc_sort_key(attacker_root)
        destroyed_model_id = str(get_entity_id(target_model) or "")
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "model_destroyed":
                continue
            if self._gsc_norm_name(reaction.get("stratagem", "")) != self._gsc_norm_name(stratagem.name):
                continue
            reaction_enemy = self._gsc_root(reaction.get("enemy_unit") or reaction.get("attacker_unit"))
            reaction_model = reaction.get("destroyed_model") or reaction.get("target_model")
            reaction_enemy_id = self._gsc_sort_key(reaction_enemy)
            reaction_model_id = str(get_entity_id(reaction_model) or "")
            if reaction_enemy_id == enemy_id and reaction_model_id == destroyed_model_id:
                return
        payload = {
            "event": "model_destroyed",
            "phase_name": "Shooting phase" if phase_name == "shooting phase" else "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacker_unit": attacker_root,
            "destroyed_model": target_model,
            "target_model": target_model,
            "destroyed_unit": destroyed_unit,
            "target_unit": destroyed_unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_genestealer_cults_xenocreed_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: Any = None,
        killing_models_by_target: Any = None,
    ) -> None:
        if not self._is_xenocreed_congregation_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        game = getattr(self, "game", None)
        if game is None or attacker_unit is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._gsc_root(attacker_unit)
        if attacker_root is None or self._gsc_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("THE PATH OF ANGUISH")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return
        candidates = self._gsc_xenocreed_path_of_anguish_candidates(
            attacker_root,
            killing_models_by_target=killing_models_by_target,
        )
        if not candidates:
            return
        attacker_id = self._gsc_sort_key(attacker_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_shooting_resolved":
                continue
            if self._gsc_norm_name(reaction.get("stratagem", "")) != self._gsc_norm_name(stratagem.name):
                continue
            reaction_enemy = self._gsc_root(
                reaction.get("enemy_unit")
                or reaction.get("attacker_unit")
                or reaction.get("unit")
                or reaction.get("target_unit")
            )
            if reaction_enemy is not None and self._gsc_sort_key(reaction_enemy) == attacker_id:
                return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacker_unit": attacker_root,
            "hits_by_target": hits_by_target,
            "killing_models_by_target": killing_models_by_target,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_genestealer_cults_xenocreed_reinforcements_step_end_reactions(
        self,
        *,
        current_player: Any = None,
    ) -> None:
        if not self._is_xenocreed_congregation_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        acting_player = current_player if current_player is not None else getattr(game, "get_current_player", lambda: None)()
        if acting_player is None or acting_player is self.player:
            return
        stratagem = self.get_by_name("THE DOWNTRODDEN RISE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return
        candidates = self._gsc_xenocreed_downtrodden_rise_candidates()
        if not candidates:
            return
        if self._gsc_reaction_exists("reinforcements_step_end", stratagem.name):
            return
        payload = {
            "event": "reinforcements_step_end",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "current_player": acting_player,
            "current_player_id": str(getattr(acting_player, "id", "") or ""),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _roll_genestealer_cults_path_of_anguish_distance(self, unit: Any) -> int:
        from ..utility.event_bus import append_dice

        max_distance = int(dice_module.get_roll("D6") or 0)
        player = getattr(unit.get_parent_army(), "player", None) if unit is not None else None
        if player is not None:
            append_dice(
                player,
                f"The Path of Anguish roll: {int(max_distance or 0)} (move {int(max_distance or 0)}\") for {getattr(unit, 'name', 'Unit')}",
            )
        return int(max_distance)

    def _queue_genestealer_cults_outlander_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_outlander_claw_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            return
        game = getattr(self, "game", None)
        if game is None or unit is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        action_key = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
        if action_key not in {"move", "normal_move", "advance", "fall_back"}:
            return
        enemy_root = self._gsc_root(unit)
        if enemy_root is None or self._gsc_owned_by_player(enemy_root, self.player):
            return
        if not self._gsc_on_battlefield(enemy_root, require_targetable=False):
            return
        stratagem = self.get_by_name("RAPID FEINT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return
        candidates = self._gsc_outlander_rapid_feint_candidates(enemy_root)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_ended":
                continue
            if self._gsc_norm_name(reaction.get("stratagem", "")) != self._gsc_norm_name(stratagem.name):
                continue
            if self._gsc_root(reaction.get("enemy_unit")) is enemy_root:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "action": action_key,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_genestealer_cults_outlander_shooting_targets_selected_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: List[Any],
    ) -> None:
        del attacking_unit
        del target_units
        return

    def _queue_genestealer_cults_outlander_fight_targets_selected_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: List[Any],
    ) -> None:
        del attacking_unit
        del target_units
        return

    def _queue_genestealer_cults_outlander_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_outlander_claw_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE" or player is self.player:
            return
        stratagem = self.get_by_name("ENCIRCLING THE PREY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return
        candidates = self._gsc_outlander_encircling_the_prey_candidates()
        if not candidates or self._gsc_reaction_exists("phase_end", stratagem.name):
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
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _gsc_can_use_along_shadowed_trails(self) -> bool:
        if not self._is_outlander_claw_detachment():
            return False
        stratagem = self.get_by_name("ALONG SHADOWED TRAILS")
        if stratagem is None:
            return False
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return False
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        return self._gsc_norm_name(getattr(stratagem, "name", "")) not in used

    def _gsc_can_use_biosanctic_evasive_vanguard(self) -> bool:
        if not self._is_biosanctic_broodsurge_detachment():
            return False
        stratagem = self.get_by_name("EVASIVE VANGUARD")
        if stratagem is None:
            return False
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return False
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        return self._gsc_norm_name(getattr(stratagem, "name", "")) not in used

    def _gsc_commit_biosanctic_evasive_vanguard(self) -> bool:
        stratagem = self.get_by_name("EVASIVE VANGUARD")
        if stratagem is None:
            return False
        if not self._gsc_spend_cp(stratagem):
            return False
        self._gsc_finalize_use(stratagem, dequeue=False)
        return True

    @staticmethod
    def _gsc_positive_hits(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, (list, tuple, set, dict)):
            return bool(len(value))
        try:
            return int(value or 0) > 0
        except (TypeError, ValueError):
            return False

    def _gsc_unit_within_range_of_unit(self, source_unit: Any, target_unit: Any, range_inches: float) -> bool:
        source_root = self._gsc_root(source_unit)
        target_root = self._gsc_root(target_unit)
        if source_root is None or target_root is None:
            return False
        try:
            from ..utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return False
        try:
            return bool(
                unit_within_range_of_unit(
                    source_root,
                    target_root,
                    float(range_inches),
                    use_attached_aggregate=True,
                )
            )
        except Exception:
            return False

    def _gsc_is_visible_to_unit(self, source_unit: Any, target_unit: Any) -> bool:
        source_root = self._gsc_root(source_unit)
        target_root = self._gsc_root(target_unit)
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if source_root is None or target_root is None or game_map is None:
            return False

        get_source_models = getattr(source_root, "get_attached_unit_models", None)
        source_models_raw = (
            list(get_source_models() or [])
            if callable(get_source_models)
            else list(getattr(source_root, "models", []) or [])
        )
        source_models = []
        for model in list(source_models_raw or []):
            alive_attr = getattr(model, "is_alive", False)
            if bool(alive_attr() if callable(alive_attr) else alive_attr):
                source_models.append(model)
        if not source_models:
            return False

        can_see_unit = getattr(game, "_model_can_see_unit", None)
        if callable(can_see_unit):
            for model in list(source_models or []):
                try:
                    if bool(can_see_unit(model, target_root, game_map=game_map)):
                        return True
                except TypeError:
                    if bool(can_see_unit(model, target_root)):
                        return True
            return False

        has_los = getattr(source_root, "_has_line_of_sight_to_target", None)
        if callable(has_los):
            for model in list(source_models or []):
                try:
                    if bool(has_los(model, target_root, game_map)):
                        return True
                except Exception:
                    continue
            return False

        can_see_model = getattr(game_map, "can_model_see_model", None)
        if not callable(can_see_model):
            return True

        get_target_models = getattr(target_root, "get_attached_unit_models", None)
        target_models = (
            list(get_target_models() or [])
            if callable(get_target_models)
            else list(getattr(target_root, "models", []) or [])
        )
        target_models_alive = []
        for model in list(target_models or []):
            alive_attr = getattr(model, "is_alive", False)
            if bool(alive_attr() if callable(alive_attr) else alive_attr):
                target_models_alive.append(model)
        target_models = target_models_alive
        for source_model in list(source_models or []):
            for target_model in list(target_models or []):
                try:
                    if bool(can_see_model(source_model, target_model)):
                        return True
                except Exception:
                    continue
        return False

    def _gsc_unit_has_any_ranged_weapon(self, unit: Any) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        for model in list(models or []):
            alive_attr = getattr(model, "is_alive", False)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                is_ranged = getattr(wargear, "is_ranged", None)
                if callable(is_ranged) and bool(is_ranged()):
                    return True
        return False

    def _gsc_unit_has_ranged_weapon_in_range(self, source_unit: Any, target_unit: Any) -> bool:
        source_root = self._gsc_root(source_unit)
        target_root = self._gsc_root(target_unit)
        if source_root is None or target_root is None:
            return False
        try:
            from ..utility.aura_utils import model_within_range_of_unit
        except Exception:
            model_within_range_of_unit = None

        get_models = getattr(source_root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(source_root, "models", []) or [])
        fallback_ranged_weapon_found = False
        for model in list(models or []):
            alive_attr = getattr(model, "is_alive", False)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
                profiles = getattr(wargear, "profiles", None) or {}
                if not profiles:
                    fallback_ranged_weapon_found = True
                    continue
                for profile in list(profiles.values() or []):
                    if profile is None:
                        continue
                    max_range = 0.0
                    effective_range = getattr(profile, "_effective_range_max", None)
                    if callable(effective_range):
                        try:
                            max_range = float(effective_range(model) or 0.0)
                        except (TypeError, ValueError):
                            max_range = 0.0
                    if max_range <= 0.0:
                        range_obj = getattr(profile, "range", None)
                        try:
                            max_range = float(getattr(range_obj, "max", 0.0) or 0.0)
                        except (TypeError, ValueError):
                            max_range = 0.0
                    if max_range <= 0.0:
                        continue
                    if callable(model_within_range_of_unit):
                        try:
                            if bool(
                                model_within_range_of_unit(
                                    model,
                                    target_root,
                                    float(max_range),
                                    use_attached_aggregate=True,
                                )
                            ):
                                return True
                        except Exception:
                            continue
        return fallback_ranged_weapon_found

    def _gsc_true_genestealer_cults_unit(self, unit: Any) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        return bool(self._gsc_is_genestealer_cults_unit(root) and not self._gsc_is_astra_militarum_unit(root))

    def _gsc_brood_brother_auxilia_army_units(self) -> List[Any]:
        if not self._is_brood_brother_auxilia_detachment():
            return []
        army = self._gsc_army()
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gsc_root(unit)
            if root is None:
                continue
            rid = self._gsc_sort_key(root)
            if rid and rid in seen:
                continue
            if rid:
                seen.add(rid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_a_dark_network_candidates(self, enemy_unit: Any) -> List[Any]:
        enemy_root = self._gsc_root(enemy_unit)
        if enemy_root is None:
            return []
        out: list[Any] = []
        for root in self._gsc_brood_brother_auxilia_army_units():
            if not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            if not (self._gsc_is_astra_militarum_unit(root) or self._gsc_true_genestealer_cults_unit(root)):
                continue
            if self._gsc_is_monster_or_vehicle(root):
                continue
            if not self._gsc_unit_within_range_of_unit(root, enemy_root, 12.0):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_acceptable_losses_engaged_gsc_units(self, enemy_unit: Any) -> List[Any]:
        enemy_root = self._gsc_root(enemy_unit)
        if enemy_root is None:
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        out: list[Any] = []
        for root in self._gsc_brood_brother_auxilia_army_units():
            if not self._gsc_true_genestealer_cults_unit(root):
                continue
            if not self._gsc_on_battlefield(root, require_targetable=False):
                continue
            try:
                if bool(game_map.is_within_engagement_range(root, enemy_root)):
                    out.append(root)
            except Exception:
                continue
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_acceptable_losses_enemy_candidates(self) -> List[Any]:
        out: list[Any] = []
        for enemy_root in self._gsc_enemy_on_battlefield_candidates():
            if self._gsc_acceptable_losses_engaged_gsc_units(enemy_root):
                out.append(enemy_root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_symbiotic_destruction_astra_candidates(self) -> List[Any]:
        out: list[Any] = []
        for root in self._gsc_brood_brother_auxilia_army_units():
            if not self._gsc_is_astra_militarum_unit(root):
                continue
            if not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            if self._gsc_has_shot_this_phase(root):
                continue
            if not self._gsc_unit_has_any_ranged_weapon(root):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_symbiotic_destruction_gsc_candidates(self) -> List[Any]:
        out: list[Any] = []
        for root in self._gsc_brood_brother_auxilia_army_units():
            if not self._gsc_true_genestealer_cults_unit(root):
                continue
            if not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            if self._gsc_has_shot_this_phase(root):
                continue
            if not self._gsc_unit_has_any_ranged_weapon(root):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_symbiotic_enemy_candidates(self, astra_unit: Any, gsc_unit: Any) -> List[Any]:
        astra_root = self._gsc_root(astra_unit)
        gsc_root = self._gsc_root(gsc_unit)
        if astra_root is None or gsc_root is None or astra_root is gsc_root:
            return []
        out: list[Any] = []
        for enemy_root in self._gsc_enemy_on_battlefield_candidates():
            if not self._gsc_is_visible_to_unit(astra_root, enemy_root):
                continue
            if not self._gsc_is_visible_to_unit(gsc_root, enemy_root):
                continue
            if not self._gsc_unit_has_ranged_weapon_in_range(astra_root, enemy_root):
                continue
            if not self._gsc_unit_has_ranged_weapon_in_range(gsc_root, enemy_root):
                continue
            out.append(enemy_root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_regimental_reinforcements_candidates(self) -> List[Any]:
        out: list[Any] = []
        for root in self._gsc_brood_brother_auxilia_army_units():
            if self._gsc_is_alive(root):
                continue
            if not self._gsc_is_astra_militarum_unit(root):
                continue
            if not self._gsc_is_infantry(root):
                continue
            if not self._gsc_has_keyword(root, "REGIMENT"):
                continue
            if self._gsc_has_keyword(root, "ARTILLERY"):
                continue
            if self._gsc_is_character_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_in_the_shadow_of_iron_source_candidates(self) -> List[Any]:
        out: list[Any] = []
        for root in self._gsc_brood_brother_auxilia_army_units():
            if not self._gsc_is_astra_militarum_unit(root):
                continue
            if not self._gsc_has_keyword(root, "VEHICLE"):
                continue
            if not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_can_use_in_the_shadow_of_iron(self) -> bool:
        if not self._is_brood_brother_auxilia_detachment():
            return False
        stratagem = self.get_by_name("IN THE SHADOW OF IRON")
        if stratagem is None:
            return False
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return False
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        return self._gsc_norm_name(getattr(stratagem, "name", "")) not in used

    def _gsc_commit_in_the_shadow_of_iron(self, *, source_unit: Any = None) -> bool:
        stratagem = self.get_by_name("IN THE SHADOW OF IRON")
        if stratagem is None:
            return False
        if not self._gsc_spend_cp(stratagem, target_unit=source_unit):
            return False
        self._gsc_finalize_use(stratagem, dequeue=False)
        return True

    def _use_genestealer_cults_biosanctic_broodsurge_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_biosanctic_broodsurge_detachment():
            return None
        name_u = self._gsc_norm_name(getattr(stratagem, "name", ""))
        if name_u == "BIO-HORROR REVELATION":
            return self._use_genestealer_cults_bio_horror_revelation(stratagem, **kwargs)
        if name_u == "GENE-TWISTED MUSCLE":
            return self._use_genestealer_cults_gene_twisted_muscle(stratagem, **kwargs)
        if name_u == "HYPER-METABOLIC VIGOUR":
            return self._use_genestealer_cults_hyper_metabolic_vigour(stratagem, **kwargs)
        if name_u == "SAINTLY PAROXYSM":
            return self._use_genestealer_cults_saintly_paroxysm(stratagem, **kwargs)
        if name_u == "STIMULATED BIO-SURGE":
            return self._use_genestealer_cults_stimulated_bio_surge(stratagem, **kwargs)
        return None

    def _use_genestealer_cults_bio_horror_revelation(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: BIO-HORROR REVELATION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: BIO-HORROR REVELATION: not opponent's phase")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._gsc_root(target_unit) if target_unit is not None else None
        candidates = self._gsc_biosanctic_broodsurge_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: BIO-HORROR REVELATION: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: BIO-HORROR REVELATION: target must be your ABERRANTS, BIOPHAGUS or PURESTRAIN GENESTEALERS unit"
            )
            return False
        context_candidates = self._gsc_resolve_unit_list(context.get("candidates"))
        if context_candidates and not self._gsc_unit_in_candidates(target_root, context_candidates):
            logger.error("ERROR: BIO-HORROR REVELATION: target was not selected")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["gsc_bio_horror_revelation_active"] = True
        sr["gsc_bio_horror_revelation_source"] = str(
            getattr(stratagem, "name", "BIO-HORROR REVELATION") or "BIO-HORROR REVELATION"
        )
        sr["gsc_bio_horror_revelation_expires_phase"] = "SHOOTING_PHASE"
        if owner:
            sr["gsc_bio_horror_revelation_turn_owner"] = owner
        if turn:
            sr["gsc_bio_horror_revelation_turn"] = turn
        target_root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: BIO-HORROR REVELATION: %s forces nearby enemy shooters to take Leadership tests this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_gene_twisted_muscle(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: GENE-TWISTED MUSCLE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._gsc_root(target_unit) if target_unit is not None else None
        candidates = self._gsc_biosanctic_fight_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: GENE-TWISTED MUSCLE: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: GENE-TWISTED MUSCLE: target must be your eligible ABERRANTS, BIOPHAGUS or PURESTRAIN GENESTEALERS unit"
            )
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["gsc_gene_twisted_muscle_active"] = True
        sr["gsc_gene_twisted_muscle_wound_bonus"] = 1
        sr["gsc_gene_twisted_muscle_expires_phase"] = "FIGHT_PHASE"
        sr["gsc_gene_twisted_muscle_source"] = str(
            getattr(stratagem, "name", "GENE-TWISTED MUSCLE") or "GENE-TWISTED MUSCLE"
        )
        if owner:
            sr["gsc_gene_twisted_muscle_turn_owner"] = owner
        if turn:
            sr["gsc_gene_twisted_muscle_turn"] = turn
        target_root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: GENE-TWISTED MUSCLE: %s gains +1 to wound against MONSTER and VEHICLE units this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_hyper_metabolic_vigour(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: HYPER-METABOLIC VIGOUR: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._gsc_root(target_unit) if target_unit is not None else None
        candidates = self._gsc_biosanctic_fight_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: HYPER-METABOLIC VIGOUR: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: HYPER-METABOLIC VIGOUR: target must be your eligible ABERRANTS, BIOPHAGUS or PURESTRAIN GENESTEALERS unit"
            )
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["gsc_hyper_metabolic_vigour_active"] = True
        sr["gsc_hyper_metabolic_vigour_expires_phase"] = "FIGHT_PHASE"
        sr["gsc_hyper_metabolic_vigour_source"] = str(
            getattr(stratagem, "name", "HYPER-METABOLIC VIGOUR") or "HYPER-METABOLIC VIGOUR"
        )
        if owner:
            sr["gsc_hyper_metabolic_vigour_turn_owner"] = owner
        if turn:
            sr["gsc_hyper_metabolic_vigour_turn"] = turn
        sr["stratagem_pile_in_distance_override"] = 6.0
        sr["stratagem_pile_in_expires_phase"] = "FIGHT_PHASE"
        sr["stratagem_consolidate_distance_override"] = 6.0
        sr["stratagem_consolidate_expires_phase"] = "FIGHT_PHASE"
        sr["stratagem_choreographer_of_war_source"] = str(
            getattr(stratagem, "name", "HYPER-METABOLIC VIGOUR") or "HYPER-METABOLIC VIGOUR"
        )
        target_root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: HYPER-METABOLIC VIGOUR: %s can pile in and consolidate 6\" this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_saintly_paroxysm(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SAINTLY PAROXYSM: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False

        source_unit = context.get("destroyed_source_unit") or context.get("unit") or context.get("target_unit")
        if source_unit is None:
            source_unit = context.get("destroyed_unit")
        destroyed_model = context.get("destroyed_model")
        if source_unit is None or destroyed_model is None:
            logger.error("ERROR: SAINTLY PAROXYSM: missing destroyed CHARACTER model")
            return False
        if not self._gsc_owned_by_player(source_unit, self.player) or not self._gsc_is_character_unit(source_unit):
            logger.error("ERROR: SAINTLY PAROXYSM: destroyed model must belong to your CHARACTER")
            return False

        enemy_unit = context.get("enemy_unit") or context.get("attacker_unit")
        enemy_root = self._gsc_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            logger.error("ERROR: SAINTLY PAROXYSM: missing destroying enemy unit")
            return False
        if self._gsc_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: SAINTLY PAROXYSM: destroying unit is not an enemy unit")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=source_unit):
            return False

        roll = max(0, int(dice_module.get_roll("D6") or 0))
        mortal_wounds = 0
        if roll >= 2:
            source_name = self._gsc_norm_name(str(getattr(source_unit, "name", "") or ""))
            if source_name in {"ABOMINANT", "PATRIARCH"}:
                mortal_wounds = max(0, int(dice_module.get_roll("D3") or 0)) + max(0, int(dice_module.get_roll("D3") or 0))
            else:
                mortal_wounds = max(0, int(dice_module.get_roll("D3") or 0))
        source_root = self._gsc_root(source_unit) or source_unit
        if mortal_wounds > 0 and hasattr(source_root, "_apply_mortal_wounds_to_unit"):
            source_root._apply_mortal_wounds_to_unit(
                enemy_root,
                int(mortal_wounds),
                game_map=getattr(game, "map", None),
                attacker_unit=source_root,
                damage_source=str(getattr(stratagem, "name", "SAINTLY PAROXYSM") or "SAINTLY PAROXYSM"),
            )

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: SAINTLY PAROXYSM: roll=%d, %s suffers %d mortal wound(s).",
            int(roll),
            getattr(enemy_root, "name", "Enemy unit"),
            int(mortal_wounds),
        )
        return True

    def _use_genestealer_cults_stimulated_bio_surge(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: STIMULATED BIO-SURGE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: STIMULATED BIO-SURGE: not your phase")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._gsc_root(target_unit) if target_unit is not None else None
        candidates = self._gsc_biosanctic_charge_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: STIMULATED BIO-SURGE: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: STIMULATED BIO-SURGE: target must be your ABERRANTS, BIOPHAGUS or PURESTRAIN GENESTEALERS unit that has not declared a charge"
            )
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["gsc_stimulated_bio_surge_active"] = True
        sr["gsc_stimulated_bio_surge_bonus_per_target"] = 1
        sr["gsc_stimulated_bio_surge_max_bonus"] = 3
        sr["gsc_stimulated_bio_surge_expires_phase"] = "CHARGE_PHASE"
        sr["gsc_stimulated_bio_surge_source"] = str(
            getattr(stratagem, "name", "STIMULATED BIO-SURGE") or "STIMULATED BIO-SURGE"
        )
        if owner:
            sr["gsc_stimulated_bio_surge_turn_owner"] = owner
        if turn:
            sr["gsc_stimulated_bio_surge_turn"] = turn
        target_root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: STIMULATED BIO-SURGE: %s gains a conditional charge-roll bonus this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _queue_genestealer_cults_brood_brother_auxilia_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: Any,
    ) -> None:
        if not self._is_brood_brother_auxilia_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        game = getattr(self, "game", None)
        if game is None or attacker_unit is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return

        attacker_root = self._gsc_root(attacker_unit)
        if attacker_root is None:
            return
        if not self._gsc_owned_by_player(attacker_root, self.player):
            return
        if not self._gsc_is_astra_militarum_unit(attacker_root):
            return
        if not self._gsc_on_battlefield(attacker_root, require_targetable=True):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(attacker_root)):
            return

        stratagem = self.get_by_name("SUPPRESS AND OVERWHELM")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return

        candidates: list[Any] = []
        seen: set[str] = set()
        if isinstance(hits_by_target, dict):
            for target, hits in list(hits_by_target.items()):
                if not self._gsc_positive_hits(hits):
                    continue
                target_root = self._gsc_root(target)
                if target_root is None:
                    continue
                target_id = self._gsc_sort_key(target_root)
                if target_id and target_id in seen:
                    continue
                if target_id:
                    seen.add(target_id)
                if self._gsc_owned_by_player(target_root, self.player):
                    continue
                if not self._gsc_on_battlefield(target_root, require_targetable=True):
                    continue
                candidates.append(target_root)
        candidates = sorted(candidates, key=self._gsc_sort_key)
        if not candidates:
            return
        if self._gsc_reaction_exists("unit_shooting_resolved", stratagem.name, unit=attacker_root):
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": attacker_root,
            "target_unit": attacker_root,
            "attacker_unit": attacker_root,
            "enemy_candidates": candidates,
        }
        if len(candidates) == 1:
            payload["enemy_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_genestealer_cults_brood_brother_auxilia_unit_set_up_reactions(
        self,
        *,
        unit: Any,
        set_up_as_reinforcements: bool = False,
        **_kwargs,
    ) -> None:
        if not self._is_brood_brother_auxilia_detachment():
            return
        if not bool(set_up_as_reinforcements):
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        game = getattr(self, "game", None)
        if game is None or unit is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        enemy_root = self._gsc_root(unit)
        if enemy_root is None:
            return
        if self._gsc_owned_by_player(enemy_root, self.player):
            return
        if not self._gsc_on_battlefield(enemy_root, require_targetable=True):
            return

        stratagem = self.get_by_name("A DARK NETWORK")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return

        candidates = self._gsc_a_dark_network_candidates(enemy_root)
        if not candidates:
            return

        enemy_id = self._gsc_sort_key(enemy_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_set_up":
                continue
            if self._gsc_norm_name(reaction.get("stratagem", "")) != self._gsc_norm_name(stratagem.name):
                continue
            reaction_enemy = self._gsc_root(reaction.get("enemy_unit"))
            if reaction_enemy is not None and self._gsc_sort_key(reaction_enemy) == enemy_id:
                return

        payload = {
            "event": "unit_set_up",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_genestealer_cults_brood_brother_auxilia_unit_destroyed_reactions(
        self,
        *,
        unit: Any,
        destroyed_by_unit: Any = None,
        **_kwargs,
    ) -> None:
        if not self._is_brood_brother_auxilia_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            return
        game = getattr(self, "game", None)
        if game is None or unit is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is self.player:
            return

        destroyed_root = self._gsc_root(unit)
        if destroyed_root is None:
            return
        if not self._gsc_owned_by_player(destroyed_root, self.player):
            return
        if not self._gsc_unit_in_candidates(destroyed_root, self._gsc_regimental_reinforcements_candidates()):
            return

        stratagem = self.get_by_name("REGIMENTAL REINFORCEMENTS")
        if stratagem is None:
            return
        if bool(getattr(self, "_used_once_per_battle", {}).get("REGIMENTAL REINFORCEMENTS", False)):
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())
        if self._gsc_norm_name(getattr(stratagem, "name", "")) in used:
            return

        destroyed_id = self._gsc_sort_key(destroyed_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_destroyed":
                continue
            if self._gsc_norm_name(reaction.get("stratagem", "")) != self._gsc_norm_name(stratagem.name):
                continue
            reaction_destroyed = self._gsc_root(reaction.get("destroyed_unit") or reaction.get("unit"))
            if reaction_destroyed is not None and self._gsc_sort_key(reaction_destroyed) == destroyed_id:
                return

        self._queue_reaction(
            {
                "event": "unit_destroyed",
                "phase_name": "Shooting phase" if phase_name == "shooting phase" else "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "destroyed_unit": destroyed_root,
                "unit": destroyed_root,
                "target_unit": destroyed_root,
                "destroyed_by_unit": self._gsc_root(destroyed_by_unit) if destroyed_by_unit is not None else None,
                "candidates": [destroyed_root],
            },
            use_timer=False,
        )

    def _resolve_genestealer_cults_acceptable_losses_after_shooting(
        self,
        *,
        attacker_unit: Any,
        declared_targets: Any = None,
    ) -> None:
        if not self._is_brood_brother_auxilia_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        game = getattr(self, "game", None)
        if game is None or attacker_unit is None:
            return

        attacker_root = self._gsc_root(attacker_unit)
        if attacker_root is None or not self._gsc_owned_by_player(attacker_root, self.player):
            return

        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("gsc_acceptable_losses_active", False)):
            return
        expected_phase = str(sr.get("gsc_acceptable_losses_expires_phase", "") or "").strip().upper()
        if expected_phase and expected_phase != "SHOOTING_PHASE":
            return
        owner = str(sr.get("gsc_acceptable_losses_turn_owner", "") or "")
        if owner and owner != str(getattr(self.player, "id", "") or ""):
            return
        try:
            effect_turn = int(sr.get("gsc_acceptable_losses_turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if effect_turn and current_turn and effect_turn != current_turn:
            return

        target_id = str(sr.get("gsc_acceptable_losses_target_id", "") or "")
        if not target_id:
            return

        declared_roots = self._gsc_resolve_unit_list(declared_targets)
        if not any(str(get_entity_id(root) or "") == target_id for root in list(declared_roots or [])):
            return

        resolve_unit = getattr(game, "_resolve_unit_by_id", None)
        if not callable(resolve_unit):
            return

        for unit_id in list(sr.get("gsc_acceptable_losses_engaged_unit_ids", []) or []):
            engaged_root = self._gsc_root(resolve_unit(str(unit_id or "")))
            if engaged_root is None or not self._gsc_on_battlefield(engaged_root, require_targetable=False):
                continue
            roll = max(0, int(dice_module.get_roll("D6") or 0))
            if roll < 5:
                continue
            mortal_wounds = max(0, int(dice_module.get_roll("D3") or 0)) + 1
            if mortal_wounds <= 0:
                continue
            applier = getattr(attacker_root, "_apply_mortal_wounds_to_unit", None)
            if callable(applier):
                applier(
                    engaged_root,
                    int(mortal_wounds),
                    game_map=getattr(game, "map", None),
                    damage_source="gsc_acceptable_losses",
                )

    def _use_genestealer_cults_brood_brother_auxilia_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_brood_brother_auxilia_detachment():
            return None
        name_u = self._gsc_norm_name(getattr(stratagem, "name", ""))
        if name_u == "A DARK NETWORK":
            return self._use_genestealer_cults_a_dark_network(stratagem, **kwargs)
        if name_u == "ACCEPTABLE LOSSES":
            return self._use_genestealer_cults_acceptable_losses(stratagem, **kwargs)
        if name_u == "IN THE SHADOW OF IRON":
            return self._use_genestealer_cults_in_the_shadow_of_iron(stratagem, **kwargs)
        if name_u == "REGIMENTAL REINFORCEMENTS":
            return self._use_genestealer_cults_regimental_reinforcements(stratagem, **kwargs)
        if name_u == "SUPPRESS AND OVERWHELM":
            return self._use_genestealer_cults_suppress_and_overwhelm(stratagem, **kwargs)
        if name_u == "SYMBIOTIC DESTRUCTION":
            return self._use_genestealer_cults_symbiotic_destruction(stratagem, **kwargs)
        return None

    def _use_genestealer_cults_outlander_claw_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_outlander_claw_detachment():
            return None
        name_u = self._gsc_norm_name(getattr(stratagem, "name", ""))
        if name_u == "ALONG SHADOWED TRAILS":
            return self._use_genestealer_cults_along_shadowed_trails(stratagem, **kwargs)
        if name_u == "CLOSE-RANGE SHOOT-OUT":
            return self._use_genestealer_cults_close_range_shoot_out(stratagem, **kwargs)
        if name_u == "RAPID FEINT":
            return self._use_genestealer_cults_rapid_feint(stratagem, **kwargs)
        if name_u == "ENCIRCLING THE PREY":
            return self._use_genestealer_cults_encircling_the_prey(stratagem, **kwargs)
        return None

    def _use_genestealer_cults_along_shadowed_trails(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        game = getattr(self, "game", None)
        if game is None:
            return False
        marker_id = str(context.get("marker_id", "") or "").strip()
        point = context.get("point")
        if not marker_id or not isinstance(point, (list, tuple)) or len(point) < 2:
            logger.error("ERROR: ALONG SHADOWED TRAILS: marker and relocation point are required")
            return False
        army = self._gsc_army()
        cult_ambush = getattr(army, "cult_ambush", None) if army is not None else None
        if cult_ambush is None:
            logger.error("ERROR: ALONG SHADOWED TRAILS: Cult Ambush manager unavailable")
            return False
        valid, reason = cult_ambush.validate_evasive_vanguard_relocation(
            marker_id,
            point,
            game=game,
        )
        if not bool(valid):
            logger.error("ERROR: ALONG SHADOWED TRAILS: %s", str(reason or "invalid relocation point"))
            return False
        if not self._gsc_spend_cp(stratagem):
            return False
        applied = bool(
            cult_ambush.apply_evasive_vanguard_relocation(
                marker_id,
                point,
                threatened_marker_ids=list(context.get("threatened_marker_ids", []) or []),
                game=game,
            )
        )
        if not applied:
            logger.error("ERROR: ALONG SHADOWED TRAILS: failed to relocate Cult Ambush marker")
            return False
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: ALONG SHADOWED TRAILS: relocated a threatened Cult Ambush marker more than 9\" from enemy units."
        )
        return True

    def _use_genestealer_cults_close_range_shoot_out(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CLOSE-RANGE SHOOT-OUT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: CLOSE-RANGE SHOOT-OUT: not your Shooting phase")
            return False
        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_resolve_unit_list(context.get("candidates"))
        if not candidates:
            candidates = self._gsc_outlander_close_range_shoot_out_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: CLOSE-RANGE SHOOT-OUT: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: CLOSE-RANGE SHOOT-OUT: target must be your GENESTEALER CULTS MOUNTED or VEHICLE unit that has not shot"
            )
            return False
        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["gsc_outlander_close_range_shoot_out_active"] = True
        sr["gsc_outlander_close_range_shoot_out_owner"] = owner_id
        sr["gsc_outlander_close_range_shoot_out_turn"] = turn
        sr["gsc_outlander_close_range_shoot_out_phase"] = "SHOOTING_PHASE"
        sr["gsc_outlander_close_range_shoot_out_range"] = 18.0
        sr["gsc_outlander_close_range_shoot_out_source"] = str(
            getattr(stratagem, "name", "CLOSE-RANGE SHOOT-OUT") or "CLOSE-RANGE SHOOT-OUT"
        )
        target_root.special_rules = sr
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: CLOSE-RANGE SHOOT-OUT: %s gains LETHAL HITS on ranged attacks against targets within 18\" this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_rapid_feint(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: RAPID FEINT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: RAPID FEINT: not opponent's Movement phase")
            return False
        action_key = str(context.get("action", "") or "").strip().lower().replace("-", "_").replace(" ", "_")
        if action_key and action_key not in {"move", "normal_move", "advance", "fall_back"}:
            logger.error("ERROR: RAPID FEINT: trigger move must be a Normal, Advance, or Fall Back move")
            return False
        enemy_root = self._gsc_root(context.get("enemy_unit") or context.get("moving_unit"))
        if enemy_root is None or self._gsc_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: RAPID FEINT: missing enemy unit context")
            return False
        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_resolve_unit_list(context.get("candidates"))
        if not candidates:
            candidates = self._gsc_outlander_rapid_feint_candidates(enemy_root)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: RAPID FEINT: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: RAPID FEINT: target must be an Achilles Ridgerunners or Atalan Jackals unit within 9\" of the enemy unit"
            )
            return False
        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: RAPID FEINT: reactive move queue unavailable")
            return False
        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        request = queue_move(
            player=self.player,
            unit=target_root,
            max_distance=6,
            kind="genestealer_cults_rapid_feint",
            movement_type="move",
            reactive_movement_type="move",
            source=str(getattr(stratagem, "name", "RAPID FEINT") or "RAPID FEINT"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
            allow_skip=True,
        )
        if request is None:
            logger.error("ERROR: RAPID FEINT: failed to queue movement decision")
            return False
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: RAPID FEINT: %s can make a Normal move of up to 6\".",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_encircling_the_prey(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: ENCIRCLING THE PREY: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: ENCIRCLING THE PREY: not opponent's Fight phase")
            return False
        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_resolve_unit_list(context.get("candidates"))
        if not candidates:
            candidates = self._gsc_outlander_encircling_the_prey_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: ENCIRCLING THE PREY: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: ENCIRCLING THE PREY: target must be your GENESTEALER CULTS MOUNTED or VEHICLE unit not in Engagement Range and wholly within 9\" of a battlefield edge"
            )
            return False
        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        if not self._gsc_place_unit_into_strategic_reserves(
            target_root,
            reason=str(getattr(stratagem, "name", "ENCIRCLING THE PREY") or "ENCIRCLING THE PREY"),
        ):
            logger.error("ERROR: ENCIRCLING THE PREY: failed to place target into Strategic Reserves")
            return False
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: ENCIRCLING THE PREY: %s enters Strategic Reserves.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_a_dark_network(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: A DARK NETWORK: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: A DARK NETWORK: not opponent's Movement phase")
            return False

        enemy_root = self._gsc_root(context.get("enemy_unit"))
        if enemy_root is None or self._gsc_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: A DARK NETWORK: missing enemy unit that was set up from Reserves")
            return False

        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_resolve_unit_list(context.get("candidates"))
        if not candidates:
            candidates = self._gsc_a_dark_network_candidates(enemy_root)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: A DARK NETWORK: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: A DARK NETWORK: target must be an eligible ASTRA MILITARUM or GENESTEALER CULTS unit within 12\""
            )
            return False

        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: A DARK NETWORK: reactive move queue unavailable")
            return False
        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        request = queue_move(
            player=self.player,
            unit=target_root,
            max_distance=6,
            kind="genestealer_cults_a_dark_network",
            movement_type="move",
            reactive_movement_type="a_dark_network",
            source=str(getattr(stratagem, "name", "A DARK NETWORK") or "A DARK NETWORK"),
            moving_unit=enemy_root,
        )
        if request is None:
            logger.error("ERROR: A DARK NETWORK: failed to queue movement decision")
            return False

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: A DARK NETWORK: %s can make a Normal move of up to 6\".",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_acceptable_losses(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: ACCEPTABLE LOSSES: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: ACCEPTABLE LOSSES: not your Shooting phase")
            return False

        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = [
            root
            for root in self._gsc_symbiotic_destruction_astra_candidates()
            if root is not None
        ]
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: ACCEPTABLE LOSSES: missing Astra Militarum target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error("ERROR: ACCEPTABLE LOSSES: target must be an eligible ASTRA MILITARUM unit that has not shot")
            return False

        enemy_root = self._gsc_root(
            context.get("enemy_unit")
            or context.get("target_enemy_unit")
            or context.get("attacking_unit")
            or context.get("attacker_unit")
        )
        enemy_candidates = self._gsc_resolve_unit_list(context.get("enemy_candidates"))
        if not enemy_candidates:
            enemy_candidates = self._gsc_acceptable_losses_enemy_candidates()
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = enemy_candidates[0]
            else:
                logger.error("ERROR: ACCEPTABLE LOSSES: missing engaged enemy unit")
                return False
        if not self._gsc_unit_in_candidates(enemy_root, enemy_candidates):
            logger.error("ERROR: ACCEPTABLE LOSSES: selected enemy must be within Engagement Range of friendly GENESTEALER CULTS units")
            return False

        engaged_units = self._gsc_resolve_unit_list(context.get("engaged_gsc_units"))
        if not engaged_units:
            engaged_units = self._gsc_acceptable_losses_engaged_gsc_units(enemy_root)
        if not engaged_units:
            logger.error("ERROR: ACCEPTABLE LOSSES: selected enemy must be within Engagement Range of one or more friendly GENESTEALER CULTS units")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False

        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["gsc_acceptable_losses_active"] = True
        sr["gsc_acceptable_losses_target_id"] = str(get_entity_id(enemy_root) or "")
        sr["gsc_acceptable_losses_engaged_unit_ids"] = [
            str(get_entity_id(unit) or "")
            for unit in list(engaged_units or [])
            if str(get_entity_id(unit) or "")
        ]
        sr["gsc_acceptable_losses_expires_phase"] = "SHOOTING_PHASE"
        sr["gsc_acceptable_losses_source"] = str(
            getattr(stratagem, "name", "ACCEPTABLE LOSSES") or "ACCEPTABLE LOSSES"
        )
        if owner:
            sr["gsc_acceptable_losses_turn_owner"] = owner
        if turn:
            sr["gsc_acceptable_losses_turn"] = turn
        target_root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: ACCEPTABLE LOSSES: %s can target %s despite Engagement Range restrictions this phase.",
            getattr(target_root, "name", "Unit"),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_genestealer_cults_in_the_shadow_of_iron(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        game = getattr(self, "game", None)
        if game is None:
            return False

        source_root = self._gsc_root(context.get("unit") or context.get("target_unit") or context.get("source_unit"))
        candidates = self._gsc_in_the_shadow_of_iron_source_candidates()
        if source_root is None:
            if len(candidates) == 1:
                source_root = candidates[0]
            else:
                logger.error("ERROR: IN THE SHADOW OF IRON: missing Astra Militarum VEHICLE unit")
                return False
        if not self._gsc_unit_in_candidates(source_root, candidates):
            logger.error("ERROR: IN THE SHADOW OF IRON: target must be an eligible ASTRA MILITARUM VEHICLE unit")
            return False

        marker_id = str(context.get("marker_id", "") or "").strip()
        point = context.get("point")
        if not marker_id or not isinstance(point, (list, tuple)) or len(point) < 2:
            logger.error("ERROR: IN THE SHADOW OF IRON: marker and relocation point are required")
            return False

        army = self._gsc_army()
        cult_ambush = getattr(army, "cult_ambush", None) if army is not None else None
        if cult_ambush is None:
            logger.error("ERROR: IN THE SHADOW OF IRON: Cult Ambush manager unavailable")
            return False
        valid, reason = cult_ambush.validate_in_the_shadow_of_iron_relocation(
            marker_id,
            point,
            source_unit=source_root,
            game=game,
        )
        if not bool(valid):
            logger.error("ERROR: IN THE SHADOW OF IRON: %s", str(reason or "invalid relocation point"))
            return False
        if not self._gsc_spend_cp(stratagem, target_unit=source_root):
            return False
        applied = bool(
            cult_ambush.apply_in_the_shadow_of_iron_relocation(
                marker_id,
                point,
                source_unit=source_root,
                threatened_marker_ids=list(context.get("threatened_marker_ids", []) or []),
                game=game,
            )
        )
        if not applied:
            logger.error("ERROR: IN THE SHADOW OF IRON: failed to relocate Cult Ambush marker")
            return False

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: IN THE SHADOW OF IRON: relocated a threatened Cult Ambush marker wholly within 6\" of %s.",
            getattr(source_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_regimental_reinforcements(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: REGIMENTAL REINFORCEMENTS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: REGIMENTAL REINFORCEMENTS: not opponent's Shooting phase")
            return False
        if bool(getattr(self, "_used_once_per_battle", {}).get("REGIMENTAL REINFORCEMENTS", False)):
            logger.error("ERROR: REGIMENTAL REINFORCEMENTS: already used this battle")
            return False

        destroyed_root = self._gsc_root(context.get("destroyed_unit") or context.get("unit") or context.get("target_unit"))
        pending_candidates = self._gsc_resolve_unit_list(context.get("candidates"))
        if destroyed_root is None:
            if len(pending_candidates) == 1:
                destroyed_root = pending_candidates[0]
            else:
                logger.error("ERROR: REGIMENTAL REINFORCEMENTS: missing destroyed unit")
                return False
        if pending_candidates:
            if not self._gsc_unit_in_candidates(destroyed_root, pending_candidates):
                logger.error("ERROR: REGIMENTAL REINFORCEMENTS: target unit was not just destroyed")
                return False
        else:
            pending_match = False
            for reaction in list(getattr(self, "_pending_reactions", []) or []):
                if str(reaction.get("event", "") or "") != "unit_destroyed":
                    continue
                if self._gsc_norm_name(reaction.get("stratagem", "")) != self._gsc_norm_name(stratagem.name):
                    continue
                reaction_destroyed = self._gsc_root(reaction.get("destroyed_unit") or reaction.get("unit"))
                if reaction_destroyed is destroyed_root:
                    pending_match = True
                    break
            if not pending_match:
                logger.error("ERROR: REGIMENTAL REINFORCEMENTS: target unit must have been just destroyed")
                return False
        if not self._gsc_unit_in_candidates(destroyed_root, self._gsc_regimental_reinforcements_candidates()):
            logger.error("ERROR: REGIMENTAL REINFORCEMENTS: target must be a destroyed ASTRA MILITARUM INFANTRY REGIMENT unit")
            return False

        army = self._gsc_army()
        cult_ambush = getattr(army, "cult_ambush", None) if army is not None else None
        if cult_ambush is None:
            logger.error("ERROR: REGIMENTAL REINFORCEMENTS: Cult Ambush manager unavailable")
            return False
        if not self._gsc_spend_cp(stratagem, target_unit=destroyed_root):
            return False

        roll = max(0, int(dice_module.get_roll("D6") or 0))
        if roll < 3:
            self._used_once_per_battle["REGIMENTAL REINFORCEMENTS"] = True
            self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
            logger.info("INFO: REGIMENTAL REINFORCEMENTS: roll=%d, no replacement unit is added.", int(roll))
            return True

        new_unit = cult_ambush.clone_unit_into_cult_ambush(destroyed_root, game=game)
        if new_unit is None:
            logger.error("ERROR: REGIMENTAL REINFORCEMENTS: failed to create replacement unit")
            return False
        rebuild = getattr(game, "rebuild_entity_registry", None)
        if callable(rebuild):
            rebuild()

        find_marker_position = getattr(cult_ambush, "find_marker_position", None)
        marker_possible = bool(callable(find_marker_position) and find_marker_position(game) is not None)
        if marker_possible:
            from ..engine.decision_kinds import DECISION_PICK_POINT
            from ..engine.decisions import DecisionOption, DecisionRequest

            request = DecisionRequest.create(
                DECISION_PICK_POINT,
                'Regimental Reinforcements: place one Cult Ambush marker more than 9" horizontally from all enemy units.',
                player_id=getattr(self.player, "id", None),
                options=[
                    DecisionOption.create(
                        "Place Cult Ambush Marker",
                        payload={"action": "place_marker"},
                    )
                ],
                context={
                    "ability": "regimental_reinforcements_marker_placement",
                    "ability_name": "Regimental Reinforcements",
                    "owner_player_id": str(getattr(self.player, "id", "") or ""),
                    "replacement_unit_id": str(get_entity_id(new_unit) or ""),
                    "destroyed_unit_id": str(get_entity_id(destroyed_root) or ""),
                },
            )
            game.request_decision(request)

        self._used_once_per_battle["REGIMENTAL REINFORCEMENTS"] = True
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: REGIMENTAL REINFORCEMENTS: roll=%d, added %s to Cult Ambush%s.",
            int(roll),
            getattr(new_unit, "name", "Unit"),
            " and queued marker placement" if marker_possible else "",
        )
        return True

    def _use_genestealer_cults_suppress_and_overwhelm(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: SUPPRESS AND OVERWHELM: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: SUPPRESS AND OVERWHELM: not your phase")
            return False

        attacker_unit = context.get("unit") or context.get("target_unit") or context.get("attacker_unit")
        attacker_root = self._gsc_root(attacker_unit) if attacker_unit is not None else None
        if attacker_root is None:
            logger.error("ERROR: SUPPRESS AND OVERWHELM: missing source Astra Militarum unit")
            return False
        if not self._gsc_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: SUPPRESS AND OVERWHELM: source unit is not yours")
            return False
        if not self._gsc_is_astra_militarum_unit(attacker_root):
            logger.error("ERROR: SUPPRESS AND OVERWHELM: source must be an Astra Militarum unit")
            return False
        if not self._gsc_on_battlefield(attacker_root, require_targetable=True):
            return False

        enemy_candidates = self._gsc_resolve_unit_list(context.get("enemy_candidates"))
        enemy_unit = context.get("enemy_unit") or context.get("target_enemy_unit")
        enemy_root = self._gsc_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = enemy_candidates[0]
            else:
                logger.error("ERROR: SUPPRESS AND OVERWHELM: missing enemy unit hit by the source unit")
                return False
        if self._gsc_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: SUPPRESS AND OVERWHELM: selected enemy unit is not valid")
            return False
        if not self._gsc_on_battlefield(enemy_root, require_targetable=True):
            logger.error("ERROR: SUPPRESS AND OVERWHELM: selected enemy unit must be on the battlefield")
            return False
        if enemy_candidates and not self._gsc_unit_in_candidates(enemy_root, enemy_candidates):
            logger.error("ERROR: SUPPRESS AND OVERWHELM: selected enemy unit was not hit by the source unit")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=attacker_root):
            return False

        sr = getattr(enemy_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["gsc_suppress_and_overwhelm_active"] = True
        sr["gsc_suppress_and_overwhelm_source"] = str(
            getattr(stratagem, "name", "SUPPRESS AND OVERWHELM") or "SUPPRESS AND OVERWHELM"
        )
        sr["gsc_suppress_and_overwhelm_source_unit_id"] = str(self._gsc_sort_key(attacker_root) or "")
        if owner:
            sr["gsc_suppress_and_overwhelm_turn_owner"] = owner
        if turn:
            sr["gsc_suppress_and_overwhelm_turn"] = turn
        enemy_root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: SUPPRESS AND OVERWHELM: %s cannot fire Overwatch this turn and GENESTEALER CULTS units can re-roll charge rolls against it.",
            getattr(enemy_root, "name", "Enemy unit"),
        )
        return True

    def _use_genestealer_cults_symbiotic_destruction(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: SYMBIOTIC DESTRUCTION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: SYMBIOTIC DESTRUCTION: not your Shooting phase")
            return False

        selected_units = self._gsc_resolve_unit_list(
            context.get("units")
            or context.get("selected_units")
            or context.get("friendly_units")
            or []
        )
        astra_root = self._gsc_root(
            context.get("astra_unit")
            or context.get("unit")
            or context.get("target_unit")
            or (selected_units[0] if selected_units else None)
        )
        gsc_root = self._gsc_root(
            context.get("gsc_unit")
            or context.get("other_unit")
            or context.get("support_unit")
            or (selected_units[1] if len(selected_units) > 1 else None)
        )
        astra_candidates = self._gsc_symbiotic_destruction_astra_candidates()
        gsc_candidates = self._gsc_symbiotic_destruction_gsc_candidates()
        if astra_root is None:
            if len(astra_candidates) == 1:
                astra_root = astra_candidates[0]
            else:
                logger.error("ERROR: SYMBIOTIC DESTRUCTION: missing Astra Militarum unit")
                return False
        if gsc_root is None:
            if len(gsc_candidates) == 1:
                gsc_root = gsc_candidates[0]
            else:
                logger.error("ERROR: SYMBIOTIC DESTRUCTION: missing Genestealer Cults unit")
                return False
        if astra_root is gsc_root:
            logger.error("ERROR: SYMBIOTIC DESTRUCTION: must select one Astra Militarum unit and one different Genestealer Cults unit")
            return False
        if not self._gsc_unit_in_candidates(astra_root, astra_candidates):
            logger.error("ERROR: SYMBIOTIC DESTRUCTION: selected Astra Militarum unit is not eligible")
            return False
        if not self._gsc_unit_in_candidates(gsc_root, gsc_candidates):
            logger.error("ERROR: SYMBIOTIC DESTRUCTION: selected Genestealer Cults unit is not eligible")
            return False

        enemy_root = self._gsc_root(
            context.get("enemy_unit")
            or context.get("target_enemy_unit")
            or context.get("attacking_unit")
            or context.get("attacker_unit")
        )
        enemy_candidates = self._gsc_resolve_unit_list(context.get("enemy_candidates"))
        if not enemy_candidates:
            enemy_candidates = self._gsc_symbiotic_enemy_candidates(astra_root, gsc_root)
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = enemy_candidates[0]
            else:
                logger.error("ERROR: SYMBIOTIC DESTRUCTION: missing enemy unit")
                return False
        if not self._gsc_unit_in_candidates(enemy_root, enemy_candidates):
            logger.error(
                "ERROR: SYMBIOTIC DESTRUCTION: enemy must be visible to both selected units and within range of at least one ranged weapon from each"
            )
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=astra_root):
            return False

        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        enemy_id = str(get_entity_id(enemy_root) or "")
        source_name = str(getattr(stratagem, "name", "SYMBIOTIC DESTRUCTION") or "SYMBIOTIC DESTRUCTION")
        for root in (astra_root, gsc_root):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["gsc_symbiotic_destruction_active"] = True
            sr["gsc_symbiotic_destruction_target_id"] = enemy_id
            sr["gsc_symbiotic_destruction_target_lock"] = True
            sr["gsc_symbiotic_destruction_reroll_wound_values"] = [1]
            sr["gsc_symbiotic_destruction_expires_phase"] = "SHOOTING_PHASE"
            sr["gsc_symbiotic_destruction_source"] = source_name
            if owner:
                sr["gsc_symbiotic_destruction_turn_owner"] = owner
            if turn:
                sr["gsc_symbiotic_destruction_turn"] = turn
            root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: SYMBIOTIC DESTRUCTION: %s and %s are locked to %s and re-roll wound rolls of 1 this phase.",
            getattr(astra_root, "name", "Unit 1"),
            getattr(gsc_root, "name", "Unit 2"),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_genestealer_cults_final_day_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_final_day_detachment():
            return None
        name_u = self._gsc_norm_name(getattr(stratagem, "name", ""))
        if name_u == "AVENGE THE STAR CHILDREN":
            return self._use_genestealer_cults_avenge_the_star_children(stratagem, **kwargs)
        if name_u == "DARTING ATTACKS":
            return self._use_genestealer_cults_darting_attacks(stratagem, **kwargs)
        if name_u == "DIVINE IMPERATIVE":
            return self._use_genestealer_cults_divine_imperative(stratagem, **kwargs)
        if name_u == "HYPERFEROCITY":
            return self._use_genestealer_cults_hyperferocity(stratagem, **kwargs)
        if name_u == "PSI SURGE":
            return self._use_genestealer_cults_psi_surge(stratagem, **kwargs)
        if name_u == "RESISTANCE TUNNELS":
            return self._use_genestealer_cults_resistance_tunnels(stratagem, **kwargs)
        return None

    def _use_genestealer_cults_avenge_the_star_children(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: AVENGE THE STAR CHILDREN: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: AVENGE THE STAR CHILDREN: not opponent's Shooting phase")
            return False

        destroyed_root = self._gsc_root(context.get("destroyed_unit"))
        enemy_root = self._gsc_root(
            context.get("enemy_unit")
            or context.get("destroyed_by_unit")
            or context.get("attacking_unit")
            or context.get("attacker_unit")
        )
        if destroyed_root is None:
            logger.error("ERROR: AVENGE THE STAR CHILDREN: missing destroyed TYRANIDS CHARACTER unit")
            return False
        if enemy_root is None:
            logger.error("ERROR: AVENGE THE STAR CHILDREN: missing destroying enemy unit")
            return False
        if not self._gsc_owned_by_player(destroyed_root, self.player):
            logger.error("ERROR: AVENGE THE STAR CHILDREN: destroyed unit is not yours")
            return False
        if not self._gsc_is_tyranids_unit(destroyed_root) or not self._gsc_is_character_unit(destroyed_root):
            logger.error("ERROR: AVENGE THE STAR CHILDREN: target must be your destroyed TYRANIDS CHARACTER unit")
            return False
        if self._gsc_is_alive(destroyed_root):
            logger.error("ERROR: AVENGE THE STAR CHILDREN: target unit was not destroyed")
            return False
        if self._gsc_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: AVENGE THE STAR CHILDREN: destroying unit must be an enemy unit")
            return False

        if not self._gsc_spend_cp(stratagem):
            return False
        mgr = self._gsc_detachment_mgr()
        mark_fn = getattr(mgr, "mark_final_day_avenged_enemy", None) if mgr is not None else None
        if not callable(mark_fn) or not bool(mark_fn(enemy_root, source=str(getattr(stratagem, "name", "") or ""))):
            logger.error("ERROR: AVENGE THE STAR CHILDREN: failed to mark the destroying enemy unit")
            return False

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: AVENGE THE STAR CHILDREN: %s is marked for friendly GENESTEALER CULTS attacks until end of battle.",
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_genestealer_cults_darting_attacks(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip()
        phase_key = self._gsc_phase_key_from_name(phase_name)
        if phase_key not in {"SHOOTING_PHASE", "CHARGE_PHASE"}:
            logger.error("ERROR: DARTING ATTACKS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: DARTING ATTACKS: not your phase")
            return False

        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_final_day_tyranids_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: DARTING ATTACKS: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error("ERROR: DARTING ATTACKS: target must be your TYRANIDS unit")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["gsc_final_day_darting_attacks_active"] = True
        sr["gsc_final_day_darting_attacks_expires_phase"] = phase_key
        sr["gsc_final_day_darting_attacks_source"] = str(getattr(stratagem, "name", "DARTING ATTACKS") or "DARTING ATTACKS")
        if owner:
            sr["gsc_final_day_darting_attacks_turn_owner"] = owner
        if turn:
            sr["gsc_final_day_darting_attacks_turn"] = turn
        target_root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: DARTING ATTACKS: %s can %s after Falling Back until end of %s.",
            getattr(target_root, "name", "Unit"),
            "shoot" if phase_key == "SHOOTING_PHASE" else "declare a charge",
            self._gsc_phase_label(phase_key),
        )
        return True

    def _use_genestealer_cults_divine_imperative(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip()
        phase_key = self._gsc_phase_key_from_name(phase_name)
        if phase_key != "CHARGE_PHASE":
            logger.error("ERROR: DIVINE IMPERATIVE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: DIVINE IMPERATIVE: not your Charge phase")
            return False

        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_final_day_genestealer_cults_candidates(phase_key="CHARGE_PHASE")
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: DIVINE IMPERATIVE: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error("ERROR: DIVINE IMPERATIVE: target must be your GENESTEALER CULTS unit that has not declared a charge")
            return False

        enemy_candidates = self._gsc_resolve_unit_list(context.get("enemy_candidates"))
        if not enemy_candidates:
            enemy_candidates = self._gsc_final_day_enemy_near_friendly_tyranids_candidates()
        enemy_root = self._gsc_root(
            context.get("enemy_unit")
            or context.get("target_enemy_unit")
            or context.get("attacking_unit")
            or context.get("attacker_unit")
        )
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = enemy_candidates[0]
            else:
                logger.error("ERROR: DIVINE IMPERATIVE: missing enemy target unit")
                return False
        if not self._gsc_unit_in_candidates(enemy_root, enemy_candidates):
            logger.error("ERROR: DIVINE IMPERATIVE: enemy target must be within Engagement Range of one or more friendly TYRANIDS units")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["gsc_final_day_divine_imperative_active"] = True
        sr["gsc_final_day_divine_imperative_expires_phase"] = "CHARGE_PHASE"
        sr["gsc_final_day_divine_imperative_source"] = str(
            getattr(stratagem, "name", "DIVINE IMPERATIVE") or "DIVINE IMPERATIVE"
        )
        sr["gsc_final_day_divine_imperative_target_id"] = self._gsc_sort_key(enemy_root)
        sr["gsc_final_day_divine_imperative_charge_bonus"] = 1
        if owner:
            sr["gsc_final_day_divine_imperative_turn_owner"] = owner
        if turn:
            sr["gsc_final_day_divine_imperative_turn"] = turn
        target_root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: DIVINE IMPERATIVE: %s gains +1 to Charge rolls and can re-roll charges when targeting %s this phase.",
            getattr(target_root, "name", "Unit"),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_genestealer_cults_hyperferocity(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip()
        phase_key = self._gsc_phase_key_from_name(phase_name)
        if phase_key != "FIGHT_PHASE":
            logger.error("ERROR: HYPERFEROCITY: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False

        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_final_day_genestealer_cults_candidates(phase_key="FIGHT_PHASE")
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: HYPERFEROCITY: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error("ERROR: HYPERFEROCITY: target must be your GENESTEALER CULTS unit that has not fought")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["gsc_final_day_hyperferocity_active"] = True
        sr["gsc_final_day_hyperferocity_expires_phase"] = "FIGHT_PHASE"
        sr["gsc_final_day_hyperferocity_source"] = str(getattr(stratagem, "name", "HYPERFEROCITY") or "HYPERFEROCITY")
        if owner:
            sr["gsc_final_day_hyperferocity_turn_owner"] = owner
        if turn:
            sr["gsc_final_day_hyperferocity_turn"] = turn
        target_root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: HYPERFEROCITY: %s re-rolls Wound rolls of 1 in melee this phase, upgrading to full re-rolls against enemies near friendly TYRANIDS.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_psi_surge(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip()
        phase_key = self._gsc_phase_key_from_name(phase_name)
        if phase_key not in {"COMMAND_PHASE", "MOVEMENT_PHASE", "SHOOTING_PHASE", "CHARGE_PHASE", "FIGHT_PHASE"}:
            logger.error("ERROR: PSI SURGE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        mgr = self._gsc_detachment_mgr()
        cooldown_fn = getattr(mgr, "final_day_psi_surge_on_cooldown", None) if mgr is not None else None
        if callable(cooldown_fn) and bool(cooldown_fn(game=game)):
            logger.error("ERROR: PSI SURGE: stratagem is still on cooldown until the end of your next Command phase")
            return False

        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_final_day_tyranids_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: PSI SURGE: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error("ERROR: PSI SURGE: target must be your TYRANIDS unit")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["gsc_final_day_psi_surge_active"] = True
        sr["gsc_final_day_psi_surge_cooldown_active"] = True
        sr["gsc_final_day_psi_surge_range_bonus"] = 3.0
        sr["gsc_final_day_psi_surge_source"] = str(getattr(stratagem, "name", "PSI SURGE") or "PSI SURGE")
        if owner:
            sr["gsc_final_day_psi_surge_turn_owner"] = owner
        if turn:
            sr["gsc_final_day_psi_surge_turn"] = turn
        target_root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: PSI SURGE: %s increases the range of its Catalyst ability by 3\" until the start of your next Command phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_resistance_tunnels(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: RESISTANCE TUNNELS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: RESISTANCE TUNNELS: not opponent's Fight phase")
            return False

        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_final_day_resistance_tunnels_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: RESISTANCE TUNNELS: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error("ERROR: RESISTANCE TUNNELS: target must be your GENESTEALER CULTS or TYRANIDS unit not within Engagement Range")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        if not self._gsc_place_unit_into_strategic_reserves(
            target_root,
            reason=str(getattr(stratagem, "name", "RESISTANCE TUNNELS") or "RESISTANCE TUNNELS"),
        ):
            logger.error("ERROR: RESISTANCE TUNNELS: failed to place target into Strategic Reserves")
            return False

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: RESISTANCE TUNNELS: %s enters Strategic Reserves.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_xenocreed_congregation_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_xenocreed_congregation_detachment():
            return None
        name_u = self._gsc_norm_name(getattr(stratagem, "name", ""))
        if name_u == "FRENZIED DEVOTION":
            return self._use_genestealer_cults_frenzied_devotion(stratagem, **kwargs)
        if name_u == "THE DOWNTRODDEN RISE":
            return self._use_genestealer_cults_the_downtrodden_rise(stratagem, **kwargs)
        if name_u == "THE PATH OF ANGUISH":
            return self._use_genestealer_cults_the_path_of_anguish(stratagem, **kwargs)
        if name_u == "TIRELESS FERVOUR":
            return self._use_genestealer_cults_tireless_fervour(stratagem, **kwargs)
        if name_u == "TRANSCENDENT CELERITY":
            return self._use_genestealer_cults_transcendent_celerity(stratagem, **kwargs)
        if name_u == "VENGEANCE FOR THE MARTYR!":
            return self._use_genestealer_cults_vengeance_for_the_martyr(stratagem, **kwargs)
        return None

    def _use_genestealer_cults_frenzied_devotion(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: FRENZIED DEVOTION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_resolve_unit_list(context.get("candidates"))
        if not candidates:
            candidates = self._gsc_xenocreed_fight_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: FRENZIED DEVOTION: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: FRENZIED DEVOTION: target must be your Acolyte Hybrids, Hybrid Metamorphs, or Neophyte Hybrids unit that has not fought"
            )
            return False
        mgr = self._gsc_detachment_mgr()
        apply_fn = getattr(mgr, "apply_xenocreed_frenzied_devotion", None) if mgr is not None else None
        if not callable(apply_fn):
            logger.error("ERROR: FRENZIED DEVOTION: detachment manager hook unavailable")
            return False
        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        if not bool(apply_fn(target_root, game=game, source_name=str(getattr(stratagem, "name", "") or ""))):
            logger.error("ERROR: FRENZIED DEVOTION: failed to apply temporary melee bonuses")
            return False
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: FRENZIED DEVOTION: %s improves non-CHARACTER melee Attacks and Weapon Skill by 1 and gains [HAZARDOUS] this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_transcendent_celerity(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: TRANSCENDENT CELERITY: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: TRANSCENDENT CELERITY: not your Shooting phase")
            return False
        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_resolve_unit_list(context.get("candidates"))
        if not candidates:
            candidates = self._gsc_xenocreed_shooting_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: TRANSCENDENT CELERITY: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: TRANSCENDENT CELERITY: target must be your Acolyte Hybrids, Hybrid Metamorphs, or Neophyte Hybrids unit that has not shot"
            )
            return False
        mgr = self._gsc_detachment_mgr()
        apply_fn = getattr(mgr, "apply_xenocreed_transcendent_celerity", None) if mgr is not None else None
        if not callable(apply_fn):
            logger.error("ERROR: TRANSCENDENT CELERITY: detachment manager hook unavailable")
            return False
        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        if not bool(apply_fn(target_root, game=game, source_name=str(getattr(stratagem, "name", "") or ""))):
            logger.error("ERROR: TRANSCENDENT CELERITY: failed to apply temporary ranged keywords")
            return False
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: TRANSCENDENT CELERITY: %s gains [ASSAULT] on ranged weapons this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_tireless_fervour(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: TIRELESS FERVOUR: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: TIRELESS FERVOUR: not your Charge phase")
            return False
        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_resolve_unit_list(context.get("candidates"))
        if not candidates:
            candidates = self._gsc_xenocreed_charge_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: TIRELESS FERVOUR: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: TIRELESS FERVOUR: target must be your Acolyte Hybrids, Hybrid Metamorphs, or Neophyte Hybrids unit that has not declared a charge"
            )
            return False
        mgr = self._gsc_detachment_mgr()
        apply_fn = getattr(mgr, "apply_xenocreed_tireless_fervour", None) if mgr is not None else None
        if not callable(apply_fn):
            logger.error("ERROR: TIRELESS FERVOUR: detachment manager hook unavailable")
            return False
        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        if not bool(apply_fn(target_root, game=game, source_name=str(getattr(stratagem, "name", "") or ""))):
            logger.error("ERROR: TIRELESS FERVOUR: failed to apply charge permissions")
            return False
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: TIRELESS FERVOUR: %s can charge after Advancing or Falling Back this phase and may re-roll the charge against enemies engaged with friendly CHARACTER units.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_vengeance_for_the_martyr(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: VENGEANCE FOR THE MARTYR!: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: VENGEANCE FOR THE MARTYR!: not opponent's Shooting phase")
            return False

        destroyed_model = context.get("destroyed_model") or context.get("target_model")
        destroyed_unit = context.get("destroyed_unit") or getattr(destroyed_model, "parent_unit", None) or context.get("target_unit")
        destroyed_root = self._gsc_root(destroyed_unit)
        enemy_root = self._gsc_root(
            context.get("enemy_unit")
            or context.get("destroyed_by_unit")
            or context.get("attacking_unit")
            or context.get("attacker_unit")
        )
        if destroyed_model is None or destroyed_root is None:
            logger.error("ERROR: VENGEANCE FOR THE MARTYR!: missing destroyed GENESTEALER CULTS CHARACTER model")
            return False
        if enemy_root is None:
            logger.error("ERROR: VENGEANCE FOR THE MARTYR!: missing destroying enemy unit")
            return False
        if not self._gsc_owned_by_player(destroyed_root, self.player):
            logger.error("ERROR: VENGEANCE FOR THE MARTYR!: destroyed model is not yours")
            return False
        if not self._gsc_is_genestealer_cults_unit(destroyed_root):
            logger.error("ERROR: VENGEANCE FOR THE MARTYR!: destroyed model must be GENESTEALER CULTS")
            return False
        destroyed_model_is_character = getattr(destroyed_model, "is_character", False)
        if callable(destroyed_model_is_character):
            try:
                destroyed_model_is_character = destroyed_model_is_character()
            except (AttributeError, TypeError, ValueError):
                destroyed_model_is_character = False
        if not bool(destroyed_model_is_character):
            logger.error("ERROR: VENGEANCE FOR THE MARTYR!: destroyed model must be a CHARACTER")
            return False
        if self._gsc_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: VENGEANCE FOR THE MARTYR!: destroying unit must be an enemy unit")
            return False

        candidates = self._gsc_resolve_unit_list(context.get("candidates"))
        if not candidates:
            candidates = self._gsc_xenocreed_character_candidates(exclude_model=destroyed_model)
        target_root = self._gsc_root(context.get("unit"))
        target_from_target = self._gsc_root(context.get("target_unit"))
        if target_root is None and self._gsc_unit_in_candidates(target_from_target, candidates):
            target_root = target_from_target
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: VENGEANCE FOR THE MARTYR!: missing target CHARACTER unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: VENGEANCE FOR THE MARTYR!: target must be one other friendly GENESTEALER CULTS CHARACTER on the battlefield or in Reserves"
            )
            return False

        mgr = self._gsc_detachment_mgr()
        mark_fn = getattr(mgr, "mark_xenocreed_martyr_enemy", None) if mgr is not None else None
        if not callable(mark_fn):
            logger.error("ERROR: VENGEANCE FOR THE MARTYR!: detachment manager hook unavailable")
            return False
        reroll_mode = "full" if self._gsc_unit_has_any_name(destroyed_unit, "Magus", "Primus", "Acolyte Iconward") else "ones"
        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        if not bool(
            mark_fn(
                enemy_root,
                source=str(getattr(stratagem, "name", "") or ""),
                reroll_mode=reroll_mode,
            )
        ):
            logger.error("ERROR: VENGEANCE FOR THE MARTYR!: failed to mark the destroying enemy")
            return False
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: VENGEANCE FOR THE MARTYR!: %s is marked until end of battle; friendly Acolyte Hybrids, Hybrid Metamorphs, and Neophyte Hybrids re-roll %s against it.",
            getattr(enemy_root, "name", "Enemy"),
            "Hit rolls" if reroll_mode == "full" else "Hit rolls of 1",
        )
        return True

    def _use_genestealer_cults_the_path_of_anguish(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: THE PATH OF ANGUISH: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: THE PATH OF ANGUISH: not opponent's Shooting phase")
            return False
        enemy_root = self._gsc_root(
            context.get("enemy_unit")
            or context.get("attacking_unit")
            or context.get("attacker_unit")
        )
        if enemy_root is None or self._gsc_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: THE PATH OF ANGUISH: missing enemy attacker")
            return False
        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_resolve_unit_list(context.get("candidates"))
        if not candidates:
            candidates = self._gsc_xenocreed_path_of_anguish_candidates(
                enemy_root,
                killing_models_by_target=context.get("killing_models_by_target"),
            )
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: THE PATH OF ANGUISH: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: THE PATH OF ANGUISH: target must be your Acolyte Hybrids or Neophyte Hybrids unit that lost models to that enemy's attacks"
            )
            return False
        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: THE PATH OF ANGUISH: reactive move queue unavailable")
            return False
        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        max_distance = kwargs.get("max_distance")
        if max_distance is None:
            max_distance = self._roll_genestealer_cults_path_of_anguish_distance(target_root)
        try:
            max_distance = int(max_distance or 0)
        except (TypeError, ValueError):
            max_distance = 0
        if max_distance <= 0:
            logger.error("ERROR: THE PATH OF ANGUISH: movement distance roll failed")
            return False
        request = queue_move(
            player=self.player,
            unit=target_root,
            attacker_unit=enemy_root,
            max_distance=int(max_distance),
            kind="xenocreed_path_of_anguish",
            movement_type="blood_surge",
            source=str(getattr(stratagem, "name", "THE PATH OF ANGUISH") or "THE PATH OF ANGUISH"),
            allow_engagement_range=True,
            allow_skip=True,
            extra_context={
                "xenocreed_path_of_anguish_closest_enemy_exclude_keywords_any": ["AIRCRAFT"],
            },
        )
        if request is None:
            logger.error("ERROR: THE PATH OF ANGUISH: failed to queue movement decision")
            return False
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: THE PATH OF ANGUISH: %s can make a Surge move up to %d\" toward the closest non-AIRCRAFT enemy.",
            getattr(target_root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _use_genestealer_cults_the_downtrodden_rise(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: THE DOWNTRODDEN RISE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: THE DOWNTRODDEN RISE: not opponent's Movement phase")
            return False
        target_root = self._gsc_root(context.get("unit") or context.get("target_unit"))
        candidates = self._gsc_resolve_unit_list(context.get("candidates"))
        if not candidates:
            candidates = self._gsc_xenocreed_downtrodden_rise_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: THE DOWNTRODDEN RISE: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: THE DOWNTRODDEN RISE: target must be your Acolyte Hybrids, Hybrid Metamorphs, or Neophyte Hybrids unit in Cult Ambush"
            )
            return False
        build_request = getattr(game, "_build_reserves_arrival_request", None)
        request_decision = getattr(game, "request_decision", None)
        if not callable(build_request) or not callable(request_decision):
            logger.error("ERROR: THE DOWNTRODDEN RISE: reserves arrival request builder unavailable")
            return False
        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        request = build_request(target_root, allow_skip=False)
        if request is None:
            logger.error("ERROR: THE DOWNTRODDEN RISE: failed to create reserves arrival request")
            return False
        request.context = dict(getattr(request, "context", {}) or {})
        request.context.update(
            {
                "ability": "the_downtrodden_rise",
                "ability_name": "The Downtrodden Rise",
                "reserves_arrival_ignore_turn_requirement": True,
                "reserves_arrival_ignore_battlefield_edge_requirement": True,
                "reserves_arrival_min_enemy_distance_override": 6.0,
            }
        )
        request_decision(request)
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: THE DOWNTRODDEN RISE: %s can be set up from Cult Ambush without a marker more than 6\" horizontally from enemy units.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        host_result = self._use_genestealer_cults_host_of_ascension_stratagem(stratagem, **kwargs)
        if host_result is not None:
            return host_result
        biosanctic_result = self._use_genestealer_cults_biosanctic_broodsurge_stratagem(stratagem, **kwargs)
        if biosanctic_result is not None:
            return biosanctic_result
        outlander_result = self._use_genestealer_cults_outlander_claw_stratagem(stratagem, **kwargs)
        if outlander_result is not None:
            return outlander_result
        final_day_result = self._use_genestealer_cults_final_day_stratagem(stratagem, **kwargs)
        if final_day_result is not None:
            return final_day_result
        xenocreed_result = self._use_genestealer_cults_xenocreed_congregation_stratagem(stratagem, **kwargs)
        if xenocreed_result is not None:
            return xenocreed_result
        return self._use_genestealer_cults_brood_brother_auxilia_stratagem(stratagem, **kwargs)

    def _use_genestealer_cults_host_of_ascension_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_host_of_ascension_detachment():
            return None
        name_u = self._gsc_norm_name(getattr(stratagem, "name", ""))
        if name_u == "TUNNEL CRAWLERS":
            return self._use_genestealer_cults_tunnel_crawlers(stratagem, **kwargs)
        if name_u == "LYING IN WAIT":
            return self._use_genestealer_cults_lying_in_wait(stratagem, **kwargs)
        if name_u == "PRIMED AND READIED":
            return self._use_genestealer_cults_primed_and_readied(stratagem, **kwargs)
        if name_u == "COORDINATED TRAP":
            return self._use_genestealer_cults_coordinated_trap(stratagem, **kwargs)
        if name_u == "RETURN TO THE SHADOWS":
            return self._use_genestealer_cults_return_to_the_shadows(stratagem, **kwargs)
        if name_u == "A DEADLY SNARE":
            return self._use_genestealer_cults_a_deadly_snare(stratagem, **kwargs)
        return None

    def _use_genestealer_cults_tunnel_crawlers(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: TUNNEL CRAWLERS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: TUNNEL CRAWLERS: not your turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._gsc_root(target_unit) if target_unit is not None else None
        candidates = self._gsc_host_of_ascension_tunnel_crawlers_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: TUNNEL CRAWLERS: missing target unit")
                return False
        if target_root not in candidates:
            logger.error(
                "ERROR: TUNNEL CRAWLERS: target must be a GENESTEALER CULTS unit arriving with Deep Strike this phase or from Cult Ambush without a marker"
            )
            return False
        context_candidates = [
            self._gsc_root(candidate)
            for candidate in list(context.get("candidates") or [])
            if candidate is not None
        ]
        if context_candidates and target_root not in context_candidates:
            logger.error("ERROR: TUNNEL CRAWLERS: target was not selected")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["tunnel_crawlers_temp_deep_strike"] = True
        sr["tunnel_crawlers_deep_strike_min_distance"] = 6.0
        sr["tunnel_crawlers_expires_phase"] = "MOVEMENT_PHASE"
        sr["tunnel_crawlers_source"] = str(getattr(stratagem, "name", "TUNNEL CRAWLERS") or "TUNNEL CRAWLERS")
        sr["tunnel_crawlers_no_charge_on_arrival"] = True
        if owner:
            sr["tunnel_crawlers_turn_owner"] = owner
        if turn:
            sr["tunnel_crawlers_turn"] = turn
        target_root.special_rules = sr
        try:
            if hasattr(target_root, "_ability_cache") and isinstance(target_root._ability_cache, dict):
                target_root._ability_cache.pop("deep_strike", None)
        except (AttributeError, TypeError, ValueError):
            pass
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: TUNNEL CRAWLERS: %s can Deep Strike within 6\" and cannot charge this turn.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_lying_in_wait(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: LYING IN WAIT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: LYING IN WAIT: not opponent's turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._gsc_root(target_unit) if target_unit is not None else None
        candidates = self._gsc_host_of_ascension_lying_in_wait_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: LYING IN WAIT: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: LYING IN WAIT: target must be a GENESTEALER CULTS BATTLELINE unit in Cult Ambush")
            return False
        context_candidates = [
            self._gsc_root(candidate)
            for candidate in list(context.get("candidates") or [])
            if candidate is not None
        ]
        if context_candidates and target_root not in context_candidates:
            logger.error("ERROR: LYING IN WAIT: target was not selected")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["lying_in_wait_cult_ambush_setup_max_distance"] = 6.0
        sr["lying_in_wait_cult_ambush_enemy_distance_mode"] = "engagement_range"
        sr["lying_in_wait_expires_phase"] = "MOVEMENT_PHASE"
        sr["lying_in_wait_source"] = str(getattr(stratagem, "name", "LYING IN WAIT") or "LYING IN WAIT")
        if owner:
            sr["lying_in_wait_turn_owner"] = owner
        if turn:
            sr["lying_in_wait_turn"] = turn
        target_root.special_rules = sr
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: LYING IN WAIT: %s can be set up wholly within 6\" of its Cult Ambush marker this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_primed_and_readied(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip()
        phase_key = self._gsc_phase_key_from_name(phase_name)
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            logger.error("ERROR: PRIMED AND READIED: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: PRIMED AND READIED: not your phase")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._gsc_root(target_unit) if target_unit is not None else None
        candidates = self._gsc_host_of_ascension_phase_attack_candidates(phase_key=phase_key)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: PRIMED AND READIED: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error("ERROR: PRIMED AND READIED: target must be a GENESTEALER CULTS unit that has not been selected this phase")
            return False
        context_candidates = [
            self._gsc_root(candidate)
            for candidate in list(context.get("candidates") or [])
            if candidate is not None
        ]
        if context_candidates and not self._gsc_unit_in_candidates(target_root, context_candidates):
            logger.error("ERROR: PRIMED AND READIED: target was not selected")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["gsc_primed_and_readied_active"] = True
        sr["gsc_primed_and_readied_crit_threshold"] = 5
        sr["gsc_primed_and_readied_expires_phase"] = phase_key
        sr["gsc_primed_and_readied_source"] = str(getattr(stratagem, "name", "PRIMED AND READIED") or "PRIMED AND READIED")
        if owner:
            sr["gsc_primed_and_readied_turn_owner"] = owner
        if turn:
            sr["gsc_primed_and_readied_turn"] = turn
        target_root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: PRIMED AND READIED: %s scores critical hits on 5+ until end of %s.",
            getattr(target_root, "name", "Unit"),
            self._gsc_phase_label(phase_key),
        )
        return True

    def _use_genestealer_cults_coordinated_trap(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip()
        phase_key = self._gsc_phase_key_from_name(phase_name)
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            logger.error("ERROR: COORDINATED TRAP: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: COORDINATED TRAP: not your phase")
            return False

        selected = (
            context.get("units")
            or context.get("selected_units")
            or context.get("friendly_units")
            or context.get("target_units")
            or context.get("unit")
        )
        friendly_roots = self._gsc_resolve_unit_list(selected)
        friendly_candidates = list(context.get("friendly_candidates") or [])
        if not friendly_candidates:
            friendly_candidates = self._gsc_host_of_ascension_phase_attack_candidates(phase_key=phase_key)
        if not friendly_roots:
            if len(friendly_candidates) == 2:
                friendly_roots = self._gsc_resolve_unit_list(friendly_candidates)
            else:
                logger.error("ERROR: COORDINATED TRAP: missing friendly target units")
                return False
        if len(friendly_roots) != 2:
            logger.error("ERROR: COORDINATED TRAP: must select exactly two friendly GENESTEALER CULTS units")
            return False
        for root in list(friendly_roots):
            if not self._gsc_unit_in_candidates(root, friendly_candidates):
                logger.error("ERROR: COORDINATED TRAP: selected friendly units are not eligible")
                return False

        enemy_unit = (
            context.get("enemy_unit")
            or context.get("target_enemy_unit")
            or context.get("attacking_unit")
            or context.get("attacker_unit")
        )
        if enemy_unit is None:
            possible_enemy = context.get("target_unit")
            possible_root = self._gsc_root(possible_enemy) if possible_enemy is not None else None
            if possible_root is not None and not self._gsc_unit_in_candidates(possible_root, friendly_roots):
                enemy_unit = possible_enemy
        enemy_candidates = list(context.get("enemy_candidates") or [])
        if not enemy_candidates:
            enemy_candidates = self._gsc_coordinated_trap_enemy_candidates_for_units(
                phase_key=phase_key,
                selected_units=friendly_roots,
            )
        enemy_root = self._gsc_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = self._gsc_root(enemy_candidates[0])
            else:
                logger.error("ERROR: COORDINATED TRAP: missing enemy target unit")
                return False
        if self._gsc_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: COORDINATED TRAP: enemy target is invalid")
            return False
        if not self._gsc_on_battlefield(enemy_root, require_targetable=True):
            logger.error("ERROR: COORDINATED TRAP: enemy target must be on the battlefield")
            return False
        if enemy_candidates and not self._gsc_unit_in_candidates(enemy_root, enemy_candidates):
            logger.error("ERROR: COORDINATED TRAP: enemy target is not currently eligible")
            return False

        if phase_key == "FIGHT_PHASE":
            game_map = getattr(game, "map", None)
            if game_map is None:
                return False
            if not all(bool(game_map.is_within_engagement_range(root, enemy_root)) for root in friendly_roots):
                logger.error(
                    "ERROR: COORDINATED TRAP: in Fight phase the enemy target must be within Engagement Range of both selected units"
                )
                return False

        primary = friendly_roots[0]
        if not self._gsc_spend_cp(stratagem, target_unit=primary):
            return False

        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        enemy_id = self._gsc_sort_key(enemy_root)
        source_name = str(getattr(stratagem, "name", "COORDINATED TRAP") or "COORDINATED TRAP")
        for root in friendly_roots:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["gsc_coordinated_trap_active"] = True
            sr["gsc_coordinated_trap_target_id"] = enemy_id
            sr["gsc_coordinated_trap_wound_bonus"] = 1
            sr["gsc_coordinated_trap_target_lock"] = True
            sr["gsc_coordinated_trap_expires_phase"] = phase_key
            sr["gsc_coordinated_trap_source"] = source_name
            if owner:
                sr["gsc_coordinated_trap_turn_owner"] = owner
            if turn:
                sr["gsc_coordinated_trap_turn"] = turn
            root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: COORDINATED TRAP: %s and %s can only target %s and gain +1 to wound until end of %s.",
            getattr(friendly_roots[0], "name", "Unit 1"),
            getattr(friendly_roots[1], "name", "Unit 2"),
            getattr(enemy_root, "name", "Enemy"),
            self._gsc_phase_label(phase_key),
        )
        return True

    def _use_genestealer_cults_return_to_the_shadows(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: RETURN TO THE SHADOWS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: RETURN TO THE SHADOWS: not opponent's turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._gsc_root(target_unit) if target_unit is not None else None
        candidates = self._gsc_host_of_ascension_return_to_the_shadows_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: RETURN TO THE SHADOWS: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error(
                "ERROR: RETURN TO THE SHADOWS: target must be your GENESTEALER CULTS INFANTRY unit not within Engagement Range"
            )
            return False
        context_candidates = [
            self._gsc_root(candidate)
            for candidate in list(context.get("candidates") or [])
            if candidate is not None
        ]
        if context_candidates and not self._gsc_unit_in_candidates(target_root, context_candidates):
            logger.error("ERROR: RETURN TO THE SHADOWS: target was not selected")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False
        if not self._gsc_place_unit_into_strategic_reserves(
            target_root,
            reason=str(getattr(stratagem, "name", "RETURN TO THE SHADOWS") or "RETURN TO THE SHADOWS"),
        ):
            logger.error("ERROR: RETURN TO THE SHADOWS: failed to place target into Strategic Reserves")
            return False

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: RETURN TO THE SHADOWS: %s placed into Strategic Reserves.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_a_deadly_snare(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: A DEADLY SNARE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: A DEADLY SNARE: not opponent's turn")
            return False

        charging_unit = (
            context.get("charging_unit")
            or context.get("enemy_unit")
            or context.get("attacking_unit")
            or context.get("attacker_unit")
        )
        charging_root = self._gsc_root(charging_unit) if charging_unit is not None else None
        if charging_root is None:
            logger.error("ERROR: A DEADLY SNARE: missing charging enemy unit")
            return False
        if self._gsc_owned_by_player(charging_root, self.player):
            logger.error("ERROR: A DEADLY SNARE: charging unit is not an enemy unit")
            return False
        if not self._gsc_on_battlefield(charging_root, require_targetable=False):
            logger.error("ERROR: A DEADLY SNARE: charging enemy unit is not eligible")
            return False

        target_units = context.get("target_units")
        if not isinstance(target_units, list):
            target_units = []
        candidates = self._gsc_host_of_ascension_deadly_snare_candidates(target_units=target_units)
        if not candidates:
            candidates = [
                root
                for root in self._gsc_resolve_unit_list(context.get("candidates"))
                if self._gsc_owned_by_player(root, self.player)
                and self._gsc_is_genestealer_cults_unit(root)
                and self._gsc_is_infantry(root)
                and self._gsc_on_battlefield(root, require_targetable=True)
            ]

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._gsc_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: A DEADLY SNARE: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error("ERROR: A DEADLY SNARE: target unit was not selected as a target of that charge")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False

        roll = max(0, int(dice_module.get_roll("D6") or 0))
        mortal_wounds = 0
        if 2 <= roll <= 4:
            mortal_wounds = max(0, int(dice_module.get_roll("D3") or 0))
        elif roll >= 5:
            mortal_wounds = 3
        if mortal_wounds > 0 and hasattr(target_root, "_apply_mortal_wounds_to_unit"):
            target_root._apply_mortal_wounds_to_unit(charging_root, int(mortal_wounds), game_map=getattr(game, "map", None))

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: A DEADLY SNARE: roll=%d, %s suffers %d mortal wound(s).",
            int(roll),
            getattr(charging_root, "name", "Enemy unit"),
            int(mortal_wounds),
        )
        return True

    def _cleanup_genestealer_cults_host_of_ascension_phase_end_effects(self, *, phase: Any) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"MOVEMENT_PHASE", "SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        seen: set[str] = set()
        for player in list(getattr(game, "players", []) or []):
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                root = self._gsc_root(unit)
                if root is None:
                    continue
                uid = self._gsc_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                changed = False
                if phase_key == "MOVEMENT_PHASE":
                    for key in (
                        "lying_in_wait_cult_ambush_setup_max_distance",
                        "lying_in_wait_cult_ambush_enemy_distance_mode",
                        "lying_in_wait_turn_owner",
                        "lying_in_wait_turn",
                        "lying_in_wait_expires_phase",
                        "lying_in_wait_source",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
                    for key in (
                        "tunnel_crawlers_deep_strike_min_distance",
                        "tunnel_crawlers_turn_owner",
                        "tunnel_crawlers_turn",
                        "tunnel_crawlers_expires_phase",
                        "tunnel_crawlers_source",
                        "tunnel_crawlers_no_charge_on_arrival",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True

                primed_exp = str(sr.get("gsc_primed_and_readied_expires_phase", "") or "").strip().upper()
                if sr.get("gsc_primed_and_readied_active") and (not primed_exp or primed_exp == phase_key):
                    for key in (
                        "gsc_primed_and_readied_active",
                        "gsc_primed_and_readied_crit_threshold",
                        "gsc_primed_and_readied_expires_phase",
                        "gsc_primed_and_readied_source",
                        "gsc_primed_and_readied_turn_owner",
                        "gsc_primed_and_readied_turn",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True

                coordinated_exp = str(sr.get("gsc_coordinated_trap_expires_phase", "") or "").strip().upper()
                if sr.get("gsc_coordinated_trap_active") and (not coordinated_exp or coordinated_exp == phase_key):
                    for key in (
                        "gsc_coordinated_trap_active",
                        "gsc_coordinated_trap_target_id",
                        "gsc_coordinated_trap_wound_bonus",
                        "gsc_coordinated_trap_target_lock",
                        "gsc_coordinated_trap_expires_phase",
                        "gsc_coordinated_trap_source",
                        "gsc_coordinated_trap_turn_owner",
                        "gsc_coordinated_trap_turn",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
                acceptable_exp = str(sr.get("gsc_acceptable_losses_expires_phase", "") or "").strip().upper()
                if sr.get("gsc_acceptable_losses_active") and (not acceptable_exp or acceptable_exp == phase_key):
                    for key in (
                        "gsc_acceptable_losses_active",
                        "gsc_acceptable_losses_target_id",
                        "gsc_acceptable_losses_engaged_unit_ids",
                        "gsc_acceptable_losses_expires_phase",
                        "gsc_acceptable_losses_source",
                        "gsc_acceptable_losses_turn_owner",
                        "gsc_acceptable_losses_turn",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
                symbiotic_exp = str(sr.get("gsc_symbiotic_destruction_expires_phase", "") or "").strip().upper()
                if sr.get("gsc_symbiotic_destruction_active") and (not symbiotic_exp or symbiotic_exp == phase_key):
                    for key in (
                        "gsc_symbiotic_destruction_active",
                        "gsc_symbiotic_destruction_target_id",
                        "gsc_symbiotic_destruction_target_lock",
                        "gsc_symbiotic_destruction_reroll_wound_values",
                        "gsc_symbiotic_destruction_expires_phase",
                        "gsc_symbiotic_destruction_source",
                        "gsc_symbiotic_destruction_turn_owner",
                        "gsc_symbiotic_destruction_turn",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
                if changed:
                    root.special_rules = sr
