from __future__ import annotations

from ._shared import *  # noqa: F401,F403


class GameReactiveDecisionsMixin:
    def queue_phoenix_gem_return(
        self,
        *,
        unit=None,
        model=None,
        position=None,
        phase_name=None,
        game_map=None,
        spec=None,
        reattach_bodyguard_unit=None,
        was_attached_when_destroyed: bool = False,
    ) -> None:
        if unit is None or model is None:
            return
        payload = {
            "unit": unit,
            "model": model,
            "position": position,
            "phase_name": phase_name,
            "game_map": game_map,
            "spec": spec or {},
            "reattach_bodyguard_unit": reattach_bodyguard_unit,
            "was_attached_when_destroyed": bool(was_attached_when_destroyed),
        }
        pending = list(getattr(self, "_phoenix_gem_pending", []) or [])
        pending.append(payload)
        self._phoenix_gem_pending = pending

    def _maybe_queue_spirit_mark(self, unit=None, action: str | None = None) -> None:
        if unit is None:
            return
        if not self.is_movement_phase():
            return
        action_key = str(action or "").strip().lower()
        if action_key not in ("move", "advance", "fall_back"):
            return
        if not self._entity_is_alive(unit, default=False):
            return
        if not bool(getattr(unit, "deployed", True)):
            return
        is_in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            return
        if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
            return

        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        owner = getattr(parent_army, "player", None)
        if owner is None or owner is not self.get_current_player():
            return

        get_army = getattr(owner, "get_army", None)
        army = get_army() if callable(get_army) else getattr(owner, "army", None)
        if army is None:
            return

        get_spirit_mark_specs = getattr(unit, "model_spirit_mark_specs", None)
        if not callable(get_spirit_mark_specs):
            return

        for model in list(getattr(unit, "models", []) or []):
            if not self._entity_is_alive(model, default=True):
                continue
            specs = list(get_spirit_mark_specs(model) or [])
            if not specs:
                continue
            for spec in list(specs or []):
                if not isinstance(spec, dict):
                    continue
                keyword = str(spec.get("keyword", "") or "").strip()
                rng = self._coerce_int(spec.get("range", 0), 0)
                if rng <= 0:
                    continue
                candidates = []
                seen = set()
                for cand in list(getattr(army, "units", []) or []):
                    if cand is None:
                        continue
                    root = self._attached_unit_root_or_self(cand)
                    if root is None:
                        continue
                    rid = str(get_entity_id(root) or "")
                    if not rid or rid in seen:
                        continue
                    seen.add(rid)
                    if not self._entity_is_alive(root, default=False):
                        continue
                    if not bool(getattr(root, "deployed", True)):
                        continue
                    cand_is_in_reserves = getattr(root, "is_in_reserves", None)
                    if callable(cand_is_in_reserves) and bool(cand_is_in_reserves()):
                        continue
                    if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                        continue
                    if not self._unit_has_keyword_safe(root, keyword):
                        continue
                    if self._unit_has_keyword_safe(root, "TITANIC"):
                        continue
                    if not self._unit_within_range_of_model(model, root, range_value=float(rng)):
                        continue
                    candidates.append(root)
                if not candidates:
                    continue
                self._queue_spirit_mark_friendly_selection(
                    player=owner,
                    source_unit=unit,
                    model=model,
                    candidates=candidates,
                    spec=spec,
                )

    def _player_has_optional_decision_hook(self, player, key: str) -> bool:
        if player is None:
            return False
        k = str(key or "").strip().upper()
        if not k:
            return False
        overrides = getattr(player, "_next_optional_decisions", None)
        if isinstance(overrides, dict) and k in overrides:
            return True
        return callable(getattr(player, "decision_hook", None))

    def _resolve_player_by_id(self, player_id: str | None):
        if not player_id:
            return None
        for p in list(self.players or []):
            pid = maybe_entity_id(p)
            if pid and str(pid) == str(player_id):
                return p
        return None

    def _resolve_unit_by_id(self, unit_id: str | None):
        if not unit_id:
            return None
        registry = getattr(self, "entity_registry", None)
        if registry is not None:
            unit = registry.get(str(unit_id), kind="unit")
            if unit is not None:
                return unit
        for p in list(self.players or []):
            army = p.get_army()
            if army is None:
                continue
            for u in list(getattr(army, "units", []) or []):
                uid = maybe_entity_id(u)
                if uid and str(uid) == str(unit_id):
                    return u
        return None

    def _resolve_model_by_id(self, model_id: str | None):
        if not model_id:
            return None
        registry = getattr(self, "entity_registry", None)
        if registry is not None:
            model = registry.get(str(model_id), kind="model")
            if model is not None:
                return model
        for p in list(self.players or []):
            army = p.get_army()
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                for model in list(getattr(unit, "models", []) or []):
                    mid = maybe_entity_id(model)
                    if mid and str(mid) == str(model_id):
                        return model
        return None

    def _option_id_for_payload(self, request: DecisionRequest, key: str, value: object) -> str | None:
        if request is None:
            return None
        for opt in list(getattr(request, "options", []) or []):
            payload = getattr(opt, "payload", {}) or {}
            if payload.get(key) == value:
                return opt.option_id
        return None

    def _decision_option_payload(self, request: DecisionRequest | None, result: DecisionResult | None) -> dict:
        if request is None or result is None:
            return {}
        for opt in list(getattr(request, "options", []) or []):
            if getattr(opt, "option_id", None) == getattr(result, "option_id", None):
                return dict(getattr(opt, "payload", {}) or {})
        return {}

    def _decision_is_skip(self, request: DecisionRequest | None, result: DecisionResult | None) -> bool:
        if result is None:
            return False
        payload = dict(getattr(result, "payload", {}) or {})
        if bool(payload.get("skipped", False)):
            return True
        if str(payload.get("action", "") or "") == "skip":
            return True
        opt_payload = self._decision_option_payload(request, result)
        if bool(opt_payload.get("skip", False)):
            return True
        return str(opt_payload.get("action", "") or "") == "skip"

    def _reactive_move_context(
        self,
        *,
        kind: str,
        unit_id: str,
        movement_type: str,
        source: str,
        moving_unit_id: str | None = None,
        attacker_unit_id: str | None = None,
        range_value: int | None = None,
        allow_engagement_range: bool | None = None,
    ) -> dict:
        ctx = {
            "reactive_move_kind": str(kind or "").strip(),
            "reactive_move_unit_id": unit_id,
            "reactive_move_source": str(source or "").strip() or "Reactive Move",
            "reactive_move_movement_type": str(movement_type or "").strip(),
        }
        if moving_unit_id:
            ctx["reactive_move_moving_unit_id"] = moving_unit_id
        if attacker_unit_id:
            ctx["reactive_move_attacker_unit_id"] = attacker_unit_id
        if range_value is not None:
            ctx["reactive_move_range"] = int(range_value)
        if allow_engagement_range is not None:
            ctx["reactive_move_allow_engagement_range"] = bool(allow_engagement_range)
        return ctx

    def _queue_optional_ability_confirmation(
        self,
        *,
        player,
        ability_key: str,
        ability_name: str,
        message: str | None = None,
        context: dict | None = None,
        payload: dict | None = None,
        instance_key: str | None = None,
    ) -> DecisionRequest | None:
        if player is None:
            return None
        key = str(ability_key or "").strip().lower()
        if not key:
            return None
        instance = str(instance_key or "").strip().lower()
        existing = None
        queue = getattr(self, "decision_queue", None)
        if queue is not None:
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                req_key = str(ctx.get("ability", "") or ctx.get("ability_key", "") or "").strip().lower()
                if req_key != key:
                    continue
                if instance:
                    req_instance = str(ctx.get("ability_instance", "") or "").strip().lower()
                    if req_instance != instance:
                        continue
                if getattr(req, "player_id", None) == getattr(player, "id", None):
                    existing = req
                    break
        if existing is not None:
            return existing
        ctx = dict(context or {})
        ctx["ability"] = key
        ctx["ability_name"] = str(ability_name or "").strip() or key.replace("_", " ").title()
        if message:
            ctx["message"] = message
        if instance:
            ctx["ability_instance"] = instance
        payload = dict(payload or {})
        options = [
            DecisionOption.create("Use", payload=dict(payload, choice=True)),
            DecisionOption.create("Skip", payload=dict(payload, choice=False)),
        ]
        request = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            ctx["ability_name"],
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _unit_on_battlefield_for_reposition(self, unit) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not is_alive():
            return False
        if not getattr(unit, "deployed", True):
            return False
        if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
            return False
        if bool(getattr(unit, "embarked_in", None)) or bool(getattr(unit, "is_embarked", False)):
            return False
        is_in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(is_in_reserves) and is_in_reserves():
            return False
        return True

    def _opponent_turn_destroyed_reposition_used(self, unit, *, turn_owner_id: str | None) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        used_turn = sr.get("opponent_turn_destroyed_reposition_turn")
        if used_turn is None:
            return False
        try:
            if int(used_turn) != int(turn):
                return False
        except Exception:
            return False
        owner = str(sr.get("opponent_turn_destroyed_reposition_turn_owner", "") or "")
        if turn_owner_id:
            return owner == str(turn_owner_id)
        return bool(owner)

    def _mark_opponent_turn_destroyed_reposition_used(self, unit, *, turn_owner_id: str | None) -> None:
        if unit is None:
            return
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        try:
            sr["opponent_turn_destroyed_reposition_turn"] = int(getattr(self, "turn", 0) or 0)
        except Exception:
            sr["opponent_turn_destroyed_reposition_turn"] = 0
        if turn_owner_id:
            sr["opponent_turn_destroyed_reposition_turn_owner"] = str(turn_owner_id)
        unit.special_rules = sr

    def _find_closest_valid_reposition_position(
        self,
        unit,
        anchor_pos,
        *,
        game_map: Map | None = None,
        radius_step: float = 0.5,
        angle_step: int = 15,
    ) -> tuple | None:
        if unit is None or anchor_pos is None:
            return None
        if game_map is None:
            game_map = getattr(self, "map", None)
        if game_map is None:
            return None
        try:
            ax = float(anchor_pos[0])
            ay = float(anchor_pos[1])
            az = float(anchor_pos[2]) if len(anchor_pos) > 2 else 0.0
        except (TypeError, ValueError, IndexError):
            return None

        try:
            models = [m for m in list(getattr(unit, "models", []) or []) if getattr(m, "is_alive", True)]
        except Exception:
            models = []
        if len(models) != 1:
            return None
        model = models[0]
        facing = float(getattr(getattr(model, "model_base", None), "facing", 0.0) or 0.0)

        collision_fn = getattr(game_map, "check_collision_with_obstacles", None)
        if not callable(collision_fn):
            collision_fn = getattr(game_map, "check_collision_with_terrain", None)

        from ...battlefield.map import validate_ruins_placement
        from ...utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases

        def _position_valid(x: float, y: float, z: float) -> bool:
            if hasattr(game_map, "is_within_boundary") and not game_map.is_within_boundary(model, destination=(x, y)):
                return False
            if callable(collision_fn) and collision_fn(model, destination=(x, y)):
                return False
            ruins_validation = validate_ruins_placement(unit, (x, y, z), game_map.terrain_features, moving_model=model)
            if not ruins_validation.get("valid", False):
                return False
            if hasattr(game_map, "check_collision_with_other_friendly_units"):
                if game_map.check_collision_with_other_friendly_units(model, destination=(x, y)):
                    return False
            if hasattr(game_map, "check_collision_with_other_enemy_units"):
                if game_map.check_collision_with_other_enemy_units(model, destination=(x, y)):
                    return False
            test_base = model.model_base
            if hasattr(unit, "_create_potential_base"):
                test_base = unit._create_potential_base(x, y, z, facing, model=model)
            for enemy in list(getattr(game_map, "get_enemy_units", lambda _u: [])(unit) or []):
                if hasattr(enemy, "is_alive") and callable(enemy.is_alive) and not enemy.is_alive():
                    continue
                if not getattr(enemy, "deployed", True):
                    continue
                try:
                    enemy_models = list(enemy.get_models_for_collision() or [])
                except Exception:
                    enemy_models = list(getattr(enemy, "models", []) or [])
                for em in enemy_models:
                    if not getattr(em, "is_alive", True):
                        continue
                    horiz = float(horizontal_distance_between_bases_2d(test_base, em.model_base))
                    vert = float(vertical_distance_between_bases(test_base, em.model_base))
                    if horiz <= ENGAGEMENT_RANGE_HORIZONTAL and vert <= ENGAGEMENT_RANGE_VERTICAL:
                        return False
            return True

        max_radius = float(math.hypot(float(game_map.width), float(game_map.height)))
        if max_radius <= 0:
            return None
        step = max(0.1, float(radius_step))
        deg_step = max(5, int(angle_step))

        best = None
        best_dist = None
        radius = 0.0
        while radius <= max_radius + 1e-6:
            if radius <= 1e-6:
                angles = (0,)
            else:
                angles = range(0, 360, deg_step)
            for deg in angles:
                ang = math.radians(float(deg))
                x = ax + math.cos(ang) * radius
                y = ay + math.sin(ang) * radius
                height_fn = getattr(game_map, "get_height_at_point", None)
                if callable(height_fn):
                    height = height_fn(x, y)
                    z = float(height) if height is not None else float(az)
                else:
                    z = float(az)
                if not _position_valid(x, y, z):
                    continue
                dist = float(get_dist(x - ax, y - ay, z - az))
                if best_dist is None or dist < best_dist - 1e-6:
                    best = (float(x), float(y), float(z), float(facing))
                    best_dist = dist
            if best_dist is not None and radius > best_dist + 1e-6:
                break
            radius += step
        return best

    def _queue_movement_phase_normal_move_weapon_attacks_bonus(
        self,
        *,
        player,
        unit,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        phase = getattr(self, "phase", None)
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname and pname != "MOVEMENT_PHASE":
            return None
        if player is not self.get_current_player():
            return None
        if not getattr(unit, "is_alive", lambda: False)():
            return None
        if not getattr(unit, "deployed", True):
            return None
        try:
            if unit.is_in_reserves() or unit.is_embarked:
                return None
        except Exception:
            pass

        try:
            models = list(getattr(unit, "models", []) or [])
        except Exception:
            models = []
        if not models:
            return None

        for m in models:
            if not getattr(m, "is_alive", True):
                continue
            try:
                specs = list(unit.model_movement_phase_normal_move_weapon_attacks_bonus_specs(m) or [])
            except Exception:
                specs = []
            if not specs:
                continue
            for spec in specs:
                key = str(spec.get("key") or "movement_phase_normal_move_bonus").strip().lower()
                if not key:
                    key = "movement_phase_normal_move_bonus"
                try:
                    army = unit.get_parent_army()
                except Exception:
                    army = None
                ia_mgr = getattr(army, "imperial_agents_detachments", None) if army is not None else None
                grant_fn = getattr(ia_mgr, "apply_extremis_sanction_extra_uses", None) if ia_mgr is not None else None
                if callable(grant_fn):
                    grant_fn(unit)
                if getattr(m, "has_used_once_per_battle", lambda _k: False)(key):
                    continue
                unit_id = maybe_entity_id(unit)
                model_id = maybe_entity_id(m)
                if not unit_id or not model_id:
                    continue
                ability_name = str(spec.get("source", "") or "Movement phase normal move boost").strip()
                ctx = {
                    "ability_name": ability_name,
                    "phase": "Movement phase",
                    "unit": getattr(unit, "name", "") or "",
                    "model": getattr(m, "name", "") or "",
                    "unit_id": unit_id,
                    "model_id": model_id,
                    "move_bonus_dice": str(spec.get("move_bonus_dice", "") or ""),
                    "move_bonus_flat": int(spec.get("move_bonus_flat", 0) or 0),
                    "attacks_bonus": int(spec.get("attacks_bonus", 0) or 0),
                    "weapon_name": str(spec.get("weapon_name", "") or ""),
                    "buff_key": key,
                }
                message = (
                    f"Activate {ability_name} for {getattr(m, 'name', 'Model')} "
                    f"({getattr(unit, 'name', 'Unit')}) before Normal move?"
                )
                return self._queue_optional_ability_confirmation(
                    player=player,
                    ability_key="movement_phase_move_weapon_bonus",
                    ability_name=ability_name,
                    message=message,
                    context=ctx,
                    payload={
                        "unit_id": unit_id,
                        "model_id": model_id,
                        "move_bonus_dice": ctx["move_bonus_dice"],
                        "move_bonus_flat": ctx["move_bonus_flat"],
                        "attacks_bonus": ctx["attacks_bonus"],
                        "weapon_name": ctx["weapon_name"],
                        "buff_key": key,
                    },
                    instance_key=f"{model_id}:{key}",
                )
        return None

    def _queue_movement_phase_flickerjump(
        self,
        *,
        player,
        unit,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        phase = getattr(self, "phase", None)
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname and pname != "MOVEMENT_PHASE":
            return None
        if player is not self.get_current_player():
            return None
        if not getattr(unit, "is_alive", lambda: False)():
            return None
        if not getattr(unit, "deployed", True):
            return None
        try:
            if unit.is_in_reserves() or unit.is_embarked:
                return None
        except Exception:
            pass

        try:
            specs = list(unit.unit_movement_phase_normal_move_speed_mortal_wounds_specs() or [])
        except Exception:
            specs = []
        if not specs:
            return None

        for spec in specs:
            move_value = int(spec.get("move_value", 0) or 0)
            if move_value <= 0:
                continue
            unit_id = maybe_entity_id(unit)
            if not unit_id:
                continue
            ability_name = str(spec.get("source", "") or "Flickerjump").strip()
            ctx = {
                "ability_name": ability_name,
                "phase": "Movement phase",
                "unit": getattr(unit, "name", "") or "",
                "unit_id": unit_id,
                "move_value": int(move_value),
            }
            message = (
                f"Activate {ability_name} for {getattr(unit, 'name', 'Unit')} before Normal move?"
            )
            return self._queue_optional_ability_confirmation(
                player=player,
                ability_key="flickerjump",
                ability_name=ability_name,
                message=message,
                context=ctx,
                payload={
                    "unit_id": unit_id,
                    "move_value": int(move_value),
                },
                instance_key=f"{unit_id}:flickerjump",
            )
        return None

    def _queue_movement_phase_visible_bonus(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
        bonus_kind: str,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        kind_key = str(bonus_kind or "").strip().lower()
        if kind_key not in ("hit", "wound"):
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        ability_key = f"movement_phase_visible_{kind_key}_bonus"
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != ability_key:
                    continue
                if str(ctx.get("model_id", "")) == str(model_id):
                    return None

        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        limit_once = bool(spec.get("limit_once_per_turn")) if isinstance(spec, dict) else False
        filtered = []
        for cand in sorted(list(candidates), key=_cand_sort_key):
            if limit_once:
                sr = getattr(cand, "special_rules", None)
                if isinstance(sr, dict) and sr.get(f"{ability_key}_active"):
                    if str(sr.get(f"{ability_key}_owner", "") or "") == owner_id and int(sr.get(f"{ability_key}_turn", 0) or 0) == turn:
                        continue
            filtered.append(cand)

        options = []
        for cand in filtered:
            options.append(
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(cand)},
                )
            )
        if not options:
            return None
        ability_name = str(spec.get("source", "") or f"Movement phase {kind_key} bonus").strip() or f"Movement phase {kind_key} bonus"
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        keyword = str(spec.get("keyword", "") or "").strip()
        try:
            bonus = int(spec.get("bonus", 0) or 0)
        except Exception:
            bonus = 0
        ctx = {
            "ability": ability_key,
            "ability_name": ability_name,
            "phase": "Movement phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_value),
            "keyword": keyword,
            "bonus": int(bonus),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_movement_phase_visible_wound_bonus(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        return self._queue_movement_phase_visible_bonus(
            player=player,
            source_unit=source_unit,
            model=model,
            candidates=candidates,
            spec=spec,
            bonus_kind="wound",
        )

    def _queue_movement_phase_visible_hit_bonus(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        return self._queue_movement_phase_visible_bonus(
            player=player,
            source_unit=source_unit,
            model=model,
            candidates=candidates,
            spec=spec,
            bonus_kind="hit",
        )

    def _queue_fight_phase_target_attack_bonus(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        options = []
        for cand in candidates:
            options.append(
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(cand)},
                )
            )
        if not options:
            return None
        ability_name = str(spec.get("source", "") or "Fight phase target bonus").strip() or "Fight phase target bonus"
        ctx = {
            "ability": "fight_phase_target_attack_bonus",
            "ability_name": ability_name,
            "phase": "Fight phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(spec.get("range", 0) or 0),
            "keyword": str(spec.get("keyword", "") or "").strip(),
            "attack_type": str(spec.get("attack_type", "") or "any").strip().lower() or "any",
            "strength_bonus": int(spec.get("strength_bonus", 0) or 0),
            "ap_bonus": int(spec.get("ap_bonus", 0) or 0),
            "damage_bonus": int(spec.get("damage_bonus", 0) or 0),
            "wound_bonus": int(spec.get("wound_bonus", 0) or 0),
            "enemy_melee_wound_penalty": int(spec.get("enemy_melee_wound_penalty", 0) or 0),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_movement_phase_end_misfortune(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "misfortune":
                    continue
                if str(ctx.get("model_id", "")) == str(model_id):
                    return None

        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        limit_once = bool(spec.get("limit_once_per_turn")) if isinstance(spec, dict) else False
        filtered = []
        for cand in sorted(list(candidates), key=_cand_sort_key):
            if limit_once:
                sr = getattr(cand, "special_rules", None)
                if isinstance(sr, dict):
                    if str(sr.get("misfortune_selected_owner", "") or "") == owner_id and int(sr.get("misfortune_selected_turn", 0) or 0) == int(turn or 0):
                        continue
            filtered.append(cand)
        if not filtered:
            return None

        options = [
            DecisionOption.create(
                str(getattr(cand, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(cand)},
            )
            for cand in filtered
        ]
        if not options:
            return None
        ability_name = str(spec.get("source", "") or "Misfortune").strip() or "Misfortune"
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        try:
            penalty = int(spec.get("penalty", -1) or -1)
        except Exception:
            penalty = -1
        ctx = {
            "ability": "misfortune",
            "ability_name": ability_name,
            "phase": "Movement phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_value),
            "penalty": int(penalty),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_movement_phase_end_nurgles_rot(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "nurgles_rot":
                    continue
                if str(ctx.get("model_id", "")) == str(model_id):
                    return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = [
            DecisionOption.create(
                str(getattr(cand, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(cand)},
            )
            for cand in sorted(list(candidates), key=_cand_sort_key)
        ]
        options.append(DecisionOption.create("None", payload={"action": "skip"}))
        if not options:
            return None
        ability_name = str(spec.get("source", "") or "Nurgle's Rot").strip() or "Nurgle's Rot"
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        try:
            penalty = int(spec.get("penalty", -1) or -1)
        except Exception:
            penalty = -1
        ctx = {
            "ability": "nurgles_rot",
            "ability_name": ability_name,
            "phase": "Movement phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_value),
            "penalty": int(penalty),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_symphony_of_pain(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "symphony_of_pain":
                    continue
                if str(ctx.get("model_id", "")) == str(model_id):
                    return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = [DecisionOption.create("None", payload={"action": "skip"})]
        for cand in sorted(list(candidates), key=_cand_sort_key):
            options.append(
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(cand)},
                )
            )
        if not options:
            return None
        ability_name = str(spec.get("source", "") or "Symphony of Pain").strip() or "Symphony of Pain"
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        keywords = list(spec.get("keywords", []) or [])
        ctx = {
            "ability": "symphony_of_pain",
            "ability_name": ability_name,
            "phase": "Movement phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_value),
            "keywords": keywords,
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_start_shooting_phase_visible_battleshock(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..decision_kinds import DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None

        ability_name = str(spec.get("source", "") or "Start of Shooting phase Battle-shock").strip() or "Start of Shooting phase Battle-shock"
        ability_key = str(ability_name).strip().lower() or "start_shooting_phase_battleshock"
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("model_id", "")) != str(model_id):
                    continue
                if str(ctx.get("ability_key", "") or "") != ability_key:
                    continue
                return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = [
            DecisionOption.create(
                str(getattr(cand, "name", "Unit") or "Unit"),
                payload={"unit_id": get_entity_id(cand)},
            )
            for cand in sorted(list(candidates), key=_cand_sort_key)
        ]
        if not options:
            return None
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        use_leadership_test = bool(spec.get("use_leadership_test", False))
        try:
            leadership_test_modifier_if_battle_shocked = int(
                spec.get("leadership_test_modifier_if_battle_shocked", 0) or 0
            )
        except Exception:
            leadership_test_modifier_if_battle_shocked = 0
        try:
            fail_mortal_wounds = int(spec.get("fail_mortal_wounds", 0) or 0)
        except Exception:
            fail_mortal_wounds = 0
        ctx = {
            "ability": "start_shooting_phase_visible_battleshock",
            "ability_name": ability_name,
            "ability_key": ability_key,
            "phase": "Shooting phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_value),
            "use_leadership_test": bool(use_leadership_test),
            "leadership_test_modifier_if_battle_shocked": int(leadership_test_modifier_if_battle_shocked),
            "fail_mortal_wounds": int(fail_mortal_wounds),
        }
        test_label = "Leadership test" if use_leadership_test else "Battle-shock test"
        request = DecisionRequest.create(
            DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET,
            f"{ability_name}: select a unit to take a {test_label}.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_start_shooting_phase_visible_hit_bonus(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None

        ability_name = str(spec.get("source", "") or "Marked by Fate").strip() or "Marked by Fate"
        ability_key = str(ability_name).strip().lower() or "start_shooting_phase_visible_hit_bonus"
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "start_shooting_phase_visible_hit_bonus":
                    continue
                if str(ctx.get("model_id", "")) != str(model_id):
                    continue
                if str(ctx.get("ability_key", "") or "") != ability_key:
                    continue
                return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = [
            DecisionOption.create(
                str(getattr(cand, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(cand)},
            )
            for cand in sorted(list(candidates or []), key=_cand_sort_key)
            if cand is not None and get_entity_id(cand)
        ]
        if not options:
            return None
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        try:
            bonus = int(spec.get("bonus", 0) or 0)
        except Exception:
            bonus = 0
        ctx = {
            "ability": "start_shooting_phase_visible_hit_bonus",
            "ability_name": ability_name,
            "ability_key": ability_key,
            "phase": "Shooting phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_value),
            "hit_bonus": int(bonus),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a visible enemy unit.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_maggot_maws(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "maggot_maws":
                    continue
                if str(ctx.get("model_id", "")) == str(model_id):
                    return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = [
            DecisionOption.create(
                str(getattr(cand, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(cand)},
            )
            for cand in sorted(list(candidates), key=_cand_sort_key)
        ]
        if not options:
            return None
        ability_name = str(spec.get("source", "") or "Maggot Maws").strip() or "Maggot Maws"
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        ctx = {
            "ability": "maggot_maws",
            "ability_name": ability_name,
            "phase": "Shooting phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_value),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_start_any_phase_battleshock_clear(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
        phase_label: str,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..decision_kinds import DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None

        ability_name = str(spec.get("source", "") or "Start of phase Battle-shock clear").strip() or "Start of phase Battle-shock clear"
        ability_key = str(spec.get("ability_key", "") or ability_name).strip().lower()
        if not ability_key:
            ability_key = "start_any_phase_clear_battleshock"
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("unit_id", "")) != str(unit_id):
                    continue
                if str(ctx.get("ability_key", "") or "") != ability_key:
                    continue
                return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = [DecisionOption.create("None", payload={"action": "skip"})]
        options.extend(
            [
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"unit_id": get_entity_id(cand)},
                )
                for cand in sorted(list(candidates), key=_cand_sort_key)
            ]
        )
        if len(options) <= 1:
            return None
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        ctx = {
            "ability": "start_any_phase_clear_battleshock",
            "ability_name": ability_name,
            "ability_key": ability_key,
            "phase": str(phase_label or "").strip() or "Phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_value),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET,
            f"{ability_name}: select a Battle-shocked unit to rally (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_cankerblight_trigger(self, *, unit=None, passed: bool = False, shadow_ctx=None, game=None) -> bool:
        if unit is None or passed:
            return False
        try:
            if unit.has_any_keyword("MONSTER") or unit.has_any_keyword("VEHICLE"):
                return False
        except Exception:
            pass
        try:
            unit_army = unit.get_parent_army()
        except Exception:
            unit_army = getattr(unit, "parent_army", None)
        if unit_army is None:
            return False
        game = game or self
        target_id = ""
        try:
            target_id = str(get_entity_id(unit) or "")
        except Exception:
            target_id = str(getattr(unit, "_id", "") or "")
        if not target_id:
            return False
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        pending = sr.get("cankerblight_pending")
        if isinstance(pending, dict):
            try:
                pending_turn = int(pending.get("turn", 0) or 0)
            except Exception:
                pending_turn = 0
            if pending_turn == int(getattr(game, "turn", 0) or 0):
                return True
            sr.pop("cankerblight_pending", None)
            unit.special_rules = sr

        sources = []
        players = list(getattr(game, "players", []) or [])
        for player in players:
            if player is None:
                continue
            try:
                army = player.get_army()
            except Exception:
                army = getattr(player, "army", None)
            if army is None or army is unit_army:
                continue
            for source_unit in list(getattr(army, "units", []) or []):
                if source_unit is None:
                    continue
                if not getattr(source_unit, "is_alive", lambda: False)():
                    continue
                if not getattr(source_unit, "deployed", True):
                    continue
                try:
                    if source_unit.is_in_reserves() or source_unit.is_embarked:
                        continue
                except Exception:
                    pass
                source_rules = getattr(source_unit, "special_rules", None)
                if not isinstance(source_rules, dict) or not source_rules.get("enhancement_cankerblight"):
                    continue
                bearer_id = source_rules.get("enhancement_bearer_model_id")
                if not bearer_id:
                    continue
                try:
                    models = list(source_unit.get_attached_unit_models() or [])
                except Exception:
                    models = list(getattr(source_unit, "models", []) or [])
                bearer_model = None
                for model in models:
                    if str(getattr(model, "_id", "") or "") != str(bearer_id):
                        continue
                    if not getattr(model, "is_alive", True):
                        continue
                    bearer_model = model
                    break
                if bearer_model is None:
                    continue
                if unit not in self._enemy_candidates_within_range_of_model(
                    model=bearer_model,
                    enemy_roots=[unit],
                    range_value=6.0,
                ):
                    continue
                sources.append((player, source_unit, bearer_model))

        if not sources:
            return False

        def _source_sort_key(entry):
            try:
                src_id = str(get_entity_id(entry[1]) or "")
            except Exception:
                src_id = str(getattr(entry[1], "_id", "") or "")
            try:
                mdl_id = str(get_entity_id(entry[2]) or "")
            except Exception:
                mdl_id = str(getattr(entry[2], "_id", "") or "")
            return (src_id, mdl_id)

        sources.sort(key=_source_sort_key)
        owner_player, source_unit, bearer_model = sources[0]
        if owner_player is None:
            return False

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "cankerblight":
                    continue
                if str(ctx.get("target_unit_id", "")) == str(target_id):
                    return True

        sr["cankerblight_pending"] = {
            "owner_id": str(getattr(owner_player, "id", "") or ""),
            "source_unit_id": str(get_entity_id(source_unit) or ""),
            "source_model_id": str(get_entity_id(bearer_model) or ""),
            "turn": int(getattr(game, "turn", 0) or 0),
            "apply_terror_if_skipped": bool(getattr(shadow_ctx, "terror_active", False)),
            "ability_name": "Cankerblight",
        }
        unit.special_rules = sr

        options = [
            DecisionOption.create("None", payload={"action": "skip"}),
            DecisionOption.create(
                str(getattr(unit, "name", "Unit") or "Unit"),
                payload={"target_unit_id": target_id},
            ),
        ]
        ctx = {
            "ability": "cankerblight",
            "ability_name": "Cankerblight",
            "phase": "Battle-shock",
            "target_unit_id": target_id,
            "source_unit_id": str(get_entity_id(source_unit) or ""),
            "source_model_id": str(get_entity_id(bearer_model) or ""),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Cankerblight: select a unit to destroy a model.",
            player_id=getattr(owner_player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return True

    def _queue_fear_made_manifest_trigger(self, *, unit=None, passed: bool = False, game=None) -> bool:
        if unit is None or passed:
            return False
        try:
            if unit.has_any_keyword("MONSTER") or unit.has_any_keyword("VEHICLE"):
                return False
        except Exception:
            pass
        try:
            unit_army = unit.get_parent_army()
        except Exception:
            unit_army = getattr(unit, "parent_army", None)
        if unit_army is None:
            return False
        game = game or self
        target_id = ""
        try:
            target_id = str(get_entity_id(unit) or "")
        except Exception:
            target_id = str(getattr(unit, "_id", "") or "")
        if not target_id:
            return False

        target_sr = getattr(unit, "special_rules", None)
        if not isinstance(target_sr, dict):
            target_sr = {}
        pending = target_sr.get("fear_made_manifest_pending")
        if isinstance(pending, dict):
            try:
                pending_turn = int(pending.get("turn", 0) or 0)
            except Exception:
                pending_turn = 0
            if pending_turn == int(getattr(game, "turn", 0) or 0):
                return True
            target_sr.pop("fear_made_manifest_pending", None)
            unit.special_rules = target_sr

        sources = []
        seen_roots: set[str] = set()
        find_member = getattr(self, "_attached_member_with_enhancement_flag", None)
        players = list(getattr(game, "players", []) or [])
        for player in players:
            if player is None:
                continue
            try:
                army = player.get_army()
            except Exception:
                army = getattr(player, "army", None)
            if army is None or army is unit_army:
                continue
            for source_unit in list(getattr(army, "units", []) or []):
                if source_unit is None:
                    continue
                try:
                    source_root = source_unit.get_attached_unit_root()
                except Exception:
                    source_root = source_unit
                if source_root is None:
                    continue
                source_root_id = str(get_entity_id(source_root) or "")
                if not source_root_id or source_root_id in seen_roots:
                    continue
                seen_roots.add(source_root_id)
                if not bool(getattr(source_root, "is_alive", lambda: False)()):
                    continue
                if not bool(getattr(source_root, "deployed", True)):
                    continue
                try:
                    if source_root.is_in_reserves() or source_root.is_embarked:
                        continue
                except Exception:
                    pass

                source_member = None
                source_sr = {}
                if callable(find_member):
                    _root, source_member, source_sr = find_member(source_root, "enhancement_fear_made_manifest")
                if source_member is None:
                    try:
                        members = list(source_root.get_attached_unit_members() or [])
                    except Exception:
                        members = [source_root]
                    if not members:
                        members = [source_root]
                    try:
                        members = sorted(members, key=lambda member: str(get_entity_id(member) or ""))
                    except Exception:
                        members = list(members)
                    for member in members:
                        if member is None:
                            continue
                        sr = getattr(member, "special_rules", None)
                        if isinstance(sr, dict) and bool(sr.get("enhancement_fear_made_manifest", False)):
                            source_member = member
                            source_sr = sr
                            break
                if source_member is None or not isinstance(source_sr, dict):
                    continue
                bearer = getattr(source_member, "_get_enhancement_bearer_model", lambda: None)()
                if bearer is None or not bool(getattr(bearer, "is_alive", True)):
                    continue
                try:
                    range_value = float(source_sr.get("enhancement_fear_made_manifest_range", 6.0) or 6.0)
                except Exception:
                    range_value = 6.0
                if range_value <= 0:
                    continue
                if unit not in self._enemy_candidates_within_range_of_model(
                    model=bearer,
                    enemy_roots=[unit],
                    range_value=float(range_value),
                ):
                    continue

                once_key = str(
                    source_sr.get("enhancement_fear_made_manifest_once_key", "fear_made_manifest")
                    or "fear_made_manifest"
                ).strip().lower()
                once_roll = str(source_sr.get("enhancement_fear_made_manifest_once_roll", "D3") or "D3").strip().upper()
                if not once_roll:
                    once_roll = "D3"
                sources.append((player, source_root, source_member, source_sr, bearer, once_key, once_roll))

        if not sources:
            return False

        def _source_sort_key(entry):
            player_obj, source_root, source_member, _source_sr, bearer_model, _once_key, _once_roll = entry
            return (
                str(get_entity_id(source_root) or ""),
                str(get_entity_id(source_member) or ""),
                str(get_entity_id(bearer_model) or ""),
                str(getattr(player_obj, "id", "") or ""),
            )

        sources.sort(key=_source_sort_key)
        owner_player, source_root, source_member, source_sr, bearer_model, once_key, once_roll = sources[0]
        if owner_player is None:
            return False

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx_req = dict(getattr(req, "context", {}) or {})
                if str(ctx_req.get("ability", "") or "") != "fear_made_manifest":
                    continue
                if str(ctx_req.get("target_unit_id", "") or "") == target_id:
                    return True

        can_use_once = False
        if once_key:
            has_used = getattr(source_root, "has_used_unit_once_per_battle", None)
            if callable(has_used):
                can_use_once = not bool(has_used(once_key))
            else:
                sr_root = getattr(source_root, "special_rules", None)
                used_map = sr_root.get("once_per_battle_used") if isinstance(sr_root, dict) else {}
                can_use_once = not bool(isinstance(used_map, dict) and used_map.get(once_key))

        ability_name = (
            str(source_sr.get("enhancement_fear_made_manifest_source", "Fear Made Manifest (Aura)") or "Fear Made Manifest (Aura)").strip()
            or "Fear Made Manifest (Aura)"
        )
        source_unit_id = str(get_entity_id(source_root) or "")
        source_member_unit_id = str(get_entity_id(source_member) or "")
        source_model_id = str(get_entity_id(bearer_model) or "")
        target_sr["fear_made_manifest_pending"] = {
            "owner_id": str(getattr(owner_player, "id", "") or ""),
            "source_unit_id": source_unit_id,
            "source_member_unit_id": source_member_unit_id,
            "source_model_id": source_model_id,
            "turn": int(getattr(game, "turn", 0) or 0),
            "ability_name": ability_name,
            "once_key": once_key,
            "once_roll": once_roll,
            "can_use_once": bool(can_use_once),
        }
        unit.special_rules = target_sr

        options = [
            DecisionOption.create(
                "Destroy 1 model",
                payload={
                    "target_unit_id": target_id,
                    "destroy_count": 1,
                    "use_once_per_battle": False,
                },
            ),
        ]
        if can_use_once:
            options.append(
                DecisionOption.create(
                    f"Destroy {once_roll} models (once per battle)",
                    payload={
                        "target_unit_id": target_id,
                        "destroy_count_roll": once_roll,
                        "use_once_per_battle": True,
                    },
                )
            )
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: choose models to destroy.",
            player_id=getattr(owner_player, "id", None),
            options=options,
            context={
                "ability": "fear_made_manifest",
                "ability_name": ability_name,
                "phase": "Battle-shock",
                "target_unit_id": target_id,
                "source_unit_id": source_unit_id,
                "source_member_unit_id": source_member_unit_id,
                "source_model_id": source_model_id,
                "once_key": once_key,
                "once_roll": once_roll,
                "can_use_once": bool(can_use_once),
            },
        )
        self.request_decision(request)
        return True

    def _queue_aeldari_guiding_presence(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        ability_name: str,
        range_inches: int,
        hit_bonus: int,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "aeldari_guiding_presence":
                    continue
                if str(ctx.get("model_id", "")) == str(model_id):
                    return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = [
            DecisionOption.create(
                str(getattr(cand, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(cand)},
            )
            for cand in sorted(list(candidates), key=_cand_sort_key)
        ]
        if not options:
            return None
        ctx = {
            "ability": "aeldari_guiding_presence",
            "ability_name": str(ability_name or "Guiding Presence").strip(),
            "phase": "Shooting phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_inches),
            "bonus": int(hit_bonus),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ctx['ability_name']}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_aeldari_lucid_eye_fate_die(
        self,
        *,
        player,
        source_unit,
        model,
        choices: list[dict],
        ability_name: str,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not choices:
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "aeldari_lucid_eye_fate_die":
                    continue
                if str(ctx.get("source_unit_id", "")) == str(unit_id):
                    return None

        options = [DecisionOption.create("None", payload={"action": "skip"})]
        for entry in sorted(
            list(choices or []),
            key=lambda item: (int(item.get("die_index", -1)), int(item.get("delta", 0))),
        ):
            try:
                die_index = int(entry.get("die_index", -1))
                before = int(entry.get("before", 0))
                delta = int(entry.get("delta", 0))
                after = int(entry.get("after", 0))
            except Exception:
                continue
            if die_index < 0 or delta not in (-1, 1):
                continue
            label = f"Fate die {die_index + 1}: {before} -> {after}"
            options.append(
                DecisionOption.create(
                    label,
                    payload={
                        "source_unit_id": str(unit_id),
                        "die_index": int(die_index),
                        "delta": int(delta),
                        "before": int(before),
                        "after": int(after),
                    },
                )
            )
        if len(options) <= 1:
            return None

        ctx = {
            "ability": "aeldari_lucid_eye_fate_die",
            "ability_name": str(ability_name or "Lucid Eye").strip(),
            "phase": "Command phase",
            "source_unit_id": str(unit_id),
            "model_id": str(model_id),
            "optional": True,
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ctx['ability_name']}: select one Fate die adjustment (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_aeldari_spirit_stone_heal(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        ability_name: str,
        range_inches: int,
        allow_skip: bool = True,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "aeldari_spirit_stone_heal":
                    continue
                if str(ctx.get("model_id", "")) == str(model_id):
                    return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = []
        if allow_skip:
            options.append(DecisionOption.create("None", payload={"action": "skip"}))
        for cand in sorted(list(candidates), key=_cand_sort_key):
            options.append(
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(cand)},
                )
            )
        if not options:
            return None
        ctx = {
            "ability": "aeldari_spirit_stone_heal",
            "ability_name": str(ability_name or "Spirit Stone of Raelyth").strip(),
            "phase": "Command phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_inches),
            "allow_skip": bool(allow_skip),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ctx['ability_name']}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_resurrection_orb_decision(
        self,
        *,
        player,
        source_unit,
        bearer_model,
        candidates: list,
        ability_name: str,
        phase_label: str,
        variant: str,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or bearer_model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None

        variant_key = str(variant or "").strip().lower()
        if variant_key not in ("nearby", "leading"):
            return None

        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        source_unit_id = get_entity_id(source_unit)
        bearer_model_id = get_entity_id(bearer_model)
        if not source_unit_id or not bearer_model_id:
            return None

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "resurrection_orb":
                    continue
                if str(ctx.get("source_unit_id", "") or "") != str(source_unit_id):
                    continue
                return None

        def _cand_sort_key(unit):
            uid = str(get_entity_id(unit) or "")
            if uid:
                return uid
            return str(getattr(unit, "name", "") or "")

        sorted_candidates = sorted(
            [unit for unit in list(candidates or []) if unit is not None],
            key=_cand_sort_key,
        )
        options = [DecisionOption.create("None", payload={"action": "skip"})]
        allowed_target_ids: list[str] = []
        for cand in sorted_candidates:
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

        ability_label = str(ability_name or "Resurrection Orb").strip() or "Resurrection Orb"
        phase_text = str(phase_label or "").strip() or "Phase"
        context = {
            "ability": "resurrection_orb",
            "ability_name": ability_label,
            "phase": phase_text,
            "optional": True,
            "source_unit_id": str(source_unit_id),
            "unit_id": str(source_unit_id),
            "source_unit": getattr(source_unit, "name", "") or "",
            "bearer_model_id": str(bearer_model_id),
            "bearer_model": getattr(bearer_model, "name", "") or "",
            "resurrection_orb_variant": variant_key,
            "allowed_target_unit_ids": list(allowed_target_ids),
            "allow_skip": True,
        }
        if variant_key == "nearby":
            context["range"] = 6
            prompt = f"{ability_label}: select one NECRONS INFANTRY or MOUNTED unit within 6\" to resurrect (or None)."
        else:
            prompt = f"{ability_label}: resurrect the bearer's led unit (or None)."

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            prompt,
            player_id=getattr(player, "id", None),
            options=options,
            context=context,
        )
        self.request_decision(request)
        return request

    def _queue_aeldari_spirit_conclave_target(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        ability_key: str,
        ability_name: str,
        range_inches: int,
        allow_skip: bool = False,
        extra_context: dict | None = None,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        ability = str(ability_key or "").strip().lower()
        if not ability:
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != ability:
                    continue
                if str(ctx.get("model_id", "") or "") == str(model_id):
                    return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = []
        if allow_skip:
            options.append(DecisionOption.create("None", payload={"action": "skip"}))
        for cand in sorted(list(candidates), key=_cand_sort_key):
            options.append(
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(cand)},
                )
            )
        if not options:
            return None
        ctx = {
            "ability": ability,
            "ability_name": str(ability_name or "Spirit Conclave enhancement").strip() or "Spirit Conclave enhancement",
            "phase": "Command phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_inches),
            "allow_skip": bool(allow_skip),
        }
        if isinstance(extra_context, dict):
            ctx.update(dict(extra_context))
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ctx['ability_name']}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_imperial_knights_valourstrike_target(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        ability_key: str,
        ability_name: str,
        phase_label: str,
        range_inches: int,
        allow_skip: bool = False,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        ability = str(ability_key or "").strip()
        if not ability:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != ability:
                    continue
                if str(ctx.get("source_unit_id", "") or "") != str(unit_id):
                    continue
                return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = []
        if allow_skip:
            options.append(DecisionOption.create("None", payload={"action": "skip"}))
        for cand in sorted(list(candidates), key=_cand_sort_key):
            cand_id = get_entity_id(cand)
            if not cand_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": cand_id},
                )
            )
        if not options:
            return None
        ability_label = str(ability_name or "Valourstrike enhancement").strip() or "Valourstrike enhancement"
        ctx = {
            "ability": ability,
            "ability_name": ability_label,
            "phase": str(phase_label or "").strip() or "Phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(range_inches),
            "allow_skip": bool(allow_skip),
        }
        prompt = f"{ability_label}: select a friendly IMPERIAL KNIGHTS unit."
        if allow_skip:
            prompt = f"{ability_label}: select a friendly IMPERIAL KNIGHTS unit (or None)."
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            prompt,
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_spirit_mark_friendly_selection(
        self,
        *,
        player,
        source_unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        if not model_id or not unit_id:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) not in ("spirit_mark_friendly", "spirit_mark_enemy"):
                    continue
                if str(ctx.get("model_id", "")) == str(model_id):
                    return None

        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        sr = getattr(source_unit, "special_rules", None)
        if isinstance(sr, dict):
            used_owner = str(sr.get("spirit_mark_used_turn_owner", "") or "")
            try:
                used_turn = int(sr.get("spirit_mark_used_turn", 0) or 0)
            except Exception:
                used_turn = 0
            used_ids = list(sr.get("spirit_mark_used_model_ids", []) or [])
            if owner_id and used_owner == owner_id and used_turn == int(turn or 0):
                if str(model_id) in [str(v) for v in used_ids if v]:
                    return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = [DecisionOption.create("None", payload={"action": "skip"})]
        for cand in sorted(list(candidates), key=_cand_sort_key):
            options.append(
                DecisionOption.create(
                    str(getattr(cand, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(cand)},
                )
            )
        if not options:
            return None
        ability_name = str(spec.get("source", "") or "Spirit Mark").strip() or "Spirit Mark"
        ctx = {
            "ability": "spirit_mark_friendly",
            "ability_name": ability_name,
            "phase": "Movement phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "range": int(spec.get("range", 0) or 0),
            "keyword": str(spec.get("keyword", "") or "").strip(),
            "sustained_hits_value": int(spec.get("sustained_hits_value", 1) or 1),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a friendly unit.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_spirit_mark_enemy_selection(
        self,
        *,
        player,
        source_unit,
        model,
        friendly_unit,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or source_unit is None or model is None or friendly_unit is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        model_id = get_entity_id(model)
        unit_id = get_entity_id(source_unit)
        friendly_id = get_entity_id(friendly_unit)
        if not model_id or not unit_id or not friendly_id:
            return None

        try:
            enemies = list(getattr(self.map, "get_enemy_units")(source_unit) or [])
        except Exception:
            enemies = []
        candidates = []
        seen = set()
        for enemy in enemies:
            if enemy is None:
                continue
            try:
                root = enemy.get_attached_unit_root()
            except Exception:
                root = enemy
            if root is None or not getattr(root, "is_alive", lambda: False)():
                continue
            if not getattr(root, "deployed", True):
                continue
            try:
                if root.is_in_reserves() or root.is_embarked:
                    continue
            except Exception:
                pass
            rid = str(get_entity_id(root) or "")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            if not self._model_can_see_unit(model, root, game_map=getattr(self, "map", None)):
                continue
            candidates.append(root)

        if not candidates:
            return None

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = [
            DecisionOption.create(
                str(getattr(cand, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(cand)},
            )
            for cand in sorted(list(candidates), key=_cand_sort_key)
        ]
        if not options:
            return None
        ability_name = str(spec.get("source", "") or "Spirit Mark").strip() or "Spirit Mark"
        ctx = {
            "ability": "spirit_mark_enemy",
            "ability_name": ability_name,
            "phase": "Movement phase",
            "unit": getattr(source_unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "model": getattr(model, "name", "") or "",
            "model_id": model_id,
            "friendly_unit_id": friendly_id,
            "sustained_hits_value": int(spec.get("sustained_hits_value", 1) or 1),
            "keyword": str(spec.get("keyword", "") or "").strip(),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select an enemy unit.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_mortal_wounds_target_decision(
        self,
        *,
        player,
        unit,
        candidates: list,
        spec: dict,
        kind: str,
        model=None,
        allow_skip: bool = False,
        phase: str | None = None,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        if not candidates:
            return None
        kind_key = str(kind or "").strip().lower()
        if kind_key not in ("charge_end", "move_over", "fight_phase_end", "bomb_squigs", "plunder", "floating_death"):
            return None
        unit_id = maybe_entity_id(unit)
        if not unit_id:
            return None
        ability_name = str((spec or {}).get("name", "") or (spec or {}).get("source", "") or "Mortal Wounds").strip()
        if not ability_name:
            ability_name = "Mortal Wounds"

        options = []
        if allow_skip:
            options.append(DecisionOption.create("Skip", payload={"action": "skip"}))

        sorted_candidates = [c for c in candidates if c is not None]
        sorted_candidates.sort(key=lambda c: str(maybe_entity_id(c) or ""))
        used_labels = set()
        candidate_ids = []
        for enemy in sorted_candidates:
            enemy_id = maybe_entity_id(enemy)
            if not enemy_id:
                continue
            candidate_ids.append(str(enemy_id))
            label = str(getattr(enemy, "name", "") or "Enemy unit")
            base = label
            idx = 2
            while label in used_labels:
                label = f"{base} ({idx})"
                idx += 1
            used_labels.add(label)
            options.append(DecisionOption.create(label, payload={"target_unit_id": enemy_id}))

        if not options or (allow_skip and len(options) == 1):
            return None

        ctx = {
            "engine_flow": True,
            "mortal_wounds_kind": kind_key,
            "unit_id": unit_id,
            "ability_name": ability_name,
            "spec": dict(spec or {}),
            "candidate_ids": list(candidate_ids),
        }
        if model is not None:
            model_id = maybe_entity_id(model)
            if model_id:
                ctx["model_id"] = str(model_id)
        if phase:
            ctx["phase"] = str(phase)

        prompt = f"{ability_name}: Select target"
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            prompt,
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_move_over_battleshock_decision(
        self,
        *,
        player,
        unit,
        model,
        candidates: list,
        spec: dict,
        allow_skip: bool = False,
    ) -> DecisionRequest | None:
        if player is None or unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        unit_id = maybe_entity_id(unit)
        model_id = maybe_entity_id(model)
        if not unit_id or not model_id:
            return None

        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest

        ability_name = str(spec.get("source", "") or "Move-over Battle-shock").strip() or "Move-over Battle-shock"
        ability_key = str(spec.get("ability_key", "") or "").strip().lower()
        if not ability_key:
            ability_key = "move_over_battleshock"

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "move_over_battleshock":
                    continue
                if str(ctx.get("model_id", "") or "") != str(model_id):
                    continue
                if str(ctx.get("ability_key", "") or "").strip().lower() != ability_key:
                    continue
                return None

        def _cand_sort_key(u):
            try:
                return str(maybe_entity_id(u) or "")
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = []
        if allow_skip:
            options.append(DecisionOption.create("None", payload={"action": "skip"}))
        for cand in sorted([c for c in list(candidates or []) if c is not None], key=_cand_sort_key):
            target_id = maybe_entity_id(cand)
            if not target_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(cand, "name", "") or "Enemy unit"),
                    payload={"target_unit_id": target_id},
                )
            )
        if not options:
            return None
        if len(options) == 1 and options[0].payload.get("action") == "skip":
            return None

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select an enemy unit moved over{'' if not allow_skip else ' (or None)'}.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "move_over_battleshock",
                "ability_name": ability_name,
                "ability_key": ability_key,
                "phase": "Movement phase",
                "source_unit_id": str(unit_id),
                "unit_id": str(unit_id),
                "model_id": str(model_id),
            },
        )
        self.request_decision(request)
        return request

    def _queue_move_over_no_cover_decision(
        self,
        *,
        player,
        unit,
        model,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or unit is None or model is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        unit_id = maybe_entity_id(unit)
        model_id = maybe_entity_id(model)
        if not unit_id or not model_id:
            return None

        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest

        ability_name = str(spec.get("source", "") or "Flame-wreathed").strip() or "Flame-wreathed"
        ability_key = str(spec.get("ability_key", "") or "").strip().lower()
        if not ability_key:
            ability_key = "move_over_no_cover"

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "move_over_no_cover":
                    continue
                if str(ctx.get("model_id", "") or "") != str(model_id):
                    continue
                if str(ctx.get("ability_key", "") or "").strip().lower() != ability_key:
                    continue
                return None

        def _cand_sort_key(u):
            try:
                return str(maybe_entity_id(u) or "")
            except Exception:
                return str(getattr(u, "name", "") or "")

        options = []
        for cand in sorted([c for c in list(candidates or []) if c is not None], key=_cand_sort_key):
            target_id = maybe_entity_id(cand)
            if not target_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(cand, "name", "") or "Enemy unit"),
                    payload={"target_unit_id": target_id},
                )
            )
        if not options:
            return None

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select an enemy unit moved over.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "move_over_no_cover",
                "ability_name": ability_name,
                "ability_key": ability_key,
                "phase": "Movement phase",
                "source_unit_id": str(unit_id),
                "unit_id": str(unit_id),
                "model_id": str(model_id),
            },
        )
        self.request_decision(request)
        return request

    def _queue_grenade_pack_flyover_target_decision(
        self,
        *,
        player,
        unit,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        unit_id = maybe_entity_id(unit)
        if not unit_id:
            return None
        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict):
            if str(sr.get("grenade_pack_flyover_used_turn_owner", "") or "") == owner_id and int(
                sr.get("grenade_pack_flyover_used_turn", 0) or 0
            ) == turn:
                return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "grenade_pack_flyover":
                    continue
                if str(ctx.get("unit_id", "")) == str(unit_id):
                    return None

        options = [DecisionOption.create("None", payload={"action": "skip"})]
        sorted_candidates = [c for c in candidates if c is not None]
        sorted_candidates.sort(key=lambda c: str(maybe_entity_id(c) or ""))
        for enemy in sorted_candidates:
            enemy_id = maybe_entity_id(enemy)
            if not enemy_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(enemy, "name", "") or "Enemy unit"),
                    payload={"target_unit_id": enemy_id},
                )
            )
        if len(options) <= 1:
            return None

        ability_name = str(spec.get("source", "") or "Grenade Pack Flyover").strip() or "Grenade Pack Flyover"
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        try:
            threshold = int(spec.get("threshold", 0) or 0)
        except Exception:
            threshold = 0
        try:
            mortal_per = int(spec.get("mortal_per_success", 1) or 0)
        except Exception:
            mortal_per = 0
        try:
            max_mortal = int(spec.get("max_mortal", 0) or 0)
        except Exception:
            max_mortal = 0
        ctx = {
            "ability": "grenade_pack_flyover",
            "ability_name": ability_name,
            "phase": "Movement phase",
            "unit": getattr(unit, "name", "") or "",
            "unit_id": unit_id,
            "source_unit_id": unit_id,
            "range": int(range_value),
            "threshold": int(threshold),
            "mortal_per_success": int(mortal_per),
            "max_mortal": int(max_mortal),
            "spec": dict(spec or {}),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_end_of_fight_embark_decision(
        self,
        *,
        player,
        transport,
        candidates: list,
        spec: dict,
    ) -> DecisionRequest | None:
        if player is None or transport is None:
            return None
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if not candidates:
            return None
        transport_id = maybe_entity_id(transport)
        if not transport_id:
            return None
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "end_of_fight_embark":
                    continue
                if str(ctx.get("transport_id", "")) == str(transport_id):
                    return None

        options = [DecisionOption.create("None", payload={"action": "skip"})]
        sorted_candidates = [c for c in candidates if c is not None]
        sorted_candidates.sort(key=lambda c: str(maybe_entity_id(c) or ""))
        for unit in sorted_candidates:
            unit_id = maybe_entity_id(unit)
            if not unit_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(unit, "name", "") or "Unit"),
                    payload={"target_unit_id": unit_id},
                )
            )
        if len(options) <= 1:
            return None

        ability_name = str(spec.get("source", "") or "End of fight embark").strip() or "End of fight embark"
        try:
            range_value = int(spec.get("range", 0) or 0)
        except Exception:
            range_value = 0
        try:
            max_models = int(spec.get("max_models", 0) or 0)
        except Exception:
            max_models = 0
        keyword = str(spec.get("keyword", "") or "").strip()
        ctx = {
            "ability": "end_of_fight_embark",
            "ability_name": ability_name,
            "phase": "Fight phase",
            "unit": getattr(transport, "name", "") or "",
            "unit_id": transport_id,
            "transport_id": transport_id,
            "range": int(range_value),
            "max_models": int(max_models),
            "keyword": keyword,
            "spec": dict(spec or {}),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a unit to embark.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_reactive_move_confirmation(
        self,
        *,
        player,
        unit,
        kind: str,
        movement_type: str,
        source: str | None,
        message: str | None,
        moving_unit=None,
        attacker_unit=None,
        range_value: int | None = None,
        allow_engagement_range: bool | None = None,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        unit_id = maybe_entity_id(unit)
        if not unit_id:
            return None
        moving_unit_id = maybe_entity_id(moving_unit) if moving_unit is not None else None
        attacker_unit_id = maybe_entity_id(attacker_unit) if attacker_unit is not None else None
        source = str(source or "").strip() or "Reactive Move"
        if not message and moving_unit is not None and range_value is not None:
            enemy_name = getattr(moving_unit, "name", "Enemy unit")
            message = (
                f"{enemy_name} ended a move within {int(range_value)}\" of {getattr(unit, 'name', 'unit')}.\n\n"
                f"{source}: Make a Normal move of up to D6\"?"
            )
        options = [
            DecisionOption.create("Move", payload={"choice": True}),
            DecisionOption.create("Skip", payload={"choice": False}),
        ]
        ctx = self._reactive_move_context(
            kind=str(kind or "").strip() or "reactive",
            unit_id=unit_id,
            movement_type=movement_type,
            source=source,
            moving_unit_id=moving_unit_id,
            attacker_unit_id=attacker_unit_id,
            range_value=range_value,
            allow_engagement_range=allow_engagement_range,
        )
        if message:
            ctx["message"] = message
        request = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            source,
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_bodyguard_return_decision(
        self,
        *,
        player,
        leader_unit,
        bodyguard_unit,
        ability: dict,
        remaining: int,
        allowed_model_ids: list[str] | None = None,
        allow_skip: bool = True,
    ) -> DecisionRequest | None:
        if player is None or leader_unit is None or bodyguard_unit is None:
            return None
        if int(remaining or 0) <= 0:
            return None
        bodyguard_id = maybe_entity_id(bodyguard_unit)
        if not bodyguard_id:
            return None
        leader_id = maybe_entity_id(leader_unit)
        if not leader_id:
            return None
        destroyed = list(getattr(bodyguard_unit, "models_lost", []) or [])
        allowed_set = {str(v) for v in list(allowed_model_ids or []) if v}
        if allowed_set:
            destroyed = [m for m in destroyed if str(get_entity_id(m) or "") in allowed_set]
        if not destroyed:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None:
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_ALLOCATE_DAMAGE:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("selection_kind", "") or "") != "bodyguard_return":
                    continue
                if str(ctx.get("leader_unit_id", "") or "") != str(leader_id):
                    continue
                if str(ctx.get("bodyguard_unit_id", "") or "") != str(bodyguard_id):
                    continue
                return req
        try:
            destroyed_sorted = sorted(destroyed, key=lambda m: str(get_entity_id(m) or ""))
        except Exception:
            destroyed_sorted = list(destroyed)
        ability_name = str(ability.get("name", "") or "Bodyguard Return")
        options = []
        if allow_skip:
            options.append(DecisionOption.create("None", payload={"model_id": None, "action": "skip"}))
        used_labels = set()
        for model in destroyed_sorted:
            label = str(getattr(model, "name", "") or "Model")
            base = label
            idx = 2
            while label in used_labels:
                label = f"{base} [{idx}]"
                idx += 1
            used_labels.add(label)
            options.append(DecisionOption.create(label, payload={"model_id": get_entity_id(model)}))
        allowed_ids = [get_entity_id(m) for m in destroyed_sorted if get_entity_id(m)]
        ctx = {
            "selection_kind": "bodyguard_return",
            "ability_name": ability_name,
            "phase": "Command phase",
            "leader_unit_id": leader_id,
            "unit_id": bodyguard_id,
            "bodyguard_unit_id": bodyguard_id,
            "amount": int(remaining or 0),
            "remaining": int(remaining or 0),
            "reason": f"{ability_name}: Return bodyguard model",
            "allowed_model_ids": allowed_ids,
            "allow_skip": bool(allow_skip),
        }
        request = DecisionRequest.create(
            DECISION_ALLOCATE_DAMAGE,
            f"{ability_name}: Return bodyguard model",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_choice_samples_decision(
        self,
        *,
        player,
        unit,
        ability_name: str,
        return_models: list | None = None,
        cp_gain: int = 0,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        unit_id = maybe_entity_id(unit)
        if not unit_id:
            return None
        queue = getattr(self, "decision_queue", None)
        if queue is not None:
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_ALLOCATE_DAMAGE:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("selection_kind", "") or "") != "choice_samples":
                    continue
                if str(ctx.get("unit_id", "") or "") != str(unit_id):
                    continue
                return req

        models = [m for m in list(return_models or []) if m is not None]
        try:
            models = sorted(models, key=lambda m: str(get_entity_id(m) or ""))
        except Exception:
            models = list(models)
        options = [DecisionOption.create("None", payload={"action": "skip"})]
        used_labels = set()
        allowed_model_ids = []
        for model in models:
            model_id = get_entity_id(model)
            if not model_id:
                continue
            allowed_model_ids.append(str(model_id))
            label = str(getattr(model, "name", "") or "Model")
            base = label
            idx = 2
            while label in used_labels:
                label = f"{base} [{idx}]"
                idx += 1
            used_labels.add(label)
            options.append(
                DecisionOption.create(
                    f"Return: {label}",
                    payload={"action": "return_model", "model_id": model_id},
                )
            )
        if int(cp_gain or 0) > 0:
            options.append(
                DecisionOption.create(
                    f"Gain {int(cp_gain)}CP",
                    payload={"action": "gain_cp", "cp_gain": int(cp_gain)},
                )
            )
        if len(options) <= 1:
            return None

        ctx = {
            "selection_kind": "choice_samples",
            "ability_name": str(ability_name or "Choice Samples").strip() or "Choice Samples",
            "phase": "Command phase",
            "unit_id": str(unit_id),
            "allowed_model_ids": list(allowed_model_ids),
            "cp_gain": int(max(0, int(cp_gain or 0))),
            "allow_skip": True,
        }
        request = DecisionRequest.create(
            DECISION_ALLOCATE_DAMAGE,
            f"{ctx['ability_name']}: Select one option.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _apply_spirit_snare_bonus_to_model(
        self,
        *,
        model,
        player=None,
        destroyed_model=None,
        ability_name: str = "Spirit Snare",
    ) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        model_id = str(get_entity_id(model) or "")
        if not model_id:
            return False
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        entries = sr.get("spirit_snare_ritual_bonus_by_model_id", {})
        if not isinstance(entries, dict):
            entries = {}
        try:
            current = int(entries.get(model_id, 0) or 0)
        except Exception:
            current = 0
        updated = max(0, min(2, current + 1))
        if updated == current:
            return False
        entries = dict(entries)
        entries[model_id] = int(updated)
        sr["spirit_snare_ritual_bonus_by_model_id"] = entries
        unit.special_rules = sr
        try:
            from ...utility.event_bus import append_action

            if player is not None:
                target_label = str(getattr(destroyed_model, "name", "model") or "model")
                append_action(
                    player,
                    f"{ability_name}: {getattr(model, 'name', 'Model')} gains +1 Ritual test bonus "
                    f"(now +{updated}) after {target_label} was destroyed.",
                )
        except Exception:
            pass
        return True

    def _queue_spirit_snare_recipient_decision(
        self,
        *,
        player,
        candidates: list,
        destroyed_model=None,
        ability_name: str = "Spirit Snare",
    ) -> DecisionRequest | None:
        if player is None:
            return None
        valid = [m for m in list(candidates or []) if m is not None and getattr(m, "is_alive", True)]
        if not valid:
            return None
        try:
            ordered = sorted(valid, key=lambda m: str(get_entity_id(m) or ""))
        except Exception:
            ordered = list(valid)
        options = []
        used_labels = set()
        for model in ordered:
            model_id = get_entity_id(model)
            if not model_id:
                continue
            unit = getattr(model, "parent_unit", None)
            unit_name = str(getattr(unit, "name", "Unit") or "Unit")
            label = f"{unit_name} - {getattr(model, 'name', 'Model')}"
            base = label
            idx = 2
            while label in used_labels:
                label = f"{base} [{idx}]"
                idx += 1
            used_labels.add(label)
            options.append(DecisionOption.create(label, payload={"model_id": model_id}))
        if not options:
            return None
        ctx = {
            "selection_kind": "spirit_snare_recipient",
            "ability_name": str(ability_name or "Spirit Snare"),
            "destroyed_model_id": get_entity_id(destroyed_model) if destroyed_model is not None else None,
            "candidate_model_ids": [opt.payload.get("model_id") for opt in options if opt.payload.get("model_id")],
        }
        request = DecisionRequest.create(
            DECISION_ALLOCATE_DAMAGE,
            f"{ability_name}: select a model to gain the Ritual bonus.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_reactive_move_movement_decision(
        self,
        *,
        player,
        unit,
        max_distance: int,
        kind: str,
        movement_type: str,
        source: str | None,
        moving_unit=None,
        attacker_unit=None,
        range_value: int | None = None,
        allow_engagement_range: bool | None = None,
        allowed_model_ids: list[str] | None = None,
        allow_skip: bool | None = None,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        unit_id = maybe_entity_id(unit)
        if not unit_id:
            return None
        moving_unit_id = maybe_entity_id(moving_unit) if moving_unit is not None else None
        attacker_unit_id = maybe_entity_id(attacker_unit) if attacker_unit is not None else None
        source = str(source or "").strip() or "Reactive Move"
        options = [
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": unit_id, "movement_type": movement_type, "action": "confirm"},
            ),
            DecisionOption.create(
                "Skip",
                payload={"unit_id": unit_id, "movement_type": movement_type, "action": "skip"},
            ),
        ]
        ctx = self._reactive_move_context(
            kind=str(kind or "").strip() or "reactive",
            unit_id=unit_id,
            movement_type=movement_type,
            source=source,
            moving_unit_id=moving_unit_id,
            attacker_unit_id=attacker_unit_id,
            range_value=range_value,
            allow_engagement_range=allow_engagement_range,
        )
        ctx["unit_id"] = unit_id
        ctx["movement_type"] = movement_type
        ctx["max_distance"] = int(max_distance)
        if allowed_model_ids is not None:
            ctx["allowed_model_ids"] = list(allowed_model_ids)
        if allow_skip is not None:
            ctx["allow_skip"] = bool(allow_skip)
        request = DecisionRequest.create(
            DECISION_MOVE_UNIT,
            f"Move {getattr(unit, 'name', 'Unit')} ({movement_type})",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_battle_focus_reactive_selection(
        self,
        *,
        player,
        candidates: list,
        manager,
        maneuver: str,
        moving_unit=None,
        attacker_unit=None,
        hits_by_unit: dict | None = None,
    ) -> DecisionRequest | None:
        if player is None or not candidates:
            return None
        if manager is None:
            return None
        maneuver_key = str(maneuver or "").strip().lower()
        if maneuver_key not in ("opportunity", "fade_back"):
            return None
        try:
            sorted_candidates = sorted(
                [c for c in candidates if c is not None],
                key=lambda c: str(maybe_entity_id(c) or ""),
            )
        except Exception:
            sorted_candidates = [c for c in candidates if c is not None]
        prompt = "Select Battle Focus reactive unit." if maneuver_key == "opportunity" else "Select Battle Focus unit to fade back."
        options = [DecisionOption.create("Skip", payload={"action": "skip"})]
        used_labels = set()
        for unit in sorted_candidates:
            label = str(getattr(unit, "name", "") or "Unit")
            if maneuver_key == "fade_back":
                try:
                    hits = int((hits_by_unit or {}).get(unit, 0) or 0)
                except Exception:
                    hits = 0
                label = f"{label} (Hits: {hits})"
            base = label
            idx = 2
            while label in used_labels:
                label = f"{base} [{idx}]"
                idx += 1
            used_labels.add(label)
            options.append(
                DecisionOption.create(
                    label,
                    payload={"unit_id": get_entity_id(unit)},
                )
            )
        ctx = {
            "ability": "battle_focus",
            "maneuver": maneuver_key,
            "reactive_move_kind": "battle_focus",
            "reactive_move_movement_type": "reactive",
        }
        if moving_unit is not None:
            moving_unit_id = maybe_entity_id(moving_unit)
            if moving_unit_id:
                ctx["reactive_move_moving_unit_id"] = moving_unit_id
        if attacker_unit is not None:
            attacker_unit_id = maybe_entity_id(attacker_unit)
            if attacker_unit_id:
                ctx["reactive_move_attacker_unit_id"] = attacker_unit_id
        request = DecisionRequest.create(
            DECISION_SELECT_OVERWATCH_SHOOTER,
            prompt,
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _maybe_queue_reactive_move_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        decision_type = str(getattr(request, "decision_type", "") or "")
        if decision_type == DECISION_CONFIRM_YES_NO:
            ctx = dict(getattr(request, "context", {}) or {})
            kind = str(ctx.get("reactive_move_kind", "") or "").strip()
            if kind not in ("loping_speed", "blood_surge", "brazen_fury", "horde_move", "unhinged_vengeance"):
                return
            opt = None
            for candidate in list(getattr(request, "options", []) or []):
                if getattr(candidate, "option_id", None) == getattr(result, "option_id", None):
                    opt = candidate
                    break
            if opt is None:
                return
            payload = getattr(opt, "payload", {}) or {}
            choice = bool(payload.get("choice", False))
            if not choice:
                return
            unit_id = str(ctx.get("reactive_move_unit_id") or ctx.get("unit_id") or "")
            unit = self._resolve_unit_by_id(unit_id)
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if unit is None or player is None:
                return
            source = str(ctx.get("reactive_move_source", "") or "Reactive Move").strip() or "Reactive Move"
            movement_type = str(ctx.get("reactive_move_movement_type", "") or "")
            if kind == "loping_speed":
                moving_unit_id = str(ctx.get("reactive_move_moving_unit_id") or "")
                moving_unit = self._resolve_unit_by_id(moving_unit_id)
                if moving_unit is None:
                    return
                rng = int(ctx.get("reactive_move_range") or 9)
                if not unit.can_loping_speed(
                    game=self,
                    game_map=getattr(self, "map", None),
                    moving_unit=moving_unit,
                    range_override=rng,
                ):
                    return
                max_distance = int(self.roll_loping_speed_distance(unit) or 0)
                if max_distance <= 0:
                    return
                self._queue_reactive_move_movement_decision(
                    player=player,
                    unit=unit,
                    moving_unit=moving_unit,
                    max_distance=max_distance,
                    kind=kind,
                    movement_type=movement_type or "loping_speed",
                    source=source,
                    range_value=rng,
                )
                return
            if kind == "blood_surge":
                if not unit.can_blood_surge(game=self, game_map=getattr(self, "map", None)):
                    return
                max_distance = int(self.roll_blood_surge_distance(unit) or 0)
                if max_distance <= 0:
                    return
                attacker_unit_id = str(ctx.get("reactive_move_attacker_unit_id") or "")
                attacker_unit = self._resolve_unit_by_id(attacker_unit_id)
                self._queue_reactive_move_movement_decision(
                    player=player,
                    unit=unit,
                    attacker_unit=attacker_unit,
                    max_distance=max_distance,
                    kind=kind,
                    movement_type=movement_type or "blood_surge",
                    source=source,
                )
                return
            if kind == "brazen_fury":
                if not unit.can_brazen_fury(game=self, game_map=getattr(self, "map", None)):
                    return
                max_distance = int(self.roll_brazen_fury_distance(unit) or 0)
                if max_distance <= 0:
                    return
                attacker_unit_id = str(ctx.get("reactive_move_attacker_unit_id") or "")
                attacker_unit = self._resolve_unit_by_id(attacker_unit_id)
                self._queue_reactive_move_movement_decision(
                    player=player,
                    unit=unit,
                    attacker_unit=attacker_unit,
                    max_distance=max_distance,
                    kind=kind,
                    movement_type=movement_type or "brazen_fury",
                    source=source,
                )
                return
            if kind == "horde_move":
                if not unit.can_horde_move(game=self, game_map=getattr(self, "map", None)):
                    return
                max_distance = int(self.roll_horde_move_distance(unit) or 0)
                if max_distance <= 0:
                    return
                attacker_unit_id = str(ctx.get("reactive_move_attacker_unit_id") or "")
                attacker_unit = self._resolve_unit_by_id(attacker_unit_id)
                self._queue_reactive_move_movement_decision(
                    player=player,
                    unit=unit,
                    attacker_unit=attacker_unit,
                    max_distance=max_distance,
                    kind=kind,
                    movement_type=movement_type or "horde_move",
                    source=source,
                )
                return
            if kind == "unhinged_vengeance":
                if not unit.can_unhinged_vengeance(game=self, game_map=getattr(self, "map", None)):
                    return
                max_distance = int(self.roll_unhinged_vengeance_distance(unit) or 0)
                if max_distance <= 0:
                    return
                attacker_unit_id = str(ctx.get("reactive_move_attacker_unit_id") or "")
                attacker_unit = self._resolve_unit_by_id(attacker_unit_id)
                self._queue_reactive_move_movement_decision(
                    player=player,
                    unit=unit,
                    attacker_unit=attacker_unit,
                    max_distance=max_distance,
                    kind=kind,
                    movement_type=movement_type or "unhinged_vengeance",
                    source=source,
                    allow_engagement_range=True,
                )
                return
        if decision_type == DECISION_SELECT_OVERWATCH_SHOOTER:
            ctx = dict(getattr(request, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != "battle_focus":
                return
            opt = None
            for candidate in list(getattr(request, "options", []) or []):
                if getattr(candidate, "option_id", None) == getattr(result, "option_id", None):
                    opt = candidate
                    break
            if opt is None:
                return
            payload = getattr(opt, "payload", {}) or {}
            if bool(result.payload.get("skipped", False)) or str(payload.get("action", "") or "") == "skip":
                return
            unit_id = str(payload.get("unit_id", "") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if unit is None or player is None:
                return
            army = player.get_army()
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            if mgr is None:
                return
            maneuver = str(ctx.get("maneuver", "") or "").strip().lower()
            moving_unit_id = str(ctx.get("reactive_move_moving_unit_id") or "")
            attacker_unit_id = str(ctx.get("reactive_move_attacker_unit_id") or "")
            moving_unit = self._resolve_unit_by_id(moving_unit_id) if moving_unit_id else None
            attacker_unit = self._resolve_unit_by_id(attacker_unit_id) if attacker_unit_id else None
            if maneuver == "opportunity":
                applied = bool(mgr.apply_reactive_maneuver(unit, mgr.MANEUVER_OPPORTUNITY, self, moving_unit=moving_unit))
            elif maneuver == "fade_back":
                ae_mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
                can_lethal_surge = bool(
                    ae_mgr is not None
                    and bool(getattr(ae_mgr, "devoted_of_ynnead_lethal_surge_available", lambda *_a, **_k: False)(unit, game=self))
                )
                if can_lethal_surge:
                    try:
                        turn = int(getattr(self, "turn", 0) or 0)
                    except Exception:
                        turn = 0
                    try:
                        turn_owner = getattr(self, "get_current_player", lambda: None)()
                    except Exception:
                        turn_owner = None
                    turn_owner_id = str(getattr(turn_owner, "id", "") or "")
                    self._queue_optional_ability_confirmation(
                        player=player,
                        ability_key="aeldari_strength_from_death_lethal_surge",
                        ability_name="Strength from Death (Lethal Surge)",
                        message=f"Use Lethal Surge for {getattr(unit, 'name', 'Unit')}?",
                        context={
                            "unit_id": unit_id,
                            "attacker_unit_id": attacker_unit_id,
                            "turn": int(turn or 0),
                            "turn_owner_id": turn_owner_id,
                        },
                        payload={
                            "unit_id": unit_id,
                            "attacker_unit_id": attacker_unit_id,
                        },
                        instance_key=f"{unit_id}:{turn}:{turn_owner_id}:aeldari_strength_from_death_lethal_surge",
                    )
                    return
                applied = bool(mgr.apply_reactive_maneuver(unit, mgr.MANEUVER_FADE_BACK, self, attacker_unit=attacker_unit))
            else:
                return
            if not applied:
                return
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                return
            if sr.get("battle_focus_reactive_move_pending"):
                return
            try:
                max_distance = int(sr.get("battle_focus_reactive_move_max", 0) or 0)
            except Exception:
                max_distance = 0
            if max_distance <= 0:
                return
            source = str(sr.get("battle_focus_reactive_move_source", "") or "Battle Focus").strip() or "Battle Focus"
            kind = str(sr.get("battle_focus_reactive_move_kind", "") or "battle_focus").strip() or "battle_focus"
            allow_engagement_range = bool(sr.get("battle_focus_reactive_move_allow_engagement_range", False))
            self._queue_reactive_move_movement_decision(
                player=player,
                unit=unit,
                moving_unit=moving_unit,
                attacker_unit=attacker_unit,
                max_distance=max_distance,
                kind=kind,
                movement_type="reactive",
                source=source,
                allow_engagement_range=allow_engagement_range,
            )
        if decision_type == DECISION_MOVE_UNIT:
            ctx = dict(getattr(request, "context", {}) or {})
            kind = str(ctx.get("reactive_move_kind", "") or "").strip()
            if kind != "careen":
                return
            opt = None
            for candidate in list(getattr(request, "options", []) or []):
                if getattr(candidate, "option_id", None) == getattr(result, "option_id", None):
                    opt = candidate
                    break
            payload = getattr(opt, "payload", {}) or {}
            skipped = bool(getattr(result, "payload", {}).get("skipped", False)) or bool(payload.get("skip", False)) or str(payload.get("action", "") or "") == "skip"
            unit_id = str(ctx.get("reactive_move_unit_id") or ctx.get("unit_id") or payload.get("unit_id") or "")
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            unit.resolve_careen_deadly_demise(game_map=getattr(self, "map", None), use_move=not skipped)
        return

    def _maybe_apply_optional_ability_confirmation(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        decision_type = str(getattr(request, "decision_type", "") or "")
        if decision_type != DECISION_CONFIRM_YES_NO:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        ability_key = str(ctx.get("ability", "") or ctx.get("ability_key", "") or "").strip().lower()
        if ability_key not in (
            "shadow_in_the_warp",
            "waaagh",
            "possessed_lord",
            "fight_phase_melee_ap_boost",
            "might_of_titan",
            "thrilling_spectacle",
            "chance_for_glory",
            "malefic_destruction",
            "sacrificial_dagger",
            "sacrificial_blessing",
            "twisted_sorceries",
            "start_any_phase_damage_set_one",
            "start_any_phase_invulnerable_save",
            "start_any_phase_fnp",
            "dark_ritual",
            "movement_phase_move_weapon_bonus",
            "hand_of_asuryan",
            "shieldbreaker",
            "soulless_horror",
            "lord_of_the_storm",
            "ammo_runt",
            "flickerjump",
            "daemonic_patrons",
            "power_from_pain_command",
            "power_from_pain_empower",
            "enhancement_fight_first",
            "umbralefic_crystal",
            "opponent_turn_strategic_reserves",
            "fight_phase_destroyed_strategic_reserves",
            "opponent_turn_destroyed_reposition",
            "cloudstrider",
            "seductive_gambit",
            "sensational_performance",
            "cult_ambush",
            "battle_focus_flitting_shadows",
            "battle_focus_sudden_strike",
            "battle_focus_fade_back",
            "sentinel_storm",
            "sweeping_advance",
            "daemonic_ordnance",
            "warp_rift_firepower",
            "seized_opportunity",
            "geomantic_hunters",
            "resource_transmutation",
            "optimal_application",
            "ruthless_reinvestment",
            "oathbound_speculator",
            "dead_reckoning",
            "warpmeld_sacrifice",
            "possessed_blade_fight",
            "furys_cage",
            "aeldari_strength_from_death_lethal_surge",
            "our_time_is_nigh",
            "desperate_devotion",
            "the_imperiums_sword",
            "rites_of_war",
        ):
            return
        selected = None
        for opt in list(getattr(request, "options", []) or []):
            if getattr(opt, "option_id", None) == getattr(result, "option_id", None):
                selected = opt
                break
        payload = dict(getattr(selected, "payload", {}) or {}) if selected is not None else {}
        choice = None
        if "choice" in payload:
            choice = bool(payload.get("choice"))
        elif "choice" in getattr(result, "payload", {}):
            choice = bool(result.payload.get("choice"))
        if ability_key == "aeldari_strength_from_death_lethal_surge":
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            army = player.get_army()
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            if mgr is None:
                return
            attacker_unit_id = str(payload.get("attacker_unit_id") or ctx.get("attacker_unit_id") or "")
            attacker_unit = self._resolve_unit_by_id(attacker_unit_id) if attacker_unit_id else None
            applied = bool(
                mgr.apply_reactive_maneuver(
                    unit,
                    mgr.MANEUVER_FADE_BACK,
                    self,
                    attacker_unit=attacker_unit,
                    use_lethal_surge=bool(choice),
                )
            )
            if not applied:
                return
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or sr.get("battle_focus_reactive_move_pending"):
                return
            try:
                max_distance = int(sr.get("battle_focus_reactive_move_max", 0) or 0)
            except Exception:
                max_distance = 0
            if max_distance <= 0:
                return
            source = str(sr.get("battle_focus_reactive_move_source", "") or "Battle Focus").strip() or "Battle Focus"
            kind = str(sr.get("battle_focus_reactive_move_kind", "") or "battle_focus").strip() or "battle_focus"
            allow_engagement_range = bool(sr.get("battle_focus_reactive_move_allow_engagement_range", False))
            self._queue_reactive_move_movement_decision(
                player=player,
                unit=unit,
                attacker_unit=attacker_unit,
                max_distance=max_distance,
                kind=kind,
                movement_type="reactive",
                source=source,
                allow_engagement_range=allow_engagement_range,
            )
            return
        if not choice:
            return

        if ability_key == "the_imperiums_sword":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                return
            source_member_id = str(payload.get("source_member_unit_id") or ctx.get("source_member_unit_id") or "")
            source_member = self._resolve_unit_by_id(source_member_id) if source_member_id else None
            if source_member is None:
                find_source = getattr(self, "_attached_member_with_enhancement_flag", None)
                if callable(find_source):
                    _root, source_member, _source_sr = find_source(root, "enhancement_the_imperiums_sword")
            if source_member is None:
                return
            sr = getattr(source_member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_the_imperiums_sword")):
                return
            once_key = str(
                payload.get("ability_key")
                or ctx.get("ability_key")
                or sr.get("enhancement_the_imperiums_sword_once_key")
                or "the_imperiums_sword"
            ).strip().lower()
            if not once_key:
                once_key = "the_imperiums_sword"
            if root.has_used_unit_once_per_battle(once_key):
                return
            try:
                attacks_bonus = int(
                    payload.get("attacks_bonus")
                    or ctx.get("attacks_bonus")
                    or sr.get("enhancement_the_imperiums_sword_other_models_bonus", 1)
                    or 1
                )
            except Exception:
                attacks_bonus = 1
            if attacks_bonus <= 0:
                return
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            if not phase_name:
                phase_name = "FIGHT_PHASE"
            sr["enhancement_the_imperiums_sword_other_models_active"] = True
            sr["enhancement_the_imperiums_sword_other_models_bonus"] = int(attacks_bonus)
            sr["enhancement_the_imperiums_sword_other_models_expires_phase"] = phase_name
            source_member.special_rules = sr
            ability_name = str(ctx.get("ability_name", "") or "The Imperium's Sword").strip() or "The Imperium's Sword"
            root.mark_unit_once_per_battle_used(once_key, ability_name=ability_name)
            return

        if ability_key == "rites_of_war":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                return
            source_member_id = str(payload.get("source_member_unit_id") or ctx.get("source_member_unit_id") or "")
            source_member = self._resolve_unit_by_id(source_member_id) if source_member_id else None
            if source_member is None:
                find_source = getattr(self, "_attached_member_with_enhancement_flag", None)
                if callable(find_source):
                    _root, source_member, _source_sr = find_source(root, "enhancement_rites_of_war")
            if source_member is None:
                return
            sr = getattr(source_member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_rites_of_war")):
                return
            once_key = str(
                payload.get("ability_key")
                or ctx.get("ability_key")
                or sr.get("enhancement_rites_of_war_once_key")
                or "rites_of_war"
            ).strip().lower()
            if not once_key:
                once_key = "rites_of_war"
            if root.has_used_unit_once_per_battle(once_key):
                return
            try:
                oc_bonus = int(
                    payload.get("objective_control_bonus")
                    or ctx.get("objective_control_bonus")
                    or sr.get("enhancement_rites_of_war_other_models_bonus", 1)
                    or 1
                )
            except Exception:
                oc_bonus = 1
            if oc_bonus <= 0:
                return
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            if not phase_name:
                phase_name = "FIGHT_PHASE"
            sr["enhancement_rites_of_war_other_models_active"] = True
            sr["enhancement_rites_of_war_other_models_bonus"] = int(oc_bonus)
            sr["enhancement_rites_of_war_other_models_expires_phase"] = phase_name
            source_member.special_rules = sr
            ability_name = str(ctx.get("ability_name", "") or "Rites of War").strip() or "Rites of War"
            root.mark_unit_once_per_battle_used(once_key, ability_name=ability_name)
            return

        if ability_key == "desperate_devotion":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            root = unit
            get_root = getattr(unit, "get_attached_unit_root", None)
            if callable(get_root):
                try:
                    resolved = get_root()
                except (AttributeError, RuntimeError, TypeError):
                    resolved = None
                if resolved is not None:
                    root = resolved
            if root is None or not root.is_alive():
                return
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
            activate = getattr(mgr, "activate_desperate_devotion", None) if mgr is not None else None
            if not callable(activate):
                return
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            action = str(payload.get("trigger_action") or ctx.get("trigger_action") or "").strip().lower()
            if not action:
                action = "move"
            activate(
                root,
                action=action,
                game=self,
                player=player,
                ability_name=str(ctx.get("ability_name", "") or "Desperate Devotion").strip() or "Desperate Devotion",
            )
            return

        if ability_key == "warpmeld_sacrifice":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                return
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            mgr = getattr(army, "thousand_sons_detachments", None) if army is not None else None
            activate = getattr(mgr, "activate_warpmeld_sacrifice", None) if mgr is not None else None
            if not callable(activate):
                return
            mode = str(payload.get("ability_mode") or ctx.get("ability_mode") or "offense").strip().lower()
            if mode not in {"offense", "defense"}:
                mode = "offense"
            activate(root, mode=mode, game=self)
            return

        if ability_key == "our_time_is_nigh":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                return
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_our_time_is_nigh")):
                return
            once_key = str(sr.get("enhancement_our_time_is_nigh_once_key", "our_time_is_nigh") or "our_time_is_nigh").strip().lower()
            has_used = getattr(root, "has_used_unit_once_per_battle", None)
            if callable(has_used) and bool(has_used(once_key)):
                return
            mark_used = getattr(root, "mark_unit_once_per_battle_used", None)
            if callable(mark_used):
                mark_used(
                    once_key,
                    ability_name=str(ctx.get("ability_name", "") or "Our Time Is Nigh").strip() or "Our Time Is Nigh",
                )
            current_player = self.get_current_player()
            current_owner = str(getattr(current_player, "id", "") or "")
            try:
                turn = int(payload.get("turn", ctx.get("turn", getattr(self, "turn", 0))) or 0)
            except Exception:
                turn = int(getattr(self, "turn", 0) or 0)
            phase_name = str(payload.get("phase", ctx.get("phase", "")) or "").strip().upper()
            if not phase_name:
                phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() or "CHARGE_PHASE"
            turn_owner_id = str(payload.get("turn_owner_id", ctx.get("turn_owner_id", "")) or "").strip()
            if not turn_owner_id:
                turn_owner_id = current_owner
            sr["enhancement_our_time_is_nigh_active"] = True
            sr["enhancement_our_time_is_nigh_turn"] = int(turn or 0)
            sr["enhancement_our_time_is_nigh_turn_owner"] = turn_owner_id
            sr["enhancement_our_time_is_nigh_phase"] = phase_name
            sr["enhancement_our_time_is_nigh_source"] = (
                str(ctx.get("ability_name", "") or "Our Time Is Nigh").strip() or "Our Time Is Nigh"
            )
            root.special_rules = sr
            return

        if ability_key == "shadow_in_the_warp":
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            army = player.get_army()
            mgr = getattr(army, "shadow_in_the_warp", None) if army is not None else None
            if mgr is None:
                return
            if not mgr.can_use_now(game=self, player=player):
                return
            mgr.activate(game=self, player=player)
            return

        if ability_key == "waaagh":
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            army = player.get_army()
            mgr = getattr(army, "waaagh", None) if army is not None else None
            if mgr is None:
                return
            if not mgr.can_call_now(game=self, player=player):
                return
            mgr.call_waaagh(game=self, player=player)
            return

        if ability_key == "seized_opportunity":
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            used_this_phase = getattr(player, "_ability_used_this_phase", None)
            if callable(used_this_phase) and bool(used_this_phase("seized_opportunity")):
                return
            army = player.get_army()
            pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
            if pe is None:
                return
            delta = int(getattr(pe, "add_yield_points", lambda _a, game=None: 0)(1, game=self) or 0)
            if delta <= 0:
                return
            mark_used = getattr(player, "_mark_ability_used_phase", None)
            if callable(mark_used):
                mark_used("seized_opportunity")
            event_system = getattr(self, "event_system", None)
            if event_system is not None:
                event_system.publish(
                    "prioritised_efficiency_updated",
                    player=player,
                    game=self,
                    delta=int(delta or 0),
                    mode=getattr(pe, "mode", None),
                    yield_points=int(getattr(pe, "yield_points", 0) or 0),
                    reason="Seized Opportunity",
                )
            return

        if ability_key == "geomantic_hunters":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or ctx.get("source_unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                return
            if not bool(getattr(root, "has_geomantic_hunters", lambda: False)()):
                return
            if not bool(getattr(root, "can_use_geomantic_hunters", lambda: False)()):
                return
            mark_used = getattr(root, "mark_geomantic_hunters_used", None)
            if callable(mark_used):
                mark_used()
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                try:
                    player = root.get_parent_army().player
                except Exception:
                    player = None
            owner_id = str(getattr(player, "id", "") or "")
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            turn = int(getattr(self, "turn", 0) or 0)
            phase_key = f"{turn}:{phase_name}:{owner_id}"
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["geomantic_hunters_active"] = True
            sr["geomantic_hunters_phase_key"] = phase_key
            sr["geomantic_hunters_owner"] = owner_id
            sr["geomantic_hunters_source"] = str(ctx.get("ability_name", "") or "Geomantic Hunters").strip() or "Geomantic Hunters"
            root.special_rules = sr
            return

        if ability_key == "resource_transmutation":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or ctx.get("source_unit_id") or "")
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not unit_id or not model_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                return
            if not bool(getattr(root, "has_resource_transmutation", lambda: False)()):
                return
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                try:
                    player = root.get_parent_army().player
                except Exception:
                    player = None
            if player is None:
                return
            army = player.get_army()
            pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
            if pe is None:
                return
            owner_id = str(getattr(player, "id", "") or "")
            turn = int(getattr(self, "turn", 0) or 0)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            try:
                if (
                    str(sr.get("resource_transmutation_used_turn_owner", "") or "") == owner_id
                    and int(sr.get("resource_transmutation_used_turn", 0) or 0) == int(turn or 0)
                ):
                    return
            except Exception:
                pass
            if not bool(getattr(pe, "spend_yield_points", lambda _a: False)(1)):
                return
            sr["resource_transmutation_active_model_id"] = model_id
            sr["resource_transmutation_owner"] = owner_id
            sr["resource_transmutation_turn"] = int(turn or 0)
            sr["resource_transmutation_source"] = str(ctx.get("ability_name", "") or "Resource Transmutation").strip() or "Resource Transmutation"
            sr["resource_transmutation_used_turn_owner"] = owner_id
            sr["resource_transmutation_used_turn"] = int(turn or 0)
            sr.pop("resource_transmutation_gain_resolved_turn_owner", None)
            sr.pop("resource_transmutation_gain_resolved_turn", None)
            root.special_rules = sr
            event_system = getattr(self, "event_system", None)
            if event_system is not None:
                event_system.publish(
                    "prioritised_efficiency_updated",
                    player=player,
                    game=self,
                    delta=-1,
                    mode=getattr(pe, "mode", None),
                    yield_points=int(getattr(pe, "yield_points", 0) or 0),
                    reason="Resource Transmutation",
                )
            return

        if ability_key == "optimal_application":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or ctx.get("source_unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                return
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                try:
                    player = root.get_parent_army().player
                except Exception:
                    player = None
            if player is None:
                return
            army = player.get_army()
            pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
            if pe is None:
                return
            detachment_mgr = getattr(army, "leagues_of_votann_detachments", None) if army is not None else None
            eligible_fn = (
                getattr(detachment_mgr, "optimal_application_shooting_unit_eligible", None)
                if detachment_mgr is not None
                else None
            )
            if not callable(eligible_fn) or not bool(eligible_fn(root)):
                return
            if not bool(getattr(pe, "spend_yield_points", lambda _a, game=None: False)(1, game=self)):
                return

            owner_id = str(getattr(player, "id", "") or "")
            turn = int(getattr(self, "turn", 0) or 0)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["optimal_application_active"] = True
            sr["optimal_application_turn_owner"] = owner_id
            sr["optimal_application_turn"] = int(turn or 0)
            sr["optimal_application_expires_phase"] = "SHOOTING_PHASE"
            sr["optimal_application_source"] = str(ctx.get("ability_name", "") or "Optimal Application").strip() or "Optimal Application"
            root.special_rules = sr

            event_system = getattr(self, "event_system", None)
            if event_system is not None:
                event_system.publish(
                    "prioritised_efficiency_updated",
                    player=player,
                    game=self,
                    delta=-1,
                    mode=getattr(pe, "mode", None),
                    yield_points=int(getattr(pe, "yield_points", 0) or 0),
                    reason="Optimal Application",
                )
            return

        if ability_key == "ruthless_reinvestment":
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            army = player.get_army()
            pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
            if pe is None:
                return
            detachment_mgr = getattr(army, "leagues_of_votann_detachments", None) if army is not None else None
            can_toggle_fn = getattr(detachment_mgr, "ruthless_reinvestment_can_toggle", None) if detachment_mgr is not None else None
            if not callable(can_toggle_fn) or not bool(can_toggle_fn(game=self, player=player)):
                return
            try:
                cost = int(payload.get("cost", ctx.get("cost", 3)) or 3)
            except Exception:
                cost = 3
            cost = max(0, int(cost or 0))
            if cost <= 0:
                return
            if not bool(getattr(pe, "spend_yield_points", lambda _a, game=None: False)(cost, game=self)):
                return
            toggled = bool(getattr(pe, "toggle_mode", lambda game=None: False)(game=self))
            if not toggled:
                return
            mark_fn = getattr(detachment_mgr, "mark_ruthless_reinvestment_toggle_used", None) if detachment_mgr is not None else None
            if callable(mark_fn):
                mark_fn(game=self, player=player)
            event_system = getattr(self, "event_system", None)
            if event_system is not None:
                event_system.publish(
                    "prioritised_efficiency_updated",
                    player=player,
                    game=self,
                    delta=-int(cost),
                    mode=getattr(pe, "mode", None),
                    yield_points=int(getattr(pe, "yield_points", 0) or 0),
                    reason="Ruthless Reinvestment",
                )
            return

        if ability_key == "oathbound_speculator":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or ctx.get("source_unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                return
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_oathbound_speculator"):
                return
            bearer = getattr(root, "_get_enhancement_bearer_model", lambda: None)()
            if bearer is None:
                return
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                try:
                    player = root.get_parent_army().player
                except Exception:
                    player = None
            if player is None:
                return
            army = player.get_army()
            pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
            if pe is None:
                return
            try:
                cost = int(payload.get("cost", ctx.get("cost", 3)) or 3)
            except Exception:
                cost = 3
            cost = max(0, int(cost or 0))
            if cost <= 0:
                return
            if not bool(getattr(pe, "spend_yield_points", lambda _a, game=None: False)(cost, game=self)):
                return
            owner_id = str(getattr(player, "id", "") or "")
            turn = int(getattr(self, "turn", 0) or 0)
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            sr["enhancement_oathbound_speculator_wound_bonus_active"] = True
            sr["enhancement_oathbound_speculator_wound_bonus"] = 1
            sr["enhancement_oathbound_speculator_phase_key"] = f"{turn}:{phase_name}:{owner_id}"
            sr["enhancement_oathbound_speculator_turn_owner"] = owner_id
            sr["enhancement_oathbound_speculator_turn"] = int(turn or 0)
            sr["enhancement_oathbound_speculator_expires_phase"] = phase_name
            sr["enhancement_oathbound_speculator_source"] = (
                str(ctx.get("ability_name", "") or "Oathbound Speculator").strip() or "Oathbound Speculator"
            )
            root.special_rules = sr
            event_system = getattr(self, "event_system", None)
            if event_system is not None:
                event_system.publish(
                    "prioritised_efficiency_updated",
                    player=player,
                    game=self,
                    delta=-int(cost),
                    mode=getattr(pe, "mode", None),
                    yield_points=int(getattr(pe, "yield_points", 0) or 0),
                    reason="Oathbound Speculator",
                )
            return

        if ability_key == "dead_reckoning":
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or ctx.get("source_unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                return
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_dead_reckoning"):
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
            bearer = getattr(root, "_get_enhancement_bearer_model", lambda: None)()
            if bearer is None:
                return
            army = player.get_army()
            pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
            if pe is None:
                return
            owner_id = str(getattr(player, "id", "") or "")
            turn_owner = str(ctx.get("turn_owner", "") or owner_id)
            try:
                turn = int(ctx.get("turn", 0) or getattr(self, "turn", 0) or 0)
            except Exception:
                turn = int(getattr(self, "turn", 0) or 0)
            try:
                if (
                    str(sr.get("dead_reckoning_resolved_turn_owner", "") or "") == turn_owner
                    and int(sr.get("dead_reckoning_resolved_turn", 0) or 0) == int(turn or 0)
                ):
                    return
            except Exception:
                pass
            spent_this_turn = bool(
                getattr(pe, "spent_yield_points_in_turn", lambda **_kwargs: False)(
                    game=self,
                    turn=int(turn or 0),
                    turn_owner_id=turn_owner,
                )
            )
            if spent_this_turn:
                return
            delta = int(getattr(pe, "add_yield_points", lambda _a, game=None: 0)(1, game=self) or 0)
            if delta <= 0:
                return
            sr["dead_reckoning_resolved_turn_owner"] = turn_owner
            sr["dead_reckoning_resolved_turn"] = int(turn or 0)
            root.special_rules = sr
            event_system = getattr(self, "event_system", None)
            if event_system is not None:
                event_system.publish(
                    "prioritised_efficiency_updated",
                    player=player,
                    game=self,
                    delta=int(delta or 0),
                    mode=getattr(pe, "mode", None),
                    yield_points=int(getattr(pe, "yield_points", 0) or 0),
                    reason="Dead Reckoning",
                )
            return

        if ability_key == "possessed_blade_fight":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or ctx.get("source_unit_id") or "")
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not unit_id or not model_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            model = self._resolve_model_by_id(model_id)
            if unit is None or model is None:
                return
            if not bool(getattr(model, "is_alive", True)):
                return
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_possessed_blade"):
                return
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
            if bearer_id and bearer_id != model_id:
                return
            get_mgr = getattr(self, "_get_emperors_children_manager", None)
            if callable(get_mgr):
                try:
                    army = unit.get_parent_army()
                except Exception:
                    army = None
                mgr = get_mgr(army)
                if mgr is None or not getattr(mgr, "is_carnival_of_excess", lambda: False)():
                    return
            selected_weapon = str(sr.get("enhancement_possessed_blade_weapon_name", "") or "").strip()
            if not selected_weapon:
                return
            weapon_name = str(payload.get("weapon_name") or ctx.get("weapon_name") or selected_weapon).strip()
            if weapon_name and hasattr(unit, "_weapon_name_matches"):
                if not unit._weapon_name_matches([selected_weapon], weapon_name):
                    return
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            if not phase_name:
                phase_name = "FIGHT_PHASE"
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                try:
                    player = unit.get_parent_army().player
                except Exception:
                    player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(self, "turn", 0) or 0)
            except Exception:
                turn = 0
            sr["enhancement_possessed_blade_fight_active"] = True
            sr["enhancement_possessed_blade_fight_turn"] = int(turn)
            sr["enhancement_possessed_blade_fight_owner"] = owner_id
            sr["enhancement_possessed_blade_fight_phase"] = phase_name
            sr["enhancement_possessed_blade_active_weapon_name"] = selected_weapon
            sr["enhancement_possessed_blade_active_model_id"] = model_id
            sr["enhancement_possessed_blade_source"] = (
                str(ctx.get("ability_name", "") or "Possessed Blade").strip() or "Possessed Blade"
            )
            unit.special_rules = sr
            return

        if ability_key == "furys_cage":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or ctx.get("source_unit_id") or "")
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not unit_id or not model_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            model = self._resolve_model_by_id(model_id)
            if unit is None or model is None:
                return
            if not bool(getattr(model, "is_alive", True)):
                return
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_furys_cage"):
                return
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
            if bearer_id and bearer_id != model_id:
                return
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            if not phase_name:
                phase_name = "FIGHT_PHASE"
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                try:
                    player = unit.get_parent_army().player
                except Exception:
                    player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(self, "turn", 0) or 0)
            except Exception:
                turn = 0

            mortal_roll = int(get_roll("D3") or 0)
            mortal_wounds = max(1, int(mortal_roll) + 1)
            applied_wounds = 0
            for _ in range(int(mortal_wounds)):
                if not bool(getattr(model, "is_alive", True)):
                    break
                model.take_damage(
                    1,
                    is_mortal=True,
                    weapon_profile=None,
                    game_map=getattr(self, "map", None),
                    damage_source="enhancement_furys_cage",
                )
                applied_wounds += 1

            ability_name = str(ctx.get("ability_name", "") or "Fury's Cage").strip() or "Fury's Cage"
            if player is not None:
                from ...utility.event_bus import append_action as _append_action, append_dice as _append_dice

                _append_dice(
                    player,
                    f"{ability_name}: D3+1 mortal wounds ({int(mortal_roll)}+1) -> {int(mortal_wounds)}.",
                )
                _append_action(
                    player,
                    f"{ability_name}: {getattr(model, 'name', 'Model')} suffers {int(applied_wounds)} mortal wounds.",
                )

            if bool(getattr(model, "is_alive", True)):
                sr["enhancement_furys_cage_active"] = True
                sr["enhancement_furys_cage_turn"] = int(turn or 0)
                sr["enhancement_furys_cage_turn_owner"] = owner_id
                sr["enhancement_furys_cage_expires_phase"] = phase_name
                sr["enhancement_furys_cage_active_model_id"] = model_id
                sr["enhancement_furys_cage_source"] = ability_name
            else:
                for key in (
                    "enhancement_furys_cage_active",
                    "enhancement_furys_cage_turn",
                    "enhancement_furys_cage_turn_owner",
                    "enhancement_furys_cage_expires_phase",
                    "enhancement_furys_cage_active_model_id",
                ):
                    sr.pop(key, None)
            unit.special_rules = sr
            return

        if ability_key == "possessed_lord":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            if getattr(model, "has_used_once_per_battle", lambda _k: False)("possessed_lord"):
                return
            if not getattr(model, "is_alive", True):
                return
            model.activate_possessed_lord()
            return

        if ability_key == "fight_phase_melee_ap_boost":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            key = str(payload.get("buff_key") or ctx.get("buff_key") or "fight_phase_melee_ap_boost").strip().lower()
            if not key:
                key = "fight_phase_melee_ap_boost"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(ctx.get("ability_name", "") or "Fight phase melee boost").strip()
            model.activate_fight_phase_melee_ap_boost(key=key, ability_name=ability_name)
            return

        if ability_key == "might_of_titan":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            key = str(
                payload.get("buff_key")
                or ctx.get("buff_key")
                or "fight_phase_melee_attacks_strength_boost"
            ).strip().lower()
            if not key:
                key = "fight_phase_melee_attacks_strength_boost"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(ctx.get("ability_name", "") or "Might of Titan").strip() or "Might of Titan"
            try:
                attacks_bonus = int(payload.get("attacks_bonus") or ctx.get("attacks_bonus") or 0)
            except Exception:
                attacks_bonus = 0
            try:
                strength_bonus = int(payload.get("strength_bonus") or ctx.get("strength_bonus") or 0)
            except Exception:
                strength_bonus = 0
            model.activate_fight_phase_melee_attacks_strength_boost(
                key=key,
                ability_name=ability_name,
                attacks_bonus=int(attacks_bonus),
                strength_bonus=int(strength_bonus),
            )
            return

        if ability_key == "thrilling_spectacle":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            key = str(
                payload.get("buff_key")
                or ctx.get("buff_key")
                or "fight_phase_melee_attacks_set_invuln"
            ).strip().lower()
            if not key:
                key = "fight_phase_melee_attacks_set_invuln"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(ctx.get("ability_name", "") or "Thrilling Spectacle").strip() or "Thrilling Spectacle"
            try:
                invuln = int(payload.get("invuln") or ctx.get("invuln") or 0)
            except Exception:
                invuln = 0
            try:
                attacks_value = int(payload.get("attacks_value") or ctx.get("attacks_value") or 0)
            except Exception:
                attacks_value = 0
            if invuln <= 0 or attacks_value <= 0:
                return
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            if not phase_name:
                phase_name = "FIGHT_PHASE"
            if hasattr(model, "set_temporary_invulnerable_save"):
                model.set_temporary_invulnerable_save(
                    key=key,
                    value=int(invuln),
                    source=ability_name,
                    expires_phase=phase_name,
                )
            melee_weapon_names: list[str] = []
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                try:
                    is_melee = bool(getattr(wargear, "is_melee", lambda: False)())
                except Exception:
                    is_melee = False
                if not is_melee:
                    continue
                name = str(getattr(wargear, "name", "") or "").strip()
                if name:
                    melee_weapon_names.append(name)
            if melee_weapon_names and hasattr(model, "set_temporary_weapon_attacks_override"):
                for idx, weapon_name in enumerate(sorted(set(melee_weapon_names), key=lambda n: str(n).lower())):
                    model.set_temporary_weapon_attacks_override(
                        key=f"{key}:weapon:{idx}",
                        weapon_name=str(weapon_name),
                        attacks_value=int(attacks_value),
                        source=ability_name,
                        expires_phase=phase_name,
                    )
            model.mark_used_once_per_battle(key, ability_name=ability_name, source="datasheet")
            return

        if ability_key == "chance_for_glory":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            key = str(payload.get("buff_key") or ctx.get("buff_key") or "fight_phase_melee_full_boost").strip().lower()
            if not key:
                key = "fight_phase_melee_full_boost"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(ctx.get("ability_name", "") or "Chance for Glory").strip()
            try:
                bonus = int(payload.get("bonus") or ctx.get("bonus") or 1)
            except Exception:
                bonus = 1
            model.activate_fight_phase_melee_full_characteristic_boost(
                key=key,
                ability_name=ability_name,
                bonus=int(bonus),
            )
            return

        if ability_key == "malefic_destruction":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            key = str(payload.get("buff_key") or ctx.get("buff_key") or "fight_phase_hellforged_attacks").strip().lower()
            if not key:
                key = "fight_phase_hellforged_attacks"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(ctx.get("ability_name", "") or "Malefic Destruction").strip()
            weapon_name = str(payload.get("weapon_name") or ctx.get("weapon_name") or "hellforged").strip() or "hellforged"
            try:
                attacks_bonus = int(payload.get("attacks_bonus") or ctx.get("attacks_bonus") or 0)
            except Exception:
                attacks_bonus = 0
            model.activate_fight_phase_hellforged_attacks_bonus(
                key=key,
                ability_name=ability_name,
                weapon_name=weapon_name,
                attacks_bonus=int(attacks_bonus or 0),
            )
            return

        if ability_key == "sacrificial_dagger":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None or not getattr(model, "is_alive", True):
                return
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            unit = self._resolve_unit_by_id(unit_id) if unit_id else getattr(model, "parent_unit", None)
            if unit is None:
                return
            ability_name = str(ctx.get("ability_name", "") or "Sacrificial Dagger").strip() or "Sacrificial Dagger"
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            if not phase_name:
                phase_name = "FIGHT_PHASE"
            # Apply mortal wound to the bearer's unit.
            if hasattr(unit, "_apply_mortal_wounds_to_unit"):
                unit._apply_mortal_wounds_to_unit(unit, 1, game_map=getattr(self, "map", None))
            # Apply temporary Psychic hit/wound bonuses to the model.
            if hasattr(model, "set_temporary_psychic_attack_bonus"):
                model.set_temporary_psychic_attack_bonus(
                    key="sacrificial_dagger",
                    hit_bonus=1,
                    wound_bonus=1,
                    source=ability_name,
                    expires_phase=phase_name,
                )
            return

        if ability_key in ("sacrificial_blessing", "twisted_sorceries"):
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None or not getattr(model, "is_alive", True):
                return
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            unit = self._resolve_unit_by_id(unit_id) if unit_id else getattr(model, "parent_unit", None)
            if unit is None:
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                return
            if ability_key == "twisted_sorceries":
                once_key = str(payload.get("buff_key") or ctx.get("buff_key") or "twisted_sorceries").strip().lower()
                if not once_key:
                    once_key = "twisted_sorceries"
                if getattr(model, "has_used_once_per_battle", lambda _k: False)(once_key):
                    return
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            if not phase_name:
                phase_name = "FIGHT_PHASE"
            ability_name = str(
                ctx.get("ability_name", "")
                or ("Sacrificial Blessing" if ability_key == "sacrificial_blessing" else "Twisted Sorceries")
            ).strip() or ("Sacrificial Blessing" if ability_key == "sacrificial_blessing" else "Twisted Sorceries")

            def _destroy_one_bodyguard_model() -> bool:
                try:
                    models = list(root._get_bodyguard_support_models() or [])
                except Exception:
                    models = list(getattr(root, "models", []) or [])
                alive = [m for m in models if getattr(m, "is_alive", False)]
                if not alive:
                    return False
                try:
                    alive.sort(key=lambda m: str(get_entity_id(m) or ""))
                except Exception:
                    pass
                picked = alive[0]
                die_fn = getattr(picked, "die", None)
                if callable(die_fn):
                    die_fn(game_map=getattr(self, "map", None))
                    return True
                return False

            def _psychic_weapon_names() -> list[str]:
                names: list[str] = []
                for wg in list(getattr(model, "wargear", []) or []):
                    if wg is None:
                        continue
                    try:
                        profiles = list((getattr(wg, "profiles", {}) or {}).values())
                    except Exception:
                        profiles = []
                    has_psychic = False
                    for profile in profiles:
                        if profile is None:
                            continue
                        try:
                            if bool(getattr(profile, "is_psychic", lambda: False)()):
                                has_psychic = True
                                break
                        except Exception:
                            continue
                    if has_psychic:
                        name = str(getattr(wg, "name", "") or "").strip()
                        if name and name not in names:
                            names.append(name)
                return names

            attacks_bonus = 0
            strength_bonus = 0
            if ability_key == "sacrificial_blessing":
                if not _destroy_one_bodyguard_model():
                    return
                try:
                    attacks_bonus = int(get_roll("D3") or 0)
                except Exception:
                    attacks_bonus = 0
                try:
                    strength_bonus = int(get_roll("D3") or 0)
                except Exception:
                    strength_bonus = 0
            else:
                attacks_bonus = 3
                strength_bonus = 3
            if attacks_bonus <= 0 and strength_bonus <= 0:
                return

            weapon_names = _psychic_weapon_names()
            if not weapon_names:
                return
            for idx, weapon_name in enumerate(weapon_names):
                if not hasattr(model, "set_temporary_weapon_bonus"):
                    break
                model.set_temporary_weapon_bonus(
                    key=f"{ability_key}:{idx}:{model_id}",
                    weapon_name=weapon_name,
                    attacks_bonus=int(attacks_bonus or 0),
                    strength_bonus=int(strength_bonus or 0),
                    source=ability_name,
                    expires_phase=phase_name,
                )
            if ability_key == "twisted_sorceries":
                model.mark_used_once_per_battle(
                    str(payload.get("buff_key") or ctx.get("buff_key") or "twisted_sorceries").strip().lower() or "twisted_sorceries",
                    ability_name=ability_name,
                    source="datasheet",
                )
            return

        if ability_key == "start_any_phase_damage_set_one":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            key = str(payload.get("buff_key") or ctx.get("buff_key") or "start_any_phase_damage_set_one").strip().lower()
            if not key:
                key = "start_any_phase_damage_set_one"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(ctx.get("ability_name", "") or "Start of phase damage set to 1").strip()
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            if not phase_name:
                phase_name = "FIGHT_PHASE"
            if hasattr(model, "set_temporary_damage_taken_override"):
                model.set_temporary_damage_taken_override(
                    key=key,
                    value=1,
                    source=ability_name,
                    expires_phase=phase_name,
                )
            model.mark_used_once_per_battle(key, ability_name=ability_name, source="datasheet")
            return

        if ability_key == "start_any_phase_invulnerable_save":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            key = str(payload.get("buff_key") or ctx.get("buff_key") or "start_any_phase_invulnerable_save").strip().lower()
            if not key:
                key = "start_any_phase_invulnerable_save"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(ctx.get("ability_name", "") or "Start of phase invulnerable save").strip()
            try:
                invuln = int(payload.get("invuln") or ctx.get("invuln") or 0)
            except Exception:
                invuln = 0
            if invuln <= 0:
                return
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            if not phase_name:
                phase_name = "FIGHT_PHASE"
            apply_to_unit = bool(payload.get("apply_to_unit", ctx.get("apply_to_unit", False)))
            if apply_to_unit:
                unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
                source_unit = self._resolve_unit_by_id(unit_id) if unit_id else None
                if source_unit is None:
                    source_unit = getattr(model, "parent_unit", None)
                get_root = getattr(source_unit, "get_attached_unit_root", None) if source_unit is not None else None
                root = get_root() if callable(get_root) else source_unit
                if root is None:
                    return
                get_models = getattr(root, "get_attached_unit_models", None)
                target_models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
                effect_key = f"{key}:{model_id}" if model_id else key
                for target_model in list(target_models or []):
                    if target_model is None or not getattr(target_model, "is_alive", True):
                        continue
                    if hasattr(target_model, "set_temporary_invulnerable_save"):
                        target_model.set_temporary_invulnerable_save(
                            key=effect_key,
                            value=int(invuln),
                            source=ability_name,
                            expires_phase=phase_name,
                        )
            elif hasattr(model, "set_temporary_invulnerable_save"):
                model.set_temporary_invulnerable_save(
                    key=key,
                    value=int(invuln),
                    source=ability_name,
                    expires_phase=phase_name,
                )
            model.mark_used_once_per_battle(key, ability_name=ability_name, source="datasheet")
            return

        if ability_key == "start_any_phase_fnp":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                return
            try:
                if not getattr(root, "deployed", True):
                    return
                if root.is_in_reserves() or root.is_embarked:
                    return
            except Exception:
                pass
            ability_name = str(ctx.get("ability_name", "") or "Start of phase FNP").strip()
            ability_key = str(payload.get("ability_key") or ctx.get("ability_key") or "start_any_phase_fnp").strip().lower()
            if not ability_key:
                ability_key = "start_any_phase_fnp"
            if root.has_used_unit_once_per_battle(ability_key):
                return
            try:
                fnp_val = int(ctx.get("fnp_value", 0) or 0)
            except Exception:
                fnp_val = 0
            if fnp_val <= 0:
                return
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            if not phase_name:
                phase_name = "FIGHT_PHASE"
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            for m in list(models or []):
                if not getattr(m, "is_alive", False):
                    continue
                if hasattr(m, "set_temporary_fnp"):
                    m.set_temporary_fnp(
                        key=f"{ability_key}:{get_entity_id(m)}",
                        value=fnp_val,
                        source=ability_name,
                        expires_phase=phase_name,
                    )
            root.mark_unit_once_per_battle_used(ability_key, ability_name=ability_name)
            return

        if ability_key == "dark_ritual":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                return
            try:
                if not getattr(root, "deployed", True):
                    return
                if root.is_in_reserves() or root.is_embarked:
                    return
            except Exception:
                pass
            ability_name = str(ctx.get("ability_name", "") or "Dark Ritual").strip() or "Dark Ritual"
            ability_key = str(payload.get("ability_key") or ctx.get("ability_key") or "dark_ritual").strip().lower()
            if not ability_key:
                ability_key = "dark_ritual"
            if root.has_used_unit_once_per_battle(ability_key):
                return
            if not root._unit_contains_model_with_keyword("CULT DEMAGOGUE"):
                return
            try:
                rule = root.get_dark_ritual_rule()
            except Exception:
                rule = None
            if not rule:
                return
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            if not phase_name:
                phase_name = str(ctx.get("phase", "") or "").strip().upper()
            if phase_name and phase_name != "COMMAND_PHASE":
                return
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["dark_ritual_active"] = True
            sr["dark_ritual_turn_owner"] = str(getattr(getattr(self, "get_current_player", lambda: None)(), "id", "") or "")
            sr["dark_ritual_turn"] = int(getattr(self, "turn", 0) or 0)
            sr["dark_ritual_expires_phase"] = "FIGHT_PHASE"
            sr["dark_ritual_hit_bonus"] = int(sr.get("dark_ritual_hit_bonus", 1) or 1)
            sr["dark_ritual_wound_bonus"] = int(sr.get("dark_ritual_wound_bonus", 1) or 1)
            sr["dark_ritual_charge_after_advance"] = True
            sr["dark_ritual_source"] = ability_name
            root.special_rules = sr
            root.mark_unit_once_per_battle_used(ability_key, ability_name=ability_name)
            try:
                self._log_action(
                    f"{getattr(root, 'name', 'Unit')} uses {ability_name} (charge after Advance; +1 Hit/Wound)."
                )
            except Exception:
                pass
            return

        if ability_key == "sweeping_advance":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not unit_id or not model_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            model = self._resolve_model_by_id(model_id)
            if unit is None or model is None:
                return
            if not unit.is_alive() or not getattr(unit, "deployed", True):
                return
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    return
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                    return
            except Exception:
                return
            key = str(payload.get("ability_key") or ctx.get("ability_key") or "sweeping_advance").strip().lower()
            if not key:
                key = "sweeping_advance"
            try:
                if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                    return
            except Exception:
                return
            ability_name = str(ctx.get("ability_name", "") or "Sweeping Advance").strip() or "Sweeping Advance"

            engaged = False
            try:
                enemies = list(getattr(self.map, "get_enemy_units", lambda _u: [])(root) or [])
            except Exception:
                enemies = []
            for enemy in list(enemies or []):
                if enemy is None or not enemy.is_alive():
                    continue
                try:
                    if self.map.is_within_engagement_range(root, enemy):
                        engaged = True
                        break
                except Exception:
                    continue

            movement_type = "fall_back" if engaged else "move"
            try:
                max_distance = int(root.get_effective_model_characteristic(model, "movement", game_map=self.map) or 0)
            except Exception:
                max_distance = 0
            if max_distance <= 0:
                try:
                    max_distance = int(getattr(root, "movement", 0) or 0)
                except Exception:
                    max_distance = 0
            if max_distance <= 0:
                return

            model.mark_used_once_per_battle(key, ability_name=ability_name, source="datasheet")
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            self._queue_reactive_move_movement_decision(
                player=player,
                unit=root,
                max_distance=max_distance,
                kind="sweeping_advance",
                movement_type=movement_type,
                source=ability_name,
                allow_skip=False,
            )
            return

        if ability_key == "movement_phase_move_weapon_bonus":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            key = str(payload.get("buff_key") or ctx.get("buff_key") or "movement_phase_normal_move_bonus").strip().lower()
            if not key:
                key = "movement_phase_normal_move_bonus"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(payload.get("ability_name") or ctx.get("ability_name") or "Movement phase normal move boost").strip()
            move_bonus_dice = str(payload.get("move_bonus_dice") or ctx.get("move_bonus_dice") or "")
            try:
                move_bonus_flat = int(payload.get("move_bonus_flat") or ctx.get("move_bonus_flat") or 0)
            except Exception:
                move_bonus_flat = 0
            weapon_name = str(payload.get("weapon_name") or ctx.get("weapon_name") or "")
            try:
                attacks_bonus = int(payload.get("attacks_bonus") or ctx.get("attacks_bonus") or 0)
            except Exception:
                attacks_bonus = 0
            model.activate_movement_phase_move_weapon_bonus(
                key=key,
                ability_name=ability_name,
                move_bonus_dice=move_bonus_dice,
                move_bonus_flat=int(move_bonus_flat),
                weapon_name=weapon_name,
                attacks_bonus=attacks_bonus,
            )
            return

        if ability_key == "hand_of_asuryan":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            if getattr(model, "has_used_once_per_battle", lambda _k: False)("hand_of_asuryan"):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(payload.get("ability_name") or ctx.get("ability_name") or "Hand of Asuryan").strip()
            weapon_name = str(payload.get("weapon_name") or ctx.get("weapon_name") or "Bloody Twins").strip()
            model.activate_hand_of_asuryan(
                key="hand_of_asuryan",
                ability_name=ability_name,
                weapon_name=weapon_name,
            )
            return

        if ability_key == "shieldbreaker":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            unit = getattr(model, "parent_unit", None)
            try:
                root = unit.get_attached_unit_root() if unit is not None else None
            except Exception:
                root = unit
            if root is None:
                return
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            ia_mgr = getattr(army, "imperial_agents_detachments", None) if army is not None else None
            grant_fn = getattr(ia_mgr, "apply_extremis_sanction_extra_uses", None) if ia_mgr is not None else None
            if callable(grant_fn):
                grant_fn(root)
            key = str(payload.get("ability_key") or ctx.get("ability_key") or "shieldbreaker").strip().lower()
            if not key:
                key = "shieldbreaker"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            if not getattr(model, "is_alive", True):
                return
            ability_name = str(payload.get("ability_name") or ctx.get("ability_name") or "Shieldbreaker").strip()
            weapon_name = str(payload.get("weapon_name") or ctx.get("weapon_name") or "exitus rifle").strip()
            try:
                wound_bonus = int(payload.get("wound_bonus") or ctx.get("wound_bonus") or 1)
            except Exception:
                wound_bonus = 1
            model.activate_shieldbreaker(
                key=key,
                ability_name=ability_name,
                weapon_name=weapon_name,
                wound_bonus=int(wound_bonus),
            )
            return

        if ability_key == "lord_of_the_storm":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None or not getattr(model, "is_alive", True):
                return
            source_unit = getattr(model, "parent_unit", None)
            if source_unit is None:
                return
            try:
                source_root = source_unit.get_attached_unit_root()
            except Exception:
                source_root = source_unit
            if source_root is None:
                return
            if not bool(getattr(source_root, "is_alive", lambda: False)()):
                return
            if not bool(getattr(source_root, "deployed", False)):
                return
            try:
                if source_root.is_in_reserves() or source_root.is_embarked:
                    return
            except Exception:
                pass
            source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
            if source_army is None:
                return
            key = str(payload.get("ability_key") or ctx.get("ability_key") or "lord_of_the_storm").strip().lower()
            if not key:
                key = "lord_of_the_storm"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            try:
                range_value = float(payload.get("range") or ctx.get("range") or 0)
            except Exception:
                range_value = 0.0
            if range_value <= 0:
                return
            ability_name = str(payload.get("ability_name") or ctx.get("ability_name") or "Lord of the Storm").strip() or "Lord of the Storm"
            if not model.mark_used_once_per_battle(key, ability_name=ability_name, source="datasheet"):
                return

            from ...utility.event_bus import append_action, append_dice

            def _unit_sort_key(unit):
                try:
                    return str(get_entity_id(unit))
                except Exception:
                    return str(getattr(unit, "name", "") or "")

            owner = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            seen_targets: set[str] = set()
            for p in sorted(list(getattr(self, "players", []) or []), key=lambda x: str(getattr(x, "id", "") or "")):
                if p is None:
                    continue
                enemy_army = self._get_player_army(p)
                if enemy_army is None or enemy_army is source_army:
                    continue
                for candidate in sorted(list(getattr(enemy_army, "units", []) or []), key=_unit_sort_key):
                    if candidate is None:
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
                    if not bool(getattr(target_root, "is_alive", lambda: False)()):
                        continue
                    if not bool(getattr(target_root, "deployed", False)):
                        continue
                    try:
                        if target_root.is_in_reserves() or target_root.is_embarked:
                            continue
                    except Exception:
                        pass

                    try:
                        in_range = bool(source_root._model_within_range_of_unit(model, target_root, float(range_value)))
                    except Exception:
                        in_range = False
                    if not in_range:
                        continue

                    trigger_roll = int(get_roll("D6") or 0)
                    mortal_wounds = 0
                    if trigger_roll == 6:
                        mortal_wounds = int(get_roll("D3") or 0) + 3
                    elif trigger_roll >= 2:
                        mortal_wounds = int(get_roll("D3") or 0)
                    if mortal_wounds > 0 and hasattr(source_root, "_apply_mortal_wounds_to_unit"):
                        source_root._apply_mortal_wounds_to_unit(target_root, int(mortal_wounds), game_map=getattr(self, "map", None))

                    if owner is not None:
                        tname = str(getattr(target_root, "name", "Unit") or "Unit")
                        if trigger_roll == 6:
                            append_dice(owner, f"{ability_name}: {tname} roll {int(trigger_roll)} -> D3+3 = {int(mortal_wounds)} mortal wounds.")
                        elif trigger_roll >= 2:
                            append_dice(owner, f"{ability_name}: {tname} roll {int(trigger_roll)} -> D3 = {int(mortal_wounds)} mortal wounds.")
                        else:
                            append_dice(owner, f"{ability_name}: {tname} roll {int(trigger_roll)} -> no effect.")
                        if mortal_wounds > 0:
                            append_action(owner, f"{ability_name}: {tname} suffers {int(mortal_wounds)} mortal wounds.")
                        else:
                            append_action(owner, f"{ability_name}: {tname} suffers no mortal wounds.")
            return

        if ability_key == "soulless_horror":
            model_id = str(payload.get("model_id") or ctx.get("model_id") or "")
            if not model_id:
                return
            model = self._resolve_model_by_id(model_id)
            if model is None:
                return
            if not getattr(model, "is_alive", True):
                return
            source_unit = getattr(model, "parent_unit", None)
            if source_unit is None:
                return
            try:
                source_root = source_unit.get_attached_unit_root()
            except Exception:
                source_root = source_unit
            if source_root is None:
                return
            source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
            if source_army is None:
                return
            ia_mgr = getattr(source_army, "imperial_agents_detachments", None)
            grant_fn = getattr(ia_mgr, "apply_extremis_sanction_extra_uses", None) if ia_mgr is not None else None
            if callable(grant_fn):
                grant_fn(source_root)
            key = str(payload.get("ability_key") or ctx.get("ability_key") or "soulless_horror").strip().lower()
            if not key:
                key = "soulless_horror"
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return
            try:
                range_value = float(payload.get("range") or ctx.get("range") or 0)
            except Exception:
                range_value = 0.0
            try:
                test_penalty = int(payload.get("test_penalty") or ctx.get("test_penalty") or 0)
            except Exception:
                test_penalty = 0
            try:
                psyker_penalty = int(payload.get("psyker_test_penalty") or ctx.get("psyker_test_penalty") or 0)
            except Exception:
                psyker_penalty = 0
            if range_value <= 0 or test_penalty <= 0:
                return
            if psyker_penalty <= 0:
                psyker_penalty = int(test_penalty)
            ability_name = str(payload.get("ability_name") or ctx.get("ability_name") or "Soulless Horror").strip() or "Soulless Horror"
            if not model.mark_used_once_per_battle(key, ability_name=ability_name, source="datasheet"):
                return
            try:
                turn = int(getattr(self, "turn", 0) or 0)
            except Exception:
                turn = 0

            from ...utility.event_bus import append_action

            def _unit_sort_key(u):
                try:
                    return str(get_entity_id(u))
                except Exception:
                    return str(getattr(u, "name", "") or "")

            tested_targets: set[str] = set()
            for p in list(getattr(self, "players", []) or []):
                if p is None:
                    continue
                enemy_army = self._get_player_army(p)
                if enemy_army is None or enemy_army is source_army:
                    continue
                seen_roots: set[str] = set()
                for candidate in sorted(list(getattr(enemy_army, "units", []) or []), key=_unit_sort_key):
                    if candidate is None:
                        continue
                    try:
                        target_root = candidate.get_attached_unit_root()
                    except Exception:
                        target_root = candidate
                    if target_root is None:
                        continue
                    target_id = str(get_entity_id(target_root) or "")
                    if not target_id or target_id in seen_roots or target_id in tested_targets:
                        continue
                    seen_roots.add(target_id)
                    if not bool(getattr(target_root, "is_alive", lambda: False)()):
                        continue
                    if not bool(getattr(target_root, "deployed", False)):
                        continue
                    try:
                        if target_root.is_in_reserves() or target_root.is_embarked:
                            continue
                    except Exception:
                        pass
                    try:
                        in_range = bool(source_root._model_within_range_of_unit(model, target_root, float(range_value)))
                    except Exception:
                        in_range = False
                    if not in_range:
                        continue

                    modifier = int(test_penalty)
                    try:
                        if bool(target_root.has_any_keyword("PSYKER")):
                            modifier = max(int(modifier), int(psyker_penalty))
                    except Exception:
                        pass
                    if modifier > 0:
                        sr = getattr(target_root, "special_rules", None)
                        if not isinstance(sr, dict):
                            sr = {}
                        try:
                            existing = int(sr.get("battle_shock_test_modifier", 0) or 0)
                        except Exception:
                            existing = 0
                        sr["battle_shock_test_modifier"] = int(existing - int(modifier))
                        reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
                        reasons.append(f"{ability_name}: -{int(modifier)}")
                        sr["battle_shock_test_modifier_reasons"] = reasons
                        target_root.special_rules = sr

                    target_root.take_battle_shock_test(int(turn or 1))
                    tested_targets.add(target_id)
                    owner_id = str(getattr(request, "player_id", "") or getattr(result, "player_id", "") or "")
                    owner = self._resolve_player_by_id(owner_id) if owner_id else None
                    if owner is not None:
                        append_action(owner, f"{ability_name}: {getattr(target_root, 'name', 'Unit')} takes a Battle-shock test.")
            return

        if ability_key == "ammo_runt":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                return
            try:
                max_uses = int(payload.get("max_uses") or ctx.get("max_uses") or 1)
            except Exception:
                max_uses = 1
            max_uses = max(0, int(max_uses))
            if max_uses <= 0:
                return
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            try:
                used = int(sr.get("ammo_runt_uses", 0) or 0)
            except Exception:
                used = 0
            if used >= max_uses:
                return
            ability_name = str(payload.get("ability_name") or ctx.get("ability_name") or "Ammo Runt").strip() or "Ammo Runt"
            next_use = int(used + 1)

            def _iter_models() -> list:
                try:
                    return list(root.get_attached_unit_models() or [])
                except Exception:
                    return list(getattr(root, "models", []) or [])

            for model in sorted(_iter_models(), key=lambda m: str(get_entity_id(m) or "")):
                if model is None or not getattr(model, "is_alive", False):
                    continue
                set_fn = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if not callable(set_fn):
                    continue
                names: list[str] = []
                seen: set[str] = set()
                for wg in list(getattr(model, "wargear", []) or []):
                    if wg is None:
                        continue
                    try:
                        if not bool(getattr(wg, "is_ranged", lambda: False)()):
                            continue
                    except Exception:
                        continue
                    weapon_name = str(getattr(wg, "name", "") or "").strip()
                    if not weapon_name:
                        continue
                    key_norm = Unit._norm_wargear_name(weapon_name)
                    if not key_norm or key_norm in seen:
                        continue
                    seen.add(key_norm)
                    names.append(weapon_name)
                for idx, weapon_name in enumerate(names):
                    set_fn(
                        key=f"ammo_runt:{next_use}:{get_entity_id(model)}:{idx}",
                        weapon_name=weapon_name,
                        keywords=["LETHAL HITS"],
                        source=ability_name,
                        expires_phase="SHOOTING_PHASE",
                        attack_type="ranged",
                    )

            sr["ammo_runt_uses"] = int(next_use)
            try:
                prev_max = int(sr.get("ammo_runt_max_uses", 0) or 0)
            except Exception:
                prev_max = 0
            sr["ammo_runt_max_uses"] = max(int(max_uses), int(prev_max))
            sr["ammo_runt_source"] = ability_name
            root.special_rules = sr
            if next_use >= max_uses:
                mark_used = getattr(root, "mark_unit_once_per_battle_used", None)
                if callable(mark_used):
                    mark_used("ammo_runt", ability_name=ability_name)
            return

        if ability_key == "flickerjump":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            try:
                move_value = int(payload.get("move_value") or ctx.get("move_value") or 0)
            except Exception:
                move_value = 0
            if move_value <= 0:
                return
            ability_name = str(payload.get("ability_name") or ctx.get("ability_name") or "Flickerjump").strip()
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            owner_id = str(getattr(request, "player_id", "") or getattr(result, "player_id", "") or "")
            if not owner_id:
                try:
                    owner_id = str(unit.get_parent_army().player.id)
                except Exception:
                    owner_id = ""
            turn = int(getattr(self, "turn", 0) or 0)
            sr["flickerjump_move_set_value"] = int(move_value)
            sr["flickerjump_move_set_turn"] = int(turn)
            if owner_id:
                sr["flickerjump_move_set_turn_owner"] = owner_id
                sr["flickerjump_no_charge_turn_owner"] = owner_id
                sr["flickerjump_pending_uses_owner"] = owner_id
            sr["flickerjump_no_charge_turn"] = int(turn)
            sr["flickerjump_pending_uses_turn"] = int(turn)
            sr["flickerjump_pending_uses"] = int(sr.get("flickerjump_pending_uses", 0) or 0) + 1
            if ability_name:
                sr["flickerjump_source"] = ability_name
            unit.special_rules = sr
            return

        if ability_key == "sentinel_storm":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                return
            try:
                if not getattr(root, "deployed", True):
                    return
                if root.is_in_reserves() or root.is_embarked:
                    return
            except Exception:
                pass
            ability_name = str(ctx.get("ability_name", "") or "Shoot again").strip()
            ability_key = str(payload.get("ability_key") or ctx.get("ability_key") or "post_shoot_shoot_again").strip().lower()
            if not ability_key:
                ability_key = "post_shoot_shoot_again"
            if root.has_used_unit_once_per_battle(ability_key):
                return
            root.mark_unit_once_per_battle_used(ability_key, ability_name=ability_name)
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            self._queue_shoot_again_decision(player=player, unit=root, source=ability_name)
            return

        if ability_key == "daemonic_ordnance":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                return
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if sr.get("daemonic_ordnance_active"):
                exp = str(sr.get("daemonic_ordnance_expires_phase", "") or "").strip().upper()
                if not exp or exp == "SHOOTING_PHASE":
                    return
            source = str(payload.get("ability_name") or ctx.get("ability_name") or "Daemonic Ordnance").strip() or "Daemonic Ordnance"
            owner_id = str(getattr(request, "player_id", "") or getattr(result, "player_id", "") or "")
            try:
                turn = int(getattr(self, "turn", 0) or 0)
            except Exception:
                turn = 0
            sr["daemonic_ordnance_active"] = True
            sr["daemonic_ordnance_source"] = source
            sr["daemonic_ordnance_expires_phase"] = "SHOOTING_PHASE"
            sr["daemonic_ordnance_turn"] = int(turn or 0)
            if owner_id:
                sr["daemonic_ordnance_owner"] = owner_id
            root.special_rules = sr
            try:
                from ...utility.event_bus import append_action
                player = getattr(root.get_parent_army(), "player", None)
                if player is not None:
                    append_action(player, f"{source}: {getattr(root, 'name', 'Unit')} gains [DEVASTATING WOUNDS] and [HAZARDOUS] for ranged weapons this phase.")
            except Exception:
                pass
            return

        if ability_key == "warp_rift_firepower":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                return
            ability_once_key = str(payload.get("ability_key") or ctx.get("ability_key") or "warp_rift_firepower").strip().lower() or "warp_rift_firepower"
            if root.has_used_unit_once_per_battle(ability_once_key):
                return
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            source = str(payload.get("ability_name") or ctx.get("ability_name") or "Warp Rift Firepower").strip() or "Warp Rift Firepower"
            owner_id = str(getattr(request, "player_id", "") or getattr(result, "player_id", "") or "")
            try:
                turn = int(getattr(self, "turn", 0) or 0)
            except Exception:
                turn = 0
            sr["warp_rift_firepower_active"] = True
            sr["warp_rift_firepower_source"] = source
            sr["warp_rift_firepower_expires_phase"] = "SHOOTING_PHASE"
            sr["warp_rift_firepower_turn"] = int(turn or 0)
            if owner_id:
                sr["warp_rift_firepower_owner"] = owner_id
            root.special_rules = sr
            root.mark_unit_once_per_battle_used(ability_once_key, ability_name=source)
            try:
                from ...utility.event_bus import append_action
                player = getattr(root.get_parent_army(), "player", None)
                if player is not None:
                    append_action(player, f"{source}: {getattr(root, 'name', 'Unit')} gains [INDIRECT FIRE] for ranged weapons this phase.")
            except Exception:
                pass
            return

        if ability_key == "daemonic_patrons":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                return
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if sr.get("daemonic_patrons_active"):
                return
            try:
                threshold = int(payload.get("crit_wound_threshold") or ctx.get("crit_wound_threshold") or 3)
            except Exception:
                threshold = 3
            if threshold < 2 or threshold > 6:
                threshold = 3
            source = str(payload.get("ability_name") or ctx.get("ability_name") or "Daemonic Patrons").strip() or "Daemonic Patrons"
            sr["daemonic_patrons_active"] = True
            sr["daemonic_patrons_called"] = True
            sr["daemonic_patrons_expires_phase"] = "FIGHT_PHASE"
            sr["daemonic_patrons_crit_wound_threshold"] = int(threshold)
            sr["daemonic_patrons_source"] = source
            root.special_rules = sr
            try:
                from ...utility.event_bus import append_action
                player = getattr(root.get_parent_army(), "player", None)
                if player is not None:
                    append_action(
                        player,
                        f"{source}: {getattr(root, 'name', 'Unit')} called upon daemonic patrons.",
                    )
            except Exception:
                pass
            return

        if ability_key == "power_from_pain_command":
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if player is None:
                return
            army = player.get_army()
            mgr = getattr(army, "power_from_pain", None) if army is not None else None
            if mgr is None:
                return
            can_fn = getattr(mgr, "has_command_phase_action", None)
            if callable(can_fn) and not bool(can_fn(game=self, player=player)):
                return
            resolve_fn = getattr(mgr, "resolve_command_phase_action", None)
            if callable(resolve_fn):
                resolve_fn(game=self, player=player)
            return

        if ability_key == "power_from_pain_empower":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            trigger = str(payload.get("trigger") or ctx.get("trigger") or "")
            if not unit_id or not trigger:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            army = unit.get_parent_army()
            mgr = getattr(army, "power_from_pain", None) if army is not None else None
            if mgr is None:
                return
            mgr.empower_unit_for_trigger(unit, trigger=trigger, game=self)
            return

        if ability_key == "enhancement_fight_first":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            can_use = getattr(unit, "can_use_enhancement_fight_first", None)
            if callable(can_use) and not bool(can_use()):
                return
            activate = getattr(unit, "activate_enhancement_fight_first", None)
            if callable(activate):
                activate()
            return

        if ability_key == "umbralefic_crystal":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                return
            if not self._unit_on_battlefield_for_reposition(root):
                return
            if getattr(root, "has_used_unit_once_per_battle", lambda _k: False)("umbralefic_crystal"):
                return
            game_map = getattr(self, "map", None)
            if game_map is None:
                return
            for enemy in list(game_map.get_enemy_units(root) or []):
                if enemy is None:
                    continue
                try:
                    enemy_root = enemy.get_attached_unit_root()
                except Exception:
                    enemy_root = enemy
                if enemy_root is None:
                    continue
                try:
                    if not getattr(enemy_root, "is_alive", lambda: False)():
                        continue
                except Exception:
                    continue
                try:
                    if game_map.is_within_engagement_range(root, enemy_root):
                        return
                except Exception:
                    continue
            used = root.enter_strategic_reserves_midgame(
                game=self,
                game_map=game_map,
                reason="Umbralefic Crystal",
            )
            if not used:
                return
            player = getattr(root.get_parent_army(), "player", None)
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(self, "turn", 0) or 0)
            except Exception:
                turn = 0
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]
            for member in members:
                if member is None:
                    continue
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["umbralefic_crystal_temp_deep_strike"] = True
                sr["umbralefic_crystal_must_arrive_turn_owner"] = owner_id
                sr["umbralefic_crystal_must_arrive_turn"] = int(turn or 0)
                member.special_rules = sr
                cache = getattr(member, "_ability_cache", None)
                if isinstance(cache, dict):
                    cache.pop("deep_strike", None)
            ability_name = str(ctx.get("ability_name", "") or "Umbralefic Crystal").strip() or "Umbralefic Crystal"
            root.mark_unit_once_per_battle_used("umbralefic_crystal", ability_name=ability_name)
            try:
                from ...utility.event_bus import append_action
                if player is not None:
                    append_action(
                        player,
                        f"{ability_name}: {getattr(root, 'name', 'Unit')} placed into Strategic Reserves.",
                    )
            except Exception:
                pass
            return

        if ability_key == "opponent_turn_strategic_reserves":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            per_battle = bool(payload.get("once_per_battle")) or bool(ctx.get("once_per_battle"))
            per_battle_key = str(payload.get("ability_key") or ctx.get("ability_key") or "opponent_turn_strategic_reserves").strip().lower()
            used = unit.enter_strategic_reserves_midgame(
                game=self,
                game_map=getattr(self, "map", None),
                reason="end of opponent turn",
            )
            if used:
                from ...utility.event_bus import append_action
                player = getattr(unit.get_parent_army(), "player", None)
                ability_name = str(ctx.get("ability_name", "") or "Strategic Reserves")
                if player is not None:
                    append_action(
                        player,
                        f"{ability_name}: {getattr(unit, 'name', 'Unit')} placed into Strategic Reserves.",
                    )
                if per_battle and per_battle_key:
                    unit.mark_unit_once_per_battle_used(per_battle_key, ability_name=ability_name)
            return

        if ability_key == "fight_phase_destroyed_strategic_reserves":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            used = unit.enter_strategic_reserves_midgame(
                game=self,
                game_map=getattr(self, "map", None),
                reason="end of fight phase",
            )
            if used:
                from ...utility.event_bus import append_action
                player = getattr(unit.get_parent_army(), "player", None)
                ability_name = str(ctx.get("ability_name", "") or "Strategic Reserves")
                if player is not None:
                    append_action(
                        player,
                        f"{ability_name}: {getattr(unit, 'name', 'Unit')} placed into Strategic Reserves.",
                    )
            return

        if ability_key == "opponent_turn_destroyed_reposition":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            if not self._unit_on_battlefield_for_reposition(unit):
                return
            turn_owner_id = str(
                ctx.get("turn_owner_id")
                or getattr(getattr(self, "get_current_player", lambda: None)(), "id", "")
                or ""
            )
            if self._opponent_turn_destroyed_reposition_used(unit, turn_owner_id=turn_owner_id):
                return
            placement = ctx.get("placement_position")
            if isinstance(placement, (list, tuple)) and len(placement) >= 4:
                placement_pos = placement
            else:
                anchor = ctx.get("destroyed_position")
                placement_pos = self._find_closest_valid_reposition_position(
                    unit,
                    anchor,
                    game_map=getattr(self, "map", None),
                )
            if not placement_pos:
                return
            try:
                models = [m for m in list(getattr(unit, "models", []) or []) if getattr(m, "is_alive", True)]
            except Exception:
                models = []
            if len(models) != 1:
                return
            model = models[0]
            model.set_location(
                float(placement_pos[0]),
                float(placement_pos[1]),
                float(placement_pos[2]),
                float(placement_pos[3]),
            )
            unit.position = (float(placement_pos[0]), float(placement_pos[1]), float(placement_pos[2]))
            if getattr(self, "map", None) is not None and hasattr(self.map, "units"):
                if unit not in self.map.units:
                    self.map.units.append(unit)
            self._mark_opponent_turn_destroyed_reposition_used(unit, turn_owner_id=turn_owner_id)
            try:
                if hasattr(self, "event_system"):
                    self.event_system.publish(
                        "unit_set_up",
                        unit=unit,
                        set_up_as_reinforcements=False,
                    )
            except Exception:
                pass
            try:
                from ...utility.event_bus import append_action
                player = getattr(unit.get_parent_army(), "player", None)
                ability_name = str(ctx.get("ability_name", "") or "Reposition")
                if player is not None:
                    append_action(
                        player,
                        f"{ability_name}: {getattr(unit, 'name', 'Unit')} repositioned after a friendly unit was destroyed.",
                    )
            except Exception:
                pass
            return

        if ability_key == "cloudstrider":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                return
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            owner_id = str(getattr(request, "player_id", "") or getattr(result, "player_id", "") or "")
            if not owner_id:
                try:
                    owner_id = str(root.get_parent_army().player.id)
                except Exception:
                    owner_id = ""
            turn = int(getattr(self, "turn", 0) or 0)
            sr["cloudstrider_deep_strike_min_distance"] = 6.0
            sr["cloudstrider_choice_turn"] = int(turn)
            if owner_id:
                sr["cloudstrider_choice_turn_owner"] = owner_id
                sr["cloudstrider_no_charge_turn_owner"] = owner_id
            sr["cloudstrider_no_charge_turn"] = int(turn)
            source = str(ctx.get("ability_name", "") or "Cloudstrider").strip() or "Cloudstrider"
            sr["cloudstrider_source"] = source
            if "aetherstride" in source.lower():
                try:
                    model_id = ""
                    models = list(root.get_attached_unit_models() or [])
                    models = [m for m in models if getattr(m, "is_alive", False)]
                    if models:
                        models.sort(key=lambda m: str(get_entity_id(m) or ""))
                        model_id = str(get_entity_id(models[0]) or "")
                    sr["aetherstride_sustained_hits_d3_active"] = True
                    sr["aetherstride_sustained_hits_d3_turn"] = int(turn)
                    sr["aetherstride_sustained_hits_d3_owner"] = owner_id
                    sr["aetherstride_model_id"] = model_id
                    sr["aetherstride_source"] = source
                except Exception:
                    pass
            root.special_rules = sr
            try:
                from ...utility.event_bus import append_action
                player = getattr(root.get_parent_army(), "player", None)
                if player is not None:
                    append_action(
                        player,
                        f"{source}: {getattr(root, 'name', 'Unit')} may Deep Strike more than 6\" away (no charge).",
                    )
            except Exception:
                pass
            return

        if ability_key == "seductive_gambit":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["seductive_gambit_active"] = True
            sr["seductive_gambit_expires_phase"] = "FIGHT_PHASE"
            unit.special_rules = sr
            return

        if ability_key == "sensational_performance":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if sr.get("sensational_performance_active"):
                return
            sr["sensational_performance_active"] = True
            sr["sensational_performance_expires_phase"] = "FIGHT_PHASE"
            sr["sensational_performance_strength_bonus"] = 1
            sr["sensational_performance_ap_bonus"] = 1
            unit.special_rules = sr
            try:
                from ...utility.event_bus import append_action
                player = getattr(unit.get_parent_army(), "player", None)
                if player is not None:
                    append_action(
                        player,
                        f"Sensational Performance: {getattr(unit, 'name', 'Unit')} gains bonuses this Fight phase.",
                    )
            except Exception:
                pass
            return

        if ability_key == "cult_ambush":
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            army = unit.get_parent_army()
            mgr = getattr(army, "cult_ambush", None) if army is not None else None
            if mgr is None:
                return
            player = getattr(army, "player", None)
            mgr.handle_unit_destroyed(unit, game=self, player=player)
            return

        if ability_key in ("battle_focus_flitting_shadows", "battle_focus_sudden_strike", "battle_focus_fade_back"):
            unit_id = str(payload.get("unit_id") or ctx.get("unit_id") or "")
            if not unit_id:
                return
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None or not unit.is_alive():
                return
            army = unit.get_parent_army()
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            if mgr is None:
                return
            if ability_key == "battle_focus_flitting_shadows":
                mgr._apply_maneuver(unit, mgr.MANEUVER_FLITTING, self)
                return
            if ability_key == "battle_focus_sudden_strike":
                mgr._apply_maneuver(unit, mgr.MANEUVER_SUDDEN_STRIKE, self)
                return
            if ability_key == "battle_focus_fade_back":
                mgr._apply_reactive_move(unit, mgr.MANEUVER_FADE_BACK, self)
                return

    def _setup_reactive_can_shoot_target(self, unit, target_unit) -> bool:
        if unit is None or target_unit is None:
            return False
        if not unit.is_alive() or not target_unit.is_alive():
            return False
        game_map = getattr(self, "map", None)
        if game_map is None:
            return False
        if bool(getattr(getattr(unit, "round_state", None), "action_locked_until_turn_end", False)):
            return False
        if bool(getattr(unit, "_reserves_edge_touch_this_turn", False)) and bool(
            getattr(unit, "arrived_from_reserves_this_turn", False)
        ):
            return False
        for model in list(getattr(unit, "models", []) or []):
            if not getattr(model, "is_alive", True):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                if not wargear.is_ranged():
                    continue
                profiles = getattr(wargear, "profiles", {}) or {}
                for profile in list(profiles.values()):
                    if profile is None:
                        continue
                    validation = unit._validate_shooting_declaration(profile, target_unit, [model], game_map)
                    if bool(validation.get("valid", False)):
                        return True
        return False

    def _setup_reactive_available_actions(self, unit, target_unit) -> list[str]:
        actions: list[str] = []
        if unit is None or target_unit is None:
            return actions
        if self._setup_reactive_can_shoot_target(unit, target_unit):
            actions.append("shoot")
        if unit.can_declare_charge_against(target_unit, self, out_of_turn=True):
            actions.append("charge")
        return actions

    def _queue_setup_reactive_target_decision(
        self,
        *,
        player,
        unit,
        candidates: list,
        rule: dict | None,
    ) -> DecisionRequest | None:
        if player is None or unit is None:
            return None
        unit_id = maybe_entity_id(unit)
        if not unit_id:
            return None
        if not candidates:
            return None
        sorted_candidates = [c for c in candidates if c is not None]
        sorted_candidates.sort(key=lambda c: str(maybe_entity_id(c) or ""))
        source = str((rule or {}).get("source", "") or "Reactive Response").strip() or "Reactive Response"
        rng = int((rule or {}).get("range", 12) or 12)
        options = [DecisionOption.create("None", payload={"action": "skip"})]
        used_labels = set()
        for enemy in sorted_candidates:
            enemy_id = maybe_entity_id(enemy)
            if not enemy_id:
                continue
            label = str(getattr(enemy, "name", "") or "Enemy unit")
            base = label
            idx = 2
            while label in used_labels:
                label = f"{base} ({idx})"
                idx += 1
            used_labels.add(label)
            options.append(DecisionOption.create(label, payload={"unit_id": enemy_id}))
        ctx = {
            "setup_reactive_flow": True,
            "setup_reactive_source": source,
            "setup_reactive_range": int(rng),
            "setup_reactive_unit_id": unit_id,
            "unit_id": unit_id,
            "setup_reactive_candidate_ids": [maybe_entity_id(c) for c in sorted_candidates if maybe_entity_id(c)],
        }
        request = DecisionRequest.create(
            DECISION_SELECT_SETUP_REACTIVE_TARGET,
            f"{source}: Select enemy unit",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_setup_reactive_action_decision(
        self,
        *,
        player,
        unit,
        target_unit,
        actions: list[str],
        source: str | None,
    ) -> DecisionRequest | None:
        if player is None or unit is None or target_unit is None:
            return None
        if not actions:
            return None
        unit_id = maybe_entity_id(unit)
        target_id = maybe_entity_id(target_unit)
        if not unit_id or not target_id:
            return None
        opts = []
        if "shoot" in actions:
            opts.append(DecisionOption.create("Shoot", payload={"action": "shoot"}))
        if "charge" in actions:
            opts.append(DecisionOption.create("Charge", payload={"action": "charge"}))
        if not opts:
            return None
        source = str(source or "Reactive Response").strip() or "Reactive Response"
        ctx = {
            "setup_reactive_flow": True,
            "setup_reactive_source": source,
            "setup_reactive_unit_id": unit_id,
            "unit_id": unit_id,
            "target_unit_id": target_id,
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
            f"{source}: Choose action",
            player_id=getattr(player, "id", None),
            options=opts,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_setup_reactive_shooting_decision(
        self,
        *,
        player,
        unit,
        target_unit,
        source: str | None,
    ) -> DecisionRequest | None:
        if player is None or unit is None or target_unit is None:
            return None
        unit_id = maybe_entity_id(unit)
        target_id = maybe_entity_id(target_unit)
        if not unit_id or not target_id:
            return None
        options = [
            DecisionOption.create("Confirm", payload={"action": "confirm", "unit_id": unit_id}),
            DecisionOption.create("Skip", payload={"action": "skip", "unit_id": unit_id}),
        ]
        source = str(source or "Reactive Response").strip() or "Reactive Response"
        ctx = {
            "unit_id": unit_id,
            "out_of_phase": True,
            "force_target_unit_id": target_id,
            "setup_reactive_source": source,
        }
        request = DecisionRequest.create(
            DECISION_DECLARE_SHOTS,
            f"{source}: Declare shots for {getattr(unit, 'name', 'Unit')}",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _queue_shoot_again_decision(
        self,
        *,
        player,
        unit,
        source: str | None,
    ) -> DecisionRequest | None:
        """Queue a standard shooting declaration for a unit that can shoot again."""
        if player is None or unit is None:
            return None
        unit_id = maybe_entity_id(unit)
        if not unit_id:
            return None
        options = [
            DecisionOption.create("Confirm", payload={"action": "confirm", "unit_id": unit_id}),
            DecisionOption.create("Skip", payload={"action": "skip", "unit_id": unit_id}),
        ]
        source = str(source or "Shoot again").strip() or "Shoot again"
        ctx = {
            "unit_id": unit_id,
            "out_of_phase": True,
            "shoot_again_source": source,
        }
        request = DecisionRequest.create(
            DECISION_DECLARE_SHOTS,
            f"{source}: Declare shots for {getattr(unit, 'name', 'Unit')}",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)
        return request

    def _maybe_queue_setup_reactive_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if not bool(ctx.get("setup_reactive_flow", False)):
            return
        decision_type = str(getattr(request, "decision_type", "") or "")

        def _get_payload():
            for opt in list(getattr(request, "options", []) or []):
                if getattr(opt, "option_id", None) == getattr(result, "option_id", None):
                    return dict(getattr(opt, "payload", {}) or {})
            return {}

        def _is_skip(payload: dict) -> bool:
            if bool((getattr(result, "payload", {}) or {}).get("skipped", False)):
                return True
            if str((getattr(result, "payload", {}) or {}).get("action", "") or "") == "skip":
                return True
            return str(payload.get("action", "") or "") == "skip"

        if decision_type == DECISION_SELECT_SETUP_REACTIVE_TARGET:
            payload = _get_payload()
            if _is_skip(payload):
                unit_id = str(ctx.get("setup_reactive_unit_id") or ctx.get("unit_id") or "")
                unit = self._resolve_unit_by_id(unit_id)
                if unit is not None:
                    unit.clear_setup_reactive_shoot_or_charge_candidates(self)
                return
            target_id = str(payload.get("unit_id") or payload.get("target_unit_id") or "")
            unit_id = str(ctx.get("setup_reactive_unit_id") or ctx.get("unit_id") or "")
            unit = self._resolve_unit_by_id(unit_id)
            target_unit = self._resolve_unit_by_id(target_id)
            player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
            if unit is None or target_unit is None or player is None:
                return
            actions = self._setup_reactive_available_actions(unit, target_unit)
            if not actions:
                unit.clear_setup_reactive_shoot_or_charge_candidates(self)
                return
            source = str(ctx.get("setup_reactive_source", "") or "Reactive Response").strip() or "Reactive Response"
            self._queue_setup_reactive_action_decision(
                player=player,
                unit=unit,
                target_unit=target_unit,
                actions=actions,
                source=source,
            )
            return

        if decision_type == DECISION_CHOOSE_SETUP_REACTIVE_ACTION:
            payload = _get_payload()
            if _is_skip(payload):
                unit_id = str(ctx.get("setup_reactive_unit_id") or ctx.get("unit_id") or "")
                unit = self._resolve_unit_by_id(unit_id)
                if unit is not None:
                    unit.clear_setup_reactive_shoot_or_charge_candidates(self)
                return
            action = str(payload.get("action", "") or "")
            if action not in ("shoot", "charge"):
                return
            unit_id = str(ctx.get("setup_reactive_unit_id") or ctx.get("unit_id") or "")
            target_id = str(ctx.get("target_unit_id") or "")
            unit = self._resolve_unit_by_id(unit_id)
            target_unit = self._resolve_unit_by_id(target_id)
            if unit is None or target_unit is None:
                return
            unit.mark_setup_reactive_shoot_or_charge_used(self)
            unit.clear_setup_reactive_shoot_or_charge_candidates(self)
            source = str(ctx.get("setup_reactive_source", "") or "Reactive Response").strip() or "Reactive Response"
            if action == "shoot":
                if not self._setup_reactive_can_shoot_target(unit, target_unit):
                    return
                player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
                if player is None:
                    return
                self._queue_setup_reactive_shooting_decision(
                    player=player,
                    unit=unit,
                    target_unit=target_unit,
                    source=source,
                )
                return
            if action == "charge":
                if not unit.can_declare_charge_against(target_unit, self, out_of_turn=True):
                    return
                # Charge declaration/roll/move should be handled via decision flow (UI/headless).
                return
            return

    def _maybe_queue_reverberating_summons_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if not bool(ctx.get("engine_flow", False)):
            return
        decision_type = str(getattr(request, "decision_type", "") or "")

        def _get_payload():
            for opt in list(getattr(request, "options", []) or []):
                if getattr(opt, "option_id", None) == getattr(result, "option_id", None):
                    return dict(getattr(opt, "payload", {}) or {})
            return {}

        def _is_skip(payload: dict) -> bool:
            if bool((getattr(result, "payload", {}) or {}).get("skipped", False)):
                return True
            if str((getattr(result, "payload", {}) or {}).get("action", "") or "") == "skip":
                return True
            return str(payload.get("action", "") or "") == "skip"

        if decision_type == DECISION_SELECT_REVERBERATING_SUMMONS_UNIT:
            payload = _get_payload()
            if _is_skip(payload):
                return
            unit_id = str(payload.get("unit_id") or payload.get("unit") or "")
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            destroyed = list(getattr(unit, "models_lost", []) or [])
            if not destroyed:
                return
            from ..decisions import DecisionOption, DecisionRequest

            options = [DecisionOption.create("None", payload={"model_id": None, "action": "skip"})]
            for model in destroyed:
                options.append(
                    DecisionOption.create(
                        getattr(model, "name", "Model"),
                        payload={"model_id": get_entity_id(model)},
                    )
                )
            req = DecisionRequest.create(
                DECISION_ALLOCATE_DAMAGE,
                "Select destroyed Plaguebearer model to return.",
                player_id=getattr(request, "player_id", None),
                options=options,
                context={
                    "engine_flow": True,
                    "selection_kind": "reverberating_summons_return",
                    "unit_id": unit_id,
                    "ability_name": ctx.get("ability_name", "") or "Reverberating Summons",
                },
            )
            self.request_decision(req)
            return

        if decision_type == DECISION_ALLOCATE_DAMAGE:
            if str(ctx.get("selection_kind", "") or "") != "reverberating_summons_return":
                return
            payload = _get_payload()
            if _is_skip(payload):
                return
            unit_id = str(ctx.get("unit_id") or "")
            unit = self._resolve_unit_by_id(unit_id)
            if unit is None:
                return
            model_id = payload.get("model_id")
            if model_id in (None, ""):
                return
            model = self.entity_registry.get(str(model_id), kind="model")
            if model is None:
                return
            unit.return_destroyed_bodyguard_models(
                1,
                game_map=getattr(self, "map", None),
                chosen_models=[model],
            )
            return

    def _maybe_queue_bodyguard_return_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        if str(getattr(request, "decision_type", "") or "") != DECISION_ALLOCATE_DAMAGE:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("selection_kind", "") or "") != "bodyguard_return":
            return

        def _get_payload():
            for opt in list(getattr(request, "options", []) or []):
                if getattr(opt, "option_id", None) == getattr(result, "option_id", None):
                    return dict(getattr(opt, "payload", {}) or {})
            return {}

        def _is_skip(payload: dict) -> bool:
            if bool((getattr(result, "payload", {}) or {}).get("skipped", False)):
                return True
            if str((getattr(result, "payload", {}) or {}).get("action", "") or "") == "skip":
                return True
            if str(payload.get("action", "") or "") == "skip":
                return True
            return payload.get("model_id") in (None, "")

        payload = _get_payload()
        if _is_skip(payload):
            return
        model_id = payload.get("model_id")
        if model_id in (None, ""):
            return
        model = None
        registry = getattr(self, "entity_registry", None)
        if registry is not None:
            model = registry.get(str(model_id), kind="model")
        if model is None:
            for p in list(self.players or []):
                army = p.get_army()
                if army is None:
                    continue
                for unit in list(getattr(army, "units", []) or []):
                    for candidate in list(getattr(unit, "models_lost", []) or []):
                        if str(getattr(candidate, "_id", "")) == str(model_id):
                            model = candidate
                            break
                    if model is not None:
                        break
                if model is not None:
                    break
        if model is None:
            return

        leader_id = str(ctx.get("leader_unit_id", "") or "")
        bodyguard_id = str(ctx.get("bodyguard_unit_id", "") or ctx.get("unit_id", "") or "")
        leader = self._resolve_unit_by_id(leader_id) if leader_id else None
        bodyguard = self._resolve_unit_by_id(bodyguard_id) if bodyguard_id else None
        if leader is None and bodyguard is None:
            return
        caller = leader if leader is not None else bodyguard
        returned = caller.return_destroyed_bodyguard_models(
            1,
            game_map=getattr(self, "map", None),
            chosen_models=[model],
        )
        ability_name = str(ctx.get("ability_name", "") or "Bodyguard Return")
        if returned > 0:
            try:
                from ...utility.event_bus import append_action
                player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
                if player is not None and bodyguard is not None:
                    append_action(
                        player,
                        f"{ability_name}: returned {getattr(model, 'name', 'Model')} to {getattr(bodyguard, 'name', 'Unit')}.",
                    )
            except Exception:
                pass
        if returned <= 0:
            return

        remaining = int(ctx.get("remaining", 0) or 0)
        remaining = max(0, remaining - 1)
        if remaining <= 0:
            return
        if bodyguard is None:
            return
        if not list(getattr(bodyguard, "models_lost", []) or []):
            return
        self._queue_bodyguard_return_decision(
            player=self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None)),
            leader_unit=leader if leader is not None else caller,
            bodyguard_unit=bodyguard,
            ability={"name": ability_name},
            remaining=remaining,
            allowed_model_ids=list(ctx.get("allowed_model_ids") or []),
            allow_skip=bool(ctx.get("allow_skip", True)),
        )

    def _maybe_apply_choice_samples_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        if str(getattr(request, "decision_type", "") or "") != DECISION_ALLOCATE_DAMAGE:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("selection_kind", "") or "") != "choice_samples":
            return

        payload = self._decision_option_payload(request, result)
        action = str(payload.get("action", "") or "").strip().lower()
        if self._decision_is_skip(request, result) or action == "skip":
            return

        ability_name = str(ctx.get("ability_name", "") or "Choice Samples").strip() or "Choice Samples"
        unit_id = str(ctx.get("unit_id", "") or "")
        player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
        unit = self._resolve_unit_by_id(unit_id) if unit_id else None

        if action == "gain_cp":
            if player is None:
                return
            try:
                cp_gain = int(payload.get("cp_gain", ctx.get("cp_gain", 0)) or 0)
            except Exception:
                cp_gain = 0
            if cp_gain <= 0:
                return
            try:
                gained = int(player.gain_command_points(int(cp_gain), reason=ability_name) or 0)
            except Exception:
                gained = 0
            try:
                from ...utility.event_bus import append_action

                append_action(player, f"{ability_name}: gained {int(gained)}CP.")
            except Exception:
                pass
            return

        model_id = payload.get("model_id")
        if model_id in (None, ""):
            return
        model = self._resolve_model_by_id(str(model_id))
        if model is None or unit is None:
            return
        returned = unit.return_destroyed_bodyguard_models(
            1,
            game_map=getattr(self, "map", None),
            chosen_models=[model],
        )
        if returned <= 0:
            return
        try:
            from ...utility.event_bus import append_action

            if player is not None:
                append_action(
                    player,
                    f"{ability_name}: returned {getattr(model, 'name', 'Model')} to {getattr(unit, 'name', 'Unit')}.",
                )
        except Exception:
            pass

    def _maybe_apply_spirit_snare_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        if str(getattr(request, "decision_type", "") or "") != DECISION_ALLOCATE_DAMAGE:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("selection_kind", "") or "") != "spirit_snare_recipient":
            return
        payload = self._decision_option_payload(request, result)
        model_id = payload.get("model_id")
        if model_id in (None, ""):
            return
        model = self._resolve_model_by_id(str(model_id))
        if model is None:
            return
        destroyed_model = None
        destroyed_model_id = str(ctx.get("destroyed_model_id", "") or "")
        if destroyed_model_id:
            destroyed_model = self._resolve_model_by_id(destroyed_model_id)
        player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
        self._apply_spirit_snare_bonus_to_model(
            model=model,
            player=player,
            destroyed_model=destroyed_model,
            ability_name=str(ctx.get("ability_name", "") or "Spirit Snare"),
        )

    def _maybe_apply_mortal_wounds_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if not bool(ctx.get("engine_flow", False)):
            return
        kind = str(ctx.get("mortal_wounds_kind", "") or "").strip().lower()
        if kind not in ("charge_end", "move_over", "fight_phase_end", "bomb_squigs", "plunder", "floating_death"):
            return
        if self._decision_is_skip(request, result):
            return
        payload = self._decision_option_payload(request, result)
        target_id = payload.get("target_unit_id", payload.get("unit_id"))
        target_unit = self._resolve_unit_by_id(str(target_id or ""))
        if target_unit is None:
            return
        unit_id = str(ctx.get("unit_id", "") or "")
        unit = self._resolve_unit_by_id(unit_id)
        if unit is None:
            return
        spec = dict(ctx.get("spec", {}) or {})
        if kind == "charge_end":
            self.resolve_charge_end_mortal_wounds(unit, target_unit, spec)
            return
        model_id = str(ctx.get("model_id", "") or "")
        model = self._resolve_model_by_id(model_id) if model_id else None
        if kind in ("move_over", "plunder"):
            self.resolve_move_over_mortal_wounds(unit, model, target_unit, spec)
            if spec.get("once_per_battle"):
                ability_key = str(spec.get("ability_key") or "").strip().lower()
                if ability_key:
                    try:
                        root = unit.get_attached_unit_root()
                    except Exception:
                        root = unit
                    if root is not None:
                        ability_name = str(spec.get("source", "") or "Move-over mortals").strip() or "Move-over mortals"
                        root.mark_unit_once_per_battle_used(ability_key, ability_name=ability_name)
            return
        if kind == "bomb_squigs":
            self.resolve_move_over_mortal_wounds(unit, None, target_unit, spec)
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                return
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            try:
                used = int(sr.get("bomb_squig_uses", 0) or 0)
            except Exception:
                used = 0
            try:
                max_uses = int(
                    spec.get("max_uses")
                    or ctx.get("max_uses")
                    or sr.get("bomb_squig_max_uses", 0)
                    or 1
                )
            except Exception:
                max_uses = 1
            max_uses = max(0, int(max_uses))
            if max_uses <= 0:
                return
            next_use = int(used + 1)
            sr["bomb_squig_uses"] = int(next_use)
            try:
                prev_max = int(sr.get("bomb_squig_max_uses", 0) or 0)
            except Exception:
                prev_max = 0
            sr["bomb_squig_max_uses"] = max(int(max_uses), int(prev_max))
            ability_name = str(spec.get("source", "") or ctx.get("ability_name", "") or "Bomb Squigs").strip() or "Bomb Squigs"
            sr["bomb_squig_source"] = ability_name
            root.special_rules = sr
            if next_use >= max_uses:
                mark_used = getattr(root, "mark_unit_once_per_battle_used", None)
                if callable(mark_used):
                    mark_used("bomb_squigs", ability_name=ability_name)
            return
        if kind == "floating_death":
            self.resolve_floating_death_mortal_wounds(unit, model, target_unit, spec)
            self._continue_floating_death_pending(unit)
            return
        if model is None:
            return
        if kind == "fight_phase_end":
            self.resolve_fight_phase_end_mortal_wounds(unit, model, target_unit, spec)
            return

    def _maybe_apply_bodyguard_loss_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        if str(getattr(request, "decision_type", "") or "") != DECISION_ALLOCATE_DAMAGE:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("selection_kind", "") or "") != "bodyguard_loss":
            return
        payload = self._decision_option_payload(request, result)
        model_id = payload.get("model_id", payload.get("model"))
        model = self._resolve_model_by_id(str(model_id or ""))
        if model is None:
            return
        leader_id = str(ctx.get("leader_unit_id", "") or "")
        bodyguard_id = str(ctx.get("bodyguard_unit_id", "") or ctx.get("unit_id", "") or "")
        leader_unit = self._resolve_unit_by_id(leader_id)
        bodyguard = self._resolve_unit_by_id(bodyguard_id)
        if leader_unit is None or bodyguard is None:
            return
        ability_name = str(ctx.get("ability_name", "") or "Leadership Test")
        self._resolve_charge_phase_bodyguard_loss(
            leader_unit,
            bodyguard,
            model,
            {"name": ability_name},
        )

    def _maybe_apply_daemonic_patrons_loss_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        if str(getattr(request, "decision_type", "") or "") != DECISION_ALLOCATE_DAMAGE:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("selection_kind", "") or "") != "daemonic_patrons_loss":
            return
        payload = self._decision_option_payload(request, result)
        model_id = payload.get("model_id", payload.get("model"))
        model = self._resolve_model_by_id(str(model_id or ""))
        if model is None:
            return
        try:
            alive = getattr(model, "is_alive", True)
            alive = alive() if callable(alive) else bool(alive)
        except Exception:
            alive = True
        if not alive:
            return
        try:
            model.die(game_map=getattr(self, "map", None))
        except Exception:
            return
        try:
            from ...utility.event_bus import append_action
            unit_id = str(ctx.get("unit_id", "") or "")
            unit = self._resolve_unit_by_id(unit_id) if unit_id else None
            ability_name = str(ctx.get("ability_name", "") or "Daemonic Patrons").strip() or "Daemonic Patrons"
            player = getattr(unit.get_parent_army(), "player", None) if unit is not None else None
            if player is not None:
                append_action(
                    player,
                    f"{ability_name}: {getattr(model, 'name', 'Model')} is destroyed.",
                )
        except Exception:
            pass

    def _maybe_apply_cult_ambush_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "")) != "cult_ambush_reinforcements":
            return
        marker_id = str(ctx.get("marker_id", "") or "")
        if not marker_id:
            return
        player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
        army = player.get_army() if player is not None else None
        mgr = getattr(army, "cult_ambush", None) if army is not None else None
        if mgr is None:
            return
        marker = None
        try:
            for entry in list(getattr(mgr, "markers", []) or []):
                if str(getattr(entry, "marker_id", "")) == marker_id:
                    marker = entry
                    break
        except Exception:
            marker = None
        if marker is None:
            return
        if not bool(getattr(marker, "active", False)):
            return

        chosen_unit = None
        if not self._decision_is_skip(request, result):
            payload = self._decision_option_payload(request, result)
            unit_id = payload.get("target_unit_id", payload.get("unit_id"))
            chosen_unit = self._resolve_unit_by_id(str(unit_id or ""))
            if chosen_unit is not None:
                try:
                    mgr.deploy_unit_from_marker(chosen_unit, marker, game=self)
                except Exception:
                    pass

        remaining_marker_ids = [str(m) for m in list(ctx.get("remaining_marker_ids") or []) if str(m or "")]
        available_unit_ids = [str(u) for u in list(ctx.get("available_unit_ids") or []) if str(u or "")]
        if chosen_unit is not None:
            try:
                used_id = str(get_entity_id(chosen_unit))
            except Exception:
                used_id = ""
            if used_id:
                available_unit_ids = [uid for uid in available_unit_ids if str(uid) != used_id]
        remaining_marker_ids = [mid for mid in remaining_marker_ids if str(mid) != marker_id]

        if not remaining_marker_ids or not available_unit_ids:
            return

        next_marker_id = ""
        for mid in list(remaining_marker_ids or []):
            next_marker_id = str(mid)
            try:
                found = False
                for entry in list(getattr(mgr, "markers", []) or []):
                    if str(getattr(entry, "marker_id", "")) == next_marker_id and bool(getattr(entry, "active", False)):
                        found = True
                        break
                if found:
                    break
            except Exception:
                break
        if not next_marker_id:
            return

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for pending in list(queue.list() or []):
                if str(getattr(pending, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                pctx = getattr(pending, "context", {}) or {}
                if str(pctx.get("ability", "")) == "cult_ambush_reinforcements" and str(pctx.get("marker_id", "")) == next_marker_id:
                    return

        from ..decisions import DecisionOption, DecisionRequest

        req_options = [DecisionOption.create("Skip (leave marker)", payload={"action": "skip"})]
        for uid in list(available_unit_ids or []):
            unit = self._resolve_unit_by_id(str(uid))
            if unit is None:
                continue
            req_options.append(
                DecisionOption.create(
                    getattr(unit, "name", "Unit"),
                    payload={"target_unit_id": str(uid)},
                )
            )
        if not req_options:
            return
        next_remaining = [mid for mid in remaining_marker_ids if str(mid) != next_marker_id]
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select Cult Ambush unit.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={
                "ability": "cult_ambush_reinforcements",
                "marker_id": next_marker_id,
                "remaining_marker_ids": list(next_remaining),
                "available_unit_ids": list(available_unit_ids),
            },
        )
        if hasattr(self, "request_decision"):
            self.request_decision(req)

    def _queue_code_chivalric_target_decision(self, mgr, player) -> bool:
        if mgr is None or player is None:
            return False
        try:
            options = list(mgr.get_eligible_character_models(game=self, player=player) or [])
        except Exception:
            options = []
        if not options:
            return False
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_SELECT_TARGET_MODEL:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("selection_kind", "")) == "code_chivalric_target":
                    return True
        from ..decisions import DecisionOption, DecisionRequest
        req_options = []
        for model in options:
            unit_name = getattr(getattr(model, "parent_unit", None), "name", "")
            label = f"{getattr(model, 'name', '')} ({unit_name})" if unit_name else str(getattr(model, "name", "Model"))
            req_options.append(DecisionOption.create(label, payload={"model_id": get_entity_id(model)}))
        if not req_options:
            return False
        req = DecisionRequest.create(
            DECISION_SELECT_TARGET_MODEL,
            "Select Code Chivalric target model.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"selection_kind": "code_chivalric_target"},
        )
        if hasattr(self, "request_decision"):
            self.request_decision(req)
        return True

    def _maybe_queue_code_chivalric_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        decision_type = str(getattr(request, "decision_type", "") or "")
        ctx = dict(getattr(request, "context", {}) or {})
        player = self._resolve_player_by_id(getattr(request, "player_id", None) or getattr(result, "player_id", None))
        army = player.get_army() if player is not None else None
        mgr = getattr(army, "code_chivalric", None) if army is not None else None
        if mgr is None:
            return

        if decision_type == DECISION_CHOOSE_CHIVALRIC_OATH:
            oath_kind = str(ctx.get("oath_kind", "") or "").strip().lower()
            if oath_kind == "deed":
                if getattr(mgr, "deed_requires_character_target", lambda: False)() and not getattr(mgr, "deed_target_model_id", None):
                    if self._queue_code_chivalric_target_decision(mgr, player):
                        return
                if not getattr(mgr, "selected_quality_key", None):
                    mgr.on_read_mission_objectives(game=self, player=player)
            elif oath_kind == "quality":
                if getattr(mgr, "deed_requires_character_target", lambda: False)() and not getattr(mgr, "deed_target_model_id", None):
                    self._queue_code_chivalric_target_decision(mgr, player)
            return

        if decision_type == DECISION_SELECT_TARGET_MODEL and str(ctx.get("selection_kind", "")) == "code_chivalric_target":
            payload = self._decision_option_payload(request, result)
            model_id = payload.get("model_id", payload.get("model"))
            model = self._resolve_model_by_id(str(model_id or ""))
            if model is not None:
                try:
                    mgr.set_deed_target_model(model)
                except Exception:
                    pass
            if not getattr(mgr, "selected_quality_key", None):
                mgr.on_read_mission_objectives(game=self, player=player)

    def queue_bodyguard_loss(
        self,
        *,
        leader_unit=None,
        bodyguard_unit=None,
        ability_name: str = "",
        player=None,
        leader_unit_id: str | None = None,
    ) -> None:
        if bodyguard_unit is None:
            return
        try:
            bodyguard = bodyguard_unit.get_attached_unit_root()
        except Exception:
            bodyguard = bodyguard_unit
        if bodyguard is None:
            return
        if leader_unit is None and leader_unit_id:
            leader_unit = self._resolve_unit_by_id(str(leader_unit_id))
        if leader_unit is None:
            try:
                leaders = list(getattr(bodyguard, "attached_leaders", []) or [])
            except Exception:
                leaders = []
            leader_unit = next((l for l in leaders if l is not None), None)
        if leader_unit is None:
            leader_unit = bodyguard
        if player is None:
            try:
                player = getattr(leader_unit.get_parent_army(), "player", None)
            except Exception:
                player = None
        ability_label = str(ability_name or "Bodyguard Loss").strip() or "Bodyguard Loss"
        candidates = [m for m in (bodyguard.models or []) if getattr(m, "is_alive", True)]
        if not candidates:
            return
        if len(candidates) == 1:
            self._resolve_charge_phase_bodyguard_loss(leader_unit, bodyguard, candidates[0], {"name": ability_label})
            return
        options = []
        sorted_candidates = [m for m in list(candidates) if m is not None]
        sorted_candidates.sort(key=lambda m: str(maybe_entity_id(m) or ""))
        for model in sorted_candidates:
            model_id = maybe_entity_id(model)
            if not model_id:
                continue
            options.append(
                DecisionOption.create(
                    getattr(model, "name", "Model"),
                    payload={"model_id": model_id},
                )
            )
        if not options:
            return
        leader_id = maybe_entity_id(leader_unit)
        bodyguard_id = maybe_entity_id(bodyguard)
        if not leader_id or not bodyguard_id:
            return
        ctx = {
            "engine_flow": True,
            "selection_kind": "bodyguard_loss",
            "leader_unit_id": leader_id,
            "bodyguard_unit_id": bodyguard_id,
            "unit_id": bodyguard_id,
            "ability_name": ability_label,
        }
        request = DecisionRequest.create(
            DECISION_ALLOCATE_DAMAGE,
            "Select Bodyguard model to destroy.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)

    def _queue_transport_reactive_disembark_decisions(
        self,
        *,
        player,
        transport,
        enemy_unit=None,
        ability: dict | None = None,
        trigger: str | None = None,
        max_units: int | None = None,
    ) -> list[DecisionRequest]:
        if player is None or transport is None:
            return []
        transport_id = maybe_entity_id(transport)
        if not transport_id:
            return []
        enemy_unit_id = maybe_entity_id(enemy_unit) if enemy_unit is not None else None
        ability_name = str((ability or {}).get("name", "") or "Reactive Disembark").strip() or "Reactive Disembark"
        try:
            rng = int((ability or {}).get("range", 0) or 0)
        except Exception:
            rng = 0

        pending = [
            req
            for req in list(self.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_DISEMBARK
            and str(getattr(req, "context", {}).get("transport_id", "")) == transport_id
        ]
        pending_units = {
            str(getattr(req, "context", {}).get("unit_id", "") or "")
            for req in pending
            if str(getattr(req, "context", {}).get("unit_id", "") or "")
        }
        single_pick = int(max_units or 0) == 1
        if single_pick and pending:
            return []

        eligible = []
        seen = set()
        for passenger in list(getattr(transport, "transport_passengers", []) or []):
            if passenger is None:
                continue
            unit_id = maybe_entity_id(passenger)
            if not unit_id:
                continue
            if unit_id in seen or unit_id in pending_units:
                continue
            seen.add(unit_id)
            try:
                if getattr(passenger.round_state, "embarked_this_round", False):
                    continue
                if getattr(passenger.round_state, "disembarked_this_round", False):
                    continue
            except Exception:
                pass
            try:
                if getattr(passenger, "embarked_in", None) is not transport:
                    continue
            except Exception:
                pass
            eligible.append(passenger)
        eligible = sorted(
            [u for u in list(eligible or []) if u is not None],
            key=lambda u: str(maybe_entity_id(u) or ""),
        )
        if not eligible:
            return []

        requests: list[DecisionRequest] = []
        if single_pick:
            options = []
            for passenger in eligible:
                unit_id = maybe_entity_id(passenger)
                if not unit_id:
                    continue
                options.append(
                    DecisionOption.create(
                        getattr(passenger, "name", "Unit"),
                        payload={"unit_id": unit_id, "transport_id": transport_id},
                    )
                )
            options.append(
                DecisionOption.create(
                    "Remain embarked",
                    payload={"action": "skip", "skip": True},
                )
            )
            ctx = {
                "transport_id": transport_id,
                "reactive_disembark": True,
                "reactive_disembark_source": ability_name,
                "reactive_disembark_max_units": 1,
            }
            if enemy_unit_id:
                ctx["reactive_disembark_enemy_unit_id"] = enemy_unit_id
            if rng:
                ctx["reactive_disembark_range"] = int(rng)
            if trigger:
                ctx["reactive_disembark_trigger"] = str(trigger)
            request = DecisionRequest.create(
                DECISION_DISEMBARK,
                f"Select one unit to disembark from {getattr(transport, 'name', 'Transport')}",
                player_id=getattr(player, "id", None),
                options=options,
                context=ctx,
            )
            self.request_decision(request)
            requests.append(request)
            return requests

        for passenger in eligible:
            unit_id = maybe_entity_id(passenger)
            if not unit_id:
                continue
            options = [
                DecisionOption.create(
                    "Disembark",
                    payload={"unit_id": unit_id, "transport_id": transport_id},
                ),
                DecisionOption.create(
                    "Remain embarked",
                    payload={"unit_id": unit_id, "transport_id": None},
                ),
            ]
            ctx = {
                "unit_id": unit_id,
                "transport_id": transport_id,
                "reactive_disembark": True,
                "reactive_disembark_source": ability_name,
            }
            if enemy_unit_id:
                ctx["reactive_disembark_enemy_unit_id"] = enemy_unit_id
            if rng:
                ctx["reactive_disembark_range"] = int(rng)
            if trigger:
                ctx["reactive_disembark_trigger"] = str(trigger)
            request = DecisionRequest.create(
                DECISION_DISEMBARK,
                f"Disembark {getattr(passenger, 'name', 'Unit')}",
                player_id=getattr(player, "id", None),
                options=options,
                context=ctx,
            )
            self.request_decision(request)
            requests.append(request)
        return requests

    def _record_setup_reactive_shoot_or_charge_candidate(self, enemy_unit) -> None:
        if enemy_unit is None:
            return
        if not self.is_movement_phase():
            return
        enemy_army = enemy_unit.get_parent_army()
        enemy_player = getattr(enemy_army, "player", None) if enemy_army is not None else None
        if enemy_player is None:
            return
        if self.get_current_player() is not enemy_player:
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return

        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Setup reactive shoot/charge requires players.")
            if p is enemy_player:
                continue
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Setup reactive shoot/charge requires an army for {p.name}.")
            seen = set()
            for candidate in list(army.units):
                if candidate is None:
                    continue
                root = candidate.get_attached_unit_root()
                if root is None:
                    continue
                rid = get_entity_id(root)
                if rid in seen:
                    continue
                seen.add(rid)
                rule = root.get_setup_reactive_shoot_or_charge_rule()
                if not rule:
                    continue
                rng = int(rule.get("range", 12) or 12)
                if not root.can_setup_reactive_shoot_or_charge(
                    game=self,
                    game_map=game_map,
                    enemy_unit=enemy_unit,
                    range_override=rng,
                ):
                    continue
                root.record_setup_reactive_shoot_or_charge_candidate(enemy_unit, game=self)
