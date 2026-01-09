from __future__ import annotations

import re
from typing import Optional

from ..utility.aura_utils import unit_within_range_of_unit


class EmperorsChildrenDetachmentManager:
    """
    Emperor's Children detachment rule helpers.

    Tracks:
    - Coterie of the Conceited: pledge targets + pact points
    - Slaanesh's Chosen: Favoured Champions switching
    - Court of the Phoenician: Master of the Pageant CP reduction usage
    """

    def __init__(self, army=None):
        self.army = army
        self.pact_points: int = 0
        self.pledge_target: int = 0
        self.pledge_round: int = 0
        self.pledge_max_units: int = 0
        self.units_destroyed_this_round: int = 0

        self.favoured_champions_unit_id: Optional[str] = None
        self._pending_favoured_unit_id: Optional[str] = None
        self._pending_favoured_turn_key: Optional[tuple] = None
        self._favoured_switch_used_turn_key: Optional[tuple] = None

        self.master_of_pageant_used_round: int = 0
        self.unbound_arrogance_used_round: int = 0

    def _norm(self, text: str) -> str:
        t = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower())
        return re.sub(r"\s+", " ", t).strip()

    def _detachment_type_matches(self, detachment_name: str) -> bool:
        try:
            det = self._norm(getattr(self.army, "detachment_type", "") or "")
        except Exception:
            det = ""
        target = self._norm(detachment_name)
        if not det or not target:
            return False
        if det == target:
            return True
        if det.endswith("s") and det[:-1] == target:
            return True
        if target.endswith("s") and target[:-1] == det:
            return True
        return det in target or target in det

    def is_ec_army(self) -> bool:
        try:
            fid = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            fid = ""
        return fid == "EC"

    def is_emperors_children_unit(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if unit.has_any_keyword("EMPEROR'S CHILDREN"):
                return True
        except Exception:
            pass
        return self.is_ec_army()

    def is_legions_of_excess_unit(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return bool(unit.has_any_keyword("LEGIONS OF EXCESS"))
        except Exception:
            return False

    def is_mercurial_host(self) -> bool:
        return self._detachment_type_matches("Mercurial Host")

    def is_peerless_bladesmen(self) -> bool:
        return self._detachment_type_matches("Peerless Bladesmen")

    def is_rapid_evisceration(self) -> bool:
        return self._detachment_type_matches("Rapid Evisceration")

    def is_carnival_of_excess(self) -> bool:
        return self._detachment_type_matches("Carnival of Excess")

    def is_coterie_of_conceited(self) -> bool:
        return self._detachment_type_matches("Coterie of the Conceited")

    def is_slaaneshs_chosen(self) -> bool:
        return self._detachment_type_matches("Slaanesh's Chosen")

    def is_court_of_the_phoenician(self) -> bool:
        return self._detachment_type_matches("Court of the Phoenician")

    def _battle_round(self, game) -> int:
        try:
            return int(getattr(game, "turn", 0) or 0)
        except Exception:
            return 0

    def _turn_key(self, game) -> tuple:
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        try:
            current = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current = None
        return (br, id(current))

    def _unit_on_battlefield(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if not unit.is_alive():
                return False
        except Exception:
            pass
        try:
            if not bool(getattr(unit, "deployed", False)):
                return False
        except Exception:
            return False
        try:
            if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
                return False
        except Exception:
            pass
        try:
            if callable(getattr(unit, "is_embarked", None)) and bool(unit.is_embarked()):
                return False
        except Exception:
            pass
        try:
            if getattr(unit, "embarked_in", None) is not None:
                return False
        except Exception:
            pass
        return True

    def _get_warlord_unit(self):
        try:
            if getattr(self.army, "warlord", None) is not None:
                return self.army.warlord
        except Exception:
            pass
        try:
            for u in list(getattr(self.army, "units", []) or []):
                if getattr(u, "is_warlord", False):
                    return u
        except Exception:
            return None
        return None

    def warlord_on_battlefield(self) -> bool:
        warlord = self._get_warlord_unit()
        return self._unit_on_battlefield(warlord)

    def on_battle_round_start(self, game) -> None:
        br = self._battle_round(game)
        if br <= 0:
            return
        self.units_destroyed_this_round = 0
        self.pledge_round = br
        self.pledge_target = 0
        self.pledge_max_units = 0
        self._pending_favoured_unit_id = None
        self._pending_favoured_turn_key = None
        self._favoured_switch_used_turn_key = None
        self._ensure_initial_favoured_champions()

    def _ensure_initial_favoured_champions(self) -> None:
        if not self.is_slaaneshs_chosen():
            return
        if self.favoured_champions_unit_id:
            return
        warlord = self._get_warlord_unit()
        if warlord is None:
            return
        try:
            root = warlord.get_attached_unit_root()
        except Exception:
            root = warlord
        uid = getattr(root, "_id", None)
        if uid:
            self.favoured_champions_unit_id = uid

    def set_pledge_target(self, value: int, *, battle_round: Optional[int] = None, max_value: Optional[int] = None) -> int:
        try:
            v = int(value)
        except Exception:
            v = 0
        if max_value is not None:
            try:
                self.pledge_max_units = int(max_value)
            except Exception:
                pass
        if v <= 0:
            self.pledge_target = 0
        else:
            lo = 1
            hi = int(self.pledge_max_units or max_value or v)
            if hi <= 0:
                hi = v
            self.pledge_target = max(lo, min(v, hi))
        if battle_round is not None:
            try:
                self.pledge_round = int(battle_round)
            except Exception:
                pass
        return int(self.pledge_target or 0)

    def increase_pledge(self, delta: int = 1) -> int:
        try:
            delta = int(delta)
        except Exception:
            delta = 1
        current = int(self.pledge_target or 0)
        new_val = max(0, current + delta)
        if int(self.pledge_max_units or 0) > 0:
            new_val = min(new_val, int(self.pledge_max_units))
        self.pledge_target = new_val
        return new_val

    def record_enemy_unit_destroyed(self, destroyed_unit, destroyed_by_unit, *, game=None) -> None:
        if destroyed_by_unit is None:
            return
        try:
            if destroyed_by_unit.get_parent_army() is not self.army:
                return
        except Exception:
            return
        try:
            if destroyed_unit.get_parent_army() is self.army:
                return
        except Exception:
            pass

        if self.is_coterie_of_conceited():
            self.units_destroyed_this_round += 1

        if not self.is_slaaneshs_chosen():
            return
        if game is None:
            return
        try:
            if not getattr(destroyed_by_unit, "is_character", False):
                return
        except Exception:
            return
        if not self.is_emperors_children_unit(destroyed_by_unit):
            return
        turn_key = self._turn_key(game)
        if self._favoured_switch_used_turn_key == turn_key:
            return
        if self._pending_favoured_unit_id:
            return
        try:
            root = destroyed_by_unit.get_attached_unit_root()
        except Exception:
            root = destroyed_by_unit
        uid = getattr(root, "_id", None)
        if not uid:
            return
        self._pending_favoured_unit_id = uid
        self._pending_favoured_turn_key = turn_key

    def resolve_pledge_end_of_round(self, game) -> dict:
        """
        Resolve Pledges to the Dark Prince at the end of the battle round.

        Returns a small result dict for UI/logging hooks.
        """
        if not self.is_coterie_of_conceited():
            return {"resolved": False}
        br = self._battle_round(game)
        if br <= 0:
            return {"resolved": False}
        pledge = int(self.pledge_target or 0)
        destroyed = int(self.units_destroyed_this_round or 0)
        if pledge <= 0:
            return {"resolved": False, "pledge": pledge, "destroyed": destroyed}
        success = destroyed >= pledge
        if success:
            try:
                self.pact_points += int(pledge)
            except Exception:
                pass
        else:
            warlord = self._get_warlord_unit()
            if warlord is not None:
                try:
                    from ..utility.dice import DiceCollection
                    dmg_roll, _dice = DiceCollection.from_string("D3").roll_detailed()
                except Exception:
                    dmg_roll = 0
                try:
                    warlord._apply_mortal_wounds_to_unit(
                        warlord,
                        int(dmg_roll or 0),
                        game_map=getattr(game, "map", None),
                    )
                except Exception:
                    pass
        return {"resolved": True, "pledge": pledge, "destroyed": destroyed, "success": success}

    def resolve_pending_favoured_champions(self, unit, *, game=None) -> bool:
        if not self.is_slaaneshs_chosen():
            return False
        if self._pending_favoured_unit_id is None:
            return False
        if game is None:
            return False
        turn_key = self._turn_key(game)
        if self._pending_favoured_turn_key and self._pending_favoured_turn_key != turn_key:
            self._pending_favoured_unit_id = None
            self._pending_favoured_turn_key = None
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        uid = getattr(root, "_id", None)
        if not uid or uid != self._pending_favoured_unit_id:
            return False
        self.favoured_champions_unit_id = uid
        self._pending_favoured_unit_id = None
        self._pending_favoured_turn_key = None
        self._favoured_switch_used_turn_key = turn_key
        return True

    def is_favoured_champions(self, unit) -> bool:
        if not unit or not self.favoured_champions_unit_id:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            return getattr(root, "_id", None) == self.favoured_champions_unit_id
        except Exception:
            return False

    def active_pact_thresholds(self) -> list[str]:
        pts = int(self.pact_points or 0)
        thresholds = []
        if pts >= 1:
            thresholds.append("1+")
        if pts >= 3:
            thresholds.append("3+")
        if pts >= 5:
            thresholds.append("5+")
        if pts >= 7:
            thresholds.append("7+")
        return thresholds

    def pact_points_at_least(self, value: int) -> bool:
        try:
            return int(self.pact_points or 0) >= int(value)
        except Exception:
            return False

    def mechanised_murder_applies(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_rapid_evisceration():
            return False
        if not self.is_emperors_children_unit(unit):
            return False
        try:
            if getattr(unit, "is_transport", False):
                return True
        except Exception:
            pass
        try:
            if bool(getattr(getattr(unit, "round_state", None), "disembarked_this_round", False)):
                return True
        except Exception:
            pass
        return False

    def quicksilver_grace_applies(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_mercurial_host():
            return False
        return self.is_emperors_children_unit(unit)

    def exquisite_swordsmanship_applies(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_peerless_bladesmen():
            return False
        return self.is_emperors_children_unit(unit)

    def sensational_performance_applies(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_court_of_the_phoenician():
            return False
        return self.is_emperors_children_unit(unit)

    def internal_rivalries_applies(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_slaaneshs_chosen():
            return False
        try:
            if not bool(getattr(unit, "is_character", False)):
                return False
        except Exception:
            return False
        return self.is_emperors_children_unit(unit)

    def is_empowered(self, unit, *, game=None) -> bool:
        if unit is None:
            return False
        if not self.is_carnival_of_excess():
            return False
        try:
            if unit.get_parent_army() is not self.army:
                return False
        except Exception:
            pass
        if not self._unit_on_battlefield(unit):
            return False
        if game is None:
            try:
                game = self.army.player.game
            except Exception:
                game = None
        if game is None:
            return False
        try:
            allies = list(getattr(self.army, "units", []) or [])
        except Exception:
            allies = []
        if self.is_emperors_children_unit(unit):
            for other in allies:
                if other is unit:
                    continue
                if not self.is_legions_of_excess_unit(other):
                    continue
                if not self._unit_on_battlefield(other):
                    continue
                try:
                    if unit_within_range_of_unit(unit, other, 6.0, use_attached_aggregate=True):
                        return True
                except Exception:
                    continue
        if self.is_legions_of_excess_unit(unit):
            for other in allies:
                if other is unit:
                    continue
                if not self.is_emperors_children_unit(other):
                    continue
                if not self._unit_on_battlefield(other):
                    continue
                try:
                    if unit_within_range_of_unit(unit, other, 6.0, use_attached_aggregate=True):
                        return True
                except Exception:
                    continue
        return False
