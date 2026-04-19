from __future__ import annotations

from ._shared import *  # noqa: F401,F403


class GameShootingFightHandlersMixin:
    def _on_shooting_targets_selected_stabilised_disembarkation(
        self,
        attacking_unit=None,
        target_units=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        if attacker_root is None:
            return
        attacker_id = str(get_entity_id(attacker_root) or "")
        if not attacker_id:
            return
        attacker_army = attacker_root.get_parent_army() if attacker_root is not None else None
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            if target_root is None:
                continue
            try:
                if target_root.get_parent_army() is attacker_army:
                    continue
            except Exception:
                continue
            if not bool(getattr(target_root, "is_transport", False)):
                continue
            try:
                if not bool(target_root.is_alive()) or not bool(getattr(target_root, "deployed", True)):
                    continue
            except Exception:
                continue
            try:
                if target_root.is_in_reserves() or bool(getattr(target_root, "is_embarked", False)):
                    continue
            except Exception:
                pass
            try:
                specs = list(target_root.unit_stabilised_disembarkation_specs() or [])
            except Exception:
                specs = []
            if not specs:
                continue
            if not list(getattr(target_root, "transport_passengers", []) or []):
                continue
            spec = next(
                (
                    s for s in list(specs or [])
                    if isinstance(s, dict) and int(s.get("disembark_max_distance", 0) or 0) > 0
                ),
                None,
            )
            if spec is None:
                continue
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            pending = sr.get("stabilised_disembarkation_pending_by_attacker")
            if not isinstance(pending, dict):
                pending = {}
            pending[attacker_id] = {
                "source": str(spec.get("source", "") or "Stabilised Disembarkation").strip() or "Stabilised Disembarkation",
                "disembark_max_distance": int(spec.get("disembark_max_distance", 0) or 0),
            }
            sr["stabilised_disembarkation_pending_by_attacker"] = pending
            target_root.special_rules = sr

    def _on_unit_shooting_resolved_stabilised_disembarkation(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None:
            return
        attacker_id = str(get_entity_id(attacker_root) or "")
        if not attacker_id:
            return
        try:
            attacker_army = attacker_root.get_parent_army()
        except Exception:
            attacker_army = None

        enemy_roots: list[Any] = []
        seen_enemy_ids: set[str] = set()
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None or army is attacker_army:
                continue
            for root in list(self._iter_unique_army_roots(army) or []):
                if root is None:
                    continue
                rid = str(get_entity_id(root) or "")
                if rid and rid in seen_enemy_ids:
                    continue
                if rid:
                    seen_enemy_ids.add(rid)
                enemy_roots.append(root)

        for enemy_root in enemy_roots:
            if enemy_root is None:
                continue
            sr = getattr(enemy_root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            pending = sr.get("stabilised_disembarkation_pending_by_attacker")
            if not isinstance(pending, dict):
                continue
            pending_spec = dict(pending.pop(attacker_id, {}) or {})
            if pending:
                sr["stabilised_disembarkation_pending_by_attacker"] = pending
            else:
                sr.pop("stabilised_disembarkation_pending_by_attacker", None)
            enemy_root.special_rules = sr
            if not pending_spec:
                continue
            if not bool(getattr(enemy_root, "is_transport", False)):
                continue
            try:
                if not bool(enemy_root.is_alive()) or not bool(getattr(enemy_root, "deployed", True)):
                    continue
            except Exception:
                continue
            try:
                if enemy_root.is_in_reserves() or bool(getattr(enemy_root, "is_embarked", False)):
                    continue
            except Exception:
                pass
            if not list(getattr(enemy_root, "transport_passengers", []) or []):
                continue
            try:
                disembark_max_distance = float(pending_spec.get("disembark_max_distance", 0) or 0)
            except Exception:
                disembark_max_distance = 0.0
            if disembark_max_distance <= 0:
                continue
            try:
                target_player = enemy_root.get_parent_army().player
            except Exception:
                target_player = None
            if target_player is None:
                continue

            ability_name = (
                str(pending_spec.get("source", "") or "Stabilised Disembarkation").strip()
                or "Stabilised Disembarkation"
            )
            ability = {
                "name": ability_name,
                "description": "",
                "disembark_max_distance": float(disembark_max_distance),
            }
            requests = self._queue_transport_reactive_disembark_decisions(
                player=target_player,
                transport=enemy_root,
                enemy_unit=attacker_root,
                ability=ability,
                trigger="enemy_shooting_targeted_transport",
                disembark_max_distance=float(disembark_max_distance),
                disembark_require_not_in_engagement=True,
            )
            if not requests:
                continue
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("transport_reactive_disembark_prompt"))
            if has_sub and bool(getattr(target_player, "has_control", lambda: False)()):
                es.publish(
                    "transport_reactive_disembark_prompt",
                    player=target_player,
                    transport=enemy_root,
                    enemy_unit=attacker_root,
                    ability=ability,
                    game=self,
                )

    def _on_fight_unit_selected_battle_focus(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None or selecting_player is None:
            return
        army = getattr(selecting_player, "army", None)
        mgr = getattr(army, "battle_focus", None) if army is not None else None
        if mgr is None:
            return
        mgr.maybe_trigger_sudden_strike(unit, self)

    def _on_unit_shooting_resolved_battle_focus(self, attacker_unit=None, hits_by_target=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        if not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Battle Focus shooting requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        hits_by_player: dict = {}
        for target_unit, hits in (hits_by_target or {}).items():
            if target_unit is None:
                continue
            hits = int(hits or 0)
            if hits <= 0:
                continue
            target_player = target_unit.get_parent_army().player
            if target_player is attacker_player:
                continue
            hits_by_player.setdefault(target_player, {})[target_unit] = hits

        for player, hits_map in hits_by_player.items():
            if player is None:
                raise RuntimeError("Battle Focus shooting requires target players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Battle Focus shooting requires an army for {player.name}.")
            mgr = getattr(army, "battle_focus", None)
            if mgr is None:
                continue
            hit_units = list(hits_map.keys())
            candidates = mgr.get_fade_back_candidates(hit_units, self)
            if not candidates:
                continue
            request = self._queue_battle_focus_reactive_selection(
                player=player,
                candidates=list(candidates),
                manager=mgr,
                maneuver="fade_back",
                attacker_unit=attacker_unit,
                hits_by_unit=dict(hits_map),
            )
            if request is None:
                continue
            if player.has_control():
                es = getattr(self, "event_system", None)
                if es is None or not hasattr(es, "subscribers"):
                    raise RuntimeError("Event system missing for Battle Focus prompt.")
                subs = getattr(es, "subscribers", None)
                if not isinstance(subs, dict):
                    raise RuntimeError("Event system subscribers not configured.")
                if subs.get("battle_focus_fade_back_prompt"):
                    es.publish(
                        "battle_focus_fade_back_prompt",
                        player=player,
                        attacker_unit=attacker_unit,
                        candidates=list(candidates),
                        hits_by_unit=dict(hits_map),
                        manager=mgr,
                    )

    def _interlocking_tactics_hit_candidates(self, attacker_unit=None, hits_by_target=None):
        if attacker_unit is None or not isinstance(hits_by_target, dict):
            return None, None, None, []
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        attacker_army = attacker_root.get_parent_army() if attacker_root is not None else None
        if attacker_army is None:
            return None, None, None, []
        attacker_player = getattr(attacker_army, "player", None)
        sm_mgr = getattr(attacker_army, "space_marines_detachments", None)
        if sm_mgr is None or not getattr(sm_mgr, "interlocking_tactics_battleline_applies", None):
            return None, None, None, []
        if not sm_mgr.interlocking_tactics_battleline_applies(attacker_root):
            return None, None, None, []

        candidates_by_id = {}
        for target_unit, hits in list((hits_by_target or {}).items()):
            if target_unit is None:
                continue
            if int(hits or 0) <= 0:
                continue
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is None:
                continue
            try:
                if target_root.get_parent_army() is attacker_army:
                    continue
            except Exception:
                continue
            try:
                if not bool(target_root.is_alive()):
                    continue
            except Exception:
                continue
            tid = str(get_entity_id(target_root) or "")
            if not tid:
                continue
            if tid not in candidates_by_id:
                candidates_by_id[tid] = target_root

        candidates = list(candidates_by_id.values())
        try:
            candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
        except Exception:
            candidates = list(candidates)
        return attacker_root, attacker_player, sm_mgr, candidates

    def _queue_interlocking_tactics_auspex_scan(self, *, attacker_root=None, attacker_player=None, candidates=None) -> None:
        if attacker_root is None or attacker_player is None:
            return
        candidate_list = list(candidates or [])
        if not candidate_list:
            return
        options = [
            DecisionOption.create(
                str(getattr(cand, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(cand)},
            )
            for cand in candidate_list
        ]
        if not options:
            return
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Interlocking Tactics: select an auspex scanned unit.",
            player_id=getattr(attacker_player, "id", None),
            options=options,
            context={
                "ability": "interlocking_tactics_auspex_scan",
                "ability_name": "Interlocking Tactics",
                "attacker_unit_id": get_entity_id(attacker_root),
                "turn": int(getattr(self, "turn", 0) or 0),
            },
        )
        self.request_decision(request)

    def _on_unit_shooting_resolved_interlocking_tactics(self, attacker_unit=None, hits_by_target=None, **_kwargs) -> None:
        attacker_root, attacker_player, _sm_mgr, candidates = self._interlocking_tactics_hit_candidates(
            attacker_unit=attacker_unit,
            hits_by_target=hits_by_target,
        )
        if attacker_root is None or attacker_player is None or not candidates:
            return
        self._queue_interlocking_tactics_auspex_scan(
            attacker_root=attacker_root,
            attacker_player=attacker_player,
            candidates=candidates,
        )

    def _on_fight_attacks_resolved_interlocking_tactics(self, unit=None, hits_by_target=None, **_kwargs) -> None:
        attacker_root, attacker_player, _sm_mgr, candidates = self._interlocking_tactics_hit_candidates(
            attacker_unit=unit,
            hits_by_target=hits_by_target,
        )
        if attacker_root is None or attacker_player is None or not candidates:
            return
        owner_id = str(getattr(attacker_player, "id", "") or "")
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        pending_turn = int(sr.get("interlocking_tactics_pending_turn", 0) or 0)
        pending_owner = str(sr.get("interlocking_tactics_pending_owner", "") or "")
        if pending_turn != current_turn or pending_owner != owner_id:
            pending_ids = []
        else:
            pending_ids = [str(v or "") for v in list(sr.get("interlocking_tactics_pending_target_ids", []) or []) if str(v or "")]
        for cand in candidates:
            cid = str(get_entity_id(cand) or "")
            if cid and cid not in pending_ids:
                pending_ids.append(cid)
        sr["interlocking_tactics_pending_turn"] = int(current_turn or 0)
        sr["interlocking_tactics_pending_owner"] = owner_id
        sr["interlocking_tactics_pending_target_ids"] = sorted(set(pending_ids))
        attacker_root.special_rules = sr

    def _on_fight_sequence_complete_interlocking_tactics(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            attacker_root = unit.get_attached_unit_root()
        except Exception:
            attacker_root = unit
        if attacker_root is None:
            return
        attacker_army = attacker_root.get_parent_army() if hasattr(attacker_root, "get_parent_army") else None
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
        if attacker_player is None:
            return
        owner_id = str(getattr(attacker_player, "id", "") or "")
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        pending_turn = int(sr.get("interlocking_tactics_pending_turn", 0) or 0)
        pending_owner = str(sr.get("interlocking_tactics_pending_owner", "") or "")
        pending_ids = [str(v or "") for v in list(sr.get("interlocking_tactics_pending_target_ids", []) or []) if str(v or "")]
        if pending_turn != current_turn or pending_owner != owner_id or not pending_ids:
            return
        candidates = []
        for unit_id in pending_ids:
            target = None
            registry = getattr(self, "entity_registry", None)
            if registry is not None and callable(getattr(registry, "get", None)):
                target = registry.get(unit_id, kind="unit")
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            if target_root is None:
                continue
            try:
                if target_root.get_parent_army() is attacker_army:
                    continue
            except Exception:
                continue
            try:
                if not bool(target_root.is_alive()):
                    continue
            except Exception:
                continue
            candidates.append(target_root)
        try:
            candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
        except Exception:
            candidates = list(candidates)
        sr.pop("interlocking_tactics_pending_turn", None)
        sr.pop("interlocking_tactics_pending_owner", None)
        sr.pop("interlocking_tactics_pending_target_ids", None)
        attacker_root.special_rules = sr
        if not candidates:
            return
        self._queue_interlocking_tactics_auspex_scan(
            attacker_root=attacker_root,
            attacker_player=attacker_player,
            candidates=candidates,
        )

    def _on_unit_shooting_resolved_legendary_slayers(self, attacker_unit=None, hits_by_target=None, **_kwargs) -> None:
        if attacker_unit is None or not isinstance(hits_by_target, dict):
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None:
            return
        attacker_army = attacker_root.get_parent_army() if hasattr(attacker_root, "get_parent_army") else None
        sm_mgr = getattr(attacker_army, "space_marines_detachments", None) if attacker_army is not None else None
        register_fn = getattr(sm_mgr, "legendary_slayers_register_shooting_resolved", None) if sm_mgr is not None else None
        if not callable(register_fn):
            return
        register_fn(attacker_unit=attacker_root, hits_by_target=hits_by_target, game=self)

    def _on_fight_attacks_resolved_legendary_slayers(self, unit=None, hits_by_target=None, **_kwargs) -> None:
        if unit is None or not isinstance(hits_by_target, dict):
            return
        try:
            attacker_root = unit.get_attached_unit_root()
        except Exception:
            attacker_root = unit
        if attacker_root is None:
            return
        attacker_army = attacker_root.get_parent_army() if hasattr(attacker_root, "get_parent_army") else None
        sm_mgr = getattr(attacker_army, "space_marines_detachments", None) if attacker_army is not None else None
        mark_fn = getattr(sm_mgr, "legendary_slayers_mark_fight_hit_targets", None) if sm_mgr is not None else None
        if not callable(mark_fn):
            return
        mark_fn(attacker_unit=attacker_root, hits_by_target=hits_by_target, game=self)

    def _on_fight_sequence_complete_legendary_slayers(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            attacker_root = unit.get_attached_unit_root()
        except Exception:
            attacker_root = unit
        if attacker_root is None:
            return
        attacker_army = attacker_root.get_parent_army() if hasattr(attacker_root, "get_parent_army") else None
        sm_mgr = getattr(attacker_army, "space_marines_detachments", None) if attacker_army is not None else None
        resolve_fn = getattr(sm_mgr, "legendary_slayers_resolve_fight_sequence", None) if sm_mgr is not None else None
        if not callable(resolve_fn):
            return
        resolve_fn(attacker_unit=attacker_root, game=self)

    def _on_fight_attacks_resolved_pack_quarry(self, unit=None, hits_by_target=None, **_kwargs) -> None:
        if unit is None or not isinstance(hits_by_target, dict):
            return
        try:
            attacker_root = unit.get_attached_unit_root()
        except Exception:
            attacker_root = unit
        if attacker_root is None:
            return
        attacker_army = attacker_root.get_parent_army() if hasattr(attacker_root, "get_parent_army") else None
        sm_mgr = getattr(attacker_army, "space_marines_detachments", None) if attacker_army is not None else None
        mark_fn = getattr(sm_mgr, "pack_quarry_mark_fight_hit_targets", None) if sm_mgr is not None else None
        if not callable(mark_fn):
            return
        mark_fn(attacker_unit=attacker_root, hits_by_target=hits_by_target, game=self)

    def _on_fight_sequence_complete_pack_quarry(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            attacker_root = unit.get_attached_unit_root()
        except Exception:
            attacker_root = unit
        if attacker_root is None:
            return
        attacker_army = attacker_root.get_parent_army() if hasattr(attacker_root, "get_parent_army") else None
        sm_mgr = getattr(attacker_army, "space_marines_detachments", None) if attacker_army is not None else None
        resolve_fn = getattr(sm_mgr, "pack_quarry_resolve_fight_sequence", None) if sm_mgr is not None else None
        if not callable(resolve_fn):
            return
        resolve_fn(attacker_unit=attacker_root, game=self)

    def _on_unit_shooting_resolved_tactical_acumen(
        self,
        attacker_unit=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Tactical Acumen requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return
        try:
            if not getattr(attacker_unit, "deployed", True):
                return
        except Exception:
            return
        try:
            if attacker_unit.is_in_reserves() or attacker_unit.is_embarked:
                return
        except Exception:
            pass

        def _has_pending_reactive_move(unit_obj) -> bool:
            unit_id = maybe_entity_id(unit_obj)
            queue = getattr(self, "decision_queue", None)
            if queue is None or not hasattr(queue, "list"):
                return False
            for req in list(queue.list() or []):
                decision_type = str(getattr(req, "decision_type", ""))
                if decision_type not in (DECISION_MOVE_UNIT, DECISION_CONFIRM_YES_NO):
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                kind = str(ctx.get("reactive_move_kind", "") or "")
                if kind not in ("tactical_acumen", "post_shoot_no_charge", "execute_and_redeploy"):
                    continue
                if str(ctx.get("unit_id", "") or "") == str(unit_id or ""):
                    return True
            return False

        if _has_pending_reactive_move(attacker_unit):
            return

        leading_specs = attacker_unit.leading_tactical_acumen_specs() or []
        for spec in leading_specs:
            leader = spec.get("leader")
            if leader is None:
                continue
            try:
                if not getattr(leader, "is_alive", lambda: False)():
                    continue
            except Exception:
                continue
            try:
                if leader.get_attached_unit_root() is not attacker_unit.get_attached_unit_root():
                    continue
            except Exception:
                pass
            try:
                max_distance = int(spec.get("range", 0) or 0)
            except Exception:
                max_distance = 0
            if max_distance <= 0:
                continue
            source = str(spec.get("source", "") or "Tactical Acumen").strip() or "Tactical Acumen"
            self._queue_reactive_move_movement_decision(
                player=attacker_player,
                unit=attacker_unit,
                max_distance=max_distance,
                kind="tactical_acumen",
                movement_type="reactive",
                source=source,
            )
            return

        unit_specs = attacker_unit.unit_post_shoot_reactive_move_no_charge_specs() or []

        engaged = False
        try:
            game_map = getattr(self, "map", None)
            if game_map is not None:
                enemies = list(game_map.get_enemy_units(attacker_unit) or [])
                for enemy in enemies:
                    if enemy is None or not enemy.is_alive():
                        continue
                    try:
                        if not bool(getattr(enemy, "deployed", True)):
                            continue
                    except Exception:
                        continue
                    try:
                        if game_map.is_within_engagement_range(attacker_unit, enemy):
                            engaged = True
                            break
                    except Exception:
                        continue
        except Exception:
            engaged = False

        try:
            attacker_army = attacker_unit.get_parent_army()
        except Exception:
            attacker_army = None
        sm_mgr = getattr(attacker_army, "space_marines_detachments", None) if attacker_army is not None else None
        execute_spec_fn = (
            getattr(sm_mgr, "vanguard_execute_and_redeploy_reactive_move", None)
            if sm_mgr is not None
            else None
        )
        if callable(execute_spec_fn) and not engaged:
            try:
                execute_distance, execute_source = execute_spec_fn(attacker_unit, game=self)
            except Exception:
                execute_distance, execute_source = 0, ""
            if int(execute_distance or 0) > 0:
                self._queue_reactive_move_movement_decision(
                    player=attacker_player,
                    unit=attacker_unit,
                    max_distance=int(execute_distance),
                    kind="execute_and_redeploy",
                    movement_type="reactive",
                    source=execute_source or "Execute and Redeploy",
                )
                return

        adm_mgr = getattr(attacker_army, "adeptus_mechanicus_detachments", None) if attacker_army is not None else None
        battle_sphere_fn = (
            getattr(adm_mgr, "skitarii_battle_sphere_uplink_reactive_move", None)
            if adm_mgr is not None
            else None
        )
        if callable(battle_sphere_fn):
            try:
                battle_sphere_distance, battle_sphere_source = battle_sphere_fn(
                    attacker_unit,
                    game=self,
                    is_engaged=engaged,
                )
            except (TypeError, ValueError):
                battle_sphere_distance, battle_sphere_source = 0, ""
            if int(battle_sphere_distance or 0) > 0:
                self._queue_reactive_move_movement_decision(
                    player=attacker_player,
                    unit=attacker_unit,
                    max_distance=int(battle_sphere_distance),
                    kind="post_shoot_no_charge",
                    movement_type="reactive",
                    source=battle_sphere_source or "Battle-sphere Uplink",
                )
                return

        if not unit_specs:
            return

        def _spec_requirements_met(spec: dict) -> bool:
            required_model_name = str(spec.get("required_model_name", "") or "").strip()
            required_wargear_name = str(spec.get("required_wargear_name", "") or "").strip()
            if not required_model_name or not required_wargear_name:
                return True
            try:
                root = attacker_unit.get_attached_unit_root()
            except Exception:
                root = attacker_unit
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]
            for member in list(members or []):
                if member is None:
                    continue
                find_model = getattr(member, "_find_model_named", None)
                matched_model = find_model(required_model_name) if callable(find_model) else None
                if matched_model is None:
                    continue
                has_wargear = getattr(member, "_model_has_wargear_named", None)
                if callable(has_wargear):
                    try:
                        if bool(has_wargear(matched_model, required_wargear_name)):
                            return True
                    except Exception:
                        continue
            return False

        for spec in unit_specs:
            if not _spec_requirements_met(spec):
                continue
            if bool(spec.get("requires_not_engaged", False)) and engaged:
                continue
            range_roll = str(spec.get("range_roll", "") or "").strip().upper()
            if bool(spec.get("use_move_characteristic", False)):
                max_distance = 0
                try:
                    models = list(attacker_unit.get_attached_unit_models() or [])
                except Exception:
                    models = list(getattr(attacker_unit, "models", []) or [])
                for model in list(models or []):
                    if model is None or not getattr(model, "is_alive", False):
                        continue
                    try:
                        current = int(attacker_unit.get_effective_model_characteristic(model, "movement", game_map=self.map) or 0)
                    except Exception:
                        current = 0
                    if current > max_distance:
                        max_distance = int(current)
            elif range_roll == "D6":
                try:
                    from ...utility.dice import get_roll
                    max_distance = int(get_roll("D6") or 0)
                except Exception:
                    max_distance = 0
                try:
                    from ...utility.event_bus import append_dice
                    append_dice(attacker_player, f"{str(spec.get('source', '') or 'Reactive move').strip()}: {max_distance}")
                except Exception:
                    pass
            else:
                try:
                    max_distance = int(spec.get("range", 0) or 0)
                except Exception:
                    max_distance = 0
            if max_distance <= 0:
                continue
            source = str(spec.get("source", "") or "Post-shoot reactive move").strip() or "Post-shoot reactive move"
            try:
                battleline_distance = int(spec.get("battleline_wholly_within_max_distance", 0) or 0)
            except Exception:
                battleline_distance = 0
            try:
                battleline_range = int(spec.get("battleline_wholly_within_range", 0) or 0)
            except Exception:
                battleline_range = 0
            if battleline_distance > 0 and battleline_range > 0:
                unit_id = str(maybe_entity_id(attacker_unit) or "")
                if not unit_id:
                    continue
                message = (
                    f"{source}: Choose one option:\n"
                    f"- Make a Normal move of up to {int(max_distance)}\".\n"
                    f"- Make a Normal move of up to {int(battleline_distance)}\", provided every model in this unit "
                    f"ends that move wholly within {int(battleline_range)}\" of one or more friendly ADEPTUS MECHANICUS BATTLELINE units."
                )
                request = DecisionRequest.create(
                    DECISION_CONFIRM_YES_NO,
                    source,
                    player_id=getattr(attacker_player, "id", None),
                    options=[
                        DecisionOption.create(
                            f"{int(max_distance)}\" Move",
                            payload={"choice": True, "post_shoot_no_charge_mode": "base"},
                        ),
                        DecisionOption.create(
                            f"{int(battleline_distance)}\" Battleline Move",
                            payload={"choice": True, "post_shoot_no_charge_mode": "battleline_6"},
                        ),
                        DecisionOption.create("Skip", payload={"choice": False}),
                    ],
                    context={
                        **self._reactive_move_context(
                            kind="post_shoot_no_charge",
                            unit_id=unit_id,
                            movement_type="reactive",
                            source=source,
                        ),
                        "message": message,
                        "post_shoot_no_charge_base_max_distance": int(max_distance),
                        "post_shoot_no_charge_battleline_max_distance": int(battleline_distance),
                        "post_shoot_no_charge_battleline_range": int(battleline_range),
                    },
                )
                self.request_decision(request)
                return
            self._queue_reactive_move_movement_decision(
                player=attacker_player,
                unit=attacker_unit,
                max_distance=max_distance,
                kind="post_shoot_no_charge",
                movement_type="reactive",
                source=source,
            )
            return

    def _on_unit_shooting_resolved_post_shoot_battleshock(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        hit_models_by_target_weapon=None,
        killing_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot Battle-shock requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _is_monster_or_vehicle(unit) -> bool:
            if unit is None:
                return False
            try:
                return bool(unit.has_any_keyword("MONSTER")) or bool(unit.has_any_keyword("VEHICLE"))
            except Exception:
                return False

        def _is_monster_or_vehicle(unit) -> bool:
            if unit is None:
                return False
            try:
                return bool(unit.has_keyword("MONSTER") or unit.has_keyword("VEHICLE"))
            except Exception:
                pass
            try:
                return bool(unit.has_any_keyword("MONSTER") or unit.has_any_keyword("VEHICLE"))
            except Exception:
                return False

        def _model_hit_target(model, target) -> bool:
            if not isinstance(hit_models_by_target, dict):
                return True
            hit_models = hit_models_by_target.get(target)
            if not hit_models:
                return False
            return model in hit_models

        def _normalize_weapon_key(value: str) -> str:
            normalizer = getattr(attacker_unit, "_normalize_keyword_phrase", None)
            if callable(normalizer):
                try:
                    return str(normalizer(value) or "")
                except Exception:
                    return ""
            text = str(value or "").lower()
            text = re.sub(r"[^a-z0-9]+", " ", text)
            return re.sub(r"\s+", " ", text).strip()

        def _target_weapon_hit_models(target, weapon_key: str):
            if not weapon_key or not isinstance(hit_models_by_target_weapon, dict):
                return None
            target_map = hit_models_by_target_weapon.get(target)
            if target_map is None:
                try:
                    target_root = target.get_attached_unit_root()
                except Exception:
                    target_root = target
                target_map = hit_models_by_target_weapon.get(target_root)
            if not isinstance(target_map, dict):
                return None
            models = target_map.get(weapon_key)
            if not models and weapon_key.endswith("s"):
                models = target_map.get(weapon_key[:-1])
            if not models and not weapon_key.endswith("s"):
                models = target_map.get(f"{weapon_key}s")
            return models

        indirect_weapon_keys_by_model: dict[str, set[str]] = {}
        all_indirect_weapon_keys: set[str] = set()

        def _model_indirect_weapon_keys(model) -> set[str]:
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in indirect_weapon_keys_by_model:
                return set(indirect_weapon_keys_by_model[model_id])
            keys: set[str] = set()
            for wargear in list(getattr(model, "wargear", []) or []):
                is_ranged_fn = getattr(wargear, "is_ranged", None)
                try:
                    if callable(is_ranged_fn) and not bool(is_ranged_fn()):
                        continue
                except Exception:
                    continue
                profiles = getattr(wargear, "profiles", None)
                if not isinstance(profiles, dict):
                    continue
                for profile in list(profiles.values()):
                    if profile is None:
                        continue
                    is_indirect_fn = getattr(profile, "is_indirect_fire", None)
                    try:
                        is_indirect = bool(is_indirect_fn()) if callable(is_indirect_fn) else False
                    except Exception:
                        is_indirect = False
                    if not is_indirect:
                        continue
                    weapon_name = ""
                    try:
                        parent = getattr(profile, "parent_wargear", None)
                        if parent is not None:
                            weapon_name = str(getattr(parent, "name", "") or "")
                    except Exception:
                        weapon_name = ""
                    if not weapon_name:
                        weapon_name = str(getattr(profile, "name", "") or "")
                    key = _normalize_weapon_key(weapon_name)
                    if key:
                        keys.add(key)
                        all_indirect_weapon_keys.add(key)
            if model_id:
                indirect_weapon_keys_by_model[model_id] = set(keys)
            return set(keys)

        def _model_hit_target_with_any_indirect_weapon(model, target) -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            weapon_keys = _model_indirect_weapon_keys(model)
            if not weapon_keys:
                return False
            for weapon_key in list(weapon_keys):
                hit_models = _target_weapon_hit_models(target, weapon_key)
                if hit_models and model in hit_models:
                    return True
            return False

        def _target_hit_with_any_indirect_weapon(target) -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            if not all_indirect_weapon_keys:
                for model in list(attacker_unit.models or []):
                    _model_indirect_weapon_keys(model)
            if not all_indirect_weapon_keys:
                return False
            for weapon_key in list(all_indirect_weapon_keys):
                hit_models = _target_weapon_hit_models(target, weapon_key)
                if hit_models:
                    return True
            return False

        def _target_hit_with_weapon_key(target, weapon_key: str) -> bool:
            normalized_key = _normalize_weapon_key(weapon_key)
            if not normalized_key:
                return False
            return bool(_target_weapon_hit_models(target, normalized_key))

        def _model_hit_target_with_weapon_key(model, target, weapon_key: str) -> bool:
            normalized_key = _normalize_weapon_key(weapon_key)
            if not normalized_key:
                return False
            models = _target_weapon_hit_models(target, normalized_key)
            if not models:
                return False
            return model in models

        def _is_monster_or_vehicle(unit) -> bool:
            if unit is None:
                return False
            try:
                return bool(unit.has_keyword("MONSTER") or unit.has_keyword("VEHICLE"))
            except Exception:
                pass
            try:
                return bool(unit.has_any_keyword("MONSTER") or unit.has_any_keyword("VEHICLE"))
            except Exception:
                return False

        def _is_vehicle(unit) -> bool:
            if unit is None:
                return False
            try:
                return bool(unit.has_keyword("VEHICLE"))
            except Exception:
                pass
            try:
                return bool(unit.has_any_keyword("VEHICLE"))
            except Exception:
                return False

        def _is_infantry(unit) -> bool:
            if unit is None:
                return False
            is_infantry_fn = getattr(unit, "is_infantry", None)
            if callable(is_infantry_fn):
                try:
                    return bool(is_infantry_fn())
                except Exception:
                    pass
            return bool(getattr(unit, "is_infantry", False))

        def _spec_allows_target(spec: dict, target) -> bool:
            infantry_only = bool(spec.get("infantry_only", False))
            exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
            exclude_vehicle_only = bool(spec.get("exclude_vehicle_only", False))
            if infantry_only and not _is_infantry(target):
                return False
            if exclude_mv and _is_monster_or_vehicle(target):
                return False
            if exclude_vehicle_only and _is_vehicle(target):
                return False
            return True

        def _model_killed_target(model, target) -> bool:
            if not isinstance(killing_models_by_target, dict):
                return False
            killed_models = killing_models_by_target.get(target)
            if not killed_models:
                return False
            return model in killed_models

        def _unit_killed_target(target) -> bool:
            if not isinstance(killing_models_by_target, dict):
                return False
            killed_models = killing_models_by_target.get(target)
            return bool(killed_models)

        def _target_within_friendly_keyword_phrase_range(target_unit, *, phrase: str, range_value: float) -> bool:
            if target_unit is None:
                return False
            if range_value <= 0:
                return False
            try:
                from ...utility.aura_utils import unit_within_range_of_unit
            except Exception:
                return False
            phrase_txt = str(phrase or "").strip()
            if not phrase_txt:
                return False
            friends = []
            try:
                game_map = getattr(self, "map", None)
                if game_map is not None:
                    friends = list(game_map.get_friendly_units(attacker_unit) or [])
            except Exception:
                friends = []
            for friendly in friends:
                if friendly is None or not friendly.is_alive():
                    continue
                try:
                    if not bool(getattr(friendly, "deployed", True)):
                        continue
                    if friendly.is_in_reserves() or friendly.is_embarked:
                        continue
                except Exception:
                    continue
                matcher = getattr(attacker_unit, "_unit_matches_keyword_phrase", None)
                if not callable(matcher):
                    continue
                if not matcher(friendly, phrase_txt):
                    continue
                try:
                    if unit_within_range_of_unit(friendly, target_unit, float(range_value), use_attached_aggregate=True):
                        return True
                except Exception:
                    continue
            return False

        from ..decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET

        def _army_usage_available(spec: dict) -> bool:
            usage_key = str(spec.get("army_usage_key", "") or "").strip().upper()
            usage_scope = str(spec.get("army_usage_scope", "") or "").strip().lower()
            if not usage_key or attacker_player is None:
                return True
            if usage_scope == "turn":
                used_turn_fn = getattr(attacker_player, "_ability_used_this_turn", None)
                if callable(used_turn_fn) and bool(used_turn_fn(usage_key)):
                    return False
            elif usage_scope == "battle_round":
                try:
                    current_turn = int(getattr(self, "turn", 0) or 0)
                except Exception:
                    current_turn = 0
                used_rounds = getattr(attacker_player, "_ability_used_battle_round", None)
                if isinstance(used_rounds, dict) and current_turn > 0:
                    if int(used_rounds.get(usage_key, 0) or 0) == int(current_turn):
                        return False
            queue = getattr(self, "decision_queue", None)
            if queue is None or not hasattr(queue, "list"):
                return True
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET:
                    continue
                if getattr(req, "player_id", None) != getattr(attacker_player, "id", None):
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("army_usage_key", "") or "").strip().upper() != usage_key:
                    continue
                if str(ctx.get("army_usage_scope", "") or "").strip().lower() != usage_scope:
                    continue
                return False
            return True

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_battleshock_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                if not _army_usage_available(spec):
                    continue
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _spec_allows_target(spec, target_unit):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    required_weapon_key = str(spec.get("require_weapon_key_hit", "") or "").strip()
                    if required_weapon_key and not _model_hit_target_with_weapon_key(model, target_unit, required_weapon_key):
                        continue
                    if bool(spec.get("require_indirect_fire_hit", False)) and not _model_hit_target_with_any_indirect_weapon(
                        model, target_unit
                    ):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        unit_specs = attacker_unit.unit_post_shoot_battleshock_specs() or []
        for spec in unit_specs:
            if not _army_usage_available(spec):
                continue
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                if not _spec_allows_target(spec, target_unit):
                    continue
                required_weapon_key = str(spec.get("require_weapon_key_hit", "") or "").strip()
                if required_weapon_key and not _target_hit_with_weapon_key(target_unit, required_weapon_key):
                    continue
                if bool(spec.get("require_indirect_fire_hit", False)) and not _target_hit_with_any_indirect_weapon(
                    target_unit
                ):
                    continue
                candidates.append(target_unit)
            if candidates:
                triggers.append((None, spec, candidates))

        if not triggers:
            return

        def _battle_shock_modifier_for_target(spec: dict, cand, model) -> int:
            modifier = 0
            try:
                modifier = int(spec.get("test_modifier", 0) or 0)
            except Exception:
                modifier = 0
            try:
                conditional_mod = int(spec.get("test_modifier_if_target_within_range", 0) or 0)
            except Exception:
                conditional_mod = 0
            if conditional_mod:
                try:
                    cond_range = float(spec.get("test_modifier_range", 0) or 0.0)
                except Exception:
                    cond_range = 0.0
                phrase = str(spec.get("test_modifier_friendly_keyword_phrase", "") or "")
                if _target_within_friendly_keyword_phrase_range(
                    cand,
                    phrase=phrase,
                    range_value=cond_range,
                ):
                    modifier += int(conditional_mod)
            try:
                infantry_weapon_mod = int(spec.get("test_modifier_if_infantry_hit_by_weapon", 0) or 0)
            except (TypeError, ValueError):
                infantry_weapon_mod = 0
            if infantry_weapon_mod and _is_infantry(cand):
                infantry_weapon_name = str(spec.get("test_modifier_if_infantry_hit_by_weapon_name", "") or "")
                if infantry_weapon_name:
                    if model is None:
                        if _target_hit_with_weapon_key(cand, infantry_weapon_name):
                            modifier += int(infantry_weapon_mod)
                    else:
                        if _model_hit_target_with_weapon_key(model, cand, infantry_weapon_name):
                            modifier += int(infantry_weapon_mod)
            try:
                if spec.get("test_modifier_on_kill"):
                    if model is None:
                        if _unit_killed_target(cand):
                            modifier += int(spec.get("test_modifier_on_kill", 0) or 0)
                    else:
                        if _model_killed_target(model, cand):
                            modifier += int(spec.get("test_modifier_on_kill", 0) or 0)
            except Exception:
                pass
            return int(modifier)

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
            if bool(spec.get("auto_each_target", False)):
                tested_ids: set[str] = set()
                for cand in list(candidates):
                    if cand is None or not getattr(cand, "is_alive", lambda: False)():
                        continue
                    target_id = str(get_entity_id(cand) or "")
                    if target_id and target_id in tested_ids:
                        continue
                    modifier = _battle_shock_modifier_for_target(spec, cand, model)
                    if modifier:
                        sr = getattr(cand, "special_rules", None)
                        if not isinstance(sr, dict):
                            sr = {}
                        current = int(sr.get("battle_shock_test_modifier", 0) or 0)
                        sr["battle_shock_test_modifier"] = int(current + modifier)
                        reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
                        reasons.append(ability_name)
                        sr["battle_shock_test_modifier_reasons"] = reasons
                        cand.special_rules = sr
                    try:
                        cand.take_battle_shock_test(int(getattr(self, "turn", 0) or 0))
                    except Exception:
                        pass
                    try:
                        target_name = str(getattr(cand, "name", "Unit") or "Unit")
                        _log_action_for_players(self, attacker_player, f"{ability_name}: {target_name} takes a Battle-shock test.")
                    except Exception:
                        pass
                    if target_id:
                        tested_ids.add(target_id)
                continue
            options = []
            for cand in list(candidates):
                modifier = _battle_shock_modifier_for_target(spec, cand, model)
                payload = {"unit_id": get_entity_id(cand)}
                if modifier:
                    payload["battle_shock_test_modifier"] = int(modifier)
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload=payload,
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
                f"{ability_name}: select a unit to take a Battle-shock test.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model) if model is not None else None,
                    "ability_name": ability_name,
                    "army_usage_key": str(spec.get("army_usage_key", "") or "").strip().upper(),
                    "army_usage_scope": str(spec.get("army_usage_scope", "") or "").strip().lower(),
                },
            )
            self.request_decision(request)

    def _on_fight_attacks_resolved_post_fight_battleshock(
        self,
        unit=None,
        attacker_unit=None,
        target_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        killing_models_by_target=None,
        **_kwargs,
    ) -> None:
        attacker_unit = attacker_unit if attacker_unit is not None else unit
        if attacker_unit is None:
            return
        if not self.is_fight_phase():
            return
        try:
            attacker_members = list(attacker_unit.get_attached_unit_members() or [])
        except Exception:
            attacker_members = [attacker_unit]
        if not attacker_members:
            attacker_members = [attacker_unit]
        attacker_model_count = 0
        for member in list(attacker_members or []):
            if member is None:
                continue
            try:
                attacker_model_count += len(list(member.models or []))
            except Exception:
                continue
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-fight Battle-shock requires an attacker player.")
        self._on_fight_attacks_resolved_creations_of_bile_specimens_for_the_spider(attacker_unit=attacker_unit)
        if attacker_player is not self.get_current_player():
            return

        if not hits_by_target:
            if target_unit is None:
                return
            hits_by_target = {target_unit: 1}

        def _is_enemy_unit(candidate) -> bool:
            if candidate is None:
                return False
            if candidate.get_parent_army() == attacker_unit.get_parent_army():
                return False
            return bool(candidate.is_alive())

        def _is_monster_or_vehicle(unit) -> bool:
            if unit is None:
                return False
            try:
                return bool(unit.has_keyword("MONSTER") or unit.has_keyword("VEHICLE"))
            except Exception:
                pass
            try:
                return bool(unit.has_any_keyword("MONSTER") or unit.has_any_keyword("VEHICLE"))
            except Exception:
                return False

        def _is_vehicle(unit) -> bool:
            if unit is None:
                return False
            try:
                return bool(unit.has_keyword("VEHICLE"))
            except Exception:
                pass
            try:
                return bool(unit.has_any_keyword("VEHICLE"))
            except Exception:
                return False

        def _is_infantry(unit) -> bool:
            if unit is None:
                return False
            is_infantry_fn = getattr(unit, "is_infantry", None)
            if callable(is_infantry_fn):
                try:
                    return bool(is_infantry_fn())
                except Exception:
                    pass
            return bool(getattr(unit, "is_infantry", False))

        def _spec_allows_target(spec: dict, target) -> bool:
            infantry_only = bool(spec.get("infantry_only", False))
            exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
            exclude_vehicle_only = bool(spec.get("exclude_vehicle_only", False))
            if infantry_only and not _is_infantry(target):
                return False
            if exclude_mv and _is_monster_or_vehicle(target):
                return False
            if exclude_vehicle_only and _is_vehicle(target):
                return False
            return True

        def _model_hit_target(model, candidate) -> bool:
            if not isinstance(hit_models_by_target, dict):
                return True
            hit_models = hit_models_by_target.get(candidate)
            if not hit_models:
                return False
            return model in hit_models

        def _model_destroyed_any_enemy_unit(model) -> bool:
            if isinstance(killing_models_by_target, dict):
                model_id = str(get_entity_id(model) or "")
                for target, killing_models in list((killing_models_by_target or {}).items()):
                    if target is None:
                        continue
                    try:
                        target_root = target.get_attached_unit_root()
                    except Exception:
                        target_root = target
                    if target_root is None:
                        continue
                    try:
                        if target_root.get_parent_army() == attacker_unit.get_parent_army():
                            continue
                    except Exception:
                        continue
                    try:
                        target_destroyed = not bool(target_root.is_alive())
                    except Exception:
                        target_destroyed = False
                    if not target_destroyed:
                        continue
                    if not killing_models:
                        return True
                    if model in killing_models:
                        return True
                    if model_id:
                        for killer in list(killing_models or []):
                            if str(get_entity_id(killer) or "") == model_id:
                                return True
                            if str(killer or "") == model_id:
                                return True
                    if attacker_model_count == 1:
                        return True
            if target_unit is None:
                return False
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is None:
                return False
            try:
                if target_root.get_parent_army() == attacker_unit.get_parent_army():
                    return False
            except Exception:
                return False
            try:
                if bool(target_root.is_alive()):
                    return False
            except Exception:
                return False
            return _model_hit_target(model, target_root) or _model_hit_target(model, target_unit)

        def _unit_destroyed_any_enemy_unit() -> bool:
            if isinstance(killing_models_by_target, dict):
                for target in list((killing_models_by_target or {}).keys()):
                    if target is None:
                        continue
                    try:
                        target_root = target.get_attached_unit_root()
                    except Exception:
                        target_root = target
                    if target_root is None:
                        continue
                    try:
                        if target_root.get_parent_army() == attacker_unit.get_parent_army():
                            continue
                    except Exception:
                        continue
                    try:
                        if not bool(target_root.is_alive()):
                            return True
                    except Exception:
                        continue
            if target_unit is None:
                return False
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is None:
                return False
            try:
                if target_root.get_parent_army() == attacker_unit.get_parent_army():
                    return False
            except Exception:
                return False
            try:
                return not bool(target_root.is_alive())
            except Exception:
                return False

        def _collect_enemy_roots_for_aura() -> list[Any]:
            game_map = getattr(self, "map", None)
            if game_map is None:
                return []
            try:
                enemies = list(game_map.get_enemy_units(attacker_unit) or [])
            except Exception:
                enemies = []
            roots: list[Any] = []
            seen_ids: set[str] = set()
            for enemy in enemies:
                if enemy is None:
                    continue
                try:
                    enemy_root = enemy.get_attached_unit_root()
                except Exception:
                    enemy_root = enemy
                if enemy_root is None:
                    continue
                try:
                    if not bool(enemy_root.is_alive()):
                        continue
                    if not bool(getattr(enemy_root, "deployed", True)):
                        continue
                    if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                        continue
                except Exception:
                    continue
                eid = str(get_entity_id(enemy_root) or "")
                if eid and eid in seen_ids:
                    continue
                if eid:
                    seen_ids.add(eid)
                roots.append(enemy_root)
            return roots

        def _willbreaker_applies_for_model(model) -> tuple[bool, str]:
            sr = getattr(attacker_unit, "special_rules", None)
            if not isinstance(sr, dict):
                return False, ""
            if not bool(sr.get("enhancement_willbreaker", False)):
                return False, ""
            if not bool(sr.get("enhancement_willbreaker_applies_after_fight", True)):
                return False, ""
            bearer_id = str(
                sr.get("enhancement_willbreaker_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            model_matches_bearer = False
            model_entity_id = str(get_entity_id(model) or "").strip()
            model_local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
            if bearer_id:
                model_matches_bearer = bool(model_entity_id == bearer_id or (model_local_id and model_local_id == bearer_id))
            else:
                get_bearer = getattr(attacker_unit, "_get_enhancement_bearer_model", None)
                bearer = get_bearer() if callable(get_bearer) else None
                if bearer is not None:
                    model_matches_bearer = bool(
                        model is bearer
                        or str(get_entity_id(bearer) or "").strip() == model_entity_id
                        or (
                            model_local_id
                            and model_local_id == str(getattr(bearer, "id", getattr(bearer, "_id", "")) or "").strip()
                        )
                    )
            if not model_matches_bearer:
                return False, ""
            source = str(sr.get("enhancement_willbreaker_source", "") or "Willbreaker").strip() or "Willbreaker"
            return True, source

        def _target_within_friendly_keyword_phrase_range(candidate, *, phrase: str, range_value: float) -> bool:
            if candidate is None or range_value <= 0:
                return False
            try:
                from ...utility.aura_utils import unit_within_range_of_unit
            except Exception:
                return False
            phrase_txt = str(phrase or "").strip()
            if not phrase_txt:
                return False
            try:
                friends = list(getattr(self, "map").get_friendly_units(attacker_unit) or [])
            except Exception:
                friends = []
            matcher = getattr(attacker_unit, "_unit_matches_keyword_phrase", None)
            if not callable(matcher):
                return False
            for friendly in friends:
                if friendly is None or not friendly.is_alive():
                    continue
                try:
                    if not bool(getattr(friendly, "deployed", True)):
                        continue
                    if friendly.is_in_reserves() or friendly.is_embarked:
                        continue
                except Exception:
                    continue
                if not matcher(friendly, phrase_txt):
                    continue
                try:
                    if unit_within_range_of_unit(friendly, candidate, float(range_value), use_attached_aggregate=True):
                        return True
                except Exception:
                    continue
            return False

        enemy_roots_for_aura = _collect_enemy_roots_for_aura()
        unit_destroyed_any_enemy_unit = _unit_destroyed_any_enemy_unit()
        try:
            current_turn = int(getattr(self, "turn", 0) or 1)
        except Exception:
            current_turn = 1

        from ..decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET

        for member in list(attacker_members or []):
            if member is None:
                continue
            for model in list(getattr(member, "models", []) or []):
                if not getattr(model, "is_alive", False):
                    continue
                aura_specs = member.model_post_fight_destroyed_aura_battleshock_specs(model) or []
                if aura_specs and enemy_roots_for_aura:
                    already_tested_enemy_ids: set[str] = set()
                    for aura_spec in aura_specs:
                        trigger_from_unit_destroy = bool(aura_spec.get("requires_unit_destroyed_enemy_unit", False))
                        if trigger_from_unit_destroy:
                            if not unit_destroyed_any_enemy_unit:
                                continue
                        elif not _model_destroyed_any_enemy_unit(model):
                            continue
                        try:
                            aura_range = float(aura_spec.get("range", 0) or 0.0)
                        except Exception:
                            aura_range = 0.0
                        if aura_range <= 0:
                            continue
                        for enemy_root in enemy_roots_for_aura:
                            enemy_id = str(get_entity_id(enemy_root) or "")
                            if enemy_id and enemy_id in already_tested_enemy_ids:
                                continue
                            try:
                                in_range = bool(
                                    self._unit_within_range_of_model(
                                        model,
                                        enemy_root,
                                        range_value=aura_range,
                                    )
                                )
                            except Exception:
                                in_range = False
                            if not in_range:
                                continue
                            enemy_root.take_battle_shock_test(current_turn)
                            if enemy_id:
                                already_tested_enemy_ids.add(enemy_id)
                specs = member.model_post_fight_battleshock_specs(model) or []
                willbreaker_applies, willbreaker_source = _willbreaker_applies_for_model(model)
                if willbreaker_applies:
                    if not any(
                        str(spec.get("source", "") or "").strip().lower() == str(willbreaker_source).strip().lower()
                        for spec in list(specs or [])
                        if isinstance(spec, dict)
                    ):
                        specs = list(specs)
                        specs.append(
                            {
                                "infantry_only": False,
                                "exclude_monster_vehicle": False,
                                "exclude_vehicle_only": False,
                                "test_modifier": 0,
                                "test_modifier_on_kill": 0,
                                "test_modifier_if_target_within_range": 0,
                                "test_modifier_range": 0,
                                "test_modifier_friendly_keyword_phrase": "",
                                "applies_after_fight": True,
                                "source": str(willbreaker_source),
                            }
                        )
                if not specs:
                    continue
                for spec in specs:
                    candidates = []
                    for cand, hits in list((hits_by_target or {}).items()):
                        if cand is None:
                            continue
                        if int(hits or 0) <= 0:
                            continue
                        if not _is_enemy_unit(cand):
                            continue
                        if not _spec_allows_target(spec, cand):
                            continue
                        if not _model_hit_target(model, cand):
                            continue
                        candidates.append(cand)
                    if not candidates:
                        continue
                    ability_name = str(spec.get("source", "") or "Post-fight Battle-shock").strip() or "Post-fight Battle-shock"
                    options = []
                    for cand in list(candidates):
                        try:
                            modifier = int(spec.get("test_modifier", 0) or 0)
                        except Exception:
                            modifier = 0
                        try:
                            conditional_mod = int(spec.get("test_modifier_if_target_within_range", 0) or 0)
                        except Exception:
                            conditional_mod = 0
                        if conditional_mod:
                            try:
                                cond_range = float(spec.get("test_modifier_range", 0) or 0.0)
                            except Exception:
                                cond_range = 0.0
                            phrase = str(spec.get("test_modifier_friendly_keyword_phrase", "") or "")
                            if _target_within_friendly_keyword_phrase_range(
                                cand,
                                phrase=phrase,
                                range_value=cond_range,
                            ):
                                modifier += int(conditional_mod)
                        payload = {"unit_id": get_entity_id(cand)}
                        if modifier:
                            payload["battle_shock_test_modifier"] = int(modifier)
                        options.append(
                            DecisionOption.create(
                                str(getattr(cand, "name", "Unit") or "Unit"),
                                payload=payload,
                            )
                        )
                    if not options:
                        continue
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
                        f"{ability_name}: select a unit to take a Battle-shock test.",
                        player_id=getattr(attacker_player, "id", None),
                        options=options,
                        context={
                            "attacker_unit_id": get_entity_id(attacker_unit),
                            "model_id": get_entity_id(model),
                            "ability_name": ability_name,
                        },
                    )
                    self.request_decision(request)

        unit_specs = attacker_unit.unit_post_fight_battleshock_specs() or []
        for spec in unit_specs:
            candidates = []
            for cand, hits in list((hits_by_target or {}).items()):
                if cand is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(cand):
                    continue
                if not _spec_allows_target(spec, cand):
                    continue
                candidates.append(cand)
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Post-fight Battle-shock").strip() or "Post-fight Battle-shock"
            options = []
            for cand in list(candidates):
                try:
                    modifier = int(spec.get("test_modifier", 0) or 0)
                except Exception:
                    modifier = 0
                try:
                    conditional_mod = int(spec.get("test_modifier_if_target_within_range", 0) or 0)
                except Exception:
                    conditional_mod = 0
                if conditional_mod:
                    try:
                        cond_range = float(spec.get("test_modifier_range", 0) or 0.0)
                    except Exception:
                        cond_range = 0.0
                    phrase = str(spec.get("test_modifier_friendly_keyword_phrase", "") or "")
                    if _target_within_friendly_keyword_phrase_range(
                        cand,
                        phrase=phrase,
                        range_value=cond_range,
                    ):
                        modifier += int(conditional_mod)
                payload = {"unit_id": get_entity_id(cand)}
                if modifier:
                    payload["battle_shock_test_modifier"] = int(modifier)
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload=payload,
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
                f"{ability_name}: select a unit to take a Battle-shock test.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": None,
                    "ability_name": ability_name,
                },
            )
            self.request_decision(request)

    def _on_fight_attacks_resolved_creations_of_bile_specimens_for_the_spider(self, *, attacker_unit=None) -> None:
        if attacker_unit is None:
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None:
            return
        try:
            attacker_army = attacker_root.get_parent_army()
        except Exception:
            attacker_army = None
        csm_mgr = getattr(attacker_army, "chaos_space_marines_detachments", None) if attacker_army is not None else None
        resolve_fn = (
            getattr(csm_mgr, "creations_of_bile_specimens_for_the_spider_post_fight_resolution", None)
            if csm_mgr is not None
            else None
        )
        if not callable(resolve_fn):
            return
        outcome = resolve_fn(attacker_root, game=self)
        if not isinstance(outcome, dict):
            return

        candidate_units = [candidate for candidate in list(outcome.get("candidate_units", []) or []) if candidate is not None]
        if not candidate_units:
            return
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        if bool(outcome.get("warlord_destroyed", False)):
            for candidate in list(candidate_units or []):
                candidate.take_battle_shock_test(current_turn)
            return

        from ..decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET

        ability_name = str(outcome.get("source", "") or "Specimens for the Spider").strip() or "Specimens for the Spider"
        attacker_id = str(get_entity_id(attacker_root) or "")
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("attacker_unit_id", "") or "") != attacker_id:
                    continue
                if str(ctx.get("ability_name", "") or "").strip().lower() != ability_name.lower():
                    continue
                return

        options = [
            DecisionOption.create(
                str(getattr(candidate, "name", "Unit") or "Unit"),
                payload={"unit_id": get_entity_id(candidate)},
            )
            for candidate in list(candidate_units or [])
        ]
        if not options:
            return
        request = DecisionRequest.create(
            DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
            f"{ability_name}: select a unit to take a Battle-shock test.",
            player_id=getattr(getattr(attacker_army, "player", None), "id", None),
            options=options,
            context={
                "attacker_unit_id": get_entity_id(attacker_root),
                "model_id": None,
                "ability_name": ability_name,
            },
        )
        self.request_decision(request)

    def _on_fight_attacks_resolved_post_fight_suppression(
        self,
        unit=None,
        attacker_unit=None,
        target_unit=None,
        hits_by_target=None,
        **_kwargs,
    ) -> None:
        attacker_unit = attacker_unit if attacker_unit is not None else unit
        if attacker_unit is None:
            return
        if not self.is_fight_phase():
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None or not attacker_root.is_alive():
            return
        attacker_army = attacker_root.get_parent_army()
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
        if attacker_player is None:
            raise RuntimeError("Post-fight suppression requires an attacker player.")

        if not hits_by_target:
            if target_unit is None:
                return
            hits_by_target = {target_unit: 1}

        specs = attacker_root.unit_post_fight_suppression_specs() or []
        if not specs:
            return

        def _is_enemy_unit(candidate) -> bool:
            if candidate is None:
                return False
            if candidate.get_parent_army() == attacker_root.get_parent_army():
                return False
            return bool(candidate.is_alive())

        def _is_monster_or_vehicle(candidate) -> bool:
            if candidate is None:
                return False
            try:
                return bool(candidate.has_keyword("MONSTER") or candidate.has_keyword("VEHICLE"))
            except Exception:
                pass
            try:
                return bool(candidate.has_any_keyword("MONSTER") or candidate.has_any_keyword("VEHICLE"))
            except Exception:
                return False

        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        players = list(getattr(self, "players", []) or [])
        next_owner_id = ""
        expires_turn = int(current_turn or 0)
        if players:
            try:
                current_index = int(getattr(self, "current_player_index", 0) or 0)
            except Exception:
                current_index = 0
            next_index = (current_index + 1) % len(players)
            next_player = players[next_index]
            next_owner_id = str(getattr(next_player, "id", "") or "")
            starting_index = getattr(self, "battle_round_starting_player_index", None)
            try:
                wraps_battle_round = bool(next_index == int(starting_index)) if starting_index is not None else bool(next_index <= current_index)
            except Exception:
                wraps_battle_round = bool(next_index <= current_index)
            if wraps_battle_round and current_turn > 0:
                expires_turn = int(current_turn + 1)

        from ..decision_kinds import DECISION_CHOOSE_POST_FIGHT_SUPPRESSION_TARGET

        for spec in list(specs or []):
            candidates = []
            for candidate, hits in list((hits_by_target or {}).items()):
                if candidate is None or int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(candidate):
                    continue
                if bool(spec.get("monster_vehicle_only", False)) and not _is_monster_or_vehicle(candidate):
                    continue
                candidates.append(candidate)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = [
                DecisionOption.create(
                    str(getattr(candidate, "name", "Unit") or "Unit"),
                    payload={"unit_id": get_entity_id(candidate)},
                )
                for candidate in list(candidates)
            ]
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "Post-fight Suppression").strip() or "Post-fight Suppression"
            request = DecisionRequest.create(
                DECISION_CHOOSE_POST_FIGHT_SUPPRESSION_TARGET,
                f"{ability_name}: select a MONSTER or VEHICLE unit to suppress.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_root),
                    "ability_name": ability_name,
                    "attack_types": list(spec.get("attack_types") or ("melee", "ranged")),
                    "expires_timing": str(spec.get("expires_timing", "") or "end_of_next_turn"),
                    "expires_turn": int(expires_turn or 0),
                    "expires_turn_owner": next_owner_id,
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_shoot_again(
        self,
        attacker_unit=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Shoot-again abilities require an attacker player.")
        if attacker_player is not self.get_current_player():
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        if root is None or not root.is_alive():
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass

        specs = root.unit_post_shoot_shoot_again_specs() or []
        if not specs:
            return
        for spec in list(specs or []):
            ability_name = str(spec.get("source", "") or "Shoot again").strip() or "Shoot again"
            ability_key = str(spec.get("ability_key") or "post_shoot_shoot_again").strip().lower()
            if not ability_key:
                ability_key = "post_shoot_shoot_again"
            if root.has_used_unit_once_per_battle(ability_key):
                continue
            unit_id = maybe_entity_id(root)
            ctx = {
                "ability_name": ability_name,
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "ability_key": ability_key,
                "phase": "Shooting phase",
            }
            message = f"Use {ability_name} to shoot again for {getattr(root, 'name', 'Unit')}?"
            self._queue_optional_ability_confirmation(
                player=attacker_player,
                ability_key="sentinel_storm",
                ability_name=ability_name,
                message=message,
                context=ctx,
                payload={"unit_id": unit_id, "ability_key": ability_key},
                instance_key=f"{unit_id}:{ability_key}",
            )

    def _on_unit_shooting_resolved_post_shoot_disembark_wound_reroll(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Fire Support requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target(model, target) -> bool:
            if not isinstance(hit_models_by_target, dict):
                return True
            hit_models = hit_models_by_target.get(target)
            if not hit_models:
                return False
            return model in hit_models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_disembark_wound_reroll_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Fire Support").strip() or "Fire Support"
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a target.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability": "post_shoot_disembark_wound_reroll",
                    "ability_name": ability_name,
                    "reroll_full": bool(spec.get("reroll_full", True)),
                    "reroll_values": list(spec.get("reroll_values", ()) or []),
                    "expires_phase": str(spec.get("expires_phase", "SHOOTING_PHASE") or ""),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_disembark_hit_reroll(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Transport Support requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target(model, target) -> bool:
            if not isinstance(hit_models_by_target, dict):
                return True
            hit_models = hit_models_by_target.get(target)
            if not hit_models:
                return False
            return model in hit_models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_disembark_hit_reroll_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for model, spec, candidates in triggers:
            ability_name = str(spec.get("source", "") or "Transport Support").strip() or "Transport Support"
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a target.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability": "post_shoot_disembark_hit_reroll",
                    "ability_name": ability_name,
                    "reroll_full": bool(spec.get("reroll_full", True)),
                    "reroll_values": list(spec.get("reroll_values", ()) or []),
                    "expires_phase": str(spec.get("expires_phase", "SHOOTING_PHASE") or ""),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_disembark_ap_bonus(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot disembark AP bonus requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target(model, target) -> bool:
            if not isinstance(hit_models_by_target, dict):
                return True
            hit_models = hit_models_by_target.get(target)
            if not hit_models:
                return False
            return model in hit_models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_disembark_ap_bonus_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Fire Focus").strip() or "Fire Focus"
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a target.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability": "post_shoot_disembark_ap_bonus",
                    "ability_name": ability_name,
                    "ap_bonus": int(spec.get("value", 1) or 1),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_disembark_psychic_hit_wound_bonus(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot disembark Psychic hit/wound bonus requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target(model, target) -> bool:
            if not isinstance(hit_models_by_target, dict):
                return True
            hit_models = hit_models_by_target.get(target)
            if not hit_models:
                return False
            return model in hit_models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_disembark_psychic_hit_wound_bonus_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Sorcerous Support").strip() or "Sorcerous Support"
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a target.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability": "post_shoot_disembark_psychic_hit_wound_bonus",
                    "ability_name": ability_name,
                    "hit_bonus": int(spec.get("hit_bonus", 0) or 0),
                    "wound_bonus": int(spec.get("wound_bonus", 0) or 0),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_thousand_sons_psychic_hit_markers(
        self,
        attacker_unit=None,
        hit_models_by_target_psychic=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None:
            return
        if not isinstance(hit_models_by_target_psychic, dict) or not hit_models_by_target_psychic:
            return
        try:
            attacker_player = attacker_unit.get_parent_army().player
        except Exception:
            attacker_player = None
        owner_id = str(getattr(attacker_player, "id", "") or "")
        if not owner_id:
            return

        try:
            has_ts = bool(attacker_unit.has_any_keyword("THOUSAND SONS"))
        except Exception:
            has_ts = False
        if not has_ts:
            return

        def _model_has_psyker_keyword(model_obj) -> bool:
            if model_obj is None:
                return False
            has_keyword = getattr(model_obj, "has_keyword", None)
            if callable(has_keyword):
                try:
                    if bool(has_keyword("PSYKER")):
                        return True
                except Exception:
                    pass
            keywords = list(getattr(model_obj, "keywords", []) or [])
            return any(str(k or "").strip().upper() == "PSYKER" for k in keywords)

        from ...rules.thousand_sons_psychic_marks import mark_target_hit_by_thousand_sons_psychic_attack

        for target_unit, hit_models in list(hit_models_by_target_psychic.items()):
            if target_unit is None:
                continue
            if not hit_models:
                continue
            if not any(_model_has_psyker_keyword(m) for m in list(hit_models or [])):
                continue
            try:
                mark_target_hit_by_thousand_sons_psychic_attack(
                    self,
                    target_unit=target_unit,
                    owner_id=owner_id,
                )
            except Exception:
                continue

    def _on_unit_shooting_resolved_post_shoot_mortal_wounds_battleshock(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot mortal wounds requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_mortal_wounds_battleshock_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    is_infantry_fn = getattr(target_unit, "is_infantry", None)
                    if callable(is_infantry_fn):
                        is_infantry = bool(is_infantry_fn())
                    else:
                        is_infantry = bool(getattr(target_unit, "is_infantry", False))
                    if not is_infantry:
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_POST_SHOOT_MORTAL_WOUNDS_TARGET

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Post-shoot Mortals").strip() or "Post-shoot Mortals"
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_POST_SHOOT_MORTAL_WOUNDS_TARGET,
                f"{ability_name}: select a unit to suffer mortal wounds.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability_name": ability_name,
                    "dice": int(spec.get("dice", 3) or 3),
                    "threshold": int(spec.get("threshold", 4) or 4),
                    "mortal_per_success": int(spec.get("mortal_per_success", 1) or 1),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_monster_vehicle_mortal_threshold(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot MONSTER/VEHICLE mortal ability requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _target_has_monster_or_vehicle_keyword(unit) -> bool:
            try:
                if unit.has_keyword("MONSTER") or unit.has_keyword("VEHICLE"):
                    return True
            except Exception:
                pass
            try:
                if unit.has_any_keyword("MONSTER") or unit.has_any_keyword("VEHICLE"):
                    return True
            except Exception:
                return False
            return False

        def _model_hit_target(model, target) -> bool:
            if not isinstance(hit_models_by_target, dict):
                return False
            models = hit_models_by_target.get(target)
            if not models:
                return False
            return model in models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_monster_vehicle_mortal_threshold_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _target_has_monster_or_vehicle_keyword(target_unit):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Post-shoot mortals").strip() or "Post-shoot mortals"
            try:
                ability_key = re.sub(r"[^a-z0-9]+", "_", ability_name.lower()).strip("_")
            except Exception:
                ability_key = ""
            ability = "metalophagic_infection" if ability_key == "metalophagic_infection" else "post_shoot_monster_vehicle_mortal_threshold"
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a hit enemy MONSTER or VEHICLE unit.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "ability": ability,
                    "ability_name": ability_name,
                    "source_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "threshold": int(spec.get("threshold", 5) or 5),
                    "mortal_wounds": spec.get("mortal_wounds", "d3"),
                    "afflicted_roll_bonus": int(spec.get("afflicted_roll_bonus", 0) or 0),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_wracking_agonies(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Wracking Agonies requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target_with_weapon(model, target, weapon_key: str) -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(weapon_key)
            if not models:
                return False
            return model in models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_wracking_agonies_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                weapon_key = str(spec.get("weapon_key", "") or "")
                if not weapon_key:
                    continue
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    is_infantry_fn = getattr(target_unit, "is_infantry", None)
                    if callable(is_infantry_fn):
                        is_infantry = bool(is_infantry_fn())
                    else:
                        is_infantry = bool(getattr(target_unit, "is_infantry", False))
                    if not is_infantry:
                        continue
                    if not _model_hit_target_with_weapon(model, target_unit, weapon_key):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_POST_SHOOT_WRACKED_AGONIES_TARGET

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Wracking Agonies").strip() or "Wracking Agonies"
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_POST_SHOOT_WRACKED_AGONIES_TARGET,
                f"{ability_name}: select a unit wracked with agonies.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability_name": ability_name,
                    "move_penalty": int(spec.get("move_penalty", -2) or -2),
                    "charge_penalty": int(spec.get("charge_penalty", -2) or -2),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_snare(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot snare requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target_with_weapon(model, target, weapon_key: str) -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(weapon_key)
            if not models and weapon_key.endswith("s"):
                models = target_map.get(weapon_key[:-1])
            if not models:
                return False
            return model in models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_snare_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                weapon_key = str(spec.get("weapon_key", "") or "")
                if not weapon_key:
                    continue
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _model_hit_target_with_weapon(model, target_unit, weapon_key):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Snare").strip() or "Snare"
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a snare target.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability": "post_shoot_snare",
                    "ability_name": ability_name,
                    "weapon_key": str(spec.get("weapon_key", "") or ""),
                    "weapon_name": str(spec.get("weapon_name", "") or ""),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_stormwracked(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Stormwracked requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target_with_weapon(model, target, weapon_key: str) -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(weapon_key)
            if not models and weapon_key.endswith("s"):
                models = target_map.get(weapon_key[:-1])
            if not models:
                return False
            return model in models

        def _is_excluded_target(unit, keywords: tuple[str, ...]) -> bool:
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            for keyword in list(keywords or ()):
                if not keyword:
                    continue
                if bool(root.has_keyword(keyword) or root.has_any_keyword(keyword)):
                    return True
            return False

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_stormwracked_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                weapon_key = str(spec.get("weapon_key", "") or "")
                if not weapon_key:
                    continue
                excluded = tuple(str(value or "").strip().upper() for value in tuple(spec.get("exclude_keywords_any", ()) or ()))
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if excluded and _is_excluded_target(target_unit, excluded):
                        continue
                    if not _model_hit_target_with_weapon(model, target_unit, weapon_key):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Tempest's Wrath (Psychic)").strip() or "Tempest's Wrath (Psychic)"
            excluded = tuple(
                str(value or "").strip().upper()
                for value in tuple(spec.get("exclude_keywords_any", ()) or ())
                if str(value or "").strip()
            )
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a stormwracked target.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability": "post_shoot_stormwracked",
                    "ability_name": ability_name,
                    "weapon_key": str(spec.get("weapon_key", "") or ""),
                    "weapon_name": str(spec.get("weapon_name", "") or ""),
                    "range_penalty": int(spec.get("range_penalty", 6) or 6),
                    "range_minimum": int(spec.get("range_minimum", 12) or 12),
                    "exclude_keywords_any": list(excluded),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_pinned(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Pinned requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return
        hit_models_by_target = _kwargs.get("hit_models_by_target")

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target_with_weapon(model, target, weapon_key: str) -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(weapon_key)
            if not models and weapon_key.endswith("s"):
                models = target_map.get(weapon_key[:-1])
            if not models:
                return False
            return model in models

        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_pinned_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                weapon_key = str(spec.get("weapon_key", "") or "")
                if not weapon_key:
                    continue
                try:
                    move_penalty = int(spec.get("move_penalty", -2) or -2)
                except Exception:
                    move_penalty = -2
                try:
                    charge_penalty = int(spec.get("charge_penalty", -2) or -2)
                except Exception:
                    charge_penalty = -2
                source = str(spec.get("source", "") or "Pinned").strip() or "Pinned"
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _model_hit_target_with_weapon(model, target_unit, weapon_key):
                        continue
                    try:
                        target_root = target_unit.get_attached_unit_root()
                    except Exception:
                        target_root = target_unit
                    owner_id = str(getattr(attacker_player, "id", "") or "")
                    try:
                        turn = int(getattr(self, "turn", 0) or 0)
                    except Exception:
                        turn = 0
                    apply_fn = getattr(target_root, "apply_pinned", None)
                    if callable(apply_fn):
                        apply_fn(
                            owner_id=owner_id,
                            turn=turn,
                            source=source,
                            move_penalty=int(move_penalty),
                            charge_penalty=int(charge_penalty),
                        )
                    else:
                        sr = getattr(target_root, "special_rules", None)
                        if not isinstance(sr, dict):
                            sr = {}
                        sr["pinned_active"] = True
                        sr["pinned_owner"] = owner_id
                        sr["pinned_turn"] = int(turn or 0)
                        sr["pinned_source"] = source
                        sr["pinned_move_penalty"] = int(move_penalty)
                        sr["pinned_charge_penalty"] = int(charge_penalty)
                        target_root.special_rules = sr
                    try:
                        tname = str(getattr(target_root, "name", "Unit") or "Unit")
                        _log_action_for_players(self, attacker_player, f"{source}: {tname} is pinned until your next turn.")
                    except Exception:
                        pass

        def _is_monster_or_vehicle(unit) -> bool:
            if unit is None:
                return False
            try:
                return bool(unit.has_keyword("MONSTER") or unit.has_keyword("VEHICLE"))
            except Exception:
                pass
            try:
                return bool(unit.has_any_keyword("MONSTER") or unit.has_any_keyword("VEHICLE"))
            except Exception:
                return False

        def _has_any_keyword(unit, keywords: list[str]) -> bool:
            if unit is None:
                return False
            for kw in list(keywords or []):
                key = str(kw or "").strip().upper()
                if not key:
                    continue
                try:
                    if bool(unit.has_keyword(key)):
                        return True
                except Exception:
                    pass
                try:
                    if bool(unit.has_any_keyword(key)):
                        return True
                except Exception:
                    pass
            return False

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        unit_specs = attacker_unit.unit_post_shoot_pinned_specs() or []
        for spec in unit_specs:
            exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
            include_keywords_any = [
                str(kw or "").strip().upper()
                for kw in list(spec.get("include_keywords_any", []) or [])
                if str(kw or "").strip()
            ]
            expires_phase = str(spec.get("expires_phase", "") or "COMMAND_PHASE").strip().upper() or "COMMAND_PHASE"
            try:
                move_penalty = int(spec.get("move_penalty", -2) or -2)
            except Exception:
                move_penalty = -2
            try:
                charge_penalty = int(spec.get("charge_penalty", -2) or -2)
            except Exception:
                charge_penalty = -2
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                if exclude_mv and _is_monster_or_vehicle(target_unit):
                    continue
                if include_keywords_any and not _has_any_keyword(target_unit, include_keywords_any):
                    continue
                candidates.append(target_unit)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "Pinned").strip() or "Pinned"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit to pin.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_pinned",
                    "ability_name": ability_name,
                    "move_penalty": int(move_penalty),
                    "charge_penalty": int(charge_penalty),
                    "expires_phase": expires_phase,
                    "include_keywords_any": list(include_keywords_any),
                },
            )
            self.request_decision(request)

        try:
            attacker_army = attacker_unit.get_parent_army()
        except Exception:
            attacker_army = None
        necron_mgr = getattr(attacker_army, "necrons_detachments", None) if attacker_army is not None else None
        gravitic_fn = (
            getattr(necron_mgr, "cryptek_conclave_gravitic_bolas_requests", None)
            if necron_mgr is not None
            else None
        )
        gravitic_requests = (
            list(
                gravitic_fn(
                    attacker_unit,
                    hits_by_target=hits_by_target,
                    hit_models_by_target=hit_models_by_target,
                    game=self,
                )
                or []
            )
            if callable(gravitic_fn)
            else []
        )
        for request_info in gravitic_requests:
            candidates = list(request_info.get("candidate_units", []) or [])
            if not candidates:
                continue
            options = [
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(cand)},
                )
                for cand in candidates
            ]
            if not options:
                continue
            ability_name = str(request_info.get("ability_name", "") or "Gravitic Bolas").strip() or "Gravitic Bolas"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit to pin.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_pinned",
                    "ability_name": ability_name,
                    "move_penalty": int(request_info.get("move_penalty", -2) or -2),
                    "charge_penalty": int(request_info.get("charge_penalty", -2) or -2),
                    "expires_phase": str(request_info.get("expires_phase", "") or "COMMAND_PHASE").strip().upper()
                    or "COMMAND_PHASE",
                    "include_keywords_any": [],
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_aflame(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot aflame requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _is_monster_or_vehicle(unit) -> bool:
            if unit is None:
                return False
            try:
                return bool(unit.has_keyword("MONSTER") or unit.has_keyword("VEHICLE"))
            except Exception:
                pass
            try:
                return bool(unit.has_any_keyword("MONSTER") or unit.has_any_keyword("VEHICLE"))
            except Exception:
                return False

        def _model_hit_target(model, target) -> bool:
            if not isinstance(hit_models_by_target, dict):
                return True
            hit_models = hit_models_by_target.get(target)
            if not hit_models:
                return False
            return model in hit_models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_aflame_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if exclude_mv and _is_monster_or_vehicle(target_unit):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_POST_SHOOT_AFLAME_TARGET

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Aflame").strip() or "Aflame"
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_POST_SHOOT_AFLAME_TARGET,
                f"{ability_name}: select a unit to set aflame.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model),
                    "ability_name": ability_name,
                    "move_penalty": int(spec.get("move_penalty", -2) or -2),
                    "advance_penalty": int(spec.get("advance_penalty", -2) or -2),
                    "charge_penalty": int(spec.get("charge_penalty", -2) or -2),
                    "roll_threshold": int(spec.get("roll_threshold", 4) or 4),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_shocked(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot shocked requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _is_monster_or_vehicle(unit) -> bool:
            if unit is None:
                return False
            try:
                return bool(unit.has_keyword("MONSTER") or unit.has_keyword("VEHICLE"))
            except Exception:
                pass
            try:
                return bool(unit.has_any_keyword("MONSTER") or unit.has_any_keyword("VEHICLE"))
            except Exception:
                return False

        def _matches_any_keyword(unit, keywords: list[str]) -> bool:
            if unit is None:
                return False
            wanted = [
                str(kw or "").strip().upper()
                for kw in list(keywords or [])
                if str(kw or "").strip()
            ]
            if not wanted:
                return True
            for keyword in wanted:
                try:
                    if unit.has_keyword(keyword):
                        return True
                except Exception:
                    pass
                try:
                    if unit.has_any_keyword(keyword):
                        return True
                except Exception:
                    pass
            return False

        def _target_weapon_hit_models(target, weapon_key: str):
            if not weapon_key or not isinstance(hit_models_by_target_weapon, dict):
                return None
            target_map = hit_models_by_target_weapon.get(target)
            if target_map is None:
                try:
                    target_root = target.get_attached_unit_root()
                except Exception:
                    target_root = target
                target_map = hit_models_by_target_weapon.get(target_root)
            if not isinstance(target_map, dict):
                return None
            models = target_map.get(weapon_key)
            if not models and weapon_key.endswith("s"):
                models = target_map.get(weapon_key[:-1])
            if not models and not weapon_key.endswith("s"):
                models = target_map.get(f"{weapon_key}s")
            if models:
                return models
            for key, key_models in list(target_map.items()):
                normalized_key = attacker_unit._normalize_keyword_phrase(key) if hasattr(attacker_unit, "_normalize_keyword_phrase") else ""
                if normalized_key == weapon_key:
                    return key_models
            return None

        def _target_hit_with_weapon(target, weapon_key: str) -> bool:
            if not weapon_key:
                return True
            return bool(_target_weapon_hit_models(target, weapon_key))

        specs = attacker_unit.unit_post_shoot_shocked_specs() or []
        if not specs:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for spec in specs:
            exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
            try:
                raw_move_penalty = spec.get("move_penalty", -2)
                move_penalty = int(-2 if raw_move_penalty is None else raw_move_penalty)
            except Exception:
                move_penalty = -2
            try:
                raw_advance_penalty = spec.get("advance_penalty", -2)
                advance_penalty = int(-2 if raw_advance_penalty is None else raw_advance_penalty)
            except Exception:
                advance_penalty = -2
            try:
                raw_charge_penalty = spec.get("charge_penalty", advance_penalty)
                charge_penalty = int(advance_penalty if raw_charge_penalty is None else raw_charge_penalty)
            except Exception:
                charge_penalty = int(advance_penalty)
            include_keywords_any = [
                str(kw or "").strip().upper()
                for kw in list(spec.get("include_keywords_any", []) or [])
                if str(kw or "").strip()
            ]
            weapon_key = str(spec.get("weapon_key", "") or "").strip()
            state_name = str(spec.get("state_name", "shocked") or "shocked").strip().lower() or "shocked"
            expires_timing = str(spec.get("expires_timing", "OPPONENT_NEXT_TURN_END") or "OPPONENT_NEXT_TURN_END").strip().upper()
            auto_each_target = bool(spec.get("auto_each_target", False))
            try:
                roll_threshold = int(spec.get("roll_threshold", 0) or 0)
            except Exception:
                roll_threshold = 0

            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                if exclude_mv and _is_monster_or_vehicle(target_unit):
                    continue
                if include_keywords_any and not _matches_any_keyword(target_unit, include_keywords_any):
                    continue
                if weapon_key and not _target_hit_with_weapon(target_unit, weapon_key):
                    continue
                candidates.append(target_unit)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            ability_name = str(spec.get("source", "") or "Shocked").strip() or "Shocked"
            if auto_each_target:
                for cand in list(candidates):
                    try:
                        target_root = cand.get_attached_unit_root()
                    except Exception:
                        target_root = cand
                    if target_root is None or not getattr(target_root, "is_alive", lambda: False)():
                        continue
                    apply_fn = getattr(target_root, "apply_shocked", None)
                    if callable(apply_fn):
                        apply_fn(
                            owner_id=str(getattr(attacker_player, "id", "") or ""),
                            turn=int(getattr(self, "turn", 0) or 0),
                            source=ability_name,
                            move_penalty=int(move_penalty),
                            advance_penalty=int(advance_penalty),
                            charge_penalty=int(charge_penalty),
                            expires_timing=expires_timing,
                        )
                    else:
                        sr = getattr(target_root, "special_rules", None)
                        if not isinstance(sr, dict):
                            sr = {}
                        sr["shocked_active"] = True
                        sr["shocked_owner"] = str(getattr(attacker_player, "id", "") or "")
                        sr["shocked_turn"] = int(getattr(self, "turn", 0) or 0)
                        sr["shocked_source"] = ability_name
                        sr["shocked_move_penalty"] = int(move_penalty)
                        sr["shocked_advance_penalty"] = int(advance_penalty)
                        sr["shocked_charge_penalty"] = int(charge_penalty)
                        sr["shocked_expires_timing"] = expires_timing
                        target_root.special_rules = sr
                    try:
                        duration_text = (
                            "until the start of your next Shooting phase"
                            if expires_timing == "OWNER_NEXT_SHOOTING_START"
                            else "until end of your opponent's next turn"
                        )
                        _log_action_for_players(
                            self,
                            attacker_player,
                            f"{ability_name}: {getattr(target_root, 'name', 'Unit')} is {state_name} {duration_text}.",
                        )
                    except Exception:
                        pass
                continue
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            candidate_ids = [str(get_entity_id(cand) or "") for cand in list(candidates) if str(get_entity_id(cand) or "").strip()]
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit to {state_name}.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "source_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_shocked",
                    "ability_name": ability_name,
                    "move_penalty": int(move_penalty),
                    "advance_penalty": int(advance_penalty),
                    "charge_penalty": int(charge_penalty),
                    "roll_threshold": int(roll_threshold) if int(roll_threshold) > 0 else 0,
                    "state_name": state_name,
                    "expires_timing": expires_timing,
                    "weapon_key": weapon_key,
                    "candidate_unit_ids": list(candidate_ids),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_staggered_oc(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot Objective Control debuff requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _is_monster_or_vehicle(unit) -> bool:
            if unit is None:
                return False
            try:
                return bool(unit.has_keyword("MONSTER") or unit.has_keyword("VEHICLE"))
            except Exception:
                pass
            try:
                return bool(unit.has_any_keyword("MONSTER") or unit.has_any_keyword("VEHICLE"))
            except Exception:
                return False

        def _target_hit_with_weapon(target, weapon_key: str) -> bool:
            if not weapon_key or not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if target_map is None:
                try:
                    target_root = target.get_attached_unit_root()
                except Exception:
                    target_root = target
                target_map = hit_models_by_target_weapon.get(target_root)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(weapon_key)
            if models:
                return True
            if weapon_key.endswith("s"):
                return bool(target_map.get(weapon_key[:-1]))
            return bool(target_map.get(f"{weapon_key}s"))

        specs = attacker_unit.unit_post_shoot_staggered_oc_specs() or []
        if not specs:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for spec in specs:
            weapon_key = str(spec.get("weapon_key", "") or "")
            if not weapon_key:
                continue
            candidates: list[Any] = []
            seen_ids: set[str] = set()
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                try:
                    target_root = target_unit.get_attached_unit_root()
                except Exception:
                    target_root = target_unit
                if target_root is None:
                    continue
                target_id = str(get_entity_id(target_root) or "").strip()
                if target_id and target_id in seen_ids:
                    continue
                if bool(spec.get("exclude_monster_vehicle", False)) and _is_monster_or_vehicle(target_root):
                    continue
                if not _target_hit_with_weapon(target_root, weapon_key):
                    continue
                if target_id:
                    seen_ids.add(target_id)
                candidates.append(target_root)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = [
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(cand)},
                )
                for cand in list(candidates)
            ]
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "Staggered").strip() or "Staggered"
            candidate_ids = [str(get_entity_id(cand) or "") for cand in list(candidates) if str(get_entity_id(cand) or "").strip()]
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit to become {str(spec.get('state_name', '') or 'staggered')}.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "source_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_staggered_oc",
                    "ability_name": ability_name,
                    "weapon_key": weapon_key,
                    "weapon_name": str(spec.get("weapon_name", "") or ""),
                    "oc_penalty": int(spec.get("oc_penalty", 0) or 0),
                    "oc_minimum": int(spec.get("oc_minimum", 1) or 1),
                    "state_name": str(spec.get("state_name", "") or "staggered"),
                    "expires_timing": str(spec.get("expires_timing", "") or "OWNER_NEXT_SHOOTING_START"),
                    "candidate_unit_ids": list(candidate_ids),
                },
            )
            self.request_decision(request)

    def _on_shooting_targets_selected_tremor_quake(
        self,
        attacking_unit=None,
        target_units=None,
        weapon_declarations=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        specs = root.unit_tremor_quake_specs() or []
        if not specs or not isinstance(weapon_declarations, list) or not weapon_declarations:
            return

        from ...utility.aura_utils import unit_within_range_of_unit

        def _normalize_weapon_key(profile) -> str:
            weapon_name = ""
            try:
                parent = getattr(profile, "parent_wargear", None)
                if parent is not None:
                    weapon_name = str(getattr(parent, "name", "") or "")
            except Exception:
                weapon_name = ""
            if not weapon_name:
                weapon_name = str(getattr(profile, "name", "") or "")
            if hasattr(root, "_normalize_keyword_phrase"):
                try:
                    return str(root._normalize_keyword_phrase(weapon_name) or "")
                except Exception:
                    return ""
            return str(weapon_name or "").strip().lower()

        def _resolve_enemy_roots() -> list[Any]:
            out: list[Any] = []
            seen: set[str] = set()
            for enemy in list(self.get_enemy_units(player) or []):
                if enemy is None:
                    continue
                try:
                    enemy_root = enemy.get_attached_unit_root()
                except Exception:
                    enemy_root = enemy
                if enemy_root is None or not enemy_root.is_alive():
                    continue
                try:
                    if not getattr(enemy_root, "deployed", True):
                        continue
                    if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                        continue
                except Exception:
                    pass
                eid = str(get_entity_id(enemy_root) or "")
                if not eid or eid in seen:
                    continue
                seen.add(eid)
                out.append(enemy_root)
            try:
                out.sort(key=lambda unit: str(get_entity_id(unit) or ""))
            except Exception:
                pass
            return out

        enemy_roots = _resolve_enemy_roots()
        if not enemy_roots:
            return
        specs_by_weapon: dict[str, list[dict]] = {}
        for spec in list(specs or []):
            weapon_key = str(spec.get("weapon_key", "") or "")
            if not weapon_key:
                continue
            specs_by_weapon.setdefault(weapon_key, []).append(spec)

        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0

        for declaration in list(weapon_declarations or []):
            if not isinstance(declaration, dict):
                continue
            profile = declaration.get("weapon_profile")
            target_unit = declaration.get("target_unit")
            if profile is None or target_unit is None:
                continue
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is None or not target_root.is_alive():
                continue
            weapon_key = _normalize_weapon_key(profile)
            if not weapon_key:
                continue
            matched_specs = list(specs_by_weapon.get(weapon_key, []) or [])
            if not matched_specs:
                continue
            for spec in matched_specs:
                try:
                    range_value = float(spec.get("range", 0) or 0.0)
                except Exception:
                    range_value = 0.0
                if range_value <= 0:
                    continue
                affected: list[Any] = []
                seen_ids: set[str] = set()
                target_id = str(get_entity_id(target_root) or "")
                if target_id:
                    seen_ids.add(target_id)
                affected.append(target_root)
                for enemy_root in list(enemy_roots):
                    if enemy_root is None or enemy_root is target_root:
                        continue
                    try:
                        if not enemy_root.has_any_keyword("INFANTRY"):
                            continue
                    except Exception:
                        continue
                    if not bool(unit_within_range_of_unit(enemy_root, target_root, range_value, use_attached_aggregate=True)):
                        continue
                    enemy_id = str(get_entity_id(enemy_root) or "")
                    if enemy_id and enemy_id in seen_ids:
                        continue
                    if enemy_id:
                        seen_ids.add(enemy_id)
                    affected.append(enemy_root)
                tested_names: list[str] = []
                for enemy_root in list(affected):
                    try:
                        enemy_root.take_battle_shock_test(current_turn)
                    except Exception:
                        pass
                    tested_names.append(str(getattr(enemy_root, "name", "Unit") or "Unit"))
                if tested_names:
                    try:
                        _log_action_for_players(
                            self,
                            player,
                            f"{str(spec.get('source', '') or 'Tremor Quake').strip() or 'Tremor Quake'}: {'; '.join(tested_names)} take Battle-shock tests.",
                        )
                    except Exception:
                        pass

    def _on_unit_shooting_resolved_harvester_of_souls(
        self,
        attacker_unit=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None:
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        pending = list(sr.get("harvester_of_souls_pending_ids", []) or [])
        if not pending:
            return
        try:
            marked_turn = int(sr.get("harvester_of_souls_turn", 0) or 0)
        except Exception:
            marked_turn = 0
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        if marked_turn and current_turn and marked_turn != current_turn:
            pending = []
        ability_name = str(sr.get("harvester_of_souls_source", "") or "Harvester of Souls").strip() or "Harvester of Souls"
        for uid in list(pending or []):
            target_unit = self._resolve_unit_by_id(uid)
            if target_unit is None or not target_unit.is_alive():
                continue
            try:
                mortal = int(get_roll("D3") or 0)
            except Exception:
                mortal = 0
            if mortal <= 0:
                continue
            root._apply_mortal_wounds_to_unit(target_unit, int(mortal), game_map=getattr(self, "map", None))
            try:
                owner = self._resolve_player_by_id(str(sr.get("harvester_of_souls_owner", "") or ""))
                if owner is not None:
                    from ...utility.event_bus import append_action
                    append_action(owner, f"{ability_name}: {getattr(target_unit, 'name', 'Unit')} suffers {int(mortal)} mortal wounds.")
            except Exception:
                pass
        for key in (
            "harvester_of_souls_pending_ids",
            "harvester_of_souls_target_id",
            "harvester_of_souls_source",
            "harvester_of_souls_owner",
            "harvester_of_souls_turn",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def _on_unit_shooting_resolved_spore_laced_shock_waves(
        self,
        attacker_unit=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None:
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        pending = list(sr.get("spore_laced_shock_waves_pending_entries", []) or [])
        if not pending:
            return
        try:
            marked_turn = int(sr.get("spore_laced_shock_waves_turn", 0) or 0)
        except Exception:
            marked_turn = 0
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        if marked_turn and current_turn and marked_turn != current_turn:
            pending = []
        owner = self._resolve_player_by_id(str(sr.get("spore_laced_shock_waves_owner", "") or ""))

        def _roll_mortal(raw_value) -> int:
            raw = str(raw_value or "").strip().lower()
            if raw == "d3":
                try:
                    return int(get_roll("D3") or 0)
                except Exception:
                    return 0
            if raw == "d6":
                try:
                    return int(get_roll("D6") or 0)
                except Exception:
                    return 0
            try:
                return int(raw_value or 0)
            except Exception:
                return 0

        from ...utility.event_bus import append_action

        for entry in list(pending or []):
            if not isinstance(entry, dict):
                continue
            source = str(entry.get("source", "") or "Spore-laced Shock Waves").strip() or "Spore-laced Shock Waves"
            mortal_raw = entry.get("mortal_wounds", "d3")
            for uid in list(entry.get("struck_ids", []) or []):
                target_unit = self._resolve_unit_by_id(str(uid or ""))
                if target_unit is None or not target_unit.is_alive():
                    continue
                mortal = _roll_mortal(mortal_raw)
                if mortal <= 0:
                    continue
                root._apply_mortal_wounds_to_unit(target_unit, int(mortal), game_map=getattr(self, "map", None))
                if owner is not None:
                    try:
                        append_action(
                            owner,
                            f"{source}: {getattr(target_unit, 'name', 'Unit')} suffers {int(mortal)} mortal wounds.",
                        )
                    except Exception:
                        pass
        for key in (
            "spore_laced_shock_waves_pending_entries",
            "spore_laced_shock_waves_owner",
            "spore_laced_shock_waves_turn",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def _on_unit_shooting_resolved_thundershock(
        self,
        attacker_unit=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None:
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        pending = list(sr.get("thundershock_pending_entries", []) or [])
        if not pending:
            return
        try:
            marked_turn = int(sr.get("thundershock_turn", 0) or 0)
        except Exception:
            marked_turn = 0
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        if marked_turn and current_turn and marked_turn != current_turn:
            pending = []
        owner = self._resolve_player_by_id(str(sr.get("thundershock_owner", "") or ""))

        def _roll_mortal(raw_value) -> int:
            raw = str(raw_value or "").strip().lower()
            if raw == "d3":
                try:
                    return int(get_roll("D3") or 0)
                except Exception:
                    return 0
            if raw == "d6":
                try:
                    return int(get_roll("D6") or 0)
                except Exception:
                    return 0
            try:
                return int(raw_value or 0)
            except Exception:
                return 0

        from ...utility.event_bus import append_action

        for entry in list(pending or []):
            if not isinstance(entry, dict):
                continue
            source = str(entry.get("source", "") or "Thundershock").strip() or "Thundershock"
            mortal_raw = entry.get("mortal_wounds", "d3")
            for uid in list(entry.get("struck_ids", []) or []):
                target_unit = self._resolve_unit_by_id(str(uid or ""))
                if target_unit is None or not target_unit.is_alive():
                    continue
                mortal = _roll_mortal(mortal_raw)
                if mortal <= 0:
                    continue
                root._apply_mortal_wounds_to_unit(target_unit, int(mortal), game_map=getattr(self, "map", None))
                if owner is not None:
                    try:
                        append_action(
                            owner,
                            f"{source}: {getattr(target_unit, 'name', 'Unit')} suffers {int(mortal)} mortal wounds.",
                        )
                    except Exception:
                        pass
        for key in (
            "thundershock_pending_entries",
            "thundershock_owner",
            "thundershock_turn",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def _on_unit_shooting_resolved_concussive_wave(
        self,
        attacker_unit=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None:
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        pending = list(sr.get("concussive_wave_pending_entries", []) or [])
        if not pending:
            return
        try:
            marked_turn = int(sr.get("concussive_wave_turn", 0) or 0)
        except Exception:
            marked_turn = 0
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        if marked_turn and current_turn and marked_turn != current_turn:
            pending = []
        owner = self._resolve_player_by_id(str(sr.get("concussive_wave_owner", "") or ""))

        def _roll_mortal(raw_value) -> int:
            raw = str(raw_value or "").strip().lower()
            if raw == "d3":
                try:
                    return int(get_roll("D3") or 0)
                except Exception:
                    return 0
            if raw == "d6":
                try:
                    return int(get_roll("D6") or 0)
                except Exception:
                    return 0
            try:
                return int(raw_value or 0)
            except Exception:
                return 0

        from ...utility.event_bus import append_action

        for entry in list(pending or []):
            if not isinstance(entry, dict):
                continue
            source = str(entry.get("source", "") or "Concussive Wave").strip() or "Concussive Wave"
            mortal_raw = entry.get("mortal_wounds", "d3")
            for uid in list(entry.get("struck_ids", []) or []):
                target_unit = self._resolve_unit_by_id(str(uid or ""))
                if target_unit is None or not target_unit.is_alive():
                    continue
                mortal = _roll_mortal(mortal_raw)
                if mortal <= 0:
                    continue
                root._apply_mortal_wounds_to_unit(target_unit, int(mortal), game_map=getattr(self, "map", None))
                if owner is not None:
                    try:
                        append_action(
                            owner,
                            f"{source}: {getattr(target_unit, 'name', 'Unit')} suffers {int(mortal)} mortal wounds.",
                        )
                    except Exception:
                        pass
        for key in (
            "concussive_wave_pending_entries",
            "concussive_wave_owner",
            "concussive_wave_turn",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def _on_unit_shooting_resolved_post_shoot_suppression(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot suppression requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _is_monster_or_vehicle(unit) -> bool:
            if bool(getattr(unit, "is_monster", False)) or bool(getattr(unit, "is_vehicle", False)):
                return True
            has_keyword = getattr(unit, "has_keyword", None)
            if callable(has_keyword):
                return bool(has_keyword("Monster") or has_keyword("Vehicle"))
            return False

        def _model_hit_target(model, target) -> bool:
            if not isinstance(hit_models_by_target, dict):
                return True
            hit_models = hit_models_by_target.get(target)
            if not hit_models:
                return False
            return model in hit_models

        def _target_weapon_hit_models(target, weapon_key: str):
            if not weapon_key or not isinstance(hit_models_by_target_weapon, dict):
                return None
            target_map = hit_models_by_target_weapon.get(target)
            if target_map is None:
                try:
                    target_root = target.get_attached_unit_root()
                except Exception:
                    target_root = target
                target_map = hit_models_by_target_weapon.get(target_root)
            if not isinstance(target_map, dict):
                return None
            models = target_map.get(weapon_key)
            if not models and weapon_key.endswith("s"):
                models = target_map.get(weapon_key[:-1])
            if not models and not weapon_key.endswith("s"):
                models = target_map.get(f"{weapon_key}s")
            return models

        def _target_hit_with_weapon(target, weapon_key: str) -> bool:
            if not weapon_key:
                return True
            return bool(_target_weapon_hit_models(target, weapon_key))

        def _model_hit_target_with_weapon(model, target, weapon_key: str) -> bool:
            if not weapon_key:
                return _model_hit_target(model, target)
            models = _target_weapon_hit_models(target, weapon_key)
            if not models:
                return False
            return model in models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_suppression_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
                weapon_key = str(spec.get("weapon_key", "") or "").strip().lower()
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if exclude_mv and _is_monster_or_vehicle(target_unit):
                        continue
                    if not _model_hit_target_with_weapon(model, target_unit, weapon_key):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        unit_specs = attacker_unit.unit_post_shoot_suppression_specs() or []
        unleash_hell_present = False
        if unit_specs:
            seen_sources = {str(spec.get("source", "") or "").strip().lower() for _m, spec, _c in triggers}
            for spec in unit_specs:
                if str(spec.get("source_key", "") or "").strip().lower() == "unleash_hell":
                    unleash_hell_present = True
                source_key = str(spec.get("source", "") or "").strip().lower()
                if source_key and source_key in seen_sources:
                    continue
                exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
                weapon_key = str(spec.get("weapon_key", "") or "").strip().lower()
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if exclude_mv and _is_monster_or_vehicle(target_unit):
                        continue
                    if not _target_hit_with_weapon(target_unit, weapon_key):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((None, spec, candidates))
                    if source_key:
                        seen_sources.add(source_key)

        if unleash_hell_present:
            sr = getattr(attacker_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["unleash_hell_consumed"] = True
            attacker_unit.special_rules = sr

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Suppressed").strip() or "Suppressed"
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET,
                f"{ability_name}: select a unit to suppress.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "model_id": get_entity_id(model) if model is not None else None,
                    "ability_name": ability_name,
                    "source_key": spec.get("source_key"),
                    "attack_types": list(spec.get("attack_types") or ("melee", "ranged")),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_afflicted(
        self,
        attacker_unit=None,
        hits_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot Afflicted requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        specs = attacker_unit.unit_post_shoot_afflicted_specs() or []
        if not specs:
            return

        for spec in specs:
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                candidates.append(target_unit)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "Afflicted").strip() or "Afflicted"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit to Afflict.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_afflicted",
                    "ability_name": ability_name,
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_no_cover(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot no-cover requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _models_include_source(models, source_model_id: str) -> bool:
            if not models:
                return False
            source_id = str(source_model_id or "").strip()
            if not source_id:
                return True
            for model in list(models or []):
                if str(maybe_entity_id(model) or "") == source_id:
                    return True
            return False

        def _target_hit_with_weapon(target, weapon_key: str, *, source_model_id: str = "") -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(weapon_key)
            if _models_include_source(models, source_model_id):
                return True
            if weapon_key.endswith("s"):
                alt_key = weapon_key[:-1]
                models = target_map.get(alt_key)
                if _models_include_source(models, source_model_id):
                    return True
            return False

        def _target_hit_by_source_model(target, source_model_id: str) -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if not isinstance(target_map, dict):
                return False
            for models in list(target_map.values() or []):
                if _models_include_source(models, source_model_id):
                    return True
            return False

        specs = attacker_unit.unit_post_shoot_no_cover_specs() or []
        if not specs:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for spec in specs:
            weapon_key = str(spec.get("weapon_key", "") or "")
            any_weapon = bool(spec.get("any_weapon", False))
            source_model_id = str(spec.get("source_model_id", "") or "").strip()
            if not weapon_key and not any_weapon:
                continue
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                if weapon_key:
                    if not _target_hit_with_weapon(target_unit, weapon_key, source_model_id=source_model_id):
                        continue
                elif source_model_id:
                    if not _target_hit_by_source_model(target_unit, source_model_id):
                        continue
                candidates.append(target_unit)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "No Cover").strip() or "No Cover"
            duration = str(spec.get("duration", "") or "phase_end").strip().lower()
            expires_phase = "SHOOTING_PHASE"
            expires_timing = "PHASE_END"
            if duration == "owner_next_shooting_start":
                expires_phase = ""
                expires_timing = "OWNER_NEXT_SHOOTING_START"
            elif duration == "turn_end":
                expires_phase = ""
                expires_timing = "TURN_END"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_no_cover",
                    "ability_name": ability_name,
                    "weapon_key": weapon_key,
                    "weapon_name": str(spec.get("weapon_name", "") or ""),
                    "source_model_id": source_model_id,
                    "expires_phase": expires_phase,
                    "expires_timing": expires_timing,
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_gsc_starfall_shells(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_army = attacker_unit.get_parent_army() if attacker_unit is not None else None
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
        if attacker_player is None:
            raise RuntimeError("Starfall Shells requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return
        gsc_mgr = getattr(attacker_army, "genestealer_cults_detachments", None) if attacker_army is not None else None
        candidate_fn = (
            getattr(gsc_mgr, "outlander_claw_starfall_shells_candidates_for_attacker", None)
            if gsc_mgr is not None
            else None
        )
        if not callable(candidate_fn):
            return

        candidates, metadata = candidate_fn(
            attacker_unit,
            hits_by_target=hits_by_target,
            hit_models_by_target_weapon=hit_models_by_target_weapon,
        )
        if not candidates:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        options = [
            DecisionOption.create(
                str(getattr(candidate, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(candidate)},
            )
            for candidate in list(candidates or [])
        ]
        if not options:
            return

        ability_name = str((metadata or {}).get("source", "") or "Starfall Shells").strip() or "Starfall Shells"
        try:
            hit_roll_penalty = int((metadata or {}).get("hit_roll_penalty", 1) or 1)
        except Exception:
            hit_roll_penalty = 1
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a unit hit by the bearer's cult sniper rifle.",
            player_id=getattr(attacker_player, "id", None),
            options=options,
            context={
                "attacker_unit_id": get_entity_id(attacker_unit),
                "ability": "gsc_starfall_shells",
                "ability_name": ability_name,
                "hit_roll_penalty": int(max(1, hit_roll_penalty)),
            },
        )
        self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_ap_bonus(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot AP bonus requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _is_monster_or_vehicle(unit) -> bool:
            if unit is None:
                return False
            try:
                return bool(unit.has_any_keyword("MONSTER")) or bool(unit.has_any_keyword("VEHICLE"))
            except Exception:
                return False

        def _normalize_weapon_key(value: str) -> str:
            normalizer = getattr(attacker_unit, "_normalize_keyword_phrase", None)
            if callable(normalizer):
                try:
                    return str(normalizer(value) or "")
                except Exception:
                    return ""
            text = str(value or "").lower()
            text = re.sub(r"[^a-z0-9]+", " ", text)
            return re.sub(r"\s+", " ", text).strip()

        def _target_hit_with_weapon_key(target, weapon_key: str) -> bool:
            normalized_key = _normalize_weapon_key(weapon_key)
            if not normalized_key or not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if target_map is None:
                try:
                    target_root = target.get_attached_unit_root()
                except Exception:
                    target_root = target
                target_map = hit_models_by_target_weapon.get(target_root)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(normalized_key)
            if not models and normalized_key.endswith("s"):
                models = target_map.get(normalized_key[:-1])
            if not models and not normalized_key.endswith("s"):
                models = target_map.get(f"{normalized_key}s")
            return bool(models)

        def _target_already_selected(unit, owner_id: str, turn: int, scope: str, phase_name: str) -> bool:
            if unit is None or not scope:
                return False
            try:
                target_root = unit.get_attached_unit_root()
            except Exception:
                target_root = unit
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                return False
            existing_scope = str(sr.get("post_shoot_ap_bonus_selected_scope", "") or "").strip().lower()
            if not existing_scope:
                return False
            if existing_scope not in ("turn", "phase"):
                return False
            selected_owner = str(sr.get("post_shoot_ap_bonus_selected_owner", "") or "")
            if selected_owner and owner_id and selected_owner != owner_id:
                return False
            selected_turn = int(sr.get("post_shoot_ap_bonus_selected_turn", 0) or 0)
            if selected_turn and turn and selected_turn != turn:
                return False
            if existing_scope == "phase":
                selected_phase = str(sr.get("post_shoot_ap_bonus_selected_phase", "") or "").strip().upper()
                if selected_phase and phase_name and selected_phase != phase_name:
                    return False
            return True

        specs = attacker_unit.unit_post_shoot_ap_bonus_specs() or []
        if not specs:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        owner_id = str(getattr(attacker_player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()

        for spec in specs:
            keyword = str(spec.get("keyword", "") or "").strip()
            attack_type = str(spec.get("attack_type", "") or "any").strip().lower() or "any"
            duration = str(spec.get("duration", "") or "phase_end").strip().lower() or "phase_end"
            if duration not in {"phase_end", "turn_end"}:
                duration = "phase_end"
            try:
                ap_bonus = int(spec.get("value", 0) or 0)
            except Exception:
                ap_bonus = 0
            limit_scope = str(spec.get("limit_scope", "") or "").strip().lower()
            exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
            weapon_key = str(spec.get("weapon_key", "") or "").strip()
            if not keyword or ap_bonus <= 0:
                continue
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                if exclude_mv and _is_monster_or_vehicle(target_unit):
                    continue
                if weapon_key and not _target_hit_with_weapon_key(target_unit, weapon_key):
                    continue
                if limit_scope and _target_already_selected(target_unit, owner_id, turn, limit_scope, phase_name):
                    continue
                candidates.append(target_unit)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "AP Bonus").strip() or "AP Bonus"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_ap_bonus",
                    "ability_name": ability_name,
                    "keyword": keyword,
                    "attack_type": attack_type,
                    "ap_bonus": int(ap_bonus),
                    "duration": duration,
                    "limit_scope": limit_scope,
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_no_overwatch(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot no-overwatch requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _target_hit_with_weapon(target, weapon_key: str) -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(weapon_key)
            if models:
                return True
            if weapon_key.endswith("s"):
                alt_key = weapon_key[:-1]
                models = target_map.get(alt_key)
                if models:
                    return True
            return False

        specs = attacker_unit.unit_post_shoot_no_overwatch_specs() or []
        if not specs:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for spec in specs:
            weapon_key = str(spec.get("weapon_key", "") or "")
            if not weapon_key:
                continue
            exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                if exclude_mv and (bool(getattr(target_unit, "is_monster", False)) or bool(getattr(target_unit, "is_vehicle", False))):
                    continue
                if not _target_hit_with_weapon(target_unit, weapon_key):
                    continue
                candidates.append(target_unit)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "No Overwatch").strip() or "No Overwatch"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_no_overwatch",
                    "ability_name": ability_name,
                    "weapon_key": weapon_key,
                    "weapon_name": str(spec.get("weapon_name", "") or ""),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_keyword_strength_bonus(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot keyword strength bonus requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target_with_weapon(model, target, weapon_key: str) -> bool:
            if not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(weapon_key)
            if not models and weapon_key.endswith("s"):
                models = target_map.get(weapon_key[:-1])
            if not models:
                return False
            return model in models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_keyword_strength_bonus_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                weapon_key = str(spec.get("weapon_key", "") or "")
                if not weapon_key:
                    continue
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _model_hit_target_with_weapon(model, target_unit, weapon_key):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "Post-shoot Strength bonus").strip() or "Post-shoot Strength bonus"
            keyword_phrase = str(spec.get("keyword_phrase", "") or "").strip()
            try:
                strength_bonus = int(spec.get("strength_bonus", 0) or 0)
            except Exception:
                strength_bonus = 0
            if strength_bonus <= 0:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a riven unit.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_keyword_strength_bonus",
                    "ability_name": ability_name,
                    "keyword_phrase": keyword_phrase,
                    "strength_bonus": int(strength_bonus),
                    "weapon_key": str(spec.get("weapon_key", "") or ""),
                    "weapon_name": str(spec.get("weapon_name", "") or ""),
                    "model_id": get_entity_id(model),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_keyword_hit_bonus(
        self,
        attacker_unit=None,
        hits_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot keyword hit bonus requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        specs = attacker_unit.unit_post_shoot_keyword_hit_bonus_specs() or []
        if not specs:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for spec in specs:
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                candidates.append(target_unit)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "Post-shoot Hit bonus").strip() or "Post-shoot Hit bonus"
            keyword = str(spec.get("keyword", "") or "").strip()
            try:
                bonus = int(spec.get("bonus", 0) or 0)
            except Exception:
                bonus = 0
            if bonus <= 0:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_keyword_hit_bonus",
                    "ability_name": ability_name,
                    "keyword_phrase": keyword,
                    "hit_bonus": int(bonus),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_keyword_wound_bonus(
        self,
        attacker_unit=None,
        hits_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot keyword wound bonus requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _matches_target_keywords(unit, target_keywords: tuple[str, ...]) -> bool:
            if not target_keywords:
                return True
            for keyword in target_keywords:
                try:
                    if unit.has_any_keyword(keyword):
                        return True
                except Exception:
                    continue
            return False

        specs = attacker_unit.unit_post_shoot_keyword_wound_bonus_specs() or []
        if not specs:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for spec in specs:
            keyword = str(spec.get("keyword", "") or "").strip()
            attack_type = str(spec.get("attack_type", "") or "any").strip().lower() or "any"
            try:
                bonus = int(spec.get("bonus", 0) or 0)
            except Exception:
                bonus = 0
            target_keywords_any = tuple(
                str(v or "").strip().lower()
                for v in list(spec.get("target_keywords_any", ()) or ())
                if str(v or "").strip()
            )
            if not keyword or bonus <= 0:
                continue
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                if not _matches_target_keywords(target_unit, target_keywords_any):
                    continue
                candidates.append(target_unit)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "Post-shoot Wound bonus").strip() or "Post-shoot Wound bonus"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_keyword_wound_bonus",
                    "ability_name": ability_name,
                    "keyword_phrase": keyword,
                    "attack_type": attack_type,
                    "wound_bonus": int(bonus),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_keyword_wound_reroll(
        self,
        attacker_unit=None,
        hits_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot keyword wound reroll requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        specs = attacker_unit.unit_post_shoot_keyword_wound_reroll_specs() or []
        if not specs:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for spec in specs:
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                candidates.append(target_unit)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "Post-shoot Wound reroll").strip() or "Post-shoot Wound reroll"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_keyword_wound_reroll",
                    "ability_name": ability_name,
                    "keyword_phrase": str(spec.get("keyword_phrase", "") or "").strip(),
                    "limit_scope": str(spec.get("limit_scope", "") or "").strip(),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_keyword_hit_reroll_ones(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot keyword hit reroll requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _normalize_weapon_key(value: str) -> str:
            normalizer = getattr(attacker_unit, "_normalize_keyword_phrase", None)
            if callable(normalizer):
                try:
                    return str(normalizer(value) or "")
                except Exception:
                    return ""
            text = str(value or "").lower()
            text = re.sub(r"[^a-z0-9]+", " ", text)
            return re.sub(r"\s+", " ", text).strip()

        def _target_hit_with_weapon_key(target, weapon_key: str) -> bool:
            normalized_key = _normalize_weapon_key(weapon_key)
            if not normalized_key or not isinstance(hit_models_by_target_weapon, dict):
                return False
            target_map = hit_models_by_target_weapon.get(target)
            if target_map is None:
                try:
                    target_root = target.get_attached_unit_root()
                except Exception:
                    target_root = target
                target_map = hit_models_by_target_weapon.get(target_root)
            if not isinstance(target_map, dict):
                return False
            models = target_map.get(normalized_key)
            if not models and normalized_key.endswith("s"):
                models = target_map.get(normalized_key[:-1])
            if not models and not normalized_key.endswith("s"):
                models = target_map.get(f"{normalized_key}s")
            return bool(models)

        specs = attacker_unit.unit_post_shoot_keyword_hit_reroll_ones_specs() or []
        if not specs:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for spec in specs:
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                weapon_key = str(spec.get("weapon_key", "") or "")
                if weapon_key and not _target_hit_with_weapon_key(target_unit, weapon_key):
                    continue
                candidates.append(target_unit)
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "Post-shoot Hit reroll").strip() or "Post-shoot Hit reroll"
            weapon_name = str(spec.get("weapon_name", "") or "").strip()
            prompt = f"{ability_name}: select a unit."
            if weapon_name:
                prompt = f"{ability_name}: select a unit hit by {weapon_name}."
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                prompt,
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_keyword_hit_reroll_ones",
                    "ability_name": ability_name,
                    "keyword_phrase": str(spec.get("keyword_phrase", "") or "").strip(),
                    "weapon_key": str(spec.get("weapon_key", "") or ""),
                    "weapon_name": weapon_name,
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_tau_advanced_scouting(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Advanced Scouting requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        owner_id = str(get_entity_id(attacker_player) or "") or str(getattr(attacker_player, "id", "") or "")
        by_target = hit_models_by_target if isinstance(hit_models_by_target, dict) else {}

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target(model, target_unit, target_root) -> bool:
            if not by_target:
                return True
            hit_models = by_target.get(target_unit)
            if hit_models is None:
                hit_models = by_target.get(target_root)
            if not hit_models:
                return False
            model_id = str(get_entity_id(model) or "")
            for hit_model in list(hit_models):
                if hit_model is model:
                    return True
                if model_id and str(get_entity_id(hit_model) or "") == model_id:
                    return True
            return False

        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_tau_advanced_scouting_specs(model) or []
            if not specs:
                continue
            model_id = str(get_entity_id(model) or "")
            if not model_id:
                continue

            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None or int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                try:
                    target_root = target_unit.get_attached_unit_root()
                except Exception:
                    target_root = target_unit
                if target_root is None:
                    continue
                if not _model_hit_target(model, target_unit, target_root):
                    continue
                sr = getattr(target_root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                marks = list(sr.get("tau_advanced_scouting_marks", []) or [])
                changed = False
                for spec in specs:
                    source = str(spec.get("source", "") or "Advanced Scouting").strip() or "Advanced Scouting"
                    keyword_phrase = str(spec.get("keyword_phrase", "") or "kroot").strip() or "kroot"
                    key = (
                        source.lower(),
                        keyword_phrase.lower(),
                        owner_id,
                        int(turn or 0),
                        model_id,
                    )
                    exists = False
                    for entry in marks:
                        if not isinstance(entry, dict):
                            continue
                        existing_key = (
                            str(entry.get("source", "") or "").strip().lower(),
                            str(entry.get("keyword_phrase", "") or "").strip().lower(),
                            str(entry.get("owner_id", "") or ""),
                            int(entry.get("turn", 0) or 0),
                            str(entry.get("source_model_id", "") or ""),
                        )
                        if existing_key == key:
                            exists = True
                            break
                    if exists:
                        continue
                    marks.append(
                        {
                            "source": source,
                            "keyword_phrase": keyword_phrase,
                            "owner_id": owner_id,
                            "turn": int(turn or 0),
                            "source_model_id": model_id,
                        }
                    )
                    changed = True
                if changed:
                    sr["tau_advanced_scouting_marks"] = marks
                    target_root.special_rules = sr

    def _on_unit_shooting_resolved_post_shoot_crit_hit_threshold(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot crit threshold requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        def _model_hit_target(model, target) -> bool:
            if not isinstance(hit_models_by_target, dict):
                return True
            hit_models = hit_models_by_target.get(target)
            if not hit_models:
                return False
            return model in hit_models

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_crit_hit_threshold_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            try:
                candidates = sorted(candidates, key=lambda u: str(maybe_entity_id(u) or ""))
            except Exception:
                candidates = list(candidates)
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            ability_name = str(spec.get("source", "") or "Post-shoot crit bonus").strip() or "Post-shoot crit bonus"
            keyword = str(spec.get("keyword", "") or "").strip()
            try:
                threshold = int(spec.get("threshold", 6) or 6)
            except Exception:
                threshold = 6
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a unit.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability": "post_shoot_crit_hit_threshold",
                    "ability_name": ability_name,
                    "keyword": keyword,
                    "threshold": int(threshold),
                    "model_id": get_entity_id(model),
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_leadership_debuff(
        self,
        attacker_unit=None,
        hits_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-shoot Leadership debuff requires an attacker player.")
        if attacker_player is not self.get_current_player():
            return

        def _is_enemy_unit(unit) -> bool:
            if unit is None:
                return False
            if unit.get_parent_army() == attacker_unit.get_parent_army():
                return False
            if not unit.is_alive():
                return False
            return True

        specs = attacker_unit.unit_post_shoot_leadership_debuff_specs() or []
        if not specs:
            return

        candidates: list[Any] = []
        for target_unit, hits in (hits_by_target or {}).items():
            if target_unit is None:
                continue
            if int(hits or 0) <= 0:
                continue
            if not _is_enemy_unit(target_unit):
                continue
            candidates.append(target_unit)

        if not candidates:
            return

        from ..decision_kinds import DECISION_CHOOSE_POST_SHOOT_LEADERSHIP_DEBUFF_TARGET

        for spec in specs:
            ability_name = (
                str(spec.get("source", "") or "Post-shoot Leadership debuff").strip() or "Post-shoot Leadership debuff"
            )
            options = []
            for cand in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"unit_id": get_entity_id(cand)},
                    )
                )
            if not options:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_POST_SHOOT_LEADERSHIP_DEBUFF_TARGET,
                f"{ability_name}: select a unit to suffer -1 to Leadership/Battle-shock tests.",
                player_id=getattr(attacker_player, "id", None),
                options=options,
                context={
                    "attacker_unit_id": get_entity_id(attacker_unit),
                    "ability_name": ability_name,
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_daemonic_poisons(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        self._maybe_trigger_daemonic_poisons(
            attacker_unit=attacker_unit,
            hits_by_target=hits_by_target,
            hit_models_by_target=hit_models_by_target,
            phase="shooting",
        )

    def _on_unit_shooting_resolved_gift_of_chaos(
        self,
        attacker_unit=None,
        hit_models_by_target_psychic=None,
        **_kwargs,
    ) -> None:
        self._maybe_trigger_gift_of_chaos(
            attacker_unit=attacker_unit,
            hit_models_by_target_psychic=hit_models_by_target_psychic,
            phase="shooting",
        )

    def _on_unit_shooting_resolved_aspect_shrine(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        root = attacker_unit.get_attached_unit_root()
        clear_fn = getattr(root, "clear_aspect_shrine_prompt_suppression", None)
        if callable(clear_fn):
            clear_fn()

    def _on_shooting_targets_selected_dark_pacts(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        get_root = getattr(attacking_unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
        else:
            root = attacking_unit
        if root is None:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        trigger_fn = getattr(root, "maybe_trigger_dark_pacts", None)
        if callable(trigger_fn):
            trigger_fn(self, phase_name=phase_name, trigger="shooting")

    def _on_shooting_targets_selected_atavistic_instigation(
        self,
        attacking_unit=None,
        target_units=None,
        weapon_declarations=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        if not isinstance(weapon_declarations, list) or not weapon_declarations:
            return

        def _normalize_weapon_key(profile) -> str:
            weapon_name = ""
            try:
                parent = getattr(profile, "parent_wargear", None)
                if parent is not None:
                    weapon_name = str(getattr(parent, "name", "") or "")
            except Exception:
                weapon_name = ""
            if not weapon_name:
                weapon_name = str(getattr(profile, "name", "") or "")
            if hasattr(root, "_normalize_keyword_phrase"):
                try:
                    return str(root._normalize_keyword_phrase(weapon_name) or "")
                except Exception:
                    return ""
            return str(weapon_name or "").strip().lower()

        model_specs: dict[str, tuple[Any, list[dict]]] = {}
        for model in list(getattr(root, "models", []) or []):
            if model is None or not getattr(model, "is_alive", False):
                continue
            specs = root.model_atavistic_instigation_specs(model) or []
            if not specs:
                continue
            mid = str(get_entity_id(model) or "")
            if not mid:
                continue
            model_specs[mid] = (model, list(specs))
        if not model_specs:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        queued_keys: set[tuple[str, str, str]] = set()
        source_unit_id = str(get_entity_id(root) or "")
        source_owner_id = str(getattr(player, "id", "") or "")
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0

        for declaration in list(weapon_declarations or []):
            if not isinstance(declaration, dict):
                continue
            profile = declaration.get("weapon_profile")
            if profile is None:
                continue
            target_unit = declaration.get("target_unit")
            if target_unit is None:
                continue
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is None or not target_root.is_alive():
                continue
            if target_root.get_parent_army() == root.get_parent_army():
                continue
            weapon_key = _normalize_weapon_key(profile)
            if not weapon_key:
                continue
            target_id = str(get_entity_id(target_root) or "")
            if not target_id:
                continue
            target_player = getattr(target_root.get_parent_army(), "player", None)
            if target_player is None:
                continue

            declaration_models = [
                model
                for model in list(declaration.get("models") or [])
                if model is not None and getattr(model, "is_alive", False)
            ]
            if declaration_models:
                source_models = declaration_models
            else:
                source_models = [entry[0] for entry in model_specs.values()]

            for model in list(source_models):
                mid = str(get_entity_id(model) or "")
                if not mid:
                    continue
                model_entry = model_specs.get(mid)
                if model_entry is None:
                    continue
                matched_specs = [
                    spec for spec in list(model_entry[1] or []) if str(spec.get("weapon_key", "") or "") == weapon_key
                ]
                if not matched_specs:
                    continue
                for spec in matched_specs:
                    queue_key = (mid, target_id, weapon_key)
                    if queue_key in queued_keys:
                        continue
                    queued_keys.add(queue_key)
                    ability_name = str(spec.get("source", "") or "Atavistic Instigation").strip() or "Atavistic Instigation"
                    try:
                        threshold = int(spec.get("stand_firm_crit_hit_threshold", 5) or 5)
                    except Exception:
                        threshold = 5
                    try:
                        duck_penalty = int(spec.get("duck_hit_roll_penalty", 1) or 1)
                    except Exception:
                        duck_penalty = 1
                    source_model_id = str(get_entity_id(model) or "")
                    options = [
                        DecisionOption.create(
                            "Stand Firm",
                            payload={
                                "target_unit_id": target_id,
                                "source_unit_id": source_unit_id,
                                "source_model_id": source_model_id,
                                "atavistic_instigation_choice": "stand_firm",
                            },
                        ),
                        DecisionOption.create(
                            "Duck for Cover",
                            payload={
                                "target_unit_id": target_id,
                                "source_unit_id": source_unit_id,
                                "source_model_id": source_model_id,
                                "atavistic_instigation_choice": "duck_for_cover",
                            },
                        ),
                    ]
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_QUARRY,
                        f"{ability_name}: choose how {getattr(target_root, 'name', 'this unit')} responds.",
                        player_id=getattr(target_player, "id", None),
                        options=options,
                        context={
                            "ability": "atavistic_instigation",
                            "ability_name": ability_name,
                            "source_unit_id": source_unit_id,
                            "source_model_id": source_model_id,
                            "source_owner_id": source_owner_id,
                            "target_unit_id": target_id,
                            "stand_firm_crit_hit_threshold": int(threshold),
                            "duck_hit_roll_penalty": int(duck_penalty),
                            "turn": int(current_turn or 0),
                        },
                    )
                    self.request_decision(request)

    def _on_shooting_targets_selected_orks_try_dat_button(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "orks_detachments", None) if army is not None else None
        build_fn = getattr(mgr, "queue_dread_mob_try_dat_button_choice", None) if mgr is not None else None
        if not callable(build_fn):
            return
        req = build_fn(root, trigger="shooting", game=self)
        if req is not None:
            self.request_decision(req)

    def _on_shooting_targets_selected_daemonic_ordnance(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            if not getattr(root, "deployed", True):
                return
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(root, "has_daemonic_ordnance", lambda: False)()):
            return

        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and sr.get("daemonic_ordnance_active"):
            exp = str(sr.get("daemonic_ordnance_expires_phase", "") or "").strip().upper()
            if not exp or exp == "SHOOTING_PHASE":
                return

        unit_id = maybe_entity_id(root)
        if not unit_id:
            return
        ability_name = "Daemonic Ordnance"
        ctx = {
            "ability": "daemonic_ordnance",
            "ability_name": ability_name,
            "phase": "Shooting phase",
            "unit": getattr(root, "name", "") or "",
            "unit_id": unit_id,
        }
        message = f"Use {ability_name} for {getattr(root, 'name', 'Unit')}?"
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="daemonic_ordnance",
            ability_name=ability_name,
            message=message,
            context=ctx,
            payload={"unit_id": unit_id},
            instance_key=f"{unit_id}:daemonic_ordnance:shooting",
        )

    def _on_shooting_targets_selected_warp_rift_firepower(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            if not getattr(root, "deployed", True):
                return
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(root, "has_warp_rift_firepower", lambda: False)()):
            return

        ability_key = "warp_rift_firepower"
        if root.has_used_unit_once_per_battle(ability_key):
            return
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and sr.get("warp_rift_firepower_active"):
            exp = str(sr.get("warp_rift_firepower_expires_phase", "") or "").strip().upper()
            if not exp or exp == "SHOOTING_PHASE":
                return

        unit_id = maybe_entity_id(root)
        if not unit_id:
            return
        ability_name = "Warp Rift Firepower"
        ctx = {
            "ability": "warp_rift_firepower",
            "ability_name": ability_name,
            "ability_key": ability_key,
            "phase": "Shooting phase",
            "unit": getattr(root, "name", "") or "",
            "unit_id": unit_id,
        }
        message = f"Use {ability_name} for {getattr(root, 'name', 'Unit')}?"
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="warp_rift_firepower",
            ability_name=ability_name,
            message=message,
            context=ctx,
            payload={"unit_id": unit_id, "ability_key": ability_key},
            instance_key=f"{unit_id}:warp_rift_firepower:shooting",
        )

    def _on_shooting_targets_selected_reorder_reality(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        get_root = getattr(attacking_unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else attacking_unit
        if root is None or not root.is_alive():
            return
        if not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        army = root.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return

        from ...utility.aura_utils import unit_within_range_of_unit

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        turn = int(getattr(self, "turn", 0) or 0)
        owner_id = str(getattr(player, "id", "") or "")
        existing_target_ids: set[str] = set()
        if bool(sr.get("reorder_reality_active")) and str(sr.get("reorder_reality_expires_phase", "") or "").strip().upper() == "SHOOTING_PHASE":
            prev_turn = int(sr.get("reorder_reality_turn", 0) or 0)
            prev_owner = str(sr.get("reorder_reality_owner", "") or "")
            same_owner = (not owner_id) or (not prev_owner) or (prev_owner == owner_id)
            if (not prev_turn or prev_turn == turn) and same_owner:
                existing_target_ids = {
                    str(v)
                    for v in list(sr.get("reorder_reality_target_ids", []) or [])
                    if str(v).strip()
                }
        target_ids = set(existing_target_ids)
        marked_any = False

        for target in list(target_units or []):
            if target is None:
                continue
            get_target_root = getattr(target, "get_attached_unit_root", None)
            target_root = get_target_root() if callable(get_target_root) else target
            if target_root is None or not target_root.is_alive():
                continue
            if not getattr(target_root, "deployed", True):
                continue
            if target_root.is_in_reserves() or target_root.is_embarked:
                continue
            if not bool(getattr(target_root, "has_reorder_reality", lambda: False)()):
                continue
            if not bool(unit_within_range_of_unit(root, target_root, 18.0, use_attached_aggregate=True)):
                continue
            target_id = str(maybe_entity_id(target_root) or "")
            if not target_id:
                continue
            target_ids.add(target_id)
            marked_any = True

        if not marked_any and not target_ids:
            return
        sr["reorder_reality_active"] = True
        sr["reorder_reality_source"] = "Reorder Reality"
        sr["reorder_reality_expires_phase"] = "SHOOTING_PHASE"
        sr["reorder_reality_turn"] = int(turn or 0)
        if owner_id:
            sr["reorder_reality_owner"] = owner_id
        sr["reorder_reality_target_ids"] = sorted(target_ids)
        root.special_rules = sr

    def _on_shooting_targets_selected_malefic_surge(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        # Attacker: Diabolic Power
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is not None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
            if mgr is not None:
                mgr.queue_malefic_surge_choice(root, trigger="shooting", game=self)
        # Defender: Unnatural Fortitude
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                troot = target.get_attached_unit_root()
            except Exception:
                troot = target
            if troot is None:
                continue
            try:
                tarmy = troot.get_parent_army()
            except Exception:
                tarmy = None
            tmgr = getattr(tarmy, "chaos_knights_detachments", None) if tarmy is not None else None
            if tmgr is not None:
                tmgr.queue_malefic_surge_choice(troot, trigger="targeted_shooting", game=self)

    def _on_shooting_targets_selected_iconoclast_dark_sacrifice(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
        queue_choice = getattr(mgr, "queue_iconoclast_dark_sacrifice_choice", None) if mgr is not None else None
        if callable(queue_choice):
            queue_choice(root, trigger="shooting", game=self)

    def _on_shooting_targets_selected_path_of_warrior(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        trigger_fn = getattr(root, "maybe_trigger_path_of_warrior", None)
        if callable(trigger_fn):
            trigger_fn(self, phase_name=phase_name, trigger="shooting")

    def _on_shooting_targets_selected_cruel_amusement(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        try:
            entries = list(root.iter_cruel_amusement_models() or [])
        except Exception:
            entries = []
        if not entries:
            return
        from ..decision_kinds import DECISION_CHOOSE_CRUEL_AMUSEMENT
        from ..decisions import DecisionOption, DecisionRequest

        pending_models = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_CRUEL_AMUSEMENT:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    mid = str(ctx.get("model_id", "") or "")
                    if mid:
                        pending_models.add(mid)
        except Exception:
            pending_models = set()

        def _sort_key(entry):
            try:
                return str(get_entity_id(entry.get("model")))
            except Exception:
                return ""

        def _max_cruel_amusement_choices_for_model(model) -> int:
            if model is None:
                return 1
            try:
                model_id = str(get_entity_id(model) or "")
            except Exception:
                model_id = ""
            parent = getattr(model, "parent_unit", None)
            try:
                source_root = parent.get_attached_unit_root() if parent is not None else None
            except Exception:
                source_root = parent
            if source_root is None:
                return 1
            try:
                members = list(source_root.get_attached_unit_members() or [])
            except Exception:
                members = [source_root]
            if not members:
                members = [source_root]
            max_choices = 1
            for member in list(members or []):
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict) or not bool(sr.get("enhancement_fanged_leer")):
                    continue
                bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
                if bearer_id and model_id and bearer_id != model_id:
                    continue
                try:
                    val = int(sr.get("enhancement_fanged_leer_select_count", 2) or 2)
                except Exception:
                    val = 2
                max_choices = max(max_choices, max(1, val))
            return max(1, min(2, int(max_choices)))

        for entry in sorted(list(entries or []), key=_sort_key):
            model = entry.get("model")
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            weapon_name = str(entry.get("weapon_name", "") or "shrieker cannon")
            ability_name = str(entry.get("source", "") or "Cruel Amusement").strip() or "Cruel Amusement"
            base_choices = (
                ("IGNORES_COVER", "Ignores Cover", "Weapon gains [IGNORES COVER] until end of phase."),
                ("PRECISION", "Precision", "Weapon gains [PRECISION] until end of phase."),
                ("SUSTAINED_HITS_3", "Sustained Hits 3", "Weapon gains [SUSTAINED HITS 3] until end of phase."),
            )
            options = [
                DecisionOption.create(
                    label,
                    payload={
                        "choice": choice_key,
                        "choices": [choice_key],
                        "summary": summary,
                    },
                )
                for choice_key, label, summary in base_choices
            ]
            if _max_cruel_amusement_choices_for_model(model) >= 2:
                for idx in range(len(base_choices)):
                    for jdx in range(idx + 1, len(base_choices)):
                        first = base_choices[idx]
                        second = base_choices[jdx]
                        combo_keys = [first[0], second[0]]
                        options.append(
                            DecisionOption.create(
                                f"{first[1]} + {second[1]}",
                                payload={
                                    "choice": "+".join(combo_keys),
                                    "choices": combo_keys,
                                    "summary": (
                                        f"Weapon gains [{first[1].upper()}] and "
                                        f"[{second[1].upper()}] until end of phase."
                                    ),
                                },
                            )
                        )
            ctx = {
                "unit_id": get_entity_id(root),
                "model_id": model_id,
                "weapon_name": weapon_name,
                "ability_name": ability_name,
                "phase_name": "SHOOTING_PHASE",
            }
            req = DecisionRequest.create(
                DECISION_CHOOSE_CRUEL_AMUSEMENT,
                f"{ability_name}: select a weapon ability.",
                player_id=getattr(player, "id", None),
                options=options,
                context=ctx,
            )
            self.request_decision(req)

    def _on_shooting_targets_selected_master_of_magicks(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        try:
            entries = list(root.iter_master_of_magicks_models() or [])
        except Exception:
            entries = []
        if not entries:
            return
        from ..decision_kinds import DECISION_CHOOSE_MASTER_OF_MAGICKS
        from ..decisions import DecisionOption, DecisionRequest

        pending_models = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_MASTER_OF_MAGICKS:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    mid = str(ctx.get("model_id", "") or "")
                    if mid:
                        pending_models.add(mid)
        except Exception:
            pending_models = set()

        def _sort_key(entry):
            try:
                return str(get_entity_id(entry.get("model")))
            except Exception:
                return ""

        for entry in sorted(list(entries or []), key=_sort_key):
            model = entry.get("model")
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            try:
                key_norm = f"master_of_magicks:{model_id}".strip().lower()
                eff = getattr(model, "_temporary_effects", None)
                if isinstance(eff, dict) and key_norm in eff:
                    exp = str((eff.get(key_norm, {}) or {}).get("expires_phase", "") or "").strip().upper()
                    if exp == "SHOOTING_PHASE":
                        continue
            except Exception:
                pass
            weapon_name = str(entry.get("weapon_name", "") or "bolt of change")
            ability_name = str(entry.get("source", "") or "Master of Magicks").strip() or "Master of Magicks"
            options = [
                DecisionOption.create(
                    "Ignores Cover",
                    payload={"choice": "IGNORES_COVER", "summary": "Weapon gains [IGNORES COVER] until end of phase."},
                ),
                DecisionOption.create(
                    "Lethal Hits",
                    payload={"choice": "LETHAL_HITS", "summary": "Weapon gains [LETHAL HITS] until end of phase."},
                ),
                DecisionOption.create(
                    "Sustained Hits D3",
                    payload={"choice": "SUSTAINED_HITS_D3", "summary": "Weapon gains [SUSTAINED HITS D3] until end of phase."},
                ),
            ]
            ctx = {
                "unit_id": get_entity_id(root),
                "model_id": model_id,
                "weapon_name": weapon_name,
                "ability_name": ability_name,
                "phase_name": "SHOOTING_PHASE",
            }
            req = DecisionRequest.create(
                DECISION_CHOOSE_MASTER_OF_MAGICKS,
                f"{ability_name}: select a weapon ability.",
                player_id=getattr(player, "id", None),
                options=options,
                context=ctx,
            )
            self.request_decision(req)

    def _on_shooting_targets_selected_technosorcerous_augmentations(
        self,
        attacking_unit=None,
        target_units=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        if army is None:
            return
        player = getattr(army, "player", None)
        if player is None or player is not self.get_current_player():
            return

        mgr = getattr(army, "necrons_detachments", None)
        eligible_fn = getattr(mgr, "technosorcerous_unit_is_eligible", None) if mgr is not None else None
        if not callable(eligible_fn) or not bool(eligible_fn(root)):
            return

        from ..decision_kinds import DECISION_CHOOSE_TECHNOSORCEROUS_AUGMENTATION
        from ..decisions import DecisionOption, DecisionRequest

        unit_id = str(get_entity_id(root) or "")
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_TECHNOSORCEROUS_AUGMENTATION:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("unit_id", "") or "") != unit_id:
                    continue
                if str(ctx.get("phase_name", "") or "").strip().upper() != phase_name:
                    continue
                return

        choice_options_fn = getattr(mgr, "technosorcerous_choice_options", None) if mgr is not None else None
        choice_options = list(choice_options_fn(root) or []) if callable(choice_options_fn) else []
        if not choice_options:
            return
        options = [
            DecisionOption.create(
                str(option.get("label", "") or str(option.get("choice", "") or "Choice")),
                payload={
                    "choice": str(option.get("choice", "") or ""),
                    "summary": str(option.get("summary", "") or ""),
                },
            )
            for option in choice_options
        ]
        req = DecisionRequest.create(
            DECISION_CHOOSE_TECHNOSORCEROUS_AUGMENTATION,
            "Technosorcerous Augmentations: select a weapon ability choice.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "unit_id": get_entity_id(root),
                "ability_name": "Technosorcerous Augmentations",
                "phase_name": "SHOOTING_PHASE",
            },
        )
        self.request_decision(req)

    def _on_shooting_targets_selected_cold_fervour(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        mgr = getattr(army, "necrons_detachments", None) if army is not None else None
        record_fn = getattr(mgr, "cold_fervour_record_targets_selected", None) if mgr is not None else None
        if callable(record_fn):
            record_fn(root, list(target_units or []), game=self)

    def _on_fight_targets_selected_cold_fervour(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        mgr = getattr(army, "necrons_detachments", None) if army is not None else None
        record_fn = getattr(mgr, "cold_fervour_record_targets_selected", None) if mgr is not None else None
        if callable(record_fn):
            record_fn(root, list(target_units or []), game=self)

    def _on_unit_shooting_resolved_cold_fervour(self, attacker_unit=None, hits_by_target=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        if root is None:
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        mgr = getattr(army, "necrons_detachments", None) if army is not None else None
        resolve_fn = getattr(mgr, "cold_fervour_register_attacks_resolved", None) if mgr is not None else None
        if not callable(resolve_fn):
            return
        target_units = list(dict(hits_by_target or {}).keys())
        activated = bool(resolve_fn(root, target_units=target_units, game=self))
        if not activated:
            return
        from ...utility.event_bus import append_action

        message = "Cold Fervour: first trigger this turn resolved, +2 Strength now applies to eligible NECRONS models until turn end."
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            append_action(player, message)

    def _on_fight_attacks_resolved_cold_fervour(self, unit=None, target_unit=None, hits_by_target=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        mgr = getattr(army, "necrons_detachments", None) if army is not None else None
        resolve_fn = getattr(mgr, "cold_fervour_register_attacks_resolved", None) if mgr is not None else None
        if not callable(resolve_fn):
            return
        targets: list = []
        if target_unit is not None:
            targets.append(target_unit)
        for candidate in list(dict(hits_by_target or {}).keys()):
            if candidate is None or candidate in targets:
                continue
            targets.append(candidate)
        activated = bool(resolve_fn(root, target_units=targets, game=self))
        if not activated:
            return
        from ...utility.event_bus import append_action

        message = "Cold Fervour: first trigger this turn resolved, +2 Strength now applies to eligible NECRONS models until turn end."
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            append_action(player, message)

    def _on_shooting_targets_selected_hand_of_asuryan(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return

        pending_models = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CONFIRM_YES_NO:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if str(ctx.get("ability", "") or "") != "hand_of_asuryan":
                        continue
                    mid = str(ctx.get("model_id", "") or "")
                    if mid:
                        pending_models.add(mid)
        except Exception:
            pending_models = set()

        def _sort_key(m):
            try:
                return str(get_entity_id(m))
            except Exception:
                return ""

        for model in sorted(list(getattr(root, "models", []) or []), key=_sort_key):
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            if getattr(model, "has_used_once_per_battle", lambda _k: False)("hand_of_asuryan"):
                continue
            specs = root.model_hand_of_asuryan_specs(model) or []
            if not specs:
                continue
            spec = specs[0]
            weapon_name = str(spec.get("weapon_name", "") or "Bloody Twins").strip() or "Bloody Twins"
            ability_name = str(spec.get("source", "") or "Hand of Asuryan").strip() or "Hand of Asuryan"
            unit_id = get_entity_id(root)
            if not unit_id or not model_id:
                continue
            ctx = {
                "ability": "hand_of_asuryan",
                "ability_name": ability_name,
                "phase": "Shooting phase",
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "model": getattr(model, "name", "") or "",
                "model_id": model_id,
                "weapon_name": weapon_name,
            }
            message = f"Use {ability_name} for {getattr(model, 'name', 'Model')}?"
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="hand_of_asuryan",
                ability_name=ability_name,
                message=message,
                context=ctx,
                payload={"unit_id": unit_id, "model_id": model_id, "weapon_name": weapon_name},
                instance_key=f"{model_id}:hand_of_asuryan",
            )
            return

    def _on_shooting_targets_selected_nova_charge(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return

        pending_models = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if str(ctx.get("ability", "") or "") != "nova_charge":
                        continue
                    mid = str(ctx.get("model_id", "") or "")
                    if mid:
                        pending_models.add(mid)
        except Exception:
            pending_models = set()

        def _model_sort_key(m):
            try:
                return str(get_entity_id(m))
            except Exception:
                return ""

        for model in sorted(list(getattr(root, "models", []) or []), key=_model_sort_key):
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            specs = list(getattr(root, "model_nova_charge_specs", lambda _m: [])(model) or [])
            if not specs:
                continue
            spec = dict(specs[0] or {})
            ability_name = str(spec.get("source", "") or "Nova Charge").strip() or "Nova Charge"
            ability_key = str(spec.get("ability_key", "") or "nova_charge").strip().lower() or "nova_charge"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(ability_key):
                continue

            ranged_weapon_names: list[str] = []
            seen: set[str] = set()
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged):
                    continue
                try:
                    if not bool(is_ranged()):
                        continue
                except Exception:
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                normalized_name = Unit._norm_wargear_name(weapon_name)
                if not normalized_name or normalized_name in seen:
                    continue
                seen.add(normalized_name)
                ranged_weapon_names.append(weapon_name)
            if not ranged_weapon_names:
                continue
            ranged_weapon_names = sorted(ranged_weapon_names, key=lambda n: Unit._norm_wargear_name(n))

            unit_id = str(get_entity_id(root) or "")
            if not unit_id or not model_id:
                continue

            options = [DecisionOption.create("None", payload={"action": "skip"})]
            for weapon_name in list(ranged_weapon_names):
                options.append(
                    DecisionOption.create(
                        weapon_name,
                        payload={
                            "unit_id": unit_id,
                            "model_id": model_id,
                            "weapon_name": weapon_name,
                            "ability_key": ability_key,
                        },
                    )
                )

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select one ranged weapon for {getattr(model, 'name', 'Model')} (or None).",
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "nova_charge",
                    "ability_name": ability_name,
                    "ability_key": ability_key,
                    "phase": "Shooting phase",
                    "unit": getattr(root, "name", "") or "",
                    "unit_id": unit_id,
                    "model": getattr(model, "name", "") or "",
                    "model_id": model_id,
                    "weapon_names": list(ranged_weapon_names),
                    "keywords": list(spec.get("keywords", []) or ["DEVASTATING WOUNDS"]),
                },
            )
            self.request_decision(request)
            return

    def _on_shooting_targets_selected_prototype_weapon_system(
        self,
        attacking_unit=None,
        target_units=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        root_fn = getattr(attacking_unit, "get_attached_unit_root", None)
        root = root_fn() if callable(root_fn) else attacking_unit
        if root is None or not root.is_alive():
            return
        get_army = getattr(root, "get_parent_army", None)
        army = get_army() if callable(get_army) else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return

        pending_models: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "prototype_weapon_system":
                    continue
                model_id = str(ctx.get("model_id", "") or "")
                if model_id:
                    pending_models.add(model_id)

        models_fn = getattr(root, "get_attached_unit_models", None)
        models = list(models_fn() or []) if callable(models_fn) else list(getattr(root, "models", []) or [])

        def _model_sort_key(model) -> str:
            return str(get_entity_id(model) or "")

        choice_key_map = {
            "LETHAL HITS": "LETHAL_HITS",
            "SUSTAINED HITS 1": "SUSTAINED_HITS_1",
        }

        for model in sorted(models, key=_model_sort_key):
            if model is None:
                continue
            alive_attr = getattr(model, "is_alive", True)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            model_id = str(get_entity_id(model) or "")
            if not model_id or model_id in pending_models:
                continue
            model_unit = getattr(model, "parent_unit", None) or root
            spec_fn = getattr(model_unit, "model_prototype_weapon_system_specs", None)
            specs = list(spec_fn(model) or []) if callable(spec_fn) else []
            if not specs:
                continue
            spec = dict(specs[0] or {})
            if bool(spec.get("requires_bearer_alive", True)) and not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            ranged_weapon_names: list[str] = []
            seen_weapon_names: set[str] = set()
            for wargear in list(getattr(model, "wargear", []) or []):
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                normalized_name = Unit._norm_wargear_name(weapon_name)
                if not normalized_name or normalized_name in seen_weapon_names:
                    continue
                seen_weapon_names.add(normalized_name)
                ranged_weapon_names.append(weapon_name)
            if not ranged_weapon_names:
                continue
            ranged_weapon_names = sorted(ranged_weapon_names, key=lambda name: Unit._norm_wargear_name(name))
            allowed_choice_keys = [
                choice_key_map[keyword]
                for keyword in list(spec.get("keyword_options", []) or [])
                if choice_key_map.get(str(keyword or "").strip().upper())
            ]
            if not allowed_choice_keys:
                continue
            unit_id = str(get_entity_id(root) or "")
            source_unit_id = str(get_entity_id(model_unit) or unit_id)
            if not unit_id:
                continue
            ability_name = str(spec.get("source", "") or "Prototype Weapon System").strip() or "Prototype Weapon System"
            ability_key = str(spec.get("ability_key", "") or "prototype_weapon_system").strip().lower() or "prototype_weapon_system"
            options = []
            for choice_key in allowed_choice_keys:
                label = "Lethal Hits" if choice_key == "LETHAL_HITS" else "Sustained Hits 1"
                options.append(
                    DecisionOption.create(
                        label,
                        payload={
                            "unit_id": unit_id,
                            "source_unit_id": source_unit_id,
                            "model_id": model_id,
                            "choice_key": choice_key,
                            "ability_key": ability_key,
                        },
                    )
                )

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a weapon mode for {getattr(model, 'name', 'Model')}.",
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "prototype_weapon_system",
                    "ability_name": ability_name,
                    "ability_key": ability_key,
                    "phase_name": "SHOOTING_PHASE",
                    "unit": getattr(root, "name", "") or "",
                    "unit_id": unit_id,
                    "source_unit_id": source_unit_id,
                    "model": getattr(model, "name", "") or "",
                    "model_id": model_id,
                    "weapon_names": list(ranged_weapon_names),
                    "allowed_choice_keys": list(allowed_choice_keys),
                    "optional": False,
                },
            )
            self.request_decision(request)
            return

    def _on_unit_shooting_resolved_prototype_weapon_system(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        root_fn = getattr(attacker_unit, "get_attached_unit_root", None)
        root = root_fn() if callable(root_fn) else attacker_unit
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        active_effects = [
            entry
            for entry in list(sr.get("enhancement_prototype_weapon_system_active_effects", []) or [])
            if isinstance(entry, dict)
        ]
        if not active_effects:
            return
        models_fn = getattr(root, "get_attached_unit_models", None)
        models = list(models_fn() or []) if callable(models_fn) else list(getattr(root, "models", []) or [])
        model_by_id: dict[str, Any] = {}
        for model in models:
            if model is None:
                continue
            entity_id = str(get_entity_id(model) or "")
            local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
            if entity_id:
                model_by_id[entity_id] = model
            if local_id:
                model_by_id[local_id] = model
        for entry in active_effects:
            model_id = str(entry.get("model_id", "") or "").strip()
            if not model_id:
                continue
            model = model_by_id.get(model_id)
            if model is None:
                continue
            effects = getattr(model, "_temporary_effects", None)
            if not isinstance(effects, dict):
                continue
            for effect_key in list(entry.get("effect_keys", []) or []):
                effect_key = str(effect_key or "").strip().lower()
                if effect_key:
                    effects.pop(effect_key, None)
        sr.pop("enhancement_prototype_weapon_system_active_effects", None)
        root.special_rules = sr

    def _on_shooting_targets_selected_shieldbreaker(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return

        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        ia_mgr = getattr(army, "imperial_agents_detachments", None) if army is not None else None
        grant_fn = getattr(ia_mgr, "apply_extremis_sanction_extra_uses", None) if ia_mgr is not None else None
        if callable(grant_fn):
            grant_fn(root)

        pending_models = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CONFIRM_YES_NO:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if str(ctx.get("ability", "") or "") != "shieldbreaker":
                        continue
                    mid = str(ctx.get("model_id", "") or "")
                    if mid:
                        pending_models.add(mid)
        except Exception:
            pending_models = set()

        def _sort_key(m):
            try:
                return str(get_entity_id(m))
            except Exception:
                return ""

        for model in sorted(list(getattr(root, "models", []) or []), key=_sort_key):
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            specs = root.model_shieldbreaker_specs(model) or []
            if not specs:
                continue
            spec = dict(specs[0] or {})
            ability_key = str(spec.get("ability_key", "") or "shieldbreaker").strip().lower()
            if not ability_key:
                ability_key = "shieldbreaker"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(ability_key):
                continue
            weapon_name = str(spec.get("weapon_name", "") or "exitus rifle").strip() or "exitus rifle"
            ability_name = str(spec.get("source", "") or "Shieldbreaker").strip() or "Shieldbreaker"
            try:
                wound_bonus = int(spec.get("wound_bonus", 1) or 1)
            except Exception:
                wound_bonus = 1
            unit_id = get_entity_id(root)
            if not unit_id or not model_id:
                continue
            ctx = {
                "ability": "shieldbreaker",
                "ability_key": ability_key,
                "ability_name": ability_name,
                "phase": "Shooting phase",
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "model": getattr(model, "name", "") or "",
                "model_id": model_id,
                "weapon_name": weapon_name,
                "wound_bonus": int(wound_bonus),
            }
            message = f"Use {ability_name} for {getattr(model, 'name', 'Model')}?"
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="shieldbreaker",
                ability_name=ability_name,
                message=message,
                context=ctx,
                payload={
                    "unit_id": unit_id,
                    "model_id": model_id,
                    "ability_key": ability_key,
                    "weapon_name": weapon_name,
                    "wound_bonus": int(wound_bonus),
                },
                instance_key=f"{model_id}:{ability_key}",
            )
            return

    def _on_shooting_targets_selected_cat_unit(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return

        specs = sorted(
            list(getattr(root, "unit_cat_unit_specs", lambda: [])() or []),
            key=lambda s: str(s.get("source", "") or "").strip().lower(),
        )
        if not specs:
            return
        spec = specs[0]
        ability_name = str(spec.get("source", "") or "CAT Unit").strip() or "CAT Unit"
        ability_key = str(spec.get("ability_key", "") or "cat_unit").strip().lower() or "cat_unit"
        if getattr(root, "has_used_unit_once_per_battle", lambda _k: False)(ability_key):
            return

        unit_id = get_entity_id(root)
        if not unit_id:
            return
        message = f"Use {ability_name} for {getattr(root, 'name', 'Unit')}?"
        ctx = {
            "ability": "cat_unit",
            "ability_key": ability_key,
            "ability_name": ability_name,
            "phase": "Shooting phase",
            "unit": getattr(root, "name", "") or "",
            "unit_id": unit_id,
        }
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="cat_unit",
            ability_name=ability_name,
            message=message,
            context=ctx,
            payload={
                "unit_id": unit_id,
                "ability_name": ability_name,
                "ability_key": ability_key,
            },
            instance_key=f"{unit_id}:{ability_key}",
        )

    def _on_shooting_targets_selected_ammo_runt(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return

        specs = sorted(
            list(getattr(root, "unit_ammo_runt_specs", lambda: [])() or []),
            key=lambda s: str(s.get("source", "") or "").strip().lower(),
        )
        if not specs:
            return
        spec = specs[0]
        ability_name = str(spec.get("source", "") or "Ammo Runt").strip() or "Ammo Runt"
        per_ammo_runt = bool(spec.get("per_ammo_runt"))

        def _count_ammo_runts(unit_obj) -> int:
            count = 0
            try:
                models = list(unit_obj._get_bodyguard_support_models() or [])
            except Exception:
                models = list(getattr(unit_obj, "models", []) or [])
            for model in models:
                if model is None or not getattr(model, "is_alive", False):
                    continue
                try:
                    for wg in list(getattr(model, "wargear", []) or []):
                        if wg is None:
                            continue
                        if Unit._norm_wargear_name(getattr(wg, "name", "")) == "ammo runt":
                            count += 1
                except Exception:
                    pass
                try:
                    for ow in list(getattr(model, "optional_wargear", []) or []):
                        if Unit._norm_wargear_name(str(ow or "")) == "ammo runt":
                            count += 1
                except Exception:
                    continue
            return max(0, int(count))

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        used = 0
        try:
            used = int(sr.get("ammo_runt_uses", 0) or 0)
        except Exception:
            used = 0

        has_explicit_total = "ammo_runt_token_total" in sr
        if per_ammo_runt:
            if has_explicit_total:
                try:
                    max_uses = max(0, int(sr.get("ammo_runt_token_total", 0) or 0))
                except Exception:
                    max_uses = 0
            else:
                max_uses = _count_ammo_runts(root)
                if max_uses <= 0:
                    # Fallback for roster contexts that omit explicit token equipment.
                    max_uses = 1
        else:
            max_uses = 1
        max_uses = max(0, int(max_uses))
        if used >= max_uses:
            return

        unit_id = get_entity_id(root)
        if not unit_id:
            return
        remaining = max(0, int(max_uses - used))
        message = f"Use {ability_name} for {getattr(root, 'name', 'Unit')}?"
        if max_uses > 1:
            suffix = "use" if remaining == 1 else "uses"
            message = f"{message} ({remaining} {suffix} remaining)"
        ctx = {
            "ability": "ammo_runt",
            "ability_name": ability_name,
            "phase": "Shooting phase",
            "unit": getattr(root, "name", "") or "",
            "unit_id": unit_id,
            "max_uses": int(max_uses),
            "remaining_uses": int(remaining),
        }
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="ammo_runt",
            ability_name=ability_name,
            message=message,
            context=ctx,
            payload={
                "unit_id": unit_id,
                "ability_name": ability_name,
                "max_uses": int(max_uses),
            },
            instance_key=f"{unit_id}:ammo_runt:{used}",
        )

    def _on_shooting_targets_selected_ratling_battlemutt(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return

        specs = sorted(
            list(getattr(root, "unit_ratling_battlemutt_specs", lambda: [])() or []),
            key=lambda s: str(s.get("source", "") or "").strip().lower(),
        )
        if not specs:
            return
        spec = specs[0]
        ability_name = str(spec.get("source", "") or "Ratling Battlemutt").strip() or "Ratling Battlemutt"
        ability_key = str(spec.get("ability_key", "") or "ratling_battlemutt").strip().lower() or "ratling_battlemutt"
        if getattr(root, "has_used_unit_once_per_battle", lambda _k: False)(ability_key):
            return

        unit_id = get_entity_id(root)
        if not unit_id:
            return
        message = f"Use {ability_name} for {getattr(root, 'name', 'Unit')}?"
        ctx = {
            "ability": "ratling_battlemutt",
            "ability_key": ability_key,
            "ability_name": ability_name,
            "phase": "Shooting phase",
            "unit": getattr(root, "name", "") or "",
            "unit_id": unit_id,
            "keywords": list(spec.get("keywords", []) or ["LETHAL HITS"]),
        }
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="ratling_battlemutt",
            ability_name=ability_name,
            message=message,
            context=ctx,
            payload={
                "unit_id": unit_id,
                "ability_key": ability_key,
                "ability_name": ability_name,
                "keywords": list(spec.get("keywords", []) or ["LETHAL HITS"]),
            },
            instance_key=f"{unit_id}:{ability_key}",
        )

    def _on_shooting_targets_selected_orks_selected_to_shoot_utilities(
        self,
        attacking_unit=None,
        target_units=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return

        roll_specs_fn = getattr(root, "unit_selected_to_shoot_roll_table_specs", None)
        if callable(roll_specs_fn):
            roll_specs = sorted(
                list(roll_specs_fn() or []),
                key=lambda spec: (
                    str(spec.get("ability_key", "") or ""),
                    str(spec.get("source", "") or "").strip().lower(),
                ),
            )
            for spec in list(roll_specs or []):
                ability_name = str(spec.get("source", "") or "Selected to shoot").strip() or "Selected to shoot"
                ability_key = (
                    str(spec.get("ability_key", "") or root._normalize_keyword_phrase(ability_name) or "selected_to_shoot")
                    .strip()
                    .lower()
                )
                if not ability_key:
                    continue
                self._queue_optional_ability_confirmation(
                    player=player,
                    ability_key=ability_key,
                    ability_name=ability_name,
                    message=f"Use {ability_name} for {getattr(root, 'name', 'Unit')}?",
                    context={
                        "ability": ability_key,
                        "ability_key": ability_key,
                        "ability_name": ability_name,
                        "phase": "Shooting phase",
                        "unit": getattr(root, "name", "") or "",
                        "unit_id": unit_id,
                    },
                    payload={
                        "unit_id": unit_id,
                        "ability_key": ability_key,
                        "ability_name": ability_name,
                    },
                    instance_key=f"{unit_id}:{ability_key}:shooting",
                )

        model_bonus_specs_fn = getattr(root, "iter_selected_to_shoot_model_ranged_bonus_specs", None)
        if not callable(model_bonus_specs_fn):
            return
        model_bonus_specs = sorted(
            list(model_bonus_specs_fn() or []),
            key=lambda spec: (
                str(spec.get("model_id", "") or ""),
                str(spec.get("ability_key", "") or ""),
                str(spec.get("source", "") or "").strip().lower(),
            ),
        )
        for spec in list(model_bonus_specs or []):
            model = spec.get("model")
            model_id = str(spec.get("model_id", "") or get_entity_id(model) or "")
            if not model_id or model is None:
                continue
            alive_attr = getattr(model, "is_alive", True)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            ability_name = str(spec.get("source", "") or "Selected to shoot").strip() or "Selected to shoot"
            ability_key = str(spec.get("ability_key", "") or "").strip().lower()
            if not ability_key:
                continue
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(ability_key):
                continue
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key=ability_key,
                ability_name=ability_name,
                message=f"Use {ability_name} for {getattr(root, 'name', 'Unit')}?",
                context={
                    "ability": ability_key,
                    "ability_key": ability_key,
                    "ability_name": ability_name,
                    "phase": "Shooting phase",
                    "unit": getattr(root, "name", "") or "",
                    "unit_id": unit_id,
                    "model": getattr(model, "name", "") or "",
                    "model_id": model_id,
                    "attacks_bonus": int(spec.get("attacks_bonus", 0) or 0),
                    "strength_bonus": int(spec.get("strength_bonus", 0) or 0),
                    "ap_bonus": int(spec.get("ap_bonus", 0) or 0),
                },
                payload={
                    "unit_id": unit_id,
                    "model_id": model_id,
                    "ability_key": ability_key,
                    "ability_name": ability_name,
                    "attacks_bonus": int(spec.get("attacks_bonus", 0) or 0),
                    "strength_bonus": int(spec.get("strength_bonus", 0) or 0),
                    "ap_bonus": int(spec.get("ap_bonus", 0) or 0),
                },
                instance_key=f"{model_id}:{ability_key}:shooting",
            )

    def _on_shooting_targets_selected_selected_to_shoot_unit_named_ranged_bonus(
        self,
        attacking_unit=None,
        target_units=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return
        specs_fn = getattr(root, "unit_selected_to_shoot_named_ranged_bonus_specs", None)
        if not callable(specs_fn):
            return
        specs = sorted(
            list(specs_fn() or []),
            key=lambda spec: (
                str(spec.get("ability_key", "") or ""),
                str(spec.get("source", "") or "").strip().lower(),
            ),
        )
        if not specs:
            return
        single_target = len(list(target_units or [])) == 1
        target_unit = target_units[0] if single_target else None
        try:
            target_root = target_unit.get_attached_unit_root() if target_unit is not None else None
        except Exception:
            target_root = target_unit
        target_unit_id = str(get_entity_id(target_root) or "") if target_root is not None else ""
        for spec in list(specs or []):
            if bool(spec.get("requires_single_target")) and not single_target:
                continue
            ability_name = str(spec.get("source", "") or "Selected to shoot").strip() or "Selected to shoot"
            ability_key = str(spec.get("ability_key", "") or "selected_to_shoot").strip().lower() or "selected_to_shoot"
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="selected_to_shoot_unit_named_ranged_bonus",
                ability_name=ability_name,
                message=f"Use {ability_name} for {getattr(root, 'name', 'Unit')}?",
                context={
                    "ability": "selected_to_shoot_unit_named_ranged_bonus",
                    "ability_key": ability_key,
                    "ability_name": ability_name,
                    "phase": "Shooting phase",
                    "unit": getattr(root, "name", "") or "",
                    "unit_id": unit_id,
                    "target_unit_id": target_unit_id,
                    "weapon_name_phrases": list(spec.get("weapon_name_phrases", []) or []),
                    "attacks_bonus": int(spec.get("attacks_bonus", 0) or 0),
                    "strength_bonus": int(spec.get("strength_bonus", 0) or 0),
                    "ap_bonus": int(spec.get("ap_bonus", 0) or 0),
                },
                payload={
                    "unit_id": unit_id,
                    "target_unit_id": target_unit_id,
                    "ability_key": ability_key,
                    "ability_name": ability_name,
                    "weapon_name_phrases": list(spec.get("weapon_name_phrases", []) or []),
                    "attacks_bonus": int(spec.get("attacks_bonus", 0) or 0),
                    "strength_bonus": int(spec.get("strength_bonus", 0) or 0),
                    "ap_bonus": int(spec.get("ap_bonus", 0) or 0),
                },
                instance_key=f"{unit_id}:{ability_key}:shooting",
            )

    def _on_shooting_targets_selected_selected_to_shoot_target_attack_keywords(
        self,
        attacking_unit=None,
        target_units=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return

        iter_specs = getattr(root, "iter_selected_to_shoot_model_target_attack_keyword_specs", None)
        if not callable(iter_specs):
            return

        game_map = getattr(self, "map", None)
        queue = getattr(self, "decision_queue", None)
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0

        def _target_sort_key(unit):
            try:
                return str(get_entity_id(unit) or "")
            except Exception:
                return str(getattr(unit, "name", "") or "")

        def _has_pending_request(*, source_unit_id: str, model_id: str) -> bool:
            if queue is None or not hasattr(queue, "list"):
                return False
            for request in list(queue.list() or []):
                if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                context = dict(getattr(request, "context", {}) or {})
                if str(context.get("ability", "") or "") != "selected_to_shoot_target_attack_keywords":
                    continue
                if str(context.get("source_unit_id", "") or "") != str(source_unit_id or ""):
                    continue
                if str(context.get("model_id", "") or "") != str(model_id or ""):
                    continue
                if int(context.get("turn", 0) or 0) != int(current_turn or 0):
                    continue
                if str(context.get("phase_name", "") or "").strip().upper() != phase_name:
                    continue
                return True
            return False

        source_unit_id = str(get_entity_id(root) or "")
        for spec in list(iter_specs() or []):
            model = spec.get("model")
            if model is None:
                continue
            alive_attr = getattr(model, "is_alive", True)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            model_id = str(spec.get("model_id", "") or get_entity_id(model) or "")
            if not model_id:
                continue
            if source_unit_id and _has_pending_request(source_unit_id=source_unit_id, model_id=model_id):
                continue
            try:
                range_value = float(spec.get("range", 0) or 0)
            except (TypeError, ValueError):
                range_value = 0.0
            if range_value <= 0:
                continue
            requires_visibility = bool(spec.get("requires_visibility", True))
            candidates: list[Any] = []
            seen_target_ids: set[str] = set()
            for target_unit in list(target_units or []):
                if target_unit is None:
                    continue
                try:
                    target_root = target_unit.get_attached_unit_root()
                except Exception:
                    target_root = target_unit
                if target_root is None:
                    continue
                target_id = str(get_entity_id(target_root) or "")
                if not target_id or target_id in seen_target_ids:
                    continue
                seen_target_ids.add(target_id)
                try:
                    if not target_root.is_alive() or not getattr(target_root, "deployed", True):
                        continue
                except Exception:
                    continue
                try:
                    if target_root.get_parent_army() is root.get_parent_army():
                        continue
                except Exception:
                    continue
                within_fn = getattr(root, "_model_within_range_of_unit", None)
                if callable(within_fn):
                    try:
                        if not bool(within_fn(model, target_root, float(range_value))):
                            continue
                    except Exception:
                        continue
                if requires_visibility:
                    can_see_fn = getattr(self, "_model_can_see_unit", None)
                    if callable(can_see_fn):
                        try:
                            if not bool(can_see_fn(model, target_root, game_map=game_map)):
                                continue
                        except Exception:
                            continue
                candidates.append(target_root)
            if not candidates:
                continue
            candidates = sorted(candidates, key=_target_sort_key)
            options = [DecisionOption.create("None", payload={"action": "skip"})]
            for target_root in list(candidates):
                options.append(
                    DecisionOption.create(
                        str(getattr(target_root, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": get_entity_id(target_root)},
                    )
                )
            ability_name = str(spec.get("source", "") or "Selected to shoot").strip() or "Selected to shoot"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select one enemy unit within {int(range_value)}\" (or None).",
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "selected_to_shoot_target_attack_keywords",
                    "ability_key": str(spec.get("ability_key", "") or "selected_to_shoot_target_attack_keywords"),
                    "ability_name": ability_name,
                    "source_unit_id": source_unit_id,
                    "unit_id": source_unit_id,
                    "model_id": model_id,
                    "range": int(range_value),
                    "requires_visibility": requires_visibility,
                    "attack_type": str(spec.get("attack_type", "") or "ranged"),
                    "keywords": list(spec.get("keywords", []) or []),
                    "candidate_unit_ids": [str(get_entity_id(target) or "") for target in list(candidates)],
                    "phase_name": phase_name,
                    "turn": int(current_turn or 0),
                    "optional": True,
                },
            )
            self.request_decision(request)

    def _on_shooting_targets_selected_sacrificial_dagger(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        root = attacking_unit.get_attached_unit_root() if hasattr(attacking_unit, "get_attached_unit_root") else attacking_unit
        if root is None or not root.is_alive():
            return
        if getattr(root, "is_in_reserves", lambda: False)() or getattr(root, "is_embarked", False):
            return
        player = root.get_parent_army().player if hasattr(root, "get_parent_army") else None
        if player is None or player is not self.get_current_player():
            return

        pending_models = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "sacrificial_dagger":
                    continue
                mid = str(ctx.get("model_id", "") or "")
                if mid:
                    pending_models.add(mid)

        for entry in sorted(
            list(root.iter_sacrificial_dagger_models() or []),
            key=lambda e: str(get_entity_id(e.get("model")) or ""),
        ):
            model = entry.get("model")
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            # Once per phase gating.
            eff = getattr(model, "_temporary_effects", None)
            if isinstance(eff, dict):
                used = eff.get("sacrificial_dagger")
                exp = str((used or {}).get("expires_phase", "") or "").strip().upper()
                if exp == "SHOOTING_PHASE":
                    continue
            ability_name = str(entry.get("source", "") or "Sacrificial Dagger").strip() or "Sacrificial Dagger"
            unit_id = get_entity_id(root)
            if not unit_id or not model_id:
                continue
            ctx = {
                "ability": "sacrificial_dagger",
                "ability_name": ability_name,
                "phase": "Shooting phase",
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "model": getattr(model, "name", "") or "",
                "model_id": model_id,
            }
            message = f"Use {ability_name} for {getattr(model, 'name', 'Model')}?"
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="sacrificial_dagger",
                ability_name=ability_name,
                message=message,
                context=ctx,
                payload={"unit_id": unit_id, "model_id": model_id},
                instance_key=f"{model_id}:sacrificial_dagger:shooting",
            )

    def _on_shooting_targets_selected_sacrificial_blessing(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        root = attacking_unit.get_attached_unit_root() if hasattr(attacking_unit, "get_attached_unit_root") else attacking_unit
        if root is None or not root.is_alive():
            return
        if getattr(root, "is_in_reserves", lambda: False)() or getattr(root, "is_embarked", False):
            return
        player = root.get_parent_army().player if hasattr(root, "get_parent_army") else None
        if player is None or player is not self.get_current_player():
            return

        pending_models = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "sacrificial_blessing":
                    continue
                mid = str(ctx.get("model_id", "") or "")
                if mid:
                    pending_models.add(mid)

        for entry in sorted(
            list(root.iter_sacrificial_blessing_models() or []),
            key=lambda e: str(get_entity_id(e.get("model")) or ""),
        ):
            model = entry.get("model")
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            unit_id = get_entity_id(root)
            if not unit_id or not model_id:
                continue
            ctx = {
                "ability": "sacrificial_blessing",
                "ability_name": str(entry.get("source", "") or "Sacrificial Blessing").strip() or "Sacrificial Blessing",
                "phase": "Shooting phase",
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "model": getattr(model, "name", "") or "",
                "model_id": model_id,
            }
            message = f"Use {ctx['ability_name']} for {getattr(model, 'name', 'Model')}?"
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="sacrificial_blessing",
                ability_name=ctx["ability_name"],
                message=message,
                context=ctx,
                payload={"unit_id": unit_id, "model_id": model_id},
                instance_key=f"{model_id}:sacrificial_blessing:shooting:{getattr(self, 'turn', 0)}",
            )

    def _on_shooting_targets_selected_twisted_sorceries(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        root = attacking_unit.get_attached_unit_root() if hasattr(attacking_unit, "get_attached_unit_root") else attacking_unit
        if root is None or not root.is_alive():
            return
        if getattr(root, "is_in_reserves", lambda: False)() or getattr(root, "is_embarked", False):
            return
        player = root.get_parent_army().player if hasattr(root, "get_parent_army") else None
        if player is None or player is not self.get_current_player():
            return

        pending_models = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "twisted_sorceries":
                    continue
                mid = str(ctx.get("model_id", "") or "")
                if mid:
                    pending_models.add(mid)

        for entry in sorted(
            list(root.iter_twisted_sorceries_models() or []),
            key=lambda e: str(get_entity_id(e.get("model")) or ""),
        ):
            model = entry.get("model")
            if model is None or not getattr(model, "is_alive", False):
                continue
            if getattr(model, "has_used_once_per_battle", lambda _k: False)("twisted_sorceries"):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            unit_id = get_entity_id(root)
            if not unit_id or not model_id:
                continue
            ctx = {
                "ability": "twisted_sorceries",
                "ability_name": str(entry.get("source", "") or "Twisted Sorceries").strip() or "Twisted Sorceries",
                "phase": "Shooting phase",
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "model": getattr(model, "name", "") or "",
                "model_id": model_id,
                "buff_key": "twisted_sorceries",
            }
            message = f"Use {ctx['ability_name']} for {getattr(model, 'name', 'Model')}?"
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="twisted_sorceries",
                ability_name=ctx["ability_name"],
                message=message,
                context=ctx,
                payload={"unit_id": unit_id, "model_id": model_id, "buff_key": "twisted_sorceries"},
                instance_key=f"{model_id}:twisted_sorceries:shooting",
            )

    def _on_shooting_targets_selected_spore_laced_shock_waves(
        self,
        attacking_unit=None,
        target_units=None,
        weapon_declarations=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        specs = root.unit_spore_laced_shock_waves_specs() or []
        if not specs:
            return
        if not isinstance(weapon_declarations, list) or not weapon_declarations:
            return

        try:
            from ...rules.nurgles_gift import NurglesGiftManager
            from ...utility.aura_utils import unit_within_range_of_unit
            from ...utility.event_bus import append_dice
        except Exception:
            return

        def _normalize_weapon_key(profile) -> str:
            weapon_name = ""
            try:
                parent = getattr(profile, "parent_wargear", None)
                if parent is not None:
                    weapon_name = str(getattr(parent, "name", "") or "")
            except Exception:
                weapon_name = ""
            if not weapon_name:
                weapon_name = str(getattr(profile, "name", "") or "")
            if hasattr(root, "_normalize_keyword_phrase"):
                try:
                    return str(root._normalize_keyword_phrase(weapon_name) or "")
                except Exception:
                    return ""
            return str(weapon_name or "").strip().lower()

        def _resolve_enemy_roots() -> list[Any]:
            out: list[Any] = []
            seen: set[str] = set()
            for enemy in list(self.get_enemy_units(player) or []):
                if enemy is None:
                    continue
                try:
                    enemy_root = enemy.get_attached_unit_root()
                except Exception:
                    enemy_root = enemy
                if enemy_root is None or not enemy_root.is_alive():
                    continue
                try:
                    if not getattr(enemy_root, "deployed", True):
                        continue
                    if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                        continue
                except Exception:
                    pass
                eid = str(get_entity_id(enemy_root) or "")
                if not eid or eid in seen:
                    continue
                seen.add(eid)
                out.append(enemy_root)
            return out

        enemy_roots = _resolve_enemy_roots()
        if not enemy_roots:
            return
        specs_by_weapon: dict[str, list[dict]] = {}
        for spec in list(specs or []):
            weapon_key = str(spec.get("weapon_key", "") or "")
            if not weapon_key:
                continue
            specs_by_weapon.setdefault(weapon_key, []).append(spec)

        pending_entries: list[dict] = []
        for declaration in list(weapon_declarations or []):
            if not isinstance(declaration, dict):
                continue
            profile = declaration.get("weapon_profile")
            if profile is None:
                continue
            target_unit = declaration.get("target_unit")
            if target_unit is None:
                continue
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is None or not target_root.is_alive():
                continue
            weapon_key = _normalize_weapon_key(profile)
            if not weapon_key:
                continue
            matched_specs = list(specs_by_weapon.get(weapon_key, []) or [])
            if not matched_specs:
                continue
            models = [m for m in list(declaration.get("models") or []) if m is not None and getattr(m, "is_alive", False)]
            trigger_count = len(models) if models else 1
            for spec in matched_specs:
                try:
                    radius = float(spec.get("range", 0) or 0)
                except Exception:
                    radius = 0.0
                if radius <= 0:
                    continue
                try:
                    threshold = int(spec.get("threshold", 0) or 0)
                except Exception:
                    threshold = 0
                if threshold <= 0:
                    continue
                try:
                    afflicted_bonus = int(spec.get("afflicted_roll_bonus", 0) or 0)
                except Exception:
                    afflicted_bonus = 0
                source = str(spec.get("source", "") or "Spore-laced Shock Waves").strip() or "Spore-laced Shock Waves"
                mortal_wounds = spec.get("mortal_wounds", "d3")
                candidates = [target_root]
                for enemy_root in list(enemy_roots):
                    if enemy_root is target_root:
                        continue
                    try:
                        if unit_within_range_of_unit(target_root, enemy_root, float(radius), use_attached_aggregate=True):
                            candidates.append(enemy_root)
                    except Exception:
                        continue
                for _idx in range(int(trigger_count)):
                    struck_ids: list[str] = []
                    for cand in list(candidates):
                        try:
                            roll = int(get_roll("D6") or 0)
                        except Exception:
                            roll = 0
                        total = int(roll)
                        if afflicted_bonus > 0:
                            try:
                                afflicted = bool(
                                    NurglesGiftManager.get_afflicted_plague_for_unit(
                                        cand,
                                        game=self,
                                        game_map=getattr(self, "map", None),
                                    )
                                    is not None
                                )
                            except Exception:
                                afflicted = False
                            if afflicted:
                                total += int(afflicted_bonus)
                        try:
                            append_dice(
                                player,
                                f"{source}: {getattr(cand, 'name', 'Unit')} roll {int(roll)}"
                                + (f" (+{int(afflicted_bonus)} afflicted)" if int(total) != int(roll) else "")
                                + f" => {int(total)} ({int(threshold)}+)",
                            )
                        except Exception:
                            pass
                        if total >= int(threshold):
                            cid = str(get_entity_id(cand) or "")
                            if cid and cid not in struck_ids:
                                struck_ids.append(cid)
                    if struck_ids:
                        pending_entries.append(
                            {
                                "target_unit_id": str(get_entity_id(target_root) or ""),
                                "struck_ids": list(struck_ids),
                                "mortal_wounds": mortal_wounds,
                                "source": source,
                            }
                        )
        if not pending_entries:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        existing = list(sr.get("spore_laced_shock_waves_pending_entries", []) or [])
        existing.extend(list(pending_entries))
        sr["spore_laced_shock_waves_pending_entries"] = existing
        sr["spore_laced_shock_waves_owner"] = str(getattr(player, "id", "") or "")
        try:
            sr["spore_laced_shock_waves_turn"] = int(getattr(self, "turn", 0) or 0)
        except Exception:
            sr["spore_laced_shock_waves_turn"] = 0
        root.special_rules = sr

    def _on_shooting_targets_selected_thundershock(
        self,
        attacking_unit=None,
        target_units=None,
        weapon_declarations=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        specs = root.unit_thundershock_specs() or []
        if not specs:
            return
        if not isinstance(weapon_declarations, list) or not weapon_declarations:
            return

        try:
            from ...utility.aura_utils import unit_within_range_of_unit
            from ...utility.event_bus import append_dice
        except Exception:
            return

        def _normalize_weapon_key(profile) -> str:
            weapon_name = ""
            try:
                parent = getattr(profile, "parent_wargear", None)
                if parent is not None:
                    weapon_name = str(getattr(parent, "name", "") or "")
            except Exception:
                weapon_name = ""
            if not weapon_name:
                weapon_name = str(getattr(profile, "name", "") or "")
            if hasattr(root, "_normalize_keyword_phrase"):
                try:
                    return str(root._normalize_keyword_phrase(weapon_name) or "")
                except Exception:
                    return ""
            return str(weapon_name or "").strip().lower()

        def _resolve_enemy_roots() -> list[Any]:
            out: list[Any] = []
            seen: set[str] = set()
            for enemy in list(self.get_enemy_units(player) or []):
                if enemy is None:
                    continue
                try:
                    enemy_root = enemy.get_attached_unit_root()
                except Exception:
                    enemy_root = enemy
                if enemy_root is None or not enemy_root.is_alive():
                    continue
                try:
                    if not getattr(enemy_root, "deployed", True):
                        continue
                    if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                        continue
                except Exception:
                    pass
                eid = str(get_entity_id(enemy_root) or "")
                if not eid or eid in seen:
                    continue
                seen.add(eid)
                out.append(enemy_root)
            try:
                out.sort(key=lambda unit: str(get_entity_id(unit) or ""))
            except Exception:
                pass
            return out

        enemy_roots = _resolve_enemy_roots()
        if not enemy_roots:
            return
        specs_by_weapon: dict[str, list[dict]] = {}
        for spec in list(specs or []):
            weapon_key = str(spec.get("weapon_key", "") or "")
            if not weapon_key:
                continue
            specs_by_weapon.setdefault(weapon_key, []).append(spec)

        pending_entries: list[dict] = []
        for declaration in list(weapon_declarations or []):
            if not isinstance(declaration, dict):
                continue
            profile = declaration.get("weapon_profile")
            if profile is None:
                continue
            target_unit = declaration.get("target_unit")
            if target_unit is None:
                continue
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is None or not target_root.is_alive():
                continue
            weapon_key = _normalize_weapon_key(profile)
            if not weapon_key:
                continue
            matched_specs = list(specs_by_weapon.get(weapon_key, []) or [])
            if not matched_specs:
                continue
            models = [m for m in list(declaration.get("models") or []) if m is not None and getattr(m, "is_alive", False)]
            trigger_count = len(models) if models else 1
            for spec in matched_specs:
                try:
                    radius = float(spec.get("range", 0) or 0)
                except Exception:
                    radius = 0.0
                if radius <= 0:
                    continue
                try:
                    threshold = int(spec.get("threshold", 0) or 0)
                except Exception:
                    threshold = 0
                if threshold <= 0:
                    continue
                source = str(spec.get("source", "") or "Thundershock").strip() or "Thundershock"
                mortal_wounds = spec.get("mortal_wounds", "d3")
                candidates = [target_root]
                for enemy_root in list(enemy_roots):
                    if enemy_root is target_root:
                        continue
                    try:
                        if unit_within_range_of_unit(target_root, enemy_root, float(radius), use_attached_aggregate=True):
                            candidates.append(enemy_root)
                    except Exception:
                        continue
                try:
                    candidates = sorted(list(candidates), key=lambda unit: str(get_entity_id(unit) or ""))
                except Exception:
                    candidates = list(candidates)
                for _idx in range(int(trigger_count)):
                    struck_ids: list[str] = []
                    for cand in list(candidates):
                        try:
                            roll = int(get_roll("D6") or 0)
                        except Exception:
                            roll = 0
                        try:
                            append_dice(
                                player,
                                f"{source}: {getattr(cand, 'name', 'Unit')} roll {int(roll)} => {int(roll)} ({int(threshold)}+)",
                            )
                        except Exception:
                            pass
                        if roll >= int(threshold):
                            cid = str(get_entity_id(cand) or "")
                            if cid and cid not in struck_ids:
                                struck_ids.append(cid)
                    if struck_ids:
                        pending_entries.append(
                            {
                                "target_unit_id": str(get_entity_id(target_root) or ""),
                                "struck_ids": list(struck_ids),
                                "mortal_wounds": mortal_wounds,
                                "source": source,
                            }
                        )
        if not pending_entries:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        existing = list(sr.get("thundershock_pending_entries", []) or [])
        existing.extend(list(pending_entries))
        sr["thundershock_pending_entries"] = existing
        sr["thundershock_owner"] = str(getattr(player, "id", "") or "")
        try:
            sr["thundershock_turn"] = int(getattr(self, "turn", 0) or 0)
        except Exception:
            sr["thundershock_turn"] = 0
        root.special_rules = sr

    def _on_shooting_targets_selected_concussive_wave(
        self,
        attacking_unit=None,
        target_units=None,
        weapon_declarations=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        specs = root.unit_concussive_wave_specs() or []
        if not specs:
            return
        if not isinstance(weapon_declarations, list) or not weapon_declarations:
            return

        try:
            from ...utility.aura_utils import unit_within_range_of_unit
            from ...utility.event_bus import append_dice
        except Exception:
            return

        def _normalize_weapon_key(profile) -> str:
            weapon_name = ""
            try:
                parent = getattr(profile, "parent_wargear", None)
                if parent is not None:
                    weapon_name = str(getattr(parent, "name", "") or "")
            except Exception:
                weapon_name = ""
            if not weapon_name:
                weapon_name = str(getattr(profile, "name", "") or "")
            if hasattr(root, "_normalize_keyword_phrase"):
                try:
                    return str(root._normalize_keyword_phrase(weapon_name) or "")
                except Exception:
                    return ""
            return str(weapon_name or "").strip().lower()

        all_roots_by_id: dict[str, Any] = {}
        for unit in list(getattr(getattr(self, "map", None), "units", []) or []):
            if unit is None:
                continue
            try:
                unit_root = unit.get_attached_unit_root()
            except Exception:
                unit_root = unit
            if unit_root is None or not unit_root.is_alive():
                continue
            try:
                if not getattr(unit_root, "deployed", True):
                    continue
                if unit_root.is_in_reserves() or unit_root.is_embarked:
                    continue
            except Exception:
                pass
            unit_id = str(get_entity_id(unit_root) or "")
            if unit_id and unit_id not in all_roots_by_id:
                all_roots_by_id[unit_id] = unit_root

        if not all_roots_by_id:
            return
        specs_by_weapon: dict[str, list[dict]] = {}
        for spec in list(specs or []):
            weapon_key = str(spec.get("weapon_key", "") or "")
            if not weapon_key:
                continue
            specs_by_weapon.setdefault(weapon_key, []).append(spec)

        pending_entries: list[dict] = []
        for declaration in list(weapon_declarations or []):
            if not isinstance(declaration, dict):
                continue
            profile = declaration.get("weapon_profile")
            if profile is None:
                continue
            target_unit = declaration.get("target_unit")
            if target_unit is None:
                continue
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is None or not target_root.is_alive():
                continue
            weapon_key = _normalize_weapon_key(profile)
            if not weapon_key:
                continue
            matched_specs = list(specs_by_weapon.get(weapon_key, []) or [])
            if not matched_specs:
                continue
            models = [m for m in list(declaration.get("models") or []) if m is not None and getattr(m, "is_alive", False)]
            trigger_count = len(models) if models else 1
            for spec in matched_specs:
                try:
                    radius = float(spec.get("range", 0) or 0)
                except Exception:
                    radius = 0.0
                if radius <= 0:
                    continue
                try:
                    threshold = int(spec.get("threshold", 0) or 0)
                except Exception:
                    threshold = 0
                if threshold <= 0:
                    continue
                source = str(spec.get("source", "") or "Concussive Wave").strip() or "Concussive Wave"
                mortal_wounds = spec.get("mortal_wounds", "d3")
                candidates = [target_root]
                for unit_id in sorted(all_roots_by_id):
                    unit_root = all_roots_by_id[unit_id]
                    if unit_root is target_root:
                        continue
                    try:
                        if unit_within_range_of_unit(target_root, unit_root, float(radius), use_attached_aggregate=True):
                            candidates.append(unit_root)
                    except Exception:
                        continue
                try:
                    candidates = sorted(list(candidates), key=lambda unit: str(get_entity_id(unit) or ""))
                except Exception:
                    candidates = list(candidates)
                for _idx in range(int(trigger_count)):
                    struck_ids: list[str] = []
                    for cand in list(candidates):
                        try:
                            roll = int(get_roll("D6") or 0)
                        except Exception:
                            roll = 0
                        try:
                            append_dice(
                                player,
                                f"{source}: {getattr(cand, 'name', 'Unit')} roll {int(roll)} => {int(roll)} ({int(threshold)}+)",
                            )
                        except Exception:
                            pass
                        if roll >= int(threshold):
                            cid = str(get_entity_id(cand) or "")
                            if cid and cid not in struck_ids:
                                struck_ids.append(cid)
                    if struck_ids:
                        pending_entries.append(
                            {
                                "target_unit_id": str(get_entity_id(target_root) or ""),
                                "struck_ids": list(struck_ids),
                                "mortal_wounds": mortal_wounds,
                                "source": source,
                            }
                        )
        if not pending_entries:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        existing = list(sr.get("concussive_wave_pending_entries", []) or [])
        existing.extend(list(pending_entries))
        sr["concussive_wave_pending_entries"] = existing
        sr["concussive_wave_owner"] = str(getattr(player, "id", "") or "")
        try:
            sr["concussive_wave_turn"] = int(getattr(self, "turn", 0) or 0)
        except Exception:
            sr["concussive_wave_turn"] = 0
        root.special_rules = sr

    def _on_shooting_targets_selected_harvester_of_souls(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not root.is_alive():
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None or player is not self.get_current_player():
            return
        specs = root.leading_harvester_of_souls_specs() or []
        if not specs:
            return
        spec = specs[0]
        leader = spec.get("leader")
        if leader is not None and not getattr(leader, "is_alive", False):
            return
        unique_targets = []
        seen = set()
        for t in list(target_units or []):
            if t is None:
                continue
            try:
                target_root = t.get_attached_unit_root()
            except Exception:
                target_root = t
            if target_root is None:
                continue
            tid = str(get_entity_id(target_root) or "")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            unique_targets.append(target_root)
        if len(unique_targets) != 1:
            return
        target_root = unique_targets[0]
        if target_root.get_parent_army() == root.get_parent_army():
            return
        if not target_root.is_alive():
            return
        ability_name = str(spec.get("source", "") or "Harvester of Souls").strip() or "Harvester of Souls"
        try:
            from ...utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return
        enemy_roots = []
        seen_enemy = set()
        for enemy in list(self.get_enemy_units(player) or []):
            if enemy is None:
                continue
            try:
                eroot = enemy.get_attached_unit_root()
            except Exception:
                eroot = enemy
            if eroot is None or not eroot.is_alive():
                continue
            try:
                if not getattr(eroot, "deployed", True):
                    continue
                if eroot.is_in_reserves() or eroot.is_embarked:
                    continue
            except Exception:
                pass
            eid = str(get_entity_id(eroot) or "")
            if not eid or eid in seen_enemy:
                continue
            seen_enemy.add(eid)
            enemy_roots.append(eroot)
        candidates = [target_root]
        for enemy_root in enemy_roots:
            if enemy_root is target_root:
                continue
            if unit_within_range_of_unit(target_root, enemy_root, 3.0):
                candidates.append(enemy_root)
        if not candidates:
            return
        try:
            owner_id = str(getattr(player, "id", "") or "")
        except Exception:
            owner_id = ""
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        marked_ids: list[str] = []
        for cand in list(candidates):
            try:
                roll = int(get_roll("D6") or 0)
            except Exception:
                roll = 0
            if roll >= 5:
                cid = str(get_entity_id(cand) or "")
                if cid and cid not in marked_ids:
                    marked_ids.append(cid)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        for key in (
            "harvester_of_souls_pending_ids",
            "harvester_of_souls_target_id",
            "harvester_of_souls_source",
            "harvester_of_souls_owner",
            "harvester_of_souls_turn",
        ):
            sr.pop(key, None)
        if marked_ids:
            sr["harvester_of_souls_pending_ids"] = list(marked_ids)
            sr["harvester_of_souls_target_id"] = str(get_entity_id(target_root) or "")
            sr["harvester_of_souls_source"] = ability_name
            sr["harvester_of_souls_owner"] = owner_id
            sr["harvester_of_souls_turn"] = int(turn or 0)
        root.special_rules = sr

    def _on_fight_unit_selected_dark_pacts(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        trigger_fn = getattr(root, "maybe_trigger_dark_pacts", None)
        if callable(trigger_fn):
            trigger_fn(self, phase_name=phase_name, trigger="fight")

    def _on_fight_unit_selected_orks_try_dat_button(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "orks_detachments", None) if army is not None else None
        build_fn = getattr(mgr, "queue_dread_mob_try_dat_button_choice", None) if mgr is not None else None
        if not callable(build_fn):
            return
        req = build_fn(root, trigger="fight", game=self)
        if req is not None:
            self.request_decision(req)

    def _on_fight_unit_selected_malefic_surge(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
        if mgr is not None:
            mgr.queue_malefic_surge_choice(root, trigger="fight", game=self)

    def _on_fight_unit_selected_iconoclast_dark_sacrifice(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
        queue_choice = getattr(mgr, "queue_iconoclast_dark_sacrifice_choice", None) if mgr is not None else None
        if callable(queue_choice):
            queue_choice(root, trigger="fight", game=self)

    def _on_fight_targets_selected_malefic_surge(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                troot = target.get_attached_unit_root()
            except Exception:
                troot = target
            if troot is None:
                continue
            try:
                tarmy = troot.get_parent_army()
            except Exception:
                tarmy = None
            tmgr = getattr(tarmy, "chaos_knights_detachments", None) if tarmy is not None else None
            if tmgr is not None:
                tmgr.queue_malefic_surge_choice(troot, trigger="targeted_fight", game=self)

    def _on_fight_unit_selected_path_of_warrior(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        trigger_fn = getattr(root, "maybe_trigger_path_of_warrior", None)
        if callable(trigger_fn):
            trigger_fn(self, phase_name=phase_name, trigger="fight")

    def _queue_accomplished_tactician_after_enemy_shooting(self, *, attacker_root=None, hits_by_target=None) -> None:
        if attacker_root is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return

        attacker_army = attacker_root.get_parent_army() if hasattr(attacker_root, "get_parent_army") else None
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
        if attacker_player is None:
            return
        if attacker_player is not self.get_current_player():
            return
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        if turn <= 0:
            return
        turn_owner = str(getattr(attacker_player, "id", "") or "")
        if not turn_owner:
            return

        from ...utility.aura_utils import model_within_range_of_unit, unit_wholly_within_range_of_unit

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        hit_roots_by_player: dict[Any, list[Any]] = {}
        seen_hits: dict[str, set[str]] = {}
        for target_unit, hits in list((hits_by_target or {}).items()):
            if target_unit is None or int(hits or 0) <= 0:
                continue
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is None:
                continue
            target_army = target_root.get_parent_army() if hasattr(target_root, "get_parent_army") else None
            target_player = getattr(target_army, "player", None) if target_army is not None else None
            if target_player is None or target_player is attacker_player:
                continue
            pid = str(getattr(target_player, "id", "") or "")
            tid = str(get_entity_id(target_root) or "")
            if not pid or not tid:
                continue
            seen = seen_hits.setdefault(pid, set())
            if tid in seen:
                continue
            seen.add(tid)
            hit_roots_by_player.setdefault(target_player, []).append(target_root)

        if not hit_roots_by_player:
            return

        queue = getattr(self, "decision_queue", None)

        def _has_pending_for_source(source_unit_id: str) -> bool:
            if queue is None or not hasattr(queue, "list"):
                return False
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "accomplished_tactician":
                    continue
                if str(ctx.get("source_unit_id", "") or "") != str(source_unit_id or ""):
                    continue
                if str(ctx.get("turn_owner", "") or "") != turn_owner:
                    continue
                if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                    continue
                return True
            return False

        for defender_player, hit_roots in list(hit_roots_by_player.items()):
            if defender_player is None:
                continue
            defender_army = defender_player.get_army()
            if defender_army is None:
                continue
            mgr = self._get_emperors_children_manager(defender_army)
            if mgr is None or not getattr(mgr, "is_rapid_evisceration", lambda: False)():
                continue

            transport_roots: list[Any] = []
            seen_transport_ids: set[str] = set()
            for unit in sorted(list(getattr(defender_army, "units", []) or []), key=_unit_sort_key):
                if unit is None:
                    continue
                try:
                    transport_root = unit.get_attached_unit_root()
                except Exception:
                    transport_root = unit
                if transport_root is None:
                    continue
                transport_id = str(get_entity_id(transport_root) or "")
                if transport_id and transport_id in seen_transport_ids:
                    continue
                if transport_id:
                    seen_transport_ids.add(transport_id)
                try:
                    if not transport_root.is_alive() or not bool(getattr(transport_root, "deployed", True)):
                        continue
                except Exception:
                    continue
                try:
                    if transport_root.is_in_reserves() or transport_root.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    is_transport = bool(getattr(transport_root, "is_transport", False))
                except Exception:
                    is_transport = False
                if not is_transport:
                    try:
                        is_transport = bool(transport_root.has_any_keyword("TRANSPORT"))
                    except Exception:
                        is_transport = False
                if not is_transport:
                    continue
                transport_roots.append(transport_root)

            if not transport_roots:
                continue

            try:
                sorted_hit_roots = sorted(list(hit_roots), key=_unit_sort_key)
            except Exception:
                sorted_hit_roots = list(hit_roots or [])

            seen_source_roots: set[str] = set()
            for unit in sorted(list(getattr(defender_army, "units", []) or []), key=_unit_sort_key):
                if unit is None:
                    continue
                try:
                    source_root = unit.get_attached_unit_root()
                except Exception:
                    source_root = unit
                if source_root is None:
                    continue
                source_root_id = str(get_entity_id(source_root) or "")
                if source_root_id and source_root_id in seen_source_roots:
                    continue
                if source_root_id:
                    seen_source_roots.add(source_root_id)
                try:
                    if not source_root.is_alive() or not bool(getattr(source_root, "deployed", True)):
                        continue
                except Exception:
                    continue
                try:
                    if source_root.is_in_reserves() or source_root.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    members = list(source_root.get_attached_unit_members() or [])
                except Exception:
                    members = [source_root]
                if not members:
                    members = [source_root]
                try:
                    members = sorted(list(members), key=_unit_sort_key)
                except Exception:
                    members = list(members)

                for source_unit in list(members or []):
                    if source_unit is None:
                        continue
                    source_sr = getattr(source_unit, "special_rules", None)
                    if not isinstance(source_sr, dict) or not source_sr.get("enhancement_accomplished_tactician"):
                        continue
                    source_unit_id = str(get_entity_id(source_unit) or "")
                    if not source_unit_id:
                        continue
                    try:
                        used_owner = str(source_sr.get("enhancement_accomplished_tactician_turn_owner", "") or "")
                        used_turn = int(source_sr.get("enhancement_accomplished_tactician_turn", 0) or 0)
                    except Exception:
                        used_owner = ""
                        used_turn = 0
                    if used_turn and used_turn == int(turn or 0) and (not used_owner or used_owner == turn_owner):
                        continue
                    if _has_pending_for_source(source_unit_id):
                        continue

                    bearer_model = getattr(source_unit, "_get_enhancement_bearer_model", lambda: None)()
                    if bearer_model is None or not bool(getattr(bearer_model, "is_alive", True)):
                        continue
                    bearer_model_id = str(get_entity_id(bearer_model) or "")
                    try:
                        select_range = int(source_sr.get("enhancement_accomplished_tactician_range", 9) or 9)
                    except Exception:
                        select_range = 9
                    try:
                        embark_range = int(source_sr.get("enhancement_accomplished_tactician_embark_range", 6) or 6)
                    except Exception:
                        embark_range = 6
                    if select_range <= 0 or embark_range <= 0:
                        continue

                    options = [DecisionOption.create("None", payload={"action": "skip"})]
                    seen_pairs: set[tuple[str, str]] = set()
                    for passenger_root in list(sorted_hit_roots or []):
                        if passenger_root is None:
                            continue
                        if passenger_root.get_parent_army() is not defender_army:
                            continue
                        try:
                            if not passenger_root.is_alive() or not bool(getattr(passenger_root, "deployed", True)):
                                continue
                        except Exception:
                            continue
                        try:
                            if passenger_root.is_in_reserves() or passenger_root.is_embarked:
                                continue
                        except Exception:
                            pass
                        if not getattr(mgr, "is_emperors_children_unit", lambda _u: False)(passenger_root):
                            continue
                        if not model_within_range_of_unit(
                            bearer_model,
                            passenger_root,
                            float(select_range),
                            use_attached_aggregate=True,
                        ):
                            continue
                        passenger_id = str(get_entity_id(passenger_root) or "")
                        if not passenger_id:
                            continue
                        for transport_root in list(transport_roots or []):
                            if transport_root is None or transport_root is passenger_root:
                                continue
                            transport_id = str(get_entity_id(transport_root) or "")
                            if not transport_id:
                                continue
                            pair_key = (passenger_id, transport_id)
                            if pair_key in seen_pairs:
                                continue
                            if not unit_wholly_within_range_of_unit(
                                transport_root,
                                passenger_root,
                                float(embark_range),
                                use_attached_aggregate=True,
                            ):
                                continue
                            try:
                                if not transport_root.can_transport(passenger_root):
                                    continue
                            except Exception:
                                continue
                            seen_pairs.add(pair_key)
                            options.append(
                                DecisionOption.create(
                                    f"{getattr(passenger_root, 'name', 'Unit')} -> {getattr(transport_root, 'name', 'Transport')}",
                                    payload={
                                        "target_unit_id": passenger_id,
                                        "transport_unit_id": transport_id,
                                    },
                                )
                            )

                    if len(options) <= 1:
                        continue

                    request = DecisionRequest.create(
                        DECISION_CHOOSE_QUARRY,
                        "Accomplished Tactician: select a hit friendly unit and transport (or None).",
                        player_id=getattr(defender_player, "id", None),
                        options=options,
                        context={
                            "ability": "accomplished_tactician",
                            "ability_name": "Accomplished Tactician",
                            "phase": "Opponent Shooting phase",
                            "optional": True,
                            "source_unit_id": source_unit_id,
                            "unit_id": source_unit_id,
                            "model_id": bearer_model_id,
                            "range": int(select_range),
                            "embark_range": int(embark_range),
                            "turn_owner": turn_owner,
                            "turn": int(turn or 0),
                        },
                    )
                    self.request_decision(request)

    def _on_unit_shooting_resolved_emperors_children(self, attacker_unit=None, hits_by_target=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
        if root is None:
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        mgr = self._get_emperors_children_manager(army)
        if mgr is not None and mgr.resolve_pending_favoured_champions(root, game=self):
            from ...utility.event_bus import append_action

            message = f"{INTERNAL_RIVALRIES_NAME}: {getattr(root, 'name', 'Unit')} are now Favoured Champions."
            for player in list(getattr(self, "players", []) or []):
                if player is None:
                    continue
                append_action(player, message)
            if getattr(self, "event_system", None) is not None:
                self.event_system.publish(
                    "emperors_children_favoured_champions_updated",
                    game=self,
                    manager=mgr,
                    unit=root,
                )

        self._queue_accomplished_tactician_after_enemy_shooting(
            attacker_root=root,
            hits_by_target=hits_by_target,
        )

    def _queue_dark_blessings_for_targets(self, *, target_units=None) -> None:
        if not target_units:
            return
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if phase_name not in ("SHOOTING_PHASE", "FIGHT_PHASE"):
            return
        seen_instance: set[str] = set()
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            if target_root is None:
                continue
            try:
                members = list(target_root.get_attached_unit_members() or [])
            except Exception:
                members = [target_root]
            if not members:
                members = [target_root]
            try:
                members = sorted(members, key=lambda u: str(get_entity_id(u)))
            except Exception:
                members = list(members)
            for member in members:
                if member is None:
                    continue
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict) or not sr.get("enhancement_dark_blessings"):
                    continue
                bearer = getattr(member, "_get_enhancement_bearer_model", lambda: None)()
                if bearer is None or not bool(getattr(bearer, "is_alive", True)):
                    continue
                once_key = str(sr.get("enhancement_dark_blessings_once_key", "") or "dark_blessings").strip().lower()
                if getattr(bearer, "has_used_once_per_battle", lambda _k: False)(once_key):
                    continue
                try:
                    army = member.get_parent_army()
                except Exception:
                    army = None
                ec_mgr = self._get_emperors_children_manager(army)
                if ec_mgr is None or not getattr(ec_mgr, "is_carnival_of_excess", lambda: False)():
                    continue
                player = getattr(army, "player", None) if army is not None else None
                if player is None:
                    continue
                unit_id = str(get_entity_id(member) or "")
                model_id = str(get_entity_id(bearer) or "")
                if not unit_id or not model_id:
                    continue
                instance_key = f"{model_id}:{once_key}:{phase_name}"
                if instance_key in seen_instance:
                    continue
                seen_instance.add(instance_key)
                invuln = int(sr.get("enhancement_dark_blessings_invulnerable_save", 3) or 3)
                message = f"Use Dark Blessings for {getattr(bearer, 'name', 'Model')}?"
                self._queue_optional_ability_confirmation(
                    player=player,
                    ability_key="start_any_phase_invulnerable_save",
                    ability_name="Dark Blessings",
                    message=message,
                    context={
                        "ability_name": "Dark Blessings",
                        "phase": phase_name.replace("_", " ").title(),
                        "unit": getattr(member, "name", "") or "",
                        "unit_id": unit_id,
                        "model": getattr(bearer, "name", "") or "",
                        "model_id": model_id,
                        "buff_key": once_key,
                        "invuln": int(invuln),
                    },
                    payload={
                        "unit_id": unit_id,
                        "model_id": model_id,
                        "buff_key": once_key,
                        "invuln": int(invuln),
                    },
                    instance_key=instance_key,
                )

    def _queue_iron_resolve_for_targets(self, *, target_units=None, attacking_unit=None, trigger_action: str = "") -> None:
        if not target_units:
            return
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if phase_name not in ("SHOOTING_PHASE", "FIGHT_PHASE"):
            return
        try:
            attacker_root = attacking_unit.get_attached_unit_root() if attacking_unit is not None else None
        except Exception:
            attacker_root = attacking_unit
        attacker_unit_id = str(get_entity_id(attacker_root) or "") if attacker_root is not None else ""
        action_key = str(trigger_action or "").strip().lower()
        if action_key not in {"shoot", "fight"}:
            action_key = "shoot" if phase_name == "SHOOTING_PHASE" else "fight"
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        seen_targets: set[str] = set()
        seen_instance: set[str] = set()
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            if target_root is None:
                continue
            target_root_id = str(get_entity_id(target_root) or "")
            if not target_root_id or target_root_id in seen_targets:
                continue
            seen_targets.add(target_root_id)
            if not bool(getattr(target_root, "is_alive", lambda: False)()):
                continue
            if not bool(getattr(target_root, "deployed", True)):
                continue
            try:
                if target_root.is_in_reserves() or target_root.is_embarked:
                    continue
            except Exception:
                pass

            _root, source_member, source_sr = self._attached_member_with_enhancement_flag(
                target_root,
                "enhancement_iron_resolve",
            )
            if source_member is None or not isinstance(source_sr, dict):
                continue
            bearer = getattr(source_member, "_get_enhancement_bearer_model", lambda: None)()
            if bearer is None or not bool(getattr(bearer, "is_alive", True)):
                continue
            once_key = str(source_sr.get("enhancement_iron_resolve_once_key", "iron_resolve") or "iron_resolve").strip().lower()
            if target_root.has_used_unit_once_per_battle(once_key):
                continue
            try:
                fnp_value = int(source_sr.get("enhancement_iron_resolve_unit_fnp", 5) or 5)
            except Exception:
                fnp_value = 5
            if fnp_value <= 0:
                continue
            army = target_root.get_parent_army() if hasattr(target_root, "get_parent_army") else None
            player = getattr(army, "player", None) if army is not None else None
            if player is None:
                continue
            unit_id = str(get_entity_id(target_root) or "")
            source_member_unit_id = str(get_entity_id(source_member) or "")
            model_id = str(get_entity_id(bearer) or "")
            if not unit_id or not source_member_unit_id or not model_id:
                continue
            ability_name = str(source_sr.get("enhancement_iron_resolve_source", "Iron Resolve") or "Iron Resolve").strip()
            if not ability_name:
                ability_name = "Iron Resolve"
            instance_key = ":".join(
                [
                    unit_id,
                    once_key,
                    phase_name,
                    str(int(turn or 0)),
                    str(getattr(player, "id", "") or ""),
                    action_key,
                    attacker_unit_id,
                ]
            )
            if instance_key in seen_instance:
                continue
            seen_instance.add(instance_key)
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="start_any_phase_fnp",
                ability_name=ability_name,
                message=f"Use {ability_name} for {getattr(target_root, 'name', 'Unit')} after being selected as a target?",
                context={
                    "ability_name": ability_name,
                    "phase": phase_name.replace("_", " ").title(),
                    "unit": getattr(target_root, "name", "") or "",
                    "unit_id": unit_id,
                    "source_unit_id": unit_id,
                    "source_member_unit_id": source_member_unit_id,
                    "model": getattr(bearer, "name", "") or "",
                    "model_id": model_id,
                    "ability_key": once_key,
                    "fnp_value": int(fnp_value),
                    "trigger_action": action_key,
                    "attacker_unit_id": attacker_unit_id,
                    "turn": int(turn or 0),
                },
                payload={
                    "unit_id": unit_id,
                    "ability_key": once_key,
                    "fnp_value": int(fnp_value),
                    "source_member_unit_id": source_member_unit_id,
                    "attacker_unit_id": attacker_unit_id,
                },
                instance_key=instance_key,
            )

    def _on_shooting_targets_selected_iron_resolve(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        self._queue_iron_resolve_for_targets(
            target_units=target_units,
            attacking_unit=attacking_unit,
            trigger_action="shoot",
        )

    def _on_fight_targets_selected_iron_resolve(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_fight_phase():
            return
        self._queue_iron_resolve_for_targets(
            target_units=target_units,
            attacking_unit=attacking_unit,
            trigger_action="fight",
        )

    def _on_shooting_targets_selected_emperors_children(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        self._queue_dark_blessings_for_targets(target_units=target_units)

    def _on_fight_targets_selected_emperors_children(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        self._queue_dark_blessings_for_targets(target_units=target_units)

    def _on_fight_attacks_resolved_emperors_children(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in list(members or []):
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not sr.get("enhancement_possessed_blade_fight_active"):
                continue
            for key in (
                "enhancement_possessed_blade_fight_active",
                "enhancement_possessed_blade_fight_turn",
                "enhancement_possessed_blade_fight_owner",
                "enhancement_possessed_blade_fight_phase",
                "enhancement_possessed_blade_active_weapon_name",
                "enhancement_possessed_blade_active_model_id",
                "enhancement_possessed_blade_source",
            ):
                sr.pop(key, None)
            member.special_rules = sr
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        mgr = self._get_emperors_children_manager(army)
        if mgr is None:
            return
        if not mgr.resolve_pending_favoured_champions(root, game=self):
            return
        from ...utility.event_bus import append_action

        message = f"{INTERNAL_RIVALRIES_NAME}: {getattr(root, 'name', 'Unit')} are now Favoured Champions."
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            append_action(player, message)
        if getattr(self, "event_system", None) is not None:
            self.event_system.publish(
                "emperors_children_favoured_champions_updated",
                game=self,
                manager=mgr,
                unit=root,
            )

    def _on_fight_unit_selected_emperors_children(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        try:
            members = sorted(members, key=lambda u: str(get_entity_id(u)))
        except Exception:
            members = list(members)
        for member in members:
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_possessed_blade"):
                continue
            weapon_name = str(sr.get("enhancement_possessed_blade_weapon_name", "") or "").strip()
            if not weapon_name:
                continue
            bearer = getattr(member, "_get_enhancement_bearer_model", lambda: None)()
            if bearer is None or not bool(getattr(bearer, "is_alive", True)):
                continue
            if sr.get("enhancement_possessed_blade_fight_active"):
                continue
            try:
                army = member.get_parent_army()
            except Exception:
                army = None
            ec_mgr = self._get_emperors_children_manager(army)
            if ec_mgr is None or not getattr(ec_mgr, "is_carnival_of_excess", lambda: False)():
                continue
            player = getattr(army, "player", None) if army is not None else None
            if player is None:
                continue
            unit_id = str(get_entity_id(member) or "")
            model_id = str(get_entity_id(bearer) or "")
            if not unit_id or not model_id:
                continue
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="possessed_blade_fight",
                ability_name="Possessed Blade",
                message=f"Use Possessed Blade for {getattr(bearer, 'name', 'Model')}?",
                context={
                    "ability_name": "Possessed Blade",
                    "phase": "Fight phase",
                    "unit": getattr(member, "name", "") or "",
                    "unit_id": unit_id,
                    "model": getattr(bearer, "name", "") or "",
                    "model_id": model_id,
                    "weapon_name": weapon_name,
                },
                payload={
                    "unit_id": unit_id,
                    "model_id": model_id,
                    "weapon_name": weapon_name,
                },
                instance_key=f"{model_id}:possessed_blade:{int(getattr(self, 'turn', 0) or 0)}",
            )

        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "emperors_children_detachments", None) if army is not None else None
        if mgr is None or not getattr(mgr, "sensational_performance_applies", lambda _u: False)(unit):
            return
        if not bool(getattr(getattr(unit, "round_state", None), "charged_this_round", False)):
            return
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if sr.get("sensational_performance_active"):
            return

        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return
        unit_id = maybe_entity_id(unit)
        ctx = {
            "ability_name": "Sensational Performance",
            "phase": "Fight phase",
            "unit": getattr(unit, "name", ""),
            "unit_id": unit_id,
        }
        message = f"Use Sensational Performance for {getattr(unit, 'name', 'Unit')}?"
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="sensational_performance",
            ability_name="Sensational Performance",
            message=message,
            context=ctx,
            payload={"unit_id": unit_id},
            instance_key=str(unit_id or ""),
        )

    def _on_fight_unit_selected_daemonic_patrons(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        specs = root.unit_fight_selected_daemonic_patrons_specs() or []
        if not specs:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if sr.get("daemonic_patrons_active"):
            return
        try:
            specs = sorted(specs, key=lambda s: str((s or {}).get("source", "") or ""))
        except Exception:
            specs = list(specs)
        spec = specs[0] if specs else {}
        try:
            threshold = int((spec or {}).get("crit_wound_threshold", 3) or 3)
        except Exception:
            threshold = 3
        if threshold < 2 or threshold > 6:
            threshold = 3
        source = str((spec or {}).get("source", "") or "Daemonic Patrons").strip() or "Daemonic Patrons"
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return
        unit_id = maybe_entity_id(root)
        if not unit_id:
            return
        ctx = {
            "ability_name": source,
            "phase": "Fight phase",
            "unit": getattr(root, "name", ""),
            "unit_id": unit_id,
            "crit_wound_threshold": int(threshold),
        }
        message = f"Call upon {source} for {getattr(root, 'name', 'Unit')}?"
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="daemonic_patrons",
            ability_name=source,
            message=message,
            context=ctx,
            payload={
                "unit_id": unit_id,
                "crit_wound_threshold": int(threshold),
                "ability_name": source,
            },
            instance_key=str(unit_id or ""),
        )

    def _on_fight_unit_selected_plasmacyte(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        root_getter = getattr(unit, "get_attached_unit_root", None)
        root = root_getter() if callable(root_getter) else unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        army_getter = getattr(root, "get_parent_army", None)
        army = army_getter() if callable(army_getter) else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return
        if selecting_player is not None and selecting_player is not player:
            return
        specs = sorted(
            list(getattr(root, "unit_plasmacyte_specs", lambda: [])() or []),
            key=lambda s: str(s.get("source", "") or "").strip().lower(),
        )
        if not specs:
            return
        spec = specs[0]
        ability_name = str(spec.get("source", "") or "Plasmacyte").strip() or "Plasmacyte"
        per_plasmacyte = bool(spec.get("per_plasmacyte"))

        def _count_plasmacytes(unit_obj) -> int:
            count = 0
            models_getter = getattr(unit_obj, "_get_bodyguard_support_models", None)
            models = list(models_getter() or []) if callable(models_getter) else list(getattr(unit_obj, "models", []) or [])
            for model in models:
                if model is None or not getattr(model, "is_alive", False):
                    continue
                model_name = Unit._norm_wargear_name(getattr(model, "name", ""))
                if "plasmacyte" in model_name:
                    count += 1
                for wg in list(getattr(model, "wargear", []) or []):
                    if wg is None:
                        continue
                    if Unit._norm_wargear_name(getattr(wg, "name", "")) == "plasmacyte":
                        count += 1
                for ow in list(getattr(model, "optional_wargear", []) or []):
                    if Unit._norm_wargear_name(str(ow or "")) == "plasmacyte":
                        count += 1
            return max(0, int(count))

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if bool(sr.get("plasmacyte_active")):
            exp = str(sr.get("plasmacyte_expires_phase", "") or "").strip().upper()
            if not exp or exp == "FIGHT_PHASE":
                return
        try:
            used = int(sr.get("plasmacyte_uses", 0) or 0)
        except (TypeError, ValueError):
            used = 0
        has_explicit_total = "plasmacyte_token_total" in sr
        if per_plasmacyte:
            if has_explicit_total:
                try:
                    max_uses = max(0, int(sr.get("plasmacyte_token_total", 0) or 0))
                except (TypeError, ValueError):
                    max_uses = 0
            else:
                max_uses = _count_plasmacytes(root)
                if max_uses <= 0:
                    # Fallback for roster contexts that omit explicit token equipment.
                    max_uses = 1
        else:
            max_uses = 1
        max_uses = max(0, int(max_uses))
        if used >= max_uses:
            return

        unit_id = get_entity_id(root)
        if not unit_id:
            return
        remaining = max(0, int(max_uses - used))
        message = f"Use {ability_name} for {getattr(root, 'name', 'Unit')}?"
        if max_uses > 1:
            suffix = "use" if remaining == 1 else "uses"
            message = f"{message} ({remaining} {suffix} remaining)"
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="plasmacyte",
            ability_name=ability_name,
            message=message,
            context={
                "ability": "plasmacyte",
                "ability_name": ability_name,
                "phase": "Fight phase",
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "max_uses": int(max_uses),
                "remaining_uses": int(remaining),
            },
            payload={
                "unit_id": unit_id,
                "ability_name": ability_name,
                "max_uses": int(max_uses),
            },
            instance_key=f"{unit_id}:plasmacyte:{used}",
        )

    def _on_fight_unit_selected_biological_warfare(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        root_getter = getattr(unit, "get_attached_unit_root", None)
        root = root_getter() if callable(root_getter) else unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        army_getter = getattr(root, "get_parent_army", None)
        army = army_getter() if callable(army_getter) else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return
        if selecting_player is not None and selecting_player is not player:
            return

        pending_keys: set[tuple[str, str]] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "biological_warfare":
                    continue
                model_id = str(ctx.get("model_id", "") or "")
                buff_key = str(ctx.get("buff_key", "") or "")
                if model_id and buff_key:
                    pending_keys.add((model_id, buff_key))

        members_getter = getattr(root, "get_attached_unit_members", None)
        members = list(members_getter() or []) if callable(members_getter) else [root]
        if not members:
            members = [root]
        unit_id = get_entity_id(root)
        if not unit_id:
            return
        for member in sorted(members, key=lambda entry: str(get_entity_id(entry) or "")):
            if member is None:
                continue
            for model in sorted(list(getattr(member, "models", []) or []), key=lambda entry: str(get_entity_id(entry) or "")):
                if model is None or not bool(getattr(model, "is_alive", False)):
                    continue
                model_id = str(get_entity_id(model) or "")
                if not model_id:
                    continue
                specs = list(
                    getattr(member, "model_fight_selected_weapon_attacks_damage_bonus_specs", lambda _m: [])(model) or []
                )
                for spec in specs:
                    buff_key = str(spec.get("buff_key", "") or "").strip().lower()
                    if not buff_key or (model_id, buff_key) in pending_keys:
                        continue
                    if bool(getattr(model, "has_used_once_per_battle", lambda _k: False)(buff_key)):
                        continue
                    ability_name = str(spec.get("source", "") or "Biological Warfare").strip() or "Biological Warfare"
                    weapon_name = str(spec.get("weapon_name", "") or "").strip()
                    message = f"Use {ability_name} for {getattr(model, 'name', 'Model')}?"
                    ctx = {
                        "ability": "biological_warfare",
                        "ability_name": ability_name,
                        "phase": "Fight phase",
                        "unit": getattr(root, "name", "") or "",
                        "unit_id": unit_id,
                        "model": getattr(model, "name", "") or "",
                        "model_id": model_id,
                        "weapon_name": weapon_name,
                        "attacks_bonus": int(spec.get("attacks_bonus", 0) or 0),
                        "damage_bonus": int(spec.get("damage_bonus", 0) or 0),
                        "buff_key": buff_key,
                    }
                    self._queue_optional_ability_confirmation(
                        player=player,
                        ability_key="biological_warfare",
                        ability_name=ability_name,
                        message=message,
                        context=ctx,
                        payload={
                            "unit_id": unit_id,
                            "model_id": model_id,
                            "weapon_name": weapon_name,
                            "attacks_bonus": ctx["attacks_bonus"],
                            "damage_bonus": ctx["damage_bonus"],
                            "buff_key": buff_key,
                            "ability_name": ability_name,
                        },
                        instance_key=f"{model_id}:{buff_key}:fight",
                    )
                    pending_keys.add((model_id, buff_key))

    def _on_fight_unit_selected_deeds_of_heroism(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        root_getter = getattr(unit, "get_attached_unit_root", None)
        root = root_getter() if callable(root_getter) else unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        army_getter = getattr(root, "get_parent_army", None)
        army = army_getter() if callable(army_getter) else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return
        if selecting_player is not None and selecting_player is not player:
            return

        pending_keys: set[tuple[str, str]] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "deeds_of_heroism":
                    continue
                model_id = str(ctx.get("model_id", "") or "")
                buff_key = str(ctx.get("buff_key", "") or "")
                if model_id and buff_key:
                    pending_keys.add((model_id, buff_key))

        members_getter = getattr(root, "get_attached_unit_members", None)
        members = list(members_getter() or []) if callable(members_getter) else [root]
        if not members:
            members = [root]
        unit_id = get_entity_id(root)
        if not unit_id:
            return
        for member in sorted(members, key=lambda entry: str(get_entity_id(entry) or "")):
            if member is None:
                continue
            for model in sorted(list(getattr(member, "models", []) or []), key=lambda entry: str(get_entity_id(entry) or "")):
                if model is None or not bool(getattr(model, "is_alive", False)):
                    continue
                model_id = str(get_entity_id(model) or "")
                if not model_id:
                    continue
                specs = list(
                    getattr(member, "model_fight_selected_unit_melee_attacks_bonus_specs", lambda _m: [])(model) or []
                )
                for spec in specs:
                    buff_key = str(spec.get("buff_key", "") or "").strip().lower()
                    if not buff_key or (model_id, buff_key) in pending_keys:
                        continue
                    if bool(getattr(model, "has_used_once_per_battle", lambda _k: False)(buff_key)):
                        continue
                    ability_name = str(spec.get("source", "") or "Deeds of Heroism").strip() or "Deeds of Heroism"
                    try:
                        attacks_bonus = int(spec.get("attacks_bonus", 0) or 0)
                    except (TypeError, ValueError):
                        attacks_bonus = 0
                    if attacks_bonus <= 0:
                        continue
                    message = f"Use {ability_name} for {getattr(model, 'name', 'Model')}?"
                    ctx = {
                        "ability": "deeds_of_heroism",
                        "ability_name": ability_name,
                        "phase": "Fight phase",
                        "unit": getattr(root, "name", "") or "",
                        "unit_id": unit_id,
                        "model": getattr(model, "name", "") or "",
                        "model_id": model_id,
                        "attacks_bonus": int(attacks_bonus),
                        "buff_key": buff_key,
                    }
                    self._queue_optional_ability_confirmation(
                        player=player,
                        ability_key="deeds_of_heroism",
                        ability_name=ability_name,
                        message=message,
                        context=ctx,
                        payload={
                            "unit_id": unit_id,
                            "model_id": model_id,
                            "attacks_bonus": ctx["attacks_bonus"],
                            "buff_key": buff_key,
                            "ability_name": ability_name,
                        },
                        instance_key=f"{model_id}:{buff_key}:fight",
                    )
                    pending_keys.add((model_id, buff_key))

    def _on_fight_unit_selected_alchemicus_familiar(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        root_getter = getattr(unit, "get_attached_unit_root", None)
        root = root_getter() if callable(root_getter) else unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        army_getter = getattr(root, "get_parent_army", None)
        army = army_getter() if callable(army_getter) else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return
        if selecting_player is not None and selecting_player is not player:
            return

        pending_keys: set[tuple[str, str]] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "alchemicus_familiar":
                    continue
                model_id = str(ctx.get("model_id", "") or "")
                buff_key = str(ctx.get("buff_key", "") or "")
                if model_id and buff_key:
                    pending_keys.add((model_id, buff_key))

        members_getter = getattr(root, "get_attached_unit_members", None)
        members = list(members_getter() or []) if callable(members_getter) else [root]
        if not members:
            members = [root]
        unit_id = get_entity_id(root)
        if not unit_id:
            return
        for member in sorted(members, key=lambda entry: str(get_entity_id(entry) or "")):
            if member is None:
                continue
            for model in sorted(list(getattr(member, "models", []) or []), key=lambda entry: str(get_entity_id(entry) or "")):
                if model is None or not bool(getattr(model, "is_alive", False)):
                    continue
                model_id = str(get_entity_id(model) or "")
                if not model_id:
                    continue
                specs = list(
                    getattr(member, "model_fight_selected_unit_target_keyword_wound_bonus_specs", lambda _m: [])(model) or []
                )
                for spec in specs:
                    buff_key = str(spec.get("buff_key", "") or "").strip().lower()
                    if not buff_key or (model_id, buff_key) in pending_keys:
                        continue
                    if bool(getattr(model, "has_used_once_per_battle", lambda _k: False)(buff_key)):
                        continue
                    ability_name = str(spec.get("source", "") or "Alchemicus Familiar").strip() or "Alchemicus Familiar"
                    target_keyword = str(spec.get("target_keyword", "") or "").strip().lower()
                    message = f"Use {ability_name} for {getattr(model, 'name', 'Model')}?"
                    ctx = {
                        "ability": "alchemicus_familiar",
                        "ability_name": ability_name,
                        "phase": "Fight phase",
                        "unit": getattr(root, "name", "") or "",
                        "unit_id": unit_id,
                        "model": getattr(model, "name", "") or "",
                        "model_id": model_id,
                        "target_keyword": target_keyword,
                        "wound_bonus": int(spec.get("wound_bonus", 0) or 0),
                        "buff_key": buff_key,
                    }
                    self._queue_optional_ability_confirmation(
                        player=player,
                        ability_key="alchemicus_familiar",
                        ability_name=ability_name,
                        message=message,
                        context=ctx,
                        payload={
                            "unit_id": unit_id,
                            "model_id": model_id,
                            "target_keyword": target_keyword,
                            "wound_bonus": ctx["wound_bonus"],
                            "buff_key": buff_key,
                            "ability_name": ability_name,
                        },
                        instance_key=f"{model_id}:{buff_key}:fight",
                    )
                    pending_keys.add((model_id, buff_key))

    def _on_fight_unit_selected_target_keyword_melee_weapon_keyword(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        root_getter = getattr(unit, "get_attached_unit_root", None)
        root = root_getter() if callable(root_getter) else unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        army_getter = getattr(root, "get_parent_army", None)
        army = army_getter() if callable(army_getter) else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return
        if selecting_player is not None and selecting_player is not player:
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return

        pending_keys: set[tuple[str, str]] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "fight_selected_target_keyword_melee_weapon_keyword":
                    continue
                model_id = str(ctx.get("model_id", "") or "")
                buff_key = str(ctx.get("buff_key", "") or "")
                if model_id and buff_key:
                    pending_keys.add((model_id, buff_key))

        def _engaged_with_keyword(keyword: str) -> bool:
            keyword = str(keyword or "").strip().upper()
            if not keyword:
                return False
            try:
                enemies = list(game_map.get_enemy_units(root) or [])
            except Exception:
                enemies = []
            for enemy in list(enemies or []):
                if enemy is None or not enemy.is_alive():
                    continue
                try:
                    if not bool(getattr(enemy, "deployed", True)):
                        continue
                except Exception:
                    continue
                try:
                    enemy_root = enemy.get_attached_unit_root()
                except Exception:
                    enemy_root = enemy
                if enemy_root is None or not enemy_root.is_alive():
                    continue
                if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                    continue
                try:
                    if not bool(game_map.is_within_engagement_range(root, enemy_root)):
                        continue
                except Exception:
                    continue
                has_any_keyword = getattr(enemy_root, "has_any_keyword", None)
                if callable(has_any_keyword):
                    try:
                        if bool(has_any_keyword(keyword)):
                            return True
                    except Exception:
                        continue
            return False

        members_getter = getattr(root, "get_attached_unit_members", None)
        members = list(members_getter() or []) if callable(members_getter) else [root]
        if not members:
            members = [root]
        unit_id = get_entity_id(root)
        if not unit_id:
            return
        for member in sorted(members, key=lambda entry: str(get_entity_id(entry) or "")):
            if member is None:
                continue
            for model in sorted(list(getattr(member, "models", []) or []), key=lambda entry: str(get_entity_id(entry) or "")):
                if model is None or not bool(getattr(model, "is_alive", False)):
                    continue
                model_id = str(get_entity_id(model) or "")
                if not model_id:
                    continue
                specs = list(
                    getattr(member, "model_fight_selected_target_keyword_melee_weapon_keyword_specs", lambda _m: [])(model)
                    or []
                )
                for spec in specs:
                    buff_key = str(spec.get("buff_key", "") or "").strip().lower()
                    if not buff_key or (model_id, buff_key) in pending_keys:
                        continue
                    if bool(getattr(model, "has_used_once_per_battle", lambda _k: False)(buff_key)):
                        continue
                    target_keyword = str(spec.get("target_keyword", "") or "").strip().upper()
                    if not _engaged_with_keyword(target_keyword):
                        continue
                    keywords = [str(v or "").strip().upper() for v in list(spec.get("keywords") or []) if str(v or "").strip()]
                    if not keywords:
                        continue
                    ability_name = str(spec.get("source", "") or "Fight-selected melee weapon keyword bonus").strip()
                    ability_name = ability_name or "Fight-selected melee weapon keyword bonus"
                    message = f"Use {ability_name} for {getattr(model, 'name', 'Model')}?"
                    ctx = {
                        "ability": "fight_selected_target_keyword_melee_weapon_keyword",
                        "ability_name": ability_name,
                        "phase": "Fight phase",
                        "unit": getattr(root, "name", "") or "",
                        "unit_id": unit_id,
                        "model": getattr(model, "name", "") or "",
                        "model_id": model_id,
                        "buff_key": buff_key,
                        "target_keyword": target_keyword,
                        "keywords": list(keywords),
                    }
                    self._queue_optional_ability_confirmation(
                        player=player,
                        ability_key="fight_selected_target_keyword_melee_weapon_keyword",
                        ability_name=ability_name,
                        message=message,
                        context=ctx,
                        payload={
                            "unit_id": unit_id,
                            "model_id": model_id,
                            "buff_key": buff_key,
                            "target_keyword": target_keyword,
                            "keywords": list(keywords),
                            "ability_name": ability_name,
                        },
                        instance_key=f"{model_id}:{buff_key}:fight",
                    )
                    pending_keys.add((model_id, buff_key))

    def _on_fight_unit_selected_charged_melee_weapon_keywords(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        if str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        try:
            if not bool(root.is_active_for_rules()):
                return
        except Exception:
            if not root.is_alive() or not getattr(root, "deployed", True):
                return
            if root.is_in_reserves() or root.is_embarked:
                return
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        if not bool(getattr(getattr(root, "round_state", None), "charged_this_round", False)):
            return

        specs = list(getattr(root, "unit_fight_selected_charged_melee_weapon_keyword_specs", lambda: [])() or [])
        if not specs:
            return

        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        if not models:
            return

        normalize_source = getattr(root, "_normalize_keyword_phrase", None)
        for spec in list(specs or []):
            keywords = [str(value or "").strip().upper() for value in list(spec.get("keywords") or []) if str(value or "").strip()]
            if not keywords:
                continue
            source = str(spec.get("source", "") or "Fight-selected charged melee weapon keyword bonus").strip()
            source = source or "Fight-selected charged melee weapon keyword bonus"
            source_key = normalize_source(source) if callable(normalize_source) else ""
            source_key = str(source_key or source).strip().lower()
            for model in list(models or []):
                if model is None:
                    continue
                alive_attr = getattr(model, "is_alive", False)
                if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                    continue
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if not callable(set_keywords):
                    continue
                model_id = str(get_entity_id(model) or "")
                seen_weapon_keys: set[str] = set()
                for wargear in list(getattr(model, "wargear", []) or []):
                    if wargear is None:
                        continue
                    is_melee = getattr(wargear, "is_melee", None)
                    if not callable(is_melee) or not bool(is_melee()):
                        continue
                    weapon_name = str(getattr(wargear, "name", "") or "").strip()
                    weapon_key = Unit._norm_wargear_name(weapon_name)
                    if not weapon_key or weapon_key in seen_weapon_keys:
                        continue
                    seen_weapon_keys.add(weapon_key)
                    set_keywords(
                        key=f"fight_selected_charge_melee_weapon_keyword:{source_key}:{model_id}:{weapon_key}",
                        weapon_name=weapon_name,
                        keywords=list(keywords),
                        source=source,
                        expires_phase="FIGHT_PHASE",
                        attack_type="melee",
                    )

    def _on_fight_unit_selected_extremis_trigger_word(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        root_getter = getattr(unit, "get_attached_unit_root", None)
        root = root_getter() if callable(root_getter) else unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        army_getter = getattr(root, "get_parent_army", None)
        army = army_getter() if callable(army_getter) else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return
        if selecting_player is not None and selecting_player is not player:
            return

        source_fn = getattr(root, "get_extremis_trigger_word_source", None)
        ability_name = str(source_fn() if callable(source_fn) else "").strip()
        if not ability_name:
            return

        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("extremis_trigger_word_active")):
            exp = str(sr.get("extremis_trigger_word_expires_phase", "") or "").strip().upper()
            if not exp or exp == "FIGHT_PHASE":
                return

        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return
        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        message = f"Use {ability_name} for {getattr(root, 'name', 'Unit')}?"
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="extremis_trigger_word",
            ability_name=ability_name,
            message=message,
            context={
                "ability": "extremis_trigger_word",
                "ability_name": ability_name,
                "phase": "Fight phase",
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "weapon_name": "arco-flails",
                "attacks_value": 6,
            },
            payload={
                "unit_id": unit_id,
                "ability_name": ability_name,
                "weapon_name": "arco-flails",
                "attacks_value": 6,
            },
            instance_key=f"{unit_id}:{turn}:{owner_id}:extremis_trigger_word",
        )

    def _on_fight_unit_selected_sacrificial_dagger(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None or not root.is_alive():
            return
        if getattr(root, "is_in_reserves", lambda: False)() or getattr(root, "is_embarked", False):
            return
        player = root.get_parent_army().player if hasattr(root, "get_parent_army") else None
        if player is None:
            return
        if selecting_player is not None and player is not selecting_player:
            return

        pending_models = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "sacrificial_dagger":
                    continue
                mid = str(ctx.get("model_id", "") or "")
                if mid:
                    pending_models.add(mid)

        for entry in sorted(
            list(root.iter_sacrificial_dagger_models() or []),
            key=lambda e: str(get_entity_id(e.get("model")) or ""),
        ):
            model = entry.get("model")
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            # Once per phase gating.
            eff = getattr(model, "_temporary_effects", None)
            if isinstance(eff, dict):
                used = eff.get("sacrificial_dagger")
                exp = str((used or {}).get("expires_phase", "") or "").strip().upper()
                if exp == "FIGHT_PHASE":
                    continue
            ability_name = str(entry.get("source", "") or "Sacrificial Dagger").strip() or "Sacrificial Dagger"
            unit_id = get_entity_id(root)
            if not unit_id or not model_id:
                continue
            ctx = {
                "ability": "sacrificial_dagger",
                "ability_name": ability_name,
                "phase": "Fight phase",
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "model": getattr(model, "name", "") or "",
                "model_id": model_id,
            }
            message = f"Use {ability_name} for {getattr(model, 'name', 'Model')}?"
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="sacrificial_dagger",
                ability_name=ability_name,
                message=message,
                context=ctx,
                payload={"unit_id": unit_id, "model_id": model_id},
                instance_key=f"{model_id}:sacrificial_dagger:fight",
            )

    def _on_fight_unit_selected_sacrificial_blessing(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None or not root.is_alive():
            return
        if getattr(root, "is_in_reserves", lambda: False)() or getattr(root, "is_embarked", False):
            return
        player = root.get_parent_army().player if hasattr(root, "get_parent_army") else None
        if player is None:
            return
        if selecting_player is not None and player is not selecting_player:
            return

        pending_models = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "sacrificial_blessing":
                    continue
                mid = str(ctx.get("model_id", "") or "")
                if mid:
                    pending_models.add(mid)

        for entry in sorted(
            list(root.iter_sacrificial_blessing_models() or []),
            key=lambda e: str(get_entity_id(e.get("model")) or ""),
        ):
            model = entry.get("model")
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            unit_id = get_entity_id(root)
            if not unit_id or not model_id:
                continue
            ctx = {
                "ability": "sacrificial_blessing",
                "ability_name": str(entry.get("source", "") or "Sacrificial Blessing").strip() or "Sacrificial Blessing",
                "phase": "Fight phase",
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "model": getattr(model, "name", "") or "",
                "model_id": model_id,
            }
            message = f"Use {ctx['ability_name']} for {getattr(model, 'name', 'Model')}?"
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="sacrificial_blessing",
                ability_name=ctx["ability_name"],
                message=message,
                context=ctx,
                payload={"unit_id": unit_id, "model_id": model_id},
                instance_key=f"{model_id}:sacrificial_blessing:fight:{getattr(self, 'turn', 0)}",
            )

    def _on_fight_unit_selected_twisted_sorceries(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None or not root.is_alive():
            return
        if getattr(root, "is_in_reserves", lambda: False)() or getattr(root, "is_embarked", False):
            return
        player = root.get_parent_army().player if hasattr(root, "get_parent_army") else None
        if player is None:
            return
        if selecting_player is not None and player is not selecting_player:
            return

        pending_models = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "twisted_sorceries":
                    continue
                mid = str(ctx.get("model_id", "") or "")
                if mid:
                    pending_models.add(mid)

        for entry in sorted(
            list(root.iter_twisted_sorceries_models() or []),
            key=lambda e: str(get_entity_id(e.get("model")) or ""),
        ):
            model = entry.get("model")
            if model is None or not getattr(model, "is_alive", False):
                continue
            if getattr(model, "has_used_once_per_battle", lambda _k: False)("twisted_sorceries"):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            unit_id = get_entity_id(root)
            if not unit_id or not model_id:
                continue
            ctx = {
                "ability": "twisted_sorceries",
                "ability_name": str(entry.get("source", "") or "Twisted Sorceries").strip() or "Twisted Sorceries",
                "phase": "Fight phase",
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "model": getattr(model, "name", "") or "",
                "model_id": model_id,
                "buff_key": "twisted_sorceries",
            }
            message = f"Use {ctx['ability_name']} for {getattr(model, 'name', 'Model')}?"
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="twisted_sorceries",
                ability_name=ctx["ability_name"],
                message=message,
                context=ctx,
                payload={"unit_id": unit_id, "model_id": model_id, "buff_key": "twisted_sorceries"},
                instance_key=f"{model_id}:twisted_sorceries:fight",
            )

    def _on_fight_unit_selected_imperial_agents_digital_weapons(
        self,
        unit=None,
        selecting_player=None,
        **_kwargs,
    ) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None or not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "is_in_reserves", lambda: False)()):
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        if army is None:
            return
        player = getattr(army, "player", None)
        if player is None:
            return
        if selecting_player is not None and selecting_player is not player:
            return
        ia_mgr = getattr(army, "imperial_agents_detachments", None)
        trigger_fn = getattr(ia_mgr, "trigger_digital_weapons_on_fight_selected", None) if ia_mgr is not None else None
        if not callable(trigger_fn):
            return
        trigger_fn(root, game=self, player=player)

    def _on_fight_unit_selected_hammer_aflame(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None:
            return
        if selecting_player is not None and selecting_player is not player:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest

        pending_model_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") not in {"hammer_aflame", "thunderous_head_butt"}:
                    continue
                if str(ctx.get("source_unit_id", "") or "") != str(get_entity_id(root) or ""):
                    continue
                model_id = str(ctx.get("model_id", "") or "")
                if model_id:
                    pending_model_ids.add(model_id)

        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        try:
            models = sorted(models, key=lambda m: str(get_entity_id(m) or ""))
        except Exception:
            models = list(models)

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        for model in list(models or []):
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_model_ids:
                continue
            get_specs = getattr(root, "model_fight_selected_mortal_table_specs", None)
            specs = list(get_specs(model) or []) if callable(get_specs) else []
            if not specs:
                continue
            for spec in specs:
                candidates: list[Any] = []
                seen_targets: set[str] = set()
                try:
                    enemy_units = list(game_map.get_enemy_units(root) or [])
                except Exception:
                    enemy_units = []
                engagement_scope = str(spec.get("engagement_scope", "unit") or "unit").strip().lower() or "unit"
                for enemy in enemy_units:
                    if enemy is None:
                        continue
                    try:
                        enemy_root = enemy.get_attached_unit_root()
                    except Exception:
                        enemy_root = enemy
                    enemy_id = str(get_entity_id(enemy_root) or "")
                    if not enemy_id or enemy_id in seen_targets:
                        continue
                    seen_targets.add(enemy_id)
                    if not enemy_root.is_alive() or not getattr(enemy_root, "deployed", True):
                        continue
                    try:
                        if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                            continue
                    except Exception:
                        pass
                    try:
                        if engagement_scope == "model":
                            within_fn = getattr(root, "_model_within_engagement_range_of_unit", None)
                            if not callable(within_fn) or not bool(within_fn(model, enemy_root)):
                                continue
                        elif not game_map.is_within_engagement_range(root, enemy_root):
                            continue
                    except Exception:
                        continue
                    candidates.append(enemy_root)
                if not candidates:
                    continue
                ability_name = str(spec.get("source", "") or "Hammer Aflame (Psychic)").strip() or "Hammer Aflame (Psychic)"
                ability_key = str(spec.get("ability_key", "") or "hammer_aflame").strip().lower() or "hammer_aflame"
                options = [DecisionOption.create("None", payload={"action": "skip"})]
                for cand in sorted(list(candidates), key=_unit_sort_key):
                    options.append(
                        DecisionOption.create(
                            str(getattr(cand, "name", "Unit") or "Unit"),
                            payload={"target_unit_id": get_entity_id(cand)},
                        )
                    )
                if len(options) <= 1:
                    continue
                req = DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    f"{ability_name}: select one enemy unit within Engagement Range (or None).",
                    player_id=getattr(player, "id", None),
                    options=options,
                    context={
                        "ability": ability_key,
                        "ability_name": ability_name,
                        "phase": "Fight phase",
                        "source_unit_id": get_entity_id(root),
                        "unit_id": get_entity_id(root),
                        "model_id": model_id,
                        "is_psychic_attack": bool(spec.get("is_psychic_attack", False)),
                        "results": list(spec.get("results", []) or []),
                    },
                )
                self.request_decision(req)
                if model_id:
                    pending_model_ids.add(model_id)
                break

    def _on_fight_unit_selected_channelled_force(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        if str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        gk_mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
        applies_fn = getattr(gk_mgr, "channelled_force_applies", None) if gk_mgr is not None else None
        if not callable(applies_fn) or not bool(applies_fn(root, game=self)):
            return
        leadership_fn = getattr(root, "pass_leadership_check", None)
        if not callable(leadership_fn):
            return

        unit_id = str(get_entity_id(root) or "")
        owner_id = str(getattr(owner, "id", "") or "")
        try:
            battle_round = int(getattr(self, "turn", 0) or 0)
        except Exception:
            battle_round = 0
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "channelled_force":
                    continue
                if str(ctx.get("unit_id", "") or "") != unit_id:
                    continue
                if str(ctx.get("turn_owner_id", "") or "") != owner_id:
                    continue
                if int(ctx.get("battle_round", battle_round) or battle_round) != battle_round:
                    continue
                return

        options = [
            DecisionOption.create(
                "None",
                payload={
                    "action": "skip",
                    "unit_id": unit_id,
                    "summary": "Do not take the Leadership test.",
                },
            ),
            DecisionOption.create(
                "Lethal Hits",
                payload={
                    "unit_id": unit_id,
                    "choice": "LETHAL_HITS",
                    "summary": "On pass: psychic melee weapons gain [LETHAL HITS] until end of phase.",
                },
            ),
            DecisionOption.create(
                "Sustained Hits 1",
                payload={
                    "unit_id": unit_id,
                    "choice": "SUSTAINED_HITS_1",
                    "summary": "On pass: psychic melee weapons gain [SUSTAINED HITS 1] until end of phase.",
                },
            ),
        ]
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"Channelled Force: choose an effect for {getattr(root, 'name', 'Unit')} (or None).",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": "channelled_force",
                "ability_name": "Channelled Force",
                "phase": "Fight phase",
                "unit_id": unit_id,
                "battle_round": int(battle_round or 0),
                "turn_owner_id": owner_id,
                "candidate_choices": ["LETHAL_HITS", "SUSTAINED_HITS_1"],
                "optional": True,
            },
        )
        self.request_decision(request)

    def _on_fight_unit_selected_embodied_prophecy(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        if str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        try:
            if not bool(root.is_active_for_rules()):
                return
        except Exception:
            if not root.is_alive() or not getattr(root, "deployed", True):
                return
            if root.is_in_reserves() or root.is_embarked:
                return

        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return

        source_fn = getattr(root, "get_embodied_prophecy_source", None)
        source_name = str(source_fn() if callable(source_fn) else "").strip()
        if not source_name:
            return

        clear_fn = getattr(root, "clear_embodied_prophecy_effect", None)
        if callable(clear_fn):
            clear_fn()

        charged = bool(getattr(getattr(root, "round_state", None), "charged_this_round", False))
        if charged:
            apply_fn = getattr(root, "apply_embodied_prophecy_effect", None)
            if callable(apply_fn):
                apply_fn(
                    lethal_hits=True,
                    sustained_hits_value=1,
                    source=source_name,
                    game=self,
                    expires_phase="FIGHT_PHASE",
                )
            return

        unit_id = str(get_entity_id(root) or "")
        owner_id = str(getattr(owner, "id", "") or "")
        try:
            battle_round = int(getattr(self, "turn", 0) or 0)
        except Exception:
            battle_round = 0
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "embodied_prophecy":
                    continue
                if str(ctx.get("unit_id", "") or "") != unit_id:
                    continue
                if str(ctx.get("turn_owner_id", "") or "") != owner_id:
                    continue
                if int(ctx.get("battle_round", battle_round) or battle_round) != battle_round:
                    continue
                return

        options = [
            DecisionOption.create(
                "Lethal Hits",
                payload={
                    "unit_id": unit_id,
                    "choice": "LETHAL_HITS",
                    "summary": "Melee weapons gain [LETHAL HITS] until end of phase.",
                },
            ),
            DecisionOption.create(
                "Sustained Hits 1",
                payload={
                    "unit_id": unit_id,
                    "choice": "SUSTAINED_HITS_1",
                    "summary": "Melee weapons gain [SUSTAINED HITS 1] until end of phase.",
                },
            ),
        ]
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{source_name}: select one melee weapon ability for {getattr(root, 'name', 'Unit')}.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": "embodied_prophecy",
                "ability_name": source_name,
                "phase": "Fight phase",
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "battle_round": int(battle_round or 0),
                "turn_owner_id": owner_id,
                "candidate_choices": ["LETHAL_HITS", "SUSTAINED_HITS_1"],
                "optional": False,
            },
        )
        self.request_decision(request)

    def _on_fight_unit_selected_harbinger_of_death(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        try:
            entries = list(root.iter_harbinger_of_death_models() or [])
        except Exception:
            entries = []
        if not entries:
            return
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None:
            return

        from ..decision_kinds import DECISION_CHOOSE_HARBINGER_OF_DEATH
        from ..decisions import DecisionOption, DecisionRequest

        pending_models = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_HARBINGER_OF_DEATH:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    mid = str(ctx.get("model_id", "") or "")
                    if mid:
                        pending_models.add(mid)
        except Exception:
            pending_models = set()

        def _sort_key(entry):
            try:
                return str(get_entity_id(entry.get("model")))
            except Exception:
                return ""

        for entry in sorted(list(entries or []), key=_sort_key):
            model = entry.get("model")
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            weapon_name = str(entry.get("weapon_name", "") or "hellforged").strip() or "hellforged"
            ability_name = str(entry.get("source", "") or "Harbinger of Death").strip() or "Harbinger of Death"
            options = [
                DecisionOption.create(
                    "Lethal Hits",
                    payload={"choice": "LETHAL_HITS", "summary": "Weapons gain [LETHAL HITS] until end of phase."},
                ),
                DecisionOption.create(
                    "Precision",
                    payload={"choice": "PRECISION", "summary": "Weapons gain [PRECISION] until end of phase."},
                ),
                DecisionOption.create(
                    "Sustained Hits 1",
                    payload={"choice": "SUSTAINED_HITS_1", "summary": "Weapons gain [SUSTAINED HITS 1] until end of phase."},
                ),
            ]
            ctx = {
                "unit_id": get_entity_id(root),
                "model_id": model_id,
                "weapon_name": weapon_name,
                "ability_name": ability_name,
                "phase_name": "FIGHT_PHASE",
            }
            req = DecisionRequest.create(
                DECISION_CHOOSE_HARBINGER_OF_DEATH,
                f"{ability_name}: select a weapon ability.",
                player_id=getattr(player, "id", None),
                options=options,
                context=ctx,
            )
            self.request_decision(req)

    def _on_fight_unit_selected_maddened_ferocity(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        if mgr is None or not getattr(mgr, "maddened_ferocity_applies", lambda _u: False)(root):
            return

        bonus = 0
        try:
            if root.is_battle_shocked():
                bonus = 2
            elif bool(getattr(getattr(root, "round_state", None), "charged_this_round", False)):
                bonus = 1
        except Exception:
            bonus = 0

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if bonus:
                sr["maddened_ferocity_melee_attacks_bonus"] = int(bonus)
                sr["maddened_ferocity_expires_phase"] = "FIGHT_PHASE"
            else:
                sr.pop("maddened_ferocity_melee_attacks_bonus", None)
                sr.pop("maddened_ferocity_expires_phase", None)
            member.special_rules = sr

    def _on_fight_unit_selected_red_thirst(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        if mgr is None or not getattr(mgr, "red_thirst_applies", lambda _u: False)(root):
            return

        charged = bool(getattr(getattr(root, "round_state", None), "charged_this_round", False))
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if charged:
                sr["red_thirst_melee_attacks_bonus"] = 1
                sr["red_thirst_melee_strength_bonus"] = 2
                sr["red_thirst_expires_phase"] = "FIGHT_PHASE"
            else:
                sr.pop("red_thirst_melee_attacks_bonus", None)
                sr.pop("red_thirst_melee_strength_bonus", None)
                sr.pop("red_thirst_expires_phase", None)
            member.special_rules = sr

    def _on_fight_unit_selected_vehement_aggression(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        if str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        source = ""
        for member in list(members or []):
            if member is None or getattr(member, "attached_to", None) is not root:
                continue
            for name, _desc in member._iter_ability_entries_for_rules(model=None):
                if str(name or "").strip().lower() == "vehement aggression":
                    source = str(name or "Vehement Aggression").strip() or "Vehement Aggression"
                    break
            if source:
                break
        if not source:
            return

        leadership_fn = getattr(root, "pass_leadership_check", None)
        if not callable(leadership_fn):
            return
        reroll_mode = "full" if bool(leadership_fn()) else "ones"

        for member in list(members or []):
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["vehement_aggression_active"] = True
            sr["vehement_aggression_reroll_mode"] = reroll_mode
            sr["vehement_aggression_source"] = source
            sr["vehement_aggression_expires_phase"] = "FIGHT_PHASE"
            member.special_rules = sr

    def _on_fight_unit_selected_hypermorphic_fury(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        mgr = getattr(army, "genestealer_cults_detachments", None)
        bonus_fn = getattr(mgr, "hypermorphic_fury_melee_attacks_bonus", None) if mgr is not None else None
        if not callable(bonus_fn):
            return

        bonus, source = bonus_fn(root, game=self)
        source_name = str(source or "Hypermorphic Fury").strip() or "Hypermorphic Fury"
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if int(bonus or 0):
                sr["hypermorphic_fury_melee_attacks_bonus"] = int(bonus or 0)
                sr["hypermorphic_fury_source"] = source_name
                sr["hypermorphic_fury_expires_phase"] = "FIGHT_PHASE"
            else:
                sr.pop("hypermorphic_fury_melee_attacks_bonus", None)
                sr.pop("hypermorphic_fury_source", None)
                sr.pop("hypermorphic_fury_expires_phase", None)
            member.special_rules = sr

    def _on_fight_unit_selected_pious_fervour(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        if str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return

        from ...utility.aura_utils import distance_between_models_bases_3d

        try:
            enemy_units = list(game_map.get_enemy_units(root) or [])
        except Exception:
            enemy_units = []
        if not enemy_units:
            return

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        try:
            members = sorted(members, key=lambda member: str(get_entity_id(member) or ""))
        except Exception:
            members = list(members)

        for member in list(members or []):
            if member is None:
                continue
            ability_name = ""
            for name, _desc in member._iter_ability_entries_for_rules(model=None):
                if str(name or "").strip().lower() == "pious fervour":
                    ability_name = str(name or "Pious Fervour").strip() or "Pious Fervour"
                    break
            if not ability_name:
                continue
            models = sorted(
                list(getattr(member, "models", []) or []),
                key=lambda model: str(get_entity_id(model) or ""),
            )
            for model in list(models or []):
                if not getattr(model, "is_alive", False):
                    continue
                seen_enemy_ids: set[str] = set()
                for enemy in list(enemy_units or []):
                    if enemy is None:
                        continue
                    try:
                        enemy_root = enemy.get_attached_unit_root()
                    except Exception:
                        enemy_root = enemy
                    if enemy_root is None:
                        continue
                    enemy_id = str(get_entity_id(enemy_root) or "")
                    if not enemy_id or enemy_id in seen_enemy_ids:
                        continue
                    if not enemy_root.is_alive() or not getattr(enemy_root, "deployed", True):
                        continue
                    if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                        continue
                    alive_enemy_models = [
                        enemy_model
                        for enemy_model in list(getattr(enemy_root, "models", []) or [])
                        if getattr(enemy_model, "is_alive", False)
                    ]
                    if not alive_enemy_models:
                        continue
                    in_range = any(
                        float(distance_between_models_bases_3d(model, enemy_model)) <= 6.0 + 1e-6
                        for enemy_model in list(alive_enemy_models)
                    )
                    if in_range:
                        seen_enemy_ids.add(enemy_id)
                attacks_bonus = min(3, len(seen_enemy_ids))
                model.set_temporary_weapon_bonus(
                    key=f"pious_fervour:{get_entity_id(model)}",
                    weapon_name="Master-crafted power weapon",
                    attacks_bonus=int(attacks_bonus),
                    source=ability_name,
                    expires_phase="FIGHT_PHASE",
                )

    def _on_fight_unit_selected_enemy_melee_hit_penalty(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return
        try:
            enemy_units = list(game_map.get_enemy_units(root) or [])
        except Exception:
            enemy_units = []
        if not enemy_units:
            return

        def _exclude_applies(spec: dict) -> bool:
            exclude_kw = str(spec.get("exclude_keyword", "") or "").strip().upper()
            if not exclude_kw:
                return False
            if exclude_kw == "TITANIC":
                try:
                    return bool(getattr(root, "is_titanic", False) or root.has_keyword("Titanic"))
                except Exception:
                    return False
            if exclude_kw == "TITAN":
                try:
                    return bool(root.has_keyword("Titan"))
                except Exception:
                    return False
            return False

        sources: list[str] = []
        seen_sources: set[str] = set()
        for enemy in enemy_units:
            if enemy is None:
                continue
            try:
                enemy_root = enemy.get_attached_unit_root()
            except Exception:
                enemy_root = enemy
            if enemy_root is None:
                continue
            if not enemy_root.is_alive() or not getattr(enemy_root, "deployed", True):
                continue
            if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                continue
            try:
                if not game_map.is_within_engagement_range(enemy_root, root):
                    continue
            except Exception:
                continue
            specs = enemy_root.unit_fight_selected_enemy_melee_hit_penalty_specs() or []
            if not specs:
                continue
            for spec in specs:
                if _exclude_applies(spec or {}):
                    continue
                source = str(spec.get("source", "") or "Engagement melee hit penalty").strip()
                if source and source.lower() not in seen_sources:
                    seen_sources.add(source.lower())
                    sources.append(source)

        if not sources:
            return

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]

        sources_sorted = sorted(sources)
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["fight_selected_enemy_melee_hit_penalty_active"] = True
            sr["fight_selected_enemy_melee_hit_penalty_expires_phase"] = "FIGHT_PHASE"
            sr["fight_selected_enemy_melee_hit_penalty_sources"] = list(sources_sorted)
            sr["fight_selected_enemy_melee_hit_penalty_value"] = 1
            member.special_rules = sr

    def _on_fight_unit_selected_selected_to_fight_reroll_choice(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        pname = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if pname and pname != "FIGHT_PHASE":
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        if not models:
            return
        try:
            if hasattr(root, "grant_selected_to_action_reroll_choice_for_models"):
                root.grant_selected_to_action_reroll_choice_for_models(models, action="fight")
        except Exception:
            return

    def _on_shooting_targets_selected_heroes_all(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        army = root.get_parent_army()
        if army is None:
            return
        mgr = getattr(army, "space_marines_detachments", None)
        start_selection = getattr(mgr, "heroes_all_start_selection", None) if mgr is not None else None
        if callable(start_selection):
            start_selection(root, action="shoot", game=self)

    def _on_fight_unit_selected_heroes_all(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        army = root.get_parent_army()
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        mgr = getattr(army, "space_marines_detachments", None)
        start_selection = getattr(mgr, "heroes_all_start_selection", None) if mgr is not None else None
        if callable(start_selection):
            start_selection(root, action="fight", game=self)

    def _queue_thousand_sons_warpmeld_sacrifice_confirmation(
        self,
        *,
        unit=None,
        mode: str,
        trigger_action: str,
        source_unit=None,
    ) -> None:
        if unit is None:
            return
        mode_key = str(mode or "").strip().lower()
        if mode_key not in {"offense", "defense"}:
            return
        action_key = str(trigger_action or "").strip().lower()
        if action_key not in {"shoot", "fight"}:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if not bool(getattr(root, "deployed", True)):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        army = root.get_parent_army()
        if army is None:
            return
        player = getattr(army, "player", None)
        if player is None:
            return
        mgr = getattr(army, "thousand_sons_detachments", None)
        can_use = getattr(mgr, "warpmeld_sacrifice_can_use", None) if mgr is not None else None
        if not callable(can_use) or not bool(can_use(root, mode=mode_key, game=self)):
            return
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return
        try:
            source_root = source_unit.get_attached_unit_root() if source_unit is not None else None
        except Exception:
            source_root = source_unit
        source_unit_id = str(get_entity_id(source_root) or "") if source_root is not None else ""
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        phase_label = phase_name.replace("_", " ").title() if phase_name else "Phase"
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        current_player = getattr(self, "get_current_player", lambda: None)()
        turn_owner_id = str(getattr(current_player, "id", "") or "")
        ability_name = "Warpmeld Sacrifice"
        if mode_key == "offense":
            message = f"Use {ability_name} for {getattr(root, 'name', 'Unit')} before resolving its attacks?"
        else:
            message = f"Use {ability_name} for {getattr(root, 'name', 'Unit')} after being selected as a target?"
        instance_parts = [
            "warpmeld_sacrifice",
            str(turn),
            phase_name,
            turn_owner_id,
            mode_key,
            action_key,
            unit_id,
        ]
        if source_unit_id:
            instance_parts.append(source_unit_id)
        instance_key = ":".join([p for p in instance_parts if p != ""])
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="warpmeld_sacrifice",
            ability_name=ability_name,
            message=message,
            context={
                "ability_name": ability_name,
                "phase": phase_label,
                "unit": getattr(root, "name", "") or "",
                "unit_id": unit_id,
                "ability_mode": mode_key,
                "trigger_action": action_key,
                "source_unit_id": source_unit_id,
                "turn": int(turn or 0),
                "turn_owner_id": turn_owner_id,
            },
            payload={
                "unit_id": unit_id,
                "ability_mode": mode_key,
                "trigger_action": action_key,
                "source_unit_id": source_unit_id,
            },
            instance_key=instance_key,
        )

    def _on_shooting_targets_selected_thousand_sons_warpmeld_sacrifice(
        self,
        attacking_unit=None,
        target_units=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None or not target_units:
            return
        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        if attacker_root is None:
            return
        self._queue_thousand_sons_warpmeld_sacrifice_confirmation(
            unit=attacker_root,
            mode="offense",
            trigger_action="shoot",
        )
        attacker_army = attacker_root.get_parent_army()
        target_roots: dict[str, Any] = {}
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            if target_root is None:
                continue
            if attacker_army is not None and target_root.get_parent_army() is attacker_army:
                continue
            target_id = str(get_entity_id(target_root) or "")
            if not target_id:
                continue
            target_roots[target_id] = target_root
        for target_id in sorted(target_roots.keys()):
            self._queue_thousand_sons_warpmeld_sacrifice_confirmation(
                unit=target_roots[target_id],
                mode="defense",
                trigger_action="shoot",
                source_unit=attacker_root,
            )

    def _on_fight_unit_selected_thousand_sons_warpmeld_sacrifice(
        self,
        unit=None,
        selecting_player=None,
        **_kwargs,
    ) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        army = root.get_parent_army()
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        self._queue_thousand_sons_warpmeld_sacrifice_confirmation(
            unit=root,
            mode="offense",
            trigger_action="fight",
        )

    def _on_fight_targets_selected_thousand_sons_warpmeld_sacrifice(
        self,
        attacking_unit=None,
        target_units=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None or not target_units:
            return
        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        if attacker_root is None:
            return
        attacker_army = attacker_root.get_parent_army()
        target_roots: dict[str, Any] = {}
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            if target_root is None:
                continue
            if attacker_army is not None and target_root.get_parent_army() is attacker_army:
                continue
            target_id = str(get_entity_id(target_root) or "")
            if not target_id:
                continue
            target_roots[target_id] = target_root
        for target_id in sorted(target_roots.keys()):
            self._queue_thousand_sons_warpmeld_sacrifice_confirmation(
                unit=target_roots[target_id],
                mode="defense",
                trigger_action="fight",
                source_unit=attacker_root,
            )

    def _on_shooting_targets_selected_thousand_sons_warpfire_infusion(
        self,
        attacking_unit=None,
        target_units=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None or not target_units:
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        army = root.get_parent_army()
        if army is None:
            return
        mgr = getattr(army, "thousand_sons_detachments", None)
        start_selection = getattr(mgr, "warpfire_infusion_start_selection", None) if mgr is not None else None
        if callable(start_selection):
            start_selection(root, action="shoot", game=self)

    def _on_fight_unit_selected_thousand_sons_warpfire_infusion(
        self,
        unit=None,
        selecting_player=None,
        **_kwargs,
    ) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        army = root.get_parent_army()
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        mgr = getattr(army, "thousand_sons_detachments", None)
        start_selection = getattr(mgr, "warpfire_infusion_start_selection", None) if mgr is not None else None
        if callable(start_selection):
            start_selection(root, action="fight", game=self)

    def _on_fight_unit_selected_master_of_wolves_ferocious_strike(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        if str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        if root.is_in_reserves() or root.is_embarked:
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        if sm_mgr is None:
            return
        applies_fn = getattr(sm_mgr, "master_of_wolves_ferocious_strike_applies", None)
        if not callable(applies_fn) or not bool(applies_fn(root, game=self)):
            return
        clear_choice = getattr(sm_mgr, "clear_master_of_wolves_ferocious_strike_choice", None)
        if callable(clear_choice):
            clear_choice(root)

        unit_id = str(get_entity_id(root) or "")
        owner_id = str(getattr(owner, "id", "") or "")
        try:
            battle_round = int(getattr(self, "turn", 0) or 0)
        except Exception:
            battle_round = 0
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "master_of_wolves_ferocious_strike":
                    continue
                if str(ctx.get("unit_id", "") or "") != unit_id:
                    continue
                if str(ctx.get("turn_owner_id", "") or "") != owner_id:
                    continue
                if int(ctx.get("battle_round", battle_round) or battle_round) != battle_round:
                    continue
                return

        options = [
            DecisionOption.create(
                "Lethal Hits",
                payload={
                    "unit_id": unit_id,
                    "choice": "LETHAL_HITS",
                    "summary": "Melee weapons gain [LETHAL HITS] until end of phase.",
                },
            ),
            DecisionOption.create(
                "Sustained Hits 1",
                payload={
                    "unit_id": unit_id,
                    "choice": "SUSTAINED_HITS_1",
                    "summary": "Melee weapons gain [SUSTAINED HITS 1] until end of phase.",
                },
            ),
        ]
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"Ferocious Strike: select weapon ability for {getattr(root, 'name', 'Unit')}.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": "master_of_wolves_ferocious_strike",
                "ability_name": "Ferocious Strike",
                "phase": "Fight phase",
                "unit_id": unit_id,
                "battle_round": int(battle_round or 0),
                "turn_owner_id": owner_id,
                "candidate_choices": ["LETHAL_HITS", "SUSTAINED_HITS_1"],
            },
        )
        self.request_decision(request)

    def _on_unit_shooting_resolved_heroes_all(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        if root is None:
            return
        army = root.get_parent_army()
        mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        end_selection = getattr(mgr, "heroes_all_end_selection", None) if mgr is not None else None
        if callable(end_selection):
            end_selection(root, action="shoot")

    def _on_fight_sequence_complete_heroes_all(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        army = root.get_parent_army()
        mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        end_selection = getattr(mgr, "heroes_all_end_selection", None) if mgr is not None else None
        if callable(end_selection):
            end_selection(root, action="fight")

    def _queue_oathbound_speculator_confirmation(self, root, *, player, trigger: str) -> None:
        if root is None or player is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("enhancement_oathbound_speculator"):
            return
        bearer = getattr(root, "_get_enhancement_bearer_model", lambda: None)()
        if bearer is None:
            return
        if not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if not bool(getattr(root, "deployed", True)):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        army = root.get_parent_army()
        pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
        if pe is None:
            return
        try:
            if int(getattr(pe, "yield_points", 0) or 0) < 3:
                return
        except Exception:
            return
        owner_id = str(getattr(player, "id", "") or "")
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        if not phase_name or turn <= 0 or not owner_id:
            return
        phase_key = f"{turn}:{phase_name}:{owner_id}"
        if (
            bool(sr.get("enhancement_oathbound_speculator_wound_bonus_active"))
            and str(sr.get("enhancement_oathbound_speculator_phase_key", "") or "") == phase_key
        ):
            return
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return
        ability_name = "Oathbound Speculator"
        trigger_label = "shoot" if str(trigger or "").strip().lower() == "shoot" else "fight"
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="oathbound_speculator",
            ability_name=ability_name,
            message=f"{ability_name}: spend 3 YP for +1 to wound until end of phase?",
            context={
                "ability_name": ability_name,
                "phase": str(getattr(getattr(self, "phase", None), "name", "") or ""),
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "cost": 3,
                "trigger": trigger_label,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
            },
            payload={
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "cost": 3,
            },
            instance_key=f"{unit_id}:{turn}:{owner_id}:{phase_name}:oathbound_speculator",
        )

    def _queue_etacarn_sb9_targeting_implant_confirmation(self, root, *, player, trigger: str) -> None:
        if root is None or player is None:
            return
        _root, source_member, source_sr = self._attached_member_with_enhancement_flag(
            root,
            "enhancement_etacarn_sb9_targeting_implant",
        )
        if source_member is None or not isinstance(source_sr, dict):
            return
        bearer = getattr(source_member, "_get_enhancement_bearer_model", lambda: None)()
        if bearer is None or not bool(getattr(bearer, "is_alive", True)):
            return
        if not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if not bool(getattr(root, "deployed", True)):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        army = root.get_parent_army()
        pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
        if pe is None:
            return
        try:
            cost = int(source_sr.get("enhancement_etacarn_sb9_targeting_implant_cost", 3) or 3)
        except Exception:
            cost = 3
        cost = max(0, int(cost or 0))
        if cost <= 0:
            return
        try:
            if int(getattr(pe, "yield_points", 0) or 0) < cost:
                return
        except Exception:
            return
        owner_id = str(getattr(player, "id", "") or "")
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if not phase_name:
            phase_name = "SHOOTING_PHASE" if str(trigger or "").strip().lower() == "shoot" else "FIGHT_PHASE"
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        if not phase_name or turn <= 0 or not owner_id:
            return
        if bool(source_sr.get("enhancement_etacarn_sb9_targeting_implant_active", False)):
            active_owner = str(source_sr.get("enhancement_etacarn_sb9_targeting_implant_turn_owner", "") or "")
            try:
                active_turn = int(source_sr.get("enhancement_etacarn_sb9_targeting_implant_turn", 0) or 0)
            except Exception:
                active_turn = 0
            active_phase = str(
                source_sr.get("enhancement_etacarn_sb9_targeting_implant_expires_phase", "") or ""
            ).strip().upper()
            if (
                (not active_owner or active_owner == owner_id)
                and (not active_turn or active_turn == turn)
                and (not active_phase or active_phase == phase_name)
            ):
                return
        root_id = str(get_entity_id(root) or "")
        source_unit_id = str(get_entity_id(source_member) or "")
        if not root_id or not source_unit_id:
            return
        ability_name = str(
            source_sr.get("enhancement_etacarn_sb9_targeting_implant_source", "") or "Etacarn SB9 Targeting Implant"
        ).strip() or "Etacarn SB9 Targeting Implant"
        try:
            sustained_hits_value = int(
                source_sr.get("enhancement_etacarn_sb9_targeting_implant_sustained_hits_value", 1) or 1
            )
        except Exception:
            sustained_hits_value = 1
        sustained_hits_value = max(1, int(sustained_hits_value or 1))
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="etacarn_sb9_targeting_implant",
            ability_name=ability_name,
            message=(
                f"{ability_name}: spend {int(cost)} YP for [SUSTAINED HITS {int(sustained_hits_value)}] until end of phase?"
            ),
            context={
                "ability_name": ability_name,
                "phase": phase_name,
                "unit_id": root_id,
                "source_unit_id": source_unit_id,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
                "cost": int(cost),
                "sustained_hits_value": int(sustained_hits_value),
                "trigger": "shoot" if str(trigger or "").strip().lower() == "shoot" else "fight",
            },
            payload={
                "unit_id": root_id,
                "source_unit_id": source_unit_id,
                "cost": int(cost),
                "sustained_hits_value": int(sustained_hits_value),
            },
            instance_key=f"{source_unit_id}:{turn}:{owner_id}:{phase_name}:etacarn_sb9_targeting_implant",
        )

    def _on_shooting_targets_selected_oathbound_speculator(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        army = root.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return
        self._queue_oathbound_speculator_confirmation(root, player=player, trigger="shoot")

    def _on_shooting_targets_selected_etacarn_sb9_targeting_implant(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        _ = target_units
        if attacking_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        army = root.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return
        self._queue_etacarn_sb9_targeting_implant_confirmation(root, player=player, trigger="shoot")

    def _on_shooting_targets_selected_trivarg_cyber_implant(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        _ = target_units
        if attacking_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        army = root.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return

        _root, source_member, source_sr = self._attached_member_with_enhancement_flag(
            root,
            "enhancement_trivarg_cyber_implant",
        )
        if source_member is None:
            return
        bearer = getattr(source_member, "_get_enhancement_bearer_model", lambda: None)()
        if bearer is None or not bool(getattr(bearer, "is_alive", True)):
            return

        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() or "SHOOTING_PHASE"
        if bool(source_sr.get("enhancement_trivarg_cyber_implant_active", False)):
            active_owner = str(source_sr.get("enhancement_trivarg_cyber_implant_turn_owner", "") or "")
            try:
                active_turn = int(source_sr.get("enhancement_trivarg_cyber_implant_turn", 0) or 0)
            except Exception:
                active_turn = 0
            active_phase = str(source_sr.get("enhancement_trivarg_cyber_implant_expires_phase", "") or "").strip().upper()
            if (
                (not active_owner or active_owner == owner_id)
                and (not active_turn or active_turn == turn)
                and (not active_phase or active_phase == phase_name)
            ):
                return

        ability_name = str(source_sr.get("enhancement_trivarg_cyber_implant_source", "") or "Trivärg Cyber Implant").strip()
        if not ability_name:
            ability_name = "Trivärg Cyber Implant"
        try:
            sustained_hits_value = int(source_sr.get("enhancement_trivarg_cyber_implant_sustained_hits_value", 2) or 2)
        except Exception:
            sustained_hits_value = 2

        round_state = getattr(root, "round_state", None)
        disembarked_this_turn = bool(getattr(round_state, "disembarked_this_round", False))
        if disembarked_this_turn:
            updated = dict(source_sr)
            updated["enhancement_trivarg_cyber_implant_active"] = True
            updated["enhancement_trivarg_cyber_implant_sustained_hits_value"] = int(max(1, sustained_hits_value))
            updated["enhancement_trivarg_cyber_implant_turn_owner"] = owner_id
            updated["enhancement_trivarg_cyber_implant_turn"] = int(turn or 0)
            updated["enhancement_trivarg_cyber_implant_expires_phase"] = phase_name
            updated["enhancement_trivarg_cyber_implant_source"] = ability_name
            source_member.special_rules = updated
            return

        pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
        if pe is None:
            return
        try:
            cost = int(source_sr.get("enhancement_trivarg_cyber_implant_cost", 2) or 2)
        except Exception:
            cost = 2
        if cost <= 0:
            return
        try:
            available_yp = int(getattr(pe, "yield_points", 0) or 0)
        except Exception:
            available_yp = 0
        if available_yp < cost:
            return

        root_id = str(get_entity_id(root) or "")
        source_unit_id = str(get_entity_id(source_member) or "")
        if not root_id or not source_unit_id:
            return
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="trivarg_cyber_implant",
            ability_name=ability_name,
            message=f"{ability_name}: spend {int(cost)} YP for [SUSTAINED HITS {int(max(1, sustained_hits_value))}] until end of phase?",
            context={
                "ability_name": ability_name,
                "phase": "Shooting phase",
                "unit_id": root_id,
                "source_unit_id": source_unit_id,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
                "cost": int(cost),
                "sustained_hits_value": int(max(1, sustained_hits_value)),
            },
            payload={
                "unit_id": root_id,
                "source_unit_id": source_unit_id,
                "cost": int(cost),
                "sustained_hits_value": int(max(1, sustained_hits_value)),
            },
            instance_key=f"{source_unit_id}:{turn}:{owner_id}:trivarg_cyber_implant",
        )

    def _on_fight_unit_selected_oathbound_speculator(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        if str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        army = root.get_parent_army()
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        self._queue_oathbound_speculator_confirmation(root, player=owner, trigger="fight")

    def _on_shooting_targets_selected_imperial_knights_questoris_companions(
        self,
        attacking_unit=None,
        target_units=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None or not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if not bool(getattr(root, "deployed", True)):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return
        detachment_mgr = getattr(army, "imperial_knights_detachments", None) if army is not None else None
        if detachment_mgr is None or not bool(getattr(detachment_mgr, "is_questoris_companions", lambda: False)()):
            return
        source_sr = getattr(root, "special_rules", None)
        if not isinstance(source_sr, dict) or not bool(source_sr.get("enhancement_wyrmslayer_divination")):
            return
        is_expended = getattr(detachment_mgr, "is_questoris_companions_enhancement_expended", None)
        if callable(is_expended) and bool(is_expended(root)):
            return

        has_fly_target = False
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            if target_root is None:
                continue
            try:
                if bool(target_root.has_any_keyword("FLY") or target_root.has_keyword("FLY")):
                    has_fly_target = True
                    break
            except Exception:
                continue
        if not has_fly_target:
            return

        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return
        source_name = str(source_sr.get("enhancement_wyrmslayer_divination_source", "") or "Wyrmslayer Divination").strip()
        source_name = source_name or "Wyrmslayer Divination"
        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="imperial_knights_wyrmslayer_divination",
            ability_name="Wyrmslayer Divination",
            message=f"Wyrmslayer Divination: use {source_name} for {getattr(root, 'name', 'Unit')}?",
            context={
                "ability_name": "Wyrmslayer Divination",
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
                "phase_name": phase_name,
            },
            payload={
                "unit_id": unit_id,
                "source_unit_id": unit_id,
            },
            instance_key=f"{unit_id}:{turn}:{owner_id}:{phase_name}:wyrmslayer_divination",
        )

    def _on_fight_unit_selected_imperial_knights_questoris_companions(
        self,
        unit=None,
        selecting_player=None,
        **_kwargs,
    ) -> None:
        if unit is None:
            return
        if str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None or not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if not bool(getattr(root, "deployed", True)):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        if owner is not self.get_current_player():
            return
        detachment_mgr = getattr(army, "imperial_knights_detachments", None) if army is not None else None
        if detachment_mgr is None or not bool(getattr(detachment_mgr, "is_questoris_companions", lambda: False)()):
            return
        source_sr = getattr(root, "special_rules", None)
        if not isinstance(source_sr, dict) or not bool(source_sr.get("enhancement_pennant_of_silvered_fury")):
            return
        is_expended = getattr(detachment_mgr, "is_questoris_companions_enhancement_expended", None)
        if callable(is_expended) and bool(is_expended(root)):
            return
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return
        source_name = str(source_sr.get("enhancement_pennant_of_silvered_fury_source", "") or "Pennant of Silvered Fury").strip()
        source_name = source_name or "Pennant of Silvered Fury"
        owner_id = str(getattr(owner, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        self._queue_optional_ability_confirmation(
            player=owner,
            ability_key="imperial_knights_pennant_of_silvered_fury",
            ability_name="Pennant of Silvered Fury",
            message=f"Pennant of Silvered Fury: use {source_name} for {getattr(root, 'name', 'Unit')}?",
            context={
                "ability_name": "Pennant of Silvered Fury",
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
                "phase_name": phase_name,
            },
            payload={
                "unit_id": unit_id,
                "source_unit_id": unit_id,
            },
            instance_key=f"{unit_id}:{turn}:{owner_id}:{phase_name}:pennant_of_silvered_fury",
        )

    def _on_fight_attacks_resolved_imperial_knights_questoris_companions(
        self,
        unit=None,
        attacker_unit=None,
        target_unit=None,
        killing_models_by_target=None,
        **_kwargs,
    ) -> None:
        attacker_unit = attacker_unit if attacker_unit is not None else unit
        if attacker_unit is None:
            return
        if str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        if root is None or not bool(getattr(root, "is_alive", lambda: False)()):
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return
        detachment_mgr = getattr(army, "imperial_knights_detachments", None) if army is not None else None
        if detachment_mgr is None or not bool(getattr(detachment_mgr, "is_questoris_companions", lambda: False)()):
            return
        source_sr = getattr(root, "special_rules", None)
        if not isinstance(source_sr, dict) or not bool(source_sr.get("enhancement_crushing_condemnation")):
            return
        is_expended = getattr(detachment_mgr, "is_questoris_companions_enhancement_expended", None)
        if callable(is_expended) and bool(is_expended(root)):
            return

        destroyed_enemy = False
        if isinstance(killing_models_by_target, dict):
            for target in list((killing_models_by_target or {}).keys()):
                if target is None:
                    continue
                try:
                    target_root = target.get_attached_unit_root()
                except Exception:
                    target_root = target
                if target_root is None:
                    continue
                try:
                    if target_root.get_parent_army() is army:
                        continue
                except Exception:
                    continue
                if not bool(getattr(target_root, "is_alive", lambda: False)()):
                    destroyed_enemy = True
                    break
        if not destroyed_enemy and target_unit is not None:
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is not None:
                try:
                    destroyed_enemy = target_root.get_parent_army() is not army and not bool(target_root.is_alive())
                except Exception:
                    destroyed_enemy = False
        if not destroyed_enemy:
            return

        candidate_fn = getattr(detachment_mgr, "questoris_companions_crushing_condemnation_candidates", None)
        if not callable(candidate_fn):
            return
        candidates = list(candidate_fn(root, game=self, game_map=self.map) or [])
        if not candidates:
            return

        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return
        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() or "FIGHT_PHASE"
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "imperial_knights_crushing_condemnation":
                    continue
                if str(ctx.get("source_unit_id", "") or ctx.get("unit_id", "") or "") != unit_id:
                    continue
                if str(ctx.get("turn_owner", "") or "") != owner_id:
                    continue
                if int(ctx.get("turn", turn) or turn) != int(turn or 0):
                    continue
                return

        source_name = str(source_sr.get("enhancement_crushing_condemnation_source", "") or "Crushing Condemnation").strip()
        source_name = source_name or "Crushing Condemnation"
        bearer = getattr(root, "_get_enhancement_bearer_model", lambda: None)()
        options = [DecisionOption.create("None", payload={"action": "skip"})]
        sorted_candidates = sorted(list(candidates), key=lambda candidate: str(maybe_entity_id(candidate) or ""))
        for target in sorted_candidates:
            target_id = str(get_entity_id(target) or "")
            if not target_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(target, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": target_id},
                )
            )
        if len(options) <= 1:
            return
        try:
            range_in = float(source_sr.get("enhancement_crushing_condemnation_range", 12.0) or 12.0)
        except Exception:
            range_in = 12.0
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{source_name}: select an enemy unit for {getattr(root, 'name', 'Unit')} (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "imperial_knights_crushing_condemnation",
                "ability_name": source_name,
                "phase_name": phase_name,
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "model_id": str(get_entity_id(bearer) or "") if bearer is not None else "",
                "range": float(range_in),
                "turn_owner": owner_id,
                "turn": int(turn or 0),
                "allow_skip": True,
                "candidate_unit_ids": [
                    str(get_entity_id(candidate) or "")
                    for candidate in sorted_candidates
                    if str(get_entity_id(candidate) or "")
                ],
            },
        )
        self.request_decision(request)

    def _on_fight_unit_selected_etacarn_sb9_targeting_implant(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        if str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        army = root.get_parent_army()
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        self._queue_etacarn_sb9_targeting_implant_confirmation(root, player=owner, trigger="fight")

    def _on_fight_unit_selected_piledriver(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        if not self.is_fight_phase():
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if not bool(getattr(root, "deployed", True)):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        army = root.get_parent_army()
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
        if pe is None:
            return
        try:
            available_yp = int(getattr(pe, "yield_points", 0) or 0)
        except Exception:
            available_yp = 0
        max_spend = max(0, min(2, int(available_yp or 0)))
        if max_spend <= 0:
            return
        _root, source_member, source_sr = self._attached_member_with_enhancement_flag(
            root,
            "enhancement_piledriver",
        )
        if source_member is None or not isinstance(source_sr, dict):
            return
        bearer = getattr(source_member, "_get_enhancement_bearer_model", lambda: None)()
        if bearer is None or not bool(getattr(bearer, "is_alive", True)):
            return
        source_unit_id = str(get_entity_id(source_member) or "")
        model_id = str(get_entity_id(bearer) or "")
        root_id = str(get_entity_id(root) or "")
        if not source_unit_id or not model_id or not root_id:
            return
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        turn_owner_id = str(getattr(self.get_current_player(), "id", "") or "")
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() or "FIGHT_PHASE"
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "piledriver":
                    continue
                if str(ctx.get("source_unit_id", "") or "") != source_unit_id:
                    continue
                if str(ctx.get("turn_owner", "") or "") != turn_owner_id:
                    continue
                if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                    continue
                if str(ctx.get("phase_name", "") or "").strip().upper() != phase_name:
                    continue
                return

        options = [DecisionOption.create("None", payload={"action": "skip", "spend_yp": 0})]
        for spend in range(1, max_spend + 1):
            options.append(
                DecisionOption.create(
                    f"Spend {int(spend)} YP",
                    payload={"action": "spend", "spend_yp": int(spend)},
                )
            )
        ability_name = (
            str(source_sr.get("enhancement_piledriver_source", "") or "Piledriver").strip()
            or "Piledriver"
        )
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: spend up to {int(max_spend)} YP for +Damage on the bearer's melee weapons until end of phase.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": "piledriver",
                "ability_name": ability_name,
                "phase": "Fight phase",
                "phase_name": phase_name,
                "optional": True,
                "unit_id": root_id,
                "source_unit_id": source_unit_id,
                "model_id": model_id,
                "turn_owner": turn_owner_id,
                "turn": int(turn or 0),
            },
        )
        self.request_decision(request)

    def _on_shooting_targets_selected_iron_ambassador(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        if not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if not bool(getattr(root, "deployed", True)):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("enhancement_iron_ambassador"):
            return
        bearer = getattr(root, "_get_enhancement_bearer_model", lambda: None)()
        if bearer is None:
            return
        used_once = getattr(root, "has_used_unit_once_per_battle", None)
        if callable(used_once) and bool(used_once("iron_ambassador")):
            return
        army = root.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return
        pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
        if pe is None:
            return
        try:
            available_yp = int(getattr(pe, "yield_points", 0) or 0)
        except Exception:
            available_yp = 0
        if available_yp <= 0:
            return
        max_spend = max(0, min(3, int(available_yp or 0)))
        if max_spend <= 0:
            return
        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        if not owner_id or turn <= 0:
            return
        unit_id = str(get_entity_id(root) or "")
        model_id = str(get_entity_id(bearer) or "")
        if not unit_id or not model_id:
            return
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "iron_ambassador":
                    continue
                if str(ctx.get("unit_id", "") or "") != unit_id:
                    continue
                if str(ctx.get("turn_owner", "") or "") != owner_id:
                    continue
                if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                    continue
                return

        options = [DecisionOption.create("None", payload={"action": "skip", "spend_yp": 0})]
        for spend in range(1, max_spend + 1):
            options.append(
                DecisionOption.create(
                    f"Spend {int(spend)} YP",
                    payload={"action": "spend", "spend_yp": int(spend)},
                )
            )
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Iron Ambassador: spend up to 3 YP for +Damage on the bearer’s ranged weapons until end of phase.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "iron_ambassador",
                "ability_name": "Iron Ambassador",
                "phase": "Shooting phase",
                "optional": True,
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "model_id": model_id,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
            },
        )
        self.request_decision(request)

    def _attached_member_with_enhancement_flag(self, unit, flag_key: str):
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return None, None, {}
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = []
        if not members:
            members = [root]
        try:
            members = sorted(members, key=lambda u: str(get_entity_id(u) or ""))
        except Exception:
            members = list(members)
        key = str(flag_key or "").strip()
        if not key:
            return root, None, {}
        for member in members:
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if isinstance(sr, dict) and sr.get(key):
                return root, member, sr
        return root, None, {}

    @staticmethod
    def _unit_is_titanic(unit) -> bool:
        if unit is None:
            return False
        if bool(getattr(unit, "is_titanic", False)):
            return True
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            return bool(has_keyword("TITANIC"))
        return False

    @staticmethod
    def _unit_is_monster_or_vehicle(unit) -> bool:
        if unit is None:
            return False
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            try:
                return bool(has_keyword("MONSTER") or has_keyword("VEHICLE"))
            except Exception:
                pass
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            try:
                return bool(has_any_keyword("MONSTER") or has_any_keyword("VEHICLE"))
            except Exception:
                return False
        return False

    def _on_fight_unit_selected_furys_cage(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        if not self.is_fight_phase():
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        owner = getattr(army, "player", None) if army is not None else None
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return

        _root, source_member, source_sr = self._attached_member_with_enhancement_flag(
            root,
            "enhancement_furys_cage",
        )
        if source_member is None:
            return

        bearer = getattr(source_member, "_get_enhancement_bearer_model", lambda: None)()
        if bearer is None or not bool(getattr(bearer, "is_alive", True)):
            return

        source_unit_id = str(get_entity_id(source_member) or "")
        model_id = str(get_entity_id(bearer) or "")
        if not source_unit_id or not model_id:
            return

        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        owner_id = str(getattr(owner, "id", "") or "")
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() or "FIGHT_PHASE"
        if bool(source_sr.get("enhancement_furys_cage_active")):
            active_owner = str(source_sr.get("enhancement_furys_cage_turn_owner", "") or "")
            try:
                active_turn = int(source_sr.get("enhancement_furys_cage_turn", 0) or 0)
            except Exception:
                active_turn = 0
            active_phase = str(source_sr.get("enhancement_furys_cage_expires_phase", "") or "").strip().upper()
            if (
                (not active_owner or active_owner == owner_id)
                and (not active_turn or active_turn == turn)
                and (not active_phase or active_phase == phase_name)
            ):
                return

        ability_name = (
            str(source_sr.get("enhancement_furys_cage_source", "") or "Fury's Cage").strip()
            or "Fury's Cage"
        )
        self._queue_optional_ability_confirmation(
            player=owner,
            ability_key="furys_cage",
            ability_name=ability_name,
            message=f"Use {ability_name} for {getattr(bearer, 'name', 'Model')}?",
            context={
                "ability_name": ability_name,
                "phase": "Fight phase",
                "unit_id": source_unit_id,
                "source_unit_id": source_unit_id,
                "model_id": model_id,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
            },
            payload={
                "unit_id": source_unit_id,
                "source_unit_id": source_unit_id,
                "model_id": model_id,
            },
            instance_key=f"{model_id}:furys_cage:{int(turn or 0)}:{owner_id}",
        )

    def _on_fight_unit_selected_eye_of_spite(self, unit=None, selecting_player=None, **_kwargs) -> None:
        if unit is None:
            return
        if not self.is_fight_phase():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not root.is_alive() or not getattr(root, "deployed", True):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return
        owner = getattr(army, "player", None)
        if owner is None:
            return
        if selecting_player is not None and selecting_player is not owner:
            return
        drukhari_mgr = getattr(army, "drukhari_detachments", None)
        is_realspace_fn = getattr(drukhari_mgr, "is_realspace_raiders", None) if drukhari_mgr is not None else None
        if not bool(callable(is_realspace_fn) and is_realspace_fn()):
            return

        _root, source_member, source_sr = self._attached_member_with_enhancement_flag(
            root,
            "enhancement_eye_of_spite",
        )
        if source_member is None:
            return
        bearer = getattr(source_member, "_get_enhancement_bearer_model", lambda: None)()
        if bearer is None or not bool(getattr(bearer, "is_alive", True)):
            return
        source_unit_id = str(get_entity_id(source_member) or "")
        model_id = str(get_entity_id(bearer) or "")
        if not source_unit_id or not model_id:
            return
        owner_id = str(getattr(owner, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() or "FIGHT_PHASE"

        if bool(source_sr.get("enhancement_eye_of_spite_temporary_active", False)):
            active_owner = str(source_sr.get("enhancement_eye_of_spite_temporary_owner", "") or "")
            try:
                active_turn = int(source_sr.get("enhancement_eye_of_spite_temporary_turn", 0) or 0)
            except Exception:
                active_turn = 0
            active_phase = str(source_sr.get("enhancement_eye_of_spite_temporary_expires_phase", "") or "").strip().upper()
            if (
                (not active_owner or active_owner == owner_id)
                and (not active_turn or active_turn == turn)
                and (not active_phase or active_phase == phase_name)
            ):
                return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "eye_of_spite":
                    continue
                if str(ctx.get("source_unit_id", "") or "") != source_unit_id:
                    continue
                if str(ctx.get("turn_owner", "") or "") != owner_id:
                    continue
                if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                    continue
                return

        try:
            pain_token_cost = int(source_sr.get("enhancement_eye_of_spite_pain_token_cost", 1) or 1)
        except Exception:
            pain_token_cost = 1
        pain_token_cost = max(1, int(pain_token_cost))
        pfp = getattr(army, "power_from_pain", None)
        available_pain = int(getattr(pfp, "tokens", 0) or 0) if pfp is not None else 0
        if available_pain < pain_token_cost:
            return
        ability_name = str(source_sr.get("enhancement_eye_of_spite_source", "") or "Eye of Spite").strip() or "Eye of Spite"
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: spend {int(pain_token_cost)} Pain token to improve bearer melee Attacks and AP by 2 instead until end of phase?",
            player_id=getattr(owner, "id", None),
            options=[
                DecisionOption.create("None", payload={"action": "skip"}),
                DecisionOption.create(
                    f"Spend {int(pain_token_cost)} Pain token",
                    payload={"action": "spend_pain_token", "pain_token_cost": int(pain_token_cost)},
                ),
            ],
            context={
                "ability": "eye_of_spite",
                "ability_name": ability_name,
                "phase": "Fight phase",
                "optional": True,
                "source_unit_id": source_unit_id,
                "unit_id": source_unit_id,
                "model_id": model_id,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
                "pain_token_cost": int(pain_token_cost),
            },
        )
        self.request_decision(request)

    def _on_unit_shooting_resolved_quake_multigenerator(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        from ..decision_kinds import DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET

        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None:
            return
        attacker_player = attacker_root.get_parent_army().player
        if attacker_player is None or attacker_player is not self.get_current_player():
            return
        root, source_member, source_sr = self._attached_member_with_enhancement_flag(
            attacker_root,
            "enhancement_quake_multigenerator",
        )
        if source_member is None:
            return

        bearer = getattr(source_member, "_get_enhancement_bearer_model", lambda: None)()
        if bearer is None:
            return
        bearer_id = str(get_entity_id(bearer) or "")
        if not bearer_id:
            return

        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        owner_id = str(getattr(attacker_player, "id", "") or "")
        if turn <= 0 or not owner_id:
            return
        attacker_unit_id = str(get_entity_id(root) or "")
        if not attacker_unit_id:
            return

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "quake_multigenerator":
                    continue
                if str(ctx.get("attacker_unit_id", "") or "") != attacker_unit_id:
                    continue
                if str(ctx.get("turn_owner", "") or "") != owner_id:
                    continue
                if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                    continue
                return

        by_target = hit_models_by_target if isinstance(hit_models_by_target, dict) else {}

        def _bearer_hit_target(target_obj) -> bool:
            if not by_target:
                return True
            hit_models = by_target.get(target_obj)
            if hit_models is None:
                try:
                    target_root_local = target_obj.get_attached_unit_root()
                except Exception:
                    target_root_local = target_obj
                hit_models = by_target.get(target_root_local)
            if not hit_models:
                return False
            for hit_model in list(hit_models or []):
                if str(get_entity_id(hit_model) or "") == bearer_id:
                    return True
            return False

        candidates: list[Any] = []
        seen_targets: set[str] = set()
        for target_unit, hits in (hits_by_target or {}).items():
            if target_unit is None or int(hits or 0) <= 0:
                continue
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is None:
                continue
            target_id = str(get_entity_id(target_root) or "")
            if not target_id or target_id in seen_targets:
                continue
            seen_targets.add(target_id)
            if target_root.get_parent_army() == attacker_root.get_parent_army():
                continue
            if not target_root.is_alive():
                continue
            if self._unit_is_titanic(target_root):
                continue
            if not _bearer_hit_target(target_unit):
                continue
            candidates.append(target_root)

        if not candidates:
            return

        ability_name = str(source_sr.get("enhancement_quake_multigenerator_source", "") or "Quake Multigenerator").strip()
        if not ability_name:
            ability_name = "Quake Multigenerator"
        options = [
            DecisionOption.create(
                str(getattr(cand, "name", "Unit") or "Unit"),
                payload={"unit_id": get_entity_id(cand)},
            )
            for cand in list(candidates)
        ]
        if not options:
            return
        request = DecisionRequest.create(
            DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET,
            f"{ability_name}: select a non-TITANIC unit to suppress.",
            player_id=getattr(attacker_player, "id", None),
            options=options,
            context={
                "ability": "quake_multigenerator",
                "ability_name": ability_name,
                "attacker_unit_id": attacker_unit_id,
                "model_id": bearer_id,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
                "source_key": "enhancement_quake_multigenerator",
            },
        )
        self.request_decision(request)

    def _on_unit_shooting_resolved_graviton_vault(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        from ..decision_kinds import DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET

        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None:
            return
        attacker_player = attacker_root.get_parent_army().player
        if attacker_player is None or attacker_player is not self.get_current_player():
            return
        root, source_member, source_sr = self._attached_member_with_enhancement_flag(
            attacker_root,
            "enhancement_graviton_vault",
        )
        if source_member is None:
            return

        bearer = getattr(source_member, "_get_enhancement_bearer_model", lambda: None)()
        if bearer is None or not bool(getattr(bearer, "is_alive", True)):
            return
        bearer_id = str(get_entity_id(bearer) or "")
        if not bearer_id:
            return

        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        owner_id = str(getattr(attacker_player, "id", "") or "")
        if turn <= 0 or not owner_id:
            return
        attacker_unit_id = str(get_entity_id(root) or "")
        if not attacker_unit_id:
            return

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "graviton_vault_shooting":
                    continue
                if str(ctx.get("attacker_unit_id", "") or "") != attacker_unit_id:
                    continue
                if str(ctx.get("turn_owner", "") or "") != owner_id:
                    continue
                if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                    continue
                return

        by_target = hit_models_by_target if isinstance(hit_models_by_target, dict) else {}

        def _bearer_hit_target(target_obj) -> bool:
            if not by_target:
                return True
            hit_models = by_target.get(target_obj)
            if hit_models is None:
                try:
                    target_root_local = target_obj.get_attached_unit_root()
                except Exception:
                    target_root_local = target_obj
                hit_models = by_target.get(target_root_local)
            if not hit_models:
                return False
            for hit_model in list(hit_models or []):
                if str(get_entity_id(hit_model) or "") == bearer_id:
                    return True
            return False

        candidates: list[Any] = []
        seen_targets: set[str] = set()
        for target_unit, hits in (hits_by_target or {}).items():
            if target_unit is None or int(hits or 0) <= 0:
                continue
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is None:
                continue
            target_id = str(get_entity_id(target_root) or "")
            if not target_id or target_id in seen_targets:
                continue
            seen_targets.add(target_id)
            if target_root.get_parent_army() == attacker_root.get_parent_army():
                continue
            if not target_root.is_alive():
                continue
            if not self._unit_is_monster_or_vehicle(target_root):
                continue
            if not _bearer_hit_target(target_unit):
                continue
            candidates.append(target_root)

        if not candidates:
            return

        ability_name = str(source_sr.get("enhancement_graviton_vault_source", "") or "Graviton Vault").strip()
        if not ability_name:
            ability_name = "Graviton Vault"
        options = [
            DecisionOption.create(
                str(getattr(cand, "name", "Unit") or "Unit"),
                payload={"unit_id": get_entity_id(cand)},
            )
            for cand in list(candidates)
        ]
        if not options:
            return
        request = DecisionRequest.create(
            DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET,
            f"{ability_name}: select a MONSTER or VEHICLE unit to suppress.",
            player_id=getattr(attacker_player, "id", None),
            options=options,
            context={
                "ability": "graviton_vault_shooting",
                "ability_name": ability_name,
                "attacker_unit_id": attacker_unit_id,
                "model_id": bearer_id,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
                "source_key": "enhancement_graviton_vault",
                "attack_types": ["melee", "ranged"],
            },
        )
        self.request_decision(request)

    def _on_fight_attacks_resolved_graviton_vault(
        self,
        unit=None,
        attacker_unit=None,
        target_unit=None,
        hits_by_target=None,
        hit_models_by_target=None,
        **_kwargs,
    ) -> None:
        attacker_unit = attacker_unit if attacker_unit is not None else unit
        if attacker_unit is None:
            return
        if not self.is_fight_phase():
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None or not attacker_root.is_alive():
            return
        attacker_army = attacker_root.get_parent_army()
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
        if attacker_player is None:
            raise RuntimeError("Graviton Vault requires an attacker player.")

        if not hits_by_target:
            if target_unit is None:
                return
            hits_by_target = {target_unit: 1}

        root, source_member, source_sr = self._attached_member_with_enhancement_flag(
            attacker_root,
            "enhancement_graviton_vault",
        )
        if source_member is None:
            return
        bearer = getattr(source_member, "_get_enhancement_bearer_model", lambda: None)()
        if bearer is None or not bool(getattr(bearer, "is_alive", True)):
            return
        bearer_id = str(get_entity_id(bearer) or "")
        if not bearer_id:
            return

        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        attacker_unit_id = str(get_entity_id(root) or "")
        if not attacker_unit_id:
            return

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            from ..decision_kinds import DECISION_CHOOSE_POST_FIGHT_SUPPRESSION_TARGET

            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_POST_FIGHT_SUPPRESSION_TARGET:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "graviton_vault_fight":
                    continue
                if str(ctx.get("attacker_unit_id", "") or "") != attacker_unit_id:
                    continue
                if int(ctx.get("turn", 0) or 0) != int(current_turn or 0):
                    continue
                return

        by_target = hit_models_by_target if isinstance(hit_models_by_target, dict) else {}

        def _bearer_hit_target(target_obj) -> bool:
            if not by_target:
                return True
            hit_models = by_target.get(target_obj)
            if hit_models is None:
                try:
                    target_root_local = target_obj.get_attached_unit_root()
                except Exception:
                    target_root_local = target_obj
                hit_models = by_target.get(target_root_local)
            if not hit_models:
                return False
            for hit_model in list(hit_models or []):
                if str(get_entity_id(hit_model) or "") == bearer_id:
                    return True
            return False

        players = list(getattr(self, "players", []) or [])
        next_owner_id = ""
        expires_turn = int(current_turn or 0)
        if players:
            try:
                current_index = int(getattr(self, "current_player_index", 0) or 0)
            except Exception:
                current_index = 0
            next_index = (current_index + 1) % len(players)
            next_player = players[next_index]
            next_owner_id = str(getattr(next_player, "id", "") or "")
            starting_index = getattr(self, "battle_round_starting_player_index", None)
            try:
                wraps_battle_round = bool(next_index == int(starting_index)) if starting_index is not None else bool(
                    next_index <= current_index
                )
            except Exception:
                wraps_battle_round = bool(next_index <= current_index)
            if wraps_battle_round and current_turn > 0:
                expires_turn = int(current_turn + 1)

        candidates = []
        seen_targets: set[str] = set()
        for candidate, hits in list((hits_by_target or {}).items()):
            if candidate is None or int(hits or 0) <= 0:
                continue
            try:
                target_root = candidate.get_attached_unit_root()
            except Exception:
                target_root = candidate
            if target_root is None:
                continue
            target_id = str(get_entity_id(target_root) or "")
            if not target_id or target_id in seen_targets:
                continue
            seen_targets.add(target_id)
            if target_root.get_parent_army() == attacker_root.get_parent_army():
                continue
            if not target_root.is_alive():
                continue
            if not self._unit_is_monster_or_vehicle(target_root):
                continue
            if not _bearer_hit_target(candidate):
                continue
            candidates.append(target_root)
        if not candidates:
            return
        try:
            candidates = sorted(candidates, key=lambda u: str(get_entity_id(u) or ""))
        except Exception:
            candidates = list(candidates)
        options = [
            DecisionOption.create(
                str(getattr(candidate, "name", "Unit") or "Unit"),
                payload={"unit_id": get_entity_id(candidate)},
            )
            for candidate in list(candidates)
        ]
        if not options:
            return
        ability_name = str(source_sr.get("enhancement_graviton_vault_source", "") or "Graviton Vault").strip()
        if not ability_name:
            ability_name = "Graviton Vault"
        from ..decision_kinds import DECISION_CHOOSE_POST_FIGHT_SUPPRESSION_TARGET

        request = DecisionRequest.create(
            DECISION_CHOOSE_POST_FIGHT_SUPPRESSION_TARGET,
            f"{ability_name}: select a MONSTER or VEHICLE unit to suppress.",
            player_id=getattr(attacker_player, "id", None),
            options=options,
            context={
                "ability": "graviton_vault_fight",
                "attacker_unit_id": attacker_unit_id,
                "ability_name": ability_name,
                "model_id": bearer_id,
                "attack_types": ["melee", "ranged"],
                "expires_turn": int(expires_turn or 0),
                "expires_turn_owner": next_owner_id,
                "source_key": "enhancement_graviton_vault",
                "turn": int(current_turn or 0),
            },
        )
        self.request_decision(request)

    def _on_shooting_targets_selected_bastion_shield(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        if attacker_root is None:
            return
        attacker_army = attacker_root.get_parent_army()
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
        if attacker_player is None or attacker_player is not self.get_current_player():
            return
        try:
            attacker_models = list(attacker_root.get_attached_unit_models() or [])
        except Exception:
            attacker_models = list(getattr(attacker_root, "models", []) or [])
        attacker_models = [m for m in list(attacker_models or []) if bool(getattr(m, "is_alive", True))]
        if not attacker_models:
            return

        from ...utility.aura_utils import model_within_range_of_unit

        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        owner_id = str(getattr(attacker_player, "id", "") or "")
        if turn <= 0 or not owner_id:
            return

        try:
            unique_targets = sorted(
                {
                    str(get_entity_id(t.get_attached_unit_root() if hasattr(t, "get_attached_unit_root") else t) or ""):
                    (t.get_attached_unit_root() if hasattr(t, "get_attached_unit_root") else t)
                    for t in list(target_units or [])
                    if t is not None
                }.values(),
                key=lambda u: str(get_entity_id(u) or ""),
            )
        except Exception:
            unique_targets = []

        for target_root in list(unique_targets or []):
            if target_root is None:
                continue
            if target_root.get_parent_army() == attacker_root.get_parent_army():
                continue
            if not target_root.is_alive():
                continue
            try:
                if not bool(getattr(target_root, "deployed", True)):
                    continue
                if target_root.is_in_reserves() or target_root.is_embarked:
                    continue
            except Exception:
                pass

            _target_root, source_member, source_sr = self._attached_member_with_enhancement_flag(
                target_root,
                "enhancement_bastion_shield",
            )
            if source_member is None:
                continue
            try:
                base_range = int(source_sr.get("enhancement_bastion_shield_base_range", 12) or 12)
            except Exception:
                base_range = 12
            try:
                extended_range = int(source_sr.get("enhancement_bastion_shield_extended_range", 18) or 18)
            except Exception:
                extended_range = 18

            has_between = False
            for model in list(attacker_models or []):
                if not model_within_range_of_unit(model, target_root, float(extended_range), use_attached_aggregate=True):
                    continue
                if model_within_range_of_unit(model, target_root, float(base_range), use_attached_aggregate=True):
                    continue
                has_between = True
                break
            if not has_between:
                continue

            if bool(source_sr.get("enhancement_bastion_shield_extended_active")):
                sr_owner = str(source_sr.get("enhancement_bastion_shield_extended_turn_owner", "") or "")
                try:
                    sr_turn = int(source_sr.get("enhancement_bastion_shield_extended_turn", 0) or 0)
                except Exception:
                    sr_turn = 0
                phase_key = str(source_sr.get("enhancement_bastion_shield_extended_expires_phase", "") or "").strip().upper()
                if (not sr_owner or sr_owner == owner_id) and (not sr_turn or sr_turn == turn):
                    if not phase_key or phase_key == "SHOOTING_PHASE":
                        continue

            target_army = target_root.get_parent_army()
            target_player = getattr(target_army, "player", None) if target_army is not None else None
            if target_player is None:
                continue
            pe = getattr(target_army, "prioritised_efficiency", None) if target_army is not None else None
            if pe is None:
                continue
            try:
                if int(getattr(pe, "yield_points", 0) or 0) < 1:
                    continue
            except Exception:
                continue

            target_root_id = str(get_entity_id(target_root) or "")
            source_member_id = str(get_entity_id(source_member) or "")
            if not target_root_id:
                continue
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                exists = False
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if str(ctx.get("ability", "") or "") != "bastion_shield":
                        continue
                    if str(ctx.get("source_unit_id", "") or "") != target_root_id:
                        continue
                    if str(ctx.get("turn_owner", "") or "") != owner_id:
                        continue
                    if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                        continue
                    exists = True
                    break
                if exists:
                    continue

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Bastion Shield: spend 1 YP to extend AP worsening to 18\" for this Shooting phase?",
                player_id=getattr(target_player, "id", None),
                options=[
                    DecisionOption.create("None", payload={"action": "skip", "spend_yp": 0}),
                    DecisionOption.create("Spend 1 YP", payload={"action": "spend", "spend_yp": 1}),
                ],
                context={
                    "ability": "bastion_shield",
                    "ability_name": "Bastion Shield",
                    "phase": "Shooting phase",
                    "optional": True,
                    "unit_id": target_root_id,
                    "source_unit_id": target_root_id,
                    "source_member_unit_id": source_member_id,
                    "attacker_unit_id": str(get_entity_id(attacker_root) or ""),
                    "turn_owner": owner_id,
                    "turn": int(turn or 0),
                },
            )
            self.request_decision(request)

    def _on_shooting_targets_selected_grey_knights_sigil_of_exigence(
        self,
        attacking_unit=None,
        target_units=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        if attacker_root is None:
            return
        try:
            unique_targets = sorted(
                {
                    str(get_entity_id(t.get_attached_unit_root() if hasattr(t, "get_attached_unit_root") else t) or ""):
                    (t.get_attached_unit_root() if hasattr(t, "get_attached_unit_root") else t)
                    for t in list(target_units or [])
                    if t is not None
                }.values(),
                key=lambda u: str(get_entity_id(u) or ""),
            )
        except Exception:
            unique_targets = []
        for target_root in list(unique_targets or []):
            if target_root is None:
                continue
            try:
                if target_root.get_parent_army() == attacker_root.get_parent_army():
                    continue
            except Exception:
                continue
            target_army = target_root.get_parent_army()
            mgr = getattr(target_army, "grey_knights_detachments", None) if target_army is not None else None
            queue_fn = getattr(mgr, "queue_sanctic_sigil_of_exigence_for_target", None) if mgr is not None else None
            if callable(queue_fn):
                queue_fn(target_root, attacking_unit=attacker_root, game=self)

    def _on_shooting_targets_selected_geomantic_hunters(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        army = root.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if not bool(getattr(root, "deployed", True)):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        if not bool(getattr(root, "has_geomantic_hunters", lambda: False)()):
            return
        if not bool(getattr(root, "can_use_geomantic_hunters", lambda: False)()):
            return
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return
        owner_id = str(getattr(player, "id", "") or "")
        turn = int(getattr(self, "turn", 0) or 0)
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="geomantic_hunters",
            ability_name="Geomantic Hunters",
            message=f"Geomantic Hunters: activate for {getattr(root, 'name', 'Unit')}?",
            context={
                "ability_name": "Geomantic Hunters",
                "phase": "Shooting phase",
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
            },
            payload={
                "unit_id": unit_id,
                "source_unit_id": unit_id,
            },
            instance_key=f"{unit_id}:{turn}:{owner_id}:geomantic_hunters",
        )

    def _on_shooting_targets_selected_resource_transmutation(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        army = root.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if not bool(getattr(root, "deployed", True)):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass
        if not bool(getattr(root, "has_resource_transmutation", lambda: False)()):
            return
        model = getattr(root, "get_resource_transmutation_model", lambda: None)()
        if model is None or not getattr(model, "is_alive", True):
            return
        pe = getattr(army, "prioritised_efficiency", None)
        if pe is None:
            return
        try:
            if int(getattr(pe, "yield_points", 0) or 0) < 1:
                return
        except Exception:
            return
        owner_id = str(getattr(player, "id", "") or "")
        turn = int(getattr(self, "turn", 0) or 0)
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict):
            try:
                if (
                    str(sr.get("resource_transmutation_used_turn_owner", "") or "") == owner_id
                    and int(sr.get("resource_transmutation_used_turn", 0) or 0) == int(turn or 0)
                ):
                    return
            except Exception:
                pass
        unit_id = str(get_entity_id(root) or "")
        model_id = str(get_entity_id(model) or "")
        if not unit_id or not model_id:
            return
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="resource_transmutation",
            ability_name="Resource Transmutation",
            message=f"Resource Transmutation: spend 1 YP for {getattr(model, 'name', 'Model')}?",
            context={
                "ability_name": "Resource Transmutation",
                "phase": "Shooting phase",
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "model_id": model_id,
                "cost": 1,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
            },
            payload={
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "model_id": model_id,
                "cost": 1,
            },
            instance_key=f"{unit_id}:{turn}:{owner_id}:resource_transmutation",
        )

    def _on_shooting_targets_selected_optimal_application(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        del target_units
        if attacking_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        army = root.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if not bool(getattr(root, "deployed", True)):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass

        detachment_mgr = getattr(army, "leagues_of_votann_detachments", None) if army is not None else None
        eligible_fn = (
            getattr(detachment_mgr, "optimal_application_shooting_unit_eligible", None)
            if detachment_mgr is not None
            else None
        )
        if not callable(eligible_fn) or not bool(eligible_fn(root)):
            return

        pe = getattr(army, "prioritised_efficiency", None)
        if pe is None:
            return
        try:
            if int(getattr(pe, "yield_points", 0) or 0) < 1:
                return
        except Exception:
            return

        active_fn = getattr(root, "_optimal_application_active_for_shooting", None)
        if callable(active_fn) and bool(active_fn(game=self)):
            return

        owner_id = str(getattr(player, "id", "") or "")
        turn = int(getattr(self, "turn", 0) or 0)
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return
        self._queue_optional_ability_confirmation(
            player=player,
            ability_key="optimal_application",
            ability_name="Optimal Application",
            message=f"Optimal Application: spend 1 YP for {getattr(root, 'name', 'Unit')}?",
            context={
                "ability_name": "Optimal Application",
                "phase": "Shooting phase",
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "cost": 1,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
            },
            payload={
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "cost": 1,
            },
            instance_key=f"{unit_id}:{turn}:{owner_id}:optimal_application",
        )

    def _on_shooting_targets_selected_integrated_tactics(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not self.is_shooting_phase():
            return
        get_root = getattr(attacking_unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else attacking_unit
        if root is None:
            return
        is_alive_fn = getattr(root, "is_alive", None)
        if callable(is_alive_fn) and not bool(is_alive_fn()):
            return
        if not bool(getattr(root, "deployed", True)):
            return
        is_in_reserves_fn = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves_fn) and bool(is_in_reserves_fn()):
            return
        embarked = getattr(root, "is_embarked", False)
        if callable(embarked):
            embarked = embarked()
        if bool(embarked):
            return

        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return
        mgr = getattr(army, "genestealer_cults_detachments", None) if army is not None else None
        candidates_fn = (
            getattr(mgr, "integrated_tactics_target_candidates_for_unit", None)
            if mgr is not None
            else None
        )
        if not callable(candidates_fn):
            return
        candidates = list(candidates_fn(root, game=self) or [])
        if not candidates:
            # Fallback path for sparse test maps: use explicitly selected targets when available.
            target_eligible_fn = getattr(mgr, "integrated_tactics_target_eligible", None) if mgr is not None else None
            seen_ids = set()
            for target in list(target_units or []):
                if target is None:
                    continue
                target_get_root = getattr(target, "get_attached_unit_root", None)
                target_root = target_get_root() if callable(target_get_root) else target
                if target_root is None:
                    continue
                if callable(target_eligible_fn) and not bool(target_eligible_fn(root, target_root, game=self)):
                    continue
                target_id = str(get_entity_id(target_root) or "")
                if not target_id or target_id in seen_ids:
                    continue
                seen_ids.add(target_id)
                candidates.append(target_root)
        if not candidates:
            return

        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return
        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except (TypeError, ValueError):
            turn = 0
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "integrated_tactics":
                    continue
                if str(ctx.get("unit_id", "") or "") != unit_id:
                    continue
                if str(ctx.get("turn_owner", "") or "") != owner_id:
                    continue
                if int(ctx.get("turn", turn) or turn) != int(turn or 0):
                    continue
                return

        sorted_candidates = sorted(list(candidates), key=lambda c: str(maybe_entity_id(c) or ""))
        options = [DecisionOption.create("None", payload={"action": "skip"})]
        for target in sorted_candidates:
            options.append(
                DecisionOption.create(
                    str(getattr(target, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(target)},
                )
            )
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"Integrated Tactics: select overlapping-fire target for {getattr(root, 'name', 'Unit')} (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "integrated_tactics",
                "ability_name": "Integrated Tactics",
                "phase": "Shooting phase",
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
                "candidate_unit_ids": [str(get_entity_id(u) or "") for u in sorted_candidates],
                "optional": True,
            },
        )
        self.request_decision(request)

    def _on_shooting_targets_selected_martial_espionage(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        get_root = getattr(attacking_unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else attacking_unit
        if root is None:
            return
        is_alive_fn = getattr(root, "is_alive", None)
        if callable(is_alive_fn) and not bool(is_alive_fn()):
            return
        if not bool(getattr(root, "deployed", True)):
            return
        is_in_reserves_fn = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves_fn) and bool(is_in_reserves_fn()):
            return
        embarked = getattr(root, "is_embarked", False)
        if callable(embarked):
            embarked = embarked()
        if bool(embarked):
            return

        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return
        mgr = getattr(army, "genestealer_cults_detachments", None) if army is not None else None
        candidates_fn = getattr(mgr, "martial_espionage_source_candidates_for_shooting_unit", None) if mgr is not None else None
        if not callable(candidates_fn):
            return
        candidates = list(candidates_fn(root, game=self) or [])
        if not candidates:
            return

        target_unit_id = str(get_entity_id(root) or "")
        if not target_unit_id:
            return
        current_player = self.get_current_player()
        current_owner_id = str(getattr(current_player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except (TypeError, ValueError):
            turn = 0
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()

        for source_root, source_member, source_sr, bearer in candidates:
            source_root_id = str(get_entity_id(source_root) or "")
            source_member_id = str(get_entity_id(source_member) or source_root_id)
            if not source_root_id or not source_member_id:
                continue
            try:
                range_in = float(source_sr.get("enhancement_martial_espionage_range", 9.0) or 9.0)
            except (TypeError, ValueError):
                range_in = 9.0
            try:
                ap_bonus = int(source_sr.get("enhancement_martial_espionage_ap_bonus", 1) or 1)
            except (TypeError, ValueError):
                ap_bonus = 1
            source_name = str(
                source_sr.get("enhancement_martial_espionage_source", "")
                or "Martial Espionage"
            ).strip() or "Martial Espionage"
            source_model_id = str(get_entity_id(bearer) or "")
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="martial_espionage",
                ability_name="Martial Espionage",
                message=f"Martial Espionage: use {source_name} for {getattr(root, 'name', 'Unit')}?",
                context={
                    "ability_name": "Martial Espionage",
                    "phase_name": phase_name,
                    "unit_id": target_unit_id,
                    "target_unit_id": target_unit_id,
                    "source_unit_id": source_root_id,
                    "source_member_unit_id": source_member_id,
                    "source_model_id": source_model_id,
                    "range": float(range_in),
                    "ap_bonus": int(max(1, ap_bonus)),
                    "turn_owner": current_owner_id,
                    "turn": int(turn or 0),
                    "optional": True,
                },
                payload={
                    "unit_id": target_unit_id,
                    "target_unit_id": target_unit_id,
                    "source_unit_id": source_root_id,
                    "source_member_unit_id": source_member_id,
                    "source_model_id": source_model_id,
                    "range": float(range_in),
                    "ap_bonus": int(max(1, ap_bonus)),
                },
                instance_key=f"{source_member_id}:{target_unit_id}:{phase_name}:{turn}:{current_owner_id}",
            )

    @staticmethod
    def _clear_persecution_prospect_source_lock(unit) -> None:
        if unit is None:
            return
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "persecution_prospect_guerrilla_active",
            "persecution_prospect_guerrilla_target_unit_id",
            "persecution_prospect_guerrilla_turn_owner",
            "persecution_prospect_guerrilla_turn",
            "persecution_prospect_guerrilla_source",
        ):
            sr.pop(key, None)
        unit.special_rules = sr

    def _on_shooting_targets_selected_persecution_prospect(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        if not bool(getattr(root, "is_alive", lambda: False)()):
            return
        if not bool(getattr(root, "deployed", True)):
            return
        try:
            if root.is_in_reserves() or root.is_embarked:
                return
        except Exception:
            pass

        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return

        detachment_mgr = getattr(army, "leagues_of_votann_detachments", None) if army is not None else None
        eligible_source_fn = (
            getattr(detachment_mgr, "persecution_prospect_shooting_unit_eligible", None)
            if detachment_mgr is not None
            else None
        )
        if not callable(eligible_source_fn) or not bool(eligible_source_fn(root)):
            return

        is_target_eligible_fn = (
            getattr(detachment_mgr, "persecution_prospect_target_eligible", None)
            if detachment_mgr is not None
            else None
        )
        candidates = []
        seen_ids = set()
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            if target_root is None:
                continue
            if callable(is_target_eligible_fn):
                if not bool(is_target_eligible_fn(root, target_root)):
                    continue
            target_id = str(get_entity_id(target_root) or "")
            if not target_id or target_id in seen_ids:
                continue
            seen_ids.add(target_id)
            candidates.append(target_root)
        if not candidates:
            return

        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "persecution_prospect_guerrilla_adepts":
                    continue
                if str(ctx.get("unit_id", "") or "") != unit_id:
                    continue
                if str(ctx.get("turn_owner", "") or "") != owner_id:
                    continue
                if int(ctx.get("turn", turn) or turn) != int(turn or 0):
                    continue
                return

        options = [DecisionOption.create("None", payload={"action": "skip"})]
        for target in sorted(list(candidates), key=lambda u: str(maybe_entity_id(u) or "")):
            options.append(
                DecisionOption.create(
                    str(getattr(target, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(target)},
                )
            )
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"Assailed From Every Angle: select a target for {getattr(root, 'name', 'Unit')} (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "persecution_prospect_guerrilla_adepts",
                "ability_name": "Assailed From Every Angle",
                "phase": "Shooting phase",
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
                "candidate_unit_ids": [str(get_entity_id(u) or "") for u in sorted(list(candidates), key=lambda c: str(maybe_entity_id(c) or ""))],
            },
        )
        self.request_decision(request)

    def _on_unit_shooting_resolved_persecution_prospect(self, attacker_unit=None, hits_by_target=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("persecution_prospect_guerrilla_active")):
            return

        owner_id = str(sr.get("persecution_prospect_guerrilla_turn_owner", "") or "")
        target_id = str(sr.get("persecution_prospect_guerrilla_target_unit_id", "") or "")
        source_name = str(sr.get("persecution_prospect_guerrilla_source", "") or "Assailed From Every Angle").strip() or "Assailed From Every Angle"
        try:
            source_turn = int(sr.get("persecution_prospect_guerrilla_turn", 0) or 0)
        except Exception:
            source_turn = 0
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        current_player = self.get_current_player()
        current_owner_id = str(getattr(current_player, "id", "") or "")
        if not owner_id or not target_id or source_turn <= 0:
            self._clear_persecution_prospect_source_lock(root)
            return
        if int(source_turn) != int(current_turn or 0):
            self._clear_persecution_prospect_source_lock(root)
            return
        if current_owner_id and owner_id != current_owner_id:
            self._clear_persecution_prospect_source_lock(root)
            return

        target_root = None
        for target_unit, hits in list(dict(hits_by_target or {}).items()):
            if target_unit is None or int(hits or 0) <= 0:
                continue
            try:
                candidate = target_unit.get_attached_unit_root()
            except Exception:
                candidate = target_unit
            if candidate is None:
                continue
            if str(get_entity_id(candidate) or "") != target_id:
                continue
            target_root = candidate
            break

        if target_root is None:
            self._clear_persecution_prospect_source_lock(root)
            return

        target_sr = getattr(target_root, "special_rules", None)
        if not isinstance(target_sr, dict):
            target_sr = {}
        already_assailed = bool(target_sr.get("persecution_prospect_assailed_active")) and str(
            target_sr.get("persecution_prospect_assailed_owner", "") or ""
        ) == owner_id
        target_sr["persecution_prospect_assailed_active"] = True
        target_sr["persecution_prospect_assailed_owner"] = owner_id
        target_sr["persecution_prospect_assailed_turn"] = int(current_turn or 0)
        target_sr["persecution_prospect_assailed_source"] = source_name
        target_sr["persecution_prospect_assailed_expires_phase"] = "SHOOTING_PHASE"
        target_root.special_rules = target_sr

        attacker_player = getattr(root.get_parent_army(), "player", None) if hasattr(root, "get_parent_army") else None
        if already_assailed:
            apply_fn = getattr(target_root, "apply_pinned", None)
            if callable(apply_fn):
                apply_fn(
                    owner_id=owner_id,
                    turn=int(current_turn or 0),
                    source=source_name,
                    move_penalty=-2,
                    charge_penalty=-2,
                    expires_phase="SHOOTING_PHASE",
                )
            else:
                pinned_sr = getattr(target_root, "special_rules", None)
                if not isinstance(pinned_sr, dict):
                    pinned_sr = {}
                pinned_sr["pinned_active"] = True
                pinned_sr["pinned_owner"] = owner_id
                pinned_sr["pinned_turn"] = int(current_turn or 0)
                pinned_sr["pinned_source"] = source_name
                pinned_sr["pinned_move_penalty"] = -2
                pinned_sr["pinned_charge_penalty"] = -2
                pinned_sr["pinned_expires_phase"] = "SHOOTING_PHASE"
                target_root.special_rules = pinned_sr
            if attacker_player is not None:
                from ...utility.event_bus import append_action

                append_action(
                    attacker_player,
                    f"{source_name}: {getattr(target_root, 'name', 'Unit')} is pinned until the start of your next Shooting phase.",
                )
        else:
            if attacker_player is not None:
                from ...utility.event_bus import append_action

                append_action(
                    attacker_player,
                    f"{source_name}: {getattr(target_root, 'name', 'Unit')} is assailed until the start of your next Shooting phase.",
                )

        self._clear_persecution_prospect_source_lock(root)

    def _on_unit_shooting_resolved_writ_of_acquisition(self, attacker_unit=None, hits_by_target=None, **_kwargs) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        if root is None:
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return
        detachment_mgr = getattr(army, "leagues_of_votann_detachments", None) if army is not None else None
        gain_fn = getattr(detachment_mgr, "writ_of_acquisition_gain", None) if detachment_mgr is not None else None
        if not callable(gain_fn):
            return
        gain_amount, reason = gain_fn(root, hits_by_target, game=self)
        if int(gain_amount or 0) <= 0:
            return
        pe = getattr(army, "prioritised_efficiency", None)
        if pe is None:
            return
        delta = int(getattr(pe, "add_yield_points", lambda _a, game=None: 0)(int(gain_amount), game=self) or 0)
        if delta <= 0:
            return
        event_system = getattr(self, "event_system", None)
        if event_system is not None:
            event_system.publish(
                "prioritised_efficiency_updated",
                player=player,
                game=self,
                delta=int(delta),
                mode=getattr(pe, "mode", None),
                yield_points=int(getattr(pe, "yield_points", 0) or 0),
                reason=str(reason or "Writ of Acquisition"),
            )
        from ...utility.event_bus import append_action

        ability_name = str(reason or "Writ of Acquisition").strip() or "Writ of Acquisition"
        append_action(player, f"{ability_name}: gained {int(delta)} YP.")

    def _on_unit_shooting_resolved_surgical_saboteur(self, attacker_unit=None, hits_by_target=None, **_kwargs) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        if root is None:
            return
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        player = getattr(army, "player", None) if army is not None else None
        if player is None or player is not self.get_current_player():
            return
        detachment_mgr = getattr(army, "leagues_of_votann_detachments", None) if army is not None else None
        if detachment_mgr is None or not bool(getattr(detachment_mgr, "is_persecution_prospect", lambda: False)()):
            return
        source_root, source_member, source_sr = detachment_mgr._attached_member_with_special_rule(
            root,
            "enhancement_surgical_saboteur",
        )
        if source_root is None or source_member is None or not isinstance(source_sr, dict):
            return
        if bool(source_sr.get("enhancement_surgical_saboteur_requires_bearer_alive", True)):
            bearer = getattr(source_member, "_get_enhancement_bearer_model", lambda: None)()
            bearer_alive = getattr(bearer, "is_alive", False) if bearer is not None else False
            if bearer is None or not bool(bearer_alive() if callable(bearer_alive) else bearer_alive):
                return
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        owner_id = str(getattr(player, "id", "") or "")
        attacker_unit_id = str(get_entity_id(source_root) or "")
        if not attacker_unit_id or not owner_id or turn <= 0:
            return
        queue = getattr(self, "decision_queue", None)
        ability_name = str(source_sr.get("enhancement_surgical_saboteur_source", "") or "Surgical Saboteur").strip()
        if not ability_name:
            ability_name = "Surgical Saboteur"
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "post_shoot_pinned":
                    continue
                if str(ctx.get("ability_name", "") or "") != ability_name:
                    continue
                if str(ctx.get("attacker_unit_id", "") or "") != attacker_unit_id:
                    continue
                if str(ctx.get("turn_owner", "") or "") != owner_id:
                    continue
                if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                    continue
                return

        candidates: list[Any] = []
        seen_targets: set[str] = set()
        for target_unit, hits in list((hits_by_target or {}).items()):
            if target_unit is None or int(hits or 0) <= 0:
                continue
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is None:
                continue
            target_id = str(get_entity_id(target_root) or "")
            if not target_id or target_id in seen_targets:
                continue
            seen_targets.add(target_id)
            if target_root.get_parent_army() == source_root.get_parent_army():
                continue
            if not bool(getattr(target_root, "is_alive", lambda: True)()):
                continue
            if not self._unit_is_monster_or_vehicle(target_root):
                continue
            candidates.append(target_root)
        if not candidates:
            return
        candidates = sorted(candidates, key=lambda unit: str(get_entity_id(unit) or ""))
        options = [
            DecisionOption.create(
                str(getattr(candidate, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(candidate)},
            )
            for candidate in list(candidates)
        ]
        if not options:
            return
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a MONSTER or VEHICLE unit to pin.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "post_shoot_pinned",
                "ability_name": ability_name,
                "attacker_unit_id": attacker_unit_id,
                "source_unit_id": attacker_unit_id,
                "move_penalty": int(source_sr.get("enhancement_surgical_saboteur_move_penalty", -2) or -2),
                "charge_penalty": int(source_sr.get("enhancement_surgical_saboteur_charge_penalty", -2) or -2),
                "expires_phase": str(
                    source_sr.get("enhancement_surgical_saboteur_expires_phase", "") or "SHOOTING_PHASE"
                ).strip().upper()
                or "SHOOTING_PHASE",
                "include_keywords_any": list(
                    source_sr.get("enhancement_surgical_saboteur_target_keywords_any", []) or []
                ),
                "candidate_unit_ids": [str(get_entity_id(candidate) or "") for candidate in list(candidates)],
                "turn_owner": owner_id,
                "turn": int(turn or 0),
            },
        )
        self.request_decision(request)

    def _on_unit_shooting_resolved_resource_transmutation(self, attacker_unit=None, killing_models_by_target=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        model_id = str(sr.get("resource_transmutation_active_model_id", "") or "")
        owner_id = str(sr.get("resource_transmutation_owner", "") or "")
        try:
            source_turn = int(sr.get("resource_transmutation_turn", 0) or 0)
        except Exception:
            source_turn = 0
        if not model_id or not owner_id or source_turn <= 0:
            return
        turn = int(getattr(self, "turn", 0) or 0)
        if source_turn != turn:
            return
        current_player = self.get_current_player()
        if current_player is None or str(getattr(current_player, "id", "") or "") != owner_id:
            return
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "SHOOTING_PHASE":
            return

        killed_by_active_model = False
        kills_map = dict(killing_models_by_target or {})
        for target_unit, killer_models in list(kills_map.items()):
            if target_unit is None:
                continue
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                target_root = target_unit
            if target_root is None:
                continue
            if bool(getattr(target_root, "is_alive", lambda: True)()):
                continue
            for killer in list(killer_models or []):
                killer_id = str(get_entity_id(killer) or "")
                if killer_id and killer_id == model_id:
                    killed_by_active_model = True
                    break
            if killed_by_active_model:
                break
        if not killed_by_active_model:
            return
        try:
            if (
                str(sr.get("resource_transmutation_gain_resolved_turn_owner", "") or "") == owner_id
                and int(sr.get("resource_transmutation_gain_resolved_turn", 0) or 0) == int(turn or 0)
            ):
                return
        except Exception:
            pass

        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "resource_transmutation_gain":
                    continue
                if str(ctx.get("unit_id", "") or "") != unit_id:
                    continue
                if str(ctx.get("turn_owner", "") or "") != owner_id:
                    continue
                if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                    continue
                return

        army = root.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        if player is None:
            return
        ability_name = str(sr.get("resource_transmutation_source", "") or "Resource Transmutation").strip() or "Resource Transmutation"
        options = [
            DecisionOption.create("None", payload={"action": "skip", "gain_yp": 0}),
            DecisionOption.create("Gain 1 YP", payload={"action": "gain", "gain_yp": 1}),
            DecisionOption.create("Gain 2 YP", payload={"action": "gain", "gain_yp": 2}),
        ]
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: gain up to 2 YP.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "resource_transmutation_gain",
                "ability_name": ability_name,
                "phase": "Shooting phase",
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "model_id": model_id,
                "turn_owner": owner_id,
                "turn": int(turn or 0),
                "optional": True,
            },
        )
        self.request_decision(request)

    def _unit_total_wounds_for_repair_barge(self, unit) -> int:
        if unit is None:
            return 0
        try:
            models = list(unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        total = 0
        for model in list(models or []):
            if model is None:
                continue
            try:
                alive_attr = getattr(model, "is_alive", True)
                is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            except Exception:
                is_alive = True
            if not is_alive:
                continue
            try:
                total += int(getattr(model, "wounds", 0) or 0)
            except Exception:
                continue
        return int(total)

    def _unit_is_necron_warriors_for_repair_barge(self, unit) -> bool:
        if unit is None:
            return False
        try:
            matcher = getattr(unit, "_unit_matches_keyword_phrase", None)
            if callable(matcher) and (
                bool(matcher(unit, "NECRON WARRIORS")) or bool(matcher(unit, "NECRONS WARRIORS"))
            ):
                return True
        except Exception:
            pass
        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any("NECRON WARRIORS")):
                    return True
            except Exception:
                pass
            try:
                if bool(has_any("NECRONS WARRIORS")):
                    return True
            except Exception:
                pass
            try:
                if (bool(has_any("NECRON")) or bool(has_any("NECRONS"))) and bool(has_any("WARRIORS")):
                    return True
            except Exception:
                pass
        return False

    def _repair_barge_model_used_this_turn(self, source_unit, model_id: str, *, turn: int, turn_owner_id: str) -> bool:
        if source_unit is None or not model_id:
            return False
        sr = getattr(source_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        used = sr.get("repair_barge_model_used_turn_by_id")
        if not isinstance(used, dict):
            return False
        entry = used.get(str(model_id))
        if not isinstance(entry, dict):
            return False
        try:
            used_turn = int(entry.get("turn", -1))
        except Exception:
            return False
        if used_turn != int(turn):
            return False
        used_owner = str(entry.get("turn_owner_id", "") or "")
        if turn_owner_id and used_owner and used_owner != str(turn_owner_id):
            return False
        return True

    def _mark_repair_barge_model_used_this_turn(self, source_unit, model_id: str, *, turn: int, turn_owner_id: str) -> None:
        if source_unit is None or not model_id:
            return
        sr = getattr(source_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        used = sr.get("repair_barge_model_used_turn_by_id")
        if not isinstance(used, dict):
            used = {}
        updated = dict(used)
        updated[str(model_id)] = {
            "turn": int(turn),
            "turn_owner_id": str(turn_owner_id or ""),
        }
        sr["repair_barge_model_used_turn_by_id"] = updated
        source_unit.special_rules = sr

    def _repair_barge_target_selected_this_turn(self, target_unit, *, turn: int, turn_owner_id: str) -> bool:
        if target_unit is None:
            return False
        sr = getattr(target_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        try:
            selected_turn = int(sr.get("repair_barge_selected_turn", -1))
        except Exception:
            return False
        if selected_turn != int(turn):
            return False
        selected_owner = str(sr.get("repair_barge_selected_turn_owner", "") or "")
        if turn_owner_id and selected_owner and selected_owner != str(turn_owner_id):
            return False
        return True

    def _mark_repair_barge_target_selected_this_turn(self, target_unit, *, turn: int, turn_owner_id: str) -> None:
        if target_unit is None:
            return
        sr = getattr(target_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["repair_barge_selected_turn"] = int(turn)
        sr["repair_barge_selected_turn_owner"] = str(turn_owner_id or "")
        target_unit.special_rules = sr

    def _iter_repair_barge_sources_for_player(self, player, *, turn: int, turn_owner_id: str) -> list[dict]:
        if player is None:
            return []
        army = self._get_player_army(player)
        if army is None:
            return []
        out: list[dict] = []

        def _model_sort_key(model):
            try:
                return str(get_entity_id(model))
            except Exception:
                return str(getattr(model, "name", "") or "")

        for source_root in list(self._iter_unique_army_roots(army) or []):
            if source_root is None:
                continue
            if not self._unit_is_active_for_reactive_trigger(source_root):
                continue
            try:
                source_models = list(source_root.get_attached_unit_models() or [])
            except Exception:
                source_models = list(getattr(source_root, "models", []) or [])
            alive_models = [m for m in list(source_models or []) if bool(getattr(m, "is_alive", True))]
            if not alive_models:
                continue
            for source_model in sorted(alive_models, key=_model_sort_key):
                model_owner = getattr(source_model, "parent_unit", None) or source_root
                spec_fn = getattr(model_owner, "model_repair_barge_specs", None)
                if not callable(spec_fn):
                    continue
                try:
                    specs = list(spec_fn(source_model) or [])
                except Exception:
                    specs = []
                for spec in list(specs or []):
                    try:
                        range_value = float(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0.0
                    if range_value <= 0:
                        continue
                    model_id = str(get_entity_id(source_model) or "")
                    if not model_id:
                        continue
                    if self._repair_barge_model_used_this_turn(
                        source_root,
                        model_id,
                        turn=int(turn),
                        turn_owner_id=str(turn_owner_id or ""),
                    ):
                        continue
                    out.append(
                        {
                            "source_root": source_root,
                            "source_model": source_model,
                            "model_owner": model_owner,
                            "model_id": model_id,
                            "ability_name": str(spec.get("source", "") or "Repair Barge").strip() or "Repair Barge",
                            "range": float(range_value),
                        }
                    )
        out.sort(key=lambda item: (str(get_entity_id(item["source_root"]) or ""), str(item["model_id"])))
        return out

    def _queue_repair_barge_decision(
        self,
        *,
        player,
        source_root,
        source_model,
        ability_name: str,
        range_inches: float,
        candidates: list,
        turn: int,
        turn_owner_id: str,
    ) -> DecisionRequest | None:
        if player is None or source_root is None or source_model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        source_unit_id = str(get_entity_id(source_root) or "")
        source_model_id = str(get_entity_id(source_model) or "")
        if not source_unit_id or not source_model_id:
            return None

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "repair_barge":
                    continue
                if str(ctx.get("source_unit_id", "") or "") != source_unit_id:
                    continue
                if str(ctx.get("model_id", "") or "") != source_model_id:
                    continue
                if str(ctx.get("turn_owner", "") or "") != str(turn_owner_id or ""):
                    continue
                if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                    continue
                return None

        def _unit_sort_key(unit):
            try:
                return str(get_entity_id(unit))
            except Exception:
                return str(getattr(unit, "name", "") or "")

        options = [DecisionOption.create("None", payload={"action": "skip"})]
        allowed_target_ids: list[str] = []
        for cand in sorted(list(candidates or []), key=_unit_sort_key):
            if cand is None:
                continue
            target_id = str(get_entity_id(cand) or "")
            if not target_id or target_id in allowed_target_ids:
                continue
            allowed_target_ids.append(target_id)
            options.append(
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": target_id},
                )
            )
        if len(options) <= 1:
            return None

        context = {
            "ability": "repair_barge",
            "ability_name": str(ability_name or "Repair Barge").strip() or "Repair Barge",
            "phase": str(getattr(getattr(self, "phase", None), "name", "") or "").replace("_", " ").title() or "Phase",
            "optional": True,
            "source_unit_id": source_unit_id,
            "unit_id": source_unit_id,
            "model_id": source_model_id,
            "range": float(range_inches),
            "allowed_target_unit_ids": list(allowed_target_ids),
            "turn_owner": str(turn_owner_id or ""),
            "turn": int(turn or 0),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{context['ability_name']}: select one friendly NECRON WARRIORS unit to activate Reanimation Protocols (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context=context,
        )
        self.request_decision(request)
        return request

    def _capture_repair_barge_snapshot(self, *, attacker_root, target_units, snapshot_attr: str) -> None:
        if attacker_root is None or not target_units:
            return
        attacker_army = attacker_root.get_parent_army() if hasattr(attacker_root, "get_parent_army") else None
        current_player = self.get_current_player()
        turn_owner_id = str(getattr(current_player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        if turn <= 0:
            return

        snapshots = getattr(self, snapshot_attr, None)
        if not isinstance(snapshots, dict):
            snapshots = {}
            setattr(self, snapshot_attr, snapshots)
        existing = dict(snapshots.get(attacker_root, {}) or {})

        seen_targets: set[str] = set()
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            if target_root is None:
                continue
            target_id = str(get_entity_id(target_root) or "")
            if not target_id or target_id in seen_targets:
                continue
            seen_targets.add(target_id)
            if not self._unit_is_active_for_reactive_trigger(target_root):
                continue
            if not self._unit_is_necron_warriors_for_repair_barge(target_root):
                continue
            target_army = target_root.get_parent_army() if hasattr(target_root, "get_parent_army") else None
            if target_army is None or target_army is attacker_army:
                continue
            target_player = getattr(target_army, "player", None)
            if target_player is None:
                continue
            if self._repair_barge_target_selected_this_turn(
                target_root,
                turn=int(turn),
                turn_owner_id=str(turn_owner_id or ""),
            ):
                continue
            has_source = False
            for source in list(
                self._iter_repair_barge_sources_for_player(
                    target_player,
                    turn=int(turn),
                    turn_owner_id=str(turn_owner_id or ""),
                )
                or []
            ):
                source_root = source.get("source_root")
                source_model = source.get("source_model")
                range_value = float(source.get("range", 0.0) or 0.0)
                if source_root is None or source_model is None or range_value <= 0:
                    continue
                try:
                    if bool(source_root._model_within_range_of_unit(source_model, target_root, range_value)):
                        has_source = True
                        break
                except Exception:
                    continue
            if not has_source:
                continue
            existing[target_root] = int(self._unit_total_wounds_for_repair_barge(target_root))

        if existing:
            snapshots[attacker_root] = existing

    def _queue_repair_barge_for_affected_targets(self, *, attacker_root, affected_targets: list) -> None:
        if attacker_root is None or not affected_targets:
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        attacker_army = attacker_root.get_parent_army() if hasattr(attacker_root, "get_parent_army") else None
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
        current_player = self.get_current_player()
        turn_owner_id = str(getattr(current_player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        if turn <= 0:
            return

        by_player: dict[Any, list[Any]] = {}
        for target_root in list(affected_targets or []):
            if target_root is None:
                continue
            target_army = target_root.get_parent_army() if hasattr(target_root, "get_parent_army") else None
            target_player = getattr(target_army, "player", None) if target_army is not None else None
            if target_player is None:
                continue
            if attacker_player is not None and target_player is attacker_player:
                continue
            by_player.setdefault(target_player, []).append(target_root)

        for player, targets in list(by_player.items()):
            unique_targets: dict[str, Any] = {}
            for target in list(targets or []):
                tid = str(get_entity_id(target) or "")
                if tid:
                    unique_targets[tid] = target
            ordered_targets = [unique_targets[k] for k in sorted(unique_targets.keys())]
            if not ordered_targets:
                continue
            for source in list(
                self._iter_repair_barge_sources_for_player(
                    player,
                    turn=int(turn),
                    turn_owner_id=str(turn_owner_id or ""),
                )
                or []
            ):
                source_root = source.get("source_root")
                source_model = source.get("source_model")
                ability_name = str(source.get("ability_name", "") or "Repair Barge")
                range_value = float(source.get("range", 0.0) or 0.0)
                if source_root is None or source_model is None or range_value <= 0:
                    continue
                candidates: list[Any] = []
                for target_root in list(ordered_targets):
                    if target_root is None:
                        continue
                    if self._repair_barge_target_selected_this_turn(
                        target_root,
                        turn=int(turn),
                        turn_owner_id=str(turn_owner_id or ""),
                    ):
                        continue
                    try:
                        in_range = bool(source_root._model_within_range_of_unit(source_model, target_root, range_value))
                    except Exception:
                        in_range = False
                    if not in_range:
                        continue
                    candidates.append(target_root)
                if not candidates:
                    continue
                self._queue_repair_barge_decision(
                    player=player,
                    source_root=source_root,
                    source_model=source_model,
                    ability_name=ability_name,
                    range_inches=float(range_value),
                    candidates=candidates,
                    turn=int(turn),
                    turn_owner_id=str(turn_owner_id or ""),
                )

    def _on_shooting_targets_selected_repair_barge(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        if attacker_root is None:
            return
        self._capture_repair_barge_snapshot(
            attacker_root=attacker_root,
            target_units=list(target_units or []),
            snapshot_attr="_repair_barge_shooting_snapshot",
        )

    def _on_unit_shooting_resolved_repair_barge(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None:
            return
        snapshots = getattr(self, "_repair_barge_shooting_snapshot", None)
        if not isinstance(snapshots, dict):
            return
        snapshot = dict(snapshots.pop(attacker_root, {}) or {})
        if not snapshot:
            return
        affected: list[Any] = []
        for target_root, before in list(snapshot.items()):
            if target_root is None:
                continue
            after = int(self._unit_total_wounds_for_repair_barge(target_root))
            if int(after or 0) < int(before or 0):
                affected.append(target_root)
        if not affected:
            return
        self._queue_repair_barge_for_affected_targets(attacker_root=attacker_root, affected_targets=affected)

    def _on_fight_targets_selected_repair_barge(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        if attacker_root is None:
            return
        self._capture_repair_barge_snapshot(
            attacker_root=attacker_root,
            target_units=list(target_units or []),
            snapshot_attr="_repair_barge_fight_snapshot",
        )

    def _on_fight_sequence_complete_repair_barge(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        try:
            attacker_root = unit.get_attached_unit_root()
        except Exception:
            attacker_root = unit
        if attacker_root is None:
            return
        snapshots = getattr(self, "_repair_barge_fight_snapshot", None)
        if not isinstance(snapshots, dict):
            return
        snapshot = dict(snapshots.pop(attacker_root, {}) or {})
        if not snapshot:
            return
        affected: list[Any] = []
        for target_root, before in list(snapshot.items()):
            if target_root is None:
                continue
            after = int(self._unit_total_wounds_for_repair_barge(target_root))
            if int(after or 0) < int(before or 0):
                affected.append(target_root)
        if not affected:
            return
        self._queue_repair_barge_for_affected_targets(attacker_root=attacker_root, affected_targets=affected)

    def _iter_unique_army_roots(self, army) -> list:
        if army is None:
            return []
        roots: dict[str, Any] = {}
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            rid = str(get_entity_id(root) or "")
            if not rid:
                continue
            roots[rid] = root
        out = list(roots.values())
        try:
            out.sort(key=lambda u: str(get_entity_id(u) or ""))
        except Exception:
            pass
        return out

    def _unit_is_active_for_reactive_trigger(self, unit) -> bool:
        if unit is None:
            return False
        if not bool(getattr(unit, "is_alive", lambda: False)()):
            return False
        if not bool(getattr(unit, "deployed", True)):
            return False
        try:
            if unit.is_in_reserves() or unit.is_embarked:
                return False
        except Exception:
            pass
        return True

    def _unit_is_death_guard(self, unit) -> bool:
        if unit is None:
            return False
        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any("DEATH GUARD")):
                    return True
            except Exception:
                pass
        has_kw = getattr(unit, "has_keyword", None)
        if callable(has_kw):
            try:
                if bool(has_kw("DEATH GUARD")):
                    return True
            except Exception:
                pass
        return str(getattr(unit, "faction", "") or "").strip().upper() == "DEATH GUARD"

    def _unit_is_engaged_with_enemy(self, unit) -> bool:
        if unit is None:
            return False
        game_map = getattr(self, "map", None)
        if game_map is None:
            return False
        try:
            enemies = list(game_map.get_enemy_units(unit) or [])
        except Exception:
            enemies = []
        seen: set[str] = set()
        for enemy in enemies:
            if enemy is None:
                continue
            try:
                enemy_root = enemy.get_attached_unit_root()
            except Exception:
                enemy_root = enemy
            if enemy_root is None or not bool(getattr(enemy_root, "is_alive", lambda: False)()):
                continue
            eid = str(get_entity_id(enemy_root) or "")
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            try:
                if game_map.is_within_engagement_range(unit, enemy_root):
                    return True
            except Exception:
                continue
        return False

    def _on_fight_targets_selected_boon_of_death(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_fight_phase():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return

        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        if attacker_root is None:
            return
        attacker_army = attacker_root.get_parent_army()
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None

        try:
            from ...utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return

        target_roots: list[Any] = []
        seen_targets: set[str] = set()
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            if target_root is None:
                continue
            tid = str(get_entity_id(target_root) or "")
            if not tid or tid in seen_targets:
                continue
            seen_targets.add(tid)
            if not self._unit_is_active_for_reactive_trigger(target_root):
                continue
            if attacker_army is not None and target_root.get_parent_army() is attacker_army:
                continue
            target_roots.append(target_root)
        if not target_roots:
            return

        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0

        queue = getattr(self, "decision_queue", None)

        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            if attacker_player is not None and player is attacker_player:
                continue
            army = self._get_player_army(player)
            if army is None:
                continue
            for source_root in list(self._iter_unique_army_roots(army) or []):
                if source_root is None:
                    continue
                if not self._unit_is_active_for_reactive_trigger(source_root):
                    continue
                if not bool(getattr(source_root, "has_boon_of_death", lambda: False)()):
                    continue
                if not bool(getattr(source_root, "can_use_lord_of_death_guard", lambda **_k: False)(game=self)):
                    continue

                source_id = str(get_entity_id(source_root) or "")
                attacker_id = str(get_entity_id(attacker_root) or "")
                if not source_id or not attacker_id:
                    continue
                already_pending = False
                if queue is not None and hasattr(queue, "list"):
                    for req in list(queue.list() or []):
                        if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                            continue
                        ctx = dict(getattr(req, "context", {}) or {})
                        if str(ctx.get("ability", "") or "") != "boon_of_death":
                            continue
                        if str(ctx.get("source_unit_id", "") or "") != source_id:
                            continue
                        if str(ctx.get("attacker_unit_id", "") or "") != attacker_id:
                            continue
                        if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                            continue
                        already_pending = True
                        break
                if already_pending:
                    continue

                candidates: list[Any] = []
                for target_root in list(target_roots or []):
                    if target_root.get_parent_army() is not army:
                        continue
                    if not self._unit_is_death_guard(target_root):
                        continue
                    try:
                        if unit_within_range_of_unit(source_root, target_root, 6.0, use_attached_aggregate=True):
                            candidates.append(target_root)
                    except Exception:
                        continue
                if not candidates:
                    continue

                try:
                    candidates.sort(key=lambda u: str(get_entity_id(u) or ""))
                except Exception:
                    pass

                options = [DecisionOption.create("None", payload={"action": "skip"})]
                for cand in candidates:
                    options.append(
                        DecisionOption.create(
                            str(getattr(cand, "name", "Unit") or "Unit"),
                            payload={"target_unit_id": get_entity_id(cand)},
                        )
                    )
                if len(options) <= 1:
                    continue

                request = DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    "Boon of Death: select a friendly unit to affect (or None).",
                    player_id=getattr(player, "id", None),
                    options=options,
                    context={
                        "ability": "boon_of_death",
                        "ability_name": "Boon of Death",
                        "source_unit_id": source_id,
                        "attacker_unit_id": attacker_id,
                        "turn": int(turn or 0),
                        "optional": True,
                    },
                )
                self.request_decision(request)

    def _on_shooting_targets_selected_inflamed_reprisal(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_shooting_phase():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return

        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        if attacker_root is None:
            return
        attacker_army = attacker_root.get_parent_army()
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None

        try:
            from ...utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return

        targeted_roots: list[Any] = []
        seen_targets: set[str] = set()
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            if target_root is None:
                continue
            tid = str(get_entity_id(target_root) or "")
            if not tid or tid in seen_targets:
                continue
            seen_targets.add(tid)
            if not self._unit_is_active_for_reactive_trigger(target_root):
                continue
            if attacker_army is not None and target_root.get_parent_army() is attacker_army:
                continue
            targeted_roots.append(target_root)
        if not targeted_roots:
            return

        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0

        queue = getattr(self, "decision_queue", None)

        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            if attacker_player is not None and player is attacker_player:
                continue
            army = self._get_player_army(player)
            if army is None:
                continue
            for source_root in list(self._iter_unique_army_roots(army) or []):
                if source_root is None:
                    continue
                if not self._unit_is_active_for_reactive_trigger(source_root):
                    continue
                if not bool(getattr(source_root, "has_inflamed_reprisal", lambda: False)()):
                    continue
                if not bool(getattr(source_root, "can_use_lord_of_death_guard", lambda **_k: False)(game=self)):
                    continue

                source_id = str(get_entity_id(source_root) or "")
                attacker_id = str(get_entity_id(attacker_root) or "")
                if not source_id or not attacker_id:
                    continue
                already_pending = False
                if queue is not None and hasattr(queue, "list"):
                    for req in list(queue.list() or []):
                        if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                            continue
                        ctx = dict(getattr(req, "context", {}) or {})
                        if str(ctx.get("ability", "") or "") != "inflamed_reprisal":
                            continue
                        if str(ctx.get("source_unit_id", "") or "") != source_id:
                            continue
                        if str(ctx.get("attacker_unit_id", "") or "") != attacker_id:
                            continue
                        if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                            continue
                        already_pending = True
                        break
                if already_pending:
                    continue

                candidates: list[Any] = []
                for target_root in list(targeted_roots or []):
                    if target_root.get_parent_army() is not army:
                        continue
                    if not self._unit_is_death_guard(target_root):
                        continue
                    if bool(getattr(target_root, "is_battle_shocked", lambda: False)()):
                        continue
                    try:
                        if not unit_within_range_of_unit(source_root, target_root, 6.0, use_attached_aggregate=True):
                            continue
                    except Exception:
                        continue
                    candidates.append(target_root)
                if not candidates:
                    continue

                try:
                    candidates.sort(key=lambda u: str(get_entity_id(u) or ""))
                except Exception:
                    pass
                options = [DecisionOption.create("None", payload={"action": "skip"})]
                for cand in candidates:
                    options.append(
                        DecisionOption.create(
                            str(getattr(cand, "name", "Unit") or "Unit"),
                            payload={"target_unit_id": get_entity_id(cand)},
                        )
                    )
                if len(options) <= 1:
                    continue

                request = DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    "Inflamed Reprisal: select a friendly unit to shoot back after attacks resolve (or None).",
                    player_id=getattr(player, "id", None),
                    options=options,
                    context={
                        "ability": "inflamed_reprisal",
                        "ability_name": "Inflamed Reprisal",
                        "source_unit_id": source_id,
                        "attacker_unit_id": attacker_id,
                        "turn": int(turn or 0),
                        "optional": True,
                    },
                )
                self.request_decision(request)

    def _on_unit_shooting_resolved_inflamed_reprisal(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        pending = getattr(self, "_inflamed_reprisal_pending", None)
        if not isinstance(pending, list) or not pending:
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None:
            return
        attacker_id = str(get_entity_id(attacker_root) or "")
        if not attacker_id:
            return
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0

        queue = getattr(self, "decision_queue", None)
        pending_shot_units: set[str] = set()
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_DECLARE_SHOTS:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if not bool(ctx.get("inflamed_reprisal_flow", False)):
                    continue
                uid = str(ctx.get("unit_id", "") or "")
                if uid:
                    pending_shot_units.add(uid)

        remaining: list[dict] = []
        for entry in list(pending or []):
            if not isinstance(entry, dict):
                continue
            try:
                entry_turn = int(entry.get("turn", 0) or 0)
            except Exception:
                entry_turn = 0
            if entry_turn != int(turn or 0):
                continue
            if str(entry.get("attacker_unit_id", "") or "") != attacker_id:
                remaining.append(entry)
                continue

            selected = self._resolve_unit_by_id(entry.get("selected_unit_id"))
            if selected is None:
                continue
            try:
                selected_root = selected.get_attached_unit_root()
            except Exception:
                selected_root = selected
            if selected_root is None or not self._unit_is_active_for_reactive_trigger(selected_root):
                continue
            selected_id = str(get_entity_id(selected_root) or "")
            if not selected_id:
                continue
            if selected_id in pending_shot_units:
                continue
            if bool(getattr(selected_root, "is_battle_shocked", lambda: False)()):
                continue
            if not self._setup_reactive_can_shoot_target(selected_root, attacker_root):
                continue

            player = getattr(selected_root.get_parent_army(), "player", None)
            if player is None:
                continue
            ability_name = str(entry.get("ability_name", "") or "Inflamed Reprisal").strip() or "Inflamed Reprisal"
            request = self._queue_setup_reactive_shooting_decision(
                player=player,
                unit=selected_root,
                target_unit=attacker_root,
                source=ability_name,
            )
            if request is None:
                continue
            request.context["inflamed_reprisal_flow"] = True
            request.context["inflamed_reprisal_source"] = ability_name
            request.context["inflamed_reprisal_enemy_unit_id"] = attacker_id
            request.context["inflamed_reprisal_unit_id"] = selected_id
            pending_shot_units.add(selected_id)
        self._inflamed_reprisal_pending = remaining

    def _on_unit_move_ended_diseased_influence(self, unit=None, action: str | None = None, **_kwargs) -> None:
        if unit is None:
            return
        if str(action or "").strip().lower() not in ("move", "advance", "fall_back"):
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return

        try:
            moving_root = unit.get_attached_unit_root()
        except Exception:
            moving_root = unit
        if moving_root is None or not self._unit_is_active_for_reactive_trigger(moving_root):
            return
        moving_army = moving_root.get_parent_army()
        moving_player = getattr(moving_army, "player", None) if moving_army is not None else None

        try:
            from ...utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return

        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0

        queue = getattr(self, "decision_queue", None)

        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            if moving_player is not None and player is moving_player:
                continue
            army = self._get_player_army(player)
            if army is None:
                continue
            army_roots = list(self._iter_unique_army_roots(army) or [])
            if not army_roots:
                continue
            for source_root in list(army_roots):
                if source_root is None:
                    continue
                if not self._unit_is_active_for_reactive_trigger(source_root):
                    continue
                if not bool(getattr(source_root, "has_diseased_influence", lambda: False)()):
                    continue
                if not bool(getattr(source_root, "can_use_lord_of_death_guard", lambda **_k: False)(game=self)):
                    continue
                source_id = str(get_entity_id(source_root) or "")
                moving_id = str(get_entity_id(moving_root) or "")
                if not source_id or not moving_id:
                    continue
                already_pending = False
                if queue is not None and hasattr(queue, "list"):
                    for req in list(queue.list() or []):
                        if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                            continue
                        ctx = dict(getattr(req, "context", {}) or {})
                        if str(ctx.get("ability", "") or "") != "diseased_influence":
                            continue
                        if str(ctx.get("source_unit_id", "") or "") != source_id:
                            continue
                        if str(ctx.get("moving_unit_id", "") or "") != moving_id:
                            continue
                        if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                            continue
                        already_pending = True
                        break
                if already_pending:
                    continue

                candidates: list[Any] = []
                for cand in list(army_roots):
                    if cand is None:
                        continue
                    if cand.get_parent_army() is not army:
                        continue
                    if not self._unit_is_active_for_reactive_trigger(cand):
                        continue
                    if not self._unit_is_death_guard(cand):
                        continue
                    if self._unit_is_engaged_with_enemy(cand):
                        continue
                    try:
                        in_trigger = unit_within_range_of_unit(moving_root, cand, 9.0, use_attached_aggregate=True)
                        in_source = unit_within_range_of_unit(source_root, cand, 6.0, use_attached_aggregate=True)
                    except Exception:
                        continue
                    if in_trigger and in_source:
                        candidates.append(cand)
                if not candidates:
                    continue
                try:
                    candidates.sort(key=lambda u: str(get_entity_id(u) or ""))
                except Exception:
                    pass
                options = [DecisionOption.create("None", payload={"action": "skip"})]
                for cand in candidates:
                    options.append(
                        DecisionOption.create(
                            str(getattr(cand, "name", "Unit") or "Unit"),
                            payload={"target_unit_id": get_entity_id(cand)},
                        )
                    )
                if len(options) <= 1:
                    continue

                request = DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    "Diseased Influence: select a friendly unit to move up to 5\" (or None).",
                    player_id=getattr(player, "id", None),
                    options=options,
                    context={
                        "ability": "diseased_influence",
                        "ability_name": "Diseased Influence",
                        "source_unit_id": source_id,
                        "moving_unit_id": moving_id,
                        "turn": int(turn or 0),
                        "optional": True,
                    },
                )
                self.request_decision(request)

    @staticmethod
    def _normalize_parasitic_infection_token(value: object) -> str:
        text = str(value or "").replace("\u2019", "'").lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _weapon_profile_matches_parasitic_infection(
        self,
        weapon_profile: object,
        expected_weapon_name: str,
    ) -> bool:
        expected = self._normalize_parasitic_infection_token(expected_weapon_name)
        if not expected:
            return False
        candidates = [
            getattr(weapon_profile, "name", ""),
            getattr(getattr(weapon_profile, "parent_wargear", None), "name", ""),
        ]
        for raw_name in candidates:
            norm_name = self._normalize_parasitic_infection_token(raw_name)
            if not norm_name:
                continue
            if expected in norm_name or norm_name in expected:
                return True
        return False

    def _get_parasitic_infection_pending_triggers(self, unit) -> list[dict]:
        if unit is None:
            return []
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return []
        raw = sr.get("parasitic_infection_pending_triggers")
        if not isinstance(raw, list):
            return []
        triggers: list[dict] = []
        for entry in raw:
            if isinstance(entry, dict):
                triggers.append(dict(entry))
        return triggers

    def _set_parasitic_infection_pending_triggers(self, unit, triggers: list[dict]) -> None:
        if unit is None:
            return
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        normalized = [dict(entry) for entry in list(triggers or []) if isinstance(entry, dict)]
        if normalized:
            sr["parasitic_infection_pending_triggers"] = normalized
        else:
            sr.pop("parasitic_infection_pending_triggers", None)
        unit.special_rules = sr

    def _consume_parasitic_infection_trigger(self, unit, *, trigger_id: int) -> None:
        if unit is None:
            return
        pending = self._get_parasitic_infection_pending_triggers(unit)
        kept: list[dict] = []
        consumed = False
        for entry in pending:
            try:
                entry_trigger_id = int(entry.get("trigger_id", 0) or 0)
            except (TypeError, ValueError):
                entry_trigger_id = 0
            if not consumed and entry_trigger_id == int(trigger_id or 0):
                consumed = True
                continue
            kept.append(entry)
        if not consumed and pending:
            kept = list(pending[1:])
        self._set_parasitic_infection_pending_triggers(unit, kept)

    def _find_parasitic_infection_trigger(self, unit, *, trigger_id: int) -> dict | None:
        for entry in self._get_parasitic_infection_pending_triggers(unit):
            try:
                if int(entry.get("trigger_id", 0) or 0) == int(trigger_id or 0):
                    return dict(entry)
            except (TypeError, ValueError):
                continue
        return None

    def _parasitic_infection_pending_pick_point_request_exists(
        self,
        *,
        source_unit_id: str,
        trigger_id: int,
    ) -> bool:
        from ..decision_kinds import DECISION_PICK_POINT

        queue = getattr(self, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_PICK_POINT:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "parasitic_infection_spawn":
                continue
            if str(ctx.get("source_unit_id", "") or "") != str(source_unit_id or ""):
                continue
            try:
                req_trigger_id = int(ctx.get("trigger_id", 0) or 0)
            except (TypeError, ValueError):
                req_trigger_id = 0
            if req_trigger_id != int(trigger_id or 0):
                continue
            return True
        return False

    def _queue_next_parasitic_infection_spawn_decision(
        self,
        source_unit,
        *,
        phase_name: str = "Shooting phase",
    ) -> None:
        if source_unit is None:
            return
        try:
            root = source_unit.get_attached_unit_root()
        except Exception:
            root = source_unit
        if root is None:
            return
        pending = self._get_parasitic_infection_pending_triggers(root)
        if not pending:
            return
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if current_turn > 0:
            filtered = []
            for entry in pending:
                try:
                    entry_turn = int(entry.get("turn", 0) or 0)
                except (TypeError, ValueError):
                    entry_turn = 0
                if entry_turn and entry_turn != current_turn:
                    continue
                filtered.append(entry)
            if len(filtered) != len(pending):
                self._set_parasitic_infection_pending_triggers(root, filtered)
            pending = filtered
        if not pending:
            return

        first = dict(pending[0])
        source_unit_id = str(get_entity_id(root) or "")
        if not source_unit_id:
            return
        try:
            trigger_id = int(first.get("trigger_id", 0) or 0)
        except (TypeError, ValueError):
            trigger_id = 0
        if trigger_id <= 0:
            self._consume_parasitic_infection_trigger(root, trigger_id=0)
            self._queue_next_parasitic_infection_spawn_decision(root, phase_name=phase_name)
            return
        if self._parasitic_infection_pending_pick_point_request_exists(
            source_unit_id=source_unit_id,
            trigger_id=int(trigger_id),
        ):
            return

        spawn_roll = str(first.get("spawn_model_count_roll", "") or "D3").strip().upper() or "D3"
        try:
            spawn_count = int(first.get("spawn_model_count", 0) or 0)
        except (TypeError, ValueError):
            spawn_count = 0
        if spawn_count <= 0:
            try:
                spawn_count = int(get_roll(spawn_roll) or 0)
            except Exception:
                spawn_count = 0
            spawn_count = max(1, min(3, int(spawn_count or 0)))
            pending[0]["spawn_model_count"] = int(spawn_count)
            self._set_parasitic_infection_pending_triggers(root, pending)
            first = dict(pending[0])

        player = getattr(root.get_parent_army(), "player", None)
        if player is None:
            return
        source_model_name = str(first.get("source_model_name", "") or "model").strip() or "model"
        ability_name = str(first.get("ability_name", "") or "Parasitic Infection").strip() or "Parasitic Infection"
        spawn_unit_name = str(first.get("spawn_unit_name", "") or "Ripper Swarms").strip() or "Ripper Swarms"
        try:
            setup_range = int(first.get("setup_range", 3) or 3)
        except (TypeError, ValueError):
            setup_range = 3

        from ..decision_kinds import DECISION_PICK_POINT

        request = DecisionRequest.create(
            DECISION_PICK_POINT,
            f"{ability_name}: place {spawn_unit_name} ({int(spawn_count)} models) within {int(setup_range)}\" of {source_model_name} (or Skip).",
            player_id=getattr(player, "id", None),
            options=[
                DecisionOption.create("Confirm", payload={"action": "confirm"}),
                DecisionOption.create("Skip", payload={"action": "skip"}),
            ],
            context={
                "ability": "parasitic_infection_spawn",
                "ability_name": ability_name,
                "phase": str(phase_name or "Shooting phase"),
                "unit_id": source_unit_id,
                "source_unit_id": source_unit_id,
                "source_model_id": str(first.get("source_model_id", "") or ""),
                "source_model_name": source_model_name,
                "target_unit_id": str(first.get("target_unit_id", "") or ""),
                "target_unit_name": str(first.get("target_unit_name", "") or ""),
                "spawn_unit_name": spawn_unit_name,
                "spawn_model_count_roll": spawn_roll,
                "spawn_model_count": int(spawn_count),
                "setup_range": int(setup_range),
                "allow_target_engagement": bool(first.get("allow_target_engagement", True)),
                "disallow_other_enemy_engagement": bool(first.get("disallow_other_enemy_engagement", True)),
                "trigger_id": int(trigger_id),
                "optional": True,
                "instruction": (
                    f"Select a setup point for {spawn_unit_name} within {int(setup_range)}\" of {source_model_name}, or Skip."
                ),
            },
        )
        self.request_decision(request)

    def _parasitic_infection_datasheet_cache_key(self, *, faction_id: str, unit_name: str) -> tuple[str, str]:
        return (str(faction_id or "").strip().upper(), self._normalize_parasitic_infection_token(unit_name))

    def _get_parasitic_infection_spawn_datasheet(self, source_unit, *, spawn_unit_name: str):
        if source_unit is None:
            return None
        try:
            root = source_unit.get_attached_unit_root()
        except Exception:
            root = source_unit
        if root is None:
            return None
        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        cache = getattr(self, "_parasitic_infection_datasheet_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._parasitic_infection_datasheet_cache = cache
        cache_key = self._parasitic_infection_datasheet_cache_key(
            faction_id=faction_id,
            unit_name=spawn_unit_name,
        )
        if cache_key in cache:
            return cache.get(cache_key)

        target_name_norm = self._normalize_parasitic_infection_token(spawn_unit_name)
        datasheet = None
        if army is not None:
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                if self._normalize_parasitic_infection_token(getattr(unit, "name", "")) != target_name_norm:
                    continue
                datasheet = getattr(unit, "_datasheet", None)
                if datasheet is not None:
                    break
        if datasheet is None:
            from ...waha_helper.waha_helper import WahaHelper

            helper = WahaHelper()
            candidate = helper.get_full_datasheet_info_by_name(
                spawn_unit_name,
                faction_id=faction_id or None,
            )
            if candidate is None and faction_id:
                candidate = helper.get_full_datasheet_info_by_name(spawn_unit_name)
            datasheet = candidate
        cache[cache_key] = datasheet
        self._parasitic_infection_datasheet_cache = cache
        return datasheet

    def _collect_parasitic_infection_disallowed_enemy_models(
        self,
        *,
        source_unit,
        allowed_engagement_unit_id: str,
    ) -> list:
        game_map = getattr(self, "map", None)
        if game_map is None or source_unit is None:
            return []
        try:
            enemy_units = list(game_map.get_enemy_units(source_unit) or [])
        except Exception:
            enemy_units = []
        disallowed: list[Any] = []
        allowed_id = str(allowed_engagement_unit_id or "")
        for enemy in enemy_units:
            if enemy is None:
                continue
            try:
                enemy_root = enemy.get_attached_unit_root()
            except Exception:
                enemy_root = enemy
            if enemy_root is None:
                continue
            if str(get_entity_id(enemy_root) or "") == allowed_id:
                continue
            get_models = getattr(enemy_root, "get_models_for_collision", None)
            models = list(get_models() or []) if callable(get_models) else list(getattr(enemy_root, "models", []) or [])
            for model in models:
                if bool(getattr(model, "is_alive", False)):
                    disallowed.append(model)
        return disallowed

    def _parasitic_infection_candidate_in_disallowed_engagement(self, candidate_base, disallowed_enemy_models: list) -> bool:
        if candidate_base is None:
            return True
        if not disallowed_enemy_models:
            return False
        from ...utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases

        for enemy_model in list(disallowed_enemy_models or []):
            enemy_base = getattr(enemy_model, "model_base", None)
            if enemy_base is None:
                continue
            try:
                horizontal = float(horizontal_distance_between_bases_2d(candidate_base, enemy_base))
                vertical = float(vertical_distance_between_bases(candidate_base, enemy_base))
            except Exception:
                continue
            if horizontal <= float(ENGAGEMENT_RANGE_HORIZONTAL) + 1e-6 and vertical <= float(ENGAGEMENT_RANGE_VERTICAL) + 1e-6:
                return True
        return False

    def _parasitic_infection_candidate_violates_enemy_exclusion_range(
        self,
        candidate_base,
        enemy_models: list,
        *,
        exclusion_range_horizontal: float,
    ) -> bool:
        if candidate_base is None:
            return True
        try:
            threshold = float(exclusion_range_horizontal)
        except (TypeError, ValueError):
            threshold = 0.0
        if threshold <= 0:
            return False
        if not enemy_models:
            return False

        from ...utility.aura_utils import horizontal_distance_between_bases_2d

        for enemy_model in list(enemy_models or []):
            enemy_base = getattr(enemy_model, "model_base", None)
            if enemy_base is None:
                continue
            try:
                horizontal = float(horizontal_distance_between_bases_2d(candidate_base, enemy_base))
            except Exception:
                continue
            if horizontal <= float(threshold) + 1e-6:
                return True
        return False

    def _parasitic_infection_candidate_valid(
        self,
        *,
        spawn_unit,
        model,
        x: float,
        y: float,
        z: float,
        facing: float,
        placed: list[tuple[float, float, float, float]],
        source_model,
        setup_range: float,
        disallowed_enemy_models: list,
        disallow_other_enemy_engagement: bool,
        enemy_exclusion_range_horizontal: float,
        game_map,
    ) -> bool:
        if spawn_unit is None or model is None or source_model is None or game_map is None:
            return False
        candidate_base = spawn_unit._create_potential_base(x, y, z, facing, model=model)
        from ...utility.aura_utils import distance_between_bases_3d

        try:
            source_base = getattr(source_model, "model_base", None)
            if source_base is None:
                return False
            if float(distance_between_bases_3d(candidate_base, source_base)) > float(setup_range) + 1e-6:
                return False
        except Exception:
            return False

        if not bool(game_map.is_within_boundary(model, destination=(x, y))):
            return False
        if bool(spawn_unit._check_collision_with_obstacles_or_terrain(game_map, model, (x, y))):
            return False
        if bool(game_map.check_collision_with_other_friendly_units(model, destination=(x, y))):
            return False
        if bool(game_map.check_collision_with_other_enemy_units(model, destination=(x, y))):
            return False
        if bool(spawn_unit._collides_with_unit_models(x, y, z, facing, placed, model=model)):
            return False
        if not bool(spawn_unit._is_coherent_within_unit(x, y, z, facing, placed, model=model)):
            return False
        if disallow_other_enemy_engagement and self._parasitic_infection_candidate_in_disallowed_engagement(
            candidate_base,
            disallowed_enemy_models,
        ):
            return False
        if self._parasitic_infection_candidate_violates_enemy_exclusion_range(
            candidate_base,
            disallowed_enemy_models,
            exclusion_range_horizontal=float(enemy_exclusion_range_horizontal or 0.0),
        ):
            return False
        return True

    def _find_parasitic_infection_spawn_placements(
        self,
        *,
        source_unit,
        source_model,
        trigger: dict,
        point: Sequence[float],
    ) -> tuple[bool, str, list[tuple[float, float, float, float]]]:
        if source_unit is None or source_model is None:
            return (False, "Parasitic Infection requires a valid source model.", [])
        game_map = getattr(self, "map", None)
        if game_map is None:
            return (False, "Parasitic Infection requires an active battlefield map.", [])

        spawn_unit_name = str(trigger.get("spawn_unit_name", "") or "Ripper Swarms").strip() or "Ripper Swarms"
        datasheet = self._get_parasitic_infection_spawn_datasheet(
            source_unit,
            spawn_unit_name=spawn_unit_name,
        )
        if datasheet is None:
            return (False, f"Parasitic Infection could not find datasheet '{spawn_unit_name}'.", [])

        try:
            spawn_count = int(trigger.get("spawn_model_count", 0) or 0)
        except (TypeError, ValueError):
            spawn_count = 0
        if spawn_count <= 0:
            return (False, "Parasitic Infection spawn count is unavailable.", [])

        from ...units.unit import Unit as UnitClass

        try:
            spawn_unit = UnitClass(datasheet, quantity=int(spawn_count))
        except TypeError:
            spawn_unit = UnitClass(datasheet)
        spawn_unit.spawned_in_battle = True
        source_army = source_unit.get_parent_army() if hasattr(source_unit, "get_parent_army") else None
        set_parent = getattr(spawn_unit, "set_parent_army", None)
        if callable(set_parent):
            set_parent(source_army)
        else:
            spawn_unit.parent_army = source_army

        models = [m for m in list(getattr(spawn_unit, "models", []) or []) if bool(getattr(m, "is_alive", False))]
        if len(models) < int(spawn_count):
            return (False, f"Parasitic Infection could not create {int(spawn_count)} {spawn_unit_name} models.", [])
        models = list(models[: int(spawn_count)])

        try:
            setup_range = float(trigger.get("setup_range", 3) or 3)
        except (TypeError, ValueError):
            setup_range = 3.0
        if setup_range <= 0:
            setup_range = 3.0

        allow_target_engagement = bool(trigger.get("allow_target_engagement", True))
        disallow_other = bool(trigger.get("disallow_other_enemy_engagement", True))
        try:
            enemy_exclusion_range_horizontal = float(trigger.get("enemy_exclusion_range_horizontal", 0.0) or 0.0)
        except (TypeError, ValueError):
            enemy_exclusion_range_horizontal = 0.0
        allowed_target_unit_id = str(trigger.get("target_unit_id", "") or "") if allow_target_engagement else ""
        disallowed_enemy_models = self._collect_parasitic_infection_disallowed_enemy_models(
            source_unit=source_unit,
            allowed_engagement_unit_id=allowed_target_unit_id,
        )

        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return (False, "Parasitic Infection setup requires point coordinates.", [])
        try:
            anchor_x = float(point[0])
            anchor_y = float(point[1])
        except (TypeError, ValueError):
            return (False, "Parasitic Infection setup point must be numeric.", [])
        if len(point) > 2:
            try:
                anchor_z = float(point[2])
            except (TypeError, ValueError):
                anchor_z = float(getattr(source_model.model_base, "z", 0.0))
        else:
            try:
                anchor_z = float(game_map.get_height_at_point(anchor_x, anchor_y))
            except Exception:
                anchor_z = float(getattr(source_model.model_base, "z", 0.0))

        placed: list[tuple[float, float, float, float]] = []
        first_model = models[0]
        first_facing = 0.0
        if not self._parasitic_infection_candidate_valid(
            spawn_unit=spawn_unit,
            model=first_model,
            x=float(anchor_x),
            y=float(anchor_y),
            z=float(anchor_z),
            facing=float(first_facing),
            placed=placed,
            source_model=source_model,
            setup_range=float(setup_range),
            disallowed_enemy_models=list(disallowed_enemy_models),
            disallow_other_enemy_engagement=bool(disallow_other),
            enemy_exclusion_range_horizontal=float(enemy_exclusion_range_horizontal),
            game_map=game_map,
        ):
            return (
                False,
                f"Parasitic Infection: selected point cannot place {spawn_unit_name} while respecting setup and engagement restrictions.",
                [],
            )
        placed.append((float(anchor_x), float(anchor_y), float(anchor_z), float(first_facing)))

        try:
            sx = float(getattr(source_model.model_base, "x", 0.0))
            sy = float(getattr(source_model.model_base, "y", 0.0))
            sz = float(getattr(source_model.model_base, "z", 0.0))
            source_radius = float(source_model.model_base.get_longest_radius())
        except Exception:
            return (False, "Parasitic Infection source model geometry is unavailable.", [])

        for model in models[1:]:
            try:
                model_radius = float(model.model_base.get_longest_radius())
            except Exception:
                try:
                    model_radius = float(model.model_base.get_radius())
                except Exception:
                    model_radius = 1.0
            min_center = float(source_radius + model_radius + 0.05)
            max_center = float(source_radius + model_radius + setup_range + 1e-6)
            if max_center < min_center:
                return (False, "Parasitic Infection cannot place all spawned models in range.", [])

            found_position = None
            ring = 0.0
            while ring <= (max_center - min_center) + 1e-6:
                radius = float(min_center + ring)
                for degrees in range(0, 360, 15):
                    radians = math.radians(float(degrees))
                    x = float(sx + math.cos(radians) * radius)
                    y = float(sy + math.sin(radians) * radius)
                    try:
                        z = float(game_map.get_height_at_point(x, y))
                    except Exception:
                        z = float(sz)
                    if self._parasitic_infection_candidate_valid(
                        spawn_unit=spawn_unit,
                        model=model,
                        x=x,
                        y=y,
                        z=float(z),
                        facing=0.0,
                        placed=placed,
                        source_model=source_model,
                        setup_range=float(setup_range),
                        disallowed_enemy_models=list(disallowed_enemy_models),
                        disallow_other_enemy_engagement=bool(disallow_other),
                        enemy_exclusion_range_horizontal=float(enemy_exclusion_range_horizontal),
                        game_map=game_map,
                    ):
                        found_position = (x, y, float(z), 0.0)
                        break
                if found_position is not None:
                    break
                ring += 0.5
            if found_position is None:
                return (
                    False,
                    f"Parasitic Infection cannot place all {spawn_unit_name} models at that point.",
                    [],
                )
            placed.append(found_position)

        return (True, "", placed)

    def _spawn_parasitic_infection_unit_from_placements(
        self,
        *,
        source_unit,
        trigger: dict,
        placements: list[tuple[float, float, float, float]],
    ):
        if source_unit is None:
            return None
        if not placements:
            return None
        game_map = getattr(self, "map", None)
        if game_map is None:
            return None

        spawn_unit_name = str(trigger.get("spawn_unit_name", "") or "Ripper Swarms").strip() or "Ripper Swarms"
        datasheet = self._get_parasitic_infection_spawn_datasheet(
            source_unit,
            spawn_unit_name=spawn_unit_name,
        )
        if datasheet is None:
            return None
        try:
            spawn_count = int(trigger.get("spawn_model_count", 0) or 0)
        except (TypeError, ValueError):
            spawn_count = 0
        if spawn_count <= 0:
            return None

        from ...units.unit import Unit as UnitClass

        try:
            spawned = UnitClass(datasheet, quantity=int(spawn_count))
        except TypeError:
            spawned = UnitClass(datasheet)
        spawned.spawned_in_battle = True
        source_army = source_unit.get_parent_army() if hasattr(source_unit, "get_parent_army") else None
        if source_army is None:
            return None
        set_parent = getattr(spawned, "set_parent_army", None)
        if callable(set_parent):
            set_parent(source_army)
        else:
            spawned.parent_army = source_army

        models = list(getattr(spawned, "models", []) or [])
        if len(models) < len(placements):
            return None
        models = list(models[: len(placements)])
        spawned.models = list(models)
        try:
            spawned.starting_model_count = int(len(models))
        except Exception:
            pass
        for model, position in zip(models, placements):
            model.set_location(
                float(position[0]),
                float(position[1]),
                float(position[2]),
                float(position[3]),
            )

        spawned.deployed = True
        reserve_fn = getattr(spawned, "set_reserve_status", None)
        if callable(reserve_fn):
            reserve_fn("deployed")
        else:
            spawned.reserve_status = "deployed"
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        spawned.reserve_turn_deployed = int(current_turn) if current_turn > 0 else None
        spawned.arrived_from_reserves_this_turn = True
        try:
            spawned.round_state.reinforced_this_round = True
            spawned.round_state.remained_stationary_this_round = False
        except Exception:
            pass

        if not bool(game_map.place_unit(spawned)):
            return None
        added = bool(source_army.add_unit(spawned))
        if not added:
            if spawned in list(getattr(game_map, "units", []) or []):
                game_map.units.remove(spawned)
            return None
        rebuild_registry = getattr(self, "rebuild_entity_registry", None)
        if callable(rebuild_registry):
            rebuild_registry()
        event_system = getattr(self, "event_system", None)
        if event_system is not None:
            event_system.publish(
                "unit_set_up",
                unit=spawned,
                set_up_as_reinforcements=False,
            )
        try:
            from ...utility.event_bus import append_action

            player = getattr(source_army, "player", None)
            if player is not None:
                append_action(
                    player,
                    f"Parasitic Infection: spawned {spawn_unit_name} ({len(placements)} model(s)).",
                )
        except Exception:
            pass
        return spawned

    def _validate_parasitic_infection_spawn_point(self, context: dict, point: Sequence[float]) -> tuple[bool, str]:
        ctx = dict(context or {})
        source_unit_id = str(ctx.get("source_unit_id", "") or ctx.get("unit_id", "") or "")
        if not source_unit_id:
            return (False, "Parasitic Infection spawn requires a source unit.")
        source_unit = self._resolve_unit_by_id(source_unit_id)
        if source_unit is None:
            return (False, "Parasitic Infection source unit could not be resolved.")
        try:
            source_root = source_unit.get_attached_unit_root()
        except Exception:
            source_root = source_unit
        if source_root is None:
            return (False, "Parasitic Infection source unit is unavailable.")

        try:
            trigger_id = int(ctx.get("trigger_id", 0) or 0)
        except (TypeError, ValueError):
            trigger_id = 0
        if trigger_id <= 0:
            return (False, "Parasitic Infection trigger id is invalid.")
        trigger = self._find_parasitic_infection_trigger(source_root, trigger_id=int(trigger_id))
        if not isinstance(trigger, dict):
            return (False, "Parasitic Infection trigger is no longer pending.")

        source_model_id = str(trigger.get("source_model_id", "") or ctx.get("source_model_id", "") or "")
        source_model = self._resolve_model_by_id(source_model_id) if source_model_id else None
        if source_model is None:
            source_model = next(
                (
                    model
                    for model in list(getattr(source_root, "models", []) or [])
                    if str(get_entity_id(model) or "") == source_model_id
                ),
                None,
            )
        if source_model is None:
            return (False, "Parasitic Infection source model could not be resolved.")

        valid, reason, _placements = self._find_parasitic_infection_spawn_placements(
            source_unit=source_root,
            source_model=source_model,
            trigger=trigger,
            point=point,
        )
        if not valid:
            return (False, str(reason or "Parasitic Infection spawn point is invalid."))
        return (True, "")

    def _apply_parasitic_infection_spawn_point(self, context: dict, point: Sequence[float]) -> bool:
        ctx = dict(context or {})
        source_unit_id = str(ctx.get("source_unit_id", "") or ctx.get("unit_id", "") or "")
        source_unit = self._resolve_unit_by_id(source_unit_id) if source_unit_id else None
        if source_unit is None:
            return False
        try:
            source_root = source_unit.get_attached_unit_root()
        except Exception:
            source_root = source_unit
        if source_root is None:
            return False
        try:
            trigger_id = int(ctx.get("trigger_id", 0) or 0)
        except (TypeError, ValueError):
            trigger_id = 0
        trigger = self._find_parasitic_infection_trigger(source_root, trigger_id=int(trigger_id))
        if not isinstance(trigger, dict):
            return False

        source_model_id = str(trigger.get("source_model_id", "") or ctx.get("source_model_id", "") or "")
        source_model = self._resolve_model_by_id(source_model_id) if source_model_id else None
        if source_model is None:
            source_model = next(
                (
                    model
                    for model in list(getattr(source_root, "models", []) or [])
                    if str(get_entity_id(model) or "") == source_model_id
                ),
                None,
            )
        if source_model is None:
            return False

        valid, _reason, placements = self._find_parasitic_infection_spawn_placements(
            source_unit=source_root,
            source_model=source_model,
            trigger=trigger,
            point=point,
        )
        if not valid:
            self._queue_next_parasitic_infection_spawn_decision(
                source_root,
                phase_name=str(ctx.get("phase", "") or "Shooting phase"),
            )
            return False

        spawned = self._spawn_parasitic_infection_unit_from_placements(
            source_unit=source_root,
            trigger=trigger,
            placements=placements,
        )
        if spawned is None:
            self._queue_next_parasitic_infection_spawn_decision(
                source_root,
                phase_name=str(ctx.get("phase", "") or "Shooting phase"),
            )
            return False

        self._consume_parasitic_infection_trigger(source_root, trigger_id=int(trigger_id))
        self._queue_next_parasitic_infection_spawn_decision(
            source_root,
            phase_name=str(ctx.get("phase", "") or "Shooting phase"),
        )
        return True

    def _skip_parasitic_infection_spawn(self, context: dict) -> None:
        ctx = dict(context or {})
        source_unit_id = str(ctx.get("source_unit_id", "") or ctx.get("unit_id", "") or "")
        source_unit = self._resolve_unit_by_id(source_unit_id) if source_unit_id else None
        if source_unit is None:
            return
        try:
            source_root = source_unit.get_attached_unit_root()
        except Exception:
            source_root = source_unit
        if source_root is None:
            return
        try:
            trigger_id = int(ctx.get("trigger_id", 0) or 0)
        except (TypeError, ValueError):
            trigger_id = 0
        self._consume_parasitic_infection_trigger(source_root, trigger_id=int(trigger_id))
        self._queue_next_parasitic_infection_spawn_decision(
            source_root,
            phase_name=str(ctx.get("phase", "") or "Shooting phase"),
        )

    def _seed_spore_mines_selection_request_exists(self, *, owner_id: str, turn: int) -> bool:
        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        queue = getattr(self, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "seed_spore_mines_select_source":
                continue
            if str(ctx.get("owner_id", "") or "") != str(owner_id or ""):
                continue
            try:
                req_turn = int(ctx.get("turn", 0) or 0)
            except (TypeError, ValueError):
                req_turn = 0
            if int(req_turn or 0) != int(turn or 0):
                continue
            return True
        return False

    def _seed_spore_mines_used_this_turn(self, *, army, owner_id: str, turn: int) -> bool:
        if army is None:
            return False
        for root in list(self._iter_unique_army_roots(army) or []):
            if root is None:
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("seed_spore_mines_used_this_turn")):
                continue
            if str(sr.get("seed_spore_mines_turn_owner", "") or "") != str(owner_id or ""):
                continue
            try:
                used_turn = int(sr.get("seed_spore_mines_turn", 0) or 0)
            except (TypeError, ValueError):
                used_turn = 0
            if int(used_turn or 0) == int(turn or 0):
                return True
        return False

    def _on_phase_start_seed_spore_mines(self, player=None, phase=None, **_kwargs) -> None:
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None:
            return
        current_player = self.get_current_player()
        if current_player is not player:
            return
        army = player.get_army()
        if army is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except (TypeError, ValueError):
            turn = 0
        if turn <= 0:
            return

        if self._seed_spore_mines_used_this_turn(army=army, owner_id=owner_id, turn=int(turn)):
            return
        if self._seed_spore_mines_selection_request_exists(owner_id=owner_id, turn=int(turn)):
            return

        candidates: list[tuple[Any, dict]] = []
        seen: set[str] = set()
        for root in list(self._iter_unique_army_roots(army) or []):
            if root is None:
                continue
            unit_id = str(get_entity_id(root) or "")
            if not unit_id or unit_id in seen:
                continue
            seen.add(unit_id)
            if not self._unit_is_active_for_reactive_trigger(root):
                continue
            try:
                if bool(getattr(root.round_state, "shot_this_round", False)):
                    continue
            except Exception:
                pass
            ineligible_fn = getattr(root, "is_shooting_phase_ineligible", None)
            if callable(ineligible_fn):
                try:
                    if bool(ineligible_fn(self)):
                        continue
                except Exception:
                    pass
            specs_fn = getattr(root, "unit_seed_spore_mines_specs", None)
            specs = list(specs_fn() or []) if callable(specs_fn) else []
            if not specs:
                continue
            spec = dict(specs[0])
            candidates.append((root, spec))

        if not candidates:
            return
        candidates = sorted(
            candidates,
            key=lambda item: str(get_entity_id(item[0]) or ""),
        )

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        options = [DecisionOption.create("None", payload={"action": "skip"})]
        spec_by_unit: dict[str, dict] = {}
        for root, spec in list(candidates):
            unit_id = str(get_entity_id(root) or "")
            if not unit_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(root, "name", "Unit") or "Unit"),
                    payload={"unit_id": unit_id},
                )
            )
            spec_by_unit[unit_id] = {
                "source": str(spec.get("source", "") or "Seed Spore Mines"),
                "spawn_unit_name": str(spec.get("spawn_unit_name", "") or "Spore Mines"),
                "setup_range": int(spec.get("setup_range", 48) or 48),
                "source_scope": str(spec.get("source_scope", "unit") or "unit").strip().lower() or "unit",
                "enemy_exclusion_range_horizontal": int(spec.get("enemy_exclusion_range_horizontal", 9) or 9),
                "count_mode": str(spec.get("count_mode", "fixed") or "fixed").strip().lower() or "fixed",
                "spawn_model_count": int(spec.get("spawn_model_count", 1) or 1),
                "spawn_model_count_roll": str(spec.get("spawn_model_count_roll", "") or "").strip().upper(),
                "count_per_source_model": int(spec.get("count_per_source_model", 1) or 1),
                "allow_target_engagement": bool(spec.get("allow_target_engagement", False)),
                "disallow_other_enemy_engagement": bool(spec.get("disallow_other_enemy_engagement", True)),
            }

        if len(options) <= 1:
            return

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Seed Spore Mines: select one unit with this ability to seed mines now (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "seed_spore_mines_select_source",
                "ability_name": "Seed Spore Mines",
                "phase": "Shooting phase",
                "owner_id": str(owner_id),
                "turn": int(turn),
                "spec_by_unit": dict(spec_by_unit),
            },
        )
        self.request_decision(request)

    def _on_model_destroyed_parasitic_infection(
        self,
        attacker_model=None,
        attacker_unit=None,
        target_model=None,
        target_unit=None,
        weapon_profile=None,
        **_kwargs,
    ) -> None:
        if attacker_model is None or target_model is None or target_unit is None:
            return
        if not self.is_shooting_phase():
            return
        if attacker_unit is None:
            attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None:
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        if attacker_root is None or target_root is None:
            return
        if attacker_root.get_parent_army() is target_root.get_parent_army():
            return

        get_specs = getattr(attacker_root, "model_parasitic_infection_specs", None)
        specs = list(get_specs(attacker_model) or []) if callable(get_specs) else []
        if not specs:
            return

        matched_spec = None
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            required_keyword = str(spec.get("required_target_keyword", "") or "INFANTRY").strip().upper() or "INFANTRY"
            model_has_keyword = bool(getattr(target_model, "has_any_keyword", lambda *_a, **_k: False)(required_keyword))
            unit_has_keyword = bool(getattr(target_root, "has_any_keyword", lambda *_a, **_k: False)(required_keyword))
            if not model_has_keyword and not unit_has_keyword:
                continue
            expected_weapon = str(spec.get("weapon_name", "") or "").strip()
            if not self._weapon_profile_matches_parasitic_infection(weapon_profile, expected_weapon):
                continue
            matched_spec = dict(spec)
            break
        if not isinstance(matched_spec, dict):
            return

        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        pending = self._get_parasitic_infection_pending_triggers(attacker_root)
        try:
            next_trigger_id = int(sr.get("parasitic_infection_next_trigger_id", 1) or 1)
        except (TypeError, ValueError):
            next_trigger_id = 1
        next_trigger_id = max(1, int(next_trigger_id))
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        current_player = getattr(self, "get_current_player", lambda: None)()
        trigger = {
            "trigger_id": int(next_trigger_id),
            "turn": int(current_turn),
            "turn_owner_id": str(getattr(current_player, "id", "") or ""),
            "source_model_id": str(get_entity_id(attacker_model) or ""),
            "source_model_name": str(getattr(attacker_model, "name", "") or "Model"),
            "target_unit_id": str(get_entity_id(target_root) or ""),
            "target_unit_name": str(getattr(target_root, "name", "") or "Enemy unit"),
            "ability_name": str(matched_spec.get("source", "") or "Parasitic Infection"),
            "spawn_unit_name": str(matched_spec.get("spawn_unit_name", "") or "Ripper Swarms"),
            "spawn_model_count_roll": str(matched_spec.get("spawn_model_count_roll", "") or "D3").strip().upper() or "D3",
            "setup_range": int(matched_spec.get("setup_range", 3) or 3),
            "allow_target_engagement": bool(matched_spec.get("allow_target_engagement", True)),
            "disallow_other_enemy_engagement": bool(matched_spec.get("disallow_other_enemy_engagement", True)),
        }
        pending.append(trigger)
        self._set_parasitic_infection_pending_triggers(attacker_root, pending)
        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["parasitic_infection_next_trigger_id"] = int(next_trigger_id + 1)
        attacker_root.special_rules = sr

    def _on_unit_shooting_resolved_parasitic_infection(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None:
            return
        pending = self._get_parasitic_infection_pending_triggers(attacker_root)
        if not pending:
            return
        self._queue_next_parasitic_infection_spawn_decision(attacker_root, phase_name="Shooting phase")

    def _queue_curse_of_walking_pox_decision(self, source_unit, *, phase_name: str, ability_name: str) -> None:
        if source_unit is None:
            return
        try:
            root = source_unit.get_attached_unit_root()
        except Exception:
            root = source_unit
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        try:
            pending = int(sr.get("curse_of_walking_pox_pending_kills", 0) or 0)
        except Exception:
            pending = 0
        if pending <= 0:
            return
        destroyed = list(getattr(root, "models_lost", []) or [])
        poxwalker_destroyed = []
        for model in destroyed:
            if model is None:
                continue
            has_any = getattr(model, "has_any_keyword", None)
            has_kw = getattr(model, "has_keyword", None)
            is_poxwalker = False
            if callable(has_any):
                try:
                    is_poxwalker = bool(has_any("POXWALKER"))
                except Exception:
                    is_poxwalker = False
            if not is_poxwalker and callable(has_kw):
                try:
                    is_poxwalker = bool(has_kw("POXWALKER"))
                except Exception:
                    is_poxwalker = False
            if is_poxwalker:
                poxwalker_destroyed.append(model)
        max_returns = min(int(pending), len(poxwalker_destroyed))
        if max_returns <= 0:
            sr["curse_of_walking_pox_pending_kills"] = 0
            root.special_rules = sr
            return
        player = getattr(root.get_parent_army(), "player", None)
        if player is None:
            return
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        source_id = str(get_entity_id(root) or "")
        if not source_id:
            return
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "curse_of_walking_pox":
                    continue
                if str(ctx.get("source_unit_id", "") or "") != source_id:
                    continue
                if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                    continue
                return

        options = [DecisionOption.create("None", payload={"action": "skip", "returns": 0})]
        for count in range(1, int(max_returns) + 1):
            label = f"Return {int(count)} model" + ("s" if int(count) != 1 else "")
            options.append(DecisionOption.create(label, payload={"returns": int(count)}))
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: return up to {int(max_returns)} destroyed Poxwalker model(s) (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "curse_of_walking_pox",
                "ability_name": ability_name,
                "source_unit_id": source_id,
                "unit_id": source_id,
                "max_returns": int(max_returns),
                "turn_owner": str(getattr(player, "id", "") or ""),
                "turn": int(turn or 0),
                "phase": str(phase_name or ""),
                "optional": True,
            },
        )
        self.request_decision(request)

    def _on_model_destroyed_curse_of_the_walking_pox(
        self,
        attacker_model=None,
        attacker_unit=None,
        target_model=None,
        target_unit=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None and attacker_model is not None:
            attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None or target_unit is None or target_model is None:
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        if attacker_root is None or target_root is None:
            return
        if attacker_root.get_parent_army() == target_root.get_parent_army():
            return
        if not bool(getattr(attacker_root, "has_curse_of_the_walking_pox", lambda: False)()):
            return

        try:
            if bool(getattr(target_model, "has_any_keyword", lambda *_a, **_k: False)("MONSTER")):
                return
            if bool(getattr(target_model, "has_any_keyword", lambda *_a, **_k: False)("VEHICLE")):
                return
        except Exception:
            pass
        try:
            if bool(getattr(target_root, "has_any_keyword", lambda *_a, **_k: False)("MONSTER")):
                return
            if bool(getattr(target_root, "has_any_keyword", lambda *_a, **_k: False)("VEHICLE")):
                return
        except Exception:
            pass

        is_poxwalker_attack = False
        if attacker_model is not None:
            has_any = getattr(attacker_model, "has_any_keyword", None)
            has_kw = getattr(attacker_model, "has_keyword", None)
            if callable(has_any):
                try:
                    is_poxwalker_attack = bool(has_any("POXWALKER"))
                except Exception:
                    is_poxwalker_attack = False
            if not is_poxwalker_attack and callable(has_kw):
                try:
                    is_poxwalker_attack = bool(has_kw("POXWALKER"))
                except Exception:
                    is_poxwalker_attack = False
        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        is_eater_plague = bool(sr.get("curse_of_walking_pox_count_eater_plague", False))
        if not is_poxwalker_attack and not is_eater_plague:
            return
        try:
            pending = int(sr.get("curse_of_walking_pox_pending_kills", 0) or 0)
        except Exception:
            pending = 0
        sr["curse_of_walking_pox_pending_kills"] = int(max(0, pending + 1))
        attacker_root.special_rules = sr

    def _on_unit_shooting_resolved_curse_of_the_walking_pox(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            root = attacker_unit.get_attached_unit_root()
        except Exception:
            root = attacker_unit
        if root is None:
            return
        if not bool(getattr(root, "has_curse_of_the_walking_pox", lambda: False)()):
            return
        self._queue_curse_of_walking_pox_decision(
            root,
            phase_name="SHOOTING_PHASE",
            ability_name="Curse of the Walking Pox",
        )

    def _on_fight_sequence_complete_curse_of_the_walking_pox(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        if not self.is_fight_phase():
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not bool(getattr(root, "has_curse_of_the_walking_pox", lambda: False)()):
            return
        self._queue_curse_of_walking_pox_decision(
            root,
            phase_name="FIGHT_PHASE",
            ability_name="Curse of the Walking Pox",
        )

    def _on_model_destroyed_death_guard_final_ingredient(
        self,
        attacker_unit=None,
        target_model=None,
        target_unit=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or target_model is None:
            return
        if not self.is_fight_phase():
            return
        attacker_army = attacker_unit.get_parent_army() if hasattr(attacker_unit, "get_parent_army") else None
        if attacker_army is None:
            return
        mgr = getattr(attacker_army, "death_guard_detachments", None)
        note_fn = getattr(mgr, "note_final_ingredient_character_model_destroyed", None) if mgr is not None else None
        if not callable(note_fn):
            return
        note_fn(
            attacker_unit=attacker_unit,
            target_model=target_model,
            target_unit=target_unit,
            game=self,
        )

    def _on_fight_sequence_complete_death_guard_final_ingredient(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        if not self.is_fight_phase():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
        if army is None:
            return
        mgr = getattr(army, "death_guard_detachments", None)
        queue_fn = getattr(mgr, "queue_final_ingredient_request_for_unit", None) if mgr is not None else None
        if not callable(queue_fn):
            return
        queue_fn(unit, game=self)

    def _on_fight_sequence_complete_lethal_ichor(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        if not self.is_fight_phase():
            return
        try:
            attacker_root = unit.get_attached_unit_root()
        except Exception:
            attacker_root = unit
        if attacker_root is None:
            return
        attacker_id = str(get_entity_id(attacker_root) or "")
        if not attacker_id:
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return
        try:
            from ...utility.event_bus import append_dice
        except Exception:
            append_dice = None

        for enemy in list(game_map.get_enemy_units(attacker_root) or []):
            if enemy is None:
                continue
            try:
                enemy_root = enemy.get_attached_unit_root()
            except Exception:
                enemy_root = enemy
            if enemy_root is None:
                continue
            if not bool(getattr(enemy_root, "has_lethal_ichor", lambda: False)()):
                continue
            sr = getattr(enemy_root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            allocations = sr.get("lethal_ichor_allocations")
            if not isinstance(allocations, dict):
                continue
            try:
                num_allocations = int(allocations.get(attacker_id, 0) or 0)
            except Exception:
                num_allocations = 0
            if num_allocations <= 0:
                continue
            num_allocations = max(0, min(6, int(num_allocations)))
            successes = 0
            rolls: list[int] = []
            for _ in range(int(num_allocations)):
                try:
                    roll = int(get_roll("D6") or 0)
                except Exception:
                    roll = 0
                rolls.append(int(roll))
                if int(roll) >= 4:
                    successes += 1
            player = getattr(enemy_root.get_parent_army(), "player", None)
            source_name = str(sr.get("lethal_ichor_source", "") or "Lethal Ichor").strip() or "Lethal Ichor"
            if callable(append_dice) and player is not None:
                append_dice(
                    player,
                    f"{source_name}: {int(num_allocations)} roll(s) vs {getattr(attacker_root, 'name', 'Unit')} -> {', '.join(str(r) for r in rolls)}",
                )
            if int(successes) > 0:
                try:
                    enemy_root._apply_mortal_wounds_to_unit(
                        attacker_root,
                        int(successes),
                        game_map=game_map,
                        attacker_unit=enemy_root,
                    )
                except Exception:
                    pass
            allocations.pop(attacker_id, None)
            if allocations:
                sr["lethal_ichor_allocations"] = allocations
            else:
                sr.pop("lethal_ichor_allocations", None)
                sr.pop("lethal_ichor_source", None)
            enemy_root.special_rules = sr

    def _on_fight_sequence_complete_allocated_melee_mortal_retaliation(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        if not self.is_fight_phase():
            return
        try:
            attacker_root = unit.get_attached_unit_root()
        except Exception:
            attacker_root = unit
        if attacker_root is None:
            return
        attacker_id = str(get_entity_id(attacker_root) or "")
        if not attacker_id:
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return
        try:
            from ...utility.event_bus import append_dice
        except Exception:
            append_dice = None

        for enemy in list(game_map.get_enemy_units(attacker_root) or []):
            if enemy is None:
                continue
            try:
                enemy_root = enemy.get_attached_unit_root()
            except Exception:
                enemy_root = enemy
            if enemy_root is None:
                continue
            sr = getattr(enemy_root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            allocations_by_key = sr.get("allocated_melee_retaliation_allocations")
            specs_by_key = sr.get("allocated_melee_retaliation_specs")
            if not isinstance(allocations_by_key, dict) or not isinstance(specs_by_key, dict):
                continue

            changed = False
            for ability_key, spec in list(specs_by_key.items()):
                if not isinstance(spec, dict):
                    continue
                allocations = allocations_by_key.get(ability_key)
                if not isinstance(allocations, dict):
                    continue
                try:
                    num_allocations = int(allocations.get(attacker_id, 0) or 0)
                except (TypeError, ValueError):
                    num_allocations = 0
                if num_allocations <= 0:
                    continue
                try:
                    threshold = int(spec.get("threshold", 4) or 4)
                except (TypeError, ValueError):
                    threshold = 4
                try:
                    mortal_wounds = int(spec.get("mortal_wounds", 1) or 1)
                except (TypeError, ValueError):
                    mortal_wounds = 1
                rolls: list[int] = []
                total_mortal_wounds = 0
                for _ in range(int(num_allocations)):
                    try:
                        roll = int(get_roll("D6") or 0)
                    except Exception:
                        roll = 0
                    rolls.append(int(roll))
                    if int(roll) >= int(threshold):
                        total_mortal_wounds += int(mortal_wounds)
                source_name = str(spec.get("source", "") or "Allocated melee retaliation").strip() or "Allocated melee retaliation"
                player = getattr(enemy_root.get_parent_army(), "player", None)
                if callable(append_dice) and player is not None:
                    append_dice(
                        player,
                        f"{source_name}: {int(num_allocations)} roll(s) vs {getattr(attacker_root, 'name', 'Unit')} -> {', '.join(str(r) for r in rolls)}",
                    )
                if total_mortal_wounds > 0:
                    enemy_root._apply_mortal_wounds_to_unit(
                        attacker_root,
                        int(total_mortal_wounds),
                        game_map=game_map,
                        attacker_unit=enemy_root,
                    )
                allocations.pop(attacker_id, None)
                changed = True
                if allocations:
                    allocations_by_key[ability_key] = allocations
                else:
                    allocations_by_key.pop(ability_key, None)
                    specs_by_key.pop(ability_key, None)

            if changed:
                if allocations_by_key:
                    sr["allocated_melee_retaliation_allocations"] = allocations_by_key
                else:
                    sr.pop("allocated_melee_retaliation_allocations", None)
                if specs_by_key:
                    sr["allocated_melee_retaliation_specs"] = specs_by_key
                else:
                    sr.pop("allocated_melee_retaliation_specs", None)
                enemy_root.special_rules = sr

    def _on_unit_shooting_resolved_repulsor_grid(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None:
            return
        attacker_id = str(get_entity_id(attacker_root) or "")
        if not attacker_id:
            return

        game_map = getattr(self, "map", None)
        if game_map is None:
            return
        enemy_roots: list[Any] = []
        seen_enemy_ids: set[str] = set()
        try:
            attacker_army = attacker_root.get_parent_army()
        except Exception:
            attacker_army = None
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None or army is attacker_army:
                continue
            for root in list(self._iter_unique_army_roots(army) or []):
                if root is None:
                    continue
                rid = str(get_entity_id(root) or "")
                if rid and rid in seen_enemy_ids:
                    continue
                if rid:
                    seen_enemy_ids.add(rid)
                enemy_roots.append(root)

        for enemy_root in enemy_roots:
            if enemy_root is None:
                continue
            get_rule = getattr(enemy_root, "get_repulsor_grid_rule", None)
            if not callable(get_rule):
                continue
            rule = get_rule()
            if not isinstance(rule, dict):
                continue
            sr = getattr(enemy_root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            pending = sr.get("repulsor_grid_pending_by_attacker")
            if not isinstance(pending, dict):
                continue
            try:
                pending_mw = int(pending.get(attacker_id, 0) or 0)
            except Exception:
                pending_mw = 0
            if pending_mw <= 0:
                continue
            if game_map is not None and bool(getattr(attacker_root, "is_alive", lambda: False)()):
                try:
                    enemy_root._apply_mortal_wounds_to_unit(
                        attacker_root,
                        int(pending_mw),
                        game_map=game_map,
                        attacker_unit=enemy_root,
                    )
                except Exception:
                    pass
            pending.pop(attacker_id, None)
            if pending:
                sr["repulsor_grid_pending_by_attacker"] = pending
            else:
                sr.pop("repulsor_grid_pending_by_attacker", None)
                sr.pop("repulsor_grid_source", None)
            enemy_root.special_rules = sr

    def _on_unit_destroyed_explosive_blight(
        self,
        unit=None,
        destroyed_by_unit=None,
        destroyed_by_model=None,
        last_model=None,
        **_kwargs,
    ) -> None:
        if unit is None or destroyed_by_unit is None:
            return
        if not self.is_shooting_phase():
            return
        try:
            attacker_root = destroyed_by_unit.get_attached_unit_root()
        except Exception:
            attacker_root = destroyed_by_unit
        try:
            target_root = unit.get_attached_unit_root()
        except Exception:
            target_root = unit
        if attacker_root is None or target_root is None:
            return
        if attacker_root.get_parent_army() == target_root.get_parent_army():
            return
        if not bool(getattr(attacker_root, "has_explosive_blight", lambda: False)()):
            return
        if destroyed_by_model is None:
            return
        center_model = last_model if last_model is not None else destroyed_by_model
        if center_model is None:
            return
        try:
            from ...rules.nurgles_gift import NurglesGiftManager
        except Exception:
            NurglesGiftManager = None
        afflicted_bonus = 0
        if NurglesGiftManager is not None:
            try:
                afflicted_bonus = 1 if NurglesGiftManager.get_afflicted_plague_for_unit(target_root, game=self, game_map=self.map) is not None else 0
            except Exception:
                afflicted_bonus = 0
        try:
            roll = int(get_roll("D6") or 0)
        except Exception:
            roll = 0
        total = int(roll) + int(afflicted_bonus)
        if int(total) < 5:
            return
        attacker_player = getattr(attacker_root.get_parent_army(), "player", None)
        owner_id = str(getattr(attacker_player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        try:
            from ...utility.aura_utils import distance_between_models_bases_3d
        except Exception:
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for enemy in list(getattr(self.map, "units", []) or []):
            if enemy is None:
                continue
            try:
                enemy_root = enemy.get_attached_unit_root()
            except Exception:
                enemy_root = enemy
            if enemy_root is None:
                continue
            eid = str(get_entity_id(enemy_root) or "")
            if not eid or eid in seen:
                continue
            seen.add(eid)
            if enemy_root.get_parent_army() is attacker_root.get_parent_army():
                continue
            if not self._unit_is_active_for_reactive_trigger(enemy_root):
                continue
            if enemy_root is target_root:
                continue
            in_range = False
            target_models = list(getattr(enemy_root, "get_attached_unit_models", lambda: [])() or [])
            for em in list(target_models):
                if em is None or not getattr(em, "is_alive", True):
                    continue
                try:
                    if float(distance_between_models_bases_3d(center_model, em)) <= 6.0 + 1e-6:
                        in_range = True
                        break
                except Exception:
                    continue
            if in_range:
                candidates.append(enemy_root)
        if not candidates:
            return
        for cand in list(candidates):
            sr = getattr(cand, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_afflicted_active"] = True
            sr["post_shoot_afflicted_owner"] = owner_id
            sr["post_shoot_afflicted_turn"] = int(turn or 0)
            sr["post_shoot_afflicted_source"] = "Explosive Blight"
            cand.special_rules = sr

    def _on_unit_destroyed_extraction_of_fresh_disease(
        self,
        unit=None,
        destroyed_by_unit=None,
        destroyed_by_weapon_profile=None,
        **_kwargs,
    ) -> None:
        if unit is None or destroyed_by_unit is None:
            return
        try:
            attacker_root = destroyed_by_unit.get_attached_unit_root()
        except Exception:
            attacker_root = destroyed_by_unit
        try:
            target_root = unit.get_attached_unit_root()
        except Exception:
            target_root = unit
        if attacker_root is None or target_root is None:
            return
        if attacker_root.get_parent_army() == target_root.get_parent_army():
            return
        wp = destroyed_by_weapon_profile
        pw = getattr(wp, "parent_wargear", None)
        if wp is None or pw is None or not bool(getattr(pw, "is_melee", lambda: False)()):
            return

        try:
            members = list(attacker_root.get_attached_unit_members() or [])
        except Exception:
            members = [attacker_root]
        if not members:
            members = [attacker_root]

        for member in list(members):
            if member is None:
                continue
            if not bool(getattr(member, "has_extraction_of_fresh_disease", lambda: False)()):
                continue
            for model in list(getattr(member, "models", []) or []):
                if model is None or not getattr(model, "is_alive", True):
                    continue
                if bool(getattr(model, "_extraction_of_fresh_disease_applied", False)):
                    continue
                try:
                    current = int(getattr(model, "_objective_control", getattr(model, "objective_control", 0)) or 0)
                except Exception:
                    current = 0
                model._objective_control = int(current + 6)
                model._extraction_of_fresh_disease_applied = True

    def _on_unit_destroyed_recalculating(self, unit=None, destroyed_by_unit=None, **_kwargs) -> None:
        if unit is None or not bool(getattr(self, "is_authoritative", True)):
            return
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            mgr = getattr(army, "oath_of_moment", None)
            trigger_fn = getattr(mgr, "on_oath_target_destroyed", None) if mgr is not None else None
            if callable(trigger_fn):
                trigger_fn(unit, game=self, player=player, destroyed_by_unit=destroyed_by_unit)
            sm_mgr = getattr(army, "space_marines_detachments", None)
            boast_fn = getattr(sm_mgr, "heroes_all_on_unit_destroyed", None) if sm_mgr is not None else None
            if callable(boast_fn):
                boast_fn(unit, destroyed_by_unit=destroyed_by_unit, game=self)
            ulrik_fn = getattr(sm_mgr, "ulrik_slayers_oath_on_unit_destroyed", None) if sm_mgr is not None else None
            if callable(ulrik_fn):
                ulrik_fn(unit, destroyed_by_unit=destroyed_by_unit, game=self)

    def _on_unit_shooting_resolved_oath_of_moment_backup_promotion(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None or not bool(getattr(self, "is_authoritative", True)):
            return
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            mgr = getattr(army, "oath_of_moment", None)
            activate_fn = getattr(mgr, "on_attacking_unit_resolved", None) if mgr is not None else None
            if callable(activate_fn):
                activate_fn(attacker_unit, game=self, player=player)

    def _on_fight_sequence_complete_oath_of_moment_backup_promotion(self, unit=None, **_kwargs) -> None:
        if unit is None or not bool(getattr(self, "is_authoritative", True)):
            return
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            mgr = getattr(army, "oath_of_moment", None)
            activate_fn = getattr(mgr, "on_attacking_unit_resolved", None) if mgr is not None else None
            if callable(activate_fn):
                activate_fn(unit, game=self, player=player)

    def _on_shooting_targets_selected_cursed_circlet(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        if attacker_root is None:
            return
        managers: list[object] = []
        seen: set[int] = set()
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            if target_root is None:
                continue
            army = target_root.get_parent_army() if hasattr(target_root, "get_parent_army") else None
            mgr = getattr(army, "necrons_detachments", None) if army is not None else None
            record_fn = getattr(mgr, "cursed_circlet_record_targets_selected", None) if mgr is not None else None
            if not callable(record_fn):
                continue
            mgr_key = id(mgr)
            if mgr_key in seen:
                continue
            seen.add(mgr_key)
            managers.append(mgr)
        for mgr in managers:
            record_fn = getattr(mgr, "cursed_circlet_record_targets_selected", None)
            if callable(record_fn):
                record_fn(attacker_root, list(target_units or []), game=self)

    def _on_unit_shooting_resolved_cursed_circlet(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None:
            return

        requests: list[dict] = []
        for player in list(getattr(self, "players", []) or []):
            if player is None:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            mgr = getattr(army, "necrons_detachments", None)
            build_fn = getattr(mgr, "cursed_circlet_reactive_move_requests", None) if mgr is not None else None
            if not callable(build_fn):
                continue
            requests.extend(list(build_fn(attacker_root, game=self) or []))
        if not requests:
            return

        from ...utility.dice import get_roll

        try:
            from ...utility.event_bus import append_dice
        except Exception:
            append_dice = None

        for request_data in list(requests or []):
            unit = request_data.get("unit")
            player = request_data.get("player")
            if unit is None or player is None:
                continue
            source_name = str(request_data.get("source_name", "Cursed Circlet") or "Cursed Circlet").strip() or "Cursed Circlet"
            range_roll = str(request_data.get("range_roll", "D6") or "D6").strip().upper() or "D6"
            max_distance = int(get_roll(range_roll) or 0)
            if callable(append_dice):
                append_dice(player, f"{source_name}: {max_distance}")
            if max_distance <= 0:
                continue
            self._queue_reactive_move_movement_decision(
                player=player,
                unit=unit,
                max_distance=int(max_distance),
                kind="cursed_circlet",
                movement_type="reactive",
                reactive_movement_type="cursed_circlet",
                source=source_name,
                moving_unit=attacker_root,
                attacker_unit=attacker_root,
                range_value=int(max_distance),
                allow_engagement_range=bool(request_data.get("allow_engagement_range", True)),
                extra_context={
                    "cursed_circlet_closest_enemy_exclude_keywords_any": list(
                        request_data.get("closest_enemy_exclude_keywords_any", ("AIRCRAFT",)) or ("AIRCRAFT",)
                    ),
                },
            )

    def _on_shooting_targets_selected_blood_surge(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        snapshot = dict(self._blood_surge_shooting_snapshot.get(attacking_unit, {}) or {})
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            try:
                if not root.has_blood_surge():
                    continue
            except Exception:
                continue
            count = self._alive_model_count(root)
            if count <= 0:
                continue
            snapshot[root] = count
        if snapshot:
            self._blood_surge_shooting_snapshot[attacking_unit] = snapshot

    def _on_unit_shooting_resolved_blood_surge(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        snapshot = self._blood_surge_shooting_snapshot.pop(attacker_unit, {})
        if not snapshot:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        for target, before in snapshot.items():
            if target is None:
                continue
            after = self._alive_model_count(target)
            if after >= int(before or 0):
                continue
            try:
                if not target.has_blood_surge():
                    continue
            except Exception:
                continue
            can_fn = getattr(target, "can_blood_surge", None)
            if callable(can_fn):
                if not can_fn(game=self, game_map=getattr(self, "map", None)):
                    continue
            player = None
            try:
                player = target.get_parent_army().player
            except Exception:
                player = None
            is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("blood_surge_prompt"))
            if is_human and es is not None:
                es.publish(
                    "blood_surge_prompt",
                    player=player,
                    unit=target,
                    attacker_unit=attacker_unit,
                    game=self,
                )
                if has_sub:
                    continue
            if not is_human:
                msg = (
                    "Blood Surge: Move D6+2\" as close as possible to the closest non-AIRCRAFT enemy unit.\n"
                    "This unit cannot Blood Surge while Battle-shocked or within Engagement Range."
                )
                request = self._queue_reactive_move_confirmation(
                    player=player,
                    unit=target,
                    kind="blood_surge",
                    movement_type="blood_surge",
                    source="Blood Surge",
                    message=msg,
                    attacker_unit=attacker_unit,
                )
                continue
            move_fn = getattr(target, "auto_blood_surge_move", None)
            if callable(move_fn):
                max_dist = int(self.roll_blood_surge_distance(target) or 0)
                move_fn(getattr(self, "map", None), max_dist)
                target.mark_blood_surge_used(self)

    def _on_shooting_targets_selected_unhinged_vengeance(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        attacker_army = attacker_root.get_parent_army() if attacker_root is not None else None
        snapshot = dict(getattr(self, "_unhinged_vengeance_shooting_snapshot", {}).get(attacking_unit, {}) or {})
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            if attacker_army is not None and root.get_parent_army() is attacker_army:
                continue
            try:
                if not root.has_unhinged_vengeance():
                    continue
            except Exception:
                continue
            can_fn = getattr(root, "can_unhinged_vengeance", None)
            if callable(can_fn):
                if not can_fn(game=self, game_map=getattr(self, "map", None)):
                    continue
            model = getattr(root, "get_unhinged_vengeance_model", lambda: None)()
            if model is None or not getattr(model, "is_alive", True):
                continue
            try:
                before = int(getattr(model, "wounds", 0) or 0)
            except Exception:
                before = 0
            if before <= 0:
                continue
            snapshot[root] = int(before)
        if snapshot:
            if not hasattr(self, "_unhinged_vengeance_shooting_snapshot") or not isinstance(
                getattr(self, "_unhinged_vengeance_shooting_snapshot", None), dict
            ):
                self._unhinged_vengeance_shooting_snapshot = {}
            self._unhinged_vengeance_shooting_snapshot[attacking_unit] = snapshot

    def _on_unit_shooting_resolved_unhinged_vengeance(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        snapshots = getattr(self, "_unhinged_vengeance_shooting_snapshot", None)
        if not isinstance(snapshots, dict):
            return
        snapshot = snapshots.pop(attacker_unit, {})
        if not snapshot:
            return
        if not self.is_shooting_phase():
            return
        current_player = self.get_current_player()
        for target, before in snapshot.items():
            if target is None:
                continue
            try:
                target_player = target.get_parent_army().player
            except Exception:
                target_player = None
            if target_player is None or target_player is current_player:
                continue
            model = getattr(target, "get_unhinged_vengeance_model", lambda: None)()
            if model is None or not getattr(model, "is_alive", True):
                continue
            try:
                after = int(getattr(model, "wounds", 0) or 0)
            except Exception:
                after = int(before or 0)
            if after >= int(before or 0):
                continue
            can_fn = getattr(target, "can_unhinged_vengeance", None)
            if callable(can_fn):
                if not can_fn(game=self, game_map=getattr(self, "map", None)):
                    continue
            player = target_player
            is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("unhinged_vengeance_prompt"))
            if is_human and es is not None:
                es.publish(
                    "unhinged_vengeance_prompt",
                    player=player,
                    unit=target,
                    attacker_unit=attacker_unit,
                    game=self,
                )
                if has_sub:
                    continue
            msg = (
                "Unhinged Vengeance: Move D6+2\" as close as possible to the closest non-AIRCRAFT enemy unit.\n"
                "This model can end this move within Engagement Range of that enemy unit."
            )
            self._queue_reactive_move_confirmation(
                player=player,
                unit=target,
                kind="unhinged_vengeance",
                movement_type="unhinged_vengeance",
                source="Unhinged Vengeance",
                message=msg,
                attacker_unit=attacker_unit,
                allow_engagement_range=True,
            )

    def _on_shooting_targets_selected_guns_blazing(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return

        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        if attacker_root is None:
            return
        attacker_army = attacker_root.get_parent_army()
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
        if attacker_player is None:
            return
        if attacker_player is not self.get_current_player():
            return

        try:
            from ...utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return

        snapshot = []
        snapshot_by_source_id: dict[str, dict[str, Any]] = {}
        for raw_entry in list(getattr(self, "_guns_blazing_shooting_targets", {}).get(attacking_unit, []) or []):
            entry = self._normalize_guns_blazing_snapshot_entry(raw_entry)
            if entry is None:
                continue
            try:
                source_root = entry["unit"].get_attached_unit_root()
            except Exception:
                source_root = entry["unit"]
            if source_root is None:
                continue
            source_id = str(get_entity_id(source_root) or "")
            if not source_id:
                continue
            trigger_targets: list[Any] = []
            seen_target_ids: set[str] = set()
            for target in list(entry.get("trigger_targets", []) or []):
                if target is None:
                    continue
                try:
                    target_root = target.get_attached_unit_root()
                except Exception:
                    target_root = target
                if target_root is None:
                    continue
                target_id = str(get_entity_id(target_root) or "")
                if target_id and target_id in seen_target_ids:
                    continue
                if target_id:
                    seen_target_ids.add(target_id)
                trigger_targets.append(target_root)
            normalized = {"unit": source_root, "trigger_targets": trigger_targets}
            snapshot_by_source_id[source_id] = normalized
            snapshot.append(normalized)
        seen_ids = set(snapshot_by_source_id.keys())

        try:
            players = list(self.players or [])
        except Exception:
            players = []
        for player in players:
            if player is None or player is attacker_player:
                continue
            army = self._get_player_army(player)
            if army is None:
                continue
            roots: dict[str, Any] = {}
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None:
                    continue
                rid = str(get_entity_id(root) or "")
                if not rid:
                    continue
                roots[rid] = root
            for rid in sorted(list(roots.keys())):
                root = roots[rid]
                if rid in seen_ids:
                    continue
                rule_fn = getattr(root, "get_guns_blazing_rule", None)
                reactive_rule = rule_fn() if callable(rule_fn) else None
                if not isinstance(reactive_rule, dict):
                    continue
                if not bool(getattr(root, "can_use_guns_blazing", lambda **_k: False)(game=self, game_map=game_map)):
                    continue
                required_keyword = str(reactive_rule.get("friendly_keyword", "") or "").strip()
                try:
                    range_value = float(reactive_rule.get("range", 3.0) or 3.0)
                except Exception:
                    range_value = 3.0
                if range_value <= 0.0:
                    range_value = 3.0
                trigger_targets: list[Any] = []
                for target in list(target_units or []):
                    if target is None:
                        continue
                    try:
                        target_root = target.get_attached_unit_root()
                    except Exception:
                        target_root = target
                    if target_root is None:
                        continue
                    if target_root.get_parent_army() is not army:
                        continue
                    if required_keyword:
                        matches_keyword = False
                        matches_phrase_fn = getattr(root, "_unit_matches_keyword_phrase", None)
                        if callable(matches_phrase_fn):
                            try:
                                matches_keyword = bool(matches_phrase_fn(target_root, required_keyword, use_effective=True))
                            except Exception:
                                matches_keyword = False
                        if not matches_keyword:
                            has_kw = getattr(target_root, "has_any_keyword", None)
                            if callable(has_kw):
                                try:
                                    matches_keyword = bool(has_kw(required_keyword))
                                except Exception:
                                    matches_keyword = False
                        if not matches_keyword:
                            continue
                    if unit_within_range_of_unit(root, target_root, float(range_value), use_attached_aggregate=True):
                        trigger_targets.append(target_root)
                if not trigger_targets:
                    continue
                entry = snapshot_by_source_id.get(rid)
                if entry is None:
                    entry = {"unit": root, "trigger_targets": []}
                    snapshot_by_source_id[rid] = entry
                    snapshot.append(entry)
                    seen_ids.add(rid)
                seen_target_ids = {str(get_entity_id(target) or "") for target in list(entry.get("trigger_targets", []) or []) if target is not None}
                for target_root in trigger_targets:
                    target_id = str(get_entity_id(target_root) or "")
                    if target_id and target_id in seen_target_ids:
                        continue
                    if target_id:
                        seen_target_ids.add(target_id)
                    entry["trigger_targets"].append(target_root)

        if not snapshot:
            return
        if not hasattr(self, "_guns_blazing_shooting_targets") or not isinstance(
            getattr(self, "_guns_blazing_shooting_targets", None), dict
        ):
            self._guns_blazing_shooting_targets = {}
        self._guns_blazing_shooting_targets[attacking_unit] = list(snapshot)

    @staticmethod
    def _normalize_guns_blazing_snapshot_entry(entry) -> dict[str, Any] | None:
        if entry is None:
            return None
        if isinstance(entry, dict):
            source = entry.get("unit")
            trigger_targets = list(entry.get("trigger_targets", []) or [])
        else:
            source = entry
            trigger_targets = []
        if source is None:
            return None
        return {
            "unit": source,
            "trigger_targets": [target for target in trigger_targets if target is not None],
        }

    def _guns_blazing_trigger_target_invalidated_by_ranged_restriction(self, attacker_unit, trigger_target, game_map) -> bool:
        if attacker_unit is None or trigger_target is None or game_map is None:
            return False
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        try:
            target_root = trigger_target.get_attached_unit_root()
        except Exception:
            target_root = trigger_target
        if attacker_root is None or target_root is None:
            return False
        if not bool(getattr(target_root, "is_alive", lambda: False)()):
            return False
        try:
            limit, _sources = target_root.get_ranged_targeting_restriction(
                game_map=game_map,
                ignore_lone_operative=False,
            )
        except Exception:
            return False
        if limit is None:
            return False
        for model in list(getattr(attacker_root, "models", []) or []):
            for wargear in list(getattr(model, "wargear", []) or []):
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged):
                    continue
                try:
                    if not bool(is_ranged()):
                        continue
                except Exception:
                    continue
                for profile in list((getattr(wargear, "profiles", {}) or {}).values()):
                    if profile is None:
                        continue
                    try:
                        if attacker_root._can_model_shoot_weapon_at_target(model, profile, target_root, game_map):
                            return False
                    except Exception:
                        continue
        return True

    def _on_unit_shooting_resolved_guns_blazing(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        shots = {}
        try:
            shots = getattr(self, "_guns_blazing_shooting_targets", {})
        except Exception:
            shots = {}
        if not isinstance(shots, dict):
            return
        targets = list(shots.pop(attacker_unit, []) or [])
        if not targets:
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return

        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None:
            return
        attacker_army = attacker_root.get_parent_army()
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
        if attacker_player is None or attacker_player is not self.get_current_player():
            return

        queue = getattr(self, "decision_queue", None)
        pending_for_source: set[str] = set()
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_DECLARE_SHOTS:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if not bool(ctx.get("guns_blazing_flow", False)):
                    continue
                uid = str(ctx.get("unit_id", "") or "")
                if uid:
                    pending_for_source.add(uid)

        for raw_entry in list(targets):
            entry = self._normalize_guns_blazing_snapshot_entry(raw_entry)
            if entry is None:
                continue
            source = entry["unit"]
            trigger_targets = list(entry.get("trigger_targets", []) or [])
            try:
                root = source.get_attached_unit_root()
            except Exception:
                root = source
            if root is None:
                continue
            source_id = str(get_entity_id(root) or "")
            if not source_id:
                continue
            if source_id in pending_for_source:
                continue
            if trigger_targets and all(
                self._guns_blazing_trigger_target_invalidated_by_ranged_restriction(attacker_root, trigger_target, game_map)
                for trigger_target in trigger_targets
            ):
                continue
            if not bool(getattr(root, "can_use_guns_blazing", lambda **_k: False)(game=self, game_map=game_map, enemy_unit=attacker_root)):
                continue
            if not self._setup_reactive_can_shoot_target(root, attacker_root):
                continue
            source_name = "Guns Blazing"
            rule_fn = getattr(root, "get_guns_blazing_rule", None)
            reactive_rule = rule_fn() if callable(rule_fn) else None
            if isinstance(reactive_rule, dict):
                source_name = str(reactive_rule.get("source", "") or source_name).strip() or source_name
            player = getattr(root.get_parent_army(), "player", None)
            if player is None:
                continue
            request = self._queue_setup_reactive_shooting_decision(
                player=player,
                unit=root,
                target_unit=attacker_root,
                source=source_name,
            )
            if request is None:
                continue
            request.context["guns_blazing_flow"] = True
            request.context["guns_blazing_source"] = source_name
            request.context["guns_blazing_enemy_unit_id"] = str(get_entity_id(attacker_root) or "")
            request.context["guns_blazing_unit_id"] = source_id
            pending_for_source.add(source_id)

    def _on_unit_destroyed_storm_of_vengeance(
        self,
        unit=None,
        last_model=None,
        destroyed_by_unit=None,
        game_map=None,
        **_kwargs,
    ) -> None:
        if unit is None or destroyed_by_unit is None:
            return
        if not self.is_shooting_phase():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        if game_map is None:
            game_map = getattr(self, "map", None)

        try:
            destroyed_root = unit.get_attached_unit_root()
        except Exception:
            destroyed_root = unit
        try:
            attacker_root = destroyed_by_unit.get_attached_unit_root()
        except Exception:
            attacker_root = destroyed_by_unit
        if destroyed_root is None or attacker_root is None or destroyed_root is attacker_root:
            return

        destroyed_army = destroyed_root.get_parent_army()
        attacker_army = attacker_root.get_parent_army()
        if destroyed_army is None or attacker_army is None or destroyed_army is attacker_army:
            return
        attacker_player = getattr(attacker_army, "player", None)
        if attacker_player is None or attacker_player is not self.get_current_player():
            return

        try:
            from ...utility.aura_utils import distance_between_models_bases_3d, unit_within_range_of_unit
        except Exception:
            return

        attacker_id = str(get_entity_id(attacker_root) or "")
        if not attacker_id:
            return

        roots: dict[str, Any] = {}
        for candidate in list(getattr(destroyed_army, "units", []) or []):
            if candidate is None:
                continue
            try:
                root = candidate.get_attached_unit_root()
            except Exception:
                root = candidate
            if root is None:
                continue
            rid = str(get_entity_id(root) or "")
            if rid:
                roots[rid] = root

        if not roots:
            return

        pending = getattr(self, "_storm_of_vengeance_pending", None)
        if not isinstance(pending, dict):
            pending = {}
            self._storm_of_vengeance_pending = pending
        bucket = list(pending.get(attacker_id, []) or [])
        pending_ids = {
            str(get_entity_id(existing) or "")
            for existing in list(bucket or [])
            if existing is not None and str(get_entity_id(existing) or "")
        }

        for rid in sorted(list(roots.keys())):
            root = roots[rid]
            if root is None or root is destroyed_root:
                continue
            if rid in pending_ids:
                continue
            if not self._unit_is_active_for_reactive_trigger(root):
                continue
            reactive_rule = getattr(root, "get_storm_of_vengeance_rule", lambda: None)()
            if not isinstance(reactive_rule, dict):
                continue
            if not bool(getattr(root, "can_use_storm_of_vengeance", lambda **_k: False)(game=self, game_map=game_map, enemy_unit=attacker_root)):
                continue

            required_keyword = str(reactive_rule.get("friendly_keyword", "") or "").strip()
            if required_keyword:
                matches_keyword = False
                matches_phrase_fn = getattr(root, "_unit_matches_keyword_phrase", None)
                if callable(matches_phrase_fn):
                    try:
                        matches_keyword = bool(matches_phrase_fn(destroyed_root, required_keyword, use_effective=False))
                    except Exception:
                        matches_keyword = False
                if not matches_keyword:
                    has_kw = getattr(destroyed_root, "has_any_keyword", None)
                    if callable(has_kw):
                        try:
                            matches_keyword = bool(has_kw(required_keyword))
                        except Exception:
                            matches_keyword = False
                if not matches_keyword:
                    continue

            try:
                range_value = float(reactive_rule.get("range", 6.0) or 6.0)
            except Exception:
                range_value = 6.0
            if range_value <= 0.0:
                range_value = 6.0

            in_range = False
            if last_model is not None and bool(getattr(last_model, "model_base", None) is not None):
                for source_model in list(getattr(root, "models", []) or []):
                    if not getattr(source_model, "is_alive", False):
                        continue
                    if getattr(source_model, "model_base", None) is None:
                        continue
                    try:
                        if float(distance_between_models_bases_3d(source_model, last_model)) <= float(range_value) + 1e-6:
                            in_range = True
                            break
                    except Exception:
                        continue
            if not in_range:
                try:
                    in_range = bool(unit_within_range_of_unit(root, destroyed_root, float(range_value), use_attached_aggregate=True))
                except Exception:
                    in_range = False
            if not in_range:
                continue

            bucket.append(root)
            pending_ids.add(rid)

        if bucket:
            pending[attacker_id] = list(bucket)

    def _on_unit_shooting_resolved_storm_of_vengeance(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        pending = getattr(self, "_storm_of_vengeance_pending", None)
        if not isinstance(pending, dict):
            return

        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None:
            return
        attacker_army = attacker_root.get_parent_army()
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
        if attacker_player is None or attacker_player is not self.get_current_player():
            return

        attacker_id = str(get_entity_id(attacker_root) or "")
        if not attacker_id:
            return
        sources = list(pending.pop(attacker_id, []) or [])
        if not sources:
            return

        game_map = getattr(self, "map", None)
        if game_map is None:
            return

        queue = getattr(self, "decision_queue", None)
        pending_for_source: set[str] = set()
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_DECLARE_SHOTS:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if not bool(ctx.get("storm_of_vengeance_flow", False)):
                    continue
                uid = str(ctx.get("unit_id", "") or "")
                if uid:
                    pending_for_source.add(uid)

        for source in list(sources):
            if source is None:
                continue
            try:
                root = source.get_attached_unit_root()
            except Exception:
                root = source
            if root is None or not self._unit_is_active_for_reactive_trigger(root):
                continue
            source_id = str(get_entity_id(root) or "")
            if not source_id or source_id in pending_for_source:
                continue
            if not bool(getattr(root, "can_use_storm_of_vengeance", lambda **_k: False)(game=self, game_map=game_map, enemy_unit=attacker_root)):
                continue
            if not self._setup_reactive_can_shoot_target(root, attacker_root):
                continue

            source_name = "Storm of Vengeance"
            rule_fn = getattr(root, "get_storm_of_vengeance_rule", None)
            reactive_rule = rule_fn() if callable(rule_fn) else None
            if isinstance(reactive_rule, dict):
                source_name = str(reactive_rule.get("source", "") or source_name).strip() or source_name
            player = getattr(root.get_parent_army(), "player", None)
            if player is None:
                continue
            request = self._queue_setup_reactive_shooting_decision(
                player=player,
                unit=root,
                target_unit=attacker_root,
                source=source_name,
            )
            if request is None:
                continue
            request.context["storm_of_vengeance_flow"] = True
            request.context["storm_of_vengeance_source"] = source_name
            request.context["storm_of_vengeance_enemy_unit_id"] = attacker_id
            request.context["storm_of_vengeance_unit_id"] = source_id
            pending_for_source.add(source_id)

    def _on_unit_shooting_resolved_hypersensory_abilities(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        try:
            attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        if attacker_root is None:
            return
        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("hypersensory_abilities_pending_move", False)):
            return

        source_name = str(sr.get("hypersensory_abilities_pending_move_source", "") or "Hypersensory Abilities").strip()
        source_name = source_name or "Hypersensory Abilities"
        enemy_unit_id = str(sr.get("hypersensory_abilities_pending_enemy_unit_id", "") or "")
        sr.pop("hypersensory_abilities_pending_move", None)
        sr.pop("hypersensory_abilities_pending_move_source", None)
        sr.pop("hypersensory_abilities_pending_enemy_unit_id", None)
        attacker_root.special_rules = sr

        if not self._unit_is_active_for_reactive_trigger(attacker_root):
            return
        player = getattr(attacker_root.get_parent_army(), "player", None)
        if player is None:
            return

        queue = getattr(self, "decision_queue", None)
        source_id = str(get_entity_id(attacker_root) or "")
        if source_id and queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_MOVE_UNIT:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("reactive_move_kind", "") or "").strip() != "hypersensory_abilities":
                    continue
                if str(ctx.get("reactive_move_unit_id", "") or "") == source_id:
                    return

        roll = int(get_roll("D6") or 0)
        try:
            from ...utility.event_bus import append_dice

            append_dice(player, f"{source_name}: {roll}")
        except Exception:
            pass
        if roll <= 0:
            return

        resolve_unit_fn = getattr(self, "_resolve_unit_by_id", None)
        enemy_unit = resolve_unit_fn(enemy_unit_id) if callable(resolve_unit_fn) and enemy_unit_id else None
        self._queue_reactive_move_movement_decision(
            player=player,
            unit=attacker_root,
            max_distance=int(roll),
            kind="hypersensory_abilities",
            movement_type="reactive",
            source=source_name,
            moving_unit=enemy_unit,
        )

    def _on_shooting_targets_selected_brazen_fury(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        snapshot = dict(self._brazen_fury_shooting_snapshot.get(attacking_unit, {}) or {})
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            try:
                if not root.has_brazen_fury():
                    continue
            except Exception:
                continue
            count = self._alive_model_count(root)
            if count <= 0:
                continue
            snapshot[root] = count
        if snapshot:
            self._brazen_fury_shooting_snapshot[attacking_unit] = snapshot

    def _on_unit_shooting_resolved_brazen_fury(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        snapshot = self._brazen_fury_shooting_snapshot.pop(attacker_unit, {})
        if not snapshot:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        if "SHOOT" not in phase_name.upper():
            return
        current_player = None
        try:
            current_player = self.get_current_player()
        except Exception:
            current_player = None
        for target, before in snapshot.items():
            if target is None:
                continue
            after = self._alive_model_count(target)
            if after >= int(before or 0):
                continue
            try:
                if not target.has_brazen_fury():
                    continue
            except Exception:
                continue
            try:
                target_player = target.get_parent_army().player
            except Exception:
                target_player = None
            if target_player is None or current_player is None:
                continue
            if target_player is current_player:
                continue
            can_fn = getattr(target, "can_brazen_fury", None)
            if callable(can_fn):
                if not can_fn(game=self, game_map=getattr(self, "map", None)):
                    continue
            player = target_player
            is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("brazen_fury_prompt"))
            if is_human and es is not None:
                es.publish(
                    "brazen_fury_prompt",
                    player=player,
                    unit=target,
                    attacker_unit=attacker_unit,
                    game=self,
                )
                if has_sub:
                    continue
            msg = (
                "Brazen Fury: Move D6\" as close as possible to the closest non-AIRCRAFT enemy unit.\n"
                "This unit cannot Brazen Fury while Battle-shocked or within Engagement Range."
            )
            self._queue_reactive_move_confirmation(
                player=player,
                unit=target,
                kind="brazen_fury",
                movement_type="brazen_fury",
                source="Brazen Fury",
                message=msg,
                attacker_unit=attacker_unit,
            )

    def _on_shooting_targets_selected_horde_move(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        snapshot = dict(self._horde_move_shooting_snapshot.get(attacking_unit, {}) or {})
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            try:
                if not root.has_horde_move():
                    continue
            except Exception:
                continue
            trigger_on_hits = False
            has_driven_by_fury = getattr(root, "has_driven_by_fury", None)
            if callable(has_driven_by_fury):
                try:
                    trigger_on_hits = bool(has_driven_by_fury())
                except Exception:
                    trigger_on_hits = False
            count = self._alive_model_count(root)
            if count <= 0 and not trigger_on_hits:
                continue
            snapshot[root] = {
                "alive_models_before": int(count),
                "trigger_on_hits": bool(trigger_on_hits),
            }
        if snapshot:
            self._horde_move_shooting_snapshot[attacking_unit] = snapshot

    def _on_unit_shooting_resolved_horde_move(self, attacker_unit=None, hits_by_target=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        snapshot = self._horde_move_shooting_snapshot.pop(attacker_unit, {})
        if not snapshot:
            return
        resolved_hits_by_target = {}
        if isinstance(hits_by_target, dict):
            for raw_target, hits in list(hits_by_target.items()):
                if raw_target is None:
                    continue
                try:
                    target_root = raw_target.get_attached_unit_root()
                except Exception:
                    target_root = raw_target
                if target_root is None:
                    continue
                target_id = str(get_entity_id(target_root) or "")
                if not target_id:
                    continue
                try:
                    resolved_hits_by_target[target_id] = int(resolved_hits_by_target.get(target_id, 0) or 0) + int(hits or 0)
                except Exception:
                    continue
        for target, before in snapshot.items():
            if target is None:
                continue
            target_id = str(get_entity_id(target) or "")
            before_count = 0
            trigger_on_hits = False
            if isinstance(before, dict):
                try:
                    before_count = int(before.get("alive_models_before", 0) or 0)
                except Exception:
                    before_count = 0
                trigger_on_hits = bool(before.get("trigger_on_hits", False))
            else:
                try:
                    before_count = int(before or 0)
                except Exception:
                    before_count = 0
            if trigger_on_hits:
                if int(resolved_hits_by_target.get(target_id, 0) or 0) <= 0:
                    continue
            else:
                after = self._alive_model_count(target)
                if after >= int(before_count or 0):
                    continue
            try:
                if not target.has_horde_move():
                    continue
            except Exception:
                continue
            can_fn = getattr(target, "can_horde_move", None)
            if callable(can_fn):
                if not can_fn(game=self, game_map=getattr(self, "map", None)):
                    continue
            rule_fn = getattr(target, "get_horde_move_rule", None)
            rule = rule_fn(game=self) if callable(rule_fn) else None
            if not isinstance(rule, dict):
                rule = {}
            player = None
            try:
                player = target.get_parent_army().player
            except Exception:
                player = None
            is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("horde_move_prompt"))
            if is_human and es is not None:
                es.publish(
                    "horde_move_prompt",
                    player=player,
                    unit=target,
                    attacker_unit=attacker_unit,
                    game=self,
                )
                if has_sub:
                    continue
            has_righteous_zeal = False
            has_righteous_zeal_fn = getattr(target, "has_righteous_zeal", None)
            if callable(has_righteous_zeal_fn):
                try:
                    has_righteous_zeal = bool(has_righteous_zeal_fn())
                except Exception:
                    has_righteous_zeal = False
            has_insurmountable_odds = False
            has_insurmountable_odds_fn = getattr(target, "has_insurmountable_odds", None)
            if callable(has_insurmountable_odds_fn):
                try:
                    has_insurmountable_odds = bool(has_insurmountable_odds_fn())
                except Exception:
                    has_insurmountable_odds = False
            source_name = str(rule.get("source", "") or "Horde Move").strip() or "Horde Move"
            try:
                fixed_distance = int(rule.get("fixed_distance", 0) or 0)
            except Exception:
                fixed_distance = 0
            if has_righteous_zeal:
                msg = (
                    "Righteous Zeal: Move D6+2\" as close as possible to the closest non-AIRCRAFT enemy unit.\n"
                    "This unit cannot make a Righteous Zeal move while Battle-shocked or within Engagement Range, and can only make one such move per phase."
                )
                source_name = "Righteous Zeal"
            elif has_insurmountable_odds:
                msg = (
                    "Insurmountable Odds: Roll D6 and make a Surge move up to that distance as close as possible to the closest non-AIRCRAFT enemy unit.\n"
                    "This unit can move within Engagement Range and cannot make this move while Battle-shocked."
                )
                source_name = "Insurmountable Odds"
            elif source_name.lower() == "glory of ultramar":
                msg = (
                    "Glory of Ultramar: Roll D6 and make a Surge move up to that distance as close as possible to the closest non-AIRCRAFT enemy unit.\n"
                    "This unit can move within Engagement Range of that enemy unit, and cannot make this move while Battle-shocked "
                    "or within Engagement Range. It can only make one Glory of Ultramar move per phase."
                )
            elif source_name.lower() == "brood surge":
                distance_text = f"{int(fixed_distance)}\"" if fixed_distance > 0 else "D6\""
                msg = (
                    f"Brood Surge: Move {distance_text} as close as possible to the closest non-AIRCRAFT enemy unit.\n"
                    "This unit can move within Engagement Range of that enemy unit and cannot make this move while Battle-shocked."
                )
            elif source_name.lower() == "driven by fury":
                msg = (
                    "Driven by Fury: Move D6+2\" as close as possible to the closest non-AIRCRAFT enemy unit.\n"
                    "This model can move within Engagement Range of that enemy unit, and cannot make this move while "
                    "Battle-shocked or within Engagement Range. It can only make one Driven by Fury move per phase."
                )
            else:
                msg = (
                    "Horde Move: Move D6\" as close as possible to the closest non-AIRCRAFT enemy unit.\n"
                    "This unit cannot make a Horde move while Battle-shocked."
                )
            self._queue_reactive_move_confirmation(
                player=player,
                unit=target,
                kind="horde_move",
                movement_type="horde_move",
                source=source_name,
                message=msg,
                attacker_unit=attacker_unit,
                allow_engagement_range=bool(rule.get("allow_engagement_range", False)),
            )

    def _on_shooting_targets_selected_blistering_assault(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        attacker_army = attacker_root.get_parent_army() if attacker_root is not None else None
        snapshot = dict(getattr(self, "_blistering_assault_shooting_snapshot", {}).get(attacking_unit, {}) or {})
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            if attacker_army is not None and root.get_parent_army() is attacker_army:
                continue
            try:
                if not root.has_blistering_assault():
                    continue
            except Exception:
                continue
            before = int(self._alive_model_wounds_total(root) or 0)
            if before <= 0:
                continue
            snapshot[root] = int(before)
        if snapshot:
            if not hasattr(self, "_blistering_assault_shooting_snapshot") or not isinstance(
                getattr(self, "_blistering_assault_shooting_snapshot", None), dict
            ):
                self._blistering_assault_shooting_snapshot = {}
            self._blistering_assault_shooting_snapshot[attacking_unit] = snapshot

    def _on_unit_shooting_resolved_blistering_assault(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        snapshots = getattr(self, "_blistering_assault_shooting_snapshot", None)
        if not isinstance(snapshots, dict):
            return
        snapshot = snapshots.pop(attacker_unit, {})
        if not snapshot:
            return
        if not self.is_shooting_phase():
            return
        current_player = self.get_current_player()
        for target, before in snapshot.items():
            if target is None:
                continue
            try:
                target_player = target.get_parent_army().player
            except Exception:
                target_player = None
            if target_player is None or target_player is current_player:
                continue
            after = int(self._alive_model_wounds_total(target) or 0)
            if after >= int(before or 0):
                continue
            can_fn = getattr(target, "can_blistering_assault", None)
            if callable(can_fn):
                if not can_fn(game=self, game_map=getattr(self, "map", None)):
                    continue
            player = target_player
            is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("blistering_assault_prompt"))
            if is_human and es is not None:
                es.publish(
                    "blistering_assault_prompt",
                    player=player,
                    unit=target,
                    attacker_unit=attacker_unit,
                    game=self,
                )
                if has_sub:
                    continue
            msg = (
                "Blistering Assault: Move D6+2\" as close as possible to the closest enemy unit.\n"
                "This unit can end this move within Engagement Range of that enemy unit."
            )
            self._queue_reactive_move_confirmation(
                player=player,
                unit=target,
                kind="blistering_assault",
                movement_type="blistering_assault",
                source="Blistering Assault",
                message=msg,
                attacker_unit=attacker_unit,
                allow_engagement_range=True,
            )

    def _on_shooting_targets_selected_bestial_rage(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        attacker_army = attacker_root.get_parent_army() if attacker_root is not None else None
        snapshot = dict(getattr(self, "_bestial_rage_shooting_snapshot", {}).get(attacking_unit, {}) or {})
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            if attacker_army is not None and root.get_parent_army() is attacker_army:
                continue
            try:
                if not root.has_bestial_rage():
                    continue
            except Exception:
                continue
            before = int(self._alive_model_wounds_total(root) or 0)
            if before <= 0:
                continue
            snapshot[root] = int(before)
        if snapshot:
            if not hasattr(self, "_bestial_rage_shooting_snapshot") or not isinstance(
                getattr(self, "_bestial_rage_shooting_snapshot", None), dict
            ):
                self._bestial_rage_shooting_snapshot = {}
            self._bestial_rage_shooting_snapshot[attacking_unit] = snapshot

    def _on_unit_shooting_resolved_bestial_rage(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        snapshots = getattr(self, "_bestial_rage_shooting_snapshot", None)
        if not isinstance(snapshots, dict):
            return
        snapshot = snapshots.pop(attacker_unit, {})
        if not snapshot:
            return
        if not self.is_shooting_phase():
            return
        current_player = self.get_current_player()
        for target, before in snapshot.items():
            if target is None:
                continue
            try:
                target_player = target.get_parent_army().player
            except Exception:
                target_player = None
            if target_player is None or target_player is current_player:
                continue
            after = int(self._alive_model_wounds_total(target) or 0)
            if after >= int(before or 0):
                continue
            can_fn = getattr(target, "can_bestial_rage", None)
            if callable(can_fn):
                if not can_fn(game=self, game_map=getattr(self, "map", None)):
                    continue
            player = target_player
            is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("bestial_rage_prompt"))
            if is_human and es is not None:
                es.publish(
                    "bestial_rage_prompt",
                    player=player,
                    unit=target,
                    attacker_unit=attacker_unit,
                    game=self,
                )
                if has_sub:
                    continue
            msg = (
                "Bestial Rage: Move D6+2\" as close as possible to the closest non-AIRCRAFT enemy unit.\n"
                "This model can end this move within Engagement Range of that enemy unit, and can only make one Bestial Rage move per phase."
            )
            self._queue_reactive_move_confirmation(
                player=player,
                unit=target,
                kind="bestial_rage",
                movement_type="bestial_rage",
                source="Bestial Rage",
                message=msg,
                attacker_unit=attacker_unit,
                allow_engagement_range=True,
            )

    def _on_shooting_targets_selected_aggressive_leader_beast(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        if not self.is_shooting_phase():
            return
        try:
            attacker_root = attacking_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacking_unit
        attacker_army = attacker_root.get_parent_army() if attacker_root is not None else None
        snapshots = getattr(self, "_aggressive_leader_beast_shooting_snapshot", None)
        if not isinstance(snapshots, dict):
            snapshots = {}
        snapshot = dict(snapshots.get(attacking_unit, {}) or {})
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            if attacker_army is not None and root.get_parent_army() is attacker_army:
                continue
            try:
                if not root.has_aggressive_leader_beast():
                    continue
            except Exception:
                continue
            can_fn = getattr(root, "can_aggressive_leader_beast", None)
            if callable(can_fn):
                if not can_fn(game=self, game_map=getattr(self, "map", None)):
                    continue
            count = int(self._alive_model_count(root) or 0)
            if count <= 0:
                continue
            snapshot[root] = int(count)
        if snapshot:
            if not hasattr(self, "_aggressive_leader_beast_shooting_snapshot") or not isinstance(
                getattr(self, "_aggressive_leader_beast_shooting_snapshot", None), dict
            ):
                self._aggressive_leader_beast_shooting_snapshot = {}
            self._aggressive_leader_beast_shooting_snapshot[attacking_unit] = snapshot

    def _on_unit_shooting_resolved_aggressive_leader_beast(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        snapshots = getattr(self, "_aggressive_leader_beast_shooting_snapshot", None)
        if not isinstance(snapshots, dict):
            return
        snapshot = snapshots.pop(attacker_unit, {})
        if not snapshot:
            return
        if not self.is_shooting_phase():
            return
        current_player = self.get_current_player()
        for target, before in snapshot.items():
            if target is None:
                continue
            try:
                target_player = target.get_parent_army().player
            except Exception:
                target_player = None
            if target_player is None or target_player is current_player:
                continue
            after = int(self._alive_model_count(target) or 0)
            if after >= int(before or 0):
                continue
            can_fn = getattr(target, "can_aggressive_leader_beast", None)
            if callable(can_fn):
                if not can_fn(game=self, game_map=getattr(self, "map", None)):
                    continue
            player = target_player
            is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("aggressive_leader_beast_prompt"))
            if is_human and es is not None:
                es.publish(
                    "aggressive_leader_beast_prompt",
                    player=player,
                    unit=target,
                    attacker_unit=attacker_unit,
                    game=self,
                )
                if has_sub:
                    continue
            msg = (
                "Aggressive Leader-beast: Roll D6 and make a Surge move up to that distance.\n"
                "The move must end as close as possible to the closest non-AIRCRAFT enemy unit, "
                "can end within Engagement Range, and cannot be made while Battle-shocked or already within Engagement Range."
            )
            self._queue_reactive_move_confirmation(
                player=player,
                unit=target,
                kind="aggressive_leader_beast",
                movement_type="aggressive_leader_beast",
                source="Aggressive Leader-beast",
                message=msg,
                attacker_unit=attacker_unit,
                allow_engagement_range=True,
            )

    def _on_shooting_targets_selected_frenzy(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        targets = list(self._frenzy_shooting_targets.get(attacking_unit, []) or [])
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            try:
                if not root.has_frenzy():
                    continue
            except Exception:
                continue
            if root not in targets:
                targets.append(root)
        if targets:
            self._frenzy_shooting_targets[attacking_unit] = targets

    def _on_unit_shooting_resolved_frenzy(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        targets = list(self._frenzy_shooting_targets.pop(attacker_unit, []) or [])
        if not targets:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        for target in targets:
            if target is None:
                continue
            try:
                if not target.has_frenzy():
                    continue
            except Exception:
                continue
            options = list(self._frenzy_available_actions(target, attacker_unit, phase_name=phase_name))
            if not options:
                continue
            player = None
            try:
                player = target.get_parent_army().player
            except Exception:
                player = None
            is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("frenzy_prompt"))
            if is_human and es is not None:
                es.publish(
                    "frenzy_prompt",
                    player=player,
                    unit=target,
                    attacker_unit=attacker_unit,
                    options=list(options),
                    game=self,
                )
                if has_sub:
                    continue
            if "shoot" in options:
                self._execute_frenzy_shooting(target, attacker_unit)
            elif "fight" in options:
                self._execute_frenzy_fight(target, attacker_unit, phase_name=phase_name)

    def _on_fight_targets_selected_frenzy(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None:
            return
        if not target_units:
            return
        targets = list(self._frenzy_fight_targets.get(attacking_unit, []) or [])
        for target in list(target_units or []):
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            try:
                if not root.has_frenzy():
                    continue
            except Exception:
                continue
            if root not in targets:
                targets.append(root)
        if targets:
            self._frenzy_fight_targets[attacking_unit] = targets

    def _on_fight_targets_selected_hysterical_frenzy(self, attacking_unit=None, target_units=None, **_kwargs) -> None:
        if attacking_unit is None or not target_units:
            return
        if not self.is_fight_phase():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        if self.map is None:
            return

        from ..decision_kinds import DECISION_CHOOSE_HYSTERICAL_FRENZY_PSYKER
        from ..decisions import DecisionOption, DecisionRequest

        pending_targets: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_HYSTERICAL_FRENZY_PSYKER:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                tid = str(ctx.get("target_unit_id", "") or "")
                if tid:
                    pending_targets.add(tid)

        def _unit_sort_key(u):
            return str(get_entity_id(u) or getattr(u, "name", "") or "")

        def _model_sort_key(m):
            return str(get_entity_id(m) or getattr(m, "name", "") or "")

        def _model_used_this_phase(model, phase_key: str) -> bool:
            eff = getattr(model, "_temporary_effects", None)
            if not isinstance(eff, dict):
                return False
            entry = eff.get("hysterical_frenzy_used")
            if not isinstance(entry, dict):
                return False
            exp = str(entry.get("expires_phase", "") or "").strip().upper()
            return bool(exp and exp == phase_key)

        attacker_army = None
        get_army = getattr(attacking_unit, "get_parent_army", None)
        if callable(get_army):
            attacker_army = get_army()

        for target in list(target_units or []):
            if target is None:
                continue
            target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
            if target_root is None or not target_root.is_alive():
                continue
            if not getattr(target_root, "deployed", True):
                continue
            if getattr(target_root, "is_in_reserves", lambda: False)() or getattr(target_root, "is_embarked", False):
                continue
            if attacker_army is not None:
                target_army = target_root.get_parent_army() if hasattr(target_root, "get_parent_army") else None
                if target_army is not None and target_army == attacker_army:
                    continue
            has_kw = getattr(target_root, "has_any_keyword", None)
            if not callable(has_kw):
                continue
            if not (has_kw("SLAANESH") and has_kw("LEGIONES DAEMONICA")):
                continue
            target_id = str(get_entity_id(target_root) or "")
            if not target_id or target_id in pending_targets:
                continue
            tsr = getattr(target_root, "special_rules", None)
            if isinstance(tsr, dict) and tsr.get("hysterical_frenzy_active"):
                exp = str(tsr.get("hysterical_frenzy_expires_phase", "") or "").strip().upper()
                if exp == "FIGHT_PHASE":
                    continue
            defender_army = target_root.get_parent_army() if hasattr(target_root, "get_parent_army") else None
            defender_player = getattr(defender_army, "player", None) if defender_army is not None else None
            if defender_player is None:
                continue
            if defender_army is None:
                defender_army = defender_player.get_army() if hasattr(defender_player, "get_army") else None
            if defender_army is None:
                continue

            candidates = []
            seen_models: set[str] = set()
            for unit in sorted(list(defender_army.units or []), key=_unit_sort_key):
                if unit is None or not unit.is_alive():
                    continue
                root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
                for entry in list(root.iter_hysterical_frenzy_models() or []):
                    model = entry.get("model")
                    if model is None or not getattr(model, "is_alive", False):
                        continue
                    mid = str(get_entity_id(model) or "")
                    if not mid or mid in seen_models:
                        continue
                    if hasattr(model, "has_any_keyword") and not model.has_any_keyword("PSYKER"):
                        continue
                    if _model_used_this_phase(model, "FIGHT_PHASE"):
                        continue
                    range_value = int(entry.get("range", 6) or 6)
                    in_range = True
                    within_fn = getattr(root, "_model_within_range_of_unit", None)
                    if callable(within_fn):
                        in_range = bool(within_fn(model, target_root, float(range_value)))
                    if not in_range:
                        continue
                    seen_models.add(mid)
                    candidates.append(
                        {
                            "model": model,
                            "model_id": mid,
                            "range": int(range_value),
                            "source": str(entry.get("source", "") or "Hysterical Frenzy").strip() or "Hysterical Frenzy",
                            "source_unit_id": get_entity_id(root),
                        }
                    )

            if not candidates:
                continue
            candidates = sorted(candidates, key=lambda c: str(c.get("model_id") or ""))
            ability_name = str(candidates[0].get("source") or "Hysterical Frenzy").strip() or "Hysterical Frenzy"
            options = [DecisionOption.create("Decline", payload={"action": "skip"})]
            for cand in candidates:
                model = cand.get("model")
                label = str(getattr(model, "name", "") or "Psyker")
                options.append(
                    DecisionOption.create(
                        label,
                        payload={
                            "model_id": cand.get("model_id"),
                            "target_unit_id": target_id,
                            "range": int(cand.get("range", 6) or 6),
                            "source_unit_id": cand.get("source_unit_id"),
                        },
                    )
                )
            ctx = {
                "ability": "hysterical_frenzy",
                "ability_name": ability_name,
                "target_unit_id": target_id,
                "phase": "Fight phase",
            }
            request = DecisionRequest.create(
                DECISION_CHOOSE_HYSTERICAL_FRENZY_PSYKER,
                f"{ability_name}: select a Psyker to use this ability (or decline).",
                player_id=getattr(defender_player, "id", None),
                options=options,
                context=ctx,
            )
            self.request_decision(request)

    def _on_fight_attacks_resolved_frenzy(self, unit=None, target_unit=None, **_kwargs) -> None:
        attacker_unit = unit
        if attacker_unit is None:
            return
        targets = list(self._frenzy_fight_targets.pop(attacker_unit, []) or [])
        if not targets:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        for target in targets:
            if target is None:
                continue
            try:
                if not target.has_frenzy():
                    continue
            except Exception:
                continue
            options = list(self._frenzy_available_actions(target, attacker_unit, phase_name=phase_name))
            if not options:
                continue
            player = None
            try:
                player = target.get_parent_army().player
            except Exception:
                player = None
            is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
            es = getattr(self, "event_system", None)
            subs = getattr(es, "subscribers", None) if es is not None else None
            has_sub = bool(isinstance(subs, dict) and subs.get("frenzy_prompt"))
            if is_human and es is not None:
                es.publish(
                    "frenzy_prompt",
                    player=player,
                    unit=target,
                    attacker_unit=attacker_unit,
                    options=list(options),
                    game=self,
                )
                if has_sub:
                    continue
            if "shoot" in options:
                self._execute_frenzy_shooting(target, attacker_unit)
            elif "fight" in options:
                self._execute_frenzy_fight(target, attacker_unit, phase_name=phase_name)

    def _frenzy_has_eligible_shot(self, unit, target_unit) -> bool:
        if unit is None or target_unit is None:
            return False
        try:
            if hasattr(unit, "is_ranged_unit"):
                return bool(unit.is_ranged_unit)
        except Exception:
            pass
        for model in list(getattr(unit, "models", []) or []):
            if not getattr(model, "is_alive", True):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                try:
                    if wargear is not None and wargear.is_ranged():
                        return True
                except Exception:
                    continue
        return False

    def _frenzy_can_fight_target(self, unit, target_unit, *, phase_name: str | None = None) -> bool:
        if unit is None or target_unit is None:
            return False
        if not getattr(unit, "is_alive", lambda: True)():
            return False
        if not bool(getattr(unit, "deployed", True)):
            return False
        if getattr(unit, "is_embarked", False) or getattr(unit, "embarked_in", None) is not None:
            return False
        game_map = getattr(self, "map", None)
        if game_map is None:
            return False
        pname = str(phase_name or "").strip().upper()
        if not pname:
            phase = getattr(self, "phase", None)
            pname = str(getattr(phase, "name", "") or phase or "").strip().upper()
        allow_pile_in = "FIGHT" in pname
        if hasattr(game_map, "is_within_engagement_range") and game_map.is_within_engagement_range(unit, target_unit):
            return True
        if not allow_pile_in:
            return False
        try:
            from ...utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
            for m in list(getattr(unit, "models", []) or []):
                if not getattr(m, "is_alive", True):
                    continue
                for em in list(getattr(target_unit, "models", []) or []):
                    if not getattr(em, "is_alive", True):
                        continue
                    h = float(horizontal_distance_between_bases_2d(m.model_base, em.model_base))
                    v = float(vertical_distance_between_bases(m.model_base, em.model_base))
                    if v > ENGAGEMENT_RANGE_VERTICAL + 1e-6:
                        continue
                    if h <= float(ENGAGEMENT_RANGE_HORIZONTAL) + 3.0 + 1e-6:
                        return True
        except Exception:
            return False
        return False

    def _frenzy_available_actions(self, unit, attacker_unit, *, phase_name: str | None = None) -> list[str]:
        if unit is None or attacker_unit is None:
            return []
        try:
            if not unit.has_frenzy():
                return []
        except Exception:
            return []
        pname = str(phase_name or "").strip().upper()
        if pname and ("SHOOT" not in pname and "FIGHT" not in pname):
            return []
        options: list[str] = []
        if self._frenzy_has_eligible_shot(unit, attacker_unit):
            options.append("shoot")
        if self._frenzy_can_fight_target(unit, attacker_unit, phase_name=pname):
            options.append("fight")
        return options

    def _build_frenzy_shooting_declarations(self, unit, target_unit) -> list[dict]:
        declarations: list[dict] = []
        if unit is None or target_unit is None:
            return declarations
        for model in list(getattr(unit, "models", []) or []):
            if not getattr(model, "is_alive", True):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                try:
                    if not wargear.is_ranged():
                        continue
                except Exception:
                    continue
                profiles = getattr(wargear, "profiles", {}) or {}
                for profile in list(profiles.values()):
                    if profile is None:
                        continue
                    declarations.append(
                        {
                            "weapon_profile": profile,
                            "target_unit": target_unit,
                            "models": [model],
                        }
                    )
        return declarations

    def _execute_frenzy_shooting(self, unit, attacker_unit) -> bool:
        if unit is None or attacker_unit is None:
            return False
        declarations = self._build_frenzy_shooting_declarations(unit, attacker_unit)
        if not declarations:
            return False
        exec_fn = getattr(unit, "execute_shooting_declarations", None)
        if not callable(exec_fn):
            return False
        return bool(exec_fn(declarations, getattr(self, "map", None), out_of_phase=True))

    def resolve_frenzy_melee_attacks(self, unit, target_unit, weapon_declarations) -> None:
        if unit is None or target_unit is None:
            return
        try:
            from ..fight_phase_manager import FightPhaseManager
            attack_summary = FightPhaseManager(self)._resolve_melee_attacks(unit, target_unit, weapon_declarations)
            self._maybe_trigger_daemonic_poisons(
                attacker_unit=unit,
                hits_by_target=attack_summary.get("hits_by_target"),
                hit_models_by_target=attack_summary.get("hit_models_by_target"),
                phase="fight",
            )
            if hasattr(self, "event_system"):
                self.event_system.publish(
                    "fight_attacks_resolved",
                    unit=unit,
                    target_unit=target_unit,
                )
        except Exception:
            return

    def _execute_frenzy_fight(self, unit, attacker_unit, *, phase_name: str | None = None) -> bool:
        if unit is None or attacker_unit is None:
            return False
        if not self._frenzy_can_fight_target(unit, attacker_unit, phase_name=phase_name):
            return False
        try:
            from ..fight_phase_manager import FightPhaseManager
            declarations = FightPhaseManager(self)._auto_select_melee_weapons(unit)
        except Exception:
            declarations = []
        if not declarations:
            return False
        self.resolve_frenzy_melee_attacks(unit, attacker_unit, declarations)
        return True
