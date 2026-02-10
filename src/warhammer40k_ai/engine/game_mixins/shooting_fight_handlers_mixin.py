from __future__ import annotations

from ._shared import *  # noqa: F401,F403


class GameShootingFightHandlersMixin:
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
            if player.has_control():
                candidates = mgr.get_fade_back_candidates(hit_units, self)
                if not candidates:
                    continue
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
            else:
                candidates = mgr.get_fade_back_candidates(hit_units, self)
                if not candidates:
                    continue
                self._queue_battle_focus_reactive_selection(
                    player=player,
                    candidates=list(candidates),
                    manager=mgr,
                    maneuver="fade_back",
                    attacker_unit=attacker_unit,
                    hits_by_unit=dict(hits_map),
                )

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
                if str(getattr(req, "decision_type", "")) != DECISION_MOVE_UNIT:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                kind = str(ctx.get("reactive_move_kind", "") or "")
                if kind not in ("tactical_acumen", "post_shoot_no_charge"):
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
        if not unit_specs:
            return

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

        for spec in unit_specs:
            if bool(spec.get("requires_not_engaged", False)) and engaged:
                continue
            range_roll = str(spec.get("range_roll", "") or "").strip().upper()
            if range_roll == "D6":
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

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_battleshock_specs(model) or []
            if not specs:
                continue
            for spec in specs:
                infantry_only = bool(spec.get("infantry_only", False))
                exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
                candidates: list[Any] = []
                for target_unit, hits in (hits_by_target or {}).items():
                    if target_unit is None:
                        continue
                    if int(hits or 0) <= 0:
                        continue
                    if not _is_enemy_unit(target_unit):
                        continue
                    if infantry_only:
                        is_infantry_fn = getattr(target_unit, "is_infantry", None)
                        if callable(is_infantry_fn):
                            is_infantry = bool(is_infantry_fn())
                        else:
                            is_infantry = bool(getattr(target_unit, "is_infantry", False))
                        if not is_infantry:
                            continue
                    if exclude_mv and _is_monster_or_vehicle(target_unit):
                        continue
                    if not _model_hit_target(model, target_unit):
                        continue
                    candidates.append(target_unit)
                if candidates:
                    triggers.append((model, spec, candidates))

        unit_specs = attacker_unit.unit_post_shoot_battleshock_specs() or []
        for spec in unit_specs:
            infantry_only = bool(spec.get("infantry_only", False))
            exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
            candidates: list[Any] = []
            for target_unit, hits in (hits_by_target or {}).items():
                if target_unit is None:
                    continue
                if int(hits or 0) <= 0:
                    continue
                if not _is_enemy_unit(target_unit):
                    continue
                if infantry_only:
                    is_infantry_fn = getattr(target_unit, "is_infantry", None)
                    if callable(is_infantry_fn):
                        is_infantry = bool(is_infantry_fn())
                    else:
                        is_infantry = bool(getattr(target_unit, "is_infantry", False))
                    if not is_infantry:
                        continue
                if exclude_mv and _is_monster_or_vehicle(target_unit):
                    continue
                candidates.append(target_unit)
            if candidates:
                triggers.append((None, spec, candidates))

        if not triggers:
            return

        from ..decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET

        for model, spec, candidates in triggers:
            if not candidates:
                continue
            ability_name = str(spec.get("source", "") or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
            options = []
            for cand in list(candidates):
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
                    if spec.get("test_modifier_on_kill"):
                        if model is None:
                            if _unit_killed_target(cand):
                                modifier += int(spec.get("test_modifier_on_kill", 0) or 0)
                        else:
                            if _model_killed_target(model, cand):
                                modifier += int(spec.get("test_modifier_on_kill", 0) or 0)
                except Exception:
                    pass
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
        **_kwargs,
    ) -> None:
        attacker_unit = attacker_unit if attacker_unit is not None else unit
        if attacker_unit is None:
            return
        if not self.is_fight_phase():
            return
        attacker_player = attacker_unit.get_parent_army().player
        if attacker_player is None:
            raise RuntimeError("Post-fight Battle-shock requires an attacker player.")
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

        def _model_hit_target(model, candidate) -> bool:
            if not isinstance(hit_models_by_target, dict):
                return True
            hit_models = hit_models_by_target.get(candidate)
            if not hit_models:
                return False
            return model in hit_models

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

        from ..decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET

        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_fight_battleshock_specs(model) or []
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
                    if not _model_hit_target(model, cand):
                        continue
                    candidates.append(cand)
                if not candidates:
                    continue
                ability_name = str(spec.get("source", "") or "Post-fight Battle-shock").strip() or "Post-fight Battle-shock"
                options = []
                for cand in list(candidates):
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

        unit_specs = attacker_unit.unit_post_shoot_pinned_specs() or []
        if not unit_specs:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for spec in unit_specs:
            exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
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

    def _on_unit_shooting_resolved_post_shoot_suppression(
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

        triggers: list[tuple[Any, dict, list[Any]]] = []
        for model in list(attacker_unit.models or []):
            if not getattr(model, "is_alive", False):
                continue
            specs = attacker_unit.model_post_shoot_suppression_specs(model) or []
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

        specs = attacker_unit.unit_post_shoot_no_cover_specs() or []
        if not specs:
            return

        from ..decision_kinds import DECISION_CHOOSE_QUARRY

        for spec in specs:
            weapon_key = str(spec.get("weapon_key", "") or "")
            any_weapon = bool(spec.get("any_weapon", False))
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
            ability_name = str(spec.get("source", "") or "No Cover").strip() or "No Cover"
            duration = str(spec.get("duration", "") or "phase_end").strip().lower()
            expires_phase = "SHOOTING_PHASE"
            expires_timing = "PHASE_END"
            if duration == "owner_next_shooting_start":
                expires_phase = ""
                expires_timing = "OWNER_NEXT_SHOOTING_START"
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
                    "expires_phase": expires_phase,
                    "expires_timing": expires_timing,
                },
            )
            self.request_decision(request)

    def _on_unit_shooting_resolved_post_shoot_ap_bonus(
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
            try:
                ap_bonus = int(spec.get("value", 0) or 0)
            except Exception:
                ap_bonus = 0
            limit_scope = str(spec.get("limit_scope", "") or "").strip().lower()
            exclude_mv = bool(spec.get("exclude_monster_vehicle", False))
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
        try:
            root = attacking_unit.get_attached_unit_root()
        except Exception:
            root = attacking_unit
        if root is None:
            return
        phase = getattr(self, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "")
        trigger_fn = getattr(root, "maybe_trigger_dark_pacts", None)
        if callable(trigger_fn):
            trigger_fn(self, phase_name=phase_name, trigger="shooting")

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

        for entry in sorted(list(entries or []), key=_sort_key):
            model = entry.get("model")
            if model is None or not getattr(model, "is_alive", False):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in pending_models:
                continue
            weapon_name = str(entry.get("weapon_name", "") or "shrieker cannon")
            ability_name = str(entry.get("source", "") or "Cruel Amusement").strip() or "Cruel Amusement"
            options = [
                DecisionOption.create(
                    "Ignores Cover",
                    payload={"choice": "IGNORES_COVER", "summary": "Weapon gains [IGNORES COVER] until end of phase."},
                ),
                DecisionOption.create(
                    "Precision",
                    payload={"choice": "PRECISION", "summary": "Weapon gains [PRECISION] until end of phase."},
                ),
                DecisionOption.create(
                    "Sustained Hits 3",
                    payload={"choice": "SUSTAINED_HITS_3", "summary": "Weapon gains [SUSTAINED HITS 3] until end of phase."},
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

    def _on_unit_shooting_resolved_emperors_children(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
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

    def _on_fight_attacks_resolved_emperors_children(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
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
                if str(ctx.get("ability", "") or "") != "hammer_aflame":
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
            candidates: list[Any] = []
            seen_targets: set[str] = set()
            try:
                enemy_units = list(game_map.get_enemy_units(root) or [])
            except Exception:
                enemy_units = []
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
                    if not game_map.is_within_engagement_range(root, enemy_root):
                        continue
                except Exception:
                    continue
                candidates.append(enemy_root)
            if not candidates:
                continue
            for spec in specs:
                ability_name = str(spec.get("source", "") or "Hammer Aflame (Psychic)").strip() or "Hammer Aflame (Psychic)"
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
                        "ability": "hammer_aflame",
                        "ability_name": ability_name,
                        "phase": "Fight phase",
                        "source_unit_id": get_entity_id(root),
                        "unit_id": get_entity_id(root),
                        "model_id": model_id,
                    },
                )
                self.request_decision(req)
                if model_id:
                    pending_model_ids.add(model_id)
                break

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

        snapshot = list(getattr(self, "_guns_blazing_shooting_targets", {}).get(attacking_unit, []) or [])
        seen_ids = {str(get_entity_id(u) or "") for u in snapshot if u is not None}

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
                if not bool(getattr(root, "has_guns_blazing", lambda: False)()):
                    continue
                if not bool(getattr(root, "can_use_guns_blazing", lambda **_k: False)(game=self, game_map=game_map)):
                    continue
                eligible = False
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
                    try:
                        if not target_root.has_any_keyword("HERETIC ASTARTES"):
                            continue
                    except Exception:
                        continue
                    if unit_within_range_of_unit(root, target_root, 3.0, use_attached_aggregate=True):
                        eligible = True
                        break
                if not eligible:
                    continue
                snapshot.append(root)
                seen_ids.add(rid)

        if not snapshot:
            return
        if not hasattr(self, "_guns_blazing_shooting_targets") or not isinstance(
            getattr(self, "_guns_blazing_shooting_targets", None), dict
        ):
            self._guns_blazing_shooting_targets = {}
        self._guns_blazing_shooting_targets[attacking_unit] = list(snapshot)

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

        for source in list(targets):
            if source is None:
                continue
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
            if not bool(getattr(root, "can_use_guns_blazing", lambda **_k: False)(game=self, game_map=game_map, enemy_unit=attacker_root)):
                continue
            if not self._setup_reactive_can_shoot_target(root, attacker_root):
                continue
            player = getattr(root.get_parent_army(), "player", None)
            if player is None:
                continue
            request = self._queue_setup_reactive_shooting_decision(
                player=player,
                unit=root,
                target_unit=attacker_root,
                source="Guns Blazing",
            )
            if request is None:
                continue
            request.context["guns_blazing_flow"] = True
            request.context["guns_blazing_source"] = "Guns Blazing"
            request.context["guns_blazing_enemy_unit_id"] = str(get_entity_id(attacker_root) or "")
            request.context["guns_blazing_unit_id"] = source_id
            pending_for_source.add(source_id)

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
            count = self._alive_model_count(root)
            if count <= 0:
                continue
            snapshot[root] = count
        if snapshot:
            self._horde_move_shooting_snapshot[attacking_unit] = snapshot

    def _on_unit_shooting_resolved_horde_move(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        snapshot = self._horde_move_shooting_snapshot.pop(attacker_unit, {})
        if not snapshot:
            return
        for target, before in snapshot.items():
            if target is None:
                continue
            after = self._alive_model_count(target)
            if after >= int(before or 0):
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
            msg = (
                "Horde Move: Move D6\" as close as possible to the closest non-AIRCRAFT enemy unit.\n"
                "This unit cannot make a Horde move while Battle-shocked."
            )
            self._queue_reactive_move_confirmation(
                player=player,
                unit=target,
                kind="horde_move",
                movement_type="horde_move",
                source="Horde Move",
                message=msg,
                attacker_unit=attacker_unit,
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

    def _frenzy_can_fight_target(self, unit, target_unit) -> bool:
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
        if self._frenzy_can_fight_target(unit, attacker_unit):
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
        if not self._frenzy_can_fight_target(unit, attacker_unit):
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
