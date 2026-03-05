from __future__ import annotations

import logging
from typing import Any, Optional

from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class TyranidsStratagemMixin:
    @staticmethod
    def _tyr_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _tyr_sort_key(entity: Any) -> str:
        return str(get_entity_id(entity) or "")

    @staticmethod
    def _tyr_has_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and has_any(keyword):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        if callable(has_kw) and has_kw(keyword):
            return True
        return False

    @staticmethod
    def _tyr_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    def _tyr_detachment_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "tyranids_detachments", None)

    def _is_tyranids_invasion_fleet_detachment(self) -> bool:
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "is_invasion_fleet", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tyranids_vanguard_onslaught_detachment(self) -> bool:
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "is_vanguard_onslaught", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tyranids_crusher_stampede_detachment(self) -> bool:
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "is_crusher_stampede", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tyranids_unit(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "_unit_is_tyranids", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if faction_id == "TYR":
            return True
        return self._tyr_has_keyword(root, "TYRANIDS")

    def _tyr_owned_by_player(self, unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(army, "player", None) is player

    def _tyr_is_infantry_unit(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        return self._tyr_has_keyword(root, "INFANTRY")

    def _tyr_is_vanguard_invader_unit(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        return self._tyr_has_keyword(root, "VANGUARD INVADER")

    def _tyr_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        if not self._tyr_is_alive(root):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        if getattr(root, "embarked_in", None) is not None:
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            return False
        if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return True

    def _tyr_unit_in_synapse_range(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        synapse_mgr = getattr(army, "synapse", None) if army is not None else None
        if synapse_mgr is None:
            return False
        return bool(synapse_mgr.unit_in_synapse_range(root, game=getattr(self, "game", None)))

    def _tyr_unit_in_engagement_range(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if root is None or game_map is None:
            return False
        for other in list(getattr(game_map, "units", []) or []):
            enemy_root = self._tyr_root(other)
            if enemy_root is None:
                continue
            if enemy_root is root:
                continue
            if not self._tyr_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if self._tyr_owned_by_player(enemy_root, self.player):
                continue
            if bool(game_map.is_within_engagement_range(root, enemy_root)):
                return True
        return False

    def _tyr_unit_in_candidates(self, root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = self._tyr_sort_key(root)
        for candidate in list(candidates or []):
            candidate_root = self._tyr_root(candidate)
            if candidate_root is None:
                continue
            if candidate_root is root:
                return True
            if rid and self._tyr_sort_key(candidate_root) == rid:
                return True
        return False

    @staticmethod
    def _tyr_phase_name(value: Any) -> str:
        return str(value or "").strip().lower().replace("_", " ")

    @staticmethod
    def _tyr_normalize_token(value: Any) -> str:
        text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
        return " ".join(text.split())

    def _tyr_is_own_command_phase(self, *, phase_name: str) -> bool:
        if phase_name != "command phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if getattr(self, "game", None) is not None else None
        return active_player is self.player

    def _tyr_is_endless_multitude_unit(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        return self._tyr_has_keyword(root, "ENDLESS MULTITUDE")

    def _tyr_unit_has_destroyed_models(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        can_return = getattr(root, "_horrors_can_return_model", None)

        def _pool_has_returnable(pool: list[Any]) -> bool:
            for model in list(pool or []):
                if callable(can_return) and not bool(can_return(model)):
                    continue
                return True
            return False

        if _pool_has_returnable(list(getattr(root, "models_lost", []) or [])):
            return True
        members_fn = getattr(root, "get_attached_unit_members", None)
        if callable(members_fn):
            for member in list(members_fn() or []):
                if member is None or member is root:
                    continue
                if _pool_has_returnable(list(getattr(member, "models_lost", []) or [])):
                    return True
        return False

    def _tyr_return_destroyed_models(self, unit: Any, *, amount: int) -> int:
        root = self._tyr_root(unit)
        if root is None:
            return 0
        qty = max(0, int(amount or 0))
        if qty <= 0:
            return 0
        return_full = getattr(self, "_return_destroyed_models_full", None)
        if callable(return_full):
            returned = return_full(
                root,
                amount=qty,
                game_map=getattr(getattr(self, "game", None), "map", None),
                skip_character=True,
            )
            return max(0, int(returned or 0))
        return 0

    def _tyr_hyper_adaptation_by_key(self) -> dict[str, Any]:
        mgr = self._tyr_detachment_mgr()
        get_available = getattr(mgr, "get_available_hyper_adaptations", None) if mgr is not None else None
        if not callable(get_available):
            return {}
        out: dict[str, Any] = {}
        for adaptation in list(get_available() or []):
            key = str(getattr(adaptation, "key", "") or "").strip().upper()
            if key:
                out[key] = adaptation
        return out

    def _tyr_resolve_predatory_imperative_adaptation(self, raw_choice: Any) -> str:
        options = self._tyr_hyper_adaptation_by_key()
        if not options:
            return ""
        mgr = self._tyr_detachment_mgr()
        restricted_key = str(getattr(mgr, "active_hyper_adaptation_key", "") or "").strip().upper() if mgr is not None else ""
        allowed_keys = sorted([key for key in options if key != restricted_key])
        if not allowed_keys:
            return ""

        choice = raw_choice
        if isinstance(choice, dict):
            choice = (
                choice.get("choice")
                or choice.get("mode")
                or choice.get("selection")
                or choice.get("adaptation")
                or choice.get("hyper_adaptation")
                or choice.get("key")
            )
        token = self._tyr_normalize_token(choice)
        if token:
            aliases = {
                "swarming instincts": "SWARMING_INSTINCTS",
                "swarming": "SWARMING_INSTINCTS",
                "hyper aggression": "HYPER_AGGRESSION",
                "hyperaggression": "HYPER_AGGRESSION",
                "hive predators": "HIVE_PREDATORS",
                "predators": "HIVE_PREDATORS",
            }
            alias_key = aliases.get(token, "")
            if alias_key and alias_key in allowed_keys:
                return alias_key
            for key in list(allowed_keys):
                adaptation = options.get(key)
                names = {
                    self._tyr_normalize_token(key),
                    self._tyr_normalize_token(getattr(adaptation, "key", "")),
                    self._tyr_normalize_token(getattr(adaptation, "name", "")),
                }
                if token in names:
                    return key
            return ""
        return allowed_keys[0]

    def _tyr_resolve_units(self, value: Any) -> list[Any]:
        raw = value
        if raw is None:
            return []
        if not isinstance(raw, (list, tuple, set)):
            raw = [raw]
        out: list[Any] = []
        seen: set[str] = set()
        for entry in list(raw or []):
            if isinstance(entry, str):
                resolver = getattr(self, "_resolve_unit_by_id", None)
                if callable(resolver):
                    entry = resolver(entry)
            root = self._tyr_root(entry)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_fight_eligible_candidates(self) -> list[Any]:
        if not self._is_tyranids_invasion_fleet_detachment():
            return []
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            is_eligible = getattr(root, "is_eligible_to_fight", None)
            if not callable(is_eligible) or not bool(is_eligible(game_map)):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_command_phase_candidates(self, *, endless_multitude_only: bool = False) -> list[Any]:
        if not self._is_tyranids_invasion_fleet_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if endless_multitude_only and not self._tyr_is_endless_multitude_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_adrenal_surge_candidates(self) -> list[Any]:
        return self._tyr_fight_eligible_candidates()

    def _tyr_predatory_imperative_candidates(self) -> list[Any]:
        return self._tyr_command_phase_candidates(endless_multitude_only=False)

    def _tyr_endless_swarm_candidates(self) -> list[Any]:
        out: list[Any] = []
        for root in self._tyr_command_phase_candidates(endless_multitude_only=True):
            if not self._tyr_unit_has_destroyed_models(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_death_frenzy_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_tyranids_invasion_fleet_detachment():
            return []
        if attacking_unit is not None:
            attacker_root = self._tyr_root(attacking_unit)
            if attacker_root is None:
                return []
            if self._tyr_owned_by_player(attacker_root, self.player):
                return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_rapid_regeneration_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_tyranids_invasion_fleet_detachment():
            return []
        if attacking_unit is not None:
            attacker_root = self._tyr_root(attacking_unit)
            if attacker_root is None:
                return []
            if self._tyr_owned_by_player(attacker_root, self.player):
                return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_overrun_candidates(self, *, unit: Any = None) -> list[Any]:
        if not self._is_tyranids_invasion_fleet_detachment():
            return []
        if unit is not None:
            root = self._tyr_root(unit)
            if root is None:
                return []
            if not self._tyr_owned_by_player(root, self.player):
                return []
            if not self._tyr_on_battlefield(root, require_targetable=True):
                return []
            if not self._is_tyranids_unit(root):
                return []
            return [root]

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit_entry in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit_entry)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_invisible_hunter_candidates(self) -> list[Any]:
        if not self._is_tyranids_vanguard_onslaught_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            is_vanguard = self._tyr_is_vanguard_invader_unit(root)
            is_tyr_infantry = self._tyr_is_infantry_unit(root)
            if not (is_vanguard or is_tyr_infantry):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_untrammelled_ferocity_candidates(self) -> list[Any]:
        if not self._is_tyranids_crusher_stampede_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            is_monster = bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")
            if not is_monster:
                continue
            if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_spend_cp(self, stratagem: Any, *, target_unit: Any = None, enemy_unit: Any = None) -> bool:
        effective_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_cost = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_cost):
            preview = apply_cost(stratagem, target_unit=target_unit, enemy_unit=enemy_unit) or {}
            effective_cost = int(preview.get("cost", effective_cost))
        return bool(
            self.player.spend_command_points(
                int(effective_cost),
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Unknown')}",
                source="stratagem",
            )
        )

    def _tyr_place_unit_into_strategic_reserves(self, unit: Any, *, reason: str = "") -> bool:
        root = self._tyr_root(unit)
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

    def _tyr_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            raw_name = str(getattr(stratagem, "name", "") or "").strip().upper()
            if raw_name:
                used.add(raw_name)

    def _tyr_clear_melee_fight_on_death_cache(self, unit: Any) -> None:
        root = self._tyr_root(unit)
        if root is None:
            return
        cache = getattr(root, "_ability_cache", None)
        if not isinstance(cache, dict):
            return
        for key in list(cache.keys()):
            if str(key).startswith("melee_fight_on_death_after_attacks:"):
                cache.pop(key, None)

    def _queue_tyranids_invasion_fleet_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None:
            return
        if not self._is_tyranids_invasion_fleet_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None:
            return
        if self._tyr_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("DEATH FRENZY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_death_frenzy_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "fight_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

        # RAPID REGENERATION
        rapid = getattr(self, "get_by_name", lambda _name: None)("RAPID REGENERATION")
        if rapid is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(rapid, "cp_cost", 0) or 0):
            return
        rapid_name = str(getattr(rapid, "name", "") or "").strip().upper()
        if rapid_name in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        rapid_candidates = self._tyr_rapid_regeneration_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not rapid_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "fight_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == rapid_name
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        rapid_payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": rapid.name,
            "cp_cost": rapid.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": rapid_candidates,
        }
        if len(rapid_candidates) == 1:
            rapid_payload["unit"] = rapid_candidates[0]
            rapid_payload["target_unit"] = rapid_candidates[0]
        if callable(queue_reaction):
            queue_reaction(rapid_payload)

    def _queue_tyranids_invasion_fleet_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None:
            return
        if not self._is_tyranids_invasion_fleet_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None:
            return
        if self._tyr_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("RAPID REGENERATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_rapid_regeneration_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "shooting_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tyranids_invasion_fleet_before_consolidate_reactions(
        self,
        *,
        unit: Any,
        target_unit: Any = None,
    ) -> None:
        if unit is None:
            return
        if not self._is_tyranids_invasion_fleet_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        root = self._tyr_root(unit)
        if root is None:
            return
        if not self._tyr_owned_by_player(root, self.player):
            return
        candidates = self._tyr_overrun_candidates(unit=root)
        if not candidates:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("OVERRUN")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "before_consolidate"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("unit") is root
            ):
                return
        payload = {
            "event": "before_consolidate",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "last_target_unit": target_unit,
            "candidates": candidates,
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tyranids_vanguard_onslaught_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_tyranids_vanguard_onslaught_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        if player is self.player:
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("INVISIBLE HUNTER")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if not stratagem.can_use(self.player, self.game, phase_name="Fight phase"):
            return

        candidates = self._tyr_invisible_hunter_candidates()
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "").strip() != "phase_end":
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != "fight phase":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() == name_u:
                return

        vanguard_candidates = [unit for unit in candidates if self._tyr_is_vanguard_invader_unit(unit)]
        infantry_candidates = [unit for unit in candidates if self._tyr_is_infantry_unit(unit)]
        max_units = 2 if len(vanguard_candidates) >= 2 else 1
        payload: dict[str, Any] = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
            "vanguard_candidates": vanguard_candidates,
            "infantry_candidates": infantry_candidates,
            "max_units": int(max_units),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _cleanup_tyranids_invasion_fleet_phase_start_effects(self, *, player: Any = None, phase: Any = None) -> None:
        if not self._is_tyranids_invasion_fleet_detachment():
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "COMMAND_PHASE":
            return
        if player is not self.player:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if sr.get("tyranids_predatory_imperative_active") is not True:
                continue
            for key in (
                "tyranids_predatory_imperative_active",
                "tyranids_predatory_imperative_adaptation_key",
                "tyranids_predatory_imperative_source",
                "tyranids_predatory_imperative_owner",
                "tyranids_predatory_imperative_turn",
            ):
                sr.pop(key, None)
            root.special_rules = sr

    def _cleanup_tyranids_crusher_stampede_phase_end_effects(self, *, phase: Any = None) -> None:
        if not self._is_tyranids_crusher_stampede_detachment():
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            exp = str(sr.get("tyranids_untrammelled_ferocity_expires_phase", "") or "").strip().upper()
            if sr.get("tyranids_untrammelled_ferocity_active") is not True:
                continue
            if exp and exp != "MOVEMENT_PHASE":
                continue

            for key, added_key in (
                ("bearer_unit_phase_move_types", "tyranids_untrammelled_ferocity_added_phase_move_types"),
                (
                    "bearer_unit_phase_move_block_titanic_types",
                    "tyranids_untrammelled_ferocity_added_phase_move_block_titanic_types",
                ),
                (
                    "bearer_unit_phase_move_engagement_types",
                    "tyranids_untrammelled_ferocity_added_phase_move_engagement_types",
                ),
            ):
                added = set(sr.get(added_key) or [])
                if not added:
                    continue
                current = list(sr.get(key) or [])
                kept = [item for item in current if item not in added]
                if kept:
                    sr[key] = kept
                else:
                    sr.pop(key, None)

            if bool(sr.get("tyranids_untrammelled_ferocity_prev_stride_height_present", False)):
                sr["titanic_stride_tall_terrain_height"] = float(
                    sr.get("tyranids_untrammelled_ferocity_prev_stride_height_value", 4.0) or 4.0
                )
            else:
                sr.pop("titanic_stride_tall_terrain_height", None)

            if bool(sr.get("tyranids_untrammelled_ferocity_prev_stride_source_present", False)):
                sr["titanic_stride_source"] = str(
                    sr.get("tyranids_untrammelled_ferocity_prev_stride_source_value", "") or ""
                )
            else:
                sr.pop("titanic_stride_source", None)

            for key in (
                "tyranids_untrammelled_ferocity_active",
                "tyranids_untrammelled_ferocity_expires_phase",
                "tyranids_untrammelled_ferocity_turn_owner",
                "tyranids_untrammelled_ferocity_turn",
                "tyranids_untrammelled_ferocity_source",
                "tyranids_untrammelled_ferocity_added_phase_move_types",
                "tyranids_untrammelled_ferocity_added_phase_move_block_titanic_types",
                "tyranids_untrammelled_ferocity_added_phase_move_engagement_types",
                "tyranids_untrammelled_ferocity_prev_stride_height_present",
                "tyranids_untrammelled_ferocity_prev_stride_height_value",
                "tyranids_untrammelled_ferocity_prev_stride_source_present",
                "tyranids_untrammelled_ferocity_prev_stride_source_value",
            ):
                sr.pop(key, None)
            root.special_rules = sr

    def _use_tyranids_invasion_fleet_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if self._is_tyranids_invasion_fleet_detachment():
            if name_u == "RAPID REGENERATION":
                return self._use_tyranids_rapid_regeneration(stratagem, **kwargs)
            if name_u == "PREDATORY IMPERATIVE":
                return self._use_tyranids_predatory_imperative(stratagem, **kwargs)
            if name_u == "ENDLESS SWARM":
                return self._use_tyranids_endless_swarm(stratagem, **kwargs)
            if name_u == "ADRENAL SURGE":
                return self._use_tyranids_adrenal_surge(stratagem, **kwargs)
            if name_u == "DEATH FRENZY":
                return self._use_tyranids_death_frenzy(stratagem, **kwargs)
            if name_u == "OVERRUN":
                return self._use_tyranids_overrun(stratagem, **kwargs)
        if self._is_tyranids_vanguard_onslaught_detachment():
            if name_u == "INVISIBLE HUNTER":
                return self._use_tyranids_invisible_hunter(stratagem, **kwargs)
        if self._is_tyranids_crusher_stampede_detachment():
            if name_u == "UNTRAMMELLED FEROCITY":
                return self._use_tyranids_untrammelled_ferocity(stratagem, **kwargs)
        return None

    def _use_tyranids_rapid_regeneration(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])

        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: RAPID REGENERATION: no target unit provided")
            return False

        root = self._tyr_root(target_unit)
        if root is None:
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: RAPID REGENERATION: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: RAPID REGENERATION: target must be a TYRANIDS unit")
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: RAPID REGENERATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: RAPID REGENERATION: not opponent's Shooting phase")
            return False

        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None:
            logger.error("ERROR: RAPID REGENERATION: missing attacking unit context")
            return False
        if self._tyr_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: RAPID REGENERATION: attacker is not an enemy unit")
            return False

        eligible = candidates or self._tyr_rapid_regeneration_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: RAPID REGENERATION: target must be one of the attacking unit's selected targets")
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            attacking_unit=attacker_root,
            phase_name=phase_label,
        ):
            logger.error("ERROR: RAPID REGENERATION: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False

        fnp_value = 5 if self._tyr_unit_in_synapse_range(root) else 6
        phase_key_fn = getattr(self, "_phase_key_from_name", None)
        phase_key = phase_key_fn(phase_name) if callable(phase_key_fn) else ""
        if not phase_key:
            phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        entry = {
            "value": int(fnp_value),
            "attack_type": "any",
            "expires_phase": str(phase_key),
            "source": str(getattr(stratagem, "name", "") or "RAPID REGENERATION"),
        }
        append_defensive_effect = getattr(self, "_append_defensive_effect", None)
        if callable(append_defensive_effect):
            append_defensive_effect(root, "defensive_fnp_overrides", entry)
        else:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            items = list(sr.get("defensive_fnp_overrides", []) or [])
            items.append(entry)
            sr["defensive_fnp_overrides"] = items
            root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RAPID REGENERATION: %s gains Feel No Pain %d+ this phase.",
            getattr(root, "name", "Unit"),
            int(fnp_value),
        )
        return True

    def _use_tyranids_predatory_imperative(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("units") or kwargs.get("selected_units")
        if selected is None:
            selected = kwargs.get("target_units")
        if selected is None:
            selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = [candidates[0]]
        selected_roots = self._tyr_resolve_units(selected)
        if not selected_roots:
            logger.error("ERROR: PREDATORY IMPERATIVE: no target unit provided")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: PREDATORY IMPERATIVE: cannot target more than two units")
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "command phase":
            logger.error("ERROR: PREDATORY IMPERATIVE: wrong phase")
            return False
        if not self._tyr_is_own_command_phase(phase_name=phase_name):
            logger.error("ERROR: PREDATORY IMPERATIVE: not your Command phase")
            return False

        eligible = candidates or self._tyr_predatory_imperative_candidates()
        for root in list(selected_roots):
            if not self._tyr_unit_in_candidates(root, eligible):
                logger.error("ERROR: PREDATORY IMPERATIVE: one or more selected units are not currently eligible")
                return False
        if len(selected_roots) == 2 and not all(self._tyr_unit_in_synapse_range(root) for root in list(selected_roots)):
            logger.error("ERROR: PREDATORY IMPERATIVE: selecting two units requires both units to be within Synapse Range")
            return False

        adaptation_choice = (
            kwargs.get("adaptation")
            or kwargs.get("hyper_adaptation")
            or kwargs.get("choice")
            or kwargs.get("mode")
            or kwargs.get("selection")
        )
        selected_key = self._tyr_resolve_predatory_imperative_adaptation(adaptation_choice)
        if not selected_key:
            logger.error("ERROR: PREDATORY IMPERATIVE: no valid Hyper-adaptation choice available")
            return False
        mgr = self._tyr_detachment_mgr()
        restricted_key = str(getattr(mgr, "active_hyper_adaptation_key", "") or "").strip().upper() if mgr is not None else ""
        if selected_key == restricted_key:
            logger.error(
                "ERROR: PREDATORY IMPERATIVE: cannot select the Hyper-adaptation chosen at the start of battle round one"
            )
            return False

        first = selected_roots[0]
        if not stratagem.can_use(self.player, self.game, target_unit=first, unit=first, phase_name="Command phase"):
            logger.error("ERROR: PREDATORY IMPERATIVE: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=first):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        source_name = str(getattr(stratagem, "name", "") or "PREDATORY IMPERATIVE")
        for root in list(selected_roots):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["tyranids_predatory_imperative_active"] = True
            sr["tyranids_predatory_imperative_adaptation_key"] = str(selected_key)
            sr["tyranids_predatory_imperative_source"] = source_name
            if owner_id:
                sr["tyranids_predatory_imperative_owner"] = owner_id
            if turn:
                sr["tyranids_predatory_imperative_turn"] = int(turn)
            root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PREDATORY IMPERATIVE: %d unit(s) gain Hyper-adaptation %s until your next Command phase.",
            len(selected_roots),
            str(selected_key),
        )
        return True

    def _use_tyranids_endless_swarm(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("units") or kwargs.get("selected_units")
        if selected is None:
            selected = kwargs.get("target_units")
        if selected is None:
            selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = [candidates[0]]
        selected_roots = self._tyr_resolve_units(selected)
        if not selected_roots:
            logger.error("ERROR: ENDLESS SWARM: no target unit provided")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: ENDLESS SWARM: cannot target more than two units")
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "command phase":
            logger.error("ERROR: ENDLESS SWARM: wrong phase")
            return False
        if not self._tyr_is_own_command_phase(phase_name=phase_name):
            logger.error("ERROR: ENDLESS SWARM: not your Command phase")
            return False

        eligible = candidates or self._tyr_endless_swarm_candidates()
        for root in list(selected_roots):
            if not self._tyr_unit_in_candidates(root, eligible):
                logger.error(
                    "ERROR: ENDLESS SWARM: one or more selected units are not eligible ENDLESS MULTITUDE units with destroyed models"
                )
                return False
        if len(selected_roots) == 2 and not all(self._tyr_unit_in_synapse_range(root) for root in list(selected_roots)):
            logger.error("ERROR: ENDLESS SWARM: selecting two units requires both units to be within Synapse Range")
            return False

        first = selected_roots[0]
        if not stratagem.can_use(self.player, self.game, target_unit=first, unit=first, phase_name="Command phase"):
            logger.error("ERROR: ENDLESS SWARM: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=first):
            return False

        total_returned = 0
        for root in list(selected_roots):
            roll = max(0, int(dice_module.get_roll("D3") or 0)) + 3
            returned = self._tyr_return_destroyed_models(root, amount=int(roll))
            total_returned += int(returned)

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ENDLESS SWARM: returned %d destroyed model(s) across %d unit(s).",
            int(total_returned),
            len(selected_roots),
        )
        return True

    def _use_tyranids_adrenal_surge(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("units") or kwargs.get("selected_units")
        if selected is None:
            selected = kwargs.get("target_units")
        if selected is None:
            selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = [candidates[0]]
        selected_roots = self._tyr_resolve_units(selected)
        if not selected_roots:
            logger.error("ERROR: ADRENAL SURGE: no target unit provided")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: ADRENAL SURGE: cannot target more than two units")
            return False

        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower().replace("_", " ")
        if phase_name != "fight phase":
            logger.error("ERROR: ADRENAL SURGE: wrong phase")
            return False

        eligible = candidates or self._tyr_adrenal_surge_candidates()
        for root in list(selected_roots):
            if not self._tyr_unit_in_candidates(root, eligible):
                logger.error("ERROR: ADRENAL SURGE: one or more selected units are not currently eligible to fight")
                return False
        if len(selected_roots) == 2 and not all(self._tyr_unit_in_synapse_range(root) for root in list(selected_roots)):
            logger.error("ERROR: ADRENAL SURGE: selecting two units requires both units to be within Synapse Range")
            return False

        first = selected_roots[0]
        if not stratagem.can_use(self.player, self.game, target_unit=first, unit=first, phase_name="Fight phase"):
            logger.error("ERROR: ADRENAL SURGE: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=first):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        source_name = str(getattr(stratagem, "name", "") or "ADRENAL SURGE")
        for root in list(selected_roots):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["tyranids_adrenal_surge_active"] = True
            sr["tyranids_adrenal_surge_crit_threshold"] = 5
            sr["tyranids_adrenal_surge_expires_phase"] = "FIGHT_PHASE"
            sr["tyranids_adrenal_surge_source"] = source_name
            if owner_id:
                sr["tyranids_adrenal_surge_turn_owner"] = owner_id
            if turn:
                sr["tyranids_adrenal_surge_turn"] = int(turn)
            root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ADRENAL SURGE: %d unit(s) gain melee critical hits on 5+ this phase.",
            len(selected_roots),
        )
        return True

    def _use_tyranids_death_frenzy(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])

        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: DEATH FRENZY: no target unit provided")
            return False

        root = self._tyr_root(target_unit)
        if root is None:
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: DEATH FRENZY: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: DEATH FRENZY: target must be a TYRANIDS unit")
            return False

        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower().replace("_", " ")
        if phase_name != "fight phase":
            logger.error("ERROR: DEATH FRENZY: wrong phase")
            return False
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None:
            logger.error("ERROR: DEATH FRENZY: missing attacking unit context")
            return False
        if self._tyr_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: DEATH FRENZY: attacker is not an enemy unit")
            return False

        eligible = candidates or self._tyr_death_frenzy_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: DEATH FRENZY: target must be one of the attacking unit's selected targets")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            attacking_unit=attacker_root,
            phase_name="Fight phase",
        ):
            logger.error("ERROR: DEATH FRENZY: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tyranids_death_frenzy_active"] = True
        sr["tyranids_death_frenzy_threshold"] = 4
        sr["tyranids_death_frenzy_expires_phase"] = "FIGHT_PHASE"
        sr["tyranids_death_frenzy_source"] = str(getattr(stratagem, "name", "") or "DEATH FRENZY")
        if owner_id:
            sr["tyranids_death_frenzy_owner"] = owner_id
        if turn:
            sr["tyranids_death_frenzy_turn"] = int(turn)
        root.special_rules = sr
        self._tyr_clear_melee_fight_on_death_cache(root)

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DEATH FRENZY: %s gains melee fight-on-death on 4+ this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_overrun(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: OVERRUN: no target unit provided")
            return False

        root = self._tyr_root(target_unit)
        if root is None:
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: OVERRUN: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: OVERRUN: target must be a TYRANIDS unit")
            return False

        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower().replace("_", " ")
        if phase_name != "fight phase":
            logger.error("ERROR: OVERRUN: wrong phase")
            return False

        eligible = candidates or self._tyr_overrun_candidates(unit=root)
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: OVERRUN: target is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: OVERRUN: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current_cons = float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0)
        sr["stratagem_consolidate_distance_override"] = max(current_cons, 6.0)
        sr["stratagem_consolidate_requires_engagement"] = True
        sr["stratagem_consolidate_expires_phase"] = "FIGHT_PHASE"
        sr["stratagem_consolidate_source"] = str(getattr(stratagem, "name", "") or "OVERRUN")

        normal_move_active = self._tyr_unit_in_synapse_range(root) and not self._tyr_unit_in_engagement_range(root)
        if normal_move_active:
            sr["tyranids_overrun_normal_move_active"] = True
            sr["tyranids_overrun_normal_move_distance"] = 6
            sr["tyranids_overrun_expires_phase"] = "FIGHT_PHASE"
            sr["tyranids_overrun_source"] = str(getattr(stratagem, "name", "") or "OVERRUN")
            if owner_id:
                sr["tyranids_overrun_turn_owner"] = owner_id
            if turn:
                sr["tyranids_overrun_turn"] = int(turn)
        else:
            for key in (
                "tyranids_overrun_normal_move_active",
                "tyranids_overrun_normal_move_distance",
                "tyranids_overrun_expires_phase",
                "tyranids_overrun_source",
                "tyranids_overrun_turn_owner",
                "tyranids_overrun_turn",
            ):
                sr.pop(key, None)
        root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: OVERRUN: %s gets +3\" consolidate this phase%s.",
            getattr(root, "name", "Unit"),
            " and may make a 6\" Normal move instead" if normal_move_active else "",
        )
        return True

    def _use_tyranids_invisible_hunter(self, stratagem: Any, **kwargs) -> bool:
        selected = (
            kwargs.get("units")
            or kwargs.get("target_units")
            or kwargs.get("selected_units")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        candidates = list(kwargs.get("candidates") or [])
        vanguard_candidates = list(kwargs.get("vanguard_candidates") or [])
        infantry_candidates = list(kwargs.get("infantry_candidates") or [])
        max_units = int(kwargs.get("max_units", 2) or 2)
        if selected is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if selected is None:
                    selected = (
                        reaction.get("units")
                        or reaction.get("target_units")
                        or reaction.get("selected_units")
                        or reaction.get("unit")
                        or reaction.get("target_unit")
                    )
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not vanguard_candidates:
                    vanguard_candidates = list(reaction.get("vanguard_candidates") or [])
                if not infantry_candidates:
                    infantry_candidates = list(reaction.get("infantry_candidates") or [])
                if "max_units" not in kwargs:
                    max_units = int(reaction.get("max_units", max_units) or max_units)
                break

        if selected is None and len(candidates) == 1:
            selected = [candidates[0]]
        selected_roots = self._tyr_resolve_units(selected)
        if not selected_roots:
            logger.error("ERROR: INVISIBLE HUNTER: no target units provided")
            return False
        if len(selected_roots) > max(1, int(max_units)):
            logger.error("ERROR: INVISIBLE HUNTER: selected too many units")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: INVISIBLE HUNTER: cannot select more than two units")
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "fight phase":
            logger.error("ERROR: INVISIBLE HUNTER: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: INVISIBLE HUNTER: not opponent's Fight phase")
            return False

        eligible = candidates or self._tyr_invisible_hunter_candidates()
        if not eligible:
            logger.error("ERROR: INVISIBLE HUNTER: no eligible units")
            return False
        valid_vanguard = self._tyr_resolve_units(vanguard_candidates) or [
            unit for unit in eligible if self._tyr_is_vanguard_invader_unit(unit)
        ]
        valid_infantry = self._tyr_resolve_units(infantry_candidates) or [
            unit for unit in eligible if self._tyr_is_infantry_unit(unit)
        ]
        selected_vanguard = 0
        selected_infantry_only = 0

        for root in list(selected_roots):
            if not self._tyr_unit_in_candidates(root, eligible):
                logger.error("ERROR: INVISIBLE HUNTER: selected unit is not currently eligible")
                return False
            if not self._tyr_owned_by_player(root, self.player):
                logger.error("ERROR: INVISIBLE HUNTER: selected unit is not yours")
                return False
            if not self._tyr_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: INVISIBLE HUNTER: selected unit must be on the battlefield and targetable")
                return False
            if not self._is_tyranids_unit(root):
                logger.error("ERROR: INVISIBLE HUNTER: selected unit must be a TYRANIDS unit")
                return False
            is_vanguard = self._tyr_unit_in_candidates(root, valid_vanguard)
            is_infantry = self._tyr_unit_in_candidates(root, valid_infantry)
            if not (is_vanguard or is_infantry):
                logger.error("ERROR: INVISIBLE HUNTER: selected unit must be VANGUARD INVADER or TYRANIDS INFANTRY")
                return False
            if is_vanguard:
                selected_vanguard += 1
            elif is_infantry:
                selected_infantry_only += 1

        if selected_infantry_only > 1:
            logger.error("ERROR: INVISIBLE HUNTER: cannot select more than one non-VANGUARD TYRANIDS INFANTRY unit")
            return False
        if selected_infantry_only > 0 and len(selected_roots) > 1:
            logger.error("ERROR: INVISIBLE HUNTER: selecting TYRANIDS INFANTRY that is not VANGUARD INVADER limits selection to one unit")
            return False
        if len(selected_roots) == 2 and selected_vanguard != 2:
            logger.error("ERROR: INVISIBLE HUNTER: selecting two units requires both to be VANGUARD INVADER units")
            return False

        can_use = False
        try:
            can_use = bool(
                stratagem.can_use(
                    self.player,
                    self.game,
                    phase_name="Fight phase",
                    unit=selected_roots[0],
                    units=list(selected_roots),
                )
            )
        except TypeError:
            can_use = bool(stratagem.can_use(self.player, self.game, phase_name="Fight phase", unit=selected_roots[0]))
        if not can_use:
            logger.error("ERROR: INVISIBLE HUNTER: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=selected_roots[0]):
            return False

        for root in list(selected_roots):
            if not self._tyr_place_unit_into_strategic_reserves(
                root,
                reason=str(getattr(stratagem, "name", "") or "INVISIBLE HUNTER"),
            ):
                logger.error(
                    "ERROR: INVISIBLE HUNTER: failed to place %s into Strategic Reserves",
                    getattr(root, "name", "Unit"),
                )
                return False

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        moved_units = ", ".join(str(getattr(root, "name", "Unit") or "Unit") for root in list(selected_roots))
        logger.info("INFO: INVISIBLE HUNTER: %s entered Strategic Reserves.", moved_units)
        return True

    def _use_tyranids_untrammelled_ferocity(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = candidates[0]
        if selected is None:
            logger.error("ERROR: UNTRAMMELLED FEROCITY: no target unit provided")
            return False

        root = self._tyr_root(selected)
        if root is None:
            return False
        if not self._is_tyranids_crusher_stampede_detachment():
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "movement phase":
            logger.error("ERROR: UNTRAMMELLED FEROCITY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: UNTRAMMELLED FEROCITY: not your turn")
            return False

        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: UNTRAMMELLED FEROCITY: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: UNTRAMMELLED FEROCITY: target must be on the battlefield and targetable")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: UNTRAMMELLED FEROCITY: target must be a TYRANIDS unit")
            return False
        is_monster = bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")
        if not is_monster:
            logger.error("ERROR: UNTRAMMELLED FEROCITY: target must be a MONSTER unit")
            return False
        if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
            logger.error("ERROR: UNTRAMMELLED FEROCITY: target already moved this phase")
            return False

        eligible = candidates or self._tyr_untrammelled_ferocity_candidates()
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: UNTRAMMELLED FEROCITY: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: UNTRAMMELLED FEROCITY: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}

        move_types = {"move", "advance", "fall_back"}

        def _merge_move_types(rule_key: str, added_key: str) -> None:
            current = set(sr.get(rule_key) or [])
            added = sorted([move_type for move_type in move_types if move_type not in current])
            merged = sorted(current.union(move_types))
            if merged:
                sr[rule_key] = merged
            if added:
                sr[added_key] = added
            else:
                sr.pop(added_key, None)

        _merge_move_types("bearer_unit_phase_move_types", "tyranids_untrammelled_ferocity_added_phase_move_types")
        _merge_move_types(
            "bearer_unit_phase_move_block_titanic_types",
            "tyranids_untrammelled_ferocity_added_phase_move_block_titanic_types",
        )
        _merge_move_types(
            "bearer_unit_phase_move_engagement_types",
            "tyranids_untrammelled_ferocity_added_phase_move_engagement_types",
        )

        stride_height_present = "titanic_stride_tall_terrain_height" in sr
        stride_source_present = "titanic_stride_source" in sr
        sr["tyranids_untrammelled_ferocity_prev_stride_height_present"] = bool(stride_height_present)
        sr["tyranids_untrammelled_ferocity_prev_stride_source_present"] = bool(stride_source_present)
        if stride_height_present:
            sr["tyranids_untrammelled_ferocity_prev_stride_height_value"] = float(
                sr.get("titanic_stride_tall_terrain_height", 4.0) or 4.0
            )
        if stride_source_present:
            sr["tyranids_untrammelled_ferocity_prev_stride_source_value"] = str(sr.get("titanic_stride_source", "") or "")

        sr["titanic_stride_tall_terrain_height"] = 4.0
        sr["titanic_stride_source"] = str(getattr(stratagem, "name", "") or "UNTRAMMELLED FEROCITY")
        sr["tyranids_untrammelled_ferocity_active"] = True
        sr["tyranids_untrammelled_ferocity_expires_phase"] = "MOVEMENT_PHASE"
        sr["tyranids_untrammelled_ferocity_source"] = str(getattr(stratagem, "name", "") or "UNTRAMMELLED FEROCITY")

        owner_id = str(getattr(self.player, "id", "") or "")
        if owner_id:
            sr["tyranids_untrammelled_ferocity_turn_owner"] = owner_id
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        if turn:
            sr["tyranids_untrammelled_ferocity_turn"] = turn

        root.special_rules = sr
        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNTRAMMELLED FEROCITY: %s can move through models (excluding TITANIC) and terrain this phase.",
            getattr(root, "name", "Unit"),
        )
        return True
