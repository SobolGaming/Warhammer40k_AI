from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from ..utility.ability_support import ABILITY_SHADOW_OF_CHAOS, army_has_ability_id
from ..utility.dice import get_roll


@dataclass(frozen=True)
class ShadowBattleShockContext:
    modifier: int = 0
    manifestation_active: bool = False
    terror_active: bool = False


class ShadowOfChaosManager:
    """
    Chaos Daemons Army Rule: The Shadow of Chaos.
    """

    GREATER_DAEMON_NAMES = {
        "BLOODTHIRSTER",
        "GREAT UNCLEAN ONE",
        "KAIROS FATEWEAVER",
        "KEEPER OF SECRETS",
        "LORD OF CHANGE",
        "ROTIGUS",
        "SHALAXI HELBANE",
        "SKARBRAND",
    }
    DARK_MASTER_ABILITY = "THE DARK MASTER (AURA)"

    def __init__(self, army=None):
        self.army = army

    def army_has_shadow(self) -> bool:
        return self._army_has_shadow()

    def _army_has_shadow(self) -> bool:
        if self.army is None:
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "CD":
            return False
        return army_has_ability_id(self.army, ABILITY_SHADOW_OF_CHAOS)

    def _unit_is_legiones_daemonica(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return unit.has_any_keyword("LEGIONES DAEMONICA")
        except Exception:
            return False

    def _get_player(self):
        try:
            return getattr(self.army, "player", None)
        except Exception:
            return None

    def _get_game(self):
        try:
            player = self._get_player()
            return getattr(player, "game", None) if player is not None else None
        except Exception:
            return None

    @staticmethod
    def _norm_text(text: str) -> str:
        val = (text or "").lower().strip()
        val = re.sub(r"<[^>]+>", " ", val)
        val = re.sub(r"[^\w\s]", " ", val)
        return re.sub(r"\s+", " ", val).strip()

    @classmethod
    def _unit_has_dark_master(cls, unit) -> bool:
        if unit is None:
            return False
        try:
            abilities = list(getattr(unit, "possible_abilities", []) or [])
        except Exception:
            abilities = []
        if abilities:
            target = cls._norm_text(cls.DARK_MASTER_ABILITY)
            for ab in abilities:
                name = cls._norm_text(getattr(ab, "name", "") or "")
                if name == target or "dark master" in name:
                    return True
        try:
            name = cls._norm_text(getattr(unit, "name", "") or "")
        except Exception:
            name = ""
        if name and name.replace(" ", "") == "belakor":
            return True
        return False

    @classmethod
    def _army_dark_master_units(cls, army) -> list:
        if army is None:
            return []
        out = []
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
            except Exception:
                pass
            if cls._unit_has_dark_master(unit):
                out.append(unit)
        return out

    @classmethod
    def unit_within_dark_master_aura(cls, unit, army, *, game=None) -> bool:
        if unit is None or army is None:
            return False
        try:
            if game is None:
                player = getattr(army, "player", None)
                game = getattr(player, "game", None) if player is not None else None
        except Exception:
            game = None
        if game is None:
            return False
        try:
            from ..utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return False
        for source in cls._army_dark_master_units(army):
            try:
                if unit_within_range_of_unit(source, unit, 6.0, use_attached_aggregate=True):
                    return True
            except Exception:
                continue
        return False

    @classmethod
    def unit_wholly_within_dark_master_aura(cls, unit, army, *, game=None) -> bool:
        if unit is None or army is None:
            return False
        try:
            if game is None:
                player = getattr(army, "player", None)
                game = getattr(player, "game", None) if player is not None else None
        except Exception:
            game = None
        if game is None:
            return False
        try:
            from ..utility.aura_utils import unit_wholly_within_range_of_unit
        except Exception:
            return False
        for source in cls._army_dark_master_units(army):
            try:
                if unit_wholly_within_range_of_unit(source, unit, 6.0, use_attached_aggregate=True):
                    return True
            except Exception:
                continue
        return False

    def get_shadow_zones(self, *, game=None, player=None) -> set[str]:
        if not self._army_has_shadow():
            return set()
        if game is None:
            game = self._get_game()
        if player is None:
            player = self._get_player()
        if game is None or player is None:
            return set()
        try:
            zones = set(game._shadow_of_chaos_zones(player))
        except Exception:
            zones = set()
        return zones

    def _unit_within_shadow_for_player(self, unit, *, game, player) -> bool:
        if unit is None or game is None or player is None:
            return False
        try:
            player_army = getattr(player, "army", None)
        except Exception:
            player_army = None
        if self.unit_within_dark_master_aura(unit, player_army, game=game):
            return True
        zones = self.get_shadow_zones(game=game, player=player)
        if not zones:
            return False
        try:
            opponent = next((p for p in (game.players or []) if p is not player), None)
        except Exception:
            opponent = None
        try:
            models = list(unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(unit, "models", []) or [])

        for model in models:
            try:
                if not getattr(model, "is_alive", True):
                    continue
            except Exception:
                continue
            try:
                x, y, _z, _f = model.get_location()
            except Exception:
                try:
                    x, y, _z = model.get_location()
                except Exception:
                    continue
            in_own = False
            in_enemy = False
            try:
                in_own = game.is_position_in_deployment_zone(float(x), float(y), player.name)
            except Exception:
                in_own = False
            try:
                if opponent is not None:
                    in_enemy = game.is_position_in_deployment_zone(float(x), float(y), opponent.name)
            except Exception:
                in_enemy = False
            zone = "own" if in_own else "enemy" if in_enemy else "nml"
            if zone in zones:
                return True
        return False

    def is_unit_within_shadow(self, unit, *, game=None) -> bool:
        if unit is None or not self._army_has_shadow():
            return False
        try:
            if unit.get_parent_army() is not self.army:
                return False
        except Exception:
            return False
        if game is None:
            game = self._get_game()
        player = self._get_player()
        if game is None or player is None:
            return False
        return self._unit_within_shadow_for_player(unit, game=game, player=player)

    def is_daemonic_manifestation_active(self, unit, *, game=None) -> bool:
        if unit is None:
            return False
        if not self._army_has_shadow():
            return False
        if not self._unit_is_legiones_daemonica(unit):
            return False
        return self.is_unit_within_shadow(unit, game=game)

    @classmethod
    def _unit_is_greater_daemon(cls, unit) -> bool:
        if unit is None:
            return False
        try:
            name = str(getattr(unit, "name", "") or "").upper()
        except Exception:
            name = ""
        if name:
            for n in cls.GREATER_DAEMON_NAMES:
                if n in name:
                    return True
        for n in cls.GREATER_DAEMON_NAMES:
            try:
                if unit.has_any_keyword(n):
                    return True
            except Exception:
                continue
        return False

    @classmethod
    def _army_greater_daemon_units(cls, army) -> list:
        if army is None:
            return []
        out = []
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
            except Exception:
                pass
            if cls._unit_is_greater_daemon(unit):
                out.append(unit)
        return out

    @classmethod
    def unit_within_greater_daemon_terror_range(cls, unit, army, *, game=None) -> bool:
        if unit is None or army is None:
            return False
        try:
            if game is None:
                player = getattr(army, "player", None)
                game = getattr(player, "game", None) if player is not None else None
        except Exception:
            game = None
        if game is None:
            return False
        try:
            from ..utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return False
        for source in cls._army_greater_daemon_units(army):
            try:
                if unit_within_range_of_unit(source, unit, 6.0, use_attached_aggregate=True):
                    return True
            except Exception:
                continue
        return False

    @classmethod
    def enemy_unit_in_shadow_or_terror(cls, unit, *, game=None) -> bool:
        if unit is None:
            return False
        try:
            unit_army = unit.get_parent_army()
        except Exception:
            unit_army = None
        if game is None:
            try:
                player = getattr(unit_army, "player", None) if unit_army is not None else None
                game = getattr(player, "game", None) if player is not None else None
            except Exception:
                game = None
        if game is None:
            return False

        for player in list(getattr(game, "players", []) or []):
            army = getattr(player, "army", None)
            if army is None or army is unit_army:
                continue
            mgr = getattr(army, "shadow_of_chaos", None)
            if mgr is None or not mgr._army_has_shadow():
                continue
            if mgr._unit_within_shadow_for_player(unit, game=game, player=player):
                return True
            if cls.unit_within_greater_daemon_terror_range(unit, army, game=game):
                return True
        return False

    @classmethod
    def battle_shock_context(cls, unit, *, game=None) -> ShadowBattleShockContext:
        modifier = 0
        manifestation = False
        terror = False
        if unit is None:
            return ShadowBattleShockContext()
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "shadow_of_chaos", None) if army is not None else None
        if mgr is not None and mgr.is_daemonic_manifestation_active(unit, game=game):
            modifier += 1
            manifestation = True
        if cls.enemy_unit_in_shadow_or_terror(unit, game=game):
            modifier -= 1
            terror = True
        return ShadowBattleShockContext(modifier=modifier, manifestation_active=manifestation, terror_active=terror)

    @classmethod
    def apply_battle_shock_outcome(cls, unit, *, passed: bool, context: ShadowBattleShockContext, game=None) -> None:
        if unit is None or context is None:
            return
        if context.manifestation_active and passed:
            cls._apply_daemonic_manifestation(unit, game=game)
        if context.terror_active and (not passed):
            cls._apply_daemonic_terror(unit, game=game)

    @classmethod
    def _unit_is_battleline(cls, unit) -> bool:
        if unit is None:
            return False
        try:
            return bool(getattr(unit, "is_battleline", False))
        except Exception:
            pass
        try:
            return unit.has_any_keyword("BATTLELINE")
        except Exception:
            return False

    @classmethod
    def _apply_daemonic_manifestation(cls, unit, *, game=None) -> None:
        if unit is None:
            return
        amount = int(get_roll("D3") or 0)
        if amount <= 0:
            return

        restored = 0
        if cls._unit_is_battleline(unit):
            restored = cls._return_destroyed_models(unit, amount)
        if restored > 0:
            print(f"Shadow of Chaos: {getattr(unit, 'name', 'unit')} returns {restored} model(s).")
            return

        damaged_model = None
        try:
            is_max, model = unit.is_max_health()
            if not is_max:
                damaged_model = model
        except Exception:
            damaged_model = None
        if damaged_model is None:
            for model in list(getattr(unit, "models", []) or []):
                try:
                    base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
                    current = int(getattr(model, "wounds", 0) or 0)
                except Exception:
                    continue
                if base_wounds and current < base_wounds:
                    damaged_model = model
                    break
        if damaged_model is None:
            return
        try:
            damaged_model.heal(amount)
        except Exception:
            try:
                base_wounds = int(getattr(damaged_model, "_base_wounds", getattr(damaged_model, "base_wounds", 0)) or 0)
                damaged_model.wounds = min(base_wounds, int(getattr(damaged_model, "wounds", 0) or 0) + amount)
            except Exception:
                pass
        print(f"Shadow of Chaos: {getattr(unit, 'name', 'unit')} regains up to {amount} lost wounds.")

    @classmethod
    def _return_destroyed_models(cls, unit, amount: int) -> int:
        if unit is None or amount <= 0:
            return 0
        lost = getattr(unit, "models_lost", None)
        if not isinstance(lost, list) or not lost:
            return 0
        restored = 0
        while restored < amount and lost:
            model = lost.pop()
            try:
                if hasattr(model, "set_parent_unit"):
                    model.set_parent_unit(unit)
                else:
                    model.parent_unit = unit
            except Exception:
                pass
            try:
                base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
                if base_wounds:
                    model.wounds = base_wounds
            except Exception:
                pass
            try:
                setattr(model, "_on_death_reactions_resolved", False)
            except Exception:
                pass
            try:
                ref = next((m for m in (getattr(unit, "models", []) or []) if getattr(m, "is_alive", True)), None)
                if ref is not None and hasattr(model, "set_location"):
                    model.set_location(*ref.get_location())
            except Exception:
                pass
            try:
                unit.models.append(model)
            except Exception:
                pass
            restored += 1
        try:
            if hasattr(unit, "update_coherency"):
                unit.update_coherency()
        except Exception:
            pass
        return restored

    @classmethod
    def _apply_daemonic_terror(cls, unit, *, game=None) -> None:
        if unit is None:
            return
        amount = int(get_roll("D3") or 0)
        if amount <= 0:
            return
        try:
            game_map = getattr(game, "map", None) if game is not None else None
        except Exception:
            game_map = None
        try:
            if hasattr(unit, "_apply_mortal_wounds_to_unit"):
                unit._apply_mortal_wounds_to_unit(unit, amount, game_map=game_map)
            else:
                for model in list(getattr(unit, "models", []) or []):
                    if amount <= 0:
                        break
                    if not getattr(model, "is_alive", True):
                        continue
                    try:
                        model.take_damage(1, is_mortal=True, weapon_profile=None, game_map=game_map)
                        amount -= 1
                    except Exception:
                        break
        except Exception:
            return
        print(f"Shadow of Chaos: {getattr(unit, 'name', 'unit')} suffers mortal wounds from Daemonic Terror.")
