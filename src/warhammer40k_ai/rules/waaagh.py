from __future__ import annotations

import re

from ..utility.ability_support import ABILITY_WAAAGH, army_has_ability_id


class WaaaghManager:
    """
    Orks army rule: Waaagh!

    Once per battle, at the start of your Command phase, you can call a Waaagh!
    Until the start of your next Command phase, units with this ability:
      - can charge after advancing,
      - get +1 Strength and +1 Attacks to melee weapons,
      - gain a 5+ invulnerable save.
    """

    def __init__(self, army=None):
        self.army = army
        self.active: bool = False
        self.used_this_battle: bool = False
        self.calls_this_battle: int = 0
        self.called_turn: int | None = None
        self.called_player = None
        self.active_scope: str = "all"
        self._unit_override_effect = "waaagh_active_override"

    @staticmethod
    def _normalized(text: str) -> str:
        value = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower())
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _current_turn(game) -> int | None:
        if game is None:
            return None
        raw = getattr(game, "turn", None)
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _current_phase_name(game) -> str:
        if game is None:
            return ""
        phase = getattr(game, "phase", None)
        return str(getattr(phase, "name", "") or "").strip().upper()

    @staticmethod
    def _game_current_player(game):
        if game is None:
            return None
        getter = getattr(game, "get_current_player", None)
        if callable(getter):
            return getter()
        return None

    def _army_has_waaagh(self) -> bool:
        army = self.army
        if army is None:
            return False
        faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        if faction_id and faction_id != "ORK":
            return False
        if army_has_ability_id(army, ABILITY_WAAAGH):
            return True
        if not faction_id:
            for unit in list(getattr(army, "units", []) or []):
                if self._unit_has_waaagh(unit):
                    return True
        return False

    @staticmethod
    def _unit_is_embarked(unit) -> bool:
        if unit is None:
            return False
        return bool(getattr(unit, "is_embarked", False))

    @staticmethod
    def _unit_parent_army(unit):
        if unit is None:
            return None
        getter = getattr(unit, "get_parent_army", None)
        if callable(getter):
            return getter()
        return getattr(unit, "parent_army", None)

    @staticmethod
    def _unit_root(unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _player_id(player) -> str:
        return str(getattr(player, "id", "") or "").strip()

    def _unit_override_source_key(self, source: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", self._normalized(source)).strip("_")
        return normalized or "source"

    def _unit_override_id(self, *, owner_id: str, source: str) -> str:
        owner_key = str(owner_id or "").strip() or "owner"
        source_key = self._unit_override_source_key(source)
        return f"waaagh_override:{owner_key}:{source_key}"

    def _iter_unit_override_entries(self, unit) -> list[dict]:
        root = self._unit_root(unit)
        if root is None:
            return []
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            return []
        entries = list(special_rules.get("orks_temp_effects", []) or [])
        normalized = [dict(entry) for entry in entries if isinstance(entry, dict)]
        normalized.sort(key=lambda entry: str(entry.get("id", "") or ""))
        return normalized

    def apply_unit_override_until_next_command_phase(self, unit, *, player=None, source: str = "Waaagh override") -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        parent_army = self._unit_parent_army(root)
        if parent_army is not None and self.army is not None and parent_army is not self.army:
            return False
        owner_player = player
        if owner_player is None and parent_army is not None:
            owner_player = getattr(parent_army, "player", None)
        if owner_player is None and self.army is not None:
            owner_player = getattr(self.army, "player", None)
        owner_id = self._player_id(owner_player)
        source_name = str(source or "Waaagh override").strip() or "Waaagh override"
        effect_id = self._unit_override_id(owner_id=owner_id, source=source_name)
        entry = {
            "id": effect_id,
            "source": source_name,
            "effect": self._unit_override_effect,
            "expires_mode": "next_command_phase",
            "expires_scope": "owner_command_phase",
        }
        if owner_id:
            entry["owner_id"] = owner_id
        game = getattr(owner_player, "game", None) if owner_player is not None else None
        current_turn = self._current_turn(game)
        if current_turn is not None:
            entry["turn"] = int(current_turn)

        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        effects = list(special_rules.get("orks_temp_effects", []) or [])
        kept: list[dict] = []
        for effect in effects:
            if not isinstance(effect, dict):
                continue
            if str(effect.get("id", "") or "").strip() == effect_id:
                continue
            kept.append(dict(effect))
        kept.append(entry)
        kept.sort(key=lambda effect: str(effect.get("id", "") or ""))
        updated = dict(special_rules)
        updated["orks_temp_effects"] = kept
        root.special_rules = updated
        return True

    def _unit_has_active_override(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        owner_player = None
        parent_army = self._unit_parent_army(root)
        if parent_army is not None:
            owner_player = getattr(parent_army, "player", None)
        owner_id = self._player_id(owner_player)
        for entry in self._iter_unit_override_entries(root):
            if str(entry.get("effect", "") or "").strip().lower() != self._unit_override_effect:
                continue
            expected_owner = str(entry.get("owner_id", "") or "").strip()
            if expected_owner and owner_id and expected_owner != owner_id:
                continue
            return True
        return False

    @staticmethod
    def _unit_has_keyword(unit, keyword: str) -> bool:
        if unit is None:
            return False
        token = str(keyword or "").strip().upper()
        if not token:
            return False
        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any(token))
        keywords = list(getattr(unit, "keywords", []) or [])
        faction_keywords = list(getattr(unit, "faction_keywords", []) or [])
        pool = [str(k or "").strip().upper() for k in keywords + faction_keywords]
        return token in set(pool)

    @staticmethod
    def _unit_members(unit) -> list:
        if unit is None:
            return []
        members_fn = getattr(unit, "get_attached_unit_members", None)
        if callable(members_fn):
            members = list(members_fn() or [])
            if members:
                return members
        return [unit]

    def _unit_or_members_have_keyword(self, unit, keyword: str) -> bool:
        if self._unit_has_keyword(unit, keyword):
            return True
        for member in self._unit_members(unit):
            if self._unit_has_keyword(member, keyword):
                return True
        return False

    def _unit_or_members_named(self, unit, names: set[str]) -> bool:
        if unit is None:
            return False
        unit_name = self._normalized(getattr(unit, "name", ""))
        if unit_name in names:
            return True
        for member in self._unit_members(unit):
            member_name = self._normalized(getattr(member, "name", ""))
            if member_name in names:
                return True
        return False

    def _orks_detachment_manager(self):
        army = self.army
        if army is None:
            return None
        return getattr(army, "orks_detachments", None)

    def _can_call_bully_boyz_second_waaagh(self, *, game=None, player=None) -> bool:
        mgr = self._orks_detachment_manager()
        if mgr is None:
            return False
        can_call = getattr(mgr, "can_call_second_waaagh", None)
        if not callable(can_call):
            return False
        return bool(can_call(game=game, player=player))

    def _second_waaagh_unit_applies(self, unit) -> bool:
        mgr = self._orks_detachment_manager()
        if mgr is not None:
            applies = getattr(mgr, "bully_boyz_second_waaagh_unit_applies", None)
            if callable(applies):
                return bool(applies(unit))
        named_units = {"nobz", "meganobz"}
        if self._unit_or_members_have_keyword(unit, "WARBOSS"):
            return True
        if self._unit_or_members_have_keyword(unit, "NOBZ"):
            return True
        if self._unit_or_members_have_keyword(unit, "MEGANOBZ"):
            return True
        return self._unit_or_members_named(unit, named_units)

    def _unit_has_waaagh(self, unit) -> bool:
        if unit is None:
            return False
        for ab in list(getattr(unit, "possible_abilities", []) or []):
            if str(getattr(ab, "name", "") or "").strip().lower() == "waaagh!":
                return True
        if self._unit_has_keyword(unit, "ORKS"):
            return True
        return False

    def next_call_scope(self, *, game=None, player=None) -> str:
        calls_used = self._effective_calls_this_battle()
        if calls_used <= 0:
            return "all"
        if calls_used == 1 and self._can_call_bully_boyz_second_waaagh(game=game, player=player):
            return "bully_boyz_restricted"
        return ""

    def next_call_is_second(self, *, game=None, player=None) -> bool:
        return self.next_call_scope(game=game, player=player) == "bully_boyz_restricted"

    def _already_called_this_turn(self, *, game=None) -> bool:
        if self.called_turn is None:
            return False
        current_turn = self._current_turn(game)
        if current_turn is None:
            return False
        return int(current_turn) == int(self.called_turn)

    def _effective_calls_this_battle(self) -> int:
        try:
            calls = int(self.calls_this_battle or 0)
        except (TypeError, ValueError):
            calls = 0
        if calls <= 0 and bool(self.used_this_battle):
            return 1
        return max(calls, 0)

    def can_call_now(self, *, game=None, player=None) -> bool:
        if not self._army_has_waaagh():
            return False
        if game is not None:
            pname = self._current_phase_name(game)
            if pname and pname != "COMMAND_PHASE":
                return False
            if player is not None:
                if self._game_current_player(game) is not player:
                    return False
            if self._already_called_this_turn(game=game):
                return False
        return bool(self.next_call_scope(game=game, player=player))

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        self._clear_unit_overrides_for_command_phase_start(game=game, player=player)
        if not self.active:
            return
        if player is None or self.called_player is not player:
            return
        current_turn = self._current_turn(game)
        if current_turn is None:
            return
        if self.called_turn is None:
            return
        if current_turn > int(self.called_turn):
            self.active = False
            self.active_scope = "all"

    def _clear_unit_overrides_for_command_phase_start(self, *, game=None, player=None) -> None:
        if self.army is None:
            return
        owner_id = self._player_id(player)
        current_turn = self._current_turn(game)
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            effects = list(special_rules.get("orks_temp_effects", []) or [])
            if not effects:
                continue
            kept: list[dict] = []
            changed = False
            for effect in effects:
                if not isinstance(effect, dict):
                    changed = True
                    continue
                if str(effect.get("effect", "") or "").strip().lower() != self._unit_override_effect:
                    kept.append(dict(effect))
                    continue
                expires_mode = str(effect.get("expires_mode", "") or "").strip().lower()
                if expires_mode != "next_command_phase":
                    kept.append(dict(effect))
                    continue
                expires_scope = str(effect.get("expires_scope", "") or "").strip().lower()
                expected_owner = str(effect.get("owner_id", "") or "").strip()
                owner_matches = not expected_owner or (owner_id and expected_owner == owner_id)
                if expires_scope == "owner_command_phase" and not owner_matches:
                    kept.append(dict(effect))
                    continue
                effect_turn_raw = effect.get("turn", None)
                try:
                    effect_turn = int(effect_turn_raw) if effect_turn_raw is not None else 0
                except (TypeError, ValueError):
                    effect_turn = 0
                if effect_turn and current_turn is not None and int(current_turn) <= int(effect_turn):
                    kept.append(dict(effect))
                    continue
                changed = True
            if not changed:
                continue
            updated = dict(special_rules)
            if kept:
                updated["orks_temp_effects"] = kept
            else:
                updated.pop("orks_temp_effects", None)
            root.special_rules = updated

    def call_waaagh(self, *, game=None, player=None) -> bool:
        if not self.can_call_now(game=game, player=player):
            return False
        scope = self.next_call_scope(game=game, player=player)
        if not scope:
            return False
        self.calls_this_battle = self._effective_calls_this_battle() + 1
        self.used_this_battle = self.calls_this_battle > 0
        self.active = True
        self.active_scope = scope
        current_turn = self._current_turn(game)
        self.called_turn = current_turn if current_turn is not None else None
        self.called_player = player

        es = getattr(game, "event_system", None)
        if es is not None:
            units = []
            for unit in list(getattr(self.army, "units", []) or []):
                if self.unit_is_affected(unit, game=game):
                    units.append(unit)
            es.publish(
                "waaagh_called",
                player=player,
                game=game,
                units=units,
                call_number=int(self.calls_this_battle),
                scope=str(self.active_scope or "all"),
            )
        return True

    def can_charge_after_advance(self, unit, *, game=None) -> bool:
        return self.unit_is_affected(unit, game=game)

    def unit_is_affected(self, unit, *, game=None) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if self._unit_is_embarked(root):
            return False
        parent_army = self._unit_parent_army(root)
        if parent_army is not None and parent_army is not self.army:
            return False
        if self._unit_has_active_override(root):
            return True
        if not self.active:
            return False
        if not self._unit_has_waaagh(root):
            return False
        if str(self.active_scope or "").strip().lower() == "bully_boyz_restricted":
            return self._second_waaagh_unit_applies(root)
        return True
