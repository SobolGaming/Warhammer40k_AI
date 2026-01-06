from typing import Tuple, Dict, Set, List, Optional
from warhammer40k_ai.classes.unit import Unit
from warhammer40k_ai.classes.enhancement import Enhancement
from warhammer40k_ai.waha_helper import WahaHelper
from warhammer40k_ai.utility.ability_support import ABILITY_DISPARATE_PATHS, army_has_ability_id, pact_restrictions_for_faction
import codecs
import uuid


# Define custom exception for validation errors
class ArmyValidationError(Exception):
    pass


def get_faction_id_from_name(faction_name: str) -> Optional[str]:
    """
    Map faction names from army list files to faction IDs used in datasheets.
    This mapping helps ensure the correct faction-specific datasheet is loaded.
    """
    import json
    import os
    
    # Normalize faction name for comparison
    faction_name_lower = faction_name.lower().strip()
    
    # Load factions from the JSON file
    factions_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'wahapedia_data', 'Factions.json')
    try:
        with open(factions_file, 'r', encoding='utf-8') as f:
            factions = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load Factions.json: {e}")
        return None
    
    # Try exact match first
    for faction in factions:
        if faction['name'].lower() == faction_name_lower:
            return faction['id']
    
    # Try partial matches for more flexible matching
    for faction in factions:
        faction_name_json = faction['name'].lower()
        if faction_name_json in faction_name_lower or faction_name_lower in faction_name_json:
            return faction['id']
    
    # If no match found, return None (will use generic lookup)
    return None


