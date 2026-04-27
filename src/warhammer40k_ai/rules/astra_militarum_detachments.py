from __future__ import annotations

import re
from typing import Any, Iterable

from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class AstraMilitarumDetachmentManager(DetachmentManagerBase):
    faction_id = "AM"
    _BRIDGEHEAD_FIRING_HOT_WEAPON_NAMES = frozenset(
        {
            "hot shot lascarbine",
            "hot shot lasgun",
            "hot shot laspistol",
            "hot shot marksman rifle",
            "hot shot volley gun",
            "sentry hot shot volley gun",
        }
    )
    _ARTILLERY_SUPPORT_MODE_ABILITY = "siege_regiment_artillery_support_mode"
    _ARTILLERY_SUPPORT_INCENDIARY_ABILITY = "siege_regiment_incendiary_bombardment"
    _ARTILLERY_SUPPORT_SMOKE_ABILITY = "siege_regiment_smoke_shells"
    _ARTILLERY_SUPPORT_CREEPING_SELECTION_ABILITY = "siege_regiment_creeping_barrage_selection"
    _STEEL_HAMMER_TITANIC_CHARACTER_SELECTION_ABILITY = "steel_hammer_titanic_character_selection"
    _ARTILLERY_SUPPORT_SHAKEN_TAG = "detachment:artillery_support_shaken"
    _ARTILLERY_SUPPORT_SHAKEN_MODIFIER_SOURCE = "ability:artillery_support_shaken"
    _ARTILLERY_SUPPORT_MODE_LABELS = {
        "creeping_barrage": "Creeping Barrage",
        "incendiary_bombardment": "Incendiary Bombardment",
        "smoke_shells": "Smoke Shells",
    }

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    @staticmethod
    def _phase_key(value: Any) -> str:
        return str(value or "").strip().upper().replace(" ", "_")

    def is_bridgehead_strike(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Bridgehead Strike")

    def is_combined_arms(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Combined Arms")

    def is_grizzled_company(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Grizzled Company")

    def is_hammer_of_the_emperor(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hammer of the Emperor")

    def is_mechanised_assault(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Mechanised Assault")

    def is_recon_element(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Recon Element")

    def is_siege_regiment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Siege Regiment")

    def is_steel_hammer(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Steel Hammer")

    @staticmethod
    def _entity_id(entity) -> str:
        return str(get_entity_id(entity) or "")

    def _current_game(self):
        if self.army is None:
            return None
        player = getattr(self.army, "player", None)
        if player is None:
            return None
        return getattr(player, "game", None)

    @staticmethod
    def _player_id(player) -> str:
        return str(getattr(player, "id", "") or "")

    def _current_player_id(self, *, game=None) -> str:
        game_obj = game if game is not None else self._current_game()
        current_player = getattr(game_obj, "get_current_player", lambda: None)() if game_obj is not None else None
        return self._player_id(current_player)

    @staticmethod
    def _clear_prefixed_special_rules(sr: dict[str, Any], prefix: str) -> None:
        for key in list(sr.keys()):
            if key == f"{prefix}_active" or key.startswith(f"{prefix}_"):
                sr.pop(key, None)

    @staticmethod
    def _clear_unit_ability_cache(unit) -> None:
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None) if unit is not None else None
        if callable(get_root):
            root = get_root()
        if root is None:
            return
        invalidate = getattr(root, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()
            return
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.clear()
            root._ability_cache = cache

    def _unit_is_on_battlefield(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        is_alive_fn = getattr(root, "is_alive", None)
        if callable(is_alive_fn):
            if not bool(is_alive_fn()):
                return False
        elif getattr(root, "is_alive", True) is False:
            return False
        if not bool(getattr(root, "deployed", True)):
            return False
        reserve_status = str(getattr(root, "reserve_status", "deployed") or "deployed").strip().lower()
        if reserve_status != "deployed":
            return False
        if bool(getattr(root, "embarked_in", None)):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        in_reserves_fn = getattr(root, "is_in_reserves", None)
        if callable(in_reserves_fn) and bool(in_reserves_fn()):
            return False
        return True

    def _iter_game_unit_roots(self, *, game=None) -> list:
        roots = []
        seen: set[str] = set()

        armies = []
        if game is not None:
            for player in list(getattr(game, "players", []) or []):
                if player is None:
                    continue
                get_army = getattr(player, "get_army", None)
                army = get_army() if callable(get_army) else getattr(player, "army", None)
                if army is not None:
                    armies.append(army)
        if self.army is not None and self.army not in armies:
            armies.append(self.army)

        for army in armies:
            for unit in list(getattr(army, "units", []) or []):
                root = self._unit_root(unit)
                if root is None:
                    continue
                root_id = self._entity_id(root)
                if not root_id:
                    root_id = f"unit:{id(root)}"
                if root_id in seen:
                    continue
                seen.add(root_id)
                roots.append(root)
        return roots

    def _friendly_battlefield_roots(self) -> list:
        if self.army is None:
            return []
        out = []
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            if not self._unit_is_on_battlefield(root):
                continue
            root_id = self._entity_id(root)
            if not root_id or root_id in seen:
                continue
            seen.add(root_id)
            out.append(root)
        out.sort(key=lambda unit: self._entity_id(unit))
        return out

    def _enemy_battlefield_roots(self, *, game=None, player=None) -> list:
        if game is None or player is None:
            return []
        get_enemy_units = getattr(game, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        out = []
        seen: set[str] = set()
        for enemy in list(get_enemy_units(player) or []):
            root = self._unit_root(enemy)
            if root is None:
                continue
            if not self._unit_is_on_battlefield(root):
                continue
            root_id = self._entity_id(root)
            if not root_id or root_id in seen:
                continue
            seen.add(root_id)
            out.append(root)
        out.sort(key=lambda unit: self._entity_id(unit))
        return out

    def _distance_between_units(self, unit_a, unit_b, *, game=None) -> float | None:
        if game is None:
            return None
        game_map = getattr(game, "map", None)
        distance_fn = getattr(game_map, "get_distance_between_units", None) if game_map is not None else None
        if not callable(distance_fn):
            distance_fn = getattr(game, "get_distance_between_units", None)
        if not callable(distance_fn):
            return None
        try:
            return float(distance_fn(unit_a, unit_b))
        except (TypeError, ValueError, AttributeError):
            return None

    def _eligible_enemy_units_for_artillery_support(self, *, game=None, player=None) -> list:
        if self.army is None:
            return []
        owner = player if player is not None else getattr(self.army, "player", None)
        game_obj = game if game is not None else getattr(owner, "game", None)
        if owner is None or game_obj is None:
            return []
        enemies = self._enemy_battlefield_roots(game=game_obj, player=owner)
        if not enemies:
            return []
        friendlies = self._friendly_battlefield_roots()
        if not friendlies:
            return enemies
        eligible = []
        for enemy in enemies:
            too_close = False
            for friendly in friendlies:
                distance = self._distance_between_units(enemy, friendly, game=game_obj)
                if distance is None:
                    continue
                if distance <= 12.0 + 1e-6:
                    too_close = True
                    break
            if not too_close:
                eligible.append(enemy)
        eligible.sort(key=lambda unit: self._entity_id(unit))
        return eligible

    def _friendly_units_for_smoke_shells(self) -> list:
        return self._friendly_battlefield_roots()

    def _pending_artillery_support_request(
        self,
        game,
        *,
        decision_type: str,
        ability_key: str,
        army_id: str,
        battle_round: int,
    ) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != str(decision_type or ""):
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != str(ability_key or ""):
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            req_round = self._safe_int(ctx.get("battle_round", 0) or 0, 0)
            if req_round and int(battle_round or 0) and req_round != int(battle_round):
                continue
            return True
        return False

    def siege_regiment_artillery_support_max_units(self, *, game=None) -> int:
        size = getattr(getattr(game, "battlefield", None), "size", None)
        size_name = str(getattr(size, "name", size) or "").strip().upper()
        if size_name == "ONSLAUGHT":
            return 4
        if size_name == "STRIKE_FORCE":
            return 3
        return 2

    def queue_siege_regiment_artillery_support_mode_request(
        self,
        *,
        game=None,
        player=None,
        battle_round: int,
    ) -> bool:
        if not self.is_siege_regiment():
            return False
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return False
        if self.army is None:
            return False
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        army_id = self._entity_id(self.army)
        if not army_id:
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        if self._pending_artillery_support_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability_key=self._ARTILLERY_SUPPORT_MODE_ABILITY,
            army_id=army_id,
            battle_round=int(battle_round or 0),
        ):
            return False

        from ..engine.decisions import DecisionOption, DecisionRequest

        max_units = self.siege_regiment_artillery_support_max_units(game=game)
        options = []
        for mode_key in ("creeping_barrage", "incendiary_bombardment", "smoke_shells"):
            mode_label = str(self._ARTILLERY_SUPPORT_MODE_LABELS.get(mode_key, mode_key) or mode_key)
            options.append(
                DecisionOption.create(
                    mode_label,
                    payload={
                        "artillery_support_mode": mode_key,
                        "mode_key": mode_key,
                    },
                )
            )
        if not options:
            return False

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Artillery Support: select Creeping Barrage, Incendiary Bombardment, or Smoke Shells.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._ARTILLERY_SUPPORT_MODE_ABILITY,
                "ability_name": "Artillery Support",
                "army_id": army_id,
                "battle_round": int(battle_round or 0),
                "max_units": int(max_units),
                "allowed_modes": ["creeping_barrage", "incendiary_bombardment", "smoke_shells"],
                "optional": False,
            },
        )
        request_decision = getattr(game, "request_decision", None)
        if callable(request_decision):
            request_decision(request)
            return True
        return False

    def _queue_siege_regiment_unit_selection_request(
        self,
        *,
        game=None,
        player=None,
        battle_round: int,
        ability_key: str,
        ability_name: str,
        prompt: str,
        allowed_units: list,
        max_units: int,
        allow_skip: bool,
        required_units: int = 0,
        extra_context: dict[str, Any] | None = None,
        skip_pending_check: bool = False,
    ) -> bool:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return False
        if self.army is None:
            return False
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        army_id = self._entity_id(self.army)
        if not army_id:
            return False
        allowed_ids = [
            unit_id
            for unit_id in (self._entity_id(unit) for unit in list(allowed_units or []))
            if unit_id
        ]
        allowed_ids = sorted({unit_id for unit_id in allowed_ids})
        if not allowed_ids:
            return False

        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
        if not bool(skip_pending_check):
            if self._pending_artillery_support_request(
                game,
                decision_type=DECISION_SELECT_REALM_OF_CHAOS_UNITS,
                ability_key=ability_key,
                army_id=army_id,
                battle_round=int(battle_round or 0),
            ):
                return False

        from ..engine.decisions import DecisionOption, DecisionRequest

        options = [DecisionOption.create("Confirm", payload={"action": "confirm"})]
        if bool(allow_skip):
            options.append(DecisionOption.create("None", payload={"action": "skip"}))

        context = {
            "ability": str(ability_key or ""),
            "ability_name": str(ability_name or ""),
            "army_id": army_id,
            "battle_round": int(battle_round or 0),
            "max_units": int(max(0, max_units)),
            "allowed_unit_ids": list(allowed_ids),
            "optional": bool(allow_skip),
        }
        if isinstance(extra_context, dict):
            context.update(dict(extra_context))
        if int(required_units or 0) > 0:
            context["required_units"] = int(required_units)
        if bool(allow_skip):
            context["skip_label"] = "None (do not select units)"

        request = DecisionRequest.create(
            DECISION_SELECT_REALM_OF_CHAOS_UNITS,
            prompt,
            player_id=getattr(owner, "id", None),
            options=options,
            context=context,
        )
        request_decision = getattr(game, "request_decision", None)
        if callable(request_decision):
            request_decision(request)
            return True
        return False

    def _queue_siege_regiment_creeping_barrage_roll_request(
        self,
        *,
        game=None,
        player=None,
        battle_round: int,
        allowed_units: list,
        successful_unit_ids: Iterable[str],
        roll_results: list[dict[str, Any]] | None,
        max_shaken: int,
    ) -> bool:
        successful_ids = self._normalise_unit_ids(successful_unit_ids)
        return self._queue_siege_regiment_unit_selection_request(
            game=game,
            player=player,
            battle_round=battle_round,
            ability_key=self._ARTILLERY_SUPPORT_CREEPING_SELECTION_ABILITY,
            ability_name="Creeping Barrage",
            prompt=(
                "Creeping Barrage: select the next eligible enemy unit to roll for "
                f"({len(successful_ids)}/{int(max_shaken)} shaken so far)."
            ),
            allowed_units=allowed_units,
            max_units=1,
            allow_skip=False,
            required_units=1,
            extra_context={
                "creeping_barrage_max_shaken": int(max_shaken),
                "creeping_barrage_successful_unit_ids": list(successful_ids),
                "creeping_barrage_rolls": list(roll_results or []),
            },
            skip_pending_check=True,
        )

    def _clear_artillery_support_shaken(self, unit) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        remove_modifiers = getattr(root, "remove_characteristic_modifiers_by_source", None)
        if callable(remove_modifiers):
            remove_modifiers(self._ARTILLERY_SUPPORT_SHAKEN_MODIFIER_SOURCE)
        modifiers = list(sr.get("charge_roll_modifiers", []) or [])
        kept = []
        for item in modifiers:
            if isinstance(item, dict) and str(item.get("tag", "") or "") == self._ARTILLERY_SUPPORT_SHAKEN_TAG:
                continue
            kept.append(item)
        if kept:
            sr["charge_roll_modifiers"] = kept
        else:
            sr.pop("charge_roll_modifiers", None)
        for key in (
            "artillery_support_shaken_active",
            "artillery_support_shaken_round",
            "artillery_support_shaken_source",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def _clear_artillery_support_scattered(self, unit) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "artillery_support_scattered_active",
            "artillery_support_scattered_round",
            "artillery_support_scattered_source",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def _clear_artillery_support_smoke_shells(self, unit) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "artillery_support_smoke_shells_active",
            "artillery_support_smoke_shells_round",
            "artillery_support_smoke_shells_source",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def clear_artillery_support_effects(self, *, game=None) -> None:
        for root in self._iter_game_unit_roots(game=game):
            self._clear_artillery_support_shaken(root)
            self._clear_artillery_support_scattered(root)
            self._clear_artillery_support_smoke_shells(root)

    def _apply_artillery_support_shaken(self, unit, *, battle_round: int, source: str) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        self._clear_artillery_support_shaken(root)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}

        source_name = str(source or "Creeping Barrage").strip() or "Creeping Barrage"
        sr["artillery_support_shaken_active"] = True
        sr["artillery_support_shaken_round"] = int(battle_round or 0)
        sr["artillery_support_shaken_source"] = source_name

        add_modifier = getattr(root, "add_characteristic_modifier", None)
        if callable(add_modifier):
            from ..utility.modifiers import Modifier, ModifierOp

            add_modifier(
                "movement",
                Modifier(
                    ModifierOp.ADD,
                    -2,
                    source=self._ARTILLERY_SUPPORT_SHAKEN_MODIFIER_SOURCE,
                ),
            )

        modifiers = list(sr.get("charge_roll_modifiers", []) or [])
        modifiers.append(
            {
                "value": -2,
                "source": f"{source_name} (Shaken)",
                "tag": self._ARTILLERY_SUPPORT_SHAKEN_TAG,
            }
        )
        sr["charge_roll_modifiers"] = modifiers
        root.special_rules = sr

    def _apply_artillery_support_scattered(self, unit, *, battle_round: int, source: str) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["artillery_support_scattered_active"] = True
        sr["artillery_support_scattered_round"] = int(battle_round or 0)
        sr["artillery_support_scattered_source"] = str(source or "Incendiary Bombardment").strip() or "Incendiary Bombardment"
        root.special_rules = sr

    def _apply_artillery_support_smoke_shells(self, unit, *, battle_round: int, source: str) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["artillery_support_smoke_shells_active"] = True
        sr["artillery_support_smoke_shells_round"] = int(battle_round or 0)
        sr["artillery_support_smoke_shells_source"] = str(source or "Smoke Shells").strip() or "Smoke Shells"
        root.special_rules = sr

    @staticmethod
    def _normalise_unit_ids(unit_ids: Iterable[str]) -> list[str]:
        ids = {
            str(unit_id or "").strip()
            for unit_id in list(unit_ids or [])
            if str(unit_id or "").strip()
        }
        return sorted(ids)

    def _resolve_roots_from_ids(self, unit_ids: Iterable[str], *, candidates: list) -> list:
        by_id = {
            self._entity_id(root): root
            for root in list(candidates or [])
            if self._entity_id(root)
        }
        selected = []
        for unit_id in self._normalise_unit_ids(unit_ids):
            root = by_id.get(unit_id)
            if root is not None:
                selected.append(root)
        return selected

    def _apply_siege_regiment_creeping_barrage(
        self,
        *,
        game=None,
        player=None,
        battle_round: int,
    ) -> dict:
        owner = player if player is not None else getattr(self.army, "player", None)
        candidates = self._eligible_enemy_units_for_artillery_support(game=game, player=owner)
        max_units = self.siege_regiment_artillery_support_max_units(game=game)
        if not candidates:
            return {
                "mode": "creeping_barrage",
                "max_units": int(max_units),
                "candidate_unit_ids": [],
                "successful_unit_ids": [],
                "shaken_unit_ids": [],
                "pending_selection": False,
            }

        if len(candidates) <= int(max_units):
            rolls = []
            shaken_ids = []
            for enemy in list(candidates or []):
                roll_value = get_roll("D6")
                enemy_id = self._entity_id(enemy)
                rolls.append({"unit_id": enemy_id, "roll": int(roll_value)})
                if roll_value < 5:
                    continue
                self._apply_artillery_support_shaken(
                    enemy,
                    battle_round=int(battle_round or 0),
                    source="Creeping Barrage",
                )
                if enemy_id:
                    shaken_ids.append(enemy_id)
            return {
                "mode": "creeping_barrage",
                "max_units": int(max_units),
                "candidate_unit_ids": [self._entity_id(unit) for unit in list(candidates or []) if self._entity_id(unit)],
                "shaken_unit_ids": list(shaken_ids),
                "rolls": rolls,
                "pending_selection": False,
            }

        queued = self._queue_siege_regiment_creeping_barrage_roll_request(
            game=game,
            player=owner,
            battle_round=int(battle_round or 0),
            allowed_units=candidates,
            successful_unit_ids=[],
            roll_results=[],
            max_shaken=int(max_units),
        )
        return {
            "mode": "creeping_barrage",
            "max_units": int(max_units),
            "candidate_unit_ids": [self._entity_id(unit) for unit in list(candidates or []) if self._entity_id(unit)],
            "shaken_unit_ids": [],
            "rolls": [],
            "pending_selection": bool(queued),
        }

    def resolve_siege_regiment_creeping_barrage_roll(
        self,
        unit_ids: Iterable[str],
        *,
        game=None,
        player=None,
        battle_round: int = 0,
        allowed_unit_ids: Iterable[str] | None = None,
        successful_unit_ids: Iterable[str] | None = None,
        roll_results: Iterable[dict[str, Any]] | None = None,
        max_shaken: int = 0,
    ) -> dict:
        owner = player if player is not None else getattr(self.army, "player", None)
        game_obj = game if game is not None else getattr(owner, "game", None)
        round_now = int(battle_round or getattr(game_obj, "turn", 0) or 0)
        if int(max_shaken or 0) <= 0:
            max_shaken = self.siege_regiment_artillery_support_max_units(game=game_obj)
        candidates = self._eligible_enemy_units_for_artillery_support(game=game_obj, player=owner)
        if allowed_unit_ids is not None:
            allowed = set(self._normalise_unit_ids(allowed_unit_ids))
            candidates = [root for root in list(candidates or []) if self._entity_id(root) in allowed]
        selected = self._resolve_roots_from_ids(unit_ids, candidates=candidates)[:1]
        if not selected:
            return {
                "mode": "creeping_barrage",
                "max_units": int(max_shaken),
                "pending_selection": False,
                "selected_unit_id": "",
                "roll": 0,
                "rolls": list(roll_results or []),
                "shaken_unit_ids": self._normalise_unit_ids(successful_unit_ids or []),
                "remaining_unit_ids": [self._entity_id(unit) for unit in list(candidates or []) if self._entity_id(unit)],
            }

        target = selected[0]
        target_id = self._entity_id(target)
        roll_value = get_roll("D6")
        rolls = list(roll_results or [])
        rolls.append({"unit_id": target_id, "roll": int(roll_value)})

        shaken_ids = self._normalise_unit_ids(successful_unit_ids or [])
        if roll_value >= 5 and target_id and target_id not in set(shaken_ids):
            self._apply_artillery_support_shaken(
                target,
                battle_round=round_now,
                source="Creeping Barrage",
            )
            shaken_ids.append(target_id)
            shaken_ids = self._normalise_unit_ids(shaken_ids)

        remaining = [
            root
            for root in list(candidates or [])
            if self._entity_id(root) and self._entity_id(root) != target_id
        ]
        queued = False
        if len(shaken_ids) < int(max_shaken) and remaining:
            queued = self._queue_siege_regiment_creeping_barrage_roll_request(
                game=game_obj,
                player=owner,
                battle_round=round_now,
                allowed_units=remaining,
                successful_unit_ids=shaken_ids,
                roll_results=rolls,
                max_shaken=int(max_shaken),
            )

        return {
            "mode": "creeping_barrage",
            "max_units": int(max_shaken),
            "pending_selection": bool(queued),
            "selected_unit_id": str(target_id or ""),
            "roll": int(roll_value),
            "rolls": rolls,
            "shaken_unit_ids": list(shaken_ids),
            "remaining_unit_ids": [self._entity_id(unit) for unit in remaining if self._entity_id(unit)],
        }

    def apply_siege_regiment_artillery_support_mode(
        self,
        mode_key: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ) -> dict:
        normalized = str(mode_key or "").strip().lower()
        if normalized not in self._ARTILLERY_SUPPORT_MODE_LABELS:
            return {}
        owner = player if player is not None else getattr(self.army, "player", None)
        game_obj = game if game is not None else getattr(owner, "game", None)
        round_now = int(battle_round or getattr(game_obj, "turn", 0) or 0)
        max_units = self.siege_regiment_artillery_support_max_units(game=game_obj)

        if normalized == "creeping_barrage":
            return self._apply_siege_regiment_creeping_barrage(
                game=game_obj,
                player=owner,
                battle_round=round_now,
            )

        if normalized == "incendiary_bombardment":
            candidates = self._eligible_enemy_units_for_artillery_support(game=game_obj, player=owner)
            queued = self._queue_siege_regiment_unit_selection_request(
                game=game_obj,
                player=owner,
                battle_round=round_now,
                ability_key=self._ARTILLERY_SUPPORT_INCENDIARY_ABILITY,
                ability_name="Incendiary Bombardment",
                prompt=(
                    "Incendiary Bombardment: select up to "
                    f"{int(max_units)} enemy unit(s) more than 12\" away to become scattered."
                ),
                allowed_units=candidates,
                max_units=int(max_units),
                allow_skip=True,
            )
            return {
                "mode": normalized,
                "max_units": int(max_units),
                "candidate_unit_ids": [self._entity_id(unit) for unit in list(candidates or []) if self._entity_id(unit)],
                "pending_selection": bool(queued),
            }

        candidates = self._friendly_units_for_smoke_shells()
        queued = self._queue_siege_regiment_unit_selection_request(
            game=game_obj,
            player=owner,
            battle_round=round_now,
            ability_key=self._ARTILLERY_SUPPORT_SMOKE_ABILITY,
            ability_name="Smoke Shells",
            prompt=(
                "Smoke Shells: select up to "
                f"{int(max_units)} friendly unit(s) to gain Stealth until the end of the battle round."
            ),
            allowed_units=candidates,
            max_units=int(max_units),
            allow_skip=True,
        )
        return {
            "mode": normalized,
            "max_units": int(max_units),
            "candidate_unit_ids": [self._entity_id(unit) for unit in list(candidates or []) if self._entity_id(unit)],
            "pending_selection": bool(queued),
        }

    def apply_siege_regiment_incendiary_bombardment_selection(
        self,
        unit_ids: Iterable[str],
        *,
        game=None,
        player=None,
        battle_round: int = 0,
        allowed_unit_ids: Iterable[str] | None = None,
    ) -> list[str]:
        owner = player if player is not None else getattr(self.army, "player", None)
        game_obj = game if game is not None else getattr(owner, "game", None)
        round_now = int(battle_round or getattr(game_obj, "turn", 0) or 0)
        max_units = self.siege_regiment_artillery_support_max_units(game=game_obj)
        candidates = self._eligible_enemy_units_for_artillery_support(game=game_obj, player=owner)
        if allowed_unit_ids is not None:
            allowed = set(self._normalise_unit_ids(allowed_unit_ids))
            candidates = [root for root in list(candidates or []) if self._entity_id(root) in allowed]
        selected = self._resolve_roots_from_ids(unit_ids, candidates=candidates)[: int(max_units)]
        applied_ids = []
        for root in selected:
            self._apply_artillery_support_scattered(
                root,
                battle_round=round_now,
                source="Incendiary Bombardment",
            )
            root_id = self._entity_id(root)
            if root_id:
                applied_ids.append(root_id)
        return applied_ids

    def apply_siege_regiment_smoke_shells_selection(
        self,
        unit_ids: Iterable[str],
        *,
        game=None,
        battle_round: int = 0,
        allowed_unit_ids: Iterable[str] | None = None,
    ) -> list[str]:
        game_obj = game if game is not None else self._current_game()
        round_now = int(battle_round or getattr(game_obj, "turn", 0) or 0)
        max_units = self.siege_regiment_artillery_support_max_units(game=game_obj)
        candidates = self._friendly_units_for_smoke_shells()
        if allowed_unit_ids is not None:
            allowed = set(self._normalise_unit_ids(allowed_unit_ids))
            candidates = [root for root in list(candidates or []) if self._entity_id(root) in allowed]
        selected = self._resolve_roots_from_ids(unit_ids, candidates=candidates)[: int(max_units)]
        applied_ids = []
        for root in selected:
            self._apply_artillery_support_smoke_shells(
                root,
                battle_round=round_now,
                source="Smoke Shells",
            )
            root_id = self._entity_id(root)
            if root_id:
                applied_ids.append(root_id)
        return applied_ids

    def apply_siege_regiment_creeping_barrage_selection(
        self,
        unit_ids: Iterable[str],
        *,
        game=None,
        player=None,
        battle_round: int = 0,
        allowed_unit_ids: Iterable[str] | None = None,
    ) -> list[str]:
        owner = player if player is not None else getattr(self.army, "player", None)
        game_obj = game if game is not None else getattr(owner, "game", None)
        round_now = int(battle_round or getattr(game_obj, "turn", 0) or 0)
        max_units = self.siege_regiment_artillery_support_max_units(game=game_obj)
        candidates = self._eligible_enemy_units_for_artillery_support(game=game_obj, player=owner)
        if allowed_unit_ids is not None:
            allowed = set(self._normalise_unit_ids(allowed_unit_ids))
            candidates = [root for root in list(candidates or []) if self._entity_id(root) in allowed]
        selected = self._resolve_roots_from_ids(unit_ids, candidates=candidates)[: int(max_units)]
        applied_ids = []
        for root in selected:
            self._apply_artillery_support_shaken(
                root,
                battle_round=round_now,
                source="Creeping Barrage",
            )
            root_id = self._entity_id(root)
            if root_id:
                applied_ids.append(root_id)
        return applied_ids

    def siege_regiment_smoke_shells_stealth_applies(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("artillery_support_smoke_shells_active")):
            return False
        marked_round = self._safe_int(sr.get("artillery_support_smoke_shells_round", 0) or 0, 0)
        if marked_round <= 0:
            return True
        game = self._current_game()
        current_round = self._safe_int(getattr(game, "turn", 0) or 0, 0)
        if current_round <= 0:
            return True
        return marked_round == current_round

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        game_obj = game if game is not None else self._current_game()
        self.cleanup_hammer_of_the_emperor_battle_round_effects(
            battle_round=int(battle_round or 0),
            game=game_obj,
        )
        self.clear_artillery_support_effects(game=game_obj)
        if not self.is_siege_regiment():
            return
        if game_obj is None or not bool(getattr(game_obj, "is_authoritative", True)):
            return
        owner = getattr(self.army, "player", None) if self.army is not None else None
        if owner is None:
            return
        self.queue_siege_regiment_artillery_support_mode_request(
            game=game_obj,
            player=owner,
            battle_round=int(battle_round or 0),
        )

    def _unit_root(self, unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
            if root is not None:
                return root
        return unit

    def _unit_in_army(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        army = self.army
        if army is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        if callable(get_parent_army):
            parent = get_parent_army()
            if parent is not None:
                return parent is army
        return root in list(getattr(army, "units", []) or [])

    @staticmethod
    def _add_keyword_once(entity, keyword: str) -> None:
        if entity is None:
            return
        kw = str(keyword or "").strip()
        if not kw:
            return
        keywords = getattr(entity, "keywords", None)
        if not isinstance(keywords, list):
            return
        existing = {str(value or "").strip().lower() for value in keywords}
        if kw.lower() not in existing:
            keywords.append(kw)

    def _iter_unique_army_roots(self) -> list:
        if self.army is None:
            return []
        out = []
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root) or f"unit:{id(root)}"
            if root_id in seen:
                continue
            seen.add(root_id)
            out.append(root)
        out.sort(key=lambda unit: self._entity_id(unit) or str(id(unit)))
        return out

    def _unit_is_astra_militarum(self, unit) -> bool:
        return self._unit_has_keyword(unit, "ASTRA MILITARUM")

    def _unit_is_squadron(self, unit) -> bool:
        return self._unit_has_keyword(unit, "SQUADRON")

    def _unit_is_titanic(self, unit) -> bool:
        return self._unit_has_keyword(unit, "TITANIC")

    def _steel_hammer_titanic_character_candidates(self) -> list:
        if not self.is_steel_hammer():
            return []
        candidates = []
        for root in self._iter_unique_army_roots():
            if not self._unit_in_army(root):
                continue
            if not self._unit_is_astra_militarum(root):
                continue
            if not self._unit_is_titanic(root):
                continue
            candidates.append(root)
        candidates.sort(key=lambda unit: self._entity_id(unit))
        return candidates

    def _pending_steel_hammer_character_selection_request(self, game, *, army_id: str) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_REALM_OF_CHAOS_UNITS:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            ability = str(ctx.get("ability", "") or "").strip().lower()
            if ability != self._STEEL_HAMMER_TITANIC_CHARACTER_SELECTION_ABILITY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            return True
        return False

    def queue_steel_hammer_titanic_character_selection_request(self, *, game=None, player=None) -> None:
        if not self.is_steel_hammer():
            return
        if self.army is None:
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if bool(getattr(self, "_steel_hammer_titanic_character_selection_resolved", False)):
            return

        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        candidates = list(self._steel_hammer_titanic_character_candidates() or [])
        if not candidates:
            self._steel_hammer_titanic_character_selection_resolved = True
            return

        army_id = self._entity_id(self.army)
        if self._pending_steel_hammer_character_selection_request(game, army_id=army_id):
            return

        candidate_ids = [self._entity_id(unit) for unit in candidates if self._entity_id(unit)]
        if not candidate_ids:
            self._steel_hammer_titanic_character_selection_resolved = True
            return

        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
        from ..engine.decisions import DecisionOption, DecisionRequest

        request = DecisionRequest.create(
            DECISION_SELECT_REALM_OF_CHAOS_UNITS,
            "Ceaseless Cannonade: select ASTRA MILITARUM TITANIC units to gain CHARACTER.",
            player_id=getattr(owner, "id", None),
            options=[
                DecisionOption.create("Confirm", payload={"action": "confirm"}),
                DecisionOption.create("None", payload={"action": "skip"}),
            ],
            context={
                "army_id": army_id,
                "ability": self._STEEL_HAMMER_TITANIC_CHARACTER_SELECTION_ABILITY,
                "ability_name": "Ceaseless Cannonade",
                "phase": "Muster Armies step",
                "allowed_unit_ids": list(candidate_ids),
                "title": "Ceaseless Cannonade",
                "subtitle": "Select any ASTRA MILITARUM TITANIC units.",
                "instruction": "Selected TITANIC units gain the CHARACTER keyword.",
                "skip_label": "None (do not select TITANIC units)",
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)

    def steel_hammer_titanic_character_selection_is_valid(self, unit_ids, *, game=None) -> tuple[bool, str]:
        del game
        if not self.is_steel_hammer():
            return False, "Ceaseless Cannonade is not active for this army."
        if unit_ids is None:
            return True, ""
        if not isinstance(unit_ids, list):
            return False, "Ceaseless Cannonade selection requires unit_ids."
        selected = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        candidates = {
            self._entity_id(unit): unit
            for unit in list(self._steel_hammer_titanic_character_candidates() or [])
            if self._entity_id(unit)
        }
        for unit_id in selected:
            if unit_id not in candidates:
                return False, "Ceaseless Cannonade selection contains an ineligible unit."
        return True, ""

    def apply_steel_hammer_titanic_character_selection(self, unit_ids, *, game=None) -> list[str]:
        selected = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        valid, _reason = self.steel_hammer_titanic_character_selection_is_valid(selected, game=game)
        if not valid:
            return []
        candidate_by_id = {
            self._entity_id(unit): unit
            for unit in list(self._steel_hammer_titanic_character_candidates() or [])
            if self._entity_id(unit)
        }
        applied_ids: list[str] = []
        for unit_id in selected:
            root = candidate_by_id.get(unit_id)
            if root is None:
                continue
            self._add_keyword_once(root, "Character")
            for model in list(getattr(root, "models", []) or []):
                self._add_keyword_once(model, "Character")
            applied_ids.append(unit_id)
        self.steel_hammer_character_titanic_unit_ids = tuple(applied_ids)
        if self.army is not None:
            setattr(self.army, "steel_hammer_character_titanic_unit_ids", list(applied_ids))
        self._steel_hammer_titanic_character_selection_resolved = True
        return list(applied_ids)

    def _steel_hammer_ceaseless_unit(self, unit):
        if not self.is_steel_hammer():
            return None
        root = self._unit_root(unit)
        if root is None:
            return None
        if not self._unit_in_army(root):
            return None
        if not self._unit_is_astra_militarum(root):
            return None
        if not (self._unit_is_titanic(root) or self._unit_is_squadron(root)):
            return None
        return root

    @staticmethod
    def _weapon_profile_is_indirect_fire(weapon_profile) -> bool:
        is_indirect = getattr(weapon_profile, "is_indirect_fire", None)
        if callable(is_indirect):
            return bool(is_indirect())
        return False

    def _is_controlling_players_shooting_phase_for_unit(self, unit, *, game=None) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        game_obj = game
        if game_obj is None:
            army = getattr(root, "get_parent_army", lambda: None)()
            game_obj = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        player = getattr(self.army, "player", None) if self.army is not None else None
        if game_obj is None or player is None:
            return False
        is_shooting_phase = getattr(game_obj, "is_shooting_phase", None)
        get_current_player = getattr(game_obj, "get_current_player", None)
        return bool(
            callable(is_shooting_phase)
            and callable(get_current_player)
            and is_shooting_phase()
            and get_current_player() is player
        )

    def _target_engaged_by_other_friendly(self, shooter, target_unit, *, game_map) -> bool:
        if shooter is None or target_unit is None or game_map is None:
            return True
        shooter_root = self._unit_root(shooter)
        for friendly in list(game_map.get_friendly_units(shooter) or []):
            friendly_root = self._unit_root(friendly)
            if friendly_root is None or friendly_root is shooter_root:
                continue
            alive = getattr(friendly_root, "is_alive", None)
            if callable(alive):
                if not bool(alive()):
                    continue
            elif not bool(getattr(friendly_root, "is_alive", True)):
                continue
            if not bool(getattr(friendly_root, "deployed", True)):
                continue
            if game_map.is_within_engagement_range(friendly_root, target_unit):
                return True
        return False

    def ceaseless_cannonade_allows_ranged_target(
        self,
        unit,
        target_unit,
        *,
        weapon_profile=None,
        game=None,
        game_map=None,
    ) -> bool:
        del weapon_profile
        root = self._steel_hammer_ceaseless_unit(unit)
        if root is None or target_unit is None or game_map is None:
            return False
        if not self._is_controlling_players_shooting_phase_for_unit(root, game=game):
            return False
        if not game_map.is_within_engagement_range(root, target_unit):
            return False
        return not self._target_engaged_by_other_friendly(root, target_unit, game_map=game_map)

    def ceaseless_cannonade_ignores_big_guns_hit_penalty(
        self,
        unit,
        target_unit,
        *,
        weapon_profile=None,
        game=None,
        game_map=None,
    ) -> bool:
        if self._weapon_profile_is_indirect_fire(weapon_profile):
            return False
        return self.ceaseless_cannonade_allows_ranged_target(
            unit,
            target_unit,
            weapon_profile=weapon_profile,
            game=game,
            game_map=game_map,
        )

    @staticmethod
    def _model_has_keyword(model, keyword: str) -> bool:
        if model is None:
            return False
        kw = str(keyword or "").strip()
        if not kw:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any(kw))
        raw = [str(k or "") for k in (getattr(model, "keywords", []) or [])]
        raw += [str(k or "") for k in (getattr(model, "faction_keywords", []) or [])]
        return kw.lower() in {k.lower() for k in raw if str(k).strip()}

    def _model_or_unit_has_keyword(self, model, unit, keyword: str) -> bool:
        root = self._unit_root(unit)
        if self._model_has_keyword(model, keyword):
            return True
        return self._unit_has_keyword(root, keyword)

    def _attached_unit_was_set_up_this_turn(self, unit, *, game=None) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False

        was_set_up = getattr(root, "_was_set_up_this_turn", None)
        if callable(was_set_up):
            return bool(was_set_up(game=game))

        if bool(getattr(root, "arrived_from_reserves_this_turn", False)):
            return True

        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "reinforced_this_round", False)):
            return True

        game_obj = game
        if game_obj is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game_obj = getattr(player, "game", None) if player is not None else None
        if game_obj is None:
            return False

        turn_now = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        reserve_turn = self._safe_int(getattr(root, "reserve_turn_deployed", 0) or 0, 0)
        return bool(turn_now > 0 and reserve_turn == turn_now)

    def _attached_unit_disembarked_from_transport_this_round(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        if round_state is None:
            return False
        if not bool(getattr(round_state, "disembarked_this_round", False)):
            return False
        transport_id = str(getattr(round_state, "disembarked_from_transport_id", "") or "").strip()
        if not transport_id:
            return False
        game_obj = getattr(getattr(self.army, "player", None), "game", None) if self.army is not None else None
        if game_obj is None:
            return True
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return True
        try:
            disembark_round = int(sr.get("voice_of_command_disembark_round", 0) or 0)
        except (TypeError, ValueError):
            disembark_round = 0
        if disembark_round > 0:
            try:
                current_round = int(getattr(game_obj, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_round = 0
            if current_round > 0 and current_round != disembark_round:
                return False
        current_owner = str(getattr(getattr(game_obj, "get_current_player", lambda: None)(), "id", "") or "").strip()
        disembark_owner = str(sr.get("voice_of_command_disembark_owner", "") or "").strip()
        if current_owner and disembark_owner and current_owner != disembark_owner:
            return False
        return True

    def _unit_within_any_objective_range(self, unit, *, game_map=None) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        checker = getattr(root, "is_within_any_objective_range", None)
        if not callable(checker):
            return False
        return bool(checker(game_map=game_map))

    def _unit_is_astra_militarum_infantry_model(self, unit, model) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self.unit_is_astra_militarum(root):
            return False
        return self._model_or_unit_has_keyword(model, root, "INFANTRY")

    def _unit_is_militarum_tempestus_model(self, unit, model) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self.unit_is_astra_militarum(root):
            return False
        return self._model_or_unit_has_keyword(model, root, "MILITARUM TEMPESTUS")

    def _unit_is_regiment_model(self, unit, model) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self.unit_is_astra_militarum(root):
            return False
        return self._model_or_unit_has_keyword(model, root, "REGIMENT")

    def _unit_is_squadron_model(self, unit, model) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self.unit_is_astra_militarum(root):
            return False
        return self._model_or_unit_has_keyword(model, root, "SQUADRON")

    def _unit_is_squadron_unit(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self.unit_is_astra_militarum(root):
            return False
        return self._unit_has_keyword(root, "SQUADRON")

    def _unit_is_walker_or_regiment_model(self, unit, model) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self.unit_is_astra_militarum(root):
            return False
        if self._model_or_unit_has_keyword(model, root, "WALKER"):
            return True
        return self._model_or_unit_has_keyword(model, root, "REGIMENT")

    def _target_is_monster_or_vehicle(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if self._unit_has_keyword(root, "MONSTER"):
            return True
        if self._unit_has_keyword(root, "VEHICLE"):
            return True
        return bool(getattr(root, "is_monster", False) or getattr(root, "is_vehicle", False))

    def unit_is_astra_militarum(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "ASTRA MILITARUM"):
            return True
        has_keywords = bool(getattr(unit, "keywords", None)) or bool(getattr(unit, "faction_keywords", None))
        if has_keywords:
            return False
        return self._army_faction_matches(self.faction_id)

    def unit_is_officer(self, unit) -> bool:
        return self._unit_has_keyword(unit, "OFFICER")

    def _unit_is_below_half_strength(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        checker = getattr(root, "is_below_half_strength", None)
        if callable(checker):
            return bool(checker())
        return bool(getattr(root, "is_below_half_strength", False))

    @staticmethod
    def _weapon_profile_is_ranged(profile) -> bool:
        if profile is None:
            return True
        parent_wargear = getattr(profile, "parent_wargear", None)
        is_ranged = getattr(parent_wargear, "is_ranged", None) if parent_wargear is not None else None
        if callable(is_ranged):
            return bool(is_ranged())
        return True

    def _hammer_turn_effect_state(self, unit, *, prefix: str, game=None):
        if not self.is_hammer_of_the_emperor():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(f"{prefix}_active", False)):
            return None, None
        game_obj = game if game is not None else self._current_game()
        current_turn = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        marked_turn = self._safe_int(sr.get(f"{prefix}_turn", 0) or 0, 0)
        if marked_turn and current_turn and marked_turn != current_turn:
            return None, None
        owner_id = str(sr.get(f"{prefix}_turn_owner", "") or "")
        active_player_id = self._current_player_id(game=game_obj)
        if owner_id and active_player_id and owner_id != active_player_id:
            return None, None
        return root, sr

    def _hammer_phase_effect_state(self, unit, *, prefix: str, game=None):
        root, sr = self._hammer_turn_effect_state(unit, prefix=prefix, game=game)
        if root is None or not isinstance(sr, dict):
            return None, None
        game_obj = game if game is not None else self._current_game()
        current_phase = self._phase_key(getattr(getattr(game_obj, "phase", None), "name", "") or "")
        marked_phase = self._phase_key(sr.get(f"{prefix}_expires_phase", "") or "")
        if current_phase and marked_phase and current_phase != marked_phase:
            return None, None
        return root, sr

    def _hammer_battle_round_effect_state(self, unit, *, prefix: str, game=None):
        if not self.is_hammer_of_the_emperor():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(f"{prefix}_active", False)):
            return None, None
        game_obj = game if game is not None else self._current_game()
        current_round = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        marked_round = self._safe_int(sr.get(f"{prefix}_battle_round", 0) or 0, 0)
        if marked_round and current_round and marked_round != current_round:
            return None, None
        owner_id = str(sr.get(f"{prefix}_owner", "") or "")
        army_owner_id = self._player_id(getattr(self.army, "player", None))
        if owner_id and army_owner_id and owner_id != army_owner_id:
            return None, None
        return root, sr

    def _siege_turn_effect_state(self, unit, *, prefix: str, game=None):
        if not self.is_siege_regiment():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(f"{prefix}_active", False)):
            return None, None
        game_obj = game if game is not None else self._current_game()
        current_turn = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        marked_turn = self._safe_int(sr.get(f"{prefix}_turn", 0) or 0, 0)
        if marked_turn and current_turn and marked_turn != current_turn:
            return None, None
        owner_id = str(sr.get(f"{prefix}_turn_owner", "") or "")
        army_owner_id = self._player_id(getattr(self.army, "player", None))
        if owner_id and army_owner_id and owner_id != army_owner_id:
            return None, None
        return root, sr

    def _siege_phase_effect_state(self, unit, *, prefix: str, game=None):
        root, sr = self._siege_turn_effect_state(unit, prefix=prefix, game=game)
        if root is None or not isinstance(sr, dict):
            return None, None
        game_obj = game if game is not None else self._current_game()
        current_phase = self._phase_key(getattr(getattr(game_obj, "phase", None), "name", "") or "")
        marked_phase = self._phase_key(sr.get(f"{prefix}_expires_phase", "") or "")
        if current_phase and marked_phase and current_phase != marked_phase:
            return None, None
        return root, sr

    def _unit_has_order(self, unit) -> bool:
        if unit is None:
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        voice = getattr(self.army, "voice_of_command", None) if self.army is not None else None
        has_any_order = getattr(voice, "attached_unit_has_any_order", None) if voice is not None else None
        if callable(has_any_order):
            return bool(has_any_order(root))
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict):
            if str(sr.get("voice_of_command_order_key", "") or "").strip():
                return True
            if list(sr.get("voice_of_command_additional_order_keys", []) or []):
                return True
            if list(sr.get("voice_of_command_temp_order_keys", []) or []):
                return True
        return False

    def _attached_unit_has_order(self, unit) -> bool:
        if unit is None:
            return False
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
        members = None
        get_members = getattr(root, "get_attached_unit_members", None)
        if callable(get_members):
            members = list(get_members() or [])
        if not members:
            members = [root]
        for member in members:
            if self._unit_has_order(member):
                return True
        return False

    def _enhancement_bearer_alive(self, unit, sr, *, bearer_key: str = "") -> bool:
        if unit is None or not isinstance(sr, dict):
            return False
        key_name = str(bearer_key or "").strip()
        bearer_id = ""
        if key_name:
            bearer_id = str(sr.get(key_name, "") or "").strip()
        if not bearer_id:
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
        if not bearer_id:
            return True
        for model in list(getattr(unit, "models", []) or []):
            if str(get_entity_id(model) or "").strip() != bearer_id:
                continue
            alive_attr = getattr(model, "is_alive", True)
            return bool(alive_attr() if callable(alive_attr) else alive_attr)
        return False

    def _attached_unit_enhancement_source(self, unit, enhancement_flag: str) -> tuple[object | None, dict | None]:
        root = self._unit_root(unit)
        if root is None:
            return None, None
        members = []
        get_members = getattr(root, "get_attached_unit_members", None)
        if callable(get_members):
            members = list(get_members() or [])
        if not members:
            members = [root]
        attached_leaders = list(getattr(root, "attached_leaders", []) or [])
        for leader in attached_leaders:
            if leader is None or leader in members:
                continue
            members.append(leader)
        for member in list(members or []):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get(str(enhancement_flag or "").strip(), False)):
                continue
            if not self._enhancement_bearer_alive(member, sr):
                continue
            return member, sr
        return None, None

    def combined_arms_grand_strategist_orders_bonus(self, unit) -> int:
        if not self.is_combined_arms():
            return 0
        root = self._unit_root(unit)
        if root is None:
            return 0
        if not self._unit_in_army(root):
            return 0
        if not self.unit_is_officer(root):
            return 0
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("enhancement_grand_strategist", False)):
            return 0
        if not self._enhancement_bearer_alive(root, sr, bearer_key="enhancement_grand_strategist_bearer_model_id"):
            return 0
        try:
            bonus = int(sr.get("enhancement_grand_strategist_additional_orders", 1) or 1)
        except (TypeError, ValueError):
            bonus = 1
        return max(0, int(bonus))

    def combined_arms_reactive_command_trigger_spec(self, unit) -> dict | None:
        if not self.is_combined_arms():
            return None
        root = self._unit_root(unit)
        if root is None:
            return None
        if not self._unit_in_army(root):
            return None
        if not self.unit_is_officer(root):
            return None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("enhancement_reactive_command", False)):
            return None
        if not self._enhancement_bearer_alive(root, sr, bearer_key="enhancement_reactive_command_bearer_model_id"):
            return None
        try:
            trigger_range = float(sr.get("enhancement_reactive_command_trigger_range", 9.0) or 9.0)
        except (TypeError, ValueError):
            trigger_range = 9.0
        try:
            orders = int(sr.get("enhancement_reactive_command_additional_orders_per_trigger", 1) or 1)
        except (TypeError, ValueError):
            orders = 1
        source = str(sr.get("enhancement_reactive_command_source", "") or "Reactive Command").strip() or "Reactive Command"
        return {
            "range": max(0.0, float(trigger_range)),
            "orders": max(1, int(orders)),
            "source": source,
            "does_not_count_towards_order_limit": bool(
                sr.get("enhancement_reactive_command_does_not_count_towards_order_limit", True)
            ),
        }

    def combined_arms_drill_commander_crit_hit_threshold(
        self,
        attacker_model,
        *,
        attack_type: str = "any",
        weapon_profile=None,
    ) -> tuple[int, str]:
        if not self.is_combined_arms():
            return 0, ""
        atype = str(attack_type or "any").strip().lower()
        if atype not in {"any", "ranged"}:
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_ranged = bool(getattr(parent, "is_ranged", lambda: False)()) if parent is not None else False
            if not is_ranged:
                return 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        if not self._unit_in_army(root):
            return 0, ""
        source_unit, sr = self._attached_unit_enhancement_source(root, "enhancement_drill_commander")
        if source_unit is None or not isinstance(sr, dict):
            return 0, ""
        attack_kind = str(sr.get("enhancement_drill_commander_attack_type", "ranged") or "ranged").strip().lower()
        if attack_kind and attack_kind not in {"any", atype}:
            return 0, ""
        requires_stationary = bool(sr.get("enhancement_drill_commander_requires_remained_stationary", True))
        remained_stationary = bool(getattr(getattr(root, "round_state", None), "remained_stationary_this_round", False))
        if requires_stationary and not remained_stationary:
            return 0, ""
        try:
            threshold = int(sr.get("enhancement_drill_commander_crit_hit_threshold", 5) or 5)
        except (TypeError, ValueError):
            threshold = 5
        threshold = int(max(2, min(6, threshold)))
        source = str(sr.get("enhancement_drill_commander_source", "") or "Drill Commander").strip() or "Drill Commander"
        return threshold, source

    def ruthless_discipline_orders_bonus(self, unit) -> int:
        if not self.is_grizzled_company():
            return 0
        if unit is None:
            return 0
        if not self.unit_is_astra_militarum(unit):
            return 0
        if not self.unit_is_officer(unit):
            return 0
        return 1

    def ruthless_discipline_reroll_hit_ones(self, unit) -> bool:
        if not self.is_grizzled_company():
            return False
        if unit is None:
            return False
        if not self.unit_is_astra_militarum(unit):
            return False
        return self._attached_unit_has_order(unit)

    def iron_tread_advance_no_roll_effect(self, unit) -> dict | None:
        if not self.is_hammer_of_the_emperor():
            return None
        root = self._unit_root(unit)
        if root is None:
            return None
        if not self._unit_in_army(root):
            return None
        if not self._unit_is_squadron_unit(root):
            return None
        return {
            "distance": 6,
            "source": "Iron Tread",
            "tag": "detachment:iron_tread",
        }

    def iron_tread_allows_advance_move_within_engagement_range(self, unit) -> bool:
        if not self.is_hammer_of_the_emperor():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        return self._unit_is_squadron_unit(root)

    def hammer_of_the_emperor_regimental_banner_objective_control_bonus(
        self,
        model,
        *,
        unit=None,
    ) -> tuple[int, str]:
        if not self.is_hammer_of_the_emperor():
            return 0, ""
        if model is None:
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        root = self._unit_root(source_unit)
        if root is None:
            return 0, ""
        if not self._unit_in_army(root):
            return 0, ""
        owner_unit, sr = self._attached_unit_enhancement_source(root, "enhancement_regimental_banner")
        if owner_unit is None or not isinstance(sr, dict):
            return 0, ""
        try:
            bonus = int(sr.get("enhancement_regimental_banner_objective_control_bonus", 3) or 3)
        except (TypeError, ValueError):
            bonus = 3
        if bonus <= 0:
            return 0, ""
        bearer_id = str(
            sr.get("enhancement_regimental_banner_bearer_model_id", "")
            or sr.get("enhancement_bearer_model_id", "")
            or ""
        ).strip()
        if not bearer_id:
            get_bearer = getattr(owner_unit, "_get_enhancement_bearer_model", None)
            bearer = get_bearer() if callable(get_bearer) else None
            bearer_id = str(get_entity_id(bearer) or "").strip()
        model_id = str(get_entity_id(model) or "").strip()
        if bearer_id and model_id and bearer_id != model_id:
            return 0, ""
        source = str(sr.get("enhancement_regimental_banner_source", "") or "Regimental Banner").strip() or "Regimental Banner"
        return int(bonus), source

    def hammer_of_the_emperor_veteran_crew_hit_reroll_mods(
        self,
        attacker_model,
        target_unit=None,
        *,
        attack_type: str = "any",
        game=None,
        game_map=None,
        target_visible=None,
    ) -> dict:
        _ = target_unit
        _ = game
        _ = game_map
        _ = target_visible
        if not self.is_hammer_of_the_emperor():
            return {}
        if str(attack_type or "any").strip().lower() != "ranged":
            return {}
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return {}
        if not self._unit_in_army(root):
            return {}
        source_unit, sr = self._attached_unit_enhancement_source(root, "enhancement_veteran_crew")
        if source_unit is None or not isinstance(sr, dict):
            return {}
        attack_kind = str(sr.get("enhancement_veteran_crew_attack_type", "ranged") or "ranged").strip().lower()
        if attack_kind and attack_kind not in {"any", "ranged"}:
            return {}
        reroll_values: list[int] = []
        for raw in list(sr.get("enhancement_veteran_crew_reroll_hit_values", (1,)) or (1,)):
            try:
                value = int(raw)
            except (TypeError, ValueError):
                continue
            if value < 1 or value > 6:
                continue
            reroll_values.append(value)
        if not reroll_values:
            reroll_values = [1]
        deduped_values = tuple(sorted(set(reroll_values)))
        source = str(sr.get("enhancement_veteran_crew_source", "") or "Veteran Crew").strip() or "Veteran Crew"
        reasons = tuple(f"{source}: re-roll Hit roll of {value}" for value in deduped_values)
        return {
            "reroll_values": deduped_values,
            "reroll_reasons": reasons,
        }

    def armoured_fist_wound_bonus(
        self,
        attacker_model,
        *,
        attack_type: str = "any",
    ) -> tuple[int, str]:
        if not self.is_mechanised_assault():
            return 0, ""
        if str(attack_type or "any").strip().lower() != "ranged":
            return 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        if not self._unit_in_army(root):
            return 0, ""
        if not self.unit_is_astra_militarum(root):
            return 0, ""
        if not self._attached_unit_disembarked_from_transport_this_round(root):
            return 0, ""
        return 1, "Armoured Fist"

    def masters_of_camouflage_benefit_of_cover(
        self,
        target_model,
        *,
        attack_type: str = "any",
    ) -> tuple[bool, str]:
        if not self.is_recon_element():
            return False, ""
        if str(attack_type or "any").strip().lower() != "ranged":
            return False, ""
        unit = getattr(target_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return False, ""
        if not self._unit_in_army(root):
            return False, ""
        if not self._unit_is_walker_or_regiment_model(root, target_model):
            return False, ""
        return True, "Masters of Camouflage"

    def masters_of_camouflage_save_characteristic_bonus(
        self,
        target_model,
        attack_instance=None,
        *,
        attack_type: str = "any",
    ) -> tuple[int, str]:
        if not self.is_recon_element():
            return 0, ""
        if str(attack_type or "any").strip().lower() != "ranged":
            return 0, ""
        unit = getattr(target_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        if not self._unit_in_army(root):
            return 0, ""
        if not self._unit_is_walker_or_regiment_model(root, target_model):
            return 0, ""
        atk = attack_instance if isinstance(attack_instance, dict) else {}
        if not bool(atk.get("benefit_of_cover", False)):
            return 0, ""

        source_text = str(atk.get("benefit_of_cover_source", "") or "").strip()
        if not source_text:
            return 1, "Masters of Camouflage"
        sources = [part.strip().lower() for part in source_text.split(",") if part.strip()]
        if not sources:
            return 1, "Masters of Camouflage"
        if any(part != "masters of camouflage" for part in sources):
            return 1, "Masters of Camouflage"
        return 0, ""

    def recon_element_courageous_diversion_target_hit_penalty(
        self,
        target_unit,
        *,
        attacker_model=None,
        weapon_profile=None,
        attack_instance=None,
        game=None,
    ) -> tuple[int, str]:
        _ = attack_instance
        if not self.is_recon_element():
            return 0, ""
        root = self._unit_root(target_unit)
        if root is None or not self._unit_in_army(root):
            return 0, ""
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("recon_courageous_diversion_active", False)):
            return 0, ""
        parent_wargear = getattr(weapon_profile, "parent_wargear", None)
        is_ranged = bool(parent_wargear and callable(getattr(parent_wargear, "is_ranged", None)) and parent_wargear.is_ranged())
        if not is_ranged:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._unit_root(attacker_unit)
        game_obj = game if game is not None else self._current_game()
        game_map = getattr(game_obj, "map", None) if game_obj is not None else None
        closest_check = getattr(attacker_root, "is_target_closest_eligible", None) if attacker_root is not None else None
        if not callable(closest_check) or game_map is None:
            return 0, ""
        if not bool(closest_check(attacker_model, weapon_profile, root, game_map)):
            return 0, ""
        source = str(sr.get("recon_courageous_diversion_source", "") or "COURAGEOUS DIVERSION").strip() or "COURAGEOUS DIVERSION"
        return 1, source

    def activate_recon_element_scramble_field(self, unit, *, game=None, source: str = "") -> bool:
        if not self.is_recon_element():
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root) or not self._unit_is_on_battlefield(root):
            return False
        game_obj = game if game is not None else self._current_game()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["recon_scramble_field_active"] = True
        sr["recon_scramble_field_range"] = 12.0
        sr["recon_scramble_field_horizontal_only"] = False
        sr["recon_scramble_field_expires_phase"] = "MOVEMENT_PHASE"
        sr["recon_scramble_field_turn"] = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        sr["recon_scramble_field_turn_owner"] = self._player_id(getattr(self.army, "player", None))
        sr["recon_scramble_field_source"] = str(source or "SCRAMBLE FIELD").strip() or "SCRAMBLE FIELD"
        root.special_rules = sr
        return True

    def recon_element_scramble_field_reserves_denial(self, unit, *, game=None) -> dict | None:
        resolved_game = game if game is not None else self._current_game()
        if resolved_game is None or not bool(getattr(resolved_game, "reinforcements_step_active", False)):
            return None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root) or not self._unit_is_on_battlefield(root):
            return None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("recon_scramble_field_active", False)):
            return None
        try:
            denial_range = float(sr.get("recon_scramble_field_range", 12.0) or 12.0)
        except (TypeError, ValueError):
            denial_range = 12.0
        if denial_range <= 0.0:
            return None
        horizontal_only = bool(sr.get("recon_scramble_field_horizontal_only", False))
        source_model_id = ""
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        for model in list(models or []):
            alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not is_alive:
                continue
            source_model_id = str(get_entity_id(model) or "").strip()
            if source_model_id:
                break
        return {
            "range": float(denial_range),
            "horizontal_only": bool(horizontal_only),
            "source": str(sr.get("recon_scramble_field_source", "") or "SCRAMBLE FIELD").strip() or "SCRAMBLE FIELD",
            "source_model_id": source_model_id,
        }

    def only_the_best_hit_reroll_mods(
        self,
        attacker_model,
        target_unit=None,
        *,
        attack_type: str = "any",
        game=None,
        game_map=None,
        target_visible=None,
    ) -> dict:
        _ = target_unit
        _ = game
        _ = game_map
        _ = target_visible
        if not self.is_bridgehead_strike():
            return {}
        if str(attack_type or "any").strip().lower() != "ranged":
            return {}
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return {}
        if not self._unit_in_army(root):
            return {}
        if not self._unit_is_astra_militarum_infantry_model(root, attacker_model):
            return {}
        return {
            "reroll_values": (1,),
            "reroll_reasons": ("Only the Best: re-roll Hit roll of 1",),
        }

    def fire_zone_purge_hit_bonus(
        self,
        attacker_model,
        *,
        attack_type: str = "any",
        game=None,
    ) -> tuple[int, str]:
        if not self.is_bridgehead_strike():
            return 0, ""
        if str(attack_type or "any").strip().lower() != "ranged":
            return 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        if not self._unit_in_army(root):
            return 0, ""
        if not self._unit_is_militarum_tempestus_model(root, attacker_model):
            return 0, ""
        set_up = self._attached_unit_was_set_up_this_turn(root, game=game)
        disembarked = self._attached_unit_disembarked_from_transport_this_round(root)
        if not (set_up or disembarked):
            return 0, ""
        return 1, "Fire Zone Purge"

    @staticmethod
    def _normalize_weapon_name(text: Any) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(text or "").strip().lower()).strip()

    def _bridgehead_firing_hot_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        attack_type: str = "any",
        weapon_profile=None,
        game=None,
    ) -> tuple[int, int, str]:
        if not self.is_bridgehead_strike():
            return 0, 0, ""
        if str(attack_type or "any").strip().lower() != "ranged":
            return 0, 0, ""
        if attacker_model is None or target_unit is None or weapon_profile is None:
            return 0, 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        target_root = self._unit_root(target_unit)
        if root is None or target_root is None:
            return 0, 0, ""
        if not self._unit_in_army(root):
            return 0, 0, ""

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("bridgehead_firing_hot_active")):
            return 0, 0, ""

        game_obj = game
        if game_obj is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game_obj = getattr(player, "game", None) if player is not None else None
        if game_obj is not None:
            active_player = getattr(game_obj, "get_current_player", lambda: None)()
            active_player_id = str(getattr(active_player, "id", "") or "")
            owner_id = str(sr.get("bridgehead_firing_hot_owner", "") or "")
            if owner_id and active_player_id and owner_id != active_player_id:
                return 0, 0, ""
            current_turn = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
            marked_turn = self._safe_int(sr.get("bridgehead_firing_hot_turn", 0) or 0, 0)
            if marked_turn and current_turn and marked_turn != current_turn:
                return 0, 0, ""
            current_phase = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper()
            expires_phase = str(sr.get("bridgehead_firing_hot_expires_phase", "") or "").strip().upper()
            if expires_phase and current_phase and expires_phase != current_phase:
                return 0, 0, ""

        weapon_name = str(getattr(getattr(weapon_profile, "parent_wargear", None), "name", "") or getattr(weapon_profile, "name", "") or "")
        if self._normalize_weapon_name(weapon_name) not in self._BRIDGEHEAD_FIRING_HOT_WEAPON_NAMES:
            return 0, 0, ""

        distance = self._distance_between_units(root, target_root, game=game_obj)
        if distance is None or distance > 12.0 + 1e-6:
            return 0, 0, ""
        source = str(sr.get("bridgehead_firing_hot_source", "") or "FIRING HOT").strip() or "FIRING HOT"
        return 1, 1, source

    def bridgehead_firing_hot_strength_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        attack_type: str = "any",
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        strength_bonus, _ap_bonus, source = self._bridgehead_firing_hot_bonus(
            attacker_model,
            target_unit,
            attack_type=attack_type,
            weapon_profile=weapon_profile,
            game=game,
        )
        return int(strength_bonus), source

    def bridgehead_firing_hot_ap_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        attack_type: str = "any",
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        _strength_bonus, ap_bonus, source = self._bridgehead_firing_hot_bonus(
            attacker_model,
            target_unit,
            attack_type=attack_type,
            weapon_profile=weapon_profile,
            game=game,
        )
        return int(ap_bonus), source

    def born_soldiers_lethal_hits_applies(
        self,
        attacker_model,
        target_unit,
        *,
        attack_type: str = "any",
        game=None,
        game_map=None,
        target_visible=None,
    ) -> tuple[bool, str]:
        if not self.is_combined_arms():
            return False, ""
        if str(attack_type or "any").strip().lower() != "ranged":
            return False, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return False, ""
        if not self._unit_in_army(root):
            return False, ""
        if target_unit is None:
            return False, ""

        visible = True
        if target_visible is None:
            local_map = game_map
            if local_map is None and game is not None:
                local_map = getattr(game, "map", None)
            if local_map is not None and hasattr(root, "_has_line_of_sight_to_target"):
                visible = bool(root._has_line_of_sight_to_target(attacker_model, target_unit, local_map))
        else:
            visible = bool(target_visible)
        if not visible:
            return False, ""

        target_is_monster_or_vehicle = self._target_is_monster_or_vehicle(target_unit)
        if self._unit_is_regiment_model(root, attacker_model) and not target_is_monster_or_vehicle:
            return True, "Born Soldiers"
        if self._unit_is_squadron_model(root, attacker_model) and target_is_monster_or_vehicle:
            return True, "Born Soldiers"
        return False, ""

    def activate_combined_arms_flexible_command(
        self,
        officers,
        *,
        game=None,
        phase_name: str = "",
        source: str = "",
    ) -> int:
        if not self.is_combined_arms():
            return 0
        game_obj = game if game is not None else self._current_game()
        round_now = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        phase_key = self._phase_key(phase_name or getattr(getattr(game_obj, "phase", None), "name", "") or "")
        owner_id = self._player_id(getattr(self.army, "player", None))
        source_name = str(source or "FLEXIBLE COMMAND").strip() or "FLEXIBLE COMMAND"
        applied = 0
        seen: set[str] = set()
        for officer in list(officers or []):
            root = self._unit_root(officer)
            if root is None or not self._unit_in_army(root):
                continue
            if not self.unit_is_astra_militarum(root) or not self.unit_is_officer(root):
                continue
            root_id = self._entity_id(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["combined_arms_flexible_command_active"] = True
            sr["combined_arms_flexible_command_round"] = int(round_now)
            sr["combined_arms_flexible_command_phase"] = phase_key
            sr["combined_arms_flexible_command_owner"] = owner_id
            sr["combined_arms_flexible_command_source"] = source_name
            root.special_rules = sr
            applied += 1
        return applied

    def combined_arms_flexible_command_target_keywords(self, officer_unit, *, game=None) -> tuple[str, ...]:
        if not self.is_combined_arms():
            return ()
        root = self._unit_root(officer_unit)
        if root is None or not self._unit_in_army(root):
            return ()
        if not self.unit_is_astra_militarum(root) or not self.unit_is_officer(root):
            return ()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("combined_arms_flexible_command_active", False)):
            return ()
        game_obj = game if game is not None else self._current_game()
        current_round = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        marked_round = self._safe_int(sr.get("combined_arms_flexible_command_round", 0) or 0, 0)
        if marked_round and current_round and marked_round != current_round:
            return ()
        current_phase = self._phase_key(getattr(getattr(game_obj, "phase", None), "name", "") or "")
        marked_phase = self._phase_key(sr.get("combined_arms_flexible_command_phase", "") or "")
        if current_phase and marked_phase and current_phase != marked_phase:
            return ()
        owner_id = str(sr.get("combined_arms_flexible_command_owner", "") or "")
        active_player_id = self._current_player_id(game=game_obj)
        if owner_id and active_player_id and owner_id != active_player_id:
            return ()
        return ("REGIMENT", "SQUADRON")

    def activate_combined_arms_fields_of_fire(
        self,
        regiment_unit,
        squadron_unit,
        enemy_unit,
        *,
        game=None,
        phase_name: str = "",
        source: str = "",
    ) -> bool:
        if not self.is_combined_arms():
            return False
        regiment_root = self._unit_root(regiment_unit)
        squadron_root = self._unit_root(squadron_unit)
        enemy_root = self._unit_root(enemy_unit)
        if regiment_root is None or squadron_root is None or enemy_root is None:
            return False
        if regiment_root is squadron_root:
            return False
        if not self._unit_in_army(regiment_root) or not self._unit_in_army(squadron_root):
            return False
        game_obj = game if game is not None else self._current_game()
        round_now = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        phase_key = self._phase_key(phase_name or getattr(getattr(game_obj, "phase", None), "name", "") or "")
        owner_id = self._player_id(getattr(self.army, "player", None))
        source_name = str(source or "FIELDS OF FIRE").strip() or "FIELDS OF FIRE"
        target_unit_id = self._entity_id(enemy_root)
        if not target_unit_id:
            return False
        for root in (regiment_root, squadron_root):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["combined_arms_fields_of_fire_active"] = True
            sr["combined_arms_fields_of_fire_target_unit_id"] = target_unit_id
            sr["combined_arms_fields_of_fire_round"] = int(round_now)
            sr["combined_arms_fields_of_fire_phase"] = phase_key
            sr["combined_arms_fields_of_fire_owner"] = owner_id
            sr["combined_arms_fields_of_fire_ap_bonus"] = 1
            sr["combined_arms_fields_of_fire_source"] = source_name
            root.special_rules = sr
        return True

    def combined_arms_fields_of_fire_ap_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        attack_type: str = "any",
        game=None,
    ) -> tuple[int, str]:
        if not self.is_combined_arms():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(attacker_unit)
        target_root = self._unit_root(target_unit)
        if root is None or target_root is None or not self._unit_in_army(root):
            return 0, ""
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("combined_arms_fields_of_fire_active", False)):
            return 0, ""
        target_unit_id = str(sr.get("combined_arms_fields_of_fire_target_unit_id", "") or "")
        if not target_unit_id or target_unit_id != self._entity_id(target_root):
            return 0, ""
        game_obj = game if game is not None else self._current_game()
        current_round = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        marked_round = self._safe_int(sr.get("combined_arms_fields_of_fire_round", 0) or 0, 0)
        if marked_round and current_round and marked_round != current_round:
            return 0, ""
        current_phase = self._phase_key(getattr(getattr(game_obj, "phase", None), "name", "") or "")
        marked_phase = self._phase_key(sr.get("combined_arms_fields_of_fire_phase", "") or "")
        if current_phase and marked_phase and current_phase != marked_phase:
            return 0, ""
        owner_id = str(sr.get("combined_arms_fields_of_fire_owner", "") or "")
        active_player_id = self._current_player_id(game=game_obj)
        if owner_id and active_player_id and owner_id != active_player_id:
            return 0, ""
        bonus = self._safe_int(sr.get("combined_arms_fields_of_fire_ap_bonus", 0) or 0, 0)
        if bonus <= 0:
            return 0, ""
        source = str(sr.get("combined_arms_fields_of_fire_source", "") or "FIELDS OF FIRE").strip() or "FIELDS OF FIRE"
        return int(bonus), source

    def activate_combined_arms_stalwart_protector(
        self,
        vehicle_unit,
        *,
        game=None,
        phase_name: str = "",
        source: str = "",
    ) -> bool:
        if not self.is_combined_arms():
            return False
        root = self._unit_root(vehicle_unit)
        if root is None or not self._unit_in_army(root):
            return False
        if not self.unit_is_astra_militarum(root) or not self._unit_has_keyword(root, "VEHICLE"):
            return False
        game_obj = game if game is not None else self._current_game()
        round_now = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        phase_key = self._phase_key(phase_name or getattr(getattr(game_obj, "phase", None), "name", "") or "")
        owner_id = self._player_id(getattr(self.army, "player", None))
        source_name = str(source or "STALWART PROTECTOR").strip() or "STALWART PROTECTOR"
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["combined_arms_stalwart_protector_active"] = True
        sr["combined_arms_stalwart_protector_round"] = int(round_now)
        sr["combined_arms_stalwart_protector_phase"] = phase_key
        sr["combined_arms_stalwart_protector_owner"] = owner_id
        sr["combined_arms_stalwart_protector_source"] = source_name
        root.special_rules = sr
        return True

    def combined_arms_stalwart_protector_rule(self, unit, *, game=None) -> dict | None:
        if not self.is_combined_arms():
            return None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("combined_arms_stalwart_protector_active", False)):
            return None
        game_obj = game if game is not None else self._current_game()
        current_round = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        marked_round = self._safe_int(sr.get("combined_arms_stalwart_protector_round", 0) or 0, 0)
        if marked_round and current_round and marked_round != current_round:
            return None
        current_phase = self._phase_key(getattr(getattr(game_obj, "phase", None), "name", "") or "")
        marked_phase = self._phase_key(sr.get("combined_arms_stalwart_protector_phase", "") or "")
        if current_phase and marked_phase and current_phase != marked_phase:
            return None
        owner_id = str(sr.get("combined_arms_stalwart_protector_owner", "") or "")
        active_player_id = self._current_player_id(game=game_obj)
        if owner_id and active_player_id and owner_id == active_player_id:
            return None
        source = str(sr.get("combined_arms_stalwart_protector_source", "") or "STALWART PROTECTOR").strip()
        source_name = source or "STALWART PROTECTOR"
        model_id = ""
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not bool(getattr(model, "is_alive", True)):
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id:
                break
        return {
            "source": source_name,
            "model_id": model_id,
            "target_keyword": "INFANTRY",
            "invulnerable_save": None,
        }

    def cleanup_combined_arms_phase_effects(
        self,
        *,
        phase_name: str = "",
        player=None,
        game=None,
        battle_round=None,
    ) -> None:
        if not self.is_combined_arms() or self.army is None:
            return
        game_obj = game if game is not None else self._current_game()
        round_now = self._safe_int(
            battle_round if battle_round is not None else getattr(game_obj, "turn", 0) or 0,
            0,
        )
        phase_key = self._phase_key(phase_name or getattr(getattr(game_obj, "phase", None), "name", "") or "")
        owner_id = self._player_id(player)
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            for prefix in (
                "combined_arms_flexible_command",
                "combined_arms_fields_of_fire",
                "combined_arms_stalwart_protector",
            ):
                if not bool(sr.get(f"{prefix}_active", False)):
                    continue
                marked_round = self._safe_int(sr.get(f"{prefix}_round", 0) or 0, 0)
                marked_phase = self._phase_key(sr.get(f"{prefix}_phase", "") or "")
                marked_owner = str(sr.get(f"{prefix}_owner", "") or "")
                if marked_round and round_now and marked_round != round_now:
                    continue
                if phase_key and marked_phase and marked_phase != phase_key:
                    continue
                if owner_id and marked_owner and marked_owner != owner_id:
                    continue
                for key in list(sr.keys()):
                    if key == f"{prefix}_active" or key.startswith(f"{prefix}_"):
                        sr.pop(key, None)
            root.special_rules = sr
            ability_cache = getattr(root, "_ability_cache", None)
            if isinstance(ability_cache, dict):
                ability_cache.pop("selfless_protector_rule", None)

    def activate_hammer_of_the_emperor_blazing_advance(
        self,
        unit,
        *,
        game=None,
        source: str = "",
    ) -> bool:
        if not self.is_hammer_of_the_emperor():
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        if not self.unit_is_astra_militarum(root) or not self._unit_has_keyword(root, "SQUADRON"):
            return False
        game_obj = game if game is not None else self._current_game()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hammer_of_the_emperor_blazing_advance_active"] = True
        sr["hammer_of_the_emperor_blazing_advance_turn"] = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        sr["hammer_of_the_emperor_blazing_advance_turn_owner"] = self._player_id(getattr(self.army, "player", None))
        sr["hammer_of_the_emperor_blazing_advance_source"] = (
            str(source or "BLAZING ADVANCE").strip() or "BLAZING ADVANCE"
        )
        root.special_rules = sr
        return True

    def activate_hammer_of_the_emperor_tactical_withdrawal(
        self,
        unit,
        *,
        game=None,
        source: str = "",
    ) -> bool:
        if not self.is_hammer_of_the_emperor():
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        if not self.unit_is_astra_militarum(root) or not self._unit_has_keyword(root, "SQUADRON"):
            return False
        game_obj = game if game is not None else self._current_game()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hammer_of_the_emperor_tactical_withdrawal_active"] = True
        sr["hammer_of_the_emperor_tactical_withdrawal_turn"] = self._safe_int(
            getattr(game_obj, "turn", 0) or 0,
            0,
        )
        sr["hammer_of_the_emperor_tactical_withdrawal_turn_owner"] = self._player_id(
            getattr(self.army, "player", None)
        )
        sr["hammer_of_the_emperor_tactical_withdrawal_source"] = (
            str(source or "TACTICAL WITHDRAWAL").strip() or "TACTICAL WITHDRAWAL"
        )
        root.special_rules = sr
        return True

    def can_shoot_after_advance(self, unit, profile=None, *, game=None) -> bool:
        if not self._weapon_profile_is_ranged(profile):
            return False
        root, _sr = self._hammer_turn_effect_state(
            unit,
            prefix="hammer_of_the_emperor_blazing_advance",
            game=game,
        )
        return bool(root is not None)

    def can_shoot_after_fall_back(self, unit, profile=None, *, game=None) -> bool:
        if not self._weapon_profile_is_ranged(profile):
            return False
        root, _sr = self._hammer_turn_effect_state(
            unit,
            prefix="hammer_of_the_emperor_tactical_withdrawal",
            game=game,
        )
        return bool(root is not None)

    def activate_hammer_of_the_emperor_crash_through(
        self,
        unit,
        *,
        game=None,
        phase_name: str = "",
        source: str = "",
    ) -> bool:
        if not self.is_hammer_of_the_emperor():
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        if not self.unit_is_astra_militarum(root) or not self._unit_has_keyword(root, "VEHICLE"):
            return False
        game_obj = game if game is not None else self._current_game()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current = set(sr.get("bearer_unit_phase_move_terrain_only_types") or [])
        added = set()
        for move_type in ("move", "advance", "charge"):
            if move_type not in current:
                current.add(move_type)
                added.add(move_type)
        if current:
            sr["bearer_unit_phase_move_terrain_only_types"] = sorted(current)
        if added:
            sr["hammer_of_the_emperor_crash_through_added_phase_move_terrain_only_types"] = sorted(added)
        sr["hammer_of_the_emperor_crash_through_active"] = True
        sr["hammer_of_the_emperor_crash_through_expires_phase"] = self._phase_key(
            phase_name or getattr(getattr(game_obj, "phase", None), "name", "") or ""
        )
        sr["hammer_of_the_emperor_crash_through_turn"] = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        sr["hammer_of_the_emperor_crash_through_turn_owner"] = self._player_id(getattr(self.army, "player", None))
        sr["hammer_of_the_emperor_crash_through_source"] = (
            str(source or "CRASH THROUGH").strip() or "CRASH THROUGH"
        )
        root.special_rules = sr
        return True

    def activate_hammer_of_the_emperor_final_hour(
        self,
        unit,
        *,
        game=None,
        source: str = "",
    ) -> bool:
        if not self.is_hammer_of_the_emperor():
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        if not self.unit_is_astra_militarum(root) or not self._unit_has_keyword(root, "SQUADRON"):
            return False
        if self.unit_is_officer(root) or not self._unit_is_below_half_strength(root):
            return False
        game_obj = game if game is not None else self._current_game()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hammer_of_the_emperor_final_hour_active"] = True
        sr["hammer_of_the_emperor_final_hour_battle_round"] = self._safe_int(
            getattr(game_obj, "turn", 0) or 0,
            0,
        )
        sr["hammer_of_the_emperor_final_hour_owner"] = self._player_id(getattr(self.army, "player", None))
        sr["hammer_of_the_emperor_final_hour_source"] = str(source or "FINAL HOUR").strip() or "FINAL HOUR"
        root.special_rules = sr
        return True

    def hammer_of_the_emperor_final_hour_hazardous_applies(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        if attacker_model is None:
            return False, ""
        if not self._weapon_profile_is_ranged(weapon_profile):
            return False, ""
        if weapon_profile is not None:
            is_one_shot = getattr(weapon_profile, "is_one_shot", None)
            if callable(is_one_shot) and bool(is_one_shot()):
                return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root, sr = self._hammer_battle_round_effect_state(
            attacker_unit,
            prefix="hammer_of_the_emperor_final_hour",
            game=game,
        )
        if root is None or not isinstance(sr, dict):
            return False, ""
        source = str(sr.get("hammer_of_the_emperor_final_hour_source", "") or "FINAL HOUR").strip() or "FINAL HOUR"
        return True, source

    def hammer_of_the_emperor_final_hour_ignore_hit_modifiers_rule(
        self,
        attacker_model,
        *,
        game=None,
    ) -> dict | None:
        if attacker_model is None:
            return None
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root, sr = self._hammer_battle_round_effect_state(
            attacker_unit,
            prefix="hammer_of_the_emperor_final_hour",
            game=game,
        )
        if root is None or not isinstance(sr, dict):
            return None
        source = str(sr.get("hammer_of_the_emperor_final_hour_source", "") or "FINAL HOUR").strip() or "FINAL HOUR"
        return {
            "name": source,
            "attack_type": "ranged",
            "skill_kinds": {"ballistic"},
            "allow_hit": True,
        }

    def activate_hammer_of_the_emperor_furious_cannonade(
        self,
        unit,
        *,
        game=None,
        phase_name: str = "",
        source: str = "",
    ) -> bool:
        if not self.is_hammer_of_the_emperor():
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        if not self.unit_is_astra_militarum(root) or not self._unit_has_keyword(root, "SQUADRON"):
            return False
        game_obj = game if game is not None else self._current_game()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hammer_of_the_emperor_furious_cannonade_active"] = True
        sr["hammer_of_the_emperor_furious_cannonade_turn"] = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        sr["hammer_of_the_emperor_furious_cannonade_turn_owner"] = self._player_id(getattr(self.army, "player", None))
        sr["hammer_of_the_emperor_furious_cannonade_expires_phase"] = self._phase_key(
            phase_name or getattr(getattr(game_obj, "phase", None), "name", "") or ""
        )
        sr["hammer_of_the_emperor_furious_cannonade_ap_bonus"] = 1
        sr["hammer_of_the_emperor_furious_cannonade_source"] = (
            str(source or "FURIOUS CANNONADE").strip() or "FURIOUS CANNONADE"
        )
        root.special_rules = sr
        return True

    def hammer_of_the_emperor_furious_cannonade_ap_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        attack_type: str = "any",
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        _ = weapon_profile
        if str(attack_type or "any").strip().lower() != "ranged":
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root, sr = self._hammer_phase_effect_state(
            attacker_unit,
            prefix="hammer_of_the_emperor_furious_cannonade",
            game=game,
        )
        target_root = self._unit_root(target_unit)
        if root is None or target_root is None or not isinstance(sr, dict):
            return 0, ""
        game_obj = game if game is not None else self._current_game()
        distance = self._distance_between_units(root, target_root, game=game_obj)
        if distance is None or distance > 12.0 + 1e-6:
            return 0, ""
        bonus = self._safe_int(sr.get("hammer_of_the_emperor_furious_cannonade_ap_bonus", 0) or 0, 0)
        if bonus <= 0:
            return 0, ""
        source = str(sr.get("hammer_of_the_emperor_furious_cannonade_source", "") or "FURIOUS CANNONADE").strip()
        return int(bonus), source or "FURIOUS CANNONADE"

    def cleanup_hammer_of_the_emperor_phase_effects(
        self,
        *,
        phase_name: str = "",
        player=None,
        game=None,
        battle_round=None,
    ) -> None:
        if not self.is_hammer_of_the_emperor() or self.army is None:
            return
        game_obj = game if game is not None else self._current_game()
        round_now = self._safe_int(
            battle_round if battle_round is not None else getattr(game_obj, "turn", 0) or 0,
            0,
        )
        phase_key = self._phase_key(phase_name or getattr(getattr(game_obj, "phase", None), "name", "") or "")
        owner_id = self._player_id(player)
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if bool(sr.get("hammer_of_the_emperor_crash_through_active", False)):
                marked_round = self._safe_int(sr.get("hammer_of_the_emperor_crash_through_turn", 0) or 0, 0)
                marked_phase = self._phase_key(sr.get("hammer_of_the_emperor_crash_through_expires_phase", "") or "")
                marked_owner = str(sr.get("hammer_of_the_emperor_crash_through_turn_owner", "") or "")
                if (not round_now or not marked_round or marked_round == round_now) and (
                    not phase_key or not marked_phase or marked_phase == phase_key
                ) and (not owner_id or not marked_owner or marked_owner == owner_id):
                    added = set(sr.get("hammer_of_the_emperor_crash_through_added_phase_move_terrain_only_types") or [])
                    current = list(sr.get("bearer_unit_phase_move_terrain_only_types") or [])
                    kept = [move_type for move_type in current if move_type not in added]
                    if kept:
                        sr["bearer_unit_phase_move_terrain_only_types"] = kept
                    else:
                        sr.pop("bearer_unit_phase_move_terrain_only_types", None)
                    self._clear_prefixed_special_rules(sr, "hammer_of_the_emperor_crash_through")
            if bool(sr.get("hammer_of_the_emperor_furious_cannonade_active", False)):
                marked_round = self._safe_int(sr.get("hammer_of_the_emperor_furious_cannonade_turn", 0) or 0, 0)
                marked_phase = self._phase_key(sr.get("hammer_of_the_emperor_furious_cannonade_expires_phase", "") or "")
                marked_owner = str(sr.get("hammer_of_the_emperor_furious_cannonade_turn_owner", "") or "")
                if (not round_now or not marked_round or marked_round == round_now) and (
                    not phase_key or not marked_phase or marked_phase == phase_key
                ) and (not owner_id or not marked_owner or marked_owner == owner_id):
                    self._clear_prefixed_special_rules(sr, "hammer_of_the_emperor_furious_cannonade")
            root.special_rules = sr

    def cleanup_recon_element_phase_effects(
        self,
        *,
        phase_name: str = "",
        player=None,
        game=None,
        battle_round=None,
    ) -> None:
        if not self.is_recon_element():
            return
        game_obj = game if game is not None else self._current_game()
        round_now = self._safe_int(
            battle_round if battle_round is not None else getattr(game_obj, "turn", 0) or 0,
            0,
        )
        phase_key = self._phase_key(phase_name or getattr(getattr(game_obj, "phase", None), "name", "") or "")
        owner_id = self._player_id(player)

        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            for prefix in (
                "recon_courageous_diversion",
                "recon_tanglefoot_grenades",
                "recon_scramble_field",
            ):
                if not bool(sr.get(f"{prefix}_active", False)):
                    continue
                marked_round = self._safe_int(sr.get(f"{prefix}_turn", 0) or 0, 0)
                marked_phase = self._phase_key(sr.get(f"{prefix}_expires_phase", "") or "")
                marked_owner = str(sr.get(f"{prefix}_turn_owner", "") or "")
                if marked_round and round_now and marked_round != round_now:
                    continue
                if phase_key and marked_phase and marked_phase != phase_key:
                    continue
                if owner_id and marked_owner and marked_owner != owner_id:
                    continue
                self._clear_prefixed_special_rules(sr, prefix)
            root.special_rules = sr

        if phase_key != "CHARGE_PHASE":
            return
        for root in self._iter_game_unit_roots(game=game_obj):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            modifiers = []
            changed = False
            for entry in list(sr.get("charge_roll_modifiers", []) or []):
                if isinstance(entry, dict) and str(entry.get("source_key", "") or "") == "astra_militarum_tanglefoot_grenades":
                    changed = True
                    continue
                modifiers.append(entry)
            if changed:
                if modifiers:
                    sr["charge_roll_modifiers"] = modifiers
                else:
                    sr.pop("charge_roll_modifiers", None)
            sr.pop("astra_militarum_tanglefoot_grenades_source", None)
            sr.pop("astra_militarum_tanglefoot_grenades_turn", None)
            sr.pop("astra_militarum_tanglefoot_grenades_turn_owner", None)
            root.special_rules = sr

    def cleanup_siege_regiment_phase_effects(
        self,
        *,
        phase_name: str = "",
        player=None,
        game=None,
        battle_round=None,
    ) -> None:
        if not self.is_siege_regiment() or self.army is None:
            return
        game_obj = game if game is not None else self._current_game()
        round_now = self._safe_int(
            battle_round if battle_round is not None else getattr(game_obj, "turn", 0) or 0,
            0,
        )
        phase_key = self._phase_key(phase_name or getattr(getattr(game_obj, "phase", None), "name", "") or "")
        owner_id = self._player_id(player)
        seen: set[str] = set()
        roots_to_invalidate: list[Any] = []
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            trench_changed = False
            for prefix in (
                "siege_regiment_callous_sacrifice",
                "siege_regiment_flare_burst",
                "siege_regiment_furious_fusillade",
                "siege_regiment_minefield",
                "siege_regiment_trench_fighters",
                "siege_regiment_over_the_top",
            ):
                if not bool(sr.get(f"{prefix}_active", False)):
                    continue
                marked_round = self._safe_int(sr.get(f"{prefix}_turn", 0) or 0, 0)
                marked_phase = self._phase_key(sr.get(f"{prefix}_expires_phase", "") or "")
                marked_owner = str(sr.get(f"{prefix}_turn_owner", "") or "")
                if marked_round and round_now and marked_round != round_now:
                    continue
                if phase_key and marked_phase and marked_phase != phase_key:
                    continue
                if owner_id and marked_owner and marked_owner != owner_id:
                    continue
                self._clear_prefixed_special_rules(sr, prefix)
                if prefix == "siege_regiment_trench_fighters":
                    trench_changed = True
            root.special_rules = sr
            if trench_changed:
                roots_to_invalidate.append(root)
        for root in list(roots_to_invalidate or []):
            self._clear_unit_ability_cache(root)

    def cleanup_hammer_of_the_emperor_battle_round_effects(
        self,
        *,
        battle_round: int = 0,
        game=None,
    ) -> None:
        if not self.is_hammer_of_the_emperor() or self.army is None:
            return
        game_obj = game if game is not None else self._current_game()
        round_now = self._safe_int(
            battle_round if battle_round is not None else getattr(game_obj, "turn", 0) or 0,
            0,
        )
        if round_now <= 0:
            return
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            for prefix in (
                "hammer_of_the_emperor_blazing_advance",
                "hammer_of_the_emperor_tactical_withdrawal",
                "hammer_of_the_emperor_crash_through",
                "hammer_of_the_emperor_furious_cannonade",
            ):
                if not bool(sr.get(f"{prefix}_active", False)):
                    continue
                marked_turn = self._safe_int(sr.get(f"{prefix}_turn", 0) or 0, 0)
                if marked_turn and marked_turn == round_now:
                    continue
                if prefix == "hammer_of_the_emperor_crash_through":
                    added = set(sr.get("hammer_of_the_emperor_crash_through_added_phase_move_terrain_only_types") or [])
                    current = list(sr.get("bearer_unit_phase_move_terrain_only_types") or [])
                    kept = [move_type for move_type in current if move_type not in added]
                    if kept:
                        sr["bearer_unit_phase_move_terrain_only_types"] = kept
                    else:
                        sr.pop("bearer_unit_phase_move_terrain_only_types", None)
                self._clear_prefixed_special_rules(sr, prefix)
            if bool(sr.get("hammer_of_the_emperor_final_hour_active", False)):
                marked_round = self._safe_int(sr.get("hammer_of_the_emperor_final_hour_battle_round", 0) or 0, 0)
                if not marked_round or marked_round != round_now:
                    self._clear_prefixed_special_rules(sr, "hammer_of_the_emperor_final_hour")
            root.special_rules = sr

    def _unit_is_transport_unit(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if self._unit_has_keyword(root, "TRANSPORT"):
            return True
        return bool(getattr(root, "is_transport", False))

    def _unit_is_aircraft_or_titanic(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if self._unit_has_keyword(root, "AIRCRAFT"):
            return True
        if self._unit_has_keyword(root, "TITANIC"):
            return True
        return bool(getattr(root, "is_aircraft", False))

    def _smoke_grenades_active_spec(self, unit) -> tuple[bool, str]:
        if not self.is_mechanised_assault():
            return False, ""
        root = self._unit_root(unit)
        if root is None:
            return False, ""
        if not self._unit_in_army(root):
            return False, ""
        source_unit, sr = self._attached_unit_enhancement_source(root, "enhancement_smoke_grenades")
        if source_unit is None or not isinstance(sr, dict):
            return False, ""
        if not bool(sr.get("enhancement_smoke_grenades_require_friendly_transport", True)):
            source = str(sr.get("enhancement_smoke_grenades_source", "") or "Smoke Grenades").strip()
            return True, source or "Smoke Grenades"
        try:
            range_value = float(sr.get("enhancement_smoke_grenades_range", 3.0) or 3.0)
        except (TypeError, ValueError):
            range_value = 3.0
        range_value = max(0.0, float(range_value))
        require_wholly_within = bool(sr.get("enhancement_smoke_grenades_require_wholly_within", True))

        from ..utility.aura_utils import unit_wholly_within_range_of_unit, unit_within_range_of_unit

        for friendly in self._friendly_battlefield_roots():
            if friendly is None or friendly is root:
                continue
            if not self._unit_is_transport_unit(friendly):
                continue
            if require_wholly_within:
                in_range = bool(
                    unit_wholly_within_range_of_unit(
                        friendly,
                        root,
                        range_value,
                        use_attached_aggregate=True,
                    )
                )
            else:
                in_range = bool(
                    unit_within_range_of_unit(
                        friendly,
                        root,
                        range_value,
                        use_attached_aggregate=True,
                    )
                )
            if not in_range:
                continue
            source = str(sr.get("enhancement_smoke_grenades_source", "") or "Smoke Grenades").strip()
            return True, source or "Smoke Grenades"
        return False, ""

    def mechanised_assault_smoke_grenades_benefit_of_cover(
        self,
        target_model,
        *,
        attack_type: str = "any",
    ) -> tuple[bool, str]:
        if str(attack_type or "any").strip().lower() != "ranged":
            return False, ""
        unit = getattr(target_model, "parent_unit", None)
        active, source = self._smoke_grenades_active_spec(unit)
        if not active:
            return False, ""
        return True, source or "Smoke Grenades"

    def mechanised_assault_smoke_grenades_stealth_applies(self, unit) -> bool:
        active, _source = self._smoke_grenades_active_spec(unit)
        return bool(active)

    def recon_element_survival_gear_scout_distance(self, unit) -> float:
        if not self.is_recon_element():
            return 0.0
        if unit is None:
            return 0.0
        root = self._unit_root(unit)
        if root is None:
            return 0.0
        if not self._unit_in_army(root):
            return 0.0
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("enhancement_survival_gear", False)):
            return 0.0
        if not self._enhancement_bearer_alive(unit, sr, bearer_key="enhancement_survival_gear_bearer_model_id"):
            return 0.0
        try:
            distance = float(sr.get("enhancement_survival_gear_scout_distance", 6.0) or 6.0)
        except (TypeError, ValueError):
            distance = 6.0
        return max(0.0, float(distance))

    def _eager_advance_distance_from_source(self, query_unit, source_unit, sr) -> float:
        if source_unit is None or not isinstance(sr, dict):
            return 0.0
        if not bool(sr.get("enhancement_eager_advance", False)):
            return 0.0
        if not self._enhancement_bearer_alive(source_unit, sr, bearer_key="enhancement_eager_advance_bearer_model_id"):
            return 0.0
        try:
            distance = float(sr.get("enhancement_eager_advance_scout_distance", 6.0) or 6.0)
        except (TypeError, ValueError):
            distance = 6.0
        distance = max(0.0, float(distance))
        if distance <= 0:
            return 0.0
        requires_leading = bool(sr.get("enhancement_eager_advance_requires_leading", True))
        if not requires_leading:
            return distance
        target_keyword = str(sr.get("enhancement_eager_advance_target_keyword", "REGIMENT") or "REGIMENT").strip().upper()
        led_root = self._unit_root(getattr(source_unit, "attached_to", None))
        if led_root is None:
            return 0.0
        if target_keyword and not self._unit_has_keyword(led_root, target_keyword):
            return 0.0
        query_root = self._unit_root(query_unit)
        if query_unit is source_unit:
            return distance
        if query_root is not None and query_root is led_root:
            return distance
        return 0.0

    def siege_regiment_eager_advance_scout_distance(self, unit) -> float:
        if not self.is_siege_regiment():
            return 0.0
        if unit is None:
            return 0.0
        root = self._unit_root(unit)
        if root is None:
            return 0.0
        if not self._unit_in_army(root):
            return 0.0

        max_distance = 0.0
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict):
            max_distance = max(max_distance, self._eager_advance_distance_from_source(unit, unit, sr))

        leaders = list(getattr(root, "attached_leaders", []) or [])
        for leader in leaders:
            if leader is None:
                continue
            leader_sr = getattr(leader, "special_rules", None)
            if not isinstance(leader_sr, dict):
                continue
            max_distance = max(max_distance, self._eager_advance_distance_from_source(unit, leader, leader_sr))

        return max(0.0, float(max_distance))

    def mechanised_assault_sacred_unguents_hit_reroll_mods(
        self,
        attacker_model,
        target_unit=None,
        *,
        attack_type: str = "any",
        game=None,
        game_map=None,
        target_visible=None,
    ) -> dict:
        _ = target_unit
        _ = game_map
        _ = target_visible
        if not self.is_mechanised_assault():
            return {}
        if str(attack_type or "any").strip().lower() != "ranged":
            return {}
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return {}
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return {}
        if not bool(sr.get("sacred_unguents_active", False)):
            return {}
        exp_phase = str(sr.get("sacred_unguents_expires_phase", "") or "").strip().upper()
        if exp_phase:
            game_obj = game
            if game_obj is None:
                try:
                    army = root.get_parent_army()
                    game_obj = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game_obj = None
            phase_name = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper()
            if phase_name and phase_name != exp_phase:
                return {}
        try:
            effect_turn = int(sr.get("sacred_unguents_turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        if effect_turn > 0:
            game_obj = game
            if game_obj is None:
                try:
                    army = root.get_parent_army()
                    game_obj = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game_obj = None
            try:
                current_turn = int(getattr(game_obj, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0
            if current_turn and current_turn != effect_turn:
                return {}
        owner_id = str(sr.get("sacred_unguents_owner", "") or "").strip()
        if owner_id:
            try:
                army = root.get_parent_army()
                player = getattr(army, "player", None) if army is not None else None
            except Exception:
                player = None
            current_owner_id = str(get_entity_id(player) or getattr(player, "id", "") or "").strip() if player is not None else ""
            if current_owner_id and current_owner_id != owner_id:
                return {}
        source = str(sr.get("sacred_unguents_source", "") or "Sacred Unguents").strip() or "Sacred Unguents"
        return {
            "reroll_full": True,
            "reroll_full_reasons": (f"{source}: re-roll Hit roll",),
        }

    def siege_regiment_flare_burst_hit_reroll_mods(
        self,
        attacker_model,
        target_unit=None,
        *,
        attack_type: str = "any",
        game=None,
        game_map=None,
        target_visible=None,
    ) -> dict:
        if not self.is_siege_regiment():
            return {}
        if str(attack_type or "any").strip().lower() != "ranged":
            return {}
        if attacker_model is None or target_unit is None:
            return {}
        root, sr = self._siege_phase_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix="siege_regiment_flare_burst",
            game=game,
        )
        target_root = self._unit_root(target_unit)
        if root is None or target_root is None or not isinstance(sr, dict):
            return {}
        game_obj = game if game is not None else self._current_game()
        visible = True
        if target_visible is None:
            local_map = game_map if game_map is not None else getattr(game_obj, "map", None)
            los_checker = getattr(root, "_has_line_of_sight_to_target", None)
            if local_map is not None and callable(los_checker):
                visible = bool(los_checker(attacker_model, target_root, local_map))
        else:
            visible = bool(target_visible)
        if not visible:
            return {}
        distance = self._distance_between_units(root, target_root, game=game_obj)
        if distance is None or distance > 12.0 + 1e-6:
            return {}
        source = str(sr.get("siege_regiment_flare_burst_source", "") or "FLARE BURST").strip() or "FLARE BURST"
        return {
            "reroll_full": True,
            "reroll_full_reasons": (f"{source}: re-roll Hit roll",),
        }

    def siege_regiment_furious_fusillade_ranged_attacks_bonus(
        self,
        attacker_model,
        target_unit=None,
        *,
        weapon_profile=None,
        game=None,
        within_half_range: bool = False,
    ) -> tuple[int, str]:
        _ = target_unit
        if not self.is_siege_regiment():
            return 0, ""
        if attacker_model is None or not bool(within_half_range):
            return 0, ""
        if not self._weapon_profile_is_ranged(weapon_profile):
            return 0, ""
        root, sr = self._siege_phase_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix="siege_regiment_furious_fusillade",
            game=game,
        )
        if root is None or not isinstance(sr, dict):
            return 0, ""
        source = (
            str(sr.get("siege_regiment_furious_fusillade_source", "") or "FURIOUS FUSILLADE").strip()
            or "FURIOUS FUSILLADE"
        )
        return 1, source

    def siege_regiment_trench_fighters_fight_on_death_rule(
        self,
        unit,
        *,
        model=None,
        game=None,
    ) -> dict | None:
        root, sr = self._siege_phase_effect_state(
            unit,
            prefix="siege_regiment_trench_fighters",
            game=game,
        )
        if root is None or not isinstance(sr, dict):
            return None
        threshold = 4
        if model is not None:
            if self._unit_is_regiment_model(root, model):
                threshold = 2
        elif self._unit_has_keyword(root, "REGIMENT"):
            threshold = 2
        source = (
            str(sr.get("siege_regiment_trench_fighters_source", "") or "TRENCH FIGHTERS").strip()
            or "TRENCH FIGHTERS"
        )
        return {"threshold": int(threshold), "source": source}

    def mechanised_assault_clear_and_secure_hit_reroll_mods(
        self,
        attacker_model,
        target_unit=None,
        *,
        attack_type: str = "any",
        game=None,
    ) -> dict:
        if not self.is_mechanised_assault():
            return {}
        if str(attack_type or "any").strip().lower() != "ranged":
            return {}
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return {}
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("mechanised_clear_and_secure_active", False)):
            return {}
        exp_phase = str(sr.get("mechanised_clear_and_secure_expires_phase", "") or "").strip().upper()
        game_obj = game
        if game_obj is None:
            game_obj = getattr(getattr(self.army, "player", None), "game", None) if self.army is not None else None
        current_phase = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper()
        if exp_phase and current_phase and exp_phase != current_phase:
            return {}
        try:
            effect_turn = int(sr.get("mechanised_clear_and_secure_turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        if effect_turn > 0:
            try:
                current_turn = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
            except (TypeError, ValueError):
                current_turn = 0
            if current_turn > 0 and current_turn != effect_turn:
                return {}
        owner_id = str(sr.get("mechanised_clear_and_secure_owner", "") or "").strip()
        current_owner = str(getattr(getattr(game_obj, "get_current_player", lambda: None)(), "id", "") or "").strip() if game_obj is not None else ""
        if owner_id and current_owner and owner_id != current_owner:
            return {}
        game_map = getattr(game_obj, "map", None) if game_obj is not None else None
        if target_unit is None or not self._unit_within_any_objective_range(target_unit, game_map=game_map):
            return {}
        source = str(sr.get("mechanised_clear_and_secure_source", "") or "Clear and Secure").strip() or "Clear and Secure"
        return {
            "reroll_full": True,
            "reroll_full_reasons": (f"{source}: re-roll Hit roll vs targets within objective range",),
        }

    def mechanised_assault_clear_and_secure_wound_reroll_mods(
        self,
        attacker_model,
        target_unit=None,
        *,
        attack_type: str = "any",
        game=None,
    ) -> dict:
        if not self.is_mechanised_assault():
            return {}
        if str(attack_type or "any").strip().lower() != "ranged":
            return {}
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return {}
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("mechanised_clear_and_secure_active", False)):
            return {}
        exp_phase = str(sr.get("mechanised_clear_and_secure_expires_phase", "") or "").strip().upper()
        game_obj = game
        if game_obj is None:
            game_obj = getattr(getattr(self.army, "player", None), "game", None) if self.army is not None else None
        current_phase = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper()
        if exp_phase and current_phase and exp_phase != current_phase:
            return {}
        try:
            effect_turn = int(sr.get("mechanised_clear_and_secure_turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        if effect_turn > 0:
            try:
                current_turn = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
            except (TypeError, ValueError):
                current_turn = 0
            if current_turn > 0 and current_turn != effect_turn:
                return {}
        owner_id = str(sr.get("mechanised_clear_and_secure_owner", "") or "").strip()
        current_owner = str(getattr(getattr(game_obj, "get_current_player", lambda: None)(), "id", "") or "").strip() if game_obj is not None else ""
        if owner_id and current_owner and owner_id != current_owner:
            return {}
        game_map = getattr(game_obj, "map", None) if game_obj is not None else None
        if target_unit is None or not self._unit_within_any_objective_range(target_unit, game_map=game_map):
            return {}
        source = str(sr.get("mechanised_clear_and_secure_source", "") or "Clear and Secure").strip() or "Clear and Secure"
        return {
            "reroll_full": True,
            "reroll_full_reasons": (f"{source}: re-roll Wound roll vs targets within objective range",),
        }

    def siege_regiment_minefield_on_enemy_move_ended(
        self,
        moving_unit,
        *,
        action: str,
        game=None,
        player=None,
    ) -> list[dict]:
        _ = player
        if not self.is_siege_regiment():
            return []
        action_key = str(action or "").strip().lower()
        if action_key != "charge":
            return []
        moving_root = self._unit_root(moving_unit)
        if moving_root is None or not self._unit_is_on_battlefield(moving_root):
            return []
        moving_army = getattr(moving_root, "get_parent_army", lambda: None)()
        if moving_army is self.army:
            return []
        game_obj = game if game is not None else self._current_game()
        game_map = getattr(game_obj, "map", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None) if game_map is not None else None
        if not callable(within_engagement):
            return []

        outcome: list[dict] = []
        seen_sources: set[str] = set()
        for friendly_root in self._friendly_battlefield_roots():
            source_id = self._entity_id(friendly_root)
            if source_id and source_id in seen_sources:
                continue
            effect_root, sr = self._siege_phase_effect_state(
                friendly_root,
                prefix="siege_regiment_minefield",
                game=game_obj,
            )
            if effect_root is None or not isinstance(sr, dict):
                continue
            if source_id:
                seen_sources.add(source_id)
            if not bool(within_engagement(moving_root, effect_root)):
                continue
            get_models = getattr(moving_root, "get_attached_unit_models", None)
            models = list(get_models() or []) if callable(get_models) else list(getattr(moving_root, "models", []) or [])
            alive_models = []
            for model in models:
                alive_attr = getattr(model, "is_alive", True)
                is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if is_alive:
                    alive_models.append(model)
            if not alive_models:
                continue
            rolls = [get_roll("D6") for _ in list(alive_models or [])]
            mortal_wounds = min(6, sum(1 for roll in list(rolls or []) if int(roll) >= 5))
            if mortal_wounds > 0:
                effect_root._apply_mortal_wounds_to_unit(
                    moving_root,
                    int(mortal_wounds),
                    game_map=game_map,
                )
            source_name = str(sr.get("siege_regiment_minefield_source", "") or "MINEFIELD").strip() or "MINEFIELD"
            outcome.append(
                {
                    "source_unit": effect_root,
                    "source_name": source_name,
                    "rolls": list(rolls),
                    "mortal_wounds": int(mortal_wounds),
                    "target_unit": moving_root,
                }
            )
        return outcome

    def _apply_tripwires_stunned(
        self,
        target_root,
        *,
        owner_id: str,
        source: str,
        hit_roll_modifier: int,
        turn: int,
    ) -> None:
        members = []
        get_members = getattr(target_root, "get_attached_unit_members", None) if target_root is not None else None
        if callable(get_members):
            members = list(get_members() or [])
        if not members and target_root is not None:
            members = [target_root]
        for member in members:
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["tripwires_stunned_active"] = True
            sr["tripwires_stunned_owner"] = str(owner_id or "")
            sr["tripwires_stunned_source"] = str(source or "Tripwires").strip() or "Tripwires"
            sr["tripwires_stunned_hit_roll_modifier"] = int(min(0, int(hit_roll_modifier or -1)))
            sr["tripwires_stunned_turn"] = int(turn or 0)
            member.special_rules = sr

    def recon_element_tripwires_on_enemy_move_ended(
        self,
        moving_unit,
        *,
        action: str,
        game=None,
        player=None,
    ) -> list[dict]:
        if not self.is_recon_element():
            return []
        action_key = str(action or "").strip().lower()
        if action_key not in {"move", "advance", "charge", "fall_back"}:
            return []
        moving_root = self._unit_root(moving_unit)
        if moving_root is None:
            return []
        if not self._unit_is_on_battlefield(moving_root):
            return []
        try:
            owner_army = self.army
            moving_army = moving_root.get_parent_army()
        except Exception:
            moving_army = None
            owner_army = self.army
        if owner_army is not None and moving_army is owner_army:
            return []

        outcome: list[dict] = []
        game_obj = game if game is not None else self._current_game()
        owner_player = player if player is not None else getattr(owner_army, "player", None)
        owner_id = str(get_entity_id(owner_player) or getattr(owner_player, "id", "") or "")
        if not owner_id and owner_player is not None:
            owner_id = str(getattr(owner_player, "id", "") or "")
        try:
            current_turn = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
        except (TypeError, ValueError):
            current_turn = 0

        from ..utility.aura_utils import unit_within_range_of_unit

        seen_sources: set[str] = set()
        for friendly_root in self._friendly_battlefield_roots():
            if friendly_root is None:
                continue
            source_id = self._entity_id(friendly_root)
            if source_id and source_id in seen_sources:
                continue
            source_unit, sr = self._attached_unit_enhancement_source(friendly_root, "enhancement_tripwires")
            if source_unit is None or not isinstance(sr, dict):
                continue
            if source_id:
                seen_sources.add(source_id)

            trigger_actions = {
                str(v or "").strip().lower()
                for v in list(sr.get("enhancement_tripwires_trigger_actions", ()) or ())
                if str(v or "").strip()
            }
            if trigger_actions and action_key not in trigger_actions:
                continue
            target_keywords = {
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_tripwires_target_keywords_any", ("INFANTRY", "MOUNTED")) or ())
                if str(v or "").strip()
            }
            if target_keywords:
                has_valid_keyword = any(self._unit_has_keyword(moving_root, keyword) for keyword in target_keywords)
                if not has_valid_keyword:
                    continue
            try:
                trigger_range = float(sr.get("enhancement_tripwires_range", 9.0) or 9.0)
            except (TypeError, ValueError):
                trigger_range = 9.0
            if trigger_range <= 0:
                continue
            if not bool(
                unit_within_range_of_unit(
                    friendly_root,
                    moving_root,
                    float(trigger_range),
                    use_attached_aggregate=True,
                )
            ):
                continue
            try:
                success_on = int(sr.get("enhancement_tripwires_success_on", 4) or 4)
            except (TypeError, ValueError):
                success_on = 4
            success_on = max(2, min(6, int(success_on)))
            try:
                roll = get_roll("D6")
            except Exception:
                roll = 0
            source_name = str(sr.get("enhancement_tripwires_source", "") or "Tripwires").strip() or "Tripwires"
            applied = int(roll) >= int(success_on)
            if applied:
                try:
                    hit_roll_modifier = int(sr.get("enhancement_tripwires_hit_roll_modifier", -1) or -1)
                except (TypeError, ValueError):
                    hit_roll_modifier = -1
                self._apply_tripwires_stunned(
                    moving_root,
                    owner_id=owner_id,
                    source=source_name,
                    hit_roll_modifier=hit_roll_modifier,
                    turn=int(current_turn),
                )
            outcome.append(
                {
                    "source_unit": friendly_root,
                    "source_name": source_name,
                    "roll": int(roll),
                    "success_on": int(success_on),
                    "applied": bool(applied),
                    "target_unit": moving_root,
                }
            )
        return outcome
