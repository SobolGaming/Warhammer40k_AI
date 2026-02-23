from __future__ import annotations

from typing import Iterable, Optional

from .detachment_manager import DetachmentManagerBase
from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id


class ChaosKnightsDetachmentManager(DetachmentManagerBase):
    faction_id = "QT"

    MALEFIC_SURGE_NAME = "Malefic Surge"
    MARKED_PREY_NAME = "Marked Prey"
    DETACHMENT_INFERNAL_LANCE = "Infernal Lance"
    DETACHMENT_HOUNDPACK_LANCE = "Houndpack Lance"
    HOUNDPACK_CHARACTER_SELECTION_ABILITY = "houndpack_lance_character_selection"

    def __init__(self, army=None):
        super().__init__(army)
        self._malefic_surge_declined_turn: Optional[int] = None
        self._malefic_surge_declined_owner: str = ""
        self.houndpack_marked_prey_unit_id: str = ""
        self.houndpack_marked_prey_turn: int = 0
        self.houndpack_marked_prey_owner_id: str = ""
        self._houndpack_character_unit_ids: set[str] = set()
        self._houndpack_character_selection_resolved: bool = False

    def is_infernal_lance(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_INFERNAL_LANCE)

    def is_houndpack_lance(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_HOUNDPACK_LANCE)

    @staticmethod
    def _unit_root(unit):
        if unit is None:
            return None
        root_fn = getattr(unit, "get_attached_unit_root", None)
        if callable(root_fn):
            root = root_fn()
            if root is not None:
                return root
        return unit

    def _unit_root_id(self, unit) -> str:
        root = self._unit_root(unit)
        if root is None:
            return ""
        return str(get_entity_id(root) or "")

    def _iter_unique_army_roots(self) -> Iterable:
        army = self.army
        if army is None:
            return []
        seen: set[str] = set()
        roots = []
        for unit in list(getattr(army, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            root_id = self._unit_root_id(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            roots.append(root)
        return roots

    def _unit_belongs_to_army(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        parent_fn = getattr(root, "get_parent_army", None)
        if callable(parent_fn):
            return parent_fn() is self.army
        return getattr(root, "parent_army", None) is self.army

    def _unit_has_war_dog_keyword(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if self._unit_has_keyword(root, "WAR DOG"):
            return True
        root_name = str(getattr(root, "name", "") or "")
        return "war dog" in self._norm(root_name)

    def _model_has_war_dog_keyword(self, model, *, unit=None) -> bool:
        if model is not None:
            has_any = getattr(model, "has_any_keyword", None)
            if callable(has_any) and bool(has_any("WAR DOG")):
                return True
        return self._unit_has_war_dog_keyword(unit)

    @staticmethod
    def _unit_is_enemy_of_player(unit, player) -> bool:
        if unit is None or player is None:
            return False
        root = ChaosKnightsDetachmentManager._unit_root(unit)
        if root is None:
            return False
        parent_fn = getattr(root, "get_parent_army", None)
        if callable(parent_fn):
            unit_army = parent_fn()
        else:
            unit_army = getattr(root, "parent_army", None)
        player_army = getattr(player, "army", None)
        if unit_army is None or player_army is None:
            return False
        return unit_army is not player_army

    def apply_houndpack_lance_battleline_keywords(self, unit=None) -> None:
        if not self.is_houndpack_lance():
            return
        roots = [self._unit_root(unit)] if unit is not None else list(self._iter_unique_army_roots())
        for root in roots:
            if root is None:
                continue
            if not self._unit_has_war_dog_keyword(root):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            if any(str(keyword).strip().upper() == "BATTLELINE" for keyword in keywords):
                continue
            keywords.append("Battleline")
            root.keywords = keywords

    def _remove_houndpack_character_keyword(self, unit) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = self._unit_sr(root)
        if not bool(sr.get("houndpack_lance_character_granted")):
            return
        keywords = [
            keyword
            for keyword in list(getattr(root, "keywords", []) or [])
            if str(keyword).strip().upper() != "CHARACTER"
        ]
        root.keywords = keywords
        sr.pop("houndpack_lance_character_granted", None)
        root.special_rules = sr

    def _grant_houndpack_character_keyword(self, unit) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        keywords = list(getattr(root, "keywords", []) or [])
        if not any(str(keyword).strip().upper() == "CHARACTER" for keyword in keywords):
            keywords.append("Character")
            root.keywords = keywords
        sr = self._unit_sr(root)
        sr["houndpack_lance_character_granted"] = True
        root.special_rules = sr

    def _reconcile_houndpack_character_keywords(self) -> None:
        if not self.is_houndpack_lance():
            return
        selected_ids = {str(unit_id or "").strip() for unit_id in self._houndpack_character_unit_ids if str(unit_id or "").strip()}
        valid_ids: set[str] = set()
        for root in list(self._iter_unique_army_roots()):
            if root is None:
                continue
            root_id = self._unit_root_id(root)
            if not root_id:
                continue
            if root_id in selected_ids:
                valid_ids.add(root_id)
                self._grant_houndpack_character_keyword(root)
                continue
            self._remove_houndpack_character_keyword(root)
        self._houndpack_character_unit_ids = valid_ids

    def _houndpack_character_candidates(self) -> list:
        candidates = []
        seen_ids: set[str] = set()
        for root in list(self._iter_unique_army_roots()):
            if root is None:
                continue
            if not self._unit_has_war_dog_keyword(root):
                continue
            root_id = self._unit_root_id(root)
            if not root_id or root_id in seen_ids:
                continue
            seen_ids.add(root_id)
            candidates.append(root)
        candidates.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return candidates

    def can_select_houndpack_character_unit(self, unit) -> bool:
        if not self.is_houndpack_lance():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_has_war_dog_keyword(root):
            return False
        root_id = self._unit_root_id(root)
        if not root_id:
            return False
        if root_id in self._houndpack_character_unit_ids:
            return True
        return len(self._houndpack_character_unit_ids) < 3

    def select_houndpack_character_unit(self, unit) -> bool:
        if not self.can_select_houndpack_character_unit(unit):
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        root_id = self._unit_root_id(root)
        if not root_id:
            return False
        self._houndpack_character_unit_ids.add(root_id)
        self._grant_houndpack_character_keyword(root)
        self._reconcile_houndpack_character_keywords()
        return True

    def ensure_houndpack_character_selection(self) -> None:
        if not self.is_houndpack_lance():
            return
        candidates = list(self._houndpack_character_candidates())
        if len(candidates) < 3:
            self._reconcile_houndpack_character_keywords()
            return
        candidate_ids = {self._unit_root_id(unit) for unit in candidates}
        selected = [
            unit_id
            for unit_id in sorted(self._houndpack_character_unit_ids)
            if unit_id in candidate_ids
        ]
        prioritized = sorted(
            candidates,
            key=lambda unit: (
                0 if getattr(unit, "enhancement", None) is not None or bool(getattr(unit, "is_warlord", False)) else 1,
                str(get_entity_id(unit) or ""),
            ),
        )
        for candidate in prioritized:
            if len(selected) >= 3:
                break
            root_id = self._unit_root_id(candidate)
            if not root_id or root_id in selected:
                continue
            selected.append(root_id)
        self._houndpack_character_unit_ids = set(selected[:3])
        self._reconcile_houndpack_character_keywords()

    def _pending_houndpack_character_request(self, game, *, army_id: str) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS

        target_army_id = str(army_id or "")
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_REALM_OF_CHAOS_UNITS:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != self.HOUNDPACK_CHARACTER_SELECTION_ABILITY:
                continue
            if target_army_id and str(ctx.get("army_id", "") or "") != target_army_id:
                continue
            return True
        return False

    def queue_houndpack_lance_character_selection_request(self, *, game=None, player=None) -> None:
        if not self.is_houndpack_lance():
            return
        if self.army is None:
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return

        self.apply_houndpack_lance_battleline_keywords()
        candidates = list(self._houndpack_character_candidates() or [])
        if len(candidates) < 3:
            return
        if len(candidates) == 3:
            self.ensure_houndpack_character_selection()
            self._houndpack_character_selection_resolved = True
            return
        if self._houndpack_character_selection_resolved and len(self._houndpack_character_unit_ids) == 3:
            return

        army_id = str(get_entity_id(self.army) or "")
        if self._pending_houndpack_character_request(game, army_id=army_id):
            return

        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
        from ..engine.decisions import DecisionOption, DecisionRequest

        candidate_ids = [str(get_entity_id(unit) or "") for unit in candidates if str(get_entity_id(unit) or "")]
        if len(candidate_ids) < 3:
            return
        request = DecisionRequest.create(
            DECISION_SELECT_REALM_OF_CHAOS_UNITS,
            "Houndpack Lance: select exactly three WAR DOG units to gain CHARACTER.",
            player_id=getattr(owner, "id", None),
            options=[DecisionOption.create("Confirm", payload={"action": "confirm"})],
            context={
                "army_id": army_id,
                "ability": self.HOUNDPACK_CHARACTER_SELECTION_ABILITY,
                "ability_name": "Marked Prey",
                "phase": "Muster Armies step",
                "max_units": 3,
                "required_units": 3,
                "allowed_unit_ids": list(candidate_ids),
                "title": "Houndpack Lance",
                "subtitle": "Select exactly three WAR DOG units.",
                "instruction": "Selected units gain the CHARACTER keyword until the end of the battle.",
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)

    def houndpack_character_selection_is_valid(self, unit_ids, *, game=None) -> tuple[bool, str]:
        del game
        if not self.is_houndpack_lance():
            return False, "Houndpack Lance is not active for this army."
        if not isinstance(unit_ids, list):
            return False, "Houndpack Lance selection requires unit_ids."
        unique_ids = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        if len(unique_ids) != 3:
            return False, "Houndpack Lance must select exactly three WAR DOG units."
        candidates = {
            str(get_entity_id(unit) or ""): unit
            for unit in list(self._houndpack_character_candidates() or [])
            if str(get_entity_id(unit) or "")
        }
        for uid in unique_ids:
            if uid not in candidates:
                return False, "Houndpack Lance selection contains an ineligible unit."
        return True, ""

    def apply_houndpack_lance_character_selection(self, unit_ids, *, game=None) -> list[str]:
        del game
        selected = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        valid, _reason = self.houndpack_character_selection_is_valid(selected)
        if not valid:
            return []
        self._houndpack_character_unit_ids = set(selected)
        self._houndpack_character_selection_resolved = True
        self._reconcile_houndpack_character_keywords()
        return list(selected)

    def clear_marked_prey(self) -> None:
        self.houndpack_marked_prey_unit_id = ""
        self.houndpack_marked_prey_turn = 0
        self.houndpack_marked_prey_owner_id = ""

    def _collect_marked_prey_candidates(self, *, game=None, player=None) -> list:
        if game is None or player is None:
            return []
        get_enemy_units = getattr(game, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        enemy_units = list(get_enemy_units(player) or [])
        candidates = []
        seen_ids: set[str] = set()
        for enemy in enemy_units:
            root = self._unit_root(enemy)
            if root is None:
                continue
            root_id = self._unit_root_id(root)
            if not root_id or root_id in seen_ids:
                continue
            seen_ids.add(root_id)
            if not self._unit_on_battlefield(root):
                continue
            if not self._unit_is_enemy_of_player(root, player):
                continue
            candidates.append(root)
        candidates.sort(key=lambda unit: (self._norm(getattr(unit, "name", "")), self._unit_root_id(unit)))
        return candidates

    def build_marked_prey_request(self, *, game=None, player=None):
        if not self.is_houndpack_lance():
            return None
        if game is None or player is None:
            return None
        if self.army is None or getattr(self.army, "player", None) is not player:
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                if str(getattr(req, "player_id", "") or "") != str(getattr(player, "id", "") or ""):
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") == "marked_prey":
                    return None

        candidates = self._collect_marked_prey_candidates(game=game, player=player)
        if not candidates:
            return None

        options = []
        candidate_ids = []
        for candidate in candidates:
            unit_id = self._unit_root_id(candidate)
            if not unit_id:
                continue
            candidate_ids.append(unit_id)
            options.append(
                DecisionOption.create(
                    str(getattr(candidate, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": unit_id},
                )
            )
        if not options:
            return None
        army_id = str(get_entity_id(self.army) or "")
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Marked Prey: select one enemy unit.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "marked_prey",
                "ability_name": self.MARKED_PREY_NAME,
                "army_id": army_id,
                "candidate_unit_ids": list(candidate_ids),
                "optional": False,
            },
        )

    def is_valid_marked_prey_target(self, target_unit, *, player=None, game=None) -> bool:
        del game  # API parity with other target validators.
        if not self.is_houndpack_lance():
            return False
        root = self._unit_root(target_unit)
        if root is None:
            return False
        if not self._unit_on_battlefield(root):
            return False
        if player is not None and not self._unit_is_enemy_of_player(root, player):
            return False
        return bool(self._unit_root_id(root))

    def select_marked_prey(self, target_unit, *, game=None, player=None) -> bool:
        if not self.is_valid_marked_prey_target(target_unit, player=player, game=game):
            return False
        self.houndpack_marked_prey_unit_id = self._unit_root_id(target_unit)
        if game is not None:
            self.houndpack_marked_prey_turn = int(getattr(game, "turn", 0) or 0)
        else:
            self.houndpack_marked_prey_turn = 0
        self.houndpack_marked_prey_owner_id = str(getattr(player, "id", "") or "")
        return True

    def is_marked_prey_target(self, target_unit) -> bool:
        target_id = self._unit_root_id(target_unit)
        if not target_id:
            return False
        return str(self.houndpack_marked_prey_unit_id or "") == str(target_id)

    def marked_prey_sustained_hits_value(self, attacker_model, target_unit, *, game_map=None) -> tuple[int, str]:
        if not self.is_houndpack_lance():
            return 0, ""
        if not str(self.houndpack_marked_prey_unit_id or "").strip():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        target_root = self._unit_root(target_unit)
        if target_root is None or not self.is_marked_prey_target(target_root):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._unit_root(attacker_unit)
        if attacker_root is None:
            return 0, ""
        if not self._unit_belongs_to_army(attacker_root):
            return 0, ""
        if not self._model_has_war_dog_keyword(attacker_model, unit=attacker_root):
            return 0, ""

        resolved_map = game_map
        if resolved_map is None:
            attacker_army = getattr(attacker_root, "get_parent_army", lambda: None)()
            attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
            game = getattr(attacker_player, "game", None) if attacker_player is not None else None
            resolved_map = getattr(game, "map", None) if game is not None else None
        los_fn = getattr(attacker_root, "_has_line_of_sight_to_target", None)
        if resolved_map is not None and callable(los_fn):
            if not bool(los_fn(attacker_model, target_root, resolved_map)):
                return 0, ""
        return 1, self.MARKED_PREY_NAME

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if game is None or player is None or self.army is None:
            return
        if getattr(self.army, "player", None) is not player:
            return
        if self.is_houndpack_lance():
            self.clear_marked_prey()
            request = self.build_marked_prey_request(game=game, player=player)
            if request is not None and hasattr(game, "request_decision"):
                game.request_decision(request)
        if self.is_infernal_lance():
            self.clear_empowered_at_command_phase_start(game=game, player=player)
            self.prompt_malefic_surge_selection(game=game, player=player)

    def validate_detachment_rules(self) -> list[str]:
        errors: list[str] = []
        if not self.is_houndpack_lance():
            return errors
        self.apply_houndpack_lance_battleline_keywords()
        candidates = list(self._houndpack_character_candidates())
        if len(candidates) < 3:
            errors.append("Houndpack Lance: your army must include three or more WAR DOG units.")
            self._reconcile_houndpack_character_keywords()
            return errors
        candidate_ids = {self._unit_root_id(unit) for unit in candidates}
        selected_valid = {
            unit_id for unit_id in self._houndpack_character_unit_ids
            if unit_id in candidate_ids
        }
        if len(selected_valid) > 3:
            errors.append("Houndpack Lance: exactly three WAR DOG units can gain the CHARACTER keyword.")
        self._houndpack_character_unit_ids = set(selected_valid)
        self.ensure_houndpack_character_selection()
        if len(self._houndpack_character_unit_ids) != 3:
            errors.append("Houndpack Lance: exactly three WAR DOG units must be selected to gain the CHARACTER keyword.")
        return errors

    def _unit_is_chaos_knights(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if hasattr(unit, "has_any_keyword") and unit.has_any_keyword("CHAOS KNIGHTS"):
                return True
        except Exception:
            pass
        try:
            for kw in list(getattr(unit, "faction_keywords", []) or []):
                if str(kw or "").strip().upper() == "CHAOS KNIGHTS":
                    return True
        except Exception:
            pass
        try:
            return str(getattr(unit, "faction", "") or "").strip().upper() == "QT"
        except Exception:
            return False

    def _unit_on_battlefield(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            return False
        try:
            if not bool(getattr(unit, "deployed", True)):
                return False
        except Exception:
            pass
        try:
            if hasattr(unit, "is_in_reserves") and callable(unit.is_in_reserves) and unit.is_in_reserves():
                return False
            if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
                return False
        except Exception:
            pass
        return True

    def _current_turn_key(self, game=None) -> int:
        try:
            return int(getattr(game, "turn", 0) or 0)
        except Exception:
            return 0

    def _current_owner_id(self, unit=None, game=None) -> str:
        if unit is not None:
            try:
                army = unit.get_parent_army()
                player = getattr(army, "player", None) if army is not None else None
                return str(getattr(player, "id", "") or "")
            except Exception:
                return ""
        if game is not None:
            try:
                player = game.get_current_player()
                return str(getattr(player, "id", "") or "")
            except Exception:
                return ""
        return ""

    def _unit_sr(self, unit) -> dict:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        return sr

    def is_unit_empowered(self, unit, *, game=None) -> bool:
        if unit is None:
            return False
        sr = self._unit_sr(unit)
        if not sr.get("malefic_surge_empowered"):
            return False
        owner = str(sr.get("malefic_surge_empowered_owner", "") or "")
        if owner:
            current = self._current_owner_id(unit=unit, game=game)
            if current and owner != current:
                return False
        return True

    def unit_used_malefic_surge_this_turn(self, unit, *, game=None) -> bool:
        if unit is None:
            return False
        sr = self._unit_sr(unit)
        owner = str(sr.get("malefic_surge_last_owner", "") or "")
        if owner:
            current = self._current_owner_id(unit=unit, game=game)
            if current and owner != current:
                return False
        try:
            return int(sr.get("malefic_surge_last_turn", -1) or -1) == int(self._current_turn_key(game))
        except Exception:
            return False

    def can_unit_malefic_surge(self, unit, *, game=None, ignore_used: bool = False) -> bool:
        if unit is None:
            return False
        if not self.is_infernal_lance():
            return False
        if not self._unit_is_chaos_knights(unit):
            return False
        if not self._unit_on_battlefield(unit):
            return False
        if not ignore_used and self.unit_used_malefic_surge_this_turn(unit, game=game):
            return False
        return True

    def _mark_empowered(self, unit, *, game=None, source: str = "") -> None:
        sr = self._unit_sr(unit)
        sr["malefic_surge_empowered"] = True
        sr["malefic_surge_empowered_turn"] = int(self._current_turn_key(game))
        sr["malefic_surge_empowered_owner"] = self._current_owner_id(unit=unit, game=game)
        if source:
            sr["malefic_surge_source"] = str(source or "").strip()
        unit.special_rules = sr

    def _mark_used(self, unit, *, game=None, choice: str | None = None) -> None:
        sr = self._unit_sr(unit)
        sr["malefic_surge_last_turn"] = int(self._current_turn_key(game))
        sr["malefic_surge_last_owner"] = self._current_owner_id(unit=unit, game=game)
        if choice:
            sr["malefic_surge_last_choice"] = str(choice or "").strip()
        for key in (
            "malefic_surge_empowered",
            "malefic_surge_empowered_turn",
            "malefic_surge_empowered_owner",
            "malefic_surge_source",
        ):
            sr.pop(key, None)
        unit.special_rules = sr

    def clear_empowered_at_command_phase_start(self, *, game=None, player=None) -> None:
        if not self.is_infernal_lance():
            return
        if self.army is None:
            return
        current_turn = int(self._current_turn_key(game))
        current_owner = str(getattr(player, "id", "") or "") if player is not None else ""
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("malefic_surge_empowered"):
                continue
            owner = str(sr.get("malefic_surge_empowered_owner", "") or "")
            if current_owner and owner and owner != current_owner:
                continue
            try:
                emp_turn = int(sr.get("malefic_surge_empowered_turn", -1) or -1)
            except Exception:
                emp_turn = -1
            if emp_turn >= 0 and emp_turn == current_turn:
                continue
            for key in (
                "malefic_surge_empowered",
                "malefic_surge_empowered_turn",
                "malefic_surge_empowered_owner",
                "malefic_surge_source",
            ):
                sr.pop(key, None)
            sr.pop("malefic_surge_choice_pending", None)
            unit.special_rules = sr
        if player is not None:
            self._malefic_surge_declined_turn = None
            self._malefic_surge_declined_owner = ""

    def _declined_this_turn(self, player=None, game=None) -> bool:
        if player is None:
            return False
        if self._malefic_surge_declined_turn is None:
            return False
        try:
            if int(self._malefic_surge_declined_turn) != int(self._current_turn_key(game)):
                return False
        except Exception:
            return False
        return str(self._malefic_surge_declined_owner or "") == str(getattr(player, "id", "") or "")

    def record_declined(self, *, player=None, game=None) -> None:
        if player is None:
            return
        self._malefic_surge_declined_turn = int(self._current_turn_key(game))
        self._malefic_surge_declined_owner = str(getattr(player, "id", "") or "")

    def get_malefic_surge_candidates(self, *, game=None) -> list:
        if self.army is None or not self.is_infernal_lance():
            return []
        units = []
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            if root in units:
                continue
            if not self.can_unit_malefic_surge(root, game=game):
                continue
            units.append(root)
        units.sort(key=lambda u: str(getattr(u, "name", "")))
        return units

    def prompt_malefic_surge_selection(self, *, game=None, player=None) -> None:
        if game is None or player is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not self.is_infernal_lance():
            return
        if self._declined_this_turn(player=player, game=game):
            return
        candidates = self.get_malefic_surge_candidates(game=game)
        if not candidates:
            return
        from ..engine.decision_kinds import DECISION_CHOOSE_MALEFIC_SURGE_UNIT
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_MALEFIC_SURGE_UNIT:
                    continue
                if str(getattr(req, "player_id", "") or "") == str(getattr(player, "id", "") or ""):
                    return

        options = []
        for unit in candidates:
            options.append(
                DecisionOption.create(
                    getattr(unit, "name", "Unit"),
                    payload={"unit_id": get_entity_id(unit)},
                )
            )
        options.append(
            DecisionOption.create(
                "None",
                payload={"skip": True, "action": "skip", "summary": "Do not select additional units."},
            )
        )
        ctx = {
            "ability": "malefic_surge",
            "ability_name": self.MALEFIC_SURGE_NAME,
            "battle_round": self._current_turn_key(game),
        }
        req = DecisionRequest.create(
            DECISION_CHOOSE_MALEFIC_SURGE_UNIT,
            "Select a unit to make a Malefic Surge (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        game.request_decision(req)

    def apply_malefic_surge(self, unit, *, game=None, ignore_used: bool = False) -> dict:
        if unit is None:
            return {"ok": False, "reason": "unit missing"}
        if not self.can_unit_malefic_surge(unit, game=game, ignore_used=ignore_used):
            return {"ok": False, "reason": "unit not eligible"}
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return {"ok": False, "reason": "unit missing"}
        extra_rerolls = []
        try:
            sr = self._unit_sr(root)
            if sr.get("enhancement_blasphemous_engine"):
                extra_rerolls.append("Blasphemous Engine")
        except Exception:
            extra_rerolls = []
        passed = bool(
            getattr(root, "pass_leadership_check", lambda **_k: True)(
                extra_reroll_sources=extra_rerolls,
                reroll_reason="Malefic Surge",
            )
        )
        if not passed:
            try:
                mortal = int(get_roll("D3") or 0)
            except Exception:
                mortal = 0
            if mortal <= 0:
                mortal = 1
            try:
                root._apply_mortal_wounds_to_unit(root, mortal, game_map=getattr(game, "map", None))
            except Exception:
                pass
        self._mark_empowered(root, game=game, source=self.MALEFIC_SURGE_NAME)
        try:
            if game is not None and hasattr(game, "event_system"):
                army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                player = getattr(army, "player", None) if army is not None else None
                game.event_system.publish(
                    "malefic_surge_applied",
                    unit=root,
                    player=player,
                    game=game,
                )
        except Exception:
            pass
        return {"ok": True, "passed": passed}

    def queue_malefic_surge_choice(self, unit, *, trigger: str, game=None) -> None:
        if unit is None or game is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not self.is_infernal_lance():
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not self.is_unit_empowered(root, game=game):
            return
        sr = self._unit_sr(root)
        if sr.get("malefic_surge_choice_pending"):
            return
        from ..engine.decision_kinds import DECISION_CHOOSE_MALEFIC_SURGE_ABILITY
        from ..engine.decisions import DecisionOption, DecisionRequest

        trigger_key = str(trigger or "").strip().lower()
        if not trigger_key:
            return

        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_MALEFIC_SURGE_ABILITY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("unit_id", "")) == str(get_entity_id(root)) and str(ctx.get("trigger", "")) == trigger_key:
                    return

        options = []
        header = "Select a Malefic Surge ability."
        if trigger_key == "movement":
            options.append(
                DecisionOption.create(
                    "Unholy Hunger",
                    payload={"choice": "UNHOLY_HUNGER", "summary": "Until end of phase, add 3\" to Move."},
                )
            )
            header = "Use Unholy Hunger for this move?"
        elif trigger_key in ("shooting", "fight"):
            options.append(
                DecisionOption.create(
                    "Lethal Hits",
                    payload={"choice": "LETHAL_HITS", "summary": "Weapons gain [LETHAL HITS] until end of phase."},
                )
            )
            options.append(
                DecisionOption.create(
                    "Sustained Hits 1",
                    payload={"choice": "SUSTAINED_HITS_1", "summary": "Weapons gain [SUSTAINED HITS 1] until end of phase."},
                )
            )
            header = "Select Diabolic Power ability."
        elif trigger_key in ("targeted_shooting", "targeted_fight"):
            options.append(
                DecisionOption.create(
                    "5+ Invulnerable Save",
                    payload={"choice": "INVULN_5", "summary": "Models gain a 5+ invulnerable save until end of phase."},
                )
            )
            options.append(
                DecisionOption.create(
                    "Feel No Pain 6+",
                    payload={"choice": "FNP_6", "summary": "Models gain Feel No Pain 6+ until end of phase."},
                )
            )
            header = "Select Unnatural Fortitude effect."
        else:
            return
        options.append(
            DecisionOption.create(
                "Skip",
                payload={"skip": True, "action": "skip", "summary": "Do not use Malefic Surge now."},
            )
        )
        player = None
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        ctx = {
            "ability": "malefic_surge",
            "ability_name": self.MALEFIC_SURGE_NAME,
            "unit_id": get_entity_id(root),
            "trigger": trigger_key,
        }
        req = DecisionRequest.create(
            DECISION_CHOOSE_MALEFIC_SURGE_ABILITY,
            header,
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        sr["malefic_surge_choice_pending"] = True
        root.special_rules = sr
        game.request_decision(req)

    def apply_malefic_surge_choice(self, unit, *, trigger: str, choice: str, game=None) -> bool:
        if unit is None or game is None:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return False
        if not self.is_unit_empowered(root, game=game):
            return False
        trigger_key = str(trigger or "").strip().lower()
        choice_key = str(choice or "").strip().upper()
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if not phase_name:
            phase_name = "SHOOTING_PHASE"
        if trigger_key == "movement" and choice_key == "UNHOLY_HUNGER":
            self._apply_unholy_hunger(root, phase_name=phase_name)
            try:
                if bool(getattr(game, "is_authoritative", True)):
                    from ..engine.decision_handlers.movement import _maybe_request_move_modifier_choice
                    _maybe_request_move_modifier_choice(game, root, action_type="move")
            except Exception:
                pass
        elif trigger_key in ("shooting", "fight") and choice_key in ("LETHAL_HITS", "SUSTAINED_HITS_1"):
            attack_type = "ranged" if trigger_key == "shooting" else "melee"
            self._apply_diabolic_power(root, choice_key, attack_type=attack_type, phase_name=phase_name)
        elif trigger_key in ("targeted_shooting", "targeted_fight") and choice_key in ("INVULN_5", "FNP_6"):
            self._apply_unnatural_fortitude(root, choice_key, phase_name=phase_name)
        else:
            return False
        self._mark_used(root, game=game, choice=choice_key)
        sr = self._unit_sr(root)
        sr.pop("malefic_surge_choice_pending", None)
        root.special_rules = sr
        return True

    def clear_pending_choice(self, unit) -> None:
        if unit is None:
            return
        sr = self._unit_sr(unit)
        sr.pop("malefic_surge_choice_pending", None)
        unit.special_rules = sr

    def _apply_unholy_hunger(self, unit, *, phase_name: str) -> None:
        try:
            models = list(unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        for model in list(models or []):
            if model is None or not getattr(model, "is_alive", True):
                continue
            if not isinstance(getattr(model, "_temporary_effects", None), dict):
                model._temporary_effects = {}
            key = f"malefic_surge_unholy_hunger:{get_entity_id(model)}".strip().lower()
            model._temporary_effects[key] = {
                "expires_phase": str(phase_name or "").strip().upper(),
                "movement_bonus": 3,
                "movement_bonus_source": "Unholy Hunger",
            }
        sr = self._unit_sr(unit)
        sr["malefic_surge_unholy_hunger_active"] = True
        sr["malefic_surge_unholy_hunger_expires_phase"] = str(phase_name or "").strip().upper()
        sr["malefic_surge_unholy_hunger_source"] = self.MALEFIC_SURGE_NAME
        unit.special_rules = sr

    def _apply_diabolic_power(self, unit, choice: str, *, attack_type: str, phase_name: str) -> None:
        sr = self._unit_sr(unit)
        sr["malefic_surge_diabolic_active"] = True
        sr["malefic_surge_diabolic_choice"] = str(choice or "").strip().upper()
        sr["malefic_surge_diabolic_attack_type"] = str(attack_type or "").strip().lower()
        sr["malefic_surge_diabolic_expires_phase"] = str(phase_name or "").strip().upper()
        sr["malefic_surge_diabolic_source"] = self.MALEFIC_SURGE_NAME
        unit.special_rules = sr

    def _apply_unnatural_fortitude(self, unit, choice: str, *, phase_name: str) -> None:
        try:
            models = list(unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        for model in list(models or []):
            if model is None or not getattr(model, "is_alive", True):
                continue
            if choice == "INVULN_5":
                setter = getattr(model, "set_temporary_invulnerable_save", None)
                if callable(setter):
                    setter(
                        key=f"malefic_surge_invuln:{get_entity_id(model)}",
                        value=5,
                        source="Unnatural Fortitude",
                        expires_phase=str(phase_name or "").strip().upper(),
                    )
            elif choice == "FNP_6":
                setter = getattr(model, "set_temporary_fnp", None)
                if callable(setter):
                    setter(
                        key=f"malefic_surge_fnp:{get_entity_id(model)}",
                        value=6,
                        source="Unnatural Fortitude",
                        expires_phase=str(phase_name or "").strip().upper(),
                    )
        sr = self._unit_sr(unit)
        sr["malefic_surge_unnatural_fortitude_active"] = True
        sr["malefic_surge_unnatural_fortitude_expires_phase"] = str(phase_name or "").strip().upper()
        sr["malefic_surge_unnatural_fortitude_source"] = self.MALEFIC_SURGE_NAME
        if sr.get("enhancement_fleshmetal_fusion"):
            sr["fleshmetal_fusion_fortitude_active"] = True
            sr["fleshmetal_fusion_fortitude_expires_phase"] = str(phase_name or "").strip().upper()
            sr["fleshmetal_fusion_fortitude_source"] = "Fleshmetal Fusion"
        unit.special_rules = sr
