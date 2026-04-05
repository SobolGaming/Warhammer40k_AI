from __future__ import annotations

from typing import Optional

from ..utility.event_bus import append_action


class FatesInFluxManager:
    OWNER_ROLL_TYPES = {"advance", "hit", "wound", "damage", "save", "hazardous"}
    OPPONENT_ROLL_TYPES = {"advance", "hit", "wound", "save"}

    def __init__(self, game=None):
        self.game = game
        self.tokens_by_player_id: dict[str, int] = {}
        self._initialized_players: set[str] = set()
        self._command_phase_awarded_turn: dict[str, int] = {}

    def to_dict(self) -> dict:
        return {
            "tokens_by_player_id": dict(self.tokens_by_player_id or {}),
            "initialized_players": sorted(self._initialized_players),
            "command_phase_awarded_turn": dict(self._command_phase_awarded_turn or {}),
        }

    @classmethod
    def from_dict(cls, data: dict | None, *, game=None) -> "FatesInFluxManager":
        mgr = cls(game=game)
        if not isinstance(data, dict):
            return mgr
        tokens = data.get("tokens_by_player_id", {}) or {}
        mgr.tokens_by_player_id = {str(k): int(v) for k, v in tokens.items()}
        mgr._initialized_players = {str(v) for v in list(data.get("initialized_players", []) or [])}
        awarded = data.get("command_phase_awarded_turn", {}) or {}
        mgr._command_phase_awarded_turn = {str(k): int(v) for k, v in awarded.items()}
        return mgr

    def _resolve_player(self, game, player_id: Optional[str]):
        if game is None or not player_id:
            return None
        registry = getattr(game, "entity_registry", None)
        if registry is not None:
            found = registry.get(str(player_id), kind="player")
            if found is not None:
                return found
        for player in list(getattr(game, "players", []) or []):
            if str(getattr(player, "id", "")) == str(player_id):
                return player
        return None

    def _resolve_unit(self, game, unit_id: Optional[str]):
        if game is None or not unit_id:
            return None
        registry = getattr(game, "entity_registry", None)
        if registry is None:
            return None
        return registry.get(str(unit_id), kind="unit")

    def _normalize_detachment(self, name: str) -> str:
        return " ".join(str(name or "").lower().split())

    def _player_has_fates_in_flux(self, player) -> bool:
        if player is None:
            return False
        army = getattr(player, "army", None)
        if army is None:
            army = player.get_army()
        if army is None:
            return False
        mgr = getattr(army, "chaos_daemons_detachments", None)
        if mgr is not None and hasattr(mgr, "is_scintillating_legion_detachment"):
            return bool(mgr.is_scintillating_legion_detachment())
        has_detachment = getattr(army, "has_detachment_type", None)
        if callable(has_detachment):
            return bool(has_detachment("Scintillating Legion"))
        det = self._normalize_detachment(getattr(army, "detachment_type", "") or "")
        return det == self._normalize_detachment("Scintillating Legion")

    def _opponent_has_fates_in_flux(self, game, player) -> bool:
        if game is None or player is None:
            return False
        for other in list(getattr(game, "players", []) or []):
            if other is player:
                continue
            if self._player_has_fates_in_flux(other):
                return True
        return False

    def _resolve_opponent(self, game, player):
        if game is None or player is None:
            return None
        for other in list(getattr(game, "players", []) or []):
            if other is player:
                continue
            return other
        return None

    def _is_tzeentch_legiones(self, unit) -> bool:
        if unit is None:
            return False
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
        for candidate in (unit, root):
            if candidate is None:
                continue
            if candidate.has_any_keyword("TZEENTCH") and candidate.has_any_keyword("LEGIONES DAEMONICA"):
                return True
        return False

    def ensure_initialized(self, game) -> None:
        if game is None:
            return
        for player in list(getattr(game, "players", []) or []):
            if player is None:
                continue
            pid = str(getattr(player, "id", "") or "")
            if not pid:
                continue
            if pid not in self.tokens_by_player_id:
                self.tokens_by_player_id[pid] = 0
            if pid not in self._initialized_players and self._player_has_fates_in_flux(player):
                self.tokens_by_player_id[pid] = 3
                self._initialized_players.add(pid)

    def tokens_for_player(self, player) -> int:
        pid = str(getattr(player, "id", "") or "")
        if not pid:
            return 0
        return int(self.tokens_by_player_id.get(pid, 0) or 0)

    def gain_tokens(self, player, amount: int, *, reason: str = "") -> int:
        if player is None:
            return 0
        pid = str(getattr(player, "id", "") or "")
        if not pid:
            return 0
        amount = int(amount or 0)
        if amount <= 0:
            return 0
        self.tokens_by_player_id[pid] = int(self.tokens_by_player_id.get(pid, 0) or 0) + amount
        append_action(player, f"Fates in Flux: +{amount} Flux token(s){' (' + reason + ')' if reason else ''}.")
        return amount

    def spend_tokens(self, player, amount: int, *, reason: str = "") -> bool:
        if player is None:
            return False
        pid = str(getattr(player, "id", "") or "")
        if not pid:
            return False
        amount = int(amount or 0)
        if amount <= 0:
            return False
        current = int(self.tokens_by_player_id.get(pid, 0) or 0)
        if current < amount:
            return False
        self.tokens_by_player_id[pid] = current - amount
        opponent = self._resolve_opponent(self.game, player)
        if opponent is not None:
            oid = str(getattr(opponent, "id", "") or "")
            if oid:
                self.tokens_by_player_id[oid] = int(self.tokens_by_player_id.get(oid, 0) or 0) + amount
        append_action(player, f"Fates in Flux: -{amount} Flux token(s){' (' + reason + ')' if reason else ''}.")
        return True

    def can_use_flux_reroll(self, *, game, player, unit, roll_type: str) -> bool:
        if game is None or player is None:
            return False
        self.ensure_initialized(game)
        if self.tokens_for_player(player) <= 0:
            return False
        rt = str(roll_type or "").strip().lower()
        if not rt:
            return False
        if self._player_has_fates_in_flux(player):
            if rt not in self.OWNER_ROLL_TYPES:
                return False
            if not self._is_tzeentch_legiones(unit):
                return False
            return True
        if rt not in self.OPPONENT_ROLL_TYPES:
            return False
        return True

    def build_reroll_rule(self, *, game, player, unit, roll_type: str) -> Optional[dict]:
        if not self.can_use_flux_reroll(game=game, player=player, unit=unit, roll_type=roll_type):
            return None
        tokens = int(self.tokens_for_player(player) or 0)
        if tokens <= 0:
            return None
        return {
            "action_id": "flux_reroll",
            "label": "Flux token re-roll",
            "mode": "select",
            "allow_success": True,
            "max_select": int(tokens),
            "source": "Fates in Flux",
        }

    def on_command_phase_start(self, *, game, player) -> None:
        if game is None or player is None:
            return
        self.ensure_initialized(game)
        if not self._player_has_fates_in_flux(player):
            return
        pid = str(getattr(player, "id", "") or "")
        if not pid:
            return
        turn = int(getattr(game, "turn", 0) or 0)
        if self._command_phase_awarded_turn.get(pid) == turn:
            return
        opponent = self._resolve_opponent(game, player)
        if opponent is None:
            return
        if self.tokens_for_player(opponent) <= 0:
            self._command_phase_awarded_turn[pid] = turn
            return
        self.gain_tokens(player, 1, reason="Command phase")
        try:
            from .enhancement_descriptors import get_enhancement_tool_descriptor
            desc = get_enhancement_tool_descriptor(enhancement_id="000009810002", name="Inescapable Eye")
            try:
                bonus = int(getattr(desc, "effect_params", {}).get("amount", 1) or 1)
            except Exception:
                bonus = 1
        except Exception:
            bonus = 1
        try:
            army = player.get_army() if hasattr(player, "get_army") else getattr(player, "army", None)
        except Exception:
            army = None
        if army is not None:
            for unit in list(getattr(army, "units", []) or []):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict) or not sr.get("enhancement_inescapable_eye"):
                    continue
                try:
                    if hasattr(unit, "is_active_for_rules") and not unit.is_active_for_rules():
                        continue
                except Exception:
                    continue
                bearer = None
                try:
                    get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
                    if callable(get_bearer):
                        bearer = get_bearer()
                except Exception:
                    bearer = None
                if bearer is None:
                    continue
                self.gain_tokens(player, bonus, reason="Inescapable Eye")
        self._command_phase_awarded_turn[pid] = turn

    def resolve_rule_context(self, *, game, player_id: Optional[str], unit_id: Optional[str], roll_type: str) -> tuple[object | None, object | None, str]:
        player = self._resolve_player(game, player_id)
        unit = self._resolve_unit(game, unit_id)
        return player, unit, str(roll_type or "")
