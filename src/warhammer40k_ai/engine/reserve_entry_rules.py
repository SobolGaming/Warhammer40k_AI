from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Sequence

from .combat_timing import geometry_profile_for_game
from .reserve_entry_geometry import (
    battlefield_dimensions,
    build_model_positions_from_anchor,
    distance_to_battlefield_edge,
    is_valid_strategic_reserves_edge,
    model_radius,
    prospective_positions_from_model_payload,
    strategic_reserves_edges,
)
from ..utility.entity_ids import get_entity_id


def _resolve_unit_by_id(game: object, unit_id: str) -> object | None:
    text = str(unit_id or "").strip()
    if not text:
        return None
    resolver = getattr(game, "_resolve_unit_by_id", None)
    if callable(resolver):
        unit = resolver(text)
        if unit is not None:
            return unit
    for player in list(getattr(game, "players", []) or []):
        if player is None:
            continue
        army = getattr(player, "army", None)
        if army is None:
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else None
        if army is None:
            continue
        for unit in list(getattr(army, "units", []) or []):
            if str(get_entity_id(unit) or "") == text:
                return unit
    return None


def _with_temporary_model_locations(
    unit: object,
    prospective: list[tuple[float, float, float, float]],
    callback: Callable[[], bool],
) -> bool:
    models = list(getattr(unit, "models", []) or [])
    snapshot: list[tuple[float, float, float, float] | None] = []
    for model in models:
        get_location = getattr(model, "get_location", None)
        if callable(get_location):
            try:
                location = get_location()
            except Exception:
                location = None
        else:
            location = None
        snapshot.append(location)
    for model, location in zip(models, prospective):
        set_location = getattr(model, "set_location", None)
        if callable(set_location):
            set_location(*location)
    try:
        return bool(callback())
    finally:
        for model, location in zip(models, snapshot):
            if location is None:
                continue
            set_location = getattr(model, "set_location", None)
            if callable(set_location):
                set_location(*location)


def masters_of_void_enemy_dz_override_active(unit: object, game: object) -> bool:
    if unit is None or game is None:
        return False
    get_root = getattr(unit, "get_attached_unit_root", None)
    root = get_root() if callable(get_root) else unit
    if root is None:
        return False
    special_rules = getattr(root, "special_rules", None)
    if not isinstance(special_rules, dict):
        return False
    if not bool(special_rules.get("imperial_agents_masters_of_the_void_enemy_dz_override_active")):
        return False

    owner_id = str(special_rules.get("imperial_agents_masters_of_the_void_enemy_dz_override_turn_owner", "") or "")
    try:
        effect_turn = int(special_rules.get("imperial_agents_masters_of_the_void_enemy_dz_override_turn", 0) or 0)
    except (TypeError, ValueError):
        effect_turn = 0
    try:
        current_turn = int(getattr(game, "turn", 0) or 0)
    except (TypeError, ValueError):
        current_turn = 0
    if effect_turn and current_turn and effect_turn != current_turn:
        return False

    current_player = getattr(game, "get_current_player", lambda: None)()
    current_owner_id = str(getattr(current_player, "id", "") or "")
    if owner_id and current_owner_id and owner_id != current_owner_id:
        return False

    expires_phase = str(
        special_rules.get("imperial_agents_masters_of_the_void_enemy_dz_override_expires_phase", "") or ""
    ).strip().upper()
    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
    if expires_phase and phase_name and expires_phase != phase_name:
        return False
    return True


