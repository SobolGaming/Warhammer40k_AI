from __future__ import annotations

import logging
from typing import Any, Optional

from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class ImperialAgentsStratagemMixin:
    @staticmethod
    def _ia_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _ia_sort_key(unit: Any) -> str:
        return str(get_entity_id(unit) or "")

    @staticmethod
    def _ia_has_keyword(unit: Any, keyword: str) -> bool:
        if unit is None:
            return False
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            if bool(has_keyword(keyword)):
                return True
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        return bool(has_any_keyword(keyword)) if callable(has_any_keyword) else False

    @staticmethod
    def _ia_unit_name_key(unit: Any) -> str:
        return " ".join(str(getattr(unit, "name", "") or "").strip().lower().split())

    @classmethod
    def _ia_is_vindicare_assassin_unit(cls, unit: Any) -> bool:
        root = cls._ia_root(unit)
        return cls._ia_unit_name_key(root) == "vindicare assassin"

    @classmethod
    def _ia_is_callidus_assassin_unit(cls, unit: Any) -> bool:
        root = cls._ia_root(unit)
        return cls._ia_unit_name_key(root) == "callidus assassin"

    @staticmethod
    def _ia_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _ia_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return True
        in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(in_reserves):
            return bool(in_reserves())
        return bool(getattr(unit, "is_in_reserves", False))

    @classmethod
    def _ia_is_on_battlefield(cls, unit: Any) -> bool:
        root = cls._ia_root(unit)
        if root is None:
            return False
        if not cls._ia_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if cls._ia_is_in_reserves(root):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        if getattr(root, "embarked_in", None) is not None:
            return False
        return True

    @staticmethod
    def _ia_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    def _ia_detachment_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "imperial_agents_detachments", None)

    def _is_veiled_blade_elimination_force(self) -> bool:
        mgr = self._ia_detachment_mgr()
        checker = getattr(mgr, "is_veiled_blade_elimination_force", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _ia_is_agents_unit(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        if self._ia_has_keyword(root, "AGENTS OF THE IMPERIUM"):
            return True
        return str(getattr(root, "faction_id", "") or "").strip().upper() == "AOI"

    def _ia_is_agents_infantry_unit(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        if not self._ia_is_agents_unit(root):
            return False
        return self._ia_has_keyword(root, "INFANTRY")

    def _ia_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None, enemy_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            preview = apply_fn(stratagem, target_unit=target_unit, enemy_unit=enemy_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return cp_cost

    def _ia_spend_cp(self, stratagem: Any, *, target_unit: Any = None, enemy_unit: Any = None) -> bool:
        cp_cost = self._ia_effective_cp_cost(stratagem, target_unit=target_unit, enemy_unit=enemy_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _ia_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _ia_pending_context(self, stratagem_name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        context = dict(kwargs or {})
        wanted = str(stratagem_name or "").strip().upper()
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            current = str(reaction.get("stratagem", "") or "").strip().upper()
            if current != wanted:
                continue
            merged = dict(reaction)
            merged.update(context)
            return merged
        return context

    def _ia_blind_grenades_candidates(self, target_units: list[Any]) -> list[Any]:
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._ia_is_agents_unit(root):
                continue
            has_grenades = self._ia_has_keyword(root, "GRENADES")
            if not has_grenades and not self._ia_is_vindicare_assassin_unit(root):
                continue
            engaged = False
            for enemy in list(game_map.get_enemy_units(root) or []):
                enemy_root = self._ia_root(enemy)
                if enemy_root is None or not self._ia_is_alive(enemy_root):
                    continue
                if bool(game_map.is_within_engagement_range(root, enemy_root)):
                    engaged = True
                    break
            if engaged:
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_ensnaring_enemy_candidates_for_unit(self, unit: Any) -> list[Any]:
        root = self._ia_root(unit)
        if root is None:
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for enemy in list(game_map.get_enemy_units(root) or []):
            enemy_root = self._ia_root(enemy)
            if enemy_root is None:
                continue
            eid = self._ia_sort_key(enemy_root)
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            if not self._ia_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if self._ia_is_in_reserves(enemy_root):
                continue
            try:
                distance = float(game_map.get_distance_between_units(root, enemy_root))
            except (TypeError, ValueError):
                continue
            if distance > 6.0:
                continue
            can_charge = getattr(root, "can_declare_charge_against", None)
            if not callable(can_charge):
                continue
            if not bool(can_charge(enemy_root, self.game, out_of_turn=True)):
                continue
            out.append(enemy_root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_ensnaring_trap_candidates(self) -> tuple[list[Any], dict[str, list[Any]]]:
        if not self._is_veiled_blade_elimination_force():
            return [], {}
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return [], {}
        out: list[Any] = []
        enemy_by_unit: dict[str, list[Any]] = {}
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._ia_is_agents_infantry_unit(root):
                continue
            enemies = self._ia_ensnaring_enemy_candidates_for_unit(root)
            if not enemies:
                continue
            out.append(root)
            if uid:
                enemy_by_unit[uid] = enemies
        return sorted(out, key=self._ia_sort_key), enemy_by_unit

    def _queue_imperial_agents_veiled_blade_charge_declared_reactions(
        self,
        *,
        charging_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_veiled_blade_elimination_force():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "charge phase":
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        charging_root = self._ia_root(charging_unit)
        if charging_root is None or not self._ia_is_alive(charging_root):
            return
        stratagem = self.get_by_name("BLIND GRENADES")
        if stratagem is None:
            return
        if self.player.command_points < self._ia_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._ia_blind_grenades_candidates(list(target_units or []))
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                str(reaction.get("event", "") or "") == "charge_declared"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "BLIND GRENADES"
                and self._ia_root(reaction.get("charging_unit")) is charging_root
            ):
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
        self._queue_reaction(payload)

    def _queue_imperial_agents_veiled_blade_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_veiled_blade_elimination_force():
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "CHARGE_PHASE":
            return
        if player is self.player:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "charge phase":
            return
        stratagem = self.get_by_name("ENSNARING TRAP")
        if stratagem is None:
            return
        if self.player.command_points < self._ia_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates, enemy_by_unit = self._ia_ensnaring_trap_candidates()
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                str(reaction.get("event", "") or "") == "phase_end"
                and str(reaction.get("phase_name", "") or "").strip().lower() == "charge phase"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "ENSNARING TRAP"
            ):
                return
        payload = {
            "event": "phase_end",
            "phase": "Charge phase",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
            "enemy_candidates_by_unit": enemy_by_unit,
        }
        if len(candidates) == 1:
            only = candidates[0]
            payload["unit"] = only
            payload["target_unit"] = only
            only_id = self._ia_sort_key(only)
            only_targets = list(enemy_by_unit.get(only_id) or [])
            if len(only_targets) == 1:
                payload["enemy_unit"] = only_targets[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_imperial_agents_veiled_blade_phase_end_effects(self, *, phase: Any) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"CHARGE_PHASE", "FIGHT_PHASE"}:
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        for p in list(getattr(game, "players", []) or []):
            army = getattr(p, "get_army", lambda: None)()
            if army is None:
                continue
            seen: set[str] = set()
            for unit in list(getattr(army, "units", []) or []):
                root = self._ia_root(unit)
                if root is None:
                    continue
                uid = self._ia_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                changed = False
                if phase_key == "CHARGE_PHASE":
                    mods = sr.get("charge_roll_modifiers")
                    if isinstance(mods, list):
                        keep: list[Any] = []
                        for item in mods:
                            if not isinstance(item, dict):
                                keep.append(item)
                                continue
                            if str(item.get("source_key", "") or "") != "imperial_agents_blind_grenades":
                                keep.append(item)
                                continue
                            exp = str(item.get("expires_phase", "") or "").strip().upper()
                            if exp and exp != phase_key:
                                keep.append(item)
                                continue
                            changed = True
                        if keep:
                            sr["charge_roll_modifiers"] = keep
                        elif "charge_roll_modifiers" in sr:
                            sr.pop("charge_roll_modifiers", None)
                if phase_key == "FIGHT_PHASE" and bool(sr.get("ensnaring_trap_callidus_melee_wound_bonus_active")):
                    exp = str(sr.get("ensnaring_trap_callidus_melee_wound_bonus_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "ensnaring_trap_callidus_melee_wound_bonus_active",
                            "ensnaring_trap_callidus_melee_wound_bonus",
                            "ensnaring_trap_callidus_melee_wound_bonus_source",
                            "ensnaring_trap_callidus_melee_wound_bonus_expires_phase",
                            "ensnaring_trap_callidus_melee_wound_bonus_turn",
                            "ensnaring_trap_callidus_melee_wound_bonus_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if changed:
                    root.special_rules = sr

    def _use_imperial_agents_veiled_blade_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_veiled_blade_elimination_force():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "BLIND GRENADES":
            return self._use_imperial_agents_blind_grenades(stratagem, **kwargs)
        if name_u == "ENSNARING TRAP":
            return self._use_imperial_agents_ensnaring_trap(stratagem, **kwargs)
        return None

    def _use_imperial_agents_blind_grenades(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: BLIND GRENADES: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: BLIND GRENADES: not opponent's turn")
            return False
        charging_unit = context.get("charging_unit") or context.get("enemy_unit") or context.get("attacker_unit")
        charging_root = self._ia_root(charging_unit)
        if charging_root is None:
            logger.error("ERROR: BLIND GRENADES: missing charging unit")
            return False
        target_units = context.get("target_units")
        if not isinstance(target_units, list):
            target_units = []
        candidates = self._ia_blind_grenades_candidates(target_units)
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: BLIND GRENADES: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: BLIND GRENADES: target was not selected as a charge target")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=charging_root):
            return False
        sr = getattr(charging_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        mods = sr.get("charge_roll_modifiers")
        if not isinstance(mods, list):
            mods = []
        penalty = -2 if self._ia_is_vindicare_assassin_unit(target_root) else -1
        target_id = self._ia_sort_key(target_root)
        mods.append(
            {
                "value": int(penalty),
                "source": str(getattr(stratagem, "name", "BLIND GRENADES") or "BLIND GRENADES"),
                "source_key": "imperial_agents_blind_grenades",
                "expires_phase": "CHARGE_PHASE",
                "target_unit_ids": [target_id] if target_id else [],
            }
        )
        sr["charge_roll_modifiers"] = mods
        charging_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_ensnaring_trap(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: ENSNARING TRAP: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: ENSNARING TRAP: not opponent's turn")
            return False
        candidates, enemy_by_unit = self._ia_ensnaring_trap_candidates()
        unit = context.get("unit") or context.get("target_unit")
        root = self._ia_root(unit) if unit is not None else None
        if root is None:
            if len(candidates) == 1:
                root = candidates[0]
            else:
                logger.error("ERROR: ENSNARING TRAP: missing target unit")
                return False
        if root not in candidates:
            logger.error("ERROR: ENSNARING TRAP: target unit is not eligible")
            return False
        root_id = self._ia_sort_key(root)
        valid_enemies = list(enemy_by_unit.get(root_id) or self._ia_ensnaring_enemy_candidates_for_unit(root))
        enemy_unit = context.get("enemy_unit")
        enemy_root = self._ia_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            if len(valid_enemies) == 1:
                enemy_root = valid_enemies[0]
            elif valid_enemies:
                enemy_root = valid_enemies[0]
            else:
                logger.error("ERROR: ENSNARING TRAP: no eligible enemy target")
                return False
        if enemy_root not in valid_enemies:
            logger.error("ERROR: ENSNARING TRAP: selected enemy is not an eligible target")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=root, enemy_unit=enemy_root):
            return False
        ok = bool(game.attempt_charge(root, enemy_root, out_of_turn=True, count_as_charged=False))
        if ok and self._ia_is_callidus_assassin_unit(root):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["ensnaring_trap_callidus_melee_wound_bonus_active"] = True
            sr["ensnaring_trap_callidus_melee_wound_bonus"] = 1
            sr["ensnaring_trap_callidus_melee_wound_bonus_source"] = str(
                getattr(stratagem, "name", "ENSNARING TRAP") or "ENSNARING TRAP"
            )
            sr["ensnaring_trap_callidus_melee_wound_bonus_expires_phase"] = "FIGHT_PHASE"
            sr["ensnaring_trap_callidus_melee_wound_bonus_turn"] = int(getattr(game, "turn", 0) or 0)
            sr["ensnaring_trap_callidus_melee_wound_bonus_turn_owner"] = str(
                getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or ""
            )
            root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        if not ok:
            logger.error("ERROR: ENSNARING TRAP: charge failed")
        return True
