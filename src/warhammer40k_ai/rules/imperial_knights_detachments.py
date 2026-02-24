from __future__ import annotations

import re
from typing import Optional

from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id
from ..utility.event_bus import append_action
from .detachment_manager import DetachmentManagerBase


class ImperialKnightsDetachmentManager(DetachmentManagerBase):
    faction_id = "QI"
    DETACHMENT_VALOURSTRIKE_LANCE = "Valourstrike Lance"
    DETACHMENT_GATE_WARDEN_LANCE = "Gate Warden Lance"
    DETACHMENT_QUESTOR_FORGEPACT = "Questor Forgepact"
    DAUNTLESS_DEFENDERS_NAME = "Dauntless Defenders"
    DAUNTLESS_DEFENDERS_ABILITY_KEY = "gate_warden_dauntless_defenders_foundation"
    COGBOUND_ALLIANCE_NAME = "Cogbound Alliance"
    FORGEPACT_ALLOWED_ADMECH_UNIT_NAMES = (
        "tech priest dominus",
        "tech priest manipulus",
        "skitarii marshal",
        "skitarii rangers",
        "skitarii vanguard",
    )

    def __init__(self, army=None):
        super().__init__(army)
        self.dauntless_foundation_objective_ids: list[str] = []
        self.dauntless_selected_round: int = 0

    def is_valourstrike_lance(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_VALOURSTRIKE_LANCE)

    def is_gate_warden_lance(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_GATE_WARDEN_LANCE)

    def is_questor_forgepact(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_QUESTOR_FORGEPACT)

    @staticmethod
    def _entity_id(entity) -> str:
        return str(get_entity_id(entity) or "")

    @staticmethod
    def _normalize_unit_name(name: str) -> str:
        text = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower())
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _attached_root(unit):
        if unit is None:
            return None
        getter = getattr(unit, "get_attached_unit_root", None)
        if callable(getter):
            return getter()
        return unit

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    def _unit_is_imperial_knights(self, unit) -> bool:
        return self._unit_has_keyword_or_faction(unit, "IMPERIAL KNIGHTS", faction_id=self.faction_id)

    def _unit_is_adeptus_mechanicus(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword_or_faction(unit, "ADEPTUS MECHANICUS"):
            return True
        normalized = self._normalize_unit_name(getattr(unit, "name", ""))
        return normalized in set(self.FORGEPACT_ALLOWED_ADMECH_UNIT_NAMES)

    def _unit_is_tech_priest(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "TECH-PRIEST"):
            return True
        normalized = self._normalize_unit_name(getattr(unit, "name", ""))
        return normalized.startswith("tech priest ")

    def _unit_on_battlefield(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        if not bool(getattr(root, "deployed", True)):
            return False
        if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
            return False
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            return False
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        return True

    def _iter_army_roots(self) -> list:
        if self.army is None:
            return []
        roots: list = []
        seen_ids: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None or not self._unit_in_army(root):
                continue
            root_id = self._entity_id(root)
            if root_id and root_id in seen_ids:
                continue
            if root_id:
                seen_ids.add(root_id)
            roots.append(root)
        roots.sort(key=lambda u: self._entity_id(u))
        return roots

    @staticmethod
    def _battle_size_points_cap(points_limit: int) -> int:
        limit = int(points_limit or 0)
        if limit <= 0:
            return 0
        if limit <= 1000:
            return 250
        if limit <= 2000:
            return 500
        return 750

    def _distance_between_units(self, source_unit, target_unit, *, game=None, game_map=None) -> Optional[float]:
        source_root = self._attached_root(source_unit)
        target_root = self._attached_root(target_unit)
        if source_root is None or target_root is None:
            return None
        resolved_game = self._resolve_game(game)
        resolved_map = game_map
        if resolved_map is None and resolved_game is not None:
            resolved_map = getattr(resolved_game, "map", None)
        get_distance = getattr(resolved_map, "get_distance_between_units", None) if resolved_map is not None else None
        if callable(get_distance):
            try:
                return float(get_distance(source_root, target_root))
            except (TypeError, ValueError):
                return None
        closest_model = getattr(source_root, "return_closest_model_in_unit", None)
        if callable(closest_model):
            try:
                _model, distance = closest_model(target_root)
                return float(distance)
            except (TypeError, ValueError):
                return None
        return None

    def _unit_within_distance(self, source_unit, target_unit, *, max_distance: float, game=None, game_map=None) -> bool:
        distance = self._distance_between_units(source_unit, target_unit, game=game, game_map=game_map)
        if distance is None:
            return False
        return float(distance) <= float(max_distance) + 1e-6

    @staticmethod
    def _heal_most_damaged_model_in_unit(unit, amount: int) -> int:
        if unit is None:
            return 0
        heal_amount = int(amount or 0)
        if heal_amount <= 0:
            return 0
        models = [m for m in list(getattr(unit, "models", []) or []) if bool(getattr(m, "is_alive", True))]
        if not models:
            return 0
        candidate = None
        max_missing = 0
        for model in models:
            base_wounds = int(getattr(model, "_base_wounds", getattr(model, "wounds", 0)) or 0)
            current_wounds = int(getattr(model, "wounds", 0) or 0)
            missing = max(0, int(base_wounds - current_wounds))
            if missing <= 0:
                continue
            if missing > max_missing:
                max_missing = missing
                candidate = model
        if candidate is None or max_missing <= 0:
            return 0
        base_wounds = int(getattr(candidate, "_base_wounds", getattr(candidate, "wounds", 0)) or 0)
        current_wounds = int(getattr(candidate, "wounds", 0) or 0)
        applied = min(int(heal_amount), max(0, int(base_wounds - current_wounds)))
        if applied <= 0:
            return 0
        candidate.wounds = int(current_wounds + applied)
        return int(applied)

    def _model_in_army(self, model) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        root = self._attached_root(unit)
        return self._unit_in_army(root)

    @staticmethod
    def _weapon_is_ranged(weapon_profile) -> bool:
        if weapon_profile is None:
            return False
        parent = getattr(weapon_profile, "parent_wargear", None)
        return bool(parent is not None and callable(getattr(parent, "is_ranged", None)) and parent.is_ranged())

    def _resolve_game(self, game=None):
        if game is not None:
            return game
        player = getattr(self.army, "player", None) if self.army is not None else None
        return getattr(player, "game", None) if player is not None else None

    def _collect_objective_entries(self, *, game=None, game_map=None) -> list[tuple[str, object, object]]:
        if game is None:
            game = self._resolve_game(None)
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)

        pool = []
        if game_map is not None:
            pool.extend(list(getattr(game_map, "objectives", []) or []))
        if game is not None:
            pool.extend(list(getattr(game, "objectives", []) or []))

        entries: list[tuple[str, object, object]] = []
        seen_ids: set[str] = set()
        for objective in pool:
            objective_id = self._entity_id(objective)
            if not objective_id or objective_id in seen_ids:
                continue
            location = getattr(objective, "location", None)
            if location is None or bool(getattr(location, "removed", False)):
                continue
            seen_ids.add(objective_id)
            entries.append((objective_id, objective, location))
        entries.sort(key=lambda entry: str(entry[0]))
        return entries

    def _objective_entry_by_id(self, objective_id: str, *, game=None, game_map=None):
        wanted = str(objective_id or "").strip()
        if not wanted:
            return None
        for entry in self._collect_objective_entries(game=game, game_map=game_map):
            if str(entry[0]) == wanted:
                return entry
        return None

    def _reconcile_dauntless_foundations(self, *, game=None, game_map=None) -> None:
        active_ids: list[str] = []
        for objective_id in list(self.dauntless_foundation_objective_ids or []):
            objective_key = str(objective_id or "").strip()
            if not objective_key:
                continue
            if objective_key in active_ids:
                continue
            if self._objective_entry_by_id(objective_key, game=game, game_map=game_map) is None:
                continue
            active_ids.append(objective_key)
            if len(active_ids) >= 2:
                break
        self.dauntless_foundation_objective_ids = list(active_ids)

    def _can_manage_dauntless_for_round(self, battle_round: int) -> bool:
        if not self.is_gate_warden_lance():
            return False
        if int(battle_round or 0) <= 0:
            return False
        if int(self.dauntless_selected_round or 0) > 0:
            return True
        return int(battle_round) == 1

    def _pending_dauntless_request(self, game, army_id: str, *, slot_index: int = 0) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return False
        list_fn = getattr(queue, "list", None)
        if not callable(list_fn):
            return False
        for req in list(list_fn() or []):
            if str(getattr(req, "decision_type", "") or "") != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self.DAUNTLESS_DEFENDERS_ABILITY_KEY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            if int(slot_index or 0) > 0:
                try:
                    queued_slot_index = int(ctx.get("slot_index", 0) or 0)
                except (TypeError, ValueError):
                    queued_slot_index = 0
                if queued_slot_index != int(slot_index):
                    continue
            return True
        return False

    def _build_dauntless_request(self, game, *, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        owner = getattr(self.army, "player", None) if self.army is not None else None
        if game is None or owner is None:
            return None

        existing_ids = [str(v or "").strip() for v in list(self.dauntless_foundation_objective_ids or []) if str(v or "").strip()]
        excluded = set(existing_ids)
        candidate_entries = [
            entry for entry in self._collect_objective_entries(game=game)
            if str(entry[0]) not in excluded
        ]
        if not candidate_entries:
            return None

        slot_index = int(len(existing_ids) + 1)
        options = []
        candidate_ids: list[str] = []
        for idx, (objective_id, objective, location) in enumerate(candidate_entries):
            candidate_ids.append(str(objective_id))
            label = str(getattr(objective, "name", "") or f"Objective {idx + 1}")
            try:
                label = f"{label} ({float(getattr(location, 'x', 0.0)):.1f}, {float(getattr(location, 'y', 0.0)):.1f})"
            except (TypeError, ValueError):
                pass
            options.append(DecisionOption.create(label, payload={"objective_id": str(objective_id)}))
        if not options:
            return None

        if int(self.dauntless_selected_round or 0) <= 0:
            if slot_index <= 1:
                prompt = "Dauntless Defenders: select your first foundation objective marker."
            else:
                prompt = "Dauntless Defenders: select your second foundation objective marker."
        else:
            prompt = "Dauntless Defenders: select a new foundation objective marker."

        army_id = self._entity_id(self.army)
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            prompt,
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self.DAUNTLESS_DEFENDERS_ABILITY_KEY,
                "ability_name": self.DAUNTLESS_DEFENDERS_NAME,
                "army_id": army_id,
                "battle_round": int(battle_round),
                "slot_index": int(slot_index),
                "existing_foundation_ids": list(existing_ids),
                "candidate_objective_ids": list(candidate_ids),
                "optional": False,
            },
        )

    def queue_dauntless_defenders_selection_request(
        self,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ) -> None:
        if not self.is_gate_warden_lance():
            return
        if self.army is None:
            return
        owner = getattr(self.army, "player", None)
        if owner is None:
            return
        if player is not None and player is not owner:
            return
        if game is None:
            game = getattr(owner, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        try:
            br = int(battle_round or getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            br = int(getattr(game, "turn", 0) or 0)
        self._reconcile_dauntless_foundations(game=game)
        if len(self.dauntless_foundation_objective_ids) >= 2:
            return
        if not self._can_manage_dauntless_for_round(br):
            return
        slot_index = int(len(self.dauntless_foundation_objective_ids) + 1)
        army_id = self._entity_id(self.army)
        if self._pending_dauntless_request(game, army_id, slot_index=int(slot_index)):
            return
        request = self._build_dauntless_request(game, battle_round=int(br))
        request_decision = getattr(game, "request_decision", None)
        if request is not None and callable(request_decision):
            request_decision(request)

    def validate_dauntless_foundation_choice(
        self,
        objective_id: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
        slot_index: int = 0,
        candidate_ids: Optional[list[str]] = None,
    ) -> tuple[bool, str]:
        del slot_index
        if not self.is_gate_warden_lance():
            return False, "Dauntless Defenders requires a Gate Warden Lance army."
        if self.army is None:
            return False, "Dauntless Defenders army not found."
        owner = getattr(self.army, "player", None)
        if owner is not None and player is not None and player is not owner:
            return False, "Dauntless Defenders must be resolved by the owning player."
        objective_key = str(objective_id or "").strip()
        if not objective_key:
            return False, "Dauntless Defenders selection requires objective_id."
        if game is None:
            game = self._resolve_game(None)
        try:
            br = int(battle_round or getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        self._reconcile_dauntless_foundations(game=game)
        if len(self.dauntless_foundation_objective_ids) >= 2:
            return False, "Dauntless Defenders already has two active foundations."
        if not self._can_manage_dauntless_for_round(br):
            return False, "Dauntless Defenders foundations can only be selected from battle round 1."
        if objective_key in set(self.dauntless_foundation_objective_ids):
            return False, "Dauntless Defenders cannot select the same foundation twice."
        normalized_candidates = {
            str(v or "").strip() for v in list(candidate_ids or []) if str(v or "").strip()
        }
        if normalized_candidates and objective_key not in normalized_candidates:
            return False, "Dauntless Defenders selected objective marker is not an eligible candidate."
        if self._objective_entry_by_id(objective_key, game=game) is None:
            return False, "Dauntless Defenders selected objective marker was not found."
        return True, ""

    def select_dauntless_foundation(
        self,
        objective_id: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
        slot_index: int = 0,
        candidate_ids: Optional[list[str]] = None,
    ):
        valid, reason = self.validate_dauntless_foundation_choice(
            objective_id,
            game=game,
            player=player,
            battle_round=battle_round,
            slot_index=slot_index,
            candidate_ids=candidate_ids,
        )
        if not valid:
            return None
        objective_key = str(objective_id or "").strip()
        if game is None:
            game = self._resolve_game(None)
        entry = self._objective_entry_by_id(objective_key, game=game)
        if entry is None:
            return None
        _objective_id, objective, _location = entry
        selected = list(self.dauntless_foundation_objective_ids or [])
        selected.append(objective_key)
        deduped: list[str] = []
        for item in selected:
            key = str(item or "").strip()
            if not key or key in deduped:
                continue
            deduped.append(key)
            if len(deduped) >= 2:
                break
        self.dauntless_foundation_objective_ids = list(deduped)
        if int(self.dauntless_selected_round or 0) <= 0:
            try:
                self.dauntless_selected_round = int(battle_round or getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                self.dauntless_selected_round = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        foundation_index = 0
        if objective_key in self.dauntless_foundation_objective_ids:
            foundation_index = int(self.dauntless_foundation_objective_ids.index(objective_key) + 1)
        return {
            "objective_id": str(objective_key),
            "objective_name": str(getattr(objective, "name", "") or "Objective marker"),
            "battle_round": int(self.dauntless_selected_round or 0),
            "foundation_index": int(foundation_index),
            "source": self.DAUNTLESS_DEFENDERS_NAME,
        }

    def _sync_dauntless_foundations(self, *, game=None, game_map=None) -> None:
        resolved_game = self._resolve_game(game)
        self._reconcile_dauntless_foundations(game=resolved_game, game_map=game_map)
        if self.army is None:
            return
        if int(self.dauntless_selected_round or 0) <= 0:
            return
        if len(self.dauntless_foundation_objective_ids) >= 2:
            return
        if resolved_game is None or not bool(getattr(resolved_game, "is_authoritative", True)):
            return
        owner = getattr(self.army, "player", None)
        try:
            br = int(getattr(resolved_game, "turn", 0) or 0)
        except (TypeError, ValueError):
            br = 0
        self.queue_dauntless_defenders_selection_request(
            game=resolved_game,
            player=owner,
            battle_round=int(br),
        )

    def _line_points_for_dauntless(self, *, game=None, game_map=None):
        self._sync_dauntless_foundations(game=game, game_map=game_map)
        if len(self.dauntless_foundation_objective_ids) < 2:
            return None
        first = self._objective_entry_by_id(self.dauntless_foundation_objective_ids[0], game=game, game_map=game_map)
        second = self._objective_entry_by_id(self.dauntless_foundation_objective_ids[1], game=game, game_map=game_map)
        if first is None or second is None:
            return None
        first_point = first[2]
        second_point = second[2]
        return (
            (float(getattr(first_point, "x", 0.0)), float(getattr(first_point, "y", 0.0))),
            (float(getattr(second_point, "x", 0.0)), float(getattr(second_point, "y", 0.0))),
        )

    @staticmethod
    def _iter_unit_models(unit) -> list:
        get_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_models):
            return list(get_models() or [])
        return list(getattr(unit, "models", []) or [])

    @staticmethod
    def _model_crosses_line(model, *, start_xy: tuple[float, float], end_xy: tuple[float, float]) -> bool:
        if model is None:
            return False
        if float(start_xy[0]) == float(end_xy[0]) and float(start_xy[1]) == float(end_xy[1]):
            return False
        from shapely.geometry import LineString, Point

        line = LineString([tuple(start_xy), tuple(end_xy)])
        model_base = getattr(model, "model_base", None)
        if model_base is not None:
            get_shape = getattr(model_base, "get_base_shape", None)
            if callable(get_shape):
                shape = get_shape()
                if shape is not None and bool(getattr(line, "intersects", lambda _geom: False)(shape)):
                    return True
        get_location = getattr(model, "get_location", None)
        if callable(get_location):
            location = get_location()
            if isinstance(location, tuple) and len(location) >= 2:
                point = Point(float(location[0]), float(location[1]))
                return bool(line.distance(point) <= 1e-6)
        return False

    def is_unit_on_dauntless_defensive_line(self, unit, *, game=None, game_map=None) -> bool:
        if not self.is_gate_warden_lance():
            return False
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        if not self._unit_is_imperial_knights(root):
            return False
        line_points = self._line_points_for_dauntless(game=game, game_map=game_map)
        if line_points is None:
            return False
        start_xy, end_xy = line_points
        for model in self._iter_unit_models(root):
            if model is None:
                continue
            if not bool(getattr(model, "is_alive", True)):
                continue
            if self._model_crosses_line(model, start_xy=start_xy, end_xy=end_xy):
                return True
        return False

    def _model_can_see_target_unit(self, model, target_unit, *, game=None, game_map=None) -> bool:
        if model is None or target_unit is None:
            return False
        resolved_game = self._resolve_game(game)
        resolved_map = game_map
        if resolved_map is None and resolved_game is not None:
            resolved_map = getattr(resolved_game, "map", None)

        target_root = self._attached_root(target_unit)
        if target_root is None:
            return False

        can_see_unit_fn = getattr(resolved_game, "_model_can_see_unit", None) if resolved_game is not None else None
        if callable(can_see_unit_fn):
            return bool(can_see_unit_fn(model, target_root, game_map=resolved_map))

        attacker_unit = getattr(model, "parent_unit", None)
        attacker_root = self._attached_root(attacker_unit)
        los_fn = getattr(attacker_root, "_has_line_of_sight_to_target", None) if attacker_root is not None else None
        if callable(los_fn) and resolved_map is not None:
            return bool(los_fn(model, target_root, resolved_map))

        can_model_see_model = getattr(resolved_map, "can_model_see_model", None) if resolved_map is not None else None
        if callable(can_model_see_model):
            for target_model in self._iter_unit_models(target_root):
                if target_model is None or not bool(getattr(target_model, "is_alive", True)):
                    continue
                if bool(can_model_see_model(model, target_model)):
                    return True
            return False
        return True

    def _forgepact_allied_units(self) -> list:
        return [unit for unit in self._iter_army_roots() if self._unit_is_adeptus_mechanicus(unit)]

    def _forgepact_points_cap(self) -> int:
        if self.army is None:
            return 0
        return self._battle_size_points_cap(int(getattr(self.army, "points_limit", 0) or 0))

    def _validate_forgepact_allies(self) -> list[str]:
        errors: list[str] = []
        allied_units = self._forgepact_allied_units()
        if not allied_units:
            return errors
        allowed_names = set(self.FORGEPACT_ALLOWED_ADMECH_UNIT_NAMES)
        total_points = 0
        for unit in allied_units:
            normalized_name = self._normalize_unit_name(getattr(unit, "name", ""))
            if normalized_name not in allowed_names:
                errors.append(
                    f"Questor Forgepact: unit '{getattr(unit, 'name', 'Unknown')}' is not an allowed Forge World ally."
                )
            if bool(getattr(unit, "is_warlord", False)):
                errors.append(
                    f"Questor Forgepact: ADEPTUS MECHANICUS unit '{getattr(unit, 'name', 'Unknown')}' cannot be your Warlord."
                )
            get_cost = getattr(unit, "get_unit_cost", None)
            if callable(get_cost):
                total_points += int(get_cost() or 0)
        points_cap = self._forgepact_points_cap()
        if points_cap <= 0 or total_points > points_cap:
            errors.append(
                f"Questor Forgepact: Forge World allies total {int(total_points)} points (cap {int(points_cap)})."
            )
        return errors

    def _forgepact_has_tech_priest_support(self, unit, *, game=None, game_map=None) -> bool:
        if not self._unit_on_battlefield(unit):
            return False
        for ally in self._iter_army_roots():
            if not self._unit_is_tech_priest(ally):
                continue
            if not self._unit_on_battlefield(ally):
                continue
            if self._unit_within_distance(unit, ally, max_distance=3.0, game=game, game_map=game_map):
                return True
        return False

    def _forgepact_nearby_imperial_knights_support(self, unit, *, game=None, game_map=None) -> bool:
        if not self._unit_on_battlefield(unit):
            return False
        source_root = self._attached_root(unit)
        source_id = self._entity_id(source_root)
        for ally in self._iter_army_roots():
            if not self._unit_is_imperial_knights(ally):
                continue
            if not self._unit_on_battlefield(ally):
                continue
            if source_id and self._entity_id(ally) == source_id:
                continue
            if self._unit_within_distance(unit, ally, max_distance=6.0, game=game, game_map=game_map):
                return True
        return False

    def _apply_forgepact_sacristan_pledges(self, *, game=None, player=None) -> None:
        if not self.is_questor_forgepact():
            return
        owner = getattr(self.army, "player", None) if self.army is not None else None
        if owner is None:
            return
        if player is not None and player is not owner:
            return
        resolved_game = self._resolve_game(game)
        resolved_map = getattr(resolved_game, "map", None) if resolved_game is not None else None
        for unit in self._iter_army_roots():
            if not self._unit_is_imperial_knights(unit):
                continue
            if not self._unit_on_battlefield(unit):
                continue
            heal_amount = 1
            source_label = "Sacristan Pledge"
            if self._forgepact_has_tech_priest_support(unit, game=resolved_game, game_map=resolved_map):
                heal_amount = max(1, int(get_roll("D3") or 0))
                source_label = f"Sacristan Pledge (Tech-Priest support D3={int(heal_amount)})"
            healed = self._heal_most_damaged_model_in_unit(unit, int(heal_amount))
            if healed > 0:
                append_action(
                    owner,
                    f"{getattr(unit, 'name', 'Imperial Knights unit')}: {source_label}, regained {int(healed)} lost wound(s).",
                )

    def forgepact_divine_inspiration_reroll_hit_wound_ones(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
        game_map=None,
    ) -> tuple[bool, bool, str]:
        if not self.is_questor_forgepact():
            return False, False, ""
        if attacker_model is None:
            return False, False, ""
        if weapon_profile is not None and not self._weapon_is_ranged(weapon_profile):
            return False, False, ""
        if weapon_profile is None:
            return False, False, ""
        if not self._model_in_army(attacker_model):
            return False, False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._attached_root(attacker_unit)
        if attacker_root is None or not self._unit_is_adeptus_mechanicus(attacker_root):
            return False, False, ""
        if not self._unit_on_battlefield(attacker_root):
            return False, False, ""
        resolved_game = self._resolve_game(game)
        resolved_map = game_map
        if resolved_map is None and resolved_game is not None:
            resolved_map = getattr(resolved_game, "map", None)
        reroll_hit_ones = True
        reroll_wound_ones = self._forgepact_nearby_imperial_knights_support(
            attacker_root,
            game=resolved_game,
            game_map=resolved_map,
        )
        return reroll_hit_ones, reroll_wound_ones, "Divine Inspiration"

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        self._apply_forgepact_sacristan_pledges(game=game, player=player)

    def validate_detachment_rules(self) -> list[str]:
        errors: list[str] = []
        if self.is_questor_forgepact():
            errors.extend(self._validate_forgepact_allies())
        return errors

    def bold_gallantry_assault_applies(self, unit, weapon_profile=None) -> bool:
        if not self.is_valourstrike_lance():
            return False
        if unit is None or not self._unit_in_army(unit):
            return False
        if not self._unit_is_imperial_knights(unit):
            return False
        if weapon_profile is None:
            return True
        return self._weapon_is_ranged(weapon_profile)

    def dauntless_defenders_sustained_hits_value(
        self,
        attacker_model,
        target_unit,
        *,
        game=None,
        game_map=None,
    ) -> tuple[int, str]:
        if not self.is_gate_warden_lance():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        if not self._model_in_army(attacker_model):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._attached_root(attacker_unit)
        if attacker_root is None or not self._unit_is_imperial_knights(attacker_root):
            return 0, ""
        resolved_game = self._resolve_game(game)
        self._sync_dauntless_foundations(game=resolved_game, game_map=game_map)
        if not self.is_unit_on_dauntless_defensive_line(attacker_root, game=resolved_game, game_map=game_map):
            return 0, ""
        if not self._model_can_see_target_unit(attacker_model, target_unit, game=resolved_game, game_map=game_map):
            return 0, ""
        return 1, self.DAUNTLESS_DEFENDERS_NAME

    def dauntless_defenders_ignore_hit_modifiers_rule(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
        game_map=None,
    ) -> Optional[dict]:
        del weapon_profile
        sustained_value, _source = self.dauntless_defenders_sustained_hits_value(
            attacker_model,
            target_unit,
            game=game,
            game_map=game_map,
        )
        if int(sustained_value or 0) <= 0:
            return None
        return {
            "name": self.DAUNTLESS_DEFENDERS_NAME,
            "attack_type": "any",
            "allow_hit": True,
            "default_choice": "ignore_negative",
        }

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self.is_gate_warden_lance():
            return
        player = getattr(self.army, "player", None) if self.army is not None else None
        if game is None and player is not None:
            game = getattr(player, "game", None)
        self.queue_dauntless_defenders_selection_request(
            game=game,
            player=player,
            battle_round=int(battle_round or 0),
        )