class Army:
    def __init__(self, faction: str, detachment_type: str, points_limit: int = 2000):
        self._id = str(uuid.uuid4())
        self.faction = faction
        # faction_id from Factions.json if known; set by parse_army_list
        self.faction_id: Optional[str] = None
        self.faction_keyword = []
        self.detachment_type = detachment_type
        self.points_limit = points_limit
        self.units = []
        self.warlord = None
        self.enhancements = []  # List of Enhancements used in the army
        self.detachment_rules = {}  # Placeholder for detachment-specific rules
        self.player = None  # Reference to the owning player

        # World Eaters: Blessings of Khorne (only used when faction_id == "WE", but safe to always attach).
        try:
            from .blessings_of_khorne import BlessingsOfKhorneManager
            self.blessings_of_khorne = BlessingsOfKhorneManager()
        except Exception:
            self.blessings_of_khorne = None

        # Aeldari: Battle Focus (safe to attach, no-op if not Aeldari/Asuryani).
        try:
            from .battle_focus import BattleFocusManager
            self.battle_focus = BattleFocusManager(self)
        except Exception:
            self.battle_focus = None

        # Space Marines (Black Templars): Templar Vows (safe to attach, no-op if not applicable).
        try:
            from .templar_vows import TemplarVowsManager
            self.templar_vows = TemplarVowsManager(self)
        except Exception:
            self.templar_vows = None

        # Space Marines: Oath of Moment (safe to attach, no-op if not applicable).
        try:
            from .oath_of_moment import OathOfMomentManager
            self.oath_of_moment = OathOfMomentManager(self)
        except Exception:
            self.oath_of_moment = None

        # Death Guard: Nurgle's Gift (Aura) plagues (safe to attach, no-op if not applicable).
        try:
            from .nurgles_gift import NurglesGiftManager
            self.nurgles_gift = NurglesGiftManager(self)
        except Exception:
            self.nurgles_gift = None

        # Chaos Daemons: The Shadow of Chaos (safe to attach, no-op if not applicable).
        try:
            from .shadow_of_chaos import ShadowOfChaosManager
            self.shadow_of_chaos = ShadowOfChaosManager(self)
        except Exception:
            self.shadow_of_chaos = None

        # Chaos Daemons: Belakor Shadow Form selection (safe to attach, no-op if not applicable).
        try:
            from .shadow_form import ShadowFormManager
            self.shadow_form = ShadowFormManager(self)
        except Exception:
            self.shadow_form = None
    
    def add_unit(self, unit: Unit) -> bool:
        if not self.faction_keyword:
            self.faction_keyword = unit.faction_keywords
        # TODO - fix once support for things like World Eaters Daemonkin Detachment is added
        #elif unit.faction_keywords != self.faction_keyword:
        #    raise ArmyValidationError(f"Unit {unit.name} does not match army faction {self.faction}.")
        unit.set_parent_army(self)
        self.units.append(unit)
        return True

    # ---------- Command phase CP gain hooks ----------
    def get_command_phase_bonus_cp_gain(self) -> int:
        """
        Return bonus CP gained during the owning player's own Command phase due to abilities.

        This represents CP gained in addition to the normal Command phase CP and should be subject
        to the per-battle-round guardrail.

        Implementation note: this is intentionally conservative and data-driven via `unit.special_rules`
        so armies/characters can set it without hard-coding faction logic here.
        """
        bonus = 0
        for u in list(getattr(self, "units", []) or []):
            try:
                if not getattr(u, "deployed", False):
                    continue
                if not u.is_alive():
                    continue
                if getattr(u, "reserve_status", "deployed") != "deployed":
                    continue
                sr = getattr(u, "special_rules", {}) or {}
                # Accept either key spelling; keep it simple.
                b = int(sr.get("command_phase_bonus_cp", sr.get("command_phase_cp_bonus", 0)) or 0)
                if b > 0:
                    bonus += b
            except Exception:
                continue
        return int(bonus)
    
    def get_total_points(self) -> int:
        return sum(unit.get_unit_cost() for unit in self.units)

    # ----------------------------------------------------------------------
    # Reserves limits (Matched Play / Chapter Approved defaults)
    # ----------------------------------------------------------------------
    def _reserve_group_roots(self) -> List[Unit]:
        """
        Return the list of "deployment groups" for this army for reserves counting.

        Per 10e setup conventions:
        - Attached Leaders do NOT count as separate units (they are part of the Attached Unit).
        - Units that start embarked do NOT count as separate units (they are part of the Transport group).

        This means the unit-count denominator for reserves is smaller after attachments/embarkments.
        """
        roots: List[Unit] = []
        for u in list(getattr(self, "units", []) or []):
            if u is None:
                continue
            try:
                if bool(getattr(u, "is_attached_leader", False)):
                    continue
            except Exception:
                pass
            try:
                if bool(getattr(u, "is_embarked", False)) or getattr(u, "embarked_in", None) is not None:
                    continue
            except Exception:
                pass
            roots.append(u)
        return roots

    def _reserve_group_members(self, root: Unit) -> List[Unit]:
        """
        Return all units that should follow `root` for reserves status and points counting.

        Includes:
        - `root` itself
        - attached leaders (if any)
        - if root is a transport: its passengers + each passenger's attached leaders
        """
        members: List[Unit] = []
        seen: set[str] = set()

        def _add(u: Optional[Unit]) -> None:
            if u is None:
                return
            try:
                uid = str(getattr(u, "_id", None) or id(u))
            except Exception:
                uid = str(id(u))
            if uid in seen:
                return
            seen.add(uid)
            members.append(u)

        _add(root)
        # attached leaders
        try:
            for l in list(getattr(root, "attached_leaders", []) or []):
                _add(l)
        except Exception:
            pass

        # transport passengers + their attached leaders
        try:
            if bool(getattr(root, "is_transport", False)):
                for p in list(getattr(root, "transport_passengers", []) or []):
                    _add(p)
                    try:
                        for l in list(getattr(p, "attached_leaders", []) or []):
                            _add(l)
                    except Exception:
                        pass
        except Exception:
            pass

        return members

    def _reserve_group_points(self, root: Unit) -> int:
        total = 0
        for u in self._reserve_group_members(root):
            try:
                total += int(u.get_unit_cost())
            except Exception:
                total += 0
        return int(total)

    def get_reserve_limits(self) -> dict:
        """
        Calculate the reserve limits for this army.

        Defaults (Chapter Approved / Matched Play style):
        - **Total Reserves** (Strategic Reserves + other Reserves): <= 50% of points AND <= 50% of unit count
        - **Strategic Reserves**: <= 25% of battle size point limit (points only)

        Notes:
        - Points caps are based on the battle size points limit (typically 2000 for Strike Force), not
          on the army's current total points (which may be lower).
        - Unit-count caps are based on "deployment groups" after attachments/embarkments.
        """
        roots = self._reserve_group_roots()
        total_units = len(roots)

        battle_size_points = int(getattr(self, "points_limit", 2000) or 2000)
        total_army_points = int(self.get_total_points())

        # 50% unit cap (rounded down)
        max_reserve_units = total_units // 2
        # 50% points cap (rounded down) from battle size
        max_reserve_points = battle_size_points // 2
        # 25% Strategic Reserves points cap (rounded down) from battle size
        max_strategic_points = battle_size_points // 4

        return {
            "total_units": total_units,
            "max_units": max_reserve_units,
            "battle_size_points": battle_size_points,
            "total_army_points": total_army_points,
            "max_points": max_reserve_points,
            "max_strategic_points": max_strategic_points,
        }

    def can_add_unit_to_reserves(self, unit: Unit, current_reserve_units: int, current_reserve_points: int) -> bool:
        """
        Check if a unit can be added to reserves without exceeding limits.
        
        Args:
            unit: The unit to check
            current_reserve_units: Current number of units in reserves
            current_reserve_points: Current points in reserves
            
        Returns:
            bool: True if the unit can be added to reserves
        """
        limits = self.get_reserve_limits()
        # Treat `unit` as a reserve-group root for counting purposes.
        unit_points = self._reserve_group_points(unit)
        
        # Check both unit count and points limits
        can_add_units = current_reserve_units < limits['max_units']
        can_add_points = current_reserve_points + unit_points <= limits['max_points']
        
        return can_add_units and can_add_points

    def validate_reserves_decisions(self, reserves_decisions: dict) -> dict:
        """
        Validate reserves decisions against the 50% limits.
        
        Args:
            reserves_decisions: Dict mapping unit names to reserve status ('deploy', 'reserves', 'strategic_reserves')
            
        Returns:
            dict: Validation result with 'valid' boolean and 'errors' list
        """
        limits = self.get_reserve_limits()
        errors: List[str] = []

        reserve_units = 0
        reserve_points = 0
        strategic_points = 0

        roots = self._reserve_group_roots()
        for root in roots:
            rid = str(getattr(root, "_id", None) or "")
            decision = reserves_decisions.get(rid, reserves_decisions.get(getattr(root, "name", ""), "deploy"))
            if decision == "strategic_reserves":
                try:
                    if bool(getattr(root, "is_fortification", False)):
                        errors.append(f"FORTIFICATIONS cannot be placed in Strategic Reserves: {getattr(root, 'name', 'Unit')}")
                        continue
                except Exception:
                    pass
            if decision in ["reserves", "strategic_reserves"]:
                reserve_units += 1
                pts = self._reserve_group_points(root)
                reserve_points += pts
                if decision == "strategic_reserves":
                    strategic_points += pts

        if reserve_units > limits["max_units"]:
            errors.append(f"Too many units in reserves: {reserve_units}/{limits['max_units']} allowed")
        if reserve_points > limits["max_points"]:
            errors.append(f"Too many points in reserves: {reserve_points}/{limits['max_points']} allowed")
        if strategic_points > limits["max_strategic_points"]:
            errors.append(f"Too many points in Strategic Reserves: {strategic_points}/{limits['max_strategic_points']} allowed")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "reserve_units": reserve_units,
            "reserve_points": reserve_points,
            "strategic_points": strategic_points,
            "limits": limits,
        }

    def enforce_reserves_limits(self, reserves_decisions: dict) -> dict:
        """
        Enforce reserve limits by modifying decisions if necessary.
        This ensures the final reserves decisions comply with the 50% limits.
        
        Args:
            reserves_decisions: Dict mapping unit names to reserve status
            
        Returns:
            dict: Modified reserves decisions that comply with limits
        """
        limits = self.get_reserve_limits()
        modified = dict(reserves_decisions or {})

        roots = self._reserve_group_roots()

        def _root_key(u: Unit) -> str:
            return str(getattr(u, "_id", None) or getattr(u, "name", ""))

        # Normalize: ensure every root has an entry (default deploy)
        for r in roots:
            k = _root_key(r)
            if k not in modified and getattr(r, "name", "") not in modified:
                modified[k] = "deploy"

        # Hard rule: Fortifications cannot be Strategic Reserves.
        for r in roots:
            try:
                if not bool(getattr(r, "is_fortification", False)):
                    continue
            except Exception:
                continue
            k = _root_key(r)
            decision = modified.get(k, modified.get(getattr(r, "name", ""), "deploy"))
            if decision == "strategic_reserves":
                modified[k] = "deploy"

        # Enforce Strategic cap first: if strategic exceeds cap, try converting strategic->reserves if eligible, else deploy.
        # Deterministic order: highest-point strategic groups first.
        while True:
            status = self.validate_reserves_decisions(modified)
            if status["valid"]:
                break
            errs = status.get("errors", []) or []
            if any("Strategic Reserves" in e for e in errs):
                strategic_roots = []
                for r in roots:
                    k = _root_key(r)
                    decision = modified.get(k, modified.get(getattr(r, "name", ""), "deploy"))
                    if decision == "strategic_reserves":
                        strategic_roots.append(r)
                strategic_roots.sort(key=lambda u: self._reserve_group_points(u), reverse=True)
                if not strategic_roots:
                    break
                r = strategic_roots[0]
                k = _root_key(r)
                # Prefer keeping in (standard) reserves if unit can Deep Strike; else deploy it.
                try:
                    can_standard = bool(r.has_deep_strike())
                except Exception:
                    can_standard = False
                modified[k] = "reserves" if can_standard else "deploy"
                continue

            # Enforce overall reserves caps (units/points): convert the highest-point reserve group to deploy until valid.
            reserve_roots = []
            for r in roots:
                k = _root_key(r)
                decision = modified.get(k, modified.get(getattr(r, "name", ""), "deploy"))
                if decision in ("reserves", "strategic_reserves"):
                    reserve_roots.append(r)
            reserve_roots.sort(key=lambda u: self._reserve_group_points(u), reverse=True)
            if not reserve_roots:
                break
            r = reserve_roots[0]
            modified[_root_key(r)] = "deploy"

        # Final: ensure we do not exceed unit-count cap if still invalid (safety)
        while True:
            status = self.validate_reserves_decisions(modified)
            if status["valid"]:
                break
            reserve_roots = []
            for r in roots:
                k = _root_key(r)
                decision = modified.get(k, modified.get(getattr(r, "name", ""), "deploy"))
                if decision in ("reserves", "strategic_reserves"):
                    reserve_roots.append(r)
            if not reserve_roots:
                break
            # Drop arbitrary last
            modified[_root_key(reserve_roots[-1])] = "deploy"

        return modified

    def get_current_reserves_status(self, reserves_decisions: dict) -> dict:
        """
        Get current reserves status and limits information.
        
        Args:
            reserves_decisions: Dict mapping unit names to reserve status
            
        Returns:
            dict: Current reserves status and limits
        """
        limits = self.get_reserve_limits()
        reserve_units = 0
        reserve_points = 0
        strategic_points = 0
        reserve_unit_names: List[str] = []
        strategic_reserve_unit_names: List[str] = []

        roots = self._reserve_group_roots()
        for root in roots:
            rid = str(getattr(root, "_id", None) or "")
            decision = reserves_decisions.get(rid, reserves_decisions.get(getattr(root, "name", ""), "deploy"))
            if decision == "reserves":
                reserve_units += 1
                pts = self._reserve_group_points(root)
                reserve_points += pts
                reserve_unit_names.append(getattr(root, "name", "Unit"))
            elif decision == "strategic_reserves":
                reserve_units += 1
                pts = self._reserve_group_points(root)
                reserve_points += pts
                strategic_points += pts
                strategic_reserve_unit_names.append(getattr(root, "name", "Unit"))

        return {
            "reserve_units": reserve_units,
            "reserve_points": reserve_points,
            "strategic_points": strategic_points,
            "limits": limits,
            "reserve_unit_names": reserve_unit_names,
            "strategic_reserve_unit_names": strategic_reserve_unit_names,
            "can_add_more_units": reserve_units < limits["max_units"],
            "can_add_more_points": reserve_points < limits["max_points"],
            "can_add_more_strategic_points": strategic_points < limits["max_strategic_points"],
        }

    def add_enhancement(self, enhancement, character_unit):
        # Assign an Enhancement to a Character unit
        if not character_unit.is_character or character_unit.is_epic_hero:
            raise ArmyValidationError(f"Enhancements can only be assigned to non-Epic Hero Characters. '{character_unit.name}' is not eligible.")
        if character_unit.enhancement:
            raise ArmyValidationError(f"Character '{character_unit.name}' already has an Enhancement.")
        # Enhancements are detachment-specific in 10e; enforce faction and detachment match when available.
        try:
            if getattr(self, "faction_id", None) and getattr(enhancement, "faction_id", ""):
                if self.faction_id != enhancement.faction_id:
                    raise ArmyValidationError(
                        f"Enhancement '{enhancement.name}' belongs to faction {enhancement.faction_id}, "
                        f"but army faction is {self.faction_id}."
                    )
        except Exception:
            pass
        try:
            if getattr(self, "detachment_type", None) and getattr(enhancement, "detachment", ""):
                if self.detachment_type != enhancement.detachment:
                    raise ArmyValidationError(
                        f"Enhancement '{enhancement.name}' is for detachment '{enhancement.detachment}', "
                        f"but army detachment is '{self.detachment_type}'."
                    )
        except Exception:
            pass
        # We intentionally do NOT strictly enforce model eligibility text from Wahapedia, because it is
        # unstructured and would cause false rejections without a robust parser.
        character_unit.enhancement = enhancement
        try:
            if hasattr(enhancement, "apply_to_unit"):
                enhancement.apply_to_unit(character_unit)
        except Exception:
            pass
        self.enhancements.append(enhancement)

    def select_warlord(self, unit: Unit):
        if not unit.is_character:
            raise ArmyValidationError(f"Only Character units can be selected as Warlord. '{unit.name}' is not a Character.")
        if self.warlord:
            raise ArmyValidationError(f"Warlord has already been selected: '{self.warlord.name}'.")
        unit.is_warlord = True
        self.warlord = unit

    def validate_points_limit(self):
        total_points = self.get_total_points()
        if total_points > self.points_limit:
            raise ArmyValidationError(f"Army exceeds the points limit of {self.points_limit} points. Total points: {total_points}.")

    def validate_unit_limits(self):
        from collections import Counter

        datasheet_counts = Counter()
        battleline_counts = Counter()
        transport_counts = Counter()

        # Count units based on datasheets and keywords
        for unit in self.units:
            datasheet_counts[unit.name] += 1
            if unit.is_battleline:
                battleline_counts[unit.name] += 1
            if unit.is_dedicated_transport:
                transport_counts[unit.name] += 1

        # Validate datasheet limits
        for name, count in datasheet_counts.items():
            unit = next(u for u in self.units if u.name == name)
            if unit.is_battleline:
                if count > 6:
                    raise ArmyValidationError(f"Battleline unit '{name}' exceeds the limit of 6.")
            elif unit.is_dedicated_transport:
                # Dedicated Transports are validated separately
                continue
            else:
                if count > 3:
                    raise ArmyValidationError(f"Unit '{name}' exceeds the limit of 3.")

        # Validate Dedicated Transport limits
        infantry_units_count = sum(1 for unit in self.units if unit.is_infantry)
        allowed_transports = infantry_units_count
        total_transports = sum(1 for unit in self.units if unit.is_dedicated_transport)

        if total_transports > allowed_transports:
            raise ArmyValidationError(
                f"Too many Dedicated Transports. Allowed: {allowed_transports}, Found: {total_transports}."
            )

    def validate_epic_heroes(self):
        epic_heroes = [unit for unit in self.units if unit.is_epic_hero]
        epic_hero_names = [hero.name for hero in epic_heroes]
        if len(epic_hero_names) != len(set(epic_hero_names)):
            duplicates = [name for name in epic_hero_names if epic_hero_names.count(name) > 1]
            raise ArmyValidationError(f"Epic Hero(s) {duplicates} included more than once.")

    def validate_leaders(self):
        # Map of units to their attached Leaders
        unit_leader_map: dict = {}
        leader_units = [unit for unit in self.units if getattr(unit, "is_leader", False)]

        for leader in leader_units:
            attached_to = getattr(leader, "attached_to", None)
            # Leaders may be left unattached in 10e (optional), so only validate if set.
            if attached_to is None:
                continue
            if attached_to not in self.units:
                raise ArmyValidationError(f"Leader '{leader.name}' is attached to an invalid unit.")
            try:
                if hasattr(leader, "can_attach_to") and not leader.can_attach_to(attached_to):
                    raise ArmyValidationError(f"Leader '{leader.name}' cannot be attached to '{attached_to.name}'.")
            except ArmyValidationError:
                raise
            except Exception:
                # If validation can't be performed, fail fast with a clear error.
                raise ArmyValidationError(f"Failed validating leader attachment for '{leader.name}'.")

            unit_leader_map.setdefault(attached_to, []).append(leader)

        # Enforce per-bodyguard leader limits
        for bodyguard, leaders in unit_leader_map.items():
            try:
                max_leaders = bodyguard.max_attached_leaders()
            except Exception:
                max_leaders = 1
            if len(leaders) > max_leaders:
                raise ArmyValidationError(
                    f"Unit '{bodyguard.name}' has {len(leaders)} Leaders attached (max {max_leaders})."
                )

    def validate_enhancements(self):
        # Rule 1: Maximum of 3 Enhancements
        if len(self.enhancements) > 3:
            raise ArmyValidationError(f"Army has more than 3 Enhancements assigned.")

        # Rule 2: Enhancements cannot be duplicated
        enhancement_names = [enhancement.name for enhancement in self.enhancements]
        if len(enhancement_names) != len(set(enhancement_names)):
            duplicates = [name for name in enhancement_names if enhancement_names.count(name) > 1]
            raise ArmyValidationError(f"Enhancements {duplicates} are assigned more than once.")

        # Rule 3: Enhancements can only be assigned to non-Epic Hero Characters
        for unit in self.units:
            if unit.enhancement:
                if unit.is_epic_hero:
                    raise ArmyValidationError(f"Epic Hero '{unit.name}' cannot have Enhancements assigned.")

    def validate_warlord(self):
        # Ensure exactly one Warlord is selected
        warlord_units = [unit for unit in self.units if unit.is_warlord]
        if len(warlord_units) != 1:
            raise ArmyValidationError(f"Army must have exactly one Warlord. Found: {len(warlord_units)}.")

        # SUPREME COMMANDER (keyword): if your army includes any SUPREME COMMANDER units,
        # one of them must be your Warlord.
        supreme_commanders = [unit for unit in self.units if unit.is_supreme_commander]
        if supreme_commanders:
            supreme_warlords = [unit for unit in supreme_commanders if unit.is_warlord]
            if not supreme_warlords:
                raise ArmyValidationError(
                    "An army that includes any SUPREME COMMANDER units must have one of them as the Warlord."
                )

    def validate_detachment_rules(self):
        # Army-rule / detachment-specific validation
        try:
            det = (getattr(self, "detachment_type", "") or "").strip()
            faction_id = (getattr(self, "faction_id", "") or "").strip().upper()
            if not det or not faction_id:
                return
            for pact in pact_restrictions_for_faction(faction_id):
                if self._detachment_matches_pact(det, pact.get("forbidden", "")):
                    raise ArmyValidationError(
                        f"{pact.get('name', 'Pact')}: armies cannot select '{pact.get('forbidden', '').strip()}' as their Army Faction."
                    )
        except ArmyValidationError:
            raise
        except Exception:
            # Fail fast with a clear error if detachment validation can't be evaluated.
            raise ArmyValidationError("Failed validating detachment/army rule restrictions.")

    def _detachment_matches_pact(self, detachment: str, forbidden: str) -> bool:
        def _norm(text: str) -> str:
            import re
            t = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower())
            return re.sub(r"\s+", " ", t).strip()

        det = _norm(detachment)
        forb = _norm(forbidden)
        if not det or not forb:
            return False
        if det == forb:
            return True
        if det.endswith("s") and det[:-1] == forb:
            return True
        if forb.endswith("s") and forb[:-1] == det:
            return True
        if det in forb or forb in det:
            return True
        return False

    def validate_allies(self):
        # Disparate Paths: allow Harlequins/Ynnari alongside the army faction.
        if not army_has_ability_id(self, ABILITY_DISPARATE_PATHS):
            self._validate_daemonic_pact()
            return

        allowed = set()
        try:
            allowed.update(
                str(k).strip().upper()
                for k in (getattr(self, "faction_keyword", []) or [])
                if str(k).strip()
            )
        except Exception:
            allowed = set()

        if not allowed:
            fid = str(getattr(self, "faction_id", "") or "").strip().upper()
            if fid == "AE":
                allowed.update({"AELDARI", "ASURYANI"})
            elif fid == "DRU":
                allowed.add("DRUKHARI")

        allowed.update({"HARLEQUINS", "YNNARI"})
        for u in list(getattr(self, "units", []) or []):
            try:
                fks = [str(k).strip().upper() for k in (getattr(u, "faction_keywords", []) or []) if str(k).strip()]
            except Exception:
                fks = []
            if not fks:
                continue
            if not any(k in allowed for k in fks):
                raise ArmyValidationError(
                    f"Unit '{getattr(u, 'name', 'Unknown')}' has faction keywords {fks}, "
                    "which are not allowed for an army with Disparate Paths (allows base faction + HARLEQUINS/YNNARI)."
                )
        self._validate_daemonic_pact()

    def _daemonic_pact_points_cap(self) -> int:
        try:
            limit = int(self.points_limit or 0)
        except Exception:
            limit = 0
        if limit <= 0:
            return 0
        if limit <= 1000:
            return 250
        if limit <= 2000:
            return 500
        return 750

    def _is_legiones_daemonica_unit(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return unit.has_any_keyword("LEGIONES DAEMONICA")
        except Exception:
            return False

    def _validate_daemonic_pact(self) -> None:
        """
        Chaos Daemons army rule (Daemonic Pact):
        - Allowed only in Chaos Knights or Heretic Astartes armies.
        - Daemon allies are limited by points cap based on battle size.
        - Daemon allies cannot be Warlord or have Enhancements.
        - For each god keyword, non-Battleline daemon allies cannot exceed Battleline daemon allies.
        """
        daemon_units = [u for u in list(getattr(self, "units", []) or []) if self._is_legiones_daemonica_unit(u)]
        if not daemon_units:
            return

        faction_id = str(getattr(self, "faction_id", "") or "").strip().upper()
        if faction_id == "CD":
            return
        if faction_id not in {"CSM", "QT"}:
            raise ArmyValidationError("Daemonic Pact: LEGIONES DAEMONICA units are only allowed in Chaos Knights or Heretic Astartes armies.")

        base_keyword = "CHAOS KNIGHTS" if faction_id == "QT" else "HERETIC ASTARTES"
        for unit in list(getattr(self, "units", []) or []):
            if unit in daemon_units:
                continue
            try:
                if not unit.has_any_keyword(base_keyword):
                    raise ArmyValidationError(
                        f"Daemonic Pact: all non-daemon units must have the {base_keyword} keyword to include daemon allies."
                    )
            except ArmyValidationError:
                raise
            except Exception:
                raise ArmyValidationError("Daemonic Pact: failed to validate base-faction keyword requirements.")

        for unit in daemon_units:
            if getattr(unit, "is_warlord", False):
                raise ArmyValidationError(
                    f"Daemonic Pact: daemon unit '{getattr(unit, 'name', 'Unknown')}' cannot be your Warlord."
                )
            if getattr(unit, "enhancement", None) is not None:
                raise ArmyValidationError(
                    f"Daemonic Pact: daemon unit '{getattr(unit, 'name', 'Unknown')}' cannot take Enhancements."
                )

        cap = self._daemonic_pact_points_cap()
        total = 0
        for unit in daemon_units:
            try:
                total += int(unit.get_unit_cost())
            except Exception:
                continue
        if cap <= 0 or total > cap:
            raise ArmyValidationError(
                f"Daemonic Pact: daemon allies total {total} points (cap {cap})."
            )

        god_keywords = ("KHORNE", "TZEENTCH", "NURGLE", "SLAANESH")
        for god in god_keywords:
            with_god = []
            for unit in daemon_units:
                try:
                    if unit.has_any_keyword(god):
                        with_god.append(unit)
                except Exception:
                    continue
            if not with_god:
                continue
            battleline = sum(1 for u in with_god if getattr(u, "is_battleline", False))
            non_battleline = len(with_god) - battleline
            if non_battleline > battleline:
                raise ArmyValidationError(
                    f"Daemonic Pact: {god} daemon allies include {non_battleline} non-BATTLELINE unit(s) "
                    f"but only {battleline} BATTLELINE unit(s)."
                )

    def validate(self) -> None:
        self.validate_points_limit()
        self.validate_unit_limits()
        self.validate_epic_heroes()
        self.validate_leaders()
        self.validate_enhancements()
        self.validate_warlord()
        self.validate_detachment_rules()
        self.validate_allies()
        print("Army is valid and ready for battle!")

    def get_active_units(self) -> List[Unit]:
        return [unit for unit in self.units if unit.deployed and unit.is_alive()]

    def __str__(self):
        return f"Army: {self.faction} - {self.detachment_type}\n{self.units}"

    def __eq__(self, other):
        return self._id == other._id

    def __hash__(self):
        return hash(self._id)

    def set_player(self, player) -> None:
        """Set the player that owns this army."""
        self.player = player

    def on_battle_round_start(self, battle_round: int) -> None:
        """Army-level start-of-battle-round hook for faction rules/state resets."""
        mgr = getattr(self, "blessings_of_khorne", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round))
        mgr = getattr(self, "battle_focus", None)
        if mgr is not None:
            try:
                game = getattr(getattr(self, "player", None), "game", None)
            except Exception:
                game = None
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "templar_vows", None)
        if mgr is not None:
            try:
                game = getattr(getattr(self, "player", None), "game", None)
            except Exception:
                game = None
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "shadow_form", None)
        if mgr is not None:
            try:
                game = getattr(getattr(self, "player", None), "game", None)
            except Exception:
                game = None
            mgr.on_battle_round_start(int(battle_round), game=game)

    def schedule_reborn_in_blood(self, *, game) -> bool:
        """
        WORLD EATERS: Angron - Reborn in Blood.

        Engine model:
        - Immediately 'revive' Angron (restore model with 8 wounds) but set him up as being in Reserves.
        - The human player can then place him using the existing Reserves arrival UI flow (Deep Strike).

        Returns True if Angron was found and scheduled, else False.
        """
        # Find the Angron unit (by ability text presence)
        target = None
        for u in list(getattr(self, "units", []) or []):
            try:
                found, _ = u._find_ability_with_patterns(["reborn in blood"])
            except Exception:
                found = False
            if found:
                target = u
                break
        if target is None:
            return False

        # If already alive/on battlefield, do nothing.
        try:
            if target.is_alive():
                return False
        except Exception:
            pass

        # Re-add the last removed model if needed (single-model unit likely has models_lost populated).
        if len(getattr(target, "models", []) or []) == 0:
            try:
                lost = list(getattr(target, "models_lost", []) or [])
            except Exception:
                lost = []
            if not lost:
                return False
            m = lost[-1]
            try:
                target.models.append(m)
                m.set_parent_unit(target)
            except Exception:
                return False

        # Restore to 8 wounds remaining
        try:
            m = target.models[0]
            setattr(m, "_wounds", 8)
        except Exception:
            try:
                target.models[0].wounds = 8
            except Exception:
                return False

        # Put into standard reserves so it can arrive via Deep Strike rules.
        try:
            target.reserve_status = "reserves"
            target.deployed = True
            target.reserve_turn_deployed = None
            target.arrived_from_reserves_this_turn = False
            setattr(target, "_reborn_in_blood_pending", True)
        except Exception:
            pass

        # Ensure not on the map until placed
        try:
            if game is not None and hasattr(game, "map") and hasattr(game.map, "units"):
                if target in game.map.units:
                    game.map.units.remove(target)
        except Exception:
            pass

        return True

