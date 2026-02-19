from __future__ import annotations

from ..utility.entity_ids import get_entity_id
from ..utility.dice import get_roll
from .detachment_manager import DetachmentManagerBase
from .nurgles_gift import NurglesGiftManager


class DeathGuardDetachmentManager(DetachmentManagerBase):
    faction_id = "DG"
    _WORLD_BLIGHT_SOURCE = "worldblight"

    def is_death_lords_chosen(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Death Lord's Chosen")

    def is_virulent_vectorium(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Virulent Vectorium")

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        return unit.get_parent_army() is self.army

    def _unit_is_death_guard(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword_or_faction(unit, "DEATH GUARD", faction_id=self.faction_id)

    def _iter_unique_attached_roots(self):
        if self.army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = unit.get_attached_unit_root()
            uid = get_entity_id(root)
            if uid in seen:
                continue
            seen.add(uid)
            yield root

    @staticmethod
    def _enemy_root_sort_key(unit) -> str:
        return str(get_entity_id(unit) or "")

    def _iter_unique_enemy_roots(self, enemy_army):
        if enemy_army is None:
            return []
        roots = []
        seen: set[str] = set()
        for unit in list(getattr(enemy_army, "units", []) or []):
            if unit is None:
                continue
            root = unit.get_attached_unit_root()
            uid = str(get_entity_id(root) or "")
            if uid in seen:
                continue
            seen.add(uid)
            roots.append(root)
        roots.sort(key=self._enemy_root_sort_key)
        return roots

    def _unit_eligible_for_deadly_vectors(self, unit) -> bool:
        if unit is None:
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if not bool(unit.is_alive()):
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return False
        if bool(unit.is_in_reserves()):
            return False
        return True

    def resolve_deadly_vectors(self, *, game=None, opponent_player=None) -> list[dict]:
        if not self.is_death_lords_chosen():
            return []
        if game is None or opponent_player is None:
            return []
        if not bool(getattr(game, "is_authoritative", True)):
            return []
        opponent_army = getattr(opponent_player, "army", None)
        if opponent_army is None or opponent_army is self.army:
            return []
        game_map = getattr(game, "map", None)
        if game_map is None:
            return []

        outcomes: list[dict] = []
        for unit in self._iter_unique_enemy_roots(opponent_army):
            if not self._unit_eligible_for_deadly_vectors(unit):
                continue
            afflicted = NurglesGiftManager.get_afflicted_plague_for_unit(unit, game=game, game_map=game_map)
            if afflicted is None:
                continue
            roll_2d6 = int(get_roll("2D6") or 0)
            modifier = -1 if bool(unit.is_below_half_strength()) else 0
            total = int(roll_2d6 + modifier)
            mortal_wounds = 0
            if total <= 6:
                mortal_wounds = int(get_roll("D3") or 0)
                if mortal_wounds > 0:
                    unit._apply_mortal_wounds_to_unit(unit, int(mortal_wounds), game_map=game_map)
            outcomes.append(
                {
                    "unit_id": str(get_entity_id(unit) or ""),
                    "roll_2d6": int(roll_2d6),
                    "modifier": int(modifier),
                    "total": int(total),
                    "mortal_wounds": int(max(0, mortal_wounds)),
                }
            )
        return outcomes

    def _unit_eligible_for_worldblight(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_in_army(unit):
            return False
        if not self._unit_is_death_guard(unit):
            return False
        if not unit.is_alive():
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if unit.is_battle_shocked():
            return False
        return True

    def _attached_unit_has_arch_contaminator(self, unit) -> bool:
        if unit is None:
            return False
        root = unit.get_attached_unit_root()
        members = list(root.get_attached_unit_members() or [])
        for member in members:
            sr = getattr(member, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_arch_contaminator"):
                return True
        return False

    def _root_within_controlled_objective(self, root, game) -> bool:
        if root is None or game is None:
            return False
        game_map = getattr(game, "map", None)
        if game_map is None:
            return False
        player = getattr(self.army, "player", None)
        if player is None:
            return False
        objectives = list(getattr(game_map, "objectives", []) or [])
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            loc.update_control(game)
            if getattr(loc, "controlling_player", None) is not player:
                continue
            if root.is_within_objective_range(loc):
                return True
        return False

    def arch_contaminator_reroll_wounds(self, unit, *, game=None) -> bool:
        if not self.is_virulent_vectorium():
            return False
        if unit is None or game is None:
            return False
        root = unit.get_attached_unit_root()
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_death_guard(root):
            return False
        if not root.is_alive() or not bool(getattr(root, "deployed", False)):
            return False
        if not self._attached_unit_has_arch_contaminator(root):
            return False
        return self._root_within_controlled_objective(root, game)

    def on_command_phase_end(self, *, game=None, player=None) -> None:
        if not self.is_virulent_vectorium():
            return
        if game is None or player is None:
            return
        if getattr(player, "army", None) is not self.army:
            return
        game_map = getattr(game, "map", None)
        if game_map is None:
            return
        objectives = list(getattr(game_map, "objectives", []) or [])
        if not objectives:
            return

        # Ensure control state is up to date before applying sticky effects.
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            loc.update_control(game)

        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            if getattr(loc, "controlling_player", None) is not player:
                continue

            has_eligible_unit = False
            for root in self._iter_unique_attached_roots():
                if not self._unit_eligible_for_worldblight(root):
                    continue
                if root.is_within_objective_range(loc):
                    has_eligible_unit = True
                    break
            if not has_eligible_unit:
                continue

            loc.set_sticky_control(player, source=self._WORLD_BLIGHT_SOURCE)
            loc.worldblight_controller = player
            loc.worldblight_source = self._WORLD_BLIGHT_SOURCE
