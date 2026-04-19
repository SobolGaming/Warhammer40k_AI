from __future__ import annotations

from dataclasses import dataclass
import html
import re
from typing import Optional

from ..utility.ability_support import ABILITY_VOICE_OF_COMMAND, army_has_ability_id
from ..utility.entity_ids import get_entity_id
from ..utility.modifiers import Modifier, ModifierOp


@dataclass(frozen=True)
class Order:
    key: str
    name: str
    summary: str


ORDER_MOVE = Order(
    key="MOVE_MOVE_MOVE",
    name="Move! Move! Move!",
    summary="Add 3\" to Move characteristic.",
)
ORDER_FIX_BAYONETS = Order(
    key="FIX_BAYONETS",
    name="Fix Bayonets!",
    summary="Improve WS of melee weapons by 1.",
)
ORDER_TAKE_AIM = Order(
    key="TAKE_AIM",
    name="Take Aim!",
    summary="Improve BS of ranged weapons by 1.",
)
ORDER_FRFSRF = Order(
    key="FIRST_RANK_FIRE",
    name="First Rank, Fire! Second Rank, Fire!",
    summary="Improve Attacks of Rapid Fire weapons by 1.",
)
ORDER_TAKE_COVER = Order(
    key="TAKE_COVER",
    name="Take Cover!",
    summary="Improve Save by 1 (to a maximum of 3+).",
)
ORDER_DUTY_HONOUR = Order(
    key="DUTY_HONOUR",
    name="Duty and Honour!",
    summary="Improve Leadership and Objective Control by 1.",
)
ORDER_TARGET_WEAK_SPOT = Order(
    key="TARGET_WEAK_SPOT",
    name="Target Weak Spot",
    summary='Ranged attacks vs enemy units within 12" improve AP by 1.',
)
ORDER_MOVE_TO_SHADOWS = Order(
    key="MOVE_TO_SHADOWS",
    name="Move to the Shadows",
    summary="Each time a ranged attack targets this unit, it has Stealth for those attacks.",
)

ORDER_LIST: tuple[Order, ...] = (
    ORDER_MOVE,
    ORDER_FIX_BAYONETS,
    ORDER_TAKE_AIM,
    ORDER_FRFSRF,
    ORDER_TAKE_COVER,
    ORDER_DUTY_HONOUR,
)
ORDER_BY_KEY = {o.key: o for o in (ORDER_LIST + (ORDER_TARGET_WEAK_SPOT, ORDER_MOVE_TO_SHADOWS))}


