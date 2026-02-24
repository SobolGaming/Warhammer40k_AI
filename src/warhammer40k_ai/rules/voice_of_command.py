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

    def orders_remaining(self, unit, battle_round: int) -> int:
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
        issued = self._order_issued_state(unit, battle_round)
        return max(0, int(count) + int(bonus) - int(issued))

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
            if not self._unit_is_available(unit):
                continue
            if self._unit_is_battleshocked(unit):
                continue
            if self.orders_remaining(unit, battle_round) <= 0:
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

        out = []
        try:
            friendlies = list(game_map.get_friendly_units(officer_unit))
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
            if keywords:
                try:
                    if not any(root.has_any_keyword(k) for k in keywords):
                        continue
                except Exception:
                    continue
            try:
                dist = float(game_map.get_distance_between_units(officer_unit, root))
            except Exception:
                dist = 999.0
            if dist > float(max_range):
                continue
            out.append(root)
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
                "voice_of_command_take_cover_cap",
            ):
                sr.pop(k, None)
        try:
            unit.remove_characteristic_modifiers_by_source("voice_of_command:")
        except Exception:
            pass

    def get_available_orders(self, officer_unit) -> list[Order]:
        if officer_unit is None:
            return list(ORDER_LIST)
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

    def _apply_order_modifiers(self, unit, order_key: str) -> None:
        if unit is None:
            return
        if not self._unit_is_astra_militarum(unit):
            return
        if order_key == ORDER_MOVE.key:
            unit.add_characteristic_modifier(
                "movement", Modifier(ModifierOp.ADD, 3, source=f"voice_of_command:{order_key}")
            )
        elif order_key == ORDER_TAKE_COVER.key:
            unit.add_characteristic_modifier(
                "save", Modifier(ModifierOp.SUB, 1, source=f"voice_of_command:{order_key}")
            )
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["voice_of_command_take_cover_cap"] = True
            unit.special_rules = sr
        elif order_key == ORDER_DUTY_HONOUR.key:
            unit.add_characteristic_modifier(
                "leadership", Modifier(ModifierOp.SUB, 1, source=f"voice_of_command:{order_key}")
            )
            unit.add_characteristic_modifier(
                "objective_control", Modifier(ModifierOp.ADD, 1, source=f"voice_of_command:{order_key}")
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
            self._apply_order_modifiers(u, order_key)

    def issue_order(self, game, officer_unit, target_unit, order_key: str, *, phase_name: str = "") -> bool:
        if officer_unit is None or target_unit is None:
            return False
        if not self._army_has_voice():
            return False
        if not self._unit_has_voice(officer_unit):
            return False
        if not self._unit_is_officer(officer_unit):
            return False
        if not self._unit_is_available(officer_unit):
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
        try:
            battle_round = int(getattr(game, "turn", 0) or 0)
        except Exception:
            battle_round = 0
        if self.orders_remaining(officer_unit, battle_round) <= 0:
            return False

        # Validate target eligibility
        if self._unit_is_battleshocked(target_unit):
            return False
        if not self._unit_is_available(target_unit):
            return False
        eligible_targets = self.get_eligible_targets(officer_unit, game=game, order_key=order_key)
        if target_unit not in eligible_targets:
            return False

        # Consume an order
        issued = self._order_issued_state(officer_unit, battle_round)
        self._set_orders_issued(officer_unit, battle_round, issued + 1)

        # Replace any existing orders
        self.clear_order(target_unit)
        try:
            for l in list(getattr(target_unit, "attached_leaders", []) or []):
                self.clear_order(l)
        except Exception:
            pass

        try:
            owner_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
        except Exception:
            owner_id = ""
        try:
            source_id = get_entity_id(officer_unit)
        except Exception:
            source_id = ""

        self._apply_order_to_unit_and_attached(target_unit, order_key, owner_id, source_id)
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

    def auto_issue_orders(self, game, player, *, phase_name: str = "", trigger: str = "") -> None:
        """No-op: orders require explicit player selection."""
        return