# Helper function to parse an army list from a text file
def parse_army_list(file_path: str, waha_helper: WahaHelper) -> Army:
    with codecs.open(file_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
        
        # Remove BOM if present
        if lines and lines[0].startswith('\ufeff'):
            lines[0] = lines[0][1:]

    import re

    def _find_points_limit(raw_lines: list[str]) -> int:
        for ln in raw_lines:
            m = re.search(r"\(([\d,]+)\s*points?\)", ln, flags=re.IGNORECASE)
            if m:
                return int(m.group(1).replace(",", ""))
        raise ValueError(f"Could not find points limit in army list header: {file_path!r}")

    def _is_app_export(raw_lines: list[str]) -> bool:
        # Be tolerant to minor formatting differences.
        return any("exported with app version" in (ln or "").lower() for ln in raw_lines)

    def _first_section_index(stripped_lines: list[str]) -> int:
        headers = {"CHARACTER", "CHARACTERS", "BATTLELINE", "OTHER DATASHEETS"}
        for i, ln in enumerate(stripped_lines):
            if (ln or "").strip().upper() in headers:
                return i
        # Fallback to 0; the unit-parse loop will skip empty lines and unknown headers,
        # but without a recognized section header the file likely isn't in a supported format.
        return 0

    stripped = [ln.strip() for ln in lines]
    is_app_format = _is_app_export(lines)
    points_limit = _find_points_limit(lines)

    # Extract faction + detachment more robustly than fixed line numbers because app exports vary.
    if is_app_format:
        # In app exports, the faction is typically the first non-empty line after the title line,
        # and the detachment is the next non-empty line that is NOT the game size line (e.g., Strike Force...).
        faction_keyword = ""
        detachment_type = ""
        for ln in stripped[1:]:
            if not ln:
                continue
            if ln.lower().startswith("exported with"):
                break
            # Skip the game size line if it appears early.
            if "strike force" in ln.lower():
                continue
            if not faction_keyword:
                faction_keyword = ln
                continue
            if not detachment_type:
                detachment_type = ln
                break
        if not faction_keyword:
            raise ValueError(f"Could not determine faction from app-export header: {file_path!r}")
        if not detachment_type:
            # Some files omit detachment; keep a safe placeholder.
            detachment_type = "Unknown Detachment"
    else:
        # Legacy/simple text format: "Army Name – Faction" then "Strike Force (...)" then detachment line.
        try:
            faction_keyword = (stripped[0].split(' – ')[-1]).strip()
        except Exception:
            faction_keyword = (stripped[0] or "").strip()
        detachment_type = (stripped[2] or "").strip() if len(stripped) > 2 else "Unknown Detachment"

    # Start parsing units at the first section header we recognize (more robust than fixed offsets).
    start_index = _first_section_index(stripped)

    print(f"Parsing army: {faction_keyword} - {detachment_type} ({points_limit} points)")

    # Create the Army object
    army = Army(faction=faction_keyword, detachment_type=detachment_type, points_limit=points_limit)
    
    # Map faction names to faction IDs for datasheet lookup
    faction_id = get_faction_id_from_name(faction_keyword)
    if faction_id:
        print(f"Using faction ID: {faction_id} for datasheet lookups")
        army.faction_id = faction_id
    else:
        print(f"Warning: Could not determine faction ID for '{faction_keyword}', using generic lookup")

    current_unit = None
    current_model_count = 0
    current_model_name = None
    current_wargear = {}
    current_enhancement = None
    is_warlord = False

    for line in lines[start_index:]:
        line = line.strip()
        if not line:
            continue

        if line.upper() in ['CHARACTER', 'CHARACTERS', 'BATTLELINE', 'OTHER DATASHEETS']:
            continue

        if line.startswith('Exported with'):
            break

        if not line.startswith('•') and not line.startswith('◦'):
            if current_unit:
                add_unit_to_army(army, current_unit, current_model_count, current_wargear, current_enhancement, waha_helper, is_warlord)
                current_unit = None
                current_model_name = None
                current_model_count = 0
                current_wargear = {}
                current_enhancement = None
                is_warlord = False

            unit_info = line.split(' (')
            unit_name = unit_info[0].strip()
            
            # Use faction-specific datasheet lookup if faction_id is available
            if faction_id:
                datasheet = waha_helper.get_full_datasheet_info_by_name(unit_name, faction_id=faction_id)
                if not datasheet:
                    # Fallback to generic lookup if faction-specific lookup fails
                    print(f"Warning: Faction-specific datasheet not found for {unit_name} (faction: {faction_id}), trying generic lookup")
                    datasheet = waha_helper.get_full_datasheet_info_by_name(unit_name)
            else:
                datasheet = waha_helper.get_full_datasheet_info_by_name(unit_name)
            
            if datasheet:
                current_unit = Unit(datasheet)
            else:
                print(f"Warning: Datasheet not found for {unit_name}")

        elif line.startswith('•') or line.startswith('◦'):
            data = line[1:].strip()
            if data.lower() == 'warlord':
                is_warlord = True
            elif data.lower().startswith('enhancement'):
                enhancement_name = data.split(':', 1)[1].strip()
                current_enhancement = waha_helper.get_enhancement_by_name(enhancement_name)
                if not current_enhancement:
                    print(f"Warning: Enhancement not found for {enhancement_name}")
            elif data.startswith('Daemonic Allegiance:'):
                allegiance = data.split(':', 1)[1].strip()
                current_unit.daemonic_allegiance = allegiance
            else:
                # This could be either a model count or wargear
                if 'x ' in data:
                    quantity, item_name = data.split('x ', 1)
                    quantity = int(quantity)
                else:
                    quantity = 1
                    item_name = data

                # Check if it's a model count or wargear
                if current_unit and any(item_name.strip() in model_name.rstrip('s') for model_name in current_unit.unit_composition.keys()):
                    current_model_count += quantity
                    current_model_name = item_name.strip()
                    current_wargear[current_model_name] = set()
                else:
                    if current_model_name:
                        current_wargear.setdefault(current_model_name, set()).add((item_name.strip(), quantity))
                    else:
                        current_wargear.setdefault(current_unit.name, set()).add((item_name.strip(), quantity))

    # Don't forget to add the last unit if there is one
    if current_unit:
        add_unit_to_army(army, current_unit, current_model_count, current_wargear, current_enhancement, waha_helper, is_warlord)

    print(f"Finished parsing. Total units: {len(army.units)}")
    return army

def add_unit_to_army(army: Army, unit: Unit, model_count: int, wargear_dict: Dict[str, Set[Tuple[str, int]]], enhancement: Enhancement, waha_helper: WahaHelper, is_warlord: bool):
    # Configure the unit with the correct number of models
    unit.configure_models(model_count, [])

    # Add wargear to the unit
    for model_name, wargear_list in wargear_dict.items():
        for wargear_name, quantity in wargear_list:
            gear_name = wargear_name.lower().replace("’","'")
            matching_gear = next((gear for gear in unit.possible_wargear if gear.name.lower().replace("’","'") == gear_name), None)
            if matching_gear:
                # Add the wargear multiple times based on quantity
                # Distribute wargear among models instead of adding multiple to each
                target_models = []
                if model_name and model_name != unit.name:
                    target_models = [model for model in unit.models if model.name.lower() == model_name.lower()]
                else:
                    target_models = unit.models

                if target_models:
                    if quantity == len(target_models):
                        # 1 item per model
                        for model in target_models:
                            model.wargear.append(matching_gear)
                    elif quantity < len(target_models):
                        # Fewer items than models - give to first N models
                        for i in range(quantity):
                            target_models[i].wargear.append(matching_gear)
                    else:
                        # More items than models - distribute evenly
                        items_per_model = quantity // len(target_models)
                        remainder = quantity % len(target_models)
                        for i, model in enumerate(target_models):
                            for _ in range(items_per_model):
                                model.wargear.append(matching_gear)
                            if i < remainder:
                                model.wargear.append(matching_gear)
                else:
                    # Fallback to old behavior if no target models found
                    for _ in range(quantity):
                        unit.add_wargear([matching_gear if gear.name.lower().replace("’","'") == gear_name else None for gear in unit.possible_wargear], model_name)
            else:
                matching_gear = next((gear for gear in unit.wargear_options if gear_name in gear.wargear_to), None)
                if matching_gear:
                    # Army lists must be deterministic: if an option can't be resolved uniquely, that's an error.
                    unit.apply_wargear_options_strict(gear_name)
                else:
                    matching_ability = next((ability for ability in unit.possible_abilities if ability.name.lower().replace("’","'") == gear_name and ability.type == 'Wargear'), None)
                    if matching_ability:
                        unit.add_ability(matching_ability, model_name)
                    else:
                        print(f"Warning: {gear_name} not found in {unit.name}'s possible wargear or abilities.")
                        for gear in unit.possible_wargear:
                            print(f"  - {gear.name}")
                        for ability in unit.possible_abilities:
                            print(f"  - {ability.name} (Ability Wargear)")

    # Validate final wargear loadout for models in this unit (critical for army-list parsing correctness)
    unit.validate_wargear_selection()

    # Add enhancement to the unit if it exists
    if enhancement:
        try:
            army.add_enhancement(enhancement, unit)
        except Exception as e:
            print(f"Warning: Could not add enhancement {enhancement.name} to {unit.name}: {str(e)}")

    # Add the unit to the army
    army.add_unit(unit)

    # Set warlord if applicable
    if is_warlord:
        army.select_warlord(unit)


# Example usage:
if __name__ == "__main__":
    waha_helper = WahaHelper()
    army = parse_army_list("army_lists/warhammer_app_dump.txt", waha_helper)
    print(f"Parsed army: {army.faction_keyword} - {army.detachment_type}")
    print(f"Total points: {army.get_total_points()} out of {army.points_limit}")
    print(f"Number of units: {len(army.units)}")
    for unit in army.units:
        print(f"- {unit.name} ({unit.get_unit_cost()} points)")
        for model in unit.models:
            print(f"  - {model.name} {'(Warlord)' if unit.is_warlord else ''}")
            for wargear in model.wargear:
                if wargear:
                    print(f"    - {wargear.name}")
            if hasattr(model, 'optional_wargear'):
                for wargear_option in model.optional_wargear:
                    print(f"    - {model.get_optional_wargear_by_name(wargear_option).name}")
            for ability in model.abilities.keys():
                if ability:
                    print(f"    - {ability} (Ability Wargear)")
            if unit.enhancement:
                print(f"    - Enhancement: {unit.enhancement.name}")
    army.validate()
