from __future__ import annotations

from collections import Counter
import re

from ..utility.aura_utils import unit_within_range_of_unit
from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class AeldariDetachmentManager(DetachmentManagerBase):
    faction_id = "AE"
    _RELENTLESS_RAIDERS_MOVE_ACTIONS = {"move", "advance", "fall_back", "charge"}
    _RIDE_THE_WIND_BATTLELINE_NAME_SNIPPETS = ("windrider", "windriders")
    _SPIRIT_CONCLAVE_BATTLELINE_NAME_SNIPPETS = ("wraithguard", "wraithblades")
    _SPIRIT_CONCLAVE_SPIRIT_GUIDES_TARGET_NAME_SNIPPETS = ("wraithblades", "wraithguard", "wraithlord")
    _SPIRIT_CONCLAVE_VENGEFUL_DEAD_TOKENS_KEY = "aeldari_spirit_conclave_vengeful_dead_tokens"
    _SPIRIT_CONCLAVE_SPIRIT_GUIDES_RANGE = 12.0
    _DEFEND_AT_ALL_COSTS_MODEL_KEYWORDS = (
        "DIRE AVENGERS",
        "DIRE AVENGER",
        "GUARDIANS",
        "GUARDIAN",
        "SUPPORT WEAPON",
        "WAR WALKERS",
        "WAR WALKER",
    )
    _DEFEND_AT_ALL_COSTS_MODEL_NAME_SNIPPETS = (
        "dire avenger",
        "guardian",
        "support weapon",
        "war walker",
    )
    _SEER_COUNCIL_STRATAGEM_FATE_VALUES = {
        "PRESENTIMENT OF DREAD": 1,
        "FOREWARNED": 2,
        "UNSHROUDED TRUTH": 3,
        "FATE INESCAPABLE": 4,
        "ISHA'S FURY": 5,
        "PSYCHIC SHIELD": 6,
    }
    _ACROBATIC_ONSLAUGHT_CAPS_BY_UNIT_NAME = {
        "death jester": 3,
        "shadowseer": 3,
        "troupe master": 3,
    }

    def __init__(self, army=None):
        super().__init__(army)
        self.seer_council_fate_dice: list[int] = []
        self.seer_council_fate_dice_generated_round: int = 0
        self.devoted_of_ynnead_lethal_surge_turn: int = 0
        self.devoted_of_ynnead_lethal_surge_turn_owner: str = ""
        self.devoted_of_ynnead_lethal_intent_phase_key: str = ""
        self.devoted_of_ynnead_lethal_intent_candidate_unit_ids: set[str] = set()
        self.ride_the_wind_last_resolved_phase_key: str = ""

    @staticmethod
    def _normalize_unit_name(name: str) -> str:
        text = re.sub(r"[^a-z0-9 ]+", " ", str(name or "").lower())
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _devoted_phase_key(*, turn: int, phase_name: str, turn_owner_id: str) -> str:
        return f"{int(turn or 0)}:{str(phase_name or '').strip().upper()}:{str(turn_owner_id or '')}"

    def _iter_unique_army_roots(self) -> list:
        roots: list = []
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            except Exception:
                root = unit
            if root is None:
                continue
            rid = str(get_entity_id(root) or "")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            roots.append(root)
        roots.sort(key=lambda u: str(get_entity_id(u) or ""))
        return roots

    def devoted_of_ynnead_unit_counts_as_ynnari(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "YNNARI"):
            return True
        if not self.is_devoted_of_ynnead():
            return False
        if bool(getattr(unit, "is_epic_hero", False)):
            return False
        return self._unit_has_keyword(unit, "ASURYANI")

    def devoted_of_ynnead_is_infantry_or_mounted(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "INFANTRY") or self._unit_has_keyword(unit, "MOUNTED")

    def devoted_of_ynnead_lethal_reprisal_candidates(self) -> list:
        if not self.is_devoted_of_ynnead():
            return []
        candidates: list = []
        for root in self._iter_unique_army_roots():
            if root is None:
                continue
            if not self.devoted_of_ynnead_unit_counts_as_ynnari(root):
                continue
            if bool(getattr(root, "is_titanic", False)) or self._unit_has_keyword(root, "TITANIC"):
                continue
            try:
                if not root.is_alive() or not bool(getattr(root, "deployed", False)):
                    continue
            except Exception:
                continue
            try:
                if root.is_in_reserves() or root.is_embarked:
                    continue
            except Exception:
                pass
            try:
                if not bool(root.is_below_starting_strength()):
                    continue
            except Exception:
                continue
            candidates.append(root)
        return candidates

    def devoted_of_ynnead_lethal_surge_available(self, unit, *, game=None) -> bool:
        if unit is None or not self.is_devoted_of_ynnead():
            return False
        if not self.devoted_of_ynnead_unit_counts_as_ynnari(unit):
            return False
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        if game is None:
            return False
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        try:
            turn_owner = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            turn_owner = None
        turn_owner_id = str(getattr(turn_owner, "id", "") or "")
        if int(self.devoted_of_ynnead_lethal_surge_turn or 0) != int(turn):
            return True
        if str(self.devoted_of_ynnead_lethal_surge_turn_owner or "") != turn_owner_id:
            return True
        return False

    def mark_devoted_of_ynnead_lethal_surge_used(self, *, game=None) -> None:
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        if game is None:
            return
        try:
            self.devoted_of_ynnead_lethal_surge_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            self.devoted_of_ynnead_lethal_surge_turn = 0
        try:
            turn_owner = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            turn_owner = None
        self.devoted_of_ynnead_lethal_surge_turn_owner = str(getattr(turn_owner, "id", "") or "")

    def record_devoted_of_ynnead_lethal_intent_candidates(
        self,
        *,
        game,
        candidate_unit_ids: list[str],
        turn_owner_id: str = "",
        phase_name: str = "SHOOTING_PHASE",
    ) -> None:
        if not self.is_devoted_of_ynnead() or game is None:
            return
        clean_ids = sorted({str(uid or "") for uid in list(candidate_unit_ids or []) if str(uid or "").strip()})
        if not clean_ids:
            return
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        owner_id = str(turn_owner_id or "")
        if not owner_id:
            try:
                owner = getattr(game, "get_current_player", lambda: None)()
            except Exception:
                owner = None
            owner_id = str(getattr(owner, "id", "") or "")
        key = self._devoted_phase_key(turn=turn, phase_name=phase_name, turn_owner_id=owner_id)
        if key != self.devoted_of_ynnead_lethal_intent_phase_key:
            self.devoted_of_ynnead_lethal_intent_phase_key = key
            self.devoted_of_ynnead_lethal_intent_candidate_unit_ids = set()
        self.devoted_of_ynnead_lethal_intent_candidate_unit_ids.update(clean_ids)

    def _has_travelling_players_rules(self) -> bool:
        return self.is_ghosts_of_the_webway() or self.is_serpents_brood()

    def _travelling_players_source_name(self) -> str:
        if self.is_serpents_brood():
            return "Boons of the Brood"
        return "Acrobatic Onslaught"

    def consume_devoted_of_ynnead_lethal_intent_candidates(
        self,
        *,
        game,
        turn_owner_id: str = "",
        phase_name: str = "SHOOTING_PHASE",
    ) -> list:
        if not self.is_devoted_of_ynnead() or game is None:
            return []
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        owner_id = str(turn_owner_id or "")
        if not owner_id:
            try:
                owner = getattr(game, "get_current_player", lambda: None)()
            except Exception:
                owner = None
            owner_id = str(getattr(owner, "id", "") or "")
        key = self._devoted_phase_key(turn=turn, phase_name=phase_name, turn_owner_id=owner_id)
        if key != self.devoted_of_ynnead_lethal_intent_phase_key:
            return []
        candidate_ids = sorted(str(v or "") for v in self.devoted_of_ynnead_lethal_intent_candidate_unit_ids if str(v or "").strip())
        self.devoted_of_ynnead_lethal_intent_phase_key = ""
        self.devoted_of_ynnead_lethal_intent_candidate_unit_ids = set()
        if not candidate_ids:
            return []
        by_id = {}
        for root in self._iter_unique_army_roots():
            by_id[str(get_entity_id(root) or "")] = root
        out: list = []
        for uid in candidate_ids:
            unit = by_id.get(uid)
            if unit is None:
                continue
            if not self.devoted_of_ynnead_unit_counts_as_ynnari(unit):
                continue
            if not self.devoted_of_ynnead_is_infantry_or_mounted(unit):
                continue
            try:
                if not unit.is_alive() or not bool(getattr(unit, "deployed", False)):
                    continue
            except Exception:
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            out.append(unit)
        return out

    def validate_detachment_rules(self) -> list[str]:
        errors: list[str] = []
        if self._has_travelling_players_rules():
            self.apply_acrobatic_onslaught_travelling_players()
            errors.extend(self._validate_acrobatic_onslaught_rules())
        if self.is_windrider_host():
            self.apply_ride_the_wind_battleline_keywords()
        if self.is_spirit_conclave():
            self.apply_spirit_conclave_battleline_keywords()
        if self.is_devoted_of_ynnead():
            errors.extend(self._validate_devoted_of_ynnead_rules())
        if self.has_veterans_of_the_void():
            errors.extend(self._validate_veterans_of_the_void_rules())
        return errors

    def _validate_acrobatic_onslaught_rules(self) -> list[str]:
        errors: list[str] = []
        if not self._has_travelling_players_rules() or self.army is None:
            return errors
        source_name = self._travelling_players_source_name()
        counts: Counter[str] = Counter()
        labels: dict[str, str] = {}
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            key = self._normalize_unit_name(getattr(unit, "name", ""))
            if key not in self._ACROBATIC_ONSLAUGHT_CAPS_BY_UNIT_NAME:
                continue
            counts[key] += 1
            if key not in labels:
                labels[key] = str(getattr(unit, "name", "") or key).strip() or key
        for key in sorted(self._ACROBATIC_ONSLAUGHT_CAPS_BY_UNIT_NAME):
            cap = int(self._ACROBATIC_ONSLAUGHT_CAPS_BY_UNIT_NAME[key])
            count = int(counts.get(key, 0))
            if count <= cap:
                continue
            label = labels.get(key, key.title())
            errors.append(
                f"{source_name} (Travelling Players): "
                f"'{label}' units {count}/{cap}."
            )
        return errors

    def get_unique_model_cap_overrides(self) -> list[dict]:
        """
        Return army inclusion cap overrides that replace generic one-of restrictions.
        """
        if not self._has_travelling_players_rules():
            return []
        out: list[dict] = []
        for unit_name, cap in sorted(self._ACROBATIC_ONSLAUGHT_CAPS_BY_UNIT_NAME.items()):
            pretty_name = " ".join(part.capitalize() for part in unit_name.split())
            out.append({"unit_name": pretty_name, "limit": int(cap)})
        return out

    def _validate_devoted_of_ynnead_rules(self) -> list[str]:
        errors: list[str] = []
        army = self.army
        if army is None:
            return errors

        units = list(getattr(army, "units", []) or [])
        if not units:
            errors.append("Strength from Death (Servants of the Whispering God): army must include Yvraine and/or The Yncarne.")
            return errors

        names = {self._normalize_unit_name(getattr(unit, "name", "")) for unit in units if unit is not None}
        yvraine_present = "yvraine" in names
        yncarne_present = "the yncarne" in names
        if not yvraine_present and not yncarne_present:
            errors.append("Strength from Death (Servants of the Whispering God): army must include Yvraine and/or The Yncarne.")
            return errors

        warlord = getattr(army, "warlord", None)
        if warlord is None:
            for unit in units:
                if bool(getattr(unit, "is_warlord", False)):
                    warlord = unit
                    break
        warlord_name = self._normalize_unit_name(getattr(warlord, "name", "")) if warlord is not None else ""
        if warlord_name not in {"yvraine", "the yncarne"}:
            errors.append("Strength from Death (Servants of the Whispering God): Yvraine or The Yncarne must be your WARLORD.")
        return errors

    def _validate_veterans_of_the_void_rules(self) -> list[str]:
        errors: list[str] = []
        if self.army is None:
            return errors

        valid_assigned = 0
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            enhancement = getattr(unit, "enhancement", None)
            if enhancement is None:
                continue
            if not self.veterans_of_the_void_allows_enhancement(unit, enhancement):
                errors.append(
                    "Veterans of the Void: "
                    f"unit '{getattr(unit, 'name', 'Unknown')}' cannot take enhancement "
                    f"'{getattr(enhancement, 'name', 'Unknown')}' (requires an ANHRATHE unit and a matching Corsair Enhancement)."
                )
                continue
            valid_assigned += 1

        max_allowed = int(self.veterans_of_the_void_max_enhancements() or 0)
        if valid_assigned > max_allowed:
            errors.append(
                f"Veterans of the Void: Corsair Enhancements assigned {int(valid_assigned)}/{int(max_allowed)}."
            )
        return errors

    def is_warhost_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Warhost")

    def is_armoured_warhost(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Armoured Warhost")

    def is_aspect_host(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Aspect Host")

    def is_devoted_of_ynnead(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Devoted of Ynnead")

    def is_ghosts_of_the_webway(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Ghosts of the Webway")

    def is_guardian_battlehost(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Guardian Battlehost")

    def is_windrider_host(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Windrider Host")

    @staticmethod
    def _model_has_keyword(model, keyword: str) -> bool:
        if model is None:
            return False
        key = str(keyword or "").strip()
        if not key:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any) and bool(has_any(key)):
            return True
        has_kw = getattr(model, "has_keyword", None)
        if callable(has_kw) and bool(has_kw(key)):
            return True
        return False

    def _model_or_unit_has_keyword(self, model, unit, keyword: str) -> bool:
        return self._model_has_keyword(model, keyword) or self._unit_has_keyword(unit, keyword)

    def _unit_is_harlequins(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "HARLEQUINS")

    def boons_of_the_brood_sustained_hits_value_for_model(self, model, *, unit=None) -> int:
        if not self.is_serpents_brood() or model is None:
            return 0
        source_unit = unit
        if source_unit is None:
            source_unit = getattr(model, "parent_unit", None)
        if source_unit is None:
            return 0
        try:
            root = source_unit.get_attached_unit_root()
        except Exception:
            root = source_unit
        if root is None or not self._unit_in_army(root):
            return 0

        is_harlequins_model = self._model_or_unit_has_keyword(model, source_unit, "HARLEQUINS")
        if is_harlequins_model:
            is_mounted_model = self._model_or_unit_has_keyword(model, source_unit, "MOUNTED")
            is_vehicle_model = self._model_or_unit_has_keyword(model, source_unit, "VEHICLE")
            if is_mounted_model or is_vehicle_model:
                return 1

        if self._unit_is_harlequins(root):
            disembarked = bool(getattr(getattr(root, "round_state", None), "disembarked_this_round", False))
            if disembarked:
                return 1
        return 0

    def _unit_is_troupe(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "TROUPE"):
            return True
        name = self._normalize_unit_name(getattr(unit, "name", ""))
        return name in {"troupe", "troupes"}

    def _unit_is_asuryani_mounted_or_vyper(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "VYPER"):
            return True
        return self._unit_has_keyword(unit, "ASURYANI") and self._unit_has_keyword(unit, "MOUNTED")

    def _unit_is_windriders(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "WINDRIDERS") or self._unit_has_keyword(unit, "WINDRIDER"):
            return True
        name = self._normalize_unit_name(getattr(unit, "name", ""))
        if not name:
            return False
        return any(snippet in name for snippet in self._RIDE_THE_WIND_BATTLELINE_NAME_SNIPPETS)

    @staticmethod
    def _resolve_root_unit(unit):
        if unit is None:
            return None
        return unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit

    def _unit_is_spirit_conclave_battleline_target(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "WRAITHGUARD") or self._unit_has_keyword(unit, "WRAITHBLADES"):
            return True
        name = self._normalize_unit_name(getattr(unit, "name", ""))
        return any(snippet in name for snippet in self._SPIRIT_CONCLAVE_BATTLELINE_NAME_SNIPPETS)

    def _unit_is_spirit_guides_target(self, unit) -> bool:
        if unit is None:
            return False
        if (
            self._unit_has_keyword(unit, "WRAITHBLADES")
            or self._unit_has_keyword(unit, "WRAITHGUARD")
            or self._unit_has_keyword(unit, "WRAITHLORD")
        ):
            return True
        name = self._normalize_unit_name(getattr(unit, "name", ""))
        return any(snippet in name for snippet in self._SPIRIT_CONCLAVE_SPIRIT_GUIDES_TARGET_NAME_SNIPPETS)

    def _unit_is_asuryani_psyker(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "ASURYANI") and self._unit_has_keyword(unit, "PSYKER")

    @staticmethod
    def _coerce_int(value, default: int = 0) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return int(default)

    @staticmethod
    def _is_alive(entity) -> bool:
        if entity is None:
            return False
        alive_attr = getattr(entity, "is_alive", None)
        if callable(alive_attr):
            return bool(alive_attr())
        return bool(alive_attr) if alive_attr is not None else True

    def _unit_is_active_for_rules(self, unit) -> bool:
        if unit is None:
            return False
        if not self._is_alive(unit):
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if str(getattr(unit, "reserve_status", "deployed") or "deployed").strip().lower() != "deployed":
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return False
        if getattr(unit, "embarked_in", None) is not None:
            return False
        return True

    def _model_is_asuryani_psyker(self, model, unit) -> bool:
        if model is None:
            return False
        model_keywords = list(getattr(model, "keywords", []) or []) + list(getattr(model, "faction_keywords", []) or [])
        if model_keywords:
            return self._model_has_keyword(model, "ASURYANI") and self._model_has_keyword(model, "PSYKER")
        return self._unit_is_asuryani_psyker(unit)

    def _model_is_wraith_construct(self, model, unit) -> bool:
        model_keywords = list(getattr(model, "keywords", []) or []) + list(getattr(model, "faction_keywords", []) or [])
        if model_keywords:
            return self._model_has_keyword(model, "WRAITH CONSTRUCT")
        return self._unit_has_keyword(unit, "WRAITH CONSTRUCT")

    def apply_spirit_conclave_battleline_keywords(self, unit=None) -> None:
        if not self.is_spirit_conclave() or self.army is None:
            return
        units = [unit] if unit is not None else list(getattr(self.army, "units", []) or [])
        for entry in units:
            root = self._resolve_root_unit(entry)
            if root is None or not self._unit_in_army(root):
                continue
            if not self._unit_is_spirit_conclave_battleline_target(root):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            if any(str(k or "").strip().lower() == "battleline" for k in keywords):
                continue
            keywords.append("Battleline")
            root.keywords = keywords

    def spirit_conclave_destroyed_psyker_awards_vengeful_dead(
        self,
        *,
        destroyed_model,
        destroyed_unit,
        destroyed_by_unit,
    ) -> bool:
        if not self.is_spirit_conclave():
            return False
        destroyed_root = self._resolve_root_unit(destroyed_unit)
        destroyed_by_root = self._resolve_root_unit(destroyed_by_unit)
        if destroyed_root is None or destroyed_by_root is None:
            return False
        if not self._unit_in_army(destroyed_root):
            return False
        if self._unit_in_army(destroyed_by_root):
            return False
        return self._model_is_asuryani_psyker(destroyed_model, destroyed_root)

    def spirit_conclave_add_vengeful_dead_tokens(self, target_unit, *, count: int = 1) -> int:
        added = max(0, self._coerce_int(count, default=0))
        if not self.is_spirit_conclave() or added <= 0:
            return 0
        root = self._resolve_root_unit(target_unit)
        if root is None or self._unit_in_army(root):
            return 0
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current = self._coerce_int(sr.get(self._SPIRIT_CONCLAVE_VENGEFUL_DEAD_TOKENS_KEY, 0), default=0)
        total = max(0, current + added)
        sr[self._SPIRIT_CONCLAVE_VENGEFUL_DEAD_TOKENS_KEY] = int(total)
        root.special_rules = sr
        return int(total)

    def spirit_conclave_vengeful_dead_tokens(self, unit) -> int:
        if unit is None:
            return 0
        root = self._resolve_root_unit(unit)
        if root is None:
            return 0
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return 0
        return max(0, self._coerce_int(sr.get(self._SPIRIT_CONCLAVE_VENGEFUL_DEAD_TOKENS_KEY, 0), default=0))

    def spirit_conclave_has_vengeful_dead_tokens(self, unit) -> bool:
        return self.spirit_conclave_vengeful_dead_tokens(unit) > 0

    def shepherds_of_the_dead_hit_bonus(self, model, attacker_unit, target_unit) -> tuple[int, str]:
        if not self.is_spirit_conclave():
            return 0, ""
        attacker_root = self._resolve_root_unit(attacker_unit)
        if attacker_root is None or not self._unit_in_army(attacker_root):
            return 0, ""
        if not self._model_is_wraith_construct(model, attacker_root):
            return 0, ""
        if not self.spirit_conclave_has_vengeful_dead_tokens(target_unit):
            return 0, ""
        return 1, "Shepherds of the Dead (+1 to hit vs Vengeful Dead)"

    def shepherds_of_the_dead_wound_bonus(self, model, attacker_unit, target_unit) -> tuple[int, str]:
        if not self.is_spirit_conclave():
            return 0, ""
        attacker_root = self._resolve_root_unit(attacker_unit)
        if attacker_root is None or not self._unit_in_army(attacker_root):
            return 0, ""
        if not self._model_is_wraith_construct(model, attacker_root):
            return 0, ""
        if not self.spirit_conclave_has_vengeful_dead_tokens(target_unit):
            return 0, ""
        return 1, "Shepherds of the Dead (+1 to wound vs Vengeful Dead)"

    def spirit_guides_battle_focus_applies(self, unit, *, game=None, game_map=None) -> bool:
        _ = game_map
        if not self.is_spirit_conclave() or self.army is None:
            return False
        root = self._resolve_root_unit(unit)
        if root is None or not self._unit_in_army(root):
            return False
        if not self._unit_is_spirit_guides_target(root):
            return False
        if not self._unit_is_active_for_rules(root):
            return False
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("aeldari_soul_bridge_active")):
            owner_id = str(sr.get("aeldari_soul_bridge_owner", "") or "")
            player_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
            if not owner_id or not player_id or owner_id == player_id:
                source_id = str(sr.get("aeldari_soul_bridge_psyker_unit_id", "") or "")
                if source_id:
                    for source in list(self._iter_unique_army_roots() or []):
                        if source is None:
                            continue
                        if str(get_entity_id(source) or "") != source_id:
                            continue
                        if self._unit_is_asuryani_psyker(source) and self._unit_is_active_for_rules(source):
                            return True
        psyker_sources: list = []
        for candidate in list(self._iter_unique_army_roots() or []):
            if candidate is None:
                continue
            if not self._unit_is_asuryani_psyker(candidate):
                continue
            if not self._unit_is_active_for_rules(candidate):
                continue
            psyker_sources.append(candidate)
        if not psyker_sources:
            return False
        range_inches = float(self._SPIRIT_CONCLAVE_SPIRIT_GUIDES_RANGE)
        for source in psyker_sources:
            if unit_within_range_of_unit(source, root, range_inches, use_attached_aggregate=True):
                return True
        return False

    def ride_the_wind_allows_standard_reserves(self, unit) -> bool:
        if not self.is_windrider_host():
            return False
        if unit is None:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        return self._unit_is_asuryani_mounted_or_vyper(root)

    def ride_the_wind_reserve_status_for_decision(self, unit, decision: str) -> str:
        status = str(decision or "").strip().lower()
        if status != "reserves":
            return status
        if not self.ride_the_wind_allows_standard_reserves(unit):
            return status
        # Ride the Wind "Reserves" entries arrive and set up using Strategic Reserves rules.
        return "strategic_reserves"

    def ride_the_wind_strategic_reserves_round_bonus(self, unit, *, game=None) -> int:
        _ = game
        if not self.is_windrider_host():
            return 0
        if unit is None:
            return 0
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return 0
        if not self._unit_in_army(root):
            return 0
        if not self._unit_is_asuryani_mounted_or_vyper(root):
            return 0
        is_in_strategic = getattr(root, "is_in_strategic_reserves", None)
        if callable(is_in_strategic) and not bool(is_in_strategic()):
            return 0
        return 1

    def apply_ride_the_wind_battleline_keywords(self, unit=None) -> None:
        if not self.is_windrider_host() or self.army is None:
            return
        if unit is None:
            units = list(getattr(self.army, "units", []) or [])
        else:
            units = [unit]
        for entry in units:
            if entry is None:
                continue
            root = entry.get_attached_unit_root() if hasattr(entry, "get_attached_unit_root") else entry
            if root is None:
                continue
            if not self._unit_in_army(root):
                continue
            if not self._unit_is_windriders(root):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            if not any(str(k or "").strip().lower() == "battleline" for k in keywords):
                keywords.append("Battleline")
                root.keywords = keywords

    def ride_the_wind_end_of_opponent_turn_max_units(self, *, game=None) -> int:
        if not self.is_windrider_host():
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

    def _ride_the_wind_phase_key(self, *, game=None, turn_ending_player_id: str = "") -> str:
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        return f"{turn}:{str(turn_ending_player_id or '').strip()}"

    def ride_the_wind_phase_already_resolved(self, *, game=None, turn_ending_player_id: str = "") -> bool:
        key = self._ride_the_wind_phase_key(game=game, turn_ending_player_id=turn_ending_player_id)
        return bool(key) and key == str(self.ride_the_wind_last_resolved_phase_key or "")

    def mark_ride_the_wind_phase_resolved(self, *, game=None, turn_ending_player_id: str = "") -> None:
        self.ride_the_wind_last_resolved_phase_key = self._ride_the_wind_phase_key(
            game=game,
            turn_ending_player_id=turn_ending_player_id,
        )

    def ride_the_wind_end_of_opponent_turn_candidates(self, *, game=None, turn_ending_player=None, game_map=None) -> list:
        if not self.is_windrider_host() or self.army is None:
            return []
        if game is None:
            player = getattr(self.army, "player", None)
            game = getattr(player, "game", None) if player is not None else None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        player = getattr(self.army, "player", None)
        if player is None:
            return []
        if turn_ending_player is not None and turn_ending_player is player:
            return []

        candidates: list = []
        for root in self._iter_unique_army_roots():
            if not self.ride_the_wind_allows_standard_reserves(root):
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
                try:
                    enemy_root = enemy.get_attached_unit_root()
                except Exception:
                    enemy_root = enemy
                if enemy_root is None:
                    continue
                enemy_alive = getattr(enemy_root, "is_alive", None)
                if callable(enemy_alive) and not bool(enemy_alive()):
                    continue
                if not bool(getattr(enemy_root, "deployed", True)):
                    continue
                try:
                    if game_map.is_within_engagement_range(root, enemy_root):
                        engaged = True
                        break
                except Exception:
                    continue
            if engaged:
                continue
            candidates.append(root)
        candidates.sort(key=lambda u: str(get_entity_id(u) or ""))
        return candidates

    def acrobatic_onslaught_charge_move_through_enemy_applies(self, unit) -> bool:
        if not self.is_ghosts_of_the_webway():
            return False
        if unit is None:
            return False
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if not self._unit_in_army(root):
            return False
        return self._unit_is_harlequins(root)

    @staticmethod
    def _apply_model_objective_control(model, value: int) -> None:
        if model is None:
            return
        oc = int(max(0, value))
        if hasattr(model, "_base_objective_control"):
            model._base_objective_control = int(oc)
        if hasattr(model, "_objective_control"):
            model._objective_control = int(oc)
        if hasattr(model, "_objective_control_raw"):
            model._objective_control_raw = str(int(oc))

    def apply_acrobatic_onslaught_travelling_players(self, unit=None) -> None:
        if not self._has_travelling_players_rules() or self.army is None:
            return
        if unit is None:
            units = list(getattr(self.army, "units", []) or [])
        else:
            units = [unit]
        for entry in units:
            if entry is None:
                continue
            root = entry.get_attached_unit_root() if hasattr(entry, "get_attached_unit_root") else entry
            if root is None:
                continue
            if not self._unit_in_army(root):
                continue
            if not self._unit_is_troupe(root):
                continue

            keywords = list(getattr(root, "keywords", []) or [])
            if not any(str(k or "").strip().lower() == "battleline" for k in keywords):
                keywords.append("Battleline")
                root.keywords = keywords

            models = list(getattr(root, "models", []) or [])
            if not models:
                continue
            troupe_models = [
                model for model in models
                if self._model_has_keyword(model, "TROUPE")
                or "troupe" in self._normalize_unit_name(getattr(model, "name", ""))
                or "player" in self._normalize_unit_name(getattr(model, "name", ""))
            ]
            if not troupe_models:
                troupe_models = list(models)
            for model in troupe_models:
                self._apply_model_objective_control(model, 2)

    def is_seer_council(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Seer Council")

    @staticmethod
    def _normalize_seer_council_stratagem_name(name: str) -> str:
        text = str(name or "").strip().upper()
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        for dash in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "−"):
            text = text.replace(dash, "-")
        text = re.sub(r"[^A-Z0-9' -]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _seer_council_fate_dice_count(self, *, game=None) -> int:
        size_name = ""
        if game is not None:
            size = getattr(getattr(game, "battlefield", None), "size", None)
            size_name = str(getattr(size, "name", "") or size or "")
        size_name = size_name.strip().upper().replace(" ", "_")
        if "INCURSION" in size_name:
            return 3
        if "STRIKE_FORCE" in size_name or "STRIKEFORCE" in size_name:
            return 6
        if "ONSLAUGHT" in size_name:
            return 9

        points_limit = int(getattr(self.army, "points_limit", 0) or 0) if self.army is not None else 0
        if points_limit >= 3000:
            return 9
        if points_limit >= 2000:
            return 6
        if points_limit >= 1000:
            return 3
        return 0

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self.is_seer_council():
            return
        br = int(battle_round or 0)
        if br != 1:
            return
        if int(self.seer_council_fate_dice_generated_round or 0) == 1:
            return

        dice_count = self._seer_council_fate_dice_count(game=game)
        pool: list[int] = []
        for _ in range(max(0, int(dice_count or 0))):
            roll = int(get_roll("D6") or 1)
            pool.append(min(6, max(1, roll)))
        self.seer_council_fate_dice = pool
        self.seer_council_fate_dice_generated_round = 1

    def preview_seer_council_fate_discount(self, *, stratagem_name: str) -> dict:
        if not self.is_seer_council():
            return {"available": False, "discount": 0, "die_value": 0, "matching_dice": 0}
        key = self._normalize_seer_council_stratagem_name(stratagem_name)
        die_value = int(self._SEER_COUNCIL_STRATAGEM_FATE_VALUES.get(key, 0) or 0)
        if die_value <= 0:
            return {"available": False, "discount": 0, "die_value": 0, "matching_dice": 0}
        pool = [int(v) for v in list(self.seer_council_fate_dice or [])]
        matching = sum(1 for value in pool if value == die_value)
        if matching <= 0:
            return {"available": False, "discount": 0, "die_value": die_value, "matching_dice": 0}
        return {"available": True, "discount": 1, "die_value": die_value, "matching_dice": matching}

    def consume_seer_council_fate_discount(self, *, stratagem_name: str) -> dict:
        preview = self.preview_seer_council_fate_discount(stratagem_name=stratagem_name)
        if not bool(preview.get("available", False)):
            out = dict(preview)
            out["consumed"] = False
            return out
        die_value = int(preview.get("die_value", 0) or 0)
        pool = [int(v) for v in list(self.seer_council_fate_dice or [])]
        try:
            idx = pool.index(die_value)
        except ValueError:
            out = dict(preview)
            out["consumed"] = False
            return out
        del pool[idx]
        self.seer_council_fate_dice = pool
        remaining = sum(1 for value in pool if value == die_value)
        return {
            "available": True,
            "consumed": True,
            "discount": 1,
            "die_value": die_value,
            "matching_dice": remaining,
        }

    def preview_seer_council_lucid_eye_adjustments(self) -> list[dict]:
        if not self.is_seer_council():
            return []
        pool = [int(v) for v in list(self.seer_council_fate_dice or [])]
        options: list[dict] = []
        for die_index, value in enumerate(pool):
            current = min(6, max(1, int(value or 0)))
            if current > 1:
                options.append(
                    {
                        "die_index": int(die_index),
                        "before": int(current),
                        "delta": -1,
                        "after": int(current - 1),
                    }
                )
            if current < 6:
                options.append(
                    {
                        "die_index": int(die_index),
                        "before": int(current),
                        "delta": 1,
                        "after": int(current + 1),
                    }
                )
        options.sort(key=lambda entry: (int(entry.get("die_index", -1)), int(entry.get("delta", 0))))
        return options

    def apply_seer_council_lucid_eye_adjustment(self, *, die_index: int, delta: int) -> dict:
        out = {
            "applied": False,
            "die_index": int(die_index),
            "delta": int(delta),
            "before": 0,
            "after": 0,
            "pool": [int(v) for v in list(self.seer_council_fate_dice or [])],
        }
        if not self.is_seer_council():
            out["reason"] = "not_seer_council"
            return out

        try:
            idx = int(die_index)
        except Exception:
            out["reason"] = "invalid_die_index"
            return out
        try:
            shift = int(delta)
        except Exception:
            out["reason"] = "invalid_delta"
            return out
        if shift not in (-1, 1):
            out["reason"] = "invalid_delta"
            return out

        legal = self.preview_seer_council_lucid_eye_adjustments()
        if not any(int(entry.get("die_index", -1)) == idx and int(entry.get("delta", 0)) == shift for entry in legal):
            out["reason"] = "illegal_adjustment"
            return out

        pool = [int(v) for v in list(self.seer_council_fate_dice or [])]
        if idx < 0 or idx >= len(pool):
            out["reason"] = "die_index_out_of_range"
            return out
        before = min(6, max(1, int(pool[idx] or 0)))
        after = min(6, max(1, int(before + shift)))
        if before == after:
            out["reason"] = "no_change"
            return out
        pool[idx] = int(after)
        self.seer_council_fate_dice = pool
        out["applied"] = True
        out["before"] = int(before)
        out["after"] = int(after)
        out["pool"] = [int(v) for v in list(pool)]
        return out

    def is_serpents_brood(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Serpent's Brood")

    def is_spirit_conclave(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Spirit Conclave")

    def is_eldritch_raiders(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Eldritch Raiders")

    def is_corsair_coterie(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Corsair Coterie")

    def has_veterans_of_the_void(self) -> bool:
        return self.is_eldritch_raiders() or self.is_corsair_coterie()

    def is_anhrathe_unit(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "ANHRATHE")

    def veterans_of_the_void_allows_enhancement(self, unit, enhancement) -> bool:
        if not self.has_veterans_of_the_void():
            return False
        if unit is None or enhancement is None:
            return False
        if self.army is not None and hasattr(unit, "get_parent_army"):
            if unit.get_parent_army() is not self.army:
                return False
        if not self.is_anhrathe_unit(unit):
            return False
        faction_id = str(getattr(enhancement, "faction_id", "") or "").strip().upper()
        if faction_id and faction_id != self.faction_id:
            return False
        detachment_name = str(getattr(enhancement, "detachment", "") or "").strip()
        if detachment_name and not self.detachment_matches(detachment_name):
            return False
        return True

    def veterans_of_the_void_max_enhancements(self) -> int:
        if not self.has_veterans_of_the_void() or self.army is None:
            return 3
        count = 0
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            if self.is_anhrathe_unit(unit):
                count += 1
        return int(count)

    @staticmethod
    def _objective_sort_key(loc) -> tuple[str, float, float]:
        objective_id = str(get_entity_id(loc) or "")
        try:
            x = float(getattr(loc, "x", 0.0) or 0.0)
        except (TypeError, ValueError):
            x = 0.0
        try:
            y = float(getattr(loc, "y", 0.0) or 0.0)
        except (TypeError, ValueError):
            y = 0.0
        return (objective_id, x, y)

    def apply_void_thieves_sticky_objectives(self, *, game=None, game_map=None) -> int:
        if not self.is_corsair_coterie() or self.army is None:
            return 0
        player = getattr(self.army, "player", None)
        if player is None:
            return 0
        resolved_map = self._resolve_game_map(game=game, game_map=game_map)
        if resolved_map is None:
            return 0

        objective_locations: list = []
        for obj in list(getattr(resolved_map, "objectives", []) or []):
            loc = getattr(obj, "location", None)
            if loc is None:
                loc = obj
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            update_control = getattr(loc, "update_control", None)
            if callable(update_control) and game is not None:
                update_control(game)
            objective_locations.append(loc)
        if not objective_locations:
            return 0
        objective_locations.sort(key=self._objective_sort_key)

        applied = 0
        for root in list(self._iter_unique_army_roots() or []):
            if root is None:
                continue
            if not self.is_anhrathe_unit(root):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive) and not bool(is_alive()):
                continue
            in_reserves = getattr(root, "is_in_reserves", None)
            if callable(in_reserves) and bool(in_reserves()):
                continue
            if bool(getattr(root, "is_embarked", False)):
                continue
            within_objective = getattr(root, "is_within_objective_range", None)
            if not callable(within_objective):
                continue

            for loc in objective_locations:
                if getattr(loc, "controlling_player", None) is not player:
                    continue
                if not bool(within_objective(loc)):
                    continue
                if (
                    getattr(loc, "sticky_controller", None) is player
                    and str(getattr(loc, "sticky_source", "") or "").strip().lower() == "void_thieves"
                ):
                    continue
                set_sticky = getattr(loc, "set_sticky_control", None)
                if callable(set_sticky):
                    set_sticky(player, source="void_thieves")
                else:
                    loc.sticky_controller = player
                    loc.sticky_source = "void_thieves"
                    loc.controlling_player = player
                applied += 1
        return int(applied)

    def resolve_relentless_raiders_enemy_move(self, enemy_unit, *, action: str, game=None, game_map=None) -> list[dict]:
        if not self.is_corsair_coterie() or self.army is None:
            return []
        action_key = str(action or "").strip().lower()
        if action_key not in self._RELENTLESS_RAIDERS_MOVE_ACTIONS:
            return []
        if enemy_unit is None:
            return []
        if self._unit_in_army(enemy_unit):
            return []
        if not bool(getattr(enemy_unit, "deployed", False)):
            return []
        is_alive = getattr(enemy_unit, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return []
        in_reserves = getattr(enemy_unit, "is_in_reserves", None)
        if callable(in_reserves) and bool(in_reserves()):
            return []
        if bool(getattr(enemy_unit, "is_embarked", False)):
            return []
        within_objective = getattr(enemy_unit, "is_within_objective_range", None)
        if not callable(within_objective):
            return []

        player = getattr(self.army, "player", None)
        if player is None:
            return []
        resolved_map = self._resolve_game_map(game=game, game_map=game_map)
        if resolved_map is None:
            return []

        objective_locations: list = []
        for obj in list(getattr(resolved_map, "objectives", []) or []):
            loc = getattr(obj, "location", None)
            if loc is None:
                loc = obj
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            update_control = getattr(loc, "update_control", None)
            if callable(update_control) and game is not None:
                update_control(game)
            if getattr(loc, "controlling_player", None) is not player:
                continue
            if not bool(within_objective(loc)):
                continue
            objective_locations.append(loc)
        if not objective_locations:
            return []
        objective_locations.sort(key=self._objective_sort_key)

        outcomes: list[dict] = []
        for loc in objective_locations:
            roll = int(get_roll("D6") or 0)
            mortal_wounds = 0
            if roll >= 2:
                mortal_wounds = int(get_roll("D3") or 0)
                if mortal_wounds > 0 and hasattr(enemy_unit, "_apply_mortal_wounds_to_unit"):
                    enemy_unit._apply_mortal_wounds_to_unit(enemy_unit, int(mortal_wounds), game_map=resolved_map)
            outcomes.append(
                {
                    "objective_id": str(get_entity_id(loc) or ""),
                    "objective_x": float(getattr(loc, "x", 0.0) or 0.0),
                    "objective_y": float(getattr(loc, "y", 0.0) or 0.0),
                    "roll": int(roll),
                    "mortal_wounds": int(max(0, mortal_wounds)),
                }
            )
        return outcomes

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        try:
            return unit.get_parent_army() is self.army
        except Exception:
            return False

    def _unit_is_aeldari_vehicle(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "AELDARI") and self._unit_has_keyword(unit, "VEHICLE")

    def _unit_is_aeldari_vehicle_fly(self, unit) -> bool:
        if unit is None:
            return False
        return (
            self._unit_has_keyword(unit, "AELDARI")
            and self._unit_has_keyword(unit, "VEHICLE")
            and self._unit_has_keyword(unit, "FLY")
        )

    def _unit_is_anhrathe_rangers_or_shroud_runners(self, unit) -> bool:
        if unit is None:
            return False
        return (
            self._unit_has_keyword(unit, "ANHRATHE")
            or self._unit_has_keyword(unit, "RANGERS")
            or self._unit_has_keyword(unit, "RANGER")
            or self._unit_has_keyword(unit, "SHROUD RUNNERS")
            or self._unit_has_keyword(unit, "SHROUD RUNNER")
        )

    def _unit_is_aspect_warriors(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "ASPECT WARRIORS")

    def _unit_is_avatar_of_khaine(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "AVATAR OF KHAINE")

    def skilled_crews_assault_applies(self, unit) -> bool:
        if not self.is_armoured_warhost():
            return False
        if not self._unit_in_army(unit):
            return False
        return self._unit_is_aeldari_vehicle(unit)

    def skilled_crews_reroll_advance_applies(self, unit) -> bool:
        if not self.is_armoured_warhost():
            return False
        if not self._unit_in_army(unit):
            return False
        return self._unit_is_aeldari_vehicle_fly(unit)

    def yriels_own_charge_after_advance_applies(self, unit) -> bool:
        if not self.is_eldritch_raiders():
            return False
        if not self._unit_in_army(unit):
            return False
        return self._unit_has_keyword(unit, "AELDARI")

    def yriels_own_reroll_advance_applies(self, unit) -> bool:
        if not self.is_eldritch_raiders():
            return False
        if not self._unit_in_army(unit):
            return False
        return self._unit_is_anhrathe_rangers_or_shroud_runners(unit)

    def can_charge_after_advance(self, unit, *, game=None) -> bool:
        _ = game
        return self.yriels_own_charge_after_advance_applies(unit)

    def path_of_the_warrior_applies(self, unit) -> bool:
        if not self.is_aspect_host():
            return False
        if not self._unit_in_army(unit):
            return False
        return self._unit_is_aspect_warriors(unit) or self._unit_is_avatar_of_khaine(unit)

    def _model_in_army(self, model) -> bool:
        if model is None or self.army is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None or not hasattr(unit, "get_parent_army"):
            return False
        return unit.get_parent_army() is self.army

    def _resolve_game_map(self, *, game=None, game_map=None):
        if game_map is not None:
            return game_map
        if game is not None:
            resolved = getattr(game, "map", None)
            if resolved is not None:
                return resolved
        player = getattr(self.army, "player", None) if self.army is not None else None
        game_obj = getattr(player, "game", None) if player is not None else None
        return getattr(game_obj, "map", None) if game_obj is not None else None

    def _model_matches_defend_at_all_costs(self, model) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any):
            for keyword in self._DEFEND_AT_ALL_COSTS_MODEL_KEYWORDS:
                if bool(has_any(keyword)):
                    return True
        has_kw = getattr(model, "has_keyword", None)
        if callable(has_kw):
            for keyword in self._DEFEND_AT_ALL_COSTS_MODEL_KEYWORDS:
                if bool(has_kw(keyword)):
                    return True
        model_name = str(getattr(model, "name", "") or "").strip().lower()
        if model_name:
            for snippet in self._DEFEND_AT_ALL_COSTS_MODEL_NAME_SNIPPETS:
                if snippet in model_name:
                    return True
        return False

    def _unit_within_any_objective(self, unit, game_map) -> bool:
        if unit is None or game_map is None:
            return False
        objectives = list(getattr(game_map, "objectives", []) or [])
        if not objectives:
            return False
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None:
                loc = obj
            if loc is None:
                continue
            if bool(getattr(loc, "removed", False)):
                continue
            within_fn = getattr(unit, "is_within_objective_range", None)
            if callable(within_fn) and bool(within_fn(loc)):
                return True
        return False

    def defend_at_all_costs_hit_bonus(self, model, attacker_unit, target_unit, *, game=None, game_map=None) -> tuple[int, str]:
        if not self.is_guardian_battlehost():
            return 0, ""
        if model is None or attacker_unit is None or target_unit is None:
            return 0, ""
        if not self._unit_in_army(attacker_unit):
            return 0, ""
        if not self._model_in_army(model):
            return 0, ""
        if not self._model_matches_defend_at_all_costs(model):
            return 0, ""
        resolved_map = self._resolve_game_map(game=game, game_map=game_map)
        if resolved_map is None:
            return 0, ""
        attacker_within_objective = self._unit_within_any_objective(attacker_unit, resolved_map)
        target_within_objective = self._unit_within_any_objective(target_unit, resolved_map)
        if attacker_within_objective or target_within_objective:
            return 1, "Defend at All Costs (+1 to hit near objectives)"
        return 0, ""
