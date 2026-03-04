from __future__ import annotations

import logging
from typing import Any, Optional

from ..utility.entity_ids import get_entity_id
from ..utility.modifiers import Modifier, ModifierOp

logger = logging.getLogger(__name__)


class ImperialAgentsStratagemMixin:
    @staticmethod
    def _ia_norm_stratagem_name(name: str) -> str:
        text = str(name or "")
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        text = text.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-")
        text = text.replace("\u2013", "-").replace("\u2014", "-")
        text = text.replace("\u00e2\u20ac\u2122", "'")
        text = text.replace("\u0192?T", "'")
        return text.strip().upper()

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

    @classmethod
    def _ia_is_eversor_assassin_unit(cls, unit: Any) -> bool:
        root = cls._ia_root(unit)
        return cls._ia_unit_name_key(root) == "eversor assassin"

    @classmethod
    def _ia_is_culexus_assassin_unit(cls, unit: Any) -> bool:
        root = cls._ia_root(unit)
        return cls._ia_unit_name_key(root) == "culexus assassin"

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

    def _is_imperialis_fleet(self) -> bool:
        mgr = self._ia_detachment_mgr()
        checker = getattr(mgr, "is_imperialis_fleet", None) if mgr is not None else None
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

    def _ia_is_agents_character_unit(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        if not self._ia_is_agents_unit(root):
            return False
        return self._ia_has_keyword(root, "CHARACTER")

    def _ia_is_voidfarers_character_unit(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        if not self._ia_is_agents_character_unit(root):
            return False
        return self._ia_has_keyword(root, "VOIDFARERS")

    @staticmethod
    def _ia_selected_to_shoot_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "shot_this_round", False))

    @staticmethod
    def _ia_selected_to_fight_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "fought_this_phase", False))

    @staticmethod
    def _ia_unit_models(unit: Any) -> list[Any]:
        if unit is None:
            return []
        get_attached_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_attached_models):
            return list(get_attached_models() or [])
        return list(getattr(unit, "models", []) or [])

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
        wanted = self._ia_norm_stratagem_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            current = self._ia_norm_stratagem_name(reaction.get("stratagem", ""))
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

    def _ia_prime_target_candidates(self, *, phase_name: str) -> list[Any]:
        if not self._is_veiled_blade_elimination_force():
            return []
        phase_key = str(phase_name or "").strip().lower()
        if phase_key not in {"shooting phase", "fight phase"}:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
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
            if not self._ia_is_agents_unit(root):
                continue
            if phase_key == "shooting phase" and self._ia_selected_to_shoot_this_phase(root):
                continue
            if phase_key == "fight phase" and self._ia_selected_to_fight_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_hyperstimms_candidates(self, target_units: list[Any]) -> list[Any]:
        if not self._is_veiled_blade_elimination_force():
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
            if not self._ia_is_agents_character_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_orbital_oversight_candidates(self, target_units: list[Any]) -> list[Any]:
        if not self._is_veiled_blade_elimination_force():
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
            if not self._ia_is_agents_infantry_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_will_sapping_salvo_candidates(self) -> list[Any]:
        if not self._is_veiled_blade_elimination_force():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
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
            if self._ia_selected_to_shoot_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_masters_of_the_void_candidates(self) -> list[Any]:
        if not self._is_imperialis_fleet():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
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
            if not self._ia_is_voidfarers_character_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _queue_imperial_agents_veiled_blade_targets_selected_reaction(
        self,
        *,
        event_name: str,
        phase_name: str,
        stratagem: Any,
        attacking_unit: Any,
        target_units: list[Any],
        candidates: list[Any],
    ) -> None:
        if stratagem is None or attacking_unit is None or not candidates:
            return
        expected_name = self._ia_norm_stratagem_name(getattr(stratagem, "name", ""))
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name or ""):
                continue
            if self._ia_norm_stratagem_name(reaction.get("stratagem", "")) != expected_name:
                continue
            if self._ia_root(reaction.get("attacking_unit")) is attacking_unit:
                return
        payload = {
            "event": str(event_name or ""),
            "phase_name": str(phase_name or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "enemy_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": list(candidates or []),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

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

    def _queue_imperial_agents_veiled_blade_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        self._queue_imperial_agents_veiled_blade_targets_selected_reactions(
            attacking_unit=attacking_unit,
            target_units=target_units,
            event_name="shooting_targets_selected",
            phase_name="Shooting phase",
        )

    def _queue_imperial_agents_veiled_blade_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        self._queue_imperial_agents_veiled_blade_targets_selected_reactions(
            attacking_unit=attacking_unit,
            target_units=target_units,
            event_name="fight_targets_selected",
            phase_name="Fight phase",
        )

    def _queue_imperial_agents_veiled_blade_targets_selected_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        event_name: str,
        phase_name: str,
    ) -> None:
        if not self._is_veiled_blade_elimination_force():
            return
        current_phase = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if current_phase != str(phase_name or "").strip().lower():
            return
        attacking_root = self._ia_root(attacking_unit)
        if attacking_root is None or not self._ia_is_alive(attacking_root):
            return
        if self._ia_owned_by_player(attacking_root, self.player):
            return

        stratagem = self.get_by_name("HYPERSTIMMS")
        if (
            stratagem is not None
            and self.player.command_points >= self._ia_effective_cp_cost(stratagem, enemy_unit=attacking_root)
            and (stratagem.name or "").strip().upper() not in self._used_stratagems_this_phase
        ):
            candidates = self._ia_hyperstimms_candidates(list(target_units or []))
            self._queue_imperial_agents_veiled_blade_targets_selected_reaction(
                event_name=event_name,
                phase_name=phase_name,
                stratagem=stratagem,
                attacking_unit=attacking_root,
                target_units=list(target_units or []),
                candidates=candidates,
            )

        if str(phase_name or "").strip().lower() != "shooting phase":
            return
        orbital = self.get_by_name("ORBITAL OVERSIGHT")
        if (
            orbital is None
            or self.player.command_points < self._ia_effective_cp_cost(orbital, enemy_unit=attacking_root)
            or (orbital.name or "").strip().upper() in self._used_stratagems_this_phase
        ):
            return
        orbital_candidates = self._ia_orbital_oversight_candidates(list(target_units or []))
        self._queue_imperial_agents_veiled_blade_targets_selected_reaction(
            event_name=event_name,
            phase_name=phase_name,
            stratagem=orbital,
            attacking_unit=attacking_root,
            target_units=list(target_units or []),
            candidates=orbital_candidates,
        )

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
        if phase_key not in {"MOVEMENT_PHASE", "CHARGE_PHASE", "SHOOTING_PHASE", "FIGHT_PHASE"}:
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
                if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"} and bool(sr.get("imperial_agents_hyperstimms_active")):
                    exp = str(sr.get("imperial_agents_hyperstimms_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        remove_modifiers = getattr(root, "remove_characteristic_modifiers_by_source", None)
                        if callable(remove_modifiers):
                            remove_modifiers("stratagem:imperial_agents_hyperstimms")
                        for model in list(getattr(root, "models", []) or []):
                            clear_fnp = getattr(model, "set_temporary_fnp", None)
                            if callable(clear_fnp):
                                clear_fnp(key="imperial_agents_hyperstimms", value=0)
                            else:
                                effects = getattr(model, "_temporary_effects", None)
                                if isinstance(effects, dict):
                                    effects.pop("imperial_agents_hyperstimms", None)
                        for key in (
                            "imperial_agents_hyperstimms_active",
                            "imperial_agents_hyperstimms_source",
                            "imperial_agents_hyperstimms_expires_phase",
                            "imperial_agents_hyperstimms_turn",
                            "imperial_agents_hyperstimms_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"} and bool(sr.get("imperial_agents_prime_target_active")):
                    exp = str(sr.get("imperial_agents_prime_target_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_prime_target_active",
                            "imperial_agents_prime_target_source",
                            "imperial_agents_prime_target_expires_phase",
                            "imperial_agents_prime_target_turn",
                            "imperial_agents_prime_target_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key == "SHOOTING_PHASE" and bool(sr.get("imperial_agents_orbital_oversight_active")):
                    exp = str(sr.get("imperial_agents_orbital_oversight_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_orbital_oversight_active",
                            "imperial_agents_orbital_oversight_source",
                            "imperial_agents_orbital_oversight_targeting_range",
                            "imperial_agents_orbital_oversight_lone_operative_targeting_range",
                            "imperial_agents_orbital_oversight_expires_phase",
                            "imperial_agents_orbital_oversight_turn",
                            "imperial_agents_orbital_oversight_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key == "SHOOTING_PHASE" and bool(sr.get("imperial_agents_will_sapping_salvo_active")):
                    exp = str(sr.get("imperial_agents_will_sapping_salvo_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for model in self._ia_unit_models(root):
                            effects = getattr(model, "_temporary_effects", None)
                            if not isinstance(effects, dict):
                                continue
                            remove_keys = [
                                key
                                for key in list(effects.keys())
                                if str(key or "").strip().lower().startswith("imperial_agents_will_sapping_salvo")
                            ]
                            for key in remove_keys:
                                effects.pop(key, None)
                        for key in (
                            "imperial_agents_will_sapping_salvo_active",
                            "imperial_agents_will_sapping_salvo_source",
                            "imperial_agents_will_sapping_salvo_expires_phase",
                            "imperial_agents_will_sapping_salvo_turn",
                            "imperial_agents_will_sapping_salvo_owner",
                            "imperial_agents_will_sapping_salvo_culexus_damage_override",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key == "MOVEMENT_PHASE" and bool(sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_active")):
                    exp = str(sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_masters_of_the_void_enemy_dz_override_active",
                            "imperial_agents_masters_of_the_void_enemy_dz_override_turn_owner",
                            "imperial_agents_masters_of_the_void_enemy_dz_override_turn",
                            "imperial_agents_masters_of_the_void_enemy_dz_override_expires_phase",
                            "imperial_agents_masters_of_the_void_enemy_dz_override_source",
                        ):
                            sr.pop(key, None)
                        changed = True
                if changed:
                    root.special_rules = sr

    def _use_imperial_agents_imperialis_fleet_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_imperialis_fleet():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "MASTERS OF THE VOID":
            return self._use_imperial_agents_masters_of_the_void(stratagem, **kwargs)
        return None

    def _use_imperial_agents_veiled_blade_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_veiled_blade_elimination_force():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        name_n = self._ia_norm_stratagem_name(name_u)
        if name_u == "BLIND GRENADES":
            return self._use_imperial_agents_blind_grenades(stratagem, **kwargs)
        if name_u == "ENSNARING TRAP":
            return self._use_imperial_agents_ensnaring_trap(stratagem, **kwargs)
        if name_u == "HYPERSTIMMS":
            return self._use_imperial_agents_hyperstimms(stratagem, **kwargs)
        if name_u == "PRIME TARGET":
            return self._use_imperial_agents_prime_target(stratagem, **kwargs)
        if name_n == "ORBITAL OVERSIGHT":
            return self._use_imperial_agents_orbital_oversight(stratagem, **kwargs)
        if name_n == "WILL-SAPPING SALVO":
            return self._use_imperial_agents_will_sapping_salvo(stratagem, **kwargs)
        return None

    def _use_imperial_agents_masters_of_the_void(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_imperialis_fleet():
            return False
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: MASTERS OF THE VOID: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: MASTERS OF THE VOID: not your turn")
            return False

        candidates = self._ia_masters_of_the_void_candidates()
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: MASTERS OF THE VOID: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: MASTERS OF THE VOID: target must be an eligible VOIDFARERS CHARACTER unit")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return False
        turn_now = int(getattr(game, "turn", 0) or 0)
        owner_id = str(getattr(self.player, "id", "") or "")
        source = str(getattr(stratagem, "name", "MASTERS OF THE VOID") or "MASTERS OF THE VOID")
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
            if not self._ia_is_agents_unit(root):
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["imperial_agents_masters_of_the_void_enemy_dz_override_active"] = True
            sr["imperial_agents_masters_of_the_void_enemy_dz_override_turn_owner"] = owner_id
            sr["imperial_agents_masters_of_the_void_enemy_dz_override_turn"] = int(turn_now)
            sr["imperial_agents_masters_of_the_void_enemy_dz_override_expires_phase"] = "MOVEMENT_PHASE"
            sr["imperial_agents_masters_of_the_void_enemy_dz_override_source"] = source
            root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

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

    def _use_imperial_agents_hyperstimms(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: HYPERSTIMMS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: HYPERSTIMMS: not opponent's Shooting phase")
            return False
        attacking_unit = context.get("attacking_unit") or context.get("enemy_unit")
        attacking_root = self._ia_root(attacking_unit)
        if attacking_root is None:
            logger.error("ERROR: HYPERSTIMMS: missing attacking unit")
            return False
        if self._ia_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: HYPERSTIMMS: attacking unit is not an enemy unit")
            return False
        target_units = context.get("target_units")
        if not isinstance(target_units, list):
            target_units = []
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is not None and not target_units:
            target_units = [target_root]
        candidates = self._ia_hyperstimms_candidates(target_units)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: HYPERSTIMMS: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: HYPERSTIMMS: target was not selected as an attack target")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False

        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        source = str(getattr(stratagem, "name", "HYPERSTIMMS") or "HYPERSTIMMS")
        add_modifier = getattr(target_root, "add_characteristic_modifier", None)
        if callable(add_modifier):
            add_modifier("toughness", Modifier(ModifierOp.ADD, 1, source="stratagem:imperial_agents_hyperstimms"))
        if self._ia_is_eversor_assassin_unit(target_root):
            for model in list(getattr(target_root, "models", []) or []):
                set_temporary_fnp = getattr(model, "set_temporary_fnp", None)
                if callable(set_temporary_fnp):
                    set_temporary_fnp(
                        key="imperial_agents_hyperstimms",
                        value=4,
                        source=source,
                        expires_phase=phase_key,
                    )
                else:
                    effects = getattr(model, "_temporary_effects", None)
                    if not isinstance(effects, dict):
                        effects = {}
                        model._temporary_effects = effects
                    effects["imperial_agents_hyperstimms"] = {
                        "expires_phase": phase_key,
                        "temporary_fnp_value": 4,
                        "temporary_fnp_source": source,
                    }

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_hyperstimms_active"] = True
        sr["imperial_agents_hyperstimms_source"] = source
        sr["imperial_agents_hyperstimms_expires_phase"] = phase_key
        sr["imperial_agents_hyperstimms_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_hyperstimms_owner"] = str(getattr(self.player, "id", "") or "")
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_orbital_oversight(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: ORBITAL OVERSIGHT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: ORBITAL OVERSIGHT: not opponent's Shooting phase")
            return False

        attacking_unit = context.get("attacking_unit") or context.get("attacker_unit") or context.get("enemy_unit")
        attacking_root = self._ia_root(attacking_unit)
        if attacking_root is None:
            logger.error("ERROR: ORBITAL OVERSIGHT: missing attacking unit")
            return False
        if self._ia_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: ORBITAL OVERSIGHT: attacking unit is not an enemy unit")
            return False

        target_units = context.get("target_units")
        if not isinstance(target_units, list):
            target_units = []
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is not None and not target_units:
            target_units = [target_root]
        candidates = self._ia_orbital_oversight_candidates(target_units)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: ORBITAL OVERSIGHT: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: ORBITAL OVERSIGHT: target must be an eligible AGENTS INFANTRY attack target")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_orbital_oversight_active"] = True
        sr["imperial_agents_orbital_oversight_source"] = str(
            getattr(stratagem, "name", "ORBITAL OVERSIGHT") or "ORBITAL OVERSIGHT"
        )
        sr["imperial_agents_orbital_oversight_targeting_range"] = 18
        sr["imperial_agents_orbital_oversight_lone_operative_targeting_range"] = 6
        sr["imperial_agents_orbital_oversight_expires_phase"] = "SHOOTING_PHASE"
        sr["imperial_agents_orbital_oversight_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_orbital_oversight_turn_owner"] = str(getattr(self.player, "id", "") or "")
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_will_sapping_salvo(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: WILL-SAPPING SALVO: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: WILL-SAPPING SALVO: not your Shooting phase")
            return False

        candidates = self._ia_will_sapping_salvo_candidates()
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: WILL-SAPPING SALVO: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: WILL-SAPPING SALVO: target must be eligible AGENTS INFANTRY not yet selected to shoot")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False

        source = str(getattr(stratagem, "name", "WILL-SAPPING SALVO") or "WILL-SAPPING SALVO")
        phase_key = "SHOOTING_PHASE"
        is_culexus = self._ia_is_culexus_assassin_unit(target_root)
        for model_index, model in enumerate(self._ia_unit_models(target_root)):
            if model is None or not bool(getattr(model, "is_alive", True)):
                continue
            model_id = str(get_entity_id(model) or model_index)
            for wargear_index, wargear in enumerate(list(getattr(model, "wargear", []) or [])):
                if wargear is None:
                    continue
                is_ranged_fn = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged_fn) or not bool(is_ranged_fn()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                key_base = f"imperial_agents_will_sapping_salvo:{model_id}:{wargear_index}:{weapon_name}".lower()
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if callable(set_keywords):
                    set_keywords(
                        key=key_base,
                        weapon_name=weapon_name,
                        keywords=["SUSTAINED HITS 1"],
                        source=source,
                        expires_phase=phase_key,
                        attack_type="ranged",
                    )
                else:
                    effects = getattr(model, "_temporary_effects", None)
                    if not isinstance(effects, dict):
                        effects = {}
                        model._temporary_effects = effects
                    effects[key_base] = {
                        "expires_phase": phase_key,
                        "weapon_keyword_bonuses": {weapon_name: ["SUSTAINED HITS 1"]},
                        "weapon_keyword_bonuses_source": source,
                        "weapon_keyword_bonuses_attack_type": "ranged",
                    }
                if not is_culexus:
                    continue
                damage_key = f"{key_base}:damage"
                set_damage_override = getattr(model, "set_temporary_weapon_damage_override", None)
                if callable(set_damage_override):
                    set_damage_override(
                        key=damage_key,
                        weapon_name=weapon_name,
                        damage_value=3,
                        source=source,
                        expires_phase=phase_key,
                    )
                else:
                    effects = getattr(model, "_temporary_effects", None)
                    if not isinstance(effects, dict):
                        effects = {}
                        model._temporary_effects = effects
                    effects[damage_key] = {
                        "expires_phase": phase_key,
                        "weapon_damage_override": {weapon_name: 3},
                        "weapon_damage_override_source": source,
                    }

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_will_sapping_salvo_active"] = True
        sr["imperial_agents_will_sapping_salvo_source"] = source
        sr["imperial_agents_will_sapping_salvo_expires_phase"] = phase_key
        sr["imperial_agents_will_sapping_salvo_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_will_sapping_salvo_owner"] = str(getattr(self.player, "id", "") or "")
        sr["imperial_agents_will_sapping_salvo_culexus_damage_override"] = bool(is_culexus)
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_prime_target(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: PRIME TARGET: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: PRIME TARGET: can only be used in your Shooting phase")
            return False

        candidates = self._ia_prime_target_candidates(phase_name=phase_name)
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: PRIME TARGET: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: PRIME TARGET: target must be an eligible AGENTS unit that has not acted")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False

        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_prime_target_active"] = True
        sr["imperial_agents_prime_target_source"] = str(getattr(stratagem, "name", "PRIME TARGET") or "PRIME TARGET")
        sr["imperial_agents_prime_target_expires_phase"] = phase_key
        sr["imperial_agents_prime_target_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_prime_target_owner"] = str(getattr(self.player, "id", "") or "")
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True
