from __future__ import annotations

import logging
from typing import Any

from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class AdeptusCustodesStratagemMixin:
    @staticmethod
    def _ac_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _ac_phase_key(value: Any) -> str:
        return str(value or "").strip().upper().replace(" ", "_")

    @staticmethod
    def _ac_has_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        token = str(keyword or "").strip()
        if not token:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and bool(has_any(token)):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        return bool(callable(has_kw) and has_kw(token))

    def _ac_detachment_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "adeptus_custodes_detachments", None)

    def _is_auric_champions_detachment(self) -> bool:
        mgr = self._ac_detachment_mgr()
        checker = getattr(mgr, "is_auric_champions", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _ac_owned_by_player(self, unit: Any, player: Any | None = None) -> bool:
        root = self._ac_root(unit)
        owner = self.player if player is None else player
        if root is None or owner is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        return getattr(army, "player", None) is owner

    def _ac_is_custodes_unit(self, unit: Any) -> bool:
        root = self._ac_root(unit)
        if root is None or not self._ac_owned_by_player(root):
            return False
        return self._ac_has_keyword(root, "ADEPTUS CUSTODES")

    def _ac_is_character_unit(self, unit: Any) -> bool:
        root = self._ac_root(unit)
        return root is not None and self._ac_is_custodes_unit(root) and self._ac_has_keyword(root, "CHARACTER")

    def _ac_unit_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._ac_root(unit)
        if root is None:
            return False
        if require_targetable:
            is_active = getattr(root, "is_active_for_rules", None)
            if callable(is_active) and not bool(is_active()):
                return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if str(getattr(root, "reserve_status", "deployed") or "").strip().lower() != "deployed":
            return False
        if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
            return False
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        return True

    def _ac_is_enemy_battlefield_unit(self, unit: Any) -> bool:
        root = self._ac_root(unit)
        if root is None or not self._ac_unit_on_battlefield(root):
            return False
        return not self._ac_owned_by_player(root)

    def _ac_current_phase_name(self, explicit: Any = "") -> str:
        phase_name = str(explicit or "").strip()
        if phase_name:
            return phase_name
        current = str(getattr(self, "_current_phase_name", "") or "").strip()
        if current:
            return current
        phase = getattr(getattr(self, "game", None), "phase", None)
        return str(getattr(phase, "name", phase) or "").strip()

    def _ac_current_turn(self) -> int:
        return int(getattr(getattr(self, "game", None), "turn", 0) or 0)

    def _ac_turn_owner_id(self) -> str:
        game = getattr(self, "game", None)
        current = game.get_current_player() if game is not None and hasattr(game, "get_current_player") else None
        return str(getattr(current, "id", "") or "").strip()

    def _ac_effective_cp_cost(self, stratagem, *, target_unit: Any) -> int:
        cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            preview = apply_fn(stratagem, target_unit=target_unit) or {}
            cost = int(preview.get("cost", cost))
        return int(cost)

    def _ac_spend_cp(self, stratagem, *, target_unit: Any) -> bool:
        cost = self._ac_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _ac_finalize_use(self, stratagem, *, dequeue: bool) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(self._normalize_stratagem_name(stratagem.name or "")).strip())

    def _ac_model_has_keyword(self, model: Any, keyword: str) -> bool:
        return self._ac_has_keyword(model, keyword)

    def _ac_alive_models(self, unit: Any) -> list[Any]:
        root = self._ac_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        alive: list[Any] = []
        for model in models:
            if model is None:
                continue
            is_alive = getattr(model, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif getattr(model, "is_alive", True) is False:
                continue
            alive.append(model)
        return alive

    def _ac_unique_units(self, units: list[Any]) -> list[Any]:
        resolved: list[Any] = []
        seen: set[str] = set()
        for unit in list(units or []):
            root = self._ac_root(unit)
            unit_id = str(get_entity_id(root) or "").strip()
            if root is None or not unit_id or unit_id in seen:
                continue
            seen.add(unit_id)
            resolved.append(root)
        resolved.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return resolved

    def _ac_enemy_battlefield_units(self) -> list[Any]:
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return []
        return self._ac_unique_units(
            [unit for unit in list(getattr(game_map, "units", []) or []) if self._ac_is_enemy_battlefield_unit(unit)]
        )

    def _ac_warlord_unit(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        warlord = getattr(army, "warlord", None) if army is not None else None
        return self._ac_root(warlord)

    def _ac_warlord_model_pair_key(self, model: Any, ability_key: str) -> str:
        model_id = str(get_entity_id(model) or "").strip()
        ability = str(ability_key or "").strip().lower()
        return f"{model_id}:{ability}"

    def _ac_superhuman_reserves_pairs(self) -> set[str]:
        pairs = getattr(self, "_auric_superhuman_reserves_granted_pairs", None)
        if not isinstance(pairs, set):
            pairs = set()
            self._auric_superhuman_reserves_granted_pairs = pairs
        return pairs

    def _ac_pending_reaction(self, stratagem_name: str) -> dict[str, Any] | None:
        wanted = str(stratagem_name or "").strip().upper()
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() == wanted:
                return reaction
        return None

    def _ac_units_within_shoulder_range(self, leader_unit: Any, bodyguard_unit: Any) -> bool:
        source_models = self._ac_alive_models(leader_unit)
        target_models = self._ac_alive_models(bodyguard_unit)
        for source_model in source_models:
            source_base = getattr(source_model, "model_base", None)
            if source_base is None:
                continue
            for target_model in target_models:
                target_base = getattr(target_model, "model_base", None)
                if target_base is None:
                    continue
                horizontal = float(horizontal_distance_between_bases_2d(source_base, target_base))
                vertical = float(vertical_distance_between_bases(source_base, target_base))
                if horizontal <= 2.0 + 1e-6 and vertical <= 5.0 + 1e-6:
                    return True
        return False

    def _queue_auric_superhuman_reserves_reaction(
        self,
        *,
        player=None,
        model=None,
        ability_key: str = "",
        ability_name: str = "",
        phase_name: str = "",
        source: str = "",
    ) -> None:
        if player is not self.player or not self._is_auric_champions_detachment() or model is None:
            return
        if str(source or "").strip().lower() not in {"datasheet", "enhancement"}:
            return
        model_unit = getattr(model, "parent_unit", None)
        root = self._ac_root(model_unit)
        if root is None or root is not self._ac_warlord_unit() or not self._ac_unit_on_battlefield(root):
            return
        pair_key = self._ac_warlord_model_pair_key(model, ability_key)
        if not pair_key or pair_key in self._ac_superhuman_reserves_pairs():
            return
        stratagem = self.get_by_name("SUPERHUMAN RESERVES")
        if stratagem is None:
            return
        phase_label = self._ac_current_phase_name(phase_name)
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name=phase_label):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "SUPERHUMAN RESERVES":
                continue
            if str(reaction.get("pair_key", "") or "").strip() == pair_key:
                return
        self._queue_reaction(
            {
                "event": "once_per_battle_ability_used",
                "phase_name": phase_label,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "model": model,
                "unit": root,
                "target_unit": root,
                "ability_key": str(ability_key or "").strip().lower(),
                "ability_name": str(ability_name or "").strip(),
                "pair_key": pair_key,
            }
        )

    def _queue_auric_the_emperors_auspice_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
    ) -> None:
        if not self._is_auric_champions_detachment() or attacking_unit is None:
            return
        if self._ac_owned_by_player(attacking_unit):
            return
        stratagem = self.get_by_name("THE EMPEROR'S AUSPICE")
        if stratagem is None:
            return
        candidates = self._ac_unique_units(
            [
                unit
                for unit in list(target_units or [])
                if self._ac_is_character_unit(unit)
                and self._ac_unit_on_battlefield(unit)
                and not self._unit_cannot_be_target_of_stratagem(self._ac_root(unit))
            ]
        )
        if not candidates:
            return
        if not stratagem.can_use(self.player, self.game, unit=candidates[0], target_unit=candidates[0], phase_name=phase_name):
            return
        attacker_id = str(get_entity_id(self._ac_root(attacking_unit)) or "").strip()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "THE EMPEROR'S AUSPICE":
                continue
            if str(reaction.get("attacking_unit_id", "") or "").strip() == attacker_id:
                return
        payload = {
            "event": "shooting_targets_selected" if "shooting" in phase_name.lower() else "fight_targets_selected",
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": self._ac_root(attacking_unit),
            "attacking_unit_id": attacker_id,
            "candidates": candidates,
            "target_units": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_auric_vigil_unending_reaction(self, *, unit: Any, model: Any) -> None:
        if not self._is_auric_champions_detachment():
            return
        phase_name = self._ac_current_phase_name()
        if self._ac_phase_key(phase_name) != "FIGHT_PHASE":
            return
        root = self._ac_root(unit)
        if root is None or model is None:
            return
        if not self._ac_is_character_unit(root) or not self._ac_owned_by_player(root):
            return
        if not self._ac_model_has_keyword(model, "CHARACTER"):
            return
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            return
        if self._unit_cannot_be_target_of_stratagem(root):
            return
        stratagem = self.get_by_name("VIGIL UNENDING")
        if stratagem is None or not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name=phase_name):
            return
        model_id = str(get_entity_id(model) or "").strip()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "VIGIL UNENDING":
                continue
            if str(reaction.get("destroyed_model_id", "") or "").strip() == model_id:
                return
        self._queue_reaction(
            {
                "event": "model_destroyed_before_removal",
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "model": model,
                "destroyed_model_id": model_id,
            },
            use_timer=False,
        )

    def _queue_auric_slayer_of_champions_reaction(self, *, destroyed_unit: Any, destroyed_by_unit: Any) -> None:
        if not self._is_auric_champions_detachment():
            return
        mgr = self._ac_detachment_mgr()
        if mgr is None or not bool(getattr(mgr, "is_assemblage_of_might_target", lambda _unit: False)(destroyed_unit)):
            return
        attacker = self._ac_root(destroyed_by_unit)
        if attacker is None or not self._ac_is_character_unit(attacker) or not self._ac_owned_by_player(attacker):
            return
        candidates = self._ac_enemy_battlefield_units()
        if not candidates:
            return
        stratagem = self.get_by_name("SLAYER OF CHAMPIONS")
        phase_name = self._ac_current_phase_name()
        if stratagem is None or not stratagem.can_use(self.player, self.game, unit=attacker, target_unit=attacker, phase_name=phase_name):
            return
        destroyed_id = str(get_entity_id(self._ac_root(destroyed_unit)) or "").strip()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "SLAYER OF CHAMPIONS":
                continue
            if str(reaction.get("destroyed_unit_id", "") or "").strip() == destroyed_id:
                return
        self._queue_reaction(
            {
                "event": "unit_destroyed",
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": attacker,
                "target_unit": attacker,
                "destroyed_unit": self._ac_root(destroyed_unit),
                "destroyed_unit_id": destroyed_id,
                "destroyed_unit_was_character": self._ac_has_keyword(self._ac_root(destroyed_unit), "CHARACTER"),
                "candidates": candidates,
            }
        )

    def _use_adeptus_custodes_stratagem(self, stratagem, **kwargs):
        name_u = str(self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")).strip()
        handled = {
            "EARNING OF A NAME",
            "SHOULDER THE MANTLE",
            "SLAYER OF CHAMPIONS",
            "SUPERHUMAN RESERVES",
            "THE EMPEROR'S AUSPICE",
            "VIGIL UNENDING",
        }
        if name_u not in handled:
            return None
        if not self._is_auric_champions_detachment():
            return False

        phase_name = self._ac_current_phase_name(kwargs.get("phase_name"))
        pending = self._ac_pending_reaction(name_u)
        dequeue = bool(kwargs.get("dequeue"))

        if name_u == "EARNING OF A NAME":
            roots = self._ac_unique_units(
                list(kwargs.get("target_units") or []) + [kwargs.get("unit") or kwargs.get("target_unit")]
            )
            if not roots or len(roots) > 2:
                logger.error("ERROR: EARNING OF A NAME: expected one or two target units")
                return False
            for root in roots:
                if not self._ac_is_character_unit(root) or not self._ac_unit_on_battlefield(root):
                    logger.error("ERROR: EARNING OF A NAME: target must be an ADEPTUS CUSTODES CHARACTER unit on the battlefield")
                    return False
                if self._unit_cannot_be_target_of_stratagem(root):
                    logger.error("ERROR: EARNING OF A NAME: invalid target unit")
                    return False
                if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                    logger.error("ERROR: EARNING OF A NAME: target unit has already fought this phase")
                    return False
            primary = roots[0]
            if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=primary):
                return False
            for root in roots:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["auric_earning_of_a_name_active"] = True
                sr["auric_earning_of_a_name_source"] = stratagem.name
                sr["auric_earning_of_a_name_turn"] = self._ac_current_turn()
                sr["auric_earning_of_a_name_owner"] = self._ac_turn_owner_id()
                sr["auric_earning_of_a_name_expires_phase"] = "FIGHT_PHASE"
                root.special_rules = sr
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "SHOULDER THE MANTLE":
            leader = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit"))
            bodyguard = self._ac_root(kwargs.get("bodyguard_unit") or kwargs.get("bodyguard"))
            if leader is None or bodyguard is None:
                logger.error("ERROR: SHOULDER THE MANTLE: missing leader or bodyguard unit")
                return False
            if not self._ac_is_character_unit(leader) or not self._ac_unit_on_battlefield(leader):
                logger.error("ERROR: SHOULDER THE MANTLE: leader must be an ADEPTUS CUSTODES CHARACTER unit on the battlefield")
                return False
            if not bool(getattr(leader, "is_leader", False)) or getattr(leader, "attached_to", None) is not None:
                logger.error("ERROR: SHOULDER THE MANTLE: target leader is already leading a unit")
                return False
            if not self._ac_unit_on_battlefield(bodyguard) or not self._ac_owned_by_player(bodyguard):
                logger.error("ERROR: SHOULDER THE MANTLE: bodyguard must be a friendly on-battlefield unit")
                return False
            if list(getattr(bodyguard, "attached_leaders", []) or []):
                logger.error("ERROR: SHOULDER THE MANTLE: bodyguard cannot already be an Attached unit")
                return False
            if bool(getattr(bodyguard, "is_battle_shocked", lambda: False)()):
                logger.error("ERROR: SHOULDER THE MANTLE: bodyguard cannot be Battle-shocked")
                return False
            if not leader.can_attach_to(bodyguard):
                logger.error("ERROR: SHOULDER THE MANTLE: selected leader cannot attach to that bodyguard")
                return False
            if not self._ac_units_within_shoulder_range(leader, bodyguard):
                logger.error("ERROR: SHOULDER THE MANTLE: bodyguard is not within 2\" horizontally and 5\" vertically")
                return False
            if not stratagem.can_use(self.player, self.game, unit=leader, target_unit=leader, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=leader):
                return False
            leader.attach_to_unit(bodyguard)
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "SLAYER OF CHAMPIONS":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("unit"))
            enemy_unit = self._ac_root(kwargs.get("enemy_unit") or kwargs.get("selected_enemy_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or (pending or {}).get("candidates") or []))
            if source_unit is None or not self._ac_is_character_unit(source_unit):
                logger.error("ERROR: SLAYER OF CHAMPIONS: missing ADEPTUS CUSTODES CHARACTER source unit")
                return False
            if enemy_unit is None and len(candidates) == 1:
                enemy_unit = candidates[0]
            if enemy_unit is None or not self._ac_is_enemy_battlefield_unit(enemy_unit):
                logger.error("ERROR: SLAYER OF CHAMPIONS: missing enemy target unit")
                return False
            if candidates and enemy_unit not in candidates:
                logger.error("ERROR: SLAYER OF CHAMPIONS: selected enemy is not an eligible candidate")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            mgr = self._ac_detachment_mgr()
            if mgr is None or not bool(getattr(mgr, "set_slayer_of_champions_target", lambda _unit: False)(enemy_unit)):
                return False
            if bool(kwargs.get("destroyed_unit_was_character", (pending or {}).get("destroyed_unit_was_character", False))):
                gain_cp = getattr(self.player, "gain_command_points", None)
                if callable(gain_cp):
                    gain_cp(1, reason=stratagem.name, source="stratagem")
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "SUPERHUMAN RESERVES":
            model = kwargs.get("model") or (pending or {}).get("model")
            model_unit = getattr(model, "parent_unit", None) if model is not None else None
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or model_unit or (pending or {}).get("unit"))
            ability_key = str(kwargs.get("ability_key") or (pending or {}).get("ability_key") or "").strip().lower()
            ability_name = str(kwargs.get("ability_name") or (pending or {}).get("ability_name") or "").strip()
            if model is None or source_unit is None or source_unit is not self._ac_warlord_unit():
                logger.error("ERROR: SUPERHUMAN RESERVES: target must be your WARLORD model")
                return False
            pair_key = self._ac_warlord_model_pair_key(model, ability_key)
            if not pair_key or pair_key in self._ac_superhuman_reserves_pairs():
                logger.error("ERROR: SUPERHUMAN RESERVES: that once-per-battle ability has already been extended")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            if not bool(model.grant_once_per_battle_extra_use(ability_key, uses=1)):
                return False
            self._ac_superhuman_reserves_pairs().add(pair_key)
            logger.info(
                "INFO: SUPERHUMAN RESERVES: %s gains one extra use of %s.",
                getattr(model, "name", "Model"),
                ability_name or ability_key or "ability",
            )
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "THE EMPEROR'S AUSPICE":
            target_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("unit") or (pending or {}).get("target_unit"))
            if target_unit is None or not self._ac_is_character_unit(target_unit):
                logger.error("ERROR: THE EMPEROR'S AUSPICE: target must be an ADEPTUS CUSTODES CHARACTER unit")
                return False
            if not stratagem.can_use(self.player, self.game, unit=target_unit, target_unit=target_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=target_unit):
                return False
            phase_key = self._ac_phase_key(phase_name)
            for model in self._ac_alive_models(target_unit):
                if not self._ac_model_has_keyword(model, "CHARACTER"):
                    continue
                model.set_temporary_fnp(
                    key=f"auric_the_emperors_auspice_{get_entity_id(model)}",
                    value=4,
                    source=stratagem.name,
                    expires_phase=phase_key,
                )
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "VIGIL UNENDING":
            target_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("unit"))
            model = kwargs.get("model") or (pending or {}).get("model")
            model_id = str(get_entity_id(model) or "").strip() if model is not None else ""
            if target_unit is None or model is None or not model_id:
                logger.error("ERROR: VIGIL UNENDING: missing destroyed character model context")
                return False
            if not self._ac_is_character_unit(target_unit) or not self._ac_model_has_keyword(model, "CHARACTER"):
                logger.error("ERROR: VIGIL UNENDING: target must be a destroyed ADEPTUS CUSTODES CHARACTER model")
                return False
            if bool(getattr(getattr(target_unit, "round_state", None), "fought_this_phase", False)):
                logger.error("ERROR: VIGIL UNENDING: target unit has already fought this phase")
                return False
            if not stratagem.can_use(self.player, self.game, unit=target_unit, target_unit=target_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=target_unit):
                return False
            sr = getattr(target_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            model_ids = {str(v).strip() for v in list(sr.get("auric_vigil_unending_model_ids", []) or []) if str(v).strip()}
            model_ids.add(model_id)
            sr["auric_vigil_unending_active"] = True
            sr["auric_vigil_unending_model_ids"] = sorted(model_ids)
            sr["auric_vigil_unending_turn"] = self._ac_current_turn()
            sr["auric_vigil_unending_owner"] = self._ac_turn_owner_id()
            sr["auric_vigil_unending_expires_phase"] = "FIGHT_PHASE"
            sr["auric_vigil_unending_source"] = stratagem.name
            target_unit.special_rules = sr
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        return None
