from __future__ import annotations

from typing import Any, Iterable

from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class AstraMilitarumDetachmentManager(DetachmentManagerBase):
    faction_id = "AM"
    _ARTILLERY_SUPPORT_MODE_ABILITY = "siege_regiment_artillery_support_mode"
    _ARTILLERY_SUPPORT_INCENDIARY_ABILITY = "siege_regiment_incendiary_bombardment"
    _ARTILLERY_SUPPORT_SMOKE_ABILITY = "siege_regiment_smoke_shells"
    _ARTILLERY_SUPPORT_CREEPING_SELECTION_ABILITY = "siege_regiment_creeping_barrage_selection"
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

        rolls = []
        successful = []
        for enemy in list(candidates or []):
            roll_value = int(get_roll("D6") or 0)
            enemy_id = self._entity_id(enemy)
            rolls.append({"unit_id": enemy_id, "roll": int(roll_value)})
            if roll_value >= 5:
                successful.append(enemy)
        successful.sort(key=lambda unit: self._entity_id(unit))
        successful_ids = [self._entity_id(unit) for unit in list(successful or []) if self._entity_id(unit)]

        if len(successful_ids) <= int(max_units):
            shaken_ids = self.apply_siege_regiment_creeping_barrage_selection(
                successful_ids,
                game=game,
                player=owner,
                battle_round=int(battle_round or 0),
                allowed_unit_ids=successful_ids,
            )
            return {
                "mode": "creeping_barrage",
                "max_units": int(max_units),
                "candidate_unit_ids": [self._entity_id(unit) for unit in list(candidates or []) if self._entity_id(unit)],
                "successful_unit_ids": list(successful_ids),
                "shaken_unit_ids": list(shaken_ids),
                "rolls": rolls,
                "pending_selection": False,
            }

        queued = self._queue_siege_regiment_unit_selection_request(
            game=game,
            player=owner,
            battle_round=int(battle_round or 0),
            ability_key=self._ARTILLERY_SUPPORT_CREEPING_SELECTION_ABILITY,
            ability_name="Creeping Barrage",
            prompt=(
                "Creeping Barrage: select "
                f"{int(max_units)} successful unit(s) to be shaken (Move -2\", Charge -2)."
            ),
            allowed_units=successful,
            max_units=int(max_units),
            allow_skip=False,
            required_units=int(max_units),
        )
        return {
            "mode": "creeping_barrage",
            "max_units": int(max_units),
            "candidate_unit_ids": [self._entity_id(unit) for unit in list(candidates or []) if self._entity_id(unit)],
            "successful_unit_ids": list(successful_ids),
            "shaken_unit_ids": [],
            "rolls": rolls,
            "pending_selection": bool(queued),
            "required_units": int(max_units),
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
        return bool(transport_id)

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

    def _unit_has_order(self, unit) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict) and str(sr.get("voice_of_command_order_key", "") or "").strip():
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
