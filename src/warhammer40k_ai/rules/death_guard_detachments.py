from __future__ import annotations

from typing import Optional

from ..utility.entity_ids import get_entity_id
from ..utility.dice import get_roll
from .detachment_manager import DetachmentManagerBase
from .nurgles_gift import DEFAULT_PLAGUES, NurglesGiftManager


class DeathGuardDetachmentManager(DetachmentManagerBase):
    faction_id = "DG"
    _MANIFOLD_MALADIES_SOURCE = "Manifold Maladies"
    _MIASMIC_BOMBARDMENT_SOURCE = "Miasmic Bombardment"
    _MIASMIC_BOMBARDMENT_RANGE = 12.0
    _NUMBERLESS_HORDE_SOURCE = "Numberless Horde"
    _NUMBERLESS_HORDE_POXWALKERS_NAME = "Poxwalkers"
    _NUMBERLESS_HORDE_STARTING_STRENGTH = 10
    _REVERBERANT_RANCIDITY_SOURCE = "Reverberant Rancidity"
    _REVERBERANT_RANCIDITY_RANGE = 7.0
    _REVERBERANT_RANCIDITY_CONTAGION_BONUS = 3.0
    _WORLD_BLIGHT_SOURCE = "worldblight"
    _VERMINOUS_HAZE_SCOUT_DISTANCE = 5.0

    def __init__(self, army=None):
        super().__init__(army=army)
        self.manifold_maladies_resolved_round: Optional[int] = None
        self.miasmic_bombardment_resolved_round: Optional[int] = None
        self.numberless_horde_spawned_rounds: set[int] = set()
        self._numberless_horde_cached_datasheet = None

    def is_champions_of_contagion(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Champions of Contagion")

    def is_flyblown_host(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Flyblown Host")

    def is_death_lords_chosen(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Death Lord's Chosen")

    def is_virulent_vectorium(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Virulent Vectorium")

    def is_mortarions_hammer(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Mortarion's Hammer")

    def is_shamblerot_vectorium(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Shamblerot Vectorium")

    def is_tallyband_summoners(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Tallyband Summoners")

    def _resolve_battle_round(self, *, game=None, battle_round=None) -> Optional[int]:
        if battle_round is not None:
            try:
                return int(battle_round)
            except (TypeError, ValueError):
                return None
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        if game is None:
            return None
        try:
            return int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_valid_plague_choice(choice_key: str) -> bool:
        key = str(choice_key or "").strip().upper()
        if not key:
            return False
        return any(str(getattr(plague, "key", "")).strip().upper() == key for plague in list(DEFAULT_PLAGUES))

    def can_select_manifold_maladies(self, *, game=None, battle_round=None) -> bool:
        if not self.is_champions_of_contagion():
            return False
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return False
        if self.manifold_maladies_resolved_round is not None and int(self.manifold_maladies_resolved_round) == int(round_value):
            return False
        gift_mgr = getattr(self.army, "nurgles_gift", None) if self.army is not None else None
        if gift_mgr is None:
            return False
        return bool(getattr(gift_mgr, "_army_has_gift", lambda: False)())

    def select_manifold_maladies(self, choice, *, battle_round=None) -> bool:
        if not self.is_champions_of_contagion():
            return False
        round_value = self._resolve_battle_round(battle_round=battle_round)
        if round_value is None:
            return False
        if self.manifold_maladies_resolved_round is not None and int(self.manifold_maladies_resolved_round) == int(round_value):
            return False
        gift_mgr = getattr(self.army, "nurgles_gift", None) if self.army is not None else None
        if gift_mgr is None:
            return False
        choice_key = str(choice or "").strip().upper()
        if choice_key in ("", "NONE", "SKIP"):
            self.manifold_maladies_resolved_round = int(round_value)
            return True
        if not self._is_valid_plague_choice(choice_key):
            return False
        gift_mgr.active_plague_key = choice_key
        self.manifold_maladies_resolved_round = int(round_value)
        return True

    def _pending_manifold_maladies_request(self, game, *, army_id: str, battle_round: int):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_PLAGUE

        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_PLAGUE:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "manifold_maladies":
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id):
                continue
            if int(ctx.get("battle_round", 0) or 0) != int(battle_round):
                continue
            return req
        return None

    def build_manifold_maladies_request(self, *, game=None, player=None, battle_round=None):
        if not self.is_champions_of_contagion():
            return None
        if game is None or player is None:
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return None
        if not self.can_select_manifold_maladies(game=game, battle_round=round_value):
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_PLAGUE
        from ..engine.decisions import DecisionOption, DecisionRequest

        army_id = str(get_entity_id(self.army) or "") if self.army is not None else ""
        if self._pending_manifold_maladies_request(game, army_id=army_id, battle_round=int(round_value)):
            return None

        options = [
            DecisionOption.create(
                "None",
                payload={
                    "action": "skip",
                    "skip": True,
                    "choice_key": "",
                    "army_id": army_id,
                    "battle_round": int(round_value),
                },
            )
        ]
        for plague in list(DEFAULT_PLAGUES):
            options.append(
                DecisionOption.create(
                    str(getattr(plague, "name", "Plague") or "Plague"),
                    payload={
                        "choice_key": str(getattr(plague, "key", "") or ""),
                        "summary": str(getattr(plague, "summary", "") or ""),
                        "army_id": army_id,
                        "battle_round": int(round_value),
                    },
                )
            )

        request = DecisionRequest.create(
            DECISION_CHOOSE_PLAGUE,
            "Manifold Maladies: select one Plague (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "manifold_maladies",
                "ability_name": self._MANIFOLD_MALADIES_SOURCE,
                "army_id": army_id,
                "battle_round": int(round_value),
                "allowed_choice_keys": [str(getattr(plague, "key", "") or "") for plague in list(DEFAULT_PLAGUES)],
                "optional": True,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return
        if (
            self.manifold_maladies_resolved_round is not None
            and int(self.manifold_maladies_resolved_round) != int(round_value)
        ):
            self.manifold_maladies_resolved_round = None
        if (
            self.miasmic_bombardment_resolved_round is not None
            and int(self.miasmic_bombardment_resolved_round) != int(round_value)
        ):
            self.miasmic_bombardment_resolved_round = None
        if not bool(getattr(game, "is_authoritative", True)):
            return
        player = getattr(self.army, "player", None) if self.army is not None else None
        if player is None:
            return
        if self.is_champions_of_contagion():
            self.build_manifold_maladies_request(game=game, player=player, battle_round=round_value)
        else:
            self.manifold_maladies_resolved_round = None

        if self.is_mortarions_hammer():
            self.build_miasmic_bombardment_request(game=game, player=player, battle_round=round_value)
        else:
            self.miasmic_bombardment_resolved_round = None
            self._clear_miasmic_bombardment_marks(game=game)

        if self.is_shamblerot_vectorium():
            self.apply_shamblerot_vectorium_poxwalkers_battleline_keywords()
        else:
            self.numberless_horde_spawned_rounds = set()

    def _numberless_horde_points_limit(self, *, game=None) -> int:
        points_limit = 0
        if self.army is not None:
            try:
                points_limit = int(getattr(self.army, "points_limit", 0) or 0)
            except (TypeError, ValueError):
                points_limit = 0
        if points_limit > 0:
            return points_limit
        battlefield = getattr(game, "battlefield", None) if game is not None else None
        if battlefield is None:
            return 0
        try:
            return int(getattr(battlefield, "points", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _numberless_horde_spawn_rounds(self, *, game=None) -> tuple[int, ...]:
        points_limit = int(self._numberless_horde_points_limit(game=game) or 0)
        if points_limit <= 1000:
            return (2, 3)
        if points_limit <= 2000:
            return (2, 3, 4)
        return (2, 3, 4, 5)

    def _unit_is_poxwalkers(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "POXWALKERS"):
            return True
        return "poxwalker" in self._norm(getattr(unit, "name", ""))

    def apply_shamblerot_vectorium_poxwalkers_battleline_keywords(self, unit=None) -> None:
        if not self.is_shamblerot_vectorium() or self.army is None:
            return
        entries = list(getattr(self.army, "units", []) or []) if unit is None else [unit]
        for entry in entries:
            root = entry.get_attached_unit_root() if entry is not None else None
            if root is None or not self._unit_in_army(root):
                continue
            if not self._unit_is_poxwalkers(root):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            if any(str(token or "").strip().lower() == "battleline" for token in keywords):
                continue
            keywords.append("Battleline")
            root.keywords = keywords

    def _numberless_horde_poxwalkers_datasheet(self):
        if self._numberless_horde_cached_datasheet is not None:
            return self._numberless_horde_cached_datasheet
        if self.army is not None:
            for unit in list(getattr(self.army, "units", []) or []):
                if unit is None or not self._unit_is_poxwalkers(unit):
                    continue
                datasheet = getattr(unit, "_datasheet", None)
                if datasheet is not None:
                    self._numberless_horde_cached_datasheet = datasheet
                    return datasheet
        from ..waha_helper.waha_helper import WahaHelper

        helper = WahaHelper()
        datasheet = helper.get_full_datasheet_info_by_name(
            self._NUMBERLESS_HORDE_POXWALKERS_NAME,
            faction_id=self.faction_id,
        )
        if datasheet is not None:
            self._numberless_horde_cached_datasheet = datasheet
        return datasheet

    def _create_numberless_horde_poxwalkers_unit(self):
        datasheet = self._numberless_horde_poxwalkers_datasheet()
        if datasheet is None:
            return None
        from ..units.unit import Unit as UnitClass

        try:
            unit = UnitClass(datasheet, quantity=int(self._NUMBERLESS_HORDE_STARTING_STRENGTH))
        except TypeError:
            unit = UnitClass(datasheet)
        unit.spawned_in_battle = True
        return unit

    def _prepare_numberless_horde_unit(self, unit, *, game=None) -> bool:
        if unit is None or self.army is None:
            return False
        set_parent = getattr(unit, "set_parent_army", None)
        if callable(set_parent):
            set_parent(self.army)
        else:
            unit.parent_army = self.army
        set_reserve = getattr(unit, "set_reserve_status", None)
        if callable(set_reserve):
            set_reserve("strategic_reserves")
        else:
            unit.reserve_status = "strategic_reserves"
        mark_midgame = getattr(unit, "mark_entered_reserves_midgame", None)
        if callable(mark_midgame):
            mark_midgame(game=game)
        unit.deployed = True
        unit.reserve_turn_deployed = None
        unit.arrived_from_reserves_this_turn = False
        self.army.add_unit(unit)
        self.apply_shamblerot_vectorium_poxwalkers_battleline_keywords(unit)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is not None and hasattr(game_map, "units") and unit in game_map.units:
            game_map.units.remove(unit)
        return True

    def spawn_numberless_horde_unit(self, *, game=None, battle_round=None):
        if not self.is_shamblerot_vectorium():
            return None
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None or int(round_value) <= 0:
            return None
        if int(round_value) not in set(self._numberless_horde_spawn_rounds(game=game)):
            return None
        if int(round_value) in set(int(v) for v in list(self.numberless_horde_spawned_rounds or set())):
            return None
        unit = self._create_numberless_horde_poxwalkers_unit()
        if unit is None:
            return None
        if not self._prepare_numberless_horde_unit(unit, game=game):
            return None
        self.numberless_horde_spawned_rounds.add(int(round_value))
        return unit

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if not self.is_shamblerot_vectorium():
            return
        owner = getattr(self.army, "player", None) if self.army is not None else None
        if owner is None or player is not owner:
            return
        if game is None:
            game = getattr(owner, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name and phase_name != "COMMAND_PHASE":
            return
        self.apply_shamblerot_vectorium_poxwalkers_battleline_keywords()
        round_value = self._resolve_battle_round(game=game)
        if round_value is None:
            return
        spawned = self.spawn_numberless_horde_unit(game=game, battle_round=int(round_value))
        if spawned is None:
            return
        event_system = getattr(game, "event_system", None)
        if event_system is not None:
            event_system.publish(
                "action_log",
                player=owner,
                message=(
                    f"{self._NUMBERLESS_HORDE_SOURCE}: added "
                    f"{getattr(spawned, 'name', self._NUMBERLESS_HORDE_POXWALKERS_NAME)} "
                    "to Strategic Reserves at Starting Strength 10."
                ),
            )

    def _miasmic_bombardment_max_units(self, *, game=None) -> int:
        points_limit = 0
        battlefield = getattr(game, "battlefield", None) if game is not None else None
        if battlefield is not None:
            try:
                points_limit = int(getattr(battlefield, "points", 0) or 0)
            except (TypeError, ValueError):
                points_limit = 0
        if points_limit <= 0:
            try:
                points_limit = int(getattr(self.army, "points_limit", 0) or 0)
            except (TypeError, ValueError):
                points_limit = 0
        if points_limit <= 1000:
            return 1
        if points_limit <= 2000:
            return 2
        return 3

    def _collect_miasmic_bombardment_candidates(self, *, game=None) -> list:
        if game is None or self.army is None:
            return []
        from ..utility import aura_utils as _aura_utils

        friendly_sources = [
            root
            for root in list(self._iter_unique_attached_roots() or [])
            if self._unit_eligible_for_deadly_vectors(root)
        ]
        owner = getattr(self.army, "player", None)
        candidates_by_id: dict[str, object] = {}
        for player in list(getattr(game, "players", []) or []):
            if player is None or player is owner:
                continue
            enemy_army = getattr(player, "army", None)
            if enemy_army is None and hasattr(player, "get_army"):
                enemy_army = player.get_army()
            for root in list(self._iter_unique_enemy_roots(enemy_army) or []):
                root_id = str(get_entity_id(root) or "")
                if not root_id or root_id in candidates_by_id:
                    continue
                if not self._unit_eligible_for_deadly_vectors(root):
                    continue
                too_close = False
                for source in friendly_sources:
                    if _aura_utils.unit_within_range_of_unit(
                        source,
                        root,
                        float(self._MIASMIC_BOMBARDMENT_RANGE),
                        use_attached_aggregate=True,
                    ):
                        too_close = True
                        break
                if too_close:
                    continue
                candidates_by_id[root_id] = root
        return [candidates_by_id[uid] for uid in sorted(candidates_by_id)]

    def _pending_miasmic_bombardment_request(self, game, *, army_id: str, battle_round: int):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS

        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_REALM_OF_CHAOS_UNITS:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "miasmic_bombardment":
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id):
                continue
            if int(ctx.get("battle_round", 0) or 0) != int(battle_round):
                continue
            return req
        return None

    @staticmethod
    def _clear_miasmic_bombardment_mark(unit) -> None:
        if unit is None:
            return
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return
        changed = False
        for key in (
            "miasmic_bombardment_active",
            "miasmic_bombardment_owner",
            "miasmic_bombardment_round",
            "miasmic_bombardment_source",
        ):
            if key in sr:
                sr.pop(key, None)
                changed = True
        if changed:
            unit.special_rules = sr

    def _clear_miasmic_bombardment_marks(self, *, game=None, keep_round: int = 0) -> None:
        if game is None or self.army is None:
            return
        owner = getattr(self.army, "player", None)
        owner_id = str(getattr(owner, "id", "") or "")
        if not owner_id:
            return
        keep_round_value = int(keep_round or 0)
        for player in list(getattr(game, "players", []) or []):
            if player is None or player is owner:
                continue
            enemy_army = getattr(player, "army", None)
            if enemy_army is None and hasattr(player, "get_army"):
                enemy_army = player.get_army()
            for root in list(self._iter_unique_enemy_roots(enemy_army) or []):
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if not bool(sr.get("miasmic_bombardment_active", False)):
                    continue
                if str(sr.get("miasmic_bombardment_owner", "") or "") != owner_id:
                    continue
                try:
                    marked_round = int(sr.get("miasmic_bombardment_round", 0) or 0)
                except (TypeError, ValueError):
                    marked_round = 0
                if keep_round_value > 0 and marked_round == keep_round_value:
                    continue
                self._clear_miasmic_bombardment_mark(root)

    def can_select_miasmic_bombardment(self, *, game=None, battle_round=None) -> bool:
        if not self.is_mortarions_hammer():
            return False
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        if game is None:
            return False
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return False
        if (
            self.miasmic_bombardment_resolved_round is not None
            and int(self.miasmic_bombardment_resolved_round) == int(round_value)
        ):
            return False
        candidates = list(self._collect_miasmic_bombardment_candidates(game=game) or [])
        if not candidates:
            return False
        return int(self._miasmic_bombardment_max_units(game=game) or 0) > 0

    def miasmic_bombardment_selection_is_valid(self, unit_ids, *, game=None, battle_round=None) -> tuple[bool, str]:
        if not self.is_mortarions_hammer():
            return False, "Miasmic Bombardment requires Mortarion's Hammer."
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        if game is None:
            return False, "Miasmic Bombardment requires a game context."
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None or int(round_value) <= 0:
            return False, "Miasmic Bombardment requires a valid battle round."
        if (
            self.miasmic_bombardment_resolved_round is not None
            and int(self.miasmic_bombardment_resolved_round) == int(round_value)
        ):
            return False, "Miasmic Bombardment has already resolved this battle round."
        if not isinstance(unit_ids, list):
            return False, "Miasmic Bombardment selection requires unit_ids."

        selected_ids = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        max_units = int(self._miasmic_bombardment_max_units(game=game) or 0)
        if len(selected_ids) > max(0, max_units):
            return False, f"Miasmic Bombardment can select at most {int(max_units)} unit(s)."

        candidate_ids = {
            str(get_entity_id(unit) or "")
            for unit in list(self._collect_miasmic_bombardment_candidates(game=game) or [])
            if str(get_entity_id(unit) or "")
        }
        for uid in selected_ids:
            if uid not in candidate_ids:
                return False, "Miasmic Bombardment selection contains an ineligible unit."
        return True, ""

    def apply_miasmic_bombardment_selection(self, unit_ids, *, game=None, battle_round: int = 0) -> list[str]:
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return []
        valid, _reason = self.miasmic_bombardment_selection_is_valid(
            unit_ids,
            game=game,
            battle_round=round_value,
        )
        if not valid:
            return []

        selected_ids = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        max_units = int(self._miasmic_bombardment_max_units(game=game) or 0)
        candidates_by_id = {
            str(get_entity_id(unit) or ""): unit
            for unit in list(self._collect_miasmic_bombardment_candidates(game=game) or [])
            if str(get_entity_id(unit) or "")
        }

        self._clear_miasmic_bombardment_marks(game=game)
        owner = getattr(self.army, "player", None) if self.army is not None else None
        owner_id = str(getattr(owner, "id", "") or "")
        applied_ids: list[str] = []
        for uid in list(selected_ids)[: max(0, int(max_units))]:
            unit = candidates_by_id.get(str(uid))
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["miasmic_bombardment_active"] = True
            sr["miasmic_bombardment_owner"] = owner_id
            sr["miasmic_bombardment_round"] = int(round_value)
            sr["miasmic_bombardment_source"] = self._MIASMIC_BOMBARDMENT_SOURCE
            unit.special_rules = sr
            applied_ids.append(str(uid))

        self.miasmic_bombardment_resolved_round = int(round_value)
        return applied_ids

    def build_miasmic_bombardment_request(self, *, game=None, player=None, battle_round=None):
        if not self.is_mortarions_hammer():
            return None
        if game is None or player is None:
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return None
        if (
            self.miasmic_bombardment_resolved_round is not None
            and int(self.miasmic_bombardment_resolved_round) == int(round_value)
        ):
            return None

        army_id = str(get_entity_id(self.army) or "") if self.army is not None else ""
        if self._pending_miasmic_bombardment_request(game, army_id=army_id, battle_round=int(round_value)):
            return None

        self._clear_miasmic_bombardment_marks(game=game, keep_round=int(round_value))
        candidates = list(self._collect_miasmic_bombardment_candidates(game=game) or [])
        candidate_ids = sorted(
            {str(get_entity_id(unit) or "") for unit in candidates if str(get_entity_id(unit) or "")}
        )
        max_units = min(
            int(self._miasmic_bombardment_max_units(game=game) or 0),
            len(candidate_ids),
        )
        if max_units <= 0 or not candidate_ids:
            self.miasmic_bombardment_resolved_round = int(round_value)
            return None

        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
        from ..engine.decisions import DecisionOption, DecisionRequest

        request = DecisionRequest.create(
            DECISION_SELECT_REALM_OF_CHAOS_UNITS,
            "Miasmic Bombardment: select enemy units to become Afflicted.",
            player_id=getattr(player, "id", None),
            options=[
                DecisionOption.create("Confirm", payload={"action": "confirm"}),
                DecisionOption.create("None", payload={"action": "skip", "skip": True}),
            ],
            context={
                "ability": "miasmic_bombardment",
                "ability_name": self._MIASMIC_BOMBARDMENT_SOURCE,
                "army_id": army_id,
                "battle_round": int(round_value),
                "max_units": int(max_units),
                "allowed_unit_ids": list(candidate_ids),
                "optional": True,
                "title": self._MIASMIC_BOMBARDMENT_SOURCE,
                "subtitle": f"Select up to {int(max_units)} enemy unit(s) more than 12\" away.",
                "instruction": "Selected units are Afflicted until end of battle round.",
                "skip_label": "None (do not select units)",
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        return unit.get_parent_army() is self.army

    def _unit_is_death_guard(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword_or_faction(unit, "DEATH GUARD", faction_id=self.faction_id)

    def _unit_is_plague_legions(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "PLAGUE LEGIONS")

    @staticmethod
    def _unit_points(unit) -> int:
        if unit is None:
            return 0
        get_cost = getattr(unit, "get_unit_cost", None)
        if callable(get_cost):
            try:
                return int(get_cost() or 0)
            except (TypeError, ValueError, AttributeError):
                return 0
        try:
            return int(getattr(unit, "points", 0) or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _tallyband_summoners_plague_legions_points_cap(points_limit: int) -> tuple[int, str]:
        if points_limit <= 1000:
            return 500, "Incursion"
        if points_limit <= 2000:
            return 1000, "Strike Force"
        return 1500, "Onslaught"

    def _unit_is_reverberant_rancidity_eligible(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_in_army(unit):
            return False
        return self._unit_eligible_for_deadly_vectors(unit)

    def _reverberant_rancidity_has_nearby_unit(self, source_unit, *, keyword: str) -> bool:
        if source_unit is None or not keyword:
            return False
        if not self._unit_is_reverberant_rancidity_eligible(source_unit):
            return False
        from ..utility import aura_utils as _aura_utils

        for root in self._iter_unique_attached_roots():
            if root is None or root is source_unit:
                continue
            if not self._unit_is_reverberant_rancidity_eligible(root):
                continue
            if not self._unit_has_keyword(root, keyword):
                continue
            if _aura_utils.unit_within_range_of_unit(
                source_unit,
                root,
                float(self._REVERBERANT_RANCIDITY_RANGE),
                use_attached_aggregate=True,
            ):
                return True
        return False

    def reverberant_rancidity_grants_nurgles_gift_source(self, unit, *, game=None, game_map=None) -> bool:
        del game
        del game_map
        if not self.is_tallyband_summoners():
            return False
        if unit is None:
            return False
        root = unit.get_attached_unit_root()
        if root is None:
            return False
        if not self._unit_is_plague_legions(root):
            return False
        return self._reverberant_rancidity_has_nearby_unit(root, keyword="DEATH GUARD")

    def reverberant_rancidity_contagion_range_bonus_for_unit(self, unit, *, game=None, game_map=None) -> float:
        del game
        del game_map
        if not self.is_tallyband_summoners():
            return 0.0
        if unit is None:
            return 0.0
        root = unit.get_attached_unit_root()
        if root is None:
            return 0.0
        if not self._unit_is_death_guard(root):
            return 0.0
        if not self._reverberant_rancidity_has_nearby_unit(root, keyword="PLAGUE LEGIONS"):
            return 0.0
        return float(self._REVERBERANT_RANCIDITY_CONTAGION_BONUS)

    def _iter_unique_attached_roots(self):
        if self.army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = unit.get_attached_unit_root()
            uid = get_entity_id(root)
            if uid in seen:
                continue
            seen.add(uid)
            yield root

    @staticmethod
    def _enemy_root_sort_key(unit) -> str:
        return str(get_entity_id(unit) or "")

    def _iter_unique_enemy_roots(self, enemy_army):
        if enemy_army is None:
            return []
        roots = []
        seen: set[str] = set()
        for unit in list(getattr(enemy_army, "units", []) or []):
            if unit is None:
                continue
            root = unit.get_attached_unit_root()
            uid = str(get_entity_id(root) or "")
            if uid in seen:
                continue
            seen.add(uid)
            roots.append(root)
        roots.sort(key=self._enemy_root_sort_key)
        return roots

    def _unit_eligible_for_deadly_vectors(self, unit) -> bool:
        if unit is None:
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if not bool(unit.is_alive()):
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return False
        if bool(unit.is_in_reserves()):
            return False
        return True

    def _unit_is_verminous_haze_eligible(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_in_army(unit):
            return False
        if not self._unit_is_death_guard(unit):
            return False
        if not self._unit_has_keyword(unit, "INFANTRY"):
            return False
        if self._unit_has_keyword(unit, "POXWALKERS"):
            return False
        if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
            return False
        return True

    def verminous_haze_applies_to_unit(self, unit) -> bool:
        if not self.is_flyblown_host():
            return False
        return self._unit_is_verminous_haze_eligible(unit)

    def verminous_haze_scout_distance_for_unit(self, unit) -> float:
        if not self.verminous_haze_applies_to_unit(unit):
            return 0.0
        return float(self._VERMINOUS_HAZE_SCOUT_DISTANCE)

    def resolve_deadly_vectors(self, *, game=None, opponent_player=None) -> list[dict]:
        if not self.is_death_lords_chosen():
            return []
        if game is None or opponent_player is None:
            return []
        if not bool(getattr(game, "is_authoritative", True)):
            return []
        opponent_army = getattr(opponent_player, "army", None)
        if opponent_army is None or opponent_army is self.army:
            return []
        game_map = getattr(game, "map", None)
        if game_map is None:
            return []

        outcomes: list[dict] = []
        for unit in self._iter_unique_enemy_roots(opponent_army):
            if not self._unit_eligible_for_deadly_vectors(unit):
                continue
            afflicted = NurglesGiftManager.get_afflicted_plague_for_unit(unit, game=game, game_map=game_map)
            if afflicted is None:
                continue
            roll_2d6 = int(get_roll("2D6") or 0)
            modifier = -1 if bool(unit.is_below_half_strength()) else 0
            total = int(roll_2d6 + modifier)
            mortal_wounds = 0
            if total <= 6:
                mortal_wounds = int(get_roll("D3") or 0)
                if mortal_wounds > 0:
                    unit._apply_mortal_wounds_to_unit(unit, int(mortal_wounds), game_map=game_map)
            outcomes.append(
                {
                    "unit_id": str(get_entity_id(unit) or ""),
                    "roll_2d6": int(roll_2d6),
                    "modifier": int(modifier),
                    "total": int(total),
                    "mortal_wounds": int(max(0, mortal_wounds)),
                }
            )
        return outcomes

    def _unit_eligible_for_worldblight(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_in_army(unit):
            return False
        if not self._unit_is_death_guard(unit):
            return False
        if not unit.is_alive():
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if unit.is_battle_shocked():
            return False
        return True

    def _attached_unit_has_arch_contaminator(self, unit) -> bool:
        if unit is None:
            return False
        root = unit.get_attached_unit_root()
        members = list(root.get_attached_unit_members() or [])
        for member in members:
            sr = getattr(member, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_arch_contaminator"):
                return True
        return False

    def _root_within_controlled_objective(self, root, game) -> bool:
        if root is None or game is None:
            return False
        game_map = getattr(game, "map", None)
        if game_map is None:
            return False
        player = getattr(self.army, "player", None)
        if player is None:
            return False
        objectives = list(getattr(game_map, "objectives", []) or [])
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            loc.update_control(game)
            if getattr(loc, "controlling_player", None) is not player:
                continue
            if root.is_within_objective_range(loc):
                return True
        return False

    def arch_contaminator_reroll_wounds(self, unit, *, game=None) -> bool:
        if not self.is_virulent_vectorium():
            return False
        if unit is None or game is None:
            return False
        root = unit.get_attached_unit_root()
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_death_guard(root):
            return False
        if not root.is_alive() or not bool(getattr(root, "deployed", False)):
            return False
        if not self._attached_unit_has_arch_contaminator(root):
            return False
        return self._root_within_controlled_objective(root, game)

    def on_command_phase_end(self, *, game=None, player=None) -> None:
        if not self.is_virulent_vectorium():
            return
        if game is None or player is None:
            return
        if getattr(player, "army", None) is not self.army:
            return
        game_map = getattr(game, "map", None)
        if game_map is None:
            return
        objectives = list(getattr(game_map, "objectives", []) or [])
        if not objectives:
            return

        # Ensure control state is up to date before applying sticky effects.
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            loc.update_control(game)

        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            if getattr(loc, "controlling_player", None) is not player:
                continue

            has_eligible_unit = False
            for root in self._iter_unique_attached_roots():
                if not self._unit_eligible_for_worldblight(root):
                    continue
                if root.is_within_objective_range(loc):
                    has_eligible_unit = True
                    break
            if not has_eligible_unit:
                continue

            loc.set_sticky_control(player, source=self._WORLD_BLIGHT_SOURCE)
            loc.worldblight_controller = player
            loc.worldblight_source = self._WORLD_BLIGHT_SOURCE

    def validate_detachment_rules(self) -> list[str]:
        errors: list[str] = []
        if not self.is_tallyband_summoners():
            return errors
        if self.army is None:
            return errors

        points_limit = int(getattr(self.army, "points_limit", 0) or 0)
        cap, size_label = self._tallyband_summoners_plague_legions_points_cap(points_limit)
        plague_legions_points = 0
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            if not self._unit_is_plague_legions(unit):
                continue
            plague_legions_points += self._unit_points(unit)
        if plague_legions_points > cap:
            errors.append(
                f"Tallyband Summoners ({self._REVERBERANT_RANCIDITY_SOURCE}): "
                f"PLAGUE LEGIONS points ({plague_legions_points}) exceed the {size_label} cap of {cap}."
            )

        warlord = getattr(self.army, "warlord", None)
        if warlord is None:
            for unit in list(getattr(self.army, "units", []) or []):
                if bool(getattr(unit, "is_warlord", False)):
                    warlord = unit
                    break
        if warlord is not None and self._unit_is_plague_legions(warlord):
            errors.append(
                f"Tallyband Summoners ({self._REVERBERANT_RANCIDITY_SOURCE}): "
                "PLAGUE LEGIONS models cannot be your WARLORD."
            )
        return errors
