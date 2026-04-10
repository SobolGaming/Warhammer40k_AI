from __future__ import annotations

import math
from itertools import combinations
from typing import Optional

from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class AdeptusMechanicusDetachmentManager(DetachmentManagerBase):
    faction_id = "ADM"

    _COHORT_CYBERNETICA_NAME = "Cohort Cybernetica"
    _CYBER_PSALM_PROGRAMMING_SOURCE = "Cyber-Psalm Programming"
    _COHORT_AUTO_DIVINATORY_SOURCE = "Auto-divinatory Targeting"
    _COHORT_BENEVOLENCE_SOURCE = "Benevolence of the Omnissiah"
    _COHORT_MACHINE_SPIRIT_SOURCE = "Machine Spirit Resurgent"
    _COHORT_MACHINE_SUPERIORITY_SOURCE = "Machine Superiority"
    _COHORT_MOTIVE_SOURCE = "Motive Imperative"
    _COHORT_TRANSCENDENT_SOURCE = "Transcendent Cogitation"
    _LEGIO_CYBERNETICA_KEYWORD = "LEGIO CYBERNETICA"
    _EXPLORATOR_MANIPLE_NAME = "Explorator Maniple"
    _ACQUISITION_ABILITY_KEY = "acquisition_at_any_cost"
    _ACQUISITION_SOURCE = "Acquisition At Any Cost"
    _EXPLORATOR_MAGOS_SOURCE = "Magos"
    _EXPLORATOR_GENETOR_SOURCE = "Genetor"
    _EXPLORATOR_LOGIS_SOURCE = "Logis"
    _EXPLORATOR_ARTISAN_SOURCE = "Artisan"
    _HALOSCREED_BATTLE_CLADE_NAME = "Haloscreed Battle Clade"
    _NOOSPHERIC_UNITS_ABILITY_KEY = "noospheric_transference_units"
    _NOOSPHERIC_OVERRIDE_ABILITY_KEY = "noospheric_transference_override"
    _NOOSPHERIC_SOURCE = "Noospheric Transference"
    _HALOSCREED_TRANSORACULAR_SOURCE = "Transoracular Dyad Wafers"
    _HALOSCREED_COGNITIVE_SOURCE = "Cognitive Reinforcement"
    _HALOSCREED_SANCTIFIED_SOURCE = "Sanctified Ordnance"
    _HALOSCREED_INLOADED_SOURCE = "Inloaded Lethality"
    _NOOSPHERIC_ELECTROMOTIVE_KEY = "ELECTROMOTIVE_ENERGISATION"
    _NOOSPHERIC_MICROACTUATOR_KEY = "MICROACTUATOR_BRACING"
    _NOOSPHERIC_PREDATION_KEY = "PREDATION_PROTOCOLS"
    _NOOSPHERIC_MUTED_KEY = "MUTED_SERVOMOTORS"
    _NOOSPHERIC_ACTIVE_FLAG_KEY = "noospheric_transference_halo_override_active"
    _NOOSPHERIC_SOURCE_FLAG_KEY = "noospheric_transference_source"
    _NOOSPHERIC_OVERRIDE_FLAG_KEY = "noospheric_transference_override_key"
    _SKITARII_HUNTER_COHORT_NAME = "Skitarii Hunter Cohort"
    _STEALTH_OPTIMISATION_SOURCE = "Stealth Optimisation"
    _SKITARII_CANTIC_THRALLNET_ABILITY_KEY = "skitarii_cantic_thrallnet"
    _SKITARII_CANTIC_THRALLNET_SOURCE = "Cantic Thrallnet"
    _SKITARII_BATTLE_SPHERE_UPLINK_SOURCE = "Battle-sphere Uplink"
    _SKITARII_CANTIC_THRALLNET_ACTIVE_KEY = "skitarii_cantic_thrallnet_active"
    _SKITARII_CANTIC_THRALLNET_SOURCE_UNIT_ID_KEY = "skitarii_cantic_thrallnet_source_unit_id"
    _SKITARII_CANTIC_THRALLNET_SOURCE_NAME_KEY = "skitarii_cantic_thrallnet_source_name"
    _SKITARII_CANTIC_THRALLNET_STARTED_ROUND_KEY = "skitarii_cantic_thrallnet_started_round"
    _SKITARII_CANTIC_THRALLNET_EXPIRES_ROUND_KEY = "skitarii_cantic_thrallnet_expires_round"
    _DATA_PSALM_CONCLAVE_NAME = "Data-Psalm Conclave"
    _DATA_PSALM_ABILITY_KEY = "data_psalm_benediction"
    _DATA_PSALM_SOURCE = "Benedictions Of The Omnissiah"
    _DATA_PSALM_PANEGYRIC_KEY = "PANEGYRIC_PROCESSION"
    _DATA_PSALM_CITATION_KEY = "CITATION_IN_SAVAGERY"
    _DATA_PSALM_AUTOSERMON_ABILITY_KEY = "data_psalm_autosermon"
    _DATA_PSALM_AUTOSERMON_SOURCE = "Data-blessed Autosermon"
    _DATA_PSALM_AUTOSERMON_ACTIVE_KEY = "data_psalm_autosermon_active"
    _DATA_PSALM_AUTOSERMON_CHOICE_KEY = "data_psalm_autosermon_choice_key"
    _DATA_PSALM_AUTOSERMON_OWNER_KEY = "data_psalm_autosermon_owner_id"
    _DATA_PSALM_AUTOSERMON_STARTED_ROUND_KEY = "data_psalm_autosermon_turn_started"
    _DATA_PSALM_AUTOSERMON_EXPIRES_ROUND_KEY = "data_psalm_autosermon_expires_round"
    _DATA_PSALM_AUTOSERMON_SOURCE_UNIT_ID_KEY = "data_psalm_autosermon_source_unit_id"
    _CULT_MECHANICUS_KEYWORD = "CULT MECHANICUS"

    _RAD_BOMBARDMENT_ABILITY_KEY = "rad_bombardment"
    _RAD_BOMBARDMENT_CHOICE_KEY = "rad_bombardment_choice"
    _RAD_BOMBARDMENT_TAKING_COVER_ROUND_KEY = "rad_bombardment_taking_cover_round"
    _RAD_BOMBARDMENT_TAKING_COVER_ADDED_KEY = "rad_bombardment_taking_cover_added_battleshock"
    _RAD_BOMBARDMENT_CHOICE_STAND_FIRM = "stand_firm"
    _RAD_BOMBARDMENT_CHOICE_TAKE_COVER = "take_cover"
    _RADIAL_SUFFUSION_FLAG_KEY = "enhancement_radial_suffusion"
    _RADIAL_SUFFUSION_ENHANCEMENT_ID = "000008385002"
    _RADIAL_SUFFUSION_ENHANCEMENT_NAME = "radial suffusion"
    _RADIAL_SUFFUSION_EXTRA_RANGE_IN = 6.0
    _EMOTIONLESS_CLARITY_FLAG_KEY = "enhancement_emotionless_clarity"
    _EMOTIONLESS_CLARITY_RANGE_KEY = "enhancement_emotionless_clarity_range"
    _EMOTIONLESS_CLARITY_SOURCE_KEY = "enhancement_emotionless_clarity_source"
    _EMOTIONLESS_CLARITY_USAGE_KEY = "enhancement_emotionless_clarity_usage"

    def __init__(self, army=None):
        super().__init__(army)
        self.active_acquisition_objective_id: str = ""
        self.acquisition_selected_round: int = 0
        self.active_noospheric_unit_ids: list[str] = []
        self.active_noospheric_override_key: str = ""
        self.noospheric_selected_round: int = 0
        self.active_data_psalm_benediction_key: Optional[str] = None
        self.data_psalm_selected_round: Optional[int] = None

    def is_rad_zone_corps(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Rad-Zone Corps")

    def is_data_psalm_conclave(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._DATA_PSALM_CONCLAVE_NAME)

    def is_cohort_cybernetica(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._COHORT_CYBERNETICA_NAME)

    def is_explorator_maniple(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._EXPLORATOR_MANIPLE_NAME)

    def is_haloscreed_battle_clade(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._HALOSCREED_BATTLE_CLADE_NAME)

    def is_skitarii_hunter_cohort(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._SKITARII_HUNTER_COHORT_NAME)

    @classmethod
    def _normalize_data_psalm_choice_key(cls, choice_key: str) -> str:
        raw = str(choice_key or "").strip().upper()
        aliases = {
            "PANEGYRIC": cls._DATA_PSALM_PANEGYRIC_KEY,
            "PANEGYRIC_PROCESSION": cls._DATA_PSALM_PANEGYRIC_KEY,
            "CITATION": cls._DATA_PSALM_CITATION_KEY,
            "CITATION_IN_SAVAGERY": cls._DATA_PSALM_CITATION_KEY,
        }
        return aliases.get(raw, "")

    @classmethod
    def data_psalm_benedictions(cls) -> tuple[tuple[str, str], ...]:
        return (
            (cls._DATA_PSALM_PANEGYRIC_KEY, "Panegyric Procession"),
            (cls._DATA_PSALM_CITATION_KEY, "Citation in Savagery"),
        )

    def can_select_data_psalm_benediction(self, *, game=None, battle_round: Optional[int] = None) -> bool:
        if not self.is_data_psalm_conclave():
            return False
        if self.active_data_psalm_benediction_key:
            return False
        if battle_round is not None:
            try:
                return int(battle_round) == 1
            except (TypeError, ValueError):
                return False
        if game is None:
            return False
        try:
            return int(getattr(game, "turn", 0) or 0) == 1
        except (TypeError, ValueError):
            return False

    def select_data_psalm_benediction(self, choice_key: str, *, battle_round: Optional[int] = None) -> bool:
        if not self.can_select_data_psalm_benediction(battle_round=battle_round):
            return False
        normalized = self._normalize_data_psalm_choice_key(choice_key)
        if not normalized:
            return False
        self.active_data_psalm_benediction_key = normalized
        if battle_round is not None:
            try:
                self.data_psalm_selected_round = int(battle_round)
            except (TypeError, ValueError):
                self.data_psalm_selected_round = None
        return True

    def _data_psalm_benediction_active(self, choice_key: str) -> bool:
        if not self.is_data_psalm_conclave():
            return False
        if not self.active_data_psalm_benediction_key:
            return False
        return self.active_data_psalm_benediction_key == self._normalize_data_psalm_choice_key(choice_key)

    @classmethod
    def _other_data_psalm_benediction_key(cls, current_choice_key: str) -> str:
        current = cls._normalize_data_psalm_choice_key(current_choice_key)
        if not current:
            return ""
        if current == cls._DATA_PSALM_PANEGYRIC_KEY:
            return cls._DATA_PSALM_CITATION_KEY
        if current == cls._DATA_PSALM_CITATION_KEY:
            return cls._DATA_PSALM_PANEGYRIC_KEY
        return ""

    def _data_psalm_autosermon_effect_active_for_unit(self, unit, choice_key: str, *, game=None) -> bool:
        if not self.is_data_psalm_conclave():
            return False
        normalized_choice = self._normalize_data_psalm_choice_key(choice_key)
        if not normalized_choice:
            return False
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(self._DATA_PSALM_AUTOSERMON_ACTIVE_KEY, False)):
            return False
        active_choice = self._normalize_data_psalm_choice_key(str(sr.get(self._DATA_PSALM_AUTOSERMON_CHOICE_KEY, "") or ""))
        if active_choice != normalized_choice:
            return False
        if game is None:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(owner, "game", None) if owner is not None else None
        if game is None:
            return True
        try:
            current_round = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_round = 0
        try:
            expires_round = int(sr.get(self._DATA_PSALM_AUTOSERMON_EXPIRES_ROUND_KEY, 0) or 0)
        except (TypeError, ValueError):
            expires_round = 0
        if expires_round <= 0:
            return True
        if current_round > expires_round:
            for key in (
                self._DATA_PSALM_AUTOSERMON_ACTIVE_KEY,
                self._DATA_PSALM_AUTOSERMON_CHOICE_KEY,
                self._DATA_PSALM_AUTOSERMON_OWNER_KEY,
                self._DATA_PSALM_AUTOSERMON_STARTED_ROUND_KEY,
                self._DATA_PSALM_AUTOSERMON_EXPIRES_ROUND_KEY,
                self._DATA_PSALM_AUTOSERMON_SOURCE_UNIT_ID_KEY,
            ):
                sr.pop(key, None)
            root.special_rules = sr
            return False
        if current_round == expires_round:
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            owner_id = str(sr.get(self._DATA_PSALM_AUTOSERMON_OWNER_KEY, "") or "")
            current_player = getattr(game, "get_current_player", lambda: None)()
            current_owner_id = str(getattr(current_player, "id", "") or "")
            if phase_name == "COMMAND_PHASE" and owner_id and current_owner_id == owner_id:
                for key in (
                    self._DATA_PSALM_AUTOSERMON_ACTIVE_KEY,
                    self._DATA_PSALM_AUTOSERMON_CHOICE_KEY,
                    self._DATA_PSALM_AUTOSERMON_OWNER_KEY,
                    self._DATA_PSALM_AUTOSERMON_STARTED_ROUND_KEY,
                    self._DATA_PSALM_AUTOSERMON_EXPIRES_ROUND_KEY,
                    self._DATA_PSALM_AUTOSERMON_SOURCE_UNIT_ID_KEY,
                ):
                    sr.pop(key, None)
                root.special_rules = sr
                return False
        return True

    def _iter_data_psalm_autosermon_sources(self) -> list[tuple]:
        if self.army is None:
            return []
        seen_roots: set[str] = set()
        sources: list[tuple] = []
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root) or str(id(root))
            if root_id in seen_roots:
                continue
            seen_roots.add(root_id)
            if not self._unit_is_on_battlefield(root):
                continue
            members = list(getattr(root, "get_attached_unit_members", lambda: [])() or [])
            if not members:
                members = [root]
            for member in list(members or []):
                if member is None:
                    continue
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict) or not bool(sr.get("enhancement_data_blessed_autosermon", False)):
                    continue
                get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                bearer = get_bearer() if callable(get_bearer) else None
                if bearer is None or not self._is_model_alive(bearer):
                    continue
                sources.append((str(root_id), root, member, sr, bearer))
        sources.sort(
            key=lambda item: (
                str(item[0]),
                self._entity_id(item[2]) or str(id(item[2])),
            )
        )
        return sources

    def _pending_data_psalm_autosermon_request(self, game, *, source_root_id: str, battle_round: int):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._DATA_PSALM_AUTOSERMON_ABILITY_KEY:
                continue
            if str(ctx.get("source_unit_id", "") or "") != str(source_root_id or ""):
                continue
            try:
                req_round = int(ctx.get("battle_round", 0) or 0)
            except (TypeError, ValueError):
                req_round = 0
            if req_round != int(battle_round):
                continue
            return req
        return None

    def _build_data_psalm_autosermon_request(self, game, *, source_root, source_member, choice_key: str, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        owner = getattr(self.army, "player", None)
        if owner is None or source_root is None or source_member is None:
            return None
        normalized_choice = self._normalize_data_psalm_choice_key(choice_key)
        if not normalized_choice:
            return None
        label_map = {key: label for key, label in self.data_psalm_benedictions()}
        choice_label = str(label_map.get(normalized_choice, normalized_choice.replace("_", " ").title()))
        source_name = str(
            getattr(source_member, "special_rules", {}).get("enhancement_data_blessed_autosermon_source", "")
            if isinstance(getattr(source_member, "special_rules", None), dict)
            else ""
        ) or self._DATA_PSALM_AUTOSERMON_SOURCE
        source_name = source_name.strip() or self._DATA_PSALM_AUTOSERMON_SOURCE
        once_key = str(
            getattr(source_member, "special_rules", {}).get("enhancement_data_blessed_autosermon_once_key", "")
            if isinstance(getattr(source_member, "special_rules", None), dict)
            else ""
        ).strip().lower() or "data_blessed_autosermon"
        source_root_id = self._entity_id(source_root)
        source_member_id = self._entity_id(source_member)
        options = [
            DecisionOption.create("None", payload={"action": "skip"}),
            DecisionOption.create(
                f"Activate ({choice_label})",
                payload={
                    "source_unit_id": source_root_id,
                    "source_member_unit_id": source_member_id,
                    "choice_key": normalized_choice,
                },
            ),
        ]
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{source_name}: activate for this Command phase (or None).",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._DATA_PSALM_AUTOSERMON_ABILITY_KEY,
                "ability_name": source_name,
                "ability_key": once_key,
                "source_unit_id": source_root_id,
                "source_member_unit_id": source_member_id,
                "battle_round": int(battle_round),
                "allowed_choice_keys": [normalized_choice],
                "optional": True,
            },
        )

    def _queue_data_psalm_autosermon_requests(self, game, *, player, battle_round: int) -> None:
        if not self.is_data_psalm_conclave():
            return
        if game is None or player is None or player is not getattr(self.army, "player", None):
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not self.active_data_psalm_benediction_key:
            return
        other_choice = self._other_data_psalm_benediction_key(self.active_data_psalm_benediction_key)
        if not other_choice:
            return
        for source_root_id, source_root, source_member, source_sr, _bearer in self._iter_data_psalm_autosermon_sources():
            once_key = str(source_sr.get("enhancement_data_blessed_autosermon_once_key", "") or "data_blessed_autosermon").strip().lower()
            if not once_key:
                once_key = "data_blessed_autosermon"
            has_used = getattr(source_root, "has_used_unit_once_per_battle", None)
            if callable(has_used) and bool(has_used(once_key)):
                continue
            if self._pending_data_psalm_autosermon_request(
                game,
                source_root_id=source_root_id,
                battle_round=int(battle_round),
            ) is not None:
                continue
            request = self._build_data_psalm_autosermon_request(
                game,
                source_root=source_root,
                source_member=source_member,
                choice_key=other_choice,
                battle_round=int(battle_round),
            )
            request_decision = getattr(game, "request_decision", None)
            if callable(request_decision) and request is not None:
                request_decision(request)

    def _clear_expired_data_psalm_autosermon_state(self, *, game=None, player=None, battle_round: int = 0) -> None:
        if game is None or player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        current_round = int(battle_round or 0)
        seen_roots: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            source_root = self._attached_root(unit)
            if source_root is None:
                continue
            root_id = self._entity_id(source_root) or str(id(source_root))
            if root_id in seen_roots:
                continue
            seen_roots.add(root_id)
            sr = getattr(source_root, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(self._DATA_PSALM_AUTOSERMON_ACTIVE_KEY, False)):
                continue
            sr_owner = str(sr.get(self._DATA_PSALM_AUTOSERMON_OWNER_KEY, "") or "")
            if sr_owner and sr_owner != owner_id:
                continue
            try:
                expires_round = int(sr.get(self._DATA_PSALM_AUTOSERMON_EXPIRES_ROUND_KEY, 0) or 0)
            except (TypeError, ValueError):
                expires_round = 0
            if expires_round <= 0 or current_round < expires_round:
                continue
            updated = dict(sr)
            for key in (
                self._DATA_PSALM_AUTOSERMON_ACTIVE_KEY,
                self._DATA_PSALM_AUTOSERMON_CHOICE_KEY,
                self._DATA_PSALM_AUTOSERMON_OWNER_KEY,
                self._DATA_PSALM_AUTOSERMON_STARTED_ROUND_KEY,
                self._DATA_PSALM_AUTOSERMON_EXPIRES_ROUND_KEY,
                self._DATA_PSALM_AUTOSERMON_SOURCE_UNIT_ID_KEY,
            ):
                updated.pop(key, None)
            source_root.special_rules = updated

    def _resolve_data_psalm_autosermon_source(self, source_unit_id: str):
        wanted = str(source_unit_id or "").strip()
        if not wanted:
            return None
        for root_id, source_root, source_member, source_sr, bearer in self._iter_data_psalm_autosermon_sources():
            if str(root_id or "").strip() != wanted:
                continue
            return source_root, source_member, source_sr, bearer
        return None

    def validate_data_psalm_autosermon_choice(
        self,
        source_unit_id: str,
        choice_key: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ) -> tuple[bool, str]:
        if not self.is_data_psalm_conclave():
            return False, "Data-blessed Autosermon requires a Data-Psalm Conclave army."
        if self.army is None:
            return False, "Data-blessed Autosermon army not found."
        owner = getattr(self.army, "player", None)
        if player is not None and owner is not None and player is not owner:
            return False, "Data-blessed Autosermon must be resolved by the owning player."
        if not self.active_data_psalm_benediction_key:
            return False, "Data-blessed Autosermon requires an active Benediction of the Omnissiah."
        resolved = self._resolve_data_psalm_autosermon_source(source_unit_id)
        if resolved is None:
            return False, "Data-blessed Autosermon source unit was not found."
        source_root, source_member, source_sr, _bearer = resolved
        once_key = str(source_sr.get("enhancement_data_blessed_autosermon_once_key", "") or "data_blessed_autosermon").strip().lower()
        if not once_key:
            once_key = "data_blessed_autosermon"
        has_used = getattr(source_root, "has_used_unit_once_per_battle", None)
        if callable(has_used) and bool(has_used(once_key)):
            return False, "Data-blessed Autosermon has already been used for this unit."
        normalized = self._normalize_data_psalm_choice_key(choice_key)
        if not normalized:
            return False, "Data-blessed Autosermon choice is not supported."
        expected_choice = self._other_data_psalm_benediction_key(self.active_data_psalm_benediction_key)
        if normalized != expected_choice:
            return False, "Data-blessed Autosermon must select the Benediction not currently active for your army."
        expected_round = int(battle_round or 0)
        if expected_round and game is not None:
            try:
                current_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_round = 0
            if current_round and current_round != expected_round:
                return False, "Data-blessed Autosermon selection is no longer in the current Command phase."
        _ = source_member
        return True, ""

    def activate_data_psalm_autosermon(
        self,
        source_unit_id: str,
        choice_key: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ):
        valid, reason = self.validate_data_psalm_autosermon_choice(
            source_unit_id,
            choice_key,
            game=game,
            player=player,
            battle_round=battle_round,
        )
        if not valid:
            return None
        resolved = self._resolve_data_psalm_autosermon_source(source_unit_id)
        if resolved is None:
            return None
        source_root, source_member, source_sr, _bearer = resolved
        normalized = self._normalize_data_psalm_choice_key(choice_key)
        labels = {key: label for key, label in self.data_psalm_benedictions()}
        owner = getattr(self.army, "player", None)
        owner_id = str(getattr(owner, "id", "") or "")
        if game is not None:
            try:
                current_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_round = int(battle_round or 0)
        else:
            current_round = int(battle_round or 0)
        if current_round <= 0:
            current_round = int(battle_round or 0)
        expires_round = int(current_round + 1) if current_round > 0 else 0
        sr_root = getattr(source_root, "special_rules", None)
        if not isinstance(sr_root, dict):
            sr_root = {}
        updated = dict(sr_root)
        source_name = str(source_sr.get("enhancement_data_blessed_autosermon_source", "") or self._DATA_PSALM_AUTOSERMON_SOURCE).strip()
        if not source_name:
            source_name = self._DATA_PSALM_AUTOSERMON_SOURCE
        updated[self._DATA_PSALM_AUTOSERMON_ACTIVE_KEY] = True
        updated[self._DATA_PSALM_AUTOSERMON_CHOICE_KEY] = normalized
        updated[self._DATA_PSALM_AUTOSERMON_OWNER_KEY] = owner_id
        updated[self._DATA_PSALM_AUTOSERMON_STARTED_ROUND_KEY] = int(current_round or 0)
        updated[self._DATA_PSALM_AUTOSERMON_EXPIRES_ROUND_KEY] = int(expires_round or 0)
        updated[self._DATA_PSALM_AUTOSERMON_SOURCE_UNIT_ID_KEY] = str(self._entity_id(source_root) or "")
        source_root.special_rules = updated
        once_key = str(source_sr.get("enhancement_data_blessed_autosermon_once_key", "") or "data_blessed_autosermon").strip().lower()
        if not once_key:
            once_key = "data_blessed_autosermon"
        mark_used = getattr(source_root, "mark_unit_once_per_battle_used", None)
        if callable(mark_used):
            mark_used(once_key, ability_name=source_name)
        return {
            "source_unit_id": str(self._entity_id(source_root) or ""),
            "choice_key": normalized,
            "choice_label": str(labels.get(normalized, normalized.replace("_", " ").title())),
            "battle_round": int(current_round or 0),
            "source": source_name,
        }

    def _pending_data_psalm_benediction_request(self, game, army_id: str):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._DATA_PSALM_ABILITY_KEY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            return req
        return None

    def _build_data_psalm_benediction_request(self, game, *, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        if game is None:
            return None
        owner = getattr(self.army, "player", None)
        if owner is None:
            return None
        army_id = self._entity_id(self.army)
        options = [
            DecisionOption.create(
                label,
                payload={
                    "army_id": army_id,
                    "choice_key": key,
                },
            )
            for key, label in self.data_psalm_benedictions()
        ]
        if not options:
            return None
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Benedictions of the Omnissiah: select one Benediction to be active for the battle.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._DATA_PSALM_ABILITY_KEY,
                "ability_name": self._DATA_PSALM_SOURCE,
                "army_id": army_id,
                "battle_round": int(battle_round),
                "allowed_choice_keys": [key for key, _label in self.data_psalm_benedictions()],
                "optional": False,
            },
        )

    def _queue_data_psalm_benediction_request(self, game, *, battle_round: int) -> None:
        if not self.is_data_psalm_conclave():
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if not self.can_select_data_psalm_benediction(game=game, battle_round=battle_round):
            return
        army_id = self._entity_id(self.army)
        if self._pending_data_psalm_benediction_request(game, army_id) is not None:
            return
        request = self._build_data_psalm_benediction_request(game, battle_round=int(battle_round))
        request_decision = getattr(game, "request_decision", None)
        if callable(request_decision) and request is not None:
            request_decision(request)

    @staticmethod
    def _entity_id(entity) -> str:
        value = get_entity_id(entity)
        return str(value or "")

    @staticmethod
    def _attached_root(unit):
        if unit is None:
            return None
        getter = getattr(unit, "get_attached_unit_root", None)
        if callable(getter):
            root = getter()
            if root is not None:
                return root
        return unit

    @staticmethod
    def _is_model_alive(model) -> bool:
        alive_attr = getattr(model, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    def _iter_unit_models(self, unit) -> list:
        if unit is None:
            return []
        get_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        else:
            models = list(getattr(unit, "models", []) or [])
        return [model for model in models if model is not None and self._is_model_alive(model)]

    def _unit_in_army(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        for own_unit in list(getattr(self.army, "units", []) or []):
            if self._attached_root(own_unit) is root:
                return True
        return False

    @staticmethod
    def _unit_is_battle_shocked(unit) -> bool:
        if unit is None:
            return False
        check = getattr(unit, "is_battle_shocked", None)
        return bool(check()) if callable(check) else False

    def _legio_cybernetica_root(self, unit):
        if not self.is_cohort_cybernetica():
            return None
        root = self._attached_root(unit)
        if root is None:
            return None
        if not self._unit_in_army(root):
            return None
        if not self._unit_has_keyword(root, self._LEGIO_CYBERNETICA_KEYWORD):
            return None
        return root

    def _cohort_cybernetica_eligible_root(
        self,
        unit,
        *,
        require_vehicle: bool = False,
        allow_legio: bool = True,
    ):
        if not self.is_cohort_cybernetica():
            return None
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return None
        is_admech = self._unit_has_keyword_or_faction(root, "ADEPTUS MECHANICUS", faction_id=self.faction_id)
        is_vehicle = bool(getattr(root, "is_vehicle", False)) or self._unit_has_keyword(root, "VEHICLE")
        is_legio = self._unit_has_keyword(root, self._LEGIO_CYBERNETICA_KEYWORD)
        if require_vehicle:
            if not is_vehicle or not is_admech:
                return None
            return root
        if is_vehicle and is_admech:
            return root
        if allow_legio and is_legio:
            return root
        return None

    def _cohort_effect_source_name(self, sr, prefix: str, default_name: str) -> str:
        if not isinstance(sr, dict):
            return str(default_name or "").strip() or "Cohort Cybernetica"
        return str(sr.get(f"{prefix}_source", "") or default_name).strip() or str(default_name or "Cohort Cybernetica")

    def _clear_cohort_effect(
        self,
        root,
        prefix: str,
        *,
        extra_keys: tuple[str, ...] = (),
        fnp_source_key: str = "",
    ) -> None:
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            f"{prefix}_active",
            f"{prefix}_turn_owner",
            f"{prefix}_turn",
            f"{prefix}_source",
            *tuple(extra_keys or ()),
        ):
            sr.pop(key, None)
        if fnp_source_key:
            entries = list(sr.get("bearer_unit_fnp") or [])
            keep = []
            for entry in entries:
                if isinstance(entry, dict) and str(entry.get("source_key", "") or "") == fnp_source_key:
                    continue
                keep.append(entry)
            if keep:
                sr["bearer_unit_fnp"] = keep
            else:
                sr.pop("bearer_unit_fnp", None)
        root.special_rules = sr

    def _cohort_command_phase_effect_state(
        self,
        unit,
        *,
        prefix: str,
        default_source: str,
        game=None,
        extra_keys: tuple[str, ...] = (),
        fnp_source_key: str = "",
    ) -> tuple[object, dict | None, str]:
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None, ""
        sr = getattr(root, "special_rules", None)
        if not (isinstance(sr, dict) and bool(sr.get(f"{prefix}_active", False))):
            return root, None, ""
        if game is None:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(owner, "game", None) if owner is not None else None
        try:
            effect_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        if game is not None and effect_turn > 0:
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0
            if current_turn >= effect_turn + 1:
                self._clear_cohort_effect(
                    root,
                    prefix,
                    extra_keys=extra_keys,
                    fnp_source_key=fnp_source_key,
                )
                return root, None, ""
        return root, sr, self._cohort_effect_source_name(sr, prefix, default_source)

    def _cohort_turn_effect_state(
        self,
        unit,
        *,
        prefix: str,
        default_source: str,
        game=None,
        extra_keys: tuple[str, ...] = (),
    ) -> tuple[object, dict | None, str]:
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None, ""
        sr = getattr(root, "special_rules", None)
        if not (isinstance(sr, dict) and bool(sr.get(f"{prefix}_active", False))):
            return root, None, ""
        if game is None:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(owner, "game", None) if owner is not None else None
        try:
            effect_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        if game is not None and effect_turn > 0:
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0
            if current_turn != effect_turn:
                self._clear_cohort_effect(root, prefix, extra_keys=extra_keys)
                return root, None, ""
        return root, sr, self._cohort_effect_source_name(sr, prefix, default_source)

    def _cohort_objective_from_sr(self, sr, *, game=None):
        if not isinstance(sr, dict):
            return None
        objective_id = str(sr.get("cohort_auto_divinatory_targeting_objective_id", "") or "").strip()
        if not objective_id:
            return None
        if game is None:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(owner, "game", None) if owner is not None else None
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return None
        for objective in list(getattr(game_map, "objectives", []) or []):
            if str(self._entity_id(objective) or "") == objective_id:
                return objective
        return None

    def cyber_psalm_programming_movement_bonus(self, model, *, unit=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        if self._legio_cybernetica_root(source_unit) is None:
            return 0, ""
        return 2, self._CYBER_PSALM_PROGRAMMING_SOURCE

    def cyber_psalm_programming_objective_control_bonus(self, model, *, unit=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        root = self._legio_cybernetica_root(source_unit)
        if root is None:
            return 0, ""
        if self._unit_is_battle_shocked(root):
            return 0, ""
        return 1, self._CYBER_PSALM_PROGRAMMING_SOURCE

    def auto_divinatory_targeting_attack_skill_override(
        self,
        model,
        *,
        attack_type: str = "any",
        weapon_profile=None,
        game=None,
    ) -> dict | None:
        _ = weapon_profile
        if model is None:
            return None
        attack_key = str(attack_type or "").strip().lower()
        if attack_key not in {"any", "ranged"}:
            return None
        source_unit = getattr(model, "parent_unit", None)
        root = self._cohort_cybernetica_eligible_root(source_unit, allow_legio=True)
        if root is None:
            return None
        _root, sr, source = self._cohort_command_phase_effect_state(
            root,
            prefix="cohort_auto_divinatory_targeting",
            default_source=self._COHORT_AUTO_DIVINATORY_SOURCE,
            game=game,
            extra_keys=("cohort_auto_divinatory_targeting_objective_id",),
        )
        if sr is None:
            return None
        return {
            "value": 3,
            "source": str(source or self._COHORT_AUTO_DIVINATORY_SOURCE),
            "attack_type": "ranged",
            "source_model_id": str(get_entity_id(model) or ""),
        }

    def auto_divinatory_targeting_attack_keywords(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[list[str], str]:
        _ = weapon_profile
        if attacker_model is None:
            return [], ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root = self._cohort_cybernetica_eligible_root(attacker_unit, allow_legio=True)
        if root is None:
            return [], ""
        _root, sr, source = self._cohort_command_phase_effect_state(
            root,
            prefix="cohort_auto_divinatory_targeting",
            default_source=self._COHORT_AUTO_DIVINATORY_SOURCE,
            game=game,
            extra_keys=("cohort_auto_divinatory_targeting_objective_id",),
        )
        if sr is None:
            return [], ""
        return ["IGNORES COVER"], str(source or self._COHORT_AUTO_DIVINATORY_SOURCE)

    def auto_divinatory_targeting_requires_objective_targets(self, unit, *, game=None) -> bool:
        root = self._cohort_cybernetica_eligible_root(unit, allow_legio=True)
        if root is None:
            return False
        _root, sr, _source = self._cohort_command_phase_effect_state(
            root,
            prefix="cohort_auto_divinatory_targeting",
            default_source=self._COHORT_AUTO_DIVINATORY_SOURCE,
            game=game,
            extra_keys=("cohort_auto_divinatory_targeting_objective_id",),
        )
        return sr is not None

    def auto_divinatory_targeting_target_is_legal(self, attacker_unit, target_unit, *, game=None) -> bool:
        attacker_root = self._cohort_cybernetica_eligible_root(attacker_unit, allow_legio=True)
        if attacker_root is None:
            return True
        _root, sr, _source = self._cohort_command_phase_effect_state(
            attacker_root,
            prefix="cohort_auto_divinatory_targeting",
            default_source=self._COHORT_AUTO_DIVINATORY_SOURCE,
            game=game,
            extra_keys=("cohort_auto_divinatory_targeting_objective_id",),
        )
        if sr is None:
            return True
        objective = self._cohort_objective_from_sr(sr, game=game)
        location = getattr(objective, "location", None) if objective is not None else None
        if location is None:
            return False
        target_root = self._attached_root(target_unit)
        if target_root is None:
            return False
        in_range = getattr(target_root, "is_within_objective_range", None)
        if callable(in_range):
            return bool(in_range(location))
        return False

    def motive_imperative_movement_bonus(self, model, *, unit=None, game=None) -> tuple[int, str]:
        _ = game
        if model is None:
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        root = self._cohort_cybernetica_eligible_root(source_unit, require_vehicle=True, allow_legio=False)
        if root is None:
            return 0, ""
        _root, sr, source = self._cohort_command_phase_effect_state(
            root,
            prefix="cohort_motive_imperative",
            default_source=self._COHORT_MOTIVE_SOURCE,
            game=game,
        )
        if sr is None:
            return 0, ""
        return 3, str(source or self._COHORT_MOTIVE_SOURCE)

    def motive_imperative_advance_roll_bonus(self, unit, *, game=None) -> tuple[int, str]:
        root = self._cohort_cybernetica_eligible_root(unit, require_vehicle=True, allow_legio=False)
        if root is None:
            return 0, ""
        _root, sr, source = self._cohort_command_phase_effect_state(
            root,
            prefix="cohort_motive_imperative",
            default_source=self._COHORT_MOTIVE_SOURCE,
            game=game,
        )
        if sr is None:
            return 0, ""
        return 1, str(source or self._COHORT_MOTIVE_SOURCE)

    def motive_imperative_charge_roll_bonus(self, unit, target_units=None, *, game=None) -> tuple[int, str]:
        _ = target_units
        root = self._cohort_cybernetica_eligible_root(unit, require_vehicle=True, allow_legio=False)
        if root is None:
            return 0, ""
        _root, sr, source = self._cohort_command_phase_effect_state(
            root,
            prefix="cohort_motive_imperative",
            default_source=self._COHORT_MOTIVE_SOURCE,
            game=game,
        )
        if sr is None:
            return 0, ""
        return 1, str(source or self._COHORT_MOTIVE_SOURCE)

    def machine_superiority_ignore_modifier_rule(self, unit, *, kind: str, game=None) -> dict | None:
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
        }:
            return None
        root = self._cohort_cybernetica_eligible_root(unit, allow_legio=True)
        if root is None:
            return None
        _root, sr, source = self._cohort_turn_effect_state(
            root,
            prefix="cohort_machine_superiority",
            default_source=self._COHORT_MACHINE_SUPERIORITY_SOURCE,
            game=game,
        )
        if sr is None:
            return None
        return {
            "source": str(source or self._COHORT_MACHINE_SUPERIORITY_SOURCE),
            "default_choice": "ignore_negative",
        }

    def machine_superiority_can_shoot_after_fall_back(self, unit, *, profile=None, game=None) -> bool:
        _ = profile
        root = self._cohort_cybernetica_eligible_root(unit, allow_legio=True)
        if root is None:
            return False
        _root, sr, _source = self._cohort_turn_effect_state(
            root,
            prefix="cohort_machine_superiority",
            default_source=self._COHORT_MACHINE_SUPERIORITY_SOURCE,
            game=game,
        )
        return sr is not None

    def machine_spirit_resurgent_hit_reroll(self, unit, *, game=None) -> tuple[bool, str]:
        root = self._cohort_cybernetica_eligible_root(unit, allow_legio=True)
        if root is None:
            return False, ""
        _root, sr, source = self._cohort_command_phase_effect_state(
            root,
            prefix="cohort_machine_spirit_resurgent",
            default_source=self._COHORT_MACHINE_SPIRIT_SOURCE,
            game=game,
        )
        if sr is None:
            return False, ""
        return True, str(source or self._COHORT_MACHINE_SPIRIT_SOURCE)

    def machine_spirit_resurgent_wound_reroll(self, unit, *, game=None) -> tuple[bool, str]:
        root = self._cohort_cybernetica_eligible_root(unit, allow_legio=True)
        if root is None:
            return False, ""
        _root, sr, source = self._cohort_command_phase_effect_state(
            root,
            prefix="cohort_machine_spirit_resurgent",
            default_source=self._COHORT_MACHINE_SPIRIT_SOURCE,
            game=game,
        )
        if sr is None:
            return False, ""
        below_half_fn = getattr(root, "is_below_half_strength", None)
        below_half = bool(below_half_fn()) if callable(below_half_fn) else False
        if not below_half:
            return False, ""
        return True, str(source or self._COHORT_MACHINE_SPIRIT_SOURCE)

    def transcendent_cogitation_applies(self, unit, *, game=None) -> bool:
        root = self._cohort_cybernetica_eligible_root(unit, allow_legio=True)
        if root is None:
            return False
        _root, sr, _source = self._cohort_command_phase_effect_state(
            root,
            prefix="cohort_transcendent_cogitation",
            default_source=self._COHORT_TRANSCENDENT_SOURCE,
            game=game,
        )
        return sr is not None

    def _cleanup_expired_cohort_cybernetica_command_phase_effects(self, *, game=None) -> None:
        if not self.is_cohort_cybernetica() or self.army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root) or str(id(root))
            if root_id in seen:
                continue
            seen.add(root_id)
            self._cohort_command_phase_effect_state(
                root,
                prefix="cohort_auto_divinatory_targeting",
                default_source=self._COHORT_AUTO_DIVINATORY_SOURCE,
                game=game,
                extra_keys=("cohort_auto_divinatory_targeting_objective_id",),
            )
            self._cohort_command_phase_effect_state(
                root,
                prefix="cohort_benevolence_of_the_omnissiah",
                default_source=self._COHORT_BENEVOLENCE_SOURCE,
                game=game,
                fnp_source_key="cohort_benevolence_of_the_omnissiah",
            )
            self._cohort_command_phase_effect_state(
                root,
                prefix="cohort_machine_spirit_resurgent",
                default_source=self._COHORT_MACHINE_SPIRIT_SOURCE,
                game=game,
            )
            self._cohort_command_phase_effect_state(
                root,
                prefix="cohort_motive_imperative",
                default_source=self._COHORT_MOTIVE_SOURCE,
                game=game,
            )
            self._cohort_command_phase_effect_state(
                root,
                prefix="cohort_transcendent_cogitation",
                default_source=self._COHORT_TRANSCENDENT_SOURCE,
                game=game,
            )
            self._cohort_turn_effect_state(
                root,
                prefix="cohort_machine_superiority",
                default_source=self._COHORT_MACHINE_SUPERIORITY_SOURCE,
                game=game,
            )

    def _data_psalm_cult_mechanicus_root(self, unit):
        if not self.is_data_psalm_conclave():
            return None
        root = self._attached_root(unit)
        if root is None:
            return None
        if not self._unit_in_army(root):
            return None
        if not self._unit_has_keyword(root, self._CULT_MECHANICUS_KEYWORD):
            return None
        return root

    @staticmethod
    def _weapon_is_attack_type(weapon_profile, attack_type: str) -> bool:
        if weapon_profile is None:
            return False
        parent = getattr(weapon_profile, "parent_wargear", None)
        if parent is None:
            return False
        checker = getattr(parent, f"is_{attack_type}", None)
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _weapon_effective_range_max(weapon_profile, attacker_model) -> float:
        if weapon_profile is None:
            return 0.0
        fn = getattr(weapon_profile, "_effective_range_max", None)
        if callable(fn):
            try:
                return float(fn(attacker_model) or 0.0)
            except (TypeError, ValueError):
                return 0.0
        range_obj = getattr(weapon_profile, "range", None)
        if range_obj is None:
            return 0.0
        try:
            return float(getattr(range_obj, "max", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _unit_made_charge_move_this_turn(self, unit, *, game=None) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "charged_this_round", False)):
            return False
        charge_suppressed_fn = getattr(root, "charge_bonus_suppressed", None)
        if callable(charge_suppressed_fn) and bool(charge_suppressed_fn(game=game)):
            return False
        return True

    def data_psalm_panegyric_procession_ap_bonus(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or target_unit is None:
            return 0, ""
        if not self._weapon_is_attack_type(weapon_profile, "ranged"):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._data_psalm_cult_mechanicus_root(attacker_unit)
        if attacker_root is None:
            return 0, ""
        army_active = self._data_psalm_benediction_active(self._DATA_PSALM_PANEGYRIC_KEY)
        unit_active = self._data_psalm_autosermon_effect_active_for_unit(
            attacker_root,
            self._DATA_PSALM_PANEGYRIC_KEY,
            game=game,
        )
        if not army_active and not unit_active:
            return 0, ""
        target_root = self._attached_root(target_unit)
        if target_root is None:
            return 0, ""
        if game is None:
            owner = getattr(self.army, "player", None)
            game = getattr(owner, "game", None) if owner is not None else None
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return 0, ""
        range_max = self._weapon_effective_range_max(weapon_profile, attacker_model)
        if range_max <= 0.0:
            return 0, ""
        distance_fn = getattr(game_map, "get_distance_between_units", None)
        if not callable(distance_fn):
            return 0, ""
        try:
            distance = float(distance_fn(attacker_root, target_root))
        except (TypeError, ValueError):
            return 0, ""
        if distance > (range_max / 2.0) + 1e-6:
            return 0, ""
        return 1, f"{self._DATA_PSALM_SOURCE} (Panegyric Procession)"

    def _data_psalm_citation_in_savagery_bonus(
        self,
        attacker_model,
        *,
        unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None:
            return 0, ""
        if not self._weapon_is_attack_type(weapon_profile, "melee"):
            return 0, ""
        source_unit = unit if unit is not None else getattr(attacker_model, "parent_unit", None)
        source_root = self._data_psalm_cult_mechanicus_root(source_unit)
        if source_root is None:
            return 0, ""
        army_active = self._data_psalm_benediction_active(self._DATA_PSALM_CITATION_KEY)
        unit_active = self._data_psalm_autosermon_effect_active_for_unit(
            source_root,
            self._DATA_PSALM_CITATION_KEY,
            game=game,
        )
        if not army_active and not unit_active:
            return 0, ""
        if not self._unit_made_charge_move_this_turn(source_root, game=game):
            return 0, ""
        return 1, f"{self._DATA_PSALM_SOURCE} (Citation in Savagery)"

    def data_psalm_citation_in_savagery_melee_strength_bonus(
        self,
        attacker_model,
        *,
        unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        return self._data_psalm_citation_in_savagery_bonus(
            attacker_model,
            unit=unit,
            weapon_profile=weapon_profile,
            game=game,
        )

    def data_psalm_citation_in_savagery_melee_attacks_bonus(
        self,
        attacker_model,
        *,
        unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        return self._data_psalm_citation_in_savagery_bonus(
            attacker_model,
            unit=unit,
            weapon_profile=weapon_profile,
            game=game,
        )

    @staticmethod
    def _clear_data_psalm_phase_effect(root, prefix: str) -> None:
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            f"{prefix}_active",
            f"{prefix}_turn_owner",
            f"{prefix}_turn",
            f"{prefix}_expires_phase",
            f"{prefix}_source",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def _data_psalm_phase_effect_state(
        self,
        unit,
        *,
        prefix: str,
        default_source: str,
        game=None,
    ) -> tuple[object, dict | None, str]:
        root = self._attached_root(unit)
        if root is None:
            return None, None, ""
        sr = getattr(root, "special_rules", None)
        if not (isinstance(sr, dict) and bool(sr.get(f"{prefix}_active", False))):
            return root, None, ""
        if game is None:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(owner, "game", None) if owner is not None else None
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
        expected_phase = str(sr.get(f"{prefix}_expires_phase", "") or "").strip().upper()
        if expected_phase and phase_key and expected_phase != phase_key:
            self._clear_data_psalm_phase_effect(root, prefix)
            return root, None, ""
        try:
            effect_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        if effect_turn and current_turn and effect_turn != current_turn:
            self._clear_data_psalm_phase_effect(root, prefix)
            return root, None, ""
        current_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
        current_player_id = str(getattr(current_player, "id", "") or "")
        owner_id = str(sr.get(f"{prefix}_turn_owner", "") or "")
        if owner_id and current_player_id and owner_id != current_player_id:
            self._clear_data_psalm_phase_effect(root, prefix)
            return root, None, ""
        source = str(sr.get(f"{prefix}_source", "") or default_source).strip() or default_source
        return root, sr, source

    def data_psalm_remorseless_fist_wound_bonus(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or target_unit is None:
            return 0, ""
        if not self._weapon_is_attack_type(weapon_profile, "melee"):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        source_root = self._data_psalm_cult_mechanicus_root(attacker_unit)
        if source_root is None:
            return 0, ""
        _root, sr, source = self._data_psalm_phase_effect_state(
            source_root,
            prefix="data_psalm_remorseless_fist",
            default_source="CHANT OF THE REMORSELESS FIST",
            game=game,
        )
        if not isinstance(sr, dict):
            return 0, ""
        return 1, source

    def data_psalm_verse_of_vengeance_fight_on_death_rule(self, unit, *, model=None, game=None) -> Optional[dict]:
        source_root = self._data_psalm_cult_mechanicus_root(unit)
        if source_root is None:
            return None
        _root, sr, source = self._data_psalm_phase_effect_state(
            source_root,
            prefix="data_psalm_verse_of_vengeance",
            default_source="VERSE OF VENGEANCE",
            game=game,
        )
        if not isinstance(sr, dict):
            return None
        return {"threshold": 4, "source": source}

    @staticmethod
    def _objective_point_for_entry(entry):
        point = getattr(entry, "location", None)
        if point is None:
            point = entry
        if point is None:
            return None
        if not hasattr(point, "x") or not hasattr(point, "y"):
            return None
        return point

    def _collect_objective_entries(self, *, game=None, game_map=None) -> list:
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        if game_map is None:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            game_obj = getattr(owner, "game", None) if owner is not None else None
            if game is None:
                game = game_obj
            game_map = getattr(game_obj, "map", None) if game_obj is not None else None

        pool = []
        if game_map is not None:
            pool.extend(list(getattr(game_map, "objectives", []) or []))
        if game is not None:
            pool.extend(list(getattr(game, "objectives", []) or []))

        entries: list = []
        seen_ids: set[str] = set()
        for objective in pool:
            point = self._objective_point_for_entry(objective)
            if point is None or bool(getattr(point, "removed", False)):
                continue
            objective_id = str(get_entity_id(objective) or get_entity_id(point) or "")
            if not objective_id or objective_id in seen_ids:
                continue
            seen_ids.add(objective_id)
            entries.append((objective_id, objective, point))
        entries.sort(key=lambda item: str(item[0]))
        return entries

    def _objective_entry_by_id(self, objective_id: str, *, game=None, game_map=None):
        wanted = str(objective_id or "").strip()
        if not wanted:
            return None
        for entry in self._collect_objective_entries(game=game, game_map=game_map):
            if str(entry[0]) == wanted:
                return entry
        return None

    def clear_acquisition_objective(self) -> None:
        self.active_acquisition_objective_id = ""
        self.acquisition_selected_round = 0

    def can_select_acquisition_objective(self, *, game=None, battle_round: Optional[int] = None) -> bool:
        if not self.is_explorator_maniple():
            return False
        br = 0
        if battle_round is not None:
            try:
                br = int(battle_round or 0)
            except (TypeError, ValueError):
                br = 0
        elif game is not None:
            try:
                br = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                br = 0
        if br <= 0:
            return False
        if self.acquisition_selected_round == br and bool(str(self.active_acquisition_objective_id or "").strip()):
            return False
        return True

    def _pending_acquisition_request(self, game, army_id: str, *, battle_round: int):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._ACQUISITION_ABILITY_KEY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            try:
                req_round = int(ctx.get("battle_round", 0) or 0)
            except (TypeError, ValueError):
                req_round = 0
            if req_round != int(battle_round):
                continue
            return req
        return None

    def _build_acquisition_request(self, game, *, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        if game is None:
            return None
        owner = getattr(self.army, "player", None)
        if owner is None:
            return None
        entries = self._collect_objective_entries(game=game)
        if not entries:
            return None
        options = []
        objective_ids: list[str] = []
        for idx, (objective_id, objective, point) in enumerate(entries):
            objective_ids.append(str(objective_id))
            label = str(getattr(objective, "name", "") or f"Objective {idx + 1}")
            try:
                label = f"{label} ({float(getattr(point, 'x', 0.0)):.1f}, {float(getattr(point, 'y', 0.0)):.1f})"
            except (TypeError, ValueError):
                pass
            options.append(DecisionOption.create(label, payload={"objective_id": str(objective_id)}))
        if not options:
            return None

        army_id = self._entity_id(self.army)
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Acquisition At Any Cost: select one objective marker to be your Acquisition objective marker.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._ACQUISITION_ABILITY_KEY,
                "ability_name": self._ACQUISITION_SOURCE,
                "army_id": army_id,
                "battle_round": int(battle_round),
                "candidate_objective_ids": list(objective_ids),
                "optional": False,
            },
        )

    def _queue_acquisition_request(self, game, *, player, battle_round: int) -> None:
        if not self.is_explorator_maniple():
            return
        if game is None or player is None:
            return
        if player is not getattr(self.army, "player", None):
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return

        br = int(battle_round or 0)
        if br <= 0:
            return
        if self.acquisition_selected_round != br:
            self.clear_acquisition_objective()
        if not self.can_select_acquisition_objective(game=game, battle_round=br):
            return

        army_id = self._entity_id(self.army)
        if self._pending_acquisition_request(game, army_id, battle_round=br) is not None:
            return
        request = self._build_acquisition_request(game, battle_round=br)
        request_decision = getattr(game, "request_decision", None)
        if callable(request_decision) and request is not None:
            request_decision(request)

    def validate_acquisition_objective_choice(
        self,
        objective_id: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ) -> tuple[bool, str]:
        if not self.is_explorator_maniple():
            return False, "Acquisition At Any Cost requires an Explorator Maniple army."
        if self.army is None:
            return False, "Acquisition At Any Cost army not found."
        if player is not None:
            owner = getattr(self.army, "player", None)
            if owner is not None and owner is not player:
                return False, "Acquisition At Any Cost must be resolved by the owning player."
        objective_id = str(objective_id or "").strip()
        if not objective_id:
            return False, "Acquisition At Any Cost selection requires objective_id."
        if self._objective_entry_by_id(objective_id, game=game) is None:
            return False, "Acquisition At Any Cost selected objective marker was not found."

        expected_round = int(battle_round or 0)
        if expected_round and game is not None:
            try:
                current_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_round = 0
            if current_round and current_round != expected_round:
                return False, "Acquisition At Any Cost selection is no longer in the current battle round."
        if expected_round and self.acquisition_selected_round == expected_round and bool(
            str(self.active_acquisition_objective_id or "").strip()
        ):
            return False, "Acquisition At Any Cost has already been selected this Command phase."
        return True, ""

    def select_acquisition_objective(
        self,
        objective_id: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ):
        valid, reason = self.validate_acquisition_objective_choice(
            objective_id,
            game=game,
            player=player,
            battle_round=battle_round,
        )
        if not valid:
            return None
        entry = self._objective_entry_by_id(str(objective_id or "").strip(), game=game)
        if entry is None:
            return None
        objective_key, objective, _point = entry
        self.active_acquisition_objective_id = str(objective_key)
        if game is not None:
            try:
                self.acquisition_selected_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                self.acquisition_selected_round = int(battle_round or 0)
        else:
            self.acquisition_selected_round = int(battle_round or 0)
        return {
            "objective_id": str(objective_key),
            "objective_name": str(getattr(objective, "name", "") or "Objective marker"),
            "battle_round": int(self.acquisition_selected_round or 0),
            "source": self._ACQUISITION_SOURCE,
        }

    def _active_acquisition_objective_point(self, *, game=None, game_map=None):
        if not self.is_explorator_maniple():
            return None
        objective_id = str(self.active_acquisition_objective_id or "").strip()
        if not objective_id:
            return None
        entry = self._objective_entry_by_id(objective_id, game=game, game_map=game_map)
        if entry is None:
            return None
        _objective_id, objective, point = entry
        if point is None or bool(getattr(point, "removed", False)):
            return None
        return objective, point

    def acquisition_at_any_cost_wound_reroll_ones(
        self,
        attacker_model,
        *,
        target_unit=None,
        game=None,
        game_map=None,
    ) -> tuple[bool, str]:
        if not self.is_explorator_maniple():
            return False, ""
        if attacker_model is None or target_unit is None:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._attached_root(attacker_unit)
        if attacker_root is None or not self._unit_in_army(attacker_root):
            return False, ""
        if not self._unit_has_keyword_or_faction(attacker_root, "ADEPTUS MECHANICUS", faction_id=self.faction_id):
            return False, ""
        active = self._active_acquisition_objective_point(game=game, game_map=game_map)
        if not isinstance(active, tuple):
            return False, ""
        _objective, objective_point = active
        attacker_within = False
        is_within_attacker = getattr(attacker_root, "is_within_objective_range", None)
        if callable(is_within_attacker):
            attacker_within = bool(is_within_attacker(objective_point))
        target_root = self._attached_root(target_unit)
        target_within = False
        if target_root is not None:
            is_within_target = getattr(target_root, "is_within_objective_range", None)
            if callable(is_within_target):
                target_within = bool(is_within_target(objective_point))
        if attacker_within or target_within:
            return True, f"{self._ACQUISITION_SOURCE} (Acquisition objective)"
        return False, ""

    @staticmethod
    def _model_within_objective_range(model, objective_point) -> bool:
        if model is None or objective_point is None:
            return False
        try:
            from shapely.geometry import Point as _ShPoint
        except ImportError:
            _ShPoint = None
        if _ShPoint is not None:
            get_base_shape = getattr(model, "get_base_shape", None)
            base_shape = get_base_shape() if callable(get_base_shape) else None
            if base_shape is not None and hasattr(base_shape, "intersects"):
                try:
                    objective_area = _ShPoint(
                        float(getattr(objective_point, "x", 0.0) or 0.0),
                        float(getattr(objective_point, "y", 0.0) or 0.0),
                    ).buffer(float(getattr(objective_point, "control_radius", 0.0) or 0.0))
                except (TypeError, ValueError):
                    objective_area = None
                if objective_area is not None and base_shape.intersects(objective_area):
                    return True
        get_location = getattr(model, "get_location", None)
        location = get_location() if callable(get_location) else None
        if not location or len(location) < 2:
            return False
        try:
            x = float(location[0])
            y = float(location[1])
            ox = float(getattr(objective_point, "x", 0.0) or 0.0)
            oy = float(getattr(objective_point, "y", 0.0) or 0.0)
            radius = float(getattr(objective_point, "control_radius", 0.0) or 0.0)
        except (TypeError, ValueError):
            return False
        base_radius_fn = getattr(getattr(model, "model_base", None), "get_radius", None)
        base_radius = base_radius_fn() if callable(base_radius_fn) else 1.0
        try:
            base_radius = float(base_radius or 0.0)
        except (TypeError, ValueError):
            base_radius = 1.0
        return ((x - ox) ** 2 + (y - oy) ** 2) ** 0.5 <= float(radius + base_radius) + 1e-6

    def _unit_within_active_acquisition_objective(
        self,
        unit,
        *,
        game=None,
        game_map=None,
        require_army_membership: bool = False,
    ) -> bool:
        if not self.is_explorator_maniple():
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        if require_army_membership and not self._unit_in_army(root):
            return False
        active = self._active_acquisition_objective_point(game=game, game_map=game_map)
        if not isinstance(active, tuple):
            return False
        _objective, objective_point = active
        is_within = getattr(root, "is_within_objective_range", None)
        if not callable(is_within):
            return False
        return bool(is_within(objective_point))

    def explorator_unit_within_acquisition_objective(self, unit, *, game=None, game_map=None) -> bool:
        return self._unit_within_active_acquisition_objective(
            unit,
            game=game,
            game_map=game_map,
            require_army_membership=True,
        )

    def _iter_explorator_enhancement_sources(self, enhancement_flag_key: str) -> list[tuple]:
        if self.army is None:
            return []
        enhancement_key = str(enhancement_flag_key or "").strip()
        if not enhancement_key:
            return []
        sources: list[tuple] = []
        seen: set[tuple[str, str]] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None or not self._unit_in_army(root):
                continue
            if not self._unit_is_on_battlefield(root):
                continue
            root_id = self._entity_id(root) or str(id(root))
            members = list(getattr(root, "get_attached_unit_members", lambda: [])() or [])
            if not members:
                members = [root]
            for member in members:
                if member is None:
                    continue
                special_rules = getattr(member, "special_rules", None)
                if not isinstance(special_rules, dict) or not bool(special_rules.get(enhancement_key, False)):
                    continue
                get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                bearer = get_bearer() if callable(get_bearer) else None
                if bearer is None or not self._is_model_alive(bearer):
                    continue
                member_id = self._entity_id(member) or str(id(member))
                dedupe_key = (str(root_id), str(member_id))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                sources.append((str(root_id), root, member, special_rules, bearer))
        sources.sort(
            key=lambda item: (
                str(item[0] or ""),
                self._entity_id(item[2]) or str(id(item[2])),
            )
        )
        return sources

    def explorator_genetor_invulnerable_save(self, target_model, *, attack_type: str = "", game=None, game_map=None) -> tuple[int, str]:
        if not self.is_explorator_maniple():
            return 0, ""
        if target_model is None:
            return 0, ""
        target_unit = getattr(target_model, "parent_unit", None)
        target_root = self._attached_root(target_unit)
        if target_root is None or not self._unit_in_army(target_root):
            return 0, ""
        if not self._unit_is_on_battlefield(target_root):
            return 0, ""
        for _source_root_id, source_root, source_member, source_sr, _bearer in self._iter_explorator_enhancement_sources(
            "enhancement_explorator_genetor"
        ):
            if source_root is not target_root:
                continue
            requires_leading = bool(source_sr.get("enhancement_explorator_genetor_requires_bearer_leading", True))
            if requires_leading and not bool(getattr(source_member, "is_attached_leader", False)):
                continue
            requires_objective = bool(
                source_sr.get("enhancement_explorator_genetor_requires_unit_within_acquisition_objective", True)
            )
            if requires_objective and not self.explorator_unit_within_acquisition_objective(
                source_root,
                game=game,
                game_map=game_map,
            ):
                continue
            try:
                inv_value = int(source_sr.get("enhancement_explorator_genetor_invulnerable_save", 4) or 4)
            except (TypeError, ValueError):
                inv_value = 4
            if inv_value <= 0:
                continue
            source_name = str(
                source_sr.get("enhancement_explorator_genetor_source", "") or self._EXPLORATOR_GENETOR_SOURCE
            ).strip() or self._EXPLORATOR_GENETOR_SOURCE
            return int(inv_value), source_name
        return 0, ""

    def explorator_logis_hit_bonus(self, attacker_model, *, target_unit=None, game=None, game_map=None) -> tuple[int, str]:
        if not self.is_explorator_maniple():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._attached_root(attacker_unit)
        if attacker_root is None or not self._unit_in_army(attacker_root):
            return 0, ""
        if not self._unit_is_on_battlefield(attacker_root):
            return 0, ""
        target_root = self._attached_root(target_unit)
        if target_root is None:
            return 0, ""
        for _source_root_id, source_root, source_member, source_sr, _bearer in self._iter_explorator_enhancement_sources(
            "enhancement_explorator_logis"
        ):
            if source_root is not attacker_root:
                continue
            requires_leading = bool(source_sr.get("enhancement_explorator_logis_requires_bearer_leading", True))
            if requires_leading and not bool(getattr(source_member, "is_attached_leader", False)):
                continue
            requires_objective = bool(
                source_sr.get("enhancement_explorator_logis_requires_target_within_acquisition_objective", True)
            )
            if requires_objective and not self._unit_within_active_acquisition_objective(
                target_root,
                game=game,
                game_map=game_map,
                require_army_membership=False,
            ):
                continue
            try:
                bonus = int(source_sr.get("enhancement_explorator_logis_hit_bonus", 1) or 1)
            except (TypeError, ValueError):
                bonus = 1
            if bonus <= 0:
                continue
            source_name = str(
                source_sr.get("enhancement_explorator_logis_source", "") or self._EXPLORATOR_LOGIS_SOURCE
            ).strip() or self._EXPLORATOR_LOGIS_SOURCE
            return int(bonus), source_name
        return 0, ""

    def _resolve_explorator_magos_cp_gain(self, *, game=None, player=None) -> None:
        if not self.is_explorator_maniple():
            return
        if game is None or player is None or self.army is None:
            return
        if player is not getattr(self.army, "player", None):
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        active = self._active_acquisition_objective_point(game=game)
        if not isinstance(active, tuple):
            return
        _objective, objective_point = active
        for source_root_id, _source_root, _source_member, source_sr, bearer in self._iter_explorator_enhancement_sources(
            "enhancement_explorator_magos"
        ):
            if not self._model_within_objective_range(bearer, objective_point):
                continue
            try:
                roll_min = int(source_sr.get("enhancement_explorator_magos_roll_min", 4) or 4)
            except (TypeError, ValueError):
                roll_min = 4
            roll_min = int(max(2, min(6, roll_min)))
            try:
                cp_gain = int(source_sr.get("enhancement_explorator_magos_cp_gain", 1) or 1)
            except (TypeError, ValueError):
                cp_gain = 1
            cp_gain = int(max(0, cp_gain))
            if cp_gain <= 0:
                continue
            roll = int(get_roll("D6") or 0)
            if roll < roll_min:
                continue
            source_name = str(
                source_sr.get("enhancement_explorator_magos_source", "") or self._EXPLORATOR_MAGOS_SOURCE
            ).strip() or self._EXPLORATOR_MAGOS_SOURCE
            gain_cp = getattr(player, "gain_command_points", None)
            if not callable(gain_cp):
                continue
            gained = int(gain_cp(cp_gain, reason=source_name) or 0)
            if gained <= 0:
                continue
            event_system = getattr(game, "event_system", None)
            if event_system is not None:
                event_system.publish(
                    "command_points_gained",
                    player=player,
                    amount=int(gained),
                    reason=source_name,
                    source_unit_id=str(source_root_id or ""),
                    source_ability=self._EXPLORATOR_MAGOS_SOURCE,
                )

    def on_command_phase_end(self, *, game=None, player=None) -> None:
        if game is None or player is None:
            return
        if player is not getattr(self.army, "player", None):
            return
        if self.is_explorator_maniple():
            self._resolve_explorator_magos_cp_gain(game=game, player=player)

    @classmethod
    def _normalize_noospheric_override_choice_key(cls, choice_key: str) -> str:
        raw = str(choice_key or "").strip().upper()
        aliases = {
            "ELECTROMOTIVE": cls._NOOSPHERIC_ELECTROMOTIVE_KEY,
            "ELECTROMOTIVE_ENERGISATION": cls._NOOSPHERIC_ELECTROMOTIVE_KEY,
            "MICROACTUATOR": cls._NOOSPHERIC_MICROACTUATOR_KEY,
            "MICROACTUATOR_BRACING": cls._NOOSPHERIC_MICROACTUATOR_KEY,
            "PREDATION": cls._NOOSPHERIC_PREDATION_KEY,
            "PREDATION_PROTOCOLS": cls._NOOSPHERIC_PREDATION_KEY,
            "MUTED": cls._NOOSPHERIC_MUTED_KEY,
            "MUTED_SERVOMOTORS": cls._NOOSPHERIC_MUTED_KEY,
        }
        return aliases.get(raw, "")

    @classmethod
    def noospheric_override_choices(cls) -> tuple[tuple[str, str], ...]:
        return (
            (cls._NOOSPHERIC_ELECTROMOTIVE_KEY, "Electromotive Energisation"),
            (cls._NOOSPHERIC_MICROACTUATOR_KEY, "Microactuator Bracing"),
            (cls._NOOSPHERIC_PREDATION_KEY, "Predation Protocols"),
            (cls._NOOSPHERIC_MUTED_KEY, "Muted Servomotors"),
        )

    def _noospheric_max_selected_units(self, *, game=None) -> int:
        if game is None:
            owner = getattr(self.army, "player", None)
            game = getattr(owner, "game", None) if owner is not None else None
        size_value = getattr(getattr(game, "battlefield", None), "size", None) if game is not None else None
        size_key = str(getattr(size_value, "name", size_value) or "").strip().upper()
        if size_key == "INCURSION":
            return 1
        if size_key == "ONSLAUGHT":
            return 3
        return 2

    def _unit_is_on_battlefield_or_embarked(self, unit) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return True
        if getattr(unit, "embarked_in", None) is not None:
            return True
        if not bool(getattr(unit, "deployed", False)):
            return False
        return str(getattr(unit, "reserve_status", "deployed") or "deployed") == "deployed"

    def _unit_is_kastelan_robots(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        members = list(getattr(root, "get_attached_unit_members", lambda: [])() or [])
        if not members:
            members = [root]
        for member in members:
            if member is None:
                continue
            if self._unit_has_keyword(member, "KASTELAN ROBOTS"):
                return True
            name = str(getattr(member, "name", "") or "").strip().lower()
            if "kastelan robots" in name:
                return True
        return False

    def _iter_haloscreed_enhancement_sources(self, enhancement_flag_key: str) -> list[tuple]:
        if not self.is_haloscreed_battle_clade() or self.army is None:
            return []
        enhancement_key = str(enhancement_flag_key or "").strip()
        if not enhancement_key:
            return []
        sources: list[tuple] = []
        seen: set[tuple[str, str]] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None or not self._unit_in_army(root):
                continue
            if not self._unit_is_on_battlefield_or_embarked(root):
                continue
            root_id = self._entity_id(root) or str(id(root))
            members = list(getattr(root, "get_attached_unit_members", lambda: [])() or [])
            if not members:
                members = [root]
            for member in members:
                if member is None:
                    continue
                special_rules = getattr(member, "special_rules", None)
                if not isinstance(special_rules, dict) or not bool(special_rules.get(enhancement_key, False)):
                    continue
                get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                bearer = get_bearer() if callable(get_bearer) else None
                if bearer is None or not self._is_model_alive(bearer):
                    continue
                member_id = self._entity_id(member) or str(id(member))
                dedupe_key = (str(root_id), str(member_id))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                sources.append((str(root_id), root, member, special_rules, bearer))
        sources.sort(
            key=lambda item: (
                str(item[0] or ""),
                self._entity_id(item[2]) or str(id(item[2])),
            )
        )
        return sources

    def _haloscreed_transoracular_root_ids(self) -> set[str]:
        root_ids: set[str] = set()
        for source_root_id, source_root, source_member, source_sr, _bearer in self._iter_haloscreed_enhancement_sources(
            "enhancement_haloscreed_transoracular_dyad_wafers"
        ):
            requires_attached = bool(
                source_sr.get("enhancement_haloscreed_transoracular_requires_bearer_attached_to_kastelan_robots", True)
            )
            if requires_attached and not bool(getattr(source_member, "is_attached_leader", False)):
                continue
            if not self._unit_is_kastelan_robots(source_root):
                continue
            root_ids.add(str(source_root_id))
        return root_ids

    def _iter_noospheric_candidate_roots(self) -> list:
        if self.army is None:
            return []
        excluded_root_ids = self._haloscreed_transoracular_root_ids()
        seen: set[str] = set()
        roots: list = []
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root) or str(id(root))
            if root_id in seen:
                continue
            seen.add(root_id)
            if root_id in excluded_root_ids:
                continue
            if not self._unit_has_keyword_or_faction(root, "ADEPTUS MECHANICUS", faction_id=self.faction_id):
                continue
            if not self._unit_is_on_battlefield_or_embarked(root):
                continue
            roots.append(root)
        roots.sort(key=lambda item: self._entity_id(item) or str(getattr(item, "name", "") or ""))
        return roots

    def _pending_noospheric_request(self, game, army_id: str, *, ability_key: str, battle_round: int):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != str(ability_key or ""):
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            try:
                req_round = int(ctx.get("battle_round", 0) or 0)
            except (TypeError, ValueError):
                req_round = 0
            if req_round != int(battle_round):
                continue
            return req
        return None

    def _clear_noospheric_flags_on_army_units(self) -> None:
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            updated = dict(sr)
            updated.pop(self._NOOSPHERIC_ACTIVE_FLAG_KEY, None)
            updated.pop(self._NOOSPHERIC_SOURCE_FLAG_KEY, None)
            updated.pop(self._NOOSPHERIC_OVERRIDE_FLAG_KEY, None)
            root.special_rules = updated

    def _apply_noospheric_flags_to_selected_units(self) -> None:
        self._clear_noospheric_flags_on_army_units()
        selected_ids = {str(uid or "").strip() for uid in list(self.active_noospheric_unit_ids or []) if str(uid or "").strip()}
        transoracular_ids = self._haloscreed_transoracular_root_ids()
        active_halo_ids = set(selected_ids) | set(transoracular_ids)
        if not active_halo_ids:
            return
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = str(self._entity_id(root) or "").strip()
            if not root_id or root_id not in active_halo_ids:
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            updated = dict(sr)
            updated[self._NOOSPHERIC_ACTIVE_FLAG_KEY] = True
            if root_id in transoracular_ids and root_id not in selected_ids:
                updated[self._NOOSPHERIC_SOURCE_FLAG_KEY] = self._HALOSCREED_TRANSORACULAR_SOURCE
            else:
                updated[self._NOOSPHERIC_SOURCE_FLAG_KEY] = self._NOOSPHERIC_SOURCE
            if str(self.active_noospheric_override_key or "").strip():
                updated[self._NOOSPHERIC_OVERRIDE_FLAG_KEY] = str(self.active_noospheric_override_key)
            else:
                updated.pop(self._NOOSPHERIC_OVERRIDE_FLAG_KEY, None)
            root.special_rules = updated

    def clear_noospheric_transference_state(self) -> None:
        self.active_noospheric_unit_ids = []
        self.active_noospheric_override_key = ""
        self.noospheric_selected_round = 0
        self._clear_noospheric_flags_on_army_units()

    def can_select_noospheric_units(self, *, game=None, battle_round: Optional[int] = None) -> bool:
        if not self.is_haloscreed_battle_clade():
            return False
        br = 0
        if battle_round is not None:
            try:
                br = int(battle_round or 0)
            except (TypeError, ValueError):
                br = 0
        elif game is not None:
            try:
                br = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                br = 0
        if br <= 0:
            return False
        if self.noospheric_selected_round == br and list(self.active_noospheric_unit_ids or []):
            return False
        return True

    def _build_noospheric_unit_selection_request(self, game, *, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        if game is None:
            return None
        owner = getattr(self.army, "player", None)
        if owner is None:
            return None
        candidates = self._iter_noospheric_candidate_roots()
        if not candidates:
            return None
        max_count = min(self._noospheric_max_selected_units(game=game), len(candidates))
        if max_count <= 0:
            return None
        options = []
        for count in range(1, max_count + 1):
            for combo in combinations(candidates, count):
                unit_ids = [self._entity_id(unit) for unit in combo]
                if any(not unit_id for unit_id in unit_ids):
                    continue
                label = " + ".join(str(getattr(unit, "name", "Unit") or "Unit") for unit in combo)
                options.append(DecisionOption.create(label, payload={"selected_unit_ids": list(unit_ids)}))
        if not options:
            return None
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            (
                "Noospheric Transference: select one or more friendly ADEPTUS MECHANICUS units "
                "to gain HALO OVERRIDE until your next Command phase."
            ),
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._NOOSPHERIC_UNITS_ABILITY_KEY,
                "ability_name": self._NOOSPHERIC_SOURCE,
                "army_id": self._entity_id(self.army),
                "battle_round": int(battle_round),
                "candidate_unit_ids": [self._entity_id(unit) for unit in candidates if self._entity_id(unit)],
                "max_selections": int(max_count),
                "optional": False,
            },
        )

    def queue_noospheric_unit_selection_request(self, *, game=None, player=None, battle_round: int = 0):
        if not self.is_haloscreed_battle_clade():
            return None
        if self.army is None:
            return None
        owner = getattr(self.army, "player", None)
        if player is None:
            player = owner
        if player is None or (owner is not None and player is not owner):
            return None
        if game is None:
            game = getattr(player, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return None
        br = int(battle_round or 0)
        if br <= 0:
            return None
        if self.noospheric_selected_round != br:
            self.clear_noospheric_transference_state()
        if not self.can_select_noospheric_units(game=game, battle_round=br):
            return None
        army_id = self._entity_id(self.army)
        if self._pending_noospheric_request(
            game,
            army_id,
            ability_key=self._NOOSPHERIC_UNITS_ABILITY_KEY,
            battle_round=br,
        ) is not None:
            return None
        request = self._build_noospheric_unit_selection_request(game, battle_round=br)
        request_fn = getattr(game, "request_decision", None)
        if callable(request_fn) and request is not None:
            request_fn(request)
        return request

    def validate_noospheric_unit_selection(
        self,
        selected_unit_ids: list[str] | tuple[str, ...] | None,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ) -> tuple[bool, str]:
        if not self.is_haloscreed_battle_clade():
            return False, "Noospheric Transference requires Haloscreed Battle Clade detachment."
        if self.army is None:
            return False, "Noospheric Transference army not found."
        owner = getattr(self.army, "player", None)
        if player is not None and owner is not None and player is not owner:
            return False, "Noospheric Transference must be resolved by the owning player."
        selected_ids = [
            str(unit_id or "").strip()
            for unit_id in list(selected_unit_ids or [])
            if str(unit_id or "").strip()
        ]
        selected_ids = list(dict.fromkeys(selected_ids))
        if not selected_ids:
            return False, "Noospheric Transference requires selecting at least one unit."
        max_count = self._noospheric_max_selected_units(game=game)
        if len(selected_ids) > int(max_count):
            return False, f"Noospheric Transference can select at most {int(max_count)} unit(s) this battle size."
        valid_by_id = {self._entity_id(unit): unit for unit in self._iter_noospheric_candidate_roots() if self._entity_id(unit)}
        if any(unit_id not in valid_by_id for unit_id in selected_ids):
            return False, "Noospheric Transference selection includes ineligible units."
        expected_round = int(battle_round or 0)
        if expected_round and game is not None:
            try:
                current_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_round = 0
            if current_round and current_round != expected_round:
                return False, "Noospheric Transference selection is no longer in the current battle round."
        if expected_round and self.noospheric_selected_round == expected_round and list(self.active_noospheric_unit_ids or []):
            return False, "Noospheric Transference units have already been selected this Command phase."
        return True, ""

    def select_noospheric_unit_selection(
        self,
        selected_unit_ids: list[str] | tuple[str, ...] | None,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ):
        valid, reason = self.validate_noospheric_unit_selection(
            selected_unit_ids,
            game=game,
            player=player,
            battle_round=battle_round,
        )
        if not valid:
            return None
        valid_by_id = {self._entity_id(unit): unit for unit in self._iter_noospheric_candidate_roots() if self._entity_id(unit)}
        selected_ids = sorted(
            {
                str(unit_id or "").strip()
                for unit_id in list(selected_unit_ids or [])
                if str(unit_id or "").strip() and str(unit_id or "").strip() in valid_by_id
            }
        )
        if not selected_ids:
            return None
        self.active_noospheric_unit_ids = list(selected_ids)
        self.active_noospheric_override_key = ""
        if game is not None:
            try:
                self.noospheric_selected_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                self.noospheric_selected_round = int(battle_round or 0)
        else:
            self.noospheric_selected_round = int(battle_round or 0)
        self._apply_noospheric_flags_to_selected_units()
        return {
            "selected_unit_ids": list(selected_ids),
            "selected_unit_names": [str(getattr(valid_by_id[unit_id], "name", "Unit") or "Unit") for unit_id in selected_ids],
            "battle_round": int(self.noospheric_selected_round or 0),
            "source": self._NOOSPHERIC_SOURCE,
        }

    def _build_noospheric_override_request(self, game, *, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        if game is None or not list(self.active_noospheric_unit_ids or []):
            return None
        owner = getattr(self.army, "player", None)
        if owner is None:
            return None
        options = [
            DecisionOption.create(label, payload={"choice_key": key})
            for key, label in self.noospheric_override_choices()
        ]
        if not options:
            return None
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Noospheric Transference: select one HALO OVERRIDE ability to apply until your next Command phase.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._NOOSPHERIC_OVERRIDE_ABILITY_KEY,
                "ability_name": self._NOOSPHERIC_SOURCE,
                "army_id": self._entity_id(self.army),
                "battle_round": int(battle_round),
                "allowed_choice_keys": [key for key, _label in self.noospheric_override_choices()],
                "optional": False,
            },
        )

    def queue_noospheric_override_request(self, *, game=None, player=None, battle_round: int = 0):
        if not self.is_haloscreed_battle_clade():
            return None
        if self.army is None:
            return None
        owner = getattr(self.army, "player", None)
        if player is None:
            player = owner
        if player is None or (owner is not None and player is not owner):
            return None
        if game is None:
            game = getattr(player, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return None
        br = int(battle_round or 0)
        if br <= 0 or self.noospheric_selected_round != br:
            return None
        if not list(self.active_noospheric_unit_ids or []):
            return None
        if str(self.active_noospheric_override_key or "").strip():
            return None
        army_id = self._entity_id(self.army)
        if self._pending_noospheric_request(
            game,
            army_id,
            ability_key=self._NOOSPHERIC_OVERRIDE_ABILITY_KEY,
            battle_round=br,
        ) is not None:
            return None
        request = self._build_noospheric_override_request(game, battle_round=br)
        request_fn = getattr(game, "request_decision", None)
        if callable(request_fn) and request is not None:
            request_fn(request)
        return request

    def validate_noospheric_override_choice(
        self,
        choice_key: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ) -> tuple[bool, str]:
        if not self.is_haloscreed_battle_clade():
            return False, "Noospheric Transference requires Haloscreed Battle Clade detachment."
        if self.army is None:
            return False, "Noospheric Transference army not found."
        owner = getattr(self.army, "player", None)
        if player is not None and owner is not None and player is not owner:
            return False, "Noospheric Transference must be resolved by the owning player."
        if not list(self.active_noospheric_unit_ids or []):
            return False, "Noospheric Transference override requires selected HALO OVERRIDE units."
        expected_round = int(battle_round or 0)
        if expected_round <= 0:
            return False, "Noospheric Transference override requires current battle round context."
        if self.noospheric_selected_round != expected_round:
            return False, "Noospheric Transference override must be selected in the same Command phase."
        normalized = self._normalize_noospheric_override_choice_key(choice_key)
        if not normalized:
            return False, "Noospheric Transference override choice is not supported."
        return True, ""

    def select_noospheric_override_choice(
        self,
        choice_key: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ):
        valid, reason = self.validate_noospheric_override_choice(
            choice_key,
            game=game,
            player=player,
            battle_round=battle_round,
        )
        if not valid:
            return None
        normalized = self._normalize_noospheric_override_choice_key(choice_key)
        self.active_noospheric_override_key = normalized
        self._apply_noospheric_flags_to_selected_units()
        labels = {key: label for key, label in self.noospheric_override_choices()}
        return {
            "choice_key": str(normalized),
            "choice_label": str(labels.get(normalized, normalized.replace("_", " ").title())),
            "battle_round": int(self.noospheric_selected_round or 0),
            "source": self._NOOSPHERIC_SOURCE,
        }

    def _unit_has_halo_override_keyword(self, unit) -> bool:
        if not self.is_haloscreed_battle_clade():
            return False
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        root_id = str(self._entity_id(root) or "").strip()
        if not root_id:
            return False
        selected_ids = {str(uid or "").strip() for uid in list(self.active_noospheric_unit_ids or []) if str(uid or "").strip()}
        if root_id in selected_ids:
            return True
        return root_id in self._haloscreed_transoracular_root_ids()

    def _unit_selected_for_noospheric(self, unit) -> bool:
        return self._unit_has_halo_override_keyword(unit)

    def _noospheric_override_active(self, choice_key: str) -> bool:
        if not self.is_haloscreed_battle_clade():
            return False
        normalized = self._normalize_noospheric_override_choice_key(choice_key)
        if not normalized:
            return False
        if not list(self.active_noospheric_unit_ids or []):
            return False
        return str(self.active_noospheric_override_key or "").strip().upper() == normalized

    def noospheric_transference_movement_bonus(self, model, *, unit=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        if not self._noospheric_override_active(self._NOOSPHERIC_ELECTROMOTIVE_KEY):
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        if not self._unit_selected_for_noospheric(source_unit):
            return 0, ""
        return 2, f"{self._NOOSPHERIC_SOURCE} (Electromotive Energisation)"

    def noospheric_transference_toughness_bonus(self, model, *, unit=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        if not self._noospheric_override_active(self._NOOSPHERIC_MICROACTUATOR_KEY):
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        if not self._unit_selected_for_noospheric(source_unit):
            return 0, ""
        return 1, f"{self._NOOSPHERIC_SOURCE} (Microactuator Bracing)"

    def noospheric_transference_charge_after_advance_applies(self, unit, *, game=None) -> bool:
        _ = game
        if not self._noospheric_override_active(self._NOOSPHERIC_PREDATION_KEY):
            return False
        return self._unit_selected_for_noospheric(unit)

    def noospheric_transference_stealth_applies(self, unit, *, game=None) -> bool:
        _ = game
        if not self._noospheric_override_active(self._NOOSPHERIC_MUTED_KEY):
            return False
        return self._unit_selected_for_noospheric(unit)

    def haloscreed_transoracular_halo_override_applies(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        root_id = str(self._entity_id(root) or "").strip()
        if not root_id:
            return False
        return root_id in self._haloscreed_transoracular_root_ids()

    def haloscreed_cognitive_reinforcement_applies(self, unit) -> bool:
        if not self.is_haloscreed_battle_clade():
            return False
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        root_id = str(self._entity_id(root) or "").strip()
        if not root_id:
            return False
        for source_root_id, _source_root, _source_member, _source_sr, _bearer in self._iter_haloscreed_enhancement_sources(
            "enhancement_haloscreed_cognitive_reinforcement"
        ):
            if str(source_root_id or "") == root_id:
                return True
        return False

    def haloscreed_sanctified_ordnance_range_bonus(self, attacker_model, *, weapon_profile=None) -> tuple[int, str]:
        if not self.is_haloscreed_battle_clade():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        if weapon_profile is not None and not self._weapon_is_attack_type(weapon_profile, "ranged"):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._attached_root(attacker_unit)
        if attacker_root is None or not self._unit_in_army(attacker_root):
            return 0, ""
        if not self._unit_is_on_battlefield_or_embarked(attacker_root):
            return 0, ""
        attacker_root_id = str(self._entity_id(attacker_root) or "").strip()
        if not attacker_root_id:
            return 0, ""
        best_bonus = 0
        best_source = ""
        for source_root_id, _source_root, _source_member, source_sr, _bearer in self._iter_haloscreed_enhancement_sources(
            "enhancement_haloscreed_sanctified_ordnance"
        ):
            if str(source_root_id or "") != attacker_root_id:
                continue
            try:
                range_bonus = int(source_sr.get("enhancement_haloscreed_sanctified_ordnance_range_bonus", 6) or 6)
            except (TypeError, ValueError):
                range_bonus = 6
            range_bonus = int(max(0, range_bonus))
            if range_bonus <= 0:
                continue
            if range_bonus > best_bonus:
                best_bonus = int(range_bonus)
                best_source = str(
                    source_sr.get("enhancement_haloscreed_sanctified_ordnance_source", "")
                    or self._HALOSCREED_SANCTIFIED_SOURCE
                ).strip() or self._HALOSCREED_SANCTIFIED_SOURCE
        if best_bonus <= 0:
            return 0, ""
        return int(best_bonus), str(best_source or self._HALOSCREED_SANCTIFIED_SOURCE)

    def haloscreed_sanctified_ordnance_hazardous_reroll_rule(
        self,
        unit,
        *,
        dice_count: int = 1,
    ) -> dict | None:
        if not self.is_haloscreed_battle_clade():
            return None
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return None
        if not self._unit_is_on_battlefield_or_embarked(root):
            return None
        root_id = str(self._entity_id(root) or "").strip()
        if not root_id:
            return None
        max_select = int(max(1, int(dice_count or 1)))
        for source_root_id, _source_root, _source_member, source_sr, _bearer in self._iter_haloscreed_enhancement_sources(
            "enhancement_haloscreed_sanctified_ordnance"
        ):
            if str(source_root_id or "") != root_id:
                continue
            if not bool(source_sr.get("enhancement_haloscreed_sanctified_ordnance_hazardous_reroll", True)):
                continue
            source_name = str(
                source_sr.get("enhancement_haloscreed_sanctified_ordnance_source", "")
                or self._HALOSCREED_SANCTIFIED_SOURCE
            ).strip() or self._HALOSCREED_SANCTIFIED_SOURCE
            return {
                "action_id": "haloscreed_sanctified_ordnance_hazardous_reroll",
                "label": f"{source_name} Hazardous re-roll",
                "mode": "select",
                "allow_success": True,
                "max_select": int(max_select),
                "source": source_name,
            }
        return None

    def haloscreed_inloaded_lethality_melee_bonuses(self, attacker_model, *, weapon_profile=None) -> tuple[int, int, str]:
        if not self.is_haloscreed_battle_clade():
            return 0, 0, ""
        if attacker_model is None:
            return 0, 0, ""
        if weapon_profile is not None and not self._weapon_is_attack_type(weapon_profile, "melee"):
            return 0, 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._attached_root(attacker_unit)
        if attacker_root is None or not self._unit_in_army(attacker_root):
            return 0, 0, ""
        if not self._unit_is_on_battlefield_or_embarked(attacker_root):
            return 0, 0, ""
        attacker_root_id = str(self._entity_id(attacker_root) or "").strip()
        attacker_model_id = str(getattr(attacker_model, "id", getattr(attacker_model, "_id", "")) or "").strip()
        if not attacker_root_id or not attacker_model_id:
            return 0, 0, ""
        for source_root_id, _source_root, source_member, source_sr, _bearer in self._iter_haloscreed_enhancement_sources(
            "enhancement_haloscreed_inloaded_lethality"
        ):
            if str(source_root_id or "") != attacker_root_id:
                continue
            bearer_id = str(
                source_sr.get("enhancement_haloscreed_inloaded_lethality_bearer_model_id", "")
                or source_sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            if not bearer_id:
                get_bearer = getattr(source_member, "_get_enhancement_bearer_model", None)
                bearer = get_bearer() if callable(get_bearer) else None
                bearer_id = str(getattr(bearer, "id", getattr(bearer, "_id", "")) or "").strip() if bearer is not None else ""
            if not bearer_id or bearer_id != attacker_model_id:
                continue
            try:
                attacks_bonus = int(source_sr.get("enhancement_haloscreed_inloaded_lethality_attacks_bonus", 3) or 3)
            except (TypeError, ValueError):
                attacks_bonus = 3
            try:
                damage_bonus = int(source_sr.get("enhancement_haloscreed_inloaded_lethality_damage_bonus", 1) or 1)
            except (TypeError, ValueError):
                damage_bonus = 1
            attacks_bonus = int(max(0, attacks_bonus))
            damage_bonus = int(max(0, damage_bonus))
            if attacks_bonus <= 0 and damage_bonus <= 0:
                continue
            source_name = str(
                source_sr.get("enhancement_haloscreed_inloaded_lethality_source", "")
                or self._HALOSCREED_INLOADED_SOURCE
            ).strip() or self._HALOSCREED_INLOADED_SOURCE
            return int(attacks_bonus), int(damage_bonus), source_name
        return 0, 0, ""

    def _iter_skitarii_enhancement_sources(self, enhancement_flag_key: str) -> list[tuple]:
        if not self.is_skitarii_hunter_cohort() or self.army is None:
            return []
        enhancement_key = str(enhancement_flag_key or "").strip()
        if not enhancement_key:
            return []
        sources: list[tuple] = []
        seen: set[tuple[str, str]] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None or not self._unit_in_army(root):
                continue
            if not self._unit_is_on_battlefield_or_embarked(root):
                continue
            root_id = self._entity_id(root) or str(id(root))
            members = list(getattr(root, "get_attached_unit_members", lambda: [])() or [])
            if not members:
                members = [root]
            for member in members:
                if member is None:
                    continue
                special_rules = getattr(member, "special_rules", None)
                if not isinstance(special_rules, dict) or not bool(special_rules.get(enhancement_key, False)):
                    continue
                get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                bearer = get_bearer() if callable(get_bearer) else None
                if bearer is None or not self._is_model_alive(bearer):
                    continue
                member_id = self._entity_id(member) or str(id(member))
                dedupe_key = (str(root_id), str(member_id))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                sources.append((str(root_id), root, member, special_rules, bearer))
        sources.sort(
            key=lambda item: (
                str(item[0] or ""),
                self._entity_id(item[2]) or str(id(item[2])),
            )
        )
        return sources

    def _clear_skitarii_cantic_thrallnet_source_assignment(self, source_root_id: str) -> None:
        source_id = str(source_root_id or "").strip()
        if not source_id or self.army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root) or str(id(root))
            if root_id in seen:
                continue
            seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if str(sr.get(self._SKITARII_CANTIC_THRALLNET_SOURCE_UNIT_ID_KEY, "") or "").strip() != source_id:
                continue
            updated = dict(sr)
            for key in (
                self._SKITARII_CANTIC_THRALLNET_ACTIVE_KEY,
                self._SKITARII_CANTIC_THRALLNET_SOURCE_UNIT_ID_KEY,
                self._SKITARII_CANTIC_THRALLNET_SOURCE_NAME_KEY,
                self._SKITARII_CANTIC_THRALLNET_STARTED_ROUND_KEY,
                self._SKITARII_CANTIC_THRALLNET_EXPIRES_ROUND_KEY,
            ):
                updated.pop(key, None)
            root.special_rules = updated

    def _clear_expired_skitarii_cantic_thrallnet_state(self, *, game=None, battle_round: int = 0) -> None:
        if self.army is None:
            return
        current_round = int(battle_round or 0)
        if current_round <= 0 and game is not None:
            try:
                current_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_round = 0
        if current_round <= 0:
            return
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root) or str(id(root))
            if root_id in seen:
                continue
            seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(self._SKITARII_CANTIC_THRALLNET_ACTIVE_KEY, False)):
                continue
            try:
                expires_round = int(sr.get(self._SKITARII_CANTIC_THRALLNET_EXPIRES_ROUND_KEY, 0) or 0)
            except (TypeError, ValueError):
                expires_round = 0
            if expires_round > int(current_round):
                continue
            updated = dict(sr)
            for key in (
                self._SKITARII_CANTIC_THRALLNET_ACTIVE_KEY,
                self._SKITARII_CANTIC_THRALLNET_SOURCE_UNIT_ID_KEY,
                self._SKITARII_CANTIC_THRALLNET_SOURCE_NAME_KEY,
                self._SKITARII_CANTIC_THRALLNET_STARTED_ROUND_KEY,
                self._SKITARII_CANTIC_THRALLNET_EXPIRES_ROUND_KEY,
            ):
                updated.pop(key, None)
            root.special_rules = updated

    def _pending_skitarii_cantic_thrallnet_request(self, game, *, source_root_id: str, battle_round: int):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._SKITARII_CANTIC_THRALLNET_ABILITY_KEY:
                continue
            if str(ctx.get("source_unit_id", "") or "") != str(source_root_id or ""):
                continue
            try:
                req_round = int(ctx.get("battle_round", 0) or 0)
            except (TypeError, ValueError):
                req_round = 0
            if req_round != int(battle_round):
                continue
            return req
        return None

    def _skitarii_cantic_thrallnet_candidate_roots(self, *, source_bearer, source_sr, game=None) -> list:
        del game
        if source_bearer is None:
            return []
        owner = getattr(self.army, "player", None)
        if owner is None:
            return []
        try:
            range_inches = float(source_sr.get("enhancement_skitarii_cantic_thrallnet_range", 12.0) or 12.0)
        except (TypeError, ValueError):
            range_inches = 12.0
        range_inches = float(max(0.0, range_inches))
        required_keywords = [
            str(kw or "").strip().upper()
            for kw in list(source_sr.get("enhancement_skitarii_cantic_thrallnet_required_target_keywords", ["SKITARII"]) or ["SKITARII"])
            if str(kw or "").strip()
        ]
        if not required_keywords:
            required_keywords = ["SKITARII"]
        from ..utility.aura_utils import model_within_range_of_unit

        candidates: list = []
        for root in self._iter_player_unit_roots(owner):
            if root is None or not self._unit_in_army(root):
                continue
            if not self._unit_is_on_battlefield(root):
                continue
            if not all(self._unit_has_keyword(root, keyword) for keyword in required_keywords):
                continue
            if not model_within_range_of_unit(source_bearer, root, range_inches, use_attached_aggregate=True):
                continue
            candidates.append(root)
        candidates.sort(key=lambda item: self._entity_id(item) or str(getattr(item, "name", "") or ""))
        return candidates

    def _build_skitarii_cantic_thrallnet_request(self, game, *, source_root, source_member, source_sr, bearer, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        if game is None or source_root is None or source_member is None or bearer is None:
            return None
        owner = getattr(self.army, "player", None)
        if owner is None:
            return None
        source_root_id = self._entity_id(source_root)
        source_member_id = self._entity_id(source_member)
        if not source_root_id:
            return None
        candidates = self._skitarii_cantic_thrallnet_candidate_roots(
            source_bearer=bearer,
            source_sr=source_sr,
            game=game,
        )
        if not candidates:
            return None
        source_name = str(
            source_sr.get("enhancement_skitarii_cantic_thrallnet_source", "")
            or self._SKITARII_CANTIC_THRALLNET_SOURCE
        ).strip() or self._SKITARII_CANTIC_THRALLNET_SOURCE
        options = [DecisionOption.create("None", payload={"action": "skip"})]
        for target in candidates:
            target_id = self._entity_id(target)
            if not target_id:
                continue
            target_name = str(getattr(target, "name", "Unit") or "Unit")
            options.append(
                DecisionOption.create(
                    target_name,
                    payload={
                        "source_unit_id": source_root_id,
                        "source_member_unit_id": source_member_id,
                        "target_unit_id": target_id,
                    },
                )
            )
        if len(options) <= 1:
            return None
        try:
            range_inches = int(float(source_sr.get("enhancement_skitarii_cantic_thrallnet_range", 12.0) or 12.0))
        except (TypeError, ValueError):
            range_inches = 12
        prompt = (
            f"{source_name}: select one friendly SKITARII unit within {int(max(0, range_inches))}\" of the bearer "
            "to treat Protector and Conqueror Imperatives as active until the start of your next battle round (or None)."
        )
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            prompt,
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._SKITARII_CANTIC_THRALLNET_ABILITY_KEY,
                "ability_name": source_name,
                "army_id": self._entity_id(self.army),
                "source_unit_id": source_root_id,
                "source_member_unit_id": source_member_id,
                "battle_round": int(battle_round),
                "candidate_unit_ids": [self._entity_id(target) for target in candidates if self._entity_id(target)],
                "optional": True,
            },
        )

    def _queue_skitarii_cantic_thrallnet_requests(self, game, *, player, battle_round: int) -> None:
        if not self.is_skitarii_hunter_cohort() or self.army is None:
            return
        if game is None or player is None:
            return
        owner = getattr(self.army, "player", None)
        if owner is None or player is not owner:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        request_decision = getattr(game, "request_decision", None)
        if not callable(request_decision):
            return
        for source_root_id, source_root, source_member, source_sr, bearer in self._iter_skitarii_enhancement_sources(
            "enhancement_skitarii_cantic_thrallnet"
        ):
            if not self._unit_is_on_battlefield(source_root):
                continue
            if self._pending_skitarii_cantic_thrallnet_request(
                game,
                source_root_id=source_root_id,
                battle_round=int(battle_round),
            ) is not None:
                continue
            request = self._build_skitarii_cantic_thrallnet_request(
                game,
                source_root=source_root,
                source_member=source_member,
                source_sr=source_sr,
                bearer=bearer,
                battle_round=int(battle_round),
            )
            if request is not None:
                request_decision(request)

    def _resolve_skitarii_cantic_thrallnet_source(self, source_unit_id: str):
        wanted_id = str(source_unit_id or "").strip()
        if not wanted_id:
            return None
        for root_id, source_root, source_member, source_sr, bearer in self._iter_skitarii_enhancement_sources(
            "enhancement_skitarii_cantic_thrallnet"
        ):
            if str(root_id or "").strip() == wanted_id:
                return source_root, source_member, source_sr, bearer
        return None

    def validate_skitarii_cantic_thrallnet_choice(
        self,
        source_unit_id: str,
        target_unit_id: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
        candidate_ids: list[str] | tuple[str, ...] | None = None,
    ) -> tuple[bool, str]:
        if not self.is_skitarii_hunter_cohort():
            return False, "Cantic Thrallnet requires Skitarii Hunter Cohort detachment."
        if self.army is None:
            return False, "Cantic Thrallnet army not found."
        owner = getattr(self.army, "player", None)
        if player is not None and owner is not None and player is not owner:
            return False, "Cantic Thrallnet must be resolved by the owning player."
        source_id = str(source_unit_id or "").strip()
        target_id = str(target_unit_id or "").strip()
        if not source_id or not target_id:
            return False, "Cantic Thrallnet requires both source and target unit ids."
        resolved_source = self._resolve_skitarii_cantic_thrallnet_source(source_id)
        if resolved_source is None:
            return False, "Cantic Thrallnet source unit is not available."
        source_root, _source_member, source_sr, bearer = resolved_source
        if source_root is None or bearer is None:
            return False, "Cantic Thrallnet source bearer is not available."
        if not self._unit_is_on_battlefield(source_root):
            return False, "Cantic Thrallnet source unit must be on the battlefield."
        allowed_ids = {
            str(unit_id or "").strip()
            for unit_id in list(candidate_ids or [])
            if str(unit_id or "").strip()
        }
        if allowed_ids and target_id not in allowed_ids:
            return False, "Cantic Thrallnet target is not an eligible candidate for this request."
        candidates = self._skitarii_cantic_thrallnet_candidate_roots(
            source_bearer=bearer,
            source_sr=source_sr,
            game=game,
        )
        valid_ids = {self._entity_id(unit) for unit in candidates if self._entity_id(unit)}
        if target_id not in valid_ids:
            return False, "Cantic Thrallnet target must be a friendly SKITARII unit within range of the bearer."
        expected_round = int(battle_round or 0)
        if expected_round > 0 and game is not None:
            try:
                current_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_round = 0
            if current_round > 0 and current_round != expected_round:
                return False, "Cantic Thrallnet selection is no longer in the current battle round."
        return True, ""

    def select_skitarii_cantic_thrallnet_choice(
        self,
        source_unit_id: str,
        target_unit_id: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
        candidate_ids: list[str] | tuple[str, ...] | None = None,
    ):
        valid, _reason = self.validate_skitarii_cantic_thrallnet_choice(
            source_unit_id,
            target_unit_id,
            game=game,
            player=player,
            battle_round=battle_round,
            candidate_ids=candidate_ids,
        )
        if not valid:
            return None
        resolved_source = self._resolve_skitarii_cantic_thrallnet_source(source_unit_id)
        if resolved_source is None:
            return None
        source_root, _source_member, source_sr, _bearer = resolved_source
        candidates = self._skitarii_cantic_thrallnet_candidate_roots(
            source_bearer=resolved_source[3],
            source_sr=source_sr,
            game=game,
        )
        candidates_by_id = {self._entity_id(unit): unit for unit in candidates if self._entity_id(unit)}
        target_id = str(target_unit_id or "").strip()
        target_root = candidates_by_id.get(target_id)
        if target_root is None:
            return None
        source_root_id = self._entity_id(source_root)
        if not source_root_id:
            return None
        self._clear_skitarii_cantic_thrallnet_source_assignment(source_root_id)
        current_round = int(battle_round or 0)
        if game is not None:
            try:
                current_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_round = int(battle_round or 0)
        if current_round <= 0:
            current_round = int(battle_round or 1)
        source_name = str(
            source_sr.get("enhancement_skitarii_cantic_thrallnet_source", "")
            or self._SKITARII_CANTIC_THRALLNET_SOURCE
        ).strip() or self._SKITARII_CANTIC_THRALLNET_SOURCE
        target_sr = getattr(target_root, "special_rules", None)
        if not isinstance(target_sr, dict):
            target_sr = {}
        target_sr = dict(target_sr)
        target_sr[self._SKITARII_CANTIC_THRALLNET_ACTIVE_KEY] = True
        target_sr[self._SKITARII_CANTIC_THRALLNET_SOURCE_UNIT_ID_KEY] = str(source_root_id)
        target_sr[self._SKITARII_CANTIC_THRALLNET_SOURCE_NAME_KEY] = source_name
        target_sr[self._SKITARII_CANTIC_THRALLNET_STARTED_ROUND_KEY] = int(current_round)
        target_sr[self._SKITARII_CANTIC_THRALLNET_EXPIRES_ROUND_KEY] = int(current_round + 1)
        target_root.special_rules = target_sr
        return {
            "source_unit_id": str(source_root_id),
            "source_unit_name": str(getattr(source_root, "name", "Unit") or "Unit"),
            "target_unit_id": str(target_id),
            "target_unit_name": str(getattr(target_root, "name", "Unit") or "Unit"),
            "source": source_name,
            "battle_round": int(current_round),
            "expires_round": int(current_round + 1),
        }

    def skitarii_cantic_thrallnet_applies(self, unit, *, game=None) -> bool:
        if not self.is_skitarii_hunter_cohort():
            return False
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(self._SKITARII_CANTIC_THRALLNET_ACTIVE_KEY, False)):
            return False
        try:
            expires_round = int(sr.get(self._SKITARII_CANTIC_THRALLNET_EXPIRES_ROUND_KEY, 0) or 0)
        except (TypeError, ValueError):
            expires_round = 0
        if expires_round <= 0:
            return False
        if game is None:
            owner = getattr(self.army, "player", None)
            game = getattr(owner, "game", None) if owner is not None else None
        if game is None:
            return True
        try:
            current_round = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_round = 0
        if current_round > 0 and current_round >= expires_round:
            updated = dict(sr)
            for key in (
                self._SKITARII_CANTIC_THRALLNET_ACTIVE_KEY,
                self._SKITARII_CANTIC_THRALLNET_SOURCE_UNIT_ID_KEY,
                self._SKITARII_CANTIC_THRALLNET_SOURCE_NAME_KEY,
                self._SKITARII_CANTIC_THRALLNET_STARTED_ROUND_KEY,
                self._SKITARII_CANTIC_THRALLNET_EXPIRES_ROUND_KEY,
            ):
                updated.pop(key, None)
            root.special_rules = updated
            return False
        return True

    def skitarii_battle_sphere_uplink_reactive_move(
        self,
        unit,
        *,
        game=None,
        is_engaged: Optional[bool] = None,
    ) -> tuple[int, str]:
        if not self.is_skitarii_hunter_cohort():
            return 0, ""
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return 0, ""
        if not self._unit_is_on_battlefield(root):
            return 0, ""
        root_id = str(self._entity_id(root) or "").strip()
        if not root_id:
            return 0, ""
        engaged = bool(is_engaged) if is_engaged is not None else False
        if is_engaged is None and game is not None:
            game_map = getattr(game, "map", None)
            if game_map is not None:
                for enemy in list(getattr(game_map, "get_enemy_units", lambda *_a, **_k: [])(root) or []):
                    if enemy is None:
                        continue
                    if hasattr(enemy, "is_alive") and callable(enemy.is_alive) and not enemy.is_alive():
                        continue
                    if bool(getattr(enemy, "is_embarked", False)) or getattr(enemy, "embarked_in", None) is not None:
                        continue
                    if bool(getattr(enemy, "deployed", False)) is False:
                        continue
                    try:
                        if game_map.is_within_engagement_range(root, enemy):
                            engaged = True
                            break
                    except (AttributeError, TypeError, ValueError):
                        continue
        for source_root_id, _source_root, _source_member, source_sr, _bearer in self._iter_skitarii_enhancement_sources(
            "enhancement_skitarii_battle_sphere_uplink"
        ):
            if str(source_root_id or "").strip() != root_id:
                continue
            if bool(source_sr.get("enhancement_skitarii_battle_sphere_uplink_requires_not_engagement_range", True)) and engaged:
                return 0, ""
            try:
                move_range = int(source_sr.get("enhancement_skitarii_battle_sphere_uplink_move_range", 6) or 6)
            except (TypeError, ValueError):
                move_range = 6
            if move_range <= 0:
                continue
            source_name = str(
                source_sr.get("enhancement_skitarii_battle_sphere_uplink_source", "")
                or self._SKITARII_BATTLE_SPHERE_UPLINK_SOURCE
            ).strip() or self._SKITARII_BATTLE_SPHERE_UPLINK_SOURCE
            return int(move_range), source_name
        return 0, ""

    def _unit_is_ironstrider_ballistarii(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "IRONSTRIDER BALLISTARII"):
            return True
        name = str(getattr(unit, "name", "") or "").strip().lower()
        return "ironstrider ballistarii" in name

    def _unit_is_skitarii_hunter_stealth_eligible(self, unit) -> bool:
        if unit is None:
            return False
        has_skitarii = self._unit_has_keyword(unit, "SKITARII")
        has_infantry_or_mounted = self._unit_has_keyword(unit, "INFANTRY") or self._unit_has_keyword(unit, "MOUNTED")
        if has_skitarii and has_infantry_or_mounted:
            return True
        return self._unit_is_ironstrider_ballistarii(unit)

    def stealth_optimisation_stealth_applies(self, unit) -> bool:
        if not self.is_skitarii_hunter_cohort():
            return False
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        return self._unit_is_skitarii_hunter_stealth_eligible(root)

    def stealth_optimisation_benefit_of_cover(
        self,
        target_model,
        *,
        attacker_model=None,
        attack_type: str = "",
        game=None,
    ) -> tuple[bool, str]:
        _ = game
        if not self.is_skitarii_hunter_cohort():
            return False, ""
        if str(attack_type or "").strip().lower() not in ("", "ranged"):
            return False, ""
        if target_model is None or attacker_model is None:
            return False, ""
        target_unit = getattr(target_model, "parent_unit", None)
        target_root = self._attached_root(target_unit)
        if target_root is None or not self._unit_in_army(target_root):
            return False, ""
        has_sicarian_keyword = self._unit_has_keyword(target_root, "SICARIAN")
        target_name = str(getattr(target_root, "name", "") or "").strip().lower()
        if not has_sicarian_keyword and "sicarian" not in target_name:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._attached_root(attacker_unit)
        if attacker_root is not None and self._unit_in_army(attacker_root):
            return False, ""
        from ..utility.aura_utils import model_within_range_of_unit

        if model_within_range_of_unit(attacker_model, target_root, 12.0, use_attached_aggregate=True):
            return False, ""
        return True, f"{self._STEALTH_OPTIMISATION_SOURCE} (Sicarian cover beyond 12\")"

    def emanatus_force_field_invulnerable_save(
        self,
        target_model,
        *,
        attack_type: str = "",
        game_map=None,
    ) -> tuple[int, str]:
        del game_map
        if str(attack_type or "").strip().lower() != "ranged":
            return 0, ""
        if target_model is None or not self._is_model_alive(target_model):
            return 0, ""

        target_unit = getattr(target_model, "parent_unit", None)
        target_root = self._attached_root(target_unit)
        if target_root is None or not self._unit_in_army(target_root):
            return 0, ""
        if not self._unit_is_on_battlefield(target_root):
            return 0, ""
        if not self._unit_has_keyword(target_root, "BATTLELINE"):
            return 0, ""
        if not self._unit_has_keyword_or_faction(target_root, "ADEPTUS MECHANICUS", faction_id=self.faction_id):
            return 0, ""

        from ..utility.aura_utils import model_wholly_within_range_of_unit

        seen: set[str] = set()
        source_roots: list = []
        for unit in list(getattr(self.army, "units", []) or []):
            source_root = self._attached_root(unit)
            if source_root is None:
                continue
            source_id = self._entity_id(source_root) or str(id(source_root))
            if source_id in seen:
                continue
            seen.add(source_id)
            source_roots.append(source_root)
        source_roots.sort(key=lambda item: self._entity_id(item) or str(getattr(item, "name", "") or ""))

        best_value = 0
        best_source = ""
        for source_root in source_roots:
            if source_root is None or not self._unit_is_on_battlefield(source_root):
                continue
            get_rule = getattr(source_root, "get_emanatus_force_field_rule", None)
            if not callable(get_rule):
                continue
            rule = get_rule()
            if not isinstance(rule, dict):
                continue
            if bool(rule.get("target_requires_battleline", False)) and not self._unit_has_keyword(target_root, "BATTLELINE"):
                continue
            target_keyword = str(rule.get("target_keyword", "") or "").strip().upper()
            if target_keyword and not self._unit_has_keyword_or_faction(target_root, target_keyword, faction_id=self.faction_id):
                continue
            try:
                range_value = int(rule.get("range", 0) or 0)
            except Exception:
                range_value = 0
            try:
                inv_value = int(rule.get("invulnerable_save", 0) or 0)
            except Exception:
                inv_value = 0
            if range_value <= 0 or inv_value <= 0:
                continue
            if not model_wholly_within_range_of_unit(
                source_root,
                target_model,
                float(range_value),
                use_attached_aggregate=True,
            ):
                continue
            if best_value <= 0 or int(inv_value) < int(best_value):
                best_value = int(inv_value)
                best_source = str(rule.get("source", "") or "Emanatus Force Field").strip() or "Emanatus Force Field"

        if best_value <= 0:
            return 0, ""
        return int(best_value), str(best_source or "Emanatus Force Field")

    def _iter_player_unit_roots(self, player) -> list:
        if player is None:
            return []
        get_army = getattr(player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(player, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        roots: list = []
        for unit in list(getattr(army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root) or str(id(root))
            if root_id in seen:
                continue
            seen.add(root_id)
            roots.append(root)
        roots.sort(key=lambda item: self._entity_id(item) or str(getattr(item, "name", "") or ""))
        return roots

    def _unit_is_on_battlefield(self, unit) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return False
        if getattr(unit, "embarked_in", None) is not None:
            return False
        return True

    def unit_within_player_deployment_zone(self, unit, player_id: str, *, game=None) -> bool:
        if unit is None or not player_id:
            return False
        if game is None:
            owner = getattr(self.army, "player", None)
            game = getattr(owner, "game", None) if owner is not None else None
        if game is None:
            return False
        in_zone = getattr(game, "is_position_in_deployment_zone", None)
        if not callable(in_zone):
            return False
        for model in self._iter_unit_models(unit):
            location = model.get_location()
            if not location or len(location) < 2:
                continue
            if in_zone(float(location[0]), float(location[1]), str(player_id)):
                return True
        return False

    def _opponent_player(self, game):
        if game is None:
            return None
        owner = getattr(self.army, "player", None)
        for player in list(getattr(game, "players", []) or []):
            if player is None or player is owner:
                continue
            return player
        return None

    def _enemy_units_in_player_deployment_zone(self, game, *, enemy_player) -> list:
        if game is None or enemy_player is None:
            return []
        enemy_id = str(getattr(enemy_player, "id", "") or "")
        if not enemy_id:
            return []
        eligible: list = []
        for root in self._iter_player_unit_roots(enemy_player):
            if not self._unit_is_on_battlefield(root):
                continue
            if not self.unit_within_player_deployment_zone(root, enemy_id, game=game):
                continue
            eligible.append(root)
        eligible.sort(key=lambda item: self._entity_id(item) or str(getattr(item, "name", "") or ""))
        return eligible

    def _unit_has_radial_suffusion(self, unit) -> bool:
        if unit is None:
            return False
        special_rules = getattr(unit, "special_rules", None)
        if isinstance(special_rules, dict) and bool(special_rules.get(self._RADIAL_SUFFUSION_FLAG_KEY, False)):
            return True
        enhancement = getattr(unit, "enhancement", None)
        if enhancement is None:
            return False
        enh_id = str(getattr(enhancement, "id", "") or "").strip()
        if enh_id == self._RADIAL_SUFFUSION_ENHANCEMENT_ID:
            return True
        enh_name = str(getattr(enhancement, "name", "") or "").strip().lower()
        return enh_name == self._RADIAL_SUFFUSION_ENHANCEMENT_NAME

    def _unit_has_active_radial_suffusion_bearer(self, unit) -> bool:
        if unit is None or not self._unit_has_radial_suffusion(unit):
            return False
        if not self._unit_is_on_battlefield(unit):
            return False
        special_rules = getattr(unit, "special_rules", None)
        bearer_id = str(special_rules.get("enhancement_bearer_model_id", "") or "") if isinstance(special_rules, dict) else ""
        if bearer_id:
            for model in list(getattr(unit, "models", []) or []):
                if str(getattr(model, "id", getattr(model, "_id", "")) or "") != bearer_id:
                    continue
                return self._is_model_alive(model)
            return False
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is None:
                return False
            return self._is_model_alive(bearer)
        for model in list(getattr(unit, "models", []) or []):
            if self._is_model_alive(model):
                return True
        return False

    def _radial_suffusion_active(self) -> bool:
        for unit in list(getattr(self.army, "units", []) or []):
            if self._unit_has_active_radial_suffusion_bearer(unit):
                return True
        return False

    def _distance_to_player_deployment_zone(self, game, *, player_id: str, x: float, y: float) -> float:
        if game is None or not player_id:
            return float("inf")
        zones = getattr(game, "deployment_zones", None)
        if not isinstance(zones, dict):
            return float("inf")
        zone_info = zones.get(str(player_id))
        if not isinstance(zone_info, dict):
            return float("inf")
        mission_zones = list(zone_info.get("mission_zones", []) or [])
        if not mission_zones:
            return float("inf")

        px = float(x)
        py = float(y)
        min_distance = float("inf")
        for mission_zone in mission_zones:
            contains_point = getattr(mission_zone, "contains_point", None)
            if callable(contains_point) and bool(contains_point(px, py)):
                return 0.0

            vertices = list(getattr(mission_zone, "vertices", []) or [])
            if len(vertices) >= 3:
                try:
                    from shapely.geometry import Point as _ShPoint
                    from shapely.geometry import Polygon as _ShPoly

                    dist = float(_ShPoint(px, py).distance(_ShPoly(vertices)))
                    if dist < min_distance:
                        min_distance = dist
                    continue
                except (ImportError, TypeError, ValueError):
                    pass

            has_rect_bounds = all(hasattr(mission_zone, attr) for attr in ("x_min", "x_max", "y_min", "y_max"))
            if has_rect_bounds:
                x_min = float(getattr(mission_zone, "x_min"))
                x_max = float(getattr(mission_zone, "x_max"))
                y_min = float(getattr(mission_zone, "y_min"))
                y_max = float(getattr(mission_zone, "y_max"))
                dx = max(x_min - px, 0.0, px - x_max)
                dy = max(y_min - py, 0.0, py - y_max)
                dist = float(math.hypot(dx, dy))
                if dist < min_distance:
                    min_distance = dist
        return min_distance

    def _unit_within_distance_of_player_deployment_zone(
        self,
        unit,
        player_id: str,
        *,
        game=None,
        distance_in: float = 0.0,
    ) -> bool:
        if unit is None or not player_id or game is None:
            return False
        threshold = float(distance_in or 0.0)
        if threshold < 0.0:
            return False
        for model in self._iter_unit_models(unit):
            location = model.get_location()
            if not location or len(location) < 2:
                continue
            dist = self._distance_to_player_deployment_zone(
                game,
                player_id=str(player_id),
                x=float(location[0]),
                y=float(location[1]),
            )
            if dist <= (threshold + 1e-6):
                return True
        return False

    def _enemy_units_for_fallout(self, game, *, enemy_player) -> list:
        targets = list(self._enemy_units_in_player_deployment_zone(game, enemy_player=enemy_player) or [])
        if not self._radial_suffusion_active():
            return targets

        enemy_id = str(getattr(enemy_player, "id", "") or "")
        if not enemy_id:
            return targets
        known_ids: set[str] = {self._entity_id(unit) or str(id(unit)) for unit in targets}
        for root in self._iter_player_unit_roots(enemy_player):
            if not self._unit_is_on_battlefield(root):
                continue
            root_id = self._entity_id(root) or str(id(root))
            if root_id in known_ids:
                continue
            if not self._unit_within_distance_of_player_deployment_zone(
                root,
                enemy_id,
                game=game,
                distance_in=self._RADIAL_SUFFUSION_EXTRA_RANGE_IN,
            ):
                continue
            known_ids.add(root_id)
            targets.append(root)
        targets.sort(key=lambda item: self._entity_id(item) or str(getattr(item, "name", "") or ""))
        return targets

    def _unit_is_legio_or_adeptus_mechanicus_vehicle(self, unit) -> bool:
        if unit is None:
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        if self._unit_has_keyword(root, self._LEGIO_CYBERNETICA_KEYWORD):
            return True
        if not self._unit_has_keyword(root, "VEHICLE"):
            return False
        return self._unit_has_keyword_or_faction(root, "ADEPTUS MECHANICUS", faction_id=self.faction_id)

    def emotionless_clarity_auto_trigger_for_destroyed_model(
        self,
        destroyed_unit,
        destroyed_model,
        *,
        game=None,
    ) -> tuple[bool, str]:
        if not self.is_cohort_cybernetica():
            return False, ""
        if destroyed_unit is None or destroyed_model is None:
            return False, ""
        target_root = self._attached_root(destroyed_unit)
        if target_root is None or not self._unit_in_army(target_root):
            return False, ""
        if not self._unit_is_legio_or_adeptus_mechanicus_vehicle(target_root):
            return False, ""
        has_deadly_demise_fn = getattr(target_root, "has_deadly_demise", None)
        if not callable(has_deadly_demise_fn):
            return False, ""
        has_deadly_demise, _damage_dice = has_deadly_demise_fn()
        if not bool(has_deadly_demise):
            return False, ""

        if game is None:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(owner, "game", None) if owner is not None else None

        current_turn = 0
        turn_owner_id = ""
        if game is not None:
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0
            get_current_player = getattr(game, "get_current_player", None)
            if callable(get_current_player):
                current_player = get_current_player()
                turn_owner_id = str(getattr(current_player, "id", "") or "")

        from ..utility.aura_utils import distance_between_models_bases_3d

        sources: list[tuple[str, object, dict, object]] = []
        seen_roots: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            source_root = self._attached_root(unit)
            if source_root is None:
                continue
            source_root_id = self._entity_id(source_root) or str(id(source_root))
            if source_root_id in seen_roots:
                continue
            seen_roots.add(source_root_id)
            if not self._unit_is_on_battlefield(source_root):
                continue
            members = list(getattr(source_root, "get_attached_unit_members", lambda: [])() or [])
            if not members:
                members = [source_root]
            for source_unit in list(members or []):
                if source_unit is None:
                    continue
                source_sr = getattr(source_unit, "special_rules", None)
                if not isinstance(source_sr, dict) or not bool(source_sr.get(self._EMOTIONLESS_CLARITY_FLAG_KEY, False)):
                    continue
                get_bearer = getattr(source_unit, "_get_enhancement_bearer_model", None)
                bearer = get_bearer() if callable(get_bearer) else None
                if bearer is None:
                    continue
                if not self._is_model_alive(bearer):
                    continue
                try:
                    range_in = float(source_sr.get(self._EMOTIONLESS_CLARITY_RANGE_KEY, 12) or 12)
                except (TypeError, ValueError):
                    range_in = 12.0
                if range_in <= 0.0:
                    continue
                try:
                    distance_in = float(distance_between_models_bases_3d(bearer, destroyed_model))
                except (TypeError, ValueError):
                    continue
                if distance_in > range_in + 1e-6:
                    continue
                source_id = self._entity_id(source_unit) or self._entity_id(source_root) or str(id(source_unit))
                sources.append((str(source_id), source_unit, source_sr, bearer))

        if not sources:
            return False, ""
        sources.sort(key=lambda item: item[0])
        for _source_id, source_unit, source_sr, _bearer in list(sources):
            usage_scope = str(source_sr.get(self._EMOTIONLESS_CLARITY_USAGE_KEY, "turn") or "turn").strip().lower()
            if usage_scope not in {"turn", "battle_round"}:
                usage_scope = "turn"
            already_used = False
            if usage_scope == "battle_round":
                try:
                    used_round = int(source_sr.get("enhancement_emotionless_clarity_used_battle_round", 0) or 0)
                except (TypeError, ValueError):
                    used_round = 0
                already_used = bool(current_turn > 0 and used_round == current_turn)
            else:
                try:
                    used_turn = int(source_sr.get("enhancement_emotionless_clarity_used_turn", 0) or 0)
                except (TypeError, ValueError):
                    used_turn = 0
                used_owner = str(source_sr.get("enhancement_emotionless_clarity_used_turn_owner", "") or "")
                if current_turn > 0 and used_turn == current_turn:
                    if not used_owner or not turn_owner_id or used_owner == turn_owner_id:
                        already_used = True
            if already_used:
                continue

            if usage_scope == "battle_round":
                source_sr["enhancement_emotionless_clarity_used_battle_round"] = int(current_turn or 0)
            else:
                source_sr["enhancement_emotionless_clarity_used_turn"] = int(current_turn or 0)
                if turn_owner_id:
                    source_sr["enhancement_emotionless_clarity_used_turn_owner"] = str(turn_owner_id)
            source_name = str(source_sr.get(self._EMOTIONLESS_CLARITY_SOURCE_KEY, "") or "Emotionless Clarity").strip() or "Emotionless Clarity"
            source_sr["enhancement_emotionless_clarity_last_source"] = source_name
            source_unit.special_rules = source_sr
            return True, source_name
        return False, ""

    def _pending_rad_bombardment_request(self, game, *, target_unit, battle_round: int):
        if game is None or target_unit is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        target_id = self._entity_id(target_unit)
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._RAD_BOMBARDMENT_ABILITY_KEY:
                continue
            if str(ctx.get("target_unit_id", "") or "") != target_id:
                continue
            if int(ctx.get("battle_round", 0) or 0) != int(battle_round):
                continue
            return req
        return None

    def _build_rad_bombardment_request(self, game, *, target_unit, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        opponent = self._opponent_player(game)
        if opponent is None or target_unit is None:
            return None
        target_id = self._entity_id(target_unit)
        source_army_id = self._entity_id(self.army)
        options = [
            DecisionOption.create(
                "Stand Firm",
                payload={
                    "army_id": source_army_id,
                    "target_unit_id": target_id,
                    self._RAD_BOMBARDMENT_CHOICE_KEY: self._RAD_BOMBARDMENT_CHOICE_STAND_FIRM,
                },
            ),
            DecisionOption.create(
                "Take Cover",
                payload={
                    "army_id": source_army_id,
                    "target_unit_id": target_id,
                    self._RAD_BOMBARDMENT_CHOICE_KEY: self._RAD_BOMBARDMENT_CHOICE_TAKE_COVER,
                },
            ),
        ]
        prompt = (
            f"Rad-bombardment: choose how {getattr(target_unit, 'name', 'this unit')} responds "
            "in your deployment zone."
        )
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            prompt,
            player_id=getattr(opponent, "id", None),
            options=options,
            context={
                "ability": self._RAD_BOMBARDMENT_ABILITY_KEY,
                "ability_name": "Rad-bombardment",
                "army_id": source_army_id,
                "target_unit_id": target_id,
                "battle_round": int(battle_round),
            },
        )

    def _queue_rad_bombardment_requests(self, game, *, battle_round: int) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        opponent = self._opponent_player(game)
        if opponent is None:
            return
        targets = self._enemy_units_in_player_deployment_zone(game, enemy_player=opponent)
        request_decision = getattr(game, "request_decision", None)
        if not callable(request_decision):
            return
        for target in targets:
            if self._pending_rad_bombardment_request(game, target_unit=target, battle_round=int(battle_round)) is not None:
                continue
            request = self._build_rad_bombardment_request(game, target_unit=target, battle_round=int(battle_round))
            if request is not None:
                request_decision(request)

    def _clear_expired_taking_cover_state(self, game, *, battle_round: int) -> None:
        if game is None or int(battle_round or 0) <= 1:
            return
        owner = getattr(self.army, "player", None)
        for player in list(getattr(game, "players", []) or []):
            if player is None or player is owner:
                continue
            for unit in self._iter_player_unit_roots(player):
                special_rules = getattr(unit, "special_rules", None)
                if not isinstance(special_rules, dict):
                    continue
                applied_round = int(special_rules.get(self._RAD_BOMBARDMENT_TAKING_COVER_ROUND_KEY, 0) or 0)
                if applied_round <= 0 or applied_round >= int(battle_round):
                    continue
                added_battleshock = bool(special_rules.get(self._RAD_BOMBARDMENT_TAKING_COVER_ADDED_KEY, False))
                special_rules = dict(special_rules)
                special_rules.pop(self._RAD_BOMBARDMENT_TAKING_COVER_ROUND_KEY, None)
                special_rules.pop(self._RAD_BOMBARDMENT_TAKING_COVER_ADDED_KEY, None)
                unit.special_rules = special_rules
                if added_battleshock:
                    clear_battleshock = getattr(unit, "clear_battle_shock", None)
                    if callable(clear_battleshock):
                        clear_battleshock()

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if game is None:
            owner = getattr(self.army, "player", None)
            game = getattr(owner, "game", None) if owner is not None else None
        br = int(battle_round or 0)
        if self.is_rad_zone_corps():
            self._clear_expired_taking_cover_state(game, battle_round=br)
            if br == 1:
                self._queue_rad_bombardment_requests(game, battle_round=br)
        if self.is_skitarii_hunter_cohort():
            self._clear_expired_skitarii_cantic_thrallnet_state(game=game, battle_round=br)
            self._queue_skitarii_cantic_thrallnet_requests(
                game,
                player=getattr(self.army, "player", None),
                battle_round=br,
            )
        if self.is_data_psalm_conclave():
            self._queue_data_psalm_benediction_request(game, battle_round=br)

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if game is None or player is None:
            return
        if player is not getattr(self.army, "player", None):
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        battle_round = int(getattr(game, "turn", 0) or 0)
        if self.is_cohort_cybernetica():
            self._cleanup_expired_cohort_cybernetica_command_phase_effects(game=game)
        if self.is_haloscreed_battle_clade():
            self.queue_noospheric_unit_selection_request(
                game=game,
                player=player,
                battle_round=int(battle_round),
            )
        if self.is_explorator_maniple():
            self._queue_acquisition_request(game, player=player, battle_round=int(battle_round))
        if self.is_data_psalm_conclave():
            self._clear_expired_data_psalm_autosermon_state(
                game=game,
                player=player,
                battle_round=int(battle_round),
            )
            self._queue_data_psalm_autosermon_requests(
                game,
                player=player,
                battle_round=int(battle_round),
            )
        if not self.is_rad_zone_corps():
            return
        if battle_round < 2 or battle_round > 5:
            return
        opponent = self._opponent_player(game)
        if opponent is None:
            return
        targets = self._enemy_units_for_fallout(game, enemy_player=opponent)
        for target in targets:
            roll = int(get_roll("D6") or 0)
            if roll < 3:
                continue
            apply_mortal_wounds = getattr(target, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortal_wounds):
                apply_mortal_wounds(target, 1, game_map=getattr(game, "map", None))
            take_battle_shock_test = getattr(target, "take_battle_shock_test", None)
            if callable(take_battle_shock_test):
                take_battle_shock_test(int(battle_round))
