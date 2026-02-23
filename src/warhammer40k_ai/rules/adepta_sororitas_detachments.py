from __future__ import annotations

from itertools import combinations

from ..utility.entity_ids import maybe_entity_id
from .detachment_manager import DetachmentManagerBase


class AdeptaSororitasDetachmentManager(DetachmentManagerBase):
    faction_id = "AS"

    THE_BLOOD_OF_MARTYRS_NAME = "The Blood of Martyrs"
    SACRED_RITES_NAME = "Sacred Rites"
    FERVENT_PURGATION_NAME = "Fervent Purgation"
    RIGHTEOUS_PURPOSE_NAME = "Righteous Purpose"
    DESPERATE_FOR_REDEMPTION_NAME = "Desperate for Redemption"

    _RIGHTEOUS_PURPOSE_ABILITY_KEY = "righteous_purpose"
    _RIGHTEOUS_PURPOSE_ACTIVE_KEY = "champions_of_faith_righteous_active"
    _RIGHTEOUS_PURPOSE_SOURCE_KEY = "champions_of_faith_righteous_source"

    _RIGHTEOUS_PURPOSE_SKILL_UNIT_NAMES = (
        "battle sisters squad",
        "celestian sacresants",
        "paragon warsuits",
    )
    _RIGHTEOUS_PURPOSE_SACRESANTS_UNIT_NAMES = ("celestian sacresants",)
    _DESPERATE_FOR_REDEMPTION_ABILITY_KEY = "desperate_for_redemption"
    _PATH_OF_THE_PENITENT_KEY = "path_of_the_penitent"
    _ABSOLUTION_IN_BATTLE_KEY = "absolution_in_battle"
    _DEATH_BEFORE_DISGRACE_KEY = "death_before_disgrace"
    _DESPERATE_FOR_REDEMPTION_VOWS = (
        (_PATH_OF_THE_PENITENT_KEY, "The Path of the Penitent"),
        (_ABSOLUTION_IN_BATTLE_KEY, "Absolution in Battle"),
        (_DEATH_BEFORE_DISGRACE_KEY, "Death Before Disgrace"),
    )

    def __init__(self, army=None):
        super().__init__(army=army)
        self.desperate_for_redemption_active_vow: str = ""
        self.desperate_for_redemption_active_battle_round: int = 0
        self.desperate_for_redemption_active_player_id: str = ""
        self.desperate_for_redemption_used_vows: list[str] = []

    def is_hallowed_martyrs(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hallowed Martyrs")

    def is_army_of_faith(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Army of Faith")

    def is_bringers_of_flame(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Bringers of Flame")

    def is_champions_of_faith(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Champions of Faith")

    def is_penitent_host(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Penitent Host")

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

    @staticmethod
    def _unit_id(unit) -> str:
        return str(maybe_entity_id(unit) or "")

    @staticmethod
    def _unit_is_alive(unit) -> bool:
        if unit is None:
            return False
        is_alive_val = getattr(unit, "is_alive", None)
        if callable(is_alive_val):
            return bool(is_alive_val())
        return bool(is_alive_val)

    @staticmethod
    def _unit_is_deployed_on_battlefield(unit) -> bool:
        if unit is None:
            return False
        if not bool(getattr(unit, "deployed", True)):
            return False
        status = str(getattr(unit, "reserve_status", "deployed") or "deployed").strip().lower()
        if status != "deployed":
            return False
        in_reserves_fn = getattr(unit, "is_in_reserves", None)
        if callable(in_reserves_fn):
            return not bool(in_reserves_fn())
        return True

    def _transport_is_on_battlefield(self, transport_unit) -> bool:
        if transport_unit is None:
            return False
        if not self._unit_is_alive(transport_unit):
            return False
        return self._unit_is_deployed_on_battlefield(transport_unit)

    def _unit_is_on_battlefield_or_embarked(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_is_alive(unit):
            return False
        embarked_in = getattr(unit, "embarked_in", None)
        if embarked_in is not None:
            return self._transport_is_on_battlefield(embarked_in)
        if bool(getattr(unit, "is_embarked", False)):
            return True
        return self._unit_is_deployed_on_battlefield(unit)

    @staticmethod
    def _unit_is_battle_shocked(unit) -> bool:
        if unit is None:
            return False
        fn = getattr(unit, "is_battle_shocked", None)
        if callable(fn):
            return bool(fn())
        return bool(getattr(unit, "battle_shocked", False))

    def _unit_name_key(self, unit) -> str:
        return self._norm(str(getattr(unit, "name", "") or ""))

    def _unit_name_matches_any(self, unit, names: tuple[str, ...]) -> bool:
        if unit is None:
            return False
        unit_name = self._unit_name_key(unit)
        if not unit_name:
            return False
        if unit_name in names:
            return True
        return any(unit_name.startswith(f"{name} ") for name in names)

    def _resolve_game_context(self, *, game=None):
        if game is not None:
            return game
        army = self.army
        if army is None:
            return None
        player = getattr(army, "player", None)
        if player is None:
            return None
        return getattr(player, "game", None)

    @classmethod
    def _normalize_desperate_for_redemption_vow_key(cls, choice_key: str) -> str:
        key = str(choice_key or "").strip().lower()
        if not key:
            return ""
        for candidate, _label in cls._DESPERATE_FOR_REDEMPTION_VOWS:
            if key == candidate:
                return candidate
        return ""

    @classmethod
    def desperate_for_redemption_vow_label(cls, choice_key: str) -> str:
        normalized = cls._normalize_desperate_for_redemption_vow_key(choice_key)
        if not normalized:
            return "None"
        for key, label in cls._DESPERATE_FOR_REDEMPTION_VOWS:
            if key == normalized:
                return str(label)
        return "None"

    def _desperate_for_redemption_used_vow_set(self) -> set[str]:
        values = [
            self._normalize_desperate_for_redemption_vow_key(v)
            for v in list(getattr(self, "desperate_for_redemption_used_vows", []) or [])
        ]
        return {v for v in values if v}

    def desperate_for_redemption_available_vow_keys(self) -> list[str]:
        if not self.is_penitent_host():
            return []
        used = self._desperate_for_redemption_used_vow_set()
        out: list[str] = []
        for key, _label in self._DESPERATE_FOR_REDEMPTION_VOWS:
            if key in used:
                continue
            out.append(key)
        return out

    def clear_desperate_for_redemption_active_vow(self) -> None:
        self.desperate_for_redemption_active_vow = ""
        self.desperate_for_redemption_active_battle_round = 0
        self.desperate_for_redemption_active_player_id = ""

    def desperate_for_redemption_active_vow_key(self, *, game=None, battle_round=None) -> str:
        if not self.is_penitent_host():
            return ""
        active = self._normalize_desperate_for_redemption_vow_key(
            str(getattr(self, "desperate_for_redemption_active_vow", "") or "")
        )
        if not active:
            return ""
        if battle_round is None:
            game_obj = self._resolve_game_context(game=game)
            if game_obj is not None:
                battle_round = int(getattr(game_obj, "turn", 0) or 0)
        try:
            battle_round_int = int(battle_round or 0)
        except (TypeError, ValueError):
            battle_round_int = 0
        try:
            selected_round = int(getattr(self, "desperate_for_redemption_active_battle_round", 0) or 0)
        except (TypeError, ValueError):
            selected_round = 0
        if selected_round and battle_round_int and selected_round != battle_round_int:
            return ""
        return active

    def can_select_desperate_for_redemption_vow(self, choice_key: str) -> bool:
        if not self.is_penitent_host():
            return False
        key = self._normalize_desperate_for_redemption_vow_key(choice_key)
        if not key:
            return False
        return key in set(self.desperate_for_redemption_available_vow_keys())

    def select_desperate_for_redemption_vow(
        self,
        choice_key: str,
        *,
        battle_round: int = 0,
        player_id: str = "",
    ) -> bool:
        if not self.is_penitent_host():
            return False
        key = self._normalize_desperate_for_redemption_vow_key(choice_key)
        if not key:
            self.clear_desperate_for_redemption_active_vow()
            return True
        if key not in set(self.desperate_for_redemption_available_vow_keys()):
            return False
        used = list(getattr(self, "desperate_for_redemption_used_vows", []) or [])
        used.append(key)
        unique_used = sorted({self._normalize_desperate_for_redemption_vow_key(v) for v in used if v})
        self.desperate_for_redemption_used_vows = [v for v in unique_used if v]

        self.desperate_for_redemption_active_vow = key
        self.desperate_for_redemption_active_battle_round = int(battle_round or 0)
        self.desperate_for_redemption_active_player_id = str(player_id or "")
        return True

    def _has_pending_desperate_for_redemption_request(
        self,
        *,
        game=None,
        player_id: str = "",
        battle_round: int = 0,
    ) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for pending in list(queue.list() or []):
            if str(getattr(pending, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(pending, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._DESPERATE_FOR_REDEMPTION_ABILITY_KEY:
                continue
            if player_id and str(getattr(pending, "player_id", "") or "") != str(player_id):
                continue
            if battle_round:
                try:
                    pending_round = int(ctx.get("battle_round", 0) or 0)
                except (TypeError, ValueError):
                    pending_round = 0
                if pending_round and pending_round != int(battle_round):
                    continue
            return True
        return False

    def queue_desperate_for_redemption_selection_request(
        self,
        *,
        battle_round: int = 0,
        game=None,
        player=None,
    ):
        if not self.is_penitent_host():
            return None
        army = self.army
        if army is None:
            return None
        army_player = getattr(army, "player", None)
        if player is None:
            player = army_player
        if player is None:
            return None
        if army_player is not None and player is not army_player:
            return None
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None or not bool(getattr(game_obj, "is_authoritative", True)):
            return None
        if int(battle_round or 0) <= 0:
            battle_round = int(getattr(game_obj, "turn", 0) or 0)
        if int(battle_round or 0) <= 0:
            return None
        available_keys = self.desperate_for_redemption_available_vow_keys()
        if not available_keys:
            return None

        player_id = str(getattr(player, "id", "") or "")
        if self._has_pending_desperate_for_redemption_request(
            game=game_obj,
            player_id=player_id,
            battle_round=int(battle_round or 0),
        ):
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = [
            DecisionOption.create(
                "None",
                payload={
                    "action": "skip",
                    "choice_key": "",
                    "choice_name": "None",
                },
            )
        ]
        for key in list(available_keys):
            label = self.desperate_for_redemption_vow_label(key)
            options.append(
                DecisionOption.create(
                    label,
                    payload={
                        "choice_key": key,
                        "choice_name": label,
                    },
                )
            )
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Desperate for Redemption: select one Vow of Atonement for this battle round.",
            player_id=player_id,
            options=options,
            context={
                "ability": self._DESPERATE_FOR_REDEMPTION_ABILITY_KEY,
                "ability_name": self.DESPERATE_FOR_REDEMPTION_NAME,
                "army_id": str(maybe_entity_id(army) or ""),
                "battle_round": int(battle_round or 0),
                "allowed_choice_keys": list(available_keys),
                "optional": True,
            },
        )
        request_fn = getattr(game_obj, "request_decision", None)
        if callable(request_fn):
            request_fn(request)
        return request

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self.is_penitent_host():
            return
        game_obj = self._resolve_game_context(game=game)
        self.clear_desperate_for_redemption_active_vow()
        self.queue_desperate_for_redemption_selection_request(
            battle_round=int(battle_round or 0),
            game=game_obj,
        )

    def _iter_righteous_purpose_candidate_units(self) -> list:
        if not self.is_champions_of_faith():
            return []
        army = self.army
        if army is None:
            return []
        unique_by_id: dict[str, object] = {}
        for unit in list(getattr(army, "units", []) or []):
            root = self._unit_root(unit)
            unit_id = self._unit_id(root)
            if not unit_id or unit_id in unique_by_id:
                continue
            if not self.unit_is_adepta_sororitas(root):
                continue
            if not self._unit_is_on_battlefield_or_embarked(root):
                continue
            unique_by_id[unit_id] = root
        return [unique_by_id[k] for k in sorted(unique_by_id.keys())]

    def _has_pending_righteous_purpose_request(self, *, game=None, player_id: str = "") -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for pending in list(queue.list() or []):
            if str(getattr(pending, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(pending, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._RIGHTEOUS_PURPOSE_ABILITY_KEY:
                continue
            if player_id and str(getattr(pending, "player_id", "") or "") != str(player_id):
                continue
            return True
        return False

    def clear_righteous_purpose_selection(self) -> None:
        army = self.army
        if army is None:
            return
        for unit in self._iter_righteous_purpose_candidate_units():
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if self._RIGHTEOUS_PURPOSE_ACTIVE_KEY in sr:
                sr.pop(self._RIGHTEOUS_PURPOSE_ACTIVE_KEY, None)
                sr.pop(self._RIGHTEOUS_PURPOSE_SOURCE_KEY, None)
                unit.special_rules = sr

    def queue_righteous_purpose_selection_request(self, *, game=None, player=None):
        if not self.is_champions_of_faith():
            return None
        army = self.army
        if army is None:
            return None
        army_player = getattr(army, "player", None)
        if player is None:
            player = army_player
        if player is None:
            return None
        if army_player is not None and player is not army_player:
            return None
        if game is None:
            game = getattr(player, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return None
        player_id = str(getattr(player, "id", "") or "")
        if self._has_pending_righteous_purpose_request(game=game, player_id=player_id):
            return None

        candidates = self._iter_righteous_purpose_candidate_units()
        if not candidates:
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = [
            DecisionOption.create(
                "None",
                payload={"action": "skip", "selected_unit_ids": [], "selection_kind": "none"},
            )
        ]
        max_count = min(3, len(candidates))
        for count in range(1, max_count + 1):
            for combo in combinations(candidates, count):
                unit_ids = [self._unit_id(unit) for unit in combo]
                if any(not unit_id for unit_id in unit_ids):
                    continue
                label = " + ".join(str(getattr(unit, "name", "Unit") or "Unit") for unit in combo)
                options.append(
                    DecisionOption.create(
                        label,
                        payload={
                            "selected_unit_ids": list(unit_ids),
                            "selection_kind": f"{count}_units",
                        },
                    )
                )

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Righteous Purpose: select up to 3 friendly ADEPTA SORORITAS units to become Righteous until your next Command phase.",
            player_id=player_id,
            options=options,
            context={
                "ability": self._RIGHTEOUS_PURPOSE_ABILITY_KEY,
                "ability_name": self.RIGHTEOUS_PURPOSE_NAME,
                "army_id": str(maybe_entity_id(army) or ""),
                "candidate_unit_ids": [self._unit_id(unit) for unit in candidates],
                "max_selections": 3,
                "optional": True,
            },
        )
        request_fn = getattr(game, "request_decision", None)
        if callable(request_fn):
            request_fn(request)
        return request

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if not self.is_champions_of_faith():
            return
        self.clear_righteous_purpose_selection()
        self.queue_righteous_purpose_selection_request(game=game, player=player)

    def apply_righteous_purpose_selection(
        self,
        selected_unit_ids: list[str] | tuple[str, ...] | None,
        *,
        game=None,
        player=None,
    ) -> list[str]:
        if not self.is_champions_of_faith():
            return []
        selected_set = {
            str(unit_id or "").strip()
            for unit_id in list(selected_unit_ids or [])
            if str(unit_id or "").strip()
        }
        if len(selected_set) > 3:
            selected_set = set(sorted(selected_set)[:3])
        valid_by_id = {self._unit_id(unit): unit for unit in self._iter_righteous_purpose_candidate_units()}
        selected_ids = [unit_id for unit_id in sorted(selected_set) if unit_id in valid_by_id]

        self.clear_righteous_purpose_selection()
        for unit_id in selected_ids:
            unit = valid_by_id.get(unit_id)
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr[self._RIGHTEOUS_PURPOSE_ACTIVE_KEY] = True
            sr[self._RIGHTEOUS_PURPOSE_SOURCE_KEY] = self.RIGHTEOUS_PURPOSE_NAME
            unit.special_rules = sr
        return selected_ids

    def righteous_purpose_is_righteous(self, unit) -> bool:
        if not self.is_champions_of_faith():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        return bool(sr.get(self._RIGHTEOUS_PURPOSE_ACTIVE_KEY))

    def righteous_purpose_move_bonus(self, unit) -> tuple[int, str]:
        if not self.is_champions_of_faith():
            return 0, ""
        if unit is None:
            return 0, ""
        if not self.unit_is_adepta_sororitas(unit):
            return 0, ""
        if not self.righteous_purpose_is_righteous(unit):
            return 0, ""
        return 1, self.RIGHTEOUS_PURPOSE_NAME

    def righteous_purpose_leadership_bonus(self, unit) -> tuple[int, str]:
        if not self.is_champions_of_faith():
            return 0, ""
        if unit is None:
            return 0, ""
        if not self.unit_is_adepta_sororitas(unit):
            return 0, ""
        if not self.righteous_purpose_is_righteous(unit):
            return 0, ""
        # Leadership improves by 1, represented as -1 to the numeric characteristic.
        return -1, self.RIGHTEOUS_PURPOSE_NAME

    def righteous_purpose_skill_bonus(self, attacker_model, *, unit=None, weapon_profile=None) -> tuple[int, str]:
        if not self.is_champions_of_faith():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        if unit is None:
            unit = getattr(attacker_model, "parent_unit", None)
        if unit is None:
            return 0, ""
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        if not self.model_is_adepta_sororitas(attacker_model, root):
            return 0, ""
        if not self.righteous_purpose_is_righteous(root):
            return 0, ""
        model_unit = getattr(attacker_model, "parent_unit", None)
        if not self._unit_name_matches_any(model_unit or root, self._RIGHTEOUS_PURPOSE_SKILL_UNIT_NAMES):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is None:
                return 0, ""
            is_melee_fn = getattr(parent, "is_melee", None)
            is_ranged_fn = getattr(parent, "is_ranged", None)
            is_melee = bool(is_melee_fn()) if callable(is_melee_fn) else False
            is_ranged = bool(is_ranged_fn()) if callable(is_ranged_fn) else False
            if not (is_melee or is_ranged):
                return 0, ""
        return 1, self.RIGHTEOUS_PURPOSE_NAME

    def righteous_purpose_sacresants_objective_control_bonus(self, model, unit) -> tuple[int, str]:
        if not self.is_champions_of_faith():
            return 0, ""
        if model is None or unit is None:
            return 0, ""
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        if not self.unit_is_adepta_sororitas(root):
            return 0, ""
        if self._unit_is_battle_shocked(root):
            return 0, ""
        model_unit = getattr(model, "parent_unit", None)
        if not self._unit_name_matches_any(model_unit, self._RIGHTEOUS_PURPOSE_SACRESANTS_UNIT_NAMES):
            return 0, ""
        return 1, self.RIGHTEOUS_PURPOSE_NAME

    def unit_is_penitent(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return self._unit_has_keyword(root, "PENITENT")

    def model_is_penitent(self, model, unit) -> bool:
        if model is not None and hasattr(model, "has_any_keyword"):
            if bool(model.has_any_keyword("PENITENT")):
                return True
        return self.unit_is_penitent(unit)

    def _unit_made_charge_move_this_turn(self, unit, *, game=None) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "charged_this_round", False)):
            return False
        charge_suppressed_fn = getattr(root, "charge_bonus_suppressed", None)
        if callable(charge_suppressed_fn) and bool(charge_suppressed_fn(game=game)):
            return False
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None:
            return True

        charged_turn = int(getattr(round_state, "charged_turn", 0) or 0)
        if charged_turn and charged_turn != int(getattr(game_obj, "turn", 0) or 0):
            return False
        charged_owner = str(getattr(round_state, "charged_turn_owner", "") or "")
        current_player = getattr(game_obj, "get_current_player", lambda: None)()
        current_owner = str(getattr(current_player, "id", "") or "")
        if charged_owner and current_owner and charged_owner != current_owner:
            return False
        return True

    def desperate_for_redemption_move_bonus(self, model, unit) -> tuple[int, str]:
        if not self.is_penitent_host():
            return 0, ""
        if model is None or unit is None:
            return 0, ""
        active = self.desperate_for_redemption_active_vow_key()
        if active != self._PATH_OF_THE_PENITENT_KEY:
            return 0, ""
        if not self.model_is_penitent(model, unit):
            return 0, ""
        return 3, f"{self.DESPERATE_FOR_REDEMPTION_NAME} (The Path of the Penitent)"

    def desperate_for_redemption_melee_attacks_bonus(self, attacker_model, *, unit=None, weapon_profile=None) -> tuple[int, str]:
        if not self.is_penitent_host():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        active = self.desperate_for_redemption_active_vow_key()
        if active != self._ABSOLUTION_IN_BATTLE_KEY:
            return 0, ""
        if unit is None:
            unit = getattr(attacker_model, "parent_unit", None)
        if unit is None or not self.model_is_penitent(attacker_model, unit):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_melee_fn = getattr(parent, "is_melee", None) if parent is not None else None
            if not callable(is_melee_fn) or not bool(is_melee_fn()):
                return 0, ""
        if not self._unit_made_charge_move_this_turn(unit):
            return 0, ""
        return 1, f"{self.DESPERATE_FOR_REDEMPTION_NAME} (Absolution in Battle)"

    def desperate_for_redemption_melee_strength_bonus(self, attacker_model, *, unit=None, weapon_profile=None) -> tuple[int, str]:
        if not self.is_penitent_host():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        active = self.desperate_for_redemption_active_vow_key()
        if active != self._ABSOLUTION_IN_BATTLE_KEY:
            return 0, ""
        if unit is None:
            unit = getattr(attacker_model, "parent_unit", None)
        if unit is None or not self.model_is_penitent(attacker_model, unit):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_melee_fn = getattr(parent, "is_melee", None) if parent is not None else None
            if not callable(is_melee_fn) or not bool(is_melee_fn()):
                return 0, ""
        if not self._unit_made_charge_move_this_turn(unit):
            return 0, ""
        return 1, f"{self.DESPERATE_FOR_REDEMPTION_NAME} (Absolution in Battle)"

    def desperate_for_redemption_melee_fight_on_death_rule(self, unit, *, model=None):
        if not self.is_penitent_host():
            return None
        if model is None or unit is None:
            return None
        active = self.desperate_for_redemption_active_vow_key()
        if active != self._DEATH_BEFORE_DISGRACE_KEY:
            return None
        if not self.model_is_penitent(model, unit):
            return None
        return {
            "threshold": 2,
            "source": f"{self.DESPERATE_FOR_REDEMPTION_NAME} (Death Before Disgrace)",
        }

    def unit_is_adepta_sororitas(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "ADEPTA SORORITAS"):
            return True
        return self._army_faction_matches(self.faction_id)

    def model_is_adepta_sororitas(self, model, unit) -> bool:
        if model is not None and hasattr(model, "has_any_keyword"):
            if bool(model.has_any_keyword("ADEPTA SORORITAS")):
                return True
        return self.unit_is_adepta_sororitas(unit)

    def sacred_rites_max_acts_of_faith_per_phase(self, unit) -> int:
        """
        Army of Faith: ADEPTA SORORITAS units can perform up to two Acts of Faith per phase.
        """
        if not self.is_army_of_faith():
            return 1
        if unit is None:
            return 1
        if not self.unit_is_adepta_sororitas(unit):
            return 1
        return 2

    def fervent_purgation_assault_applies(self, unit, weapon_profile=None) -> bool:
        if not self.is_bringers_of_flame():
            return False
        if unit is None:
            return False
        if not self.unit_is_adepta_sororitas(unit):
            return False
        if weapon_profile is None:
            return True
        parent = getattr(weapon_profile, "parent_wargear", None)
        if parent is None:
            return False
        is_ranged_fn = getattr(parent, "is_ranged", None)
        if not callable(is_ranged_fn):
            return False
        return bool(is_ranged_fn())

    def fervent_purgation_strength_bonus(
        self,
        attacker_model,
        target_unit=None,
        *,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[int, str]:
        if not self.is_bringers_of_flame():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None:
            return 0, ""
        if not self.fervent_purgation_assault_applies(attacker_unit, weapon_profile):
            return 0, ""
        try:
            distance = float((attack_instance or {}).get("distance_to_target", 0.0) or 0.0)
        except Exception:
            distance = 0.0
        if distance <= 0.0 and target_unit is not None:
            game_map = None
            try:
                game_map = getattr(getattr(attacker_unit.get_parent_army(), "player", None), "game", None).map
            except Exception:
                game_map = None
            if game_map is not None:
                try:
                    distance = float(game_map.get_distance_between_units(attacker_unit, target_unit))
                except Exception:
                    distance = 0.0
        if distance <= 0.0 or distance > 6.0 + 1e-6:
            return 0, ""
        return 1, self.FERVENT_PURGATION_NAME

    def blood_of_martyrs_hit_bonus(self, model, unit) -> tuple[int, str]:
        """
        Hallowed Martyrs: +1 to Hit while the model's unit is below Starting Strength.
        """
        if not self.is_hallowed_martyrs():
            return 0, ""
        if unit is None or not self.model_is_adepta_sororitas(model, unit):
            return 0, ""
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if hasattr(root, "is_below_starting_strength") and root.is_below_starting_strength():
            return 1, f"{self.THE_BLOOD_OF_MARTYRS_NAME} (+1 to hit below Starting Strength)"
        return 0, ""

    def blood_of_martyrs_wound_bonus(self, model, unit) -> tuple[int, str]:
        """
        Hallowed Martyrs: +1 to Wound while the model's unit is Below Half-strength.
        """
        if not self.is_hallowed_martyrs():
            return 0, ""
        if unit is None or not self.model_is_adepta_sororitas(model, unit):
            return 0, ""
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if hasattr(root, "is_below_half_strength") and root.is_below_half_strength():
            return 1, f"{self.THE_BLOOD_OF_MARTYRS_NAME} (+1 to wound below Half-strength)"
        return 0, ""