def transponder_lock_module_turn_one_spotter_requirement_satisfied(
    unit: object,
    prospective: list[tuple[float, float, float, float]],
    *,
    pending_deep_strike: bool,
    game: object,
) -> bool:
    if unit is None or game is None or not bool(pending_deep_strike):
        return True
    get_root = getattr(unit, "get_attached_unit_root", None)
    root = get_root() if callable(get_root) else unit
    if root is None:
        return True
    special_rules = getattr(root, "special_rules", None)
    if not isinstance(special_rules, dict) or not bool(special_rules.get("enhancement_transponder_lock_module")):
        return True
    try:
        current_turn = int(getattr(game, "turn", 0) or 0)
    except (TypeError, ValueError):
        current_turn = 0
    if current_turn != 1:
        return True

    try:
        max_range = float(special_rules.get("enhancement_transponder_lock_module_turn_one_spotter_range", 12.0) or 12.0)
    except (TypeError, ValueError):
        max_range = 12.0
    if max_range <= 0.0:
        return False

    required_keywords = [
        str(value or "").strip().upper()
        for value in list(
            special_rules.get(
                "enhancement_transponder_lock_module_turn_one_spotter_keywords_any",
                ("KROOT", "VESPID STINGWINGS"),
            )
            or ()
        )
        if str(value or "").strip()
    ]
    if not required_keywords:
        required_keywords = ["KROOT", "VESPID STINGWINGS"]

    army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
    game_map = getattr(game, "map", None)
    if army is None or game_map is None:
        return False

    from ..utility.aura_utils import distance_between_bases_3d

    def _unit_has_required_keyword(candidate_unit: object) -> bool:
        if candidate_unit is None:
            return False
        has_any_keyword = getattr(candidate_unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            for keyword in required_keywords:
                if bool(has_any_keyword(keyword)):
                    return True
        pool: list[str] = []
        pool.extend([str(value or "").strip().upper() for value in list(getattr(candidate_unit, "keywords", []) or [])])
        pool.extend(
            [str(value or "").strip().upper() for value in list(getattr(candidate_unit, "faction_keywords", []) or [])]
        )
        return any(keyword in pool for keyword in required_keywords)

    friendly_units: list[object] = []
    seen_ids: set[str] = set()
    for candidate in list(getattr(game_map, "units", []) or []):
        if candidate is None:
            continue
        get_candidate_root = getattr(candidate, "get_attached_unit_root", None)
        candidate_root = get_candidate_root() if callable(get_candidate_root) else candidate
        if candidate_root is None or candidate_root is root:
            continue
        candidate_id = str(get_entity_id(candidate_root) or "")
        if candidate_id and candidate_id in seen_ids:
            continue
        if candidate_id:
            seen_ids.add(candidate_id)
        candidate_army = candidate_root.get_parent_army() if hasattr(candidate_root, "get_parent_army") else None
        if candidate_army is not army:
            continue
        is_alive = getattr(candidate_root, "is_alive", None)
        alive = bool(is_alive()) if callable(is_alive) else bool(getattr(candidate_root, "is_alive", True))
        if not alive:
            continue
        if not bool(getattr(candidate_root, "deployed", False)):
            continue
        if str(getattr(candidate_root, "reserve_status", "deployed") or "deployed") != "deployed":
            continue
        if bool(getattr(candidate_root, "is_embarked", False)) or getattr(candidate_root, "embarked_in", None) is not None:
            continue
        if not _unit_has_required_keyword(candidate_root):
            continue
        friendly_units.append(candidate_root)

    if not friendly_units:
        return False

    for index, (x, y, z, facing) in enumerate(prospective):
        if index >= len(getattr(root, "models", []) or []):
            break
        base = root._create_potential_base(x, y, z, facing, model=root.models[index])
        for spotter in list(friendly_units or []):
            for model in list(getattr(spotter, "models", []) or []):
                model_alive_attr = getattr(model, "is_alive", True)
                model_alive = bool(model_alive_attr() if callable(model_alive_attr) else model_alive_attr)
                if not model_alive:
                    continue
                if float(distance_between_bases_3d(base, model.model_base)) <= float(max_range) + 1e-6:
                    return True
    return False


def _resolve_tunnel_marker(game: object, unit: object, prospective: list[tuple[float, float, float, float]], context: dict) -> object | None:
    try:
        army = unit.get_parent_army()
    except Exception:
        army = None
    tyr_mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
    marker_fn = getattr(tyr_mgr, "subterranean_assault_arrival_marker_for_positions", None) if tyr_mgr is not None else None
    if not callable(marker_fn):
        return None
    allowed_marker_ids = tuple(
        str(value or "").strip() for value in list(context.get("tunnel_marker_allowed_ids") or []) if str(value or "").strip()
    )
    excluded_marker_ids = tuple(
        str(value or "").strip()
        for value in list(context.get("tunnel_marker_excluded_ids") or [])
        if str(value or "").strip()
    )
    return marker_fn(
        unit,
        list(prospective),
        game=game,
        allowed_marker_ids=allowed_marker_ids,
        excluded_marker_ids=excluded_marker_ids,
    )


def _anchor_validation_error(
    game: object,
    unit: object,
    prospective: list[tuple[float, float, float, float]],
    *,
    context: dict,
) -> str | None:
    anchor_unit_id = str(context.get("reserves_arrival_anchor_unit_id", "") or "").strip()
    try:
        anchor_range = float(context.get("reserves_arrival_anchor_range", 0.0) or 0.0)
    except (TypeError, ValueError):
        anchor_range = 0.0
    anchor_wholly_within = bool(context.get("reserves_arrival_anchor_wholly_within", False))
    anchor_source_name = str(context.get("reserves_arrival_anchor_source", "") or "").strip()
    if not anchor_unit_id or anchor_range <= 0.0:
        return None
    anchor_unit = _resolve_unit_by_id(game, anchor_unit_id)
    get_root = getattr(anchor_unit, "get_attached_unit_root", None)
    anchor_root = get_root() if callable(get_root) else anchor_unit
    if anchor_root is None:
        return "Reserves arrival anchor unit was not found."
    if not bool(getattr(anchor_root, "deployed", True)):
        return "Reserves arrival anchor unit is not on the battlefield."
    if str(getattr(anchor_root, "reserve_status", "deployed") or "deployed") != "deployed":
        return "Reserves arrival anchor unit is not on the battlefield."
    if bool(getattr(anchor_root, "embarked_in", None)) or bool(getattr(anchor_root, "is_embarked", False)):
        return "Reserves arrival anchor unit is not on the battlefield."

    from ..utility.aura_utils import model_wholly_within_range_of_unit, model_within_range_of_unit

    create_base = getattr(unit, "_create_potential_base", None)
    if not callable(create_base):
        return "Reserves arrival anchor validation is unavailable."
    for model, (x, y, z, facing) in zip(list(getattr(unit, "models", []) or []), prospective):
        if not getattr(model, "is_alive", True):
            continue
        candidate_base = create_base(x, y, z, facing, model=model)
        proxy_model = SimpleNamespace(model_base=candidate_base, is_alive=True)
        if anchor_wholly_within:
            in_range = bool(
                model_wholly_within_range_of_unit(
                    anchor_root,
                    proxy_model,
                    float(anchor_range),
                    use_attached_aggregate=True,
                )
            )
        else:
            in_range = bool(
                model_within_range_of_unit(
                    proxy_model,
                    anchor_root,
                    float(anchor_range),
                    use_attached_aggregate=True,
                )
            )
        if in_range:
            continue
        source_label = anchor_source_name or "Anchor ability"
        if anchor_wholly_within:
            return f"{source_label}: reserves arrival must be wholly within {int(anchor_range)}\" of the source unit."
        return f"{source_label}: reserves arrival must be within {int(anchor_range)}\" of the source unit."
    return None


def _hallowed_ground_error(game: object, unit: object, prospective: list[tuple[float, float, float, float]]) -> str | None:
    get_root = getattr(unit, "get_attached_unit_root", None)
    root = get_root() if callable(get_root) else unit
    if root is None:
        return None
    special_rules = getattr(root, "special_rules", None)
    requires_hallowed_ground = False
    if isinstance(special_rules, dict) and bool(special_rules.get("hallowed_beacon_requires_hallowed_ground")):
        owner_id = str(special_rules.get("hallowed_beacon_turn_owner", "") or "")
        try:
            effect_turn = int(special_rules.get("hallowed_beacon_turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        expires_phase = str(special_rules.get("hallowed_beacon_expires_phase", "") or "").strip().upper()
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        current_owner = str(getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or "")
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        requires_hallowed_ground = True
        if owner_id and current_owner and owner_id != current_owner:
            requires_hallowed_ground = False
        if requires_hallowed_ground and effect_turn and current_turn and effect_turn != current_turn:
            requires_hallowed_ground = False
        if requires_hallowed_ground and expires_phase and phase_name and expires_phase != phase_name:
            requires_hallowed_ground = False
    if not requires_hallowed_ground:
        return None

    army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
    gk_mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
    checker = getattr(gk_mgr, "unit_wholly_within_hallowed_ground", None) if gk_mgr is not None else None
    if not callable(checker):
        return "Hallowed Beacon: reserves arrival must be wholly within Hallowed Ground."

    valid = _with_temporary_model_locations(
        root,
        prospective,
        lambda: bool(checker(root, game=game)),
    )
    if valid:
        return None
    return "Hallowed Beacon: reserves arrival must be wholly within Hallowed Ground."


def _resolve_min_enemy_distance(
    game: object,
    unit: object,
    prospective: list[tuple[float, float, float, float]],
    *,
    context: dict,
    battlefield_edge: str | None,
    tunnel_marker: object | None,
) -> float:
    geometry = geometry_profile_for_game(game, context=context)
    min_enemy_distance = float(geometry.ingress_exclusion_distance or 0.0)
    warp_rifts = getattr(game, "_warp_rifts_min_distance", None)
    if callable(warp_rifts):
        try:
            resolved = warp_rifts(unit)
        except Exception:
            resolved = None
        if resolved is not None:
            min_enemy_distance = float(resolved)
    if tunnel_marker is not None:
        min_enemy_distance = 6.0
    min_enemy_distance_override = context.get("reserves_arrival_min_enemy_distance_override")
    if min_enemy_distance_override is not None:
        try:
            min_enemy_distance = max(0.0, float(min_enemy_distance_override))
        except (TypeError, ValueError):
            min_enemy_distance = 0.0
    if battlefield_edge is not None or tunnel_marker is not None:
        return float(min_enemy_distance)

    override_fn = getattr(unit, "get_deep_strike_min_distance_override", None)
    if callable(override_fn):
        try:
            override = override_fn()
        except Exception:
            override = None
        if override:
            min_enemy_distance = min(float(min_enemy_distance), float(override))

    try:
        army = unit.get_parent_army()
    except Exception:
        army = None
    dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
    beckoning_fn = (
        getattr(dg_mgr, "tallyband_beckoning_blight_deep_strike_min_enemy_distance", None)
        if dg_mgr is not None
        else None
    )
    if callable(beckoning_fn):
        try:
            beckoning_distance, _beckoning_source = beckoning_fn(
                unit,
                prospective_positions=list(prospective),
                game=game,
                game_map=getattr(game, "map", None),
            )
        except Exception:
            beckoning_distance = 0.0
        if float(beckoning_distance or 0.0) > 0.0:
            min_enemy_distance = min(float(min_enemy_distance), float(beckoning_distance))
    return float(min_enemy_distance)


def _evaluate_reserves_arrival_prospective(
    game: object,
    unit: object,
    prospective: list[tuple[float, float, float, float]],
    *,
    context: dict,
    forced_battlefield_edge: str | None = None,
) -> dict[str, Any]:
    width, height = battlefield_dimensions(game)
    if width is None or height is None:
        return {"errors": []}

    try:
        effective_turn = int(getattr(game, "turn", 0) or 0)
    except (TypeError, ValueError):
        effective_turn = 0
    strategic_setup_turn = getattr(unit, "get_strategic_reserves_setup_turn", None)
    if callable(strategic_setup_turn):
        try:
            effective_turn = int(strategic_setup_turn(game=game, current_turn=effective_turn))
        except Exception:
            pass

    player_id = None
    try:
        army = unit.get_parent_army()
        player_id = getattr(getattr(army, "player", None), "id", None)
    except Exception:
        player_id = None

    strategic_ok = False
    strategic_used_edge_touch = False
    selected_edge: str | None = None
    ignore_battlefield_edge_requirement = bool(
        context.get("reserves_arrival_ignore_battlefield_edge_requirement", False)
    )

    if bool(getattr(unit, "is_in_strategic_reserves", lambda: False)()):
        candidate_edges = [forced_battlefield_edge] if forced_battlefield_edge else list(strategic_reserves_edges())
        for edge in candidate_edges:
            checker = getattr(game, "is_valid_strategic_reserves_edge", None)
            if callable(checker):
                try:
                    if not bool(checker(edge, turn=effective_turn)):
                        continue
                except Exception:
                    continue
            elif not is_valid_strategic_reserves_edge(game, edge, turn=effective_turn):
                continue
            if effective_turn == 2 and player_id and not masters_of_void_enemy_dz_override_active(unit, game):
                enemy_dz_checker = getattr(game, "is_position_in_enemy_deployment_zone", None)
                if callable(enemy_dz_checker):
                    any_in_enemy_dz = False
                    for (x, y, _z, _facing) in prospective:
                        try:
                            if enemy_dz_checker(float(x), float(y), player_id):
                                any_in_enemy_dz = True
                                break
                        except Exception:
                            continue
                    if any_in_enemy_dz:
                        continue
            used_touch = False
            ok_all = True
            for model, (x, y, z, _facing) in zip(list(getattr(unit, "models", []) or []), prospective):
                radius = float(model_radius(model))
                distance = distance_to_battlefield_edge((x, y, z), edge, width=width, height=height)
                max_center = 6.0 - radius
                if max_center >= 0.0:
                    if distance > max_center + 1e-6:
                        ok_all = False
                        break
                    continue
                if abs(distance - radius) > 0.25:
                    ok_all = False
                    break
                used_touch = True
            if not ok_all:
                continue
            strategic_ok = True
            strategic_used_edge_touch = bool(used_touch)
            selected_edge = edge
            break

    tunnel_marker = _resolve_tunnel_marker(game, unit, prospective, context)

    deep_strike_ok = True
    if bool(getattr(unit, "is_in_strategic_reserves", lambda: False)()):
        try:
            deep_strike_ok = bool(getattr(unit, "has_deep_strike", lambda: False)())
        except Exception:
            deep_strike_ok = False
        if not deep_strike_ok:
            special_rules = getattr(unit, "special_rules", None)
            if isinstance(special_rules, dict) and (
                bool(special_rules.get("cosmic_precision_temp_deep_strike", False))
                or bool(special_rules.get("dread_talons_screaming_descent_temp_deep_strike", False))
            ):
                deep_strike_ok = True
        if not strategic_ok and not deep_strike_ok and tunnel_marker is None and not ignore_battlefield_edge_requirement:
            has_tunnel_rule = False
            try:
                army = unit.get_parent_army()
            except Exception:
                army = None
            tyr_mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
            has_tunnel_rule = bool(tyr_mgr is not None and getattr(tyr_mgr, "is_subterranean_assault", lambda: False)())
            if has_tunnel_rule:
                return {
                    "errors": [
                        "Reserves arrival must be within 6\" of a battlefield edge or wholly within 9\" of a Tunnel Marker."
                    ]
                }
            return {"errors": ["Reserves arrival must be within 6\" of a battlefield edge."]}

    battlefield_edge = selected_edge if strategic_ok else None

    anchor_error = _anchor_validation_error(game, unit, prospective, context=context)
    if anchor_error:
        return {"errors": [anchor_error]}

    hallowed_ground_error = _hallowed_ground_error(game, unit, prospective)
    if hallowed_ground_error:
        return {"errors": [hallowed_ground_error]}

    min_enemy_distance_override = context.get("reserves_arrival_min_enemy_distance_override")
    min_enemy_distance = _resolve_min_enemy_distance(
        game,
        unit,
        prospective,
        context=context,
        battlefield_edge=battlefield_edge,
        tunnel_marker=tunnel_marker,
    )

    game_map = getattr(game, "map", None)
    if battlefield_edge is None and tunnel_marker is None:
        checker = getattr(unit, "is_dark_apparitions_arrival_valid", None)
        if callable(checker):
            try:
                if not bool(checker(prospective, game=game, game_map=game_map)):
                    return {
                        "errors": [
                            "Dark Apparitions: reserves Deep Strike setup must be wholly within 9\" of one or more friendly EMPEROR'S CHILDREN units."
                        ]
                    }
            except Exception:
                return {"errors": ["Dark Apparitions: reserves Deep Strike setup validation failed."]}
        checker = getattr(unit, "is_through_the_veil_arrival_valid", None)
        if callable(checker):
            try:
                if not bool(checker(prospective, game=game, game_map=game_map)):
                    return {
                        "errors": [
                            "Through the Veil: SCARAB OCCULT TERMINATORS must arrive wholly within your army's Flow of Magic."
                        ]
                    }
            except Exception:
                return {"errors": ["Through the Veil: reserves Deep Strike setup validation failed."]}

    from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases

    enemy_units: list[object] = []
    try:
        player = unit.get_parent_army().player
        enemy_units = list(getattr(game, "get_enemy_units", lambda _player: [])(player) or [])
    except Exception:
        enemy_units = []
    enemy_models: list[tuple[object, object]] = []
    for enemy in list(enemy_units or []):
        get_root = getattr(enemy, "get_attached_unit_root", None)
        enemy_root = get_root() if callable(get_root) else enemy
        if enemy_root is None:
            continue
        is_alive = getattr(enemy_root, "is_alive", None)
        try:
            alive = bool(is_alive()) if callable(is_alive) else bool(getattr(enemy_root, "is_alive", True))
        except Exception:
            alive = bool(getattr(enemy_root, "is_alive", True))
        if not alive:
            continue
        if not bool(getattr(enemy_root, "deployed", False)):
            continue
        if str(getattr(enemy_root, "reserve_status", "deployed") or "deployed") != "deployed":
            continue
        if getattr(enemy_root, "embarked_in", None) is not None or bool(getattr(enemy_root, "is_embarked", False)):
            continue
        for enemy_model in list(getattr(enemy_root, "models", []) or []):
            if not getattr(enemy_model, "is_alive", True):
                continue
            enemy_models.append((enemy_root, enemy_model))

    geometry = geometry_profile_for_game(game, context=context)
    for model, (x, y, z, facing) in zip(list(getattr(unit, "models", []) or []), prospective):
        create_base = getattr(unit, "_create_potential_base", None)
        if not callable(create_base):
            continue
        try:
            base = create_base(x, y, z, facing, model=model)
        except Exception:
            base = None
        if base is None:
            continue
        for enemy_root, enemy_model in list(enemy_models or []):
            try:
                distance = float(horizontal_distance_between_bases_2d(base, enemy_model.model_base))
            except Exception:
                continue
            required_distance = float(min_enemy_distance)
            if min_enemy_distance_override is None and battlefield_edge is None and tunnel_marker is None:
                per_enemy_fn = getattr(unit, "get_deep_strike_min_distance_vs_enemy", None)
                if callable(per_enemy_fn):
                    try:
                        per_enemy = per_enemy_fn(enemy_root, game=game, game_map=game_map)
                    except Exception:
                        per_enemy = None
                    if per_enemy:
                        required_distance = float(per_enemy)
            if required_distance > 0.0 and distance < float(required_distance):
                return {"errors": [f"Reserves arrival must be more than {int(required_distance)}\" from enemy models."]}
            if bool(context.get("reserves_arrival_require_not_engagement", False)):
                try:
                    vertical_distance = float(vertical_distance_between_bases(base, enemy_model.model_base))
                except Exception:
                    continue
                if (
                    distance <= float(geometry.engagement_range_horizontal)
                    and vertical_distance <= float(geometry.engagement_range_vertical)
                ):
                    return {"errors": ["Reserves arrival must not be within Engagement Range of enemy models."]}

    denial_checker = getattr(game, "_reserves_denial_violated", None)
    if callable(denial_checker):
        try:
            if bool(denial_checker(unit, prospective)):
                return {"errors": ["Reserves arrival position is denied by an enemy ability."]}
        except Exception:
            pass

    if bool(getattr(unit, "is_in_strategic_reserves", lambda: False)()):
        pending_deep_strike = bool(deep_strike_ok and not strategic_ok and tunnel_marker is None)
    else:
        pending_deep_strike = bool(tunnel_marker is None)
    if not transponder_lock_module_turn_one_spotter_requirement_satisfied(
        unit,
        list(prospective),
        pending_deep_strike=pending_deep_strike,
        game=game,
    ):
        return {
            "errors": [
                "Transponder Lock Module: first-turn Deep Strike setup must be within 12\" of a friendly KROOT or VESPID STINGWINGS unit."
            ]
        }

    return {
        "errors": [],
        "prospective": prospective,
        "battlefield_edge": battlefield_edge,
        "edge_touch": bool(strategic_ok and strategic_used_edge_touch),
        "pending_deep_strike": bool(pending_deep_strike),
        "tunnel_marker_id": str(getattr(tunnel_marker, "marker_id", "") or ""),
        "min_enemy_distance": float(min_enemy_distance),
    }


def evaluate_reserves_arrival_positions(
    game: object,
    unit: object,
    model_positions: object,
    *,
    ctx: dict | None = None,
) -> dict[str, Any]:
    context = dict(ctx or {})
    placement_kind = str(context.get("placement_kind", "") or "").strip().lower()
    is_hyperphasic_recall = placement_kind == "hyperphasic_recall"
    is_subterranean_tunnel_network = placement_kind == "subterranean_tunnel_network"
    if unit is None:
        return {"errors": ["Reserves arrival requires a unit."]}
    in_reserves_fn = getattr(unit, "is_in_reserves", None)
    in_reserves = bool(in_reserves_fn()) if callable(in_reserves_fn) else (
        str(getattr(unit, "reserve_status", "deployed") or "deployed").strip().lower() in {"reserves", "strategic_reserves"}
    )
    if (
        not is_hyperphasic_recall
        and not is_subterranean_tunnel_network
        and not in_reserves
    ):
        return {"errors": ["Unit is not in reserves."]}
    ignore_turn_requirement = bool(context.get("reserves_arrival_ignore_turn_requirement", False))
    if not ignore_turn_requirement and not is_hyperphasic_recall and not is_subterranean_tunnel_network:
        can_arrive = getattr(unit, "can_arrive_from_reserves", None)
        if callable(can_arrive):
            try:
                if not bool(can_arrive(getattr(game, "turn", 0))):
                    return {"errors": ["Unit cannot arrive from reserves this turn."]}
            except Exception:
                return {"errors": ["Reserves arrival eligibility check failed."]}

    prospective_result = prospective_positions_from_model_payload(unit, model_positions)
    error = str(prospective_result.get("error", "") or "")
    if error:
        return {"errors": [error]}
    return _evaluate_reserves_arrival_prospective(
        game,
        unit,
        list(prospective_result.get("prospective") or []),
        context=context,
    )


def validate_reserves_arrival_positions(
    game: object,
    unit: object,
    model_positions: object,
    *,
    ctx: dict | None = None,
) -> Sequence[str]:
    evaluation = evaluate_reserves_arrival_positions(game, unit, model_positions, ctx=ctx)
    if evaluation.get("errors"):
        return tuple(evaluation.get("errors") or [])
    return ()


def can_place_unit_arriving_from_reserves(
    game: object,
    unit: object,
    position: tuple[float, float, float],
    *,
    battlefield_edge: str | None = None,
) -> bool:
    if game is None or unit is None:
        return False
    width, height = battlefield_dimensions(game)
    if width is None or height is None:
        return False
    if float(position[0]) < 0.0 or float(position[0]) >= float(width):
        return False
    if float(position[1]) < 0.0 or float(position[1]) >= float(height):
        return False
    if hasattr(unit, "_pending_reserves_edge_touch"):
        delattr(unit, "_pending_reserves_edge_touch")
    model_positions = build_model_positions_from_anchor(
        game,
        unit,
        x=float(position[0]),
        y=float(position[1]),
        avoid_friendly_units=True,
    )
    if not model_positions:
        return False
    prospective_result = prospective_positions_from_model_payload(unit, model_positions)
    error = str(prospective_result.get("error", "") or "")
    if error:
        return False
    evaluation = _evaluate_reserves_arrival_prospective(
        game,
        unit,
        list(prospective_result.get("prospective") or []),
        context={},
        forced_battlefield_edge=str(battlefield_edge or "").strip().lower() or None,
    )
    errors = list(evaluation.get("errors") or [])
    if errors:
        return False
    if bool(evaluation.get("edge_touch")):
        setattr(unit, "_pending_reserves_edge_touch", True)
    elif hasattr(unit, "_pending_reserves_edge_touch"):
        delattr(unit, "_pending_reserves_edge_touch")
    setattr(unit, "_pending_reserves_deep_strike", bool(evaluation.get("pending_deep_strike", False)))
    tunnel_marker_id = str(evaluation.get("tunnel_marker_id", "") or "")
    if tunnel_marker_id:
        setattr(unit, "_pending_reserves_tunnel_marker_id", tunnel_marker_id)
    elif hasattr(unit, "_pending_reserves_tunnel_marker_id"):
        delattr(unit, "_pending_reserves_tunnel_marker_id")
    return True
