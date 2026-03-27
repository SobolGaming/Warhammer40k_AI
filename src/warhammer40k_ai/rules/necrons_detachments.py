from __future__ import annotations

from dataclasses import dataclass
import re

from ..utility.aura_utils import distance_between_models_bases_3d
from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


@dataclass(frozen=True)
class CommandPhaseBearerTargetSpec:
    ability_name: str
    target_label: str
    range_inches: float
    keyword_groups: tuple[tuple[str, ...], ...]
    exclude_keywords: tuple[str, ...]
    effect_key: str
    effect_value: int = 0


class NecronsDetachmentManager(DetachmentManagerBase):
    faction_id = "NEC"
    _ANNIHILATION_PROTOCOL_CHARGE_KEYWORDS = ("DESTROYER CULT", "FLAYED ONES")
    _ANNIHILATION_PROTOCOL_RANGED_KEYWORD = "DESTROYER CULT"
    _ANNIHILATION_PROTOCOL_CHARGE_SOURCE = "Annihilation Protocol (+1 to Charge roll vs Below Half-strength)"
    _ANNIHILATION_PROTOCOL_AP_SOURCE = "Annihilation Protocol (+1 AP vs closest eligible target)"
    _INGRAINED_SUPERIORITY_SOURCE = "Ingrained Superiority"
    _POWER_MATRIX_KEYWORDS = ("CRYPTEK", "CANOPTEK")
    _POWER_MATRIX_SOURCE = "Power Matrix"
    _COLD_FERVOUR_SOURCE = "Cold Fervour"
    _COLD_FERVOUR_BONUS = 2
    _HYPERPHASING_SOURCE = "Hyperphasing"
    _WORTHY_FOES_SOURCE = "Worthy Foes"
    _WORTHY_FOES_ATTACKER_KEYWORDS = ("NOBLE", "LYCHGUARD", "TRIARCH")
    _COSMIC_DISTORTION_SOURCE = "Cosmic Distortion"
    _COSMIC_DISTORTION_DEFAULT_RANGE = 6.0
    _COSMIC_DISTORTION_SURGED_RANGE = 9.0
    _COSMIC_DISTORTION_AP_BONUS = 1
    _COSMIC_DISTORTION_MORTAL_WOUNDS = 3
    _PANTHEON_BINDING_SURCHARGE_BY_UNIT_NAME = {
        "c tan shard of the deceiver": 40,
        "c tan shard of the nightbringer": 30,
        "c tan shard of the void dragon": 20,
        "transcendent c tan": 25,
    }
    _TECHNOSORCEROUS_AUGMENTATIONS_SOURCE = "Technosorcerous Augmentations"
    _TECHNOSORCEROUS_CHOICE_DATA = {
        "ANTI_INFANTRY_3": {
            "keyword": "ANTI-INFANTRY 3+",
            "label": "Anti-Infantry 3+",
            "summary": "Ranged weapons gain [ANTI-INFANTRY 3+] until end of phase.",
        },
        "ANTI_MOUNTED_4": {
            "keyword": "ANTI-MOUNTED 4+",
            "label": "Anti-Mounted 4+",
            "summary": "Ranged weapons gain [ANTI-MOUNTED 4+] until end of phase.",
        },
        "ASSAULT": {
            "keyword": "ASSAULT",
            "label": "Assault",
            "summary": "Ranged weapons gain [ASSAULT] until end of phase.",
        },
        "HEAVY": {
            "keyword": "HEAVY",
            "label": "Heavy",
            "summary": "Ranged weapons gain [HEAVY] until end of phase.",
        },
        "IGNORES_COVER": {
            "keyword": "IGNORES COVER",
            "label": "Ignores Cover",
            "summary": "Ranged weapons gain [IGNORES COVER] until end of phase.",
        },
        "ANTI_MONSTER_5": {
            "keyword": "ANTI-MONSTER 5+",
            "label": "Anti-Monster 5+",
            "summary": "Ranged weapons gain [ANTI-MONSTER 5+] until end of phase.",
        },
        "ANTI_VEHICLE_5": {
            "keyword": "ANTI-VEHICLE 5+",
            "label": "Anti-Vehicle 5+",
            "summary": "Ranged weapons gain [ANTI-VEHICLE 5+] until end of phase.",
        },
    }
    _TECHNOSORCEROUS_BASE_CHOICE_ORDER = (
        "ANTI_INFANTRY_3",
        "ANTI_MOUNTED_4",
        "ASSAULT",
        "HEAVY",
        "IGNORES_COVER",
    )
    _TECHNOSORCEROUS_ATOMIC_EXTRA_CHOICE_ORDER = (
        "ANTI_MONSTER_5",
        "ANTI_VEHICLE_5",
    )

    _COMMAND_PHASE_SELECT_FRIENDLY_RE = re.compile(
        r"in your command phase, select one friendly (?P<target>.+?) unit(?:,|\s)*"
        r"(?:\((?P<exclude>[^)]+)\)\s*)?"
        r"within (?P<range>\d+)\s*\"?\s*of (?:the bearer|this model)",
        flags=re.IGNORECASE,
    )
    _COMMAND_PHASE_FELL_BACK_SHOOT_RE = re.compile(
        r"eligible to shoot in a turn in which it fell back",
        flags=re.IGNORECASE,
    )
    _COMMAND_PHASE_DAMAGE_REDUCTION_RE = re.compile(
        r"each time an attack is allocated to a model in that unit,\s*subtract\s+(?P<val>\d+)\s+from\s+the\s+damage\s+characteristic\s+of\s+that\s+attack",
        flags=re.IGNORECASE,
    )

    def __init__(self, army=None):
        super().__init__(army)
        self._power_matrix_phase_key: tuple[int, str] | None = None
        self._power_matrix_nml_active: bool = False
        self._power_matrix_enemy_active: bool = False
        self._cold_fervour_turn_key: tuple[int, str] | None = None
        self._cold_fervour_activated_turn_key: tuple[int, str] | None = None
        self._cold_fervour_target_snapshots_by_attacker: dict[str, dict[str, tuple[object, bool, bool]]] = {}
        self._cursed_circlet_target_snapshots_by_attacker: dict[str, dict[str, tuple[object, int]]] = {}
        self.hyperphasing_last_resolved_phase_key: str = ""
        self.worthy_foes_target_unit_id: str = ""
        self.worthy_foes_target_name: str = ""
        self._cosmic_distortion_phase_key: str = ""
        self._cosmic_distortion_surged_unit_ids: set[str] = set()

    def is_starshatter_arsenal(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Starshatter Arsenal")

    def is_annihilation_legion(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Annihilation Legion")

    def is_awakened_dynasty(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Awakened Dynasty")

    def is_canoptek_court(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Canoptek Court")

    def is_cursed_legion(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Cursed Legion")

    def is_hypercrypt_legion(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hypercrypt Legion")

    def is_obeisance_phalanx(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Obeisance Phalanx")

    def is_cryptek_conclave(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Cryptek Conclave")

    def is_pantheon_of_woe(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Pantheon of Woe")

    @staticmethod
    def _normalize_name(value: str) -> str:
        text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _unit_root(unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
            if root is not None:
                return root
        return unit

    def _unit_belongs_to_army(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        if callable(get_parent_army):
            unit_army = get_parent_army()
        else:
            unit_army = getattr(root, "parent_army", None)
        return unit_army is self.army

    def _unit_contains_keyword(self, unit, keyword: str) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if self._unit_has_keyword(root, keyword):
            return True
        members_fn = getattr(root, "get_attached_unit_members", None)
        if not callable(members_fn):
            return False
        for member in list(members_fn() or []):
            if self._unit_has_keyword(member, keyword):
                return True
        return False

    def _unit_contains_any_keyword(self, unit, keywords: tuple[str, ...]) -> bool:
        for keyword in keywords:
            if self._unit_contains_keyword(unit, keyword):
                return True
        return False

    @staticmethod
    def _entity_has_keyword(entity, keyword: str) -> bool:
        if entity is None:
            return False
        kw = str(keyword or "").strip()
        if not kw:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any(kw))
        raw = [str(k or "") for k in (getattr(entity, "keywords", []) or [])]
        raw += [str(k or "") for k in (getattr(entity, "faction_keywords", []) or [])]
        return kw.lower() in {k.lower() for k in raw if str(k).strip()}

    @staticmethod
    def _iter_unit_models(unit) -> list:
        if unit is None:
            return []
        get_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_models):
            return [m for m in list(get_models() or []) if m is not None]
        return [m for m in list(getattr(unit, "models", []) or []) if m is not None]

    @staticmethod
    def _weapon_profile_is_ranged(weapon_profile) -> bool:
        if weapon_profile is None:
            return False
        parent_wargear = getattr(weapon_profile, "parent_wargear", None)
        if parent_wargear is None:
            return False
        is_ranged = getattr(parent_wargear, "is_ranged", None)
        if not callable(is_ranged):
            return False
        return bool(is_ranged())

    @staticmethod
    def _model_has_weapon_profile(model, weapon_profile) -> bool:
        if model is None or weapon_profile is None:
            return False
        parent_wargear = getattr(weapon_profile, "parent_wargear", None)
        if parent_wargear is None:
            return False
        model_wargear = list(getattr(model, "wargear", []) or [])
        if parent_wargear in model_wargear:
            return True
        target_name = str(getattr(parent_wargear, "name", "") or "").strip().lower()
        if not target_name:
            return False
        for wargear in model_wargear:
            if str(getattr(wargear, "name", "") or "").strip().lower() == target_name:
                return True
        return False

    def _iter_attached_members(self, unit) -> list:
        root = self._unit_root(unit)
        if root is None:
            return []
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        members.sort(key=lambda item: (str(get_entity_id(item) or ""), str(getattr(item, "name", "") or "")))
        return members

    def _attached_member_special_rules_with_flag(self, unit, flag_key: str) -> list[tuple[object, dict]]:
        out: list[tuple[object, dict]] = []
        for member in self._iter_attached_members(unit):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get(flag_key)):
                continue
            out.append((member, sr))
        return out

    @staticmethod
    def _model_is_alive(model) -> bool:
        if model is None:
            return False
        is_alive = getattr(model, "is_alive", False)
        return bool(is_alive() if callable(is_alive) else is_alive)

    @staticmethod
    def _enhancement_bearer_is_alive_for_member(member, special_rules: dict | None = None) -> bool:
        unit = member
        sr = special_rules if isinstance(special_rules, dict) else getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
        if bearer_id:
            for model in list(getattr(unit, "models", []) or []):
                model_id = str(get_entity_id(model) or "").strip()
                local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                if bearer_id in {model_id, local_id}:
                    return NecronsDetachmentManager._model_is_alive(model)
            return False
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is not None:
                return NecronsDetachmentManager._model_is_alive(bearer)
        return any(
            NecronsDetachmentManager._model_is_alive(model)
            for model in list(getattr(unit, "models", []) or [])
        )

    @staticmethod
    def _enhancement_bearer_model_for_member(member, special_rules: dict | None = None):
        unit = member
        if unit is None:
            return None
        sr = special_rules if isinstance(special_rules, dict) else getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
        if bearer_id:
            for model in list(getattr(unit, "models", []) or []):
                entity_id = str(get_entity_id(model) or "").strip()
                local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                if bearer_id in {entity_id, local_id}:
                    return model
            return None
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is not None:
                return bearer
        models = list(getattr(unit, "models", []) or [])
        if len(models) == 1:
            return models[0]
        for model in models:
            if NecronsDetachmentManager._model_is_alive(model):
                return model
        return None

    def _member_is_currently_leading_root(self, member, root) -> bool:
        if member is None or root is None or member is root:
            return False
        attached_to = getattr(member, "attached_to", None)
        return self._unit_root(attached_to) is root

    def _attached_members_with_active_enhancement(
        self,
        unit,
        flag_key: str,
        *,
        require_attached_member_to_lead_root: bool = False,
    ) -> list[tuple[object, dict]]:
        root = self._unit_root(unit)
        if root is None:
            return []
        out: list[tuple[object, dict]] = []
        for member, sr in self._attached_member_special_rules_with_flag(root, flag_key):
            if not self._enhancement_bearer_is_alive_for_member(member, sr):
                continue
            if (
                member is not root
                and require_attached_member_to_lead_root
                and not self._member_is_currently_leading_root(member, root)
            ):
                continue
            out.append((member, sr))
        return out

    def technosorcerous_unit_is_eligible(self, unit) -> bool:
        if not self.is_cryptek_conclave():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_belongs_to_army(root):
            return False
        return self._unit_contains_keyword(root, "CRYPTEK")

    def technosorcerous_choice_keyword(self, choice_key: str) -> str:
        key = str(choice_key or "").strip().upper()
        return str(self._TECHNOSORCEROUS_CHOICE_DATA.get(key, {}).get("keyword", "") or "")

    def technosorcerous_choice_label(self, choice_key: str) -> str:
        key = str(choice_key or "").strip().upper()
        label = str(self._TECHNOSORCEROUS_CHOICE_DATA.get(key, {}).get("label", "") or "").strip()
        return label or key

    def technosorcerous_choice_summary(self, choice_key: str) -> str:
        key = str(choice_key or "").strip().upper()
        summary = str(self._TECHNOSORCEROUS_CHOICE_DATA.get(key, {}).get("summary", "") or "").strip()
        if summary:
            return summary
        keyword = self.technosorcerous_choice_keyword(key)
        if keyword:
            return f"Ranged weapons gain [{keyword}] until end of phase."
        return ""

    def _cryptek_conclave_atomic_disintegrators_extra_choice_keys(self, unit) -> tuple[str, ...]:
        if not self.is_cryptek_conclave():
            return ()
        root = self._unit_root(unit)
        if root is None or not self.technosorcerous_unit_is_eligible(root):
            return ()
        configured: set[str] = set()
        for _member, sr in self._attached_members_with_active_enhancement(
            root,
            "enhancement_atomic_disintegrators",
            require_attached_member_to_lead_root=True,
        ):
            for choice_key in list(sr.get("enhancement_atomic_disintegrators_extra_choice_keys", []) or []):
                key = str(choice_key or "").strip().upper()
                if key:
                    configured.add(key)
        return tuple(
            key
            for key in self._TECHNOSORCEROUS_ATOMIC_EXTRA_CHOICE_ORDER
            if key in configured and key in self._TECHNOSORCEROUS_CHOICE_DATA
        )

    def technosorcerous_available_choice_keys(self, unit) -> tuple[str, ...]:
        if not self.technosorcerous_unit_is_eligible(unit):
            return ()
        choices = list(self._TECHNOSORCEROUS_BASE_CHOICE_ORDER)
        extras = self._cryptek_conclave_atomic_disintegrators_extra_choice_keys(unit)
        for choice_key in extras:
            if choice_key not in choices:
                choices.append(choice_key)
        return tuple(choices)

    def technosorcerous_choice_is_valid(self, unit, choice_key: str) -> bool:
        key = str(choice_key or "").strip().upper()
        if not key:
            return False
        return key in set(self.technosorcerous_available_choice_keys(unit))

    def technosorcerous_choice_options(self, unit) -> list[dict]:
        options: list[dict] = []
        for choice_key in self.technosorcerous_available_choice_keys(unit):
            options.append(
                {
                    "choice": choice_key,
                    "label": self.technosorcerous_choice_label(choice_key),
                    "summary": self.technosorcerous_choice_summary(choice_key),
                }
            )
        return options

    @staticmethod
    def _current_phase_name(game) -> str:
        if game is None:
            return ""
        return str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()

    @staticmethod
    def _current_turn(game) -> int:
        try:
            return int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _technosorcerous_assault_flag_active(self, unit, *, game=None) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("technosorcerous_assault_active")):
            return False
        if game is None:
            return True
        expires_phase = str(sr.get("technosorcerous_assault_expires_phase", "") or "").strip().upper()
        if expires_phase and expires_phase != self._current_phase_name(game):
            return False
        try:
            active_turn = int(sr.get("technosorcerous_assault_turn", 0) or 0)
        except (TypeError, ValueError):
            active_turn = 0
        current_turn = self._current_turn(game)
        if active_turn and current_turn and active_turn != current_turn:
            return False
        active_owner = str(sr.get("technosorcerous_assault_turn_owner", "") or "").strip()
        if active_owner:
            player = getattr(self.army, "player", None)
            owner_id = str(getattr(player, "id", "") or "").strip()
            if owner_id and owner_id != active_owner:
                return False
        return True

    def technosorcerous_assault_applies(self, unit, weapon_profile, *, game=None) -> bool:
        if not self.technosorcerous_unit_is_eligible(unit):
            return False
        if not self._weapon_profile_is_ranged(weapon_profile):
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if self._technosorcerous_assault_flag_active(root, game=game):
            return True
        for model in self._iter_unit_models(root):
            if not bool(getattr(model, "is_alive", True)):
                continue
            if not self._entity_has_keyword(model, "CRYPTEK"):
                continue
            if self._model_has_weapon_profile(model, weapon_profile):
                return True
        return False

    def apply_technosorcerous_augmentation_choice(self, unit, choice_key: str, *, game=None) -> bool:
        keyword = self.technosorcerous_choice_keyword(choice_key)
        if not keyword:
            return False
        if not self.technosorcerous_unit_is_eligible(unit):
            return False
        root = self._unit_root(unit)
        if root is None:
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        try:
            seq = int(sr.get("technosorcerous_augmentations_sequence", 0) or 0)
        except (TypeError, ValueError):
            seq = 0
        seq += 1
        sr["technosorcerous_augmentations_sequence"] = int(seq)

        applied = False
        unit_id = str(get_entity_id(root) or id(root))
        choice_key_norm = str(choice_key or "").strip().upper()
        for model in self._iter_unit_models(root):
            if not bool(getattr(model, "is_alive", True)):
                continue
            set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
            if not callable(set_keywords):
                continue
            model_id = str(get_entity_id(model) or id(model))
            for index, wargear in enumerate(list(getattr(model, "wargear", []) or [])):
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                effect_key = (
                    "technosorcerous_augmentations"
                    f":{unit_id}:{choice_key_norm}:{seq}:{model_id}:{int(index)}"
                )
                set_keywords(
                    key=effect_key,
                    weapon_name=weapon_name,
                    keywords=[keyword],
                    source=self._TECHNOSORCEROUS_AUGMENTATIONS_SOURCE,
                    expires_phase="SHOOTING_PHASE",
                    attack_type="ranged",
                )
                applied = True

        if keyword == "ASSAULT":
            sr["technosorcerous_assault_active"] = True
            sr["technosorcerous_assault_expires_phase"] = "SHOOTING_PHASE"
            if game is not None:
                sr["technosorcerous_assault_turn"] = self._current_turn(game)
                player = getattr(self.army, "player", None)
                sr["technosorcerous_assault_turn_owner"] = str(getattr(player, "id", "") or "")
        root.special_rules = sr
        return bool(applied)

    @staticmethod
    def _current_turn_owner_id(game) -> str:
        if game is None:
            return ""
        get_current_player = getattr(game, "get_current_player", None)
        if not callable(get_current_player):
            return ""
        player = get_current_player()
        return str(getattr(player, "id", "") or "")

    def _cold_fervour_turn_key_for_game(self, game) -> tuple[int, str]:
        return (self._current_turn(game), self._current_turn_owner_id(game))

    def _cold_fervour_sync_turn_state(self, game) -> None:
        key = self._cold_fervour_turn_key_for_game(game)
        if key == self._cold_fervour_turn_key:
            return
        self._cold_fervour_turn_key = key
        self._cold_fervour_activated_turn_key = None
        self._cold_fervour_target_snapshots_by_attacker = {}

    def _cold_fervour_attacker_unit_is_eligible(self, unit) -> bool:
        if not self.is_cursed_legion():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_belongs_to_army(root):
            return False
        return self._unit_contains_keyword(root, "DESTROYER CULT")

    @staticmethod
    def _cold_fervour_model_has_keyword(model, keyword: str) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any(keyword))
        raw = [str(k or "") for k in list(getattr(model, "keywords", []) or [])]
        raw += [str(k or "") for k in list(getattr(model, "faction_keywords", []) or [])]
        return str(keyword or "").strip().lower() in {k.lower() for k in raw if str(k).strip()}

    @staticmethod
    def _unit_alive_and_below_half_state(unit) -> tuple[bool, bool]:
        if unit is None:
            return (False, False)
        alive_attr = getattr(unit, "is_alive", None)
        if callable(alive_attr):
            alive = bool(alive_attr())
        else:
            alive = bool(alive_attr)
        below_half_fn = getattr(unit, "is_below_half_strength", None)
        if callable(below_half_fn):
            below_half = bool(below_half_fn())
        else:
            below_half = False
        return (alive, below_half)

    def _cold_fervour_secondary_bonus_active(self, game) -> bool:
        key = self._cold_fervour_turn_key_for_game(game)
        return bool(self._cold_fervour_activated_turn_key is not None and self._cold_fervour_activated_turn_key == key)

    def _cold_fervour_secondary_model_eligible(self, model) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_belongs_to_army(root):
            return False
        if not self.unit_is_necrons(root):
            return False
        if self._cold_fervour_model_has_keyword(model, "DESTROYER CULT"):
            return False
        if self._cold_fervour_model_has_keyword(model, "MONSTER"):
            return False
        if self._cold_fervour_model_has_keyword(model, "TITANIC"):
            return False
        return True

    def cold_fervour_strength_bonus(self, attacker_model, weapon_profile, *, game=None) -> tuple[int, str]:
        if attacker_model is None or weapon_profile is None:
            return (0, "")
        if not self.is_cursed_legion():
            return (0, "")
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None or not self._unit_belongs_to_army(root):
            return (0, "")

        if self._cold_fervour_model_has_keyword(attacker_model, "DESTROYER CULT"):
            return (self._COLD_FERVOUR_BONUS, self._COLD_FERVOUR_SOURCE)

        self._cold_fervour_sync_turn_state(game)
        if not self._cold_fervour_secondary_bonus_active(game):
            return (0, "")
        if not self._cold_fervour_secondary_model_eligible(attacker_model):
            return (0, "")
        return (self._COLD_FERVOUR_BONUS, self._COLD_FERVOUR_SOURCE)

    def cold_fervour_record_targets_selected(self, attacking_unit, target_units, *, game=None) -> None:
        if not self._cold_fervour_attacker_unit_is_eligible(attacking_unit):
            return
        self._cold_fervour_sync_turn_state(game)
        root = self._unit_root(attacking_unit)
        if root is None:
            return
        attacker_id = str(get_entity_id(root) or id(root))
        snapshots: dict[str, tuple[object, bool, bool]] = {}
        for target in list(target_units or []):
            target_root = self._unit_root(target)
            if target_root is None:
                continue
            target_id = str(get_entity_id(target_root) or id(target_root))
            if target_id in snapshots:
                continue
            before_alive, before_below_half = self._unit_alive_and_below_half_state(target_root)
            snapshots[target_id] = (target_root, bool(before_alive), bool(before_below_half))
        if snapshots:
            self._cold_fervour_target_snapshots_by_attacker[attacker_id] = snapshots
        else:
            self._cold_fervour_target_snapshots_by_attacker.pop(attacker_id, None)

    def cold_fervour_register_attacks_resolved(self, attacker_unit, *, target_units=None, game=None) -> bool:
        if not self._cold_fervour_attacker_unit_is_eligible(attacker_unit):
            return False
        self._cold_fervour_sync_turn_state(game)
        root = self._unit_root(attacker_unit)
        if root is None:
            return False
        attacker_id = str(get_entity_id(root) or id(root))
        snapshots = dict(self._cold_fervour_target_snapshots_by_attacker.get(attacker_id, {}) or {})
        if not snapshots:
            return False

        resolved_target_ids: list[str] = []
        for target in list(target_units or []):
            target_root = self._unit_root(target)
            if target_root is None:
                continue
            target_id = str(get_entity_id(target_root) or id(target_root))
            if target_id and target_id not in resolved_target_ids:
                resolved_target_ids.append(target_id)
        if not resolved_target_ids:
            resolved_target_ids = list(snapshots.keys())

        triggered = False
        for target_id in resolved_target_ids:
            entry = snapshots.pop(target_id, None)
            if not isinstance(entry, tuple) or len(entry) != 3:
                continue
            target_root, before_alive, before_below_half = entry
            if not bool(before_alive):
                continue
            after_alive, after_below_half = self._unit_alive_and_below_half_state(target_root)
            became_below_half = (not bool(before_below_half)) and bool(after_alive) and bool(after_below_half)
            destroyed = not bool(after_alive)
            if destroyed or became_below_half:
                triggered = True
                break

        if snapshots:
            self._cold_fervour_target_snapshots_by_attacker[attacker_id] = snapshots
        else:
            self._cold_fervour_target_snapshots_by_attacker.pop(attacker_id, None)

        if not triggered:
            return False
        if self._cold_fervour_secondary_bonus_active(game):
            return False
        self._cold_fervour_activated_turn_key = self._cold_fervour_turn_key_for_game(game)
        return True

    @staticmethod
    def _unit_alive_model_count(unit) -> int:
        return sum(1 for model in NecronsDetachmentManager._iter_unit_models(unit) if NecronsDetachmentManager._model_is_alive(model))

    @staticmethod
    def _unit_is_battle_shocked(unit) -> bool:
        root = NecronsDetachmentManager._unit_root(unit)
        if root is None:
            return False
        is_battle_shocked = getattr(root, "is_battle_shocked", None)
        if callable(is_battle_shocked):
            return bool(is_battle_shocked())
        return bool(getattr(root, "battle_shocked", False))

    def _active_cursed_circlet_source_for_unit(self, unit) -> dict | None:
        if not self.is_cursed_legion():
            return None
        root = self._unit_root(unit)
        if root is None or not self._unit_belongs_to_army(root):
            return None
        for member, special_rules in self._attached_member_special_rules_with_flag(root, "enhancement_cursed_circlet"):
            if not self._enhancement_bearer_is_alive_for_member(member, special_rules):
                continue
            source_name = str(
                special_rules.get("enhancement_cursed_circlet_source", "Cursed Circlet") or "Cursed Circlet"
            ).strip() or "Cursed Circlet"
            range_roll = str(special_rules.get("enhancement_cursed_circlet_range_roll", "D6") or "D6").strip().upper()
            exclude_keywords_any = [
                str(value or "").strip().upper()
                for value in list(
                    special_rules.get("enhancement_cursed_circlet_closest_enemy_exclude_keywords_any", ("AIRCRAFT",))
                    or ("AIRCRAFT",)
                )
                if str(value or "").strip()
            ]
            return {
                "member": member,
                "source_name": source_name,
                "range_roll": range_roll or "D6",
                "allow_engagement_range": bool(
                    special_rules.get("enhancement_cursed_circlet_allow_engagement_range", True)
                ),
                "requires_not_battle_shocked": bool(
                    special_rules.get("enhancement_cursed_circlet_requires_not_battle_shocked", True)
                ),
                "closest_enemy_exclude_keywords_any": exclude_keywords_any or ["AIRCRAFT"],
            }
        return None

    def _cursed_circlet_has_eligible_enemy(
        self,
        unit,
        *,
        game=None,
        exclude_keywords_any: tuple[str, ...] | list[str] | None = None,
    ) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        own_army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        excluded = tuple(str(value or "").strip().upper() for value in list(exclude_keywords_any or ()) if str(value or "").strip())
        seen: set[str] = set()
        for other in list(getattr(game_map, "units", []) or []):
            other_root = self._unit_root(other)
            if other_root is None:
                continue
            other_id = str(get_entity_id(other_root) or id(other_root))
            if other_id in seen:
                continue
            seen.add(other_id)
            if other_root is root:
                continue
            other_get_parent_army = getattr(other_root, "get_parent_army", None)
            other_army = (
                other_get_parent_army() if callable(other_get_parent_army) else getattr(other_root, "parent_army", None)
            )
            if own_army is not None and other_army is own_army:
                continue
            if self._unit_alive_model_count(other_root) <= 0:
                continue
            if excluded and self._unit_contains_any_keyword(other_root, excluded):
                continue
            return True
        return False

    def cursed_circlet_record_targets_selected(self, attacking_unit, target_units, *, game=None) -> None:
        if not self.is_cursed_legion():
            return
        attacker_root = self._unit_root(attacking_unit)
        if attacker_root is None:
            return
        attacker_id = str(get_entity_id(attacker_root) or id(attacker_root))
        attacker_get_parent_army = getattr(attacker_root, "get_parent_army", None)
        attacker_army = (
            attacker_get_parent_army()
            if callable(attacker_get_parent_army)
            else getattr(attacker_root, "parent_army", None)
        )
        snapshots = dict(self._cursed_circlet_target_snapshots_by_attacker.get(attacker_id, {}) or {})
        for target in list(target_units or []):
            target_root = self._unit_root(target)
            if target_root is None:
                continue
            target_get_parent_army = getattr(target_root, "get_parent_army", None)
            target_army = target_get_parent_army() if callable(target_get_parent_army) else getattr(target_root, "parent_army", None)
            if attacker_army is not None and target_army is attacker_army:
                continue
            if self._active_cursed_circlet_source_for_unit(target_root) is None:
                continue
            alive_model_count = int(self._unit_alive_model_count(target_root) or 0)
            if alive_model_count <= 0:
                continue
            target_id = str(get_entity_id(target_root) or id(target_root))
            snapshots[target_id] = (target_root, alive_model_count)
        if snapshots:
            self._cursed_circlet_target_snapshots_by_attacker[attacker_id] = snapshots
        else:
            self._cursed_circlet_target_snapshots_by_attacker.pop(attacker_id, None)

    def cursed_circlet_reactive_move_requests(self, attacker_unit, *, game=None) -> list[dict]:
        if not self.is_cursed_legion():
            return []
        attacker_root = self._unit_root(attacker_unit)
        if attacker_root is None:
            return []
        attacker_id = str(get_entity_id(attacker_root) or id(attacker_root))
        snapshots = dict(self._cursed_circlet_target_snapshots_by_attacker.pop(attacker_id, {}) or {})
        if not snapshots:
            return []
        attacker_get_parent_army = getattr(attacker_root, "get_parent_army", None)
        attacker_army = (
            attacker_get_parent_army()
            if callable(attacker_get_parent_army)
            else getattr(attacker_root, "parent_army", None)
        )
        requests: list[dict] = []
        for target_id in sorted(snapshots):
            entry = snapshots.get(target_id)
            if not isinstance(entry, tuple) or len(entry) != 2:
                continue
            target_root, before_count = entry
            if target_root is None:
                continue
            after_count = int(self._unit_alive_model_count(target_root) or 0)
            if after_count >= int(before_count or 0):
                continue
            source_data = self._active_cursed_circlet_source_for_unit(target_root)
            if source_data is None:
                continue
            if bool(source_data.get("requires_not_battle_shocked", True)) and self._unit_is_battle_shocked(target_root):
                continue
            target_get_parent_army = getattr(target_root, "get_parent_army", None)
            target_army = target_get_parent_army() if callable(target_get_parent_army) else getattr(target_root, "parent_army", None)
            if target_army is None or target_army is attacker_army:
                continue
            if not self._cursed_circlet_has_eligible_enemy(
                target_root,
                game=game,
                exclude_keywords_any=source_data.get("closest_enemy_exclude_keywords_any", ("AIRCRAFT",)),
            ):
                continue
            player = getattr(target_army, "player", None)
            if player is None:
                continue
            requests.append(
                {
                    "player": player,
                    "unit": target_root,
                    "attacker_unit": attacker_root,
                    "source_name": str(source_data.get("source_name", "Cursed Circlet") or "Cursed Circlet"),
                    "range_roll": str(source_data.get("range_roll", "D6") or "D6").strip().upper() or "D6",
                    "allow_engagement_range": bool(source_data.get("allow_engagement_range", True)),
                    "closest_enemy_exclude_keywords_any": list(
                        source_data.get("closest_enemy_exclude_keywords_any", ("AIRCRAFT",)) or ("AIRCRAFT",)
                    ),
                }
            )
        return requests

    def _iter_unique_army_roots(self) -> list:
        if self.army is None:
            return []
        units = list(getattr(self.army, "units", []) or [])
        out: list = []
        seen: set[str] = set()
        for unit in units:
            root = self._unit_root(unit)
            if root is None:
                continue
            root_id = str(get_entity_id(root) or id(root))
            if root_id in seen:
                continue
            seen.add(root_id)
            out.append(root)
        out.sort(key=lambda u: str(get_entity_id(u) or id(u)))
        return out

    def hyperphasing_end_of_opponent_turn_max_units(self, *, game=None) -> int:
        if not self.is_hypercrypt_legion():
            return 0
        size_name = ""
        if game is not None:
            size = getattr(getattr(game, "battlefield", None), "size", None)
            size_name = str(getattr(size, "name", "") or size or "")
        size_name = size_name.strip().upper().replace(" ", "_")
        if "INCURSION" in size_name:
            return 1
        if "STRIKE_FORCE" in size_name or "STRIKEFORCE" in size_name:
            return 2
        if "ONSLAUGHT" in size_name:
            return 3
        points_limit = int(getattr(self.army, "points_limit", 0) or 0) if self.army is not None else 0
        if points_limit >= 3000:
            return 3
        if points_limit >= 2000:
            return 2
        return 1

    def _hyperphasing_phase_key(self, *, game=None, turn_ending_player_id: str = "") -> str:
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        turn = self._current_turn(game)
        return f"{int(turn)}:{str(turn_ending_player_id or '').strip()}"

    def hyperphasing_phase_already_resolved(self, *, game=None, turn_ending_player_id: str = "") -> bool:
        key = self._hyperphasing_phase_key(game=game, turn_ending_player_id=turn_ending_player_id)
        return bool(key) and key == str(self.hyperphasing_last_resolved_phase_key or "")

    def mark_hyperphasing_phase_resolved(self, *, game=None, turn_ending_player_id: str = "") -> None:
        self.hyperphasing_last_resolved_phase_key = self._hyperphasing_phase_key(
            game=game,
            turn_ending_player_id=turn_ending_player_id,
        )

    def hyperphasing_end_of_opponent_turn_candidates(self, *, game=None, turn_ending_player=None, game_map=None) -> list:
        if not self.is_hypercrypt_legion() or self.army is None:
            return []
        if game is None:
            player = getattr(self.army, "player", None)
            game = getattr(player, "game", None) if player is not None else None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        player = getattr(self.army, "player", None)
        if player is None:
            return []
        if turn_ending_player is not None:
            turn_ending_id = str(get_entity_id(turn_ending_player) or getattr(turn_ending_player, "id", "") or "")
            player_id = str(get_entity_id(player) or getattr(player, "id", "") or "")
            if turn_ending_id and turn_ending_id == player_id:
                return []
            if turn_ending_player is player:
                return []

        candidates: list = []
        for root in self._iter_unique_army_roots():
            if not self.unit_is_necrons(root):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            reserve_status = str(getattr(root, "reserve_status", "deployed") or "deployed").strip().lower()
            if reserve_status != "deployed":
                continue
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive) and not bool(is_alive()):
                continue
            if bool(getattr(root, "embarked_in", None)) or bool(getattr(root, "is_embarked", False)):
                continue
            if game_map is None:
                candidates.append(root)
                continue
            engaged = False
            for enemy in list(getattr(game_map, "get_enemy_units", lambda _u: [])(root) or []):
                if enemy is None:
                    continue
                enemy_root = self._unit_root(enemy)
                if enemy_root is None:
                    continue
                enemy_alive = getattr(enemy_root, "is_alive", None)
                if callable(enemy_alive) and not bool(enemy_alive()):
                    continue
                if not bool(getattr(enemy_root, "deployed", True)):
                    continue
                if bool(getattr(enemy_root, "is_embarked", False)):
                    continue
                if bool(game_map.is_within_engagement_range(root, enemy_root)):
                    engaged = True
                    break
            if engaged:
                continue
            candidates.append(root)
        candidates.sort(key=lambda u: str(get_entity_id(u) or id(u)))
        return candidates

    def clear_worthy_foes_target(self) -> None:
        self.worthy_foes_target_unit_id = ""
        self.worthy_foes_target_name = ""
        if self.army is not None:
            setattr(self.army, "worthy_foes_target_unit_id", "")
            setattr(self.army, "worthy_foes_target_name", "")

    def set_worthy_foes_target(self, target_unit) -> bool:
        if target_unit is None:
            return False
        root = self._unit_root(target_unit)
        if root is None:
            return False
        rid = str(get_entity_id(root) or "").strip()
        if not rid:
            return False
        self.worthy_foes_target_unit_id = rid
        self.worthy_foes_target_name = str(getattr(root, "name", "") or "")
        if self.army is not None:
            setattr(self.army, "worthy_foes_target_unit_id", self.worthy_foes_target_unit_id)
            setattr(self.army, "worthy_foes_target_name", self.worthy_foes_target_name)
        return True

    def is_worthy_foe_target(self, target_unit) -> bool:
        if target_unit is None:
            return False
        target_id = str(self.worthy_foes_target_unit_id or "").strip()
        if not target_id:
            return False
        root = self._unit_root(target_unit)
        if root is None:
            return False
        rid = str(get_entity_id(root) or "").strip()
        return bool(rid) and rid == target_id

    def _worthy_foes_attacker_eligible(self, attacker_model) -> bool:
        if attacker_model is None:
            return False
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None:
            return False
        root = self._unit_root(attacker_unit)
        if root is None:
            return False
        if not self._unit_belongs_to_army(root):
            return False
        return self._unit_contains_any_keyword(root, self._WORTHY_FOES_ATTACKER_KEYWORDS)

    def worthy_foes_wound_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        game=None,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[int, str]:
        del game  # Present for parity with other detachment manager hooks.
        del weapon_profile
        del attack_instance
        if not self.is_obeisance_phalanx():
            return 0, ""
        if not self._worthy_foes_attacker_eligible(attacker_model):
            return 0, ""
        if not self.is_worthy_foe_target(target_unit):
            return 0, ""
        return 1, self._WORTHY_FOES_SOURCE

    def _worthy_foes_eligible_enemy_units(self, *, game=None, player=None) -> list:
        if not self.is_obeisance_phalanx():
            return []
        if game is None or player is None:
            return []
        get_enemy_units = getattr(game, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        enemy_units = list(get_enemy_units(player) or [])
        if not enemy_units:
            return []

        out: list = []
        seen: set[str] = set()
        for enemy in enemy_units:
            root = self._unit_root(enemy)
            if root is None:
                continue
            rid = str(get_entity_id(root) or "").strip()
            if not rid or rid in seen:
                continue
            seen.add(rid)
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive) and not bool(is_alive()):
                continue
            if not bool(getattr(root, "deployed", True)):
                continue
            reserve_status = str(getattr(root, "reserve_status", "deployed") or "deployed").strip().lower()
            if reserve_status != "deployed":
                continue
            if bool(getattr(root, "embarked_in", None)) or bool(getattr(root, "is_embarked", False)):
                continue
            out.append(root)
        out.sort(key=lambda u: str(get_entity_id(u) or id(u)))
        return out

    def _pending_worthy_foes_target_request(self, *, game=None, army_id: str = "") -> bool:
        queue = getattr(game, "decision_queue", None) if game is not None else None
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "worthy_foes":
                continue
            if army_id and str(ctx.get("army_id", "") or "") != str(army_id):
                continue
            return True
        return False

    def build_worthy_foes_request(self, *, game=None, player=None):
        if not self.is_obeisance_phalanx():
            return None
        if game is None or player is None:
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        targets = self._worthy_foes_eligible_enemy_units(game=game, player=player)
        if not targets:
            return None

        army_id = str(get_entity_id(self.army) or "") if self.army is not None else ""
        if self._pending_worthy_foes_target_request(game=game, army_id=army_id):
            return None

        options = []
        for target in targets:
            target_id = str(get_entity_id(target) or "").strip()
            if not target_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(target, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": target_id},
                )
            )
        if not options:
            return None

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Worthy Foes: select one enemy unit.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "worthy_foes",
                "ability_name": "Worthy Foes",
                "army_id": army_id,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    def _cosmic_distortion_phase_key_for_game(self, *, game=None) -> str:
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        phase_name = self._current_phase_name(game)
        if not phase_name:
            return ""
        turn = int(self._current_turn(game) or 0)
        turn_owner_id = str(self._current_turn_owner_id(game) or "")
        return f"{turn}:{turn_owner_id}:{phase_name}"

    def _sync_cosmic_distortion_phase_state(self, *, game=None) -> str:
        if not self.is_pantheon_of_woe():
            self._cosmic_distortion_phase_key = ""
            self._cosmic_distortion_surged_unit_ids = set()
            return ""
        phase_key = self._cosmic_distortion_phase_key_for_game(game=game)
        if not phase_key:
            self._cosmic_distortion_phase_key = ""
            self._cosmic_distortion_surged_unit_ids = set()
            return ""
        if phase_key != self._cosmic_distortion_phase_key:
            self._cosmic_distortion_phase_key = phase_key
            self._cosmic_distortion_surged_unit_ids = set()
        return phase_key

    def current_cosmic_distortion_phase_key(self, *, game=None) -> str:
        return str(self._sync_cosmic_distortion_phase_state(game=game) or "")

    def _pantheon_monster_unit_is_eligible(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_belongs_to_army(root):
            return False
        if not self.unit_is_necrons(root):
            return False
        if not self._unit_contains_keyword(root, "MONSTER"):
            return False
        if not self._unit_is_active(root):
            return False
        return True

    def cosmic_distortion_phase_surge_candidates(self, *, game=None, player=None) -> list:
        if not self.is_pantheon_of_woe():
            return []
        if player is not None and player is not getattr(self.army, "player", None):
            return []
        self._sync_cosmic_distortion_phase_state(game=game)
        candidates: list = []
        for root in self._iter_unique_army_roots():
            if not self._pantheon_monster_unit_is_eligible(root):
                continue
            candidates.append(root)
        candidates.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return candidates

    def _pending_cosmic_distortion_phase_surge_request(self, *, game=None, army_id: str = "", phase_key: str = "") -> bool:
        queue = getattr(game, "decision_queue", None) if game is not None else None
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != "SELECT_REALM_OF_CHAOS_UNITS":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "cosmic_distortion_phase_surge":
                continue
            if army_id and str(ctx.get("army_id", "") or "") != str(army_id):
                continue
            if phase_key and str(ctx.get("phase_key", "") or "") != str(phase_key):
                continue
            return True
        return False

    def build_cosmic_distortion_phase_surge_request(self, *, game=None, player=None, phase_name: str = ""):
        if not self.is_pantheon_of_woe():
            return None
        if game is None or player is None:
            return None
        if player is not getattr(self.army, "player", None):
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
        from ..engine.decisions import DecisionOption, DecisionRequest

        phase_key = self._sync_cosmic_distortion_phase_state(game=game)
        if not phase_key:
            return None

        phase_name_upper = str(phase_name or self._current_phase_name(game) or "").strip().upper()
        if not phase_name_upper:
            return None

        candidates = self.cosmic_distortion_phase_surge_candidates(game=game, player=player)
        if not candidates:
            return None

        army_id = str(get_entity_id(self.army) or "") if self.army is not None else ""
        if self._pending_cosmic_distortion_phase_surge_request(game=game, army_id=army_id, phase_key=phase_key):
            return None

        candidate_ids = [
            str(get_entity_id(unit) or "")
            for unit in list(candidates or [])
            if str(get_entity_id(unit) or "").strip()
        ]
        candidate_ids = sorted(set(candidate_ids))
        if not candidate_ids:
            return None

        request = DecisionRequest.create(
            DECISION_SELECT_REALM_OF_CHAOS_UNITS,
            "Cosmic Distortion: select NECRONS MONSTER units to surge Distortion Fields.",
            player_id=getattr(player, "id", None),
            options=[
                DecisionOption.create("Confirm selection", payload={"action": "confirm"}),
                DecisionOption.create("Do not use", payload={"action": "skip"}),
            ],
            context={
                "ability": "cosmic_distortion_phase_surge",
                "ability_name": "Cosmic Distortion",
                "army_id": army_id,
                "phase_key": phase_key,
                "phase_name": phase_name_upper,
                "allowed_unit_ids": list(candidate_ids),
                "outside_shadow_unit_ids": [],
                "max_units": int(len(candidate_ids)),
                "title": "Cosmic Distortion",
                "subtitle": "Select any NECRONS MONSTER unit(s) to suffer 3 mortal wounds.",
                "instruction": (
                    "Selected units suffer 3 mortal wounds and increase Distortion Fields range to 9\" "
                    "until the end of this phase."
                ),
                "skip_label": "None (do not use this ability)",
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    def apply_cosmic_distortion_phase_surge(self, unit_ids: list[str], *, game=None, phase_key: str = "", player=None) -> list:
        if not self.is_pantheon_of_woe():
            return []
        if player is not None and player is not getattr(self.army, "player", None):
            return []
        current_phase_key = self._sync_cosmic_distortion_phase_state(game=game)
        expected_phase_key = str(phase_key or current_phase_key or "")
        if current_phase_key and expected_phase_key and current_phase_key != expected_phase_key:
            return []

        candidates = self.cosmic_distortion_phase_surge_candidates(game=game, player=player)
        candidates_by_id = {
            str(get_entity_id(unit) or ""): unit
            for unit in list(candidates or [])
            if unit is not None
        }
        selected_ids = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})

        selected_units: list = []
        for uid in selected_ids:
            unit = candidates_by_id.get(uid)
            if unit is None:
                continue
            selected_units.append(unit)

        game_map = getattr(game, "map", None) if game is not None else None
        surged_unit_ids: set[str] = set()
        for unit in list(selected_units or []):
            apply_mortals = getattr(unit, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortals):
                apply_mortals(unit, int(self._COSMIC_DISTORTION_MORTAL_WOUNDS), game_map=game_map)
            unit_id = str(get_entity_id(unit) or "").strip()
            if unit_id:
                surged_unit_ids.add(unit_id)

        self._cosmic_distortion_phase_key = current_phase_key
        self._cosmic_distortion_surged_unit_ids = set(surged_unit_ids)
        if self.army is not None:
            setattr(self.army, "cosmic_distortion_phase_key", self._cosmic_distortion_phase_key)
            setattr(self.army, "cosmic_distortion_surged_unit_ids", sorted(self._cosmic_distortion_surged_unit_ids))
        return selected_units

    def cosmic_distortion_ap_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        del weapon_profile
        if not self.is_pantheon_of_woe():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""

        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._unit_root(attacker_unit)
        if attacker_root is None or not self._unit_belongs_to_army(attacker_root):
            return 0, ""

        target_root = self._unit_root(target_unit)
        if target_root is None:
            return 0, ""
        if self._unit_belongs_to_army(target_root):
            return 0, ""

        self._sync_cosmic_distortion_phase_state(game=game)
        surged_unit_ids = set(self._cosmic_distortion_surged_unit_ids or set())
        for source_unit in list(self.cosmic_distortion_phase_surge_candidates(game=game) or []):
            source_id = str(get_entity_id(source_unit) or "").strip()
            aura_range = float(self._COSMIC_DISTORTION_DEFAULT_RANGE)
            if source_id and source_id in surged_unit_ids:
                aura_range = float(self._COSMIC_DISTORTION_SURGED_RANGE)
            if self._source_in_range_of_target(source_unit, target_root, aura_range):
                return int(self._COSMIC_DISTORTION_AP_BONUS), self._COSMIC_DISTORTION_SOURCE
        return 0, ""

    def pantheon_of_woe_points_surcharge_for_unit(self, unit) -> int:
        if not self.is_pantheon_of_woe():
            return 0
        root = self._unit_root(unit)
        if root is None:
            return 0
        if not self._unit_belongs_to_army(root):
            return 0
        if not self.unit_is_necrons(root):
            return 0
        if not self._unit_contains_keyword(root, "MONSTER"):
            return 0
        unit_name_key = self._normalize_name(str(getattr(root, "name", "") or ""))
        return int(self._PANTHEON_BINDING_SURCHARGE_BY_UNIT_NAME.get(unit_name_key, 0) or 0)

    def validate_detachment_rules(self) -> list[str]:
        errors: list[str] = []
        if not self.is_pantheon_of_woe() or self.army is None:
            return errors

        for root in self._iter_unique_army_roots():
            if root is None:
                continue
            if not self._unit_belongs_to_army(root):
                continue
            if not self.unit_is_necrons(root):
                continue
            if not self._unit_contains_keyword(root, "MONSTER"):
                continue
            unit_name = str(getattr(root, "name", "") or "").strip() or "Unknown Unit"
            unit_name_key = self._normalize_name(unit_name)
            if unit_name_key in self._PANTHEON_BINDING_SURCHARGE_BY_UNIT_NAME:
                continue
            errors.append(
                "Pantheon of Woe (Necrodermal Binding): "
                f"no configured points surcharge mapping for '{unit_name}'."
            )
        return errors

    def _annihilation_protocol_charge_eligible(self, unit) -> bool:
        if not self.is_annihilation_legion():
            return False
        if unit is None:
            return False
        if not self._unit_belongs_to_army(unit):
            return False
        return self._unit_contains_any_keyword(unit, self._ANNIHILATION_PROTOCOL_CHARGE_KEYWORDS)

    def _annihilation_protocol_ranged_eligible(self, unit) -> bool:
        if not self._annihilation_protocol_charge_eligible(unit):
            return False
        return self._unit_contains_keyword(unit, self._ANNIHILATION_PROTOCOL_RANGED_KEYWORD)

    @staticmethod
    def _normalize_target_units(target_units) -> list:
        if target_units is None:
            return []
        if isinstance(target_units, (list, tuple, set)):
            return [t for t in list(target_units or []) if t is not None]
        return [target_units]

    def annihilation_protocol_charge_reroll_applies(self, unit, *, target_units=None, game=None) -> bool:
        del game  # Unused; present for parity with other detachment manager hooks.
        if not self._annihilation_protocol_charge_eligible(unit):
            return False
        if target_units is None:
            return True
        return bool(self._normalize_target_units(target_units))

    def annihilation_protocol_charge_roll_bonus(self, unit, *, target_units=None, game=None) -> tuple[int, str]:
        del game  # Unused; present for parity with other detachment manager hooks.
        if not self._annihilation_protocol_charge_eligible(unit):
            return 0, ""
        for target in self._normalize_target_units(target_units):
            root = self._unit_root(target)
            if root is None:
                continue
            is_below_half = getattr(root, "is_below_half_strength", None)
            if callable(is_below_half) and bool(is_below_half()):
                return 1, self._ANNIHILATION_PROTOCOL_CHARGE_SOURCE
        return 0, ""

    def annihilation_protocol_ranged_ap_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        weapon_profile=None,
        game_map=None,
    ) -> tuple[int, str]:
        if attacker_model is None or target_unit is None:
            return 0, ""
        if weapon_profile is None or game_map is None:
            return 0, ""
        parent_wargear = getattr(weapon_profile, "parent_wargear", None)
        if parent_wargear is None or not callable(getattr(parent_wargear, "is_ranged", None)):
            return 0, ""
        if not bool(parent_wargear.is_ranged()):
            return 0, ""

        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if not self._annihilation_protocol_ranged_eligible(attacker_unit):
            return 0, ""

        root = self._unit_root(attacker_unit)
        is_closest = getattr(root, "is_target_closest_eligible", None) if root is not None else None
        if not callable(is_closest):
            return 0, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return 0, ""

        if bool(is_closest(attacker_model, weapon_profile, target_root, game_map)):
            return 1, self._ANNIHILATION_PROTOCOL_AP_SOURCE
        return 0, ""

    def annihilation_legion_ingrained_superiority_critical_wound_ap_bonus(
        self,
        attacker_model,
        attack_instance,
        *,
        game=None,
    ) -> tuple[int, str]:
        _ = game
        if not self.is_annihilation_legion():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        if not isinstance(attack_instance, dict) or not bool(attack_instance.get("crit_wound", False)):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(attacker_unit)
        if root is None:
            return 0, ""
        if not self._unit_belongs_to_army(root):
            return 0, ""
        if not self._entity_has_keyword(root, "NECRONS"):
            return 0, ""
        for member, sr in self._attached_member_special_rules_with_flag(root, "enhancement_ingrained_superiority"):
            if not self._enhancement_bearer_is_alive_for_member(member, sr):
                continue
            try:
                bonus = int(sr.get("enhancement_ingrained_superiority_critical_wound_ap_bonus", 1) or 1)
            except (TypeError, ValueError):
                bonus = 1
            if bonus <= 0:
                continue
            source = str(sr.get("enhancement_ingrained_superiority_source", "") or self._INGRAINED_SUPERIORITY_SOURCE).strip()
            return int(bonus), source or self._INGRAINED_SUPERIORITY_SOURCE
        return 0, ""

    @staticmethod
    def _phase_key_for_game(game) -> tuple[int, str]:
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            turn = 0
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        return turn, phase_name

    def on_phase_start(self, *, game=None) -> None:
        if game is None:
            return
        self._sync_cosmic_distortion_phase_state(game=game)
        if not self.is_canoptek_court():
            return
        player = getattr(self.army, "player", None)
        if player is None:
            return
        phase_key = self._phase_key_for_game(game)
        self._power_matrix_phase_key = phase_key
        self._power_matrix_nml_active = False
        self._power_matrix_enemy_active = False
        zones_fn = getattr(game, "_shadow_of_chaos_zones", None)
        if callable(zones_fn):
            zones = set(zones_fn(player))
            self._power_matrix_nml_active = "nml" in zones
            self._power_matrix_enemy_active = "enemy" in zones

    def _active_power_matrix_zones(self, game) -> set[str]:
        zones = {"own"}
        if game is None:
            return zones
        phase_key = self._phase_key_for_game(game)
        if self._power_matrix_phase_key != phase_key:
            self._power_matrix_phase_key = phase_key
            self._power_matrix_nml_active = False
            self._power_matrix_enemy_active = False
            player = getattr(self.army, "player", None)
            zones_fn = getattr(game, "_shadow_of_chaos_zones", None)
            if player is not None and callable(zones_fn):
                snapshot = set(zones_fn(player))
                self._power_matrix_nml_active = "nml" in snapshot
                self._power_matrix_enemy_active = "enemy" in snapshot
        if self._power_matrix_nml_active:
            zones.add("nml")
        if self._power_matrix_enemy_active:
            zones.add("enemy")
        return zones

    def _unit_is_power_matrix_eligible(self, unit) -> bool:
        if not self.is_canoptek_court():
            return False
        if unit is None:
            return False
        if not self._unit_belongs_to_army(unit):
            return False
        return self._unit_contains_any_keyword(unit, self._POWER_MATRIX_KEYWORDS)

    def _model_within_power_matrix(self, model, *, game, player, opponent, zones: set[str]) -> bool:
        if model is None:
            return False
        if not bool(getattr(model, "is_alive", True)):
            return False
        get_location = getattr(model, "get_location", None)
        if not callable(get_location):
            return False
        location = get_location()
        if location is None or len(location) < 2:
            return False
        x = float(location[0] or 0.0)
        y = float(location[1] or 0.0)
        base = getattr(model, "model_base", None)
        if base is None:
            return False
        in_own = bool(game.is_position_wholly_in_deployment_zone(x, y, base, player.id))
        in_enemy = bool(game.is_position_wholly_in_deployment_zone(x, y, base, opponent.id)) if opponent is not None else False
        if in_own:
            zone = "own"
        elif in_enemy:
            zone = "enemy"
        else:
            zone = "nml"
        return zone in zones

    def unit_wholly_within_power_matrix(self, unit, *, game=None) -> bool:
        if not self.is_canoptek_court():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_belongs_to_army(root):
            return False
        player = getattr(self.army, "player", None)
        if player is None:
            return False
        if game is None:
            game = getattr(player, "game", None)
        if game is None:
            return False
        opponent = next((p for p in (getattr(game, "players", None) or []) if p is not player), None)
        zones = self._active_power_matrix_zones(game)
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        if not models:
            return False
        for model in models:
            if not self._model_within_power_matrix(
                model,
                game=game,
                player=player,
                opponent=opponent,
                zones=zones,
            ):
                return False
        return True

    def power_matrix_hit_reroll_mods(self, attacker_model, *, game=None) -> dict:
        if not self.is_canoptek_court():
            return {}
        if attacker_model is None:
            return {}
        unit = getattr(attacker_model, "parent_unit", None)
        if not self._unit_is_power_matrix_eligible(unit):
            return {}
        reroll_values = (1,)
        reroll_reasons = (f"{self._POWER_MATRIX_SOURCE}: re-roll Hit rolls of 1",)
        if self.unit_wholly_within_power_matrix(unit, game=game):
            return {
                "reroll_values": reroll_values,
                "reroll_reasons": reroll_reasons,
                "reroll_full": True,
                "reroll_full_reasons": (f"{self._POWER_MATRIX_SOURCE}: re-roll Hit roll",),
            }
        return {
            "reroll_values": reroll_values,
            "reroll_reasons": reroll_reasons,
            "reroll_full": False,
            "reroll_full_reasons": (),
        }

    def unit_is_necrons(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword_or_faction(unit, "NECRONS", faction_id=self.faction_id)

    def unit_is_vehicle_or_mounted(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "VEHICLE") or self._unit_has_keyword(unit, "MOUNTED")

    def unit_is_titanic(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if bool(getattr(unit, "is_titanic", False)):
                return True
        except Exception:
            pass
        return self._unit_has_keyword(unit, "TITANIC")

    def unit_is_monster(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if bool(getattr(unit, "is_monster", False)):
                return True
        except Exception:
            pass
        return self._unit_has_keyword(unit, "MONSTER")

    def relentless_onslaught_applies(self, unit) -> bool:
        if not self.is_starshatter_arsenal():
            return False
        return self.unit_is_necrons(unit)

    def relentless_onslaught_hit_bonus_applies(self, unit) -> bool:
        if not self.relentless_onslaught_applies(unit):
            return False
        return not self.unit_is_monster(unit)

    def relentless_onslaught_hit_bonus(self, attacker_unit, target_unit, *, game=None) -> tuple[int, str]:
        if not self.relentless_onslaught_hit_bonus_applies(attacker_unit):
            return 0, ""
        if attacker_unit is None or target_unit is None:
            return 0, ""
        game_map = getattr(game, "map", None) if game is not None else None
        try:
            if bool(attacker_unit._target_within_objective_range(target_unit, game_map)):
                return 1, "Relentless Onslaught (+1 to hit vs objective)"
        except Exception:
            pass
        return 0, ""

    def awakened_dynasty_phasal_subjugator_hit_bonus(self, attacker_unit, *, game=None) -> tuple[int, str]:
        if not self.is_awakened_dynasty():
            return 0, ""
        root = self._unit_root(attacker_unit)
        if root is None:
            return 0, ""
        if not self._unit_belongs_to_army(root) or not self._unit_is_active(root):
            return 0, ""
        if not self.unit_is_necrons(root):
            return 0, ""
        if self._unit_contains_keyword(root, "CHARACTER"):
            return 0, ""

        target_models = [model for model in self._iter_unit_models(root) if self._model_is_alive(model)]
        if not target_models:
            return 0, ""

        roots_by_key: dict[tuple[str, str], object] = {}
        for unit in list(getattr(self.army, "units", []) or []):
            source_root = self._unit_root(unit)
            if source_root is None:
                continue
            root_id = str(get_entity_id(source_root) or getattr(source_root, "_id", "") or "").strip()
            root_name = str(getattr(source_root, "name", "") or "").strip()
            roots_by_key[(root_id, root_name)] = source_root

        for _key, source_root in sorted(roots_by_key.items()):
            if not self._unit_is_active(source_root):
                continue
            for member, sr in self._attached_member_special_rules_with_flag(source_root, "enhancement_phasal_subjugator"):
                if bool(sr.get("enhancement_phasal_subjugator_requires_bearer_alive", True)) and not self._enhancement_bearer_is_alive_for_member(member, sr):
                    continue
                bearer_model = self._enhancement_bearer_model_for_member(member, sr)
                if bearer_model is None or not self._model_is_alive(bearer_model):
                    continue
                try:
                    range_inches = float(sr.get("enhancement_phasal_subjugator_range_inches", 6.0) or 6.0)
                except (TypeError, ValueError):
                    range_inches = 6.0
                if range_inches < 0.0:
                    continue
                for target_model in target_models:
                    distance = float(distance_between_models_bases_3d(bearer_model, target_model))
                    if distance > range_inches + 1e-6:
                        continue
                    try:
                        bonus = int(sr.get("enhancement_phasal_subjugator_hit_roll_bonus", 1) or 1)
                    except (TypeError, ValueError):
                        bonus = 1
                    if not bonus:
                        return 0, ""
                    source = (
                        str(sr.get("enhancement_phasal_subjugator_source", "") or "Phasal Subjugator (Aura)").strip()
                        or "Phasal Subjugator (Aura)"
                    )
                    return int(bonus), f"{source} (+{int(bonus)} to hit aura)"
        return 0, ""

    def canoptek_court_hyperphasic_fulcrum_wound_reroll_ones(self, attacker_model, *, game=None) -> tuple[bool, str]:
        if not self.is_canoptek_court():
            return False, ""
        if attacker_model is None:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(attacker_unit)
        if root is None:
            return False, ""
        if not self._unit_belongs_to_army(root) or not self._unit_is_active(root):
            return False, ""
        if not self.unit_wholly_within_power_matrix(root, game=game):
            return False, ""

        for member, sr in self._attached_member_special_rules_with_flag(root, "enhancement_hyperphasic_fulcrum"):
            if not self._member_is_currently_leading_root(member, root):
                continue
            if bool(sr.get("enhancement_hyperphasic_fulcrum_requires_bearer_alive", True)) and not self._enhancement_bearer_is_alive_for_member(member, sr):
                continue
            source = (
                str(sr.get("enhancement_hyperphasic_fulcrum_source", "") or "Hyperphasic Fulcrum").strip()
                or "Hyperphasic Fulcrum"
            )
            return True, f"{source}: re-roll Wound roll of 1 while wholly within Power Matrix"
        return False, ""

    def canoptek_court_metalodermal_tesla_weave_charge_declared_reactions(
        self,
        charging_unit,
        *,
        declared_targets=None,
        game=None,
    ) -> list[dict]:
        if not self.is_canoptek_court() or game is None:
            return []
        charging_root = self._unit_root(charging_unit)
        if charging_root is None or self._unit_belongs_to_army(charging_root):
            return []
        if not self._unit_is_active(charging_root):
            return []

        target_roots_by_id: dict[str, object] = {}
        for target in list(declared_targets or []):
            target_root = self._unit_root(target)
            if target_root is None:
                continue
            if not self._unit_belongs_to_army(target_root) or not self._unit_is_active(target_root):
                continue
            target_id = str(get_entity_id(target_root) or id(target_root))
            target_roots_by_id[target_id] = target_root
        if not target_roots_by_id:
            return []

        phase_key = self._phase_key_for_game(game)
        phase_key_token = f"{int(phase_key[0])}:{str(phase_key[1] or '').strip().upper()}"
        outcomes: list[dict] = []
        for target_id in sorted(target_roots_by_id):
            target_root = target_roots_by_id[target_id]
            for member, sr in self._attached_member_special_rules_with_flag(
                target_root,
                "enhancement_metalodermal_tesla_weave",
            ):
                if bool(sr.get("enhancement_metalodermal_tesla_weave_requires_bearer_alive", True)) and not self._enhancement_bearer_is_alive_for_member(member, sr):
                    continue
                if str(sr.get("enhancement_metalodermal_tesla_weave_last_phase_key", "") or "") == phase_key_token:
                    continue

                trigger_roll = int(get_roll("D6") or 0)
                mortal_wounds = 0
                mortal_note = ""
                if 2 <= trigger_roll <= 5:
                    rolled_mortal = int(get_roll("D3") or 0)
                    mortal_wounds = max(0, int(rolled_mortal))
                    mortal_note = f"D3={int(rolled_mortal)}"
                elif trigger_roll >= 6:
                    mortal_wounds = 3

                sr["enhancement_metalodermal_tesla_weave_last_phase_key"] = phase_key_token
                member.special_rules = sr

                if mortal_wounds > 0:
                    apply_mortals = getattr(target_root, "_apply_mortal_wounds_to_unit", None)
                    if callable(apply_mortals):
                        apply_mortals(charging_root, int(mortal_wounds), game_map=getattr(game, "map", None))

                outcomes.append(
                    {
                        "source": str(
                            sr.get("enhancement_metalodermal_tesla_weave_source", "") or "Metalodermal Tesla Weave"
                        ).strip()
                        or "Metalodermal Tesla Weave",
                        "charging_unit_name": str(getattr(charging_root, "name", "") or "Enemy unit").strip()
                        or "Enemy unit",
                        "trigger_roll": int(trigger_roll),
                        "mortal_wounds": int(mortal_wounds),
                        "mortal_note": mortal_note,
                    }
                )
        return outcomes

    def cryptek_conclave_gauntlet_of_compression_range_bonus(
        self,
        attacker_model,
        weapon_profile,
        *,
        game=None,
    ) -> tuple[int, str]:
        del game
        if not self.is_cryptek_conclave():
            return 0, ""
        if attacker_model is None or weapon_profile is None:
            return 0, ""
        if not self._weapon_profile_is_ranged(weapon_profile):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(attacker_unit)
        if root is None or not self._unit_belongs_to_army(root) or not self._unit_is_active(root):
            return 0, ""

        for _member, sr in self._attached_members_with_active_enhancement(
            root,
            "enhancement_gauntlet_of_compression",
            require_attached_member_to_lead_root=True,
        ):
            try:
                range_bonus = int(sr.get("enhancement_gauntlet_of_compression_range_bonus", 6) or 6)
            except (TypeError, ValueError):
                range_bonus = 6
            if range_bonus <= 0:
                continue
            source = (
                str(sr.get("enhancement_gauntlet_of_compression_source", "") or "Gauntlet of Compression").strip()
                or "Gauntlet of Compression"
            )
            return int(range_bonus), f"{source} +{int(range_bonus)}\""
        return 0, ""

    def cryptek_conclave_gravitic_bolas_requests(
        self,
        attacker_unit,
        *,
        hits_by_target=None,
        hit_models_by_target=None,
        game=None,
    ) -> list[dict]:
        if not self.is_cryptek_conclave():
            return []
        root = self._unit_root(attacker_unit)
        if root is None or not self._unit_belongs_to_army(root) or not self._unit_is_active(root):
            return []
        if game is None:
            return []

        def _target_root_for_key(target_unit):
            target_root = self._unit_root(target_unit)
            return target_root if target_root is not None else target_unit

        def _target_hit_by_bearer(target_unit, bearer_model) -> bool:
            if bearer_model is None or target_unit is None:
                return False
            if isinstance(hit_models_by_target, dict):
                for candidate, hit_models in list(hit_models_by_target.items()):
                    if _target_root_for_key(candidate) is not _target_root_for_key(target_unit):
                        continue
                    models = list(hit_models or [])
                    return bearer_model in models
                return False
            unit_models = self._iter_unit_models(root)
            if len(unit_models) == 1 and unit_models[0] is bearer_model:
                try:
                    return int((hits_by_target or {}).get(target_unit, 0) or 0) > 0
                except (AttributeError, TypeError, ValueError):
                    return False
            return False

        requests: list[dict] = []
        for member, sr in self._attached_members_with_active_enhancement(
            root,
            "enhancement_gravitic_bolas",
            require_attached_member_to_lead_root=True,
        ):
            bearer_model = self._enhancement_bearer_model_for_member(member, sr)
            if not self._model_is_alive(bearer_model):
                continue
            exclude_keywords_any = [
                str(value or "").strip().upper()
                for value in list(sr.get("enhancement_gravitic_bolas_exclude_keywords_any", []) or [])
                if str(value or "").strip()
            ]
            candidates: list = []
            for target_unit, hits in list((hits_by_target or {}).items()):
                if target_unit is None:
                    continue
                try:
                    if int(hits or 0) <= 0:
                        continue
                except (TypeError, ValueError):
                    continue
                target_root = self._unit_root(target_unit)
                if target_root is None or self._unit_belongs_to_army(target_root) or not self._unit_is_active(target_root):
                    continue
                if exclude_keywords_any and any(self._unit_has_keyword(target_root, kw) for kw in exclude_keywords_any):
                    continue
                if not _target_hit_by_bearer(target_root, bearer_model):
                    continue
                candidates.append(target_root)
            if not candidates:
                continue
            candidates = sorted(
                {cand for cand in candidates},
                key=lambda unit_obj: str(get_entity_id(unit_obj) or ""),
            )
            try:
                move_penalty = int(sr.get("enhancement_gravitic_bolas_move_penalty", -2) or -2)
            except (TypeError, ValueError):
                move_penalty = -2
            try:
                charge_penalty = int(sr.get("enhancement_gravitic_bolas_charge_penalty", -2) or -2)
            except (TypeError, ValueError):
                charge_penalty = -2
            requests.append(
                {
                    "ability_name": str(sr.get("enhancement_gravitic_bolas_source", "") or "Gravitic Bolas").strip()
                    or "Gravitic Bolas",
                    "expires_phase": str(sr.get("enhancement_gravitic_bolas_expires_phase", "") or "COMMAND_PHASE").strip().upper()
                    or "COMMAND_PHASE",
                    "move_penalty": int(move_penalty),
                    "charge_penalty": int(charge_penalty),
                    "candidate_units": list(candidates),
                }
            )
        return requests

    def relentless_onslaught_assault_applies(self, unit) -> bool:
        if not self.relentless_onslaught_applies(unit):
            return False
        if self.unit_is_titanic(unit):
            return False
        return self.unit_is_vehicle_or_mounted(unit)

    def _normalize_rules_text(self, text: str) -> str:
        if not text:
            return ""
        try:
            text = re.sub(r"<[^>]+>", " ", text)
        except Exception:
            pass
        text = text.replace("\n", " ").replace("\r", " ")
        return re.sub(r"\s+", " ", text).strip()

    def _strip_eligibility_prefix(self, text: str) -> str:
        t = str(text or "")
        low = t.lower()
        for marker in (" model only.", " models only."):
            idx = low.find(marker)
            if idx != -1:
                return t[idx + len(marker):].strip()
        return t

    def _parse_keyword_groups(self, target_desc: str) -> tuple[tuple[str, ...], ...]:
        if not target_desc:
            return ()
        desc = re.sub(r"\s+", " ", str(target_desc)).strip()
        parts = [p.strip() for p in re.split(r"\s+or\s+", desc, flags=re.IGNORECASE) if p.strip()]
        groups: list[tuple[str, ...]] = []
        for part in parts:
            tokens = part.split()
            if not tokens:
                continue
            last = tokens[-1]
            rest = tokens[:-1]
            group: list[str] = []
            if rest:
                group.append(" ".join(rest))
            group.append(last)
            groups.append(tuple(group))
        return tuple(groups)

    def _parse_exclude_keywords(self, text: str) -> tuple[str, ...]:
        if not text:
            return ()
        low = str(text).lower()
        out: list[str] = []
        if "titanic" in low:
            out.append("TITANIC")
        if "monster" in low:
            out.append("MONSTER")
        if "vehicle" in low and "mounted" in low and "excluding" in low:
            # If a rule explicitly excludes VEHICLE/MOUNTED, respect it.
            out.append("VEHICLE")
            out.append("MOUNTED")
        return tuple(out)

    def _unit_matches_keyword_groups(self, unit, groups: tuple[tuple[str, ...], ...]) -> bool:
        if unit is None:
            return False
        if not groups:
            return True
        for group in groups:
            if all(self._unit_has_keyword(unit, kw) for kw in group):
                return True
        return False

    def _unit_has_any_excluded_keyword(self, unit, exclude: tuple[str, ...]) -> bool:
        if unit is None:
            return False
        for kw in exclude:
            if self._unit_has_keyword(unit, kw):
                return True
        return False

    def _unit_is_active(self, unit) -> bool:
        if unit is None:
            return False
        fn = getattr(unit, "is_active_for_rules", None)
        if callable(fn):
            return bool(fn())
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            return False
        try:
            if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", True)):
                return False
        except Exception:
            pass
        try:
            if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
                return False
        except Exception:
            pass
        try:
            if bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            pass
        try:
            if getattr(unit, "embarked_in", None) is not None:
                return False
        except Exception:
            pass
        return True

    def _source_in_range_of_target(self, source_unit, target_unit, range_inches: float) -> bool:
        try:
            r = float(range_inches)
        except Exception:
            return False
        if source_unit is None or target_unit is None or r < 0:
            return False
        try:
            source_models = list(getattr(source_unit, "models", []) or [])
        except Exception:
            source_models = []
        source_models = [m for m in source_models if getattr(m, "is_alive", True)]
        if not source_models:
            return False
        try:
            target_models = list(target_unit.get_attached_unit_models() or [])
        except Exception:
            target_models = list(getattr(target_unit, "models", []) or [])
        target_models = [m for m in target_models if getattr(m, "is_alive", True)]
        if not target_models:
            return False
        for sm in source_models:
            for tm in target_models:
                if distance_between_models_bases_3d(sm, tm) <= r + 1e-6:
                    return True
        return False

    def _iter_command_phase_bearer_specs(self, unit) -> list[CommandPhaseBearerTargetSpec]:
        specs: list[CommandPhaseBearerTargetSpec] = []
        if unit is None:
            return specs
        iter_fn = getattr(unit, "_iter_ability_entries_for_rules", None)
        if not callable(iter_fn):
            return specs
        for name, desc in iter_fn(model=None):
            text = self._normalize_rules_text(desc or name or "")
            if not text:
                continue
            text = text.replace("\u2019", "'")
            text = self._strip_eligibility_prefix(text)
            if not text:
                continue
            m = self._COMMAND_PHASE_SELECT_FRIENDLY_RE.search(text)
            if not m:
                continue
            target_desc = str(m.group("target") or "").strip()
            exclude_raw = str(m.group("exclude") or "").strip()
            try:
                range_inches = float(m.group("range"))
            except Exception:
                range_inches = 0.0
            keyword_groups = self._parse_keyword_groups(target_desc)
            exclude_keywords = self._parse_exclude_keywords(exclude_raw)
            target_label = target_desc or "unit"

            if self._COMMAND_PHASE_FELL_BACK_SHOOT_RE.search(text):
                specs.append(
                    CommandPhaseBearerTargetSpec(
                        ability_name=str(name or "Command Phase Ability"),
                        target_label=target_label,
                        range_inches=range_inches,
                        keyword_groups=keyword_groups,
                        exclude_keywords=exclude_keywords,
                        effect_key="fell_back_shoot",
                        effect_value=1,
                    )
                )

            dmg = self._COMMAND_PHASE_DAMAGE_REDUCTION_RE.search(text)
            if dmg:
                try:
                    val = int(dmg.group("val"))
                except Exception:
                    val = 0
                if val:
                    specs.append(
                        CommandPhaseBearerTargetSpec(
                            ability_name=str(name or "Command Phase Ability"),
                            target_label=target_label,
                            range_inches=range_inches,
                            keyword_groups=keyword_groups,
                            exclude_keywords=exclude_keywords,
                            effect_key="damage_reduction",
                            effect_value=int(val),
                        )
                    )
        return specs

    def spec_from_context(self, ctx: dict | None) -> CommandPhaseBearerTargetSpec | None:
        if not isinstance(ctx, dict):
            return None
        if not bool(ctx.get("necrons_command_phase_enhancement")):
            return None
        ability_name = str(ctx.get("ability") or ctx.get("ability_name") or "").strip()
        target_label = str(ctx.get("target_label") or "unit").strip() or "unit"
        try:
            range_inches = float(ctx.get("range", 0) or 0.0)
        except Exception:
            range_inches = 0.0
        effect_key = str(ctx.get("effect_key") or "").strip()
        try:
            effect_value = int(ctx.get("effect_value", 0) or 0)
        except Exception:
            effect_value = 0
        raw_groups = list(ctx.get("keyword_groups", []) or [])
        keyword_groups: list[tuple[str, ...]] = []
        for group in raw_groups:
            if not group:
                continue
            if isinstance(group, (tuple, list)):
                cleaned = tuple(str(k or "").strip() for k in group if str(k or "").strip())
            else:
                cleaned = (str(group).strip(),)
            if cleaned:
                keyword_groups.append(cleaned)
        exclude = tuple(str(k or "").strip() for k in (ctx.get("exclude_keywords", []) or []) if str(k or "").strip())
        if not ability_name or not effect_key:
            return None
        return CommandPhaseBearerTargetSpec(
            ability_name=ability_name,
            target_label=target_label,
            range_inches=range_inches,
            keyword_groups=tuple(keyword_groups),
            exclude_keywords=exclude,
            effect_key=effect_key,
            effect_value=effect_value,
        )

    def _pending_request_for_source_spec(self, game, source_unit, spec: CommandPhaseBearerTargetSpec):
        if game is None or source_unit is None or spec is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        source_id = str(get_entity_id(source_unit) or "")
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = getattr(req, "context", {}) or {}
            if not bool(ctx.get("necrons_command_phase_enhancement")):
                continue
            if str(ctx.get("source_unit_id", "")) != source_id:
                continue
            if str(ctx.get("effect_key", "")) != str(spec.effect_key):
                continue
            if str(ctx.get("ability", "")) != str(spec.ability_name):
                continue
            return req
        return None

    def build_command_phase_bearer_request(self, game, player, source_unit, spec: CommandPhaseBearerTargetSpec, targets: list):
        if game is None or source_unit is None or spec is None or not targets:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = []
        for target in targets:
            options.append(
                DecisionOption.create(
                    getattr(target, "name", "Unit"),
                    payload={"target_unit_id": get_entity_id(target)},
                )
            )
        ctx = {
            "necrons_command_phase_enhancement": True,
            "source_unit_id": get_entity_id(source_unit),
            "ability": getattr(spec, "ability_name", ""),
            "effect_key": getattr(spec, "effect_key", ""),
            "effect_value": int(getattr(spec, "effect_value", 0) or 0),
            "range": float(getattr(spec, "range_inches", 0.0) or 0.0),
            "target_label": getattr(spec, "target_label", ""),
            "keyword_groups": [list(group) for group in (spec.keyword_groups or [])],
            "exclude_keywords": list(spec.exclude_keywords or ()),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select command phase enhancement target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    def get_command_phase_bearer_sources(self) -> list[dict]:
        sources: list[dict] = []
        army = self.army
        if army is None:
            return sources
        for unit in list(getattr(army, "units", []) or []):
            if not self._unit_is_active(unit):
                continue
            specs = self._iter_command_phase_bearer_specs(unit)
            for spec in specs:
                sources.append({"source": unit, "spec": spec})
        return sources

    def get_command_phase_bearer_targets(self, source_unit, spec: CommandPhaseBearerTargetSpec) -> list:
        army = self.army
        if army is None or source_unit is None or spec is None:
            return []
        eligible: list = []
        seen = set()
        for unit in list(getattr(army, "units", []) or []):
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                key = getattr(root, "_id", None) or id(root)
            except Exception:
                key = id(root)
            if key in seen:
                continue
            seen.add(key)
            if not self._unit_is_active(root):
                continue
            if not self._unit_matches_keyword_groups(root, spec.keyword_groups):
                continue
            if self._unit_has_any_excluded_keyword(root, spec.exclude_keywords):
                continue
            if not self._source_in_range_of_target(source_unit, root, spec.range_inches):
                continue
            eligible.append(root)
        eligible.sort(key=lambda u: str(getattr(u, "name", "")))
        return eligible

    def clear_command_phase_bearer_effects(self) -> None:
        army = self.army
        if army is None:
            return
        for unit in list(getattr(army, "units", []) or []):
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            for key in (
                "command_phase_fell_back_and_shoot_active",
                "command_phase_fell_back_and_shoot_source",
            ):
                sr.pop(key, None)
            entries = list(sr.get("allocated_damage_reductions", []) or [])
            kept = []
            for entry in entries:
                tag = str(entry.get("tag", "") or "")
                if tag.startswith("command_phase_bearer_damage_reduction"):
                    continue
                kept.append(entry)
            if kept:
                sr["allocated_damage_reductions"] = kept
            elif "allocated_damage_reductions" in sr:
                sr.pop("allocated_damage_reductions", None)
            unit.special_rules = sr

    def apply_command_phase_bearer_effect(self, source_unit, target_unit, spec: CommandPhaseBearerTargetSpec) -> bool:
        if source_unit is None or target_unit is None or spec is None:
            return False
        try:
            root = target_unit.get_attached_unit_root()
        except Exception:
            root = target_unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if spec.effect_key == "fell_back_shoot":
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["command_phase_fell_back_and_shoot_active"] = True
                sr["command_phase_fell_back_and_shoot_source"] = str(spec.ability_name or "")
                member.special_rules = sr
            return True
        if spec.effect_key == "damage_reduction":
            tag = f"command_phase_bearer_damage_reduction:{get_entity_id(source_unit)}:{spec.ability_name}"
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                entries = list(sr.get("allocated_damage_reductions", []) or [])
                kept = []
                for entry in entries:
                    if str(entry.get("tag", "") or "") == tag:
                        continue
                    kept.append(entry)
                kept.append(
                    {
                        "value": int(spec.effect_value),
                        "attack_type": "any",
                        "source": str(spec.ability_name or "Command phase effect"),
                        "op": "sub",
                        "tag": tag,
                    }
                )
                sr["allocated_damage_reductions"] = kept
                member.special_rules = sr
            return True
        return False

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        self.clear_command_phase_bearer_effects()
        self.clear_worthy_foes_target()
        if self.army is None or player is None:
            return
        if player is not getattr(self.army, "player", None):
            return
        self.build_worthy_foes_request(game=game, player=player)
        sources = self.get_command_phase_bearer_sources()
        if not sources:
            return
        for entry in sources:
            source_unit = entry.get("source")
            spec = entry.get("spec")
            targets = self.get_command_phase_bearer_targets(source_unit, spec)
            if not targets:
                continue
            if len(targets) == 1:
                self.apply_command_phase_bearer_effect(source_unit, targets[0], spec)
                continue
            pending = self._pending_request_for_source_spec(game, source_unit, spec)
            if pending is None and game is not None:
                self.build_command_phase_bearer_request(game, player, source_unit, spec, targets)
                continue
            if pending is not None:
                continue
            continue
