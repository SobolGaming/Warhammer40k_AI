import logging
from typing import List, Tuple, Optional, Callable
from typing import TYPE_CHECKING
from .model import Model
from ..utility.model_base import Base, BaseType
from .wargear import Wargear, WargearOption, parse_option_string, parse_alternate_3
from .ability import Ability
from ..utility.range import Range
from ..utility.calcs import (
    get_dist,
    get_angle,
    convert_mm_to_inches,
    build_spatial_index,
    footprint_from_offsets,
    build_formation_templates,
    query_spatial_index,
    measure_path_distance,
    measure_direct_distance,
    movement_segment_cost,
)
from ..utility.dice import get_roll, DiceCollection
from ..utility.attack_roll_parser import AttackRollCondition, AttackRollRule, parse_attack_roll_text
from .status_effects import StatusEffect, BattleShockEffect
from ..utility.entity_ids import get_entity_id
import uuid
import copy
import re
import html
import numpy as np
import math
from enum import Enum, auto
from shapely.affinity import translate
from ..utility.dice import DiceCollection

# Forward declarations
if TYPE_CHECKING:
    from .map import Map
    from .army import Army
    from .game import Game

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


class UnitRoundState:
    remained_stationary_this_round: bool = True  # Units are stationary by default until they move
    advanced_this_round: bool = False
    shot_this_round: bool = False
    fell_back_this_round: bool = False
    reinforced_this_round: bool = False
    attempted_charge_this_round: bool = False  # Track if unit attempted a charge (prevents multiple attempts)
    charged_this_round: bool = False  # Track if unit successfully made a charge move (charge bonus may be suppressed)
    charge_bonus_suppressed_turn: Optional[int] = None
    charge_bonus_suppressed_turn_owner: Optional[str] = None
    moved_this_round: bool = False  # Track if unit has moved during movement phase
    num_lost_models_this_round: int = 0
    advance_roll: int = None  # Store advance roll for the round
    # Transport / Embark / Disembark tracking
    embarked_this_round: bool = False
    disembarked_this_round: bool = False
    disembarked_from_moved_transport: bool = False  # Counts as Normal move, cannot move further this turn
    disembarked_from_destroyed_transport: bool = False  # Counts as Normal move; typically cannot charge
    disembarked_cannot_charge: bool = False  # Explicit "cannot charge" override after disembark
    # Mission actions
    performing_action_name: Optional[str] = None
    action_started_turn: Optional[int] = None
    action_completes_turn: Optional[int] = None
    action_locked_until_turn_end: bool = False  # Cannot shoot or declare charge while true (except titanic character rule handled at call site)
    fought_this_phase: bool = False  # Used by timing-sensitive rules (e.g., Total Carnage)
    engaged_enemies_at_turn_start: Optional[set] = None  # Track engaged enemy unit ids at start of controlling player's turn
    charge_target_ids: Optional[set] = None  # Track declared charge target unit ids


class MovementAction(Enum):
    REMAIN_STATIONARY = auto()
    MOVE = auto()
    ADVANCE = auto()
    FALL_BACK = auto()
    CHARGE = auto()


class MovementState(Enum):
    IN_ENGAGEMENT_RANGE = auto()
    OUT_OF_ENGAGEMENT_RANGE = auto()


class Unit:
    def __init__(self, datasheet, quantity=None, enhancement=None):
        self._id = str(uuid.uuid4())
        self._datasheet = datasheet
        self.name = datasheet.name
        self.faction = datasheet.faction_data["name"]
        self.keywords = getattr(datasheet, 'keywords', [])  # Use getattr with a default value
        self.faction_keywords = getattr(datasheet, 'faction_keywords', [])  # Use getattr with a default value
        try:
            self.unit_composition = self._parse_unit_composition(datasheet.datasheets_unit_composition)
        except Exception as e:
            print(f"{self.name} - NEED TO HANDLE - ERROR PARSING UNIT COMPOSITION: {e}")
            self.unit_composition = {}
            return
        try:
            self.models_cost = self._parse_models_cost(datasheet.datasheets_models_cost)
        except Exception as e:
            #print(f"{self.name} - NEED TO HANDLE - ERROR PARSING MODELS COST: {e}")
            self.models_cost = { "spawn_on_death": 0 }
        self.models = self._create_models(datasheet, quantity)

        # Wargear Stuff
        self.possible_wargear = self._parse_wargear(datasheet)
        self.wargear_options = []
        self._parse_wargear_options(datasheet) # this needs to here, sets above variable
        self.possible_abilities = self._parse_abilities(datasheet)
        self.add_wargear()

        # Attachments
        self.can_be_attached_to = getattr(datasheet, 'attached_to', [])
        self.can_be_attached_to_names = getattr(datasheet, 'attached_to_names', [])
        # For Bodyguard units: track Leaders attached to this unit (in 10e, this forms an Attached Unit).
        # We keep the Leader units as real units for combat/abilities, but UI + movement can treat the group as one.
        self.attached_leaders: List['Unit'] = []

        if hasattr(datasheet, 'damaged_w') and datasheet.damaged_w:
            self.damaged_profile = self._parse_range(datasheet.damaged_w)
            self.damaged_profile_desc = getattr(datasheet, 'damaged_description', None)
        else:
            self.damaged_profile = None
            self.damaged_profile_desc = None
        # Track active degraded-profile modifiers so we can remove them on healing.
        self._damaged_profile_active: bool = False
        self._damaged_profile_stat_deltas: dict[str, int] = {}

        self.attached_to = None  # For Leaders, to track which unit they are attached to
        self.enhancement = enhancement  # The Enhancement assigned to this unit (if any)
        self.is_warlord = False
        self.parent_army = None
        self.spawned_in_battle = False  # Spawn-only units should not be mustered.
        self.daemonic_allegiance = "UNSET"

        # Game State specific attributes
        self.models_lost = []
        self.status_effects = []  # List of active status effects
        self.special_rules = {}  # Dictionary of special rules
        self.stats = {}  # Dictionary of stats modifiers
        self.deployed = False

        # Unified Core Rules modifier pipeline (10e)
        # Map: characteristic_key -> list[Modifier]
        self._characteristic_modifiers = {}

        # Reserves tracking
        self.reserve_status = 'deployed'  # 'deployed', 'reserves', 'strategic_reserves'
        self.reserve_turn_deployed = None  # Turn when unit arrived from reserves
        self.arrived_from_reserves_this_turn = False  # Flag for movement/charge restrictions
        # Hover mode (AIRCRAFT core ability)
        self.hover_mode = False
        self.hover_declared = False

        # Transport / embark state
        self.transport_rules_text: str = str(getattr(datasheet, "transport", "") or "")
        self.transport_capacity: int = self._parse_transport_capacity(datasheet)
        self.transport_required_keywords, self.transport_excluded_keywords = self._parse_transport_restrictions(datasheet)
        self.transport_passengers: List['Unit'] = []
        self.embarked_in: Optional['Unit'] = None  # The transport unit this unit is embarked within (if any)

        # Initialize round-tracked variables
        self.initialize_round()

        self.position = None  # Initialize position as None
        self.update_coherency()  # Sets coherency_distance and required_neighbors
        
        # Track starting strength for Battle-Shock tests
        self.starting_model_count = len(self.models)
        self.starting_total_wounds = sum(model._base_wounds for model in self.models)
        
        # Ability cache for performance optimization
        self._ability_cache = {}
        # Aspect Shrine Token tracking (Aeldari wargear ability)
        self._aspect_shrine_tokens_total = 0
        self._aspect_shrine_tokens_used = 0
        self._aspect_shrine_prompt_suppressed = False

        # Parse a small subset of defensive "against attacks with X characteristic of Y" rules into special_rules.
        # (AP/Damage-based ones are applied at Allocate Attack time in the attack sequence.)
        try:
            self._parse_against_attack_characteristic_defensive_rules()
        except Exception:
            # Defensive: never block unit construction due to unsupported/unknown text patterns.
            pass
        # Parse unit-level mustering restrictions encoded on datasheet abilities.
        try:
            self._parse_warlord_enhancement_restrictions()
        except Exception:
            # Defensive: never block unit construction due to unsupported/unknown text patterns.
            pass
        # Parse spawn-only units that are created by other rules instead of mustering.
        try:
            self._parse_spawn_only_restrictions()
        except Exception:
            # Defensive: never block unit construction due to unsupported/unknown text patterns.
            pass
        # Parse command-phase CP gains and sticky objective flags.
        try:
            self._refresh_command_phase_flags()
        except Exception:
            pass
        # Parse enemy Fall Back Desperate Escape triggers.
        try:
            self._refresh_fall_back_desperate_escape_flags()
        except Exception:
            pass
        # Parse once-per-battle-round stratagem CP discounts for targeted units.
        try:
            self._refresh_targeted_stratagem_cp_discount_flags()
        except Exception:
            pass
        # Parse "first time destroyed" return-to-battlefield abilities.
        try:
            self._refresh_return_on_death_flags()
        except Exception:
            pass
        # Parse charge-end mortal wound triggers.
        try:
            self._refresh_charge_end_mortal_wounds_flags()
        except Exception:
            pass
        # Parse fight-within-3" eligibility abilities.
        try:
            self._refresh_fight_within_3_flags()
        except Exception:
            pass
        # Parse common bearer-unit effects (charge bonuses, Leadership set).
        try:
            self._refresh_bearer_unit_common_modifiers()
        except Exception:
            # Defensive: never block unit construction due to unsupported/unknown text patterns.
            pass
        # Parse bearer-only keyword additions (e.g., SMOKE).
        try:
            self._refresh_bearer_keyword_flags()
        except Exception:
            pass
        # Parse move-over friendly MONSTER/VEHICLE + low-terrain traversal rules.
        try:
            self._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass

    def _add_stat_additive(self, key: str, delta: int) -> None:
        """Apply an additive stat delta, tracking it for later removal (damaged profiles)."""
        from ..utility.modifiers import Modifier, ModifierOp

        self.add_characteristic_modifier(key, Modifier(ModifierOp.ADD, int(delta), source="damaged_profile"))
        self._damaged_profile_stat_deltas[key] = int(self._damaged_profile_stat_deltas.get(key, 0)) + int(delta)

    def _clear_damaged_profile_effects(self) -> None:
        """Remove previously-applied degraded profile modifiers (best-effort)."""
        # Remove stat deltas by source tag.
        try:
            self.remove_characteristic_modifiers_by_source("damaged_profile")
        except Exception:
            pass
        self._damaged_profile_stat_deltas = {}

        # Remove non-stat effects
        try:
            if getattr(self, "special_rules", None) is None:
                self.special_rules = {}
            for k in (
                "damaged_hit_roll_modifier",
                "damaged_half_attacks",
                "damaged_melee_attacks_bonus",
                "damaged_attacks_bonus_weapon_name",
                "damaged_attacks_bonus_weapon_amount",
                "relics_of_matriarchs_max_choices",
            ):
                if k in self.special_rules:
                    del self.special_rules[k]
        except Exception:
            pass
        self._damaged_profile_active = False

    def add_characteristic_modifier(self, characteristic: str, modifier) -> None:
        """
        Register a Core Rules modifier for a characteristic.
        `characteristic` keys are simple strings (e.g. "movement", "objective_control").
        """
        if not characteristic:
            return
        if getattr(self, "_characteristic_modifiers", None) is None:
            self._characteristic_modifiers = {}
        key = str(characteristic).strip().lower()
        self._characteristic_modifiers.setdefault(key, []).append(modifier)

    def remove_characteristic_modifiers_by_source(self, source_prefix: str) -> None:
        if getattr(self, "_characteristic_modifiers", None) is None:
            return
        p = str(source_prefix or "")
        if not p:
            return
        for k, mods in list(self._characteristic_modifiers.items()):
            kept = []
            for m in (mods or []):
                try:
                    if str(getattr(m, "source", "") or "").startswith(p):
                        continue
                except Exception:
                    pass
                kept.append(m)
            self._characteristic_modifiers[k] = kept

    def get_effective_model_characteristic(self, model: Model, characteristic: str, *, game_map=None) -> int:
        """
        Centralized characteristic resolution that follows Core Rules modifier ordering.

        This is intentionally conservative: it only applies engine-registered modifiers plus a small
        subset of strict text-based effects (e.g. OC while leading, OC-halving in engagement range).
        """
        from ..utility.modifiers import (
            Modifier,
            ModifierOp,
            apply_characteristic_caps,
            apply_numeric_modifiers,
        )

        c = str(characteristic or "").strip().lower()
        base_val = None
        base_raw = None

        if c in ("movement", "move", "m"):
            base_val = int(getattr(model, "_movement", getattr(model, "movement", 0)))
            base_raw = getattr(model, "_movement_raw", None)
            ckey = "movement"
        elif c in ("toughness", "t"):
            base_val = int(getattr(model, "_toughness", getattr(model, "toughness", 0)))
            base_raw = getattr(model, "_toughness_raw", None)
            ckey = "toughness"
        elif c in ("save", "sv"):
            base_val = int(getattr(model, "_save", getattr(model, "save", 0)))
            base_raw = getattr(model, "_save_raw", None)
            ckey = "save"
        elif c in ("leadership", "ld"):
            base_val = int(getattr(model, "_leadership", getattr(model, "leadership", 0)))
            base_raw = getattr(model, "_leadership_raw", None)
            ckey = "leadership"
        elif c in ("objective_control", "oc"):
            base_val = int(getattr(model, "_objective_control", getattr(model, "objective_control", 0)))
            base_raw = getattr(model, "_objective_control_raw", None)
            ckey = "objective_control"
        else:
            # Unknown characteristic: best-effort passthrough.
            try:
                return int(getattr(model, c))
            except Exception:
                return 0

        mods = []
        # Engine-registered modifiers (from enhancements, damaged profiles, status effects, etc.)
        try:
            mods.extend(list((self._characteristic_modifiers or {}).get(ckey, []) or []))
        except Exception:
            pass

        # OC: strict "leading" bonus (e.g. Astartes Banner) from attached leaders.
        if ckey == "objective_control":
            try:
                leaders = list(getattr(self, "attached_leaders", []) or [])
            except Exception:
                leaders = []
            for leader in leaders:
                try:
                    for ab in (getattr(leader, "possible_abilities", []) or []):
                        desc = str(getattr(ab, "description", "") or "").replace("\u2019", "'")
                        if desc and ("leading a unit" in desc.lower()) and ("objective control characteristic" in desc.lower()):
                            import re
                            if re.search(r"add\s+1\s+to\s+the\s+objective\s+control\s+characteristic", desc, flags=re.IGNORECASE):
                                mods.append(Modifier(ModifierOp.ADD, 1, source="ability:leading_oc_add_1"))
                except Exception:
                    continue

            # OC: strict enemy engagement-range halving (e.g. Chitinous Horrors).
            try:
                if game_map is None:
                    army = self.get_parent_army()
                    game = getattr(getattr(army, "player", None), "game", None)
                    game_map = getattr(game, "map", None) if game is not None else None
            except Exception:
                game_map = None
            if game_map is not None:
                try:
                    from ..utility.aura_effects import get_enemy_engagement_oc_divisors
                    for reason in get_enemy_engagement_oc_divisors(self, game_map=game_map):
                        mods.append(Modifier(ModifierOp.DIV, 2, source=reason))
                except Exception:
                    pass

            # Friendly OC auras (ADD) \u2013 applied as an ADD modifier so DIV happens first.
            try:
                from ..utility.aura_effects import get_aura_objective_control_bonus
                bonus = int(get_aura_objective_control_bonus(self, game_map=game_map) or 0)
                if bonus:
                    mods.append(Modifier(ModifierOp.ADD, bonus, source="aura:objective_control_add"))
            except Exception:
                pass

        afflicted_plague = None
        try:
            from ..rules.nurgles_gift import (
                NurglesGiftManager,
                PLAGUE_RATTLEJOINT,
                PLAGUE_SCABROUS,
            )
            afflicted_plague = NurglesGiftManager.get_afflicted_plague_for_unit(self, game_map=game_map)
        except Exception:
            afflicted_plague = None

        scabrous_oc_floor = False
        if afflicted_plague is not None:
            if ckey == "save" and afflicted_plague.key == PLAGUE_RATTLEJOINT.key:
                mods.append(Modifier(ModifierOp.ADD, 1, source="nurgles_gift:rattlejoint_ague"))
            elif ckey == "movement" and afflicted_plague.key == PLAGUE_SCABROUS.key:
                mods.append(Modifier(ModifierOp.ADD, -1, source="nurgles_gift:scabrous_soulrot"))
            elif ckey == "leadership" and afflicted_plague.key == PLAGUE_SCABROUS.key:
                mods.append(Modifier(ModifierOp.ADD, 1, source="nurgles_gift:scabrous_soulrot"))
            elif ckey == "objective_control" and afflicted_plague.key == PLAGUE_SCABROUS.key:
                mods.append(Modifier(ModifierOp.ADD, -1, source="nurgles_gift:scabrous_soulrot"))
                scabrous_oc_floor = True

        if ckey == "leadership":
            if game_map is None:
                try:
                    army = self.get_parent_army()
                    game = getattr(getattr(army, "player", None), "game", None)
                    game_map = getattr(game, "map", None) if game is not None else None
                except Exception:
                    game_map = None
            if game_map is not None:
                try:
                    from ..rules.harbingers_of_dread import HarbingersOfDreadManager, DEATHLY_TERROR, DESPAIR
                    active = HarbingersOfDreadManager.leadership_auras_for_unit(self, game_map=game_map)
                    if DEATHLY_TERROR.key in active:
                        mods.append(Modifier(ModifierOp.ADD, 1, source="harbingers_of_dread:deathly_terror"))
                    if DESPAIR.key in active:
                        mods.append(Modifier(ModifierOp.ADD, 1, source="harbingers_of_dread:despair"))
                except Exception:
                    pass

        # Emperor's Children: Internal Rivalries (Slaanesh's Chosen) - ignore negative Move modifiers.
        try:
            if ckey == "movement":
                army = self.get_parent_army()
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is not None and getattr(mgr, "internal_rivalries_applies", lambda _u: False)(self):
                    kept = []
                    ignored = []
                    for m in list(mods or []):
                        try:
                            val = int(getattr(m, "value", 0) or 0)
                        except Exception:
                            val = 0
                        try:
                            op = getattr(m, "op", None)
                        except Exception:
                            op = None
                        negative = False
                        if op == ModifierOp.ADD and val < 0:
                            negative = True
                        elif op == ModifierOp.SUB and val > 0:
                            negative = True
                        elif op == ModifierOp.MUL and val < 1:
                            negative = True
                        elif op == ModifierOp.DIV and val > 1:
                            negative = True
                        if negative:
                            ignored.append(m)
                        else:
                            kept.append(m)
                    if ignored:
                        mods = kept
                        try:
                            sr = getattr(self, "special_rules", None)
                            if not isinstance(sr, dict):
                                sr = {}
                            ignored_sources = tuple(sorted(str(getattr(m, "source", "") or "") for m in ignored))
                            kept_sources = tuple(sorted(str(getattr(m, "source", "") or "") for m in kept))
                            sig = (ignored_sources, kept_sources)
                            if sr.get("internal_rivalries_move_mod_signature") != sig:
                                sr["internal_rivalries_move_mod_signature"] = sig
                                self.special_rules = sr
                                from ..utility.event_bus import append_action
                                pn = self.get_parent_army().player
                                ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                                msg = f"Internal Rivalries: ignored negative Move modifiers ({ignored_text})."
                                append_action(pn, msg)
                                if kept_sources:
                                    kept_text = ", ".join(s for s in kept_sources if s)
                                    if kept_text:
                                        append_action(pn, f"Internal Rivalries: applied Move modifiers ({kept_text}).")
                        except Exception:
                            pass
        except Exception:
            pass

        # World Eaters: Driven by Ultimate Rage (Aura) - ignore negative Move modifiers.
        try:
            if ckey == "movement":
                from ..rules.wrathful_presence import driven_by_ultimate_rage_applies
                if driven_by_ultimate_rage_applies(self, game_map=game_map):
                    kept = []
                    ignored = []
                    for m in list(mods or []):
                        try:
                            val = int(getattr(m, "value", 0) or 0)
                        except Exception:
                            val = 0
                        try:
                            op = getattr(m, "op", None)
                        except Exception:
                            op = None
                        negative = False
                        if op == ModifierOp.ADD and val < 0:
                            negative = True
                        elif op == ModifierOp.SUB and val > 0:
                            negative = True
                        elif op == ModifierOp.MUL and val < 1:
                            negative = True
                        elif op == ModifierOp.DIV and val > 1:
                            negative = True
                        if negative:
                            ignored.append(m)
                        else:
                            kept.append(m)
                    if ignored:
                        mods = kept
                        try:
                            sr = getattr(self, "special_rules", None)
                            if not isinstance(sr, dict):
                                sr = {}
                            ignored_sources = tuple(sorted(str(getattr(m, "source", "") or "") for m in ignored))
                            kept_sources = tuple(sorted(str(getattr(m, "source", "") or "") for m in kept))
                            sig = (ignored_sources, kept_sources)
                            if sr.get("driven_by_ultimate_rage_move_mod_signature") != sig:
                                sr["driven_by_ultimate_rage_move_mod_signature"] = sig
                                self.special_rules = sr
                                from ..utility.event_bus import append_action
                                pn = self.get_parent_army().player
                                ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                                msg = f"Driven by Ultimate Rage: ignored negative Move modifiers ({ignored_text})."
                                append_action(pn, msg)
                                if kept_sources:
                                    kept_text = ", ".join(s for s in kept_sources if s)
                                    if kept_text:
                                        append_action(pn, f"Driven by Ultimate Rage: applied Move modifiers ({kept_text}).")
                        except Exception:
                            pass
        except Exception:
            pass

        # Apply core ordering + rounding.
        interim, dbg = apply_numeric_modifiers(int(base_val), mods, base_raw=base_raw)

        # Damage 0 exception handled at weapon level, not model level.
        final = apply_characteristic_caps(ckey, interim, base_raw=base_raw)
        if scabrous_oc_floor and int(base_val) > 0 and final < 1:
            final = 1
        if ckey == "save":
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict) and sr.get("voice_of_command_take_cover_cap"):
                    try:
                        base_save = int(base_val)
                    except Exception:
                        base_save = None
                    if base_save is not None and base_save <= 3:
                        # Do not improve saves already 3+ or better.
                        final = max(int(final), base_save)
                    else:
                        final = max(int(final), 3)
            except Exception:
                pass
        return int(final)

    def _apply_damaged_profile_effects(self, profile_text: str) -> None:
        """
        Apply a *small* subset of common damaged-profile effects from Wahapedia text.

        Supported patterns (10e):
        - "subtract N from the Hit roll" -> -N to hit (capped later with other modifiers)
        - "subtract N from ... Objective Control characteristic" -> OC -N
        - "subtract N\" from ... Move characteristic" / "subtract N from ... Move characteristic" -> Move -N
        - "halve the Attacks characteristic of ... weapons" -> halve attacks (round up)
        - "add N to the Attacks characteristic of this model's melee weapons" -> +N attacks for melee weapons
        - "add N to the Attacks characteristic of this model's <weapon name>" -> +N attacks for that weapon only
        - "the Attacks characteristics of all of its weapons are halved" -> halve attacks (round up)
        - "only select one ability when using its Relics of the Matriarchs ability" -> set a limiter flag (future hook)

        Everything else is currently informational only.
        """
        import re

        # Start from a clean slate to avoid double-stacking across multiple checks.
        self._clear_damaged_profile_effects()

        t = (profile_text or "").replace("\u2019", "'")
        t = re.sub(r"\s+", " ", t).strip()
        tl = t.lower()

        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}

        # -N to hit
        m = re.search(r"subtract\s+(\d+)\s+from\s+the\s+hit\s+roll", tl)
        if m:
            try:
                self.special_rules["damaged_hit_roll_modifier"] = -int(m.group(1))
            except Exception:
                pass

        # OC penalty (this model's / its / this unit's)
        m = re.search(r"subtract\s+(\d+)\s+from\s+(?:this\s+(?:model|unit)'?s|its)\s+objective\s+control\s+characteristic", tl)
        if m:
            try:
                self._add_stat_additive("objective_control", -int(m.group(1)))
            except Exception:
                pass

        # Move penalty (with or without inch mark)
        m = re.search(r"subtract\s+(\d+)\s*(?:\"|inches)?\s+from\s+(?:this\s+model'?s|its)\s+move\s+characteristic", tl)
        if m:
            try:
                self._add_stat_additive("movement", -int(m.group(1)))
            except Exception:
                pass

        # Halve attacks characteristic of weapons
        if ("halve the attacks characteristic" in tl and "weapon" in tl) or ("attacks characteristics of all of its weapons are halved" in tl):
            self.special_rules["damaged_half_attacks"] = True

        # Add N to Attacks characteristic (melee weapons)
        m = re.search(r"add\s+(\d+)\s+to\s+the\s+attacks\s+characteristic\s+of\s+this\s+model'?s\s+melee\s+weapons", tl)
        if m:
            try:
                self.special_rules["damaged_melee_attacks_bonus"] = int(m.group(1))
            except Exception:
                pass

        # Add N to Attacks characteristic of a specific named weapon ("this model's Slaughter and Carnage")
        m = re.search(r"add\s+(\d+)\s+to\s+the\s+attacks\s+characteristic\s+of\s+this\s+model'?s\s+([a-z0-9 \-']+)", tl)
        if m and "melee weapons" not in tl:
            try:
                amt = int(m.group(1))
                wname = m.group(2).strip().rstrip(".")
                # Avoid capturing generic "weapons"
                if wname and wname not in ("weapons", "weapon"):
                    self.special_rules["damaged_attacks_bonus_weapon_name"] = wname
                    self.special_rules["damaged_attacks_bonus_weapon_amount"] = amt
            except Exception:
                pass

        # Triumph of Saint Katherine: relic-selection limiter (future hook)
        if "relics of the matriarchs" in tl and "only select one ability" in tl:
            self.special_rules["relics_of_matriarchs_max_choices"] = 1

        self._damaged_profile_active = True

    def _parse_against_attack_characteristic_defensive_rules(self) -> None:
        """
        Parse a very small subset of defensive rules that key off an incoming attack's characteristics.

        Core timing note (10e): if the characteristic involved is AP or Damage, such rules are applied at
        the Allocate Attack step. Our attack sequence allocates a target model before resolving saves,
        so these parsed effects are evaluated during saving throw resolution (per-allocated-model).

        Currently supported patterns (strict):
        - "Each time an attack with a Damage characteristic of 1 is allocated to a model in this unit,
           add 1 to any armour saving throw made against that attack"

        Effects are stored in `unit.special_rules` for the save step to consult.
        """
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        try:
            if "armor_save_bonus_vs_damage_characteristic" in self.special_rules:
                del self.special_rules["armor_save_bonus_vs_damage_characteristic"]
        except Exception:
            pass
        try:
            if "allocated_damage_reductions" in self.special_rules:
                del self.special_rules["allocated_damage_reductions"]
        except Exception:
            pass

        # Collect all rules text from unit abilities.
        entries = []
        for a in self._iter_active_possible_abilities():
            if isinstance(a, str):
                entries.append(("", a))
            else:
                name = str(getattr(a, "name", "") or "")
                desc = str(getattr(a, "description", "") or "")
                entries.append((name, desc or name))

        for name, raw in entries:
            t = self._normalize_rules_text(raw)
            if not t:
                continue
            tl = t.lower()

            # Save bonus vs allocated attacks with Damage characteristic of N.
            # Example: "Each time an attack with a Damage characteristic of 1 is allocated to a model in this unit,
            # add 1 to any armour saving throw made against that attack"
            m = re.search(
                r"each\s+time\s+an\s+attack\s+with\s+a\s+damage\s+characteristic\s+of\s+(\d+)\s+is\s+allocated\s+to\s+a\s+model\s+in\s+this\s+unit,\s+add\s+(\d+)\s+to\s+any\s+armou?r\s+saving\s+throw\s+made\s+against\s+that\s+attack",
                tl,
                flags=re.IGNORECASE,
            )
            if m:
                dmg = int(m.group(1))
                bonus = int(m.group(2))
                spec = self.special_rules.get("armor_save_bonus_vs_damage_characteristic")
                if not isinstance(spec, dict):
                    spec = {}
                spec[int(dmg)] = int(spec.get(int(dmg), 0)) + int(bonus)
                self.special_rules["armor_save_bonus_vs_damage_characteristic"] = spec

            # Damage reduction when attacks are allocated to this model/unit.
            m = re.search(
                r"each\s+time\s+(?:an|a)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+is\s+allocated\s+to\s+"
                r"(?:this\s+model|a\s+model\s+in\s+this\s+unit)\s*,\s*"
                r"subtract\s+(?P<val>\d+)\s+from\s+the\s+damage\s+characteristic\s+of\s+that\s+attack",
                tl,
                flags=re.IGNORECASE,
            )
            if m:
                try:
                    val = int(m.group("val"))
                except Exception:
                    val = 0
                if val:
                    atype = (m.group("atype") or "any").strip().lower()
                    label = (name or "Damage reduction ability").strip() or "Damage reduction ability"
                    sr = self.special_rules
                    items = list(sr.get("allocated_damage_reductions", []) or [])
                    items.append(
                        {
                            "value": int(val),
                            "attack_type": atype,
                            "source": label,
                            "op": "sub",
                        }
                    )
                    sr["allocated_damage_reductions"] = items
                    self.special_rules = sr

            # Damage halving when attacks are allocated to this model/unit.
            m = re.search(
                r"each\s+time\s+(?:an|a)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+is\s+allocated\s+to\s+"
                r"(?:this\s+model|a\s+model\s+in\s+this\s+unit)\s*,\s*"
                r"(?:halve|half)\s+the\s+damage\s+characteristic\s+of\s+that\s+attack",
                tl,
                flags=re.IGNORECASE,
            )
            if not m:
                m = re.search(
                    r"each\s+time\s+(?:an|a)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+is\s+allocated\s+to\s+"
                    r"(?:this\s+model|a\s+model\s+in\s+this\s+unit).*?"
                    r"damage\s+characteristic\s+of\s+that\s+attack\s+is\s+halved",
                    tl,
                    flags=re.IGNORECASE,
                )
            if m:
                atype = (m.group("atype") or "any").strip().lower()
                label = (name or "Damage halving ability").strip() or "Damage halving ability"
                sr = self.special_rules
                items = list(sr.get("allocated_damage_reductions", []) or [])
                items.append(
                    {
                        "value": 2,
                        "attack_type": atype,
                        "source": label,
                        "op": "div",
                    }
                )
                sr["allocated_damage_reductions"] = items
                self.special_rules = sr

    _CANNOT_BE_WARLORD_RE = re.compile(r"\bcannot be your\s+warlord\b", re.IGNORECASE)
    _CANNOT_BE_GIVEN_ENHANCEMENTS_RE = re.compile(r"\bcannot be given\s+(?:an?\s+)?enhancements?\b", re.IGNORECASE)
    _BEARER_UNIT_CHARGE_BONUS_RE = re.compile(
        r"add\s+(\d+)\s+to\s+charge\s+rolls?\s+made\s+for\s+(?:the\s+bearer'?s\s+unit|this\s+unit|this\s+model'?s\s+unit)",
        re.IGNORECASE,
    )
    _BEARER_UNIT_ADVANCE_BONUS_RE = re.compile(
        r"add\s+(\d+)\s+to\s+advance\s+rolls?\s+made\s+for\s+the\s+bearer'?s\s+unit",
        re.IGNORECASE,
    )
    _BEARER_UNIT_ADVANCE_AND_CHARGE_BONUS_RE = re.compile(
        r"add\s+(\d+)\s+to\s+advance\s+and\s+charge\s+rolls?\s+made\s+for\s+the\s+bearer'?s\s+unit",
        re.IGNORECASE,
    )
    _ENEMY_FALLBACK_DESPERATE_ESCAPE_RE = re.compile(
        r"each\s+time\s+an?\s+enemy\s+unit.*?within\s+engagement\s+range.*?falls?\s+back.*?desperate\s+escape",
        re.IGNORECASE,
    )
    _ENEMY_FALLBACK_DESPERATE_ESCAPE_EXCLUDE_RE = re.compile(
        r"excluding\s+monsters?\s+and\s+vehicles?",
        re.IGNORECASE,
    )
    _ENEMY_FALLBACK_DESPERATE_ESCAPE_BS_PENALTY_RE = re.compile(
        r"battle[-\s]?shocked.*?subtract\s+(\d+)\s+from\s+each\s+of\s+those\s+desperate\s+escape\s+tests",
        re.IGNORECASE,
    )
    _BEARER_UNIT_LEADERSHIP_SET_RE = re.compile(
        r"models\s+in\s+the\s+bearer'?s\s+unit\s+have\s+a\s+leadership\s+characteristic\s+of\s+(\d+)\+?",
        re.IGNORECASE,
    )
    _BEARER_UNIT_MOVEMENT_SET_RE = re.compile(
        r"models\s+in\s+the\s+bearer'?s\s+unit\s+have\s+a\s+move\s+characteristic\s+of\s+(\d+)",
        re.IGNORECASE,
    )
    _BEARER_UNIT_OC_BONUS_RE = re.compile(
        r"add\s+(\d+)\s+to\s+the\s+objective\s+control\s+characteristic\s+of\s+(?:models\s+in\s+)?the\s+bearer'?s\s+unit",
        re.IGNORECASE,
    )
    _UNIT_CONTAINS_OC_BONUS_RE = re.compile(
        r"while\s+this\s+unit\s+contains\s+an?\s+(?P<model>.+?),\s*add\s+(?P<amt>\d+)\s+to\s+the\s+objective\s+control\s+"
        r"characteristic\s+of\s+models\s+in\s+this\s+unit",
        re.IGNORECASE,
    )
    _BEARER_UNIT_FNP_RE = re.compile(
        r"(?:models\s+in\s+)?the\s+bearer'?s\s+unit.*?\bfeel\s+no\s+pain\b\s*([1-6])\+",
        re.IGNORECASE,
    )
    _BEARER_UNIT_INVULNERABLE_SAVE_RE = re.compile(
        r"models\s+in\s+the\s+bearer'?s\s+unit\s+have\s+(?:a|the)?\s*([1-6])\+?\s*invulnerable\s+save",
        re.IGNORECASE,
    )
    _BEARER_UNIT_SUSTAINED_HITS_RE = re.compile(
        r"(?:weapons?\s+equipped\s+by\s+models\s+in|models\s+in)\s+the\s+bearer'?s\s+unit.*?\bsustained\s+hits\b\s*(\d+)",
        re.IGNORECASE,
    )
    _BEARER_UNIT_IGNORES_COVER_RE = re.compile(
        r"(?:weapons?\s+equipped\s+by\s+models\s+in|attacks?\s+made\s+by\s+models\s+in)\s+the\s+bearer'?s\s+unit.*?\bignores\s+cover\b",
        re.IGNORECASE,
    )
    _BEARER_UNIT_TARGET_HIT_PENALTY_RE = re.compile(
        r"each\s+time\s+(?:a|an)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+targets\s+the\s+bearer'?s\s+unit,\s+subtract\s+1\s+from\s+the\s+hit\s+roll",
        re.IGNORECASE,
    )
    _BEARER_UNIT_DEEP_STRIKE_RE = re.compile(
        r"models\s+in\s+(?:the\s+bearer'?s|that)\s+unit\s+have\s+the\s+deep\s+strike\s+ability",
        re.IGNORECASE,
    )
    _BEARER_UNIT_PHASE_MOVE_RE = re.compile(
        r"each\s+time\s+a\s+model\s+in\s+(?:the\s+bearer'?s|that)\s+unit\s+makes\s+a\s+.*?\bmove\b.*?move\s+horizontally\s+through\s+models\s+and\s+terrain\s+features",
        re.IGNORECASE,
    )
    _BEARER_UNIT_PHASE_TERRAIN_ONLY_RE = re.compile(
        r"each\s+time\s+a\s+model\s+in\s+(?:the\s+bearer'?s|that)\s+unit\s+makes\s+a\s+.*?\bmove\b.*?move\s+horizontally\s+through\s+terrain\s+features",
        re.IGNORECASE,
    )
    _BEARER_UNIT_PHASE_ENGAGEMENT_RE = re.compile(
        r"models\s+in\s+(?:the\s+bearer'?s|that)\s+unit\s+can\s+move\s+within\s+engagement\s+range\s+of\s+enemy\s+models.*?"
        r"cannot\s+end\s+that\s+move\s+within\s+engagement\s+range\s+of\s+them",
        re.IGNORECASE,
    )
    _BEARER_SMOKE_KEYWORD_TOKENS = "bearer has the smoke keyword"
    _COMMAND_PHASE_BONUS_CP_RE = re.compile(
        r"(?:at\s+the\s+)?start\s+of\s+(?:each\s+of\s+)?your\s+command\s+phase[s]?\b.*?\bgain\s+(\d+)\s*(?:cp|command point(?:s)?)",
        re.IGNORECASE,
    )
    _COMMAND_PHASE_REGAIN_WOUND_RE = re.compile(
        r"(?:at\s+the\s+)?start\s+of\s+(?:each\s+of\s+)?your\s+command\s+phase[s]?[,.]?\s*this\s+model\s+regains?\s+(\d+)\s+lost\s+wounds?",
        re.IGNORECASE,
    )
    _OPPONENT_TURN_STRATEGIC_RESERVES_RE = re.compile(
        r"at the end of your opponents turn if this unit is not within engagement range of one or more enemy units? "
        r"you can remove it from the battlefield and place it into strategic reserves?",
        re.IGNORECASE,
    )
    _TRANSPORT_REACTIVE_DISEMBARK_RE = re.compile(
        r"in your opponents movement phase each time an enemy unit is set up(?: on the battlefield)? or ends (?:a )?normal "
        r"advance or fall back move within (\d+) of this (?:model|unit) any units embarked within it can disembark",
        re.IGNORECASE,
    )
    _ENEMY_MOVE_REACTIVE_D6_RE = re.compile(
        r"once\s+per\s+turn,?\s+when\s+an\s+enemy\s+unit\s+ends\s+a\s+normal(?:,)?\s+advance\s+or\s+fall\s+back\s+move\s+"
        r"within\s+(?P<range>\d+)\s*\"?\s+of\s+this\s+(?:model(?: s)? unit|unit|model)"
        r"(?:\s+if\s+this\s+unit\s+is\s+not\s+within\s+engagement\s+range\s+of\s+(?:one\s+or\s+more|any)\s+enemy\s+units?)?"
        r".*?make\s+a\s+normal\s+move\s+of\s+up\s+to\s+(?P<move>d6|\d+)",
        re.IGNORECASE,
    )
    _SETUP_REACTIVE_SHOOT_CHARGE_RE = re.compile(
        r"at\s+the\s+end\s+of\s+your\s+opponent'?s?\s+movement\s+phase.*?"
        r"select\s+one\s+enemy\s+unit\s+that\s+was\s+set\s+up\s+on\s+the\s+battlefield\s+within\s+(?P<range>\d+).*?"
        r"(?:this\s+model|this\s+unit)\s+can\s+then\s+either.*?"
        r"shoot\s+at\s+that\s+unit.*?eligible\s+target.*?"
        r"declare\s+a\s+charge\s+against\s+that\s+unit.*?does\s+not\s+receive\s+any\s+charge\s+bonus",
        re.IGNORECASE,
    )
    _REROLL_ADVANCE_CHARGE_RE = re.compile(
        r"re-?roll\s+advance\s+and\s+charge\s+rolls?\s+made\s+for\s+(?:this\s+model|the\s+bearer'?s\s+unit|that\s+unit)",
        re.IGNORECASE,
    )
    _REROLL_CHARGE_BEARER_UNIT_RE = re.compile(
        r"re-?roll\s+charge\s+rolls?\s+made\s+for\s+(?:this\s+model|the\s+bearer'?s\s+unit|that\s+unit)",
        re.IGNORECASE,
    )
    _REROLL_CHARGE_CLOSEST_ELIGIBLE_RE = re.compile(
        r"each\s+time\s+this\s+unit\s+declares\s+a\s+charge\s+that\s+targets?\s+the\s+closest\s+(?:eligible\s+)?enemy\s+unit.*?re-?roll\s+the\s+charge\s+roll",
        re.IGNORECASE,
    )
    _REROLL_CHARGE_SETUP_TURN_RE = re.compile(
        r"re-?roll\s+charge\s+rolls?\s+made\s+for\s+(?:the\s+bearer'?s\s+unit|that\s+unit).*?\bset\s+up\s+on\s+the\s+battlefield\b",
        re.IGNORECASE,
    )
    _REROLL_CHARGE_OBJECTIVE_RE = re.compile(
        r"bearer'?s\s+unit\s+declares\s+a\s+charge.*?targets?\s+of\s+that\s+charge.*?within\s+range\s+of\s+an?\s+objective\s+marker.*?re-?roll\s+the\s+charge\s+roll",
        re.IGNORECASE,
    )
    _CHARGE_ROLL_TARGET_STRENGTH_BONUS_RE = re.compile(
        r"each\s+time\s+this\s+(?:model|unit)\s+declares\s+a\s+charge\s+that\s+targets?\s+one\s+or\s+more\s+units?\s+(?:that\s+are\s+)?"
        r"below\s+starting\s+strength\s+add\s+(?P<base>\d+)\s+to\s+the\s+charge\s+roll\s+if\s+one\s+or\s+more\s+of\s+"
        r"the\s+targets?\s+of\s+that\s+charge\s+are\s+below\s+half\s+strength\s+add\s+(?P<half>\d+)\s+to\s+the\s+charge\s+roll\s+instead",
        re.IGNORECASE,
    )
    _TARGETED_STRATAGEM_CP_DISCOUNT_RE = re.compile(
        r"once\s+per\s+battle\s+round\s+one\s+(?:unit|model)\s+from\s+your\s+army\s+with\s+this\s+ability\s+can\s+use\s+it\s+when\s+"
        r"(?:its\s+unit|this\s+models\s+unit|that\s+models\s+unit)\s+is\s+targeted\s+with\s+a\s+stratagem\s+"
        r"(?:if\s+it\s+does\s+)?reduce\s+the\s+cp\s+cost\s+of\s+that\s+(?:use|usage)\s+of\s+that\s+stratagem\s+by\s+1\s*cp",
        re.IGNORECASE,
    )
    _TARGETED_STRATAGEM_CP_DISCOUNT_AURA_RE = re.compile(
        r"once\s+per\s+battle\s+round\s+one\s+(?:unit|model)\s+from\s+your\s+army\s+with\s+this\s+ability\s+can\s+use\s+it\s+when\s+a\s+friendly\s+"
        r"(?P<keyword>[a-z0-9 ]+?)\s+unit\s+within\s+(?P<range>\d+)\s+of\s+(?:that|this)\s+model\s+is\s+targeted\s+with\s+a\s+stratagem\s+"
        r"(?:if\s+it\s+does\s+)?reduce\s+the\s+cp\s+cost\s+of\s+that\s+(?:use|usage)\s+of\s+that\s+stratagem\s+by\s+1\s*cp",
        re.IGNORECASE,
    )
    _TARGETED_STRATAGEM_CP_DISCOUNT_AURA_ALT_RE = re.compile(
        r"once\s+per\s+battle\s+round\s+when\s+a\s+friendly\s+(?P<keyword>[a-z0-9 ]+?)\s+unit\s+within\s+(?P<range>\d+)\s+of\s+this\s+model\s+"
        r"is\s+targeted\s+with\s+a\s+stratagem\s+this\s+model\s+can\s+use\s+this\s+ability\s+(?:if\s+it\s+does\s+)?"
        r"reduce\s+the\s+cp\s+cost\s+of\s+that\s+(?:use|usage)\s+of\s+that\s+stratagem\s+by\s+1\s*cp",
        re.IGNORECASE,
    )
    _TARGETED_STRATAGEM_CP_DISCOUNT_AURA_ALT2_RE = re.compile(
        r"once\s+per\s+battle\s+round\s+one\s+friendly\s+(?P<keyword>[a-z0-9 ]+?)\s+unit\s+within\s+(?P<range>\d+)\s+of\s+this\s+model\s+"
        r"can\s+be\s+targeted\s+with\s+a\s+stratagem\s+(?:if\s+it\s+does\s+)?reduce\s+the\s+cp\s+cost\s+of\s+that\s+(?:use|usage)\s+"
        r"of\s+that\s+stratagem\s+by\s+1\s*cp",
        re.IGNORECASE,
    )
    _POST_SHOOT_BATTLESHOCK_RE = re.compile(
        r"in your shooting phase after this model has shot select one enemy (?:(?P<infantry>infantry) )?unit "
        r"(?:that was )?hit by one or more of those attacks that unit must take a battle shock test",
        re.IGNORECASE,
    )
    _POST_SHOOT_SUPPRESSION_RE = re.compile(
        r"in your shooting phase after this model has shot select one enemy unit hit by one or more of those attacks "
        r"(?:(?P<exclude>excluding monsters and vehicles) )?until the start of your next turn that enemy unit is suppressed "
        r"while a unit is suppressed each time a model in that unit makes an attack subtract 1 from the hit roll",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_ENGAGEMENT_BATTLESHOCK_RE = re.compile(
        r"at the start of the fight phase each enemy unit within engagement range of this model must take a battle shock test "
        r"subtracting 1 from that test if that enemy unit is below half strength",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_END_ENGAGEMENT_MORTAL_EIGHT_D6_RE = re.compile(
        r"at the end of the fight phase you can select one enemy unit within engagement range of this model "
        r"and roll (?:eight|8) d6 for each 4 that enemy unit suffers 1 mortal wounds?",
        re.IGNORECASE,
    )
    _MOVE_OVER_MORTAL_WOUNDS_RE = re.compile(
        r"each time (?:this model|the bearer) ends a (?P<moves>[a-z ]+) move "
        r"(?:you can )?(?:select|choose) one enemy unit(?: excluding monsters and vehicles)? "
        r"(?:that )?(?:it )?moved over during that move "
        r"(?:and |then )?roll (?P<dice>\d+|one|two|three|four|five|six|seven|eight|nine|ten) d6 "
        r"for each (?P<threshold>\d)\+ that (?:enemy )?unit suffers (?P<mw>\d+) mortal wounds?",
        re.IGNORECASE,
    )
    _CHARGE_PHASE_BODYGUARD_LOSS_RE = re.compile(
        r"at the end of your charge phase if this model is leading a unit and that unit is not within "
        r"engagement range of (?:one or more|any) enemy units? you must take a leadership test for this model "
        r"if that test is failed one bodyguard model in that unit is destroyed",
        re.IGNORECASE,
    )
    _PHASE_END_LEADERSHIP_CP_GAIN_RE = re.compile(
        r"at the end of your shooting phase or the fight phase if "
        r"(?:the bearers unit|the bearer s unit|this unit|this models unit|this model s unit) destroyed one or more enemy units? that phase "
        r"(?:the bearers unit|the bearer s unit|this unit|this models unit|this model s unit) takes a leadership test "
        r"if that test is passed you gain (?P<cp>\d+|one) ?(?:cp|command points?)",
        re.IGNORECASE,
    )
    _RETURN_ON_DEATH_RE = re.compile(
        r"the first time (?:this model|the bearer) is destroyed(?: remove it from play without resolving its deadly demise ability)?(?: then)? "
        r"(?:at the end of the phase roll one d6|roll one d6 at the end of the phase) on a (?P<roll>\d+) "
        r"set (?:this model|the bearer) back up on the battlefield(?: as close as possible to where it was destroyed)? "
        r"and not within engagement range of (?:one or more|any) enemy (?:units|models) with "
        r"(?P<wounds>its full wounds remaining|(?:d3|d6|\d+) wounds? remaining)",
        re.IGNORECASE,
    )
    _FIGHT_WITHIN_3_RE = re.compile(
        r"selected\s+to\s+fight.*?eligible\s+to\s+fight.*?within\s+3\"?.*?engagement\s+range",
        re.IGNORECASE,
    )
    _CHARGE_END_MORTAL_PER_MODEL_RE = re.compile(
        r"each\s+time\s+(?:this\s+model'?s\s+unit|this\s+unit)\s+ends?\s+a\s+charge\s+move.*?"
        r"(?:select|choose)\s+one\s+enemy\s+unit\s+within\s+engagement\s+range.*?"
        r"roll\s+one\s+d6\s+for\s+each\s+model\s+in\s+(?:this\s+unit|that\s+unit|this\s+model'?s\s+unit).*?"
        r"for\s+each\s+4\+.*?d3\s+mortal\s+wounds?",
        re.IGNORECASE,
    )
    _CHARGE_MOVE_DEVASTATING_WOUNDS_RE = re.compile(
        r"each\s+time\s+this\s+(?:model|unit|model'?s\s+unit)\s+makes?\s+a\s+charge\s+move.*?"
        r"until\s+the\s+end\s+of\s+(?:the\s+)?turn.*?"
        r"melee\s+weapons.*?devastating\s+wounds",
        re.IGNORECASE,
    )
    _CHARGE_END_MORTAL_TABLE_RE = re.compile(
        r"each\s+time\s+(?:this\s+model'?s\s+unit|this\s+unit)\s+ends?\s+a\s+charge\s+move.*?"
        r"(?:select|choose)\s+one\s+enemy\s+unit\s+within\s+engagement\s+range.*?"
        r"roll\s+one\s+d6.*?on\s+a\s+2\s*-\s*3.*?mortal\s+wound.*?"
        r"on\s+a\s+4\s*-\s*5.*?d3\s+mortal\s+wounds?.*?"
        r"on\s+a\s+6.*?d3\s*\+\s*3\s+mortal\s+wounds?",
        re.IGNORECASE,
    )
    _DAEMONIC_ALLEGIANCE_WARGEAR_HEADER_TOKENS = (
        "when",
        "you",
        "select",
        "this",
        "model",
        "to",
        "include",
        "in",
        "your",
        "army",
        "you",
        "must",
        "select",
        "one",
        "of",
        "the",
        "keywords",
        "below",
        "until",
        "the",
        "end",
        "of",
        "the",
        "battle",
        "this",
        "model",
        "has",
        "that",
        "keyword",
        "and",
        "the",
        "additional",
        "wargear",
        "stated",
        "for",
        "that",
        "keyword",
        "below",
    )
    _DAEMONIC_ALLEGIANCE_WARGEAR_KEYWORDS = ("khorne", "tzeentch", "nurgle", "slaanesh")
    _DAEMONIC_ALLEGIANCE_WARGEAR_EFFECT_TOKENS = (
        "this",
        "model",
        "is",
        "additionally",
        "equipped",
        "with",
    )
    _NUMBER_WORDS = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    _BEARER_INVULNERABLE_SAVE_RE = re.compile(
        r"^the bearer has a (\d)\+ invulnerable save\.?$",
        re.IGNORECASE,
    )
    _BEARER_SAVE_CHARACTERISTIC_RE = re.compile(
        r"^the bearer has a save characteristic of (\d)\+\.?$",
        re.IGNORECASE,
    )
    _TARGET_HIT_ROLL_PENALTY_UNIT_RE = re.compile(
        r"^each time (?:a|an) (?:(?P<atype>melee|ranged) )?attack targets this unit, subtract 1 from the hit roll",
        re.IGNORECASE,
    )
    _TARGET_HIT_ROLL_PENALTY_MODEL_RE = re.compile(
        r"^each time (?:a|an) (?:(?P<atype>melee|ranged) )?attack targets this model, subtract 1 from the hit roll",
        re.IGNORECASE,
    )
    _SPAWN_ONLY_ABILITY_RE = re.compile(r"^using\s+sir\s+hekhtur$", re.IGNORECASE)

    def _parse_warlord_enhancement_restrictions(self) -> None:
        """Parse datasheet abilities that forbid Warlord selection or Enhancements."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}

        found_warlord = False
        found_enhancements = False

        def _scan(text: str) -> None:
            nonlocal found_warlord, found_enhancements
            if not text or (found_warlord and found_enhancements):
                return
            normalized = self._normalize_rules_text(text)
            if not normalized:
                return
            if not found_warlord and self._CANNOT_BE_WARLORD_RE.search(normalized):
                found_warlord = True
            if not found_enhancements and self._CANNOT_BE_GIVEN_ENHANCEMENTS_RE.search(normalized):
                found_enhancements = True

        # Unit-level abilities
        for ab in list(getattr(self, "possible_abilities", []) or []):
            try:
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
            except Exception:
                desc = ""
            _scan(desc)
            if found_warlord and found_enhancements:
                break

        # Model-level abilities
        if not (found_warlord and found_enhancements):
            for model in list(getattr(self, "models", []) or []):
                try:
                    abilities = getattr(model, "abilities", {}) or {}
                except Exception:
                    abilities = {}
                for ab in abilities.values():
                    try:
                        desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
                    except Exception:
                        desc = ""
                    _scan(desc)
                    if found_warlord and found_enhancements:
                        break
                if found_warlord and found_enhancements:
                    break

        if found_warlord:
            self.special_rules["cannot_be_warlord"] = True
        if found_enhancements:
            self.special_rules["cannot_be_given_enhancements"] = True

    def _parse_spawn_only_restrictions(self) -> None:
        """Flag units that cannot be mustered and only spawn via other rules."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}

        try:
            cost_entries = getattr(self._datasheet, "datasheets_models_cost", None) or []
        except Exception:
            cost_entries = []
        if cost_entries:
            return

        for ab in list(getattr(self, "possible_abilities", []) or []):
            try:
                name = ab if isinstance(ab, str) else (getattr(ab, "name", "") or "")
            except Exception:
                name = ""
            if self._SPAWN_ONLY_ABILITY_RE.search(str(name).strip()):
                self.special_rules["spawn_only"] = True
                self.special_rules["spawn_only_reason"] = "USING SIR HEKHTUR + no points data"
                return

    def _parse_daemonic_allegiance_wargear_options(self, text: str) -> list[tuple[str, str]]:
        norm = self._normalize_rules_text(text or "")
        if not norm:
            return []
        tokens = re.sub(r"[^a-z0-9]+", " ", norm.lower()).split()
        header = list(self._DAEMONIC_ALLEGIANCE_WARGEAR_HEADER_TOKENS)
        if tokens[:len(header)] != header:
            return []
        idx = len(header)
        if idx >= len(tokens):
            return []
        keywords = set(self._DAEMONIC_ALLEGIANCE_WARGEAR_KEYWORDS)
        effect = list(self._DAEMONIC_ALLEGIANCE_WARGEAR_EFFECT_TOKENS)
        options: list[tuple[str, str]] = []
        seen = set()
        while idx < len(tokens):
            kw = tokens[idx]
            if kw not in keywords:
                return []
            idx += 1
            if tokens[idx:idx + len(effect)] != effect:
                return []
            idx += len(effect)
            start = idx
            while idx < len(tokens) and tokens[idx] not in keywords:
                idx += 1
            if start == idx:
                return []
            wargear_raw = " ".join(tokens[start:idx]).strip()
            if not wargear_raw:
                return []
            kw_upper = kw.upper()
            if kw_upper in seen:
                return []
            seen.add(kw_upper)
            resolved = wargear_raw
            try:
                want = Unit._norm_wargear_name(wargear_raw)
                for wg in list(getattr(self, "possible_wargear", []) or []):
                    try:
                        if Unit._norm_wargear_name(getattr(wg, "name", "")) == want:
                            resolved = str(getattr(wg, "name", "") or wargear_raw)
                            break
                    except Exception:
                        continue
            except Exception:
                resolved = wargear_raw
            options.append((kw_upper, resolved))
        return options

    def get_daemonic_allegiance_options(self) -> list[tuple[str, str]]:
        cache = getattr(self, "_ability_cache", None)
        if isinstance(cache, dict) and "daemonic_allegiance_options" in cache:
            return list(cache.get("daemonic_allegiance_options") or [])
        options: list[tuple[str, str]] = []
        for ab in self._iter_active_abilities():
            try:
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
            except Exception:
                desc = ""
            parsed = self._parse_daemonic_allegiance_wargear_options(desc or "")
            if parsed:
                options = parsed
                break
        if not isinstance(cache, dict):
            cache = {}
        cache["daemonic_allegiance_options"] = list(options)
        self._ability_cache = cache
        return list(options)

    def get_daemonic_allegiance_selection(self) -> Optional[str]:
        choice = getattr(self, "daemonic_allegiance", None)
        if choice:
            token = str(choice).strip()
            if token.lower() in ("unset", "none"):
                choice = None
            else:
                choice = token
        if choice:
            return str(choice).strip()
        try:
            sr = getattr(self, "special_rules", None)
        except Exception:
            sr = None
        if isinstance(sr, dict):
            choice = sr.get("daemonic_allegiance")
            if choice:
                token = str(choice).strip()
                if token.lower() in ("unset", "none"):
                    choice = None
                else:
                    choice = token
        return str(choice).strip() if choice else None

    def apply_daemonic_allegiance_selection(self, selection: Optional[str] = None) -> bool:
        options = list(self.get_daemonic_allegiance_options() or [])
        if not options:
            return False
        if not selection:
            selection = self.get_daemonic_allegiance_selection()
        if not selection:
            sr = getattr(self, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["daemonic_allegiance_pending"] = True
            self.special_rules = sr
            return False
        matched = None
        for kw, wargear_name in options:
            if kw.strip().lower() == str(selection).strip().lower():
                matched = (kw, wargear_name)
                break
        if matched is None:
            raise ValueError(f"Daemonic Allegiance selection '{selection}' is not valid for unit '{self.name}'.")
        kw, wargear_name = matched
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if sr.get("daemonic_allegiance_applied") and sr.get("daemonic_allegiance") == kw:
            return True
        self.daemonic_allegiance = kw
        sr["daemonic_allegiance"] = kw
        sr["daemonic_allegiance_wargear"] = wargear_name
        sr.pop("daemonic_allegiance_pending", None)
        if kw not in list(getattr(self, "keywords", []) or []):
            try:
                self.keywords.append(kw)
            except Exception:
                pass
        target_norm = Unit._norm_wargear_name(wargear_name)
        matching = None
        for wg in list(getattr(self, "possible_wargear", []) or []):
            try:
                if Unit._norm_wargear_name(getattr(wg, "name", "")) == target_norm:
                    matching = wg
                    break
            except Exception:
                continue
        for model in list(getattr(self, "models", []) or []):
            try:
                wargear_list = list(getattr(model, "wargear", []) or [])
            except Exception:
                wargear_list = []
            if any(Unit._norm_wargear_name(getattr(wg, "name", "")) == target_norm for wg in wargear_list if wg):
                continue
            if matching is not None:
                wargear_list.append(matching)
                model.wargear = wargear_list
            else:
                try:
                    optional = list(getattr(model, "optional_wargear", []) or [])
                    optional.append(str(wargear_name))
                    model.optional_wargear = optional
                except Exception:
                    pass
        if matching is None:
            sr["daemonic_allegiance_wargear_missing"] = wargear_name
        sr["daemonic_allegiance_applied"] = True
        self.special_rules = sr
        return True

    def _scan_command_phase_sticky_objective(self) -> bool:
        for ab in self._iter_active_abilities():
            try:
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
            except Exception:
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            low = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
            if "end of your command phase" not in low:
                continue
            if "objective marker remains under your control" not in low:
                continue
            if "objective marker you control" not in low:
                continue
            if "within range of an objective marker" not in low:
                continue
            loc_sticky = "level of control" in low and "greater than yours" in low
            timed_sticky = "start or end of any turn" in low and "until your opponent controls it" in low
            if not (loc_sticky or timed_sticky):
                continue
            return True
        return False

    def _scan_command_phase_bodyguard_return_ability(self):
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            low = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
            if "command phase" not in low:
                continue
            if "bodyguard model" not in low:
                continue
            if "return" not in low or "destroyed" not in low:
                continue
            if "not leading a unit" in low:
                continue
            if (
                "leading a unit" not in low
                and "leading this unit" not in low
                and "bearer is leading a unit" not in low
            ):
                continue
            if "can return" not in low:
                continue
            m = re.search(
                r"return\s+(?:up to\s+)?(one|a|\d+)\s+destroyed\s+bodyguard\s+models?",
                low,
            )
            if not m:
                continue
            token = m.group(1)
            try:
                amount = int(token)
            except Exception:
                amount = 1 if token in ("one", "a") else 0
            if amount <= 0:
                continue
            return {
                "amount": amount,
                "name": name or "Bodyguard Return",
                "description": desc or "",
            }
        return None

    def _scan_charge_phase_bodyguard_loss_ability(self):
        pattern = self._CHARGE_PHASE_BODYGUARD_LOSS_RE
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            text_src = self._strip_eligibility_prefix(desc or "")
            text = self._normalize_rules_text(text_src or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if pattern.fullmatch(norm):
                return {
                    "name": name or "Charge Phase Leadership Test",
                    "description": desc or "",
                }
        return None

    def _scan_end_of_opponent_turn_strategic_reserves_ability(self):
        pattern = self._OPPONENT_TURN_STRATEGIC_RESERVES_RE
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if pattern.fullmatch(norm):
                return {
                    "name": name or "Strategic Reserves",
                    "description": desc or "",
                }
        return None

    def _scan_transport_reactive_disembark_ability(self):
        pattern = self._TRANSPORT_REACTIVE_DISEMBARK_RE
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            m = pattern.fullmatch(norm)
            if not m:
                continue
            try:
                rng = int(m.group(1))
            except Exception:
                rng = 0
            if rng <= 0:
                continue
            return {
                "name": name or "Reactive Disembark",
                "description": desc or "",
                "range": rng,
            }
        return None

    def _parse_command_phase_regain_wound_amount(self, text: str) -> int:
        if not text:
            return 0
        m = self._COMMAND_PHASE_REGAIN_WOUND_RE.search(text)
        if not m:
            return 0
        try:
            return int(m.group(1))
        except Exception:
            return 0

    def get_command_phase_regain_wound_amount(self, model: Optional['Model'] = None) -> int:
        """
        Return the number of wounds a model regains at the start of your Command phase.

        - Unit-level abilities apply to every model in the unit.
        - Model-level abilities only apply to that specific model.
        """
        cache_key = "command_phase_regain_wound_unit_amount"
        if cache_key in getattr(self, "_ability_cache", {}):
            base_amount = int(self._ability_cache[cache_key] or 0)
        else:
            base_amount = 0
            for ab in self._iter_active_possible_abilities():
                try:
                    if isinstance(ab, str):
                        desc = ab
                    else:
                        desc = str(getattr(ab, "description", "") or getattr(ab, "name", "") or "")
                except Exception:
                    desc = ""
                text = self._normalize_rules_text(desc or "")
                if not text:
                    continue
                base_amount += self._parse_command_phase_regain_wound_amount(text)
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache[cache_key] = int(base_amount or 0)

        if model is None:
            return int(base_amount or 0)

        amount = int(base_amount or 0)
        for ab in list(getattr(model, "abilities", {}) or {}).values():
            try:
                if not self._ability_is_active(ab):
                    continue
            except Exception:
                pass
            try:
                if isinstance(ab, str):
                    desc = ab
                else:
                    desc = str(getattr(ab, "description", "") or getattr(ab, "name", "") or "")
            except Exception:
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            amount += self._parse_command_phase_regain_wound_amount(text)
        return int(amount or 0)

    def _refresh_command_phase_flags(self) -> None:
        """Parse command-phase CP gains and sticky objective flags into special_rules."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        try:
            if "command_phase_bonus_cp" in sr:
                del sr["command_phase_bonus_cp"]
            if "sticky_objectives" in sr:
                del sr["sticky_objectives"]
        except Exception:
            pass
        try:
            cache = getattr(self, "_ability_cache", None)
            if isinstance(cache, dict) and "command_phase_sticky_objective" in cache:
                del cache["command_phase_sticky_objective"]
        except Exception:
            pass

        bonus_cp = 0
        for ab in self._iter_active_abilities():
            try:
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
            except Exception:
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            m = self._COMMAND_PHASE_BONUS_CP_RE.search(text)
            if m:
                try:
                    bonus_cp += int(m.group(1))
                except Exception:
                    continue

        if bonus_cp > 0:
            sr["command_phase_bonus_cp"] = int(bonus_cp)

        if self._scan_command_phase_sticky_objective():
            sr["sticky_objectives"] = True

        self.special_rules = sr

    def _refresh_fall_back_desperate_escape_flags(self) -> None:
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        try:
            for key in (
                "enemy_fallback_desperate_escape",
                "enemy_fallback_desperate_escape_exclude_monster_vehicle",
                "enemy_fallback_desperate_escape_bs_penalty",
                "enemy_fallback_desperate_escape_sources",
            ):
                if key in sr:
                    del sr[key]
        except Exception:
            pass

        sources: list[str] = []
        exclude_monster_vehicle = False
        bs_penalty = 0
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                continue
            text = self._normalize_rules_text(desc or "").lower()
            if not text:
                continue
            if "desperate escape" not in text:
                continue
            if ("fall back" not in text) and ("falls back" not in text) and ("fallback" not in text):
                continue
            if "excluding monsters and vehicles" in text or ("excluding monsters" in text and "vehicles" in text):
                exclude_monster_vehicle = True
            if "battle-shocked" in text and ("subtract 1" in text or "subtract one" in text):
                bs_penalty = max(bs_penalty, 1)
            if name:
                sources.append(name)

        if sources:
            sr["enemy_fallback_desperate_escape"] = True
            sr["enemy_fallback_desperate_escape_sources"] = sources
            if exclude_monster_vehicle:
                sr["enemy_fallback_desperate_escape_exclude_monster_vehicle"] = True
            if bs_penalty:
                sr["enemy_fallback_desperate_escape_bs_penalty"] = int(bs_penalty)
        self.special_rules = sr

    def _refresh_targeted_stratagem_cp_discount_flags(self) -> None:
        """Parse unit abilities that reduce Stratagem CP cost when this unit is targeted."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        try:
            if "stratagem_target_cp_discount" in sr:
                del sr["stratagem_target_cp_discount"]
            if "stratagem_target_cp_discount_sources" in sr:
                del sr["stratagem_target_cp_discount_sources"]
            if "stratagem_target_cp_discount_aura" in sr:
                del sr["stratagem_target_cp_discount_aura"]
        except Exception:
            pass

        names: list[str] = []
        aura_specs: list[dict] = []
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                continue
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if not norm:
                continue

            if self._TARGETED_STRATAGEM_CP_DISCOUNT_RE.fullmatch(norm):
                if name:
                    names.append(name)
                else:
                    names.append("Stratagem CP Discount")
                continue

            for pat in (
                self._TARGETED_STRATAGEM_CP_DISCOUNT_AURA_RE,
                self._TARGETED_STRATAGEM_CP_DISCOUNT_AURA_ALT_RE,
                self._TARGETED_STRATAGEM_CP_DISCOUNT_AURA_ALT2_RE,
            ):
                m = pat.fullmatch(norm)
                if not m:
                    continue
                try:
                    rng = int(m.group("range"))
                except Exception:
                    rng = 0
                if rng <= 0:
                    continue
                kw = str(m.group("keyword") or "").strip()
                if kw:
                    kw = re.sub(r"\s+", " ", kw).strip().upper()
                spec = {
                    "range": rng,
                    "keyword": kw,
                    "name": name or "Stratagem CP Discount",
                    "description": desc or "",
                }
                aura_specs.append(spec)
                break

        if names:
            sr["stratagem_target_cp_discount"] = True
            seen = set()
            deduped: list[str] = []
            for n in names:
                key = str(n).strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                deduped.append(str(n))
            if deduped:
                sr["stratagem_target_cp_discount_sources"] = deduped

        if aura_specs:
            seen_specs: set[tuple] = set()
            deduped_specs: list[dict] = []
            for spec in aura_specs:
                key = (
                    int(spec.get("range", 0) or 0),
                    str(spec.get("keyword", "") or "").strip().lower(),
                    str(spec.get("name", "") or "").strip().lower(),
                )
                if key in seen_specs:
                    continue
                seen_specs.add(key)
                deduped_specs.append(spec)
            if deduped_specs:
                sr["stratagem_target_cp_discount_aura"] = deduped_specs

        self.special_rules = sr

    @staticmethod
    def _parse_return_on_death_wounds(text: str):
        t = str(text or "").strip().lower()
        if not t:
            return "full"
        if "full wounds" in t:
            return "full"
        if "d3" in t:
            return "d3"
        if "d6" in t:
            return "d6"
        m = re.search(r"\d+", t)
        if m:
            try:
                return int(m.group(0))
            except Exception:
                return "full"
        return "full"

    def _refresh_return_on_death_flags(self) -> None:
        """Parse 'first time destroyed' return-to-battlefield abilities into special_rules."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        try:
            if "return_on_death_specs" in sr:
                del sr["return_on_death_specs"]
        except Exception:
            pass

        specs: list[dict] = []
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                continue
            text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or ""))
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", "s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if not norm:
                continue
            m = self._RETURN_ON_DEATH_RE.fullmatch(norm)
            if not m:
                continue
            try:
                roll_min = int(m.group("roll") or 2)
            except Exception:
                roll_min = 2
            wounds_raw = m.group("wounds") or ""
            wounds = self._parse_return_on_death_wounds(wounds_raw)
            skip_deadly = "without resolving its deadly demise ability" in norm
            key = re.sub(r"[^a-z0-9]+", "_", str(name or "return_on_death").lower()).strip("_")
            if not key:
                key = "return_on_death"
            specs.append(
                {
                    "name": name or "Return on Death",
                    "roll_min": roll_min,
                    "wounds": wounds,
                    "skip_deadly_demise": bool(skip_deadly),
                    "key": key,
                }
            )

        if specs:
            seen: set[tuple] = set()
            deduped: list[dict] = []
            for spec in specs:
                key = (
                    str(spec.get("key", "") or "").strip().lower(),
                    int(spec.get("roll_min", 0) or 0),
                    str(spec.get("wounds", "") or "").strip().lower(),
                )
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(spec)
            if deduped:
                sr["return_on_death_specs"] = deduped

        try:
            if hasattr(self, "_ability_cache"):
                self._ability_cache.pop("return_on_death_specs", None)
        except Exception:
            pass

        self.special_rules = sr

    def _get_return_on_death_specs(self) -> list[dict]:
        cache_key = "return_on_death_specs"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache.get(cache_key) or [])

        sr = getattr(self, "special_rules", None)
        specs = list(sr.get("return_on_death_specs", []) or []) if isinstance(sr, dict) else []

        if isinstance(sr, dict) and sr.get("enhancement_phoenix_gem"):
            specs.append(
                {
                    "name": "Phoenix Gem",
                    "roll_min": 2,
                    "wounds": "full",
                    "skip_deadly_demise": False,
                    "key": "phoenix_gem",
                }
            )

        seen: set[tuple] = set()
        deduped: list[dict] = []
        for spec in specs:
            key = (
                str(spec.get("key", "") or "").strip().lower(),
                int(spec.get("roll_min", 0) or 0),
                str(spec.get("wounds", "") or "").strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(spec)

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(deduped)
        return list(deduped)

    def _refresh_charge_end_mortal_wounds_flags(self) -> None:
        """Parse charge-move mortal wound triggers into special_rules."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        specs = []
        seen = set()

        for u in members:
            if u is None:
                continue
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text = u._normalize_rules_text(desc or "")
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                low = text.lower()
                if "charge move" not in low or "mortal wound" not in low:
                    continue
                kind = None
                if self._CHARGE_END_MORTAL_PER_MODEL_RE.search(text):
                    kind = "per_model_4plus_d3"
                elif self._CHARGE_END_MORTAL_TABLE_RE.search(text):
                    kind = "table_d6_2_3_4_5_6"
                if not kind:
                    continue
                source = str(name or "Charge Mortals").strip() or "Charge Mortals"
                key = (kind, source.lower())
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "kind": kind,
                        "name": source,
                        "description": str(desc or ""),
                    }
                )

        for u in members:
            if u is None:
                continue
            sr_u = getattr(u, "special_rules", None)
            if not isinstance(sr_u, dict):
                sr_u = {}
            if specs:
                sr_u["charge_end_mortal_wounds"] = list(specs)
            else:
                if "charge_end_mortal_wounds" in sr_u:
                    del sr_u["charge_end_mortal_wounds"]
            u.special_rules = sr_u

    def _refresh_fight_within_3_flags(self) -> None:
        """Parse fight-within-3\" eligibility abilities into special_rules."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        specs = []
        seen = set()

        for u in members:
            if u is None:
                continue
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text = u._normalize_rules_text(desc or "")
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                low = text.lower()
                if "selected to fight" not in low:
                    continue
                if "eligible to fight" not in low:
                    continue
                if "within 3" not in low:
                    continue
                if "engagement range" not in low:
                    continue
                if not self._FIGHT_WITHIN_3_RE.search(text):
                    continue
                source = str(name or "Fight Within 3\"").strip() or "Fight Within 3\""
                key = source.lower()
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "name": source,
                        "description": str(desc or ""),
                    }
                )

        for u in members:
            if u is None:
                continue
            sr_u = getattr(u, "special_rules", None)
            if not isinstance(sr_u, dict):
                sr_u = {}
            if specs:
                sr_u["fight_within_3"] = list(specs)
            else:
                if "fight_within_3" in sr_u:
                    del sr_u["fight_within_3"]
            if not specs and "fight_within_3_active" in sr_u:
                del sr_u["fight_within_3_active"]
            if not specs and "fight_within_3_active_source" in sr_u:
                del sr_u["fight_within_3_active_source"]
            u.special_rules = sr_u

    def _refresh_bearer_unit_common_modifiers(self) -> None:
        """Parse common bearer/leading-unit rules that grant simple unit-wide modifiers."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        # Clear prior bearer-unit modifiers from all attached members.
        for u in members:
            try:
                u.remove_characteristic_modifiers_by_source("ability:bearer_unit_leadership")
            except Exception:
                pass
            try:
                u.remove_characteristic_modifiers_by_source("ability:bearer_unit_movement_set")
            except Exception:
                pass
            try:
                u.remove_characteristic_modifiers_by_source("ability:bearer_unit_objective_control")
            except Exception:
                pass
            try:
                u.remove_characteristic_modifiers_by_source("ability:unit_contains_objective_control")
            except Exception:
                pass
            try:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                existing = sr.get("charge_roll_modifiers")
                if isinstance(existing, list):
                    kept = []
                    for item in existing:
                        if isinstance(item, dict) and item.get("tag") == "ability:bearer_unit_charge_bonus":
                            continue
                        kept.append(item)
                    if kept:
                        sr["charge_roll_modifiers"] = kept
                    elif "charge_roll_modifiers" in sr:
                        del sr["charge_roll_modifiers"]
                existing = sr.get("advance_roll_modifiers")
                if isinstance(existing, list):
                    kept = []
                    for item in existing:
                        if isinstance(item, dict) and item.get("tag") == "ability:bearer_unit_advance_bonus":
                            continue
                        kept.append(item)
                    if kept:
                        sr["advance_roll_modifiers"] = kept
                    elif "advance_roll_modifiers" in sr:
                        del sr["advance_roll_modifiers"]
                for key in (
                    "bearer_unit_fnp",
                    "bearer_unit_invulnerable_save",
                    "bearer_unit_sustained_hits_value",
                    "bearer_unit_sustained_hits_value_melee",
                    "bearer_unit_sustained_hits_value_ranged",
                    "bearer_unit_ignores_cover",
                    "bearer_unit_target_hit_penalties",
                    "bearer_unit_deep_strike",
                    "bearer_unit_phase_move_types",
                    "bearer_unit_phase_move_terrain_only_types",
                    "bearer_unit_phase_move_engagement_types",
                    "bearer_unit_auto_pass_desperate_escape",
                ):
                    if key in sr:
                        del sr[key]
                u.special_rules = sr
            except Exception:
                pass
            try:
                cache = getattr(u, "_ability_cache", None)
                if isinstance(cache, dict):
                    for k in list(cache.keys()):
                        if k == "feel_no_pain" or k == "deep_strike" or k.startswith("target_hit_penalty:") or k.startswith("model_invulnerable_save:"):
                            del cache[k]
                        if k.startswith("model_save_characteristic:"):
                            del cache[k]
            except Exception:
                pass

        seen = set()
        charge_mods: list[tuple[int, str]] = []
        advance_mods: list[tuple[int, str]] = []
        leadership_sets: list[tuple[int, str]] = []
        movement_sets: list[tuple[int, str]] = []
        oc_mods: list[tuple[int, str]] = []
        contains_oc_mods: list[tuple[int, str]] = []
        fnp_entries: list[dict] = []
        invuln_entries: list[dict] = []
        sustained_hits_value = 0
        sustained_hits_value_melee = 0
        sustained_hits_value_ranged = 0
        ignores_cover_sources: set[str] = set()
        hit_penalties: list[dict] = []
        phase_move_types: set[str] = set()
        phase_move_terrain_only_types: set[str] = set()
        phase_engagement_types: set[str] = set()
        auto_pass_desperate_escape = False
        grant_deep_strike = False

        def _iter_sentences(text: str) -> list[str]:
            if not text:
                return []
            cleaned = re.sub(r";\s*", ". ", text)
            return [part.strip() for part in re.split(r"\.\s*", cleaned) if part.strip()]

        def _parse_move_types(value: str) -> set[str]:
            return self._parse_move_types_from_text(value)

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                key = (
                    str(name or "").strip().lower(),
                    u._normalize_rules_text(desc or "").lower(),
                )
                if key in seen:
                    continue
                seen.add(key)
                text = u._normalize_rules_text(desc or name or "")
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                text_lower = text.lower()
                requires_attached_leader = bool(re.search(r"\bthis model is leading\b", text_lower))
                if requires_attached_leader and not getattr(u, "is_attached_leader", False):
                    continue
                if "leading a unit" in text_lower and "bearer's unit" not in text_lower:
                    text = re.sub(r"\bthat unit\b", "the bearer's unit", text, flags=re.IGNORECASE)

                for sentence in _iter_sentences(text):
                    if not sentence:
                        continue
                    m = self._BEARER_UNIT_ADVANCE_AND_CHARGE_BONUS_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            advance_mods.append((val, source))
                            charge_mods.append((val, source))
                    m = self._BEARER_UNIT_ADVANCE_BONUS_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            advance_mods.append((val, source))
                    m = self._BEARER_UNIT_CHARGE_BONUS_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            charge_mods.append((val, source))

                    m = self._BEARER_UNIT_LEADERSHIP_SET_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            leadership_sets.append((val, source))

                    m = self._BEARER_UNIT_MOVEMENT_SET_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            movement_sets.append((val, source))

                    m = self._BEARER_UNIT_OC_BONUS_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            oc_mods.append((val, source))

                    m = self._UNIT_CONTAINS_OC_BONUS_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group("amt"))
                        except Exception:
                            val = None
                        if val:
                            target = m.group("model")
                            if u._unit_contains_model_named(target):
                                source = str(name or "Unit contains ability").strip() or "Unit contains ability"
                                contains_oc_mods.append((val, source))

                    m = self._BEARER_UNIT_FNP_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            cond = None
                            try:
                                sm = sentence.lower()
                                cm = re.search(
                                    r"(?:feel\s+no\s+pain|fnp)\s*\(?[1-6]\+(?:\)?)\s+(?:ability\s+)?(against|while|when)\s+(.+)",
                                    sm,
                                    flags=re.IGNORECASE,
                                )
                                if cm and cm.group(1) and cm.group(2):
                                    cond = f"{cm.group(1)} {cm.group(2)}".strip()
                            except Exception:
                                cond = None
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            fnp_entries.append({"value": int(val), "condition": cond, "source": source})

                    m = self._BEARER_UNIT_INVULNERABLE_SAVE_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                            invuln_entries.append({"value": int(val), "source": source})

                    m = self._BEARER_UNIT_SUSTAINED_HITS_RE.search(sentence)
                    if m:
                        try:
                            val = int(m.group(1))
                        except Exception:
                            val = None
                        if val:
                            scope = sentence.lower()
                            has_melee = "melee" in scope
                            has_ranged = "ranged" in scope
                            if has_melee and not has_ranged:
                                sustained_hits_value_melee = max(int(sustained_hits_value_melee), int(val))
                            elif has_ranged and not has_melee:
                                sustained_hits_value_ranged = max(int(sustained_hits_value_ranged), int(val))
                            elif has_melee and has_ranged:
                                sustained_hits_value_melee = max(int(sustained_hits_value_melee), int(val))
                                sustained_hits_value_ranged = max(int(sustained_hits_value_ranged), int(val))
                            else:
                                sustained_hits_value = max(int(sustained_hits_value), int(val))

                    if self._BEARER_UNIT_IGNORES_COVER_RE.search(sentence):
                        source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                        ignores_cover_sources.add(source)

                    m = self._BEARER_UNIT_TARGET_HIT_PENALTY_RE.search(sentence)
                    if m:
                        atype = (m.group("atype") or "any").strip().lower()
                        source = str(name or "Bearer unit ability").strip() or "Bearer unit ability"
                        hit_penalties.append({"value": 1, "attack_type": atype, "source": source})

                    sentence_lower = sentence.lower()
                    if self._BEARER_UNIT_DEEP_STRIKE_RE.search(sentence_lower):
                        grant_deep_strike = True

                    if self._BEARER_UNIT_PHASE_MOVE_RE.search(sentence_lower):
                        move_types = _parse_move_types(sentence_lower)
                        if move_types:
                            phase_move_types.update(move_types)
                    elif self._BEARER_UNIT_PHASE_TERRAIN_ONLY_RE.search(sentence_lower):
                        move_types = _parse_move_types(sentence_lower)
                        if move_types:
                            phase_move_terrain_only_types.update(move_types)

                    if self._BEARER_UNIT_PHASE_ENGAGEMENT_RE.search(sentence_lower):
                        move_types = _parse_move_types(sentence_lower)
                        if move_types:
                            phase_engagement_types.update(move_types)
                        if "desperate escape" in sentence_lower and "automatic" in sentence_lower and "pass" in sentence_lower:
                            auto_pass_desperate_escape = True

        if charge_mods:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                mods = list(sr.get("charge_roll_modifiers", []) or [])
                for val, source in charge_mods:
                    mods.append({
                        "value": int(val),
                        "source": source,
                        "tag": "ability:bearer_unit_charge_bonus",
                    })
                sr["charge_roll_modifiers"] = mods
                u.special_rules = sr

        if advance_mods:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                mods = list(sr.get("advance_roll_modifiers", []) or [])
                for val, source in advance_mods:
                    mods.append({
                        "value": int(val),
                        "source": source,
                        "tag": "ability:bearer_unit_advance_bonus",
                    })
                sr["advance_roll_modifiers"] = mods
                u.special_rules = sr

        if leadership_sets:
            from ..utility.modifiers import Modifier, ModifierOp

            for u in members:
                for val, source in leadership_sets:
                    u.add_characteristic_modifier(
                        "leadership",
                        Modifier(ModifierOp.SET, int(val), source=f"ability:bearer_unit_leadership:{source}"),
                    )

        if movement_sets:
            from ..utility.modifiers import Modifier, ModifierOp

            for u in members:
                for val, source in movement_sets:
                    u.add_characteristic_modifier(
                        "movement",
                        Modifier(ModifierOp.SET, int(val), source=f"ability:bearer_unit_movement_set:{source}"),
                    )

        if oc_mods:
            from ..utility.modifiers import Modifier, ModifierOp

            for u in members:
                for val, source in oc_mods:
                    u.add_characteristic_modifier(
                        "objective_control",
                        Modifier(ModifierOp.ADD, int(val), source=f"ability:bearer_unit_objective_control:{source}"),
                    )

        if contains_oc_mods:
            from ..utility.modifiers import Modifier, ModifierOp

            for u in members:
                for val, source in contains_oc_mods:
                    u.add_characteristic_modifier(
                        "objective_control",
                        Modifier(ModifierOp.ADD, int(val), source=f"ability:unit_contains_objective_control:{source}"),
                    )

        if fnp_entries:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_fnp"] = list(fnp_entries)
                u.special_rules = sr

        if invuln_entries:
            deduped = []
            seen_invuln = set()
            for entry in invuln_entries:
                try:
                    val = int(entry.get("value"))
                except Exception:
                    continue
                source = str(entry.get("source", "") or "")
                key = (val, source)
                if key in seen_invuln:
                    continue
                seen_invuln.add(key)
                deduped.append({"value": val, "source": source})
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_invulnerable_save"] = list(deduped)
                u.special_rules = sr

        if sustained_hits_value:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_sustained_hits_value"] = int(sustained_hits_value)
                u.special_rules = sr
        if sustained_hits_value_melee:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_sustained_hits_value_melee"] = int(sustained_hits_value_melee)
                u.special_rules = sr
        if sustained_hits_value_ranged:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_sustained_hits_value_ranged"] = int(sustained_hits_value_ranged)
                u.special_rules = sr

        if ignores_cover_sources:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_ignores_cover"] = True
                u.special_rules = sr

        if hit_penalties:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_target_hit_penalties"] = list(hit_penalties)
                u.special_rules = sr

        if grant_deep_strike:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_deep_strike"] = True
                u.special_rules = sr

        if phase_move_types:
            move_types_sorted = sorted(phase_move_types)
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_phase_move_types"] = list(move_types_sorted)
                u.special_rules = sr

        if phase_move_terrain_only_types:
            move_types_sorted = sorted(phase_move_terrain_only_types)
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_phase_move_terrain_only_types"] = list(move_types_sorted)
                u.special_rules = sr

        if phase_engagement_types:
            move_types_sorted = sorted(phase_engagement_types)
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_phase_move_engagement_types"] = list(move_types_sorted)
                u.special_rules = sr

        if auto_pass_desperate_escape:
            for u in members:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["bearer_unit_auto_pass_desperate_escape"] = True
                u.special_rules = sr

    def _refresh_bearer_keyword_flags(self) -> None:
        """Parse bearer-only keyword additions (e.g., SMOKE) into special_rules."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        for u in members:
            try:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                if "ability_added_keywords" in sr:
                    del sr["ability_added_keywords"]
                u.special_rules = sr
            except Exception:
                continue

        for u in members:
            added: list[str] = []
            for ab in u._iter_active_abilities():
                try:
                    if isinstance(ab, str):
                        desc = ab
                    else:
                        desc = str(getattr(ab, "description", "") or getattr(ab, "name", "") or "")
                except Exception:
                    desc = ""
                text = u._normalize_rules_text(desc or "")
                if not text:
                    continue
                norm = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
                norm = re.sub(r"'s\b", "s", norm)
                norm = re.sub(r"[^a-z0-9]+", " ", norm)
                norm = re.sub(r"\s+", " ", norm).strip()
                if re.fullmatch(r"(?:the )?" + re.escape(self._BEARER_SMOKE_KEYWORD_TOKENS), norm):
                    added.append("Smoke")
            if added:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                seen = set()
                unique = []
                for kw in added:
                    k = str(kw).strip()
                    lk = k.lower()
                    if not k or lk in seen:
                        continue
                    seen.add(lk)
                    unique.append(k)
                if unique:
                    sr["ability_added_keywords"] = unique
                u.special_rules = sr

    def _refresh_move_over_friendly_monster_vehicle_flags(self) -> None:
        """Parse move-over friendly MONSTER/VEHICLE and low-terrain traversal rules into special_rules."""
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        for key in (
            "move_over_friendly_monster_vehicle_types",
            "move_over_low_terrain_height_types",
            "move_over_low_terrain_height_value",
        ):
            if key in sr:
                del sr[key]

        pattern = (
            r"each time (?:this model|this unit) makes a (?P<moves>.+?) move "
            r"it can move (?:over|through) friendly monster (?:and|or) vehicle models? and "
            r"(?:sections of )?terrain features that are (?P<height>\d+) or less in height"
            r"(?: as if they were not there)?"
        )
        terrain_only_pattern = (
            r"each time (?:this model|this unit) makes a (?P<moves>.+?) move "
            r"it can move (?:over|through) (?:sections of )?terrain features that are (?P<height>\d+) or less in height"
            r"(?: as if they were not there)?"
        )
        friendly_move_types: set[str] = set()
        low_terrain_move_types: set[str] = set()
        height_value: Optional[int] = None
        seen: set[str] = set()

        def _parse_move_types(moves_text: str) -> Optional[set[str]]:
            tokens = [t for t in moves_text.split() if t]
            allowed = {"normal", "advance", "fall", "back", "fallback", "or", "and"}
            if not tokens or any(t not in allowed for t in tokens):
                return None
            if "normal" not in tokens:
                return None
            parsed: set[str] = {"move"}
            if "advance" in tokens:
                parsed.add("advance")
            if "fallback" in tokens or "fall back" in moves_text:
                parsed.add("fall_back")
            return parsed

        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text = str(desc or name or "")
            text = self._strip_eligibility_prefix(text)
            norm = self._normalize_rules_text(text)
            if not norm:
                continue
            norm = norm.replace("\u2019", "'").replace("\u0192?T", "'")
            norm = re.sub(r"'s\b", "s", norm, flags=re.IGNORECASE)
            norm = re.sub(r"[^a-z0-9]+", " ", norm.lower())
            norm = re.sub(r"\s+", " ", norm).strip()
            if not norm or norm in seen:
                continue
            seen.add(norm)
            m = re.fullmatch(pattern, norm)
            if m:
                moves_text = (m.group("moves") or "").strip()
                move_types = _parse_move_types(moves_text or "")
                if move_types is None:
                    continue
                friendly_move_types.update(move_types)
                low_terrain_move_types.update(move_types)
                try:
                    height = int(m.group("height"))
                except Exception:
                    height = None
                if height is not None:
                    if height_value is None or height > height_value:
                        height_value = height
                continue
            m = re.fullmatch(terrain_only_pattern, norm)
            if not m:
                continue
            moves_text = (m.group("moves") or "").strip()
            move_types = _parse_move_types(moves_text or "")
            if move_types is None:
                continue
            low_terrain_move_types.update(move_types)
            try:
                height = int(m.group("height"))
            except Exception:
                height = None
            if height is not None:
                if height_value is None or height > height_value:
                    height_value = height

        if friendly_move_types:
            sr["move_over_friendly_monster_vehicle_types"] = sorted(friendly_move_types)
        if height_value is not None:
            sr["move_over_low_terrain_height_value"] = float(height_value)
            sr["move_over_low_terrain_height_types"] = sorted(low_terrain_move_types or {"move", "advance"})
        self.special_rules = sr

    def _unit_contains_model_named(self, target: str) -> bool:
        norm_target = self._normalize_attached_unit_name(target)
        if not norm_target:
            return False
        for article in ("an ", "a "):
            if norm_target.startswith(article):
                norm_target = norm_target[len(article):].strip()
        if not norm_target:
            return False
        target_tokens = set(norm_target.split())
        for model in list(getattr(self, "models", []) or []):
            name = self._normalize_attached_unit_name(getattr(model, "name", ""))
            if not name:
                continue
            if norm_target in name:
                return True
            if target_tokens and target_tokens.issubset(set(name.split())):
                return True
        return False

    def _transport_disembark_rules(self) -> dict:
        """
        Detect transport abilities that modify disembark behavior (Assault Ramp/Vehicle patterns).

        Returns:
            dict with keys:
              - allow_after_advance (bool): can disembark after transport Advanced
              - allow_charge_after_normal_move (bool): can charge after disembarking from a Normal move
        """
        cache_key = "transport_disembark_rules"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rules = {
            "allow_after_advance": False,
            "allow_charge_after_normal_move": False,
        }

        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text = self._normalize_rules_text(desc or name or "")
            if not text:
                continue
            low = text.lower()

            # Assault Ramp: disembark after Normal move and still eligible to charge.
            if (
                "disembark" in low
                and "after it has made a normal move" in low
                and ("eligible to declare a charge" in low or "can declare a charge" in low)
            ):
                rules["allow_charge_after_normal_move"] = True

            # Assault Vehicle: disembark after Advance, counts as Normal move, cannot charge.
            if (
                "disembark" in low
                and "after it has advanced" in low
                and "cannot declare a charge" in low
            ):
                rules["allow_after_advance"] = True

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rules
        return rules

    def _parse_attribute(self, attribute_value: str) -> int:
        # Remove " and + from the attribute value
        attribute_value = attribute_value.replace("\"", "").replace("+", "").replace("*", "")
        if "-" in attribute_value:
            return 0
        return int(attribute_value)

    def _parse_range(self, range_string: str) -> Range:
        return Range.from_string(range_string)

    def _is_unknown_base_size(self, base_size: str) -> bool:
        raw = str(base_size or "").strip().lower()
        return raw in ("", "use model", "no official base size")

    def _warn_unknown_base_size(self, model_name: str, fallback_desc: str) -> None:
        if not hasattr(self, "_unknown_base_size_warnings"):
            self._unknown_base_size_warnings = set()
        key = (str(model_name or "").strip().lower(), str(fallback_desc or "").strip().lower())
        if key in self._unknown_base_size_warnings:
            return
        self._unknown_base_size_warnings.add(key)
        print(
            f"WARNING: {self.name}: base size for '{model_name or 'model'}' is unspecified; "
            f"using {fallback_desc}."
        )

    def _parse_base_size(
        self,
        base_size: str,
        *,
        fallback_base_size: Optional[str] = None,
        model_name: str = "",
    ) -> Base:
        def _strip_flying(raw: str) -> tuple[str, bool]:
            cleaned = str(raw or "")
            is_flying = "flying base" in cleaned.lower()
            if is_flying:
                cleaned = re.sub(r"flying base", "", cleaned, flags=re.IGNORECASE).strip()
            return cleaned, is_flying

        cleaned, is_flying = _strip_flying(base_size)
        if self._is_unknown_base_size(cleaned):
            if fallback_base_size and not self._is_unknown_base_size(fallback_base_size):
                cleaned, fallback_flying = _strip_flying(fallback_base_size)
                is_flying = is_flying or fallback_flying
            else:
                # No reliable base size provided; use a conservative default and warn once.
                if bool(getattr(self, "is_vehicle", False)) or bool(getattr(self, "is_monster", False)) or bool(getattr(self, "is_transport", False)):
                    base = Base(BaseType.HULL, (convert_mm_to_inches(80 / 2), convert_mm_to_inches(40 / 2)))
                    self._warn_unknown_base_size(model_name, "80x40mm hull")
                else:
                    base = Base(BaseType.CIRCULAR, convert_mm_to_inches(32 / 2.0))
                    self._warn_unknown_base_size(model_name, "32mm base")
                if is_flying:
                    setattr(base, "is_flying_base", True)
                return base

        cleaned = cleaned.replace("mm", "").strip()
        if "x" in cleaned:
            major, minor = cleaned.split("x")
            major = convert_mm_to_inches(float(major.strip()) / 2.0)
            minor = convert_mm_to_inches(float(minor.strip()) / 2.0)
            base = Base(BaseType.ELLIPTICAL, (major, minor))
        else:
            base = Base(BaseType.CIRCULAR, convert_mm_to_inches(float(cleaned.strip()) / 2.0))

        if is_flying:
            setattr(base, "is_flying_base", True)
        return base

    def _normalize_base_size_name(self, text: str) -> str:
        text = (text or "").lower()
        text = re.sub(r"\([^)]*\)", " ", text)
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _parse_base_size_descr_overrides(self, base_size_descr: str) -> dict:
        if not base_size_descr:
            return {}
        base_size_descr = (
            base_size_descr.replace("\u2019", "'")
            .replace("\u2013", "-")
            .replace("\u2014", "-")
        )
        overrides: dict[str, str] = {}
        patterns = [
            r"(?P<name>[A-Za-z0-9 '\-]+?)\s+model\s+(?P<size>\d+(?:\.\d+)?\s*mm|\d+\s*x\s*\d+\s*mm)",
            r"(?P<name>[A-Za-z0-9 '\-]+?)\s+on\s+(?P<size>\d+(?:\.\d+)?\s*mm|\d+\s*x\s*\d+\s*mm)",
            r"(?P<name>[A-Za-z0-9 '\-]+?)\s+(?P<size>\d+(?:\.\d+)?\s*mm|\d+\s*x\s*\d+\s*mm)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, base_size_descr, flags=re.IGNORECASE):
                name = match.group("name").strip()
                size = match.group("size").strip()
                if not re.search(r"[A-Za-z]", name):
                    continue
                overrides[self._normalize_base_size_name(name)] = size
        return overrides

    def _select_base_size_override(self, base_size_descr: str, model_name: str) -> Optional[str]:
        if not base_size_descr or not model_name:
            return None
        overrides = self._parse_base_size_descr_overrides(base_size_descr)
        if not overrides:
            return None
        model_norm = self._normalize_base_size_name(model_name)
        if not model_norm:
            return None
        best = None
        best_len = -1
        for name_norm, size in overrides.items():
            if not name_norm:
                continue
            if name_norm == model_norm or name_norm in model_norm or model_norm in name_norm:
                if len(name_norm) > best_len:
                    best = size
                    best_len = len(name_norm)
        return best

    @property
    def id(self) -> str:
        return self._id

    def _parse_unit_composition(self, unit_composition):
        """
        Parse `datasheets_unit_composition` entries.

        Most entries are simple:
        - "1 Boss Nob"
        - "2-5 Space Marine Bikers"

        Some entries are composite (multiple parts):
        - "1 Runtherd and 10 Gretchin"
        - "1 Grenadier Sergeant, 7 Grenadiers and 1 Heavy Weapons Team"

        We ignore pure informational lines like:
        - "This unit can contain a maximum of 10 models."
        - "10 MODELS MAXIMUM"
        """
        import re

        def _split_top_level_commas(text: str) -> list[str]:
            parts: list[str] = []
            buf: list[str] = []
            depth = 0
            for ch in text:
                if ch == "(":
                    depth += 1
                elif ch == ")" and depth > 0:
                    depth -= 1
                if ch == "," and depth == 0:
                    seg = "".join(buf).strip()
                    if seg:
                        parts.append(seg)
                    buf = []
                else:
                    buf.append(ch)
            tail = "".join(buf).strip()
            if tail:
                parts.append(tail)
            return parts

        def _split_top_level_and(text: str) -> list[str]:
            # Split on " and " only when it looks like it separates entries (next token starts with a digit/range),
            # and only at top-level (not inside parentheses).
            parts: list[str] = []
            buf: list[str] = []
            depth = 0
            i = 0
            while i < len(text):
                ch = text[i]
                if ch == "(":
                    depth += 1
                elif ch == ")" and depth > 0:
                    depth -= 1
                if depth == 0 and text[i : i + 5].lower() == " and ":
                    nxt = text[i + 5 : i + 15].lstrip()
                    if nxt and re.match(r"^\d", nxt):
                        seg = "".join(buf).strip()
                        if seg:
                            parts.append(seg)
                        buf = []
                        i += 5
                        continue
                buf.append(ch)
                i += 1
            tail = "".join(buf).strip()
            if tail:
                parts.append(tail)
            return parts

        # Optional overall cap from informational lines like "10 MODELS MAXIMUM".
        # This is useful for validation and for complex compositions we don't fully model yet.
        self.unit_models_maximum = None

        options: list[dict[str, tuple[int, int]]] = []
        current: dict[str, tuple[int, int]] = {}
        for comp in unit_composition or []:
            desc = str(comp.get("description", "") or "").strip()
            if not desc:
                continue

            dlow = desc.strip().rstrip(".").lower()
            # Capture max models (do not treat as composition entry).
            if dlow.startswith("this unit can contain a maximum of "):
                mmax = re.search(r"maximum of\s+(\d+)\s+models", dlow)
                if mmax:
                    try:
                        self.unit_models_maximum = int(mmax.group(1))
                    except Exception:
                        pass
                continue
            if dlow.endswith("models maximum"):
                mmax = re.search(r"(\d+)\s+models maximum", dlow)
                if mmax:
                    try:
                        self.unit_models_maximum = int(mmax.group(1))
                    except Exception:
                        pass
                continue
            if dlow in ("or", "or:"):
                if current:
                    options.append(current)
                    current = {}
                continue
            if dlow.startswith("one of the following:"):
                continue

            # Remove trailing keyword annotation after an en-dash (" \u2013 EPIC HERO", etc.)
            main = desc.split(" \u2013 ", 1)[0].strip().rstrip(".")

            # Split into segments at top level: commas, then "and" separators.
            segments: list[str] = []
            for seg in _split_top_level_commas(main):
                for s2 in _split_top_level_and(seg):
                    s2 = s2.strip().rstrip(".")
                    if s2:
                        segments.append(s2)

            for seg in segments or [main]:
                seg = seg.strip().rstrip(".")
                m = re.match(r"^(?P<count>\d+(?:-\d+)?)\s+(?P<name>.+)$", seg)
                if not m:
                    continue
                count = m.group("count")
                model_name = m.group("name").strip().rstrip(".")
                if "-" in count:
                    min_size, max_size = map(int, count.split("-", 1))
                else:
                    min_size = max_size = int(count)
                if model_name in current:
                    prev_min, prev_max = current[model_name]
                    current[model_name] = (prev_min + min_size, prev_max + max_size)
                else:
                    current[model_name] = (min_size, max_size)

        if current:
            options.append(current)

        def _total_min(opt: dict[str, tuple[int, int]]) -> int:
            return sum(min_size for min_size, _ in opt.values())

        if options:
            try:
                self.unit_composition_options = options
            except Exception:
                pass
            return min(options, key=_total_min)

        try:
            self.unit_composition_options = []
        except Exception:
            pass
        return {}

    def _create_models(self, datasheet, quantity=None):
        models = []
        total_models = 0

        def _select_unit_composition_option(requested_qty: Optional[int]):
            options = getattr(self, "unit_composition_options", None)
            if not isinstance(options, list) or not options:
                return getattr(self, "unit_composition", {})

            def _totals(opt: dict[str, tuple[int, int]]) -> tuple[int, int]:
                min_total = sum(min_size for min_size, _ in opt.values())
                max_total = sum(max_size for _, max_size in opt.values())
                return min_total, max_total

            if requested_qty is None:
                return min(options, key=lambda opt: _totals(opt)[0])

            for opt in options:
                min_total, max_total = _totals(opt)
                if min_total <= requested_qty <= max_total:
                    return opt

            return min(options, key=lambda opt: _totals(opt)[0])

        chosen = _select_unit_composition_option(quantity)
        if isinstance(chosen, dict) and chosen:
            self.unit_composition = chosen

        def _normalize_name(s: str) -> str:
            s = (s or "").replace("\u2019", "'").strip().lower()
            s = re.sub(r"<[^>]+>", " ", s)
            s = re.sub(r"[^a-z0-9\s]", " ", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s

        def _pick_profile_for_model(model_name: str) -> dict:
            """
            Datasheets often have multiple model profiles (e.g. Attack Bike vs Space Marine Bike,
            Exarch vs regular). Unit composition names don't always match profile names 1:1
            (e.g. "Biker Sergeant" uses the "SPACE MARINE BIKE" profile).

            Heuristic: exact/substring match on normalized names; otherwise token overlap with
            light fuzzy matching (biker~bike). Falls back to first profile.
            """
            try:
                profiles = list(getattr(datasheet, "datasheets_models", []) or [])
            except Exception:
                profiles = []
            if not profiles:
                return {}

            want = _normalize_name(model_name)
            want_tokens = set(want.split())

            best = profiles[0]
            best_score = -1

            for prof in profiles:
                pname = _normalize_name(str(prof.get("name", "") or ""))
                if not pname:
                    continue
                if pname == want:
                    return prof
                if pname and (pname in want or want in pname):
                    # Strong match, but keep searching for exact
                    score = 100
                else:
                    p_tokens = set(pname.split())
                    overlap = len(want_tokens & p_tokens)
                    # Fuzzy: treat biker/bikes as matching bike
                    fuzzy = 0
                    if "biker" in want_tokens and "bike" in p_tokens:
                        fuzzy += 1
                    if "bikes" in want_tokens and "bike" in p_tokens:
                        fuzzy += 1
                    if "bike" in want_tokens and "biker" in p_tokens:
                        fuzzy += 1
                    score = overlap + fuzzy

                if score > best_score:
                    best = prof
                    best_score = score

            return best

        def _select_fallback_base_size() -> Optional[str]:
            try:
                profiles = list(getattr(datasheet, "datasheets_models", []) or [])
            except Exception:
                profiles = []
            for prof in profiles:
                try:
                    raw = str(prof.get("base_size", "") or "").strip()
                except Exception:
                    raw = ""
                if raw and not self._is_unknown_base_size(raw):
                    return raw
            return None

        fallback_base_size = _select_fallback_base_size()

        if quantity is None:
            # If no quantity is specified, use the minimum number of models
            quantity = sum(min_size for _, (min_size, _) in self.unit_composition.items())

        # Enforce an overall maximum if provided in datasheet composition metadata.
        try:
            max_cap = getattr(self, "unit_models_maximum", None)
            if isinstance(max_cap, int) and max_cap > 0 and quantity > max_cap:
                print(f" {self.name} requested size {quantity} exceeds maximum {max_cap}; clamping to {max_cap}.")
                quantity = max_cap
        except Exception:
            pass

        for model_name, (min_size, max_size) in self.unit_composition.items():
            if isinstance(max_size, tuple):
                max_size = max_size[1]  # Use the second value if it's a tuple
            model_count = min(max_size, max(min_size, quantity - total_models))
            # Remove 's' from the end of model_name if it's plural
            if model_name.endswith('s'):
                model_name = model_name[:-1]

            profile = _pick_profile_for_model(model_name)
            # Default to first profile if anything is missing
            if not profile:
                profile = datasheet.datasheets_models[0]
            for _ in range(model_count):
                model = Model(
                    name=model_name,
                    movement=self._parse_attribute(profile.get("M", datasheet.datasheets_models[0]["M"])),
                    toughness=self._parse_attribute(profile.get("T", datasheet.datasheets_models[0]["T"])),
                    save=self._parse_attribute(profile.get("Sv", datasheet.datasheets_models[0]["Sv"])),
                    wounds=self._parse_attribute(profile.get("W", datasheet.datasheets_models[0]["W"])),
                    leadership=self._parse_attribute(profile.get("Ld", datasheet.datasheets_models[0]["Ld"])),
                    objective_control=self._parse_attribute(profile.get("OC", datasheet.datasheets_models[0]["OC"])),
                    model_base=self._parse_base_size(
                        self._select_base_size_override(
                            str(profile.get("base_size_descr", datasheet.datasheets_models[0].get("base_size_descr", "")) or ""),
                            model_name,
                        )
                        or profile.get("base_size", datasheet.datasheets_models[0]["base_size"]),
                        fallback_base_size=fallback_base_size,
                        model_name=model_name,
                    ),
                    inv_save=self._parse_attribute(profile.get("inv_sv", datasheet.datasheets_models[0]["inv_sv"])),
                    inv_save_condition=str(profile.get("inv_sv_descr", datasheet.datasheets_models[0].get("inv_sv_descr", "")) or "").lower(),
                    movement_raw=str(profile.get("M", datasheet.datasheets_models[0].get("M", "")) or ""),
                    toughness_raw=str(profile.get("T", datasheet.datasheets_models[0].get("T", "")) or ""),
                    save_raw=str(profile.get("Sv", datasheet.datasheets_models[0].get("Sv", "")) or ""),
                    wounds_raw=str(profile.get("W", datasheet.datasheets_models[0].get("W", "")) or ""),
                    leadership_raw=str(profile.get("Ld", datasheet.datasheets_models[0].get("Ld", "")) or ""),
                    objective_control_raw=str(profile.get("OC", datasheet.datasheets_models[0].get("OC", "")) or ""),
                    inv_save_raw=str(profile.get("inv_sv", datasheet.datasheets_models[0].get("inv_sv", "")) or ""),
                )
                model.set_parent_unit(self)
                models.append(model)
                total_models += 1
            if total_models >= quantity:
                break
        return models

    def _parse_loadout(self, loadout: str, model_name: str = "", return_optional: bool = False) -> List[Wargear] | Tuple[List[Wargear], List[str]]:
        def _norm_item(s: str) -> str:
            s = (s or "").replace("\u2019", "'").lower().strip()
            s = re.sub(r"<[^>]+>", " ", s)
            # remove punctuation but keep hyphens (for items like "grav-gun")
            s = re.sub(r"[^\w\s\-']", " ", s)
            s = s.replace("'", "")  # ignore apostrophes for matching
            s = re.sub(r"\s+", " ", s).strip()
            return s

        entries = (loadout or "").replace('\u2019', "'").lower().split('.')

        def _parse_loadout_quantity(item_name: str) -> Tuple[int, str]:
            if quantity_match := re.match(r"^(\d+) (.*)s$", item_name.strip()):
                return int(quantity_match.group(1)), quantity_match.group(2)
            return 1, item_name.strip()

        starting_wargear = []
        optional_wargear: List[str] = []
        wargear_lookup = {
            _norm_item(getattr(wg, "name", "")): wg
            for wg in (getattr(self, "possible_wargear", []) or [])
            if wg
        }
        wargear_ability_names: dict[str, str] = {}
        for ab in list(getattr(self, "possible_abilities", []) or []):
            try:
                atype = str(getattr(ab, "type", "") or "").lower()
                if "wargear" not in atype:
                    continue
                name = getattr(ab, "name", "") or ""
                if name:
                    wargear_ability_names[_norm_item(name)] = name
            except Exception:
                continue

        def _record_item(item_name: str, quantity: int) -> None:
            norm = _norm_item(item_name)
            if not norm:
                return
            wg = wargear_lookup.get(norm)
            if wg is not None:
                for _ in range(quantity):
                    starting_wargear.append(wg)
                return
            ability_name = wargear_ability_names.get(norm)
            if ability_name:
                for _ in range(quantity):
                    optional_wargear.append(ability_name)
        for entry in entries:
            if not entry:
                continue
            entry = entry.strip()

            if match := re.match(r"^this model is equipped with: (.*)$", entry):
                for item_name in match.group(1).split(";"):
                    quantity, item_name = _parse_loadout_quantity(item_name)
                    _record_item(item_name, quantity)
            elif match := re.match(r"^every model is equipped with: (.*)$", entry):
                for item_name in match.group(1).split(";"):
                    quantity, item_name = _parse_loadout_quantity(item_name)
                    _record_item(item_name, quantity)
            elif match := re.match(r"^(?:the|every) (.*) model is equipped with: (.*)$", entry):
                if model_name and model_name == match.group(1).strip():
                    for item_name in match.group(2).split(";"):
                        quantity, item_name = _parse_loadout_quantity(item_name)
                        _record_item(item_name, quantity)
                else:
                    continue
            elif match := re.match(r"^(?:the|every|a|an) (\D+) is equipped with: (.*)$", entry):
                actors = [match.group(1)]
                if " and " in actors[0]:
                    actors = actors[0].split(" and ")
                for actor in actors:
                    if model_name and model_name == actor.strip():
                        for item_name in match.group(2).split(";"):
                            quantity, item_name = _parse_loadout_quantity(item_name)
                            _record_item(item_name, quantity)
                    else:
                        continue
            elif match := re.match(r"^(\D+) is equipped with: (.*)$", entry):
                actors = [match.group(1)]
                if " and " in actors[0]:
                    actors = actors[0].split(" and ")
                for actor in actors:
                    if model_name and model_name == actor.strip():
                        for item_name in match.group(2).split(";"):
                            quantity, item_name = _parse_loadout_quantity(item_name)
                            _record_item(item_name, quantity)
                    else:
                        continue
            elif match := re.match(r"^this (?:model|unit) is equipped with: nothing$", entry):
                continue
            else:
                print(f"UNKNOWN LOADOUT: {entry}")
        if return_optional:
            return starting_wargear, optional_wargear
        return starting_wargear

    def _parse_wargear(self, datasheet):
        possible_wargear = []
        if hasattr(datasheet, 'datasheets_wargear'):
            for wargear_data in datasheet.datasheets_wargear:
                #print(f"Parsing wargear {wargear_data['name']}")
                if ' \u2013 ' in wargear_data['name']:
                    name, profile = wargear_data['name'].split(' \u2013 ')
                    if name not in [wargear.name for wargear in possible_wargear]:
                        #print(f"Adding wargear {name} with profile {profile}")
                        possible_wargear.append(Wargear(wargear_data))
                    else:
                        for wargear in possible_wargear:
                            if wargear.name == name:
                                #print(f"Adding profile {profile} to wargear {name}")
                                wargear.add_profile(profile, wargear_data)
                                break
                else:
                    #print(f"Adding wargear {wargear_data['name']}")
                    possible_wargear.append(Wargear(wargear_data))
        return possible_wargear

    def _parse_wargear_options(self, datasheet) -> None:
        wargear_options = []
        if hasattr(datasheet, 'datasheets_options'):
            for wargear_option_data in datasheet.datasheets_options:
                wargear_options.append(wargear_option_data["description"])
        self.parse_wargear_options(wargear_options)

    def _parse_abilities(self, datasheet) -> List[Ability]:
        abilities = []
        if hasattr(datasheet, 'datasheets_abilities'):
            for ability in datasheet.datasheets_abilities:
                if 'ability_data' in ability.keys():
                    abilities.append(Ability(ability["ability_data"]["name"],
                                            ability["ability_data"]["faction_id"],
                                            ability["ability_data"]["description"],
                                            ability["type"],
                                            ability["parameter"],
                                            ability["ability_data"]["legend"]))
                else:
                    abilities.append(Ability(ability["name"],
                                            "",
                                            ability["description"],
                                            ability["type"],
                                            ability["parameter"]))
        return abilities

    def parse_wargear_option(self, option: str) -> None:
        return parse_option_string(option, unit_ref=self)

    def parse_wargear_options(self, options: List[str]):
        if len(options) == 1 and options[0].lower() == "none":
            self.wargear_options = {}
            return
        import re

        def _norm(s: str) -> str:
            s = (s or "").replace("\u2019", "'").lower().strip()
            s = re.sub(r"<[^>]+>", " ", s)
            s = re.sub(r"[^\w\s\-']", " ", s)
            s = s.replace("'", "")
            s = re.sub(r"\s+", " ", s).strip()
            return s

        # Parse and store constraint-only lines (they are not selectable options, but affect validity).
        # These are the "Additional / Not implemented" lines like pistol pairing and max ranged weapon limits.
        self._wargear_constraints = getattr(self, "_wargear_constraints", {}) or {}
        self._wargear_constraints.setdefault("max_ranged_weapons", None)
        self._wargear_constraints.setdefault("two_ranged_requires_pistol", False)
        self._wargear_constraints.setdefault("two_ranged_requires_cyclone_pair", False)
        self._wargear_constraints.setdefault("mutex_sets", [])  # list[set[str]]
        self._wargear_constraints.setdefault("max_counts", {})  # dict[str,int]
        self._wargear_constraints.setdefault("model_option_mutex", False)
        self._wargear_constraints.setdefault("forbidden_if_any_option", set())

        cleaned: List[str] = []
        for raw in options:
            text = (raw or "").strip()
            t = _norm(text)
            # Max ranged weapons
            m = re.match(r"each model cannot be equipped with more than (\d+) ranged weapons", t)
            if m:
                self._wargear_constraints["max_ranged_weapons"] = int(m.group(1))
                continue
            # Pistol pairing when 2 ranged
            if "can only be equipped with two ranged weapons if one of them is a pistol" in t:
                self._wargear_constraints["two_ranged_requires_pistol"] = True
                # Also: only have one pistol (already implied by that text)
                continue
            # Cyclone pairing (Wolf Guard Pack Leader in Terminator Armour)
            if "can only be equipped with two ranged weapons if one of them is a cyclone missile launcher" in t:
                self._wargear_constraints["two_ranged_requires_cyclone_pair"] = True
                continue
            # Mutual exclusion: "cannot be equipped with both X and Y"
            m = re.match(r"(?:no model|this model) can(?:not)? be equipped with both (.+?) and (.+?)(?: at the same time)?$", t)
            if m:
                a = _norm(m.group(1))
                b = _norm(m.group(2))
                if a and b:
                    self._wargear_constraints["mutex_sets"].append({a, b})
                continue
            # Max counts: "cannot be equipped with more than 1 X"
            # Hive Tyrant line has multiple clauses; parse all occurrences.
            maxes = list(re.finditer(r"cannot be equipped with more than (\d+) ([\w\s\-']+)", t))
            if maxes:
                for mm in maxes:
                    n = int(mm.group(1))
                    nm = _norm(mm.group(2))
                    if nm:
                        self._wargear_constraints["max_counts"][nm] = min(self._wargear_constraints["max_counts"].get(nm, n), n)
                continue
            # Model option mutex / forbidden weapons for that group
            if "a model can only take one of these options" in t:
                self._wargear_constraints["model_option_mutex"] = True
                # "cannot be equipped with a X or an Y"
                forbid = re.findall(r"cannot be equipped with an? ([\w\s\-']+)", t)
                for f in forbid:
                    ff = _norm(f)
                    if ff:
                        self._wargear_constraints["forbidden_if_any_option"].add(ff)
                continue
            if "cannot be equipped with more than one of these wargear options" in t:
                self._wargear_constraints["model_option_mutex"] = True
                continue

            cleaned.append(text)

        wargear_options = parse_alternate_3(cleaned, self)
        self.wargear_options = wargear_options

    def apply_wargear_option(self, wargear_option: WargearOption):
        """
        Apply a wargear option to the unit.

        IMPORTANT:
        - A wargear option is a *rule* granting allowed additions/replacements. This method applies one chosen
          option outcome to models (used by army-list parsing and any future UI selection).
        - `wargear_option.wargear_to` is a list of possible "choices", each being a list of (qty, item_name) tuples.
        """
        import re
        from warhammer40k_ai.units.wargear import WargearOptionType

        def _norm(s: str) -> str:
            s = (s or "").replace("\u2019", "'").lower().strip()
            s = re.sub(r"<[^>]+>", " ", s)
            s = re.sub(r"[^\w\s\-']", " ", s)
            s = s.replace("'", "")
            s = re.sub(r"\s+", " ", s).strip()
            return s

        def _iter_choice_item_names() -> list[str]:
            out: list[str] = []
            for choice in (wargear_option.wargear_to or []):
                for qty, nm in (choice or []):
                    if nm:
                        out.append(_norm(str(nm)))
            return out

        def _actor_matches_model(actor: str, model_name: str) -> bool:
            a = _norm(actor)
            m = _norm(model_name)
            if not a or not m:
                return False
            if a in ("model", "this model", "unit"):
                return True
            return a == m or a in m or m in a

        def _effective_model_limit_max() -> int:
            """Apply common scaling conditionals (e.g. 'For every 5 models in this unit,...')."""
            max_models = int(getattr(wargear_option.model_quantity, "max", 1) or 1)
            # Scale by "for every N models in this unit"
            for cond in list(getattr(wargear_option, "conditionals", []) or []):
                m = re.search(r"for every\s+(\d+)\s+[\w\s']+\s+in th[ei]s unit", (cond or "").lower())
                if m:
                    try:
                        n = int(m.group(1))
                        if n > 0:
                            max_models = max_models * max(1, (len(self.models) // n))
                    except Exception:
                        pass
            return max_models

        def _conditions_met(model) -> bool:
            # Best-effort: supports common constraint phrases produced by the parser.
            for cond in list(getattr(wargear_option, "conditionals", []) or []):
                cl = (cond or "").lower().strip()
                if cl.startswith("not equipped with "):
                    excluded = _norm(cl.replace("not equipped with ", ""))
                    # Check both currently equipped wargear and already-picked option names
                    try:
                        for wg in getattr(model, "wargear", []) or []:
                            if _norm(getattr(wg, "name", "")) == excluded:
                                return False
                    except Exception:
                        pass
                    try:
                        for ow in getattr(model, "optional_wargear", []) or []:
                            if _norm(ow) == excluded:
                                return False
                    except Exception:
                        pass
                elif cl.startswith("equipped with "):
                    required = _norm(cl.replace("equipped with ", ""))
                    has_req = False
                    for wg in list(getattr(model, "wargear", []) or []):
                        if wg and _norm(getattr(wg, "name", "")) == required:
                            has_req = True
                            break
                    if not has_req:
                        return False
                elif cl.startswith("contains ") and " models" in cl:
                    # "contains 10 models" (unit-level conditional)
                    m = re.match(r"contains\s+(\d+)\s+models", cl)
                    if m:
                        if len(self.models) != int(m.group(1)):
                            return False
                elif cl.startswith("cannot replace "):
                    # This is handled by replacement lock checks, not eligibility.
                    continue
            return True

        def _get_replacement_locks(model) -> set[str]:
            locks = getattr(model, "_wargear_replacement_locks", None)
            if locks is None:
                locks = set()
                setattr(model, "_wargear_replacement_locks", locks)
            return locks

        def _apply_post_locks(model) -> None:
            # Conditionals like "cannot replace lasgun" apply to the model that receives this option.
            locks = _get_replacement_locks(model)
            for cond in list(getattr(wargear_option, "conditionals", []) or []):
                cl = (cond or "").lower().strip()
                if cl.startswith("cannot replace "):
                    locks.add(_norm(cl.replace("cannot replace ", "")))

        def _per_model_mutex_blocked(model) -> bool:
            # If the same model can't take more than one of these options, block if it already has any
            # item from this option's choices.
            conds = " | ".join(list(getattr(wargear_option, "conditionals", []) or [])).lower()
            if ("same model cannot be equipped with more than one of these wargear options" not in conds
                and "you cannot select both of these options for the same model" not in conds):
                return False
            option_items = {_norm(nm) for choice in (getattr(wargear_option, "wargear_to", []) or []) for qty, nm in (choice or []) if nm}
            for wg in list(getattr(model, "wargear", []) or []):
                if wg and _norm(getattr(wg, "name", "")) in option_items:
                    return True
            return False

        def _no_duplicates_in_choices_blocked(model) -> bool:
            conds = " | ".join(list(getattr(wargear_option, "conditionals", []) or [])).lower()
            if "no duplicates in choices" not in conds:
                return False
            allowed = {_norm(nm) for choice in (getattr(wargear_option, "wargear_to", []) or []) for qty, nm in (choice or []) if nm}
            counts = {}
            for wg in list(getattr(model, "wargear", []) or []):
                if wg:
                    n = _norm(getattr(wg, "name", ""))
                    if n in allowed:
                        counts[n] = counts.get(n, 0) + 1
                        if counts[n] > 1:
                            return True
            return False

        def _lock_selected_items(model, selected_names_norm: set[str]) -> None:
            conds = " | ".join(list(getattr(wargear_option, "conditionals", []) or [])).lower()
            if "lock_selected_items" not in conds:
                return
            locks = _get_replacement_locks(model)
            for n in selected_names_norm:
                locks.add(n)

        def _max_per_models_limit() -> tuple[int, int] | None:
            # Parse "to a maximum of X per Y models in this unit"
            for cond in list(getattr(wargear_option, "conditionals", []) or []):
                cl = (cond or "").lower().strip().replace("\u2019", "'")
                m = re.match(r"to a maximum of (\d+) per (\d+) models in this unit", cl)
                if m:
                    return int(m.group(1)), int(m.group(2))
            return None

        def _max_one_per_model() -> bool:
            return any((c or "").lower().strip() == "maximum 1 per model" for c in (getattr(wargear_option, "conditionals", []) or []))

        def _unit_dynamic_cap_for_item(item_norm: str) -> int | None:
            # Handle: "you cannot select the same weapon more than once per unit unless it contains 20 models, ..."
            conds = " | ".join(list(getattr(wargear_option, "conditionals", []) or [])).lower()
            m = re.search(r"you cannot select the same (?:weapon|option) more than once per unit unless it contains (\d+) models, in which case you cannot select the same (?:weapon|option) more than twice per unit", conds)
            if m:
                n = int(m.group(1))
                return 2 if len(self.models) >= n else 1
            return None

        def _unit_unique_cap(item_norm: str) -> int | None:
            conds = " | ".join(list(getattr(wargear_option, "conditionals", []) or [])).lower()
            if "you cannot select the same weapon from this list more than once per unit" in conds:
                return 1
            if "you cannot select the same weapon from this list more than twice per unit" in conds:
                return 2
            return None

        def _unit_count_item(item_norm: str) -> int:
            n = 0
            for m in (self.models or []):
                for wg in list(getattr(m, "wargear", []) or []):
                    if wg and _norm(getattr(wg, "name", "")) == item_norm:
                        n += 1
            return n

        def _find_wargear(item_name: str):
            wanted = _norm(item_name)
            for wg in (getattr(self, "possible_wargear", []) or []):
                if wg and _norm(getattr(wg, "name", "")) == wanted:
                    return wg
            return None

        def _is_ranged_wargear(wg) -> bool:
            try:
                for prof in getattr(wg, "profiles", {}).values():
                    if prof and hasattr(prof, "is_ranged") and prof.is_ranged():
                        return True
            except Exception:
                pass
            return False

        def _is_pistol_wargear(wg) -> bool:
            try:
                for prof in getattr(wg, "profiles", {}).values():
                    if prof and hasattr(prof, "is_pistol") and prof.is_pistol():
                        return True
            except Exception:
                pass
            return False

        def _validate_constraints(model) -> bool:
            c = getattr(self, "_wargear_constraints", {}) or {}
            wargear = list(getattr(model, "wargear", []) or [])

            # Max counts for named items
            max_counts = c.get("max_counts", {}) or {}
            if max_counts:
                counts = {}
                for wg in wargear:
                    if wg:
                        nm = _norm(getattr(wg, "name", ""))
                        counts[nm] = counts.get(nm, 0) + 1
                for nm, mx in max_counts.items():
                    if counts.get(nm, 0) > int(mx):
                        return False

            # Mutual exclusions
            for s in c.get("mutex_sets", []) or []:
                present = 0
                for wg in wargear:
                    if wg and _norm(getattr(wg, "name", "")) in s:
                        present += 1
                        if present > 1:
                            return False

            # Max ranged weapons
            max_r = c.get("max_ranged_weapons")
            if max_r is not None:
                ranged = [wg for wg in wargear if wg and _is_ranged_wargear(wg)]
                if len(ranged) > int(max_r):
                    return False

            # Two ranged requires pistol
            if c.get("two_ranged_requires_pistol"):
                ranged = [wg for wg in wargear if wg and _is_ranged_wargear(wg)]
                if len(ranged) == 2:
                    pistols = [wg for wg in ranged if _is_pistol_wargear(wg)]
                    if len(pistols) != 1:
                        return False
                if len(ranged) > 2:
                    return False

            # Cyclone pairing constraint
            if c.get("two_ranged_requires_cyclone_pair"):
                ranged = [wg for wg in wargear if wg and _is_ranged_wargear(wg)]
                if len(ranged) == 2:
                    names = {_norm(getattr(wg, "name", "")) for wg in ranged if wg}
                    if "cyclone missile launcher" not in names:
                        return False
                    other = (names - {"cyclone missile launcher"})
                    if not other:
                        return False
                    # Allowed partners: storm bolter OR combi-weapon
                    if not (("storm bolter" in other) or ("combi-weapon" in other)):
                        return False
                if len(ranged) > 2:
                    return False

            return True

        def _mark_model_took_any_option(model) -> None:
            try:
                setattr(model, "_took_any_wargear_option", True)
            except Exception:
                pass

        def _model_has_bundle(model, bundle) -> bool:
            """
            bundle: list[(qty, item_name)] describing the items that must exist on the model.
            """
            if not bundle:
                return True
            counts: dict[str, int] = {}
            for wg in list(getattr(model, "wargear", []) or []):
                if not wg:
                    continue
                nm = _norm(getattr(wg, "name", ""))
                counts[nm] = counts.get(nm, 0) + 1
            for qty, nm in bundle:
                want = _norm(nm)
                if counts.get(want, 0) < int(qty):
                    return False
            return True

        def _pick_matching_from_bundle(model):
            """
            wargear_from can represent alternatives (A or B). Pick the first bundle that matches this model.
            Returns None if none match.
            """
            from_bundles = list(getattr(wargear_option, "wargear_from", []) or [])
            if not from_bundles:
                return []
            for bundle in from_bundles:
                if _model_has_bundle(model, bundle):
                    return bundle
            return None

        # Select models eligible for this option
        actor = getattr(wargear_option, "model_name", "") or ""
        eligible_models = [m for m in (self.models or []) if _actor_matches_model(actor, getattr(m, "name", "")) and _conditions_met(m)]
        if not eligible_models:
            return

        # "All ..." semantics: boolean toggle (everyone or no one).
        # Do NOT treat "exactly 1 model" as all-or-none; that's just a single-model pick.
        req_min = int(getattr(getattr(wargear_option, "model_quantity", None), "min", 0) or 0)
        req_max = int(getattr(getattr(wargear_option, "model_quantity", None), "max", 0) or 0)
        cond_blob = " | ".join(list(getattr(wargear_option, "conditionals", []) or [])).lower()
        all_or_none = ("all_or_none" in cond_blob) or (req_min == req_max and req_min > 1 and len(eligible_models) == req_min)

        if all_or_none:
            # Must apply to exactly the required number of models, otherwise none.
            if len(eligible_models) != req_min:
                return
            # For replacements: ensure every model can satisfy a "from" bundle.
            if getattr(wargear_option, "wargear_type", None) == WargearOptionType.REPLACEMENT:
                for m in eligible_models:
                    if _pick_matching_from_bundle(m) is None:
                        return

        # Apply model limit (max)
        max_models = _effective_model_limit_max()
        eligible_models = eligible_models[:max_models]

        # Choose the first "choice" by default (callers can filter options beforehand).
        choices = list(getattr(wargear_option, "wargear_to", []) or [])
        if not choices:
            return
        choice = choices[0]

        # Apply to models
        for model in eligible_models:
            # Global option mutex / forbidden weapons
            c = getattr(self, "_wargear_constraints", {}) or {}
            if c.get("model_option_mutex") and getattr(model, "_took_any_wargear_option", False):
                continue
            forbidden = c.get("forbidden_if_any_option", set()) or set()
            if forbidden:
                if any(_norm(getattr(wg, "name", "")) in forbidden for wg in list(getattr(model, "wargear", []) or []) if wg):
                    continue

            if _per_model_mutex_blocked(model):
                continue
            if _max_one_per_model():
                # If model already has any of the option's choice items, block further selections
                allowed = {_norm(nm) for choice in (getattr(wargear_option, "wargear_to", []) or []) for qty, nm in (choice or []) if nm}
                if any(_norm(getattr(wg, "name", "")) in allowed for wg in list(getattr(model, "wargear", []) or []) if wg):
                    continue
            if _no_duplicates_in_choices_blocked(model):
                continue
            # Replacement: remove wargear_from then add choice items.
            if getattr(wargear_option, "wargear_type", None) == WargearOptionType.REPLACEMENT:
                bundle = _pick_matching_from_bundle(model)
                if bundle is None:
                    # For non-all-or-none options, just skip models that don't match the "from" clause.
                    continue
                # Respect replacement locks (e.g. "that model's lasgun cannot be replaced")
                locks = _get_replacement_locks(model)
                if any(_norm(nm) in locks for qty, nm in bundle):
                    continue
                for qty, nm in bundle:
                    tgt = _norm(nm)
                    removed = 0
                    kept = []
                    for wg in list(getattr(model, "wargear", []) or []):
                        if wg and removed < int(qty) and _norm(getattr(wg, "name", "")) == tgt:
                            removed += 1
                            continue
                        kept.append(wg)
                    model.wargear = kept

            # Add items from the selected choice
            # Support: "item_limit is equal to number of equipped X"
            # Interpreted as "you have N slots equal to count(equipped X); each selection consumes 1 slot".
            remaining_slots = None
            for cond in list(getattr(wargear_option, "conditionals", []) or []):
                cl = (cond or "").lower().strip()
                if cl.startswith("item_limit is equal to number of equipped "):
                    what = _norm(cl.replace("item_limit is equal to number of equipped ", ""))
                    if not what:
                        remaining_slots = 0
                        break
                    cap = sum(
                        1
                        for wg in list(getattr(model, "wargear", []) or [])
                        if wg and _norm(getattr(wg, "name", "")) == what
                    )
                    allowed_items = {
                        _norm(nm)
                        for ch in (getattr(wargear_option, "wargear_to", []) or [])
                        for q, nm in (ch or [])
                        if nm
                    }
                    already_taken = sum(
                        1
                        for wg in list(getattr(model, "wargear", []) or [])
                        if wg and _norm(getattr(wg, "name", "")) in allowed_items
                    )
                    remaining_slots = max(0, int(cap) - int(already_taken))
                    break
            if remaining_slots is not None and remaining_slots <= 0:
                _apply_post_locks(model)
                continue

            for qty, nm in choice:
                cap = _unit_unique_cap(_norm(nm))
                if cap is not None:
                    if _unit_count_item(_norm(nm)) >= cap:
                        continue
                dyn = _unit_dynamic_cap_for_item(_norm(nm))
                if dyn is not None and _unit_count_item(_norm(nm)) >= dyn:
                    continue
                ratio = _max_per_models_limit()
                if ratio is not None:
                    x, y = ratio
                    limit = max(0, (len(self.models) // y) * x)
                    # Cap applies across the unit for any items in this option's choice list
                    allowed = {_norm(nn) for ch in (getattr(wargear_option, "wargear_to", []) or []) for qq, nn in (ch or []) if nn}
                    already = sum(1 for mm in (self.models or []) for wg in list(getattr(mm, "wargear", []) or []) if wg and _norm(getattr(wg, "name", "")) in allowed)
                    if already >= limit:
                        continue
                wg = _find_wargear(nm)
                if wg is None:
                    # Keep as optional note (so UI/printouts can still show it)
                    try:
                        if _norm(nm) == "aspect shrine token":
                            self.add_aspect_shrine_tokens(int(qty) if qty else 1)
                        model.optional_wargear.append(str(nm))
                    except Exception:
                        pass
                    continue
                to_add = int(qty) if qty else 1
                if remaining_slots is not None:
                    to_add = min(to_add, remaining_slots)
                for _ in range(to_add):
                    model.wargear.append(wg)
                    if not _validate_constraints(model):
                        # rollback the last add and stop
                        try:
                            model.wargear.pop()
                        except Exception:
                            pass
                        break
                # Lock selected items if required
                _lock_selected_items(model, {_norm(getattr(wg, "name", ""))} if wg else set())
                if remaining_slots is not None:
                    remaining_slots -= to_add
                    if remaining_slots <= 0:
                        break

            # Apply any post-locks to the model after successfully taking this option
            _apply_post_locks(model)
            _mark_model_took_any_option(model)

        # Wargear selection can activate/deactivate wargear abilities.
        try:
            self._invalidate_ability_cache()
        except Exception:
            pass
        try:
            self._parse_against_attack_characteristic_defensive_rules()
        except Exception:
            pass
        try:
            self._refresh_bearer_unit_common_modifiers()
        except Exception:
            pass
        try:
            self._refresh_bearer_keyword_flags()
        except Exception:
            pass
        try:
            self._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass
        try:
            self._refresh_command_phase_flags()
        except Exception:
            pass
        try:
            self._refresh_fall_back_desperate_escape_flags()
        except Exception:
            pass
        try:
            self._refresh_targeted_stratagem_cp_discount_flags()
        except Exception:
            pass
        try:
            self._refresh_charge_end_mortal_wounds_flags()
        except Exception:
            pass
        try:
            self._refresh_fight_within_3_flags()
        except Exception:
            pass

    def apply_wargear_options(self, wargear_name: Optional[str] = None) -> None:
        """
        Apply wargear options.

        - If `wargear_name` is provided: apply the first option that can yield that wargear item (best-effort).
        - If not provided: apply a conservative default set of non-weapon options (those that only add
          "optional wargear" notes because the items do not exist in `possible_wargear`).
        """
        import re

        def _norm(s: str) -> str:
            s = (s or "").replace("\u2019", "'").lower().strip()
            s = re.sub(r"[^\w\s\-']", " ", s)
            s = s.replace("'", "")
            s = re.sub(r"\s+", " ", s).strip()
            return s

        def _find_wargear(item_name: str):
            wanted = _norm(item_name)
            for wg in (getattr(self, "possible_wargear", []) or []):
                if wg and _norm(getattr(wg, "name", "")) == wanted:
                    return wg
            return None

        if not wargear_name:
            # Default behavior used by some unit construction tests:
            # apply only "non-weapon" options that would otherwise be represented as optional_wargear notes.
            for opt in list(getattr(self, "wargear_options", []) or []):
                choices = list(getattr(opt, "wargear_to", []) or [])
                if not choices:
                    continue
                first = choices[0] or []
                if not first:
                    continue
                # Only auto-apply if *all* items are unknown wargear (i.e. they will land in optional_wargear)
                if all(_find_wargear(nm) is None for qty, nm in first if nm):
                    if any(_norm(nm) == "aspect shrine token" for qty, nm in first if nm):
                        continue
                    self.apply_wargear_option(opt)
            return

        def _norm_variants(s: str) -> set[str]:
            n = _norm(s)
            out = {n}
            if n.endswith("s") and not n.endswith("ss") and len(n) > 3:
                out.add(n[:-1])
            return out

        # Allow disambiguation by exact bundle:
        # - "2 big shootas"
        # - "1 big shoota and 1 rokkit launcha"
        # If user provides qty or multiple items, we require an exact match against a choice.
        spec = (wargear_name or "").strip().lower()
        spec = spec.replace(", ", " and ")
        parts = [p.strip() for p in spec.split(" and ") if p.strip()]
        wanted_tuples = []
        explicit = False
        for p in parts:
            m = re.match(r"^\s*(\d+)\s+(.+?)\s*$", p)
            if m:
                explicit = True
                q = int(m.group(1))
                nm = m.group(2)
            else:
                q = 1
                nm = p
            wanted_tuples.append((q, nm))
        if len(wanted_tuples) > 1:
            explicit = True

        wanted_single = _norm(spec)
        wanted_vars = _norm_variants(spec)

        # STRICT SELECTION RULE:
        # `wargear_name` must uniquely identify exactly one (option, choice) in this unit.
        # If it matches multiple choices/options, we do nothing rather than guessing.
        matches: list[tuple[object, object]] = []
        for opt in list(getattr(self, "wargear_options", []) or []):
            all_choices = list(getattr(opt, "wargear_to", []) or [])
            if not all_choices:
                continue
            for choice in all_choices:
                if not choice:
                    continue
                if explicit:
                    # exact bundle match (order-insensitive)
                    wanted_norm = sorted([(int(q), _norm(nm)) for q, nm in wanted_tuples])
                    choice_norm = sorted([(int(q), _norm(nm)) for q, nm in (choice or []) if nm])
                    if wanted_norm == choice_norm:
                        matches.append((opt, choice))
                else:
                    for qty, nm in (choice or []):
                        nm_vars = _norm_variants(nm)
                        name_match = bool(nm_vars & wanted_vars) or (_norm(nm) == wanted_single)
                        if name_match:
                            matches.append((opt, choice))
                            break

        if not matches:
            # Silent by default (used by UI/other callers), but army-list parsing can request strict behavior.
            strict = False
            try:
                strict = bool(getattr(self, "_strict_wargear_option_resolution", False))
            except Exception:
                strict = False
            if strict:
                raise ValueError(f"Could not resolve wargear option for '{wargear_name}' on unit '{getattr(self, 'name', '<unknown>')}'")
            return

        if len(matches) != 1:
            # Ambiguous (common filler items like "close combat weapon", or shared bundle items like "axe of khorne").
            # Special-case: if there is exactly one ADDITIONAL match and the rest are REPLACEMENT,
            # default to the ADDITIONAL (common "equip X OR replace Y with X" phrasing).
            try:
                from warhammer40k_ai.units.wargear import WargearOptionType
                additional = [(o, c) for (o, c) in matches if getattr(o, "wargear_type", None) == WargearOptionType.ADDITIONAL]
                replacement = [(o, c) for (o, c) in matches if getattr(o, "wargear_type", None) == WargearOptionType.REPLACEMENT]
                if len(additional) == 1 and len(additional) + len(replacement) == len(matches):
                    matches = additional
                else:
                    strict = False
                    try:
                        strict = bool(getattr(self, "_strict_wargear_option_resolution", False))
                    except Exception:
                        strict = False
                    if strict:
                        raise ValueError(
                            f"Ambiguous wargear option '{wargear_name}' for unit '{getattr(self, 'name', '<unknown>')}' "
                            f"(matched {len(matches)} choices)"
                        )
                    return
            except Exception:
                strict = False
                try:
                    strict = bool(getattr(self, "_strict_wargear_option_resolution", False))
                except Exception:
                    strict = False
                if strict:
                    raise ValueError(
                        f"Ambiguous wargear option '{wargear_name}' for unit '{getattr(self, 'name', '<unknown>')}' "
                        f"(matched {len(matches)} choices)"
                    )
                return

        opt, choice = matches[0]
        # Reorder choices to put selected choice first, then apply.
        try:
            choices = list(getattr(opt, "wargear_to", []) or [])
            idx = choices.index(choice)
            if idx != 0:
                choices[0], choices[idx] = choices[idx], choices[0]
                opt.wargear_to = choices
            self.apply_wargear_option(opt)
        except Exception:
            return

    def apply_wargear_options_strict(self, wargear_name: str) -> None:
        """
        Strict variant used by army list parsing: failure to resolve a requested option is an error.
        """
        setattr(self, "_strict_wargear_option_resolution", True)
        try:
            self.apply_wargear_options(wargear_name)
        finally:
            # Always restore default behavior
            try:
                delattr(self, "_strict_wargear_option_resolution")
            except Exception:
                setattr(self, "_strict_wargear_option_resolution", False)

    @staticmethod
    def _norm_wargear_name(s: str) -> str:
        import re
        s = (s or "").replace("\u2019", "'").lower().strip()
        s = re.sub(r"<[^>]+>", " ", s)
        s = re.sub(r"[^\w\s\-']", " ", s)
        s = s.replace("'", "")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def validate_wargear_selection(self) -> None:
        """
        Validate that currently equipped wargear respects parsed wargear constraints.
        This is especially important for army-list parsing, which may directly assign wargear.
        """
        c = getattr(self, "_wargear_constraints", {}) or {}
        if not c:
            return

        def _is_ranged(wg) -> bool:
            return bool(wg) and hasattr(wg, "is_ranged") and wg.is_ranged()

        def _is_pistol(wg) -> bool:
            if not wg:
                return False
            for prof in (getattr(wg, "profiles", {}) or {}).values():
                if prof.is_pistol():
                    return True
            return False

        max_counts = c.get("max_counts", {}) or {}
        mutex_sets = c.get("mutex_sets", []) or []
        max_r = c.get("max_ranged_weapons", None)
        two_ranged_requires_pistol = bool(c.get("two_ranged_requires_pistol", False))
        two_ranged_requires_cyclone_pair = bool(c.get("two_ranged_requires_cyclone_pair", False))

        for model in list(getattr(self, "models", []) or []):
            wargear = [wg for wg in list(getattr(model, "wargear", []) or []) if wg]
            names_norm = [self._norm_wargear_name(getattr(wg, "name", "")) for wg in wargear]

            # Max counts for named items
            if max_counts:
                counts = {}
                for nm in names_norm:
                    counts[nm] = counts.get(nm, 0) + 1
                for nm, mx in max_counts.items():
                    if counts.get(nm, 0) > int(mx):
                        raise ValueError(
                            f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                            f"'{nm}' exceeds max {mx}. Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                        )

            # Mutual exclusions
            for s in mutex_sets:
                present = [nm for nm in names_norm if nm in (s or set())]
                if len(set(present)) > 1:
                    raise ValueError(
                        f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                        f"Mutually exclusive items equipped: {sorted(set(present))}. Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                    )

            # Max ranged weapons
            if max_r is not None:
                ranged = [wg for wg in wargear if _is_ranged(wg)]
                if len(ranged) > int(max_r):
                    raise ValueError(
                        f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                        f"Has {len(ranged)} ranged weapons (max {max_r}). Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                    )

            # Two ranged requires pistol
            if two_ranged_requires_pistol:
                ranged = [wg for wg in wargear if _is_ranged(wg)]
                if len(ranged) == 2:
                    pistols = [wg for wg in ranged if _is_pistol(wg)]
                    if len(pistols) != 1:
                        raise ValueError(
                            f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                            f"Two ranged weapons require exactly one pistol. Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                        )
                if len(ranged) > 2:
                    raise ValueError(
                        f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                        f"Has {len(ranged)} ranged weapons (max 2 under pistol pairing rule). Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                    )

            # Cyclone pairing constraint
            if two_ranged_requires_cyclone_pair:
                ranged = [wg for wg in wargear if _is_ranged(wg)]
                if len(ranged) == 2:
                    names = {self._norm_wargear_name(getattr(wg, "name", "")) for wg in ranged}
                    if "cyclone missile launcher" not in names:
                        raise ValueError(
                            f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                            f"Two ranged weapons require 'cyclone missile launcher'. Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                        )
                    other = (names - {"cyclone missile launcher"})
                    if not other or not (("storm bolter" in other) or ("combi-weapon" in other)):
                        raise ValueError(
                            f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                            f"'cyclone missile launcher' must be paired with 'storm bolter' or 'combi-weapon'. "
                            f"Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                        )
                if len(ranged) > 2:
                    raise ValueError(
                        f"Invalid wargear for unit '{getattr(self, 'name', '<unknown>')}', model '{getattr(model, 'name', '<unknown>')}'. "
                        f"Has {len(ranged)} ranged weapons (max 2 under cyclone pairing rule). Equipped: {[getattr(wg, 'name', '') for wg in wargear]}"
                    )

    def add_wargear(self, wargear: List[Wargear]=[], model_name: str=None) -> None:
        for model_instance in self.models:
            wargear_to_add = []
            optional_wargear = []
            if not wargear:
                parsed = self._parse_loadout(
                    getattr(self._datasheet, 'loadout', []),
                    model_instance.name.lower(),
                    return_optional=True,
                )
                if isinstance(parsed, tuple):
                    wargear_to_add, optional_wargear = parsed
                else:
                    wargear_to_add = parsed
            else:
                wargear_to_add.extend(wargear)
            for wargear_instance in wargear_to_add:
                if model_name:
                    if model_instance.name.lower() == model_name.lower():
                        if wargear_instance:
                            model_instance.wargear.append(wargear_instance.clone())
                else:
                    if wargear_instance:
                        model_instance.wargear.append(wargear_instance.clone())
            if optional_wargear:
                for ow in optional_wargear:
                    try:
                        model_instance.optional_wargear.append(str(ow))
                    except Exception:
                        continue
        if wargear:
            self.validate_wargear_selection()

    def set_parent_army(self, army_ptr) -> None:
        """Set the parent army of the unit."""
        self.parent_army = army_ptr

    def get_parent_army(self) -> Optional['Army']:
        """Get the parent army of the unit."""
        return self.parent_army

    def _publish_unit_event(self, event_name: str, **kwargs) -> None:
        if not event_name:
            return
        if "unit" not in kwargs:
            kwargs["unit"] = self
        army = self.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        game = getattr(player, "game", None) if player is not None else None
        event_system = getattr(game, "event_system", None) if game is not None else None
        if event_system is None:
            return
        try:
            event_system.publish(event_name, **kwargs)
        except Exception:
            pass

    def add_ability(self, ability: Ability, model_name: str=None, quantity: int=1000) -> None:
        """Add ability to the unit."""
        count = 0
        for model in self.models:
            if count >= quantity:
                break
            if model_name:
                if model.name == model_name:
                    model.add_ability(ability)
            else:
                model.add_ability(ability)
            count += 1
        # Invalidate ability cache since abilities changed
        self._invalidate_ability_cache()

    def _invalidate_ability_cache(self) -> None:
        """Invalidate ability cache when unit state changes."""
        if hasattr(self, '_ability_cache'):
            self._ability_cache.clear()

    # Remove a Model from a Unit (e.g., when it dies)
    def remove_model(self, model: Model, fleed: bool = False, game_map: Optional['Map'] = None) -> None:
        assert model in self.models

        # If this is the last bodyguard model in an Attached unit, snapshot its toughness so wound rolls
        # continue to use the bodyguard toughness until the attacking unit finishes resolving attacks.
        try:
            if len(self.models) == 1 and (not bool(getattr(self, "is_leader", False))) and list(getattr(self, "attached_leaders", []) or []):
                self._last_bodyguard_toughness = int(getattr(model, "toughness", getattr(model, "_toughness", 0)))
        except Exception:
            pass

        # Check for Deadly Demise ability before removing the model
        skip_deadly = False
        try:
            skip_deadly = bool(getattr(model, "_skip_deadly_demise_once", False))
        except Exception:
            skip_deadly = False
        if skip_deadly:
            try:
                setattr(model, "_skip_deadly_demise_once", False)
            except Exception:
                pass
        if not fleed and game_map is not None and not skip_deadly:
            self._trigger_deadly_demise(model, game_map)

        # Remove model itself
        self.round_state.num_lost_models_this_round += 1
        self.models_lost.append(model)
        self.models.remove(model)

        # Invalidate ability cache since unit composition changed
        self._invalidate_ability_cache()

        logger.info(f"Unit has {len(self.models)} models left!")
        #if len(self.models) < 1:
        #    if not fleed:
        #        self.callbacks[hook_events.ENEMY_UNIT_KILLED].append(logger.error(self))
        #    self.parent_detachment.removeUnit(self)
        self.update_coherency()
        try:
            self._refresh_bearer_unit_common_modifiers()
        except Exception:
            pass
        try:
            self._refresh_bearer_keyword_flags()
        except Exception:
            pass
        try:
            self._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass

        # Publish unit destroyed event (best-effort). Note: "destroyed" should not
        # trigger for fleeing/removal-type effects.
        if (not fleed) and len(self.models) < 1:
            # If a Leader is destroyed while attached, immediately detach it so the bodyguard
            # no longer counts it for keyword/strength/collision purposes.
            try:
                if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                    self.detach_from_unit()
            except Exception:
                pass

            # If a BODYGUARD in an Attached unit is destroyed but Leaders remain, do NOT separate immediately.
            # Mark pending separation; it will be resolved after the attacking unit finishes resolving attacks.
            try:
                if (not bool(getattr(self, "is_leader", False))) and list(getattr(self, "attached_leaders", []) or []):
                    any_leader_alive = any(len(getattr(l, "models", []) or []) > 0 for l in (getattr(self, "attached_leaders", []) or []))
                    if any_leader_alive:
                        setattr(self, "_pending_leader_separation", True)
                        return
            except Exception:
                pass

            try:
                game = self.get_parent_army().player.game
                game.event_system.publish(
                    "unit_destroyed",
                    unit=self,
                    last_model=model,
                    destroyed_by_model=getattr(self, "_last_destroyed_by_model", None),
                    destroyed_by_unit=getattr(self, "_last_destroyed_by_unit", None),
                    destroyed_by_weapon_profile=getattr(self, "_last_destroyed_by_weapon_profile", None),
                    game_map=game_map,
                )
            except Exception:
                pass

    def _handle_model_destroyed(self, model: Model, game_map: Optional['Map'] = None) -> None:
        """Handle reactive 'on death' mechanics before the model is removed.

        This is invoked from `Model.die()` right before `Unit.remove_model()`.
        """
        if game_map is None:
            return

        # Guard: only once per model (avoid double-trigger if die() is called twice)
        if getattr(model, "_on_death_reactions_resolved", False):
            return
        model._on_death_reactions_resolved = True

        # Publish a generic event hook for UI/agents (best-effort)
        try:
            game = self.get_parent_army().player.game
            game.event_system.publish("model_destroyed_before_removal", unit=self, model=model)
            # Mission scoring hooks (e.g., Fixed Assassination)
            if hasattr(game, "record_model_destroyed"):
                game.record_model_destroyed(model)
        except Exception:
            pass

        # Return-on-death abilities (e.g., Phoenix Gem / "first time destroyed" rules).
        try:
            specs = list(self._get_return_on_death_specs() or [])
        except Exception:
            specs = []
        if specs:
            for spec in specs:
                try:
                    key = str(spec.get("key") or spec.get("name") or "return_on_death").strip().lower()
                except Exception:
                    key = "return_on_death"
                if not key:
                    key = "return_on_death"
                once_key = f"return_on_death:{key}"
                try:
                    already = bool(getattr(model, "has_used_once_per_battle", lambda _k: False)(once_key))
                except Exception:
                    already = False
                if already:
                    continue
                try:
                    game = self.get_parent_army().player.game
                except Exception:
                    game = None
                if game is None:
                    continue
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                pos = None
                try:
                    pos = model.get_location()
                except Exception:
                    pos = None
                if pos is None:
                    try:
                        pos = getattr(self, "position", None)
                    except Exception:
                        pos = None
                if spec.get("skip_deadly_demise"):
                    try:
                        setattr(model, "_skip_deadly_demise_once", True)
                    except Exception:
                        pass
                if hasattr(game, "queue_phoenix_gem_return"):
                    game.queue_phoenix_gem_return(
                        unit=self,
                        model=model,
                        position=pos,
                        phase_name=phase_name,
                        game_map=game_map,
                        spec=spec,
                    )
                    try:
                        label = str(spec.get("name") or "Return on Death")
                        print(f"{label}: {model.name} will attempt to return at end of phase.")
                    except Exception:
                        pass
                try:
                    model.mark_used_once_per_battle(once_key)
                except Exception:
                    pass
                break

        # WORLD EATERS: Total Carnage (Blessings of Khorne) - deferred "fight on death" after attacker finishes attacks.
        # Trigger: a model is destroyed by a MELEE attack, model's unit benefits from Total Carnage, and unit has not fought this phase.
        try:
            # Only if we have map context (needed for fight-on-death targeting)
            if game_map is not None:
                army = self.get_parent_army()
                mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
                game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
                br = int(getattr(game, "turn", 0) or 0) if game is not None else 0

                if mgr is not None and br > 0:
                    # Eligibility: attached unit group qualifies if ANY member has Blessings of Khorne ability
                    qualifies = False
                    try:
                        qualifies = bool(self.get_attached_unit_root().attached_unit_has_blessings_of_khorne())
                    except Exception:
                        qualifies = False

                    if qualifies and mgr.is_blessing_active_for_unit("TOTAL_CARNAGE", self, battle_round=br):
                        # Must not have fought this phase
                        if not bool(getattr(self.round_state, "fought_this_phase", False)):
                            wp = getattr(self, "_last_destroyed_by_weapon_profile", None)
                            is_melee = False
                            try:
                                parent = getattr(wp, "parent_wargear", None)
                                is_melee = bool(parent is not None and parent.is_melee())
                            except Exception:
                                is_melee = False
                            if is_melee:
                                mgr.queue_total_carnage_model(model_obj=model)
        except Exception:
            # Fail-safe: don't break death processing
            pass

        # Temporarily treat the model as "alive" so existing targeting/engagement checks work.
        original_wounds = getattr(model, "_wounds", None)
        try:
            if original_wounds is not None and original_wounds <= 0:
                model._wounds = 1

            # Prefer Fight on Death when engaged; otherwise try Shoot on Death.
            did_fight = False
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict) and sr.get("pain_fight_on_death_2plus"):
                    if not bool(getattr(self.round_state, "fought_this_phase", False)):
                        wp = getattr(self, "_last_destroyed_by_weapon_profile", None)
                        is_melee = False
                        try:
                            parent = getattr(wp, "parent_wargear", None)
                            is_melee = bool(parent is not None and parent.is_melee())
                        except Exception:
                            is_melee = False
                        if is_melee:
                            roll = int(get_roll("D6"))
                            try:
                                from ..utility.event_bus import append_dice
                                pn = self.get_parent_army().player
                                append_dice(pn, f"Mindless Killing Machines roll: {roll} for {self.name}")
                            except Exception:
                                pass
                            if roll >= 2:
                                did_fight = self._try_fight_on_death(model=model, game_map=game_map)
            except Exception:
                pass
            if (not did_fight) and self.has_fight_on_death():
                did_fight = self._try_fight_on_death(model=model, game_map=game_map)

            if (not did_fight) and self.has_shoot_on_death():
                self._try_shoot_on_death(model=model, game_map=game_map)
        finally:
            if original_wounds is not None:
                model._wounds = original_wounds

    def _try_fight_on_death(self, model: Model, game_map: 'Map') -> bool:
        """Attempt to resolve Fight-on-Death for a single destroyed model."""
        if getattr(model, "_fight_on_death_used", False):
            return False

        enemy_units = [u for u in game_map.get_enemy_units(self) if u.is_alive()]
        engaged = [u for u in enemy_units if game_map.is_within_engagement_range(self, u)]
        if not engaged:
            return False

        # Choose the closest engaged unit (edge-to-edge)
        def _closest_dist(enemy_unit: 'Unit') -> float:
            best = float("inf")
            from ..utility.aura_utils import distance_between_models_bases_3d
            for em in enemy_unit.models:
                if not em.is_alive:
                    continue
                best = min(best, float(distance_between_models_bases_3d(model, em)))
            return best

        target_unit = min(engaged, key=_closest_dist)

        melee_profiles = []
        for wargear in getattr(model, "wargear", []) or []:
            try:
                if not wargear.is_melee():
                    continue
            except Exception:
                continue
            if not getattr(wargear, "profiles", None):
                continue
            profile = wargear.profiles.get("default") or next(iter(wargear.profiles.values()))
            melee_profiles.append(profile)

        if not melee_profiles:
            return False

        model._fight_on_death_used = True
        try:
            game = self.get_parent_army().player.game
            game.event_system.publish("fight_on_death_triggered", unit=self, model=model, target=target_unit)
        except Exception:
            pass

        print(f"{model.name} fights on death into {target_unit.name}")
        for profile in melee_profiles:
            try:
                profile.attack(target_unit, model, game_map=game_map)
            except Exception as e:
                print(f"Fight on Death attack error: {e}")

        return True

    def _try_shoot_on_death(self, model: Model, game_map: 'Map') -> bool:
        """Attempt to resolve Shoot-on-Death for a single destroyed model."""
        if getattr(model, "_shoot_on_death_used", False):
            return False

        # Collect one profile per ranged weapon (choose 'default' or the first profile).
        ranged_profiles = []
        for wargear in getattr(model, "wargear", []) or []:
            try:
                if not wargear.is_ranged():
                    continue
            except Exception:
                continue
            if not getattr(wargear, "profiles", None):
                continue
            profile = wargear.profiles.get("default") or next(iter(wargear.profiles.values()))
            ranged_profiles.append(profile)

        if not ranged_profiles:
            return False

        enemy_units = [u for u in game_map.get_enemy_units(self) if u.is_alive()]
        if not enemy_units:
            return False

        # Choose the closest unit that at least one profile can shoot.
        best_target = None
        best_dist = float("inf")
        for enemy_unit in enemy_units:
            for profile in ranged_profiles:
                try:
                    if not self._can_model_shoot_weapon_at_target(model, profile, enemy_unit, game_map):
                        continue
                except Exception:
                    continue
                # compute distance to closest enemy model
                d = float("inf")
                for em in enemy_unit.models:
                    if not em.is_alive:
                        continue
                    from ..utility.aura_utils import distance_between_models_bases_3d
                    d = min(d, float(distance_between_models_bases_3d(model, em)))
                if d < best_dist:
                    best_dist = d
                    best_target = enemy_unit

        if best_target is None:
            return False

        model._shoot_on_death_used = True
        try:
            game = self.get_parent_army().player.game
            game.event_system.publish("shoot_on_death_triggered", unit=self, model=model, target=best_target)
        except Exception:
            pass

        print(f"{model.name} shoots on death into {best_target.name}")
        shots_executed = 0
        attack_context = {"pending_mortal_wounds": {}, "defer_mortal_wounds": True}
        for profile in ranged_profiles:
            try:
                shots_executed += self._execute_weapon_attacks(
                    profile,
                    best_target,
                    [model],
                    game_map,
                    attack_context=attack_context,
                )
            except Exception as e:
                print(f"Shoot on Death attack error: {e}")

        self._resolve_pending_attack_mortal_wounds(attack_context, best_target, game_map=game_map)
        return shots_executed > 0

    def _trigger_deadly_demise(self, dying_model: Model, game_map: 'Map') -> None:
        """Trigger Deadly Demise ability when a model is killed.
        
        Args:
            dying_model: The model that is being killed
            game_map: The game map to find nearby units
        """
        # Check if the unit has Deadly Demise ability
        has_deadly_demise, damage_dice = self.has_deadly_demise()
        if not has_deadly_demise:
            return
        
        print(f"{self.name} has Deadly Demise {damage_dice} - checking for explosion!")
        
        # Roll D6 to see if Deadly Demise triggers
        trigger_roll = get_roll("D6")
        try:
            from ..utility.event_bus import append_dice
            pn = self.get_parent_army().player
            append_dice(pn, f"Deadly Demise trigger: rolled {trigger_roll} (need 6)")
        except Exception:
            pass
        if trigger_roll != 6:
            print(f"Deadly Demise trigger roll: {trigger_roll} (needed 6) - No explosion!")
            return
        
        print(f"Deadly Demise trigger roll: {trigger_roll} - EXPLOSION! ")
        
        # Get the dying model's position
        model_position = dying_model.get_location()
        if not model_position:
            print(f"Cannot determine position of dying model for Deadly Demise")
            return
        
        # Find all units within 6 inches of the dying model
        nearby_units = self._get_units_within_range(model_position, 6.0, game_map)
        
        if not nearby_units:
            print(f"Deadly Demise triggered but no units within 6\" - no damage dealt")
            return
        
        # Apply damage to each nearby unit
        total_damage_dealt = 0
        for target_unit in nearby_units:
            # Roll damage independently for each unit (if it's a dice roll)
            if damage_dice.number > 0:  # It's a dice roll like D3, D6
                damage_amount = damage_dice.roll()
            else:  # It's a fixed number
                damage_amount = damage_dice.modifier
            
            print(f"{target_unit.name} suffers {damage_amount} mortal wounds from Deadly Demise!")
            
            # Apply mortal wounds to the target unit
            models_destroyed = self._apply_mortal_wounds_to_unit(target_unit, damage_amount, game_map=game_map)
            total_damage_dealt += damage_amount
            
            if models_destroyed > 0:
                print(f"Deadly Demise destroyed {models_destroyed} model(s) in {target_unit.name}")
        
        print(f"Deadly Demise complete: {total_damage_dealt} total mortal wounds dealt to {len(nearby_units)} unit(s)")

    def trigger_deadly_demise_manually(self, dying_model: Model, game_map: 'Map') -> None:
        """Manually trigger Deadly Demise for testing or when game context is available.
        
        This method can be called from the UI or game context when a model is killed
        and the game_map is available.
        
        Args:
            dying_model: The model that is being killed
            game_map: The game map to find nearby units
        """
        self._trigger_deadly_demise(dying_model, game_map)

    def _get_units_within_range(self, position: Tuple[float, float, float, float], range_inches: float, game_map: 'Map') -> List['Unit']:
        """Get all units within the specified range of a position.
        
        Args:
            position: (x, y, z, facing) position to check from
            range_inches: Range in inches to check
            game_map: The game map containing all units
            
        Returns:
            List of units within range (excluding the unit containing the position)
        """
        units_within_range = []
        x, y, z = position[0], position[1], position[2]
        
        for unit in game_map.units:
            if unit == self:  # Skip our own unit
                continue
            
            if not unit.is_alive():  # Skip destroyed units
                continue
            
            # Get the closest model in the unit to our position
            closest_distance = float('inf')
            for model in unit.models:
                if not model.is_alive:
                    continue
                model_pos = model.get_location()
                if model_pos:
                    model_distance = get_dist(
                        x - model_pos[0],
                        y - model_pos[1],
                        z - model_pos[2] if len(model_pos) > 2 else 0
                    )
                    closest_distance = min(closest_distance, model_distance)

            if closest_distance == float('inf'):
                continue

            distance = closest_distance
            
            if distance <= range_inches:
                units_within_range.append(unit)
        
        return units_within_range

    def _apply_mortal_wounds_to_unit(
        self,
        target_unit: 'Unit',
        mortal_wound_amount: int,
        game_map: Optional['Map'] = None,
        *,
        is_psychic_attack: bool = False,
        initial_model: Optional['Model'] = None,
        apply_fn: Optional[Callable[['Model'], None]] = None,
        allocation_ctx: Optional[object] = None,
        allow_initial_model_outside_candidates: bool = False,
    ) -> int:
        """Apply mortal wounds to a unit, distributing them among models.

        Args:
            target_unit: The unit to apply mortal wounds to
            mortal_wound_amount: Number of mortal wounds to apply
            initial_model: Optional model to allocate the first mortal wound to (e.g., Precision)
            apply_fn: Optional callback to apply each mortal wound to a model (defaults to Model.take_damage)
            allocation_ctx: Optional DamageAllocationCtx override for UI context
            allow_initial_model_outside_candidates: Allow initial_model even if not in allocation candidates

        Returns:
            Number of models destroyed by the mortal wounds
        """
        models_destroyed = 0
        current_model = None

        try:
            if initial_model is not None and getattr(initial_model, "is_alive", True):
                current_model = initial_model
        except Exception:
            current_model = None

        # Apply mortal wounds one at a time to models in the unit
        for _ in range(mortal_wound_amount):
            if not target_unit.is_alive():
                break  # Unit is destroyed, stop applying wounds

            # Use the standard wound allocation candidate list (handles attached units: bodyguard -> leaders)
            try:
                candidates = target_unit.get_models_for_wound_allocation()
            except Exception:
                candidates = [m for m in (getattr(target_unit, "models", []) or []) if getattr(m, "is_alive", True)]
            if not candidates:
                break

            # Reset current model if it is no longer eligible.
            if current_model is not None:
                try:
                    if not getattr(current_model, "is_alive", True):
                        current_model = None
                    elif current_model not in candidates:
                        if allow_initial_model_outside_candidates:
                            try:
                                all_models = target_unit.get_models_for_collision()
                            except Exception:
                                all_models = list(candidates)
                            if current_model not in all_models:
                                current_model = None
                        else:
                            current_model = None
                except Exception:
                    current_model = None

            if current_model is None:
                # Human UI may choose among eligible models only when rules allow (i.e., no wounded eligible model)
                from ..utility.damage_allocation import DamageAllocationCtx, choose_damage_allocation_model
                try:
                    player = target_unit.get_parent_army().player
                    is_human = self._player_has_local_control(player)
                except Exception:
                    is_human = False
                provider = getattr(game_map, "damage_allocation_provider", None) if game_map is not None else None
                ctx = allocation_ctx or DamageAllocationCtx(reason="Allocate mortal wound", damage_source="mortal")
                current_model = choose_damage_allocation_model(
                    target_unit,
                    candidates,
                    is_human=is_human,
                    provider=provider,
                    ctx=ctx,
                )
                if current_model is None:
                    break

            # Apply the mortal wound
            if callable(apply_fn):
                apply_fn(current_model)
            else:
                current_model.take_damage(
                    1,
                    is_mortal=True,
                    weapon_profile=None,
                    game_map=game_map,
                    is_psychic_attack=is_psychic_attack,
                )

            # Check if the model was destroyed
            if not current_model.is_alive:
                models_destroyed += 1
                current_model = None

        return models_destroyed

    def _resolve_pending_attack_mortal_wounds(
        self,
        attack_context: Optional[dict],
        target_unit: Optional['Unit'],
        game_map: Optional['Map'] = None,
    ) -> None:
        if not isinstance(attack_context, dict) or target_unit is None:
            return
        pending_by_target = attack_context.get("pending_mortal_wounds")
        if not isinstance(pending_by_target, dict):
            return
        from .wargear import WargearProfile
        WargearProfile.resolve_pending_mortal_wounds_for_target(
            pending_by_target, target_unit, game_map=game_map
        )

    def _player_has_local_control(self, player) -> bool:
        if player is None:
            return False
        try:
            if callable(getattr(player, "has_control", None)):
                return bool(player.has_control())
        except Exception:
            pass
        try:
            from ..roster.player import PlayerControl
            return bool(getattr(player, "control", None) == PlayerControl.LOCAL)
        except Exception:
            return False
        return False

    def add_model(self, model: Model) -> None:
        assert model not in self.models
        model.set_parent_unit(self)
        self.models.append(model)
        # Invalidate ability cache since unit composition changed
        self._invalidate_ability_cache()
        self.update_coherency()

    def update_coherency(self) -> None:
        # Coherency thresholds depend on the number of models in the unit.
        # Use alive model count so casualties adjust the requirement correctly.
        alive_count = len([m for m in self.models if getattr(m, 'is_alive', True)])
        if alive_count <= 1:
            self.coherency_distance = 2.0
            self.required_neighbors = 0
        elif alive_count >= 7:
            self.coherency_distance = 2.0
            self.required_neighbors = 2
        else:
            self.coherency_distance = 2.0
            self.required_neighbors = 1

    def initialize_round(self) -> None:
        """Reset round-tracked variables to default state."""
        self.round_state = UnitRoundState()
        # Check status effects expiration (with safe defaults)
        for status_effect in list(getattr(self, "status_effects", []) or []):
            try:
                status_effect.check_expiration(self)
            except Exception:
                # If status effect check fails, just continue
                # This prevents crashes from incomplete status effect implementations
                pass
        
        # Reset reserves arrival flag
        self.arrived_from_reserves_this_turn = False
        # Reset edge-touch Strategic Reserves restriction (only applies on the turn the unit arrives).
        try:
            setattr(self, "_reserves_edge_touch_this_turn", False)
        except Exception:
            pass

        # Reset per-model "counts as having shot via Firing Deck" flags.
        # This is model-scoped (not unit-scoped) to support the core rule that only the selected embarked
        # models count as having shot when their weapons are used via a transport's Firing Deck.
        for m in list(getattr(self, "models", []) or []):
            try:
                setattr(m, "_shot_via_firing_deck_this_round", False)
            except Exception:
                pass

        # Clear any stale firing-deck virtual wargear bookkeeping.
        try:
            self.clear_firing_deck_virtual_wargear()
        except Exception:
            pass

    def is_max_health(self) -> Tuple[bool, Optional[Model]]:
        """
        Check if the unit is at full health.

        Returns:
            Tuple[bool, Optional[Model]]: A tuple containing:
                - A boolean indicating if the unit is at full health
                - The first damaged model found, or None if all models are at full health
        """
        for model in self.models:
            if not model.is_max_health:
                return False, model
        return True, None

    def is_below_half_strength(self) -> bool:
        """
        Check if the unit is below half its starting strength for Battle-Shock purposes.
        
        For multi-model units: Check if current model count is less than half starting count
        For single-model units: Check if current wounds are less than half starting wounds
        
        Returns:
            bool: True if unit is below half strength and should take Battle-Shock tests
        """
        # Attached Leaders are not evaluated separately; the Attached unit is treated as one unit.
        try:
            if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                return False
        except Exception:
            pass

        # Compute effective starting/current strength across attached members (bodyguard + leaders).
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = root.get_attached_unit_members()
        except Exception:
            members = [self]

        starting_models = 0
        current_models = 0
        starting_wounds = 0
        current_wounds = 0

        for u in members:
            try:
                starting_models += int(getattr(u, "starting_model_count", len(getattr(u, "models", []) or [])))
            except Exception:
                starting_models += 0
            try:
                current_models += int(len(getattr(u, "models", []) or []))
            except Exception:
                current_models += 0
            try:
                starting_wounds += int(getattr(u, "starting_total_wounds", 0))
            except Exception:
                pass
            try:
                for m in (getattr(u, "models", []) or []):
                    if getattr(m, "is_alive", True):
                        current_wounds += int(getattr(m, "wounds", 0))
            except Exception:
                pass

        # If destroyed, definitely below half strength
        if current_models <= 0:
            return True

        if starting_models > 1:
            # Multi-model unit: check model count
            return current_models < (starting_models / 2.0)

        # Single-model unit: check wounds
        if starting_wounds <= 0:
            return False
        return current_wounds < (starting_wounds / 2.0)

    def is_below_starting_strength(self) -> bool:
        """
        Check if the unit is Below Starting Strength (distinct from Below Half-strength).

        Rules intent:
        - Multi-model unit: below starting strength if remaining model count < starting model count.
        - Starting Strength of 1 (single-model): below starting strength if the model has fewer wounds remaining
          than its starting wounds.

        Attached Leaders are treated as part of the unit for this check, consistent with other Battle-shock checks.

        Returns:
            bool: True if below starting strength.
        """
        # Attached Leaders are not evaluated separately; the Attached unit is treated as one unit.
        try:
            if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                return False
        except Exception:
            pass

        # Compute effective starting/current strength across attached members (bodyguard + leaders).
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = root.get_attached_unit_members()
        except Exception:
            members = [self]

        starting_models = 0
        current_models = 0
        starting_wounds = 0
        current_wounds = 0

        for u in members:
            try:
                starting_models += int(getattr(u, "starting_model_count", len(getattr(u, "models", []) or [])))
            except Exception:
                starting_models += 0
            try:
                current_models += int(len(getattr(u, "models", []) or []))
            except Exception:
                current_models += 0
            try:
                starting_wounds += int(getattr(u, "starting_total_wounds", 0) or 0)
            except Exception:
                pass
            try:
                for m in (getattr(u, "models", []) or []):
                    if getattr(m, "is_alive", True):
                        current_wounds += int(getattr(m, "wounds", 0) or 0)
            except Exception:
                pass

        # Multi-model unit: model-count based
        if starting_models > 1:
            return current_models < starting_models

        # Starting Strength of 1: wounds-based
        if starting_wounds <= 0:
            return False
        return current_wounds < starting_wounds

    def is_battle_shocked(self) -> bool:
        """
        Check if the unit is currently battle-shocked.
        
        Returns:
            bool: True if the unit has a BattleShockEffect status effect
        """
        return any(isinstance(effect, BattleShockEffect) for effect in list(getattr(self, "status_effects", []) or []))

    def pass_leadership_check(self) -> bool:
        """Perform a Leadership test by rolling 2D6 against the unit's Leadership characteristic.
        
        Returns:
            bool: True if the test is passed, False if failed
        """
        roll_result = None
        dice_rolls = None
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "acts_of_faith", None) if army is not None else None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if mgr is not None and mgr.can_use_act_of_faith(self, game=game):
                roll_result, dice_rolls, _miracle_used = mgr.resolve_roll(
                    self,
                    roll_type="battle-shock",
                    game=game,
                    dice_count=2,
                    die_faces=6,
                )
        except Exception:
            roll_result = None
            dice_rolls = None
        if roll_result is None:
            roll_result = get_roll("2D6")
        leadership_value = self.leadership
        # 10e: lower Leadership is better; you pass if roll <= Ld.
        passed = roll_result <= leadership_value
        
        # Provide detailed feedback
        dice_note = ""
        try:
            if dice_rolls and isinstance(dice_rolls, list):
                dice_note = f" (dice {list(dice_rolls)})"
        except Exception:
            dice_note = ""
        if passed:
            print(f"{self.name} Leadership test: 2D6 rolled {roll_result}{dice_note} vs Ld {leadership_value} - PASSED! ")
        else:
            print(f"{self.name} Leadership test: 2D6 rolled {roll_result}{dice_note} vs Ld {leadership_value} - FAILED! ")
        
        return passed

    def pass_leadership_check_for_model(self, model: Optional['Model']) -> bool:
        """Perform a Leadership test for a specific model (2D6 vs that model's Leadership characteristic)."""
        if model is None:
            return False
        roll_result = None
        dice_rolls = None
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "acts_of_faith", None) if army is not None else None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if mgr is not None and mgr.can_use_act_of_faith(self, game=game):
                roll_result, dice_rolls, _miracle_used = mgr.resolve_roll(
                    self,
                    roll_type="battle-shock",
                    game=game,
                    dice_count=2,
                    die_faces=6,
                )
        except Exception:
            roll_result = None
            dice_rolls = None
        if roll_result is None:
            roll_result = get_roll("2D6")
        try:
            leadership_value = int(getattr(model, "leadership", self.leadership))
        except Exception:
            leadership_value = self.leadership
        passed = roll_result <= leadership_value

        dice_note = ""
        try:
            if dice_rolls and isinstance(dice_rolls, list):
                dice_note = f" (dice {list(dice_rolls)})"
        except Exception:
            dice_note = ""
        model_name = getattr(model, "name", "Model")
        if passed:
            print(f"{model_name} Leadership test: 2D6 rolled {roll_result}{dice_note} vs Ld {leadership_value} - PASSED! ")
        else:
            print(f"{model_name} Leadership test: 2D6 rolled {roll_result}{dice_note} vs Ld {leadership_value} - FAILED! ")

        return passed

    @property
    def is_epic_hero(self) -> bool:
        return "Epic Hero" in self.keywords

    @property
    def is_battleline(self) -> bool:
        return "Battleline" in self.keywords

    @property
    def is_dedicated_transport(self) -> bool:
        return "Dedicated Transport" in self.keywords

    @property
    def is_transport(self) -> bool:
        return "Transport" in self.keywords

    @property
    def is_embarked(self) -> bool:
        return self.embarked_in is not None

    def _parse_transport_capacity(self, datasheet) -> int:
        """
        Best-effort parsing for 10th edition Transport Capacity.

        Wahapedia data typically stores this as an ability entry on the datasheet (often "Transport"),
        with descriptions like "Transport Capacity: 12" or "Transport 12".
        """
        # Prefer the explicit `datasheet.transport` field (Wahapedia)
        try:
            t = str(getattr(datasheet, "transport", "") or "").strip()
            if t:
                m = re.search(r"transport\s+capacity\s+(?:of\s+)?(\d+)", t, flags=re.IGNORECASE)
                if m:
                    return int(m.group(1))
                m = re.search(r"transport\s*capacity\s*[:\-]\s*(\d+)", t, flags=re.IGNORECASE)
                if m:
                    return int(m.group(1))
        except Exception:
            pass

        try:
            keywords = getattr(datasheet, "keywords", []) or []
            if "Transport" not in keywords and "Dedicated Transport" not in keywords:
                return 0
        except Exception:
            # If keywords can't be read, fall back to parsing abilities only.
            pass

        candidates: List[str] = []
        try:
            if hasattr(datasheet, 'datasheets_abilities'):
                for a in datasheet.datasheets_abilities:
                    # Prefer raw description/name if present
                    n = str(a.get("name", "") or "")
                    d = str(a.get("description", "") or "")
                    if d:
                        candidates.append(f"{n} {d}".strip())
                    elif n:
                        candidates.append(n.strip())
        except Exception:
            candidates = []

        text = " \n ".join([c for c in candidates if c])
        if not text:
            return 0

        # Common patterns across sources
        patterns = [
            r"transport\s*capacity\s*[:\-]\s*(\d+)",
            r"\btransport\s*\(?\s*(\d+)\s*\)?\b",
        ]
        for pat in patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    continue
        return 0

    def _parse_transport_restrictions(self, datasheet) -> Tuple[set[str], set[str]]:
        """
        Parse best-effort keyword restrictions from the datasheet's `transport` text.

        Example:
        "This model has a transport capacity of 12 HERETIC ASTARTES INFANTRY models.
         It cannot transport TERMINATOR, JUMP PACK, OBLITERATOR or POSSESSED models."
        """
        required: set[str] = set()
        excluded: set[str] = set()

        try:
            text = str(getattr(datasheet, "transport", "") or "")
        except Exception:
            text = ""
        if not text:
            return required, excluded

        # Required clause between capacity number and "models"
        m = re.search(r"transport\s+capacity\s+(?:of\s+)?\d+\s+(.+?)\s+models?\b", text, flags=re.IGNORECASE)
        req_clause = (m.group(1) or "").strip() if m else ""
        if req_clause:
            known: List[str] = []
            try:
                known.extend(list(getattr(datasheet, "keywords", []) or []))
            except Exception:
                pass
            try:
                known.extend(list(getattr(datasheet, "faction_keywords", []) or []))
            except Exception:
                pass
            # Common keywords seen in transport restrictions
            known.extend(["Infantry", "Beast", "Mounted", "Jump Pack", "Terminator", "Possessed", "Obliterator", "Gravis", "Phobos"])

            upper_clause = req_clause.upper()
            for kw in known:
                try:
                    if re.search(rf"(?<![A-Z0-9]){re.escape(str(kw).upper())}(?![A-Z0-9])", upper_clause):
                        required.add(str(kw))
                except Exception:
                    continue

        # Excluded clause: "cannot transport ..."
        m2 = re.search(r"cannot\s+transport\s+(.+?)(?:\.\s*|$)", text, flags=re.IGNORECASE)
        excl_clause = (m2.group(1) or "").strip() if m2 else ""
        if excl_clause:
            excl_clause = re.sub(r"\bmodels?\b", "", excl_clause, flags=re.IGNORECASE).strip()
            parts = re.split(r"\s*,\s*|\s+or\s+|\s+and\s+", excl_clause, flags=re.IGNORECASE)
            for p in parts:
                token = (p or "").strip()
                if not token:
                    continue
                excluded.add(token.title() if token.isupper() else token)

        return required, excluded

    def get_transport_slots_required(self) -> int:
        """How many transport 'slots' this unit uses. Default: 1 per alive model."""
        # Datasheets can have non-1 model slot costs (e.g. Terminators, Jump Packs), but we don't
        # have a unified schema for that yet. Keep this conservative and overridable.
        # Attached leader units should never be embarked separately; count them via the bodyguard.
        try:
            if bool(getattr(self, "is_attached_leader", False)):
                return 0
        except Exception:
            pass
        # Imperial Agents Kill Team: specific models count as 2 slots.
        has_kill_team = False
        try:
            root = self.get_attached_unit_root()
            if root is not None and hasattr(root, "attached_unit_has_kill_team"):
                has_kill_team = bool(root.attached_unit_has_kill_team())
        except Exception:
            has_kill_team = False
        if has_kill_team:
            try:
                models = self.get_models_for_collision()
            except Exception:
                models = self.models
            total = 0
            for m in (models or []):
                try:
                    if not getattr(m, "is_alive", False):
                        continue
                except Exception:
                    pass
                total += 2 if self._kill_team_model_uses_two_transport_slots(m) else 1
            return int(total)
        try:
            # If this unit has attached leaders, include their models for capacity.
            try:
                models = self.get_models_for_collision()
            except Exception:
                models = self.models
            return sum(1 for m in models if getattr(m, "is_alive", False))
        except Exception:
            return len(self.models)

    def _kill_team_model_uses_two_transport_slots(self, model: Model) -> bool:
        name = str(getattr(model, "name", "") or "").lower()
        if not name:
            return False
        tokens = ("terminator", "outrider", "biker", "jump pack", "jump-pack")
        return any(tok in name for tok in tokens)

    @property
    def transport_slots_used(self) -> int:
        try:
            return sum(u.get_transport_slots_required() for u in (self.transport_passengers or []) if u and u.is_alive())
        except Exception:
            return 0

    @property
    def transport_slots_remaining(self) -> int:
        return max(0, int(self.transport_capacity or 0) - int(self.transport_slots_used or 0))

    def can_transport(self, passenger_unit: 'Unit') -> bool:
        """Core eligibility + capacity check (datasheet-specific restrictions are best-effort)."""
        if passenger_unit is None:
            return False
        if passenger_unit == self:
            return False
        if not self.is_transport:
            return False
        if not self.is_alive():
            return False
        if passenger_unit.is_embarked:
            return False
        # Must be a friendly unit
        try:
            if self.get_parent_army() is None or passenger_unit.get_parent_army() is None:
                return False
            if self.get_parent_army() != passenger_unit.get_parent_army():
                return False
        except Exception:
            return False
        # Datasheet-specific restrictions (from Wahapedia `datasheet.transport` field when present)
        req = getattr(self, "transport_required_keywords", set()) or set()
        excl = getattr(self, "transport_excluded_keywords", set()) or set()
        if req:
            for kw in req:
                if not passenger_unit.has_any_keyword(str(kw)):
                    return False
        else:
            # Default core restriction: transports carry Infantry (unless specified otherwise)
            if not passenger_unit.is_infantry:
                return False
        if excl:
            for kw in excl:
                if passenger_unit.has_any_keyword(str(kw)):
                    return False
        # Capacity
        needed = passenger_unit.get_transport_slots_required()
        if needed <= 0:
            return False
        if self.transport_capacity <= 0:
            return False
        return (self.transport_slots_used + needed) <= self.transport_capacity

    def add_passenger(self, passenger_unit: 'Unit', game_map: 'Map') -> bool:
        """Embark bookkeeping. Removes passenger from the map."""
        if game_map is None:
            raise RuntimeError("Embark requires an active game map.")
        if not self.can_transport(passenger_unit):
            return False
        if passenger_unit in self.transport_passengers:
            return True
        self.transport_passengers.append(passenger_unit)
        passenger_unit.embarked_in = self
        passenger_unit.round_state.embarked_this_round = True
        # If passenger is an attached-unit root, mark attached leaders as embarked too.
        for leader in list(getattr(passenger_unit, "attached_leaders", []) or []):
            if leader is None:
                continue
            leader.embarked_in = self
            leader.round_state.embarked_this_round = True
            if leader in game_map.units:
                game_map.units.remove(leader)
            leader.position = None
            publish_fn = getattr(leader, "_publish_unit_event", None)
            if callable(publish_fn):
                publish_fn("unit_embarked", unit=leader, transport_unit=self)
                publish_fn("unit_state_changed", unit=leader, reason="embarked", transport_unit=self)
        # Remove from battlefield representation
        if passenger_unit in game_map.units:
            game_map.units.remove(passenger_unit)
        # Clear a concrete battlefield position while embarked
        passenger_unit.position = None
        passenger_unit._publish_unit_event("unit_embarked", unit=passenger_unit, transport_unit=self)
        passenger_unit._publish_unit_event("unit_state_changed", unit=passenger_unit, reason="embarked", transport_unit=self)
        return True

    def remove_passenger(self, passenger_unit: 'Unit') -> None:
        if passenger_unit in self.transport_passengers:
            self.transport_passengers.remove(passenger_unit)
        if getattr(passenger_unit, "embarked_in", None) == self:
            passenger_unit.embarked_in = None
        # Clear embarked state for attached leaders as well.
        for leader in list(getattr(passenger_unit, "attached_leaders", []) or []):
            if leader is None:
                continue
            if getattr(leader, "embarked_in", None) == self:
                leader.embarked_in = None
            publish_fn = getattr(leader, "_publish_unit_event", None)
            if callable(publish_fn):
                publish_fn("unit_disembarked", unit=leader, transport_unit=self)
                publish_fn("unit_state_changed", unit=leader, reason="disembarked", transport_unit=self)
        passenger_unit._publish_unit_event("unit_disembarked", unit=passenger_unit, transport_unit=self)
        passenger_unit._publish_unit_event("unit_state_changed", unit=passenger_unit, reason="disembarked", transport_unit=self)

    @property
    def is_leader(self) -> bool:
        try:
            return len(self.can_be_attached_to) > 0
        except Exception:
            return False

    @property
    def is_attached_leader(self) -> bool:
        """True if this Leader is currently attached to a Bodyguard unit."""
        return bool(self.is_leader and getattr(self, "attached_to", None) is not None)

    def get_datasheet_id(self) -> Optional[str]:
        try:
            return getattr(self._datasheet, "id", None)
        except Exception:
            return None

    def get_attached_unit_root(self) -> 'Unit':
        """Return the 'root' unit for this attached unit group (Bodyguard if attached, else self)."""
        if self.is_leader and getattr(self, "attached_to", None) is not None:
            return self.attached_to
        return self

    def get_attached_unit_members(self) -> List['Unit']:
        """Return all Unit objects that move/deploy/embark together as one Attached unit."""
        root = self.get_attached_unit_root()
        try:
            leaders = list(getattr(root, "attached_leaders", []) or [])
        except Exception:
            leaders = []
        # Root first, then leaders
        return [root] + [u for u in leaders if u is not None]

    def get_attached_unit_models(self) -> List['Model']:
        """Flatten models across the attached unit members (bodyguard + leaders)."""
        models: List['Model'] = []
        for u in self.get_attached_unit_members():
            try:
                models.extend(list(getattr(u, "models", []) or []))
            except Exception:
                continue
        return models

    def get_kill_team_majority_toughness(self) -> Optional[int]:
        """
        Return the majority Toughness across models in this attached unit.
        If tied, return the highest Toughness.
        """
        try:
            models = list(self.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(self, "models", []) or [])
        if not models:
            return None
        counts: dict[int, int] = {}
        for m in models:
            try:
                if not getattr(m, "is_alive", False):
                    continue
            except Exception:
                pass
            try:
                t_val = int(getattr(m, "toughness", getattr(m, "_toughness", 0)) or 0)
            except Exception:
                continue
            if t_val <= 0:
                continue
            counts[t_val] = counts.get(t_val, 0) + 1
        if not counts:
            return None
        max_count = max(counts.values())
        tied = [t for (t, c) in counts.items() if c == max_count]
        return max(tied) if tied else None

    def get_models_for_rendering(self) -> List['Model']:
        """Models used for battlefield rendering/hover detection (include attached Leaders)."""
        root = self.get_attached_unit_root()
        # If called on a Leader that's attached, render is handled by the bodyguard root.
        if root is not self:
            try:
                return root.get_models_for_rendering()
            except Exception:
                return list(getattr(root, "models", []) or [])
        return self.get_attached_unit_models()

    def get_models_for_collision(self) -> List['Model']:
        """Models used for collision/pathfinding/LOS checks (include attached Leaders)."""
        root = self.get_attached_unit_root()
        if root is not self:
            try:
                return root.get_models_for_collision()
            except Exception:
                return list(getattr(root, "models", []) or [])
        return self.get_attached_unit_models()

    def is_within_objective_range(self, objective_point) -> bool:
        """Return True if any alive model in this unit is within objective control range."""
        if objective_point is None:
            return False
        try:
            if not self.is_alive() or not getattr(self, "deployed", False):
                return False
        except Exception:
            return False
        try:
            if bool(getattr(self, "is_embarked", False)) or self.is_in_reserves():
                return False
        except Exception:
            pass
        try:
            models = list(self.get_models_for_collision() or [])
        except Exception:
            models = list(getattr(self, "models", []) or [])
        models = [m for m in models if bool(getattr(m, "is_alive", True))]
        if not models:
            return False
        try:
            from shapely.geometry import Point as _ShPoint
            area = _ShPoint(objective_point.x, objective_point.y).buffer(
                float(getattr(objective_point, "control_radius", 0.0) or 0.0)
            )
        except Exception:
            area = None
        for model in models:
            try:
                if area is not None:
                    base = model.model_base.get_base_shape()
                    if base.intersects(area):
                        return True
            except Exception:
                pass
            try:
                pos = model.get_location()
            except Exception:
                pos = None
            if not pos:
                continue
            try:
                dx = float(pos[0]) - float(getattr(objective_point, "x", 0.0))
                dy = float(pos[1]) - float(getattr(objective_point, "y", 0.0))
                radius = float(getattr(objective_point, "control_radius", 0.0) or 0.0)
                base_r = float(getattr(model.model_base, "get_radius", lambda: 1.0)())
                if (dx * dx + dy * dy) ** 0.5 <= (radius + base_r):
                    return True
            except Exception:
                continue
        return False

    def get_models_for_wound_allocation(self) -> List['Model']:
        """
        Models eligible to be allocated wounds for this unit right now.

        For Attached units:
        - While any bodyguard models remain, allocate to bodyguards only.
        - Once bodyguards are gone (but separation is pending until the end of an attack sequence),
          allocate to the attached leaders' models.
        """
        # If this is an attached Leader, allocation is handled by the bodyguard unit.
        try:
            if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                return []
        except Exception:
            pass

        # Bodyguard models first
        bodyguards = list(getattr(self, "models", []) or [])
        bodyguards_alive = [m for m in bodyguards if getattr(m, "is_alive", True)]
        if bodyguards_alive:
            return bodyguards_alive

        # If no bodyguards remain, allocate to leader models (if any)
        leaders_models: list['Model'] = []
        try:
            for l in list(getattr(self, "attached_leaders", []) or []):
                for m in (getattr(l, "models", []) or []):
                    if getattr(m, "is_alive", True):
                        leaders_models.append(m)
        except Exception:
            pass
        return leaders_models

    def get_effective_keywords(self) -> List[str]:
        """Effective keywords for rules checks while attached (union of all members)."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = root.get_attached_unit_members()
        except Exception:
            members = [self]
        kws: list[str] = []
        seen: set[str] = set()
        for u in members:
            try:
                hover_active = bool(getattr(u, "hover_mode", False))
                for k in (getattr(u, "keywords", []) or []):
                    ks = str(k)
                    lk = ks.lower()
                    if hover_active and lk == "aircraft":
                        continue
                    if lk in seen:
                        continue
                    seen.add(lk)
                    kws.append(ks)
                sr = getattr(u, "special_rules", None)
                if isinstance(sr, dict):
                    extra = list(sr.get("ability_added_keywords", []) or [])
                else:
                    extra = []
                for k in extra:
                    ks = str(k)
                    lk = ks.lower()
                    if lk in seen:
                        continue
                    seen.add(lk)
                    kws.append(ks)
            except Exception:
                continue
        return kws

    def get_effective_faction_keywords(self) -> List[str]:
        """Effective faction keywords while attached (union of all members)."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = root.get_attached_unit_members()
        except Exception:
            members = [self]
        kws: list[str] = []
        seen: set[str] = set()
        for u in members:
            try:
                disciple_active = False
                try:
                    if u._disciple_of_khorne_active(bodyguard=root):
                        disciple_active = True
                except Exception:
                    disciple_active = False
                for k in (getattr(u, "faction_keywords", []) or []):
                    ks = str(k)
                    lk = ks.lower()
                    if disciple_active and lk == "world eaters":
                        continue
                    if lk in seen:
                        continue
                    seen.add(lk)
                    kws.append(ks)
                if disciple_active and "blood legions" not in seen:
                    seen.add("blood legions")
                    kws.append("Blood Legions")
            except Exception:
                continue
        return kws

    def max_attached_leaders(self) -> int:
        """
        Default 10e: one Leader per Bodyguard unit.
        Some datasheets allow two Leaders; we detect common phrasing in abilities as a best-effort.
        """
        # Leaders can't have leaders attached "to" them in core rules; treat as 0/1 only on bodyguard.
        try:
            if self.is_leader:
                return 0
        except Exception:
            pass
        max_leaders = 1
        try:
            for ab in getattr(self, "possible_abilities", []) or []:
                text = (getattr(ab, "description", "") or "").lower()
                if ("up to 2 leaders" in text) or ("up to two leaders" in text):
                    max_leaders = 2
                    break
                if ("can be attached to this unit even if another leader is already attached" in text):
                    max_leaders = 2
                    break
        except Exception:
            pass
        return max_leaders

    def _normalize_attached_unit_name(self, text: str) -> str:
        raw = html.unescape(str(text or ""))
        raw = raw.replace("\u2019", "'").replace("\u2018", "'")
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"[^a-z0-9]+", " ", raw.lower())
        return re.sub(r"\s+", " ", raw).strip()

    def _leader_can_attach_to_unit_name(self, unit_name: str) -> bool:
        target = self._normalize_attached_unit_name(unit_name)
        if not target:
            return False
        names = getattr(self, "can_be_attached_to_names", []) or []
        for name in names:
            if self._normalize_attached_unit_name(name) == target:
                return True
        army = self.get_parent_army()
        if army is None:
            return False
        allowed = set(getattr(self, "can_be_attached_to", []) or [])
        for unit in list(getattr(army, "units", []) or []):
            try:
                dsid = unit.get_datasheet_id()
            except Exception:
                dsid = None
            if not dsid or dsid not in allowed:
                continue
            if self._normalize_attached_unit_name(getattr(unit, "name", "")) == target:
                return True
        return False

    def _parse_attached_unit_rule(self, text: str) -> tuple[list[str], list[str], list[str]]:
        cleaned = html.unescape(str(text or ""))
        cleaned = cleaned.replace("\u2019", "'").replace("\u2018", "'")
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            return [], [], []

        match = re.search(
            r"if a (.+?) (?:model|unit) from your army.*?can be attached to (.+)",
            cleaned,
            flags=re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r"if a (.+?) from your army.*?can be attached to (.+)",
                cleaned,
                flags=re.IGNORECASE,
            )
        if not match:
            return [], [], []

        leader_clause = match.group(1)
        base_clause = match.group(2)

        base_clause = re.split(r"\bit can\b", base_clause, maxsplit=1, flags=re.IGNORECASE)[0]
        base_clause = base_clause.split(".", 1)[0].strip()
        base_names: list[str] = []
        for part in re.split(r"\bor\b", base_clause, flags=re.IGNORECASE):
            part = part.strip(" ,;.")
            part = re.sub(r"^(?:an?|the)\s+", "", part, flags=re.IGNORECASE)
            part = re.sub(r"\bunit\b\s*$", "", part, flags=re.IGNORECASE)
            part = part.strip(" ,;.")
            if part:
                base_names.append(part)

        excluded: list[str] = []
        excl_match = re.search(r"excluding\s+([^)]+)", leader_clause, flags=re.IGNORECASE)
        if excl_match:
            excl_clause = excl_match.group(1)
            excluded = [
                token.strip().upper()
                for token in re.split(r"\bor\b|\band\b|,", excl_clause, flags=re.IGNORECASE)
                if token.strip()
            ]
            leader_clause = leader_clause[:excl_match.start()].strip()

        leader_clause = re.sub(r"\bunit\b|\bmodel\b", "", leader_clause, flags=re.IGNORECASE)
        leader_clause = leader_clause.replace("(", " ").replace(")", " ")
        leader_clause = re.sub(r"\s+", " ", leader_clause).strip()
        leader_keywords = [
            token.strip().upper()
            for token in re.split(r"\bor\b|\band\b|,", leader_clause, flags=re.IGNORECASE)
            if token.strip()
        ]

        return leader_keywords, base_names, excluded

    def _can_attach_via_attached_unit_rule(self, bodyguard: "Unit") -> bool:
        if bodyguard is None:
            return False
        abilities = list(getattr(bodyguard, "possible_abilities", []) or [])
        for ab in abilities:
            try:
                name = ab if isinstance(ab, str) else getattr(ab, "name", "")
            except Exception:
                name = ""
            if "attached unit" not in str(name or "").lower():
                continue
            try:
                desc = ab if isinstance(ab, str) else getattr(ab, "description", "")
            except Exception:
                desc = ""
            leader_keywords, base_names, excluded = self._parse_attached_unit_rule(desc)
            if not base_names or not leader_keywords:
                continue
            if excluded and any(self.has_any_keyword(k) for k in excluded):
                continue
            if not any(self.has_any_keyword(k) for k in leader_keywords):
                continue
            for base_name in base_names:
                if self._leader_can_attach_to_unit_name(base_name):
                    return True
        return False

    def can_attach_to(self, bodyguard: 'Unit') -> bool:
        """Validate basic 10e attachment eligibility using Wahapedia leader linkage data."""
        if not self.is_leader:
            return False
        if bodyguard is None or bodyguard is self:
            return False
        # Same army
        try:
            if self.get_parent_army() is None or bodyguard.get_parent_army() is None:
                return False
            if self.get_parent_army() != bodyguard.get_parent_army():
                return False
        except Exception:
            return False
        # Can't attach to another leader unit
        try:
            if bodyguard.is_leader:
                return False
        except Exception:
            pass
        # Disciple of Khorne: Lord on Juggernaut can attach to Bloodcrushers/Flesh Hounds.
        try:
            if self._disciple_of_khorne_can_attach_to(bodyguard):
                return True
        except Exception:
            pass
        # Bodyguard datasheet id must be in leader's allowed attached_to list (IDs)
        allowed = getattr(self, "can_be_attached_to", []) or []
        try:
            bodyguard_id = bodyguard.get_datasheet_id()
        except Exception:
            bodyguard_id = None
        if not bodyguard_id:
            return False
        if bodyguard_id in allowed:
            return True
        return self._can_attach_via_attached_unit_rule(bodyguard)

    def attach_to_unit(self, bodyguard: 'Unit') -> None:
        """Attach this Leader to a Bodyguard unit (Declare Battle Formations)."""
        if not self.is_leader:
            raise ValueError(f"Unit '{self.name}' is not a Leader and cannot be attached.")
        if not self.can_attach_to(bodyguard):
            raise ValueError(f"Leader '{self.name}' cannot be attached to '{getattr(bodyguard, 'name', 'Unknown')}'.")
        # Enforce per-bodyguard leader limit
        max_leaders = bodyguard.max_attached_leaders()
        if max_leaders <= 0:
            raise ValueError(f"Unit '{bodyguard.name}' cannot have Leaders attached.")
        try:
            current = list(getattr(bodyguard, "attached_leaders", []) or [])
        except Exception:
            current = []
        # If already attached to this unit, no-op
        if self in current and getattr(self, "attached_to", None) is bodyguard:
            return
        if len(current) >= max_leaders:
            raise ValueError(f"Unit '{bodyguard.name}' already has the maximum number of Leaders attached ({max_leaders}).")
        # Detach from any prior bodyguard first
        if getattr(self, "attached_to", None) is not None and getattr(self, "attached_to", None) is not bodyguard:
            self.detach_from_unit()
        # Attach
        self.attached_to = bodyguard
        if self not in current:
            current.append(self)
        bodyguard.attached_leaders = current
        try:
            self._apply_attached_possessed_formation_bonus(bodyguard)
        except Exception:
            pass
        # Attachment status affects leading-only abilities; refresh caches/rules.
        try:
            self._invalidate_ability_cache()
        except Exception:
            pass
        try:
            bodyguard._invalidate_ability_cache()
        except Exception:
            pass
        try:
            self._parse_against_attack_characteristic_defensive_rules()
        except Exception:
            pass
        try:
            bodyguard._parse_against_attack_characteristic_defensive_rules()
        except Exception:
            pass
        try:
            self._refresh_bearer_unit_common_modifiers()
        except Exception:
            pass
        try:
            bodyguard._refresh_bearer_unit_common_modifiers()
        except Exception:
            pass
        try:
            self._refresh_bearer_keyword_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_bearer_keyword_flags()
        except Exception:
            pass
        try:
            self._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass
        try:
            self._refresh_command_phase_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_command_phase_flags()
        except Exception:
            pass
        try:
            self._refresh_fall_back_desperate_escape_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_fall_back_desperate_escape_flags()
        except Exception:
            pass
        try:
            self._refresh_targeted_stratagem_cp_discount_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_targeted_stratagem_cp_discount_flags()
        except Exception:
            pass
        try:
            self._refresh_charge_end_mortal_wounds_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_charge_end_mortal_wounds_flags()
        except Exception:
            pass
        try:
            self._refresh_fight_within_3_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_fight_within_3_flags()
        except Exception:
            pass

    def detach_from_unit(self) -> None:
        """Detach this Leader from its Bodyguard unit."""
        if not self.is_leader:
            return
        bodyguard = getattr(self, "attached_to", None)
        if bodyguard is None:
            return
        try:
            leaders = list(getattr(bodyguard, "attached_leaders", []) or [])
            if self in leaders:
                leaders.remove(self)
            bodyguard.attached_leaders = leaders
        except Exception:
            pass
        self.attached_to = None
        # Attachment status affects leading-only abilities; refresh caches/rules.
        try:
            self._invalidate_ability_cache()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._invalidate_ability_cache()
        except Exception:
            pass
        try:
            self._parse_against_attack_characteristic_defensive_rules()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._parse_against_attack_characteristic_defensive_rules()
        except Exception:
            pass
        try:
            self._refresh_bearer_unit_common_modifiers()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_bearer_unit_common_modifiers()
        except Exception:
            pass
        try:
            self._refresh_bearer_keyword_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_bearer_keyword_flags()
        except Exception:
            pass
        try:
            self._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass
        try:
            self._refresh_command_phase_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_command_phase_flags()
        except Exception:
            pass
        try:
            self._refresh_fall_back_desperate_escape_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_fall_back_desperate_escape_flags()
        except Exception:
            pass
        try:
            self._refresh_targeted_stratagem_cp_discount_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_targeted_stratagem_cp_discount_flags()
        except Exception:
            pass
        try:
            self._refresh_charge_end_mortal_wounds_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_charge_end_mortal_wounds_flags()
        except Exception:
            pass
        try:
            self._refresh_fight_within_3_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_fight_within_3_flags()
        except Exception:
            pass

    @property
    def is_supreme_commander(self) -> bool:
        # Wahapedia encodes this as a datasheet-sourced ability row (ability_id == ""),
        # e.g. name == "SUPREME COMMANDER".
        for ab in getattr(self, "possible_abilities", []) or []:
            if isinstance(ab, str):
                if ab.strip().upper() == "SUPREME COMMANDER":
                    return True
                continue
            name = str(getattr(ab, "name", "") or "")
            if name.strip().upper() == "SUPREME COMMANDER":
                return True
        return False

    @property
    def is_monster(self) -> bool:
        return self.has_keyword("Monster")

    @property
    def is_vehicle(self) -> bool:
        return self.has_keyword("Vehicle")

    @property
    def is_aircraft(self) -> bool:
        if bool(getattr(self, "hover_mode", False)):
            return False
        return self.has_keyword("Aircraft")

    @property
    def is_fortification(self) -> bool:
        return self.has_keyword("Fortification")

    @property
    def is_character(self) -> bool:
        return self.has_keyword("Character")

    @property
    def is_psyker(self) -> bool:
        return self.has_keyword("Psyker")

    @property
    def is_infantry(self) -> bool:
        return self.has_keyword("Infantry")

    def counts_as_infantry_for_terrain(self) -> bool:
        """Kill Team models count as Infantry for terrain interaction (RUINS traversal)."""
        if self.is_infantry:
            return True
        try:
            root = self.get_attached_unit_root()
            if root is not None and hasattr(root, "attached_unit_has_kill_team"):
                return bool(root.attached_unit_has_kill_team())
        except Exception:
            pass
        return False

    @property
    def is_beast(self) -> bool:
        return self.has_keyword("Beast")

    @property
    def is_titanic(self) -> bool:
        return self.has_keyword("Titanic")

    @property
    def is_towering(self) -> bool:
        return self.has_keyword("Towering")

    @property
    def is_flying(self) -> bool:
        return self.has_keyword("Fly")

    @property
    def is_smoke(self) -> bool:
        return self.has_keyword("Smoke")

    @property
    def is_belisarius_cawl(self) -> bool:
        return self.has_keyword("Belisarius Cawl")

    @property
    def is_imperium_primarch(self) -> bool:
        return self.has_keyword("Imperium") and self.has_keyword("Primarch")

    def has_super_heavy_walker(self) -> bool:
        """True if this unit has the Super-heavy Walker (or War Engine) ability."""
        try:
            found, _ = self._find_ability_with_patterns(
                [
                    "super-heavy walker",
                    "super-heavy war engine",
                    "super heavy war engine",
                ]
            )
            return bool(found)
        except Exception:
            return False

    def has_hover(self) -> bool:
        """True if this unit has the Hover core ability."""
        if 'hover' in getattr(self, '_ability_cache', {}):
            return bool(self._ability_cache['hover'])
        found = False
        for ab in self._iter_active_abilities():
            try:
                name = str(getattr(ab, "name", "") or "").strip().lower()
            except Exception:
                name = ""
            if name == "hover":
                found = True
                break
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['hover'] = bool(found)
        return bool(found)

    def set_hover_mode(self, enabled: bool) -> None:
        """Enable/disable Hover mode (Move becomes 20", AIRCRAFT keyword removed for rules)."""
        enabled = bool(enabled)
        if bool(getattr(self, "hover_mode", False)) == enabled:
            return
        self.hover_mode = enabled
        try:
            self.remove_characteristic_modifiers_by_source("hover_mode")
        except Exception:
            pass
        if enabled:
            try:
                from ..utility.modifiers import Modifier, ModifierOp
                self.add_characteristic_modifier(
                    "movement",
                    Modifier(ModifierOp.SET, 20, source="hover_mode"),
                )
            except Exception:
                pass

    def has_flip_belt(self) -> bool:
        """True if this unit has the Flip Belt ability (ignore vertical distance for certain moves)."""
        if 'flip_belt' in getattr(self, '_ability_cache', {}):
            return bool(self._ability_cache['flip_belt'])
        found, _ = self._find_ability_with_patterns(["flip belt"])
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['flip_belt'] = bool(found)
        return bool(found)

    def must_start_in_reserves(self) -> bool:
        """True if this unit must start the battle in Reserves (e.g., non-hover AIRCRAFT)."""
        if bool(getattr(self, "hover_mode", False)):
            return False
        return bool(self.is_aircraft)

    def has_kill_team(self) -> bool:
        """Check if the unit has the Kill Team ability (Imperial Agents)."""
        if 'kill_team' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['kill_team']
        found, _ = self._find_ability_with_patterns(["kill team"])
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['kill_team'] = found
        return found
    
    def can_move_through_ruins_walls(self) -> bool:
        """Check if this unit can move through RUINS walls via Breachable-style rules."""
        return (self.counts_as_infantry_for_terrain() or self.is_beast or
                self.is_imperium_primarch or self.is_belisarius_cawl)
    
    def can_access_upper_floors(self) -> bool:
        """Check if this unit can be placed on upper floors of RUINS."""
        return (self.counts_as_infantry_for_terrain() or self.is_beast or
                self.is_imperium_primarch or self.is_belisarius_cawl or
                self.is_flying)
    
    def can_overhang_floor(self) -> bool:
        """Check if this unit's base can overhang floor edges on upper floors."""
        return False

    def has_keyword_local(self, keyword: str) -> bool:
        kw = (keyword or "").lower().strip()
        if not kw:
            return False
        try:
            return kw in [k.lower() for k in (self.keywords or [])]
        except Exception:
            return False

    def has_any_keyword_local(self, keyword: str) -> bool:
        """Case-insensitive keyword check across local keywords + faction_keywords."""
        kw = (keyword or "").lower().strip()
        if not kw:
            return False
        try:
            if kw in [k.lower() for k in (self.keywords or [])]:
                return True
        except Exception:
            pass
        try:
            if kw in [k.lower() for k in (self.faction_keywords or [])]:
                return True
        except Exception:
            pass
        return False

    def has_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").lower().strip()
        if not kw:
            return False
        try:
            return kw in [k.lower() for k in (self.get_effective_keywords() or [])]
        except Exception:
            return kw in [k.lower() for k in (self.keywords or [])]

    def has_any_keyword(self, keyword: str) -> bool:
        """Case-insensitive keyword check across keywords + faction_keywords."""
        kw = (keyword or "").lower().strip()
        if not kw:
            return False
        try:
            if kw in [k.lower() for k in (self.get_effective_keywords() or [])]:
                return True
        except Exception:
            pass
        try:
            if kw in [k.lower() for k in (self.get_effective_faction_keywords() or [])]:
                return True
        except Exception:
            pass
        return False

    @property
    def movement(self) -> int:
        if not getattr(self, "models", None):
            return int(getattr(self, "_movement", 0) or 0)
        m = self.models[0]
        return int(getattr(m, "movement", getattr(m, "_movement", getattr(self, "_movement", 0))) or 0)

    @property
    def toughness(self) -> int:
        # 10e Attached Units: To Wound uses the Bodyguard's Toughness while the Leader is attached.
        try:
            if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                return int(self.attached_to.toughness)
        except Exception:
            pass

        # If bodyguard models are gone but separation is pending, preserve the last known bodyguard Toughness
        try:
            if len(self.models) == 0 and bool(getattr(self, "_pending_leader_separation", False)):
                t = getattr(self, "_last_bodyguard_toughness", None)
                if t is not None:
                    return int(t)
        except Exception:
            pass

        return self.models[0].toughness

    @property
    def save(self) -> int:
        return int(self.models[0].save)

    @property
    def inv_save(self) -> Optional[int]:
        return self.models[0].inv_save

    @property
    def leadership(self) -> int:
        # Best Leadership in the unit (lowest value). For Attached units, consider leaders + bodyguards.
        try:
            if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                # Avoid double-resolution; attached leaders delegate to their bodyguard unit.
                return int(self.attached_to.leadership)
        except Exception:
            pass

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        try:
            models = root.get_models_for_collision()
        except Exception:
            models = root.models

        best = None
        for m in (models or []):
            try:
                if not getattr(m, "is_alive", True):
                    continue
                ld = int(getattr(m, "leadership"))
                best = ld if best is None else min(best, ld)
            except Exception:
                continue

        if best is not None:
            return best
        # Fallback to first model if something is off
        return self.models[0].leadership

    @property
    def objective_control(self) -> int:
        # Use the unified pipeline so DIV/MUL ordering is correct (e.g. halve then +1).
        try:
            # Call as an unbound method so this property still works when accessed via
            # `Unit.objective_control.fget(stub_unit)` in tests that use lightweight stubs.
            return int(Unit.get_effective_model_characteristic(self, self.models[0], "objective_control"))
        except Exception:
            return int(self.models[0].objective_control)

    @property
    def has_circular_base(self) -> bool:
        return self.models[0].has_circular_base

    @property
    def base_size(self) -> float:
        return self.models[0].base_size

    @property
    def model_height(self) -> float:
        return max(model.model_base.model_height for model in self.models)

    def print_unit(self):
        for model in self.models:
            print(f"\n{model}")

    def get_unique_model_names(self) -> List[str]:
        return list(set(model.name for model in self.models))

    def _parse_models_cost(self, models_cost):
        """
        Parse `datasheets_models_cost` rows from Wahapedia.

        Common forms:
        - "3 models" -> "80" (base cost by model-count bucket)
        - "Attack Bike" -> "+55" (add-on model/upgrade cost)

        We store:
        - `self.models_cost`: dict[int, int] mapping model-count bucket -> points
        - `self.models_cost_addons`: dict[str, int] mapping addon label -> points (lower-cased)
        """
        import re

        base: dict[int, int] = {}
        self.models_cost_addons = {}

        for cost_entry in (models_cost or []):
            desc = str(cost_entry.get("description", "") or "").strip()
            cost_raw = str(cost_entry.get("cost", "") or "").strip()

            # Base bucket:
            # - "10 models" -> 10
            # - "1 Spanner and 4 Lootas" -> 5 (sum of all counts)
            nums = re.findall(r"\b\d+\b", desc)
            if nums:
                try:
                    if len(nums) == 1:
                        n = int(nums[0])
                    else:
                        n = sum(int(x) for x in nums)
                    base[n] = int(cost_raw.replace("+", "").strip())
                    continue
                except Exception:
                    pass

            # Add-on row: typically "+55" or "55"
            m = re.match(r"^\+?\s*(\d+)\s*$", cost_raw)
            if m and desc:
                self.models_cost_addons[desc.lower()] = int(m.group(1))

        return base

    def calculate_points(self, num_models):
        # Only consider numeric thresholds.
        numeric = [(k, v) for k, v in (self.models_cost or {}).items() if isinstance(k, int)]
        for threshold, cost in sorted(numeric, reverse=True):
            if num_models >= threshold:
                return int(cost)
        return 0

    def max_models_for_points(self, max_points):
        max_models = 0
        numeric = [(k, v) for k, v in (self.models_cost or {}).items() if isinstance(k, int)]
        for num_models, cost in sorted(numeric):
            if int(cost) <= max_points:
                max_models = int(num_models)
            else:
                break
        return max_models

    def get_unit_cost(self) -> int:
        """
        Calculate the cost of the unit based on the number of models.
        If the unit has an enhancement, add the enhancement cost to the unit cost.

        Returns:
            int: The cost of the unit in points (including enhancement cost if applicable)
        """
        num_models = len(self.models)
        total = self.calculate_points(num_models) + (self.enhancement.points if self.enhancement else 0)

        # Add-on model/upgrade costs (e.g. "Attack Bike" +55) when present.
        try:
            addons = getattr(self, "models_cost_addons", None) or {}
            if addons:
                # Count by model name, case-insensitive exact match.
                counts = {}
                for m in (self.models or []):
                    try:
                        name = str(getattr(m, "name", "") or "").strip().lower()
                        if not name:
                            continue
                        counts[name] = counts.get(name, 0) + 1
                    except Exception:
                        continue
                for addon_name, addon_cost in addons.items():
                    c = counts.get(str(addon_name).strip().lower(), 0)
                    if c:
                        total += int(addon_cost) * int(c)
        except Exception:
            pass

        return int(total)

    def configure_models(self, count, wargear):
        # Recreate the models with the specified count
        self.models = self._create_models(self._datasheet, count)
        self.update_coherency()

        # Apply wargear to all models
        for model in self.models:
            if wargear:
                if type(wargear) == list:
                    for wargear_item in wargear:
                        model.add_wargear(wargear_item)
                else:
                    model.add_wargear(wargear)
            else:
                model.wargear = []

    @property
    def abilities(self):
        abilities = []
        for model in self.models:
            abilities.extend(model.abilities)
        return abilities

    @property
    def health_percent(self) -> float:
        """Calculate the percentage of remaining health."""
        total_wounds = sum(model.wounds for model in self.models)
        max_wounds = sum(model._base_wounds for model in self.models)
        if max_wounds == 0:
            return 0
        return (total_wounds / max_wounds) * 100

    @property
    def is_ranged_unit(self) -> bool:
        """Determine if the unit is primarily a ranged unit."""
        # For simplicity, if the unit has more ranged weapons than melee weapons
        ranged_weapons = 0
        melee_weapons = 0
        for model in self.models:
            for weapon in model.wargear:
                if weapon.is_ranged():
                    ranged_weapons += 1
                elif weapon.is_melee():
                    melee_weapons += 1
        return ranged_weapons >= melee_weapons

    @property
    def is_melee_unit(self) -> bool:
        """Determine if the unit is primarily a melee unit."""
        return not self.is_ranged_unit()

    @property
    def max_charge_distance(self) -> float:
        """Calculate the maximum possible charge distance."""
        return 12.0  # 2D6 maximum roll

    def get_threat_level(self, target_unit: Optional['Unit'] = None) -> Tuple[float, float]:
        """Calculate the threat level of the unit based on offensive capabilities."""
        melee_threat = 0
        ranged_threat = 0
        for model in self.models:
            for weapon in model.wargear:
                if weapon.is_ranged() or weapon.is_melee():
                    dmg_potential = weapon.get_damage_potential(target_unit)
                    #print(f"{weapon.name} damage potential: {dmg_potential}")
                    if weapon.is_ranged():
                        ranged_threat += dmg_potential
                    else:
                        melee_threat += dmg_potential
                else:
                    raise Exception(f"UNHANDLED WEAPON TYPE: {weapon.name}")
        return ranged_threat, melee_threat

    def get_threat_per_cost(self, target_unit: Optional['Unit'] = None) -> Tuple[float, float]:
        ranged_threat, melee_threat = self.get_threat_level(target_unit)
        try:
            cost = self.models_cost[len(self.models)]
        except KeyError:
            try:
                cost = self.models_cost[len(self.models) - 1]
                cost += self.models_cost["extra"]
            except KeyError:
                print(f"No cost found for {self.name}")
                cost = 1000
        return ranged_threat / cost, melee_threat / cost

    ###########################################################################
    ### Core Actions
    ###########################################################################
    def apply_command_abilities(self) -> None:
        """Applies command abilities during the Command phase."""
        for ability in self.abilities.get('command_phase', []):
            ability.activate(self)

    ###########################################################################
    ### Command
    ###########################################################################
    def do_command_action(self, game_map: 'Map', current_turn: int = 1) -> bool:
        """Executes the command action for the unit.
        
        Args:
            game_map: The game map
            current_turn: The current battle round number
        """
        self.initialize_round()
        # Battle-shock expires at the start of *your* next Command phase.
        # Clear Battle-shock before running the step's Battle-shock tests.
        self.clear_battle_shock()

        # Do Battle Shock Test for appropriate units
        if (not self.is_alive()):
            return True
        # If forced to test for being Below Starting Strength, do not also test for being Below Half-strength
        # unless explicitly stated.
        if self.is_below_starting_strength():
            print(f"{self.name} is below starting strength - taking Battle-Shock test")
            self.take_battle_shock_test(current_turn)
        elif self.is_below_half_strength():
            print(f"{self.name} is below half strength - taking Battle-Shock test")
            self.take_battle_shock_test(current_turn)

        return True

    ###########################################################################
    ### Movement
    ###########################################################################
    def do_move_action(self, action: int, destination: Tuple[float, float, float], game_map: 'Map') -> bool:
        """Executes the given movement action."""
        return self._execute_action(action, destination, game_map)

    def get_engagement_state(self, game_map: 'Map') -> int:
        """Determine if the unit is in engagement range of any enemy model."""
        enemy_units = game_map.get_enemy_units(self)

        engaged = False
        engaged_non_aircraft = False
        for enemy_unit in enemy_units:
            if not enemy_unit.is_alive():
                continue
            if game_map.is_within_engagement_range(self, enemy_unit):
                engaged = True
                if not bool(getattr(enemy_unit, "is_aircraft", False)):
                    engaged_non_aircraft = True
                    break

        self._engaged_only_by_aircraft = bool(engaged and not engaged_non_aircraft)

        return MovementState.IN_ENGAGEMENT_RANGE if engaged else MovementState.OUT_OF_ENGAGEMENT_RANGE

    def get_available_move_actions(self, state: int) -> List[int]:
        """Get the list of available actions based on the current state."""
        try:
            state_enum = state if isinstance(state, MovementState) else MovementState(state)
        except Exception:
            state_enum = state

        # AIRCRAFT: only Normal moves allowed (no Advance/Fall Back/Remain Stationary).
        if bool(getattr(self, "is_aircraft", False)):
            return [MovementAction.MOVE.value]

        engaged_only_by_aircraft = bool(getattr(self, "_engaged_only_by_aircraft", False))
        if state_enum == MovementState.IN_ENGAGEMENT_RANGE:
            if engaged_only_by_aircraft:
                return [
                    MovementAction.REMAIN_STATIONARY.value,
                    MovementAction.MOVE.value,
                    MovementAction.ADVANCE.value,
                    MovementAction.FALL_BACK.value,
                ]
            return [MovementAction.REMAIN_STATIONARY.value, MovementAction.FALL_BACK.value]
        return [MovementAction.REMAIN_STATIONARY.value, MovementAction.MOVE.value, MovementAction.ADVANCE.value]

    def _execute_action(self, action: int, destination: Tuple[float, float, float], game_map: 'Map', advance_roll: int = None) -> bool:
        """Execute a movement action for the unit."""
        # Transport disembark restrictions: if you disembarked from a moved/destroyed transport,
        # you count as having made a Normal move and cannot move further this turn.
        if getattr(self.round_state, "disembarked_from_moved_transport", False) or getattr(self.round_state, "disembarked_from_destroyed_transport", False):
            if action in (MovementAction.MOVE.value, MovementAction.ADVANCE.value, MovementAction.FALL_BACK.value):
                print(f"{self.name} cannot move further after disembarking this turn")
                return False

        # AIRCRAFT: only Normal moves allowed.
        if bool(getattr(self, "is_aircraft", False)):
            if action in (MovementAction.REMAIN_STATIONARY.value, MovementAction.ADVANCE.value, MovementAction.FALL_BACK.value):
                print(f"{self.name} cannot {('remain stationary' if action == MovementAction.REMAIN_STATIONARY.value else 'advance' if action == MovementAction.ADVANCE.value else 'fall back')} (AIRCRAFT)")
                return False

        # If the unit is currently performing a mission Action and moves (excluding pile-in/consolidation handled elsewhere), cancel the Action
        def _cancel_action_due_to_move():
            if getattr(self.round_state, 'performing_action_name', None):
                print(f"{self.name} moved; cancelling Action '{self.round_state.performing_action_name}'")
                self.round_state.performing_action_name = None
                self.round_state.action_completes_turn = None
                self.round_state.action_locked_until_turn_end = False

        success = False
        # Resolve player/game for events
        _player = getattr(self.get_parent_army(), 'player', None)
        _game = getattr(_player, 'game', None) if _player else None
        def _publish(evt: str, **kwargs):
            try:
                if _game and hasattr(_game, 'event_system'):
                    _game.event_system.publish(evt, **kwargs)
            except Exception:
                pass
        # AELDARI: Battle Focus move-triggered manoeuvres (Swift/Flitting/Star Engines)
        if action in (MovementAction.MOVE.value, MovementAction.ADVANCE.value, MovementAction.FALL_BACK.value):
            try:
                army = self.get_parent_army()
                mgr = getattr(army, "battle_focus", None) if army is not None else None
                if mgr is not None:
                    act_name = ('advance' if action == MovementAction.ADVANCE.value else 'fall_back' if action == MovementAction.FALL_BACK.value else 'move')
                    mgr.maybe_trigger_move_maneuvers(self, act_name, _game)
            except Exception:
                pass

        # Overwatch trigger: movement start
        if action in (MovementAction.MOVE.value, MovementAction.ADVANCE.value, MovementAction.FALL_BACK.value):
            _publish("unit_move_started", unit=self, action=('advance' if action == MovementAction.ADVANCE.value else 'fall_back' if action == MovementAction.FALL_BACK.value else 'move'))
        if action == MovementAction.REMAIN_STATIONARY.value:
            print(f"{self.name} remains stationary")
            success = self.remain_stationary()
        elif action == MovementAction.MOVE.value:
            print(f"{self.name} moves to {destination}")
            success = self.move(destination, game_map)
            if success:
                _cancel_action_due_to_move()
        elif action == MovementAction.ADVANCE.value:
            print(f"{self.name} advances to {destination}")
            success = self.advance(destination, game_map)
            if success:
                _cancel_action_due_to_move()
        elif action == MovementAction.FALL_BACK.value:
            print(f"{self.name} falls back")
            # Provide an empty path list for fall back action
            success = self.fall_back(destination, [], game_map)
            if success:
                _cancel_action_due_to_move()
        else:
            raise ValueError(f"Invalid action: {action}")
        
        # Mark unit as having moved this round if action was successful
        # AND set remained_stationary_this_round to False if the unit actually moved
        if success:
            self.round_state.moved_this_round = True
            # If the unit performed any movement action (not remain stationary), 
            # it did not remain stationary this round
            if action != MovementAction.REMAIN_STATIONARY.value:
                self.round_state.remained_stationary_this_round = False
            # Overwatch trigger: movement end
            if action in (MovementAction.MOVE.value, MovementAction.ADVANCE.value, MovementAction.FALL_BACK.value):
                _publish("unit_move_ended", unit=self, action=('advance' if action == MovementAction.ADVANCE.value else 'fall_back' if action == MovementAction.FALL_BACK.value else 'move'))
        
        return success

    def remain_stationary(self) -> bool:
        if bool(getattr(self, "is_aircraft", False)):
            print(f"{self.name} cannot Remain Stationary (AIRCRAFT)")
            return False
        # Unit explicitly chose to remain stationary, so mark it as such
        self.round_state.remained_stationary_this_round = True
        return True

    # ---------------- Ability helpers (best-effort parsing) ----------------
    _LEADING_ABILITY_PREFIX_RE = re.compile(r"^\W*while this model is leading a unit\b", re.IGNORECASE)
    _NOT_LEADING_ABILITY_RE = re.compile(r"\bif this model is not leading a unit\b", re.IGNORECASE)

    def _ability_requires_leading(self, ability) -> bool:
        """Return True if the ability text is gated by 'While this model is leading a unit'."""
        desc = ""
        try:
            if isinstance(ability, str):
                desc = ability
            else:
                desc = getattr(ability, "description", "") or ""
        except Exception:
            desc = ""
        text = self._normalize_rules_text(desc)
        if not text:
            return False
        return bool(self._LEADING_ABILITY_PREFIX_RE.match(text))

    def _ability_requires_not_leading(self, ability) -> bool:
        """Return True if the ability text requires the model to NOT be leading a unit."""
        desc = ""
        try:
            if isinstance(ability, str):
                desc = ability
            else:
                desc = getattr(ability, "description", "") or ""
        except Exception:
            desc = ""
        text = self._normalize_rules_text(desc)
        if not text:
            return False
        return bool(self._NOT_LEADING_ABILITY_RE.search(text))

    def _ability_is_active(self, ability) -> bool:
        """Return True if the ability is currently active for this unit."""
        if self._ability_requires_leading(ability):
            # Only enforce leading attachment when this unit is actually a Leader datasheet.
            if bool(getattr(self, "is_leader", False)) and not bool(getattr(self, "is_attached_leader", False)):
                return False
        elif self._ability_requires_not_leading(ability):
            if bool(getattr(self, "is_attached_leader", False)):
                return False
        try:
            if self._ability_attached_possessed_formation_bonus_distance(ability) is not None:
                sr = getattr(self, "special_rules", None)
                return bool(isinstance(sr, dict) and sr.get("attached_possessed_formation_bonus"))
        except Exception:
            pass
        try:
            from ..rules.wrathful_presence import ability_name_to_key, unit_has_active_wrathful_presence
            name = ability if isinstance(ability, str) else getattr(ability, "name", "")
            key = ability_name_to_key(name)
            if key:
                return bool(unit_has_active_wrathful_presence(self, key))
        except Exception:
            pass

        # Power from Pain: pain abilities only apply while the unit is Empowered.
        try:
            name = ""
            if isinstance(ability, str):
                name = ability
            else:
                name = getattr(ability, "name", "") or ""
            if "(pain)" in str(name or "").lower():
                sr = getattr(self, "special_rules", None)
                if not (isinstance(sr, dict) and sr.get("pain_empowered")):
                    return False
        except Exception:
            pass

        # Wargear abilities only apply if the wargear is equipped.
        try:
            atype = str(getattr(ability, "type", "") or "").lower()
            if "wargear" in atype:
                return self._has_wargear_named(getattr(ability, "name", ""))
        except Exception:
            pass
        return True

    def _ability_attached_possessed_formation_bonus_distance(self, ability) -> Optional[int]:
        """
        Return the Scouts distance for the "attached to WORLD EATERS POSSESSED" formation bonus ability.
        """
        desc = ""
        name = ""
        try:
            if isinstance(ability, str):
                desc = ability
            else:
                name = str(getattr(ability, "name", "") or "")
                desc = str(getattr(ability, "description", "") or "")
        except Exception:
            desc = ""
        text = self._normalize_rules_text(f"{name} {desc}")
        if not text:
            return None
        low = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
        if "declare battle formations" not in low:
            return None
        if "attached to a world eaters possessed unit" not in low:
            return None
        if "deep strike" not in low or "scout" not in low:
            return None
        m = re.search(r"scouts?\s*(\d+)", low)
        if not m:
            return None
        return int(m.group(1))

    def _apply_attached_possessed_formation_bonus(self, bodyguard: 'Unit') -> None:
        """Apply the WORLD EATERS POSSESSED formation bonus for Leaders like LORD OF THE EIGHTBOUND."""
        if bodyguard is None:
            return
        dist = None
        for ab in (getattr(self, "possible_abilities", []) or []):
            dist = self._ability_attached_possessed_formation_bonus_distance(ab)
            if dist is not None:
                break
        if dist is None:
            return
        try:
            if not bodyguard.has_any_keyword_local("WORLD EATERS"):
                return
            if not bodyguard.has_any_keyword_local("POSSESSED"):
                return
        except Exception:
            return
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if not sr.get("attached_possessed_formation_bonus"):
            sr["attached_possessed_formation_bonus"] = True
            sr["attached_possessed_formation_scout_distance"] = int(dist)
            self.special_rules = sr

    def _get_aspect_shrine_root(self) -> 'Unit':
        try:
            return self.get_attached_unit_root()
        except Exception:
            return self

    def get_aspect_shrine_token_total(self) -> int:
        root = self._get_aspect_shrine_root()
        total = int(getattr(root, "_aspect_shrine_tokens_total", 0) or 0)
        if total <= 0:
            # Fallback to optional wargear count if tokens predate the unit-level counter.
            count = 0
            try:
                for model in list(getattr(root, "models", []) or []):
                    for ow in list(getattr(model, "optional_wargear", []) or []):
                        if Unit._norm_wargear_name(str(ow or "")) == "aspect shrine token":
                            count += 1
            except Exception:
                count = 0
            if count:
                total = count
                try:
                    setattr(root, "_aspect_shrine_tokens_total", int(total))
                except Exception:
                    pass
        return max(0, int(total))

    def get_aspect_shrine_token_used(self) -> int:
        root = self._get_aspect_shrine_root()
        used = int(getattr(root, "_aspect_shrine_tokens_used", 0) or 0)
        return max(0, int(used))

    def get_aspect_shrine_token_remaining(self) -> int:
        return max(0, self.get_aspect_shrine_token_total() - self.get_aspect_shrine_token_used())

    def add_aspect_shrine_tokens(self, count: int = 1) -> None:
        root = self._get_aspect_shrine_root()
        try:
            count = int(count)
        except Exception:
            count = 1
        if count <= 0:
            return
        try:
            current = int(getattr(root, "_aspect_shrine_tokens_total", 0) or 0)
        except Exception:
            current = 0
        try:
            setattr(root, "_aspect_shrine_tokens_total", current + count)
        except Exception:
            pass

    def spend_aspect_shrine_token(self, count: int = 1) -> bool:
        root = self._get_aspect_shrine_root()
        try:
            count = int(count)
        except Exception:
            count = 1
        if count <= 0:
            return False
        total = self.get_aspect_shrine_token_total()
        used = self.get_aspect_shrine_token_used()
        if used + count > total:
            return False
        try:
            setattr(root, "_aspect_shrine_tokens_used", used + count)
        except Exception:
            return False
        return True

    def is_aspect_shrine_prompt_suppressed(self) -> bool:
        root = self._get_aspect_shrine_root()
        return bool(getattr(root, "_aspect_shrine_prompt_suppressed", False))

    def set_aspect_shrine_prompt_suppressed(self, suppressed: bool = True) -> None:
        root = self._get_aspect_shrine_root()
        try:
            setattr(root, "_aspect_shrine_prompt_suppressed", bool(suppressed))
        except Exception:
            pass

    def clear_aspect_shrine_prompt_suppression(self) -> None:
        self.set_aspect_shrine_prompt_suppressed(False)

    def _has_wargear_named(self, name: str) -> bool:
        want = Unit._norm_wargear_name(name)
        if not want:
            return False
        if want == "aspect shrine token":
            try:
                if self.get_aspect_shrine_token_total() > 0:
                    return True
            except Exception:
                pass
        for model in list(getattr(self, "models", []) or []):
            try:
                for wg in list(getattr(model, "wargear", []) or []):
                    if wg and Unit._norm_wargear_name(getattr(wg, "name", "")) == want:
                        return True
            except Exception:
                pass
            try:
                for ow in list(getattr(model, "optional_wargear", []) or []):
                    if Unit._norm_wargear_name(str(ow or "")) == want:
                        return True
            except Exception:
                continue
        return False

    def _model_has_wargear_named(self, model: Optional['Model'], name: str) -> bool:
        if model is None:
            return False
        want = Unit._norm_wargear_name(name)
        if not want:
            return False
        try:
            for wg in list(getattr(model, "wargear", []) or []):
                if wg and Unit._norm_wargear_name(getattr(wg, "name", "")) == want:
                    return True
        except Exception:
            pass
        try:
            for ow in list(getattr(model, "optional_wargear", []) or []):
                if Unit._norm_wargear_name(str(ow or "")) == want:
                    return True
        except Exception:
            pass
        return False

    def _parse_bearer_invulnerable_save(self, text: str) -> Optional[int]:
        if not text:
            return None
        normalized = self._normalize_rules_text(text)
        if not normalized:
            return None
        normalized = normalized.replace("\u2019", "'")
        normalized = re.sub(r"\s+([.])", r"\1", normalized).strip()
        m = self._BEARER_INVULNERABLE_SAVE_RE.match(normalized)
        if not m:
            return None
        try:
            return int(m.group(1))
        except Exception:
            return None

    def _parse_bearer_save_characteristic(self, text: str) -> Optional[int]:
        if not text:
            return None
        normalized = self._normalize_rules_text(text)
        if not normalized:
            return None
        normalized = normalized.replace("\u2019", "'")
        normalized = re.sub(r"\s+([.])", r"\1", normalized).strip()
        m = self._BEARER_SAVE_CHARACTERISTIC_RE.match(normalized)
        if not m:
            return None
        try:
            return int(m.group(1))
        except Exception:
            return None

    def get_model_invulnerable_save_override(self, model: Optional['Model'] = None) -> tuple[Optional[int], Optional[str]]:
        """
        Return (invulnerable_save_value, source_name) for bearer-only invuln wargear abilities.
        """
        if model is None:
            return None, None
        cache_key = f"model_invulnerable_save:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        best_value: Optional[int] = None
        best_source: Optional[str] = None

        # Model-level abilities (if any)
        try:
            for ab in getattr(model, "abilities", {}).values():
                try:
                    desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or "")
                    name = ab if isinstance(ab, str) else (getattr(ab, "name", "") or "Model ability")
                except Exception:
                    desc = ""
                    name = "Model ability"
                val = self._parse_bearer_invulnerable_save(desc)
                if val is None:
                    continue
                if best_value is None or val < best_value:
                    best_value = val
                    best_source = str(name or "Model ability")
        except Exception:
            pass

        # Wargear abilities tied to equipped items.
        for ab in list(getattr(self, "possible_abilities", []) or []):
            try:
                atype = str(getattr(ab, "type", "") or "").lower()
                if "wargear" not in atype:
                    continue
                name = getattr(ab, "name", "") or ""
                if not name:
                    continue
                if not self._model_has_wargear_named(model, name):
                    continue
                desc = getattr(ab, "description", "") or ""
                val = self._parse_bearer_invulnerable_save(desc)
                if val is None:
                    continue
                if best_value is None or val < best_value:
                    best_value = val
                    best_source = str(name)
            except Exception:
                continue

        # Leading/bearer unit abilities that grant an invulnerable save to the unit.
        try:
            sr = getattr(self, "special_rules", None)
            entries = sr.get("bearer_unit_invulnerable_save") if isinstance(sr, dict) else None
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        val = entry.get("value")
                        source = entry.get("source")
                    elif isinstance(entry, (list, tuple)):
                        val = entry[0] if entry else None
                        source = entry[1] if len(entry) > 1 else None
                    else:
                        continue
                    try:
                        val = int(val)
                    except Exception:
                        continue
                    if best_value is None or val < best_value:
                        best_value = int(val)
                        best_source = str(source or "Bearer unit ability")
        except Exception:
            pass

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = (best_value, best_source)
        return best_value, best_source

    def get_model_save_characteristic_override(self, model: Optional['Model'] = None) -> tuple[Optional[int], Optional[str]]:
        """
        Return (save_value, source_name) for bearer-only save characteristic overrides.
        """
        if model is None:
            return None, None
        cache_key = f"model_save_characteristic:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        best_value: Optional[int] = None
        best_source: Optional[str] = None

        # Model-level abilities (if any)
        try:
            for ab in getattr(model, "abilities", {}).values():
                try:
                    desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or "")
                    name = ab if isinstance(ab, str) else (getattr(ab, "name", "") or "Model ability")
                except Exception:
                    desc = ""
                    name = "Model ability"
                val = self._parse_bearer_save_characteristic(desc)
                if val is None:
                    continue
                if best_value is None or val < best_value:
                    best_value = val
                    best_source = str(name or "Model ability")
        except Exception:
            pass

        # Wargear abilities tied to equipped items.
        for ab in list(getattr(self, "possible_abilities", []) or []):
            try:
                atype = str(getattr(ab, "type", "") or "").lower()
                if "wargear" not in atype:
                    continue
                name = getattr(ab, "name", "") or ""
                if not name:
                    continue
                if not self._model_has_wargear_named(model, name):
                    continue
                desc = getattr(ab, "description", "") or ""
                val = self._parse_bearer_save_characteristic(desc)
                if val is None:
                    continue
                if best_value is None or val < best_value:
                    best_value = val
                    best_source = str(name)
            except Exception:
                continue

        # Unit-level abilities on single-model units.
        try:
            if len(list(getattr(self, "models", []) or [])) == 1:
                for ab in list(getattr(self, "possible_abilities", []) or []):
                    try:
                        desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or "")
                        name = ab if isinstance(ab, str) else (getattr(ab, "name", "") or "Unit ability")
                    except Exception:
                        desc = ""
                        name = "Unit ability"
                    val = self._parse_bearer_save_characteristic(desc)
                    if val is None:
                        continue
                    if best_value is None or val < best_value:
                        best_value = val
                        best_source = str(name or "Unit ability")
        except Exception:
            pass

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = (best_value, best_source)
        return best_value, best_source

    def _iter_active_possible_abilities(self):
        """Yield unit-level abilities that are currently active for this unit."""
        for ab in (getattr(self, "possible_abilities", []) or []):
            try:
                if not self._ability_is_active(ab):
                    continue
            except Exception:
                continue
            yield ab

    def _iter_active_abilities(self):
        """Yield unit + model abilities that are currently active for this unit."""
        for ab in self._iter_active_possible_abilities():
            yield ab
        for ab in (list(getattr(self, "abilities", []) or []) or []):
            try:
                if not self._ability_is_active(ab):
                    continue
            except Exception:
                continue
            yield ab

    def _iter_active_ability_texts(self):
        """Yield name/description strings for active abilities (used by text scanners)."""
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    if ab:
                        yield ab
                    continue
                nm = str(getattr(ab, "name", "") or "")
                ds = str(getattr(ab, "description", "") or "")
                if nm:
                    yield nm
                if ds:
                    yield ds
            except Exception:
                continue

    def _iter_attached_leader_leading_abilities(self):
        """Yield (ability, leader_unit) for attached leaders with leading-only abilities."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is not self:
            for item in root._iter_attached_leader_leading_abilities():
                yield item
            return
        leaders = list(getattr(root, "attached_leaders", []) or [])
        for leader in leaders:
            if leader is None:
                continue
            try:
                abilities = list(getattr(leader, "possible_abilities", []) or [])
            except Exception:
                abilities = []
            for ab in abilities:
                try:
                    if not leader._ability_requires_leading(ab):
                        continue
                    if not leader._ability_is_active(ab):
                        continue
                except Exception:
                    continue
                yield ab, leader

    def _iter_attached_leader_ability_texts(self):
        """Yield name/description strings for attached leader leading abilities."""
        for ab, _leader in self._iter_attached_leader_leading_abilities():
            try:
                if isinstance(ab, str):
                    if ab:
                        yield ab
                    continue
                nm = str(getattr(ab, "name", "") or "")
                ds = str(getattr(ab, "description", "") or "")
                if nm:
                    yield nm
                if ds:
                    yield ds
            except Exception:
                continue

    def _iter_reroll_scan_texts(self):
        """Yield ability texts for reroll detection."""
        iter_active = getattr(self, "_iter_active_ability_texts", None)
        if callable(iter_active):
            for t in iter_active():
                yield t
        iter_leader = getattr(self, "_iter_attached_leader_ability_texts", None)
        if callable(iter_leader):
            for t in iter_leader():
                yield t

    def _iter_attached_unit_reroll_texts(self):
        """Yield normalized ability texts for attached unit reroll rules (includes leaders)."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        seen = set()
        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text = u._normalize_rules_text(desc or name or "")
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                text = Unit._strip_eligibility_prefix(text)
                if "leading a unit" in text.lower() and "bearer's unit" not in text.lower():
                    text = re.sub(r"\bthat unit\b", "the bearer's unit", text, flags=re.IGNORECASE)
                key = text.lower()
                if key in seen:
                    continue
                seen.add(key)
                yield text

    def _iter_attack_roll_rule_texts(self, text: str) -> list[str]:
        """Extract attack-roll rule clauses from a rules text (best-effort)."""
        if not text:
            return []
        cleaned = self._normalize_rules_text(text)
        if not cleaned:
            return []
        cleaned = Unit._strip_eligibility_prefix(cleaned)
        cleaned = re.sub(r";\s*", ". ", cleaned)
        sentences = [part.strip() for part in re.split(r"\.\s*", cleaned) if part.strip()]
        if not sentences:
            return []
        candidates: list[str] = []

        def _effect_start(value: str) -> bool:
            return bool(re.match(r"^(?:if|add|subtract|you can|reroll|re-?roll|a successful|an unmodified|a critical)\b", value, flags=re.IGNORECASE))

        for idx, sentence in enumerate(sentences):
            sl = sentence.lower()
            if "each time" not in sl or "attack" not in sl:
                continue
            if not any(k in sl for k in ("hit roll", "wound roll", "critical", "reroll", "re-roll", "subtract", "add")):
                continue
            parts = [sentence]
            j = idx + 1
            while j < len(sentences):
                nxt = sentences[j].strip()
                if not nxt:
                    j += 1
                    continue
                if _effect_start(nxt):
                    parts.append(nxt)
                    j += 1
                    continue
                break
            candidates.append(". ".join(parts))

        if not candidates:
            candidates = [cleaned]
        return candidates

    def _parse_attack_roll_rules_from_text(self, text: str):
        """Parse attack-roll rules from text into structured rules."""
        rules = []
        for chunk in self._iter_attack_roll_rule_texts(text):
            try:
                rule = parse_attack_roll_text(chunk)
            except Exception:
                rule = None
            if rule is not None:
                rules.append(rule)
        return rules

    def _get_unit_attack_roll_rules(self):
        """Collect and cache unit-level attack roll rules for this attached unit."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "unit_attack_roll_rules"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]
        rules = []
        seen_names: set[str] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in members:
            for name, desc in member._iter_ability_entries_for_rules():
                try:
                    ability_name = str(name or "").replace("\u2019", "'").strip()
                except Exception:
                    ability_name = ""
                name_key = ability_name.lower().strip()
                if name_key and name_key in seen_names:
                    continue
                if name_key:
                    seen_names.add(name_key)
                text_src = desc or name or ""
                for rule in self._parse_attack_roll_rules_from_text(text_src):
                    if rule.scope != "unit":
                        continue
                    if rule.subject not in ("model_in_this_unit", "model_in_that_unit"):
                        continue
                    rules.append((rule, ability_name or "Unit ability"))
        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rules
        return rules

    def _attack_condition_met(self, condition: Optional[AttackRollCondition], *, target=None, source_unit=None) -> bool:
        """Evaluate attack-roll conditions against the current unit/target."""
        if condition is None:
            return True
        unit = source_unit or self
        try:
            unit = unit.get_attached_unit_root()
        except Exception:
            pass
        if condition.attacker_below_starting_strength:
            try:
                if not unit.is_below_starting_strength():
                    return False
            except Exception:
                return False
        if condition.attacker_below_half_strength:
            try:
                if not unit.is_below_half_strength():
                    return False
            except Exception:
                return False
        if condition.target_battleshocked:
            try:
                if not (target is not None and target.is_battle_shocked()):
                    return False
            except Exception:
                return False
        if condition.target_within_objective:
            try:
                if not self._target_within_objective_range(target):
                    return False
            except Exception:
                return False
        if condition.target_within_range is not None:
            try:
                from ..utility.aura_utils import unit_within_range_of_unit
                t_unit = target
                if t_unit is not None and not hasattr(t_unit, "get_attached_unit_root"):
                    t_unit = getattr(t_unit, "parent_unit", t_unit)
                if t_unit is None:
                    return False
                game = None
                try:
                    game = getattr(getattr(unit.get_parent_army(), "player", None), "game", None)
                except Exception:
                    game = None
                if game is None:
                    try:
                        game = getattr(getattr(t_unit.get_parent_army(), "player", None), "game", None)
                    except Exception:
                        game = None
                game_map = getattr(game, "map", None) if game is not None else None
                if game_map is not None:
                    placed = list(getattr(game_map, "units", []) or [])
                    try:
                        s_root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
                    except Exception:
                        s_root = unit
                    try:
                        t_root = t_unit.get_attached_unit_root() if hasattr(t_unit, "get_attached_unit_root") else t_unit
                    except Exception:
                        t_root = t_unit
                    if s_root not in placed or t_root not in placed:
                        return False
                if not unit_within_range_of_unit(unit, t_unit, float(condition.target_within_range), use_attached_aggregate=True):
                    return False
            except Exception:
                return False
        if condition.target_can_fly is not None:
            try:
                can_fly = bool(getattr(target, "is_flying", False))
            except Exception:
                can_fly = False
            if not can_fly:
                try:
                    can_fly = bool(target.has_keyword("FLY") or target.has_any_keyword("FLY"))
                except Exception:
                    can_fly = False
            if bool(condition.target_can_fly) != bool(can_fly):
                return False
        if condition.target_below_starting_strength:
            try:
                if not (target is not None and target.is_below_starting_strength()):
                    return False
            except Exception:
                return False
        if condition.target_below_half_strength:
            try:
                if not (target is not None and target.is_below_half_strength()):
                    return False
            except Exception:
                return False

        def _target_has_keyword(keyword: str) -> bool:
            if target is None:
                return False
            kw = str(keyword or "").strip()
            if not kw:
                return False
            try:
                return bool(target.has_keyword(kw.upper()))
            except Exception:
                try:
                    return bool(target.has_any_keyword(kw.upper()))
                except Exception:
                    return False

        if condition.target_keywords_any:
            if not any(_target_has_keyword(k) for k in condition.target_keywords_any):
                return False
        if condition.target_keywords_all:
            if not all(_target_has_keyword(k) for k in condition.target_keywords_all):
                return False
        if condition.target_exclude_keywords_any:
            if any(_target_has_keyword(k) for k in condition.target_exclude_keywords_any):
                return False
        return True

    def get_leading_attack_roll_modifiers(self, attack_type: str, *, target=None) -> dict:
        """
        Return leading-only attack roll modifiers from attached leaders for the attached unit.

        Supports strict patterns parsed by attack_roll_parser (full clause matching).
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"

        cache_key = "leading_attack_roll_rules"
        if cache_key in getattr(root, "_ability_cache", {}):
            rules = root._ability_cache[cache_key]
        else:
            rules = []
            seen_names: set[str] = set()
            for ab, _leader in root._iter_attached_leader_leading_abilities():
                try:
                    name = str(getattr(ab, "name", "") or "Leading ability").replace("\u2019", "'")
                    desc = str(getattr(ab, "description", "") or "")
                except Exception:
                    name = "Leading ability"
                    desc = ""
                name_key = name.strip().lower()
                if name_key and name_key != "leading ability" and name_key in seen_names:
                    continue
                if name_key and name_key != "leading ability":
                    seen_names.add(name_key)
                text_src = desc or name or ""
                for rule in self._parse_attack_roll_rules_from_text(text_src):
                    if rule.scope != "leading":
                        continue
                    if rule.subject not in ("model_in_that_unit", "model_in_this_unit"):
                        continue
                    rules.append((rule, name or "Leading ability"))
            if not hasattr(root, "_ability_cache"):
                root._ability_cache = {}
            root._ability_cache[cache_key] = rules

        mods = {
            "hit": 0,
            "wound": 0,
            "reroll_hit_ones": False,
            "reroll_wound_ones": False,
            "reroll_hit_values": (),
            "reroll_wound_values": (),
            "reroll_hit_full": False,
            "reroll_wound_full": False,
            "crit_hit_threshold": None,
            "crit_wound_threshold": None,
            "hit_reasons": (),
            "wound_reasons": (),
            "reroll_hit_reasons": (),
            "reroll_wound_reasons": (),
            "reroll_hit_full_reasons": (),
            "reroll_wound_full_reasons": (),
            "crit_hit_reasons": (),
            "crit_wound_reasons": (),
        }

        hit_reasons: list[str] = []
        wound_reasons: list[str] = []
        reroll_hit_reasons: list[str] = []
        reroll_wound_reasons: list[str] = []
        reroll_hit_full_reasons: list[str] = []
        reroll_wound_full_reasons: list[str] = []
        crit_hit_reasons: list[str] = []
        crit_wound_reasons: list[str] = []
        reroll_hit_values: set[int] = set()
        reroll_wound_values: set[int] = set()
        crit_hit_threshold = None
        crit_wound_threshold = None

        def _cond_suffix(cond: Optional[AttackRollCondition]) -> str:
            if not cond:
                return ""
            parts = []
            if cond.target_battleshocked:
                parts.append("vs Battle-shocked targets")
            if cond.attacker_below_starting_strength:
                parts.append("while below Starting Strength")
            if cond.attacker_below_half_strength:
                parts.append("while below Half-strength")
            if cond.target_within_objective:
                parts.append("vs targets within objective range")
            if cond.target_within_range is not None:
                parts.append(f"vs targets within {cond.target_within_range}\"")
            if cond.target_can_fly is True:
                parts.append("vs FLY targets")
            if cond.target_can_fly is False:
                parts.append("vs non-FLY targets")
            if cond.target_keywords_any:
                if set(cond.target_keywords_any) == {"character"}:
                    parts.append("vs CHARACTER targets")
                elif set(cond.target_keywords_any) == {"monster", "vehicle"}:
                    parts.append("vs MONSTER/VEHICLE targets")
            if cond.target_below_starting_strength:
                parts.append("vs targets below Starting Strength")
            if cond.target_below_half_strength:
                parts.append("vs targets below Half-strength")
            if cond.target_exclude_keywords_any:
                parts.append("excluding " + ", ".join(cond.target_exclude_keywords_any))
            if not parts:
                return ""
            return " (" + "; ".join(parts) + ")"

        for rule, name in list(rules or []):
            if atype != "any" and rule.attack_type not in ("any", atype):
                continue
            for eff in rule.effects:
                if not self._attack_condition_met(eff.condition, target=target, source_unit=root):
                    continue
                label = name or "Leading ability"
                if eff.kind in ("add", "sub") and eff.roll in ("hit", "wound"):
                    val = int(eff.value or 0)
                    if eff.kind == "sub":
                        val = -val
                    if eff.roll == "hit":
                        mods["hit"] += val
                        hit_reasons.append(f"{val:+d} to hit from {label}{_cond_suffix(eff.condition)}")
                    else:
                        mods["wound"] += val
                        wound_reasons.append(f"{val:+d} to wound from {label}{_cond_suffix(eff.condition)}")
                elif eff.kind == "reroll":
                    if eff.roll == "hit":
                        if eff.reroll_full:
                            mods["reroll_hit_full"] = True
                            reroll_hit_full_reasons.append(f"Leading: re-roll Hit roll from {label}{_cond_suffix(eff.condition)}")
                        if eff.reroll_values:
                            reroll_hit_values.update(int(v) for v in eff.reroll_values)
                            reroll_hit_reasons.append(
                                f"Leading: re-roll Hit rolls of {', '.join(str(v) for v in sorted(eff.reroll_values))} from {label}{_cond_suffix(eff.condition)}"
                            )
                    elif eff.roll == "wound":
                        if eff.reroll_full:
                            mods["reroll_wound_full"] = True
                            reroll_wound_full_reasons.append(f"Leading: re-roll Wound roll from {label}{_cond_suffix(eff.condition)}")
                        if eff.reroll_values:
                            reroll_wound_values.update(int(v) for v in eff.reroll_values)
                            reroll_wound_reasons.append(
                                f"Leading: re-roll Wound rolls of {', '.join(str(v) for v in sorted(eff.reroll_values))} from {label}{_cond_suffix(eff.condition)}"
                            )
                elif eff.kind == "crit" and eff.critical_threshold:
                    if eff.roll == "hit":
                        crit_hit_threshold = eff.critical_threshold if crit_hit_threshold is None else min(crit_hit_threshold, eff.critical_threshold)
                        crit_hit_reasons.append(f"Leading: critical hit on {eff.critical_threshold}+ from {label}{_cond_suffix(eff.condition)}")
                    elif eff.roll == "wound":
                        crit_wound_threshold = eff.critical_threshold if crit_wound_threshold is None else min(crit_wound_threshold, eff.critical_threshold)
                        crit_wound_reasons.append(f"Leading: critical wound on {eff.critical_threshold}+ from {label}{_cond_suffix(eff.condition)}")

        mods["reroll_hit_values"] = tuple(sorted(reroll_hit_values))
        mods["reroll_wound_values"] = tuple(sorted(reroll_wound_values))
        mods["reroll_hit_ones"] = bool(1 in reroll_hit_values)
        mods["reroll_wound_ones"] = bool(1 in reroll_wound_values)
        mods["crit_hit_threshold"] = crit_hit_threshold
        mods["crit_wound_threshold"] = crit_wound_threshold
        mods["hit_reasons"] = tuple(hit_reasons)
        mods["wound_reasons"] = tuple(wound_reasons)
        mods["reroll_hit_reasons"] = tuple(reroll_hit_reasons)
        mods["reroll_wound_reasons"] = tuple(reroll_wound_reasons)
        mods["reroll_hit_full_reasons"] = tuple(reroll_hit_full_reasons)
        mods["reroll_wound_full_reasons"] = tuple(reroll_wound_full_reasons)
        mods["crit_hit_reasons"] = tuple(crit_hit_reasons)
        mods["crit_wound_reasons"] = tuple(crit_wound_reasons)
        return mods

    def get_unit_hit_reroll_modifiers(self, attack_type: str, *, target=None) -> dict:
        """
        Return unit-level hit modifiers for this attached unit, parsed via attack_roll_parser.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"

        rules = self._get_unit_attack_roll_rules()

        mods = {
            "hit": 0,
            "reroll_hit_ones": False,
            "reroll_hit_values": (),
            "reroll_hit_full": False,
            "crit_hit_threshold": None,
            "hit_reasons": (),
            "reroll_hit_reasons": (),
            "reroll_hit_full_reasons": (),
            "crit_hit_reasons": (),
        }

        hit_reasons: list[str] = []
        reroll_hit_reasons: list[str] = []
        reroll_hit_full_reasons: list[str] = []
        crit_hit_reasons: list[str] = []
        reroll_hit_values: set[int] = set()
        crit_hit_threshold = None

        def _cond_suffix(cond: Optional[AttackRollCondition]) -> str:
            if not cond:
                return ""
            parts = []
            if cond.target_battleshocked:
                parts.append("vs Battle-shocked targets")
            if cond.attacker_below_starting_strength:
                parts.append("while below Starting Strength")
            if cond.attacker_below_half_strength:
                parts.append("while below Half-strength")
            if cond.target_within_objective:
                parts.append("vs targets within objective range")
            if cond.target_within_range is not None:
                parts.append(f"vs targets within {cond.target_within_range}\"")
            if cond.target_can_fly is True:
                parts.append("vs FLY targets")
            if cond.target_can_fly is False:
                parts.append("vs non-FLY targets")
            if cond.target_keywords_any:
                if set(cond.target_keywords_any) == {"character"}:
                    parts.append("vs CHARACTER targets")
                elif set(cond.target_keywords_any) == {"monster", "vehicle"}:
                    parts.append("vs MONSTER/VEHICLE targets")
            if cond.target_below_starting_strength:
                parts.append("vs targets below Starting Strength")
            if cond.target_below_half_strength:
                parts.append("vs targets below Half-strength")
            if cond.target_exclude_keywords_any:
                parts.append("excluding " + ", ".join(cond.target_exclude_keywords_any))
            if not parts:
                return ""
            return " (" + "; ".join(parts) + ")"

        for rule, name in list(rules or []):
            if atype != "any" and rule.attack_type not in ("any", atype):
                continue
            for eff in rule.effects:
                if not self._attack_condition_met(eff.condition, target=target, source_unit=root):
                    continue
                if eff.roll != "hit":
                    continue
                label = name or "Unit ability"
                if eff.kind in ("add", "sub"):
                    val = int(eff.value or 0)
                    if eff.kind == "sub":
                        val = -val
                    mods["hit"] += val
                    hit_reasons.append(f"{val:+d} to hit from {label}{_cond_suffix(eff.condition)}")
                elif eff.kind == "reroll":
                    if eff.reroll_full:
                        mods["reroll_hit_full"] = True
                        reroll_hit_full_reasons.append(f"{label}: re-roll Hit roll{_cond_suffix(eff.condition)}")
                    if eff.reroll_values:
                        reroll_hit_values.update(int(v) for v in eff.reroll_values)
                        reroll_hit_reasons.append(
                            f"{label}: re-roll Hit rolls of {', '.join(str(v) for v in sorted(eff.reroll_values))}{_cond_suffix(eff.condition)}"
                        )
                elif eff.kind == "crit" and eff.critical_threshold:
                    crit_hit_threshold = eff.critical_threshold if crit_hit_threshold is None else min(crit_hit_threshold, eff.critical_threshold)
                    crit_hit_reasons.append(f"{label}: critical hit on {eff.critical_threshold}+{_cond_suffix(eff.condition)}")

        mods["reroll_hit_values"] = tuple(sorted(reroll_hit_values))
        mods["reroll_hit_ones"] = bool(1 in reroll_hit_values)
        mods["crit_hit_threshold"] = crit_hit_threshold
        mods["hit_reasons"] = tuple(hit_reasons)
        mods["reroll_hit_reasons"] = tuple(reroll_hit_reasons)
        mods["reroll_hit_full_reasons"] = tuple(reroll_hit_full_reasons)
        mods["crit_hit_reasons"] = tuple(crit_hit_reasons)
        return mods

    def get_unit_wound_reroll_modifiers(self, attack_type: str, *, target=None) -> dict:
        """
        Return unit-level wound modifiers for this attached unit, parsed via attack_roll_parser.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"

        rules = self._get_unit_attack_roll_rules()

        mods = {
            "wound": 0,
            "reroll_wound_ones": False,
            "reroll_wound_values": (),
            "reroll_wound_full": False,
            "crit_wound_threshold": None,
            "wound_reasons": (),
            "reroll_wound_reasons": (),
            "reroll_wound_full_reasons": (),
            "crit_wound_reasons": (),
        }

        wound_reasons: list[str] = []
        reroll_wound_reasons: list[str] = []
        reroll_wound_full_reasons: list[str] = []
        crit_wound_reasons: list[str] = []
        reroll_wound_values: set[int] = set()
        crit_wound_threshold = None

        def _cond_suffix(cond: Optional[AttackRollCondition]) -> str:
            if not cond:
                return ""
            parts = []
            if cond.target_battleshocked:
                parts.append("vs Battle-shocked targets")
            if cond.attacker_below_starting_strength:
                parts.append("while below Starting Strength")
            if cond.attacker_below_half_strength:
                parts.append("while below Half-strength")
            if cond.target_within_objective:
                parts.append("vs targets within objective range")
            if cond.target_within_range is not None:
                parts.append(f"vs targets within {cond.target_within_range}\"")
            if cond.target_can_fly is True:
                parts.append("vs FLY targets")
            if cond.target_can_fly is False:
                parts.append("vs non-FLY targets")
            if cond.target_keywords_any:
                if set(cond.target_keywords_any) == {"character"}:
                    parts.append("vs CHARACTER targets")
                elif set(cond.target_keywords_any) == {"monster", "vehicle"}:
                    parts.append("vs MONSTER/VEHICLE targets")
            if cond.target_below_starting_strength:
                parts.append("vs targets below Starting Strength")
            if cond.target_below_half_strength:
                parts.append("vs targets below Half-strength")
            if cond.target_exclude_keywords_any:
                parts.append("excluding " + ", ".join(cond.target_exclude_keywords_any))
            if not parts:
                return ""
            return " (" + "; ".join(parts) + ")"

        for rule, name in list(rules or []):
            if atype != "any" and rule.attack_type not in ("any", atype):
                continue
            for eff in rule.effects:
                if not self._attack_condition_met(eff.condition, target=target, source_unit=root):
                    continue
                if eff.roll != "wound":
                    continue
                label = name or "Unit ability"
                if eff.kind in ("add", "sub"):
                    val = int(eff.value or 0)
                    if eff.kind == "sub":
                        val = -val
                    mods["wound"] += val
                    wound_reasons.append(f"{val:+d} to wound from {label}{_cond_suffix(eff.condition)}")
                elif eff.kind == "reroll":
                    if eff.reroll_full:
                        mods["reroll_wound_full"] = True
                        reroll_wound_full_reasons.append(f"{label}: re-roll Wound roll{_cond_suffix(eff.condition)}")
                    if eff.reroll_values:
                        reroll_wound_values.update(int(v) for v in eff.reroll_values)
                        reroll_wound_reasons.append(
                            f"{label}: re-roll Wound rolls of {', '.join(str(v) for v in sorted(eff.reroll_values))}{_cond_suffix(eff.condition)}"
                        )
                elif eff.kind == "crit" and eff.critical_threshold:
                    crit_wound_threshold = eff.critical_threshold if crit_wound_threshold is None else min(crit_wound_threshold, eff.critical_threshold)
                    crit_wound_reasons.append(f"{label}: critical wound on {eff.critical_threshold}+{_cond_suffix(eff.condition)}")

        mods["reroll_wound_values"] = tuple(sorted(reroll_wound_values))
        mods["reroll_wound_ones"] = bool(1 in reroll_wound_values)
        mods["crit_wound_threshold"] = crit_wound_threshold
        mods["wound_reasons"] = tuple(wound_reasons)
        mods["reroll_wound_reasons"] = tuple(reroll_wound_reasons)
        mods["reroll_wound_full_reasons"] = tuple(reroll_wound_full_reasons)
        mods["crit_wound_reasons"] = tuple(crit_wound_reasons)
        return mods

    def get_melee_damage_bonus_vs_monster_vehicle(self) -> int:
        """
        Return bonus Damage for melee attacks that target MONSTER or VEHICLE units.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "melee_damage_bonus_vs_monster_vehicle"
        if cache_key in getattr(root, "_ability_cache", {}):
            return int(root._ability_cache[cache_key] or 0)

        bonus = 0
        seen: set[tuple[str, str]] = set()

        def _monster_vehicle_only_condition(cond: Optional[AttackRollCondition]) -> bool:
            if cond is None:
                return False
            if cond.attacker_below_starting_strength or cond.attacker_below_half_strength:
                return False
            if cond.target_below_starting_strength:
                return False
            if cond.target_battleshocked or cond.target_within_objective:
                return False
            if cond.target_within_range is not None:
                return False
            if cond.target_can_fly is not None:
                return False
            if cond.target_below_half_strength:
                return False
            if cond.target_keywords_all or cond.target_exclude_keywords_any:
                return False
            kw_any = {k.strip().lower() for k in (cond.target_keywords_any or ()) if k}
            return bool({"monster", "vehicle"}.issubset(kw_any))

        def _scan(text: str, name: str = "") -> int:
            if not text:
                return 0
            norm = self._normalize_rules_text(text)
            if not norm:
                return 0
            key = (str(name or "").strip().lower(), norm.lower())
            if key in seen:
                return 0
            seen.add(key)
            total = 0
            for rule in self._parse_attack_roll_rules_from_text(text):
                if rule.scope not in ("unit", "leading"):
                    continue
                if rule.subject not in ("model_in_this_unit", "model_in_that_unit", "this_model"):
                    continue
                if rule.attack_type not in ("melee", "any"):
                    continue
                for eff in rule.effects:
                    if eff.roll != "damage" or eff.kind != "add":
                        continue
                    if not _monster_vehicle_only_condition(eff.condition):
                        continue
                    try:
                        val = int(eff.value or 0)
                    except Exception:
                        val = 0
                    if val:
                        total += val
            return total

        for ab in root._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    bonus += _scan(ab, "")
                else:
                    desc = str(getattr(ab, "description", "") or "")
                    name = str(getattr(ab, "name", "") or "")
                    if desc:
                        bonus += _scan(desc, name)
                    else:
                        bonus += _scan(name, name)
            except Exception:
                continue

        try:
            for ab, _leader in root._iter_attached_leader_leading_abilities():
                try:
                    if isinstance(ab, str):
                        bonus += _scan(ab, "")
                    else:
                        desc = str(getattr(ab, "description", "") or "")
                        name = str(getattr(ab, "name", "") or "")
                        if desc:
                            bonus += _scan(desc, name)
                        else:
                            bonus += _scan(name, name)
                except Exception:
                    continue
        except Exception:
            pass

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = int(bonus or 0)
        return int(bonus or 0)

    def _was_set_up_this_turn(self, *, game=None) -> bool:
        try:
            if bool(getattr(self, "arrived_from_reserves_this_turn", False)):
                return True
        except Exception:
            pass
        try:
            if bool(getattr(self.round_state, "reinforced_this_round", False)):
                return True
        except Exception:
            pass
        try:
            if game is None:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            if turn and int(getattr(self, "reserve_turn_deployed", 0) or 0) == turn:
                return True
        except Exception:
            pass
        return False

    def _target_within_objective_range(self, target_unit=None, game_map=None) -> bool:
        if target_unit is None:
            return False
        if game_map is None:
            try:
                game_map = getattr(getattr(self.get_parent_army(), "player", None), "game", None).map
            except Exception:
                game_map = None
        objectives = list(getattr(game_map, "objectives", []) or []) if game_map is not None else []
        if not objectives:
            return False
        try:
            if bool(getattr(target_unit, "is_embarked", False)) or target_unit.is_in_reserves():
                return False
        except Exception:
            pass
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None:
                loc = obj
            try:
                if target_unit.is_within_objective_range(loc):
                    return True
            except Exception:
                continue
            try:
                models = list(target_unit.get_models_for_collision() or [])
            except Exception:
                models = list(getattr(target_unit, "models", []) or [])
            models = [m for m in models if bool(getattr(m, "is_alive", True))]
            if not models:
                continue
            try:
                from shapely.geometry import Point as _ShPoint
                area = _ShPoint(loc.x, loc.y).buffer(float(getattr(loc, "control_radius", 0.0) or 0.0))
            except Exception:
                area = None
            for model in models:
                try:
                    if area is not None:
                        base = model.model_base.get_base_shape()
                        if base.intersects(area):
                            return True
                except Exception:
                    pass
                try:
                    pos = model.get_location()
                except Exception:
                    pos = None
                if not pos:
                    continue
                try:
                    dx = float(pos[0]) - float(getattr(loc, "x", 0.0))
                    dy = float(pos[1]) - float(getattr(loc, "y", 0.0))
                    radius = float(getattr(loc, "control_radius", 0.0) or 0.0)
                    base_r = float(getattr(model.model_base, "get_radius", lambda: 1.0)())
                    if (dx * dx + dy * dy) ** 0.5 <= (radius + base_r):
                        return True
                except Exception:
                    continue
        return False

    def can_reroll_advance_roll(self) -> bool:
        """
        Best-effort detection for abilities that allow re-rolling Advance rolls for this unit/model.

        This is intentionally text-based so it can support multiple datasheets without hardcoding.
        """
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "prioritised_efficiency", None) if army is not None else None
            if mgr is not None and getattr(mgr, "_army_has_rule", lambda: False)() and getattr(mgr, "_unit_in_army", lambda _u: False)(self):
                if getattr(mgr, "is_hostile_acquisition", lambda: False)():
                    return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "emperors_children", None) if army is not None else None
            if mgr is not None and getattr(mgr, "quicksilver_grace_applies", lambda _u: False)(self):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_reroll_advance"):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bondsman_reroll_advance"):
                return True
        except Exception:
            pass
        try:
            for u in list(self.get_attached_unit_members() or []):
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if sr.get("enhancement_reroll_advance") or sr.get("enhancement_reroll_advance_charge"):
                    return True
        except Exception:
            pass
        try:
            iter_fn = getattr(self, "_iter_attached_unit_reroll_texts", None)
            if callable(iter_fn):
                for text in iter_fn():
                    low = text.lower()
                    if self._REROLL_ADVANCE_CHARGE_RE.search(low):
                        return True
                    if ("re-roll" in low or "reroll" in low) and "advance roll" in low:
                        if "bearer's unit" in low or "this model" in low or "that unit" in low:
                            return True
        except Exception:
            pass
        for t in Unit._iter_reroll_scan_texts(self):
            s = str(t or "").lower()
            if ("re-roll" in s or "reroll" in s) and "advance" in s:
                return True
        return False

    def _filter_internal_rivalries_roll_modifiers(self, modifiers, *, kind: str) -> list[tuple[int, str]]:
        if not modifiers:
            return list(modifiers or [])
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "emperors_children", None) if army is not None else None
            if mgr is None or not getattr(mgr, "internal_rivalries_applies", lambda _u: False)(self):
                return list(modifiers or [])
        except Exception:
            return list(modifiers or [])

        kept = []
        ignored = []
        for val, source in list(modifiers or []):
            try:
                v = int(val or 0)
            except Exception:
                v = 0
            if v < 0:
                ignored.append((v, source))
            else:
                kept.append((v, source))

        if ignored:
            try:
                sr = getattr(self, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                ignored_sources = tuple(sorted(str(s or "") for _v, s in ignored if str(s or "").strip()))
                kept_sources = tuple(sorted(str(s or "") for _v, s in kept if str(s or "").strip()))
                sig = (ignored_sources, kept_sources)
                key = f"internal_rivalries_{str(kind or '').strip().lower()}_mod_signature"
                if sr.get(key) != sig:
                    sr[key] = sig
                    self.special_rules = sr
                    from ..utility.event_bus import append_action
                    pn = self.get_parent_army().player
                    label = "Advance roll" if str(kind or "").strip().lower() == "advance" else "Charge roll"
                    ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                    append_action(pn, f"Internal Rivalries: ignored negative {label} modifiers ({ignored_text}).")
                    if kept_sources:
                        kept_text = ", ".join(s for s in kept_sources if s)
                        if kept_text:
                            append_action(pn, f"Internal Rivalries: applied {label} modifiers ({kept_text}).")
            except Exception:
                pass

        return kept

    def _filter_driven_by_ultimate_rage_roll_modifiers(self, modifiers, *, kind: str) -> list[tuple[int, str]]:
        if not modifiers:
            return list(modifiers or [])
        try:
            from ..rules.wrathful_presence import driven_by_ultimate_rage_applies
            if not driven_by_ultimate_rage_applies(self):
                return list(modifiers or [])
        except Exception:
            return list(modifiers or [])

        kept = []
        ignored = []
        for val, source in list(modifiers or []):
            try:
                v = int(val or 0)
            except Exception:
                v = 0
            if v < 0:
                ignored.append((v, source))
            else:
                kept.append((v, source))

        if ignored:
            try:
                sr = getattr(self, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                ignored_sources = tuple(sorted(str(s or "") for _v, s in ignored if str(s or "").strip()))
                kept_sources = tuple(sorted(str(s or "") for _v, s in kept if str(s or "").strip()))
                sig = (ignored_sources, kept_sources)
                key = f"driven_by_ultimate_rage_{str(kind or '').strip().lower()}_mod_signature"
                if sr.get(key) != sig:
                    sr[key] = sig
                    self.special_rules = sr
                    from ..utility.event_bus import append_action
                    pn = self.get_parent_army().player
                    label = "Advance roll" if str(kind or "").strip().lower() == "advance" else "Charge roll"
                    ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                    append_action(pn, f"Driven by Ultimate Rage: ignored negative {label} modifiers ({ignored_text}).")
                    if kept_sources:
                        kept_text = ", ".join(s for s in kept_sources if s)
                        if kept_text:
                            append_action(pn, f"Driven by Ultimate Rage: applied {label} modifiers ({kept_text}).")
            except Exception:
                pass

        return kept

    def _collect_advance_roll_modifiers(self) -> list[tuple[int, str]]:
        mods: list[tuple[int, str]] = []
        sr = getattr(self, "special_rules", None)
        try:
            bonus = int(sr.get("code_chivalric_advance_bonus", 0) or 0) if isinstance(sr, dict) else 0
        except Exception:
            bonus = 0
        if bonus:
            mods.append((bonus, "Code Chivalric"))
        if isinstance(sr, dict):
            try:
                extra = int(sr.get("advance_roll_modifier", 0) or 0)
            except Exception:
                extra = 0
            if extra:
                mods.append((extra, "Advance roll modifier"))
            try:
                extra_list = sr.get("advance_roll_modifiers", None)
            except Exception:
                extra_list = None
            if isinstance(extra_list, list):
                for item in extra_list:
                    try:
                        if isinstance(item, (list, tuple)) and len(item) >= 1:
                            val = int(item[0] or 0)
                            source = str(item[1] if len(item) > 1 else "Advance roll modifier")
                        elif isinstance(item, dict):
                            val = int(item.get("value", 0) or 0)
                            source = str(item.get("source", "") or "Advance roll modifier")
                        else:
                            val = int(item or 0)
                            source = "Advance roll modifier"
                    except Exception:
                        continue
                    if val:
                        mods.append((val, source))
        try:
            from ..utility.aura_effects import get_aura_advance_charge_roll_modifiers
            aura_mods, _ = get_aura_advance_charge_roll_modifiers(self)
            for val, source in list(aura_mods or []):
                if val:
                    mods.append((int(val), source))
        except Exception:
            pass
        return mods

    def _apply_advance_roll_modifiers(self, roll: int) -> int:
        mods = self._collect_advance_roll_modifiers()
        mods = self._filter_internal_rivalries_roll_modifiers(mods, kind="advance")
        mods = self._filter_driven_by_ultimate_rage_roll_modifiers(mods, kind="advance")
        for val, source in mods:
            if not val:
                continue
            roll += int(val)
            try:
                if val > 0:
                    print(f"{self.name} advance bonus: +{val}\" ({source})")
                else:
                    print(f"{self.name} advance penalty: {val}\" ({source})")
            except Exception:
                pass
        return int(roll)

    def _is_charge_target_closest_eligible(self, target_unit, *, game_map=None, game=None) -> bool:
        if target_unit is None:
            return False
        if game is None:
            try:
                game = self.get_parent_army().player.game
            except Exception:
                game = None
        if game_map is None:
            try:
                game_map = getattr(game, "map", None)
            except Exception:
                game_map = None
        if game_map is None or game is None:
            return False

        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit

        try:
            if not self.can_declare_charge_against(target_root, game, out_of_turn=True):
                return False
        except Exception:
            return False

        try:
            target_dist = float(game_map.get_distance_between_units(self, target_root))
        except Exception:
            target_dist = None
        if target_dist is None:
            return False

        enemies = None
        try:
            player = self.get_parent_army().player
        except Exception:
            player = None
        if player is not None and game is not None:
            try:
                enemies = list(game.get_enemy_units(player) or [])
            except Exception:
                enemies = None
        if enemies is None:
            try:
                enemies = list(game_map.get_enemy_units(self) or [])
            except Exception:
                enemies = []

        if not enemies:
            return False

        closest = None
        seen = set()
        for enemy_unit in enemies:
            try:
                root = enemy_unit.get_attached_unit_root()
            except Exception:
                root = enemy_unit
            if root is None:
                continue
            rid = get_entity_id(root)
            if rid in seen:
                continue
            seen.add(rid)
            try:
                if hasattr(root, "is_alive") and callable(root.is_alive) and not root.is_alive():
                    continue
            except Exception:
                pass
            try:
                if hasattr(root, "deployed") and not bool(getattr(root, "deployed", True)):
                    continue
            except Exception:
                pass
            try:
                if not self.can_declare_charge_against(root, game, out_of_turn=True):
                    continue
            except Exception:
                continue
            try:
                dist = float(game_map.get_distance_between_units(self, root))
            except Exception:
                continue
            if closest is None or dist < closest:
                closest = dist

        if closest is None:
            return False
        return target_dist <= closest + 1e-6

    def can_reroll_charge_roll(self, *, target_unit=None, game_map=None, game=None) -> bool:
        """
        Best-effort detection for abilities that allow re-rolling Charge rolls for this unit/model.
        """
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "prioritised_efficiency", None) if army is not None else None
            if mgr is not None and getattr(mgr, "_army_has_rule", lambda: False)() and getattr(mgr, "_unit_in_army", lambda _u: False)(self):
                if getattr(mgr, "is_hostile_acquisition", lambda: False)():
                    return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_charge_reroll"):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_reroll_charge"):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bondsman_reroll_charge"):
                return True
        except Exception:
            pass
        try:
            enh = getattr(self, "enhancement", None)
            if enh is not None and str(getattr(enh, "name", "") or "").strip().lower() == "battle-lust":
                return True
        except Exception:
            pass
        conditional_found = False
        try:
            for u in list(self.get_attached_unit_members() or []):
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if sr.get("enhancement_charge_reroll"):
                    return True
                if sr.get("enhancement_charge_reroll_on_setup_turn"):
                    conditional_found = True
                    if self._was_set_up_this_turn(game=game):
                        return True
                if sr.get("enhancement_charge_reroll_if_target_on_objective"):
                    conditional_found = True
                    if self._target_within_objective_range(target_unit, game_map):
                        return True
        except Exception:
            pass

        try:
            iter_fn = getattr(self, "_iter_attached_unit_reroll_texts", None)
            if callable(iter_fn):
                for text in iter_fn():
                    low = text.lower()
                    if self._REROLL_CHARGE_OBJECTIVE_RE.search(low):
                        conditional_found = True
                        if self._target_within_objective_range(target_unit, game_map):
                            return True
                        continue
                    if self._REROLL_CHARGE_SETUP_TURN_RE.search(low):
                        conditional_found = True
                        if self._was_set_up_this_turn(game=game):
                            return True
                        continue
                    if self._REROLL_CHARGE_CLOSEST_ELIGIBLE_RE.search(low):
                        conditional_found = True
                        if self._is_charge_target_closest_eligible(
                            target_unit,
                            game_map=game_map,
                            game=game,
                        ):
                            return True
                        continue
                    if self._REROLL_ADVANCE_CHARGE_RE.search(low):
                        return True
                    if self._REROLL_CHARGE_BEARER_UNIT_RE.search(low):
                        return True
        except Exception:
            pass

        if conditional_found:
            return False

        for t in Unit._iter_reroll_scan_texts(self):
            s = self._normalize_rules_text(str(t or "")).lower()
            if ("re-roll" in s or "reroll" in s) and "charge" in s:
                return True
        return False

    def _charge_roll_target_strength_specs(self) -> list[dict]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "charge_roll_target_strength_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, int, int]] = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                text_src = self._strip_eligibility_prefix(text_src)
                normalized = self._normalize_rules_text(text_src)
                normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = normalized.lower()
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                m = self._CHARGE_ROLL_TARGET_STRENGTH_BONUS_RE.fullmatch(normalized)
                if not m:
                    continue
                try:
                    base_bonus = int(m.group("base") or 0)
                except Exception:
                    base_bonus = 0
                try:
                    half_bonus = int(m.group("half") or 0)
                except Exception:
                    half_bonus = 0
                source = str(name or "Charge roll bonus").strip() or "Charge roll bonus"
                key = (source.lower(), base_bonus, half_bonus)
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"base_bonus": base_bonus, "half_bonus": half_bonus, "source": source})

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def get_charge_roll_target_strength_modifiers(self, target_units=None) -> list[tuple[int, str]]:
        specs = self._charge_roll_target_strength_specs()
        if not specs:
            return []
        if target_units is None:
            return []
        targets = list(target_units) if isinstance(target_units, (list, tuple, set)) else [target_units]
        if not targets:
            return []

        has_below_start = False
        has_below_half = False
        for target in targets:
            if target is None:
                continue
            try:
                root = target.get_attached_unit_root()
            except Exception:
                root = target
            if root is None:
                continue
            try:
                if root.is_below_half_strength():
                    has_below_half = True
            except Exception:
                pass
            try:
                if root.is_below_starting_strength():
                    has_below_start = True
            except Exception:
                pass

        if not has_below_half and not has_below_start:
            return []

        modifiers: list[tuple[int, str]] = []
        for spec in specs:
            if has_below_half and int(spec.get("half_bonus", 0) or 0):
                modifiers.append((int(spec.get("half_bonus", 0) or 0), spec.get("source", "Charge roll bonus")))
            elif has_below_start and int(spec.get("base_bonus", 0) or 0):
                modifiers.append((int(spec.get("base_bonus", 0) or 0), spec.get("source", "Charge roll bonus")))
        return modifiers

    def register_wargear_charge_keyword_hit(
        self,
        target_unit: 'Unit',
        keyword: str,
        *,
        no_overwatch: bool = False,
        game: Optional['Game'] = None,
    ) -> bool:
        """Track charge/Overwatch effects from wargear keyword hits against a target unit."""
        if target_unit is None:
            return False
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
            self.special_rules = sr

        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        target_id = get_entity_id(target_root)

        hits = sr.get("wargear_charge_keyword_hits")
        if not isinstance(hits, dict):
            hits = {}

        entry = dict(hits.get(target_id) or {})
        keywords = set(entry.get("keywords", []) or [])
        key_norm = str(keyword or "").strip().lower()
        if key_norm:
            keywords.add(key_norm)

        updated = False
        prev_bonus = int(entry.get("charge_bonus", 0) or 0)
        if prev_bonus < 2:
            entry["charge_bonus"] = 2
            updated = True
        if no_overwatch and not bool(entry.get("no_overwatch", False)):
            entry["no_overwatch"] = True
            updated = True
        if keywords != set(entry.get("keywords", []) or []):
            entry["keywords"] = sorted(keywords)
            updated = True

        hits[target_id] = entry
        sr["wargear_charge_keyword_hits"] = hits

        owner_id = ""
        if game is not None:
            getter = getattr(game, "get_current_player", None)
            if callable(getter):
                current_player = getter()
                if current_player is not None:
                    owner_id = get_entity_id(current_player)
        if not owner_id:
            army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
            player = getattr(army, "player", None)
            if player is not None:
                owner_id = get_entity_id(player)
        if owner_id:
            sr["wargear_charge_keyword_hits_turn_owner"] = owner_id
        if game is not None:
            sr["wargear_charge_keyword_hits_turn"] = int(getattr(game, "turn", 0) or 0)
        return updated

    def _get_wargear_charge_keyword_effects(self, target_unit: 'Unit', *, game: Optional['Game'] = None) -> Optional[dict]:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return None
        hits = sr.get("wargear_charge_keyword_hits")
        if not isinstance(hits, dict) or target_unit is None:
            return None
        if game is not None:
            owner_id = str(sr.get("wargear_charge_keyword_hits_turn_owner", "") or "")
            if owner_id:
                getter = getattr(game, "get_current_player", None)
                if callable(getter):
                    current = getter()
                    if current is None or get_entity_id(current) != owner_id:
                        return None
        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        target_id = get_entity_id(target_root)
        entry = hits.get(target_id)
        if not isinstance(entry, dict):
            return None
        return entry

    def get_wargear_charge_keyword_modifiers(self, target_unit: 'Unit', *, game: Optional['Game'] = None) -> list[tuple[int, str]]:
        entry = self._get_wargear_charge_keyword_effects(target_unit, game=game)
        if not entry:
            return []
        bonus = int(entry.get("charge_bonus", 0) or 0)
        if not bonus:
            return []
        keywords = [str(k) for k in (entry.get("keywords", []) or []) if str(k or "").strip()]
        if keywords:
            label = "/".join([k.title() for k in keywords])
            source = f"{label} (wargear)"
        else:
            source = "Wargear keyword (charge bonus)"
        return [(bonus, source)]

    def is_overwatch_prevented_against(self, target_unit: 'Unit', *, game: Optional['Game'] = None) -> bool:
        entry = self._get_wargear_charge_keyword_effects(target_unit, game=game)
        if not entry:
            return False
        return bool(entry.get("no_overwatch", False))

    def has_thrill_seekers(self) -> bool:
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    nm = ab
                else:
                    nm = getattr(ab, "name", "")
                if "thrill seekers" in str(nm or "").lower():
                    return True
            except Exception:
                continue
        return False

    def _is_shadow_legion_detachment(self) -> bool:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        if mgr is not None:
            try:
                return bool(mgr.is_shadow_legion_detachment())
            except Exception:
                return False
        return False

    def _is_legion_of_excess_detachment(self) -> bool:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        if mgr is not None:
            try:
                return bool(mgr.is_legion_of_excess_detachment())
            except Exception:
                return False
        return False

    def _is_daemonic_incursion_detachment(self) -> bool:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        if mgr is not None:
            try:
                return bool(mgr.is_daemonic_incursion_detachment())
            except Exception:
                return False
        return False

    def _first_prince_of_chaos_active(self) -> bool:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        if mgr is not None:
            try:
                return bool(mgr.first_prince_of_chaos_active())
            except Exception:
                return False
        return False

    def _first_prince_has_god_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip()
        if not kw:
            return False
        try:
            if self.has_any_keyword(kw):
                return True
        except Exception:
            pass
        return False

    def has_first_prince_tzeentch_defense(self) -> bool:
        return self._first_prince_of_chaos_active() and self._first_prince_has_god_keyword("TZEENTCH")

    def has_first_prince_nurgle_defense(self) -> bool:
        return self._first_prince_of_chaos_active() and self._first_prince_has_god_keyword("NURGLE")

    def has_first_prince_slaanesh_no_overwatch(self) -> bool:
        return self._first_prince_of_chaos_active() and self._first_prince_has_god_keyword("SLAANESH")

    def _is_belakor(self) -> bool:
        name = str(getattr(self, "name", "") or "").lower().replace("\u2019", "'")
        return "belakor" in name or "be'lakor" in name

    def _is_chaos_undivided(self) -> bool:
        try:
            if self.has_any_keyword("UNIDIVIDED") or self.has_any_keyword("CHAOS UNDIVIDED"):
                return True
        except Exception:
            pass
        return self._is_belakor()

    def has_dark_pacts(self) -> bool:
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    nm = ab
                else:
                    nm = getattr(ab, "name", "")
                if "dark pacts" in str(nm or "").lower():
                    return True
            except Exception:
                continue
        return False

    def has_cabal_of_sorcerers(self) -> bool:
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    nm = ab
                else:
                    nm = getattr(ab, "name", "")
                if "cabal of sorcerers" in str(nm or "").lower():
                    return True
            except Exception:
                continue
        return False

    def has_martial_katah(self) -> bool:
        if "martial_katah" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["martial_katah"])

        def _norm(text: str) -> str:
            return str(text or "").replace("\u2019", "'").replace("\u0192?T", "'").lower()

        patterns = ("martial ka'tah", "martial katah")
        found = False
        for ab in self._iter_active_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = getattr(ab, "name", "") or ""
                    desc = getattr(ab, "description", "") or ""
                text = _norm(f"{name} {desc}")
                if any(p in text for p in patterns):
                    found = True
                    break
            except Exception:
                continue

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["martial_katah"] = found
        return found

    def can_use_dark_pacts(self) -> bool:
        has_pacts = self.has_dark_pacts()
        first_prince = self._first_prince_of_chaos_active() and self._is_chaos_undivided()
        if not has_pacts and not first_prince:
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return True
        fid = str(getattr(army, "faction_id", "") or "").strip().upper()
        if fid and fid != "CSM" and not first_prince:
            return False
        return True

    def _auto_pass_dark_pacts_test(self) -> bool:
        return self._first_prince_of_chaos_active() and self._is_belakor()

    def apply_dark_pacts_choice(self, game, *, choice: str, phase_name: str, trigger: str) -> bool:
        trigger_norm = str(trigger or "").strip().lower()
        if trigger_norm not in ("shooting", "fight"):
            return False
        if not self.can_use_dark_pacts():
            return False
        choice_norm = str(choice or "").strip().upper()
        options = ("LETHAL HITS", "SUSTAINED HITS 1")
        if choice_norm not in options:
            return False
        passed = True
        if not self._auto_pass_dark_pacts_test():
            try:
                passed = bool(self.pass_leadership_check())
            except Exception:
                passed = False
        if not passed:
            try:
                from ..utility.dice import DiceCollection
                dmg_roll, _dice = DiceCollection.from_string("D3").roll_detailed()
                self._apply_mortal_wounds_to_unit(self, int(dmg_roll or 0), game_map=getattr(game, "map", None))
            except Exception:
                pass
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["dark_pacts_active"] = True
        sr["dark_pacts_choice"] = choice_norm
        sr["dark_pacts_expires_phase"] = str(phase_name or "").strip().upper() or "FIGHT_PHASE"
        self.special_rules = sr
        return True

    def maybe_trigger_dark_pacts(self, game, *, phase_name: str, trigger: str) -> None:
        trigger_norm = str(trigger or "").strip().lower()
        if trigger_norm not in ("shooting", "fight"):
            return
        if not self.can_use_dark_pacts():
            return
        try:
            player = self.get_parent_army().player
        except Exception:
            player = None
        if player is None:
            return
        ctx = {
            "unit": getattr(self, "name", "") or "",
            "phase": phase_name,
            "trigger": trigger,
        }
        if not player._should_use_optional_ability("DARK_PACTS", ctx):
            return
        options = ["LETHAL HITS", "SUSTAINED HITS 1"]
        choice = player._choose_optional_value("DARK_PACTS_CHOICE", options, ctx)
        if not choice:
            return
        self.apply_dark_pacts_choice(game, choice=str(choice), phase_name=phase_name, trigger=trigger)

    def prepare_advance(self) -> int:
        """Pre-roll advance dice for UI display. Returns the advance roll."""
        if not hasattr(self.round_state, 'advance_roll') or self.round_state.advance_roll is None:
            advance_roll = None
            miracle_used = False
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict) and sr.get("pain_advance_no_roll"):
                    fixed = int(sr.get("pain_advance_fixed_bonus", 0) or 0)
                    self.round_state.advance_roll = fixed
                    try:
                        from ..utility.event_bus import append_dice
                        pn = self.get_parent_army().player
                        append_dice(pn, f"Advance roll fixed: {fixed} for {self.name}")
                    except Exception:
                        pass
                    return fixed
            except Exception:
                pass
            try:
                army = self.get_parent_army()
                mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                if mgr is not None and mgr.can_use_act_of_faith(self, game=game):
                    advance_roll, _dice, miracle_used = mgr.resolve_roll(
                        self,
                        roll_type="advance",
                        game=game,
                        dice_count=1,
                        die_faces=6,
                    )
            except Exception:
                advance_roll = None
                miracle_used = False
            if advance_roll is None:
                advance_roll = get_roll("D6")
            try:
                from ..utility.event_bus import append_dice
                pn = self.get_parent_army().player
                if miracle_used:
                    append_dice(pn, f"Miracle die used for Advance roll: {advance_roll} for {self.name}")
                else:
                    append_dice(pn, f"Advance roll: {advance_roll} for {self.name}")
            except Exception:
                pass
            # Apply advance roll modifiers (includes Code Chivalric, etc).
            try:
                advance_roll = self._apply_advance_roll_modifiers(int(advance_roll))
            except Exception:
                pass
            # Provide reroll callback (may be used by rules/stratagems)
            try:
                _player = getattr(self.get_parent_army(), 'player', None)
                _game = getattr(_player, 'game', None) if _player else None
                if _game and hasattr(_game, 'event_system'):
                    def _reroll():
                        new_roll = get_roll("D6")
                        self.round_state.advance_roll = new_roll
                        try:
                            from ..utility.event_bus import append_dice as _append
                            _append(_player, f"Advance re-roll: {new_roll} for {self.name}")
                        except Exception:
                            pass
                        print(f"{self.name} advance re-roll: {new_roll}")
                        return new_roll
                    # If this unit has a rule-based reroll (e.g., "re-roll Advance rolls"),
                    # offer it via a blocking provider BEFORE publishing roll_made for Command Re-roll.
                    reroll_used = False
                    try:
                        provider = getattr(getattr(_game, "map", None), "roll_reroll_provider", None)
                        is_human = self._player_has_local_control(_player)
                        if is_human and callable(provider) and self.can_reroll_advance_roll():
                            want = bool(provider(player=_player, unit=self, roll_type="advance", value=advance_roll, dice=None))
                            if want:
                                advance_roll = _reroll()
                                reroll_used = True
                    except Exception:
                        reroll_used = False

                    # Store final value
                    self.round_state.advance_roll = advance_roll
                    print(f"{self.name} advance roll: {advance_roll}\" (Move {self.movement}\" + {advance_roll}\" = {self.movement + advance_roll}\")")

                    # Publish roll event (reroll may be locked if already used)
                    from ..utility.reroll_tracker import prepare_reroll_event
                    roll_id, reroll_cb, reroll_locked = prepare_reroll_event(
                        _game,
                        _reroll,
                        reroll_used=bool(reroll_used),
                        used_result=advance_roll,
                    )
                    _game.event_system.publish(
                        "roll_made",
                        player=_player,
                        unit=self,
                        roll_type="advance",
                        value=advance_roll,
                        reroll=reroll_cb,
                        reroll_locked=bool(reroll_locked),
                        roll_id=roll_id,
                        miracle_used=bool(miracle_used),
                    )
            except Exception:
                pass
            # Ensure stored even if no game/event_system
            self.round_state.advance_roll = advance_roll
            print(f"{self.name} advance roll: {advance_roll}\" (Move {self.movement}\" + {advance_roll}\" = {self.movement + advance_roll}\")")
            return advance_roll
        return self.round_state.advance_roll

    def get_advance_roll(self) -> int:
        """Get the current advance roll, or None if not rolled yet."""
        return getattr(self.round_state, 'advance_roll', None)

    def _path_crosses_tall_terrain(self, path, game_map, *, height_threshold: float = 4.0) -> bool:
        try:
            from shapely.geometry import LineString
        except Exception:
            return False
        if game_map is None:
            return False
        try:
            terrain_features = list(getattr(game_map, "terrain_features", []) or [])
        except Exception:
            terrain_features = []
        if not terrain_features:
            return False

        for i in range(1, len(path or [])):
            try:
                x0, y0 = float(path[i - 1][0]), float(path[i - 1][1])
                x1, y1 = float(path[i][0]), float(path[i][1])
            except Exception:
                continue
            seg = LineString([(x0, y0), (x1, y1)])
            for terrain in terrain_features:
                footprint = getattr(terrain, "footprint", None)
                if footprint is None:
                    continue
                try:
                    if not seg.intersects(footprint):
                        continue
                except Exception:
                    continue

                walls = getattr(terrain, "walls", None)
                if walls:
                    for wall in list(walls or []):
                        try:
                            poly = wall.get("polygon", None)
                            if poly is None or not seg.intersects(poly):
                                continue
                            z0 = float(wall.get("z_bottom", 0.0) or 0.0)
                            z1 = float(wall.get("z_top", 0.0) or 0.0)
                            if (z1 - z0) > height_threshold:
                                return True
                        except Exception:
                            continue

                feature_height = None
                try:
                    if hasattr(terrain, "height"):
                        feature_height = float(getattr(terrain, "height", 0.0) or 0.0)
                    elif hasattr(terrain, "rim_height"):
                        feature_height = float(getattr(terrain, "rim_height", 0.0) or 0.0)
                    elif hasattr(terrain, "bounding_box") and isinstance(terrain.bounding_box, dict):
                        max_z = float(terrain.bounding_box.get("max", (0.0, 0.0, 0.0))[2] or 0.0)
                        min_z = float(terrain.bounding_box.get("min", (0.0, 0.0, 0.0))[2] or 0.0)
                        feature_height = max_z - min_z
                except Exception:
                    feature_height = None
                if feature_height is not None and feature_height > height_threshold:
                    return True

        return False

    def _apply_super_heavy_walker_terrain_shock(self, game_map, *, action: str) -> None:
        if action not in ("move", "advance", "fall_back"):
            return
        if not self.has_super_heavy_walker():
            return
        if game_map is None:
            return

        any_crossed = False
        for model in list(getattr(self, "models", []) or []):
            try:
                if not getattr(model, "is_alive", True):
                    continue
            except Exception:
                continue
            path = getattr(model, "last_move_path", None)
            if not path or len(path) < 2:
                continue
            if self._path_crosses_tall_terrain(path, game_map, height_threshold=4.0):
                any_crossed = True
                break

        if not any_crossed:
            return

        roll = int(get_roll("D6"))
        try:
            from ..utility.event_bus import append_dice
            pn = self.get_parent_army().player
            append_dice(pn, f"Super-heavy Walker terrain roll: {roll} for {self.name}")
        except Exception:
            pass
        if roll != 1:
            return

        try:
            game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            current_turn = int(getattr(game, "turn", 1) or 1) if game is not None else 1
        except Exception:
            current_turn = 1

        try:
            if not self.is_battle_shocked():
                self.apply_status_effect(BattleShockEffect(current_turn))
        except Exception:
            pass
        print(f"{self.name} is battle-shocked after moving through tall terrain (Super-heavy Walker).")

    def advance(self, destination: Tuple[float, float, float], game_map: 'Map') -> bool:
        if bool(getattr(self, "is_aircraft", False)):
            print(f"{self.name} cannot Advance (AIRCRAFT)")
            return False
        # Check if unit can advance after arriving from reserves
        if self.arrived_from_reserves_this_turn and not self.can_advance_after_arriving_from_reserves():
            logger.info(f"{self.name} cannot advance - arrived from reserves this turn")
            return False
        return self.move(destination, game_map, advance=True)

    def _aircraft_normal_move(
        self,
        destination: Tuple[float, float, float],
        game_map: 'Map',
        *,
        pivot_degrees: Optional[float] = None,
    ) -> bool:
        """Resolve AIRCRAFT Normal move (straight line, minimum 20", no max; optional post-move pivot)."""
        if not self.models:
            logger.error(f"Cannot move unit {self.name}: no models in unit")
            return False

        # Check if unit can move after arriving from reserves
        if self.arrived_from_reserves_this_turn and not self.can_move_after_arriving_from_reserves():
            logger.info(f"{self.name} cannot move - arrived from reserves this turn")
            return False

        # Use first alive model as reference
        model = next((m for m in self.models if getattr(m, "is_alive", False)), None)
        if model is None:
            logger.error(f"Cannot move unit {self.name}: no valid models")
            return False

        start_pos = model.get_location()
        if not start_pos:
            logger.error(f"Cannot move unit {self.name}: first model has no position")
            return False

        try:
            dest_x = float(destination[0])
            dest_y = float(destination[1])
        except Exception:
            logger.error(f"Cannot move unit {self.name}: invalid destination")
            return False

        start_x, start_y = float(start_pos[0]), float(start_pos[1])
        start_z = float(start_pos[2]) if len(start_pos) > 2 else 0.0

        facing = float(getattr(model.model_base, "facing", 0.0) or 0.0)
        # Facing 0 points along +Y (consistent with get_angle usage)
        forward_x = math.sin(facing)
        forward_y = math.cos(facing)

        dx = dest_x - start_x
        dy = dest_y - start_y
        forward_dist = (dx * forward_x) + (dy * forward_y)
        # Lateral offset (perpendicular to facing)
        side_dist = (dx * forward_y) - (dy * forward_x)

        # Straight-line requirement
        if forward_dist <= 1e-6:
            print(f"{self.name} must move forward (AIRCRAFT)")
            return False
        if abs(side_dist) > 0.25:
            print(f"{self.name} must move straight forward (AIRCRAFT)")
            return False

        min_move = 20.0

        # Helper: required forward distance for base-to-base >= min_move
        def _required_forward_distance_for_model(m) -> float:
            from ..utility.aura_utils import horizontal_distance_between_bases_2d
            base_start = m.model_base
            # Expand search window until requirement satisfied (should converge quickly)
            hi = max(min_move, 1.0)
            for _ in range(16):
                test_base = self._create_potential_base(
                    base_start.x + forward_x * hi,
                    base_start.y + forward_y * hi,
                    base_start.z,
                    facing,
                    model=m,
                )
                if float(horizontal_distance_between_bases_2d(base_start, test_base)) >= min_move:
                    break
                hi *= 1.5
            lo = 0.0
            for _ in range(20):
                mid = (lo + hi) / 2.0
                test_base = self._create_potential_base(
                    base_start.x + forward_x * mid,
                    base_start.y + forward_y * mid,
                    base_start.z,
                    facing,
                    model=m,
                )
                if float(horizontal_distance_between_bases_2d(base_start, test_base)) >= min_move:
                    hi = mid
                else:
                    lo = mid
            return float(hi)

        # Compute minimum forward distance required for all models (base-to-base >= 20")
        required_forward = 0.0
        for m in self.models:
            if not getattr(m, "is_alive", False):
                continue
            try:
                required_forward = max(required_forward, _required_forward_distance_for_model(m))
            except Exception:
                required_forward = max(required_forward, min_move)

        def _forward_move_within_boundary(dist: float) -> bool:
            if game_map is None:
                return True
            for m in self.models:
                if not getattr(m, "is_alive", False):
                    continue
                new_x = float(m.model_base.x) + forward_x * dist
                new_y = float(m.model_base.y) + forward_y * dist
                if not game_map.is_within_boundary(m, (new_x, new_y)):
                    return False
            return True

        def _send_to_strategic_reserves(reason: str) -> bool:
            try:
                if hasattr(self, "set_reserve_status"):
                    self.set_reserve_status("strategic_reserves")
                else:
                    self.reserve_status = "strategic_reserves"
            except Exception:
                pass
            try:
                if hasattr(self, "mark_entered_reserves_midgame"):
                    game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                    self.mark_entered_reserves_midgame(game=game)
            except Exception:
                pass
            try:
                self.deployed = True
                self.reserve_turn_deployed = None
                self.arrived_from_reserves_this_turn = False
            except Exception:
                pass
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            except Exception:
                current_turn = 0
            try:
                if current_turn > 0:
                    setattr(self, "_aircraft_return_turn", current_turn + 1)
            except Exception:
                pass
            try:
                if game_map is not None and hasattr(game_map, "units") and self in game_map.units:
                    game_map.units.remove(self)
            except Exception:
                pass
            if reason:
                print(f"{self.name} placed into Strategic Reserves ({reason})")
            else:
                print(f"{self.name} placed into Strategic Reserves")
            return True

        # Minimum Move enforcement
        if forward_dist + 1e-6 < required_forward:
            if not _forward_move_within_boundary(required_forward):
                return _send_to_strategic_reserves("minimum move impossible")
            return _send_to_strategic_reserves("minimum move not met")

        # Leaving the battlefield -> Strategic Reserves
        if not _forward_move_within_boundary(forward_dist):
            return _send_to_strategic_reserves("left the battlefield")

        move_dx = forward_x * forward_dist
        move_dy = forward_y * forward_dist

        # Build proposed positions
        proposed = []
        for m in self.models:
            if not getattr(m, "is_alive", False):
                continue
            new_x = float(m.model_base.x) + move_dx
            new_y = float(m.model_base.y) + move_dy
            new_z = game_map.get_height_at_point(new_x, new_y) if game_map else float(m.model_base.z)
            proposed.append((m, new_x, new_y, new_z))

        # Final-position validation: no overlaps, no ending in engagement range
        if game_map is not None:
            for m, nx, ny, _nz in proposed:
                if game_map.check_collision_with_other_friendly_units(m, (nx, ny)):
                    print(f"{self.name} cannot move - {m.name} would overlap a friendly model")
                    return False
                if game_map.check_collision_with_other_enemy_units(m, (nx, ny)):
                    print(f"{self.name} cannot move - {m.name} would overlap an enemy model")
                    return False

            from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
            from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
            for enemy in game_map.get_enemy_units(self):
                if not enemy.is_alive() or not enemy.deployed:
                    continue
                for em in enemy.models:
                    if not getattr(em, "is_alive", False):
                        continue
                    for m, nx, ny, nz in proposed:
                        test_base = self._create_potential_base(nx, ny, nz, facing, model=m)
                        horiz = float(horizontal_distance_between_bases_2d(test_base, em.model_base))
                        vert = float(vertical_distance_between_bases(test_base, em.model_base))
                        if horiz <= ENGAGEMENT_RANGE_HORIZONTAL and vert <= ENGAGEMENT_RANGE_VERTICAL:
                            print(f"{self.name} cannot end within Engagement Range (AIRCRAFT)")
                            return False

        final_facing = facing
        if pivot_degrees is not None:
            try:
                pivot_val = float(pivot_degrees)
            except (TypeError, ValueError):
                pivot_val = 0.0
            pivot_val = max(-90.0, min(90.0, pivot_val))
            final_facing = (facing + math.radians(pivot_val)) % (2.0 * math.pi)

        # Apply movement (pivot after move is optional)
        for m, nx, ny, nz in proposed:
            try:
                m.last_move_path = [
                    (m.model_base.x, m.model_base.y, m.model_base.z, m.model_base.facing),
                    (nx, ny, nz, final_facing),
                ]
            except Exception:
                pass
            m.set_location(nx, ny, nz, final_facing)

        pivot_note = ""
        if pivot_degrees:
            try:
                pivot_note = f", pivot {float(pivot_degrees):.1f}°"
            except (TypeError, ValueError):
                pivot_note = ""
        print(
            f"{self.name} moved from ({start_x:.1f}, {start_y:.1f}) "
            f"to ({start_x + move_dx:.1f}, {start_y + move_dy:.1f}) "
            f"- distance: {forward_dist:.1f}\"{pivot_note}"
        )
        return True

    def move(
        self,
        destination: Tuple[float, float, float],
        game_map: 'Map',
        advance: bool = False,
        *,
        aircraft_pivot_degrees: Optional[float] = None,
    ) -> bool:
        """
        Moves the unit towards the destination using optimized individual model pathfinding.
        
        This method now uses the new pathfinding system that:
        1. Moves models individually using optimized pathfinding
        2. Validates coherency after all models have moved
        3. If coherency would be broken at the end of the move, the move is NOT allowed and is rolled back
        """
        if bool(getattr(self, "is_aircraft", False)):
            return self._aircraft_normal_move(destination, game_map, pivot_degrees=aircraft_pivot_degrees)
        if not self.models:
            logger.error(f"Cannot move unit {self.name}: no models in unit")
            return False
        
        # Check if unit can move after arriving from reserves
        if self.arrived_from_reserves_this_turn and not self.can_move_after_arriving_from_reserves():
            logger.info(f"{self.name} cannot move - arrived from reserves this turn")
            return False

        # Get starting position from first model for feedback
        if not self.models or not self.models[0].is_alive:
            logger.error(f"Cannot move unit {self.name}: no valid models")
            return False

        first_model = self.models[0]
        if callable(getattr(first_model, "get_location", None)):
            first_model_pos = first_model.get_location()
        else:
            base = getattr(first_model, "model_base", None)
            if base is None:
                logger.error(f"Cannot fall back unit {self.name}: missing model position")
                return False
            first_model_pos = (float(getattr(base, "x", 0.0)), float(getattr(base, "y", 0.0)), float(getattr(base, "z", 0.0)))
        if not first_model_pos:
            logger.error(f"Cannot move unit {self.name}: first model has no position")
            return False

        # Store starting position for feedback
        start_x, start_y = first_model_pos[0], first_model_pos[1]
        start_z = first_model_pos[2] if len(first_model_pos) > 2 else 0

        # BACKUP ORIGINAL POSITIONS - Critical for proper rollback on failure
        original_model_positions = []
        for model in self.models:
            original_model_positions.append(model.get_location())

        # Get the movement range from the first model (assuming all models have the same movement)
        movement_range = self.movement

        # If advancing, use stored advance roll or roll new one
        if advance:
            pain_fixed = None
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict) and sr.get("pain_advance_no_roll"):
                    pain_fixed = int(sr.get("pain_advance_fixed_bonus", 0) or 0)
            except Exception:
                pain_fixed = None

            # Use stored advance roll if available, otherwise roll new one
            if pain_fixed is not None:
                advance_roll = pain_fixed
                self.round_state.advance_roll = advance_roll
                try:
                    from ..utility.event_bus import append_dice
                    pn = self.get_parent_army().player
                    append_dice(pn, f"Advance roll fixed: {advance_roll} for {self.name}")
                except Exception:
                    pass
            elif not hasattr(self.round_state, 'advance_roll') or self.round_state.advance_roll is None:
                advance_roll = None
                miracle_used = False
                try:
                    army = self.get_parent_army()
                    mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    if mgr is not None and mgr.can_use_act_of_faith(self, game=game):
                        advance_roll, _dice, miracle_used = mgr.resolve_roll(
                            self,
                            roll_type="advance",
                            game=game,
                            dice_count=1,
                            die_faces=6,
                        )
                except Exception:
                    advance_roll = None
                    miracle_used = False
                if advance_roll is None:
                    advance_roll = get_roll("D6")
                try:
                    from ..utility.event_bus import append_dice
                    pn = self.get_parent_army().player
                    if miracle_used:
                        append_dice(pn, f"Miracle die used for Advance roll: {advance_roll} for {self.name}")
                    else:
                        append_dice(pn, f"Advance roll: {advance_roll} for {self.name}")
                except Exception:
                    pass
                # Optional rule-based reroll prompt (e.g., "re-roll Advance rolls")
                try:
                    _player = getattr(self.get_parent_army(), 'player', None)
                    _game = getattr(_player, 'game', None) if _player else None
                    def _reroll():
                        new_roll = get_roll("D6")
                        self.round_state.advance_roll = new_roll
                        try:
                            from ..utility.event_bus import append_dice as _append
                            _append(_player, f"Advance re-roll: {new_roll} for {self.name}")
                        except Exception:
                            pass
                        return new_roll
                    reroll_used = False
                    provider = getattr(getattr(_game, "map", None), "roll_reroll_provider", None)
                    is_human = self._player_has_local_control(_player)
                    if is_human and callable(provider) and self.can_reroll_advance_roll():
                        if bool(provider(player=_player, unit=self, roll_type="advance", value=advance_roll, dice=None)):
                            advance_roll = _reroll()
                            reroll_used = True
                    # Apply advance roll modifiers (includes Code Chivalric, etc).
                    try:
                        advance_roll = self._apply_advance_roll_modifiers(int(advance_roll))
                    except Exception:
                        pass
                    # Publish roll event (best-effort)
                    if _game is not None and hasattr(_game, "event_system"):
                        from ..utility.reroll_tracker import prepare_reroll_event
                        roll_id, reroll_cb, reroll_locked = prepare_reroll_event(
                            _game,
                            _reroll,
                            reroll_used=bool(reroll_used),
                            used_result=advance_roll,
                        )
                        _game.event_system.publish(
                            "roll_made",
                            player=_player,
                            unit=self,
                            roll_type="advance",
                            value=advance_roll,
                            reroll=reroll_cb,
                            reroll_locked=bool(reroll_locked),
                            roll_id=roll_id,
                            miracle_used=bool(miracle_used),
                        )
                except Exception:
                    pass
                self.round_state.advance_roll = advance_roll
                print(f"Advance roll: {advance_roll}")
            else:
                advance_roll = self.round_state.advance_roll
                print(f"Using stored advance roll: {advance_roll}")
            
            if advance_roll is None:
                logger.error(f"Failed to roll dice for advancing unit {self.name}")
                return False
            movement_range += advance_roll

        from ..utility.calcs import MovementType
        movement_type = MovementType.ADVANCE if advance else MovementType.MOVE
        # Calculate straight-line distance to destination (rules-aware)
        distance_to_destination = measure_direct_distance(
            (start_x, start_y, start_z),
            (destination[0], destination[1], destination[2]),
            self,
            movement_type,
            game_map,
        )

        # Check if destination is within movement range
        if distance_to_destination > movement_range:
            print(f"{self.name} cannot reach destination {distance_to_destination:.1f}\" away (max {'advance' if advance else 'move'}: {movement_range}\")")
            return False

        # Generate potential positions for models with reduced boundary repulsors for better formation finding
        boundary_repulsors = self._get_reduced_boundary_repulsors(game_map)
        potential_positions = self.calculate_model_positions(destination[0], destination[1], game_map, boundary_repulsors=boundary_repulsors)
        
        # Check if formation finding failed
        if potential_positions is None:
            print(f"{self.name} cannot move - no valid formation found at destination")
            return False

        # Use the new individual model pathfinding system
        from ..utility.calcs import get_individual_model_movement_path, process_unit_movement_with_coherency_check
        
        model_movements = []
        successful_moves = 0

        # Move each model individually using optimized pathfinding
        for model_index, (model, model_destination) in enumerate(zip(self.models, potential_positions)):
            model_start = model.get_location()
            logging.debug(f"Model {model._id} {model.name} attempting to move from {model_start} to {model_destination}")
            
            # Calculate straight-line distance for this model
            model_distance = measure_direct_distance(
                (model_start[0], model_start[1], model_start[2] if len(model_start) > 2 else 0.0),
                (model_destination[0], model_destination[1], model_destination[2] if len(model_destination) > 2 else 0.0),
                self,
                movement_type,
                game_map,
            )
            
            # Check if this model can reach its destination
            if model_distance > movement_range:
                print(f"Model {model._id} cannot reach destination {model_distance:.1f}\" away (max: {movement_range}\")")
                continue  # Skip this model, don't move it
            
            # Use new optimized pathfinding for individual model movement
            path = get_individual_model_movement_path(self, model_index, model_destination, game_map, movement_range)
            
            if not path:
                logger.debug(f"Model {model._id} optimized pathfinding failed - destination may violate movement rules")
                continue
            
            # Calculate path distance
            path_distance = measure_path_distance(path, self, movement_type, game_map)
            
            if path_distance > movement_range:
                print(f"Model {model._id} path distance {path_distance:.1f}\" exceeds movement {movement_range}\"")
                # Try to move as far as possible along the path
                last_node = model_start
                model.last_move_path = [last_node]
                distance_along_path = 0.0
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                
                for node in path[1:]:
                    segment_distance = movement_segment_cost(last_node, node, self, movement_type)
                    
                    if distance_along_path + segment_distance > movement_range:
                        # Stop here, can't go further
                        break
                    
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                # Move to the furthest reachable position
                if distance_along_path > 0:
                    final_position = model.last_move_path[-1]
                    model.set_location(final_position[0], final_position[1], final_position[2], final_position[3])
                    model_movements.append((model_index, model.last_move_path))
                    successful_moves += 1
                    logger.debug(f"Model {model._id} moved along path to {final_position[:3]}, distance: {distance_along_path:.1f}\"")
            else:
                # Path is within range, move to destination
                model.set_location(*model_destination)
                last_node = model_start
                model.last_move_path = [last_node]
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                distance_along_path = 0.0
                
                for node in path[1:]:
                    segment_distance = movement_segment_cost(last_node, node, self, movement_type)
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                model_movements.append((model_index, model.last_move_path))
                successful_moves += 1
                logger.debug(f"Model {model._id} moved to {model_destination}, path distance: {distance_along_path:.1f}\"")

        # Unit position is now determined by model positions
        
        # Check if any movement occurred
        if successful_moves == 0:
            print(f"{self.name} could not move - no models could reach any valid positions")
            return False

        # NEW: Validate unit coherency after all models have moved
        is_coherent, non_coherent_models = process_unit_movement_with_coherency_check(self, model_movements)
        
        if not is_coherent:
            print(f"{self.name} move rejected: unit coherency would be broken (non-coherent models: {non_coherent_models})")
            # ROLLBACK: Restore original positions (movement ending out of coherency is not allowed)
            for i, original_pos in enumerate(original_model_positions):
                if i < len(self.models):
                    self.models[i].set_location(*original_pos)
            return False
        
        # CRITICAL VALIDATION: Check for illegal overlaps after movement
        # This catches cases where models might be overlapping with enemies after movement
        if self.models and self.models[0].is_alive:
            final_position = self.models[0].get_location()
            end_x, end_y = final_position[0], final_position[1]
            end_z = final_position[2] if len(final_position) > 2 else start_z
        else:
            end_x, end_y = start_x, start_y  # Fallback to start position
            end_z = start_z
        
        # Check for base overlaps with enemy models
        enemy_units = game_map.get_enemy_units(self)
        for model in self.models:
            if not model.is_alive:
                continue
            for enemy_unit in enemy_units:
                if not enemy_unit.is_alive() or not enemy_unit.deployed:
                    continue
                for enemy_model in enemy_unit.models:
                    if not enemy_model.is_alive:
                        continue
                    # Check if this model's base overlaps with the enemy model's base
                    if model.model_base.collides_with(enemy_model.model_base):
                        print(f"{self.name} cannot move - {model.name} would overlap with {enemy_model.name} from {enemy_unit.name}")
                        # ROLLBACK: Restore original positions
                        for i, original_pos in enumerate(original_model_positions):
                            if i < len(self.models):
                                self.models[i].set_location(*original_pos)
                        return False
        
        # Calculate actual distance the unit moved (rules-aware)
        unit_distance_moved = measure_direct_distance(
            (start_x, start_y, start_z),
            (end_x, end_y, end_z),
            self,
            movement_type,
            game_map,
        )
        
        # Provide detailed feedback
        action_name = 'advanced' if advance else 'moved'
        print(f"{self.name} {action_name} from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        
        if successful_moves < len(self.models):
            print(f" Note: Only {successful_moves}/{len(self.models)} models could move to valid positions")

        logger.info(f"Unit {self.name} {action_name} from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        self.round_state.advanced_this_round = advance
        try:
            self._apply_super_heavy_walker_terrain_shock(
                game_map,
                action="advance" if advance else "move",
            )
        except Exception:
            pass
        return True

    def charge_move(
        self,
        destination: Tuple[float, float, float],
        game_map: 'Map',
        target_unit: 'Unit' = None,
        target_units: Optional[list['Unit']] = None,
    ) -> bool:
        """Special movement for charge actions that allows moving into engagement range.
        
        Unlike normal movement, charge movement:
        1. Allows models to move into engagement range of enemy units
        2. Uses relaxed collision detection for final positioning
        3. Prioritizes achieving engagement range over perfect formations
        """
        if bool(getattr(self, "is_aircraft", False)):
            print(f"{self.name} cannot declare charges (AIRCRAFT)")
            return False
        # Mission Actions: a unit performing an Action is not eligible to declare a charge
        if getattr(self.round_state, 'action_locked_until_turn_end', False):
            print(f"{self.name} is performing an Action and cannot declare a charge this turn")
            return False
        if not self.models:
            logger.error(f"Cannot charge move unit {self.name}: no models in unit")
            return False

        # Publish movement start for stratagem reaction windows (e.g. FIRE OVERWATCH).
        try:
            _player = getattr(self.get_parent_army(), 'player', None)
            _game = getattr(_player, 'game', None) if _player else None
            if _game and hasattr(_game, 'event_system'):
                _game.event_system.publish("unit_move_started", unit=self, action="charge")
        except Exception:
            pass
        
        # Get starting position from first model
        if not self.models or not self.models[0].is_alive:
            logger.error(f"Cannot charge move unit {self.name}: no valid models")
            return False

        first_model = self.models[0]
        if callable(getattr(first_model, "get_location", None)):
            first_model_pos = first_model.get_location()
        else:
            base = getattr(first_model, "model_base", None)
            if base is None:
                logger.error(f"Cannot fall back unit {self.name}: first model has no position")
                return False
            first_model_pos = (float(getattr(base, "x", 0.0)), float(getattr(base, "y", 0.0)), float(getattr(base, "z", 0.0)))
        if not first_model_pos:
            logger.error(f"Cannot charge move unit {self.name}: first model has no position")
            return False
        
        # Store starting position for feedback and rollback
        start_x, start_y = first_model_pos[0], first_model_pos[1]
        start_z = first_model_pos[2] if len(first_model_pos) > 2 else 0
        
        # Store original model positions for potential rollback
        original_model_positions = []
        for model in self.models:
            model_pos = model.get_location()
            original_model_positions.append(model_pos)
        
        # Store original model positions for potential rollback
        
        from ..utility.calcs import MovementType
        # Calculate maximum charge distance available (rules-aware)
        max_charge_distance = measure_direct_distance(
            (start_x, start_y, start_z),
            (destination[0], destination[1], destination[2]),
            self,
            MovementType.CHARGE,
            game_map,
        )
        
        targets = list(target_units or [])
        if not targets and target_unit is not None:
            targets = [target_unit]
        if not targets:
            print(f"ERROR: {self.name} cannot charge without target units.")
            return False
        if any(t is None or not t.is_alive() for t in targets):
            print(f"ERROR: {self.name} cannot charge - one or more targets are invalid.")
            return False
        # Charge toward specific target unit (primary)
        all_enemy_models = [model for model in targets[0].models if model.is_alive]
        print(f"{self.name} charging specifically toward {targets[0].name} ({len(all_enemy_models)} models)")
        if not all_enemy_models:
            print(f"{self.name} cannot charge - no alive models in target unit {targets[0].name}")
            return False
        
        successful_moves = 0
        
        # FAST PATH FOR SINGLE MODEL UNITS - use pathfinding but skip formation complexity
        if len(self.models) == 1:
            print(f"{self.name} using single-model charge path")
            model = self.models[0]
            model_start = model.get_location()
            
            # Calculate straight-line distance to destination (rules-aware)
            model_distance = measure_direct_distance(
                (model_start[0], model_start[1], model_start[2] if len(model_start) > 2 else 0.0),
                (destination[0], destination[1], destination[2]),
                self,
                MovementType.CHARGE,
                game_map,
            )
            
            # Check if within charge distance
            if model_distance > max_charge_distance:
                print(f"{self.name} cannot reach charge destination {model_distance:.1f}\" away (max: {max_charge_distance}\")")
                return False
            
            # Use charge-aware pathfinding for single model (can navigate around obstacles and into engagement range)
            from ..utility.calcs import get_charge_movement_path

            pathfinding_result = get_charge_movement_path(
                model, destination, max_charge_distance, game_map, targets[0], target_units=targets
            )
            
            if not pathfinding_result or not pathfinding_result.get('valid'):
                print(f"{self.name} cannot charge to destination - pathfinding failed (obstacles in way)")
                return False

            shortest_path = pathfinding_result['path']
            
            # Calculate path distance
            path_distance = measure_path_distance(shortest_path, self, MovementType.CHARGE, game_map)
            
            # Check if path is within charge distance
            if path_distance > max_charge_distance:
                print(f"{self.name} path distance {path_distance:.1f}\" exceeds charge distance {max_charge_distance}\"")
                return False
            
            # Move the model to destination
            new_z = game_map.get_height_at_point(destination[0], destination[1])
            new_facing = self.calculate_strategic_facing(destination[0], destination[1], game_map)
            model.set_location(destination[0], destination[1], new_z, new_facing)
            successful_moves = 1
            
            print(f"{self.name} (single model) charged via pathfinding - distance: {path_distance:.1f}\"")
        
        else:
            # COMPLEX PATH FOR MULTI-MODEL UNITS - use formation positioning
            print(f"{self.name} using multi-model charge path")
            
            # Generate potential positions for models with enhanced pathfinding for charges
            boundary_repulsors = self._get_reduced_boundary_repulsors(game_map)
            potential_positions = self.calculate_model_positions(destination[0], destination[1], game_map, boundary_repulsors=boundary_repulsors)
            
            # Use formation positioning if available, otherwise fall back to individual positioning
            if potential_positions is not None:
                # Use formation positioning with enhanced pathfinding validation
                for model, model_destination in zip(self.models, potential_positions):
                    model_start = model.get_location()
                    
                    # Calculate distance for this model
                    model_distance = measure_direct_distance(
                        (model_start[0], model_start[1], model_start[2] if len(model_start) > 2 else 0.0),
                        (model_destination[0], model_destination[1], model_destination[2] if len(model_destination) > 2 else 0.0),
                        self,
                        MovementType.CHARGE,
                        game_map,
                    )
                    
                    # Check if within charge distance
                    if model_distance > max_charge_distance:
                        logger.debug(f"Model {model._id} cannot reach charge destination {model_distance:.1f}\" away (max: {max_charge_distance}\")")
                        continue
                    
                    # Use charge-aware pathfinding for charge movement
                    from ..utility.calcs import get_charge_movement_path

                    pathfinding_result = get_charge_movement_path(
                        model, model_destination, max_charge_distance, game_map, targets[0], target_units=targets
                    )

                    if pathfinding_result and pathfinding_result.get('valid'):
                        shortest_path = pathfinding_result['path']
                        
                        # Calculate path distance
                        path_distance = measure_path_distance(shortest_path, self, MovementType.CHARGE, game_map)
                        
                        if path_distance <= max_charge_distance:
                            # Move to destination
                            model.set_location(*model_destination)
                            successful_moves += 1
                            logger.debug(f"Model {model._id} charge moved {path_distance:.1f}\" to formation position")
                        else:
                            logger.debug(f"Model {model._id} path distance {path_distance:.1f}\" exceeds charge distance {max_charge_distance}\"")
                    else:
                        logger.debug(f"Model {model._id} cannot charge to formation position - pathfinding failed")
            else:
                print(f"{self.name} charge failed - no valid formation found, trying individual positioning")
            
            # If formation failed or had limited success, try individual model positioning
            if successful_moves < len(self.models) // 2:  # If less than half succeeded
                # Move each model individually using enhanced pathfinding
                for model in self.models:
                    model_start = model.get_location()
                
                    # Find the closest enemy model to this model
                    closest_enemy = None
                    closest_distance = float('inf')
                    
                    for enemy_model in all_enemy_models:
                        enemy_pos = enemy_model.get_location()
                        distance = get_dist(
                            enemy_pos[0] - model_start[0],
                            enemy_pos[1] - model_start[1],
                            enemy_pos[2] - model_start[2] if len(model_start) > 2 else 0
                        )
                        if distance < closest_distance:
                            closest_distance = distance
                            closest_enemy = enemy_model
                    
                    if not closest_enemy:
                        continue
                    
                    # Calculate direction towards closest enemy
                    enemy_pos = closest_enemy.get_location()
                    dx = enemy_pos[0] - model_start[0]
                    dy = enemy_pos[1] - model_start[1]
                    dz = enemy_pos[2] - model_start[2] if len(model_start) > 2 else 0
                    
                    distance_to_enemy = get_dist(dx, dy, dz)
                    
                    if distance_to_enemy == 0:
                        # Already at enemy position, no movement needed
                        successful_moves += 1
                        continue
                    
                    # Normalize direction vector
                    dx /= distance_to_enemy
                    dy /= distance_to_enemy
                    dz /= distance_to_enemy if distance_to_enemy > 0 else 1
                    
                    # Calculate how far to move: use the distance provided by attempt_charge
                    # Get as close as possible to the enemy for better pile-in positioning
                    target_distance = max_charge_distance  # Use the distance calculated by attempt_charge
                    
                    if target_distance <= 0:
                        # Already close enough or can't move closer
                        successful_moves += 1
                        continue
                    
                    # Calculate new position
                    new_x = model_start[0] + dx * target_distance
                    new_y = model_start[1] + dy * target_distance
                    new_z = game_map.get_height_at_point(new_x, new_y)
                    new_facing = self.calculate_strategic_facing(new_x, new_y, game_map)
                    
                    # CRITICAL: Validate position before moving to prevent friendly unit overlaps
                    # Import here to avoid circular imports
                    from ..utility.calcs import check_friendly_ending_collision
                    
                    # Check if the new position would collide with friendly units
                    if check_friendly_ending_collision(model, (new_x, new_y, new_z), game_map):
                        # Position would cause collision - try to find alternative position
                        # Try positions at different distances along the same direction
                        alternative_found = False
                        for distance_factor in [0.9, 0.8, 0.7, 0.6, 0.5]:
                            alt_distance = target_distance * distance_factor
                            alt_x = model_start[0] + dx * alt_distance
                            alt_y = model_start[1] + dy * alt_distance
                            alt_z = game_map.get_height_at_point(alt_x, alt_y)
                            
                            if not check_friendly_ending_collision(model, (alt_x, alt_y, alt_z), game_map):
                                # Found a valid alternative position
                                new_x, new_y, new_z = alt_x, alt_y, alt_z
                                target_distance = alt_distance
                                alternative_found = True
                                logger.debug(f"Model {model._id} found alternative charge position at {distance_factor:.1f} of original distance")
                                break
                        
                        if not alternative_found:
                            # No valid position found - skip this model
                            logger.debug(f"Model {model._id} cannot charge - no valid position found without friendly collisions")
                            continue
                    
                    # Move the model to the validated position
                    model.set_location(new_x, new_y, new_z, new_facing)
                    successful_moves += 1
                    
                    actual_distance_moved = get_dist(
                        new_x - model_start[0],
                        new_y - model_start[1],
                        new_z - model_start[2] if len(model_start) > 2 else 0
                    )
                    target_name = target_unit.name if target_unit else "closest enemy"
                    logger.debug(f"Model {model._id} charge moved {actual_distance_moved:.1f}\" towards {closest_enemy.name} (from {target_name})")
        
        # Unit position is now determined by model positions
        
        # Check if any movement occurred
        if successful_moves == 0:
            print(f"{self.name} could not charge - no models could reach any valid positions")
            return False
        
        # CRITICAL VALIDATION: Final check for any overlaps after all models positioned
        # This catches edge cases where models might still overlap despite individual validation
        friendly_units = game_map.get_friendly_units(self)
        for model in self.models:
            if not model.is_alive:
                continue
            for friendly_unit in friendly_units:
                if friendly_unit == self or not friendly_unit.is_alive() or not friendly_unit.deployed:
                    continue
                for friendly_model in friendly_unit.models:
                    if not friendly_model.is_alive:
                        continue
                    # Check if this model's base overlaps with the friendly model's base
                    if model.model_base.collides_with(friendly_model.model_base):
                        print(f"{self.name} charge failed - {model.name} would overlap with {friendly_model.name} from {friendly_unit.name}")
                        # ROLLBACK: Restore original positions
                        for i, original_pos in enumerate(original_model_positions):
                            if i < len(self.models):
                                self.models[i].set_location(*original_pos)
                        return False

        # Coherency validation: charge moves must end in coherency (movement ending out of coherency is not allowed)
        try:
            from ..utility.calcs import validate_unit_coherency_after_movement
            final_positions = [m.get_location() for m in self.models]
            is_coherent, non_coherent_models = validate_unit_coherency_after_movement(self, final_positions)
            if not is_coherent:
                print(f"{self.name} charge move rejected: unit coherency would be broken (non-coherent models: {non_coherent_models})")
                for i, original_pos in enumerate(original_model_positions):
                    if i < len(self.models):
                        self.models[i].set_location(*original_pos)
                return False
        except Exception as e:
            # If coherency validation itself fails, fail-fast rather than silently allowing illegal states.
            raise

        # Charge targets validation (must engage all targets, avoid non-targets)
        ok, reason = self.validate_charge_end_state(targets, game_map)
        if not ok:
            print(f"{self.name} charge move rejected: {reason}")
            for i, original_pos in enumerate(original_model_positions):
                if i < len(self.models):
                    self.models[i].set_location(*original_pos)
            return False
        
        # Get final position for feedback from first model
        if self.models and self.models[0].is_alive:
            final_position = self.models[0].get_location()
            end_x, end_y = final_position[0], final_position[1]
            end_z = final_position[2] if len(final_position) > 2 else start_z
        else:
            end_x, end_y = start_x, start_y  # Fallback to start position
            end_z = start_z
        
        # Calculate actual distance the unit moved (rules-aware)
        unit_distance_moved = measure_direct_distance(
            (start_x, start_y, start_z),
            (end_x, end_y, end_z),
            self,
            MovementType.CHARGE,
            game_map,
        )
        
        # Provide detailed feedback
        print(f"{self.name} moved from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        
        if successful_moves < len(self.models):
            print(f" Note: Only {successful_moves}/{len(self.models)} models could move to valid positions")
        
        # Mark unit as having moved this round
        self.round_state.moved_this_round = True
        
        logger.info(f"Unit {self.name} charge moved from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        # Publish movement end for stratagem reaction windows (e.g. TANK SHOCK / FIRE OVERWATCH on Charge moves).
        try:
            _player = getattr(self.get_parent_army(), 'player', None)
            _game = getattr(_player, 'game', None) if _player else None
            if _game and hasattr(_game, 'event_system'):
                _game.event_system.publish("unit_move_ended", unit=self, action="charge")
        except Exception:
            pass
        return True

    def _grant_charge_move_devastating_wounds(self, model: 'Model', source: str = "") -> None:
        """Apply temporary Devastating Wounds (melee) to a model until end of turn."""
        if model is None:
            return
        if not isinstance(getattr(model, "_temporary_effects", None), dict):
            model._temporary_effects = {}
        model._temporary_effects["charge_move_devastating_wounds"] = {
            "devastating_wounds_melee": True,
            "expires_phase": "FIGHT_PHASE",
            "source": str(source or "Charge move ability"),
        }

    def _apply_charge_move_devastating_wounds(self) -> bool:
        """
        Apply temporary Devastating Wounds (melee) to models when the unit completes a charge move.

        Supports rules like:
          "Each time this model makes a Charge move, until the end of the turn, its melee weapons have the
          [DEVASTATING WOUNDS] ability."
        """
        applied = False

        def _iter_sentences(text: str) -> list[str]:
            if not text:
                return []
            cleaned = re.sub(r";\s*", ". ", text)
            return [part.strip() for part in re.split(r"\.\s*", cleaned) if part.strip()]

        try:
            members = list(self.get_attached_unit_members() or [])
        except Exception:
            members = [self]

        # Unit-level abilities (apply to all models in that unit member).
        for unit in members:
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text = unit._normalize_rules_text(desc or name or "")
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                for sentence in _iter_sentences(text):
                    if self._CHARGE_MOVE_DEVASTATING_WOUNDS_RE.search(sentence):
                        for model in list(getattr(unit, "models", []) or []):
                            if not getattr(model, "is_alive", True):
                                continue
                            self._grant_charge_move_devastating_wounds(model, source=name or "Charge move ability")
                        applied = True
                        break

        # Model-level abilities (apply only to that model).
        for unit in members:
            for model in list(getattr(unit, "models", []) or []):
                if model is None or not getattr(model, "is_alive", True):
                    continue
                for name, desc in unit._iter_model_specific_ability_entries(model):
                    text = unit._normalize_rules_text(desc or name or "")
                    if not text:
                        continue
                    text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                    for sentence in _iter_sentences(text):
                        if self._CHARGE_MOVE_DEVASTATING_WOUNDS_RE.search(sentence):
                            self._grant_charge_move_devastating_wounds(model, source=name or "Charge move ability")
                            applied = True
                            break

        return applied

    def fall_back(self, destination: Tuple[float, float, float], path: List[Tuple[float, float, float]], game_map: 'Map') -> bool:
        """Falls back from close combat.
        
        Battle-Shocked units that fall back must take Desperate Escape Tests.
        Units that fall back can move within engagement range and over enemy models,
        but cannot end within engagement range of any enemy models.
        """
        if bool(getattr(self, "is_aircraft", False)):
            print(f"{self.name} cannot Fall Back (AIRCRAFT)")
            return False
        print(f"{self.name} falls back from combat")

        try:
            from ..rules.wrathful_presence import overwhelming_wrath_sources_for_unit
            sources = overwhelming_wrath_sources_for_unit(self, game_map=game_map)
        except Exception:
            sources = []
        if sources:
            try:
                passed = bool(self.pass_leadership_check())
            except Exception:
                passed = True
            if not passed:
                try:
                    self.round_state.remained_stationary_this_round = True
                except Exception:
                    pass
                try:
                    from ..utility.event_bus import append_action
                    pn = self.get_parent_army().player
                    src_names = [getattr(s, "name", "") for s in sources if getattr(s, "name", "")]
                    src_text = ", ".join(src_names) if src_names else "Overwhelming Wrath"
                    append_action(pn, f"Overwhelming Wrath: {self.name} failed a Leadership test and remains stationary ({src_text}).")
                except Exception:
                    pass
                return False
        
        fallback_desperate = False
        fallback_bs_penalty = 0
        if game_map is not None:
            try:
                enemy_units = list(game_map.get_enemy_units(self) or [])
            except Exception:
                try:
                    unit_army = self.get_parent_army()
                except Exception:
                    unit_army = None
                enemy_units = [
                    u for u in list(getattr(game_map, "units", []) or [])
                    if getattr(u, "get_parent_army", lambda: None)() is not unit_army
                ]
            for enemy in enemy_units:
                sr = getattr(enemy, "special_rules", None)
                if not isinstance(sr, dict) or not sr.get("enemy_fallback_desperate_escape"):
                    continue
                if sr.get("enemy_fallback_desperate_escape_exclude_monster_vehicle"):
                    try:
                        if self.has_any_keyword("MONSTER") or self.has_any_keyword("VEHICLE"):
                            continue
                    except Exception:
                        pass
                try:
                    if hasattr(game_map, "is_within_engagement_range") and not game_map.is_within_engagement_range(self, enemy):
                        continue
                except Exception:
                    continue
                fallback_desperate = True
                try:
                    fallback_bs_penalty = max(fallback_bs_penalty, int(sr.get("enemy_fallback_desperate_escape_bs_penalty", 0) or 0))
                except Exception:
                    pass

        is_battleshocked = self.is_battle_shocked()
        if is_battleshocked or fallback_desperate:
            roll_modifier = 0
            if is_battleshocked and fallback_desperate and fallback_bs_penalty:
                roll_modifier = -abs(int(fallback_bs_penalty))
            models_lost = self.take_desperate_escape_test(
                game_map,
                reason="fall back",
                roll_modifier=roll_modifier,
            )
            # Check if unit was wiped out during Desperate Escape Test
            if not self.is_alive():
                print(f"INFO: {self.name} was completely destroyed during Desperate Escape Test!")
                return False

        # Execute Fall Back movement for each model
        if not self.models:
            logger.error(f"Cannot fall back unit {self.name}: no models in unit")
            return False
        
        # Get starting position from first model
        if not self.models or not self.models[0].is_alive:
            logger.error(f"Cannot fall back unit {self.name}: no valid models")
            return False

        first_model = self.models[0]
        if callable(getattr(first_model, "get_location", None)):
            first_model_pos = first_model.get_location()
        else:
            base = getattr(first_model, "model_base", None)
            if base is None:
                logger.error(f"Cannot fall back unit {self.name}: first model has no position")
                return False
            first_model_pos = (float(getattr(base, "x", 0.0)), float(getattr(base, "y", 0.0)), float(getattr(base, "z", 0.0)))
        if not first_model_pos:
            logger.error(f"Cannot fall back unit {self.name}: first model has no position")
            return False

        # Store starting position for feedback
        start_x, start_y = first_model_pos[0], first_model_pos[1]
        start_z = first_model_pos[2] if len(first_model_pos) > 2 else 0
        
        # Fall Back movement distance is the unit's Move characteristic
        movement_range = self.movement
        
        from ..utility.calcs import MovementType
        # Calculate straight-line distance to destination (rules-aware)
        distance_to_destination = measure_direct_distance(
            (start_x, start_y, start_z),
            (destination[0], destination[1], destination[2]),
            self,
            MovementType.FALL_BACK,
            game_map,
        )
        
        # Check if destination is within movement range
        if distance_to_destination > movement_range:
            print(f"{self.name} cannot reach fall back destination {distance_to_destination:.1f}\" away (max move: {movement_range}\")")
            return False

        # Generate potential positions for models with reduced boundary repulsors for better formation finding
        boundary_repulsors = self._get_reduced_boundary_repulsors(game_map)
        potential_positions = self.calculate_model_positions(destination[0], destination[1], game_map, boundary_repulsors=boundary_repulsors)
        
        # Check if formation finding failed
        if potential_positions is None:
            print(f"{self.name} cannot fall back - no valid formation found at destination")
            return False
            
        successful_moves = 0
        total_models_moved_over_enemies = 0
        
        for model, model_destination in zip(self.models, potential_positions):
            model_start = model.get_location()
            logging.debug(f"Model {model._id} {model.name} attempting to fall back from {model_start} to {model_destination}")
            
            # Calculate straight-line distance for this model
            model_distance = measure_direct_distance(
                (model_start[0], model_start[1], model_start[2] if len(model_start) > 2 else 0.0),
                (model_destination[0], model_destination[1], model_destination[2] if len(model_destination) > 2 else 0.0),
                self,
                MovementType.FALL_BACK,
                game_map,
            )
            
            # Check if this model can reach its destination
            if model_distance > movement_range:
                print(f"Model {model._id} cannot reach fall back destination {model_distance:.1f}\" away (max: {movement_range}\")")
                continue  # Skip this model, don't move it
            
            # Try pathfinding for Fall Back movement using standard pathfinding
            from ..utility.calcs import get_movement_path_preview, MovementType

            pathfinding_result = get_movement_path_preview(
                model,
                model_destination,
                self.movement,
                game_map,
                movement_type=MovementType.FALL_BACK,
            )

            if not pathfinding_result or not pathfinding_result.get('valid'):
                logger.debug(f"Model {model._id} pathfinding failed for fall back - destination may be invalid")
                continue

            # Convert 2D path to 3D
            shortest_path = pathfinding_result['path']
            
            # Calculate path distance
            path_distance = measure_path_distance(shortest_path, self, MovementType.FALL_BACK, game_map)
            
            # Check for Desperate Escape Tests (models that move over enemy models).
            # New pathfinding does not track enemy models moved over, so this stays empty.
            enemy_models_moved_over = []
            if enemy_models_moved_over and not self.is_titanic and not self.is_flying:
                print(f" Model {model._id} must take Desperate Escape Test for moving over {len(enemy_models_moved_over)} enemy model(s)")
                
                # Take Desperate Escape Test for this model
                roll = get_roll("D6")
                if roll <= 2:
                    print(f"Model {model._id}: Rolled {roll} on Desperate Escape Test - DESTROYED! ")
                    self.remove_model(model, fleed=True, game_map=game_map)
                    continue  # Model is destroyed, don't move it
                else:
                    print(f"Model {model._id}: Rolled {roll} on Desperate Escape Test - Survives ")
                    total_models_moved_over_enemies += 1
            
            if path_distance > movement_range:
                print(f"Model {model._id} path distance {path_distance:.1f}\" exceeds movement {movement_range}\"")
                # Try to move as far as possible along the path
                last_node = model_start
                model.last_move_path = [last_node]
                distance_along_path = 0.0
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                
                for node in shortest_path[1:]:
                    segment_distance = movement_segment_cost(last_node, node, self, MovementType.FALL_BACK)
                    
                    if distance_along_path + segment_distance > movement_range:
                        # Stop here, can't go further
                        break
                    
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                # Move to the furthest reachable position
                if distance_along_path > 0:
                    final_position = model.last_move_path[-1]
                    model.set_location(final_position[0], final_position[1], final_position[2], final_position[3])
                    successful_moves += 1
                    logger.debug(f"Model {model._id} fell back along path to {final_position[:3]}, distance: {distance_along_path:.1f}\"")
            else:
                # Path is within range, move to destination
                model.set_location(*model_destination)
                last_node = model_start
                model.last_move_path = [last_node]
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                distance_along_path = 0.0
                
                for node in shortest_path[1:]:
                    segment_distance = movement_segment_cost(last_node, node, self, MovementType.FALL_BACK)
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                successful_moves += 1
                logger.debug(f"Model {model._id} fell back to {model_destination}, path distance: {distance_along_path:.1f}\"")
        
        # Unit position is now determined by model positions
        
        # Check if any movement occurred
        if successful_moves == 0:
            print(f"{self.name} could not fall back - no models could reach valid positions")
            return False
        
        # Check if unit was wiped out during Desperate Escape Tests
        if not self.is_alive():
            print(f"{self.name} was completely destroyed during Fall Back Desperate Escape Tests!")
            return False
        
        # CRITICAL VALIDATION: Check for illegal overlaps after fall back
        # Fall back has special rules - units can move over enemies but cannot end overlapping
        enemy_units = game_map.get_enemy_units(self)
        for model in self.models:
            if not model.is_alive:
                continue
            for enemy_unit in enemy_units:
                if not enemy_unit.is_alive() or not enemy_unit.deployed:
                    continue
                for enemy_model in enemy_unit.models:
                    if not enemy_model.is_alive:
                        continue
                    # Check if this model's base overlaps with the enemy model's base
                    if model.model_base.collides_with(enemy_model.model_base):
                        print(f"{self.name} cannot fall back - {model.name} cannot end overlapping with {enemy_model.name} from {enemy_unit.name}")
                        # For fall back, we don't have original positions stored, so this is a critical error
                        # The fall back move should have been validated during pathfinding
                        return False
        
        # Get final position for feedback from first model
        if self.models and self.models[0].is_alive:
            final_position = self.models[0].get_location()
            end_x, end_y = final_position[0], final_position[1]
            end_z = final_position[2] if len(final_position) > 2 else start_z
        else:
            end_x, end_y = start_x, start_y  # Fallback to start position
            end_z = start_z
        
        # Calculate actual distance the unit moved (rules-aware)
        unit_distance_moved = measure_direct_distance(
            (start_x, start_y, start_z),
            (end_x, end_y, end_z),
            self,
            MovementType.FALL_BACK,
            game_map,
        )
        
        # Provide detailed feedback
        print(f"{self.name} fell back from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        
        if total_models_moved_over_enemies > 0:
            print(f" {total_models_moved_over_enemies} model(s) moved over enemy models and survived Desperate Escape Tests")
        
        if successful_moves < len(self.models):
            remaining_models = len(self.models)
            print(f" Note: Only {successful_moves} models could fall back to valid positions, {remaining_models} models remain")
        
        logger.info(f"Unit {self.name} fell back from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        self.round_state.fell_back_this_round = True
        try:
            self._apply_super_heavy_walker_terrain_shock(game_map, action="fall_back")
        except Exception:
            pass
        return True

    def _eligibility_text_has_extra_clauses(self, text: str) -> bool:
        if not text:
            return False
        markers = [
            " but ",
            " instead ",
            " unless ",
            " except ",
            " however ",
            " only ",
            " while ",
            " after ",
            " before ",
            " until ",
            " at the start",
            " start of",
            " each time",
            " choose ",
            " select ",
            " one of",
            " following",
            ":",
        ]
        t = f" {text} "
        return any(m in t for m in markers)

    def _has_simple_eligibility_rule(self, patterns: List[str]) -> bool:
        for name, desc in self._iter_ability_entries_for_rules():
            text = self._normalize_rules_text(f"{name} {desc}").lower()
            if not text:
                continue
            if any(p in text for p in patterns):
                if self._eligibility_text_has_extra_clauses(text):
                    continue
                return True
        return False

    def has_advance_and_shoot(self) -> bool:
        """Check if the unit has an ability that allows shooting after advancing.
        
        This checks for unit abilities that allow shooting after advancing,
        based on actual Warhammer 40k ability descriptions.
        
        Returns:
            bool: True if the unit has an ability that allows shooting after advancing
        """
        # Use cached result if available
        if 'advance_and_shoot' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['advance_and_shoot']
        
        found = False
        if self.has_thrill_seekers():
            found = True
        elif self._first_prince_of_chaos_active() and self._first_prince_has_god_keyword("KHORNE"):
            found = True
        else:
            found = self._has_simple_eligibility_rule([
                "eligible to shoot in a turn in which it advanced",
                "eligible to shoot in a turn in which it fell back or advanced",
                "eligible to shoot in a turn in which it advanced or fell back",
                "eligible to shoot and declare a charge in a turn in which it advanced",
                "eligible to shoot and declare a charge in a turn in which it advanced or fell back",
                "eligible to shoot and declare a charge in a turn in which it fell back or advanced",
                "that unit is eligible to shoot and declare a charge in a turn in which it advanced",
                "that unit is eligible to shoot and declare a charge in a turn in which it advanced or fell back",
                "that unit is eligible to shoot and declare a charge in a turn in which it fell back or advanced",
            ])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['advance_and_shoot'] = found
        
        return found

    def has_advance_and_charge(self) -> bool:
        """Check if the unit has an ability that allows charging after advancing.

        This checks for unit abilities that allow charging after advancing,
        based on actual Warhammer 40k ability descriptions.

        Returns:
            bool: True if the unit has an ability that allows charging after advancing
        """
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "waaagh", None) if army is not None else None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if mgr is not None and mgr.unit_is_affected(self, game=game):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("apoplectic_frenzy_active"):
                return True
        except Exception:
            pass
        # Use cached result if available
        if 'advance_and_charge' in getattr(self, '_ability_cache', {}):
            cached_result = self._ability_cache['advance_and_charge']
            #print(f"{self.name} has_advance_and_charge (cached): {cached_result}")
            return cached_result

        print(f"{self.name} checking for advance and charge abilities...")

        found = False
        if self.has_thrill_seekers():
            found = True
        elif self._first_prince_of_chaos_active() and self._first_prince_has_god_keyword("KHORNE"):
            found = True
        else:
            found = self._has_simple_eligibility_rule([
                "eligible to declare a charge in a turn in which it advanced",
                "eligible to declare a charge in a turn in which it advanced or fell back",
                "eligible to declare a charge in a turn in which it fell back or advanced",
                "eligible to charge in a turn in which it advanced",
                "eligible to charge in a turn in which it advanced or fell back",
                "eligible to charge in a turn in which it fell back or advanced",
                "eligible to shoot and declare a charge in a turn in which it advanced",
                "eligible to shoot and declare a charge in a turn in which it advanced or fell back",
                "eligible to shoot and declare a charge in a turn in which it fell back or advanced",
                "that unit is eligible to shoot and declare a charge in a turn in which it advanced",
                "that unit is eligible to shoot and declare a charge in a turn in which it advanced or fell back",
                "that unit is eligible to shoot and declare a charge in a turn in which it fell back or advanced",
            ])

        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['advance_and_charge'] = found

        return found

    def has_fell_back_and_shoot(self) -> bool:
        """Check if the unit has an ability that allows shooting after falling back.
        
        This checks for unit abilities that allow shooting after falling back,
        based on actual Warhammer 40k ability descriptions.
        
        Returns:
            bool: True if the unit has an ability that allows shooting after falling back
        """
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("feigned_retreat_active"):
                owner = str(sr.get("feigned_retreat_turn_owner", "") or "")
                turn = int(sr.get("feigned_retreat_turn", 0) or 0)
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                if game is None:
                    return True
                if owner and str(getattr(game.get_current_player(), "id", "") or "") == owner:
                    if int(getattr(game, "turn", 0) or 0) == int(turn or 0):
                        return True
        except Exception:
            pass
        # Use cached result if available
        if 'fell_back_and_shoot' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['fell_back_and_shoot']
        
        found = False
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "duty_before_all_applies", None):
                if mgr.duty_before_all_applies(self):
                    found = True
        except Exception:
            pass
        if not found:
            if self.has_thrill_seekers():
                found = True
            else:
                found = self._has_simple_eligibility_rule([
                    "eligible to shoot in a turn in which it fell back",
                    "eligible to shoot in a turn in which it fell back or advanced",
                    "eligible to shoot in a turn in which it advanced or fell back",
                    "eligible to shoot and declare a charge in a turn in which it fell back",
                    "eligible to shoot and declare a charge in a turn in which it advanced or fell back",
                    "eligible to shoot and declare a charge in a turn in which it fell back or advanced",
                    "that unit is eligible to shoot and declare a charge in a turn in which it fell back",
                    "that unit is eligible to shoot and declare a charge in a turn in which it advanced or fell back",
                    "that unit is eligible to shoot and declare a charge in a turn in which it fell back or advanced",
                ])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['fell_back_and_shoot'] = found
        
        return found

    def can_shoot_after_advance(self, profile) -> bool:
        """Check if this unit can shoot after advancing with the given weapon profile.
        
        A unit can shoot after advancing if either:
        1. The weapon profile is an Assault weapon, OR
        2. The unit has an ability that allows shooting after advancing
        
        Args:
            profile: The weapon profile to check
            
        Returns:
            bool: True if the unit can shoot this weapon after advancing
        """
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("battle_focus_star_engines_active"):
                return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "doctrina_imperatives", None) if army is not None else None
            if mgr is not None:
                game = getattr(getattr(army, "player", None), "game", None)
                if mgr.conqueror_assault_applies(self, game=game):
                    if getattr(profile, "parent_wargear", None) is not None and profile.parent_wargear.is_ranged():
                        return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bondsman_assault_ranged"):
                if getattr(profile, "parent_wargear", None) is not None and profile.parent_wargear.is_ranged():
                    return True
        except Exception:
            pass
        # Check for Assault weapons
        if profile.is_assault():
            return True
            
        # Check for unit abilities that allow advance and shoot
        if self.has_advance_and_shoot():
            return True
            
        return False

    def can_shoot_after_fall_back(self, profile) -> bool:
        """Check if this unit can shoot after falling back with the given weapon profile.
        
        In 10th edition, Falling Back normally makes a unit not eligible to shoot.
        A unit can only shoot after falling back if it has an ability that explicitly allows it.
        
        Args:
            profile: The weapon profile to check
            
        Returns:
            bool: True if the unit can shoot this weapon after falling back
        """
        # Check for unit abilities that allow shooting after falling back
        if self.has_fell_back_and_shoot():
            return True
            
        return False

    def can_charge_after_advance(self) -> bool:
        """Check if this unit can charge after advancing.

        A unit can charge after advancing if it has an ability that allows it.

        Returns:
            bool: True if the unit can charge after advancing
        """
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bondsman_charge_after_advance"):
                return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_charge_after_advance"):
                return True
        except Exception:
            pass
        has_ability = self.has_advance_and_charge()
        #print(f"{self.name} can_charge_after_advance check: {has_ability}")
        return has_ability

    def can_charge_after_fall_back(self) -> bool:
        """Check if this unit can charge after falling back."""
        if self.has_thrill_seekers():
            return True
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "duty_before_all_applies", None):
                if mgr.duty_before_all_applies(self):
                    return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("feigned_retreat_active"):
                owner = str(sr.get("feigned_retreat_turn_owner", "") or "")
                turn = int(sr.get("feigned_retreat_turn", 0) or 0)
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
                if game is None:
                    return True
                if owner and str(getattr(game.get_current_player(), "id", "") or "") == owner:
                    if int(getattr(game, "turn", 0) or 0) == int(turn or 0):
                        return True
        except Exception:
            pass
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_charge_after_fall_back"):
                return True
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "templar_vows", None) if army is not None else None
            if mgr is not None and mgr.can_charge_after_fall_back(self):
                return True
        except Exception:
            pass
        return self._has_simple_eligibility_rule([
            "eligible to declare a charge in a turn in which it fell back",
            "eligible to declare a charge in a turn in which it advanced or fell back",
            "eligible to declare a charge in a turn in which it fell back or advanced",
            "eligible to charge in a turn in which it advanced or fell back",
            "eligible to charge in a turn in which it fell back or advanced",
            "eligible to shoot and declare a charge in a turn in which it fell back",
            "eligible to shoot and declare a charge in a turn in which it advanced or fell back",
            "eligible to shoot and declare a charge in a turn in which it fell back or advanced",
            "that unit is eligible to shoot and declare a charge in a turn in which it fell back",
            "that unit is eligible to shoot and declare a charge in a turn in which it advanced or fell back",
            "that unit is eligible to shoot and declare a charge in a turn in which it fell back or advanced",
        ])

    def _thrill_seekers_restrictions_active(self) -> bool:
        if not self.has_thrill_seekers():
            return False
        return bool(getattr(self.round_state, "advanced_this_round", False) or getattr(self.round_state, "fell_back_this_round", False))

    def _thrill_seekers_restriction_reason(self, target_unit: 'Unit', game) -> Optional[str]:
        if not self._thrill_seekers_restrictions_active():
            return None
        if target_unit is None:
            return None
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        target_id = get_entity_id(target_root)
        engaged_ids = getattr(self.round_state, "engaged_enemies_at_turn_start", None) or set()
        if target_id is not None and target_id in engaged_ids:
            return "Thrill Seekers: cannot target a unit engaged at start of turn"
        try:
            phase_targets = getattr(game, "phase_targeted_units", None)
        except Exception:
            phase_targets = None
        try:
            phase_charge_targets = getattr(game, "phase_charge_targets", None)
        except Exception:
            phase_charge_targets = None
        if isinstance(phase_targets, dict) and target_id is not None:
            attackers = phase_targets.get(target_id, set()) or set()
            other_attackers = [a for a in attackers if a != get_entity_id(self)]
            if other_attackers:
                return "Thrill Seekers: target already selected by another unit this phase"
        if isinstance(phase_charge_targets, dict) and target_id is not None:
            chargers = phase_charge_targets.get(target_id, set()) or set()
            other_chargers = [a for a in chargers if a != get_entity_id(self)]
            if other_chargers:
                return "Thrill Seekers: target already selected by another unit this phase"
        return None

    def _sensational_performance_restriction_reason(self, target_unit: 'Unit', game) -> Optional[str]:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return None
        if not sr.get("sensational_performance_active"):
            return None
        exp = str(sr.get("sensational_performance_expires_phase", "") or "").strip().upper()
        if exp:
            try:
                pname = str(getattr(getattr(game, "phase", None), "name", "") or getattr(game, "phase", "") or "").strip().upper()
            except Exception:
                pname = ""
            if pname and pname != exp:
                return None
        if target_unit is None:
            return None
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        target_id = get_entity_id(target_root)
        engaged_ids = getattr(self.round_state, "engaged_enemies_at_turn_start", None) or set()
        if target_id is not None and target_id in engaged_ids:
            return "Sensational Performance: cannot target a unit engaged at start of turn"
        try:
            phase_targets = getattr(game, "phase_targeted_units", None)
        except Exception:
            phase_targets = None
        if isinstance(phase_targets, dict) and target_id is not None:
            attackers = phase_targets.get(target_id, set()) or set()
            other_attackers = [a for a in attackers if a != getattr(self, "_id", None)]
            if other_attackers:
                return "Sensational Performance: target already selected by another unit this phase"
        return None

    def scout_move(self, destination: Tuple[float, float, float], game_map: 'Map') -> bool:
        """Execute a scout move for the unit during pre-battle rules phase.
        
        Scout moves have special restrictions:
        - Cannot move within engagement range of enemy units
        - Cannot end within 9" of enemy units
        - Cannot charge or advance during scout move
        - Considered a normal move action (terrain rules apply)
        
        Args:
            destination: Target position (x, y, z)
            game_map: The game map for validation and movement
            
        Returns:
            bool: True if scout move was successful
        """
        if not self.models:
            logger.error(f"Cannot scout move unit {self.name}: no models in unit")
            return False
        
        # Check if unit has scout ability
        has_scout, scout_distance = self.has_scout()
        if not has_scout:
            logger.error(f"Unit {self.name} does not have Scout ability")
            return False
        
        # Check if unit has already made a scout move
        if hasattr(self, 'scout_move_made') and self.scout_move_made:
            logger.error(f"Unit {self.name} has already made a scout move")
            return False
        
        # Check if unit is deployed (not in reserves)
        if not self.deployed or self.reserve_status != 'deployed':
            logger.error(f"Unit {self.name} is not deployed and cannot make scout move")
            return False
        
        # Get starting position from first model
        if not self.models or not self.models[0].is_alive:
            logger.error(f"Cannot scout move unit {self.name}: no valid models")
            return False

        first_model_pos = self.models[0].get_location()
        if not first_model_pos:
            logger.error(f"Cannot scout move unit {self.name}: first model has no position")
            return False

        # Store starting position for feedback
        start_x, start_y = first_model_pos[0], first_model_pos[1]
        start_z = first_model_pos[2] if len(first_model_pos) > 2 else 0
        
        from ..utility.calcs import MovementType
        # Calculate straight-line distance to destination (rules-aware)
        distance_to_destination = measure_direct_distance(
            (start_x, start_y, start_z),
            (destination[0], destination[1], destination[2]),
            self,
            MovementType.SCOUT,
            game_map,
        )
        
        # Check if destination is within scout distance
        if distance_to_destination > scout_distance:
            print(f"{self.name} cannot reach scout destination {distance_to_destination:.1f}\" away (max scout: {scout_distance}\")")
            return False
        
        # Generate potential positions for models with reduced boundary repulsors for better formation finding
        boundary_repulsors = self._get_reduced_boundary_repulsors(game_map)
        potential_positions = self.calculate_model_positions(destination[0], destination[1], game_map, boundary_repulsors=boundary_repulsors)
        
        # Check if formation finding failed
        if potential_positions is None:
            print(f"{self.name} cannot scout move - no valid formation found at destination")
            return False

        # Check scout restriction: cannot end within 9" of enemy models (base-to-base closest-point distance).
        from ..utility.aura_utils import distance_between_bases_3d
        enemy_models = [em for eu in game_map.get_enemy_units(self) if eu.is_alive() and eu.deployed for em in eu.models if em.is_alive]
        for idx, (x, y, z, facing) in enumerate(potential_positions):
            if idx >= len(self.models):
                break
            mb = self._create_potential_base(x, y, z, facing, model=self.models[idx])
            for em in enemy_models:
                if float(distance_between_bases_3d(mb, em.model_base)) < 9.0:
                    print(f"{self.name} cannot scout move to destination - would end within 9\" of {em.parent_unit.name}")
                    return False
            
        # BACKUP ORIGINAL POSITIONS - Critical for proper rollback on failure
        original_model_positions = []
        for model in self.models:
            original_model_positions.append(model.get_location())

        successful_moves = 0
        
        for model, model_destination in zip(self.models, potential_positions):
            model_start = model.get_location()
            logging.debug(f"Model {model._id} {model.name} attempting scout move from {model_start} to {model_destination}")
            
            # Calculate straight-line distance for this model
            model_distance = measure_direct_distance(
                (model_start[0], model_start[1], model_start[2] if len(model_start) > 2 else 0.0),
                (model_destination[0], model_destination[1], model_destination[2] if len(model_destination) > 2 else 0.0),
                self,
                MovementType.SCOUT,
                game_map,
            )
            
            # Check if this model can reach its destination
            if model_distance > scout_distance:
                print(f"Model {model._id} cannot reach scout destination {model_distance:.1f}\" away (max: {scout_distance}\")")
                continue  # Skip this model, don't move it
            
            # Use new optimized pathfinding for scout move (individual model movement)
            from ..utility.calcs import get_individual_model_movement_path
            
            # Find model index for pathfinding
            model_index = None
            for i, m in enumerate(self.models):
                if m == model:
                    model_index = i
                    break
            
            if model_index is None:
                logger.error(f"Could not find model index for {model.name}")
                continue
            
            path = get_individual_model_movement_path(self, model_index, model_destination, game_map, scout_distance)
            
            if not path:
                logger.debug(f"Model {model._id} optimized pathfinding failed for scout move - destination may be invalid")
                continue
            
            # Calculate path distance
            path_distance = measure_path_distance(path, self, MovementType.SCOUT, game_map)
            
            if path_distance > scout_distance:
                print(f"Model {model._id} path distance {path_distance:.1f}\" exceeds scout distance {scout_distance}\"")
                # Try to move as far as possible along the path
                last_node = model_start
                model.last_move_path = [last_node]
                distance_along_path = 0.0
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                
                for node in path[1:]:
                    segment_distance = movement_segment_cost(last_node, node, self, MovementType.SCOUT)
                    
                    if distance_along_path + segment_distance > scout_distance:
                        # Stop here, can't go further
                        break
                    
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                # Move to the furthest reachable position
                if distance_along_path > 0:
                    final_position = model.last_move_path[-1]
                    model.set_location(final_position[0], final_position[1], final_position[2], final_position[3])
                    successful_moves += 1
                    logger.debug(f"Model {model._id} scout moved along path to {final_position[:3]}, distance: {distance_along_path:.1f}\"")
            else:
                # Path is within range, move to destination
                model.set_location(*model_destination)
                last_node = model_start
                model.last_move_path = [last_node]
                direction_to_destination = get_angle(model_destination[0] - model.model_base.x, model_destination[1] - model.model_base.y)
                distance_along_path = 0.0
                
                for node in path[1:]:
                    segment_distance = movement_segment_cost(last_node, node, self, MovementType.SCOUT)
                    distance_along_path += segment_distance
                    last_node = (node[0], node[1], node[2] if len(node) > 2 else 0, direction_to_destination)
                    model.last_move_path.append(last_node)
                
                successful_moves += 1
                logger.debug(f"Model {model._id} scout moved to {model_destination}, path distance: {distance_along_path:.1f}\"")
        
        # Unit position is now determined by model positions
        
        # Check if any movement occurred
        if successful_moves == 0:
            print(f"{self.name} could not scout move - no models could reach valid positions")
            return False
        
        # NEW: Validate unit coherency after all models have moved (scout moves must maintain coherency)
        from ..utility.calcs import validate_unit_coherency_after_movement
        
        # Get final positions of all models
        final_positions = []
        for model in self.models:
            final_positions.append(model.get_location())
        
        is_coherent, non_coherent_models = validate_unit_coherency_after_movement(self, final_positions)
        
        if not is_coherent:
            print(f"{self.name} scout move rejected: unit coherency would be broken (non-coherent models: {non_coherent_models})")
            # ROLLBACK: Restore original positions (movement ending out of coherency is not allowed)
            for i, original_pos in enumerate(original_model_positions):
                if i < len(self.models):
                    self.models[i].set_location(*original_pos)
            return False
        
        # CRITICAL VALIDATION: Check for illegal overlaps after scout move
        # Scout moves cannot end overlapping with enemy models
        enemy_units = game_map.get_enemy_units(self)
        for model in self.models:
            if not model.is_alive:
                continue
            for enemy_unit in enemy_units:
                if not enemy_unit.is_alive() or not enemy_unit.deployed:
                    continue
                for enemy_model in enemy_unit.models:
                    if not enemy_model.is_alive:
                        continue
                    # Check if this model's base overlaps with the enemy model's base
                    if model.model_base.collides_with(enemy_model.model_base):
                        print(f"{self.name} cannot scout move - {model.name} cannot end overlapping with {enemy_model.name} from {enemy_unit.name}")
                        # ROLLBACK: Restore original positions
                        for i, original_pos in enumerate(original_model_positions):
                            if i < len(self.models):
                                self.models[i].set_location(*original_pos)
                        return False
        
        # Get final position for feedback from first model
        if self.models and self.models[0].is_alive:
            final_position = self.models[0].get_location()
            end_x, end_y = final_position[0], final_position[1]
            end_z = final_position[2] if len(final_position) > 2 else start_z
        else:
            end_x, end_y = start_x, start_y  # Fallback to start position
            end_z = start_z
        
        # Calculate actual distance the unit moved (rules-aware)
        unit_distance_moved = measure_direct_distance(
            (start_x, start_y, start_z),
            (end_x, end_y, end_z),
            self,
            MovementType.SCOUT,
            game_map,
        )
        
        # Mark unit as having made a scout move
        self.scout_move_made = True
        
        # Provide detailed feedback
        print(f"{self.name} scout moved from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        
        if successful_moves < len(self.models):
            print(f" Note: Only {successful_moves}/{len(self.models)} models could scout move to valid positions")
        
        logger.info(f"Unit {self.name} scout moved from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f}) - distance: {unit_distance_moved:.1f}\"")
        return True

    def can_shoot_in_engagement_range(self, game_map: 'Map', profile=None) -> bool:
        """Check if this unit can shoot while in engagement range with the given weapon profile."""
        # Check if unit is in engagement range ("Locked in Combat")
        is_engaged = any(
            game_map.is_within_engagement_range(self, enemy)
            for enemy in game_map.get_enemy_units(self)
            if enemy.is_alive()
        )
        
        if not is_engaged:
            return True
            
        # If engaged and no profile provided, assume cannot shoot
        if profile is None:
            return False
            
        # PISTOLS: can be used while within Engagement Range (target restriction enforced elsewhere)
        if profile.is_pistol():
            return True

        # BIG GUNS NEVER TIRE (BGNT):
        # In the controlling player's Shooting phase, VEHICLE/MONSTER units remain eligible to shoot while Locked in Combat.
        if (self.is_vehicle or self.is_monster) and self._is_controlling_players_shooting_phase():
            return True

        return False

    def can_shoot_at_target_while_engaged(self, target, profile, game_map) -> bool:
        """Check if this unit can shoot at a specific target while engaged with other units."""
        # If unit is not in engagement range, they can always shoot
        if not any(game_map.is_within_engagement_range(self, enemy)
                  for enemy in game_map.get_enemy_units(self) if enemy.is_alive()):
            return True

        # If target is the unit we're engaged with, Pistols can shoot; Vehicles/Monsters can shoot in-phase via BGNT.
        if target.is_alive() and game_map.is_within_engagement_range(self, target):
            if profile.is_pistol():
                return True
            return (self.is_vehicle or self.is_monster) and self._is_controlling_players_shooting_phase()

        # If target is not the unit we're engaged with, only Vehicles/Monsters can shoot in-phase via BGNT.
        return (self.is_vehicle or self.is_monster) and self._is_controlling_players_shooting_phase()

    def _is_controlling_players_shooting_phase(self) -> bool:
        """
        Return True only during this unit's controlling player's Shooting phase.

        Used for rules that explicitly apply only "in your Shooting phase" (e.g., Big Guns Never Tire).
        """
        army = self.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        game = getattr(player, "game", None) if player is not None else None
        if game is None or player is None:
            return False
        return bool(getattr(game, "is_shooting_phase", lambda: False)() and getattr(game, "get_current_player", lambda: None)() is player)

    def _is_locked_in_combat(self, game_map: 'Map') -> bool:
        """Return True if this unit is within Engagement Range of any enemy unit."""
        return any(
            game_map.is_within_engagement_range(self, enemy)
            for enemy in game_map.get_enemy_units(self)
            if enemy.is_alive()
        )

    @staticmethod
    def _is_unit_locked_in_combat(unit: 'Unit', game_map: 'Map') -> bool:
        """Return True if `unit` is within Engagement Range of any of its enemy units."""
        return any(
            game_map.is_within_engagement_range(unit, enemy)
            for enemy in game_map.get_enemy_units(unit)
            if enemy.is_alive()
        )

    ###########################################################################
    ### Shooting Phase Actions
    ###########################################################################
    def execute_shooting_declarations(self, weapon_declarations: List[dict], game_map: 'Map', *, out_of_phase: bool = False) -> bool:
        """
        Execute shooting declarations according to Warhammer 40k rules.
        
        Args:
            weapon_declarations: List of dicts with keys:
                - 'weapon_profile': WargearProfile to use
                - 'target_unit': Unit to target
                - 'models': List of models using this weapon
            game_map: Map instance for line of sight and range checks
            out_of_phase: True for out-of-phase shooting (e.g., Overwatch) so it does not consume normal shooting
            
        Returns:
            bool: True if any attacks were successful
        """
        if not weapon_declarations:
            print(f"{self.name}: No shooting declarations to execute")
            return False
            
        # Check if unit can shoot
        # Mission Actions: a unit performing an Action is not eligible to shoot until that Action completes or end of turn
        if getattr(self.round_state, 'action_locked_until_turn_end', False):
            print(f"{self.name} is performing an Action and cannot shoot this turn")
            return False
        if (not out_of_phase) and self.round_state.shot_this_round:
            print(f"{self.name} has already shot this round")
            return False

        # Chapter Approved exception: if this unit arrived from reserves via the "base touches edge"
        # Strategic Reserves placement, it cannot shoot this turn.
        try:
            if bool(getattr(self, "_reserves_edge_touch_this_turn", False)) and bool(getattr(self, "arrived_from_reserves_this_turn", False)):
                print(f"{self.name} cannot shoot this turn (edge-touch Strategic Reserves placement)")
                return False
        except Exception:
            pass
            
        if self.round_state.fell_back_this_round:
            # Check if any weapons in the declarations can shoot after falling back
            can_shoot_any_weapon = False
            for declaration in weapon_declarations:
                if self.can_shoot_after_fall_back(declaration['weapon_profile']):
                    can_shoot_any_weapon = True
                    break
            
            if not can_shoot_any_weapon:
                print(f"{self.name} cannot shoot after falling back")
                return False
            
        # BGNT hit modifier snapshot:
        # When a VEHICLE/MONSTER makes ranged attacks and it was Locked in Combat when it selected targets,
        # apply -1 to Hit (unless Pistols). Snapshot this now so casualties later don't change it mid-activation.
        try:
            bgnt_locked_at_selection = bool((self.is_vehicle or self.is_monster) and self._is_controlling_players_shooting_phase() and self._is_locked_in_combat(game_map))
            setattr(self, "_bgnt_locked_at_target_selection", bgnt_locked_at_selection)
        except Exception:
            # Best-effort only; do not fail shooting if we can't snapshot.
            pass

        # Enforce PISTOL selection rules (10e):
        # - For non-VEHICLE/non-MONSTER models: if any non-pistol ranged weapons are selected, pistols cannot also be used.
        # - While within Engagement Range: only Pistols can be used by non-VEHICLE/non-MONSTER models.
        # This is enforced best-effort by filtering models out of conflicting declarations.
        try:
            is_vehicle_or_monster = bool(self.is_vehicle or self.is_monster)
            # Determine if this unit is engaged with any enemy
            engaged = self._is_locked_in_combat(game_map)

            # Build per-model "has pistol decl" and "has other decl"
            by_model: dict[str, dict[str, bool]] = {}
            for decl in weapon_declarations:
                wp = decl.get("weapon_profile")
                if wp is None:
                    continue
                is_pistol = bool(wp.is_pistol())
                for m in decl.get("models") or []:
                    if not getattr(m, "is_alive", False):
                        continue
                    key = get_entity_id(m)
                    entry = by_model.setdefault(key, {"pistol": False, "other": False})
                    if is_pistol:
                        entry["pistol"] = True
                    else:
                        entry["other"] = True

            # Filter declarations
            filtered_decls: list[dict] = []
            for decl in weapon_declarations:
                wp = decl.get("weapon_profile")
                if wp is None:
                    filtered_decls.append(decl)
                    continue
                wp_is_pistol = bool(wp.is_pistol())
                keep_models = []
                removed = 0
                for m in decl.get("models") or []:
                    if not getattr(m, "is_alive", False):
                        removed += 1
                        continue
                    flags = by_model.get(get_entity_id(m), {"pistol": False, "other": False})
                    if is_vehicle_or_monster:
                        # VEHICLE/MONSTER are not subject to the pistol-vs-other exclusivity rule.
                        keep_models.append(m)
                        continue
                    if engaged:
                        # Engaged non-VEHICLE/non-MONSTER: only pistols.
                        if wp_is_pistol:
                            keep_models.append(m)
                        else:
                            removed += 1
                        continue
                    # Not engaged non-VEHICLE/non-MONSTER:
                    # If both pistol and other were selected, prefer "other" and drop pistols.
                    if flags["pistol"] and flags["other"] and wp_is_pistol:
                        removed += 1
                        continue
                    keep_models.append(m)
                if removed and keep_models:
                    new_decl = dict(decl)
                    new_decl["models"] = keep_models
                    filtered_decls.append(new_decl)
                elif keep_models:
                    filtered_decls.append(decl)
                # else: drop empty declaration
            weapon_declarations = filtered_decls
        except Exception:
            pass

        print(f"{self.name} executing {len(weapon_declarations)} shooting declarations...")
        
        if not out_of_phase:
            # Mark unit as having shot this round (regardless of success)
            self.round_state.shot_this_round = True

            # Firing Deck: models whose weapons are used via a transport count as having shot.
            # We mark them here (once) so even if some declarations fail validation, they still
            # count as having been selected to shoot via the transport.
            try:
                fd_models = []
                for decl in weapon_declarations:
                    for m in (decl.get("firing_deck_source_models") or []):
                        if m is not None:
                            fd_models.append(m)
                # De-dupe
                seen = set()
                for m in fd_models:
                    mid = get_entity_id(m)
                    if mid in seen:
                        continue
                    seen.add(mid)
                    try:
                        setattr(m, "_shot_via_firing_deck_this_round", True)
                    except Exception:
                        pass
                    # Also mark the source unit as having shot this round (best-effort) to prevent
                    # shoot-again effects from re-selecting that unit in this round.
                    try:
                        pu = getattr(m, "parent_unit", None)
                        if pu is not None and hasattr(pu, "round_state"):
                            pu.round_state.shot_this_round = True
                    except Exception:
                        pass
            except Exception:
                pass
        
        successful_attacks = 0
        hit_tracker = {}
        hit_models_by_target = {}
        
        # Begin attack resolution window(s) for targets (so attached leaders don't separate mid-sequence)
        # Publish a reaction window for defensive stratagems (e.g. GO TO GROUND) right after targets are selected.
        try:
            if weapon_declarations and hasattr(self, "get_parent_army") and self.get_parent_army() is not None:
                game = getattr(self.get_parent_army().player, "game", None)
                if game is not None and hasattr(game, "event_system"):
                    touched_targets = []
                    seen_targets = set()
                    for decl in weapon_declarations:
                        t = decl.get("target_unit")
                        if t is None:
                            continue
                        tid = get_entity_id(t)
                        if tid in seen_targets:
                            continue
                        seen_targets.add(tid)
                        touched_targets.append(t)
                    if touched_targets:
                        game.event_system.publish(
                            "shooting_targets_selected",
                            attacking_unit=self,
                            target_units=list(touched_targets),
                        )
        except Exception:
            pass

        touched_targets = []
        try:
            seen_targets = set()
            for decl in weapon_declarations:
                t = decl.get("target_unit")
                if t is None:
                    continue
                tid = get_entity_id(t)
                if tid in seen_targets:
                    continue
                seen_targets.add(tid)
                touched_targets.append(t)
            for t in touched_targets:
                if hasattr(t, "begin_attack_resolution"):
                    t.begin_attack_resolution()
        except Exception:
            touched_targets = []

        attack_context = {"pending_mortal_wounds": {}, "defer_mortal_wounds": True}
        remaining_by_target: dict[str, dict] = {}
        for decl in weapon_declarations:
            t = decl.get("target_unit")
            if t is None:
                continue
            tid = get_entity_id(t)
            entry = remaining_by_target.get(tid)
            if entry is None:
                remaining_by_target[tid] = {"unit": t, "count": 1}
            else:
                entry["count"] = int(entry.get("count", 0) or 0) + 1

        # Execute each weapon declaration
        for declaration in weapon_declarations:
            weapon_profile = declaration['weapon_profile']
            target_unit = declaration['target_unit']
            models_with_weapon = declaration['models']
            weapon_instance = declaration.get('weapon_instance', None)
            try:
                # Validate this declaration
                validation = self._validate_shooting_declaration(weapon_profile, target_unit, models_with_weapon, game_map)
                if not validation['valid']:
                    print(f"{self.name} - {weapon_profile.name}: {validation['reason']}")
                    continue

                # Execute attacks with this weapon
                weapon_attacks = self._execute_weapon_attacks(
                    weapon_profile,
                    target_unit,
                    models_with_weapon,
                    game_map,
                    weapon_instance,
                    hit_tracker=hit_tracker,
                    hit_models_by_target=hit_models_by_target,
                    attack_context=attack_context,
                )
                successful_attacks += weapon_attacks
            finally:
                tid = get_entity_id(target_unit)
                entry = remaining_by_target.get(tid)
                if entry is not None:
                    entry["count"] = int(entry.get("count", 0) or 0) - 1
                    if entry["count"] <= 0:
                        self._resolve_pending_attack_mortal_wounds(attack_context, entry["unit"], game_map=game_map)

        try:
            game = self.get_parent_army().player.game
            if game is not None and hasattr(game, "event_system"):
                game.event_system.publish(
                    "unit_shooting_resolved",
                    attacker_unit=self,
                    hits_by_target=dict(hit_tracker),
                    hit_models_by_target=dict(hit_models_by_target),
                )
        except Exception:
            pass
            
        # Report shooting results
        if successful_attacks > 0:
            print(f"{self.name} completed shooting with {successful_attacks} attacks executed")
            try:
                from ..utility.event_bus import append_action
                pn = self.get_parent_army().player
                append_action(pn, f"{self.name} completed shooting: {successful_attacks} attacks")
            except Exception:
                pass
            
            # Check if target unit was destroyed
            for declaration in weapon_declarations:
                target_unit = declaration['target_unit']
                if not target_unit.is_alive():
                    print(f"{target_unit.name} has been destroyed!")
        else:
            print(f"{self.name} failed to execute any attacks")
            
        # End attack resolution window(s) and resolve pending separations (now that this unit is done attacking).
        try:
            for t in touched_targets:
                if hasattr(t, "end_attack_resolution"):
                    t.end_attack_resolution(game_map=game_map)
        except Exception:
            pass

        # Clear BGNT snapshot to avoid leaking state into future activations.
        try:
            delattr(self, "_bgnt_locked_at_target_selection")
        except Exception:
            pass

        return successful_attacks > 0
    
    def _validate_shooting_declaration(self, weapon_profile, target_unit, models_with_weapon, game_map) -> dict:
        """Validate a shooting declaration"""
        # Check if target is an enemy unit
        if target_unit.get_parent_army() == self.get_parent_army():
            return {"valid": False, "reason": "Cannot target friendly units"}
        
        # Check if target is alive
        if not target_unit.is_alive():
            return {"valid": False, "reason": "Target unit is destroyed"}
        
        # Check if unit can shoot after advancing
        if self.round_state.advanced_this_round:
            # Unit method already checks both weapon-specific and unit-specific abilities
            if not self.can_shoot_after_advance(weapon_profile):
                return {"valid": False, "reason": "Unit advanced and cannot shoot with this weapon"}
        
        # Check if unit can shoot after falling back
        if self.round_state.fell_back_this_round:
            if not self.can_shoot_after_fall_back(weapon_profile):
                return {"valid": False, "reason": "Unit fell back and cannot shoot with this weapon"}

        # Thrill Seekers: extra target restrictions when advancing or falling back
        game = None
        try:
            game = self.get_parent_army().player.game
        except Exception:
            game = None
        reason = self._thrill_seekers_restriction_reason(target_unit, game)
        if reason:
            return {"valid": False, "reason": reason}
        
        # Check if any models can actually shoot this weapon at the target
        models_in_range = []
        for model in models_with_weapon:
            if not model.is_alive:
                continue
                
            # Check if this model has the weapon
            has_weapon = False
            for wargear in model.wargear:
                if weapon_profile.parent_wargear == wargear:
                    has_weapon = True
                    break
            
            if not has_weapon:
                continue

            # ONE SHOT: weapons with this keyword can only be used once per battle (per model).
            try:
                if getattr(weapon_profile, "is_one_shot", lambda: False)():
                    key = getattr(weapon_profile, "one_shot_key", lambda: "")()
                    used = getattr(model, "_one_shot_used", set())
                    if key and key in used:
                        continue
            except Exception:
                # If anything goes wrong, do not block the shot.
                pass
                
            # Check range and line of sight
            if self._can_model_shoot_weapon_at_target(model, weapon_profile, target_unit, game_map):
                models_in_range.append(model)
        
        if not models_in_range:
            return {"valid": False, "reason": "No models in range or line of sight"}
            
        return {"valid": True, "reason": "Valid shooting declaration"}
    
    def _can_model_shoot_weapon_at_target(self, model, weapon_profile, target_unit, game_map) -> bool:
        """Check if a specific model can shoot a weapon at a target"""
        # INDIRECT FIRE + TORRENT: Torrent weapons cannot be used "via Indirect Fire" when no target models are visible.
        # Practical enforcement: if a weapon has both keywords, require visibility to at least one target model.
        try:
            if weapon_profile.is_indirect_fire() and weapon_profile.is_torrent():
                if not self._attacking_unit_has_any_los_to_target_unit(target_unit, game_map):
                    return False
        except Exception:
            # If anything goes wrong, be conservative and require LOS for Torrent+Indirect weapons.
            try:
                if weapon_profile.is_indirect_fire() and weapon_profile.is_torrent():
                    if not self._attacking_unit_has_any_los_to_target_unit(target_unit, game_map):
                        return False
            except Exception:
                pass

        # TARGET LEGALITY: Locked in Combat targeting restrictions (10e).
        # - Units that are Locked in Combat normally cannot be selected as targets of ranged attacks.
        # - Exception: in the controlling player's Shooting phase, VEHICLE/MONSTER units can be targeted even while Locked.
        # - Pistols can target units within Engagement Range of the shooter (own combat), enforced here.
        # - BGNT also allows a VEHICLE/MONSTER (in its controlling player's Shooting phase) to target enemy units
        #   it is within Engagement Range of (i.e., shoot into its own combat), subject to BLAST restriction.
        target_locked = Unit._is_unit_locked_in_combat(target_unit, game_map)
        if target_locked:
            shooter_in_er_of_target = game_map.is_within_engagement_range(self, target_unit)
            if weapon_profile.is_pistol():
                if not shooter_in_er_of_target:
                    return False
            else:
                in_phase = self._is_controlling_players_shooting_phase()
                if shooter_in_er_of_target:
                    # BGNT: shoot into own combat (target is in ER of this unit) in-phase.
                    if not ((self.is_vehicle or self.is_monster) and in_phase):
                        return False
                else:
                    # BGNT target exception: target is a VEHICLE/MONSTER and shooter is in its shooting phase.
                    if not ((target_unit.is_vehicle or target_unit.is_monster) and in_phase):
                        return False

        # BLAST restriction supersedes BGNT targeting:
        # Blast weapons cannot target a unit that is within Engagement Range of any friendly unit (relative to the shooter).
        if weapon_profile.is_blast():
            for friendly in game_map.get_friendly_units(self):
                if not friendly.is_alive() or not getattr(friendly, "deployed", True):
                    continue
                if game_map.is_within_engagement_range(friendly, target_unit):
                    return False

        # Check range using base-to-base closest-point distance (not centroid-to-centroid, not model height)
        min_distance = float('inf')
        target_models = target_unit.get_models_for_collision()
        from ..utility.aura_utils import distance_between_models_bases_3d
        for target_model in target_models:
            if not target_model.is_alive:
                continue
            distance = float(distance_between_models_bases_3d(model, target_model))
            min_distance = min(min_distance, distance)
        
        if min_distance > weapon_profile.range.max:
            return False

        # Check line of sight (INDIRECT FIRE weapons can target without LOS)
        try:
            if not getattr(weapon_profile, "is_indirect_fire", lambda: False)():
                if not self._has_line_of_sight_to_target(model, target_unit, game_map):
                    return False
        except Exception:
            # If anything goes wrong determining indirect/LOS, fall back to requiring LOS
            if not self._has_line_of_sight_to_target(model, target_unit, game_map):
                return False
            
        # Check Lone Operative restriction
        if target_unit.has_lone_operative():
            # Lone Operative units can only be targeted if the attacking model is within 12 inches
            if min_distance > 12.0:
                return False

        # Wreathed in Shadows (Belakor Shadow Form): 18" ranged targeting restriction.
        try:
            from ..rules.shadow_form import target_unit_has_wreathed_in_shadows
            if target_unit_has_wreathed_in_shadows(target_unit, game_map=game_map):
                if min_distance > 18.0:
                    return False
        except Exception:
            pass
            
        # Check engagement range restrictions
        if not self._can_shoot_while_engaged(model, weapon_profile, target_unit, game_map):
            return False
            
        return True

    def is_target_closest_eligible(
        self,
        model,
        weapon_profile,
        target_unit,
        game_map,
        *,
        max_distance: Optional[float] = None,
        require_keywords: Optional[set[str]] = None,
    ) -> bool:
        """Return True if target_unit is the closest eligible target for this model/weapon."""
        if model is None or weapon_profile is None or target_unit is None or game_map is None:
            return False

        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        required = None
        if require_keywords:
            try:
                required = {str(k or "").strip() for k in require_keywords if str(k or "").strip()}
            except Exception:
                required = None

        def _matches_required(unit) -> bool:
            if not required:
                return True
            for kw in required:
                try:
                    if unit.has_any_keyword(kw):
                        return True
                except Exception:
                    continue
            return False

        if not _matches_required(target_root):
            return False

        try:
            if not self._can_model_shoot_weapon_at_target(model, weapon_profile, target_root, game_map):
                return False
        except Exception:
            return False

        def _min_distance_to_unit(unit) -> Optional[float]:
            try:
                target_models = unit.get_models_for_collision()
            except Exception:
                target_models = list(getattr(unit, "models", []) or [])
            from ..utility.aura_utils import distance_between_models_bases_3d
            min_dist = float("inf")
            for tm in target_models:
                if not getattr(tm, "is_alive", False):
                    continue
                dist = float(distance_between_models_bases_3d(model, tm))
                if dist < min_dist:
                    min_dist = dist
            if min_dist == float("inf"):
                return None
            return min_dist

        target_dist = _min_distance_to_unit(target_root)
        if target_dist is None:
            return False
        if max_distance is not None and target_dist > max_distance:
            return False

        closest = None
        seen = set()
        for enemy_unit in game_map.get_enemy_units(self):
            try:
                root = enemy_unit.get_attached_unit_root()
            except Exception:
                root = enemy_unit
            if root is None:
                continue
            rid = get_entity_id(root)
            if rid in seen:
                continue
            seen.add(rid)
            try:
                if hasattr(root, "is_alive") and callable(root.is_alive) and not root.is_alive():
                    continue
            except Exception:
                pass
            try:
                if hasattr(root, "deployed") and not bool(getattr(root, "deployed", True)):
                    continue
            except Exception:
                pass
            try:
                if not self._can_model_shoot_weapon_at_target(model, weapon_profile, root, game_map):
                    continue
            except Exception:
                continue
            if not _matches_required(root):
                continue
            dist = _min_distance_to_unit(root)
            if dist is None:
                continue
            if max_distance is not None and dist > max_distance:
                continue
            if closest is None or dist < closest:
                closest = dist

        if closest is None:
            return False
        return target_dist <= closest + 1e-6

    def _attacking_unit_has_any_los_to_target_unit(self, target_unit, game_map) -> bool:
        """Return True if ANY model in this unit has LOS to ANY model in target_unit."""
        try:
            for m in self.models:
                if not getattr(m, "is_alive", False):
                    continue
                if self._has_line_of_sight_to_target(m, target_unit, game_map):
                    return True
        except Exception:
            pass
        return False
    
    def _has_line_of_sight_to_target(self, shooting_model, target_unit, game_map) -> bool:
        """Check if shooting model has line of sight to target unit.

        LOS exists if a line can be drawn from ANY point on the shooter's 3D volume
        to ANY point on the 3D volume of ANY model in the target unit without being
        blocked by terrain or enemy models. Friendly models are ignored for blocking.
        """
        # Late imports to avoid circulars
        from shapely.geometry import LineString

        def sample_model_points_3d(model: 'Model', perimeter_points: int = 8, z_levels: int = 3) -> list:
            base_shape = model.model_base.get_base_shape()
            # Ensure polygon exterior length > 0
            exterior = base_shape.exterior
            perimeter_samples = []
            if exterior.length > 0 and perimeter_points > 0:
                step = exterior.length / perimeter_points
                for i in range(perimeter_points):
                    p = exterior.interpolate(step * i)
                    perimeter_samples.append((p.x, p.y))
            # Always include centroid
            centroid = base_shape.centroid
            xy_points = [(centroid.x, centroid.y)] + perimeter_samples

            # Z samples: bottom, mid, top (minus tiny epsilon to stay within volume)
            z_bottom = model.model_base.z
            z_top = model.model_base.z + getattr(model.model_base, 'model_height', 2.0)
            if z_levels <= 1:
                z_samples = [z_bottom + 0.01]
            elif z_levels == 2:
                z_samples = [z_bottom + 0.01, z_top - 0.01]
            else:
                z_mid = (z_bottom + z_top) / 2.0
                z_samples = [z_bottom + 0.01, z_mid, z_top - 0.01]

            points_3d = []
            for (x, y) in xy_points:
                for z in z_samples:
                    points_3d.append((x, y, z))
            return points_3d

        def is_segment_blocked(p0: tuple, p1: tuple, target_model: 'Model') -> bool:
            # Quick reject: degenerate line in XY projects to a point
            line2d = LineString([(p0[0], p0[1]), (p1[0], p1[1])])
            if line2d.length == 0:
                return False

            # Helper to compute z at param t along the 2D line
            def z_at_t(t: float) -> float:
                return p0[2] + t * (p1[2] - p0[2])

            # Terrain blocking (including special Ruins visibility rules)
            for terrain in getattr(game_map, 'terrain_features', []):
                footprint = getattr(terrain, 'footprint', None)
                # Special Ruins visibility handling
                is_ruins = hasattr(terrain, 'walls') and hasattr(terrain, 'openings') and footprint is not None
                if is_ruins and footprint is not None:
                    shooter_shape = shooting_model.model_base.get_base_shape()
                    target_shape = target_model.model_base.get_base_shape()
                    shooter_inside_any = footprint.intersects(shooter_shape)
                    target_inside_any = footprint.intersects(target_shape)
                    shooter_wholly_within = footprint.covers(shooter_shape)
                    shooter_is_aircraft = False
                    target_is_aircraft = False
                    shooter_is_towering = False
                    try:
                        shooter_is_aircraft = bool(getattr(shooting_model.parent_unit, "is_aircraft", False))
                        target_is_aircraft = bool(getattr(target_model.parent_unit, "is_aircraft", False))
                        shooter_is_towering = bool(getattr(shooting_model.parent_unit, "is_towering", False))
                    except Exception:
                        pass

                    # Aircraft always default to normal LOS: skip special ruins blocking
                    if shooter_is_aircraft or target_is_aircraft:
                        pass
                    else:
                    # If both models are outside this ruins and the footprint lies between them, LOS is blocked.
                        if not shooter_inside_any and not target_inside_any:
                            if line2d.intersects(footprint):
                                return True

                    # If shooter is inside this ruins but not wholly within and not towering, cannot see out
                        if shooter_inside_any and not shooter_wholly_within and not shooter_is_towering:
                            if not target_inside_any:
                                # Shooter partially within cannot see out of the ruins
                                return True

                    # Otherwise, visibility to/from/within ruins is determined normally below

                # If terrain has explicit walls/openings (e.g., ruins), treat walls as vertical blockers
                walls = getattr(terrain, 'walls', None)
                openings = getattr(terrain, 'openings', None)
                if walls:
                    for wall in walls:
                        wall_poly = wall.get('polygon')
                        if wall_poly is None:
                            continue
                        if not line2d.intersects(wall_poly):
                            continue
                        inter = line2d.intersection(wall_poly)
                        # Representative intersection point in XY
                        inter_pt = None
                        if inter.is_empty:
                            continue
                        if inter.geom_type == 'Point':
                            inter_pt = inter
                        elif inter.geom_type in ('LineString', 'MultiPoint', 'MultiLineString'):
                            # Take centroid for a representative point
                            inter_pt = inter.centroid
                        else:
                            inter_pt = inter.representative_point()

                        # Compute param t along line for z
                        t = line2d.project(inter_pt) / line2d.length if line2d.length > 0 else 0.0
                        # Ignore intersections at endpoints
                        if t <= 1e-6 or t >= 1.0 - 1e-6:
                            continue
                        z_here = z_at_t(t)
                        z_bottom = wall.get('z_bottom', 0.0)
                        z_top = wall.get('z_top', z_bottom)

                        if z_bottom <= z_here <= z_top:
                            # Check if an opening at this XY,Z allows LOS
                            allowed = False
                            if openings:
                                for op in openings:
                                    if not op.get('allows_los', False):
                                        continue
                                    op_poly = op.get('polygon')
                                    if op_poly is None:
                                        continue
                                    if not op_poly.contains(inter_pt):
                                        continue
                                    if op.get('z_bottom', -1e9) <= z_here <= op.get('z_top', 1e9):
                                        allowed = True
                                        break
                            if not allowed:
                                return True  # Blocked by wall without LOS opening
                else:
                    # Generic blocking by terrain footprint with height
                    footprint = getattr(terrain, 'footprint', None)
                    if footprint is None:
                        continue
                    if not line2d.intersects(footprint):
                        continue
                    inter = line2d.intersection(footprint)
                    if inter.is_empty:
                        continue
                    # Representative intersection point
                    if inter.geom_type == 'Point':
                        inter_pt = inter
                    elif inter.geom_type in ('LineString', 'MultiPoint', 'MultiLineString'):
                        inter_pt = inter.centroid
                    else:
                        inter_pt = inter.representative_point()
                    t = line2d.project(inter_pt) / line2d.length if line2d.length > 0 else 0.0
                    if t <= 1e-6 or t >= 1.0 - 1e-6:
                        continue
                    z_here = z_at_t(t)
                    # Determine vertical bounds
                    min_z, max_z = 0.0, 0.0
                    if hasattr(terrain, 'height'):
                        min_z, max_z = 0.0, getattr(terrain, 'height')
                    elif hasattr(terrain, 'rim_height'):
                        min_z, max_z = 0.0, getattr(terrain, 'rim_height')
                    elif hasattr(terrain, 'bounding_box') and isinstance(terrain.bounding_box, dict):
                        try:
                            min_z = terrain.bounding_box.get('min', (0, 0, 0))[2]
                            max_z = terrain.bounding_box.get('max', (0, 0, 0))[2]
                        except Exception:
                            min_z, max_z = 0.0, 2.0
                    else:
                        max_z = 2.0  # default obstacle height
                    if min_z <= z_here <= max_z:
                        return True

            # Enemy models blocking (ignore friendlies and ignore models in the target unit)
            for enemy_unit in game_map.get_enemy_units(self):
                if not enemy_unit.is_alive() or not enemy_unit.deployed:
                    continue
                if enemy_unit == target_unit:
                    continue
                for enemy_model in enemy_unit.models:
                    if not enemy_model.is_alive:
                        continue
                    enemy_poly = enemy_model.model_base.get_base_shape()
                    if not line2d.intersects(enemy_poly):
                        continue
                    inter = line2d.intersection(enemy_poly)
                    if inter.is_empty:
                        continue
                    if inter.geom_type == 'Point':
                        inter_pt = inter
                    elif inter.geom_type in ('LineString', 'MultiPoint', 'MultiLineString'):
                        inter_pt = inter.centroid
                    else:
                        inter_pt = inter.representative_point()
                    t = line2d.project(inter_pt) / line2d.length if line2d.length > 0 else 0.0
                    if t <= 1e-6 or t >= 1.0 - 1e-6:
                        continue
                    z_here = z_at_t(t)
                    em_z0 = enemy_model.model_base.z
                    em_z1 = em_z0 + getattr(enemy_model.model_base, 'model_height', 2.0)
                    if em_z0 <= z_here <= em_z1:
                        return True

            return False

        # Validate inputs
        if shooting_model is None or target_unit is None or game_map is None:
            return False
        if not shooting_model.is_alive or not target_unit.is_alive():
            return False

        # Sample 3D points on shooter and on each target model; LOS if any pair is unblocked
        shooter_points = sample_model_points_3d(shooting_model, perimeter_points=8, z_levels=3)

        for target_model in target_unit.models:
            if not target_model.is_alive:
                continue
            target_points = sample_model_points_3d(target_model, perimeter_points=8, z_levels=3)
            for p0 in shooter_points:
                for p1 in target_points:
                    if not is_segment_blocked(p0, p1, target_model):
                        return True

        return False
    
    def _can_shoot_while_engaged(self, model, weapon_profile, target_unit, game_map) -> bool:
        """Check if model can shoot while engaged with other units"""
        # Check if unit is in engagement range
        is_engaged = any(game_map.is_within_engagement_range(self, enemy)
                        for enemy in game_map.get_enemy_units(self) if enemy.is_alive())
        
        if not is_engaged:
            return True
            
        # If engaged, check weapon type and target
        # PISTOL (10e):
        # - A unit can shoot with Pistols while within Engagement Range.
        # - When it does so, it must target an enemy unit it is within Engagement Range of.
        if weapon_profile.is_pistol():
            return game_map.is_within_engagement_range(self, target_unit)

        # VEHICLE / MONSTER (Big Guns Never Tire style behavior):
        # Only applies in the controlling player's Shooting phase.
        if self.is_vehicle or self.is_monster:
            if not self._is_controlling_players_shooting_phase():
                return False

            # BLAST restriction (friendly engagement) is enforced in _can_model_shoot_weapon_at_target.
            # Keep a small safety-net here too for direct callers.
            if weapon_profile.is_blast():
                for friendly in game_map.get_friendly_units(self):
                    if not friendly.is_alive() or not getattr(friendly, "deployed", True):
                        continue
                    if game_map.is_within_engagement_range(friendly, target_unit):
                        return False
            return True
            
        # Check if target is the unit we're engaged with
        if game_map.is_within_engagement_range(self, target_unit):
            return weapon_profile.is_pistol()
            
        # If target is different from engaged unit, only vehicles can shoot
        return False
    
    def _execute_weapon_attacks(
        self,
        weapon_profile,
        target_unit,
        models_with_weapon,
        game_map,
        weapon_instance=None,
        hit_tracker=None,
        hit_models_by_target=None,
        attack_context: Optional[dict] = None,
    ) -> int:
        """Execute attacks with a specific weapon profile"""
        successful_attacks = 0
        
        for model in models_with_weapon:
            if not model.is_alive:
                continue

            active_profile = weapon_profile
            if getattr(active_profile, "is_bubblechukka", lambda: False)():
                roll = int(get_roll("D6") or 0)
                selected = active_profile.get_bubblechukka_profile_for_roll(roll)
                if selected is not None:
                    active_profile = selected
                    army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
                    player = getattr(army, "player", None)
                    if player is not None:
                        from ..utility.event_bus import append_dice
                        append_dice(player, f"Bubblechukka rolled {roll}: using {selected.name}")

            # ONE SHOT: prevent repeated use (per model)
            if getattr(active_profile, "is_one_shot", lambda: False)():
                key = getattr(active_profile, "one_shot_key", lambda: "")()
                used = getattr(model, "_one_shot_used", set())
                if key and key in used:
                    continue
                
            # Check if this model can still shoot this weapon at this target
            if not self._can_model_shoot_weapon_at_target(model, active_profile, target_unit, game_map):
                continue
                
            # Verify the model has this weapon
            has_weapon = False
            for wargear in model.wargear:
                for profile_name, profile in wargear.profiles.items():
                    if profile == active_profile:
                        has_weapon = True
                        break
                if has_weapon:
                    break
            
            if not has_weapon:
                continue
                
            # Execute the attack - each declaration represents exactly one weapon firing
            try:
                weapon_display = f"{active_profile.parent_wargear.name}"
                if weapon_instance:
                    weapon_display += f" #{weapon_instance}"
                print(f"{model.name} attacking with {weapon_display}")
                
                # Execute the attack using the weapon profile (pass game_map for cover/terrain context)
                try:
                    attack_result = active_profile.attack(
                        target_unit, model, game_map=game_map, attack_context=attack_context
                    )
                except TypeError as exc:
                    if "attack_context" in str(exc):
                        attack_result = active_profile.attack(
                            target_unit, model, game_map=game_map
                        )
                    else:
                        raise
                if hit_tracker is not None:
                    try:
                        hits = int(getattr(attack_result, "total_hits", 0) or 0)
                    except Exception:
                        hits = 0
                    if hits > 0:
                        hit_tracker[target_unit] = int(hit_tracker.get(target_unit, 0) or 0) + hits
                        if hit_models_by_target is not None:
                            try:
                                hit_models_by_target.setdefault(target_unit, set()).add(model)
                            except Exception:
                                pass
                # Count successful execution of the attack (not damage dealt)
                successful_attacks += 1

                # Mark ONE SHOT weapons as expended after firing (hit or miss).
                if getattr(active_profile, "is_one_shot", lambda: False)():
                    key = getattr(active_profile, "one_shot_key", lambda: "")()
                    if key:
                        used = getattr(model, "_one_shot_used", set())
                        if not isinstance(used, set):
                            used = set()
                        used.add(key)
                        setattr(model, "_one_shot_used", used)
            except Exception as e:
                print(f"Error executing attack with {weapon_profile.name}: {e}")
                # Don't increment successful_attacks if there was an exception
                
        return successful_attacks

    # Fight Phase Actions
    def pile_in_towards_enemies(self, game_map: 'Map') -> bool:
        print("WARN: Pile-in requires UI/controlled movement; legacy auto-move removed.")
        return False

    def _is_model_in_base_to_base_contact(self, model: 'Model', enemy_models: List['Model'], game_map: 'Map') -> bool:
        """Check if a model is in base-to-base (edge-to-edge) contact with any enemy model."""
        from ..utility.constants import BASE_CONTACT_EPSILON, ENGAGEMENT_RANGE_VERTICAL
        # Base-to-base contact is defined as bases touching (edge-to-edge ~= 0). We treat
        # anything within BASE_CONTACT_EPSILON as base contact to account for discretization.
        for enemy_model in enemy_models:
            from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
            edge = float(horizontal_distance_between_bases_2d(model.model_base, enemy_model.model_base))
            vert = float(vertical_distance_between_bases(model.model_base, enemy_model.model_base))
            if edge <= BASE_CONTACT_EPSILON and vert <= ENGAGEMENT_RANGE_VERTICAL:
                return True
        return False
    
    def consolidate_towards_enemies(self, game_map: 'Map') -> bool:
        print("WARN: Consolidate requires UI/controlled movement; legacy auto-move removed.")
        return False

    def auto_blood_surge_move(self, game_map: 'Map', max_distance: float) -> bool:
        print("WARN: Blood Surge requires UI/controlled movement; legacy auto-move removed.")
        return False

    def take_battle_shock_test(self, current_turn: int = 1):
        """Takes a battle shock test.
        
        Args:
            current_turn: The current battle round number (used for status effect duration)
        """
        # Destroyed units do not take Battle-shock tests, and abilities cannot force a destroyed unit to test.
        try:
            alive_models = any(bool(getattr(m, "is_alive", True)) for m in (getattr(self, "models", []) or []))
        except Exception:
            alive_models = False
        if not alive_models:
            try:
                for u in list(getattr(self, "attached_leaders", []) or []):
                    if any(bool(getattr(m, "is_alive", True)) for m in (getattr(u, "models", []) or [])):
                        alive_models = True
                        break
            except Exception:
                alive_models = alive_models
        if not alive_models:
            return

        is_already_battle_shocked = bool(self.is_battle_shocked())

        # Resolve event system (best-effort; avoid crashing on partial test stubs).
        event_system = None
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        player = getattr(army, "player", None) if army is not None else None
        game = getattr(player, "game", None) if player is not None else None
        event_system = getattr(game, "event_system", None) if game is not None else None

        if event_system is not None:
            try:
                event_system.publish("battle_shock_test_started", unit=self)
            except Exception:
                pass
        shadow_ctx = None
        shadow_mod = 0
        try:
            from ..rules.shadow_of_chaos import ShadowOfChaosManager
            shadow_ctx = ShadowOfChaosManager.battle_shock_context(self, game=game)
            shadow_mod = int(getattr(shadow_ctx, "modifier", 0) or 0)
        except Exception:
            shadow_ctx = None
            shadow_mod = 0
        synapse_3d6 = False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        try:
            synapse_mgr = getattr(army, "synapse", None) if army is not None else None
        except Exception:
            synapse_mgr = None
        try:
            if synapse_mgr is not None and synapse_mgr.unit_in_synapse_range(self, game=game):
                synapse_3d6 = True
        except Exception:
            synapse_3d6 = False
        extra_mod = 0
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and "battle_shock_test_modifier" in sr:
                extra_mod = int(sr.get("battle_shock_test_modifier", 0) or 0)
                sr.pop("battle_shock_test_modifier", None)
                sr.pop("battle_shock_test_modifier_reasons", None)
                self.special_rules = sr
        except Exception:
            extra_mod = 0
        # Core Stratagem: INSANE BRAVERY can make this unit automatically pass this test.
        # It is consumed on use (one-shot for the next Battle-shock test).
        auto_passed = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("auto_pass_next_battle_shock_test") is True:
                sr.pop("auto_pass_next_battle_shock_test", None)
                self.special_rules = sr
                passed = True
                auto_passed = True
            else:
                auto_passed = False
        except Exception:
            auto_passed = False

        icon_of_war_reroll_available = False
        if not auto_passed:
            try:
                icon_of_war_reroll_available = bool(self._icon_of_war_battle_shock_reroll_available())
            except Exception:
                icon_of_war_reroll_available = False

        if not auto_passed:
            total_mod = int(shadow_mod) + int(extra_mod)
            manual_roll = bool(synapse_3d6 or total_mod != 0 or icon_of_war_reroll_available)
            if not manual_roll:
                try:
                    passed = bool(self.pass_leadership_check())
                except Exception:
                    passed = False
            else:
                dice_expr = "3D6" if synapse_3d6 else "2D6"
                roll_result = None
                dice_rolls = None
                try:
                    army = self.get_parent_army()
                    mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    if mgr is not None and mgr.can_use_act_of_faith(self, game=game):
                        roll_result, dice_rolls, _miracle_used = mgr.resolve_roll(
                            self,
                            roll_type="battle-shock",
                            game=game,
                            dice_count=3 if synapse_3d6 else 2,
                            die_faces=6,
                        )
                except Exception:
                    roll_result = None
                    dice_rolls = None
                if roll_result is None:
                    roll_result = get_roll(dice_expr)
                leadership_value = self.leadership
                try:
                    mod_roll = int(roll_result) + int(total_mod)
                except Exception:
                    mod_roll = roll_result
                dice_note = ""
                try:
                    if dice_rolls and isinstance(dice_rolls, list):
                        dice_note = f" (dice {list(dice_rolls)})"
                except Exception:
                    dice_note = ""
                passed = mod_roll <= leadership_value
                if total_mod:
                    print(
                        f"{self.name} Leadership test: {dice_expr} rolled {roll_result}{dice_note} (mod {total_mod:+}) "
                        f"-> {mod_roll} vs Ld {leadership_value} - {'PASSED' if passed else 'FAILED'}"
                    )
                else:
                    print(
                        f"{self.name} Leadership test: {dice_expr} rolled {roll_result}{dice_note} "
                        f"-> {mod_roll} vs Ld {leadership_value} - {'PASSED' if passed else 'FAILED'}"
                    )

                if icon_of_war_reroll_available:
                    try:
                        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None)
                        is_human = self._player_has_local_control(player)
                    except Exception:
                        provider = None
                        is_human = False
                    if is_human and callable(provider):
                        try:
                            want_reroll = bool(
                                provider(
                                    player=player,
                                    unit=self,
                                    roll_type="battle-shock",
                                    value=roll_result,
                                    dice=dice_rolls,
                                )
                            )
                        except Exception:
                            want_reroll = False
                        try:
                            from ..utility.event_bus import append_action
                            pn = player
                        except Exception:
                            append_action = None
                            pn = None
                        if want_reroll:
                            original_roll = roll_result
                            new_roll = get_roll(dice_expr)
                            roll_result = new_roll
                            try:
                                mod_roll = int(roll_result) + int(total_mod)
                            except Exception:
                                mod_roll = roll_result
                            passed = mod_roll <= leadership_value
                            if append_action and pn:
                                append_action(
                                    pn,
                                    f"Icon of War: {self.name} re-rolls Battle-shock test ({original_roll} -> {new_roll}).",
                                )
                            if total_mod:
                                print(
                                    f"{self.name} Leadership test re-roll: {dice_expr} rolled {roll_result} (mod {total_mod:+}) "
                                    f"-> {mod_roll} vs Ld {leadership_value} - {'PASSED' if passed else 'FAILED'}"
                                )
                            else:
                                print(
                                    f"{self.name} Leadership test re-roll: {dice_expr} rolled {roll_result} "
                                    f"-> {mod_roll} vs Ld {leadership_value} - {'PASSED' if passed else 'FAILED'}"
                                )
                        else:
                            if append_action and pn:
                                append_action(
                                    pn,
                                    f"Icon of War: {self.name} keeps Battle-shock roll ({roll_result}).",
                                )

        # Units that are already Battle-shocked can still be forced to take another Battle-shock test,
        # but the result does not change the unit's Battle-shocked status or duration.
        if (not passed) and (not is_already_battle_shocked):
            battle_shock_effect = BattleShockEffect(current_turn)
            self.apply_status_effect(battle_shock_effect)
            print(f"{self.name} has failed the battle shock test and is battle-shocked!")

        if shadow_ctx is not None:
            try:
                from ..rules.shadow_of_chaos import ShadowOfChaosManager
                ShadowOfChaosManager.apply_battle_shock_outcome(self, passed=passed, context=shadow_ctx, game=game)
            except Exception:
                pass

        if event_system is not None:
            try:
                event_system.publish("battle_shock_test_resolved", unit=self, passed=passed)
            except Exception:
                pass

    def clear_battle_shock(self) -> bool:
        """Remove Battle-shock from this unit (used at the start of its owner's next Command phase)."""
        removed = False
        for eff in list(getattr(self, "status_effects", []) or []):
            if isinstance(eff, BattleShockEffect):
                try:
                    self.remove_status_effect(eff)
                    removed = True
                except Exception:
                    continue
        return removed

    # ---------------- Reanimation Protocols ----------------

    def _reanimation_choose_model(self, eligible_models, *, is_human: bool, provider, reason: str, instruction: Optional[str] = None):
        if not eligible_models:
            return None
        if len(eligible_models) == 1:
            return eligible_models[0]
        if is_human and callable(provider):
            try:
                ctx = {"reason": reason}
                if instruction:
                    ctx["instruction"] = instruction
                chosen = provider(self.get_attached_unit_root(), list(eligible_models), ctx)
                if chosen is not None and chosen in eligible_models:
                    return chosen
            except Exception:
                pass
        return eligible_models[0]

    def _check_collision_with_obstacles_or_terrain(
        self,
        game_map: Optional['Map'],
        model: Model,
        destination: Tuple[float, float],
    ) -> bool:
        if game_map is None or model is None:
            return False
        fn = getattr(game_map, "check_collision_with_obstacles", None)
        if not callable(fn):
            fn = getattr(game_map, "check_collision_with_terrain", None)
        if callable(fn):
            try:
                return bool(fn(model, destination=destination))
            except Exception:
                return False
        return False

    def _reanimation_position_valid(
        self,
        x: float,
        y: float,
        z: float,
        facing: float,
        model: Model,
        alive_models: list[Model],
        game_map: Optional['Map'],
        required_neighbors: int,
    ) -> bool:
        if game_map is None:
            return True
        try:
            if not game_map.is_within_boundary(model, destination=(x, y)):
                return False
            if self._check_collision_with_obstacles_or_terrain(game_map, model, (x, y)):
                return False
            if game_map.check_collision_with_other_friendly_units(model, destination=(x, y)):
                return False
            if game_map.check_collision_with_other_enemy_units(model, destination=(x, y)):
                return False
        except Exception:
            return False

        try:
            candidate_base = self._create_potential_base(x, y, z, facing, model=model)
        except Exception:
            return False

        for m in list(alive_models or []):
            try:
                if not getattr(m, "is_alive", True):
                    continue
            except Exception:
                pass
            try:
                if candidate_base.collides_with(m.model_base):
                    return False
            except Exception:
                pass

        if required_neighbors <= 0:
            return True

        neighbors = 0
        for m in list(alive_models or []):
            try:
                base = m.model_base
                horizontal = candidate_base.get_base_shape().distance(base.get_base_shape())
                vertical = abs(float(getattr(candidate_base, "z", 0.0)) - float(getattr(base, "z", 0.0)))
            except Exception:
                continue
            if horizontal <= 2.0 + 1e-6 and vertical <= 5.0 + 1e-6:
                neighbors += 1
                if neighbors >= required_neighbors:
                    return True
        return False

    def _find_reanimation_position(
        self,
        model: Model,
        alive_models: list[Model],
        *,
        game_map: Optional['Map'],
        required_neighbors: int,
    ) -> Optional[Tuple[float, float, float, float]]:
        if not alive_models:
            return None
        if game_map is None:
            return None

        try:
            mr = float(model.model_base.get_longest_radius())
        except Exception:
            try:
                mr = float(model.model_base.get_radius())
            except Exception:
                mr = 1.0

        for anchor in list(alive_models or []):
            try:
                ax, ay, az, af = anchor.get_location()
            except Exception:
                continue
            try:
                ar = float(anchor.model_base.get_longest_radius())
            except Exception:
                try:
                    ar = float(anchor.model_base.get_radius())
                except Exception:
                    ar = 1.0

            min_center = ar + mr + 0.05
            max_center = min_center + 2.0 + 1e-6
            for ring in np.arange(0.0, max(0.01, max_center - min_center) + 0.001, 0.5):
                r = float(min_center + ring)
                if r > max_center + 1e-6:
                    break
                for deg in range(0, 360, 15):
                    ang = math.radians(deg)
                    x = ax + math.cos(ang) * r
                    y = ay + math.sin(ang) * r
                    z = az
                    facing = af
                    if self._reanimation_position_valid(
                        x,
                        y,
                        z,
                        facing,
                        model,
                        alive_models,
                        game_map,
                        required_neighbors,
                    ):
                        return (x, y, z, facing)
        return None

    def return_destroyed_bodyguard_models(
        self,
        amount: int,
        *,
        game_map: Optional['Map'] = None,
        chosen_models: Optional[list[Model]] = None,
    ) -> int:
        if int(amount or 0) <= 0:
            return 0
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return 0
        try:
            if bool(getattr(root, "is_leader", False)):
                return 0
        except Exception:
            pass

        try:
            destroyed = list(getattr(root, "models_lost", []) or [])
        except Exception:
            destroyed = []
        if not destroyed:
            return 0

        try:
            starting = int(getattr(root, "starting_model_count", 0) or 0)
        except Exception:
            starting = 0
        if starting <= 0:
            try:
                starting = len(getattr(root, "models", []) or []) + len(destroyed)
            except Exception:
                starting = len(destroyed)

        try:
            alive_models = [m for m in (getattr(root, "models", []) or []) if getattr(m, "is_alive", True)]
        except Exception:
            alive_models = list(getattr(root, "models", []) or [])

        current = len(alive_models)
        if starting and current >= starting:
            return 0

        max_return = int(amount or 0)
        if starting:
            max_return = min(max_return, max(0, starting - current))
        if max_return <= 0:
            return 0
        if chosen_models is not None:
            to_return = []
            seen_ids: set[str] = set()
            for model in list(chosen_models or []):
                if model is None:
                    continue
                mid = get_entity_id(model)
                if mid in seen_ids:
                    continue
                if model in destroyed:
                    to_return.append(model)
                    seen_ids.add(mid)
        else:
            to_return = destroyed[:max_return]
        if not to_return:
            return 0
        if len(to_return) > max_return:
            to_return = to_return[:max_return]

        returned = 0
        for model in to_return:
            try:
                if hasattr(root, "models_lost") and model in root.models_lost:
                    root.models_lost.remove(model)
            except Exception:
                pass
            try:
                if hasattr(model, "set_parent_unit"):
                    model.set_parent_unit(root)
                else:
                    model.parent_unit = root
            except Exception:
                pass
            try:
                base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
            except Exception:
                base_wounds = 0
            if base_wounds <= 0:
                base_wounds = 1
            try:
                model.wounds = base_wounds
            except Exception:
                try:
                    model._wounds = base_wounds
                except Exception:
                    pass
            try:
                if hasattr(model, "_check_damaged_profile"):
                    model._check_damaged_profile()
            except Exception:
                pass
            try:
                setattr(model, "_on_death_reactions_resolved", False)
                setattr(model, "_fight_on_death_used", False)
                setattr(model, "_shoot_on_death_used", False)
            except Exception:
                pass
            added = False
            try:
                if hasattr(root, "add_model"):
                    root.add_model(model)
                    added = True
                else:
                    root.models.append(model)
                    added = True
            except Exception:
                added = False
            if not added:
                try:
                    root.models.append(model)
                except Exception:
                    pass
            try:
                if alive_models and hasattr(root, "_find_reanimation_position"):
                    new_count = len(alive_models) + 1
                    required_neighbors = 0 if new_count <= 1 else (2 if new_count >= 7 else 1)
                    pos = root._find_reanimation_position(
                        model,
                        alive_models,
                        game_map=game_map,
                        required_neighbors=required_neighbors,
                    )
                    if pos is not None and hasattr(model, "set_location"):
                        model.set_location(*pos)
            except Exception:
                pass
            alive_models.append(model)
            try:
                if hasattr(root, "update_coherency"):
                    root.update_coherency()
            except Exception:
                pass
            returned += 1
        return returned

    def apply_reanimation_protocols(
        self,
        wounds_to_restore: int,
        *,
        game_map: Optional['Map'] = None,
        is_human: bool = False,
        provider=None,
    ) -> dict:
        """
        Resolve Reanimation Protocols for this (attached) unit group.

        Returns a dict with counts of healed wounds and returned models.
        """
        result = {"healed": 0, "returned": 0}
        if int(wounds_to_restore or 0) <= 0:
            return result

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        try:
            if not getattr(root, "deployed", True):
                return result
            if str(getattr(root, "reserve_status", "deployed")) != "deployed":
                return result
            if hasattr(root, "is_in_reserves") and callable(getattr(root, "is_in_reserves")):
                if bool(root.is_in_reserves()):
                    return result
            if bool(getattr(root, "embarked_in", None)):
                return result
            if bool(getattr(root, "is_embarked", False)):
                return result
        except Exception:
            pass

        try:
            if hasattr(root, "is_alive") and callable(getattr(root, "is_alive")) and not root.is_alive():
                return result
        except Exception:
            pass

        try:
            members = root.get_attached_unit_members()
        except Exception:
            members = [root]

        def _is_alive_model(m) -> bool:
            try:
                return bool(getattr(m, "is_alive", True))
            except Exception:
                return True

        def _is_wounded_model(m) -> bool:
            try:
                return _is_alive_model(m) and (not bool(getattr(m, "is_max_health", True)))
            except Exception:
                try:
                    w = int(getattr(m, "wounds", 0))
                    bw = int(getattr(m, "_base_wounds", getattr(m, "base_wounds", w)))
                    return _is_alive_model(m) and w < bw
                except Exception:
                    return False

        alive_models = [m for u in (members or []) for m in (getattr(u, "models", []) or []) if _is_alive_model(m)]
        if not alive_models:
            return result

        for _ in range(int(wounds_to_restore or 0)):
            wounded = [m for m in alive_models if _is_wounded_model(m)]
            if wounded:
                target = self._reanimation_choose_model(
                    wounded,
                    is_human=is_human,
                    provider=provider,
                    reason="Reanimation Protocols - Restore Wound",
                    instruction="Select a wounded model to regain 1 wound.",
                )
                if target is None:
                    break
                try:
                    if hasattr(target, "heal"):
                        target.heal(1)
                    else:
                        base_wounds = int(getattr(target, "_base_wounds", getattr(target, "base_wounds", 0)) or 0)
                        target.wounds = min(base_wounds, int(getattr(target, "wounds", 0) or 0) + 1)
                    if hasattr(target, "_check_damaged_profile"):
                        target._check_damaged_profile()
                except Exception:
                    pass
                result["healed"] += 1
                continue

            try:
                if hasattr(root, "is_below_starting_strength") and callable(getattr(root, "is_below_starting_strength")):
                    if not root.is_below_starting_strength():
                        break
            except Exception:
                pass

            destroyed_pool: List[Tuple['Unit', Model]] = []
            for u in (members or []):
                lost = getattr(u, "models_lost", None)
                if isinstance(lost, list) and lost:
                    destroyed_pool.extend([(u, m) for m in lost])
            if not destroyed_pool:
                break

            if len(destroyed_pool) == 1:
                unit_for_model, model = destroyed_pool[0]
            else:
                candidates = [m for (_u, m) in destroyed_pool]
                chosen = self._reanimation_choose_model(
                    candidates,
                    is_human=is_human,
                    provider=provider,
                    reason="Reanimation Protocols - Return Model",
                    instruction="Select a destroyed model to return with 1 wound.",
                )
                if chosen is None or chosen not in candidates:
                    chosen = candidates[0]
                unit_for_model = next((u for (u, m) in destroyed_pool if m is chosen), members[0])
                model = chosen

            try:
                if hasattr(unit_for_model, "models_lost") and model in unit_for_model.models_lost:
                    unit_for_model.models_lost.remove(model)
            except Exception:
                pass

            try:
                if hasattr(model, "set_parent_unit"):
                    model.set_parent_unit(unit_for_model)
                else:
                    model.parent_unit = unit_for_model
            except Exception:
                pass

            try:
                model.wounds = 1
            except Exception:
                try:
                    model._wounds = 1
                except Exception:
                    pass
            try:
                if hasattr(model, "_check_damaged_profile"):
                    model._check_damaged_profile()
            except Exception:
                pass

            try:
                setattr(model, "_on_death_reactions_resolved", False)
                setattr(model, "_fight_on_death_used", False)
                setattr(model, "_shoot_on_death_used", False)
            except Exception:
                pass

            try:
                if hasattr(unit_for_model, "add_model"):
                    unit_for_model.add_model(model)
                else:
                    unit_for_model.models.append(model)
            except Exception:
                pass

            alive_models = [m for u in (members or []) for m in (getattr(u, "models", []) or []) if _is_alive_model(m)]
            new_count = len(alive_models)
            required_neighbors = 0 if new_count <= 1 else (2 if new_count >= 7 else 1)
            pos = self._find_reanimation_position(
                model,
                [m for m in alive_models if m is not model],
                game_map=game_map,
                required_neighbors=required_neighbors,
            )
            if pos is not None:
                try:
                    model.set_location(*pos)
                except Exception:
                    pass

            try:
                if hasattr(unit_for_model, "update_coherency"):
                    unit_for_model.update_coherency()
                if root is not unit_for_model and hasattr(root, "update_coherency"):
                    root.update_coherency()
            except Exception:
                pass

            result["returned"] += 1

        return result

    def use_ability(self, ability: Ability, target: 'Unit', game_map: 'Map'):
        """Uses a special ability."""
        from .map import Map  # Import inside the function
        assert isinstance(game_map, Map)
        if ability:
            ability.activate(self)
            print(f"{self.name} uses ability: {ability.name}.")
        else:
            print(f"{self.name} does not have ability: {ability.name}.")

    def embark(self, transport_unit: 'Unit', *, game_map: 'Map') -> None:
        """
        Embark (10th edition core rules, best-effort):
        - End a Normal/Advance/Fall Back move with all models within 3" of a friendly Transport.
        - Capacity must allow it.
        - Cannot embark and disembark in the same phase/turn (tracked by round_state flags).
        """
        if game_map is None:
            raise RuntimeError("Embark requires an active game map.")
        army = self.get_parent_army()
        if army is None or getattr(army, "player", None) is None or getattr(army.player, "game", None) is None:
            raise RuntimeError("Embark requires a unit assigned to a player with an active game.")
        game = army.player.game

        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and sr.get("fire_and_fade_no_embark_turn_owner"):
            owner = str(sr.get("fire_and_fade_no_embark_turn_owner") or "")
            turn = int(sr.get("fire_and_fade_no_embark_turn", 0) or 0)
            current_player = game.get_current_player()
            if owner and current_player is not None:
                if current_player.id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                    print(f"{self.name} cannot embark this turn (Fire and Fade)")
                    return

        if self.round_state.disembarked_this_round:
            print(f"{self.name} cannot embark after disembarking this turn")
            return

        if not transport_unit.can_transport(self):
            print(f"{self.name} cannot embark onto {transport_unit.name}.")
            return

        # Pre-battle "declare embarked units" support: during setup/deployment, units can start embarked
        # without having moved or being within 3". If neither unit is deployed yet, allow embark bookkeeping only.
        if (not self.deployed) and (not transport_unit.deployed):
            ok = transport_unit.add_passenger(self, game_map=game_map)
            if ok:
                print(f"{self.name} starts embarked within {transport_unit.name}.")
            else:
                print(f"{self.name} cannot embark onto {transport_unit.name}.")
            return

        # Must have actually moved (Normal/Advance/Fall Back) this round (not remain stationary)
        if getattr(self.round_state, "remained_stationary_this_round", False):
            print(f"{self.name} cannot embark (did not move this phase)")
            return

        # Must be within 3" with all models
        if transport_unit.models and transport_unit.models[0].is_alive:
            from ..utility.aura_utils import distance_between_models_bases_3d
            t_model = transport_unit.models[0]
            for m in self.models:
                if not m.is_alive:
                    continue
                d = distance_between_models_bases_3d(m, t_model)
                if d > 3.0 + 1e-6:
                    print(f"{self.name} cannot embark: not all models are within 3\" of {transport_unit.name}")
                    return

        ok = transport_unit.add_passenger(self, game_map=game_map)
        if ok:
            print(f"{self.name} embarks onto {transport_unit.name}.")
        else:
            print(f"{self.name} cannot embark onto {transport_unit.name}.")

    def _find_disembark_positions(
        self,
        transport_base,
        game_map: 'Map',
        max_distance: float,
        require_not_in_engagement: bool = True,
    ) -> Optional[List[Tuple[float, float, float, float]]]:
        """
        Attempt to find legal placements for all models in this unit wholly within
        `max_distance` of the transport, without collisions and (optionally) not within engagement range.
        """
        if transport_base is None:
            return None
        if not self.models:
            return []

        # Determine anchor point & radii
        tx, ty = float(getattr(transport_base, "x", 0.0)), float(getattr(transport_base, "y", 0.0))
        tz = float(getattr(transport_base, "z", 0.0))
        try:
            tr = float(transport_base.get_longest_radius())
        except Exception:
            try:
                tr = float(transport_base.get_radius())
            except Exception:
                tr = 1.0

        enemy_units = [u for u in game_map.get_enemy_units(self) if u.is_alive()]
        enemy_models = []
        for eu in enemy_units:
            for em in eu.models:
                if getattr(em, "is_alive", False):
                    enemy_models.append(em)

        placed: List[Tuple[float, float, float, float]] = []
        facing = 0.0

        for idx, model in enumerate(self.models):
            if not model.is_alive:
                continue
            try:
                mr = float(model.model_base.get_longest_radius())
            except Exception:
                try:
                    mr = float(model.model_base.get_radius())
                except Exception:
                    mr = 1.0

            # Minimum distance to avoid overlapping the transport base itself
            min_center = tr + mr + 0.05
            max_center = max_distance + tr + mr + 1e-6

            found = None
            # Spiral-ish sampling around the transport
            for ring in np.arange(0.0, max(0.01, max_center - min_center) + 0.001, 0.5):
                r = float(min_center + ring)
                if r > max_center + 1e-6:
                    break
                for deg in range(0, 360, 15):
                    ang = math.radians(deg)
                    x = tx + math.cos(ang) * r
                    y = ty + math.sin(ang) * r
                    z = tz

                    # Base-to-base "within max_distance" check
                    try:
                        candidate_base = self._create_potential_base(x, y, z, facing, model=model)
                        # Wholly within X of a unit is stronger than just edge-distance; but for our placement search
                        # we enforce a conservative necessary condition: base-to-base distance <= X.
                        # (The final placement validator for disembark handles the full constraints.)
                        # Use base-plane 3D distance (closest points on bases/hulls), not model height.
                        from ..utility.aura_utils import distance_between_bases_3d
                        edge = float(distance_between_bases_3d(candidate_base, transport_base))
                        if edge > float(max_distance) + 1e-6:
                            continue
                    except Exception:
                        pass

                    # Collision checks vs battlefield
                    try:
                        if not game_map.is_within_boundary(model, destination=(x, y)):
                            continue
                        if self._check_collision_with_obstacles_or_terrain(game_map, model, (x, y)):
                            continue
                        if game_map.check_collision_with_other_friendly_units(model, destination=(x, y)):
                            continue
                        if game_map.check_collision_with_other_enemy_units(model, destination=(x, y)):
                            continue
                    except Exception:
                        continue

                    # Collision checks within this unit
                    try:
                        if self._collides_with_unit_models(x, y, z, facing, placed, model=model):
                            continue
                        if not self._is_coherent_within_unit(x, y, z, facing, placed, model=model):
                            continue
                    except Exception:
                        # If coherency logic fails, allow placement but still avoid collisions.
                        pass

                    # Disembark requirement: not within engagement range of any enemy models
                    if require_not_in_engagement and enemy_models:
                        from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                        candidate_base = self._create_potential_base(x, y, z, facing, model=model)
                        too_close = False
                        for em in enemy_models:
                            if not getattr(em, "is_alive", False):
                                continue
                            horizontal = float(horizontal_distance_between_bases_2d(candidate_base, em.model_base))
                            vertical = float(vertical_distance_between_bases(candidate_base, em.model_base))
                            if horizontal <= 1.0 + 1e-6 and vertical <= 5.0 + 1e-6:
                                # Too close to an enemy model for disembark
                                too_close = True
                                break
                        if too_close:
                            continue

                    found = (x, y, z, facing)
                    break
                if found is not None:
                    break

            if found is None:
                return None
            placed.append(found)

        return placed

    def _find_single_disembark_position(
        self,
        *,
        model: Model,
        transport_base,
        game_map: 'Map',
        max_distance: float,
        placed: List[Tuple[float, float, float, float]],
        require_not_in_engagement: bool = True,
    ) -> Optional[Tuple[float, float, float, float]]:
        """Find a valid disembark position for one model given already-placed models."""
        if transport_base is None:
            return None
        tx, ty = float(getattr(transport_base, "x", 0.0)), float(getattr(transport_base, "y", 0.0))
        tz = float(getattr(transport_base, "z", 0.0))
        try:
            tr = float(transport_base.get_longest_radius())
        except Exception:
            try:
                tr = float(transport_base.get_radius())
            except Exception:
                tr = 1.0
        try:
            mr = float(model.model_base.get_longest_radius())
        except Exception:
            try:
                mr = float(model.model_base.get_radius())
            except Exception:
                mr = 1.0

        enemy_units = [u for u in game_map.get_enemy_units(self) if u.is_alive()]
        enemy_models = []
        for eu in enemy_units:
            for em in eu.models:
                if getattr(em, "is_alive", False):
                    enemy_models.append(em)

        facing = 0.0
        min_center = tr + mr + 0.05
        max_center = max_distance + tr + mr + 1e-6

        for ring in np.arange(0.0, max(0.01, max_center - min_center) + 0.001, 0.5):
            r = float(min_center + ring)
            if r > max_center + 1e-6:
                break
            for deg in range(0, 360, 15):
                ang = math.radians(deg)
                x = tx + math.cos(ang) * r
                y = ty + math.sin(ang) * r
                z = tz

                # Base-to-base "within max_distance" check
                from ..utility.aura_utils import distance_between_bases_3d
                candidate_base = self._create_potential_base(x, y, z, facing, model=model)
                edge = float(distance_between_bases_3d(candidate_base, transport_base))
                if edge > max_distance + 1e-6:
                    continue

                # Collision checks vs battlefield
                try:
                    if not game_map.is_within_boundary(model, destination=(x, y)):
                        continue
                    if self._check_collision_with_obstacles_or_terrain(game_map, model, (x, y)):
                        continue
                    if game_map.check_collision_with_other_friendly_units(model, destination=(x, y)):
                        continue
                    if game_map.check_collision_with_other_enemy_units(model, destination=(x, y)):
                        continue
                except Exception:
                    continue

                # Collision checks within this unit
                try:
                    if self._collides_with_unit_models(x, y, z, facing, placed, model=model):
                        continue
                    if not self._is_coherent_within_unit(x, y, z, facing, placed, model=model):
                        continue
                except Exception:
                    pass

                if require_not_in_engagement and enemy_models:
                    from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                    candidate_base = self._create_potential_base(x, y, z, facing, model=model)
                    blocked = False
                    for em in enemy_models:
                        if not getattr(em, "is_alive", False):
                            continue
                        horizontal = float(horizontal_distance_between_bases_2d(candidate_base, em.model_base))
                        vertical = float(vertical_distance_between_bases(candidate_base, em.model_base))
                        if horizontal <= 1.0 + 1e-6 and vertical <= 5.0 + 1e-6:
                            blocked = True
                            break
                    if blocked:
                        continue

                return (x, y, z, facing)

        return None

    def _apply_goretrack_onslaught_disembark_effect(self, *, game=None, current_turn: int = 0) -> None:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "world_eaters_detachments", None)
        if mgr is None or not getattr(mgr, "goretrack_onslaught_applies", None):
            return
        try:
            if not mgr.goretrack_onslaught_applies(self):
                return
        except Exception:
            return
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return
        if game is None:
            try:
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        try:
            owner = str(getattr(current_player, "id", "") or "")
        except Exception:
            owner = ""
        if not owner:
            try:
                owner = str(getattr(getattr(army, "player", None), "id", "") or "")
            except Exception:
                owner = ""
        try:
            turn = int(getattr(game, "turn", current_turn) or current_turn)
        except Exception:
            turn = int(current_turn or 0)
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for unit in members:
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["goretrack_onslaught_active"] = True
            if owner:
                sr["goretrack_onslaught_turn_owner"] = owner
            if turn:
                sr["goretrack_onslaught_turn"] = int(turn)
            unit.special_rules = sr

    def disembark(
        self,
        game_map: Optional['Map'] = None,
        transport_unit: Optional['Unit'] = None,
        *,
        destroyed_transport: bool = False,
        emergency: bool = False,
        current_turn: int = 1,
    ) -> bool:
        """
        Disembark (10th edition core rules, best-effort).

        - Normally: set up wholly within 3" of the transport and not within engagement range.
        - If the transport moved normally this phase: this unit counts as having made a Normal move,
          cannot move further this turn; charge eligibility depends on transport rules (e.g. Assault Ramp).
        - Cannot disembark after the transport Advanced or Fell Back this turn unless a rule allows it.
        - Destroyed transport: immediate disembark; mortal wounds; battle-shock; counts as Normal move; cannot charge.
        - Emergency disembarkation (only on destroyed transport when 3" setup is impossible):
          set up wholly within 6"; harsher mortals; models that cannot be set up are destroyed.
        """
        if game_map is None:
            raise RuntimeError("Disembark requires an active game map.")

        if self.round_state.embarked_this_round and not destroyed_transport:
            print(f"ERROR: {self.name} cannot disembark after embarking this turn")
            return False

        if self.round_state.disembarked_this_round:
            return False

        if transport_unit is None:
            transport_unit = self.embarked_in
        if transport_unit is None:
            print(f"ERROR: {self.name} is not embarked in a transport")
            return False

        transport_rules = transport_unit._transport_disembark_rules()
        allow_after_advance = bool(transport_rules.get("allow_after_advance", False))
        allow_charge_after_normal_move = bool(transport_rules.get("allow_charge_after_normal_move", False))
        sr = getattr(transport_unit, "special_rules", None)
        if isinstance(sr, dict) and sr.get("pain_rapid_deployment_active"):
            allow_after_advance = True

        # Transport state restrictions for normal disembark
        if not destroyed_transport:
            if getattr(transport_unit.round_state, "advanced_this_round", False):
                if not allow_after_advance:
                    print(f"ERROR: {self.name} cannot disembark: {transport_unit.name} Advanced this turn")
                    return False
            if getattr(transport_unit.round_state, "fell_back_this_round", False):
                print(f"ERROR: {self.name} cannot disembark: {transport_unit.name} Fell Back this turn")
                return False


        # Determine transport base reference (alive transport uses its current model base)
        transport_base = None
        if transport_unit.models and transport_unit.models[0].is_alive:
            transport_base = transport_unit.models[0].model_base

        if transport_base is None:
            # If transport is destroyed, caller should supply a transport_unit that has a last-known base available
            # via attribute `_last_known_base` (set by Game destroyed transport handler).
            transport_base = getattr(transport_unit, "_last_known_base", None)

        if transport_base is None:
            print(f"ERROR: {self.name} cannot disembark (missing transport position)")
            return False

        # Choose disembark radius
        disembark_distance = 6.0 if emergency else 3.0

        placements = self._find_disembark_positions(
            transport_base=transport_base,
            game_map=game_map,
            max_distance=disembark_distance,
            require_not_in_engagement=True,
        )

        if placements is None and destroyed_transport and not emergency:
            # Try emergency disembarkation
            return self.disembark(
                game_map=game_map,
                transport_unit=transport_unit,
                destroyed_transport=True,
                emergency=True,
                current_turn=current_turn,
            )

        if placements is None:
            if destroyed_transport and emergency:
                # Emergency disembarkation: models that cannot be set up are destroyed (not necessarily the whole unit).
                print(f"WARN: {self.name} emergency disembarkation: could not place all models within 6\"; destroying any unplaced models")
                alive_models = [m for m in self.models if getattr(m, "is_alive", False)]
                placed_positions: List[Tuple[float, float, float, float]] = []
                placed_models: List[Model] = []
                unplaced_models: List[Model] = []
                for m in alive_models:
                    pos = self._find_single_disembark_position(
                        model=m,
                        transport_base=transport_base,
                        game_map=game_map,
                        max_distance=6.0,
                        placed=placed_positions,
                        require_not_in_engagement=True,
                    )
                    if pos is None:
                        unplaced_models.append(m)
                        continue
                    placed_positions.append(pos)
                    placed_models.append(m)

                # Commit placements (if any)
                for m, pos in zip(placed_models, placed_positions):
                    m.set_location(*pos)

                # Destroy any unplaced models (so they don't interfere with placement validation)
                for m in unplaced_models:
                    m.wounds = 0
                    m.die(game_map=game_map)

                if placed_models:
                    if not game_map.place_unit(self):
                        # If battlefield validation fails, treat as no placements
                        placed_models = []
                        placed_positions = []

                # Remove from passengers list (even if unit ended up destroyed)
                transport_unit.remove_passenger(self)
                if not placed_models:
                    # Nothing could be set up; unit is likely destroyed or cannot disembark at all
                    return False

                # Emergency disembarkation from a destroyed transport still applies destroyed-transport effects
                self.round_state.disembarked_this_round = True
                self.round_state.disembarked_from_destroyed_transport = True
                self.round_state.disembarked_cannot_charge = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
                game = None
                army = self.get_parent_army()
                if army is not None and getattr(army, "player", None) is not None:
                    game = army.player.game
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
                sr = getattr(self, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                if pname:
                    sr["voice_of_command_disembark_phase"] = pname
                    sr["voice_of_command_disembark_round"] = int(getattr(game, "turn", current_turn) or current_turn) if game is not None else int(current_turn or 0)
                self.special_rules = sr
                self._apply_goretrack_onslaught_disembark_effect(game=game, current_turn=current_turn)

                # Battle-shock until next Command phase
                if not self.is_battle_shocked():
                    self.apply_status_effect(BattleShockEffect(current_turn))

                # Mortal wounds on 1-3
                for m in list(self.models):
                    if not getattr(m, "is_alive", False):
                        continue
                    roll = get_roll("D6")
                    if roll <= 3:
                        m.take_damage(1, is_mortal=True, game_map=game_map)

                return True
            print(f"ERROR: {self.name} cannot disembark: no valid placement found")
            return False

        # Commit placements (include attached leaders' models if any)
        placement_models = [m for m in self.get_models_for_collision() if getattr(m, "is_alive", False)]

        for model, pos in zip(placement_models, placements):
            model.set_location(*pos)
        # Add back to map (place_unit validates collisions)
        if not hasattr(game_map, "place_unit"):
            raise RuntimeError("Disembark requires a game map with place_unit().")
        if not game_map.place_unit(self):
            print(f"ERROR: {self.name} disembark failed: map placement validation failed")
            return False

        # Remove from transport passengers list
        transport_unit.remove_passenger(self)

        self.round_state.disembarked_this_round = True
        game = None
        army = self.get_parent_army()
        if army is not None and getattr(army, "player", None) is not None:
            game = army.player.game
        pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if pname:
            sr["voice_of_command_disembark_phase"] = pname
            sr["voice_of_command_disembark_round"] = int(getattr(game, "turn", current_turn) or current_turn) if game is not None else int(current_turn or 0)
        self.special_rules = sr
        self._apply_goretrack_onslaught_disembark_effect(game=game, current_turn=current_turn)

        # Apply moved/charge restrictions depending on cause
        if destroyed_transport:
            self.round_state.disembarked_from_destroyed_transport = True
            self.round_state.disembarked_cannot_charge = True
            self.round_state.moved_this_round = True
            self.round_state.remained_stationary_this_round = False
            # Battle-shock until next Command phase
            if not self.is_battle_shocked():
                self.apply_status_effect(BattleShockEffect(current_turn))
            # Mortal wounds
            # Destroyed transport: on 1 take 1 MW; Emergency: on 1-3 take 1 MW
            threshold = 3 if emergency else 1
            for m in list(self.models):
                if not getattr(m, "is_alive", False):
                    continue
                roll = get_roll("D6")
                if roll <= threshold:
                    m.take_damage(1, is_mortal=True, game_map=game_map)
        else:
            moved_this_round = bool(getattr(transport_unit.round_state, "moved_this_round", False))
            remained_stationary = bool(getattr(transport_unit.round_state, "remained_stationary_this_round", False))
            advanced = bool(getattr(transport_unit.round_state, "advanced_this_round", False))
            fell_back = bool(getattr(transport_unit.round_state, "fell_back_this_round", False))

            if advanced and allow_after_advance:
                # Assault Vehicle: counts as Normal move, cannot charge this turn.
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.disembarked_cannot_charge = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
            elif moved_this_round and not remained_stationary and not advanced and not fell_back:
                # Normal moved transport disembark: counts as Normal move, no further move; charge depends on Assault Ramp.
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
                if not allow_charge_after_normal_move:
                    self.round_state.disembarked_cannot_charge = True


        return True

    def validate_disembark_placement(
        self,
        model: 'Model',
        x: float,
        y: float,
        z: float,
        *,
        transport_unit: Optional['Unit'] = None,
        game_map: Optional['Map'] = None,
        max_distance: float = 3.0,
        require_not_in_engagement: bool = True,
    ) -> dict:
        """Validate manual disembark placement for a single model."""
        if game_map is None:
            return {"valid": False, "reason": "No map context"}
        if transport_unit is None:
            transport_unit = self.embarked_in
        if transport_unit is None:
            return {"valid": False, "reason": "No transport"}

        transport_base = None
        try:
            if transport_unit.models and transport_unit.models[0].is_alive:
                transport_base = transport_unit.models[0].model_base
        except Exception:
            transport_base = None
        if transport_base is None:
            transport_base = getattr(transport_unit, "_last_known_base", None)
        if transport_base is None:
            return {"valid": False, "reason": "Missing transport position"}

        try:
            facing = float(getattr(getattr(model, "model_base", None), "facing", 0.0) or 0.0)
        except Exception:
            facing = 0.0
        try:
            candidate_base = self._create_potential_base(float(x), float(y), float(z), facing, model=model)
        except Exception:
            return {"valid": False, "reason": "Invalid base"}

        try:
            from ..utility.aura_utils import distance_between_bases_3d
            edge = float(distance_between_bases_3d(candidate_base, transport_base))
            if edge > float(max_distance) + 1e-6:
                return {"valid": False, "reason": "Too far from transport"}
        except Exception:
            return {"valid": False, "reason": "Range check failed"}

        try:
            if not game_map.is_within_boundary(model, destination=(float(x), float(y))):
                return {"valid": False, "reason": "Outside battlefield"}
        except Exception:
            pass
        try:
            if self._check_collision_with_obstacles_or_terrain(game_map, model, (float(x), float(y))):
                return {"valid": False, "reason": "Blocked by terrain"}
        except Exception:
            pass
        try:
            if game_map.check_collision_with_other_friendly_units(model, destination=(float(x), float(y))):
                return {"valid": False, "reason": "Collides with friendly unit"}
        except Exception:
            pass
        try:
            if game_map.check_collision_with_other_enemy_units(model, destination=(float(x), float(y))):
                return {"valid": False, "reason": "Collides with enemy unit"}
        except Exception:
            pass

        if require_not_in_engagement:
            try:
                from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                for enemy in list(game_map.get_enemy_units(self) or []):
                    try:
                        if not getattr(enemy, "deployed", True):
                            continue
                        if hasattr(enemy, "is_alive") and not enemy.is_alive():
                            continue
                    except Exception:
                        continue
                    try:
                        models = list(enemy.get_models_for_collision() or [])
                    except Exception:
                        models = list(getattr(enemy, "models", []) or [])
                    for em in models:
                        if not getattr(em, "is_alive", True):
                            continue
                        horizontal = float(horizontal_distance_between_bases_2d(candidate_base, em.model_base))
                        vertical = float(vertical_distance_between_bases(candidate_base, em.model_base))
                        if horizontal <= 1.0 + 1e-6 and vertical <= 5.0 + 1e-6:
                            return {"valid": False, "reason": "Within Engagement Range"}
            except Exception:
                pass

        return {"valid": True, "reason": "OK"}

    def finalize_manual_disembark(
        self,
        game_map: Optional['Map'] = None,
        transport_unit: Optional['Unit'] = None,
        *,
        destroyed_transport: bool = False,
        emergency: bool = False,
        current_turn: int = 1,
    ) -> bool:
        """Finalize disembark bookkeeping after manual placement."""
        if game_map is None:
            raise RuntimeError("Finalize disembark requires an active game map.")

        if self.round_state.embarked_this_round and not destroyed_transport:
            print(f"ERROR: {self.name} cannot disembark after embarking this turn")
            return False

        if self.round_state.disembarked_this_round:
            return False

        if transport_unit is None:
            transport_unit = self.embarked_in
        if transport_unit is None:
            print(f"ERROR: {self.name} is not embarked in a transport")
            return False

        transport_rules = transport_unit._transport_disembark_rules()
        allow_after_advance = bool(transport_rules.get("allow_after_advance", False))
        allow_charge_after_normal_move = bool(transport_rules.get("allow_charge_after_normal_move", False))
        sr = getattr(transport_unit, "special_rules", None)
        if isinstance(sr, dict) and sr.get("pain_rapid_deployment_active"):
            allow_after_advance = True

        if not destroyed_transport:
            if getattr(transport_unit.round_state, "advanced_this_round", False):
                if not allow_after_advance:
                    print(f"ERROR: {self.name} cannot disembark: {transport_unit.name} Advanced this turn")
                    return False
            if getattr(transport_unit.round_state, "fell_back_this_round", False):
                print(f"ERROR: {self.name} cannot disembark: {transport_unit.name} Fell Back this turn")
                return False

        if self in game_map.units:
            game_map.units.remove(self)

        if not hasattr(game_map, "place_unit"):
            raise RuntimeError("Finalize disembark requires a game map with place_unit().")
        if not game_map.place_unit(self):
            print(f"ERROR: {self.name} disembark failed: map placement validation failed")
            return False

        transport_unit.remove_passenger(self)

        self.round_state.disembarked_this_round = True
        game = None
        army = self.get_parent_army()
        if army is not None and getattr(army, "player", None) is not None:
            game = army.player.game
        pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if pname:
            sr["voice_of_command_disembark_phase"] = pname
            sr["voice_of_command_disembark_round"] = int(getattr(game, "turn", current_turn) or current_turn) if game is not None else int(current_turn or 0)
        self.special_rules = sr
        self._apply_goretrack_onslaught_disembark_effect(game=game, current_turn=current_turn)

        if destroyed_transport:
            self.round_state.disembarked_from_destroyed_transport = True
            self.round_state.disembarked_cannot_charge = True
            self.round_state.moved_this_round = True
            self.round_state.remained_stationary_this_round = False
            if not self.is_battle_shocked():
                self.apply_status_effect(BattleShockEffect(current_turn))
            threshold = 3 if emergency else 1
            for m in list(self.models):
                if not getattr(m, "is_alive", False):
                    continue
                roll = get_roll("D6")
                if roll <= threshold:
                    m.take_damage(1, is_mortal=True, game_map=game_map)
        else:
            moved_this_round = bool(getattr(transport_unit.round_state, "moved_this_round", False))
            remained_stationary = bool(getattr(transport_unit.round_state, "remained_stationary_this_round", False))
            advanced = bool(getattr(transport_unit.round_state, "advanced_this_round", False))
            fell_back = bool(getattr(transport_unit.round_state, "fell_back_this_round", False))

            if advanced and allow_after_advance:
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.disembarked_cannot_charge = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
            elif moved_this_round and not remained_stationary and not advanced and not fell_back:
                self.round_state.disembarked_from_moved_transport = True
                self.round_state.moved_this_round = True
                self.round_state.remained_stationary_this_round = False
                if not allow_charge_after_normal_move:
                    self.round_state.disembarked_cannot_charge = True

        return True

    def take_damage(self, amount: int):
        pass
    
    def apply_status_effect(self, status_effect: StatusEffect) -> None:
        status_effect.apply_effect(self)
        effects = getattr(self, "status_effects", None)
        if not isinstance(effects, list):
            self.status_effects = []
        self.status_effects.append(status_effect)
    
    def remove_status_effect(self, status_effect: StatusEffect) -> None:
        status_effect.remove_effect(self)
        effects = getattr(self, "status_effects", None)
        if not isinstance(effects, list):
            self.status_effects = []
        if status_effect in self.status_effects:
            self.status_effects.remove(status_effect)

    ###########################################################################
    ### Position and Coherency
    ###########################################################################
    def is_alive(self) -> bool:
        # Attached unit is alive if either bodyguards or attached leaders have alive models.
        if len(self.models) > 0:
            return True
        try:
            for l in list(getattr(self, "attached_leaders", []) or []):
                if len(getattr(l, "models", []) or []) > 0:
                    return True
        except Exception:
            pass
        return False

    def is_active_for_rules(self) -> bool:
        """True if the unit is alive and on the battlefield for rules purposes."""
        if not self.is_alive():
            return False
        if not bool(getattr(self, "deployed", False)):
            return False
        if str(getattr(self, "reserve_status", "deployed") or "deployed") != "deployed":
            return False
        try:
            if self.is_embarked:
                return False
        except Exception:
            if getattr(self, "embarked_in", None):
                return False
        return True

    def resolve_pending_leader_separation(self, game_map: Optional['Map'] = None) -> None:
        """If this bodyguard has pending separation, detach leaders into solo units now."""
        if not bool(getattr(self, "_pending_leader_separation", False)):
            return
        try:
            attached = list(getattr(self, "attached_leaders", []) or [])
        except Exception:
            attached = []
        if not attached:
            self._pending_leader_separation = False
            return

        for leader in attached:
            try:
                leader.detach_from_unit()
                leader.deployed = True
                leader.set_reserve_status("deployed")
                leader.reserve_turn_deployed = getattr(self, "reserve_turn_deployed", None)
                if game_map is not None and hasattr(game_map, "units"):
                    if leader not in game_map.units:
                        game_map.units.append(leader)
            except Exception:
                continue

        # Remove the bodyguard unit from the map if it has no models left.
        try:
            if game_map is not None and hasattr(game_map, "units") and self in game_map.units and len(self.models) == 0:
                game_map.units.remove(self)
        except Exception:
            pass

        self._pending_leader_separation = False

    def _attack_resolution_root(self) -> 'Unit':
        """Resolve attack-window bookkeeping to the attached-unit root (bodyguard)."""
        try:
            return self.get_attached_unit_root()
        except Exception:
            return self

    def begin_attack_resolution(self) -> None:
        """Mark that an attacking unit has started resolving attacks against this unit."""
        root = self._attack_resolution_root()
        try:
            depth = int(getattr(root, "_attack_resolution_depth", 0))
        except Exception:
            depth = 0
        root._attack_resolution_depth = depth + 1

    def end_attack_resolution(self, game_map: Optional['Map'] = None) -> None:
        """Mark that an attacking unit finished resolving attacks; resolve pending separation if safe."""
        root = self._attack_resolution_root()
        try:
            depth = int(getattr(root, "_attack_resolution_depth", 0))
        except Exception:
            depth = 0
        depth = max(0, depth - 1)
        root._attack_resolution_depth = depth
        if depth == 0:
            try:
                root.resolve_pending_leader_separation(game_map=game_map)
            except Exception:
                pass

            # WORLD EATERS: Resolve any deferred Total Carnage fights now that the attacker finished its attacks.
            try:
                army = root.get_parent_army()
                mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
                game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
                br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                if mgr is not None and br > 0 and mgr.is_blessing_active_for_unit("TOTAL_CARNAGE", root, battle_round=br):
                    # Only if this attached unit group actually qualifies for Blessings
                    if root.attached_unit_has_blessings_of_khorne():
                        mgr.resolve_total_carnage_queue(owning_unit=root, game_map=game_map)
            except Exception:
                pass

    def attached_unit_has_blessings_of_khorne(self) -> bool:
        """Attached unit eligibility: true if any attached member (bodyguard or leader) has Blessings of Khorne ability."""
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "blood_tithe_might_of_khorne_applies", None):
                if mgr.blood_tithe_might_of_khorne_applies(self):
                    return True
            if mgr is not None and getattr(mgr, "unit_is_blood_legions", None):
                if mgr.unit_is_blood_legions(self) and self._unit_within_icon_of_war_range():
                    return True
        except Exception:
            pass
        for u in self.get_attached_unit_members():
            try:
                found, _ = u._find_ability_with_patterns(["blessings of khorne"])
            except Exception:
                found = False
            if found:
                return True
        return False

    def has_icon_of_khorne(self) -> bool:
        """True if this unit has the Icon of Khorne ability."""
        if "icon_of_khorne" in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache["icon_of_khorne"])
        found, _ = self._find_ability_with_patterns(["icon of khorne"])
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache["icon_of_khorne"] = bool(found)
        return bool(found)

    def has_icon_of_war(self) -> bool:
        """True if this unit has the Icon of War enhancement."""
        cache_key = "icon_of_war"
        if cache_key in getattr(self, "_ability_cache", {}):
            if bool(self._ability_cache[cache_key]):
                return True
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_icon_of_war"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "icon of war" or enh_id == "000010078002":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def has_disciple_of_khorne(self) -> bool:
        """True if this unit has the Disciple of Khorne enhancement."""
        cache_key = "disciple_of_khorne"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])
        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_disciple_of_khorne"):
                found = True
        except Exception:
            found = False
        if not found:
            try:
                enh = getattr(self, "enhancement", None)
                name = str(getattr(enh, "name", "") or "").strip().lower()
                enh_id = str(getattr(enh, "id", "") or "").strip()
                if name == "disciple of khorne" or enh_id == "000010078004":
                    found = True
            except Exception:
                found = False
        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def _is_lord_on_juggernaut(self) -> bool:
        try:
            dsid = str(getattr(getattr(self, "_datasheet", None), "id", "") or "").strip()
        except Exception:
            dsid = ""
        if dsid == "000002625":
            return True
        try:
            name = self._normalize_attached_unit_name(getattr(self, "name", ""))
        except Exception:
            name = ""
        return name == "lord on juggernaut"

    def _disciple_of_khorne_bodyguard_allowed(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        try:
            dsid = str(getattr(getattr(bodyguard, "_datasheet", None), "id", "") or "").strip()
        except Exception:
            dsid = ""
        if dsid in {"000004107", "000004108"}:
            return True
        try:
            name = self._normalize_attached_unit_name(getattr(bodyguard, "name", ""))
        except Exception:
            name = ""
        return name in {"bloodcrushers", "flesh hounds"}

    def _disciple_of_khorne_is_bearer(self) -> bool:
        if not self.has_disciple_of_khorne():
            return False
        if not self.is_leader:
            return False
        if not self._is_lord_on_juggernaut():
            return False
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if mgr is None:
            return False
        try:
            if not mgr.is_khorne_daemonkin():
                return False
        except Exception:
            return False
        return True

    def _disciple_of_khorne_active(self, bodyguard=None) -> bool:
        if not self._disciple_of_khorne_is_bearer():
            return False
        if bodyguard is None:
            bodyguard = getattr(self, "attached_to", None)
        if bodyguard is None:
            return False
        return self._disciple_of_khorne_bodyguard_allowed(bodyguard)

    def _disciple_of_khorne_can_attach_to(self, bodyguard) -> bool:
        if bodyguard is None:
            return False
        if not self._disciple_of_khorne_is_bearer():
            return False
        return self._disciple_of_khorne_bodyguard_allowed(bodyguard)

    def _disciple_of_khorne_active_leaders(self) -> list["Unit"]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        leaders = list(getattr(root, "attached_leaders", []) or [])
        active: list["Unit"] = []
        for leader in leaders:
            try:
                if leader._disciple_of_khorne_active(bodyguard=root):
                    active.append(leader)
            except Exception:
                continue
        return active

    def _unit_on_battlefield_for_icon_of_war(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if not bool(getattr(unit, "deployed", True)):
                return False
            if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
                return False
        except Exception:
            return False
        try:
            if bool(getattr(unit, "embarked_in", None)) or bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            pass
        return True

    def _models_within_icon_of_war_range(self, source_unit, target_unit, *, radius: float) -> bool:
        try:
            from ..utility.aura_utils import distance_between_models_bases_3d
        except Exception:
            return False
        try:
            src_models = list(getattr(source_unit, "models", []) or [])
        except Exception:
            src_models = []
        try:
            tgt_models = list(target_unit.get_attached_unit_models() or [])
        except Exception:
            tgt_models = list(getattr(target_unit, "models", []) or [])
        if not src_models or not tgt_models:
            return False
        for sm in src_models:
            try:
                if not getattr(sm, "is_alive", True):
                    continue
            except Exception:
                continue
            for tm in tgt_models:
                try:
                    if not getattr(tm, "is_alive", True):
                        continue
                except Exception:
                    continue
                try:
                    if distance_between_models_bases_3d(sm, tm) <= float(radius) + 1e-6:
                        return True
                except Exception:
                    continue
        return False

    def _unit_within_icon_of_war_range(self, *, radius: float = 6.0) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if not self._unit_on_battlefield_for_icon_of_war(root):
            return False
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return False
        try:
            units = list(getattr(army, "units", []) or [])
        except Exception:
            units = []
        for source in units:
            try:
                if not source.has_icon_of_war():
                    continue
            except Exception:
                continue
            if not self._unit_on_battlefield_for_icon_of_war(source):
                continue
            if self._models_within_icon_of_war_range(source, root, radius=radius):
                return True
        return False

    def _icon_of_war_battle_shock_reroll_available(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if mgr is None:
            return False
        try:
            if not mgr.is_khorne_daemonkin():
                return False
        except Exception:
            return False
        try:
            if not mgr.is_blood_tithe_active("MIGHT_OF_KHORNE"):
                return False
        except Exception:
            return False
        try:
            if not mgr.unit_is_blood_legions(root):
                return False
        except Exception:
            return False
        return bool(root._unit_within_icon_of_war_range())

    def has_command_phase_sticky_objective(self) -> bool:
        """
        True if this unit has the datasheet ability that makes objectives sticky at end of your Command phase.
        """
        cache_key = "command_phase_sticky_objective"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])

        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("sticky_objectives"):
                found = True
            else:
                found = self._scan_command_phase_sticky_objective()
                if isinstance(sr, dict):
                    if found:
                        sr["sticky_objectives"] = True
                    elif "sticky_objectives" in sr:
                        del sr["sticky_objectives"]
        except Exception:
            found = self._scan_command_phase_sticky_objective()

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def get_command_phase_bodyguard_return_ability(self):
        """
        Return ability info dict for command-phase bodyguard model returns, or None if not available.
        """
        cache_key = "command_phase_bodyguard_return_ability"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        ability = None
        try:
            if not bool(getattr(self, "is_attached_leader", False)):
                ability = None
            else:
                ability = self._scan_command_phase_bodyguard_return_ability()
        except Exception:
            ability = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = ability
        return ability

    def get_charge_phase_bodyguard_loss_ability(self):
        """
        Return ability info dict for end-of-Charge-phase Leadership test bodyguard losses, or None.
        """
        cache_key = "charge_phase_bodyguard_loss_ability"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        ability = None
        try:
            if not bool(getattr(self, "is_attached_leader", False)):
                ability = None
            else:
                ability = self._scan_charge_phase_bodyguard_loss_ability()
        except Exception:
            ability = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = ability
        return ability

    def get_end_of_opponent_turn_strategic_reserves_ability(self):
        """
        Return ability info dict for end-of-opponent-turn Strategic Reserves removal, or None if not available.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "opponent_turn_strategic_reserves_ability"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        ability = None
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in members:
            try:
                ability = member._scan_end_of_opponent_turn_strategic_reserves_ability()
            except Exception:
                ability = None
            if ability:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = ability
        return ability

    def get_transport_reactive_disembark_ability(self):
        """
        Return ability info dict for reactive transport disembark triggers, or None if not available.
        """
        cache_key = "transport_reactive_disembark_ability"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        ability = None
        try:
            if not bool(getattr(self, "is_transport", False)):
                ability = None
            else:
                ability = self._scan_transport_reactive_disembark_ability()
        except Exception:
            ability = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = ability
        return ability

    def attached_unit_has_icon_of_khorne(self) -> bool:
        """Attached unit eligibility: true if any attached member has Icon of Khorne."""
        for u in self.get_attached_unit_members():
            try:
                if u.has_icon_of_khorne():
                    return True
            except Exception:
                continue
        return False

    def attached_unit_has_command_phase_sticky_objective(self) -> bool:
        """Attached unit eligibility: true if any attached member has sticky objective ability."""
        for u in self.get_attached_unit_members():
            try:
                sr = getattr(u, "special_rules", None)
                if isinstance(sr, dict) and sr.get("sticky_objectives"):
                    return True
                if u.has_command_phase_sticky_objective():
                    return True
            except Exception:
                continue
        return False

    def attached_unit_has_kill_team(self) -> bool:
        """Attached unit eligibility: true if any attached member has the Kill Team ability."""
        for u in self.get_attached_unit_members():
            try:
                if u.has_kill_team():
                    return True
            except Exception:
                continue
        return False

    def attached_unit_has_martial_katah(self) -> bool:
        """Attached unit eligibility: true if any attached member has Martial Ka'tah."""
        for u in self.get_attached_unit_members():
            try:
                if u.has_martial_katah():
                    return True
            except Exception:
                continue
        return False

    def leading_unit_weapons_have_lethal_hits(self, attack_type: Optional[str] = None) -> bool:
        """
        Leading-only ability: while a leader is attached, weapons in that unit gain [LETHAL HITS].

        attack_type: "melee", "ranged", or None to check any weapon type.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        def _resolve(flags: dict, attack_kind: Optional[str]) -> bool:
            kind = str(attack_kind or "").strip().lower()
            if kind == "melee":
                return bool(flags.get("any")) or bool(flags.get("melee"))
            if kind == "ranged":
                return bool(flags.get("any")) or bool(flags.get("ranged"))
            return bool(flags.get("any")) or bool(flags.get("melee")) or bool(flags.get("ranged"))

        cache_key = "leading_unit_lethal_hits"
        cache = getattr(root, "_ability_cache", {})
        if cache_key in cache:
            cached = cache.get(cache_key)
            if isinstance(cached, dict):
                return _resolve(cached, attack_type)
            return bool(cached)

        flags = {"any": False, "melee": False, "ranged": False}
        lethal_any_re = re.compile(
            r"weapons equipped by models in that unit have the \[?lethal hits\]? ability",
            re.IGNORECASE,
        )
        lethal_melee_re = re.compile(
            r"melee weapons equipped by models in that unit have the \[?lethal hits\]? ability",
            re.IGNORECASE,
        )
        lethal_ranged_re = re.compile(
            r"ranged weapons equipped by models in that unit have the \[?lethal hits\]? ability",
            re.IGNORECASE,
        )
        for ab, _leader in root._iter_attached_leader_leading_abilities():
            try:
                desc = ab if isinstance(ab, str) else (getattr(ab, "description", "") or getattr(ab, "name", ""))
            except Exception:
                desc = ""
            text = self._normalize_rules_text(desc or "")
            if not text:
                continue
            text = text.replace("\u2019", "'").replace("\u0192?T", "'")
            try:
                rest = self._LEADING_ABILITY_PREFIX_RE.sub("", text, count=1).strip(" ,:;-")
            except Exception:
                rest = text
            if lethal_melee_re.search(rest):
                flags["melee"] = True
            elif lethal_ranged_re.search(rest):
                flags["ranged"] = True
            elif lethal_any_re.search(rest):
                flags["any"] = True
            if flags["any"]:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = flags
        return _resolve(flags, attack_type)

    def set_martial_katah_choice(self, choice: str) -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["martial_katah_choice"] = str(choice or "").strip().upper()
        root.special_rules = sr

    def clear_martial_katah_choice(self) -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        sr.pop("martial_katah_choice", None)
        root.special_rules = sr

    def set_exquisite_swordsmanship_choice(self, choice: str) -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["exquisite_swordsmanship_choice"] = str(choice or "").strip().upper()
        sr["exquisite_swordsmanship_expires_phase"] = "FIGHT_PHASE"
        root.special_rules = sr

    def clear_exquisite_swordsmanship_choice(self) -> None:
        root = self.get_attached_unit_root()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for k in ("exquisite_swordsmanship_choice", "exquisite_swordsmanship_expires_phase"):
            sr.pop(k, None)
        root.special_rules = sr

    def attached_unit_has_reanimation_protocols(self) -> bool:
        """Attached unit eligibility: true if any attached member has Reanimation Protocols."""
        for u in self.get_attached_unit_members():
            try:
                if u.has_reanimation_protocols():
                    return True
            except Exception:
                continue
        return False

    def get_fight_phase_move_distance_override(self, movement_kind: str) -> Optional[float]:
        """
        Return a fight-phase move distance override (pile-in / consolidate) if a rule modifies it.
        movement_kind: 'pile_in' or 'consolidate'
        """
        kind = str(movement_kind).strip().lower()
        if kind not in ("pile_in", "consolidate"):
            return None

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        override = None

        try:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict):
                exp = str(sr.get("battle_focus_sudden_strike_expires_phase", "") or "").strip().upper()
                if exp:
                    pname = ""
                    try:
                        army = root.get_parent_army()
                        game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
                        phase = getattr(game, "phase", None) if game is not None else None
                        pname = str(getattr(phase, "name", "") or phase or "").strip().upper()
                    except Exception:
                        pname = ""
                    if not pname or pname == exp:
                        override = max(float(override or 0.0), 6.0)
        except Exception:
            pass

        try:
            army = root.get_parent_army()
            mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
            game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
            br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            if mgr is not None and br > 0:
                if root.attached_unit_has_blessings_of_khorne():
                    if mgr.is_blessing_active_for_unit("RAGE_FUELLED_INVIGORATION", root, battle_round=br):
                        override = max(float(override or 0.0), 6.0)
        except Exception:
            pass

        if kind == "consolidate":
            try:
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict):
                    dist = sr.get("stratagem_consolidate_distance_override")
                    if dist is not None:
                        override = max(float(override or 0.0), float(dist))
            except Exception:
                pass

        return float(override) if override else None

    def maybe_resolve_pending_separation(self, game_map: Optional['Map'] = None) -> None:
        """Resolve pending separation only if no attack resolution window is active."""
        root = self._attack_resolution_root()
        try:
            depth = int(getattr(root, "_attack_resolution_depth", 0))
        except Exception:
            depth = 0
        if depth == 0:
            try:
                root.resolve_pending_leader_separation(game_map=game_map)
            except Exception:
                pass



    def get_closest_model_position_to_target(self, target_position: Tuple[float, float, float]) -> Optional[Tuple[float, float, float]]:
        """Get the position of the model closest to a target position.

        Args:
            target_position: (x, y, z) coordinates of the target

        Returns:
            Tuple[float, float, float]: Position of closest model or None if no alive models
        """
        closest_model = None
        closest_distance = float('inf')

        for model in self.models:
            if not model.is_alive:
                continue
            model_pos = model.get_location()
            if model_pos:
                distance = get_dist(
                    target_position[0] - model_pos[0],
                    target_position[1] - model_pos[1],
                    target_position[2] - model_pos[2] if len(model_pos) > 2 else 0
                )
                if distance < closest_distance:
                    closest_distance = distance
                    closest_model = model

        return closest_model.get_location() if closest_model else None

    def is_point_inside(self, x, y):
        # Check if point is within any model's base
        for model in self.models:
            if not model.is_alive:
                continue
            model_pos = model.get_location()
            if model_pos:
                # Check if point is within model's base radius
                model_radius = getattr(model.model_base, 'radius', 1.0)
                if isinstance(model_radius, (tuple, list)):
                    model_radius = max(model_radius)  # Use larger radius for elliptical bases
                distance = get_dist(x - model_pos[0], y - model_pos[1])
                if distance <= model_radius:
                    return True
        return False

    def score_position(self, x, y, z, facing, game_map, model, placed_positions):
        """
        Score a candidate position for model placement.
        Lower is better. 
        You can enhance this to factor in more things: cover, distance to objective, edge, enemy, etc.
        """
        # Simple version: maximize coherency, avoid edge, avoid obstacles.
        battlefield_width, battlefield_height = game_map.width, game_map.height

        # Distance from board edge (prefer center)
        min_x_dist = min(x, battlefield_width - x)
        min_y_dist = min(y, battlefield_height - y)
        edge_penalty = max(0, 6.0 - min(min_x_dist, min_y_dist)) * 10  # penalize <6" from edge

        # Penalty if near obstacle/impassable (cover not scored in this heuristic).
        cover_bonus = 0

        # Coherency bonus (number of coherent neighbors)
        coherent_neighbors = 0
        for pos in placed_positions:
            other_x, other_y, other_z, other_facing = pos
            # Assume unit has .coherency_distance
            dist = get_dist(x - other_x, y - other_y, z - other_z)
            if dist <= self.coherency_distance:
                coherent_neighbors += 1
        # Encourage more neighbors
        coherency_bonus = -coherent_neighbors * 20

        return edge_penalty + cover_bonus + coherency_bonus

    def _get_reduced_boundary_repulsors(self, game_map: 'Map') -> List:
        """Get reduced boundary repulsors for formation finding during movement.
        
        These are smaller than the full battlefield edge repulsors to allow better
        formation finding in crowded areas while still preventing units from going
        off the battlefield.
        """
        from shapely.geometry import Polygon
        
        repulsors = []
        repulsor_thickness = 0.25  # Reduced from 0.5 to 0.25 inches
        
        # Left battlefield edge repulsor (reduced)
        left_edge = Polygon([
            (-repulsor_thickness, -repulsor_thickness),
            (0, -repulsor_thickness),
            (0, game_map.height + repulsor_thickness),
            (-repulsor_thickness, game_map.height + repulsor_thickness)
        ])
        repulsors.append(left_edge)
        
        # Right battlefield edge repulsor (reduced)
        right_edge = Polygon([
            (game_map.width, -repulsor_thickness),
            (game_map.width + repulsor_thickness, -repulsor_thickness),
            (game_map.width + repulsor_thickness, game_map.height + repulsor_thickness),
            (game_map.width, game_map.height + repulsor_thickness)
        ])
        repulsors.append(right_edge)
        
        # Bottom battlefield edge repulsor (reduced)
        bottom_edge = Polygon([
            (-repulsor_thickness, -repulsor_thickness),
            (game_map.width + repulsor_thickness, -repulsor_thickness),
            (game_map.width + repulsor_thickness, 0),
            (-repulsor_thickness, 0)
        ])
        repulsors.append(bottom_edge)
        
        # Top battlefield edge repulsor (reduced)
        top_edge = Polygon([
            (-repulsor_thickness, game_map.height),
            (game_map.width + repulsor_thickness, game_map.height),
            (game_map.width + repulsor_thickness, game_map.height + repulsor_thickness),
            (-repulsor_thickness, game_map.height + repulsor_thickness)
        ])
        repulsors.append(top_edge)

        print(f"DEBUG: _get_reduced_boundary_repulsors returning {len(repulsors)} repulsors for map size {game_map.width}x{game_map.height}")

        return repulsors

    def calculate_strategic_facing(self, x: float, y: float, game_map: 'Map') -> float:
        """Calculate strategic facing direction towards enemies or objectives"""
        
        # Get our army to determine enemies
        army = self.get_parent_army()
        if not army:
            return 0.0  # Default facing if no army context
        
        best_target = None
        min_distance = float('inf')
        
        # Priority 1: Face nearest visible enemy unit
        for unit in game_map.units:
            if unit != self and unit.get_parent_army() != army and unit.is_alive():
                # Find the closest model in the enemy unit to our position
                closest_enemy_distance = float('inf')
                closest_enemy_pos = None

                for model in unit.models:
                    if model.is_alive:
                        enemy_pos = model.get_location()
                        distance = get_dist(x - enemy_pos[0], y - enemy_pos[1])
                        if distance < closest_enemy_distance:
                            closest_enemy_distance = distance
                            closest_enemy_pos = enemy_pos

                if closest_enemy_pos and closest_enemy_distance < min_distance:
                    min_distance = closest_enemy_distance
                    best_target = closest_enemy_pos
        
        # Priority 2: If no enemies, face towards objectives
        if not best_target and hasattr(game_map, 'objectives'):
            for objective in game_map.objectives:
                obj_pos = (objective.location.x, objective.location.y)
                distance = get_dist(x - obj_pos[0], y - obj_pos[1])
                if distance < min_distance:
                    min_distance = distance
                    best_target = obj_pos
        
        # Priority 3: Face towards center of battlefield
        if not best_target:
            center_x = game_map.width / 2
            center_y = game_map.height / 2
            best_target = (center_x, center_y)
        
        # Calculate angle to target
        dx = best_target[0] - x
        dy = best_target[1] - y
        return get_angle(dy, dx)

    def calculate_model_positions(self,
                                start_x: float,
                                start_y: float,
                                game_map: 'Map',
                                grid_step=0.5,
                                relax_iters=5,
                                avoid_friendly_units=True,
                                boundary_repulsors=None):
        """
        Computes (x, y, z, facing) for each model in self.models.
        Tries formation templates (block, wedge, circle, column) built 
        with safe spacing based on base size; falls back to per-model A*.
        
        Args:
            start_x: Target X coordinate for unit placement
            start_y: Target Y coordinate for unit placement
            game_map: The game map
            grid_step: Step size for pathfinding grid (default 0.5)
            relax_iters: Number of relaxation iterations (default 5)
            avoid_friendly_units: Whether to avoid collisions with friendly units
            boundary_repulsors: Optional list of boundary repulsor polygons to avoid
            
        Returns:
            List of (x, y, z, facing) tuples for each model, or None if failed
        """
        if not self.models:
            return []

        if boundary_repulsors is None:
            boundary_repulsors = []

        # Single model - use fast path
        if len(self.models) == 1:
            z = game_map.get_height_at_point(start_x, start_y)
            self.models[0].set_location(start_x, start_y, z, 0.0)
            return [(start_x, start_y, z, 0.0)]

        print(f"DEBUG: calculate_model_positions for {self.name} ({len(self.models)} models)")
        print(f"DEBUG: start position: ({start_x:.1f}, {start_y:.1f})")
        print(f"DEBUG: avoid_friendly_units: {avoid_friendly_units}")
        print(f"DEBUG: boundary_repulsors: {len(boundary_repulsors) if boundary_repulsors else 0}")

        # Debug boundary repulsors
        if len(boundary_repulsors) == 0:
            print(f"DEBUG: No boundary repulsors provided - this might cause formation finding issues")
        else:
            print(f"DEBUG: Boundary repulsors provided: {[type(br).__name__ for br in boundary_repulsors]}")

        # FAST PATH FOR SINGLE-MODEL UNITS (avoid terrain & enemy models)
        if len(self.models) == 1:
            print(f"DEBUG: Using single-model fast path")
            # initial drop
            z = game_map.get_height_at_point(start_x, start_y)
            f = self.calculate_strategic_facing(start_x, start_y, game_map)
            pos = [start_x, start_y, z, f]
            m = self.models[0]

            # Build list of blocking models (enemies + optionally friendlies)
            blocking_models = game_map.get_enemy_models(self)
            if avoid_friendly_units:
                # Add friendly models from other units (excluding self)
                friendly_models = []
                for unit in game_map.get_friendly_units(self):
                    if unit != self:  # Don't include models from the unit being positioned
                        friendly_models.extend(unit.models)
                blocking_models.extend(friendly_models)
            
            # Use provided boundary repulsors or default to empty list
            if boundary_repulsors is None:
                boundary_repulsors = []
            
            # one-off spatial index of terrain + blocking models + boundary repulsors
            # Convert terrain features to blocking polygons for this unit
            from ..utility.calcs import get_terrain_blocking_polygons
            terrain_polygons = []
            for terrain_feature in game_map.terrain_features:
                blocking_polygons = get_terrain_blocking_polygons(self, terrain_feature)
                terrain_polygons.extend(blocking_polygons)

            tree = build_spatial_index(terrain_polygons + boundary_repulsors, blocking_models)

            # relax away from any collisions
            for _ in range(relax_iters):
                # build the model's polygon at its trial spot
                base = m.model_base.get_base_shape()
                poly = translate(base,
                                pos[0] - base.centroid.x,
                                pos[1] - base.centroid.y)

                # check for collisions with terrain/enemy/friendly/boundary blockers
                hits = query_spatial_index(tree, poly)
                # if no intersection, we're done
                # DEBUG: Add defensive programming to catch geometry type errors
                try:
                    if not any(poly.intersects(b) for b in hits):
                        break
                except TypeError as e:
                    print(f"DEBUG: TypeError in single-model intersects check: {e}")
                    print(f"DEBUG: poly type: {type(poly)}")
                    print(f"DEBUG: hits count: {len(hits)}")
                    for i, hit in enumerate(hits):
                        print(f"DEBUG: hit {i}: {type(hit)} - {hit}")
                        if hasattr(hit, 'geom_type'):
                            print(f"DEBUG:   geom_type: {hit.geom_type}")
                        if hasattr(hit, 'is_valid'):
                            print(f"DEBUG:   is_valid: {hit.is_valid}")
                    raise

                # repel vector from first blocker
                b = next(b for b in hits if poly.intersects(b))
                vx = poly.centroid.x - b.centroid.x
                vy = poly.centroid.y - b.centroid.y
                norm = get_dist(vx, vy) or 1.0
                pos[0] += (vx / norm) * grid_step
                pos[1] += (vy / norm) * grid_step
                pos[2] = game_map.get_height_at_point(pos[0], pos[1])

            # commit and return
            m.set_location(*pos)
            print(f"DEBUG: Single-model positioning successful")
            return [(pos[0], pos[1], pos[2], pos[3])]

        print(f"DEBUG: Using multi-model formation templates")
        # SLOW PATH FOR MULTI-MODEL UNITS
        # 1) Build list of blocking models (enemies + optionally friendlies)
        enemy_models = game_map.get_enemy_models(self)
        blocking_models = enemy_models
        print(f"DEBUG: Found {len(enemy_models)} enemy models")
        
        if avoid_friendly_units:
            # Add friendly models from other units (excluding self)
            friendly_models = []
            for unit in game_map.get_friendly_units(self):
                if unit != self:  # Don't include models from the unit being positioned
                    friendly_models.extend(unit.models)
            blocking_models.extend(friendly_models)
            print(f"DEBUG: Added {len(friendly_models)} friendly models from other units")
        
        print(f"DEBUG: Total blocking models: {len(blocking_models)} (enemies: {len(enemy_models)}, friendlies: {len(blocking_models) - len(enemy_models)})")
        
        # 2) Use provided boundary repulsors or default to empty list
        if boundary_repulsors is None:
            boundary_repulsors = []
        
        # 3) Spatial index of terrain + blocking models + boundary repulsors
        # Convert terrain features to blocking polygons for this unit
        from ..utility.calcs import get_terrain_blocking_polygons
        terrain_polygons = []
        for terrain_feature in game_map.terrain_features:
            blocking_polygons = get_terrain_blocking_polygons(self, terrain_feature)
            terrain_polygons.extend(blocking_polygons)

        tree = build_spatial_index(terrain_polygons + boundary_repulsors, blocking_models)

        # 4) Compute safe spacing from the model base shape
        # Use tighter spacing for deployment to allow formations to fit in crowded areas
        # Models can be in base-to-base contact (spacing = 2 * radius) but we allow slightly tighter
        base_radius = self.models[0].model_base.radius[0]
        spacing = 2 * base_radius * 0.8  # 80% of full spacing allows for tighter formations
        print(f"DEBUG: Computed spacing: {spacing:.2f} inches (base radius: {base_radius:.2f})")

        # 5) Build formation templates
        templates = build_formation_templates(len(self.models), spacing)
        print(f"DEBUG: Generated {len(templates)} formation templates: {list(templates.keys())}")

        origin_2d = np.array((start_x, start_y), float)

        # 6) Try each template
        for template_name, offsets in templates.items():
            print(f"DEBUG: Trying template '{template_name}' with {len(offsets)} positions")
            
            # world positions in 2D & then lift to 3D + facing
            world = []
            pts2d = offsets + origin_2d
            for x, y in pts2d:
                z = game_map.get_height_at_point(x, y)
                f = self.calculate_strategic_facing(x, y, game_map)
                world.append([x, y, z, f])

            # Check individual model base collisions instead of unit footprint
            # This allows unit footprints to overlap as long as individual model bases don't overlap
            model_collision_detected = False
            for i, (dx, dy) in enumerate(offsets):
                model_x = origin_2d[0] + dx
                model_y = origin_2d[1] + dy
                
                # Create temporary model base at this position
                temp_model = self.models[i] if i < len(self.models) else self.models[0]
                temp_base = temp_model.model_base.get_base_shape()
                temp_base_positioned = translate(temp_base, 
                                               model_x - temp_base.centroid.x,
                                               model_y - temp_base.centroid.y)
                
                # Check collision with obstacles and enemy models only
                # (friendly unit avoidance is handled by the avoid_friendly_units parameter)
                base_hits = query_spatial_index(tree, temp_base_positioned)
                if len(base_hits) > 0:
                    # Check if any hits are actual overlaps (not just touching)
                    for hit in base_hits:
                        if temp_base_positioned.overlaps(hit):
                            model_collision_detected = True
                            break
                    if model_collision_detected:
                        break
            
            if model_collision_detected:
                print(f"DEBUG: Template '{template_name}' rejected - model base overlap detected")
                continue

            # Debug: Check if any models are outside battlefield bounds
            models_outside_bounds = 0
            for i, pos in enumerate(world):
                if pos[0] < 0 or pos[0] > game_map.width or pos[1] < 0 or pos[1] > game_map.height:
                    models_outside_bounds += 1

            if models_outside_bounds > 0:
                print(f"DEBUG: Template '{template_name}' rejected - {models_outside_bounds} models outside battlefield bounds (map: {game_map.width}x{game_map.height})")
                continue

            print(f"DEBUG: Template '{template_name}' passed footprint check, starting relaxation")

            # Relaxation loop (terrain + self-collisions)
            for relax_iter in range(relax_iters):
                collided = False
                
                # precompute friendly polys at current trial positions
                friendly = []
                for idx, pos in enumerate(world):
                    base = self.models[idx].model_base.get_base_shape()
                    friendly.append(
                        translate(base, 
                                pos[0] - base.centroid.x, 
                                pos[1] - base.centroid.y)
                    )

                for i, pos in enumerate(world):
                    poly_i = friendly[i]
                    # gather blockers as a pure Python list
                    hits = query_spatial_index(tree, poly_i) \
                        + [p for j,p in enumerate(friendly) if j != i]

                    # DEBUG: Add defensive programming to catch geometry type errors
                    try:
                        intersects_any = any(poly_i.intersects(b) for b in hits)
                    except TypeError as e:
                        print(f"DEBUG: TypeError in multi-model intersects check: {e}")
                        print(f"DEBUG: poly_i type: {type(poly_i)}")
                        print(f"DEBUG: hits count: {len(hits)}")
                        for idx, hit in enumerate(hits):
                            print(f"DEBUG: hit {idx}: {type(hit)} - {hit}")
                            if hasattr(hit, 'geom_type'):
                                print(f"DEBUG:   geom_type: {hit.geom_type}")
                            if hasattr(hit, 'is_valid'):
                                print(f"DEBUG:   is_valid: {hit.is_valid}")
                        raise
                    
                    if intersects_any:
                        # repel along the vector between centroids
                        b = next(b for b in hits if poly_i.intersects(b))
                        vx = poly_i.centroid.x - b.centroid.x
                        vy = poly_i.centroid.y - b.centroid.y
                        norm = get_dist(vx, vy) or 1.0
                        pos[0] += (vx / norm) * grid_step
                        pos[1] += (vy / norm) * grid_step
                        pos[2] = game_map.get_height_at_point(pos[0], pos[1])
                        collided = True
                        
                if not collided:
                    print(f"DEBUG: Template '{template_name}' completed relaxation after {relax_iter + 1} iterations")
                    break
                elif relax_iter == relax_iters - 1:
                    print(f"DEBUG: Template '{template_name}' still had collisions after {relax_iters} relaxation iterations")

            # after you've cleared collisions...
            attract_iters = 5
            attract_step = 0.2
            target_min = 0.25
            for _ in range(attract_iters):
                moved = False
                for i, m1 in enumerate(self.models):
                    for j, m2 in enumerate(self.models[i+1:], start=i+1):
                        d = m1.model_base.edge_to_edge_distance(m2.model_base)
                        if d > target_min + 1e-6:
                            # move each halfway toward the other
                            dx = (m2.x - m1.x)
                            dy = (m2.y - m1.y)
                            norm = get_dist(dx, dy)
                            shift = min(attract_step, d/2) / norm
                            m1.model_base.x += dx * shift
                            m1.model_base.y += dy * shift
                            m2.model_base.x -= dx * shift
                            m2.model_base.y -= dy * shift
                            moved = True
                if not moved:
                    break

            # Final overlap catcher
            final_polys = []
            for idx, pos in enumerate(world):
                base = self.models[idx].model_base.get_base_shape()
                final_polys.append(
                    translate(base,
                            pos[0] - base.centroid.x,
                            pos[1] - base.centroid.y)
                )

            # if any true-area overlap, reject this template
            ok = True
            for i in range(len(final_polys)):
                for j in range(i+1, len(final_polys)):
                    if final_polys[i].overlaps(final_polys[j]):
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                print(f"DEBUG: Template '{template_name}' rejected - final overlap check failed")
                continue

            # Commit & coherency-graph check
            for m, pos in zip(self.models, world):
                m.set_location(*pos)
                
            coherency_ok = self.check_coherency_graph()
            print(f"DEBUG: Template '{template_name}' coherency check: {' PASSED' if coherency_ok else ' FAILED'}")
            
            if coherency_ok:
                print(f"DEBUG: Successfully found formation using template '{template_name}'")
                return [(x, y, z, f) for x, y, z, f in world]
            else:
                print(f"DEBUG: Template '{template_name}' rejected - coherency check failed")

        # 7) If none fit, raise or fallback
        print(f"DEBUG: All {len(templates)} templates failed - no valid formation found")
        # No valid formation found - return None instead of raising exception
        # This allows auto-deployment to try other positions
        return None

    def _create_potential_base(self, x: float, y: float, z: float, facing: float, model: Model = None):
        # Create a new base with the same properties as the specified model's base
        if model is None:
            model = self.models[0]  # Default to first model
        new_base = copy.deepcopy(model.model_base)
        new_base.x, new_base.y, new_base.z = x, y, z
        new_base.set_facing(facing)
        return new_base

    def _collides_with_unit_models(self, x: float, y: float, z: float, facing: float, positions: List[Tuple[float, float, float, float]], model: Model = None) -> bool:
        """Check if the model at the given position collides with any other model in the unit."""
        if not positions:
            return False

        if len(self.models) == 1:
            return False

        new_base = self._create_potential_base(x, y, z, facing, model)

        for i, pos in enumerate(positions):
            # Use the corresponding model for each position
            other_model = self.models[i] if i < len(self.models) else self.models[0]
            other_base = self._create_potential_base(pos[0], pos[1], pos[2], pos[3], other_model)
            if new_base.collides_with(other_base):
                logger.debug(f"Collision detected!")
                return True
        return False

    def _is_coherent_within_unit(self, x: float, y: float, z: float, facing: float, positions: List[Tuple[float, float, float, float]], model: Model = None) -> bool:
        """Check if the model at the given position is within coherency with the unit."""
        new_base = self._create_potential_base(x, y, z, facing, model)

        # Check against already placed models
        found_neighbors = 0
        current_neighbors_needed = 0 if len(positions) == 0 else 1 if len(positions) == 1 else self.required_neighbors

        if current_neighbors_needed == 0:
            return True

        for i, pos in enumerate(positions):
            # Use the corresponding model for each position
            other_model = self.models[i] if i < len(self.models) else self.models[0]
            other_base = self._create_potential_base(pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0, pos[3] if len(pos) > 3 else facing, other_model)
            # 10th ed coherency: <=2" horizontal (base edge-to-edge) AND <=5" vertical (base-to-base)
            try:
                horizontal = new_base.get_base_shape().distance(other_base.get_base_shape())
                vertical = abs(float(getattr(new_base, 'z', 0.0)) - float(getattr(other_base, 'z', 0.0)))
            except Exception:
                horizontal = float('inf')
                vertical = float('inf')
            if horizontal <= self.coherency_distance + 1e-6 and vertical <= 5.0 + 1e-6:
                found_neighbors += 1
                if found_neighbors >= current_neighbors_needed:
                    return True
        return False

    def check_coherency_graph(self):
        """
        Returns True if every model in the unit
        has the required number of neighbors within edge-to-edge
        coherency_distance.

        - Units of 1\u20135 models: each model needs at least 1 neighbor.
        - Units of 6+ models: each model needs at least 2 neighbors.
        """
        models = self.models

        for i, m1 in enumerate(models):
            neighbors = 0
            for j, m2 in enumerate(models):
                if i == j:
                    continue
                # 10th ed coherency: <=2" horizontal (base edge-to-edge) AND <=5" vertical (base-to-base)
                try:
                    horizontal = m1.model_base.get_base_shape().distance(m2.model_base.get_base_shape())
                    vertical = abs(float(getattr(m1.model_base, 'z', 0.0)) - float(getattr(m2.model_base, 'z', 0.0)))
                except Exception:
                    horizontal = float('inf')
                    vertical = float('inf')
                if horizontal <= self.coherency_distance + 1e-6 and vertical <= 5.0 + 1e-6:
                    neighbors += 1
                if neighbors >= self.required_neighbors:
                    break

            if neighbors < self.required_neighbors:
                return False

        return True


    def _is_valid_position(self, x: float, y: float, z: float, facing: float, game_map: 'Map', placed_positions: List[Tuple[float, float, float, float]], model: Model = None) -> bool:
        if model is None:
            model = self.models[0]  # Use the first model as a reference
        if not game_map.is_within_boundary(model, (x, y)):
            return False
        if self._check_collision_with_obstacles_or_terrain(game_map, model, (x, y)):
            return False
        if game_map.check_collision_with_other_friendly_units(model, (x, y)):
            return False
        if game_map.check_collision_with_other_enemy_units(model, (x, y)):
            return False
        if self._collides_with_unit_models(x, y, z, facing, placed_positions, model):
            return False
        if not self._is_coherent_within_unit(x, y, z, facing, placed_positions, model):
            return False
        return True


    ###########################################################################
    ### Range and Line of Sight
    ###########################################################################
    def maximum_range(self) -> int:
        """Maximum range of the unit."""
        if hasattr(self, 'max_shooting_range'):
            return self.max_shooting_range

        max_range = 0
        for model in self.models:
            max_range = max(max_range, model.maximum_range())
        self.max_shooting_range = max_range
        return max_range

    def print_unit(self) -> str:
        return f"{self.name} :: M: {self.movement}\", T: {self.toughness}, Sv: {self.save}, InvSv: {self.inv_save}, OC: {self.objective_control}"

    ###########################################################################
    ### Dunder Methods
    ###########################################################################
    def __str__(self):
        return f"{self.name} ({len(self.models)} models)"

    def __repr__(self):
        return f"Unit(name='{self.name}', models={len(self.models)})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Unit):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def can_declare_charge_against(self, target_unit: 'Unit', game: 'Game', *, out_of_turn: bool = False) -> bool:
        """Check if this unit can declare a charge against the target unit."""
        if not self.is_alive() or not target_unit.is_alive():
            return False

        if not self._can_declare_charge_base(game, out_of_turn=out_of_turn):
            return False

        # Only FLY units can charge AIRCRAFT.
        try:
            if bool(getattr(target_unit, "is_aircraft", False)) and not bool(getattr(self, "is_flying", False)):
                return False
        except Exception:
            pass

        # Cabal of Sorcerers (Temporal Surge): cannot charge until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("cabal_temporal_surge_no_charge_turn_owner"):
                owner = str(sr.get("cabal_temporal_surge_no_charge_turn_owner") or "")
                turn = int(sr.get("cabal_temporal_surge_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    try:
                        if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                            return False
                    except Exception:
                        return False
        except Exception:
            pass

        # Swooping Descent: arriving within 9" denies charges until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_swooping_descent_no_charge_turn_owner"):
                owner = str(sr.get("pain_swooping_descent_no_charge_turn_owner") or "")
                turn = int(sr.get("pain_swooping_descent_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Fire and Fade: cannot charge until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("fire_and_fade_no_charge_turn_owner"):
                owner = str(sr.get("fire_and_fade_no_charge_turn_owner") or "")
                turn = int(sr.get("fire_and_fade_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass
            
        if self._thrill_seekers_restriction_reason(target_unit, game):
            return False
        
        # Check if target is within maximum charge range (2D6 = max 12")
        distance = game.map.get_distance_between_units(self, target_unit)
        max_distance = self.max_charge_distance
        getter = getattr(game, "get_max_charge_distance", None) if game is not None else None
        if callable(getter):
            max_distance = float(getter(self, target_unit=target_unit))
        if distance > max_distance:
            return False
            
        # Check if there's a clear charge path
        # This is simplified - in real 40k you can charge around terrain
        if game.map.is_path_blocked(self, target_unit):
            return False
            
        return True

    def _can_declare_charge_base(self, game: 'Game', *, out_of_turn: bool = False) -> bool:
        if not self.is_alive():
            return False
        if bool(getattr(self, "is_aircraft", False)):
            return False
        if self.round_state.attempted_charge_this_round and not out_of_turn:
            return False
        if self.round_state.advanced_this_round and not self.can_charge_after_advance():
            return False
        if getattr(self.round_state, "disembarked_cannot_charge", False):
            return False
        if getattr(self.round_state, "disembarked_from_destroyed_transport", False):
            return False
        if self.round_state.fell_back_this_round and not self.can_charge_after_fall_back():
            return False
        if getattr(self.round_state, 'action_locked_until_turn_end', False):
            return False
        if self.arrived_from_reserves_this_turn and not self.can_charge_after_arriving_from_reserves():
            return False

        # Units within Engagement Range of any enemy cannot declare charges.
        try:
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
        if game_map is not None:
            try:
                enemy_units = list(game_map.get_enemy_units(self) or [])
            except Exception:
                enemy_units = []
            for enemy in enemy_units:
                if not getattr(enemy, "is_alive", False):
                    continue
                if game_map.is_within_engagement_range(self, enemy):
                    return False
        return True

    def can_declare_charge(self, game: 'Game', *, out_of_turn: bool = False) -> bool:
        """Check if this unit is eligible to declare any charge this phase."""
        if not self._can_declare_charge_base(game, out_of_turn=out_of_turn):
            return False
        try:
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
        if game_map is None:
            return False
        enemy_units = [u for u in game_map.get_enemy_units(self) if u.is_alive()]
        if not enemy_units:
            return False
        max_distance = float(getattr(self, "max_charge_distance", 0) or 0)
        getter = getattr(game, "get_max_charge_distance", None)
        if callable(getter):
            max_distance = float(getter(self, target_unit=None))
        for enemy in enemy_units:
            try:
                if game_map.get_distance_between_units(self, enemy) <= max_distance:
                    return True
            except Exception:
                continue
        return False

    def validate_charge_end_state(self, target_units: list['Unit'], game_map: 'Map') -> tuple[bool, str]:
        """Validate charge end position against declared targets and non-targets."""
        if not target_units:
            return False, "Charge requires at least one target"
        target_ids = {get_entity_id(u) for u in list(target_units or []) if u is not None}
        missing = []
        for target in target_units:
            if target is None or not getattr(target, "is_alive", False):
                missing.append(getattr(target, "name", "Unknown"))
                continue
            if not game_map.is_within_engagement_range(self, target):
                missing.append(getattr(target, "name", "Unknown"))
        if missing:
            return False, f"Charge must end within Engagement Range of all targets (missing: {', '.join(missing)})"
        # Cannot end within Engagement Range of non-target enemy units.
        for enemy in list(game_map.get_enemy_units(self) or []):
            if enemy is None or not getattr(enemy, "is_alive", False):
                continue
            if get_entity_id(enemy) in target_ids:
                continue
            if game_map.is_within_engagement_range(self, enemy):
                return False, f"Charge cannot end within Engagement Range of non-target unit {enemy.name}"
        return True, ""

    def get_threat_value(self) -> float:
        """Calculate the total threat value of this unit."""
        ranged_threat, melee_threat = self.get_threat_level()
        return ranged_threat + melee_threat

    def get_overwatch_risk(self, charging_unit: 'Unit', game: 'Game') -> float:
        """Calculate the risk this unit poses in overwatch to a charging unit.
        
        Args:
            charging_unit (Unit): The unit attempting to charge
            game (Game): The game instance for distance calculations
            
        Returns:
            float: Risk value from 0.0 to 1.0, where higher values indicate more risk
        """
        # Base risk on our ranged threat level
        ranged_threat, _ = self.get_threat_level()
        
        # Modify based on distance (closer = more dangerous)
        distance = game.get_distance_between_units(charging_unit, self)
        distance_modifier = 1.0 / max(distance, 1.0)  # Avoid division by zero
        
        # Consider if we've already shot this round
        if self.round_state.shot_this_round:
            ranged_threat *= 0.5  # Reduced effectiveness if already shot
            
        # Consider remaining CP for stratagems
        army = self.get_parent_army()
        if army and army.player:
            cp_modifier = min(1.0, army.player.command_points / 3.0)  # Scale based on available CP
            ranged_threat *= (1.0 + cp_modifier)  # More CP = more potential threats
        
        return ranged_threat * distance_modifier
    
    def _find_ability_with_patterns(self, patterns: List[str], extract_value: bool = False, value_pattern: str = None) -> Tuple[bool, Optional[str]]:
        r"""
        Helper method to find abilities matching given patterns and optionally extract values.
        
        Args:
            patterns: List of patterns to search for (case-insensitive)
            extract_value: Whether to extract a value from the matched text
            value_pattern: Regex pattern to extract value (e.g., r'(\d+)' for numbers, r'(\d+|D\d+)' for dice)
        
        Returns:
            Tuple[bool, Optional[str]]: (found, extracted_value)
        """
        # Check keywords first
        for keyword in self.keywords:
            for pattern in patterns:
                if pattern.lower() in keyword.lower():
                    if extract_value and value_pattern:
                        match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', keyword.lower())
                        if match:
                            return True, match.group(1)
                        else:
                            raise ValueError(f"{pattern} ability found in keyword '{keyword}' but could not extract value for unit '{self.name}'")
                    else:
                        return True, None
        
        # Check unit-level abilities (possible_abilities)
        for ability in self._iter_active_possible_abilities():
            if isinstance(ability, str):
                for pattern in patterns:
                    if pattern.lower() in ability.lower():
                        if extract_value and value_pattern:
                            match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', ability.lower())
                            if match:
                                return True, match.group(1)
                            else:
                                raise ValueError(f"{pattern} ability found in ability string '{ability}' but could not extract value for unit '{self.name}'")
                        else:
                            return True, None
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, 'name') and ability.name:
                    for pattern in patterns:
                        if pattern.lower() in ability.name.lower():
                            ability_name_matched = True
                            if extract_value and value_pattern:
                                match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', ability.name.lower())
                                if match:
                                    return True, match.group(1)
                                else:
                                    # Check if ability has a parameter attribute
                                    if hasattr(ability, 'parameter') and ability.parameter:
                                        param_match = re.search(value_pattern, ability.parameter)
                                        if param_match:
                                            return True, param_match.group(1)
                                        else:
                                            raise ValueError(f"{pattern} ability found in ability name '{ability.name}' with parameter '{ability.parameter}' but could not extract value for unit '{self.name}'")
                                    else:
                                        raise ValueError(f"{pattern} ability found in ability name '{ability.name}' but could not extract value for unit '{self.name}'")
                            else:
                                return True, None
                
                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, 'description') and ability.description:
                    for pattern in patterns:
                        if pattern.lower() in ability.description.lower():
                            if extract_value and value_pattern:
                                match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', ability.description.lower())
                                if match:
                                    return True, match.group(1)
                                else:
                                    raise ValueError(f"{pattern} ability found in ability description '{ability.description}' but could not extract value for unit '{self.name}'")
                            else:
                                return True, None
        
        # Check model-level abilities
        for ability in self.abilities:
            try:
                if not self._ability_is_active(ability):
                    continue
            except Exception:
                pass
            if isinstance(ability, str):
                for pattern in patterns:
                    if pattern.lower() in ability.lower():
                        if extract_value and value_pattern:
                            match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', ability.lower())
                            if match:
                                return True, match.group(1)
                            else:
                                raise ValueError(f"{pattern} ability found in model ability string '{ability}' but could not extract value for unit '{self.name}'")
                        else:
                            return True, None
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, 'name') and ability.name:
                    for pattern in patterns:
                        if pattern.lower() in ability.name.lower():
                            ability_name_matched = True
                            if extract_value and value_pattern:
                                match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', ability.name.lower())
                                if match:
                                    return True, match.group(1)
                                else:
                                    # Check if ability has a parameter attribute
                                    if hasattr(ability, 'parameter') and ability.parameter:
                                        param_match = re.search(value_pattern, ability.parameter)
                                        if param_match:
                                            return True, param_match.group(1)
                                        else:
                                            raise ValueError(f"{pattern} ability found in model ability name '{ability.name}' with parameter '{ability.parameter}' but could not extract value for unit '{self.name}'")
                                    else:
                                        raise ValueError(f"{pattern} ability found in model ability name '{ability.name}' but could not extract value for unit '{self.name}'")
                            else:
                                return True, None
                
                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, 'description') and ability.description:
                    for pattern in patterns:
                        if pattern.lower() in ability.description.lower():
                            if extract_value and value_pattern:
                                match = re.search(rf'{pattern.lower()}\s*\(?{value_pattern}', ability.description.lower())
                                if match:
                                    return True, match.group(1)
                                else:
                                    raise ValueError(f"{pattern} ability found in model ability description '{ability.description}' but could not extract value for unit '{self.name}'")
                            else:
                                return True, None
        
        return False, None

    def has_deep_strike(self) -> bool:
        """Check if the unit has Deep Strike ability."""
        # Use cached result if available
        if 'deep_strike' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['deep_strike']

        found = False
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bearer_unit_deep_strike"):
                found = True
        except Exception:
            pass
        if not found:
            try:
                if self._disciple_of_khorne_active():
                    found = True
            except Exception:
                found = False
        if not found:
            if (
                self._first_prince_of_chaos_active()
                and self._is_chaos_undivided()
                and self.has_any_keyword("HERETIC ASTARTES")
            ):
                found = True
            else:
                found, _ = self._find_ability_with_patterns(["deep strike", "deepstrike"])

        # Attached units can only Deep Strike if every model has Deep Strike.
        try:
            if found and (not bool(getattr(self, "is_leader", False)) or getattr(self, "attached_to", None) is None):
                root = self.get_attached_unit_root()
                leaders = list(getattr(root, "attached_leaders", []) or [])
                for leader in leaders:
                    try:
                        if not leader.has_deep_strike():
                            found = False
                            break
                    except Exception:
                        found = False
                        break
        except Exception:
            pass
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['deep_strike'] = found
        
        return found

    def has_infiltrate(self) -> bool:
        """Check if the unit has Infiltrate ability."""
        # Use cached result if available
        if 'infiltrate' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['infiltrate']
        
        found, _ = self._find_ability_with_patterns(["infiltrators", "infiltrate"])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['infiltrate'] = found
        
        return found
    
    def has_stealth(self) -> bool:
        """Check if the unit has Stealth ability."""
        # Stratagem: SMOKESCREEN grants Stealth until end of phase.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("smokescreen_active") is True:
                return True
        except Exception:
            pass
        # Use cached result if available
        if 'stealth' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['stealth']
        
        found, _ = self._find_ability_with_patterns(["stealth"])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['stealth'] = found
        
        return found
    
    def has_scout(self) -> Tuple[bool, float]:
        """Check if the unit has Scout ability and return the scout distance.
        
        Returns:
            Tuple[bool, float]: A tuple containing:
                - A boolean indicating if the unit has Scout ability
                - The scout distance in inches (0.0 if no Scout ability)
        """
        # Use cached result if available
        if 'scout' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['scout']
        
        try:
            found, distance_str = self._find_ability_with_patterns(["scout"], extract_value=True, value_pattern=r'(\d+)')
        except ValueError:
            found, distance_str = False, None
            try:
                for txt in self._iter_active_ability_texts():
                    low = str(txt or "").lower()
                    if "scout" not in low:
                        continue
                    m = re.search(r"scouts?\s*(\d+)", low)
                    if m:
                        found = True
                        distance_str = m.group(1)
                        break
            except Exception:
                found, distance_str = False, None
        result = (True, float(distance_str)) if found else (False, 0.0)

        # Attached units can only Scout if every model has Scouts (use smallest distance if mixed).
        try:
            if result[0] and (not bool(getattr(self, "is_leader", False)) or getattr(self, "attached_to", None) is None):
                root = self.get_attached_unit_root()
                leaders = list(getattr(root, "attached_leaders", []) or [])
                min_dist = float(result[1])
                for leader in leaders:
                    try:
                        l_found, l_dist = leader.has_scout()
                    except Exception:
                        l_found, l_dist = False, 0.0
                    if not l_found:
                        result = (False, 0.0)
                        break
                    try:
                        min_dist = min(min_dist, float(l_dist))
                    except Exception:
                        pass
                if result[0]:
                    result = (True, float(min_dist))
        except Exception:
            pass
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['scout'] = result
        
        return result
    
    def get_scout_distance_normalized(self, max_scout_distance: float = 12.0) -> float:
        """Get the normalized scout distance for deployment considerations.
        
        Args:
            max_scout_distance (float): Maximum possible scout distance for normalization
            
        Returns:
            float: Normalized scout distance (0.0 to 1.0), where 1.0 represents maximum scout mobility
        """
        has_scout_ability, scout_distance = self.has_scout()
        if not has_scout_ability:
            return 0.0
        
        return min(scout_distance / max_scout_distance, 1.0)

    def has_redeploy(self) -> Tuple[bool, int, bool]:
        """Check if the unit grants redeploy capability.

        Returns:
            Tuple[bool, int, bool]:
                - has_redeploy: True if this unit grants redeploy to units in the army
                - count: number of units that can be redeployed (default 3; D3 treated as 3 for now)
                - can_place_in_reserves: True if redeployed units may be placed into Strategic Reserves regardless of limits

        Notes:
            We intentionally parse ability descriptions rather than names. The wording generally includes
            "after both players have deployed their armies" and "select up to" N units from your army "and redeploy them".
        """
        # Use cached result if available
        if 'redeploy' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['redeploy']

        has_redeploy = False
        count = 0
        can_place_in_reserves = False

        # Normalize abilities list: abilities may be attached to models in unit
        abilities_to_check = []
        for model in getattr(self, 'models', []):
            for ability in getattr(model, 'abilities', []):
                if ability and hasattr(ability, 'description'):
                    try:
                        if not self._ability_is_active(ability):
                            continue
                    except Exception:
                        pass
                    abilities_to_check.append(ability.description)

        # Also include unit-level possible_abilities if present
        for ability in self._iter_active_possible_abilities():
            if ability and hasattr(ability, 'description'):
                abilities_to_check.append(ability.description)

        for desc in abilities_to_check:
            text = desc.lower()
            if ("after both players have deployed their armies" in text and "redeploy" in text):
                # Attempt to extract count from "select up to" phrases
                has_redeploy = True
                # Support numeric or dice expressions like D3, D6, D10 (optionally with +N)
                m = re.search(r"select\s+up\s+to\s+((?:\d+)|(?:d\d+(?:\s*\+\s*\d+)?))", text)
                if m:
                    val = m.group(1)
                    if val.startswith('d'):
                        # Roll the indicated die expression (e.g., D3, D6, D10), with optional +N
                        try:
                            expr = val.upper().replace(' ', '')
                            d = DiceCollection.from_string(expr)
                            total, rolls = d.roll_detailed()
                            count = max(count, total)
                            # Cache roll detail for UI/logging (generic cache)
                            setattr(self, '_redeploy_d_roll', {'expr': expr, 'total': total, 'rolls': rolls})
                            print(f"{self.name} Redeploy {expr} roll: {total} (rolled {rolls})")
                        except Exception:
                            # Fallback to minimal 1 if dice utilities unavailable
                            count = max(count, 1)
                    else:
                        try:
                            count = max(count, int(val))
                        except Exception:
                            pass
                else:
                    count = max(count, 3)  # default to 3 if unspecified
                if "strategic reserves" in text:
                    can_place_in_reserves = True

        result = (has_redeploy, count, can_place_in_reserves)
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['redeploy'] = result
        return result
    
    def has_firing_deck(self) -> Tuple[bool, int]:
        """Check if the unit has Firing Deck ability and return the number of weapons.
        
        Returns:
            Tuple[bool, int]: A tuple containing:
                - A boolean indicating if the unit has Firing Deck ability
                - The number of weapons that can fire from the deck (0 if no Firing Deck ability)
        """
        found, number_str = self._find_ability_with_patterns(["firing deck"], extract_value=True, value_pattern=r'(\d+)')
        if found:
            return True, int(number_str)
        return False, 0

    ###########################################################################
    ### Firing Deck (Transport) support
    ###########################################################################
    def clear_firing_deck_virtual_wargear(self) -> None:
        """
        Remove temporary "virtual" wargear added to the transport model to represent embarked weapons.

        This is used by the UI: the transport is treated as being equipped with those weapons
        for the duration of its shooting selection / resolution.
        """
        # Remove injected wargear from transport models
        vw = list(getattr(self, "_firing_deck_virtual_wargear", []) or [])
        if not vw:
            self._firing_deck_virtual_wargear = []
            self._firing_deck_virtual_sources = {}
            return
        for model in list(getattr(self, "models", []) or []):
            try:
                if not getattr(model, "is_alive", False):
                    continue
                if not hasattr(model, "wargear"):
                    continue
                model.wargear = [w for w in (model.wargear or []) if w not in vw]
            except Exception:
                continue
        self._firing_deck_virtual_wargear = []
        self._firing_deck_virtual_sources = {}

    def apply_firing_deck_virtual_wargear(self, selections: List[dict]) -> None:
        """
        Add temporary wargear/profile objects onto the transport model(s) so the existing
        shooting engine can validate and resolve attacks from the transport's position.

        `selections` entries are expected to include:
        - model: embarked Model providing the weapon
        - wargear: Wargear instance on the embarked model
        - profile: WargearProfile selected
        - profile_name: profile name string (optional)

        After this, `_firing_deck_virtual_sources[profile_clone.id] = [source_model]` is populated
        so shooting resolution can mark those embarked models as having shot.
        """
        import copy

        # Clear any previous injection first (safe even if none)
        self.clear_firing_deck_virtual_wargear()

        # Find at least one alive transport model to host these virtual weapons
        host_models = [m for m in (getattr(self, "models", []) or []) if getattr(m, "is_alive", False)]
        if not host_models:
            return
        host = host_models[0]

        class _VirtualWargear:
            def __init__(self, name: str, profile_obj):
                self.name = (name or "Firing Deck").replace("\u2019", "'")
                self.type = "ranged"
                self.profiles = {"default": profile_obj}

            def is_ranged(self) -> bool:
                return True

            def is_melee(self) -> bool:
                return False

        self._firing_deck_virtual_wargear = []
        self._firing_deck_virtual_sources = {}

        # Build one virtual wargear per selected embarked weapon (keeps them as individual entries)
        for s in list(selections or []):
            src_model = s.get("model")
            src_wargear = s.get("wargear")
            src_profile = s.get("profile")
            if src_model is None or src_wargear is None or src_profile is None:
                continue

            # Exclude ONE SHOT entirely for firing deck selection (explicit requirement)
            if src_profile.is_one_shot():
                continue

            # Clone the profile so we can safely re-parent it without mutating the source model's weapon.
            pclone = copy.copy(src_profile)
            pclone._id = str(uuid.uuid4())
            vname = f"{getattr(src_wargear, 'name', 'Weapon')} (Firing Deck)"
            vwg = _VirtualWargear(vname, pclone)
            pclone.parent_wargear = vwg

            try:
                host.wargear.append(vwg)
            except Exception:
                try:
                    host.wargear = list(getattr(host, "wargear", []) or []) + [vwg]
                except Exception:
                    continue

            self._firing_deck_virtual_wargear.append(vwg)
            self._firing_deck_virtual_sources[pclone.id] = [src_model]
    
    def has_fight_first(self) -> bool:
        """Check if the unit has Fight First ability.
        
        Fight First abilities can come from various sources:
        - Unit keywords like "Fight First"
        - Ability names like "Fights First", "Combat Reflexes", etc.
        - Descriptions containing fight first rules
        
        Returns:
            bool: True if the unit has any Fight First ability
        """
        # Enhancement temporary effects (fight phase) on the attached unit root.
        try:
            root = self.get_attached_unit_root()
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_fight_first_active"):
                return True
        except Exception:
            pass
        # Use cached result if available
        if 'fight_first' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['fight_first']
        
        patterns = [
            "fight first", 
            "fights first", 
            "combat reflexes",
            "lightning reflexes",
            "swift strike",
            "martial prowess"
        ]
        found, _ = self._find_ability_with_patterns(patterns)
        if not found:
            for t in self._iter_attached_leader_ability_texts():
                s = str(t or "").lower()
                if any(p in s for p in patterns):
                    found = True
                    break
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['fight_first'] = found
        
        return found

    def has_enhancement_fight_first_once_per_battle(self) -> bool:
        """Return True if this unit has a once-per-battle enhancement that grants Fight First."""
        sr = getattr(self, "special_rules", None)
        return bool(isinstance(sr, dict) and sr.get("enhancement_fight_first_once_per_battle"))

    def _enhancement_fight_first_once_key(self) -> str:
        enh = getattr(self, "enhancement", None)
        base = str(getattr(enh, "id", "") or "").strip()
        if not base:
            base = str(getattr(enh, "name", "") or "").strip()
        if not base:
            base = "fight_first"
        return f"enhancement_fight_first:{base}".lower()

    def _get_enhancement_bearer_model(self):
        for m in list(getattr(self, "models", []) or []):
            try:
                if not getattr(m, "is_alive", True):
                    continue
            except Exception:
                continue
            return m
        return None

    def can_use_enhancement_fight_first(self) -> bool:
        if not self.has_enhancement_fight_first_once_per_battle():
            return False
        model = self._get_enhancement_bearer_model()
        if model is None:
            return False
        try:
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(self._enhancement_fight_first_once_key()):
                return False
        except Exception:
            return False
        return True

    def activate_enhancement_fight_first(self) -> bool:
        """Activate a once-per-battle enhancement to grant Fight First to the bearer's unit."""
        if not self.has_enhancement_fight_first_once_per_battle():
            return False
        model = self._get_enhancement_bearer_model()
        if model is None:
            return False
        key = self._enhancement_fight_first_once_key()
        try:
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                return False
        except Exception:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if getattr(root, "special_rules", None) is None:
            root.special_rules = {}
        sr = root.special_rules
        sr["enhancement_fight_first_active"] = True
        sr["enhancement_fight_first_expires_phase"] = "FIGHT_PHASE"
        try:
            source = str(getattr(getattr(self, "enhancement", None), "name", "") or "").strip()
            if source:
                sr["enhancement_fight_first_source"] = source
        except Exception:
            pass
        try:
            getattr(model, "mark_used_once_per_battle", lambda _k: None)(key)
        except Exception:
            pass
        root.special_rules = sr
        return True

    def _seductive_gambit_active(self) -> bool:
        try:
            army = self.get_parent_army()
        except Exception:
            army = None
        mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        if mgr is None or not getattr(mgr, "is_legion_of_excess_detachment", lambda: False)():
            return False
        try:
            sr = getattr(self, "special_rules", None)
            return isinstance(sr, dict) and bool(sr.get("seductive_gambit_active"))
        except Exception:
            return False

    def has_fight_on_death(self) -> bool:
        """Check if the unit has a Fight on Death style ability.

        This is implemented as a pattern match against keywords / abilities text.
        The actual resolution is handled at model death time (see `_handle_model_destroyed`).
        """
        if 'fight_on_death' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['fight_on_death']

        found, _ = self._find_ability_with_patterns([
            "fight on death",
            "fights on death",
            "fight when destroyed",
            "fight when this model is destroyed",
            "fight before removing",
            "fight before it is removed",
            "fight before it is removed from play",
            "fight when slain",
            "fight when killed",
            "last stand",
        ])

        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['fight_on_death'] = found
        return found

    def has_shoot_on_death(self) -> bool:
        """Check if the unit has a Shoot on Death style ability.

        Implemented as a pattern match; resolution occurs at model death time.
        """
        if 'shoot_on_death' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['shoot_on_death']

        found, _ = self._find_ability_with_patterns([
            "shoot on death",
            "shoots on death",
            "shoot when destroyed",
            "shoot when this model is destroyed",
            "shoot before removing",
            "shoot before it is removed",
            "shoot before it is removed from play",
            "shoot when slain",
            "shoot when killed",
        ])

        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['shoot_on_death'] = found
        return found

    def has_blood_surge(self) -> bool:
        """Check if the unit has the Blood Surge datasheet ability."""
        if 'blood_surge' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['blood_surge']

        found, _ = self._find_ability_with_patterns(["blood surge"])
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['blood_surge'] = found
        return found

    def get_loping_speed_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Once per turn, when an enemy unit ends a Normal, Advance or Fall Back move within 9\" of this unit,
        if this unit is not within Engagement Range of one or more enemy units, it can make a Normal move of up to D6\"."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "loping_speed_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        seen = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                key = (str(name or "").strip().lower(), u._normalize_rules_text(text_src).lower())
                if key in seen:
                    continue
                seen.add(key)
                text = u._normalize_rules_text(self._strip_eligibility_prefix(text_src))
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                m = self._ENEMY_MOVE_REACTIVE_D6_RE.search(text)
                if not m:
                    continue
                try:
                    rng = int(m.group("range") or 0)
                except Exception:
                    rng = 0
                if rng <= 0:
                    rng = 9
                move_token = str(m.group("move") or "").strip().lower()
                source = str(name or "Loping Speed").strip() or "Loping Speed"
                rule = {"range": int(rng), "source": source}
                if move_token:
                    if move_token.isdigit():
                        try:
                            move_value = int(move_token)
                        except Exception:
                            move_value = 0
                        if move_value > 0:
                            rule["max_distance"] = int(move_value)
                    else:
                        rule["distance_roll"] = move_token.upper()
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def get_setup_reactive_shoot_or_charge_rule(self) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "At the end of your opponent's Movement phase, you can select one enemy unit that was set up on the battlefield
        within 12\" of this model; this model can then either shoot at that unit (if eligible) or declare a charge
        against that unit (no Charge bonus)."
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "setup_reactive_shoot_or_charge_rule"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        rule = None
        seen = set()
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        for u in members:
            for name, desc in u._iter_ability_entries_for_rules(model=None):
                text_src = desc or name or ""
                if not text_src:
                    continue
                key = (str(name or "").strip().lower(), u._normalize_rules_text(text_src).lower())
                if key in seen:
                    continue
                seen.add(key)
                text = u._normalize_rules_text(self._strip_eligibility_prefix(text_src))
                if not text:
                    continue
                text = text.replace("\u2019", "'").replace("\u0192?T", "'")
                m = self._SETUP_REACTIVE_SHOOT_CHARGE_RE.search(text)
                if not m:
                    continue
                try:
                    rng = int(m.group("range") or 0)
                except Exception:
                    rng = 0
                if rng <= 0:
                    rng = 12
                source = str(name or "Reactive Response").strip() or "Reactive Response"
                rule = {"range": int(rng), "source": source}
                break
            if rule is not None:
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = rule
        return rule

    def _loping_speed_turn_key(self, game=None) -> str:
        if game is None:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        owner = str(getattr(current_player, "name", "") or "")
        return f"{br}:{owner}"

    def _setup_reactive_shoot_or_charge_turn_key(self, game=None) -> str:
        if game is None:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        try:
            owner = str(getattr(current_player, "id", "") or "")
        except Exception:
            owner = ""
        phase = ""
        try:
            phase = str(getattr(getattr(game, "phase", None), "name", "") or "")
        except Exception:
            phase = ""
        return f"{br}:{owner}:{phase}"

    def setup_reactive_shoot_or_charge_used_this_phase(self, game=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._setup_reactive_shoot_or_charge_turn_key(game)
        return str(sr.get("setup_reactive_shoot_or_charge_used_key", "")) == key

    def mark_setup_reactive_shoot_or_charge_used(self, game=None) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["setup_reactive_shoot_or_charge_used_key"] = self._setup_reactive_shoot_or_charge_turn_key(game)
        root.special_rules = sr

    def record_setup_reactive_shoot_or_charge_candidate(self, enemy_unit, game=None) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if enemy_unit is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        key = self._setup_reactive_shoot_or_charge_turn_key(game)
        if str(sr.get("setup_reactive_shoot_or_charge_candidates_key", "")) != key:
            sr["setup_reactive_shoot_or_charge_candidates"] = []
        sr["setup_reactive_shoot_or_charge_candidates_key"] = key
        try:
            enemy_id = get_entity_id(enemy_unit)
        except Exception:
            enemy_id = None
        if not enemy_id:
            root.special_rules = sr
            return
        candidates = list(sr.get("setup_reactive_shoot_or_charge_candidates", []) or [])
        if enemy_id not in candidates:
            candidates.append(enemy_id)
        sr["setup_reactive_shoot_or_charge_candidates"] = candidates
        root.special_rules = sr

    def get_setup_reactive_shoot_or_charge_candidates(self, game=None) -> list[str]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return []
        key = self._setup_reactive_shoot_or_charge_turn_key(game)
        if str(sr.get("setup_reactive_shoot_or_charge_candidates_key", "")) != key:
            return []
        return list(sr.get("setup_reactive_shoot_or_charge_candidates", []) or [])

    def clear_setup_reactive_shoot_or_charge_candidates(self, game=None) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        key = self._setup_reactive_shoot_or_charge_turn_key(game)
        if str(sr.get("setup_reactive_shoot_or_charge_candidates_key", "")) != key:
            return
        sr.pop("setup_reactive_shoot_or_charge_candidates", None)
        sr.pop("setup_reactive_shoot_or_charge_candidates_key", None)
        root.special_rules = sr

    def can_setup_reactive_shoot_or_charge(
        self,
        game=None,
        game_map=None,
        *,
        enemy_unit=None,
        range_override: Optional[int] = None,
    ) -> bool:
        rule = self.get_setup_reactive_shoot_or_charge_rule()
        if not rule:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        if not root.is_alive() or not getattr(root, "deployed", False):
            return False
        try:
            if root.is_in_reserves():
                return False
        except Exception:
            pass
        try:
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                return False
        except Exception:
            pass
        if root.setup_reactive_shoot_or_charge_used_this_phase(game):
            return False
        if enemy_unit is not None and game_map is not None:
            try:
                rng = int(range_override or rule.get("range", 12) or 12)
            except Exception:
                rng = 12
            try:
                from ..utility.aura_utils import unit_within_range_of_unit
                if not unit_within_range_of_unit(root, enemy_unit, float(rng), use_attached_aggregate=True):
                    return False
            except Exception:
                return False
        return True

    def loping_speed_used_this_turn(self, game=None) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._loping_speed_turn_key(game)
        return str(sr.get("loping_speed_used_turn_key", "")) == key

    def mark_loping_speed_used(self, game=None) -> None:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["loping_speed_used_turn_key"] = self._loping_speed_turn_key(game)
        root.special_rules = sr

    def can_loping_speed(self, game=None, game_map=None, *, moving_unit=None, range_override: Optional[int] = None) -> bool:
        rule = self.get_loping_speed_rule()
        if not rule:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        if not root.is_alive() or not getattr(root, "deployed", False):
            return False
        try:
            if root.is_in_reserves():
                return False
        except Exception:
            pass
        try:
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                return False
        except Exception:
            pass
        if root.loping_speed_used_this_turn(game):
            return False
        if game_map is None:
            try:
                game_map = getattr(game, "map", None)
            except Exception:
                game_map = None
        if game_map is not None:
            try:
                for enemy in game_map.get_enemy_units(root):
                    if game_map.is_within_engagement_range(root, enemy):
                        return False
            except Exception:
                pass
        if moving_unit is not None and game_map is not None:
            try:
                rng = int(range_override or rule.get("range", 9) or 9)
            except Exception:
                rng = 9
            try:
                dist = float(game_map.get_distance_between_units(root, moving_unit))
            except Exception:
                dist = None
            if dist is None or dist > float(rng) + 1e-6:
                return False
        return True

    def has_frenzy(self) -> bool:
        """True if this unit has the Helbrute-style Frenzy ability (shoot or fight vs the triggering unit)."""
        if 'frenzy' in getattr(self, '_ability_cache', {}):
            return bool(self._ability_cache['frenzy'])

        found = False
        try:
            for name, desc in self._iter_ability_entries_for_rules(model=None):
                text = self._normalize_rules_text(f"{name} {desc}").lower()
                if "frenzy" not in text:
                    continue
                if "can either shoot or fight" not in text:
                    continue
                if "only target that enemy unit" not in text:
                    continue
                found = True
                break
        except Exception:
            found = False

        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['frenzy'] = bool(found)
        return bool(found)

    def has_furious_onslaught(self, model: Optional['Model'] = None) -> bool:
        """True if this model has the Furious Onslaught datasheet ability."""
        if model is None:
            return False
        cache_key = f"furious_onslaught:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return bool(self._ability_cache[cache_key])

        found = False
        try:
            for name, desc in self._iter_model_specific_ability_entries(model):
                text = self._normalize_rules_text(name or "")
                if text and "furious onslaught" in text.lower():
                    found = True
                    break
                text = self._normalize_rules_text(desc or "")
                if text and "furious onslaught" in text.lower():
                    found = True
                    break
        except Exception:
            found = False

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = bool(found)
        return bool(found)

    def get_closest_enemy_hit_reroll_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time a model in this unit makes a ranged attack that targets the closest enemy unit,
        you can re-roll the Hit roll."
        """
        if model is None:
            return None
        cache_key = f"closest_enemy_hit_reroll_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            for name, desc in self._iter_ability_entries_for_rules(model=model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower()
                if "ranged attack" not in low:
                    continue
                if not re.search(r"closest\s+(?:eligible\s+)?enemy\s+unit", low):
                    continue
                if "hit roll" not in low:
                    continue
                if ("re-roll" not in low) and ("reroll" not in low):
                    continue
                source = str(name or "Closest enemy unit").strip() or "Closest enemy unit"
                rule = {"source": source}
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_closest_monster_vehicle_reroll_rule(self, model: Optional['Model'] = None) -> Optional[dict]:
        """
        Return rule info for abilities like:
        "Each time this model makes a ranged attack that targets the closest eligible MONSTER or VEHICLE target within 18\",
        you can re-roll the Wound roll and you can re-roll the Damage roll."
        """
        if model is None:
            return None
        cache_key = f"closest_monster_vehicle_reroll_rule:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        rule = None
        try:
            for name, desc in self._iter_model_specific_ability_entries(model):
                text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                if not text:
                    continue
                low = text.lower()
                if "ranged attack" not in low:
                    continue
                if "closest eligible" not in low:
                    continue
                if "monster" not in low or "vehicle" not in low:
                    continue
                if ("re-roll" not in low) and ("reroll" not in low):
                    continue
                m = re.search(r"within\s+(\d+)\s*(?:\"|inches)", low)
                if not m:
                    continue
                allow_wound = bool(re.search(r"re-?roll\s+the\s+wound\s+roll", low))
                allow_damage = bool(re.search(r"re-?roll\s+the\s+damage\s+roll", low))
                if not (allow_wound or allow_damage):
                    continue
                try:
                    rng = int(m.group(1))
                except Exception:
                    continue
                source = str(name or "Closest eligible MONSTER/VEHICLE").strip() or "Closest eligible MONSTER/VEHICLE"
                rule = {
                    "range": rng,
                    "reroll_wound": bool(allow_wound),
                    "reroll_damage": bool(allow_damage),
                    "source": source,
                }
                break
        except Exception:
            rule = None

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = rule
        return rule

    def get_two_melee_weapons_attacks_bonus(self, model: Optional['Model'] = None) -> int:
        """
        Return the Attacks bonus for abilities like:
        "If this model is equipped with two melee weapons in addition to its close combat weapon,
        add 2 to the Attacks characteristic of those two weapons."
        """
        if model is None:
            return 0
        cache_key = f"two_melee_weapons_attacks_bonus:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            try:
                return int(self._ability_cache[cache_key] or 0)
            except Exception:
                return 0

        bonus = 0
        try:
            import re

            for name, desc in self._iter_model_specific_ability_entries(model):
                text = self._normalize_rules_text(f"{name} {desc}")
                if not text:
                    continue
                low = text.lower().replace("\u2019", "'")
                if "two melee weapons" not in low:
                    continue
                if "close combat weapon" not in low:
                    continue
                m = re.search(
                    r"add\s+(\d+)\s+to\s+the\s+attacks\s+characteristic\s+of\s+those\s+(?:two\s+)?weapons",
                    low,
                )
                if not m:
                    continue
                bonus = int(m.group(1))
                break
        except Exception:
            bonus = 0

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = int(bonus)
        return int(bonus)

    def get_two_melee_weapons_bonus(self, model: Optional['Model'] = None):
        """
        Return (bonus, eligible_wargear) for the two-melee-weapons clause.
        Bonus applies only if the model has a close combat weapon and exactly two other melee weapons.
        """
        if model is None:
            return 0, []
        bonus = int(self.get_two_melee_weapons_attacks_bonus(model) or 0)
        if bonus <= 0:
            return 0, []

        ccw_present = False
        eligible = []
        for wg in list(getattr(model, "wargear", []) or []):
            try:
                if not wg or not wg.is_melee():
                    continue
            except Exception:
                continue
            name_norm = self._norm_wargear_name(getattr(wg, "name", "") or "")
            if "close combat weapon" in name_norm:
                ccw_present = True
                continue
            eligible.append(wg)

        if not ccw_present or len(eligible) != 2:
            return 0, []
        return bonus, eligible

    def can_reroll_blood_surge_roll(self) -> bool:
        """Check for a leader-provided reroll to the Blood Surge D6 (e.g., Forwards, for Blood!)."""
        for t in self._iter_attached_leader_ability_texts():
            s = str(t or "").lower()
            if ("blood surge" in s) and ("re-roll" in s or "reroll" in s):
                return True
        for t in self._iter_active_ability_texts():
            s = str(t or "").lower()
            if ("blood surge" in s) and ("re-roll" in s or "reroll" in s):
                return True
        return False

    def _blood_surge_phase_key(self, game=None) -> str:
        if game is None:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        try:
            phase = getattr(game, "phase", None)
            pname = str(getattr(phase, "name", "") or phase or "").strip().upper()
        except Exception:
            pname = ""
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        owner = str(getattr(current_player, "name", "") or "")
        return f"{br}:{pname}:{owner}"

    def blood_surge_used_this_phase(self, game=None) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        key = self._blood_surge_phase_key(game)
        return str(sr.get("blood_surge_used_phase_key", "")) == key

    def mark_blood_surge_used(self, game=None) -> None:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["blood_surge_used_phase_key"] = self._blood_surge_phase_key(game)
        self.special_rules = sr

    def can_blood_surge(self, game=None, game_map=None) -> bool:
        if not self.has_blood_surge():
            return False
        if not self.is_alive() or not getattr(self, "deployed", False):
            return False
        if self.is_battle_shocked():
            return False
        if self.blood_surge_used_this_phase(game):
            return False
        if game_map is None:
            try:
                game_map = getattr(game, "map", None)
            except Exception:
                game_map = None
        if game_map is not None:
            try:
                for enemy in game_map.get_enemy_units(self):
                    if game_map.is_within_engagement_range(self, enemy):
                        return False
            except Exception:
                pass
        return True

    def has_reanimation_protocols(self) -> bool:
        """Check if the unit has Reanimation Protocols (Necrons army rule)."""
        if 'reanimation_protocols' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['reanimation_protocols']

        found, _ = self._find_ability_with_patterns(["reanimation protocols", "reanimation protocol"])

        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['reanimation_protocols'] = found
        return found

    def _normalize_rules_text(self, text: str) -> str:
        """Normalize Wahapedia-style text for rule pattern matching."""
        if not text:
            return ""
        # Strip HTML tags like <span class="kwb">CHARACTER</span>
        try:
            text = re.sub(r"<[^>]+>", " ", text)
        except Exception:
            pass
        # Normalize whitespace and punctuation spacing
        text = text.replace("\n", " ").replace("\r", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _strip_eligibility_prefix(text: str) -> str:
        """
        Strip Wahapedia-style eligibility prefixes like:
          "<KEYWORDS> model only. <rules text...>"
        """
        t = str(text or "")
        low = t.lower()
        for marker in (" model only.", " models only."):
            idx = low.find(marker)
            if idx != -1:
                return t[idx + len(marker):].strip()
        return t

    @staticmethod
    def _parse_move_types_from_text(value: str) -> set[str]:
        """Parse movement type tokens (normal/advance/fall back/charge) from a text fragment."""
        types: set[str] = set()
        if not value:
            return types
        low = str(value).lower()
        if "normal" in low:
            types.add("move")
        if "advance" in low:
            types.add("advance")
        if "fall back" in low or "fallback" in low:
            types.add("fall_back")
        if "charge" in low:
            types.add("charge")
        return types

    def _iter_ability_entries_for_rules(self, model: Optional['Model'] = None):
        """Yield (name, description) pairs for unit/model abilities."""
        # Unit-level abilities
        for a in self._iter_active_possible_abilities():
            if isinstance(a, str):
                yield a, a
            else:
                yield getattr(a, "name", "") or "", getattr(a, "description", "") or ""

        # Model-level abilities (if provided)
        if model is not None:
            try:
                for a in getattr(model, "abilities", {}).values():
                    if isinstance(a, str):
                        if self._ability_is_active(a):
                            yield a, a
                    else:
                        if self._ability_is_active(a):
                            yield getattr(a, "name", "") or "", getattr(a, "description", "") or ""
            except Exception:
                pass

    def _iter_model_specific_ability_entries(self, model: Optional['Model'] = None):
        """
        Yield (name, description) pairs for model-specific rules.

        - Always includes model-level abilities (if provided).
        - Includes unit-level abilities only when the unit is a single-model unit.
        """
        if model is None:
            return
        try:
            if len(getattr(self, "models", []) or []) <= 1:
                for a in self._iter_active_possible_abilities():
                    if isinstance(a, str):
                        yield a, a
                    else:
                        yield getattr(a, "name", "") or "", getattr(a, "description", "") or ""
        except Exception:
            pass
        try:
            for a in getattr(model, "abilities", {}).values():
                try:
                    if not self._ability_is_active(a):
                        continue
                except Exception:
                    pass
                if isinstance(a, str):
                    yield a, a
                else:
                    yield getattr(a, "name", "") or "", getattr(a, "description", "") or ""
        except Exception:
            pass

    def model_can_reroll_wound_vs_character(self, model: Optional['Model'] = None) -> tuple[bool, Optional[str]]:
        """
        Model-specific rule: re-roll the Wound roll vs CHARACTER targets.

        Returns (allowed, reason_name).
        """
        if model is None:
            return False, None
        cache_key = f"model_reroll_wound_vs_character:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        allowed = False
        reason = None
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            for rule in self._parse_attack_roll_rules_from_text(text_src):
                if rule.subject not in ("this_model", "model_in_this_unit"):
                    continue
                for eff in rule.effects:
                    if eff.roll != "wound" or eff.kind != "reroll" or not eff.reroll_full:
                        continue
                    cond = eff.condition
                    if not cond or (
                        "character" not in set(cond.target_keywords_any or ())
                        and "character" not in set(cond.target_keywords_all or ())
                    ):
                        continue
                    allowed = True
                    reason = str(name or "Model ability")
                    break
                if allowed:
                    break
            if allowed:
                break

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = (allowed, reason)
        return allowed, reason

    def model_can_reroll_hit_vs_character(self, model: Optional['Model'] = None) -> tuple[bool, Optional[str]]:
        """
        Model-specific rule: re-roll the Hit roll vs CHARACTER targets.

        Returns (allowed, reason_name).
        """
        if model is None:
            return False, None
        cache_key = f"model_reroll_hit_vs_character:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        allowed = False
        reason = None
        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            for rule in self._parse_attack_roll_rules_from_text(text_src):
                if rule.subject not in ("this_model", "model_in_this_unit"):
                    continue
                for eff in rule.effects:
                    if eff.roll != "hit" or eff.kind != "reroll" or not eff.reroll_full:
                        continue
                    cond = eff.condition
                    if not cond or (
                        "character" not in set(cond.target_keywords_any or ())
                        and "character" not in set(cond.target_keywords_all or ())
                    ):
                        continue
                    allowed = True
                    reason = str(name or "Model ability")
                    break
                if allowed:
                    break
            if allowed:
                break

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = (allowed, reason)
        return allowed, reason

    def model_hit_bonus_vs_fly(self, model: Optional['Model'] = None, *, attack_type: str = "any") -> tuple[int, Optional[str]]:
        """
        Model-specific rule: +N to Hit rolls vs targets that can FLY.

        Returns (bonus, reason_name).
        """
        if model is None:
            return 0, None
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"
        cache_key = f"model_hit_bonus_vs_fly:{get_entity_id(model)}:{atype}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return self._ability_cache[cache_key]

        bonus = 0
        reason = None

        def _fly_only_condition(cond: Optional[AttackRollCondition]) -> bool:
            if cond is None:
                return False
            if cond.target_can_fly is not True:
                return False
            if cond.attacker_below_starting_strength or cond.attacker_below_half_strength:
                return False
            if cond.target_battleshocked or cond.target_within_objective or cond.target_within_range is not None:
                return False
            if cond.target_keywords_any or cond.target_keywords_all or cond.target_exclude_keywords_any:
                return False
            if cond.target_below_starting_strength:
                return False
            if cond.target_below_half_strength:
                return False
            return True

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            for rule in self._parse_attack_roll_rules_from_text(text_src):
                if rule.subject not in ("this_model", "model_in_this_unit"):
                    continue
                if atype != "any" and rule.attack_type not in ("any", atype):
                    continue
                for eff in rule.effects:
                    if eff.roll != "hit" or eff.kind != "add":
                        continue
                    if not _fly_only_condition(eff.condition):
                        continue
                    try:
                        val = int(eff.value or 0)
                    except Exception:
                        val = 0
                    if val:
                        bonus = val
                        reason = str(name or "Model ability")
                        break
                if bonus:
                    break
            if bonus:
                break

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = (bonus, reason)
        return bonus, reason

    def _get_model_attack_roll_rules(self, model: Optional['Model'] = None) -> list[tuple['AttackRollRule', str]]:
        if model is None:
            return []
        cache_key = f"model_attack_roll_rules:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        rules: list[tuple[AttackRollRule, str]] = []
        seen_names: set[str] = set()
        for name, desc in self._iter_model_specific_ability_entries(model):
            try:
                ability_name = str(name or "").replace("\u2019", "'").strip()
            except Exception:
                ability_name = ""
            name_key = ability_name.lower().strip()
            if name_key and name_key in seen_names:
                continue
            if name_key:
                seen_names.add(name_key)
            text_src = desc or name or ""
            for rule in self._parse_attack_roll_rules_from_text(text_src):
                if rule.subject != "this_model":
                    continue
                rules.append((rule, ability_name or "Model ability"))

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(rules)
        return list(rules)

    def model_attack_roll_modifiers_vs_weakened_target(
        self,
        model: Optional['Model'] = None,
        *,
        attack_type: str = "any",
        target: Optional['Unit'] = None,
    ) -> dict:
        """
        Model-specific rule: add to Hit/Wound rolls vs targets below Starting Strength/Half-strength.
        """
        mods = {
            "hit": 0,
            "wound": 0,
            "hit_reasons": (),
            "wound_reasons": (),
        }
        if model is None:
            return mods
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        rules = self._get_model_attack_roll_rules(model)
        if not rules:
            return mods

        hit_reasons: list[str] = []
        wound_reasons: list[str] = []

        def _cond_suffix(cond: Optional[AttackRollCondition]) -> str:
            if not cond:
                return ""
            parts = []
            if cond.target_battleshocked:
                parts.append("vs Battle-shocked targets")
            if cond.attacker_below_starting_strength:
                parts.append("while below Starting Strength")
            if cond.attacker_below_half_strength:
                parts.append("while below Half-strength")
            if cond.target_within_objective:
                parts.append("vs targets within objective range")
            if cond.target_within_range is not None:
                parts.append(f"vs targets within {cond.target_within_range}\"")
            if cond.target_can_fly is True:
                parts.append("vs FLY targets")
            if cond.target_can_fly is False:
                parts.append("vs non-FLY targets")
            if cond.target_keywords_any:
                if set(cond.target_keywords_any) == {"character"}:
                    parts.append("vs CHARACTER targets")
                elif set(cond.target_keywords_any) == {"monster", "vehicle"}:
                    parts.append("vs MONSTER/VEHICLE targets")
            if cond.target_below_starting_strength:
                parts.append("vs targets below Starting Strength")
            if cond.target_below_half_strength:
                parts.append("vs targets below Half-strength")
            if cond.target_exclude_keywords_any:
                parts.append("excluding " + ", ".join(cond.target_exclude_keywords_any))
            if not parts:
                return ""
            return " (" + "; ".join(parts) + ")"

        for rule, name in list(rules or []):
            if atype != "any" and rule.attack_type not in ("any", atype):
                continue
            if rule.scope == "leading" and not bool(getattr(self, "is_attached_leader", False)):
                continue
            for eff in rule.effects:
                if eff.roll not in ("hit", "wound"):
                    continue
                if eff.kind not in ("add", "sub"):
                    continue
                cond = eff.condition
                if not cond or not (cond.target_below_starting_strength or cond.target_below_half_strength):
                    continue
                if not self._attack_condition_met(cond, target=target, source_unit=root):
                    continue
                try:
                    val = int(eff.value or 0)
                except Exception:
                    val = 0
                if eff.kind == "sub":
                    val = -val
                if not val:
                    continue
                label = name or "Model ability"
                if eff.roll == "hit":
                    mods["hit"] += val
                    hit_reasons.append(f"{val:+d} to hit from {label}{_cond_suffix(cond)}")
                else:
                    mods["wound"] += val
                    wound_reasons.append(f"{val:+d} to wound from {label}{_cond_suffix(cond)}")

        mods["hit_reasons"] = tuple(hit_reasons)
        mods["wound_reasons"] = tuple(wound_reasons)
        return mods

    def model_post_shoot_battleshock_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has shot, select a hit enemy unit to take a Battle-shock test.

        Returns a list of specs with keys:
            - infantry_only: bool
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, bool]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_BATTLESHOCK_RE.fullmatch(normalized)
            if not m:
                continue
            infantry_only = bool(m.group("infantry"))
            source = str(name or "Post-shoot Battle-shock").strip() or "Post-shoot Battle-shock"
            key = (source.lower(), infantry_only)
            if key in seen:
                continue
            seen.add(key)
            specs.append({"infantry_only": infantry_only, "source": source})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_post_shoot_suppression_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: after this model has shot, select a hit enemy unit to become suppressed.

        Returns a list of specs with keys:
            - exclude_monster_vehicle: bool
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_post_shoot_suppression:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple[str, bool]] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._POST_SHOOT_SUPPRESSION_RE.fullmatch(normalized)
            if not m:
                continue
            exclude_mv = bool(m.group("exclude")) or ("excluding monsters and vehicles" in normalized)
            source = str(name or "Post-shoot Suppression").strip() or "Post-shoot Suppression"
            key = (source.lower(), exclude_mv)
            if key in seen:
                continue
            seen.add(key)
            specs.append({"exclude_monster_vehicle": exclude_mv, "source": source})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_start_fight_phase_engagement_battleshock_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: at the start of the Fight phase, enemies in engagement range test Battle-shock.

        Returns a list of specs with keys:
            - source: ability name
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_engagement_battleshock:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._FIGHT_PHASE_ENGAGEMENT_BATTLESHOCK_RE.fullmatch(normalized):
                continue
            source = str(name or "Fight phase Battle-shock").strip() or "Fight phase Battle-shock"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append({"source": source})

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_end_fight_phase_engagement_mortal_wounds_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Fight phase, select an engaged enemy and roll eight D6 for mortal wounds.

        Returns a list of specs with keys:
            - source: ability name
            - dice: int
            - threshold: int
            - mortal_per_success: int
        """
        if model is None:
            return []
        cache_key = f"model_fight_phase_end_mortal_wounds:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[str] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not self._FIGHT_PHASE_END_ENGAGEMENT_MORTAL_EIGHT_D6_RE.fullmatch(normalized):
                continue
            source = str(name or "Fight phase mortals").strip() or "Fight phase mortals"
            key = source.lower()
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "dice": 8,
                    "threshold": 4,
                    "mortal_per_success": 1,
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def model_move_over_mortal_wounds_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """
        Model-specific rule: end of Normal/Advance move, select an enemy unit moved over and roll D6s for mortals.

        Returns a list of specs with keys:
            - source: ability name
            - dice: int
            - threshold: int
            - mortal_per_success: int
            - move_types: list[str] (e.g., ["move", "advance"])
            - exclude_monster_vehicle: bool
        """
        if model is None:
            return []
        cache_key = f"model_move_over_mortal_wounds:{get_entity_id(model)}"
        if cache_key in getattr(self, "_ability_cache", {}):
            return list(self._ability_cache[cache_key])

        specs: list[dict] = []
        seen: set[tuple] = set()

        for name, desc in self._iter_model_specific_ability_entries(model):
            text_src = desc or name or ""
            if not text_src:
                continue
            text_src = self._strip_eligibility_prefix(text_src)
            normalized = self._normalize_rules_text(text_src)
            if not normalized:
                continue
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9+]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if "moved over" not in normalized or "mortal wound" not in normalized:
                continue
            if "for each model" in normalized:
                continue
            if "one of the following" in normalized:
                continue

            m = self._MOVE_OVER_MORTAL_WOUNDS_RE.fullmatch(normalized)
            if not m:
                continue

            moves_text = (m.group("moves") or "").strip()
            move_types = self._parse_move_types_from_text(moves_text)
            if "move" not in move_types:
                continue
            if not move_types.issubset({"move", "advance"}):
                continue

            dice_raw = (m.group("dice") or "").strip().lower()
            dice_count = None
            if dice_raw.isdigit():
                dice_count = int(dice_raw)
            else:
                dice_count = self._NUMBER_WORDS.get(dice_raw)
            if not dice_count or dice_count <= 0:
                continue
            try:
                threshold = int(m.group("threshold") or 0)
            except Exception:
                threshold = 0
            try:
                mortal_per = int(m.group("mw") or 0)
            except Exception:
                mortal_per = 0
            if threshold <= 0 or mortal_per <= 0:
                continue

            exclude_mv = "excluding monsters and vehicles" in normalized or "excluding monster and vehicle" in normalized
            source = str(name or "Move-over mortals").strip() or "Move-over mortals"
            key = (
                source.lower(),
                int(dice_count),
                int(threshold),
                int(mortal_per),
                tuple(sorted(move_types)),
                bool(exclude_mv),
            )
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "source": source,
                    "dice": int(dice_count),
                    "threshold": int(threshold),
                    "mortal_per_success": int(mortal_per),
                    "move_types": sorted(move_types),
                    "exclude_monster_vehicle": bool(exclude_mv),
                }
            )

        if not hasattr(self, "_ability_cache"):
            self._ability_cache = {}
        self._ability_cache[cache_key] = list(specs)
        return list(specs)

    def get_target_hit_roll_penalty(
        self,
        attack_type: str,
        target_model: Optional['Model'] = None,
    ) -> tuple[int, tuple[str, ...]]:
        """
        Return total penalties to Hit rolls for attacks that target this unit/model.

        Supports strict patterns:
        - Each time an attack targets this unit/model, subtract 1 from the Hit roll.
        - Each time a melee/ranged attack targets this unit/model, subtract 1 from the Hit roll.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"

        model_key = getattr(target_model, "_id", None) if target_model is not None else "unit"
        cache_key = f"target_hit_penalty:{atype}:{model_key}"
        if cache_key in getattr(root, "_ability_cache", {}):
            return root._ability_cache[cache_key]

        penalty = 0
        reasons: list[str] = []
        seen: set[str] = set()

        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict):
            entries = sr.get("bearer_unit_target_hit_penalties")
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        at = str(entry.get("attack_type", "any") or "any").lower()
                        val = int(entry.get("value", 1) or 1)
                        src = str(entry.get("source", "") or "Bearer unit ability").strip() or "Bearer unit ability"
                    elif isinstance(entry, (list, tuple)):
                        at = "any"
                        val = int(entry[0]) if entry else 1
                        src = str(entry[1]) if len(entry) > 1 else "Bearer unit ability"
                    else:
                        continue
                    if atype != "any" and at not in ("any", atype):
                        continue
                    key = f"bearer_unit:{src.lower()}"
                    if key in seen:
                        continue
                    seen.add(key)
                    penalty += int(val)
                    reasons.append(f"-{val} to hit from {src}")

        def _match_entries(entries, scope_key: str) -> None:
            nonlocal penalty
            for name, desc in entries:
                text_src = desc or name or ""
                if not text_src:
                    continue
                for rule in self._parse_attack_roll_rules_from_text(text_src):
                    if rule.scope != "defensive":
                        continue
                    if atype != "any" and rule.attack_type not in ("any", atype):
                        continue
                    reason_name = str(name or "Ability").strip() or "Ability"
                    key = f"{scope_key}:{reason_name.lower()}"
                    if key in seen:
                        break
                    for eff in rule.effects:
                        if eff.roll != "hit" or eff.kind != "sub":
                            continue
                        if eff.condition and not self._attack_condition_met(eff.condition, target=root, source_unit=root):
                            continue
                        val = int(eff.value or 0)
                        if val <= 0:
                            continue
                        seen.add(key)
                        penalty += val
                        reasons.append(f"-{val} to hit from {reason_name}")
                        break
                    if key in seen:
                        break

        unit_entries = []
        for ab in root._iter_active_possible_abilities():
            if isinstance(ab, str):
                unit_entries.append((ab, ab))
            else:
                unit_entries.append((getattr(ab, "name", "") or "", getattr(ab, "description", "") or ""))
        _match_entries(unit_entries, "unit")

        model = target_model
        if model is None:
            try:
                models = list(getattr(root, "models", []) or [])
            except Exception:
                models = []
            if len(models) == 1:
                model = models[0]
        if model is not None:
            model_entries = list(root._iter_model_specific_ability_entries(model))
            _match_entries(model_entries, "model")

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = (int(penalty), tuple(reasons))
        return int(penalty), tuple(reasons)

    def _parse_phase_end_leadership_cp_gain_specs_from_text(self, ability_name: str, ability_desc: str) -> List[dict]:
        """Parse end-of-phase Leadership test CP gain abilities."""
        normalized = self._normalize_rules_text(ability_desc)
        if not normalized:
            return []
        norm = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
        norm = norm.lower()
        norm = re.sub(r"'s\b", "s", norm)
        norm = re.sub(r"[^a-z0-9]+", " ", norm)
        norm = re.sub(r"\s+", " ", norm).strip()
        m = self._PHASE_END_LEADERSHIP_CP_GAIN_RE.fullmatch(norm)
        if not m:
            return []
        token = str(m.group("cp") or "").strip().lower()
        try:
            cp = int(token)
        except Exception:
            cp = 1 if token == "one" else 1
        return [
            {
                "type": "phase_end_leadership_cp_gain",
                "cp": int(cp),
                "source_ability": ability_name or "",
            }
        ]

    def get_phase_end_leadership_cp_gain_specs(self) -> List[dict]:
        """Return end-of-phase Leadership test CP gain specs for this unit group."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "phase_end_leadership_cp_gain_specs"
        if cache_key in getattr(root, "_ability_cache", {}):
            return list(root._ability_cache[cache_key])

        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        specs: List[dict] = []
        seen = set()
        for unit in members:
            if unit is None:
                continue
            for name, desc in unit._iter_ability_entries_for_rules(model=None):
                text_src = unit._strip_eligibility_prefix(desc or name or "")
                parsed = unit._parse_phase_end_leadership_cp_gain_specs_from_text(name, text_src)
                for spec in parsed:
                    key = (spec.get("source_ability", "").lower(), int(spec.get("cp", 1) or 1))
                    if key in seen:
                        continue
                    seen.add(key)
                    specs.append(spec)

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = list(specs)
        return list(specs)

    def _parse_cp_on_kill_specs_from_text(self, ability_name: str, ability_desc: str) -> List[dict]:
        """Parse partial support for 'gain CP when destroying enemy keyword unit/model' abilities.

        This intentionally focuses on broad, extendible text patterns rather than specific names.
        """
        normalized = self._normalize_rules_text(ability_desc)
        txt = normalized.lower()

        # Must look like a 'destroy' trigger and reference CP gain.
        if "gain" not in txt or "cp" not in txt:
            return []
        if "destroys" not in txt:
            return []

        # Extract CP amount (default 1 if implied)
        cp = 1
        try:
            m = re.search(r"gain\s+(\d+)\s*cp", txt, flags=re.IGNORECASE)
            if m:
                cp = int(m.group(1))
        except Exception:
            cp = 1

        # Keyword extraction (extendible)
        keyword_map = {
            "character": "CHARACTER",
            "epic hero": "EPIC HERO",
            "monster": "MONSTER",
            "vehicle": "VEHICLE",
            "psyker": "PSYKER",
        }

        if "enemy" not in txt:
            has_keyword = any(needle in txt for needle in keyword_map)
            if not has_keyword:
                return []

        # Detect what is being destroyed: unit vs model (defaults to model_destroyed)
        trigger = "model_destroyed"
        try:
            # If text explicitly says "... destroys an enemy <X> unit", use unit_destroyed
            if re.search(r"destroys\s+an?\s+(?:enemy\s+)?\b.*\bunit\b", txt):
                trigger = "unit_destroyed"
            # If it explicitly says model, prefer model_destroyed
            if re.search(r"destroys\s+an?\s+(?:enemy\s+)?\b.*\bmodel\b", txt):
                trigger = "model_destroyed"
        except Exception:
            trigger = "model_destroyed"

        # Restriction extraction (extendible)
        requires_melee = False
        try:
            # e.g. "with a melee attack"
            if "melee attack" in txt or "with a melee" in txt:
                requires_melee = True
        except Exception:
            requires_melee = False

        target_keywords = []
        for needle, kw in keyword_map.items():
            if needle in txt:
                target_keywords.append(kw)

        # Determine keyword match mode. If multiple keywords are mentioned and "or" appears,
        # treat as ANY. Otherwise default to ALL.
        target_keyword_mode = "all"
        try:
            if len(target_keywords) > 1 and " or " in txt:
                target_keyword_mode = "any"
        except Exception:
            target_keyword_mode = "all"

        return [{
            "type": "gain_cp_on_destroy",
            "trigger": trigger,
            "cp": cp,
            # empty set means "any target" (e.g. The Great Wolf)
            "target_keywords": set(target_keywords),
            "target_keyword_mode": target_keyword_mode,
            "requires_melee": requires_melee,
            "source_ability": ability_name or "",
        }]

    def _parse_heal_on_kill_specs_from_text(self, ability_name: str, ability_desc: str) -> List[dict]:
        """Parse partial support for 'regain wounds when destroying enemy keyword unit/model' abilities."""
        normalized = self._normalize_rules_text(ability_desc)
        txt = normalized.lower()

        if "destroys" not in txt or "enemy" not in txt:
            return []
        if "regains" not in txt or "lost wounds" not in txt:
            return []

        # Determine trigger (unit vs model). Default to unit_destroyed if "unit" appears near destroy.
        trigger = "model_destroyed"
        try:
            if re.search(r"destroys\s+an?\s+enemy\b.*\bunit\b", txt):
                trigger = "unit_destroyed"
            if re.search(r"destroys\s+an?\s+enemy\b.*\bmodel\b", txt):
                trigger = "model_destroyed"
        except Exception:
            trigger = "unit_destroyed"

        # Parse heal amount expression (e.g. D6, D3, 3)
        heal_expr = None
        try:
            m = re.search(r"regains\s+up\s+to\s+(\d+|d\d+)\s+lost wounds", txt, flags=re.IGNORECASE)
            if m:
                heal_expr = m.group(1).upper()
        except Exception:
            heal_expr = None
        if not heal_expr:
            return []

        requires_melee = False
        try:
            if "melee attack" in txt or "with a melee" in txt:
                requires_melee = True
        except Exception:
            requires_melee = False

        keyword_map = {
            "character": "CHARACTER",
            "epic hero": "EPIC HERO",
            "monster": "MONSTER",
            "vehicle": "VEHICLE",
            "psyker": "PSYKER",
        }
        target_keywords = []
        for needle, kw in keyword_map.items():
            if needle in txt:
                target_keywords.append(kw)

        # If there are no keywords, we can't safely implement the intent.
        if not target_keywords:
            return []

        target_keyword_mode = "all"
        try:
            # Champion Slayer: "CHARACTER or MONSTER"
            if len(target_keywords) > 1 and " or " in txt:
                target_keyword_mode = "any"
        except Exception:
            target_keyword_mode = "all"

        return [{
            "type": "heal_on_destroy",
            "trigger": trigger,
            "heal_expr": heal_expr,
            "target_keywords": set(target_keywords),
            "target_keyword_mode": target_keyword_mode,
            "requires_melee": requires_melee,
            "source_ability": ability_name or "",
        }]

    def get_kill_reward_specs(self, model: Optional['Model'] = None) -> List[dict]:
        """Return parsed 'on destroy' reward specs for this unit (and optionally a specific model).

        Used by the event system to support abilities like Trophy Taker / Feeder Tendrils /
        Skulls for Khorne / The Great Wolf / Feared Interrogator / Champion Slayer (partial support).
        """
        # Cache unit-level specs (model-specific specs are not cached here)
        cache_key = "kill_reward_specs_base"
        if cache_key in getattr(self, "_ability_cache", {}):
            base_specs = self._ability_cache[cache_key]
        else:
            base_specs: List[dict] = []
            for n, d in self._iter_ability_entries_for_rules(model=None):
                base_specs.extend(self._parse_cp_on_kill_specs_from_text(n, d))
                base_specs.extend(self._parse_heal_on_kill_specs_from_text(n, d))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache[cache_key] = base_specs

        # Add model-specific specs (if any)
        if model is None:
            return list(base_specs)

        model_specs: List[dict] = []
        for n, d in self._iter_ability_entries_for_rules(model=model):
            # Avoid double-counting unit-level entries by only parsing model abilities here.
            # We already parsed unit-level in base_specs.
            if n and any(s.get("source_ability") == n for s in base_specs):
                continue
            model_specs.extend(self._parse_cp_on_kill_specs_from_text(n, d))
            model_specs.extend(self._parse_heal_on_kill_specs_from_text(n, d))

        return list(base_specs) + model_specs
    
    def is_eligible_to_fight(self, game_map: 'Map') -> bool:
        """Check if the unit is eligible to fight in the Fight Phase.
        
        A unit is eligible to fight if:
        a) it is within engagement range of one or more enemy units, OR
        b) it made a charge move this turn (current player's turn)
        
        Args:
            game_map: The game map to check for enemy units and engagement range
            
        Returns:
            bool: True if the unit is eligible to fight
        """
        if not self.is_alive() or not self.deployed:
            return False
        
        # Check if unit charged this turn - units that charged can always fight
        if self.round_state.charged_this_round:
            return True
        
        # Check if unit is within engagement range of any enemy unit
        enemy_units = game_map.get_enemy_units(self)
        for enemy_unit in enemy_units:
            if not enemy_unit.is_alive():
                continue
            if not game_map.is_within_engagement_range(self, enemy_unit):
                continue
            try:
                if bool(getattr(self, "is_aircraft", False)):
                    if bool(getattr(enemy_unit, "is_flying", False)):
                        return True
                    continue
                if bool(getattr(enemy_unit, "is_aircraft", False)) and not bool(getattr(self, "is_flying", False)):
                    continue
            except Exception:
                pass
            return True
        
        return False

    def has_fight_within_3_ability(self) -> bool:
        """Return True if this unit has a 'fight within 3\"' eligibility ability."""
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and sr.get("fight_within_3"):
            return True
        return False

    def get_fight_within_3_sources(self) -> list[str]:
        """Return ability names that grant fight-within-3\" eligibility."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return []
        specs = sr.get("fight_within_3", []) or []
        names = []
        for item in specs:
            if isinstance(item, dict):
                name = str(item.get("name", "") or "").strip()
            else:
                name = str(item or "").strip()
            if name:
                names.append(name)
        return names

    def fight_within_3_active(self) -> bool:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        return bool(sr.get("fight_within_3_active", False))

    def set_fight_within_3_active(self, active: bool, source: str | None = None) -> None:
        if getattr(self, "special_rules", None) is None:
            self.special_rules = {}
        sr = self.special_rules
        if bool(active):
            sr["fight_within_3_active"] = True
            if source:
                sr["fight_within_3_active_source"] = str(source)
        else:
            if "fight_within_3_active" in sr:
                del sr["fight_within_3_active"]
            if "fight_within_3_active_source" in sr:
                del sr["fight_within_3_active_source"]
        self.special_rules = sr

    def clear_fight_within_3_active(self) -> None:
        self.set_fight_within_3_active(False)

    def _model_within_engagement_range_of_unit(self, model, target_unit) -> bool:
        try:
            from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
            from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
        except Exception:
            return False
        try:
            target_models = list(target_unit.get_models_for_collision() or [])
        except Exception:
            target_models = list(getattr(target_unit, "models", []) or [])
        for tm in target_models:
            try:
                if not getattr(tm, "is_alive", False):
                    continue
            except Exception:
                pass
            try:
                hd = float(horizontal_distance_between_bases_2d(model.model_base, tm.model_base))
                vd = float(vertical_distance_between_bases(model.model_base, tm.model_base))
            except Exception:
                continue
            if hd <= ENGAGEMENT_RANGE_HORIZONTAL and vd <= ENGAGEMENT_RANGE_VERTICAL:
                return True
        return False

    def _model_within_range_of_unit(self, model, target_unit, radius: float) -> bool:
        try:
            from ..utility.aura_utils import distance_between_models_bases_3d
        except Exception:
            return False
        try:
            target_models = list(target_unit.get_models_for_collision() or [])
        except Exception:
            target_models = list(getattr(target_unit, "models", []) or [])
        for tm in target_models:
            try:
                if not getattr(tm, "is_alive", False):
                    continue
            except Exception:
                pass
            try:
                if float(distance_between_models_bases_3d(model, tm)) <= float(radius) + 1e-6:
                    return True
            except Exception:
                continue
        return False

    def get_fight_eligible_models_for_target(self, target_unit, game_map: Optional['Map'] = None, *, allow_within_3: Optional[bool] = None) -> list:
        """Return models in this unit eligible to fight the given target unit."""
        try:
            models = list(self.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(self, "models", []) or [])
        models = [m for m in models if bool(getattr(m, "is_alive", True))]
        if not models or target_unit is None:
            return []

        if not self.has_fight_within_3_ability():
            return list(models)

        if game_map is None:
            return list(models)

        try:
            if not game_map.is_within_engagement_range(self, target_unit):
                return []
        except Exception:
            return []

        if allow_within_3 is None:
            allow_within_3 = self.fight_within_3_active()

        eligible = []
        for model in models:
            if self._model_within_engagement_range_of_unit(model, target_unit):
                eligible.append(model)
                continue
            if allow_within_3 and self._model_within_range_of_unit(model, target_unit, 3.0):
                eligible.append(model)
        return eligible

    def _charge_bonus_suppressed_key(self, game=None) -> tuple[int, str]:
        if game is None:
            try:
                game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
            owner = str(getattr(current_player, "id", "") or "")
        except Exception:
            owner = ""
        return turn, owner

    def mark_charge_bonus_suppressed(self, game=None) -> None:
        turn, owner = self._charge_bonus_suppressed_key(game)
        try:
            self.round_state.charge_bonus_suppressed_turn = int(turn or 0)
        except Exception:
            self.round_state.charge_bonus_suppressed_turn = int(turn or 0)
        try:
            self.round_state.charge_bonus_suppressed_turn_owner = str(owner or "")
        except Exception:
            self.round_state.charge_bonus_suppressed_turn_owner = str(owner or "")

    def charge_bonus_suppressed(self, game=None) -> bool:
        try:
            sup_turn = int(getattr(self.round_state, "charge_bonus_suppressed_turn", 0) or 0)
        except Exception:
            sup_turn = 0
        try:
            sup_owner = str(getattr(self.round_state, "charge_bonus_suppressed_turn_owner", "") or "")
        except Exception:
            sup_owner = ""
        if not sup_turn or not sup_owner:
            return False
        turn, owner = self._charge_bonus_suppressed_key(game)
        return sup_turn == int(turn or 0) and sup_owner == str(owner or "")
    
    def should_fight_first(self) -> bool:
        """Check if this unit should fight in the Fight First stage.
        
        Units fight first if they:
        1. Have an inherent Fight First ability, OR
        2. Charged this turn
        
        Returns:
            bool: True if the unit should fight in the Fight First stage
        """
        if self._seductive_gambit_active():
            return False
        # Units that charged this turn fight first
        game = None
        try:
            game = getattr(getattr(self.get_parent_army(), "player", None), "game", None)
        except Exception:
            game = None
        if self.round_state.charged_this_round and not self.charge_bonus_suppressed(game):
            return True
            
        # Units with Fight First abilities fight first
        if self.has_fight_first():
            return True
        
        return False
    
    def has_deadly_demise(self) -> Tuple[bool, DiceCollection]:
        """Check if the unit has Deadly Demise ability and return the damage value.
        
        Returns:
            Tuple[bool, DiceCollection]: A tuple containing:
                - A boolean indicating if the unit has Deadly Demise ability
                - A DiceCollection object representing the damage value (e.g., "3", "D3", "D6") or None if no Deadly Demise ability
        """
        # Use cached result if available
        if 'deadly_demise' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['deadly_demise']
        
        found, damage_str = self._find_ability_with_patterns(["deadly demise"], extract_value=True, value_pattern=r'(\d+|D\d+)')
        if found:
            try:
                dice_collection = DiceCollection.from_string(damage_str)
                result = (True, dice_collection)
            except ValueError:
                raise ValueError(f"Deadly Demise ability found but could not parse damage value '{damage_str}' for unit '{self.name}'")
        else:
            result = (False, None)
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['deadly_demise'] = result
        
        return result

    def _find_all_abilities_with_patterns(self, patterns: List[str], value_pattern: str) -> List[Tuple[int, Optional[str]]]:
        """
        Helper method to find all instances of abilities matching given patterns and extract values with conditions.
        Used specifically for Feel No Pain which can have multiple instances with conditions.
        
        Args:
            patterns: List of patterns to search for (case-insensitive)
            value_pattern: Regex pattern to extract value and optional condition
        
        Returns:
            List[Tuple[int, Optional[str]]]: List of (dice_value, condition) tuples
        """
        found_abilities = []
        
        # Check keywords first
        for keyword in self.keywords:
            for pattern in patterns:
                if pattern.lower() in keyword.lower():
                    match = re.search(value_pattern, keyword.lower())
                    if match:
                        dice_value = int(match.group(1))
                        condition = match.group(2).strip() if match.group(2) else None
                        found_abilities.append((dice_value, condition))
                    else:
                        raise ValueError(f"{pattern} ability found in keyword '{keyword}' but could not extract dice value for unit '{self.name}'")
        
        # Check unit-level abilities (possible_abilities)
        for ability in self._iter_active_possible_abilities():
            if isinstance(ability, str):
                for pattern in patterns:
                    if pattern.lower() in ability.lower():
                        match = re.search(value_pattern, ability.lower())
                        if match:
                            dice_value = int(match.group(1))
                            condition = match.group(2).strip() if match.group(2) else None
                            found_abilities.append((dice_value, condition))
                        else:
                            raise ValueError(f"{pattern} ability found in ability string '{ability}' but could not extract dice value for unit '{self.name}'")
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, 'name') and ability.name:
                    for pattern in patterns:
                        if pattern.lower() in ability.name.lower():
                            ability_name_matched = True
                            match = re.search(value_pattern, ability.name.lower())
                            if match:
                                dice_value = int(match.group(1))
                                condition = match.group(2).strip() if match.group(2) else None
                                found_abilities.append((dice_value, condition))
                            else:
                                # Check if ability has a parameter attribute (e.g., "5+")
                                if hasattr(ability, 'parameter') and ability.parameter:
                                    param_match = re.search(r'(\d+)\+', ability.parameter)
                                    if param_match:
                                        dice_value = int(param_match.group(1))
                                        found_abilities.append((dice_value, None))
                                    else:
                                        raise ValueError(f"{pattern} ability found in ability name '{ability.name}' with parameter '{ability.parameter}' but could not extract dice value for unit '{self.name}'")
                                else:
                                    raise ValueError(f"{pattern} ability found in ability name '{ability.name}' but could not extract dice value for unit '{self.name}'")
                
                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, 'description') and ability.description:
                    desc_text = self._normalize_rules_text(ability.description)
                    for pattern in patterns:
                        if pattern.lower() in desc_text.lower():
                            match = re.search(value_pattern, desc_text.lower())
                            if match:
                                dice_value = int(match.group(1))
                                condition = match.group(2).strip() if match.group(2) else None
                                found_abilities.append((dice_value, condition))
                            else:
                                raise ValueError(f"{pattern} ability found in ability description '{ability.description}' but could not extract dice value for unit '{self.name}'")
        
        # Check model-level abilities
        for ability in self.abilities:
            try:
                if not self._ability_is_active(ability):
                    continue
            except Exception:
                pass
            if isinstance(ability, str):
                for pattern in patterns:
                    if pattern.lower() in ability.lower():
                        match = re.search(value_pattern, ability.lower())
                        if match:
                            dice_value = int(match.group(1))
                            condition = match.group(2).strip() if match.group(2) else None
                            found_abilities.append((dice_value, condition))
                        else:
                            raise ValueError(f"{pattern} ability found in model ability string '{ability}' but could not extract dice value for unit '{self.name}'")
            else:
                # Ability object with name and description attributes
                ability_name_matched = False
                if hasattr(ability, 'name') and ability.name:
                    for pattern in patterns:
                        if pattern.lower() in ability.name.lower():
                            ability_name_matched = True
                            match = re.search(value_pattern, ability.name.lower())
                            if match:
                                dice_value = int(match.group(1))
                                condition = match.group(2).strip() if match.group(2) else None
                                found_abilities.append((dice_value, condition))
                            else:
                                # Check if ability has a parameter attribute (e.g., "5+")
                                if hasattr(ability, 'parameter') and ability.parameter:
                                    param_match = re.search(r'(\d+)\+', ability.parameter)
                                    if param_match:
                                        dice_value = int(param_match.group(1))
                                        found_abilities.append((dice_value, None))
                                    else:
                                        raise ValueError(f"{pattern} ability found in model ability name '{ability.name}' with parameter '{ability.parameter}' but could not extract dice value for unit '{self.name}'")
                                else:
                                    raise ValueError(f"{pattern} ability found in model ability name '{ability.name}' but could not extract dice value for unit '{self.name}'")
                
                # Only check description if ability name didn't match
                if not ability_name_matched and hasattr(ability, 'description') and ability.description:
                    desc_text = self._normalize_rules_text(ability.description)
                    for pattern in patterns:
                        if pattern.lower() in desc_text.lower():
                            match = re.search(value_pattern, desc_text.lower())
                            if match:
                                dice_value = int(match.group(1))
                                condition = match.group(2).strip() if match.group(2) else None
                                found_abilities.append((dice_value, condition))
                            else:
                                raise ValueError(f"{pattern} ability found in model ability description '{ability.description}' but could not extract dice value for unit '{self.name}'")
        
        return found_abilities

    def has_feel_no_pain(self) -> List[Tuple[int, Optional[str]]]:
        """Check if the unit has Feel No Pain abilities and return all of them.
        
        Returns:
            List[Tuple[int, Optional[str]]]: A list of tuples containing:
                - The dice roll needed (e.g., 5 for "5+", 6 for "6+")
                - Optional condition string (e.g., "against psychic attacks", "against mortal wounds") (None if unconditional)
        """
        # Use cached result if available
        cached = None
        if 'feel_no_pain' in getattr(self, '_ability_cache', {}):
            cached = list(self._ability_cache['feel_no_pain'])
        if cached is None:
            cached = self._find_all_abilities_with_patterns(
                ["feel no pain", "fnp"],
                r'(?:feel no pain|fnp)\s*\(?(\d+)\+(?:\)?)(?:\s+(.+))?',
            )
            # Cache the base result (dynamic additions are layered below).
            if not hasattr(self, '_ability_cache'):
                self._ability_cache = {}
            self._ability_cache['feel_no_pain'] = list(cached)

        result = list(cached)
        try:
            sr = getattr(self, "special_rules", None)
            entries = sr.get("bearer_unit_fnp") if isinstance(sr, dict) else None
            if isinstance(entries, list):
                seen = set((int(v), (c or "")) for v, c in result)
                for entry in entries:
                    if isinstance(entry, dict):
                        val = entry.get("value")
                        cond = entry.get("condition")
                    elif isinstance(entry, (list, tuple)):
                        val = entry[0] if entry else None
                        cond = entry[1] if len(entry) > 1 else None
                    else:
                        continue
                    try:
                        val = int(val)
                    except Exception:
                        continue
                    key = (int(val), str(cond or ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    result.append((int(val), cond))
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if mgr is not None and getattr(mgr, "blood_tithe_enraged_abjuration_applies", None):
                if mgr.blood_tithe_enraged_abjuration_applies(self):
                    entry = (5, "against psychic attacks and mortal wounds")
                    if entry not in result:
                        result.append(entry)
        except Exception:
            pass
        return result

    def get_max_weapon_range(self) -> float:
        """Get the maximum range of all weapons in the unit."""
        max_range = 0
        for model in self.models:
            for weapon in model.wargear:
                # Skip melee weapons
                if weapon.is_melee():
                    continue
                
                # Get the maximum range from all profiles
                for profile in weapon.profiles.values():
                    if hasattr(profile, 'range') and profile.range and hasattr(profile.range, 'max'):
                        max_range = max(max_range, profile.range.max)
        
        return max_range

    ###########################################################################
    ### Reserves System
    ###########################################################################
    # Units arriving from reserves (including Deep Strike) have the following restrictions:
    # - CANNOT move normally or advance (unless special rules allow it)
    # - CAN shoot, charge, and fight normally (this is the default rule)
    # - Only special rules would prevent charging/shooting after arriving from reserves
    def set_reserve_status(self, status: str) -> None:
        """Set the reserve status of the unit.
        
        Args:
            status: 'deployed', 'reserves', 'strategic_reserves'
        """
        valid_statuses = ['deployed', 'reserves', 'strategic_reserves']
        if status not in valid_statuses:
            raise ValueError(f"Invalid reserve status: {status}. Must be one of {valid_statuses}")
        prev_status = getattr(self, "reserve_status", None)
        self.reserve_status = status
        # Note: deployed flag is managed separately by deployment logic
        # deployed=True means deployment decision made, deployed=False means needs decision
        if prev_status != status:
            self._publish_unit_event(
                "unit_reserve_status_changed",
                unit=self,
                previous_status=prev_status,
                reserve_status=status,
            )
            self._publish_unit_event(
                "unit_state_changed",
                unit=self,
                reason="reserve_status_changed",
                previous_status=prev_status,
                reserve_status=status,
            )

        # Attached unit behavior: Leaders follow the Bodyguard's reserve decision.
        try:
            for leader in list(getattr(self, "attached_leaders", []) or []):
                try:
                    leader_prev = getattr(leader, "reserve_status", None)
                    leader.reserve_status = status
                except Exception:
                    continue
                if leader_prev != status:
                    publish_fn = getattr(leader, "_publish_unit_event", None)
                    if callable(publish_fn):
                        publish_fn(
                            "unit_reserve_status_changed",
                            unit=leader,
                            previous_status=leader_prev,
                            reserve_status=status,
                        )
                        publish_fn(
                            "unit_state_changed",
                            unit=leader,
                            reason="reserve_status_changed",
                            previous_status=leader_prev,
                            reserve_status=status,
                        )
        except Exception:
            pass

    def mark_entered_reserves_midgame(self, game=None) -> None:
        """Mark that this unit entered reserves during the battle (not at deployment)."""
        try:
            turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        except Exception:
            turn = 0
        try:
            setattr(self, "_entered_reserves_midgame_round", int(turn))
            setattr(self, "_entered_reserves_midgame", True)
        except Exception:
            pass

    def enter_strategic_reserves_midgame(self, *, game=None, game_map=None, reason: str = "") -> bool:
        """Place this unit (and any attached members) into Strategic Reserves mid-battle."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        if game is None:
            try:
                game = getattr(getattr(root.get_parent_army(), "player", None), "game", None)
            except Exception:
                game = None
        if game_map is None and game is not None:
            try:
                game_map = getattr(game, "map", None)
            except Exception:
                game_map = None
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]

        for member in members:
            try:
                member.set_reserve_status("strategic_reserves")
            except Exception:
                try:
                    member.reserve_status = "strategic_reserves"
                except Exception:
                    pass
            try:
                member.mark_entered_reserves_midgame(game=game)
            except Exception:
                pass
            try:
                if bool(getattr(member, "is_aircraft", False)) and not bool(getattr(member, "hover_mode", False)):
                    if game is not None:
                        member._aircraft_return_turn = int(getattr(game, "turn", 0) or 0) + 1
            except Exception:
                pass
            try:
                member.deployed = True
                member.reserve_turn_deployed = None
                member.arrived_from_reserves_this_turn = False
            except Exception:
                pass
            try:
                if game_map is not None and hasattr(game_map, "units") and member in game_map.units:
                    game_map.units.remove(member)
            except Exception:
                pass

        label = reason or "mid-battle ability"
        try:
            print(f"{root.name} placed into Strategic Reserves ({label})")
        except Exception:
            pass
        return True
        
    def is_in_reserves(self) -> bool:
        """Check if the unit is currently in reserves (any type)."""
        return self.reserve_status in ['reserves', 'strategic_reserves']
    
    def is_in_standard_reserves(self) -> bool:
        """Check if the unit is in standard reserves (Deep Strike, etc.)."""
        return self.reserve_status == 'reserves'
    
    def is_in_strategic_reserves(self) -> bool:
        """Check if the unit is in strategic reserves."""
        return self.reserve_status == 'strategic_reserves'
    
    def can_arrive_from_reserves(self, current_turn: int) -> bool:
        """Check if the unit can arrive from reserves this turn.
        
        Args:
            current_turn: The current battle round number
        
        Returns:
            bool: True if the unit can arrive from reserves this turn
        """
        if not self.is_in_reserves():
            return False

        # Reborn in Blood: only the next Movement phase is eligible.
        try:
            if bool(getattr(self, "_reborn_in_blood_pending", False)):
                allowed_round = getattr(self, "_reborn_in_blood_arrival_round", None)
                if allowed_round is not None and int(current_turn) != int(allowed_round):
                    return False
                try:
                    army = self.get_parent_army()
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    if game is not None:
                        if not getattr(game, "is_movement_phase", lambda: False)():
                            return False
                        if getattr(game, "get_current_player", lambda: None)() is not getattr(army, "player", None):
                            return False
                except Exception:
                    pass
        except Exception:
            pass
        
        # Units cannot arrive from reserves on Turn 1
        if current_turn < 2:
            return False

        # AIRCRAFT placed into Strategic Reserves mid-game return next turn.
        try:
            aircraft_return_turn = getattr(self, "_aircraft_return_turn", None)
        except Exception:
            aircraft_return_turn = None
        if aircraft_return_turn is not None:
            try:
                if int(current_turn) < int(aircraft_return_turn):
                    return False
            except Exception:
                return False
        
        # Chapter Approved: the "must arrive by end of battle round 3" restriction applies only to
        # units that STARTED the game in reserves, not units placed into reserves mid-game.
        try:
            started_in_reserves = bool(getattr(self, "_started_in_reserves", False))
        except Exception:
            started_in_reserves = False
        if started_in_reserves and current_turn > 3:
            return False
        
        return True

    def _finalize_reserves_arrival(self, turn: int, game_map: Optional['Map'] = None) -> bool:
        """Finalize state updates for a unit that has been set up from reserves."""
        # Unit position is now determined by model positions
        try:
            pre_reserve_status = str(getattr(self, "reserve_status", "") or "")
        except Exception:
            pre_reserve_status = ""
        try:
            pending_deep_strike = bool(getattr(self, "_pending_reserves_deep_strike", False))
        except Exception:
            pending_deep_strike = False
        try:
            if hasattr(self, "_pending_reserves_deep_strike"):
                delattr(self, "_pending_reserves_deep_strike")
        except Exception:
            pass

        # Update unit status
        self.deployed = True
        self.set_reserve_status("deployed")
        self.reserve_turn_deployed = turn
        self.arrived_from_reserves_this_turn = True
        try:
            if hasattr(self, "_reborn_in_blood_pending"):
                delattr(self, "_reborn_in_blood_pending")
        except Exception:
            pass
        try:
            if hasattr(self, "_reborn_in_blood_arrival_round"):
                delattr(self, "_reborn_in_blood_arrival_round")
        except Exception:
            pass
        try:
            if hasattr(self, "_aircraft_return_turn"):
                delattr(self, "_aircraft_return_turn")
        except Exception:
            pass

        try:
            army = self.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            sr = getattr(self, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if pname:
                sr["voice_of_command_set_up_phase"] = pname
                try:
                    sr["voice_of_command_set_up_round"] = int(getattr(game, "turn", turn) or turn)
                except Exception:
                    sr["voice_of_command_set_up_round"] = int(turn or 0)
            self.special_rules = sr
        except Exception:
            pass

        # Grey Knights: Fury of Titan (Deep Strike arrivals re-roll hit/wound 1s until end of turn).
        try:
            used_deep_strike = bool(pre_reserve_status == "reserves" or pending_deep_strike)
            if used_deep_strike and self.has_deep_strike():
                army = self.get_parent_army()
                mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
                if mgr is not None and getattr(mgr, "fury_of_titan_applies", None):
                    if mgr.fury_of_titan_applies(self, used_deep_strike=True):
                        mgr.apply_fury_of_titan(self)
        except Exception:
            pass

        # Reserves arrivals count as having made a Normal move this turn (reinforced).
        try:
            self.round_state.reinforced_this_round = True
            self.round_state.remained_stationary_this_round = False
        except Exception:
            pass

        # Chapter Approved exception: if the unit was too large to be set up wholly within 6" of an edge
        # and instead used the "base touches edge" placement, it cannot move, charge, or shoot this turn.
        try:
            edge_touch = bool(getattr(self, "_pending_reserves_edge_touch", False))
        except Exception:
            edge_touch = False
        try:
            if hasattr(self, "_pending_reserves_edge_touch"):
                delattr(self, "_pending_reserves_edge_touch")
        except Exception:
            pass
        try:
            setattr(self, "_reserves_edge_touch_this_turn", bool(edge_touch))
        except Exception:
            pass

        # Swooping Descent: if set up within 9" of an enemy, cannot charge until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            pain_min = float(sr.get("pain_deep_strike_min_distance", 0) or 0) if isinstance(sr, dict) else 0.0
            if pain_min and game_map is not None:
                from ..utility.aura_utils import horizontal_distance_between_bases_2d
                within_nine = False
                for enemy in list(game_map.get_enemy_units(self) or []):
                    try:
                        if not getattr(enemy, "is_alive", lambda: True)():
                            continue
                        if not getattr(enemy, "deployed", True):
                            continue
                    except Exception:
                        continue
                    for em in list(getattr(enemy, "models", []) or []):
                        if not getattr(em, "is_alive", True):
                            continue
                        for m in list(getattr(self, "models", []) or []):
                            if not getattr(m, "is_alive", True):
                                continue
                            if float(horizontal_distance_between_bases_2d(m.model_base, em.model_base)) <= 9.0 + 1e-6:
                                within_nine = True
                                break
                        if within_nine:
                            break
                    if within_nine:
                        break
                if within_nine:
                    try:
                        owner = self.get_parent_army().player.id
                    except Exception:
                        owner = ""
                    sr["pain_swooping_descent_no_charge_turn"] = int(turn or 0)
                    if owner:
                        sr["pain_swooping_descent_no_charge_turn_owner"] = owner
                    self.special_rules = sr
        except Exception:
            pass

        logger.info(f" {self.name} arrived from reserves at turn {turn}")
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if mgr is not None and game is not None:
                mgr.maybe_trigger_setup_maneuver(self, game)
        except Exception:
            pass
        try:
            army = self.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if game is not None and hasattr(game, "event_system"):
                game.event_system.publish("unit_set_up", unit=self)
        except Exception:
            pass
        return True
    
    def must_arrive_from_reserves(self, current_turn: int) -> bool:
        """Check if the unit must arrive from reserves this turn or be destroyed.
        
        Args:
            current_turn: The current battle round number
        
        Returns:
            bool: True if the unit must arrive this turn or be destroyed
        """
        try:
            if bool(getattr(self, "_reborn_in_blood_pending", False)):
                allowed_round = getattr(self, "_reborn_in_blood_arrival_round", None)
                if allowed_round is None or int(current_turn) != int(allowed_round):
                    return False
                try:
                    army = self.get_parent_army()
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    if game is not None and not getattr(game, "is_movement_phase", lambda: False)():
                        return False
                except Exception:
                    pass
                return True
        except Exception:
            pass
        # AIRCRAFT returning next turn is mandatory.
        try:
            aircraft_return_turn = getattr(self, "_aircraft_return_turn", None)
        except Exception:
            aircraft_return_turn = None
        if aircraft_return_turn is not None:
            try:
                return self.is_in_reserves() and int(current_turn) >= int(aircraft_return_turn)
            except Exception:
                return self.is_in_reserves()

        try:
            started_in_reserves = bool(getattr(self, "_started_in_reserves", False))
        except Exception:
            started_in_reserves = False
        return self.is_in_reserves() and started_in_reserves and current_turn >= 3
    
    def arrive_from_reserves(self, position: Tuple[float, float, float], turn: int, game_map: Optional['Map'] = None) -> bool:
        """Deploy the unit from reserves at the specified position.
        
        Args:
            position: (x, y, z) coordinates where the unit should be placed
            turn: Current turn number
        
        Returns:
            bool: True if deployment was successful
        """
        if not self.can_arrive_from_reserves(turn):
            return False
        
        # Deploy all models at calculated positions
        try:
            # Use the existing model positioning logic with battlefield edge repulsors
            boundary_repulsors = game_map.get_battlefield_edge_repulsors() if game_map else []
            # During deployment, use relaxed friendly unit avoidance to allow tighter formations
            model_positions = self.calculate_model_positions(position[0], position[1], game_map, boundary_repulsors=boundary_repulsors, avoid_friendly_units=False)
            
            # Check if formation finding failed
            if model_positions is None:
                logger.warning(f"Could not find valid formation for {self.name} arriving from reserves - using default placement")
                # Default: place all models at the unit position
                for model in self.models:
                    model.set_location(position[0], position[1], position[2], 0.0)
            else:
                for model, model_pos in zip(self.models, model_positions):
                    model.set_location(model_pos[0], model_pos[1], model_pos[2], model_pos[3])
        except Exception as e:
            logger.warning(f"Could not calculate model positions for {self.name} arriving from reserves: {e}")
            # Default: place all models at the unit position
            for model in self.models:
                model.set_location(position[0], position[1], position[2], 0.0)
        
        # Unit position is now determined by model positions
        return self._finalize_reserves_arrival(turn, game_map)
    
    def can_move_after_arriving_from_reserves(self) -> bool:
        """Check if the unit can move normally after arriving from reserves this turn."""
        # Units arriving from reserves cannot move unless they have special rules
        if not self.arrived_from_reserves_this_turn:
            return True
        
        # Check for special abilities that allow movement after arriving from reserves
        for ability in self._iter_active_possible_abilities():
            if hasattr(ability, 'name') and ability.name:
                if "can move after" in ability.name.lower() or "move after arriving" in ability.name.lower():
                    return True
            if hasattr(ability, 'description') and ability.description:
                if "can move after" in ability.description.lower() or "move after arriving" in ability.description.lower():
                    return True
        
        return False
    
    def can_advance_after_arriving_from_reserves(self) -> bool:
        """Check if the unit can advance after arriving from reserves this turn."""
        if not self.arrived_from_reserves_this_turn:
            return True
        
        # Units arriving from reserves cannot advance unless they have special rules
        # Check for special abilities that allow advancing after arriving from reserves
        for ability in self._iter_active_possible_abilities():
            if hasattr(ability, 'name') and ability.name:
                if "can advance after" in ability.name.lower() or "advance after arriving" in ability.name.lower():
                    return True
            if hasattr(ability, 'description') and ability.description:
                if "can advance after" in ability.description.lower() or "advance after arriving" in ability.description.lower():
                    return True
        
        return False
    
    def can_charge_after_arriving_from_reserves(self) -> bool:
        """Check if the unit can charge after arriving from reserves this turn."""
        if not self.arrived_from_reserves_this_turn:
            return True

        # Edge-touch exception: cannot charge this turn.
        try:
            if bool(getattr(self, "_reserves_edge_touch_this_turn", False)):
                return False
        except Exception:
            pass
        
        # Units arriving from reserves CAN charge by default (this is the normal rule)
        # Only special restrictions would prevent charging
        for ability in self._iter_active_possible_abilities():
            if hasattr(ability, 'name') and ability.name:
                if ("cannot charge after" in ability.name.lower() or 
                    "no charge after arriving" in ability.name.lower()):
                    return False
            if hasattr(ability, 'description') and ability.description:
                if ("cannot charge after" in ability.description.lower() or 
                    "no charge after arriving" in ability.description.lower()):
                    return False
        
        return True  # Default: can charge after arriving from reserves

    def take_desperate_escape_test(
        self,
        game_map: Optional['Map'] = None,
        *,
        roll_modifier: int = 0,
        reason: str | None = None,
    ) -> int:
        """
        Take a Desperate Escape Test - rolling D6 for each model, destroying on 1-2.
        This is required for Battle-Shocked units that fall back.
        
        Returns:
            int: Number of models destroyed during the test
        """
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bearer_unit_auto_pass_desperate_escape"):
                print(f"{self.name} automatically passes Desperate Escape tests.")
                return 0
        except Exception:
            pass
        note = str(reason or "").strip()
        if note:
            print(f"{self.name} {note} - taking Desperate Escape Test!")
        else:
            print(f"{self.name} is Battle-Shocked and falling back - taking Desperate Escape Test!")
        
        models_to_test = self.models.copy()  # Copy to avoid modifying list while iterating
        models_destroyed = 0
        mod = int(roll_modifier or 0)
        
        for i, model in enumerate(models_to_test):
            roll = get_roll("D6")
            final_roll = roll + mod
            if final_roll <= 2:
                # Model is destroyed
                if mod:
                    print(f"Model {i+1}: Rolled {roll} ({mod:+d} -> {final_roll}) - DESTROYED! ")
                else:
                    print(f"Model {i+1}: Rolled {roll} - DESTROYED! ")
                self.remove_model(model, fleed=True, game_map=game_map)  # Mark as fled, not killed in combat
                models_destroyed += 1
            else:
                # Model survives
                if mod:
                    print(f"Model {i+1}: Rolled {roll} ({mod:+d} -> {final_roll}) - Survives ")
                else:
                    print(f"Model {i+1}: Rolled {roll} - Survives ")
        
        if models_destroyed > 0:
            print(f"Desperate Escape Test complete: {models_destroyed} model(s) destroyed, {len(self.models)} remain")
        else:
            print(f"Desperate Escape Test complete: All models survived!")
        
        return models_destroyed

    def has_lone_operative(self) -> bool:
        """Check if the unit has Lone Operative ability."""
        # Lone Operative does NOT "leak" into an Attached unit via a Leader.
        # If a Leader with Lone Operative is attached to a Bodyguard unit that does not have Lone Operative,
        # the Attached unit does not benefit from Lone Operative while attached.
        try:
            if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                root = self.get_attached_unit_root()
                if root is not None and root is not self:
                    return bool(root.has_lone_operative())
        except Exception:
            pass

        # Base Lone Operative (static): use cached result if available
        if 'lone_operative' in getattr(self, '_ability_cache', {}):
            base_found = bool(self._ability_cache['lone_operative'])
        else:
            base_found, _ = self._find_ability_with_patterns(["lone operative", "loneoperative"])
            # Cache the base result
            if not hasattr(self, '_ability_cache'):
                self._ability_cache = {}
            self._ability_cache['lone_operative'] = bool(base_found)

        # LORD OF MURDER (datasheet rule, not an Aura keyworded ability):
        # While this model is within 3" of one or more friendly WORLD EATERS INFANTRY units,
        # this model has the Lone Operative ability.
        has_lord_of_murder = False
        try:
            for a in getattr(self, "possible_abilities", []) or []:
                nm = str(getattr(a, "name", "") or "")
                if nm.strip().lower() == "lord of murder":
                    has_lord_of_murder = True
                    break
        except Exception:
            has_lord_of_murder = False

        if has_lord_of_murder:
            game_map = None
            try:
                game_map = self.get_parent_army().player.game.map
            except Exception:
                game_map = None
            if game_map is not None:
                try:
                    from ..utility.aura_utils import unit_within_range_of_unit
                    for other in list(game_map.get_friendly_units(self)):
                        if other is self:
                            continue
                        if not getattr(other, "is_alive", lambda: True)():
                            continue
                        if (other.has_any_keyword("WORLD EATERS") and other.has_keyword("Infantry")):
                            if unit_within_range_of_unit(self, other, 3.0, use_attached_aggregate=True):
                                return True
                except Exception:
                    pass

        return bool(base_found)