class VoiceOfCommandManager:
    """
    Astra Militarum army rule: Voice of Command.
    """

    def __init__(self, army=None):
        self.army = army

    def _army_has_voice(self) -> bool:
        if self.army is None:
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "AM":
            return False
        return army_has_ability_id(self.army, ABILITY_VOICE_OF_COMMAND)

    def _unit_has_voice(self, unit) -> bool:
        if unit is None:
            return False
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            maybe_root = get_root()
            if maybe_root is not None:
                root = maybe_root
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("gsc_brood_brothers_voice_of_command_lost")):
            return False
        for ab in (list(getattr(unit, "possible_abilities", []) or []) + list(getattr(unit, "abilities", []) or [])):
            try:
                name = ab if isinstance(ab, str) else getattr(ab, "name", "")
                if "voice of command" in str(name or "").lower():
                    return True
            except Exception:
                continue
        return False

    def _unit_is_officer(self, unit) -> bool:
        try:
            return bool(unit.has_any_keyword("OFFICER"))
        except Exception:
            return False

    def _unit_is_astra_militarum(self, unit) -> bool:
        try:
            return bool(unit.has_any_keyword("ASTRA MILITARUM"))
        except Exception:
            return False

    def _unit_is_available(self, unit) -> bool:
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
            if getattr(unit, "reserve_status", "deployed") != "deployed":
                return False
        except Exception:
            pass
        try:
            emb = getattr(unit, "is_embarked", False)
            if callable(emb):
                if emb():
                    return False
            elif bool(emb):
                return False
        except Exception:
            pass
        try:
            if getattr(unit, "embarked_in", None) is not None:
                return False
        except Exception:
            pass
        return True

    def _transport_has_mobile_command_vehicle(self, transport_unit) -> bool:
        if transport_unit is None:
            return False
        for ab in self._iter_unit_abilities(transport_unit):
            try:
                text = ab if isinstance(ab, str) else getattr(ab, "description", "")
                if not text:
                    text = ab if isinstance(ab, str) else getattr(ab, "name", "")
            except Exception:
                continue
            norm = self._normalize_order_text(str(text or ""))
            if (
                "in your command phase" in norm
                and "embarked within this transport can issue orders" in norm
                and "measure distances to and from this transport" in norm
            ):
                return True
        return False

    def _mobile_command_vehicle_selected_officer_id(self, transport_unit, battle_round: int) -> str:
        if transport_unit is None or battle_round <= 0:
            return ""
        sr = getattr(transport_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return ""
        try:
            selected_round = int(sr.get("mobile_command_vehicle_round", -1) or -1)
        except Exception:
            selected_round = -1
        if selected_round != int(battle_round):
            sr.pop("mobile_command_vehicle_round", None)
            sr.pop("mobile_command_vehicle_officer_id", None)
            transport_unit.special_rules = sr
            return ""
        return str(sr.get("mobile_command_vehicle_officer_id", "") or "").strip()

    def _mark_mobile_command_vehicle_selected_officer(self, transport_unit, battle_round: int, officer_unit) -> None:
        if transport_unit is None or officer_unit is None or battle_round <= 0:
            return
        sr = getattr(transport_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["mobile_command_vehicle_round"] = int(battle_round)
        sr["mobile_command_vehicle_officer_id"] = str(get_entity_id(officer_unit) or "").strip()
        transport_unit.special_rules = sr

    def _mobile_command_vehicle_transport(
        self,
        officer_unit,
        *,
        phase_name: str = "",
        battle_round: int = 0,
        game=None,
    ):
        if officer_unit is None:
            return None
        try:
            if hasattr(officer_unit, "is_alive") and callable(officer_unit.is_alive) and not officer_unit.is_alive():
                return None
        except Exception:
            return None
        if not bool(getattr(officer_unit, "deployed", True)):
            return None
        reserve_status = str(getattr(officer_unit, "reserve_status", "deployed") or "deployed").strip().lower()
        if reserve_status not in ("deployed", "embarked"):
            return None
        transport = getattr(officer_unit, "embarked_in", None)
        if transport is None:
            return None
        if not self._transport_has_mobile_command_vehicle(transport):
            return None
        pname = str(phase_name or "").strip().upper()
        if not pname:
            game_obj = game
            if game_obj is None:
                try:
                    army = officer_unit.get_parent_army()
                except Exception:
                    army = None
                game_obj = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            pname = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return None
        if not self._unit_is_available(transport):
            return None
        if battle_round <= 0:
            game_obj = game
            if game_obj is None:
                try:
                    army = officer_unit.get_parent_army()
                except Exception:
                    army = None
                game_obj = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            try:
                battle_round = int(getattr(game_obj, "turn", 0) or 0)
            except Exception:
                battle_round = 0
        officer_id = str(get_entity_id(officer_unit) or "").strip()
        selected_officer_id = self._mobile_command_vehicle_selected_officer_id(transport, battle_round)
        if selected_officer_id and officer_id and selected_officer_id != officer_id:
            return None
        return transport

    def _mechanised_vox_relay_transport(
        self,
        officer_unit,
        *,
        phase_name: str = "",
        battle_round: int = 0,
        game=None,
    ):
        if officer_unit is None:
            return None
        transport = getattr(officer_unit, "embarked_in", None)
        if transport is None:
            return None
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("mechanised_vox_relay_active", False)):
            return None
        pname = str(phase_name or "").strip().upper()
        game_obj = game
        if game_obj is None:
            try:
                army = officer_unit.get_parent_army()
            except Exception:
                army = None
            game_obj = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        if not pname:
            pname = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return None
        exp_phase = str(sr.get("mechanised_vox_relay_expires_phase", "") or "").strip().upper()
        if exp_phase and exp_phase != pname:
            return None
        if battle_round <= 0:
            try:
                battle_round = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
            except Exception:
                battle_round = 0
        try:
            relay_round = int(sr.get("mechanised_vox_relay_turn", 0) or 0)
        except Exception:
            relay_round = 0
        if relay_round > 0 and battle_round > 0 and relay_round != battle_round:
            return None
        owner_id = str(sr.get("mechanised_vox_relay_owner", "") or "").strip()
        current_owner = str(getattr(getattr(game_obj, "get_current_player", lambda: None)(), "id", "") or "").strip() if game_obj is not None else ""
        if owner_id and current_owner and owner_id != current_owner:
            return None
        relay_transport_id = str(sr.get("mechanised_vox_relay_transport_id", "") or "").strip()
        transport_id = str(get_entity_id(transport) or "").strip()
        if relay_transport_id and transport_id and relay_transport_id != transport_id:
            return None
        if not self._unit_is_available(transport):
            return None
        return transport

    def _unit_is_battleshocked(self, unit) -> bool:
        try:
            if hasattr(unit, "is_battle_shocked") and callable(unit.is_battle_shocked):
                return bool(unit.is_battle_shocked())
        except Exception:
            return False
        return False

    def _strip_html(self, text: str) -> str:
        raw = re.sub(r"<[^>]+>", " ", str(text or ""))
        raw = html.unescape(raw)
        raw = raw.replace("\u2019", "'").replace("\u2018", "'")
        raw = raw.replace("\u0192?T", "'")
        raw = re.sub(r"\s+", " ", raw).strip()
        return raw

    def _normalize_order_text(self, text: str) -> str:
        clean = self._strip_html(text)
        clean = clean.replace("\u2019", "'").replace("\u2018", "'")
        clean = clean.lower()
        clean = re.sub(r"[^a-z0-9\s']", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def _iter_unit_abilities(self, unit):
        if unit is None:
            return
        for ab in (list(getattr(unit, "possible_abilities", []) or []) + list(getattr(unit, "abilities", []) or [])):
            yield ab

    def _parse_orders_profile(self, unit) -> tuple[int, list[str], list[str]]:
        count = 1
        keywords: list[str] = []
        allowed_order_keys: list[str] = []
        for ab in self._iter_unit_abilities(unit):
            try:
                name = ab if isinstance(ab, str) else getattr(ab, "name", "")
                if "orders" not in str(name or "").lower():
                    continue
                desc = ab if isinstance(ab, str) else getattr(ab, "description", "")
                text = self._strip_html(desc)
                m = re.search(r"issue\s+(?:up\s+to\s+)?(\d+)\s+orders?", text, flags=re.IGNORECASE)
                if m:
                    count = int(m.group(1))
                target_match = re.search(r"orders?\s+to\s*:?\s*(.+?)(?:\.|$)", text, flags=re.IGNORECASE)
                if target_match:
                    seg = target_match.group(1)
                    seg = re.split(r"\bwithin\b", seg, maxsplit=1, flags=re.IGNORECASE)[0]
                    seg = seg.replace(":", " ")
                    seg = re.sub(r"\b(friendly|eligible)\b", "", seg, flags=re.IGNORECASE)
                    raw_parts = re.split(r"\bunits?\b", seg, flags=re.IGNORECASE)
                    parsed: list[str] = []
                    for part in raw_parts:
                        part = part.strip(" ,;:")
                        if not part:
                            continue
                        part = re.sub(r"^(?:a|an|the)\s+", "", part, flags=re.IGNORECASE)
                        for token in re.split(r",|\bor\b|\band\b", part, flags=re.IGNORECASE):
                            token = token.strip()
                            if token:
                                parsed.append(token.upper())
                    seen = set()
                    keywords = []
                    for item in parsed:
                        if item in seen:
                            continue
                        seen.add(item)
                        keywords.append(item)
                if "can only issue" in text.lower():
                    norm_text = self._normalize_order_text(text)
                    allowed = []
                    for order in ORDER_LIST:
                        name_norm = self._normalize_order_text(order.name)
                        if name_norm and name_norm in norm_text:
                            allowed.append(order.key)
                    allowed_order_keys = allowed
                break
            except Exception:
                continue
        return count, keywords, allowed_order_keys

    def _parse_order_range_override_from_text(self, text: str) -> float:
        rules = self._strip_html(text).lower().replace("\u2019", "'").replace("\u2018", "'")
        if "issues an order" not in rules or "eligible unit up to" not in rules:
            return 0.0
        pattern = (
            r"each time\s+"
            r"(?:this model|the officer in the bearer'?s unit)\s+"
            r"issues?\s+an?\s+order\s*,?\s*"
            r"it\s+can\s+issue\s+(?:it|that order)\s+to\s+an?\s+eligible\s+unit\s+"
            r"up\s+to\s+(\d+(?:\.\d+)?)\s*(?:\"|inches?)?\s*away"
        )
        m = re.search(pattern, rules, flags=re.IGNORECASE)
        if not m:
            return 0.0
        try:
            value = float(m.group(1) or 0.0)
        except Exception:
            return 0.0
        if value <= 0:
            return 0.0
        return value

    def _officer_order_range_from_abilities(self, officer_unit) -> float:
        if officer_unit is None:
            return 0.0
        max_range = 0.0
        for ab in self._iter_unit_abilities(officer_unit):
            try:
                text = ab if isinstance(ab, str) else getattr(ab, "description", "")
                if not text:
                    text = ab if isinstance(ab, str) else getattr(ab, "name", "")
            except Exception:
                continue
            parsed = self._parse_order_range_override_from_text(str(text or ""))
            if parsed > max_range:
                max_range = parsed
        return max_range

    def _order_issued_state(self, unit, battle_round: int) -> int:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        try:
            round_key = int(sr.get("voice_of_command_orders_round", -1))
        except Exception:
            round_key = -1
        if round_key != int(battle_round):
            sr["voice_of_command_orders_round"] = int(battle_round)
            sr["voice_of_command_orders_issued"] = 0
        unit.special_rules = sr
        try:
            return int(sr.get("voice_of_command_orders_issued", 0) or 0)
        except Exception:
            return 0

    def _set_orders_issued(self, unit, battle_round: int, value: int) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["voice_of_command_orders_round"] = int(battle_round)
        sr["voice_of_command_orders_issued"] = int(value)
        unit.special_rules = sr

    def _unit_has_enhancement_flag(self, unit, flag_key: str) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        return bool(sr.get(str(flag_key or "").strip()))

    def _officer_has_abhuman_detail(self, officer_unit) -> bool:
        return self._unit_has_enhancement_flag(officer_unit, "enhancement_abhuman_detail")

    def _officer_has_aquilan_eye(self, officer_unit) -> bool:
        return self._unit_has_enhancement_flag(officer_unit, "enhancement_aquilan_eye")

    def _officer_has_spec_ops_veteran(self, officer_unit) -> bool:
        return self._unit_has_enhancement_flag(officer_unit, "enhancement_spec_ops_veteran")

    def _officer_has_laud_hailer(self, officer_unit) -> bool:
        return self._unit_has_enhancement_flag(officer_unit, "enhancement_laud_hailer")

    def _officer_has_bombast_class_vox_array(self, officer_unit) -> bool:
        return self._unit_has_enhancement_flag(officer_unit, "enhancement_bombast_class_vox_array")

    def _officer_has_calm_under_fire(self, officer_unit) -> bool:
        return self._unit_has_enhancement_flag(officer_unit, "enhancement_calm_under_fire")

    def _officer_has_siege_over_the_top_active(self, officer_unit, battle_round: int, *, game=None) -> bool:
        if officer_unit is None:
            return False
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("siege_regiment_over_the_top_active", False)):
            return False
        try:
            marked_round = int(sr.get("siege_regiment_over_the_top_turn", 0) or 0)
        except Exception:
            marked_round = 0
        if marked_round and battle_round and marked_round != int(battle_round):
            return False
        game_obj = game
        if game_obj is None:
            try:
                army = officer_unit.get_parent_army()
            except Exception:
                army = None
            game_obj = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        phase_name = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper() if game_obj is not None else ""
        expires_phase = str(sr.get("siege_regiment_over_the_top_expires_phase", "") or "").strip().upper()
        if expires_phase and phase_name and expires_phase != phase_name:
            return False
        owner_id = str(sr.get("siege_regiment_over_the_top_turn_owner", "") or "").strip()
        current_player = getattr(game_obj, "get_current_player", lambda: None)() if game_obj is not None else None
        current_owner_id = str(getattr(current_player, "id", "") or "").strip()
        if owner_id and current_owner_id and owner_id != current_owner_id:
            return False
        return True

    def _calm_under_fire_order_target_keyword(self, officer_unit) -> str:
        sr = getattr(officer_unit, "special_rules", None)
        if isinstance(sr, dict):
            keyword = str(
                sr.get("enhancement_calm_under_fire_order_target_keyword", "SQUADRON") or "SQUADRON"
            ).strip().upper()
            if keyword:
                return keyword
        return "SQUADRON"

    def _calm_under_fire_additional_targets(self, officer_unit) -> int:
        sr = getattr(officer_unit, "special_rules", None)
        if isinstance(sr, dict):
            try:
                value = int(sr.get("enhancement_calm_under_fire_additional_targets", 1) or 1)
            except Exception:
                value = 1
            return max(0, int(value))
        return 1

    def _calm_under_fire_once_per_turn(self, officer_unit) -> bool:
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return True
        return bool(sr.get("enhancement_calm_under_fire_once_per_turn", True))

    def _officer_calm_under_fire_used_this_round(self, officer_unit, battle_round: int) -> bool:
        if not self._calm_under_fire_once_per_turn(officer_unit):
            return False
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        try:
            used_round = int(sr.get("enhancement_calm_under_fire_used_round", -1) or -1)
        except Exception:
            used_round = -1
        return used_round == int(battle_round)

    def _bombast_order_target_keyword(self, officer_unit) -> str:
        sr = getattr(officer_unit, "special_rules", None)
        if isinstance(sr, dict):
            keyword = str(
                sr.get("enhancement_bombast_class_vox_array_order_target_keyword", "REGIMENT") or "REGIMENT"
            ).strip().upper()
            if keyword:
                return keyword
        return "REGIMENT"

    def _bombast_max_targets(self, officer_unit) -> int:
        sr = getattr(officer_unit, "special_rules", None)
        if isinstance(sr, dict):
            try:
                val = int(sr.get("enhancement_bombast_class_vox_array_max_targets", 3) or 3)
            except Exception:
                val = 3
            return max(1, int(val))
        return 3

    def _bombast_requires_master_vox(self, officer_unit) -> bool:
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return True
        return bool(sr.get("enhancement_bombast_class_vox_array_requires_master_vox", True))

    def _officer_unit_has_master_vox(self, officer_unit) -> bool:
        if officer_unit is None:
            return False
        root = officer_unit
        get_root = getattr(officer_unit, "get_attached_unit_root", None)
        if callable(get_root):
            maybe_root = get_root()
            if maybe_root is not None:
                root = maybe_root

        members = []
        get_members = getattr(root, "get_attached_unit_members", None)
        if callable(get_members):
            members = list(get_members() or [])
        if not members:
            members = [root]

        for unit in members:
            if unit is None:
                continue
            has_wargear_named = getattr(unit, "_has_wargear_named", None)
            if callable(has_wargear_named):
                try:
                    if bool(has_wargear_named("master vox")):
                        return True
                except Exception:
                    pass
            for model in list(getattr(unit, "models", []) or []):
                for wargear in list(getattr(model, "wargear", []) or []):
                    name = self._normalize_order_text(str(getattr(wargear, "name", "") or ""))
                    if "master vox" in name:
                        return True
                for optional_wargear in list(getattr(model, "optional_wargear", []) or []):
                    name = self._normalize_order_text(str(optional_wargear or ""))
                    if "master vox" in name:
                        return True
            for ability in self._iter_unit_abilities(unit):
                try:
                    ability_name = ability if isinstance(ability, str) else getattr(ability, "name", "")
                except Exception:
                    ability_name = ""
                try:
                    ability_desc = ability if isinstance(ability, str) else getattr(ability, "description", "")
                except Exception:
                    ability_desc = ""
                if "master vox" in self._normalize_order_text(str(ability_name or "")):
                    return True
                if "master vox" in self._normalize_order_text(str(ability_desc or "")):
                    return True
        return False

    def _officer_bombast_multi_target_available(self, officer_unit) -> bool:
        if not self._officer_has_bombast_class_vox_array(officer_unit):
            return False
        if self._bombast_max_targets(officer_unit) <= 1:
            return False
        if self._bombast_requires_master_vox(officer_unit) and not self._officer_unit_has_master_vox(officer_unit):
            return False
        return True

    def _officer_calm_under_fire_multi_target_available(self, officer_unit, battle_round: int) -> bool:
        if not self._officer_has_calm_under_fire(officer_unit):
            return False
        if self._calm_under_fire_additional_targets(officer_unit) <= 0:
            return False
        if self._officer_calm_under_fire_used_this_round(officer_unit, battle_round):
            return False
        return True

    def _target_matches_siege_over_the_top_keyword(self, target_unit) -> bool:
        return self._target_has_keyword(target_unit, "INFANTRY") and self._target_has_keyword(target_unit, "REGIMENT")

    def _target_has_keyword(self, target_unit, keyword: str) -> bool:
        key = str(keyword or "").strip().upper()
        if not key:
            return True
        try:
            return bool(target_unit.has_any_keyword(key))
        except Exception:
            return False

    def _target_matches_bombast_keyword(self, officer_unit, target_unit) -> bool:
        return self._target_has_keyword(target_unit, self._bombast_order_target_keyword(officer_unit))

    def _target_matches_calm_under_fire_keyword(self, officer_unit, target_unit) -> bool:
        return self._target_has_keyword(target_unit, self._calm_under_fire_order_target_keyword(officer_unit))

    @staticmethod
    def _normalise_order_key_list(values) -> list[str]:
        keys: list[str] = []
        for raw in list(values or []):
            key = str(raw or "").strip().upper()
            if not key or key not in ORDER_BY_KEY or key in keys:
                continue
            keys.append(key)
        return keys

    @staticmethod
    def _attached_unit_root(unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
            if root is not None:
                return root
        return unit

    @staticmethod
    def _attached_unit_members(root) -> list:
        if root is None:
            return []
        members = []
        get_members = getattr(root, "get_attached_unit_members", None)
        if callable(get_members):
            members = list(get_members() or [])
        if not members:
            members = [root]
        return members

    def _attached_unit_order_keys(self, unit) -> list[str]:
        root = self._attached_unit_root(unit)
        if root is None:
            return []
        members = self._attached_unit_members(root)
        keys: list[str] = []
        for member in members:
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            active_key = str(sr.get("voice_of_command_order_key", "") or "").strip().upper()
            if active_key in ORDER_BY_KEY and active_key not in keys:
                keys.append(active_key)
            for extra_key in self._normalise_order_key_list(sr.get("voice_of_command_additional_order_keys", [])):
                if extra_key not in keys:
                    keys.append(extra_key)
            for temp_key in self._normalise_order_key_list(sr.get("voice_of_command_temp_order_keys", [])):
                if temp_key not in keys:
                    keys.append(temp_key)
        return keys

    def _attached_unit_permanent_order_keys(self, unit) -> list[str]:
        root = self._attached_unit_root(unit)
        if root is None:
            return []
        members = self._attached_unit_members(root)
        keys: list[str] = []
        for member in members:
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            active_key = str(sr.get("voice_of_command_order_key", "") or "").strip().upper()
            if active_key in ORDER_BY_KEY and active_key not in keys:
                keys.append(active_key)
            for extra_key in self._normalise_order_key_list(sr.get("voice_of_command_additional_order_keys", [])):
                if extra_key not in keys:
                    keys.append(extra_key)
        return keys

    def get_active_order_keys(self, unit) -> list[str]:
        return list(self._attached_unit_order_keys(unit))

    def get_permanent_order_keys(self, unit) -> list[str]:
        return list(self._attached_unit_permanent_order_keys(unit))

    def attached_unit_has_any_order(self, unit) -> bool:
        return bool(self._attached_unit_order_keys(unit))

    def _refresh_order_state_for_unit_and_attached(self, unit) -> None:
        root = self._attached_unit_root(unit)
        if root is None:
            return
        units = [root]
        units.extend(list(getattr(root, "attached_leaders", []) or []))
        for member in units:
            if member is None or not self._unit_is_astra_militarum(member):
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            active_key = str(sr.get("voice_of_command_order_key", "") or "").strip().upper()
            if active_key not in ORDER_BY_KEY:
                for key in (
                    "voice_of_command_order_key",
                    "voice_of_command_order_owner",
                    "voice_of_command_order_source",
                ):
                    sr.pop(key, None)
                active_key = ""
            additional_keys = self._normalise_order_key_list(sr.get("voice_of_command_additional_order_keys", []))
            temp_keys = self._normalise_order_key_list(sr.get("voice_of_command_temp_order_keys", []))
            if additional_keys:
                sr["voice_of_command_additional_order_keys"] = list(additional_keys)
            else:
                sr.pop("voice_of_command_additional_order_keys", None)
            if temp_keys:
                sr["voice_of_command_temp_order_keys"] = list(temp_keys)
            else:
                sr.pop("voice_of_command_temp_order_keys", None)
            sr.pop("voice_of_command_take_cover_cap", None)
            member.special_rules = sr
            try:
                member.remove_characteristic_modifiers_by_source("voice_of_command:")
            except Exception:
                pass
            try:
                member.remove_characteristic_modifiers_by_source("voice_of_command_temp:")
            except Exception:
                pass
            if active_key:
                self._apply_order_modifiers(member, active_key, source_prefix="voice_of_command:")
            for extra_key in additional_keys:
                self._apply_order_modifiers(member, extra_key, source_prefix="voice_of_command:")
            for temp_key in temp_keys:
                self._apply_order_modifiers(member, temp_key, source_prefix="voice_of_command_temp:")

    def _set_temp_order_keys_on_unit_and_attached(self, unit, order_keys: list[str]) -> None:
        root = self._attached_unit_root(unit)
        if root is None:
            return
        temp_keys = self._normalise_order_key_list(order_keys)
        units = [root]
        units.extend(list(getattr(root, "attached_leaders", []) or []))
        for member in units:
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if temp_keys:
                sr["voice_of_command_temp_order_keys"] = list(temp_keys)
            else:
                sr.pop("voice_of_command_temp_order_keys", None)
            member.special_rules = sr
        self._refresh_order_state_for_unit_and_attached(root)

    def _current_game(self):
        player = getattr(self.army, "player", None) if self.army is not None else None
        return getattr(player, "game", None) if player is not None else None

    def _resolve_army_root_by_id(self, entity_id: str):
        wanted = str(entity_id or "").strip()
        if not wanted or self.army is None:
            return None
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_unit_root(unit)
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "").strip()
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if root_id == wanted:
                return root
        return None

    def _active_player_id(self, game=None) -> str:
        game_obj = game if game is not None else self._current_game()
        active_player = getattr(game_obj, "get_current_player", lambda: None)() if game_obj is not None else None
        return str(getattr(active_player, "id", "") or "")

    @staticmethod
    def _phase_key(phase_name: str) -> str:
        return str(phase_name or "").strip().upper().replace(" ", "_")

    def _clear_inspired_command_pending_for_officer(self, officer_unit) -> None:
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "combined_arms_inspired_command_pending_round",
            "combined_arms_inspired_command_pending",
        ):
            sr.pop(key, None)
        officer_unit.special_rules = sr

    def _clear_inspired_command_pending(self) -> None:
        if self.army is None:
            return
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            self._clear_inspired_command_pending_for_officer(unit)

    def _inspired_command_pending_state(self, officer_unit, battle_round: int) -> int:
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return 0
        try:
            pending_round = int(sr.get("combined_arms_inspired_command_pending_round", -1) or -1)
        except Exception:
            pending_round = -1
        if pending_round != int(battle_round):
            self._clear_inspired_command_pending_for_officer(officer_unit)
            return 0
        return 1 if bool(sr.get("combined_arms_inspired_command_pending")) else 0

    def start_inspired_command_pending(self, officers, battle_round: int) -> list:
        self._clear_inspired_command_pending()
        applied: list = []
        seen: set[str] = set()
        for officer in list(officers or []):
            root = self._attached_unit_root(officer)
            if root is None:
                continue
            unit_id = str(get_entity_id(root) or "").strip()
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["combined_arms_inspired_command_pending_round"] = int(battle_round)
            sr["combined_arms_inspired_command_pending"] = True
            root.special_rules = sr
            applied.append(root)
        return applied

    def _consume_inspired_command_pending_order(self, officer_unit, battle_round: int) -> bool:
        if self._inspired_command_pending_state(officer_unit, battle_round) <= 0:
            return False
        self._clear_inspired_command_pending()
        return True

    def consume_inspired_command_skip(self, officer_unit=None, *, game=None, battle_round: int | None = None) -> bool:
        round_now = 0
        if battle_round is not None:
            try:
                round_now = int(battle_round or 0)
            except Exception:
                round_now = 0
        if round_now <= 0:
            game_obj = game if game is not None else self._current_game()
            try:
                round_now = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
            except Exception:
                round_now = 0
        if round_now <= 0:
            round_now = 1
        had_pending = False
        if self.army is not None:
            for unit in list(getattr(self.army, "units", []) or []):
                if self._inspired_command_pending_state(unit, round_now) > 0:
                    had_pending = True
                    break
        self._clear_inspired_command_pending()
        return had_pending

    def _set_coordinated_action_state(self, unit, partner_unit, *, battle_round: int, phase_name: str, owner_id: str, source: str = "") -> None:
        root = self._attached_unit_root(unit)
        partner_root = self._attached_unit_root(partner_unit)
        if root is None or partner_root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["voice_of_command_coordinated_action_partner_id"] = str(get_entity_id(partner_root) or "")
        sr["voice_of_command_coordinated_action_round"] = int(battle_round)
        sr["voice_of_command_coordinated_action_phase"] = self._phase_key(phase_name)
        sr["voice_of_command_coordinated_action_owner"] = str(owner_id or "")
        sr["voice_of_command_coordinated_action_source"] = str(source or "COORDINATED ACTION").strip() or "COORDINATED ACTION"
        root.special_rules = sr

    def _clear_coordinated_action_state_for_unit(self, unit) -> None:
        root = self._attached_unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        for key in (
            "voice_of_command_coordinated_action_partner_id",
            "voice_of_command_coordinated_action_round",
            "voice_of_command_coordinated_action_phase",
            "voice_of_command_coordinated_action_owner",
            "voice_of_command_coordinated_action_source",
        ):
            sr.pop(key, None)
        sr.pop("voice_of_command_temp_order_keys", None)
        root.special_rules = sr
        self._refresh_order_state_for_unit_and_attached(root)

    def _coordinated_action_partner(self, unit, *, game=None, battle_round: int | None = None, phase_name: str = "", owner_id: str = ""):
        root = self._attached_unit_root(unit)
        if root is None:
            return None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None
        partner_id = str(sr.get("voice_of_command_coordinated_action_partner_id", "") or "").strip()
        if not partner_id:
            return None
        game_obj = game if game is not None else self._current_game()
        round_now = int(battle_round or 0)
        if round_now <= 0:
            try:
                round_now = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
            except Exception:
                round_now = 0
        phase_key = self._phase_key(phase_name)
        if not phase_key and game_obj is not None:
            phase_key = self._phase_key(getattr(getattr(game_obj, "phase", None), "name", "") or "")
        current_owner = str(owner_id or "")
        if not current_owner:
            current_owner = self._active_player_id(game_obj)
        try:
            marked_round = int(sr.get("voice_of_command_coordinated_action_round", -1) or -1)
        except Exception:
            marked_round = -1
        marked_phase = self._phase_key(str(sr.get("voice_of_command_coordinated_action_phase", "") or ""))
        marked_owner = str(sr.get("voice_of_command_coordinated_action_owner", "") or "")
        if round_now > 0 and marked_round > 0 and marked_round != round_now:
            return None
        if phase_key and marked_phase and marked_phase != phase_key:
            return None
        if current_owner and marked_owner and marked_owner != current_owner:
            return None
        return self._resolve_army_root_by_id(partner_id)

    def _sync_coordinated_action_pair(self, unit, *, game=None, battle_round: int | None = None, phase_name: str = "", owner_id: str = "") -> None:
        root = self._attached_unit_root(unit)
        if root is None:
            return
        partner = self._coordinated_action_partner(
            root,
            game=game,
            battle_round=battle_round,
            phase_name=phase_name,
            owner_id=owner_id,
        )
        if partner is None:
            self._set_temp_order_keys_on_unit_and_attached(root, [])
            return
        root_permanent = self._attached_unit_permanent_order_keys(root)
        partner_permanent = self._attached_unit_permanent_order_keys(partner)
        root_temp = [key for key in partner_permanent if key not in root_permanent]
        partner_temp = [key for key in root_permanent if key not in partner_permanent]
        self._set_temp_order_keys_on_unit_and_attached(root, root_temp)
        self._set_temp_order_keys_on_unit_and_attached(partner, partner_temp)

    def set_coordinated_action_pair(self, regiment_unit, squadron_unit, *, game=None, phase_name: str = "", source: str = "") -> bool:
        regiment_root = self._attached_unit_root(regiment_unit)
        squadron_root = self._attached_unit_root(squadron_unit)
        if regiment_root is None or squadron_root is None or regiment_root is squadron_root:
            return False
        game_obj = game if game is not None else self._current_game()
        try:
            battle_round = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
        except Exception:
            battle_round = 0
        phase_text = str(phase_name or getattr(getattr(game_obj, "phase", None), "name", "") or "")
        owner_id = self._active_player_id(game_obj)
        self._set_coordinated_action_state(
            regiment_root,
            squadron_root,
            battle_round=battle_round,
            phase_name=phase_text,
            owner_id=owner_id,
            source=source,
        )
        self._set_coordinated_action_state(
            squadron_root,
            regiment_root,
            battle_round=battle_round,
            phase_name=phase_text,
            owner_id=owner_id,
            source=source,
        )
        self._sync_coordinated_action_pair(
            regiment_root,
            game=game_obj,
            battle_round=battle_round,
            phase_name=phase_text,
            owner_id=owner_id,
        )
        return True

    def clear_coordinated_action_phase_effects(self, *, phase_name: str = "", player=None, game=None, battle_round: int | None = None) -> None:
        if self.army is None:
            return
        game_obj = game if game is not None else self._current_game()
        phase_key = self._phase_key(phase_name)
        if not phase_key and game_obj is not None:
            phase_key = self._phase_key(getattr(getattr(game_obj, "phase", None), "name", "") or "")
        round_now = int(battle_round or 0)
        if round_now <= 0:
            try:
                round_now = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
            except Exception:
                round_now = 0
        owner_id = str(getattr(player, "id", "") or "")
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_unit_root(unit)
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "").strip()
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            partner_id = str(sr.get("voice_of_command_coordinated_action_partner_id", "") or "").strip()
            if not partner_id:
                continue
            try:
                marked_round = int(sr.get("voice_of_command_coordinated_action_round", -1) or -1)
            except Exception:
                marked_round = -1
            marked_phase = self._phase_key(str(sr.get("voice_of_command_coordinated_action_phase", "") or ""))
            marked_owner = str(sr.get("voice_of_command_coordinated_action_owner", "") or "")
            if round_now > 0 and marked_round > 0 and marked_round != round_now:
                continue
            if phase_key and marked_phase and marked_phase != phase_key:
                continue
            if owner_id and marked_owner and marked_owner != owner_id:
                continue
            self._clear_coordinated_action_state_for_unit(root)

    def _attached_unit_command_rod_order_capacity(self, unit) -> int:
        root = self._attached_unit_root(unit)
        if root is None:
            return 1
        members = self._attached_unit_members(root)
        seen_ids: set[str] = set()
        for member in members:
            if member is None or member is root:
                continue
            member_id = str(get_entity_id(member) or "").strip()
            if member_id and member_id in seen_ids:
                continue
            if member_id:
                seen_ids.add(member_id)
            attached_root = self._attached_unit_root(getattr(member, "attached_to", None))
            if attached_root is not root:
                continue
            for ability in self._iter_unit_abilities(member):
                try:
                    text = ability if isinstance(ability, str) else getattr(ability, "description", "")
                    if not text:
                        text = ability if isinstance(ability, str) else getattr(ability, "name", "")
                except Exception:
                    continue
                norm = self._normalize_order_text(str(text or ""))
                if re.fullmatch(
                    r"while (?:the bearer|this model) is leading a unit that unit can be affected by up to two different orders at the same time",
                    norm,
                ):
                    return 2
        return 1

    def _set_orders_on_unit_and_attached(self, unit, order_keys: list[str], owner_id: str, source_id: str) -> None:
        if unit is None:
            return
        root = self._attached_unit_root(unit)
        if root is None:
            return
        keys = self._normalise_order_key_list(order_keys)
        units = [root]
        units.extend(list(getattr(root, "attached_leaders", []) or []))
        for member in units:
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            for key in (
                "voice_of_command_order_key",
                "voice_of_command_order_owner",
                "voice_of_command_order_source",
                "voice_of_command_additional_order_keys",
            ):
                sr.pop(key, None)
            member.special_rules = sr
        if not keys:
            self._refresh_order_state_for_unit_and_attached(root)
            return
        self._apply_order_to_unit_and_attached(root, keys[0], owner_id, source_id)
        if len(keys) > 1:
            for member in units:
                if member is None:
                    continue
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["voice_of_command_additional_order_keys"] = list(keys[1:])
                member.special_rules = sr
        self._refresh_order_state_for_unit_and_attached(root)

    @staticmethod
    def _enhancement_bearer_alive(unit, sr, *, bearer_key: str = "") -> bool:
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

    def _stalwarts_honours_additional_order_key(self, target_unit) -> str:
        root = self._attached_unit_root(target_unit)
        if root is None:
            return ""
        members = self._attached_unit_members(root)
        for leader in list(getattr(root, "attached_leaders", []) or []):
            if leader is None or leader in members:
                continue
            members.append(leader)
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("enhancement_stalwarts_honours", False)):
                continue
            if not self._enhancement_bearer_alive(
                member,
                sr,
                bearer_key="enhancement_stalwarts_honours_bearer_model_id",
            ):
                continue
            if bool(sr.get("enhancement_stalwarts_honours_requires_leading", True)):
                attached_root = self._attached_unit_root(getattr(member, "attached_to", None))
                if attached_root is None or attached_root is not root:
                    continue
            key = str(sr.get("enhancement_stalwarts_honours_additional_order_key", "TAKE_COVER") or "TAKE_COVER").strip().upper()
            if key in ORDER_BY_KEY:
                return key
        return ""

    def _clear_bombast_pending(self, officer_unit) -> None:
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "enhancement_bombast_class_vox_array_pending_round",
            "enhancement_bombast_class_vox_array_pending_order_key",
            "enhancement_bombast_class_vox_array_pending_remaining_targets",
            "enhancement_bombast_class_vox_array_pending_target_ids",
        ):
            sr.pop(key, None)
        officer_unit.special_rules = sr

    def _bombast_pending_state(self, officer_unit, battle_round: int) -> dict:
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return {}
        try:
            pending_round = int(sr.get("enhancement_bombast_class_vox_array_pending_round", -1) or -1)
        except Exception:
            pending_round = -1
        if pending_round != int(battle_round):
            self._clear_bombast_pending(officer_unit)
            return {}
        order_key = str(
            sr.get("enhancement_bombast_class_vox_array_pending_order_key", "") or ""
        ).strip().upper()
        try:
            remaining = int(sr.get("enhancement_bombast_class_vox_array_pending_remaining_targets", 0) or 0)
        except Exception:
            remaining = 0
        if not order_key or remaining <= 0:
            self._clear_bombast_pending(officer_unit)
            return {}
        selected_ids: set[str] = set()
        for raw in list(sr.get("enhancement_bombast_class_vox_array_pending_target_ids", []) or []):
            text = str(raw or "").strip()
            if text:
                selected_ids.add(text)
        return {
            "order_key": order_key,
            "remaining_targets": int(remaining),
            "selected_target_ids": selected_ids,
        }

    def _start_bombast_pending(self, officer_unit, battle_round: int, order_key: str, target_unit_id: str) -> None:
        remaining = self._bombast_max_targets(officer_unit) - 1
        if remaining <= 0:
            self._clear_bombast_pending(officer_unit)
            return
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["enhancement_bombast_class_vox_array_pending_round"] = int(battle_round)
        sr["enhancement_bombast_class_vox_array_pending_order_key"] = str(order_key or "").strip().upper()
        sr["enhancement_bombast_class_vox_array_pending_remaining_targets"] = int(remaining)
        target_ids = []
        text = str(target_unit_id or "").strip()
        if text:
            target_ids.append(text)
        sr["enhancement_bombast_class_vox_array_pending_target_ids"] = target_ids
        officer_unit.special_rules = sr

    def _consume_bombast_pending_target(self, officer_unit, battle_round: int, target_unit_id: str) -> None:
        pending = self._bombast_pending_state(officer_unit, battle_round)
        if not pending:
            return
        order_key = str(pending.get("order_key", "") or "").strip().upper()
        selected = {str(v or "").strip() for v in list(pending.get("selected_target_ids", set()) or set()) if str(v or "").strip()}
        text = str(target_unit_id or "").strip()
        if text:
            selected.add(text)
        remaining = int(pending.get("remaining_targets", 0) or 0) - 1
        if remaining <= 0:
            self._clear_bombast_pending(officer_unit)
            return
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["enhancement_bombast_class_vox_array_pending_round"] = int(battle_round)
        sr["enhancement_bombast_class_vox_array_pending_order_key"] = order_key
        sr["enhancement_bombast_class_vox_array_pending_remaining_targets"] = int(remaining)
        sr["enhancement_bombast_class_vox_array_pending_target_ids"] = sorted(selected)
        officer_unit.special_rules = sr

    def _officer_has_bombast_pending_targets(self, officer_unit, battle_round: int) -> bool:
        return bool(self._bombast_pending_state(officer_unit, battle_round))

    def _clear_calm_under_fire_pending(self, officer_unit) -> None:
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "enhancement_calm_under_fire_pending_round",
            "enhancement_calm_under_fire_pending_order_key",
            "enhancement_calm_under_fire_pending_remaining_targets",
            "enhancement_calm_under_fire_pending_target_ids",
        ):
            sr.pop(key, None)
        officer_unit.special_rules = sr

    def _calm_under_fire_pending_state(self, officer_unit, battle_round: int) -> dict:
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return {}
        try:
            pending_round = int(sr.get("enhancement_calm_under_fire_pending_round", -1) or -1)
        except Exception:
            pending_round = -1
        if pending_round != int(battle_round):
            self._clear_calm_under_fire_pending(officer_unit)
            return {}
        order_key = str(sr.get("enhancement_calm_under_fire_pending_order_key", "") or "").strip().upper()
        try:
            remaining = int(sr.get("enhancement_calm_under_fire_pending_remaining_targets", 0) or 0)
        except Exception:
            remaining = 0
        if not order_key or remaining <= 0:
            self._clear_calm_under_fire_pending(officer_unit)
            return {}
        selected_ids: set[str] = set()
        for raw in list(sr.get("enhancement_calm_under_fire_pending_target_ids", []) or []):
            text = str(raw or "").strip()
            if text:
                selected_ids.add(text)
        return {
            "order_key": order_key,
            "remaining_targets": int(remaining),
            "selected_target_ids": selected_ids,
        }

    def _start_calm_under_fire_pending(self, officer_unit, battle_round: int, order_key: str, target_unit_id: str) -> None:
        remaining = self._calm_under_fire_additional_targets(officer_unit)
        if remaining <= 0:
            self._clear_calm_under_fire_pending(officer_unit)
            return
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["enhancement_calm_under_fire_pending_round"] = int(battle_round)
        sr["enhancement_calm_under_fire_pending_order_key"] = str(order_key or "").strip().upper()
        sr["enhancement_calm_under_fire_pending_remaining_targets"] = int(remaining)
        target_ids = []
        text = str(target_unit_id or "").strip()
        if text:
            target_ids.append(text)
        sr["enhancement_calm_under_fire_pending_target_ids"] = target_ids
        officer_unit.special_rules = sr

    def _consume_calm_under_fire_pending_target(self, officer_unit, battle_round: int, target_unit_id: str) -> None:
        pending = self._calm_under_fire_pending_state(officer_unit, battle_round)
        if not pending:
            return
        order_key = str(pending.get("order_key", "") or "").strip().upper()
        selected = {str(v or "").strip() for v in list(pending.get("selected_target_ids", set()) or set()) if str(v or "").strip()}
        text = str(target_unit_id or "").strip()
        if text:
            selected.add(text)
        remaining = int(pending.get("remaining_targets", 0) or 0) - 1
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if self._calm_under_fire_once_per_turn(officer_unit):
            sr["enhancement_calm_under_fire_used_round"] = int(battle_round)
        if remaining <= 0:
            for key in (
                "enhancement_calm_under_fire_pending_round",
                "enhancement_calm_under_fire_pending_order_key",
                "enhancement_calm_under_fire_pending_remaining_targets",
                "enhancement_calm_under_fire_pending_target_ids",
            ):
                sr.pop(key, None)
            officer_unit.special_rules = sr
            return
        sr["enhancement_calm_under_fire_pending_round"] = int(battle_round)
        sr["enhancement_calm_under_fire_pending_order_key"] = order_key
        sr["enhancement_calm_under_fire_pending_remaining_targets"] = int(remaining)
        sr["enhancement_calm_under_fire_pending_target_ids"] = sorted(selected)
        officer_unit.special_rules = sr

    def _officer_has_calm_under_fire_pending_targets(self, officer_unit, battle_round: int) -> bool:
        return bool(self._calm_under_fire_pending_state(officer_unit, battle_round))

    def _clear_siege_over_the_top_pending(self, officer_unit) -> None:
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "siege_regiment_over_the_top_pending_round",
            "siege_regiment_over_the_top_pending_order_key",
            "siege_regiment_over_the_top_pending_target_ids",
        ):
            sr.pop(key, None)
        officer_unit.special_rules = sr

    def _siege_over_the_top_pending_state(self, officer_unit, battle_round: int) -> dict:
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return {}
        try:
            pending_round = int(sr.get("siege_regiment_over_the_top_pending_round", -1) or -1)
        except Exception:
            pending_round = -1
        if pending_round != int(battle_round):
            self._clear_siege_over_the_top_pending(officer_unit)
            return {}
        order_key = str(sr.get("siege_regiment_over_the_top_pending_order_key", "") or "").strip().upper()
        if order_key != ORDER_MOVE.key:
            self._clear_siege_over_the_top_pending(officer_unit)
            return {}
        selected_ids: set[str] = set()
        for raw in list(sr.get("siege_regiment_over_the_top_pending_target_ids", []) or []):
            text = str(raw or "").strip()
            if text:
                selected_ids.add(text)
        if not selected_ids:
            self._clear_siege_over_the_top_pending(officer_unit)
            return {}
        return {"order_key": ORDER_MOVE.key, "selected_target_ids": selected_ids}

    def _start_siege_over_the_top_pending(self, officer_unit, battle_round: int, target_unit_id: str) -> None:
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["siege_regiment_over_the_top_pending_round"] = int(battle_round)
        sr["siege_regiment_over_the_top_pending_order_key"] = ORDER_MOVE.key
        target_ids = []
        text = str(target_unit_id or "").strip()
        if text:
            target_ids.append(text)
        sr["siege_regiment_over_the_top_pending_target_ids"] = target_ids
        officer_unit.special_rules = sr

    def _consume_siege_over_the_top_pending_target(self, officer_unit, battle_round: int, target_unit_id: str) -> None:
        pending = self._siege_over_the_top_pending_state(officer_unit, battle_round)
        if not pending:
            return
        selected = {str(v or "").strip() for v in list(pending.get("selected_target_ids", set()) or set()) if str(v or "").strip()}
        text = str(target_unit_id or "").strip()
        if text:
            selected.add(text)
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["siege_regiment_over_the_top_pending_round"] = int(battle_round)
        sr["siege_regiment_over_the_top_pending_order_key"] = ORDER_MOVE.key
        sr["siege_regiment_over_the_top_pending_target_ids"] = sorted(selected)
        officer_unit.special_rules = sr

    def _officer_has_siege_over_the_top_pending_targets(self, officer_unit, battle_round: int) -> bool:
        return bool(self._siege_over_the_top_pending_state(officer_unit, battle_round))

    def _officer_reactive_command_spec(self, officer_unit) -> dict:
        if officer_unit is None:
            return {}
        army = self.army
        if army is None:
            get_parent_army = getattr(officer_unit, "get_parent_army", None)
            if callable(get_parent_army):
                army = get_parent_army()
        mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        spec_fn = getattr(mgr, "combined_arms_reactive_command_trigger_spec", None) if mgr is not None else None
        if callable(spec_fn):
            spec = spec_fn(officer_unit)
            if isinstance(spec, dict):
                return spec
        return {}

    def _reactive_command_pending_state(self, officer_unit, battle_round: int) -> int:
        if officer_unit is None:
            return 0
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return 0
        try:
            pending_round = int(sr.get("enhancement_reactive_command_pending_round", -1) or -1)
        except Exception:
            pending_round = -1
        if pending_round != int(battle_round):
            sr.pop("enhancement_reactive_command_pending_round", None)
            sr.pop("enhancement_reactive_command_pending_orders", None)
            officer_unit.special_rules = sr
            return 0
        try:
            pending = int(sr.get("enhancement_reactive_command_pending_orders", 0) or 0)
        except Exception:
            pending = 0
        return max(0, int(pending))

    def _set_reactive_command_pending_state(self, officer_unit, battle_round: int, pending_orders: int) -> None:
        if officer_unit is None:
            return
        sr = getattr(officer_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        count = max(0, int(pending_orders or 0))
        if count <= 0:
            sr.pop("enhancement_reactive_command_pending_round", None)
            sr.pop("enhancement_reactive_command_pending_orders", None)
        else:
            sr["enhancement_reactive_command_pending_round"] = int(battle_round)
            sr["enhancement_reactive_command_pending_orders"] = int(count)
        officer_unit.special_rules = sr

    def _consume_reactive_command_pending_order(self, officer_unit, battle_round: int) -> bool:
        current = self._reactive_command_pending_state(officer_unit, battle_round)
        if current <= 0:
            return False
        self._set_reactive_command_pending_state(officer_unit, battle_round, current - 1)
        return True

    def register_reactive_command_enemy_set_up(self, enemy_unit, *, game=None) -> list:
        if enemy_unit is None:
            return []
        if not self._army_has_voice():
            return []
        if self.army is None:
            return []
        try:
            enemy_army = enemy_unit.get_parent_army()
        except Exception:
            enemy_army = None
        if enemy_army is self.army:
            return []
        player = getattr(self.army, "player", None)
        if player is None:
            return []
        game_obj = game if game is not None else getattr(player, "game", None)
        if game_obj is None:
            return []
        game_map = getattr(game_obj, "map", None)
        if game_map is None:
            return []
        try:
            battle_round = int(getattr(game_obj, "turn", 0) or 0)
        except Exception:
            battle_round = 0
        if battle_round <= 0:
            battle_round = 1

        try:
            enemy_root = enemy_unit.get_attached_unit_root()
        except Exception:
            enemy_root = enemy_unit
        if enemy_root is None:
            return []
        try:
            if not self._unit_is_available(enemy_root):
                return []
        except Exception:
            return []

        candidates = []
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            if not self._unit_has_voice(unit):
                continue
            if not self._unit_is_officer(unit):
                continue
            if not self._unit_is_available(unit):
                continue
            if self._unit_is_battleshocked(unit):
                continue
            spec = self._officer_reactive_command_spec(unit)
            if not spec:
                continue
            try:
                trigger_range = float(spec.get("range", 9.0) or 9.0)
            except Exception:
                trigger_range = 9.0
            if trigger_range <= 0:
                continue
            try:
                additional_orders = int(spec.get("orders", 1) or 1)
            except Exception:
                additional_orders = 1
            additional_orders = max(1, int(additional_orders))
            try:
                officer_root = unit.get_attached_unit_root()
            except Exception:
                officer_root = unit
            if officer_root is None:
                continue
            try:
                dist = float(game_map.get_distance_between_units(officer_root, enemy_root))
            except Exception:
                continue
            if dist > trigger_range:
                continue
            pending = self._reactive_command_pending_state(unit, battle_round)
            self._set_reactive_command_pending_state(unit, battle_round, pending + additional_orders)
            unit_id = str(get_entity_id(unit) or "").strip()
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            candidates.append(unit)
        candidates.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return candidates

    def consume_reactive_command_skip(self, officer_unit, *, game=None, battle_round: int | None = None) -> bool:
        if officer_unit is None:
            return False
        round_now = 0
        if battle_round is not None:
            try:
                round_now = int(battle_round or 0)
            except Exception:
                round_now = 0
        if round_now <= 0:
            game_obj = game
            if game_obj is None:
                try:
                    army = officer_unit.get_parent_army()
                    game_obj = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                except Exception:
                    game_obj = None
            try:
                round_now = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
            except Exception:
                round_now = 0
        if round_now <= 0:
            round_now = 1
        return self._consume_reactive_command_pending_order(officer_unit, round_now)

    def _get_officer_enhancement_orders(self, officer_unit) -> list[Order]:
        extra: list[Order] = []
        if self._officer_has_aquilan_eye(officer_unit):
            sr = getattr(officer_unit, "special_rules", None)
            order_key = str(sr.get("enhancement_aquilan_eye_order_key", ORDER_TARGET_WEAK_SPOT.key) or "").strip().upper() if isinstance(sr, dict) else ORDER_TARGET_WEAK_SPOT.key
            if order_key == ORDER_TARGET_WEAK_SPOT.key:
                extra.append(ORDER_TARGET_WEAK_SPOT)
        if self._officer_has_spec_ops_veteran(officer_unit):
            sr = getattr(officer_unit, "special_rules", None)
            order_key = str(sr.get("enhancement_spec_ops_veteran_order_key", ORDER_MOVE_TO_SHADOWS.key) or "").strip().upper() if isinstance(sr, dict) else ORDER_MOVE_TO_SHADOWS.key
            if order_key == ORDER_MOVE_TO_SHADOWS.key:
                extra.append(ORDER_MOVE_TO_SHADOWS)
        return extra

    def _officer_order_range(self, officer_unit, *, order_key: str = "") -> float:
        max_range = 6.0
        ability_range = self._officer_order_range_from_abilities(officer_unit)
        if ability_range > max_range:
            max_range = ability_range
        if self._officer_has_laud_hailer(officer_unit):
            sr = getattr(officer_unit, "special_rules", None)
            if isinstance(sr, dict):
                try:
                    val = float(sr.get("enhancement_laud_hailer_order_range", 12.0) or 12.0)
                except Exception:
                    val = 12.0
                if val > 0:
                    if val > max_range:
                        max_range = val
            elif 12.0 > max_range:
                max_range = 12.0
        return float(max_range)

    def get_order_range(self, officer_unit, *, order_key: str = "") -> float:
        return float(self._officer_order_range(officer_unit, order_key=order_key))

    def _orders_recurring_capacity(self, unit) -> int:
        count, _, _ = self._parse_orders_profile(unit)
        bonus = 0
        army = self.army
        if army is None and unit is not None:
            get_parent_army = getattr(unit, "get_parent_army", None)
            if callable(get_parent_army):
                army = get_parent_army()
        mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        bonus_fn = getattr(mgr, "ruthless_discipline_orders_bonus", None) if mgr is not None else None
        if callable(bonus_fn):
            bonus = int(bonus_fn(unit) or 0)
        grand_bonus_fn = getattr(mgr, "combined_arms_grand_strategist_orders_bonus", None) if mgr is not None else None
        if callable(grand_bonus_fn):
            bonus += int(grand_bonus_fn(unit) or 0)
        return max(0, int(count) + int(bonus))

    def _officer_once_per_battle_additional_orders_available(self, unit) -> int:
        if unit is None:
            return 0
        fn = getattr(unit, "servo_scribes_additional_orders_available", None)
        if callable(fn):
            try:
                return max(0, int(fn() or 0))
            except Exception:
                return 0
        return 0

    def orders_remaining(self, unit, battle_round: int) -> int:
        capacity = self._orders_recurring_capacity(unit)
        capacity += self._officer_once_per_battle_additional_orders_available(unit)
        issued = self._order_issued_state(unit, battle_round)
        return max(0, int(capacity) - int(issued))

    def orders_remaining_for_trigger(self, unit, battle_round: int, *, trigger: str = "") -> int:
        trigger_key = str(trigger or "").strip().lower()
        if trigger_key == "reactive_command_setup":
            return self._reactive_command_pending_state(unit, battle_round)
        if trigger_key == "inspired_command":
            return self._inspired_command_pending_state(unit, battle_round)
        return self.orders_remaining(unit, battle_round)

    def officer_has_order_capacity(self, unit, battle_round: int, *, trigger: str = "") -> bool:
        if unit is None:
            return False
        remaining = self.orders_remaining_for_trigger(unit, battle_round, trigger=trigger)
        if remaining > 0:
            return True
        if self._officer_has_bombast_pending_targets(unit, battle_round):
            return True
        if self._officer_has_siege_over_the_top_pending_targets(unit, battle_round):
            return True
        return self._officer_has_calm_under_fire_pending_targets(unit, battle_round)

    def _unit_ready_for_end_phase(self, unit, phase_name: str, battle_round: Optional[int] = None) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        pname = str(phase_name or "").strip().upper()
        if not pname:
            return False
        if str(sr.get("voice_of_command_disembark_phase", "") or "").strip().upper() == pname:
            if battle_round is None:
                return True
            try:
                return int(sr.get("voice_of_command_disembark_round", -1)) == int(battle_round)
            except Exception:
                return True
        if str(sr.get("voice_of_command_set_up_phase", "") or "").strip().upper() == pname:
            if battle_round is None:
                return True
            try:
                return int(sr.get("voice_of_command_set_up_round", -1)) == int(battle_round)
            except Exception:
                return True
        return False

    def get_eligible_officers(self, *, game=None, player=None, phase_name: str = "", trigger: str = "") -> list:
        if not self._army_has_voice():
            return []
        if player is None:
            player = getattr(self.army, "player", None)
        if game is None and player is not None:
            try:
                game = player.game
            except Exception:
                game = None
        if player is None:
            return []
        battle_round = int(getattr(game, "turn", 0) or 0) if game is not None else 0

        out = []
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            if not self._unit_has_voice(unit):
                continue
            if not self._unit_is_officer(unit):
                continue
            mobile_command_transport = self._mobile_command_vehicle_transport(
                unit,
                phase_name=phase_name,
                battle_round=battle_round,
                game=game,
            )
            vox_relay_transport = self._mechanised_vox_relay_transport(
                unit,
                phase_name=phase_name,
                battle_round=battle_round,
                game=game,
            )
            if not self._unit_is_available(unit) and mobile_command_transport is None and vox_relay_transport is None:
                continue
            if self._unit_is_battleshocked(unit):
                continue
            if not self.officer_has_order_capacity(unit, battle_round, trigger=trigger):
                continue
            if trigger == "phase_end" and not self._unit_ready_for_end_phase(unit, phase_name, battle_round):
                continue
            out.append(unit)
        return out

    def get_eligible_targets(self, officer_unit, *, game=None, order_key: str = "") -> list:
        if officer_unit is None:
            return []
        if game is None:
            try:
                game = officer_unit.get_parent_army().player.game
            except Exception:
                game = None
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        try:
            battle_round = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        except Exception:
            battle_round = 0
        mobile_command_transport = self._mobile_command_vehicle_transport(
            officer_unit,
            battle_round=battle_round,
            game=game,
        )
        vox_relay_transport = self._mechanised_vox_relay_transport(
            officer_unit,
            battle_round=battle_round,
            game=game,
        )
        order_anchor = mobile_command_transport or vox_relay_transport
        if order_anchor is None and not self._unit_is_available(officer_unit):
            return []

        _, keywords, _ = self._parse_orders_profile(officer_unit)
        keywords = [k for k in (keywords or []) if k]
        if self._officer_has_abhuman_detail(officer_unit):
            sr = getattr(officer_unit, "special_rules", None)
            extra_keywords = []
            if isinstance(sr, dict):
                for kw in list(sr.get("enhancement_abhuman_detail_order_target_keywords", ()) or ()):
                    text = str(kw or "").strip().upper()
                    if text:
                        extra_keywords.append(text)
            if not extra_keywords:
                extra_keywords = ["OGRYN"]
            keywords.extend(extra_keywords)
        army = self.army
        if army is None:
            try:
                army = officer_unit.get_parent_army()
            except Exception:
                army = None
        mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        extra_target_keywords_fn = getattr(mgr, "combined_arms_flexible_command_target_keywords", None) if mgr is not None else None
        if callable(extra_target_keywords_fn):
            keywords.extend(list(extra_target_keywords_fn(officer_unit, game=game) or ()))
        seen_keywords = set()
        deduped_keywords: list[str] = []
        for kw in keywords:
            k = str(kw or "").strip().upper()
            if not k or k in seen_keywords:
                continue
            seen_keywords.add(k)
            deduped_keywords.append(k)
        keywords = deduped_keywords
        max_range = self.get_order_range(officer_unit, order_key=order_key)
        pending_siege = self._siege_over_the_top_pending_state(officer_unit, battle_round) if battle_round > 0 else {}
        if pending_siege:
            pending_order = str(pending_siege.get("order_key", "") or "").strip().upper()
            if order_key and pending_order and order_key != pending_order:
                return []
        siege_over_the_top_active = bool(
            order_key == ORDER_MOVE.key
            and self._officer_has_siege_over_the_top_active(officer_unit, battle_round, game=game)
        )

        out = []
        try:
            friendlies = list(game_map.get_friendly_units(order_anchor or officer_unit))
        except Exception:
            friendlies = []
        seen = set()
        for unit in friendlies:
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            try:
                uid = get_entity_id(root)
            except Exception:
                uid = ""
            if uid in seen:
                continue
            seen.add(uid)
            if not self._unit_is_available(root):
                continue
            if self._unit_is_battleshocked(root):
                continue
            vox_relay_transport_target = bool(
                vox_relay_transport is not None
                and self._unit_is_astra_militarum(root)
                and self._target_has_keyword(root, "TRANSPORT")
                and not self._target_has_keyword(root, "TITANIC")
            )
            if siege_over_the_top_active or pending_siege:
                if not self._target_matches_siege_over_the_top_keyword(root):
                    continue
            elif keywords:
                try:
                    if not any(root.has_any_keyword(k) for k in keywords) and not vox_relay_transport_target:
                        continue
                except Exception:
                    continue
            ignore_range = bool(vox_relay_transport_target or siege_over_the_top_active or pending_siege)
            if not ignore_range:
                try:
                    dist = float(game_map.get_distance_between_units(order_anchor or officer_unit, root))
                except Exception:
                    dist = 999.0
                if dist > float(max_range):
                    continue
            out.append(root)
        pending_bombast = self._bombast_pending_state(officer_unit, battle_round) if battle_round > 0 else {}
        if pending_bombast:
            pending_order = str(pending_bombast.get("order_key", "") or "").strip().upper()
            if order_key and pending_order and order_key != pending_order:
                return []
            selected_target_ids = {
                str(v or "").strip()
                for v in list(pending_bombast.get("selected_target_ids", set()) or set())
                if str(v or "").strip()
            }
            filtered = []
            for target in out:
                if not self._target_matches_bombast_keyword(officer_unit, target):
                    continue
                target_id = str(get_entity_id(target) or "").strip()
                if target_id and target_id in selected_target_ids:
                    continue
                filtered.append(target)
            out = filtered

        pending_calm = self._calm_under_fire_pending_state(officer_unit, battle_round) if battle_round > 0 else {}
        if pending_calm:
            pending_order = str(pending_calm.get("order_key", "") or "").strip().upper()
            if order_key and pending_order and order_key != pending_order:
                return []
            selected_target_ids = {
                str(v or "").strip()
                for v in list(pending_calm.get("selected_target_ids", set()) or set())
                if str(v or "").strip()
            }
            filtered = []
            for target in out:
                if not self._target_matches_calm_under_fire_keyword(officer_unit, target):
                    continue
                target_id = str(get_entity_id(target) or "").strip()
                if target_id and target_id in selected_target_ids:
                    continue
                filtered.append(target)
            out = filtered
        if pending_siege:
            selected_target_ids = {
                str(v or "").strip()
                for v in list(pending_siege.get("selected_target_ids", set()) or set())
                if str(v or "").strip()
            }
            filtered = []
            for target in out:
                if not self._target_matches_siege_over_the_top_keyword(target):
                    continue
                target_id = str(get_entity_id(target) or "").strip()
                if target_id and target_id in selected_target_ids:
                    continue
                filtered.append(target)
            out = filtered
        return out

    def clear_order(self, unit) -> None:
        if unit is None:
            return
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict):
            for k in (
                "voice_of_command_order_key",
                "voice_of_command_order_owner",
                "voice_of_command_order_source",
                "voice_of_command_additional_order_keys",
                "voice_of_command_temp_order_keys",
                "voice_of_command_take_cover_cap",
            ):
                sr.pop(k, None)
        try:
            unit.remove_characteristic_modifiers_by_source("voice_of_command:")
        except Exception:
            pass
        try:
            unit.remove_characteristic_modifiers_by_source("voice_of_command_temp:")
        except Exception:
            pass

    def get_available_orders(self, officer_unit) -> list[Order]:
        if officer_unit is None:
            return list(ORDER_LIST)
        battle_round = 0
        try:
            army = self.army if self.army is not None else officer_unit.get_parent_army()
        except Exception:
            army = None
        try:
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        except Exception:
            game = None
        if game is not None:
            try:
                battle_round = int(getattr(game, "turn", 0) or 0)
            except Exception:
                battle_round = 0
        _, _, allowed = self._parse_orders_profile(officer_unit)
        enhancement_orders = self._get_officer_enhancement_orders(officer_unit)
        if not allowed:
            base = list(ORDER_LIST)
        else:
            base = [order for order in ORDER_LIST if order.key in allowed]
        seen = {order.key for order in base}
        out: list[Order] = []
        out.extend(base)
        for order in enhancement_orders:
            if order.key in seen:
                continue
            seen.add(order.key)
            out.append(order)
        if battle_round > 0:
            if self.orders_remaining(officer_unit, battle_round) <= 0:
                pending = self._bombast_pending_state(officer_unit, battle_round)
                if pending:
                    pending_order = ORDER_BY_KEY.get(str(pending.get("order_key", "") or "").strip().upper())
                    if pending_order is not None:
                        return [pending_order]
                pending = self._siege_over_the_top_pending_state(officer_unit, battle_round)
                if pending:
                    pending_order = ORDER_BY_KEY.get(str(pending.get("order_key", "") or "").strip().upper())
                    if pending_order is not None:
                        return [pending_order]
                pending = self._calm_under_fire_pending_state(officer_unit, battle_round)
                if pending:
                    pending_order = ORDER_BY_KEY.get(str(pending.get("order_key", "") or "").strip().upper())
                    if pending_order is not None:
                        return [pending_order]
        return out

    def clear_orders_for_player(self, player) -> None:
        if player is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        for unit in list(getattr(army, "units", []) or []):
            self.clear_order(unit)

    def _apply_order_modifiers(self, unit, order_key: str, *, source_prefix: str = "voice_of_command:") -> None:
        if unit is None:
            return
        if not self._unit_is_astra_militarum(unit):
            return
        if order_key == ORDER_MOVE.key:
            unit.add_characteristic_modifier(
                "movement", Modifier(ModifierOp.ADD, 3, source=f"{source_prefix}{order_key}")
            )
        elif order_key == ORDER_TAKE_COVER.key:
            unit.add_characteristic_modifier(
                "save", Modifier(ModifierOp.SUB, 1, source=f"{source_prefix}{order_key}")
            )
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["voice_of_command_take_cover_cap"] = True
            unit.special_rules = sr
        elif order_key == ORDER_DUTY_HONOUR.key:
            unit.add_characteristic_modifier(
                "leadership", Modifier(ModifierOp.SUB, 1, source=f"{source_prefix}{order_key}")
            )
            unit.add_characteristic_modifier(
                "objective_control", Modifier(ModifierOp.ADD, 1, source=f"{source_prefix}{order_key}")
            )

    def _apply_order_to_unit_and_attached(self, unit, order_key: str, owner_id: str, source_id: str) -> None:
        if unit is None:
            return
        units = [unit]
        try:
            units.extend(list(getattr(unit, "attached_leaders", []) or []))
        except Exception:
            pass
        for u in units:
            if u is None:
                continue
            if not self._unit_is_astra_militarum(u):
                continue
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["voice_of_command_order_key"] = order_key
            sr["voice_of_command_order_owner"] = owner_id
            sr["voice_of_command_order_source"] = source_id
            u.special_rules = sr

    def _apply_additional_order_to_unit_and_attached(self, unit, order_key: str) -> None:
        if unit is None:
            return
        key = str(order_key or "").strip().upper()
        if key not in ORDER_BY_KEY:
            return
        units = [unit]
        units.extend(list(getattr(unit, "attached_leaders", []) or []))
        for member in units:
            if member is None:
                continue
            if not self._unit_is_astra_militarum(member):
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            extra_keys = self._normalise_order_key_list(sr.get("voice_of_command_additional_order_keys", []))
            if key in extra_keys:
                sr["voice_of_command_additional_order_keys"] = list(extra_keys)
                member.special_rules = sr
                continue
            extra_keys.append(key)
            sr["voice_of_command_additional_order_keys"] = list(extra_keys)
            member.special_rules = sr
        self._refresh_order_state_for_unit_and_attached(unit)

    def issue_order(self, game, officer_unit, target_unit, order_key: str, *, phase_name: str = "", trigger: str = "") -> bool:
        if officer_unit is None or target_unit is None:
            return False
        if not self._army_has_voice():
            return False
        if not self._unit_has_voice(officer_unit):
            return False
        if not self._unit_is_officer(officer_unit):
            return False
        try:
            battle_round = int(getattr(game, "turn", 0) or 0)
        except Exception:
            battle_round = 0
        mobile_command_transport = self._mobile_command_vehicle_transport(
            officer_unit,
            phase_name=phase_name,
            battle_round=battle_round,
            game=game,
        )
        vox_relay_transport = self._mechanised_vox_relay_transport(
            officer_unit,
            phase_name=phase_name,
            battle_round=battle_round,
            game=game,
        )
        order_anchor = mobile_command_transport or vox_relay_transport
        if not self._unit_is_available(officer_unit) and order_anchor is None:
            return False
        if self._unit_is_battleshocked(officer_unit):
            return False

        order_key = str(order_key or "").strip().upper()
        if order_key not in ORDER_BY_KEY:
            return False
        allowed = self._parse_orders_profile(officer_unit)[2]
        enhancement_order_keys = {order.key for order in self._get_officer_enhancement_orders(officer_unit)}
        if order_key in (ORDER_TARGET_WEAK_SPOT.key, ORDER_MOVE_TO_SHADOWS.key) and order_key not in enhancement_order_keys:
            return False
        if allowed and order_key not in allowed and order_key not in enhancement_order_keys:
            return False
        trigger_key = str(trigger or "").strip().lower()
        reactive_trigger = trigger_key == "reactive_command_setup"
        inspired_trigger = trigger_key == "inspired_command"
        pending_bombast = self._bombast_pending_state(officer_unit, battle_round) if battle_round > 0 else {}
        pending_calm = self._calm_under_fire_pending_state(officer_unit, battle_round) if battle_round > 0 else {}
        pending_siege = self._siege_over_the_top_pending_state(officer_unit, battle_round) if battle_round > 0 else {}
        continuation_kind = ""
        continuation_pending = {}

        if pending_bombast:
            pending_order_key = str(pending_bombast.get("order_key", "") or "").strip().upper()
            if pending_order_key == order_key and int(pending_bombast.get("remaining_targets", 0) or 0) > 0:
                continuation_kind = "bombast"
                continuation_pending = pending_bombast
            else:
                self._clear_bombast_pending(officer_unit)
                pending_bombast = {}

        if pending_calm:
            pending_order_key = str(pending_calm.get("order_key", "") or "").strip().upper()
            if continuation_kind:
                if pending_order_key != order_key:
                    self._clear_calm_under_fire_pending(officer_unit)
                    pending_calm = {}
            elif pending_order_key == order_key and int(pending_calm.get("remaining_targets", 0) or 0) > 0:
                continuation_kind = "calm_under_fire"
                continuation_pending = pending_calm
            else:
                self._clear_calm_under_fire_pending(officer_unit)
                pending_calm = {}
        if pending_siege:
            pending_order_key = str(pending_siege.get("order_key", "") or "").strip().upper()
            if continuation_kind:
                if pending_order_key != order_key:
                    self._clear_siege_over_the_top_pending(officer_unit)
                    pending_siege = {}
            elif pending_order_key == order_key:
                continuation_kind = "siege_over_the_top"
                continuation_pending = pending_siege
            else:
                self._clear_siege_over_the_top_pending(officer_unit)
                pending_siege = {}

        continuation_issue = bool(continuation_kind)
        reactive_pending_available = (
            self._reactive_command_pending_state(officer_unit, battle_round) if reactive_trigger and battle_round > 0 else 0
        )
        inspired_pending_available = (
            self._inspired_command_pending_state(officer_unit, battle_round) if inspired_trigger and battle_round > 0 else 0
        )
        if not continuation_issue and reactive_trigger:
            if reactive_pending_available <= 0:
                return False
        elif not continuation_issue and inspired_trigger:
            if inspired_pending_available <= 0:
                return False
        elif not continuation_issue and self.orders_remaining(officer_unit, battle_round) <= 0:
            return False

        # Validate target eligibility
        if self._unit_is_battleshocked(target_unit):
            return False
        if not self._unit_is_available(target_unit):
            return False
        eligible_targets = self.get_eligible_targets(officer_unit, game=game, order_key=order_key)
        if target_unit not in eligible_targets:
            return False
        target_unit_id = str(get_entity_id(target_unit) or "").strip()
        if continuation_kind == "bombast":
            if not self._target_matches_bombast_keyword(officer_unit, target_unit):
                return False
            selected_target_ids = {
                str(v or "").strip()
                for v in list(continuation_pending.get("selected_target_ids", set()) or set())
                if str(v or "").strip()
            }
            if target_unit_id and target_unit_id in selected_target_ids:
                return False
        elif continuation_kind == "calm_under_fire":
            if not self._target_matches_calm_under_fire_keyword(officer_unit, target_unit):
                return False
            selected_target_ids = {
                str(v or "").strip()
                for v in list(continuation_pending.get("selected_target_ids", set()) or set())
                if str(v or "").strip()
            }
            if target_unit_id and target_unit_id in selected_target_ids:
                return False
        elif continuation_kind == "siege_over_the_top":
            if order_key != ORDER_MOVE.key:
                return False
            if not self._target_matches_siege_over_the_top_keyword(target_unit):
                return False
            selected_target_ids = {
                str(v or "").strip()
                for v in list(continuation_pending.get("selected_target_ids", set()) or set())
                if str(v or "").strip()
            }
            if target_unit_id and target_unit_id in selected_target_ids:
                return False

        try:
            owner_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
        except Exception:
            owner_id = ""
        try:
            source_id = get_entity_id(officer_unit)
        except Exception:
            source_id = ""

        max_orders = max(1, int(self._attached_unit_command_rod_order_capacity(target_unit)))
        current_order_keys = self._attached_unit_permanent_order_keys(target_unit)
        target_order_keys = [order_key]
        if max_orders > 1 and current_order_keys:
            if order_key in current_order_keys:
                target_order_keys = list(current_order_keys)
            elif len(current_order_keys) < max_orders:
                target_order_keys = list(current_order_keys) + [order_key]
            else:
                retained_keys = [key for key in list(current_order_keys) if key != order_key]
                target_order_keys = retained_keys[-(max_orders - 1) :] + [order_key]

        self._set_orders_on_unit_and_attached(target_unit, target_order_keys, owner_id, source_id)
        if mobile_command_transport is not None:
            self._mark_mobile_command_vehicle_selected_officer(mobile_command_transport, battle_round, officer_unit)
        additional_order_key = self._stalwarts_honours_additional_order_key(target_unit)
        if additional_order_key and additional_order_key not in target_order_keys:
            self._apply_additional_order_to_unit_and_attached(target_unit, additional_order_key)
        if not continuation_issue:
            if reactive_trigger and reactive_pending_available > 0:
                self._consume_reactive_command_pending_order(officer_unit, battle_round)
            elif inspired_trigger:
                if not self._consume_inspired_command_pending_order(officer_unit, battle_round):
                    return False
            else:
                issued = self._order_issued_state(officer_unit, battle_round)
                issued_after = int(issued) + 1
                self._set_orders_issued(officer_unit, battle_round, issued_after)
                recurring_capacity = self._orders_recurring_capacity(officer_unit)
                if issued_after > int(recurring_capacity):
                    mark_extra = getattr(officer_unit, "mark_servo_scribes_additional_order_used", None)
                    if callable(mark_extra):
                        mark_extra()
        self._sync_coordinated_action_pair(
            target_unit,
            game=game,
            battle_round=battle_round,
            phase_name=phase_name,
            owner_id=self._active_player_id(game),
        )
        if continuation_kind == "bombast":
            self._consume_bombast_pending_target(officer_unit, battle_round, target_unit_id)
        elif continuation_kind == "calm_under_fire":
            self._consume_calm_under_fire_pending_target(officer_unit, battle_round, target_unit_id)
        elif continuation_kind == "siege_over_the_top":
            self._consume_siege_over_the_top_pending_target(officer_unit, battle_round, target_unit_id)
            if not self.get_eligible_targets(officer_unit, game=game, order_key=order_key):
                self._clear_siege_over_the_top_pending(officer_unit)
        else:
            if self._officer_bombast_multi_target_available(officer_unit) and self._target_matches_bombast_keyword(
                officer_unit, target_unit
            ):
                self._start_bombast_pending(officer_unit, battle_round, order_key, target_unit_id)
            else:
                self._clear_bombast_pending(officer_unit)
            if self._officer_calm_under_fire_multi_target_available(
                officer_unit,
                battle_round,
            ) and self._target_matches_calm_under_fire_keyword(officer_unit, target_unit):
                self._start_calm_under_fire_pending(officer_unit, battle_round, order_key, target_unit_id)
            else:
                self._clear_calm_under_fire_pending(officer_unit)
            if (
                order_key == ORDER_MOVE.key
                and self._officer_has_siege_over_the_top_active(officer_unit, battle_round, game=game)
                and self._target_matches_siege_over_the_top_keyword(target_unit)
            ):
                remaining_siege_targets = [
                    candidate
                    for candidate in list(eligible_targets or [])
                    if str(get_entity_id(candidate) or "").strip() != target_unit_id
                    and self._target_matches_siege_over_the_top_keyword(candidate)
                ]
                if remaining_siege_targets:
                    self._start_siege_over_the_top_pending(officer_unit, battle_round, target_unit_id)
                else:
                    self._clear_siege_over_the_top_pending(officer_unit)
            else:
                self._clear_siege_over_the_top_pending(officer_unit)
        return True

    def _attached_unit_has_order_key(self, unit, order_key: str) -> bool:
        if unit is None:
            return False
        order_key = str(order_key or "").strip().upper()
        if not order_key:
            return False
        root = unit
        try:
            get_root = getattr(unit, "get_attached_unit_root", None)
            if callable(get_root):
                root = get_root()
        except Exception:
            root = unit
        members = []
        try:
            get_members = getattr(root, "get_attached_unit_members", None)
            if callable(get_members):
                members = list(get_members() or [])
        except Exception:
            members = []
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            active_key = str(sr.get("voice_of_command_order_key", "") or "").strip().upper()
            if active_key == order_key:
                return True
            additional_keys = self._normalise_order_key_list(sr.get("voice_of_command_additional_order_keys", []))
            if order_key in additional_keys:
                return True
            temp_keys = self._normalise_order_key_list(sr.get("voice_of_command_temp_order_keys", []))
            if order_key in temp_keys:
                return True
        return False

    def target_weak_spot_ap_bonus(self, attacker_unit, target_unit, *, game_map=None) -> int:
        if attacker_unit is None or target_unit is None:
            return 0
        if not self._attached_unit_has_order_key(attacker_unit, ORDER_TARGET_WEAK_SPOT.key):
            return 0
        if game_map is None:
            try:
                army = attacker_unit.get_parent_army()
                player = getattr(army, "player", None) if army is not None else None
                game = getattr(player, "game", None) if player is not None else None
                game_map = getattr(game, "map", None) if game is not None else None
            except Exception:
                game_map = None
        if game_map is None:
            return 0
        attacker_root = attacker_unit
        target_root = target_unit
        try:
            if hasattr(attacker_unit, "get_attached_unit_root"):
                attacker_root = attacker_unit.get_attached_unit_root()
        except Exception:
            attacker_root = attacker_unit
        try:
            if hasattr(target_unit, "get_attached_unit_root"):
                target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        try:
            dist = float(game_map.get_distance_between_units(attacker_root, target_root))
        except Exception:
            dist = 999.0
        if dist <= 12.0:
            return 1
        return 0

    def move_to_shadows_hit_penalty(self, target_unit, *, attack_type: str = "") -> int:
        atype = str(attack_type or "").strip().lower()
        if atype != "ranged":
            return 0
        if self._attached_unit_has_order_key(target_unit, ORDER_MOVE_TO_SHADOWS.key):
            return 1
        return 0

    def _pending_order_sequence_request(
        self,
        game,
        decision_type: str,
        *,
        player_id: str = "",
        context: dict | None = None,
    ):
        queue = getattr(game, "decision_queue", None) if game is not None else None
        list_fn = getattr(queue, "list", None) if queue is not None else None
        if not callable(list_fn):
            return None
        expected_context = dict(context or {})
        for request in list(list_fn() or []):
            if str(getattr(request, "decision_type", "") or "") != str(decision_type or ""):
                continue
            if player_id and str(getattr(request, "player_id", "") or "") != str(player_id):
                continue
            request_context = dict(getattr(request, "context", {}) or {})
            matches = True
            for key, value in expected_context.items():
                if request_context.get(key) != value:
                    matches = False
                    break
            if matches:
                return request
        return None

    def _available_orders_with_targets(self, officer_unit, *, game) -> list[Order]:
        orders = list(self.get_available_orders(officer_unit) or [])
        available: list[Order] = []
        for order in list(orders or []):
            order_key = str(getattr(order, "key", "") or "").strip().upper()
            if not order_key:
                continue
            targets = list(self.get_eligible_targets(officer_unit, game=game, order_key=order_key) or [])
            if targets:
                available.append(order)
        return available

    def queue_order_sequence_start(self, game, player, *, phase_name: str = "", trigger: str = ""):
        request_fn = getattr(game, "request_decision", None) if game is not None else None
        if player is None or not callable(request_fn):
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        battle_round = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        officers = list(self.get_eligible_officers(game=game, player=player, phase_name=phase_name, trigger=trigger) or [])
        filtered_officers = [
            officer for officer in list(officers or [])
            if officer is not None and self._available_orders_with_targets(officer, game=game)
        ]
        if not filtered_officers:
            return None

        context = {
            "ability": "voice_of_command_officer",
            "phase_name": str(phase_name or ""),
            "trigger": str(trigger or ""),
            "army_id": str(get_entity_id(self.army) or "") if self.army is not None else "",
        }
        existing = self._pending_order_sequence_request(
            game,
            DECISION_CHOOSE_QUARRY,
            player_id=str(getattr(player, "id", "") or ""),
            context=context,
        )
        if existing is not None:
            return existing

        filtered_officers.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        used_labels: set[str] = set()
        options = [DecisionOption.create("Skip orders", payload={"action": "skip"})]
        for officer in filtered_officers:
            remaining = int(self.orders_remaining_for_trigger(officer, battle_round, trigger=trigger or "") or 0)
            label = f"{getattr(officer, 'name', 'Officer')} ({remaining} order{'s' if remaining != 1 else ''} remaining)"
            base = label
            suffix = 2
            while label in used_labels:
                label = f"{base} [{suffix}]"
                suffix += 1
            used_labels.add(label)
            options.append(
                DecisionOption.create(
                    label,
                    payload={
                        "target_unit_id": str(get_entity_id(officer) or ""),
                        "army_id": context["army_id"],
                        "phase_name": str(phase_name or ""),
                        "trigger": str(trigger or ""),
                    },
                )
            )

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select an officer to issue orders.",
            player_id=getattr(player, "id", None),
            options=options,
            context=context,
        )
        request_fn(request)
        return request

    def queue_order_sequence_order_request(
        self,
        game,
        player,
        officer_unit,
        *,
        phase_name: str = "",
        trigger: str = "",
    ):
        request_fn = getattr(game, "request_decision", None) if game is not None else None
        if player is None or officer_unit is None or not callable(request_fn):
            return None

        from ..engine.decision_kinds import DECISION_ISSUE_ORDER
        from ..engine.decisions import DecisionOption, DecisionRequest

        officer_id = str(get_entity_id(officer_unit) or "")
        if not officer_id:
            return None
        orders = self._available_orders_with_targets(officer_unit, game=game)
        if not orders:
            return None

        context = {
            "ability": "voice_of_command_order",
            "officer_unit_id": officer_id,
            "phase_name": str(phase_name or ""),
            "trigger": str(trigger or ""),
            "army_id": str(get_entity_id(self.army) or "") if self.army is not None else "",
        }
        existing = self._pending_order_sequence_request(
            game,
            DECISION_ISSUE_ORDER,
            player_id=str(getattr(player, "id", "") or ""),
            context=context,
        )
        if existing is not None:
            return existing

        options = [
            DecisionOption.create(
                "Skip orders",
                payload={"action": "skip", "officer_unit_id": officer_id, "army_id": context["army_id"]},
            )
        ]
        for order in list(orders or []):
            options.append(
                DecisionOption.create(
                    getattr(order, "name", "Order"),
                    payload={
                        "officer_unit_id": officer_id,
                        "order_key": getattr(order, "key", ""),
                        "summary": getattr(order, "summary", ""),
                        "army_id": context["army_id"],
                        "phase_name": str(phase_name or ""),
                        "trigger": str(trigger or ""),
                    },
                )
            )

        request = DecisionRequest.create(
            DECISION_ISSUE_ORDER,
            f"Select order for {getattr(officer_unit, 'name', 'Officer')}",
            player_id=getattr(player, "id", None),
            options=options,
            context=context,
        )
        request_fn(request)
        return request

    def queue_order_sequence_target_request(
        self,
        game,
        player,
        officer_unit,
        order_key: str,
        *,
        phase_name: str = "",
        trigger: str = "",
    ):
        request_fn = getattr(game, "request_decision", None) if game is not None else None
        if player is None or officer_unit is None or not callable(request_fn):
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        officer_id = str(get_entity_id(officer_unit) or "")
        normalized_key = str(order_key or "").strip().upper()
        if not officer_id or not normalized_key:
            return None
        targets = list(self.get_eligible_targets(officer_unit, game=game, order_key=normalized_key) or [])
        if not targets:
            return None

        context = {
            "ability": "voice_of_command_target",
            "officer_unit_id": officer_id,
            "order_key": normalized_key,
            "phase_name": str(phase_name or ""),
            "trigger": str(trigger or ""),
            "army_id": str(get_entity_id(self.army) or "") if self.army is not None else "",
        }
        existing = self._pending_order_sequence_request(
            game,
            DECISION_CHOOSE_QUARRY,
            player_id=str(getattr(player, "id", "") or ""),
            context=context,
        )
        if existing is not None:
            return existing

        targets.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        options = [DecisionOption.create("Cancel", payload={"action": "skip"})]
        for target_unit in list(targets or []):
            options.append(
                DecisionOption.create(
                    getattr(target_unit, "name", "Unit"),
                    payload={
                        "target_unit_id": str(get_entity_id(target_unit) or ""),
                        "officer_unit_id": officer_id,
                        "order_key": normalized_key,
                        "army_id": context["army_id"],
                    },
                )
            )

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select Voice of Command target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=context,
        )
        request_fn(request)
        return request

    def auto_issue_orders(self, game, player, *, phase_name: str = "", trigger: str = "") -> None:
        """No-op: orders require explicit player selection."""
        return
