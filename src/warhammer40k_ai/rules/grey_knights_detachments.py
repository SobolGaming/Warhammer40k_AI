from __future__ import annotations

from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class GreyKnightsDetachmentManager(DetachmentManagerBase):
    faction_id = "GK"

    def __init__(self, army=None):
        super().__init__(army)
        self._hallowed_ground_phase_key: tuple | None = None
        self._hallowed_ground_nml_active: bool = False
        self._hallowed_ground_enemy_active: bool = False

    def is_brotherhood_strike(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Brotherhood Strike")

    def is_hallowed_conclave(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hallowed Conclave")

    def is_warpbane_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Warpbane Task Force")

    def _attached_unit_has_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for u in members:
            if self._unit_has_keyword(u, keyword):
                return True
        return False

    def _is_grey_knights_unit(self, unit) -> bool:
        if unit is None:
            return False
        if self._attached_unit_has_keyword(unit, "GREY KNIGHTS"):
            return True
        return self._army_faction_matches(self.faction_id)

    def _is_purifier_squad_unit(self, unit) -> bool:
        if unit is None:
            return False
        if self._attached_unit_has_keyword(unit, "PURIFIER SQUAD"):
            return True
        return "purifier squad" in str(getattr(unit, "name", "") or "").lower()

    def _unit_is_active(self, unit) -> bool:
        if unit is None:
            return False
        fn = getattr(unit, "is_active_for_rules", None)
        if callable(fn):
            return bool(fn())
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not is_alive():
            return False
        if not bool(getattr(unit, "deployed", True)):
            return False
        if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return False
        if getattr(unit, "embarked_in", None) is not None:
            return False
        return True

    def _hallowed_ground_phase_key_for_game(self, game) -> tuple:
        try:
            round_num = int(getattr(game, "turn", 0) or 0)
        except Exception:
            round_num = 0
        try:
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            phase_name = ""
        return (round_num, phase_name)

    def on_phase_start(self, *, game=None) -> None:
        if not self.is_warpbane_task_force():
            return
        if game is None:
            return
        player = getattr(self.army, "player", None)
        if player is None:
            return
        phase_key = self._hallowed_ground_phase_key_for_game(game)
        self._hallowed_ground_phase_key = phase_key
        self._hallowed_ground_nml_active = False
        self._hallowed_ground_enemy_active = False
        zones = set()
        if hasattr(game, "_shadow_of_chaos_zones"):
            zones = set(game._shadow_of_chaos_zones(player))
        self._hallowed_ground_nml_active = "nml" in zones
        self._hallowed_ground_enemy_active = "enemy" in zones

    def _active_hallowed_ground_zones(self, game) -> set[str]:
        zones = {"own"}
        if game is None:
            return zones
        phase_key = self._hallowed_ground_phase_key_for_game(game)
        if self._hallowed_ground_phase_key == phase_key:
            if self._hallowed_ground_nml_active:
                zones.add("nml")
            if self._hallowed_ground_enemy_active:
                zones.add("enemy")
        return zones

    def _iter_purifier_units(self) -> list:
        army = getattr(self, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        sources: list = []
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            if root is None:
                continue
            rid = get_entity_id(root)
            if rid in seen:
                continue
            seen.add(rid)
            if not self._is_purifier_squad_unit(root):
                continue
            if not self._unit_is_active(root):
                continue
            sources.append(root)
        return sources

    def _model_is_within_hallowed_ground(
        self,
        model,
        *,
        game,
        player,
        opponent,
        zones: set[str],
        purifier_units: list,
    ) -> bool:
        if model is None:
            return False
        if not getattr(model, "is_alive", True):
            return False
        if not hasattr(model, "get_location"):
            return False
        location = model.get_location()
        if location is None or len(location) < 2:
            return False
        x = float(location[0])
        y = float(location[1])
        base = getattr(model, "model_base", None)
        if base is None:
            return False

        in_own = game.is_position_wholly_in_deployment_zone(x, y, base, player.id)
        in_enemy = False
        if opponent is not None:
            in_enemy = game.is_position_wholly_in_deployment_zone(x, y, base, opponent.id)

        if in_own and "own" in zones:
            return True
        if in_enemy and "enemy" in zones:
            return True
        if (not in_own and not in_enemy) and "nml" in zones:
            return True

        from ..utility.aura_utils import model_wholly_within_range_of_unit

        for source in purifier_units:
            if model_wholly_within_range_of_unit(source, model, 6.0, use_attached_aggregate=True):
                return True
        return False

    def _paragon_treat_as_within_hallowed_ground_active(self, unit, *, game=None) -> bool:
        if unit is None:
            return False
        if game is None:
            player = getattr(self.army, "player", None)
            if player is not None:
                game = getattr(player, "game", None)
        if game is None:
            return False
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("paragon_of_sanctity_hallowed_ground_active", False)):
            return False
        try:
            effect_turn = int(sr.get("paragon_of_sanctity_hallowed_ground_turn", 0) or 0)
        except Exception:
            effect_turn = 0
        effect_phase = str(sr.get("paragon_of_sanctity_hallowed_ground_phase", "") or "").strip().upper()
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        return bool(effect_turn == current_turn and effect_phase and effect_phase == current_phase)

    def model_wholly_within_hallowed_ground(self, model, *, game=None) -> bool:
        if not self.is_warpbane_task_force():
            return False
        if model is None:
            return False
        player = getattr(self.army, "player", None)
        if player is None:
            return False
        if game is None:
            game = getattr(player, "game", None)
        if game is None:
            return False
        opponent = next((p for p in (getattr(game, "players", None) or []) if p is not player), None)
        zones = self._active_hallowed_ground_zones(game)
        purifier_units = self._iter_purifier_units()
        return self._model_is_within_hallowed_ground(
            model,
            game=game,
            player=player,
            opponent=opponent,
            zones=zones,
            purifier_units=purifier_units,
        )

    def unit_within_hallowed_ground(self, unit, *, game=None) -> bool:
        if not self.is_warpbane_task_force():
            return False
        if self.unit_wholly_within_hallowed_ground(unit, game=game):
            return True
        return self._paragon_treat_as_within_hallowed_ground_active(unit, game=game)

    def unit_wholly_within_hallowed_ground(self, unit, *, game=None) -> bool:
        if not self.is_warpbane_task_force():
            return False
        if unit is None:
            return False
        player = getattr(self.army, "player", None)
        if player is None:
            return False
        if game is None:
            game = getattr(player, "game", None)
        if game is None:
            return False
        opponent = next((p for p in (getattr(game, "players", None) or []) if p is not player), None)
        zones = self._active_hallowed_ground_zones(game)

        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None:
            return False
        if hasattr(root, "get_attached_unit_models"):
            models = list(root.get_attached_unit_models() or [])
        else:
            models = list(getattr(root, "models", []) or [])
        if not models:
            return False

        purifier_units = self._iter_purifier_units()

        for model in models:
            if not self._model_is_within_hallowed_ground(
                model,
                game=game,
                player=player,
                opponent=opponent,
                zones=zones,
                purifier_units=purifier_units,
            ):
                return False
        return True

    def hallowed_ground_hit_reroll_mods(
        self,
        attacker_model,
        target_unit,
        *,
        attack_type: str = "any",
        game=None,
        game_map=None,
        target_visible: bool | None = None,
    ) -> dict:
        if not self.is_warpbane_task_force():
            return {}
        unit = getattr(attacker_model, "parent_unit", None)
        if unit is None or not self._is_grey_knights_unit(unit):
            return {}
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            return {}
        if atype == "ranged":
            if target_visible is False:
                return {}
            if target_visible is None:
                if game_map is not None and hasattr(unit, "_has_line_of_sight_to_target"):
                    target_visible = bool(unit._has_line_of_sight_to_target(attacker_model, target_unit, game_map))
                else:
                    target_visible = False
            if not target_visible:
                return {}

        if game is None:
            player = getattr(self.army, "player", None)
            game = getattr(player, "game", None) if player is not None else None

        reroll_values = {1}
        reroll_reasons = ["Hallowed Ground: re-roll Hit rolls of 1"]
        reroll_full = False
        reroll_full_reasons: list[str] = []
        if self._is_purifier_squad_unit(unit) or self.unit_wholly_within_hallowed_ground(unit, game=game):
            reroll_full = True
            reroll_full_reasons.append("Hallowed Ground: re-roll Hit roll")

        return {
            "reroll_values": tuple(sorted(reroll_values)),
            "reroll_reasons": tuple(reroll_reasons),
            "reroll_full": bool(reroll_full),
            "reroll_full_reasons": tuple(reroll_full_reasons),
        }

    def duty_before_all_applies(self, unit) -> bool:
        if not self.is_hallowed_conclave():
            return False
        if unit is None:
            return False
        return self._attached_unit_has_keyword(unit, "GREY KNIGHTS") and self._attached_unit_has_keyword(unit, "TERMINATOR")

    def fury_of_titan_applies(self, unit, *, used_deep_strike: bool = False) -> bool:
        if not self.is_brotherhood_strike():
            return False
        if unit is None or not used_deep_strike:
            return False
        return True

    def apply_fury_of_titan(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_brotherhood_strike():
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in members:
            try:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["fury_of_titan_active"] = True
                sr["fury_of_titan_expires_phase"] = "FIGHT_PHASE"
                member.special_rules = sr
            except Exception:
                continue
        return True
