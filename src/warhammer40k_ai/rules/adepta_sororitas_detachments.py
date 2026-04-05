from __future__ import annotations

from itertools import combinations

from ..utility.entity_ids import maybe_entity_id
from ..utility.aura_utils import distance_between_models_bases_3d, unit_within_range_of_unit
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
    _VERSE_OF_HOLY_PIETY_ABILITY_KEY = "verse_of_holy_piety_vow"
    _PATH_OF_THE_PENITENT_KEY = "path_of_the_penitent"
    _ABSOLUTION_IN_BATTLE_KEY = "absolution_in_battle"
    _DEATH_BEFORE_DISGRACE_KEY = "death_before_disgrace"
    _DIVINE_ASPECT_ABILITY_KEY = "divine_aspect_target"
    _DIVINE_ASPECT_PENDING_KEY = "enhancement_divine_aspect_pending"
    _DIVINE_ASPECT_SOURCE_NAME = "Divine Aspect"
    _VERSE_OF_HOLY_PIETY_SOURCE_NAME = "Verse of Holy Piety"
    _DESPERATE_FOR_REDEMPTION_VOWS = (
        (_PATH_OF_THE_PENITENT_KEY, "The Path of the Penitent"),
        (_ABSOLUTION_IN_BATTLE_KEY, "Absolution in Battle"),
        (_DEATH_BEFORE_DISGRACE_KEY, "Death Before Disgrace"),
    )
    _LIGHT_OF_THE_EMPEROR_ACTIVE_KEY = "army_of_faith_light_of_the_emperor_active"
    _LIGHT_OF_THE_EMPEROR_TURN_KEY = "army_of_faith_light_of_the_emperor_turn"
    _LIGHT_OF_THE_EMPEROR_OWNER_KEY = "army_of_faith_light_of_the_emperor_turn_owner"
    _LIGHT_OF_THE_EMPEROR_SOURCE_KEY = "army_of_faith_light_of_the_emperor_source"
    _LIGHT_OF_THE_EMPEROR_JUMP_PACK_AURA_KEY = "army_of_faith_light_of_the_emperor_jump_pack_aura"

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

    @staticmethod
    def _member_sort_key(member: object) -> str:
        entity_id = str(maybe_entity_id(member) or "").strip()
        if entity_id:
            return entity_id
        return str(getattr(member, "name", "") or "").strip().lower()

    def _verse_of_holy_piety_source_state(self, unit) -> tuple[bool, str]:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return False, ""
        if not bool(sr.get("enhancement_verse_of_holy_piety", False)):
            return False, ""
        source_name = str(
            sr.get("enhancement_verse_of_holy_piety_source", "") or self._VERSE_OF_HOLY_PIETY_SOURCE_NAME
        ).strip()
        if not source_name:
            source_name = self._VERSE_OF_HOLY_PIETY_SOURCE_NAME
        return True, source_name

    def _verse_of_holy_piety_bearer_model(self, unit):
        if unit is None:
            return None
        sr = getattr(unit, "special_rules", None)
        bearer_id = ""
        if isinstance(sr, dict):
            bearer_id = str(
                sr.get("enhancement_verse_of_holy_piety_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
        for model in list(getattr(unit, "models", []) or []):
            if model is None:
                continue
            if bearer_id and str(maybe_entity_id(model) or "") != bearer_id:
                continue
            if self._model_is_alive(model):
                return model
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        bearer = get_bearer() if callable(get_bearer) else None
        if bearer is None:
            return None
        if bearer_id and str(maybe_entity_id(bearer) or "") != bearer_id:
            return None
        if not self._model_is_alive(bearer):
            return None
        return bearer

    def _iter_verse_of_holy_piety_sources(self) -> list[dict]:
        if not self.is_penitent_host():
            return []
        army = self.army
        if army is None:
            return []
        out: list[dict] = []
        seen_source_ids: set[str] = set()
        for source_unit in list(getattr(army, "units", []) or []):
            if source_unit is None:
                continue
            source_id = str(maybe_entity_id(source_unit) or "").strip()
            if not source_id or source_id in seen_source_ids:
                continue
            is_source, source_name = self._verse_of_holy_piety_source_state(source_unit)
            if not is_source:
                continue
            root = self._unit_root(source_unit)
            if root is None:
                continue
            if not self._unit_is_alive(root):
                continue
            if not self._unit_is_deployed_on_battlefield(root):
                continue
            if bool(getattr(root, "is_embarked", False)):
                continue
            bearer_model = self._verse_of_holy_piety_bearer_model(source_unit)
            if bearer_model is None:
                continue
            source_sr = getattr(source_unit, "special_rules", None)
            if not isinstance(source_sr, dict):
                source_sr = {}
            used = bool(source_sr.get("enhancement_verse_of_holy_piety_used", False))
            out.append(
                {
                    "source_unit": source_unit,
                    "source_root": root,
                    "source_unit_id": source_id,
                    "source_name": source_name,
                    "source_used": bool(used),
                    "bearer_model_id": str(maybe_entity_id(bearer_model) or ""),
                }
            )
            seen_source_ids.add(source_id)
        return sorted(out, key=lambda item: str(item.get("source_unit_id", "") or ""))

    def _has_pending_verse_of_holy_piety_request(
        self,
        *,
        game=None,
        player_id: str = "",
        source_unit_id: str = "",
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
            if player_id and str(getattr(pending, "player_id", "") or "") != str(player_id):
                continue
            ctx = dict(getattr(pending, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._VERSE_OF_HOLY_PIETY_ABILITY_KEY:
                continue
            if source_unit_id and str(ctx.get("source_unit_id", "") or "") != str(source_unit_id):
                continue
            if int(battle_round or 0) > 0:
                try:
                    pending_round = int(ctx.get("battle_round", 0) or 0)
                except (TypeError, ValueError):
                    pending_round = 0
                if pending_round and pending_round != int(battle_round):
                    continue
            return True
        return False

    def queue_verse_of_holy_piety_selection_requests(
        self,
        *,
        battle_round: int = 0,
        game=None,
        player=None,
    ) -> list:
        if not self.is_penitent_host():
            return []
        army = self.army
        if army is None:
            return []
        army_player = getattr(army, "player", None)
        if player is None:
            player = army_player
        if player is None or army_player is None or player is not army_player:
            return []
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None or not bool(getattr(game_obj, "is_authoritative", True)):
            return []
        if int(battle_round or 0) <= 0:
            battle_round = int(getattr(game_obj, "turn", 0) or 0)
        if int(battle_round or 0) <= 0:
            return []

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        player_id = str(getattr(player, "id", "") or "")
        request_fn = getattr(game_obj, "request_decision", None)
        if not callable(request_fn):
            return []

        vow_keys = [key for key, _label in self._DESPERATE_FOR_REDEMPTION_VOWS]
        queued: list = []
        for source in self._iter_verse_of_holy_piety_sources():
            source_unit = source.get("source_unit")
            source_unit_id = str(source.get("source_unit_id", "") or "")
            if source_unit is None or not source_unit_id:
                continue
            if bool(source.get("source_used", False)):
                continue
            if self._has_pending_verse_of_holy_piety_request(
                game=game_obj,
                player_id=player_id,
                source_unit_id=source_unit_id,
                battle_round=int(battle_round or 0),
            ):
                continue

            options = [
                DecisionOption.create(
                    "None",
                    payload={
                        "action": "skip",
                        "choice_key": "",
                        "choice_name": "None",
                        "source_unit_id": source_unit_id,
                    },
                )
            ]
            for key in list(vow_keys):
                label = self.desperate_for_redemption_vow_label(key)
                options.append(
                    DecisionOption.create(
                        label,
                        payload={
                            "choice_key": key,
                            "choice_name": label,
                            "source_unit_id": source_unit_id,
                        },
                    )
                )

            source_name = str(source.get("source_name", "") or self._VERSE_OF_HOLY_PIETY_SOURCE_NAME).strip()
            if not source_name:
                source_name = self._VERSE_OF_HOLY_PIETY_SOURCE_NAME
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                (
                    f"{source_name}: once per battle, select one Vow of Atonement to be active for "
                    f"{getattr(source_unit, 'name', 'the bearer unit')} this battle round (or select None)."
                ),
                player_id=player_id,
                options=options,
                context={
                    "ability": self._VERSE_OF_HOLY_PIETY_ABILITY_KEY,
                    "ability_name": source_name,
                    "army_id": str(maybe_entity_id(army) or ""),
                    "source_unit_id": source_unit_id,
                    "source_model_id": str(source.get("bearer_model_id", "") or ""),
                    "battle_round": int(battle_round or 0),
                    "allowed_choice_keys": list(vow_keys),
                    "optional": True,
                    "once_per_battle": True,
                },
            )
            request_fn(request)
            queued.append(request)
        return queued

    def select_verse_of_holy_piety_vow(
        self,
        source_unit,
        choice_key: str,
        *,
        battle_round: int = 0,
        player_id: str = "",
    ) -> bool:
        if not self.is_penitent_host():
            return False
        if source_unit is None:
            return False
        source_army = getattr(source_unit, "get_parent_army", lambda: None)()
        if source_army is not self.army:
            return False
        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict):
            return False
        if not bool(source_sr.get("enhancement_verse_of_holy_piety", False)):
            return False
        if bool(source_sr.get("enhancement_verse_of_holy_piety_used", False)):
            return False
        if self._verse_of_holy_piety_bearer_model(source_unit) is None:
            return False

        key = self._normalize_desperate_for_redemption_vow_key(choice_key)
        if not key:
            return True

        source_sr = dict(source_sr)
        source_sr["enhancement_verse_of_holy_piety_used"] = True
        source_sr["enhancement_verse_of_holy_piety_active_vow"] = key
        source_sr["enhancement_verse_of_holy_piety_active_battle_round"] = int(battle_round or 0)
        source_sr["enhancement_verse_of_holy_piety_active_player_id"] = str(player_id or "")
        source_unit.special_rules = source_sr
        return True

    def clear_verse_of_holy_piety_active_vows(self) -> None:
        army = self.army
        if army is None:
            return
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if (
                "enhancement_verse_of_holy_piety_active_vow" not in sr
                and "enhancement_verse_of_holy_piety_active_battle_round" not in sr
                and "enhancement_verse_of_holy_piety_active_player_id" not in sr
            ):
                continue
            sr = dict(sr)
            sr.pop("enhancement_verse_of_holy_piety_active_vow", None)
            sr.pop("enhancement_verse_of_holy_piety_active_battle_round", None)
            sr.pop("enhancement_verse_of_holy_piety_active_player_id", None)
            unit.special_rules = sr

    def verse_of_holy_piety_active_vow_key(self, unit, *, game=None, battle_round=None) -> str:
        if not self.is_penitent_host():
            return ""
        root = self._unit_root(unit)
        if root is None:
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
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = []
        if not members:
            members = [root]
        members = sorted(
            [member for member in list(members or []) if member is not None],
            key=self._member_sort_key,
        )
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not (isinstance(sr, dict) and bool(sr.get("enhancement_verse_of_holy_piety", False))):
                continue
            key = self._normalize_desperate_for_redemption_vow_key(
                str(sr.get("enhancement_verse_of_holy_piety_active_vow", "") or "")
            )
            if not key:
                continue
            try:
                selected_round = int(sr.get("enhancement_verse_of_holy_piety_active_battle_round", 0) or 0)
            except (TypeError, ValueError):
                selected_round = 0
            if selected_round and battle_round_int and selected_round != battle_round_int:
                continue
            return key
        return ""

    def _desperate_for_redemption_vow_active_for_unit(self, vow_key: str, *, unit, model=None, game=None) -> bool:
        normalized = self._normalize_desperate_for_redemption_vow_key(vow_key)
        if not normalized:
            return False
        active_army_vow = self.desperate_for_redemption_active_vow_key(game=game)
        if active_army_vow == normalized:
            return model is None or self.model_is_penitent(model, unit)
        verse_vow = self.verse_of_holy_piety_active_vow_key(unit, game=game)
        if verse_vow == normalized:
            return True
        return False

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self.is_penitent_host():
            return
        game_obj = self._resolve_game_context(game=game)
        self.clear_desperate_for_redemption_active_vow()
        self.clear_verse_of_holy_piety_active_vows()
        self.queue_desperate_for_redemption_selection_request(
            battle_round=int(battle_round or 0),
            game=game_obj,
        )
        self.queue_verse_of_holy_piety_selection_requests(
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

    @staticmethod
    def _model_is_alive(model) -> bool:
        if model is None:
            return False
        alive_val = getattr(model, "is_alive", None)
        if callable(alive_val):
            return bool(alive_val())
        return bool(alive_val)

    def _divine_aspect_source_state(self, unit) -> tuple[bool, float, str]:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return False, 0.0, ""
        if not bool(sr.get("enhancement_divine_aspect", False)):
            return False, 0.0, ""
        try:
            range_inches = float(sr.get("enhancement_divine_aspect_range", 12.0) or 12.0)
        except Exception:
            range_inches = 12.0
        source_name = str(sr.get("enhancement_divine_aspect_source", "") or self._DIVINE_ASPECT_SOURCE_NAME).strip()
        if not source_name:
            source_name = self._DIVINE_ASPECT_SOURCE_NAME
        return True, float(max(0.0, range_inches)), source_name

    def _divine_aspect_bearer_model(self, unit):
        if unit is None:
            return None
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        bearer = get_bearer() if callable(get_bearer) else None
        if bearer is None:
            try:
                models = list(unit.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(unit, "models", []) or [])
            for model in models:
                if self._model_is_alive(model):
                    bearer = model
                    break
        if bearer is None or not self._model_is_alive(bearer):
            return None
        return bearer

    def _iter_divine_aspect_sources(self) -> list[dict]:
        if not self.is_army_of_faith():
            return []
        army = self.army
        if army is None:
            return []
        out: list[dict] = []
        seen_ids: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            unit_id = str(maybe_entity_id(unit) or "")
            if not unit_id or unit_id in seen_ids:
                continue
            root = self._unit_root(unit)
            if root is None:
                continue
            if not self._unit_is_alive(root):
                continue
            if not self._unit_is_deployed_on_battlefield(root):
                continue
            if bool(getattr(root, "is_embarked", False)):
                continue
            if not self.unit_is_adepta_sororitas(root):
                continue
            is_source, range_inches, source_name = self._divine_aspect_source_state(unit)
            if not is_source:
                continue
            bearer_model = self._divine_aspect_bearer_model(unit)
            if bearer_model is None:
                continue
            seen_ids.add(unit_id)
            out.append(
                {
                    "source_unit": unit,
                    "source_root": root,
                    "source_unit_id": unit_id,
                    "source_name": source_name,
                    "range_inches": float(max(0.0, range_inches)),
                    "bearer_model": bearer_model,
                    "bearer_model_id": str(maybe_entity_id(bearer_model) or ""),
                }
            )
        return sorted(
            out,
            key=lambda item: (
                str(item.get("source_unit_id", "") or ""),
                str(item.get("bearer_model_id", "") or ""),
            ),
        )

    def _divine_aspect_enemy_candidates(self, *, game=None, player=None, bearer_model=None, range_inches: float = 12.0) -> list:
        if game is None or player is None or bearer_model is None:
            return []
        try:
            max_range = float(range_inches)
        except Exception:
            max_range = 0.0
        if max_range <= 0.0:
            return []
        out: dict[str, object] = {}
        for enemy_player in list(getattr(game, "players", []) or []):
            if enemy_player is None or enemy_player is player:
                continue
            enemy_army = getattr(enemy_player, "army", None)
            if enemy_army is None:
                getter = getattr(enemy_player, "get_army", None)
                if callable(getter):
                    enemy_army = getter()
            if enemy_army is None:
                continue
            for enemy_unit in list(getattr(enemy_army, "units", []) or []):
                enemy_root = self._unit_root(enemy_unit)
                enemy_id = self._unit_id(enemy_root)
                if enemy_root is None or not enemy_id or enemy_id in out:
                    continue
                if not self._unit_is_alive(enemy_root):
                    continue
                if not self._unit_is_deployed_on_battlefield(enemy_root):
                    continue
                if bool(getattr(enemy_root, "is_embarked", False)):
                    continue
                try:
                    enemy_models = list(enemy_root.get_attached_unit_models() or [])
                except Exception:
                    enemy_models = list(getattr(enemy_root, "models", []) or [])
                in_range = False
                for enemy_model in enemy_models:
                    if not self._model_is_alive(enemy_model):
                        continue
                    try:
                        distance = float(distance_between_models_bases_3d(bearer_model, enemy_model))
                    except Exception:
                        continue
                    if distance <= max_range + 1e-6:
                        in_range = True
                        break
                if in_range:
                    out[enemy_id] = enemy_root
        return [out[uid] for uid in sorted(out.keys())]

    def _has_pending_divine_aspect_request(self, *, game=None, player_id: str = "", source_unit_id: str = "", turn: int = 0) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for pending in list(queue.list() or []):
            if str(getattr(pending, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            if player_id and str(getattr(pending, "player_id", "") or "") != str(player_id):
                continue
            pending_ctx = dict(getattr(pending, "context", {}) or {})
            if str(pending_ctx.get("ability", "") or "") != self._DIVINE_ASPECT_ABILITY_KEY:
                continue
            if source_unit_id and str(pending_ctx.get("source_unit_id", "") or "") != str(source_unit_id):
                continue
            if int(turn or 0) > 0:
                try:
                    pending_turn = int(pending_ctx.get("turn", 0) or 0)
                except (TypeError, ValueError):
                    pending_turn = 0
                if pending_turn and pending_turn != int(turn):
                    continue
            return True
        return False

    def queue_divine_aspect_selection_requests(self, *, game=None, player=None) -> list:
        if not self.is_army_of_faith():
            return []
        army = self.army
        if army is None:
            return []
        owner = getattr(army, "player", None)
        if player is None:
            player = owner
        if player is None or owner is None or player is not owner:
            return []
        if game is None:
            game = getattr(player, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return []
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "MOVEMENT_PHASE":
            return []
        if player is not getattr(game, "get_current_player", lambda: None)():
            return []
        request_fn = getattr(game, "request_decision", None)
        if not callable(request_fn):
            return []

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        turn = int(getattr(game, "turn", 0) or 0)
        player_id = str(getattr(player, "id", "") or "")
        army_id = str(maybe_entity_id(army) or "")
        queued: list = []
        for source in self._iter_divine_aspect_sources():
            source_unit = source.get("source_unit")
            source_unit_id = str(source.get("source_unit_id", "") or "")
            bearer_model = source.get("bearer_model")
            if source_unit is None or not source_unit_id or bearer_model is None:
                continue
            if self._has_pending_divine_aspect_request(
                game=game,
                player_id=player_id,
                source_unit_id=source_unit_id,
                turn=turn,
            ):
                continue
            candidates = self._divine_aspect_enemy_candidates(
                game=game,
                player=player,
                bearer_model=bearer_model,
                range_inches=float(source.get("range_inches", 12.0) or 12.0),
            )
            if not candidates:
                continue
            options = [
                DecisionOption.create(
                    "None",
                    payload={
                        "action": "skip",
                        "target_unit_id": "",
                        "source_unit_id": source_unit_id,
                    },
                )
            ]
            candidate_ids: list[str] = []
            for target in candidates:
                target_id = self._unit_id(target)
                if not target_id:
                    continue
                candidate_ids.append(target_id)
                options.append(
                    DecisionOption.create(
                        str(getattr(target, "name", "Enemy Unit") or "Enemy Unit"),
                        payload={
                            "target_unit_id": target_id,
                            "source_unit_id": source_unit_id,
                        },
                    )
                )
            if not candidate_ids:
                continue
            ability_name = str(source.get("source_name", "") or self._DIVINE_ASPECT_SOURCE_NAME).strip()
            if not ability_name:
                ability_name = self._DIVINE_ASPECT_SOURCE_NAME
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                (
                    f"{ability_name}: select one enemy unit within "
                    f"{int(float(source.get('range_inches', 12.0) or 12.0))}\" of the bearer to take a Battle-shock test."
                ),
                player_id=player_id,
                options=options,
                context={
                    "ability": self._DIVINE_ASPECT_ABILITY_KEY,
                    "ability_name": ability_name,
                    "army_id": army_id,
                    "phase": "Movement phase",
                    "turn": int(turn),
                    "optional": True,
                    "source_unit_id": source_unit_id,
                    "source_model_id": str(source.get("bearer_model_id", "") or ""),
                    "range_inches": float(source.get("range_inches", 12.0) or 12.0),
                    "candidate_unit_ids": list(candidate_ids),
                },
            )
            request_fn(request)
            queued.append(request)
        return queued

    def apply_divine_aspect_target_selection(
        self,
        source_unit,
        target_unit,
        *,
        game=None,
        player=None,
        ability_name: str = "",
    ) -> dict:
        if not self.is_army_of_faith():
            return {"ok": False}
        if source_unit is None:
            return {"ok": False}
        army = self.army
        if army is None:
            return {"ok": False}
        owner = getattr(army, "player", None)
        if player is None:
            player = owner
        if player is None or owner is None or player is not owner:
            return {"ok": False}
        source_army = getattr(source_unit, "get_parent_army", lambda: None)()
        if source_army is not army:
            return {"ok": False}
        is_source, range_inches, resolved_name = self._divine_aspect_source_state(source_unit)
        if not is_source:
            return {"ok": False}
        bearer_model = self._divine_aspect_bearer_model(source_unit)
        if bearer_model is None:
            return {"ok": False}

        source_root = self._unit_root(source_unit)
        source_unit_id = str(maybe_entity_id(source_unit) or "")
        if not source_unit_id and source_root is not None:
            source_unit_id = str(maybe_entity_id(source_root) or "")

        if target_unit is None:
            return {
                "ok": True,
                "source_unit_id": source_unit_id,
                "target_unit_id": "",
                "triggered": False,
            }

        target_root = self._unit_root(target_unit)
        if target_root is None:
            return {"ok": False}
        target_unit_id = self._unit_id(target_root)
        if not target_unit_id:
            return {"ok": False}
        if source_root is not None and target_root.get_parent_army() is source_root.get_parent_army():
            return {"ok": False}
        try:
            target_models = list(target_root.get_attached_unit_models() or [])
        except Exception:
            target_models = list(getattr(target_root, "models", []) or [])
        in_range = False
        for target_model in target_models:
            if not self._model_is_alive(target_model):
                continue
            try:
                distance = float(distance_between_models_bases_3d(bearer_model, target_model))
            except Exception:
                continue
            if distance <= float(range_inches) + 1e-6:
                in_range = True
                break
        if not in_range:
            return {"ok": False}

        if not ability_name:
            ability_name = str(resolved_name or self._DIVINE_ASPECT_SOURCE_NAME)
        owner_player_id = str(getattr(owner, "id", "") or "")
        source_army_id = str(maybe_entity_id(army) or "")
        pending_entry = {
            "owner_player_id": owner_player_id,
            "source_army_id": source_army_id,
            "source_unit_id": source_unit_id,
            "target_unit_id": target_unit_id,
            "ability_name": str(ability_name or self._DIVINE_ASPECT_SOURCE_NAME),
            "turn": int(getattr(game, "turn", 0) or 0) if game is not None else 0,
        }
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        pending_list = list(sr.get(self._DIVINE_ASPECT_PENDING_KEY, []) or [])
        pending_list.append(pending_entry)
        sr[self._DIVINE_ASPECT_PENDING_KEY] = pending_list
        target_root.special_rules = sr

        take_test = getattr(target_root, "take_battle_shock_test", None)
        if callable(take_test):
            take_test(int(getattr(game, "turn", 0) or 0) if game is not None else 0)

        return {
            "ok": True,
            "source_unit_id": source_unit_id,
            "target_unit_id": target_unit_id,
            "triggered": True,
            "ability_name": str(ability_name),
        }

    def on_divine_aspect_battle_shock_resolved(self, target_unit, *, passed: bool, game=None) -> dict | None:
        if not self.is_army_of_faith() or target_unit is None:
            return None
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return None
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            return None
        pending_list = list(sr.get(self._DIVINE_ASPECT_PENDING_KEY, []) or [])
        if not pending_list:
            return None

        owner = getattr(getattr(self.army, "player", None), "id", None)
        owner_id = str(owner or "")
        source_army_id = str(maybe_entity_id(self.army) or "")
        consumed = None
        remaining: list[dict] = []
        for pending in pending_list:
            if not isinstance(pending, dict):
                continue
            if consumed is not None:
                remaining.append(pending)
                continue
            pending_owner = str(pending.get("owner_player_id", "") or "")
            pending_army = str(pending.get("source_army_id", "") or "")
            if owner_id and pending_owner and pending_owner != owner_id:
                remaining.append(pending)
                continue
            if source_army_id and pending_army and pending_army != source_army_id:
                remaining.append(pending)
                continue
            consumed = pending
        if consumed is None:
            return None
        if remaining:
            sr[self._DIVINE_ASPECT_PENDING_KEY] = remaining
        else:
            sr.pop(self._DIVINE_ASPECT_PENDING_KEY, None)
        target_root.special_rules = sr

        gained = False
        if not bool(passed):
            aof_mgr = getattr(self.army, "acts_of_faith", None)
            gain_fn = getattr(aof_mgr, "gain_miracle_die", None) if aof_mgr is not None else None
            if callable(gain_fn):
                gain_fn(game=game, allow_reroll=False, reason=str(consumed.get("ability_name", "") or self._DIVINE_ASPECT_SOURCE_NAME))
                gained = True
        return {
            "target_unit_id": str(consumed.get("target_unit_id", "") or ""),
            "source_unit_id": str(consumed.get("source_unit_id", "") or ""),
            "ability_name": str(consumed.get("ability_name", "") or self._DIVINE_ASPECT_SOURCE_NAME),
            "gained_miracle_die": bool(gained),
            "passed": bool(passed),
        }

    def unit_is_penitent(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return self._unit_has_keyword(root, "PENITENT")

    def model_is_penitent(self, model, unit) -> bool:
        if model is not None and hasattr(model, "has_any_keyword"):
            if bool(model.has_any_keyword("PENITENT")):
                return True
        model_id = str(maybe_entity_id(model) or "").strip() if model is not None else ""
        if model_id:
            root = self._unit_root(unit)
            if root is not None:
                try:
                    members = list(root.get_attached_unit_members() or [])
                except Exception:
                    members = []
                if not members:
                    members = [root]
                for member in list(members or []):
                    if member is None:
                        continue
                    sr = getattr(member, "special_rules", None)
                    if not (
                        isinstance(sr, dict)
                        and bool(sr.get("enhancement_catechism_of_divine_penitence", False))
                    ):
                        continue
                    bearer_id = str(
                        sr.get("enhancement_catechism_of_divine_penitence_bearer_model_id", "")
                        or sr.get("enhancement_bearer_model_id", "")
                        or ""
                    ).strip()
                    if bearer_id and bearer_id == model_id:
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
        if not self._desperate_for_redemption_vow_active_for_unit(
            self._PATH_OF_THE_PENITENT_KEY,
            unit=unit,
            model=model,
        ):
            return 0, ""
        if not self.model_is_penitent(model, unit):
            return 0, ""
        return 3, f"{self.DESPERATE_FOR_REDEMPTION_NAME} (The Path of the Penitent)"

    def desperate_for_redemption_melee_attacks_bonus(self, attacker_model, *, unit=None, weapon_profile=None) -> tuple[int, str]:
        if not self.is_penitent_host():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        if unit is None:
            unit = getattr(attacker_model, "parent_unit", None)
        if not self._desperate_for_redemption_vow_active_for_unit(
            self._ABSOLUTION_IN_BATTLE_KEY,
            unit=unit,
            model=attacker_model,
        ):
            return 0, ""
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
        if unit is None:
            unit = getattr(attacker_model, "parent_unit", None)
        if not self._desperate_for_redemption_vow_active_for_unit(
            self._ABSOLUTION_IN_BATTLE_KEY,
            unit=unit,
            model=attacker_model,
        ):
            return 0, ""
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
        if not self._desperate_for_redemption_vow_active_for_unit(
            self._DEATH_BEFORE_DISGRACE_KEY,
            unit=unit,
            model=model,
        ):
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

    def clear_light_of_the_emperor(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        changed = False
        for key in (
            self._LIGHT_OF_THE_EMPEROR_ACTIVE_KEY,
            self._LIGHT_OF_THE_EMPEROR_TURN_KEY,
            self._LIGHT_OF_THE_EMPEROR_OWNER_KEY,
            self._LIGHT_OF_THE_EMPEROR_SOURCE_KEY,
            self._LIGHT_OF_THE_EMPEROR_JUMP_PACK_AURA_KEY,
        ):
            if key in sr:
                sr.pop(key, None)
                changed = True
        if changed:
            root.special_rules = sr
        return changed

    def apply_light_of_the_emperor(self, target_unit, *, game=None, source_name: str = "") -> bool:
        if not self.is_army_of_faith() or target_unit is None:
            return False
        root = self._unit_root(target_unit)
        if root is None or not self._unit_is_alive(root):
            return False
        if not self.unit_is_adepta_sororitas(root):
            return False
        if not self._unit_is_deployed_on_battlefield(root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        game_obj = self._resolve_game_context(game=game)
        current_player = getattr(game_obj, "get_current_player", lambda: None)() if game_obj is not None else None
        sr[self._LIGHT_OF_THE_EMPEROR_ACTIVE_KEY] = True
        sr[self._LIGHT_OF_THE_EMPEROR_SOURCE_KEY] = (
            str(source_name or "LIGHT OF THE EMPEROR").strip() or "LIGHT OF THE EMPEROR"
        )
        sr[self._LIGHT_OF_THE_EMPEROR_JUMP_PACK_AURA_KEY] = bool(self._unit_has_keyword(root, "JUMP PACK"))
        sr[self._LIGHT_OF_THE_EMPEROR_OWNER_KEY] = str(
            maybe_entity_id(current_player) or getattr(current_player, "id", "") or ""
        )
        sr[self._LIGHT_OF_THE_EMPEROR_TURN_KEY] = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
        root.special_rules = sr
        return True

    def _light_of_the_emperor_state(self, unit, *, game=None) -> tuple[bool, str, bool]:
        root = self._unit_root(unit)
        if root is None:
            return False, "", False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(self._LIGHT_OF_THE_EMPEROR_ACTIVE_KEY, False)):
            return False, "", False
        game_obj = self._resolve_game_context(game=game)
        if game_obj is not None:
            owner_id = str(sr.get(self._LIGHT_OF_THE_EMPEROR_OWNER_KEY, "") or "")
            try:
                effect_turn = int(sr.get(self._LIGHT_OF_THE_EMPEROR_TURN_KEY, 0) or 0)
            except (TypeError, ValueError):
                effect_turn = 0
            try:
                current_turn = int(getattr(game_obj, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0
            current_player = getattr(game_obj, "get_current_player", lambda: None)()
            current_owner_id = str(maybe_entity_id(current_player) or getattr(current_player, "id", "") or "")
            if (effect_turn and current_turn and effect_turn != current_turn) or (
                owner_id and current_owner_id and owner_id != current_owner_id
            ):
                self.clear_light_of_the_emperor(root)
                return False, "", False
        source = str(sr.get(self._LIGHT_OF_THE_EMPEROR_SOURCE_KEY, "") or "LIGHT OF THE EMPEROR").strip()
        if not source:
            source = "LIGHT OF THE EMPEROR"
        return True, source, bool(sr.get(self._LIGHT_OF_THE_EMPEROR_JUMP_PACK_AURA_KEY, False))

    def _light_of_the_emperor_applies_to_unit(self, unit, *, game=None) -> tuple[bool, str]:
        if not self.is_army_of_faith():
            return False, ""
        root = self._unit_root(unit)
        if root is None or not self._unit_is_alive(root):
            return False, ""
        if not self.unit_is_adepta_sororitas(root):
            return False, ""
        active, source, _jump_pack_aura = self._light_of_the_emperor_state(root, game=game)
        if active:
            return True, source
        if not self._unit_is_deployed_on_battlefield(root):
            return False, ""
        army = self.army
        if army is None:
            return False, ""
        seen: set[str] = set()
        for unit_entry in list(getattr(army, "units", []) or []):
            source_root = self._unit_root(unit_entry)
            source_id = self._unit_id(source_root)
            if source_root is None or not source_id or source_id in seen:
                continue
            seen.add(source_id)
            if source_root is root:
                continue
            if not self._unit_is_alive(source_root):
                continue
            if not self._unit_is_deployed_on_battlefield(source_root):
                continue
            if not self._unit_has_keyword(source_root, "JUMP PACK"):
                continue
            source_active, source_name, jump_pack_aura = self._light_of_the_emperor_state(source_root, game=game)
            if not source_active or not jump_pack_aura:
                continue
            if unit_within_range_of_unit(source_root, root, 3.0, use_attached_aggregate=True):
                return True, source_name
        return False, ""

    def light_of_the_emperor_ignore_modifier_rule(self, unit, *, kind: str, game=None) -> dict | None:
        if not self.is_army_of_faith():
            return None
        kind_key = str(kind or "").strip().lower()
        if kind_key not in {
            "move",
            "advance",
            "charge",
            "hit",
            "wound",
            "toughness",
            "leadership",
            "objective_control",
            "save",
        }:
            return None
        applies, source = self._light_of_the_emperor_applies_to_unit(unit, game=game)
        if not applies:
            return None
        return {
            "source": str(source or "LIGHT OF THE EMPEROR").strip() or "LIGHT OF THE EMPEROR",
            "default_choice": "ignore_negative",
        }

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

    def bringers_of_flame_rites_of_fire_wound_bonus(
        self,
        attacker_model,
        target_unit=None,
        *,
        weapon_profile=None,
        attack_instance=None,
        game=None,
    ) -> tuple[int, str]:
        if not self.is_bringers_of_flame():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(attacker_unit)
        target_root = self._unit_root(target_unit)
        if root is None or target_root is None:
            return 0, ""
        get_parent_army = getattr(root, "get_parent_army", None)
        root_army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        if root_army is not self.army:
            return 0, ""
        if not self.unit_is_adepta_sororitas(root):
            return 0, ""
        if not self._attached_unit_disembarked_from_transport_this_round(root):
            return 0, ""
        parent = getattr(weapon_profile, "parent_wargear", None)
        is_ranged_fn = getattr(parent, "is_ranged", None) if parent is not None else None
        if callable(is_ranged_fn) and not bool(is_ranged_fn()):
            return 0, ""

        sr = getattr(root, "special_rules", None)
        active = sr.get("bringers_of_flame_rites_of_fire_active") if isinstance(sr, dict) else None
        if not isinstance(active, dict):
            return 0, ""

        game_obj = self._resolve_game_context(game=game)
        if game_obj is None:
            return 0, ""
        current_turn = int(getattr(game_obj, "turn", 0) or 0)
        current_player = getattr(game_obj, "get_current_player", lambda: None)()
        current_owner = str(maybe_entity_id(current_player) or getattr(current_player, "id", "") or "")
        current_phase = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper() or "UNKNOWN"
        current_phase_key = f"{current_turn}:{current_owner}:{current_phase}"
        if str(active.get("phase_key", "") or "") != current_phase_key:
            return 0, ""

        within_six = bool(unit_within_range_of_unit(root, target_root, 6.0, use_attached_aggregate=True))
        if not within_six:
            return 0, ""

        game_map = getattr(game_obj, "map", None)
        target_within_objective_fn = getattr(root, "_target_within_objective_range", None)
        if not callable(target_within_objective_fn):
            return 0, ""
        if not bool(target_within_objective_fn(target_root, game_map)):
            return 0, ""

        source = str(active.get("source", "") or "Rites of Fire").strip() or "Rites of Fire"
        return 1, source

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
